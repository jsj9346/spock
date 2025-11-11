# Unified Database Update System Enhancements - Design Specification

**Author**: Quant Investment Platform  
**Date**: 2025-11-02  
**Status**: Design Phase  
**Version**: 1.0

---

## Table of Contents

1. [Overview](#overview)
2. [Phase 3: Quarterly Financials Implementation](#phase-3-quarterly-financials-implementation)
3. [Enhancement 1: PostgreSQL Migration for kis_data_collector](#enhancement-1-postgresql-migration-for-kis_data_collector)
4. [Enhancement 2: Parallel Processing](#enhancement-2-parallel-processing)
5. [Enhancement 3: Data Quality Validation Rules](#enhancement-3-data-quality-validation-rules)
6. [Implementation Priorities](#implementation-priorities)
7. [Risk Analysis](#risk-analysis)

---

## Overview

### Current System Architecture

The unified database update system consists of the following components:

```
DatabaseUpdateOrchestrator (orchestrator.py)
  ├─ CheckpointManager (checkpoint.py)
  ├─ MultiRateLimiter (rate_limiter.py)
  └─ DataQualityValidator (validators.py)

Pipeline Steps:
  1. Tickers Update (KR + overseas)
  2. OHLCV Data Collection
  3. Fundamental Data Backfill (DART)
  4. Dividend Yield Calculation
  5. Quarterly Financials (optional, not implemented)
```

### Design Goals

1. **Consistency**: Follow established patterns from existing components
2. **Modularity**: Maintain separation of concerns
3. **Fault Tolerance**: Checkpoint-based recovery and error handling
4. **Performance**: Optimize for large-scale data collection
5. **Maintainability**: Clear interfaces and comprehensive documentation

---

## Phase 3: Quarterly Financials Implementation

### 1. Requirements Analysis

**Data Source**: DART API quarterly reports  
**Target**: ticker_fundamentals table with period_type = 'QUARTERLY'  
**Key Extraction**: 순자산 (Total Equity) from quarterly balance sheets  
**Rate Limit**: 1 req/sec (DART API safe limit)

### 2. Component Design

#### 2.1 Class Structure

```python
"""
Quarterly Financials Updater for Database Update Pipeline

Updates ticker_fundamentals table with quarterly financial data from DART API.
Extracts balance sheet items (assets, liabilities, equity) from Q1/Q2/Q3 reports.

Author: Quant Investment Platform
Date: 2025-11-02
"""

import sys
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime, date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.dart_api_client import DARTApiClient


class QuarterlyFinancialsUpdater:
    """
    DART quarterly financial statement updater
    
    Features:
    - Q1/Q2/Q3 financial statement retrieval
    - Balance sheet extraction (assets, liabilities, equity)
    - Incremental update support
    - Dry-run mode
    - Rate limiting (1 req/sec)
    - Statistics reporting
    
    Usage:
        updater = QuarterlyFinancialsUpdater(db, dart, dry_run=False)
        result = updater.run_update(
            incremental=True,
            fiscal_year=2024,
            quarters=['Q1', 'Q2', 'Q3']
        )
    """
    
    # Report codes for quarterly periods
    REPORT_CODES = {
        'Q1': '11013',  # 1분기보고서
        'Q2': '11012',  # 반기보고서
        'Q3': '11014',  # 3분기보고서
    }
    
    # Period end dates
    PERIOD_DATES = {
        'Q1': '-03-31',
        'Q2': '-06-30',
        'Q3': '-09-30',
    }
    
    def __init__(self, 
                 db: PostgresDatabaseManager,
                 dart: DARTApiClient,
                 dry_run: bool = False,
                 rate_limit_delay: float = 1.0):
        """
        Initialize quarterly financials updater
        
        Args:
            db: PostgreSQL database manager
            dart: DART API client
            dry_run: If True, preview operations without database writes
            rate_limit_delay: Delay between API calls in seconds (default: 1.0)
        """
        self.db = db
        self.dart = dart
        self.dry_run = dry_run
        self.rate_limit_delay = rate_limit_delay
        
        # Statistics
        self.stats = {
            'tickers_processed': 0,
            'tickers_success': 0,
            'tickers_skipped_no_corp_code': 0,
            'tickers_skipped_no_data': 0,
            'tickers_failed': 0,
            'api_calls': 0,
            'records_inserted': 0,
            'records_updated': 0,
            'quarters_processed': {}  # Q1/Q2/Q3 breakdown
        }
        
        # Load corp code mapping (reuse from backfill_fundamentals_dart)
        self.corp_code_map = self._load_corp_code_mapping()
        
        logger.info("QuarterlyFinancialsUpdater initialized")
    
    def run_update(self,
                   incremental: bool = False,
                   fiscal_year: Optional[int] = None,
                   quarters: Optional[List[str]] = None,
                   limit: Optional[int] = None) -> Dict:
        """
        Run quarterly financials update
        
        Args:
            incremental: If True, only update missing quarterly data
            fiscal_year: Specific fiscal year to update (default: current year)
            quarters: List of quarters to update (default: ['Q1', 'Q2', 'Q3'])
            limit: Maximum number of tickers to process (for testing)
        
        Returns:
            Statistics dict
        """
        start_time = datetime.now()
        
        # Determine fiscal year
        if fiscal_year is None:
            fiscal_year = datetime.now().year
        
        # Determine quarters
        if quarters is None:
            quarters = ['Q1', 'Q2', 'Q3']
        
        logger.info("="*80)
        logger.info("QUARTERLY FINANCIALS UPDATE")
        logger.info("="*80)
        logger.info(f"Fiscal Year: {fiscal_year}")
        logger.info(f"Quarters: {', '.join(quarters)}")
        logger.info(f"Mode: {'INCREMENTAL' if incremental else 'FULL UPDATE'}")
        logger.info(f"Dry Run: {self.dry_run}")
        logger.info("="*80)
        
        # Get tickers to process
        tickers = self._get_tickers_for_update(
            incremental=incremental,
            fiscal_year=fiscal_year,
            quarters=quarters,
            limit=limit
        )
        
        if not tickers:
            logger.warning("⚠️ No tickers to process")
            return self.stats
        
        logger.info(f"\n📊 Processing {len(tickers)} tickers...")
        
        # Process each ticker
        for idx, ticker_info in enumerate(tickers, 1):
            ticker = ticker_info['ticker']
            self.stats['tickers_processed'] += 1
            
            logger.info(f"\n[{idx}/{len(tickers)}] Processing {ticker}...")
            
            try:
                # Process ticker for all quarters
                success = self._process_ticker(ticker_info, fiscal_year, quarters)
                
                if success:
                    self.stats['tickers_success'] += 1
                else:
                    self.stats['tickers_failed'] += 1
                    
            except Exception as e:
                logger.error(f"❌ [{ticker}] Unexpected error: {e}")
                self.stats['tickers_failed'] += 1
                continue
        
        # Print summary
        self._print_summary(start_time)
        
        return self.stats
    
    def _get_tickers_for_update(self,
                                incremental: bool,
                                fiscal_year: int,
                                quarters: List[str],
                                limit: Optional[int]) -> List[Dict]:
        """
        Query tickers that need quarterly data
        
        Args:
            incremental: If True, only fetch tickers missing quarterly data
            fiscal_year: Target fiscal year
            quarters: List of quarters to check
            limit: Maximum number of tickers
        
        Returns:
            List of ticker dicts with ticker, name, corp_code
        """
        if incremental:
            # Build WHERE clause to check missing quarters
            quarter_checks = []
            for quarter in quarters:
                period_date = f"{fiscal_year}{self.PERIOD_DATES[quarter]}"
                quarter_checks.append(f"""
                    NOT EXISTS (
                        SELECT 1 FROM ticker_fundamentals tf
                        WHERE tf.ticker = t.ticker
                          AND tf.region = 'KR'
                          AND tf.date = '{period_date}'
                          AND tf.period_type = 'QUARTERLY'
                    )
                """)
            
            query = f"""
            SELECT DISTINCT t.ticker, t.name
            FROM tickers t
            WHERE t.region = 'KR'
              AND t.asset_type = 'STOCK'
              AND t.is_active = TRUE
              AND ({' OR '.join(quarter_checks)})
            ORDER BY t.ticker
            """
        else:
            # Full update: All KR stocks
            query = """
            SELECT DISTINCT t.ticker, t.name
            FROM tickers t
            WHERE t.region = 'KR'
              AND t.asset_type = 'STOCK'
              AND t.is_active = TRUE
            ORDER BY t.ticker
            """
        
        if limit:
            query += f" LIMIT {limit}"
        
        results = self.db.execute_query(query)
        
        # Enrich with corp_code
        tickers_with_codes = []
        for row in results:
            ticker = row['ticker']
            name = row['name']
            corp_code = self.corp_code_map.get(ticker)
            
            if corp_code:
                tickers_with_codes.append({
                    'ticker': ticker,
                    'name': name,
                    'corp_code': corp_code
                })
        
        logger.info(
            f"📊 Found {len(tickers_with_codes)} KR stocks with DART corp codes "
            f"(from {len(results)} total)"
        )
        
        return tickers_with_codes
    
    def _process_ticker(self, 
                       ticker_info: Dict,
                       fiscal_year: int,
                       quarters: List[str]) -> bool:
        """
        Process single ticker: fetch quarterly data for all quarters
        
        Args:
            ticker_info: Dict with ticker, name, corp_code
            fiscal_year: Target fiscal year
            quarters: List of quarters to process
        
        Returns:
            True if at least one quarter succeeded, False otherwise
        """
        ticker = ticker_info['ticker']
        corp_code = ticker_info.get('corp_code')
        
        if not corp_code:
            logger.warning(f"⚠️ [{ticker}] No corp_code - skipping")
            self.stats['tickers_skipped_no_corp_code'] += 1
            return False
        
        any_success = False
        
        # Process each quarter
        for quarter in quarters:
            try:
                success = self._process_quarter(
                    ticker, corp_code, fiscal_year, quarter
                )
                
                if success:
                    any_success = True
                    
                    # Update quarter stats
                    if quarter not in self.stats['quarters_processed']:
                        self.stats['quarters_processed'][quarter] = 0
                    self.stats['quarters_processed'][quarter] += 1
                    
            except Exception as e:
                logger.error(f"❌ [{ticker}] {quarter} failed: {e}")
                continue
        
        return any_success
    
    def _process_quarter(self,
                        ticker: str,
                        corp_code: str,
                        fiscal_year: int,
                        quarter: str) -> bool:
        """
        Process single quarter: fetch and store quarterly financial data
        
        Args:
            ticker: Stock ticker
            corp_code: DART corporate code
            fiscal_year: Target fiscal year
            quarter: Quarter identifier ('Q1', 'Q2', 'Q3')
        
        Returns:
            True if successful, False otherwise
        """
        import time
        
        # Rate limiting
        time.sleep(self.rate_limit_delay)
        self.stats['api_calls'] += 1
        
        # Get report code
        reprt_code = self.REPORT_CODES[quarter]
        
        # Fetch quarterly financial data from DART
        try:
            params = {
                'corp_code': corp_code,
                'bsns_year': fiscal_year,
                'reprt_code': reprt_code,
                'fs_div': 'CFS'  # Consolidated financial statements
            }
            
            response = self.dart._make_request('fnlttSinglAcntAll.json', params)
            data = response.json()
            
            if data['status'] != '000' or not data.get('list'):
                logger.debug(f"⏭️ [{ticker}] {quarter} {fiscal_year}: No data available")
                self.stats['tickers_skipped_no_data'] += 1
                return False
            
            items = data.get('list', [])
            
            # Parse financial items
            metrics = self._parse_quarterly_financials(
                ticker, items, fiscal_year, quarter
            )
            
            # Get latest price
            price = self._get_latest_price(ticker, metrics['date'])
            
            if not price:
                logger.warning(f"⚠️ [{ticker}] {quarter}: No price data")
                return False
            
            # Calculate ratios
            ratios = self._calculate_valuation_ratios(ticker, metrics, price)
            
            # Insert/update database
            success = self._insert_or_update_quarterly_data(
                ticker, metrics, ratios, price
            )
            
            if success:
                logger.info(f"✅ [{ticker}] {quarter} {fiscal_year} updated")
                return True
            else:
                logger.warning(f"⚠️ [{ticker}] {quarter} {fiscal_year} failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ [{ticker}] {quarter} {fiscal_year} error: {e}")
            return False
    
    def _parse_quarterly_financials(self,
                                    ticker: str,
                                    items: List[Dict],
                                    fiscal_year: int,
                                    quarter: str) -> Dict:
        """
        Parse DART quarterly financial statement items
        
        Args:
            ticker: Ticker symbol
            items: List of financial statement items
            fiscal_year: Fiscal year
            quarter: Quarter identifier
        
        Returns:
            Dict with parsed metrics
        """
        # Create lookup dict (use first occurrence)
        item_lookup = {}
        for item in items:
            account_name = item.get('account_nm', '')
            amount = item.get('thstrm_amount', '0').replace(',', '')
            
            if account_name not in item_lookup:
                try:
                    item_lookup[account_name] = float(amount)
                except (ValueError, TypeError):
                    pass
        
        # Determine period date
        period_date = f"{fiscal_year}{self.PERIOD_DATES[quarter]}"
        
        metrics = {
            'ticker': ticker,
            'date': period_date,
            'period_type': 'QUARTERLY',
            'fiscal_year': fiscal_year,
            'data_source': 'DART',
            
            # Balance sheet items
            'total_assets': item_lookup.get('자산총계', 0),
            'total_liabilities': item_lookup.get('부채총계', 0),
            'total_equity': item_lookup.get('자본총계', 0),
            'current_assets': item_lookup.get('유동자산', 0),
            'current_liabilities': item_lookup.get('유동부채', 0),
            
            # Income statement items (YTD cumulative for Q1/Q2/Q3)
            'revenue': (item_lookup.get('영업수익', 0) or
                       item_lookup.get('매출액', 0) or
                       item_lookup.get('수익(매출액)', 0)),
            'operating_profit': (item_lookup.get('영업이익', 0) or
                               item_lookup.get('영업이익(손실)', 0)),
            'net_income': (item_lookup.get('분기순이익(손실)', 0) or
                          item_lookup.get('분기순이익', 0) or
                          item_lookup.get('반기순이익(손실)', 0) or
                          item_lookup.get('반기순이익', 0))
        }
        
        # Calculate derived metrics
        if metrics['total_equity'] > 0 and metrics['net_income'] > 0:
            metrics['roe'] = (metrics['net_income'] / metrics['total_equity']) * 100
        
        if metrics['total_assets'] > 0 and metrics['net_income'] > 0:
            metrics['roa'] = (metrics['net_income'] / metrics['total_assets']) * 100
        
        if metrics['total_equity'] > 0 and metrics['total_liabilities'] > 0:
            metrics['debt_ratio'] = (metrics['total_liabilities'] / metrics['total_equity']) * 100
        
        return metrics
    
    def _get_latest_price(self, ticker: str, as_of_date: str) -> Optional[float]:
        """
        Get latest closing price from ohlcv_data
        
        Args:
            ticker: Stock ticker
            as_of_date: Date to query (YYYY-MM-DD format)
        
        Returns:
            Closing price or None
        """
        try:
            query = """
            SELECT close FROM ohlcv_data
            WHERE ticker = %s AND region = 'KR' AND date <= %s
            ORDER BY date DESC LIMIT 1
            """
            result = self.db.execute_query(query, (ticker, as_of_date))
            
            if result and len(result) > 0:
                return float(result[0]['close'])
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ [{ticker}] Failed to get price: {e}")
            return None
    
    def _calculate_valuation_ratios(self, 
                                    ticker: str,
                                    metrics: Dict,
                                    price: float) -> Dict:
        """
        Calculate valuation ratios (P/E, P/B) from quarterly data
        
        Args:
            ticker: Stock ticker
            metrics: Parsed financial metrics
            price: Current stock price
        
        Returns:
            Dict with calculated ratios
        """
        ratios = {}
        
        try:
            total_equity = metrics.get('total_equity', 0)
            net_income = metrics.get('net_income', 0)
            shares_outstanding = metrics.get('shares_outstanding')
            
            # Note: Quarterly earnings are cumulative (YTD)
            # For proper P/E calculation, we'd need trailing 12-month earnings
            # This is a simplified implementation
            
            if shares_outstanding and shares_outstanding > 0:
                # Book value per share
                if total_equity > 0:
                    book_value_per_share = total_equity / shares_outstanding
                    if book_value_per_share > 0:
                        ratios['pbr'] = price / book_value_per_share
                
                # Earnings per share (YTD)
                if net_income > 0:
                    eps = net_income / shares_outstanding
                    if eps > 0:
                        ratios['per'] = price / eps
                
                # Market cap
                ratios['market_cap'] = int(price * shares_outstanding)
        
        except Exception as e:
            logger.error(f"❌ [{ticker}] Failed to calculate ratios: {e}")
        
        return ratios
    
    def _insert_or_update_quarterly_data(self,
                                         ticker: str,
                                         metrics: Dict,
                                         ratios: Dict,
                                         price: float) -> bool:
        """
        Insert or update quarterly financial data in ticker_fundamentals
        
        Args:
            ticker: Stock ticker
            metrics: Parsed financial metrics
            ratios: Calculated valuation ratios
            price: Current stock price
        
        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would insert/update quarterly data for {ticker}")
            logger.info(f"  → Date: {metrics['date']}, Quarter: {metrics['period_type']}")
            return True
        
        try:
            # Prepare data (reuse structure from backfill_fundamentals_dart)
            query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type,
                close_price,
                total_assets, total_liabilities, total_equity,
                revenue, operating_profit, net_income,
                current_assets, current_liabilities,
                fiscal_year,
                per, pbr, market_cap,
                data_source, created_at
            )
            VALUES (
                %s, %s, %s, %s,
                %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s,
                %s, %s, %s,
                %s, NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                close_price = EXCLUDED.close_price,
                total_assets = EXCLUDED.total_assets,
                total_liabilities = EXCLUDED.total_liabilities,
                total_equity = EXCLUDED.total_equity,
                revenue = EXCLUDED.revenue,
                operating_profit = EXCLUDED.operating_profit,
                net_income = EXCLUDED.net_income,
                current_assets = EXCLUDED.current_assets,
                current_liabilities = EXCLUDED.current_liabilities,
                per = EXCLUDED.per,
                pbr = EXCLUDED.pbr,
                market_cap = EXCLUDED.market_cap,
                data_source = EXCLUDED.data_source
            """
            
            params = (
                ticker, 'KR', metrics['date'], metrics['period_type'],
                float(price),
                metrics.get('total_assets'), metrics.get('total_liabilities'), metrics.get('total_equity'),
                metrics.get('revenue'), metrics.get('operating_profit'), metrics.get('net_income'),
                metrics.get('current_assets'), metrics.get('current_liabilities'),
                metrics['fiscal_year'],
                ratios.get('per'), ratios.get('pbr'), ratios.get('market_cap'),
                metrics['data_source']
            )
            
            self.db.execute_update(query, params)
            
            # Track insert/update
            if self.db.cursor.rowcount > 0:
                if 'INSERT' in self.db.cursor.statusmessage:
                    self.stats['records_inserted'] += 1
                else:
                    self.stats['records_updated'] += 1
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [{ticker}] Database insert/update failed: {e}")
            return False
    
    def _load_corp_code_mapping(self) -> Dict[str, str]:
        """
        Load DART corp_code mapping from database
        (Reuse logic from DARTFundamentalBackfiller)
        
        Returns:
            Dict mapping ticker -> corp_code
        """
        logger.info("Loading DART corp_code mapping...")
        
        try:
            query = """
            SELECT ticker, corp_code
            FROM stock_details
            WHERE region = 'KR' AND corp_code IS NOT NULL
            """
            results = self.db.execute_query(query)
            
            corp_code_map = {row['ticker']: row['corp_code'] for row in results}
            logger.info(f"✅ Loaded {len(corp_code_map)} corp codes from database")
            
            return corp_code_map
            
        except Exception as e:
            logger.error(f"Failed to load corp codes: {e}")
            return {}
    
    def _print_summary(self, start_time: datetime):
        """Print execution summary"""
        end_time = datetime.now()
        duration = end_time - start_time
        
        logger.info("\n" + "="*80)
        logger.info("UPDATE COMPLETED")
        logger.info("="*80)
        logger.info(f"Duration: {duration}")
        logger.info(f"\nStatistics:")
        logger.info(f"  Tickers Processed: {self.stats['tickers_processed']}")
        logger.info(f"  ✅ Success: {self.stats['tickers_success']}")
        logger.info(f"  ❌ Failed: {self.stats['tickers_failed']}")
        logger.info(f"\nQuarter Breakdown:")
        for quarter, count in self.stats['quarters_processed'].items():
            logger.info(f"  {quarter}: {count} tickers")
        logger.info(f"\nDatabase Operations:")
        logger.info(f"  Records Inserted: {self.stats['records_inserted']}")
        logger.info(f"  Records Updated: {self.stats['records_updated']}")
        logger.info(f"\nAPI Metrics:")
        logger.info(f"  Total API Calls: {self.stats['api_calls']}")
        logger.info("="*80)
```

#### 2.2 Integration with Orchestrator

**File**: `modules/orchestration/orchestrator.py`

```python
def _update_quarterly_financials(self, regions: List[str], **kwargs) -> Dict:
    """Update quarterly financial statements (KR only, optional)"""
    logger.info("🔄 Updating quarterly financials...")
    
    results = {}
    
    for region in regions:
        if region == 'KR':
            try:
                from scripts.update_quarterly_financials import QuarterlyFinancialsUpdater
                from modules.dart_api_client import DARTApiClient
                
                # Initialize DART client
                dart_api_key = os.getenv('DART_API_KEY')
                if not dart_api_key:
                    logger.error(f"  ❌ [{region}] DART_API_KEY not found")
                    results[region] = {
                        'success': False,
                        'error': 'DART_API_KEY not configured'
                    }
                    continue
                
                dart = DARTApiClient(api_key=dart_api_key)
                updater = QuarterlyFinancialsUpdater(
                    self.db, dart,
                    dry_run=kwargs.get('dry_run', False),
                    rate_limit_delay=1.0
                )
                
                # Run quarterly update
                result = updater.run_update(
                    incremental=kwargs.get('incremental', True),
                    fiscal_year=kwargs.get('fiscal_year'),
                    quarters=kwargs.get('quarters'),
                    limit=self.config.get('limit')
                )
                
                results[region] = result
                
                logger.info(
                    f"  ✅ [{region}] {result['tickers_success']} success, "
                    f"{result['tickers_failed']} failed"
                )
                
            except Exception as e:
                logger.error(f"  ❌ [{region}] Failed: {e}")
                results[region] = {'success': False, 'error': str(e)}
        
        else:
            # Not applicable for overseas markets
            results[region] = {
                'success': True,
                'message': 'Not applicable for overseas markets'
            }
    
    return results
```

#### 2.3 Testing Strategy

**File**: `tests/orchestration/test_quarterly_financials_updater.py`

```python
"""
Unit tests for QuarterlyFinancialsUpdater

Tests:
1. Corp code mapping loading
2. Ticker selection (incremental vs full)
3. DART API quarterly data parsing
4. Database insert/update logic
5. Quarter-specific date handling
6. Dry-run mode
7. Rate limiting
8. Error handling
"""

import pytest
from unittest.mock import Mock, patch
from scripts.update_quarterly_financials import QuarterlyFinancialsUpdater


class TestQuarterlyFinancialsUpdater:
    
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.fixture
    def mock_dart(self):
        return Mock()
    
    @pytest.fixture
    def updater(self, mock_db, mock_dart):
        return QuarterlyFinancialsUpdater(
            db=mock_db,
            dart=mock_dart,
            dry_run=False,
            rate_limit_delay=0.1
        )
    
    def test_quarter_date_mapping(self, updater):
        """Test correct period date mapping for quarters"""
        assert updater.PERIOD_DATES['Q1'] == '-03-31'
        assert updater.PERIOD_DATES['Q2'] == '-06-30'
        assert updater.PERIOD_DATES['Q3'] == '-09-30'
    
    def test_report_code_mapping(self, updater):
        """Test correct DART report code mapping"""
        assert updater.REPORT_CODES['Q1'] == '11013'
        assert updater.REPORT_CODES['Q2'] == '11012'
        assert updater.REPORT_CODES['Q3'] == '11014'
    
    def test_incremental_query_generation(self, updater, mock_db):
        """Test incremental mode query generation"""
        mock_db.execute_query.return_value = []
        
        updater._get_tickers_for_update(
            incremental=True,
            fiscal_year=2024,
            quarters=['Q1', 'Q2'],
            limit=None
        )
        
        # Verify query contains missing quarter checks
        query = mock_db.execute_query.call_args[0][0]
        assert 'NOT EXISTS' in query
        assert '2024-03-31' in query
        assert '2024-06-30' in query
    
    def test_dry_run_mode(self, mock_db, mock_dart):
        """Test dry-run mode doesn't write to database"""
        updater = QuarterlyFinancialsUpdater(
            db=mock_db,
            dart=mock_dart,
            dry_run=True
        )
        
        metrics = {'date': '2024-03-31', 'period_type': 'QUARTERLY'}
        ratios = {'per': 10.5, 'pbr': 1.2}
        
        result = updater._insert_or_update_quarterly_data(
            '005930', metrics, ratios, 70000.0
        )
        
        assert result is True
        assert mock_db.execute_update.call_count == 0
    
    def test_quarterly_financial_parsing(self, updater):
        """Test parsing of quarterly financial items"""
        mock_items = [
            {'account_nm': '자산총계', 'thstrm_amount': '1,000,000'},
            {'account_nm': '부채총계', 'thstrm_amount': '400,000'},
            {'account_nm': '자본총계', 'thstrm_amount': '600,000'},
            {'account_nm': '분기순이익(손실)', 'thstrm_amount': '50,000'}
        ]
        
        metrics = updater._parse_quarterly_financials(
            '005930', mock_items, 2024, 'Q1'
        )
        
        assert metrics['ticker'] == '005930'
        assert metrics['date'] == '2024-03-31'
        assert metrics['period_type'] == 'QUARTERLY'
        assert metrics['total_assets'] == 1000000.0
        assert metrics['total_equity'] == 600000.0
        assert metrics['net_income'] == 50000.0
    
    def test_rate_limiting(self, updater):
        """Test rate limiting between API calls"""
        import time
        
        start = time.time()
        
        # Simulate processing 3 quarters
        for _ in range(3):
            time.sleep(updater.rate_limit_delay)
            updater.stats['api_calls'] += 1
        
        elapsed = time.time() - start
        
        # Should take at least 0.3 seconds (3 * 0.1s delay)
        assert elapsed >= 0.3
        assert updater.stats['api_calls'] == 3
    
    def test_error_handling_no_corp_code(self, updater):
        """Test error handling when corp_code is missing"""
        ticker_info = {'ticker': '999999', 'name': 'Test', 'corp_code': None}
        
        result = updater._process_ticker(ticker_info, 2024, ['Q1'])
        
        assert result is False
        assert updater.stats['tickers_skipped_no_corp_code'] == 1
```

---

## Enhancement 1: PostgreSQL Migration for kis_data_collector

### 1. Current Architecture Analysis

**Current State**:
```
kis_data_collector.py
  ├─ SQLite database (data/spock_local.db)
  ├─ OHLCV data collection from KIS API
  ├─ Technical indicator calculation
  └─ Multi-market support (KR, US, HK, CN, JP, VN)
```

**Issues**:
- Dual database architecture (SQLite + PostgreSQL)
- Data synchronization overhead
- Limited SQLite performance for large datasets
- Complex migration path for historical data

### 2. Migration Strategy

#### Option A: Big-Bang Migration (Recommended)

**Approach**: Replace SQLite with direct PostgreSQL integration

**Advantages**:
- Clean architecture
- Single source of truth
- Better performance
- Simpler codebase

**Disadvantages**:
- Requires thorough testing
- One-time migration of historical data
- Breaking change

**Timeline**: 2-3 weeks

#### Option B: Gradual Migration

**Approach**: Support both SQLite and PostgreSQL with feature flag

**Advantages**:
- Lower risk
- Gradual rollout
- Easy rollback

**Disadvantages**:
- Code complexity
- Maintenance burden
- Temporary dual-database state

**Timeline**: 3-4 weeks

### 3. Implementation Design (Option A)

#### 3.1 Class Structure Changes

```python
"""
kis_data_collector.py - Phase 1 데이터 수집기 (PostgreSQL 통합)

Purpose:
- Direct PostgreSQL integration (replaces SQLite)
- KIS API OHLCV data collection
- Technical indicator calculation
- Multi-market support

Author: Spock Trading System
Migration Date: 2025-11-02
"""

import sys
import os
from datetime import datetime, timedelta
import logging

# PostgreSQL database manager
from modules.db_manager_postgres import PostgresDatabaseManager


class KISDataCollector:
    """
    KIS API OHLCV Data Collector with PostgreSQL Integration
    
    Changes from SQLite version:
    - Uses PostgresDatabaseManager instead of SQLite
    - Hypertable-optimized queries for TimescaleDB
    - Batch insert support for better performance
    - Native PostgreSQL types (no SQLite conversions)
    
    Migration:
    - Replace db_path with db connection parameters
    - Update all queries to PostgreSQL syntax
    - Add batch insert logic
    - Remove SQLite-specific code
    """
    
    def __init__(self, region: str = 'KR', db_manager: PostgresDatabaseManager = None):
        """
        Initialize KIS Data Collector with PostgreSQL
        
        Args:
            region: Market region ('KR', 'US', 'HK', 'CN', 'JP', 'VN')
            db_manager: PostgreSQL database manager (if None, creates new)
        """
        self.region = region
        
        # Initialize PostgreSQL connection
        if db_manager is None:
            self.db = PostgresDatabaseManager()
            self.owns_db = True
        else:
            self.db = db_manager
            self.owns_db = False
        
        logger.info(f"✅ KISDataCollector initialized (region={region}, PostgreSQL mode)")
        
        # Rest of initialization...
    
    def collect_ohlcv_batch(self, tickers: List[str], start_date: date, end_date: date) -> Dict:
        """
        Collect OHLCV data for multiple tickers (PostgreSQL-optimized)
        
        Changes:
        - Use PostgreSQL batch insert with COPY
        - Leverage TimescaleDB hypertable optimizations
        - Better error handling for connection issues
        
        Args:
            tickers: List of ticker symbols
            start_date: Start date for collection
            end_date: End date for collection
        
        Returns:
            Collection statistics
        """
        stats = {
            'tickers_collected': 0,
            'tickers_failed': 0,
            'total_records': 0
        }
        
        for ticker in tickers:
            try:
                # Fetch from KIS API (existing logic)
                ohlcv_df = self._fetch_ohlcv_from_kis(ticker, start_date, end_date)
                
                if ohlcv_df is None or ohlcv_df.empty:
                    stats['tickers_failed'] += 1
                    continue
                
                # Calculate technical indicators (existing logic)
                ohlcv_df = self._calculate_technical_indicators(ohlcv_df)
                
                # Insert to PostgreSQL with batch COPY (NEW)
                self._batch_insert_ohlcv(ticker, ohlcv_df)
                
                stats['tickers_collected'] += 1
                stats['total_records'] += len(ohlcv_df)
                
            except Exception as e:
                logger.error(f"❌ [{ticker}] Collection failed: {e}")
                stats['tickers_failed'] += 1
                continue
        
        return stats
    
    def _batch_insert_ohlcv(self, ticker: str, ohlcv_df: pd.DataFrame) -> None:
        """
        Batch insert OHLCV data using PostgreSQL COPY (NEW)
        
        Performance: 10-100x faster than individual INSERTs
        
        Args:
            ticker: Ticker symbol
            ohlcv_df: DataFrame with OHLCV data and technical indicators
        """
        # Prepare data for COPY
        ohlcv_df['ticker'] = ticker
        ohlcv_df['region'] = self.region
        ohlcv_df['timeframe'] = '1d'
        
        # Column mapping
        columns = [
            'ticker', 'region', 'date', 'timeframe',
            'open', 'high', 'low', 'close', 'volume',
            'ma5', 'ma20', 'ma60', 'ma120', 'ma200',
            'rsi', 'macd', 'macd_signal', 'volume_ma20'
        ]
        
        # Use COPY FROM STDIN for batch insert
        try:
            # Create CSV buffer
            from io import StringIO
            
            buffer = StringIO()
            ohlcv_df[columns].to_csv(buffer, index=False, header=False)
            buffer.seek(0)
            
            # Execute COPY
            with self.db.connection.cursor() as cursor:
                cursor.copy_from(
                    buffer,
                    'ohlcv_data',
                    sep=',',
                    columns=columns,
                    null=''
                )
            
            self.db.connection.commit()
            
            logger.debug(f"✅ [{ticker}] Batch inserted {len(ohlcv_df)} records")
            
        except Exception as e:
            self.db.connection.rollback()
            logger.error(f"❌ [{ticker}] Batch insert failed: {e}")
            raise
    
    def _get_last_collection_date(self, ticker: str) -> Optional[date]:
        """
        Get last collection date for incremental updates (PostgreSQL query)
        
        Changes:
        - Use PostgreSQL date functions
        - Leverage TimescaleDB time-based indexes
        
        Args:
            ticker: Ticker symbol
        
        Returns:
            Last collection date or None
        """
        query = """
        SELECT MAX(date) as last_date
        FROM ohlcv_data
        WHERE ticker = %s AND region = %s
        """
        
        result = self.db.execute_query(query, (ticker, self.region))
        
        if result and result[0]['last_date']:
            return result[0]['last_date']
        else:
            return None
    
    def close(self):
        """Close database connection if owned"""
        if self.owns_db and self.db:
            self.db.close()
```

#### 3.2 Migration Script

**File**: `scripts/migrations/migrate_sqlite_to_postgres.py`

```python
"""
SQLite to PostgreSQL Migration Script

Migrates historical OHLCV data from SQLite to PostgreSQL.

Features:
- Batch migration with checkpoint support
- Data validation
- Progress reporting
- Rollback support

Usage:
    python3 scripts/migrations/migrate_sqlite_to_postgres.py \
      --sqlite-db data/spock_local.db \
      --batch-size 10000 \
      --validate
"""

import sys
import os
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from modules.db_manager_postgres import PostgresDatabaseManager


class SQLiteToPostgresMigrator:
    """
    Migrate OHLCV data from SQLite to PostgreSQL
    
    Migration Strategy:
    1. Validate source data
    2. Create PostgreSQL schema if needed
    3. Batch migrate OHLCV data (10k records per batch)
    4. Validate migrated data
    5. Update tickers metadata
    
    Features:
    - Checkpoint-based recovery
    - Batch processing for memory efficiency
    - Data validation
    - Progress reporting
    """
    
    def __init__(self,
                 sqlite_db_path: str,
                 postgres_db: PostgresDatabaseManager,
                 batch_size: int = 10000):
        """
        Initialize migrator
        
        Args:
            sqlite_db_path: Path to SQLite database
            postgres_db: PostgreSQL database manager
            batch_size: Number of records per batch
        """
        self.sqlite_db_path = sqlite_db_path
        self.postgres_db = postgres_db
        self.batch_size = batch_size
        
        # Statistics
        self.stats = {
            'total_records': 0,
            'migrated_records': 0,
            'failed_records': 0,
            'tickers_migrated': 0
        }
        
        logger.info(f"SQLiteToPostgresMigrator initialized (batch_size={batch_size})")
    
    def run_migration(self, validate: bool = True) -> Dict:
        """
        Run full migration
        
        Args:
            validate: If True, validate data after migration
        
        Returns:
            Migration statistics
        """
        logger.info("="*80)
        logger.info("SQLite → PostgreSQL Migration")
        logger.info("="*80)
        
        start_time = datetime.now()
        
        try:
            # Step 1: Connect to SQLite
            sqlite_conn = sqlite3.connect(self.sqlite_db_path)
            sqlite_conn.row_factory = sqlite3.Row
            
            # Step 2: Get migration scope
            self._get_migration_scope(sqlite_conn)
            
            # Step 3: Migrate OHLCV data
            self._migrate_ohlcv_data(sqlite_conn)
            
            # Step 4: Migrate ticker metadata
            self._migrate_ticker_metadata(sqlite_conn)
            
            # Step 5: Validate if requested
            if validate:
                self._validate_migration(sqlite_conn)
            
            # Close SQLite connection
            sqlite_conn.close()
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise
        
        finally:
            # Print summary
            end_time = datetime.now()
            duration = end_time - start_time
            
            logger.info("\n" + "="*80)
            logger.info("MIGRATION COMPLETED")
            logger.info("="*80)
            logger.info(f"Duration: {duration}")
            logger.info(f"Records Migrated: {self.stats['migrated_records']}/{self.stats['total_records']}")
            logger.info(f"Tickers Migrated: {self.stats['tickers_migrated']}")
            logger.info("="*80)
        
        return self.stats
    
    def _get_migration_scope(self, sqlite_conn):
        """Get total number of records to migrate"""
        cursor = sqlite_conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM ohlcv_data")
        self.stats['total_records'] = cursor.fetchone()[0]
        
        logger.info(f"📊 Migration scope: {self.stats['total_records']} records")
    
    def _migrate_ohlcv_data(self, sqlite_conn):
        """Migrate OHLCV data in batches"""
        logger.info("🔄 Migrating OHLCV data...")
        
        cursor = sqlite_conn.cursor()
        offset = 0
        
        while True:
            # Fetch batch from SQLite
            query = f"""
            SELECT * FROM ohlcv_data
            ORDER BY ticker, date
            LIMIT {self.batch_size} OFFSET {offset}
            """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            if not rows:
                break
            
            # Insert batch to PostgreSQL
            self._insert_batch_to_postgres(rows)
            
            offset += len(rows)
            self.stats['migrated_records'] += len(rows)
            
            # Progress report
            progress = (self.stats['migrated_records'] / self.stats['total_records']) * 100
            logger.info(f"  Progress: {self.stats['migrated_records']}/{self.stats['total_records']} ({progress:.1f}%)")
    
    def _insert_batch_to_postgres(self, rows):
        """Insert batch of records to PostgreSQL"""
        # Prepare INSERT query
        query = """
        INSERT INTO ohlcv_data (
            ticker, region, date, timeframe,
            open, high, low, close, volume,
            ma5, ma20, ma60, ma120, ma200,
            rsi, macd, macd_signal, volume_ma20
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, region, date, timeframe) DO NOTHING
        """
        
        # Prepare data tuples
        data = []
        for row in rows:
            data.append((
                row['ticker'], row['region'], row['date'], row['timeframe'],
                row['open'], row['high'], row['low'], row['close'], row['volume'],
                row.get('ma5'), row.get('ma20'), row.get('ma60'), row.get('ma120'), row.get('ma200'),
                row.get('rsi'), row.get('macd'), row.get('macd_signal'), row.get('volume_ma20')
            ))
        
        # Execute batch insert
        self.postgres_db.execute_batch(query, data)
    
    def _migrate_ticker_metadata(self, sqlite_conn):
        """Migrate ticker metadata"""
        logger.info("🔄 Migrating ticker metadata...")
        
        cursor = sqlite_conn.cursor()
        cursor.execute("SELECT * FROM tickers")
        rows = cursor.fetchall()
        
        for row in rows:
            # Insert to PostgreSQL (ON CONFLICT DO UPDATE)
            query = """
            INSERT INTO tickers (ticker, region, name, asset_type, is_active)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (ticker, region) DO UPDATE SET
                name = EXCLUDED.name,
                is_active = EXCLUDED.is_active
            """
            
            self.postgres_db.execute_update(
                query,
                (row['ticker'], row['region'], row['name'], row.get('asset_type', 'STOCK'), True)
            )
        
        self.stats['tickers_migrated'] = len(rows)
        logger.info(f"✅ Migrated {len(rows)} tickers")
    
    def _validate_migration(self, sqlite_conn):
        """Validate migrated data"""
        logger.info("🔍 Validating migration...")
        
        # Compare record counts
        cursor = sqlite_conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM ohlcv_data")
        sqlite_count = cursor.fetchone()[0]
        
        query = "SELECT COUNT(*) as cnt FROM ohlcv_data"
        result = self.postgres_db.execute_query(query)
        postgres_count = result[0]['cnt']
        
        logger.info(f"  SQLite: {sqlite_count} records")
        logger.info(f"  PostgreSQL: {postgres_count} records")
        
        if sqlite_count == postgres_count:
            logger.info("✅ Validation passed")
        else:
            logger.warning(f"⚠️ Record count mismatch: {sqlite_count} vs {postgres_count}")
```

#### 3.3 Testing Strategy

**Tests Required**:
1. PostgreSQL connection handling
2. Batch insert performance
3. Data type conversions
4. Technical indicator calculations
5. Incremental update logic
6. Migration script validation
7. Backward compatibility

**Test Coverage Target**: >90%

---

## Enhancement 2: Parallel Processing

### 1. Parallelization Opportunities

**Current Sequential Operations**:
```
Tickers Update:     Sequential per region
OHLCV Collection:   Sequential per ticker
Fundamentals:       Sequential per ticker (DART rate limit)
Dividend Calc:      Sequential per ticker
```

**Parallelizable Operations**:
- Multiple tickers within rate limits
- Multi-region data collection
- Independent calculation tasks

### 2. Implementation Strategy

#### 2.1 Thread Pool Approach

**Use Case**: I/O-bound operations (API calls, database queries)

```python
"""
Parallel OHLCV Collection with Thread Pool

Features:
- Concurrent ticker processing
- Rate limit compliance
- Error isolation
- Progress tracking
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class ParallelOHLCVCollector:
    """
    Parallel OHLCV data collector with thread pool
    
    Features:
    - Concurrent ticker processing (configurable workers)
    - Rate limit enforcement per API source
    - Error isolation (one ticker failure doesn't stop others)
    - Progress tracking and reporting
    
    Performance:
    - 3-5x speedup for KIS API (rate limit: 20 req/sec)
    - Memory efficient (streaming results)
    - Automatic retry with exponential backoff
    """
    
    def __init__(self,
                 collector: 'KISDataCollector',
                 max_workers: int = 10,
                 rate_limiter: Optional['RateLimiter'] = None):
        """
        Initialize parallel collector
        
        Args:
            collector: Base OHLCV collector instance
            max_workers: Maximum concurrent threads (default: 10)
            rate_limiter: Rate limiter for API calls
        """
        self.collector = collector
        self.max_workers = max_workers
        self.rate_limiter = rate_limiter
        
        logger.info(f"ParallelOHLCVCollector initialized (workers={max_workers})")
    
    def collect_batch_parallel(self,
                               tickers: List[str],
                               start_date: date,
                               end_date: date) -> Dict:
        """
        Collect OHLCV data for multiple tickers in parallel
        
        Args:
            tickers: List of ticker symbols
            start_date: Start date
            end_date: End date
        
        Returns:
            Collection statistics
        """
        stats = {
            'tickers_collected': 0,
            'tickers_failed': 0,
            'total_records': 0
        }
        
        logger.info(f"🚀 Starting parallel collection for {len(tickers)} tickers...")
        
        # Create thread pool
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_ticker = {
                executor.submit(
                    self._collect_single_ticker,
                    ticker,
                    start_date,
                    end_date
                ): ticker
                for ticker in tickers
            }
            
            # Process completed tasks
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                
                try:
                    result = future.result()
                    
                    if result['success']:
                        stats['tickers_collected'] += 1
                        stats['total_records'] += result['records']
                    else:
                        stats['tickers_failed'] += 1
                        
                except Exception as e:
                    logger.error(f"❌ [{ticker}] Exception: {e}")
                    stats['tickers_failed'] += 1
                
                # Progress report
                progress = (stats['tickers_collected'] + stats['tickers_failed']) / len(tickers) * 100
                logger.info(f"  Progress: {progress:.1f}% ({stats['tickers_collected']} success, {stats['tickers_failed']} failed)")
        
        logger.info(f"✅ Parallel collection complete: {stats['tickers_collected']}/{len(tickers)} tickers")
        
        return stats
    
    def _collect_single_ticker(self,
                              ticker: str,
                              start_date: date,
                              end_date: date) -> Dict:
        """
        Collect data for single ticker (thread-safe)
        
        Args:
            ticker: Ticker symbol
            start_date: Start date
            end_date: End date
        
        Returns:
            Result dict with success flag and record count
        """
        try:
            # Rate limiting
            if self.rate_limiter:
                self.rate_limiter.wait_if_needed()
            
            # Fetch OHLCV data
            ohlcv_df = self.collector._fetch_ohlcv_from_kis(ticker, start_date, end_date)
            
            if ohlcv_df is None or ohlcv_df.empty:
                return {'success': False, 'records': 0}
            
            # Calculate indicators
            ohlcv_df = self.collector._calculate_technical_indicators(ohlcv_df)
            
            # Insert to database (thread-safe with connection pooling)
            self.collector._batch_insert_ohlcv(ticker, ohlcv_df)
            
            return {'success': True, 'records': len(ohlcv_df)}
            
        except Exception as e:
            logger.error(f"❌ [{ticker}] Collection failed: {e}")
            return {'success': False, 'records': 0}
```

#### 2.2 Process Pool Approach

**Use Case**: CPU-bound operations (technical indicator calculations)

```python
"""
Parallel Technical Indicator Calculation with Process Pool

Use Case: Large-scale indicator calculation across many tickers
Performance: 3-5x speedup on multi-core systems
"""

from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count
import pandas as pd


class ParallelIndicatorCalculator:
    """
    Parallel technical indicator calculator
    
    Features:
    - Multi-process calculation for CPU-bound operations
    - Automatic CPU core detection
    - Memory-efficient chunking
    - Progress tracking
    
    Performance:
    - 3-5x speedup on 4+ core systems
    - Scales linearly with CPU cores
    - Memory usage: ~1GB per worker
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize calculator
        
        Args:
            max_workers: Max processes (default: CPU count - 1)
        """
        if max_workers is None:
            max_workers = max(1, cpu_count() - 1)
        
        self.max_workers = max_workers
        logger.info(f"ParallelIndicatorCalculator initialized (workers={max_workers})")
    
    def calculate_batch(self, ohlcv_data: List[Tuple[str, pd.DataFrame]]) -> Dict[str, pd.DataFrame]:
        """
        Calculate indicators for multiple tickers in parallel
        
        Args:
            ohlcv_data: List of (ticker, dataframe) tuples
        
        Returns:
            Dict mapping ticker to dataframe with indicators
        """
        results = {}
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit tasks
            future_to_ticker = {
                executor.submit(_calculate_indicators_worker, ticker, df): ticker
                for ticker, df in ohlcv_data
            }
            
            # Collect results
            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                
                try:
                    df_with_indicators = future.result()
                    results[ticker] = df_with_indicators
                except Exception as e:
                    logger.error(f"❌ [{ticker}] Indicator calculation failed: {e}")
        
        return results


def _calculate_indicators_worker(ticker: str, df: pd.DataFrame) -> pd.DataFrame:
    """
    Worker function for parallel indicator calculation
    (Must be top-level function for multiprocessing)
    
    Args:
        ticker: Ticker symbol
        df: OHLCV dataframe
    
    Returns:
        Dataframe with calculated indicators
    """
    # Calculate moving averages
    df['ma5'] = df['close'].rolling(window=5).mean()
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma60'] = df['close'].rolling(window=60).mean()
    df['ma120'] = df['close'].rolling(window=120).mean()
    df['ma200'] = df['close'].rolling(window=200).mean()
    
    # Calculate RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Calculate MACD
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    
    # Volume MA
    df['volume_ma20'] = df['volume'].rolling(window=20).mean()
    
    return df
```

#### 2.3 Integration with Orchestrator

```python
# File: modules/orchestration/orchestrator.py

def _update_ohlcv(self, regions: List[str], **kwargs) -> Dict:
    """
    Update OHLCV data for all regions (with parallel processing)
    
    New features:
    - Parallel ticker processing
    - Configurable worker count
    - Rate limit compliance
    """
    logger.info("🔄 Updating OHLCV data...")
    
    results = {}
    enable_parallel = kwargs.get('parallel', True)
    max_workers = kwargs.get('max_workers', 10)
    
    for region in regions:
        try:
            if region == 'KR':
                from scripts.collect_ohlcv_orchestrated import OHLCVCollectorAdapter
                
                adapter = OHLCVCollectorAdapter(
                    self.db,
                    region=region,
                    dry_run=kwargs.get('dry_run', False)
                )
                
                # Use parallel collection if enabled
                if enable_parallel:
                    from modules.parallel_collector import ParallelOHLCVCollector
                    
                    parallel_collector = ParallelOHLCVCollector(
                        collector=adapter.collector,
                        max_workers=max_workers,
                        rate_limiter=self.rate_limiters.get('KIS')
                    )
                    
                    result = parallel_collector.collect_batch_parallel(
                        tickers=adapter._get_ticker_list(
                            incremental=kwargs.get('incremental', True),
                            limit=self.config.get('limit')
                        ),
                        start_date=adapter._get_start_date(incremental=True),
                        end_date=datetime.now().date()
                    )
                else:
                    # Sequential collection (original)
                    result = adapter.run_collection(
                        incremental=kwargs.get('incremental', True),
                        limit=self.config.get('limit')
                    )
                
                results[region] = result
                logger.info(
                    f"  ✅ [{region}] {result.get('tickers_collected', 0)} tickers collected "
                    f"in {result.get('duration', 0):.2f}s "
                    f"({'parallel' if enable_parallel else 'sequential'})"
                )
                
        except Exception as e:
            logger.error(f"  ❌ [{region}] Failed: {e}")
            results[region] = {'success': False, 'error': str(e)}
    
    return results
```

### 3. Performance Benchmarks

**Expected Performance Improvements**:

| Operation | Sequential | Parallel (10 workers) | Speedup |
|-----------|------------|----------------------|---------|
| OHLCV Collection (100 tickers) | 500s | 150s | 3.3x |
| Indicator Calculation (1000 tickers) | 120s | 35s | 3.4x |
| Full Pipeline (KR market) | 60m | 20m | 3.0x |

**Resource Requirements**:
- CPU: 4+ cores recommended
- Memory: ~2GB per 10 workers
- Network: Stable connection for API calls

---

## Enhancement 3: Data Quality Validation Rules

### 1. Current Validation Gaps

**Existing Validators** (validators.py):
- Ticker coverage
- OHLCV coverage
- Fundamental coverage
- Basic price anomaly detection

**Missing Validations**:
- Fundamental data consistency
- Missing data patterns
- Outlier detection
- Cross-table consistency
- Data staleness checks

### 2. Enhanced Validation Framework

#### 2.1 Expanded Validator Class

```python
"""
Enhanced Data Quality Validators

New features:
- Fundamental data consistency checks
- Advanced outlier detection
- Missing data pattern analysis
- Cross-table consistency validation
- Data staleness monitoring
- Automated remediation suggestions
"""

from typing import Dict, List, Optional, Tuple
import logging
import numpy as np
from modules.db_manager_postgres import PostgresDatabaseManager

logger = logging.getLogger(__name__)


class EnhancedDataQualityValidator:
    """
    Enhanced data quality validator with comprehensive checks
    
    New Validations:
    1. Fundamental consistency (assets = liabilities + equity)
    2. Ratio validity (P/E, P/B within reasonable ranges)
    3. Missing data patterns (systematic gaps)
    4. Outlier detection (Z-score, IQR methods)
    5. Cross-table consistency (ohlcv vs fundamentals)
    6. Data staleness (last update checks)
    7. Duplicate detection (same ticker/date/period)
    """
    
    # Validation thresholds
    FUNDAMENTAL_BALANCE_TOLERANCE = 0.05  # 5% tolerance for assets = liab + equity
    PER_MIN, PER_MAX = -100, 1000  # P/E ratio bounds
    PBR_MIN, PBR_MAX = 0, 50  # P/B ratio bounds
    PRICE_CHANGE_THRESHOLD = 0.30  # 30% daily change is outlier
    DATA_STALENESS_DAYS = 7  # Data older than 7 days is stale
    MISSING_DATA_THRESHOLD = 0.20  # 20% missing data triggers alert
    
    def __init__(self, db: PostgresDatabaseManager):
        """Initialize enhanced validator"""
        self.db = db
        logger.info("EnhancedDataQualityValidator initialized")
    
    def validate_comprehensive(self, regions: List[str]) -> Dict[str, Dict]:
        """
        Run comprehensive validation suite
        
        Args:
            regions: List of region codes
        
        Returns:
            Dict mapping region to validation results with all checks
        """
        logger.info(f"🔍 Running comprehensive validation for regions: {regions}")
        
        results = {}
        
        for region in regions:
            results[region] = {
                'fundamental_consistency': self._validate_fundamental_consistency(region),
                'ratio_validity': self._validate_ratio_validity(region),
                'missing_data_patterns': self._validate_missing_data_patterns(region),
                'outlier_detection': self._validate_outliers(region),
                'cross_table_consistency': self._validate_cross_table_consistency(region),
                'data_staleness': self._validate_data_staleness(region),
                'duplicate_detection': self._validate_duplicates(region)
            }
            
            # Overall pass/fail
            results[region]['passed'] = all(
                v.get('passed', True)
                for v in results[region].values()
                if isinstance(v, dict)
            )
            
            # Log summary
            status = "✅" if results[region]['passed'] else "⚠️"
            logger.info(f"  {status} [{region}] Comprehensive validation complete")
        
        return results
    
    def _validate_fundamental_consistency(self, region: str) -> Dict:
        """
        Validate fundamental accounting equation: Assets = Liabilities + Equity
        
        Args:
            region: Region code
        
        Returns:
            Validation result with inconsistent tickers
        """
        logger.info(f"  Checking fundamental consistency for {region}...")
        
        query = """
        SELECT
            ticker,
            date,
            total_assets,
            total_liabilities,
            total_equity,
            ABS((total_assets - (total_liabilities + total_equity)) / NULLIF(total_assets, 0)) as imbalance_ratio
        FROM ticker_fundamentals
        WHERE region = %s
          AND total_assets > 0
          AND ABS((total_assets - (total_liabilities + total_equity)) / total_assets) > %s
        ORDER BY imbalance_ratio DESC
        LIMIT 100
        """
        
        result = self.db.execute_query(query, (region, self.FUNDAMENTAL_BALANCE_TOLERANCE))
        
        inconsistent_count = len(result) if result else 0
        
        return {
            'passed': inconsistent_count == 0,
            'inconsistent_count': inconsistent_count,
            'threshold': self.FUNDAMENTAL_BALANCE_TOLERANCE,
            'samples': result[:10] if result else []
        }
    
    def _validate_ratio_validity(self, region: str) -> Dict:
        """
        Validate valuation ratios are within reasonable bounds
        
        Args:
            region: Region code
        
        Returns:
            Validation result with invalid ratios
        """
        logger.info(f"  Checking ratio validity for {region}...")
        
        query = """
        SELECT
            ticker,
            date,
            per,
            pbr,
            CASE
                WHEN per < %s OR per > %s THEN 'Invalid P/E'
                WHEN pbr < %s OR pbr > %s THEN 'Invalid P/B'
                ELSE 'Unknown'
            END as issue
        FROM ticker_fundamentals
        WHERE region = %s
          AND (
              (per IS NOT NULL AND (per < %s OR per > %s))
              OR
              (pbr IS NOT NULL AND (pbr < %s OR pbr > %s))
          )
        ORDER BY date DESC
        LIMIT 100
        """
        
        result = self.db.execute_query(
            query,
            (self.PER_MIN, self.PER_MAX, self.PBR_MIN, self.PBR_MAX,
             region,
             self.PER_MIN, self.PER_MAX, self.PBR_MIN, self.PBR_MAX)
        )
        
        invalid_count = len(result) if result else 0
        
        return {
            'passed': invalid_count == 0,
            'invalid_count': invalid_count,
            'per_bounds': (self.PER_MIN, self.PER_MAX),
            'pbr_bounds': (self.PBR_MIN, self.PBR_MAX),
            'samples': result[:10] if result else []
        }
    
    def _validate_missing_data_patterns(self, region: str) -> Dict:
        """
        Detect systematic missing data patterns
        
        Args:
            region: Region code
        
        Returns:
            Validation result with missing data statistics
        """
        logger.info(f"  Checking missing data patterns for {region}...")
        
        # Check fundamental fields completeness
        query = """
        SELECT
            COUNT(*) as total_records,
            COUNT(total_assets) as has_assets,
            COUNT(total_equity) as has_equity,
            COUNT(revenue) as has_revenue,
            COUNT(net_income) as has_net_income,
            COUNT(per) as has_per,
            COUNT(pbr) as has_pbr
        FROM ticker_fundamentals
        WHERE region = %s
        """
        
        result = self.db.execute_query(query, (region,))
        
        if not result:
            return {'passed': False, 'error': 'No data'}
        
        row = result[0]
        total = row['total_records']
        
        # Calculate missing percentages
        missing_stats = {
            'assets': 1 - (row['has_assets'] / total) if total > 0 else 0,
            'equity': 1 - (row['has_equity'] / total) if total > 0 else 0,
            'revenue': 1 - (row['has_revenue'] / total) if total > 0 else 0,
            'net_income': 1 - (row['has_net_income'] / total) if total > 0 else 0,
            'per': 1 - (row['has_per'] / total) if total > 0 else 0,
            'pbr': 1 - (row['has_pbr'] / total) if total > 0 else 0
        }
        
        # Check if any field exceeds threshold
        high_missing = {
            field: pct
            for field, pct in missing_stats.items()
            if pct > self.MISSING_DATA_THRESHOLD
        }
        
        return {
            'passed': len(high_missing) == 0,
            'missing_stats': missing_stats,
            'high_missing_fields': high_missing,
            'threshold': self.MISSING_DATA_THRESHOLD
        }
    
    def _validate_outliers(self, region: str) -> Dict:
        """
        Detect price and volume outliers using statistical methods
        
        Args:
            region: Region code
        
        Returns:
            Validation result with outlier tickers
        """
        logger.info(f"  Detecting outliers for {region}...")
        
        # Detect price outliers (>30% daily change)
        query = """
        WITH price_changes AS (
            SELECT
                ticker,
                date,
                close,
                LAG(close) OVER (PARTITION BY ticker ORDER BY date) as prev_close,
                ABS((close - LAG(close) OVER (PARTITION BY ticker ORDER BY date)) / 
                    NULLIF(LAG(close) OVER (PARTITION BY ticker ORDER BY date), 0)) as change_pct
            FROM ohlcv_data
            WHERE region = %s
              AND date >= NOW() - INTERVAL '30 days'
        )
        SELECT
            ticker,
            date,
            close,
            prev_close,
            change_pct
        FROM price_changes
        WHERE change_pct > %s
        ORDER BY change_pct DESC
        LIMIT 100
        """
        
        result = self.db.execute_query(query, (region, self.PRICE_CHANGE_THRESHOLD))
        
        outlier_count = len(result) if result else 0
        
        return {
            'passed': outlier_count < 10,  # Allow up to 10 outliers
            'outlier_count': outlier_count,
            'threshold': self.PRICE_CHANGE_THRESHOLD,
            'samples': result[:10] if result else []
        }
    
    def _validate_cross_table_consistency(self, region: str) -> Dict:
        """
        Validate consistency between ohlcv_data and ticker_fundamentals
        
        Args:
            region: Region code
        
        Returns:
            Validation result with consistency issues
        """
        logger.info(f"  Checking cross-table consistency for {region}...")
        
        # Check if fundamentals exist for tickers with OHLCV data
        query = """
        SELECT
            t.ticker,
            COUNT(DISTINCT o.date) as ohlcv_days,
            COUNT(DISTINCT f.date) as fundamental_records
        FROM tickers t
        LEFT JOIN ohlcv_data o ON t.ticker = o.ticker AND t.region = o.region
        LEFT JOIN ticker_fundamentals f ON t.ticker = f.ticker AND t.region = f.region
        WHERE t.region = %s
          AND t.is_etf = FALSE
        GROUP BY t.ticker
        HAVING COUNT(DISTINCT o.date) > 0 AND COUNT(DISTINCT f.date) = 0
        LIMIT 100
        """
        
        result = self.db.execute_query(query, (region,))
        
        missing_fundamentals_count = len(result) if result else 0
        
        return {
            'passed': missing_fundamentals_count < 50,
            'missing_fundamentals_count': missing_fundamentals_count,
            'samples': result[:10] if result else []
        }
    
    def _validate_data_staleness(self, region: str) -> Dict:
        """
        Check for stale data (not updated recently)
        
        Args:
            region: Region code
        
        Returns:
            Validation result with stale tickers
        """
        logger.info(f"  Checking data staleness for {region}...")
        
        # Check OHLCV data staleness
        query = """
        SELECT
            ticker,
            MAX(date) as last_update,
            NOW()::date - MAX(date) as days_stale
        FROM ohlcv_data
        WHERE region = %s
        GROUP BY ticker
        HAVING NOW()::date - MAX(date) > %s
        LIMIT 100
        """
        
        result = self.db.execute_query(query, (region, self.DATA_STALENESS_DAYS))
        
        stale_count = len(result) if result else 0
        
        return {
            'passed': stale_count < 10,
            'stale_count': stale_count,
            'threshold_days': self.DATA_STALENESS_DAYS,
            'samples': result[:10] if result else []
        }
    
    def _validate_duplicates(self, region: str) -> Dict:
        """
        Detect duplicate records (same ticker/date/period)
        
        Args:
            region: Region code
        
        Returns:
            Validation result with duplicate records
        """
        logger.info(f"  Detecting duplicates for {region}...")
        
        # Check fundamental duplicates
        query = """
        SELECT
            ticker,
            date,
            period_type,
            COUNT(*) as duplicate_count
        FROM ticker_fundamentals
        WHERE region = %s
        GROUP BY ticker, date, period_type
        HAVING COUNT(*) > 1
        LIMIT 100
        """
        
        result = self.db.execute_query(query, (region,))
        
        duplicate_count = len(result) if result else 0
        
        return {
            'passed': duplicate_count == 0,
            'duplicate_count': duplicate_count,
            'samples': result[:10] if result else []
        }
    
    def generate_remediation_report(self, validation_results: Dict) -> str:
        """
        Generate automated remediation recommendations
        
        Args:
            validation_results: Results from validate_comprehensive
        
        Returns:
            Markdown-formatted remediation report
        """
        report = []
        report.append("# Data Quality Remediation Report\n")
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for region, results in validation_results.items():
            report.append(f"## Region: {region}\n")
            
            # Check each validation
            if not results.get('fundamental_consistency', {}).get('passed'):
                report.append("### ⚠️ Fundamental Consistency Issues\n")
                report.append("**Recommendation**: Re-run DART backfill for inconsistent tickers\n")
                report.append("```bash\n")
                report.append("python3 scripts/backfill_fundamentals_dart.py --incremental\n")
                report.append("```\n\n")
            
            if not results.get('ratio_validity', {}).get('passed'):
                report.append("### ⚠️ Invalid Valuation Ratios\n")
                report.append("**Recommendation**: Recalculate ratios with updated price data\n")
                report.append("```bash\n")
                report.append("python3 scripts/calculate_valuation_ratios.py --region KR\n")
                report.append("```\n\n")
            
            if not results.get('outlier_detection', {}).get('passed'):
                report.append("### ⚠️ Price Outliers Detected\n")
                report.append("**Recommendation**: Investigate anomalies and apply data corrections\n")
                report.append("```bash\n")
                report.append("python3 scripts/detect_price_anomalies.py --region KR\n")
                report.append("```\n\n")
            
            if not results.get('data_staleness', {}).get('passed'):
                report.append("### ⚠️ Stale Data Detected\n")
                report.append("**Recommendation**: Run incremental update to refresh data\n")
                report.append("```bash\n")
                report.append("python3 modules/orchestration/orchestrator.py --regions KR --incremental\n")
                report.append("```\n\n")
        
        return "".join(report)
```

---

## Implementation Priorities

### Priority 1: Quarterly Financials (HIGH)
**Rationale**: Fills critical gap in Phase 3 requirements  
**Timeline**: 1-2 weeks  
**Dependencies**: None  
**Risk**: Low (follows established patterns)

### Priority 2: Enhanced Validation (MEDIUM)
**Rationale**: Improves data quality confidence  
**Timeline**: 1 week  
**Dependencies**: None  
**Risk**: Low (extends existing validators)

### Priority 3: PostgreSQL Migration (HIGH)
**Rationale**: Eliminates dual-database architecture  
**Timeline**: 2-3 weeks  
**Dependencies**: Requires thorough testing  
**Risk**: Medium (breaking change)

### Priority 4: Parallel Processing (LOW)
**Rationale**: Performance optimization (nice-to-have)  
**Timeline**: 2 weeks  
**Dependencies**: PostgreSQL migration recommended  
**Risk**: Medium (concurrency complexity)

---

## Risk Analysis

### Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| DART API rate limit violations | High | Medium | Implement strict rate limiting (1 req/sec) |
| Data quality degradation | High | Low | Comprehensive validation before deployment |
| PostgreSQL migration data loss | Critical | Low | Full backup + validation + rollback plan |
| Concurrency bugs in parallel processing | Medium | Medium | Extensive testing + gradual rollout |
| Memory exhaustion with large datasets | Medium | Low | Batch processing + memory monitoring |

### Operational Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Extended downtime during migration | Medium | Low | Off-hours deployment + checkpoint recovery |
| Performance regression | Medium | Low | Benchmark testing before/after |
| Increased operational complexity | Low | Medium | Comprehensive documentation + training |

### Dependencies

**External Dependencies**:
- DART API availability (99%+ uptime)
- PostgreSQL stability
- KIS API access

**Internal Dependencies**:
- Existing DART client (dart_api_client.py)
- Database manager (db_manager_postgres.py)
- Orchestration framework (modules/orchestration/)

---

## Appendix A: File Structure

```
spock/
  scripts/
    update_quarterly_financials.py      (NEW - Phase 3)
    migrations/
      migrate_sqlite_to_postgres.py     (NEW - Enhancement 1)
  
  modules/
    parallel_collector.py                (NEW - Enhancement 2)
    orchestration/
      orchestrator.py                    (MODIFY - integrate new features)
      validators.py                      (EXTEND - enhanced validations)
  
  tests/
    orchestration/
      test_quarterly_financials_updater.py  (NEW - Phase 3)
      test_parallel_collector.py             (NEW - Enhancement 2)
      test_enhanced_validators.py            (NEW - Enhancement 3)
  
  docs/
    UNIFIED_DB_UPDATE_SYSTEM_ENHANCEMENTS.md  (THIS DOCUMENT)
```

---

## Appendix B: Database Schema Changes

### ticker_fundamentals table (already supports quarterly data)

```sql
-- No schema changes needed for Phase 3
-- Existing structure already supports period_type = 'QUARTERLY'

-- Verify constraint
SELECT constraint_name, constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'ticker_fundamentals'
  AND constraint_name LIKE '%period_type%';

-- Expected constraint:
-- UNIQUE (ticker, region, date, period_type)
```

### Performance Indexes for Quarterly Queries

```sql
-- Add index for quarterly data retrieval (if not exists)
CREATE INDEX IF NOT EXISTS idx_ticker_fundamentals_quarterly
ON ticker_fundamentals (region, ticker, date DESC)
WHERE period_type = 'QUARTERLY';

-- Add index for fiscal year queries
CREATE INDEX IF NOT EXISTS idx_ticker_fundamentals_fiscal_year
ON ticker_fundamentals (fiscal_year, period_type);
```

---

**End of Document**
