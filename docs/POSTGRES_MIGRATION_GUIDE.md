# PostgreSQL Migration Guide

**Phase 4: SQLite to PostgreSQL + TimescaleDB Migration**

Complete guide for migrating from Spock's SQLite database to PostgreSQL + TimescaleDB for the Quant Investment Platform.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Pre-Migration Checklist](#pre-migration-checklist)
4. [Migration Workflow](#migration-workflow)
5. [Step-by-Step Migration](#step-by-step-migration)
6. [Validation & Testing](#validation--testing)
7. [Post-Migration Tasks](#post-migration-tasks)
8. [Rollback Procedures](#rollback-procedures)
9. [Troubleshooting](#troubleshooting)
10. [Performance Optimization](#performance-optimization)

---

## Overview

### Migration Objectives

- **Unlimited Retention**: Move from 250-day SQLite retention to unlimited PostgreSQL storage
- **Time-Series Optimization**: Leverage TimescaleDB hypertables for efficient OHLCV data
- **Query Performance**: Achieve <100ms queries for 250 days, <1s for 10 years
- **Data Compression**: Enable 10x space savings with TimescaleDB compression
- **Zero Data Loss**: 100% data integrity with comprehensive validation

### What Changes

| Aspect | SQLite (Spock) | PostgreSQL (Quant Platform) |
|--------|----------------|------------------------------|
| **Database** | SQLite file | PostgreSQL 15+ server |
| **Retention** | 250 days | Unlimited |
| **Size** | ~500 MB | Scalable to TB+ |
| **Time-Series** | Basic tables | TimescaleDB hypertables |
| **Compression** | None | 10x with TimescaleDB |
| **Queries** | Simple indexed | Advanced with continuous aggregates |
| **Backup** | File copy | pg_dump + S3 |

### What Stays the Same

- ✅ Table schemas (backward compatible)
- ✅ Data structure (tickers, ohlcv_data, technical_analysis)
- ✅ Application code (SQLiteDatabaseManager → PostgresDatabaseManager)
- ✅ 70% of existing infrastructure

---

## Prerequisites

### System Requirements

**Minimum**:
- macOS 10.15+ or Linux
- 8 GB RAM
- 50 GB free disk space
- Python 3.11+

**Recommended**:
- 16 GB RAM
- 100 GB free disk space (for growth)
- SSD storage

### Software Installation

#### 1. PostgreSQL 15+

**macOS (Homebrew)**:
```bash
brew install postgresql@17
brew services start postgresql@17
```

**Linux (Ubuntu/Debian)**:
```bash
sudo apt-get update
sudo apt-get install postgresql-15 postgresql-contrib-15
sudo systemctl start postgresql
```

**Verify installation**:
```bash
psql --version
# Expected: psql (PostgreSQL) 17.x
```

#### 2. TimescaleDB 2.11+

**macOS (Homebrew)**:
```bash
brew tap timescale/tap
brew install timescaledb

# Add to PostgreSQL config
timescaledb-tune --quiet --yes
```

**Linux (Ubuntu/Debian)**:
```bash
sudo sh -c "echo 'deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -
sudo apt-get update
sudo apt-get install timescaledb-2-postgresql-15
sudo timescaledb-tune
```

**Verify installation**:
```bash
psql -c "SELECT default_version FROM pg_available_extensions WHERE name = 'timescaledb';"
# Expected: 2.11.x or higher
```

#### 3. Python Dependencies

```bash
cd ~/spock
pip install -r requirements_quant.txt

# Key dependencies:
# - psycopg2==2.9.7 (PostgreSQL adapter)
# - prometheus-client==0.23.1 (metrics)
```

### Database Setup

#### Create Database

```bash
# Create database
createdb quant_platform

# Or using psql
psql -c "CREATE DATABASE quant_platform;"
```

#### Enable TimescaleDB

```bash
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

#### Verify connection

```bash
psql -d quant_platform -c "SELECT version();"
```

---

## Pre-Migration Checklist

### 1. Environment Configuration

**Create/update `.env` file**:
```bash
# PostgreSQL configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=quant_platform
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_secure_password

# SQLite source (existing)
SQLITE_DB_PATH=data/spock_local.db
```

**Verify configuration**:
```bash
python3 -c "
from modules.db_manager_postgres import PostgresDatabaseManager
db = PostgresDatabaseManager()
print('✅ PostgreSQL connection successful')
"
```

### 2. Source Database Verification

**Check SQLite database**:
```bash
sqlite3 data/spock_local.db ".tables"
# Expected: tickers, ohlcv_data, technical_analysis, stock_details, etf_details

sqlite3 data/spock_local.db "SELECT COUNT(*) FROM ohlcv_data;"
# Record this number for validation
```

**Database statistics**:
```bash
python3 -c "
from modules.db_manager_sqlite import SQLiteDatabaseManager
db = SQLiteDatabaseManager('data/spock_local.db')

tables = ['tickers', 'ohlcv_data', 'technical_analysis', 'stock_details', 'etf_details']
for table in tables:
    try:
        count = db.execute_query(f'SELECT COUNT(*) as count FROM {table}')[0]['count']
        print(f'{table:25s}: {count:,} rows')
    except:
        print(f'{table:25s}: Table not found')
"
```

### 3. Disk Space Check

```bash
# Check available space
df -h ~/spock

# Estimate PostgreSQL size (SQLite size * 1.5)
du -sh data/spock_local.db
```

### 4. Backup Source Database

**Critical: Always backup before migration**

```bash
# Create backup directory
mkdir -p backups/sqlite

# Backup SQLite database
cp data/spock_local.db backups/sqlite/spock_local_$(date +%Y%m%d_%H%M%S).db

# Verify backup
ls -lh backups/sqlite/
```

---

## Migration Workflow

### High-Level Process

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Pre-Migration                                            │
│    ✓ Install PostgreSQL + TimescaleDB                      │
│    ✓ Configure environment                                  │
│    ✓ Backup SQLite database                                │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. Schema Initialization                                    │
│    ✓ Create PostgreSQL database                            │
│    ✓ Enable TimescaleDB extension                          │
│    ✓ Create tables and hypertables                         │
│    ✓ Setup continuous aggregates                           │
│    ✓ Configure compression policies                        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Data Migration                                           │
│    ✓ Migrate tickers (metadata)                            │
│    ✓ Migrate OHLCV data (batch processing)                 │
│    ✓ Migrate technical analysis                            │
│    ✓ Migrate stock/ETF details                             │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Validation                                               │
│    ✓ Row count comparison                                  │
│    ✓ Date coverage verification                            │
│    ✓ Data quality checks                                   │
│    ✓ Performance benchmarks                                │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Post-Migration                                           │
│    ✓ Enable compression                                    │
│    ✓ Setup monitoring (Prometheus + Grafana)               │
│    ✓ Configure automated backups                           │
│    ✓ Update application configuration                      │
└─────────────────────────────────────────────────────────────┘
```

### Estimated Timeline

| Phase | Duration | Complexity |
|-------|----------|------------|
| Pre-Migration | 2-3 hours | Low |
| Schema Initialization | 30 minutes | Low |
| Data Migration | 2-4 hours* | Medium |
| Validation | 1-2 hours | Medium |
| Post-Migration | 2-3 hours | Medium |
| **Total** | **8-12 hours** | **Medium** |

*Migration time depends on data volume (10K-1M+ OHLCV records)

---

## Step-by-Step Migration

### Phase 1: Schema Initialization

#### Initialize PostgreSQL Schema

```bash
# Run schema initialization script
python3 scripts/init_postgres_schema.py

# Expected output:
# ✅ Created table: tickers
# ✅ Created hypertable: ohlcv_data
# ✅ Created table: technical_analysis
# ✅ Created continuous aggregate: ohlcv_monthly
# ✅ Created continuous aggregate: ohlcv_yearly
# ✅ Configured compression policy
# ✅ Schema initialization complete
```

#### Verify Schema

```bash
# Check tables
psql -d quant_platform -c "\dt"

# Check hypertables
psql -d quant_platform -c "
SELECT hypertable_name, hypertable_schema
FROM timescaledb_information.hypertables;
"

# Expected: ohlcv_data
```

#### Verify Continuous Aggregates

```bash
psql -d quant_platform -c "
SELECT view_name, materialization_hypertable_name
FROM timescaledb_information.continuous_aggregates;
"

# Expected: ohlcv_monthly, ohlcv_yearly
```

### Phase 2: Data Migration

#### Option A: Dry Run (Recommended First)

```bash
# Test migration without committing
python3 scripts/migrate_sqlite_to_postgres.py --dry-run

# Expected output:
# [DRY RUN] Would insert 500 tickers
# [DRY RUN] Would insert 250,000 OHLCV records
# Migration completed successfully (dry run)
```

#### Option B: Full Migration (All Tables)

```bash
# Migrate all data
python3 scripts/migrate_sqlite_to_postgres.py \
  --batch-size 10000

# Expected output:
# Migrating tickers...
# ✅ Migrated 500 tickers
#
# Migrating OHLCV data...
# Progress: 10.0% (25,000/250,000) | Rate: 5,000 rows/s
# Progress: 20.0% (50,000/250,000) | Rate: 5,200 rows/s
# ...
# ✅ Migrated 250,000 OHLCV records
#
# ===== MIGRATION SUMMARY =====
# tickers:              Total: 500      | Migrated: 500      | Success: 100%
# ohlcv_data:           Total: 250,000  | Migrated: 250,000  | Success: 100%
# technical_analysis:   Total: 125,000  | Migrated: 125,000  | Success: 100%
```

#### Option C: Partial Migration (Specific Tables)

```bash
# Migrate only tickers and OHLCV
python3 scripts/migrate_sqlite_to_postgres.py \
  --tables tickers,ohlcv_data \
  --batch-size 5000
```

#### Option D: Regional Migration (KR Only)

```bash
# Migrate only Korean market data
python3 scripts/migrate_sqlite_to_postgres.py \
  --region KR \
  --batch-size 10000
```

#### Option E: Incremental Migration (Recent Data)

```bash
# Migrate only data after specific date
python3 scripts/migrate_sqlite_to_postgres.py \
  --start-date 2024-01-01 \
  --batch-size 10000
```

### Phase 3: Validation

#### Step 1: Row Count Validation

```bash
# Validate row counts
python3 scripts/validate_postgres_data.py

# Expected output:
# Validating row counts...
# ✅ tickers: 500 rows (match)
# ✅ ohlcv_data: 250,000 rows (match)
# ✅ technical_analysis: 125,000 rows (match)
```

#### Step 2: Data Quality Checks

```bash
# Comprehensive quality checks
python3 scripts/data_quality_checks.py --comprehensive

# Expected output:
# ✅ No duplicate records found
# ✅ All prices are consistent
# ✅ No significant date gaps
# ⚠️  Volume anomaly: TICKER (KR) - 2024-10-15: 1,000,000 (5.2x avg)
```

#### Step 3: Performance Benchmarks

```bash
# Run performance benchmarks
python3 scripts/benchmark_postgres_performance.py

# Expected output:
# ===== PERFORMANCE BENCHMARK =====
# ✅ 250_days:    45ms  (target: <100ms)
# ✅ 1_year:     320ms  (target: <500ms)
# ✅ 10_years:   850ms  (target: <1000ms)
# ✅ ALL PERFORMANCE TARGETS MET
```

### Phase 4: Post-Migration Configuration

#### Enable Compression

```bash
# Compress data older than 1 year
psql -d quant_platform -c "
SELECT add_compression_policy('ohlcv_data', INTERVAL '365 days');
"

# Manually compress existing old data
psql -d quant_platform -c "
SELECT compress_chunk(i)
FROM show_chunks('ohlcv_data', older_than => INTERVAL '365 days') i;
"

# Verify compression
psql -d quant_platform -c "
SELECT
    hypertable_name,
    compression_status,
    COUNT(*) as chunk_count
FROM timescaledb_information.chunks
WHERE hypertable_schema = 'public'
GROUP BY hypertable_name, compression_status;
"
```

#### Setup Automated Backups

```bash
# Test backup script
./scripts/backup_postgres.sh

# Schedule daily backups (crontab)
crontab -e

# Add this line (daily backup at 2 AM):
0 2 * * * /Users/13ruce/spock/scripts/backup_postgres.sh >> /Users/13ruce/spock/logs/backup.log 2>&1
```

#### Start Monitoring

```bash
# Start Prometheus metrics server
python3 modules/monitoring/postgres_metrics.py --port 8000 --interval 60 &

# Verify metrics endpoint
curl http://localhost:8000/metrics | grep postgres_database_size_bytes

# Import Grafana dashboard
# 1. Open Grafana UI (http://localhost:3000)
# 2. Navigate to Dashboards → Import
# 3. Upload dashboards/postgres_monitoring.json
```

---

## Validation & Testing

### Data Integrity Tests

#### 1. Exact Row Count Match

```sql
-- SQLite
SELECT 'tickers' as table_name, COUNT(*) as count FROM tickers
UNION ALL
SELECT 'ohlcv_data', COUNT(*) FROM ohlcv_data
UNION ALL
SELECT 'technical_analysis', COUNT(*) FROM technical_analysis;

-- PostgreSQL (should match exactly)
SELECT 'tickers' as table_name, COUNT(*) as count FROM tickers
UNION ALL
SELECT 'ohlcv_data', COUNT(*) FROM ohlcv_data
UNION ALL
SELECT 'technical_analysis', COUNT(*) FROM technical_analysis;
```

#### 2. Date Coverage Verification

```sql
-- Verify date ranges match
SELECT
    ticker,
    region,
    MIN(date) as min_date,
    MAX(date) as max_date,
    COUNT(*) as row_count
FROM ohlcv_data
WHERE ticker = '005930' AND region = 'KR'
GROUP BY ticker, region;
```

#### 3. Sample Data Comparison

```bash
# Compare random sample
python3 -c "
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.db_manager_postgres import PostgresDatabaseManager

sqlite_db = SQLiteDatabaseManager('data/spock_local.db')
postgres_db = PostgresDatabaseManager()

# Sample query
query = '''
    SELECT ticker, date, close
    FROM ohlcv_data
    WHERE ticker = '005930' AND region = 'KR'
    ORDER BY date DESC
    LIMIT 10
'''

sqlite_results = sqlite_db.execute_query(query)
postgres_results = postgres_db.execute_query(query)

print('SQLite:', sqlite_results[0])
print('PostgreSQL:', postgres_results[0])
print('Match:', sqlite_results == postgres_results)
"
```

### Performance Validation

#### Query Performance Tests

```bash
# Run comprehensive benchmarks
python3 scripts/benchmark_postgres_performance.py --comprehensive

# Verify targets:
# ✅ 250 days: <100ms
# ✅ 1 year: <500ms
# ✅ 10 years: <1s
```

#### Index Effectiveness

```sql
-- Check index usage
SELECT
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY idx_scan DESC;

-- Expected: High idx_scan for primary keys and date indexes
```

---

## Post-Migration Tasks

### 1. Update Application Configuration

**Update database connections in code**:

```python
# Before (SQLite)
from modules.db_manager_sqlite import SQLiteDatabaseManager
db = SQLiteDatabaseManager('data/spock_local.db')

# After (PostgreSQL)
from modules.db_manager_postgres import PostgresDatabaseManager
db = PostgresDatabaseManager()
```

### 2. Optimize PostgreSQL

```bash
# Run ANALYZE to update statistics
psql -d quant_platform -c "ANALYZE;"

# Vacuum to reclaim space
psql -d quant_platform -c "VACUUM ANALYZE;"
```

### 3. Monitor Initial Performance

```bash
# Start metrics collection
python3 modules/monitoring/postgres_metrics.py --port 8000 &

# Monitor for 24 hours
# Check Grafana dashboard for anomalies
```

### 4. Document Migration

```bash
# Create migration report
cat > logs/migration_report_$(date +%Y%m%d).txt <<EOF
Migration Date: $(date)
Database: quant_platform
Source: SQLite (data/spock_local.db)
Target: PostgreSQL 17 + TimescaleDB

Tables Migrated:
- tickers: [row count]
- ohlcv_data: [row count]
- technical_analysis: [row count]

Validation: ✅ Passed
Performance: ✅ Targets Met
Duration: [hours]
EOF
```

---

## Rollback Procedures

### If Migration Fails

#### 1. Immediate Rollback

```bash
# Stop migration script (Ctrl+C)

# Drop PostgreSQL database
psql -c "DROP DATABASE IF EXISTS quant_platform;"

# Recreate clean database
psql -c "CREATE DATABASE quant_platform;"
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"

# Re-run schema initialization
python3 scripts/init_postgres_schema.py

# Retry migration
python3 scripts/migrate_sqlite_to_postgres.py --dry-run
```

#### 2. Restore from Backup

```bash
# If PostgreSQL data is corrupted
./scripts/restore_postgres.sh --latest

# Or restore specific backup
./scripts/restore_postgres.sh --file backups/postgres/quant_platform_20251027_120000.sql.gz
```

#### 3. Continue Using SQLite

**SQLite is NOT deleted during migration**, so you can continue using it:

```python
# Application still works with SQLite
from modules.db_manager_sqlite import SQLiteDatabaseManager
db = SQLiteDatabaseManager('data/spock_local.db')
```

---

## Troubleshooting

### Common Issues

#### 1. "Database connection refused"

**Symptoms**:
```
psycopg2.OperationalError: could not connect to server
```

**Solutions**:
```bash
# Check PostgreSQL is running
brew services list | grep postgresql
# or
sudo systemctl status postgresql

# Start PostgreSQL
brew services start postgresql@17
# or
sudo systemctl start postgresql

# Verify port
psql -c "SHOW port;"
```

#### 2. "TimescaleDB extension not found"

**Symptoms**:
```
ERROR: extension "timescaledb" does not exist
```

**Solutions**:
```bash
# Install TimescaleDB
brew install timescaledb

# Run tune script
timescaledb-tune --quiet --yes

# Restart PostgreSQL
brew services restart postgresql@17

# Enable extension
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

#### 3. "Out of disk space"

**Symptoms**:
```
ERROR: could not write to file: No space left on device
```

**Solutions**:
```bash
# Check disk space
df -h

# Clean up old logs
rm logs/*.log.old

# Clean up old backups
find backups/postgres -name "*.sql.gz" -mtime +30 -delete

# Compress existing data
psql -d quant_platform -c "
SELECT compress_chunk(i)
FROM show_chunks('ohlcv_data') i;
"
```

#### 4. "Migration very slow"

**Symptoms**:
- Migration running >4 hours
- Rate <1000 rows/sec

**Solutions**:
```bash
# Increase batch size
python3 scripts/migrate_sqlite_to_postgres.py --batch-size 50000

# Disable indexes temporarily (advanced)
psql -d quant_platform -c "
DROP INDEX IF EXISTS ohlcv_data_ticker_region_date_idx;
"

# Re-run migration

# Recreate indexes
python3 scripts/init_postgres_schema.py
```

#### 5. "Row count mismatch"

**Symptoms**:
```
❌ ohlcv_data: SQLite=250,000, PostgreSQL=248,500
```

**Solutions**:
```bash
# Check for errors in migration log
grep ERROR logs/*_migration.log

# Identify missing data
python3 -c "
from modules.db_manager_sqlite import SQLiteDatabaseManager
from modules.db_manager_postgres import PostgresDatabaseManager

sqlite_db = SQLiteDatabaseManager('data/spock_local.db')
postgres_db = PostgresDatabaseManager()

# Find missing tickers
sqlite_tickers = set([r['ticker'] for r in sqlite_db.execute_query('SELECT DISTINCT ticker FROM ohlcv_data')])
postgres_tickers = set([r['ticker'] for r in postgres_db.execute_query('SELECT DISTINCT ticker FROM ohlcv_data')])

missing = sqlite_tickers - postgres_tickers
print('Missing tickers:', missing)
"

# Re-run migration for specific ticker
python3 scripts/migrate_sqlite_to_postgres.py --ticker [ticker] --region [region]
```

---

## Performance Optimization

### Query Optimization

#### 1. Create Additional Indexes

```sql
-- Index for common query patterns
CREATE INDEX IF NOT EXISTS ohlcv_data_close_idx
ON ohlcv_data (close);

CREATE INDEX IF NOT EXISTS ohlcv_data_volume_idx
ON ohlcv_data (volume);

-- Composite index for backtest queries
CREATE INDEX IF NOT EXISTS ohlcv_data_ticker_date_idx
ON ohlcv_data (ticker, date DESC);
```

#### 2. Update Statistics Regularly

```bash
# Add to crontab (daily at 3 AM)
0 3 * * * psql -d quant_platform -c "ANALYZE;" >> /Users/13ruce/spock/logs/maintenance.log 2>&1
```

#### 3. Configure PostgreSQL Settings

```bash
# Edit postgresql.conf
# Locations:
# macOS: /opt/homebrew/var/postgresql@17/postgresql.conf
# Linux: /etc/postgresql/17/main/postgresql.conf

# Recommended settings for 16GB RAM system:
shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 1GB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 32MB
max_worker_processes = 8
max_parallel_workers_per_gather = 4
max_parallel_workers = 8

# Restart PostgreSQL
brew services restart postgresql@17
```

### Storage Optimization

#### Enable Compression

```sql
-- Check compression status
SELECT
    hypertable_name,
    compression_status,
    COUNT(*) as chunks,
    pg_size_pretty(SUM(total_bytes)) as total_size
FROM timescaledb_information.chunks
WHERE hypertable_schema = 'public'
GROUP BY hypertable_name, compression_status;

-- Compress all eligible chunks
SELECT compress_chunk(i)
FROM show_chunks('ohlcv_data', older_than => INTERVAL '365 days') i;
```

#### Monitor Compression Savings

```sql
SELECT
    hypertable_name,
    pg_size_pretty(before_compression_total_bytes) as uncompressed,
    pg_size_pretty(after_compression_total_bytes) as compressed,
    ROUND((1 - after_compression_total_bytes::float / before_compression_total_bytes) * 100, 1) as savings_pct
FROM timescaledb_information.compression_settings
WHERE hypertable_schema = 'public';
```

---

## Success Criteria

### Migration Success Checklist

- [ ] All tables migrated with 100% row count match
- [ ] Date coverage verified (min/max dates match)
- [ ] Data quality checks passed (no duplicates, no inconsistencies)
- [ ] Performance benchmarks met (<100ms for 250 days, <1s for 10 years)
- [ ] TimescaleDB features enabled (hypertables, compression, continuous aggregates)
- [ ] Monitoring operational (Prometheus + Grafana)
- [ ] Automated backups configured and tested
- [ ] Rollback procedure documented and tested

### Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| 250-day OHLCV query | <100ms | ☐ |
| 1-year OHLCV query | <500ms | ☐ |
| 10-year OHLCV query | <1s | ☐ |
| Index hit rate | >90% | ☐ |
| Compression ratio | >5x | ☐ |
| Data freshness | <7 days | ☐ |
| Backup success rate | 100% | ☐ |

---

## Next Steps

After successful migration:

1. **Read**: [POSTGRES_OPERATIONS.md](POSTGRES_OPERATIONS.md) - Daily operations guide
2. **Configure**: Application code to use PostgreSQL
3. **Monitor**: Grafana dashboard for 7 days
4. **Optimize**: Based on actual query patterns
5. **Document**: Any custom configurations or issues encountered

---

**Migration Guide Version**: 1.0
**Last Updated**: 2025-10-27
**Status**: Phase 4 Complete
