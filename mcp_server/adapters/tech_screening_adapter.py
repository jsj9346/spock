# mcp_server/adapters/tech_screening_adapter.py
"""
TechScreeningAdapter - DB 레벨 기술적 지표 스크리닝 어댑터.

PostgreSQL Window Functions를 사용하여 MA/RSI 계산 및 필터링을 수행.
기존 Python 기반 계산 대비 5~10x 성능 향상.

Architecture:
    MCP Tool -> TechScreeningAdapter -> PostgreSQL (Window Functions)

Performance:
    - 전체 KR 시장 (2000+ 티커): <3초
    - 필터링된 결과 (50개): <1초
    - 캐시 히트: <100ms

Author: Spock MCP Server
Date: 2025-11-30
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import structlog

from modules.db_manager_postgres import PostgresDatabaseManager
from mcp_server.config import Config
from mcp_server.utils.errors import DatabaseError, ValidationError

logger = structlog.get_logger()


class TechScreeningAdapter:
    """
    DB 레벨 기술적 지표 스크리닝 어댑터.

    PostgreSQL Window Functions로 MA/RSI를 계산하고,
    WHERE 절로 PRE-fetch 필터링을 수행하여 성능 최적화.

    Example:
        >>> adapter = TechScreeningAdapter()
        >>> result = await adapter.screen_by_technical_indicators(
        ...     region="KR",
        ...     filters={"trend": "bullish", "rsi_max": 30}
        ... )
        >>> len(result["stocks"])
        15
    """

    # SQL 쿼리: 기술적 지표 계산 및 필터링
    SCREENING_QUERY = """
    WITH
    -- Step 1: 최근 201일 데이터 로드 (MA200 계산에 필요)
    recent_data AS (
        SELECT
            o.ticker,
            o.date,
            o.open,
            o.high,
            o.low,
            o.close,
            o.volume,
            t.name as ticker_name
        FROM ohlcv_data o
        JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
        WHERE o.region = %(region)s
          AND o.timeframe = '1d'
          AND o.date >= NOW() - INTERVAL '400 days'
          AND t.is_active = true
    ),

    -- Step 2: 이동평균 계산 (Window Functions)
    with_ma AS (
        SELECT
            ticker,
            ticker_name,
            date,
            close,
            volume,
            -- MA 계산
            AVG(close) OVER (
                PARTITION BY ticker
                ORDER BY date
                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
            ) as ma20,
            AVG(close) OVER (
                PARTITION BY ticker
                ORDER BY date
                ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
            ) as ma50,
            AVG(close) OVER (
                PARTITION BY ticker
                ORDER BY date
                ROWS BETWEEN 199 PRECEDING AND CURRENT ROW
            ) as ma200,
            -- 거래량 평균
            AVG(volume) OVER (
                PARTITION BY ticker
                ORDER BY date
                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
            ) as avg_volume_20,
            -- Row count for MA validity check
            COUNT(*) OVER (
                PARTITION BY ticker
                ORDER BY date
                ROWS BETWEEN 199 PRECEDING AND CURRENT ROW
            ) as data_count
        FROM recent_data
    ),

    -- Step 3: RSI 계산 (14일 기준)
    with_price_change AS (
        SELECT
            *,
            close - LAG(close) OVER (PARTITION BY ticker ORDER BY date) as price_change
        FROM with_ma
    ),
    with_gains_losses AS (
        SELECT
            *,
            CASE WHEN price_change > 0 THEN price_change ELSE 0 END as gain,
            CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END as loss
        FROM with_price_change
    ),
    with_avg_gains AS (
        SELECT
            *,
            AVG(gain) OVER (
                PARTITION BY ticker ORDER BY date
                ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
            ) as avg_gain,
            AVG(loss) OVER (
                PARTITION BY ticker ORDER BY date
                ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
            ) as avg_loss
        FROM with_gains_losses
    ),

    -- Step 4: 최신 데이터만 추출 + 지표 계산
    latest_indicators AS (
        SELECT DISTINCT ON (ticker)
            ticker,
            ticker_name,
            date,
            close as price,
            volume,
            ROUND(ma20::numeric, 2) as ma20,
            ROUND(ma50::numeric, 2) as ma50,
            ROUND(ma200::numeric, 2) as ma200,
            -- RSI 계산
            CASE
                WHEN avg_loss = 0 OR avg_loss IS NULL THEN 100
                WHEN avg_gain IS NULL THEN 50
                ELSE ROUND((100 - (100 / (1 + avg_gain / NULLIF(avg_loss, 0))))::numeric, 2)
            END as rsi,
            -- 트렌드 분류
            CASE
                WHEN ma20 > ma50 AND ma50 > ma200 THEN 'bullish'
                WHEN ma20 < ma50 AND ma50 < ma200 THEN 'bearish'
                ELSE 'neutral'
            END as trend,
            -- Price vs MA
            CASE WHEN close > ma20 THEN 'above' ELSE 'below' END as price_vs_ma20,
            CASE WHEN close > ma200 THEN 'above' ELSE 'below' END as price_vs_ma200,
            -- 거래량 서지
            CASE WHEN volume > avg_volume_20 * 2 THEN true ELSE false END as volume_surge,
            -- 거래량 비율
            ROUND((volume / NULLIF(avg_volume_20, 0))::numeric, 2) as volume_ratio,
            -- MA20 이격도 (percent) - 가격이 MA20에서 얼마나 떨어져 있는지
            ROUND(((close - ma20) / NULLIF(ma20, 0) * 100.0)::numeric, 2) as ma20_distance,
            -- MA200 이격도 (percent)
            ROUND(((close - ma200) / NULLIF(ma200, 0) * 100.0)::numeric, 2) as ma200_distance,
            -- 데이터 충분성 체크
            data_count
        FROM with_avg_gains
        WHERE data_count >= 200  -- MA200 계산 가능한 티커만
        ORDER BY ticker, date DESC
    ),

    -- Step 5: MA Crossover 감지 (전일 대비 - 최근 5일 이내 크로스오버)
    crossover_data AS (
        SELECT
            ticker,
            date,
            ma20,
            ma50,
            -- 전일 MA20이 MA50 위에 있었는지 (1=above, 0=below)
            CASE WHEN LAG(ma20, 1) OVER (PARTITION BY ticker ORDER BY date) >
                      LAG(ma50, 1) OVER (PARTITION BY ticker ORDER BY date) THEN 1 ELSE 0 END as prev_ma20_above,
            -- 당일 MA20이 MA50 위에 있는지
            CASE WHEN ma20 > ma50 THEN 1 ELSE 0 END as ma20_above
        FROM with_ma
        WHERE date >= NOW() - INTERVAL '10 days'
          AND data_count >= 50
          AND ma20 IS NOT NULL
          AND ma50 IS NOT NULL
    ),
    crossovers AS (
        SELECT DISTINCT ON (ticker)
            ticker,
            CASE
                -- Golden Cross: 전일에는 MA20 < MA50이었는데 당일 MA20 > MA50
                WHEN prev_ma20_above = 0 AND ma20_above = 1 THEN 'golden_cross'
                -- Death Cross: 전일에는 MA20 > MA50이었는데 당일 MA20 < MA50
                WHEN prev_ma20_above = 1 AND ma20_above = 0 THEN 'death_cross'
                ELSE 'none'
            END as ma_crossover,
            date as crossover_date
        FROM crossover_data
        WHERE prev_ma20_above IS NOT NULL
          AND date >= NOW() - INTERVAL '5 days'  -- 최근 5일 이내 크로스오버만
        ORDER BY ticker, date DESC
    )

    -- Final: 필터링 및 결과 반환
    SELECT
        li.ticker,
        li.ticker_name as name,
        li.date,
        li.price,
        li.ma20,
        li.ma50,
        li.ma200,
        li.rsi,
        li.trend,
        li.price_vs_ma20,
        li.price_vs_ma200,
        COALESCE(c.ma_crossover, 'none') as ma_crossover,
        li.volume_surge,
        li.volume_ratio,
        li.ma20_distance,
        li.ma200_distance
    FROM latest_indicators li
    LEFT JOIN crossovers c ON li.ticker = c.ticker
    WHERE 1=1
        {dynamic_filters}
    ORDER BY {sort_column} {sort_order}
    LIMIT %(limit)s;
    """

    def __init__(self, config: Optional[Config] = None):
        """
        TechScreeningAdapter 초기화.

        Args:
            config: MCP 설정 (기본값: 환경 변수에서 로드)
        """
        self.config = config or Config.from_env()

        # PostgreSQL 연결 (소규모 풀)
        self.db_manager = PostgresDatabaseManager(
            host=self.config.postgres_host,
            port=self.config.postgres_port,
            database=self.config.postgres_db,
            user=self.config.postgres_user,
            password=self.config.postgres_password,
            pool_min_conn=2,
            pool_max_conn=5,
        )

        # 캐시 (60초 TTL)
        self._cache: Dict[str, Any] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_ttl = 60  # seconds

        logger.info("tech_screening_adapter_initialized")

    async def screen_by_technical_indicators(
        self,
        region: str = "KR",
        filters: Optional[Dict[str, Any]] = None,
        sort_by: str = "volume_desc",
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        기술적 지표 기반 주식 스크리닝.

        DB 레벨에서 MA/RSI 계산 및 필터링을 수행하여 성능 최적화.

        Args:
            region: 시장 코드 (KR, US, JP, HK, CN, VN)
            filters: 필터 조건 (모두 선택적, AND 조합)
                - trend: "bullish" | "bearish" | "neutral"
                - rsi_min: 0-100 (최소 RSI)
                - rsi_max: 0-100 (최대 RSI, 예: 30은 과매도)
                - price_vs_ma20: "above" | "below"
                - price_vs_ma200: "above" | "below"
                - ma_crossover: "golden_cross" | "death_cross"
                - volume_surge: true | false
            sort_by: 정렬 기준
                - "rsi_asc": RSI 오름차순 (과매도 우선)
                - "rsi_desc": RSI 내림차순 (과매수 우선)
                - "volume_desc": 거래량 비율 내림차순 (기본값)
                - "price_change_desc": 가격 내림차순
            limit: 최대 결과 수 (기본값: 50, 최대: 200)

        Returns:
            {
                "success": true,
                "stocks": [
                    {
                        "ticker": "005930",
                        "name": "삼성전자",
                        "date": "2025-11-29",
                        "price": 52000.0,
                        "technical": {
                            "ma20": 51500.0,
                            "ma50": 50800.0,
                            "ma200": 49500.0,
                            "rsi": 45.2,
                            "trend": "bullish",
                            "price_vs_ma20": "above",
                            "price_vs_ma200": "above",
                            "ma_crossover": "none",
                            "volume_surge": false,
                            "volume_ratio": 1.25
                        }
                    },
                    ...
                ],
                "count": N,
                "filters_applied": {...},
                "execution_time_ms": 234.5
            }

        Raises:
            ValidationError: 잘못된 입력 파라미터
            DatabaseError: 데이터베이스 쿼리 실패
        """
        start_time = datetime.now()

        # 입력 검증
        self._validate_inputs(region, filters, sort_by, limit)

        # 캐시 확인
        cache_key = self._make_cache_key(region, filters, sort_by, limit)
        if self._is_cache_valid(cache_key):
            logger.debug("cache_hit", key=cache_key)
            cached = self._cache[cache_key]
            cached["from_cache"] = True
            return cached

        # 동적 필터 SQL 생성
        dynamic_filters, params = self._build_dynamic_filters(filters)

        # 정렬 조건
        sort_column, sort_order = self._parse_sort_by(sort_by)

        # 전체 쿼리 조립
        query = self.SCREENING_QUERY.format(
            dynamic_filters=dynamic_filters,
            sort_column=sort_column,
            sort_order=sort_order
        )
        params["region"] = region
        params["limit"] = limit

        try:
            logger.info(
                "tech_screening_start",
                region=region,
                filters=filters,
                limit=limit
            )

            rows = self.db_manager.execute_query(query, params)

            # 결과 변환
            stocks = self._format_results(rows)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            result = {
                "success": True,
                "stocks": stocks,
                "count": len(stocks),
                "filters_applied": filters or {},
                "region": region,
                "sort_by": sort_by,
                "execution_time_ms": round(execution_time, 2),
                "timestamp": datetime.now().isoformat(),
                "from_cache": False
            }

            # 캐시 저장
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now()

            logger.info(
                "tech_screening_complete",
                count=len(stocks),
                execution_time_ms=round(execution_time, 2)
            )

            return result

        except Exception as e:
            logger.error("tech_screening_error", error=str(e))
            raise DatabaseError(
                f"Technical screening failed: {e}",
                {"region": region, "filters": filters}
            )

    def _validate_inputs(
        self,
        region: str,
        filters: Optional[Dict[str, Any]],
        sort_by: str,
        limit: int
    ) -> None:
        """입력 파라미터 검증."""
        # Region 검증
        valid_regions = {"KR", "US", "JP", "HK", "CN", "VN"}
        if region not in valid_regions:
            raise ValidationError(
                f"Invalid region: {region}",
                {"valid_regions": list(valid_regions)}
            )

        # Limit 검증
        if limit < 1 or limit > 200:
            raise ValidationError(
                f"limit must be between 1 and 200, got {limit}",
                {"limit": limit}
            )

        # Sort 검증
        valid_sorts = {
            "rsi_asc", "rsi_desc", "volume_desc", "price_change_desc",
            "price_asc", "price_desc",
            "ma20_distance_asc", "ma200_distance_asc",
            "ma20_above_close", "ma20_below_close"
        }
        if sort_by not in valid_sorts:
            raise ValidationError(
                f"Invalid sort_by: {sort_by}",
                {"valid_sorts": list(valid_sorts)}
            )

        # Filters 검증
        if filters:
            valid_filters = {
                "trend", "rsi_min", "rsi_max",
                "price_vs_ma20", "price_vs_ma200",
                "ma_crossover", "volume_surge"
            }
            for key in filters:
                if key not in valid_filters:
                    raise ValidationError(
                        f"Invalid filter: {key}",
                        {"valid_filters": list(valid_filters)}
                    )

            # Trend 검증
            if "trend" in filters:
                valid_trends = {"bullish", "bearish", "neutral"}
                if filters["trend"] not in valid_trends:
                    raise ValidationError(
                        f"Invalid trend: {filters['trend']}",
                        {"valid_trends": list(valid_trends)}
                    )

            # RSI 범위 검증
            if "rsi_min" in filters:
                if not 0 <= filters["rsi_min"] <= 100:
                    raise ValidationError(
                        f"rsi_min must be between 0 and 100",
                        {"rsi_min": filters["rsi_min"]}
                    )

            if "rsi_max" in filters:
                if not 0 <= filters["rsi_max"] <= 100:
                    raise ValidationError(
                        f"rsi_max must be between 0 and 100",
                        {"rsi_max": filters["rsi_max"]}
                    )

            # MA Crossover 검증
            if "ma_crossover" in filters:
                valid_crossovers = {"golden_cross", "death_cross"}
                if filters["ma_crossover"] not in valid_crossovers:
                    raise ValidationError(
                        f"Invalid ma_crossover: {filters['ma_crossover']}",
                        {"valid_crossovers": list(valid_crossovers)}
                    )

    def _build_dynamic_filters(
        self,
        filters: Optional[Dict[str, Any]]
    ) -> tuple[str, Dict]:
        """
        필터 조건에서 동적 SQL WHERE 절 생성.

        SQL Injection 방지를 위해 parameterized query 사용.
        """
        if not filters:
            return "", {}

        clauses = []
        params = {}

        # Trend 필터
        if "trend" in filters:
            clauses.append("AND li.trend = %(trend)s")
            params["trend"] = filters["trend"]

        # RSI 범위 필터 (NULL 제외)
        if "rsi_min" in filters:
            clauses.append("AND li.rsi IS NOT NULL AND li.rsi >= %(rsi_min)s")
            params["rsi_min"] = filters["rsi_min"]

        if "rsi_max" in filters:
            clauses.append("AND li.rsi IS NOT NULL AND li.rsi <= %(rsi_max)s")
            params["rsi_max"] = filters["rsi_max"]

        # Price vs MA 필터
        if "price_vs_ma20" in filters:
            clauses.append("AND li.price_vs_ma20 = %(price_vs_ma20)s")
            params["price_vs_ma20"] = filters["price_vs_ma20"]

        if "price_vs_ma200" in filters:
            clauses.append("AND li.price_vs_ma200 = %(price_vs_ma200)s")
            params["price_vs_ma200"] = filters["price_vs_ma200"]

        # MA Crossover 필터
        if "ma_crossover" in filters:
            clauses.append("AND c.ma_crossover = %(ma_crossover)s")
            params["ma_crossover"] = filters["ma_crossover"]

        # Volume Surge 필터
        if "volume_surge" in filters and filters["volume_surge"]:
            clauses.append("AND li.volume_surge = true")

        return "\n        ".join(clauses), params

    def _parse_sort_by(self, sort_by: str) -> tuple[str, str]:
        """정렬 기준 파싱."""
        sort_map = {
            # 기본 정렬
            "rsi_asc": ("li.rsi", "ASC NULLS LAST"),
            "rsi_desc": ("li.rsi", "DESC NULLS LAST"),
            "volume_desc": ("li.volume_ratio", "DESC NULLS LAST"),
            "price_change_desc": ("li.price", "DESC NULLS LAST"),
            # 추가 정렬 옵션
            "price_asc": ("li.price", "ASC NULLS LAST"),
            "price_desc": ("li.price", "DESC NULLS LAST"),
            # MA20 이격도 정렬 (절대값 기준 - MA20에 가장 가까운 종목)
            "ma20_distance_asc": ("ABS(li.ma20_distance)", "ASC NULLS LAST"),
            # MA200 이격도 정렬
            "ma200_distance_asc": ("ABS(li.ma200_distance)", "ASC NULLS LAST"),
            # MA20 이격도 (양수 우선 - MA20 위 종목 중 가까운 것)
            "ma20_above_close": ("li.ma20_distance", "ASC NULLS LAST"),
            # MA20 이격도 (음수 우선 - MA20 아래 종목 중 가까운 것)
            "ma20_below_close": ("li.ma20_distance", "DESC NULLS LAST"),
        }
        return sort_map.get(sort_by, ("li.volume_ratio", "DESC NULLS LAST"))

    def _format_results(self, rows: List[Dict]) -> List[Dict]:
        """DB 결과를 API 응답 포맷으로 변환."""
        if not rows:
            return []

        stocks = []
        for row in rows:
            stock = {
                "ticker": row["ticker"],
                "name": row["name"],
                "date": row["date"].strftime("%Y-%m-%d") if row.get("date") else None,
                "price": float(row["price"]) if row.get("price") is not None else None,
                "technical": {
                    "ma20": float(row["ma20"]) if row.get("ma20") is not None else None,
                    "ma50": float(row["ma50"]) if row.get("ma50") is not None else None,
                    "ma200": float(row["ma200"]) if row.get("ma200") is not None else None,
                    "rsi": float(row["rsi"]) if row.get("rsi") is not None else None,
                    "trend": row.get("trend"),
                    "price_vs_ma20": row.get("price_vs_ma20"),
                    "price_vs_ma200": row.get("price_vs_ma200"),
                    "ma_crossover": row.get("ma_crossover"),
                    "volume_surge": row.get("volume_surge"),
                    "volume_ratio": float(row["volume_ratio"]) if row.get("volume_ratio") is not None else None,
                    "ma20_distance": float(row["ma20_distance"]) if row.get("ma20_distance") is not None else None,
                    "ma200_distance": float(row["ma200_distance"]) if row.get("ma200_distance") is not None else None
                }
            }
            stocks.append(stock)
        return stocks

    def _make_cache_key(
        self,
        region: str,
        filters: Optional[Dict[str, Any]],
        sort_by: str,
        limit: int
    ) -> str:
        """캐시 키 생성."""
        filter_str = ""
        if filters:
            filter_str = "|".join(f"{k}={v}" for k, v in sorted(filters.items()))
        return f"tech_screen:{region}:{filter_str}:{sort_by}:{limit}"

    def _is_cache_valid(self, key: str) -> bool:
        """캐시 유효성 확인."""
        if key not in self._cache or key not in self._cache_time:
            return False

        age = (datetime.now() - self._cache_time[key]).total_seconds()
        return age < self._cache_ttl

    # =========================================================================
    # Phase 1 확장: 특정 ticker 목록에 대한 기술적 지표 조회
    # =========================================================================

    # SQL 쿼리: 특정 ticker 목록에 대한 기술적 지표 계산
    INDICATORS_FOR_TICKERS_QUERY = """
    WITH
    -- Step 1: 지정된 ticker의 최근 201일 데이터 로드
    recent_data AS (
        SELECT
            o.ticker,
            o.date,
            o.open,
            o.high,
            o.low,
            o.close,
            o.volume,
            t.name as ticker_name
        FROM ohlcv_data o
        JOIN tickers t ON o.ticker = t.ticker AND o.region = t.region
        WHERE o.ticker IN %(tickers)s
          AND o.region = %(region)s
          AND o.timeframe = '1d'
          AND o.date >= NOW() - INTERVAL '400 days'
    ),

    -- Step 2: 이동평균 계산 (Window Functions)
    with_ma AS (
        SELECT
            ticker,
            ticker_name,
            date,
            close,
            volume,
            -- MA 계산
            AVG(close) OVER (
                PARTITION BY ticker
                ORDER BY date
                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
            ) as ma20,
            AVG(close) OVER (
                PARTITION BY ticker
                ORDER BY date
                ROWS BETWEEN 49 PRECEDING AND CURRENT ROW
            ) as ma50,
            AVG(close) OVER (
                PARTITION BY ticker
                ORDER BY date
                ROWS BETWEEN 199 PRECEDING AND CURRENT ROW
            ) as ma200,
            -- 거래량 평균
            AVG(volume) OVER (
                PARTITION BY ticker
                ORDER BY date
                ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
            ) as avg_volume_20,
            -- Row count for MA validity check
            COUNT(*) OVER (
                PARTITION BY ticker
                ORDER BY date
                ROWS BETWEEN 199 PRECEDING AND CURRENT ROW
            ) as data_count,
            -- 1개월 전 종가 (약 20 거래일)
            LAG(close, 20) OVER (PARTITION BY ticker ORDER BY date) as close_1m_ago
        FROM recent_data
    ),

    -- Step 3: RSI 계산 (14일 기준)
    with_price_change AS (
        SELECT
            *,
            close - LAG(close) OVER (PARTITION BY ticker ORDER BY date) as price_change
        FROM with_ma
    ),
    with_gains_losses AS (
        SELECT
            *,
            CASE WHEN price_change > 0 THEN price_change ELSE 0 END as gain,
            CASE WHEN price_change < 0 THEN ABS(price_change) ELSE 0 END as loss
        FROM with_price_change
    ),
    with_avg_gains AS (
        SELECT
            *,
            AVG(gain) OVER (
                PARTITION BY ticker ORDER BY date
                ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
            ) as avg_gain,
            AVG(loss) OVER (
                PARTITION BY ticker ORDER BY date
                ROWS BETWEEN 13 PRECEDING AND CURRENT ROW
            ) as avg_loss
        FROM with_gains_losses
    ),

    -- Step 4: 최신 데이터만 추출 + 지표 계산
    latest_indicators AS (
        SELECT DISTINCT ON (ticker)
            ticker,
            ticker_name,
            date,
            close as price,
            volume,
            ROUND(ma20::numeric, 2) as ma20,
            ROUND(ma50::numeric, 2) as ma50,
            ROUND(ma200::numeric, 2) as ma200,
            -- RSI 계산
            CASE
                WHEN avg_loss = 0 OR avg_loss IS NULL THEN 100
                WHEN avg_gain IS NULL THEN 50
                ELSE ROUND((100 - (100 / (1 + avg_gain / NULLIF(avg_loss, 0))))::numeric, 2)
            END as rsi,
            -- 트렌드 분류
            CASE
                WHEN ma20 > ma50 AND ma50 > ma200 THEN 'bullish'
                WHEN ma20 < ma50 AND ma50 < ma200 THEN 'bearish'
                ELSE 'neutral'
            END as trend,
            -- Price vs MA
            CASE WHEN close > ma20 THEN 'above' ELSE 'below' END as price_vs_ma20,
            CASE WHEN close > ma200 THEN 'above' ELSE 'below' END as price_vs_ma200,
            -- 거래량 서지
            CASE WHEN volume > avg_volume_20 * 2 THEN true ELSE false END as volume_surge,
            -- 거래량 비율
            ROUND((volume / NULLIF(avg_volume_20, 0))::numeric, 2) as volume_ratio,
            -- MA20 이격도 (percent)
            ROUND(((close - ma20) / NULLIF(ma20, 0) * 100.0)::numeric, 2) as ma20_distance,
            -- MA200 이격도 (percent)
            ROUND(((close - ma200) / NULLIF(ma200, 0) * 100.0)::numeric, 2) as ma200_distance,
            -- 1개월 수익률 (percent)
            CASE
                WHEN close_1m_ago IS NOT NULL AND close_1m_ago > 0
                THEN ROUND(((close - close_1m_ago) / close_1m_ago * 100.0)::numeric, 2)
                ELSE NULL
            END as price_change_1m,
            -- 20일 평균 거래량
            ROUND(avg_volume_20::numeric, 0) as avg_volume_20d,
            -- 데이터 충분성 체크
            data_count
        FROM with_avg_gains
        WHERE data_count >= 20  -- 최소 MA20 계산 가능한 티커
        ORDER BY ticker, date DESC
    ),

    -- Step 5: MA Crossover 감지
    crossover_data AS (
        SELECT
            ticker,
            date,
            ma20,
            ma50,
            CASE WHEN LAG(ma20, 1) OVER (PARTITION BY ticker ORDER BY date) >
                      LAG(ma50, 1) OVER (PARTITION BY ticker ORDER BY date) THEN 1 ELSE 0 END as prev_ma20_above,
            CASE WHEN ma20 > ma50 THEN 1 ELSE 0 END as ma20_above
        FROM with_ma
        WHERE date >= NOW() - INTERVAL '10 days'
          AND data_count >= 50
          AND ma20 IS NOT NULL
          AND ma50 IS NOT NULL
    ),
    crossovers AS (
        SELECT DISTINCT ON (ticker)
            ticker,
            CASE
                WHEN prev_ma20_above = 0 AND ma20_above = 1 THEN 'golden_cross'
                WHEN prev_ma20_above = 1 AND ma20_above = 0 THEN 'death_cross'
                ELSE 'none'
            END as ma_crossover,
            date as crossover_date
        FROM crossover_data
        WHERE prev_ma20_above IS NOT NULL
          AND date >= NOW() - INTERVAL '5 days'
        ORDER BY ticker, date DESC
    )

    -- Final: 결과 반환 (필터 없이)
    SELECT
        li.ticker,
        li.ticker_name as name,
        li.date,
        li.price,
        li.ma20,
        li.ma50,
        li.ma200,
        li.rsi,
        li.trend,
        li.price_vs_ma20,
        li.price_vs_ma200,
        COALESCE(c.ma_crossover, 'none') as ma_crossover,
        li.volume_surge,
        li.volume_ratio,
        li.ma20_distance,
        li.ma200_distance,
        li.price_change_1m,
        li.avg_volume_20d
    FROM latest_indicators li
    LEFT JOIN crossovers c ON li.ticker = c.ticker
    ORDER BY li.ticker;
    """

    async def get_indicators_for_tickers(
        self,
        tickers: List[str],
        region: str = "KR",
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        특정 ticker 목록에 대한 기술적 지표 조회.

        screen_by_technical_indicators()와 달리 전체 시장이 아닌
        지정된 ticker 목록에 대해서만 기술적 지표를 계산.

        Args:
            tickers: ticker 목록 (예: ["005930", "000660"])
            region: 시장 코드 (KR, US, JP, HK, CN, VN)
            filters: 선택적 필터 (적용 시 결과에서 제외)
                - trend: "bullish" | "bearish" | "neutral"
                - rsi_min, rsi_max: RSI 범위
                - price_vs_ma20, price_vs_ma200: "above" | "below"
                - volume_surge: true

        Returns:
            {
                "success": true,
                "indicators": {
                    "005930": {
                        "name": "삼성전자",
                        "date": "2025-11-29",
                        "price": 52000.0,
                        "rsi": 45.2,
                        "ma20": 51500.0,
                        "ma50": 50800.0,
                        "ma200": 49500.0,
                        "trend": "bullish",
                        "price_vs_ma20": "above",
                        "price_vs_ma200": "above",
                        "ma_crossover": "none",
                        "volume_surge": false,
                        "volume_ratio": 1.25,
                        "ma20_distance": 0.97,
                        "ma200_distance": 5.05,
                        "price_change_1m": 3.5,
                        "avg_volume_20d": 15000000
                    },
                    ...
                },
                "count": N,
                "tickers_requested": N,
                "tickers_with_data": N,
                "execution_time_ms": 123.4
            }

        Raises:
            ValidationError: 잘못된 입력
            DatabaseError: DB 쿼리 실패
        """
        start_time = datetime.now()

        if not tickers:
            return {
                "success": True,
                "indicators": {},
                "count": 0,
                "tickers_requested": 0,
                "tickers_with_data": 0,
                "execution_time_ms": 0
            }

        # 캐시 확인
        cache_key = self._make_tickers_cache_key(tickers, region, filters)
        if self._is_cache_valid(cache_key):
            logger.debug("cache_hit_tickers", key=cache_key[:50])
            cached = self._cache[cache_key]
            cached["from_cache"] = True
            return cached

        try:
            logger.info(
                "get_indicators_for_tickers_start",
                ticker_count=len(tickers),
                region=region
            )

            # DB 쿼리 실행
            rows = self.db_manager.execute_query(
                self.INDICATORS_FOR_TICKERS_QUERY,
                {"tickers": tuple(tickers), "region": region}
            )

            # 결과 변환 (Dict 형식)
            indicators = {}
            for row in rows:
                ticker = row["ticker"]

                # 필터 적용 (선택적)
                if filters and not self._passes_filters(row, filters):
                    continue

                indicators[ticker] = {
                    "name": row.get("name"),
                    "date": row["date"].strftime("%Y-%m-%d") if row.get("date") else None,
                    "price": float(row["price"]) if row.get("price") is not None else None,
                    "rsi": float(row["rsi"]) if row.get("rsi") is not None else None,
                    "ma20": float(row["ma20"]) if row.get("ma20") is not None else None,
                    "ma50": float(row["ma50"]) if row.get("ma50") is not None else None,
                    "ma200": float(row["ma200"]) if row.get("ma200") is not None else None,
                    "trend": row.get("trend"),
                    "price_vs_ma20": row.get("price_vs_ma20"),
                    "price_vs_ma200": row.get("price_vs_ma200"),
                    "ma_crossover": row.get("ma_crossover"),
                    "volume_surge": row.get("volume_surge"),
                    "volume_ratio": float(row["volume_ratio"]) if row.get("volume_ratio") is not None else None,
                    "ma20_distance": float(row["ma20_distance"]) if row.get("ma20_distance") is not None else None,
                    "ma200_distance": float(row["ma200_distance"]) if row.get("ma200_distance") is not None else None,
                    "price_change_1m": float(row["price_change_1m"]) if row.get("price_change_1m") is not None else None,
                    "avg_volume_20d": int(row["avg_volume_20d"]) if row.get("avg_volume_20d") is not None else None,
                }

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            result = {
                "success": True,
                "indicators": indicators,
                "count": len(indicators),
                "tickers_requested": len(tickers),
                "tickers_with_data": len(rows),
                "filters_applied": filters or {},
                "region": region,
                "execution_time_ms": round(execution_time, 2),
                "timestamp": datetime.now().isoformat(),
                "from_cache": False
            }

            # 캐시 저장
            self._cache[cache_key] = result
            self._cache_time[cache_key] = datetime.now()

            logger.info(
                "get_indicators_for_tickers_complete",
                count=len(indicators),
                execution_time_ms=round(execution_time, 2)
            )

            return result

        except Exception as e:
            logger.error("get_indicators_for_tickers_error", error=str(e))
            raise DatabaseError(
                f"Failed to get indicators for tickers: {e}",
                {"tickers": tickers[:5], "region": region}
            )

    def _passes_filters(self, row: Dict, filters: Dict[str, Any]) -> bool:
        """행이 필터 조건을 통과하는지 확인."""
        if "trend" in filters and row.get("trend") != filters["trend"]:
            return False

        if "rsi_min" in filters:
            rsi = row.get("rsi")
            if rsi is None or rsi < filters["rsi_min"]:
                return False

        if "rsi_max" in filters:
            rsi = row.get("rsi")
            if rsi is None or rsi > filters["rsi_max"]:
                return False

        if "price_vs_ma20" in filters and row.get("price_vs_ma20") != filters["price_vs_ma20"]:
            return False

        if "price_vs_ma200" in filters and row.get("price_vs_ma200") != filters["price_vs_ma200"]:
            return False

        if "volume_surge" in filters and filters["volume_surge"] and not row.get("volume_surge"):
            return False

        if "ma_crossover" in filters and row.get("ma_crossover") != filters["ma_crossover"]:
            return False

        return True

    def _make_tickers_cache_key(
        self,
        tickers: List[str],
        region: str,
        filters: Optional[Dict[str, Any]]
    ) -> str:
        """ticker 기반 캐시 키 생성."""
        tickers_hash = hash(tuple(sorted(tickers)))
        filter_str = ""
        if filters:
            filter_str = "|".join(f"{k}={v}" for k, v in sorted(filters.items()))
        return f"tech_tickers:{region}:{tickers_hash}:{filter_str}"
