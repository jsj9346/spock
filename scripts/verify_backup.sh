#!/bin/bash
#
# Spock Backup Verification Script
# 백업 무결성 검증 및 복원 가능성 테스트
#
# Usage: bash scripts/verify_backup.sh [backup_directory]
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

BACKUP_DIR="${1}"

if [ -z "$BACKUP_DIR" ]; then
    echo -e "${RED}Error: Backup directory not specified${NC}"
    echo "Usage: bash scripts/verify_backup.sh [backup_directory]"
    exit 1
fi

if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}Error: Backup directory does not exist: ${BACKUP_DIR}${NC}"
    exit 1
fi

echo -e "${BLUE}🔍 Spock Backup Verification${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Backup Directory: ${BACKUP_DIR}"
echo ""

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNINGS=0

# Function to check file exists
check_file() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    local file="$1"
    local description="$2"
    local critical="${3:-true}"

    if [ -f "${BACKUP_DIR}/${file}" ]; then
        size=$(du -sh "${BACKUP_DIR}/${file}" | cut -f1)
        echo -e "${GREEN}✓${NC} ${description}: ${file} (${size})"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        if [ "$critical" = "true" ]; then
            echo -e "${RED}✗${NC} ${description}: ${file} MISSING (CRITICAL)"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
        else
            echo -e "${YELLOW}⚠${NC} ${description}: ${file} MISSING (optional)"
            WARNINGS=$((WARNINGS + 1))
        fi
        return 1
    fi
}

# Function to check directory exists
check_dir() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    local dir="$1"
    local description="$2"

    if [ -d "${BACKUP_DIR}/${dir}" ]; then
        count=$(find "${BACKUP_DIR}/${dir}" -type f | wc -l)
        echo -e "${GREEN}✓${NC} ${description}: ${dir}/ (${count} files)"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "${RED}✗${NC} ${description}: ${dir}/ MISSING"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi
}

# Function to verify SQL file
verify_sql() {
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    local file="$1"
    local description="$2"

    if [ ! -f "${BACKUP_DIR}/${file}" ]; then
        echo -e "${RED}✗${NC} ${description}: File missing"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi

    # Check if file is not empty
    if [ ! -s "${BACKUP_DIR}/${file}" ]; then
        echo -e "${RED}✗${NC} ${description}: File is empty"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
        return 1
    fi

    # Check for SQL syntax (basic)
    if grep -q "CREATE TABLE\|INSERT INTO\|COPY" "${BACKUP_DIR}/${file}"; then
        size=$(du -sh "${BACKUP_DIR}/${file}" | cut -f1)
        lines=$(wc -l < "${BACKUP_DIR}/${file}" | xargs)
        echo -e "${GREEN}✓${NC} ${description}: Valid SQL (${size}, ${lines} lines)"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
        return 0
    else
        echo -e "${YELLOW}⚠${NC} ${description}: No SQL statements found"
        WARNINGS=$((WARNINGS + 1))
        return 1
    fi
}

# ==========================================
# 1. Critical Files Check
# ==========================================
echo -e "${YELLOW}▶ Critical Files${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_file "MANIFEST.md" "Backup manifest"
check_file "system_info.txt" "System information"
check_file "spock_repo.bundle" "Git repository bundle"
check_file "env/.env" "Environment file"
check_file "database/complete.sql" "Complete database dump"

echo ""

# ==========================================
# 2. Database Files Check
# ==========================================
echo -e "${YELLOW}▶ Database Backup Files${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

verify_sql "database/schema.sql" "Database schema"
verify_sql "database/data.sql" "Database data"
verify_sql "database/complete.sql" "Complete database"

check_file "database/table_statistics.txt" "Table statistics" false
check_file "database/data_counts.txt" "Data counts" false

echo ""

# ==========================================
# 3. Environment Files Check
# ==========================================
echo -e "${YELLOW}▶ Environment Files${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_file "env/.env" "Main environment file"
check_file "env/env_vars_list.txt" "Environment variables list"
check_file "env/.env.bak" "Backup environment file" false

if [ -d "${BACKUP_DIR}/env/config" ]; then
    check_dir "env/config" "Config directory"
fi

echo ""

# ==========================================
# 4. Python Environment Check
# ==========================================
echo -e "${YELLOW}▶ Python Environment${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_file "python/requirements_frozen.txt" "Frozen requirements"
check_file "python/requirements.txt" "Project requirements" false
check_file "python/requirements_quant.txt" "Quant requirements" false

# Count packages
if [ -f "${BACKUP_DIR}/python/requirements_frozen.txt" ]; then
    pkg_count=$(wc -l < "${BACKUP_DIR}/python/requirements_frozen.txt" | xargs)
    echo "  → ${pkg_count} Python packages"
fi

echo ""

# ==========================================
# 5. Git Repository Check
# ==========================================
echo -e "${YELLOW}▶ Git Repository${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

check_file "spock_repo.bundle" "Git bundle"
check_file "git_current_branch.txt" "Current branch" false
check_file "git_recent_commits.txt" "Recent commits" false

# Verify git bundle
if [ -f "${BACKUP_DIR}/spock_repo.bundle" ]; then
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    if git bundle verify "${BACKUP_DIR}/spock_repo.bundle" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Git bundle is valid"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo -e "${RED}✗${NC} Git bundle verification failed"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
fi

echo ""

# ==========================================
# 6. Critical Files Backup Check
# ==========================================
echo -e "${YELLOW}▶ Critical Project Files${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -d "${BACKUP_DIR}/critical_files" ]; then
    check_dir "critical_files/docs" "Documentation" false
    check_dir "critical_files/scripts" "Scripts" false
    check_dir "critical_files/logs" "Recent logs" false
fi

echo ""

# ==========================================
# 7. Size and Integrity Check
# ==========================================
echo -e "${YELLOW}▶ Size and Integrity${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
BACKUP_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
echo "Total backup size: ${BACKUP_SIZE}"

# Check if backup is reasonable size (should be > 500MB)
BACKUP_SIZE_MB=$(du -sm "${BACKUP_DIR}" | cut -f1)
if [ $BACKUP_SIZE_MB -gt 500 ]; then
    echo -e "${GREEN}✓${NC} Backup size is reasonable (> 500MB)"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo -e "${YELLOW}⚠${NC} Backup size seems small (< 500MB)"
    WARNINGS=$((WARNINGS + 1))
fi

# Check database dump size
if [ -f "${BACKUP_DIR}/database/complete.sql" ]; then
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    DB_SIZE_MB=$(du -sm "${BACKUP_DIR}/database/complete.sql" | cut -f1)
    if [ $DB_SIZE_MB -gt 100 ]; then
        echo -e "${GREEN}✓${NC} Database dump size is reasonable (> 100MB)"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo -e "${YELLOW}⚠${NC} Database dump seems small (< 100MB)"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

echo ""

# ==========================================
# 8. Data Integrity Verification
# ==========================================
echo -e "${YELLOW}▶ Data Integrity${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check for common corruption indicators in SQL files
if [ -f "${BACKUP_DIR}/database/complete.sql" ]; then
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    # Check for truncated file (should end properly)
    if tail -1 "${BACKUP_DIR}/database/complete.sql" | grep -q "PostgreSQL database dump complete"; then
        echo -e "${GREEN}✓${NC} Database dump appears complete"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo -e "${YELLOW}⚠${NC} Database dump may be incomplete"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

# Verify .env file has required variables
if [ -f "${BACKUP_DIR}/env/.env" ]; then
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))

    required_vars=("POSTGRES_HOST" "POSTGRES_DB")
    missing_vars=0

    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "${BACKUP_DIR}/env/.env"; then
            missing_vars=$((missing_vars + 1))
        fi
    done

    if [ $missing_vars -eq 0 ]; then
        echo -e "${GREEN}✓${NC} Environment file contains required variables"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo -e "${YELLOW}⚠${NC} Environment file missing ${missing_vars} required variables"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

echo ""

# ==========================================
# Summary
# ==========================================
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Verification Summary${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "Total Checks: ${TOTAL_CHECKS}"
echo -e "${GREEN}Passed: ${PASSED_CHECKS}${NC}"
echo -e "${RED}Failed: ${FAILED_CHECKS}${NC}"
echo -e "${YELLOW}Warnings: ${WARNINGS}${NC}"
echo ""

# Overall status
if [ $FAILED_CHECKS -eq 0 ]; then
    if [ $WARNINGS -eq 0 ]; then
        echo -e "${GREEN}✓ Backup verification PASSED (Perfect)${NC}"
        echo ""
        echo "This backup is ready for restoration."
        echo "Proceed with: see scripts/RESTORE_GUIDE.md"
        exit 0
    else
        echo -e "${YELLOW}⚠ Backup verification PASSED (with warnings)${NC}"
        echo ""
        echo "Backup is usable but has some warnings."
        echo "Review warnings above before restoration."
        exit 0
    fi
else
    echo -e "${RED}✗ Backup verification FAILED${NC}"
    echo ""
    echo "Critical files are missing. Do NOT use this backup for restoration."
    echo "Create a new backup with: bash scripts/backup_full_system.sh"
    exit 1
fi
