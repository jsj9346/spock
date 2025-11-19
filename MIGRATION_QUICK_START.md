# 🚀 Spock 노트북 마이그레이션 빠른 시작 가이드

새 노트북으로 마이그레이션하기 전에 이 가이드를 따라주세요.

---

## 📋 준비물

- ✅ 외장 드라이브 (최소 20GB 여유 공간)
- ✅ 새 macOS 노트북
- ✅ 인터넷 연결
- ✅ 2-3시간 여유 시간

---

## 🎯 기존 노트북에서 할 일 (백업)

### 1단계: 사전 정리 (10분)
```bash
cd ~/spock

# Git 상태 확인 및 커밋
git status
git add .
git commit -m "Pre-migration backup"
git push origin main

# 불필요한 파일 정리
find logs -type f -mtime +30 -delete
find . -name "*.pyc" -delete
```

### 2단계: 전체 백업 실행 (30분)
```bash
cd ~/spock

# 외장 드라이브에 백업
bash scripts/backup_full_system.sh /Volumes/ExternalDrive/spock_backup

# 백업 완료 후 표시되는 경로 기록하기
```

### 3단계: 백업 검증 (5분)
```bash
# 백업 검증
bash scripts/verify_backup.sh /Volumes/ExternalDrive/spock_backup

# "Backup verification PASSED" 메시지 확인
```

### ✅ 백업 완료!
외장 드라이브를 안전하게 보관하세요.

---

## 🆕 새 노트북에서 할 일 (복원)

### 1단계: 시스템 환경 설치 (60분)

#### Homebrew 설치
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# PATH 설정 (Apple Silicon)
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
source ~/.zprofile
```

#### Python (Anaconda) 설치
```bash
# Anaconda 다운로드 및 설치
curl -O https://repo.anaconda.com/archive/Anaconda3-2024.10-1-MacOSX-arm64.sh
bash Anaconda3-2024.10-1-MacOSX-arm64.sh

# 터미널 재시작 후
source ~/.zshrc
python3 --version  # Python 3.12.11 확인
```

#### PostgreSQL + TimescaleDB 설치
```bash
# PostgreSQL 14 설치 (기존 시스템과 동일)
brew install postgresql@14

# PATH 추가
echo 'export PATH="/opt/homebrew/opt/postgresql@14/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# TimescaleDB 설치
brew tap timescale/tap
brew install timescaledb
timescaledb-tune --quiet --yes

# 서비스 시작
brew services start postgresql@14

# 확인
psql --version
```

### 2단계: 프로젝트 복원 (30분)

#### Git 저장소 복원
```bash
# 백업 경로 설정 (외장 드라이브)
BACKUP=/Volumes/ExternalDrive/spock_backup

# 홈 디렉토리로 이동
cd ~

# Git bundle에서 복원
git clone $BACKUP/spock_repo.bundle spock
cd spock

# 리모트 재설정
git remote remove origin
git remote add origin https://github.com/jsj9346/spock.git
```

#### 환경 파일 복원
```bash
# .env 파일 복사
cp $BACKUP/env/.env ~/spock/.env
cp $BACKUP/env/config ~/spock/config -r

# 권한 설정
chmod 600 .env
```

#### Python 패키지 설치
```bash
cd ~/spock

# 패키지 설치 (15-20분 소요)
pip install -r $BACKUP/python/requirements_frozen.txt

# 또는
pip install -r requirements.txt
pip install -r requirements_quant.txt
```

### 3단계: 데이터베이스 복원 (60분)

#### DB 생성 및 확장 활성화
```bash
# 데이터베이스 생성
createdb quant_platform

# TimescaleDB 확장 활성화
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

#### 데이터 복원
```bash
# 전체 복원 (30-60분 소요)
psql -d quant_platform -f $BACKUP/database/complete.sql

# 진행 상황 확인 (별도 터미널)
watch -n 5 'psql -d quant_platform -c "SELECT COUNT(*) FROM ohlcv_data;"'
```

### 4단계: 검증 (10분)

#### DB 연결 테스트
```bash
cd ~/spock

python3 -c "
from modules.db_manager_postgres import DatabaseManager
db = DatabaseManager()
result = db.execute_query('SELECT COUNT(*) FROM tickers')
print(f'✓ Tickers: {result[0][0]}')  # Should be 21,224
"
```

#### 전체 기능 테스트
```bash
# MCP 서버 테스트
python3 -c "
import sys
sys.path.insert(0, '.')
from mcp_server.server import get_system_status
print(get_system_status())
"

# 백테스팅 테스트
python3 examples/backtest_kr_vectorbt.py

# 오케스트레이터 테스트
python3 -m modules.orchestration.orchestrator --regions KR --steps tickers --dry-run
```

### ✅ 복원 완료!

---

## 🆘 문제 해결

### PostgreSQL 연결 실패
```bash
# 서비스 재시작
brew services restart postgresql@14

# 로그 확인
tail -50 /opt/homebrew/var/log/postgresql@14.log
```

### Python 패키지 설치 실패
```bash
# 가상환경 생성
conda create -n spock python=3.12
conda activate spock

# 재설치
pip install -r requirements.txt
```

### 데이터베이스 복원 느림
```bash
# 정상입니다. 5.8M 레코드 복원에 30-60분 소요됩니다.
# 진행 상황 확인:
psql -d quant_platform -c "
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 5;
"
```

---

## 📚 상세 문서

더 자세한 내용은 다음 문서를 참조하세요:

1. **[MIGRATION_PLAN.md](docs/MIGRATION_PLAN.md)** - 전체 마이그레이션 계획
2. **[RESTORE_GUIDE.md](scripts/RESTORE_GUIDE.md)** - 상세 복원 가이드
3. **[CLAUDE.md](CLAUDE.md)** - 프로젝트 개요

---

## ✅ 최종 체크리스트

### 백업 (기존 노트북)
- [ ] Git 커밋 및 푸시 완료
- [ ] 전체 백업 실행 완료
- [ ] 백업 검증 통과
- [ ] 외장 드라이브에 복사 완료

### 복원 (새 노트북)
- [ ] Homebrew 설치
- [ ] Python (Anaconda) 설치
- [ ] PostgreSQL + TimescaleDB 설치
- [ ] Git 저장소 복원
- [ ] 환경 파일 복원
- [ ] Python 패키지 설치
- [ ] 데이터베이스 복원
- [ ] 전체 기능 테스트 통과

### 검증
- [ ] Ticker 수: 21,224개
- [ ] OHLCV 레코드: 5.8M+
- [ ] DB 크기: ~2.87GB
- [ ] 백테스팅 실행 성공
- [ ] MCP 서버 정상 동작

---

**예상 총 소요 시간**: 2-3시간
**난이도**: 중급

문제 발생 시: [scripts/RESTORE_GUIDE.md](scripts/RESTORE_GUIDE.md)의 트러블슈팅 섹션 참조

---

**마이그레이션 성공을 기원합니다! 🎉**
