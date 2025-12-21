# KIS API Token Caching Implementation

## Date: 2025-10-15

## Overview

Implemented file-based token caching system to comply with KIS API's **1-per-day token issuance limit** and prevent frequent token requests that can result in API suspension.

## Problem Identified

**Original Issue**:
- User reported: "과거에 이미 정상 작동 되었지만 현재 그렇지 않다"
- Root cause: Frequent token requests hitting KIS API's 1-day issuance limit
- Symptom: `403 Forbidden` errors on OAuth endpoint

**Why It Happened**:
- Token stored only in memory (`self.access_token`, `self.token_expires_at`)
- Every program restart requested a new token
- Multiple test runs in one day exceeded the limit
- No persistence across sessions

## Solution: File-Based Token Caching

### Implementation Details

**File**: `modules/api_clients/kis_overseas_stock_api.py`

**Key Changes**:

#### 1. Added Token Cache Path
```python
def __init__(self,
             app_key: str,
             app_secret: str,
             base_url: str = 'https://openapi.koreainvestment.com:9443',
             token_cache_path: str = 'data/.kis_token_cache.json'):
    ...
    self.token_cache_path = Path(token_cache_path)

    # Load cached token if available
    self._load_token_from_cache()
```

#### 2. Token Load from Cache
```python
def _load_token_from_cache(self):
    """
    Load cached access token from file

    - Checks file existence and permissions
    - Validates token expiration (with 1-hour buffer)
    - Loads token into memory if valid
    - Deletes expired cache automatically
    """
```

**Security Checks**:
- File permissions verification (should be 600)
- Token expiration validation with 1-hour safety buffer
- Automatic cleanup of expired tokens

#### 3. Token Save to Cache
```python
def _save_token_to_cache(self):
    """
    Save access token to cache file

    - Creates data/ directory if needed
    - Writes JSON with token and expiration
    - Sets secure permissions (600)
    """
```

**Cache Format** (`data/.kis_token_cache.json`):
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "expires_at": "2025-10-16T15:38:50.302014",
  "cached_at": "2025-10-15T15:38:50.302097"
}
```

#### 4. Updated Token Retrieval Logic
```python
def _get_access_token(self) -> str:
    """
    OAuth 2.0 Access Token 발급 (with file-based caching)

    Token management:
    1. Check memory (already loaded from cache in __init__)
    2. If valid, return cached token
    3. If expired/missing, request new token from API
    4. Save new token to cache file for reuse across sessions
    """
```

### Security Measures

**File Permissions**: 600 (owner read/write only)
```bash
-rw-------@ 1 13ruce  staff  461 Oct 15 15:38 .kis_token_cache.json
```

**Git Exclusion** (`.gitignore`):
```
# KIS API Token Cache (sensitive)
data/.kis_token_cache.json
```

**Location**: `data/` directory (application data, not code)

## Testing and Validation

### Test Script Created
**File**: `scripts/check_token_cache.py`

**Features**:
- Cache file existence and permission check
- Token validity and expiration check
- Token load/save cycle testing
- Security verification

### Test Results

**Cache File Status**:
```
✅ Cache file exists
✅ Secure permissions (600)
✅ Token valid for 24.0 hours
✅ Cached at: 2025-10-15 15:38:50
✅ Expires at: 2025-10-16 15:38:50
```

**API Client Initialization**:
```
✅ API client initialized
✅ Token loaded from cache
✅ Token length: 346 chars
✅ Valid for: 24.0 hours
```

## Benefits

### 1. Compliance with KIS API Policy
- Respects 1-per-day token issuance limit
- Prevents API suspension due to frequent requests
- Automatic token reuse across sessions

### 2. Performance Improvement
- No OAuth request on every startup
- Instant token availability from cache
- Reduced API call latency

### 3. Reliability
- Survives program restarts
- Automatic expiration handling
- 1-hour safety buffer prevents edge cases

### 4. Security
- 600 file permissions (owner-only access)
- Excluded from version control
- Stored in application data directory

## Known Issues and Next Steps

### ✅ Resolved: Token Caching (v1.0 - 2025-10-15)
- [x] File-based token persistence
- [x] Secure file permissions
- [x] Automatic expiration handling
- [x] Git exclusion

### ✅ Resolved: Token Caching Improvements (v2.0 - 2025-10-15)
- [x] Unified validation with optimized 5-minute buffer (99.65% efficiency)
- [x] Enhanced cache loading with automatic error recovery
- [x] Refactored token retrieval logic
- [x] File locking for race condition prevention
- [x] Proactive token refresh (30 minutes before expiry)
- [x] Comprehensive monitoring API (`get_token_status()`)

**See**: `docs/TOKEN_CACHING_IMPROVEMENTS.md` for detailed implementation guide

### ⏳ Pending: OHLCV Data Retrieval

**Issue**: KIS API returns empty `output2` for OHLCV requests

**Root Cause** (from Phase 6 Completion Report):
> "Used placeholder TR_ID `HHDFS76240000` for all overseas markets"
> "KIS API documentation may not have finalized TR_IDs for all markets"

**Evidence**:
```
📡 Request: TR_ID=HHDFS76240000, EXCD=NASD, SYMB=AAPL
📊 Response: rt_cd=0, msg="정상처리 되었습니다.", output2=0 items
```

**Next Steps**:
1. **Research KIS API Documentation**:
   - Find correct TR_ID for overseas stock daily price data
   - Verify endpoint URL is correct
   - Check parameter format requirements

2. **Contact KIS API Support**:
   - Request TR_ID mapping guide for overseas markets
   - Confirm endpoint and parameter format
   - Clarify documentation for overseas stock OHLCV

3. **Alternative Approaches**:
   - Check if different endpoint is needed (not `/uapi/overseas-price/v1/quotations/dailyprice`)
   - Try different parameter combinations
   - Review KIS API sample code if available

## Recommendations

### Immediate Actions
1. ✅ **Use token caching system** - Prevents rate limit issues
2. ⏳ **Research correct TR_ID** - Required for OHLCV data retrieval
3. ⏳ **Test with KIS API support** - Confirm correct endpoint and parameters

### Best Practices for Token Management
1. **Never request token manually** - Always use `_get_access_token()` method
2. **Check cache before testing** - Run `scripts/check_token_cache.py` to verify
3. **Wait for expiration** - If blocked, wait until next day (24 hours)
4. **Monitor cache file** - Ensure `data/.kis_token_cache.json` has 600 permissions

### Development Workflow
```bash
# Check token status before testing
python3 scripts/check_token_cache.py

# If token is valid, proceed with testing
python3 scripts/deploy_us_adapter.py --tickers AAPL MSFT --days 5

# If token is expired/missing, it will be requested automatically
# (Only once per 24 hours)
```

## References

- **Implementation**: `modules/api_clients/kis_overseas_stock_api.py`
- **Test Script**: `scripts/check_token_cache.py`
- **Issue Report**: `docs/US_ADAPTER_TOKEN_LIMIT_ISSUE.md`
- **Phase 6 Report**: `docs/PHASE6_COMPLETION_REPORT.md`
- **KIS API Policy**: "접근 토큰은 1일 1회 발급 원칙이며, 유효기간내 잦은 토큰 발급 발생 시 이용이 제한 될 수 있습니다."

---

**Author**: Claude Code
**Date**: 2025-10-15
**Status**: ✅ Token caching implemented and tested
**Next**: 🔍 Research correct TR_ID for OHLCV data retrieval
