"""
FactorCombiner 테스트

테스트 대상:
    - EqualWeightCombiner (3 tests)
    - CategoryWeightCombiner (3 tests)
    - OptimizationCombiner (3 tests)
    - Integration Tests (3 tests)

Total: 12 tests
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime
from unittest.mock import Mock, patch
from decimal import Decimal

from modules.factors.factor_combiner import (
    EqualWeightCombiner,
    CategoryWeightCombiner,
    OptimizationCombiner,
    FACTOR_CATEGORY_MAP,
    DEFAULT_CATEGORY_WEIGHTS
)
from modules.factors.factor_base import FactorCategory


# ========================================
# Test Fixtures
# ========================================

@pytest.fixture
def sample_factor_scores():
    """22개 팩터 점수 (5개 범주)"""
    return {
        # Momentum (3) - 평균 72
        'momentum_12m': 75.5,
        'rsi_momentum': 68.2,
        'short_term_momentum': 72.0,

        # Value (4) - 평균 59.5
        'pe_ratio': 60.0,
        'pb_ratio': 55.0,
        'ev_ebitda': 58.0,
        'dividend_yield': 65.0,

        # Quality (9) - 평균 81.1
        'roe': 85.0,
        'roa': 80.0,
        'operating_margin': 82.0,
        'net_margin': 78.0,
        'current_ratio': 75.0,
        'quick_ratio': 72.0,
        'debt_to_equity': 90.0,
        'accruals_ratio': 70.0,
        'cf_to_ni': 88.0,

        # Low-Vol (3) - 평균 50
        'volatility': 45.0,
        'beta': 50.0,
        'max_drawdown': 55.0,

        # Size (3) - 평균 52.3
        'market_cap': 20.0,
        'liquidity': 85.0,
        'float': 52.0
    }


@pytest.fixture
def partial_scores():
    """15개 팩터만 제공 (30% 누락)"""
    return {
        'momentum_12m': 75.5,
        'rsi_momentum': 68.2,
        'short_term_momentum': 72.0,

        'pe_ratio': 60.0,
        'pb_ratio': 55.0,
        'ev_ebitda': 58.0,

        'roe': 85.0,
        'roa': 80.0,
        'operating_margin': 82.0,
        'net_margin': 78.0,
        'current_ratio': 75.0,
        'quick_ratio': 72.0,

        'volatility': 45.0,
        'beta': 50.0,

        'market_cap': 20.0
    }


@pytest.fixture
def scores_with_none():
    """None/NaN 혼합"""
    return {
        'momentum_12m': 75.5,
        'pe_ratio': None,
        'roe': 85.0,
        'rsi_momentum': np.nan,
        'volatility': 45.0,
        'market_cap': 20.0
    }


# ========================================
# EqualWeightCombiner Tests (3 tests)
# ========================================

class TestEqualWeightCombiner:
    """EqualWeightCombiner (동일 가중치) 테스트"""

    def test_combine_simple_average(self):
        """3개 팩터 단순 평균 테스트"""
        # Given: 3개 팩터 점수
        scores = {
            'momentum_12m': 75.0,
            'pe_ratio': 60.0,
            'roe': 85.0
        }

        combiner = EqualWeightCombiner()

        # When: 조합
        result = combiner.combine(scores)

        # Then: 평균 = (75 + 60 + 85) / 3 = 73.33
        assert result == pytest.approx(73.33, abs=0.01)

    def test_get_weights_equal_distribution(self):
        """동일 가중치 분배 테스트 (5개 팩터)"""
        # Given: 5개 팩터
        scores = {
            'momentum_12m': 75.0,
            'pe_ratio': 60.0,
            'roe': 85.0,
            'volatility': 45.0,
            'market_cap': 20.0
        }

        combiner = EqualWeightCombiner()

        # When: 가중치 계산
        weights = combiner.get_weights(scores)

        # Then: 각 0.2 (1/5)
        assert len(weights) == 5
        for factor, weight in weights.items():
            assert weight == pytest.approx(0.2, abs=1e-6)

        # 합 = 1.0
        assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)

    def test_handle_missing_values(self, scores_with_none):
        """None/NaN 처리 테스트"""
        # Given: None, NaN 혼합 (유효한 값 4개)
        combiner = EqualWeightCombiner()

        # When: 조합
        result = combiner.combine(scores_with_none)

        # Then: None/NaN 필터링 후 평균
        # Valid: momentum_12m=75.5, roe=85.0, volatility=45.0, market_cap=20.0
        # Average: (75.5 + 85.0 + 45.0 + 20.0) / 4 = 56.375
        assert result == pytest.approx(56.375, abs=0.01)


# ========================================
# CategoryWeightCombiner Tests (3 tests)
# ========================================

class TestCategoryWeightCombiner:
    """CategoryWeightCombiner (범주별 가중치) 테스트"""

    def test_default_category_weights(self, sample_factor_scores):
        """기본 범주 가중치 테스트 (각 0.20)"""
        # Given: 기본 가중치 (MOMENTUM=0.2, VALUE=0.2, QUALITY=0.2, LOW_VOL=0.2, SIZE=0.2)
        combiner = CategoryWeightCombiner()

        # When: 조합
        result = combiner.combine(sample_factor_scores)

        # Then: 범주별 평균의 가중 합
        # MOMENTUM avg: (75.5 + 68.2 + 72.0) / 3 = 71.9
        # VALUE avg: (60 + 55 + 58 + 65) / 4 = 59.5
        # QUALITY avg: (85 + 80 + 82 + 78 + 75 + 72 + 90 + 70 + 88) / 9 = 80.0
        # LOW_VOL avg: (45 + 50 + 55) / 3 = 50.0
        # SIZE avg: (20 + 85 + 52) / 3 = 52.33

        # Weighted: 0.2 * 71.9 + 0.2 * 59.5 + 0.2 * 80.0 + 0.2 * 50.0 + 0.2 * 52.33
        expected = 0.2 * (71.9 + 59.5 + 80.0 + 50.0 + 52.33)
        assert result == pytest.approx(expected, abs=0.5)

    def test_custom_aggressive_strategy(self, sample_factor_scores):
        """공격적 전략 (모멘텀 높은 가중치) 테스트"""
        # Given: 공격적 가중치
        custom_weights = {
            'MOMENTUM': 0.40,  # High
            'VALUE': 0.35,
            'QUALITY': 0.15,
            'LOW_VOL': 0.05,   # Low
            'SIZE': 0.05       # Low
        }

        combiner = CategoryWeightCombiner(custom_weights)

        # When: 조합
        result = combiner.combine(sample_factor_scores)

        # Then: 모멘텀에 높은 가중치
        # Expected: 0.40 * 71.9 + 0.35 * 59.5 + 0.15 * 80.0 + 0.05 * 50.0 + 0.05 * 52.33
        expected = (
            0.40 * 71.9 +
            0.35 * 59.5 +
            0.15 * 80.0 +
            0.05 * 50.0 +
            0.05 * 52.33
        )
        assert result == pytest.approx(expected, abs=0.5)

        # 모멘텀 가중치가 높으므로 기본 전략보다 영향력 큼
        default_combiner = CategoryWeightCombiner()
        default_result = default_combiner.combine(sample_factor_scores)

        # 모멘텀(71.9) > 전체 평균이므로, 공격적 전략이 더 높은 점수
        assert result > default_result

    def test_weight_validation_error(self):
        """가중치 검증 오류 테스트"""
        # Given: 잘못된 가중치 (합 ≠ 1.0)
        invalid_weights = {
            'MOMENTUM': 0.30,
            'VALUE': 0.25,
            'QUALITY': 0.25,
            'LOW_VOL': 0.15
            # SIZE 누락 → 합 = 0.95
        }

        # When/Then: ValueError 발생
        with pytest.raises(ValueError, match="must sum to 1.0"):
            CategoryWeightCombiner(invalid_weights)

        # Given: 음수 가중치
        negative_weights = {
            'MOMENTUM': 0.40,
            'VALUE': 0.35,
            'QUALITY': 0.15,
            'LOW_VOL': -0.05,  # Negative
            'SIZE': 0.15
        }

        # When/Then: ValueError 발생
        with pytest.raises(ValueError, match="must be non-negative"):
            CategoryWeightCombiner(negative_weights)


# ========================================
# OptimizationCombiner Tests (3 tests)
# ========================================

class TestOptimizationCombiner:
    """OptimizationCombiner (최적화 기반) 테스트"""

    def test_combine_before_fit_error(self):
        """fit() 호출 전 combine() 오류 테스트"""
        # Given: Fitted 안 된 combiner
        combiner = OptimizationCombiner(db_path='mock_db')

        scores = {'momentum_12m': 75.0, 'pe_ratio': 60.0}

        # When/Then: ValueError 발생
        with pytest.raises(ValueError, match="Must call fit\\(\\) before combine\\(\\)"):
            combiner.combine(scores)

    @patch('psycopg2.connect')
    def test_fit_and_combine_success(self, mock_connect, sample_factor_scores):
        """fit() → combine() 워크플로우 테스트 (PostgreSQL Mock)"""
        # Given: Mock PostgreSQL connection
        mock_cursor = Mock()

        # Simulate 60 days × 12 factors historical returns
        # Format: [{'date': ..., 'factor_name': ..., 'factor_return': ...}, ...]
        mock_rows = []
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        factor_names = [
            '12M_Momentum', '1M_Momentum', 'RSI_Momentum',
            'PE_Ratio', 'PB_Ratio',
            'ROE_Proxy', 'Earnings_Quality', 'Operating_Profit_Margin', 'Book_Value_Quality',
            'Current_Ratio', 'Debt_Ratio', 'Dividend_Stability'
        ]

        for date in dates:
            for factor in factor_names:
                mock_rows.append({
                    'date': date,
                    'factor_name': factor,
                    'factor_return': np.random.normal(0.001, 0.02)  # 0.1% mean, 2% std
                })

        mock_cursor.fetchall.return_value = mock_rows
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        combiner = OptimizationCombiner(db_path='mock_db')

        # When: fit() 호출
        combiner.fit(start_date='2024-01-01', end_date='2024-03-01', objective='max_sharpe')

        # Then: fitted 상태
        assert combiner._is_fitted is True
        assert combiner.optimal_weights is not None
        assert len(combiner.optimal_weights) > 0

        # When: combine() 호출
        # Use only factors from fitted model
        fitted_scores = {factor: 75.0 for factor in combiner.optimal_weights.keys()}
        fitted_scores.update({'12M_Momentum': 80.0, 'PE_Ratio': 65.0})

        result = combiner.combine(fitted_scores)

        # Then: 유효한 composite score
        assert 0 <= result <= 100

    @patch('psycopg2.connect')
    def test_get_optimal_weights(self, mock_connect):
        """get_optimal_weights() 테스트 (fit 후)"""
        # Given: Mock fitted combiner
        mock_cursor = Mock()
        mock_rows = []
        dates = pd.date_range('2024-01-01', periods=60, freq='D')
        factor_names = ['12M_Momentum', 'PE_Ratio', 'ROE_Proxy']

        for date in dates:
            for factor in factor_names:
                mock_rows.append({
                    'date': date,
                    'factor_name': factor,
                    'factor_return': np.random.normal(0.001, 0.02)
                })

        mock_cursor.fetchall.return_value = mock_rows
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        combiner = OptimizationCombiner(db_path='mock_db')
        combiner.fit(start_date='2024-01-01', end_date='2024-03-01')

        # When: get_optimal_weights() 호출
        weights = combiner.get_optimal_weights()

        # Then: 유효한 가중치
        assert isinstance(weights, dict)
        assert len(weights) > 0

        # 가중치 합 = 1.0 (tolerance)
        total = sum(weights.values())
        assert total == pytest.approx(1.0, abs=1e-2)

        # 모든 가중치 0-1 범위
        for weight in weights.values():
            assert 0 <= weight <= 1.0


# ========================================
# Integration Tests (3 tests)
# ========================================

class TestIntegration:
    """통합 테스트"""

    @patch('psycopg2.connect')
    def test_all_combiners_same_input(self, mock_connect, sample_factor_scores):
        """동일 입력으로 3개 combiner 실행 → 다른 결과"""
        # Given: Mock OptimizationCombiner
        mock_cursor = Mock()
        mock_rows = []
        dates = pd.date_range('2024-01-01', periods=60, freq='D')

        # Use factors that exist in sample_factor_scores
        factor_names = ['12M_Momentum', 'PE_Ratio', 'ROE_Proxy']

        for date in dates:
            for factor in factor_names:
                mock_rows.append({
                    'date': date,
                    'factor_name': factor,
                    'factor_return': np.random.normal(0.001, 0.02)
                })

        mock_cursor.fetchall.return_value = mock_rows
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_connect.return_value = mock_conn

        # When: 3개 combiner 실행
        equal_combiner = EqualWeightCombiner()
        category_combiner = CategoryWeightCombiner()
        opt_combiner = OptimizationCombiner(db_path='mock_db')
        opt_combiner.fit(start_date='2024-01-01', end_date='2024-03-01')

        equal_result = equal_combiner.combine(sample_factor_scores)
        category_result = category_combiner.combine(sample_factor_scores)

        # Use only fitted factors for OptimizationCombiner
        fitted_scores = {f: sample_factor_scores.get(f.lower().replace('_', ''), 75.0)
                        for f in opt_combiner.optimal_weights.keys()}
        opt_result = opt_combiner.combine(fitted_scores)

        # Then: 각기 다른 결과 (각자 다른 가중치 전략)
        assert equal_result != category_result

        # 모두 유효한 범위
        assert 0 <= equal_result <= 100
        assert 0 <= category_result <= 100
        assert 0 <= opt_result <= 100

    def test_factor_category_mapping(self):
        """FACTOR_CATEGORY_MAP 검증"""
        # Given: 22개 핵심 팩터
        expected_factors = {
            # Momentum (3)
            'momentum_12m', 'rsi_momentum', 'short_term_momentum',
            # Value (4)
            'pe_ratio', 'pb_ratio', 'ev_ebitda', 'dividend_yield',
            # Quality (9)
            'roe', 'roa', 'operating_margin', 'net_margin',
            'current_ratio', 'quick_ratio', 'debt_to_equity',
            'accruals_ratio', 'cf_to_ni',
            # Low-Vol (3)
            'volatility', 'beta', 'max_drawdown',
            # Size (3)
            'market_cap', 'liquidity', 'float'
        }

        # When: 매핑 확인
        mapped_factors = set(FACTOR_CATEGORY_MAP.keys())

        # Then: 모든 핵심 팩터 매핑됨
        assert expected_factors.issubset(mapped_factors)

        # 5개 범주 모두 존재
        categories = {cat.name for cat in FACTOR_CATEGORY_MAP.values()}
        expected_categories = {'MOMENTUM', 'VALUE', 'QUALITY', 'LOW_VOL', 'SIZE'}
        assert expected_categories.issubset(categories)

    def test_partial_factor_coverage(self, partial_scores):
        """부분 팩터 커버리지 처리 (30% 누락)"""
        # Given: 22개 중 15개만 제공
        equal_combiner = EqualWeightCombiner()
        category_combiner = CategoryWeightCombiner()

        # When: 조합
        equal_result = equal_combiner.combine(partial_scores)
        category_result = category_combiner.combine(partial_scores)

        # Then: 정상 작동 (누락 데이터 처리)
        assert 0 <= equal_result <= 100
        assert 0 <= category_result <= 100

        # 가중치도 정상 계산
        equal_weights = equal_combiner.get_weights(partial_scores)
        category_weights = category_combiner.get_weights(partial_scores)

        assert len(equal_weights) == 15  # 15개 팩터
        assert len(category_weights) == 15

        # 가중치 합 = 1.0
        assert sum(equal_weights.values()) == pytest.approx(1.0, abs=1e-6)
        assert sum(category_weights.values()) == pytest.approx(1.0, abs=1e-6)
