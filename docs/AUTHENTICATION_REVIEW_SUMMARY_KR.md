# 인증 시스템 재설계 요약 (Authentication Review Summary)

**작성일**: 2025-10-22
**버전**: 1.0.0
**상태**: 설계 완료

---

## 변경 사항 개요

기존의 복잡한 JWT 인증 방식을 **4가지 모드를 지원하는 유연한 인증 아키텍처**로 재설계했습니다.

### 주요 변경 사항

| 항목 | 기존 설계 | 새로운 설계 |
|------|----------|------------|
| **인증 방식** | JWT 토큰 (고정) | 4가지 모드 선택 가능 |
| **토큰 저장** | OS Keychain (복잡) | 파일 기반 세션 (간단) |
| **의존성** | python-jose, keyring, cryptography | bcrypt만 필요 |
| **초기 설정** | 수동 사용자 생성 | 자동 setup 마법사 |
| **개인 사용** | 과도하게 복잡 | 간단하고 직관적 |
| **AWS 통합** | 없음 | AWS CLI 인증 지원 |
| **상업화 대비** | JWT만 가능 | JWT로 쉽게 마이그레이션 |

---

## 4가지 인증 모드

### Mode 1: Local (인증 없음)
**용도**: 로컬 개발 및 테스트

```bash
quant_platform.py --mode local backtest run
# 인증 불필요, 직접 DB 접근
```

**특징**:
- ✅ 개발 시 마찰 없음
- ✅ 빠른 반복 작업
- ❌ 원격 접근 불가
- ❌ 다중 사용자 불가

---

### Mode 2: Simple Auth (추천 - 개인 클라우드용)
**용도**: 개인 또는 소규모 팀의 클라우드 배포

#### 초기 설정 (최초 1회)
```bash
python3 quant_platform.py setup

# 출력:
# DB에 등록된 사용자가 없습니다.
# 관리자 계정을 생성하겠습니다.
#
# 관리자 아이디 [admin]: admin
# 이메일: your@email.com
# 비밀번호: ***
# 비밀번호 확인: ***
#
# ✓ 관리자 계정 생성 완료: admin
# 이제 'quant_platform.py auth login'으로 로그인할 수 있습니다.
```

#### 일상적인 사용
```bash
# 로그인
python3 quant_platform.py auth login
# 아이디: admin
# 비밀번호: ***
# ✓ 로그인 성공. 환영합니다, admin!

# 로그인 상태 확인
python3 quant_platform.py auth status
# 로그인 상태: admin
# 세션 만료: 2025-10-29 12:34:56 (7일)

# 클라우드 백엔드 사용
python3 quant_platform.py --mode cloud backtest run --strategy momentum_value

# 로그아웃
python3 quant_platform.py auth logout
# ✓ 로그아웃 완료
```

**특징**:
- ✅ 간단한 설정 (setup 마법사)
- ✅ 7일 세션 유지 (편리한 UX)
- ✅ bcrypt 암호화
- ✅ 세션 토큰: `~/.quant_platform/session.json`
- ✅ 5-10명 규모 지원 가능
- ✅ 추후 JWT로 쉽게 마이그레이션
- ❌ 대규모 사용자에는 부적합

**추천 이유**:
- 개인 사용에 최적화
- 복잡한 의존성 없음
- 클라우드 배포 가능
- 보안성 충분
- 향후 확장 가능

---

### Mode 3: AWS CLI Auth (AWS 배포 시 추천)
**용도**: AWS에 배포하고 AWS CLI를 사용하는 경우

#### 설정 및 사용
```bash
# 1. AWS CLI 설정 (최초 1회)
aws configure
# AWS Access Key ID: AKIA...
# AWS Secret Access Key: ***
# Default region: us-east-1

# 2. AWS 자격 증명으로 로그인
python3 quant_platform.py --mode cloud --auth aws auth login
# AWS CLI 자격 증명으로 인증 중...
# ✓ AWS 인증 성공!
# 계정: 123456789012
# 사용자 ARN: arn:aws:iam::123456789012:user/yourname

# 3. 클라우드 백엔드 사용
python3 quant_platform.py --mode cloud --auth aws backtest run --strategy momentum_value
```

**특징**:
- ✅ 별도의 비밀번호 불필요
- ✅ 기존 AWS 보안 활용 (IAM)
- ✅ AWS ARN 기반 자동 사용자 생성
- ✅ AWS STS 토큰 (1시간 유효)
- ❌ AWS CLI 설치 필요
- ❌ AWS 배포에만 적용 가능

**추천 조건**:
- AWS에 시스템을 배포하는 경우
- 이미 AWS CLI를 사용 중인 경우
- IAM 정책으로 권한 관리를 원하는 경우

---

### Mode 4: JWT Auth (미래 상업화용)
**용도**: 다중 사용자 플랫폼, 상업적 배포

#### 특징
- JWT 토큰 (RS256 서명)
- OS Keychain 저장 (macOS/Windows/Linux)
- 자동 토큰 갱신
- 역할 기반 접근 제어 (RBAC)
- 사용자 관리 API
- 감사 로그

#### 마이그레이션 방법
```bash
# config/cli_config.yaml에서 모드 변경
authentication:
  mode: jwt

# 사용자 관리
python3 quant_platform.py admin user create --username alice --email alice@example.com --role analyst
python3 quant_platform.py admin user list
python3 quant_platform.py admin user deactivate bob

# JWT 토큰은 OS Keychain에 안전하게 저장
python3 quant_platform.py auth login
```

**언제 사용**:
- 상업화를 결정했을 때
- 다중 사용자 지원 필요 (>10명)
- 엄격한 보안 요구사항
- 규정 준수 필요 (SOC 2, ISO 27001)

---

## 데이터베이스 스키마

### 사용자 테이블
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),           -- bcrypt 해시 (AWS 사용자는 비어있음)
    aws_arn VARCHAR(255) UNIQUE,          -- AWS 인증용
    aws_account_id VARCHAR(12),
    role VARCHAR(20) DEFAULT 'user',      -- 'admin', 'user', 'analyst'
    is_active BOOLEAN DEFAULT true,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 세션 테이블
```sql
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(64) UNIQUE NOT NULL,  -- 랜덤 토큰 (64자)
    expires_at TIMESTAMP NOT NULL,              -- 7일 후
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 감사 로그
```sql
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(100) NOT NULL,         -- 'login', 'backtest_run', 'optimize'
    resource VARCHAR(255),
    timestamp TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20)                    -- 'success', 'failure'
);
```

---

## 설치 및 의존성

### 업데이트된 의존성
```bash
# 핵심 의존성 (간소화됨)
pip install rich httpx bcrypt loguru orjson pyyaml

# AWS 통합 (선택사항)
pip install boto3

# JWT 인증 (미래 상업화용, 현재는 불필요)
# pip install python-jose[cryptography] keyring
```

### 제거된 의존성
- ❌ `python-jose` - JWT 토큰 (복잡, 현재 불필요)
- ❌ `keyring` - OS Keychain 저장 (복잡, 현재 불필요)
- ❌ `cryptography` - 고급 암호화 (과도함)
- ❌ `passlib` - 비밀번호 해싱 (bcrypt로 충분)

### 추가된 의존성
- ✅ `bcrypt` - 간단한 비밀번호 해싱
- ✅ `boto3` - AWS 통합 (선택사항)

---

## 구현 우선순위

### Week 1: Mode 2 (Simple Auth) - 최우선
1. Setup 마법사 구현
2. Username/password 로그인
3. 세션 관리 (7일 토큰)
4. `--mode cloud` 플래그 지원

**결과물**: 개인 사용에 충분한 인증 시스템

---

### Week 2: Mode 3 (AWS Auth) - 선택사항
1. AWS STS 통합
2. IAM 기반 자동 사용자 생성
3. AWS CLI 감지

**조건**: AWS에 배포하는 경우에만 구현

---

### 미래: Mode 4 (JWT) - 상업화 결정 시
1. Simple Auth에서 JWT로 마이그레이션
2. 사용자 관리 API 구현
3. RBAC (admin, analyst, user 역할) 추가
4. OS Keychain 저장

**조건**: 상업화를 결정했을 때

---

## 보안 고려사항

### Simple Auth (Mode 2) 보안

#### 비밀번호 저장
```python
import bcrypt

def hash_password(password: str) -> str:
    """bcrypt로 비밀번호 해싱"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, password_hash: str) -> bool:
    """비밀번호 검증"""
    return bcrypt.checkpw(password.encode(), password_hash.encode())
```

#### 세션 토큰 생성
```python
import secrets

def generate_session_token() -> str:
    """암호학적으로 안전한 랜덤 토큰 생성"""
    return secrets.token_urlsafe(48)  # 64자 URL-safe 문자열
```

#### 세션 정리 (크론 작업)
```python
# scripts/cleanup_expired_sessions.py
def cleanup_expired_sessions():
    """만료된 세션을 DB에서 삭제"""
    db = DatabaseManager()
    db.execute("""
        DELETE FROM sessions
        WHERE expires_at < NOW()
    """)
```

**크론 작업**:
```bash
# 매일 새벽 2시에 실행
0 2 * * * python3 /path/to/cleanup_expired_sessions.py
```

#### HTTPS 강제
```python
# api/main.py
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app = FastAPI()

if os.getenv("ENVIRONMENT") == "production":
    # 프로덕션에서는 HTTPS 강제
    app.add_middleware(HTTPSRedirectMiddleware)
```

---

## 업데이트된 문서

다음 문서들이 업데이트되었습니다:

1. **`AUTHENTICATION_ARCHITECTURE.md`** (신규 생성)
   - 4가지 인증 모드 상세 설명
   - 구현 예제 코드
   - DB 스키마
   - 보안 가이드라인
   - 마이그레이션 경로

2. **`QUANT_PLATFORM_CLI_DESIGN.md`** (업데이트)
   - 인증 섹션 재작성
   - 멀티모드 인증 참조 추가

3. **`CLI_DESIGN_SUMMARY.md`** (업데이트)
   - 인증 플로우 간소화
   - 4가지 모드 설명 추가

4. **`IMPLEMENTATION_CHECKLIST_CLI.md`** (업데이트)
   - 의존성 목록 간소화
   - Setup 명령 추가
   - 인증 관리자 태스크 업데이트

5. **`requirements_cli.txt`** (업데이트)
   - 불필요한 의존성 제거 (python-jose, keyring, passlib)
   - bcrypt 추가

---

## 비교 매트릭스

| 기능 | Local | Simple | AWS | JWT |
|------|-------|--------|-----|-----|
| **용도** | 개발 | 개인 클라우드 | AWS 네이티브 | 상업적 |
| **설정 복잡도** | 없음 | 낮음 | 중간 | 높음 |
| **보안 수준** | 없음 | 기본 | 높음 | 매우 높음 |
| **다중 사용자** | ❌ | 제한적 (5-10명) | ✅ | ✅ |
| **세션 수명** | N/A | 7일 | 1시간 | 1시간 (access), 7일 (refresh) |
| **감사 로그** | ❌ | ✅ | ✅ | ✅ |
| **RBAC** | ❌ | 기본 | ✅ | ✅ |
| **AWS 통합** | ❌ | ❌ | ✅ | 선택사항 |
| **자격 증명 저장** | .env | 로컬 파일 | AWS CLI | OS Keychain |
| **상업화 준비** | ❌ | ❌ | 부분적 | ✅ |

---

## 추천 사항

### 현재 사용 사례 (개인, 비상업적)

**1차 추천: Mode 2 (Simple Authentication)**

**이유**:
- ✅ 간단한 setup 마법사로 초기 설정
- ✅ 복잡한 의존성 없음 (JWT/keyring 불필요)
- ✅ 7일 세션 (좋은 UX)
- ✅ 내장 감사 로그
- ✅ 5-10명 지원 가능 (향후 가족/팀 사용)
- ✅ JWT로 쉽게 마이그레이션
- ✅ 클라우드 배포에 충분히 안전
- ✅ 세션 기반 (익숙한 패턴)

**2차 추천: Mode 3 (AWS Auth) - AWS 배포 시**

**이유**:
- ✅ 별도의 자격 증명 관리 불필요
- ✅ 기존 AWS 보안 활용
- ✅ 자동 사용자 생성
- ✅ AWS 네이티브 통합
- ✅ IAM 정책 지원

**추천하지 않음: Mode 1 (Local No Auth)**
- 로컬 개발 전용
- 클라우드 배포에 부적합

**추천하지 않음: Mode 4 (JWT) - 현재는**
- 개인 사용에 과도하게 복잡
- 나중에 상업화 시 마이그레이션 가능

---

## 다음 단계

### 즉시 진행 (Week 1)
1. **Mode 2 (Simple Auth) 구현**
   - Setup 마법사 (`quant_platform.py setup`)
   - Username/password 로그인
   - 세션 관리 (7일 토큰)
   - `--mode cloud` 플래그

### 선택사항 (Week 2)
2. **Mode 3 (AWS Auth) 구현** - AWS 배포 시
   - AWS STS 통합
   - IAM 기반 사용자 생성
   - AWS CLI 감지

### 미래 (상업화 결정 시)
3. **Mode 4 (JWT) 마이그레이션**
   - Simple sessions → JWT 토큰
   - 사용자 관리 API
   - RBAC 추가
   - OS Keychain 저장

---

## 질문 & 답변

### Q1: DB에 사용자가 없을 때 어떻게 되나요?
**A**: `quant_platform.py setup` 명령이 자동으로 감지하여 관리자 계정 생성을 안내합니다.

### Q2: 비밀번호를 잊어버리면?
**A**:
- **개발 중**: DB에서 직접 수정하거나 재설정
- **프로덕션**: 비밀번호 재설정 기능 추가 (이메일 인증)

### Q3: AWS CLI 인증과 Simple 인증을 함께 사용할 수 있나요?
**A**: 네. 사용자 선택에 따라 두 방식 모두 지원합니다.
```bash
# Simple 인증
quant_platform.py --mode cloud auth login

# AWS 인증
quant_platform.py --mode cloud --auth aws auth login
```

### Q4: 상업화 시 기존 사용자는 어떻게 되나요?
**A**: 기존 세션 토큰은 JWT로 자동 마이그레이션됩니다. 사용자는 다시 로그인만 하면 됩니다.

### Q5: 세션 수명을 변경할 수 있나요?
**A**: 네. `config/cli_config.yaml`에서 설정 가능합니다.
```yaml
authentication:
  simple:
    session_lifetime_days: 7  # 원하는 일수로 변경
```

---

## 결론

복잡한 JWT 인증을 **4가지 유연한 인증 모드**로 재설계하여:

1. ✅ **개인 사용에 최적화** (Mode 2 Simple Auth)
2. ✅ **AWS 통합 지원** (Mode 3 AWS Auth)
3. ✅ **향후 상업화 대비** (Mode 4 JWT Auth)
4. ✅ **의존성 간소화** (bcrypt만 필요)
5. ✅ **초기 설정 자동화** (Setup 마법사)
6. ✅ **보안성 유지** (bcrypt, HTTPS, 감사 로그)

**다음 작업**: Mode 2 (Simple Auth) 구현부터 시작하시면 됩니다.

---

**문서 버전**: 1.0.0
**최종 업데이트**: 2025-10-22
**상태**: 설계 완료 - 구현 준비 완료
