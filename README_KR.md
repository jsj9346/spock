# Spock - Quant Investment Platform (퀀트 투자 플랫폼)

증거 기반 투자 전략 개발을 위한 체계적인 정량적 연구 및 포트폴리오 관리 플랫폼

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-316192.svg)](https://www.postgresql.org/)
[![TimescaleDB](https://img.shields.io/badge/TimescaleDB-2.11+-orange.svg)](https://www.timescale.com/)

## ⚠️ 투자 위험 고지

**이 소프트웨어는 교육 및 연구 목적으로만 제공됩니다.**

- 과거 성과가 미래 수익을 보장하지 않습니다
- 개발자는 이 플랫폼 사용으로 발생한 금융 손실에 대해 책임지지 않습니다
- 거래 및 투자는 원금 손실 위험을 수반합니다
- 이 소프트웨어는 금융, 투자, 법률, 세무 자문을 구성하지 않습니다
- 투자 결정 전 전문 금융 자문가와 상담하세요
- 백테스팅 결과는 실제 거래 조건(슬리피지, 유동성, 시장 충격)을 반영하지 못할 수 있습니다
- 모든 투자 전략은 리스크를 수반하며 이익을 보장하지 않습니다

**이 소프트웨어를 사용함으로써 귀하는 이러한 위험을 이해하고 수용함을 인정합니다.**

---

## 🚀 빠른 링크

- **[👉 시작 가이드 (한국어)](GETTING_STARTED.md)** - ⭐ **신규 사용자는 여기서 시작!**
- **[👉 Getting Started (English)](GETTING_STARTED_EN.md)** - ⭐ **New users start here!**
- **[📚 문서 인덱스](DOCUMENTATION_INDEX.md)** - 전체 문서 로드맵
- **[⚡ 빠른 시작](QUICKSTART.md)** - 5분 설정 가이드

---

## 🎯 프로젝트 개요

**Spock - Quant Investment Platform**은 체계적인 전략 개발, 백테스팅, 포트폴리오 최적화를 위해 설계된 종합 연구 프레임워크입니다. 자동 매매 실행에서 엄격한 정량적 연구와 증거 기반 의사결정에 초점을 맞춘 플랫폼으로 전환되었습니다.

### 핵심 철학

- **🎯 백테스팅 엔진 우선**: 전략 개발 전 백테스팅 인프라 완성 및 검증
- **📊 연구 중심 접근**: 배포 전 엄격한 백테스팅을 통한 전략 검증
- **🔬 증거 기반 의사결정**: 데이터 기반 팩터 분석 및 체계적 신호 생성
- **⚖️ 체계적 리스크 관리**: 정량적 리스크 평가 및 포트폴리오 수준 제약
- **🔄 재현 가능한 결과**: 결정론적 백테스트 결과를 가진 버전 관리 전략
- **📈 멀티팩터 프레임워크**: 강건한 알파 생성을 위한 검증된 팩터(Value, Momentum, Quality) 결합

### 타겟 사용자

- **정량 연구자**: 투자 전략을 개발하고 검증하는 연구자
- **포트폴리오 관리자**: 체계적인 자산 배분 및 리밸런싱을 추구하는 관리자
- **개인 투자자**: 증거 기반 팩터 포트폴리오를 구축하는 투자자
- **학술 연구자**: 팩터 성과 및 포트폴리오 최적화를 연구하는 학자

---

## ✨ 주요 기능

### 1. 멀티팩터 분석 엔진

팩터 기반 종목 선정을 통한 체계적 알파 생성:

- **가치 팩터**: P/E, P/B, EV/EBITDA, 배당수익률, FCF 수익률
- **모멘텀 팩터**: 12개월 수익률, RSI 모멘텀, 52주 고점 근접도
- **품질 팩터**: ROE, 부채비율, 이익 품질, 이익률 안정성
- **저변동성 팩터**: 과거 변동성, 베타, 최대 낙폭, CVaR
- **규모 팩터**: 시가총액, 거래량, 자유유동주식

**팩터 결합 방법**:
- 동일 가중
- 최적화 기반 가중 (샤프 비율 최대화)
- 리스크 조정 가중 (역변동성)
- 머신러닝 (XGBoost/RandomForest)

### 2. 하이브리드 백테스팅 엔진

**프로덕션**: 커스텀 이벤트 기반 엔진 (안정적, 구현 완료 ✅)
- 실행 로직 완전 제어
- 현실적인 거래 비용 시뮬레이션
- 실시간 포트폴리오 추적에 적합

**연구**: vectorbt 통합 (100배 빠른 파라미터 최적화 🎯)
- 벡터화 백테스팅 (NumPy 기반)
- 파라미터 튜닝에 이상적
- 내장 성과 지표
- 최소한의 통합 노력

**고급**: backtrader/zipline 지원 (선택사항 📋)
- backtrader: 실시간 거래 브로커 통합
- zipline: 기관급 리스크 모델

**성과 지표**:
- 수익률: 총 수익, 연간 수익, 롤링 수익
- 리스크 조정: 샤프, 소르티노, 칼마 비율
- 낙폭: 최대, 평균, 지속 기간
- 승률, 리스크 지표 (VaR, CVaR, 변동성, 베타)

### 3. 포트폴리오 최적화

리스크 제약 하의 최적 자산 배분:

- **평균-분산 최적화** (Markowitz): 효율적 투자선 계산
- **리스크 패리티**: 각 자산의 동등한 리스크 기여
- **블랙-리터만 모델**: 시장 균형 + 투자자 견해를 결합한 베이지안 접근
- **켈리 기준**: 기하 성장 최대화를 위한 다자산 확장

**제약 유형**:
- 포지션 한도 (자산별 최소/최대)
- 섹터 한도 (섹터당 최대 40%)
- 회전율 제약 (리밸런싱 최대 20%)
- 현금 준비금 요구사항
- 롱 온리 또는 롱-숏

### 4. 리스크 관리 시스템

정량적 리스크 평가 및 모니터링:

- **VaR (위험 가치)**: 과거, 파라메트릭, 몬테카를로 방법
- **CVaR (조건부 VaR)**: 테일 리스크 포착
- **스트레스 테스팅**: 과거 시나리오 (2008 위기, 2020 COVID, 2022 약세장)
- **상관관계 분석**: 자산 상관 행렬, 팩터 익스포저
- **리스크 한도**: 포트폴리오 VaR <5%, 단일 포지션 VaR <1%, 섹터 집중도 <40%

### 5. 인터랙티브 대시보드

Streamlit 기반 연구 워크벤치:

- **백테스트 엔진 모니터**: 엔진 성능 및 검증
- **백테스트 결과**: 전략 성과 시각화
- **포트폴리오 분석**: 현재 보유 종목 및 리스크 지표
- **팩터 분석**: 팩터 성과 및 상관관계
- **리스크 대시보드**: VaR, CVaR, 스트레스 테스트

---

## 🏗️ 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                     Streamlit 연구 대시보드                      │
│  전략 빌더 | 백테스트 결과 | 포트폴리오 분석                     │
└───────────────────┬─────────────────────────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│                        FastAPI 백엔드                            │
│  /strategies | /backtest | /optimize | /risk | /data            │
└───────────────────┬─────────────────────────────────────────────┘
                    │
┌───────────────────┴─────────────────────────────────────────────┐
│                    핵심 엔진 레이어                              │
├──────────────────┬──────────────────┬──────────────────────────┤
│  멀티팩터        │  백테스팅        │  포트폴리오 최적화       │
│  분석 엔진       │  엔진            │  (cvxpy)                 │
│  - 가치          │  - 커스텀 ✅     │  - 평균-분산             │
│  - 모멘텀        │  - vectorbt 🎯   │  - 리스크 패리티         │
│  - 품질          │  - backtrader 📋 │  - 블랙-리터만           │
│  - 저변동성      │  - zipline 📋    │  - 켈리 다자산           │
│  - 규모          │                  │  - 제약 처리             │
└──────────────────┴──────────────────┴──────────────────────────┘
                    │
┌───────────────────▼─────────────────────────────────────────────┐
│            데이터 레이어 (PostgreSQL + TimescaleDB)              │
│  하이퍼테이블: ohlcv_data (연속 집계)                           │
│  테이블: tickers, factors, strategies, data/backtest_results         │
│  보존: 무제한 (1년 후 압축)                                     │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🚀 빠른 시작

### 사전 요구사항

- Python 3.11+
- PostgreSQL 15+
- TimescaleDB 2.11+

### 설치

```bash
# 저장소 클론
git clone https://github.com/jsj9346/spock.git
cd spock

# 가상 환경 생성
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 종속성 설치
pip install -r requirements_quant.txt

# PostgreSQL + TimescaleDB 설치 (macOS)
brew install postgresql timescaledb
timescaledb-tune --quiet --yes

# 데이터베이스 생성
createdb quant_platform
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# 스키마 초기화
python3 scripts/init_postgres_schema.py

# 환경 설정
cp .env.example .env
# API 키와 데이터베이스 자격증명으로 .env 편집
```

### 사용법

**대시보드 실행**:
```bash
streamlit run dashboard/app.py
# http://localhost:8501 접속
```

**API 실행**:
```bash
uvicorn api.main:app --reload --port 8000
# http://localhost:8000/docs에서 API 문서 확인
```

**백테스트 실행**:
```bash
python3 quant_platform.py backtest \
  --strategy momentum_value \
  --start 2018-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000 \
  --engine vectorbt
```

**포트폴리오 최적화**:
```bash
python3 quant_platform.py optimize \
  --method mean_variance \
  --target-return 0.15 \
  --constraints config/optimization_constraints.yaml
```

---

## 📚 문서

- **아키텍처**: [docs/QUANT_PLATFORM_ARCHITECTURE.md](docs/QUANT_PLATFORM_ARCHITECTURE.md)
- **팩터 라이브러리**: [docs/FACTOR_LIBRARY_REFERENCE.md](docs/FACTOR_LIBRARY_REFERENCE.md)
- **백테스팅 가이드**: [docs/BACKTESTING_GUIDE.md](docs/BACKTESTING_GUIDE.md)
- **최적화 쿡북**: [docs/OPTIMIZATION_COOKBOOK.md](docs/OPTIMIZATION_COOKBOOK.md)
- **데이터베이스 스키마**: [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md)

---

## 📈 성공 지표

### 백테스팅 엔진 (Phase 1 - 핵심)
- ✅ 커스텀 엔진: 5년 시뮬레이션 <30초
- ✅ vectorbt: 5년 시뮬레이션 <1초
- ✅ 정확도 검증: 참조 백테스트와 >95% 일치
- ✅ 테스트 커버리지: >90% 코드 커버리지

### 전략 성능
- 타겟 샤프 비율: >1.5 (업계 표준: 1.0)
- 백테스트 정확도: >90% 일관성
- 팩터 독립성: 상관관계 <0.5
- 최소 거래 수: >100 (통계적 유의성)

### 포트폴리오 성능
- 총 수익률: 연간 >15% (vs KOSPI ~8%)
- 샤프 비율: >1.5
- 최대 낙폭: <15%
- 승률: >55%
- VaR (95%): 포트폴리오 가치의 <5%

---

## 🧪 연구 모범 사례

- **과적합 회피**: 표본 내가 아닌 walk-forward 최적화 사용
- **거래 비용**: 항상 현실적인 수수료 및 슬리피지 포함
- **생존 편향**: 시점 데이터 사용 (선행 금지)
- **데이터 품질**: 분할, 배당, 오류 검증
- **통계적 유의성**: 의미 있는 결과를 위해 >100 거래 필요

---

## 🔧 환경 변수 설정

`.env` 파일 생성:
```
# 데이터베이스
DB_HOST=localhost
DB_PORT=5432
DB_NAME=quant_platform
DB_USER=your_user
DB_PASSWORD=your_password

# API 키
KIS_APP_KEY=your_kis_app_key
KIS_APP_SECRET=your_kis_app_secret
POLYGON_API_KEY=your_polygon_key
```

---

## 🤝 기여하기

기여를 환영합니다! 다음 가이드라인을 따라주세요:

1. 저장소 포크
2. 피처 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 변경사항 커밋 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 푸시 (`git push origin feature/amazing-feature`)
5. Pull Request 열기

**다음 사항을 확인해주세요**:
- 모든 테스트 통과 (`pytest tests/`)
- PEP 8 스타일 가이드 준수
- 문서 업데이트
- 백테스팅 결과 재현 가능

---

## 📝 라이선스

이 프로젝트는 MIT 라이선스로 제공됩니다 - 자세한 내용은 [LICENSE](LICENSE) 파일 참조

**주요 사항**:
- ✅ 자유롭게 사용, 수정, 배포 가능
- ✅ 상업적 사용 허용
- ✅ 보증 제공 안 함
- ⚠️ 투자 손실에 대한 개발자 책임 없음

---

## 🙏 감사의 말

**Spock에서 재사용된 구성요소 (70%)**:
- 데이터 수집 인프라 (KIS API 어댑터, 시장 파서)
- 기술 분석 모듈 (MA, RSI, MACD, 볼린저 밴드)
- 리스크 관리 (켈리 계산기, ATR 기반 포지션 사이징)
- 모니터링 인프라 (Prometheus + Grafana)

**라이브러리 및 프레임워크**:
- [pandas](https://pandas.pydata.org/) - 데이터 처리
- [NumPy](https://numpy.org/) - 수치 계산
- [vectorbt](https://vectorbt.dev/) - 빠른 백테스팅
- [cvxpy](https://www.cvxpy.org/) - 볼록 최적화
- [TimescaleDB](https://www.timescale.com/) - 시계열 데이터베이스
- [Streamlit](https://streamlit.io/) - 인터랙티브 대시보드
- [FastAPI](https://fastapi.tiangolo.com/) - 모던 웹 프레임워크

**연구 참고문헌**:
- Fama & French (1992) - 3팩터 모델
- Carhart (1997) - 4팩터 모델 (모멘텀)
- Asness, Moskowitz & Pedersen (2013) - 가치와 모멘텀 어디서나
- Novy-Marx (2013) - 품질 팩터
- Ang, Hodrick, Xing & Zhang (2006) - 저변동성 이상현상

---

## 📧 연락처

- GitHub: [@jsj9346](https://github.com/jsj9346)
- Email: jsj9346@gmail.com

---

## 🗓️ 프로젝트 현황

**최종 업데이트**: 2025-11-12
**버전**: 1.1.0 (한국어)
**현재 단계**: Phase 1 - 백테스팅 엔진 개발 및 검증 (Week 1-2)
**개발 단계**: 엔진 우선 개발 단계

**로드맵**:
- ✅ Phase 0: 프로젝트 정리 및 Git 설정
- 🔄 Phase 1: 백테스팅 엔진 (진행 중 - **우선순위**)
- 📋 Phase 2: 데이터베이스 마이그레이션
- 📋 Phase 3: 팩터 라이브러리
- 📋 Phase 4: 전략 개발
- 📋 Phase 5: 웹 인터페이스

---

**❤️ 정량적 연구와 체계적 투자를 위해 제작되었습니다**
