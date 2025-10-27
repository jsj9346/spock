#!/usr/bin/env python3
"""
kr_data_quality_workflow.py - Automated KR Market Data Quality Workflow

Purpose:
- Automated workflow for ensuring KR market data quality
- Orchestrates collection → recalculation → validation
- Generates comprehensive quality reports

Workflow:
1. Check current data quality status
2. Run full historical data collection if needed (250 days)
3. Recalculate all technical indicators
4. Validate final data quality
5. Generate completion report

Usage:
    python3 scripts/kr_data_quality_workflow.py [--skip-collection] [--skip-recalculation]

Flags:
    --skip-collection      Skip data collection step (use existing data)
    --skip-recalculation   Skip indicator recalculation step
    --force                Force execution even if validations fail
"""

import sys
import os
import subprocess
import argparse
import time
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Script paths
VALIDATION_SCRIPT = 'scripts/validate_kr_data_quality.py'
COLLECTION_SCRIPT = 'scripts/collect_full_kr_250days.py'
RECALCULATION_SCRIPT = 'scripts/recalculate_technical_indicators.py'

# Workflow configuration
TARGET_DAYS = 250
TARGET_NULL_RATE = 1.0  # <1% NULL is target


def print_section_header(title: str):
    """Print formatted section header"""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}\n")


def run_command(cmd: str, description: str, timeout: int = None) -> tuple[int, str, str]:
    """
    Run shell command and return exit code, stdout, stderr

    Args:
        cmd: Command to execute
        description: Human-readable description
        timeout: Timeout in seconds (None = no timeout)

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    logger.info(f"🔄 {description}...")
    logger.debug(f"   Command: {cmd}")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return result.returncode, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        logger.error(f"❌ Command timed out after {timeout} seconds")
        return 1, "", "Timeout"
    except Exception as e:
        logger.error(f"❌ Command failed: {e}")
        return 1, "", str(e)


def check_script_exists(script_path: str) -> bool:
    """Check if script file exists"""
    if not os.path.exists(script_path):
        logger.error(f"❌ Script not found: {script_path}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description='KR Market Data Quality Workflow')
    parser.add_argument('--skip-collection', action='store_true', help='Skip data collection step')
    parser.add_argument('--skip-recalculation', action='store_true', help='Skip indicator recalculation step')
    parser.add_argument('--force', action='store_true', help='Force execution even if validations fail')
    args = parser.parse_args()

    workflow_start_time = time.time()

    print_section_header("KR MARKET DATA QUALITY WORKFLOW")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Configuration:")
    print(f"  - Target data coverage: {TARGET_DAYS} days")
    print(f"  - Target NULL rate: <{TARGET_NULL_RATE}%")
    print(f"  - Skip collection: {args.skip_collection}")
    print(f"  - Skip recalculation: {args.skip_recalculation}")
    print(f"  - Force mode: {args.force}")

    # Verify all scripts exist
    print_section_header("STEP 0: PRE-FLIGHT CHECKS")

    all_scripts_exist = True
    for script in [VALIDATION_SCRIPT, COLLECTION_SCRIPT, RECALCULATION_SCRIPT]:
        if check_script_exists(script):
            logger.info(f"✅ Found: {script}")
        else:
            all_scripts_exist = False

    if not all_scripts_exist:
        logger.error("❌ Missing required scripts. Aborting workflow.")
        sys.exit(1)

    logger.info("✅ All required scripts found")

    # Step 1: Initial validation
    print_section_header("STEP 1: INITIAL DATA QUALITY VALIDATION")

    exit_code, stdout, stderr = run_command(
        f'python3 {VALIDATION_SCRIPT}',
        "Running initial data quality validation",
        timeout=300
    )

    print(stdout)  # Show validation report

    if exit_code == 0:
        logger.info("✅ Initial validation passed - data quality is excellent")
        if not args.force:
            logger.info("ℹ️  No workflow execution needed. Use --force to run anyway.")
            sys.exit(0)
    elif exit_code == 1:
        logger.warning("⚠️  Critical issues detected - workflow execution required")
    elif exit_code == 2:
        logger.warning("⚠️  Minor issues detected - workflow execution recommended")

    # Step 2: Full historical data collection
    if not args.skip_collection:
        print_section_header("STEP 2: FULL HISTORICAL DATA COLLECTION (250 DAYS)")

        logger.info(f"📊 Collecting {TARGET_DAYS} days of historical data for all KR tickers...")
        logger.info(f"⏱️  Estimated time: ~28 minutes (3,745 tickers × 0.45s)")

        collection_start = time.time()

        exit_code, stdout, stderr = run_command(
            f'python3 {COLLECTION_SCRIPT}',
            "Running full historical data collection",
            timeout=3600  # 1 hour timeout
        )

        collection_time = time.time() - collection_start

        if exit_code == 0:
            logger.info(f"✅ Data collection completed in {collection_time/60:.1f} minutes")
            print(stdout[-2000:])  # Show last 2000 chars of output (final summary)
        else:
            logger.error(f"❌ Data collection failed")
            logger.error(stderr)
            if not args.force:
                logger.error("Aborting workflow. Use --force to continue anyway.")
                sys.exit(1)
    else:
        logger.info("⏭️  Skipping data collection (--skip-collection flag)")

    # Step 3: Technical indicator recalculation
    if not args.skip_recalculation:
        print_section_header("STEP 3: TECHNICAL INDICATOR RECALCULATION")

        logger.info(f"📊 Recalculating 16 technical indicators for all KR tickers...")
        logger.info(f"⏱️  Estimated time: ~60 seconds (vectorized calculations)")

        recalc_start = time.time()

        exit_code, stdout, stderr = run_command(
            f'python3 {RECALCULATION_SCRIPT}',
            "Running technical indicator recalculation",
            timeout=600  # 10 minute timeout
        )

        recalc_time = time.time() - recalc_start

        if exit_code == 0:
            logger.info(f"✅ Indicator recalculation completed in {recalc_time:.1f} seconds")
            print(stdout[-2000:])  # Show last 2000 chars of output (final summary)
        else:
            logger.error(f"❌ Indicator recalculation failed")
            logger.error(stderr)
            if not args.force:
                logger.error("Aborting workflow. Use --force to continue anyway.")
                sys.exit(1)
    else:
        logger.info("⏭️  Skipping indicator recalculation (--skip-recalculation flag)")

    # Step 4: Final validation
    print_section_header("STEP 4: FINAL DATA QUALITY VALIDATION")

    exit_code, stdout, stderr = run_command(
        f'python3 {VALIDATION_SCRIPT}',
        "Running final data quality validation",
        timeout=300
    )

    print(stdout)  # Show validation report

    workflow_time = time.time() - workflow_start_time

    # Final summary
    print_section_header("WORKFLOW COMPLETION SUMMARY")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total workflow time: {workflow_time/60:.1f} minutes")

    if exit_code == 0:
        logger.info("✅ WORKFLOW SUCCESS - Data quality is excellent")
        logger.info("✅ System is ready for LayeredScoringEngine execution")
        print(f"\n🎯 Next Steps:")
        print(f"   1. Review validation report above")
        print(f"   2. Run LayeredScoringEngine: python3 spock.py --mode manual --region KR")
        print(f"   3. Monitor scoring results and performance")
        sys.exit(0)
    elif exit_code == 1:
        logger.warning("⚠️  WORKFLOW COMPLETED WITH CRITICAL ISSUES")
        logger.warning("⚠️  Review validation report and address critical issues")
        print(f"\n📋 Recommended Actions:")
        print(f"   1. Review validation report above")
        print(f"   2. Re-run workflow if needed: python3 scripts/kr_data_quality_workflow.py")
        print(f"   3. Check logs for detailed error information")
        sys.exit(1)
    else:
        logger.warning("⚠️  WORKFLOW COMPLETED WITH WARNINGS")
        logger.warning("⚠️  Data is usable but may have minor gaps")
        print(f"\n📋 Recommended Actions:")
        print(f"   1. Review validation report above")
        print(f"   2. Consider re-running specific steps if needed")
        print(f"   3. Proceed with caution to LayeredScoringEngine execution")
        sys.exit(2)


if __name__ == '__main__':
    main()
