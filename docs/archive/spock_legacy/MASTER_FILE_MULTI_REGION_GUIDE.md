# Multi-Region Master File Integration Guide

**Purpose**: Step-by-step guide for extending master file integration to HK, CN, JP, VN markets

**Prerequisites**: US market integration complete (reference implementation)

---

## Quick Reference

### Market Codes Mapping

| Region | KIS API Exchange | Master File Code | Exchange Name |
|--------|------------------|------------------|---------------|
| **US** | NASD, NYSE, AMEX | nas, nys, ams | NASDAQ, NYSE, AMEX |
| **HK** | SEHK | hks | Hong Kong Stock Exchange |
| **CN** | SHAA, SZAA | shs, szs | Shanghai, Shenzhen |
| **JP** | TKSE | tse | Tokyo Stock Exchange |
| **VN** | HASE, VNSE | hnx, hsx | Hanoi, Ho Chi Minh |

### Master File URLs

```
Base URL: https://new.real.download.dws.co.kr/common/master/

US:
- https://new.real.download.dws.co.kr/common/master/nasmst.cod.zip
- https://new.real.download.dws.co.kr/common/master/nysmst.cod.zip
- https://new.real.download.dws.co.kr/common/master/amsmst.cod.zip

HK:
- https://new.real.download.dws.co.kr/common/master/hksmst.cod.zip

CN:
- https://new.real.download.dws.co.kr/common/master/shsmst.cod.zip
- https://new.real.download.dws.co.kr/common/master/szsmst.cod.zip

JP:
- https://new.real.download.dws.co.kr/common/master/tsemst.cod.zip

VN:
- https://new.real.download.dws.co.kr/common/master/hnxmst.cod.zip
- https://new.real.download.dws.co.kr/common/master/hsxmst.cod.zip
```

---

## Integration Workflow

### Step 1: Verify Master File Manager Support

**Already Complete** ✅

The `KISMasterFileManager` already supports all markets:

```python
MARKET_CODES = {
    'US': ['nas', 'nys', 'ams'],
    'CN': ['shs', 'szs'],
    'HK': ['hks'],
    'JP': ['tse'],
    'VN': ['hnx', 'hsx'],  # hnx = Hanoi, hsx = Ho Chi Minh
}
```

**Test Command**:
```bash
# Test HK master file
python3 -c "
from modules.api_clients.kis_master_file_manager import KISMasterFileManager
mgr = KISMasterFileManager()
hk_tickers = mgr.get_all_tickers('HK', force_refresh=True)
print(f'HK tickers: {len(hk_tickers):,}')
"
```

### Step 2: Verify API Client Integration

**Already Complete** ✅

The `KISOverseasStockAPI` exchange code mapping already supports all markets:

```python
exchange_to_market = {
    'NASD': 'nas', 'NYSE': 'nys', 'AMEX': 'ams',  # US
    'SEHK': 'hks',                                  # HK
    'SHAA': 'shs', 'SZAA': 'szs',                  # CN
    'TKSE': 'tse',                                  # JP
    'HASE': 'hnx', 'VNSE': 'hsx',                  # VN
}
```

**Test Command**:
```bash
# Test HK API integration
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI

api = KISOverseasStockAPI(os.getenv('KIS_APP_KEY'), os.getenv('KIS_APP_SECRET'))
hk_tickers = api.get_tickers_with_details('HK', force_refresh=False)
print(f'HK tickers: {len(hk_tickers):,}')
"
```

### Step 3: Update Market Adapters

**Action Required** ⚠️

Copy the US adapter pattern to other market adapters:

#### Example: Hong Kong Adapter (`hk_adapter_kis.py`)

```python
def scan_stocks(self,
                force_refresh: bool = False,
                exchanges: Optional[List[str]] = None,
                max_count: Optional[int] = None,
                use_master_file: bool = True) -> List[Dict]:
    """
    Scan HK stocks from KIS Master Files or API

    Data Source Priority:
    1. Master File: Instant, ~500-1,000 HK stocks
    2. KIS API: 20 req/sec, real-time data (fallback)
    """
    logger.info(f"📊 Scanning HK stocks ({'Master File' if use_master_file else 'KIS API'})...")

    # Check cache unless force refresh
    if not force_refresh:
        cached_stocks = self._load_tickers_from_cache(
            asset_type='STOCK',
            ttl_hours=24
        )
        if cached_stocks:
            logger.info(f"✅ Loaded {len(cached_stocks)} HK stocks from cache")
            return cached_stocks

    # Try master file first (instant, comprehensive)
    if use_master_file:
        all_stocks = self._scan_stocks_from_master_file(exchanges, max_count)
        if all_stocks:
            # Save to database
            logger.info(f"💾 Saving {len(all_stocks)} HK stocks to database...")
            self._save_tickers_to_db(all_stocks, asset_type='STOCK')

            # Log exchange breakdown
            self._log_exchange_breakdown(all_stocks)
            return all_stocks

        logger.info("⚠️ Master file unavailable, falling back to API method")

    # Fallback to API method (legacy)
    return self._scan_stocks_from_api(exchanges, max_count)

def _scan_stocks_from_master_file(self,
                                  exchanges: Optional[List[str]] = None,
                                  max_count: Optional[int] = None) -> List[Dict]:
    """
    Scan HK stocks from master files (instant, no API calls)

    Performance:
    - Instant: No API calls
    - Coverage: ~500-1,000 HK stocks
    """
    try:
        # Get detailed ticker information from master files
        hk_tickers = self.kis_api.get_tickers_with_details(
            region=self.REGION_CODE,  # 'HK'
            force_refresh=False
        )

        if not hk_tickers:
            logger.warning("⚠️ No HK tickers from master files")
            return []

        logger.info(f"✅ Master File: {len(hk_tickers)} HK tickers loaded (instant)")

        # Filter by exchanges if specified
        if exchanges:
            exchange_names = [self.EXCHANGE_NAMES.get(code, code) for code in exchanges]
            hk_tickers = [t for t in hk_tickers if t.get('exchange') in exchange_names]
            logger.info(f"   Filtered to {len(hk_tickers)} tickers for exchanges: {exchange_names}")

        # Apply max_count if specified
        if max_count:
            hk_tickers = hk_tickers[:max_count]
            logger.info(f"   Limited to {max_count} tickers")

        # Enrich with yfinance data (for sector/fundamentals)
        all_stocks = []
        for i, ticker_data in enumerate(hk_tickers, 1):
            try:
                ticker = ticker_data['ticker']

                # Parse additional info from yfinance (sector, market cap)
                ticker_info = self.stock_parser.parse_ticker_info(ticker)

                if ticker_info:
                    # Merge master file data with yfinance data
                    ticker_info.update({
                        'ticker': ticker,
                        'name': ticker_data.get('name', ticker_info.get('name', '')),
                        'name_kor': ticker_data.get('name_kor', ''),
                        'exchange': ticker_data.get('exchange', ''),
                        'region': self.REGION_CODE,
                        'asset_type': 'STOCK',
                        'is_active': True,
                        'kis_exchange_code': ticker_data.get('market_code', '').upper(),
                        'sector_code': ticker_data.get('sector_code', ''),
                    })
                    all_stocks.append(ticker_info)

                if (i % 100) == 0:
                    logger.info(f"   Processed {i}/{len(hk_tickers)} tickers...")

            except Exception as e:
                logger.debug(f"⚠️ Failed to parse {ticker_data.get('ticker')}: {e}")
                continue

        logger.info(f"✅ Master File scan complete: {len(all_stocks)} stocks enriched")
        return all_stocks

    except Exception as e:
        logger.error(f"❌ Master file scan failed: {e}")
        return []

def _scan_stocks_from_api(self,
                         exchanges: Optional[List[str]] = None,
                         max_count: Optional[int] = None) -> List[Dict]:
    """
    Scan HK stocks from KIS API (legacy method)

    Performance:
    - ~1-2 minutes for ~500-1,000 stocks (20 req/sec)
    """
    target_exchanges = exchanges if exchanges else self.EXCHANGE_CODES

    all_stocks = []
    for exchange_code in target_exchanges:
        try:
            logger.info(f"📡 Fetching tradable tickers from {exchange_code} (API)...")

            # Fetch tradable tickers from KIS API (use_master_file=False)
            tickers = self.kis_api.get_tradable_tickers(
                exchange_code=exchange_code,
                max_count=max_count,
                use_master_file=False  # Force API method
            )

            if not tickers:
                logger.warning(f"⚠️ No tickers returned for {exchange_code}")
                continue

            logger.info(f"✅ {exchange_code}: {len(tickers)} tradable tickers")

            # Parse each ticker
            for ticker in tickers:
                try:
                    ticker_info = self.stock_parser.parse_ticker_info(ticker)

                    if ticker_info:
                        ticker_info['exchange'] = self.EXCHANGE_NAMES[exchange_code]
                        ticker_info['region'] = self.REGION_CODE
                        ticker_info['asset_type'] = 'STOCK'
                        ticker_info['is_active'] = True
                        ticker_info['kis_exchange_code'] = exchange_code

                        all_stocks.append(ticker_info)

                except Exception as e:
                    logger.debug(f"⚠️ Failed to parse {ticker}: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Failed to scan {exchange_code}: {e}")
            continue

    if not all_stocks:
        logger.warning("⚠️ No HK stocks found")
        return []

    # Save to database
    logger.info(f"💾 Saving {len(all_stocks)} HK stocks to database...")
    self._save_tickers_to_db(all_stocks, asset_type='STOCK')

    logger.info(f"✅ API scan complete: {len(all_stocks)} stocks")

    self._log_exchange_breakdown(all_stocks)
    return all_stocks

def _log_exchange_breakdown(self, stocks: List[Dict]):
    """Log exchange breakdown statistics"""
    exchange_counts = {}
    for stock in stocks:
        exchange = stock.get('exchange', 'Unknown')
        exchange_counts[exchange] = exchange_counts.get(exchange, 0) + 1

    for exchange, count in exchange_counts.items():
        logger.info(f"   {exchange}: {count} stocks")
```

### Step 4: Create Integration Tests

**Template**: Copy `test_master_file_integration.py` and modify for each region

```bash
# Create test for HK
cp scripts/test_master_file_integration.py scripts/test_hk_integration.py

# Modifications needed:
# 1. Change 'US' → 'HK'
# 2. Change USAdapterKIS → HKAdapterKIS
# 3. Update expected ticker counts (~500-1,000 for HK)
# 4. Update exchange codes (NASD/NYSE/AMEX → SEHK)
```

### Step 5: Validate Integration

**Validation Commands**:

```bash
# 1. Test master file manager for all regions
python3 scripts/test_master_file_manager.py

# 2. Test HK integration
python3 scripts/test_hk_integration.py

# 3. Test CN integration
python3 scripts/test_cn_integration.py

# 4. Test JP integration
python3 scripts/test_jp_integration.py

# 5. Test VN integration
python3 scripts/test_vn_integration.py
```

---

## Region-Specific Considerations

### Hong Kong (HK)

**Ticker Format**:
- KIS API: `0700`, `9988`
- Master File: `0700`, `9988`
- Normalized: `0700.HK`, `9988.HK`

**Ticker Normalization**:
```python
def _normalize_ticker(self, symbol: str, market_code: str) -> str:
    if market_code == 'hks':
        symbol = symbol.strip()
        if not symbol.endswith('.HK'):
            symbol = symbol.zfill(4) + '.HK'  # Pad to 4 digits
        return symbol
```

**Expected Coverage**: ~500-1,000 stocks

### China (CN)

**Ticker Format**:
- KIS API: `600519`, `000858`
- Master File: `600519`, `000858`
- Normalized: `600519.SS` (Shanghai), `000858.SZ` (Shenzhen)

**Ticker Normalization**:
```python
def _normalize_ticker(self, symbol: str, market_code: str) -> str:
    if market_code == 'shs':  # Shanghai
        return symbol.strip() + '.SS' if not symbol.endswith('.SS') else symbol.strip()
    elif market_code == 'szs':  # Shenzhen
        return symbol.strip() + '.SZ' if not symbol.endswith('.SZ') else symbol.strip()
```

**Expected Coverage**: ~500-1,000 stocks (선강통/후강통 only)

### Japan (JP)

**Ticker Format**:
- KIS API: `7203`, `9984`
- Master File: `7203`, `9984`
- Normalized: `7203`, `9984` (no suffix)

**Ticker Normalization**:
```python
def _normalize_ticker(self, symbol: str, market_code: str) -> str:
    if market_code == 'tse':
        return symbol.strip()  # No normalization needed
```

**Expected Coverage**: ~500-1,000 stocks

### Vietnam (VN)

**Ticker Format**:
- KIS API: `VCB`, `VHM`
- Master File: `vcb`, `vhm`
- Normalized: `VCB`, `VHM` (uppercase)

**Ticker Normalization**:
```python
def _normalize_ticker(self, symbol: str, market_code: str) -> str:
    if market_code in ['hnx', 'hsx']:  # Vietnam
        return symbol.strip().upper()
```

**Expected Coverage**: ~100-300 stocks (VN30 index mainly)

---

## Performance Expectations

### Master File Method (Instant)

| Region | Exchanges | Expected Tickers | Scan Time | API Calls |
|--------|-----------|------------------|-----------|-----------|
| **US** | NASD, NYSE, AMEX | 6,527 | 0.24s | 0 |
| **HK** | SEHK | 500-1,000 | <0.2s | 0 |
| **CN** | SHAA, SZAA | 500-1,000 | <0.2s | 0 |
| **JP** | TKSE | 500-1,000 | <0.2s | 0 |
| **VN** | HASE, VNSE | 100-300 | <0.1s | 0 |

### API Method (Fallback)

| Region | Exchanges | Expected Tickers | Scan Time | API Calls |
|--------|-----------|------------------|-----------|-----------|
| **US** | NASD, NYSE, AMEX | ~3,000 | ~2.5 min | ~3,000 |
| **HK** | SEHK | ~500-1,000 | ~1-2 min | ~500-1,000 |
| **CN** | SHAA, SZAA | ~500-1,000 | ~1-2 min | ~500-1,000 |
| **JP** | TKSE | ~500-1,000 | ~1-2 min | ~500-1,000 |
| **VN** | HASE, VNSE | ~100-300 | ~0.5-1 min | ~100-300 |

---

## Deployment Strategy

### Phase 1: US Market (Complete ✅)

- [x] Master file manager implementation
- [x] API client integration
- [x] US adapter updates
- [x] Integration tests
- [x] Documentation

### Phase 2: Hong Kong Market

- [ ] Update HK adapter (`hk_adapter_kis.py`)
- [ ] Create HK integration test
- [ ] Test with real HK data
- [ ] Validate ticker normalization (padding + .HK suffix)
- [ ] Deploy to production

### Phase 3: China Market

- [ ] Update CN adapter (`cn_adapter_kis.py`)
- [ ] Create CN integration test
- [ ] Test with real CN data
- [ ] Validate ticker normalization (.SS/.SZ suffixes)
- [ ] Deploy to production

### Phase 4: Japan Market

- [ ] Update JP adapter (`jp_adapter_kis.py`)
- [ ] Create JP integration test
- [ ] Test with real JP data
- [ ] Validate ticker normalization (no suffix)
- [ ] Deploy to production

### Phase 5: Vietnam Market

- [ ] Update VN adapter (`vn_adapter_kis.py`)
- [ ] Create VN integration test
- [ ] Test with real VN data
- [ ] Validate ticker normalization (uppercase)
- [ ] Deploy to production

---

## Testing Checklist

### Per Region Testing

- [ ] Master file download successful
- [ ] Master file parsing correct (ticker count)
- [ ] Ticker normalization correct (format validation)
- [ ] API client integration working
- [ ] Market adapter scan working
- [ ] Database save successful
- [ ] Data quality validation passed (>95% complete)
- [ ] Performance metrics met (<1s scan time)

### Cross-Region Testing

- [ ] Multi-region scan doesn't conflict
- [ ] Region column properly set in database
- [ ] No ticker contamination between regions
- [ ] Cache TTL working per region
- [ ] Force refresh working per region

---

## Common Issues and Solutions

### Issue 1: Ticker Normalization Mismatch

**Symptoms**:
- Tickers in database don't match yfinance format
- Data collection fails for normalized tickers

**Solution**:
- Verify normalization logic matches parser expectations
- Test with sample tickers from each exchange
- Update parser if needed to handle both formats

### Issue 2: Master File Parse Failure

**Symptoms**:
- `parse_market()` returns empty DataFrame
- Security type filter removes all tickers

**Solution**:
- Verify security type column value (should be int 2)
- Check encoding (should be cp949 for Korean)
- Validate column names match expected format

### Issue 3: yfinance Enrichment Fails

**Symptoms**:
- `scan_stocks()` returns 0 stocks
- Master file has tickers but enrichment fails

**Solution**:
- Make yfinance enrichment optional
- Use master file data as primary source
- Log enrichment failures without blocking

---

## Reference Implementation

**Complete US Integration**: See `us_adapter_kis.py:93-328`

**Key Methods**:
1. `scan_stocks()` - Main entry point with master file priority
2. `_scan_stocks_from_master_file()` - Master file method (instant)
3. `_scan_stocks_from_api()` - API method (fallback)
4. `_log_exchange_breakdown()` - Statistics logging

**Copy Pattern**: Use US implementation as template for all other regions

---

## Conclusion

**Current Status**: US integration complete and production-ready

**Next Steps**:
1. Deploy US integration to production
2. Validate US integration in production environment
3. Extend to HK, CN, JP, VN markets using this guide
4. Monitor performance and data quality metrics

**Estimated Timeline**:
- Phase 2 (HK): 1-2 days
- Phase 3 (CN): 1-2 days
- Phase 4 (JP): 1-2 days
- Phase 5 (VN): 1-2 days
- **Total**: ~1 week for complete multi-region rollout

**Success Criteria**:
- All 5 regions using master file method by default
- <1s scan time per region
- 100% API call reduction for ticker scanning
- >95% data quality validation
- Zero production incidents
