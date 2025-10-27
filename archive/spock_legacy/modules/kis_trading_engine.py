#!/usr/bin/env python3
"""
KIS Trading Engine - Simplified Stock Trading Execution Engine

🎯 Core Features:
- KIS API-based order execution (buy/sell)
- Tick size compliance for Korean stock market
- Position tracking and P&L calculation
- Stop loss (-8%) and take profit (+20%) automation
- Fee-adjusted calculations

💰 Trading Strategy:
- Stan Weinstein Stage 2 entry points
- Mark Minervini 7-8% stop loss rule
- William O'Neil 20-25% profit taking

📊 Reference: KIS Developers API, SQLite local storage

Design: MVP (Minimum Viable Product) - ~800-1,000 lines
Code Reuse: 60-70% from Makenaide trading_engine.py (2,419 lines)
"""

import os
import time
import sqlite3
import logging
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum
from dotenv import load_dotenv

# Phase 5 Task 4: Portfolio Management Integration
from modules.portfolio_manager import PortfolioManager

# Phase 6: Blacklist Manager Integration
from modules.blacklist_manager import BlacklistManager

# Load environment variables
load_dotenv()

# Logger setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('kis_trading_engine')


# ========================================================================
# Constants and Configuration
# ========================================================================

# Tick Size Rules for Korean Stock Market
TICK_SIZE_RULES_KRW = {
    # (min_price, max_price): tick_size
    (0, 1000): 1,                    # <1K: 1 KRW
    (1000, 5000): 5,                 # 1K-5K: 5 KRW
    (5000, 10000): 10,               # 5K-10K: 10 KRW
    (10000, 50000): 50,              # 10K-50K: 50 KRW
    (50000, 100000): 100,            # 50K-100K: 100 KRW
    (100000, 500000): 500,           # 100K-500K: 500 KRW
    (500000, float('inf')): 1000     # 500K+: 1,000 KRW
}

# Trading Fees (2025 기준)
TRADING_FEES = {
    'buy': {
        'commission': 0.00015,  # 0.015% (온라인 증권사)
        'securities_tax': 0.0,  # 매수 시 없음
        'total': 0.00015
    },
    'sell': {
        'commission': 0.00015,  # 0.015%
        'securities_tax': 0.0023,  # 0.23% (KOSPI), 0% (KOSDAQ)
        'total': 0.00245  # KOSPI 기준 (worst case)
    }
}


# ========================================================================
# Enums and Data Classes
# ========================================================================

class OrderType(Enum):
    """주문 타입"""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(Enum):
    """주문 상태"""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PARTIAL = "PARTIAL"
    API_ERROR = "API_ERROR"
    INVALID_INPUT = "INVALID_INPUT"


class TradeStatus(Enum):
    """거래 상태"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass
class TradeResult:
    """거래 결과"""
    success: bool
    order_type: OrderType
    ticker: str
    quantity: float
    price: float
    amount: float
    fee: float
    order_id: Optional[str] = None
    message: str = ""
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')


@dataclass
class PositionInfo:
    """포지션 정보"""
    ticker: str
    quantity: float
    avg_buy_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    buy_timestamp: datetime
    hold_days: int
    region: str = 'KR'

    @property
    def should_stop_loss(self) -> bool:
        """손절 조건 체크 (-8%)"""
        return self.unrealized_pnl_percent <= -8.0

    @property
    def should_take_profit(self) -> bool:
        """익절 조건 체크 (+20%)"""
        return self.unrealized_pnl_percent >= 20.0


@dataclass
class TradingConfig:
    """거래 설정"""
    min_order_amount_krw: float = 10000  # 최소 주문 금액
    max_positions: int = 10  # 최대 동시 보유 종목
    stop_loss_percent: float = -8.0  # 손절 비율 (%)
    take_profit_percent: float = 20.0  # 익절 비율 (%)
    api_rate_limit_delay: float = 0.1  # API 호출 간격 (초)
    order_type: str = '00'  # 00:지정가, 01:시장가


# ========================================================================
# Helper Functions
# ========================================================================

def adjust_price_to_tick_size(price: float) -> int:
    """
    KIS API 주문가격을 호가 단위에 맞게 조정

    Args:
        price: 원래 가격 (float)

    Returns:
        조정된 가격 (int)

    Examples:
        >>> adjust_price_to_tick_size(9999)
        9995
        >>> adjust_price_to_tick_size(49999)
        49950
        >>> adjust_price_to_tick_size(99999)
        99900
    """
    for (min_price, max_price), tick_size in TICK_SIZE_RULES_KRW.items():
        if min_price <= price < max_price:
            return int(round(price / tick_size) * tick_size)
    return int(price)


def calculate_fee_adjusted_amount(amount_krw: float, is_buy: bool = True) -> Dict[str, float]:
    """
    수수료 반영한 실제 거래 금액 계산

    Args:
        amount_krw: 거래 금액
        is_buy: True면 매수, False면 매도

    Returns:
        {
            'original_amount': 원래 금액,
            'adjusted_amount': 수수료 차감 후 금액,
            'fee': 수수료,
            'fee_rate': 수수료율
        }
    """
    if is_buy:
        fee_rate = TRADING_FEES['buy']['total']
        adjusted_amount = amount_krw / (1 + fee_rate)
        fee = amount_krw - adjusted_amount
    else:
        fee_rate = TRADING_FEES['sell']['total']
        adjusted_amount = amount_krw * (1 - fee_rate)
        fee = amount_krw - adjusted_amount

    return {
        'original_amount': amount_krw,
        'adjusted_amount': adjusted_amount,
        'fee': fee,
        'fee_rate': fee_rate
    }


# ========================================================================
# Rate Limiter
# ========================================================================

class RateLimiter:
    """
    API 호출 제한 관리자

    KIS API 제한:
    - 초당 요청: 20 req/sec
    - 분당 요청: 1,000 req/min
    """

    def __init__(self, max_requests: int = 20, window: float = 1.0):
        self.max_requests = max_requests
        self.window = window
        self.requests = []

    def wait_if_needed(self):
        """필요시 대기"""
        now = time.time()

        # Remove old requests outside window
        self.requests = [req_time for req_time in self.requests if now - req_time < self.window]

        # Check if rate limit exceeded
        if len(self.requests) >= self.max_requests:
            sleep_time = self.window - (now - self.requests[0])
            if sleep_time > 0:
                logger.debug(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
                self.requests = []

        # Record this request
        self.requests.append(now)


# ========================================================================
# KIS API Client
# ========================================================================

class KISAPIClient:
    """
    KIS API 클라이언트 (Simplified)

    Note: This is a simplified mock implementation for MVP.
    For production, use a proper KIS API library like 'mojito' or implement full OAuth flow.
    """

    def __init__(self, app_key: str, app_secret: str, account_no: str, base_url: str = None, is_mock: bool = True):
        self.app_key = app_key
        self.app_secret = app_secret
        self.account_no = account_no
        self.is_mock = is_mock

        if base_url:
            self.base_url = base_url
        elif is_mock:
            self.base_url = "https://openapivts.koreainvestment.com:29443"  # Mock/Virtual Trading
        else:
            self.base_url = "https://openapi.koreainvestment.com:9443"  # Real Trading

        self.access_token = None
        self.token_expiry = None
        self.rate_limiter = RateLimiter(max_requests=20, window=1.0)

        # Try to load cached token (production mode only)
        if not is_mock:
            self._load_token_from_cache()
            self._validate_production_mode()

    def get_access_token(self) -> str:
        """
        Access token 발급 (24시간 유효)

        KIS API OAuth 2.0 인증
        - Endpoint: POST /oauth2/tokenP
        - Rate Limit: 1 request/day
        - Token Validity: 24 hours

        Returns:
            Access token (JWT format)

        Raises:
            requests.HTTPError: API request failed
            ValueError: Invalid credentials or response
        """
        # 1. Check if existing token is still valid
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            logger.info(f"✅ Using cached access token (expires: {self.token_expiry})")
            return self.access_token

        # 2. Mock mode fallback
        if self.is_mock:
            self.access_token = f"MOCK_TOKEN_{datetime.now().strftime('%Y%m%d')}"
            self.token_expiry = datetime.now() + timedelta(hours=24)
            logger.info("✅ Mock access token generated")
            return self.access_token

        # 3. Real OAuth 2.0 token request
        logger.info("🔐 Requesting new KIS API access token...")

        try:
            # 3a. Prepare request
            url = f"{self.base_url}/oauth2/tokenP"
            headers = {
                "content-type": "application/json; charset=utf-8"
            }
            body = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret
            }

            # 3b. Send POST request
            response = requests.post(url, headers=headers, json=body, timeout=10)

            # 3c. Handle errors
            if response.status_code != 200:
                error_msg = f"Token request failed: {response.status_code} - {response.text}"
                logger.error(f"❌ {error_msg}")
                raise requests.HTTPError(error_msg)

            # 3d. Parse response
            data = response.json()

            if "access_token" not in data:
                error_msg = f"Invalid response (missing access_token): {data}"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)

            # 3e. Store token and expiry
            self.access_token = data["access_token"]
            expires_in = data.get("expires_in", 86400)  # Default 24 hours
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

            logger.info(f"✅ Access token obtained successfully")
            logger.info(f"   Token type: {data.get('token_type', 'Bearer')}")
            logger.info(f"   Expires at: {self.token_expiry}")

            # 3f. Save token to cache file (for 24-hour reuse)
            self._save_token_to_cache()

            return self.access_token

        except requests.exceptions.Timeout:
            logger.error("❌ Token request timed out (>10s)")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Token request failed: {e}")
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"❌ Failed to parse token response: {e}")
            raise

    def _save_token_to_cache(self):
        """
        Save access token to cache file for 24-hour reuse

        File: data/.kis_token_cache.json
        Format: {
            "access_token": "eyJ0eXAi...",
            "token_expiry": "2025-10-21T09:00:00",
            "app_key": "PA12..." (for validation)
        }
        """
        try:
            # Determine cache file path (same directory as db if using db_path pattern)
            cache_dir = os.path.dirname(os.path.abspath(__file__))
            if hasattr(self, 'db_path'):
                cache_dir = os.path.dirname(self.db_path)
            else:
                # Default to data directory
                cache_dir = os.path.join(os.path.dirname(cache_dir), 'data')

            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, '.kis_token_cache.json')

            cache_data = {
                "access_token": self.access_token,
                "token_expiry": self.token_expiry.isoformat(),
                "app_key": self.app_key  # For validation
            }

            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)

            logger.debug(f"💾 Token cached to {cache_file}")

        except Exception as e:
            logger.warning(f"⚠️  Failed to cache token: {e}")

    def _load_token_from_cache(self):
        """
        Load cached access token if still valid

        Returns:
            True if cached token loaded successfully
        """
        try:
            # Determine cache file path
            cache_dir = os.path.dirname(os.path.abspath(__file__))
            if hasattr(self, 'db_path'):
                cache_dir = os.path.dirname(self.db_path)
            else:
                cache_dir = os.path.join(os.path.dirname(cache_dir), 'data')

            cache_file = os.path.join(cache_dir, '.kis_token_cache.json')

            if not os.path.exists(cache_file):
                logger.debug("📂 No token cache file found")
                return False

            with open(cache_file, 'r') as f:
                cache_data = json.load(f)

            # Validate cache
            if cache_data.get("app_key") != self.app_key:
                logger.warning("⚠️  Cached token belongs to different app_key")
                return False

            # Check expiry
            token_expiry = datetime.fromisoformat(cache_data["token_expiry"])
            if datetime.now() >= token_expiry:
                logger.debug("⏰ Cached token expired")
                return False

            # Load token
            self.access_token = cache_data["access_token"]
            self.token_expiry = token_expiry

            logger.info(f"✅ Loaded cached token (expires: {self.token_expiry})")
            return True

        except Exception as e:
            logger.warning(f"⚠️  Failed to load cached token: {e}")
            return False

    def _validate_production_mode(self):
        """
        Validate configuration before real trading

        Raises:
            ValueError: Missing or invalid configuration
        """
        # 1. Check credentials
        if not self.app_key or self.app_key == "MOCK_KEY":
            raise ValueError("Missing KIS_APP_KEY for production mode")

        if not self.app_secret or self.app_secret == "MOCK_SECRET":
            raise ValueError("Missing KIS_APP_SECRET for production mode")

        if not self.account_no or self.account_no == "MOCK_ACCOUNT" or self.account_no == "00000000-00":
            raise ValueError("Missing KIS_ACCOUNT_NO for production mode")

        # 2. Display prominent warning
        logger.warning("=" * 70)
        logger.warning("⚠️  PRODUCTION MODE ENABLED - REAL MONEY TRADING ⚠️")
        logger.warning("   All orders will be executed with real money")
        logger.warning("   Make sure you understand the risks")
        logger.warning(f"   Account: {self.account_no[:4]}****{self.account_no[-2:]}")
        logger.warning("=" * 70)

        # 3. Require explicit confirmation
        confirmation = os.getenv("KIS_PRODUCTION_CONFIRMED", "NO")
        if confirmation != "YES":
            logger.error("❌ Production mode requires KIS_PRODUCTION_CONFIRMED=YES in .env")
            raise ValueError(
                "Production mode requires KIS_PRODUCTION_CONFIRMED=YES in .env file. "
                "This is a safety measure to prevent accidental real trading."
            )

        logger.info("✅ Production mode validation passed")

    def get_current_price(self, ticker: str) -> float:
        """
        현재가 조회

        Args:
            ticker: 종목코드 (6자리)

        Returns:
            현재가 (float)
        """
        self.rate_limiter.wait_if_needed()

        if self.is_mock:
            # Mock price for testing
            import random
            mock_price = random.uniform(10000, 100000)
            logger.debug(f"Mock price for {ticker}: {mock_price:.0f} KRW")
            return mock_price

        # Real KIS API price query
        try:
            # 1. Validate input
            if not ticker or len(ticker) != 6 or not ticker.isdigit():
                raise ValueError(f"Invalid ticker: {ticker} (expected 6-digit code)")

            # 2. Ensure we have access token
            access_token = self.get_access_token()

            # 3. Prepare API request
            url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"

            headers = {
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {access_token}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": "FHKST01010100"  # 국내주식 현재가 시세
            }

            params = {
                "FID_COND_MRKT_DIV_CODE": "J",  # J: 주식/ETF/ETN
                "FID_INPUT_ISCD": ticker
            }

            # 4. Send GET request
            logger.debug(f"📊 Querying price for {ticker}...")
            response = requests.get(url, headers=headers, params=params, timeout=10)

            # 5. Handle errors
            if response.status_code != 200:
                error_msg = f"Price query failed: {response.status_code} - {response.text}"
                logger.error(f"❌ {error_msg}")
                raise requests.HTTPError(error_msg)

            # 6. Parse response
            data = response.json()

            if "output" not in data or "stck_prpr" not in data["output"]:
                error_msg = f"Invalid price response (missing stck_prpr): {data}"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)

            # 7. Extract price data
            current_price = float(data["output"]["stck_prpr"])  # 주식 현재가
            change = data["output"].get("prdy_vrss", "N/A")  # 전일 대비
            change_rate = data["output"].get("prdy_ctrt", "N/A")  # 전일 대비율
            volume = data["output"].get("acml_vol", "N/A")  # 누적 거래량

            logger.debug(f"📈 [{ticker}] Price: {current_price:,.0f} KRW (Change: {change} KRW, {change_rate}%, Vol: {volume})")

            return current_price

        except requests.exceptions.Timeout:
            logger.error(f"❌ Price query timed out for {ticker}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Price query failed for {ticker}: {e}")
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"❌ Failed to parse price response for {ticker}: {e}")
            raise

    def execute_buy_order(self, ticker: str, quantity: int, price: int, order_type: str = '00') -> Dict:
        """
        매수 주문 실행

        Args:
            ticker: 종목코드 (6자리)
            quantity: 주문 수량
            price: 주문 가격 (tick size adjusted)
            order_type: 주문 구분 (00:지정가, 01:시장가)

        Returns:
            {
                'success': bool,
                'order_id': str,
                'avg_price': float,
                'quantity': int,
                'message': str
            }
        """
        self.rate_limiter.wait_if_needed()

        if self.is_mock:
            # Mock order execution
            order_id = f"MOCK_BUY_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            logger.info(f"✅ Mock buy order: {ticker} x {quantity} @ {price} KRW")
            return {
                'success': True,
                'order_id': order_id,
                'avg_price': float(price),
                'quantity': quantity,
                'message': 'Mock order executed successfully'
            }

        # Real KIS API buy order execution
        try:
            # 1. Validate inputs
            if not ticker or len(ticker) != 6 or not ticker.isdigit():
                raise ValueError(f"Invalid ticker: {ticker} (expected 6-digit code)")
            if quantity <= 0:
                raise ValueError(f"Invalid quantity: {quantity} (must be > 0)")
            if price <= 0:
                raise ValueError(f"Invalid price: {price} (must be > 0)")
            if order_type not in ['00', '01']:
                raise ValueError(f"Invalid order_type: {order_type} (expected '00' or '01')")

            # 2. Parse account number (format: "12345678-01")
            if '-' in self.account_no:
                cano, acnt_prdt_cd = self.account_no.split('-')
            else:
                # Assume last 2 digits are product code
                cano = self.account_no[:-2]
                acnt_prdt_cd = self.account_no[-2:]

            # 3. Ensure we have access token
            access_token = self.get_access_token()

            # 4. Prepare API request
            url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"

            headers = {
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {access_token}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": "TTTC0802U"  # 모의투자 매수 (실전: VTTC0802U)
            }

            body = {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "PDNO": ticker,
                "ORD_DVSN": order_type,
                "ORD_QTY": str(quantity),
                "ORD_UNPR": str(price) if order_type == '00' else "0"  # 시장가는 0
            }

            # 5. Send POST request
            logger.info(f"🛒 Placing BUY order: {ticker} x {quantity} @ {price:,} KRW")

            response = requests.post(url, headers=headers, json=body, timeout=10)

            # 6. Handle errors
            if response.status_code != 200:
                error_msg = f"Buy order failed: {response.status_code} - {response.text}"
                logger.error(f"❌ {error_msg}")
                raise requests.HTTPError(error_msg)

            # 7. Parse response
            data = response.json()

            # Check return code
            if data.get("rt_cd") != "0":
                error_msg = f"Order rejected: {data.get('msg1', 'Unknown error')}"
                logger.error(f"❌ {error_msg}")
                return {
                    'success': False,
                    'order_id': None,
                    'avg_price': 0.0,
                    'quantity': 0,
                    'message': error_msg
                }

            # 8. Extract order info
            output = data.get("output", {})
            order_id = output.get("ODNO", "UNKNOWN")
            order_time = output.get("ORD_TMD", "UNKNOWN")

            logger.info(f"✅ BUY order placed successfully")
            logger.info(f"   Order ID: {order_id}")
            logger.info(f"   Order Time: {order_time}")
            logger.info(f"   Message: {data.get('msg1', 'N/A')}")

            return {
                'success': True,
                'order_id': order_id,
                'avg_price': float(price),  # Assuming full fill at order price
                'quantity': quantity,
                'message': data.get('msg1', 'Order executed successfully')
            }

        except requests.exceptions.Timeout:
            logger.error(f"❌ Buy order timed out for {ticker}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Buy order failed for {ticker}: {e}")
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"❌ Failed to parse buy order response: {e}")
            raise

    def execute_sell_order(self, ticker: str, quantity: int, price: int, order_type: str = '00') -> Dict:
        """
        매도 주문 실행

        Args:
            ticker: 종목코드 (6자리)
            quantity: 주문 수량
            price: 주문 가격 (tick size adjusted)
            order_type: 주문 구분 (00:지정가, 01:시장가)

        Returns:
            {
                'success': bool,
                'order_id': str,
                'avg_price': float,
                'quantity': int,
                'message': str
            }
        """
        self.rate_limiter.wait_if_needed()

        if self.is_mock:
            # Mock order execution
            order_id = f"MOCK_SELL_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            logger.info(f"✅ Mock sell order: {ticker} x {quantity} @ {price} KRW")
            return {
                'success': True,
                'order_id': order_id,
                'avg_price': float(price),
                'quantity': quantity,
                'message': 'Mock order executed successfully'
            }

        # Real KIS API sell order execution
        try:
            # 1. Validate inputs
            if not ticker or len(ticker) != 6 or not ticker.isdigit():
                raise ValueError(f"Invalid ticker: {ticker} (expected 6-digit code)")
            if quantity <= 0:
                raise ValueError(f"Invalid quantity: {quantity} (must be > 0)")
            if price <= 0:
                raise ValueError(f"Invalid price: {price} (must be > 0)")
            if order_type not in ['00', '01']:
                raise ValueError(f"Invalid order_type: {order_type} (expected '00' or '01')")

            # 2. Parse account number (format: "12345678-01")
            if '-' in self.account_no:
                cano, acnt_prdt_cd = self.account_no.split('-')
            else:
                # Assume last 2 digits are product code
                cano = self.account_no[:-2]
                acnt_prdt_cd = self.account_no[-2:]

            # 3. Ensure we have access token
            access_token = self.get_access_token()

            # 4. Prepare API request
            url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"

            headers = {
                "content-type": "application/json; charset=utf-8",
                "authorization": f"Bearer {access_token}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": "TTTC0801U"  # 모의투자 매도 (실전: VTTC0801U)
            }

            body = {
                "CANO": cano,
                "ACNT_PRDT_CD": acnt_prdt_cd,
                "PDNO": ticker,
                "ORD_DVSN": order_type,
                "ORD_QTY": str(quantity),
                "ORD_UNPR": str(price) if order_type == '00' else "0"  # 시장가는 0
            }

            # 5. Send POST request
            logger.info(f"💰 Placing SELL order: {ticker} x {quantity} @ {price:,} KRW")

            response = requests.post(url, headers=headers, json=body, timeout=10)

            # 6. Handle errors
            if response.status_code != 200:
                error_msg = f"Sell order failed: {response.status_code} - {response.text}"
                logger.error(f"❌ {error_msg}")
                raise requests.HTTPError(error_msg)

            # 7. Parse response
            data = response.json()

            # Check return code
            if data.get("rt_cd") != "0":
                error_msg = f"Order rejected: {data.get('msg1', 'Unknown error')}"
                logger.error(f"❌ {error_msg}")
                return {
                    'success': False,
                    'order_id': None,
                    'avg_price': 0.0,
                    'quantity': 0,
                    'message': error_msg
                }

            # 8. Extract order info
            output = data.get("output", {})
            order_id = output.get("ODNO", "UNKNOWN")
            order_time = output.get("ORD_TMD", "UNKNOWN")

            logger.info(f"✅ SELL order placed successfully")
            logger.info(f"   Order ID: {order_id}")
            logger.info(f"   Order Time: {order_time}")
            logger.info(f"   Message: {data.get('msg1', 'N/A')}")

            return {
                'success': True,
                'order_id': order_id,
                'avg_price': float(price),  # Assuming full fill at order price
                'quantity': quantity,
                'message': data.get('msg1', 'Order executed successfully')
            }

        except requests.exceptions.Timeout:
            logger.error(f"❌ Sell order timed out for {ticker}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Sell order failed for {ticker}: {e}")
            raise
        except (KeyError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"❌ Failed to parse sell order response: {e}")
            raise


# ========================================================================
# Main Trading Engine
# ========================================================================

class KISTradingEngine:
    """
    KIS Trading Engine - Simplified MVP

    Features:
    - Buy order execution with tick size compliance
    - Sell order execution with P&L calculation
    - Position tracking
    - Stop loss / take profit automation
    """

    def __init__(self, db_path: str, config: TradingConfig = None, dry_run: bool = True,
                 portfolio_manager: Optional[PortfolioManager] = None):
        """
        Initialize KIS Trading Engine

        Args:
            db_path: SQLite database path
            config: Trading configuration
            dry_run: If True, use mock API (no real trades)
            portfolio_manager: PortfolioManager instance (Phase 5)
        """
        self.db_path = db_path
        self.config = config or TradingConfig()
        self.dry_run = dry_run

        # Phase 5 Task 4: Portfolio Manager Integration
        self.portfolio_manager = portfolio_manager or PortfolioManager(
            db_path=db_path,
            initial_cash=10000000.0  # 10M KRW default
        )

        # Phase 6: Blacklist Manager Integration
        from modules.db_manager_sqlite import SQLiteDatabaseManager
        db_manager = SQLiteDatabaseManager(db_path=db_path)
        self.blacklist_manager = BlacklistManager(db_manager=db_manager)

        # Initialize KIS API client
        app_key = os.getenv('KIS_APP_KEY', 'MOCK_KEY')
        app_secret = os.getenv('KIS_APP_SECRET', 'MOCK_SECRET')
        account_no = os.getenv('KIS_ACCOUNT_NO', 'MOCK_ACCOUNT')

        self.kis_client = KISAPIClient(
            app_key=app_key,
            app_secret=app_secret,
            account_no=account_no,
            is_mock=dry_run
        )

        logger.info(f"🚀 KIS Trading Engine initialized (dry_run={dry_run})")
        logger.info(f"💼 Portfolio Manager: Total Value = {self.portfolio_manager.get_total_portfolio_value():,.0f} KRW")
        logger.info(f"🚫 Blacklist Manager: Loaded successfully")

    # ====================================================================
    # Lot Size Helper Methods
    # ====================================================================

    def _get_lot_size_from_db(self, ticker: str, region: str = 'KR') -> int:
        """
        Get lot_size for a ticker from database

        Args:
            ticker: Stock ticker code
            region: Region code (KR, US, CN, HK, JP, VN)

        Returns:
            lot_size (int), defaults to 1 if not found
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT lot_size
                FROM tickers
                WHERE ticker = ? AND region = ?
            """, (ticker, region))

            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                return int(result[0])
            else:
                logger.warning(f"⚠️  [{ticker}] lot_size not found in DB, defaulting to 1")
                return 1

        except Exception as e:
            logger.error(f"❌ Failed to get lot_size for {ticker}: {e}")
            return 1  # Safe fallback

    def _round_quantity_to_lot_size(self, quantity: int, lot_size: int) -> int:
        """
        Round quantity down to nearest valid lot_size multiple

        Args:
            quantity: Raw quantity calculated from budget
            lot_size: Minimum trading unit (1, 100, etc.)

        Returns:
            Rounded quantity (int)

        Examples:
            >>> _round_quantity_to_lot_size(157, 100)
            100
            >>> _round_quantity_to_lot_size(57, 100)
            0
            >>> _round_quantity_to_lot_size(5, 1)
            5
        """
        if lot_size <= 0:
            logger.error(f"❌ Invalid lot_size: {lot_size}, defaulting to 1")
            lot_size = 1

        # Round down to nearest multiple
        rounded = (quantity // lot_size) * lot_size

        if rounded != quantity:
            logger.info(f"📊 Quantity adjusted: {quantity} → {rounded} (lot_size={lot_size})")

        return int(rounded)

    # ====================================================================
    # Core Trading Methods
    # ====================================================================

    def execute_buy_order(self, ticker: str, amount_krw: float, sector: str = 'Unknown',
                          region: str = 'KR') -> TradeResult:
        """
        매수 주문 실행 (Phase 5: Position Limits Check)

        Args:
            ticker: 종목코드 (6자리)
            amount_krw: 매수 금액 (KRW)
            sector: 섹터 정보 (GICS classification)
            region: 지역 코드 (KR, US, etc.)

        Returns:
            TradeResult
        """
        try:
            # 1. Validate inputs
            if amount_krw < self.config.min_order_amount_krw:
                return TradeResult(
                    success=False,
                    order_type=OrderType.BUY,
                    ticker=ticker,
                    quantity=0,
                    price=0,
                    amount=0,
                    fee=0,
                    message=f"Amount too small (min: {self.config.min_order_amount_krw} KRW)"
                )

            # Phase 6: Blacklist Check (CRITICAL SAFETY CHECK)
            if self.blacklist_manager.is_blacklisted(ticker, region):
                logger.warning(f"🚫 ORDER REJECTED: {ticker} ({region}) is blacklisted")
                return TradeResult(
                    success=False,
                    order_type=OrderType.BUY,
                    ticker=ticker,
                    quantity=0,
                    price=0,
                    amount=amount_krw,
                    fee=0,
                    message=f"Order rejected: Ticker {ticker} is blacklisted in region {region}"
                )

            # Phase 5: Position Limit Checks (4-layer validation)
            can_buy, limit_reason = self.portfolio_manager.check_position_limits(
                ticker=ticker,
                amount_krw=amount_krw,
                sector=sector,
                region=region
            )

            if not can_buy:
                logger.warning(f"❌ Position Limit Violation: {ticker} - {limit_reason}")
                return TradeResult(
                    success=False,
                    order_type=OrderType.BUY,
                    ticker=ticker,
                    quantity=0,
                    price=0,
                    amount=amount_krw,
                    fee=0,
                    message=f"Position limit violated: {limit_reason}"
                )

            # 2. Get current price
            current_price = self.kis_client.get_current_price(ticker)

            # 3. Adjust price to tick size
            adjusted_price = adjust_price_to_tick_size(current_price)

            # 4. Calculate fee-adjusted quantity
            fee_calc = calculate_fee_adjusted_amount(amount_krw, is_buy=True)
            adjusted_amount = fee_calc['adjusted_amount']
            fee = fee_calc['fee']

            # 5. Calculate raw quantity
            raw_quantity = int(adjusted_amount / adjusted_price)

            if raw_quantity == 0:
                return TradeResult(
                    success=False,
                    order_type=OrderType.BUY,
                    ticker=ticker,
                    quantity=0,
                    price=adjusted_price,
                    amount=amount_krw,
                    fee=fee,
                    message=f"Calculated quantity is 0 (price too high: {adjusted_price} KRW)"
                )

            # 5a. Get lot_size from database
            lot_size = self._get_lot_size_from_db(ticker, region)

            # 5b. Round quantity to lot_size multiple
            quantity = self._round_quantity_to_lot_size(raw_quantity, lot_size)

            # 5c. Validate rounded quantity
            if quantity == 0:
                return TradeResult(
                    success=False,
                    order_type=OrderType.BUY,
                    ticker=ticker,
                    quantity=0,
                    price=adjusted_price,
                    amount=amount_krw,
                    fee=fee,
                    message=f"Rounded quantity is 0 (raw: {raw_quantity}, lot_size: {lot_size}). Increase order amount."
                )

            # 5d. Verify rounded quantity still within budget
            actual_cost = quantity * adjusted_price
            if actual_cost > adjusted_amount:
                logger.warning(f"⚠️  Rounded quantity exceeds budget (cost: {actual_cost:,.0f} > budget: {adjusted_amount:,.0f})")
                # This should not happen with round-down logic, but added as safety check

            # 6. Execute KIS API buy order
            order_result = self.kis_client.execute_buy_order(
                ticker=ticker,
                quantity=quantity,
                price=adjusted_price,
                order_type=self.config.order_type
            )

            if not order_result['success']:
                return TradeResult(
                    success=False,
                    order_type=OrderType.BUY,
                    ticker=ticker,
                    quantity=quantity,
                    price=adjusted_price,
                    amount=amount_krw,
                    fee=fee,
                    message=order_result.get('message', 'Order execution failed')
                )

            # 7. Save trade record (Phase 5: with sector, region, reason)
            actual_price = order_result['avg_price']
            actual_quantity = order_result['quantity']
            actual_amount = actual_price * actual_quantity

            self._save_trade_record(
                ticker=ticker,
                entry_price=actual_price,
                quantity=actual_quantity,
                order_type=OrderType.BUY,
                order_id=order_result['order_id'],
                sector=sector,  # Phase 5
                region=region,  # Phase 5
                reason=f"Stage 2 Breakout - Entry at {actual_price:,.0f} KRW"  # Phase 5
            )

            logger.info(f"✅ BUY order executed: {ticker} x {actual_quantity} @ {actual_price:.0f} KRW")

            return TradeResult(
                success=True,
                order_type=OrderType.BUY,
                ticker=ticker,
                quantity=actual_quantity,
                price=actual_price,
                amount=actual_amount,
                fee=fee,
                order_id=order_result['order_id'],
                message="Buy order executed successfully"
            )

        except Exception as e:
            logger.error(f"❌ Buy order failed for {ticker}: {e}")
            return TradeResult(
                success=False,
                order_type=OrderType.BUY,
                ticker=ticker,
                quantity=0,
                price=0,
                amount=amount_krw,
                fee=0,
                message=f"Error: {str(e)}"
            )

    def execute_sell_order(self, ticker: str, quantity: Optional[float] = None, reason: str = 'manual', region: str = 'KR') -> TradeResult:
        """
        매도 주문 실행

        Args:
            ticker: 종목코드 (6자리)
            quantity: 매도 수량 (None이면 전량 매도)
            reason: 매도 사유 (stop_loss, take_profit, manual)
            region: 지역 코드 (KR, US, etc.)

        Returns:
            TradeResult
        """
        try:
            # 1. Get current position
            position = self._get_position_from_db(ticker, region)

            if not position:
                return TradeResult(
                    success=False,
                    order_type=OrderType.SELL,
                    ticker=ticker,
                    quantity=0,
                    price=0,
                    amount=0,
                    fee=0,
                    message=f"No open position found for {ticker}"
                )

            # 2. Determine quantity to sell
            sell_quantity = quantity if quantity is not None else position['quantity']
            sell_quantity = int(sell_quantity)

            if sell_quantity > position['quantity']:
                sell_quantity = int(position['quantity'])

            # 2a. Get lot_size and validate sell quantity
            lot_size = self._get_lot_size_from_db(ticker, region)

            # 2b. Validate that sell quantity is a valid lot_size multiple
            if sell_quantity % lot_size != 0:
                logger.warning(f"⚠️  Sell quantity {sell_quantity} is not a multiple of lot_size {lot_size}")
                # Round down to nearest valid multiple
                rounded_quantity = self._round_quantity_to_lot_size(sell_quantity, lot_size)

                if rounded_quantity == 0:
                    return TradeResult(
                        success=False,
                        order_type=OrderType.SELL,
                        ticker=ticker,
                        quantity=sell_quantity,
                        price=0,
                        amount=0,
                        fee=0,
                        message=f"Sell quantity {sell_quantity} rounded to 0 (lot_size: {lot_size}). Invalid sell quantity."
                    )

                sell_quantity = rounded_quantity
                logger.info(f"📊 Sell quantity adjusted to lot_size multiple: {sell_quantity}")

            # 3. Get current price
            current_price = self.kis_client.get_current_price(ticker)

            # 4. Adjust price to tick size
            adjusted_price = adjust_price_to_tick_size(current_price)

            # 5. Execute KIS API sell order
            order_result = self.kis_client.execute_sell_order(
                ticker=ticker,
                quantity=sell_quantity,
                price=adjusted_price,
                order_type=self.config.order_type
            )

            if not order_result['success']:
                return TradeResult(
                    success=False,
                    order_type=OrderType.SELL,
                    ticker=ticker,
                    quantity=sell_quantity,
                    price=adjusted_price,
                    amount=0,
                    fee=0,
                    message=order_result.get('message', 'Order execution failed')
                )

            # 6. Calculate P&L
            actual_price = order_result['avg_price']
            actual_quantity = order_result['quantity']
            actual_amount = actual_price * actual_quantity

            fee_calc = calculate_fee_adjusted_amount(actual_amount, is_buy=False)
            fee = fee_calc['fee']

            entry_price = position['entry_price']
            pnl = (actual_price - entry_price) * actual_quantity - fee
            pnl_percent = ((actual_price - entry_price) / entry_price) * 100

            # 7. Update trade record
            self._update_trade_record(
                ticker=ticker,
                exit_price=actual_price,
                exit_quantity=actual_quantity,
                pnl=pnl,
                pnl_percent=pnl_percent,
                exit_reason=reason,
                region=region
            )

            logger.info(f"✅ SELL order executed: {ticker} x {actual_quantity} @ {actual_price:.0f} KRW (P&L: {pnl:+.0f} KRW, {pnl_percent:+.2f}%)")

            return TradeResult(
                success=True,
                order_type=OrderType.SELL,
                ticker=ticker,
                quantity=actual_quantity,
                price=actual_price,
                amount=actual_amount,
                fee=fee,
                order_id=order_result['order_id'],
                message=f"Sell order executed (reason: {reason}, P&L: {pnl:+.0f} KRW)"
            )

        except Exception as e:
            logger.error(f"❌ Sell order failed for {ticker}: {e}")
            return TradeResult(
                success=False,
                order_type=OrderType.SELL,
                ticker=ticker,
                quantity=quantity or 0,
                price=0,
                amount=0,
                fee=0,
                message=f"Error: {str(e)}"
            )

    # ====================================================================
    # Position Management
    # ====================================================================

    def get_current_positions(self) -> List[PositionInfo]:
        """
        현재 보유 포지션 조회

        Returns:
            List[PositionInfo]
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    ticker,
                    region,
                    SUM(quantity) as total_quantity,
                    AVG(entry_price) as avg_entry_price,
                    MIN(entry_timestamp) as first_buy_timestamp
                FROM trades
                WHERE trade_status = 'OPEN'
                GROUP BY ticker, region
                HAVING total_quantity > 0
            """)

            rows = cursor.fetchall()
            conn.close()

            positions = []

            for row in rows:
                ticker = row[0]
                region = row[1]
                quantity = row[2]
                avg_buy_price = row[3]
                buy_timestamp = datetime.strptime(row[4], '%Y-%m-%d %H:%M:%S')

                # Get current price
                try:
                    current_price = self.kis_client.get_current_price(ticker)
                except Exception as e:
                    logger.warning(f"Failed to get current price for {ticker}: {e}")
                    current_price = avg_buy_price

                # Calculate metrics
                market_value = current_price * quantity
                cost_basis = avg_buy_price * quantity
                unrealized_pnl = market_value - cost_basis
                unrealized_pnl_percent = ((current_price - avg_buy_price) / avg_buy_price) * 100
                hold_days = (datetime.now() - buy_timestamp).days

                position = PositionInfo(
                    ticker=ticker,
                    quantity=quantity,
                    avg_buy_price=avg_buy_price,
                    current_price=current_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_percent=unrealized_pnl_percent,
                    buy_timestamp=buy_timestamp,
                    hold_days=hold_days,
                    region=region
                )

                positions.append(position)

            return positions

        except Exception as e:
            logger.error(f"Failed to get current positions: {e}")
            return []

    def check_sell_conditions(self, position: PositionInfo) -> Tuple[bool, str]:
        """
        매도 조건 체크

        Args:
            position: PositionInfo

        Returns:
            (should_sell: bool, reason: str)
        """
        # 1. Stop Loss Check (-8%)
        if position.should_stop_loss:
            return (True, 'stop_loss')

        # 2. Take Profit Check (+20%)
        if position.should_take_profit:
            return (True, 'take_profit')

        # 3. Time-based Exit (Optional: 90 days)
        if position.hold_days >= 90:
            if position.unrealized_pnl_percent > 0:
                return (True, 'time_based_profit')

        return (False, 'hold')

    def process_portfolio_management(self) -> Dict[str, Any]:
        """
        포트폴리오 관리 프로세스 실행

        Returns:
            {
                'positions_checked': int,
                'sell_executed': int,
                'sell_results': List[TradeResult]
            }
        """
        logger.info("=" * 70)
        logger.info("[Portfolio Management]")
        logger.info("=" * 70)

        positions = self.get_current_positions()
        sell_results = []

        logger.info(f"📊 Current positions: {len(positions)}")

        for position in positions:
            logger.info(f"\n{position.ticker}:")
            logger.info(f"  Quantity: {position.quantity:.0f}")
            logger.info(f"  Avg Buy: {position.avg_buy_price:.0f} KRW")
            logger.info(f"  Current: {position.current_price:.0f} KRW")
            logger.info(f"  P&L: {position.unrealized_pnl:+.0f} KRW ({position.unrealized_pnl_percent:+.2f}%)")
            logger.info(f"  Hold: {position.hold_days} days")

            should_sell, reason = self.check_sell_conditions(position)

            if should_sell:
                logger.info(f"  🚨 Sell signal: {reason}")
                result = self.execute_sell_order(
                    ticker=position.ticker,
                    quantity=position.quantity,
                    reason=reason
                )
                sell_results.append(result)
            else:
                logger.info(f"  ✅ Hold")

        logger.info("\n" + "=" * 70)
        logger.info(f"✅ Portfolio management complete")
        logger.info(f"   Positions checked: {len(positions)}")
        logger.info(f"   Sell executed: {len(sell_results)}")
        logger.info("=" * 70)

        return {
            'positions_checked': len(positions),
            'sell_executed': len(sell_results),
            'sell_results': sell_results
        }

    # ====================================================================
    # Database Operations
    # ====================================================================

    def _save_trade_record(self, ticker: str, entry_price: float, quantity: float,
                           order_type: OrderType, order_id: str = None, sector: str = 'Unknown',
                           region: str = 'KR', reason: str = None):
        """
        거래 기록 저장 (Phase 5: Enhanced with sector, region, reason)

        Args:
            ticker: 종목코드
            entry_price: 진입가
            quantity: 수량
            order_type: 주문 타입
            order_id: 주문 ID
            sector: 섹터 정보 (Phase 5)
            region: 지역 코드 (Phase 5)
            reason: 거래 사유 (Phase 5)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Phase 5: Calculate position size percentage
            portfolio_value = self.portfolio_manager.get_total_portfolio_value()
            position_value = entry_price * quantity
            position_size_percent = (position_value / portfolio_value) * 100 if portfolio_value > 0 else 0

            cursor.execute("""
                INSERT INTO trades (
                    ticker, region, side, order_type, quantity,
                    entry_price, price, amount,
                    entry_timestamp, trade_status,
                    sector, position_size_percent, reason,
                    order_no, order_time, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ticker,
                region,
                order_type.value,  # BUY
                'LIMIT',  # order_type string
                quantity,
                entry_price,
                entry_price,  # price (하위 호환성)
                entry_price * quantity,  # amount
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                TradeStatus.OPEN.value,
                sector,
                position_size_percent,
                reason or f"{order_type.value} order",
                order_id,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),  # order_time
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')  # created_at
            ))

            conn.commit()
            conn.close()

            logger.info(f"✅ Trade record saved: {ticker} ({sector}) - {position_size_percent:.2f}% of portfolio")

            # Phase 5: Sync portfolio table after trade
            self.portfolio_manager.sync_portfolio_table()

        except Exception as e:
            logger.error(f"Failed to save trade record for {ticker}: {e}")

    def _update_trade_record(self, ticker: str, exit_price: float, exit_quantity: float,
                              pnl: float, pnl_percent: float, exit_reason: str, region: str = 'KR'):
        """
        거래 기록 업데이트 (매도 시) - Phase 5: Enhanced with portfolio sync

        Args:
            ticker: 종목코드
            exit_price: 청산가
            exit_quantity: 청산 수량
            pnl: 실현 손익 (KRW)
            pnl_percent: 실현 손익 (%)
            exit_reason: 매도 사유
            region: 지역 코드 (Phase 5)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE trades
                SET exit_price = ?,
                    exit_timestamp = ?,
                    trade_status = ?,
                    reason = ?
                WHERE ticker = ?
                  AND region = ?
                  AND trade_status = 'OPEN'
            """, (
                exit_price,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                TradeStatus.CLOSED.value,
                exit_reason,
                ticker,
                region
            ))

            conn.commit()
            conn.close()

            logger.info(f"✅ Trade record closed: {ticker} - P&L: {pnl:,.0f} KRW ({pnl_percent:+.2f}%)")

            # Phase 5: Sync portfolio table after closing position
            self.portfolio_manager.sync_portfolio_table()

        except Exception as e:
            logger.error(f"Failed to update trade record for {ticker}: {e}")

    def _get_position_from_db(self, ticker: str, region: str = 'KR') -> Optional[Dict]:
        """
        DB에서 포지션 정보 조회

        Args:
            ticker: 종목코드
            region: 지역 코드 (KR, US, etc.)

        Returns:
            {
                'ticker': str,
                'region': str,
                'quantity': float,
                'entry_price': float,
                'entry_timestamp': str
            } or None
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    ticker,
                    region,
                    SUM(quantity) as total_quantity,
                    AVG(entry_price) as avg_entry_price,
                    MIN(entry_timestamp) as first_buy_timestamp
                FROM trades
                WHERE ticker = ? AND region = ?
                AND trade_status = 'OPEN'
                GROUP BY ticker, region
            """, (ticker, region))

            row = cursor.fetchone()
            conn.close()

            if row and row[2] > 0:
                return {
                    'ticker': row[0],
                    'region': row[1],
                    'quantity': row[2],
                    'entry_price': row[3],
                    'entry_timestamp': row[4]
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get position from DB for {ticker}: {e}")
            return None


# ========================================================================
# Main (for testing)
# ========================================================================

if __name__ == '__main__':
    # Example usage
    engine = KISTradingEngine(
        db_path="data/spock_local.db",
        dry_run=True  # Mock mode
    )

    # Test buy order
    result = engine.execute_buy_order('005930', 100000)  # Samsung Electronics, 100K KRW
    print(f"\nBuy result: {result}")

    # Test get positions
    positions = engine.get_current_positions()
    print(f"\nCurrent positions: {len(positions)}")

    # Test portfolio management
    summary = engine.process_portfolio_management()
    print(f"\nPortfolio management: {summary}")
