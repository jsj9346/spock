"""
Phase 5 E2E Pipeline Tests: Complete Stage 2 → Kelly → Trading Decision Flow

Tests the end-to-end pipeline from data collection through Stage 2 scoring,
Kelly calculation, and trading decision generation.

Test Coverage:
- Complete pipeline workflow (data → scoring → Kelly → decision)
- Multi-ticker batch processing
- Buy/Watch/Avoid signal generation with Kelly positions
- Performance benchmarks
- Error recovery across pipeline stages
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import time
from typing import List, Dict
from modules.integrated_scoring_system import LayeredScoringEngine
from modules.stock_kelly_calculator import (
    StockKellyCalculator,
    PatternType,
    RiskLevel
)
from modules.db_manager_sqlite import SQLiteDatabaseManager


class TestE2EPipeline:
    """Test complete end-to-end pipeline"""

    @pytest.fixture
    def db_manager(self):
        return SQLiteDatabaseManager(db_path="data/spock_local.db")

    @pytest.fixture
    def scoring_engine(self, db_manager):
        return LayeredScoringEngine(db_manager=db_manager)

    @pytest.fixture
    def kelly_calculator(self):
        return StockKellyCalculator(
            db_path="data/spock_local.db",
            risk_level=RiskLevel.MODERATE
        )

    def test_complete_pipeline_single_ticker(self, db_manager, scoring_engine, kelly_calculator):
        """Test complete pipeline for single ticker"""
        ticker = '005930'  # Samsung Electronics

        # Step 1: Verify OHLCV data exists
        ohlcv_data = db_manager.get_ohlcv_data(ticker=ticker, region='KR', limit=250)
        assert len(ohlcv_data) >= 200, "Need at least 200 days of OHLCV data"

        # Step 2: Run Stage 2 scoring
        start_time = time.time()
        stage2_result = scoring_engine.calculate_comprehensive_score(
            ticker=ticker,
            region='KR'
        )
        stage2_time = time.time() - start_time

        assert stage2_result is not None
        assert 'total_score' in stage2_result
        print(f"\n✅ Stage 2 scoring completed in {stage2_time:.3f}s")
        print(f"   Score: {stage2_result['total_score']:.1f}/100")

        # Step 3: Calculate Kelly position
        start_time = time.time()
        kelly_result = kelly_calculator.calculate_position_size(stage2_result)
        kelly_time = time.time() - start_time

        assert kelly_result.ticker == ticker
        assert kelly_result.recommended_position_size > 0
        print(f"✅ Kelly calculation completed in {kelly_time:.3f}s")
        print(f"   Pattern: {kelly_result.pattern_type.value}")
        print(f"   Position: {kelly_result.recommended_position_size:.2f}%")

        # Step 4: Generate trading decision
        decision = self._generate_trading_decision(stage2_result, kelly_result)

        assert decision['action'] in ['BUY', 'WATCH', 'AVOID']
        print(f"✅ Trading decision: {decision['action']}")
        print(f"   Reason: {decision['reason']}")

        # Total pipeline time
        total_time = stage2_time + kelly_time
        assert total_time < 2.0, f"Pipeline too slow: {total_time:.3f}s"

    def test_complete_pipeline_batch_20(self, db_manager, scoring_engine, kelly_calculator):
        """Test complete pipeline for 20 tickers"""
        # Get 20 tickers with sufficient data
        all_tickers = db_manager.get_tickers(region='KR', asset_type='STOCK', is_active=True)

        valid_tickers = []
        for ticker_data in all_tickers:
            ticker = ticker_data['ticker']
            ohlcv_data = db_manager.get_ohlcv_data(ticker=ticker, region='KR', limit=250)
            if len(ohlcv_data) >= 200:
                valid_tickers.append(ticker)
            if len(valid_tickers) >= 20:
                break

        assert len(valid_tickers) >= 20, "Need at least 20 tickers with sufficient data"

        # Process batch
        start_time = time.time()
        results = []

        for ticker in valid_tickers[:20]:
            # Stage 2 scoring
            stage2_result = scoring_engine.calculate_comprehensive_score(
                ticker=ticker,
                region='KR'
            )

            if stage2_result:
                # Kelly calculation
                kelly_result = kelly_calculator.calculate_position_size(stage2_result)

                # Trading decision
                decision = self._generate_trading_decision(stage2_result, kelly_result)

                results.append({
                    'ticker': ticker,
                    'stage2_score': stage2_result['total_score'],
                    'kelly_position': kelly_result.recommended_position_size,
                    'pattern': kelly_result.pattern_type.value,
                    'action': decision['action']
                })

        batch_time = time.time() - start_time

        # Verify results
        assert len(results) >= 18, f"Success rate too low: {len(results)}/20"

        # Performance check
        avg_time_per_ticker = batch_time / len(results)
        assert avg_time_per_ticker < 1.0, f"Too slow per ticker: {avg_time_per_ticker:.3f}s"

        # Print summary
        print(f"\n✅ Batch processing completed in {batch_time:.2f}s")
        print(f"   Average per ticker: {avg_time_per_ticker:.3f}s")
        print(f"   Success rate: {len(results)}/20")

        # Action distribution
        buy_count = sum(1 for r in results if r['action'] == 'BUY')
        watch_count = sum(1 for r in results if r['action'] == 'WATCH')
        avoid_count = sum(1 for r in results if r['action'] == 'AVOID')

        print(f"   BUY: {buy_count}, WATCH: {watch_count}, AVOID: {avoid_count}")

    def test_buy_signals_with_kelly_positions(self, db_manager, scoring_engine, kelly_calculator):
        """Test BUY signal generation with Kelly positions"""
        # Get tickers
        tickers = db_manager.get_tickers(region='KR', asset_type='STOCK', is_active=True)[:30]

        buy_signals = []

        for ticker_data in tickers:
            ticker = ticker_data['ticker']

            # Check data availability
            ohlcv_data = db_manager.get_ohlcv_data(ticker=ticker, region='KR', limit=250)
            if len(ohlcv_data) < 200:
                continue

            # Stage 2 scoring
            stage2_result = scoring_engine.calculate_comprehensive_score(
                ticker=ticker,
                region='KR'
            )

            if stage2_result and stage2_result['total_score'] >= 70:
                # Kelly calculation
                kelly_result = kelly_calculator.calculate_position_size(stage2_result)

                # Generate BUY signal
                buy_signals.append({
                    'ticker': ticker,
                    'name': ticker_data.get('name', 'Unknown'),
                    'stage2_score': stage2_result['total_score'],
                    'kelly_position': kelly_result.recommended_position_size,
                    'kelly_pattern': kelly_result.pattern_type.value,
                    'kelly_reasoning': self._format_kelly_reasoning(kelly_result)
                })

        # Sort by Kelly position (highest first)
        buy_signals.sort(key=lambda x: x['kelly_position'], reverse=True)

        # Verify BUY signals
        assert len(buy_signals) > 0, "Should have at least some BUY signals"

        print(f"\n✅ Generated {len(buy_signals)} BUY signals with Kelly positions:")
        for i, signal in enumerate(buy_signals[:5], 1):
            print(f"\n{i}. {signal['ticker']} ({signal['name']})")
            print(f"   Stage 2 Score: {signal['stage2_score']:.1f}/100")
            print(f"   Kelly Position: {signal['kelly_position']:.2f}%")
            print(f"   Pattern: {signal['kelly_pattern']}")
            print(f"   Reasoning: {signal['kelly_reasoning']}")

    def _generate_trading_decision(self, stage2_result: Dict, kelly_result) -> Dict:
        """Generate trading decision based on Stage 2 and Kelly results"""
        score = stage2_result['total_score']
        position = kelly_result.recommended_position_size

        if score >= 70 and position >= 5.0:
            return {
                'action': 'BUY',
                'reason': f"Strong signal (score: {score:.1f}, position: {position:.1f}%)"
            }
        elif score >= 60 and position >= 3.0:
            return {
                'action': 'WATCH',
                'reason': f"Moderate signal (score: {score:.1f}, position: {position:.1f}%)"
            }
        else:
            return {
                'action': 'AVOID',
                'reason': f"Weak signal (score: {score:.1f}, position: {position:.1f}%)"
            }

    def _format_kelly_reasoning(self, kelly_result) -> str:
        """Format Kelly reasoning for display"""
        return (f"{kelly_result.pattern_type.value} pattern "
                f"(win rate: {kelly_result.win_rate*100:.0f}%, "
                f"quality: {kelly_result.quality_multiplier:.1f}x)")


class TestPipelinePerformance:
    """Test pipeline performance benchmarks"""

    @pytest.fixture
    def db_manager(self):
        return SQLiteDatabaseManager(db_path="data/spock_local.db")

    @pytest.fixture
    def scoring_engine(self, db_manager):
        return LayeredScoringEngine(db_manager=db_manager)

    @pytest.fixture
    def kelly_calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def test_pipeline_performance_single_ticker(self, db_manager, scoring_engine, kelly_calculator):
        """Benchmark single ticker pipeline performance"""
        ticker = '005930'

        # Run 10 iterations
        times = []
        for _ in range(10):
            start_time = time.time()

            # Stage 2
            stage2_result = scoring_engine.calculate_comprehensive_score(ticker, 'KR')

            # Kelly
            if stage2_result:
                kelly_calculator.calculate_position_size(stage2_result)

            elapsed = time.time() - start_time
            times.append(elapsed)

        # Calculate statistics
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"\n📊 Performance Benchmark (10 iterations):")
        print(f"   Average: {avg_time:.3f}s")
        print(f"   Min: {min_time:.3f}s")
        print(f"   Max: {max_time:.3f}s")

        # Performance assertions
        assert avg_time < 1.0, f"Average time too slow: {avg_time:.3f}s"
        assert max_time < 2.0, f"Max time too slow: {max_time:.3f}s"

    def test_pipeline_throughput(self, db_manager, scoring_engine, kelly_calculator):
        """Test pipeline throughput (tickers per minute)"""
        # Get 50 tickers
        all_tickers = db_manager.get_tickers(region='KR', asset_type='STOCK', is_active=True)

        valid_tickers = []
        for ticker_data in all_tickers:
            ticker = ticker_data['ticker']
            ohlcv_data = db_manager.get_ohlcv_data(ticker=ticker, region='KR', limit=250)
            if len(ohlcv_data) >= 200:
                valid_tickers.append(ticker)
            if len(valid_tickers) >= 50:
                break

        # Process batch
        start_time = time.time()
        success_count = 0

        for ticker in valid_tickers[:50]:
            stage2_result = scoring_engine.calculate_comprehensive_score(ticker, 'KR')
            if stage2_result:
                kelly_calculator.calculate_position_size(stage2_result)
                success_count += 1

        elapsed = time.time() - start_time

        # Calculate throughput
        throughput_per_minute = (success_count / elapsed) * 60

        print(f"\n📊 Pipeline Throughput:")
        print(f"   Processed: {success_count} tickers in {elapsed:.2f}s")
        print(f"   Throughput: {throughput_per_minute:.1f} tickers/minute")

        # Throughput assertion (should handle at least 30 tickers/minute)
        assert throughput_per_minute >= 30, f"Throughput too low: {throughput_per_minute:.1f}/min"


class TestPipelineErrorRecovery:
    """Test error recovery across pipeline stages"""

    @pytest.fixture
    def kelly_calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def test_pipeline_with_missing_ohlcv(self, kelly_calculator):
        """Test pipeline recovery when OHLCV data missing"""
        # Mock Stage 2 result with valid structure
        stage2_result = {
            'ticker': 'MISSING_DATA',
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

        # Should not crash, should return result with DEFAULT pattern
        kelly_result = kelly_calculator.calculate_position_size(stage2_result)

        assert kelly_result.ticker == 'MISSING_DATA'
        assert kelly_result.recommended_position_size > 0


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
