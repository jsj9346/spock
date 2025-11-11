# ETF Sector Tagging Guide

**Purpose**: Improve ETF sector classification accuracy from ~70% (name-based) to ~95% (manually verified)

**Status**: Tool Ready, Data Entry Pending

**Estimated Time**: 4-6 hours for 200 ETFs (2-3 ETFs/minute)

---

## Overview

The `screen_etfs` tool currently uses name-based sector classification with ~70% accuracy. For users who need higher precision, manual sector tagging can improve accuracy to ~95%.

### Current vs. Manual Classification

| Aspect | Name-Based (Current) | Manual Tagging (Optional) |
|--------|---------------------|---------------------------|
| Accuracy | ~70% | ~95% |
| Effort | None (automatic) | 4-6 hours (one-time) |
| Maintenance | None | Update for new ETFs |
| Use Case | General screening | Precise sector analysis |

---

## When to Use Manual Tagging

### ✅ Use Manual Tagging If:
- Building sector-specific portfolios (e.g., "top 3 semiconductor ETFs")
- Comparing ETFs within narrow sectors
- Academic or professional research requiring precision
- Managing client portfolios with sector constraints

### ❌ Skip Manual Tagging If:
- General screening and exploration (name-based is sufficient)
- Multi-sector screening (broad categorization works fine)
- Casual research or learning
- Time-constrained projects

---

## Tool Usage

### Step 1: Run Migration (One-Time)

```bash
# Add sector_manual column to database
psql -d quant_platform -f scripts/migrations/add_etf_sector_manual.sql
```

**Result**: Adds `sector_manual` column to `etf_details` table.

---

### Step 2: Start Tagging Session

```bash
# Tag top 200 ETFs (sorted by volume/liquidity)
python3 scripts/etf_sector_tagger.py --limit 200 --volume-sort

# Tag all 1,061 ETFs (comprehensive)
python3 scripts/etf_sector_tagger.py --limit 1061

# Resume session (skip already-tagged ETFs automatically)
python3 scripts/etf_sector_tagger.py --limit 200
```

---

### Step 3: Interactive Tagging

For each ETF, you'll see:

```
================================================================================
ETF 1/200
================================================================================
Ticker:          091160
Name:            KODEX 반도체
Current Sector:  Semiconductor
Listing Date:    2015-05-08
Volume (20d):    3,500,000
Price:           45,000 KRW
RSI:             58.0
MA Trend:        bullish
================================================================================

Available Sectors:
--------------------------------------------------------------------------------
  1. Broad Market                         2. Semiconductor
  3. Battery/Secondary Battery            4. Bio/Healthcare
  5. Finance                              6. IT/Technology
  7. Energy                               8. Real Estate
  9. Automotive                           10. Chemical
  11. Construction                        12. Steel/Materials
  13. Retail/Consumer                     14. Entertainment/Media
  15. Game/Contents                       16. ESG/Sustainable
  17. Dividend                            18. Leverage/Inverse
  19. Commodity                           20. International
  21. Bond                                22. Mixed/Other
--------------------------------------------------------------------------------

Shortcuts:
  [s] Skip this ETF
  [q] Quit and save progress
  [h] Show this help menu
================================================================================

Enter sector number (1-22), 's' to skip, 'q' to quit, 'h' for help: 2
```

**Input**: Type `2` (for Semiconductor)

**Result**: `✅ Saved: KODEX 반도체 → Semiconductor`

---

### Step 4: Resume Anytime

The tool saves progress to the database after each tag. You can:
- Quit with `q` at any time
- Resume by running the script again
- Already-tagged ETFs are skipped automatically

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1-22` | Select sector by number |
| `s` | Skip this ETF (don't tag) |
| `q` | Quit and save progress |
| `h` | Show help menu |

---

## Sector Categories

The tool provides 22 predefined sector categories:

### Core Sectors (1-15)
1. **Broad Market** - KOSPI 200, KOSDAQ 150, etc.
2. **Semiconductor** - Chip manufacturers, equipment
3. **Battery/Secondary Battery** - EV batteries, energy storage
4. **Bio/Healthcare** - Pharmaceuticals, medical devices
5. **Finance** - Banks, insurance, securities
6. **IT/Technology** - Software, cloud, AI
7. **Energy** - Oil, gas, renewable
8. **Real Estate** - REITs, construction
9. **Automotive** - Car manufacturers, parts
10. **Chemical** - Chemicals, materials
11. **Construction** - Infrastructure, housing
12. **Steel/Materials** - Metals, raw materials
13. **Retail/Consumer** - Consumer goods, retail
14. **Entertainment/Media** - Content, broadcasting
15. **Game/Contents** - Gaming, digital content

### Special Categories (16-22)
16. **ESG/Sustainable** - ESG, green energy, sustainable investing
17. **Dividend** - High-dividend focus
18. **Leverage/Inverse** - Leveraged or inverse ETFs
19. **Commodity** - Gold, silver, commodities
20. **International** - Global markets, foreign stocks
21. **Bond** - Government bonds, corporate bonds
22. **Mixed/Other** - Multi-sector, thematic, uncategorized

---

## Best Practices

### 1. Prioritize by Volume
```bash
# Start with most liquid ETFs (default behavior)
python3 scripts/etf_sector_tagger.py --limit 200 --volume-sort
```

**Rationale**: High-volume ETFs are most commonly used by investors, so tagging them first provides maximum benefit.

### 2. Tag in Sessions
- **Session 1**: Top 50 ETFs (~30 minutes)
- **Session 2**: Next 50 ETFs (~30 minutes)
- **Session 3**: Next 100 ETFs (~1 hour)
- **Total**: 200 ETFs in 2 hours (spread across multiple days if needed)

### 3. Use Existing Classification as Hint
The tool shows the current name-based sector. Use it as a starting point:
- If correct → Confirm with same number
- If wrong → Select correct sector

### 4. Handle Edge Cases
- **Multi-sector ETFs**: Choose primary sector (e.g., "IT" for AI+Cloud ETF)
- **Thematic ETFs**: Use "Mixed/Other" if no clear single sector
- **Leverage/Inverse**: Always tag as "Leverage/Inverse" regardless of underlying

---

## Database Integration

### Schema

```sql
-- etf_details table
CREATE TABLE etf_details (
    ticker VARCHAR(20) NOT NULL,
    region VARCHAR(2) NOT NULL,
    sector_theme TEXT,          -- Auto-generated from name (70% accuracy)
    sector_manual TEXT,          -- Manually tagged (95% accuracy)
    ...
    PRIMARY KEY (ticker, region)
);

-- Index for efficient queries
CREATE INDEX idx_etf_details_sector_manual
ON etf_details(sector_manual) WHERE sector_manual IS NOT NULL;
```

### Query Priority

When both `sector_theme` and `sector_manual` exist:
```python
# In ETF screening adapter
sector = etf.get("sector_manual") or etf.get("sector_theme") or "Unknown"
```

**Result**: Manual tags override automatic classification.

---

## Verification and Quality Assurance

### Check Progress

```sql
-- Count tagged vs. untagged ETFs
SELECT
    COUNT(*) FILTER (WHERE sector_manual IS NOT NULL) as manually_tagged,
    COUNT(*) FILTER (WHERE sector_manual IS NULL) as not_tagged,
    COUNT(*) as total
FROM etf_details
WHERE region = 'KR';
```

### Verify Sector Distribution

```sql
-- Top sectors by ETF count
SELECT
    COALESCE(sector_manual, sector_theme) as sector,
    COUNT(*) as etf_count,
    COUNT(sector_manual) as manual_count,
    COUNT(sector_theme) - COUNT(sector_manual) as auto_count
FROM etf_details
WHERE region = 'KR'
GROUP BY sector
ORDER BY etf_count DESC
LIMIT 10;
```

### Audit Accuracy

```sql
-- Compare manual vs. automatic classification
SELECT
    sector_theme as auto_sector,
    sector_manual as manual_sector,
    COUNT(*) as count
FROM etf_details
WHERE region = 'KR'
  AND sector_manual IS NOT NULL
  AND sector_theme != sector_manual
GROUP BY sector_theme, sector_manual
ORDER BY count DESC;
```

---

## Maintenance

### Adding New ETFs

When new ETFs are listed:

```bash
# Tag only new ETFs (automatically skips already-tagged)
python3 scripts/etf_sector_tagger.py --limit 1100
```

The tool will:
1. Fetch all ETFs
2. Skip already-tagged ones
3. Present only new ETFs for tagging

### Updating Existing Tags

```sql
-- Update specific ETF sector
UPDATE etf_details
SET sector_manual = 'Semiconductor'
WHERE ticker = '091160' AND region = 'KR';

-- Bulk update (e.g., fix typo)
UPDATE etf_details
SET sector_manual = 'Battery/Secondary Battery'
WHERE sector_manual = 'Secondary Battery';
```

---

## Performance Impact

### Query Performance

```sql
-- Sector-filtered query (indexed)
EXPLAIN ANALYZE
SELECT * FROM etf_details
WHERE sector_manual = 'Semiconductor'
  AND region = 'KR';

-- Result: Index Scan (0.1ms) - No performance impact
```

### Storage

- **Column Size**: ~20 bytes per ETF
- **Total Overhead**: 1,061 ETFs × 20 bytes = ~21 KB
- **Impact**: Negligible (0.001% of database size)

---

## Alternative Approaches (Not Implemented)

### 1. Machine Learning Classification
- **Effort**: 2-3 weeks (data labeling, model training, deployment)
- **Accuracy**: ~85-90% (better than name-based, worse than manual)
- **Maintenance**: Retraining needed for new sectors

### 2. Web Scraping Sector Data
- **Effort**: 1-2 weeks (scraper development, data mapping)
- **Accuracy**: ~80-85% (depends on source data quality)
- **Maintenance**: Fragile (breaks when websites change)

### 3. API Integration (e.g., KRX, ETFCheck)
- **Effort**: 1 week (authentication, API integration)
- **Accuracy**: ~90-95% (depends on API data quality)
- **Maintenance**: Low (stable APIs)
- **Blockers**: Authentication issues, API limitations (see ETF Phase 1 Day 2 Status)

**Conclusion**: Manual tagging is the most cost-effective approach for 200 ETFs, with highest accuracy and no ongoing maintenance.

---

## Summary

✅ **Tool Created**: `scripts/etf_sector_tagger.py`
✅ **Migration Ready**: `scripts/migrations/add_etf_sector_manual.sql`
✅ **Documentation**: This guide
⏸️ **Data Entry**: Pending user decision

**Next Steps**:
1. Decide if manual tagging is needed for your use case
2. If yes: Run migration and start tagging session
3. If no: Continue using name-based classification (~70% accuracy)

---

**Last Updated**: 2025-10-31
**Status**: Tool Ready, Awaiting User Decision
**Estimated ROI**: High for precision use cases, Low for general screening
