# PostgreSQL + TimescaleDB Migration Runbook

**Quant Investment Platform - Database Migration Guide**

**Version**: 1.0 (Phase 1 Complete)
**Created**: 2025-10-21
**Status**: Production-Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Fresh Installation](#fresh-installation)
4. [Data Migration](#data-migration)
5. [Data Validation](#data-validation)
6. [Performance Verification](#performance-verification)
7. [Rollback Procedures](#rollback-procedures)
8. [Troubleshooting](#troubleshooting)
9. [Post-Migration Checklist](#post-migration-checklist)

---

## Overview

### Migration Scope

**Source**: SQLite (`data/spock_local.db`)
**Target**: PostgreSQL 15+ + TimescaleDB 2.11+ (`quant_platform` database)

**Tables Migrated** (7 core tables):
1. tickers (18,661 rows)
2. ohlcv_data (926,325 rows) → TimescaleDB hypertable
3. stock_details (17,606 rows)
4. etf_details (1,028 rows)
5. etf_holdings (3 rows)
6. ticker_fundamentals (47 rows with region enhancement)
7. technical_analysis (0 rows - schema only)

**Additional Tables Created** (8 tables):
- global_market_indices, exchange_rate_history (Phase 1 infrastructure)
- strategies, backtest_results, portfolio_holdings, portfolio_transactions,
  walk_forward_results, optimization_history (Quant Platform)

**Estimated Time**: 2-3 hours (first-time), 30 minutes (experienced)

---

## Prerequisites

### System Requirements

**Operating System**:
- macOS 11+ (Apple Silicon or Intel)
- Ubuntu 20.04+ / Debian 11+
- Windows 10+ (WSL2 recommended)

**Hardware Recommendations**:
- CPU: 4+ cores
- RAM: 8GB minimum, 16GB recommended
- Disk: 10GB free space (20GB+ for production)

### Software Dependencies

**Required**:
```bash
# PostgreSQL 15+
postgresql@15 (or later)

# TimescaleDB 2.11+
timescaledb

# Python 3.11+
python3.11 (or later)

# Python Packages (from requirements_quant.txt)
psycopg2-binary==2.9.7
pandas==2.0.3
python-dotenv==1.0.0
```

**Installation (macOS)**:
```bash
# Install PostgreSQL 15 + TimescaleDB
brew install postgresql@15 timescaledb

# Configure TimescaleDB
timescaledb-tune --quiet --yes

# Start PostgreSQL
brew services start postgresql@15

# Install Python dependencies
pip3 install -r requirements_quant.txt
```

**Installation (Ubuntu/Debian)**:
```bash
# Add PostgreSQL repository
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -

# Install PostgreSQL
sudo apt-get update
sudo apt-get install -y postgresql-15 postgresql-contrib-15

# Add TimescaleDB repository
sudo add-apt-repository ppa:timescale/timescaledb-ppa
sudo apt-get update

# Install TimescaleDB
sudo apt-get install -y timescaledb-2-postgresql-15

# Configure TimescaleDB
sudo timescaledb-tune --quiet --yes

# Start PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Install Python dependencies
pip3 install -r requirements_quant.txt
```

### Environment Configuration

**Create `.env` file** (if not exists):
```bash
# PostgreSQL Connection
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=quant_platform
POSTGRES_USER=<your_username>
POSTGRES_PASSWORD=<your_password>

# API Keys (if needed)
KIS_APP_KEY=<your_kis_app_key>
KIS_APP_SECRET=<your_kis_app_secret>
```

---

## Fresh Installation

### Step 1: Create Database

**Command**:
```bash
# Create database
createdb quant_platform

# Verify creation
psql -l | grep quant_platform
```

**Expected Output**:
```
 quant_platform | <username> | UTF8     | en_US.UTF-8 | en_US.UTF-8 |
```

### Step 2: Enable TimescaleDB Extension

**Command**:
```bash
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

**Verification**:
```bash
psql -d quant_platform -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';"
```

**Expected Output**:
```
   extname   | extversion
-------------+------------
 timescaledb | 2.11.2
(1 row)
```

### Step 3: Initialize Schema

**Command**:
```bash
# Run Phase 1 schema initialization scripts
psql -d quant_platform -f scripts/init_postgres_schema.sql
psql -d quant_platform -f scripts/add_global_indices_and_rates.sql
psql -d quant_platform -f scripts/add_quant_platform_tables.sql
```

**Verification**:
```bash
psql -d quant_platform -c "\dt"
```

**Expected Output**: 19 tables listed

### Step 4: Create TimescaleDB Hypertables

**Command**:
```bash
psql -d quant_platform -f scripts/create_timescaledb_hypertables.sql
```

**Verification**:
```bash
psql -d quant_platform -c "SELECT hypertable_name, num_chunks FROM timescaledb_information.hypertables;"
```

**Expected Output**:
```
 hypertable_name | num_chunks
-----------------+------------
 ohlcv_data      |          0
 factor_scores   |          0
(2 rows)
```

### Step 5: Create Continuous Aggregates

**Command**:
```bash
psql -d quant_platform -f scripts/create_continuous_aggregates.sql
```

**Verification**:
```bash
psql -d quant_platform -c "SELECT view_name FROM timescaledb_information.continuous_aggregates;"
```

**Expected Output**:
```
    view_name
-----------------
 ohlcv_monthly
 ohlcv_quarterly
 ohlcv_yearly
(3 rows)
```

### Step 6: Setup Compression Policy

**Command**:
```bash
psql -d quant_platform -f scripts/setup_compression_policy.sql
```

**Verification**:
```bash
psql -d quant_platform -c "SELECT hypertable_name, COUNT(*) as policy_count FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression' GROUP BY hypertable_name;"
```

**Expected Output**: 5 compression policies configured

---

## Data Migration

### Step 1: Verify Source Database

**Check SQLite database exists**:
```bash
ls -lh data/spock_local.db
```

**Check row counts**:
```bash
sqlite3 data/spock_local.db "
SELECT 'tickers' as table_name, COUNT(*) FROM tickers
UNION ALL SELECT 'ohlcv_data', COUNT(*) FROM ohlcv_data
UNION ALL SELECT 'stock_details', COUNT(*) FROM stock_details;"
```

### Step 2: Run Migration Script

**Command**:
```bash
python3 scripts/migrate_from_sqlite.py --source data/spock_local.db --dry-run
```

**Review dry-run output**, then execute:
```bash
python3 scripts/migrate_from_sqlite.py --source data/spock_local.db
```

**Expected Duration**: 2-5 minutes for ~1M rows

**Progress Indicators**:
```
Migrating tickers... 18661 rows ✅
Migrating ohlcv_data... 926325 rows ✅
Migrating stock_details... 17606 rows ✅
Migrating etf_details... 1028 rows ✅
Migration complete: 963620 total rows
```

### Step 3: Verify Migration

**Row count comparison**:
```bash
python3 scripts/validate_phase1_data.py --verbose
```

**Expected Output**:
```
Total Checks: 42
✅ Passed: 35 (83.3%)
⚠️ Warnings: 1 (etf_details: -1 row acceptable)
❌ Failed: 6 (all expected - see validation report)
```

**Critical Checks** (Must Pass):
- ✅ Data Integrity: 9/9 checks (100%)
- ✅ TimescaleDB Health: 10/10 checks (100%)
- ✅ Performance: 1/1 check (100%)

---

## Data Validation

### Validation Categories

**1. Row Count Comparison** (SQLite vs PostgreSQL):
```bash
psql -d quant_platform -c "
SELECT 'tickers' as table_name, COUNT(*) FROM tickers
UNION ALL SELECT 'ohlcv_data', COUNT(*) FROM ohlcv_data
UNION ALL SELECT 'stock_details', COUNT(*) FROM stock_details;"
```

**2. Data Integrity Checks**:
```bash
psql -d quant_platform -c "
-- NULL checks
SELECT
    COUNT(*) FILTER (WHERE ticker IS NULL) as null_ticker,
    COUNT(*) FILTER (WHERE close IS NULL) as null_close
FROM ohlcv_data;

-- Duplicate checks
SELECT COUNT(*) as dup_count
FROM (
    SELECT ticker, region, date, COUNT(*) as cnt
    FROM ohlcv_data
    GROUP BY ticker, region, date
    HAVING COUNT(*) > 1
) dups;
"
```

**Expected**: 0 NULL values, 0 duplicates

**3. TimescaleDB Health**:
```bash
psql -d quant_platform -c "
SELECT hypertable_name, num_chunks, compression_enabled
FROM timescaledb_information.hypertables;"
```

**Expected**: ohlcv_data with chunks, compression enabled

### Automated Validation

**Run comprehensive validation**:
```bash
python3 scripts/validate_phase1_data.py --report /tmp/validation_report.txt
```

**Review report**:
```bash
cat /tmp/validation_report.txt
```

---

## Performance Verification

### Run Benchmark Suite

**Command**:
```bash
python3 scripts/benchmark_queries.py
```

**Performance Targets**:
- OHLCV 10-year query: <1000ms
- Continuous aggregate query: <100ms
- Factor score query: <500ms
- Backtest query: <200ms

**Expected Results** (Phase 1 achieved):
```
Total Benchmarks: 13
✅ Passed: 13 (100%)
Performance: All queries <100ms (Excellent)
```

### Performance Tuning

**Run performance analysis**:
```bash
psql -d quant_platform -f scripts/performance_tuning.sql
```

**Key Metrics**:
- Cache hit ratio: >90% (target), 99.65% (achieved)
- Index usage: All indexes actively used
- Connection pool: 10-30 connections optimal

---

## Rollback Procedures

### Scenario 1: Migration Failure (Incomplete)

**1. Drop PostgreSQL database**:
```bash
dropdb quant_platform
```

**2. Recreate and retry**:
```bash
createdb quant_platform
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
# Re-run fresh installation steps
```

### Scenario 2: Data Corruption Detected

**1. Stop all connections**:
```bash
psql -d postgres -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'quant_platform' AND pid <> pg_backend_pid();"
```

**2. Restore from backup** (if available):
```bash
pg_restore -d quant_platform /path/to/backup.dump
```

**3. Or re-migrate from SQLite**:
```bash
psql -d quant_platform -c "TRUNCATE TABLE ohlcv_data CASCADE;"
python3 scripts/migrate_from_sqlite.py --source data/spock_local.db
```

### Scenario 3: Revert to SQLite

**1. Verify SQLite database intact**:
```bash
sqlite3 data/spock_local.db "SELECT COUNT(*) FROM ohlcv_data;"
```

**2. Update application configuration**:
```python
# Change db_manager import
from modules.db_manager_sqlite import SQLiteDatabaseManager as DatabaseManager
```

**3. PostgreSQL database can remain for reference**

---

## Troubleshooting

### Issue 1: TimescaleDB Extension Not Found

**Error**:
```
ERROR: could not open extension control file "timescaledb.control"
```

**Solution**:
```bash
# macOS
brew reinstall timescaledb

# Ubuntu/Debian
sudo apt-get install --reinstall timescaledb-2-postgresql-15

# Restart PostgreSQL
brew services restart postgresql@15  # macOS
sudo systemctl restart postgresql    # Linux
```

### Issue 2: Connection Pool Exhaustion

**Error**:
```
FATAL: sorry, too many clients already
```

**Solution**:
```bash
# Check current connections
psql -d quant_platform -c "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = 'quant_platform';"

# Increase max_connections in postgresql.conf
sudo nano /opt/homebrew/var/postgresql@15/postgresql.conf  # macOS
# Set: max_connections = 100

# Restart PostgreSQL
brew services restart postgresql@15
```

### Issue 3: Slow Migration Performance

**Symptoms**: Migration taking >10 minutes

**Solution**:
```bash
# Disable indexes during migration
psql -d quant_platform -c "DROP INDEX IF EXISTS idx_ohlcv_ticker_region_timeframe_date;"

# Run migration
python3 scripts/migrate_from_sqlite.py --source data/spock_local.db

# Rebuild indexes
psql -d quant_platform -c "CREATE INDEX idx_ohlcv_ticker_region_timeframe_date ON ohlcv_data(ticker, region, timeframe, date DESC);"
psql -d quant_platform -c "ANALYZE ohlcv_data;"
```

### Issue 4: Hypertable Creation Fails

**Error**:
```
ERROR: cannot create a unique index without the column "date"
```

**Solution**:
Hypertables require partition key in all unique indexes. Update schema:
```sql
-- Change PRIMARY KEY to include partition key (date)
ALTER TABLE ohlcv_data DROP CONSTRAINT ohlcv_data_pkey;
ALTER TABLE ohlcv_data ADD PRIMARY KEY (ticker, region, date, timeframe);

-- Now create hypertable
SELECT create_hypertable('ohlcv_data', 'date', chunk_time_interval => INTERVAL '1 month');
```

### Issue 5: Compression Policy Not Working

**Error**: Chunks not being compressed

**Solution**:
```bash
# Check compression policy
psql -d quant_platform -c "SELECT * FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression';"

# Manually run compression (for testing)
psql -d quant_platform -c "CALL run_job((SELECT job_id FROM timescaledb_information.jobs WHERE proc_name = 'policy_compression' LIMIT 1));"

# Verify compression
psql -d quant_platform -c "SELECT * FROM timescaledb_information.chunks WHERE is_compressed = TRUE;"
```

**Note**: Compression only applies to chunks older than compression policy threshold (365 days by default)

---

## Post-Migration Checklist

### Data Validation
- [ ] All tables created (19 total)
- [ ] Row counts match (tickers: 18,661, ohlcv_data: 926,325, etc.)
- [ ] No NULL values in critical columns
- [ ] No duplicate records
- [ ] Foreign key relationships intact

### TimescaleDB Configuration
- [ ] Hypertables created (ohlcv_data, factor_scores)
- [ ] Continuous aggregates created (ohlcv_monthly, ohlcv_quarterly, ohlcv_yearly)
- [ ] Compression policies enabled (5 policies)
- [ ] Chunks partitioned correctly (monthly intervals)

### Performance Verification
- [ ] Benchmark suite executed (100% pass rate expected)
- [ ] Cache hit ratio >90% (99.65% achieved)
- [ ] All queries <1s (Phase 1 achieved <100ms)
- [ ] Connection pool configured (10-30 connections)

### Application Integration
- [ ] Update `db_manager_postgres.py` connection settings
- [ ] Test data collection scripts (KIS API, Polygon.io)
- [ ] Verify backtesting engine works with PostgreSQL
- [ ] Test Streamlit dashboard connectivity

### Documentation
- [ ] Review Database Schema Diagram
- [ ] Keep Migration Runbook updated
- [ ] Document any custom configurations
- [ ] Save validation reports for reference

### Backup Strategy
- [ ] Setup automated backups (pg_dump daily)
- [ ] Test backup restoration procedure
- [ ] Document backup schedule and retention policy

---

## Quick Reference

### Common Commands

**Check database status**:
```bash
psql -d quant_platform -c "\dt"
psql -d quant_platform -c "SELECT COUNT(*) FROM ohlcv_data;"
```

**View TimescaleDB info**:
```bash
psql -d quant_platform -c "SELECT * FROM timescaledb_information.hypertables;"
psql -d quant_platform -c "SELECT * FROM timescaledb_information.chunks ORDER BY range_start DESC LIMIT 5;"
```

**Performance check**:
```bash
psql -d quant_platform -f scripts/performance_tuning.sql
python3 scripts/benchmark_queries.py
```

**Validation check**:
```bash
python3 scripts/validate_phase1_data.py --verbose
```

### Emergency Contacts

**PostgreSQL Issues**:
- Official Docs: https://www.postgresql.org/docs/15/
- Community: https://www.postgresql.org/community/

**TimescaleDB Issues**:
- Official Docs: https://docs.timescale.com/
- GitHub: https://github.com/timescale/timescaledb

---

## References

- **Database Schema Diagram**: docs/DATABASE_SCHEMA_DIAGRAM.md
- **Performance Tuning Guide**: docs/PERFORMANCE_TUNING_GUIDE.md
- **Phase 1 Implementation Plan**: docs/PHASE1_IMPLEMENTATION_PLAN.md
- **Validation Reports**: /tmp/task6_validation_report.txt

---

**Document Status**: ✅ Complete
**Last Updated**: 2025-10-21
**Next Review**: 2025-11-21 (monthly)
**Maintainer**: Quant Platform Development Team
