# Technical Indicator Integration Design - spock_refresh.py

**Date**: 2025-11-14
**Purpose**: Design document for integrating technical indicator calculation logic into spock_refresh.py
**Scope**: ALL refresh modes that include technical indicators (5 modes total)

---

## Executive Summary

This design document outlines the integration of direct technical indicator calculation into spock_refresh.py, replacing the current subprocess-based approach with a more efficient, monitorable, and maintainable solution.

**Key Improvements**:
- ✅ Direct class import instead of subprocess calls
- ✅ Real-time progress monitoring with ETA
- ✅ Support for all 6 markets (KR, HK, US, JP, CN, VN)
- ✅ Incremental vs full calculation modes
- ✅ Enhanced error handling and retry logic
- ✅ Consistent concurrency control with @with_lock decorator
- ✅ **Comprehensive coverage of ALL 5 refresh modes**

---

## Current Implementation Analysis

### 1. Current Architecture (Subprocess-Based)

**File**: `spock_refresh.py`

**All modes currently use subprocess approach**:
```python
# Quick Refresh (Line 1039-1049)
args = ['--steps', 'ohlcv', 'daily_valuation', 'technical_indicators', ...]
run_update_database(args, ...)  # Subprocess call

# Full Refresh (Line 1097-1115)
args = ['--steps', 'tickers', 'ohlcv', 'fundamentals', 'technical_indicators', ...]
run_update_database(args, ...)  # Subprocess call

# Incremental Refresh (Line 1119-1128)
args = ['--steps', 'tickers', 'ohlcv', 'fundamentals', 'technical_indicators', ...]
run_update_database(args, ...)  # Subprocess call

# Custom Refresh (Line 1131-1164)
steps = user_input.split()  # Can include 'technical_indicators'
run_update_database(['--steps'] + steps, ...)  # Subprocess call

# Technical Indicators Only (Line 2634-2694)
args = ['--steps', 'technical_indicators', ...]
run_update_database(args, ...)  # Subprocess call
```

**Limitations (ALL modes)**:
- ❌ No real-time progress monitoring
- ❌ Limited error handling
- ❌ Cannot customize batch size
- ❌ Extra process overhead
- ❌ Difficult to debug

### 2. Target Integration Points (5 Modes)

**1️⃣ Quick Refresh** (Line 1039-1049, Menu Option 1):
- Current: Includes 'technical_indicators' in steps via subprocess
- Target: Direct calculation with incremental mode
- Expected time: 5-10 minutes (incremental)
- Priority: **HIGH** (most frequently used)

**2️⃣ Full Refresh** (Line 1097-1115, Menu Option 2):
- Current: Includes 'technical_indicators' in steps via subprocess
- Target: Direct calculation with full recalculation
- Expected time: 30-60 minutes (full)
- Priority: **HIGH** (critical for data integrity)

**3️⃣ Incremental Refresh** (Line 1119-1128, Menu Option 3):
- Current: Includes 'technical_indicators' in steps via subprocess
- Target: Direct calculation with incremental mode
- Expected time: 10-15 minutes (incremental)
- Priority: **MEDIUM** (similar to Quick Refresh but more comprehensive)

**4️⃣ Custom Refresh** (Line 1131-1164, Menu Option 4):
- Current: User can select 'technical_indicators' step, executes via subprocess
- Target: Detect if 'technical_indicators' in selected steps, apply direct calculation
- Expected time: Varies based on user selection
- Priority: **LOW** (advanced users only, conditional integration)

**5️⃣ Technical Indicators Only** (Line 2634-2694, Menu Option 11):
- Current: Subprocess call to update_database.py
- Target: Enhanced standalone function with multi-region support
- Expected time: Varies by region (2-8 hours for new regions)
- Priority: **HIGH** (dedicated function for indicator calculation)

---

## Proposed Architecture

### 1. Direct Class Import Approach

**Advantages**:
- ✅ Real-time progress updates (ETA, percentage, current ticker)
- ✅ Better error handling with ticker-level retry
- ✅ Configurable batch size (50-200)
- ✅ No subprocess overhead (~10% performance improvement)
- ✅ Easier debugging and testing

**Implementation**:
```python
# Import at top of spock_refresh.py
from scripts.calculate_technical_indicators import TechnicalIndicatorCalculator

# Helper function for direct calculation
def _run_technical_indicators_direct(
    regions: List[str],
    batch_size: int = 100,
    incremental: bool = True,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Run technical indicator calculation directly using TechnicalIndicatorCalculator.

    Args:
        regions: List of regions (KR, HK, US, JP, CN, VN)
        batch_size: Number of tickers per batch (50-200)
        incremental: Only calculate missing indicators vs full recalculation
        dry_run: Preview without execution

    Returns:
        Dict with results: {
            'total_tickers': int,
            'success_count': int,
            'failed_count': int,
            'duration_minutes': float
        }
    """
    db_manager = PostgresDatabaseManager()
    calculator = TechnicalIndicatorCalculator(db_manager)

    results = {}
    for region in regions:
        logger.info(f"Calculating technical indicators for {region}...")
        result = calculator.calculate_all_tickers(
            region=region,
            batch_size=batch_size,
            incremental=incremental,
            dry_run=dry_run
        )
        results[region] = result

        # Progress summary
        logger.info(f"{region} completed: {result['success_count']}/{result['total_tickers']} "
                   f"tickers in {result['duration_minutes']:.1f} minutes")

    return results
```

### 2. Integration into Refresh Modes

#### A. Quick Refresh Enhancement

**Location**: Line 1039-1049

**Current Behavior**:
```python
@with_lock('quick_refresh', timeout=300)
def run_quick_refresh():
    args = [..., '--steps', 'ohlcv', 'daily_valuation', 'technical_indicators', ...]
    run_update_database(args, ...)
```

**Proposed Enhancement**:
```python
@with_lock('quick_refresh', timeout=300)
def run_quick_refresh():
    """Quick refresh - OHLCV + Daily Valuation + Technical Indicators (Incremental)"""
    regions = select_regions(default_regions=['KR'])

    # Phase 1: OHLCV + Daily Valuation (via update_database.py)
    args = [
        '--regions'] + regions + [
        '--steps', 'ohlcv', 'daily_valuation', 'dividend', 'fx_tracking',
        '--incremental',
        '--verbose'
    ]
    run_update_database(args, f'Quick Refresh - Data Update ({", ".join(regions)})')

    # Phase 2: Technical Indicators (direct calculation)
    print("\n" + "=" * 80)
    print("Phase 2: Technical Indicators Calculation (Incremental)")
    print("=" * 80)

    results = _run_technical_indicators_direct(
        regions=regions,
        batch_size=100,
        incremental=True,  # Only calculate missing indicators
        dry_run=False
    )

    # Summary
    total_success = sum(r['success_count'] for r in results.values())
    total_tickers = sum(r['total_tickers'] for r in results.values())
    total_time = sum(r['duration_minutes'] for r in results.values())

    print(f"\n✅ Quick Refresh Complete:")
    print(f"   Regions: {', '.join(regions)}")
    print(f"   Technical Indicators: {total_success}/{total_tickers} tickers")
    print(f"   Total Time: {total_time:.1f} minutes")
```

**Benefits**:
- ✅ Incremental mode only updates missing indicators (~5-10 minutes)
- ✅ Real-time progress monitoring during calculation
- ✅ Faster execution than subprocess approach

#### B. Full Refresh Enhancement

**Location**: Line 1097-1115

**Current Behavior**:
```python
@with_lock('full_refresh', timeout=600)
def run_full_refresh():
    args = [..., '--steps', 'tickers', 'ohlcv', 'fundamentals', 'daily_valuation', 'technical_indicators', ...]
    run_update_database(args, ...)
```

**Proposed Enhancement**:
```python
@with_lock('full_refresh', timeout=600)
def run_full_refresh():
    """Full refresh - All data including technical indicators (Full Recalculation)"""
    regions = select_regions(default_regions=['KR', 'HK'])

    # Phase 1: All data except technical indicators (via update_database.py)
    args = [
        '--regions'] + regions + [
        '--steps', 'tickers', 'ohlcv', 'fundamentals', 'daily_valuation', 'dividend', 'fx_tracking',
        '--verbose'
    ]
    run_update_database(args, f'Full Refresh - Data Update ({", ".join(regions)})')

    # Phase 2: Technical Indicators (direct calculation, full recalculation)
    print("\n" + "=" * 80)
    print("Phase 2: Technical Indicators Calculation (Full Recalculation)")
    print("=" * 80)

    results = _run_technical_indicators_direct(
        regions=regions,
        batch_size=100,
        incremental=False,  # Recalculate all indicators
        dry_run=False
    )

    # Summary
    total_success = sum(r['success_count'] for r in results.values())
    total_tickers = sum(r['total_tickers'] for r in results.values())
    total_time = sum(r['duration_minutes'] for r in results.values())

    print(f"\n✅ Full Refresh Complete:")
    print(f"   Regions: {', '.join(regions)}")
    print(f"   Technical Indicators: {total_success}/{total_tickers} tickers (full recalculation)")
    print(f"   Total Time: {total_time:.1f} minutes")
```

**Benefits**:
- ✅ Full recalculation ensures data consistency
- ✅ Progress monitoring for long-running operations
- ✅ Clear separation between data update and indicator calculation

#### C. Technical Indicators Only Mode Enhancement

**Location**: Line 2634-2694

**Current Behavior**:
```python
def run_technical_indicators_update():
    """Run technical indicators calculation"""
    # Limited to KR, HK, or Both
    # Calls update_database.py via subprocess
```

**Proposed Enhancement**:
```python
@with_lock('technical_indicators', timeout=600)
def run_technical_indicators_update():
    """
    Run technical indicators calculation for selected regions.

    Features:
    - All 6 markets support (KR, HK, US, JP, CN, VN)
    - Incremental vs Full recalculation option
    - Configurable batch size
    - Real-time progress monitoring with ETA
    - Dry-run mode for preview
    """
    print("\n" + "=" * 80)
    print("Technical Indicators Calculation")
    print("=" * 80)

    # Step 1: Region Selection (support all 6 markets)
    print("\nSelect regions for technical indicators calculation:")
    print("1. KR (Korea) - 3,760 tickers ✅ (100% coverage)")
    print("2. HK (Hong Kong) - 2,752 tickers ✅ (100% coverage)")
    print("3. US (United States) - 6,107 tickers ⚠️ (needs calculation)")
    print("4. JP (Japan) - 4,028 tickers ⚠️ (needs calculation)")
    print("5. CN (China) - 2,425 tickers ⚠️ (needs calculation)")
    print("6. VN (Vietnam) - 309 tickers ⚠️ (needs calculation)")
    print("7. All regions (parallel execution recommended)")
    print("8. Custom selection")

    choice = input("\nEnter choice (1-8): ").strip()

    region_map = {
        '1': ['KR'],
        '2': ['HK'],
        '3': ['US'],
        '4': ['JP'],
        '5': ['CN'],
        '6': ['VN'],
        '7': ['KR', 'HK', 'US', 'JP', 'CN', 'VN'],
        '8': None  # Custom selection
    }

    if choice == '8':
        regions = select_regions_custom()
    else:
        regions = region_map.get(choice, ['KR'])

    # Step 2: Calculation Mode
    print("\nCalculation mode:")
    print("1. Incremental (only missing indicators) - Recommended for updates")
    print("2. Full recalculation (all indicators) - Recommended for new regions")

    mode_choice = input("Enter choice (1-2, default=1): ").strip() or '1'
    incremental = (mode_choice == '1')

    # Step 3: Batch Size
    print("\nBatch size (tickers per batch):")
    print("  50 - Conservative (slower, lower memory)")
    print(" 100 - Balanced (recommended)")
    print(" 200 - Aggressive (faster, higher memory)")

    batch_input = input("Enter batch size (default=100): ").strip() or '100'
    batch_size = int(batch_input)

    # Step 4: Dry Run Option
    dry_run_choice = input("\nDry run (preview without execution)? (y/n, default=n): ").strip().lower()
    dry_run = (dry_run_choice == 'y')

    # Summary
    print("\n" + "=" * 80)
    print("Calculation Summary:")
    print("=" * 80)
    print(f"Regions: {', '.join(regions)}")
    print(f"Mode: {'Incremental' if incremental else 'Full Recalculation'}")
    print(f"Batch Size: {batch_size}")
    print(f"Dry Run: {'Yes' if dry_run else 'No'}")

    # Estimate time
    ticker_counts = {
        'KR': 3760, 'HK': 2752, 'US': 6107,
        'JP': 4028, 'CN': 2425, 'VN': 309
    }
    total_tickers = sum(ticker_counts[r] for r in regions)
    estimated_minutes = total_tickers / 10  # ~10 tickers/minute (conservative)

    print(f"\nEstimated time: {estimated_minutes:.0f} minutes ({estimated_minutes/60:.1f} hours)")
    print("=" * 80)

    if not dry_run:
        confirm = input("\nProceed with calculation? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Calculation cancelled.")
            return

    # Execute
    print("\nStarting calculation...")
    start_time = time.time()

    results = _run_technical_indicators_direct(
        regions=regions,
        batch_size=batch_size,
        incremental=incremental,
        dry_run=dry_run
    )

    # Final Summary
    elapsed_minutes = (time.time() - start_time) / 60
    total_success = sum(r['success_count'] for r in results.values())
    total_tickers = sum(r['total_tickers'] for r in results.values())
    total_failed = sum(r['failed_count'] for r in results.values())

    print("\n" + "=" * 80)
    print("✅ Technical Indicators Calculation Complete")
    print("=" * 80)
    print(f"Total Tickers: {total_tickers}")
    print(f"Success: {total_success} ({total_success/total_tickers*100:.1f}%)")
    print(f"Failed: {total_failed}")
    print(f"Total Time: {elapsed_minutes:.1f} minutes ({elapsed_minutes/60:.1f} hours)")
    print("=" * 80)

    # Detailed per-region results
    print("\nPer-Region Results:")
    for region, result in results.items():
        print(f"\n{region}:")
        print(f"  Tickers: {result['total_tickers']}")
        print(f"  Success: {result['success_count']}")
        print(f"  Failed: {result['failed_count']}")
        print(f"  Duration: {result['duration_minutes']:.1f} minutes")
```

**Benefits**:
- ✅ All 6 markets support (KR, HK, US, JP, CN, VN)
- ✅ Incremental vs Full recalculation option
- ✅ Configurable batch size for performance tuning
- ✅ Real-time progress monitoring with ETA
- ✅ Dry-run mode for preview
- ✅ Estimated time calculation based on ticker count
- ✅ Detailed per-region results summary

#### D. Incremental Refresh Enhancement

**Location**: Line 1119-1128, Menu Option 3

**Current Behavior**:
```python
def run_incremental_refresh():
    """Incremental refresh - missing data only"""
    args = [
        '--regions'] + regions + [
        '--steps', 'tickers', 'ohlcv', 'fundamentals', 'daily_valuation', 'technical_indicators', 'dividend', 'fx_tracking',
        '--incremental',
        '--verbose'
    ]
    run_update_database(args, ...)
```

**Proposed Enhancement**:
```python
@with_lock('incremental_refresh', timeout=600)
def run_incremental_refresh():
    """Incremental refresh - Missing data only (all steps including technical indicators)"""
    regions = select_regions(default_regions=['KR'], prompt_message="🔄 Incremental Refresh - Select regions:")

    # Phase 1: All data except technical indicators (via update_database.py)
    args = [
        '--regions'] + regions + [
        '--steps', 'tickers', 'ohlcv', 'fundamentals', 'daily_valuation', 'dividend', 'fx_tracking',
        '--incremental',
        '--verbose'
    ]
    run_update_database(args, f'Incremental Refresh - Data Update ({", ".join(regions)})')

    # Phase 2: Technical Indicators (direct calculation, incremental mode)
    print("\n" + "=" * 80)
    print("Phase 2: Technical Indicators Calculation (Incremental)")
    print("=" * 80)

    results = _run_technical_indicators_direct(
        regions=regions,
        batch_size=100,
        incremental=True,  # Only calculate missing indicators
        dry_run=False
    )

    # Summary
    total_success = sum(r['success_count'] for r in results.values())
    total_tickers = sum(r['total_tickers'] for r in results.values())
    total_time = sum(r['duration_minutes'] for r in results.values())

    print(f"\n✅ Incremental Refresh Complete:")
    print(f"   Regions: {', '.join(regions)}")
    print(f"   Technical Indicators: {total_success}/{total_tickers} tickers")
    print(f"   Total Time: {total_time:.1f} minutes")
```

**Benefits**:
- ✅ Incremental mode only updates missing indicators (~10-15 minutes)
- ✅ More comprehensive than Quick Refresh (includes tickers, fundamentals)
- ✅ Real-time progress monitoring during calculation
- ✅ Consistent with Quick/Full refresh pattern

#### E. Custom Refresh Enhancement (Conditional)

**Location**: Line 1131-1164, Menu Option 4

**Current Behavior**:
```python
def run_custom_refresh():
    """Custom refresh with user input"""
    print("Available: tickers ohlcv fundamentals daily_valuation technical_indicators dividend fx_tracking")
    steps_input = input("Steps [ohlcv fundamentals]: ").strip()
    steps = steps_input.split() if steps_input else ['ohlcv', 'fundamentals']
    # technical_indicators NOT in default
    run_update_database(['--steps'] + steps, ...)
```

**Proposed Enhancement**:
```python
def run_custom_refresh():
    """Custom refresh with user input - smart detection for technical indicators"""
    print(f"\n{colored('⚙️  Custom Refresh', Fore.MAGENTA + Style.BRIGHT)}")
    print("=" * 60)

    # Select regions
    print(f"\n{colored('Select regions (space-separated):', Fore.CYAN)}")
    print("  Available: KR US HK JP CN VN")
    regions_input = input(f"{colored('Regions [KR]:', Fore.CYAN)} ").strip()
    regions = regions_input.split() if regions_input else ['KR']

    # Select steps
    print(f"\n{colored('Select steps (space-separated):', Fore.CYAN)}")
    print("  Available: tickers ohlcv fundamentals daily_valuation technical_indicators dividend fx_tracking")
    steps_input = input(f"{colored('Steps [ohlcv fundamentals]:', Fore.CYAN)} ").strip()
    steps = steps_input.split() if steps_input else ['ohlcv', 'fundamentals']

    # Check if technical_indicators is selected
    has_technical_indicators = 'technical_indicators' in steps

    # Incremental?
    incremental_input = input(f"\n{colored('Incremental mode? [Y/n]:', Fore.CYAN)} ").strip().lower()
    incremental = incremental_input != 'n'

    # Dry run?
    dry_run_input = input(f"{colored('Dry run (preview only)? [y/N]:', Fore.CYAN)} ").strip().lower()
    dry_run = dry_run_input == 'y'

    # Phase 1: All steps except technical_indicators (if technical_indicators selected)
    if has_technical_indicators:
        non_tech_steps = [s for s in steps if s != 'technical_indicators']
        if non_tech_steps:
            args = ['--regions'] + regions + ['--steps'] + non_tech_steps
            if incremental:
                args.append('--incremental')
            if dry_run:
                args.append('--dry-run')
            args.append('--verbose')
            run_update_database(args, f"Custom Refresh - Data Update (regions={regions}, steps={non_tech_steps})")

        # Phase 2: Technical Indicators (direct calculation)
        print("\n" + "=" * 80)
        print("Phase 2: Technical Indicators Calculation")
        print("=" * 80)

        if not dry_run:
            results = _run_technical_indicators_direct(
                regions=regions,
                batch_size=100,
                incremental=incremental,
                dry_run=False
            )

            total_success = sum(r['success_count'] for r in results.values())
            total_tickers = sum(r['total_tickers'] for r in results.values())
            total_time = sum(r['duration_minutes'] for r in results.values())

            print(f"\n✅ Custom Refresh Complete:")
            print(f"   Technical Indicators: {total_success}/{total_tickers} tickers")
            print(f"   Time: {total_time:.1f} minutes")
        else:
            print("(Dry run - technical indicators calculation skipped)")
    else:
        # No technical_indicators selected, use standard subprocess approach
        args = ['--regions'] + regions + ['--steps'] + steps
        if incremental:
            args.append('--incremental')
        if dry_run:
            args.append('--dry-run')
        args.append('--verbose')
        run_update_database(args, f"Custom Refresh (regions={regions}, steps={steps})")
```

**Benefits**:
- ✅ Smart detection of technical_indicators in user selection
- ✅ Applies direct calculation only when needed
- ✅ Consistent Phase 1/2 pattern with other refresh modes
- ✅ No impact on users who don't select technical_indicators
- ✅ Advanced users get progress monitoring when using technical indicators

**Priority**: **LOW** (advanced users, conditional integration)

---

## Implementation Plan

### Phase 1: Core Integration (Week 1)
1. **Import TechnicalIndicatorCalculator** (Line ~20)
   ```python
   from scripts.calculate_technical_indicators import TechnicalIndicatorCalculator
   ```

2. **Add Helper Function** (Line ~1000, before refresh functions)
   ```python
   def _run_technical_indicators_direct(
       regions: List[str],
       batch_size: int = 100,
       incremental: bool = True,
       dry_run: bool = False
   ) -> Dict[str, Any]:
       """Direct technical indicator calculation with progress monitoring"""
       # Implementation as outlined above
   ```

3. **Add Custom Region Selection** (Line ~2600, before run_technical_indicators_update)
   ```python
   def select_regions_custom() -> List[str]:
       """Interactive custom region selection"""
       available = ['KR', 'HK', 'US', 'JP', 'CN', 'VN']
       selected = []

       print("\nSelect regions (space-separated): KR HK US JP CN VN")
       print("Examples:")
       print("  KR HK          - Korea and Hong Kong")
       print("  US JP CN       - United States, Japan, and China")
       print("  ALL            - All regions")

       input_str = input("\nEnter regions: ").strip().upper()

       if input_str == 'ALL':
           return available

       for region in input_str.split():
           if region in available and region not in selected:
               selected.append(region)

       return selected if selected else ['KR']  # Default to KR
   ```

### Phase 2: Quick Refresh Integration (Week 1)
1. **Modify run_quick_refresh()** (Line 1039-1049)
   - Remove 'technical_indicators' from update_database.py steps
   - Add Phase 2 with direct calculation (incremental mode)
   - Add progress monitoring and summary

### Phase 3: Full Refresh Integration (Week 1)
1. **Modify run_full_refresh()** (Line 1097-1115)
   - Remove 'technical_indicators' from update_database.py steps
   - Add Phase 2 with direct calculation (full recalculation)
   - Add progress monitoring and summary

### Phase 4: Incremental Refresh Integration (Week 1)
1. **Modify run_incremental_refresh()** (Line 1119-1128)
   - Remove 'technical_indicators' from update_database.py steps
   - Add Phase 2 with direct calculation (incremental mode)
   - Add progress monitoring and summary
   - Consistent with Quick/Full refresh pattern

### Phase 5: Custom Refresh Integration (Week 2)
1. **Modify run_custom_refresh()** (Line 1131-1164)
   - Add smart detection for 'technical_indicators' in user selection
   - Split into Phase 1 (non-tech steps) + Phase 2 (technical indicators) when applicable
   - Apply direct calculation only if technical_indicators selected
   - Maintain backward compatibility for users who don't select technical_indicators

### Phase 6: Enhanced Technical Indicators Only Mode (Week 2)
1. **Replace run_technical_indicators_update()** (Line 2634-2694)
   - Complete rewrite with enhanced features
   - All 6 markets support
   - Incremental vs Full option
   - Batch size configuration
   - Dry-run mode
   - Estimated time calculation
   - Detailed results summary

### Phase 7: Testing and Validation (Week 2)
1. **Unit Tests**
   - Test _run_technical_indicators_direct() with mock data
   - Test region selection logic
   - Test batch size configuration
   - Test incremental vs full mode
   - Test smart detection in Custom Refresh

2. **Integration Tests (All 5 Modes)**
   - **Quick Refresh**: Test with small dataset (KR, 10 tickers, incremental)
   - **Full Refresh**: Test with small dataset (KR, 10 tickers, full recalculation)
   - **Incremental Refresh**: Test with small dataset (KR, 10 tickers, incremental)
   - **Custom Refresh**: Test with and without technical_indicators selection
   - **Technical Indicators Only**: Test with all options (region selection, batch size, dry-run)
   - Validate progress monitoring and ETA accuracy across all modes

3. **Performance Tests**
   - Benchmark batch sizes (50, 100, 200) on 1000 tickers
   - Measure incremental vs full recalculation time
   - Validate memory usage with large datasets (US, 6107 tickers)
   - Compare subprocess vs direct calculation performance (expected 10-20% improvement)

---

## Configuration and Performance Tuning

### Batch Size Recommendations

| Market | Tickers | Recommended Batch | Estimated Time (Incremental) | Estimated Time (Full) |
|--------|---------|-------------------|------------------------------|----------------------|
| KR | 3,760 | 100 | 10-15 minutes | 30-40 minutes |
| HK | 2,752 | 100 | 8-12 minutes | 25-35 minutes |
| US | 6,107 | 100 | 15-20 minutes | 60-90 minutes |
| JP | 4,028 | 100 | 10-15 minutes | 40-60 minutes |
| CN | 2,425 | 100 | 8-12 minutes | 25-35 minutes |
| VN | 309 | 50 | 2-3 minutes | 5-8 minutes |

**Batch Size Guidelines**:
- **50**: Conservative, best for low-memory environments or unstable connections
- **100**: Balanced, recommended for most use cases (good speed + stability)
- **200**: Aggressive, best for high-memory environments + stable connections (20-30% faster)

### Concurrency Control

**Existing @with_lock Decorator**:
```python
@with_lock('technical_indicators', timeout=600)
def run_technical_indicators_update():
    """Prevents concurrent technical indicator calculations"""
    # Implementation
```

**Lock Timeout Recommendations**:
- Quick refresh: 300 seconds (5 minutes) - adequate for incremental updates
- Full refresh: 600 seconds (10 minutes) - adequate for small regions
- Technical indicators only: 3600 seconds (60 minutes) - for large multi-region calculations

---

## Error Handling and Retry Logic

### Ticker-Level Error Handling

**Current Implementation** (calculate_technical_indicators.py):
```python
def calculate_all_tickers(self, region: str, batch_size: int = 50):
    for ticker in tickers:
        try:
            self.calculate_indicators_for_ticker(ticker, region)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to calculate for {ticker}: {e}")
            failed_count += 1
```

**Enhanced Error Handling**:
```python
def calculate_all_tickers(self, region: str, batch_size: int = 50, max_retries: int = 3):
    for ticker in tickers:
        retries = 0
        while retries < max_retries:
            try:
                self.calculate_indicators_for_ticker(ticker, region)
                success_count += 1
                break
            except Exception as e:
                retries += 1
                if retries >= max_retries:
                    logger.error(f"Failed to calculate for {ticker} after {max_retries} retries: {e}")
                    failed_tickers.append((ticker, str(e)))
                    failed_count += 1
                else:
                    logger.warning(f"Retry {retries}/{max_retries} for {ticker}")
                    time.sleep(1)  # Brief delay before retry
```

### Progress Monitoring

**Real-Time Progress Updates**:
```python
def calculate_all_tickers(self, region: str, batch_size: int = 50):
    total = len(tickers)
    start_time = time.time()

    for idx, ticker in enumerate(tickers, 1):
        # Calculate indicators
        # ...

        # Progress update every batch
        if idx % batch_size == 0:
            elapsed = time.time() - start_time
            rate = idx / elapsed  # tickers per second
            remaining = (total - idx) / rate  # estimated seconds remaining

            print(f"Progress: {idx}/{total} ({idx/total*100:.1f}%) | "
                  f"Rate: {rate*60:.1f} tickers/min | "
                  f"ETA: {remaining/60:.0f} minutes")
```

---

## Migration Path

### Step 1: Backup Current Implementation
```bash
# Backup spock_refresh.py before modifications
cp spock_refresh.py spock_refresh.py.backup_20251114
```

### Step 2: Implement Changes
1. Add imports and helper functions
2. Modify Quick refresh
3. Modify Full refresh
4. Replace Technical indicators only mode

### Step 3: Testing Phase
1. Test with small dataset (KR, 10 tickers)
2. Validate incremental mode
3. Validate full recalculation mode
4. Test all 6 markets

### Step 4: Production Deployment
1. Execute technical indicators calculation for US, JP, CN, VN
2. Monitor performance and errors
3. Adjust batch sizes if needed

### Step 5: Documentation
1. Update spock_refresh.py docstrings
2. Update user guide
3. Document configuration options

---

## Success Metrics

### Performance Targets
- ✅ Quick refresh (incremental): 5-10 minutes for KR/HK
- ✅ Full refresh (full recalculation): 30-40 minutes for KR/HK
- ✅ Technical indicators only: <2 hours for single large market (US)
- ✅ Progress monitoring: Updates every 100 tickers (<30s intervals)
- ✅ Error rate: <1% failed tickers (with 3 retries)

### User Experience Targets
- ✅ Real-time progress with ETA
- ✅ Clear error messages with retry information
- ✅ Detailed results summary with per-region breakdown
- ✅ Configurable batch size for performance tuning
- ✅ Dry-run mode for safe previewing

### Code Quality Targets
- ✅ DRY principle: Single _run_technical_indicators_direct() helper
- ✅ Consistent error handling across all modes
- ✅ Comprehensive logging for debugging
- ✅ Clear separation of concerns (data update vs indicator calculation)

---

## Appendix A: Code Examples

### Example 1: Quick Refresh with Technical Indicators
```bash
# User workflow
$ python3 spock_refresh.py

Menu:
1. Quick Refresh
...

Enter choice: 1

Select regions (default: KR):
1. KR
2. HK
3. KR + HK
...

Enter choice: 1

# Execution
Phase 1: Data Update (OHLCV, Daily Valuation)
...

Phase 2: Technical Indicators Calculation (Incremental)
Calculating technical indicators for KR...
Progress: 100/3760 (2.7%) | Rate: 120 tickers/min | ETA: 30 minutes
Progress: 200/3760 (5.3%) | Rate: 125 tickers/min | ETA: 28 minutes
...
Progress: 3760/3760 (100.0%) | Rate: 130 tickers/min | ETA: 0 minutes

✅ Quick Refresh Complete:
   Regions: KR
   Technical Indicators: 3760/3760 tickers
   Total Time: 8.5 minutes
```

### Example 2: Technical Indicators Only - Multi-Region
```bash
$ python3 spock_refresh.py

Menu:
...
8. Technical Indicators Only

Enter choice: 8

Select regions:
1. KR
2. HK
3. US
4. JP
5. CN
6. VN
7. All regions
8. Custom selection

Enter choice: 7

Calculation mode:
1. Incremental (only missing indicators)
2. Full recalculation (all indicators)

Enter choice: 2

Batch size (default=100): 100

Dry run? (y/n): n

Calculation Summary:
Regions: KR, HK, US, JP, CN, VN
Mode: Full Recalculation
Batch Size: 100
Estimated time: 394 minutes (6.6 hours)

Proceed with calculation? (y/n): y

# Execution with real-time monitoring
Starting calculation for KR...
Progress: 100/3760 (2.7%) | Rate: 120 tickers/min | ETA: 30 minutes
...

Starting calculation for HK...
...

✅ Technical Indicators Calculation Complete
Total Tickers: 21,381
Success: 21,315 (99.7%)
Failed: 66
Total Time: 385.2 minutes (6.4 hours)

Per-Region Results:
KR: 3760 tickers, 3755 success, 5 failed, 29.5 minutes
HK: 2752 tickers, 2750 success, 2 failed, 21.8 minutes
US: 6107 tickers, 6090 success, 17 failed, 95.3 minutes
JP: 4028 tickers, 4020 success, 8 failed, 63.2 minutes
CN: 2425 tickers, 2420 success, 5 failed, 38.1 minutes
VN: 309 tickers, 280 success, 29 failed, 4.8 minutes
```

---

## Appendix B: Database Schema Impact

No database schema changes required. The integration uses existing:
- `technical_analysis` table
- `ohlcv_data` table (source data)

**Existing Schema** (QUANT_DATABASE_SCHEMA.md):
```sql
CREATE TABLE technical_analysis (
    ticker TEXT NOT NULL,
    region TEXT NOT NULL,
    date DATE NOT NULL,
    ma5 NUMERIC,
    ma20 NUMERIC,
    ma60 NUMERIC,
    ma120 NUMERIC,
    ma200 NUMERIC,
    rsi_14 NUMERIC,
    macd NUMERIC,
    macd_signal NUMERIC,
    macd_hist NUMERIC,
    PRIMARY KEY (ticker, region, date)
);
```

---

## Conclusion

This design provides a comprehensive solution for integrating technical indicator calculation into **ALL 5 refresh modes** in spock_refresh.py with:

1. **Comprehensive Coverage**: All 5 refresh modes updated (Quick, Full, Incremental, Custom, Technical Indicators Only)
2. **Enhanced User Experience**: Real-time progress, ETA, configurable options across all modes
3. **Better Performance**: Direct class import, configurable batch sizes, parallel execution support
4. **Improved Maintainability**: DRY principle, consistent error handling, clear separation of concerns
5. **Production Ready**: Retry logic, detailed logging, comprehensive testing

**Integration Summary**:

| Mode | Priority | Approach | Expected Time Saving |
|------|----------|----------|---------------------|
| 1️⃣ Quick Refresh | **HIGH** | Phase 1+2 pattern, incremental | ~10-15% faster |
| 2️⃣ Full Refresh | **HIGH** | Phase 1+2 pattern, full recalculation | ~10-15% faster |
| 3️⃣ Incremental Refresh | **MEDIUM** | Phase 1+2 pattern, incremental | ~10-15% faster |
| 4️⃣ Custom Refresh | **LOW** | Smart detection, conditional integration | ~10-15% faster (when tech indicators selected) |
| 5️⃣ Technical Indicators Only | **HIGH** | Complete rewrite, multi-region support | Real-time progress monitoring |

**Next Steps**:
1. ✅ Review and approve design (5 modes)
2. ⏳ Implement Phase 1-3: Core + Quick + Full + Incremental (Week 1)
3. ⏳ Implement Phase 4-6: Custom + Technical Only (Week 2)
4. ⏳ Implement Phase 7: Testing all 5 modes (Week 2)
5. ⏳ Deploy to production
6. ⏳ Execute technical indicators calculation for US, JP, CN, VN markets

**Estimated Implementation Time**: 2 weeks
- **Week 1**: Core integration + 3 high-priority modes (Quick, Full, Incremental)
- **Week 2**: Custom mode + Enhanced Technical Only mode + Comprehensive testing

**Code Changes Summary**:
- **New code**: ~200 lines (helper functions + region selection)
- **Modified code**: ~150 lines (5 refresh functions)
- **Total impact**: ~350 lines across 1 file (spock_refresh.py)

---

**Document Version**: 2.0 (Updated with 5 modes)
**Author**: Claude Code
**Last Updated**: 2025-11-14
**Changelog**:
- v1.0 (2025-11-14): Initial design with 3 modes
- v2.0 (2025-11-14): Expanded to cover ALL 5 refresh modes (added Incremental + Custom)
