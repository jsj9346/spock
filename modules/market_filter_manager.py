"""
Market Filter Manager - Multi-Market Configuration System

Handles market-specific filter configurations for global stock markets.

Features:
1. Load market-specific YAML configurations
2. Currency normalization (all to KRW)
3. Threshold validation and application
4. Market-specific rule handling

Supported Markets:
- KR: Korea (KOSPI/KOSDAQ)
- US: United States (NYSE/NASDAQ/AMEX)
- HK: Hong Kong (HKEX)
- CN: China (SSE/SZSE via Stock Connect)
- JP: Japan (TSE)
- VN: Vietnam (HOSE/HNX)

Author: Spock Trading System
Date: 2025-10-04
"""

import os
import yaml
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FilterResult:
    """Filter application result with details"""
    passed: bool
    reason: str
    normalized_data: Dict


class MarketFilterConfig:
    """
    Market-specific filter configuration loader

    Loads and manages filter settings from YAML configuration files.
    Provides methods for threshold checks and currency conversion.
    """

    def __init__(self, config_path: str):
        """
        Load market configuration from YAML file

        Args:
            config_path: Path to market config YAML
                        (e.g., 'config/market_filters/kr_filter_config.yaml')

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If config file is invalid YAML
            KeyError: If required config keys are missing
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)

        # Validate required keys
        self._validate_config()

        # Extract core settings
        self.region = self.config['region']
        self.market_name = self.config['market_name']
        self.currency = self.config['currency']

        # Exchange rate settings
        exchange_rate_config = self.config['exchange_rate']
        self.exchange_rate_source = exchange_rate_config['source']
        self.default_exchange_rate = float(exchange_rate_config['default_rate'])
        self._current_exchange_rate = self.default_exchange_rate

        # Stage 0 filter settings
        self.stage0_filters = self.config['stage0_filters']

        logger.info(
            f"✅ Loaded {self.region} market config: {self.market_name} "
            f"(Currency: {self.currency}, Rate: {self.default_exchange_rate})"
        )

    def _validate_config(self):
        """Validate required configuration keys"""
        required_keys = ['region', 'market_name', 'currency', 'exchange_rate', 'stage0_filters']
        for key in required_keys:
            if key not in self.config:
                raise KeyError(f"Missing required config key: {key}")

        # Validate stage0_filters subkeys
        required_stage0_keys = [
            'min_market_cap_krw',
            'min_trading_value_krw',
            'price_range_min_krw',
            'price_range_max_krw'
        ]
        for key in required_stage0_keys:
            if key not in self.config['stage0_filters']:
                raise KeyError(f"Missing required stage0_filters key: {key}")

    def update_exchange_rate(self, rate: float, source: str = 'manual'):
        """
        Update current exchange rate

        Args:
            rate: New exchange rate (local currency to KRW)
            source: Rate source ('kis_api', 'bok', 'manual', etc.)
        """
        self._current_exchange_rate = rate
        logger.info(
            f"🔄 [{self.region}] Exchange rate updated: {rate} "
            f"(source: {source})"
        )

    def get_exchange_rate(self) -> float:
        """Get current exchange rate"""
        return self._current_exchange_rate

    def convert_to_krw(self, value_local: float) -> int:
        """
        Convert local currency value to KRW

        Args:
            value_local: Value in local currency

        Returns:
            Value in KRW (integer)
        """
        return int(value_local * self._current_exchange_rate)

    def get_min_market_cap_krw(self) -> int:
        """Get minimum market cap threshold in KRW"""
        return int(self.stage0_filters['min_market_cap_krw'])

    def get_min_trading_value_krw(self) -> int:
        """Get minimum trading value threshold in KRW"""
        return int(self.stage0_filters['min_trading_value_krw'])

    def get_price_range_krw(self) -> Tuple[int, int]:
        """
        Get price range (min, max) in KRW

        Returns:
            (min_price_krw, max_price_krw) tuple
        """
        return (
            int(self.stage0_filters['price_range_min_krw']),
            int(self.stage0_filters['price_range_max_krw'])
        )

    def should_exclude_ticker(self, ticker_data: Dict) -> Tuple[bool, str]:
        """
        Check if ticker should be excluded based on market-specific rules

        Args:
            ticker_data: Ticker metadata dictionary with keys:
                - ticker: Stock ticker code
                - name: Stock name
                - asset_type: 'STOCK', 'ETF', 'ETN', etc.
                - market_warn_code: (Korea) 관리종목 코드
                - is_stock_connect: (China) Stock Connect 여부
                - is_delisting: Delisting flag
                - price_local: Current price in local currency
                - (other market-specific fields)

        Returns:
            (should_exclude: bool, reason: str)
        """
        filters = self.stage0_filters

        # Korea-specific: Admin stocks (관리종목)
        if self.region == 'KR' and filters.get('exclude_admin_stocks', False):
            market_warn_code = ticker_data.get('market_warn_code', '00')
            if market_warn_code != '00':
                return True, f'admin_stock_{market_warn_code}'

        # US-specific: Penny stocks
        if self.region == 'US' and filters.get('exclude_penny_stocks', False):
            price_local = ticker_data.get('price_local', 0)
            if price_local < 1.0:
                return True, 'penny_stock'

        # US-specific: OTC markets
        if self.region == 'US' and filters.get('exclude_otc', False):
            if ticker_data.get('is_otc', False):
                return True, 'otc_market'

        # China-specific: Non-Stock Connect
        if self.region == 'CN' and filters.get('stock_connect_only', False):
            if not ticker_data.get('is_stock_connect', False):
                return True, 'not_stock_connect'

        # Common: Delisting
        if filters.get('exclude_delisting', False):
            if ticker_data.get('is_delisting', False):
                return True, 'delisting'

        # Common: Asset type exclusions
        asset_type = ticker_data.get('asset_type', 'STOCK')

        if filters.get('exclude_etf', False) and asset_type == 'ETF':
            return True, 'etf'

        if filters.get('exclude_etn', False) and asset_type == 'ETN':
            return True, 'etn'

        if filters.get('exclude_spac', False) and asset_type == 'SPAC':
            return True, 'spac'

        if filters.get('exclude_preferred_stock', False) and asset_type == 'PREFERRED':
            return True, 'preferred_stock'

        # Korea-specific: KONEX
        if self.region == 'KR' and filters.get('exclude_konex', False):
            if ticker_data.get('market', '').upper() == 'KONEX':
                return True, 'konex'

        return False, ''

    def apply_stage0_filter(self, ticker_data: Dict) -> FilterResult:
        """
        Apply Stage 0 filter (Basic Market Filter)

        Args:
            ticker_data: Ticker data dictionary with local currency values
                Required keys:
                - ticker: Stock code
                - market_cap_local: Market cap in local currency
                - trading_value_local: Daily trading value in local currency
                - price_local: Current price in local currency
                - (other optional fields for market-specific rules)

        Returns:
            FilterResult with:
            - passed: True if ticker passes all filters
            - reason: Empty if passed, failure reason if not
            - normalized_data: Dict with KRW-normalized values
        """
        ticker = ticker_data.get('ticker', 'UNKNOWN')

        # Convert to KRW for threshold comparison
        market_cap_local = ticker_data.get('market_cap_local', 0)
        trading_value_local = ticker_data.get('trading_value_local', 0)
        price_local = ticker_data.get('price_local', 0)

        market_cap_krw = self.convert_to_krw(market_cap_local)
        trading_value_krw = self.convert_to_krw(trading_value_local)
        price_krw = self.convert_to_krw(price_local)

        # Filter 0: Data Completeness (시가총액/거래대금 = 0 필터링)
        # 상장폐지/거래정지 종목은 시가총액 = 0으로 표시됨
        if market_cap_krw == 0 and market_cap_local == 0:
            return FilterResult(
                passed=False,
                reason='market_cap_zero (상장폐지/거래정지 가능성)',
                normalized_data={}
            )

        if trading_value_krw == 0 and trading_value_local == 0:
            return FilterResult(
                passed=False,
                reason='trading_value_zero (거래없음/거래정지 가능성)',
                normalized_data={}
            )

        # Filter 1: Market Cap
        min_market_cap = self.get_min_market_cap_krw()
        if market_cap_krw < min_market_cap:
            return FilterResult(
                passed=False,
                reason=f'market_cap_too_low ({market_cap_krw:,} < {min_market_cap:,} KRW)',
                normalized_data={}
            )

        # Filter 2: Trading Value
        min_trading_value = self.get_min_trading_value_krw()
        if trading_value_krw < min_trading_value:
            return FilterResult(
                passed=False,
                reason=f'trading_value_too_low ({trading_value_krw:,} < {min_trading_value:,} KRW)',
                normalized_data={}
            )

        # Filter 3: Price Range
        price_min_krw, price_max_krw = self.get_price_range_krw()
        if price_krw < price_min_krw:
            return FilterResult(
                passed=False,
                reason=f'price_too_low ({price_krw:,} < {price_min_krw:,} KRW)',
                normalized_data={}
            )

        # price_max_krw = 0 means no maximum
        if price_max_krw > 0 and price_krw > price_max_krw:
            return FilterResult(
                passed=False,
                reason=f'price_too_high ({price_krw:,} > {price_max_krw:,} KRW)',
                normalized_data={}
            )

        # Filter 4: Market-specific exclusions
        should_exclude, exclude_reason = self.should_exclude_ticker(ticker_data)
        if should_exclude:
            return FilterResult(
                passed=False,
                reason=exclude_reason,
                normalized_data={}
            )

        # Passed all filters
        normalized_data = {
            'market_cap_krw': market_cap_krw,
            'trading_value_krw': trading_value_krw,
            'current_price_krw': price_krw,
            'market_cap_local': market_cap_local,
            'trading_value_local': trading_value_local,
            'current_price_local': price_local,
            'currency': self.currency,
            'exchange_rate_to_krw': self._current_exchange_rate,
            'exchange_rate_date': datetime.now().strftime('%Y-%m-%d'),
            'exchange_rate_source': self.exchange_rate_source
        }

        logger.debug(
            f"✅ [{self.region}] {ticker} passed Stage 0 filter "
            f"(Market Cap: {market_cap_krw:,} KRW)"
        )

        return FilterResult(
            passed=True,
            reason='',
            normalized_data=normalized_data
        )


class MarketFilterManager:
    """
    Multi-market filter configuration manager

    Manages filter configurations for all supported markets.
    Provides unified interface for applying filters across markets.
    """

    def __init__(self, config_dir: str = 'config/market_filters'):
        """
        Initialize MarketFilterManager

        Args:
            config_dir: Directory containing market config YAML files
                       Default: 'config/market_filters'
        """
        self.config_dir = Path(config_dir)
        self.configs: Dict[str, MarketFilterConfig] = {}

        # Load all available market configs
        self._load_all_configs()

    def _load_all_configs(self):
        """Load all market configuration files from config directory"""
        if not self.config_dir.exists():
            logger.warning(
                f"⚠️ Config directory not found: {self.config_dir}"
            )
            logger.info(
                f"💡 Create config files in: {self.config_dir.absolute()}"
            )
            return

        loaded_count = 0
        for config_file in self.config_dir.glob('*_filter_config.yaml'):
            try:
                config = MarketFilterConfig(str(config_file))
                self.configs[config.region] = config
                loaded_count += 1

            except Exception as e:
                logger.error(
                    f"❌ Failed to load {config_file.name}: {e}"
                )

        if loaded_count == 0:
            logger.warning(
                "⚠️ No market config files loaded. "
                "Check config/market_filters/ directory."
            )
        else:
            regions = ', '.join(self.configs.keys())
            logger.info(
                f"✅ Loaded {loaded_count} market configs: {regions}"
            )

    def get_config(self, region: str) -> Optional[MarketFilterConfig]:
        """
        Get filter configuration for specific market

        Args:
            region: Market region code ('KR', 'US', 'HK', 'CN', 'JP', 'VN')

        Returns:
            MarketFilterConfig instance or None if not found
        """
        config = self.configs.get(region.upper())

        if config is None:
            logger.warning(
                f"⚠️ No config found for region: {region}. "
                f"Available: {self.get_supported_regions()}"
            )

        return config

    def get_supported_regions(self) -> List[str]:
        """Get list of supported market regions"""
        return sorted(list(self.configs.keys()))

    def has_config(self, region: str) -> bool:
        """Check if configuration exists for market"""
        return region.upper() in self.configs

    def apply_stage0_filter(
        self,
        region: str,
        ticker_data: Dict
    ) -> FilterResult:
        """
        Apply Stage 0 filter for specific market

        Args:
            region: Market region code ('KR', 'US', etc.)
            ticker_data: Ticker data with local currency values

        Returns:
            FilterResult with passed status, reason, and normalized data

        Raises:
            ValueError: If no configuration exists for the region
        """
        config = self.get_config(region)

        if config is None:
            return FilterResult(
                passed=False,
                reason=f'no_config_for_{region}',
                normalized_data={}
            )

        return config.apply_stage0_filter(ticker_data)

    def update_exchange_rate(
        self,
        region: str,
        rate: float,
        source: str = 'manual'
    ):
        """
        Update exchange rate for specific market

        Args:
            region: Market region code
            rate: New exchange rate (local currency to KRW)
            source: Rate source identifier
        """
        config = self.get_config(region)

        if config:
            config.update_exchange_rate(rate, source)
        else:
            logger.warning(
                f"⚠️ Cannot update exchange rate: "
                f"No config for region {region}"
            )

    def get_all_exchange_rates(self) -> Dict[str, float]:
        """
        Get current exchange rates for all markets

        Returns:
            Dict mapping region code to exchange rate
        """
        return {
            region: config.get_exchange_rate()
            for region, config in self.configs.items()
        }

    def reload_configs(self):
        """Reload all configuration files (useful for config updates)"""
        logger.info("🔄 Reloading market filter configurations...")
        self.configs.clear()
        self._load_all_configs()


# Module-level convenience function
def get_filter_manager(config_dir: str = 'config/market_filters') -> MarketFilterManager:
    """
    Get MarketFilterManager instance (singleton pattern recommended)

    Args:
        config_dir: Configuration directory path

    Returns:
        MarketFilterManager instance
    """
    return MarketFilterManager(config_dir)


# CLI Testing
if __name__ == '__main__':
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    parser = argparse.ArgumentParser(
        description='Market Filter Manager - Configuration Loader'
    )
    parser.add_argument(
        '--config-dir',
        default='config/market_filters',
        help='Market filter config directory'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run test with sample data'
    )

    args = parser.parse_args()

    # Initialize manager
    manager = MarketFilterManager(config_dir=args.config_dir)

    # Display loaded configs
    print("\n" + "="*60)
    print("Market Filter Manager - Loaded Configurations")
    print("="*60)

    if not manager.configs:
        print("❌ No configurations loaded")
    else:
        for region in manager.get_supported_regions():
            config = manager.get_config(region)
            print(f"\n📊 {region}: {config.market_name}")
            print(f"   Currency: {config.currency}")
            print(f"   Exchange Rate: {config.get_exchange_rate()}")
            print(f"   Min Market Cap: {config.get_min_market_cap_krw():,} KRW")
            print(f"   Min Trading Value: {config.get_min_trading_value_krw():,} KRW")
            price_min, price_max = config.get_price_range_krw()
            print(f"   Price Range: {price_min:,} ~ {price_max:,} KRW")

    # Test filter application
    if args.test and manager.has_config('KR'):
        print("\n" + "="*60)
        print("Testing Stage 0 Filter (Korea Market)")
        print("="*60)

        # Sample ticker data
        test_ticker = {
            'ticker': '005930',
            'name': '삼성전자',
            'asset_type': 'STOCK',
            'market': 'KOSPI',
            'market_cap_local': 500_000_000_000_000,  # 500조원
            'trading_value_local': 1_000_000_000_000,  # 1조원
            'price_local': 70_000,  # 70,000원
            'market_warn_code': '00'
        }

        result = manager.apply_stage0_filter('KR', test_ticker)

        print(f"\nTicker: {test_ticker['ticker']} ({test_ticker['name']})")
        print(f"Result: {'✅ PASSED' if result.passed else '❌ FAILED'}")

        if not result.passed:
            print(f"Reason: {result.reason}")
        else:
            print(f"Market Cap (KRW): {result.normalized_data['market_cap_krw']:,}")
            print(f"Trading Value (KRW): {result.normalized_data['trading_value_krw']:,}")
            print(f"Current Price (KRW): {result.normalized_data['current_price_krw']:,}")

    print("\n" + "="*60)
