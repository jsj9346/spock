# PostgreSQL + TimescaleDB Setup Guide
## Quant Investment Platform - Database Installation

**Status**: ✅ Complete
**Date**: 2025-10-20
**PostgreSQL Version**: 17.6 (Homebrew)
**TimescaleDB Version**: 2.22.1

---

## Installation Summary

This guide documents the successful installation and configuration of PostgreSQL 17 + TimescaleDB 2.22.1 for the Quant Investment Platform.

---

## Environment Information

**System**: macOS Sonoma 14.x (Apple Silicon M1/M2/M3)
**Package Manager**: Homebrew
**Database**: quant_platform
**Extension**: TimescaleDB 2.22.1
**Python Connector**: psycopg2 2.9.9

---

## Installation Steps (macOS)

### Step 1: Install PostgreSQL 17

```bash
# Add TimescaleDB tap
brew tap timescale/tap

# Install TimescaleDB (includes PostgreSQL 17 as dependency)
brew install timescaledb

# Verify installation
brew list timescaledb
brew list postgresql@17
```

**Result**:
- PostgreSQL 17.6 installed to `/opt/homebrew/Cellar/postgresql@17/17.6`
- TimescaleDB 2.22.1 installed to `/opt/homebrew/Cellar/timescaledb/2.22.1`

### Step 2: Configure TimescaleDB

```bash
# Move TimescaleDB files into place
timescaledb_move.sh

# Run auto-tuning (optimizes for your system)
timescaledb-tune --quiet --yes --pg-config=/opt/homebrew/opt/postgresql@17/bin/pg_config
```

**Auto-Tuning Results** (16 GB RAM, 8 CPUs):
```ini
shared_preload_libraries = 'timescaledb'
shared_buffers = 4GB
effective_cache_size = 12GB
maintenance_work_mem = 2047MB
work_mem = 5242kB
timescaledb.max_background_workers = 16
max_worker_processes = 27
max_parallel_workers_per_gather = 4
max_parallel_workers = 8
wal_buffers = 16MB
min_wal_size = 512MB
checkpoint_completion_target = 0.9
max_locks_per_transaction = 512
autovacuum_max_workers = 10
```

### Step 3: Enable TimescaleDB Extension

```bash
# Add shared_preload_libraries to postgresql.conf
echo "shared_preload_libraries = 'timescaledb'" >> /opt/homebrew/var/postgresql@17/postgresql.conf

# Stop old PostgreSQL (if running)
brew services stop postgresql@14

# Start PostgreSQL 17
brew services start postgresql@17

# Create database
createdb quant_platform

# Enable TimescaleDB extension
psql -d quant_platform -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
```

### Step 4: Verify Installation

```bash
# Check PostgreSQL version
psql --version
# Expected: psql (PostgreSQL) 17.6 (Homebrew)

# Check TimescaleDB extension
psql -d quant_platform -c "SELECT extname, extversion FROM pg_extension WHERE extname='timescaledb';"
# Expected: timescaledb | 2.22.1
```

### Step 5: Python Connection Test

```bash
# Install psycopg2 (if not already installed)
pip3 install psycopg2-binary==2.9.7

# Test connection
python3 -c "
import psycopg2
conn = psycopg2.connect(
    host='localhost',
    port=5432,
    database='quant_platform',
    user='$(whoami)'
)
cursor = conn.cursor()
cursor.execute('SELECT version();')
print('✅ PostgreSQL Connection Success!')
print(cursor.fetchone()[0][:50])
cursor.close()
conn.close()
"
```

**Expected Output**:
```
✅ PostgreSQL Connection Success!
PostgreSQL 17.6 (Homebrew) on aarch64-apple-darwin...
```

---

## Configuration Files

### PostgreSQL Configuration
**Location**: `/opt/homebrew/var/postgresql@17/postgresql.conf`

**Key Settings**:
```ini
# TimescaleDB
shared_preload_libraries = 'timescaledb'
shared_buffers = 4GB
effective_cache_size = 12GB
work_mem = 5242kB

# Performance
max_worker_processes = 27
max_parallel_workers = 8
checkpoint_completion_target = 0.9

# TimescaleDB Workers
timescaledb.max_background_workers = 16
```

### Environment Variables (.env)
**Location**: `/Users/13ruce/spock/.env`

```ini
# PostgreSQL + TimescaleDB Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=quant_platform
POSTGRES_USER=<your-username>
POSTGRES_PASSWORD=

# Legacy SQLite (for migration)
SQLITE_DB_PATH=data/spock_local.db
```

---

## Service Management

### Start/Stop/Restart PostgreSQL

```bash
# Start
brew services start postgresql@17

# Stop
brew services stop postgresql@17

# Restart
brew services restart postgresql@17

# Check status
brew services list | grep postgres
```

### PostgreSQL CLI

```bash
# Connect to database
psql -d quant_platform

# Common commands
\l              # List databases
\dt             # List tables
\d+ table_name  # Describe table
\q              # Quit
```

---

## Troubleshooting

### Issue 1: TimescaleDB Extension Not Loaded

**Error**:
```
FATAL: extension "timescaledb" must be preloaded
```

**Solution**:
```bash
# Add to postgresql.conf
echo "shared_preload_libraries = 'timescaledb'" >> /opt/homebrew/var/postgresql@17/postgresql.conf

# Restart PostgreSQL
brew services restart postgresql@17
```

### Issue 2: Connection Refused

**Error**:
```
psql: could not connect to server: Connection refused
```

**Solution**:
```bash
# Check if PostgreSQL is running
brew services list | grep postgres

# If not running
brew services start postgresql@17

# Check logs
tail -f /opt/homebrew/var/log/postgresql@17.log
```

### Issue 3: Port Conflict

**Error**:
```
FATAL: lock file "postmaster.pid" already exists
```

**Solution**:
```bash
# Check what's running on port 5432
lsof -i :5432

# Kill old PostgreSQL process (if safe)
pkill -f postgres

# Restart PostgreSQL
brew services restart postgresql@17
```

---

## Next Steps

### Day 2: Schema Implementation
- Create `scripts/init_postgres_schema.py`
- Implement core tables (tickers, ohlcv_data, factor_scores)
- Create hypertables and continuous aggregates
- Setup compression policies

### Day 3: Database Manager
- Implement `modules/db_manager_postgres.py`
- Connection pooling with psycopg2.pool
- CRUD methods compatible with SQLiteDatabaseManager
- Bulk insert optimization

### Day 4: Data Migration
- Implement `scripts/migrate_from_sqlite.py`
- Migrate tickers, stock_details, etf_details
- Migrate ohlcv_data (2.5M rows)
- Verify data integrity

### Day 5: Testing & Validation
- Row count verification
- Query performance benchmarks
- Compression effectiveness testing
- Integration tests

---

## Performance Benchmarks (Expected)

| Operation | Target | Notes |
|-----------|--------|-------|
| 10-year OHLCV query | <1 second | With hypertable indexing |
| Bulk insert 10K rows | <1 second | Using COPY command |
| Monthly aggregate query | <10ms | With continuous aggregates |
| Compression ratio | 10x | TimescaleDB compression |
| Connection pool | 5-20 connections | ThreadedConnectionPool |

---

## References

- [PostgreSQL Documentation](https://www.postgresql.org/docs/17/)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [psycopg2 Documentation](https://www.psycopg.org/docs/)
- [Phase 1 Migration Design](PHASE1_DATABASE_MIGRATION_DESIGN.md)

---

## Appendix A: Installation Verification Checklist

- [x] PostgreSQL 17.6 installed
- [x] TimescaleDB 2.22.1 installed
- [x] PostgreSQL service running
- [x] quant_platform database created
- [x] TimescaleDB extension enabled
- [x] psycopg2 connection successful
- [x] Configuration files updated
- [x] .env file configured

**Status**: ✅ All checks passed

---

## Appendix B: System Resources

**Memory Allocation**:
- shared_buffers: 4GB (25% of 16GB RAM)
- effective_cache_size: 12GB (75% of 16GB RAM)
- work_mem: 5.2MB per connection

**CPU Allocation**:
- max_worker_processes: 27
- max_parallel_workers: 8
- timescaledb.max_background_workers: 16

**Disk I/O**:
- wal_buffers: 16MB
- min_wal_size: 512MB
- checkpoint_completion_target: 0.9 (smooth checkpoints)

---

**Document Version**: 1.0
**Last Updated**: 2025-10-20 11:15 KST
**Verified By**: Quant Platform Development Team
