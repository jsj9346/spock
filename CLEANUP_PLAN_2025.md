# Comprehensive Cleanup Plan 2025
**Analysis Date**: 2025-11-03
**Previous Cleanup**: 2025-10-26 (193MB recovered)
**Current Disk Usage**: logs/ (971MB), docs/ (6.2MB), archive/ (920KB)

---

## 📊 Executive Summary

### Cleanup Potential
| Category | Size | Files | Risk | Priority | Estimated Recovery |
|----------|------|-------|------|----------|-------------------|
| Large Log Files (>50MB) | ~900MB | 13 files | LOW | **P0** | ~900MB |
| Empty Log Files | ~0MB | 20+ files | ZERO | **P1** | Negligible |
| Old Log Files (7-30d) | ~70MB | 107 files | LOW | **P1** | ~70MB |
| Python Cache | ~5MB | Many dirs | ZERO | **P1** | ~5MB |
| Completion Reports | ~2MB | 71 files | MEDIUM | **P2** | ~2MB |
| Root Test Files | ~50KB | 7 files | ZERO | **P1** | 0MB (relocate) |
| macOS Metadata | ~10KB | 2 files | ZERO | **P1** | Negligible |
| Week/Phase Scripts | ~500KB | 13+ files | MEDIUM | **P3** | ~500KB |
| **TOTAL POTENTIAL** | **~975MB** | **230+ files** | - | - | **~975MB** |

---

## 🎯 Priority 0: Large Log Files (HIGH IMPACT, LOW RISK)

### Target: ~900MB Recovery

**Large Backfill Logs (>50MB)** - Completed operations, no longer needed:

```bash
# Top 10 Largest Log Files (Total: ~900MB)
227M  logs/20251027_backfill_kr_ohlcv_pykrx.log          # Week 3 backfill
191M  logs/20251022_backfill_fundamentals_pykrx.log      # Fundamentals backfill
166M  logs/backfill_kr_week3_full_universe.log           # Week 3 full universe
64M   logs/pykrx_production_backfill_RESTART.log         # Production restart
62M   logs/backfill_kr_ohlcv_week3.log                   # Week 3 OHLCV
39M   logs/20251023_backfill_kr_ohlcv_pykrx.log          # October 23 backfill
38M   logs/ohlcv_backfill_2020_2023_20251024_133013.log  # 2020-2023 backfill
38M   logs/20251024_backfill_kr_ohlcv_pykrx.log          # October 24 backfill
27M   logs/ohlcv_backfill_20251023_142636.log            # October 23 OHLCV
23M   logs/20251021_backfill_fundamentals_pykrx.log      # October 21 fundamentals
```

**Recommended Actions**:
1. **Archive Strategy**: Compress logs older than 7 days
   ```bash
   # Archive large logs (>10MB, older than 7 days)
   find logs -name "*.log" -size +10M -mtime +7 -exec gzip {} \;
   ```

2. **Safe Deletion**: Remove compressed archives after 30 days
   ```bash
   # Delete old compressed logs (after verification)
   find logs -name "*.log.gz" -mtime +30 -delete
   ```

3. **Immediate Safe Deletion** (after verification):
   - Backfill logs from October 21-28 (backfill operations completed)
   - Week 3 completion logs (phase completed per CLAUDE.md)
   - Production restart logs (system stable)

**Risk Assessment**: **LOW** ✅
- All operations completed successfully
- Data safely stored in PostgreSQL database
- Logs are diagnostic only, not operational
- Recent logs (<7 days) preserved

---

## 🎯 Priority 1: Quick Wins (IMMEDIATE, ZERO RISK)

### 1. Empty Log Files (20+ files)
**Space**: Negligible
**Risk**: ZERO ✅

```bash
# Empty log files - safe to delete
logs/20251007_spock.log                                    0B
logs/20251008_spock.log                                    0B
logs/20251009_spock.log                                    0B
logs/20251010_spock.log                                    0B
logs/20251014_etf_aum_backfill.log                         0B
logs/20251016_stock_sentiment.log                          0B
logs/20251017_etf_null_fix.log                             0B
logs/20251019_stock_sentiment.log                          0B
logs/20251029_backfill_kr_ohlcv_pykrx.log                  0B
logs/20251030_stock_sentiment.log                          0B
logs/20251101_backfill_fundamentals_dart.log               0B
logs/20251102_collect_ohlcv_orchestrated.log               0B
logs/us_adapter_deploy_20251015_145814.log                 0B
logs/us_adapter_deploy_20251015_145820.log                 0B
logs/us_adapter_deploy_20251015_152718.log                 0B
logs/us_adapter_deploy_20251019_180023.log                 0B
# ... and more
```

**Action**:
```bash
# Find and delete all empty log files
find logs -name "*.log" -size 0 -delete
```

---

### 2. Python Cache Files
**Space**: ~5MB
**Risk**: ZERO ✅ (auto-regenerated)

**Target Directories**:
```
tests/backtesting/optimization/__pycache__/
tests/backtesting/__pycache__/
tests/backtesting/data_providers/__pycache__/
tests/backtesting/validation/__pycache__/
# ... and more throughout the project
```

**Action**:
```bash
# Remove all Python cache files and directories
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
find . -type f -name "*.pyo" -delete
```

**Add to .gitignore** (if not already present):
```gitignore
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
```

---

### 3. macOS Metadata Files
**Space**: ~10KB
**Risk**: ZERO ✅

```bash
# Find and remove .DS_Store files (2 found)
find . -name ".DS_Store" -delete
```

**Add to .gitignore**:
```gitignore
.DS_Store
.AppleDouble
.LSOverride
```

---

### 4. Root Directory Test Files
**Space**: Negligible (but improves organization)
**Risk**: ZERO ✅ (relocate, not delete)

**Files to Relocate**:
```
test_cli_login.py              → tests/cli/
test_screening_production.py   → tests/screening/
test_technical_filter_fix.py   → tests/filters/
test_get_technical_indicators.py → tests/indicators/
test_etf_screening.py          → tests/etf/
test_etf_scorer.py             → tests/etf/
test_tracking_error.py         → tests/etf/
```

**Action**:
```bash
# Create target directories if needed
mkdir -p tests/cli tests/screening tests/filters tests/indicators tests/etf

# Move files (with git mv for tracked files)
git mv test_cli_login.py tests/cli/
git mv test_screening_production.py tests/screening/
git mv test_technical_filter_fix.py tests/filters/
git mv test_get_technical_indicators.py tests/indicators/
git mv test_etf_screening.py tests/etf/
git mv test_etf_scorer.py tests/etf/
git mv test_tracking_error.py tests/etf/
```

---

## 🎯 Priority 2: Documentation Consolidation (MEDIUM RISK)

### Target: ~2MB, 71+ Completion Reports

**Context**: Previous cleanup (2025-10-26) archived 8 historical reports. Many completion reports remain from completed phases.

**Current Focus** (per CLAUDE.md):
- Phase 0.2: Code stabilization (COMPLETE)
- Phase 1: Backtesting engine (IN PROGRESS)
- Phase 2+: Future work

**Completion Reports Candidates for Archival** (71 files):

#### Category A: Pre-Phase 0 Historical Reports (SAFE TO ARCHIVE)
```markdown
# Phase 1 Legacy (Completed)
docs/PHASE1_BACKTEST_ENGINE_EXECUTION_PLAN.md
docs/PHASE1_DATABASE_MIGRATION_DESIGN.md
docs/PHASE1_ETF_HOLDINGS_COMPLETION_REPORT.md
docs/PHASE1_GLOBAL_OHLCV_FILTERING_COMPLETION_REPORT.md
docs/PHASE1_WEEK1_COMPLETION_REPORT.md
docs/PHASE1.5_COMPLETION_REPORT.md
docs/PHASE1.5_FUNDAMENTAL_DATA_BACKFILL.md

# Weekly Completion Reports (Completed)
docs/WEEK1_COMPLETION_REPORT.md
docs/WEEK1_FOUNDATION_COMPLETION_REPORT.md
docs/WEEK1_LOT_SIZE_COMPLETION_REPORT.md
docs/WEEK1_SCHEMA_COMPLETION_REPORT.md
docs/WEEK2_COMPLETION_REPORT.md
docs/WEEK2_LOT_SIZE_COMPLETION_REPORT.md
docs/WEEK2_VALUE_FACTORS_COMPLETION_REPORT.md
docs/WEEK4_COMPLETION_REPORT.md
docs/WEEK5_PHASE0_COMPLETION_REPORT.md
docs/WEEK5_PHASE1_COMPLETION_REPORT.md
docs/WEEK7_PARAMETER_OPTIMIZER_COMPLETION_REPORT.md

# Task-Specific Completion Reports (Completed)
docs/TASK_2.1_COMPLETION_REPORT.md
docs/TASK_2.2_COMPLETION_REPORT.md
docs/TASK_2.3_COMPLETION_REPORT.md
docs/TASK_2.4_COMPLETION_REPORT.md
docs/TASK_3.1_E2E_TESTING_COMPLETION_REPORT.md

# Day-Specific Completion Reports (Completed)
docs/DAY1_MORNING_COMPLETION_REPORT.md
docs/DAY1_AFTERNOON_COMPLETION_REPORT.md
docs/DAY3_COMPLETION_REPORT.md
docs/DAY4_COMPLETION_REPORT.md
docs/DAY5_MIGRATION_SCRIPT_COMPLETION.md
docs/DAY5_FINAL_MIGRATION_STATUS.md

# Phase 2-6 Completion Reports (Completed)
docs/PHASE2_TER_COMPLETION_REPORT.md
docs/PHASE2_JP_LOT_SIZE_COMPLETION_REPORT.md
docs/PHASE3_COMPLETION_REPORT.md
docs/PHASE3_AUTO_CLEANUP_COMPLETION_REPORT.md
docs/PHASE3_PERFORMANCE_OPTIMIZATION_COMPLETION_REPORT.md
docs/PHASE4_JP_COMPLETION_REPORT.md
docs/PHASE5_VN_COMPLETION_REPORT.md
docs/PHASE6_COMPLETION_REPORT.md
docs/PHASE_1.5_COMPLETION_REPORT.md

# Feature-Specific Completion Reports (Completed)
docs/DART_REPORT_PRIORITY_COMPLETION_REPORT.md
docs/DATABASE_MAINTENANCE_COMPLETION_SUMMARY.md
docs/EXCHANGE_RATE_MANAGER_COMPLETION_REPORT.md
docs/FULL_MIGRATION_COMPLETION_REPORT.md
docs/HISTORICAL_FUNDAMENTAL_COMPLETION_REPORT.md
docs/HK_LOT_SIZE_FIX_COMPLETION_REPORT.md
docs/KELLY_GPT_INTEGRATION_COMPLETION_REPORT.md
docs/MULTI_REGION_MASTER_FILE_INTEGRATION_COMPLETE.md
docs/ORPHANED_TICKER_BACKFILL_COMPLETION_REPORT.md
docs/TICKER_CORP_CODE_MAPPING_COMPLETION_REPORT.md

# CLI Sprint Reports (Completed)
docs/CLI_SPRINT1_COMPLETION_REPORT.md
docs/CLI_SPRINT7_COMPLETION_REPORT.md
docs/CLI_SPRINT7_UNIT_TEST_COMPLETION_REPORT.md
docs/CLI_SPRINT8_COMPLETION_REPORT.md
docs/CLI_SPRINT9_COMPLETION_REPORT.md
docs/CLI_SPRINT_COMPLETION_REPORT.md

# ETF-Specific Completion Reports (Completed)
docs/ETF_PHASE1_DAY1_COMPLETION.md
docs/ETF_PHASE1_DAY2_STATUS.md
docs/ETF_PHASE2_COMPLETION_REPORT.md
docs/ETF_SCREENING_FINAL_COMPLETION_REPORT.md

# Backtest Workflow Reports (Completed)
docs/BACKTEST_WORKFLOW_PHASE1_COMPLETION_REPORT.md
docs/BACKTEST_WORKFLOW_PHASE2A_COMPLETION_REPORT.md

# Phase 0 Reports (Keep PHASE0_2, archive older)
docs/PHASE0_2_COMPLETION_REPORT.md  ← KEEP (current)
docs/PHASE0_3_COMPLETION_REPORT.md  ← KEEP (current)
```

#### Category B: Analysis Reports (26+ files, evaluate individually)
```markdown
# May still be relevant - REVIEW before archival
docs/ALTERNATIVE_TER_DATA_SOURCES_ANALYSIS.md
docs/ARCHITECTURE_ANALYSIS_REPORT.md
docs/ETF_NULL_COLUMNS_ANALYSIS_REPORT.md
docs/GLOBAL_DB_ARCHITECTURE_ANALYSIS.md
docs/PHASE2_DRY_RUN_ANALYSIS.md
docs/SCANNER_ARCHITECTURE_ANALYSIS.md
docs/SCALE_UP_DECISION_ANALYSIS.md
docs/WEEK2_WEEK3_FACTOR_ANALYSIS_COMPLETION.md
docs/WEEK5_TEST_FAILURE_ANALYSIS.md
docs/WEEK6_FACTOR_ANALYSIS_COMPLETION.md
docs/CLI_DEPENDENCY_ANALYSIS.md
docs/CLI_DEVELOPMENT_COMPLETION_ANALYSIS.md
docs/PHASE0_FAILURE_ANALYSIS.md
docs/PHASE0_2_COVERAGE_ANALYSIS.md
docs/DB_UPDATE_ANALYSIS_REPORT.md
docs/BACKTEST_WORKFLOW_ANALYSIS.md
docs/UNIFIED_DB_UPDATE_SCRIPT_ANALYSIS.md
docs/PHASE2_IMPLEMENTATION_ANALYSIS.md

# Root-level analysis (already in archive/ but duplicates exist)
DIRECTORY_ANALYSIS_20251026.md
README_ANALYSIS.md
SPOCK_FUNCTIONAL_COMPLETENESS_ANALYSIS.md
```

**Recommended Archive Structure**:
```
archive/
├── completion_reports/
│   ├── phase1/          # Phase 1 completion reports
│   ├── phase2/          # Phase 2 completion reports
│   ├── phase3_6/        # Phase 3-6 completion reports
│   ├── weekly/          # Week 1-7 completion reports
│   ├── tasks/           # Task-specific reports
│   ├── daily/           # Day-specific reports
│   ├── cli_sprints/     # CLI sprint reports
│   ├── etf/             # ETF-related reports
│   └── backtest/        # Backtest workflow reports
└── analysis_reports/
    ├── architecture/    # Architecture analysis
    ├── data_quality/    # Data quality reports
    └── performance/     # Performance analysis
```

**Action Plan**:
```bash
# Create archive structure
mkdir -p archive/completion_reports/{phase1,phase2,phase3_6,weekly,tasks,daily,cli_sprints,etf,backtest}
mkdir -p archive/analysis_reports/{architecture,data_quality,performance}

# Archive Phase 1 reports (example)
git mv docs/PHASE1_*.md archive/completion_reports/phase1/

# Archive weekly reports
git mv docs/WEEK*_COMPLETION*.md archive/completion_reports/weekly/

# ... continue for other categories
```

**Risk Assessment**: **MEDIUM** ⚠️
- Reports contain historical context and decisions
- May be referenced in current documentation
- **RECOMMENDED**: Keep in git history, just relocate
- **NEVER DELETE**: These contain valuable project history

---

## 🎯 Priority 3: Legacy Scripts Review (EVALUATE CAREFULLY)

### Target: ~500KB, 13+ Week/Phase-Specific Scripts

**Context**: Many scripts are named by week/phase, which may indicate completion.

**Week-Based Scripts** (likely obsolete after completion):
```python
# Week 3 Scripts (Week 3 completed per CLAUDE.md)
scripts/week3_collect_corporate_actions.py
scripts/week3_collect_corporate_actions_dart.py
scripts/week3_define_universe.py
scripts/week3_define_universe_v1_slow.py      # v1 superseded
scripts/week3_validate_data_quality.py
scripts/week3_adjust_prices.py

# Week 4 Scripts (Week 4 completed per CLAUDE.md)
scripts/week4_deduplicate_ohlcv.py
```

**Phase-Based Scripts** (evaluate individually):
```python
# Phase 1-2 Scripts
scripts/backfill_phase2_historical.py
scripts/phase2_add_detailed_columns.sql
scripts/validate_phase1_data.py
scripts/validate_phase2_backfill.py
scripts/validate_phase2_data.py
scripts/verify_fx_phase1.py
```

**Backfill Scripts** (40 total, many may be one-time use):
```bash
# Scripts directory contains ~40 backfill/migrate scripts
scripts/*backfill*.py    # Historical data loading (one-time operations?)
scripts/*migrate*.py     # Database migrations (completed?)
```

**Recommended Actions**:

1. **Inventory Active Scripts**:
   ```bash
   # Check which scripts are referenced in current codebase
   for script in scripts/week*.py scripts/phase*.py; do
     echo "=== $script ==="
     grep -r "$(basename $script .py)" . --include="*.py" --include="*.md" --exclude-dir=archive
   done
   ```

2. **Archive Obsolete Scripts**:
   ```bash
   mkdir -p archive/scripts/{week_based,phase_based,backfill}

   # Archive week-based scripts (after verification)
   git mv scripts/week3_*.py archive/scripts/week_based/
   git mv scripts/week4_*.py archive/scripts/week_based/
   ```

3. **Create Script Inventory Document**:
   ```markdown
   # scripts/README.md

   ## Active Scripts
   - [Current production scripts with descriptions]

   ## Archived Scripts
   - See archive/scripts/ for historical one-time-use scripts
   ```

**Risk Assessment**: **MEDIUM** ⚠️
- Scripts may be referenced in runbooks or documentation
- Some may still be used for data repairs or re-runs
- **RECOMMENDED**: Archive, don't delete
- **VERIFY**: Check git log for recent usage

---

## 🎯 Priority 4: Configuration & Validation Files (LOW PRIORITY)

### Additional Cleanup Candidates

**Validation Reports** (historical, possibly obsolete):
```
validation_reports/pytest_20251016_150926.log
validation_reports/schema_20251016_150926.log
```

**Test Reports** (archived structure):
```
test_reports/phase5_task1_20251014/
test_reports/phase5_task2_20251014/
test_reports/phase5_task3_20251014/
```

**Action**: Archive if older than 30 days and referenced nowhere in current code.

---

## 📋 Implementation Checklist

### Phase 1: Immediate Safe Actions (5-10 minutes)
- [ ] Delete empty log files (0 bytes, 20+ files)
- [ ] Remove Python cache directories (`__pycache__/`)
- [ ] Delete `.DS_Store` files (macOS metadata)
- [ ] Update `.gitignore` to prevent cache/metadata

### Phase 2: Large Log File Management (10-15 minutes)
- [ ] Archive logs >10MB older than 7 days (compress with gzip)
- [ ] Verify compressed archives are readable
- [ ] Document log retention policy in operations guide

### Phase 3: File Organization (15-20 minutes)
- [ ] Relocate root test files to appropriate `tests/` subdirectories
- [ ] Create test directory structure
- [ ] Update test runner configuration if needed

### Phase 4: Documentation Archival (30-45 minutes)
- [ ] Create archive directory structure
- [ ] Review completion reports for dependencies
- [ ] Archive Phase 1-6 completion reports
- [ ] Archive weekly completion reports
- [ ] Update main documentation with archive references

### Phase 5: Script Evaluation (1-2 hours)
- [ ] Inventory active vs. obsolete scripts
- [ ] Check script references in codebase
- [ ] Archive week/phase-specific scripts
- [ ] Create scripts README with inventory

### Phase 6: Verification (15 minutes)
- [ ] Run full test suite to verify no breakage
- [ ] Check documentation links aren't broken
- [ ] Verify archive structure is accessible
- [ ] Update CLAUDE.md with cleanup completion

---

## 🛡️ Safety Protocols

### Before Any Deletion
1. **Git Status Check**: Ensure all changes are committed
2. **Backup**: Create timestamped backup of logs/ directory
   ```bash
   tar -czf logs_backup_$(date +%Y%m%d_%H%M%S).tar.gz logs/
   ```
3. **Test**: Run full test suite before and after
4. **Documentation**: Update cleanup tracking document

### Rollback Plan
```bash
# If issues arise, restore from backup
tar -xzf logs_backup_YYYYMMDD_HHMMSS.tar.gz

# Restore archived files if needed
git mv archive/completion_reports/phase1/*.md docs/
```

---

## 📊 Expected Results

### Space Recovery Projection
| Phase | Recovery | Time | Risk |
|-------|----------|------|------|
| Phase 1 | ~5MB | 10 min | ZERO |
| Phase 2 | ~900MB | 15 min | LOW |
| Phase 3 | 0MB (org) | 20 min | ZERO |
| Phase 4 | ~2MB | 45 min | MEDIUM |
| Phase 5 | ~500KB | 2 hrs | MEDIUM |
| **Total** | **~905MB** | **~3.5 hrs** | **LOW-MEDIUM** |

### Organization Improvements
- ✅ Cleaner root directory (test files relocated)
- ✅ Organized documentation (archive/ structure)
- ✅ Reduced log directory size by 93%
- ✅ Clear separation: active vs. historical
- ✅ Git history preserved for all archived files

---

## 🎯 Success Criteria

### Quantitative
- [ ] Disk usage: logs/ reduced from 971MB to <70MB
- [ ] File count: Reduced by ~230 files
- [ ] Root directory: 0 test files (all in tests/)
- [ ] Documentation: Active docs <50 files

### Qualitative
- [ ] Clear distinction between active and archived content
- [ ] No broken documentation links
- [ ] All tests passing
- [ ] Git history intact
- [ ] Team can easily find historical context when needed

---

## 📝 Notes

### Previous Cleanup (2025-10-26)
- Removed 192MB migration log
- Archived 27 Spock legacy files
- Archived 8 historical analysis reports
- Total: ~193MB recovered

### Current Project Focus
- Phase 0.2: Code stabilization (COMPLETE)
- Phase 1: Backtesting engine (IN PROGRESS)
- Focus: Test coverage expansion and engine validation

### References
- CLAUDE.md: Current status and roadmap
- CLEANUP_COMPLETION_REPORT.md: Previous cleanup details
- .gitignore: Exclusion patterns

---

**Last Updated**: 2025-11-03
**Next Review**: 2025-12-03 (monthly cleanup recommended)
