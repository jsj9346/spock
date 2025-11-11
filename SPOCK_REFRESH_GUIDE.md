# Spock Database Refresh Tool - 사용 가이드

**크로스 플랫폼 데이터베이스 업데이트 도구** (Mac | Windows | Linux)

---

## 🚀 빠른 시작

### 1. 필수 설치

```bash
# Python 3.11+ 필요 (이미 설치됨)
python3 --version

# PostgreSQL 실행 확인
psql --version
```

### 2. 선택 설치 (컬러 출력용)

```bash
# 예쁜 컬러 출력을 위해 설치 (선택사항)
pip install colorama
```

### 3. 즉시 사용

```bash
# 대화형 메뉴 (초보자 권장)
python3 spock_refresh.py

# 빠른 업데이트 (최근 1주일)
python3 spock_refresh.py --quick

# 현재 상태 확인
python3 spock_refresh.py --status
```

---

## 📖 사용 방법

### 대화형 모드 (Interactive Menu)

**권장**: 초보자 및 일반 사용자

```bash
python3 spock_refresh.py
```

**화면 예시:**
```
╔════════════════════════════════════════════════════════════════╗
║   📊 Spock Database Refresh Tool                          ║
║   Current Status: 1,369,727 records | Latest: 2025-10-29    ║
╚════════════════════════════════════════════════════════════════╝

선택하세요:
  1. 🚀 Quick Refresh (5분) - 최근 1주일 데이터만
  2. 📈 Full Refresh (30분) - 전체 데이터 업데이트
  3. 🔄 Incremental (10분) - 누락된 데이터만
  4. ⚙️  Custom - 직접 설정
  5. 📅 Schedule Setup - 자동화 설정
  6. 📊 Status - 현재 데이터 상태 확인
  0. 🚪 종료

선택 (0-6): _
```

---

### CLI 모드 (Command Line)

**권장**: 고급 사용자 및 자동화

#### 기본 명령어

```bash
# 1. 빠른 업데이트 (5분) - 최근 1주일만
python3 spock_refresh.py --quick

# 2. 전체 업데이트 (30분) - 모든 데이터
python3 spock_refresh.py --full

# 3. 점진적 업데이트 (10분) - 누락된 데이터만
python3 spock_refresh.py --incremental

# 4. 현재 상태 확인
python3 spock_refresh.py --status
```

#### 고급 옵션

```bash
# 특정 지역만 업데이트
python3 spock_refresh.py --quick --regions KR US

# 미리보기 (실제 변경 없음)
python3 spock_refresh.py --full --dry-run

# 상세 로그 출력
python3 spock_refresh.py --quick --verbose
```

---

## 📋 업데이트 모드 비교

| 모드 | 시간 | 데이터 범위 | 사용 시기 |
|------|------|------------|----------|
| **Quick** | ~5분 | 최근 1주일 | 일일 업데이트 |
| **Full** | ~30분 | 전체 데이터 | 주간/월간 대청소 |
| **Incremental** | ~10분 | 누락 데이터만 | 오류 복구 |

### Quick Refresh (일일 권장)
```bash
python3 spock_refresh.py --quick
```
- **업데이트**: OHLCV, 펀더멘털, 배당
- **범위**: 최근 1주일
- **시간**: ~5분
- **사용**: 매일 아침 실행

### Full Refresh (주간/월간)
```bash
python3 spock_refresh.py --full
```
- **업데이트**: 티커, OHLCV, 펀더멘털, 배당
- **범위**: 전체 히스토리
- **시간**: ~30분
- **사용**: 주말 또는 월초

### Incremental (문제 해결)
```bash
python3 spock_refresh.py --incremental
```
- **업데이트**: 누락된 데이터만
- **범위**: 자동 감지
- **시간**: ~10분
- **사용**: 오류 발생 후 복구

---

## 📅 자동화 설정

### macOS (launchd)

**대화형 설정:**
```bash
python3 spock_refresh.py
# → 5번 선택: Schedule Setup
```

**수동 설정:**
```bash
# 1. plist 파일 생성 (스크립트가 자동으로 생성)
python3 spock_refresh.py --schedule

# 2. launchd 로드
launchctl load ~/Library/LaunchAgents/com.spock.refresh.plist

# 3. 상태 확인
launchctl list | grep spock

# 4. 테스트 실행
launchctl start com.spock.refresh
```

**직접 편집:**
```bash
# plist 파일 위치
~/Library/LaunchAgents/com.spock.refresh.plist

# 스케줄 변경 (예: 매일 오전 9시)
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>9</integer>
    <key>Minute</key>
    <integer>0</integer>
</dict>
```

---

### Linux (cron)

**대화형 설정:**
```bash
python3 spock_refresh.py
# → 5번 선택: Schedule Setup
```

**수동 설정:**
```bash
# 1. crontab 편집
crontab -e

# 2. 다음 라인 추가 (매일 오전 9시)
0 9 * * * /usr/bin/python3 /path/to/spock/spock_refresh.py --quick >> ~/spock_refresh.log 2>&1

# 3. 저장 후 확인
crontab -l
```

**cron 스케줄 예시:**
```bash
# 매일 오전 9시
0 9 * * * python3 /path/to/spock_refresh.py --quick

# 매주 일요일 오전 2시 (Full Refresh)
0 2 * * 0 python3 /path/to/spock_refresh.py --full

# 평일 오전 9시, 오후 6시 (Quick Refresh)
0 9,18 * * 1-5 python3 /path/to/spock_refresh.py --quick
```

---

### Windows (Task Scheduler)

**대화형 설정:**
```bash
python spock_refresh.py
# → 5번 선택: Schedule Setup
```

**GUI 설정:**
1. `Win + R` → `taskschd.msc` 실행
2. "작업 만들기..." 클릭
3. **일반 탭**:
   - 이름: `Spock Database Refresh`
   - 가장 높은 권한으로 실행 체크
4. **트리거 탭**:
   - 새로 만들기 → 매일, 오전 9:00
5. **작업 탭**:
   - 프로그램: `C:\Python311\python.exe`
   - 인수: `C:\Users\YourName\spock\spock_refresh.py --quick`
   - 시작 위치: `C:\Users\YourName\spock`
6. **확인** 클릭

**PowerShell 명령어 (관리자 권한):**
```powershell
$action = New-ScheduledTaskAction -Execute "python.exe" -Argument "C:\path\to\spock\spock_refresh.py --quick"
$trigger = New-ScheduledTaskTrigger -Daily -At 9am
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "SpockDatabaseRefresh" -Description "Spock Database Daily Refresh"
```

---

## 🔧 문제 해결

### 1. PostgreSQL 연결 실패

**증상:**
```
❌ Cannot connect to database
💡 Make sure PostgreSQL is running and .env is configured
```

**해결:**
```bash
# PostgreSQL 실행 확인
brew services list | grep postgresql  # macOS
systemctl status postgresql           # Linux
net start postgresql-x64-15           # Windows

# PostgreSQL 시작
brew services start postgresql@17     # macOS
sudo systemctl start postgresql       # Linux
net start postgresql-x64-15           # Windows

# .env 파일 확인
cat .env | grep DB_
```

---

### 2. 모듈 없음 오류

**증상:**
```
ModuleNotFoundError: No module named 'xxx'
```

**해결:**
```bash
# 필수 패키지 재설치
pip install -r requirements_quant.txt

# 선택 패키지 (컬러 출력)
pip install colorama
```

---

### 3. 권한 오류 (macOS/Linux)

**증상:**
```
Permission denied: spock_refresh.py
```

**해결:**
```bash
# 실행 권한 부여
chmod +x spock_refresh.py

# 또는 python3로 실행
python3 spock_refresh.py
```

---

### 4. API 레이트 리밋

**증상:**
```
Rate limit exceeded: DART API
```

**해결:**
- **Quick Refresh 사용**: Full Refresh 대신 Quick 사용
- **Incremental 모드**: 누락된 데이터만 업데이트
- **시간대 조정**: 새벽/심야 시간대 실행

---

### 5. 업데이트 중단 복구

**증상:**
업데이트 중 Ctrl+C로 중단 또는 오류 발생

**해결:**
```bash
# Incremental 모드로 재실행
python3 spock_refresh.py --incremental

# 또는 대화형 메뉴에서 "3. Incremental" 선택
python3 spock_refresh.py
```

---

## 📊 데이터 상태 확인

### CLI에서 확인

```bash
python3 spock_refresh.py --status
```

**출력 예시:**
```
📊 Current Database Status
============================================================
  Tickers:        21,098
  OHLCV Records:  1,369,727 (latest: 2025-10-29)
  Fundamentals:   46,452 (latest: 2025-10-28)
  Factor Scores:  1,303,491 (latest: 2025-10-29)
  Freshness:      ✅ Up to date!
============================================================
```

### PostgreSQL에서 직접 확인

```bash
psql -d quant_platform -c "
SELECT
    'OHLCV' as table_name,
    COUNT(*) as records,
    MAX(date) as latest
FROM ohlcv_data
UNION ALL
SELECT 'Fundamentals', COUNT(*), MAX(date) FROM ticker_fundamentals
UNION ALL
SELECT 'Factors', COUNT(*), MAX(date) FROM factor_scores;
"
```

---

## 💡 사용 팁

### 1. 일일 워크플로우

**아침 루틴 (5분):**
```bash
# 1. 상태 확인
python3 spock_refresh.py --status

# 2. Quick Refresh (필요시)
python3 spock_refresh.py --quick
```

---

### 2. 주간 워크플로우

**주말 대청소 (30분):**
```bash
# Full Refresh (주말에 실행)
python3 spock_refresh.py --full --regions KR US

# 또는 자동화 설정 (일요일 새벽 2시)
crontab -e
# 0 2 * * 0 python3 /path/to/spock_refresh.py --full
```

---

### 3. 백그라운드 실행

**macOS/Linux:**
```bash
# nohup으로 백그라운드 실행
nohup python3 spock_refresh.py --full > ~/spock_refresh.log 2>&1 &

# 진행 상황 확인
tail -f ~/spock_refresh.log
```

**Windows:**
```powershell
# PowerShell에서 백그라운드 실행
Start-Process python -ArgumentList "spock_refresh.py --full" -NoNewWindow -RedirectStandardOutput "spock_refresh.log"
```

---

### 4. Dry Run으로 미리보기

```bash
# 실제 변경 없이 미리보기
python3 spock_refresh.py --full --dry-run

# 예상 시간과 작업 내용 확인 후 실행
python3 spock_refresh.py --full
```

---

## 🎯 권장 사용 패턴

### 패턴 1: 적극적 투자자 (일일 거래)

```bash
# 매일 아침 9시 자동 실행 (launchd/cron)
python3 spock_refresh.py --quick

# 또는 수동 실행
python3 spock_refresh.py
# → "1. Quick Refresh" 선택
```

---

### 패턴 2: 장기 투자자 (주간 확인)

```bash
# 주말마다 Full Refresh
python3 spock_refresh.py --full

# 자동화 (일요일 새벽 2시)
# crontab: 0 2 * * 0 python3 spock_refresh.py --full
```

---

### 패턴 3: 백테스터 (연구용)

```bash
# 필요할 때만 Incremental
python3 spock_refresh.py --incremental

# 또는 특정 지역만
python3 spock_refresh.py --quick --regions KR
```

---

## 📞 지원

### 로그 파일 위치

- **업데이트 로그**: `logs/db_update_YYYYMMDD_HHMMSS.log`
- **스케줄 로그** (macOS): `~/spock_refresh.log`
- **스케줄 로그** (Linux): `~/spock_refresh.log`
- **스케줄 로그** (Windows): Task Scheduler 로그 확인

### 고급 옵션

더 많은 옵션은 기본 스크립트 참조:
```bash
python3 scripts/update_database.py --help
```

---

## 📝 변경 이력

**v1.0.0 (2025-11-04)**
- 초기 릴리스
- 대화형 메뉴 지원
- CLI 모드 지원
- 크로스 플랫폼 자동화 설정
- 상태 모니터링

---

## 🔐 보안 주의사항

1. **.env 파일 보호**: API 키가 포함된 .env 파일은 절대 공유하지 마세요
2. **로그 파일 주의**: 로그에 민감한 정보가 포함될 수 있습니다
3. **권한 최소화**: 스케줄링 시 필요한 최소 권한만 부여

---

**Happy Trading! 📈**
