"""
Refresh Configuration Management

Configuration for the database refresh system, managing multi-region
data updates, backfills, and maintenance operations.

Maps to: config/refresh_config.yaml

Classes:
    RefreshConfig: Main configuration class for refresh operations

Usage:
    from infrastructure.config import RefreshConfig

    # Load with defaults
    config = RefreshConfig.load()

    # Access settings
    print(f"Enabled regions: {config.enabled_regions}")
    print(f"Batch size: {config.batch_size}")
    print(f"Equity time per ticker: {config.equity_backfill_time_per_ticker}")
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict
import os
import logging

from .base_config import BaseConfig

logger = logging.getLogger(__name__)


@dataclass
class RefreshConfig(BaseConfig):
    """
    Database refresh system configuration

    This class manages all configuration for:
    - Global system settings (logging, workers, checkpoints)
    - Region settings (enabled regions, rate limits)
    - OHLCV update settings (batch sizes, lookback periods)
    - Equity backfill settings (time estimates, batch sizes)

    All values can be overridden via:
    1. Environment variables (SPOCK_*)
    2. User config (~/.spock/config/refresh_config.yaml)
    3. Project config (config/refresh_config.yaml)

    Attributes:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_workers: Maximum concurrent workers for parallel operations
        checkpoint_enabled: Enable checkpoint-based resume functionality
        checkpoint_dir: Directory for storing checkpoint files

        enabled_regions: List of enabled market regions
        rate_limits: API rate limits per region (requests/second)

        batch_size: OHLCV batch processing size
        lookback_days: Days to look back for incremental updates
        max_history_days: Maximum history to fetch for new tickers

        equity_backfill_time_per_ticker: Estimated time per ticker (hours)
        equity_batch_sizes: Predefined batch size options
    """

    # ========================================================================
    # Global Settings
    # ========================================================================
    log_level: str = "INFO"
    max_workers: int = 4
    checkpoint_enabled: bool = True
    checkpoint_dir: str = "data/checkpoints"

    # ========================================================================
    # Region Settings
    # ========================================================================
    enabled_regions: List[str] = field(default_factory=lambda: [
        "KR", "US", "HK", "JP", "CN", "VN"
    ])

    rate_limits: Dict[str, int] = field(default_factory=lambda: {
        "KR": 100,  # pykrx (fast, local)
        "US": 5,    # yfinance (slow, API limited)
        "HK": 10,   # yfinance
        "JP": 10,   # yfinance
        "CN": 10,   # yfinance
        "VN": 10    # custom adapter
    })

    # ========================================================================
    # OHLCV Update Settings
    # ========================================================================
    batch_size: int = 100
    lookback_days: int = 1
    max_history_days: int = 1825  # 5 years

    # ========================================================================
    # Equity Backfill Settings (Phase 0.2)
    # ========================================================================
    # Time estimates based on empirical data:
    # - DART API: ~108 sec/ticker * 3 years = 0.09 hours/ticker
    equity_backfill_time_per_ticker: float = 0.09

    equity_batch_sizes: Dict[str, int] = field(default_factory=lambda: {
        "test": 2,       # Dry run test
        "small": 10,     # Quick test batch
        "medium": 50,    # Medium batch
        "large": 100,    # Quick batch (9 hours)
        "xlarge": 500    # Medium batch (45 hours)
    })

    # ========================================================================
    # Listing Date Backfill Settings (Phase 0.2)
    # ========================================================================
    # Time estimates per ticker by region (seconds)
    listing_date_time_per_ticker: Dict[str, float] = field(default_factory=lambda: {
        "KR": 0.02,  # KRX API (very fast)
        "US": 2.5,   # yfinance (slow due to rate limits)
        "JP": 2.0,   # yfinance
        "HK": 2.0,   # yfinance
        "CN": 2.0,   # yfinance
        "VN": 2.0    # yfinance
    })

    # Coverage thresholds for status classification
    coverage_thresholds: Dict[str, float] = field(default_factory=lambda: {
        "excellent": 95.0,  # >= 95%
        "good": 80.0,       # >= 80%
        "fair": 50.0        # >= 50%
        # Below 50% = poor
    })

    @classmethod
    def get_default_config_path(cls) -> Path:
        """Get the default configuration file path"""
        # Navigate from infrastructure/config/ to project root config/
        return Path(__file__).parent.parent.parent / 'config' / 'refresh_config.yaml'

    @classmethod
    def _apply_env_overrides(cls, config_data: Dict) -> Dict:
        """
        Apply environment variable overrides

        Supported environment variables:
            SPOCK_LOG_LEVEL: Override log level
            SPOCK_MAX_WORKERS: Override max workers
            SPOCK_CHECKPOINT_ENABLED: Enable/disable checkpoints
            SPOCK_CHECKPOINT_DIR: Override checkpoint directory
            SPOCK_ENABLED_REGIONS: Comma-separated list of regions

        Example:
            export SPOCK_LOG_LEVEL=DEBUG
            export SPOCK_MAX_WORKERS=8
            export SPOCK_ENABLED_REGIONS=KR,US,JP
        """
        # Extract nested 'global' section if present (from YAML structure)
        if 'global' in config_data:
            global_section = config_data['global']
        else:
            global_section = config_data

        # Log level
        if log_level := os.getenv('SPOCK_LOG_LEVEL'):
            global_section['log_level'] = log_level.upper()
            logger.debug(f"Environment override: log_level={log_level}")

        # Max workers
        if max_workers := os.getenv('SPOCK_MAX_WORKERS'):
            try:
                global_section['max_workers'] = int(max_workers)
                logger.debug(f"Environment override: max_workers={max_workers}")
            except ValueError:
                logger.warning(f"Invalid SPOCK_MAX_WORKERS value: {max_workers}")

        # Checkpoint enabled
        if checkpoint := os.getenv('SPOCK_CHECKPOINT_ENABLED'):
            global_section['checkpoint_enabled'] = checkpoint.lower() in ('true', '1', 'yes')
            logger.debug(f"Environment override: checkpoint_enabled={checkpoint}")

        # Checkpoint directory
        if checkpoint_dir := os.getenv('SPOCK_CHECKPOINT_DIR'):
            global_section['checkpoint_dir'] = checkpoint_dir
            logger.debug(f"Environment override: checkpoint_dir={checkpoint_dir}")

        # Enabled regions
        if regions := os.getenv('SPOCK_ENABLED_REGIONS'):
            region_list = [r.strip().upper() for r in regions.split(',')]
            if 'regions' not in config_data:
                config_data['regions'] = {}
            config_data['regions']['enabled'] = region_list
            logger.debug(f"Environment override: enabled_regions={region_list}")

        # Flatten nested structure for dataclass initialization
        # YAML: global.log_level → dataclass: log_level
        flattened = {}

        # Global settings
        if 'global' in config_data:
            flattened.update(config_data['global'])

        # Regions settings
        if 'regions' in config_data:
            regions_section = config_data['regions']
            if 'enabled' in regions_section:
                flattened['enabled_regions'] = regions_section['enabled']
            if 'rate_limits' in regions_section:
                flattened['rate_limits'] = regions_section['rate_limits']

        # OHLCV settings
        if 'ohlcv_update' in config_data:
            ohlcv_section = config_data['ohlcv_update']
            if 'batch_size' in ohlcv_section:
                flattened['batch_size'] = ohlcv_section['batch_size']
            if 'incremental' in ohlcv_section:
                incr = ohlcv_section['incremental']
                if 'lookback_days' in incr:
                    flattened['lookback_days'] = incr['lookback_days']
                if 'max_history_days' in incr:
                    flattened['max_history_days'] = incr['max_history_days']

        # Return only flattened data (removes nested structure)
        # This ensures dataclass only receives valid field names
        return flattened

    def validate(self) -> bool:
        """
        Validate configuration values

        Raises:
            ValueError: If any configuration value is invalid

        Returns:
            True if all validations pass
        """
        # Log level validation
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_log_levels:
            raise ValueError(
                f"Invalid log_level: {self.log_level}. "
                f"Must be one of {valid_log_levels}"
            )

        # Max workers validation
        if not 1 <= self.max_workers <= 16:
            raise ValueError(
                f"Invalid max_workers: {self.max_workers}. "
                f"Must be between 1 and 16"
            )

        # Regions validation
        valid_regions = ["KR", "US", "CN", "HK", "JP", "VN"]
        for region in self.enabled_regions:
            if region not in valid_regions:
                raise ValueError(
                    f"Invalid region: {region}. "
                    f"Must be one of {valid_regions}"
                )

        # Rate limits validation
        for region, limit in self.rate_limits.items():
            if limit <= 0:
                raise ValueError(
                    f"Invalid rate_limit for {region}: {limit}. "
                    f"Must be > 0"
                )

        # Batch size validation
        if self.batch_size <= 0:
            raise ValueError(
                f"Invalid batch_size: {self.batch_size}. "
                f"Must be > 0"
            )

        # Lookback days validation
        if self.lookback_days < 0:
            raise ValueError(
                f"Invalid lookback_days: {self.lookback_days}. "
                f"Must be >= 0"
            )

        # Max history days validation
        if self.max_history_days <= 0:
            raise ValueError(
                f"Invalid max_history_days: {self.max_history_days}. "
                f"Must be > 0"
            )

        # Equity backfill time validation
        if self.equity_backfill_time_per_ticker <= 0:
            raise ValueError(
                f"Invalid equity_backfill_time_per_ticker: {self.equity_backfill_time_per_ticker}. "
                f"Must be > 0"
            )

        logger.debug("Configuration validation passed")
        return True

    def get_equity_batch_size(self, batch_type: str = "medium") -> int:
        """
        Get equity backfill batch size by type

        Args:
            batch_type: Batch type (test, small, medium, large, xlarge)

        Returns:
            Batch size for the specified type

        Raises:
            KeyError: If batch_type is invalid
        """
        if batch_type not in self.equity_batch_sizes:
            raise KeyError(
                f"Invalid batch_type: {batch_type}. "
                f"Must be one of {list(self.equity_batch_sizes.keys())}"
            )
        return self.equity_batch_sizes[batch_type]

    def get_rate_limit(self, region: str) -> int:
        """
        Get API rate limit for a region

        Args:
            region: Region code (KR, US, etc.)

        Returns:
            Rate limit (requests/second)

        Raises:
            KeyError: If region is not configured
        """
        if region not in self.rate_limits:
            raise KeyError(
                f"No rate_limit configured for region: {region}"
            )
        return self.rate_limits[region]

    def estimate_equity_backfill_time(self, ticker_count: int) -> float:
        """
        Estimate equity backfill time in hours

        Args:
            ticker_count: Number of tickers to backfill

        Returns:
            Estimated time in hours
        """
        return ticker_count * self.equity_backfill_time_per_ticker

    def estimate_listing_date_backfill_time(
        self,
        region: str,
        ticker_count: int
    ) -> float:
        """
        Estimate listing date backfill time in seconds

        Args:
            region: Region code (KR, US, etc.)
            ticker_count: Number of tickers to backfill

        Returns:
            Estimated time in seconds
        """
        time_per_ticker = self.listing_date_time_per_ticker.get(region, 2.0)
        return ticker_count * time_per_ticker
