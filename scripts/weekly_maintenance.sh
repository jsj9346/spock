#!/bin/bash
# weekly_maintenance.sh - Weekly Maintenance Script
# Schedule: Every Sunday at 2:00 AM
# Add to crontab: 0 2 * * 0 /Users/13ruce/spock/scripts/weekly_maintenance.sh

echo "======================================================================="
echo "Spock Trading System - Weekly Maintenance"
echo "Started: $(date)"
echo "======================================================================="

# Change to project directory
cd /Users/13ruce/spock

# 1. Stop services
echo -e "\n1. Stopping services..."
pkill -f "python3.*spock" && echo "✅ Services stopped" || echo "⚠️  No services running"

# 2. Database maintenance
echo -e "\n2. Database maintenance..."
echo "   - Analyzing database..."
sqlite3 data/spock_local.db "ANALYZE;" && echo "   ✅ Analysis complete"

echo "   - Rebuilding indexes..."
sqlite3 data/spock_local.db "REINDEX;" && echo "   ✅ Indexes rebuilt"

echo "   - Vacuuming database..."
DB_SIZE_BEFORE=$(du -h data/spock_local.db | cut -f1)
sqlite3 data/spock_local.db "VACUUM;" && echo "   ✅ Vacuum complete"
DB_SIZE_AFTER=$(du -h data/spock_local.db | cut -f1)
echo "   Database size: $DB_SIZE_BEFORE → $DB_SIZE_AFTER"

# 3. Clean old data (250-day retention)
echo -e "\n3. Cleaning old data (250-day retention)..."
python3 -c "from modules.db_manager_sqlite import SQLiteDatabaseManager; \
db = SQLiteDatabaseManager(); \
deleted = db.cleanup_old_ohlcv_data(retention_days=250); \
print(f'   ✅ Deleted {deleted:,} old rows')" 2>&1

# 4. Clean old logs and reports
echo -e "\n4. Cleaning old files..."
LOGS_DELETED=$(find logs/ -name "*.log" -mtime +7 -delete -print | wc -l)
echo "   ✅ Deleted $LOGS_DELETED old log files"

METRICS_DELETED=$(find metrics_reports/ -name "metrics_*.json" -mtime +7 -delete -print | wc -l)
echo "   ✅ Deleted $METRICS_DELETED old metric files"

ALERTS_DELETED=$(find alert_logs/ -name "alerts_*.json" -mtime +7 -delete -print | wc -l)
echo "   ✅ Deleted $ALERTS_DELETED old alert files"

VALIDATION_DELETED=$(find validation_reports/ -name "*.json" -mtime +30 -delete -print | wc -l)
echo "   ✅ Deleted $VALIDATION_DELETED old validation reports"

BACKUPS_DELETED=$(find data/backups/ -name "*.tar.gz" -mtime +7 -delete -print | wc -l)
echo "   ✅ Deleted $BACKUPS_DELETED old backup files"

# 5. Backup database
echo -e "\n5. Creating database backup..."
BACKUP_FILE="data/backups/spock_db_$(date +%Y%m%d).tar.gz"
tar -czf "$BACKUP_FILE" data/spock_local.db
if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "   ✅ Backup created: $BACKUP_FILE ($BACKUP_SIZE)"
else
    echo "   ❌ Backup failed"
fi

# 6. Performance benchmark
echo -e "\n6. Running performance benchmark..."
python3 scripts/benchmark_performance.py > /dev/null 2>&1
if [ $? -eq 0 ]; then
    LATEST_BENCHMARK=$(ls -t benchmark_reports/performance_*.json | head -1)
    echo "   ✅ Benchmark complete: $LATEST_BENCHMARK"
else
    echo "   ⚠️  Benchmark failed"
fi

# 7. Data quality check
echo -e "\n7. Running data quality validation..."
python3 scripts/validate_data_quality.py --output validation_reports/weekly_$(date +%Y%m%d).json > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Validation complete"
else
    echo "   ⚠️  Validation failed"
fi

# 8. System health check
echo -e "\n8. System health check..."
python3 -c "from modules.metrics_collector import MetricsCollector; \
collector = MetricsCollector(); \
summary = collector.get_metrics_summary(); \
status = summary['overall_status']; \
score = summary['overall_health_score']; \
print(f'   Status: {status.upper()} ({score}/100)'); \
if summary['critical_alerts']: \
    print(f'   🚨 {len(summary[\"critical_alerts\"])} critical alerts'); \
if summary['warnings']: \
    print(f'   ⚠️  {len(summary[\"warnings\"])} warnings')" 2>&1

# 9. Disk space check
echo -e "\n9. Disk space check..."
df -h | grep -E '/Users/13ruce' | awk '{print "   Disk usage: "$5" ("$3"/"$2")"}'

# 10. Summary
echo -e "\n======================================================================="
echo "Weekly Maintenance Complete"
echo "Completed: $(date)"
echo "======================================================================="

# Note: Services are not automatically restarted
# Manual restart required after review
echo -e "\n⚠️  Note: Services stopped. Manual restart required."
echo "   To restart: ./scripts/verify_deployment.sh"
