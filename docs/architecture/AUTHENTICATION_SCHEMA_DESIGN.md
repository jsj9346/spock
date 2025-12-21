# Authentication Schema Design

**Version**: 2.0.0
**Date**: 2025-10-22
**Status**: ✅ Implemented

---

## Purpose

Multi-mode authentication database schema supporting:
- **Mode 1**: Local Personal (No Auth) - Development only
- **Mode 2**: Personal Cloud (Simple Auth) - **Default for personal use**
- **Mode 3**: AWS CLI Integration - AWS-native deployments
- **Mode 4**: Commercial/Multi-User (Full Auth) - Future commercial use

---

## Schema Overview

### Tables Created

```
┌─────────────────────────────────────────────────────────────────┐
│                  Authentication Schema                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  users                                                          │
│  ├─ id (SERIAL PRIMARY KEY)                                     │
│  ├─ username (VARCHAR(50) UNIQUE NOT NULL)                      │
│  ├─ email (VARCHAR(255) UNIQUE NOT NULL)                        │
│  ├─ password_hash (VARCHAR(255))          ← bcrypt for Mode 2  │
│  ├─ aws_arn (VARCHAR(255) UNIQUE)         ← AWS ARN for Mode 3 │
│  ├─ aws_account_id (VARCHAR(12))                                │
│  ├─ role (VARCHAR(20) DEFAULT 'user')     ← admin/user/analyst │
│  ├─ is_active (BOOLEAN DEFAULT true)                            │
│  ├─ last_login (TIMESTAMP)                                      │
│  ├─ created_at (TIMESTAMP DEFAULT NOW())                        │
│  └─ updated_at (TIMESTAMP DEFAULT NOW())                        │
│                                                                  │
│  sessions                                                       │
│  ├─ id (SERIAL PRIMARY KEY)                                     │
│  ├─ user_id (INTEGER REFERENCES users(id))                      │
│  ├─ session_token (VARCHAR(64) UNIQUE)    ← Secure random token│
│  ├─ expires_at (TIMESTAMP NOT NULL)       ← 7 days (Mode 2)    │
│  └─ created_at (TIMESTAMP DEFAULT NOW())   ← 1 hour (Mode 3)   │
│                                                                  │
│  audit_log                                                      │
│  ├─ id (BIGSERIAL PRIMARY KEY)                                  │
│  ├─ user_id (INTEGER REFERENCES users(id))                      │
│  ├─ action (VARCHAR(100) NOT NULL)        ← login/backtest/etc │
│  ├─ resource (VARCHAR(255))               ← Strategy name/ID   │
│  ├─ timestamp (TIMESTAMP DEFAULT NOW())                         │
│  ├─ ip_address (INET)                                           │
│  └─ status (VARCHAR(20) DEFAULT 'success')                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Table Specifications

### 1. users Table

**Purpose**: Central user account management for all authentication modes

**Schema**:
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),           -- bcrypt hash (NULL for AWS users)
    aws_arn VARCHAR(255) UNIQUE,          -- AWS IAM ARN (for AWS auth mode)
    aws_account_id VARCHAR(12),           -- AWS account ID
    role VARCHAR(20) DEFAULT 'user',      -- 'admin', 'user', 'analyst'
    is_active BOOLEAN DEFAULT true,       -- Account status
    last_login TIMESTAMP,                 -- Last successful login
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Indexes**:
- `idx_users_username` - Fast username lookup for login
- `idx_users_email` - Fast email lookup
- `idx_users_aws_arn` - Fast AWS ARN lookup (partial index, only non-NULL)
- `idx_users_active` - Fast active user filtering (partial index)

**Constraints**:
- `UNIQUE (username)` - No duplicate usernames
- `UNIQUE (email)` - No duplicate emails
- `UNIQUE (aws_arn)` - One AWS ARN per user

**Triggers**:
- `update_users_updated_at` - Automatically update `updated_at` on row changes

**Mode-Specific Usage**:
- **Mode 1 (Local)**: Not used (no authentication)
- **Mode 2 (Simple Auth)**: `username`, `email`, `password_hash` required
- **Mode 3 (AWS Auth)**: `username`, `email`, `aws_arn`, `aws_account_id` required (password_hash NULL)
- **Mode 4 (JWT Auth)**: All fields available, JWT token stored in sessions table

---

### 2. sessions Table

**Purpose**: Session token management for stateless authentication

**Schema**:
```sql
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(64) UNIQUE NOT NULL,  -- Cryptographically secure token
    expires_at TIMESTAMP NOT NULL,              -- Session expiration
    created_at TIMESTAMP DEFAULT NOW()
);
```

**Indexes**:
- `idx_sessions_token` - Fast token lookup for validation
- `idx_sessions_user_id` - Fast user session lookup
- `idx_sessions_expires` - Fast expired session cleanup

**Constraints**:
- `UNIQUE (session_token)` - No duplicate tokens
- `FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE` - Cascade delete sessions when user deleted

**Token Generation**:
```python
import secrets
session_token = secrets.token_urlsafe(48)  # 48 bytes → 64-character URL-safe token
```

**Expiration Policy**:
- **Mode 2 (Simple Auth)**: 7 days (168 hours)
- **Mode 3 (AWS Auth)**: 1 hour (AWS STS token lifetime)
- **Mode 4 (JWT Auth)**: Configurable (default 24 hours)

**Cleanup**:
```sql
-- Manual cleanup
DELETE FROM sessions WHERE expires_at < NOW();

-- Using helper function
SELECT cleanup_expired_sessions();
```

---

### 3. audit_log Table

**Purpose**: Security audit trail for compliance and debugging

**Schema**:
```sql
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,           -- Action type
    resource VARCHAR(255),                  -- Resource identifier
    timestamp TIMESTAMP DEFAULT NOW(),
    ip_address INET,                        -- Client IP
    status VARCHAR(20) DEFAULT 'success'    -- 'success', 'failure'
);
```

**Indexes**:
- `idx_audit_log_user_id` - Fast user activity lookup
- `idx_audit_log_timestamp` - Chronological log retrieval
- `idx_audit_log_action` - Fast action type filtering
- `idx_audit_log_status` - Fast failure detection (partial index)

**Common Action Types**:
- `login` - User authentication
- `logout` - User session termination
- `backtest_run` - Backtest execution
- `optimize` - Portfolio optimization
- `strategy_create` - Strategy creation
- `strategy_update` - Strategy modification
- `strategy_delete` - Strategy deletion

**Example Audit Entries**:
```sql
-- Successful login
INSERT INTO audit_log (user_id, action, resource, ip_address, status)
VALUES (1, 'login', NULL, '192.168.1.100', 'success');

-- Failed login attempt
INSERT INTO audit_log (user_id, action, resource, ip_address, status)
VALUES (NULL, 'login', 'admin', '192.168.1.100', 'failure');

-- Backtest execution
INSERT INTO audit_log (user_id, action, resource, ip_address, status)
VALUES (1, 'backtest_run', 'momentum_value', '192.168.1.100', 'success');
```

**Retention Policy**:
- Keep all audit logs indefinitely for compliance
- Consider partitioning by month for large deployments
- Archive logs older than 1 year to cold storage

---

## Helper Functions

### 1. update_updated_at_column()

**Purpose**: Automatically update `updated_at` timestamp on row modifications

**Implementation**:
```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach to users table
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Usage**: Automatic (no manual invocation needed)

---

### 2. cleanup_expired_sessions()

**Purpose**: Delete expired session tokens

**Implementation**:
```sql
CREATE OR REPLACE FUNCTION cleanup_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM sessions WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
```

**Usage**:
```sql
-- Manual cleanup
SELECT cleanup_expired_sessions();  -- Returns number of deleted sessions

-- Scheduled cleanup (via cron or scheduled job)
-- Run daily at 2:00 AM
```

**Scheduled Cleanup** (PostgreSQL pg_cron extension):
```sql
-- Install pg_cron extension
CREATE EXTENSION pg_cron;

-- Schedule daily cleanup at 2:00 AM
SELECT cron.schedule('cleanup-sessions', '0 2 * * *', 'SELECT cleanup_expired_sessions();');
```

---

## Schema Initialization

### Installation

```bash
# Run schema initialization script
python3 scripts/init_auth_schema.py

# Output:
# ✅ Connected to PostgreSQL: quant_platform@localhost:5432
# 🚀 Initializing authentication schema...
# ✅ Creating users table
# ✅ Creating sessions table
# ✅ Creating audit_log table
# ✅ Creating update_updated_at_column function
# ✅ Creating cleanup_expired_sessions function
# 🔍 Validating authentication schema...
# ✅ Table 'users' exists
# ✅ Table 'sessions' exists
# ✅ Table 'audit_log' exists
# ✅ Function 'update_updated_at_column' exists
# ✅ Function 'cleanup_expired_sessions' exists
# ✅ Authentication schema initialization complete
```

### Validation

```bash
# Validate existing schema
python3 scripts/init_auth_schema.py --validate

# Check tables manually
psql -d quant_platform -c "\dt" | grep -E "(users|sessions|audit_log)"

# Verify table structure
psql -d quant_platform -c "\d users"
psql -d quant_platform -c "\d sessions"
psql -d quant_platform -c "\d audit_log"
```

### Reset Schema

```bash
# Drop and recreate tables (use with caution - deletes all users)
python3 scripts/init_auth_schema.py --drop

# WARNING: This will delete:
# - All user accounts
# - All active sessions
# - All audit logs
```

---

## Security Considerations

### Password Security (Mode 2 - Simple Auth)

**Hashing Algorithm**: bcrypt with cost factor 12

**Implementation**:
```python
import bcrypt

# Hash password during registration
password = "user_password"
password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))

# Verify password during login
is_valid = bcrypt.checkpw(password.encode('utf-8'), password_hash)
```

**Best Practices**:
- ✅ Never store plaintext passwords
- ✅ Use bcrypt cost factor ≥12 (recommended: 12-14)
- ✅ Salt is automatically included in bcrypt hash
- ✅ Enforce minimum password length (8 characters)
- ✅ Require password confirmation during registration

---

### Session Token Security

**Token Generation**:
```python
import secrets

# Generate cryptographically secure token (48 bytes → 64 characters)
session_token = secrets.token_urlsafe(48)
```

**Token Properties**:
- Length: 64 characters (URL-safe Base64)
- Entropy: 288 bits (48 bytes × 8 bits/byte)
- Collision probability: ~10^-86 (negligible)

**Best Practices**:
- ✅ Use `secrets` module (not `random`)
- ✅ Token length ≥48 bytes (64 characters)
- ✅ URL-safe encoding (Base64 with `-` and `_`)
- ✅ Set reasonable expiration (7 days for personal use)
- ✅ Clean up expired tokens regularly

---

### AWS IAM Integration (Mode 3)

**ARN Validation**:
```python
import boto3

# Validate AWS CLI credentials
sts = boto3.client('sts')
identity = sts.get_caller_identity()

aws_arn = identity['Arn']          # arn:aws:iam::123456789012:user/alice
aws_account_id = identity['Account']  # 123456789012
```

**Best Practices**:
- ✅ Validate AWS STS credentials before creating user
- ✅ Store ARN and account ID for audit purposes
- ✅ Use IAM roles for EC2 instances (not access keys)
- ✅ Set short session expiration (1 hour)
- ✅ Leverage AWS CloudTrail for audit logging

---

### Audit Logging

**What to Log**:
- ✅ All authentication attempts (success/failure)
- ✅ All user actions (backtest, optimize, strategy changes)
- ✅ Resource access (strategy names, backtest IDs)
- ✅ Client IP addresses
- ✅ Timestamps (UTC)

**What NOT to Log**:
- ❌ Passwords (plaintext or hashed)
- ❌ Session tokens
- ❌ Sensitive data (API keys, credentials)

**Example Logging**:
```python
def log_audit(db, user_id: int, action: str, resource: str = None,
              ip_address: str = None, status: str = 'success'):
    """Log user action to audit trail"""
    db.execute("""
        INSERT INTO audit_log (user_id, action, resource, ip_address, status)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, action, resource, ip_address, status))
```

---

## Integration Points

### 1. CLI Authentication (Mode 2)

**Login Flow**:
```python
# cli/commands/auth.py
def login():
    username = input("Username: ")
    password = getpass("Password: ")

    # Call API
    response = api_client.post('/api/v1/auth/login', json={
        "username": username,
        "password": password
    })

    if response.status_code == 200:
        data = response.json()
        # Store session token locally
        save_session(data['session_token'], data['expires_at'])
```

**Session Storage**:
```python
# ~/.quant_platform/session.json
{
    "session_token": "abc123...xyz",
    "expires_at": "2025-10-29T13:35:55",
    "username": "admin"
}
```

---

### 2. API Authentication Middleware

**FastAPI Dependency**:
```python
# api/middleware/auth.py
async def get_current_user(session_token: str = Header(...), db: Session = Depends(get_db)):
    """Validate session token and return current user"""
    session = db.query(Session).filter(
        Session.session_token == session_token,
        Session.expires_at > datetime.now()
    ).first()

    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user = db.query(User).filter(User.id == session.user_id).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    return user
```

**Protected Endpoint**:
```python
@router.post("/backtest")
async def run_backtest(strategy: BacktestRequest, current_user: User = Depends(get_current_user)):
    """Run backtest (requires authentication)"""
    # Log action
    log_audit(db, current_user.id, 'backtest_run', strategy.name)

    # Execute backtest
    result = backtest_engine.run(strategy)
    return result
```

---

## Performance Optimization

### Index Strategy

**Critical Indexes** (already created):
- `users.username` - Login queries (High frequency)
- `sessions.session_token` - Session validation (Very high frequency)
- `audit_log.timestamp DESC` - Recent activity queries (Medium frequency)

**Partial Indexes** (conditional):
- `users.is_active WHERE is_active = true` - Active user filtering (reduces index size)
- `users.aws_arn WHERE aws_arn IS NOT NULL` - AWS user filtering (sparse data)
- `audit_log.status WHERE status = 'failure'` - Failed action detection (sparse data)

---

### Query Optimization

**Session Validation** (Most Frequent):
```sql
-- Optimized query (uses idx_sessions_token)
SELECT s.*, u.*
FROM sessions s
JOIN users u ON s.user_id = u.id
WHERE s.session_token = $1
  AND s.expires_at > NOW()
  AND u.is_active = true;

-- Execution time: <5ms (with index)
```

**User Lookup**:
```sql
-- Optimized query (uses idx_users_username)
SELECT * FROM users
WHERE username = $1
  AND is_active = true;

-- Execution time: <2ms (with index)
```

---

## Migration Guide

### From No Authentication to Simple Auth

**Step 1**: Initialize schema
```bash
python3 scripts/init_auth_schema.py
```

**Step 2**: Create admin account
```bash
python3 quant_platform.py setup
# Interactive wizard creates first admin user
```

**Step 3**: Update CLI to use authentication
```yaml
# config/cli_config.yaml
mode: cloud
authentication:
  enabled: true
  mode: simple
```

**Step 4**: Login and test
```bash
python3 quant_platform.py auth login
python3 quant_platform.py backtest run --strategy momentum_value
```

---

### From Simple Auth to AWS Auth

**Step 1**: Configure AWS CLI
```bash
aws configure
# Enter AWS Access Key ID, Secret Access Key, Region
```

**Step 2**: Create AWS user in database
```python
# api/routes/auth_routes.py
@router.post("/auth/aws-login")
async def aws_login(db: Session = Depends(get_db)):
    # Validate AWS credentials via STS
    sts = boto3.client('sts')
    identity = sts.get_caller_identity()

    aws_arn = identity['Arn']
    aws_account_id = identity['Account']

    # Find or create user
    user = db.query(User).filter(User.aws_arn == aws_arn).first()
    if not user:
        user = User(
            username=identity['UserId'],
            email=f"{identity['UserId']}@aws.iam",
            aws_arn=aws_arn,
            aws_account_id=aws_account_id
        )
        db.add(user)
        db.commit()

    # Create session (1-hour expiration)
    session_token = secrets.token_urlsafe(48)
    expires_at = datetime.now() + timedelta(hours=1)

    session = Session(user_id=user.id, session_token=session_token, expires_at=expires_at)
    db.add(session)
    db.commit()

    return {"session_token": session_token, "expires_at": expires_at.isoformat()}
```

**Step 3**: Update CLI configuration
```yaml
# config/cli_config.yaml
authentication:
  mode: aws
```

**Step 4**: Login with AWS
```bash
python3 quant_platform.py --auth aws auth login
```

---

## Testing

### Unit Tests

```python
# tests/test_auth_schema.py
import pytest
import bcrypt
from datetime import datetime, timedelta

def test_user_creation():
    """Test user account creation"""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash=bcrypt.hashpw(b"password", bcrypt.gensalt()),
        role="user"
    )
    db.add(user)
    db.commit()

    assert user.id is not None
    assert user.is_active is True
    assert user.created_at is not None

def test_session_creation():
    """Test session token creation"""
    session = Session(
        user_id=1,
        session_token=secrets.token_urlsafe(48),
        expires_at=datetime.now() + timedelta(days=7)
    )
    db.add(session)
    db.commit()

    assert session.id is not None
    assert len(session.session_token) == 64

def test_audit_logging():
    """Test audit log entries"""
    log_entry = AuditLog(
        user_id=1,
        action="login",
        status="success",
        ip_address="192.168.1.100"
    )
    db.add(log_entry)
    db.commit()

    assert log_entry.id is not None
    assert log_entry.timestamp is not None
```

---

## Troubleshooting

### Common Issues

**Issue 1**: `psycopg2.OperationalError: FATAL: role "postgres" does not exist`

**Solution**:
```bash
# Create PostgreSQL user
createuser postgres -s

# Or use current macOS user
export POSTGRES_USER=$(whoami)
python3 scripts/init_auth_schema.py --user $(whoami)
```

---

**Issue 2**: `psycopg2.errors.DuplicateTable: relation "users" already exists`

**Solution**:
```bash
# Drop existing tables first
python3 scripts/init_auth_schema.py --drop

# Or skip if already initialized
python3 scripts/init_auth_schema.py --validate
```

---

**Issue 3**: Session tokens not expiring

**Solution**:
```sql
-- Manual cleanup
SELECT cleanup_expired_sessions();

-- Schedule automatic cleanup (pg_cron)
CREATE EXTENSION pg_cron;
SELECT cron.schedule('cleanup-sessions', '0 2 * * *', 'SELECT cleanup_expired_sessions();');
```

---

## References

**Related Documentation**:
- `AUTHENTICATION_ARCHITECTURE.md` - Multi-mode authentication design
- `QUANT_PLATFORM_CLI_IMPLEMENTATION_PLAN.md` - Implementation guide
- `UNIFIED_DEVELOPMENT_ROADMAP.md` - Development timeline

**External Resources**:
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [bcrypt Python Library](https://pypi.org/project/bcrypt/)
- [Python secrets Module](https://docs.python.org/3/library/secrets.html)
- [AWS STS Documentation](https://docs.aws.amazon.com/STS/latest/APIReference/welcome.html)

---

**Last Updated**: 2025-10-22
**Version**: 2.0.0
**Status**: ✅ Implemented and Validated
