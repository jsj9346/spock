# Spock 프로젝트 - 주식 자동매매 시스템

## 🎯 프로젝트 개요

Spock은 makenaide 암호화폐 자동매매 시스템을 기반으로 개발하는 **한국투자증권 API 기반 주식 자동매매 시스템**입니다. 검증된 makenaide 아키텍처와 분석 엔진을 활용하여 주식시장(한국 및 글로벌)에 특화된 자동매매 플랫폼을 구축합니다.

### 핵심 철학
- **전략 우선, 자동화는 도구**: makenaide와 동일한 철학
- **"지지 않는 것"에 집중**: 장기 생존과 복리 구조 목표
- **손실은 짧고 수익은 길게**: 체계적인 리스크 관리
- **검증된 패턴 활용**: makenaide에서 검증된 Weinstein/Minervini/O'Neil 전략

## 🏗️ Makenaide 재사용성 분석

### 🚀 **높은 재사용성 (거의 그대로 사용 가능)**

#### 📊 **핵심 분석 엔진**
```
kelly_calculator.py           # Kelly 공식 기반 포지션 사이징 - 완전 재사용 가능
market_sentiment.py          # 시장 감정 분석 (Fear&Greed Index) - 주식용으로 약간 수정
gpt_analyzer.py             # GPT 기반 차트 패턴 분석 - 완전 재사용 가능
integrated_scoring_system.py # 통합 점수 시스템 - 완전 재사용 가능
layered_scoring_engine.py    # 다층 점수 엔진 - 완전 재사용 가능
basic_scoring_modules.py     # 기본 점수 모듈 - 완전 재사용 가능
adaptive_scoring_config.py   # 적응형 점수 설정 - 완전 재사용 가능
```

#### 🛠️ **유틸리티 & 인프라**
```
utils.py                    # 범용 유틸리티 함수 - 완전 재사용 가능
db_manager_sqlite.py        # SQLite DB 관리자 - 완전 재사용 가능
init_db_sqlite.py          # DB 초기화 스크립트 - 스키마만 수정
monitoring_system.py        # 모니터링 시스템 - 완전 재사용 가능
failure_tracker.py          # 실패 추적기 - 완전 재사용 가능
auto_recovery_system.py     # 자동 복구 시스템 - 완전 재사용 가능
```

### 🔄 **중간 재사용성 (API 부분만 수정)**

#### 📈 **데이터 수집 & 처리**
```
data_collector.py           # 업비트 API → 한국투자증권 API로 변경
scanner.py                  # 종목 스캔 - KRW 마켓 → 주식 종목으로 변경
update_technical_indicators.py # 기술적 지표 업데이트 - 데이터 소스만 변경
```

#### 💰 **거래 실행**
```
trading_engine.py           # 업비트 API → 한국투자증권 API로 변경
```

#### 🎯 **메인 오케스트레이터**
```
makenaide.py               # 전체 파이프라인 - API 연결 부분만 수정하여 spock.py로 변경
```

### 📋 **낮은 재사용성 (참고용)**

#### 🔧 **AWS/배포 관련**
```
setup_sns_topics.py         # SNS 설정 - 주식용 알림으로 재구성 참고
deploy_*.py                 # 배포 스크립트들 - 구조 참고용
ec2_*.py                   # EC2 관련 - 구조 참고용
lambda_*.py                # Lambda 관련 - 로컬 환경에서는 불필요
```

#### 🧪 **테스트 & 디버그**
```
debug_*.py                 # 디버그 스크립트들 - 구조 참고용
real_data_integration_test.py # 테스트 - 주식 데이터로 재작성 참고
compare_scoring_systems.py   # 점수 시스템 비교 - 참고용
```

## 📁 **추천 Spock 프로젝트 구조**

```
~/spock/
├── spock.py                    # makenaide.py 기반 메인 오케스트레이터
├── modules/
│   ├── kis_data_collector.py    # data_collector.py 기반 (한국투자증권 API)
│   ├── stock_scanner.py         # scanner.py 기반 (주식 종목 스캔)
│   ├── kis_trading_engine.py    # trading_engine.py 기반 (KIS API)
│   ├── kelly_calculator.py      # 그대로 복사
│   ├── market_sentiment.py      # 주식용으로 약간 수정
│   ├── gpt_analyzer.py         # 그대로 복사
│   ├── integrated_scoring_system.py # 그대로 복사
│   ├── layered_scoring_engine.py    # 그대로 복사
│   ├── basic_scoring_modules.py     # 그대로 복사
│   ├── adaptive_scoring_config.py   # 그대로 복사
│   ├── stock_utils.py          # utils.py 기반
│   └── db_manager_sqlite.py    # 그대로 복사
├── config/
│   ├── kis_api_config.py       # 한국투자증권 API 설정
│   ├── stock_blacklist.json    # 주식 블랙리스트
│   └── market_schedule.json    # 주식시장 운영시간 설정
├── data/
│   ├── spock_local.db          # SQLite 데이터베이스
│   └── backups/                # 백업 디렉토리
├── logs/
│   └── spock.log               # 로그 파일
└── tests/
    ├── test_kis_api.py         # KIS API 테스트
    └── test_scoring_system.py  # 점수 시스템 테스트
```

## 🎯 **개발 로드맵**

### Phase 1: 기반 환경 구축 (완전 재사용)
- [ ] `utils.py`, `db_manager_sqlite.py` 복사
- [ ] SQLite 스키마 설계 (`init_db_sqlite.py` 참고)
- [ ] 기본 로깅 및 모니터링 시스템 구축
- [ ] 프로젝트 디렉토리 구조 생성

### Phase 2: 분석 엔진 구축 (완전 재사용)
- [ ] `kelly_calculator.py` 복사 및 테스트
- [ ] `gpt_analyzer.py` 복사 및 테스트
- [ ] `integrated_scoring_system.py` 및 관련 모듈 복사
- [ ] 점수 시스템 주식용 파라미터 조정

### Phase 3: API 연동 개발 (중간 재사용)
- [ ] 한국투자증권 API 연동 모듈 개발
- [ ] `data_collector.py` → `kis_data_collector.py` 변환
- [ ] `trading_engine.py` → `kis_trading_engine.py` 변환
- [ ] `scanner.py` → `stock_scanner.py` 변환

### Phase 4: 메인 파이프라인 구축
- [ ] `makenaide.py` → `spock.py` 변환
- [ ] 주식시장 특화 로직 추가
- [ ] 시장 시간 관리 (장 시작/종료 시간)
- [ ] 통합 테스트 및 검증

### Phase 5: 주식시장 특화 기능
- [ ] 주식시장 감정 지표 추가 (VIX, 외국인 매매 등)
- [ ] 섹터별 분석 기능
- [ ] 글로벌 시장 연동 (미국, 일본 등)
- [ ] 배당일정 관리

## 💰 **예상 개발 효율성**

### 코드 재사용률
- **완전 재사용**: 약 40% (핵심 분석 엔진 + 유틸리티)
- **중간 재사용**: 약 30% (API 연동 부분만 수정)
- **신규 개발**: 약 30% (주식 특화 기능)

### 개발 시간 단축 효과
- **전체 개발 시간**: 약 **70% 단축** 예상
- **검증된 로직 활용**: 품질 안정성 확보
- **테스트 시간 단축**: 기존 테스트 케이스 활용 가능

## 🔧 **주요 수정 포인트**

### API 연동 변경
```python
# Before (makenaide - 업비트)
import pyupbit
upbit = pyupbit.Upbit(access, secret)

# After (spock - 한국투자증권)
import kis_api
kis = kis_api.KISApi(app_key, app_secret)
```

### 데이터 구조 변경
```python
# Before (암호화폐 - 24시간 거래)
ticker_format = "KRW-BTC"

# After (주식 - 장중만 거래)
ticker_format = "005930"  # 삼성전자
market_hours = "09:00-15:30"
```

### 시장 감정 지표 확장
```python
# Before (암호화폐)
- Fear&Greed Index
- BTC 트렌드

# After (주식)
- Fear&Greed Index
- VIX 지수
- 외국인 매매 동향
- 기관 매매 동향
```

## 🚀 **개발 시작 가이드**

1. **환경 설정**
   ```bash
   mkdir ~/spock
   cd ~/spock
   python -m venv spock_env
   source spock_env/bin/activate
   ```

2. **기본 모듈 복사**
   ```bash
   cp ~/makenaide/utils.py ~/spock/modules/stock_utils.py
   cp ~/makenaide/db_manager_sqlite.py ~/spock/modules/
   cp ~/makenaide/kelly_calculator.py ~/spock/modules/
   # ... 기타 재사용 모듈들
   ```

3. **한국투자증권 API 설정**
   - KIS Developers 가입 및 API 키 발급
   - 모의투자 환경 설정
   - API 연동 테스트

4. **첫 번째 파이프라인 구축**
   - 종목 스캔 → 데이터 수집 → 점수 계산 → 포지션 사이징

이렇게 구조화하면 makenaide의 검증된 로직을 최대한 활용하면서 주식시장에 특화된 자동매매 시스템을 효율적으로 개발할 수 있습니다.