"""
Parsers Package

Data transformers and normalizers for converting raw API responses
to standardized format for database insertion.

Available parsers:
- StockParser: Normalize Korean stock data (KRX, pykrx)
- ETFParser: Normalize ETF data with tracking error calculations
- USStockParser: Normalize US stock data (Polygon.io, yfinance)
- HKStockParser: Normalize Hong Kong stock data (yfinance)
- CNStockParser: Normalize Chinese stock data (AkShare, yfinance) with CSRC→GICS mapping
- JPStockParser: Normalize Japanese stock data (yfinance) with TSE→GICS mapping
- VNStockParser: Normalize Vietnamese stock data (yfinance) with ICB→GICS mapping
"""

from .stock_parser import StockParser
from .etf_parser import ETFParser
from .us_stock_parser import USStockParser
from .hk_stock_parser import HKStockParser
from .cn_stock_parser import CNStockParser
from .jp_stock_parser import JPStockParser
from .vn_stock_parser import VNStockParser

__all__ = ['StockParser', 'ETFParser', 'USStockParser', 'HKStockParser', 'CNStockParser', 'JPStockParser', 'VNStockParser']
