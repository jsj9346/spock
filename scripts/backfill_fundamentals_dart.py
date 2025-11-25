#!/usr/bin/env python3
"""
Phase 2: DART Annual Fundamental Data Backfill for KR Market

Backfills ticker_fundamentals table with ANNUAL financial statement data from DART API.
Collects multi-year historical data (2022-2024) for accurate ROE and YOY growth calculations.
Extracts: ROE, ROA, Debt Ratio, Revenue, Operating Profit, Net Income, Total Assets/Liabilities/Equity

Target Coverage: >80% of KR market (1,091+ stocks out of 1,364)
Data Source: DART (Korea Financial Supervisory Service)
Period Type: ANNUAL (11011) - consolidated financial statements only

Usage:
    # Gap-Aware Backfill (Recommended for Incremental Updates - Phase 3)
    python3 scripts/backfill_fundamentals_dart.py --use-gap-analysis --limit 100

    # Gap-Aware Dry Run (Preview gap analysis + backfill targets)
    python3 scripts/backfill_fundamentals_dart.py --use-gap-analysis --dry-run --limit 10

    # Gap-Aware with Custom Columns
    python3 scripts/backfill_fundamentals_dart.py --use-gap-analysis \
        --target-columns capital_stock capital_surplus retained_earnings treasury_stock

    # ====== Legacy Mode (Backward Compatibility) ======

    # Full backfill (2022-2024 annual data)
    python3 scripts/backfill_fundamentals_dart.py

    # Dry run (preview only)
    python3 scripts/backfill_fundamentals_dart.py --dry-run --limit 5

    # Custom year range
    python3 scripts/backfill_fundamentals_dart.py --start-year 2020 --end-year 2024

    # Incremental update (only missing data)
    python3 scripts/backfill_fundamentals_dart.py --incremental

    # Limit processing (for testing)
    python3 scripts/backfill_fundamentals_dart.py --limit 10

    # Rate limiting (requests per hour)
    python3 scripts/backfill_fundamentals_dart.py --rate-limit 1.0  # 1 req/sec

Expected Results:
    - ~3,273 records (1,091 tickers × 3 years)
    - ROE accuracy: 7-15% (vs 1.28% with SEMI-ANNUAL data)
    - Flexible mode screening: 30-50 stocks (vs 0 before)
    - Strict mode screening: 5-10 stocks (vs 0 before)

Author: Quant Investment Platform - Phase 2
"""

import sys
import os
import argparse
import logging
import json
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
from decimal import Decimal

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.dart_api_client import DARTApiClient
from modules.backfill.orchestrator import BackfillOrchestrator
from modules.backfill.gap_analyzer import GapAnalyzer
from modules.backfill.data_structures import GapPriority
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
log_filename = f"log/{datetime.now().strftime('%Y%m%d')}_backfill_fundamentals_dart.log"
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class DARTFundamentalBackfiller:
    """DART fundamental data backfill orchestrator"""

    def __init__(self, db: PostgresDatabaseManager, dart: DARTApiClient,
                 dry_run: bool = False, rate_limit_delay: float = 1.0,
                 start_year: int = 2022, end_year: int = 2024):
        """
        Initialize backfiller

        Args:
            db: PostgreSQL database manager
            dart: DART API client
            dry_run: If True, preview operations without database writes
            rate_limit_delay: Delay between API calls in seconds (default: 1.0 = 1 req/sec)
            start_year: Start year for historical data collection (default: 2022)
            end_year: End year for historical data collection (default: 2024)
        """
        self.db = db
        self.dart = dart
        self.dry_run = dry_run
        self.rate_limit_delay = rate_limit_delay
        self.start_year = start_year
        self.end_year = end_year

        # Statistics
        self.stats = {
            'tickers_processed': 0,
            'tickers_success': 0,
            'tickers_skipped_no_corp_code': 0,
            'tickers_skipped_no_data': 0,
            'tickers_skipped_listing_date': 0,  # New: Filtered by listing_date
            'tickers_failed': 0,
            'api_calls': 0,
            'records_inserted': 0,
            'records_updated': 0,
            'records_processed': 0  # Total year records processed (tickers × years)
        }

        # Load corp code mapping
        self.corp_code_map = self._load_corp_code_mapping()

    def _load_corp_code_mapping(self) -> Dict[str, str]:
        """
        Load DART corp_code mapping from database or config file

        Returns:
            Dict mapping ticker -> corp_code
        """
        logger.info("Loading DART corp_code mapping...")

        # Try to load from database first (preferred)
        try:
            query = """
            SELECT ticker, corp_code
            FROM stock_details
            WHERE region = 'KR' AND corp_code IS NOT NULL
            """
            results = self.db.execute_query(query)

            corp_code_map = {row['ticker']: row['corp_code'] for row in results}
            logger.info(f"✅ Loaded {len(corp_code_map)} corp codes from database")

            if corp_code_map:
                return corp_code_map

        except Exception as e:
            logger.warning(f"Failed to load corp codes from database: {e}")

        # Fallback: Download and parse DART corp codes XML
        try:
            # Download corp codes XML file
            xml_path = self.dart.download_corp_codes()

            if not xml_path or not os.path.exists(xml_path):
                raise Exception("Failed to download corp codes XML")

            # Parse corp codes (returns corp_name -> {corp_code, stock_code})
            corp_data = self.dart.parse_corp_codes(xml_path)

            # Create reverse mapping: stock_code -> corp_code
            mapping = {}
            for corp_name, data in corp_data.items():
                stock_code = data.get('stock_code')
                corp_code = data.get('corp_code')

                if stock_code and corp_code and stock_code.strip():
                    # Normalize stock code to 6 digits (pad with leading zeros)
                    stock_code_normalized = stock_code.strip().zfill(6)
                    mapping[stock_code_normalized] = corp_code

            logger.info(f"✅ Loaded {len(mapping)} corp codes from DART XML")
            return mapping

        except Exception as e:
            logger.error(f"Failed to load corp codes from DART XML: {e}")

        # If all else fails, return empty dict (will skip tickers without corp codes)
        logger.warning("⚠️ No corp code mapping available - will skip most tickers")
        return {}

    def _get_earliest_backfill_date(self) -> date:
        """
        Get earliest date for backfill filtering

        Returns:
            Earliest backfill date (start_year-01-01)
        """
        return date(self.start_year, 1, 1)

    def _filter_by_listing_date(self, tickers: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Filter tickers by listing date relative to backfill period

        Args:
            tickers: List of ticker dicts with listing_date field

        Returns:
            Tuple of (valid_tickers, skipped_tickers)
        """
        earliest_date = self._get_earliest_backfill_date()
        valid = []
        skipped = []

        for ticker in tickers:
            listing_date = ticker.get('listing_date')

            # Include if: no listing_date OR listed before/on backfill start date
            if not listing_date or listing_date <= earliest_date:
                valid.append(ticker)
            else:
                skipped.append(ticker)
                logger.debug(
                    f"Skipping {ticker['ticker']} ({ticker['name']}) - "
                    f"listed after backfill period "
                    f"(listing_date: {listing_date}, earliest: {earliest_date})"
                )

        return valid, skipped

    def get_kr_tickers_for_backfill(self, incremental: bool = False, limit: Optional[int] = None,
                                     ticker_file: Optional[str] = None) -> List[Dict]:
        """
        Query KR tickers that need fundamental data backfill

        Args:
            incremental: If True, only fetch tickers missing recent data
            limit: Maximum number of tickers to return (for testing)
            ticker_file: CSV file path with ticker list (ticker,name,volume_rank columns)

        Returns:
            List of ticker dicts with ticker, name, corp_code
        """
        # Option 1: Load from CSV file (priority)
        if ticker_file:
            logger.info(f"📁 Loading tickers from file: {ticker_file}")
            import csv

            results = []
            try:
                with open(ticker_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        results.append({
                            'ticker': row['ticker'],
                            'name': row['name']
                        })

                logger.info(f"✅ Loaded {len(results)} tickers from CSV file")

            except Exception as e:
                logger.error(f"❌ Failed to load ticker file: {e}")
                return []

        # Option 2: Query from database
        else:
            earliest_date = self._get_earliest_backfill_date()

            if incremental:
                # Incremental: Only tickers with no data in last 90 days
                query = """
                SELECT DISTINCT t.ticker, t.name, t.listing_date
                FROM tickers t
                LEFT JOIN ticker_fundamentals tf ON t.ticker = tf.ticker
                    AND t.region = tf.region
                    AND tf.date >= NOW() - INTERVAL '90 days'
                WHERE t.region = 'KR'
                  AND t.asset_type = 'STOCK'
                  AND t.is_active = TRUE
                  AND (t.listing_date IS NULL OR t.listing_date <= %s)
                  AND tf.id IS NULL
                ORDER BY t.ticker
                """
                params = [earliest_date]
            else:
                # Full backfill: All KR stocks (exclude recently listed)
                query = """
                SELECT DISTINCT t.ticker, t.name, t.listing_date
                FROM tickers t
                WHERE t.region = 'KR'
                  AND t.asset_type = 'STOCK'
                  AND t.is_active = TRUE
                  AND (t.listing_date IS NULL OR t.listing_date <= %s)
                ORDER BY t.ticker
                """
                params = [earliest_date]

            if limit:
                query += f" LIMIT {limit}"

            results = self.db.execute_query(query, params)

        # Look up corp_code from config file for each ticker
        tickers_with_codes = []
        for row in results:
            ticker = row['ticker']
            name = row['name']

            # Look up corp_code from loaded corp_code_map dict
            corp_code = self.corp_code_map.get(ticker)

            if corp_code:
                tickers_with_codes.append({
                    'ticker': ticker,
                    'name': name,
                    'corp_code': corp_code
                })
            else:
                logger.debug(f"⚠️ [{ticker}] No DART corp_code found - skipping")

        logger.info(f"📊 Found {len(tickers_with_codes)} KR stocks with DART corp codes (from {len(results)} total)")
        return tickers_with_codes

    def fetch_dart_historical_fundamentals(self, ticker: str, corp_code: str,
                                           start_year: int, end_year: int) -> List[Dict]:
        """
        Fetch historical ANNUAL fundamental data for multiple years

        Args:
            ticker: Stock ticker (e.g., '005930')
            corp_code: DART corporate code (8-digit)
            start_year: Start year for data collection (e.g., 2022)
            end_year: End year for data collection (e.g., 2024)

        Returns:
            List of dicts with annual fundamental metrics (one per year)
        """
        try:
            # Rate limiting
            time.sleep(self.rate_limit_delay)
            self.stats['api_calls'] += 1

            # Call DART API for historical data (ANNUAL reports only)
            metrics_list = self.dart.get_historical_fundamentals(
                ticker=ticker,
                corp_code=corp_code,
                start_year=start_year,
                end_year=end_year
            )

            if not metrics_list:
                logger.warning(f"⚠️ [{ticker}] No historical data available ({start_year}-{end_year})")
                return []

            # Validate each year's data
            validated_metrics = []
            for metrics in metrics_list:
                if 'ticker' in metrics and 'date' in metrics and 'fiscal_year' in metrics:
                    validated_metrics.append(metrics)
                else:
                    year = metrics.get('fiscal_year', 'Unknown')
                    logger.warning(f"⚠️ [{ticker}] Invalid metrics structure for year {year}")

            if validated_metrics:
                logger.info(f"✅ [{ticker}] DART historical data: {len(validated_metrics)} years ({start_year}-{end_year})")
            else:
                logger.warning(f"⚠️ [{ticker}] No valid annual reports found")

            return validated_metrics

        except Exception as e:
            logger.error(f"❌ [{ticker}] DART API call failed: {e}")
            return []

    def get_latest_price(self, ticker: str, as_of_date: Optional[date] = None) -> Optional[Decimal]:
        """
        Get latest closing price from ohlcv_data

        Args:
            ticker: Stock ticker
            as_of_date: Specific date (if None, use latest available)

        Returns:
            Closing price or None
        """
        try:
            if as_of_date:
                query = """
                SELECT close FROM ohlcv_data
                WHERE ticker = %s AND region = 'KR' AND date <= %s
                ORDER BY date DESC LIMIT 1
                """
                params = (ticker, as_of_date)
            else:
                query = """
                SELECT close FROM ohlcv_data
                WHERE ticker = %s AND region = 'KR'
                ORDER BY date DESC LIMIT 1
                """
                params = (ticker,)

            result = self.db.execute_query(query, params)

            if result and len(result) > 0:
                return Decimal(str(result[0]['close']))
            else:
                logger.warning(f"⚠️ [{ticker}] No price data available")
                return None

        except Exception as e:
            logger.error(f"❌ [{ticker}] Failed to get price: {e}")
            return None

    def calculate_valuation_ratios(self, ticker: str, metrics: Dict, price: Decimal) -> Dict:
        """
        Calculate valuation ratios (P/E, P/B) from DART financial data

        Args:
            ticker: Stock ticker
            metrics: DART fundamental metrics
            price: Current stock price

        Returns:
            Dict with calculated ratios
        """
        ratios = {}

        try:
            # Extract financial statement items
            total_equity = metrics.get('total_equity', 0)
            net_income = metrics.get('net_income', 0)
            revenue = metrics.get('revenue', 0)
            shares_outstanding = metrics.get('shares_outstanding')  # May not be available

            # Calculate earnings per share (EPS)
            if net_income > 0 and shares_outstanding and shares_outstanding > 0:
                eps = net_income / shares_outstanding
                ratios['eps'] = eps

                # Calculate P/E ratio
                if eps > 0:
                    ratios['per'] = float(price / Decimal(str(eps)))

            # Calculate book value per share
            if total_equity > 0 and shares_outstanding and shares_outstanding > 0:
                book_value_per_share = total_equity / shares_outstanding
                ratios['book_value_per_share'] = book_value_per_share

                # Calculate P/B ratio
                if book_value_per_share > 0:
                    ratios['pbr'] = float(price / Decimal(str(book_value_per_share)))

            # Calculate P/S ratio (Price-to-Sales)
            if revenue > 0 and shares_outstanding and shares_outstanding > 0:
                sales_per_share = revenue / shares_outstanding
                if sales_per_share > 0:
                    ratios['psr'] = float(price / Decimal(str(sales_per_share)))

            # Calculate market cap (if shares_outstanding available)
            if shares_outstanding:
                ratios['market_cap'] = int(float(price) * shares_outstanding)

            logger.debug(f"📊 [{ticker}] Calculated ratios: PER={ratios.get('per')}, PBR={ratios.get('pbr')}")

        except Exception as e:
            logger.error(f"❌ [{ticker}] Failed to calculate ratios: {e}")

        return ratios

    def insert_or_update_fundamental_data(self, ticker: str, metrics: Dict, ratios: Dict, price: Decimal) -> bool:
        """
        Insert or update ticker_fundamentals record

        Args:
            ticker: Stock ticker
            metrics: DART fundamental metrics
            ratios: Calculated valuation ratios
            price: Current stock price

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would insert/update fundamental data for {ticker}")
            logger.info(f"  → Date: {metrics.get('date')}, Fiscal Year: {metrics.get('fiscal_year')}")
            logger.info(f"  → Data Source: {metrics.get('data_source')}")

            # Format large numbers with thousands separator
            assets = metrics.get('total_assets', 0)
            equity = metrics.get('total_equity', 0)
            liab = metrics.get('total_liabilities', 0)
            rev = metrics.get('revenue', 0)
            op_profit = metrics.get('operating_profit', 0)
            net_inc = metrics.get('net_income', 0)

            logger.info(f"  → Balance Sheet: Assets={assets:,.0f} KRW, Equity={equity:,.0f} KRW, Liabilities={liab:,.0f} KRW")
            logger.info(f"  → Income Statement: Revenue={rev:,.0f} KRW, Op.Profit={op_profit:,.0f} KRW, Net Income={net_inc:,.0f} KRW")

            roe = metrics.get('roe')
            per = ratios.get('per')
            pbr = ratios.get('pbr')
            roe_str = f"{roe:.2f}" if roe is not None else "N/A"
            per_str = f"{per:.2f}" if per is not None else "N/A"
            pbr_str = f"{pbr:.2f}" if pbr is not None else "N/A"
            logger.info(f"  → Ratios: ROE={roe_str}%, PER={per_str}, PBR={pbr_str}")
            return True

        try:
            # Prepare data for insertion
            data = {
                'ticker': ticker,
                'region': 'KR',
                'date': metrics.get('date'),
                'period_type': metrics.get('period_type', 'ANNUAL'),
                'close_price': float(price),
                'data_source': metrics.get('data_source'),

                # From DART
                'total_assets': metrics.get('total_assets'),
                'total_liabilities': metrics.get('total_liabilities'),
                'total_equity': metrics.get('total_equity'),
                'revenue': metrics.get('revenue'),
                'operating_profit': metrics.get('operating_profit'),
                'net_income': metrics.get('net_income'),
                'current_assets': metrics.get('current_assets'),
                'current_liabilities': metrics.get('current_liabilities'),
                'inventory': metrics.get('inventory'),
                'fiscal_year': metrics.get('fiscal_year'),
                'roe': metrics.get('roe'),
                'roa': metrics.get('roa'),
                'debt_ratio': metrics.get('debt_ratio'),

                # Calculated ratios
                'per': ratios.get('per'),
                'pbr': ratios.get('pbr'),
                'psr': ratios.get('psr'),
                'market_cap': ratios.get('market_cap'),
                'shares_outstanding': metrics.get('shares_outstanding'),

                # Phase 2: Manufacturing Industry Indicators (6)
                'cogs': metrics.get('cogs'),
                'gross_profit': metrics.get('gross_profit'),
                'pp_e': metrics.get('pp_e'),
                'depreciation': metrics.get('depreciation'),
                'accounts_receivable': metrics.get('accounts_receivable'),
                'accumulated_depreciation': metrics.get('accumulated_depreciation'),

                # Phase 2: Retail/E-Commerce Industry Indicators (3)
                'sga_expense': metrics.get('sga_expense'),
                'rd_expense': metrics.get('rd_expense'),
                'operating_expense': metrics.get('operating_expense'),

                # Phase 2: Financial Industry Indicators (5)
                'interest_income': metrics.get('interest_income'),
                'interest_expense': metrics.get('interest_expense'),
                'loan_portfolio': metrics.get('loan_portfolio'),
                'npl_amount': metrics.get('npl_amount'),
                'nim': metrics.get('nim'),

                # Phase 2: Common Indicators (4)
                'investing_cf': metrics.get('investing_cf'),
                'financing_cf': metrics.get('financing_cf'),
                'ebitda': metrics.get('ebitda'),
                'ebitda_margin': metrics.get('ebitda_margin'),

                # Phase 3: Equity Account Breakdown (8 columns)
                'capital_stock': metrics.get('capital_stock'),
                'capital_surplus': metrics.get('capital_surplus'),
                'retained_earnings': metrics.get('retained_earnings'),
                'treasury_stock': metrics.get('treasury_stock'),
                'other_comprehensive_income': metrics.get('other_comprehensive_income'),
                'non_controlling_interest': metrics.get('non_controlling_interest'),
                'unappropriated_retained_earnings': metrics.get('unappropriated_retained_earnings'),
                'legal_reserve': metrics.get('legal_reserve'),

                # Phase 3: Equity Validation (2 columns)
                'equity_validation_passed': metrics.get('equity_validation_passed'),
                'equity_validation_error_pct': metrics.get('equity_validation_error_pct')
            }

            # UPSERT query (Phase 2: 36 existing + 18 new + Phase 3: 10 equity columns = 64 columns)
            query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type,
                shares_outstanding, market_cap, close_price,
                per, pbr, psr,
                total_assets, total_liabilities, total_equity,
                revenue, operating_profit, net_income,
                current_assets, current_liabilities, inventory,
                cogs, gross_profit, pp_e, depreciation, accounts_receivable, accumulated_depreciation,
                sga_expense, rd_expense, operating_expense,
                interest_income, interest_expense, loan_portfolio, npl_amount, nim,
                investing_cf, financing_cf, ebitda, ebitda_margin,
                capital_stock, capital_surplus, retained_earnings, treasury_stock,
                other_comprehensive_income, non_controlling_interest,
                unappropriated_retained_earnings, legal_reserve,
                equity_validation_passed, equity_validation_error_pct,
                fiscal_year,
                data_source, created_at
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s,
                %s,
                %s, NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                shares_outstanding = EXCLUDED.shares_outstanding,
                market_cap = EXCLUDED.market_cap,
                close_price = EXCLUDED.close_price,
                per = EXCLUDED.per,
                pbr = EXCLUDED.pbr,
                psr = EXCLUDED.psr,
                total_assets = EXCLUDED.total_assets,
                total_liabilities = EXCLUDED.total_liabilities,
                total_equity = EXCLUDED.total_equity,
                revenue = EXCLUDED.revenue,
                operating_profit = EXCLUDED.operating_profit,
                net_income = EXCLUDED.net_income,
                current_assets = EXCLUDED.current_assets,
                current_liabilities = EXCLUDED.current_liabilities,
                inventory = EXCLUDED.inventory,
                cogs = EXCLUDED.cogs,
                gross_profit = EXCLUDED.gross_profit,
                pp_e = EXCLUDED.pp_e,
                depreciation = EXCLUDED.depreciation,
                accounts_receivable = EXCLUDED.accounts_receivable,
                accumulated_depreciation = EXCLUDED.accumulated_depreciation,
                sga_expense = EXCLUDED.sga_expense,
                rd_expense = EXCLUDED.rd_expense,
                operating_expense = EXCLUDED.operating_expense,
                interest_income = EXCLUDED.interest_income,
                interest_expense = EXCLUDED.interest_expense,
                loan_portfolio = EXCLUDED.loan_portfolio,
                npl_amount = EXCLUDED.npl_amount,
                nim = EXCLUDED.nim,
                investing_cf = EXCLUDED.investing_cf,
                financing_cf = EXCLUDED.financing_cf,
                ebitda = EXCLUDED.ebitda,
                ebitda_margin = EXCLUDED.ebitda_margin,
                capital_stock = EXCLUDED.capital_stock,
                capital_surplus = EXCLUDED.capital_surplus,
                retained_earnings = EXCLUDED.retained_earnings,
                treasury_stock = EXCLUDED.treasury_stock,
                other_comprehensive_income = EXCLUDED.other_comprehensive_income,
                non_controlling_interest = EXCLUDED.non_controlling_interest,
                unappropriated_retained_earnings = EXCLUDED.unappropriated_retained_earnings,
                legal_reserve = EXCLUDED.legal_reserve,
                equity_validation_passed = EXCLUDED.equity_validation_passed,
                equity_validation_error_pct = EXCLUDED.equity_validation_error_pct,
                fiscal_year = EXCLUDED.fiscal_year,
                data_source = EXCLUDED.data_source
            """

            # Convert data dict to tuple in correct order (36 existing + 18 Phase2 + 10 Phase3 = 64 columns)
            params = (
                data['ticker'], data['region'], data['date'], data['period_type'],
                data['shares_outstanding'], data['market_cap'], data['close_price'],
                data['per'], data['pbr'], data['psr'],
                data.get('total_assets'), data.get('total_liabilities'), data.get('total_equity'),
                data.get('revenue'), data.get('operating_profit'), data.get('net_income'),
                data.get('current_assets'), data.get('current_liabilities'), data.get('inventory'),
                # Phase 2: Manufacturing (6)
                data.get('cogs'), data.get('gross_profit'), data.get('pp_e'),
                data.get('depreciation'), data.get('accounts_receivable'), data.get('accumulated_depreciation'),
                # Phase 2: Retail/E-Commerce (3)
                data.get('sga_expense'), data.get('rd_expense'), data.get('operating_expense'),
                # Phase 2: Financial (5)
                data.get('interest_income'), data.get('interest_expense'), data.get('loan_portfolio'),
                data.get('npl_amount'), data.get('nim'),
                # Phase 2: Common (4)
                data.get('investing_cf'), data.get('financing_cf'), data.get('ebitda'), data.get('ebitda_margin'),
                # Phase 3: Equity Account Breakdown (8)
                data.get('capital_stock'), data.get('capital_surplus'), data.get('retained_earnings'), data.get('treasury_stock'),
                data.get('other_comprehensive_income'), data.get('non_controlling_interest'),
                data.get('unappropriated_retained_earnings'), data.get('legal_reserve'),
                # Phase 3: Equity Validation (2)
                data.get('equity_validation_passed'), data.get('equity_validation_error_pct'),
                # Metadata
                data.get('fiscal_year'),
                data['data_source']
            )

            self.db.execute_update(query, params)

            # Determine if insert or update
            if self.db.cursor.rowcount > 0:
                if 'INSERT' in self.db.cursor.statusmessage:
                    self.stats['records_inserted'] += 1
                    logger.info(f"✅ [{ticker}] Inserted fundamental data")
                else:
                    self.stats['records_updated'] += 1
                    logger.info(f"✅ [{ticker}] Updated fundamental data")
                return True
            else:
                logger.warning(f"⚠️ [{ticker}] No rows affected")
                return False

        except Exception as e:
            logger.error(f"❌ [{ticker}] Database insert/update failed: {e}")
            return False

    def check_duplicate_exists(self, ticker: str, target_date: date, period_type: str = 'ANNUAL') -> bool:
        """
        Check if fundamental data already exists for ticker+date+period_type

        Args:
            ticker: Stock ticker (KR format)
            target_date: Date to check
            period_type: Period type (ANNUAL, Q1, Q2, Q3, Q4)

        Returns:
            True if data exists, False otherwise
        """
        try:
            query = """
            SELECT COUNT(*) as count
            FROM ticker_fundamentals
            WHERE ticker = %s
              AND region = 'KR'
              AND date = %s
              AND period_type = %s
              AND data_source = 'DART'
            """
            result = self.db.execute_query(query, (ticker, target_date, period_type))

            if result and result[0]['count'] > 0:
                logger.debug(f"🔄 [KR:{ticker}] Duplicate found for {target_date} ({period_type}), will update")
                return True
            return False

        except Exception as e:
            logger.error(f"❌ [KR:{ticker}] Duplicate check failed: {e}")
            return False

    def process_ticker(self, ticker_info: Dict, start_year: int, end_year: int) -> bool:
        """
        Process single ticker: fetch DART historical data, calculate ratios, insert to database

        Args:
            ticker_info: Dict with ticker, name, corp_code
            start_year: Start year for historical data
            end_year: End year for historical data

        Returns:
            True if at least one year was successfully processed, False otherwise
        """
        ticker = ticker_info['ticker']
        name = ticker_info.get('name', 'Unknown')
        corp_code = ticker_info.get('corp_code')

        logger.info(f"{'='*60}")
        logger.info(f"Processing {ticker} ({name}) - Years {start_year}-{end_year}")
        logger.info(f"{'='*60}")

        # Validate corp_code
        if not corp_code:
            logger.warning(f"⚠️ [{ticker}] No corp_code available - skipping")
            self.stats['tickers_skipped_no_corp_code'] += 1
            return False

        # Step 1: Fetch DART historical fundamental data (multiple years)
        metrics_list = self.fetch_dart_historical_fundamentals(ticker, corp_code, start_year, end_year)
        if not metrics_list:
            self.stats['tickers_skipped_no_data'] += 1
            return False

        # Process each year's data
        years_processed = 0
        for metrics in metrics_list:
            fiscal_year = metrics.get('fiscal_year', 'Unknown')
            target_date = metrics.get('date')
            period_type = metrics.get('period_type', 'ANNUAL')

            logger.info(f"\n📅 [{ticker}] Processing fiscal year {fiscal_year}...")

            # Check for duplicates (will still update if exists via UPSERT)
            if target_date and self.check_duplicate_exists(ticker, target_date, period_type):
                logger.info(f"🔄 [KR:{ticker}] Data exists for {target_date} ({period_type}), will update")

            # Step 2: Get historical price (as of report date)
            price = self.get_latest_price(ticker, as_of_date=target_date)
            if not price:
                logger.warning(f"⚠️ [{ticker}] No price data for {target_date} - skipping year {fiscal_year}")
                continue

            # Step 3: Calculate valuation ratios
            ratios = self.calculate_valuation_ratios(ticker, metrics, price)

            # Step 4: Insert/update database
            success = self.insert_or_update_fundamental_data(ticker, metrics, ratios, price)

            if success:
                years_processed += 1
                self.stats['records_processed'] += 1
                logger.info(f"✅ [{ticker}] Year {fiscal_year} processed successfully")
            else:
                logger.warning(f"⚠️ [{ticker}] Year {fiscal_year} failed to insert/update")

        # Mark ticker as successful if at least one year was processed
        if years_processed > 0:
            self.stats['tickers_success'] += 1
            logger.info(f"✅ [{ticker}] Completed: {years_processed}/{len(metrics_list)} years processed")
            return True
        else:
            self.stats['tickers_failed'] += 1
            logger.warning(f"❌ [{ticker}] Failed: No years successfully processed")
            return False

    def run_backfill(self, incremental: bool = False, limit: Optional[int] = None,
                     ticker_file: Optional[str] = None) -> Dict:
        """
        Run full backfill process

        Args:
            incremental: If True, only fetch missing data
            limit: Maximum tickers to process (for testing)
            ticker_file: CSV file with ticker list

        Returns:
            Statistics dict
        """
        start_time = datetime.now()
        logger.info("="*80)
        logger.info("PHASE 1: DART FUNDAMENTAL DATA BACKFILL - TOP 100 LIQUID TICKERS")
        logger.info("="*80)
        logger.info(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Mode: {'TICKER FILE' if ticker_file else ('INCREMENTAL' if incremental else 'FULL BACKFILL')}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info(f"Rate Limit: {self.rate_limit_delay} sec/request")
        if ticker_file:
            logger.info(f"Ticker File: {ticker_file}")
        if limit:
            logger.info(f"Limit: {limit} tickers")
        logger.info("="*80)

        # Get tickers for backfill
        tickers = self.get_kr_tickers_for_backfill(incremental=incremental, limit=limit,
                                                    ticker_file=ticker_file)

        if not tickers:
            logger.warning("⚠️ No tickers to process")
            return self.stats

        logger.info(f"\n📊 Processing {len(tickers)} tickers...")

        # Checkpoint system: Save progress every 100 tickers
        checkpoint_interval = 100
        checkpoint_file = f"log/backfill_checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        # Process each ticker
        for idx, ticker_info in enumerate(tickers, 1):
            ticker = ticker_info['ticker']
            self.stats['tickers_processed'] += 1

            logger.info(f"\n[{idx}/{len(tickers)}] Processing {ticker}...")

            try:
                self.process_ticker(ticker_info, self.start_year, self.end_year)

            except Exception as e:
                import traceback
                logger.error(f"❌ [{ticker}] Unexpected error: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                self.stats['tickers_failed'] += 1
                continue

            # Checkpoint: Save progress every N tickers
            if idx % checkpoint_interval == 0:
                self._save_checkpoint(checkpoint_file, idx, tickers)

        # Final statistics
        end_time = datetime.now()
        duration = end_time - start_time

        logger.info("\n" + "="*80)
        logger.info("BACKFILL COMPLETED")
        logger.info("="*80)
        logger.info(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Duration: {duration}")
        logger.info(f"Year Range: {self.start_year}-{self.end_year} ({self.end_year - self.start_year + 1} years)")
        logger.info(f"\nStatistics:")
        logger.info(f"  Tickers Processed: {self.stats['tickers_processed']}")
        logger.info(f"  ✅ Success: {self.stats['tickers_success']}")
        logger.info(f"  ⚠️ Skipped (No Corp Code): {self.stats['tickers_skipped_no_corp_code']}")
        logger.info(f"  ⚠️ Skipped (No Data): {self.stats['tickers_skipped_no_data']}")
        logger.info(f"  📅 Skipped (Listing Date): {self.stats['tickers_skipped_listing_date']}")
        logger.info(f"  ❌ Failed: {self.stats['tickers_failed']}")
        logger.info(f"\nDatabase Operations:")
        logger.info(f"  Year Records Processed: {self.stats['records_processed']} (across all tickers)")
        logger.info(f"  Records Inserted: {self.stats['records_inserted']}")
        logger.info(f"  Records Updated: {self.stats['records_updated']}")
        avg_years = self.stats['records_processed'] / max(self.stats['tickers_success'], 1)
        logger.info(f"  Avg Years per Ticker: {avg_years:.2f}")
        logger.info(f"\nAPI Metrics:")
        logger.info(f"  Total API Calls: {self.stats['api_calls']}")
        logger.info(f"  Avg Time per Call: {duration.total_seconds() / max(self.stats['api_calls'], 1):.2f} sec")
        logger.info("="*80)

        # Calculate coverage
        self._print_coverage_report()

        return self.stats

    def _save_checkpoint(self, checkpoint_file: str, current_idx: int, tickers: List[Dict]):
        """Save progress checkpoint"""
        try:
            checkpoint_data = {
                'timestamp': datetime.now().isoformat(),
                'current_index': current_idx,
                'total_tickers': len(tickers),
                'stats': self.stats
            }

            with open(checkpoint_file, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)

            logger.info(f"💾 Checkpoint saved: {current_idx}/{len(tickers)} tickers processed")

        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")

    def _print_coverage_report(self):
        """Print data coverage report"""
        try:
            query = """
            SELECT
                COUNT(DISTINCT ticker) as tickers_with_data,
                (SELECT COUNT(*) FROM tickers WHERE region = 'KR' AND asset_type = 'STOCK' AND is_active = TRUE) as total_tickers,
                ROUND(COUNT(DISTINCT ticker)::numeric /
                      (SELECT COUNT(*) FROM tickers WHERE region = 'KR' AND asset_type = 'STOCK' AND is_active = TRUE) * 100, 2) as coverage_pct
            FROM ticker_fundamentals
            WHERE region = 'KR' AND date >= NOW() - INTERVAL '90 days'
            """

            result = self.db.execute_query(query)

            if result:
                row = result[0]
                logger.info(f"\n📊 KR Market Coverage:")
                logger.info(f"  Tickers with Data: {row['tickers_with_data']}")
                logger.info(f"  Total Tickers: {row['total_tickers']}")
                logger.info(f"  Coverage: {row['coverage_pct']}%")

                target_coverage = 80.0
                if row['coverage_pct'] >= target_coverage:
                    logger.info(f"  ✅ Target coverage (>{target_coverage}%) ACHIEVED")
                else:
                    logger.info(f"  ⚠️ Target coverage (>{target_coverage}%) NOT YET ACHIEVED")
                    logger.info(f"  → Need {int(row['total_tickers'] * target_coverage / 100) - row['tickers_with_data']} more tickers")

        except Exception as e:
            logger.error(f"Failed to generate coverage report: {e}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='DART Fundamental Data Backfill (Phase 2 - Annual Data)')
    parser.add_argument('--dry-run', action='store_true', help='Preview operations without database writes')
    parser.add_argument('--incremental', action='store_true', help='Only fetch missing data (last 90 days)')
    parser.add_argument('--limit', type=int, help='Limit number of tickers (for testing)')
    parser.add_argument('--ticker-file', type=str, help='CSV file with ticker list (ticker,name,volume_rank columns)')
    parser.add_argument('--rate-limit', type=float, default=1.0, help='Delay between API calls in seconds (default: 1.0)')
    parser.add_argument('--start-year', type=int, default=2022, help='Start year for historical data (default: 2022)')
    parser.add_argument('--end-year', type=int, default=2024, help='End year for historical data (default: 2024)')

    # Gap Analysis Options (Phase 3)
    parser.add_argument(
        '--use-gap-analysis',
        action='store_true',
        help='Use gap analysis for optimized backfill (recommended for incremental updates)'
    )
    parser.add_argument(
        '--target-columns',
        nargs='+',
        default=['capital_stock', 'capital_surplus', 'retained_earnings'],
        help='Columns to check for gaps (default: equity account columns)'
    )

    args = parser.parse_args()

    try:
        # Initialize database
        db = PostgresDatabaseManager()
        logger.info("✅ Connected to PostgreSQL database")

        # ========================================================================
        # Path Selection: Gap-Aware vs Legacy Mode
        # ========================================================================

        if args.use_gap_analysis:
            # ✅ NEW: Gap-Aware Backfill using BackfillOrchestrator
            logger.info("🔍 Gap-Aware 모드: BackfillOrchestrator 사용")

            # Initialize components
            gap_analyzer = GapAnalyzer(db)
            orchestrator = BackfillOrchestrator(
                db=db,
                gap_analyzer=gap_analyzer,
                dry_run=args.dry_run
            )

            # Execute gap-aware backfill
            result = orchestrator.execute_backfill(
                backfill_type='equity',
                target_columns=args.target_columns,
                region='KR',
                limit=args.limit,
                backfill_start_date=date(args.start_year, 1, 1)
            )

            # Print summary
            if result.success:
                summary = result.get_summary()
                logger.info("=" * 80)
                logger.info("📊 Gap-Aware Backfill 완료 요약:")
                logger.info(f"  Gap Analysis:")
                for key, value in summary['gap_analysis'].items():
                    logger.info(f"    - {key}: {value}")
                logger.info(f"  Backfill Stats:")
                for key, value in summary['backfill_stats'].items():
                    logger.info(f"    - {key}: {value}")
                logger.info("=" * 80)

                # Exit code based on success
                sys.exit(0)
            else:
                logger.error(f"❌ Gap-Aware Backfill 실패: {result.error_message}")
                sys.exit(1)

        else:
            # ✅ LEGACY: Original DARTFundamentalBackfiller (Backward Compatibility)
            logger.info("📦 Legacy 모드: DARTFundamentalBackfiller 사용")

            # Initialize DART API client
            dart = DARTApiClient(rate_limit_delay=args.rate_limit * 36.0)  # Convert to 36-sec delay
            logger.info("✅ DART API client initialized")

            # Run backfill
            backfiller = DARTFundamentalBackfiller(
                db=db,
                dart=dart,
                dry_run=args.dry_run,
                rate_limit_delay=args.rate_limit,
                start_year=args.start_year,
                end_year=args.end_year
            )

            stats = backfiller.run_backfill(
                incremental=args.incremental,
                limit=args.limit,
                ticker_file=args.ticker_file
            )

            # Exit code based on success rate
            success_rate = stats['tickers_success'] / max(stats['tickers_processed'], 1) * 100
            if success_rate >= 70:
                logger.info(f"✅ Backfill completed successfully (success rate: {success_rate:.1f}%)")
                sys.exit(0)
            else:
                logger.warning(f"⚠️ Backfill completed with low success rate: {success_rate:.1f}%")
                sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\n⚠️ Backfill interrupted by user")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
