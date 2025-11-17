"""
Momentum Factors 테스트

테스트 대상:
    - TwelveMonthMomentumFactor (4 tests)
    - RSIMomentumFactor (4 tests)
    - ShortTermMomentumFactor (4 tests)

Total: 12 tests
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from modules.factors.momentum_factors import (
    TwelveMonthMomentumFactor,
    RSIMomentumFactor,
    ShortTermMomentumFactor
)
from modules.factors.factor_base import FactorResult, FactorCategory


# ========================================
# Test Fixtures
# ========================================

@pytest.fixture
def ohlcv_data_252days():
    """252일(1년) OHLCV 데이터"""
    dates = pd.date_range(end=datetime.now(), periods=252, freq='D')

    # 모멘텀 시뮬레이션: 시작가 50,000 → 종가 60,000 (20% 상승)
    close_prices = np.linspace(50000, 60000, 252)

    # MA20, MA60 추가
    data = pd.DataFrame({
        'date': dates,
        'open': close_prices * 0.99,
        'high': close_prices * 1.01,
        'low': close_prices * 0.98,
        'close': close_prices,
        'volume': np.random.randint(1000000, 2000000, 252)
    })

    # MA20 계산
    data['ma20'] = data['close'].rolling(window=20, min_periods=1).mean()

    # MA60 계산
    data['ma60'] = data['close'].rolling(window=60, min_periods=1).mean()

    return data


@pytest.fixture
def ohlcv_data_with_rsi():
    """RSI 포함 OHLCV 데이터 (60일)"""
    dates = pd.date_range(end=datetime.now(), periods=60, freq='D')

    close_prices = np.linspace(50000, 55000, 60)

    data = pd.DataFrame({
        'date': dates,
        'close': close_prices,
        'volume': np.random.randint(1000000, 2000000, 60)
    })

    # RSI-14 시뮬레이션 (60 범위, optimal zone)
    data['rsi_14'] = np.linspace(55, 65, 60)

    return data


@pytest.fixture
def short_term_data():
    """단기 모멘텀용 40일 데이터 (30일 최소 필요)"""
    dates = pd.date_range(end=datetime.now(), periods=40, freq='D')

    close_prices = np.linspace(50000, 52000, 40)  # 4% 상승

    data = pd.DataFrame({
        'date': dates,
        'close': close_prices,
        'volume': np.random.randint(1000000, 2000000, 40)
    })

    return data


# ========================================
# TwelveMonthMomentumFactor Tests (4 tests)
# ========================================

class TestTwelveMonthMomentumFactor:
    """12개월 모멘텀 팩터 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = TwelveMonthMomentumFactor()

        # Then: 속성 검증
        assert factor.name == "12M_Momentum"
        assert factor.category == FactorCategory.MOMENTUM
        assert factor.lookback_days == 252
        assert factor.min_required_days == 252

    def test_calculate_success(self, ohlcv_data_252days):
        """12개월 모멘텀 계산 성공 테스트"""
        # Given: 252일 데이터 (50,000 → 60,000, 20% 상승)
        factor = TwelveMonthMomentumFactor()

        # When: 계산 실행
        result = factor.calculate(data=ohlcv_data_252days, ticker='005930')

        # Then: 결과 검증
        assert isinstance(result, FactorResult)
        assert result.factor_name == "12M_Momentum"
        assert result.ticker == '005930'

        # 12M 모멘텀 > 0 (상승 추세)
        assert result.raw_value > 0

        # 메타데이터 검증
        assert 'base_momentum_return' in result.metadata
        assert 'volume_weight' in result.metadata
        assert 'trend_score' in result.metadata
        assert result.metadata['data_points'] == 252

    def test_calculate_insufficient_data(self):
        """데이터 부족 시 처리 테스트"""
        # Given: 100일 데이터 (252일 미만)
        dates = pd.date_range(end=datetime.now(), periods=100, freq='D')
        insufficient_data = pd.DataFrame({
            'date': dates,
            'close': np.linspace(50000, 55000, 100),
            'volume': np.random.randint(1000000, 2000000, 100),
            'ma20': np.linspace(50000, 55000, 100),
            'ma60': np.linspace(50000, 55000, 100)
        })

        factor = TwelveMonthMomentumFactor()

        # When: 계산 실행
        result = factor.calculate(data=insufficient_data, ticker='INVALID')

        # Then: None 반환 (데이터 부족)
        assert result is None

    def test_volume_and_trend_adjustments(self, ohlcv_data_252days):
        """Volume 가중치 및 트렌드 조정 테스트"""
        # Given: Volume과 MA가 포함된 데이터
        factor = TwelveMonthMomentumFactor()

        # When: 계산 실행
        result = factor.calculate(data=ohlcv_data_252days, ticker='005930')

        # Then: Volume weight가 0.5 ~ 1.5 범위
        assert 0.5 <= result.metadata['volume_weight'] <= 1.5

        # Trend score가 -1.0 ~ 1.0 범위
        assert -1.0 <= result.metadata['trend_score'] <= 1.0

        # 최종 모멘텀 = base * volume_weight * (1 + trend_score * 0.1)
        base_momentum = result.metadata['base_momentum_return']
        volume_weight = result.metadata['volume_weight']
        trend_score = result.metadata['trend_score']
        expected_momentum = base_momentum * volume_weight * (1 + trend_score * 0.1)

        assert abs(result.raw_value - expected_momentum) < 1.0


# ========================================
# RSIMomentumFactor Tests (4 tests)
# ========================================

class TestRSIMomentumFactor:
    """RSI 모멘텀 팩터 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = RSIMomentumFactor()

        # Then: 속성 검증
        assert factor.name == "RSI_Momentum"
        assert factor.category == FactorCategory.MOMENTUM
        assert factor.lookback_days == 60
        assert factor.min_required_days == 30

    def test_calculate_optimal_rsi(self, ohlcv_data_with_rsi):
        """최적 RSI 구간(50-70) 계산 테스트"""
        # Given: RSI 60인 데이터 (optimal zone)
        factor = RSIMomentumFactor()

        # When: 계산 실행
        result = factor.calculate(data=ohlcv_data_with_rsi, ticker='000660')

        # Then: 결과 검증
        assert isinstance(result, FactorResult)
        assert result.factor_name == "RSI_Momentum"

        # RSI 60 → score = 100 (최적 구간)
        assert result.raw_value == 100.0

        # 메타데이터 검증
        assert result.metadata['rsi_value'] == pytest.approx(65.0, abs=1.0)
        assert result.metadata['rsi_zone'] == "bullish_momentum"

    def test_calculate_extreme_rsi(self):
        """극단 RSI (overbought/oversold) 처리 테스트"""
        # Given: RSI 85 (overbought)
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        overbought_data = pd.DataFrame({
            'date': dates,
            'close': np.linspace(50000, 55000, 30),
            'rsi_14': [85.0] * 30
        })

        factor = RSIMomentumFactor()

        # When: 계산 실행
        result = factor.calculate(data=overbought_data, ticker='035720')

        # Then: RSI >80 → score = 25 (overbought penalty)
        assert result.raw_value == 25.0
        assert result.metadata['rsi_zone'] == "overbought"

    def test_missing_rsi_column(self):
        """RSI 컬럼 없음 처리 테스트"""
        # Given: RSI 컬럼 없는 데이터
        dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
        no_rsi_data = pd.DataFrame({
            'date': dates,
            'close': np.linspace(50000, 55000, 30),
            'volume': np.random.randint(1000000, 2000000, 30)
        })

        factor = RSIMomentumFactor()

        # When: 계산 실행
        result = factor.calculate(data=no_rsi_data, ticker='INVALID')

        # Then: None 반환 (RSI 없음)
        assert result is None


# ========================================
# ShortTermMomentumFactor Tests (4 tests)
# ========================================

class TestShortTermMomentumFactor:
    """단기 모멘텀 팩터 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = ShortTermMomentumFactor()

        # Then: 속성 검증
        assert factor.name == "1M_Momentum"
        assert factor.category == FactorCategory.MOMENTUM
        assert factor.lookback_days == 60
        assert factor.min_required_days == 30

    def test_calculate_success(self, short_term_data):
        """단기 모멘텀 계산 성공 테스트"""
        # Given: 40일 데이터 (50,000 → 52,000, 4% 상승)
        factor = ShortTermMomentumFactor()

        # When: 계산 실행
        result = factor.calculate(data=short_term_data, ticker='005380')

        # Then: 결과 검증
        assert isinstance(result, FactorResult)
        assert result.factor_name == "1M_Momentum"
        assert result.ticker == '005380'

        # 1M 모멘텀 > 0 (상승 추세)
        assert result.raw_value > 0

        # 메타데이터 검증
        assert 'momentum_return' in result.metadata
        assert 'volume_confirmed' in result.metadata
        assert 'price_20d_ago' in result.metadata
        assert 'current_price' in result.metadata

    def test_calculate_insufficient_data(self):
        """데이터 부족 시 처리 테스트"""
        # Given: 10일 데이터 (30일 미만)
        dates = pd.date_range(end=datetime.now(), periods=10, freq='D')
        insufficient_data = pd.DataFrame({
            'date': dates,
            'close': np.linspace(50000, 51000, 10),
            'volume': np.random.randint(1000000, 2000000, 10)
        })

        factor = ShortTermMomentumFactor()

        # When: 계산 실행
        result = factor.calculate(data=insufficient_data, ticker='INVALID')

        # Then: None 반환 (데이터 부족)
        assert result is None

    def test_volume_weighted_momentum(self, short_term_data):
        """Volume 가중 모멘텀 테스트"""
        # Given: Volume 정보가 포함된 데이터
        # Volume을 인위적으로 증가시켜 가중치 효과 확인
        high_volume_data = short_term_data.copy()
        high_volume_data.loc[high_volume_data.index[-5:], 'volume'] *= 2  # 최근 5일 거래량 2배

        factor = ShortTermMomentumFactor()

        # When: 계산 실행
        result = factor.calculate(data=high_volume_data, ticker='051910')

        # Then: Volume 가중치가 반영됨
        assert isinstance(result, FactorResult)
        assert result.raw_value > 0

        # 높은 거래량 → 더 높은 신뢰도
        assert result.confidence > 0.5
