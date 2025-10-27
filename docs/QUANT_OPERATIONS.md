# Operations Guide - Quant Investment Platform

Monitoring, logging, and operational procedures for production environment.

**Last Updated**: 2025-10-26

---

## Overview

Operational infrastructure reused from Spock with quant-specific enhancements.

### Monitoring Stack
- **Prometheus**: Metrics collection and storage
- **Grafana**: Visualization and alerting
- **Loguru**: Structured application logging
- **psutil**: System resource monitoring

---

## Logging

### Log Files

**Location**: `logs/YYYYMMDD_quant_platform.log`
**Retention**: 30 days (automatic cleanup)
**Rotation**: Daily at midnight

### Log Levels

```python
# Configuration in config/logging.yaml
levels:
  DEBUG: Development only
  INFO: Normal operations
  WARNING: Potential issues
  ERROR: Recoverable errors
  CRITICAL: System failures
```

### Log Format

```
2025-10-26 14:30:45.123 | INFO     | modules.backtest.backtest_engine:run:145 - Backtest started for strategy=momentum_value
2025-10-26 14:31:15.456 | INFO     | modules.backtest.backtest_engine:run:278 - Backtest completed: sharpe=1.82, return=45.2%
```

### Example Logging Usage

```python
from loguru import logger

# Info logging
logger.info("Backtest started for strategy={}", strategy_name)

# Warning logging
logger.warning("Factor correlation high: {:.2f}", correlation)

# Error logging with context
try:
    results = run_backtest()
except Exception as e:
    logger.error("Backtest failed: {}", e, exc_info=True)

# Performance logging
with logger.contextualize(strategy=strategy_name):
    logger.info("Performance: sharpe={:.2f}", sharpe_ratio)
```

---

## Performance Metrics (Prometheus)

### Metrics Categories

#### 1. Backtest Metrics

```python
# Backtest execution time
quant_backtest_duration_seconds{strategy="momentum_value", engine="vectorbt"} 0.6

# Backtest success rate
quant_backtest_success_rate{strategy="momentum_value"} 0.98

# Results cache hit rate
quant_backtest_cache_hit_rate 0.75
```

#### 2. Optimization Metrics

```python
# Optimization convergence time
quant_optimization_duration_seconds{method="mean_variance"} 45.2

# Constraint violations
quant_optimization_constraint_violations_total{method="risk_parity"} 0
```

#### 3. Factor Metrics

```python
# Factor calculation time
quant_factor_calculation_duration_seconds{factor="momentum"} 2.5

# Factor data availability
quant_factor_data_availability{factor="value", region="KR"} 0.995
```

#### 4. Database Metrics

```python
# Query execution time
quant_db_query_duration_seconds{query_type="ohlcv_fetch"} 0.15

# Connection pool usage
quant_db_connection_pool_active 5
quant_db_connection_pool_idle 15

# Disk usage
quant_db_disk_usage_bytes 3.5e9  # 3.5 GB
```

#### 5. API Metrics

```python
# Request rate
quant_api_requests_total{endpoint="/backtest", method="POST"} 1234

# Request latency
quant_api_request_duration_seconds{endpoint="/backtest"} 0.18

# Error rate
quant_api_errors_total{endpoint="/backtest", status="500"} 2
```

### Metrics Exporter

```python
# modules/monitoring/metrics_exporter.py
from prometheus_client import Counter, Histogram, Gauge

# Define metrics
backtest_duration = Histogram(
    'quant_backtest_duration_seconds',
    'Backtest execution time',
    ['strategy', 'engine']
)

# Export metrics
with backtest_duration.labels(
    strategy='momentum_value',
    engine='vectorbt'
).time():
    results = run_backtest()
```

---

## Alerting (Grafana + Alertmanager)

### Alert Levels

#### Critical Alerts (Immediate Action)
- Database connection lost
- API failures (>5% error rate)
- Optimization errors (constraint violations)
- Backtest engine failures

```yaml
# Alert configuration
- alert: DatabaseConnectionLost
  expr: quant_db_connection_pool_active == 0
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "Database connection lost"
    description: "No active database connections for 1 minute"
```

#### Warning Alerts (Review Required)
- Slow backtest (>60s)
- Factor calculation failures
- High memory usage (>80%)
- Cache miss rate >50%

```yaml
- alert: BacktestTooSlow
  expr: quant_backtest_duration_seconds{engine="custom"} > 60
  for: 5m
  labels:
    severity: warning
  annotations:
    summary: "Backtest execution too slow"
    description: "Custom engine backtest taking >60 seconds"
```

#### Info Alerts (Awareness)
- Daily factor updates completed
- Weekly performance reports generated
- Monthly rebalancing executed

```yaml
- alert: DailyFactorUpdate
  expr: quant_factor_data_availability > 0.99
  labels:
    severity: info
  annotations:
    summary: "Daily factor update completed"
    description: "Factor data availability: {{ $value | humanizePercentage }}"
```

---

## Monitoring Dashboards

### 1. Backtest Dashboard

**Panels**:
- Backtest execution time (custom vs vectorbt)
- Success rate by strategy
- Cache hit rate
- Parameter optimization duration

**Access**: `http://localhost:3000/d/backtest`

### 2. Database Dashboard

**Panels**:
- Query latency (p50, p95, p99)
- Connection pool usage
- Disk usage trends
- Compression ratio

**Access**: `http://localhost:3000/d/database`

### 3. API Dashboard

**Panels**:
- Request rate by endpoint
- Latency distribution
- Error rate trends
- Rate limiting metrics

**Access**: `http://localhost:3000/d/api`

### 4. System Dashboard

**Panels**:
- CPU usage
- Memory usage
- Disk I/O
- Network traffic

**Access**: `http://localhost:3000/d/system`

---

## Operational Procedures

### Daily Operations

#### Morning Checklist
```bash
# 1. Check system status
systemctl status quant_platform

# 2. Verify database connections
psql -d quant_platform -c "SELECT 1;"

# 3. Check disk usage
df -h | grep quant_platform

# 4. Review overnight logs
tail -n 100 logs/$(date +%Y%m%d)_quant_platform.log | grep ERROR
```

#### Evening Checklist
```bash
# 1. Verify factor updates
psql -d quant_platform -c "
SELECT factor_name, MAX(date)
FROM factor_scores
GROUP BY factor_name
ORDER BY factor_name;
"

# 2. Check backtest queue
curl http://localhost:8000/backtest/queue

# 3. Backup database
pg_dump -Fc quant_platform > backups/quant_platform_$(date +%Y%m%d).dump
```

### Weekly Operations

#### Sunday Night Maintenance
```bash
# 1. Vacuum and analyze database
psql -d quant_platform -c "VACUUM ANALYZE;"

# 2. Check compression status
psql -d quant_platform -c "
SELECT show_chunks('ohlcv_data');
"

# 3. Review weekly performance
python3 scripts/generate_weekly_report.py --week $(date +%Y%W)

# 4. Rotate old logs
find logs/ -name "*.log" -mtime +30 -delete
```

### Monthly Operations

#### First Sunday of Month
```bash
# 1. Full database backup
pg_dump -Fc quant_platform > backups/quant_platform_monthly_$(date +%Y%m).dump

# 2. Strategy performance review
python3 scripts/generate_monthly_report.py --month $(date +%Y%m)

# 3. Factor correlation analysis
python3 modules/factors/factor_correlation.py \
  --factors all \
  --start $(date -d '1 year ago' +%Y-%m-%d) \
  --output reports/factor_correlation_$(date +%Y%m).csv

# 4. Portfolio rebalancing
python3 quant_platform.py rebalance \
  --strategy all \
  --dry-run
```

---

## Troubleshooting

### Common Issues

#### Issue 1: Backtest Too Slow

**Symptoms**: Custom engine >60s, vectorbt >5s

**Diagnosis**:
```bash
# Check data size
psql -d quant_platform -c "
SELECT COUNT(*)
FROM ohlcv_data
WHERE ticker = '005930' AND date >= '2020-01-01';
"

# Check system resources
top -p $(pgrep -f quant_platform)
```

**Solutions**:
1. Use vectorbt for research (100x faster)
2. Reduce date range
3. Enable result caching
4. Increase memory allocation

#### Issue 2: Database Connection Pool Exhausted

**Symptoms**: Connection errors, high latency

**Diagnosis**:
```bash
# Check active connections
psql -d quant_platform -c "
SELECT COUNT(*) FROM pg_stat_activity
WHERE datname = 'quant_platform';
"
```

**Solutions**:
1. Increase max_connections in postgresql.conf
2. Implement connection pooling (pgbouncer)
3. Close idle connections
4. Review application connection logic

#### Issue 3: High Memory Usage

**Symptoms**: >80% RAM usage, OOM errors

**Diagnosis**:
```bash
# Check memory usage
free -h
ps aux --sort=-%mem | head -10
```

**Solutions**:
1. Reduce batch size for factor calculations
2. Enable result pagination
3. Clear cache periodically
4. Use streaming for large datasets

---

## Performance Targets

### System Performance

| Metric | Target | Alert Threshold |
|--------|--------|----------------|
| Backtest (Custom) | <30s | >60s |
| Backtest (vectorbt) | <1s | >5s |
| Database Query | <1s | >3s |
| API Latency (p95) | <200ms | >500ms |
| Dashboard Load | <3s | >10s |

### Resource Usage

| Resource | Normal | Warning | Critical |
|----------|--------|---------|----------|
| CPU | <50% | 50-80% | >80% |
| Memory | <70% | 70-85% | >85% |
| Disk | <80% | 80-90% | >90% |
| Disk I/O | <50 MB/s | 50-100 MB/s | >100 MB/s |

---

## Related Documentation

- **Architecture**: QUANT_PLATFORM_ARCHITECTURE.md
- **Database Schema**: QUANT_DATABASE_SCHEMA.md
- **Development Workflows**: QUANT_DEVELOPMENT_WORKFLOWS.md
- **Backtesting Engines**: QUANT_BACKTESTING_ENGINES.md
- **Roadmap**: QUANT_ROADMAP.md
