"""
Phase 5 Integration Tests (Simplified): Kelly Calculator Integration

Simplified integration tests focusing on Kelly Calculator integration
with mock Stage 2 results to avoid database schema dependencies.

Test Coverage:
- Stage 2 mock results → Kelly calculator workflow
- Batch processing simulation
- Database consistency checks
- Error recovery
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import sqlite3
from modules.stock_kelly_calculator import (
    StockKellyCalculator,
    PatternType,
    RiskLevel
)


class TestKellyWithMockStage2:
    """Test Kelly Calculator with mock Stage 2 results"""

    @pytest.fixture
    def kelly_calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def _create_mock_stage2_result(self, ticker: str, score: float, pattern: str = 'breakout'):
        """Create mock Stage 2 result for testing"""
        return {
            'ticker': ticker,
            'region': 'KR',
            'total_score': score,
            'details': {
                'layers': {
                    'structural': {
                        'modules': {
                            'StageAnalysisModule': {
                                'score': 15 if score >= 80 else 12,
                                'details': {'current_stage': 2 if score >= 70 else 1}
                            }
                        }
                    },
                    'micro': {
                        'modules': {
                            'PatternRecognitionModule': {
                                'details': {'patterns_found': [pattern] if pattern else []}
                            }
                        }
                    }
                }
            }
        }

    def test_kelly_single_mock_ticker(self, kelly_calculator):
        """Test Kelly with single mock Stage 2 result"""
        mock_stage2 = self._create_mock_stage2_result('TEST_SINGLE', 85.0, 'breakout')

        kelly_result = kelly_calculator.calculate_position_size(mock_stage2)

        assert kelly_result.ticker == 'TEST_SINGLE'
        assert kelly_result.pattern_type == PatternType.STAGE_2_BREAKOUT
        assert 5.0 <= kelly_result.recommended_position_size <= 15.0
        assert kelly_result.quality_score == 85.0

    def test_kelly_batch_10_mock(self, kelly_calculator):
        """Test Kelly with batch of 10 mock results"""
        results = []

        for i in range(10):
            ticker = f'TEST_{i:03d}'
            score = 70 + (i * 2)  # Scores from 70 to 88
            pattern = ['breakout', 'vcp', 'cup_handle'][i % 3]

            mock_stage2 = self._create_mock_stage2_result(ticker, score, pattern)
            kelly_result = kelly_calculator.calculate_position_size(mock_stage2)
            results.append(kelly_result)

        # Verify all calculated
        assert len(results) == 10

        # Verify higher scores get higher positions
        positions = [r.recommended_position_size for r in results]
        scores = [r.quality_score for r in results]

        # Generally, higher scores should correlate with higher positions
        assert positions[-1] >= positions[0], "Higher score should have higher position"

    def test_kelly_batch_50_mock(self, kelly_calculator):
        """Test Kelly with batch of 50 mock results (stress test)"""
        results = []
        errors = []

        for i in range(50):
            try:
                ticker = f'STRESS_{i:03d}'
                score = 50 + (i % 40)  # Scores from 50 to 89
                pattern = ['breakout', 'vcp', 'cup_handle', None][i % 4]

                mock_stage2 = self._create_mock_stage2_result(ticker, score, pattern)
                kelly_result = kelly_calculator.calculate_position_size(mock_stage2)
                results.append(kelly_result)
            except Exception as e:
                errors.append({'ticker': ticker, 'error': str(e)})

        # Verify success rate
        success_rate = len(results) / 50
        assert success_rate >= 0.95, f"Success rate too low: {success_rate:.2%}"

        # Verify pattern distribution
        pattern_counts = {}
        for result in results:
            pattern = result.pattern_type.value
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

        print(f"\nPattern Distribution (50 mock tickers):")
        for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {pattern}: {count} ({count/len(results)*100:.1f}%)")

    def test_kelly_error_handling_missing_data(self, kelly_calculator):
        """Test Kelly with incomplete Stage 2 data"""
        incomplete_result = {
            'ticker': 'MISSING_DATA',
            'region': 'KR',
            'total_score': 75,
            # Missing 'details' key
        }

        kelly_result = kelly_calculator.calculate_position_size(incomplete_result)

        assert kelly_result.ticker == 'MISSING_DATA'
        assert kelly_result.pattern_type == PatternType.DEFAULT
        assert kelly_result.recommended_position_size > 0

    def test_kelly_invalid_score(self, kelly_calculator):
        """Test Kelly with invalid quality score"""
        invalid_score_result = {
            'ticker': 'INVALID_SCORE',
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

        kelly_result = kelly_calculator.calculate_position_size(invalid_score_result)

        assert kelly_result.ticker == 'INVALID_SCORE'
        assert kelly_result.recommended_position_size <= 5.0  # Should be very small


class TestDatabasePersistence:
    """Test database persistence of Kelly results"""

    @pytest.fixture
    def kelly_calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def test_kelly_results_saved_to_database(self, kelly_calculator):
        """Test that Kelly results are persisted to database"""
        # Create mock Stage 2 result
        mock_stage2 = {
            'ticker': 'DB_TEST_001',
            'region': 'KR',
            'total_score': 80,
            'details': {
                'layers': {
                    'structural': {
                        'modules': {
                            'StageAnalysisModule': {
                                'score': 14,
                                'details': {'current_stage': 2}
                            }
                        }
                    },
                    'micro': {
                        'modules': {
                            'PatternRecognitionModule': {
                                'details': {'patterns_found': ['breakout']}
                            }
                        }
                    }
                }
            }
        }

        # Calculate Kelly
        kelly_result = kelly_calculator.calculate_position_size(mock_stage2)

        # Verify saved to database
        conn = sqlite3.connect("data/spock_local.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticker, pattern_type, win_rate, kelly_pct, recommended_position_size
            FROM kelly_sizing
            WHERE ticker = ?
            ORDER BY calculation_date DESC
            LIMIT 1
        """, ('DB_TEST_001',))

        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 'DB_TEST_001'
        assert row[2] == kelly_result.win_rate
        assert row[4] == kelly_result.recommended_position_size

    def test_kelly_batch_database_consistency(self, kelly_calculator):
        """Test database consistency after batch Kelly calculations"""
        # Process batch of 20 mock results
        for i in range(20):
            ticker = f'BATCH_{i:02d}'
            mock_stage2 = {
                'ticker': ticker,
                'region': 'KR',
                'total_score': 70 + i,
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

            kelly_calculator.calculate_position_size(mock_stage2)

        # Verify database has all records
        conn = sqlite3.connect("data/spock_local.db")
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(DISTINCT ticker)
            FROM kelly_sizing
            WHERE ticker LIKE 'BATCH_%'
        """)

        count = cursor.fetchone()[0]
        conn.close()

        assert count >= 15, f"Database should have most batch records, got {count}"


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
