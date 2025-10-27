"""
Phase 5 Unit Tests: Kelly Calculator

Tests individual components of StockKellyCalculator to ensure
each function works correctly in isolation.

Test Coverage:
- Calculator initialization
- Pattern detection from Stage 2 results
- Kelly formula calculation
- Quality multiplier logic
- Risk adjustment logic
- Database operations
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import sqlite3
from modules.stock_kelly_calculator import (
    StockKellyCalculator,
    PatternType,
    RiskLevel,
    KellyResult,
    PatternProbability,
    QualityScoreAdjustment
)


class TestStockKellyCalculatorInit:
    """Test calculator initialization"""

    def test_kelly_calculator_init_moderate(self):
        """Test calculator initialization with moderate risk"""
        calculator = StockKellyCalculator(
            db_path="data/spock_local.db",
            risk_level=RiskLevel.MODERATE
        )

        assert calculator.risk_level == RiskLevel.MODERATE
        assert calculator.max_single_position == 15.0
        assert calculator.max_sector_allocation == 40.0
        assert len(calculator.pattern_probabilities) == 6
        assert len(calculator.quality_adjustments) == 6

    def test_kelly_calculator_init_conservative(self):
        """Test calculator initialization with conservative risk"""
        calculator = StockKellyCalculator(
            db_path="data/spock_local.db",
            risk_level=RiskLevel.CONSERVATIVE,
            max_single_position=10.0
        )

        assert calculator.risk_level == RiskLevel.CONSERVATIVE
        assert calculator.max_single_position == 10.0

    def test_kelly_calculator_init_aggressive(self):
        """Test calculator initialization with aggressive risk"""
        calculator = StockKellyCalculator(
            db_path="data/spock_local.db",
            risk_level=RiskLevel.AGGRESSIVE,
            max_single_position=20.0
        )

        assert calculator.risk_level == RiskLevel.AGGRESSIVE
        assert calculator.max_single_position == 20.0

    def test_pattern_probabilities_initialization(self):
        """Test pattern probabilities are correctly initialized"""
        calculator = StockKellyCalculator(db_path="data/spock_local.db")

        # Check Stage 2 Breakout
        stage2_prob = calculator.pattern_probabilities[PatternType.STAGE_2_BREAKOUT]
        assert stage2_prob.win_rate == 0.65
        assert stage2_prob.avg_win == 0.25
        assert stage2_prob.avg_loss == 0.08
        assert stage2_prob.base_position == 10.0

        # Check VCP Breakout
        vcp_prob = calculator.pattern_probabilities[PatternType.VCP_BREAKOUT]
        assert vcp_prob.win_rate == 0.62
        assert vcp_prob.base_position == 8.0

        # Check Default
        default_prob = calculator.pattern_probabilities[PatternType.DEFAULT]
        assert default_prob.win_rate == 0.55
        assert default_prob.base_position == 3.0


class TestPatternDetection:
    """Test pattern detection from Stage 2 results"""

    @pytest.fixture
    def calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def test_pattern_detection_stage2_breakout(self, calculator):
        """Test Stage 2 Breakout pattern detection"""
        stage2_result = {
            'ticker': '005930',
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
        }

        pattern = calculator.detect_pattern_from_stage2(stage2_result)
        assert pattern == PatternType.STAGE_2_BREAKOUT

    def test_pattern_detection_vcp_breakout(self, calculator):
        """Test VCP Breakout pattern detection"""
        stage2_result = {
            'ticker': '000660',
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
                                'details': {'patterns_found': ['vcp', 'consolidation']}
                            }
                        }
                    }
                }
            }
        }

        pattern = calculator.detect_pattern_from_stage2(stage2_result)
        assert pattern == PatternType.VCP_BREAKOUT

    def test_pattern_detection_cup_handle(self, calculator):
        """Test Cup & Handle pattern detection"""
        stage2_result = {
            'ticker': '035720',
            'region': 'KR',
            'total_score': 68,
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
                                'details': {'patterns_found': ['cup_handle']}
                            }
                        }
                    }
                }
            }
        }

        pattern = calculator.detect_pattern_from_stage2(stage2_result)
        assert pattern == PatternType.CUP_HANDLE

    def test_pattern_detection_default(self, calculator):
        """Test default pattern detection for low scores"""
        stage2_result = {
            'ticker': '012330',
            'region': 'KR',
            'total_score': 45,
            'details': {
                'layers': {
                    'structural': {
                        'modules': {
                            'StageAnalysisModule': {
                                'score': 8,
                                'details': {'current_stage': 1}
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

        pattern = calculator.detect_pattern_from_stage2(stage2_result)
        assert pattern == PatternType.DEFAULT


class TestQualityMultiplier:
    """Test quality multiplier calculation"""

    @pytest.fixture
    def calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def test_quality_multiplier_exceptional(self, calculator):
        """Test exceptional quality score (85-100)"""
        multiplier, desc = calculator.get_quality_multiplier(90.0)
        assert multiplier == 1.4
        assert "Exceptional" in desc

    def test_quality_multiplier_excellent(self, calculator):
        """Test excellent quality score (75-85)"""
        multiplier, desc = calculator.get_quality_multiplier(80.0)
        assert multiplier == 1.3
        assert "Excellent" in desc

    def test_quality_multiplier_strong(self, calculator):
        """Test strong quality score (70-75)"""
        multiplier, desc = calculator.get_quality_multiplier(72.0)
        assert multiplier == 1.2
        assert "Strong" in desc

    def test_quality_multiplier_good(self, calculator):
        """Test good quality score (60-70)"""
        multiplier, desc = calculator.get_quality_multiplier(65.0)
        assert multiplier == 1.0
        assert "Good" in desc

    def test_quality_multiplier_moderate(self, calculator):
        """Test moderate quality score (50-60)"""
        multiplier, desc = calculator.get_quality_multiplier(55.0)
        assert multiplier == 0.8
        assert "Moderate" in desc

    def test_quality_multiplier_weak(self, calculator):
        """Test weak quality score (<50)"""
        multiplier, desc = calculator.get_quality_multiplier(40.0)
        assert multiplier == 0.6
        assert "Weak" in desc


class TestRiskAdjustment:
    """Test risk level adjustment"""

    def test_risk_adjustment_conservative(self):
        """Test conservative risk adjustment (Half Kelly)"""
        calculator = StockKellyCalculator(
            db_path="data/spock_local.db",
            risk_level=RiskLevel.CONSERVATIVE
        )
        adjustment = calculator._get_risk_adjustment()
        assert adjustment == 0.5

    def test_risk_adjustment_moderate(self):
        """Test moderate risk adjustment (60% Kelly)"""
        calculator = StockKellyCalculator(
            db_path="data/spock_local.db",
            risk_level=RiskLevel.MODERATE
        )
        adjustment = calculator._get_risk_adjustment()
        assert adjustment == 0.6

    def test_risk_adjustment_aggressive(self):
        """Test aggressive risk adjustment (75% Kelly)"""
        calculator = StockKellyCalculator(
            db_path="data/spock_local.db",
            risk_level=RiskLevel.AGGRESSIVE
        )
        adjustment = calculator._get_risk_adjustment()
        assert adjustment == 0.75


class TestKellyFormulaCalculation:
    """Test Kelly formula calculation"""

    @pytest.fixture
    def calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def test_kelly_calculation_stage2_breakout(self, calculator):
        """Test Kelly calculation for Stage 2 Breakout"""
        stage2_result = {
            'ticker': '005930',
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
        }

        kelly_result = calculator.calculate_position_size(stage2_result)

        # Assertions
        assert kelly_result.ticker == '005930'
        assert kelly_result.region == 'KR'
        assert kelly_result.pattern_type == PatternType.STAGE_2_BREAKOUT
        assert kelly_result.win_rate == 0.65
        assert kelly_result.kelly_pct > 0
        assert kelly_result.half_kelly_pct == kelly_result.kelly_pct * 0.5
        assert 0 < kelly_result.recommended_position_size <= 15.0
        assert kelly_result.quality_score == 85.0
        assert kelly_result.quality_multiplier == 1.4

    def test_kelly_calculation_respects_max_position(self, calculator):
        """Test that Kelly calculation respects max position limit"""
        # High score that would exceed max position
        stage2_result = {
            'ticker': 'TEST',
            'region': 'KR',
            'total_score': 95,
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
        }

        kelly_result = calculator.calculate_position_size(stage2_result)

        # Should not exceed max single position
        assert kelly_result.recommended_position_size <= calculator.max_single_position


class TestDatabaseOperations:
    """Test database save/load operations"""

    @pytest.fixture
    def calculator(self):
        return StockKellyCalculator(db_path="data/spock_local.db")

    def test_database_save(self, calculator):
        """Test Kelly result is saved to database"""
        stage2_result = {
            'ticker': 'TEST_SAVE',
            'region': 'KR',
            'total_score': 75,
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
                                'details': {'patterns_found': []}
                            }
                        }
                    }
                }
            }
        }

        # Calculate and save
        kelly_result = calculator.calculate_position_size(stage2_result)

        # Verify in database
        conn = sqlite3.connect("data/spock_local.db")
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticker, pattern_type, win_rate, kelly_pct, recommended_position_size
            FROM kelly_sizing
            WHERE ticker = ?
            ORDER BY calculation_date DESC
            LIMIT 1
        """, ('TEST_SAVE',))

        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[0] == 'TEST_SAVE'
        assert row[1] == kelly_result.pattern_type.value
        assert row[2] == kelly_result.win_rate
        assert row[3] == kelly_result.kelly_pct
        assert row[4] == kelly_result.recommended_position_size


# Run tests
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
