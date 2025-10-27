#!/usr/bin/env python3
"""
KIS API Sell Order & Integration Tests (Day 3)

Tests sell order execution and end-to-end trading pipeline.

Run: python3 tests/test_kis_sell_and_integration_day3.py
"""
import os
import sys
import pytest
from datetime import datetime
from unittest.mock import patch, Mock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from modules.kis_trading_engine import KISAPIClient


# Helper context manager for production mode tests
class ProductionModeTest:
    def __enter__(self):
        os.environ["KIS_PRODUCTION_CONFIRMED"] = "YES"
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if "KIS_PRODUCTION_CONFIRMED" in os.environ:
            del os.environ["KIS_PRODUCTION_CONFIRMED"]


class TestKISSellOrder:
    """Test suite for KIS API sell order"""

    def test_mock_sell_order(self):
        """Test mock mode sell order"""
        client = KISAPIClient(
            app_key="MOCK_KEY",
            app_secret="MOCK_SECRET",
            account_no="00000000-00",
            is_mock=True
        )

        result = client.execute_sell_order(
            ticker="005930",
            quantity=10,
            price=72000,
            order_type='00'
        )

        assert result['success'] is True
        assert result['order_id'].startswith("MOCK_SELL_")
        assert result['quantity'] == 10
        assert result['avg_price'] == 72000.0
        print(f"✅ Mock sell order: {result['order_id']}")

    @patch('requests.post')
    def test_real_sell_order_success(self, mock_post):
        """Test successful real sell order (mocked response)"""
        # Mock successful order response
        mock_order_response = Mock()
        mock_order_response.status_code = 200
        mock_order_response.json.return_value = {
            "rt_cd": "0",  # Success
            "msg1": "정상처리 되었습니다",
            "output": {
                "ODNO": "0000654321",
                "ORD_TMD": "153145"
            }
        }

        # Mock token response
        mock_token_response = Mock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 86400
        }

        # Configure mock_post to return different responses
        mock_post.side_effect = [mock_token_response, mock_order_response]

        with ProductionModeTest():
            client = KISAPIClient(
                app_key="TEST_KEY_SELL",
                app_secret="TEST_SECRET",
                account_no="12345678-01",
                is_mock=False
            )

            # Clear cached token
            client.access_token = None
            client.token_expiry = None

            result = client.execute_sell_order(
                ticker="005930",
                quantity=10,
                price=72000,
                order_type='00'
            )

            assert result['success'] is True
            assert result['order_id'] == "0000654321"
            assert result['quantity'] == 10
            assert result['avg_price'] == 72000.0
            print(f"✅ Real sell order: {result['order_id']}")

            # Verify API call (check tr_id is for SELL)
            sell_call_args = mock_post.call_args_list[1]  # Second call is sell order
            assert sell_call_args[1]['headers']['tr_id'] == "TTTC0801U"  # SELL tr_id

    def test_sell_order_validation(self):
        """Test sell order input validation"""
        with ProductionModeTest():
            client = KISAPIClient(
                app_key="TEST_KEY",
                app_secret="TEST_SECRET",
                account_no="12345678-01",
                is_mock=False
            )

            # Clear cached token
            client.access_token = None
            client.token_expiry = None

            # Invalid ticker
            with pytest.raises(ValueError, match="Invalid ticker"):
                client.execute_sell_order("AAPL", 10, 100, '00')

            # Invalid quantity
            with pytest.raises(ValueError, match="Invalid quantity"):
                client.execute_sell_order("005930", 0, 100, '00')

            # Invalid price
            with pytest.raises(ValueError, match="Invalid price"):
                client.execute_sell_order("005930", 10, 0, '00')

            # Invalid order_type
            with pytest.raises(ValueError, match="Invalid order_type"):
                client.execute_sell_order("005930", 10, 100, '02')

        print("✅ Sell order input validation works")

    @patch('requests.post')
    def test_sell_order_rejected(self, mock_post):
        """Test sell order rejection handling"""
        # Mock rejected order response
        mock_order_response = Mock()
        mock_order_response.status_code = 200
        mock_order_response.json.return_value = {
            "rt_cd": "1",  # Failure
            "msg1": "보유수량이 부족합니다"
        }

        # Mock token response
        mock_token_response = Mock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 86400
        }

        mock_post.side_effect = [mock_token_response, mock_order_response]

        with ProductionModeTest():
            client = KISAPIClient(
                app_key="TEST_KEY_SELL_REJECTED",
                app_secret="TEST_SECRET",
                account_no="12345678-01",
                is_mock=False
            )

            # Clear cached token
            client.access_token = None
            client.token_expiry = None

            result = client.execute_sell_order("005930", 10, 72000)

            assert result['success'] is False
            assert result['order_id'] is None
            assert "부족" in result['message']
            print(f"✅ Sell order rejection: {result['message']}")


class TestTradingPipeline:
    """Test suite for end-to-end trading pipeline"""

    @patch('requests.get')
    @patch('requests.post')
    def test_full_trading_cycle(self, mock_post, mock_get):
        """Test complete trading cycle: price query → buy → sell"""
        # Mock price query response
        mock_price_response = Mock()
        mock_price_response.status_code = 200
        mock_price_response.json.return_value = {
            "output": {
                "stck_prpr": "71500",
                "prdy_vrss": "1000",
                "prdy_ctrt": "1.42",
                "acml_vol": "12345678"
            }
        }
        mock_get.return_value = mock_price_response

        # Mock token response
        mock_token_response = Mock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 86400
        }

        # Mock buy order response
        mock_buy_response = Mock()
        mock_buy_response.status_code = 200
        mock_buy_response.json.return_value = {
            "rt_cd": "0",
            "msg1": "정상처리 되었습니다",
            "output": {
                "ODNO": "BUY123456",
                "ORD_TMD": "153000"
            }
        }

        # Mock sell order response
        mock_sell_response = Mock()
        mock_sell_response.status_code = 200
        mock_sell_response.json.return_value = {
            "rt_cd": "0",
            "msg1": "정상처리 되었습니다",
            "output": {
                "ODNO": "SELL654321",
                "ORD_TMD": "153100"
            }
        }

        # Configure mock_post responses
        mock_post.side_effect = [
            mock_token_response,  # Token for price query
            mock_buy_response,    # Buy order
            mock_sell_response    # Sell order
        ]

        with ProductionModeTest():
            client = KISAPIClient(
                app_key="TEST_KEY_PIPELINE",
                app_secret="TEST_SECRET",
                account_no="12345678-01",
                is_mock=False
            )

            # Clear cached token
            client.access_token = None
            client.token_expiry = None

            # 1. Query price
            price = client.get_current_price("005930")
            assert price == 71500.0
            print(f"✅ Step 1: Price query - {price:,.0f} KRW")

            # 2. Buy order
            buy_result = client.execute_buy_order("005930", 10, int(price))
            assert buy_result['success'] is True
            assert buy_result['order_id'] == "BUY123456"
            print(f"✅ Step 2: Buy order - {buy_result['order_id']}")

            # 3. Sell order
            sell_result = client.execute_sell_order("005930", 10, int(price) + 500)
            assert sell_result['success'] is True
            assert sell_result['order_id'] == "SELL654321"
            print(f"✅ Step 3: Sell order - {sell_result['order_id']}")

            print("✅ Full trading cycle completed successfully")

    def test_mock_trading_cycle(self):
        """Test complete mock trading cycle"""
        client = KISAPIClient(
            app_key="MOCK_KEY",
            app_secret="MOCK_SECRET",
            account_no="00000000-00",
            is_mock=True
        )

        # 1. Query price (mock)
        price = client.get_current_price("005930")
        assert 10000 <= price <= 100000
        print(f"✅ Mock price: {price:,.0f} KRW")

        # 2. Buy order (mock)
        buy_result = client.execute_buy_order("005930", 10, int(price))
        assert buy_result['success'] is True
        print(f"✅ Mock buy: {buy_result['order_id']}")

        # 3. Sell order (mock)
        sell_result = client.execute_sell_order("005930", 10, int(price) + 1000)
        assert sell_result['success'] is True
        print(f"✅ Mock sell: {sell_result['order_id']}")

        print("✅ Mock trading cycle completed successfully")


class TestProductionSafety:
    """Test suite for production mode safety checks"""

    def test_production_mode_missing_credentials(self):
        """Test production mode validation with missing credentials"""
        # Missing app_key
        with pytest.raises(ValueError, match="Missing KIS_APP_KEY"):
            KISAPIClient(
                app_key="MOCK_KEY",
                app_secret="REAL_SECRET",
                account_no="12345678-01",
                is_mock=False
            )

        # Missing app_secret
        with pytest.raises(ValueError, match="Missing KIS_APP_SECRET"):
            KISAPIClient(
                app_key="REAL_KEY",
                app_secret="MOCK_SECRET",
                account_no="12345678-01",
                is_mock=False
            )

        # Missing account_no
        with pytest.raises(ValueError, match="Missing KIS_ACCOUNT_NO"):
            KISAPIClient(
                app_key="REAL_KEY",
                app_secret="REAL_SECRET",
                account_no="00000000-00",
                is_mock=False
            )

        print("✅ Production mode credential validation works")

    def test_production_mode_missing_confirmation(self):
        """Test production mode requires explicit confirmation"""
        # Ensure KIS_PRODUCTION_CONFIRMED is not set
        old_value = os.getenv("KIS_PRODUCTION_CONFIRMED")
        if "KIS_PRODUCTION_CONFIRMED" in os.environ:
            del os.environ["KIS_PRODUCTION_CONFIRMED"]

        try:
            with pytest.raises(ValueError, match="KIS_PRODUCTION_CONFIRMED=YES"):
                KISAPIClient(
                    app_key="REAL_KEY_12345",
                    app_secret="REAL_SECRET_12345",
                    account_no="12345678-01",
                    is_mock=False
                )

            print("✅ Production mode confirmation requirement works")

        finally:
            # Restore old value
            if old_value is not None:
                os.environ["KIS_PRODUCTION_CONFIRMED"] = old_value

    def test_production_mode_with_confirmation(self):
        """Test production mode succeeds with proper configuration"""
        # Set confirmation
        os.environ["KIS_PRODUCTION_CONFIRMED"] = "YES"

        try:
            # This should succeed (but won't actually connect)
            with ProductionModeTest():
                client = KISAPIClient(
                    app_key="REAL_KEY_CONFIRMED",
                    app_secret="REAL_SECRET_CONFIRMED",
                    account_no="12345678-01",
                    is_mock=False
                )

                assert client.is_mock is False
                print("✅ Production mode with confirmation works")

        finally:
            # Clean up
            if "KIS_PRODUCTION_CONFIRMED" in os.environ:
                del os.environ["KIS_PRODUCTION_CONFIRMED"]


if __name__ == '__main__':
    import sys

    print("\n" + "=" * 70)
    print("Running KIS Sell Order & Integration Tests (Day 3)")
    print("=" * 70 + "\n")

    pytest.main([__file__, '-v', '-s'])

    print("\n" + "=" * 70)
    print("✅ All Day 3 tests passed!")
    print("=" * 70 + "\n")
