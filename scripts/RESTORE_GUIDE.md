# Spock 시스템 복원 가이드

새 노트북으로 Spock 프로젝트를 마이그레이션하기 위한 단계별 가이드입니다.

## 📋 사전 준비

### 필요한 항목
- ✅ 백업 파일 (외장 드라이브 또는 클라우드에서)
- ✅ 새 macOS 노트북
- ✅ 관리자 권한
- ✅ 인터넷 연결
- ✅ 백업 시 기록한 시스템 정보

### 예상 소요 시간
- **전체 복원**: 2-3시간
- **데이터베이스 복원**: 30-60분
- **환경 설정**: 30분
- **검증**: 30분

---

## 🚀 복원 절차

### Phase 1: 시스템 환경 준비 (60분)

#### 1.1 Homebrew 설치
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# PATH 설정 (Apple Silicon Mac의 경우)
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

#### 1.2 Python 설치 (Anaconda)
```bash
# Anaconda 다운로드
curl -O https://repo.anaconda.com/archive/Anaconda3-2024.10-1-MacOSX-arm64.sh

# 설치
bash Anaconda3-2024.10-1-MacOSX-arm64.sh

# 설치 후 터미널 재시작
source ~/.zshrc
```

**검증**:
```bash
python3 --version  # Should show Python 3.12.11 or similar
which python3      # Should show /Users/[username]/anaconda3/bin/python3
```

#### 1.3 PostgreSQL 설치

**Option A: PostgreSQL 14 설치 (현재 시스템과 동일)**
```bash
brew install postgresql@14

# PATH 추가
echo 'export PATH="/opt/homebrew/opt/postgresql@14/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 서비스 시작
brew services start postgresql@14
```

**Option B: PostgreSQL 17 설치 (최신 버전)**
```bash
brew install postgresql@17

# PATH 추가
echo 'export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 서비스 시작
brew services start postgresql@17
```

**권장**: PostgreSQL 14 (기존 시스템과 동일하여 호환성 문제 없음)

#### 1.4 TimescaleDB 설치
```bash
brew tap timescale/tap
brew install timescaledb

# TimescaleDB 설정
timescaledb-tune --quiet --yes

# PostgreSQL 재시작
brew services restart postgresql@14  # 또는 postgresql@17
```

**검증**:
```bash
psql --version
# Should show: psql (PostgreSQL) 14.x

psql postgres -c "SELECT version();"
# Should connect without errors
```

#### 1.5 Git 설정
```bash
# Git 사용자 정보 설정
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# GitHub SSH 키 생성 (선택사항)
ssh-keygen -t ed25519 -C "your.email@example.com"
cat ~/.ssh/id_ed25519.pub  # GitHub에 등록
```

---

### Phase 2: 프로젝트 복원 (30분)

#### 2.1 백업 파일 준비
```bash
# 외장 드라이브 또는 클라우드에서 백업 다운로드
# 예: /Volumes/ExternalDrive/spock_backup/migration_YYYYMMDD_HHMMSS

BACKUP_DIR="/path/to/your/backup"  # 실제 경로로 변경
cd ~
```

#### 2.2 Git 저장소 복원

**Option A: Git Bundle 사용 (오프라인 가능)**
```bash
# 새 디렉토리 생성
mkdir -p ~/spock
cd ~/spock

# Bundle에서 복원
git clone ${BACKUP_DIR}/spock_repo.bundle spock
cd spock

# 리모트 재설정
git remote remove origin
git remote add origin https://github.com/jsj9346/spock.git

# (선택사항) 최신 변경사항 가져오기
git fetch origin
git pull origin main
```

**Option B: GitHub에서 직접 클론 (온라인 필요)**
```bash
cd ~
git clone https://github.com/jsj9346/spock.git
cd spock

# 백업 시점의 커밋으로 체크아웃 (MANIFEST.md에서 확인)
git checkout [commit_hash]
```

#### 2.3 환경 파일 복원
```bash
cd ~/spock

# .env 파일 복사
cp ${BACKUP_DIR}/env/.env .env
cp ${BACKUP_DIR}/env/.env.bak .env.bak

# config 디렉토리 복사
cp -r ${BACKUP_DIR}/env/config ./

# 권한 설정 (보안)
chmod 600 .env .env.bak
```

**⚠️ 중요**: `.env` 파일에 API 키가 포함되어 있으므로 안전하게 관리하세요!

#### 2.4 Python 패키지 설치
```bash
cd ~/spock

# pip 업그레이드
pip install --upgrade pip

# 패키지 설치 (백업 시 frozen requirements 사용)
pip install -r ${BACKUP_DIR}/python/requirements_frozen.txt

# 또는 프로젝트 requirements 사용
pip install -r requirements.txt
pip install -r requirements_quant.txt
```

**트러블슈팅**:
```bash
# 일부 패키지 설치 실패 시
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt --no-cache-dir
```

---

### Phase 3: 데이터베이스 복원 (60분)

#### 3.1 데이터베이스 생성
```bash
# PostgreSQL 서비스 확인
brew services list | grep postgresql

# 데이터베이스 생성
createdb quant_platform

# TimescaleDB 확장 활성화
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# 확장 확인
psql -d quant_platform -c "SELECT extname, extversion FROM pg_extension;"
```

#### 3.2 데이터베이스 복원

**Option A: 전체 덤프 복원 (간단)**
```bash
cd ~/spock

# 전체 복원 (스키마 + 데이터)
psql -d quant_platform -f ${BACKUP_DIR}/database/complete.sql

# 진행 상황 확인 (별도 터미널)
psql -d quant_platform -c "
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
"
```

**Option B: 스키마 + 데이터 분리 복원 (권장, 더 안전)**
```bash
# 1. 스키마 먼저 복원
psql -d quant_platform -f ${BACKUP_DIR}/database/schema.sql

# 2. TimescaleDB 하이퍼테이블 재생성 (필요한 경우)
psql -d quant_platform -c "
SELECT create_hypertable('ohlcv_data', 'date', if_not_exists => TRUE);
"

# 3. 데이터 복원
psql -d quant_platform -f ${BACKUP_DIR}/database/data.sql
```

**예상 시간**:
- Schema: ~1분
- Data: ~30-60분 (5.8M 레코드)

#### 3.3 데이터 검증
```bash
# 레코드 수 확인
psql -d quant_platform -c "
SELECT 'tickers' as table_name, COUNT(*) as count FROM tickers
UNION ALL SELECT 'ohlcv_data', COUNT(*) FROM ohlcv_data
UNION ALL SELECT 'ticker_fundamentals', COUNT(*) FROM ticker_fundamentals
ORDER BY count DESC;
"

# 백업 시 카운트와 비교
cat ${BACKUP_DIR}/database/data_counts.txt

# 데이터베이스 크기 확인
psql -d quant_platform -c "
SELECT pg_size_pretty(pg_database_size('quant_platform'));
"
```

**예상 결과**:
```
 table_name          | count
---------------------+---------
 ohlcv_data          | 5823357
 tickers             | 21224
 ticker_fundamentals | ~thousands
```

---

### Phase 4: 설정 및 검증 (30분)

#### 4.1 디렉토리 구조 확인
```bash
cd ~/spock

# 필요한 디렉토리 생성
mkdir -p logs
mkdir -p backups
mkdir -p data

# 권한 설정
chmod 755 scripts/*.sh
```

#### 4.2 데이터베이스 연결 테스트
```bash
cd ~/spock

# Python에서 DB 연결 테스트
python3 -c "
from modules.db_manager_postgres import DatabaseManager
db = DatabaseManager()
result = db.execute_query('SELECT COUNT(*) FROM tickers')
print(f'Tickers count: {result[0][0]}')
"
```

**성공 시**: `Tickers count: 21224` 출력

#### 4.3 MCP 서버 테스트
```bash
cd ~/spock

# Spock MCP 서버 상태 확인
python3 -c "
import sys
sys.path.insert(0, '.')
from mcp_server.server import get_system_status
status = get_system_status()
print(status)
"
```

#### 4.4 백테스팅 엔진 테스트
```bash
cd ~/spock

# 간단한 백테스트 실행
python3 examples/backtest_kr_vectorbt.py

# 또는 퀀트 플랫폼 CLI 테스트
python3 quant_platform.py auth status
```

#### 4.5 전체 시스템 검증
```bash
cd ~/spock

# 오케스트레이터 dry-run 테스트
python3 -m modules.orchestration.orchestrator \
  --regions KR \
  --steps tickers \
  --dry-run

# 성공하면 데이터 수집도 테스트 가능
python3 -m modules.orchestration.orchestrator \
  --regions KR \
  --steps ohlcv \
  --incremental \
  --dry-run
```

---

## 🔧 트러블슈팅

### 문제 1: PostgreSQL 연결 실패
```bash
# 서비스 상태 확인
brew services list | grep postgresql

# 재시작
brew services restart postgresql@14

# 로그 확인
tail -50 /opt/homebrew/var/log/postgresql@14.log
```

### 문제 2: TimescaleDB 확장 로드 실패
```bash
# pg_config 경로 확인
pg_config --version

# TimescaleDB 재설치
brew reinstall timescaledb
timescaledb-tune --quiet --yes
brew services restart postgresql@14
```

### 문제 3: Python 패키지 충돌
```bash
# 가상환경 생성 (권장)
conda create -n spock python=3.12
conda activate spock

# 패키지 재설치
pip install -r requirements.txt
```

### 문제 4: 데이터베이스 복원 느림
```bash
# 인덱스 제거 후 복원 (빠름)
psql -d quant_platform -f ${BACKUP_DIR}/database/schema.sql

# 인덱스 없이 데이터 복원
psql -d quant_platform -c "DROP INDEX IF EXISTS idx_ohlcv_date;"
psql -d quant_platform -f ${BACKUP_DIR}/database/data.sql

# 복원 후 인덱스 재생성
psql -d quant_platform -c "CREATE INDEX idx_ohlcv_date ON ohlcv_data(date);"
```

### 문제 5: .env 파일 누락 또는 손상
```bash
# 백업에서 복사
cp ${BACKUP_DIR}/env/.env ~/spock/.env

# 환경 변수 확인
cat ${BACKUP_DIR}/env/env_vars_list.txt

# 필요한 변수 수동 설정
nano ~/spock/.env
```

---

## ✅ 복원 검증 체크리스트

### 시스템 환경
- [ ] Python 3.12+ 설치 확인
- [ ] PostgreSQL 14+ 설치 및 실행 확인
- [ ] TimescaleDB 확장 활성화 확인
- [ ] Git 설정 완료

### 프로젝트 파일
- [ ] Git 저장소 복원 완료
- [ ] `.env` 파일 복원 및 권한 설정
- [ ] Python 패키지 설치 완료
- [ ] 디렉토리 구조 확인

### 데이터베이스
- [ ] 데이터베이스 생성 확인
- [ ] 스키마 복원 완료
- [ ] 데이터 복원 완료 (레코드 수 일치)
- [ ] 데이터베이스 크기 확인 (~2.87GB)

### 기능 테스트
- [ ] DB 연결 테스트 성공
- [ ] MCP 서버 상태 확인 성공
- [ ] 백테스팅 엔진 실행 성공
- [ ] 오케스트레이터 dry-run 성공

---

## 📊 복원 후 최적화 (선택사항)

### PostgreSQL 설정 최적화
```bash
# postgresql.conf 편집
nano /opt/homebrew/var/postgresql@14/postgresql.conf

# 권장 설정 (16GB RAM 기준)
shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 1GB
work_mem = 64MB
```

### TimescaleDB 압축 설정
```sql
-- 1년 이상 된 데이터 압축 (공간 절약)
SELECT add_compression_policy('ohlcv_data', INTERVAL '1 year');
```

### 인덱스 재구성
```sql
-- 인덱스 통계 업데이트
ANALYZE;

-- 인덱스 재구성 (성능 향상)
REINDEX DATABASE quant_platform;
```

---

## 🔐 보안 체크리스트

- [ ] `.env` 파일 권한 600 설정
- [ ] 백업 파일에서 민감 정보 삭제
- [ ] GitHub SSH 키 설정 (선택사항)
- [ ] PostgreSQL 비밀번호 변경 (선택사항)
- [ ] API 키 유효성 확인

---

## 📞 지원

복원 중 문제가 발생하면:
1. 백업 디렉토리의 `system_info.txt` 확인
2. PostgreSQL 로그 확인: `/opt/homebrew/var/log/postgresql@14.log`
3. Python 오류 로그 확인: `~/spock/logs/`

**문서 참조**:
- [QUANT_DEVELOPMENT_WORKFLOWS.md](../docs/QUANT_DEVELOPMENT_WORKFLOWS.md)
- [QUANT_DATABASE_SCHEMA.md](../docs/QUANT_DATABASE_SCHEMA.md)
- [CLAUDE.md](../CLAUDE.md)

---

**복원 완료 후**: 새 노트북에서 전체 백업을 다시 수행하여 복원이 성공적이었는지 확인하세요!
