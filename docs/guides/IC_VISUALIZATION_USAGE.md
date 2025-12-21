# IC Visualization Usage Guide

**Date**: 2025-10-23
**Module**: `modules/visualization/ic_charts.py`
**CLI Script**: `scripts/visualize_ic_time_series.py`
**Integration**: `modules/analysis/performance_reporter.py`

---

## Overview

The IC (Information Coefficient) visualization system provides interactive and static charts for analyzing factor predictive power over time. The system offers three ways to generate visualizations:

1. **Standalone CLI Script** - Command-line tool for quick chart generation
2. **PerformanceReporter Integration** - Programmatic API for workflow integration
3. **Direct ICChartGenerator** - Low-level API for custom implementations

---

## Quick Start

### Option 1: Standalone CLI (Recommended for Manual Analysis)

```bash
# Generate all chart types for KR market
python3 scripts/visualize_ic_time_series.py \
  --region KR \
  --holding-period 21 \
  --output-dir reports/ic_charts/

# Generate specific charts with date filter
python3 scripts/visualize_ic_time_series.py \
  --start-date 2025-01-01 \
  --end-date 2025-09-30 \
  --charts timeseries,distribution \
  --formats html

# Generate for specific factors only
python3 scripts/visualize_ic_time_series.py \
  --factors PE_Ratio,PB_Ratio \
  --charts dashboard \
  --formats html,png
```

### Option 2: PerformanceReporter Integration (Recommended for Workflows)

```python
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.analysis.performance_reporter import PerformanceReporter
from modules.analysis.factor_analyzer import ICResult

# Initialize components
db = PostgresDatabaseManager()
reporter = PerformanceReporter(output_dir='reports/', theme='plotly_white')

# Load IC results from database
ic_results = load_ic_results_from_db(db, 'PE_Ratio', 'KR', 21)

# Generate interactive charts
files = reporter.ic_time_series_report_plotly(
    factor_name='PE_Ratio',
    ic_results=ic_results,
    region='KR',
    holding_period=21,
    export_formats=['html'],
    chart_types=['timeseries', 'distribution', 'dashboard']
)

print(f"Dashboard saved to: {files['dashboard_html']}")
```

---

## Chart Types

### 1. IC Time Series (`timeseries`)

**Description**: Interactive line chart showing IC evolution over time with rolling average and significance markers.

**Features**:
- Main IC line with data points
- 20-day rolling average (dashed line)
- Statistical significance markers (gold stars, p < 0.05)
- Zero reference line
- Range selector (1M, 3M, 6M, YTD, 1Y, All)
- Date range slider
- Interactive hover tooltips

**When to Use**:
- Monitor daily IC trends
- Identify regime changes (value premium vs. reversal)
- Spot statistically significant periods

**Example Output**:
```
IC Range: -0.3429 to +0.4867
Avg IC: +0.0509
Rolling Avg Smoothing: 20 days
```

---

### 2. Monthly IC Heatmap (`heatmap`)

**Description**: Calendar-style heatmap showing IC distribution by month and day.

**Features**:
- X-axis: Day of month (1-31)
- Y-axis: Year-Month
- Color scale: Red (negative IC) → Yellow (neutral) → Green (positive IC)
- Text annotations with IC values
- Missing data handled gracefully

**When to Use**:
- Identify seasonal patterns in factor performance
- Spot monthly trends (e.g., "February 2025 had consistently positive IC")
- Visualize long-term performance patterns

**Example Output**:
```
February 2025: Avg IC = +0.3131 (all days green)
July 2025: Avg IC = -0.2034 (all days red)
```

---

### 3. IC Distribution (`distribution`)

**Description**: Overlaid histograms showing IC distribution for each factor.

**Features**:
- 30 bins for granularity
- Color-coded by factor
- Mean IC line (dashed, factor-colored)
- Zero reference line
- Transparency for overlap visibility
- Statistical summary annotations

**When to Use**:
- Compare IC distributions across factors
- Assess IC consistency (narrow vs. wide distribution)
- Identify outlier IC values

**Example Output**:
```
PE_Ratio Distribution: Mean = +0.0509, Std = 0.1944
PB_Ratio Distribution: Mean = +0.0309, Std = 0.2030
```

---

### 4. Rolling IC Average (`rolling`)

**Description**: Rolling average chart with threshold lines for regime identification.

**Features**:
- Smoothed rolling average (20-day window)
- Threshold lines at ±0.05
- Zero reference line
- Shaded fill to zero
- Range selector

**When to Use**:
- Identify sustained regime changes
- Filter out daily noise
- Set factor exposure rules (e.g., "increase exposure when rolling IC > 0.05")

**Example Output**:
```
Strong Regime (IC > 0.05): 45% of time
Weak Regime (IC < -0.05): 28% of time
Neutral: 27% of time
```

---

### 5. Multi-Factor Dashboard (`dashboard`)

**Description**: 2x2 subplot grid combining all visualizations.

**Features**:
- Top-left: IC time series with rolling average
- Top-right: IC distribution
- Bottom-left: Rolling IC average
- Bottom-right: Monthly heatmap (first factor)
- Unified color scheme
- Single export file

**When to Use**:
- Comprehensive factor analysis in one view
- Executive summaries and presentations
- Quick comparison of multiple factors

**Example Output**: Single HTML file with all 4 charts (~4.4 MB).

---

## CLI Reference

### Full Command Syntax

```bash
python3 scripts/visualize_ic_time_series.py \
  [--region REGION] \
  [--holding-period DAYS] \
  [--start-date YYYY-MM-DD] \
  [--end-date YYYY-MM-DD] \
  [--factors FACTOR1,FACTOR2,...] \
  [--charts CHART1,CHART2,...] \
  [--rolling-window DAYS] \
  [--output-dir PATH] \
  [--formats FORMAT1,FORMAT2,...] \
  [--theme THEME]
```

### Arguments

**Database Filters**:
- `--region` - Market region (default: `KR`)
- `--holding-period` - Forward return period in days (default: `21`)
- `--start-date` - Start date filter (format: `YYYY-MM-DD`)
- `--end-date` - End date filter (format: `YYYY-MM-DD`)
- `--factors` - Comma-separated factor names (default: all factors)

**Chart Options**:
- `--charts` - Chart types: `timeseries`, `heatmap`, `distribution`, `rolling`, `dashboard`, or `all` (default: `all`)
- `--rolling-window` - Rolling window size (default: `20`)

**Export Options**:
- `--output-dir` - Output directory (default: `reports/ic_charts/`)
- `--formats` - Export formats: `html`, `png` (default: `html`)
- `--theme` - Plotly theme (default: `plotly_white`)

### Available Themes

- `plotly_white` (default) - Clean white background
- `plotly_dark` - Dark theme for presentations
- `ggplot2` - ggplot2-inspired theme
- `seaborn` - Seaborn-inspired theme
- `simple_white` - Minimal white theme
- `none` - No theme styling

---

## PerformanceReporter API Reference

### Method Signature

```python
def ic_time_series_report_plotly(
    self,
    factor_name: str,
    ic_results: List[ICResult],
    region: str = 'KR',
    holding_period: int = 21,
    export_formats: List[str] = ['html'],
    chart_types: List[str] = ['timeseries', 'distribution']
) -> Dict[str, str]
```

### Parameters

- **factor_name** (`str`): Name of factor (e.g., `'PE_Ratio'`)
- **ic_results** (`List[ICResult]`): List of ICResult objects from FactorAnalyzer
- **region** (`str`, optional): Market region for chart title (default: `'KR'`)
- **holding_period** (`int`, optional): Forward return period for chart title (default: `21`)
- **export_formats** (`List[str]`, optional): Export formats - `['html']`, `['png']`, or `['html', 'png']` (default: `['html']`)
- **chart_types** (`List[str]`, optional): Chart types to generate - `['timeseries', 'distribution', 'rolling', 'dashboard']` (default: `['timeseries', 'distribution']`)

### Returns

`Dict[str, str]`: Dictionary mapping chart type to file path.

**Example Return Value**:
```python
{
    'timeseries_html': 'reports/PE_Ratio_ic_timeseries_interactive_20251023_133335.html',
    'distribution_html': 'reports/PE_Ratio_ic_distribution_interactive_20251023_133335.html',
    'rolling_html': 'reports/PE_Ratio_ic_rolling_avg_interactive_20251023_133335.html',
    'dashboard_html': 'reports/PE_Ratio_ic_dashboard_interactive_20251023_133335.html'
}
```

---

## Advanced Usage Examples

### Example 1: Automated Daily IC Report

```python
#!/usr/bin/env python3
"""Daily IC Report Generator"""

import os
from datetime import date, timedelta
from modules.db_manager_postgres import PostgresDatabaseManager
from modules.analysis.performance_reporter import PerformanceReporter
from modules.analysis.factor_analyzer import FactorAnalyzer

# Configuration
FACTORS = ['PE_Ratio', 'PB_Ratio', '12M_Momentum']
REGION = 'KR'
HOLDING_PERIOD = 21
OUTPUT_DIR = 'reports/daily_ic/'

# Initialize
db = PostgresDatabaseManager()
reporter = PerformanceReporter(output_dir=OUTPUT_DIR)
analyzer = FactorAnalyzer(db)

# Load last 3 months of IC data
end_date = date.today()
start_date = end_date - timedelta(days=90)

for factor_name in FACTORS:
    print(f"\nGenerating report for {factor_name}...")

    # Calculate IC (or load from cache)
    ic_results = analyzer.calculate_ic_time_series(
        factor_name=factor_name,
        region=REGION,
        holding_period=HOLDING_PERIOD,
        start_date=start_date,
        end_date=end_date
    )

    # Generate interactive dashboard
    files = reporter.ic_time_series_report_plotly(
        factor_name=factor_name,
        ic_results=ic_results,
        region=REGION,
        holding_period=HOLDING_PERIOD,
        export_formats=['html'],
        chart_types=['dashboard']
    )

    print(f"  ✓ Dashboard: {files['dashboard_html']}")
```

---

### Example 2: Compare Multiple Factors Side-by-Side

```python
#!/usr/bin/env python3
"""Multi-Factor IC Comparison"""

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.visualization.ic_charts import ICChartGenerator
import pandas as pd

# Load IC data for multiple factors
db = PostgresDatabaseManager()

query = """
    SELECT date, factor_name, ic, p_value, num_stocks, is_significant
    FROM ic_time_series
    WHERE region = 'KR'
      AND holding_period = 21
      AND factor_name IN ('PE_Ratio', 'PB_Ratio', '12M_Momentum')
    ORDER BY date, factor_name
"""

results = db.execute_query(query)
ic_df = pd.DataFrame(results)
ic_df['date'] = pd.to_datetime(ic_df['date'])

# Generate multi-factor dashboard (all factors in one chart)
generator = ICChartGenerator(theme='plotly_white')
fig = generator.create_multi_factor_dashboard(ic_df, rolling_window=20)
fig.write_html('reports/multi_factor_comparison.html')

print("✓ Multi-factor comparison saved: reports/multi_factor_comparison.html")
```

---

### Example 3: Export to PNG for PowerPoint

```python
#!/usr/bin/env python3
"""Export IC Charts to PNG for Presentations"""

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.analysis.performance_reporter import PerformanceReporter
from modules.analysis.factor_analyzer import ICResult

# Load IC data
db = PostgresDatabaseManager()
ic_results = load_ic_results_from_db(db, 'PE_Ratio', 'KR', 21)

# Generate PNG charts for PowerPoint
reporter = PerformanceReporter(output_dir='reports/presentation/', theme='plotly_white')

files = reporter.ic_time_series_report_plotly(
    factor_name='PE_Ratio',
    ic_results=ic_results,
    export_formats=['png'],  # PNG only
    chart_types=['dashboard']
)

print(f"PNG chart for PowerPoint: {files['dashboard_png']}")
```

**Note**: PNG export requires `kaleido` package:
```bash
pip install kaleido
```

---

## Output File Structure

### CLI Script Output

```
reports/ic_charts/
├── ic_timeseries_KR_20251023_132939.html (4.4 MB)
├── ic_heatmap_PB_Ratio_KR_20251023_132939.html (4.4 MB)
├── ic_heatmap_PE_Ratio_KR_20251023_132939.html (4.4 MB)
├── ic_distribution_KR_20251023_132939.html (4.4 MB)
├── ic_rolling_avg_KR_20251023_132939.html (4.4 MB)
└── ic_dashboard_KR_20251023_132939.html (4.4 MB)
```

### PerformanceReporter Output

```
reports/
├── PE_Ratio_ic_timeseries_interactive_20251023_133335.html
├── PE_Ratio_ic_distribution_interactive_20251023_133335.html
├── PE_Ratio_ic_rolling_avg_interactive_20251023_133335.html
└── PE_Ratio_ic_dashboard_interactive_20251023_133335.html
```

---

## Troubleshooting

### Issue 1: "Plotly not available" warning

**Cause**: `plotly` package not installed

**Solution**:
```bash
pip install plotly==5.17.0
```

---

### Issue 2: PNG export fails with "kaleido package required"

**Cause**: `kaleido` package not installed (needed for static image export)

**Solution**:
```bash
pip install kaleido
```

**Alternative**: Use HTML export only:
```python
export_formats=['html']  # Skip PNG export
```

---

### Issue 3: Charts are empty or no data

**Cause**: No IC data in database for specified filters

**Solution**:
1. Verify IC data exists:
```sql
SELECT COUNT(*) FROM ic_time_series WHERE region = 'KR' AND holding_period = 21;
```

2. Run IC calculation first:
```bash
python3 scripts/calculate_ic_time_series.py --region KR --holding-period 21
```

---

### Issue 4: File size too large (>10 MB)

**Cause**: Plotly HTML files include full JavaScript libraries

**Solutions**:
1. Use PNG export for documents:
```python
export_formats=['png']
```

2. Use CDN mode (smaller files):
```python
fig.write_html(filepath, include_plotlyjs='cdn')
```

3. Use gzip compression:
```bash
gzip -9 reports/ic_charts/*.html
```

---

## Performance Considerations

### File Sizes

- **HTML (interactive)**: ~4.4 MB per chart (includes Plotly.js library)
- **PNG (static)**: ~100-500 KB per chart (requires kaleido)
- **Dashboard**: ~4.4 MB (combines 4 charts in one file)

### Generation Speed

- **Single chart**: <1 second
- **All 6 charts**: ~2-3 seconds
- **Multi-factor dashboard**: ~1-2 seconds per factor

### Memory Usage

- **Peak memory**: ~200-300 MB (during chart generation)
- **Database query**: <1 second for 310 IC records

---

## Best Practices

### 1. Choose Appropriate Chart Types

- **Daily monitoring**: Use `timeseries` only
- **Monthly reports**: Use `dashboard` for comprehensive view
- **Presentations**: Use `distribution` and `rolling` for clarity
- **Research deep-dive**: Use `all` chart types

### 2. Optimize Export Formats

- **Interactive exploration**: Use `html` format
- **Documents/reports**: Use `png` format (requires kaleido)
- **Web embedding**: Use `html` with CDN mode

### 3. Date Range Selection

- **Short-term (1-3 months)**: Daily noise visible, use `timeseries`
- **Medium-term (3-12 months)**: Regime changes visible, use `rolling`
- **Long-term (1+ years)**: Seasonal patterns visible, use `heatmap`

### 4. Factor Comparison

- **Single factor**: Use standalone CLI for quick analysis
- **Multiple factors**: Use PerformanceReporter API in loop
- **All factors**: Load all IC data once, use ICChartGenerator directly

---

## Integration with Streamlit Dashboard

### Future Integration Plan

The IC visualization system is designed for easy integration into Streamlit dashboards:

```python
import streamlit as st
from modules.visualization.ic_charts import ICChartGenerator
import pandas as pd

# Load IC data
ic_df = load_ic_data_from_db(...)

# Generate chart
generator = ICChartGenerator()
fig = generator.plot_ic_time_series(ic_df)

# Display in Streamlit
st.plotly_chart(fig, use_container_width=True)
```

**Status**: Planned for Week 8-9 (Web Interface implementation phase)

---

## References

- **Main Module**: `modules/visualization/ic_charts.py`
- **CLI Script**: `scripts/visualize_ic_time_series.py`
- **Integration**: `modules/analysis/performance_reporter.py`
- **Test Script**: `tests/test_performance_reporter_plotly.py`
- **IC Analysis Report**: `analysis/IC_TIME_SERIES_ANALYSIS.md`

---

**Last Updated**: 2025-10-23
**Author**: Spock Quant Platform
