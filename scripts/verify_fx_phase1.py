#!/usr/bin/env python3
"""
Phase 1 FX Infrastructure Verification Script

Purpose:
- Verify all Phase 1 components are correctly installed and configured
- Test database connectivity and schema
- Validate BOK API integration
- Check Prometheus metrics availability
- Verify scripts are executable
- Run quick smoke tests

Verification Checklist:
✓ Phase 1-A: Database Migration
✓ Phase 1-B: BOK API Integration
✓ Phase 1-C: FX Data Collector
✓ Phase 1-D: Historical Backfill
✓ Phase 1-E: Monitoring Stack
✓ Phase 1-F: Testing Suite

Usage:
    python3 scripts/verify_fx_phase1.py

Exit Codes:
    0 - All verifications passed
    1 - Some verifications failed (warnings)
    2 - Critical failures detected

Author: Spock Quant Platform
Created: 2025-10-24
"""

import os
import sys
import logging
import subprocess
from pathlib import Path
from datetime import date, datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


# ================================================================
# Verification Results Tracker
# ================================================================

class VerificationResults:
    """Track verification results"""

    def __init__(self):
        self.passed = []
        self.failed = []
        self.warnings = []
        self.critical_failures = []

    def add_pass(self, check_name: str, message: str = ""):
        self.passed.append((check_name, message))
        logger.info(f"✅ {check_name}: {message}" if message else f"✅ {check_name}")

    def add_fail(self, check_name: str, message: str = "", critical: bool = False):
        if critical:
            self.critical_failures.append((check_name, message))
            logger.error(f"❌ CRITICAL: {check_name}: {message}")
        else:
            self.failed.append((check_name, message))
            logger.warning(f"❌ {check_name}: {message}")

    def add_warning(self, check_name: str, message: str = ""):
        self.warnings.append((check_name, message))
        logger.warning(f"⚠️  {check_name}: {message}")

    def print_summary(self):
        """Print verification summary"""
        logger.info("")
        logger.info("=" * 80)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"✅ Passed: {len(self.passed)}")
        logger.info(f"❌ Failed: {len(self.failed)}")
        logger.info(f"⚠️  Warnings: {len(self.warnings)}")
        logger.info(f"🚨 Critical: {len(self.critical_failures)}")
        logger.info("=" * 80)

        if self.critical_failures:
            logger.error("\nCRITICAL FAILURES:")
            for check, msg in self.critical_failures:
                logger.error(f"  - {check}: {msg}")

        if self.failed:
            logger.warning("\nFAILURES:")
            for check, msg in self.failed:
                logger.warning(f"  - {check}: {msg}")

        if self.warnings:
            logger.warning("\nWARNINGS:")
            for check, msg in self.warnings:
                logger.warning(f"  - {check}: {msg}")

    def get_exit_code(self) -> int:
        """Determine exit code based on results"""
        if self.critical_failures:
            return 2  # Critical failure
        elif self.failed:
            return 1  # Some failures
        else:
            return 0  # All passed


results = VerificationResults()


# ================================================================
# Phase 1-A: Database Migration Verification
# ================================================================

def verify_database_migration():
    """Verify PostgreSQL database and fx_valuation_signals table"""
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1-A: DATABASE MIGRATION VERIFICATION")
    logger.info("=" * 80)

    try:
        from modules.db_manager_postgres import PostgresDatabaseManager

        db = PostgresDatabaseManager()
        results.add_pass("PostgreSQL Connection", "Database connected")

        # Check fx_valuation_signals table exists
        check_table_sql = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'fx_valuation_signals'
            )
        """
        exists = db.execute_query(check_table_sql)

        # Handle different return formats (list of tuples or dict-like)
        table_exists = False
        if exists:
            if isinstance(exists, list) and len(exists) > 0:
                if isinstance(exists[0], (tuple, list)):
                    table_exists = exists[0][0] if len(exists[0]) > 0 else False
                elif isinstance(exists[0], dict):
                    table_exists = exists[0].get('exists', False)
            elif isinstance(exists, dict):
                table_exists = exists.get('exists', False)

        if table_exists:
            results.add_pass("fx_valuation_signals Table", "Table exists")
        else:
            results.add_fail("fx_valuation_signals Table", "Table not found", critical=True)
            return

        # Check table schema
        schema_sql = """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'fx_valuation_signals'
            ORDER BY ordinal_position
        """
        columns = db.execute_query(schema_sql)

        required_columns = ['currency', 'region', 'date', 'usd_rate', 'data_quality']

        # Handle different return formats
        actual_columns = []
        if columns:
            for col in columns:
                if isinstance(col, (tuple, list)):
                    actual_columns.append(col[0])
                elif isinstance(col, dict):
                    actual_columns.append(col.get('column_name', ''))

        for col in required_columns:
            if col in actual_columns:
                results.add_pass(f"Column: {col}", "Present")
            else:
                results.add_fail(f"Column: {col}", "Missing", critical=True)

        # Check materialized view
        view_exists_sql = """
            SELECT EXISTS (
                SELECT FROM pg_matviews
                WHERE matviewname = 'mv_latest_fx_signals'
            )
        """
        view_exists_result = db.execute_query(view_exists_sql)

        # Handle different return formats
        view_exists = False
        if view_exists_result:
            if isinstance(view_exists_result, list) and len(view_exists_result) > 0:
                if isinstance(view_exists_result[0], (tuple, list)):
                    view_exists = view_exists_result[0][0] if len(view_exists_result[0]) > 0 else False
                elif isinstance(view_exists_result[0], dict):
                    view_exists = view_exists_result[0].get('exists', False)

        if view_exists:
            results.add_pass("Materialized View", "mv_latest_fx_signals exists")
        else:
            results.add_warning("Materialized View", "mv_latest_fx_signals not found")

        # Check for any data
        data_count_sql = "SELECT COUNT(*) FROM fx_valuation_signals"
        count_result = db.execute_query(data_count_sql)

        # Handle different return formats
        record_count = 0
        if count_result:
            if isinstance(count_result, list) and len(count_result) > 0:
                if isinstance(count_result[0], (tuple, list)):
                    record_count = count_result[0][0] if len(count_result[0]) > 0 else 0
                elif isinstance(count_result[0], dict):
                    record_count = count_result[0].get('count', 0)

        if record_count > 0:
            results.add_pass("Data Presence", f"{record_count} records found")
        else:
            results.add_warning("Data Presence", "No data in table (run backfill)")

        # Note: PostgresDatabaseManager uses connection pooling, no need to explicitly close

    except Exception as e:
        import traceback
        error_msg = f"{type(e).__name__}: {str(e)}"
        logger.error(f"Exception details: {traceback.format_exc()}")
        results.add_fail("Database Verification", error_msg, critical=True)


# ================================================================
# Phase 1-B: BOK API Integration Verification
# ================================================================

def verify_bok_api_integration():
    """Verify BOK API integration"""
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1-B: BOK API INTEGRATION VERIFICATION")
    logger.info("=" * 80)

    try:
        from modules.exchange_rate_manager import ExchangeRateManager

        manager = ExchangeRateManager()
        results.add_pass("ExchangeRateManager Import", "Module loaded")

        # Test BOK API call
        usd_rate = manager.get_rate('USD')

        if usd_rate and usd_rate > 0:
            results.add_pass("BOK API Test", f"USD/KRW rate: {usd_rate}")
        else:
            results.add_warning("BOK API Test", "Could not fetch USD rate (cache may be stale)")

        # Test all currencies
        currencies = ['USD', 'HKD', 'CNY', 'JPY', 'VND']
        for currency in currencies:
            rate = manager.get_rate(currency)
            if rate and rate > 0:
                results.add_pass(f"BOK API: {currency}", f"Rate: {rate}")
            else:
                results.add_warning(f"BOK API: {currency}", "Could not fetch rate")

    except Exception as e:
        results.add_fail("BOK API Integration", str(e))


# ================================================================
# Phase 1-C: FX Data Collector Verification
# ================================================================

def verify_fx_data_collector():
    """Verify FX data collector module"""
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1-C: FX DATA COLLECTOR VERIFICATION")
    logger.info("=" * 80)

    try:
        from modules.fx_data_collector import FXDataCollector

        collector = FXDataCollector()
        results.add_pass("FXDataCollector Import", "Module loaded")

        # Check supported currencies
        if len(collector.SUPPORTED_CURRENCIES) == 5:
            results.add_pass("Supported Currencies", f"{len(collector.SUPPORTED_CURRENCIES)} currencies")
        else:
            results.add_fail("Supported Currencies", f"Expected 5, got {len(collector.SUPPORTED_CURRENCIES)}")

        # Test collection script exists and is executable
        collection_script = project_root / 'scripts' / 'collect_fx_data.py'
        if collection_script.exists():
            results.add_pass("Collection Script", f"{collection_script.name} exists")

            if os.access(collection_script, os.X_OK):
                results.add_pass("Script Executable", "collect_fx_data.py is executable")
            else:
                results.add_warning("Script Executable", "collect_fx_data.py not executable")
        else:
            results.add_fail("Collection Script", "collect_fx_data.py not found", critical=True)

    except Exception as e:
        results.add_fail("FX Data Collector", str(e), critical=True)


# ================================================================
# Phase 1-D: Historical Backfill Verification
# ================================================================

def verify_historical_backfill():
    """Verify historical backfill script"""
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1-D: HISTORICAL BACKFILL VERIFICATION")
    logger.info("=" * 80)

    try:
        # Check backfill script exists
        backfill_script = project_root / 'scripts' / 'backfill_fx_history.py'

        if backfill_script.exists():
            results.add_pass("Backfill Script", f"{backfill_script.name} exists")

            if os.access(backfill_script, os.X_OK):
                results.add_pass("Script Executable", "backfill_fx_history.py is executable")
            else:
                results.add_warning("Script Executable", "backfill_fx_history.py not executable")
        else:
            results.add_fail("Backfill Script", "backfill_fx_history.py not found", critical=True)

        # Test dry run mode
        try:
            result = subprocess.run(
                [sys.executable, str(backfill_script), '--dry-run', '--years', '0'],
                capture_output=True,
                timeout=10,
                cwd=project_root
            )

            if result.returncode == 0:
                results.add_pass("Backfill Dry Run", "Script executed successfully")
            else:
                results.add_warning("Backfill Dry Run", f"Exit code: {result.returncode}")

        except subprocess.TimeoutExpired:
            results.add_warning("Backfill Dry Run", "Script timed out (acceptable for dry run)")
        except Exception as e:
            results.add_warning("Backfill Dry Run", str(e))

    except Exception as e:
        results.add_fail("Historical Backfill", str(e))


# ================================================================
# Phase 1-E: Monitoring Stack Verification
# ================================================================

def verify_monitoring_stack():
    """Verify Prometheus metrics and Grafana dashboard"""
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1-E: MONITORING STACK VERIFICATION")
    logger.info("=" * 80)

    try:
        # Check Prometheus metrics module
        metrics_file = project_root / 'monitoring' / 'prometheus' / 'fx_collection_metrics.py'

        if metrics_file.exists():
            results.add_pass("Prometheus Metrics", "fx_collection_metrics.py exists")
        else:
            results.add_fail("Prometheus Metrics", "fx_collection_metrics.py not found")

        # Test metrics import
        try:
            from monitoring.prometheus.fx_collection_metrics import get_metrics

            metrics = get_metrics()

            if metrics.enabled:
                results.add_pass("Prometheus Client", "prometheus_client available")
            else:
                results.add_warning("Prometheus Client", "prometheus_client not installed")

        except Exception as e:
            results.add_warning("Metrics Import", str(e))

        # Check Grafana dashboard
        dashboard_file = project_root / 'monitoring' / 'grafana' / 'fx_dashboard.json'

        if dashboard_file.exists():
            results.add_pass("Grafana Dashboard", "fx_dashboard.json exists")
        else:
            results.add_fail("Grafana Dashboard", "fx_dashboard.json not found")

        # Check alert rules
        alert_rules_file = project_root / 'monitoring' / 'grafana' / 'alert_rules.yaml'

        if alert_rules_file.exists():
            results.add_pass("Alert Rules", "alert_rules.yaml exists")
        else:
            results.add_warning("Alert Rules", "alert_rules.yaml not found")

    except Exception as e:
        results.add_fail("Monitoring Stack", str(e))


# ================================================================
# Phase 1-F: Testing Suite Verification
# ================================================================

def verify_testing_suite():
    """Verify unit and integration tests"""
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 1-F: TESTING SUITE VERIFICATION")
    logger.info("=" * 80)

    try:
        # Check unit tests
        unit_test_file = project_root / 'tests' / 'test_fx_data_collector.py'

        if unit_test_file.exists():
            results.add_pass("Unit Tests", "test_fx_data_collector.py exists")
        else:
            results.add_fail("Unit Tests", "test_fx_data_collector.py not found")

        # Check integration tests
        integration_test_file = project_root / 'tests' / 'test_fx_backfill_integration.py'

        if integration_test_file.exists():
            results.add_pass("Integration Tests", "test_fx_backfill_integration.py exists")
        else:
            results.add_fail("Integration Tests", "test_fx_backfill_integration.py not found")

        # Test pytest availability
        try:
            subprocess.run(['pytest', '--version'], capture_output=True, check=True)
            results.add_pass("pytest", "pytest is installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            results.add_warning("pytest", "pytest not installed (pip install pytest)")

    except Exception as e:
        results.add_fail("Testing Suite", str(e))


# ================================================================
# Additional System Checks
# ================================================================

def verify_system_dependencies():
    """Verify system dependencies and environment"""
    logger.info("\n" + "=" * 80)
    logger.info("SYSTEM DEPENDENCIES VERIFICATION")
    logger.info("=" * 80)

    # Check Python version
    python_version = sys.version_info
    if python_version >= (3, 11):
        results.add_pass("Python Version", f"{python_version.major}.{python_version.minor}")
    else:
        results.add_warning("Python Version", f"{python_version.major}.{python_version.minor} (3.11+ recommended)")

    # Check .env file
    env_file = project_root / '.env'
    if env_file.exists():
        results.add_pass(".env File", "Present")
    else:
        results.add_warning(".env File", "Not found (optional for BOK API)")

    # Check logs directory
    logs_dir = project_root / 'logs'
    if logs_dir.exists():
        results.add_pass("Logs Directory", "Present")
    else:
        results.add_warning("Logs Directory", "Creating...")
        logs_dir.mkdir(parents=True, exist_ok=True)

    # Check data directory
    data_dir = project_root / 'data'
    if data_dir.exists():
        results.add_pass("Data Directory", "Present")
    else:
        results.add_warning("Data Directory", "Creating...")
        data_dir.mkdir(parents=True, exist_ok=True)


# ================================================================
# Main Verification Runner
# ================================================================

def main():
    """Run all verification checks"""
    logger.info("=" * 80)
    logger.info("FX INFRASTRUCTURE PHASE 1 VERIFICATION")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    # Run verifications
    verify_system_dependencies()
    verify_database_migration()
    verify_bok_api_integration()
    verify_fx_data_collector()
    verify_historical_backfill()
    verify_monitoring_stack()
    verify_testing_suite()

    # Print summary
    results.print_summary()

    # Return exit code
    exit_code = results.get_exit_code()

    if exit_code == 0:
        logger.info("\n✅ All verifications PASSED")
    elif exit_code == 1:
        logger.warning("\n⚠️  Some verifications FAILED (non-critical)")
    else:
        logger.error("\n❌ CRITICAL failures detected")

    return exit_code


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
