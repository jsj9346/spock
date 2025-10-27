"""
Stage 1 Technical Pre-screen Filter

Purpose:
  - Load Stage 0 results from filter_cache_stage0 (600 tickers)
  - Apply LayeredScoringEngine (Macro + Structural layers)
  - Filter based on technical indicators
  - Save to filter_cache_stage1 (target: 250 tickers)

Technical Criteria:
  1. MA Alignment: 5 > 20 > 60 > 120 > 200 (bullish structure)
  2. RSI Range: 30-70 (not overbought/oversold)
  3. MACD Signal: Bullish crossover
  4. Volume Spike: Recent volume > 20-day average
  5. Price Action: Above MA20 support

Author: Spock Trading System
"""

import os
import sys
import logging
import sqlite3
from typing import List, Dict, Optional
from datetime import datetime, timedelta

# Add parent directory to path for module imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import scoring system from Makenaide (95% reusable)
from modules.layered_scoring_engine import LayeredScoringEngine
from modules.integrated_scoring_system import IntegratedScoringSystem
from modules.market_filter_manager import MarketFilterManager

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class StockPreFilter:
    """
    Stage 1 Technical Pre-screen Filter

    Load Stage 0 → Apply Technical Filters → Save Stage 1
    600 tickers → 250 tickers (58% reduction)
    """

    def __init__(self, db_path: str = 'data/spock_local.db', region: str = 'KR'):
        self.db_path = db_path
        self.region = region

        # Load filter configuration
        self.filter_manager = MarketFilterManager(config_dir='config/market_filters')
        self.config = self.filter_manager.get_config(region)

        # Initialize scoring system
        self.scoring_engine = LayeredScoringEngine()

        # Phase 6: Initialize BlacklistManager
        try:
            from modules.blacklist_manager import BlacklistManager
            from modules.db_manager_sqlite import SQLiteDatabaseManager

            db_manager = SQLiteDatabaseManager(db_path=db_path)
            self.blacklist_manager = BlacklistManager(db_manager=db_manager)
            logger.info("✅ BlacklistManager initialized for Technical Filter")

        except Exception as e:
            logger.warning(f"⚠️ BlacklistManager initialization failed: {e}, blacklist filtering disabled")
            self.blacklist_manager = None

        logger.info(f"✅ StockPreFilter initialized (region={region})")

    def run_stage1_filter(self, force_refresh: bool = False) -> List[Dict]:
        """
        Run Stage 1 Technical Pre-screen

        Args:
            force_refresh: Ignore cache and re-run filter

        Returns:
            List of tickers that passed Stage 1 filter
        """
        start_time = datetime.now()

        # Check cache first
        if not force_refresh:
            cached = self._load_from_cache()
            if cached:
                logger.info(f"✅ Stage 1 캐시 히트: {len(cached)}개 종목")
                return cached

        # Load Stage 0 results
        stage0_tickers = self._load_stage0_results()
        if not stage0_tickers:
            logger.error("❌ Stage 0 결과 없음. scanner.py를 먼저 실행하세요.")
            return []

        logger.info(f"🔍 Stage 1 필터 시작: {len(stage0_tickers)}개 종목")

        # Phase 6: Apply Blacklist Filter (BEFORE technical analysis)
        blacklist_rejected = 0
        if self.blacklist_manager:
            ticker_codes = [t['ticker'] for t in stage0_tickers]
            blacklist_filtered = self.blacklist_manager.filter_blacklisted_tickers(ticker_codes, self.region)
            blacklist_rejected = len(ticker_codes) - len(blacklist_filtered)

            if blacklist_rejected > 0:
                logger.info(f"🚫 Blacklist filter: Removed {blacklist_rejected} blacklisted tickers")
                logger.debug(f"   Blacklisted: {set(ticker_codes) - set(blacklist_filtered)}")

                # Filter stage0_tickers to remove blacklisted tickers
                stage0_tickers = [t for t in stage0_tickers if t['ticker'] in blacklist_filtered]

            logger.info(f"✅ Blacklist filter: {len(stage0_tickers)} tickers passed")
        else:
            logger.debug("⏭️ Blacklist filter skipped (BlacklistManager not available)")

        if not stage0_tickers:
            logger.warning("⚠️ No tickers passed blacklist filter")
            return []

        # Apply Stage 1 filter
        filtered_tickers = []
        passed_count = 0
        failed_count = 0

        # Get data completeness requirements from config
        data_completeness = self.config.config.get('stage1_filters', {}).get('data_completeness', {})
        min_ohlcv_days = data_completeness.get('min_ohlcv_days', 250)  # Default: 250 days
        max_gap_days = data_completeness.get('max_gap_days', 60)
        required_continuity = data_completeness.get('required_continuity', False)

        for ticker_data in stage0_tickers:
            ticker = ticker_data['ticker']

            # Load OHLCV data for technical analysis
            ohlcv_data = self._load_ohlcv_data(ticker)
            if not ohlcv_data or len(ohlcv_data) < min_ohlcv_days:
                logger.debug(f"⚠️ {ticker}: OHLCV 데이터 부족 ({len(ohlcv_data) if ohlcv_data else 0}일, 필요: {min_ohlcv_days}일)")
                failed_count += 1
                continue

            # Check data continuity (optional, 13개월 월봉 필터)
            if required_continuity:
                continuity_check = self._check_data_continuity(ticker, ohlcv_data, max_gap_days)
                if not continuity_check['passed']:
                    logger.debug(f"⚠️ {ticker}: {continuity_check['reason']}")
                    failed_count += 1
                    continue

            # Apply technical filters
            filter_result = self._apply_technical_filters(ticker, ticker_data, ohlcv_data)

            if filter_result['passed']:
                # Merge filter results
                ticker_data.update(filter_result)

                # Add OHLCV data fields needed for cache
                latest = ohlcv_data[0]
                ticker_data['ma5'] = latest.get('ma5')
                ticker_data['ma20'] = latest.get('ma20')
                ticker_data['ma60'] = latest.get('ma60')
                ticker_data['rsi_14'] = latest.get('rsi')
                ticker_data['week_52_high_krw'] = ticker_data.get('current_price_krw', 0)  # Approximate with current price

                # Calculate volume averages from OHLCV data
                volumes = [row.get('volume', 0) for row in ohlcv_data[:10]]
                ticker_data['volume_3d_avg'] = sum(volumes[:3]) // 3 if len(volumes) >= 3 else 0
                ticker_data['volume_10d_avg'] = sum(volumes[:10]) // 10 if len(volumes) >= 10 else 0

                # Data window metadata
                ticker_data['data_start_date'] = ohlcv_data[-1].get('date') if ohlcv_data else None
                ticker_data['data_end_date'] = ohlcv_data[0].get('date') if ohlcv_data else None

                filtered_tickers.append(ticker_data)
                passed_count += 1
            else:
                failed_count += 1
                logger.debug(f"❌ {ticker} ({ticker_data.get('name')}): {filter_result['failed_reason']}")

        # Save to Stage 1 cache
        self._save_to_cache(filtered_tickers)

        # Log execution
        execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)

        # Calculate total input before blacklist filter (for accurate statistics)
        total_input = len(stage0_tickers) + blacklist_rejected

        self._log_filter_execution(
            input_count=total_input,
            output_count=len(filtered_tickers),
            execution_time_ms=execution_time_ms
        )

        # Phase 6: Enhanced summary with blacklist statistics
        logger.info(f"📊 Stage 1 필터링 완료:")
        logger.info(f"   • Input (Stage 0):        {total_input} tickers")
        if blacklist_rejected > 0:
            logger.info(f"   • Blacklist rejected:     {blacklist_rejected} tickers")
            logger.info(f"   • Blacklist passed:       {len(stage0_tickers)} tickers")
        logger.info(f"   • Technical filter passed: {len(filtered_tickers)} tickers (passed: {passed_count}, failed: {failed_count})")
        logger.info(f"   • Execution time:         {execution_time_ms}ms")

        return filtered_tickers

    def _load_stage0_results(self) -> List[Dict]:
        """Load Stage 0 results from filter_cache_stage0"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    ticker, name, exchange as market, region, currency,
                    market_cap_krw, market_cap_local,
                    trading_value_krw, trading_value_local,
                    current_price_krw, current_price_local,
                    exchange_rate_to_krw, 0 as stage0_score
                FROM filter_cache_stage0
                WHERE region = ? AND stage0_passed = 1
                ORDER BY market_cap_krw DESC
            """, (self.region,))

            tickers = []
            for row in cursor.fetchall():
                ticker_data = dict(row)
                tickers.append(ticker_data)

            conn.close()

            logger.info(f"✅ Stage 0 결과 로드: {len(tickers)}개 종목")
            return tickers

        except Exception as e:
            logger.error(f"Stage 0 결과 로드 실패: {e}")
            return []

    def _load_ohlcv_data(self, ticker: str) -> Optional[List[Dict]]:
        """Load OHLCV data for technical analysis (250 days)"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    date, open, high, low, close, volume,
                    ma5, ma20, ma60, ma120, ma200,
                    rsi_14 as rsi, macd, macd_signal, macd_hist as macd_histogram,
                    volume_ma20
                FROM ohlcv_data
                WHERE ticker = ? AND timeframe = 'D'
                ORDER BY date DESC
                LIMIT 250
            """, (ticker,))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                logger.debug(f"⚠️ {ticker}: OHLCV 데이터 없음 (0 rows returned)")
                return None

            # Convert to list of dicts (most recent first)
            ohlcv_data = [dict(row) for row in rows]
            logger.debug(f"✅ {ticker}: OHLCV 데이터 로드 완료 ({len(ohlcv_data)} rows)")
            return ohlcv_data

        except Exception as e:
            logger.debug(f"OHLCV 로드 실패 ({ticker}): {e}")
            return None

    def _apply_technical_filters(self, ticker: str, ticker_data: Dict, ohlcv_data: List[Dict]) -> Dict:
        """
        Apply Stage 1 Technical Filters

        Returns:
            {
                'passed': True/False,
                'failed_reason': str,
                'ma_alignment_score': int,
                'rsi_score': int,
                'macd_signal': str,
                'volume_spike': bool,
                'stage1_score': int
            }
        """
        latest = ohlcv_data[0]  # Most recent data

        result = {
            'passed': False,
            'stage1_passed': False,  # For scanner compatibility
            'failed_reason': '',
            'ma_alignment_score': 0,
            'rsi_score': 0,
            'macd_signal': 'NEUTRAL',
            'volume_spike': False,
            'stage1_score': 0
        }

        # Get Stage 1 filter config
        stage1_config = self.config.config.get('stage1_filters', {})

        # Filter 1: MA Alignment (5 > 20 > 60 > 120 > 200)
        ma_alignment = self._check_ma_alignment(latest)
        result['ma_alignment_score'] = ma_alignment['score']

        if not ma_alignment['passed']:
            result['failed_reason'] = ma_alignment['reason']
            return result

        # Filter 2: RSI Range (30-70, not overbought/oversold)
        rsi_check = self._check_rsi_range(latest, stage1_config)
        result['rsi_score'] = rsi_check['score']

        if not rsi_check['passed']:
            result['failed_reason'] = rsi_check['reason']
            return result

        # Filter 3: MACD Signal (bullish crossover)
        macd_check = self._check_macd_signal(latest, stage1_config)
        result['macd_signal'] = macd_check['signal']

        if not macd_check['passed']:
            result['failed_reason'] = macd_check['reason']
            return result

        # Filter 4: Volume Spike (recent volume > 20-day average)
        volume_check = self._check_volume_spike(latest, stage1_config)
        result['volume_spike'] = volume_check['spike']

        if not volume_check['passed']:
            result['failed_reason'] = volume_check['reason']
            return result

        # Filter 5: Price above MA20 (support level)
        price_check = self._check_price_above_ma20(latest)

        if not price_check['passed']:
            result['failed_reason'] = price_check['reason']
            return result

        # Calculate Stage 1 score (weighted average)
        result['stage1_score'] = self._calculate_stage1_score(result)
        result['passed'] = True
        result['stage1_passed'] = True  # For scanner compatibility

        return result

    def _check_ma_alignment(self, latest: Dict) -> Dict:
        """Check MA alignment: 5 > 20 > 60 > 120 > 200 (bullish)"""
        ma5 = latest.get('ma5')
        ma20 = latest.get('ma20')
        ma60 = latest.get('ma60')
        ma120 = latest.get('ma120')
        ma200 = latest.get('ma200')

        # Check if all MAs exist
        if not all([ma5, ma20, ma60, ma120, ma200]):
            return {'passed': False, 'score': 0, 'reason': 'MA 데이터 부족'}

        # Check alignment
        if ma5 > ma20 > ma60 > ma120 > ma200:
            return {'passed': True, 'score': 100, 'reason': ''}
        elif ma5 > ma20 > ma60:
            return {'passed': True, 'score': 75, 'reason': ''}
        else:
            return {'passed': False, 'score': 0, 'reason': 'MA 정배열 아님'}

    def _check_rsi_range(self, latest: Dict, config: Dict) -> Dict:
        """Check RSI range (30-70, not overbought/oversold)"""
        rsi = latest.get('rsi')

        if not rsi:
            return {'passed': False, 'score': 0, 'reason': 'RSI 데이터 없음'}

        # Get thresholds from config
        rsi_min = config.get('rsi_min', 30)
        rsi_max = config.get('rsi_max', 70)

        if rsi < rsi_min:
            return {'passed': False, 'score': 0, 'reason': f'RSI 과매도 ({rsi:.1f})'}
        elif rsi > rsi_max:
            return {'passed': False, 'score': 0, 'reason': f'RSI 과매수 ({rsi:.1f})'}
        else:
            # Score based on distance from extremes
            score = 100 - abs(rsi - 50) * 2  # Best at RSI=50
            return {'passed': True, 'score': int(score), 'reason': ''}

    def _check_macd_signal(self, latest: Dict, config: Dict) -> Dict:
        """Check MACD signal (bullish crossover)"""
        macd = latest.get('macd')
        macd_signal = latest.get('macd_signal')
        macd_histogram = latest.get('macd_histogram')

        if not all([macd, macd_signal, macd_histogram]):
            return {'passed': False, 'signal': 'UNKNOWN', 'reason': 'MACD 데이터 없음'}

        # Bullish: MACD > Signal and histogram > 0
        if macd > macd_signal and macd_histogram > 0:
            return {'passed': True, 'signal': 'BULLISH', 'reason': ''}
        else:
            return {'passed': False, 'signal': 'BEARISH', 'reason': 'MACD 약세'}

    def _check_volume_spike(self, latest: Dict, config: Dict) -> Dict:
        """Check volume spike (recent volume > 20-day average)"""
        volume = latest.get('volume')
        volume_ma20 = latest.get('volume_ma20')

        if not all([volume, volume_ma20]):
            return {'passed': False, 'spike': False, 'reason': 'Volume 데이터 없음'}

        # Get threshold from config
        volume_spike_ratio = config.get('volume_spike_ratio', 1.5)

        if volume > volume_ma20 * volume_spike_ratio:
            return {'passed': True, 'spike': True, 'reason': ''}
        else:
            return {'passed': False, 'spike': False, 'reason': 'Volume 부족'}

    def _check_price_above_ma20(self, latest: Dict) -> Dict:
        """Check if price is above MA20 (support level)"""
        close = latest.get('close')
        ma20 = latest.get('ma20')

        if not all([close, ma20]):
            return {'passed': False, 'reason': 'Price/MA20 데이터 없음'}

        if close > ma20:
            return {'passed': True, 'reason': ''}
        else:
            return {'passed': False, 'reason': 'Price < MA20'}

    def _check_data_continuity(self, ticker: str, ohlcv_data: List[Dict], max_gap_days: int) -> Dict:
        """
        Check data continuity (13개월 월봉 필터)

        Args:
            ticker: Stock ticker
            ohlcv_data: OHLCV data (sorted DESC by date)
            max_gap_days: Maximum allowed gap in days

        Returns:
            {'passed': bool, 'reason': str}
        """
        from datetime import datetime, timedelta

        # Convert dates to datetime objects
        dates = []
        for row in ohlcv_data:
            date_str = row.get('date')
            if not date_str:
                continue
            try:
                # Parse date (format: YYYY-MM-DD or YYYYMMDD)
                if '-' in date_str:
                    dt = datetime.strptime(date_str, '%Y-%m-%d')
                else:
                    dt = datetime.strptime(date_str, '%Y%m%d')
                dates.append(dt)
            except Exception as e:
                logger.debug(f"⚠️ {ticker}: 날짜 파싱 실패 ({date_str}): {e}")
                continue

        if not dates or len(dates) < 2:
            return {'passed': False, 'reason': 'OHLCV 날짜 데이터 부족'}

        # Sort dates ascending (oldest first)
        dates.sort()

        # Check gaps between consecutive dates
        max_gap_found = 0
        gap_count = 0

        for i in range(1, len(dates)):
            gap_days = (dates[i] - dates[i-1]).days

            # Skip weekends (2 days) and short holidays (< 7 days)
            if gap_days <= 7:
                continue

            # Found a significant gap
            if gap_days > max_gap_days:
                gap_count += 1
                max_gap_found = max(max_gap_found, gap_days)

        if gap_count > 0:
            return {
                'passed': False,
                'reason': f'데이터 공백 발견 ({gap_count}개, 최대 {max_gap_found}일 > {max_gap_days}일 허용치)'
            }

        return {'passed': True, 'reason': ''}

    def _calculate_stage1_score(self, result: Dict) -> int:
        """Calculate weighted Stage 1 score (0-100)"""
        weights = {
            'ma_alignment': 0.30,
            'rsi': 0.25,
            'macd': 0.20,
            'volume': 0.15,
            'price_position': 0.10
        }

        ma_score = result['ma_alignment_score']
        rsi_score = result['rsi_score']
        macd_score = 100 if result['macd_signal'] == 'BULLISH' else 0
        volume_score = 100 if result['volume_spike'] else 0
        price_score = 100  # Already checked in _check_price_above_ma20

        total_score = (
            ma_score * weights['ma_alignment'] +
            rsi_score * weights['rsi'] +
            macd_score * weights['macd'] +
            volume_score * weights['volume'] +
            price_score * weights['price_position']
        )

        return int(total_score)

    def _save_to_cache(self, tickers: List[Dict]):
        """Save Stage 1 results to filter_cache_stage1"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Delete existing Stage 1 cache for this region
            cursor.execute("DELETE FROM filter_cache_stage1 WHERE region = ?", (self.region,))

            today = datetime.now().date().isoformat()

            for ticker_data in tickers:
                cursor.execute("""
                    INSERT OR REPLACE INTO filter_cache_stage1 (
                        ticker, region,
                        ma5, ma20, ma60, rsi_14,
                        current_price_krw, week_52_high_krw,
                        volume_3d_avg, volume_10d_avg,
                        filter_date, data_start_date, data_end_date,
                        stage1_passed, filter_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    ticker_data['ticker'],
                    self.region,
                    ticker_data.get('ma5'),
                    ticker_data.get('ma20'),
                    ticker_data.get('ma60'),
                    ticker_data.get('rsi_14'),
                    ticker_data.get('current_price_krw', 0),
                    ticker_data.get('week_52_high_krw', 0),
                    ticker_data.get('volume_3d_avg', 0),
                    ticker_data.get('volume_10d_avg', 0),
                    today,
                    ticker_data.get('data_start_date'),
                    ticker_data.get('data_end_date'),
                    True,  # stage1_passed (they passed the filter)
                    None  # filter_reason (no failure reason)
                ))

            conn.commit()
            conn.close()

            logger.info(f"💾 Stage 1 캐시 저장 완료: {len(tickers)}개 종목")

        except Exception as e:
            logger.error(f"Stage 1 캐시 저장 실패: {e}")

    def _load_from_cache(self) -> Optional[List[Dict]]:
        """Load Stage 1 results from cache (TTL: 1h market hours, 24h after-hours)"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check TTL
            from modules.stock_utils import check_market_hours
            is_market_hours = check_market_hours()
            ttl_hours = 1 if is_market_hours else 24

            cursor.execute("""
                SELECT MAX(created_at) as last_update
                FROM filter_cache_stage1
                WHERE region = ?
            """, (self.region,))

            result = cursor.fetchone()
            if not result or not result['last_update']:
                conn.close()
                return None

            last_update = datetime.fromisoformat(result['last_update'])
            age_hours = (datetime.now() - last_update).total_seconds() / 3600

            if age_hours > ttl_hours:
                logger.info(f"⏰ Stage 1 캐시 만료 ({age_hours:.1f}시간 경과, TTL={ttl_hours}시간)")
                conn.close()
                return None

            # Load from cache
            cursor.execute("""
                SELECT *
                FROM filter_cache_stage1
                WHERE region = ? AND passed_filters = 1
                ORDER BY stage1_score DESC
            """, (self.region,))

            tickers = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return tickers

        except Exception as e:
            logger.warning(f"Stage 1 캐시 로드 실패: {e}")
            return None

    def _log_filter_execution(self, input_count: int, output_count: int, execution_time_ms: int):
        """Log filter execution to filter_execution_log"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            today = datetime.now().date().isoformat()
            reduction_rate = round((1 - output_count / input_count) * 100, 2) if input_count > 0 else 0
            execution_time_sec = execution_time_ms / 1000.0

            cursor.execute("""
                INSERT INTO filter_execution_log (
                    execution_date, stage, region,
                    input_count, output_count, reduction_rate,
                    execution_time_sec
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                today, 1, self.region,
                input_count, output_count, reduction_rate,
                execution_time_sec
            ))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.warning(f"필터 실행 로그 기록 실패: {e}")


# CLI for testing
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Phase 3: Stage 1 Technical Pre-screen Filter')
    parser.add_argument('--force-refresh', action='store_true', help='캐시 무시하고 강제 갱신')
    parser.add_argument('--db-path', default='data/spock_local.db', help='SQLite DB 경로')
    parser.add_argument('--region', default='KR', choices=['KR', 'US', 'HK', 'CN', 'JP', 'VN'], help='시장 지역 코드')
    parser.add_argument('--debug', action='store_true', help='디버그 모드')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Run Stage 1 filter
    pre_filter = StockPreFilter(db_path=args.db_path, region=args.region)

    try:
        tickers = pre_filter.run_stage1_filter(force_refresh=args.force_refresh)

        print("\n" + "="*60)
        print(f"✅ Stage 1 필터링 완료: {len(tickers)}개 종목 (region={args.region})")
        print("="*60)

        # Display top 10 by Stage 1 score
        print("\n[Stage 1 점수 상위 10개 종목]")
        for i, ticker in enumerate(tickers[:10], 1):
            stage1_score = ticker.get('stage1_score', 0)
            ma_score = ticker.get('ma_alignment_score', 0)
            rsi_score = ticker.get('rsi_score', 0)
            macd = ticker.get('macd_signal', 'N/A')
            volume_spike = '✅' if ticker.get('volume_spike') else '❌'

            print(f"{i:2d}. {ticker['ticker']:6s} {ticker['name']:15s} "
                  f"Stage1={stage1_score:3d} (MA={ma_score:3d}, RSI={rsi_score:3d}, MACD={macd}, Vol={volume_spike})")

        print(f"\n💾 DB 저장 위치: {args.db_path}")
        print(f"📊 Stage 1 캐시 테이블: filter_cache_stage1")

    except Exception as e:
        logger.error(f"Stage 1 필터링 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
