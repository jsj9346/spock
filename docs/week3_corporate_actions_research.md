# Week 3: Corporate Actions Data Sources Research

**Date**: 2025-10-27
**Purpose**: Identify data sources for stock splits, dividends, and rights issues beyond pykrx
**Status**: ✅ Research Complete

---

## Executive Summary

**Current Gap**: `pykrx` library provides dividend data but lacks stock splits and rights issues
**Solution**: Use DART (전자공시) OpenAPI with `OpenDartReader` Python library for comprehensive corporate actions
**Recommendation**: Implement DART as primary source with KRX data.krx.co.kr as backup

---

## Data Source Comparison

| Source | Dividends | Stock Splits | Rights Issues | API Available | Cost | Authentication |
|--------|-----------|--------------|---------------|---------------|------|----------------|
| **pykrx** | ✅ | ❌ | ❌ | Python Library | Free | None |
| **DART (OpenDartReader)** | ✅ | ✅ | ✅ | Python Library | Free | API Key Required |
| **KRX data.krx.co.kr** | ✅ | ✅ | ✅ | Web + API | Free | Registration + Contract |
| **Naver Finance** | ✅ | ✅ | ⚠️ | No Official API | Free | Web Scraping Only |
| **KIND (kind.krx.co.kr)** | ✅ | ✅ | ✅ | Web Interface | Free | None |

**Legend**:
- ✅ = Fully Supported
- ⚠️ = Partial/Unofficial
- ❌ = Not Available

---

## 1. DART (전자공시) OpenAPI - **RECOMMENDED**

### Overview
Korea Financial Supervisory Service's electronic disclosure system providing comprehensive corporate action data through Open DART API.

### Why DART is Recommended
1. **Complete Coverage**: All corporate actions from listed companies
2. **Official Source**: Government-operated financial disclosure system
3. **Free Access**: No cost with API key registration
4. **Python Library**: `OpenDartReader` simplifies integration
5. **Historical Data**: Complete disclosure archives since company listing
6. **Structured Data**: JSON/XML format with consistent schema

### Available Corporate Actions Data

**Dividends (배당)**:
- Cash dividends
- Stock dividends
- Dividend dates and amounts
- Dividend ratios
- Historical dividend records

**Capital Increases (증자)**:
- Paid-in capital increase (유상증자)
- Bonus shares/Free capital increase (무상증자)
- Combined capital increase (유무상증자)
- Rights issue details
- Subscription dates and ratios

**Stock Splits & Consolidations**:
- Stock split announcements (분할)
- Stock consolidation (병합)
- Split ratios and effective dates

**Other Corporate Actions**:
- Capital reduction (감자)
- Share exchanges (주식교환)
- Mergers and acquisitions
- Treasury stock operations (자기주식)

### OpenDartReader Implementation

#### Installation
```bash
pip install OpenDartReader
```

#### API Key Registration
1. Visit https://opendart.fss.or.kr/
2. Create account
3. Apply for API key (instant approval)
4. Copy API key to `.env` file

#### Basic Usage Examples

```python
import OpenDartReader

# Initialize with API key
dart = OpenDartReader(api_key='your_api_key_here')

# 1. Get dividend information
# Samsung Electronics (005930), dividends, 2023
dividends = dart.report('005930', '배당', 2023)

# 2. Get capital increase events
# Paid-in capital increases for Samsung Electronics
capital_increases = dart.event('005930', '유상증자')

# 3. Get stock split information from registration statements
splits = dart.regstate('005930', '분할', start='2020-01-01', end='2024-12-31')

# 4. Get bonus shares (free capital increase)
bonus_shares = dart.event('005930', '무상증자')

# 5. Get capital reduction events
capital_reductions = dart.event('005930', '감자')

# 6. Get all corporate events for date range
all_events = dart.list('005930', start='2023-01-01', end='2023-12-31')
```

#### Corporate Actions Data Structure

**Dividend Data Response** (`dart.report()`):
```python
{
    'rcept_no': '공시접수번호',
    'corp_name': '회사명',
    'se': '구분(결산/분기)',
    'stock_knd': '주식종류',
    'thstrm': '당기',
    'frmtrm': '전기',
    'lwfr': '전전기',
    # Dividend amounts per share
    'cash_div_per': '현금배당금액',
    'stk_div_per': '주식배당금액',
    # Dividend ratios
    'cash_div_rate': '현금배당률',
    'stk_div_rate': '주식배당률'
}
```

**Capital Increase Data Response** (`dart.event()`):
```python
{
    'rcept_no': '공시접수번호',
    'corp_name': '회사명',
    'dcm_no': '문서번호',
    'report_nm': '보고서명',
    'rcept_dt': '접수일자',
    # Capital increase details
    'isu_dcrs_de': '증자일자',
    'isu_dcrs_stle': '증자방식',
    'isu_dcrs_stock_knd': '증자주식종류',
    'isu_dcrs_qy': '증자수량',
    'isu_dcrs_mstvdv_fval_amount': '증자후액면가액'
}
```

**Stock Split Data Response** (`dart.regstate()`):
```python
{
    'rcept_no': '공시접수번호',
    'corp_name': '회사명',
    'report_nm': '보고서명',
    'flr_nm': '제출인',
    'rcept_dt': '접수일자',
    # Split information extracted from registration statement
    'rm': '비고(분할비율 등 상세정보)'
}
```

### Integration with Week 3 Collection Script

Modify `scripts/week3_collect_corporate_actions.py`:

```python
import OpenDartReader
from datetime import datetime

def collect_dart_corporate_actions(ticker: str, start_date: str, end_date: str):
    """
    Collect corporate actions from DART

    Args:
        ticker: 6-digit stock code (e.g., '005930')
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        dict: Corporate actions data
    """
    dart = OpenDartReader(os.getenv('DART_API_KEY'))

    corporate_actions = {
        'dividends': [],
        'stock_splits': [],
        'bonus_shares': [],
        'rights_issues': [],
        'capital_reductions': []
    }

    # Collect dividends
    years = range(int(start_date[:4]), int(end_date[:4]) + 1)
    for year in years:
        try:
            div_data = dart.report(ticker, '배당', year)
            if div_data is not None and len(div_data) > 0:
                corporate_actions['dividends'].extend(div_data.to_dict('records'))
        except Exception as e:
            logger.warning(f"Failed to get dividends for {year}: {e}")

    # Collect capital increases (rights issues)
    try:
        capital_inc = dart.event(ticker, '유상증자', start=start_date, end=end_date)
        if capital_inc is not None and len(capital_inc) > 0:
            corporate_actions['rights_issues'].extend(capital_inc.to_dict('records'))
    except Exception as e:
        logger.warning(f"Failed to get capital increases: {e}")

    # Collect bonus shares (free capital increase)
    try:
        bonus = dart.event(ticker, '무상증자', start=start_date, end=end_date)
        if bonus is not None and len(bonus) > 0:
            corporate_actions['bonus_shares'].extend(bonus.to_dict('records'))
    except Exception as e:
        logger.warning(f"Failed to get bonus shares: {e}")

    # Collect stock splits
    try:
        splits = dart.regstate(ticker, '분할', start=start_date, end=end_date)
        if splits is not None and len(splits) > 0:
            corporate_actions['stock_splits'].extend(splits.to_dict('records'))
    except Exception as e:
        logger.warning(f"Failed to get stock splits: {e}")

    # Collect capital reductions
    try:
        reductions = dart.event(ticker, '감자', start=start_date, end=end_date)
        if reductions is not None and len(reductions) > 0:
            corporate_actions['capital_reductions'].extend(reductions.to_dict('records'))
    except Exception as e:
        logger.warning(f"Failed to get capital reductions: {e}")

    return corporate_actions
```

### Environment Configuration

Add to `.env`:
```bash
# DART API Key (https://opendart.fss.or.kr/)
DART_API_KEY=your_dart_api_key_here
```

### Rate Limits & Best Practices

**DART API Rate Limits**:
- No official rate limit published
- Recommended: 1 request per second (conservative)
- Batch requests where possible
- Use date range filters to reduce data volume

**Error Handling**:
```python
import time
from requests.exceptions import HTTPError

def safe_dart_request(func, max_retries=3, delay=1.0):
    """Wrapper for DART API calls with retry logic"""
    for attempt in range(max_retries):
        try:
            return func()
        except HTTPError as e:
            if e.response.status_code == 429:  # Too many requests
                wait_time = delay * (2 ** attempt)
                logger.warning(f"Rate limit hit, waiting {wait_time}s")
                time.sleep(wait_time)
            else:
                raise
        except Exception as e:
            logger.error(f"DART request failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise
    return None
```

---

## 2. KRX 정보데이터시스템 (data.krx.co.kr) - Backup

### Overview
Official Korea Exchange data platform providing market data and corporate action information.

### Access Requirements
1. **Registration**: Create account at https://data.krx.co.kr/
2. **Application**: Apply for data usage approval
3. **Contract**: Sign agreement with KOSCOM (KRX technology provider)
4. **API Access**: Obtain API credentials after approval

### Pros
- Official exchange data
- Real-time updates
- Comprehensive market statistics
- High data quality

### Cons
- Complex approval process (days to weeks)
- Formal contract required
- API documentation primarily in Korean
- May require commercial agreement for API access

### Usage Recommendation
**Fallback Option**: Use if DART data is incomplete or additional validation needed

---

## 3. KIND (Korea Investors Network for Disclosure) - Manual Backup

### Overview
Web-based disclosure platform (https://kind.krx.co.kr/) operated by Korea Exchange.

### Available Data
- Stock splits and consolidations
- Capital increases and reductions
- Dividend announcements
- Rights offerings
- Merger and acquisition notices

### Access Method
**Web Interface Only** - No official API

**Manual Collection Process**:
1. Visit https://kind.krx.co.kr/disclosure/todaydisclosure.do
2. Search by ticker or company name
3. Filter by disclosure type (증자, 배당, 분할 등)
4. Download PDF or HTML disclosure documents
5. Extract relevant data manually or via parsing

### Pros
- No registration required
- Complete disclosure archives
- Official source
- Free access

### Cons
- No API (web scraping required)
- Manual data extraction
- Not suitable for automated batch processing
- PDF parsing complexity

### Usage Recommendation
**Last Resort**: Manual validation or filling data gaps when automated sources fail

---

## 4. Naver Finance - Not Recommended

### Overview
Naver provides comprehensive stock information but **no official API**.

### Limitations
1. **No Official API**: Must use web scraping
2. **Legal Risk**: Terms of service may prohibit automated scraping
3. **Data Reliability**: No guarantee of data accuracy or completeness
4. **Fragile**: Website changes break scrapers
5. **Rate Limiting**: IP blocking on excessive requests

### Adjusted Close Price Availability
Naver Finance provides adjusted close prices that account for:
- Stock splits
- Dividends
- Capital increases

**Access Method** (Unofficial):
```python
import pandas as pd

# Example: Get adjusted prices (web scraping - not recommended)
url = f"https://finance.naver.com/item/sise_day.nhn?code={ticker}"
df = pd.read_html(url, encoding='cp949')[0]
# Adjusted prices include corporate action adjustments
```

### Usage Recommendation
**Not Recommended** - Legal and technical risks outweigh benefits

---

## Implementation Roadmap

### Phase 1: DART Integration (Week 3) ✅ Current
1. **Register for DART API Key**
   - Visit https://opendart.fss.or.kr/
   - Complete registration (5 minutes)
   - Obtain API key

2. **Install OpenDartReader**
   ```bash
   pip install OpenDartReader
   ```

3. **Update Environment Configuration**
   ```bash
   # Add to .env
   DART_API_KEY=your_api_key_here
   ```

4. **Modify `week3_collect_corporate_actions.py`**
   - Add DART collection methods
   - Implement error handling and rate limiting
   - Test with 5 sample tickers

5. **Validate Data Quality**
   - Compare DART dividends with pykrx
   - Verify stock split data completeness
   - Check data consistency across sources

### Phase 2: Database Schema Update (Week 3)
1. **Extend `corporate_actions` Table**
   ```sql
   ALTER TABLE corporate_actions
   ADD COLUMN dart_receipt_no VARCHAR(20),  -- DART 공시접수번호
   ADD COLUMN dart_report_name TEXT,         -- 보고서명
   ADD COLUMN event_details JSONB,           -- Event-specific JSON data
   ADD COLUMN data_source VARCHAR(20);       -- 'DART', 'pykrx', 'manual'
   ```

2. **Create Indexes**
   ```sql
   CREATE INDEX idx_corporate_actions_dart ON corporate_actions(dart_receipt_no);
   CREATE INDEX idx_corporate_actions_source ON corporate_actions(data_source);
   ```

### Phase 3: Price Adjustment Enhancement (Week 3)
1. **Integrate DART Split Data**
   - Parse split ratios from DART
   - Calculate adjustment factors
   - Apply backward price adjustments

2. **Validate Adjusted Prices**
   - Compare with Naver Finance adjusted prices
   - Verify split factor calculations
   - Check dividend adjustments

3. **Quality Assurance**
   - Test with known corporate action dates
   - Verify price continuity before/after splits
   - Validate total return calculations

### Phase 4: Fallback Mechanism (Week 4)
1. **Implement KRX Backup**
   - Register for KRX data access
   - Implement fallback logic for DART failures
   - Log data source for each record

2. **Manual CSV Template** (Emergency Backup)
   ```csv
   ticker,action_type,ex_date,record_date,payment_date,ratio,amount,notes
   005930,SPLIT,2018-05-04,2018-05-03,,50:1,,50주 분할
   005930,DIVIDEND,2023-03-31,2023-03-31,2023-04-14,,361,현금배당
   ```

---

## Data Quality Validation Checklist

Before proceeding to Week 4 backtesting, verify:

- [ ] DART API key registered and tested
- [ ] OpenDartReader installed and configured
- [ ] Dividend data collected for all 350 tickers
- [ ] Stock split events identified and recorded
- [ ] Rights issue/bonus share data complete
- [ ] Capital reduction events captured
- [ ] Data consistency validated across sources
- [ ] Database schema updated with DART fields
- [ ] Price adjustment script updated for splits
- [ ] Adjusted prices validated against reference data
- [ ] Corporate actions documentation complete
- [ ] Fallback mechanism tested

---

## Cost-Benefit Analysis

| Factor | DART | KRX data.krx.co.kr | Naver (Scraping) |
|--------|------|-------------------|------------------|
| **Implementation Time** | 2 hours | 1-2 weeks | 4-8 hours |
| **Ongoing Maintenance** | Low | Medium | High |
| **Data Quality** | High | High | Medium |
| **Legal Risk** | None | None | High |
| **API Stability** | High | High | N/A |
| **Cost** | Free | Free* | Free |
| **Recommended** | ✅ Yes | ⚠️ Backup | ❌ No |

*May require commercial agreement for high-volume API access

---

## Recommended Next Steps

1. **Immediate (Today)**:
   - ✅ Register DART API key
   - ✅ Install OpenDartReader
   - ✅ Test with Samsung Electronics (005930)

2. **After Backfill Complete**:
   - Run DART corporate actions collection for all 350 tickers
   - Validate data against pykrx dividend data
   - Update price adjustment script with stock splits

3. **Week 4 Preparation**:
   - Verify adjusted prices using split/dividend factors
   - Compare with external reference (Naver adjusted prices)
   - Document corporate action dates for backtesting exclusions

---

## References

### Official Documentation
- **DART OpenAPI**: https://opendart.fss.or.kr/
- **OpenDartReader GitHub**: https://github.com/FinanceData/OpenDartReader
- **KRX 정보데이터시스템**: https://data.krx.co.kr/
- **KIND 공시시스템**: https://kind.krx.co.kr/

### Python Libraries
- **OpenDartReader**: `pip install OpenDartReader`
- **pykrx**: `pip install pykrx` (existing)

### Related Documentation
- [week3_collect_corporate_actions.py](../scripts/week3_collect_corporate_actions.py)
- [week3_adjust_prices.py](../scripts/week3_adjust_prices.py)
- [QUANT_DATABASE_SCHEMA.md](QUANT_DATABASE_SCHEMA.md)

---

**Research Status**: ✅ Complete
**Implementation Status**: 🔄 Ready for execution after backfill
**Next Action**: Register DART API key and test collection script

