"""
Quality Factors PostgreSQL 테스트

테스트 대상:
    - Profitability: ROEFactor, ROAFactor, OperatingMarginFactor, NetProfitMarginFactor (12 tests)
    - Liquidity: CurrentRatioFactor, QuickRatioFactor (6 tests)
    - Leverage: DebtToEquityFactor (3 tests)
    - Earnings Quality: AccrualsRatioFactor, CFToNIRatioFactor (6 tests)

Total: 27 tests
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from decimal import Decimal

from modules.factors.quality_factors import (
    ROEFactor,
    ROAFactor,
    OperatingMarginFactor,
    NetProfitMarginFactor,
    CurrentRatioFactor,
    QuickRatioFactor,
    DebtToEquityFactor,
    AccrualsRatioFactor,
    CFToNIRatioFactor
)
from modules.factors.factor_base import FactorResult, FactorCategory


# ========================================
# Profitability Factors Tests (12 tests)
# ========================================

class TestROEFactor:
    """ROE (자기자본이익률) 팩터 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = ROEFactor()

        # Then: 속성 검증
        assert factor.name == "ROE"
        assert factor.category == FactorCategory.QUALITY
        assert factor.lookback_days == 365
        assert factor.min_required_days == 1
        # Confidence 0.9 (연구 결과 확인)

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_calculate_success(self, mock_connect):
        """ROE 계산 성공 테스트 (정상적인 수익성)"""
        # Given: Mock database connection
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            50_000_000,    # net_income: $50M
            250_000_000,   # total_equity: $250M
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = ROEFactor()

        # When: Calculate ROE
        result = factor.calculate(data=None, ticker='005930', region='KR')

        # Then: 결과 검증
        assert isinstance(result, FactorResult)
        assert result.factor_name == "ROE"
        assert result.ticker == '005930'

        # ROE = (50M / 250M) × 100 = 20%
        assert result.raw_value == pytest.approx(20.0, abs=0.1)

        # 메타데이터 검증
        assert result.metadata['roe'] == pytest.approx(20.0, abs=0.01)
        assert result.metadata['fiscal_year'] == 2024

        # Confidence 검증
        assert result.confidence == 0.9

        # DB 쿼리 호출 검증
        mock_connect.assert_called_once()
        mock_cursor.execute.assert_called_once()

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_edge_case_zero_equity(self, mock_connect):
        """total_equity = 0 처리 테스트 (WHERE 절 필터링)"""
        # Given: fetchone returns None (zero equity filtered by WHERE clause)
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = ROEFactor()

        # When: Calculate with zero equity
        result = factor.calculate(data=None, ticker='INVALID', region='US')

        # Then: None 반환 (데이터 없음)
        assert result is None


class TestROAFactor:
    """ROA (총자산이익률) 팩터 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = ROAFactor()

        # Then: 속성 검증
        assert factor.name == "ROA"
        assert factor.category == FactorCategory.QUALITY
        assert factor.lookback_days == 365
        assert factor.min_required_days == 1

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_calculate_success(self, mock_connect):
        """ROA 계산 성공 테스트"""
        # Given: Mock database with efficient asset use
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            50_000_000,    # net_income: $50M
            500_000_000,   # total_assets: $500M
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = ROAFactor()

        # When: Calculate ROA
        result = factor.calculate(data=None, ticker='000660', region='KR')

        # Then: ROA = (50M / 500M) × 100 = 10%
        assert isinstance(result, FactorResult)
        assert result.factor_name == "ROA"
        assert result.raw_value == pytest.approx(10.0, abs=0.1)
        assert result.metadata['roa'] == pytest.approx(10.0, abs=0.01)
        assert result.metadata['fiscal_year'] == 2024
        assert result.confidence == 0.9

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_edge_case_zero_assets(self, mock_connect):
        """total_assets = 0 처리 테스트"""
        # Given: Zero assets filtered by WHERE clause
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = ROAFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='INVALID')

        # Then: None 반환
        assert result is None


class TestOperatingMarginFactor:
    """Operating Margin (영업이익률) 팩터 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = OperatingMarginFactor()

        # Then: 속성 검증
        assert factor.name == "Operating_Margin"
        assert factor.category == FactorCategory.QUALITY
        assert factor.lookback_days == 365
        assert factor.min_required_days == 1

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_calculate_success(self, mock_connect):
        """영업이익률 계산 성공 테스트"""
        # Given: High operating efficiency
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            200_000_000,   # operating_profit: $200M
            1_000_000_000, # revenue: $1B
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = OperatingMarginFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='035720', region='KR')

        # Then: Operating Margin = (200M / 1B) × 100 = 20%
        assert isinstance(result, FactorResult)
        assert result.factor_name == "Operating_Margin"
        assert result.raw_value == pytest.approx(20.0, abs=0.1)
        assert result.metadata['operating_margin'] == pytest.approx(20.0, abs=0.01)

        # Confidence 0.95 (higher than other margins)
        assert result.confidence == 0.95

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_edge_case_zero_revenue(self, mock_connect):
        """revenue = 0 처리 테스트"""
        # Given: Zero revenue filtered
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = OperatingMarginFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='INVALID')

        # Then: None 반환
        assert result is None


class TestNetProfitMarginFactor:
    """Net Profit Margin (순이익률) 팩터 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = NetProfitMarginFactor()

        # Then: 속성 검증
        assert factor.name == "Net_Profit_Margin"
        assert factor.category == FactorCategory.QUALITY
        assert factor.lookback_days == 365
        assert factor.min_required_days == 1

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_calculate_success(self, mock_connect):
        """순이익률 계산 성공 테스트"""
        # Given: Profitable business
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            50_000_000,    # net_income: $50M
            1_000_000_000, # revenue: $1B
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = NetProfitMarginFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='005380', region='KR')

        # Then: Net Margin = (50M / 1B) × 100 = 5%
        assert isinstance(result, FactorResult)
        assert result.factor_name == "Net_Profit_Margin"
        assert result.raw_value == pytest.approx(5.0, abs=0.1)
        assert result.metadata['net_profit_margin'] == pytest.approx(5.0, abs=0.01)
        assert result.confidence == 0.9

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_edge_case_negative_income(self, mock_connect):
        """net_income < 0 허용 테스트 (손실 허용)"""
        # Given: Company with loss (negative income is allowed)
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            -10_000_000,   # net_income: -$10M (loss)
            1_000_000_000, # revenue: $1B
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = NetProfitMarginFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='LOSS_CO', region='US')

        # Then: Negative margin allowed
        assert isinstance(result, FactorResult)
        assert result.raw_value == pytest.approx(-1.0, abs=0.1)  # -10M / 1B = -1%
        assert result.metadata['net_profit_margin'] < 0


# ========================================
# Liquidity Factors Tests (6 tests)
# ========================================

class TestCurrentRatioFactor:
    """Current Ratio (유동비율) 팩터 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = CurrentRatioFactor()

        # Then: 속성 검증
        assert factor.name == "Current_Ratio"
        assert factor.category == FactorCategory.QUALITY
        assert factor.lookback_days == 365
        assert factor.min_required_days == 1

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_calculate_success(self, mock_connect):
        """유동비율 계산 성공 테스트 (건전한 유동성)"""
        # Given: Healthy liquidity (2.0x ratio)
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            300_000_000,   # current_assets: $300M
            150_000_000,   # current_liabilities: $150M
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = CurrentRatioFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='005930', region='KR')

        # Then: Current Ratio = (300M / 150M) × 100 = 200 (2.0x as percentage)
        assert isinstance(result, FactorResult)
        assert result.factor_name == "Current_Ratio"
        assert result.raw_value == pytest.approx(200.0, abs=0.1)
        assert result.metadata['current_ratio'] == pytest.approx(200.0, abs=0.01)

        # Confidence 0.95
        assert result.confidence == 0.95

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_edge_case_zero_liabilities(self, mock_connect):
        """current_liabilities = 0 처리 테스트"""
        # Given: Zero liabilities filtered
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = CurrentRatioFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='INVALID')

        # Then: None 반환
        assert result is None


class TestQuickRatioFactor:
    """Quick Ratio (당좌비율) 팩터 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = QuickRatioFactor()

        # Then: 속성 검증
        assert factor.name == "Quick_Ratio"
        assert factor.category == FactorCategory.QUALITY
        assert factor.lookback_days == 365
        assert factor.min_required_days == 1

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_calculate_success_with_inventory(self, mock_connect):
        """당좌비율 계산 성공 테스트 (재고 있음)"""
        # Given: Company with inventory
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            300_000_000,   # current_assets: $300M
            50_000_000,    # inventory: $50M
            150_000_000,   # current_liabilities: $150M
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = QuickRatioFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='000660', region='KR')

        # Then: Quick Ratio = ((300M - 50M) / 150M) × 100 = 166.67 (1.67x as %)
        assert isinstance(result, FactorResult)
        assert result.factor_name == "Quick_Ratio"
        assert result.raw_value == pytest.approx(166.67, abs=0.5)
        assert result.metadata['quick_ratio'] == pytest.approx(166.67, abs=0.5)
        assert result.confidence == 0.95

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_null_inventory_handling(self, mock_connect):
        """inventory = NULL 처리 테스트 (0으로 간주)"""
        # Given: NULL inventory (should default to 0)
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            300_000_000,   # current_assets: $300M
            None,          # inventory: NULL
            150_000_000,   # current_liabilities: $150M
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = QuickRatioFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='SERVICE_CO', region='US')

        # Then: Quick Ratio = ((300M - 0) / 150M) × 100 = 200 (2.0x)
        assert isinstance(result, FactorResult)
        assert result.raw_value == pytest.approx(200.0, abs=0.1)


# ========================================
# Leverage Factor Tests (3 tests)
# ========================================

class TestDebtToEquityFactor:
    """Debt-to-Equity Ratio (부채비율) 팩터 테스트 - NEGATED"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = DebtToEquityFactor()

        # Then: 속성 검증
        assert factor.name == "Debt_to_Equity"
        assert factor.category == FactorCategory.QUALITY
        assert factor.lookback_days == 365
        assert factor.min_required_days == 1

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_calculate_success_negation(self, mock_connect):
        """부채비율 계산 성공 - raw_value 음수 확인"""
        # Given: Moderate leverage (1.0x D/E)
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            250_000_000,   # total_liabilities: $250M
            250_000_000,   # total_equity: $250M
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = DebtToEquityFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='005930', region='KR')

        # Then: raw_value는 음수 (negated for ranking)
        assert isinstance(result, FactorResult)
        assert result.factor_name == "Debt_to_Equity"

        # D/E = 250M / 250M = 1.0 → raw_value = -(1.0 × 100) = -100
        assert result.raw_value == pytest.approx(-100.0, abs=0.1)

        # Confidence 0.95
        assert result.confidence == 0.95

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_metadata_contains_actual_ratio(self, mock_connect):
        """metadata에는 실제 비율(양수) 저장 확인"""
        # Given: High leverage (4.0x D/E)
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            400_000_000,   # total_liabilities: $400M
            100_000_000,   # total_equity: $100M
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = DebtToEquityFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='LEVERED_CO', region='US')

        # Then: raw_value 음수, metadata 양수
        assert result.raw_value == pytest.approx(-400.0, abs=0.1)  # Negated
        assert result.metadata['debt_to_equity'] == pytest.approx(400.0, abs=0.1)  # Actual ratio
        assert result.metadata['fiscal_year'] == 2024


# ========================================
# Earnings Quality Factors Tests (6 tests)
# ========================================

class TestAccrualsRatioFactor:
    """Accruals Ratio (발생액 비율) 팩터 테스트 - NEGATED"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = AccrualsRatioFactor()

        # Then: 속성 검증
        assert factor.name == "Accruals_Ratio"
        assert factor.category == FactorCategory.QUALITY
        assert factor.lookback_days == 365
        assert factor.min_required_days == 1

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_calculate_success_negation(self, mock_connect):
        """발생액 비율 계산 - raw_value 음수 확인"""
        # Given: Low quality earnings (accruals > 0, NI > OCF)
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            100_000_000,   # net_income: $100M
            50_000_000,    # operating_cash_flow: $50M (less than NI)
            1_000_000_000, # total_assets: $1B
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = AccrualsRatioFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='ACCRUAL_CO', region='US')

        # Then: Accruals = (100M - 50M) / 1B = 0.05
        #       raw_value = -0.05 (negated)
        assert isinstance(result, FactorResult)
        assert result.factor_name == "Accruals_Ratio"
        assert result.raw_value == pytest.approx(-0.05, abs=0.001)  # Negated

        # Confidence 0.9
        assert result.confidence == 0.9

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_high_quality_negative_accruals(self, mock_connect):
        """고품질 이익: OCF > NI → 음의 발생액"""
        # Given: High quality earnings (OCF > NI)
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            50_000_000,    # net_income: $50M
            60_000_000,    # operating_cash_flow: $60M (more than NI)
            1_000_000_000, # total_assets: $1B
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = AccrualsRatioFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='QUALITY_CO', region='KR')

        # Then: Accruals = (50M - 60M) / 1B = -0.01 (negative accruals = high quality)
        #       raw_value = -(-0.01) = 0.01 (negation makes it positive for ranking)
        assert isinstance(result, FactorResult)
        assert result.raw_value == pytest.approx(0.01, abs=0.001)

        # Metadata contains actual accruals (negative)
        assert result.metadata['accruals_ratio'] == pytest.approx(-0.01, abs=0.0001)


class TestCFToNIRatioFactor:
    """CF-to-NI Ratio (현금흐름/순이익 비율) 팩터 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = CFToNIRatioFactor()

        # Then: 속성 검증
        assert factor.name == "CF_to_NI_Ratio"
        assert factor.category == FactorCategory.QUALITY
        assert factor.lookback_days == 365
        assert factor.min_required_days == 1

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_calculate_success_cash_backed(self, mock_connect):
        """현금 기반 이익 테스트 (ratio > 1.0)"""
        # Given: Cash-backed earnings (OCF > NI)
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (
            60_000_000,    # operating_cash_flow: $60M
            50_000_000,    # net_income: $50M
            2024           # fiscal_year
        )

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = CFToNIRatioFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='005930', region='KR')

        # Then: CF/NI = 60M / 50M = 1.2 (high quality)
        assert isinstance(result, FactorResult)
        assert result.factor_name == "CF_to_NI_Ratio"
        assert result.raw_value == pytest.approx(1.2, abs=0.01)
        assert result.metadata['cf_to_ni_ratio'] == pytest.approx(1.2, abs=0.01)

        # Confidence 0.9
        assert result.confidence == 0.9

    @patch('modules.factors.quality_factors.psycopg2.connect')
    def test_edge_case_zero_net_income(self, mock_connect):
        """net_income = 0 필터링 테스트"""
        # Given: Zero net income filtered by WHERE clause
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None

        mock_conn = Mock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        factor = CFToNIRatioFactor()

        # When: Calculate
        result = factor.calculate(data=None, ticker='ZERO_NI', region='US')

        # Then: None 반환
        assert result is None
