#!/bin/bash
#
# PostgreSQL Restore Script
#
# Restores PostgreSQL database from backup file.
#
# Features:
# - Restore from local backup or S3
# - Pre-restore validation
# - Database recreation
# - Post-restore validation
# - Dry-run mode for testing
#
# Usage:
#   ./scripts/restore_postgres.sh --file backups/postgres/quant_platform_20251027_120000.sql.gz
#   ./scripts/restore_postgres.sh --latest
#   ./scripts/restore_postgres.sh --from-s3 --date 2025-10-27
#   ./scripts/restore_postgres.sh --dry-run --latest

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${PROJECT_ROOT}/backups/postgres"
LOG_DIR="${PROJECT_ROOT}/logs"
LOG_FILE="${LOG_DIR}/restore_$(date +%Y%m%d_%H%M%S).log"

# Database configuration
DB_NAME="${POSTGRES_DB:-quant_platform}"
DB_USER="${POSTGRES_USER:-postgres}"
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"

# S3 configuration
S3_BUCKET="${BACKUP_S3_BUCKET:-}"
S3_PREFIX="${BACKUP_S3_PREFIX:-postgres-backups}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Variables
BACKUP_FILE=""
FROM_S3=false
USE_LATEST=false
DRY_RUN=false
RESTORE_DATE=""

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

# Parse command-line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --file)
            BACKUP_FILE="$2"
            shift 2
            ;;
        --latest)
            USE_LATEST=true
            shift
            ;;
        --from-s3)
            FROM_S3=true
            shift
            ;;
        --date)
            RESTORE_DATE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --file FILE          Restore from specific backup file"
            echo "  --latest             Restore from latest backup"
            echo "  --from-s3            Download backup from S3"
            echo "  --date YYYY-MM-DD    Restore from specific date (requires --from-s3)"
            echo "  --dry-run            Test restore without applying changes"
            echo "  --help               Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --latest"
            echo "  $0 --file backups/postgres/quant_platform_20251027_120000.sql.gz"
            echo "  $0 --from-s3 --date 2025-10-27"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create directories
mkdir -p "$BACKUP_DIR"
mkdir -p "$LOG_DIR"

log_info "Starting PostgreSQL restore..."
log_info "Database: $DB_NAME"
log_info "Host: $DB_HOST:$DB_PORT"

if [ "$DRY_RUN" = true ]; then
    log_warn "DRY RUN MODE - No changes will be applied"
fi

# Determine which backup to use
if [ "$FROM_S3" = true ]; then
    log_step "Downloading backup from S3..."

    if [ -z "$S3_BUCKET" ]; then
        log_error "S3_BUCKET not configured in environment"
        exit 1
    fi

    if [ -n "$RESTORE_DATE" ]; then
        # Find backup for specific date
        S3_PATTERN="${RESTORE_DATE//-/}"  # Convert YYYY-MM-DD to YYYYMMDD
        log_info "Looking for backup from date: $RESTORE_DATE"

        S3_KEY=$(aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" | \
                 grep "quant_platform_${S3_PATTERN}" | \
                 tail -1 | \
                 awk '{print $4}')

        if [ -z "$S3_KEY" ]; then
            log_error "No backup found for date: $RESTORE_DATE"
            exit 1
        fi
    else
        # Get latest backup from S3
        log_info "Finding latest backup in S3..."

        S3_KEY=$(aws s3 ls "s3://$S3_BUCKET/$S3_PREFIX/" | \
                 grep "quant_platform_" | \
                 sort | \
                 tail -1 | \
                 awk '{print $4}')

        if [ -z "$S3_KEY" ]; then
            log_error "No backups found in S3"
            exit 1
        fi
    fi

    log_info "Downloading: $S3_KEY"
    BACKUP_FILE="${BACKUP_DIR}/${S3_KEY}"

    if ! aws s3 cp "s3://$S3_BUCKET/$S3_PREFIX/$S3_KEY" "$BACKUP_FILE" 2>&1 | tee -a "$LOG_FILE"; then
        log_error "Failed to download backup from S3"
        exit 1
    fi

    log_info "Download complete ✓"

elif [ "$USE_LATEST" = true ]; then
    log_step "Finding latest local backup..."

    BACKUP_FILE=$(find "$BACKUP_DIR" -name "quant_platform_*.sql.gz" -type f | sort | tail -1)

    if [ -z "$BACKUP_FILE" ]; then
        log_error "No local backups found in $BACKUP_DIR"
        exit 1
    fi

    log_info "Found: $(basename "$BACKUP_FILE")"

elif [ -z "$BACKUP_FILE" ]; then
    log_error "No backup file specified. Use --file, --latest, or --from-s3"
    exit 1
fi

# Validate backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
log_info "Backup file: $(basename "$BACKUP_FILE")"
log_info "Backup size: $BACKUP_SIZE"

# Validate backup integrity
log_step "Validating backup integrity..."

if ! gunzip -t "$BACKUP_FILE" 2>&1 | tee -a "$LOG_FILE"; then
    log_error "Backup file is corrupted"
    exit 1
fi

log_info "Backup integrity verified ✓"

if [ "$DRY_RUN" = true ]; then
    log_info "DRY RUN: Would restore from $BACKUP_FILE"
    log_info "DRY RUN: Exiting without making changes"
    exit 0
fi

# Confirm restore (destructive operation)
log_warn "⚠️  This will DESTROY the current database: $DB_NAME"
log_warn "⚠️  All existing data will be PERMANENTLY LOST"
echo -n "Are you sure you want to continue? (yes/no): "
read -r CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    log_info "Restore cancelled by user"
    exit 0
fi

# Check PostgreSQL accessibility
log_step "Checking PostgreSQL connection..."

if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" > /dev/null 2>&1; then
    log_error "PostgreSQL is not accessible at $DB_HOST:$DB_PORT"
    exit 1
fi

log_info "PostgreSQL is accessible ✓"

# Disconnect all users from database
log_step "Disconnecting all users from database..."

psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
    "SELECT pg_terminate_backend(pg_stat_activity.pid)
     FROM pg_stat_activity
     WHERE pg_stat_activity.datname = '$DB_NAME'
       AND pid <> pg_backend_pid();" 2>&1 | tee -a "$LOG_FILE" || true

log_info "Users disconnected ✓"

# Drop and recreate database
log_step "Dropping database $DB_NAME..."

if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
    "DROP DATABASE IF EXISTS $DB_NAME;" 2>&1 | tee -a "$LOG_FILE"; then
    log_info "Database dropped ✓"
else
    log_error "Failed to drop database"
    exit 1
fi

log_step "Creating database $DB_NAME..."

if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c \
    "CREATE DATABASE $DB_NAME;" 2>&1 | tee -a "$LOG_FILE"; then
    log_info "Database created ✓"
else
    log_error "Failed to create database"
    exit 1
fi

# Enable TimescaleDB extension
log_step "Enabling TimescaleDB extension..."

if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c \
    "CREATE EXTENSION IF NOT EXISTS timescaledb;" 2>&1 | tee -a "$LOG_FILE"; then
    log_info "TimescaleDB enabled ✓"
else
    log_warn "Failed to enable TimescaleDB (may not be installed)"
fi

# Restore database
log_step "Restoring database from backup..."

START_TIME=$(date +%s)

if gunzip -c "$BACKUP_FILE" | psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
    2>&1 | tee -a "$LOG_FILE"; then

    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    log_info "Database restored successfully ✓"
    log_info "Restore duration: ${DURATION}s"
else
    log_error "Database restore failed"
    exit 1
fi

# Verify restore
log_step "Verifying restore..."

# Count tables
TABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")

log_info "Tables restored: $TABLE_COUNT"

# Count OHLCV rows
OHLCV_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM ohlcv_data;" 2>/dev/null || echo "0")

log_info "OHLCV rows: $(echo $OHLCV_COUNT | tr -d ' ')"

# Verify TimescaleDB hypertables
HYPERTABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c \
    "SELECT COUNT(*) FROM timescaledb_information.hypertables;" 2>/dev/null || echo "0")

log_info "TimescaleDB hypertables: $(echo $HYPERTABLE_COUNT | tr -d ' ')"

# Update statistics
log_step "Updating database statistics..."

if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c \
    "ANALYZE;" 2>&1 | tee -a "$LOG_FILE"; then
    log_info "Statistics updated ✓"
else
    log_warn "Failed to update statistics"
fi

# Final summary
log_info "=" * 70
log_info "RESTORE COMPLETED SUCCESSFULLY ✓"
log_info "=" * 70
log_info "Database: $DB_NAME"
log_info "Backup file: $(basename "$BACKUP_FILE")"
log_info "Duration: ${DURATION}s"
log_info "Tables: $TABLE_COUNT"
log_info "Log file: $LOG_FILE"

exit 0
