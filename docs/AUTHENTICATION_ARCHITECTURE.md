# Quant Platform Authentication Architecture

**Purpose**: Flexible authentication system supporting personal use, AWS integration, and future commercialization

**Design Philosophy**: Start simple (personal use) → Scale up (commercial) without breaking changes

---

## Overview

### Authentication Modes

```
┌─────────────────────────────────────────────────────────────────┐
│                   Authentication Mode Selection                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Mode 1: Local Personal (No Auth)                              │
│  └─> quant_platform.py --mode local [command]                  │
│      • No authentication required                               │
│      • Direct database access                                   │
│      • Ideal for: Single-user, local development               │
│                                                                  │
│  Mode 2: Personal Cloud (Simple Auth)                          │
│  └─> quant_platform.py --mode cloud [command]                  │
│      • First-time setup wizard                                  │
│      • Simple username/password                                 │
│      • Session-based authentication                             │
│      • Ideal for: Personal cloud deployment                     │
│                                                                  │
│  Mode 3: AWS CLI Integration                                   │
│  └─> quant_platform.py --mode cloud --auth aws [command]       │
│      • Leverages AWS CLI credentials                            │
│      • No separate login needed                                 │
│      • AWS STS for identity validation                          │
│      • Ideal for: AWS-native deployments                        │
│                                                                  │
│  Mode 4: Commercial/Multi-User (Full Auth)                     │
│  └─> quant_platform.py --mode cloud --auth jwt [command]       │
│      • JWT token-based authentication                           │
│      • User management API                                      │
│      • Role-based access control (RBAC)                         │
│      • Ideal for: Multi-user, commercial deployment             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Decision Tree

```
Start → Is mode=local?
         ├─> YES → No authentication (direct DB access)
         └─> NO → Is AWS CLI configured?
                  ├─> YES → AWS CLI auth available
                  │         User choice: AWS auth or Simple auth?
                  └─> NO → Simple auth or JWT auth?
                           ├─> Personal use → Simple auth
                           └─> Commercial → JWT auth
```

---

## Mode 1: Local Personal (No Authentication)

**Use Case**: Single-user development/research on local machine

### Configuration

```yaml
# config/cli_config.yaml
mode: local
authentication:
  enabled: false

database:
  type: postgresql
  host: localhost
  port: 5432
  database: quant_platform
  # Direct connection, no authentication
```

### Implementation

```python
# cli/utils/auth_manager.py
class AuthManager:
    def __init__(self, mode: str = "local"):
        self.mode = mode

    def authenticate(self) -> bool:
        """Authenticate based on mode"""
        if self.mode == "local":
            # No authentication needed
            return True
        elif self.mode == "cloud":
            return self._cloud_authenticate()

    def get_database_credentials(self) -> Dict[str, str]:
        """Get DB credentials based on mode"""
        if self.mode == "local":
            # Read from environment or config
            return {
                "host": os.getenv("DB_HOST", "localhost"),
                "port": os.getenv("DB_PORT", "5432"),
                "database": os.getenv("DB_NAME", "quant_platform"),
                "user": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", "")
            }
```

### Pros/Cons

**Pros**:
- ✅ Zero friction for personal use
- ✅ No login overhead
- ✅ Fast development iteration
- ✅ Direct database access

**Cons**:
- ❌ No security for multi-user scenarios
- ❌ Not suitable for remote access
- ❌ No audit trail

---

## Mode 2: Personal Cloud (Simple Authentication)

**Use Case**: Single-user or small team, cloud-hosted backend

### First-Time Setup Wizard

```python
# cli/commands/setup.py
def run_first_time_setup():
    """Interactive setup wizard for initial configuration"""
    console = Console()

    console.print("[bold cyan]Quant Platform - First-Time Setup[/bold cyan]\n")

    # Check if users exist in database
    db = DatabaseManager()
    user_count = db.execute("SELECT COUNT(*) FROM users")[0][0]

    if user_count == 0:
        console.print("[yellow]No users found in database.[/yellow]")
        console.print("Let's create your admin account.\n")

        # Create admin account
        username = Prompt.ask("Admin username", default="admin")
        email = Prompt.ask("Admin email")

        # Password with confirmation
        while True:
            password = Prompt.ask("Admin password", password=True)
            confirm = Prompt.ask("Confirm password", password=True)
            if password == confirm:
                break
            console.print("[red]Passwords don't match. Try again.[/red]")

        # Hash password
        password_hash = hash_password(password)

        # Create user in database
        db.execute("""
            INSERT INTO users (username, email, password_hash, role, created_at)
            VALUES (%s, %s, %s, 'admin', NOW())
        """, (username, email, password_hash))

        console.print(f"\n[green]✓[/green] Admin account created: {username}")
        console.print(f"[green]✓[/green] You can now login with: quant_platform.py auth login")

    else:
        console.print(f"[green]Found {user_count} existing users.[/green]")
        console.print("Use 'quant_platform.py auth login' to authenticate.")
```

### Database Schema

```sql
-- User management table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt hash
    role VARCHAR(20) DEFAULT 'user',      -- 'admin', 'user', 'analyst'
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Session management (simple token-based)
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(64) UNIQUE NOT NULL,  -- Random token
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Audit log
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,           -- 'login', 'backtest_run', 'optimize'
    resource VARCHAR(255),                  -- Resource affected
    timestamp TIMESTAMP DEFAULT NOW(),
    ip_address INET,
    status VARCHAR(20)                      -- 'success', 'failure'
);
```

### Authentication Flow

```python
# cli/commands/auth.py
def login(api_client: APIClient):
    """Simple login with username/password"""
    console = Console()

    username = Prompt.ask("Username")
    password = Prompt.ask("Password", password=True)

    # Call API
    response = api_client.post('/api/v1/auth/login', data={
        "username": username,
        "password": password
    })

    if response.status_code == 200:
        data = response.json()

        # Store session token (simple file-based storage)
        session_token = data['session_token']
        expires_at = data['expires_at']

        # Save to local config file
        session_file = Path.home() / '.quant_platform' / 'session.json'
        session_file.parent.mkdir(exist_ok=True)

        session_file.write_text(json.dumps({
            'session_token': session_token,
            'expires_at': expires_at,
            'username': username
        }))

        console.print(f"[green]✓[/green] Login successful. Welcome, {username}!")
    else:
        console.print("[red]✗[/red] Login failed. Check your credentials.")


# api/routes/auth_routes.py
@router.post("/login")
async def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    """Simple username/password login"""
    # Find user
    user = db.query(User).filter(User.username == credentials.username).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    # Generate session token (random 64-character string)
    session_token = secrets.token_urlsafe(48)
    expires_at = datetime.now() + timedelta(days=7)  # 7-day session

    # Create session
    session = Session(
        user_id=user.id,
        session_token=session_token,
        expires_at=expires_at
    )
    db.add(session)
    db.commit()

    # Update last login
    user.last_login = datetime.now()
    db.commit()

    # Audit log
    log_audit(db, user.id, "login", "success")

    return {
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "user": {
            "username": user.username,
            "email": user.email,
            "role": user.role
        }
    }
```

### Session Validation Middleware

```python
# api/middleware/auth_middleware.py
async def validate_session(request: Request, db: Session = Depends(get_db)):
    """Validate session token from headers"""
    session_token = request.headers.get("X-Session-Token")

    if not session_token:
        raise HTTPException(status_code=401, detail="No session token provided")

    # Find session
    session = db.query(Session).filter(
        Session.session_token == session_token,
        Session.expires_at > datetime.now()
    ).first()

    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    # Get user
    user = db.query(User).filter(User.id == session.user_id).first()

    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="User not active")

    # Attach user to request
    request.state.user = user

    return user
```

### Pros/Cons

**Pros**:
- ✅ Simple to implement and understand
- ✅ No complex JWT/keyring dependencies
- ✅ Session-based (familiar pattern)
- ✅ Built-in first-time setup wizard
- ✅ Suitable for personal cloud use
- ✅ 7-day session lifetime (good UX)

**Cons**:
- ❌ Less scalable than JWT
- ❌ Requires database query per request
- ❌ Session cleanup needed (cron job)

---

## Mode 3: AWS CLI Integration

**Use Case**: AWS-native deployment leveraging existing AWS credentials

### Prerequisites

User must have AWS CLI configured:
```bash
aws configure
# AWS Access Key ID: AKIA...
# AWS Secret Access Key: ***
# Default region: us-east-1
```

### Authentication Flow

```
1. User runs: quant_platform.py --mode cloud --auth aws backtest run
2. CLI checks for AWS credentials:
   - ~/.aws/credentials (default profile)
   - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
3. CLI generates temporary AWS STS token
4. CLI sends STS token to backend API
5. Backend validates STS token with AWS
6. Backend grants access if valid
```

### Implementation

```python
# cli/utils/aws_auth_manager.py
import boto3
from botocore.exceptions import ClientError

class AWSAuthManager:
    """AWS CLI-based authentication"""

    def __init__(self):
        self.sts_client = boto3.client('sts')

    def is_aws_configured(self) -> bool:
        """Check if AWS CLI is configured"""
        try:
            # Try to get caller identity
            response = self.sts_client.get_caller_identity()
            return True
        except:
            return False

    def get_temporary_credentials(self) -> Dict[str, str]:
        """Get temporary AWS credentials using STS"""
        try:
            # Get caller identity (validates credentials)
            identity = self.sts_client.get_caller_identity()

            # Generate session token (valid for 1 hour)
            response = self.sts_client.get_session_token(
                DurationSeconds=3600  # 1 hour
            )

            credentials = response['Credentials']

            return {
                'access_key_id': credentials['AccessKeyId'],
                'secret_access_key': credentials['SecretAccessKey'],
                'session_token': credentials['SessionToken'],
                'expiration': credentials['Expiration'].isoformat(),
                'user_arn': identity['Arn'],
                'account_id': identity['Account']
            }

        except ClientError as e:
            raise AuthenticationError(f"AWS authentication failed: {e}")

    def validate_sts_token(self, access_key: str, secret_key: str,
                          session_token: str) -> bool:
        """Validate STS token (server-side)"""
        try:
            sts = boto3.client(
                'sts',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token
            )

            # Try to get caller identity
            identity = sts.get_caller_identity()
            return True

        except:
            return False


# cli/commands/auth.py
def login_with_aws():
    """Authenticate using AWS CLI credentials"""
    console = Console()

    aws_auth = AWSAuthManager()

    # Check AWS configuration
    if not aws_auth.is_aws_configured():
        console.print("[red]✗[/red] AWS CLI not configured.")
        console.print("Run 'aws configure' first.")
        return

    console.print("[cyan]Authenticating with AWS CLI credentials...[/cyan]")

    # Get temporary credentials
    try:
        credentials = aws_auth.get_temporary_credentials()

        # Send to backend for validation
        api_client = APIClient()
        response = api_client.post('/api/v1/auth/aws-login', data=credentials)

        if response.status_code == 200:
            data = response.json()

            # Store session token
            save_session(data['session_token'], data['expires_at'])

            console.print(f"[green]✓[/green] AWS authentication successful!")
            console.print(f"[dim]Account: {credentials['account_id']}[/dim]")
            console.print(f"[dim]User ARN: {credentials['user_arn']}[/dim]")
        else:
            console.print("[red]✗[/red] AWS authentication failed.")

    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")


# api/routes/auth_routes.py
@router.post("/aws-login")
async def aws_login(credentials: AWSCredentials, db: Session = Depends(get_db)):
    """Authenticate using AWS STS token"""
    aws_auth = AWSAuthManager()

    # Validate STS token with AWS
    is_valid = aws_auth.validate_sts_token(
        credentials.access_key_id,
        credentials.secret_access_key,
        credentials.session_token
    )

    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid AWS credentials")

    # Extract AWS account ID and user ARN
    account_id = credentials.account_id
    user_arn = credentials.user_arn

    # Find or create user based on AWS ARN
    user = db.query(User).filter(User.aws_arn == user_arn).first()

    if not user:
        # Auto-create user from AWS identity
        username = user_arn.split('/')[-1]  # Extract username from ARN

        user = User(
            username=username,
            email=f"{username}@aws",  # Placeholder email
            password_hash="",  # No password for AWS users
            aws_arn=user_arn,
            aws_account_id=account_id,
            role='user'
        )
        db.add(user)
        db.commit()

    # Create session
    session_token = secrets.token_urlsafe(48)
    expires_at = datetime.now() + timedelta(hours=1)  # Match STS expiration

    session = Session(
        user_id=user.id,
        session_token=session_token,
        expires_at=expires_at
    )
    db.add(session)
    db.commit()

    # Audit log
    log_audit(db, user.id, "aws_login", "success")

    return {
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "user": {
            "username": user.username,
            "aws_arn": user.aws_arn,
            "role": user.role
        }
    }
```

### Database Schema Update

```sql
-- Add AWS-specific fields to users table
ALTER TABLE users ADD COLUMN aws_arn VARCHAR(255) UNIQUE;
ALTER TABLE users ADD COLUMN aws_account_id VARCHAR(12);
ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL;  -- Allow empty for AWS users
```

### Pros/Cons

**Pros**:
- ✅ Leverages existing AWS infrastructure
- ✅ No separate credentials to manage
- ✅ AWS-native security (IAM policies)
- ✅ Automatic user provisioning
- ✅ Ideal for AWS deployments
- ✅ STS tokens are temporary (1 hour)

**Cons**:
- ❌ Requires AWS CLI installation
- ❌ Only works for AWS deployments
- ❌ Short session lifetime (1 hour, matches STS)
- ❌ Additional AWS API calls (cost)

---

## Mode 4: Commercial/Multi-User (JWT Authentication)

**Use Case**: Multi-user platform with role-based access control

**Implementation**: See existing `QUANT_PLATFORM_CLI_DESIGN.md` (already designed)

### Key Features

- ✅ JWT tokens with RS256 signatures
- ✅ OS keychain storage (macOS Keychain, Windows Credential Manager)
- ✅ Automatic token refresh
- ✅ Role-based access control (admin, analyst, user)
- ✅ IP whitelisting (optional)
- ✅ Audit logging
- ✅ User management API

### When to Use

- Multiple users (>5)
- Commercial deployment
- External API access
- Strict security requirements
- Compliance needs (SOC 2, ISO 27001)

---

## Unified Authentication Manager

**Design**: Single `AuthManager` class supporting all 4 modes

```python
# cli/utils/auth_manager.py
from typing import Optional, Dict, Any
from enum import Enum

class AuthMode(Enum):
    LOCAL = "local"           # No authentication
    SIMPLE = "simple"         # Username/password + session
    AWS = "aws"               # AWS CLI integration
    JWT = "jwt"               # Full JWT authentication

class AuthManager:
    """Unified authentication manager supporting multiple modes"""

    def __init__(self, mode: AuthMode, config: Dict[str, Any]):
        self.mode = mode
        self.config = config

        # Initialize mode-specific handlers
        if mode == AuthMode.AWS:
            self.aws_auth = AWSAuthManager()
        elif mode == AuthMode.JWT:
            self.jwt_auth = JWTAuthManager()

    def authenticate(self, username: Optional[str] = None,
                    password: Optional[str] = None) -> bool:
        """Authenticate based on mode"""

        if self.mode == AuthMode.LOCAL:
            # No authentication needed
            return True

        elif self.mode == AuthMode.SIMPLE:
            # Simple username/password
            return self._simple_login(username, password)

        elif self.mode == AuthMode.AWS:
            # AWS CLI authentication
            return self._aws_login()

        elif self.mode == AuthMode.JWT:
            # JWT authentication
            return self._jwt_login(username, password)

    def _simple_login(self, username: str, password: str) -> bool:
        """Simple session-based login"""
        api_client = APIClient(self.config['api_base_url'])
        response = api_client.post('/api/v1/auth/login', data={
            "username": username,
            "password": password
        })

        if response.status_code == 200:
            data = response.json()
            self._save_session(data['session_token'], data['expires_at'])
            return True
        return False

    def _aws_login(self) -> bool:
        """AWS CLI-based login"""
        try:
            credentials = self.aws_auth.get_temporary_credentials()

            api_client = APIClient(self.config['api_base_url'])
            response = api_client.post('/api/v1/auth/aws-login', data=credentials)

            if response.status_code == 200:
                data = response.json()
                self._save_session(data['session_token'], data['expires_at'])
                return True
            return False
        except Exception:
            return False

    def _jwt_login(self, username: str, password: str) -> bool:
        """JWT-based login"""
        # See QUANT_PLATFORM_CLI_DESIGN.md for full implementation
        pass

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for API requests"""
        if self.mode == AuthMode.LOCAL:
            return {}

        # For all authenticated modes, use session token
        session = self._load_session()
        if session and session['expires_at'] > datetime.now():
            return {"X-Session-Token": session['session_token']}

        return {}

    def _save_session(self, token: str, expires_at: str):
        """Save session to local file"""
        session_file = Path.home() / '.quant_platform' / 'session.json'
        session_file.parent.mkdir(exist_ok=True)

        session_file.write_text(json.dumps({
            'session_token': token,
            'expires_at': expires_at,
            'mode': self.mode.value
        }))

    def _load_session(self) -> Optional[Dict[str, Any]]:
        """Load session from local file"""
        session_file = Path.home() / '.quant_platform' / 'session.json'

        if not session_file.exists():
            return None

        try:
            data = json.loads(session_file.read_text())
            data['expires_at'] = datetime.fromisoformat(data['expires_at'])
            return data
        except:
            return None
```

---

## Configuration

### CLI Configuration File

```yaml
# config/cli_config.yaml
# Global settings
mode: local  # local, cloud
deployment: personal  # personal, commercial

# Authentication settings
authentication:
  # Mode selection (auto-detect or explicit)
  mode: auto  # auto, simple, aws, jwt

  # Simple auth settings
  simple:
    session_lifetime_days: 7
    password_min_length: 8

  # AWS auth settings
  aws:
    enabled: true
    profile: default  # AWS CLI profile to use
    region: us-east-1

  # JWT auth settings (future)
  jwt:
    algorithm: RS256
    access_token_expire_minutes: 60
    refresh_token_expire_days: 7

# API settings
api:
  local:
    base_url: "http://localhost:8000"
  cloud:
    base_url: "https://api.quant-platform.com"  # Your AWS deployment URL

# Database settings
database:
  local:
    host: localhost
    port: 5432
    database: quant_platform
    user: postgres
    password: ""  # Load from .env
  cloud:
    host: quant-db.us-east-1.rds.amazonaws.com
    port: 5432
    database: quant_platform
    user: quant_user
    password: ""  # Load from AWS Secrets Manager
```

### Environment Variables

```bash
# .env file (local development)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=quant_platform
DB_USER=postgres
DB_PASSWORD=your_secure_password

# AWS credentials (optional, for AWS auth mode)
# AWS_ACCESS_KEY_ID=AKIA...
# AWS_SECRET_ACCESS_KEY=...
# (Or use aws configure)

# API settings
API_BASE_URL=http://localhost:8000
```

---

## Migration Path

### Phase 1: Personal Use (Now)
```
quant_platform.py --mode local [command]
# No authentication, direct DB access
```

### Phase 2: Personal Cloud (Immediate)
```bash
# First-time setup
quant_platform.py setup
# Creates admin account

# Login
quant_platform.py auth login
# Username: admin
# Password: ***

# Use cloud backend
quant_platform.py --mode cloud backtest run --strategy momentum_value
```

### Phase 3: AWS Integration (Optional)
```bash
# Configure AWS CLI
aws configure

# Login with AWS
quant_platform.py --mode cloud --auth aws auth login

# Use cloud backend with AWS auth
quant_platform.py --mode cloud --auth aws backtest run --strategy momentum_value
```

### Phase 4: Commercial Deployment (Future)
```bash
# Enable JWT authentication in config
# config/cli_config.yaml
authentication:
  mode: jwt

# User management
quant_platform.py admin user create --username alice --email alice@example.com --role analyst
quant_platform.py admin user list
quant_platform.py admin user deactivate bob

# Login with JWT
quant_platform.py auth login
# Token stored in OS keychain
```

---

## Comparison Matrix

| Feature | Local | Simple | AWS | JWT |
|---------|-------|--------|-----|-----|
| **Use Case** | Development | Personal Cloud | AWS Native | Commercial |
| **Setup Complexity** | None | Low | Medium | High |
| **Security Level** | None | Basic | High | Very High |
| **Multi-User** | ❌ | Limited (5-10) | ✅ | ✅ |
| **Session Lifetime** | N/A | 7 days | 1 hour | 1 hour (access), 7 days (refresh) |
| **Audit Logging** | ❌ | ✅ | ✅ | ✅ |
| **RBAC** | ❌ | Basic | ✅ | ✅ |
| **AWS Integration** | ❌ | ❌ | ✅ | Optional |
| **Credential Storage** | .env | Local file | AWS CLI | OS Keychain |
| **Commercialization Ready** | ❌ | ❌ | Partial | ✅ |

---

## Recommendations

### For Your Current Use Case (Personal, Non-Commercial)

**Primary Recommendation: Mode 2 (Simple Authentication)**

**Rationale**:
- ✅ Simple setup with first-time wizard
- ✅ No complex dependencies (JWT, keyring)
- ✅ 7-day session lifetime (good UX)
- ✅ Built-in audit logging
- ✅ Can support 5-10 users (future family/team)
- ✅ Easy migration to JWT later
- ✅ Secure enough for cloud deployment
- ✅ Session-based (familiar pattern)

**Secondary Recommendation: Mode 3 (AWS Auth) if deploying to AWS**

**Rationale**:
- ✅ No separate credentials to manage
- ✅ Leverages existing AWS security
- ✅ Automatic user provisioning
- ✅ AWS-native integration
- ✅ IAM policy support

**Not Recommended: Mode 1 (Local No Auth)**
- Only for local development
- Not suitable for cloud deployment

**Not Recommended: Mode 4 (JWT) - For Now**
- Overly complex for personal use
- Can migrate to this later if commercializing

### Implementation Priority

**Week 1: Mode 2 (Simple Auth)**
1. Implement first-time setup wizard
2. Create username/password login
3. Session management (7-day tokens)
4. Update CLI to support `--mode cloud`

**Week 2: Mode 3 (AWS Auth) - Optional**
1. Implement AWS STS integration
2. Auto-provisioning from AWS IAM
3. AWS CLI detection

**Future: Mode 4 (JWT) - When Commercializing**
1. Migrate from simple sessions to JWT
2. Implement user management API
3. Add RBAC (admin, analyst, user roles)
4. OS keychain storage

---

## Security Considerations

### Simple Auth (Mode 2) Security

**Password Storage**:
```python
import bcrypt

def hash_password(password: str) -> str:
    """Hash password with bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash"""
    return bcrypt.checkpw(password.encode(), password_hash.encode())
```

**Session Token Generation**:
```python
import secrets

def generate_session_token() -> str:
    """Generate cryptographically secure random token"""
    return secrets.token_urlsafe(48)  # 64-character URL-safe string
```

**Session Cleanup (Cron Job)**:
```python
# scripts/cleanup_expired_sessions.py
def cleanup_expired_sessions():
    """Remove expired sessions from database"""
    db = DatabaseManager()
    db.execute("""
        DELETE FROM sessions
        WHERE expires_at < NOW()
    """)

    print(f"Cleaned up expired sessions at {datetime.now()}")

# Run daily via cron
# 0 2 * * * python3 /path/to/cleanup_expired_sessions.py
```

**HTTPS Enforcement**:
```python
# api/main.py
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app = FastAPI()

if os.getenv("ENVIRONMENT") == "production":
    # Force HTTPS in production
    app.add_middleware(HTTPSRedirectMiddleware)
```

### AWS Auth (Mode 3) Security

**STS Token Validation**:
```python
# Server-side validation with AWS
def validate_sts_token(credentials: AWSCredentials) -> bool:
    """Validate STS token directly with AWS"""
    try:
        sts = boto3.client(
            'sts',
            aws_access_key_id=credentials.access_key_id,
            aws_secret_access_key=credentials.secret_access_key,
            aws_session_token=credentials.session_token
        )

        # Try to get caller identity
        identity = sts.get_caller_identity()

        # Verify account matches
        if identity['Account'] != credentials.account_id:
            return False

        return True
    except:
        return False
```

**IAM Policy for Quant Platform**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sts:GetCallerIdentity",
        "sts:GetSessionToken"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## Testing Checklist

### Mode 2 (Simple Auth) Testing

- [ ] First-time setup wizard creates admin account
- [ ] Login with correct credentials succeeds
- [ ] Login with incorrect credentials fails
- [ ] Session token persists across CLI invocations
- [ ] Session expiration (7 days) works correctly
- [ ] Logout clears session token
- [ ] Password hashing uses bcrypt
- [ ] Session cleanup cron job removes expired sessions
- [ ] HTTPS redirect in production
- [ ] Audit log records login/logout events

### Mode 3 (AWS Auth) Testing

- [ ] AWS CLI configuration detected
- [ ] STS token generation succeeds
- [ ] STS token validation works
- [ ] User auto-provisioning from AWS ARN
- [ ] AWS account ID verification
- [ ] IAM policy allows required actions
- [ ] Session expires after 1 hour (matches STS)

---

## Conclusion

**For your personal use case**, I recommend **Mode 2 (Simple Authentication)** as the default:

1. **Simple Setup**: First-time wizard creates admin account
2. **No Complex Dependencies**: No JWT/keyring, just session tokens
3. **Good UX**: 7-day session lifetime
4. **Secure Enough**: bcrypt passwords, HTTPS, session tokens
5. **Future-Proof**: Easy migration to JWT when commercializing
6. **Audit Trail**: Built-in audit logging

**If deploying to AWS**, consider **Mode 3 (AWS Auth)** as an alternative:
- Leverages existing AWS credentials
- No separate password to remember
- AWS-native security with IAM

**When commercializing**, migrate to **Mode 4 (JWT)**:
- Full-featured authentication
- OS keychain storage
- RBAC support
- Industry-standard security

---

**Last Updated**: 2025-10-22
**Version**: 1.0.0
**Status**: Design Complete - Ready for Implementation
