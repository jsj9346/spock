# KIS Master File URL Configuration

**Author**: Spock Trading System
**Date**: 2025-10-15
**Status**: Production Ready ✅
**Source**: https://github.com/koreainvestment/open-trading-api/blob/main/stocks_info/overseas_stock_code.py

---

## 1. Download URL Pattern

```
https://new.real.download.dws.co.kr/common/master/{market_code}mst.cod.zip
```

**Example**:
```python
# Download NASDAQ master file
url = "https://new.real.download.dws.co.kr/common/master/nasmst.cod.zip"

# Download NYSE master file
url = "https://new.real.download.dws.co.kr/common/master/nysmst.cod.zip"
```

---

## 2. Market Code Mapping

### 2.1 All Available Markets

| Market Code | Exchange | Country/Region | Asset Type | Est. Tickers |
|-------------|----------|----------------|------------|--------------|
| **US Markets** |
| `nas` | NASDAQ | United States | Stock | ~2,000 |
| `nys` | NYSE | United States | Stock | ~800 |
| `ams` | AMEX | United States | Stock | ~200 |
| **China Markets** |
| `shs` | Shanghai SE | China | Stock | ~300-500 |
| `shi` | Shanghai SE | China | Index | N/A |
| `szs` | Shenzhen SE | China | Stock | ~300-500 |
| `szi` | Shenzhen SE | China | Index | N/A |
| **Other Markets** |
| `tse` | Tokyo SE | Japan | Stock | ~500-1,000 |
| `hks` | Hong Kong SE | Hong Kong | Stock | ~500-1,000 |
| `hnx` | Hanoi SE | Vietnam | Stock | ~50-150 |
| `hsx` | Ho Chi Minh SE | Vietnam | Stock | ~50-150 |

### 2.2 Stock-Only Markets (Exclude Indices)

For ticker collection, use **stock markets only** (exclude index codes):

```python
STOCK_MARKETS = {
    'US': ['nas', 'nys', 'ams'],
    'CN': ['shs', 'szs'],  # Exclude 'shi', 'szi' (indices)
    'HK': ['hks'],
    'JP': ['tse'],
    'VN': ['hnx', 'hsx'],
}
```

### 2.3 Region to Market Code Mapping

```python
REGION_TO_MARKETS = {
    'US': ['nas', 'nys', 'ams'],
    'CN': ['shs', 'szs'],
    'HK': ['hks'],
    'JP': ['tse'],
    'VN': ['hnx', 'hsx'],
}
```

### 2.4 Market Code to Exchange Name

```python
MARKET_CODE_TO_EXCHANGE = {
    # US
    'nas': 'NASDAQ',
    'nys': 'NYSE',
    'ams': 'AMEX',

    # China
    'shs': 'SSE',  # Shanghai Stock Exchange
    'szs': 'SZSE', # Shenzhen Stock Exchange

    # Hong Kong
    'hks': 'HKEX',

    # Japan
    'tse': 'TSE',

    # Vietnam
    'hnx': 'HNX',
    'hsx': 'HOSE',  # Ho Chi Minh Stock Exchange
}
```

---

## 3. File Format Specification

### 3.1 File Structure

```
{market_code}mst.cod.zip          # Compressed file
  └─ {market_code}mst.cod         # Tab-separated text file
```

### 3.2 Encoding

- **Character Encoding**: `cp949` (Korean EUC-KR)
- **Separator**: `\t` (tab)
- **Line Ending**: `\n` or `\r\n`

### 3.3 Data Columns (24 columns)

```python
COLUMNS = [
    'National code',              # 0: 국가 코드
    'Exchange id',                # 1: 거래소 ID
    'Exchange code',              # 2: 거래소 코드
    'Exchange name',              # 3: 거래소 이름
    'Symbol',                     # 4: 티커 심볼 ⭐
    'realtime symbol',            # 5: 실시간 심볼
    'Korea name',                 # 6: 한글 종목명 ⭐
    'English name',               # 7: 영문 종목명 ⭐
    'Security type',              # 8: 1=Index, 2=Stock, 3=ETP/ETF, 4=Warrant ⭐
    'currency',                   # 9: 통화 (USD, HKD, CNY, JPY, VND)
    'float position',             # 10: 소수점 위치
    'data type',                  # 11: 데이터 타입
    'base price',                 # 12: 기준가
    'Bid order size',             # 13: 매수 호가 단위
    'Ask order size',             # 14: 매도 호가 단위
    'market start time',          # 15: 장 시작 시간 (HHMM)
    'market end time',            # 16: 장 종료 시간 (HHMM)
    'DR 여부(Y/N)',               # 17: DR 여부
    'DR 국가코드',                # 18: DR 국가 코드
    '업종분류코드',               # 19: 업종 분류 코드 ⭐
    '지수구성종목 존재 여부',     # 20: 지수 구성 종목 여부
    'Tick size Type',             # 21: 호가 단위 타입
    '구분코드',                   # 22: ETF/ETN/ETC 구분 (001=ETF, 002=ETN, etc.)
    'Tick size type 상세'         # 23: 호가 단위 상세
]
```

**Key Columns** (marked with ⭐):
- **Column 4**: `Symbol` - Ticker symbol (e.g., AAPL, 0700)
- **Column 6**: `Korea name` - Korean name (한글 종목명)
- **Column 7**: `English name` - English name (e.g., Apple Inc.)
- **Column 8**: `Security type` - Filter stocks only (type = 2)
- **Column 19**: `업종분류코드` - Sector classification code

---

## 4. Security Type Filter

**Only include stocks** (exclude indices, ETFs, warrants):

```python
SECURITY_TYPE_MAP = {
    '1': 'INDEX',    # Skip
    '2': 'STOCK',    # ✅ Include
    '3': 'ETF',      # Skip (or separate collection)
    '4': 'WARRANT',  # Skip
}
```

**Filter logic**:
```python
# Only include rows where Security type == '2' (Stock)
df = df[df['Security type'] == '2']
```

---

## 5. Download Implementation

### 5.1 Basic Download Function

```python
import urllib.request
import ssl
import zipfile
import os

def download_master_file(market_code: str, output_dir: str = 'data/master_files') -> str:
    """
    Download KIS master file

    Args:
        market_code: Market code (e.g., 'nas', 'nys', 'hks')
        output_dir: Directory to save files

    Returns:
        Path to extracted .cod file
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Download URL
    url = f"https://new.real.download.dws.co.kr/common/master/{market_code}mst.cod.zip"

    # Disable SSL verification (as per KIS example)
    ssl._create_default_https_context = ssl._create_unverified_context

    # Download zip file
    zip_path = os.path.join(output_dir, f"{market_code}mst.cod.zip")
    urllib.request.urlretrieve(url, zip_path)

    # Extract zip file
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(output_dir)

    # Return path to .cod file
    cod_path = os.path.join(output_dir, f"{market_code}mst.cod")
    return cod_path
```

### 5.2 File Size Check (HTTP HEAD)

```python
import urllib.request

def get_remote_file_size(market_code: str) -> int:
    """
    Get remote file size without downloading

    Args:
        market_code: Market code

    Returns:
        File size in bytes
    """
    url = f"https://new.real.download.dws.co.kr/common/master/{market_code}mst.cod.zip"

    try:
        req = urllib.request.Request(url, method='HEAD')
        with urllib.request.urlopen(req) as response:
            size = int(response.headers.get('Content-Length', 0))
            return size
    except Exception as e:
        logger.error(f"Failed to get file size for {market_code}: {e}")
        return 0
```

---

## 6. Parsing Implementation

### 6.1 Basic Parser

```python
import pandas as pd

def parse_master_file(cod_file_path: str, market_code: str) -> pd.DataFrame:
    """
    Parse .cod master file

    Args:
        cod_file_path: Path to .cod file
        market_code: Market code

    Returns:
        DataFrame with parsed tickers
    """
    # Define column names
    columns = [
        'National code', 'Exchange id', 'Exchange code', 'Exchange name',
        'Symbol', 'realtime symbol', 'Korea name', 'English name',
        'Security type', 'currency', 'float position', 'data type',
        'base price', 'Bid order size', 'Ask order size',
        'market start time', 'market end time',
        'DR 여부(Y/N)', 'DR 국가코드', '업종분류코드',
        '지수구성종목 존재 여부', 'Tick size Type',
        '구분코드', 'Tick size type 상세'
    ]

    # Read tab-separated file with cp949 encoding
    df = pd.read_table(cod_file_path, sep='\t', encoding='cp949', names=columns)

    # Filter: Only stocks (Security type == '2')
    df = df[df['Security type'] == '2']

    # Select relevant columns
    df = df[[
        'Symbol',          # Ticker
        'English name',    # Name
        'Korea name',      # Korean name
        'Exchange code',   # Exchange
        'currency',        # Currency
        '업종분류코드',    # Sector code
    ]]

    return df
```

### 6.2 Ticker Normalization

```python
def normalize_ticker(symbol: str, market_code: str) -> str:
    """
    Normalize ticker symbol based on market

    Args:
        symbol: Raw ticker symbol
        market_code: Market code

    Returns:
        Normalized ticker
    """
    # US markets: Use as-is (AAPL, MSFT)
    if market_code in ['nas', 'nys', 'ams']:
        return symbol.strip().upper()

    # Hong Kong: Add .HK suffix if not present
    elif market_code == 'hks':
        symbol = symbol.strip()
        if not symbol.endswith('.HK'):
            # Pad to 4 digits: 700 → 0700.HK
            symbol = symbol.zfill(4) + '.HK'
        return symbol

    # China: Add .SS or .SZ suffix
    elif market_code == 'shs':
        symbol = symbol.strip()
        if not symbol.endswith('.SS'):
            symbol = symbol + '.SS'
        return symbol

    elif market_code == 'szs':
        symbol = symbol.strip()
        if not symbol.endswith('.SZ'):
            symbol = symbol + '.SZ'
        return symbol

    # Japan: Use 4-digit code (7203)
    elif market_code == 'tse':
        return symbol.strip()

    # Vietnam: 3-letter uppercase (VCB, FPT)
    elif market_code in ['hnx', 'hsx']:
        return symbol.strip().upper()

    return symbol.strip()
```

---

## 7. Complete Example

```python
import pandas as pd
import urllib.request
import ssl
import zipfile
import os
import logging

logger = logging.getLogger(__name__)

class KISMasterFileManager:
    """KIS Master File Manager"""

    BASE_URL = "https://new.real.download.dws.co.kr/common/master"

    MARKET_CODES = {
        'US': ['nas', 'nys', 'ams'],
        'CN': ['shs', 'szs'],
        'HK': ['hks'],
        'JP': ['tse'],
        'VN': ['hnx', 'hsx'],
    }

    def __init__(self, cache_dir: str = 'data/master_files'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)

        # Disable SSL verification
        ssl._create_default_https_context = ssl._create_unverified_context

    def download_market(self, market_code: str, force: bool = False) -> str:
        """Download master file for specific market"""

        # Check if update needed (file size comparison)
        if not force and not self._needs_update(market_code):
            logger.info(f"[{market_code}] No update needed - using cached file")
            return self._get_cod_path(market_code)

        # Download
        url = f"{self.BASE_URL}/{market_code}mst.cod.zip"
        zip_path = os.path.join(self.cache_dir, f"{market_code}mst.cod.zip")

        logger.info(f"[{market_code}] Downloading from {url}")
        urllib.request.urlretrieve(url, zip_path)

        # Extract
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(self.cache_dir)

        cod_path = self._get_cod_path(market_code)
        logger.info(f"[{market_code}] Extracted to {cod_path}")

        return cod_path

    def parse_market(self, market_code: str) -> pd.DataFrame:
        """Parse master file for specific market"""

        cod_path = self._get_cod_path(market_code)

        if not os.path.exists(cod_path):
            raise FileNotFoundError(f"Master file not found: {cod_path}")

        # Parse
        df = pd.read_table(
            cod_path,
            sep='\t',
            encoding='cp949',
            names=self._get_column_names()
        )

        # Filter stocks only
        df = df[df['Security type'] == '2'].copy()

        logger.info(f"[{market_code}] Parsed {len(df)} stocks")

        return df

    def get_all_tickers(self, region: str, force_refresh: bool = False) -> List[Dict]:
        """Get all tickers for region"""

        market_codes = self.MARKET_CODES.get(region, [])
        all_tickers = []

        for market_code in market_codes:
            # Download
            self.download_market(market_code, force=force_refresh)

            # Parse
            df = self.parse_market(market_code)

            # Convert to ticker dictionaries
            for _, row in df.iterrows():
                ticker_info = {
                    'ticker': self._normalize_ticker(row['Symbol'], market_code),
                    'name': row['English name'],
                    'name_kor': row.get('Korea name', ''),
                    'exchange': self._get_exchange_name(market_code),
                    'region': region,
                    'currency': self._get_currency(market_code),
                    'sector_code': row.get('업종분류코드', ''),
                }
                all_tickers.append(ticker_info)

        logger.info(f"[{region}] Total tickers: {len(all_tickers)}")

        return all_tickers

    def _needs_update(self, market_code: str) -> bool:
        """Check if master file needs update (size comparison)"""

        local_path = self._get_cod_path(market_code)

        if not os.path.exists(local_path):
            return True  # File doesn't exist

        # Get local file size
        local_size = os.path.getsize(local_path)

        # Get remote file size
        url = f"{self.BASE_URL}/{market_code}mst.cod.zip"
        try:
            req = urllib.request.Request(url, method='HEAD')
            with urllib.request.urlopen(req) as response:
                remote_size = int(response.headers.get('Content-Length', 0))
        except:
            logger.warning(f"[{market_code}] Failed to check remote size")
            return False

        # Compare
        if remote_size > local_size:
            logger.info(f"[{market_code}] Update needed: {local_size} → {remote_size} bytes")
            return True

        return False

    def _get_cod_path(self, market_code: str) -> str:
        """Get path to .cod file"""
        return os.path.join(self.cache_dir, f"{market_code}mst.cod")

    def _get_column_names(self) -> List[str]:
        """Get column names"""
        return [
            'National code', 'Exchange id', 'Exchange code', 'Exchange name',
            'Symbol', 'realtime symbol', 'Korea name', 'English name',
            'Security type', 'currency', 'float position', 'data type',
            'base price', 'Bid order size', 'Ask order size',
            'market start time', 'market end time',
            'DR 여부(Y/N)', 'DR 국가코드', '업종분류코드',
            '지수구성종목 존재 여부', 'Tick size Type',
            '구분코드', 'Tick size type 상세'
        ]

    def _normalize_ticker(self, symbol: str, market_code: str) -> str:
        """Normalize ticker symbol"""
        # (Implementation as shown in section 6.2)
        pass

    def _get_exchange_name(self, market_code: str) -> str:
        """Get exchange name from market code"""
        mapping = {
            'nas': 'NASDAQ', 'nys': 'NYSE', 'ams': 'AMEX',
            'hks': 'HKEX', 'shs': 'SSE', 'szs': 'SZSE',
            'tse': 'TSE', 'hnx': 'HNX', 'hsx': 'HOSE',
        }
        return mapping.get(market_code, market_code.upper())

    def _get_currency(self, market_code: str) -> str:
        """Get currency from market code"""
        if market_code in ['nas', 'nys', 'ams']:
            return 'USD'
        elif market_code == 'hks':
            return 'HKD'
        elif market_code in ['shs', 'szs']:
            return 'CNY'
        elif market_code == 'tse':
            return 'JPY'
        elif market_code in ['hnx', 'hsx']:
            return 'VND'
        return 'USD'


# Usage example
if __name__ == '__main__':
    manager = KISMasterFileManager()

    # Get all US tickers
    us_tickers = manager.get_all_tickers('US', force_refresh=True)
    print(f"US tickers: {len(us_tickers)}")

    # Get all Hong Kong tickers
    hk_tickers = manager.get_all_tickers('HK', force_refresh=True)
    print(f"HK tickers: {len(hk_tickers)}")
```

---

## 8. Integration with Existing Code

### 8.1 Update kis_overseas_stock_api.py

```python
# modules/api_clients/kis_overseas_stock_api.py

from .kis_master_file_manager import KISMasterFileManager

class KISOverseasStockAPI:
    def __init__(self, app_key: str, app_secret: str):
        # ... existing code ...

        # Add master file manager
        self.master_file_manager = KISMasterFileManager()

    def get_tradable_tickers(self, exchange_code: str, max_count: int = None) -> List[Dict]:
        """
        [UPDATED] Get tradable tickers from KIS master file

        Args:
            exchange_code: KIS exchange code (NASD, NYSE, etc.)
            max_count: Maximum tickers to return

        Returns:
            List of ticker dictionaries
        """
        # Map KIS exchange code to market code
        exchange_to_market = {
            'NASD': 'nas',
            'NYSE': 'nys',
            'AMEX': 'ams',
            'SEHK': 'hks',
            'SHAA': 'shs',
            'SZAA': 'szs',
            'TKSE': 'tse',
            'HASE': 'hnx',
            'VNSE': 'hsx',
        }

        market_code = exchange_to_market.get(exchange_code)
        if not market_code:
            raise ValueError(f"Unsupported exchange: {exchange_code}")

        # Download and parse master file
        self.master_file_manager.download_market(market_code)
        df = self.master_file_manager.parse_market(market_code)

        # Convert to ticker list
        tickers = []
        for _, row in df.iterrows():
            ticker_info = {
                'ticker': row['Symbol'],
                'name': row['English name'],
                'exchange': exchange_code,
            }
            tickers.append(ticker_info)

        # Apply limit
        if max_count:
            tickers = tickers[:max_count]

        return tickers
```

---

## 9. Testing

### 9.1 Quick Test Script

```bash
# Create test script
cat > test_master_file_download.py << 'EOF'
from kis_master_file_manager import KISMasterFileManager
import logging

logging.basicConfig(level=logging.INFO)

manager = KISMasterFileManager()

# Test NASDAQ download
print("Testing NASDAQ download...")
us_tickers = manager.get_all_tickers('US', force_refresh=True)
print(f"✅ Downloaded {len(us_tickers)} US tickers")
print(f"Sample: {us_tickers[:5]}")
EOF

# Run test
python3 test_master_file_download.py
```

---

**END OF URL CONFIGURATION**
