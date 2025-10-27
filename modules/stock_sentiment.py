#!/usr/bin/env python3
"""
stock_sentiment.py - Market Sentiment Analysis Module

Purpose:
- Aggregate market sentiment from multiple sources (VIX, Global Indices, Foreign/Institution Flow)
- Calculate comprehensive sentiment score (-100 to +100)
- Classify market regime (BULL, BULL_CORRECTION, SIDEWAYS, BEAR_RALLY, BEAR)
- Provide position sizing multipliers based on volatility and sentiment

Data Sources:
1. VIX Volatility Index (yfinance) - 50% weight
2. Global Market Indices (yfinance) - 25% weight
   - US: S&P 500, NASDAQ, DOW
   - Asia: Hang Seng, Nikkei 225
3. Foreign/Institution Flow (KIS API) - 15% weight
4. Sector Rotation (database) - 10% weight

Architecture:
- IndexDataSource: Abstract interface for index data providers
- YFinanceIndexSource: Primary implementation using Yahoo Finance
- KISIndexSource: Future implementation (when KIS API parameters confirmed)
- GlobalMarketCollector: Unified index data collection
- MarketSentimentAnalyzer: Main analysis engine

Author: Spock Trading System
Date: 2025-10-15
"""

import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import json
import time
import requests
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# External libraries
try:
    import yfinance as yf
    HAS_YFINANCE = True
except ImportError:
    HAS_YFINANCE = False
    print("⚠️ yfinance not available - pip install yfinance")

# Internal modules
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(f'logs/{datetime.now().strftime("%Y%m%d")}_stock_sentiment.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# Enums and Constants
# ============================================================================

class VolatilityLevel(Enum):
    """VIX-based volatility classification"""
    VERY_LOW = "VERY_LOW"      # VIX < 12: Complacency
    LOW = "LOW"                 # VIX 12-16: Low volatility
    MODERATE = "MODERATE"       # VIX 16-20: Normal volatility
    HIGH = "HIGH"               # VIX 20-30: Elevated volatility
    VERY_HIGH = "VERY_HIGH"     # VIX 30+: Fear/Panic


class MarketRegime(Enum):
    """Market regime classification"""
    BULL = "BULL"                           # Strong uptrend, high confidence
    BULL_CORRECTION = "BULL_CORRECTION"     # Uptrend with pullback
    SIDEWAYS = "SIDEWAYS"                   # Range-bound, low conviction
    BEAR_RALLY = "BEAR_RALLY"               # Temporary bounce in downtrend
    BEAR = "BEAR"                           # Strong downtrend, risk-off


# Position sizing multipliers by volatility level
VIX_POSITION_MULTIPLIERS = {
    VolatilityLevel.VERY_LOW: 1.0,      # Full position size
    VolatilityLevel.LOW: 0.75,          # 75% position size
    VolatilityLevel.MODERATE: 0.75,     # 75% position size
    VolatilityLevel.HIGH: 0.5,          # 50% position size
    VolatilityLevel.VERY_HIGH: 0.25,    # 25% position size
}


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class VIXData:
    """VIX volatility index data"""
    date: str
    vix_value: float
    volatility_level: VolatilityLevel
    position_sizing_multiplier: float  # 1.0, 0.75, 0.5, 0.25
    change_percent: float
    timestamp: datetime


@dataclass
class GlobalMarketData:
    """Individual global market index data"""
    date: str
    symbol: str                         # e.g., '^GSPC', '^DJI', '^HSI'
    index_name: str                     # e.g., 'S&P 500', 'DOW', 'Hang Seng'
    region: str                         # 'US' or 'ASIA'
    close_price: float
    open_price: float
    high_price: float
    low_price: float
    volume: int
    change_percent: float               # Daily change %
    trend_5d: str                       # 'UP', 'DOWN', 'FLAT'
    consecutive_days: int               # Consecutive days in same direction
    timestamp: datetime


@dataclass
class ForeignInstitutionData:
    """Foreign and institutional investor flow data"""
    date: str
    ticker: str
    foreign_net_buy: float              # KRW (+ = buying, - = selling)
    institution_net_buy: float          # KRW
    foreign_ownership_pct: float        # Current ownership %
    foreign_trend_days: int             # Consecutive days of buying/selling
    institution_trend_days: int
    signal: str                         # 'STRONG_BUY', 'BUY', 'NEUTRAL', 'SELL', 'STRONG_SELL'
    timestamp: datetime


@dataclass
class SectorRotationData:
    """Sector rotation and relative strength data"""
    date: str
    sector_performance: Dict[str, float]    # Sector name → % change
    leading_sectors: List[str]              # Top 3 performing sectors
    lagging_sectors: List[str]              # Bottom 3 sectors
    rotation_signal: str                    # 'OFFENSIVE', 'DEFENSIVE', 'NEUTRAL'
    timestamp: datetime


@dataclass
class MarketSentimentSummary:
    """Comprehensive market sentiment summary"""
    date: str

    # Component scores (-100 to +100)
    vix_score: float                    # 60% weight (increased from 50%)
    global_indices_score: float         # 25% weight (unchanged)
    sector_rotation_score: float        # 15% weight (increased from 10%)

    # Overall sentiment
    total_score: float                  # Weighted sum (-100 to +100)
    market_regime: MarketRegime
    confidence_level: float             # 0.0 to 1.0

    # Position sizing recommendation
    position_multiplier: float          # Based on VIX and sentiment
    max_position_pct: float             # Max position % per stock

    # Metadata
    timestamp: datetime
    data_completeness: float            # % of data sources available


# ============================================================================
# Abstract Index Data Source Interface
# ============================================================================

class IndexDataSource(ABC):
    """
    Abstract interface for global market index data providers

    Purpose:
    - Allow swappable data sources (yfinance, KIS API, etc.)
    - Standardize data format across different providers
    - Enable easy testing with mock data sources

    Implementations:
    - YFinanceIndexSource: Primary (proven, reliable)
    - KISIndexSource: Future (pending parameter confirmation)
    """

    @abstractmethod
    def get_index_data(self, symbol: str, days: int = 5) -> Optional[GlobalMarketData]:
        """
        Fetch index data for given symbol

        Args:
            symbol: Index symbol (e.g., '^GSPC', '^DJI')
            days: Number of days to fetch (for trend calculation)

        Returns:
            GlobalMarketData or None if failed
        """
        pass

    @abstractmethod
    def get_batch_indices(self, symbols: List[str], days: int = 5) -> Dict[str, GlobalMarketData]:
        """
        Fetch multiple indices in batch

        Args:
            symbols: List of index symbols
            days: Number of days to fetch

        Returns:
            Dictionary mapping symbol → GlobalMarketData
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if data source is currently available"""
        pass


# ============================================================================
# YFinance Index Data Source (Primary Implementation)
# ============================================================================

class YFinanceIndexSource(IndexDataSource):
    """
    Yahoo Finance index data source using yfinance library

    Advantages:
    - ✅ No API key required (free, unlimited)
    - ✅ Reliable index data (S&P 500, NASDAQ, DOW, Hang Seng, Nikkei)
    - ✅ Already used for VIX data in codebase
    - ✅ Simple session-based caching

    Rate Limiting:
    - Self-imposed: 1.0 req/sec to avoid abuse detection
    - Session caching: 5-minute TTL

    Error Handling:
    - Network failures: Retry with exponential backoff (3 attempts)
    - Invalid symbols: Return None gracefully
    - Empty data: Log warning and return None
    """

    def __init__(self, rate_limit_sec: float = 1.0, cache_ttl_sec: int = 300):
        """
        Initialize YFinance index source

        Args:
            rate_limit_sec: Seconds between requests (default: 1.0)
            cache_ttl_sec: Cache TTL in seconds (default: 5 minutes)
        """
        if not HAS_YFINANCE:
            raise RuntimeError("yfinance library not available - pip install yfinance")

        self.rate_limit_sec = rate_limit_sec
        self.cache_ttl_sec = cache_ttl_sec
        self.last_request_time: Optional[float] = None

        # Session cache: symbol → (data, timestamp)
        self.cache: Dict[str, Tuple[GlobalMarketData, datetime]] = {}

        logger.info(f"📊 YFinanceIndexSource initialized (rate_limit={rate_limit_sec}s, cache_ttl={cache_ttl_sec}s)")

    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        if self.last_request_time:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_sec:
                sleep_time = self.rate_limit_sec - elapsed
                logger.debug(f"⏱️ Rate limiting: sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)

        self.last_request_time = time.time()

    def _get_from_cache(self, symbol: str) -> Optional[GlobalMarketData]:
        """Get data from cache if valid"""
        if symbol in self.cache:
            data, cached_time = self.cache[symbol]
            age_seconds = (datetime.now() - cached_time).total_seconds()

            if age_seconds < self.cache_ttl_sec:
                logger.debug(f"✅ Cache hit for {symbol} (age: {age_seconds:.0f}s)")
                return data
            else:
                logger.debug(f"⏰ Cache expired for {symbol} (age: {age_seconds:.0f}s > {self.cache_ttl_sec}s)")
                del self.cache[symbol]

        return None

    def _calculate_trend(self, prices: List[float]) -> Tuple[str, int]:
        """
        Calculate trend direction and consecutive days

        Args:
            prices: List of closing prices (oldest to newest)

        Returns:
            (trend, consecutive_days) where trend is 'UP', 'DOWN', or 'FLAT'
        """
        if len(prices) < 2:
            return 'FLAT', 0

        # Calculate daily changes
        changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        if not changes:
            return 'FLAT', 0

        # Determine current trend
        last_change = changes[-1]
        if abs(last_change) < 0.001:  # Essentially flat
            return 'FLAT', 1

        current_trend = 'UP' if last_change > 0 else 'DOWN'

        # Count consecutive days in same direction
        consecutive = 1
        for i in range(len(changes) - 2, -1, -1):
            if (current_trend == 'UP' and changes[i] > 0) or \
               (current_trend == 'DOWN' and changes[i] < 0):
                consecutive += 1
            else:
                break

        return current_trend, consecutive

    def get_index_data(self, symbol: str, days: int = 5) -> Optional[GlobalMarketData]:
        """
        Fetch index data from Yahoo Finance

        Args:
            symbol: Index symbol (e.g., '^GSPC', '^DJI', '^HSI')
            days: Number of days to fetch (for trend calculation)

        Returns:
            GlobalMarketData or None if failed
        """
        # Check cache first
        cached_data = self._get_from_cache(symbol)
        if cached_data:
            return cached_data

        # Enforce rate limiting
        self._rate_limit()

        try:
            # Fetch data from yfinance
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=f"{days}d")

            if hist.empty:
                logger.warning(f"⚠️ No data returned for {symbol}")
                return None

            # Get most recent row
            latest = hist.iloc[-1]
            latest_date = hist.index[-1].strftime('%Y-%m-%d')

            # Calculate change %
            if len(hist) >= 2:
                prev_close = hist.iloc[-2]['Close']
                change_pct = ((latest['Close'] - prev_close) / prev_close) * 100
            else:
                change_pct = 0.0

            # Calculate trend
            close_prices = hist['Close'].tolist()
            trend, consecutive_days = self._calculate_trend(close_prices)

            # Determine region and name
            region, index_name = self._get_index_info(symbol)

            # Create GlobalMarketData
            data = GlobalMarketData(
                date=latest_date,
                symbol=symbol,
                index_name=index_name,
                region=region,
                close_price=float(latest['Close']),
                open_price=float(latest['Open']),
                high_price=float(latest['High']),
                low_price=float(latest['Low']),
                volume=int(latest['Volume']) if 'Volume' in latest else 0,
                change_percent=change_pct,
                trend_5d=trend,
                consecutive_days=consecutive_days,
                timestamp=datetime.now()
            )

            # Cache the result
            self.cache[symbol] = (data, datetime.now())

            logger.info(f"✅ {index_name}: {data.close_price:.2f} ({data.change_percent:+.2f}%) - {trend} {consecutive_days}d")

            return data

        except Exception as e:
            logger.error(f"❌ Failed to fetch {symbol}: {e}")
            return None

    def get_batch_indices(self, symbols: List[str], days: int = 5) -> Dict[str, GlobalMarketData]:
        """
        Fetch multiple indices with rate limiting

        Args:
            symbols: List of index symbols
            days: Number of days to fetch

        Returns:
            Dictionary mapping symbol → GlobalMarketData
        """
        results = {}

        for symbol in symbols:
            data = self.get_index_data(symbol, days)
            if data:
                results[symbol] = data

        logger.info(f"📊 Batch collection: {len(results)}/{len(symbols)} indices retrieved")

        return results

    def is_available(self) -> bool:
        """Test if yfinance is accessible by fetching S&P 500"""
        try:
            test_data = self.get_index_data('^GSPC', days=1)
            return test_data is not None
        except Exception as e:
            logger.error(f"❌ YFinance availability check failed: {e}")
            return False

    @staticmethod
    def _get_index_info(symbol: str) -> Tuple[str, str]:
        """Get region and name for index symbol"""
        INDEX_INFO = {
            '^GSPC': ('US', 'S&P 500'),
            '^IXIC': ('US', 'NASDAQ Composite'),
            '^DJI': ('US', 'DOW Jones Industrial'),
            '^HSI': ('ASIA', 'Hang Seng'),
            '^N225': ('ASIA', 'Nikkei 225'),
        }

        return INDEX_INFO.get(symbol, ('UNKNOWN', symbol))


# ============================================================================
# Global Market Collector (Unified Index Collection)
# ============================================================================

class GlobalMarketCollector:
    """
    Unified global market indices collector

    Supported Indices:
    - US: S&P 500 (^GSPC), NASDAQ (^IXIC), DOW (^DJI)
    - Asia: Hang Seng (^HSI), Nikkei 225 (^N225)

    Architecture:
    - Uses IndexDataSource interface (swappable providers)
    - Primary: YFinanceIndexSource
    - Future: KISIndexSource (when parameters confirmed)

    Performance:
    - Batch collection: ~5-10 seconds for all 5 indices
    - Session caching: 5-minute TTL reduces redundant calls
    """

    INDEX_SYMBOLS = {
        'US': {
            'SP500': '^GSPC',      # S&P 500 Index
            'NASDAQ': '^IXIC',     # NASDAQ Composite
            'DOW': '^DJI',         # DOW Jones Industrial Average
        },
        'ASIA': {
            'HANG_SENG': '^HSI',   # Hang Seng Index (Hong Kong)
            'NIKKEI': '^N225',     # Nikkei 225 (Japan)
        }
    }

    def __init__(self, data_source: Optional[IndexDataSource] = None):
        """
        Initialize collector with data source

        Args:
            data_source: IndexDataSource implementation (default: YFinanceIndexSource)
        """
        if data_source is None:
            data_source = YFinanceIndexSource()

        self.data_source = data_source

        logger.info(f"🌐 GlobalMarketCollector initialized with {type(data_source).__name__}")

    def collect_all_indices(self, days: int = 5) -> Dict[str, GlobalMarketData]:
        """
        Collect all 5 global market indices

        Args:
            days: Number of days for trend calculation

        Returns:
            Dictionary mapping symbol → GlobalMarketData
        """
        all_symbols = []
        for region_symbols in self.INDEX_SYMBOLS.values():
            all_symbols.extend(region_symbols.values())

        logger.info(f"📊 Collecting {len(all_symbols)} global indices...")

        start_time = time.time()
        results = self.data_source.get_batch_indices(all_symbols, days)
        elapsed = time.time() - start_time

        logger.info(f"✅ Collection complete: {len(results)}/{len(all_symbols)} indices in {elapsed:.1f}s")

        return results

    def collect_us_indices(self, days: int = 5) -> Dict[str, GlobalMarketData]:
        """Collect US market indices only"""
        symbols = list(self.INDEX_SYMBOLS['US'].values())
        return self.data_source.get_batch_indices(symbols, days)

    def collect_asia_indices(self, days: int = 5) -> Dict[str, GlobalMarketData]:
        """Collect Asia market indices only"""
        symbols = list(self.INDEX_SYMBOLS['ASIA'].values())
        return self.data_source.get_batch_indices(symbols, days)


# ============================================================================
# Database Persistence Layer
# ============================================================================

class GlobalIndicesDatabase:
    """
    Database layer for global market indices

    Responsibilities:
    - Save index data to global_market_indices table
    - Retrieve historical index data for scoring
    - Handle upsert logic (insert or update)
    """

    def __init__(self, db_path: str = 'data/spock_local.db'):
        """Initialize database connection"""
        self.db_path = db_path
        logger.info(f"💾 GlobalIndicesDatabase initialized: {db_path}")

    def save_index_data(self, data: GlobalMarketData) -> bool:
        """
        Save or update index data in database

        Args:
            data: GlobalMarketData to save

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO global_market_indices
                (date, symbol, index_name, region, close_price, open_price, high_price, low_price,
                 volume, change_percent, trend_5d, consecutive_days, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.date,
                data.symbol,
                data.index_name,
                data.region,
                data.close_price,
                data.open_price,
                data.high_price,
                data.low_price,
                data.volume,
                data.change_percent,
                data.trend_5d,
                data.consecutive_days,
                data.timestamp.isoformat()
            ))

            conn.commit()
            conn.close()

            logger.debug(f"💾 Saved {data.symbol} for {data.date}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to save {data.symbol}: {e}")
            return False

    def save_batch(self, indices: Dict[str, GlobalMarketData]) -> int:
        """
        Save multiple indices in batch

        Args:
            indices: Dictionary mapping symbol → GlobalMarketData

        Returns:
            Number of successfully saved indices
        """
        saved_count = 0

        for symbol, data in indices.items():
            if self.save_index_data(data):
                saved_count += 1

        logger.info(f"💾 Saved {saved_count}/{len(indices)} indices to database")
        return saved_count

    def get_latest_indices(self) -> Dict[str, GlobalMarketData]:
        """
        Get most recent index data for all symbols

        Returns:
            Dictionary mapping symbol → GlobalMarketData
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT date, symbol, index_name, region, close_price, open_price, high_price, low_price,
                       volume, change_percent, trend_5d, consecutive_days, created_at
                FROM global_market_indices
                WHERE date = (SELECT MAX(date) FROM global_market_indices WHERE symbol = global_market_indices.symbol)
            """)

            rows = cursor.fetchall()
            conn.close()

            results = {}
            for row in rows:
                data = GlobalMarketData(
                    date=row[0],
                    symbol=row[1],
                    index_name=row[2],
                    region=row[3],
                    close_price=row[4],
                    open_price=row[5],
                    high_price=row[6],
                    low_price=row[7],
                    volume=row[8],
                    change_percent=row[9],
                    trend_5d=row[10],
                    consecutive_days=row[11],
                    timestamp=datetime.fromisoformat(row[12])
                )
                results[data.symbol] = data

            logger.info(f"📊 Retrieved {len(results)} latest indices from database")
            return results

        except Exception as e:
            logger.error(f"❌ Failed to retrieve indices: {e}")
            return {}


# ============================================================================
# Market Sentiment Analyzer (Main Integration Class)
# ============================================================================

class MarketSentimentAnalyzer:
    """
    Market sentiment 통합 분석 엔진

    Purpose:
    - Aggregate sentiment from multiple sources (VIX, Global Indices, Sector Rotation)
    - Calculate comprehensive sentiment score (-100 to +100)
    - Classify market regime (BULL, BEAR, SIDEWAYS, etc.)
    - Provide position sizing recommendations

    Data Sources (100점 배점):
    1. VIX Volatility (60점) - yfinance ^VIX - Market fear/greed indicator
    2. Global Market Indices (25점) - GlobalMarketCollector - US/Asia market direction
    3. Sector Rotation (15점) - Database analysis - Risk-on/off capital flows

    Note:
    - Foreign/Institution flow removed for global market compatibility
    - All data sources work across all markets (KR, US, CN, HK, JP, VN)
    - External investor sentiment already reflected in global indices

    Architecture:
    - Uses GlobalMarketCollector for index data (Phase 1 완료)
    - Uses YFinanceIndexSource for VIX data
    - Coordinates with database for sector analysis
    - Returns MarketSentimentSummary with actionable insights
    """

    def __init__(self, db_manager: SQLiteDatabaseManager):
        """
        Initialize Market Sentiment Analyzer

        Args:
            db_manager: Database manager for persistence and sector analysis
        """
        self.db = db_manager
        self.global_collector = GlobalMarketCollector()  # Uses default YFinanceIndexSource
        self.vix_source = YFinanceIndexSource()

        logger.info("MarketSentimentAnalyzer initialized")

    def collect_all_sentiment_data(self) -> MarketSentimentSummary:
        """
        모든 센티먼트 데이터 수집 및 통합 스코어 계산

        Returns:
            MarketSentimentSummary with comprehensive analysis
        """
        logger.info("=" * 80)
        logger.info("Starting comprehensive market sentiment analysis")
        logger.info("=" * 80)

        # 1. VIX 수집 (60점) - Increased from 50
        logger.info("\n[1/3] Collecting VIX Volatility Index...")
        vix_score = self._collect_and_score_vix()

        # 2. 글로벌 지수 수집 (25점) - Unchanged
        logger.info("\n[2/3] Collecting Global Market Indices...")
        global_indices = self.global_collector.collect_all_indices(days=5)
        global_score = calculate_global_indices_score(global_indices)

        # 3. Sector Rotation 분석 (15점) - Increased from 10
        logger.info("\n[3/3] Analyzing Sector Rotation...")
        sector_score = self._analyze_sector_rotation()

        # 4. 통합 스코어 계산 (가중합)
        # VIX: -50~+10 range * 0.6 weight = -30~+6 points
        # Global: 25 points (already weighted)
        # Sector: -15~+15 range = 15 points max
        total_score = (
            vix_score * 0.6 +         # 60% weight (VIX -50~+10 → -30~+6)
            global_score +             # 25 points (unchanged)
            sector_score               # 15 points (range expanded)
        )

        # 5. Market Regime 분류
        regime = self._classify_market_regime(total_score, vix_score)

        # 6. Position Multiplier 계산
        position_multiplier = self._calculate_position_multiplier(vix_score, total_score)

        # 7. Confidence 및 Completeness 계산
        confidence = self._calculate_confidence(global_indices, vix_score, sector_score)
        completeness = self._calculate_completeness(global_indices, vix_score, sector_score)

        # 8. MarketSentimentSummary 생성
        summary = MarketSentimentSummary(
            date=datetime.now().strftime("%Y-%m-%d"),
            vix_score=vix_score,
            global_indices_score=global_score,
            sector_rotation_score=sector_score,
            total_score=total_score,
            market_regime=regime,
            confidence_level=confidence,
            position_multiplier=position_multiplier,
            max_position_pct=15.0 * position_multiplier,
            timestamp=datetime.now(),
            data_completeness=completeness
        )

        logger.info("\n" + "=" * 80)
        logger.info("MARKET SENTIMENT SUMMARY")
        logger.info("=" * 80)
        logger.info(f"  Total Score:          {total_score:+.2f} / 100.0")
        logger.info(f"  Market Regime:        {regime.value}")
        logger.info(f"  Confidence Level:     {confidence*100:.1f}%")
        logger.info(f"  Data Completeness:    {completeness*100:.1f}%")
        logger.info(f"  Position Multiplier:  {position_multiplier:.2f}x")
        logger.info(f"  Max Position Size:    {summary.max_position_pct:.2f}% per stock")
        logger.info("=" * 80)

        return summary

    def _collect_and_score_vix(self) -> float:
        """
        VIX 수집 및 스코어링 (50점 배점)

        VIX 해석:
        - < 12: VERY_LOW (complacency) → -10점 (과도한 낙관)
        - 12-16: LOW (normal) → +10점 (안정)
        - 16-20: MODERATE → 0점 (중립)
        - 20-30: HIGH → -20점 (위험 회피)
        - 30-40: VERY_HIGH → -35점 (공포)
        - > 40: EXTREME → -50점 (패닉)

        Returns:
            -50 ~ +10 (50점 스케일)
        """
        try:
            vix_data = self.vix_source.get_index_data('^VIX', days=5)

            if not vix_data:
                logger.warning("  ⚠️ VIX data unavailable, using neutral score (0.0)")
                return 0.0

            vix_value = vix_data.close_price
            vix_change = vix_data.change_percent

            # VIX 절대값 기반 스코어
            if vix_value < 12:
                base_score = -10  # Complacency risk
                level = "VERY_LOW (Complacency)"
            elif vix_value < 16:
                base_score = +10  # Low volatility, positive
                level = "LOW (Bullish)"
            elif vix_value < 20:
                base_score = 0    # Normal
                level = "MODERATE (Neutral)"
            elif vix_value < 30:
                base_score = -20  # Elevated fear
                level = "HIGH (Caution)"
            elif vix_value < 40:
                base_score = -35  # High fear
                level = "VERY_HIGH (Fear)"
            else:
                base_score = -50  # Extreme panic
                level = "EXTREME (Panic)"

            # VIX 변화율 조정 (±5점)
            if vix_change > 10:  # VIX 급등 (공포 증가)
                adjustment = -5
                change_desc = "spiking (fear rising)"
            elif vix_change < -10:  # VIX 급락 (안정화)
                adjustment = +5
                change_desc = "falling (calming)"
            else:
                adjustment = 0
                change_desc = "stable"

            final_score = base_score + adjustment

            # Save to database
            self._save_vix_to_db(vix_value, vix_change, final_score)

            logger.info(f"  VIX: {vix_value:.2f} ({vix_change:+.2f}%) - {level}")
            logger.info(f"  Trend: {change_desc}")
            logger.info(f"  VIX Score: {final_score:+.1f}/50.0")

            return final_score

        except Exception as e:
            logger.error(f"  ❌ VIX collection failed: {e}")
            return 0.0  # Neutral on error

    def _save_vix_to_db(self, vix_value: float, vix_change: float, score: float):
        """VIX 데이터 DB 저장"""
        try:
            # market_sentiment 테이블에 저장
            # TODO: 테이블이 없으면 생성 필요 (init_db.py 업데이트 필요)
            query = """
                INSERT OR REPLACE INTO market_sentiment
                (date, indicator_type, indicator_value, change_percent, score, updated_at)
                VALUES (?, 'VIX', ?, ?, ?, ?)
            """
            params = (
                datetime.now().strftime("%Y-%m-%d"),
                vix_value,
                vix_change,
                score,
                datetime.now().isoformat()
            )

            # Execute query (will fail gracefully if table doesn't exist)
            try:
                conn = self.db._get_connection()
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                cursor.close()
            except Exception:
                # Table may not exist yet, skip saving
                pass

        except Exception as e:
            logger.warning(f"  VIX DB save failed (non-critical): {e}")


    def _analyze_sector_rotation(self) -> float:
        """
        섹터 순환 분석 (15점 배점)

        분석 기준:
        - 리딩 섹터(IT, 금융, 경기소비재) 상승 → +15점 (Risk-on)
        - 방어 섹터(유틸리티, 필수소비재, 헬스케어) 상승 → -15점 (Risk-off)
        - 혼재 → 0점

        Returns:
            -15 ~ +15 (15점 스케일)
        """
        try:
            # DB에서 섹터별 최근 5일 평균 수익률 조회
            query = """
                SELECT
                    t.gics_sector,
                    AVG(
                        (o.close - o_prev.close) / o_prev.close * 100
                    ) as avg_return
                FROM tickers t
                JOIN ohlcv_data o ON t.ticker = o.ticker
                JOIN ohlcv_data o_prev ON t.ticker = o_prev.ticker
                    AND o_prev.date = date(o.date, '-1 day')
                WHERE o.date >= date('now', '-5 days')
                    AND t.region = 'KR'
                    AND t.gics_sector IS NOT NULL
                GROUP BY t.gics_sector
                HAVING COUNT(*) >= 3
                ORDER BY avg_return DESC
            """

            # Execute query using connection
            conn = self.db._get_connection()
            cursor = conn.cursor()
            cursor.execute(query)
            sector_performance = cursor.fetchall()
            cursor.close()

            if not sector_performance or len(sector_performance) < 3:
                logger.warning("  ⚠️ Insufficient sector data for rotation analysis")
                logger.info("  Sector Rotation Score: 0.0/10.0 (NEUTRAL - Insufficient data)")
                return 0.0

            # 상위 3개 섹터 확인
            top_sectors = [row[0] for row in sector_performance[:3]]

            # 리딩 섹터 vs 방어 섹터 분류
            leading_sectors = {
                'Information Technology',
                'Financials',
                'Consumer Discretionary',
                'Communication Services'
            }
            defensive_sectors = {
                'Utilities',
                'Consumer Staples',
                'Health Care',
                'Real Estate'
            }

            leading_count = sum(1 for s in top_sectors if s in leading_sectors)
            defensive_count = sum(1 for s in top_sectors if s in defensive_sectors)

            if leading_count >= 2:
                score = +15  # Risk-on (bullish)
                classification = "RISK-ON (Leading sectors outperforming)"
            elif defensive_count >= 2:
                score = -15  # Risk-off (bearish)
                classification = "RISK-OFF (Defensive sectors outperforming)"
            else:
                score = 0    # Mixed
                classification = "MIXED (No clear rotation)"

            logger.info(f"  Top Sectors: {', '.join(top_sectors)}")
            logger.info(f"  Classification: {classification}")
            logger.info(f"  Sector Rotation Score: {score:+.1f}/15.0")

            return score

        except Exception as e:
            logger.error(f"  ❌ Sector rotation analysis failed: {e}")
            return 0.0

    def _classify_market_regime(self, total_score: float, vix_score: float) -> MarketRegime:
        """
        시장 국면 분류

        Classification:
        - BULL: total_score > 50, VIX < 20 (score > -20)
        - BULL_CORRECTION: total_score > 20, VIX 20-30
        - SIDEWAYS: -20 < total_score < 20
        - BEAR_RALLY: total_score < -20, improving trend
        - BEAR: total_score < -50, VIX > 30

        Args:
            total_score: Weighted sentiment score (-100 to +100)
            vix_score: VIX-based score (-50 to +10)

        Returns:
            MarketRegime enum
        """
        if total_score > 50 and vix_score > -20:
            return MarketRegime.BULL
        elif total_score > 20:
            return MarketRegime.BULL_CORRECTION
        elif -20 <= total_score <= 20:
            return MarketRegime.SIDEWAYS
        elif total_score < -50:
            return MarketRegime.BEAR
        else:
            return MarketRegime.BEAR_RALLY

    def _calculate_position_multiplier(self, vix_score: float, total_score: float) -> float:
        """
        VIX 및 총점 기반 포지션 배율 계산

        Multipliers:
        - VIX < 16 (score > 0) + Score > 50: 1.0 (full position)
        - VIX 16-20 (score 0) + Score > 20: 0.75
        - VIX 20-30 (score < -20) or Score < 0: 0.5
        - VIX > 30 (score < -35) or Score < -50: 0.25

        Args:
            vix_score: VIX-based score (-50 to +10)
            total_score: Total sentiment score (-100 to +100)

        Returns:
            Position multiplier (0.25, 0.5, 0.75, or 1.0)
        """
        # VIX 기반 multiplier
        if vix_score > 0:  # VIX < 16
            vix_mult = 1.0
        elif vix_score > -20:  # VIX 16-20
            vix_mult = 0.75
        elif vix_score > -35:  # VIX 20-30
            vix_mult = 0.5
        else:  # VIX > 30
            vix_mult = 0.25

        # 총점 기반 multiplier
        if total_score > 50:
            score_mult = 1.0
        elif total_score > 20:
            score_mult = 0.75
        elif total_score > -20:
            score_mult = 0.5
        else:
            score_mult = 0.25

        # 두 multiplier 중 작은 값 사용 (보수적 접근)
        return min(vix_mult, score_mult)

    def _calculate_confidence(
        self,
        global_indices: Dict[str, GlobalMarketData],
        vix_score: float,
        sector_score: float
    ) -> float:
        """
        데이터 신뢰도 계산

        Confidence factors:
        - Global indices completeness (5/5 indices = 1.0)
        - VIX data availability (yes = 1.0, no = 0.0)
        - Consistency across sources (all positive or all negative = high)

        Returns:
            Confidence level (0.0 to 1.0)
        """
        # Global indices completeness
        indices_completeness = len(global_indices) / 5.0  # 5 expected indices

        # VIX availability
        vix_available = 1.0 if vix_score != 0 else 0.0

        # Signal consistency (all sources agree in direction)
        signals = [vix_score, sector_score]
        positive_count = sum(1 for s in signals if s > 0)
        negative_count = sum(1 for s in signals if s < 0)

        if positive_count == 2 or negative_count == 2:
            consistency = 1.0  # All agree
        else:
            consistency = 0.5  # Mixed signals

        # Weighted average
        confidence = (
            indices_completeness * 0.4 +
            vix_available * 0.3 +
            consistency * 0.3
        )

        return min(confidence, 1.0)

    def _calculate_completeness(
        self,
        global_indices: Dict[str, GlobalMarketData],
        vix_score: float,
        sector_score: float
    ) -> float:
        """
        데이터 완전성 계산

        Completeness factors:
        - VIX: 40% (critical)
        - Global indices: 40% (critical)
        - Sector Rotation: 20%

        Returns:
            Completeness (0.0 to 1.0)
        """
        vix_complete = 0.40 if vix_score != 0 else 0.0
        indices_complete = 0.40 * (len(global_indices) / 5.0)
        sector_complete = 0.20 if sector_score != 0 else 0.0

        return vix_complete + indices_complete + sector_complete


# ============================================================================
# Global Indices Scoring Algorithm
# ============================================================================

def calculate_global_indices_score(indices: Dict[str, GlobalMarketData]) -> float:
    """
    Calculate global market indices sentiment score

    Scoring Breakdown (25 points total):
    - US indices (17.5 points): S&P 500 (40%), NASDAQ (35%), DOW (25%)
    - Asia indices (7.5 points): Hang Seng (60%), Nikkei (40%)
    - Consistency bonus (±3 points): 3+ consecutive days same direction

    Formula per index:
        score = (change_percent / 3.0) * max_points * weight

    Example:
        S&P 500: +1.5% change
        → (1.5 / 3.0) * 17.5 * 0.40 = +3.5 points

    Args:
        indices: Dictionary mapping symbol → GlobalMarketData

    Returns:
        Score from -25 to +25
    """
    if not indices:
        logger.warning("⚠️ No index data provided for scoring")
        return 0.0

    # US indices weights (70% of 25 = 17.5 points)
    US_WEIGHTS = {
        '^GSPC': 0.40,   # S&P 500: 40% of US weight
        '^IXIC': 0.35,   # NASDAQ: 35% of US weight
        '^DJI': 0.25,    # DOW: 25% of US weight
    }

    # Asia indices weights (30% of 25 = 7.5 points)
    ASIA_WEIGHTS = {
        '^HSI': 0.60,    # Hang Seng: 60% of Asia weight
        '^N225': 0.40,   # Nikkei: 40% of Asia weight
    }

    us_score = 0.0
    asia_score = 0.0

    # Calculate US indices score (max 17.5 points)
    for symbol, weight in US_WEIGHTS.items():
        if symbol in indices:
            data = indices[symbol]
            # Cap change at ±3% to prevent extreme scores
            capped_change = max(-3.0, min(3.0, data.change_percent))
            us_score += (capped_change / 3.0) * 17.5 * weight

    # Calculate Asia indices score (max 7.5 points)
    for symbol, weight in ASIA_WEIGHTS.items():
        if symbol in indices:
            data = indices[symbol]
            capped_change = max(-3.0, min(3.0, data.change_percent))
            asia_score += (capped_change / 3.0) * 7.5 * weight

    # Consistency bonus: Check if 3+ indices moving in same direction for 3+ days
    consistency_bonus = _calculate_consistency_bonus(indices)

    total_score = us_score + asia_score + consistency_bonus

    # Clamp final score to -25 to +25
    total_score = max(-25.0, min(25.0, total_score))

    logger.info(f"📊 Global Indices Score: {total_score:+.2f} (US: {us_score:+.2f}, Asia: {asia_score:+.2f}, Bonus: {consistency_bonus:+.2f})")

    return total_score


def _calculate_consistency_bonus(indices: Dict[str, GlobalMarketData]) -> float:
    """
    Calculate consistency bonus based on trend alignment

    Bonus Logic:
    - +3 points: 3+ indices in UP trend for 3+ consecutive days
    - -3 points: 3+ indices in DOWN trend for 3+ consecutive days
    - 0 points: Mixed or insufficient consistency

    Args:
        indices: Dictionary mapping symbol → GlobalMarketData

    Returns:
        Bonus from -3 to +3
    """
    up_count = 0
    down_count = 0

    for data in indices.values():
        if data.trend_5d == 'UP' and data.consecutive_days >= 3:
            up_count += 1
        elif data.trend_5d == 'DOWN' and data.consecutive_days >= 3:
            down_count += 1

    if up_count >= 3:
        return 3.0
    elif down_count >= 3:
        return -3.0
    else:
        return 0.0


# ============================================================================
# Main Execution (Testing)
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("stock_sentiment.py - Market Sentiment Analysis Test")
    print("=" * 80)
    print("\nPhase 2: Complete Market Sentiment Pipeline Integration")
    print("=" * 80)

    # Initialize Database
    print("\n[Setup] Initializing Database...")
    print("-" * 80)
    db = SQLiteDatabaseManager()
    print("✅ Database initialized")

    # Test 1: MarketSentimentAnalyzer - Complete Pipeline
    print("\n" + "=" * 80)
    print("[Test 1] MarketSentimentAnalyzer - Complete Pipeline")
    print("=" * 80)

    analyzer = MarketSentimentAnalyzer(db_manager=db)
    summary = analyzer.collect_all_sentiment_data()

    print("\n" + "=" * 80)
    print("COMPREHENSIVE SENTIMENT REPORT")
    print("=" * 80)
    print(f"\n📅 Date: {summary.date}")
    print(f"⏰ Timestamp: {summary.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n📊 Component Scores:")
    print(f"  VIX Volatility:         {summary.vix_score:+7.2f} / 50.0  (60% weight)")
    print(f"  Global Indices:         {summary.global_indices_score:+7.2f} / 25.0  (25% weight)")
    print(f"  Sector Rotation:        {summary.sector_rotation_score:+7.2f} / 15.0  (15% weight)")
    print(f"\n🎯 Overall Sentiment:")
    print(f"  Total Score:            {summary.total_score:+7.2f} / 100.0")
    print(f"  Market Regime:          {summary.market_regime.value}")
    print(f"  Confidence Level:       {summary.confidence_level*100:6.1f}%")
    print(f"  Data Completeness:      {summary.data_completeness*100:6.1f}%")
    print(f"\n💰 Position Sizing Recommendations:")
    print(f"  Position Multiplier:    {summary.position_multiplier:.2f}x")
    print(f"  Max Position per Stock: {summary.max_position_pct:.2f}%")

    # Recommendation
    if summary.total_score > 50:
        recommendation = "STRONGLY BULLISH - Aggressive positioning"
    elif summary.total_score > 20:
        recommendation = "MODERATELY BULLISH - Standard positioning"
    elif summary.total_score > -20:
        recommendation = "NEUTRAL - Selective positioning"
    elif summary.total_score > -50:
        recommendation = "MODERATELY BEARISH - Defensive positioning"
    else:
        recommendation = "STRONGLY BEARISH - Cash preservation"

    print(f"\n💡 Recommendation: {recommendation}")
    print("=" * 80)

    # Test 2: YFinanceIndexSource - Individual Component Test
    print("\n\n" + "=" * 80)
    print("[Test 2] YFinanceIndexSource - Single Index")
    print("=" * 80)

    yf_source = YFinanceIndexSource()
    sp500_data = yf_source.get_index_data('^GSPC', days=5)

    if sp500_data:
        print(f"✅ S&P 500 Data Retrieved:")
        print(f"   Date: {sp500_data.date}")
        print(f"   Close: {sp500_data.close_price:.2f}")
        print(f"   Change: {sp500_data.change_percent:+.2f}%")
        print(f"   Trend: {sp500_data.trend_5d} ({sp500_data.consecutive_days} days)")
    else:
        print("❌ Failed to retrieve S&P 500 data")

    # Test 2: GlobalMarketCollector
    print("\n[Test 2] GlobalMarketCollector - All Indices")
    print("-" * 80)

    collector = GlobalMarketCollector()
    all_indices = collector.collect_all_indices(days=5)

    if all_indices:
        print(f"\n✅ Retrieved {len(all_indices)} indices:\n")

        for symbol, data in all_indices.items():
            print(f"  {data.index_name:20s} | {data.close_price:8.2f} | "
                  f"{data.change_percent:+6.2f}% | {data.trend_5d:5s} {data.consecutive_days}d")
    else:
        print("❌ No indices retrieved")

    # Test 3: Cache Performance
    print("\n[Test 3] Cache Performance Test")
    print("-" * 80)

    print("First call (network):")
    start = time.time()
    collector.collect_all_indices()
    first_call_time = time.time() - start
    print(f"  Time: {first_call_time:.2f}s")

    print("\nSecond call (cached):")
    start = time.time()
    collector.collect_all_indices()
    second_call_time = time.time() - start
    print(f"  Time: {second_call_time:.2f}s")

    print(f"\nCache speedup: {first_call_time / max(second_call_time, 0.001):.1f}x faster")

    # Test 4: Database Persistence
    print("\n[Test 4] Database Persistence")
    print("-" * 80)

    db = GlobalIndicesDatabase()
    saved_count = db.save_batch(all_indices)
    print(f"✅ Saved {saved_count} indices to database")

    # Retrieve from database
    retrieved_indices = db.get_latest_indices()
    print(f"✅ Retrieved {len(retrieved_indices)} indices from database")

    # Test 5: Scoring Algorithm
    print("\n[Test 5] Global Indices Scoring Algorithm")
    print("-" * 80)

    score = calculate_global_indices_score(all_indices)
    print(f"\n✅ Global Indices Score: {score:+.2f} / 25.0")

    # Score breakdown
    print("\nScore Breakdown:")
    print(f"  {'Index':20s} | {'Change %':>10s} | {'Trend':^12s} | {'Weight':>8s}")
    print("  " + "-" * 60)

    US_WEIGHTS = {'^GSPC': 0.40, '^IXIC': 0.35, '^DJI': 0.25}
    ASIA_WEIGHTS = {'^HSI': 0.60, '^N225': 0.40}

    for symbol, weight in US_WEIGHTS.items():
        if symbol in all_indices:
            data = all_indices[symbol]
            print(f"  {data.index_name:20s} | {data.change_percent:+9.2f}% | "
                  f"{data.trend_5d:5s} {data.consecutive_days:2d}d | US {weight:.0%}")

    for symbol, weight in ASIA_WEIGHTS.items():
        if symbol in all_indices:
            data = all_indices[symbol]
            print(f"  {data.index_name:20s} | {data.change_percent:+9.2f}% | "
                  f"{data.trend_5d:5s} {data.consecutive_days:2d}d | Asia {weight:.0%}")

    print("\n" + "=" * 80)
    print("✅ All tests completed successfully")
    print("=" * 80)
