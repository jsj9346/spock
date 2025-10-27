"""
Phase 5 Integration Tests: Stage 2 → Kelly Calculator Workflow

Tests the integration between LayeredScoringEngine (Stage 2) and StockKellyCalculator
to ensure seamless data flow and correct position sizing calculations.

Test Coverage:
- Stage 2 scoring → Kelly calculator workflow
- Batch processing (10, 50, 100 tickers)
- Database consistency checks
- Error recovery and edge cases
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import sqlite3
import asyncio
from modules.stock_kelly_calculator import (
    StockKellyCalculator,
    PatternType,
    RiskLevel
)
from modules.integrated_scoring_system import IntegratedScoringSystem
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestStage2ToKellyWorkflow:
    """Test Stage 2 → Kelly integration workflow"""

    @pytest.fixture
    def db_manager(self):
        return SQLiteDatabaseManager(db_path="data/spock_local.db")

    @pytest.fixture
    def scoring_engine(self):
        return IntegratedScoringSystem(db_path="data/spock_local.db")

    @pytest.fixture
    def kelly_calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def test_stage2_to_kelly_single_ticker(self, scoring_engine, kelly_calculator):
        """Test single ticker workflow from Stage 2 scoring to Kelly calculation"""
        ticker = '005930'  # Samsung Electronics

        # Step 1: Run Stage 2 scoring (async)
        stage2_result = asyncio.run(scoring_engine.analyze_ticker(ticker))

        assert stage2_result is not None
        assert 'total_score' in stage2_result
        assert 'details' in stage2_result

        # Step 2: Calculate Kelly position
        kelly_result = kelly_calculator.calculate_position_size(stage2_result)

        # Verify Kelly result
        assert kelly_result.ticker == ticker
        assert kelly_result.region == region
        assert kelly_result.pattern_type in PatternType
        assert 0 <= kelly_result.recommended_position_size <= 15.0
        assert kelly_result.quality_score == stage2_result['total_score']

        # Step 3: Verify database persistence
        conn = sqlite3.connect("data/spock_local.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticker, pattern_type, recommended_position_size
            FROM kelly_sizing
            WHERE ticker = ?
            ORDER BY calculation_date DESC
            LIMIT 1
        """, (ticker,))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == ticker
        assert row[2] == kelly_result.recommended_position_size

    def test_stage2_to_kelly_batch_10(self, db_manager, scoring_engine, kelly_calculator):
        """Test batch processing for 10 tickers"""
        # Get 10 active tickers from database
        tickers = db_manager.get_tickers(region='KR', asset_type='STOCK', is_active=True)[:10]

        assert len(tickers) >= 10, "Need at least 10 tickers in database"

        results = []
        for ticker_data in tickers[:10]:
            ticker = ticker_data['ticker']

            # Stage 2 scoring
            stage2_result = scoring_engine.calculate_comprehensive_score(
                ticker=ticker,
                region='KR'
            )

            if stage2_result:
                # Kelly calculation
                kelly_result = kelly_calculator.calculate_position_size(stage2_result)
                results.append(kelly_result)

        # Verify batch results
        assert len(results) >= 5, "Should have at least 5 successful calculations"

        for result in results:
            assert result.ticker is not None
            assert 0 <= result.recommended_position_size <= 15.0
            assert result.pattern_type in PatternType

    def test_stage2_to_kelly_batch_50(self, db_manager, scoring_engine, kelly_calculator):
        """Test batch processing for 50 tickers"""
        # Get 50 active tickers
        tickers = db_manager.get_tickers(region='KR', asset_type='STOCK', is_active=True)[:50]

        assert len(tickers) >= 50, "Need at least 50 tickers in database"

        results = []
        errors = []

        for ticker_data in tickers[:50]:
            ticker = ticker_data['ticker']

            try:
                # Stage 2 scoring
                stage2_result = scoring_engine.calculate_comprehensive_score(
                    ticker=ticker,
                    region='KR'
                )

                if stage2_result:
                    # Kelly calculation
                    kelly_result = kelly_calculator.calculate_position_size(stage2_result)
                    results.append(kelly_result)
            except Exception as e:
                errors.append({'ticker': ticker, 'error': str(e)})

        # Verify batch results
        success_rate = len(results) / 50
        assert success_rate >= 0.8, f"Success rate too low: {success_rate:.2%}"

        # Verify error handling
        if errors:
            print(f"Errors encountered: {len(errors)}")
            for error in errors[:3]:  # Print first 3 errors
                print(f"  {error['ticker']}: {error['error']}")

    def test_stage2_to_kelly_batch_100(self, db_manager, scoring_engine, kelly_calculator):
        """Test batch processing for 100 tickers (stress test)"""
        # Get 100 active tickers
        tickers = db_manager.get_tickers(region='KR', asset_type='STOCK', is_active=True)[:100]

        assert len(tickers) >= 100, "Need at least 100 tickers in database"

        results = []
        errors = []
        pattern_counts = {}

        for ticker_data in tickers[:100]:
            ticker = ticker_data['ticker']

            try:
                # Stage 2 scoring
                stage2_result = scoring_engine.calculate_comprehensive_score(
                    ticker=ticker,
                    region='KR'
                )

                if stage2_result:
                    # Kelly calculation
                    kelly_result = kelly_calculator.calculate_position_size(stage2_result)
                    results.append(kelly_result)

                    # Track pattern distribution
                    pattern = kelly_result.pattern_type.value
                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

            except Exception as e:
                errors.append({'ticker': ticker, 'error': str(e)})

        # Verify batch results
        success_rate = len(results) / 100
        assert success_rate >= 0.75, f"Success rate too low: {success_rate:.2%}"

        # Verify pattern distribution
        print(f"\nPattern Distribution (100 tickers):")
        for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {pattern}: {count} ({count/len(results)*100:.1f}%)")


class TestKellyErrorHandling:
    """Test Kelly calculator error handling and edge cases"""

    @pytest.fixture
    def kelly_calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def test_kelly_with_missing_stage2_data(self, kelly_calculator):
        """Test Kelly calculation with incomplete Stage 2 data"""
        incomplete_result = {
            'ticker': 'TEST_MISSING',
            'region': 'KR',
            'total_score': 75,
            # Missing 'details' key
        }

        # Should not crash, should return DEFAULT pattern
        kelly_result = kelly_calculator.calculate_position_size(incomplete_result)

        assert kelly_result.ticker == 'TEST_MISSING'
        assert kelly_result.pattern_type == PatternType.DEFAULT
        assert kelly_result.recommended_position_size > 0

    def test_kelly_with_invalid_score(self, kelly_calculator):
        """Test Kelly calculation with invalid quality score"""
        invalid_score_result = {
            'ticker': 'TEST_INVALID',
            'region': 'KR',
            'total_score': -10,  # Invalid negative score
            'details': {
                'layers': {
                    'structural': {
                        'modules': {
                            'StageAnalysisModule': {
                                'score': 0,
                                'details': {'current_stage': 1}
                            }
                        }
                    }
                }
            }
        }

        # Should handle gracefully with minimum position
        kelly_result = kelly_calculator.calculate_position_size(invalid_score_result)

        assert kelly_result.ticker == 'TEST_INVALID'
        assert kelly_result.recommended_position_size <= 5.0  # Should be very small


class TestDatabaseConsistency:
    """Test database consistency after Kelly calculations"""

    @pytest.fixture
    def db_manager(self):
        return SQLiteDatabaseManager(db_path="data/spock_local.db")

    @pytest.fixture
    def kelly_calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def test_database_consistency_after_batch(self, db_manager, kelly_calculator):
        """Test database consistency after batch Kelly calculations"""
        # Get 20 tickers for testing
        tickers = db_manager.get_tickers(region='KR', asset_type='STOCK', is_active=True)[:20]

        # Clear existing Kelly records for these tickers
        conn = sqlite3.connect("data/spock_local.db")
        cursor = conn.cursor()

        for ticker_data in tickers[:20]:
            ticker = ticker_data['ticker']

            # Create mock Stage 2 result
            stage2_result = {
                'ticker': ticker,
                'region': 'KR',
                'total_score': 70,
                'details': {
                    'layers': {
                        'structural': {
                            'modules': {
                                'StageAnalysisModule': {
                                    'score': 12,
                                    'details': {'current_stage': 2}
                                }
                            }
                        }
                    }
                }
            }

            # Calculate Kelly
            kelly_calculator.calculate_position_size(stage2_result)

        # Verify database consistency
        cursor.execute("""
            SELECT COUNT(DISTINCT ticker)
            FROM kelly_sizing
            WHERE ticker IN ({})
        """.format(','.join('?' * len(tickers[:20]))),
        [t['ticker'] for t in tickers[:20]])

        count = cursor.fetchone()[0]
        conn.close()

        assert count >= 15, f"Database should have records for most tickers, got {count}"

    def test_kelly_results_retrieval(self, db_manager):
        """Test retrieval of Kelly results from database"""
        # Get latest Kelly calculations
        conn = sqlite3.connect("data/spock_local.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ticker, pattern_type, win_rate, kelly_pct, recommended_position_size
            FROM kelly_sizing
            ORDER BY calculation_date DESC
            LIMIT 10
        """)

        rows = cursor.fetchall()
        conn.close()

        assert len(rows) > 0, "Should have Kelly records in database"

        for row in rows:
            ticker, pattern, win_rate, kelly_pct, position_size = row

            # Verify data integrity
            assert ticker is not None
            assert pattern in [p.value for p in PatternType]
            assert 0 <= win_rate <= 1
            assert kelly_pct >= 0
            assert 0 <= position_size <= 20


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
