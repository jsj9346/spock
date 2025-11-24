# PostgreSQL Operations Guide - Quant Investment Platform

**Document Version**: 1.0.0
**Last Updated**: 2025-10-27
**Applies To**: PostgreSQL 15+ with TimescaleDB 2.11+

---

## Table of Contents

1. [Overview](#overview)
2. [Daily Operations](#daily-operations)
3. [Monitoring & Alerting](#monitoring--alerting)
4. [Performance Tuning](#performance-tuning)
5. [Data Quality Management](#data-quality-management)
6. [Backup & Recovery](#backup--recovery)
7. [Maintenance Tasks](#maintenance-tasks)
8. [Troubleshooting](#troubleshooting)
9. [Incident Response](#incident-response)
10. [Best Practices](#best-practices)

---

## Overview

### Purpose
This guide provides operational procedures for managing PostgreSQL + TimescaleDB in the Quant Investment Platform production environment.

### Operational Philosophy
- **Proactive Monitoring**: Detect issues before they impact users
- **Data Quality First**: Maintain >99.9% data accuracy
- **Performance SLOs**: Meet query performance targets (<100ms for 250 days, <1s for 10 years)
- **Automated Recovery**: Minimize manual intervention through automation
- **Evidence-Based Decisions**: Use metrics and logs for all operational decisions

### System Architecture
```
┌──────────────────────────────────────────────────────┐
│         Grafana Dashboard (Port 3000)                │
│  Database Metrics | Alerts | Performance Tracking   │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│      Prometheus Metrics Collector (Port 8000)        │
│  postgres_metrics.py | 50+ metrics | 1min interval  │
└─────────────────────┬────────────────────────────────┘
                      │
┌─────────────────────▼────────────────────────────────┐
│        PostgreSQL 15 + TimescaleDB 2.11              │
│  Hypertables | Continuous Aggregates | Compression  │
└──────────────────────────────────────────────────────┘
```

---

## Daily Operations

### Morning Checklist (5-10 minutes)

**1. Check System Health**
```bash
# Quick health check
psql -d quant_platform -c "
SELECT
    'Database Size' AS metric,
    pg_size_pretty(pg_database_size('quant_platform')) AS value
UNION ALL
SELECT 'Active Connections', COUNT(*)::text
    FROM pg_stat_activity WHERE datname = 'quant_platform'
UNION ALL
SELECT 'Slow Queries (24h)', COUNT(*)::text
    FROM pg_stat_statements WHERE mean_exec_time > 1000;
"
```

**Expected Results**:
- Database Size: Growing steadily (~1GB/month for KR stocks)
- Active Connections: <20
- Slow Queries: <10

**2. Review Grafana Dashboard**
- Navigate to: `http://localhost:3000/dashboards/postgres-monitoring`
- Check for red/yellow alerts in Overview panel
- Verify data freshness: Latest OHLCV data should be <24 hours old

**3. Check Backup Status**
```bash
# Verify latest backup exists
ls -lh ~/spock/backups/ | head -5

# Check backup age
LATEST_BACKUP=$(ls -t ~/spock/backups/*.sql.gz | head -1)
BACKUP_AGE=$(( ($(date +%s) - $(stat -f %m "$LATEST_BACKUP")) / 3600 ))
echo "Latest backup age: ${BACKUP_AGE} hours"

# Should be <24 hours
if [ "$BACKUP_AGE" -gt 24 ]; then
    echo "⚠️  WARNING: Backup is more than 24 hours old!"
fi
```

**4. Review Alert Log**
```bash
# Check for critical alerts (last 24 hours)
grep -i "critical\|error" ~/spock/logs/$(date +%Y%m%d)_quant_platform.log | tail -20
```

### End-of-Day Checklist (5 minutes)

**1. Verify Data Collection**
```bash
# Check today's OHLCV data ingestion
psql -d quant_platform -c "
SELECT
    region,
    COUNT(DISTINCT ticker) AS tickers_updated,
    COUNT(*) AS total_rows,
    MIN(date) AS oldest_date,
    MAX(date) AS latest_date
FROM ohlcv_data
WHERE date = CURRENT_DATE
GROUP BY region;
"
```

**Expected**: Should see data for current date (if market was open)

**2. Check Data Quality Report**
```bash
# Run comprehensive quality checks
python3 ~/spock/scripts/data_quality_checks.py --comprehensive --region KR

# Review summary output
# Expected: 0 missing dates, 0 duplicates, 0 price anomalies
```

**3. Review Performance Metrics**
```bash
# Check average query performance
psql -d quant_platform -c "
SELECT
    query_type,
    COUNT(*) AS executions,
    ROUND(AVG(duration_ms)::numeric, 2) AS avg_duration_ms,
    ROUND(MAX(duration_ms)::numeric, 2) AS max_duration_ms
FROM (
    SELECT
        CASE
            WHEN query LIKE '%ohlcv_data%' THEN 'OHLCV Query'
            WHEN query LIKE '%technical_analysis%' THEN 'Technical'
            ELSE 'Other'
        END AS query_type,
        mean_exec_time AS duration_ms
    FROM pg_stat_statements
    WHERE calls > 10
) AS query_stats
GROUP BY query_type;
"
```

**Expected**: OHLCV Query avg <200ms, max <1000ms

---

## Monitoring & Alerting

### Prometheus Metrics Overview

**Starting Metrics Server**:
```bash
# Start Prometheus metrics collector
python3 ~/spock/modules/monitoring/postgres_metrics.py --port 8000 &

# Verify metrics endpoint
curl http://localhost:8000/metrics | head -20
```

**Key Metrics Categories** (50+ total):

1. **Database Size** (10 metrics)
   - `postgres_database_size_bytes`: Total database size
   - `postgres_table_size_bytes{table="ohlcv_data"}`: Individual table sizes
   - `postgres_index_size_bytes{table="ohlcv_data"}`: Index sizes

2. **Query Performance** (15 metrics)
   - `postgres_query_duration_seconds`: Query execution time histogram
   - `postgres_slow_queries_total`: Queries >1s counter
   - `postgres_query_errors_total`: Query error counter

3. **Connection Pool** (5 metrics)
   - `postgres_active_connections`: Current active connections
   - `postgres_idle_connections`: Idle connections in pool
   - `postgres_connection_pool_size`: Total pool size

4. **Data Quality** (12 metrics)
   - `postgres_data_freshness_seconds{region="KR"}`: Time since last data update
   - `postgres_missing_dates_count`: Number of date gaps >3 days
   - `postgres_duplicate_records_count`: Duplicate OHLCV records

5. **TimescaleDB** (8 metrics)
   - `postgres_hypertable_chunks{hypertable="ohlcv_data"}`: Chunk count
   - `postgres_compressed_chunks`: Compressed chunk count
   - `postgres_compression_ratio`: Compression efficiency

### Alert Rules (20+ alerts)

**Critical Alerts** (immediate action required):
- **DatabaseDown**: Metrics collector unreachable for >1min
- **DatabaseSizeCritical**: Database >100GB
- **DuplicateRecordsDetected**: Duplicate OHLCV records found
- **QueryErrorRateHigh**: >1 query error/sec for >5min

**Warning Alerts** (review within 1 hour):
- **DataStale**: OHLCV data >7 days old
- **MissingDatesHigh**: >50 date gaps (>3 days)
- **SlowQueriesHigh**: >0.1 slow queries/sec
- **IndexHitRateLow**: Index hit rate <90%
- **BacktestQuerySlow**: P95 backtest query >1s

**Info Alerts** (review daily):
- **CompressionNotEnabled**: Hypertable has >100 uncompressed chunks for >24h
- **TableSizeGrowing**: Table growing >100MB/day for >7 days

### Grafana Dashboard Usage

**Dashboard URL**: `http://localhost:3000/dashboards/postgres-monitoring`

**15 Visualization Panels**:

1. **Database Overview** (4 panels)
   - Total database size trend
   - Table sizes (stacked bar chart)
   - Row counts by table
   - Total tickers by region

2. **Query Performance** (4 panels)
   - Query duration by type (time series)
   - Backtest query percentiles (P50/P95/P99)
   - Slow query rate (counter)
   - Query error rate (counter)

3. **Connections & Resources** (3 panels)
   - Active connections (gauge)
   - Index hit rate by table (gauge)
   - Cache hit rate (gauge)

4. **Data Quality** (2 panels)
   - Data age by region (time series)
   - Missing dates count (gauge)

5. **TimescaleDB** (2 panels)
   - Hypertable sizes (bar chart)
   - Chunk counts (gauge)

**Dashboard Annotations**:
- Deployment events
- Migration timestamps
- Performance tuning changes

---

## Performance Tuning

### Query Optimization Workflow

**Step 1: Identify Slow Queries**
```sql
-- Top 10 slowest queries (by total time)
SELECT
    queryid,
    LEFT(query, 80) AS query_preview,
    calls,
    ROUND(total_exec_time::numeric, 2) AS total_time_ms,
    ROUND(mean_exec_time::numeric, 2) AS avg_time_ms,
    ROUND(stddev_exec_time::numeric, 2) AS stddev_ms
FROM pg_stat_statements
WHERE query NOT LIKE '%pg_stat_statements%'
ORDER BY total_exec_time DESC
LIMIT 10;
```

**Step 2: Analyze Query Plan**
```sql
-- Use EXPLAIN ANALYZE for problematic query
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT ticker, date, close
FROM ohlcv_data
WHERE ticker = '005930' AND region = 'KR'
    AND date >= CURRENT_DATE - INTERVAL '1 year'
ORDER BY date;
```

**What to Look For**:
- **Seq Scan**: Should use indexes for large tables
- **Execution Time**: Compare actual vs. estimated rows
- **Buffers**: High shared hits = good, high reads = cache miss

**Step 3: Create Missing Indexes**
```sql
-- Example: Index on frequently filtered columns
CREATE INDEX CONCURRENTLY idx_ohlcv_ticker_date
    ON ohlcv_data(ticker, region, date DESC);

-- Verify index usage
SELECT
    schemaname, tablename, indexname,
    idx_scan, idx_tup_read, idx_tup_fetch
FROM pg_stat_user_indexes
WHERE indexname = 'idx_ohlcv_ticker_date';
```

**Step 4: Update Statistics**
```sql
-- Refresh query planner statistics
ANALYZE ohlcv_data;
ANALYZE technical_analysis;

-- Verify statistics freshness
SELECT
    schemaname, tablename,
    last_analyze, last_autoanalyze
FROM pg_stat_user_tables
WHERE tablename IN ('ohlcv_data', 'technical_analysis');
```

### Performance Tuning Checklist

**Database Configuration** (`postgresql.conf`):

```ini
# Memory Settings (for 16GB RAM system)
shared_buffers = 4GB                # 25% of RAM
effective_cache_size = 12GB         # 75% of RAM
work_mem = 64MB                     # Per-operation memory
maintenance_work_mem = 1GB          # For VACUUM, CREATE INDEX

# Query Planner
random_page_cost = 1.1              # SSD-optimized (default 4.0)
effective_io_concurrency = 200      # SSD concurrent I/O

# Write-Ahead Log
wal_buffers = 16MB
checkpoint_completion_target = 0.9
max_wal_size = 4GB

# TimescaleDB Settings
timescaledb.max_background_workers = 8
```

**Apply Configuration Changes**:
```bash
# Reload PostgreSQL configuration
psql -d quant_platform -c "SELECT pg_reload_conf();"

# Or restart for some settings
brew services restart postgresql@17
```

### Index Maintenance

**Check Index Health**:
```sql
-- Bloated or unused indexes
SELECT
    schemaname, tablename, indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    idx_scan AS times_used,
    CASE
        WHEN idx_scan = 0 THEN 'UNUSED - Consider dropping'
        WHEN idx_scan < 100 THEN 'RARELY USED'
        ELSE 'OK'
    END AS status
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;
```

**Rebuild Bloated Indexes**:
```sql
-- Concurrent rebuild (no table locking)
REINDEX INDEX CONCURRENTLY idx_ohlcv_ticker_region_date;
```

### Vacuum & Analyze Schedule

**Manual Vacuum** (run weekly):
```sql
-- Full vacuum with analyze
VACUUM (ANALYZE, VERBOSE) ohlcv_data;
VACUUM (ANALYZE, VERBOSE) technical_analysis;
```

**Autovacuum Monitoring**:
```sql
-- Check autovacuum status
SELECT
    schemaname, relname,
    last_vacuum, last_autovacuum,
    n_dead_tup, n_live_tup,
    ROUND(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 2) AS dead_tuple_pct
FROM pg_stat_user_tables
WHERE n_dead_tup > 0
ORDER BY n_dead_tup DESC;
```

---

## Data Quality Management

### Daily Data Quality Checks

**Automated Quality Checks** (run daily at 6 AM):
```bash
# Add to crontab
# 0 6 * * * /usr/bin/python3 ~/spock/scripts/data_quality_checks.py --comprehensive --region KR >> ~/spock/logs/data_quality.log 2>&1

# Run manually
python3 ~/spock/scripts/data_quality_checks.py --comprehensive --region KR
```

**Quality Check Output**:
```
=== Data Quality Report ===
Region: KR
Date: 2025-10-27

✅ Missing Dates: 0 gaps found
✅ Duplicate Records: 0 duplicates found
✅ Price Anomalies: 0 outliers (threshold: 3.0 std dev)
✅ NULL Values: 0 NULL prices found
✅ Business Logic: All OHLCV records pass validation

Summary: PASS (0 issues found)
```

### Missing Date Detection

**Find Date Gaps**:
```sql
-- Gaps >3 days in OHLCV data
WITH date_ranges AS (
    SELECT
        ticker, region,
        date AS current_date,
        LAG(date) OVER (PARTITION BY ticker, region ORDER BY date) AS prev_date,
        date - LAG(date) OVER (PARTITION BY ticker, region ORDER BY date) AS gap_days
    FROM ohlcv_data
)
SELECT
    ticker, region, prev_date, current_date, gap_days
FROM date_ranges
WHERE gap_days > 3
ORDER BY gap_days DESC, ticker;
```

**Backfill Missing Dates**:
```bash
# Identify missing dates
python3 ~/spock/scripts/data_quality_checks.py --check missing-dates --region KR > missing_dates.txt

# Backfill using KIS API
python3 ~/spock/modules/kis_data_collector.py \
    --tickers $(cat missing_dates.txt | cut -d',' -f1) \
    --start-date 2024-01-01 \
    --end-date 2024-12-31 \
    --region KR
```

### Price Anomaly Detection

**Z-Score Outlier Detection** (automated in data_quality_checks.py):
```sql
-- Find price movements >3 standard deviations
WITH daily_returns AS (
    SELECT
        ticker, region, date, close,
        (close - LAG(close) OVER w) / NULLIF(LAG(close) OVER w, 0) AS daily_return
    FROM ohlcv_data
    WINDOW w AS (PARTITION BY ticker, region ORDER BY date)
),
return_stats AS (
    SELECT
        ticker, region,
        AVG(daily_return) AS mean_return,
        STDDEV(daily_return) AS std_return
    FROM daily_returns
    WHERE daily_return IS NOT NULL
    GROUP BY ticker, region
)
SELECT
    dr.ticker, dr.region, dr.date, dr.close, dr.daily_return,
    ROUND(((dr.daily_return - rs.mean_return) / NULLIF(rs.std_return, 0))::numeric, 2) AS z_score
FROM daily_returns dr
JOIN return_stats rs USING (ticker, region)
WHERE ABS((dr.daily_return - rs.mean_return) / NULLIF(rs.std_return, 0)) > 3.0
ORDER BY ABS((dr.daily_return - rs.mean_return) / NULLIF(rs.std_return, 0)) DESC;
```

**Investigation Steps**:
1. Verify data source (check KIS API response)
2. Check for stock splits or dividends
3. Validate against external source (Yahoo Finance, Bloomberg)
4. If confirmed error, correct or remove data

### Duplicate Record Detection

**Find Duplicates**:
```sql
-- Detect duplicate OHLCV records (should be 0)
SELECT
    ticker, region, date, COUNT(*) AS duplicate_count
FROM ohlcv_data
GROUP BY ticker, region, date
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;
```

**Remove Duplicates** (if found):
```sql
-- Keep earliest inserted record, remove duplicates
WITH duplicates AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY ticker, region, date
            ORDER BY created_at
        ) AS rn
    FROM ohlcv_data
)
DELETE FROM ohlcv_data
WHERE id IN (
    SELECT id FROM duplicates WHERE rn > 1
);
```

---

## Backup & Recovery

### Automated Backup Schedule

**Cron Configuration**:
```bash
# Daily backup at 2 AM (when market is closed)
0 2 * * * /Users/13ruce/spock/scripts/backup_postgres.sh >> /Users/13ruce/spock/logs/backup.log 2>&1

# Weekly full backup with S3 upload (Sunday 3 AM)
0 3 * * 0 /Users/13ruce/spock/scripts/backup_postgres.sh --upload-s3 >> /Users/13ruce/spock/logs/backup_weekly.log 2>&1
```

### Manual Backup

**Full Database Backup**:
```bash
# Standard backup
~/spock/scripts/backup_postgres.sh

# With S3 upload
~/spock/scripts/backup_postgres.sh --upload-s3

# Dry run (test mode)
~/spock/scripts/backup_postgres.sh --dry-run
```

**Backup Verification**:
```bash
# List available backups
ls -lh ~/spock/backups/

# Check backup integrity
LATEST_BACKUP=$(ls -t ~/spock/backups/*.sql.gz | head -1)
gunzip -t "$LATEST_BACKUP" && echo "✅ Backup is valid"
```

### Recovery Procedures

**Restore from Latest Backup**:
```bash
# Full restore (destroys current database)
~/spock/scripts/restore_postgres.sh --latest

# Dry run (test without applying)
~/spock/scripts/restore_postgres.sh --latest --dry-run
```

**Restore from Specific Backup**:
```bash
# List available backups
ls ~/spock/backups/

# Restore specific backup
~/spock/scripts/restore_postgres.sh --file ~/spock/backups/quant_platform_20251027_020000.sql.gz
```

**Restore from S3**:
```bash
# Download and restore from S3
~/spock/scripts/restore_postgres.sh --from-s3 --file s3://quant-backups/quant_platform_20251027_020000.sql.gz
```

### Point-in-Time Recovery (PITR)

**Enable WAL Archiving** (`postgresql.conf`):
```ini
wal_level = replica
archive_mode = on
archive_command = 'test ! -f /path/to/archive/%f && cp %p /path/to/archive/%f'
```

**Restore to Specific Timestamp**:
```bash
# Stop PostgreSQL
brew services stop postgresql@17

# Restore base backup
gunzip -c ~/spock/backups/quant_platform_20251027_020000.sql.gz | psql -d postgres

# Create recovery.conf
cat > $PGDATA/recovery.conf <<EOF
restore_command = 'cp /path/to/archive/%f %p'
recovery_target_time = '2025-10-27 14:30:00'
EOF

# Start PostgreSQL (will replay WAL to target time)
brew services start postgresql@17
```

---

## Maintenance Tasks

### Weekly Maintenance (30 minutes)

**1. Database Cleanup**:
```sql
-- Remove old pg_stat_statements data
SELECT pg_stat_statements_reset();

-- Vacuum analyze large tables
VACUUM (ANALYZE, VERBOSE) ohlcv_data;
VACUUM (ANALYZE, VERBOSE) technical_analysis;
```

**2. Index Maintenance**:
```sql
-- Rebuild bloated indexes
REINDEX INDEX CONCURRENTLY idx_ohlcv_ticker_region_date;
REINDEX INDEX CONCURRENTLY idx_technical_ticker_date;
```

**3. TimescaleDB Chunk Management**:
```sql
-- Check chunk count
SELECT hypertable_name, COUNT(*) AS chunk_count
FROM timescaledb_information.chunks
GROUP BY hypertable_name;

-- Drop old chunks (optional, for data retention policy)
SELECT drop_chunks('ohlcv_data', INTERVAL '5 years');
```

**4. Review Slow Query Log**:
```bash
# Extract slow queries from pg_stat_statements
psql -d quant_platform -c "
SELECT
    queryid,
    LEFT(query, 100) AS query_preview,
    calls,
    ROUND(mean_exec_time::numeric, 2) AS avg_ms
FROM pg_stat_statements
WHERE mean_exec_time > 1000
ORDER BY mean_exec_time DESC
LIMIT 20;
" > slow_queries_$(date +%Y%m%d).txt
```

### Monthly Maintenance (1-2 hours)

**1. Compression Review**:
```sql
-- Check compression status
SELECT
    hypertable_name,
    COUNT(*) FILTER (WHERE is_compressed = true) AS compressed_chunks,
    COUNT(*) FILTER (WHERE is_compressed = false) AS uncompressed_chunks,
    ROUND(COUNT(*) FILTER (WHERE is_compressed = true)::numeric /
          NULLIF(COUNT(*), 0) * 100, 2) AS compression_pct
FROM timescaledb_information.chunks
GROUP BY hypertable_name;

-- Enable compression on old chunks (>1 year)
SELECT compress_chunk(i, if_not_compressed => true)
FROM show_chunks('ohlcv_data', older_than => INTERVAL '1 year') i;
```

**2. Database Statistics Update**:
```sql
-- Full analyze for query planner
ANALYZE VERBOSE;
```

**3. Review Database Size Trends**:
```sql
-- Database growth analysis
SELECT
    'ohlcv_data' AS table_name,
    pg_size_pretty(pg_total_relation_size('ohlcv_data')) AS total_size,
    pg_size_pretty(pg_relation_size('ohlcv_data')) AS table_size,
    pg_size_pretty(pg_total_relation_size('ohlcv_data') - pg_relation_size('ohlcv_data')) AS index_size
UNION ALL
SELECT 'technical_analysis',
    pg_size_pretty(pg_total_relation_size('technical_analysis')),
    pg_size_pretty(pg_relation_size('technical_analysis')),
    pg_size_pretty(pg_total_relation_size('technical_analysis') - pg_relation_size('technical_analysis'));
```

**4. Backup Verification Test**:
```bash
# Test restore in temporary database
createdb quant_platform_test
gunzip -c ~/spock/backups/$(ls -t ~/spock/backups/*.sql.gz | head -1) | psql -d quant_platform_test

# Verify data integrity
psql -d quant_platform_test -c "SELECT COUNT(*) FROM ohlcv_data;"

# Drop test database
dropdb quant_platform_test
```

### Quarterly Maintenance (2-4 hours)

**1. Performance Audit**:
```bash
# Run comprehensive performance benchmarks
python3 ~/spock/scripts/benchmark_postgres_performance.py --comprehensive

# Review results and identify regressions
# Compare against baseline metrics
```

**2. Security Audit**:
```sql
-- Review user permissions
SELECT
    grantee, privilege_type, table_name
FROM information_schema.role_table_grants
WHERE grantee != 'postgres'
ORDER BY grantee, table_name;

-- Check for weak passwords (should force rotation)
SELECT usename, valuntil
FROM pg_shadow
WHERE valuntil < CURRENT_DATE + INTERVAL '30 days'
   OR valuntil IS NULL;
```

**3. Disk Space Planning**:
```bash
# Check disk usage trends
df -h ~/spock/data/

# Estimate growth rate
CURRENT_SIZE=$(psql -d quant_platform -tAc "SELECT pg_database_size('quant_platform');")
DAYS_AGO=90
PREV_SIZE=5000000000  # From logs or monitoring

DAILY_GROWTH=$(( ($CURRENT_SIZE - $PREV_SIZE) / $DAYS_AGO ))
echo "Average daily growth: $(numfmt --to=iec-i --suffix=B $DAILY_GROWTH)"

# Project 6 months ahead
PROJECTED_SIZE=$(( $CURRENT_SIZE + ($DAILY_GROWTH * 180) ))
echo "Projected size in 6 months: $(numfmt --to=iec-i --suffix=B $PROJECTED_SIZE)"
```

---

## Troubleshooting

### Common Issues & Solutions

#### Issue 1: Slow Query Performance

**Symptoms**:
- Backtest queries taking >5 seconds
- Dashboard loading slowly
- Grafana alerts: `BacktestQuerySlow`

**Diagnosis**:
```sql
-- Check for missing indexes
SELECT
    schemaname, tablename,
    seq_scan, seq_tup_read,
    idx_scan, idx_tup_fetch,
    ROUND((seq_scan::float / NULLIF(seq_scan + idx_scan, 0)) * 100, 2) AS seq_scan_pct
FROM pg_stat_user_tables
WHERE seq_scan > 1000
ORDER BY seq_scan DESC;
```

**Solutions**:
1. **Create Missing Indexes**:
```sql
-- Most common query pattern: ticker + date range
CREATE INDEX CONCURRENTLY idx_ohlcv_ticker_date
    ON ohlcv_data(ticker, region, date DESC);
```

2. **Update Query Statistics**:
```sql
ANALYZE ohlcv_data;
```

3. **Increase Work Memory** (for complex queries):
```sql
SET work_mem = '256MB';
```

#### Issue 2: High Database Size

**Symptoms**:
- Database >100GB
- Grafana alert: `DatabaseSizeCritical`
- Disk space running low

**Diagnosis**:
```sql
-- Find largest tables
SELECT
    schemaname, tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

**Solutions**:
1. **Enable Compression** (TimescaleDB):
```sql
-- Enable compression policy (compress chunks >1 year old)
SELECT add_compression_policy('ohlcv_data', INTERVAL '1 year');

-- Manually compress old chunks
SELECT compress_chunk(i, if_not_compressed => true)
FROM show_chunks('ohlcv_data', older_than => INTERVAL '1 year') i;
```

2. **Drop Old Data** (if retention policy allows):
```sql
-- Drop chunks older than 5 years
SELECT drop_chunks('ohlcv_data', INTERVAL '5 years');
```

3. **Vacuum Full** (reclaim disk space):
```sql
-- WARNING: Locks table, run during maintenance window
VACUUM FULL ohlcv_data;
```

#### Issue 3: Connection Pool Exhaustion

**Symptoms**:
- Application errors: "FATAL: remaining connection slots reserved"
- Grafana alert: `ActiveConnectionsHigh`
- Slow API responses

**Diagnosis**:
```sql
-- Check active connections
SELECT
    datname, usename, application_name, state,
    COUNT(*) AS connection_count
FROM pg_stat_activity
WHERE datname = 'quant_platform'
GROUP BY datname, usename, application_name, state
ORDER BY connection_count DESC;
```

**Solutions**:
1. **Increase Max Connections** (`postgresql.conf`):
```ini
max_connections = 100  # Default: 100, increase to 200
```

2. **Close Idle Connections**:
```sql
-- Find idle connections >10 minutes
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'quant_platform'
  AND state = 'idle'
  AND state_change < NOW() - INTERVAL '10 minutes';
```

3. **Implement Connection Pooling** (PgBouncer):
```bash
# Install PgBouncer
brew install pgbouncer

# Configure /usr/local/etc/pgbouncer.ini
[databases]
quant_platform = host=localhost port=5432 dbname=quant_platform

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
```

#### Issue 4: Data Quality Issues

**Symptoms**:
- Grafana alerts: `DuplicateRecordsDetected`, `MissingDatesHigh`
- Backtests showing unexpected results
- Price anomalies detected

**Diagnosis**:
```bash
# Run comprehensive data quality checks
python3 ~/spock/scripts/data_quality_checks.py --comprehensive --region KR
```

**Solutions**:
1. **Remove Duplicate Records**:
```sql
WITH duplicates AS (
    SELECT id, ROW_NUMBER() OVER (
        PARTITION BY ticker, region, date ORDER BY created_at
    ) AS rn
    FROM ohlcv_data
)
DELETE FROM ohlcv_data
WHERE id IN (SELECT id FROM duplicates WHERE rn > 1);
```

2. **Backfill Missing Dates**:
```bash
# Identify gaps
python3 ~/spock/scripts/data_quality_checks.py --check missing-dates --region KR

# Re-run data collector for missing dates
python3 ~/spock/modules/kis_data_collector.py --backfill --region KR
```

3. **Correct Price Anomalies**:
```bash
# Investigate outliers
python3 ~/spock/scripts/data_quality_checks.py --check price-anomalies --threshold 3.0

# Manually correct or remove bad data
psql -d quant_platform -c "DELETE FROM ohlcv_data WHERE ticker = '005930' AND date = '2025-10-15';"
```

#### Issue 5: Backup Failures

**Symptoms**:
- Grafana alert: `BackupMissing`
- Backup log shows errors
- Backup files not created

**Diagnosis**:
```bash
# Check backup log
tail -50 ~/spock/logs/backup.log

# Check disk space
df -h ~/spock/backups/

# Test pg_dump manually
pg_dump -h localhost -U postgres -d quant_platform -f /tmp/test_backup.sql
```

**Solutions**:
1. **Insufficient Disk Space**:
```bash
# Free up space
rm ~/spock/backups/quant_platform_202508*.sql.gz

# Adjust retention policy in backup script
# RETENTION_DAYS=30 → RETENTION_DAYS=15
```

2. **Permission Issues**:
```bash
# Fix backup directory permissions
chmod 755 ~/spock/backups/
chown $(whoami) ~/spock/backups/
```

3. **Database Connection Issues**:
```bash
# Verify PostgreSQL is running
brew services list | grep postgresql

# Test connection
psql -d quant_platform -c "SELECT 1;"
```

### Emergency Procedures

#### Database Crash Recovery

**Symptoms**: PostgreSQL won't start, data corruption

**Steps**:
1. **Check PostgreSQL Logs**:
```bash
tail -100 /opt/homebrew/var/log/postgresql@17.log
```

2. **Attempt Safe Start**:
```bash
# Stop any running instances
brew services stop postgresql@17

# Start in single-user mode
postgres --single -D /opt/homebrew/var/postgresql@17 quant_platform
```

3. **Restore from Backup**:
```bash
# If recovery fails, restore from latest backup
~/spock/scripts/restore_postgres.sh --latest
```

#### Data Corruption Detection

**Symptoms**: Unexpected query results, constraint violations

**Steps**:
1. **Check Database Integrity**:
```sql
-- Verify table integrity
SELECT * FROM pg_check_constraints('ohlcv_data');

-- Reindex all tables
REINDEX DATABASE quant_platform;
```

2. **Validate Against Source**:
```bash
# Compare PostgreSQL vs. SQLite
python3 ~/spock/scripts/validate_postgres_data.py --comprehensive
```

3. **Restore Affected Tables**:
```bash
# Restore specific table from backup
pg_restore -h localhost -U postgres -d quant_platform -t ohlcv_data ~/spock/backups/latest.sql.gz
```

---

## Incident Response

### Incident Severity Levels

**P0 - Critical** (Response: Immediate):
- Database completely down
- Data corruption detected
- Security breach

**P1 - High** (Response: <1 hour):
- Slow queries impacting all users
- Backup failures
- Data quality issues affecting >10% of data

**P2 - Medium** (Response: <4 hours):
- Performance degradation (<50% slower)
- Monitoring system down
- Non-critical data quality issues

**P3 - Low** (Response: <24 hours):
- Minor performance issues
- Informational alerts
- Documentation updates

### Incident Response Workflow

**1. Detection & Assessment** (5 minutes):
```bash
# Quick health check
psql -d quant_platform -c "SELECT 1;"  # Database responsive?
curl http://localhost:8000/metrics  # Metrics collecting?
curl http://localhost:3000/  # Grafana accessible?

# Check system resources
top -l 1 | grep -E "CPU|PhysMem"
df -h
```

**2. Containment** (10 minutes):
```bash
# Stop non-essential services
pkill -f "quant_platform.py"

# Increase logging verbosity
export LOG_LEVEL=DEBUG

# Create incident snapshot
pg_dump -d quant_platform -f ~/incident_snapshot_$(date +%Y%m%d_%H%M%S).sql
```

**3. Investigation** (30 minutes):
```bash
# Collect diagnostics
psql -d quant_platform -c "SELECT * FROM pg_stat_activity;" > activity_snapshot.txt
psql -d quant_platform -c "SELECT * FROM pg_stat_statements ORDER BY total_exec_time DESC LIMIT 50;" > slow_queries.txt
grep -i "error\|critical" ~/spock/logs/$(date +%Y%m%d)_quant_platform.log > error_log.txt
```

**4. Resolution** (varies):
- Apply fix based on root cause (see Troubleshooting section)
- Verify fix resolves issue
- Monitor for recurrence

**5. Post-Incident Review** (within 48 hours):
- Document root cause
- Update runbooks
- Implement preventive measures
- Update alerting rules if needed

### Incident Documentation Template

```markdown
# Incident Report

**Incident ID**: INC-2025-1027-001
**Severity**: P1
**Start Time**: 2025-10-27 14:30:00 KST
**End Time**: 2025-10-27 15:15:00 KST
**Duration**: 45 minutes

## Summary
Brief description of the incident

## Impact
- Users affected: X
- Services impacted: Y
- Data integrity: OK / COMPROMISED

## Timeline
- 14:30 - Alert triggered: BacktestQuerySlow
- 14:35 - Investigation started
- 14:45 - Root cause identified: Missing index
- 15:00 - Fix applied: Created index
- 15:15 - Incident resolved

## Root Cause
Detailed explanation of what caused the incident

## Resolution
Steps taken to resolve the incident

## Preventive Measures
- Action 1: Create index on commonly queried columns
- Action 2: Add monitoring for index usage
- Action 3: Update documentation

## Lessons Learned
What we learned from this incident
```

---

## Best Practices

### Query Writing Guidelines

**1. Always Use Prepared Statements**:
```python
# Good: Parameterized query (prevents SQL injection)
query = "SELECT * FROM ohlcv_data WHERE ticker = %s AND region = %s"
cursor.execute(query, (ticker, region))

# Bad: String concatenation (SQL injection risk)
query = f"SELECT * FROM ohlcv_data WHERE ticker = '{ticker}' AND region = '{region}'"
```

**2. Limit Result Sets**:
```sql
-- Good: Explicit limit
SELECT * FROM ohlcv_data
WHERE ticker = '005930' AND region = 'KR'
ORDER BY date DESC
LIMIT 1000;

-- Bad: Unbounded query (could return millions of rows)
SELECT * FROM ohlcv_data WHERE region = 'KR';
```

**3. Use Indexes Effectively**:
```sql
-- Good: Index-friendly query (uses idx_ohlcv_ticker_region_date)
SELECT * FROM ohlcv_data
WHERE ticker = '005930' AND region = 'KR' AND date >= '2024-01-01'
ORDER BY date DESC;

-- Bad: Function on indexed column (index not used)
SELECT * FROM ohlcv_data
WHERE YEAR(date) = 2024;  -- Use: WHERE date >= '2024-01-01' AND date < '2025-01-01'
```

### Monitoring Best Practices

**1. Set Realistic Baselines**:
- Collect 2 weeks of metrics before setting alert thresholds
- Use P95 instead of max for latency alerts
- Account for market hours (higher load during trading hours)

**2. Actionable Alerts Only**:
- Every alert must have a defined response action
- No alerts for informational metrics
- Alert fatigue = missed critical issues

**3. Regular Review**:
- Weekly: Review triggered alerts, adjust thresholds
- Monthly: Review alert coverage, add missing alerts
- Quarterly: Audit alert relevance, remove noise

### Backup Best Practices

**1. Follow 3-2-1 Rule**:
- 3 copies of data (production + 2 backups)
- 2 different media types (local disk + S3)
- 1 offsite copy (S3 in different region)

**2. Test Restores Regularly**:
- Monthly: Restore backup to test environment
- Quarterly: Full disaster recovery drill
- Annual: Cross-region restore test

**3. Automate Everything**:
- Scheduled backups (cron)
- Automated verification (checksum)
- Automated cleanup (retention policy)
- Automated alerts (backup failures)

### Security Best Practices

**1. Principle of Least Privilege**:
```sql
-- Create read-only user for reporting
CREATE USER reporting_user WITH PASSWORD 'strong_password';
GRANT CONNECT ON DATABASE quant_platform TO reporting_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO reporting_user;

-- Prevent write access
REVOKE INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public FROM reporting_user;
```

**2. Encrypt Sensitive Data**:
```sql
-- Use pgcrypto for sensitive columns
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Encrypt API keys
UPDATE config SET api_key = pgp_sym_encrypt(api_key, 'encryption_key');
```

**3. Audit Logging**:
```sql
-- Enable audit logging for sensitive operations
ALTER TABLE tickers ENABLE ROW LEVEL SECURITY;

CREATE POLICY audit_policy ON tickers
FOR ALL TO PUBLIC
USING (true)
WITH CHECK (true);
```

### Performance Best Practices

**1. Batch Operations**:
```python
# Good: Batch insert (10x faster)
rows = [(ticker, date, open, high, low, close) for ...]
cursor.executemany("INSERT INTO ohlcv_data VALUES %s", rows)

# Bad: Individual inserts
for row in rows:
    cursor.execute("INSERT INTO ohlcv_data VALUES %s", row)
```

**2. Use Continuous Aggregates** (TimescaleDB):
```sql
-- Pre-compute monthly aggregates
CREATE MATERIALIZED VIEW ohlcv_monthly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 month', date) AS month,
    ticker, region,
    first(open, date) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, date) AS close,
    sum(volume) AS volume
FROM ohlcv_data
GROUP BY month, ticker, region;

-- Refresh policy
SELECT add_continuous_aggregate_policy('ohlcv_monthly',
    start_offset => INTERVAL '3 months',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 day');
```

**3. Connection Pooling**:
```python
# Good: Use connection pool
from psycopg2 import pool
connection_pool = pool.ThreadedConnectionPool(5, 20, dsn=DATABASE_URL)

# Bad: Create new connection for each query
conn = psycopg2.connect(dsn=DATABASE_URL)
```

---

## Appendix

### Useful SQL Queries

**Database Health Summary**:
```sql
SELECT
    'Database Size' AS metric,
    pg_size_pretty(pg_database_size('quant_platform')) AS value
UNION ALL
SELECT 'Total Tables', COUNT(*)::text
    FROM information_schema.tables WHERE table_schema = 'public'
UNION ALL
SELECT 'Total Indexes', COUNT(*)::text
    FROM pg_indexes WHERE schemaname = 'public'
UNION ALL
SELECT 'Active Connections', COUNT(*)::text
    FROM pg_stat_activity WHERE datname = 'quant_platform'
UNION ALL
SELECT 'Cache Hit Rate', ROUND(
    sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0) * 100, 2
)::text || '%'
    FROM pg_statio_user_tables;
```

**Table Bloat Detection**:
```sql
SELECT
    schemaname, tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    ROUND(
        (pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename))::numeric /
        NULLIF(pg_total_relation_size(schemaname||'.'||tablename), 0) * 100,
        2
    ) AS bloat_pct
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Performance Benchmarks

**Query Performance Targets**:
| Query Type | Target (ms) | Acceptable (ms) | Critical (ms) |
|------------|-------------|-----------------|---------------|
| Single ticker, 250 days | <100 | <200 | >500 |
| Single ticker, 1 year | <200 | <500 | >1000 |
| Single ticker, 10 years | <1000 | <2000 | >5000 |
| Backtest (5 years, 50 tickers) | <5000 | <10000 | >30000 |
| Portfolio optimization | <10000 | <30000 | >60000 |

**Database Size Estimates**:
| Data Type | Row Size | Rows/Ticker/Year | Storage/Ticker/Year |
|-----------|----------|------------------|---------------------|
| OHLCV | ~80 bytes | 250 | ~20KB |
| Technical Indicators | ~120 bytes | 250 | ~30KB |
| Factor Scores | ~60 bytes | 250 | ~15KB |

**Total Storage** (1000 tickers, 10 years):
- OHLCV: ~200MB
- Technical: ~300MB
- Factors: ~150MB
- Indexes: ~400MB
- **Total: ~1GB** (uncompressed)
- **With Compression: ~200MB** (5x savings)

### Command Reference

**PostgreSQL Commands**:
```bash
# Start/stop PostgreSQL
brew services start postgresql@17
brew services stop postgresql@17
brew services restart postgresql@17

# Connect to database
psql -d quant_platform

# Import SQL file
psql -d quant_platform -f schema.sql

# Export database
pg_dump -d quant_platform -f backup.sql

# List databases
psql -l

# List tables
psql -d quant_platform -c "\dt"

# Show table schema
psql -d quant_platform -c "\d ohlcv_data"
```

**Monitoring Commands**:
```bash
# Start Prometheus metrics server
python3 ~/spock/modules/monitoring/postgres_metrics.py --port 8000 &

# Check metrics endpoint
curl http://localhost:8000/metrics

# Start Grafana
brew services start grafana

# Access Grafana UI
open http://localhost:3000
```

**Maintenance Commands**:
```bash
# Run data quality checks
python3 ~/spock/scripts/data_quality_checks.py --comprehensive

# Performance benchmarks
python3 ~/spock/scripts/benchmark_postgres_performance.py --comprehensive

# Validate data integrity
python3 ~/spock/scripts/validate_postgres_data.py --comprehensive

# Manual backup
~/spock/scripts/backup_postgres.sh

# Restore from backup
~/spock/scripts/restore_postgres.sh --latest
```

---

## Contact & Support

### Escalation Path

**Level 1 - Self-Service**:
- Check this operations guide
- Review Grafana dashboards
- Check application logs

**Level 2 - Team Lead** (incidents, performance issues):
- Email: team-lead@example.com
- Slack: #quant-platform-ops

**Level 3 - Database Admin** (data corruption, backup failures):
- Email: dba@example.com
- On-call: [PagerDuty]

### Resources

**Documentation**:
- [POSTGRES_MIGRATION_GUIDE.md](POSTGRES_MIGRATION_GUIDE.md) - Migration procedures
- [QUANT_DATABASE_SCHEMA.md](QUANT_DATABASE_SCHEMA.md) - Schema reference
- [QUANT_ROADMAP.md](QUANT_ROADMAP.md) - Project roadmap

**External Resources**:
- PostgreSQL Documentation: https://www.postgresql.org/docs/
- TimescaleDB Documentation: https://docs.timescale.com/
- Prometheus Documentation: https://prometheus.io/docs/
- Grafana Documentation: https://grafana.com/docs/

**Community**:
- PostgreSQL Slack: https://postgres-slack.herokuapp.com/
- TimescaleDB Community: https://slack.timescale.com/

---

**Document Version**: 1.0.0
**Last Reviewed**: 2025-10-27
**Next Review**: 2025-11-27
**Owner**: Quant Platform Team
