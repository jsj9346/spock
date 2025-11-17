#!/usr/bin/env python3
"""
Temporary script to update US OHLCV data with stale_days=3
This bypasses the default 7-day threshold to update US data aged 3+ days.
"""

import sys
import os

# Ensure we're in the spock directory
os.chdir('/Users/13ruce/spock')

from modules.database.postgresql_manager import PostgreSQLManager
from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator
from datetime import datetime

def main():
    """Update US OHLCV with stale_days=3"""

    print("=" * 80)
    print("🚀 US OHLCV Update with stale_days=3")
    print("=" * 80)
    print()
    print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Initialize database and orchestrator
    db = PostgreSQLManager()
    orchestrator = DatabaseUpdateOrchestrator(db, config={
        'validate': True,
        'checkpoint_enabled': True
    })

    # Run pipeline with stale_days=3
    print("📊 Configuration:")
    print("  - Region: US")
    print("  - Steps: ohlcv")
    print("  - Mode: incremental")
    print("  - Stale Days: 3 (default is 7)")
    print()
    print("This will update only US tickers with data older than 3 days.")
    print()

    try:
        result = orchestrator.run_pipeline(
            regions=['US'],
            steps=['ohlcv'],
            dry_run=False,
            incremental=True,
            stale_days=3  # Override default 7
        )

        print()
        print("=" * 80)
        print("✅ Update Complete!")
        print("=" * 80)
        print()
        print(f"End Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duration: {result.get('total_duration', 0):.1f}s")
        print()

        if result['steps_completed']:
            print(f"✅ Completed: {result['steps_completed']}")
        if result['steps_failed']:
            print(f"❌ Failed: {result['steps_failed']}")

        return 0 if not result['steps_failed'] else 1

    except Exception as e:
        print()
        print("=" * 80)
        print(f"❌ Error: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
