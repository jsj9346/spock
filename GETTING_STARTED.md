# 시작하기 (Getting Started)

**처음 사용하시는 분을 위한 친절한 가이드**

---

## 🎯 이 프로젝트는 무엇인가요?

**Quant Investment Platform**은 데이터 기반 투자 전략을 개발하고 검증하는 체계적인 연구 플랫폼입니다.

### 3줄 요약

- 📊 **백테스팅**: 과거 데이터로 투자 전략을 테스트하고 검증
- 🔬 **팩터 분석**: 통계적으로 검증된 가치, 모멘텀, 품질 팩터 분석
- 💼 **포트폴리오 최적화**: 리스크 관리와 함께 최적의 자산 배분 계산

### 무엇을 할 수 있나요?

✅ **전략 개발**: 나만의 투자 전략을 만들고 과거 데이터로 테스트
✅ **성과 분석**: 샤프 비율, 최대 낙폭, 승률 등 성과 지표 자동 계산
✅ **리스크 관리**: VaR, CVaR 등 정량적 리스크 측정
✅ **포트폴리오 최적화**: 효율적 투자선(Efficient Frontier) 계산
✅ **멀티팩터 분석**: 가치, 모멘텀, 품질 팩터 조합 연구

### 무엇을 할 수 없나요?

❌ **실시간 자동매매**: 현재는 연구 및 백테스팅 전용입니다
❌ **투자 조언**: 이 소프트웨어는 투자 자문이 아닙니다
❌ **수익 보장**: 과거 성과가 미래 수익을 보장하지 않습니다

---

## 👥 누구를 위한 것인가요?

### 주 사용자
- **퀀트 연구자**: 투자 전략을 개발하고 통계적으로 검증하는 분
- **개인 투자자**: 증거 기반 포트폴리오를 구축하려는 분
- **데이터 과학자**: 금융 데이터 분석과 머신러닝에 관심 있는 분

### 필요한 배경 지식
- ✅ **Python 기초**: 기본 문법과 패키지 설치 경험
- ✅ **투자 기본 개념**: 주식, 수익률, 리스크 등 기본 용어 이해
- ⭐ **통계/확률 지식**: 있으면 좋지만 필수는 아님
- ⭐ **데이터베이스 경험**: 있으면 좋지만 자동 설정됨

---

## 🚀 3단계로 시작하기 (15분)

### 1단계: 환경 설정 (5분)

```bash
# 1. 저장소 클론
git clone https://github.com/jsj9346/spock.git
cd spock

# 2. 가상 환경 생성 (권장)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 필요한 패키지 설치
pip install -r requirements_quant.txt
```

**예상 설치 시간**: 약 3-5분 (인터넷 속도에 따라 다름)

### 2단계: 데이터베이스 설정 (5분)

#### PostgreSQL + TimescaleDB 설치

**macOS (Homebrew)**:
```bash
brew install postgresql@17 timescaledb
timescaledb-tune --quiet --yes
brew services start postgresql@17
```

**Ubuntu/Debian**:
```bash
sudo apt install postgresql-17 timescaledb-2-postgresql-17
sudo systemctl start postgresql
```

**Windows**:
- [PostgreSQL 설치](https://www.postgresql.org/download/windows/)
- [TimescaleDB 설치](https://docs.timescale.com/install/latest/self-hosted/installation-windows/)

#### 데이터베이스 초기화

```bash
# 1. 데이터베이스 생성
createdb quant_platform

# 2. TimescaleDB 확장 활성화
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# 3. 스키마 초기화 (테이블, 인덱스 생성)
python3 scripts/init_postgres_schema.py
```

**성공 메시지**:
```
✅ Database created: quant_platform
✅ TimescaleDB extension enabled
✅ Schema initialized: 12 tables, 8 indexes
✅ Hypertables created: ohlcv_data
```

### 3단계: 첫 백테스트 실행 (5분)

```bash
# 모멘텀-가치 복합 전략 백테스트 (2020-2023년)
python3 quant_platform.py backtest \
  --strategy momentum_value \
  --start 2020-01-01 \
  --end 2023-12-31 \
  --initial-capital 100000000 \
  --engine vectorbt
```

**예상 결과**:
```
🔄 백테스팅 시작...
✅ 데이터 로딩: 3,000개 종목 (5초)
✅ 전략 실행: 150회 리밸런싱 (10초)
✅ 성과 계산 완료

📊 백테스트 결과:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
총 수익률:        +45.2%
연평균 수익률:    +12.8%
샤프 비율:        1.65
최대 낙폭:        -18.3%
승률:             58.2%
총 거래 수:       420회
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 📚 다음 단계 학습 경로

### 🔰 초보자 (프로젝트 처음 사용)

**1단계**: [빠른 시작 가이드](QUICKSTART.md)
→ 5분 안에 기본 기능 체험

**2단계**: [프로젝트 개요](README.md)
→ 전체 기능과 아키텍처 이해

**3단계**: [CLI 사용법](docs/CLI_USAGE_GUIDE.md)
→ 명령줄 인터페이스 사용법

**4단계**: [백테스팅 가이드](docs/BACKTESTING_GUIDE.md)
→ 올바른 백테스팅 방법 학습

### 💻 개발자 (코드 기여 또는 커스터마이징)

**1단계**: [전체 프로젝트 가이드](CLAUDE.md)
→ 프로젝트 구조와 개발 철학

**2단계**: [데이터베이스 스키마](docs/DATABASE_SCHEMA.md)
→ 데이터 구조와 쿼리 패턴

**3단계**: [백테스팅 엔진 비교](docs/QUANT_BACKTESTING_ENGINES.md)
→ 엔진별 특징과 선택 가이드

**4단계**: [팩터 라이브러리](docs/FACTOR_LIBRARY_REFERENCE.md)
→ 팩터 정의와 계산 방법

**5단계**: [개발 워크플로우](docs/QUANT_DEVELOPMENT_WORKFLOWS.md)
→ 실제 개발 절차와 명령어

### 🚀 운영자 (프로덕션 환경 구축)

**1단계**: [배포 가이드](docs/DEPLOYMENT_GUIDE.md)
→ 서버 배포 및 설정

**2단계**: [운영 매뉴얼](docs/OPERATIONS_RUNBOOK.md)
→ 일상적인 운영 절차

**3단계**: [모니터링 가이드](docs/QUANT_OPERATIONS.md)
→ Prometheus + Grafana 설정

---

## ❓ 자주 묻는 질문 (FAQ)

### 일반 질문

**Q1: 실제 거래가 가능한가요?**
A: 아니요, 현재 버전은 **연구 및 백테스팅 전용**입니다. 실제 거래는 지원하지 않습니다.

**Q2: 어떤 시장을 지원하나요?**
A: 한국(KR), 미국(US), 중국(CN), 홍콩(HK), 일본(JP), 베트남(VN) 6개 시장을 지원합니다.

**Q3: 무료로 사용할 수 있나요?**
A: 네, MIT 라이선스로 무료 사용, 수정, 배포가 가능합니다. 단, **투자 손실에 대한 책임은 사용자에게 있습니다**.

**Q4: 프로그래밍 경험이 없어도 사용할 수 있나요?**
A: Python 기본 문법과 터미널 사용법을 알면 사용 가능합니다. 완전 초보자라면 먼저 Python 기초를 학습하는 것을 권장합니다.

### 기술 질문

**Q5: 왜 PostgreSQL을 사용하나요? SQLite는 안 되나요?**
A:
- PostgreSQL + TimescaleDB: 무제한 과거 데이터, 시계열 최적화, 프로덕션 안정성
- SQLite: 테스트용으로는 가능하지만, 대량 데이터 처리에는 부적합

**Q6: 백테스팅 엔진이 여러 개인 이유는?**
A:
- **Custom Engine**: 프로덕션 안정성, 세밀한 제어
- **vectorbt**: 연구용, 100배 빠른 파라미터 최적화
- **backtrader/zipline**: 선택사항, 특수 기능

**Q7: 데이터는 어디서 가져오나요?**
A:
- 한국 시장: KIS API (한국투자증권)
- 글로벌 시장: Polygon.io, yfinance (설정 필요)

**Q8: 얼마나 많은 과거 데이터가 필요한가요?**
A:
- **최소**: 2년 (신뢰도 낮음)
- **권장**: 5년 이상 (통계적 유의성 확보)
- **이상적**: 10년 이상 (다양한 시장 사이클 포함)

### 성과 관련 질문

**Q9: 좋은 백테스트 결과란?**
A:
- 샤프 비율: >1.5 (업계 표준: 1.0)
- 최대 낙폭: <15%
- 승률: >55%
- 거래 수: >100회 (통계적 유의성)

**Q10: 백테스트 결과를 실제 거래에서 기대할 수 있나요?**
A: **아니요**. 백테스트는 과거 데이터 기반이며, 실제 거래에서는 슬리피지, 수수료, 시장 충격 등으로 성과가 낮아집니다. 보수적으로 50-70% 정도만 기대하세요.

### 트러블슈팅

**Q11: 설치 중 오류가 발생합니다**
A: [트러블슈팅 가이드](TROUBLESHOOTING_INDEX.md) 참조 또는 다음 확인:
```bash
# Python 버전 확인 (3.11 이상 필요)
python3 --version

# pip 업그레이드
pip install --upgrade pip

# 의존성 재설치
pip install -r requirements_quant.txt --force-reinstall
```

**Q12: 데이터베이스 연결 오류**
A:
```bash
# PostgreSQL 실행 확인
brew services list | grep postgresql  # macOS
sudo systemctl status postgresql      # Linux

# 데이터베이스 존재 확인
psql -l | grep quant_platform

# .env 파일 확인
cat .env | grep DB_
```

**Q13: 백테스트가 너무 느립니다**
A:
- **vectorbt 사용**: `--engine vectorbt` (100배 빠름)
- **기간 단축**: 먼저 1년 데이터로 테스트
- **종목 수 제한**: 상위 500개 종목만 분석

---

## 🎓 학습 리소스

### 프로젝트 문서
- 📖 [전체 문서 목록](DOCUMENTATION_INDEX.md)
- 🐛 [문제 해결 가이드](TROUBLESHOOTING_INDEX.md)
- 🏗️ [프로젝트 구조](PROJECT_INDEX.md)
- 🔧 [API 통합 가이드](API_INTEGRATION_GUIDE.md)

### 외부 리소스

**백테스팅 프레임워크**:
- [vectorbt 공식 문서](https://vectorbt.dev/)
- [backtrader 가이드](https://www.backtrader.com/)
- [zipline 튜토리얼](https://zipline.ml4trading.io/)

**포트폴리오 최적화**:
- [PyPortfolioOpt 문서](https://pyportfolioopt.readthedocs.io/)
- [cvxpy 예제](https://www.cvxpy.org/examples/)

**학술 논문** (팩터 연구):
- Fama & French (1992) - Three-Factor Model
- Carhart (1997) - Momentum Factor
- Asness et al. (2013) - Value and Momentum Everywhere
- Novy-Marx (2013) - Quality Factor

### 온라인 강의
- [Quantopian Lectures](https://www.quantopian.com/lectures) - 무료 퀀트 투자 강의
- [Coursera: Financial Engineering](https://www.coursera.org/learn/financial-engineering-1)
- [QuantConnect Tutorials](https://www.quantconnect.com/tutorials/)

---

## 💡 팁과 모범 사례

### 백테스팅 팁
1. **항상 거래 비용 포함**: 수수료, 슬리피지를 현실적으로 설정
2. **walk-forward 최적화 사용**: 과적합 방지
3. **다양한 시장 환경 테스트**: 상승장, 하락장, 횡보장 모두 검증
4. **최소 100회 거래 확보**: 통계적 유의성을 위해 충분한 샘플 필요

### 리스크 관리 팁
1. **포지션 크기 제한**: 단일 종목 5% 이하
2. **섹터 분산**: 한 섹터 40% 이하
3. **스톱로스 설정**: 최대 낙폭 15% 제한
4. **현금 보유**: 포트폴리오의 10-20% 현금 유지

### 개발 팁
1. **작은 것부터 시작**: 단순한 전략으로 시작해서 점진적으로 복잡하게
2. **버전 관리 사용**: Git으로 전략 변경 이력 추적
3. **문서화**: 전략의 가정과 논리를 명확히 기록
4. **코드 리뷰**: 동료에게 전략 로직 검토 요청

---

## 📧 도움이 필요하신가요?

### 문서 및 지원
- 📖 **문서**: 프로젝트 루트의 `docs/` 디렉토리
- 🐛 **버그 리포트**: [GitHub Issues](https://github.com/jsj9346/spock/issues)
- ✉️ **이메일**: jsj9346@gmail.com
- 💬 **토론**: [GitHub Discussions](https://github.com/jsj9346/spock/discussions)

### 기여하기
프로젝트 개선에 참여하고 싶으신가요?
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a Pull Request

[기여 가이드라인](CONTRIBUTING.md) 참조 (준비 중)

---

## ⚠️ 중요 고지사항

**투자 위험 경고**:
- 이 소프트웨어는 **교육 및 연구 목적**으로 제공됩니다
- 과거 성과가 미래 수익을 보장하지 않습니다
- 모든 투자는 원금 손실의 위험이 있습니다
- 투자 결정 전 전문가와 상담하세요
- 개발자는 투자 손실에 대해 책임지지 않습니다

**라이선스**:
- MIT 라이선스 (상업적 사용 가능)
- 무보증 제공 (AS-IS)
- 자세한 내용은 [LICENSE](LICENSE) 파일 참조

---

## 🗺️ 다음 단계

축하합니다! 이제 Quant Investment Platform을 시작할 준비가 되었습니다.

### 체크리스트
- [ ] Python 3.11+ 설치 완료
- [ ] PostgreSQL + TimescaleDB 설치 완료
- [ ] 프로젝트 클론 및 패키지 설치 완료
- [ ] 데이터베이스 초기화 완료
- [ ] 첫 백테스트 실행 성공
- [ ] 다음 학습 자료 확인

### 추천 학습 순서
1. ✅ **GETTING_STARTED.md** (이 문서) ← 현재 위치
2. ⏭️ [QUICKSTART.md](QUICKSTART.md) - 5분 빠른 시작
3. ⏭️ [README.md](README.md) - 프로젝트 전체 개요
4. ⏭️ [BACKTESTING_GUIDE.md](docs/BACKTESTING_GUIDE.md) - 백테스팅 모범 사례
5. ⏭️ [CLAUDE.md](CLAUDE.md) - 개발자용 상세 가이드

---

**마지막 업데이트**: 2025-11-12
**버전**: 1.0.0
**상태**: 초보자 가이드 완성 ✅

**즐거운 퀀트 연구 되세요! 📊✨**
