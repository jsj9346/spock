# Spock 노트북 마이그레이션 플랜

새 노트북으로의 Spock 프로젝트 완전 마이그레이션을 위한 종합 계획서입니다.

**작성일**: 2025-11-17
**대상**: Spock Quant Investment Platform
**예상 소요 시간**: 2-3시간
**난이도**: 중급

---

## 📊 마이그레이션 개요

### 이전 대상
| 항목 | 크기/수량 | 설명 |
|------|----------|------|
| **프로젝트 코드** | 13GB | Git 저장소 + 의존성 |
| **PostgreSQL DB** | 2.87GB | quant_platform 데이터베이스 |
| **OHLCV 레코드** | 5.8M+ | 6개 시장, 7년 히스토리 |
| **Ticker 수** | 21,224개 | CN, HK, JP, KR, US, VN |
| **환경 파일** | ~10KB | .env, config |
| **문서** | ~50MB | docs, examples, reports |

### 마이그레이션 전략
- **백업 방식**: 전체 시스템 백업 (오프라인 복원 가능)
- **데이터 무결성**: SHA256 체크섬 검증
- **복원 방법**: 스크립트 자동화 + 수동 검증
- **롤백 전략**: 기존 노트북 유지 (검증 완료 후 폐기)

---

## 🗓️ 마이그레이션 타임라인

### Phase 1: 사전 준비 (D-7 ~ D-1)
**목표**: 백업 완료 및 검증

| 단계 | 소요시간 | 작업 내용 | 담당자 | 완료일 |
|------|---------|----------|--------|--------|
| 1.1 | 10분 | 미사용 파일 정리 (logs, 임시 파일) | 사용자 | |
| 1.2 | 15분 | Git 커밋 및 푸시 (모든 변경사항) | 사용자 | |
| 1.3 | 30분 | 전체 백업 실행 | 자동 | |
| 1.4 | 10분 | 백업 검증 | 자동 | |
| 1.5 | 20분 | 외장 드라이브 복사 | 사용자 | |
| 1.6 | 10분 | 클라우드 백업 (선택) | 사용자 | |

**산출물**:
- ✅ 백업 디렉토리 (외장 드라이브)
- ✅ 백업 검증 리포트
- ✅ MANIFEST.md

### Phase 2: 새 노트북 환경 구축 (D-Day, 60분)
**목표**: 시스템 환경 준비

| 단계 | 소요시간 | 작업 내용 |
|------|---------|----------|
| 2.1 | 10분 | Homebrew 설치 |
| 2.2 | 15분 | Python (Anaconda) 설치 |
| 2.3 | 15분 | PostgreSQL 14 + TimescaleDB 설치 |
| 2.4 | 10분 | Git 설정 |
| 2.5 | 10분 | 환경 검증 |

**검증 포인트**:
- [ ] Python 3.12+ 설치 확인
- [ ] PostgreSQL 서비스 실행 확인
- [ ] TimescaleDB 확장 로드 확인

### Phase 3: 프로젝트 복원 (D-Day, 30분)
**목표**: 코드 및 환경 복원

| 단계 | 소요시간 | 작업 내용 |
|------|---------|----------|
| 3.1 | 5분 | Git 저장소 복원 (bundle 또는 clone) |
| 3.2 | 3분 | 환경 파일 복사 (.env, config) |
| 3.3 | 20분 | Python 패키지 설치 |
| 3.4 | 2분 | 디렉토리 구조 확인 |

**검증 포인트**:
- [ ] Git 저장소 정상 복원
- [ ] .env 파일 존재 및 권한 600
- [ ] requirements.txt 패키지 설치 완료

### Phase 4: 데이터베이스 복원 (D-Day, 60분)
**목표**: PostgreSQL 데이터 복원

| 단계 | 소요시간 | 작업 내용 |
|------|---------|----------|
| 4.1 | 2분 | 데이터베이스 생성 |
| 4.2 | 3분 | TimescaleDB 확장 활성화 |
| 4.3 | 50분 | 데이터 복원 (5.8M 레코드) |
| 4.4 | 5분 | 데이터 검증 |

**검증 포인트**:
- [ ] 레코드 수 일치 (5.8M OHLCV)
- [ ] Ticker 수 일치 (21,224개)
- [ ] 데이터베이스 크기 확인 (~2.87GB)

### Phase 5: 통합 테스트 (D-Day, 30분)
**목표**: 전체 시스템 기능 검증

| 단계 | 소요시간 | 작업 내용 |
|------|---------|----------|
| 5.1 | 5분 | DB 연결 테스트 |
| 5.2 | 10분 | MCP 서버 테스트 |
| 5.3 | 10분 | 백테스팅 엔진 테스트 |
| 5.4 | 5분 | 오케스트레이터 dry-run |

**검증 포인트**:
- [ ] Python에서 DB 연결 성공
- [ ] MCP 서버 상태 정상
- [ ] 백테스트 실행 성공
- [ ] 오케스트레이터 동작 확인

### Phase 6: 최종 검증 및 정리 (D+1, 60분)
**목표**: 프로덕션 준비 완료

| 단계 | 소요시간 | 작업 내용 |
|------|---------|----------|
| 6.1 | 15분 | 전체 기능 테스트 (실제 데이터 수집) |
| 6.2 | 20분 | 새 노트북에서 백업 수행 |
| 6.3 | 10분 | 백업 비교 (원본 vs 복원) |
| 6.4 | 10분 | 문서 업데이트 |
| 6.5 | 5분 | 기존 노트북 데이터 정리 계획 |

---

## 🛠️ 사전 준비 체크리스트

### 현재 노트북 (백업 전)
- [ ] Git 상태 정리 (모든 변경사항 커밋)
  ```bash
  git status
  git add .
  git commit -m "Pre-migration commit"
  git push origin main
  ```

- [ ] 불필요한 파일 정리
  ```bash
  # 대용량 로그 파일 삭제
  find logs -type f -mtime +30 -delete

  # 임시 파일 삭제
  find . -name "*.pyc" -delete
  find . -name "__pycache__" -type d -exec rm -rf {} +
  ```

- [ ] 데이터 무결성 확인
  ```bash
  # DB 레코드 수 확인
  psql -d quant_platform -c "SELECT COUNT(*) FROM ohlcv_data;"

  # 테이블 통계 확인
  psql -d quant_platform -c "\dt+"
  ```

- [ ] 환경 변수 목록 확인
  ```bash
  cat .env | grep -v "^#" | cut -d= -f1 > env_vars_checklist.txt
  ```

### 필요한 도구 및 자료
- [ ] 외장 드라이브 (최소 20GB 여유 공간)
- [ ] 클라우드 스토리지 계정 (선택사항)
- [ ] GitHub 계정 및 SSH 키
- [ ] API 키 목록 (KIS, DART, AWS 등)
- [ ] PostgreSQL 관리 도구 (pgAdmin, DBeaver 등)

---

## 📝 백업 실행 가이드

### Step 1: 전체 백업 실행
```bash
cd ~/spock

# 백업 스크립트에 실행 권한 부여
chmod +x scripts/backup_full_system.sh

# 기본 위치에 백업 (~/spock/backups/migration_YYYYMMDD_HHMMSS)
bash scripts/backup_full_system.sh

# 또는 외장 드라이브에 직접 백업
bash scripts/backup_full_system.sh /Volumes/ExternalDrive/spock_backup
```

**예상 시간**: 30분
**예상 크기**: ~4GB (압축 전)

### Step 2: 백업 검증
```bash
# 백업 검증 스크립트 실행
chmod +x scripts/verify_backup.sh
bash scripts/verify_backup.sh /path/to/backup/directory

# 검증 리포트 확인
cat /path/to/backup/directory/backup_verification.txt
```

**검증 항목**:
- ✅ Git bundle 유효성
- ✅ SQL 파일 무결성
- ✅ 환경 파일 존재
- ✅ Python requirements 완전성
- ✅ 전체 백업 크기 (> 500MB)

### Step 3: 외장 드라이브 복사
```bash
# 외장 드라이브 마운트 확인
ls /Volumes/

# 백업 복사
cp -R /path/to/backup/directory /Volumes/ExternalDrive/spock_backup_$(date +%Y%m%d)

# 복사 검증 (체크섬)
diff -r /path/to/backup/directory /Volumes/ExternalDrive/spock_backup_$(date +%Y%m%d)
```

### Step 4: 클라우드 백업 (선택사항)
```bash
# AWS S3 예제
aws s3 cp /path/to/backup/directory s3://your-bucket/spock_backup/ --recursive

# Google Drive 예제 (rclone 사용)
rclone copy /path/to/backup/directory gdrive:spock_backup/
```

---

## 🔧 복원 실행 가이드

자세한 복원 절차는 [RESTORE_GUIDE.md](../scripts/RESTORE_GUIDE.md)를 참조하세요.

### 빠른 복원 절차 (요약)
```bash
# 1. 시스템 환경 준비
brew install postgresql@14 timescaledb

# 2. Git 저장소 복원
cd ~
git clone /path/to/backup/spock_repo.bundle spock
cd spock

# 3. 환경 파일 복원
cp /path/to/backup/env/.env .env

# 4. Python 패키지 설치
pip install -r /path/to/backup/python/requirements_frozen.txt

# 5. 데이터베이스 복원
createdb quant_platform
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
psql -d quant_platform -f /path/to/backup/database/complete.sql

# 6. 검증
python3 -c "from modules.db_manager_postgres import DatabaseManager; \
            db = DatabaseManager(); \
            print(db.execute_query('SELECT COUNT(*) FROM tickers'))"
```

---

## ⚠️ 위험 요소 및 대응 방안

### 위험 1: 데이터베이스 복원 실패
**증상**: `psql: error: connection to server failed`

**원인**:
- PostgreSQL 서비스 미실행
- TimescaleDB 확장 미설치
- 버전 불일치 (PostgreSQL 14 vs 17)

**대응**:
```bash
# 서비스 재시작
brew services restart postgresql@14

# 확장 확인
psql -d quant_platform -c "SELECT * FROM pg_extension;"

# 로그 확인
tail -50 /opt/homebrew/var/log/postgresql@14.log
```

### 위험 2: Python 패키지 충돌
**증상**: `ImportError` 또는 `ModuleNotFoundError`

**원인**:
- Python 버전 차이
- 시스템 라이브러리 의존성
- 패키지 버전 충돌

**대응**:
```bash
# 가상환경 생성
conda create -n spock python=3.12
conda activate spock

# 패키지 재설치
pip install --upgrade pip
pip install -r requirements.txt --no-cache-dir
```

### 위험 3: 환경 변수 누락
**증상**: API 호출 실패, 인증 오류

**원인**:
- .env 파일 누락 또는 손상
- API 키 만료
- 네트워크 권한 문제

**대응**:
```bash
# 백업에서 재복사
cp /path/to/backup/env/.env ~/spock/.env

# 필요한 변수 확인
cat /path/to/backup/env/env_vars_list.txt

# API 키 유효성 테스트
python3 -c "from modules.api_clients.kis_client import KISClient; \
            client = KISClient(); print(client.get_token())"
```

### 위험 4: Git 히스토리 손실
**증상**: 최근 커밋 누락

**원인**:
- 백업 시점 이후 커밋
- Git bundle 불완전

**대응**:
```bash
# GitHub에서 최신 변경사항 가져오기
git remote add origin https://github.com/jsj9346/spock.git
git fetch origin
git merge origin/main
```

---

## ✅ 최종 검증 체크리스트

### 시스템 환경
- [ ] Python 3.12+ 실행 확인: `python3 --version`
- [ ] PostgreSQL 서비스 실행: `brew services list | grep postgresql`
- [ ] TimescaleDB 확장 로드: `psql -c "SELECT extname FROM pg_extension;"`
- [ ] Git 설정 완료: `git config --list`

### 프로젝트 파일
- [ ] 프로젝트 디렉토리 크기 확인: `du -sh ~/spock` (should be ~13GB)
- [ ] .env 파일 권한: `ls -la ~/spock/.env` (should be -rw-------)
- [ ] Git 상태 정상: `git status`
- [ ] Python 패키지 설치: `pip list | wc -l` (should be 100+ packages)

### 데이터베이스
- [ ] DB 연결 성공: `psql -d quant_platform -c "SELECT 1;"`
- [ ] OHLCV 레코드 수: `psql -d quant_platform -c "SELECT COUNT(*) FROM ohlcv_data;"` (should be 5.8M+)
- [ ] Ticker 수: `psql -d quant_platform -c "SELECT COUNT(*) FROM tickers;"` (should be 21,224)
- [ ] 데이터베이스 크기: `psql -d quant_platform -c "SELECT pg_size_pretty(pg_database_size('quant_platform'));"` (should be ~2.87GB)

### 기능 테스트
- [ ] DB 연결 테스트:
  ```bash
  python3 -c "from modules.db_manager_postgres import DatabaseManager; \
              db = DatabaseManager(); print('DB OK')"
  ```

- [ ] MCP 서버 테스트:
  ```bash
  python3 -c "import sys; sys.path.insert(0, '.'); \
              from mcp_server.server import get_system_status; \
              print(get_system_status())"
  ```

- [ ] 백테스팅 테스트:
  ```bash
  python3 examples/backtest_kr_vectorbt.py
  ```

- [ ] 오케스트레이터 테스트:
  ```bash
  python3 -m modules.orchestration.orchestrator --regions KR --steps tickers --dry-run
  ```

### 데이터 무결성
- [ ] 최신 데이터 날짜: `psql -d quant_platform -c "SELECT MAX(date) FROM ohlcv_data;"`
- [ ] 시장별 Ticker 분포:
  ```sql
  SELECT region, COUNT(*) FROM tickers GROUP BY region ORDER BY region;
  ```
- [ ] 테이블 크기 확인:
  ```sql
  SELECT tablename, pg_size_pretty(pg_total_relation_size(tablename))
  FROM pg_tables WHERE schemaname = 'public'
  ORDER BY pg_total_relation_size(tablename) DESC LIMIT 10;
  ```

---

## 📞 지원 및 문제 해결

### 문서 참조
1. [RESTORE_GUIDE.md](../scripts/RESTORE_GUIDE.md) - 상세 복원 가이드
2. [QUANT_DATABASE_SCHEMA.md](QUANT_DATABASE_SCHEMA.md) - DB 스키마 문서
3. [QUANT_DEVELOPMENT_WORKFLOWS.md](QUANT_DEVELOPMENT_WORKFLOWS.md) - 개발 워크플로우

### 로그 확인
- **Python 오류**: `~/spock/logs/`
- **PostgreSQL 로그**: `/opt/homebrew/var/log/postgresql@14.log`
- **Backup 로그**: `~/spock/backups/migration_YYYYMMDD_HHMMSS/`

### 긴급 롤백
복원 중 심각한 문제 발생 시:
1. 새 노트북 작업 중단
2. 기존 노트북으로 복귀
3. 백업 재수행
4. 문제 원인 파악 후 재시도

---

## 📊 마이그레이션 성공 기준

### 필수 요구사항 (Must Have)
- ✅ 데이터베이스 레코드 수 100% 일치
- ✅ 전체 기능 정상 동작 (DB, MCP, 백테스팅)
- ✅ 환경 변수 및 API 키 정상 작동
- ✅ Git 히스토리 완전 보존

### 선택 요구사항 (Nice to Have)
- ✅ 로그 파일 보존 (최근 30일)
- ✅ 백업 히스토리 보존
- ✅ 문서 및 예제 완전 복원

### 성능 기준
- 데이터베이스 쿼리 응답 시간: <1초 (10년 데이터)
- 백테스팅 실행 시간: <2초 (vectorbt, 5년 시뮬레이션)
- 오케스트레이터 dry-run: <10초

---

## 🎉 마이그레이션 완료 후 작업

### 1. 새 노트북에서 백업 수행
```bash
cd ~/spock
bash scripts/backup_full_system.sh
```

### 2. 백업 비교
```bash
# 레코드 수 비교
diff \
  /path/to/old/backup/database/data_counts.txt \
  ~/spock/backups/migration_YYYYMMDD_HHMMSS/database/data_counts.txt
```

### 3. 기존 노트북 정리
- [ ] 중요 파일 최종 확인
- [ ] 민감 정보 삭제 (.env, API 키)
- [ ] 데이터베이스 덤프 삭제
- [ ] 프로젝트 디렉토리 아카이브

### 4. 문서 업데이트
- [ ] CLAUDE.md 시스템 정보 업데이트
- [ ] README.md 업데이트
- [ ] 마이그레이션 날짜 기록

---

**마이그레이션 성공을 기원합니다! 🚀**

문제 발생 시 [RESTORE_GUIDE.md](../scripts/RESTORE_GUIDE.md)의 트러블슈팅 섹션을 참조하세요.
