# Phase 2: Factor Library Development - Technical Design Specification

**Quant Investment Platform - Multi-Factor Analysis Engine**

**Created**: 2025-10-21
**Version**: 1.0 (Design Phase)
**Status**: Design Complete - Ready for Implementation
**Dependencies**: Phase 1 Complete (PostgreSQL + TimescaleDB)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Factor Library Design](#factor-library-design)
4. [Factor Calculation Engine](#factor-calculation-engine)
5. [Factor Combination Framework](#factor-combination-framework)
6. [Database Integration](#database-integration)
7. [Performance Optimization](#performance-optimization)
8. [Implementation Plan](#implementation-plan)
9. [Testing Strategy](#testing-strategy)
10. [API Specification](#api-specification)

---

## Executive Summary

### Purpose

Phase 2 implements a **Multi-Factor Analysis Engine** for systematic alpha generation through evidence-based factor investing. The system calculates, combines, and analyzes quantitative factors (Value, Momentum, Quality, Low-Volatility, Size) to generate composite stock ranking scores for portfolio construction.

### Core Objectives

1. **Factor Library**: Implement 20+ proven quantitative factors across 5 categories
2. **Calculation Engine**: Daily factor score calculation for 18K+ tickers across 6 markets
3. **Combination Framework**: Multiple factor weighting schemes (equal, optimization, ML)
4. **Performance**: <5 seconds for full universe factor calculation
5. **Storage**: PostgreSQL + TimescaleDB integration with compression

### Key Metrics

- **Factors**: 20+ factors across 5 categories (Value, Momentum, Quality, Low-Vol, Size)
- **Universe**: 18,661 tickers across 6 markets (KR, US, CN, HK, JP, VN)
- **Update Frequency**: Daily (after market close)
- **Calculation Time**: <5 seconds for full universe
- **Storage**: ~100KB/day compressed (~36MB/year)
- **Query Performance**: <10ms for factor retrieval

---

## System Architecture

### High-Level Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                   Factor Analysis Workflow                      │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 1: Data Collection (Reuse Spock Infrastructure)         │
│  ├─ Market Data: OHLCV from ohlcv_data (TimescaleDB)         │
│  ├─ Fundamentals: P/E, P/B, ROE from ticker_fundamentals     │
│  ├─ Technical: RSI, Moving Averages from technical_analysis  │
│  └─ Metadata: Sector, Market Cap from stock_details          │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 2: Factor Calculation (New - Phase 2)                   │
│  ├─ Value Factors: P/E, P/B, EV/EBITDA, Div Yield            │
│  ├─ Momentum Factors: 12M Return, RSI, 52W High              │
│  ├─ Quality Factors: ROE, D/E, Margin Stability              │
│  ├─ Low-Vol Factors: Volatility, Beta, Drawdown              │
│  └─ Size Factors: Market Cap, Liquidity                      │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 3: Factor Normalization (Z-Score, Percentile)           │
│  ├─ Cross-Sectional: Normalize within region                 │
│  ├─ Winsorization: Cap outliers at 3σ                        │
│  ├─ Z-Score: (value - mean) / std                            │
│  └─ Percentile: Rank 0-100 within universe                   │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 4: Factor Storage (PostgreSQL + TimescaleDB)            │
│  ├─ Table: factor_scores (hypertable)                        │
│  ├─ Columns: ticker, region, date, factor_name, score        │
│  ├─ Compression: After 365 days (10x reduction)              │
│  └─ Performance: Indexed for fast retrieval                  │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 5: Factor Combination (Multiple Strategies)             │
│  ├─ Equal Weighting: Simple average                          │
│  ├─ Optimization: Maximize Sharpe ratio                      │
│  ├─ Risk-Adjusted: Inverse volatility                        │
│  └─ Machine Learning: XGBoost/RandomForest                   │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│  Step 6: Composite Score (0-100 Alpha Score)                  │
│  ├─ Weighted Sum: Σ(weight_i × factor_i)                     │
│  ├─ Normalization: Map to 0-100 range                        │
│  ├─ Storage: strategies table                                │
│  └─ Output: Stock rankings for portfolio construction        │
└────────────────────────────────────────────────────────────────┘
```

### Component Hierarchy

```
modules/factors/
├── factor_base.py              # Abstract base class + utilities
│   ├── FactorBase (ABC)        # Base class for all factors
│   ├── FactorRegistry          # Factory pattern for factor creation
│   ├── FactorValidator         # Input/output validation
│   └── FactorCache             # In-memory caching for performance
│
├── value_factors.py            # Value factor implementations
│   ├── PERatioFactor           # Price-to-Earnings ratio
│   ├── PBRatioFactor           # Price-to-Book ratio
│   ├── EVToEBITDAFactor        # Enterprise Value / EBITDA
│   ├── DividendYieldFactor     # Dividend Yield
│   └── FCFYieldFactor          # Free Cash Flow Yield
│
├── momentum_factors.py         # Momentum factor implementations
│   ├── PriceMomentumFactor     # 12-month price return (excl. last month)
│   ├── RSIMomentumFactor       # RSI-based momentum
│   ├── FiftyTwoWeekHighFactor  # Proximity to 52-week high
│   ├── VolumeWeightedMomentumFactor  # Volume-adjusted momentum
│   └── EarningsMomentumFactor  # Earnings surprise momentum
│
├── quality_factors.py          # Quality factor implementations
│   ├── ROEFactor               # Return on Equity
│   ├── DebtToEquityFactor      # Debt-to-Equity ratio
│   ├── EarningsQualityFactor   # Accruals-based earnings quality
│   ├── ProfitMarginFactor      # Net profit margin stability
│   └── CashFlowQualityFactor   # Operating cash flow / Net income
│
├── low_vol_factors.py          # Low-volatility factor implementations
│   ├── VolatilityFactor        # Historical volatility (60-day)
│   ├── BetaFactor              # Beta vs market index
│   ├── MaxDrawdownFactor       # Maximum drawdown (252-day)
│   ├── DownsideDeviationFactor # Downside deviation (semi-volatility)
│   └── CVaRFactor              # Conditional Value at Risk
│
├── size_factors.py             # Size factor implementations
│   ├── MarketCapFactor         # Market capitalization
│   ├── LiquidityFactor         # Average daily trading volume
│   └── FreeFloatFactor         # Free float percentage
│
├── factor_calculator.py        # Batch factor calculation
│   ├── FactorCalculator        # Main calculation orchestrator
│   ├── calculate_all_factors() # Calculate all factors for universe
│   ├── calculate_factor()      # Calculate single factor
│   └── parallel_calculation()  # Parallel processing for performance
│
├── factor_combiner.py          # Factor combination framework
│   ├── FactorCombiner (ABC)    # Base combiner class
│   ├── EqualWeightCombiner     # Simple average
│   ├── OptimizationCombiner    # Sharpe ratio optimization
│   ├── RiskAdjustedCombiner    # Inverse volatility weighting
│   └── MLCombiner              # XGBoost/RandomForest
│
└── factor_analyzer.py          # Factor performance analysis
    ├── FactorAnalyzer          # Analyze factor performance
    ├── analyze_factor_returns()# Historical factor returns
    ├── factor_correlation()    # Factor independence check
    └── factor_turnover()       # Factor stability analysis
```

---

## Factor Library Design

### Factor Base Class

**Abstract Base Class**: All factors inherit from `FactorBase` for consistency

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from datetime import date

class FactorBase(ABC):
    """
    Abstract base class for all quantitative factors.

    All factors must implement:
    1. calculate() - Core factor calculation logic
    2. validate_inputs() - Input data validation
    3. normalize() - Normalization strategy (z-score, percentile)
    4. metadata property - Factor name, category, description
    """

    def __init__(self, db_manager, config: Optional[Dict] = None):
        self.db_manager = db_manager
        self.config = config or {}
        self.name = self.metadata['name']
        self.category = self.metadata['category']
        self.description = self.metadata['description']

    @property
    @abstractmethod
    def metadata(self) -> Dict:
        """
        Factor metadata for identification and documentation.

        Returns:
            Dict with keys: name, category, description, formula, data_requirements
        """
        pass

    @abstractmethod
    def calculate(self, tickers: List[str], region: str,
                  as_of_date: date) -> pd.DataFrame:
        """
        Calculate factor scores for given tickers.

        Args:
            tickers: List of ticker symbols
            region: Market region (KR, US, CN, HK, JP, VN)
            as_of_date: Calculation date

        Returns:
            DataFrame with columns: ticker, region, date, score
        """
        pass

    def validate_inputs(self, df: pd.DataFrame) -> bool:
        """
        Validate input data quality.

        Checks:
        - No NULL values in required columns
        - Data types correct
        - Sufficient historical data
        - Outlier detection
        """
        required_columns = self.metadata['data_requirements']

        # Check for required columns
        if not all(col in df.columns for col in required_columns):
            missing = set(required_columns) - set(df.columns)
            raise ValueError(f"Missing required columns: {missing}")

        # Check for NULL values
        null_counts = df[required_columns].isnull().sum()
        if null_counts.any():
            raise ValueError(f"NULL values detected: {null_counts[null_counts > 0]}")

        return True

    def normalize(self, df: pd.DataFrame, method: str = 'zscore') -> pd.DataFrame:
        """
        Normalize factor scores for cross-sectional comparison.

        Args:
            df: DataFrame with 'score' column
            method: 'zscore', 'percentile', 'minmax'

        Returns:
            DataFrame with normalized 'score' and 'percentile' columns
        """
        if method == 'zscore':
            # Winsorize outliers at 3 standard deviations
            mean = df['score'].mean()
            std = df['score'].std()
            df['score'] = df['score'].clip(mean - 3*std, mean + 3*std)

            # Z-score normalization
            df['score'] = (df['score'] - mean) / std

        elif method == 'percentile':
            # Rank-based percentile (0-100)
            df['score'] = df['score'].rank(pct=True) * 100

        elif method == 'minmax':
            # Min-max scaling (0-100)
            min_val = df['score'].min()
            max_val = df['score'].max()
            df['score'] = ((df['score'] - min_val) / (max_val - min_val)) * 100

        # Always compute percentile for storage
        df['percentile'] = df['score'].rank(pct=True) * 100

        return df

    def save_to_db(self, df: pd.DataFrame) -> int:
        """
        Save factor scores to factor_scores table (TimescaleDB hypertable).

        Args:
            df: DataFrame with columns: ticker, region, date, score, percentile

        Returns:
            Number of rows inserted
        """
        df['factor_name'] = self.name

        # Batch insert for performance
        insert_query = """
        INSERT INTO factor_scores (ticker, region, date, factor_name, score, percentile)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, region, date, factor_name)
        DO UPDATE SET score = EXCLUDED.score, percentile = EXCLUDED.percentile
        """

        rows = df[['ticker', 'region', 'date', 'factor_name', 'score', 'percentile']].values.tolist()

        with self.db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(insert_query, rows)
                conn.commit()

        return len(rows)
```

### Factor Categories and Implementations

#### 1. Value Factors

**Purpose**: Identify undervalued stocks based on fundamental metrics

##### A. P/E Ratio Factor

```python
class PERatioFactor(FactorBase):
    """
    Price-to-Earnings Ratio Factor

    Formula: P/E = Market Price / Earnings Per Share

    Lower P/E = Higher Score (Value)

    Data Requirements:
    - stock_details.current_price
    - ticker_fundamentals.eps (Earnings Per Share)
    """

    @property
    def metadata(self) -> Dict:
        return {
            'name': 'pe_ratio',
            'category': 'value',
            'description': 'Price-to-Earnings ratio - lower is better (value)',
            'formula': 'P/E = Market Price / EPS',
            'data_requirements': ['current_price', 'eps'],
            'invert': True  # Lower P/E is better, so invert for scoring
        }

    def calculate(self, tickers: List[str], region: str, as_of_date: date) -> pd.DataFrame:
        """Calculate P/E ratio for given tickers."""

        # Fetch price data
        price_query = """
        SELECT ticker, region, close AS current_price
        FROM ohlcv_data
        WHERE ticker = ANY(%s) AND region = %s AND date = %s
        """

        # Fetch fundamental data
        fundamental_query = """
        SELECT ticker, region, eps
        FROM ticker_fundamentals
        WHERE ticker = ANY(%s) AND region = %s AND date <= %s
        ORDER BY date DESC
        LIMIT 1
        """

        with self.db_manager.get_connection() as conn:
            prices = pd.read_sql(price_query, conn, params=(tickers, region, as_of_date))
            fundamentals = pd.read_sql(fundamental_query, conn, params=(tickers, region, as_of_date))

        # Merge data
        df = prices.merge(fundamentals, on=['ticker', 'region'], how='inner')

        # Calculate P/E ratio
        df['score'] = df['current_price'] / df['eps']

        # Remove invalid P/E (negative earnings, missing data)
        df = df[df['score'] > 0]

        # Invert P/E (lower is better for value)
        df['score'] = 1 / df['score']

        # Normalize
        df = self.normalize(df, method='zscore')

        df['date'] = as_of_date

        return df[['ticker', 'region', 'date', 'score', 'percentile']]
```

##### B. P/B Ratio Factor

```python
class PBRatioFactor(FactorBase):
    """
    Price-to-Book Ratio Factor

    Formula: P/B = Market Price / Book Value Per Share

    Lower P/B = Higher Score (Value)

    Data Requirements:
    - stock_details.current_price
    - ticker_fundamentals.book_value_per_share
    """

    @property
    def metadata(self) -> Dict:
        return {
            'name': 'pb_ratio',
            'category': 'value',
            'description': 'Price-to-Book ratio - lower is better (value)',
            'formula': 'P/B = Market Price / Book Value Per Share',
            'data_requirements': ['current_price', 'book_value_per_share'],
            'invert': True
        }

    def calculate(self, tickers: List[str], region: str, as_of_date: date) -> pd.DataFrame:
        """Calculate P/B ratio for given tickers."""

        # Similar to P/E calculation
        # Fetch price and book value, calculate ratio, normalize

        # (Implementation details omitted for brevity)
        pass
```

##### C. Dividend Yield Factor

```python
class DividendYieldFactor(FactorBase):
    """
    Dividend Yield Factor

    Formula: Div Yield = Annual Dividend / Market Price

    Higher Dividend Yield = Higher Score (Value)

    Data Requirements:
    - stock_details.current_price
    - ticker_fundamentals.annual_dividend
    """

    @property
    def metadata(self) -> Dict:
        return {
            'name': 'dividend_yield',
            'category': 'value',
            'description': 'Annual dividend yield - higher is better (income)',
            'formula': 'Div Yield = Annual Dividend / Price',
            'data_requirements': ['current_price', 'annual_dividend'],
            'invert': False  # Higher yield is better
        }

    def calculate(self, tickers: List[str], region: str, as_of_date: date) -> pd.DataFrame:
        """Calculate dividend yield for given tickers."""

        # Fetch price and dividend data
        # Calculate yield = dividend / price
        # Normalize

        # (Implementation details omitted for brevity)
        pass
```

#### 2. Momentum Factors

**Purpose**: Identify stocks with strong price trends

##### A. 12-Month Price Momentum Factor

```python
class PriceMomentumFactor(FactorBase):
    """
    12-Month Price Momentum Factor (excluding last month)

    Formula: Return = (Price_t-1 / Price_t-12) - 1

    Excludes last month to avoid short-term reversal.

    Higher Return = Higher Score (Momentum)

    Data Requirements:
    - ohlcv_data (252 days for 12 months, excluding 21 days for last month)
    """

    @property
    def metadata(self) -> Dict:
        return {
            'name': 'price_momentum_12m',
            'category': 'momentum',
            'description': '12-month price return (excluding last month)',
            'formula': '(Price_t-21 / Price_t-252) - 1',
            'data_requirements': ['close'],
            'lookback_days': 252,
            'exclude_last_days': 21,
            'invert': False  # Higher momentum is better
        }

    def calculate(self, tickers: List[str], region: str, as_of_date: date) -> pd.DataFrame:
        """Calculate 12-month price momentum."""

        # Fetch 252 days of historical prices
        query = """
        SELECT ticker, region, date, close
        FROM ohlcv_data
        WHERE ticker = ANY(%s)
          AND region = %s
          AND date BETWEEN %s - INTERVAL '252 days' AND %s
        ORDER BY ticker, date
        """

        with self.db_manager.get_connection() as conn:
            df = pd.read_sql(query, conn, params=(tickers, region, as_of_date, as_of_date))

        # Calculate return: (Price_t-21 / Price_t-252) - 1
        results = []
        for ticker in tickers:
            ticker_df = df[df['ticker'] == ticker].sort_values('date')

            if len(ticker_df) < 252:
                continue  # Insufficient data

            price_t_21 = ticker_df.iloc[-21]['close']  # Price 21 days ago
            price_t_252 = ticker_df.iloc[0]['close']   # Price 252 days ago

            momentum = (price_t_21 / price_t_252) - 1

            results.append({
                'ticker': ticker,
                'region': region,
                'date': as_of_date,
                'score': momentum
            })

        df = pd.DataFrame(results)

        # Normalize
        df = self.normalize(df, method='zscore')

        return df[['ticker', 'region', 'date', 'score', 'percentile']]
```

##### B. RSI Momentum Factor

```python
class RSIMomentumFactor(FactorBase):
    """
    RSI-Based Momentum Factor

    Formula: RSI = 100 - (100 / (1 + RS))
    where RS = Average Gain / Average Loss (14-day)

    Higher RSI (50-100) = Higher Score (Momentum)
    Lower RSI (0-50) = Lower Score (Oversold)

    Data Requirements:
    - technical_analysis.rsi_14
    """

    @property
    def metadata(self) -> Dict:
        return {
            'name': 'rsi_momentum',
            'category': 'momentum',
            'description': 'RSI-based momentum (14-day)',
            'formula': 'RSI = 100 - (100 / (1 + RS))',
            'data_requirements': ['rsi_14'],
            'invert': False
        }

    def calculate(self, tickers: List[str], region: str, as_of_date: date) -> pd.DataFrame:
        """Calculate RSI momentum."""

        # Fetch RSI data from technical_analysis table
        query = """
        SELECT ticker, region, date, rsi_14 AS score
        FROM technical_analysis
        WHERE ticker = ANY(%s) AND region = %s AND date = %s
        """

        with self.db_manager.get_connection() as conn:
            df = pd.read_sql(query, conn, params=(tickers, region, as_of_date))

        # RSI already in 0-100 range
        # Normalize for cross-sectional comparison
        df = self.normalize(df, method='zscore')

        return df[['ticker', 'region', 'date', 'score', 'percentile']]
```

#### 3. Quality Factors

**Purpose**: Identify companies with strong fundamentals and business quality

##### A. Return on Equity (ROE) Factor

```python
class ROEFactor(FactorBase):
    """
    Return on Equity (ROE) Factor

    Formula: ROE = Net Income / Shareholders' Equity

    Higher ROE = Higher Score (Quality)

    Data Requirements:
    - ticker_fundamentals.net_income
    - ticker_fundamentals.shareholders_equity
    """

    @property
    def metadata(self) -> Dict:
        return {
            'name': 'roe',
            'category': 'quality',
            'description': 'Return on Equity - higher is better (profitability)',
            'formula': 'ROE = Net Income / Shareholders Equity',
            'data_requirements': ['net_income', 'shareholders_equity'],
            'invert': False
        }

    def calculate(self, tickers: List[str], region: str, as_of_date: date) -> pd.DataFrame:
        """Calculate ROE for given tickers."""

        # Fetch fundamental data
        query = """
        SELECT ticker, region, net_income, shareholders_equity
        FROM ticker_fundamentals
        WHERE ticker = ANY(%s) AND region = %s AND date <= %s
        ORDER BY date DESC
        LIMIT 1
        """

        with self.db_manager.get_connection() as conn:
            df = pd.read_sql(query, conn, params=(tickers, region, as_of_date))

        # Calculate ROE
        df['score'] = df['net_income'] / df['shareholders_equity']

        # Remove invalid ROE (negative equity, missing data)
        df = df[df['shareholders_equity'] > 0]

        # Normalize
        df = self.normalize(df, method='zscore')

        df['date'] = as_of_date

        return df[['ticker', 'region', 'date', 'score', 'percentile']]
```

##### B. Debt-to-Equity Factor

```python
class DebtToEquityFactor(FactorBase):
    """
    Debt-to-Equity Ratio Factor

    Formula: D/E = Total Debt / Shareholders' Equity

    Lower D/E = Higher Score (Quality - Financial Stability)

    Data Requirements:
    - ticker_fundamentals.total_debt
    - ticker_fundamentals.shareholders_equity
    """

    @property
    def metadata(self) -> Dict:
        return {
            'name': 'debt_to_equity',
            'category': 'quality',
            'description': 'Debt-to-Equity ratio - lower is better (financial stability)',
            'formula': 'D/E = Total Debt / Shareholders Equity',
            'data_requirements': ['total_debt', 'shareholders_equity'],
            'invert': True  # Lower D/E is better
        }

    def calculate(self, tickers: List[str], region: str, as_of_date: date) -> pd.DataFrame:
        """Calculate Debt-to-Equity ratio."""

        # Similar to ROE calculation
        # Fetch debt and equity data, calculate ratio, normalize

        # (Implementation details omitted for brevity)
        pass
```

#### 4. Low-Volatility Factors

**Purpose**: Identify stocks with lower risk characteristics

##### A. Historical Volatility Factor

```python
class VolatilityFactor(FactorBase):
    """
    Historical Volatility Factor (60-day)

    Formula: Volatility = StdDev(Daily Returns) × √252 (annualized)

    Lower Volatility = Higher Score (Low-Vol)

    Data Requirements:
    - ohlcv_data (60 days for volatility calculation)
    """

    @property
    def metadata(self) -> Dict:
        return {
            'name': 'volatility_60d',
            'category': 'low_volatility',
            'description': '60-day annualized volatility - lower is better (risk)',
            'formula': 'StdDev(Daily Returns) × √252',
            'data_requirements': ['close'],
            'lookback_days': 60,
            'invert': True  # Lower volatility is better
        }

    def calculate(self, tickers: List[str], region: str, as_of_date: date) -> pd.DataFrame:
        """Calculate 60-day historical volatility."""

        # Fetch 60 days of historical prices
        query = """
        SELECT ticker, region, date, close
        FROM ohlcv_data
        WHERE ticker = ANY(%s)
          AND region = %s
          AND date BETWEEN %s - INTERVAL '60 days' AND %s
        ORDER BY ticker, date
        """

        with self.db_manager.get_connection() as conn:
            df = pd.read_sql(query, conn, params=(tickers, region, as_of_date, as_of_date))

        # Calculate daily returns and volatility
        results = []
        for ticker in tickers:
            ticker_df = df[df['ticker'] == ticker].sort_values('date')

            if len(ticker_df) < 60:
                continue  # Insufficient data

            # Calculate daily returns
            ticker_df['return'] = ticker_df['close'].pct_change()

            # Annualized volatility = StdDev(daily returns) × √252
            volatility = ticker_df['return'].std() * np.sqrt(252)

            results.append({
                'ticker': ticker,
                'region': region,
                'date': as_of_date,
                'score': volatility
            })

        df = pd.DataFrame(results)

        # Invert volatility (lower is better)
        df['score'] = 1 / df['score']

        # Normalize
        df = self.normalize(df, method='zscore')

        return df[['ticker', 'region', 'date', 'score', 'percentile']]
```

##### B. Beta Factor

```python
class BetaFactor(FactorBase):
    """
    Beta Factor (Market Sensitivity)

    Formula: Beta = Covariance(Stock Returns, Market Returns) / Variance(Market Returns)

    Lower Beta (< 1.0) = Higher Score (Low-Vol - Low Market Sensitivity)

    Data Requirements:
    - ohlcv_data (252 days for stock and market index)
    - global_market_indices (252 days for market benchmark)
    """

    @property
    def metadata(self) -> Dict:
        return {
            'name': 'beta',
            'category': 'low_volatility',
            'description': 'Beta vs market index - lower is better (market sensitivity)',
            'formula': 'Beta = Cov(Stock, Market) / Var(Market)',
            'data_requirements': ['close', 'market_index'],
            'lookback_days': 252,
            'invert': True  # Lower beta is better for low-vol
        }

    def calculate(self, tickers: List[str], region: str, as_of_date: date) -> pd.DataFrame:
        """Calculate beta for given tickers."""

        # Fetch stock prices
        stock_query = """
        SELECT ticker, region, date, close
        FROM ohlcv_data
        WHERE ticker = ANY(%s)
          AND region = %s
          AND date BETWEEN %s - INTERVAL '252 days' AND %s
        ORDER BY ticker, date
        """

        # Fetch market index prices
        market_query = """
        SELECT date, close AS market_close
        FROM global_market_indices
        WHERE index_code = %s  -- e.g., 'KOSPI' for KR, 'SPX' for US
          AND date BETWEEN %s - INTERVAL '252 days' AND %s
        ORDER BY date
        """

        # Get appropriate market index for region
        market_index_map = {
            'KR': 'KOSPI',
            'US': 'SPX',
            'CN': 'CSI300',
            'HK': 'HSI',
            'JP': 'NIKKEI225',
            'VN': 'VN30'
        }
        market_index = market_index_map.get(region, 'SPX')

        with self.db_manager.get_connection() as conn:
            stock_df = pd.read_sql(stock_query, conn, params=(tickers, region, as_of_date, as_of_date))
            market_df = pd.read_sql(market_query, conn, params=(market_index, as_of_date, as_of_date))

        # Calculate beta for each ticker
        results = []
        for ticker in tickers:
            ticker_df = stock_df[stock_df['ticker'] == ticker].sort_values('date')

            if len(ticker_df) < 252 or len(market_df) < 252:
                continue  # Insufficient data

            # Merge stock and market data
            merged = ticker_df.merge(market_df, on='date', how='inner')

            # Calculate returns
            merged['stock_return'] = merged['close'].pct_change()
            merged['market_return'] = merged['market_close'].pct_change()

            # Calculate beta = Cov(stock, market) / Var(market)
            covariance = merged[['stock_return', 'market_return']].cov().iloc[0, 1]
            market_variance = merged['market_return'].var()

            beta = covariance / market_variance

            results.append({
                'ticker': ticker,
                'region': region,
                'date': as_of_date,
                'score': beta
            })

        df = pd.DataFrame(results)

        # Invert beta (lower is better for low-vol)
        df['score'] = 1 / df['score']

        # Normalize
        df = self.normalize(df, method='zscore')

        return df[['ticker', 'region', 'date', 'score', 'percentile']]
```

#### 5. Size Factors

**Purpose**: Identify small-cap vs large-cap stocks

##### A. Market Capitalization Factor

```python
class MarketCapFactor(FactorBase):
    """
    Market Capitalization Factor

    Formula: Market Cap = Share Price × Shares Outstanding

    Smaller Market Cap = Higher Score (Size Premium)

    Data Requirements:
    - stock_details.current_price
    - stock_details.shares_outstanding
    """

    @property
    def metadata(self) -> Dict:
        return {
            'name': 'market_cap',
            'category': 'size',
            'description': 'Market capitalization - smaller is better (size premium)',
            'formula': 'Market Cap = Price × Shares Outstanding',
            'data_requirements': ['current_price', 'shares_outstanding'],
            'invert': True  # Smaller cap is better for size premium
        }

    def calculate(self, tickers: List[str], region: str, as_of_date: date) -> pd.DataFrame:
        """Calculate market capitalization."""

        # Fetch price data
        price_query = """
        SELECT ticker, region, close AS current_price
        FROM ohlcv_data
        WHERE ticker = ANY(%s) AND region = %s AND date = %s
        """

        # Fetch shares outstanding
        shares_query = """
        SELECT ticker, region, shares_outstanding
        FROM stock_details
        WHERE ticker = ANY(%s) AND region = %s
        """

        with self.db_manager.get_connection() as conn:
            prices = pd.read_sql(price_query, conn, params=(tickers, region, as_of_date))
            shares = pd.read_sql(shares_query, conn, params=(tickers, region))

        # Merge data
        df = prices.merge(shares, on=['ticker', 'region'], how='inner')

        # Calculate market cap
        df['score'] = df['current_price'] * df['shares_outstanding']

        # Invert market cap (smaller is better for size premium)
        df['score'] = 1 / df['score']

        # Normalize
        df = self.normalize(df, method='zscore')

        df['date'] = as_of_date

        return df[['ticker', 'region', 'date', 'score', 'percentile']]
```

---

## Factor Calculation Engine

### FactorCalculator Class

**Purpose**: Orchestrate batch calculation of all factors for the entire universe

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
import pandas as pd
from datetime import date
import time

class FactorCalculator:
    """
    Factor Calculation Orchestrator

    Responsibilities:
    1. Register all factors
    2. Calculate factors in parallel for performance
    3. Handle errors and missing data gracefully
    4. Store results in database
    5. Monitor performance metrics
    """

    def __init__(self, db_manager, config: Optional[Dict] = None):
        self.db_manager = db_manager
        self.config = config or {}
        self.factors = {}  # Registry of all factor instances
        self.performance_metrics = {}

    def register_factor(self, factor: FactorBase):
        """Register a factor for calculation."""
        self.factors[factor.name] = factor

    def register_all_factors(self):
        """Register all 20+ factors."""

        # Value Factors
        self.register_factor(PERatioFactor(self.db_manager))
        self.register_factor(PBRatioFactor(self.db_manager))
        self.register_factor(EVToEBITDAFactor(self.db_manager))
        self.register_factor(DividendYieldFactor(self.db_manager))
        self.register_factor(FCFYieldFactor(self.db_manager))

        # Momentum Factors
        self.register_factor(PriceMomentumFactor(self.db_manager))
        self.register_factor(RSIMomentumFactor(self.db_manager))
        self.register_factor(FiftyTwoWeekHighFactor(self.db_manager))
        self.register_factor(VolumeWeightedMomentumFactor(self.db_manager))
        self.register_factor(EarningsMomentumFactor(self.db_manager))

        # Quality Factors
        self.register_factor(ROEFactor(self.db_manager))
        self.register_factor(DebtToEquityFactor(self.db_manager))
        self.register_factor(EarningsQualityFactor(self.db_manager))
        self.register_factor(ProfitMarginFactor(self.db_manager))
        self.register_factor(CashFlowQualityFactor(self.db_manager))

        # Low-Volatility Factors
        self.register_factor(VolatilityFactor(self.db_manager))
        self.register_factor(BetaFactor(self.db_manager))
        self.register_factor(MaxDrawdownFactor(self.db_manager))
        self.register_factor(DownsideDeviationFactor(self.db_manager))
        self.register_factor(CVaRFactor(self.db_manager))

        # Size Factors
        self.register_factor(MarketCapFactor(self.db_manager))
        self.register_factor(LiquidityFactor(self.db_manager))
        self.register_factor(FreeFloatFactor(self.db_manager))

    def calculate_all_factors(self, region: str, as_of_date: date,
                              parallel: bool = True) -> Dict:
        """
        Calculate all registered factors for entire universe.

        Args:
            region: Market region (KR, US, CN, HK, JP, VN)
            as_of_date: Calculation date
            parallel: Use parallel processing (default: True)

        Returns:
            Dict with summary statistics
        """
        start_time = time.time()

        # Get all tickers for region
        tickers = self._get_tickers_for_region(region)

        print(f"Calculating {len(self.factors)} factors for {len(tickers)} tickers in {region}...")

        if parallel:
            results = self._calculate_parallel(tickers, region, as_of_date)
        else:
            results = self._calculate_sequential(tickers, region, as_of_date)

        elapsed_time = time.time() - start_time

        # Summary statistics
        summary = {
            'region': region,
            'date': as_of_date,
            'num_factors': len(self.factors),
            'num_tickers': len(tickers),
            'num_scores': sum(len(r) for r in results.values()),
            'elapsed_time_seconds': elapsed_time,
            'scores_per_second': sum(len(r) for r in results.values()) / elapsed_time,
            'success_rate': sum(1 for r in results.values() if len(r) > 0) / len(self.factors)
        }

        print(f"✅ Factor calculation complete: {summary['num_scores']} scores in {elapsed_time:.2f}s "
              f"({summary['scores_per_second']:.0f} scores/sec)")

        return summary

    def _calculate_parallel(self, tickers: List[str], region: str,
                            as_of_date: date) -> Dict:
        """Calculate factors in parallel using ThreadPoolExecutor."""

        results = {}
        max_workers = self.config.get('max_workers', 8)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all factor calculations
            future_to_factor = {
                executor.submit(factor.calculate, tickers, region, as_of_date): factor_name
                for factor_name, factor in self.factors.items()
            }

            # Collect results as they complete
            for future in as_completed(future_to_factor):
                factor_name = future_to_factor[future]
                try:
                    df = future.result()

                    # Save to database
                    factor = self.factors[factor_name]
                    rows_inserted = factor.save_to_db(df)

                    results[factor_name] = df
                    print(f"  ✅ {factor_name}: {rows_inserted} scores calculated")

                except Exception as e:
                    print(f"  ❌ {factor_name}: Error - {str(e)}")
                    results[factor_name] = pd.DataFrame()  # Empty DataFrame on error

        return results

    def _calculate_sequential(self, tickers: List[str], region: str,
                              as_of_date: date) -> Dict:
        """Calculate factors sequentially (for debugging)."""

        results = {}

        for factor_name, factor in self.factors.items():
            try:
                df = factor.calculate(tickers, region, as_of_date)
                rows_inserted = factor.save_to_db(df)

                results[factor_name] = df
                print(f"  ✅ {factor_name}: {rows_inserted} scores calculated")

            except Exception as e:
                print(f"  ❌ {factor_name}: Error - {str(e)}")
                results[factor_name] = pd.DataFrame()

        return results

    def _get_tickers_for_region(self, region: str) -> List[str]:
        """Get all active tickers for a region."""

        query = """
        SELECT ticker
        FROM tickers
        WHERE region = %s AND asset_type IN ('stock', 'etf')
        ORDER BY ticker
        """

        with self.db_manager.get_connection() as conn:
            df = pd.read_sql(query, conn, params=(region,))

        return df['ticker'].tolist()

    def calculate_single_factor(self, factor_name: str, tickers: List[str],
                                region: str, as_of_date: date) -> pd.DataFrame:
        """
        Calculate a single factor (for testing/debugging).

        Args:
            factor_name: Name of factor to calculate
            tickers: List of tickers
            region: Market region
            as_of_date: Calculation date

        Returns:
            DataFrame with factor scores
        """
        if factor_name not in self.factors:
            raise ValueError(f"Factor '{factor_name}' not registered")

        factor = self.factors[factor_name]

        df = factor.calculate(tickers, region, as_of_date)
        factor.save_to_db(df)

        return df
```

---

## Factor Combination Framework

### FactorCombiner Base Class

```python
from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
from typing import Dict, List

class FactorCombiner(ABC):
    """
    Abstract base class for factor combination strategies.

    Combines multiple factor scores into a single composite score (0-100).
    """

    def __init__(self, db_manager, config: Optional[Dict] = None):
        self.db_manager = db_manager
        self.config = config or {}

    @abstractmethod
    def combine(self, factor_names: List[str], tickers: List[str],
                region: str, as_of_date: date) -> pd.DataFrame:
        """
        Combine factor scores into composite score.

        Args:
            factor_names: List of factor names to combine
            tickers: List of tickers
            region: Market region
            as_of_date: Calculation date

        Returns:
            DataFrame with columns: ticker, region, date, composite_score
        """
        pass

    def fetch_factor_scores(self, factor_names: List[str], tickers: List[str],
                           region: str, as_of_date: date) -> pd.DataFrame:
        """Fetch factor scores from database."""

        query = """
        SELECT ticker, region, date, factor_name, score, percentile
        FROM factor_scores
        WHERE ticker = ANY(%s)
          AND region = %s
          AND date = %s
          AND factor_name = ANY(%s)
        """

        with self.db_manager.get_connection() as conn:
            df = pd.read_sql(query, conn, params=(tickers, region, as_of_date, factor_names))

        return df
```

### Equal Weight Combiner

```python
class EqualWeightCombiner(FactorCombiner):
    """
    Equal Weight Factor Combination

    Composite Score = Average(Factor Scores)

    Simplest approach, no assumptions about factor performance.
    """

    def combine(self, factor_names: List[str], tickers: List[str],
                region: str, as_of_date: date) -> pd.DataFrame:
        """Combine factors using equal weights."""

        # Fetch all factor scores
        df = self.fetch_factor_scores(factor_names, tickers, region, as_of_date)

        # Pivot to wide format (tickers × factors)
        pivot_df = df.pivot_table(
            index=['ticker', 'region', 'date'],
            columns='factor_name',
            values='score'
        ).reset_index()

        # Calculate equal-weighted composite score
        pivot_df['composite_score'] = pivot_df[factor_names].mean(axis=1)

        # Normalize composite score to 0-100 range
        pivot_df['composite_score'] = (
            (pivot_df['composite_score'] - pivot_df['composite_score'].min()) /
            (pivot_df['composite_score'].max() - pivot_df['composite_score'].min()) * 100
        )

        return pivot_df[['ticker', 'region', 'date', 'composite_score']]
```

### Optimization-Based Combiner

```python
from scipy.optimize import minimize

class OptimizationCombiner(FactorCombiner):
    """
    Optimization-Based Factor Combination

    Maximize Sharpe Ratio of composite factor returns.

    Uses historical factor returns to find optimal weights.
    """

    def combine(self, factor_names: List[str], tickers: List[str],
                region: str, as_of_date: date) -> pd.DataFrame:
        """Combine factors using optimized weights."""

        # Get historical factor returns (last 252 trading days)
        historical_returns = self._get_historical_factor_returns(
            factor_names, region, as_of_date, lookback_days=252
        )

        # Optimize weights to maximize Sharpe ratio
        optimal_weights = self._optimize_weights(historical_returns)

        # Fetch current factor scores
        df = self.fetch_factor_scores(factor_names, tickers, region, as_of_date)

        # Pivot to wide format
        pivot_df = df.pivot_table(
            index=['ticker', 'region', 'date'],
            columns='factor_name',
            values='score'
        ).reset_index()

        # Calculate weighted composite score
        pivot_df['composite_score'] = sum(
            pivot_df[factor_name] * weight
            for factor_name, weight in zip(factor_names, optimal_weights)
        )

        # Normalize to 0-100 range
        pivot_df['composite_score'] = (
            (pivot_df['composite_score'] - pivot_df['composite_score'].min()) /
            (pivot_df['composite_score'].max() - pivot_df['composite_score'].min()) * 100
        )

        return pivot_df[['ticker', 'region', 'date', 'composite_score']]

    def _get_historical_factor_returns(self, factor_names: List[str],
                                       region: str, as_of_date: date,
                                       lookback_days: int) -> pd.DataFrame:
        """Get historical returns for each factor (top decile vs bottom decile)."""

        # (Implementation: Fetch factor scores for last 252 days, compute returns)
        # Returns DataFrame with columns: date, factor_name, return
        pass

    def _optimize_weights(self, historical_returns: pd.DataFrame) -> np.ndarray:
        """
        Optimize factor weights to maximize Sharpe ratio.

        Constraint: Weights sum to 1.0
        """

        # Pivot to wide format (dates × factors)
        pivot_df = historical_returns.pivot_table(
            index='date',
            columns='factor_name',
            values='return'
        )

        # Calculate mean returns and covariance matrix
        mean_returns = pivot_df.mean()
        cov_matrix = pivot_df.cov()

        num_factors = len(mean_returns)

        # Objective function: Negative Sharpe ratio (minimize)
        def objective(weights):
            portfolio_return = np.dot(weights, mean_returns)
            portfolio_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
            sharpe_ratio = portfolio_return / portfolio_std
            return -sharpe_ratio  # Minimize negative Sharpe = Maximize Sharpe

        # Constraints
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}  # Weights sum to 1
        ]

        # Bounds (0 to 1 for each weight)
        bounds = [(0, 1) for _ in range(num_factors)]

        # Initial guess (equal weights)
        initial_weights = np.array([1.0 / num_factors] * num_factors)

        # Optimize
        result = minimize(
            objective,
            initial_weights,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints
        )

        return result.x
```

### Risk-Adjusted Combiner

```python
class RiskAdjustedCombiner(FactorCombiner):
    """
    Risk-Adjusted Factor Combination

    Inverse Volatility Weighting

    Higher volatility factors get lower weight.
    """

    def combine(self, factor_names: List[str], tickers: List[str],
                region: str, as_of_date: date) -> pd.DataFrame:
        """Combine factors using inverse volatility weights."""

        # Get historical factor volatilities
        factor_volatilities = self._get_factor_volatilities(factor_names, region, as_of_date)

        # Calculate inverse volatility weights
        inverse_vols = 1 / factor_volatilities
        weights = inverse_vols / inverse_vols.sum()

        # Fetch current factor scores
        df = self.fetch_factor_scores(factor_names, tickers, region, as_of_date)

        # Pivot to wide format
        pivot_df = df.pivot_table(
            index=['ticker', 'region', 'date'],
            columns='factor_name',
            values='score'
        ).reset_index()

        # Calculate weighted composite score
        pivot_df['composite_score'] = sum(
            pivot_df[factor_name] * weight
            for factor_name, weight in zip(factor_names, weights)
        )

        # Normalize to 0-100 range
        pivot_df['composite_score'] = (
            (pivot_df['composite_score'] - pivot_df['composite_score'].min()) /
            (pivot_df['composite_score'].max() - pivot_df['composite_score'].min()) * 100
        )

        return pivot_df[['ticker', 'region', 'date', 'composite_score']]

    def _get_factor_volatilities(self, factor_names: List[str],
                                 region: str, as_of_date: date) -> pd.Series:
        """Calculate historical volatility of factor returns (last 252 days)."""

        # (Implementation: Fetch factor scores for last 252 days, compute volatility)
        # Returns Series with factor_name as index, volatility as values
        pass
```

---

## Database Integration

### factor_scores Table (TimescaleDB Hypertable)

**Already created in Phase 1** - No schema changes needed.

```sql
-- Existing schema (from Phase 1)
CREATE TABLE factor_scores (
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    date DATE NOT NULL,
    factor_name VARCHAR(50) NOT NULL,
    score NUMERIC(10, 4),
    percentile NUMERIC(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (ticker, region, date, factor_name)
);

-- TimescaleDB hypertable (already configured)
SELECT create_hypertable('factor_scores', 'date', if_not_exists => TRUE);

-- Compression policy (already configured)
ALTER TABLE factor_scores SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'ticker, region, factor_name',
    timescaledb.compress_orderby = 'date DESC'
);

SELECT add_compression_policy('factor_scores', INTERVAL '365 days');

-- Indexes (already created)
CREATE INDEX idx_factor_scores_ticker ON factor_scores(ticker, region, date DESC);
CREATE INDEX idx_factor_scores_factor ON factor_scores(factor_name, date DESC);
CREATE INDEX idx_factor_scores_date ON factor_scores(date DESC);
```

### Continuous Aggregates for Factor Analysis

**New**: Create continuous aggregates for factor performance metrics

```sql
-- Monthly factor score averages (for factor analysis)
CREATE MATERIALIZED VIEW factor_scores_monthly
WITH (timescaledb.continuous) AS
SELECT ticker, region, factor_name,
       time_bucket('1 month', date) AS month,
       AVG(score) AS avg_score,
       STDDEV(score) AS stddev_score,
       MIN(score) AS min_score,
       MAX(score) AS max_score,
       AVG(percentile) AS avg_percentile
FROM factor_scores
GROUP BY ticker, region, factor_name, month;

-- Refresh policy (daily at 03:00 UTC)
SELECT add_continuous_aggregate_policy('factor_scores_monthly',
    start_offset => INTERVAL '3 months',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');

-- Factor correlation matrix (cross-sectional, daily)
CREATE MATERIALIZED VIEW factor_correlation_daily
WITH (timescaledb.continuous) AS
SELECT region, date, factor_name,
       AVG(score) AS mean_score,
       STDDEV(score) AS stddev_score,
       COUNT(*) AS num_stocks
FROM factor_scores
GROUP BY region, date, factor_name;

-- Refresh policy (daily at 04:00 UTC)
SELECT add_continuous_aggregate_policy('factor_correlation_daily',
    start_offset => INTERVAL '1 month',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');
```

---

## Performance Optimization

### Calculation Performance

**Target**: <5 seconds for full universe factor calculation (18K tickers × 20 factors)

**Optimization Strategies**:

1. **Parallel Processing**: Use `ThreadPoolExecutor` for concurrent factor calculations
2. **Batch Database Queries**: Fetch all tickers at once, minimize round-trips
3. **In-Memory Caching**: Cache frequently accessed data (market indices, fundamental data)
4. **Vectorized Operations**: Use NumPy/Pandas vectorization instead of Python loops
5. **Database Indexes**: Ensure all factor_scores queries use indexes

### Storage Performance

**Expected Storage**:
- **Raw factor scores**: 18,661 tickers × 20 factors × 365 days = 136M rows/year
- **Uncompressed**: ~136M rows × 80 bytes = ~11GB/year
- **Compressed (10x)**: ~1.1GB/year

**Compression Strategy**:
- Compress data older than 365 days (automatic)
- Segment by (ticker, region, factor_name) for efficient queries
- Order by date DESC for time-series access patterns

### Query Performance

**Target**: <10ms for factor retrieval queries

**Optimization**:
1. **Indexes**: Ensure all queries use indexes (ticker, region, date, factor_name)
2. **Continuous Aggregates**: Pre-compute monthly averages for factor analysis
3. **Connection Pooling**: Reuse database connections (already configured in Phase 1)
4. **Query Plan Analysis**: Use EXPLAIN ANALYZE to verify index usage

**Example Query Performance**:
```sql
-- Fetch all factors for a ticker (should use idx_factor_scores_ticker)
EXPLAIN ANALYZE
SELECT ticker, region, date, factor_name, score, percentile
FROM factor_scores
WHERE ticker = '005930' AND region = 'KR' AND date = '2025-10-21';

-- Expected: Index Scan using idx_factor_scores_ticker (cost <10ms)
```

---

## Implementation Plan

### Phase 2 Task Breakdown

**Total Estimated Time**: 2-3 weeks (based on CLAUDE.md roadmap)

#### Week 1: Factor Library Foundation

**Task 1.1**: Factor Base Class and Registry (Day 1-2)
- [ ] Implement `factor_base.py` (FactorBase, FactorRegistry, FactorValidator, FactorCache)
- [ ] Unit tests for base class functionality
- [ ] Documentation

**Task 1.2**: Value Factors (Day 3-4)
- [ ] Implement 5 value factors (P/E, P/B, EV/EBITDA, Div Yield, FCF Yield)
- [ ] Unit tests for each factor
- [ ] Integration tests with PostgreSQL

**Task 1.3**: Momentum Factors (Day 5)
- [ ] Implement 5 momentum factors (12M return, RSI, 52W high, vol-weighted, earnings)
- [ ] Unit tests and integration tests

#### Week 2: Quality, Low-Vol, Size Factors

**Task 2.1**: Quality Factors (Day 1-2)
- [ ] Implement 5 quality factors (ROE, D/E, earnings quality, margin, cash flow)
- [ ] Unit tests and integration tests

**Task 2.2**: Low-Volatility Factors (Day 3-4)
- [ ] Implement 5 low-vol factors (volatility, beta, drawdown, downside dev, CVaR)
- [ ] Unit tests and integration tests

**Task 2.3**: Size Factors (Day 5)
- [ ] Implement 3 size factors (market cap, liquidity, free float)
- [ ] Unit tests and integration tests

#### Week 3: Calculation Engine and Combination Framework

**Task 3.1**: Factor Calculation Engine (Day 1-2)
- [ ] Implement `factor_calculator.py` (FactorCalculator with parallel processing)
- [ ] Performance testing and optimization
- [ ] Continuous aggregates for factor analysis

**Task 3.2**: Factor Combination Framework (Day 3-4)
- [ ] Implement 4 combiners (Equal Weight, Optimization, Risk-Adjusted, ML)
- [ ] Backtesting of combination strategies
- [ ] Integration tests

**Task 3.3**: Factor Analyzer and Documentation (Day 5)
- [ ] Implement `factor_analyzer.py` (historical returns, correlation, turnover)
- [ ] Complete documentation (FACTOR_LIBRARY_REFERENCE.md)
- [ ] End-to-end testing

---

## Testing Strategy

### Unit Tests

**Test Coverage**: >90% for all factor classes

**Test Cases**:
1. **FactorBase Tests**:
   - Metadata validation
   - Input validation (missing columns, NULL values, data types)
   - Normalization (z-score, percentile, min-max)
   - Database save/retrieve

2. **Factor-Specific Tests**:
   - Calculation correctness (manual verification of formulas)
   - Edge cases (zero/negative values, missing data, outliers)
   - Performance (calculation time <1 second for 100 tickers)

3. **FactorCalculator Tests**:
   - Parallel vs sequential calculation consistency
   - Error handling (missing data, database failures)
   - Performance benchmarks (<5 seconds for full universe)

4. **FactorCombiner Tests**:
   - Composite score calculation
   - Weight optimization convergence
   - Edge cases (single factor, all factors equal)

### Integration Tests

**Test Scenarios**:
1. **End-to-End Workflow**:
   - Calculate all factors for KR market
   - Combine factors into composite score
   - Store results in database
   - Retrieve and validate

2. **Multi-Region Testing**:
   - Test KR, US, CN, HK, JP, VN markets
   - Verify region-specific market indices (KOSPI, SPX, etc.)
   - Cross-region factor consistency

3. **Historical Backfill**:
   - Calculate factors for last 365 days
   - Verify compression policy activation
   - Query performance for compressed data

### Performance Tests

**Benchmarks**:
1. **Factor Calculation Speed**:
   - Single factor: <50ms for 1,000 tickers
   - All factors (parallel): <5 seconds for 18,661 tickers

2. **Database Performance**:
   - Factor insertion: >1,000 rows/second
   - Factor retrieval: <10ms for single ticker, all factors
   - Continuous aggregate refresh: <30 seconds

3. **Memory Usage**:
   - Factor calculation: <2GB RAM for full universe
   - Database connection pool: <100MB overhead

---

## API Specification

### FactorCalculator API

```python
# Initialize
from modules.db_manager_postgres import DBManagerPostgres
from modules.factors.factor_calculator import FactorCalculator

db_manager = DBManagerPostgres()
calculator = FactorCalculator(db_manager)
calculator.register_all_factors()

# Calculate all factors for a region
summary = calculator.calculate_all_factors(
    region='KR',
    as_of_date=date(2025, 10, 21),
    parallel=True
)

# Calculate single factor
df = calculator.calculate_single_factor(
    factor_name='pe_ratio',
    tickers=['005930', '000660', '035720'],
    region='KR',
    as_of_date=date(2025, 10, 21)
)
```

### FactorCombiner API

```python
from modules.factors.factor_combiner import EqualWeightCombiner, OptimizationCombiner

# Equal weight combination
combiner = EqualWeightCombiner(db_manager)
composite_df = combiner.combine(
    factor_names=['pe_ratio', 'pb_ratio', 'price_momentum_12m', 'roe'],
    tickers=['005930', '000660', '035720'],
    region='KR',
    as_of_date=date(2025, 10, 21)
)

# Optimization-based combination
opt_combiner = OptimizationCombiner(db_manager)
composite_df = opt_combiner.combine(
    factor_names=['pe_ratio', 'pb_ratio', 'price_momentum_12m', 'roe'],
    tickers=['005930', '000660', '035720'],
    region='KR',
    as_of_date=date(2025, 10, 21)
)
```

### FactorAnalyzer API

```python
from modules.factors.factor_analyzer import FactorAnalyzer

analyzer = FactorAnalyzer(db_manager)

# Analyze factor returns
factor_returns = analyzer.analyze_factor_returns(
    factor_name='price_momentum_12m',
    region='KR',
    start_date=date(2020, 1, 1),
    end_date=date(2025, 10, 21)
)

# Factor correlation matrix
correlation_matrix = analyzer.factor_correlation(
    factor_names=['pe_ratio', 'pb_ratio', 'price_momentum_12m', 'roe'],
    region='KR',
    as_of_date=date(2025, 10, 21)
)

# Factor turnover analysis
turnover = analyzer.factor_turnover(
    factor_name='price_momentum_12m',
    region='KR',
    window_days=30
)
```

---

## Next Steps

### After Phase 2 Completion

**Phase 3: Backtesting Engine** (Weeks 5-6)
- Integrate backtrader, zipline, vectorbt
- Implement transaction cost model
- Performance metrics calculator

**Phase 4: Portfolio Optimization** (Week 7)
- Mean-variance optimizer (cvxpy)
- Risk parity optimizer
- Black-Litterman model

**Phase 5: Risk Management** (Week 8)
- VaR/CVaR calculator
- Stress testing framework
- Correlation analyzer

**Phase 6: Web Interface** (Weeks 9-10)
- Streamlit research dashboard
- Strategy builder page
- Portfolio analytics page

---

## References

### Academic Literature

1. **Fama-French Three-Factor Model** (1993)
   - Value: HML (High Minus Low book-to-market)
   - Size: SMB (Small Minus Big market cap)
   - Market: Rm - Rf (Market return - Risk-free rate)

2. **Carhart Four-Factor Model** (1997)
   - Momentum: UMD (Up Minus Down 12-month return)

3. **Fama-French Five-Factor Model** (2015)
   - Profitability: RMW (Robust Minus Weak operating profitability)
   - Investment: CMA (Conservative Minus Aggressive investment)

4. **Low-Volatility Anomaly** (Baker, Bradley, Wurgler, 2011)
   - Low-volatility stocks outperform high-volatility stocks

### Industry Standards

- **MSCI Barra Factor Models**: Commercial factor model provider
- **Bloomberg PORT**: Portfolio optimization and risk analytics
- **FactSet**: Factor library and backtesting platform

### Internal Documentation

- **Phase 1 Completion Report**: `/tmp/phase1_completion_report.txt`
- **Database Schema**: `docs/DATABASE_SCHEMA_DIAGRAM.md`
- **Performance Tuning**: `docs/PERFORMANCE_TUNING_GUIDE.md`
- **Migration Runbook**: `docs/MIGRATION_RUNBOOK.md`

---

**Document Status**: Design Complete - Ready for Implementation
**Last Updated**: 2025-10-21
**Next Review**: After Phase 2 Implementation Complete
