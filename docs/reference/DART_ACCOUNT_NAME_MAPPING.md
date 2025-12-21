# DART API Account Name Mapping Guide

**API Endpoint**: `fnlttSinglAcntAll.json` (ALL Account Items API)

**Purpose**: Map Phase 2 financial statement columns to actual DART API account names (계정명)

**Status**: Based on Samsung Electronics (005930) 2023 Annual Report Analysis

---

## Phase 2 Field Mapping (18 Columns)

### 1. Manufacturing Industry Indicators (6 columns)

| DB Column | Target Korean Name | Actual DART Name | Status | Notes |
|-----------|-------------------|------------------|--------|-------|
| `cogs` | 매출원가 | **영업수익** - **매출원가** | ✅ EXISTS | Use calculation: Revenue - COGS |
| `gross_profit` | 매출총이익 | **매출총이익** | ✅ EXISTS | Direct field available |
| `pp_e` | 유형자산 | **유형자산** | ✅ EXISTS | Direct field available |
| `depreciation` | 감가상각비 | ❌ NOT AVAILABLE | ⚠️ MISSING | Use cash flow calculation (see below) |
| `accounts_receivable` | 매출채권 | **매출채권** | ✅ EXISTS | Direct field available |
| `accumulated_depreciation` | 감가상각누계액 | ❌ NOT AVAILABLE | ⚠️ MISSING | Not disclosed separately |

**Depreciation Calculation Workaround**:
```python
# Method 1: Operating Cash Flow Adjustment (most accurate)
depreciation = operating_profit - operating_cash_flow + working_capital_change

# Method 2: PP&E Change Analysis (approximation)
depreciation = (pp_e_prev_year - pp_e_curr_year) + pp_e_acquisitions - pp_e_disposals

# Available DART fields for Method 2:
# - 유형자산의 취득 (PP&E Acquisitions)
# - 유형자산의 처분 (PP&E Disposals)
```

---

### 2. Retail/E-Commerce Industry Indicators (3 columns)

| DB Column | Target Korean Name | Actual DART Name | Status | Notes |
|-----------|-------------------|------------------|--------|-------|
| `sga_expense` | 판매비와관리비 | **판매비와관리비** | ✅ EXISTS | Direct field available |
| `rd_expense` | 연구개발비 | ❌ NOT AVAILABLE | ⚠️ MISSING | Included in SG&A, not broken out |
| `operating_expense` | 영업비용 | (**매출원가** + **판매비와관리비**) | ✅ CALCULATED | Sum of COGS + SG&A |

**R&D Expense Workaround**:
```python
# Most companies do NOT disclose R&D separately in financial statements
# R&D is typically included in SG&A (판매비와관리비)
#
# Options:
# 1. Use SG&A as proxy for operating expenses (conservative)
# 2. Check company's business report (사업보고서) for R&D disclosure
# 3. Set to NULL/0 if not available
rd_expense = None  # or 0
```

---

### 3. Financial Industry Indicators (5 columns)

| DB Column | Target Korean Name | Actual DART Name | Status | Notes |
|-----------|-------------------|------------------|--------|-------|
| `interest_income` | 이자수익 | **이자의 수취** OR **금융수익** | ✅ PARTIAL | Cash flow vs. accrual basis |
| `interest_expense` | 이자비용 | **이자의 지급** OR **금융비용** | ✅ PARTIAL | Cash flow vs. accrual basis |
| `loan_portfolio` | 대출금 | ❌ NOT AVAILABLE | ⚠️ N/A | Only for banks/financial companies |
| `npl_amount` | 부실채권 OR 고정이하여신 | ❌ NOT AVAILABLE | ⚠️ N/A | Only for banks/financial companies |
| `nim` | 순이자마진 | ❌ NOT AVAILABLE | ⚠️ N/A | Only for banks/financial companies |

**Interest Income/Expense Options**:

**Option A: Cash Flow Basis** (Direct from DART)
```python
interest_income = item_lookup.get('이자의 수취', 0)     # Interest received (cash)
interest_expense = item_lookup.get('이자의 지급', 0)    # Interest paid (cash)
```

**Option B: Accrual Basis** (Broader financial income/expense)
```python
interest_income = item_lookup.get('금융수익', 0)        # Financial income (accrual)
interest_expense = item_lookup.get('금융비용', 0)       # Financial expense (accrual)
```

**Recommendation**: Use **Option B (Accrual Basis)** for consistency with other financial metrics.

**Financial Industry Fields**: Only applicable to banks, insurance companies, securities firms. For manufacturing/tech companies, set to NULL/0.

---

### 4. Common Indicators (4 columns)

| DB Column | Target Korean Name | Actual DART Name | Status | Notes |
|-----------|-------------------|------------------|--------|-------|
| `investing_cf` | 투자활동현금흐름 | **투자활동현금흐름** | ✅ EXISTS | Direct field available |
| `financing_cf` | 재무활동현금흐름 | **재무활동현금흐름** | ✅ EXISTS | Direct field available |
| `ebitda` | 상각전영업이익 | (**영업이익** + **감가상각비**) | ⚠️ PARTIAL | Depreciation not available |
| `ebitda_margin` | EBITDA 마진 | (EBITDA / **영업수익** * 100) | ⚠️ PARTIAL | Depreciation not available |

**EBITDA Calculation**:
```python
# Standard formula
operating_profit = item_lookup.get('영업이익', 0)
depreciation = item_lookup.get('감가상각비', 0)  # Usually NOT available
ebitda = operating_profit + depreciation

# Since depreciation is NOT separately disclosed:
# Option 1: Use operating profit as proxy (conservative)
ebitda = operating_profit

# Option 2: Estimate depreciation from cash flow statement
operating_cf = item_lookup.get('영업활동현금흐름', 0)
working_capital_change = item_lookup.get('영업활동으로 인한 자산부채의 변동', 0)
depreciation_estimate = operating_cf - operating_profit - working_capital_change
ebitda = operating_profit + depreciation_estimate

# Recommendation: Use Option 2 for better accuracy
```

---

## Core Financial Statement Fields (Phase 1)

These fields are available in `fnlttSinglAcntAll.json` response:

| DB Column | Target Korean Name | Actual DART Name | Status |
|-----------|-------------------|------------------|--------|
| `revenue` | 매출액 | **영업수익** | ✅ EXISTS |
| `operating_profit` | 영업이익 | **영업이익** | ✅ EXISTS |
| `net_income` | 당기순이익 | **당기순이익(손실)** | ✅ EXISTS |
| `total_assets` | 자산총계 | **자산총계** | ✅ EXISTS |
| `total_liabilities` | 부채총계 | **부채총계** | ✅ EXISTS |
| `total_equity` | 자본총계 | **자본총계** | ✅ EXISTS |
| `operating_cf` | 영업활동현금흐름 | **영업활동현금흐름** | ✅ EXISTS |

---

## API Request Parameters

```python
params = {
    'corp_code': corp_code,      # DART 8-digit corporate code
    'bsns_year': year,            # 4-digit year (e.g., 2023)
    'reprt_code': '11011',        # Report type (11011=Annual)
    'fs_div': 'OFS'               # Financial statement type
}

# fs_div options:
# - 'OFS' = 개별재무제표 (Separate/Individual Financial Statements)
# - 'CFS' = 연결재무제표 (Consolidated Financial Statements)
```

**Recommendation**: Use **CFS (Consolidated)** for listed companies with subsidiaries, **OFS (Separate)** for standalone companies.

---

## Parsing Logic Update

### Before (Wrong Endpoint):
```python
response = self._make_request('fnlttSinglAcnt.json', params)
# Result: Only 14 summary items returned
```

### After (Correct Endpoint):
```python
params = {
    'corp_code': corp_code,
    'bsns_year': year,
    'reprt_code': '11011',
    'fs_div': 'CFS'  # ADD THIS PARAMETER
}
response = self._make_request('fnlttSinglAcntAll.json', params)
# Result: 100+ detailed account items returned
```

### Updated Item Lookup:
```python
# Create lookup dictionary
item_lookup = {}
for item in items:
    account_name = item.get('account_nm', '')
    amount = item.get('thstrm_amount', '0').replace(',', '')
    try:
        item_lookup[account_name] = float(amount)
    except (ValueError, TypeError):
        pass

# Phase 2 field extraction (with fallbacks)
revenue = item_lookup.get('영업수익', 0)
cogs = item_lookup.get('매출원가', 0)
gross_profit = item_lookup.get('매출총이익', 0) or (revenue - cogs)
pp_e = item_lookup.get('유형자산', 0)
accounts_receivable = item_lookup.get('매출채권', 0)

# Depreciation (estimated from cash flow)
operating_profit = item_lookup.get('영업이익', 0)
operating_cf = item_lookup.get('영업활동현금흐름', 0)
working_capital_change = item_lookup.get('영업활동으로 인한 자산부채의 변동', 0)
depreciation = operating_cf - operating_profit - working_capital_change if operating_cf > 0 else 0

# Accumulated depreciation - NOT AVAILABLE, set to NULL
accumulated_depreciation = None

# SG&A expense
sga_expense = item_lookup.get('판매비와관리비', 0)

# R&D expense - NOT AVAILABLE, set to NULL
rd_expense = None

# Operating expense (COGS + SG&A)
operating_expense = cogs + sga_expense

# Interest income/expense (use accrual basis for consistency)
interest_income = item_lookup.get('금융수익', 0)
interest_expense = item_lookup.get('금융비용', 0)

# Loan portfolio, NPL, NIM - Only for financial companies
loan_portfolio = item_lookup.get('대출금', 0) if company_industry == 'FINANCIAL' else None
npl_amount = None  # Rarely disclosed
nim = ((interest_income - interest_expense) / loan_portfolio * 100) if loan_portfolio and loan_portfolio > 0 else None

# Cash flows
investing_cf = item_lookup.get('투자활동현금흐름', 0)
financing_cf = item_lookup.get('재무활동현금흐름', 0)

# EBITDA (use estimated depreciation)
ebitda = operating_profit + depreciation if depreciation > 0 else operating_profit
ebitda_margin = (ebitda / revenue * 100) if revenue > 0 else 0
```

---

## Data Quality Notes

### Fields with High Availability (>90% of companies)
- ✅ Revenue (영업수익)
- ✅ COGS (매출원가)
- ✅ Gross Profit (매출총이익)
- ✅ Operating Profit (영업이익)
- ✅ Net Income (당기순이익)
- ✅ Assets, Liabilities, Equity
- ✅ PP&E (유형자산)
- ✅ Accounts Receivable (매출채권)
- ✅ SG&A Expense (판매비와관리비)
- ✅ Operating/Investing/Financing Cash Flows

### Fields with Low Availability (<50% of companies)
- ⚠️ Depreciation (감가상각비) - **Must estimate from cash flow**
- ⚠️ Accumulated Depreciation (감가상각누계액) - **Set to NULL**
- ⚠️ R&D Expense (연구개발비) - **Set to NULL or check business report**
- ⚠️ Loan Portfolio/NPL/NIM - **Only for financial companies**

### Industry-Specific Availability

**Manufacturing Companies** (Samsung, Hyundai, LG):
- ✅ COGS, Gross Profit, PP&E, Accounts Receivable
- ⚠️ Depreciation (estimate), R&D (NULL)
- ❌ Loan Portfolio, NPL, NIM (N/A)

**Financial Companies** (KB Financial, Shinhan, Hana):
- ❌ COGS, Gross Profit (N/A)
- ✅ Interest Income, Interest Expense
- ✅ Loan Portfolio, NPL, NIM
- ❌ PP&E (minimal)

**Tech/E-Commerce Companies** (Naver, Kakao, Coupang):
- ⚠️ COGS (service COGS, not inventory)
- ✅ SG&A, Operating Expenses
- ⚠️ R&D (sometimes disclosed)
- ❌ PP&E (minimal)

---

## Recommendations

1. **Use Consolidated Statements (CFS)** for listed companies with subsidiaries
2. **Estimate Depreciation** from operating cash flow when not directly disclosed
3. **Set NULL for unavailable fields** rather than using 0 (distinguishes missing data from zero value)
4. **Industry-specific logic** for financial vs. manufacturing vs. tech companies
5. **Validation step** to check data quality after backfill (e.g., gross profit = revenue - COGS)

---

**Last Updated**: 2025-10-24
**Source**: Samsung Electronics (005930) 2023 Annual Report via DART API
**Total DART Account Items**: 115 (vs. 14 in summary API)
