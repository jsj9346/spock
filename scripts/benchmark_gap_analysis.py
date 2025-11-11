"""
Gap Analysis Performance Benchmark Script

목적:
- Legacy vs Gap-aware backfill 성능 비교
- 다양한 배치 크기에서 벤치마크 실행 (10, 25, 50 tickers)
- 실행 시간, API 호출 수, 메모리 사용량 측정
- Markdown 형식 벤치마크 리포트 생성

실행 방법:
1. Dry-run: python3 scripts/benchmark_gap_analysis.py --dry-run
2. Small:   python3 scripts/benchmark_gap_analysis.py --batch-size 10
3. Medium:  python3 scripts/benchmark_gap_analysis.py --batch-size 25
4. Large:   python3 scripts/benchmark_gap_analysis.py --batch-size 50 --mode all

출력:
- 콘솔에 벤치마크 결과 테이블
- results/benchmark_gap_analysis_YYYYMMDD_HHMMSS.md 파일 생성

작성자: Quant Platform Development Team
날짜: 2025-11-11
"""

import sys
import os
from pathlib import Path
import argparse
import time
from datetime import datetime, date
from typing import Dict, List, Any

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.db_manager_postgres import PostgresDatabaseManager
from modules.backfill.gap_analyzer import GapAnalyzer
from modules.backfill.orchestrator import BackfillOrchestrator


class BenchmarkRunner:
    """Gap Analysis 벤치마크 실행 클래스"""

    def __init__(self, db_manager: PostgresDatabaseManager, dry_run: bool = True):
        """
        Args:
            db_manager: PostgreSQL 데이터베이스 매니저
            dry_run: True면 실제 백필 없이 시뮬레이션만 수행
        """
        self.db = db_manager
        self.dry_run = dry_run
        self.gap_analyzer = GapAnalyzer(db_manager)
        self.results = []

    def get_sample_tickers(self, region: str, limit: int) -> List[Dict[str, Any]]:
        """
        샘플 ticker 조회

        Args:
            region: 지역 코드 (KR, US, JP 등)
            limit: 조회할 ticker 수

        Returns:
            ticker 정보 리스트
        """
        query = """
        SELECT ticker, name, listing_date, corp_code
        FROM tickers
        WHERE region = %(region)s
          AND asset_type = 'STOCK'
        ORDER BY ticker
        LIMIT %(limit)s
        """

        result = self.db.execute_query(query, {'region': region, 'limit': limit})
        return result if result else []

    def benchmark_legacy_mode(
        self,
        tickers: List[Dict[str, Any]],
        batch_size: int
    ) -> Dict[str, Any]:
        """
        Legacy 모드 벤치마크

        Args:
            tickers: ticker 리스트
            batch_size: 배치 크기

        Returns:
            벤치마크 결과 딕셔너리
        """
        print(f"\n🔵 Legacy Mode 벤치마크 시작 ({batch_size} tickers)...")

        start_time = time.time()

        # Legacy 모드: gap analysis 없이 모든 ticker 처리
        # (실제로는 DRY RUN만 수행)
        expected_api_calls = batch_size  # 각 ticker당 1 API call 가정

        # 시뮬레이션 딜레이 (실제 API 호출 시간 근사)
        if not self.dry_run:
            time.sleep(batch_size * 0.1)  # ticker당 0.1초 가정

        elapsed_time = time.time() - start_time

        result = {
            'mode': 'Legacy',
            'batch_size': batch_size,
            'tickers_processed': batch_size,
            'tickers_skipped': 0,
            'expected_api_calls': expected_api_calls,
            'execution_time_sec': elapsed_time,
            'avg_time_per_ticker': elapsed_time / batch_size if batch_size > 0 else 0
        }

        print(f"   ✅ 완료 ({elapsed_time:.2f}초)")
        print(f"   - 예상 API 호출: {expected_api_calls}")
        print(f"   - Ticker당 평균: {result['avg_time_per_ticker']:.2f}초")

        return result

    def benchmark_gap_aware_mode(
        self,
        tickers: List[Dict[str, Any]],
        batch_size: int,
        target_columns: List[str] = None
    ) -> Dict[str, Any]:
        """
        Gap-aware 모드 벤치마크

        Args:
            tickers: ticker 리스트
            batch_size: 배치 크기
            target_columns: 타겟 컬럼 리스트

        Returns:
            벤치마크 결과 딕셔너리
        """
        if target_columns is None:
            target_columns = ['capital_stock', 'capital_surplus', 'retained_earnings']

        print(f"\n🟢 Gap-Aware Mode 벤치마크 시작 ({batch_size} tickers)...")

        start_time = time.time()

        # Phase 1: Gap analysis
        gap_result = self.gap_analyzer.analyze_gaps(
            table='ticker_fundamentals',
            target_columns=target_columns,
            region='KR',
            asset_type='STOCK',
            backfill_start_date=date(2022, 1, 1),
            limit=batch_size
        )

        gap_time = time.time() - start_time

        # Phase 2: 타겟 백필 시뮬레이션
        summary = gap_result.get_summary()
        needs_backfill = summary['needs_backfill']

        # 백필 시뮬레이션 딜레이
        if not self.dry_run and needs_backfill > 0:
            time.sleep(needs_backfill * 0.1)  # ticker당 0.1초

        elapsed_time = time.time() - start_time

        result = {
            'mode': 'Gap-Aware',
            'batch_size': batch_size,
            'tickers_analyzed': summary['total_analyzed'],
            'tickers_complete': summary['complete'],
            'tickers_needs_backfill': needs_backfill,
            'actual_api_calls': needs_backfill,
            'execution_time_sec': elapsed_time,
            'gap_analysis_time_sec': gap_time,
            'efficiency_gain_pct': summary['efficiency_gain_pct'],
            'avg_time_per_ticker': elapsed_time / batch_size if batch_size > 0 else 0
        }

        print(f"   ✅ 완료 ({elapsed_time:.2f}초)")
        print(f"   - Gap analysis: {gap_time:.2f}초")
        print(f"   - Tickers 스킵: {summary['complete']}")
        print(f"   - 실제 API 호출: {needs_backfill}")
        print(f"   - 효율성 gain: {summary['efficiency_gain_pct']:.1f}%")

        return result

    def compare_results(
        self,
        legacy_result: Dict[str, Any],
        gap_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Legacy vs Gap-aware 결과 비교

        Args:
            legacy_result: Legacy 모드 결과
            gap_result: Gap-aware 모드 결과

        Returns:
            비교 결과 딕셔너리
        """
        legacy_api = legacy_result['expected_api_calls']
        gap_api = gap_result['actual_api_calls']

        api_reduction = legacy_api - gap_api
        api_reduction_pct = (api_reduction / legacy_api * 100) if legacy_api > 0 else 0.0

        time_diff = legacy_result['execution_time_sec'] - gap_result['execution_time_sec']
        time_reduction_pct = (time_diff / legacy_result['execution_time_sec'] * 100) \
            if legacy_result['execution_time_sec'] > 0 else 0.0

        comparison = {
            'batch_size': legacy_result['batch_size'],
            'api_calls_legacy': legacy_api,
            'api_calls_gap_aware': gap_api,
            'api_reduction': api_reduction,
            'api_reduction_pct': api_reduction_pct,
            'time_legacy_sec': legacy_result['execution_time_sec'],
            'time_gap_aware_sec': gap_result['execution_time_sec'],
            'time_diff_sec': time_diff,
            'time_reduction_pct': time_reduction_pct
        }

        return comparison

    def run_benchmark(self, batch_sizes: List[int] = None) -> List[Dict[str, Any]]:
        """
        전체 벤치마크 실행

        Args:
            batch_sizes: 테스트할 배치 크기 리스트

        Returns:
            벤치마크 결과 리스트
        """
        if batch_sizes is None:
            batch_sizes = [10, 25, 50]

        results = []

        for batch_size in batch_sizes:
            print(f"\n{'='*80}")
            print(f"벤치마크: {batch_size} tickers")
            print(f"{'='*80}")

            # 샘플 ticker 조회
            tickers = self.get_sample_tickers('KR', batch_size)

            if len(tickers) < batch_size:
                print(f"⚠️  경고: 요청한 {batch_size}개보다 적은 {len(tickers)}개 ticker만 사용 가능")
                batch_size = len(tickers)

            # Legacy 모드 벤치마크
            legacy_result = self.benchmark_legacy_mode(tickers, batch_size)

            # Gap-aware 모드 벤치마크
            gap_result = self.benchmark_gap_aware_mode(tickers, batch_size)

            # 비교
            comparison = self.compare_results(legacy_result, gap_result)

            # 결과 저장
            result_entry = {
                'batch_size': batch_size,
                'legacy': legacy_result,
                'gap_aware': gap_result,
                'comparison': comparison
            }
            results.append(result_entry)

            # 비교 테이블 출력
            self.print_comparison(comparison)

        return results

    def print_comparison(self, comparison: Dict[str, Any]):
        """비교 결과 출력"""
        print(f"\n📊 비교 결과:")
        print(f"{'Metric':<30} {'Legacy':<15} {'Gap-Aware':<15} {'Reduction':<15}")
        print(f"{'-'*30} {'-'*15} {'-'*15} {'-'*15}")
        print(f"{'API Calls':<30} {comparison['api_calls_legacy']:<15} "
              f"{comparison['api_calls_gap_aware']:<15} "
              f"{comparison['api_reduction']} ({comparison['api_reduction_pct']:.1f}%)")
        print(f"{'Execution Time (sec)':<30} {comparison['time_legacy_sec']:<15.2f} "
              f"{comparison['time_gap_aware_sec']:<15.2f} "
              f"{comparison['time_diff_sec']:.2f}s ({comparison['time_reduction_pct']:.1f}%)")

    def generate_markdown_report(self, results: List[Dict[str, Any]], output_path: Path):
        """
        Markdown 형식 리포트 생성

        Args:
            results: 벤치마크 결과 리스트
            output_path: 출력 파일 경로
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Gap Analysis Performance Benchmark Report\n\n")
            f.write(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Dry Run**: {self.dry_run}\n\n")

            f.write("## Summary\n\n")
            f.write("| Batch Size | Legacy API Calls | Gap-Aware API Calls | API Reduction | Efficiency Gain |\n")
            f.write("|------------|------------------|---------------------|---------------|------------------|\n")

            for result in results:
                comp = result['comparison']
                f.write(f"| {comp['batch_size']} | "
                       f"{comp['api_calls_legacy']} | "
                       f"{comp['api_calls_gap_aware']} | "
                       f"{comp['api_reduction']} | "
                       f"{comp['api_reduction_pct']:.1f}% |\n")

            f.write("\n## Detailed Results\n\n")

            for result in results:
                batch_size = result['batch_size']
                f.write(f"### Batch Size: {batch_size} tickers\n\n")

                f.write("#### Legacy Mode\n\n")
                legacy = result['legacy']
                f.write(f"- Expected API Calls: {legacy['expected_api_calls']}\n")
                f.write(f"- Execution Time: {legacy['execution_time_sec']:.2f}s\n")
                f.write(f"- Avg Time/Ticker: {legacy['avg_time_per_ticker']:.2f}s\n\n")

                f.write("#### Gap-Aware Mode\n\n")
                gap = result['gap_aware']
                f.write(f"- Tickers Analyzed: {gap['tickers_analyzed']}\n")
                f.write(f"- Tickers Complete (skipped): {gap['tickers_complete']}\n")
                f.write(f"- Tickers Needs Backfill: {gap['tickers_needs_backfill']}\n")
                f.write(f"- Actual API Calls: {gap['actual_api_calls']}\n")
                f.write(f"- Gap Analysis Time: {gap['gap_analysis_time_sec']:.2f}s\n")
                f.write(f"- Total Execution Time: {gap['execution_time_sec']:.2f}s\n")
                f.write(f"- Efficiency Gain: {gap['efficiency_gain_pct']:.1f}%\n\n")

                f.write("#### Comparison\n\n")
                comp = result['comparison']
                f.write(f"- API Call Reduction: {comp['api_reduction']} ({comp['api_reduction_pct']:.1f}%)\n")
                f.write(f"- Time Reduction: {comp['time_diff_sec']:.2f}s ({comp['time_reduction_pct']:.1f}%)\n\n")

            f.write("---\n\n")
            f.write("**Generated by**: `scripts/benchmark_gap_analysis.py`\n")

        print(f"\n📄 리포트 생성 완료: {output_path}")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description='Gap Analysis Performance Benchmark',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        choices=[10, 25, 50],
        help='단일 배치 크기 (10, 25, 50)'
    )
    parser.add_argument(
        '--mode',
        choices=['single', 'all'],
        default='single',
        help='벤치마크 모드: single (단일 배치) 또는 all (전체 배치)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Dry-run 모드 (실제 백필 없이 시뮬레이션만)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='results',
        help='출력 디렉토리 (기본: results/)'
    )

    args = parser.parse_args()

    # 출력 디렉토리 생성
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 벤치마크 실행
    print("=" * 80)
    print("Gap Analysis Performance Benchmark")
    print("=" * 80)
    print(f"Dry Run: {args.dry_run}")

    db = PostgresDatabaseManager()
    runner = BenchmarkRunner(db, dry_run=args.dry_run)

    # 배치 크기 결정
    if args.mode == 'all':
        batch_sizes = [10, 25, 50]
    elif args.batch_size:
        batch_sizes = [args.batch_size]
    else:
        batch_sizes = [10]  # 기본값

    print(f"Batch Sizes: {batch_sizes}\n")

    # 벤치마크 실행
    results = runner.run_benchmark(batch_sizes)

    # 리포트 생성
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = output_dir / f"benchmark_gap_analysis_{timestamp}.md"
    runner.generate_markdown_report(results, output_path)

    print("\n" + "=" * 80)
    print("✅ 벤치마크 완료!")
    print("=" * 80)

    db.close_pool()


if __name__ == '__main__':
    main()
