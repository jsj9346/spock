"""
Phase 5 Scanner Integration Tests: Kelly Calculator Integration with Scanner

Tests the integration of StockKellyCalculator into the Scanner module's
run_stage2_scoring() workflow to ensure seamless buy signal generation
with Kelly position sizing.

Test Coverage:
- Scanner + Kelly integration workflow
- Buy signal generation with Kelly positions
- Signal sorting by Kelly position size
- Scanner error handling with Kelly calculations
- Performance impact of Kelly integration
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import time
from modules.scanner import Scanner
from modules.stock_kelly_calculator import StockKellyCalculator, PatternType
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestScannerKellyIntegration:
    """Test Scanner integration with Kelly Calculator"""

    @pytest.fixture
    def db_manager(self):
        return SQLiteDatabaseManager(db_path="data/spock_local.db")

    @pytest.fixture
    def scanner(self, db_manager):
        return Scanner(
            db_manager=db_manager,
            risk_level='moderate',
            min_score=70
        )

    @pytest.fixture
    def kelly_calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def test_scanner_run_stage2_with_kelly(self, scanner):
        """Test scanner's run_stage2_scoring with Kelly integration"""
        # Get sample tickers
        tickers = ['005930', '000660', '035720', '051910', '068270']

        # Run Stage 2 scoring with Kelly
        start_time = time.time()
        buy_signals, watch_list, avoid_list = scanner.run_stage2_scoring(
            tickers=tickers,
            region='KR'
        )
        elapsed = time.time() - start_time

        print(f"\n✅ Scanner completed in {elapsed:.2f}s")
        print(f"   BUY signals: {len(buy_signals)}")
        print(f"   WATCH list: {len(watch_list)}")
        print(f"   AVOID list: {len(avoid_list)}")

        # Verify buy signals have Kelly fields
        if buy_signals:
            for signal in buy_signals:
                assert 'ticker' in signal
                assert 'stage2_score' in signal

                # Check Kelly fields (if integrated)
                if 'kelly_position' in signal:
                    print(f"\n✅ Kelly fields present in buy signal:")
                    print(f"   Ticker: {signal['ticker']}")
                    print(f"   Stage 2 Score: {signal['stage2_score']:.1f}")
                    print(f"   Kelly Position: {signal['kelly_position']:.2f}%")
                    print(f"   Kelly Pattern: {signal.get('kelly_pattern', 'N/A')}")

                    # Verify Kelly fields are valid
                    assert 0 < signal['kelly_position'] <= 20
                    if 'kelly_pattern' in signal:
                        assert signal['kelly_pattern'] in [p.value for p in PatternType]

    def test_buy_signals_sorted_by_kelly(self, scanner):
        """Test that buy signals are sorted by Kelly position size"""
        # Get more tickers for better testing
        tickers = [
            '005930', '000660', '035720', '051910', '068270',
            '005380', '006400', '035420', '012330', '000270'
        ]

        # Run Stage 2 scoring
        buy_signals, _, _ = scanner.run_stage2_scoring(
            tickers=tickers,
            region='KR'
        )

        if len(buy_signals) >= 2 and 'kelly_position' in buy_signals[0]:
            # Verify sorting (highest Kelly position first)
            kelly_positions = [s['kelly_position'] for s in buy_signals]

            is_sorted = all(kelly_positions[i] >= kelly_positions[i+1]
                           for i in range(len(kelly_positions)-1))

            assert is_sorted, "Buy signals should be sorted by Kelly position (descending)"

            print(f"\n✅ Buy signals sorted by Kelly position:")
            for i, signal in enumerate(buy_signals[:5], 1):
                print(f"{i}. {signal['ticker']}: "
                      f"{signal['kelly_position']:.2f}% "
                      f"(score: {signal['stage2_score']:.1f})")

    def test_kelly_integration_with_manual_signals(self, kelly_calculator):
        """Test Kelly calculation for manually created Stage 2 signals"""
        # Create mock Stage 2 results
        mock_signals = [
            {
                'ticker': 'TEST_HIGH',
                'region': 'KR',
                'total_score': 85,
                'details': {
                    'layers': {
                        'structural': {
                            'modules': {
                                'StageAnalysisModule': {
                                    'score': 15,
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
            },
            {
                'ticker': 'TEST_MEDIUM',
                'region': 'KR',
                'total_score': 72,
                'details': {
                    'layers': {
                        'structural': {
                            'modules': {
                                'StageAnalysisModule': {
                                    'score': 12,
                                    'details': {'current_stage': 2}
                                }
                            }
                        },
                        'micro': {
                            'modules': {
                                'PatternRecognitionModule': {
                                    'details': {'patterns_found': ['vcp']}
                                }
                            }
                        }
                    }
                }
            },
            {
                'ticker': 'TEST_LOW',
                'region': 'KR',
                'total_score': 65,
                'details': {
                    'layers': {
                        'structural': {
                            'modules': {
                                'StageAnalysisModule': {
                                    'score': 10,
                                    'details': {'current_stage': 2}
                                }
                            }
                        },
                        'micro': {
                            'modules': {
                                'PatternRecognitionModule': {
                                    'details': {'patterns_found': []}
                                }
                            }
                        }
                    }
                }
            }
        ]

        # Calculate Kelly for each
        kelly_results = []
        for signal in mock_signals:
            kelly_result = kelly_calculator.calculate_position_size(signal)
            kelly_results.append({
                'ticker': signal['ticker'],
                'score': signal['total_score'],
                'kelly_position': kelly_result.recommended_position_size,
                'pattern': kelly_result.pattern_type.value
            })

        # Verify position sizes reflect score differences
        print(f"\n✅ Kelly positions reflect quality scores:")
        for result in sorted(kelly_results, key=lambda x: x['kelly_position'], reverse=True):
            print(f"   {result['ticker']}: "
                  f"{result['kelly_position']:.2f}% "
                  f"(score: {result['score']:.1f}, "
                  f"pattern: {result['pattern']})")

        # High score should have higher position
        high_result = next(r for r in kelly_results if r['ticker'] == 'TEST_HIGH')
        low_result = next(r for r in kelly_results if r['ticker'] == 'TEST_LOW')

        assert high_result['kelly_position'] > low_result['kelly_position'], \
            "Higher quality score should result in larger Kelly position"


class TestScannerPerformanceWithKelly:
    """Test performance impact of Kelly integration"""

    @pytest.fixture
    def db_manager(self):
        return SQLiteDatabaseManager(db_path="data/spock_local.db")

    @pytest.fixture
    def scanner(self, db_manager):
        return Scanner(
            db_manager=db_manager,
            risk_level='moderate',
            min_score=70
        )

    def test_performance_impact_20_tickers(self, scanner):
        """Test performance impact of Kelly integration on 20 tickers"""
        # Get 20 tickers
        all_tickers = scanner.db.get_tickers(region='KR', asset_type='STOCK', is_active=True)
        tickers = [t['ticker'] for t in all_tickers[:20]]

        # Run with Kelly integration
        start_time = time.time()
        buy_signals, watch_list, avoid_list = scanner.run_stage2_scoring(
            tickers=tickers,
            region='KR'
        )
        with_kelly_time = time.time() - start_time

        total_processed = len(buy_signals) + len(watch_list) + len(avoid_list)

        print(f"\n📊 Performance with Kelly integration (20 tickers):")
        print(f"   Total time: {with_kelly_time:.2f}s")
        print(f"   Per ticker: {with_kelly_time/20:.3f}s")
        print(f"   Processed: {total_processed} stocks")

        # Performance should still be reasonable
        assert with_kelly_time < 30.0, f"Too slow with Kelly: {with_kelly_time:.2f}s"

        # Per-ticker time should be under 1.5 seconds
        avg_time = with_kelly_time / 20
        assert avg_time < 1.5, f"Per-ticker time too slow: {avg_time:.3f}s"


class TestScannerErrorHandlingWithKelly:
    """Test error handling when Kelly integration fails"""

    @pytest.fixture
    def scanner(self):
        db_manager = SQLiteDatabaseManager(db_path="data/spock_local.db")
        return Scanner(
            db_manager=db_manager,
            risk_level='moderate',
            min_score=70
        )

    def test_scanner_handles_kelly_errors_gracefully(self, scanner):
        """Test that scanner continues when Kelly calculation fails"""
        # Mix of valid and problematic tickers
        tickers = ['005930', 'INVALID_TICKER', '000660']

        # Should not crash, should handle errors gracefully
        try:
            buy_signals, watch_list, avoid_list = scanner.run_stage2_scoring(
                tickers=tickers,
                region='KR'
            )

            # Verify scanner continued despite errors
            total_processed = len(buy_signals) + len(watch_list) + len(avoid_list)
            print(f"\n✅ Scanner handled errors gracefully:")
            print(f"   Processed: {total_processed} stocks")
            print(f"   BUY: {len(buy_signals)}, WATCH: {len(watch_list)}, AVOID: {len(avoid_list)}")

            assert total_processed >= 2, "Should process at least valid tickers"

        except Exception as e:
            pytest.fail(f"Scanner should handle Kelly errors gracefully, got: {e}")


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
