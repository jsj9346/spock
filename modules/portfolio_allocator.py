#!/usr/bin/env python3
"""
Portfolio Allocator Module
===========================
Manages portfolio allocation templates, asset class holdings, and rebalancing logic.

Architecture:
- Template-based allocation (Conservative, Balanced, Aggressive, Custom)
- 5 Asset Classes: bonds_etf, commodities_etf, dividend_stocks, individual_stocks, cash
- 3 Rebalancing Strategies: threshold, periodic, hybrid
- Integration: KIS Trading Engine, Portfolio Manager, LayeredScoringEngine

Author: Spock Development Team
Date: 2025-10-15
Version: 1.0
"""

import yaml
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal


class PortfolioAllocatorError(Exception):
    """Base exception for PortfolioAllocator errors"""
    pass


class TemplateValidationError(PortfolioAllocatorError):
    """Raised when template validation fails"""
    pass


class TemplateNotFoundError(PortfolioAllocatorError):
    """Raised when template cannot be found"""
    pass


class PortfolioAllocator:
    """
    Portfolio Allocation Manager

    Manages portfolio allocation templates, tracks current holdings by asset class,
    and provides rebalancing recommendations based on drift thresholds.

    Attributes:
        template_name (str): Active template name
        template_config (Dict): Loaded template configuration
        db_manager: Database manager instance
        logger: Logging instance
    """

    # Valid asset classes
    ASSET_CLASSES = [
        'bonds_etf',
        'commodities_etf',
        'dividend_stocks',
        'individual_stocks',
        'cash'
    ]

    # Valid risk levels
    RISK_LEVELS = ['conservative', 'moderate', 'aggressive']

    # Valid rebalancing methods
    REBALANCING_METHODS = ['threshold', 'periodic', 'hybrid']

    def __init__(self, template_name: str, db_manager, config_dir: str = 'config'):
        """
        Initialize PortfolioAllocator with a template.

        Args:
            template_name: Name of portfolio template ('conservative', 'balanced', 'aggressive', 'custom')
            db_manager: SQLiteDatabaseManager instance for database operations
            config_dir: Directory containing portfolio_templates.yaml (default: 'config')

        Raises:
            TemplateNotFoundError: If template doesn't exist
            TemplateValidationError: If template fails validation
        """
        self.template_name = template_name
        self.db_manager = db_manager
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / 'portfolio_templates.yaml'

        # Setup logging
        self.logger = logging.getLogger(f'{__name__}.{template_name}')

        # Load and validate template
        self.template_config = self.load_template(template_name)

        # Cache for current allocation (invalidate on updates)
        self._allocation_cache: Optional[Dict[str, float]] = None
        self._cache_timestamp: Optional[datetime] = None

        self.logger.info(f"PortfolioAllocator initialized with template '{template_name}'")

    def load_template(self, template_name: str) -> Dict:
        """
        Load portfolio template configuration from YAML file.

        Priority:
        1. Load from YAML file (config/portfolio_templates.yaml)
        2. Validate configuration structure and values
        3. Sync to database (portfolio_templates table)

        Args:
            template_name: Name of template to load

        Returns:
            Dict: Template configuration with allocation targets and rebalancing settings

        Raises:
            TemplateNotFoundError: If template doesn't exist in YAML
            TemplateValidationError: If template fails validation
            FileNotFoundError: If YAML file doesn't exist
        """
        # Check if YAML file exists
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")

        try:
            # Load YAML configuration
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # Check if templates section exists
            if 'templates' not in config:
                raise TemplateValidationError("YAML file missing 'templates' section")

            # Check if specific template exists
            if template_name not in config['templates']:
                available = ', '.join(config['templates'].keys())
                raise TemplateNotFoundError(
                    f"Template '{template_name}' not found. Available: {available}"
                )

            # Extract template configuration
            template_config = config['templates'][template_name]

            # Add template name to config
            template_config['template_name'] = template_name

            # Validate template
            self.validate_template(template_config)

            self.logger.info(f"Template '{template_name}' loaded successfully from YAML")

            return template_config

        except yaml.YAMLError as e:
            raise TemplateValidationError(f"YAML parsing error: {e}")
        except Exception as e:
            self.logger.error(f"Failed to load template '{template_name}': {e}")
            raise

    def validate_template(self, config: Dict) -> bool:
        """
        Validate portfolio template configuration.

        Validation Rules:
        1. Required fields present (allocation, rebalancing, limits)
        2. Allocation percentages sum to 100.0 (±0.01 tolerance)
        3. Each allocation 0.0-100.0 range
        4. Risk level in valid set
        5. Rebalancing method in valid set

        Args:
            config: Template configuration dict

        Returns:
            bool: True if validation passes

        Raises:
            TemplateValidationError: If any validation rule fails
        """
        # Check required top-level keys
        required_keys = ['name', 'risk_level', 'allocation', 'rebalancing', 'limits']
        for key in required_keys:
            if key not in config:
                raise TemplateValidationError(f"Missing required field: {key}")

        # Validate risk level
        risk_level = config['risk_level']
        if risk_level not in self.RISK_LEVELS:
            raise TemplateValidationError(
                f"Invalid risk_level '{risk_level}'. Must be one of: {self.RISK_LEVELS}"
            )

        # Validate allocation
        allocation = config['allocation']

        # Check all asset classes present
        for asset_class in self.ASSET_CLASSES:
            if asset_class not in allocation:
                raise TemplateValidationError(f"Missing asset class in allocation: {asset_class}")

        # Validate allocation percentages
        total_allocation = 0.0
        for asset_class, percentage in allocation.items():
            if not isinstance(percentage, (int, float)):
                raise TemplateValidationError(
                    f"Allocation for {asset_class} must be numeric, got {type(percentage)}"
                )

            if not 0.0 <= percentage <= 100.0:
                raise TemplateValidationError(
                    f"Allocation for {asset_class} must be 0-100%, got {percentage}%"
                )

            total_allocation += percentage

        # Check allocation sums to 100% (with tolerance for floating point)
        if not 99.99 <= total_allocation <= 100.01:
            raise TemplateValidationError(
                f"Total allocation must sum to 100%, got {total_allocation:.2f}%"
            )

        # Validate rebalancing configuration
        rebalancing = config['rebalancing']

        if 'method' not in rebalancing:
            raise TemplateValidationError("Rebalancing configuration missing 'method'")

        method = rebalancing['method']
        if method not in self.REBALANCING_METHODS:
            raise TemplateValidationError(
                f"Invalid rebalancing method '{method}'. Must be one of: {self.REBALANCING_METHODS}"
            )

        # Validate method-specific parameters
        if method in ['threshold', 'hybrid']:
            if 'drift_threshold_percent' not in rebalancing:
                raise TemplateValidationError(
                    f"Rebalancing method '{method}' requires 'drift_threshold_percent'"
                )

            drift_threshold = rebalancing['drift_threshold_percent']
            if not 0.0 <= drift_threshold <= 100.0:
                raise TemplateValidationError(
                    f"drift_threshold_percent must be 0-100%, got {drift_threshold}%"
                )

        if method in ['periodic', 'hybrid']:
            if 'periodic_interval_days' not in rebalancing:
                raise TemplateValidationError(
                    f"Rebalancing method '{method}' requires 'periodic_interval_days'"
                )

        # Validate position limits
        limits = config['limits']
        required_limits = [
            'max_single_position_percent',
            'max_sector_exposure_percent',
            'min_cash_reserve_percent',
            'max_concurrent_positions'
        ]

        for limit_key in required_limits:
            if limit_key not in limits:
                raise TemplateValidationError(f"Missing required limit: {limit_key}")

            # Validate percentage limits
            if 'percent' in limit_key:
                limit_value = limits[limit_key]
                if not 0.0 <= limit_value <= 100.0:
                    raise TemplateValidationError(
                        f"{limit_key} must be 0-100%, got {limit_value}%"
                    )

        self.logger.debug(f"Template validation passed for '{config.get('template_name', 'unknown')}'")

        return True

    def list_available_templates(self) -> List[str]:
        """
        List all available portfolio templates from YAML configuration.

        Returns:
            List[str]: List of template names
        """
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            if 'templates' not in config:
                return []

            return list(config['templates'].keys())

        except Exception as e:
            self.logger.error(f"Failed to list templates: {e}")
            return []

    def get_allocation_targets(self) -> Dict[str, float]:
        """
        Get target allocation percentages for all asset classes.

        Returns:
            Dict[str, float]: Asset class -> target percentage mapping
        """
        return self.template_config['allocation'].copy()

    def get_rebalancing_config(self) -> Dict:
        """
        Get rebalancing configuration for current template.

        Returns:
            Dict: Rebalancing method, thresholds, and intervals
        """
        return self.template_config['rebalancing'].copy()

    def get_position_limits(self) -> Dict:
        """
        Get position limit configuration for current template.

        Returns:
            Dict: Position limits (max single position, max sector exposure, etc.)
        """
        return self.template_config['limits'].copy()

    def get_asset_class_details(self, asset_class: str) -> Optional[Dict]:
        """
        Get detailed configuration for specific asset class.

        Args:
            asset_class: Asset class name ('bonds_etf', 'commodities_etf', etc.)

        Returns:
            Optional[Dict]: Asset class configuration or None if not found
        """
        if asset_class not in self.ASSET_CLASSES:
            self.logger.warning(f"Invalid asset class: {asset_class}")
            return None

        asset_classes = self.template_config.get('asset_classes', {})
        return asset_classes.get(asset_class, {})

    def get_current_allocation(self, use_cache: bool = True) -> Dict[str, float]:
        """
        Calculate current portfolio allocation percentages from database holdings.

        Queries asset_class_holdings table and calculates percentage of total
        portfolio value for each asset class.

        Args:
            use_cache: Use cached allocation if available (default: True)

        Returns:
            Dict[str, float]: Asset class -> current percentage mapping
                             Returns 0.0 for asset classes with no holdings
        """
        # Check cache validity (5 minute expiry)
        if use_cache and self._allocation_cache is not None:
            if self._cache_timestamp is not None:
                cache_age = (datetime.now() - self._cache_timestamp).total_seconds()
                if cache_age < 300:  # 5 minutes
                    self.logger.debug(f"Using cached allocation (age: {cache_age:.1f}s)")
                    return self._allocation_cache.copy()

        try:
            # Query database for current holdings grouped by asset class
            query = """
                SELECT asset_class, SUM(market_value) as total_value
                FROM asset_class_holdings
                WHERE template_name = ?
                GROUP BY asset_class
            """

            results = self.db_manager.execute_query(query, (self.template_name,))

            # Calculate total portfolio value
            total_portfolio_value = sum(row[1] for row in results)

            # Initialize allocation dict with zeros
            allocation = {asset_class: 0.0 for asset_class in self.ASSET_CLASSES}

            # Calculate percentages
            if total_portfolio_value > 0:
                for asset_class, market_value in results:
                    if asset_class in self.ASSET_CLASSES:
                        allocation[asset_class] = (market_value / total_portfolio_value) * 100.0

            # Update cache
            self._allocation_cache = allocation.copy()
            self._cache_timestamp = datetime.now()

            self.logger.debug(f"Current allocation calculated: {allocation}")

            return allocation

        except Exception as e:
            self.logger.error(f"Failed to calculate current allocation: {e}")
            # Return zero allocation on error
            return {asset_class: 0.0 for asset_class in self.ASSET_CLASSES}

    def calculate_drift(self) -> Dict[str, float]:
        """
        Calculate drift between current and target allocations.

        Drift = Current Allocation % - Target Allocation %
        Positive drift: Asset class is overweight
        Negative drift: Asset class is underweight

        Returns:
            Dict[str, float]: Asset class -> drift percentage mapping
        """
        current_allocation = self.get_current_allocation()
        target_allocation = self.get_allocation_targets()

        drift = {}
        for asset_class in self.ASSET_CLASSES:
            current = current_allocation.get(asset_class, 0.0)
            target = target_allocation.get(asset_class, 0.0)
            drift[asset_class] = current - target

        self.logger.debug(f"Drift calculated: {drift}")

        return drift

    def get_max_drift(self) -> Tuple[str, float]:
        """
        Get asset class with maximum absolute drift.

        Returns:
            Tuple[str, float]: (asset_class, drift_percentage)
        """
        drift = self.calculate_drift()

        # Find max absolute drift
        max_asset_class = max(drift.items(), key=lambda x: abs(x[1]))

        return max_asset_class

    def check_rebalancing_needed(self, check_date: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Check if portfolio rebalancing is needed based on template configuration.

        Rebalancing Triggers:
        - Threshold method: Any asset class drift exceeds drift_threshold_percent
        - Periodic method: Time since last rebalance >= periodic_interval_days
        - Hybrid method: Either threshold OR periodic condition met

        Args:
            check_date: Date to check rebalancing against (default: now)

        Returns:
            Tuple[bool, str]: (rebalancing_needed, reason)
        """
        if check_date is None:
            check_date = datetime.now()

        rebalancing_config = self.get_rebalancing_config()
        method = rebalancing_config['method']

        # Check threshold-based rebalancing
        threshold_triggered = False
        threshold_reason = ""

        if method in ['threshold', 'hybrid']:
            drift_threshold = rebalancing_config.get('drift_threshold_percent', 5.0)
            max_asset_class, max_drift = self.get_max_drift()

            if abs(max_drift) > drift_threshold:
                threshold_triggered = True
                threshold_reason = (
                    f"Drift threshold exceeded: {max_asset_class} "
                    f"drift={max_drift:+.2f}% (threshold={drift_threshold}%)"
                )

        # Check periodic rebalancing
        periodic_triggered = False
        periodic_reason = ""

        if method in ['periodic', 'hybrid']:
            periodic_interval = rebalancing_config.get('periodic_interval_days', 90)

            # Query last rebalancing date from database
            try:
                query = """
                    SELECT MAX(execution_start_time)
                    FROM rebalancing_history
                    WHERE template_name = ?
                      AND status = 'completed'
                """
                result = self.db_manager.execute_query(query, (self.template_name,))

                if result and result[0][0]:
                    last_rebalance_str = result[0][0]
                    # Parse datetime from SQLite string
                    last_rebalance = datetime.fromisoformat(last_rebalance_str)
                    days_since = (check_date - last_rebalance).days

                    if days_since >= periodic_interval:
                        periodic_triggered = True
                        periodic_reason = (
                            f"Periodic interval reached: {days_since} days since last rebalance "
                            f"(interval={periodic_interval} days)"
                        )
                else:
                    # No previous rebalancing - trigger periodic
                    periodic_triggered = True
                    periodic_reason = "No previous rebalancing history found"

            except Exception as e:
                self.logger.warning(f"Failed to check periodic rebalancing: {e}")

        # Determine final rebalancing decision based on method
        if method == 'threshold':
            needed = threshold_triggered
            reason = threshold_reason if threshold_triggered else "No threshold breach"

        elif method == 'periodic':
            needed = periodic_triggered
            reason = periodic_reason if periodic_triggered else "Periodic interval not reached"

        elif method == 'hybrid':
            needed = threshold_triggered or periodic_triggered
            if threshold_triggered and periodic_triggered:
                reason = f"{threshold_reason} AND {periodic_reason}"
            elif threshold_triggered:
                reason = threshold_reason
            elif periodic_triggered:
                reason = periodic_reason
            else:
                reason = "No rebalancing trigger met"

        else:
            needed = False
            reason = f"Unknown rebalancing method: {method}"

        self.logger.info(f"Rebalancing check: needed={needed}, reason={reason}")

        return (needed, reason)

    def log_drift_to_database(self) -> None:
        """
        Log current drift metrics to allocation_drift_log table.

        Alert Levels:
        - Green: |drift| <= 3%
        - Yellow: 3% < |drift| <= 5%
        - Red: |drift| > 5%
        """
        drift = self.calculate_drift()
        drift_threshold = self.get_rebalancing_config().get('drift_threshold_percent', 5.0)

        try:
            for asset_class, drift_percent in drift.items():
                target = self.get_allocation_targets()[asset_class]
                current = self.get_current_allocation()[asset_class]

                # Determine alert level
                abs_drift = abs(drift_percent)
                if abs_drift <= 3.0:
                    alert_level = 'green'
                    rebalancing_needed = 0
                elif abs_drift <= 5.0:
                    alert_level = 'yellow'
                    rebalancing_needed = 0
                else:
                    alert_level = 'red'
                    rebalancing_needed = 1 if abs_drift > drift_threshold else 0

                # Insert drift log
                insert_query = """
                    INSERT INTO allocation_drift_log (
                        template_name, asset_class,
                        target_percent, current_percent, drift_percent,
                        alert_level, rebalancing_needed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """

                self.db_manager.execute_update(
                    insert_query,
                    (self.template_name, asset_class, target, current, drift_percent,
                     alert_level, rebalancing_needed)
                )

            self.logger.info(f"Drift logged to database for template '{self.template_name}'")

        except Exception as e:
            self.logger.error(f"Failed to log drift to database: {e}")

    def invalidate_cache(self) -> None:
        """
        Invalidate allocation cache.

        Call this after updating holdings to force recalculation.
        """
        self._allocation_cache = None
        self._cache_timestamp = None
        self.logger.debug("Allocation cache invalidated")

    def __repr__(self) -> str:
        """String representation of PortfolioAllocator"""
        return (
            f"PortfolioAllocator(template='{self.template_name}', "
            f"risk_level='{self.template_config['risk_level']}')"
        )

    def __str__(self) -> str:
        """Human-readable string representation"""
        allocation = self.template_config['allocation']
        alloc_str = ', '.join([f"{k}: {v}%" for k, v in allocation.items()])
        return f"{self.template_config['name']} ({alloc_str})"


# Module-level convenience functions

def load_template(template_name: str, db_manager, config_dir: str = 'config') -> PortfolioAllocator:
    """
    Convenience function to create PortfolioAllocator instance.

    Args:
        template_name: Template name to load
        db_manager: Database manager instance
        config_dir: Configuration directory (default: 'config')

    Returns:
        PortfolioAllocator: Initialized allocator instance
    """
    return PortfolioAllocator(template_name, db_manager, config_dir)


def list_templates(config_dir: str = 'config') -> List[str]:
    """
    List all available templates without initializing allocator.

    Args:
        config_dir: Configuration directory (default: 'config')

    Returns:
        List[str]: Available template names
    """
    config_file = Path(config_dir) / 'portfolio_templates.yaml'

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        return list(config.get('templates', {}).keys())

    except Exception:
        return []


if __name__ == '__main__':
    # Demo usage
    import sys
    from pathlib import Path
    # Add parent directory to path for imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from modules.db_manager_sqlite import SQLiteDatabaseManager

    # Initialize database manager
    db = SQLiteDatabaseManager(db_path='data/spock_local.db')

    # List available templates
    print("Available Templates:")
    templates = list_templates()
    for template in templates:
        print(f"  - {template}")

    # Load balanced template (default)
    print("\nLoading 'balanced' template...")
    allocator = load_template('balanced', db)

    print(f"\nTemplate: {allocator}")
    print(f"Risk Level: {allocator.template_config['risk_level']}")

    print("\nTarget Allocation:")
    for asset_class, percentage in allocator.get_allocation_targets().items():
        print(f"  {asset_class}: {percentage}%")

    print("\nRebalancing Configuration:")
    rebalancing = allocator.get_rebalancing_config()
    print(f"  Method: {rebalancing['method']}")
    print(f"  Drift Threshold: {rebalancing.get('drift_threshold_percent', 'N/A')}%")

    print("\nPosition Limits:")
    limits = allocator.get_position_limits()
    for key, value in limits.items():
        print(f"  {key}: {value}")
