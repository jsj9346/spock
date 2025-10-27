# Factor Library Reference Guide

Comprehensive guide to the Quant Investment Platform's multi-factor analysis library.

---

## Overview

The factor library implements **18 quantitative factors** across 5 categories for systematic stock selection and portfolio construction.

**Design Philosophy**:
- Evidence-based factors from academic research (Fama-French, Carhart, etc.)
- Standardized z-score normalization for cross-sectional ranking
- Modular architecture enabling factor combination strategies
- PostgreSQL integration for historical factor analysis

---

## Factor Categories

### 1. Value Factors (4 factors)

Fundamental valuation metrics seeking undervalued stocks.

#### 1.1 P/E Ratio Factor (`PERatioFactor`)

**Formula**: `Score = -P/E`  
**Higher Score = Lower P/E = Undervalued**

**Data Source**: `ticker_fundamentals.per` (pykrx, DART, yfinance)

**Interpretation**:
| P/E Range | Classification | Investment Implication |
|-----------|---------------|------------------------|
| < 10 | Undervalued | Deep value opportunity |
| 10-20 | Fair value | Balanced valuation |
| 20-30 | Growth premium | High growth expectations |
| > 30 | Overvalued | Speculative or unprofitable |

**Example**:
```python
from modules.factors import PERatioFactor

pe_factor = PERatioFactor()
result = pe_factor.calculate(data=None, ticker='005930')

# Output: FactorResult(
#   ticker='005930',
#   factor_name='PE_Ratio',
#   raw_value=-12.5,  # Negated for ranking
#   z_score=0.85,     # Above average value
#   percentile=75.3   # Top quartile
# )
```

#### 1.2 P/B Ratio Factor (`PBRatioFactor`)

**Formula**: `Score = -P/B`  
**Higher Score = Lower P/B = Undervalued**

**Data Source**: `ticker_fundamentals.pbr`

**Interpretation**:
| P/B Range | Classification | Investment Implication |
|-----------|---------------|------------------------|
| < 1.0 | Deep value | Trading below book value |
| 1-3 | Fair value | Balanced valuation |
| 3-5 | Growth premium | Quality/growth premium |
| > 5 | Expensive | High expectations or intangibles |

#### 1.3 EV/EBITDA Factor (`EVToEBITDAFactor`)

**Formula**: `Score = -(Enterprise Value / EBITDA)`  
**Higher Score = Lower EV/EBITDA = Undervalued**

**Data Source**: `ticker_fundamentals.ev_ebitda` (yfinance)

**Advantages over P/E**:
- Accounts for capital structure (debt + equity)
- Less affected by accounting differences
- Better for comparing companies with different leverage

**Interpretation**:
| EV/EBITDA Range | Classification |
|-----------------|----------------|
| < 10 | Undervalued |
| 10-15 | Fair value |
| > 15 | Expensive or high growth |

#### 1.4 Dividend Yield Factor (`DividendYieldFactor`)

**Formula**: `Score = Dividend Yield` (NOT negated)  
**Higher Score = Higher Yield = Income Opportunity**

**Data Source**: `ticker_fundamentals.dividend_yield`

**Interpretation**:
| Yield Range | Classification |
|-------------|----------------|
| > 4% | High yield (value/income stock) |
| 2-4% | Moderate yield |
| < 2% | Low yield (growth stock) |
| 0% | No dividend (reinvestment strategy) |

---

### 2. Momentum Factors (3 factors)

Trend-following strategies based on price and technical indicators.

#### 2.1 12-Month Momentum (`TwelveMonthMomentumFactor`)

**Formula**: `Return = (Price_today / Price_12m_ago) - 1`  
**Higher Score = Stronger Uptrend**

**Data Source**: `ohlcv_data` (252 trading days)

**Methodology**:
- Excludes last month (avoids short-term reversal)
- Minimum 220 trading days required
- Caps outliers at ±3 sigma

**Academic Foundation**:
- Jegadeesh & Titman (1993): "Returns to Buying Winners and Selling Losers"
- Momentum premium: Stocks with strong past returns continue outperforming

**Example**:
```python
from modules.factors import TwelveMonthMomentumFactor

momentum = TwelveMonthMomentumFactor()
result = momentum.calculate(data=ohlcv_data, ticker='005930')

# Output: FactorResult(
#   raw_value=0.25,    # 25% return over 12 months
#   z_score=1.2,       # Above average momentum
#   percentile=85.7    # Top 15% of stocks
# )
```

#### 2.2 RSI Momentum (`RSIMomentumFactor`)

**Formula**: `RSI = 100 - (100 / (1 + RS))` where `RS = Avg Gain / Avg Loss`  
**Optimal Range**: 50-70 (bullish momentum)

**Data Source**: `ohlcv_data` (14-day RSI)

**Interpretation**:
| RSI Range | Signal |
|-----------|--------|
| > 70 | Overbought (potential reversal) |
| 50-70 | Bullish momentum |
| 30-50 | Neutral |
| < 30 | Oversold (potential bounce) |

#### 2.3 Short-Term Momentum (`ShortTermMomentumFactor`)

**Formula**: `Return = (Price_today / Price_1m_ago) - 1`  
**Higher Score = Recent Price Strength**

**Use Case**: Tactical allocation, short-term trading signals

---

### 3. Quality Factors (9 factors)

Business quality and financial health metrics.

#### 3.1 ROE Factor (`ROEFactor`)

**Formula**: `ROE = Net Income / Shareholders' Equity`  
**Higher Score = Better Profitability**

**Data Source**: `ticker_fundamentals` (quarterly/annual reports)

**Interpretation**:
| ROE Range | Classification |
|-----------|----------------|
| > 20% | Excellent (sustainable competitive advantage) |
| 15-20% | Good |
| 10-15% | Average |
| < 10% | Poor (capital inefficiency) |

**Example**:
```python
from modules.factors import ROEFactor

roe = ROEFactor()
result = roe.calculate(data=None, ticker='005930')

# Samsung Electronics typically has ROE ~15-20%
# Output: FactorResult(
#   raw_value=18.5,    # 18.5% ROE
#   z_score=1.1,       # Above average quality
#   percentile=78.2
# )
```

#### 3.2 ROA Factor (`ROAFactor`)

**Formula**: `ROA = Net Income / Total Assets`

#### 3.3 Operating Margin (`OperatingMarginFactor`)

**Formula**: `Operating Margin = Operating Income / Revenue`

#### 3.4 Debt-to-Equity Ratio (`DebtToEquityFactor`)

**Formula**: `Score = -(Debt / Equity)`  
**Higher Score = Lower Leverage = Less Risk**

**Interpretation**:
| D/E Range | Classification |
|-----------|----------------|
| < 0.5 | Conservative (low debt) |
| 0.5-1.5 | Moderate leverage |
| > 1.5 | Aggressive (high debt risk) |

#### 3.5 Accruals Ratio (`AccrualsRatioFactor`)

**Formula**: `Accruals = (Net Income - Operating Cash Flow) / Total Assets`  
**Lower Accruals = Higher Quality Earnings**

**Academic Foundation**:
- Sloan (1996): "Do Stock Prices Fully Reflect Information in Accruals?"
- High accruals predict lower future returns (earnings quality concern)

---

### 4. Low-Volatility Factors (3 factors)

Risk reduction and defensive strategies.

#### 4.1 Historical Volatility (`HistoricalVolatilityFactor`)

**Formula**: `Volatility = Std Dev(daily returns) × √252`  
**Lower Score = Lower Risk**

**Data Source**: `ohlcv_data` (60-day rolling window)

**Interpretation**:
| Annualized Vol | Classification |
|----------------|----------------|
| < 15% | Low volatility (defensive) |
| 15-30% | Moderate volatility |
| > 30% | High volatility (speculative) |

#### 4.2 Beta Factor (`BetaFactor`)

**Formula**: `Beta = Cov(stock, market) / Var(market)`  
**Lower Beta = Less Market Sensitivity**

**Requires**: Market index data (KOSPI for KR stocks)

#### 4.3 Maximum Drawdown (`MaxDrawdownFactor`)

**Formula**: `Max Drawdown = (Peak - Trough) / Peak`  
**Lower Drawdown = More Stable**

---

### 5. Size Factors (3 factors)

Market capitalization and liquidity metrics.

#### 5.1 Market Cap Factor (`MarketCapFactor`)

**Formula**: `Market Cap = Price × Shares Outstanding`  
**Lower Market Cap = Size Premium (SMB)**

**Academic Foundation**:
- Fama-French (1992): Small-cap stocks outperform large-cap

#### 5.2 Liquidity Factor (`LiquidityFactor`)

**Formula**: `Liquidity = Average Daily Volume × Price`

#### 5.3 Float Factor (`FloatFactor`)

**Formula**: `Free Float % = Publicly Traded Shares / Total Shares`

---

## Factor Combination Strategies

### Equal-Weight Combiner

```python
from modules.factors import EqualWeightCombiner, PERatioFactor, ROEFactor

factors = [PERatioFactor(), ROEFactor()]
combiner = EqualWeightCombiner(factors=factors)

results = [factor.calculate(data, ticker) for factor in factors]
combined_score = combiner.combine(results)
```

### Category-Weight Combiner

```python
from modules.factors import CategoryWeightCombiner

combiner = CategoryWeightCombiner(
    category_weights={
        'value': 0.4,
        'momentum': 0.3,
        'quality': 0.3
    }
)
```

### Optimization-Based Combiner

```python
from modules.factors import OptimizationCombiner

# Uses historical factor performance to determine optimal weights
combiner = OptimizationCombiner(
    objective='sharpe_ratio',  # Maximize risk-adjusted returns
    lookback_days=252
)
```

---

## Database Integration

### Saving Factor Scores

```python
from modules.factors import PERatioFactor
from modules.db_manager_postgres import PostgresDatabaseManager

db = PostgresDatabaseManager()
factor = PERatioFactor()

# Calculate for universe
results = []
for ticker in ['005930', '000660', '035420']:
    result = factor.calculate(data=None, ticker=ticker)
    if result:
        results.append(result)

# Save to database
saved_count = factor.save_results(results, db, region='KR')
print(f"Saved {saved_count} factor scores")
```

### Querying Historical Factors

```sql
-- Get top 20 stocks by P/E factor (value stocks)
SELECT ticker, score, percentile
FROM factor_scores
WHERE factor_name = 'PE_Ratio'
  AND region = 'KR'
  AND date = '2025-10-22'
ORDER BY score DESC
LIMIT 20;

-- Multi-factor analysis
SELECT 
    ticker,
    MAX(CASE WHEN factor_name = 'PE_Ratio' THEN percentile END) as pe_percentile,
    MAX(CASE WHEN factor_name = 'ROE' THEN percentile END) as roe_percentile,
    MAX(CASE WHEN factor_name = '12M_Momentum' THEN percentile END) as momentum_percentile
FROM factor_scores
WHERE region = 'KR' AND date = '2025-10-22'
GROUP BY ticker
HAVING COUNT(DISTINCT factor_name) >= 3
ORDER BY 
    (MAX(CASE WHEN factor_name = 'PE_Ratio' THEN percentile END) +
     MAX(CASE WHEN factor_name = 'ROE' THEN percentile END) +
     MAX(CASE WHEN factor_name = '12M_Momentum' THEN percentile END)) / 3 DESC
LIMIT 20;
```

---

## Performance Benchmarks

**Target Performance Metrics**:
- Factor calculation: <1s per ticker
- Universe scan (200 tickers): <30s
- Database save: <5s for 1000 records
- Historical backtest (5 years): <60s

**Optimization Tips**:
1. Use vectorized operations (pandas/numpy)
2. Batch database queries
3. Cache fundamental data
4. Parallelize factor calculations (multiprocessing)

---

## Best Practices

### 1. Data Quality Validation
```python
# Always validate data before factor calculation
valid, error = factor.validate_data(data)
if not valid:
    logger.warning(f"Data validation failed: {error}")
    return None
```

### 2. Outlier Handling
```python
# Cap extreme values at ±3 sigma
z_score = np.clip(raw_z_score, -3.0, 3.0)
```

### 3. Missing Data Strategy
```python
# Handle missing fundamentals gracefully
if result is None:
    # Option 1: Use previous quarter data
    # Option 2: Skip stock from universe
    # Option 3: Use industry median
    pass
```

### 4. Factor Decay Analysis
```python
# Monitor factor effectiveness over time
SELECT 
    factor_name,
    DATE_TRUNC('quarter', date) as quarter,
    CORR(percentile, LAG(percentile, 20) OVER (PARTITION BY ticker ORDER BY date)) as autocorr
FROM factor_scores
GROUP BY factor_name, quarter
ORDER BY quarter DESC;
```

---

## Testing

### Unit Tests

```python
# tests/test_factors.py
import pytest
from modules.factors import PERatioFactor

def test_pe_factor_calculation():
    """Test P/E factor with known inputs"""
    factor = PERatioFactor()
    
    # Mock data
    result = factor.calculate(data=None, ticker='TEST001')
    
    assert result is not None
    assert result.factor_name == 'PE_Ratio'
    assert -100 <= result.raw_value <= 0  # Negated P/E
    assert 0 <= result.percentile <= 100
```

### Integration Tests

```python
def test_factor_database_save():
    """Test end-to-end factor calculation and save"""
    db = PostgresDatabaseManager()
    factor = PERatioFactor()
    
    results = [factor.calculate(None, '005930')]
    saved = factor.save_results(results, db, 'KR')
    
    assert saved == 1
```

---

## Troubleshooting

### Issue: "No data available for ticker"

**Cause**: Missing fundamental data in `ticker_fundamentals`

**Solution**:
```bash
# Run yfinance backfill for missing ticker
python3 scripts/backfill_fundamentals_yfinance.py --tickers 005930 --region KR
```

### Issue: "Insufficient data length"

**Cause**: Not enough historical OHLCV data for momentum factors

**Solution**:
```python
# Check minimum data requirements
factor = TwelveMonthMomentumFactor()
print(f"Min required days: {factor.min_required_days}")  # 220 days

# Reduce requirement for new IPOs
factor.min_required_days = 60
```

### Issue: "All NULL percentiles"

**Cause**: Insufficient universe size for percentile calculation

**Solution**:
```python
# Expand universe to at least 20 stocks
tickers = db.execute_query("""
    SELECT ticker FROM tickers
    WHERE region = 'KR' AND is_active = TRUE
    LIMIT 50  -- Increase from 10
""")
```

---

## Roadmap

### Phase 2A (Complete)
- ✅ 18 core factors implemented
- ✅ PostgreSQL integration
- ✅ Factor combination framework

### Phase 2B (Next)
- [ ] Factor performance attribution
- [ ] Automatic factor rebalancing
- [ ] Walk-forward optimization
- [ ] Factor momentum (meta-factor)

### Phase 3 (Future)
- [ ] Machine learning factor selection
- [ ] Custom factor builder UI (Streamlit)
- [ ] Real-time factor updates
- [ ] Factor ETF tracking

---

## References

### Academic Papers

1. **Fama & French (1992)**: "The Cross-Section of Expected Stock Returns"  
   - Foundation for value and size factors

2. **Jegadeesh & Titman (1993)**: "Returns to Buying Winners and Selling Losers"  
   - Momentum factor evidence

3. **Sloan (1996)**: "Do Stock Prices Fully Reflect Information in Accruals and Cash Flows?"  
   - Quality factor (earnings quality)

4. **Carhart (1997)**: "On Persistence in Mutual Fund Performance"  
   - Four-factor model (added momentum to Fama-French)

5. **Novy-Marx (2013)**: "The Other Side of Value: The Gross Profitability Premium"  
   - Operating profitability factor

### Industry Resources

- **AQR Capital Management**: Factor investing white papers
- **Research Affiliates**: Smart beta research
- **MSCI Factor Indexes**: Factor methodology documentation

---

**Last Updated**: 2025-10-22  
**Version**: 2.0  
**Status**: Production Ready
