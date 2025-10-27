#!/bin/bash
################################################################################
# run_validation_suite.sh - Phase 2 Validation Suite Runner
#
# Purpose:
# - Validate Phase 2 Global OHLCV Filtering System
# - Run all integration tests
# - Validate database schema
# - Check market-specific scripts
# - Generate validation report
#
# Usage:
#   ./scripts/run_validation_suite.sh [--quick|--full|--report-only]
#
# Author: Spock Trading System
# Created: 2025-10-16
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VALIDATION_MODE="${1:-full}"  # quick, full, report-only
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="${PROJECT_ROOT}/validation_reports"
REPORT_FILE="${REPORT_DIR}/validation_${TIMESTAMP}.txt"

# Create report directory
mkdir -p "${REPORT_DIR}"

################################################################################
# Helper Functions
################################################################################

print_header() {
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

################################################################################
# Validation Steps
################################################################################

validate_environment() {
    print_header "Step 1: Environment Validation"

    # Check Python version
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version)
        print_success "Python: ${PYTHON_VERSION}"
    else
        print_error "Python 3 not found"
        return 1
    fi

    # Check required Python packages
    REQUIRED_PACKAGES=("pandas" "numpy" "pytest" "sqlite3")
    for package in "${REQUIRED_PACKAGES[@]}"; do
        if python3 -c "import ${package}" &> /dev/null; then
            print_success "Package: ${package}"
        else
            print_warning "Package missing: ${package}"
        fi
    done

    # Check database
    if [ -f "${PROJECT_ROOT}/data/spock_local.db" ]; then
        DB_SIZE=$(du -h "${PROJECT_ROOT}/data/spock_local.db" | cut -f1)
        print_success "Database: spock_local.db (${DB_SIZE})"
    else
        print_warning "Database not found (expected for fresh install)"
    fi

    echo ""
}

validate_phase2_scripts() {
    print_header "Step 2: Phase 2 Scripts Validation"

    # Check market-specific collection scripts
    SCRIPTS=(
        "scripts/collect_us_stocks.py"
        "scripts/collect_hk_stocks.py"
        "scripts/collect_cn_stocks.py"
        "scripts/collect_jp_stocks.py"
        "scripts/collect_vn_stocks.py"
        "scripts/validate_db_schema.py"
    )

    for script in "${SCRIPTS[@]}"; do
        SCRIPT_PATH="${PROJECT_ROOT}/${script}"
        if [ -f "${SCRIPT_PATH}" ] && [ -x "${SCRIPT_PATH}" ]; then
            print_success "${script} - exists and executable"
        else
            print_error "${script} - missing or not executable"
            return 1
        fi
    done

    echo ""
}

run_integration_tests() {
    print_header "Step 3: Integration Tests"

    cd "${PROJECT_ROOT}"

    if [ "${VALIDATION_MODE}" = "report-only" ]; then
        print_info "Skipping tests (report-only mode)"
        echo ""
        return 0
    fi

    # Run Phase 2 integration tests
    print_info "Running Phase 2 integration tests..."
    if python3 -m pytest tests/test_phase2_integration.py -v --tb=short > "${REPORT_DIR}/pytest_${TIMESTAMP}.log" 2>&1; then
        PASS_COUNT=$(grep -c "PASSED" "${REPORT_DIR}/pytest_${TIMESTAMP}.log" || echo "0")
        FAIL_COUNT=$(grep -c "FAILED" "${REPORT_DIR}/pytest_${TIMESTAMP}.log" || echo "0")
        print_success "Integration tests: ${PASS_COUNT} passed, ${FAIL_COUNT} failed"
    else
        print_error "Integration tests failed (see log: ${REPORT_DIR}/pytest_${TIMESTAMP}.log)"
        return 1
    fi

    echo ""
}

validate_database_schema() {
    print_header "Step 4: Database Schema Validation"

    if [ "${VALIDATION_MODE}" = "report-only" ]; then
        print_info "Skipping schema validation (report-only mode)"
        echo ""
        return 0
    fi

    # Run database schema validation
    if [ -f "${PROJECT_ROOT}/data/spock_local.db" ]; then
        print_info "Running database schema validation..."
        if python3 "${PROJECT_ROOT}/scripts/validate_db_schema.py" > "${REPORT_DIR}/schema_${TIMESTAMP}.log" 2>&1; then
            print_success "Database schema validation passed"
        else
            EXIT_CODE=$?
            if [ ${EXIT_CODE} -eq 2 ]; then
                print_warning "Database schema validation passed with warnings"
            else
                print_error "Database schema validation failed"
                return 1
            fi
        fi
    else
        print_warning "Database not found, skipping schema validation"
    fi

    echo ""
}

validate_cli_interfaces() {
    print_header "Step 5: CLI Interface Validation"

    # Test --help for each script
    SCRIPTS=("us" "hk" "cn" "jp" "vn")

    for market in "${SCRIPTS[@]}"; do
        SCRIPT="${PROJECT_ROOT}/scripts/collect_${market}_stocks.py"
        if python3 "${SCRIPT}" --help > /dev/null 2>&1; then
            print_success "${market} script: --help works"
        else
            print_error "${market} script: --help failed"
            return 1
        fi
    done

    echo ""
}

generate_report() {
    print_header "Validation Report"

    {
        echo "============================================================"
        echo "Phase 2 Validation Report"
        echo "============================================================"
        echo "Timestamp: ${TIMESTAMP}"
        echo "Validation Mode: ${VALIDATION_MODE}"
        echo "Project Root: ${PROJECT_ROOT}"
        echo ""

        echo "Environment:"
        python3 --version
        echo ""

        echo "Phase 2 Scripts:"
        ls -lh "${PROJECT_ROOT}/scripts/collect_"*.py 2>/dev/null || echo "No scripts found"
        echo ""

        if [ -f "${PROJECT_ROOT}/data/spock_local.db" ]; then
            echo "Database:"
            du -h "${PROJECT_ROOT}/data/spock_local.db"
            sqlite3 "${PROJECT_ROOT}/data/spock_local.db" "SELECT COUNT(*) as ohlcv_rows FROM ohlcv_data" 2>/dev/null || echo "N/A"
            echo ""
        fi

        if [ -f "${REPORT_DIR}/pytest_${TIMESTAMP}.log" ]; then
            echo "Test Results:"
            tail -20 "${REPORT_DIR}/pytest_${TIMESTAMP}.log"
            echo ""
        fi

        echo "============================================================"
        echo "Validation Complete"
        echo "============================================================"
    } | tee "${REPORT_FILE}"

    print_success "Report saved: ${REPORT_FILE}"
    echo ""
}

################################################################################
# Main Execution
################################################################################

main() {
    print_header "Phase 2 Validation Suite"
    echo ""

    # Run validation steps
    validate_environment
    validate_phase2_scripts

    if [ "${VALIDATION_MODE}" != "report-only" ]; then
        run_integration_tests
        validate_database_schema
        validate_cli_interfaces
    fi

    generate_report

    print_header "Validation Summary"
    print_success "All validation steps completed"
    print_info "Full report: ${REPORT_FILE}"
    echo ""
}

# Execute main
main
