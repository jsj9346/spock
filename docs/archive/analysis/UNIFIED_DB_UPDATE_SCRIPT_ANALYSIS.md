# 통합 DB 최신화 스크립트 설계 분석 리포트

**생성일**: 2025-11-01
**분석 목적**: 분산된 DB 최신화 기능을 단일 통합 스크립트로 구현하기 위한 기술적 타당성 및 설계 분석
**분석자**: Claude Code - /sc:analyze

---

## 📋 Executive Summary

### 분석 결론: ✅ **통합 스크립트 구현 가능 및 권장**

**핵심 결론**:
- 현재 분산된 5개 스크립트를 **하나의 마스터 스크립트**로 통합하는 것은 **기술적으로 가능**하며 **강력히 권장**됨
- 모든 스크립트가 Python 기반이며 공통 의존성(PostgreSQL, dotenv)을 공유함
- 각 단계가 독립적으로 실행 가능하도록 설계되어 있어 통합이 용이함
- 예상 구현 시간: **4-6 시간** (단일 개발자 기준)

### 주요 이점
| 이점 | 설명 | 영향도 |
|------|------|--------|
| **운영 편의성** | 단일 명령어로 전체 DB 최신화 완료 | 🔴 High |
| **에러 관리** | 통합된 에러 핸들링 및 롤백 전략 | 🔴 High |
| **일관성 보장** | 단계별 의존성 관리로 데이터 정합성 보장 | 🔴 High |
| **모니터링** | 전체 파이프라인 진행 상황 추적 | 🟡 Medium |
| **자동화** | Cron job 스케줄링 간소화 | 🟡 Medium |
| **유지보수** | 단일 진입점으로 버그 수정 및 개선 용이 | 🟢 Low |

### 주요 위험 요소
| 위험 | 완화 전략 | 우선순위 |
|------|-----------|----------|
| **단일 장애점** | 체크포인트 저장, 부분 재실행 기능 | 🔴 High |
| **긴 실행 시간** | 백그라운드 실행, 진행 상황 로깅 | 🟡 Medium |
| **Rate Limiting 충돌** | API 호출 통합 관리, 지연 시간 조정 | 🟡 Medium |
| **메모리 사용량** | 배치 처리, 스트리밍 방식 적용 | 🟢 Low |

---

## 1️⃣ 현재 시스템 분석

### 1.1 분산 스크립트 현황

#### 📊 스크립트 인벤토리

| # | 스크립트 | 기능 | 의존성 | 실행 시간 | 상태 |
|---|---------|------|--------|----------|------|
| 1 | `update_master_files.py` | 해외 ticker 업데이트 | KIS API | ~20s (5 regions) | ✅ 구현 |
| 2 | `update_kr_tickers.py` | KR ticker 업데이트 | pykrx | ~10s | ❌ 미구현 |
| 3 | `kis_data_collector.py` | OHLCV 증분 업데이트 | KIS API | ~60s (2.5K tickers) | ✅ 구현 |
| 4 | `backfill_fundamentals_dart.py` | 펀더멘털 데이터 | DART API | ~300s (300 tickers) | ✅ 구현 |
| 5 | `calculate_dividend_yield.py` | 배당 수익률 계산 | PostgreSQL | ~30s (1.2K tickers) | ✅ 구현 |
| 6 | `backfill_quarterly_financials.py` | 분기별 순자산 | DART API | ~200s (예상) | ❌ 미구현 |

**총 예상 실행 시간**: ~10-12분 (순차 실행 시, rate limiting 포함)

#### 🔗 의존성 그래프

```
PostgreSQL Database
       │
       ├─── update_master_files.py (해외 ticker)
       │         │
       │         ├─── KISOverseasStockAPI
       │         └─── KISMasterFileManager
       │
       ├─── update_kr_tickers.py (KR ticker) [미구현]
       │         │
       │         └─── pykrx.stock
       │
       ├─── kis_data_collector.py (OHLCV)
       │         │
       │         ├─── KIS API
       │         ├─── pandas_ta (기술 지표)
       │         └─── tickers 테이블 (의존)
       │
       ├─── backfill_fundamentals_dart.py (펀더멘털)
       │         │
       │         ├─── DARTApiClient
       │         ├─── tickers 테이블 (의존)
       │         └─── ohlcv_data 테이블 (최신 주가 조회)
       │
       ├─── calculate_dividend_yield.py (배당 수익률)
       │         │
       │         ├─── ticker_fundamentals 테이블 (DPS)
       │         └─── ohlcv_data 테이블 (최신 주가)
       │
       └─── backfill_quarterly_financials.py (분기별 순자산) [미구현]
                 │
                 ├─── DARTApiClient
                 └─── tickers 테이블 (의존)
```

**의존성 순서**:
1. **Tickers 업데이트** (독립) → 2. **OHLCV 업데이트** (tickers 의존) → 3. **펄더멘털 업데이트** (tickers + ohlcv 의존) → 4. **배당 수익률 계산** (fundamentals + ohlcv 의존) → 5. **분기별 순자산** (tickers 의존)

### 1.2 공통 패턴 분석

#### ✅ 공통 설계 패턴

모든 스크립트가 다음 패턴을 공유:

```python
# 1. 공통 구조
class [Feature]Processor:
    def __init__(self, db: PostgresDatabaseManager, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self.stats = {...}  # 통계 추적

    def process(self, ...):
        # 메인 로직
        pass

    def get_statistics(self):
        return self.stats

def main():
    parser = argparse.ArgumentParser(...)
    # --dry-run, --limit, --incremental 등 공통 플래그
    args = parser.parse_args()

    db = PostgresDatabaseManager()
    processor = [Feature]Processor(db, dry_run=args.dry_run)
    result = processor.process(...)

    # 통계 출력
    print_summary(result)
```

#### 🔑 공통 기능

| 기능 | 구현 스크립트 수 | 설명 |
|------|-----------------|------|
| **Dry Run 모드** | 5/5 (100%) | `--dry-run` 플래그로 미리보기 |
| **Incremental 모드** | 3/5 (60%) | `--incremental` 플래그로 증분 업데이트 |
| **Rate Limiting** | 2/5 (40%) | API 호출 제한 준수 |
| **Checkpoint 저장** | 1/5 (20%) | 중단 시 재개 가능 |
| **통계 추적** | 5/5 (100%) | 성공/실패/스킵 카운트 |
| **Logging** | 5/5 (100%) | 파일 및 콘솔 로그 |

#### 🎯 공통 의존성

```python
# 모든 스크립트가 공유하는 의존성
import os
import sys
import time
import logging
import argparse
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

from modules.db_manager_postgres import PostgresDatabaseManager
```

---

## 2️⃣ 통합 스크립트 아키텍처 설계

### 2.1 아키텍처 개요

#### 🏗️ 레이어 구조

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLI Interface Layer                           │
│  - Argument parsing (regions, steps, dry-run, incremental)       │
│  - User interaction (progress display, confirmations)            │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                 Orchestration Layer                              │
│  - Pipeline execution manager                                    │
│  - Step sequencing and dependency resolution                     │
│  - Error handling and rollback coordination                      │
│  - Progress tracking and reporting                               │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                   Step Execution Layer                           │
│  ┌─────────────┬──────────────┬──────────────┬─────────────┐   │
│  │ Ticker      │ OHLCV        │ Fundamental  │ Dividend    │   │
│  │ Updater     │ Collector    │ Backfiller   │ Calculator  │   │
│  └─────────────┴──────────────┴──────────────┴─────────────┘   │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                   Data Access Layer                              │
│  - PostgresDatabaseManager                                       │
│  - Transaction management                                        │
│  - Connection pooling                                            │
└───────────────────────┬─────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────┐
│                 External Services Layer                          │
│  - KIS API (tickers, OHLCV)                                     │
│  - DART API (fundamentals, quarterly financials)                │
│  - pykrx (KR ticker list, dividend data)                        │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 핵심 컴포넌트 설계

#### 📦 Component 1: DatabaseUpdateOrchestrator

**역할**: 전체 파이프라인 실행 조율

```python
class DatabaseUpdateOrchestrator:
    """
    통합 DB 업데이트 오케스트레이터

    Features:
    - 단계별 실행 순서 관리
    - 의존성 해결 (ticker → ohlcv → fundamental)
    - 에러 핸들링 및 롤백
    - 진행 상황 추적
    - Checkpoint 저장/복구
    """

    def __init__(self, db: PostgresDatabaseManager, config: Dict):
        self.db = db
        self.config = config
        self.stats = {
            'start_time': None,
            'end_time': None,
            'total_duration': 0.0,
            'steps_completed': [],
            'steps_failed': [],
            'step_stats': {}
        }
        self.checkpoint_manager = CheckpointManager()

    def run_pipeline(self, regions: List[str], steps: List[str], **kwargs) -> Dict:
        """
        실행 파이프라인

        Args:
            regions: 업데이트할 리전 리스트
            steps: 실행할 단계 리스트
            **kwargs: 추가 옵션 (dry_run, incremental, force, etc.)

        Returns:
            실행 결과 딕셔너리
        """
        self.stats['start_time'] = datetime.now()

        try:
            # Step 1: Pre-flight checks
            self._pre_flight_checks(regions, steps)

            # Step 2: Execute pipeline
            for step in steps:
                if not self._should_execute_step(step):
                    continue

                step_result = self._execute_step(step, regions, **kwargs)
                self._handle_step_result(step, step_result)

                # Save checkpoint
                self.checkpoint_manager.save(step, step_result)

            # Step 3: Post-execution validation
            self._post_execution_validation(regions)

        except Exception as e:
            self._handle_pipeline_failure(e)
            raise

        finally:
            self.stats['end_time'] = datetime.now()
            self.stats['total_duration'] = (
                self.stats['end_time'] - self.stats['start_time']
            ).total_seconds()

        return self.stats

    def _execute_step(self, step: str, regions: List[str], **kwargs) -> Dict:
        """단계별 실행 로직"""
        step_mapping = {
            'tickers': self._update_tickers,
            'ohlcv': self._update_ohlcv,
            'fundamentals': self._update_fundamentals,
            'ratios': self._calculate_ratios,
            'dividend': self._calculate_dividend,
            'quarterly': self._update_quarterly_financials
        }

        executor = step_mapping.get(step)
        if not executor:
            raise ValueError(f"Unknown step: {step}")

        return executor(regions, **kwargs)
```

#### 📦 Component 2: Step Executors (각 기능별)

**TickerUpdater**:
```python
class TickerUpdater:
    """Ticker 테이블 업데이트 실행자"""

    def update_tickers(self, regions: List[str], dry_run: bool = False) -> Dict:
        """
        Ticker 테이블 증분 업데이트

        Process:
        1. KR: pykrx를 통한 KOSPI/KOSDAQ/KONEX ticker 리스트 조회
        2. Overseas: KIS API master files 다운로드
        3. 신규 상장 감지 및 INSERT
        4. 상장폐지 감지 및 status='delisted' UPDATE
        """
        results = {}

        for region in regions:
            if region == 'KR':
                results[region] = self._update_kr_tickers(dry_run)
            else:
                results[region] = self._update_overseas_tickers(region, dry_run)

        return results
```

**OHLCVCollector**:
```python
class OHLCVCollector:
    """OHLCV 데이터 수집 실행자"""

    def collect_ohlcv(self, regions: List[str], incremental: bool = True,
                      lookback_days: int = 7, dry_run: bool = False) -> Dict:
        """
        OHLCV 데이터 증분 수집

        Process:
        1. 각 ticker의 최신 OHLCV 날짜 조회
        2. Gap 감지 (최신 날짜 ~ 오늘)
        3. Gap 기간만 API 호출하여 수집
        4. PostgreSQL upsert로 저장
        """
        # KIS API rate limiting: 20 req/sec, 1,000 req/min
        rate_limiter = RateLimiter(max_rate=20, time_window=1.0)

        results = {}
        for region in regions:
            results[region] = self._collect_region_ohlcv(
                region, incremental, lookback_days, rate_limiter, dry_run
            )

        return results
```

**FundamentalBackfiller**:
```python
class FundamentalBackfiller:
    """펀더멘털 데이터 수집 실행자"""

    def backfill_fundamentals(self, regions: List[str], incremental: bool = True,
                               dry_run: bool = False) -> Dict:
        """
        펀더멘털 데이터 수집 및 주가배수 계산

        Process:
        1. 미수집 ticker 조회 (incremental mode)
        2. DART API로 최신 사업보고서 데이터 가져오기
        3. ROE, ROA, Debt Ratio 등 추출
        4. 최신 OHLCV 종가 조회
        5. P/E, P/B, P/S 계산
        6. ticker_fundamentals 테이블 upsert
        """
        # DART API rate limiting: ~1 req/sec (안전)
        rate_limiter = RateLimiter(max_rate=1, time_window=1.0)

        results = {}
        for region in regions:
            if region == 'KR':
                results[region] = self._backfill_kr_fundamentals(
                    incremental, rate_limiter, dry_run
                )
            else:
                results[region] = self._backfill_global_fundamentals(
                    region, incremental, dry_run
                )

        return results
```

**DividendCalculator**:
```python
class DividendCalculator:
    """배당 수익률 계산 실행자"""

    def calculate_dividend_yield(self, regions: List[str],
                                  dry_run: bool = False) -> Dict:
        """
        배당 수익률 계산

        Formula:
        Dividend Yield (%) = (Latest DPS / Latest Stock Price) × 100

        Process:
        1. pykrx에서 최신 배당금(DPS) 조회
        2. ohlcv_data에서 최신 종가 조회
        3. 배당 수익률 계산
        4. ticker_fundamentals 테이블 UPDATE
        """
        results = {}
        for region in regions:
            if region == 'KR':
                results[region] = self._calculate_kr_dividend_yield(dry_run)
            # 기타 시장은 yfinance 또는 다른 데이터 소스 사용

        return results
```

#### 📦 Component 3: Utility Components

**CheckpointManager**:
```python
class CheckpointManager:
    """체크포인트 저장/복구 관리자"""

    def save(self, step: str, result: Dict) -> None:
        """
        체크포인트 저장

        Format:
        {
            "timestamp": "2025-11-01T09:30:00",
            "step": "fundamentals",
            "result": {...},
            "next_step": "dividend"
        }
        """
        checkpoint_file = f"log/checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(checkpoint_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'step': step,
                'result': result,
                'next_step': self._get_next_step(step)
            }, f, indent=2)

    def load_latest(self) -> Optional[Dict]:
        """최신 체크포인트 로드"""
        checkpoint_files = glob.glob("log/checkpoint_*.json")
        if not checkpoint_files:
            return None

        latest_file = max(checkpoint_files, key=os.path.getmtime)
        with open(latest_file, 'r') as f:
            return json.load(f)

    def resume_from_checkpoint(self) -> str:
        """체크포인트에서 재개할 다음 단계 반환"""
        checkpoint = self.load_latest()
        if checkpoint:
            return checkpoint.get('next_step')
        return None
```

**RateLimiter**:
```python
class RateLimiter:
    """API 호출 속도 제한 관리자"""

    def __init__(self, max_rate: int, time_window: float = 1.0):
        """
        Args:
            max_rate: 시간 윈도우당 최대 호출 수
            time_window: 시간 윈도우 (초)
        """
        self.max_rate = max_rate
        self.time_window = time_window
        self.calls = []

    def wait_if_needed(self) -> None:
        """필요시 대기"""
        now = time.time()

        # 윈도우 밖의 오래된 호출 제거
        self.calls = [t for t in self.calls if now - t < self.time_window]

        # Rate limit 초과 시 대기
        if len(self.calls) >= self.max_rate:
            sleep_time = self.time_window - (now - self.calls[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
                self.calls.pop(0)

        self.calls.append(now)
```

**DataQualityValidator**:
```python
class DataQualityValidator:
    """데이터 품질 검증자"""

    def validate_pipeline_output(self, regions: List[str]) -> Dict:
        """
        파이프라인 실행 후 데이터 품질 검증

        Checks:
        1. Ticker coverage (각 리전별 ticker 수)
        2. OHLCV coverage (최근 30일 데이터 존재 비율)
        3. Fundamental coverage (펀더멘털 데이터 존재 비율)
        4. Anomaly detection (가격 급등/급락)
        """
        validation_results = {}

        for region in regions:
            validation_results[region] = {
                'ticker_count': self._count_tickers(region),
                'ohlcv_coverage': self._check_ohlcv_coverage(region),
                'fundamental_coverage': self._check_fundamental_coverage(region),
                'anomalies': self._detect_anomalies(region),
                'passed': True  # Overall pass/fail
            }

        return validation_results
```

---

## 3️⃣ 실행 순서 및 의존성 분석

### 3.1 단계별 의존성 매트릭스

| 단계 | 의존 단계 | 필수/선택 | 이유 |
|------|----------|----------|------|
| **1. Tickers** | - | - | 독립적 실행 가능 |
| **2. OHLCV** | 1. Tickers | 필수 | ticker 리스트가 있어야 OHLCV 수집 가능 |
| **3. Fundamentals** | 1. Tickers, 2. OHLCV | 필수 | ticker 필요 + 최신 주가로 주가배수 계산 |
| **4. Ratios** | 3. Fundamentals | 자동 | Fundamentals 단계에서 자동 계산 |
| **5. Dividend** | 2. OHLCV, 3. Fundamentals | 필수 | 최신 주가 + 배당금 데이터 필요 |
| **6. Quarterly** | 1. Tickers | 필수 | ticker 필요, OHLCV는 선택 |

### 3.2 최적 실행 순서

#### 🎯 Sequential Execution (순차 실행 - 권장)

```
1. Tickers Update (KR + Overseas)
   ↓ (의존성: ticker 리스트 필요)
2. OHLCV Update (All regions)
   ↓ (의존성: 최신 주가 필요)
3. Fundamentals Update (DART for KR, yfinance for others)
   ↓ (자동 계산: P/E, P/B, P/S)
4. Dividend Yield Calculation (KR)
   ↓ (선택적 실행)
5. Quarterly Financials Update (KR, optional)
```

**총 예상 실행 시간**: ~10-12분

#### ⚡ Parallel Execution Opportunities (병렬 실행 가능 부분)

```
┌─ Tickers Update ──────────────────┐
│  ├─ KR (pykrx)      [10s]         │  ← 병렬 가능
│  ├─ US (KIS API)    [5s]          │  ← 병렬 가능
│  ├─ HK (KIS API)    [3s]          │  ← 병렬 가능
│  ├─ JP (KIS API)    [4s]          │  ← 병렬 가능
│  └─ CN, VN (KIS API) [8s]         │  ← 병렬 가능
└────────────────────────────────────┘
   ↓ (병렬 실행 시 ~10s, 순차 실행 시 ~30s)

┌─ OHLCV Update ────────────────────┐
│  ├─ KR (2.5K tickers) [60s]       │  ← 병렬 가능 (배치 단위)
│  └─ Overseas [40s]                │  ← 병렬 가능
└────────────────────────────────────┘
   ↓ (병렬 실행 시 ~60s, 순차 실행 시 ~100s)

...
```

**병렬 실행 시 예상 시간 단축**: ~30-40% (10-12분 → 7-8분)

### 3.3 에러 시나리오 및 복구 전략

#### 🚨 에러 시나리오 매트릭스

| 시나리오 | 영향 범위 | 복구 전략 | 우선순위 |
|---------|----------|----------|----------|
| **Tickers 단계 실패** | 전체 파이프라인 중단 | 재시도 (3회), 실패 시 체크포인트 저장 | 🔴 Critical |
| **OHLCV 단계 부분 실패** | 해당 ticker만 영향 | 실패한 ticker 리스트 저장, 재실행 | 🟡 High |
| **Fundamentals API timeout** | 해당 ticker만 영향 | Rate limiting 완화, 재시도 | 🟡 High |
| **Database connection 손실** | 진행 중 단계 실패 | 자동 재연결, 트랜잭션 롤백 | 🔴 Critical |
| **Disk full** | 로그 파일 쓰기 실패 | 경고 후 계속 실행 | 🟢 Medium |
| **네트워크 불안정** | API 호출 실패 | 지수 백오프 재시도 (최대 5회) | 🟡 High |

#### 🔧 복구 메커니즘

**1. Checkpoint-based Recovery**
```python
def run_pipeline_with_recovery(self, ...):
    """체크포인트 기반 복구 실행"""

    # 1. 체크포인트 확인
    checkpoint = self.checkpoint_manager.load_latest()

    if checkpoint and self.config.get('resume', False):
        logger.info(f"Resuming from checkpoint: {checkpoint['step']}")
        start_step = checkpoint.get('next_step')
    else:
        start_step = steps[0]

    # 2. 시작 단계부터 실행
    for step in steps[steps.index(start_step):]:
        try:
            result = self._execute_step(step, ...)
            self.checkpoint_manager.save(step, result)

        except Exception as e:
            logger.error(f"Step {step} failed: {e}")

            if self.config.get('fail_fast', False):
                raise

            # 에러 로그 저장 후 다음 단계 계속
            self._log_step_failure(step, e)
```

**2. Transaction-based Rollback**
```python
def _execute_step_with_transaction(self, step: str, ...):
    """트랜잭션 기반 단계 실행"""

    conn = self.db.get_connection()

    try:
        conn.begin()  # 트랜잭션 시작

        # 단계 실행
        result = self._execute_step_logic(step, ...)

        conn.commit()  # 성공 시 커밋
        return result

    except Exception as e:
        conn.rollback()  # 실패 시 롤백
        logger.error(f"Rolling back step {step}: {e}")
        raise
```

**3. Retry with Exponential Backoff**
```python
def _api_call_with_retry(self, api_func, max_retries: int = 5):
    """지수 백오프 재시도"""

    for attempt in range(max_retries):
        try:
            return api_func()

        except (TimeoutError, ConnectionError) as e:
            if attempt == max_retries - 1:
                raise

            wait_time = 2 ** attempt  # 1, 2, 4, 8, 16초
            logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s")
            time.sleep(wait_time)
```

---

## 4️⃣ 성능 및 확장성 분석

### 4.1 성능 프로파일

#### ⏱️ 예상 실행 시간 (순차 실행)

| 단계 | KR | US | HK | JP | CN | VN | 총계 |
|------|----|----|----|----|----|----|------|
| **Tickers** | 10s | 5s | 3s | 4s | 4s | 4s | 30s |
| **OHLCV** | 60s | 40s | 20s | 25s | 30s | 15s | 190s |
| **Fundamentals** | 300s | 120s | 60s | 80s | 90s | 40s | 690s |
| **Dividend** | 30s | - | - | - | - | - | 30s |
| **Quarterly** | 200s | - | - | - | - | - | 200s |
| **Validation** | 10s | 5s | 3s | 3s | 3s | 3s | 27s |
| **총 실행 시간** | 610s | 170s | 86s | 112s | 127s | 62s | **1,167s ≈ 19.5분** |

#### ⚡ 최적화 전략

**1. 병렬 처리 (Multi-threading)**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def _update_tickers_parallel(self, regions: List[str]) -> Dict:
    """리전별 ticker 업데이트 병렬 실행"""

    results = {}

    with ThreadPoolExecutor(max_workers=len(regions)) as executor:
        future_to_region = {
            executor.submit(self._update_single_region, region): region
            for region in regions
        }

        for future in as_completed(future_to_region):
            region = future_to_region[future]
            try:
                results[region] = future.result()
            except Exception as e:
                logger.error(f"Region {region} failed: {e}")
                results[region] = {'success': False, 'error': str(e)}

    return results
```

**예상 효과**: Tickers 단계 30s → 10s (67% 단축)

**2. 배치 처리 (Batch Processing)**
```python
def _collect_ohlcv_batch(self, tickers: List[str], batch_size: int = 50):
    """배치 단위 OHLCV 수집"""

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]

        # 배치 API 호출
        ohlcv_data = self.api.get_ohlcv_batch(batch)

        # 배치 INSERT
        self.db.insert_ohlcv_batch(ohlcv_data)

        logger.info(f"Processed batch {i//batch_size + 1}/{len(tickers)//batch_size}")
```

**예상 효과**: OHLCV 단계 190s → 120s (37% 단축)

**3. 캐싱 (In-Memory Caching)**
```python
from functools import lru_cache

@lru_cache(maxsize=10000)
def _get_latest_ohlcv_date(self, ticker: str) -> Optional[date]:
    """최신 OHLCV 날짜 조회 (캐싱)"""
    # 데이터베이스 조회는 첫 호출 시에만 발생
    query = "SELECT MAX(date) FROM ohlcv_data WHERE ticker=%s"
    result = self.db.execute_query(query, (ticker,))
    return result[0]['max'] if result else None
```

**예상 효과**: Database 쿼리 감소 (~50% 단축)

#### 📊 최적화 후 예상 실행 시간

| 최적화 전 | 최적화 후 | 개선율 |
|----------|----------|--------|
| **19.5분** | **8-10분** | **~50% 단축** |

### 4.2 확장성 고려사항

#### 📈 스케일 시나리오

| 시나리오 | 현재 규모 | 5년 후 예상 | 확장 전략 |
|---------|----------|------------|----------|
| **Ticker 수** | ~16K | ~25K | 병렬 처리, 리전별 분산 |
| **OHLCV 데이터 볼륨** | ~1.4M 레코드 | ~10M 레코드 | 배치 처리, 파티셔닝 |
| **API 호출 수** | ~3K calls/day | ~10K calls/day | Rate limiting 최적화, 캐싱 |
| **실행 시간** | ~10분 | ~15-20분 | 증분 업데이트, 병렬화 |

#### 🔧 확장성 전략

**1. 데이터베이스 파티셔닝**
```sql
-- TimescaleDB 하이퍼테이블 파티셔닝 (이미 적용됨)
SELECT create_hypertable('ohlcv_data', 'date', chunk_time_interval => INTERVAL '1 month');

-- 리전별 파티셔닝 추가 (선택적)
CREATE TABLE ohlcv_data_kr PARTITION OF ohlcv_data FOR VALUES IN ('KR');
CREATE TABLE ohlcv_data_us PARTITION OF ohlcv_data FOR VALUES IN ('US');
...
```

**2. 증분 업데이트 최적화**
```python
def _get_incremental_update_tickers(self, region: str, days: int = 7) -> List[str]:
    """최근 N일간 업데이트가 없는 ticker만 조회"""

    query = """
    SELECT t.ticker
    FROM tickers t
    LEFT JOIN (
        SELECT ticker, MAX(date) as last_date
        FROM ohlcv_data
        WHERE region = %s AND date >= NOW() - INTERVAL '%s days'
        GROUP BY ticker
    ) o ON t.ticker = o.ticker
    WHERE t.region = %s AND (o.last_date IS NULL OR o.last_date < CURRENT_DATE)
    """

    result = self.db.execute_query(query, (region, days, region))
    return [row['ticker'] for row in result]
```

**3. 분산 실행 (Multi-machine)**
```bash
# 리전별 분산 실행 (선택적 - 대규모 환경)
# Machine 1: KR 시장 전담
python3 scripts/update_database.py --regions KR

# Machine 2: US, HK 시장 전담
python3 scripts/update_database.py --regions US HK

# Machine 3: JP, CN, VN 시장 전담
python3 scripts/update_database.py --regions JP CN VN
```

---

## 5️⃣ 보안 및 데이터 무결성

### 5.1 보안 고려사항

#### 🔐 API Key 관리

**현재 방식** (dotenv):
```python
load_dotenv()
KIS_APP_KEY = os.getenv('KIS_APP_KEY')
DART_API_KEY = os.getenv('DART_API_KEY')
```

**권장 사항**:
- ✅ `.env` 파일을 `.gitignore`에 추가 (이미 적용됨)
- ✅ Production 환경에서는 환경 변수 또는 AWS Secrets Manager 사용
- ⚠️ API Key 로테이션 정책 수립 (90일마다)

#### 🛡️ SQL Injection 방지

**현재 방식** (Parameterized Queries):
```python
# ✅ 안전: Parameterized query
query = "SELECT * FROM tickers WHERE ticker=%s AND region=%s"
result = self.db.execute_query(query, (ticker, region))

# ❌ 위험: String concatenation
query = f"SELECT * FROM tickers WHERE ticker='{ticker}'"  # SQL Injection 가능
```

**권장 사항**:
- ✅ 모든 데이터베이스 쿼리에 Parameterized Queries 사용 (현재 준수 중)
- ✅ ORM 사용 고려 (SQLAlchemy, Django ORM)

### 5.2 데이터 무결성 보장

#### 🔒 트랜잭션 관리

**ACID 속성 보장**:
```python
def _update_with_transaction(self, updates: List[Dict]):
    """트랜잭션으로 데이터 무결성 보장"""

    conn = self.db.get_connection()

    try:
        conn.begin()  # Atomicity 시작

        for update in updates:
            self._execute_update(update)

        conn.commit()  # Consistency 보장
        logger.info("Transaction committed successfully")

    except Exception as e:
        conn.rollback()  # Isolation & Durability
        logger.error(f"Transaction rolled back: {e}")
        raise
```

#### 🔍 데이터 검증

**입력 데이터 검증**:
```python
def _validate_ohlcv_data(self, data: Dict) -> bool:
    """OHLCV 데이터 유효성 검증"""

    validations = [
        ('ticker', lambda x: len(x) == 6 and x.isdigit()),  # KR ticker 형식
        ('date', lambda x: isinstance(x, date)),
        ('open', lambda x: x > 0),
        ('high', lambda x: x >= data['open']),
        ('low', lambda x: x <= data['open']),
        ('close', lambda x: x > 0),
        ('volume', lambda x: x >= 0)
    ]

    for field, validator in validations:
        if not validator(data.get(field)):
            logger.warning(f"Invalid {field}: {data.get(field)}")
            return False

    return True
```

**이상치 탐지**:
```python
def _detect_price_anomalies(self, ticker: str, new_close: float) -> bool:
    """가격 이상치 탐지 (급등/급락 >±20%)"""

    # 최근 종가 조회
    query = "SELECT close FROM ohlcv_data WHERE ticker=%s ORDER BY date DESC LIMIT 1"
    result = self.db.execute_query(query, (ticker,))

    if not result:
        return False

    prev_close = result[0]['close']
    change_pct = (new_close - prev_close) / prev_close * 100

    if abs(change_pct) > 20:
        logger.warning(f"Price anomaly detected for {ticker}: {change_pct:.2f}%")
        return True

    return False
```

---

## 6️⃣ 구현 계획 및 권장사항

### 6.1 구현 우선순위

#### Phase 1: Core Infrastructure (1-2일)

**우선순위 🔴 High**

| Task | 설명 | 예상 시간 |
|------|------|----------|
| 1. `DatabaseUpdateOrchestrator` 클래스 개발 | 파이프라인 실행 조율자 | 3-4 hours |
| 2. `CheckpointManager` 개발 | 체크포인트 저장/복구 | 1-2 hours |
| 3. `RateLimiter` 개발 | API 호출 속도 제한 | 1 hour |
| 4. CLI 인터페이스 개발 | argparse 기반 명령줄 인터페이스 | 2 hours |

**총 예상 시간**: 7-9 hours

#### Phase 2: Step Executors (2-3일)

**우선순위 🟡 Medium**

| Task | 설명 | 예상 시간 |
|------|------|----------|
| 5. `TickerUpdater` 개발 (KR 포함) | pykrx + KIS API 통합 | 3-4 hours |
| 6. `OHLCVCollector` 래핑 | 기존 kis_data_collector 통합 | 2 hours |
| 7. `FundamentalBackfiller` 래핑 | 기존 backfill_fundamentals_dart 통합 | 2 hours |
| 8. `DividendCalculator` 래핑 | 기존 calculate_dividend_yield 통합 | 1 hour |
| 9. `QuarterlyFinancialsUpdater` 개발 | 분기별 순자산 업데이트 (신규) | 4-6 hours |

**총 예상 시간**: 12-15 hours

#### Phase 3: Testing & Optimization (1-2일)

**우선순위 🟢 Low**

| Task | 설명 | 예상 시간 |
|------|------|----------|
| 10. 단위 테스트 작성 | pytest 기반 테스트 | 4 hours |
| 11. 통합 테스트 작성 | 전체 파이프라인 테스트 | 3 hours |
| 12. 성능 최적화 | 병렬 처리, 캐싱 적용 | 3-4 hours |
| 13. 문서화 | README, 사용 가이드 작성 | 2 hours |

**총 예상 시간**: 12-13 hours

### 6.2 총 구현 시간 예상

| Phase | 예상 시간 | 누적 시간 |
|-------|----------|----------|
| Phase 1: Core Infrastructure | 7-9 hours | 7-9 hours |
| Phase 2: Step Executors | 12-15 hours | 19-24 hours |
| Phase 3: Testing & Optimization | 12-13 hours | 31-37 hours |

**총 예상 구현 시간**: **31-37 hours (약 4-5일, 단일 개발자 기준)**

### 6.3 최종 권장사항

#### ✅ 통합 스크립트 개발 강력 권장

**이유**:
1. **운영 효율성**: 단일 명령어로 전체 DB 최신화 가능
2. **에러 관리**: 통합된 에러 핸들링 및 복구 전략
3. **데이터 정합성**: 단계별 의존성 관리로 일관성 보장
4. **자동화 용이**: Cron job 스케줄링 간소화
5. **유지보수성**: 단일 진입점으로 버그 수정 및 개선 용이

#### 🎯 구현 순서 권장

1. **Phase 1 먼저 완료** (핵심 인프라)
   - `DatabaseUpdateOrchestrator`, `CheckpointManager`, `RateLimiter`
   - CLI 인터페이스

2. **기존 스크립트 래핑** (Phase 2의 6-8번)
   - 기존 코드를 재사용하여 빠르게 통합

3. **신규 기능 개발** (Phase 2의 5, 9번)
   - KR Ticker Updater, Quarterly Financials Updater

4. **최적화 및 테스트** (Phase 3)
   - 병렬 처리, 캐싱, 단위/통합 테스트

#### 📝 스크립트 사용 예시

```bash
# 전체 DB 최신화 (권장 - 일일 실행)
python3 scripts/update_database.py

# KR 시장만 업데이트
python3 scripts/update_database.py --regions KR

# 특정 단계만 실행
python3 scripts/update_database.py --steps tickers ohlcv

# Dry run (미리보기)
python3 scripts/update_database.py --dry-run

# 증분 업데이트 (미수집 데이터만)
python3 scripts/update_database.py --incremental

# 체크포인트에서 재개
python3 scripts/update_database.py --resume

# 백그라운드 실행
nohup python3 scripts/update_database.py > log/db_update_$(date +%Y%m%d).log 2>&1 &
```

#### 🔄 자동화 스케줄링 (Cron)

```bash
# Crontab 설정
crontab -e

# 매일 오전 6시 자동 실행
0 6 * * * cd /Users/13ruce/spock && python3 scripts/update_database.py --incremental >> log/daily_update.log 2>&1
```

---

## 7️⃣ 대안 분석

### Option A: 통합 스크립트 (권장)

**장점**:
- ✅ 단일 명령어로 전체 DB 최신화
- ✅ 통합된 에러 핸들링
- ✅ 자동화 용이

**단점**:
- ⚠️ 초기 개발 시간 필요 (4-5일)
- ⚠️ 단일 장애점 (체크포인트로 완화)

**권장 시나리오**: 프로덕션 환경, 일일 자동 실행

### Option B: Bash 스크립트 래퍼

**예시**:
```bash
#!/bin/bash
# daily_db_update.sh

python3 scripts/update_master_files.py --regions US HK JP CN VN
python3 scripts/update_kr_tickers.py  # 개발 필요
python3 -m modules.kis_data_collector --region KR
python3 scripts/backfill_fundamentals_dart.py --incremental
python3 scripts/calculate_dividend_yield.py
```

**장점**:
- ✅ 빠른 구현 (30분)
- ✅ 간단한 구조

**단점**:
- ❌ 에러 핸들링 약함
- ❌ 체크포인트 없음
- ❌ 진행 상황 추적 어려움

**권장 시나리오**: 임시 사용, 개발 환경

### Option C: 수동 실행

**현재 상태 유지**

**장점**:
- ✅ 개발 시간 불필요

**단점**:
- ❌ 운영 부담 증가
- ❌ 휴먼 에러 가능성
- ❌ 자동화 불가

**권장 시나리오**: 개발 초기 단계만

---

## 📊 종합 평가 매트릭스

| 평가 기준 | Option A (통합 스크립트) | Option B (Bash 래퍼) | Option C (수동 실행) |
|----------|-------------------------|---------------------|-------------------|
| **구현 난이도** | 🟡 Medium (4-5일) | 🟢 Low (30분) | 🟢 None |
| **운영 편의성** | 🟢 Excellent | 🟡 Good | 🔴 Poor |
| **에러 관리** | 🟢 Excellent | 🔴 Poor | 🔴 Poor |
| **확장성** | 🟢 Excellent | 🟡 Good | 🔴 Poor |
| **유지보수성** | 🟢 Excellent | 🟡 Good | 🔴 Poor |
| **자동화 가능성** | 🟢 Excellent | 🟡 Good | 🔴 None |
| **데이터 정합성** | 🟢 Excellent | 🟡 Good | 🟡 Good |
| **총점** | **9.5/10** | **6.5/10** | **2.5/10** |

---

## 🎯 최종 결론

### ✅ 권장 사항: **Option A - 통합 스크립트 개발**

**근거**:
1. **장기적 가치**: 초기 투자(4-5일) 대비 운영 효율성 대폭 개선
2. **확장성**: 향후 기능 추가 및 최적화 용이
3. **프로덕션 준비**: 에러 관리, 체크포인트, 모니터링 기능 내장
4. **자동화**: Cron job으로 완전 자동화 가능

### 📌 단계별 실행 계획

#### Step 1: 즉시 실행 가능 (현재)
```bash
# 임시 Bash 스크립트 사용 (Option B)
./scripts/daily_db_update.sh
```

#### Step 2: 통합 스크립트 개발 (1주일 내)
```python
# scripts/update_database.py 개발
# Phase 1 → Phase 2 → Phase 3 순차 진행
```

#### Step 3: 프로덕션 배포 (2주 후)
```bash
# Cron job 등록
0 6 * * * cd /Users/13ruce/spock && python3 scripts/update_database.py --incremental
```

---

**리포트 종료**

**다음 단계**: 통합 스크립트 개발 착수 여부 확인
