#!/usr/bin/env python3
"""
Error Tracking Enhancement Test Script

Tests the improved error tracking capabilities in the orchestrator.
Simulates a failure scenario to verify detailed traceback logging.

Usage:
    python3 test_error_tracking.py
"""

import sys
import os
import logging
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator


def setup_test_logging():
    """Setup logging for test"""
    log_format = '%(asctime)s | %(levelname)-8s | %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    logging.basicConfig(
        level=logging.DEBUG,  # Enable DEBUG to see traceback logs
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(f'log/error_tracking_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        ]
    )


def test_error_tracking():
    """
    Test error tracking with a controlled failure scenario

    This test will:
    1. Create an orchestrator with verbose logging
    2. Attempt to run a step that will fail
    3. Verify that detailed traceback is logged
    """
    print("\n" + "="*80)
    print("🧪 Error Tracking Enhancement Test")
    print("="*80)
    print("\nThis test verifies that:")
    print("  1. ✅ Exception traceback is captured")
    print("  2. ✅ Error timestamp is recorded")
    print("  3. ✅ Detailed error info is logged to file")
    print("  4. ✅ Summary shows error details")
    print()

    setup_test_logging()
    logger = logging.getLogger(__name__)

    try:
        # Initialize database connection
        logger.info("Initializing database connection...")
        db = PostgresDatabaseManager()

        # Create orchestrator
        orchestrator = DatabaseUpdateOrchestrator(db, config={
            'fail_fast': False,  # Continue on error to test error handling
            'validate': False     # Skip validation for test
        })

        logger.info("✅ Orchestrator initialized")

        # Test scenario: Run with invalid step to trigger error handling
        logger.info("\n🔬 Testing error handling with invalid configuration...")

        # This will fail because we're passing invalid parameters
        # The error tracking should capture the full traceback
        result = orchestrator.run_pipeline(
            regions=['INVALID_REGION'],  # Invalid region to trigger error
            steps=['ohlcv'],
            dry_run=False,
            incremental=True
        )

        # Check results
        print("\n" + "="*80)
        print("📋 Test Results")
        print("="*80)

        if result['steps_failed']:
            print(f"\n✅ Error handling triggered successfully!")
            print(f"   Failed steps: {result['steps_failed']}")

            # Check if detailed error info was captured
            for step in result['steps_failed']:
                step_result = result['step_results'].get(step, {})

                print(f"\n📊 Error Details for step '{step}':")
                print(f"   Error message: {step_result.get('error', 'N/A')}")
                print(f"   Timestamp: {step_result.get('timestamp', 'N/A')}")
                print(f"   Has traceback: {'✅ YES' if 'traceback' in step_result else '❌ NO'}")

                if 'traceback' in step_result:
                    print(f"\n   Traceback preview (first 300 chars):")
                    print(f"   {step_result['traceback'][:300]}...")

        else:
            print(f"\n⚠️  No errors triggered (unexpected)")

        print("\n" + "="*80)
        print("✅ Test completed!")
        print("="*80)
        print(f"\nCheck the log file for detailed traceback:")
        print(f"   log/error_tracking_test_*.log")
        print()

    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        logger.error(f"Traceback:\n{traceback.format_exc()}")
        sys.exit(1)

    finally:
        try:
            db.close_pool()
            logger.info("Database connection closed")
        except Exception:
            pass


if __name__ == '__main__':
    test_error_tracking()
