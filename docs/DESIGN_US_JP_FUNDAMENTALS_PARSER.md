# US/JP Financial Data Parsing System Design

## 1. Executive Summary

### 1.1 Purpose
SEC EDGAR(US)와 EDINET(JP) 공식 API를 활용하여 해외 시장 재무데이터를 수집하고 `ticker_fundamentals` 테이블에 저장하는 시스템 설계

### 1.2 Scope
| Region | Data Source | API Type | Authentication | Rate Limit |
|--------|-------------|----------|----------------|------------|
| US | SEC EDGAR | REST API | None (User-Agent required) | 10 req/sec |
| JP | EDINET API v2 | REST API | API Key (Free) | ~1 req/sec |

### 1.3 Data Coverage Target
- **US**: S&P 500 + Russell 1000 (~1,000 tickers)
- **JP**: TOPIX 500 + Nikkei 225 (~600 tickers)
- **Historical Depth**: 5년 (2020-2024) → CAGR 계산 가능

---

## 2. Architecture Overview

### 2.1 기존 Spock 아키텍처 이해

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         spock_refresh.py                                 │
│              (User-Friendly CLI - imports from orchestrators)           │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │ imports
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              modules/orchestration/orchestrator.py                       │
│                   DatabaseUpdateOrchestrator                            │
│        (Main Orchestrator - coordinates all update steps)               │
│                                                                          │
│  Steps: tickers → ohlcv → fundamentals → daily_valuation → ...          │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │ calls
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│modules/backfill/│  │ scripts/        │  │ modules/        │
│orchestrator.py  │  │ backfill_*.py   │  │ collection/     │
│BackfillOrches-  │  │ (Direct scripts)│  │ *_adapter.py    │
│trator (Gap-     │  │                 │  │                 │
│Aware Backfill)  │  │                 │  │                 │
└────────┬────────┘  └─────────────────┘  └─────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              modules/backfill/executor_base.py                           │
│                     BackfillExecutor (Abstract)                          │
│                                                                          │
│  Implementations:                                                        │
│  - EquityBackfillExecutor (equity_executor.py)                          │
│  - ListingDateBackfillExecutor (listing_date_executor.py)               │
│  - SECBackfillExecutor (sec_executor.py) ← 신규                          │
│  - EDINETBackfillExecutor (edinet_executor.py) ← 신규                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 신규 US/JP 통합 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────┐
│              modules/orchestration/orchestrator.py                       │
│                   DatabaseUpdateOrchestrator                            │
│                                                                          │
│  _update_fundamentals(regions):                                         │
│     if 'KR': → DARTFundamentalBackfiller (기존)                         │
│     if 'US': → SECBackfillExecutor (신규)                               │
│     if 'JP': → EDINETBackfillExecutor (신규)                            │
│     else:    → YFinanceFundamentalBackfiller (기존, 다른 리전)           │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
     ┌────────────────────────┼────────────────────────┐
     │                        │                        │
     ▼                        ▼                        ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ modules/     │      │ modules/     │      │ modules/     │
│ backfill/    │      │ backfill/    │      │ backfill/    │
│ equity_      │      │ sec_         │      │ edinet_      │
│ executor.py  │      │ executor.py  │      │ executor.py  │
│ (KR - 기존)  │      │ (US - 신규)  │      │ (JP - 신규)  │
└──────┬───────┘      └──────┬───────┘      └──────┬───────┘
       │                     │                     │
       ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ modules/     │      │ modules/     │      │ modules/     │
│ dart_api_    │      │ api_clients/ │      │ api_clients/ │
│ client.py    │      │ sec_edgar_   │      │ edinet_      │
│ (기존)        │      │ api.py       │      │ api.py       │
│              │      │ (신규)        │      │ (신규)        │
└──────┬───────┘      └──────┬───────┘      └──────┬───────┘
       │                     │                     │
       ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        ticker_fundamentals                               │
│              (PostgreSQL - 65+ columns unified schema)                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Gap-Aware Backfill 통합 (선택적)

BackfillOrchestrator를 활용한 gap-aware 백필도 지원:

```
┌─────────────────────────────────────────────────────────────────────────┐
│              modules/backfill/orchestrator.py                            │
│                     BackfillOrchestrator                                 │
│                                                                          │
│  _get_backfill_executor(backfill_type):                                 │
│     if 'equity':       → EquityBackfillExecutor (KR)                    │
│     if 'listing_date': → ListingDateBackfillExecutor                    │
│     if 'sec':          → SECBackfillExecutor (US) ← 신규                │
│     if 'edinet':       → EDINETBackfillExecutor (JP) ← 신규             │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. SEC EDGAR Integration (US Market)

### 3.1 API Specification
```yaml
Base URL: https://data.sec.gov
Endpoints:
  Company Facts: /api/xbrl/companyfacts/CIK{cik}.json
  Company Concept: /api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json
  Submissions: /cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=10-K&output=atom

Authentication:
  Type: None (API Key not required)
  User-Agent: Required (email address)

Rate Limit:
  Requests: 10/second
  Recommendation: 100ms delay between requests

Data Format:
  Primary: JSON (XBRL converted)
  Filing Types: 10-K (Annual), 10-Q (Quarterly)
```

### 3.2 CIK Mapping Strategy

SEC는 ticker가 아닌 CIK(Central Index Key)를 사용합니다. 매핑 전략:

```python
# Option 1: SEC Company Tickers JSON (Recommended)
# https://www.sec.gov/files/company_tickers.json

{
  "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
  "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
  ...
}

# Option 2: SEC EDGAR Full-Text Search
# https://efts.sec.gov/LATEST/search-index?q={ticker}&dateRange=custom&startdt=2024-01-01
```

### 3.3 Data Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  company_tickers │     │  companyfacts   │     │ ticker_         │
│  .json (SEC)    │ ──► │  API Response   │ ──► │ fundamentals    │
│ ticker→CIK map  │     │  XBRL→JSON      │     │ (PostgreSQL)    │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### 3.4 SEC API Client Design

```python
# modules/api_clients/sec_edgar_api.py

from typing import Dict, List, Optional
from datetime import date
import requests
import time
import logging

logger = logging.getLogger(__name__)


class SECEdgarApiClient:
    """SEC EDGAR API Client for US Financial Data"""

    BASE_URL = "https://data.sec.gov"
    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

    # XBRL US-GAAP Taxonomy Mappings
    XBRL_TAGS = {
        # Income Statement
        'revenue': ['Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax',
                   'SalesRevenueNet', 'RevenueFromContractWithCustomerIncludingAssessedTax'],
        'gross_profit': ['GrossProfit'],
        'operating_profit': ['OperatingIncomeLoss'],
        'net_income': ['NetIncomeLoss', 'ProfitLoss'],
        'ebitda': ['EarningsBeforeInterestTaxesDepreciationAndAmortization'],  # Often calculated

        # Balance Sheet
        'total_assets': ['Assets'],
        'total_liabilities': ['Liabilities'],
        'total_equity': ['StockholdersEquity', 'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],
        'current_assets': ['AssetsCurrent'],
        'current_liabilities': ['LiabilitiesCurrent'],
        'inventory': ['InventoryNet'],
        'pp_e': ['PropertyPlantAndEquipmentNet'],
        'accounts_receivable': ['AccountsReceivableNetCurrent'],

        # Cash Flow
        'operating_cash_flow': ['NetCashProvidedByUsedInOperatingActivities'],
        'investing_cf': ['NetCashProvidedByUsedInInvestingActivities'],
        'financing_cf': ['NetCashProvidedByUsedInFinancingActivities'],
        'capex': ['PaymentsToAcquirePropertyPlantAndEquipment'],

        # Per Share
        'trailing_eps': ['EarningsPerShareBasic', 'EarningsPerShareDiluted'],
        'shares_outstanding': ['CommonStockSharesOutstanding', 'WeightedAverageNumberOfSharesOutstandingBasic'],

        # Equity Breakdown
        'capital_stock': ['CommonStockValue'],
        'retained_earnings': ['RetainedEarningsAccumulatedDeficit'],
        'treasury_stock': ['TreasuryStockValue'],
    }

    def __init__(self, user_agent: str = "SpockQuantPlatform/1.0 (contact@example.com)",
                 rate_limit_delay: float = 0.1):
        """
        Initialize SEC EDGAR API Client

        Args:
            user_agent: Required by SEC (include contact email)
            rate_limit_delay: Delay between requests (default: 100ms)
        """
        self.user_agent = user_agent
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent,
            'Accept': 'application/json'
        })

        # CIK mapping cache
        self._cik_map: Optional[Dict[str, str]] = None

    def _load_cik_mapping(self) -> Dict[str, str]:
        """Load ticker → CIK mapping from SEC"""
        if self._cik_map is not None:
            return self._cik_map

        try:
            response = self.session.get(self.TICKERS_URL)
            response.raise_for_status()
            data = response.json()

            # Build ticker → CIK map (pad CIK to 10 digits)
            self._cik_map = {}
            for entry in data.values():
                ticker = entry['ticker'].upper()
                cik = str(entry['cik_str']).zfill(10)
                self._cik_map[ticker] = cik

            logger.info(f"Loaded {len(self._cik_map)} ticker→CIK mappings from SEC")
            return self._cik_map

        except Exception as e:
            logger.error(f"Failed to load CIK mapping: {e}")
            return {}

    def get_cik(self, ticker: str) -> Optional[str]:
        """Get CIK for a ticker symbol"""
        cik_map = self._load_cik_mapping()
        return cik_map.get(ticker.upper())

    def get_company_facts(self, cik: str) -> Optional[Dict]:
        """
        Get all XBRL facts for a company

        Returns comprehensive financial data including all historical filings
        """
        time.sleep(self.rate_limit_delay)

        url = f"{self.BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"CIK {cik} not found in SEC EDGAR")
            else:
                logger.error(f"SEC API error for CIK {cik}: {e}")
            return None

        except Exception as e:
            logger.error(f"Failed to fetch company facts for CIK {cik}: {e}")
            return None

    def get_historical_fundamentals(
        self,
        ticker: str,
        start_year: int = 2020,
        end_year: int = 2024,
        period_type: str = 'ANNUAL'  # ANNUAL or QUARTERLY
    ) -> List[Dict]:
        """
        Extract historical fundamental data from SEC EDGAR

        Args:
            ticker: US stock ticker (e.g., 'AAPL')
            start_year: Start year for historical data
            end_year: End year for historical data
            period_type: 'ANNUAL' (10-K) or 'QUARTERLY' (10-Q)

        Returns:
            List of dicts with annual/quarterly fundamental metrics
        """
        cik = self.get_cik(ticker)
        if not cik:
            logger.warning(f"No CIK found for ticker {ticker}")
            return []

        facts = self.get_company_facts(cik)
        if not facts:
            return []

        # Extract US-GAAP facts
        us_gaap = facts.get('facts', {}).get('us-gaap', {})

        # Build year→metrics mapping
        yearly_data = {}

        for metric_name, xbrl_tags in self.XBRL_TAGS.items():
            for tag in xbrl_tags:
                if tag not in us_gaap:
                    continue

                units = us_gaap[tag].get('units', {})

                # Try USD first, then shares
                values = units.get('USD', units.get('shares', []))

                for entry in values:
                    # Filter by form type (10-K for annual, 10-Q for quarterly)
                    form = entry.get('form', '')
                    if period_type == 'ANNUAL' and form != '10-K':
                        continue
                    if period_type == 'QUARTERLY' and form != '10-Q':
                        continue

                    # Extract fiscal year from end date
                    end_date = entry.get('end', '')
                    if not end_date:
                        continue

                    fiscal_year = int(end_date[:4])

                    if fiscal_year < start_year or fiscal_year > end_year:
                        continue

                    # Initialize year entry
                    if fiscal_year not in yearly_data:
                        yearly_data[fiscal_year] = {
                            'ticker': ticker,
                            'region': 'US',
                            'fiscal_year': fiscal_year,
                            'date': date(fiscal_year, 12, 31),  # Year-end date
                            'period_type': period_type,
                            'data_source': 'SEC_EDGAR'
                        }

                    # Store value (use latest filing for each year)
                    if metric_name not in yearly_data[fiscal_year] or \
                       entry.get('filed', '') > yearly_data[fiscal_year].get('_filed_date', ''):
                        yearly_data[fiscal_year][metric_name] = entry.get('val')
                        yearly_data[fiscal_year]['_filed_date'] = entry.get('filed', '')

                # Found data for this metric, skip remaining tags
                if any(metric_name in yd for yd in yearly_data.values()):
                    break

        # Clean up internal fields and calculate derived metrics
        result = []
        for year_data in sorted(yearly_data.values(), key=lambda x: x['fiscal_year']):
            year_data.pop('_filed_date', None)

            # Calculate FCF = Operating CF - CapEx
            ocf = year_data.get('operating_cash_flow')
            capex = year_data.get('capex')
            if ocf and capex:
                year_data['fcf'] = ocf - abs(capex)

            # Calculate EBITDA if not provided (simplified)
            if not year_data.get('ebitda'):
                op_profit = year_data.get('operating_profit')
                if op_profit:
                    # Note: Full EBITDA requires D&A which may not be available
                    year_data['ebitda'] = op_profit  # Placeholder

            result.append(year_data)

        logger.info(f"[{ticker}] Extracted {len(result)} years of SEC data ({start_year}-{end_year})")
        return result
```

### 3.5 SEC Backfiller Design

```python
# scripts/backfill_fundamentals_sec.py

class SECFundamentalBackfiller:
    """SEC EDGAR fundamental data backfill orchestrator for US market"""

    def __init__(
        self,
        db: PostgresDatabaseManager,
        sec: SECEdgarApiClient,
        dry_run: bool = False,
        rate_limit_delay: float = 0.1,
        start_year: int = 2020,
        end_year: int = 2024
    ):
        self.db = db
        self.sec = sec
        self.dry_run = dry_run
        self.rate_limit_delay = rate_limit_delay
        self.start_year = start_year
        self.end_year = end_year

        self.stats = {
            'tickers_processed': 0,
            'tickers_success': 0,
            'tickers_skipped_no_cik': 0,
            'tickers_skipped_no_data': 0,
            'tickers_failed': 0,
            'api_calls': 0,
            'records_inserted': 0,
            'records_updated': 0
        }

    def get_us_tickers_for_backfill(self, limit: Optional[int] = None) -> List[Dict]:
        """Query US tickers from database"""
        query = """
        SELECT DISTINCT t.ticker, t.name
        FROM tickers t
        WHERE t.region = 'US'
          AND t.asset_type = 'STOCK'
          AND t.is_active = TRUE
        ORDER BY t.ticker
        """
        if limit:
            query += f" LIMIT {limit}"

        return self.db.execute_query(query)

    def process_ticker(self, ticker_info: Dict) -> bool:
        """Process single US ticker"""
        ticker = ticker_info['ticker']

        # Fetch SEC EDGAR data
        metrics_list = self.sec.get_historical_fundamentals(
            ticker=ticker,
            start_year=self.start_year,
            end_year=self.end_year,
            period_type='ANNUAL'
        )

        if not metrics_list:
            self.stats['tickers_skipped_no_data'] += 1
            return False

        years_processed = 0
        for metrics in metrics_list:
            success = self.insert_or_update_fundamental_data(ticker, metrics)
            if success:
                years_processed += 1

        if years_processed > 0:
            self.stats['tickers_success'] += 1
            return True

        self.stats['tickers_failed'] += 1
        return False

    def insert_or_update_fundamental_data(self, ticker: str, metrics: Dict) -> bool:
        """UPSERT fundamental data to ticker_fundamentals table"""
        if self.dry_run:
            logger.info(f"[DRY RUN] Would insert/update {ticker} for {metrics.get('fiscal_year')}")
            return True

        try:
            query = """
            INSERT INTO ticker_fundamentals (
                ticker, region, date, period_type, fiscal_year, data_source,
                revenue, gross_profit, operating_profit, net_income, ebitda,
                total_assets, total_liabilities, total_equity,
                current_assets, current_liabilities, inventory, pp_e, accounts_receivable,
                operating_cash_flow, investing_cf, financing_cf, capex, fcf,
                trailing_eps, shares_outstanding,
                capital_stock, retained_earnings, treasury_stock,
                created_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                NOW()
            )
            ON CONFLICT (ticker, region, date, period_type)
            DO UPDATE SET
                revenue = EXCLUDED.revenue,
                gross_profit = EXCLUDED.gross_profit,
                operating_profit = EXCLUDED.operating_profit,
                net_income = EXCLUDED.net_income,
                ebitda = EXCLUDED.ebitda,
                total_assets = EXCLUDED.total_assets,
                total_liabilities = EXCLUDED.total_liabilities,
                total_equity = EXCLUDED.total_equity,
                current_assets = EXCLUDED.current_assets,
                current_liabilities = EXCLUDED.current_liabilities,
                inventory = EXCLUDED.inventory,
                pp_e = EXCLUDED.pp_e,
                accounts_receivable = EXCLUDED.accounts_receivable,
                operating_cash_flow = EXCLUDED.operating_cash_flow,
                investing_cf = EXCLUDED.investing_cf,
                financing_cf = EXCLUDED.financing_cf,
                capex = EXCLUDED.capex,
                fcf = EXCLUDED.fcf,
                trailing_eps = EXCLUDED.trailing_eps,
                shares_outstanding = EXCLUDED.shares_outstanding,
                capital_stock = EXCLUDED.capital_stock,
                retained_earnings = EXCLUDED.retained_earnings,
                treasury_stock = EXCLUDED.treasury_stock,
                data_source = EXCLUDED.data_source,
                last_updated = NOW()
            """

            params = (
                ticker, 'US', metrics['date'], metrics['period_type'],
                metrics['fiscal_year'], 'SEC_EDGAR',
                metrics.get('revenue'), metrics.get('gross_profit'),
                metrics.get('operating_profit'), metrics.get('net_income'),
                metrics.get('ebitda'),
                metrics.get('total_assets'), metrics.get('total_liabilities'),
                metrics.get('total_equity'),
                metrics.get('current_assets'), metrics.get('current_liabilities'),
                metrics.get('inventory'), metrics.get('pp_e'),
                metrics.get('accounts_receivable'),
                metrics.get('operating_cash_flow'), metrics.get('investing_cf'),
                metrics.get('financing_cf'), metrics.get('capex'), metrics.get('fcf'),
                metrics.get('trailing_eps'), metrics.get('shares_outstanding'),
                metrics.get('capital_stock'), metrics.get('retained_earnings'),
                metrics.get('treasury_stock')
            )

            self.db.execute_update(query, params)
            self.stats['records_inserted'] += 1
            return True

        except Exception as e:
            logger.error(f"[{ticker}] Database insert failed: {e}")
            return False
```

---

## 4. EDINET Integration (JP Market)

### 4.1 API Specification

```yaml
Base URL: https://api.edinet-fsa.go.jp/api/v2
Endpoints:
  Document List: /documents.json?date={YYYY-MM-DD}&type=2
  Document: /documents/{docID}?type=1  # ZIP with XBRL

Authentication:
  Type: API Key (Subscription-Key header)
  Registration: https://disclosure2.edinet-fsa.go.jp/
  Cost: Free

Rate Limit:
  Recommendation: 1 request/second

Data Format:
  Primary: XBRL (XML) in ZIP archive
  Alternative: CSV available for some documents
  Filing Types: 有価証券報告書 (Annual), 四半期報告書 (Quarterly)
```

### 4.2 EDINET Code Mapping Strategy

EDINET는 ticker가 아닌 EDINETコード(E+5digit)를 사용합니다:

```python
# Option 1: EDINET Code List (Monthly Update)
# https://disclosure2.edinet-fsa.go.jp/weee0010.aspx

# Option 2: Securities Code Mapping (証券コード)
# EDINET documents contain 証券コード which maps to ticker

# Example Mapping:
{
    "E00012": {"ticker": "7203", "name": "トヨタ自動車"},
    "E00015": {"ticker": "6758", "name": "ソニー"},
    ...
}
```

### 4.3 EDINET API Client Design

```python
# modules/api_clients/edinet_api.py

import zipfile
import io
from xml.etree import ElementTree
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
import requests
import time
import logging

logger = logging.getLogger(__name__)


class EDINETApiClient:
    """EDINET API Client for JP Financial Data"""

    BASE_URL = "https://api.edinet-fsa.go.jp/api/v2"

    # XBRL JP-GAAP/IFRS Taxonomy Mappings
    # Note: JP uses different namespaces (jpcrp, jppfs)
    XBRL_NAMESPACES = {
        'jpcrp': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jpcrp/2023-02-01/jpcrp_cor',
        'jppfs': 'http://disclosure.edinet-fsa.go.jp/taxonomy/jppfs/2023-02-01/jppfs_cor',
        'xbrli': 'http://www.xbrl.org/2003/instance',
    }

    XBRL_TAGS = {
        # Income Statement (損益計算書)
        'revenue': ['NetSales', 'OperatingRevenuesOrdinaryRevenuesAndNOIOrdinary'],
        'gross_profit': ['GrossProfit'],
        'operating_profit': ['OperatingIncome', 'OperatingProfit'],
        'net_income': ['ProfitLossAttributableToOwnersOfParent', 'ProfitLoss'],

        # Balance Sheet (貸借対照表)
        'total_assets': ['TotalAssets', 'Assets'],
        'total_liabilities': ['Liabilities'],
        'total_equity': ['NetAssets', 'Equity'],
        'current_assets': ['CurrentAssets'],
        'current_liabilities': ['CurrentLiabilities'],
        'inventory': ['Inventories'],
        'pp_e': ['PropertyPlantAndEquipment'],

        # Cash Flow (キャッシュフロー計算書)
        'operating_cash_flow': ['NetCashProvidedByUsedInOperatingActivities'],
        'investing_cf': ['NetCashProvidedByUsedInInvestingActivities'],
        'financing_cf': ['NetCashProvidedByUsedInFinancingActivities'],

        # Per Share (1株当たり)
        'trailing_eps': ['BasicEarningsLossPerShare'],
        'shares_outstanding': ['NumberOfIssuedSharesAsOfFilingDateCommonStock'],
    }

    def __init__(
        self,
        api_key: str,
        rate_limit_delay: float = 1.0
    ):
        """
        Initialize EDINET API Client

        Args:
            api_key: EDINET Subscription-Key
            rate_limit_delay: Delay between requests (default: 1 second)
        """
        self.api_key = api_key
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            'Subscription-Key': api_key,
            'Accept': 'application/json'
        })

        # EDINET code → ticker mapping cache
        self._edinet_map: Optional[Dict[str, str]] = None

    def get_document_list(
        self,
        target_date: date,
        doc_type: int = 2  # 2 = 有価証券報告書等
    ) -> List[Dict]:
        """
        Get list of documents submitted on a specific date

        Args:
            target_date: Target date (YYYY-MM-DD)
            doc_type: 1=メタデータ, 2=提出書類一覧

        Returns:
            List of document metadata
        """
        time.sleep(self.rate_limit_delay)

        url = f"{self.BASE_URL}/documents.json"
        params = {
            'date': target_date.strftime('%Y-%m-%d'),
            'type': doc_type
        }

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Filter for 有価証券報告書 (Annual Report)
            results = data.get('results', [])
            annual_reports = [
                doc for doc in results
                if doc.get('docTypeCode') == '120'  # 有価証券報告書
            ]

            return annual_reports

        except Exception as e:
            logger.error(f"Failed to get document list for {target_date}: {e}")
            return []

    def download_document(self, doc_id: str) -> Optional[bytes]:
        """
        Download document ZIP file

        Args:
            doc_id: Document ID (e.g., 'S100ABCD')

        Returns:
            ZIP file bytes or None
        """
        time.sleep(self.rate_limit_delay)

        url = f"{self.BASE_URL}/documents/{doc_id}"
        params = {'type': 1}  # 1 = 提出本文書及び監査報告書

        try:
            response = self.session.get(url, params=params, stream=True)
            response.raise_for_status()
            return response.content

        except Exception as e:
            logger.error(f"Failed to download document {doc_id}: {e}")
            return None

    def parse_xbrl_from_zip(self, zip_bytes: bytes) -> Optional[Dict]:
        """
        Parse XBRL data from ZIP archive

        Args:
            zip_bytes: ZIP file content as bytes

        Returns:
            Dict with extracted financial data
        """
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), 'r') as z:
                # Find XBRL instance file (typically *_ixbrl.htm or *.xbrl)
                xbrl_files = [
                    f for f in z.namelist()
                    if f.endswith('.xbrl') or ('ixbrl' in f.lower() and f.endswith('.htm'))
                ]

                if not xbrl_files:
                    logger.warning("No XBRL file found in ZIP")
                    return None

                # Read and parse the first XBRL file
                xbrl_content = z.read(xbrl_files[0])
                return self._parse_xbrl_content(xbrl_content)

        except Exception as e:
            logger.error(f"Failed to parse XBRL from ZIP: {e}")
            return None

    def _parse_xbrl_content(self, xbrl_content: bytes) -> Dict:
        """Parse XBRL XML content and extract financial data"""
        try:
            root = ElementTree.fromstring(xbrl_content)

            # Register namespaces
            for prefix, uri in self.XBRL_NAMESPACES.items():
                ElementTree.register_namespace(prefix, uri)

            extracted = {}

            # Extract each metric
            for metric_name, tags in self.XBRL_TAGS.items():
                for tag in tags:
                    # Search in different namespaces
                    for ns_prefix, ns_uri in self.XBRL_NAMESPACES.items():
                        element = root.find(f'.//{{{ns_uri}}}{tag}')
                        if element is not None and element.text:
                            try:
                                extracted[metric_name] = float(element.text.replace(',', ''))
                                break
                            except ValueError:
                                continue

                    if metric_name in extracted:
                        break

            return extracted

        except Exception as e:
            logger.error(f"Failed to parse XBRL content: {e}")
            return {}

    def get_historical_fundamentals(
        self,
        ticker: str,
        start_year: int = 2020,
        end_year: int = 2024
    ) -> List[Dict]:
        """
        Get historical fundamental data for a JP ticker

        This method searches for annual reports filed by the company
        and extracts financial data from each report.

        Args:
            ticker: JP stock ticker (4-digit, e.g., '7203')
            start_year: Start year
            end_year: End year

        Returns:
            List of annual fundamental data dicts
        """
        results = []

        # Search for annual reports in the date range
        # Annual reports are typically filed 3 months after fiscal year end
        for year in range(start_year, end_year + 1):
            # Most JP companies have March fiscal year end
            # 有価証券報告書 filed around June
            search_start = date(year, 4, 1)
            search_end = date(year, 7, 31)

            # Search each day for filings
            current_date = search_start
            while current_date <= search_end:
                documents = self.get_document_list(current_date)

                for doc in documents:
                    # Check if this is the company we're looking for
                    securities_code = doc.get('secCode', '')[:4]
                    if securities_code != ticker:
                        continue

                    # Download and parse the document
                    doc_id = doc.get('docID')
                    zip_content = self.download_document(doc_id)

                    if not zip_content:
                        continue

                    metrics = self.parse_xbrl_from_zip(zip_content)

                    if metrics:
                        metrics.update({
                            'ticker': ticker,
                            'region': 'JP',
                            'fiscal_year': year - 1,  # Report is for previous fiscal year
                            'date': date(year - 1, 3, 31),  # Assume March fiscal year end
                            'period_type': 'ANNUAL',
                            'data_source': 'EDINET',
                            'doc_id': doc_id
                        })
                        results.append(metrics)

                        # Found annual report for this year, move to next year
                        break

                if any(r['fiscal_year'] == year - 1 for r in results):
                    break

                current_date += timedelta(days=1)

        logger.info(f"[{ticker}] Extracted {len(results)} years of EDINET data")
        return results
```

### 4.4 EDINET Backfiller Design

```python
# scripts/backfill_fundamentals_edinet.py

class EDINETFundamentalBackfiller:
    """EDINET fundamental data backfill orchestrator for JP market"""

    def __init__(
        self,
        db: PostgresDatabaseManager,
        edinet: EDINETApiClient,
        dry_run: bool = False,
        start_year: int = 2020,
        end_year: int = 2024
    ):
        self.db = db
        self.edinet = edinet
        self.dry_run = dry_run
        self.start_year = start_year
        self.end_year = end_year

        self.stats = {
            'tickers_processed': 0,
            'tickers_success': 0,
            'tickers_skipped_no_data': 0,
            'tickers_failed': 0,
            'api_calls': 0,
            'records_inserted': 0
        }

    def get_jp_tickers_for_backfill(self, limit: Optional[int] = None) -> List[Dict]:
        """Query JP tickers from database"""
        query = """
        SELECT DISTINCT t.ticker, t.name
        FROM tickers t
        WHERE t.region = 'JP'
          AND t.asset_type = 'STOCK'
          AND t.is_active = TRUE
        ORDER BY t.ticker
        """
        if limit:
            query += f" LIMIT {limit}"

        return self.db.execute_query(query)

    def process_ticker(self, ticker_info: Dict) -> bool:
        """Process single JP ticker"""
        ticker = ticker_info['ticker']

        metrics_list = self.edinet.get_historical_fundamentals(
            ticker=ticker,
            start_year=self.start_year,
            end_year=self.end_year
        )

        if not metrics_list:
            self.stats['tickers_skipped_no_data'] += 1
            return False

        years_processed = 0
        for metrics in metrics_list:
            success = self.insert_or_update_fundamental_data(ticker, metrics)
            if success:
                years_processed += 1

        if years_processed > 0:
            self.stats['tickers_success'] += 1
            return True

        self.stats['tickers_failed'] += 1
        return False

    # insert_or_update_fundamental_data - similar to SEC backfiller
```

---

## 5. Data Mapping to ticker_fundamentals

### 5.1 Complete Column Mapping

| Column Name | SEC EDGAR (US-GAAP) | EDINET (JP-GAAP) | Notes |
|-------------|---------------------|------------------|-------|
| **Identity** | | | |
| ticker | From mapping | 証券コード | |
| region | 'US' | 'JP' | Hardcoded |
| date | Filing end date | 決算期末 | |
| period_type | '10-K' → 'ANNUAL' | '有報' → 'ANNUAL' | |
| fiscal_year | Extracted from date | 決算年度 | |
| data_source | 'SEC_EDGAR' | 'EDINET' | |
| **Income Statement** | | | |
| revenue | Revenues | NetSales | 매출액 |
| gross_profit | GrossProfit | GrossProfit | 매출총이익 |
| operating_profit | OperatingIncomeLoss | OperatingIncome | 영업이익 |
| net_income | NetIncomeLoss | ProfitLoss | 순이익 |
| ebitda | Calculated | Calculated | EBITDA |
| cogs | CostOfRevenue | CostOfSales | 매출원가 |
| sga_expense | SellingGeneralAdmin | SellingGeneralAdmin | 판관비 |
| **Balance Sheet** | | | |
| total_assets | Assets | TotalAssets | 총자산 |
| total_liabilities | Liabilities | Liabilities | 총부채 |
| total_equity | StockholdersEquity | NetAssets | 총자본 |
| current_assets | AssetsCurrent | CurrentAssets | 유동자산 |
| current_liabilities | LiabilitiesCurrent | CurrentLiabilities | 유동부채 |
| inventory | InventoryNet | Inventories | 재고자산 |
| pp_e | PropertyPlantEquipment | PPE | 유형자산 |
| accounts_receivable | AccountsReceivableNet | AccountsReceivable | 매출채권 |
| **Cash Flow** | | | |
| operating_cash_flow | CashFromOperations | OperatingCF | 영업활동CF |
| investing_cf | CashFromInvesting | InvestingCF | 투자활동CF |
| financing_cf | CashFromFinancing | FinancingCF | 재무활동CF |
| capex | PaymentsForPPE | CapitalExpenditure | 설비투자 |
| fcf | Calculated | Calculated | 잉여현금흐름 |
| **Equity Breakdown** | | | |
| capital_stock | CommonStockValue | CapitalStock | 자본금 |
| capital_surplus | AdditionalPaidIn | CapitalSurplus | 자본잉여금 |
| retained_earnings | RetainedEarnings | RetainedEarnings | 이익잉여금 |
| treasury_stock | TreasuryStock | TreasuryStock | 자기주식 |
| **Per Share** | | | |
| trailing_eps | EarningsPerShareBasic | BasicEPS | EPS |
| shares_outstanding | SharesOutstanding | IssuedShares | 발행주식수 |

### 5.2 Currency Considerations

| Region | Currency | Conversion Required |
|--------|----------|---------------------|
| US | USD | No - Store as-is |
| JP | JPY | No - Store as-is |

**Note**: 통화 변환 없이 원시 값을 저장합니다. CAGR 계산은 동일 통화 내에서 수행되므로 문제없습니다.

---

## 6. Integration with Orchestrators

### 6.1 DatabaseUpdateOrchestrator 통합

`modules/orchestration/orchestrator.py`의 `_update_fundamentals` 메서드 수정:

```python
# modules/orchestration/orchestrator.py

def _update_fundamentals(self, regions: List[str], **kwargs) -> Dict:
    """Update fundamental data for all regions"""
    logger.info("🔄 Updating fundamental data...")

    results = {}

    for region in regions:
        if region == 'KR':
            # 기존: DART API for KR market
            from scripts.backfill_fundamentals_dart import DARTFundamentalBackfiller
            from modules.dart_api_client import DARTApiClient
            # ... (기존 코드 유지)

        elif region == 'US':
            # 신규: SEC EDGAR for US market
            try:
                from modules.backfill.sec_executor import SECBackfillExecutor

                executor = SECBackfillExecutor(
                    db=self.db,
                    dry_run=kwargs.get('dry_run', False)
                )

                # Validate prerequisites
                is_ready, issues = executor.validate_prerequisites()
                if not is_ready:
                    logger.error(f"  ❌ [{region}] Prerequisites failed: {issues}")
                    results[region] = {'success': False, 'error': str(issues)}
                    continue

                # Get tickers and execute backfill
                result = executor.run_backfill(
                    start_year=kwargs.get('start_year', 2020),
                    end_year=kwargs.get('end_year', 2024),
                    limit=self.config.get('limit')
                )

                results[region] = result
                logger.info(
                    f"  ✅ [{region}] {result.get('tickers_success', 0)} success, "
                    f"{result.get('tickers_failed', 0)} failed"
                )

            except Exception as e:
                logger.error(f"  ❌ [{region}] Failed: {e}")
                results[region] = {'success': False, 'error': str(e)}

        elif region == 'JP':
            # 신규: EDINET for JP market
            try:
                from modules.backfill.edinet_executor import EDINETBackfillExecutor

                executor = EDINETBackfillExecutor(
                    db=self.db,
                    dry_run=kwargs.get('dry_run', False)
                )

                is_ready, issues = executor.validate_prerequisites()
                if not is_ready:
                    logger.error(f"  ❌ [{region}] Prerequisites failed: {issues}")
                    results[region] = {'success': False, 'error': str(issues)}
                    continue

                result = executor.run_backfill(
                    start_year=kwargs.get('start_year', 2020),
                    end_year=kwargs.get('end_year', 2024),
                    limit=self.config.get('limit')
                )

                results[region] = result
                logger.info(
                    f"  ✅ [{region}] {result.get('tickers_success', 0)} success, "
                    f"{result.get('tickers_failed', 0)} failed"
                )

            except Exception as e:
                logger.error(f"  ❌ [{region}] Failed: {e}")
                results[region] = {'success': False, 'error': str(e)}

        else:
            # 기존: yfinance for other overseas markets (HK, CN, VN)
            from scripts.backfill_fundamentals_yfinance import YFinanceFundamentalBackfiller
            # ... (기존 코드 유지)

    return results
```

### 6.2 BackfillOrchestrator 통합 (Gap-Aware)

`modules/backfill/orchestrator.py`의 `_get_backfill_executor` 메서드 수정:

```python
# modules/backfill/orchestrator.py

def _get_backfill_executor(
    self,
    backfill_type: str
) -> BackfillExecutor:
    """
    Get appropriate backfill executor for type (Factory Pattern)
    """
    if backfill_type in ('equity', 'fundamentals'):
        from modules.backfill.equity_executor import EquityBackfillExecutor
        return EquityBackfillExecutor(self.db, dry_run=self.dry_run)

    elif backfill_type == 'listing_date':
        from modules.backfill.listing_date_executor import ListingDateBackfillExecutor
        return ListingDateBackfillExecutor(self.db, dry_run=self.dry_run)

    # 신규: SEC (US) Executor
    elif backfill_type == 'sec':
        from modules.backfill.sec_executor import SECBackfillExecutor
        return SECBackfillExecutor(self.db, dry_run=self.dry_run)

    # 신규: EDINET (JP) Executor
    elif backfill_type == 'edinet':
        from modules.backfill.edinet_executor import EDINETBackfillExecutor
        return EDINETBackfillExecutor(self.db, dry_run=self.dry_run)

    else:
        raise ValueError(
            f"Unknown backfill type: {backfill_type}. "
            f"Supported types: equity, fundamentals, listing_date, sec, edinet"
        )
```

### 6.3 spock_refresh.py 통합 (CLI 메뉴)

`spock_refresh.py`는 단순히 메뉴 옵션만 추가하고, 실제 작업은 오케스트레이터에 위임:

```python
# spock_refresh.py (CLI 메뉴 추가)

def run_fundamentals_menu():
    """Fundamentals backfill submenu"""
    print(f"\n{colored('📊 Fundamentals Backfill Options:', Fore.CYAN)}")
    print(f"  1. 🇰🇷 KR (DART)")
    print(f"  2. 🇺🇸 US (SEC EDGAR) ← 신규")
    print(f"  3. 🇯🇵 JP (EDINET) ← 신규")
    print(f"  4. 🌍 All (KR + US + JP)")
    print(f"  0. Back to main menu")

    choice = input("Select: ").strip()

    if choice == '1':
        regions = ['KR']
    elif choice == '2':
        regions = ['US']
    elif choice == '3':
        regions = ['JP']
    elif choice == '4':
        regions = ['KR', 'US', 'JP']
    else:
        return

    # 실제 작업은 DatabaseUpdateOrchestrator에 위임
    from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator
    orchestrator = DatabaseUpdateOrchestrator(db, config={})
    result = orchestrator._update_fundamentals(regions, dry_run=False)
    print(f"Result: {result}")
```

---

## 7. File Structure

```
modules/
   api_clients/
      sec_edgar_api.py          # SEC EDGAR API client (신규)
      edinet_api.py             # EDINET API client (신규)
      dart_api_client.py        # DART API client (기존)
      yfinance_api.py           # yfinance wrapper (기존)

scripts/
   backfill_fundamentals_sec.py     # SEC backfiller (신규)
   backfill_fundamentals_edinet.py  # EDINET backfiller (신규)
   backfill_fundamentals_dart.py    # DART backfiller (기존)
   backfill_fundamentals_yfinance.py # yfinance backfiller (기존)

config/
   data_sources.yaml           # API configuration (신규)
   xbrl_mappings/
      us_gaap_mapping.json     # US XBRL tag mappings
      jp_gaap_mapping.json     # JP XBRL tag mappings
```

---

## 8. Environment Variables

```bash
# .env 추가 항목

# SEC EDGAR (US)
SEC_USER_AGENT="SpockQuantPlatform/1.0 (your-email@example.com)"
SEC_RATE_LIMIT_DELAY=0.1  # 100ms between requests

# EDINET (JP)
EDINET_API_KEY="your-edinet-subscription-key"
EDINET_RATE_LIMIT_DELAY=1.0  # 1 second between requests
```

---

## 9. Implementation Phases

### Phase 1: SEC EDGAR (US) - Week 1-2
1. **Day 1-2**: `SECEdgarApiClient` 구현
   - CIK 매핑 로드
   - Company Facts API 호출
   - XBRL 파싱 로직
2. **Day 3-4**: `SECFundamentalBackfiller` 구현
   - DART 패턴 기반 백필러
   - UPSERT 로직
3. **Day 5**: 테스트 및 검증
   - S&P 500 상위 10개 종목 테스트
   - 데이터 정합성 검증

### Phase 2: EDINET (JP) - Week 3-4
1. **Day 1-2**: `EDINETApiClient` 구현
   - API 키 등록 및 설정
   - 문서 목록 조회
   - XBRL ZIP 다운로드 및 파싱
2. **Day 3-4**: `EDINETFundamentalBackfiller` 구현
   - 일본어 XBRL 태그 매핑
   - 회계연도 처리 (3월 결산)
3. **Day 5**: 테스트 및 검증
   - TOPIX 상위 10개 종목 테스트
   - 데이터 정합성 검증

### Phase 3: Integration - Week 5
1. **Day 1-2**: `spock_refresh.py` 통합
2. **Day 3**: CAGR 도구 테스트 (US/JP 지원 확인)
3. **Day 4-5**: 문서화 및 운영 가이드

---

## 10. Success Criteria

| Metric | Target |
|--------|--------|
| US Coverage | >500 tickers (S&P 500) |
| JP Coverage | >400 tickers (TOPIX 500) |
| Historical Depth | 5년 (2020-2024) |
| CAGR Calculation | US/JP 리전 지원 |
| Data Accuracy | >95% (샘플 검증) |
| API Rate Limit | No throttling errors |

---

## 11. Risk Mitigation

| Risk | Mitigation |
|------|------------|
| SEC rate limiting | 100ms delay + exponential backoff |
| EDINET XBRL parsing complexity | Fallback to CSV when available |
| Missing historical data | Document gap and skip gracefully |
| Currency confusion | Store raw values, note currency in metadata |
| XBRL taxonomy changes | Version-aware tag mappings in config |

---

**Document Version**: 1.0
**Created**: 2025-11-26
**Author**: Quant Investment Platform
**Status**: Design Complete - Ready for Implementation
