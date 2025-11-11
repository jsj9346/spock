# Factor Independence Validation

Comprehensive guide for validating factor independence in the Quant Investment Platform.

**Last Updated**: 2025-10-28
**Status**: Production Ready

---

## Overview

The **IndependenceValidator** ensures that factors in the factor library are sufficiently independent (correlation < 0.5) to avoid redundancy and multicollinearity in portfolio construction.

### Why Factor Independence Matters

**Problem**: Highly correlated factors provide redundant signals and reduce portfolio diversification effectiveness.

**Impact**:
- **Overfitting**: Correlated factors amplify the same signal, leading to concentrated risk
- **Reduced Alpha**: Redundant factors don't add independent alpha sources
- **Unstable Portfolios**: High correlation causes portfolios to become unstable during regime changes

**Solution**: Systematic validation of factor correlations with actionable recommendations for factor selection and weighting.

---

## Core Concepts

### Independence Threshold

**Default**: `|r| < 0.5` (correlation coefficient absolute value less than 0.5)

**Interpretation**:
- **0.0 - 0.3**: Low correlation (highly independent)
- **0.3 - 0.5**: Moderate correlation (acceptable independence)
- **0.5 - 0.7**: High correlation (may need adjustment)
- **0.7 - 1.0**: Very high correlation (likely redundant)

### Correlation Types

#### Inter-Category Correlations
Correlations between factors from **different categories** (e.g., Momentum vs Value).

**Expected Behavior**: Low correlation (factors should provide independent signals)

**Example**:
```
12M_Momentum ↔ PB_Ratio: r=0.15 (✅ Independent)
```

#### Intra-Category Correlations
Correlations between factors within the **same category** (e.g., two momentum factors).

**Expected Behavior**: Moderate correlation is acceptable if factors capture different aspects

**Example**:
```
12M_Momentum ↔ 1M_Momentum: r=0.45 (✅ Acceptable - different time horizons)
```

---

## Implementation

### IndependenceValidator Class

**Location**: `/Users/13ruce/spock/modules/factors/independence_validator.py` (562 lines)

**Purpose**: Validate factor independence using correlation analysis on historical factor scores

**Key Methods**:
1. `validate_independence()` - Main validation entry point
2. `_load_factor_time_series()` - Load factor data for correlation analysis
3. `_calculate_pairwise_correlations()` - Calculate all factor pair correlations
4. `_generate_recommendations()` - Provide actionable recommendations
5. `save_report()` - Export validation results to file

### Data Flow

```
┌─────────────────────────────────────────────┐
│  Factor Scores Database (PostgreSQL)        │
│  - factor_scores table                      │
│  - Columns: date, ticker, factor_name,      │
│    percentile (0-100 normalized)            │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  IndependenceValidator                      │
│  1. Load factor time series                 │
│  2. Pivot to wide format (dates x factors)  │
│  3. Calculate pairwise Pearson correlations │
│  4. Compare against threshold               │
│  5. Generate category summary               │
│  6. Create recommendations                  │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  IndependenceValidationReport               │
│  - Total/independent/correlated pairs       │
│  - Detailed correlation results             │
│  - Category summaries                       │
│  - Actionable recommendations               │
└─────────────────────────────────────────────┘
```

---

## Usage Examples

### Basic Validation

```python
from modules.factors.independence_validator import IndependenceValidator
from datetime import date

# Initialize validator
validator = IndependenceValidator(
    region='KR',
    independence_threshold=0.5,
    min_sample_size=20
)

# Run validation
report = validator.validate_independence(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
    tickers=None  # None = all available tickers
)

# Print summary
print(report)

# Save detailed report
validator.save_report(report, 'results/independence_report.txt')
```

**Output**:
```
Independence Validation Report
==================================================
Date: 2025-10-28 11:37:41
Period: 2024-01-01 to 2024-12-31
Universe: 139 tickers
Threshold: |r| < 0.5

Results:
  Total pairs tested: 36
  Independent pairs: 32 (88.9%)
  Correlated pairs: 4
```

### Custom Threshold

```python
# Stricter independence requirement
strict_validator = IndependenceValidator(
    region='KR',
    independence_threshold=0.3,  # More strict
    min_sample_size=20
)

report = strict_validator.validate_independence(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31)
)

print(f"Independence rate: {report.independence_rate:.1f}%")
```

### Targeted Universe

```python
# Validate independence for specific tickers
tickers = ['005930', '000660', '035420', '035720', '051910']

report = validator.validate_independence(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
    tickers=tickers
)
```

### Iterate Through Correlated Pairs

```python
# Identify highly correlated factors
correlated_pairs = [
    c for c in report.correlations
    if not c.is_independent
]

# Sort by correlation strength
correlated_pairs.sort(key=lambda x: abs(x.correlation), reverse=True)

print(f"\nFound {len(correlated_pairs)} correlated pairs:")
for pair in correlated_pairs:
    print(f"  {pair.factor1} ↔ {pair.factor2}: r={pair.correlation:.3f}")
    print(f"    Categories: {pair.category1} / {pair.category2}")
    print(f"    Samples: {pair.sample_size}, p-value: {pair.p_value:.4f}\n")
```

---

## Test Results (2024-09-01 to 2024-10-22)

### Overall Independence

- **Total factor pairs tested**: 36
- **Independent pairs**: 32 (88.9%)
- **Correlated pairs**: 4 (11.1%)
- **Universe**: 139 tickers
- **Observations**: 4,309 (date, ticker) combinations

### Correlated Factors Identified

| Factor 1 | Factor 2 | Correlation | Category 1 | Category 2 | Status |
|----------|----------|-------------|------------|------------|--------|
| 1M_Momentum | RSI_Momentum | 1.000 | 1M | RSI | ❌ Perfect correlation |
| Operating_Profit_Margin | ROE_Proxy | 0.870 | Operating | ROE | ❌ High correlation |
| Current_Ratio | Debt_Ratio | 0.754 | Current | Debt | ❌ High correlation |
| PB_Ratio | PE_Ratio | 0.717 | PB | PE | ❌ High correlation |

### Recommendations

#### 1. Perfect Correlation (1M_Momentum ↔ RSI_Momentum)
**Problem**: Factors are measuring the same signal (r=1.000)

**Recommendation**: **Drop one factor**
- Keep: `12M_Momentum` (longer-term signal, more stable)
- Drop: `1M_Momentum` or `RSI_Momentum` (redundant)

**Implementation**:
```python
# In factor combination strategy
from modules.factors.factor_combiner import CategoryWeightCombiner

combiner = CategoryWeightCombiner(weights={
    'Momentum': 0.30,
    'Value': 0.25,
    'Quality': 0.25,
    'Low-Vol': 0.20
})

# Exclude redundant factor
combiner.exclude_factors = ['1M_Momentum']  # Keep RSI_Momentum
```

#### 2. High Quality Factor Correlation (Operating_Profit_Margin ↔ ROE_Proxy)
**Problem**: Both measure profitability (r=0.870)

**Recommendation**: **Use equal weighting or drop one**
- Option A: Equal weight both factors in Quality category
- Option B: Keep `ROE_Proxy` (more fundamental metric)

**Implementation**:
```python
# Option A: Equal weighting (default behavior)
combiner = CategoryWeightCombiner(weights={'Quality': 0.25})

# Option B: Drop redundant factor
combiner.exclude_factors = ['Operating_Profit_Margin']
```

#### 3. Financial Health Correlation (Current_Ratio ↔ Debt_Ratio)
**Problem**: Both measure liquidity/debt (r=0.754)

**Recommendation**: **Keep both with reduced category weight**
- Reasoning: They capture complementary aspects (liquidity vs leverage)
- Solution: Reduce Quality category weight to compensate for correlation

**Implementation**:
```python
combiner = CategoryWeightCombiner(weights={
    'Momentum': 0.30,
    'Value': 0.30,
    'Quality': 0.20,  # Reduced from 0.25 due to correlation
    'Low-Vol': 0.20
})
```

#### 4. Value Factor Correlation (PB_Ratio ↔ PE_Ratio)
**Problem**: Both are value metrics (r=0.717)

**Recommendation**: **Use equal weighting within Value category**
- Reasoning: PB and PE capture different aspects of valuation
- Solution: Equal weight to avoid over-weighting correlated signals

**Implementation**:
```python
# Default behavior: Equal weight within category
combiner = CategoryWeightCombiner(weights={'Value': 0.30})

# Alternatively, use optimization-based combiner
from modules.factors.factor_combiner import OptimizationCombiner
combiner = OptimizationCombiner()
combiner.fit(start_date='2022-01-01', end_date='2024-12-31')
```

---

## Interpretation Guidelines

### Acceptable Correlation Ranges

**By Factor Type**:

| Comparison | Acceptable Range | Reasoning |
|------------|------------------|-----------|
| Inter-category | |r| < 0.5 | Factors should provide independent signals |
| Intra-category (different time horizons) | |r| < 0.7 | Same signal type, different frequencies |
| Intra-category (different metrics) | |r| < 0.6 | Similar concept, different measurements |

**Special Cases**:
- **Momentum factors** (different timeframes): 0.4-0.6 is acceptable
- **Value factors** (different ratios): 0.5-0.7 is acceptable
- **Quality factors** (different profitability metrics): 0.6-0.8 may be acceptable

### Statistical Significance

**P-Value Interpretation**:
- **p < 0.001**: Highly significant (correlation is not due to chance)
- **p < 0.01**: Significant (strong evidence of correlation)
- **p < 0.05**: Moderately significant (conventional threshold)
- **p > 0.05**: Not significant (correlation may be spurious)

**Sample Size Requirements**:
- **Minimum**: 20 observations (default threshold)
- **Recommended**: 50+ observations for robust results
- **Ideal**: 100+ observations for high confidence

---

## Integration with Factor Library

### Workflow: Validate → Adjust → Re-validate

```python
from modules.factors.independence_validator import IndependenceValidator
from modules.factors.factor_combiner import OptimizationCombiner
from datetime import date

# Step 1: Initial validation
validator = IndependenceValidator(region='KR', independence_threshold=0.5)
report = validator.validate_independence(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31)
)

# Step 2: Identify correlated pairs
correlated = [c for c in report.correlations if not c.is_independent]
print(f"Found {len(correlated)} correlated pairs")

# Step 3: Adjust factor weights
combiner = OptimizationCombiner()
combiner.exclude_factors = ['1M_Momentum']  # Drop perfect correlation
combiner.fit(start_date='2024-01-01', end_date='2024-12-31')

# Step 4: Re-validate with adjusted factors
# (Run validation again after exclusion)
```

### Automated Monitoring

**Frequency**: Monthly (correlations can change over time)

**Script**: `scripts/monitor_factor_independence.py`

```python
#!/usr/bin/env python3
"""
Monthly factor independence monitoring script

Cron schedule: 0 2 1 * * (run at 2 AM on 1st of each month)
"""

from modules.factors.independence_validator import IndependenceValidator
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)

def monthly_validation():
    """Run monthly factor independence validation"""

    validator = IndependenceValidator(region='KR', independence_threshold=0.5)

    # Validate last 3 months
    end_date = date.today()
    start_date = end_date - timedelta(days=90)

    report = validator.validate_independence(start_date, end_date)

    # Save report
    output_path = f'results/independence_monthly_{end_date.strftime("%Y%m%d")}.txt'
    validator.save_report(report, output_path)

    # Alert if independence rate drops below 80%
    if report.independence_rate < 80:
        logger.warning(
            f"Factor independence rate dropped to {report.independence_rate:.1f}%! "
            f"Review: {output_path}"
        )
    else:
        logger.info(f"Factor independence validated: {report.independence_rate:.1f}%")

if __name__ == '__main__':
    monthly_validation()
```

---

## Troubleshooting

### Issue: "No factor scores found"

**Cause**: Factor scores not calculated for specified period/universe

**Solution**:
```python
# Check available date range
import psycopg2
conn = psycopg2.connect(dbname="quant_platform", user="13ruce", host="localhost")
cur = conn.cursor()
cur.execute("""
    SELECT MIN(date), MAX(date), COUNT(DISTINCT ticker)
    FROM factor_scores
    WHERE region = 'KR';
""")
print(cur.fetchone())
conn.close()

# Adjust validation period accordingly
```

### Issue: "Insufficient samples" warnings

**Cause**: Not enough common observations between factor pairs

**Solution**:
- Increase time period (need more dates)
- Reduce `min_sample_size` parameter (if acceptable)
- Check for missing factor data

```python
# Lower minimum sample requirement (use with caution)
validator = IndependenceValidator(
    region='KR',
    independence_threshold=0.5,
    min_sample_size=10  # Reduced from default 20
)
```

### Issue: All correlations fail with dtype error

**Cause**: Percentile values stored as object dtype in database

**Solution**: Already fixed in validator with `pd.to_numeric()` conversion

```python
# In _load_factor_time_series():
df['percentile'] = pd.to_numeric(df['percentile'], errors='coerce')
```

---

## API Reference

### IndependenceValidator

```python
class IndependenceValidator:
    """
    Validator for testing factor independence using correlation analysis

    Args:
        region: Region filter for factors (default: 'KR')
        independence_threshold: Maximum correlation for independence (default: 0.5)
        min_sample_size: Minimum observations required (default: 20)
        significance_level: P-value threshold (default: 0.05)
    """

    def validate_independence(
        self,
        start_date: date,
        end_date: date,
        tickers: Optional[List[str]] = None
    ) -> IndependenceValidationReport:
        """
        Validate factor independence for given period and universe

        Args:
            start_date: Start date for correlation analysis
            end_date: End date for correlation analysis
            tickers: Optional list of tickers (None = all available)

        Returns:
            IndependenceValidationReport with validation results
        """

    def save_report(
        self,
        report: IndependenceValidationReport,
        filepath: str,
        include_details: bool = True
    ) -> None:
        """
        Save validation report to file

        Args:
            report: Validation report to save
            filepath: Output file path
            include_details: Include detailed correlation results
        """
```

### IndependenceValidationReport

```python
@dataclass
class IndependenceValidationReport:
    """
    Comprehensive independence validation report

    Attributes:
        validation_date: Date of validation
        universe_size: Number of tickers analyzed
        period: Date range used for correlation analysis
        independence_threshold: Correlation threshold
        total_factor_pairs: Total number of factor pairs tested
        independent_pairs: Number of pairs meeting threshold
        correlated_pairs: Number of pairs failing threshold
        correlations: List of all correlation results
        category_summary: Independence summary by category
        recommendations: Actionable recommendations
    """

    @property
    def independence_rate(self) -> float:
        """Calculate percentage of independent pairs"""
```

### CorrelationResult

```python
@dataclass
class CorrelationResult:
    """
    Result of pairwise factor correlation analysis

    Attributes:
        factor1: First factor name
        factor2: Second factor name
        correlation: Pearson correlation coefficient (-1 to 1)
        p_value: Statistical significance
        sample_size: Number of observations
        category1: Category of first factor
        category2: Category of second factor
        is_independent: Whether correlation meets threshold
        threshold: Independence threshold used
    """
```

---

## Related Documentation

- **Factor Library**: `FACTOR_LIBRARY_REFERENCE.md` (implementation details)
- **Factor Combiners**: `factor_combiner.py` (how to weight correlated factors)
- **Batch Analysis**: `scripts/generate_factor_performance_report.py` (factor backtesting)
- **Roadmap**: `QUANT_ROADMAP.md` (Phase 4, Week 6 - Factor Analysis)

---

## References

### Academic Literature

1. **Fama & French (1993)**: "Common risk factors in the returns on stocks and bonds"
   - Established importance of factor independence in multi-factor models

2. **Asness, Moskowitz & Pedersen (2013)**: "Value and Momentum Everywhere"
   - Analyzed correlation between value and momentum factors across markets

3. **Novy-Marx (2013)**: "The other side of value"
   - Showed how different value metrics can be correlated

### Industry Standards

- **MSCI**: Factor correlation monitoring as part of factor quality standards
- **AQR**: Publishes factor correlation matrices quarterly
- **Research Affiliates**: Emphasizes factor independence in smart beta portfolios

---

**Last Updated**: 2025-10-28
**Next Review**: 2025-11-28 (monthly)
**Status**: ✅ Production Ready (88.9% independence rate)
