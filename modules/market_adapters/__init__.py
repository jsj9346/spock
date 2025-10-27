"""
Market Adapters Package

Regional market adapters for unified ticker discovery and data collection.

Each adapter handles both:
- Phase 1: Ticker Discovery (scanning)
- Phase 2: OHLCV Data Collection

Available adapters:
- BaseMarketAdapter: Abstract base class (this module)
- KoreaAdapter: Korea market (KOSPI, KOSDAQ, NXT) - Phase 1 ✅
- USAdapter: US market (NYSE, NASDAQ, AMEX) - Phase 2 ✅ (Polygon.io)
- USAdapterKIS: US market (KIS API) - Phase 6 ✅ (tradable tickers only, 240x faster)
- HKAdapter: Hong Kong market (HKEX) - Phase 3a ✅ (yfinance)
- HKAdapterKIS: Hong Kong market (KIS API) - Phase 6 ✅ (tradable tickers only, 20x faster)
- CNAdapter: China market (SSE, SZSE) with AkShare+yfinance hybrid - Phase 3b ✅
- CNAdapterKIS: China market (KIS API) - Phase 6 ✅ (선강통/후강통, 13x faster)
- JPAdapter: Japan market (TSE) - Phase 4 ✅ (yfinance)
- JPAdapterKIS: Japan market (KIS API) - Phase 6 ✅ (tradable tickers only, 20x faster)
- VNAdapter: Vietnam market (HOSE, HNX) - Phase 5 ✅ (yfinance)
- VNAdapterKIS: Vietnam market (KIS API) - Phase 6 ✅ (tradable tickers only, 20x faster)
"""

from .base_adapter import BaseMarketAdapter
from .kr_adapter import KoreaAdapter
from .us_adapter import USAdapter
from .us_adapter_kis import USAdapterKIS
from .hk_adapter import HKAdapter
from .hk_adapter_kis import HKAdapterKIS
from .cn_adapter import CNAdapter
from .cn_adapter_kis import CNAdapterKIS
from .jp_adapter import JPAdapter
from .jp_adapter_kis import JPAdapterKIS
from .vn_adapter import VNAdapter
from .vn_adapter_kis import VNAdapterKIS

__all__ = [
    'BaseMarketAdapter',
    'KoreaAdapter',
    'USAdapter', 'USAdapterKIS',
    'HKAdapter', 'HKAdapterKIS',
    'CNAdapter', 'CNAdapterKIS',
    'JPAdapter', 'JPAdapterKIS',
    'VNAdapter', 'VNAdapterKIS'
]
