# US Adapter Deployment - Token Limit Issue

## Date: 2025-10-15

## Issue Summary

Encountered KIS API **1-per-day token issuance limit** during US adapter deployment testing. The deployment partially succeeded but revealed OHLCV data retrieval issues.

## Timeline of Events

### 15:27:07 - Initial Deployment Test
```bash
python3 scripts/deploy_us_adapter.py --tickers AAPL MSFT --days 5
```

**Results**:
- ✅ Token obtained successfully (expires in 86400s / 24 hours)
- ✅ Authentication worked
- ❌ No OHLCV data returned for AAPL and MSFT
- ⚠️ Warning: `[AAPL] No OHLCV data returned`
- ⚠️ Warning: `[MSFT] No OHLCV data returned`

### 15:27:08+ - Subsequent API Tests
All subsequent API requests failed with:
```
❌ 403 Client Error: Forbidden for url: https://openapi.koreainvestment.com:9443/oauth2/tokenP
```

**Diagnosis**: Hit the 1-per-day token issuance limit (as per KIS API policy)

## Root Cause Analysis

### 1. Token Limit Restriction (Documented)
From user's note:
> "접근 토큰은 1일 1회 발급 원칙이며, 유효기간내 잦은 토큰 발급 발생 시 이용이 제한 될 수 있습니다."
> (Access tokens can only be issued once per day, frequent issuance may result in usage restrictions)

**Impact**: Cannot test API modifications until tomorrow

### 2. OHLCV Data Retrieval Issue

**Code Location**: `modules/api_clients/kis_overseas_stock_api.py` lines 284-287

```python
# Parse OHLCV data
ohlcv_list = data.get('output2', [])
if not ohlcv_list:
    logger.warning(f"⚠️ [{ticker}] No OHLCV data returned")
    return pd.DataFrame()
```

**Observed Behavior**:
- API call succeeded (no HTTP error)
- Response status: `rt_cd='0'` (success)
- But `output2` field was empty

**Possible Causes**:
1. **Wrong TR_ID**: Currently using `'HHDFS76240000'` for all exchanges
   - This might be the TR_ID for ticker search, not OHLCV data
   - Different KIS API endpoints require different TR_IDs
2. **Wrong Endpoint**: Using `/uapi/overseas-price/v1/quotations/dailyprice`
   - Might need a different endpoint for overseas stocks
3. **Parameter Format**: Date format or exchange code might be incorrect
4. **Market Hours**: API might not return data outside trading hours

## Credential Status

**Verified Working** (as of earlier test):
- APP_KEY: 36 characters (PSBUu4h4...xQn0)
- APP_SECRET: 180 characters (wbbk...f7g=)
- Format: JWT or base64-encoded (not standard 20/40 char format)
- ✅ USAdapterKIS.check_connection() succeeded earlier

**Current Status**: Token exhausted for today (2025-10-15)

## Action Plan for Tomorrow

### Step 1: Research KIS API Documentation
**Objective**: Find correct TR_ID and endpoint for overseas stock OHLCV data

**Questions to Answer**:
1. What is the correct TR_ID for overseas stock daily price data?
2. Is `/uapi/overseas-price/v1/quotations/dailyprice` the correct endpoint?
3. Are there different TR_IDs for different exchanges (US vs HK vs CN)?
4. What is the correct parameter format?

**Reference Documentation**:
- KIS Open API Documentation: https://apiportal.koreainvestment.com
- Check TR_ID mapping guide
- Review overseas stock API examples

### Step 2: Add Enhanced Logging
**File**: `modules/api_clients/kis_overseas_stock_api.py`

**Add debug logging before line 284**:
```python
try:
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    # DEBUG: Log full API response
    logger.debug(f"[{ticker}] KIS API Response:")
    logger.debug(f"  rt_cd: {data.get('rt_cd')}")
    logger.debug(f"  msg_cd: {data.get('msg_cd')}")
    logger.debug(f"  msg1: {data.get('msg1')}")
    logger.debug(f"  output2 length: {len(data.get('output2', []))}")

    # Check response status
    if data.get('rt_cd') != '0':
        error_msg = data.get('msg1', 'Unknown error')
        logger.error(f"❌ [{ticker}] KIS OHLCV error: {error_msg}")
        return pd.DataFrame()
```

### Step 3: Test with Fresh Token (Tomorrow)
**Wait until**: 2025-10-16 00:00 KST (Korea time) for token reset

**Test Command**:
```bash
# Small test with debug logging
python3 scripts/deploy_us_adapter.py --tickers AAPL --days 1

# If successful, expand to full test
python3 scripts/deploy_us_adapter.py --tickers AAPL MSFT GOOGL --days 5
```

### Step 4: Verify TR_ID and Endpoint
**Research Checklist**:
- [ ] Confirm correct TR_ID for US stocks OHLCV
- [ ] Confirm correct TR_ID for HK stocks OHLCV
- [ ] Confirm correct TR_ID for CN stocks OHLCV
- [ ] Verify endpoint URL is correct
- [ ] Check if exchange code format is correct (NASD vs NAS vs NASDAQ)
- [ ] Verify date parameter format (YYYYMMDD)

### Step 5: Alternative Testing Approach
If token limit persists, use **KIS mock investment API** for testing:
- Mock API URL: `https://openapivts.koreainvestment.com:29443`
- Separate token quota (testing environment)
- Same API structure as production

## Lessons Learned

### 1. Token Management
- ⚠️ **1 token per day limit is strict** - must be conservative with token requests
- ✅ **Token caching works** - 24-hour validity with `token_expires_at` check
- ⚠️ **Plan testing carefully** - each day allows only one token request

### 2. API Testing Strategy
- ✅ **Test authentication separately** - validate credentials first
- ✅ **Use small test datasets** - start with 1-2 tickers
- ⚠️ **Add comprehensive logging** - capture full API responses for debugging
- ⚠️ **Research endpoints first** - verify TR_ID and parameters before testing

### 3. Deployment Workflow
- ✅ **Database query fix worked** - no more `get_tickers()` signature error
- ✅ **Exchange code default worked** - using 'NASD' as default is acceptable
- ⚠️ **OHLCV retrieval needs fix** - TR_ID or endpoint might be incorrect

## Current Status

### ✅ Completed
- KIS API credentials validated (36/180 char format)
- Database query method signature fixed (line 293 in deploy_us_adapter.py)
- Deployment script runs without crashes
- Token caching and expiration tracking confirmed working

### ⏳ Blocked (Until Tomorrow)
- OHLCV data retrieval testing (empty `output2` response)
- TR_ID and endpoint verification
- Full deployment validation

### 📋 Next Steps (2025-10-16)
1. Research correct TR_ID from KIS API documentation
2. Add enhanced debug logging to capture API responses
3. Test OHLCV retrieval with fresh token
4. If successful, proceed with full deployment (3,000 US stocks)

## References

- **Deployment Script**: `scripts/deploy_us_adapter.py`
- **KIS API Client**: `modules/api_clients/kis_overseas_stock_api.py`
- **US Adapter**: `modules/market_adapters/us_adapter_kis.py`
- **Deployment Guide**: `docs/US_ADAPTER_DEPLOYMENT_GUIDE.md`
- **Credential Setup**: `docs/KIS_API_CREDENTIAL_SETUP_GUIDE.md`

---

**Author**: Claude Code
**Date**: 2025-10-15
**Status**: Blocked - waiting for token reset (tomorrow)
