#!/bin/bash
#
# Spock Full System Backup Script
# 노트북 마이그레이션을 위한 전체 시스템 백업
#
# Usage: bash scripts/backup_full_system.sh [backup_location]
# Example: bash scripts/backup_full_system.sh /Volumes/ExternalDrive/spock_backup
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
PROJECT_DIR="/Users/13ruce/spock"
DEFAULT_BACKUP_DIR="${PROJECT_DIR}/backups/migration_${TIMESTAMP}"
BACKUP_DIR="${1:-$DEFAULT_BACKUP_DIR}"
DB_NAME="quant_platform"

# Create backup directory
echo -e "${BLUE}📦 Spock Full System Backup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Backup Location: ${BACKUP_DIR}"
echo "Timestamp: ${TIMESTAMP}"
echo ""

mkdir -p "${BACKUP_DIR}"
cd "${PROJECT_DIR}"

# Function to print section header
print_header() {
    echo ""
    echo -e "${YELLOW}▶ $1${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# Function to check success
check_success() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ $1${NC}"
    else
        echo -e "${RED}✗ $1 FAILED${NC}"
        exit 1
    fi
}

# ============================================
# 1. System Information
# ============================================
print_header "1/7 시스템 정보 수집"

cat > "${BACKUP_DIR}/system_info.txt" << EOF
Spock System Backup Information
================================
Backup Date: $(date)
Hostname: $(hostname)
macOS Version: $(sw_vers -productVersion)
Processor: $(sysctl -n machdep.cpu.brand_string)

Python Version: $(python3 --version)
Python Location: $(which python3)

PostgreSQL Version: $(psql --version)
pg_dump Location: $(which pg_dump)

Git Remote: $(git remote -v | head -1)
Git Branch: $(git branch --show-current)
Git Latest Commit: $(git log -1 --oneline)

Project Size: $(du -sh ${PROJECT_DIR} | cut -f1)
Database Size: $(psql -d ${DB_NAME} -t -c "SELECT pg_size_pretty(pg_database_size('${DB_NAME}'));" | xargs)

Installed Packages:
$(brew list | grep -E "postgresql|timescaledb|python")

PostgreSQL Extensions:
$(psql -d ${DB_NAME} -t -c "SELECT extname || ' ' || extversion FROM pg_extension ORDER BY extname;")
EOF

check_success "System information collected"

# ============================================
# 2. Git Repository Backup
# ============================================
print_header "2/7 Git 저장소 백업"

# Check for uncommitted changes
UNCOMMITTED=$(git status --porcelain | wc -l)
if [ $UNCOMMITTED -gt 0 ]; then
    echo -e "${YELLOW}⚠ Warning: ${UNCOMMITTED} uncommitted changes detected${NC}"
    git status --short > "${BACKUP_DIR}/uncommitted_changes.txt"
fi

# Create git bundle (complete repository backup)
git bundle create "${BACKUP_DIR}/spock_repo.bundle" --all
check_success "Git bundle created"

# Export current branch and commit info
git branch --show-current > "${BACKUP_DIR}/git_current_branch.txt"
git log --oneline -20 > "${BACKUP_DIR}/git_recent_commits.txt"
check_success "Git metadata exported"

# ============================================
# 3. Environment Files Backup
# ============================================
print_header "3/7 환경 파일 백업"

mkdir -p "${BACKUP_DIR}/env"

# Copy .env files
if [ -f .env ]; then
    cp .env "${BACKUP_DIR}/env/.env"
    check_success ".env file backed up"
fi

if [ -f .env.bak ]; then
    cp .env.bak "${BACKUP_DIR}/env/.env.bak"
    check_success ".env.bak file backed up"
fi

# Copy config files
if [ -d config ]; then
    cp -r config "${BACKUP_DIR}/env/"
    check_success "config directory backed up"
fi

# Export environment variable names (not values, for security)
env | grep -E "^(KIS_|DART_|AWS_|POSTGRES)" | cut -d= -f1 > "${BACKUP_DIR}/env/env_vars_list.txt"
check_success "Environment variables list exported"

# ============================================
# 4. PostgreSQL Database Backup
# ============================================
print_header "4/7 PostgreSQL 데이터베이스 백업"

mkdir -p "${BACKUP_DIR}/database"

echo "Backing up database schema..."
pg_dump -d ${DB_NAME} --schema-only --no-owner --no-privileges \
    -f "${BACKUP_DIR}/database/schema.sql"
check_success "Database schema backed up"

echo "Backing up database data (this may take several minutes)..."
pg_dump -d ${DB_NAME} --data-only --no-owner --no-privileges \
    -f "${BACKUP_DIR}/database/data.sql"
check_success "Database data backed up"

echo "Creating complete database dump..."
pg_dump -d ${DB_NAME} --no-owner --no-privileges \
    -f "${BACKUP_DIR}/database/complete.sql"
check_success "Complete database dump created"

# Export table statistics
psql -d ${DB_NAME} -c "
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    n_tup_ins as inserts,
    n_tup_upd as updates,
    n_tup_del as deletes
FROM pg_tables
LEFT JOIN pg_stat_user_tables USING (schemaname, tablename)
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
" > "${BACKUP_DIR}/database/table_statistics.txt"
check_success "Table statistics exported"

# Export data counts
psql -d ${DB_NAME} -c "
SELECT 'tickers' as table_name, COUNT(*) as count FROM tickers
UNION ALL SELECT 'ohlcv_data', COUNT(*) FROM ohlcv_data
UNION ALL SELECT 'ticker_fundamentals', COUNT(*) FROM ticker_fundamentals
UNION ALL SELECT 'stock_details', COUNT(*) FROM stock_details
UNION ALL SELECT 'etf_details', COUNT(*) FROM etf_details
UNION ALL SELECT 'global_market_indices', COUNT(*) FROM global_market_indices
ORDER BY count DESC;
" > "${BACKUP_DIR}/database/data_counts.txt"
check_success "Data counts exported"

# ============================================
# 5. Python Environment Backup
# ============================================
print_header "5/7 Python 환경 백업"

mkdir -p "${BACKUP_DIR}/python"

# Export installed packages
pip freeze > "${BACKUP_DIR}/python/requirements_frozen.txt"
check_success "pip freeze exported"

# Copy requirements files
if [ -f requirements.txt ]; then
    cp requirements.txt "${BACKUP_DIR}/python/"
fi
if [ -f requirements_quant.txt ]; then
    cp requirements_quant.txt "${BACKUP_DIR}/python/"
fi
check_success "requirements files backed up"

# Export conda environment (if using conda)
if command -v conda &> /dev/null; then
    conda env export > "${BACKUP_DIR}/python/conda_environment.yml"
    check_success "conda environment exported"
fi

# ============================================
# 6. Critical Files Backup
# ============================================
print_header "6/7 주요 파일 백업"

mkdir -p "${BACKUP_DIR}/critical_files"

# Backup documentation
if [ -d docs ]; then
    cp -r docs "${BACKUP_DIR}/critical_files/"
    check_success "Documentation backed up"
fi

# Backup logs (recent only)
if [ -d logs ]; then
    mkdir -p "${BACKUP_DIR}/critical_files/logs"
    find logs -type f -mtime -7 -exec cp {} "${BACKUP_DIR}/critical_files/logs/" \;
    check_success "Recent logs backed up"
fi

# Backup scripts
if [ -d scripts ]; then
    cp -r scripts "${BACKUP_DIR}/critical_files/"
    check_success "Scripts backed up"
fi

# Backup existing backups metadata
if [ -d backups ]; then
    ls -lh backups > "${BACKUP_DIR}/critical_files/existing_backups_list.txt"
    check_success "Existing backups list created"
fi

# ============================================
# 7. Verification & Manifest
# ============================================
print_header "7/7 백업 검증 및 매니페스트 생성"

# Create manifest
cat > "${BACKUP_DIR}/MANIFEST.md" << EOF
# Spock Migration Backup Manifest

**Backup Date**: $(date)
**Backup Location**: ${BACKUP_DIR}
**Project Version**: $(git describe --tags 2>/dev/null || echo "N/A")

## Backup Contents

### 1. System Information
- \`system_info.txt\` - Complete system configuration

### 2. Git Repository
- \`spock_repo.bundle\` - Complete git repository ($(du -sh "${BACKUP_DIR}/spock_repo.bundle" | cut -f1))
- \`git_current_branch.txt\` - Current branch name
- \`git_recent_commits.txt\` - Recent commit history
- \`uncommitted_changes.txt\` - Uncommitted changes (if any)

### 3. Environment Files
- \`env/.env\` - Main environment file (ENCRYPTED - handle with care)
- \`env/.env.bak\` - Backup environment file
- \`env/config/\` - Configuration directory
- \`env/env_vars_list.txt\` - Environment variable names

### 4. Database
- \`database/schema.sql\` - Database schema only ($(du -sh "${BACKUP_DIR}/database/schema.sql" | cut -f1))
- \`database/data.sql\` - Database data only ($(du -sh "${BACKUP_DIR}/database/data.sql" | cut -f1))
- \`database/complete.sql\` - Complete database dump ($(du -sh "${BACKUP_DIR}/database/complete.sql" | cut -f1))
- \`database/table_statistics.txt\` - Table sizes and statistics
- \`database/data_counts.txt\` - Record counts by table

### 5. Python Environment
- \`python/requirements_frozen.txt\` - Exact package versions ($(wc -l < "${BACKUP_DIR}/python/requirements_frozen.txt" | xargs) packages)
- \`python/requirements.txt\` - Project requirements
- \`python/requirements_quant.txt\` - Quant-specific requirements
- \`python/conda_environment.yml\` - Conda environment (if applicable)

### 6. Critical Files
- \`critical_files/docs/\` - Documentation directory
- \`critical_files/logs/\` - Recent logs (last 7 days)
- \`critical_files/scripts/\` - Utility scripts
- \`critical_files/existing_backups_list.txt\` - List of existing backups

### 7. Verification
- \`MANIFEST.md\` - This file
- \`backup_verification.txt\` - Backup integrity checks
- \`RESTORE_GUIDE.md\` - Step-by-step restoration guide

## Backup Statistics

- **Total Backup Size**: $(du -sh "${BACKUP_DIR}" | cut -f1)
- **Database Size**: $(psql -d ${DB_NAME} -t -c "SELECT pg_size_pretty(pg_database_size('${DB_NAME}'));" | xargs)
- **Total OHLCV Records**: $(psql -d ${DB_NAME} -t -c "SELECT COUNT(*) FROM ohlcv_data;" | xargs)
- **Total Tickers**: $(psql -d ${DB_NAME} -t -c "SELECT COUNT(*) FROM tickers;" | xargs)
- **Git Commits**: $(git rev-list --count HEAD)

## Next Steps

1. **Verify Backup Integrity**: Run \`bash scripts/verify_backup.sh ${BACKUP_DIR}\`
2. **Test Restoration**: Perform test restore on a separate machine (see RESTORE_GUIDE.md)
3. **Secure Storage**: Copy backup to external drive and cloud storage
4. **Update Documentation**: Document any special configurations

## Security Notes

⚠️ **IMPORTANT**: This backup contains sensitive information:
- API keys and credentials in \`.env\` files
- Database connection strings
- Trading account information

**Handle with care**:
- Encrypt external drive backups
- Use secure cloud storage with encryption
- Never share \`.env\` files publicly
- Delete old backups after successful migration

## Support

For restoration instructions, see: \`RESTORE_GUIDE.md\`
For issues, contact: [Your contact information]

---
Generated by: backup_full_system.sh
Backup ID: ${TIMESTAMP}
EOF

check_success "Manifest created"

# Verify backup files exist
echo ""
echo "Verifying backup integrity..."
cat > "${BACKUP_DIR}/backup_verification.txt" << EOF
Backup Verification Report
==========================
Date: $(date)

Critical Files Check:
EOF

for file in "spock_repo.bundle" "env/.env" "database/complete.sql" "python/requirements_frozen.txt"; do
    if [ -f "${BACKUP_DIR}/${file}" ]; then
        size=$(du -sh "${BACKUP_DIR}/${file}" | cut -f1)
        echo "✓ ${file} (${size})" >> "${BACKUP_DIR}/backup_verification.txt"
    else
        echo "✗ ${file} MISSING" >> "${BACKUP_DIR}/backup_verification.txt"
    fi
done

cat "${BACKUP_DIR}/backup_verification.txt"
check_success "Backup verification completed"

# ============================================
# Summary
# ============================================
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Backup Completed Successfully!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Backup Location: ${BACKUP_DIR}"
echo "Total Size: $(du -sh "${BACKUP_DIR}" | cut -f1)"
echo ""
echo "Next Steps:"
echo "1. Review: cat ${BACKUP_DIR}/MANIFEST.md"
echo "2. Verify: bash scripts/verify_backup.sh ${BACKUP_DIR}"
echo "3. Copy to external drive or cloud storage"
echo ""
echo -e "${YELLOW}⚠ Remember to handle .env files securely!${NC}"
echo ""
