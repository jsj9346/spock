#!/usr/bin/env python3
"""
Dividend Data Migration Script

Migrates existing dividend data from ticker_fundamentals to dividend_history table.
This script extracts the most recent dividend information from DAILY data
and creates initial records in the dividend_history table.

Note: For complete dividend history, use DividendCollector to fetch from external sources.
"""

import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.constants.regions import CURRENCY_MAP


class DividendDataMigrator:
    """Migrates dividend data from ticker_fundamentals to dividend_history"""

    def __init__(self, db_manager: PostgresDatabaseManager):
        self.db = db_manager
        self.migrated_count = 0
        self.skipped_count = 0
        self.error_count = 0

    def get_latest_dividend_data(self, region: str) -> List[Dict]:
        """
        Get the most recent dividend data for each ticker from DAILY data.

        Uses window function to get the latest record per ticker where
        dividend_per_share is non-null and positive.
        """
        query = """
        WITH latest_dividends AS (
            SELECT
                ticker,
                region,
                date,
                dividend_per_share,
                dividend_yield,
                ROW_NUMBER() OVER (
                    PARTITION BY ticker
                    ORDER BY date DESC
                ) as rn
            FROM ticker_fundamentals
            WHERE region = %s
                AND period_type = 'DAILY'
                AND dividend_per_share IS NOT NULL
                AND dividend_per_share > 0
        )
        SELECT
            ticker,
            region,
            date,
            dividend_per_share,
            dividend_yield
        FROM latest_dividends
        WHERE rn = 1
        ORDER BY ticker;
        """

        result = self.db.execute_query(query, (region,))
        return result if result else []

    def check_existing_record(self, ticker: str, region: str, fiscal_year: int) -> bool:
        """Check if a record already exists in dividend_history"""
        query = """
        SELECT 1 FROM dividend_history
        WHERE ticker = %s AND region = %s AND fiscal_year = %s
        LIMIT 1;
        """
        result = self.db.execute_query(query, (ticker, region, fiscal_year))
        return len(result) > 0 if result else False

    def insert_dividend_record(self, record: Dict) -> bool:
        """Insert a single dividend record into dividend_history"""
        query = """
        INSERT INTO dividend_history (
            ticker, region, fiscal_year, dividend_type,
            dividend_per_share, dividend_yield,
            currency, data_source
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s,
            %s, %s
        )
        ON CONFLICT (ticker, region, fiscal_year, dividend_type, ex_dividend_date)
        DO UPDATE SET
            dividend_per_share = EXCLUDED.dividend_per_share,
            dividend_yield = EXCLUDED.dividend_yield,
            updated_at = NOW();
        """

        try:
            success = self.db.execute_update(query, (
                record['ticker'],
                record['region'],
                record['fiscal_year'],
                record['dividend_type'],
                record['dividend_per_share'],
                record['dividend_yield'],
                record['currency'],
                record['data_source'],
            ))
            return success
        except Exception as e:
            logger.error(f"Failed to insert {record['ticker']}: {e}")
            return False

    def migrate_region(self, region: str) -> Dict:
        """Migrate dividend data for a specific region"""
        logger.info(f"Starting migration for region: {region}")

        # Get latest dividend data
        dividend_data = self.get_latest_dividend_data(region)
        logger.info(f"Found {len(dividend_data)} tickers with dividend data in {region}")

        region_stats = {
            "total": len(dividend_data),
            "migrated": 0,
            "skipped": 0,
            "errors": 0,
        }

        current_year = datetime.now().year

        for record in dividend_data:
            # Determine fiscal year from date
            record_date = record.get('date')
            if record_date:
                if isinstance(record_date, str):
                    record_date = datetime.strptime(record_date, '%Y-%m-%d').date()
                fiscal_year = record_date.year
            else:
                fiscal_year = current_year

            # Check if already exists
            exists = self.check_existing_record(
                record['ticker'], region, fiscal_year
            )

            if exists:
                region_stats["skipped"] += 1
                self.skipped_count += 1
                continue

            # Prepare record for insertion
            migration_record = {
                "ticker": record['ticker'],
                "region": region,
                "fiscal_year": fiscal_year,
                "dividend_type": "annual",  # Default to annual for migrated data
                "dividend_per_share": record['dividend_per_share'],
                "dividend_yield": record['dividend_yield'],
                "currency": CURRENCY_MAP.get(region, "USD"),
                "data_source": "migration_from_fundamentals",
            }

            success = self.insert_dividend_record(migration_record)

            if success:
                region_stats["migrated"] += 1
                self.migrated_count += 1
            else:
                region_stats["errors"] += 1
                self.error_count += 1

        logger.info(
            f"Region {region} completed: "
            f"migrated={region_stats['migrated']}, "
            f"skipped={region_stats['skipped']}, "
            f"errors={region_stats['errors']}"
        )

        return region_stats

    def run_migration(self, regions: Optional[List[str]] = None) -> Dict:
        """
        Run the full migration for specified regions.

        Args:
            regions: List of region codes to migrate. If None, migrate all.

        Returns:
            Migration summary statistics
        """
        if regions is None:
            regions = ["KR", "US", "JP", "HK", "CN", "VN"]

        logger.info(f"Starting dividend data migration for regions: {regions}")

        results = {}
        for region in regions:
            try:
                results[region] = self.migrate_region(region)
            except Exception as e:
                logger.error(f"Failed to migrate region {region}: {e}")
                results[region] = {"error": str(e)}

        summary = {
            "total_migrated": self.migrated_count,
            "total_skipped": self.skipped_count,
            "total_errors": self.error_count,
            "regions": results,
        }

        return summary


def main():
    """Run dividend data migration"""
    logger.info("=" * 60)
    logger.info("Dividend Data Migration")
    logger.info("=" * 60)

    # Initialize database connection
    db_manager = PostgresDatabaseManager()

    # Create migrator and run
    migrator = DividendDataMigrator(db_manager)
    summary = migrator.run_migration()

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("Migration Summary")
    logger.info("=" * 60)
    logger.info(f"Total Migrated: {summary['total_migrated']}")
    logger.info(f"Total Skipped:  {summary['total_skipped']}")
    logger.info(f"Total Errors:   {summary['total_errors']}")

    logger.info("\nBy Region:")
    for region, stats in summary['regions'].items():
        if isinstance(stats, dict) and 'error' not in stats:
            logger.info(
                f"  {region}: migrated={stats.get('migrated', 0)}, "
                f"skipped={stats.get('skipped', 0)}, "
                f"errors={stats.get('errors', 0)}"
            )
        else:
            logger.error(f"  {region}: FAILED - {stats.get('error', 'Unknown error')}")

    return summary


if __name__ == "__main__":
    result = main()

    # Exit with error code if there were errors
    if result.get('total_errors', 0) > 0:
        sys.exit(1)
    sys.exit(0)
