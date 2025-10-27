#!/bin/bash
#
# PostgreSQL Backup Script for Quant Platform
#
# Usage:
#   ./scripts/backup_postgres.sh [--compress] [--retention-days N]
#

set -euo pipefail

# Configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
readonly BACKUP_DIR="${PROJECT_ROOT}/backups/postgres"
readonly DB_NAME="quant_platform"
readonly DB_USER="${POSTGRES_USER:-$USER}"
readonly DB_HOST="${POSTGRES_HOST:-localhost}"
readonly DB_PORT="${POSTGRES_PORT:-5432}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
COMPRESS="${COMPRESS:-false}"

# Logging
readonly LOG_FILE="${PROJECT_ROOT}/logs/backup_postgres_$(date +%Y%m%d).log"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    log "ERROR: $*" >&2
    exit 1
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --compress) COMPRESS=true; shift ;;
        --retention-days) RETENTION_DAYS="$2"; shift 2 ;;
        *) error "Unknown argument: $1" ;;
    esac
done

# Create directories
mkdir -p "$BACKUP_DIR" "$(dirname "$LOG_FILE")"

# Generate backup filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql"
[[ "$COMPRESS" == "true" ]] && BACKUP_FILE="${BACKUP_FILE}.gz"

log "======================================================================="
log "PostgreSQL Backup Starting"
log "Database: ${DB_NAME}, Backup: ${BACKUP_FILE}"

# Perform backup
START_TIME=$(date +%s)
if [[ "$COMPRESS" == "true" ]]; then
    /opt/homebrew/opt/postgresql@17/bin/pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        --format=custom --compress=9 --file="$BACKUP_FILE"
else
    /opt/homebrew/opt/postgresql@17/bin/pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        --format=custom --file="$BACKUP_FILE"
fi

DURATION=$(($(date +%s) - START_TIME))
BACKUP_SIZE=$(du -sh "$BACKUP_FILE" | cut -f1)
log "✅ Backup completed in ${DURATION}s, size: ${BACKUP_SIZE}"

# Cleanup old backups
DELETED=0
while IFS= read -r -d '' file; do
    rm -f "$file"; ((DELETED++)) || true
done < <(find "$BACKUP_DIR" -name "${DB_NAME}_*.sql*" -mtime "+${RETENTION_DAYS}" -print0)
log "✅ Deleted ${DELETED} old backups (retention: ${RETENTION_DAYS} days)"
log "======================================================================="

exit 0
