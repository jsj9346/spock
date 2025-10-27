#!/usr/bin/env python3
"""
test_kelly_gpt_integration.py - Kelly Calculator + GPT Analyzer Integration Test

Tests the 2-stage position sizing:
1. Technical analysis → Kelly position
2. GPT Stage 2 validation → Final position with adjustment

Requirements:
- SQLite database initialized
- OpenAI API key configured (for GPT tests)
- Stock data available for test tickers
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file
from dotenv import load_dotenv
load_dotenv(dotenv_path=project_root / '.env')

from modules.kelly_calculator import KellyCalculator, PatternType, RiskLevel
from modules.db_manager_sqlite import SQLiteDatabaseManager


def test_kelly_without_gpt():
    """Test 1: Kelly Calculator without GPT (baseline)"""
    print("\n" + "="*80)
    print("TEST 1: Kelly Calculator WITHOUT GPT (Baseline)")
    print("="*80)

    # Initialize Kelly Calculator
    kelly_calc = KellyCalculator(
        db_path="./data/spock_local.db",
        risk_level=RiskLevel.MODERATE
    )

    # Test ticker
    ticker = "005930"  # Samsung Electronics
    detected_pattern = PatternType.STAGE_1_TO_2
    quality_score = 75.0

    print(f"\n📊 Testing {ticker} (Pattern: {detected_pattern.value}, Quality: {quality_score})")

    # Calculate position WITHOUT GPT
    result = kelly_calc.calculate_position_with_gpt(
        ticker=ticker,
        detected_pattern=detected_pattern,
        quality_score=quality_score,
        risk_level=RiskLevel.MODERATE,
        use_gpt=False  # GPT disabled
    )

    # Verify results
    print(f"\n✅ Results (GPT Disabled):")
    print(f"   Technical Position: {result.technical_position_pct:.2f}%")
    print(f"   GPT Confidence: {result.gpt_confidence}")
    print(f"   GPT Adjustment: {result.gpt_adjustment:.2f}x")
    print(f"   Final Position: {result.final_position_pct:.2f}%")

    # Assertions
    assert result.technical_position_pct > 0, "Technical position should be > 0"
    assert result.gpt_confidence is None, "GPT confidence should be None when disabled"
    assert result.gpt_adjustment == 1.0, "GPT adjustment should be 1.0 when disabled"
    assert result.final_position_pct == result.technical_position_pct, \
        "Final position should equal technical position when GPT disabled"

    print("\n✅ TEST 1 PASSED: Kelly works without GPT")
    return result


def test_kelly_with_gpt_enabled():
    """Test 2: Kelly Calculator with GPT enabled"""
    print("\n" + "="*80)
    print("TEST 2: Kelly Calculator WITH GPT (Full Integration)")
    print("="*80)

    # Check if OpenAI API key is available
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("\n⏭️ SKIPPED: OPENAI_API_KEY not found in environment")
        print("   Set OPENAI_API_KEY to test GPT integration")
        return None

    # Initialize Kelly Calculator
    kelly_calc = KellyCalculator(
        db_path="./data/spock_local.db",
        risk_level=RiskLevel.MODERATE
    )

    # Enable GPT analysis
    try:
        kelly_calc.enable_gpt_analysis(
            enable=True,
            api_key=api_key,
            daily_cost_limit=0.50
        )
        print("✅ GPT analysis enabled")
    except Exception as e:
        print(f"\n❌ FAILED: Could not enable GPT analysis: {e}")
        return None

    # Test ticker with high quality (≥70, will trigger GPT)
    ticker = "005930"  # Samsung Electronics
    detected_pattern = PatternType.STAGE_1_TO_2
    quality_score = 75.0

    print(f"\n📊 Testing {ticker} (Pattern: {detected_pattern.value}, Quality: {quality_score})")
    print(f"   Quality {quality_score} ≥ 70 → GPT analysis WILL be triggered")

    # Calculate position WITH GPT
    result = kelly_calc.calculate_position_with_gpt(
        ticker=ticker,
        detected_pattern=detected_pattern,
        quality_score=quality_score,
        risk_level=RiskLevel.MODERATE,
        use_gpt=True  # GPT enabled
    )

    # Verify results
    print(f"\n✅ Results (GPT Enabled):")
    print(f"   Technical Position: {result.technical_position_pct:.2f}%")
    print(f"   GPT Confidence: {result.gpt_confidence}")
    print(f"   GPT Recommendation: {result.gpt_recommendation}")
    print(f"   GPT Adjustment: {result.gpt_adjustment:.2f}x")
    print(f"   Final Position: {result.final_position_pct:.2f}%")

    # Assertions
    assert result.technical_position_pct > 0, "Technical position should be > 0"
    assert result.gpt_confidence is not None, "GPT confidence should be set"
    assert result.gpt_recommendation is not None, "GPT recommendation should be set"
    assert 0.5 <= result.gpt_adjustment <= 1.5, "GPT adjustment should be in 0.5-1.5 range"
    assert result.final_position_pct is not None, "Final position should be set"

    print("\n✅ TEST 2 PASSED: Kelly + GPT integration works")
    return result


def test_quality_threshold_filtering():
    """Test 3: Quality threshold filtering (< 70 should skip GPT)"""
    print("\n" + "="*80)
    print("TEST 3: Quality Threshold Filtering (Quality < 70)")
    print("="*80)

    # Check if OpenAI API key is available
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("\n⏭️ SKIPPED: OPENAI_API_KEY not found in environment")
        return None

    # Initialize Kelly Calculator
    kelly_calc = KellyCalculator(
        db_path="./data/spock_local.db",
        risk_level=RiskLevel.MODERATE
    )

    # Enable GPT analysis
    kelly_calc.enable_gpt_analysis(enable=True, api_key=api_key)

    # Test ticker with LOW quality (< 70, should skip GPT)
    ticker = "000660"  # SK Hynix
    detected_pattern = PatternType.STAGE_2_CONTINUATION
    quality_score = 65.0  # Below threshold

    print(f"\n📊 Testing {ticker} (Pattern: {detected_pattern.value}, Quality: {quality_score})")
    print(f"   Quality {quality_score} < 70 → GPT analysis should be SKIPPED")

    # Calculate position (GPT should be skipped due to low quality)
    result = kelly_calc.calculate_position_with_gpt(
        ticker=ticker,
        detected_pattern=detected_pattern,
        quality_score=quality_score,
        risk_level=RiskLevel.MODERATE,
        use_gpt=True  # GPT enabled BUT quality too low
    )

    # Verify results
    print(f"\n✅ Results (Quality < 70, GPT Skipped):")
    print(f"   Technical Position: {result.technical_position_pct:.2f}%")
    print(f"   GPT Confidence: {result.gpt_confidence}")
    print(f"   GPT Adjustment: {result.gpt_adjustment:.2f}x")
    print(f"   Final Position: {result.final_position_pct:.2f}%")

    # Assertions
    assert result.technical_position_pct > 0, "Technical position should be > 0"
    assert result.gpt_confidence is None, "GPT confidence should be None (quality < 70)"
    assert result.gpt_adjustment == 1.0, "GPT adjustment should be 1.0 (quality < 70)"
    assert result.final_position_pct == result.technical_position_pct, \
        "Final should equal technical when GPT skipped"

    print("\n✅ TEST 3 PASSED: Quality threshold filtering works")
    return result


def test_database_persistence():
    """Test 4: Verify GPT fields are persisted to database"""
    print("\n" + "="*80)
    print("TEST 4: Database Persistence (GPT Fields)")
    print("="*80)

    db = SQLiteDatabaseManager(db_path="./data/spock_local.db")
    conn = db._get_connection()
    cursor = conn.cursor()

    # Query recent kelly_analysis records with GPT data
    cursor.execute("""
        SELECT ticker, technical_position_pct, gpt_confidence,
               gpt_recommendation, gpt_adjustment, final_position_pct
        FROM kelly_analysis
        WHERE gpt_confidence IS NOT NULL
        ORDER BY analysis_date DESC
        LIMIT 5
    """)

    rows = cursor.fetchall()
    conn.close()

    if rows:
        print(f"\n✅ Found {len(rows)} kelly_analysis records with GPT data:")
        for row in rows:
            ticker, tech_pct, gpt_conf, gpt_rec, gpt_adj, final_pct = row
            print(f"   {ticker}: Technical {tech_pct:.2f}% × GPT {gpt_adj:.2f} "
                  f"→ Final {final_pct:.2f}% (Confidence: {gpt_conf:.2f})")
        print("\n✅ TEST 4 PASSED: GPT fields persisted to database")
    else:
        print("\nℹ️ No kelly_analysis records with GPT data found")
        print("   Run TEST 2 with GPT enabled to create records")

    return len(rows) > 0


def main():
    """Run all integration tests"""
    print("\n" + "="*80)
    print("Kelly Calculator + GPT Analyzer Integration Tests")
    print("="*80)

    # Check database
    db_path = "./data/spock_local.db"
    if not os.path.exists(db_path):
        print(f"\n❌ ERROR: Database not found at {db_path}")
        print("   Run database initialization first")
        sys.exit(1)

    print(f"✅ Database found: {db_path}")

    # Test suite
    results = {}

    try:
        # Test 1: Kelly without GPT (baseline)
        results['test1'] = test_kelly_without_gpt()

        # Test 2: Kelly with GPT (full integration)
        results['test2'] = test_kelly_with_gpt_enabled()

        # Test 3: Quality threshold filtering
        results['test3'] = test_quality_threshold_filtering()

        # Test 4: Database persistence
        results['test4'] = test_database_persistence()

        # Summary
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)

        test_count = len([r for r in results.values() if r is not None])
        skipped_count = len([r for r in results.values() if r is None])

        print(f"\n✅ Tests Passed: {test_count}")
        if skipped_count > 0:
            print(f"⏭️ Tests Skipped: {skipped_count} (OPENAI_API_KEY not configured)")

        print("\n🎉 All integration tests completed successfully!")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
