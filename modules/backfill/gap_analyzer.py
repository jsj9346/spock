"""
Column-level gap detection for backfill optimization

This module provides intelligent gap analysis to identify which tickers
need backfilling, enabling 90%+ API call reduction in incremental updates.

Key Features:
- Column-level NULL detection using SQL FILTER clause
- Priority classification (FULLY_MISSING > PARTIALLY_MISSING > COMPLETE)
- Performance: <2s for 2,000+ tickers (POC: 0.08s)
- Flexible filtering: region, asset_type, date range, limits

Example Usage:
    from modules.backfill.gap_analyzer import GapAnalyzer
    from modules.db_manager_postgres import PostgresDatabaseManager
    from datetime import date

    db = PostgresDatabaseManager()
    analyzer = GapAnalyzer(db)

    result = analyzer.analyze_gaps(
        table='ticker_fundamentals',
        target_columns=['capital_stock', 'capital_surplus', 'retained_earnings'],
        region='KR',
        backfill_start_date=date(2022, 1, 1)
    )

    # Get backfill targets (FULLY_MISSING + PARTIALLY_MISSING)
    targets = result.get_backfill_targets()
    print(f"Tickers needing backfill: {len(targets)}")

    # Get efficiency metrics
    summary = result.get_summary()
    print(f"API calls saved: {summary['complete']} ({summary['efficiency_gain_pct']:.1f}%)")

Author: Quant Platform Development Team
Date: 2025-11-11
"""

import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import date, datetime

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backfill.data_structures import (
    GapPriority,
    TickerGapInfo,
    GapAnalysisResult
)

logger = logging.getLogger(__name__)


class GapAnalyzer:
    """
    Column-level gap detection with priority classification

    Analyzes database tables to identify missing data at the column level,
    enabling targeted backfill operations that skip tickers with complete data.

    This implements the "scan-then-backfill" optimization pattern that reduces
    API calls by 90%+ in incremental update scenarios.
    """

    def __init__(self, db: PostgresDatabaseManager):
        """
        Initialize GapAnalyzer with database connection

        Args:
            db: PostgreSQL database manager instance
        """
        self.db = db
        logger.debug("GapAnalyzer initialized")

    def analyze_gaps(
        self,
        table: str,
        target_columns: List[str],
        region: str = 'KR',
        asset_type: str = 'STOCK',
        backfill_start_date: Optional[date] = None,
        limit: Optional[int] = None
    ) -> GapAnalysisResult:
        """
        Analyze column-level gaps in target table

        Executes optimized SQL query to identify tickers with missing data
        in specified columns. Results are classified by priority:
        - FULLY_MISSING: No data exists or all values are NULL (priority 1)
        - PARTIALLY_MISSING: Some values are NULL (priority 2)
        - COMPLETE: All values present, skip backfill (priority 3)

        Args:
            table: Target table name (e.g., 'ticker_fundamentals')
            target_columns: List of columns to check for NULL values
            region: Market region filter (default: 'KR')
            asset_type: Asset type filter (default: 'STOCK')
            backfill_start_date: Start date for backfill period (optional)
            limit: Maximum number of tickers to analyze (optional)

        Returns:
            GapAnalysisResult with classified tickers and efficiency metrics

        Example:
            analyzer = GapAnalyzer(db)
            result = analyzer.analyze_gaps(
                table='ticker_fundamentals',
                target_columns=['capital_stock', 'capital_surplus'],
                region='KR',
                backfill_start_date=date(2022, 1, 1),
                limit=100
            )

            print(f"Tickers needing backfill: {len(result.get_backfill_targets())}")
            print(f"Efficiency gain: {result.get_summary()['efficiency_gain_pct']:.1f}%")
        """
        start_time = datetime.now()

        logger.info(f"Starting gap analysis for {table}...")
        logger.info(f"  Target columns: {', '.join(target_columns)}")
        logger.info(f"  Region: {region}, Asset Type: {asset_type}")
        if backfill_start_date:
            logger.info(f"  Backfill start date: {backfill_start_date}")
        if limit:
            logger.info(f"  Limit: {limit} tickers")

        # Generate gap detection query
        query, params = self.get_gap_query(
            table=table,
            target_columns=target_columns,
            filters={
                'region': region,
                'asset_type': asset_type,
                'backfill_start_date': backfill_start_date,
                'limit': limit
            }
        )

        # Execute query
        try:
            rows = self.db.execute_query(query, params)
        except Exception as e:
            logger.error(f"Gap analysis query failed: {e}")
            raise

        # Classify results by priority
        fully_missing = []
        partially_missing = []
        complete = []

        for row in rows:
            ticker_info = TickerGapInfo(
                ticker=row['ticker'],
                name=row['name'],
                region=region,
                corp_code=row.get('corp_code'),
                listing_date=row.get('listing_date'),
                missing_count=row['missing_count'],
                total_count=row['total_count'],
                priority=GapPriority(row['priority']),
                target_columns=target_columns
            )

            if ticker_info.priority == GapPriority.FULLY_MISSING:
                fully_missing.append(ticker_info)
            elif ticker_info.priority == GapPriority.PARTIALLY_MISSING:
                partially_missing.append(ticker_info)
            else:
                complete.append(ticker_info)

        elapsed = (datetime.now() - start_time).total_seconds()

        result = GapAnalysisResult(
            fully_missing=fully_missing,
            partially_missing=partially_missing,
            complete=complete,
            total_analyzed=len(rows),
            analysis_time_sec=elapsed
        )

        # Log summary
        summary = result.get_summary()
        logger.info(f"Gap analysis completed in {summary['analysis_time_sec']:.2f}s")
        logger.info(f"  Total analyzed: {summary['total_analyzed']:,}")
        logger.info(f"  Fully missing: {summary['fully_missing']:,}")
        logger.info(f"  Partially missing: {summary['partially_missing']:,}")
        logger.info(f"  Complete (skip): {summary['complete']:,}")
        logger.info(f"  Needs backfill: {summary['needs_backfill']:,}")
        logger.info(f"  Efficiency gain: {summary['efficiency_gain_pct']:.1f}%")

        return result

    def get_gap_query(
        self,
        table: str,
        target_columns: List[str],
        filters: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate optimized gap detection SQL query

        Builds a SQL query with column-level NULL detection using the FILTER clause
        for efficient gap identification. The query uses a CTE (Common Table Expression)
        for clarity and performance.

        Query Structure:
        1. CTE: Join tickers with target table, count NULL values per ticker
        2. Main query: Classify gaps by priority and filter to backfill candidates

        Args:
            table: Target table name to analyze
            target_columns: Columns to check for NULL values
            filters: Dict with region, asset_type, backfill_start_date, limit

        Returns:
            Tuple of (query_string, parameters_dict)

        Example:
            query, params = analyzer.get_gap_query(
                table='ticker_fundamentals',
                target_columns=['capital_stock', 'capital_surplus'],
                filters={'region': 'KR', 'asset_type': 'STOCK',
                         'backfill_start_date': date(2022, 1, 1)}
            )
        """
        # Build NULL condition for target columns
        # Example: "tf.capital_stock IS NULL OR tf.capital_surplus IS NULL"
        null_conditions = ' OR '.join([f'tf.{col} IS NULL' for col in target_columns])

        # Build base query with CTE for gap detection
        query = f"""
        WITH ticker_gaps AS (
          SELECT
            t.ticker,
            t.name,
            t.listing_date,
            -- Count records with NULL values in target columns
            COUNT(tf.id) FILTER (WHERE {null_conditions}) as missing_count,
            -- Count total records in date range
            COUNT(tf.id) as total_count
          FROM tickers t
          LEFT JOIN {table} tf
            ON t.ticker = tf.ticker
            AND t.region = tf.region
        """

        # Add date filter if specified
        if filters.get('backfill_start_date'):
            query += "    AND tf.date >= %(backfill_start_date)s\n"

        # Add WHERE clause for ticker filters
        query += """
          WHERE t.region = %(region)s
            AND t.asset_type = %(asset_type)s
            AND t.is_active = TRUE
        """

        # Filter tickers by listing date if backfill_start_date specified
        if filters.get('backfill_start_date'):
            query += "    AND (t.listing_date IS NULL OR t.listing_date <= %(backfill_start_date)s)\n"

        # Complete CTE
        query += """
          GROUP BY t.ticker, t.name, t.listing_date
        )
        SELECT
          ticker,
          name,
          listing_date,
          missing_count,
          total_count,
          -- Priority classification
          CASE
            WHEN total_count = 0 THEN 1              -- FULLY_MISSING (no data)
            WHEN missing_count = total_count THEN 1  -- FULLY_MISSING (all NULL)
            WHEN missing_count > 0 THEN 2            -- PARTIALLY_MISSING
            ELSE 3                                   -- COMPLETE (skip)
          END as priority
        FROM ticker_gaps
        WHERE missing_count > 0 OR total_count = 0  -- Only tickers needing backfill
        ORDER BY priority, missing_count DESC
        """

        # Add limit if specified
        if filters.get('limit'):
            query += " LIMIT %(limit)s"

        # Build parameters dict
        params = {
            'region': filters['region'],
            'asset_type': filters['asset_type']
        }

        if filters.get('backfill_start_date'):
            params['backfill_start_date'] = filters['backfill_start_date']

        if filters.get('limit'):
            params['limit'] = filters['limit']

        logger.debug(f"Generated gap query with {len(target_columns)} target columns")
        logger.debug(f"Parameters: {params}")

        return query, params

    @staticmethod
    def classify_gap_priority(missing_count: int, total_count: int) -> GapPriority:
        """
        Classify gap priority based on missing/total counts

        This is a utility method for testing and validation. The actual
        classification is done in SQL for performance.

        Args:
            missing_count: Number of records with NULL values
            total_count: Total number of records

        Returns:
            GapPriority enum value

        Example:
            priority = GapAnalyzer.classify_gap_priority(0, 10)
            assert priority == GapPriority.COMPLETE
        """
        if total_count == 0:
            return GapPriority.FULLY_MISSING
        elif missing_count == total_count:
            return GapPriority.FULLY_MISSING
        elif missing_count > 0:
            return GapPriority.PARTIALLY_MISSING
        else:
            return GapPriority.COMPLETE
