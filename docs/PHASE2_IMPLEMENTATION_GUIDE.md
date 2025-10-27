# Phase 2: Factor Library Development - Implementation Guide

**Quick Start Guide for Developers**

**Created**: 2025-10-21
**Version**: 1.0
**Dependencies**: Phase 1 Complete (PostgreSQL + TimescaleDB)

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Directory Structure](#directory-structure)
3. [Implementation Checklist](#implementation-checklist)
4. [Code Templates](#code-templates)
5. [Testing Guide](#testing-guide)
6. [Performance Targets](#performance-targets)
7. [Common Issues](#common-issues)

---

## Quick Start

### Prerequisites

✅ **Phase 1 Complete**: PostgreSQL + TimescaleDB operational
✅ **Python 3.11+**: Installed and configured
✅ **Dependencies**: Install quant platform requirements

```bash
# Install dependencies
pip3 install -r requirements_quant.txt

# Verify database connection
python3 -c "from modules.db_manager_postgres import DBManagerPostgres; db = DBManagerPostgres(); print('✅ Database connected')"

# Verify factor_scores table exists
psql -d quant_platform -c "\d factor_scores"
```

### Implementation Timeline

**Total Duration**: 2-3 weeks
**Team Size**: 1-2 developers
**Estimated LOC**: ~3,000 lines

**Week 1**: Factor Library Foundation (Base classes, Value factors, Momentum factors)
**Week 2**: Quality, Low-Vol, Size factors
**Week 3**: Calculation Engine, Combination Framework, Testing

---

## Directory Structure

```
modules/factors/
├── __init__.py                 # Package initialization
├── factor_base.py              # Base classes (FactorBase, FactorRegistry, etc.)
├── value_factors.py            # 5 value factors
├── momentum_factors.py         # 5 momentum factors
├── quality_factors.py          # 5 quality factors
├── low_vol_factors.py          # 5 low-volatility factors
├── size_factors.py             # 3 size factors
├── factor_calculator.py        # Batch calculation orchestrator
├── factor_combiner.py          # Factor combination strategies
└── factor_analyzer.py          # Factor performance analysis

tests/factors/
├── __init__.py
├── test_factor_base.py         # Unit tests for base classes
├── test_value_factors.py       # Tests for value factors
├── test_momentum_factors.py    # Tests for momentum factors
├── test_quality_factors.py     # Tests for quality factors
├── test_low_vol_factors.py     # Tests for low-volatility factors
├── test_size_factors.py        # Tests for size factors
├── test_factor_calculator.py   # Tests for calculation engine
├── test_factor_combiner.py     # Tests for combination framework
└── test_factor_analyzer.py     # Tests for factor analyzer

config/
└── factor_definitions.yaml     # Factor configuration file

docs/
├── PHASE2_FACTOR_LIBRARY_DESIGN.md  # Detailed design specification
├── PHASE2_IMPLEMENTATION_GUIDE.md   # This document
└── FACTOR_LIBRARY_REFERENCE.md      # Factor definitions and formulas (to be created)
```

---

## Implementation Checklist

### Week 1: Foundation and Core Factors

#### Day 1-2: Factor Base Class

- [ ] **Task 1.1.1**: Create `modules/factors/__init__.py`
  ```python
  """Factor Library for Quant Investment Platform."""
  __version__ = "1.0.0"
  ```

- [ ] **Task 1.1.2**: Implement `modules/factors/factor_base.py`
  - [ ] `FactorBase` abstract class (metadata, calculate, validate_inputs, normalize, save_to_db)
  - [ ] `FactorRegistry` for factory pattern
  - [ ] `FactorValidator` for input/output validation
  - [ ] `FactorCache` for in-memory caching
  - [ ] Unit tests: `tests/factors/test_factor_base.py`

**Acceptance Criteria**:
- ✅ All base classes implemented with docstrings
- ✅ Unit tests pass (>90% coverage)
- ✅ Validation logic handles edge cases (NULL values, missing columns, outliers)

#### Day 3-4: Value Factors

- [ ] **Task 1.2.1**: Implement `modules/factors/value_factors.py`
  - [ ] `PERatioFactor` (Price-to-Earnings ratio)
  - [ ] `PBRatioFactor` (Price-to-Book ratio)
  - [ ] `EVToEBITDAFactor` (Enterprise Value / EBITDA)
  - [ ] `DividendYieldFactor` (Dividend Yield)
  - [ ] `FCFYieldFactor` (Free Cash Flow Yield)

- [ ] **Task 1.2.2**: Unit tests: `tests/factors/test_value_factors.py`
  - [ ] Test P/E calculation (sample: Samsung Electronics 005930)
  - [ ] Test P/B calculation (sample: SK Hynix 000660)
  - [ ] Test dividend yield (sample: Korea Electric Power 015760)
  - [ ] Edge cases: Negative earnings, missing data, outliers

**Acceptance Criteria**:
- ✅ All 5 value factors implemented
- ✅ Unit tests pass with real database data
- ✅ Performance: <50ms per factor for 1,000 tickers

#### Day 5: Momentum Factors

- [ ] **Task 1.3.1**: Implement `modules/factors/momentum_factors.py`
  - [ ] `PriceMomentumFactor` (12-month return, excl. last month)
  - [ ] `RSIMomentumFactor` (RSI-based momentum)
  - [ ] `FiftyTwoWeekHighFactor` (Proximity to 52-week high)
  - [ ] `VolumeWeightedMomentumFactor` (Volume-adjusted momentum)
  - [ ] `EarningsMomentumFactor` (Earnings surprise momentum)

- [ ] **Task 1.3.2**: Unit tests: `tests/factors/test_momentum_factors.py`
  - [ ] Test 12-month momentum (verify excludes last month)
  - [ ] Test RSI momentum (range 0-100)
  - [ ] Edge cases: Insufficient historical data, low volume

**Acceptance Criteria**:
- ✅ All 5 momentum factors implemented
- ✅ Unit tests pass
- ✅ 12-month momentum correctly excludes last 21 days

### Week 2: Quality, Low-Vol, Size Factors

#### Day 1-2: Quality Factors

- [ ] **Task 2.1.1**: Implement `modules/factors/quality_factors.py`
  - [ ] `ROEFactor` (Return on Equity)
  - [ ] `DebtToEquityFactor` (Debt-to-Equity ratio)
  - [ ] `EarningsQualityFactor` (Accruals-based earnings quality)
  - [ ] `ProfitMarginFactor` (Net profit margin stability)
  - [ ] `CashFlowQualityFactor` (Operating cash flow / Net income)

- [ ] **Task 2.1.2**: Unit tests: `tests/factors/test_quality_factors.py`
  - [ ] Test ROE calculation (verify positive shareholder equity)
  - [ ] Test Debt-to-Equity (low D/E = high score)
  - [ ] Edge cases: Negative equity, zero debt

**Acceptance Criteria**:
- ✅ All 5 quality factors implemented
- ✅ Unit tests pass
- ✅ Earnings quality factor uses accruals methodology

#### Day 3-4: Low-Volatility Factors

- [ ] **Task 2.2.1**: Implement `modules/factors/low_vol_factors.py`
  - [ ] `VolatilityFactor` (60-day annualized volatility)
  - [ ] `BetaFactor` (Beta vs market index)
  - [ ] `MaxDrawdownFactor` (Maximum drawdown, 252-day)
  - [ ] `DownsideDeviationFactor` (Downside deviation, semi-volatility)
  - [ ] `CVaRFactor` (Conditional Value at Risk)

- [ ] **Task 2.2.2**: Unit tests: `tests/factors/test_low_vol_factors.py`
  - [ ] Test volatility calculation (verify annualization: × √252)
  - [ ] Test beta calculation (verify market index selection by region)
  - [ ] Test max drawdown (verify 252-day window)
  - [ ] Edge cases: Constant price (zero volatility), extreme volatility

**Acceptance Criteria**:
- ✅ All 5 low-volatility factors implemented
- ✅ Unit tests pass
- ✅ Beta factor uses correct market index per region (KOSPI for KR, SPX for US)

#### Day 5: Size Factors

- [ ] **Task 2.3.1**: Implement `modules/factors/size_factors.py`
  - [ ] `MarketCapFactor` (Market capitalization)
  - [ ] `LiquidityFactor` (Average daily trading volume)
  - [ ] `FreeFloatFactor` (Free float percentage)

- [ ] **Task 2.3.2**: Unit tests: `tests/factors/test_size_factors.py`
  - [ ] Test market cap calculation (price × shares outstanding)
  - [ ] Test liquidity (average volume, 30-day)
  - [ ] Edge cases: Missing shares outstanding, zero volume

**Acceptance Criteria**:
- ✅ All 3 size factors implemented
- ✅ Unit tests pass
- ✅ Market cap correctly inverted (smaller cap = higher score)

### Week 3: Calculation Engine and Combination Framework

#### Day 1-2: Factor Calculation Engine

- [ ] **Task 3.1.1**: Implement `modules/factors/factor_calculator.py`
  - [ ] `FactorCalculator` class
  - [ ] `register_all_factors()` method
  - [ ] `calculate_all_factors()` method (with parallel processing)
  - [ ] `calculate_single_factor()` method (for testing)
  - [ ] `_calculate_parallel()` method (ThreadPoolExecutor)
  - [ ] `_calculate_sequential()` method (for debugging)
  - [ ] `_get_tickers_for_region()` method

- [ ] **Task 3.1.2**: Create continuous aggregates for factor analysis
  ```sql
  -- Run in psql
  \i scripts/create_factor_continuous_aggregates.sql
  ```

- [ ] **Task 3.1.3**: Unit tests: `tests/factors/test_factor_calculator.py`
  - [ ] Test sequential calculation (all factors, KR market)
  - [ ] Test parallel calculation (verify consistency with sequential)
  - [ ] Test error handling (missing data, database failures)
  - [ ] Performance test: <5 seconds for full KR universe (18,661 tickers × 20 factors)

**Acceptance Criteria**:
- ✅ FactorCalculator implemented with parallel processing
- ✅ Continuous aggregates created (factor_scores_monthly, factor_correlation_daily)
- ✅ Unit tests pass
- ✅ Performance: <5 seconds for full universe calculation

#### Day 3-4: Factor Combination Framework

- [ ] **Task 3.2.1**: Implement `modules/factors/factor_combiner.py`
  - [ ] `FactorCombiner` abstract base class
  - [ ] `EqualWeightCombiner` (simple average)
  - [ ] `OptimizationCombiner` (Sharpe ratio optimization)
  - [ ] `RiskAdjustedCombiner` (inverse volatility weighting)
  - [ ] `MLCombiner` (XGBoost/RandomForest) - Optional

- [ ] **Task 3.2.2**: Unit tests: `tests/factors/test_factor_combiner.py`
  - [ ] Test equal weight combination (verify simple average)
  - [ ] Test optimization combination (verify Sharpe ratio maximization)
  - [ ] Test risk-adjusted combination (verify inverse volatility weights)
  - [ ] Test edge cases (single factor, all factors equal)

**Acceptance Criteria**:
- ✅ All 3-4 combiners implemented
- ✅ Unit tests pass
- ✅ Optimization combiner converges (<10 iterations)

#### Day 5: Factor Analyzer and Documentation

- [ ] **Task 3.3.1**: Implement `modules/factors/factor_analyzer.py`
  - [ ] `FactorAnalyzer` class
  - [ ] `analyze_factor_returns()` method (historical factor returns)
  - [ ] `factor_correlation()` method (factor independence check)
  - [ ] `factor_turnover()` method (factor stability analysis)

- [ ] **Task 3.3.2**: Create `docs/FACTOR_LIBRARY_REFERENCE.md`
  - [ ] Factor definitions and formulas (all 20+ factors)
  - [ ] Data requirements for each factor
  - [ ] Expected ranges and interpretations
  - [ ] Usage examples

- [ ] **Task 3.3.3**: End-to-end testing
  - [ ] Test full workflow: Calculate → Combine → Analyze
  - [ ] Test multi-region (KR, US, CN, HK, JP, VN)
  - [ ] Test historical backfill (last 365 days)

**Acceptance Criteria**:
- ✅ FactorAnalyzer implemented with performance metrics
- ✅ FACTOR_LIBRARY_REFERENCE.md complete
- ✅ End-to-end tests pass for all regions

---

## Code Templates

### Factor Implementation Template

```python
from modules.factors.factor_base import FactorBase
from typing import List, Dict
import pandas as pd
from datetime import date

class YourFactorName(FactorBase):
    """
    Brief description of the factor.

    Formula: Mathematical formula (LaTeX-style)

    Interpretation: Higher/Lower is better

    Data Requirements:
    - table.column_name (description)
    """

    @property
    def metadata(self) -> Dict:
        return {
            'name': 'your_factor_name',
            'category': 'value|momentum|quality|low_volatility|size',
            'description': 'Brief description',
            'formula': 'Mathematical formula',
            'data_requirements': ['column1', 'column2'],
            'invert': True|False  # True if lower values are better
        }

    def calculate(self, tickers: List[str], region: str,
                  as_of_date: date) -> pd.DataFrame:
        """Calculate factor scores for given tickers."""

        # Step 1: Fetch data from database
        query = """
        SELECT ticker, region, column1, column2
        FROM table_name
        WHERE ticker = ANY(%s) AND region = %s AND date = %s
        """

        with self.db_manager.get_connection() as conn:
            df = pd.read_sql(query, conn, params=(tickers, region, as_of_date))

        # Step 2: Calculate factor score
        df['score'] = df['column1'] / df['column2']  # Example calculation

        # Step 3: Handle edge cases
        df = df[df['column2'] != 0]  # Remove division by zero

        # Step 4: Invert if needed (lower is better)
        if self.metadata['invert']:
            df['score'] = 1 / df['score']

        # Step 5: Normalize
        df = self.normalize(df, method='zscore')

        # Step 6: Add metadata
        df['date'] = as_of_date

        return df[['ticker', 'region', 'date', 'score', 'percentile']]
```

### Unit Test Template

```python
import unittest
from datetime import date
from modules.db_manager_postgres import DBManagerPostgres
from modules.factors.your_module import YourFactorName

class TestYourFactorName(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up database connection for all tests."""
        cls.db_manager = DBManagerPostgres()
        cls.factor = YourFactorName(cls.db_manager)

    def test_metadata(self):
        """Test factor metadata."""
        metadata = self.factor.metadata
        self.assertEqual(metadata['name'], 'your_factor_name')
        self.assertEqual(metadata['category'], 'value')  # Adjust as needed
        self.assertIn('formula', metadata)
        self.assertIn('data_requirements', metadata)

    def test_calculate_single_ticker(self):
        """Test factor calculation for single ticker."""
        tickers = ['005930']  # Samsung Electronics (KR)
        region = 'KR'
        as_of_date = date(2025, 10, 21)

        df = self.factor.calculate(tickers, region, as_of_date)

        # Assertions
        self.assertEqual(len(df), 1)
        self.assertIn('ticker', df.columns)
        self.assertIn('score', df.columns)
        self.assertIn('percentile', df.columns)
        self.assertEqual(df['ticker'].iloc[0], '005930')

    def test_calculate_multiple_tickers(self):
        """Test factor calculation for multiple tickers."""
        tickers = ['005930', '000660', '035720']  # Samsung, SK Hynix, Kakao
        region = 'KR'
        as_of_date = date(2025, 10, 21)

        df = self.factor.calculate(tickers, region, as_of_date)

        # Assertions
        self.assertGreater(len(df), 0)
        self.assertLessEqual(len(df), 3)  # May be less if data missing

    def test_edge_cases(self):
        """Test edge cases (missing data, zero values, outliers)."""
        # Test with ticker that has missing data
        tickers = ['INVALID']
        region = 'KR'
        as_of_date = date(2025, 10, 21)

        df = self.factor.calculate(tickers, region, as_of_date)

        # Should return empty DataFrame (no error)
        self.assertEqual(len(df), 0)

    def test_normalization(self):
        """Test z-score normalization."""
        tickers = ['005930', '000660', '035720']
        region = 'KR'
        as_of_date = date(2025, 10, 21)

        df = self.factor.calculate(tickers, region, as_of_date)

        if len(df) > 0:
            # Z-scores should have mean ~0, std ~1
            mean_score = df['score'].mean()
            std_score = df['score'].std()

            self.assertAlmostEqual(mean_score, 0, delta=0.5)
            self.assertAlmostEqual(std_score, 1, delta=0.5)

    def test_performance(self):
        """Test calculation performance (<50ms for 1,000 tickers)."""
        import time

        # Get 1,000 KR tickers
        query = "SELECT ticker FROM tickers WHERE region = 'KR' LIMIT 1000"
        with self.db_manager.get_connection() as conn:
            df = pd.read_sql(query, conn)
        tickers = df['ticker'].tolist()

        region = 'KR'
        as_of_date = date(2025, 10, 21)

        start_time = time.time()
        df = self.factor.calculate(tickers, region, as_of_date)
        elapsed_time = time.time() - start_time

        # Performance assertion (<50ms)
        self.assertLess(elapsed_time, 0.05, f"Calculation took {elapsed_time:.3f}s (>50ms)")

if __name__ == '__main__':
    unittest.main()
```

---

## Testing Guide

### Running Tests

```bash
# Run all factor tests
python3 -m pytest tests/factors/ -v

# Run specific test module
python3 -m pytest tests/factors/test_value_factors.py -v

# Run with coverage
python3 -m pytest tests/factors/ --cov=modules/factors --cov-report=html

# Run performance tests
python3 -m pytest tests/factors/ -k "performance" -v
```

### Test Data Setup

**Option 1**: Use existing Phase 1 data (recommended)
```bash
# Verify data exists
psql -d quant_platform -c "SELECT COUNT(*) FROM ohlcv_data WHERE region = 'KR';"
```

**Option 2**: Load sample test data
```bash
# Load test fixtures
python3 tests/fixtures/load_test_data.py
```

### Coverage Targets

- **Unit Tests**: >90% code coverage
- **Integration Tests**: All critical paths tested
- **Performance Tests**: All factors meet performance targets

---

## Performance Targets

### Factor Calculation

| Metric | Target | Measurement |
|--------|--------|-------------|
| Single factor (1,000 tickers) | <50ms | Unit tests |
| All factors (parallel, 18,661 tickers) | <5 seconds | Integration tests |
| Database insertion | >1,000 rows/sec | Bulk insert |
| Memory usage | <2GB RAM | Full universe calculation |

### Database Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Factor retrieval (single ticker, all factors) | <10ms | Query benchmarks |
| Factor retrieval (all tickers, single factor) | <100ms | Query benchmarks |
| Continuous aggregate refresh | <30 seconds | TimescaleDB jobs |
| Compression ratio | ~10x | TimescaleDB compression |

### Code Quality

| Metric | Target | Tool |
|--------|--------|------|
| Test coverage | >90% | pytest-cov |
| Linting | 0 errors | pylint, flake8 |
| Type hints | 100% | mypy |
| Documentation | All public methods | docstrings |

---

## Common Issues

### Issue 1: Database Connection Errors

**Symptom**: `psycopg2.OperationalError: could not connect to server`

**Solution**:
```bash
# Verify PostgreSQL is running
brew services list | grep postgresql

# Restart if needed
brew services restart postgresql@17

# Verify connection
psql -d quant_platform -c "SELECT 1;"
```

### Issue 2: Missing Historical Data

**Symptom**: `calculate()` returns empty DataFrame

**Solution**:
```bash
# Check data availability
psql -d quant_platform -c "
SELECT region, COUNT(*) FROM ohlcv_data GROUP BY region;
"

# If data missing, run data collection
python3 scripts/backfill_historical_data.py --region KR --days 365
```

### Issue 3: Slow Factor Calculation

**Symptom**: Factor calculation >5 seconds for full universe

**Solution**:
1. **Enable parallel processing**: Set `parallel=True` in `calculate_all_factors()`
2. **Increase max_workers**: Set `max_workers=16` in FactorCalculator config
3. **Verify database indexes**: Run `EXPLAIN ANALYZE` on slow queries
4. **Optimize SQL queries**: Use batch fetching, avoid N+1 queries

### Issue 4: Out of Memory Errors

**Symptom**: `MemoryError` during factor calculation

**Solution**:
1. **Batch processing**: Calculate factors in batches of 5,000 tickers
2. **Reduce max_workers**: Set `max_workers=4` (lower parallelism)
3. **Clear cache**: Implement cache eviction in FactorCache

### Issue 5: Factor Correlation >0.7

**Symptom**: High correlation between factors (multicollinearity)

**Solution**:
1. **Remove redundant factors**: Use factor_analyzer.py to identify correlations
2. **Use PCA**: Apply Principal Component Analysis to reduce dimensions
3. **Adjust factor weights**: Use optimization-based combiner to handle correlation

---

## Next Steps

### After Phase 2 Implementation

1. **Phase 3: Backtesting Engine**
   - Integrate backtrader, zipline, vectorbt
   - Transaction cost model
   - Performance metrics

2. **Phase 4: Portfolio Optimization**
   - Mean-variance optimizer
   - Risk parity optimizer
   - Black-Litterman model

3. **Phase 5: Risk Management**
   - VaR/CVaR calculator
   - Stress testing
   - Correlation analyzer

4. **Phase 6: Web Interface**
   - Streamlit dashboard
   - Strategy builder
   - Portfolio analytics

---

## Support & Resources

### Documentation

- **Design Spec**: `docs/PHASE2_FACTOR_LIBRARY_DESIGN.md`
- **Implementation Guide**: `docs/PHASE2_IMPLEMENTATION_GUIDE.md` (this document)
- **Factor Reference**: `docs/FACTOR_LIBRARY_REFERENCE.md` (to be created)
- **Database Schema**: `docs/DATABASE_SCHEMA_DIAGRAM.md`

### Code Examples

- **Factor Implementation**: See templates above
- **Unit Tests**: See `tests/factors/` directory
- **Integration Tests**: See `tests/integration/` directory

### Academic References

- **Fama-French Models**: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- **Quantitative Finance**: "Quantitative Equity Portfolio Management" by Chincarini & Kim
- **Factor Investing**: "Your Complete Guide to Factor-Based Investing" by Berkin & Swedroe

---

**Document Status**: Ready for Implementation
**Last Updated**: 2025-10-21
**Version**: 1.0
