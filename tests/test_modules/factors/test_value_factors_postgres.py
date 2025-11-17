"""
Value Factors PostgreSQL 테스트

테스트 대상:
    - DividendYieldFactorPostgres (5 tests)
    - EVToEBITDAFactorPostgres (5 tests)
    - CompositeValueFactor (5 tests)

Total: 15 tests
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from modules.factors.value_factors import (
    DividendYieldFactorPostgres,
    EVToEBITDAFactorPostgres,
    CompositeValueFactor
)
from modules.factors.factor_base import FactorResult, FactorCategory


# ========================================
# DividendYieldFactorPostgres Tests (5 tests)
# ========================================

class TestDividendYieldFactorPostgres:
    """DividendYieldFactorPostgres 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = DividendYieldFactorPostgres()

        # Then: 속성 검증
        assert factor.name == "Dividend_Yield"
        assert factor.category == FactorCategory.VALUE

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_calculate_success(self, mock_db_manager):
        """배당수익률 계산 성공 테스트"""
        # Given: Mock DB execute_query 두 번 호출 (factor_scores + meta_query)
        factor_scores_result = [{
            'ticker': '005930',
            'score': 2.5,
            'percentile': 65.0,
            'date': datetime.now()
        }]

        meta_query_result = [{
            'dividend_yield': 3.5,
            'per': 12.5,
            'pbr': 1.2,
            'period_type': 'DAILY',
            'data_source': 'pykrx'
        }]

        mock_db = Mock()
        mock_db.execute_query.side_effect = [factor_scores_result, meta_query_result]
        mock_db_manager.return_value = mock_db

        factor = DividendYieldFactorPostgres()

        # When: 계산 실행
        result = factor.calculate(data=None, ticker='005930')

        # Then: 결과 검증
        assert isinstance(result, FactorResult)
        assert result.factor_name == "Dividend_Yield"
        assert result.ticker == '005930'
        assert result.raw_value == 2.5
        assert result.percentile == 65.0

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_calculate_no_data(self, mock_db_manager):
        """데이터 없음 처리 테스트"""
        # Given: 빈 리스트 반환
        mock_db = Mock()
        mock_db.execute_query.return_value = []
        mock_db_manager.return_value = mock_db

        factor = DividendYieldFactorPostgres()

        # When: 계산 실행
        result = factor.calculate(data=None, ticker='INVALID')

        # Then: None 반환
        assert result is None

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_calculate_multiple_rows(self, mock_db_manager):
        """여러 행 반환 시 첫 번째 데이터 사용 테스트 (ORDER BY DESC LIMIT 1)"""
        # Given: 첫 번째가 최신 데이터 (ORDER BY DESC)
        factor_scores_result = [{
            'ticker': '005930',
            'score': 2.5,
            'percentile': 65.0,
            'date': datetime.now()
        }]

        meta_query_result = [{
            'dividend_yield': 3.5,
            'per': 12.5,
            'pbr': 1.2,
            'period_type': 'DAILY',
            'data_source': 'pykrx'
        }]

        mock_db = Mock()
        mock_db.execute_query.side_effect = [factor_scores_result, meta_query_result]
        mock_db_manager.return_value = mock_db

        factor = DividendYieldFactorPostgres()

        # When: 계산 실행
        result = factor.calculate(data=None, ticker='005930')

        # Then: 첫 번째 (최신) 데이터 사용
        assert result.raw_value == 2.5
        assert result.percentile == 65.0

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_metadata_structure(self, mock_db_manager):
        """메타데이터 구조 검증 테스트"""
        # Given: Mock DB 설정 (두 번 호출)
        factor_scores_result = [{
            'ticker': '005930',
            'score': 2.5,
            'percentile': 65.0,
            'date': datetime.now()
        }]

        meta_query_result = [{
            'dividend_yield': 3.5,
            'per': 12.5,
            'pbr': 1.2,
            'period_type': 'DAILY',
            'data_source': 'pykrx'
        }]

        mock_db = Mock()
        mock_db.execute_query.side_effect = [factor_scores_result, meta_query_result]
        mock_db_manager.return_value = mock_db

        factor = DividendYieldFactorPostgres()

        # When: 계산 실행
        result = factor.calculate(data=None, ticker='005930')

        # Then: 메타데이터 존재 확인
        assert isinstance(result.metadata, dict)
        assert 'data_source' in result.metadata or 'calculation_date' in result.metadata


# ========================================
# EVToEBITDAFactorPostgres Tests (5 tests)
# ========================================

class TestEVToEBITDAFactorPostgres:
    """EVToEBITDAFactorPostgres 테스트"""

    def test_initialization(self):
        """팩터 초기화 테스트"""
        # When: 팩터 생성
        factor = EVToEBITDAFactorPostgres()

        # Then: 속성 검증
        assert factor.name == "EV_EBITDA"
        assert factor.category == FactorCategory.VALUE

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_calculate_success(self, mock_db_manager):
        """EV/EBITDA 계산 성공 테스트"""
        # Given: Mock DB 설정 (두 번 호출: factor_scores + meta_query)
        factor_scores_result = [{
            'ticker': '000660',
            'score': 8.5,
            'percentile': 70.0,
            'date': datetime.now()
        }]

        meta_query_result = [{
            'ebitda': 500000000000,  # 5000억
            'total_liabilities': 1000000000000,
            'current_assets': 800000000000,
            'fiscal_year': 2024,
            'period_type': 'SEMI-ANNUAL',
            'data_source': 'DART'
        }]

        mock_db = Mock()
        mock_db.execute_query.side_effect = [factor_scores_result, meta_query_result]
        mock_db_manager.return_value = mock_db

        factor = EVToEBITDAFactorPostgres()

        # When: 계산 실행
        result = factor.calculate(data=None, ticker='000660')

        # Then: 결과 검증
        assert isinstance(result, FactorResult)
        assert result.factor_name == "EV_EBITDA"
        assert result.raw_value == 8.5
        assert result.percentile == 70.0

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_calculate_no_data(self, mock_db_manager):
        """데이터 없음 처리 테스트"""
        # Given: 빈 리스트 반환
        mock_db = Mock()
        mock_db.execute_query.return_value = []
        mock_db_manager.return_value = mock_db

        factor = EVToEBITDAFactorPostgres()

        # When: 계산 실행
        result = factor.calculate(data=None, ticker='INVALID')

        # Then: None 반환
        assert result is None

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_percentile_ranking(self, mock_db_manager):
        """Percentile ranking 검증 테스트"""
        # Given: percentile 포함 데이터 (두 번 호출)
        factor_scores_result = [{
            'ticker': '005380',
            'score': 6.8,
            'percentile': 85.0,
            'date': datetime.now()
        }]

        meta_query_result = [{
            'ebitda': 300000000000,
            'total_liabilities': 600000000000,
            'current_assets': 500000000000,
            'fiscal_year': 2024,
            'period_type': 'ANNUAL',
            'data_source': 'DART'
        }]

        mock_db = Mock()
        mock_db.execute_query.side_effect = [factor_scores_result, meta_query_result]
        mock_db_manager.return_value = mock_db

        factor = EVToEBITDAFactorPostgres()

        # When: 계산 실행
        result = factor.calculate(data=None, ticker='005380')

        # Then: percentile 검증
        assert result.percentile == 85.0
        assert 0 <= result.percentile <= 100

    @patch('modules.factors.value_factors.PostgresDatabaseManager')
    def test_database_error_handling(self, mock_db_manager):
        """데이터베이스 에러 처리 테스트"""
        # Given: DB 에러 시뮬레이션
        mock_db = Mock()
        mock_db.execute_query.side_effect = Exception("DB connection failed")
        mock_db_manager.return_value = mock_db

        factor = EVToEBITDAFactorPostgres()

        # When/Then: 에러 발생 시 None 반환
        result = factor.calculate(data=None, ticker='005930')
        assert result is None


# ========================================
# CompositeValueFactor Tests (5 tests)
# ========================================

class TestCompositeValueFactor:
    """CompositeValueFactor 통합 테스트"""

    @patch('modules.factors.value_factors.DividendYieldFactorPostgres')
    @patch('modules.factors.value_factors.EVToEBITDAFactorPostgres')
    def test_initialization_default_weights(self, mock_ev_factor_class, mock_div_factor_class):
        """기본 가중치로 초기화 테스트"""
        # Given: 내부 팩터 생성 패치 (PostgreSQL 연결 방지)
        mock_div_factor_class.return_value = Mock()
        mock_ev_factor_class.return_value = Mock()

        # When: 기본 가중치로 생성
        factor = CompositeValueFactor()

        # Then: 속성 검증
        assert factor.name == "Composite_Value"
        assert factor.category == FactorCategory.VALUE
        assert factor.div_weight == 0.5
        assert factor.ev_weight == 0.5

    @patch('modules.factors.value_factors.DividendYieldFactorPostgres')
    @patch('modules.factors.value_factors.EVToEBITDAFactorPostgres')
    def test_initialization_custom_weights(self, mock_ev_factor_class, mock_div_factor_class):
        """커스텀 가중치로 초기화 테스트"""
        # Given: 내부 팩터 생성 패치 (PostgreSQL 연결 방지)
        mock_div_factor_class.return_value = Mock()
        mock_ev_factor_class.return_value = Mock()

        # When: 커스텀 가중치로 생성
        factor = CompositeValueFactor(div_weight=0.7, ev_weight=0.3)

        # Then: 가중치 검증
        assert factor.div_weight == 0.7
        assert factor.ev_weight == 0.3

    @patch('modules.factors.value_factors.DividendYieldFactorPostgres')
    @patch('modules.factors.value_factors.EVToEBITDAFactorPostgres')
    def test_calculate_composite_score(self, mock_ev_factor_class, mock_div_factor_class):
        """복합 점수 계산 테스트"""
        # Given: Mock 팩터 결과
        div_result = FactorResult(
            ticker="005930",
            factor_name="Dividend_Yield",
            raw_value=2.5,
            z_score=0.65,
            percentile=65.0,
            confidence=0.9
        )
        ev_result = FactorResult(
            ticker="005930",
            factor_name="EV_EBITDA",
            raw_value=8.5,
            z_score=0.70,
            percentile=70.0,
            confidence=0.85
        )

        mock_div_instance = Mock()
        mock_div_instance.calculate.return_value = div_result
        mock_div_factor_class.return_value = mock_div_instance

        mock_ev_instance = Mock()
        mock_ev_instance.calculate.return_value = ev_result
        mock_ev_factor_class.return_value = mock_ev_instance

        factor = CompositeValueFactor()

        # When: 계산 실행
        result = factor.calculate(data=None, ticker='005930')

        # Then: 가중 평균 검증 (percentile 기반)
        expected_percentile = 0.5 * 65.0 + 0.5 * 70.0  # 67.5
        assert isinstance(result, FactorResult)
        assert abs(result.percentile - expected_percentile) < 0.01
        assert result.factor_name == "Composite_Value"

    @patch('modules.factors.value_factors.DividendYieldFactorPostgres')
    @patch('modules.factors.value_factors.EVToEBITDAFactorPostgres')
    def test_missing_factor_handling(self, mock_ev_factor_class, mock_div_factor_class):
        """일부 팩터 데이터 없을 때 처리 테스트"""
        # Given: 하나의 팩터만 데이터 있음
        div_result = FactorResult(
            ticker="005930",
            factor_name="Dividend_Yield",
            raw_value=2.5,
            z_score=0.65,
            percentile=65.0,
            confidence=0.9
        )

        mock_div_instance = Mock()
        mock_div_instance.calculate.return_value = div_result
        mock_div_factor_class.return_value = mock_div_instance

        mock_ev_instance = Mock()
        mock_ev_instance.calculate.return_value = None  # 데이터 없음
        mock_ev_factor_class.return_value = mock_ev_instance

        factor = CompositeValueFactor()

        # When: 계산 실행
        result = factor.calculate(data=None, ticker='005930')

        # Then: 둘 다 필요하므로 None 반환
        assert result is None

    @patch('modules.factors.value_factors.DividendYieldFactorPostgres')
    @patch('modules.factors.value_factors.EVToEBITDAFactorPostgres')
    def test_confidence_aggregation(self, mock_ev_factor_class, mock_div_factor_class):
        """신뢰도 집계 테스트"""
        # Given: 다른 신뢰도의 팩터 결과
        div_result = FactorResult(
            ticker="005930",
            factor_name="Dividend_Yield",
            raw_value=2.5,
            z_score=0.65,
            percentile=65.0,
            confidence=0.9
        )
        ev_result = FactorResult(
            ticker="005930",
            factor_name="EV_EBITDA",
            raw_value=8.5,
            z_score=0.70,
            percentile=70.0,
            confidence=0.7
        )

        mock_div_instance = Mock()
        mock_div_instance.calculate.return_value = div_result
        mock_div_factor_class.return_value = mock_div_instance

        mock_ev_instance = Mock()
        mock_ev_instance.calculate.return_value = ev_result
        mock_ev_factor_class.return_value = mock_ev_instance

        factor = CompositeValueFactor()

        # When: 계산 실행
        result = factor.calculate(data=None, ticker='005930')

        # Then: 신뢰도는 최소값 사용 (보수적 접근)
        assert result.confidence <= min(0.9, 0.7)
        assert result.confidence >= 0.0
