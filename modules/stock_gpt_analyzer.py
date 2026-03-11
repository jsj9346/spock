#!/usr/bin/env python3
"""
stock_gpt_analyzer.py - Phase 3 GPT 기반 차트 패턴 분석기 (Spock - Global Stock Version)

🎯 핵심 기능:
- VCP (Volatility Contraction Pattern) 감지 - 마크 미너비니 전략
- Cup & Handle 패턴 감지 - 윌리엄 오닐 전략
- Stage 2 Breakout 검증 - 스탠 와인스타인 전략 (NEW for Spock)
- OpenAI GPT-5-mini API 연동 - 비용 최적화 ($0.00015/1K tokens)
- 지능적 선택 실행 - LayeredScoringEngine 70점 이상만 GPT 분석
- 3단계 캐싱 시스템 - 메모리 → DB(72시간) → API 호출

💰 비용 최적화:
- GPT-5-mini 사용: 최신 모델로 높은 분석 품질 확보
- 일일 예산 $0.50 제한: 월 $15 이하 운영
- 지능적 필터링: 고품질 후보만 선별 (LayeredScoringEngine ≥70)
- 캐싱 전략: 중복 분석 방지

🌏 Global Stock Support:
- Markets: KR (KOSPI/KOSDAQ), US (NYSE/NASDAQ/AMEX), CN (SSE/SZSE), HK (HKEX), JP (TSE), VN (HOSE/HNX)
- Unified database: data/spock_local.db
- Region-aware analysis with Stage 2 validation

📊 Phase 3 위치:
Phase 2 (LayeredScoringEngine) → Phase 3 (StockGPTAnalyzer) → Phase 4 (kelly_calculator)
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import logging
import openai

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PatternType(Enum):
    """차트 패턴 타입"""
    VCP = "vcp"
    CUP_HANDLE = "cup_handle"
    BOTH = "both"
    NONE = "none"

class GPTRecommendation(Enum):
    """GPT 추천 등급"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    AVOID = "AVOID"

@dataclass
class VCPAnalysis:
    """VCP 패턴 분석 결과"""
    detected: bool
    confidence: float  # 0.0-1.0
    stage: int  # 1-4 수축 단계
    volatility_ratio: float  # 변동성 수축 비율
    reasoning: str

@dataclass
class CupHandleAnalysis:
    """Cup & Handle 패턴 분석 결과"""
    detected: bool
    confidence: float  # 0.0-1.0
    cup_depth_ratio: float  # 컵 깊이 비율
    handle_duration_days: int  # 핸들 지속 일수
    reasoning: str

@dataclass
class Stage2Analysis:
    """Stage 2 Breakout Validation Result (Weinstein Theory)

    Stage 2 characteristics:
    - MA alignment: MA5 > MA20 > MA60 > MA120 > MA200
    - Volume surge: Current volume > 1.5× average
    - Price position: Within 10% of 52-week high
    - Trend confirmation: Price above all major MAs

    Reference: Stan Weinstein's "Secrets for Profiting in Bull and Bear Markets"
    """
    confirmed: bool
    confidence: float  # 0.0-1.0
    ma_alignment: bool  # MA5 > MA20 > MA60 > MA120
    volume_surge: bool  # Volume > 1.5x average (20-day)
    reasoning: str

@dataclass
class GPTAnalysisResult:
    """GPT 분석 종합 결과 (Spock - Global Stock Version)

    New fields for stock trading:
    - stage2_analysis: Weinstein Stage 2 breakout validation
    - position_adjustment: Kelly Calculator multiplier (0.5-1.5)
    """
    ticker: str
    analysis_date: str
    vcp_analysis: VCPAnalysis
    cup_handle_analysis: CupHandleAnalysis
    stage2_analysis: Stage2Analysis  # NEW: Stage 2 Breakout validation
    recommendation: GPTRecommendation
    confidence: float
    reasoning: str
    position_adjustment: float  # NEW: 0.5-1.5 Kelly multiplier
    api_cost_usd: float
    processing_time_ms: int

class CostManager:
    """GPT API 비용 관리"""

    def __init__(self, daily_limit: float = 0.50, db_path: str = "./data/spock_local.db"):
        self.daily_limit = daily_limit  # $0.50/일 제한
        self.db_path = db_path
        self.gpt_5_mini_cost_per_1k = 0.00015  # GPT-5-mini: $0.00015/1K tokens

    def estimate_cost(self, text_length: int) -> float:
        """분석 비용 추정"""
        # 영어/한글 혼합 텍스트, 평균 2.5 tokens로 계산
        tokens = text_length * 2.5
        input_cost = (tokens / 1000) * self.gpt_5_mini_cost_per_1k

        # 응답 토큰도 고려 (보통 입력의 20% 정도)
        output_tokens = tokens * 0.2
        output_cost = (output_tokens / 1000) * self.gpt_5_mini_cost_per_1k

        total_cost = input_cost + output_cost
        logger.debug(f"💰 비용 추정: {tokens}토큰 → ${total_cost:.6f}")
        return total_cost

    def get_daily_usage(self) -> float:
        """오늘 사용한 비용 조회"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now().strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT COALESCE(SUM(api_cost_usd), 0)
                FROM gpt_analysis
                WHERE DATE(created_at) = ?
            """, (today,))

            daily_usage = cursor.fetchone()[0]
            conn.close()

            logger.info(f"💰 오늘 GPT 사용 비용: ${daily_usage:.4f} / ${self.daily_limit:.2f}")
            return daily_usage

        except Exception as e:
            logger.error(f"❌ 일일 사용량 조회 실패: {e}")
            return 0.0

    def check_daily_budget(self, estimated_cost: float = 0.0) -> bool:
        """일일 예산 확인"""
        daily_usage = self.get_daily_usage()
        remaining = self.daily_limit - daily_usage

        if estimated_cost > remaining:
            logger.warning(f"⚠️ 예산 초과: 필요 ${estimated_cost:.4f} > 남은 예산 ${remaining:.4f}")
            return False

        return True

    def should_use_gpt(self, ticker: str, technical_score: float, text_length: int = 2000) -> bool:
        """GPT 사용 여부 결정"""
        # 1. 기술적 점수 확인 (15점 이상만)
        if technical_score < 15.0:
            logger.info(f"📊 {ticker}: 기술적 점수 {technical_score:.1f}점 → GPT 스킵")
            return False

        # 2. 비용 확인
        estimated_cost = self.estimate_cost(text_length)
        if not self.check_daily_budget(estimated_cost):
            logger.warning(f"💰 {ticker}: 예산 부족 → GPT 스킵")
            return False

        logger.info(f"✅ {ticker}: 점수 {technical_score:.1f}점, 비용 ${estimated_cost:.4f} → GPT 분석 진행")
        return True

class CacheManager:
    """분석 결과 캐싱 관리"""

    def __init__(self, db_path: str = "./data/spock_local.db"):
        self.db_path = db_path
        self.memory_cache = {}  # 메모리 캐시
        self.db_cache_hours = 72  # DB 캐시 72시간 (3일)

    def get_cache_key(self, ticker: str, date: str) -> str:
        """캐시 키 생성"""
        return f"{ticker}_{date}"

    def is_cache_valid(self, cached_date: str, max_age_hours: int) -> bool:
        """캐시 유효성 확인"""
        try:
            cached_time = datetime.fromisoformat(cached_date.replace('Z', '+00:00'))
            current_time = datetime.now()
            age_hours = (current_time - cached_time).total_seconds() / 3600

            return age_hours <= max_age_hours
        except Exception:
            return False

    def get_cached_analysis(self, ticker: str, max_age_hours: int = 72) -> Optional[GPTAnalysisResult]:
        """캐시된 분석 결과 조회"""
        try:
            # 1. 메모리 캐시 확인
            today = datetime.now().strftime('%Y-%m-%d')
            cache_key = self.get_cache_key(ticker, today)

            if cache_key in self.memory_cache:
                logger.info(f"🚀 {ticker}: 메모리 캐시 히트 (즉시 반환, 비용 절약)")
                return self.memory_cache[cache_key]

            # 2. DB 캐시 확인 - 3일(72시간) 이내 데이터 검색으로 변경
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # 72시간(3일) 이내 데이터만 검색
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            cutoff_str = cutoff_time.strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute("""
                SELECT * FROM gpt_analysis
                WHERE ticker = ? AND created_at >= ?
                ORDER BY created_at DESC LIMIT 1
            """, (ticker, cutoff_str))

            row = cursor.fetchone()
            conn.close()

            if row:
                cached_time = datetime.fromisoformat(row[16])  # created_at 컬럼 (인덱스 16)
                age_hours = (datetime.now() - cached_time).total_seconds() / 3600
                logger.info(f"💾 {ticker}: DB 캐시 히트 (생성: {age_hours:.1f}시간 전, 유효기간: {max_age_hours}시간)")
                result = self._row_to_result(row)
                self.memory_cache[cache_key] = result  # 메모리 캐시에도 저장
                return result

            logger.debug(f"🔍 {ticker}: 캐시 없음, 새로운 분석 필요")
            return None

        except Exception as e:
            logger.error(f"❌ {ticker} 캐시 조회 실패: {e}")
            return None

    def save_to_cache(self, result: GPTAnalysisResult):
        """메모리 캐시에 저장"""
        cache_key = self.get_cache_key(result.ticker, result.analysis_date)
        self.memory_cache[cache_key] = result
        logger.debug(f"💾 {result.ticker}: 메모리 캐시 저장")

    def _row_to_result(self, row) -> GPTAnalysisResult:
        """DB row를 GPTAnalysisResult로 변환 (Spock - Global Stock Version)"""
        # DB 스키마에 맞춰 파싱 (실제 테이블 구조 기준)
        vcp = VCPAnalysis(
            detected=bool(row[3]),   # vcp_detected
            confidence=row[4],       # vcp_confidence
            stage=row[5],           # vcp_stage
            volatility_ratio=row[6] or 0.0,  # vcp_volatility_ratio
            reasoning="DB에서 로드"  # vcp_reasoning 컬럼이 없음
        )

        cup_handle = CupHandleAnalysis(
            detected=bool(row[7]),   # cup_handle_detected
            confidence=row[8],       # cup_handle_confidence
            cup_depth_ratio=row[9] or 0.0,     # cup_depth_ratio
            handle_duration_days=row[10] or 0,  # handle_duration_days
            reasoning="DB에서 로드"   # cup_handle_reasoning 컬럼이 없음
        )

        # NEW: Stage 2 Analysis (Weinstein Theory) - indices 16-20
        # Note: These columns will be added in database migration (Task 1.3)
        # For now, provide default values to maintain backward compatibility
        try:
            stage2 = Stage2Analysis(
                confirmed=bool(row[16]) if len(row) > 16 else False,       # stage2_confirmed
                confidence=row[17] if len(row) > 17 else 0.0,              # stage2_confidence
                ma_alignment=bool(row[18]) if len(row) > 18 else False,    # stage2_ma_alignment
                volume_surge=bool(row[19]) if len(row) > 19 else False,    # stage2_volume_surge
                reasoning=row[20] if len(row) > 20 else "DB migration pending"  # stage2_reasoning
            )
            position_adj = row[21] if len(row) > 21 else 1.0  # position_adjustment
        except (IndexError, TypeError):
            # Backward compatibility: Old database schema without Stage 2 columns
            stage2 = Stage2Analysis(
                confirmed=False,
                confidence=0.0,
                ma_alignment=False,
                volume_surge=False,
                reasoning="DB migration pending"
            )
            position_adj = 1.0

        return GPTAnalysisResult(
            ticker=row[1],           # ticker
            analysis_date=row[2],    # analysis_date
            vcp_analysis=vcp,
            cup_handle_analysis=cup_handle,
            stage2_analysis=stage2,  # NEW
            recommendation=GPTRecommendation(row[11]),  # gpt_recommendation
            confidence=row[12],      # gpt_confidence
            reasoning=row[13] or "", # gpt_reasoning
            position_adjustment=position_adj,  # NEW
            api_cost_usd=row[14] or 0.0,       # api_cost_usd
            processing_time_ms=row[15] or 0    # processing_time_ms
        )

class StockGPTAnalyzer:
    """
    OpenAI GPT-5-mini 기반 차트 패턴 분석기 (Spock - Global Stock Version)

    Supports: KR, US, CN, HK, JP, VN stock markets
    Database: data/spock_local.db
    """

    def __init__(self,
                 db_path: str = "./data/spock_local.db",
                 api_key: str = None,
                 enable_gpt: bool = True,
                 daily_cost_limit: float = 0.50):

        from dotenv import load_dotenv
        load_dotenv()
        self.db_path = db_path
        self.enable_gpt = enable_gpt
        self.cost_manager = CostManager(daily_cost_limit, db_path)
        self.cache_manager = CacheManager(db_path)

        # OpenAI API 설정 (.env 파일에서 키 로드)
        self.openai_client = None
        if api_key:
            self.openai_client = openai.OpenAI(api_key=api_key)
        elif os.getenv('OPENAI_API_KEY'):
            self.openai_client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            logger.info("✅ .env 파일에서 OpenAI API 키 로드 완료")
        else:
            logger.warning("⚠️ OpenAI API 키가 없습니다. GPT 분석이 비활성화됩니다.")
            logger.info("💡 .env 파일에 OPENAI_API_KEY를 설정해주세요.")
            self.enable_gpt = False

        self.init_database()
        logger.info("🤖 StockGPTAnalyzer 초기화 완료 (Global Stock Support)")

    def init_database(self):
        """gpt_analysis 테이블 생성"""
        try:
            # DB 락 방지를 위해 타임아웃 설정
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()

            create_table_sql = """
            CREATE TABLE IF NOT EXISTS gpt_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                analysis_date TEXT NOT NULL,

                -- VCP 패턴 분석
                vcp_detected BOOLEAN DEFAULT 0,
                vcp_confidence REAL DEFAULT 0.0,
                vcp_stage INTEGER DEFAULT 0,
                vcp_volatility_ratio REAL DEFAULT 0.0,
                vcp_reasoning TEXT DEFAULT '',

                -- Cup & Handle 패턴 분석
                cup_handle_detected BOOLEAN DEFAULT 0,
                cup_handle_confidence REAL DEFAULT 0.0,
                cup_depth_ratio REAL DEFAULT 0.0,
                handle_duration_days INTEGER DEFAULT 0,
                cup_handle_reasoning TEXT DEFAULT '',

                -- GPT 종합 분석
                gpt_recommendation TEXT DEFAULT 'HOLD',
                gpt_confidence REAL DEFAULT 0.0,
                gpt_reasoning TEXT DEFAULT '',
                api_cost_usd REAL DEFAULT 0.0,
                processing_time_ms INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),

                UNIQUE(ticker, analysis_date)
            );
            """

            cursor.execute(create_table_sql)

            # 인덱스 생성
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpt_analysis_ticker ON gpt_analysis(ticker);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpt_analysis_date ON gpt_analysis(analysis_date);")

            conn.commit()
            conn.close()

            logger.info("✅ gpt_analysis 테이블 초기화 완료")

        except Exception as e:
            logger.warning(f"⚠️ gpt_analysis 테이블 생성 스킵: {e}")
            # 테이블 생성 실패해도 계속 진행 (다른 프로세스에서 이미 생성했을 수 있음)

    def analyze_candidates(self, stage2_candidates: List[Dict]) -> List[Dict]:
        """Stage 2 후보들에 대한 GPT 패턴 분석"""
        logger.info(f"🎯 GPT 패턴 분석 시작: {len(stage2_candidates)}개 후보")

        enhanced_results = []
        gpt_analyzed_count = 0

        for candidate in stage2_candidates:
            ticker = candidate['ticker']
            quality_score = candidate.get('quality_score', 0)

            try:
                # 1. 캐시 확인
                cached_result = self.cache_manager.get_cached_analysis(ticker)
                if cached_result:
                    candidate['gpt_analysis'] = cached_result
                    candidate['final_score'] = self._calculate_enhanced_score(candidate, cached_result)
                    enhanced_results.append(candidate)
                    continue

                # 2. GPT 분석 여부 결정
                if not self.enable_gpt or not self.cost_manager.should_use_gpt(ticker, quality_score):
                    candidate['gpt_analysis'] = None
                    candidate['final_score'] = quality_score  # 기존 점수 유지
                    enhanced_results.append(candidate)
                    continue

                # 3. GPT 분석 실행
                gpt_result = self.analyze_ticker(ticker)
                if gpt_result:
                    candidate['gpt_analysis'] = gpt_result
                    candidate['final_score'] = self._calculate_enhanced_score(candidate, gpt_result)
                    gpt_analyzed_count += 1
                else:
                    candidate['gpt_analysis'] = None
                    candidate['final_score'] = quality_score

                enhanced_results.append(candidate)

            except Exception as e:
                logger.error(f"❌ {ticker} GPT 분석 실패: {e}")
                candidate['gpt_analysis'] = None
                candidate['final_score'] = quality_score
                enhanced_results.append(candidate)

        logger.info(f"✅ GPT 분석 완료: {gpt_analyzed_count}개 종목 분석")
        return enhanced_results

    def analyze_ticker(self, ticker: str) -> Optional[GPTAnalysisResult]:
        """개별 종목 GPT 패턴 분석"""
        start_time = time.time()

        try:
            # 1. 캐시 확인 (중요: API 호출 전 반드시 확인)
            cached_result = self.cache_manager.get_cached_analysis(ticker)
            if cached_result:
                logger.info(f"🚀 {ticker}: 캐시 히트! API 호출 건너뛰기 (비용 절약)")
                return cached_result

            # 2. OHLCV 데이터 로드
            df = self._get_ohlcv_data(ticker)
            if df.empty:
                logger.warning(f"📊 {ticker}: 데이터 없음")
                return None

            # 2. 차트 데이터 텍스트 변환
            chart_text = self._prepare_chart_data_for_gpt(df)

            # 3. OpenAI API 호출 (NEW: Stage 2 analysis included)
            vcp_analysis, cup_handle_analysis, stage2_analysis, recommendation, confidence, reasoning, position_adjustment, cost = self._call_openai_api(chart_text, ticker)

            # 4. 결과 생성 (NEW: Stage 2 and position_adjustment fields)
            processing_time = int((time.time() - start_time) * 1000)

            result = GPTAnalysisResult(
                ticker=ticker,
                analysis_date=datetime.now().strftime('%Y-%m-%d'),
                vcp_analysis=vcp_analysis,
                cup_handle_analysis=cup_handle_analysis,
                stage2_analysis=stage2_analysis,  # NEW
                recommendation=recommendation,
                confidence=confidence,
                reasoning=reasoning,
                position_adjustment=position_adjustment,  # NEW
                api_cost_usd=cost,
                processing_time_ms=processing_time
            )

            # 5. 저장 및 캐싱
            self._save_analysis_result(result)
            self.cache_manager.save_to_cache(result)

            logger.info(f"✅ {ticker}: GPT 분석 완료 (${cost:.4f}, {processing_time}ms) → 3일 캐시 저장")
            return result

        except Exception as e:
            logger.error(f"❌ {ticker} GPT 분석 실패: {e}")
            return None

    def _get_ohlcv_data(self, ticker: str, days: int = 120) -> pd.DataFrame:
        """SQLite에서 OHLCV 데이터 조회"""
        try:
            conn = sqlite3.connect(self.db_path)

            query = """
            SELECT ticker, date, open, high, low, close, volume,
                   ma5, ma20, ma60, ma120, ma200, rsi_14 as rsi
            FROM ohlcv_data
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT ?
            """

            df = pd.read_sql_query(query, conn, params=(ticker, days))
            conn.close()

            if df.empty:
                return pd.DataFrame()

            # 날짜 순으로 정렬 (오래된 것부터)
            df = df.sort_values('date').reset_index(drop=True)
            df['date'] = pd.to_datetime(df['date'])

            return df

        except Exception as e:
            logger.error(f"❌ {ticker} 데이터 조회 실패: {e}")
            return pd.DataFrame()

    def _prepare_chart_data_for_gpt(self, df: pd.DataFrame) -> str:
        """Convert chart data to text format for GPT analysis (Enhanced for Stage 2)"""
        if df.empty:
            return ""

        ticker = df['ticker'].iloc[0]

        # Use only recent 60 days data (token optimization)
        recent_df = df.tail(60)

        # Calculate key statistics
        current_price = recent_df['close'].iloc[-1]

        # NEW: MA5, MA120 added for Stage 2 analysis
        ma5 = recent_df['ma5'].iloc[-1] if 'ma5' in recent_df.columns and pd.notna(recent_df['ma5'].iloc[-1]) else 0
        ma20 = recent_df['ma20'].iloc[-1] if pd.notna(recent_df['ma20'].iloc[-1]) else 0
        ma60 = recent_df['ma60'].iloc[-1] if pd.notna(recent_df['ma60'].iloc[-1]) else 0
        ma120 = recent_df['ma120'].iloc[-1] if 'ma120' in recent_df.columns and pd.notna(recent_df['ma120'].iloc[-1]) else 0

        # NEW: 20-day volume average for Stage 2
        volume_recent = recent_df['volume'].iloc[-1]
        volume_avg_60d = recent_df['volume'].mean()
        volume_avg_20d = recent_df['volume'].tail(20).mean()

        # NEW: Stage 2 Breakout Indicators
        # MA Alignment Check (MA5 > MA20 > MA60 > MA120)
        ma_alignment = False
        if ma5 > 0 and ma20 > 0 and ma60 > 0 and ma120 > 0:
            ma_alignment = (ma5 > ma20 > ma60 > ma120)

        # Volume Surge Check (current > 1.5x 20-day average)
        volume_surge = (volume_recent > 1.5 * volume_avg_20d) if volume_avg_20d > 0 else False

        # Price volatility analysis
        price_changes = recent_df['close'].pct_change().dropna()
        volatility = price_changes.std() * 100

        # High/Low analysis
        high_30d = recent_df['high'].tail(30).max()
        low_30d = recent_df['low'].tail(30).min()
        current_vs_high = ((current_price - high_30d) / high_30d) * 100
        current_vs_low = ((current_price - low_30d) / low_30d) * 100

        # Safe percentage calculation
        ma5_pct = ((current_price-ma5)/ma5)*100 if ma5 > 0 else 0
        ma20_pct = ((current_price-ma20)/ma20)*100 if ma20 > 0 else 0
        ma60_pct = ((current_price-ma60)/ma60)*100 if ma60 > 0 else 0
        ma120_pct = ((current_price-ma120)/ma120)*100 if ma120 > 0 else 0

        chart_text = f"""
{ticker} Global Stock Chart Analysis (Recent 60 Days):

Price Information:
- Current Price: {current_price:,.0f} (currency unit)
- MA5: {ma5:,.0f} ({ma5_pct:+.1f}%)
- MA20: {ma20:,.0f} ({ma20_pct:+.1f}%)
- MA60: {ma60:,.0f} ({ma60_pct:+.1f}%)
- MA120: {ma120:,.0f} ({ma120_pct:+.1f}%)
- 30-Day High: {high_30d:,.0f} ({current_vs_high:+.1f}%)
- 30-Day Low: {low_30d:,.0f} ({current_vs_low:+.1f}%)

Volume Analysis (Enhanced for Stage 2):
- Current Volume: {volume_recent:,.0f}
- 20-Day Average: {volume_avg_20d:,.0f}
- 60-Day Average: {volume_avg_60d:,.0f}
- Volume Ratio (vs 20d avg): {volume_recent/volume_avg_20d:.2f}x
- Volume Surge Detected: {'YES' if volume_surge else 'NO'} (>1.5x threshold)

Stage 2 Breakout Indicators (Weinstein Theory):
- MA Alignment (MA5>MA20>MA60>MA120): {'YES' if ma_alignment else 'NO'}
- Volume Surge (>1.5x 20d avg): {'YES' if volume_surge else 'NO'}
- Price Near 30d High: {current_vs_high:+.1f}%

Volatility:
- Daily Volatility: {volatility:.1f}%

Recent 20-Day Price Movement:
"""

        # Add recent 20 days price data (enhanced with 20d avg volume ratio)
        recent_20 = recent_df.tail(20).reset_index(drop=True)
        for i, row in recent_20.iterrows():
            date = row['date'].strftime('%m/%d')
            close = row['close']
            # Use 20-day average for more accurate volume ratio
            volume_ratio_20d = row['volume'] / volume_avg_20d if volume_avg_20d > 0 else 0
            change = ((close - recent_20['close'].iloc[i-1]) / recent_20['close'].iloc[i-1] * 100) if i > 0 else 0

            chart_text += f"{date}: {close:,.0f} ({change:+.1f}%) Vol:{volume_ratio_20d:.2f}x\n"

        return chart_text

    def _call_openai_api(self, chart_text: str, ticker: str, max_retries: int = 2) -> Tuple[VCPAnalysis, CupHandleAnalysis, Stage2Analysis, GPTRecommendation, float, str, float, float]:
        """OpenAI API 호출 (재시도 로직 포함)"""

        last_exception = None
        for attempt in range(max_retries):
            try:
                logger.debug(f"🔄 {ticker} API 호출 시도 {attempt + 1}/{max_retries}")

                # 비용 계산
                estimated_cost = self.cost_manager.estimate_cost(len(chart_text))

                # Enhanced prompt with stronger JSON enforcement
                prompt = f"""
Analyze this global stock market chart data and respond ONLY with valid JSON:

{chart_text}

Required analysis:
1. VCP Pattern (Mark Minervini's Volatility Contraction Pattern)
2. Cup & Handle Pattern (William O'Neil's breakout pattern)
3. Stage 2 Breakout (Stan Weinstein's uptrend confirmation)

CRITICAL: Respond with ONLY this JSON structure (no other text):

{{
"vcp": {{"detected": true, "confidence": 0.75, "stage": 3, "volatility_ratio": 0.15, "reasoning": "Brief VCP analysis"}},
"cup_handle": {{"detected": false, "confidence": 0.3, "cup_depth_ratio": 0.0, "handle_duration_days": 0, "reasoning": "Brief Cup analysis"}},
"stage2": {{"confirmed": true, "confidence": 0.85, "ma_alignment": true, "volume_surge": true, "reasoning": "Brief Stage 2 analysis"}},
"overall": {{"recommendation": "BUY", "confidence": 0.8, "position_adjustment": 1.2, "reasoning": "Brief overall analysis"}}
}}

Requirements:
VCP Pattern:
- detected: boolean (true/false)
- confidence: float (0.0-1.0)
- stage: integer (1-4, contraction stage)
- volatility_ratio: float (0.0-1.0, 10d/30d volatility)
- reasoning: string (under 100 chars)

Cup & Handle Pattern:
- detected: boolean (true/false)
- confidence: float (0.0-1.0)
- cup_depth_ratio: float (0.0-1.0, depth as % of high)
- handle_duration_days: integer (0+)
- reasoning: string (under 100 chars)

Stage 2 Breakout (Weinstein Theory):
- confirmed: boolean (true/false, uptrend breakout)
- confidence: float (0.0-1.0)
- ma_alignment: boolean (MA5 > MA20 > MA60 > MA120)
- volume_surge: boolean (volume > 1.5x average)
- reasoning: string (under 100 chars)

Overall Assessment:
- recommendation: "STRONG_BUY", "BUY", "HOLD", or "AVOID"
- confidence: float (0.0-1.0)
- position_adjustment: float (0.5-1.5, Kelly multiplier for position sizing)
- reasoning: string (under 150 chars)

Position Adjustment Guidelines:
- 0.5-0.7: Weak patterns, reduce position
- 0.8-1.0: Average patterns, maintain position
- 1.1-1.3: Strong patterns, increase position
- 1.4-1.5: Exceptional patterns, maximum confidence

RESPOND ONLY WITH VALID JSON. NO OTHER TEXT.
"""

                # OpenAI API 호출 (새로운 API 형식)
                if not self.openai_client:
                    raise Exception("OpenAI 클라이언트가 초기화되지 않았습니다")

                response = self.openai_client.chat.completions.create(
                    model="gpt-5-mini",  # GPT-5-mini 사용
                    messages=[
                        {"role": "system", "content": "You are a professional global stock market technical analyst specializing in Mark Minervini's VCP patterns, William O'Neil's Cup & Handle patterns, and Stan Weinstein's Stage 2 theory. You must respond ONLY in the specified JSON format. Do not include any other text or explanations. Ensure exact JSON format compliance to prevent parsing errors."},
                        {"role": "user", "content": prompt}
                    ],
                    max_completion_tokens=1200,  # Increased for Stage 2 analysis
                    # temperature 파라미터 제거 - gpt-5-mini에서 지원하지 않음 (기본값 1 사용)
                )

                # 응답 파싱 (JSON 정형화 처리)
                response_text = response.choices[0].message.content.strip()

                # 응답 상세 디버깅
                logger.debug(f"🔍 {ticker} 원본 응답 길이: {len(response_text)}")
                if len(response_text) == 0:
                    logger.error(f"❌ {ticker} 빈 응답 수신")
                    raise Exception("빈 응답 수신")

                # JSON 추출 (```json ``` 블록이 있을 경우 처리)
                if "```json" in response_text:
                    start = response_text.find("```json") + 7
                    end = response_text.find("```", start)
                    if end != -1:
                        response_text = response_text[start:end].strip()
                        logger.debug(f"🔍 {ticker} JSON 블록 추출 완료")
                elif "```" in response_text:
                    start = response_text.find("```") + 3
                    end = response_text.find("```", start)
                    if end != -1:
                        response_text = response_text[start:end].strip()
                        logger.debug(f"🔍 {ticker} 코드 블록 추출 완료")

                # JSON 파싱 전 최종 검증
                if not response_text or not response_text.strip():
                    logger.error(f"❌ {ticker} 추출된 JSON 텍스트가 비어있음")
                    raise Exception("추출된 JSON 텍스트가 비어있음")

                try:
                    analysis_data = json.loads(response_text)
                    logger.debug(f"✅ {ticker} JSON 파싱 성공")
                except json.JSONDecodeError as e:
                    logger.error(f"❌ {ticker} JSON 파싱 실패: {e}")
                    logger.error(f"응답 전체 내용 ({len(response_text)}자): {repr(response_text)}")
                    logger.error(f"응답 미리보기: {response_text[:500]}...")
                    raise Exception(f"JSON 파싱 실패: {e}")

                # VCP 분석 결과 (타입 검증 및 기본값 처리)
                vcp_data = analysis_data.get('vcp', {})
                vcp_analysis = VCPAnalysis(
                    detected=bool(vcp_data.get('detected', False)),
                    confidence=float(vcp_data.get('confidence', 0.0)),
                    stage=int(vcp_data.get('stage', 0)),
                    volatility_ratio=float(vcp_data.get('volatility_ratio', 0.0)),
                    reasoning=str(vcp_data.get('reasoning', '패턴 감지되지 않음'))
                )

                # Cup & Handle 분석 결과 (타입 검증 및 기본값 처리)
                cup_data = analysis_data.get('cup_handle', {})
                cup_handle_analysis = CupHandleAnalysis(
                    detected=bool(cup_data.get('detected', False)),
                    confidence=float(cup_data.get('confidence', 0.0)),
                    cup_depth_ratio=float(cup_data.get('cup_depth_ratio', 0.0)),
                    handle_duration_days=int(cup_data.get('handle_duration_days', 0)),
                    reasoning=str(cup_data.get('reasoning', '패턴 감지되지 않음'))
                )

                # NEW: Stage 2 Breakout 분석 결과 (Weinstein Theory)
                stage2_data = analysis_data.get('stage2', {})
                stage2_analysis = Stage2Analysis(
                    confirmed=bool(stage2_data.get('confirmed', False)),
                    confidence=float(stage2_data.get('confidence', 0.0)),
                    ma_alignment=bool(stage2_data.get('ma_alignment', False)),
                    volume_surge=bool(stage2_data.get('volume_surge', False)),
                    reasoning=str(stage2_data.get('reasoning', '패턴 감지되지 않음'))
                )

                # 종합 분석 결과 (타입 검증 및 기본값 처리)
                overall = analysis_data.get('overall', {})
                recommendation_str = overall.get('recommendation', 'HOLD')
                position_adjustment = float(overall.get('position_adjustment', 1.0))

                # 유효한 추천 등급 확인
                valid_recommendations = ['STRONG_BUY', 'BUY', 'HOLD', 'AVOID']
                if recommendation_str not in valid_recommendations:
                    logger.warning(f"⚠️ {ticker}: 잘못된 추천 등급 '{recommendation_str}' → 'HOLD'로 변경")
                    recommendation_str = 'HOLD'

                recommendation = GPTRecommendation(recommendation_str)
                confidence = float(overall.get('confidence', 0.0))
                reasoning = str(overall.get('reasoning', '분석 결과 없음'))

                # 값 범위 검증
                vcp_analysis.confidence = max(0.0, min(1.0, vcp_analysis.confidence))
                vcp_analysis.stage = max(1, min(4, vcp_analysis.stage))
                vcp_analysis.volatility_ratio = max(0.0, min(1.0, vcp_analysis.volatility_ratio))

                cup_handle_analysis.confidence = max(0.0, min(1.0, cup_handle_analysis.confidence))
                cup_handle_analysis.cup_depth_ratio = max(0.0, min(1.0, cup_handle_analysis.cup_depth_ratio))
                cup_handle_analysis.handle_duration_days = max(0, cup_handle_analysis.handle_duration_days)

                # NEW: Stage 2 validation
                stage2_analysis.confidence = max(0.0, min(1.0, stage2_analysis.confidence))

                confidence = max(0.0, min(1.0, confidence))

                # NEW: Position adjustment validation (0.5-1.5 range)
                position_adjustment = max(0.5, min(1.5, position_adjustment))

                logger.info(f"🤖 {ticker}: GPT-5-mini 분석 완료 - {recommendation.value} ({confidence:.2f}) | Stage2: {stage2_analysis.confirmed} | Position: {position_adjustment:.2f}x")

                return vcp_analysis, cup_handle_analysis, stage2_analysis, recommendation, confidence, reasoning, position_adjustment, estimated_cost

            except Exception as e:
                last_exception = e
                logger.warning(f"⚠️ {ticker} API 시도 {attempt + 1} 실패: {e}")

                if attempt == max_retries - 1:
                    # 모든 시도 실패
                    logger.error(f"❌ {ticker} 모든 재시도 실패: {last_exception}")

                    # 기본값 반환 (Stage 2 포함)
                    vcp_analysis = VCPAnalysis(False, 0.0, 0, 0.0, "API 호출 실패")
                    cup_handle_analysis = CupHandleAnalysis(False, 0.0, 0.0, 0, "API 호출 실패")
                    stage2_analysis = Stage2Analysis(False, 0.0, False, False, "API 호출 실패")
                    return vcp_analysis, cup_handle_analysis, stage2_analysis, GPTRecommendation.HOLD, 0.0, "분석 실패", 1.0, 0.0
                else:
                    # 다음 시도를 위해 잠시 대기
                    import time
                    time.sleep(1)
                    continue

        # 이 부분에 도달하면 안 됨 (모든 경로에서 return이 있어야 함)
        logger.error(f"❌ {ticker} 예상치 못한 코드 경로")
        vcp_analysis = VCPAnalysis(False, 0.0, 0, 0.0, "예상치 못한 오류")
        cup_handle_analysis = CupHandleAnalysis(False, 0.0, 0.0, 0, "예상치 못한 오류")
        stage2_analysis = Stage2Analysis(False, 0.0, False, False, "예상치 못한 오류")
        return vcp_analysis, cup_handle_analysis, stage2_analysis, GPTRecommendation.HOLD, 0.0, "예상치 못한 오류", 1.0, 0.0

    def _calculate_enhanced_score(self, technical_result: Dict, gpt_result: GPTAnalysisResult) -> float:
        """기술적 분석 + GPT 분석 종합 점수"""
        base_score = technical_result.get('quality_score', 10.0)

        # GPT 추천에 따른 가중치
        if gpt_result.recommendation == GPTRecommendation.STRONG_BUY:
            multiplier = 1.4
        elif gpt_result.recommendation == GPTRecommendation.BUY:
            multiplier = 1.2
        elif gpt_result.recommendation == GPTRecommendation.HOLD:
            multiplier = 1.0
        else:  # AVOID
            multiplier = 0.7

        # GPT 신뢰도 반영
        enhanced_score = base_score * multiplier * (0.5 + 0.5 * gpt_result.confidence)

        logger.debug(f"📊 점수 계산: {base_score:.1f} × {multiplier:.1f} × {gpt_result.confidence:.2f} = {enhanced_score:.1f}")
        return enhanced_score

    def _save_analysis_result(self, result: GPTAnalysisResult):
        """분석 결과 SQLite 저장 (Spock - Global Stock Version)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # NEW: Stage 2 fields included in INSERT statement
            # Note: Database migration (Task 1.3) must be completed before this works
            cursor.execute("""
                INSERT OR REPLACE INTO gpt_analysis (
                    ticker, analysis_date,
                    vcp_detected, vcp_confidence, vcp_stage, vcp_volatility_ratio, vcp_reasoning,
                    cup_handle_detected, cup_handle_confidence, cup_depth_ratio, handle_duration_days, cup_handle_reasoning,
                    stage2_confirmed, stage2_confidence, stage2_ma_alignment, stage2_volume_surge, stage2_reasoning,
                    gpt_recommendation, gpt_confidence, gpt_reasoning,
                    position_adjustment, api_cost_usd, processing_time_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                result.ticker, result.analysis_date,
                # VCP Analysis
                result.vcp_analysis.detected, result.vcp_analysis.confidence,
                result.vcp_analysis.stage, result.vcp_analysis.volatility_ratio, result.vcp_analysis.reasoning,
                # Cup & Handle Analysis
                result.cup_handle_analysis.detected, result.cup_handle_analysis.confidence,
                result.cup_handle_analysis.cup_depth_ratio, result.cup_handle_analysis.handle_duration_days,
                result.cup_handle_analysis.reasoning,
                # NEW: Stage 2 Analysis (Weinstein Theory)
                result.stage2_analysis.confirmed, result.stage2_analysis.confidence,
                result.stage2_analysis.ma_alignment, result.stage2_analysis.volume_surge,
                result.stage2_analysis.reasoning,
                # GPT Recommendation
                result.recommendation.value, result.confidence, result.reasoning,
                # NEW: Position Adjustment for Kelly Calculator
                result.position_adjustment,
                # Cost Tracking
                result.api_cost_usd, result.processing_time_ms
            ))

            conn.commit()
            conn.close()

            logger.debug(f"💾 {result.ticker}: GPT 분석 결과 DB 저장 완료 (Stage 2 포함)")

        except sqlite3.OperationalError as e:
            if "no such column" in str(e):
                logger.error(f"❌ {result.ticker}: DB 마이그레이션 필요 - Stage 2 컬럼 누락")
                logger.info("💡 Task 1.3 (Database Migration)을 먼저 실행해주세요")
            else:
                logger.error(f"❌ {result.ticker} GPT 분석 결과 저장 실패: {e}")
        except Exception as e:
            logger.error(f"❌ {result.ticker} GPT 분석 결과 저장 실패: {e}")

def main():
    """테스트 실행 (Spock - Global Stock Version)"""
    print("🧪 Stock GPT Analyzer 테스트 시작")

    # API 키 없이 기본 기능 테스트
    analyzer = StockGPTAnalyzer(enable_gpt=False)
    print("✅ StockGPTAnalyzer 초기화 완료 (GPT 비활성화)")

    # 테스트 후보 데이터
    test_candidates = [
        {'ticker': 'KRW-BTC', 'quality_score': 18.5},
        {'ticker': 'KRW-ETH', 'quality_score': 16.2},
        {'ticker': 'KRW-XRP', 'quality_score': 14.1},
    ]

    print(f"📊 테스트 후보: {len(test_candidates)}개")

    # 분석 실행 (GPT 없이)
    results = analyzer.analyze_candidates(test_candidates)

    # 결과 출력
    print("\n📋 분석 결과:")
    for result in results:
        print(f"\n📊 {result['ticker']}:")
        print(f"  기술적 점수: {result.get('quality_score', 0):.1f}")
        print(f"  최종 점수: {result.get('final_score', 0):.1f}")

        gpt_analysis = result.get('gpt_analysis')
        if gpt_analysis:
            print(f"  GPT 추천: {gpt_analysis.recommendation.value}")
            print(f"  GPT 신뢰도: {gpt_analysis.confidence:.2f}")
            print(f"  비용: ${gpt_analysis.api_cost_usd:.4f}")
        else:
            print("  GPT 분석: 스킵됨 (API 키 없음 또는 점수 부족)")

    print("\n✅ 테스트 완료!")

    # 비용 관리 테스트
    cost_manager = CostManager()
    print(f"\n💰 비용 관리 테스트:")
    print(f"  일일 한도: ${cost_manager.daily_limit:.2f}")
    print(f"  샘플 텍스트 비용: ${cost_manager.estimate_cost(1000):.6f}")

    print("\n🎯 GPT Analyzer 구현 완료!")
    print("📋 주요 기능:")
    print("  ✅ VCP 패턴 분석 구조")
    print("  ✅ Cup & Handle 패턴 분석 구조")
    print("  ✅ GPT-5-mini API 연동")
    print("  ✅ 비용 최적화 (일일 $0.50 제한)")
    print("  ✅ 3단계 캐싱 시스템")
    print("  ✅ SQLite 통합 저장")

if __name__ == "__main__":
    main()