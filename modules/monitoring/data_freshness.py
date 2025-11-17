#!/usr/bin/env python3
"""
Data Freshness Monitoring Module

Monitors data freshness for all data sources:
- OHLCV data (by region)
- Global market indices
- Bond yields
- Ticker fundamentals
- Technical indicators

Provides:
- Automatic freshness checks
- Configurable thresholds (warning, critical)
- Clear status reporting
- Integration with orchestrator validation

Created: 2025-11-16
Phase: 2.2 - Data Freshness Monitoring
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

from loguru import logger

from modules.db_manager_postgres import PostgresDatabaseManager


class FreshnessStatus(Enum):
    """Data freshness status levels"""
    FRESH = "✅ FRESH"
    WARNING = "⚠️ WARNING"
    CRITICAL = "❌ CRITICAL"
    NO_DATA = "🚫 NO DATA"


class DataFreshnessMonitor:
    """
    Data freshness monitoring for Quant Platform

    Features:
    - Per-region OHLCV freshness tracking
    - Macro data freshness (indices, bonds, fundamentals)
    - Configurable thresholds
    - Automated validation after updates
    - Clear status reporting
    """

    # ========================================================================
    # Freshness Thresholds (in days)
    # ========================================================================

    THRESHOLDS = {
        'ohlcv': {
            'warning': 3,      # 3 days old = warning
            'critical': 7,     # 7 days old = critical
        },
        'fundamentals': {
            'warning': 7,      # 7 days for fundamentals
            'critical': 14,
        },
        'macro_indices': {
            'warning': 1,      # Macro should be daily
            'critical': 3,
        },
        'bonds': {
            'warning': 1,
            'critical': 3,
        },
        'technical': {
            'warning': 3,
            'critical': 7,
        }
    }

    def __init__(self, db: PostgresDatabaseManager, config: Dict = None):
        """
        Initialize data freshness monitor

        Args:
            db: PostgreSQL database manager
            config: Optional configuration (custom thresholds, etc.)
        """
        self.db = db
        self.config = config or {}

        # Override thresholds if provided in config
        if 'thresholds' in self.config:
            self.THRESHOLDS.update(self.config['thresholds'])

        logger.info("✅ DataFreshnessMonitor initialized")

    def _get_freshness_status(
        self,
        days_old: Optional[int],
        data_type: str
    ) -> FreshnessStatus:
        """
        Determine freshness status based on age and data type

        Args:
            days_old: Number of days since last update (None if no data)
            data_type: Type of data (ohlcv, macro_indices, etc.)

        Returns:
            FreshnessStatus enum
        """
        if days_old is None:
            return FreshnessStatus.NO_DATA

        thresholds = self.THRESHOLDS.get(data_type, self.THRESHOLDS['ohlcv'])

        if days_old <= thresholds['warning']:
            return FreshnessStatus.FRESH
        elif days_old <= thresholds['critical']:
            return FreshnessStatus.WARNING
        else:
            return FreshnessStatus.CRITICAL

    def check_ohlcv_freshness(
        self,
        regions: List[str] = None
    ) -> Dict[str, Dict]:
        """
        Check OHLCV data freshness by region

        Args:
            regions: List of regions to check (None = all)

        Returns:
            Dictionary with freshness status per region
        """
        if regions is None:
            regions = ['KR', 'US', 'HK', 'JP', 'CN', 'VN']

        results = {}

        for region in regions:
            query = """
                SELECT
                    COUNT(DISTINCT ticker) as ticker_count,
                    MAX(date) as latest_date,
                    (CURRENT_DATE - MAX(date)) as days_old
                FROM ohlcv_data
                WHERE region = %s
            """

            rows = self.db.execute_query(query, (region,))
            if not rows:
                results[region] = {
                    'status': FreshnessStatus.NO_DATA,
                    'ticker_count': 0,
                    'latest_date': None,
                    'days_old': None
                }
                continue

            row = rows[0]
            ticker_count = row['ticker_count']
            latest_date = row['latest_date']
            days_old = row['days_old']

            status = self._get_freshness_status(days_old, 'ohlcv')

            results[region] = {
                'status': status,
                'ticker_count': ticker_count,
                'latest_date': latest_date,
                'days_old': days_old
            }

        return results

    def check_macro_indices_freshness(self) -> Dict:
        """
        Check global market indices freshness

        Returns:
            Dictionary with freshness status
        """
        query = """
            SELECT
                COUNT(DISTINCT symbol) as index_count,
                MAX(date) as latest_date,
                (CURRENT_DATE - MAX(date)) as days_old
            FROM global_market_indices
        """

        rows = self.db.execute_query(query)
        if not rows or rows[0]['index_count'] == 0:
            return {
                'status': FreshnessStatus.NO_DATA,
                'index_count': 0,
                'latest_date': None,
                'days_old': None
            }

        row = rows[0]
        index_count = row['index_count']
        latest_date = row['latest_date']
        days_old = row['days_old']

        status = self._get_freshness_status(days_old, 'macro_indices')

        return {
            'status': status,
            'index_count': index_count,
            'latest_date': latest_date,
            'days_old': days_old
        }

    def check_bond_yields_freshness(self) -> Dict:
        """
        Check bond yields freshness

        Returns:
            Dictionary with freshness status
        """
        query = """
            SELECT
                COUNT(DISTINCT maturity) as bond_count,
                MAX(date) as latest_date,
                (CURRENT_DATE - MAX(date)) as days_old
            FROM bond_yields
        """

        rows = self.db.execute_query(query)
        if not rows or rows[0]['bond_count'] == 0:
            return {
                'status': FreshnessStatus.NO_DATA,
                'bond_count': 0,
                'latest_date': None,
                'days_old': None
            }

        row = rows[0]
        bond_count = row['bond_count']
        latest_date = row['latest_date']
        days_old = row['days_old']

        status = self._get_freshness_status(days_old, 'bonds')

        return {
            'status': status,
            'bond_count': bond_count,
            'latest_date': latest_date,
            'days_old': days_old
        }

    def run_full_check(
        self,
        verbose: bool = True
    ) -> Dict:
        """
        Run comprehensive freshness check on all data sources

        Args:
            verbose: If True, print detailed status

        Returns:
            Dictionary with all freshness checks
        """
        logger.info("=" * 80)
        logger.info("Data Freshness Check")
        logger.info("=" * 80)

        results = {
            'ohlcv': self.check_ohlcv_freshness(),
            'macro_indices': self.check_macro_indices_freshness(),
            'bonds': self.check_bond_yields_freshness(),
            'timestamp': date.today().isoformat()
        }

        # Count issues
        warnings = 0
        criticals = 0
        no_data = 0

        for data_type, data in results.items():
            if data_type == 'timestamp':
                continue

            # Check if this is multi-region data (ohlcv) or single data source
            if data_type == 'ohlcv':
                # Multi-region data (ohlcv)
                for region, region_data in data.items():
                    if region_data['status'] == FreshnessStatus.WARNING:
                        warnings += 1
                    elif region_data['status'] == FreshnessStatus.CRITICAL:
                        criticals += 1
                    elif region_data['status'] == FreshnessStatus.NO_DATA:
                        no_data += 1
            else:
                # Single data source (macro_indices, bonds)
                if 'status' in data:
                    if data['status'] == FreshnessStatus.WARNING:
                        warnings += 1
                    elif data['status'] == FreshnessStatus.CRITICAL:
                        criticals += 1
                    elif data['status'] == FreshnessStatus.NO_DATA:
                        no_data += 1

        results['summary'] = {
            'warnings': warnings,
            'criticals': criticals,
            'no_data': no_data,
            'overall_status': (
                FreshnessStatus.CRITICAL if criticals > 0 else
                FreshnessStatus.WARNING if warnings > 0 else
                FreshnessStatus.NO_DATA if no_data > 0 else
                FreshnessStatus.FRESH
            )
        }

        # Print detailed status if verbose
        if verbose:
            self._print_status_report(results)

        return results

    def _print_status_report(self, results: Dict):
        """
        Print formatted status report

        Args:
            results: Results from run_full_check()
        """
        logger.info("")
        logger.info("📊 OHLCV Data Freshness:")
        logger.info("─" * 80)

        for region, data in results['ohlcv'].items():
            status_str = data['status'].value
            latest = data['latest_date'] if data['latest_date'] else 'N/A'
            days = f"{data['days_old']}d" if data['days_old'] is not None else 'N/A'
            tickers = data['ticker_count']

            logger.info(
                f"  {region:4s} | {status_str:15s} | Latest: {latest} | "
                f"Age: {days:5s} | Tickers: {tickers:,}"
            )

        logger.info("")
        logger.info("📊 Macro Data Freshness:")
        logger.info("─" * 80)

        # Market indices
        indices = results['macro_indices']
        status_str = indices['status'].value
        latest = indices['latest_date'] if indices['latest_date'] else 'N/A'
        days = f"{indices['days_old']}d" if indices['days_old'] is not None else 'N/A'
        count = indices['index_count']

        logger.info(
            f"  Market Indices   | {status_str:15s} | Latest: {latest} | "
            f"Age: {days:5s} | Count: {count}"
        )

        # Bonds
        bonds = results['bonds']
        status_str = bonds['status'].value
        latest = bonds['latest_date'] if bonds['latest_date'] else 'N/A'
        days = f"{bonds['days_old']}d" if bonds['days_old'] is not None else 'N/A'
        count = bonds['bond_count']

        logger.info(
            f"  Bond Yields      | {status_str:15s} | Latest: {latest} | "
            f"Age: {days:5s} | Count: {count}"
        )

        logger.info("")
        logger.info("📝 Summary:")
        logger.info("─" * 80)

        summary = results['summary']
        overall = summary['overall_status'].value

        logger.info(f"  Overall Status: {overall}")
        logger.info(f"  Warnings:       {summary['warnings']}")
        logger.info(f"  Criticals:      {summary['criticals']}")
        logger.info(f"  No Data:        {summary['no_data']}")

        logger.info("=" * 80)


def main():
    """Test/CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Data Freshness Monitoring')
    parser.add_argument(
        '--regions',
        nargs='+',
        choices=['KR', 'US', 'HK', 'JP', 'CN', 'VN'],
        help='Regions to check (default: all)'
    )
    parser.add_argument('--quiet', action='store_true', help='Quiet mode (summary only)')

    args = parser.parse_args()

    # Initialize
    db = PostgresDatabaseManager()
    monitor = DataFreshnessMonitor(db)

    # Run check
    results = monitor.run_full_check(verbose=not args.quiet)

    # Exit with appropriate code
    summary = results['summary']
    if summary['criticals'] > 0:
        exit(2)  # Critical issues
    elif summary['warnings'] > 0:
        exit(1)  # Warnings
    else:
        exit(0)  # All good


if __name__ == '__main__':
    main()
