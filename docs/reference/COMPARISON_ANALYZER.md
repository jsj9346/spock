# Comparison Analyzer Documentation

## Overview

The **ComparisonAnalyzer** module provides comprehensive year-over-year comparison and trend analysis capabilities for fundamental financial data. It calculates growth rates, CAGR (Compound Annual Growth Rate), and classifies trends to help identify improving, stable, or declining financial metrics.

## Features

- **Year-over-Year (YoY) Growth**: Calculate growth rates between consecutive years
- **CAGR Calculation**: Compute compound annual growth rates for multi-year periods
- **Trend Classification**: Automatically classify metrics as improving, stable, or declining
- **Multi-Metric Analysis**: Analyze multiple financial metrics simultaneously
- **Summary Generation**: Aggregate results with overall trend and strongest/weakest metrics
- **Robust Error Handling**: Gracefully handle missing data, negative values, and edge cases

## Installation

The ComparisonAnalyzer is part of the `modules/fundamentals` package:

```python
from modules.fundamentals.comparison_analyzer import ComparisonAnalyzer
```

## Quick Start

### Basic Usage

```python
from modules.fundamentals.comparison_analyzer import ComparisonAnalyzer
from decimal import Decimal

# Initialize analyzer
analyzer = ComparisonAnalyzer()

# Sample annual data (Samsung Electronics)
annual_data = [
    {'fiscal_year': 2024, 'revenue': Decimal('258700000000000'), 'net_income': Decimal('22700000000000')},
    {'fiscal_year': 2023, 'revenue': Decimal('222600000000000'), 'net_income': Decimal('14900000000000')},
    {'fiscal_year': 2022, 'revenue': Decimal('302200000000000'), 'net_income': Decimal('55300000000000')},
]

# Analyze
result = analyzer.analyze_annual_comparison(
    annual_data,
    metrics=['revenue', 'net_income']
)

# Access results
print(f"Revenue YoY 2024 vs 2023: {result['yoy']['revenue']['2024_vs_2023']:.2%}")
print(f"Net Income 2Y CAGR: {result['cagr']['net_income']['2y']:.2%}")
print(f"Overall Trend: {result['summary']['overall_trend']}")
```

## API Reference

### Class: ComparisonAnalyzer

#### Methods

##### `calculate_yoy_growth(current_value, previous_value)`

Calculate year-over-year growth rate.

**Formula**: `(current - previous) / abs(previous)`

**Parameters**:
- `current_value` (Decimal, optional): Current year value
- `previous_value` (Decimal, optional): Previous year value

**Returns**:
- `float`: Growth rate as decimal (0.15 = 15%), or `None` if calculation not possible

**Example**:
```python
yoy = analyzer.calculate_yoy_growth(Decimal('115'), Decimal('100'))
# Returns: 0.15 (15% growth)
```

**Edge Cases**:
- Returns `None` if either value is `None`
- Returns `None` if previous value is zero (division by zero)
- Uses absolute value in denominator for negative previous values
- Rounds result to 4 decimal places

---

##### `calculate_cagr(start_value, end_value, years)`

Calculate Compound Annual Growth Rate.

**Formula**: `(end_value / start_value)^(1/years) - 1`

**Parameters**:
- `start_value` (Decimal, optional): Starting year value
- `end_value` (Decimal, optional): Ending year value
- `years` (int): Number of years in the period

**Returns**:
- `float`: CAGR as decimal (0.05 = 5% annual growth), or `None` if calculation not possible

**Example**:
```python
cagr = analyzer.calculate_cagr(Decimal('100'), Decimal('121'), 2)
# Returns: 0.1 (10% annual growth)
```

**Edge Cases**:
- Returns `None` if either value is `None`
- Returns `None` if years <= 0
- Returns `None` if start_value <= 0 or end_value <= 0
- Rounds result to 4 decimal places

---

##### `classify_trend(growth_rate)`

Classify growth rate into trend categories.

**Parameters**:
- `growth_rate` (float, optional): Growth rate as decimal

**Returns**:
- `str`: One of 'improving', 'declining', 'stable', or 'unknown'

**Thresholds**:
- `improving`: growth > 5% (0.05)
- `declining`: growth < -5% (-0.05)
- `stable`: -5% ≤ growth ≤ 5%
- `unknown`: growth is `None`

**Example**:
```python
trend = analyzer.classify_trend(0.15)  # Returns: 'improving'
trend = analyzer.classify_trend(-0.10)  # Returns: 'declining'
trend = analyzer.classify_trend(0.03)  # Returns: 'stable'
```

---

##### `analyze_annual_comparison(annual_data, metrics=None)`

Perform comprehensive multi-year comparison analysis.

**Parameters**:
- `annual_data` (List[Dict]): List of annual records (will be auto-sorted by fiscal_year DESC)
  ```python
  [
      {'fiscal_year': 2024, 'revenue': Decimal('300T'), 'net_income': Decimal('20T'), ...},
      {'fiscal_year': 2023, 'revenue': Decimal('250T'), 'net_income': Decimal('15T'), ...},
      ...
  ]
  ```
- `metrics` (List[str], optional): Metrics to analyze (default: `DEFAULT_METRICS`)

**Returns**:
- `Dict`: Analysis result with the following structure:
  ```python
  {
      'yoy': {
          'revenue': {
              '2024_vs_2023': 0.162,
              '2023_vs_2022': -0.143,
              ...
          },
          'net_income': {...}
      },
      'cagr': {
          'revenue': {
              '3y': 0.002,
              '2y': 0.08
          },
          'net_income': {...}
      },
      'trends': {
          'revenue': 'improving',
          'net_income': 'stable'
      },
      'summary': {
          'overall_trend': 'improving',
          'strongest_metric': 'revenue',
          'weakest_metric': 'net_income',
          'years_analyzed': 5
      }
  }
  ```

**Raises**:
- `ValueError`: If annual_data is empty

**Default Metrics**:
```python
DEFAULT_METRICS = [
    'revenue',
    'operating_profit',
    'net_income',
    'ebitda',
    'total_assets',
    'total_equity'
]
```

**Example**:
```python
result = analyzer.analyze_annual_comparison(annual_data)

# Access YoY growth
revenue_yoy = result['yoy']['revenue']['2024_vs_2023']

# Access CAGR
revenue_cagr_3y = result['cagr']['revenue']['3y']

# Access trends
revenue_trend = result['trends']['revenue']

# Access summary
overall_trend = result['summary']['overall_trend']
strongest = result['summary']['strongest_metric']
```

---

##### `compare_with_sector(ticker_data, sector_avg, metrics)` 🚧

Compare ticker performance against sector average (placeholder for future implementation).

**Status**: Not yet implemented

**Returns**:
```python
{
    'status': 'not_implemented',
    'message': 'Sector comparison will be available in future release'
}
```

## Data Requirements

### Input Data Format

Annual fundamental data should be provided as a list of dictionaries with the following structure:

```python
annual_data = [
    {
        'fiscal_year': 2024,
        'ticker': '005930',
        'region': 'KR',
        'revenue': Decimal('258700000000000'),
        'operating_profit': Decimal('15700000000000'),
        'net_income': Decimal('22700000000000'),
        'ebitda': Decimal('45200000000000'),
        'total_assets': Decimal('448800000000000'),
        'total_equity': Decimal('308600000000000'),
        'roe': Decimal('7.4'),
        'roa': Decimal('5.1'),
        # ... other metrics
    },
    # ... more years
]
```

### Database Schema

When fetching from `ticker_fundamentals` table:

```sql
SELECT
    ticker,
    region,
    fiscal_year,
    date,
    revenue,
    operating_profit,
    net_income,
    ebitda,
    total_assets,
    total_equity,
    total_liabilities,
    roe,
    roa,
    debt_to_equity_ratio,
    current_ratio
FROM ticker_fundamentals
WHERE ticker = %s
    AND region = %s
    AND period_type = 'ANNUAL'
ORDER BY fiscal_year DESC
```

## Usage Examples

### Example 1: Analyze Single Ticker

```python
from modules.fundamentals.comparison_analyzer import ComparisonAnalyzer
from modules.db_manager_postgres import PostgresDatabaseManager
from decimal import Decimal

# Initialize
db = PostgresDatabaseManager()
analyzer = ComparisonAnalyzer()

# Fetch annual data
query = """
    SELECT fiscal_year, revenue, net_income, ebitda, roe
    FROM ticker_fundamentals
    WHERE ticker = %s AND region = %s AND period_type = 'ANNUAL'
    ORDER BY fiscal_year DESC
"""
results = db.execute_query(query, ('005930', 'KR'))

# Convert to dict format
annual_data = [
    {
        'fiscal_year': row[0],
        'revenue': row[1],
        'net_income': row[2],
        'ebitda': row[3],
        'roe': row[4]
    }
    for row in results
]

# Analyze
result = analyzer.analyze_annual_comparison(
    annual_data,
    metrics=['revenue', 'net_income', 'ebitda', 'roe']
)

# Display results
print(f"Overall Trend: {result['summary']['overall_trend']}")
print(f"Strongest Metric: {result['summary']['strongest_metric']}")

for metric in ['revenue', 'net_income']:
    print(f"\n{metric.upper()} Analysis:")
    for period, yoy in result['yoy'][metric].items():
        print(f"  {period}: {yoy:.2%}")
```

### Example 2: Compare Multiple Tickers

```python
def analyze_ticker(ticker, region='KR'):
    db = PostgresDatabaseManager()
    analyzer = ComparisonAnalyzer()

    # Fetch data
    annual_data = fetch_annual_fundamentals(db, ticker, region)

    # Analyze
    result = analyzer.analyze_annual_comparison(annual_data)

    db.close()
    return result

# Compare Samsung vs SK Hynix
samsung_result = analyze_ticker('005930', 'KR')
skhynix_result = analyze_ticker('000660', 'KR')

print(f"Samsung Overall Trend: {samsung_result['summary']['overall_trend']}")
print(f"SK Hynix Overall Trend: {skhynix_result['summary']['overall_trend']}")

# Compare revenue growth
samsung_revenue_yoy = list(samsung_result['yoy']['revenue'].values())[0]
skhynix_revenue_yoy = list(skhynix_result['yoy']['revenue'].values())[0]

print(f"\nRevenue YoY:")
print(f"  Samsung: {samsung_revenue_yoy:.2%}")
print(f"  SK Hynix: {skhynix_revenue_yoy:.2%}")
```

### Example 3: Identify Improving vs Declining Metrics

```python
result = analyzer.analyze_annual_comparison(annual_data)

# Group metrics by trend
improving = []
declining = []
stable = []

for metric, trend in result['trends'].items():
    if trend == 'improving':
        improving.append(metric)
    elif trend == 'declining':
        declining.append(metric)
    elif trend == 'stable':
        stable.append(metric)

print(f"Improving Metrics: {improving}")
print(f"Declining Metrics: {declining}")
print(f"Stable Metrics: {stable}")
```

## Interpretation Guide

### YoY Growth Interpretation

| YoY Growth | Interpretation |
|-----------|----------------|
| > 20% | Strong growth |
| 10% - 20% | Good growth |
| 5% - 10% | Moderate growth |
| -5% - 5% | Stable |
| -10% - -5% | Moderate decline |
| -20% - -10% | Concerning decline |
| < -20% | Severe decline |

### CAGR Interpretation

| CAGR | Interpretation |
|------|----------------|
| > 15% | Exceptional long-term growth |
| 10% - 15% | Strong long-term growth |
| 5% - 10% | Good long-term growth |
| 0% - 5% | Modest long-term growth |
| < 0% | Long-term decline |

### Trend Classification

- **Improving** (>5%): Positive momentum, growing metrics
- **Stable** (-5% to 5%): Consistent performance, no major changes
- **Declining** (<-5%): Negative momentum, shrinking metrics
- **Unknown**: Insufficient data or calculation not possible

## Performance Considerations

### Computation Complexity

- YoY Growth: O(1) per pair of years
- CAGR: O(1) per period
- Full Analysis: O(n × m) where n = number of years, m = number of metrics

### Typical Performance

For a ticker with 5 years of data and 10 metrics:
- YoY Calculations: ~40 operations
- CAGR Calculations: ~20 operations
- Total Time: <10ms

### Memory Usage

Minimal memory footprint:
- Input data: ~1KB per year per ticker
- Analysis result: ~5KB per ticker
- No caching required for single-use analysis

## Error Handling

### Common Edge Cases

1. **Missing Data**:
   ```python
   # Gracefully handles None values
   yoy = analyzer.calculate_yoy_growth(None, Decimal('100'))
   # Returns: None
   ```

2. **Division by Zero**:
   ```python
   # Handles zero previous value
   yoy = analyzer.calculate_yoy_growth(Decimal('100'), Decimal('0'))
   # Returns: None
   ```

3. **Negative Values**:
   ```python
   # Uses absolute value in denominator
   yoy = analyzer.calculate_yoy_growth(Decimal('100'), Decimal('-50'))
   # Returns: 3.0 (300% growth from negative)
   ```

4. **Insufficient Years**:
   ```python
   # Single year - no YoY calculated
   result = analyzer.analyze_annual_comparison([{'fiscal_year': 2024, 'revenue': Decimal('100')}])
   # result['yoy']['revenue'] will be empty {}
   ```

## Testing

Comprehensive test suite included in `tests/unit/test_comparison_analyzer.py`:

```bash
# Run all tests
pytest tests/unit/test_comparison_analyzer.py -v

# Run specific test class
pytest tests/unit/test_comparison_analyzer.py::TestYoYGrowth -v

# Run with coverage
pytest tests/unit/test_comparison_analyzer.py --cov=modules.fundamentals.comparison_analyzer
```

**Test Coverage**: 38 tests covering:
- YoY growth calculations (9 tests)
- CAGR calculations (12 tests)
- Trend classification (4 tests)
- Annual comparison analysis (9 tests)
- Sector comparison placeholder (1 test)
- Edge cases (3 tests)

## Integration with MCP Tools

The ComparisonAnalyzer integrates with MCP (Model Context Protocol) tools through:

### 1. Fundamentals Tool

```python
# Get fundamentals with comparison
result = use_mcp_tool(
    server_name="spock",
    tool_name="get_fundamentals",
    arguments={
        "ticker": "005930",
        "region": "KR",
        "include_comparison": True  # Enables ComparisonAnalyzer
    }
)
```

### 2. Ratios Tool

```python
# Get ratios with trend analysis
result = use_mcp_tool(
    server_name="spock",
    tool_name="get_ratios",
    arguments={
        "ticker": "005930",
        "region": "KR",
        "include_trends": True  # Enables trend classification
    }
)
```

## Future Enhancements

### Planned Features

1. **Sector Comparison** 🚧
   - Compare ticker metrics against sector/industry averages
   - Calculate relative strength scores
   - Identify outperformers and underperformers

2. **Peer Comparison**
   - Multi-ticker comparison tables
   - Ranking by growth metrics
   - Correlation analysis

3. **Statistical Significance**
   - T-tests for growth rate significance
   - Confidence intervals for CAGR
   - Outlier detection

4. **Visualization**
   - Growth trend charts
   - CAGR waterfall plots
   - Comparison heatmaps

5. **Advanced Metrics**
   - Growth volatility analysis
   - Momentum indicators
   - Regression analysis

## Troubleshooting

### Issue: YoY returns None

**Cause**: Missing data or zero previous value

**Solution**:
```python
# Check data availability
if current_value is None or previous_value is None:
    logger.warning("Missing data for YoY calculation")

# Check for zero values
if previous_value == 0:
    logger.warning("Previous value is zero, cannot calculate YoY")
```

### Issue: CAGR returns None for multi-year period

**Cause**: Negative values or insufficient data

**Solution**:
```python
# Ensure all values are positive
if start_value <= 0 or end_value <= 0:
    logger.warning("CAGR requires positive values")

# Check sufficient years
if years <= 0:
    logger.warning("CAGR requires years > 0")
```

### Issue: Trends showing 'unknown'

**Cause**: Insufficient YoY data or calculation failures

**Solution**:
```python
# Check YoY data availability
if not result['yoy'].get(metric):
    logger.warning(f"No YoY data for {metric}, trend will be unknown")

# Ensure at least 2 years of data
if len(annual_data) < 2:
    logger.warning("At least 2 years required for trend analysis")
```

## References

- **YoY Growth**: Standard year-over-year percentage change calculation
- **CAGR**: Compound Annual Growth Rate formula
- **Trend Analysis**: Technical analysis trend classification methods

## Support

For issues, questions, or feature requests:
1. Check the [examples](../examples/example_comparison_analyzer.py)
2. Review the [test suite](../tests/unit/test_comparison_analyzer.py)
3. See [MCP Integration](./MCP_INTEGRATION.md) for tool usage

---

**Last Updated**: 2025-11-27
**Version**: 1.0.0
**Status**: Production Ready ✅
