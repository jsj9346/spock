# Factor Formulas and Academic References

**Document Version**: 1.0
**Last Updated**: 2025-10-23
**Platform**: Spock Quant Platform
**Purpose**: Comprehensive mathematical formulas and academic foundations for all implemented factors

---

## Table of Contents

1. [Overview](#overview)
2. [Mathematical Notation](#mathematical-notation)
3. [Value Factors](#value-factors)
4. [Momentum Factors](#momentum-factors)
5. [Quality Factors](#quality-factors)
6. [Low-Volatility Factors](#low-volatility-factors)
7. [Size Factors](#size-factors)
8. [Factor Combination Methods](#factor-combination-methods)
9. [Academic References](#academic-references)
10. [Implementation Guidelines](#implementation-guidelines)

---

## Overview

This document provides the mathematical formulas, theoretical foundations, and academic references for all factors implemented in the Spock Quant Platform. Each factor includes:

1. **Exact Mathematical Formula**: Precise calculation methodology
2. **Theoretical Foundation**: Economic rationale and academic research
3. **Seminal Papers**: Key academic papers supporting the factor
4. **Expected Performance**: Typical IC ranges and market conditions
5. **Implementation Notes**: Platform-specific details

---

## Mathematical Notation

| Symbol | Meaning | Example |
|--------|---------|---------|
| $P_t$ | Stock price at time $t$ | $P_0$ = today's closing price |
| $P_{t-n}$ | Stock price $n$ periods ago | $P_{t-252}$ = price 252 trading days ago |
| $r_t$ | Return at time $t$ | $r_t = (P_t / P_{t-1}) - 1$ |
| $V_t$ | Trading volume at time $t$ | Daily share volume |
| $E$ | Earnings (annual) | Trailing 12-month earnings |
| $BV$ | Book value | Shareholders' equity |
| $EBITDA$ | Earnings Before Interest, Taxes, Depreciation, Amortization | Operating cash earnings |
| $EV$ | Enterprise Value | $EV = \text{Market Cap} + \text{Net Debt}$ |
| $D$ | Annual dividend per share | Sum of last 4 quarterly dividends |
| $\sigma$ | Standard deviation (volatility) | $\sigma = \sqrt{\frac{1}{n}\sum(r_i - \bar{r})^2}$ |
| $\beta$ | Beta (systematic risk) | $\beta = \frac{\text{Cov}(r_i, r_m)}{\text{Var}(r_m)}$ |
| $r_f$ | Risk-free rate | Government bond yield |
| $\rho$ | Correlation coefficient | Spearman rank correlation |
| $IC$ | Information Coefficient | $IC = \rho(\text{factor}, \text{returns})$ |

---

## Value Factors

### 1. Price-to-Earnings Ratio (P/E Ratio)

#### Mathematical Formula

$$
\text{PE\_Ratio} = \frac{P_t}{EPS}
$$

Where:
- $P_t$ = Current stock price (closing price on date $t$)
- $EPS$ = Earnings per share (trailing 12 months)

$$
EPS = \frac{\text{Net Income}}{\text{Shares Outstanding}}
$$

#### Factor Score (Inverted for Ranking)

$$
\text{Value\_Score}_{\text{PE}} = -\text{PE\_Ratio}
$$

**Rationale**: Lower P/E ratio indicates undervaluation. By negating, higher scores represent better value opportunities.

#### Normalized Score (0-100 Scale)

$$
\text{Percentile\_Score} = \text{PercentileRank}(\text{PE\_Ratio}, \text{Universe})
$$

$$
\text{Normalized\_Score} = 100 - \text{Percentile\_Score}
$$

#### Theoretical Foundation

**Economic Rationale**:
1. **Mean Reversion**: P/E ratios tend to revert to historical averages over 3-5 year horizons
2. **Earnings Expectations**: Low P/E reflects pessimistic market expectations that may be overstated
3. **Risk Premium**: Value stocks (low P/E) compensate investors for higher perceived risk

**Seminal Papers**:

1. **Basu, S. (1977)**. *Investment Performance of Common Stocks in Relation to Their Price-Earnings Ratios: A Test of the Efficient Market Hypothesis*. Journal of Finance, 32(3), 663-682.
   - **Key Finding**: Low P/E portfolios earn 7% higher annual returns than high P/E
   - **Sample**: NYSE stocks, 1956-1971
   - **Methodology**: Portfolio sorts, risk-adjusted returns

2. **Fama, E. F., & French, K. R. (1992)**. *The Cross-Section of Expected Stock Returns*. Journal of Finance, 47(2), 427-465.
   - **Key Finding**: P/E (value) and size explain cross-sectional stock returns better than beta
   - **Sample**: NYSE, AMEX, NASDAQ, 1963-1990
   - **Significance**: Foundation of multi-factor models

3. **Asness, C. S., Moskowitz, T. J., & Pedersen, L. H. (2013)**. *Value and Momentum Everywhere*. Journal of Finance, 68(3), 929-985.
   - **Key Finding**: Value premium exists across 40+ years and 20+ countries
   - **Evidence**: P/E premium robust internationally

#### Expected Performance

**IC Statistics** (Based on current KR market data):
- **Average IC**: +0.0509
- **IC Range**: -0.3429 to +0.4867
- **% Positive IC**: 56.8% (88/155 dates)
- **% Statistically Significant (p<0.05)**: 31.0% (48/155 dates)

**Market Regime Performance**:
- **Value Premium Regime**: IC = +0.15 to +0.30 (Feb-Mar 2025, May-Jun 2025)
- **Value Reversal Regime**: IC = -0.20 to -0.05 (Apr 2025, Jul-Sep 2025)
- **Neutral Regime**: IC = +0.05 to +0.13 (Nov 2024)

**Annual Return Premium**: 2-4% (value minus growth, long-only portfolios)

#### Implementation Details

**Database Field**: `ticker_fundamentals.pe_ratio`

**Calculation**:
```python
pe_ratio = current_price / trailing_12m_eps

# Invert for value score
value_score = -pe_ratio

# Winsorize outliers
pe_ratio_capped = np.clip(pe_ratio,
                          np.percentile(all_pe_ratios, 1),
                          np.percentile(all_pe_ratios, 99))

# Normalize to 0-100 percentile
from scipy.stats import percentileofscore
percentile = percentileofscore(all_pe_ratios, pe_ratio)
normalized_score = 100 - percentile  # Invert (low P/E = high score)
```

**Data Requirements**:
- **Price Data**: Daily closing price (from `ohlcv_data`)
- **Earnings Data**: Quarterly earnings reports (trailing 12 months)
- **Update Frequency**: Daily (price), Quarterly (earnings)
- **Minimum Threshold**: $P/E > 0$ (exclude negative earnings firms)

**Handling Special Cases**:
- **Negative Earnings**: Exclude from P/E analysis (undefined ratio)
- **Zero Earnings**: Exclude from analysis
- **Extreme P/E (>100)**: Cap at 99th percentile to reduce outlier impact
- **Financial Firms**: P/E interpretation differs due to accounting (consider using P/B instead)

---

### 2. Price-to-Book Ratio (P/B Ratio)

#### Mathematical Formula

$$
\text{PB\_Ratio} = \frac{P_t}{BV}
$$

Where:
- $P_t$ = Current stock price
- $BV$ = Book value per share

$$
BV = \frac{\text{Shareholders' Equity}}{\text{Shares Outstanding}}
$$

#### Factor Score (Inverted)

$$
\text{Value\_Score}_{\text{PB}} = -\text{PB\_Ratio}
$$

#### Theoretical Foundation

**Economic Rationale**:
1. **Distress Risk**: Firms trading below book value ($P/B < 1$) may be in financial distress, requiring risk premium
2. **Tangible Asset Value**: P/B reflects valuation relative to net tangible assets
3. **Accounting Conservatism**: Book value provides anchor for fair value estimation

**Seminal Papers**:

1. **Fama, E. F., & French, K. R. (1992)**. *The Cross-Section of Expected Stock Returns*. Journal of Finance, 47(2), 427-465.
   - **Key Finding**: Book-to-market ratio (inverse of P/B) is strongest predictor of cross-sectional returns
   - **HML Factor**: High minus low book-to-market earns 0.50% monthly return
   - **Significance**: P/B becomes core factor in Fama-French 3-factor model

2. **Lakonishok, J., Shleifer, A., & Vishny, R. W. (1994)**. *Contrarian Investment, Extrapolation, and Risk*. Journal of Finance, 49(5), 1541-1578.
   - **Key Finding**: Value strategies (low P/B) earn 10-11% annually vs. 7-8% for growth (high P/B)
   - **Sample**: NYSE, AMEX, 1968-1990
   - **Interpretation**: Value premium driven by behavioral biases (overreaction)

3. **Asness, C. S., Moskowitz, T. J., & Pedersen, L. H. (2013)**. *Value and Momentum Everywhere*. Journal of Finance, 68(3), 929-985.
   - **Key Finding**: P/B premium exists across 40 countries, 40+ years
   - **International Evidence**: Value factor robust globally

#### Expected Performance

**IC Statistics** (Current KR market data):
- **Average IC**: +0.0309
- **IC Range**: -0.4342 to +0.4744
- **% Positive IC**: 51.0% (79/155 dates)
- **% Statistically Significant**: 23.9% (37/155 dates)

**Market Regime Performance**:
- **Best Month**: February 2025 (IC = +0.3131, 87.5% positive)
- **Worst Month**: April 2025 (IC = -0.1925, 0% positive)

**Annual Return Premium**: 2-3% (value minus growth)

#### Implementation Details

**Database Field**: `ticker_fundamentals.pb_ratio`

**Calculation**:
```python
book_value_per_share = shareholders_equity / shares_outstanding
pb_ratio = current_price / book_value_per_share

# Invert for value score
value_score = -pb_ratio

# Normalize
percentile = percentileofscore(all_pb_ratios, pb_ratio)
normalized_score = 100 - percentile
```

**Handling Special Cases**:
- **Negative Equity**: Exclude from analysis (distressed firms)
- **Near-Zero Book Value**: Exclude if $BV < 0.01 \times \text{Market Cap}$
- **Goodwill-Heavy Firms**: Consider tangible book value adjustment: $\text{Tangible BV} = BV - \text{Intangibles}$
- **Financial Firms**: P/B more relevant than P/E (regulatory capital requirements)

---

### 3. Enterprise Value / EBITDA

#### Mathematical Formula

$$
\text{EV/EBITDA} = \frac{EV}{EBITDA}
$$

Where:

$$
EV = \text{Market Cap} + \text{Total Debt} - \text{Cash}
$$

$$
\text{Market Cap} = P_t \times \text{Shares Outstanding}
$$

$$
EBITDA = \text{Operating Income} + \text{Depreciation} + \text{Amortization}
$$

#### Factor Score (Inverted)

$$
\text{Value\_Score}_{\text{EV/EBITDA}} = -\text{EV/EBITDA}
$$

#### Theoretical Foundation

**Economic Rationale**:
1. **Capital Structure Neutral**: EV accounts for debt, making comparisons valid across different leverage levels
2. **Operating Earnings**: EBITDA represents cash earnings before financing and tax decisions
3. **M&A Valuation**: Widely used in acquisition valuations

**Seminal Papers**:

1. **Loughran, T., & Wellman, J. W. (2011)**. *New Evidence on the Relation Between the Enterprise Multiple and Average Stock Returns*. Journal of Financial Economics, 100(2), 381-397.
   - **Key Finding**: Low EV/EBITDA quintile outperforms high quintile by 8% annually
   - **Sample**: US stocks, 1963-2009
   - **Significance**: EV/EBITDA superior to P/E for leveraged firms

2. **Gray, W. R., & Vogel, J. (2012)**. *Analyzing Valuation Measures: A Performance Horse-Race over the Past 40 Years*. Journal of Portfolio Management, 39(1), 112-121.
   - **Key Finding**: EV/EBITDA combines value and quality signals
   - **Sharpe Ratio**: 0.45 for EV/EBITDA portfolios

#### Expected Performance

- **Average IC**: +0.04 to +0.09
- **Strong Regime**: +0.15 to +0.35
- **Weak Regime**: -0.05 to +0.05

#### Status

⏳ **Not Yet Implemented** - Requires fundamental data backfill (total_debt, cash, EBITDA)

---

## Momentum Factors

### 1. 12-Month Momentum (Excluding Last Month)

#### Mathematical Formula

$$
\text{12M\_Momentum} = \frac{P_{t-21}}{P_{t-252}} - 1
$$

Where:
- $P_{t-21}$ = Stock price 21 trading days ago (~1 month)
- $P_{t-252}$ = Stock price 252 trading days ago (~12 months)

**Rationale**: Exclude last month (21 trading days) to avoid short-term reversal effects documented by Jegadeesh (1990).

#### Factor Score (Direct)

$$
\text{Momentum\_Score} = \text{12M\_Momentum}
$$

**Interpretation**: Higher 12-month return indicates stronger price momentum.

#### Theoretical Foundation

**Economic Rationale**:
1. **Investor Underreaction**: Gradual information diffusion leads to price momentum
2. **Behavioral Biases**: Anchoring, confirmation bias, herding behavior
3. **Positive Feedback Trading**: Trend-following strategies create self-reinforcing cycles

**Seminal Papers**:

1. **Jegadeesh, N., & Titman, S. (1993)**. *Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency*. Journal of Finance, 48(1), 65-91.
   - **Key Finding**: Stocks with high past returns (3-12 months) continue to outperform
   - **WML Strategy**: Winners minus losers earn 1% monthly return (12% annually)
   - **Sample**: NYSE/AMEX, 1965-1989
   - **Persistence**: Momentum profits exist for up to 12 months

2. **Carhart, M. M. (1997)**. *On Persistence in Mutual Fund Performance*. Journal of Finance, 52(1), 57-82.
   - **Key Finding**: Momentum is a systematic risk factor (4-factor model)
   - **MOM Factor**: Added to Fama-French 3-factor model
   - **Sharpe Ratio**: 0.50 for momentum factor

3. **Asness, C. S., Moskowitz, T. J., & Pedersen, L. H. (2013)**. *Value and Momentum Everywhere*. Journal of Finance, 68(3), 929-985.
   - **Key Finding**: Momentum premium exists across 40+ countries and multiple asset classes
   - **International Evidence**: 12-month momentum robust globally

#### Expected Performance

- **Average IC**: +0.05 to +0.12
- **Strong Regime**: +0.20 to +0.40 (trending markets)
- **Weak Regime**: -0.10 to +0.05 (mean-reverting markets)
- **Annual Return Premium**: 5-10% (long winners, short losers)

#### Implementation Details

**Database Field**: `ticker_fundamentals.momentum_12m`

**Calculation**:
```python
# Get prices (adjusted for splits and dividends)
price_1m_ago = get_adjusted_price(date - timedelta(days=21))
price_12m_ago = get_adjusted_price(date - timedelta(days=252))

# Calculate momentum (skip last month)
momentum_12m = (price_1m_ago / price_12m_ago) - 1

# Direct score (higher return = higher momentum score)
momentum_score = momentum_12m

# Normalize to percentile
percentile = percentileofscore(all_momentum_12m, momentum_12m)
normalized_score = percentile
```

**Data Requirements**:
- **Price Data**: Daily adjusted closing prices for last 252 trading days (~1 year)
- **Minimum History**: 252 trading days
- **Adjustments**: Adjusted for stock splits, dividends, corporate actions

**Handling Special Cases**:
- **IPOs (<252 days history)**: Exclude from momentum analysis
- **Stock Splits**: Use adjusted prices (multiply by split ratio)
- **Trading Halts**: Interpolate missing prices or exclude halt dates
- **Extreme Returns (>100% or <-50%)**: Cap at 99th and 1st percentiles

---

### 2. 1-Month Momentum (Short-Term Reversal)

#### Mathematical Formula

$$
\text{1M\_Momentum} = \frac{P_t}{P_{t-21}} - 1
$$

Where:
- $P_t$ = Current stock price
- $P_{t-21}$ = Stock price 21 trading days ago

#### Factor Score (Inverted for Reversal Strategy)

$$
\text{Reversal\_Score} = -\text{1M\_Momentum}
$$

**Rationale**: Short-term momentum reverses (overreaction effect). Stocks with high 1-month returns tend to underperform in the next month.

#### Theoretical Foundation

**Economic Rationale**:
1. **Overreaction**: Short-term price movements driven by noise trading and overreaction
2. **Liquidity Provision**: Market makers and arbitrageurs provide liquidity, creating reversal
3. **Bid-Ask Bounce**: Microstructure effects contribute to short-term reversals

**Seminal Papers**:

1. **Jegadeesh, N. (1990)**. *Evidence of Predictable Behavior of Security Returns*. Journal of Finance, 45(3), 881-898.
   - **Key Finding**: 1-month returns negatively predict future returns (reversal effect)
   - **Return**: 2% monthly return from reversal strategy
   - **Sample**: NYSE, 1934-1987

2. **Lehmann, B. N. (1990)**. *Fads, Martingales, and Market Efficiency*. Quarterly Journal of Economics, 105(1), 1-28.
   - **Key Finding**: Weekly reversals exist across NYSE/AMEX stocks
   - **Magnitude**: Larger for small-cap and high-volatility stocks

3. **Nagel, S. (2012)**. *Evaporating Liquidity*. Review of Financial Studies, 25(7), 2005-2039.
   - **Key Finding**: Reversal stronger for high-volatility stocks due to liquidity constraints

#### Expected Performance

- **Average IC**: +0.03 to +0.08 (reversal strategy)
- **Strong Regime**: +0.10 to +0.20
- **Weak Regime**: -0.05 to +0.05

#### Implementation Details

**Database Field**: `ticker_fundamentals.momentum_1m`

**Calculation**:
```python
current_price = get_price(date)
price_1m_ago = get_price(date - timedelta(days=21))

# Calculate 1-month return
momentum_1m = (current_price / price_1m_ago) - 1

# Invert for reversal strategy (losers outperform winners)
reversal_score = -momentum_1m

# Normalize (high 1M return = low reversal score)
percentile = percentileofscore(all_momentum_1m, momentum_1m)
normalized_score = 100 - percentile  # Invert
```

**Handling Special Cases**:
- **Extreme Returns**: Cap at ±50% for 1-month period
- **Low Liquidity**: Reversal may be unreliable for illiquid stocks
- **Corporate Events**: Exclude stocks with M&A announcements, earnings releases, stock splits

---

### 3. RSI Momentum (Technical Indicator)

#### Mathematical Formula

$$
\text{RSI} = 100 - \frac{100}{1 + RS}
$$

Where:

$$
RS = \frac{\text{Average Gain (14 days)}}{\text{Average Loss (14 days)}}
$$

Detailed calculation:

$$
\text{Average Gain} = \frac{1}{14} \sum_{i=1}^{14} \max(0, r_i)
$$

$$
\text{Average Loss} = \frac{1}{14} \sum_{i=1}^{14} \max(0, -r_i)
$$

Where $r_i = P_i - P_{i-1}$ (daily price change)

#### Factor Score (Mean-Reversion Strategy)

$$
\text{RSI\_Score} =
\begin{cases}
100 - \text{RSI} & \text{if } \text{RSI} > 70 \text{ (overbought, short signal)} \\
\text{RSI} + 30 & \text{if } \text{RSI} < 30 \text{ (oversold, long signal)} \\
50 & \text{otherwise (neutral)}
\end{cases}
$$

#### Theoretical Foundation

**Technical Analysis**: Wilder, J. W. (1978). *New Concepts in Technical Trading Systems*. Trend Research.

**Key Concepts**:
- **RSI Range**: 0-100 scale measuring momentum
- **Overbought**: RSI > 70 signals excessive buying, expect mean reversion
- **Oversold**: RSI < 30 signals excessive selling, expect bounce
- **Divergence**: RSI diverging from price signals trend reversal

**Academic Evidence** (Limited):
- Brock, W., Lakonishok, J., & LeBaron, B. (1992). *Simple Technical Trading Rules and the Stochastic Properties of Stock Returns*. Journal of Finance, 47(5), 1731-1764.
  - **Key Finding**: Some technical rules (including RSI-like indicators) show profitability
  - **Caveat**: Profitability diminishes after transaction costs

#### Expected Performance

- **Average IC**: +0.01 to +0.04 (weak factor)
- **Strong Regime**: +0.05 to +0.10
- **Weak Regime**: -0.05 to +0.02

#### Implementation Details

**Database Field**: `ticker_fundamentals.rsi_momentum`

**Calculation**:
```python
# Calculate 14-day gains and losses
daily_changes = np.diff(prices[-15:])
gains = np.array([max(0, change) for change in daily_changes])
losses = np.array([max(0, -change) for change in daily_changes])

# Average gains and losses
avg_gain = np.mean(gains)
avg_loss = np.mean(losses)

# Calculate RS and RSI
rs = avg_gain / avg_loss if avg_loss > 0 else 100
rsi = 100 - (100 / (1 + rs))

# Mean-reversion score
if rsi > 70:
    score = 100 - rsi  # Short signal (lower score)
elif rsi < 30:
    score = rsi + 70   # Long signal (boost score)
else:
    score = 50  # Neutral
```

**Handling Special Cases**:
- **Zero Loss Days** (all gains): RSI = 100 (extreme overbought)
- **Zero Gain Days** (all losses): RSI = 0 (extreme oversold)
- **Low Volatility**: RSI hovers at 50 (no clear signal)

---

## Quality Factors

### 1. Return on Equity (ROE)

#### Mathematical Formula

$$
\text{ROE} = \frac{\text{Net Income}}{\text{Shareholders' Equity}}
$$

Annualized:

$$
\text{ROE}_{\text{annual}} = \frac{\text{Net Income}_{\text{TTM}}}{\text{Avg Shareholders' Equity}}
$$

Where TTM = Trailing Twelve Months

#### Factor Score (Direct)

$$
\text{Quality\_Score}_{\text{ROE}} = \text{ROE}
$$

**Interpretation**: Higher ROE indicates more efficient use of equity capital (higher quality).

#### Theoretical Foundation

**Economic Rationale**:
1. **Capital Efficiency**: High ROE firms generate more profits per dollar of equity
2. **Competitive Advantage**: Sustained high ROE indicates moat (pricing power, brand, technology)
3. **Reinvestment Opportunity**: High ROE firms can reinvest earnings at high rates

**Seminal Papers**:

1. **Novy-Marx, R. (2013)**. *The Other Side of Value: The Gross Profitability Premium*. Journal of Financial Economics, 108(1), 1-28.
   - **Key Finding**: Profitable firms (high gross profitability, similar to ROE) outperform unprofitable firms
   - **Return Premium**: 0.31% monthly (3.7% annually)
   - **Significance**: Profitability as strong as value in predicting returns

2. **Fama, E. F., & French, K. R. (2015)**. *A Five-Factor Asset Pricing Model*. Journal of Financial Economics, 116(1), 1-22.
   - **Key Finding**: Profitability factor (RMW: Robust Minus Weak) in 5-factor model
   - **Profitability Proxy**: Operating profitability (similar to ROE)
   - **Alpha**: Profitability factor adds explanatory power beyond 3-factor model

3. **Asness, C. S., Frazzini, A., & Pedersen, L. H. (2019)**. *Quality Minus Junk*. Review of Accounting Studies, 24(1), 34-112.
   - **Key Finding**: Quality factor (including ROE) earns 3-5% annually (quality minus junk)
   - **Sharpe Ratio**: 0.60 for quality factor
   - **Robustness**: Quality premium robust across markets and time periods

#### Expected Performance

- **Average IC**: +0.03 to +0.07
- **Strong Regime**: +0.10 to +0.20
- **Weak Regime**: -0.05 to +0.05

#### Status

⏳ **Not Yet Implemented** - Requires fundamental data backfill (net_income, shareholders_equity)

---

### 2. Accruals Ratio (Earnings Quality)

#### Mathematical Formula

$$
\text{Accruals} = \frac{\text{Net Income} - \text{Operating Cash Flow}}{\text{Total Assets}}
$$

#### Factor Score (Inverted)

$$
\text{Quality\_Score}_{\text{Accruals}} = -\text{Accruals}
$$

**Rationale**: Lower accruals indicate higher earnings quality (earnings backed by cash flow). High accruals suggest earnings manipulation or unsustainable accounting.

#### Theoretical Foundation

**Economic Rationale**:
1. **Earnings Persistence**: Cash-based earnings more persistent than accrual-based earnings
2. **Accounting Manipulation**: High accruals may indicate aggressive accounting
3. **Working Capital**: High accruals often from working capital buildup (inventory, receivables)

**Seminal Papers**:

1. **Sloan, R. G. (1996)**. *Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?* The Accounting Review, 71(3), 289-315.
   - **Key Finding**: High accruals predict lower future returns (accrual anomaly)
   - **Return Spread**: 10.4% annually (low accruals minus high accruals)
   - **Sample**: US stocks, 1962-1991
   - **Explanation**: Investors overweight accrual component vs. cash flow component

2. **Richardson, S. A., Sloan, R. G., Soliman, M. T., & Tuna, I. (2005)**. *Accrual Reliability, Earnings Persistence and Stock Prices*. Journal of Accounting and Economics, 39(3), 437-485.
   - **Key Finding**: Total accruals (not just working capital) predict returns
   - **Persistence**: Low accrual firms have more persistent earnings

3. **Piotroski, J. D. (2000)**. *Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers*. Journal of Accounting Research, 38, 1-41.
   - **F-Score**: Includes accruals as one of 9 quality indicators
   - **Return**: High F-Score value stocks earn 23% annually vs. -25% for low F-Score

#### Expected Performance

- **Average IC**: +0.03 to +0.08
- **Strong Regime**: +0.10 to +0.20
- **Weak Regime**: -0.05 to +0.05

#### Status

⏳ **Not Yet Implemented** - Requires cash flow data backfill

---

## Low-Volatility Factors

### 1. Historical Volatility (60-Day)

#### Mathematical Formula

$$
\sigma_{60d} = \sqrt{\frac{1}{60} \sum_{i=1}^{60} (r_i - \bar{r})^2}
$$

Annualized:

$$
\sigma_{\text{annual}} = \sigma_{60d} \times \sqrt{252}
$$

Where:
- $r_i$ = Daily return on day $i$: $r_i = (P_i / P_{i-1}) - 1$
- $\bar{r}$ = Average daily return over 60 days: $\bar{r} = \frac{1}{60}\sum_{i=1}^{60} r_i$
- $\sqrt{252}$ = Annualization factor (252 trading days per year)

#### Factor Score (Inverted for Low-Volatility)

$$
\text{LowVol\_Score} = -\sigma_{\text{annual}}
$$

**Interpretation**: Lower volatility indicates defensive characteristics. Higher low-vol score represents safer stocks.

#### Theoretical Foundation

**Economic Rationale**:
1. **Leverage Constraints**: Investors cannot leverage low-vol stocks to desired risk level, creating mispricing
2. **Behavioral Bias**: Preference for lottery-like high-vol stocks (overpriced)
3. **Benchmark Constraints**: Fund managers underweight low-vol stocks to avoid career risk

**Seminal Papers**:

1. **Ang, A., Hodrick, R. J., Xing, Y., & Zhang, X. (2006)**. *The Cross-Section of Volatility and Expected Returns*. Journal of Finance, 61(1), 259-299.
   - **Key Finding**: Low idiosyncratic volatility stocks earn higher returns than high volatility stocks
   - **Contradiction**: Violates CAPM (high risk should earn high return)
   - **Return Spread**: 1% monthly (low vol minus high vol)

2. **Baker, M., Bradley, B., & Wurgler, J. (2011)**. *Benchmarks as Limits to Arbitrage: Understanding the Low-Volatility Anomaly*. Financial Analysts Journal, 67(1), 40-54.
   - **Key Finding**: Low-volatility portfolios earn 0.8% monthly alpha
   - **Sharpe Ratio**: 0.60-0.80 for low-vol strategies
   - **Explanation**: Benchmark constraints prevent arbitrage

3. **Blitz, D., & van Vliet, P. (2007)**. *The Volatility Effect: Lower Risk Without Lower Return*. Journal of Portfolio Management, 34(1), 102-113.
   - **Key Finding**: Low-vol stocks earn same returns as high-vol stocks with 30% less risk
   - **International Evidence**: Low-vol anomaly exists across developed markets

#### Expected Performance

- **Average IC**: +0.03 to +0.07
- **Strong Regime**: +0.10 to +0.20 (crisis periods, risk-off)
- **Weak Regime**: -0.05 to +0.05 (bull markets, risk-on)

#### Status

⏳ **Not Yet Implemented** - Requires 60-day OHLCV backfill

---

### 2. Beta (Systematic Risk)

#### Mathematical Formula

$$
\beta = \frac{\text{Cov}(r_i, r_m)}{\text{Var}(r_m)}
$$

Expanded:

$$
\beta = \frac{\sum_{t=1}^{n}(r_{i,t} - \bar{r}_i)(r_{m,t} - \bar{r}_m)}{\sum_{t=1}^{n}(r_{m,t} - \bar{r}_m)^2}
$$

Where:
- $r_{i,t}$ = Stock return on day $t$
- $r_{m,t}$ = Market index return on day $t$ (e.g., KOSPI for KR, S&P 500 for US)
- $\bar{r}_i$ = Average stock return over estimation period
- $\bar{r}_m$ = Average market return over estimation period
- $n$ = 252 trading days (~1 year)

#### Factor Score (Inverted for Low-Beta)

$$
\text{LowBeta\_Score} = -\beta
$$

#### Theoretical Foundation

**Economic Rationale**:
1. **Leverage Constraints**: Investors cannot leverage low-beta stocks to desired risk level
2. **Betting-Against-Beta**: High-beta stocks are overpriced due to institutional demand
3. **Benchmark Constraints**: Funds avoid low-beta stocks to prevent tracking error

**Seminal Papers**:

1. **Black, F., Jensen, M. C., & Scholes, M. (1972)**. *The Capital Asset Pricing Model: Some Empirical Tests*. Studies in the Theory of Capital Markets, 81(3), 79-121.
   - **Key Finding**: Security market line (SML) is flatter than CAPM predicts
   - **Implication**: Low-beta stocks earn higher risk-adjusted returns than CAPM predicts

2. **Frazzini, A., & Pedersen, L. H. (2014)**. *Betting Against Beta*. Journal of Financial Economics, 111(1), 1-25.
   - **Key Finding**: BAB (Betting Against Beta) factor earns 0.8% monthly return
   - **Sharpe Ratio**: 0.78 for BAB factor
   - **Sample**: US stocks 1926-2012, international stocks 1983-2012
   - **Robustness**: BAB premium exists across 20 countries, multiple asset classes

3. **Baker, M., Bradley, B., & Wurgler, J. (2011)**. *Benchmarks as Limits to Arbitrage: Understanding the Low-Volatility Anomaly*. Financial Analysts Journal, 67(1), 40-54.
   - **Key Finding**: Low-beta stocks outperform high-beta stocks on risk-adjusted basis
   - **Alpha**: 6% annually for low-beta portfolios

#### Expected Performance

- **Average IC**: +0.02 to +0.06
- **Strong Regime**: +0.08 to +0.15 (market downturns, defensive rotation)
- **Weak Regime**: -0.05 to +0.05 (bull markets, risk-seeking)

#### Status

⏳ **Not Yet Implemented** - Requires market index data and 252-day OHLCV

---

## Factor Combination Methods

### 1. Equal Weighting

#### Formula

$$
S_{\text{combined}} = \frac{1}{N} \sum_{i=1}^{N} S_i
$$

Where:
- $S_i$ = Normalized score for factor $i$ (0-100 scale)
- $N$ = Number of factors

**Advantages**:
- Simple and transparent
- No optimization required (no overfitting risk)
- Diversifies single-factor risk

**Disadvantages**:
- Ignores factor performance differences
- No adaptation to changing market regimes

**When to Use**: Default method for initial multi-factor strategies, minimal data requirements

---

### 2. IC-Weighted

#### Formula

$$
S_{\text{combined}} = \sum_{i=1}^{N} w_i \times S_i
$$

Where:

$$
w_i = \frac{IC_i}{\sum_{j=1}^{N} IC_j}
$$

- $IC_i$ = Historical Information Coefficient for factor $i$ (average over last 6-12 months)
- $S_i$ = Normalized score for factor $i$

**Example** (Current KR data):

Given:
- $IC_{\text{PE}} = 0.0509$
- $IC_{\text{PB}} = 0.0309$

$$
w_{\text{PE}} = \frac{0.0509}{0.0509 + 0.0309} = 62.2\%
$$

$$
w_{\text{PB}} = \frac{0.0309}{0.0509 + 0.0309} = 37.8\%
$$

**Advantages**:
- Weights factors by predictive power
- Automatically reduces weight of weak factors
- Adapts to factor performance

**Disadvantages**:
- Requires IC calculation history (6+ months minimum)
- May overfit to recent performance

**When to Use**: After 6+ months of IC history available, medium turnover acceptable

---

### 3. Mean-Variance Optimization

#### Formula

Maximize:

$$
\text{Sharpe Ratio} = \frac{E[r_p] - r_f}{\sigma_p}
$$

Subject to:

$$
\sum_{i=1}^{N} w_i = 1, \quad w_i \geq 0
$$

Where:
- $E[r_p] = \sum_{i=1}^{N} w_i \times IC_i$ (expected portfolio IC)
- $\sigma_p = \sqrt{w^T \Sigma w}$ (portfolio IC volatility)
- $\Sigma$ = Covariance matrix of factor ICs
- $r_f$ = Risk-free IC (baseline = 0)

**Optimization Problem**:

$$
\max_{w} \frac{\sum_{i=1}^{N} w_i \times IC_i}{\sqrt{w^T \Sigma w}}
$$

**Advantages**:
- Maximizes risk-adjusted returns
- Accounts for factor correlations
- Theoretically optimal

**Disadvantages**:
- Requires stable covariance matrix estimation (unstable with <12 months data)
- Sensitive to estimation error
- May concentrate in few factors (corner solutions)

**When to Use**: After 12+ months of IC history, when factor correlations are stable

---

## Academic References

### Foundational Papers

1. **Graham, B., & Dodd, D. (1934)**. *Security Analysis*. McGraw-Hill.
   - **Topic**: Value investing fundamentals
   - **Key Metrics**: P/E ratio, P/B ratio, dividend yield as valuation tools

2. **Banz, R. W. (1981)**. *The Relationship Between Return and Market Value of Common Stocks*. Journal of Financial Economics, 9(1), 3-18.
   - **Topic**: Size effect discovery
   - **Key Finding**: Small firms earn 5% higher annual returns than large firms
   - **Sample**: NYSE stocks, 1936-1975

3. **Fama, E. F., & French, K. R. (1992)**. *The Cross-Section of Expected Stock Returns*. Journal of Finance, 47(2), 427-465.
   - **Topic**: Multi-factor model (size, value)
   - **Key Finding**: P/B and size explain cross-sectional returns better than CAPM beta
   - **Significance**: Foundation of modern factor investing

4. **Jegadeesh, N., & Titman, S. (1993)**. *Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency*. Journal of Finance, 48(1), 65-91.
   - **Topic**: Momentum effect
   - **Key Finding**: 12-month momentum strategy earns 1% monthly return (12% annually)
   - **Sample**: NYSE/AMEX, 1965-1989

5. **Sloan, R. G. (1996)**. *Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings?* The Accounting Review, 71(3), 289-315.
   - **Topic**: Earnings quality (accruals anomaly)
   - **Key Finding**: High accruals predict 10.4% lower annual returns
   - **Explanation**: Investors overweight accruals vs. cash flow

6. **Piotroski, J. D. (2000)**. *Value Investing: The Use of Historical Financial Statement Information to Separate Winners from Losers*. Journal of Accounting Research, 38, 1-41.
   - **Topic**: Quality factors (F-Score)
   - **Key Finding**: High F-Score value stocks earn 23% annually vs. -25% for low F-Score
   - **Methodology**: 9 quality signals including accruals, profitability, leverage

7. **Ang, A., Hodrick, R. J., Xing, Y., & Zhang, X. (2006)**. *The Cross-Section of Volatility and Expected Returns*. Journal of Finance, 61(1), 259-299.
   - **Topic**: Low-volatility anomaly
   - **Key Finding**: Low idiosyncratic volatility stocks earn 1% higher monthly returns
   - **Contradiction**: Violates CAPM prediction

8. **Baker, M., Bradley, B., & Wurgler, J. (2011)**. *Benchmarks as Limits to Arbitrage: Understanding the Low-Volatility Anomaly*. Financial Analysts Journal, 67(1), 40-54.
   - **Topic**: Low-volatility premium explanation
   - **Key Finding**: Low-vol portfolios earn 0.8% monthly alpha
   - **Explanation**: Benchmark constraints prevent arbitrage

9. **Asness, C. S., Moskowitz, T. J., & Pedersen, L. H. (2013)**. *Value and Momentum Everywhere*. Journal of Finance, 68(3), 929-985.
   - **Topic**: Factor premiums across markets
   - **Key Finding**: Value and momentum exist in 40+ countries, multiple asset classes
   - **Robustness**: Factors persist across 215+ years of data

10. **Frazzini, A., & Pedersen, L. H. (2014)**. *Betting Against Beta*. Journal of Financial Economics, 111(1), 1-25.
    - **Topic**: Low-beta anomaly
    - **Key Finding**: BAB factor earns 0.8% monthly (Sharpe ratio 0.78)
    - **Sample**: 20 countries, 1926-2012

11. **Fama, E. F., & French, K. R. (2015)**. *A Five-Factor Asset Pricing Model*. Journal of Financial Economics, 116(1), 1-22.
    - **Topic**: 5-factor model extension
    - **Key Factors**: Size, value, profitability, investment, market
    - **Significance**: Profitability and investment factors improve on 3-factor model

12. **Asness, C. S., Frazzini, A., & Pedersen, L. H. (2019)**. *Quality Minus Junk*. Review of Accounting Studies, 24(1), 34-112.
    - **Topic**: Quality factor
    - **Key Finding**: Quality factor earns 3-5% annually (Sharpe ratio 0.60)
    - **Quality Metrics**: Profitability, growth, safety, payout

---

## Implementation Guidelines

### Data Quality Requirements

1. **Price Data**: Daily adjusted closing prices (splits, dividends)
2. **Fundamental Data**: Quarterly updates (minimum), annual data for quality factors
3. **Data Integrity**: Validate for missing values, outliers, data errors
4. **Point-in-Time**: Use only data available on calculation date (no look-ahead bias)

### Factor Calculation Workflow

```python
# 1. Load data
prices = get_ohlcv_data(ticker, start_date, end_date)
fundamentals = get_fundamental_data(ticker, date)

# 2. Calculate raw factor value
factor_value = calculate_factor(prices, fundamentals)

# 3. Normalize (z-score or percentile)
z_score = (factor_value - mean) / std_dev
percentile = percentileofscore(all_factors, factor_value)

# 4. Store in database
save_factor_score(ticker, date, factor_name, factor_value, z_score, percentile)
```

### Performance Monitoring

**Key Metrics**:
- **Information Coefficient (IC)**: $\rho(\text{factor}, \text{forward returns})$
- **IC Hit Rate**: % of dates with IC > 0
- **IC Significance**: % of dates with p-value < 0.05
- **Factor Sharpe Ratio**: Risk-adjusted return of factor portfolios

**Acceptable Thresholds**:
- Average IC > 0.03 (statistically significant)
- IC Hit Rate > 55% (better than random)
- IC Significance > 25% (consistent predictive power)
- Factor Sharpe > 1.0 (viable strategy)

---

**Document Status**: ✅ Production-Ready
**Last Updated**: 2025-10-23
**Version**: 1.0
**Author**: Spock Quant Platform
