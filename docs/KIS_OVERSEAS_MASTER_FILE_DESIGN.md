# KIS Overseas Master File - New Listing Detection System Design

**Author**: Spock Trading System
**Date**: 2025-10-15
**Status**: Design Phase
**Reference Implementation**: `scripts/backfill_sector_kis_master.py`

---

## 1. Overview

### 1.1 Purpose
Design an automated new listing detection system for overseas (US, HK, CN, JP, VN) stock tickers using KIS master files with periodic file size comparison logic.

### 1.2 Problem Statement
Current Issues:
- KIS API endpoints (`HHDFS76410000`, `CTPF1702R`) do not support bulk ticker listing
- Manual ticker list (`add_us_tickers_simple.py`) contains only 85 stocks
- No automated mechanism to detect newly listed stocks
- Temporary yfinance solution includes non-tradable stocks (~8,000 total vs ~3,000 tradable)

### 1.3 Proposed Solution
Implement master file-based ticker management system:
- Periodic download of KIS master files from official sources
- File size comparison for change detection
- Automatic parsing and database update
- New listing notification and tracking

---

## 2. System Architecture

### 2.1 Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 Master File Manager                          │
│  - Periodic scheduler (cron/APScheduler)                    │
│  - File size comparison logic                               │
│  - Download orchestration                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Master File Downloader                          │
│  - HTTP HEAD request (size check)                           │
│  - HTTP GET request (file download)                         │
│  - Local cache management                                   │
│  - Checksum verification                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Master File Parser                              │
│  - Format detection (.mst → .txt conversion)                │
│  - Ticker extraction                                        │
│  - Metadata parsing (name, exchange, sector)               │
│  - Data validation                                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Database Updater                                │
│  - Diff calculation (new/changed/removed tickers)           │
│  - Batch insert/update operations                           │
│  - Transaction management                                   │
│  - Rollback capability                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              Notification System                             │
│  - New listing alerts                                       │
│  - Change summary reports                                   │
│  - Error notifications                                      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
[KIS Master File Server]
         │
         │ (1) HEAD request (size check)
         ▼
[Local Cache Metadata]
         │
         │ (2) Size comparison
         ▼
    [Decision]
         │
         ├─ Same size → Skip download
         │
         └─ Larger size → Download
                    │
                    │ (3) GET request (download)
                    ▼
            [Local Master File]
                    │
                    │ (4) Parse
                    ▼
            [Ticker List (New)]
                    │
                    │ (5) Diff calculation
                    ▼
            [Database Tickers (Old)]
                    │
                    │ (6) Update database
                    ▼
            [Updated Database]
                    │
                    │ (7) Notify
                    ▼
            [Alert/Report]
```

---

## 3. File Size Comparison Logic

### 3.1 User Proposal
> "주기적으로 마스터파일사이즈를 비교하여 보유한 마스터파일과 새로 받아야 할 마스터파일의 사이즈가 동일한 경우 패스, 새로 받을 마스터파일의 사이즈가 큰경우 다운 받고 덮어쓰기"

### 3.2 Implementation Strategy

#### Step 1: Periodic Size Check
```python
def check_for_updates(self, exchange: str) -> bool:
    """
    Check if master file has updates by comparing file sizes

    Args:
        exchange: Exchange code (NASD, NYSE, AMEX, SEHK, SHAA, SZAA, TKSE, HASE, VNSE)

    Returns:
        True if update is needed (remote size > local size)
    """
    # Get local file metadata
    local_file_path = self._get_local_file_path(exchange)
    local_size = self._get_local_file_size(local_file_path)
    local_modified_time = self._get_local_file_mtime(local_file_path)

    # Get remote file metadata via HTTP HEAD request
    remote_url = self._get_master_file_url(exchange)
    remote_size = self._get_remote_file_size(remote_url)

    # Size comparison logic
    if local_size is None:
        # Local file doesn't exist - need to download
        logger.info(f"[{exchange}] No local master file - download required")
        return True

    if remote_size > local_size:
        # Remote file is larger - new listings detected
        logger.info(f"[{exchange}] Master file size increased: {local_size} → {remote_size} bytes")
        return True

    if remote_size == local_size:
        # Same size - skip download
        logger.info(f"[{exchange}] Master file unchanged ({local_size} bytes) - skip")
        return False

    if remote_size < local_size:
        # Remote file is smaller - potential issue or delisting
        logger.warning(
            f"[{exchange}] Remote file smaller than local ({remote_size} < {local_size}) - "
            f"possible delisting or file issue - download for verification"
        )
        return True
```

#### Step 2: Download Strategy
```python
def download_master_file(self, exchange: str, force: bool = False) -> bool:
    """
    Download master file if update is needed

    Args:
        exchange: Exchange code
        force: Force download regardless of size check

    Returns:
        True if download successful
    """
    if not force and not self.check_for_updates(exchange):
        return False  # No update needed

    remote_url = self._get_master_file_url(exchange)
    local_file_path = self._get_local_file_path(exchange)

    # Create backup of existing file (if exists)
    self._backup_existing_file(local_file_path)

    try:
        # Download with progress tracking
        response = requests.get(remote_url, stream=True, timeout=60)
        response.raise_for_status()

        # Save to temporary file first
        temp_file = f"{local_file_path}.tmp"
        with open(temp_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        # Verify download (size check)
        downloaded_size = os.path.getsize(temp_file)
        expected_size = int(response.headers.get('Content-Length', 0))

        if downloaded_size != expected_size:
            raise ValueError(f"Size mismatch: {downloaded_size} != {expected_size}")

        # Move temp file to final location (atomic operation)
        os.replace(temp_file, local_file_path)

        logger.info(f"[{exchange}] Master file downloaded: {downloaded_size} bytes")
        return True

    except Exception as e:
        logger.error(f"[{exchange}] Download failed: {e}")
        # Restore from backup if available
        self._restore_from_backup(local_file_path)
        return False
```

---

## 4. Master File Format & Parsing

### 4.1 File Format Investigation

Based on KIS documentation and reference implementation (`backfill_sector_kis_master.py`):

**Korean Market** (Reference):
- Format: Excel (.xlsx)
- Source: `https://raw.githubusercontent.com/koreainvestment/open-trading-api/main/exchange_code/종목코드_마스터.xlsx`
- Columns: 단축코드, 한글명, 섹터, 업종, 섹터코드, 업종코드

**Overseas Markets** (Expected):
- Format: .mst files (binary) → convertible to .txt
- Source: KIS Developers portal (downloadable from website)
- Expected columns (US example):
  - Ticker symbol (e.g., AAPL)
  - Company name (e.g., Apple Inc.)
  - Exchange code (NASD, NYSE, AMEX)
  - Sector/Industry information
  - Listing status (active/inactive)

### 4.2 Parser Implementation

```python
class OverseasMasterFileParser:
    """Parser for KIS overseas stock master files"""

    EXCHANGE_FORMATS = {
        'NASD': 'txt',   # NASDAQ
        'NYSE': 'txt',   # New York Stock Exchange
        'AMEX': 'txt',   # American Stock Exchange
        'SEHK': 'txt',   # Hong Kong Stock Exchange
        'SHAA': 'txt',   # Shanghai Stock Exchange A-shares
        'SZAA': 'txt',   # Shenzhen Stock Exchange A-shares
        'TKSE': 'txt',   # Tokyo Stock Exchange
        'HASE': 'txt',   # Ho Chi Minh Stock Exchange
        'VNSE': 'txt',   # Hanoi Stock Exchange
    }

    def parse_master_file(self, file_path: str, exchange: str) -> List[Dict]:
        """
        Parse overseas master file

        Args:
            file_path: Path to master file
            exchange: Exchange code

        Returns:
            List of ticker dictionaries
        """
        file_format = self.EXCHANGE_FORMATS.get(exchange, 'txt')

        if file_format == 'txt':
            return self._parse_txt_format(file_path, exchange)
        else:
            raise ValueError(f"Unsupported format: {file_format}")

    def _parse_txt_format(self, file_path: str, exchange: str) -> List[Dict]:
        """
        Parse .txt format master file

        Expected format (tab-separated or fixed-width):
        TICKER    NAME              EXCHANGE    SECTOR
        AAPL      Apple Inc.        NASD        Technology
        MSFT      Microsoft Corp.   NASD        Technology
        ...
        """
        tickers = []

        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Parse line (adjust based on actual format)
                parts = line.split('\t')  # or line.split() for whitespace

                if len(parts) < 2:
                    continue

                ticker_info = {
                    'ticker': parts[0].strip(),
                    'name': parts[1].strip() if len(parts) > 1 else '',
                    'exchange': self._normalize_exchange(exchange),
                    'region': self._get_region_from_exchange(exchange),
                    'sector': parts[2].strip() if len(parts) > 2 else 'Unknown',
                    'industry': parts[3].strip() if len(parts) > 3 else 'Unknown',
                    'is_active': self._parse_active_status(parts) if len(parts) > 4 else True,
                }

                tickers.append(ticker_info)

        logger.info(f"[{exchange}] Parsed {len(tickers)} tickers from master file")
        return tickers

    def _normalize_exchange(self, exchange_code: str) -> str:
        """Map KIS exchange code to standard exchange name"""
        exchange_map = {
            'NASD': 'NASDAQ',
            'NYSE': 'NYSE',
            'AMEX': 'AMEX',
            'SEHK': 'HKEX',
            'SHAA': 'SSE',
            'SZAA': 'SZSE',
            'TKSE': 'TSE',
            'HASE': 'HOSE',
            'VNSE': 'HNX',
        }
        return exchange_map.get(exchange_code, exchange_code)

    def _get_region_from_exchange(self, exchange_code: str) -> str:
        """Map exchange code to region"""
        region_map = {
            'NASD': 'US', 'NYSE': 'US', 'AMEX': 'US',
            'SEHK': 'HK',
            'SHAA': 'CN', 'SZAA': 'CN',
            'TKSE': 'JP',
            'HASE': 'VN', 'VNSE': 'VN',
        }
        return region_map.get(exchange_code, 'UNKNOWN')
```

---

## 5. New Listing Detection

### 5.1 Diff Calculation

```python
class NewListingDetector:
    """Detect new/changed/removed tickers by comparing master file with database"""

    def __init__(self, db: SQLiteDatabaseManager):
        self.db = db

    def calculate_diff(self, new_tickers: List[Dict], region: str) -> Dict:
        """
        Calculate differences between new master file and existing database

        Args:
            new_tickers: Parsed tickers from new master file
            region: Region code (US, HK, CN, JP, VN)

        Returns:
            Dictionary with new, changed, removed tickers
        """
        # Get existing tickers from database
        existing_tickers = self._get_existing_tickers(region)
        existing_map = {t['ticker']: t for t in existing_tickers}

        # Create new ticker map
        new_map = {t['ticker']: t for t in new_tickers}

        # Calculate differences
        new_ticker_symbols = set(new_map.keys()) - set(existing_map.keys())
        removed_ticker_symbols = set(existing_map.keys()) - set(new_map.keys())
        common_ticker_symbols = set(new_map.keys()) & set(existing_map.keys())

        # Detect changes in existing tickers
        changed_tickers = []
        for ticker in common_ticker_symbols:
            if self._has_changes(existing_map[ticker], new_map[ticker]):
                changed_tickers.append({
                    'ticker': ticker,
                    'old': existing_map[ticker],
                    'new': new_map[ticker],
                })

        diff_result = {
            'new': [new_map[t] for t in new_ticker_symbols],
            'changed': changed_tickers,
            'removed': [existing_map[t] for t in removed_ticker_symbols],
            'unchanged': len(common_ticker_symbols) - len(changed_tickers),
        }

        logger.info(
            f"[{region}] Diff: "
            f"New={len(diff_result['new'])}, "
            f"Changed={len(diff_result['changed'])}, "
            f"Removed={len(diff_result['removed'])}, "
            f"Unchanged={diff_result['unchanged']}"
        )

        return diff_result

    def _has_changes(self, old_ticker: Dict, new_ticker: Dict) -> bool:
        """Check if ticker has meaningful changes"""
        # Compare key fields
        for field in ['name', 'sector', 'industry', 'is_active']:
            if old_ticker.get(field) != new_ticker.get(field):
                return True
        return False

    def _get_existing_tickers(self, region: str) -> List[Dict]:
        """Get existing tickers from database"""
        conn = self.db._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ticker, name, exchange, region, sector, industry, is_active
            FROM tickers
            WHERE region = ? AND asset_type = 'STOCK'
        """, (region,))

        tickers = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return tickers
```

### 5.2 Database Update Strategy

```python
class MasterFileUpdater:
    """Update database with new master file data"""

    def __init__(self, db: SQLiteDatabaseManager):
        self.db = db

    def update_database(self, diff: Dict, region: str, dry_run: bool = False) -> bool:
        """
        Update database with diff results

        Args:
            diff: Diff calculation result
            region: Region code
            dry_run: If True, simulate without actual updates

        Returns:
            True if successful
        """
        if dry_run:
            logger.info(f"[{region}] DRY RUN MODE - No actual database updates")

        conn = self.db._get_connection()
        cursor = conn.cursor()

        try:
            # Start transaction
            cursor.execute("BEGIN TRANSACTION")

            # 1. Insert new tickers
            for ticker_info in diff['new']:
                if not dry_run:
                    self._insert_ticker(cursor, ticker_info)
                logger.info(
                    f"✅ [{ticker_info['ticker']}] NEW: {ticker_info['name']} "
                    f"({ticker_info['exchange']})"
                    f"{' (DRY RUN)' if dry_run else ''}"
                )

            # 2. Update changed tickers
            for change in diff['changed']:
                if not dry_run:
                    self._update_ticker(cursor, change['new'])
                logger.info(
                    f"🔄 [{change['ticker']}] CHANGED: "
                    f"{self._describe_changes(change['old'], change['new'])}"
                    f"{' (DRY RUN)' if dry_run else ''}"
                )

            # 3. Mark removed tickers as inactive (don't delete)
            for ticker_info in diff['removed']:
                if not dry_run:
                    self._deactivate_ticker(cursor, ticker_info['ticker'])
                logger.info(
                    f"⏸️ [{ticker_info['ticker']}] REMOVED: Marked as inactive"
                    f"{' (DRY RUN)' if dry_run else ''}"
                )

            # Commit transaction
            if not dry_run:
                conn.commit()
                logger.info(f"[{region}] Database updated successfully")
            else:
                conn.rollback()
                logger.info(f"[{region}] DRY RUN - Changes rolled back")

            return True

        except Exception as e:
            conn.rollback()
            logger.error(f"[{region}] Database update failed: {e}")
            return False

        finally:
            conn.close()

    def _insert_ticker(self, cursor, ticker_info: Dict):
        """Insert new ticker into database"""
        cursor.execute("""
            INSERT OR REPLACE INTO tickers
            (ticker, name, name_eng, exchange, region, currency, asset_type,
             is_active, created_at, last_updated, data_source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ticker_info['ticker'],
            ticker_info['name'],
            ticker_info['name'],  # name_eng same as name for overseas
            ticker_info['exchange'],
            ticker_info['region'],
            self._get_currency(ticker_info['region']),
            'STOCK',
            ticker_info.get('is_active', True),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'kis_master_file'
        ))

    def _update_ticker(self, cursor, ticker_info: Dict):
        """Update existing ticker"""
        cursor.execute("""
            UPDATE tickers
            SET name = ?, name_eng = ?, is_active = ?, last_updated = ?
            WHERE ticker = ? AND region = ?
        """, (
            ticker_info['name'],
            ticker_info['name'],
            ticker_info.get('is_active', True),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ticker_info['ticker'],
            ticker_info['region']
        ))

    def _deactivate_ticker(self, cursor, ticker: str):
        """Mark ticker as inactive (delisted)"""
        cursor.execute("""
            UPDATE tickers
            SET is_active = 0, last_updated = ?
            WHERE ticker = ?
        """, (
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ticker
        ))

    def _get_currency(self, region: str) -> str:
        """Get currency code from region"""
        currency_map = {
            'US': 'USD',
            'HK': 'HKD',
            'CN': 'CNY',
            'JP': 'JPY',
            'VN': 'VND',
        }
        return currency_map.get(region, 'USD')

    def _describe_changes(self, old: Dict, new: Dict) -> str:
        """Generate human-readable change description"""
        changes = []
        for field in ['name', 'sector', 'industry', 'is_active']:
            old_val = old.get(field)
            new_val = new.get(field)
            if old_val != new_val:
                changes.append(f"{field}: {old_val} → {new_val}")
        return ", ".join(changes)
```

---

## 6. Periodic Scheduler

### 6.1 Scheduling Strategy

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

class MasterFileUpdateScheduler:
    """Schedule periodic master file updates"""

    def __init__(self, db: SQLiteDatabaseManager):
        self.db = db
        self.scheduler = BackgroundScheduler()

        # Components
        self.downloader = OverseasMasterFileDownloader()
        self.parser = OverseasMasterFileParser()
        self.detector = NewListingDetector(db)
        self.updater = MasterFileUpdater(db)

    def start(self):
        """Start scheduler with configured jobs"""
        # Daily check at 6:00 AM (after market close, before next open)
        self.scheduler.add_job(
            func=self.check_all_markets,
            trigger=CronTrigger(hour=6, minute=0),
            id='daily_master_file_check',
            name='Daily Master File Check',
            replace_existing=True
        )

        # Weekly full refresh on Sunday at 3:00 AM
        self.scheduler.add_job(
            func=self.full_refresh_all_markets,
            trigger=CronTrigger(day_of_week='sun', hour=3, minute=0),
            id='weekly_full_refresh',
            name='Weekly Full Refresh',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info("✅ Master file update scheduler started")

    def check_all_markets(self):
        """Check all overseas markets for updates"""
        exchanges = ['NASD', 'NYSE', 'AMEX', 'SEHK', 'SHAA', 'SZAA', 'TKSE', 'HASE', 'VNSE']

        for exchange in exchanges:
            try:
                self.check_market(exchange, force=False)
            except Exception as e:
                logger.error(f"[{exchange}] Check failed: {e}")

    def check_market(self, exchange: str, force: bool = False):
        """
        Check single market for updates

        Args:
            exchange: Exchange code
            force: Force download regardless of size check
        """
        logger.info(f"[{exchange}] Starting update check...")

        # Step 1: Check and download if needed
        downloaded = self.downloader.download_master_file(exchange, force=force)

        if not downloaded and not force:
            logger.info(f"[{exchange}] No update needed - skipped")
            return

        # Step 2: Parse master file
        file_path = self.downloader._get_local_file_path(exchange)
        new_tickers = self.parser.parse_master_file(file_path, exchange)

        if not new_tickers:
            logger.error(f"[{exchange}] Parse failed - no tickers extracted")
            return

        # Step 3: Calculate diff
        region = self.parser._get_region_from_exchange(exchange)
        diff = self.detector.calculate_diff(new_tickers, region)

        # Step 4: Update database
        success = self.updater.update_database(diff, region, dry_run=False)

        if success:
            # Step 5: Send notification if there are changes
            if diff['new'] or diff['changed'] or diff['removed']:
                self.notify_changes(exchange, diff)

        logger.info(f"[{exchange}] Update complete")

    def full_refresh_all_markets(self):
        """Force full refresh for all markets (weekly)"""
        logger.info("=" * 80)
        logger.info("🔄 Starting Weekly Full Refresh")
        logger.info("=" * 80)

        exchanges = ['NASD', 'NYSE', 'AMEX', 'SEHK', 'SHAA', 'SZAA', 'TKSE', 'HASE', 'VNSE']

        for exchange in exchanges:
            try:
                self.check_market(exchange, force=True)
            except Exception as e:
                logger.error(f"[{exchange}] Full refresh failed: {e}")

        logger.info("=" * 80)
        logger.info("✅ Weekly Full Refresh Complete")
        logger.info("=" * 80)

    def notify_changes(self, exchange: str, diff: Dict):
        """Send notification about changes"""
        # TODO: Implement notification system (email, Slack, etc.)
        logger.info(
            f"🔔 [{exchange}] Changes detected: "
            f"New={len(diff['new'])}, "
            f"Changed={len(diff['changed'])}, "
            f"Removed={len(diff['removed'])}"
        )

    def stop(self):
        """Stop scheduler"""
        self.scheduler.shutdown()
        logger.info("⏹️ Master file update scheduler stopped")
```

### 6.2 Schedule Configuration

| Frequency | Trigger | Purpose | Exchange Coverage |
|-----------|---------|---------|-------------------|
| **Daily** | 6:00 AM | Size check + update if needed | All (NASD, NYSE, AMEX, SEHK, SHAA, SZAA, TKSE, HASE, VNSE) |
| **Weekly** | Sunday 3:00 AM | Force full refresh | All exchanges |
| **On-Demand** | Manual trigger | Emergency update or testing | Specific exchange(s) |

---

## 7. Error Handling & Recovery

### 7.1 Error Scenarios

| Error Type | Scenario | Recovery Action |
|------------|----------|-----------------|
| **Download Failure** | Network timeout, 404 Not Found | Retry with exponential backoff (3 attempts), restore from backup |
| **Size Mismatch** | Downloaded size ≠ Content-Length | Delete temp file, retry download |
| **Parse Error** | Invalid file format, corrupted data | Skip update, alert admin, use previous version |
| **Database Error** | Transaction failure, lock timeout | Rollback transaction, retry after delay |
| **Remote File Smaller** | Potential delisting or file issue | Download for verification, compare contents, alert admin |

### 7.2 Backup Strategy

```python
class BackupManager:
    """Manage master file backups"""

    BACKUP_DIR = "data/master_file_backups"
    MAX_BACKUPS = 7  # Keep 7 days of backups

    def backup_file(self, file_path: str) -> str:
        """
        Create timestamped backup of master file

        Args:
            file_path: Path to master file

        Returns:
            Path to backup file
        """
        if not os.path.exists(file_path):
            return None

        # Create backup directory
        os.makedirs(self.BACKUP_DIR, exist_ok=True)

        # Generate backup filename with timestamp
        basename = os.path.basename(file_path)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"{basename}.{timestamp}.bak"
        backup_path = os.path.join(self.BACKUP_DIR, backup_filename)

        # Copy file to backup location
        shutil.copy2(file_path, backup_path)

        # Cleanup old backups
        self._cleanup_old_backups(basename)

        logger.info(f"💾 Backup created: {backup_path}")
        return backup_path

    def restore_from_backup(self, file_path: str) -> bool:
        """
        Restore most recent backup

        Args:
            file_path: Path to master file

        Returns:
            True if restore successful
        """
        basename = os.path.basename(file_path)
        backups = self._list_backups(basename)

        if not backups:
            logger.warning(f"⚠️ No backups found for {basename}")
            return False

        # Get most recent backup
        latest_backup = backups[0]

        try:
            shutil.copy2(latest_backup, file_path)
            logger.info(f"♻️ Restored from backup: {latest_backup}")
            return True
        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            return False

    def _list_backups(self, basename: str) -> List[str]:
        """List all backups for given file, sorted by timestamp (newest first)"""
        if not os.path.exists(self.BACKUP_DIR):
            return []

        backups = []
        for filename in os.listdir(self.BACKUP_DIR):
            if filename.startswith(basename):
                backup_path = os.path.join(self.BACKUP_DIR, filename)
                backups.append(backup_path)

        # Sort by modification time (newest first)
        backups.sort(key=os.path.getmtime, reverse=True)
        return backups

    def _cleanup_old_backups(self, basename: str):
        """Delete old backups beyond MAX_BACKUPS limit"""
        backups = self._list_backups(basename)

        if len(backups) > self.MAX_BACKUPS:
            for old_backup in backups[self.MAX_BACKUPS:]:
                os.remove(old_backup)
                logger.info(f"🗑️ Deleted old backup: {old_backup}")
```

---

## 8. Monitoring & Logging

### 8.1 Logging Strategy

```python
# Log levels by event type
EVENT_LOG_LEVELS = {
    'size_check': logging.INFO,
    'download_start': logging.INFO,
    'download_complete': logging.INFO,
    'download_failed': logging.ERROR,
    'parse_success': logging.INFO,
    'parse_failed': logging.ERROR,
    'new_listing': logging.INFO,
    'ticker_changed': logging.INFO,
    'ticker_removed': logging.WARNING,
    'db_update_success': logging.INFO,
    'db_update_failed': logging.ERROR,
}

# Log format
LOG_FORMAT = (
    "%(asctime)s [%(levelname)s] "
    "[%(exchange)s] %(event_type)s - %(message)s"
)

# Example usage
logger.info(
    "New listing detected",
    extra={
        'exchange': 'NASD',
        'event_type': 'new_listing',
        'ticker': 'NEWTICKER',
        'name': 'New Company Inc.',
    }
)
```

### 8.2 Metrics Collection

```python
class MetricsCollector:
    """Collect metrics for master file updates"""

    def record_update_run(self, exchange: str, result: Dict):
        """Record update run metrics"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'exchange': exchange,
            'download_time_ms': result.get('download_time_ms'),
            'parse_time_ms': result.get('parse_time_ms'),
            'file_size_bytes': result.get('file_size_bytes'),
            'tickers_parsed': result.get('tickers_parsed'),
            'new_tickers': result.get('new_tickers'),
            'changed_tickers': result.get('changed_tickers'),
            'removed_tickers': result.get('removed_tickers'),
            'update_success': result.get('update_success'),
        }

        # Store metrics (could be database, file, or monitoring system)
        self._store_metrics(metrics)

    def get_update_history(self, exchange: str, days: int = 30) -> List[Dict]:
        """Get update history for analysis"""
        # Retrieve historical metrics
        pass
```

### 8.3 Alert Rules

| Alert Type | Condition | Severity | Action |
|------------|-----------|----------|--------|
| **Download Failure** | 3 consecutive failures | Critical | Admin notification, use backup |
| **Large File Size Increase** | Size increase >20% | Warning | Verify authenticity before update |
| **High New Listing Count** | >100 new tickers in single update | Warning | Manual review recommended |
| **Mass Delisting** | >50 tickers removed | Critical | Manual verification required |
| **Parse Failure** | Unable to extract tickers | Critical | Admin notification, skip update |

---

## 9. Master File URL Configuration

### 9.1 URL Discovery Process

**For KIS Overseas Master Files**, the exact URLs need to be discovered from:

1. **KIS Developers Portal**: https://apiportal.koreainvestment.com/
   - Check "자료실" or "Downloads" section
   - Look for "해외주식 종목코드 마스터"

2. **KIS GitHub Repository**: https://github.com/koreainvestment/open-trading-api
   - Check `/exchange_code/` or `/overseas_stocks/` directories
   - Look for sample master files or documentation

3. **KIS API Documentation**: Excel file (`한국투자증권_오픈API_전체문서_20250920_030000.xlsx`)
   - Check for master file download guidance
   - May contain direct download links

### 9.2 URL Configuration (Placeholder)

```python
class MasterFileURLConfig:
    """Master file URL configuration"""

    # Base URLs (to be updated after investigation)
    GITHUB_BASE = "https://raw.githubusercontent.com/koreainvestment/open-trading-api/main"
    DEVELOPER_PORTAL_BASE = "https://apiportal.koreainvestment.com/download"

    # Exchange-specific URLs (to be confirmed)
    MASTER_FILE_URLS = {
        # US Markets
        'NASD': f"{GITHUB_BASE}/exchange_code/nasdaq_master.mst",  # Placeholder
        'NYSE': f"{GITHUB_BASE}/exchange_code/nyse_master.mst",    # Placeholder
        'AMEX': f"{GITHUB_BASE}/exchange_code/amex_master.mst",    # Placeholder

        # Hong Kong
        'SEHK': f"{GITHUB_BASE}/exchange_code/hkex_master.mst",    # Placeholder

        # China
        'SHAA': f"{GITHUB_BASE}/exchange_code/sse_master.mst",     # Placeholder
        'SZAA': f"{GITHUB_BASE}/exchange_code/szse_master.mst",    # Placeholder

        # Japan
        'TKSE': f"{GITHUB_BASE}/exchange_code/tse_master.mst",     # Placeholder

        # Vietnam
        'HASE': f"{GITHUB_BASE}/exchange_code/hose_master.mst",    # Placeholder
        'VNSE': f"{GITHUB_BASE}/exchange_code/hnx_master.mst",     # Placeholder
    }

    @classmethod
    def get_master_file_url(cls, exchange: str) -> str:
        """Get master file URL for exchange"""
        url = cls.MASTER_FILE_URLS.get(exchange)
        if not url:
            raise ValueError(f"No URL configured for exchange: {exchange}")
        return url
```

**Action Required**: After investigation, update URLs with actual locations.

---

## 10. Implementation Plan

### Phase 1: Investigation (Week 1)
- [ ] Investigate KIS Developers portal for master file URLs
- [ ] Download sample master files for each exchange
- [ ] Analyze file formats (.mst structure, encoding, columns)
- [ ] Document actual file structure and parsing requirements

### Phase 2: Core Implementation (Week 2)
- [ ] Implement `OverseasMasterFileDownloader` class
- [ ] Implement `OverseasMasterFileParser` class
- [ ] Implement `NewListingDetector` class
- [ ] Implement `MasterFileUpdater` class
- [ ] Unit tests for each component

### Phase 3: Scheduler Integration (Week 3)
- [ ] Implement `MasterFileUpdateScheduler` class
- [ ] Integrate with existing spock.py orchestrator
- [ ] Add command-line interface for manual operations
- [ ] Integration tests

### Phase 4: Error Handling & Monitoring (Week 4)
- [ ] Implement `BackupManager` class
- [ ] Add retry logic and exponential backoff
- [ ] Implement `MetricsCollector` class
- [ ] Setup alert rules and notifications
- [ ] End-to-end testing

### Phase 5: Production Deployment (Week 5)
- [ ] Deploy to production environment
- [ ] Monitor initial runs for 7 days
- [ ] Tune thresholds and schedules based on actual data
- [ ] Documentation and runbook

---

## 11. API Integration Points

### 11.1 Update kis_overseas_stock_api.py

```python
# modules/api_clients/kis_overseas_stock_api.py

class KISOverseasStockAPI:
    """KIS Overseas Stock API Client"""

    def __init__(self, app_key: str, app_secret: str, base_url: str = None):
        # ... existing code ...

        # Add master file manager
        self.master_file_manager = OverseasMasterFileManager(self)

    def get_tradable_tickers(self, exchange_code: str, force_refresh: bool = False):
        """
        [UPDATED] Get tradable tickers from KIS master file

        Args:
            exchange_code: Exchange code (NASD, NYSE, AMEX, etc.)
            force_refresh: Force download of master file

        Returns:
            List of tradable ticker dictionaries
        """
        # Use master file instead of API
        return self.master_file_manager.get_tickers(
            exchange_code=exchange_code,
            force_refresh=force_refresh
        )
```

### 11.2 Update Market Adapters

```python
# modules/market_adapters/us_adapter_kis.py

class USAdapterKIS(BaseMarketAdapter):
    """US Market Adapter using KIS API"""

    def scan_stocks(self, force_refresh: bool = False) -> List[Dict]:
        """
        Scan US stocks from KIS master files

        Args:
            force_refresh: Force master file download

        Returns:
            List of US stock dictionaries
        """
        tickers = []

        # Scan all US exchanges
        for exchange in ['NASD', 'NYSE', 'AMEX']:
            exchange_tickers = self.kis_api.get_tradable_tickers(
                exchange_code=exchange,
                force_refresh=force_refresh
            )
            tickers.extend(exchange_tickers)

        logger.info(f"[US] Scanned {len(tickers)} tickers from master files")
        return tickers
```

---

## 12. Testing Strategy

### 12.1 Unit Tests

```python
# tests/test_master_file_manager.py

class TestOverseasMasterFileDownloader(unittest.TestCase):
    """Test master file downloader"""

    def test_check_for_updates_no_local_file(self):
        """Test update check when local file doesn't exist"""
        downloader = OverseasMasterFileDownloader()
        result = downloader.check_for_updates('NASD')
        self.assertTrue(result)  # Should return True (need to download)

    def test_check_for_updates_size_increased(self):
        """Test update check when remote file is larger"""
        # Mock local file with size 1000
        # Mock remote file with size 1500
        # Assert: should return True
        pass

    def test_check_for_updates_size_same(self):
        """Test update check when sizes are equal"""
        # Mock local file with size 1000
        # Mock remote file with size 1000
        # Assert: should return False
        pass

    def test_download_with_size_mismatch(self):
        """Test download failure due to size mismatch"""
        # Mock download with mismatched Content-Length
        # Assert: should raise ValueError and restore backup
        pass

class TestOverseasMasterFileParser(unittest.TestCase):
    """Test master file parser"""

    def test_parse_valid_file(self):
        """Test parsing valid master file"""
        # Create sample .txt file with known data
        # Parse and verify extracted tickers
        pass

    def test_parse_empty_file(self):
        """Test parsing empty file"""
        # Assert: should return empty list
        pass

    def test_normalize_exchange_codes(self):
        """Test exchange code normalization"""
        parser = OverseasMasterFileParser()
        self.assertEqual(parser._normalize_exchange('NASD'), 'NASDAQ')
        self.assertEqual(parser._normalize_exchange('SEHK'), 'HKEX')

class TestNewListingDetector(unittest.TestCase):
    """Test new listing detection"""

    def test_calculate_diff_new_tickers(self):
        """Test detection of new tickers"""
        # Setup: database with 100 tickers
        # Master file with 105 tickers (5 new)
        # Assert: diff['new'] contains 5 tickers
        pass

    def test_calculate_diff_removed_tickers(self):
        """Test detection of removed tickers"""
        # Setup: database with 100 tickers
        # Master file with 95 tickers (5 removed)
        # Assert: diff['removed'] contains 5 tickers
        pass

    def test_calculate_diff_changed_tickers(self):
        """Test detection of changed ticker metadata"""
        # Setup: ticker with name "Old Company Inc."
        # Master file with name "New Company Inc."
        # Assert: diff['changed'] contains 1 ticker
        pass
```

### 12.2 Integration Tests

```python
# tests/test_master_file_integration.py

class TestMasterFileIntegration(unittest.TestCase):
    """Integration tests for master file system"""

    def test_full_update_workflow(self):
        """Test complete update workflow: download → parse → diff → update"""
        # Step 1: Download master file
        # Step 2: Parse tickers
        # Step 3: Calculate diff
        # Step 4: Update database
        # Step 5: Verify database state
        pass

    def test_scheduler_daily_run(self):
        """Test scheduled daily update"""
        # Start scheduler
        # Trigger manual run
        # Verify: all exchanges checked
        pass

    def test_backup_and_restore(self):
        """Test backup creation and restoration"""
        # Create backup
        # Corrupt master file
        # Restore from backup
        # Verify: file restored correctly
        pass
```

### 12.3 Dry Run Mode

```bash
# Test without actual database updates
python3 scripts/update_overseas_master_files.py --dry-run --exchange NASD

# Expected output:
# [NASD] DRY RUN MODE - No actual database updates
# ✅ [AAPL] NEW: Apple Inc. (NASDAQ) (DRY RUN)
# ✅ [MSFT] NEW: Microsoft Corp. (NASDAQ) (DRY RUN)
# ...
# [NASD] DRY RUN - Changes rolled back
```

---

## 13. Documentation & Runbook

### 13.1 Operator Runbook

**Manual Update Operation**:
```bash
# Update single exchange
python3 scripts/update_overseas_master_files.py --exchange NASD

# Update all exchanges
python3 scripts/update_overseas_master_files.py --all

# Force refresh (ignore size check)
python3 scripts/update_overseas_master_files.py --exchange NASD --force

# Dry run (preview changes)
python3 scripts/update_overseas_master_files.py --exchange NASD --dry-run
```

**Troubleshooting**:
```bash
# Check master file metadata
python3 scripts/check_master_file_status.py --exchange NASD

# View update history
python3 scripts/view_update_history.py --exchange NASD --days 30

# Restore from backup
python3 scripts/restore_master_file.py --exchange NASD

# Verify database integrity
python3 scripts/verify_ticker_data.py --region US
```

---

## 14. Success Criteria

| Metric | Target | Method |
|--------|--------|--------|
| **Update Detection Accuracy** | >99% | Compare with manual verification |
| **Download Success Rate** | >98% | Track successful downloads / total attempts |
| **Parse Success Rate** | >99.5% | Track successful parses / total downloads |
| **Database Update Success** | >99.9% | Track transaction commits / attempts |
| **False Positive Rate** | <1% | Manual review of detected changes |
| **Latency (Daily Check)** | <30 seconds per exchange | Monitor execution time |
| **Downtime** | <0.1% missed updates | Track scheduler health |

---

## 15. Future Enhancements

### 15.1 Phase 2 Features
- [ ] Real-time update notifications (email, Slack, SMS)
- [ ] Web dashboard for monitoring master file status
- [ ] Automatic sector/industry enrichment via external APIs
- [ ] Multi-region concurrent updates with thread pool
- [ ] Machine learning-based anomaly detection

### 15.2 Phase 3 Features
- [ ] Historical ticker tracking (track lifetime of each ticker)
- [ ] IPO calendar integration
- [ ] Delisting prediction model
- [ ] Cross-market correlation analysis
- [ ] API endpoint for external access to master file data

---

## 16. References

### 16.1 KIS Resources
- **KIS Developers Portal**: https://apiportal.koreainvestment.com/
- **KIS GitHub Repository**: https://github.com/koreainvestment/open-trading-api
- **KIS API Documentation**: `한국투자증권_오픈API_전체문서_20250920_030000.xlsx`

### 16.2 Internal Documentation
- **Reference Implementation**: `scripts/backfill_sector_kis_master.py`
- **Database Schema**: `modules/db_manager_sqlite.py`
- **KIS API Client**: `modules/api_clients/kis_overseas_stock_api.py`
- **Market Adapters**: `modules/market_adapters/us_adapter_kis.py`

### 16.3 Related Documents
- **CLAUDE.md**: Project overview and architecture
- **PHASE6_COMPLETION_REPORT.md**: KIS global integration details
- **GLOBAL_ADAPTER_DESIGN.md**: Adapter pattern implementation

---

## Appendix A: File Size Comparison Edge Cases

### A.1 Edge Case Handling

| Scenario | Remote Size | Local Size | Action | Rationale |
|----------|-------------|------------|--------|-----------|
| **Normal Growth** | 1,200 KB | 1,000 KB | Download | New listings added |
| **Massive Growth** | 2,000 KB | 1,000 KB | Download + Alert | Unusual increase (>20%) |
| **Same Size** | 1,000 KB | 1,000 KB | Skip | No changes detected |
| **Minor Decrease** | 995 KB | 1,000 KB | Download + Verify | Possible delisting or format change |
| **Major Decrease** | 500 KB | 1,000 KB | Alert + Manual Review | Potential corruption or mass delisting |
| **No Local File** | 1,000 KB | None | Download | Initial setup |
| **Zero Remote Size** | 0 KB | 1,000 KB | Skip + Alert | Server error |

### A.2 Validation Rules

```python
def validate_file_size_change(old_size: int, new_size: int) -> Dict:
    """
    Validate file size change and determine action

    Returns:
        {
            'action': 'download' | 'skip' | 'alert',
            'reason': str,
            'severity': 'info' | 'warning' | 'critical'
        }
    """
    if old_size is None or old_size == 0:
        return {'action': 'download', 'reason': 'Initial setup', 'severity': 'info'}

    if new_size == 0:
        return {'action': 'skip', 'reason': 'Invalid remote size', 'severity': 'critical'}

    size_change_pct = ((new_size - old_size) / old_size) * 100

    if abs(size_change_pct) < 0.1:
        # Less than 0.1% change - treat as same
        return {'action': 'skip', 'reason': 'No significant change', 'severity': 'info'}

    if size_change_pct > 0:
        # File grew
        if size_change_pct > 20:
            return {
                'action': 'download',
                'reason': f'Large increase ({size_change_pct:.1f}%)',
                'severity': 'warning'
            }
        else:
            return {
                'action': 'download',
                'reason': f'Normal growth ({size_change_pct:.1f}%)',
                'severity': 'info'
            }
    else:
        # File shrank
        if abs(size_change_pct) > 10:
            return {
                'action': 'alert',
                'reason': f'Major decrease ({size_change_pct:.1f}%)',
                'severity': 'critical'
            }
        else:
            return {
                'action': 'download',
                'reason': f'Minor decrease ({size_change_pct:.1f}%)',
                'severity': 'warning'
            }
```

---

## Appendix B: Master File Format Examples

### B.1 Expected Format (.mst → .txt conversion)

**Example: NASDAQ Master File**
```
# NASDAQ Stock Master File
# Generated: 2025-10-15 06:00:00
# Total Stocks: 3,125
TICKER    NAME                        EXCHANGE    SECTOR                  INDUSTRY
AAPL      Apple Inc.                  NASD        Technology              Computer Hardware
MSFT      Microsoft Corporation       NASD        Technology              Software
GOOGL     Alphabet Inc. Class A       NASD        Technology              Internet Services
AMZN      Amazon.com Inc.             NASD        Consumer Discretionary  E-Commerce
META      Meta Platforms Inc.         NASD        Technology              Social Media
...
```

**Expected Columns**:
1. `TICKER`: Ticker symbol (e.g., AAPL)
2. `NAME`: Company name (e.g., Apple Inc.)
3. `EXCHANGE`: Exchange code (NASD, NYSE, AMEX)
4. `SECTOR`: GICS Level 1 sector
5. `INDUSTRY`: GICS Level 2 industry
6. `STATUS` (optional): Active/Inactive

---

**END OF DESIGN DOCUMENT**
