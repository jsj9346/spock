#!/usr/bin/env python3
"""
KIS API Price Query & Buy Order Tests (Day 2)

Tests price query and buy order execution functionality.

Run: python3 tests/test_kis_price_and_buy_day2.py
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


class TestKISPriceQuery:
    """Test suite for KIS API price query"""

    def test_mock_price_query(self):
        """Test mock mode price generation"""
        client = KISAPIClient(
            app_key="MOCK_KEY",
            app_secret="MOCK_SECRET",
            account_no="00000000-00",
            is_mock=True
        )

        price = client.get_current_price("005930")

        assert price is not None
        assert 10000 <= price <= 100000  # Mock price range
        print(f"✅ Mock price: {price:,.0f} KRW")

    @patch('requests.get')
    def test_real_price_query_success(self, mock_get):
        """Test successful real price query (mocked response)"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "output": {
                "stck_prpr": "71500",      # 주식 현재가
                "prdy_vrss": "1000",       # 전일 대비
                "prdy_ctrt": "1.42",       # 전일 대비율
                "acml_vol": "12345678"     # 누적 거래량
            }
        }
        mock_get.return_value = mock_response

        with ProductionModeTest():
            client = KISAPIClient(
                app_key="TEST_KEY_PRICE",
                app_secret="TEST_SECRET",
                account_no="12345678-01",
                is_mock=False
            )

            # Clear cached token
            client.access_token = None
            client.token_expiry = None

            # Mock the token request too
            with patch('requests.post') as mock_post_token:
                mock_token_response = Mock()
                mock_token_response.status_code = 200
                mock_token_response.json.return_value = {
                    "access_token": "test_token",
                    "expires_in": 86400
                }
                mock_post_token.return_value = mock_token_response

                price = client.get_current_price("005930")

            assert price == 71500.0
            print(f"✅ Real price query: {price:,.0f} KRW")

            # Verify API call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "/uapi/domestic-stock/v1/quotations/inquire-price" in call_args[0][0]
            assert call_args[1]['params']['FID_INPUT_ISCD'] == "005930"

    def test_price_query_invalid_ticker(self):
        """Test price query with invalid ticker"""
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

            # Test invalid tickers
            with pytest.raises(ValueError, match="Invalid ticker"):
                client.get_current_price("AAPL")  # Not 6 digits

            with pytest.raises(ValueError, match="Invalid ticker"):
                client.get_current_price("12345")  # Only 5 digits

        print("✅ Price query invalid ticker validation works")

    @patch('requests.get')
    def test_price_query_timeout(self, mock_get):
        """Test price query timeout handling"""
        import requests
        mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

        with ProductionModeTest():
            client = KISAPIClient(
                app_key="TEST_KEY_TIMEOUT_PRICE",
                app_secret="TEST_SECRET",
                account_no="12345678-01",
                is_mock=False
            )

            # Clear cached token
            client.access_token = None
            client.token_expiry = None

            # Mock token request
            with patch('requests.post') as mock_post_token:
                mock_token_response = Mock()
                mock_token_response.status_code = 200
                mock_token_response.json.return_value = {
                    "access_token": "test_token",
                    "expires_in": 86400
                }
                mock_post_token.return_value = mock_token_response

                with pytest.raises(requests.exceptions.Timeout):
                    client.get_current_price("005930")

        print("✅ Price query timeout handling works")

    @patch('requests.get')
    def test_price_query_malformed_response(self, mock_get):
        """Test price query with malformed response"""
        # Mock response without stck_prpr
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "output": {
                "error": "missing_price"
            }
        }
        mock_get.return_value = mock_response

        with ProductionModeTest():
            client = KISAPIClient(
                app_key="TEST_KEY_MALFORMED_PRICE",
                app_secret="TEST_SECRET",
                account_no="12345678-01",
                is_mock=False
            )

            # Clear cached token
            client.access_token = None
            client.token_expiry = None

            # Mock token request
            with patch('requests.post') as mock_post_token:
                mock_token_response = Mock()
                mock_token_response.status_code = 200
                mock_token_response.json.return_value = {
                    "access_token": "test_token",
                    "expires_in": 86400
                }
                mock_post_token.return_value = mock_token_response

                with pytest.raises(ValueError):
                    client.get_current_price("005930")

        print("✅ Price query malformed response handling works")


class TestKISBuyOrder:
    """Test suite for KIS API buy order"""

    def test_mock_buy_order(self):
        """Test mock mode buy order"""
        client = KISAPIClient(
            app_key="MOCK_KEY",
            app_secret="MOCK_SECRET",
            account_no="00000000-00",
            is_mock=True
        )

        result = client.execute_buy_order(
            ticker="005930",
            quantity=10,
            price=71000,
            order_type='00'
        )

        assert result['success'] is True
        assert result['order_id'].startswith("MOCK_BUY_")
        assert result['quantity'] == 10
        assert result['avg_price'] == 71000.0
        print(f"✅ Mock buy order: {result['order_id']}")

    @patch('requests.post')
    def test_real_buy_order_success(self, mock_post):
        """Test successful real buy order (mocked response)"""
        # Mock successful order response
        mock_order_response = Mock()
        mock_order_response.status_code = 200
        mock_order_response.json.return_value = {
            "rt_cd": "0",  # Success
            "msg1": "정상처리 되었습니다",
            "output": {
                "ODNO": "0000123456",
                "ORD_TMD": "153045"
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
                app_key="TEST_KEY_BUY",
                app_secret="TEST_SECRET",
                account_no="12345678-01",
                is_mock=False
            )

            # Clear cached token
            client.access_token = None
            client.token_expiry = None

            result = client.execute_buy_order(
                ticker="005930",
                quantity=10,
                price=71000,
                order_type='00'
            )

            assert result['success'] is True
            assert result['order_id'] == "0000123456"
            assert result['quantity'] == 10
            assert result['avg_price'] == 71000.0
            print(f"✅ Real buy order: {result['order_id']}")

    def test_buy_order_validation(self):
        """Test buy order input validation"""
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
                client.execute_buy_order("AAPL", 10, 100, '00')

            # Invalid quantity
            with pytest.raises(ValueError, match="Invalid quantity"):
                client.execute_buy_order("005930", -10, 100, '00')

            # Invalid price
            with pytest.raises(ValueError, match="Invalid price"):
                client.execute_buy_order("005930", 10, -100, '00')

            # Invalid order_type
            with pytest.raises(ValueError, match="Invalid order_type"):
                client.execute_buy_order("005930", 10, 100, '99')

        print("✅ Buy order input validation works")

    def test_buy_order_account_parsing(self):
        """Test account number parsing"""
        # Test with hyphen format
        client1 = KISAPIClient(
            app_key="MOCK_KEY",
            app_secret="MOCK_SECRET",
            account_no="12345678-01",
            is_mock=True
        )

        result1 = client1.execute_buy_order("005930", 10, 71000)
        assert result1['success'] is True

        # Test without hyphen format
        client2 = KISAPIClient(
            app_key="MOCK_KEY",
            app_secret="MOCK_SECRET",
            account_no="1234567801",
            is_mock=True
        )

        result2 = client2.execute_buy_order("005930", 10, 71000)
        assert result2['success'] is True

        print("✅ Account number parsing works")

    @patch('requests.post')
    def test_buy_order_rejected(self, mock_post):
        """Test buy order rejection handling"""
        # Mock rejected order response
        mock_order_response = Mock()
        mock_order_response.status_code = 200
        mock_order_response.json.return_value = {
            "rt_cd": "1",  # Failure
            "msg1": "주문가능금액이 부족합니다"
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
                app_key="TEST_KEY_REJECTED",
                app_secret="TEST_SECRET",
                account_no="12345678-01",
                is_mock=False
            )

            # Clear cached token
            client.access_token = None
            client.token_expiry = None

            result = client.execute_buy_order("005930", 10, 71000)

            assert result['success'] is False
            assert result['order_id'] is None
            assert "부족" in result['message']
            print(f"✅ Buy order rejection: {result['message']}")


if __name__ == '__main__':
    import sys

    print("\n" + "=" * 70)
    print("Running KIS Price Query & Buy Order Tests (Day 2)")
    print("=" * 70 + "\n")

    pytest.main([__file__, '-v', '-s'])

    print("\n" + "=" * 70)
    print("✅ All Day 2 tests passed!")
    print("=" * 70 + "\n")
