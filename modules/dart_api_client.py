#!/usr/bin/env python3
"""
DART (금융감독원 전자공시시스템) Open API Client

Provides access to FSS DART Open API for ETF disclosure data extraction.
Supports TER (Total Expense Ratio) extraction from quarterly/annual reports.

API Documentation: https://opendart.fss.or.kr/

Author: Spock Trading System
"""

import os
import time
import json
import zipfile
import logging
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
logger = logging.getLogger(__name__)


class DARTApiClient:
    """
    DART Open API client for ETF disclosure data extraction

    Rate Limits:
    - 1,000 requests per day
    - Recommended: 100 requests per hour for safety margin
    """

    BASE_URL = "https://opendart.fss.or.kr/api"
    CORP_CODE_URL = "https://opendart.fss.or.kr/api/corpCode.xml"

    def __init__(self, api_key: Optional[str] = None, rate_limit_delay: float = 36.0):
        """
        Initialize DART API client

        Args:
            api_key: DART Open API key (if None, loads from environment variable DART_API_KEY)
            rate_limit_delay: Delay between requests in seconds (default: 36s = 100 req/hour)
        """
        from dotenv import load_dotenv
        load_dotenv()
        self.api_key = api_key or os.getenv('DART_API_KEY')
        if not self.api_key:
            raise ValueError(
                "DART API key not provided. "
                "Set DART_API_KEY environment variable or pass api_key parameter. "
                "Get API key from: https://opendart.fss.or.kr/"
            )

        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def _wait_for_rate_limit(self):
        """Enforce rate limiting between API calls"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.1f}s")
            time.sleep(wait_time)
        self.last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Dict, max_retries: int = 3) -> requests.Response:
        """
        Make API request with rate limiting and retry logic

        Args:
            endpoint: API endpoint path
            params: Request parameters
            max_retries: Maximum number of retry attempts

        Returns:
            Response object

        Raises:
            requests.RequestException: If request fails after all retries
        """
        params['crtfc_key'] = self.api_key

        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()

                url = f"{self.BASE_URL}/{endpoint}"
                response = self.session.get(url, params=params, timeout=30)
                response.raise_for_status()

                return response

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
                if attempt == max_retries - 1:
                    raise
                time.sleep(5 * (attempt + 1))  # Exponential backoff

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(5 * (attempt + 1))

        raise requests.RequestException("All retry attempts failed")

    def download_corp_codes(self, save_path: str = "config/dart_corp_codes.xml") -> str:
        """
        Download DART corporate code master file

        Args:
            save_path: Path to save the downloaded XML file

        Returns:
            Path to saved file
        """
        logger.info("Downloading DART corporate code master...")

        try:
            self._wait_for_rate_limit()

            response = self.session.get(
                self.CORP_CODE_URL,
                params={'crtfc_key': self.api_key},
                timeout=60
            )
            response.raise_for_status()

            # DART returns a ZIP file containing CORPCODE.xml
            zip_path = save_path.replace('.xml', '.zip')

            # Ensure directory exists
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # Save ZIP file
            with open(zip_path, 'wb') as f:
                f.write(response.content)

            # Extract XML from ZIP
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(os.path.dirname(save_path))

            # Rename extracted file
            extracted_file = os.path.join(os.path.dirname(save_path), 'CORPCODE.xml')
            if os.path.exists(extracted_file):
                os.rename(extracted_file, save_path)

            # Clean up ZIP file
            os.remove(zip_path)

            logger.info(f"Corporate code master saved to {save_path}")
            return save_path

        except Exception as e:
            logger.error(f"Failed to download corporate codes: {e}")
            raise

    def parse_corp_codes(self, xml_path: str) -> Dict[str, Dict]:
        """
        Parse DART corporate code XML file

        Args:
            xml_path: Path to CORPCODE.xml file

        Returns:
            Dictionary mapping corp_name -> {corp_code, stock_code}
        """
        logger.info(f"Parsing corporate codes from {xml_path}")

        corp_mapping = {}

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            for corp in root.findall('list'):
                corp_code = corp.find('corp_code').text
                corp_name = corp.find('corp_name').text
                stock_code = corp.find('stock_code').text

                # Store mapping
                corp_mapping[corp_name] = {
                    'corp_code': corp_code,
                    'stock_code': stock_code if stock_code else None
                }

            logger.info(f"Parsed {len(corp_mapping)} corporate codes")
            return corp_mapping

        except Exception as e:
            logger.error(f"Failed to parse corporate codes: {e}")
            raise

    def search_disclosure(
        self,
        corp_code: str,
        start_date: str,
        end_date: str,
        report_type: str = 'A001',  # Annual report
        page_count: int = 100
    ) -> List[Dict]:
        """
        Search for disclosures by corporation and date range

        Args:
            corp_code: DART corporate code (8 digits)
            start_date: Start date (YYYYMMDD)
            end_date: End date (YYYYMMDD)
            report_type: Report type code (A001=annual, A002=semi, A003=quarterly)
            page_count: Number of results per page

        Returns:
            List of disclosure documents
        """
        params = {
            'corp_code': corp_code,
            'bgn_de': start_date,
            'end_de': end_date,
            'pblntf_ty': report_type,
            'page_count': page_count
        }

        try:
            response = self._make_request('list.json', params)
            data = response.json()

            if data['status'] == '000':  # Success
                return data.get('list', [])
            else:
                logger.warning(f"DART API error: {data.get('message', 'Unknown error')}")
                return []

        except Exception as e:
            logger.error(f"Failed to search disclosures: {e}")
            return []

    def get_fundamental_metrics(self, ticker: str, corp_code: Optional[str] = None) -> Optional[Dict]:
        """
        Get fundamental metrics for a Korean stock from DART API

        Args:
            ticker: Korean stock ticker (6-digit code, e.g., '005930')
            corp_code: DART corporate code (8-digit, optional - will look up if not provided)

        Returns:
            Dict with fundamental metrics or None on failure

        Example:
            metrics = dart.get_fundamental_metrics('005930')
            # {'ticker': '005930', 'per': 12.5, 'pbr': 1.8, 'roe': 15.2, ...}

        Note:
            Phase 1 Week 2: Enhanced implementation with intelligent report selection
            - Tries quarterly/semi-annual reports first (most recent data)
            - Falls back to annual report if quarterly data not available
            - Automatically selects most recent available report based on current date
        """
        try:
            # Look up corp_code if not provided
            if not corp_code:
                logger.warning(f"⚠️ [DART] {ticker}: Corp code lookup not implemented yet")
                return None

            # Get prioritized list of reports to try (most recent first)
            report_attempts = self._get_report_priority_list()

            # Try each report type in priority order
            for year, reprt_code, report_name in report_attempts:
                logger.debug(f"🔍 [DART] {ticker}: Trying {report_name} ({year})")

                # Use fnlttSinglAcntAll for ALL account items (100+ vs 14 summary)
                params = {
                    'corp_code': corp_code,
                    'bsns_year': year,
                    'reprt_code': reprt_code,
                    'fs_div': 'CFS'  # CFS=연결재무제표 (Consolidated)
                }

                try:
                    response = self._make_request('fnlttSinglAcntAll.json', params)
                    data = response.json()

                    # If successful and has data, use this report
                    if data['status'] == '000' and data.get('list'):
                        items = data.get('list', [])
                        logger.info(f"✅ [DART] {ticker}: Using {report_name} ({year})")

                        # Parse financial metrics with metadata
                        metrics = self._parse_financial_statements(ticker, items, year, reprt_code)
                        return metrics
                    else:
                        logger.debug(f"⏭️ [DART] {ticker}: {report_name} ({year}) not available")

                except Exception as e:
                    logger.debug(f"⏭️ [DART] {ticker}: {report_name} ({year}) failed - {e}")
                    continue

            # If all attempts failed
            logger.warning(f"⚠️ [DART] {ticker}: No financial data available from any report type")
            return None

        except Exception as e:
            logger.error(f"❌ [DART] {ticker}: Failed to get fundamental metrics - {e}")
            return None

    def get_historical_fundamentals(self,
                                   ticker: str,
                                   corp_code: str,
                                   start_year: int,
                                   end_year: int) -> List[Dict]:
        """
        Get historical annual fundamental data for backtesting

        Args:
            ticker: Korean stock ticker (6-digit code)
            corp_code: DART corporate code (8-digit)
            start_year: Start fiscal year (e.g., 2020)
            end_year: End fiscal year (e.g., 2024)

        Returns:
            List of fundamental metrics dictionaries (one per year)

        Example:
            metrics_list = dart.get_historical_fundamentals(
                ticker='005930',
                corp_code='00126380',
                start_year=2020,
                end_year=2024
            )
            # Returns 5 dicts (2020, 2021, 2022, 2023, 2024)

        Note:
            - Only collects annual reports (11011) for efficiency
            - Used for backtesting with historical data
            - Each year's data is independent
        """
        results = []

        for year in range(start_year, end_year + 1):
            logger.info(f"📊 [DART] {ticker}: Collecting {year} annual report...")

            try:
                # Query annual report for specific year
                # Use fnlttSinglAcntAll for ALL account items (100+ vs 14 summary)
                params = {
                    'corp_code': corp_code,
                    'bsns_year': year,
                    'reprt_code': '11011',  # Annual report only
                    'fs_div': 'CFS'  # CFS=연결재무제표 (Consolidated), OFS=개별재무제표 (Separate)
                }

                response = self._make_request('fnlttSinglAcntAll.json', params)
                data = response.json()

                if data['status'] == '000' and data.get('list'):
                    items = data.get('list', [])

                    # Parse financial metrics
                    metrics = self._parse_financial_statements(
                        ticker=ticker,
                        items=items,
                        year=year,
                        reprt_code='11011'
                    )

                    results.append(metrics)
                    logger.info(f"✅ [DART] {ticker}: {year} annual data collected")

                else:
                    logger.warning(f"⚠️ [DART] {ticker}: {year} annual data not available")

            except Exception as e:
                logger.error(f"❌ [DART] {ticker}: Failed to collect {year} data - {e}")
                continue

        logger.info(f"📊 [DART] {ticker}: Collected {len(results)}/{end_year - start_year + 1} years")
        return results

    def _get_report_priority_list(self) -> List[Tuple[int, str, str]]:
        """
        Get prioritized list of reports to try based on current date

        Returns:
            List of (year, reprt_code, report_name) tuples in priority order

        Report Types:
            - '11011': Annual report (사업보고서) - Published Mar-Apr
            - '11012': Semi-annual report (반기보고서) - Published Aug
            - '11013': Q1 report (1분기보고서) - Published May
            - '11014': Q3 report (3분기보고서) - Published Nov

        Priority Strategy (based on publication schedule):
            November-December: Q3 2025 > H1 2025 > Q1 2025 > Annual 2025
            August-October: H1 2025 > Q1 2025 > Annual 2025 > Q3 2024
            May-July: Q1 2025 > Annual 2025 > H1 2024
            April: Annual 2025 > Q3 2024 > H1 2024
            January-March: Q3 2024 > H1 2024 > Annual 2024
        """
        current_year = datetime.now().year
        current_month = datetime.now().month
        priority_list = []

        if current_month >= 11:
            # November-December: Q3 should be available
            priority_list = [
                (current_year, '11014', 'Q3 Report'),
                (current_year, '11012', 'Semi-Annual Report'),
                (current_year, '11013', 'Q1 Report'),
                (current_year, '11011', 'Annual Report'),
                (current_year - 1, '11014', 'Q3 Report (Previous Year)'),
            ]
        elif current_month >= 8:
            # August-October: Semi-annual should be available
            priority_list = [
                (current_year, '11012', 'Semi-Annual Report'),
                (current_year, '11013', 'Q1 Report'),
                (current_year, '11011', 'Annual Report'),
                (current_year - 1, '11014', 'Q3 Report (Previous Year)'),
                (current_year - 1, '11012', 'Semi-Annual Report (Previous Year)'),
            ]
        elif current_month >= 5:
            # May-July: Q1 should be available
            priority_list = [
                (current_year, '11013', 'Q1 Report'),
                (current_year, '11011', 'Annual Report'),
                (current_year - 1, '11014', 'Q3 Report (Previous Year)'),
                (current_year - 1, '11012', 'Semi-Annual Report (Previous Year)'),
            ]
        elif current_month >= 4:
            # April: Annual should be available
            priority_list = [
                (current_year, '11011', 'Annual Report'),
                (current_year - 1, '11014', 'Q3 Report (Previous Year)'),
                (current_year - 1, '11012', 'Semi-Annual Report (Previous Year)'),
                (current_year - 1, '11013', 'Q1 Report (Previous Year)'),
            ]
        else:
            # January-March: Use previous year's quarterly data
            priority_list = [
                (current_year - 1, '11014', 'Q3 Report (Previous Year)'),
                (current_year - 1, '11012', 'Semi-Annual Report (Previous Year)'),
                (current_year - 1, '11013', 'Q1 Report (Previous Year)'),
                (current_year - 1, '11011', 'Annual Report (Previous Year)'),
            ]

        logger.debug(f"📊 Report priority (month {current_month}): {[name for _, _, name in priority_list]}")
        return priority_list

    def _extract_equity_accounts(self, item_lookup: Dict[str, float]) -> Dict[str, Optional[float]]:
        """
        Extract detailed equity account breakdown from DART financial statements.

        Uses fuzzy matching with priority-ordered patterns to handle account name
        variations across different companies.

        Args:
            item_lookup: Dictionary mapping account names to amounts

        Returns:
            Dict with 8 equity account keys:
                - capital_stock: 자본금 (common + preferred stock)
                - capital_surplus: 자본잉여금 (paid-in capital above par)
                - retained_earnings: 이익잉여금 (accumulated profits)
                - treasury_stock: 자기주식 (repurchased shares, negative)
                - other_comprehensive_income: 기타포괄손익누계액
                - non_controlling_interest: 비지배지분 (minority interest)
                - unappropriated_retained_earnings: 미처분이익잉여금
                - legal_reserve: 이익준비금

        Note:
            - Treasury stock is normalized to negative (deduction account)
            - Returns None for missing accounts (graceful degradation)
            - Patterns ordered by priority (most common first)
        """
        # Priority-ordered fuzzy matching patterns
        # Each account has multiple variations to handle different company naming conventions
        EQUITY_ACCOUNT_PATTERNS = {
            'capital_stock': [
                '자본금',
                '보통주자본금',
                '우선주자본금',
                '자 본 금',  # With spaces
                '자본금(보통주)',  # With parentheses
            ],
            'capital_surplus': [
                '자본잉여금',
                '주식발행초과금',
                '자본 잉여금',  # With space
                '자본잉여금(주식발행초과금)',  # With parentheses
            ],
            'retained_earnings': [
                '이익잉여금',
                '이익잉여금(결손금)',  # With deficit notation
                '이 익 잉 여 금',  # With spaces
                '이익잉여금(미처분)',  # With unappropriated notation
            ],
            'treasury_stock': [
                '자기주식',
                '자기주식처분손익',
                '자 기 주 식',  # With spaces
                '자기주식취득',
            ],
            'other_comprehensive_income': [
                '기타포괄손익누계액',
                '기타자본구성요소',
                '기타자본항목',
                '기타포괄손익',
            ],
            'non_controlling_interest': [
                '비지배지분',
                '소수주주지분',  # Alternative term
                '비지배주주지분',
            ],
            'unappropriated_retained_earnings': [
                '미처분이익잉여금',
                '미처분이익잉여금(미처리결손금)',
            ],
            'legal_reserve': [
                '이익준비금',
                '법정적립금',
            ],
        }

        equity_accounts = {}

        # Extract each equity account using fuzzy matching
        for account_key, patterns in EQUITY_ACCOUNT_PATTERNS.items():
            value = None

            # Try each pattern in priority order
            for pattern in patterns:
                if pattern in item_lookup:
                    value = item_lookup[pattern]
                    break

            # Special handling: Treasury stock must be negative (deduction account)
            if account_key == 'treasury_stock' and value is not None and value > 0:
                logger.warning(
                    f"Treasury stock has positive value ({value}), normalizing to negative"
                )
                value = -value

            equity_accounts[account_key] = value

        return equity_accounts

    def _validate_equity_breakdown(
        self,
        total_equity: float,
        equity_accounts: Dict[str, Optional[float]],
        tolerance: float = 0.05
    ) -> Dict[str, any]:
        """
        Validate equity account breakdown accuracy.

        Checks if sum of equity components matches total_equity within tolerance.

        Args:
            total_equity: Total equity from financial statements (자본총계)
            equity_accounts: Dict with detailed equity account breakdown
            tolerance: Acceptable percentage difference (default: 5%)

        Returns:
            Dict with validation results:
                - passed: True if within tolerance, False otherwise, None if cannot validate
                - calculated_equity: Sum of equity components
                - error_amount: Absolute difference
                - error_percentage: Percentage difference (0-100)
                - message: Human-readable validation message

        Logic:
            calculated_equity = capital_stock + capital_surplus + retained_earnings +
                               treasury_stock (negative) + other_comprehensive_income +
                               non_controlling_interest

            error_percentage = |total_equity - calculated_equity| / |total_equity| * 100

            passed = error_percentage <= tolerance * 100
        """
        # Extract components (skip sub-accounts: unappropriated_retained_earnings, legal_reserve)
        capital_stock = equity_accounts.get('capital_stock')
        capital_surplus = equity_accounts.get('capital_surplus')
        retained_earnings = equity_accounts.get('retained_earnings')
        treasury_stock = equity_accounts.get('treasury_stock')
        other_comprehensive_income = equity_accounts.get('other_comprehensive_income')
        non_controlling_interest = equity_accounts.get('non_controlling_interest')

        # Check if we have enough data to validate
        # Require at least capital_stock + retained_earnings (core components)
        if capital_stock is None and retained_earnings is None:
            return {
                'passed': None,
                'calculated_equity': None,
                'error_amount': None,
                'error_percentage': None,
                'message': 'Insufficient data: missing both capital_stock and retained_earnings'
            }

        # Calculate equity from components (sum only non-None values)
        components = [
            capital_stock,
            capital_surplus,
            retained_earnings,
            treasury_stock,  # Already normalized to negative
            other_comprehensive_income,
            non_controlling_interest,
        ]

        calculated_equity = sum(v for v in components if v is not None)

        # Calculate error
        if total_equity == 0:
            # Special case: total_equity is zero
            if calculated_equity == 0:
                return {
                    'passed': True,
                    'calculated_equity': 0,
                    'error_amount': 0,
                    'error_percentage': 0.0,
                    'message': 'Both total_equity and calculated_equity are zero (valid)'
                }
            else:
                return {
                    'passed': False,
                    'calculated_equity': calculated_equity,
                    'error_amount': abs(calculated_equity),
                    'error_percentage': None,  # Cannot calculate percentage when denominator is zero
                    'message': f'total_equity is zero but calculated_equity is {calculated_equity}'
                }

        error_amount = abs(total_equity - calculated_equity)
        error_percentage = (error_amount / abs(total_equity)) * 100

        passed = error_percentage <= (tolerance * 100)

        # Generate message
        if passed:
            message = f'Validation passed: {error_percentage:.2f}% error (within {tolerance*100}% tolerance)'
        else:
            message = f'Validation FAILED: {error_percentage:.2f}% error (outside {tolerance*100}% tolerance)'
            logger.warning(
                f"Equity validation failed: total={total_equity}, "
                f"calculated={calculated_equity}, error={error_percentage:.2f}%"
            )

        return {
            'passed': passed,
            'calculated_equity': calculated_equity,
            'error_amount': error_amount,
            'error_percentage': error_percentage,
            'message': message
        }

    def _parse_financial_statements(self, ticker: str, items: List[Dict],
                                   year: int, reprt_code: str) -> Dict:
        """
        Parse DART financial statement items into fundamental metrics

        Args:
            ticker: Ticker symbol
            items: List of financial statement items from DART API
            year: Fiscal year for this report
            reprt_code: Report type code ('11011'/'11012'/'11013'/'11014')

        Returns:
            Dict with parsed fundamental metrics

        Note:
            DART provides comprehensive financial statement data.
            This parser extracts key metrics: assets, liabilities, equity,
            revenue, operating profit, net income, etc.
        """
        # Determine period type from report code
        period_type_map = {
            '11011': 'ANNUAL',
            '11012': 'SEMI-ANNUAL',
            '11013': 'QUARTERLY',
            '11014': 'QUARTERLY'
        }
        period_type = period_type_map.get(reprt_code, 'ANNUAL')

        # Option B Pattern: Use simple categorical data_source identifier
        # Changed from detailed format "DART-YYYY-CODE" to simple "DART"
        data_source = 'DART'

        # Map report codes to proper fiscal period end dates
        if reprt_code == '11011':  # Annual report
            date = f"{year}-12-31"
        elif reprt_code == '11012':  # Semi-annual report
            date = f"{year}-06-30"
        elif reprt_code == '11013':  # Q1 report
            date = f"{year}-03-31"
        elif reprt_code == '11014':  # Q3 report
            date = f"{year}-09-30"
        else:
            date = f"{year}-12-31"  # Default to year-end

        metrics = {
            'ticker': ticker,
            'date': date,  # Use fiscal period end date instead of current date
            'period_type': period_type,
            'fiscal_year': year,
            'created_at': datetime.now().isoformat(),
            'data_source': data_source
        }

        # Create lookup dict for financial items
        # DART uses Korean account names (계정명)
        # FIX: Use FIRST occurrence for duplicate account names
        # - DART API returns multiple entries for same account (IS, CIS, CF, SCE, BS)
        # - Income Statement (IS) items appear first → correct values
        # - Statement of Changes in Equity (SCE) appears last → often contains zeros
        # - Example: '당기순이익' has 10 entries, last 3 are zeros from SCE
        item_lookup = {}
        for item in items:
            account_name = item.get('account_nm', '')
            amount = item.get('thstrm_amount', '0').replace(',', '')  # 당기금액

            # Only use FIRST occurrence (skip if already exists)
            if account_name not in item_lookup:
                try:
                    item_lookup[account_name] = float(amount)
                except (ValueError, TypeError):
                    pass

        # Extract key financial items
        # Note: Account names may vary slightly across companies
        # Phase 2: Now using fuzzy matching for equity accounts

        # Balance sheet items
        total_assets = item_lookup.get('자산총계', 0)
        total_liabilities = item_lookup.get('부채총계', 0)
        total_equity = item_lookup.get('자본총계', 0)

        # ============================================================
        # Phase 2: Extract detailed equity account breakdown
        # ============================================================
        equity_accounts = self._extract_equity_accounts(item_lookup)

        # Validate equity breakdown (5% tolerance)
        equity_validation = self._validate_equity_breakdown(
            total_equity, equity_accounts
        )
        current_assets = item_lookup.get('유동자산', 0)
        current_liabilities = item_lookup.get('유동부채', 0)
        inventory = item_lookup.get('재고자산', 0)

        # Income statement items
        # Note: DART uses various field names for revenue across different companies
        # - 영업수익: Financial institutions (banks, insurance)
        # - 매출액: Standard manufacturing/services
        # - 수익(매출액): Samsung 2022 and some others
        # - 매출: LG Chem and similar companies
        revenue = (item_lookup.get('영업수익', 0) or
                   item_lookup.get('매출액', 0) or
                   item_lookup.get('수익(매출액)', 0) or
                   item_lookup.get('매출', 0))
        # Operating profit field name variations
        # - '영업이익': Standard (older filings)
        # - '영업이익(손실)': Modern format with profit/loss indicator (SK Hynix, Kakao, Samsung SDI)
        operating_profit = (item_lookup.get('영업이익', 0) or
                           item_lookup.get('영업이익(손실)', 0))
        # Net income field name variations
        # - '당기순이익(손실)': Annual reports (modern format)
        # - '당기순이익': Annual reports (older format)
        # - '반기순이익(손실)': Semi-annual reports (modern format)
        # - '반기순이익': Semi-annual reports (older format)
        # - '분기순이익(손실)': Quarterly reports (modern format)
        # - '분기순이익': Quarterly reports (older format)
        net_income = (item_lookup.get('당기순이익(손실)', 0) or
                     item_lookup.get('당기순이익', 0) or
                     item_lookup.get('반기순이익(손실)', 0) or
                     item_lookup.get('반기순이익', 0) or
                     item_lookup.get('분기순이익(손실)', 0) or
                     item_lookup.get('분기순이익', 0))

        # Calculate derived metrics (if possible)
        if total_equity > 0 and net_income > 0:
            metrics['roe'] = (net_income / total_equity) * 100  # ROE (%)

        if total_assets > 0 and net_income > 0:
            metrics['roa'] = (net_income / total_assets) * 100  # ROA (%)

        if total_equity > 0 and total_liabilities > 0:
            metrics['debt_ratio'] = (total_liabilities / total_equity) * 100  # Debt ratio (%)

        # Store raw financial items for reference
        metrics['total_assets'] = total_assets
        metrics['total_liabilities'] = total_liabilities
        metrics['total_equity'] = total_equity
        metrics['revenue'] = revenue
        metrics['operating_profit'] = operating_profit
        metrics['net_income'] = net_income
        metrics['current_assets'] = current_assets
        metrics['current_liabilities'] = current_liabilities
        metrics['inventory'] = inventory

        # Store detailed equity account breakdown (Phase 2)
        metrics['capital_stock'] = equity_accounts.get('capital_stock')
        metrics['capital_surplus'] = equity_accounts.get('capital_surplus')
        metrics['retained_earnings'] = equity_accounts.get('retained_earnings')
        metrics['treasury_stock'] = equity_accounts.get('treasury_stock')
        metrics['other_comprehensive_income'] = equity_accounts.get('other_comprehensive_income')
        metrics['non_controlling_interest'] = equity_accounts.get('non_controlling_interest')
        metrics['unappropriated_retained_earnings'] = equity_accounts.get('unappropriated_retained_earnings')
        metrics['legal_reserve'] = equity_accounts.get('legal_reserve')

        # Store equity validation result
        metrics['equity_validation_passed'] = equity_validation.get('passed')
        metrics['equity_validation_error_pct'] = equity_validation.get('error_percentage')

        # ============================================================
        # Phase 2: Detailed Financial Statement Items (18 columns)
        # ============================================================

        # Manufacturing Industry Indicators (6 items)
        # COGS field name variations: '매출원가' (standard), '영업원가' (some companies)
        cogs = item_lookup.get('매출원가', 0) or item_lookup.get('영업원가', 0)
        pp_e = item_lookup.get('유형자산', 0)
        accounts_receivable = item_lookup.get('매출채권', 0)

        # Gross profit - use direct field if available, otherwise calculate
        gross_profit = item_lookup.get('매출총이익', 0)
        if gross_profit == 0 and revenue > 0 and cogs > 0:
            gross_profit = revenue - cogs

        # Depreciation - estimate from cash flow if not directly available
        depreciation_direct = item_lookup.get('감가상각비', 0)

        # Operating cash flow field name variations
        # - '영업활동현금흐름': Standard (no space)
        # - '영업활동 현금흐름': SK Hynix (with space)
        # - '영업활동으로 인한 현금흐름': Kakao (detailed description)
        # - '영업으로부터 창출된 현금흐름': Alternative phrasing
        operating_cf = (item_lookup.get('영업활동현금흐름', 0) or
                       item_lookup.get('영업활동 현금흐름', 0) or
                       item_lookup.get('영업활동으로 인한 현금흐름', 0) or
                       item_lookup.get('영업으로부터 창출된 현금흐름', 0))

        working_capital_change = item_lookup.get('영업활동으로 인한 자산부채의 변동', 0)

        if depreciation_direct > 0:
            depreciation = depreciation_direct
        elif operating_cf > 0 and operating_profit > 0:
            # Estimate: Depreciation ≈ Operating CF - Operating Profit - Working Capital Change
            depreciation = max(0, operating_cf - operating_profit - working_capital_change)
        else:
            depreciation = 0

        # Accumulated depreciation - rarely disclosed separately, set to None if not available
        accumulated_depreciation = item_lookup.get('감가상각누계액', None)

        # Retail/E-Commerce Industry Indicators (3 items)
        sga_expense = item_lookup.get('판매비와관리비', 0)

        # R&D expense - rarely disclosed separately, set to None if not available
        rd_expense = item_lookup.get('연구개발비', None)

        # Calculate operating expense (COGS + SG&A)
        operating_expense = cogs + sga_expense

        # Financial Industry Indicators (5 items)
        # Use accrual basis (금융수익/금융비용) instead of cash basis (이자의 수취/지급)
        interest_income = item_lookup.get('금융수익', 0)
        interest_expense = item_lookup.get('금융비용', 0)

        # Loan portfolio, NPL, NIM - only for financial companies
        loan_portfolio = item_lookup.get('대출금', None)
        npl_amount = item_lookup.get('부실채권', None) or item_lookup.get('고정이하여신', None)

        # Calculate NIM (순이자마진) only if loan portfolio exists
        if loan_portfolio and loan_portfolio > 0:
            nim = ((interest_income - interest_expense) / loan_portfolio * 100)
        else:
            nim = None

        # Common Indicators (4 items)
        investing_cf = item_lookup.get('투자활동현금흐름', 0)
        financing_cf = item_lookup.get('재무활동현금흐름', 0)

        # Calculate EBITDA (use estimated depreciation if direct value not available)
        # Fixed logic: Don't require both operating_profit > 0 AND depreciation > 0
        # - If depreciation available: EBITDA = Operating Profit + Depreciation
        # - If depreciation unavailable: EBITDA = Operating Profit (as proxy)
        if depreciation > 0:
            ebitda = operating_profit + depreciation
        else:
            # Depreciation unavailable - use operating profit as EBITDA proxy
            ebitda = operating_profit if operating_profit != 0 else 0

        # Calculate EBITDA margin
        ebitda_margin = (ebitda / revenue * 100) if revenue > 0 and ebitda > 0 else 0

        # Store new detailed financial items
        # Manufacturing (6)
        metrics['cogs'] = cogs
        metrics['gross_profit'] = gross_profit
        metrics['pp_e'] = pp_e
        metrics['depreciation'] = depreciation
        metrics['accounts_receivable'] = accounts_receivable
        metrics['accumulated_depreciation'] = accumulated_depreciation

        # Retail/E-Commerce (3)
        metrics['sga_expense'] = sga_expense
        metrics['rd_expense'] = rd_expense
        metrics['operating_expense'] = operating_expense

        # Financial (5)
        metrics['interest_income'] = interest_income
        metrics['interest_expense'] = interest_expense
        metrics['loan_portfolio'] = loan_portfolio
        metrics['npl_amount'] = npl_amount
        metrics['nim'] = nim

        # Common (4)
        metrics['investing_cf'] = investing_cf
        metrics['financing_cf'] = financing_cf
        metrics['ebitda'] = ebitda
        metrics['ebitda_margin'] = ebitda_margin

        logger.debug(f"✅ [DART] {ticker}: Parsed financial metrics (36 existing + 18 Phase 2 items)")

        return metrics

    def get_document_content(self, rcept_no: str) -> Optional[str]:
        """
        Get disclosure document content

        Args:
            rcept_no: Receipt number of the disclosure

        Returns:
            Document content as HTML/XML string, or None if failed
        """
        params = {'rcept_no': rcept_no}

        try:
            response = self._make_request('document.xml', params)
            return response.text

        except Exception as e:
            logger.error(f"Failed to get document content: {e}")
            return None

    def extract_ter_from_report(
        self,
        corp_code: str,
        lookback_days: int = 365
    ) -> Optional[float]:
        """
        Extract TER (Total Expense Ratio) from most recent financial report

        Args:
            corp_code: DART corporate code
            lookback_days: Number of days to look back for reports

        Returns:
            TER as float (e.g., 0.45 for 0.45%), or None if not found
        """
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y%m%d')

        # Try annual reports first, then semi-annual, then quarterly
        for report_type in ['A001', 'A002', 'A003']:
            disclosures = self.search_disclosure(
                corp_code=corp_code,
                start_date=start_date,
                end_date=end_date,
                report_type=report_type
            )

            if not disclosures:
                continue

            # Get most recent disclosure
            latest = disclosures[0]
            rcept_no = latest.get('rcept_no')

            if not rcept_no:
                continue

            # Get document content
            content = self.get_document_content(rcept_no)

            if content:
                # Try to extract TER from content
                ter = self._parse_ter_from_html(content)
                if ter is not None:
                    return ter

        logger.warning(f"Could not extract TER for corp_code {corp_code}")
        return None

    def _parse_ter_from_html(self, html_content: str) -> Optional[float]:
        """
        Parse TER value from HTML/XML disclosure content

        Args:
            html_content: HTML/XML content from DART disclosure

        Returns:
            TER as float, or None if not found
        """
        try:
            # Common TER field patterns in Korean ETF reports
            ter_patterns = [
                '총보수비용',
                '총보수',
                'TER',
                'Total Expense Ratio',
                '운용보수',
                '펀드보수'
            ]

            # Try to find TER value in HTML
            # This is a simplified implementation - actual parsing may need BeautifulSoup
            for pattern in ter_patterns:
                if pattern in html_content:
                    # Extract numeric value near the pattern
                    # Placeholder: Real implementation requires proper HTML parsing
                    logger.debug(f"Found TER pattern: {pattern}")
                    # TODO: Implement proper HTML/XML parsing logic
                    pass

            return None

        except Exception as e:
            logger.error(f"Failed to parse TER from HTML: {e}")
            return None


class DARTCorpCodeMapper:
    """
    Mapper for ETF ticker -> DART corporate code
    Uses issuer name matching
    """

    def __init__(self, mapping_file: str = "config/dart_corp_codes_mapping.json"):
        """
        Initialize corp code mapper

        Args:
            mapping_file: Path to JSON mapping file
        """
        self.mapping_file = mapping_file
        self.issuer_to_corp_code = {}
        self.load_mapping()

    def load_mapping(self):
        """Load existing mapping from file"""
        if os.path.exists(self.mapping_file):
            try:
                with open(self.mapping_file, 'r', encoding='utf-8') as f:
                    self.issuer_to_corp_code = json.load(f)
                logger.info(f"Loaded {len(self.issuer_to_corp_code)} issuer mappings")
            except Exception as e:
                logger.warning(f"Failed to load mapping file: {e}")
                self.issuer_to_corp_code = {}
        else:
            logger.info("No existing mapping file found, starting fresh")

    def save_mapping(self):
        """Save mapping to file"""
        try:
            os.makedirs(os.path.dirname(self.mapping_file), exist_ok=True)
            with open(self.mapping_file, 'w', encoding='utf-8') as f:
                json.dump(self.issuer_to_corp_code, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.issuer_to_corp_code)} issuer mappings")
        except Exception as e:
            logger.error(f"Failed to save mapping file: {e}")

    def build_mapping_from_corp_codes(self, corp_codes: Dict[str, Dict]):
        """
        Build issuer -> corp_code mapping from DART corp codes

        Args:
            corp_codes: Dictionary from DARTApiClient.parse_corp_codes()
        """
        # Common issuer name variations
        issuer_variations = {
            '미래에셋자산운용': ['미래에셋자산운용(주)', 'Mirae Asset', '미래에셋'],
            '삼성자산운용': ['삼성자산운용(주)', 'Samsung Asset', '삼성'],
            '케이비자산운용': ['케이비자산운용(주)', 'KB Asset', 'KB'],
            '한화자산운용': ['한화자산운용', 'Hanwha Asset', '한화'],
            '신한자산운용': ['신한자산운용 주식회사', 'Shinhan Asset', '신한'],
        }

        for corp_name, corp_info in corp_codes.items():
            # Direct match
            if corp_name in self.issuer_to_corp_code:
                continue

            # Check if any issuer variation matches
            for canonical_name, variations in issuer_variations.items():
                if any(var in corp_name for var in variations):
                    self.issuer_to_corp_code[canonical_name] = corp_info['corp_code']
                    break

            # Also store full corp name
            self.issuer_to_corp_code[corp_name] = corp_info['corp_code']

        self.save_mapping()
        logger.info(f"Built mapping with {len(self.issuer_to_corp_code)} issuers")

    def get_corp_code(self, issuer: str) -> Optional[str]:
        """
        Get DART corporate code for an issuer

        Args:
            issuer: Issuer name (e.g., "미래에셋자산운용(주)")

        Returns:
            DART corporate code, or None if not found
        """
        # Direct match
        if issuer in self.issuer_to_corp_code:
            return self.issuer_to_corp_code[issuer]

        # Fuzzy match - check if issuer name contains any key
        for stored_issuer, corp_code in self.issuer_to_corp_code.items():
            if stored_issuer in issuer or issuer in stored_issuer:
                return corp_code

        logger.warning(f"No DART corp code found for issuer: {issuer}")
        return None


def main():
    """Test DART API client"""
    import argparse

    parser = argparse.ArgumentParser(description='DART API Client Test')
    parser.add_argument('--download-codes', action='store_true', help='Download corporate codes')
    parser.add_argument('--test-search', type=str, help='Test disclosure search with corp_code')

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    try:
        client = DARTApiClient()

        if args.download_codes:
            xml_path = client.download_corp_codes()
            corp_codes = client.parse_corp_codes(xml_path)

            # Build mapping
            mapper = DARTCorpCodeMapper()
            mapper.build_mapping_from_corp_codes(corp_codes)

            logger.info("✅ Corporate codes downloaded and mapped")

        if args.test_search:
            # Test disclosure search
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

            disclosures = client.search_disclosure(
                corp_code=args.test_search,
                start_date=start_date,
                end_date=end_date
            )

            logger.info(f"Found {len(disclosures)} disclosures")
            for disc in disclosures[:5]:
                logger.info(f"  - {disc.get('report_nm')} ({disc.get('rcept_dt')})")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise


if __name__ == '__main__':
    main()
