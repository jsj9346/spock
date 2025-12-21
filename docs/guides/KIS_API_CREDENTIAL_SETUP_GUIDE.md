# KIS API Credential Setup Guide

**Purpose**: Step-by-step guide to obtain and configure Korea Investment & Securities (KIS) API credentials for Spock Trading System.

**Date**: 2025-10-15
**Status**: Production Ready

---

## Overview

KIS API credentials consist of:
- **APP_KEY**: Application key (public identifier)
- **APP_SECRET**: Application secret (private key)
- **BASE_URL**: API endpoint (`https://openapi.koreainvestment.com:9443`)

**Important Restrictions**:
- ⚠️ **1-per-day token issuance**: Access tokens can only be issued once per day
- ⚠️ **Usage restrictions**: Frequent token requests may result in API access suspension
- ⚠️ **Rate limits**: 20 requests/second, 1,000 requests/minute

---

## Prerequisites

### 1. KIS Trading Account
- Active Korea Investment & Securities trading account
- Real account (모의투자 mock account also supported for testing)
- Overseas trading permission enabled (해외주식 거래 권한)

### 2. KIS HTS Installation
- Download KIS HTS (한국투자증권 홈트레이딩시스템)
- URL: https://www.koreainvestment.com/main/Main.jsp
- Complete initial login and security setup

### 3. Identity Verification
- Phone verification (휴대폰 인증)
- Public certificate or digital signature (공동인증서/전자서명)
- Trading password (거래비밀번호)

---

## Step 1: Register for API Access

### 1.1 Access KIS Open API Portal
```
URL: https://apiportal.koreainvestment.com
```

**Login Process**:
1. Click "로그인" (Login)
2. Select "공동인증서 로그인" (Certificate Login) or "간편인증 로그인" (Simple Login)
3. Enter your KIS trading account credentials
4. Complete 2FA verification

### 1.2 Navigate to API Registration
```
Menu Path: My Page (마이페이지) → App Management (앱 관리) → Register App (앱 등록)
```

### 1.3 Fill Application Form

**Required Information**:
- **Application Name** (앱 이름): `Spock Trading System` (or your preferred name)
- **Application Type** (앱 유형): `Personal Trading` (개인매매용)
- **API Usage** (API 사용 용도):
  - ✅ Domestic Stock Trading (국내주식)
  - ✅ Overseas Stock Trading (해외주식)
  - ✅ Real-time Quotation (실시간시세)
  - ✅ Historical Data (과거데이터)
- **Development Environment** (개발환경): `Python`
- **Expected Daily API Calls** (일 예상 호출 건수): `10,000` (adjust based on usage)

**Agreement Checkboxes**:
- ✅ API Terms of Service (API 이용약관)
- ✅ Personal Information Processing (개인정보 처리방침)
- ✅ Third-party Information Provision (제3자 정보제공 동의)

### 1.4 Submit and Wait for Approval

**Approval Timeline**:
- Instant approval: Most personal accounts
- 1-3 business days: Review required cases
- Email notification: When approved

**Check Status**:
```
Menu: My Page → App Management → View App Status
```

---

## Step 2: Retrieve API Credentials

### 2.1 Access Approved Application
```
Menu: My Page → App Management → [Your App Name]
```

### 2.2 Copy Credentials

**APP_KEY** (앱 키):
```
Format: PA1234567890abcdefghij (20-character alphanumeric)
Location: "앱 키(App Key)" section
```

**APP_SECRET** (앱 시크릿):
```
Format: abcdefghijklmnopqrstuvwxyz1234567890ABCD (40-character alphanumeric)
Location: "시크릿(Secret)" section
⚠️ Click "View Secret" (시크릿 보기) - requires password confirmation
```

**Account Number** (계좌번호):
```
Format: 12345678-01 (8 digits + 2 digit suffix)
Location: "계좌번호" section
Note: For trading operations (not data collection)
```

### 2.3 Security Warnings
- 🔒 **Never commit credentials to version control**
- 🔒 **Never share credentials publicly**
- 🔒 **Store securely in environment variables**
- 🔒 **Regenerate if compromised**

---

## Step 3: Configure Spock Environment

### 3.1 Create .env File

**Location**: `/Users/13ruce/spock/.env`

**Template**:
```bash
# KIS API Credentials
KIS_APP_KEY=YOUR_APP_KEY_HERE
KIS_APP_SECRET=YOUR_APP_SECRET_HERE
KIS_BASE_URL=https://openapi.koreainvestment.com:9443

# Account Information (for trading)
KIS_ACCOUNT_NUMBER=12345678-01
KIS_ACCOUNT_PRODUCT_CODE=01

# API Environment (real or mock)
KIS_ENVIRONMENT=real  # or 'mock' for testing

# Optional: OpenAI GPT-4 (for chart analysis)
OPENAI_API_KEY=your_openai_key_here
```

**Example (with dummy values)**:
```bash
# KIS API Credentials
KIS_APP_KEY=PA1234567890abcdefghij
KIS_APP_SECRET=abcdefghijklmnopqrstuvwxyz1234567890ABCD
KIS_BASE_URL=https://openapi.koreainvestment.com:9443

# Account Information
KIS_ACCOUNT_NUMBER=12345678-01
KIS_ACCOUNT_PRODUCT_CODE=01

# API Environment
KIS_ENVIRONMENT=real
```

### 3.2 Secure File Permissions

```bash
# Set secure permissions (owner read/write only)
chmod 600 /Users/13ruce/spock/.env

# Verify permissions
ls -l /Users/13ruce/spock/.env
# Should show: -rw------- (600)
```

### 3.3 Verify .gitignore

Ensure `.env` is excluded from version control:

```bash
# Check if .env is in .gitignore
grep -q "^\.env$" .gitignore || echo ".env" >> .gitignore

# Verify
cat .gitignore | grep "\.env"
```

---

## Step 4: Validate Credentials

### 4.1 Run Validation Script

```bash
# Navigate to Spock directory
cd ~/spock

# Run credential validation script
python3 scripts/validate_kis_credentials.py
```

**Expected Output (Success)**:
```
🔍 Validating KIS API credentials...
✅ Environment file exists: /Users/13ruce/spock/.env
✅ APP_KEY loaded: PA12***************ghij (20 chars)
✅ APP_SECRET loaded: abcd***********************************BCD (40 chars)
✅ BASE_URL loaded: https://openapi.koreainvestment.com:9443

📡 Testing KIS API connection...
✅ OAuth token obtained successfully
✅ Token expires in: 86400 seconds (24 hours)

📊 Testing market data access...
✅ Korea market data: Accessible
✅ US market data: Accessible
✅ Overseas market data: Accessible

🎉 All validation checks passed!
```

**Expected Output (Failure)**:
```
🔍 Validating KIS API credentials...
❌ Environment file not found: /Users/13ruce/spock/.env
   → Create .env file with KIS credentials

OR

✅ Environment file exists
❌ APP_KEY not found in .env
   → Add: KIS_APP_KEY=your_app_key

OR

✅ Credentials loaded
❌ OAuth token request failed: 401 Unauthorized
   → Check APP_KEY and APP_SECRET are correct
   → Verify API access is approved in KIS portal
```

### 4.2 Manual Connection Test

If validation script fails, test manually:

```python
# Test 1: Load environment variables
from dotenv import load_dotenv
import os

load_dotenv()
app_key = os.getenv('KIS_APP_KEY')
app_secret = os.getenv('KIS_APP_SECRET')

print(f"APP_KEY: {app_key[:4]}***{app_key[-4:] if app_key else 'NOT FOUND'}")
print(f"APP_SECRET: {app_secret[:4]}***{app_secret[-4:] if app_secret else 'NOT FOUND'}")

# Test 2: Request OAuth token
from modules.api_clients.kis_overseas_stock_api import KISOverseaStockAPI

api = KISOverseaStockAPI(app_key=app_key, app_secret=app_secret)
token_response = api._get_access_token()

if token_response and 'access_token' in token_response:
    print("✅ OAuth token obtained successfully")
    print(f"Token expires in: {token_response.get('expires_in', 'unknown')} seconds")
else:
    print("❌ Failed to obtain OAuth token")
    print(f"Response: {token_response}")
```

---

## Step 5: Test with Demo Scripts

### 5.1 Test US Adapter (Quick Test)

```bash
# Test US adapter with 5 sample tickers
python3 examples/us_adapter_demo.py
```

**Expected Output**:
```
🇺🇸 US Market Adapter Demo (KIS API)
================================================

📊 Scanning US stocks (may take 2-3 minutes)...
✅ Found 2,947 US stocks

📈 Collecting OHLCV for 5 sample tickers...
✅ [AAPL] Apple Inc. - 250 days collected
✅ [MSFT] Microsoft Corporation - 250 days collected
✅ [GOOGL] Alphabet Inc. - 250 days collected
✅ [TSLA] Tesla Inc. - 250 days collected
✅ [AMZN] Amazon.com Inc. - 250 days collected

📊 Sample Data Preview (AAPL):
        date    open    high     low   close     volume
2025-10-15  175.50  178.20  175.00  177.80  52000000
...
```

### 5.2 Test Korea Adapter (Fastest Test)

```bash
# Test Korea adapter with Samsung (005930)
python3 -c "
from modules.market_adapters.kr_adapter import KRAdapter
from modules.db_manager_sqlite import SQLiteDatabaseManager
import os
from dotenv import load_dotenv

load_dotenv()
db = SQLiteDatabaseManager()
adapter = KRAdapter(db, os.getenv('KIS_APP_KEY'), os.getenv('KIS_APP_SECRET'))

print('Testing Korea market access...')
stocks = adapter.scan_stocks(max_count=10)
print(f'✅ Found {len(stocks)} stocks')
print(f'Sample: {stocks[0] if stocks else \"None\"}')
"
```

### 5.3 Test Deployment Script (Dry Run)

```bash
# Test US adapter deployment (validation only)
python3 scripts/deploy_us_adapter.py --dry-run
```

**Expected Output**:
```
🔍 Validating prerequisites...
✅ Database exists: /Users/13ruce/spock/data/spock_local.db
✅ KIS API connection successful
📊 US Market Status: OPEN/CLOSED
✅ Database schema has region column

🎉 Dry run validation passed!
```

---

## Troubleshooting

### Issue 1: .env File Not Found

**Symptom**:
```
❌ Environment file not found: /Users/13ruce/spock/.env
```

**Solution**:
```bash
# Create .env file
touch /Users/13ruce/spock/.env

# Edit with your credentials
nano /Users/13ruce/spock/.env

# Paste template and replace YOUR_APP_KEY_HERE with actual values
# Save: Ctrl+O, Enter, Ctrl+X
```

### Issue 2: Invalid Credentials (401 Unauthorized)

**Symptom**:
```
❌ OAuth token request failed: 401 Unauthorized
```

**Solutions**:

1. **Check credentials format**:
   ```bash
   # APP_KEY should be 20 characters
   echo $KIS_APP_KEY | wc -c
   # Should output: 21 (20 chars + newline)

   # APP_SECRET should be 40 characters
   echo $KIS_APP_SECRET | wc -c
   # Should output: 41 (40 chars + newline)
   ```

2. **Verify credentials in KIS portal**:
   - Login: https://apiportal.koreainvestment.com
   - Navigate: My Page → App Management
   - Compare APP_KEY and APP_SECRET

3. **Check API approval status**:
   - Status should be "승인됨" (Approved)
   - If "심사중" (Under Review), wait for approval

4. **Regenerate credentials**:
   - KIS Portal → App Management → [Your App]
   - Click "재발급" (Regenerate)
   - Update .env file with new credentials

### Issue 3: Rate Limit Exceeded

**Symptom**:
```
❌ API request failed: 429 Too Many Requests
```

**Solutions**:

1. **Check token issuance frequency**:
   - Only request tokens once per day
   - Tokens are valid for 24 hours
   - Reuse existing token instead of requesting new one

2. **Implement token caching** (already in KIS API client):
   ```python
   # KIS API client automatically caches tokens
   # Token reused until expiration
   # No manual intervention needed
   ```

3. **Adjust request rate**:
   ```bash
   # Reduce collection speed
   python3 scripts/deploy_us_adapter.py --rate-limit 10
   # Default: 20 req/sec, reduced to 10 req/sec
   ```

### Issue 4: Overseas Trading Not Enabled

**Symptom**:
```
❌ Overseas market data: Not accessible
Error: 해외주식 거래 권한이 없습니다 (No overseas stock trading permission)
```

**Solutions**:

1. **Enable overseas trading**:
   - Login to KIS HTS (홈트레이딩시스템)
   - Menu: 해외주식 → 해외주식 신청 (Overseas Stock Application)
   - Complete registration form
   - Wait 1-2 business days for approval

2. **Verify permission in KIS Portal**:
   - Login: https://apiportal.koreainvestment.com
   - My Page → Account Info → Trading Permissions
   - Should show: "해외주식거래" (Overseas Stock Trading): Enabled

3. **Use mock account for testing**:
   ```bash
   # Switch to mock environment in .env
   KIS_ENVIRONMENT=mock

   # Mock account doesn't require overseas permission
   # Data may be limited or simulated
   ```

### Issue 5: Token Expiration During Long Operations

**Symptom**:
```
❌ API request failed: 401 Unauthorized
Note: Token was valid initially but expired during operation
```

**Solutions**:

1. **Automatic token refresh** (already implemented):
   ```python
   # KIS API client automatically refreshes expired tokens
   # No manual intervention needed
   ```

2. **Monitor token expiration**:
   ```bash
   # Check token expiration time
   python3 scripts/test_kis_connection.py --check-token
   ```

3. **Request new token before long operations**:
   ```bash
   # Request fresh token (once per day limit applies)
   python3 scripts/test_kis_connection.py --refresh-token
   ```

---

## Security Best Practices

### 1. Credential Storage
- ✅ **Use .env file**: Never hardcode credentials in source code
- ✅ **Secure permissions**: `chmod 600 .env` (owner read/write only)
- ✅ **Version control**: Add `.env` to `.gitignore`
- ✅ **Backup**: Store encrypted backup in secure location

### 2. Token Management
- ✅ **1-per-day rule**: Minimize token requests to avoid restrictions
- ✅ **Token caching**: Reuse tokens until expiration (24 hours)
- ✅ **Automatic refresh**: Use built-in token refresh mechanism
- ✅ **Monitor expiration**: Track token validity before long operations

### 3. API Usage
- ✅ **Rate limiting**: Respect 20 req/sec, 1,000 req/min limits
- ✅ **Error handling**: Implement exponential backoff on failures
- ✅ **Monitoring**: Track API usage in `kis_api_logs` table
- ✅ **Logging**: Log errors but never log credentials

### 4. Account Security
- ✅ **2FA enabled**: Use two-factor authentication for KIS portal
- ✅ **Strong password**: Use unique password for trading account
- ✅ **Regular review**: Monitor API access logs in KIS portal
- ✅ **Revoke access**: Regenerate credentials if compromised

---

## Validation Checklist

Before running production deployment, verify:

- [ ] KIS trading account active
- [ ] Overseas trading permission enabled
- [ ] API access approved in KIS portal
- [ ] APP_KEY and APP_SECRET obtained
- [ ] .env file created with correct format
- [ ] File permissions set to 600
- [ ] .env excluded from version control
- [ ] Validation script passes all checks
- [ ] Demo script successfully collects data
- [ ] Token caching working correctly
- [ ] Rate limiting verified (<20 req/sec)

---

## Next Steps

After successful credential setup:

1. **Run Deployment Script**:
   ```bash
   python3 scripts/deploy_us_adapter.py --full --days 250
   ```

2. **Monitor Metrics**:
   - Prometheus: http://localhost:8002/metrics
   - Grafana: http://localhost:3000

3. **Verify Data Quality**:
   ```bash
   # Check NULL regions (should be 0)
   python3 -c "
   from modules.db_manager_sqlite import SQLiteDatabaseManager
   db = SQLiteDatabaseManager()
   conn = db._get_connection()
   cursor = conn.cursor()
   cursor.execute('SELECT COUNT(*) FROM ohlcv_data WHERE region IS NULL')
   print(f'NULL regions: {cursor.fetchone()[0]}')
   conn.close()
   "
   ```

4. **Review Documentation**:
   - Deployment Guide: `docs/US_ADAPTER_DEPLOYMENT_GUIDE.md`
   - Implementation Summary: `docs/US_ADAPTER_IMPLEMENTATION_SUMMARY.md`

---

## Support Resources

### KIS API Portal
- URL: https://apiportal.koreainvestment.com
- Documentation: https://apiportal.koreainvestment.com/apiservice
- FAQ: https://apiportal.koreainvestment.com/board/faq

### KIS Customer Support
- Phone: 1544-5000 (Korea)
- Email: api@koreainvestment.com
- Hours: 09:00-18:00 KST (weekdays)

### Spock Project Documentation
- Main README: `CLAUDE.md`
- Architecture: `spock_architecture.mmd`
- PRD: `spock_PRD.md`

---

**Credential Setup Guide Version**: 1.0.0
**Last Updated**: 2025-10-15
**Status**: ✅ Production Ready
