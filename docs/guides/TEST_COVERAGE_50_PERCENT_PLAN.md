# 테스트 커버리지 50%+ 달성 계획

## 현재 상태 분석

### 코드베이스 규모
- **총 코드 라인**: 32,623 Stmts
- **현재 커버리지**: ~5.86% (약 1,900줄 커버)
- **목표 커버리지**: 50% (약 16,312줄 커버 필요)
- **추가 커버 필요**: 약 14,400줄

### 현재 테스트 현황
| 카테고리 | 테스트 수 | 상태 |
|---------|---------|------|
| test_value_factors.py | 33 | ✅ |
| test_momentum_factors.py | 27 | ✅ |
| tests/unit/ | 155 | ✅ (154 통과, 1 스킵) |
| **총계** | **215** | **모두 통과** |

### 핵심 모듈 현재 커버리지
| 모듈 | 커버리지 | 비고 |
|------|---------|------|
| comparison_analyzer.py | 92.13% | ✅ 우수 |
| collection_tracker.py | 78.14% | ✅ 양호 |
| factor_base.py | 53.38% | ⚠️ 중간 |
| value_factors.py | 28.32% | 부분 테스트 |
| momentum_factors.py | 25.14% | 부분 테스트 |

---

## Phase 1: 고영향 순수 함수 모듈 (예상 +8% = 14%)

**목표**: 외부 의존성 없는 순수 계산 모듈 테스트
**예상 소요**: 3-4일
**추가 커버리지**: ~2,600줄

### 1.1 Parsers 모듈 (1,200+ Stmts)
```
modules/parsers/
├── stock_parser.py          (56 Stmts)
├── us_stock_parser.py       (137 Stmts)
├── jp_stock_parser.py       (115 Stmts)
├── vn_stock_parser.py       (111 Stmts)
├── hk_stock_parser.py       (114 Stmts)
├── cn_stock_parser.py       (184 Stmts)
└── etf_parser.py            (76 Stmts)
```

**테스트 전략**:
- 입력: 샘플 마스터 파일 데이터 (fixture)
- 출력: 파싱된 ticker 정보 검증
- Edge cases: 빈 데이터, 잘못된 포맷, 특수문자

**예시 테스트**:
```python
@pytest.mark.parametrize("raw_data,expected", [
    ("005930|삼성전자|KOSPI|전기전자", {"ticker": "005930", "name": "삼성전자"}),
    ("", None),  # 빈 데이터
])
def test_kr_parser_parse_line(raw_data, expected):
    parser = KRStockParser()
    result = parser.parse_line(raw_data)
    assert result == expected
```

### 1.2 Risk 모듈 (368 Stmts)
```
modules/risk/
├── var_calculator.py        (104 Stmts)
├── cvar_calculator.py       (85 Stmts)
└── risk_base.py             (179 Stmts)
```

**테스트 전략**:
- VaR/CVaR 계산: 알려진 수익률 분포로 검증
- 수학적 정확성: scipy 결과와 비교
- Edge cases: 빈 배열, 단일 값, 음수 분산

**예시 테스트**:
```python
def test_var_calculation_normal_distribution():
    """정규분포에서 95% VaR = 1.645 * std"""
    returns = np.random.normal(0, 0.02, 1000)  # 2% 일일 변동성
    calculator = VaRCalculator(confidence=0.95)
    var = calculator.calculate(returns)
    expected_var = 1.645 * 0.02  # 약 3.29%
    assert abs(var - expected_var) < 0.005
```

### 1.3 Optimization 모듈 (400+ Stmts)
```
modules/optimization/
├── optimizer_base.py             (121 Stmts)
├── mean_variance_optimizer.py    (94 Stmts)
├── risk_parity_optimizer.py      (64 Stmts)
└── factor_optimizer.py           (114 Stmts)
```

**테스트 전략**:
- Mean-Variance: 2-3개 자산으로 수동 계산 검증
- Risk Parity: 동일 변동성 → 동일 가중치 검증
- 제약조건: 합계 100%, 개별 한도 준수

---

## Phase 2: 데이터 처리 모듈 Mock 테스트 (예상 +12% = 26%)

**목표**: DB/API 의존 모듈에 Mock 적용
**예상 소요**: 5-7일
**추가 커버리지**: ~3,900줄

### 2.1 Orchestrator (821 Stmts) - 최대 영향
```python
# Mock 전략
@patch('modules.orchestration.orchestrator.PostgresDatabaseManager')
@patch('modules.orchestration.orchestrator.KISAPIClient')
class TestOrchestrator:
    def test_refresh_single_region(self, mock_api, mock_db):
        mock_db.return_value.execute_query.return_value = [
            {'ticker': '005930', 'name': '삼성전자'}
        ]
        mock_api.return_value.get_ohlcv.return_value = pd.DataFrame({...})

        orchestrator = DatabaseUpdateOrchestrator()
        result = orchestrator.refresh_region('KR', mode='quick')

        assert result['status'] == 'success'
        mock_db.return_value.execute_query.assert_called()
```

**핵심 테스트 케이스**:
1. `refresh_region()` - 지역별 갱신
2. `_collect_ohlcv()` - OHLCV 수집 로직
3. `_calculate_dividend()` - 배당 계산
4. `_handle_error()` - 에러 처리
5. Checkpoint 저장/복원

### 2.2 Collection Adapters (1,500+ Stmts)
```
modules/collection/
├── kr_postgres_ohlcv_adapter.py    (303 Stmts)
├── dividend_collector.py           (215 Stmts)
├── etf_collector.py                (273 Stmts)
├── macro_data_adapter.py           (237 Stmts)
└── kr_etf_details_backfiller.py    (227 Stmts)
```

**Mock 전략**:
```python
@pytest.fixture
def mock_kis_api():
    with patch('modules.collection.kr_postgres_ohlcv_adapter.KISAPIClient') as mock:
        mock.return_value.get_ohlcv.return_value = pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=10),
            'open': [100]*10, 'high': [105]*10,
            'low': [95]*10, 'close': [102]*10, 'volume': [1000]*10
        })
        yield mock

def test_ohlcv_adapter_fetch(mock_kis_api, mock_db):
    adapter = KRPostgresOHLCVAdapter()
    result = adapter.fetch_ohlcv('005930', '2024-01-01', '2024-01-10')
    assert len(result) == 10
    assert 'close' in result.columns
```

### 2.3 DB Manager (612 Stmts - SQLite)
```python
# In-memory SQLite로 실제 테스트 가능
@pytest.fixture
def sqlite_db():
    db = SQLiteDatabaseManager(':memory:')
    db.execute_query('''
        CREATE TABLE tickers (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            region TEXT
        )
    ''')
    yield db
    db.close()

def test_insert_and_query(sqlite_db):
    sqlite_db.execute_query(
        "INSERT INTO tickers VALUES (?, ?, ?)",
        ('005930', '삼성전자', 'KR')
    )
    result = sqlite_db.execute_query(
        "SELECT * FROM tickers WHERE ticker = ?", ('005930',)
    )
    assert len(result) == 1
    assert result[0]['name'] == '삼성전자'
```

---

## Phase 3: 복잡한 비즈니스 로직 모듈 (예상 +14% = 40%)

**목표**: 핵심 비즈니스 로직 검증
**예상 소요**: 7-10일
**추가 커버리지**: ~4,500줄

### 3.1 Stock 분석 모듈 (2,000+ Stmts)
```
modules/
├── stock_utils.py              (567 Stmts)
├── stock_pre_filter.py         (311 Stmts)
├── stock_metadata_enricher.py  (384 Stmts)
├── stock_kelly_calculator.py   (203 Stmts)
├── stock_sentiment.py          (454 Stmts) - 외부 API 의존
└── stock_gpt_analyzer.py       (435 Stmts) - GPT API 의존
```

**테스트 가능 영역**:
- `stock_utils.py`: 순수 유틸리티 함수들
- `stock_pre_filter.py`: 필터링 로직 (Mock DB)
- `stock_kelly_calculator.py`: 켈리 공식 계산

**Mock 필요 영역**:
- `stock_sentiment.py`: 외부 감성 API Mock
- `stock_gpt_analyzer.py`: OpenAI API Mock

```python
@patch('modules.stock_gpt_analyzer.openai.ChatCompletion.create')
def test_gpt_analysis(mock_openai):
    mock_openai.return_value = {
        'choices': [{'message': {'content': '{"score": 75, "analysis": "긍정적"}'}}]
    }
    analyzer = StockGPTAnalyzer()
    result = analyzer.analyze('005930')
    assert result['score'] == 75
```

### 3.2 Screening 모듈 (879 Stmts)
```
modules/screening/
├── composite_scorer.py         (105 Stmts)
├── technical_calculator.py     (129 Stmts)
├── etf_data_collector.py       (171 Stmts)
├── etf_fundamental_scorer.py   (147 Stmts)
├── etf_screening_adapter.py    (273 Stmts)
└── stock_screener.py           (54 Stmts)
```

**테스트 전략**:
- `composite_scorer.py`: 점수 계산 로직 검증
- `technical_calculator.py`: 기술 지표 계산 (pandas-ta 비교)
- `stock_screener.py`: 스크리닝 조건 검증

### 3.3 Portfolio & Risk Manager (505 Stmts)
```
modules/
├── portfolio_allocator.py     (243 Stmts)
└── risk_manager.py            (262 Stmts)
```

**테스트 전략**:
- 포트폴리오 배분: 제약조건 준수 검증
- 리스크 한도: VaR 한도 초과 시 경고

---

## Phase 4: 통합 테스트 확대 (예상 +10% = 50%)

**목표**: E2E 시나리오 검증
**예상 소요**: 5-7일
**추가 커버리지**: ~3,200줄

### 4.1 백테스팅 통합 테스트
```python
@pytest.mark.integration
class TestBacktestIntegration:
    """백테스트 파이프라인 E2E 테스트"""

    @pytest.fixture
    def sample_strategy(self):
        return {
            'name': 'momentum_value',
            'factors': ['12M_Momentum', 'Dividend_Yield'],
            'weights': [0.6, 0.4],
            'rebalance_freq': 'monthly'
        }

    def test_full_backtest_pipeline(self, sample_strategy, test_db):
        """전체 백테스트 파이프라인 테스트"""
        # 1. 데이터 로드
        data_provider = PostgresDataProvider(test_db)
        data = data_provider.get_ohlcv(['005930', '000660'],
                                       '2023-01-01', '2023-12-31')

        # 2. 팩터 계산
        factor_engine = FactorEngine()
        factors = factor_engine.calculate_all(data, sample_strategy['factors'])

        # 3. 백테스트 실행
        engine = BacktestEngine()
        result = engine.run(data, factors, sample_strategy)

        # 4. 결과 검증
        assert result['sharpe_ratio'] is not None
        assert result['max_drawdown'] < 0
        assert len(result['trades']) > 0
```

### 4.2 데이터 파이프라인 통합 테스트
```python
@pytest.mark.integration
def test_data_collection_pipeline():
    """데이터 수집 파이프라인 E2E"""
    # Setup: Mock external APIs
    with patch_all_external_apis():
        orchestrator = DatabaseUpdateOrchestrator(test_mode=True)

        # Execute
        result = orchestrator.refresh_region('KR',
                                             mode='quick',
                                             tickers=['005930'])

        # Verify
        assert result['ohlcv_updated'] > 0
        assert result['errors'] == []
```

### 4.3 MCP 서버 통합 테스트
```python
@pytest.mark.integration
class TestMCPServerIntegration:
    """MCP 서버 도구 통합 테스트"""

    def test_get_fundamentals_tool(self, mcp_client):
        result = mcp_client.call_tool(
            'get_fundamentals',
            {'ticker': '005930', 'region': 'KR'}
        )
        assert 'revenue' in result
        assert 'net_income' in result

    def test_get_ratios_tool(self, mcp_client):
        result = mcp_client.call_tool(
            'get_ratios',
            {'ticker': '005930', 'region': 'KR', 'category': 'profitability'}
        )
        assert 'roe' in result
        assert 'roa' in result
```

---

## Mock 전략 상세

### 외부 의존성 목록
| 의존성 | 사용 모듈 | Mock 방법 |
|-------|---------|----------|
| PostgreSQL | 대부분 | `@patch('PostgresDatabaseManager')` |
| KIS API | OHLCV, 시세 | `@patch('KISAPIClient')` |
| yfinance | 해외 데이터 | `@patch('yfinance.Ticker')` |
| OpenAI | GPT 분석 | `@patch('openai.ChatCompletion')` |
| pykrx | KR 펀더멘털 | `@patch('pykrx.stock')` |
| DART API | 재무제표 | `responses` 라이브러리 |

### 공통 Fixture 설계
```python
# tests/conftest.py

@pytest.fixture
def mock_db():
    """모든 DB 호출 Mock"""
    with patch('modules.db_manager_postgres.PostgresDatabaseManager') as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock_instance

@pytest.fixture
def sample_ohlcv():
    """샘플 OHLCV 데이터"""
    return pd.DataFrame({
        'date': pd.date_range('2024-01-01', periods=252),
        'open': np.random.uniform(50000, 55000, 252),
        'high': np.random.uniform(55000, 60000, 252),
        'low': np.random.uniform(45000, 50000, 252),
        'close': np.random.uniform(50000, 55000, 252),
        'volume': np.random.randint(100000, 1000000, 252)
    })

@pytest.fixture
def sample_fundamentals():
    """샘플 펀더멘털 데이터"""
    return {
        'ticker': '005930',
        'revenue': Decimal('300000000000000'),
        'net_income': Decimal('40000000000000'),
        'total_assets': Decimal('400000000000000'),
        'roe': Decimal('12.5'),
        'per': Decimal('15.3')
    }
```

---

## 우선순위 및 일정

### 작업 우선순위 (ROI 기준)
| 순위 | 모듈 | Stmts | 난이도 | 영향도 | 예상 일수 |
|-----|------|-------|-------|-------|---------|
| 1 | parsers/* | 793 | 낮음 | 높음 | 2일 |
| 2 | risk/* | 368 | 중간 | 높음 | 2일 |
| 3 | orchestrator.py | 821 | 높음 | 매우 높음 | 3일 |
| 4 | optimization/* | 393 | 중간 | 높음 | 2일 |
| 5 | collection/* | 1,255 | 높음 | 높음 | 4일 |
| 6 | screening/* | 879 | 중간 | 중간 | 3일 |
| 7 | stock_*.py | 2,354 | 높음 | 중간 | 5일 |
| 8 | 통합 테스트 | - | 높음 | 높음 | 5일 |

### 예상 일정
| Phase | 기간 | 목표 커버리지 | 주요 작업 |
|-------|-----|-------------|---------|
| Phase 1 | Week 1 | 14% | Parsers, Risk, Optimization |
| Phase 2 | Week 2-3 | 26% | Orchestrator, Collection, DB |
| Phase 3 | Week 4-5 | 40% | Stock 모듈, Screening |
| Phase 4 | Week 6 | 50%+ | 통합 테스트, 마무리 |

---

## 성공 기준

### 정량적 기준
- [ ] 전체 커버리지 50% 이상
- [ ] 핵심 모듈 (factors, fundamentals) 80% 이상
- [ ] 테스트 통과율 95% 이상
- [ ] 테스트 실행 시간 5분 이내

### 정성적 기준
- [ ] 모든 공개 API에 대한 테스트 존재
- [ ] Edge case 처리 검증
- [ ] 회귀 방지 테스트 포함
- [ ] CI/CD 파이프라인 통합

---

## 참고: 테스트 실행 명령어

```bash
# 전체 테스트 + 커버리지
pytest tests/ --cov=modules --cov-report=html

# 특정 모듈만
pytest tests/ --cov=modules/factors --cov-report=term-missing

# 빠른 단위 테스트만
pytest tests/unit/ -v --tb=short

# 통합 테스트
pytest tests/integration/ -v -m integration

# 커버리지 리포트 생성
pytest tests/ --cov=modules --cov-report=html && open htmlcov/index.html
```

---

**작성일**: 2025-12-12
**버전**: 1.0.0
**상태**: 설계 완료, 구현 대기
