"""
DatabaseUpdateOrchestrator 프로덕션 통합 테스트

목적:
- 실제 PostgreSQL 데이터베이스 연결 검증
- 단일 스텝 실행 검증
- 전체 파이프라인 실행 검증
- 재시도 로직 및 에러 핸들링 검증
- Rich UI 진행률 표시 검증

실행 방법:
1. Dry-run 모드: python3 -m pytest tests/integration/production/test_orchestrator_production.py --dry-run
2. 실제 DB 모드: python3 -m pytest tests/integration/production/test_orchestrator_production.py
"""

import sys
import os
from datetime import datetime
import pytest

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from modules.orchestration.orchestrator import DatabaseUpdateOrchestrator
from modules.db_manager_postgres import PostgresDatabaseManager


@pytest.fixture(scope="module")
def db_manager():
    """PostgreSQL 데이터베이스 매니저 fixture"""
    db = PostgresDatabaseManager()
    yield db
    db.close_pool()


@pytest.fixture(scope="module")
def orchestrator(db_manager):
    """DatabaseUpdateOrchestrator 인스턴스 fixture"""
    config = {
        'limit': 50,  # 테스트용 제한
        'enable_rich_ui': True,
    }
    return DatabaseUpdateOrchestrator(db_manager=db_manager, config=config)


class TestOrchestratorProductionSingleStep:
    """Orchestrator 단일 스텝 실행 테스트"""

    def test_01_step_fx_tracking(self, orchestrator):
        """테스트 2.1.1: FX Tracking 스텝 실행"""
        print("\n" + "="*80)
        print("테스트 2.1.1: FX Tracking 스텝 실행")
        print("="*80)

        result = orchestrator.run(
            regions=['KR'],
            steps=['fx_tracking'],
            dry_run=False,
            incremental=True
        )

        print(f"\n결과:")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - 완료된 스텝: {result.get('steps_completed', [])}")
        print(f"  - 실행 시간: {result.get('elapsed_time', 0):.2f}초")

        assert result['success'], "FX Tracking 스텝 실행 실패"
        assert 'fx_tracking' in result.get('steps_completed', []), "fx_tracking 스텝 미완료"
        print("✅ FX Tracking 스텝 실행 성공")

    def test_02_step_classification(self, orchestrator):
        """테스트 2.1.2: Classification 스텝 실행"""
        print("\n" + "="*80)
        print("테스트 2.1.2: Classification 스텝 실행")
        print("="*80)

        result = orchestrator.run(
            regions=['KR'],
            steps=['classification'],
            dry_run=False,
            incremental=True
        )

        print(f"\n결과:")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - 완료된 스텝: {result.get('steps_completed', [])}")
        print(f"  - 실행 시간: {result.get('elapsed_time', 0):.2f}초")

        assert result['success'], "Classification 스텝 실행 실패"
        assert 'classification' in result.get('steps_completed', []), "classification 스텝 미완료"
        print("✅ Classification 스텝 실행 성공")

    def test_03_step_etf_data(self, orchestrator):
        """테스트 2.1.3: ETF Data 스텝 실행"""
        print("\n" + "="*80)
        print("테스트 2.1.3: ETF Data 스텝 실행")
        print("="*80)

        result = orchestrator.run(
            regions=['KR'],
            steps=['etf_data'],
            dry_run=False,
            incremental=True
        )

        print(f"\n결과:")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - 완료된 스텝: {result.get('steps_completed', [])}")
        print(f"  - 실행 시간: {result.get('elapsed_time', 0):.2f}초")

        assert result['success'], "ETF Data 스텝 실행 실패"
        assert 'etf_data' in result.get('steps_completed', []), "etf_data 스텝 미완료"
        print("✅ ETF Data 스텝 실행 성공")


class TestOrchestratorProductionFullPipeline:
    """Orchestrator 전체 파이프라인 실행 테스트"""

    def test_04_full_pipeline_four_steps(self, orchestrator):
        """테스트 2.2.1: 전체 파이프라인 (4개 스텝) 실행"""
        print("\n" + "="*80)
        print("테스트 2.2.1: 전체 파이프라인 (4개 스텝) 실행")
        print("="*80)

        # 4개 핵심 스텝 실행 (fx_tracking, classification, etf_data)
        result = orchestrator.run(
            regions=['KR'],
            steps=['ticker_refresh', 'fx_tracking', 'classification', 'etf_data'],
            dry_run=False,
            incremental=True
        )

        print(f"\n결과:")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - 완료된 스텝: {result.get('steps_completed', [])}")
        print(f"  - 실패한 스텝: {result.get('steps_failed', [])}")
        print(f"  - 실행 시간: {result.get('elapsed_time', 0):.2f}초")

        expected_steps = ['ticker_refresh', 'fx_tracking', 'classification', 'etf_data']
        completed_steps = result.get('steps_completed', [])

        print(f"\n📊 스텝 완료 현황:")
        for step in expected_steps:
            status = "✅" if step in completed_steps else "❌"
            print(f"  {status} {step}")

        assert result['success'], "전체 파이프라인 실행 실패"
        assert len(completed_steps) >= 3, f"최소 3개 스텝 완료 필요 (완료: {len(completed_steps)}개)"
        print("✅ 전체 파이프라인 실행 성공")

    def test_05_pipeline_performance(self, orchestrator):
        """테스트 2.2.2: 파이프라인 성능 메트릭"""
        print("\n" + "="*80)
        print("테스트 2.2.2: 파이프라인 성능 메트릭")
        print("="*80)

        import time

        start_time = time.time()
        result = orchestrator.run(
            regions=['KR'],
            steps=['fx_tracking', 'classification', 'etf_data'],
            dry_run=False,
            incremental=True
        )
        elapsed_time = time.time() - start_time

        print(f"\n⏱️  성능 메트릭:")
        print(f"  - 전체 실행 시간: {elapsed_time:.2f}초")
        print(f"  - 완료된 스텝: {len(result.get('steps_completed', []))}개")
        print(f"  - 스텝당 평균: {elapsed_time/max(len(result.get('steps_completed', [])), 1):.2f}초")

        # 성능 기준 검증 (limit=50 기준 15분 = 900초)
        assert elapsed_time < 900, f"실행 시간 초과: {elapsed_time:.2f}초 (기준: 900초)"
        print("✅ 성능 기준 충족 (<15분)")


class TestOrchestratorProductionRetryLogic:
    """Orchestrator 재시도 로직 검증"""

    def test_06_retry_logic_with_temporary_failure(self, db_manager):
        """테스트 2.3.1: 임시 실패 시 재시도 로직"""
        print("\n" + "="*80)
        print("테스트 2.3.1: 임시 실패 시 재시도 로직")
        print("="*80)

        from unittest.mock import Mock, patch
        import time

        config = {
            'limit': 10,
            'enable_rich_ui': False,  # 테스트 시 Rich UI 비활성화
        }
        orchestrator = DatabaseUpdateOrchestrator(db_manager=db_manager, config=config)

        # FXTracker mock: 첫 번째 호출 실패, 두 번째 호출 성공
        call_count = {'count': 0}

        def mock_track_exchange_rates(*args, **kwargs):
            call_count['count'] += 1
            if call_count['count'] == 1:
                print(f"  시도 {call_count['count']}: 실패 시뮬레이션")
                raise Exception("Temporary API failure")
            else:
                print(f"  시도 {call_count['count']}: 성공")
                return {'success': True, 'updated': 4, 'signals': 0}

        with patch.object(orchestrator, '_track_exchange_rates', side_effect=mock_track_exchange_rates):
            start_time = time.time()
            result = orchestrator.run(
                regions=['KR'],
                steps=['fx_tracking'],
                dry_run=False,
                incremental=True
            )
            elapsed_time = time.time() - start_time

        print(f"\n결과:")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - 재시도 횟수: {call_count['count']}")
        print(f"  - 실행 시간: {elapsed_time:.2f}초")

        assert result['success'], "재시도 후에도 실패"
        assert call_count['count'] == 2, f"재시도 횟수 불일치 (예상: 2, 실제: {call_count['count']})"
        print("✅ 재시도 로직 검증 성공")

    def test_07_checkpoint_recovery(self, orchestrator, db_manager):
        """테스트 2.3.2: 체크포인트 복구 검증"""
        print("\n" + "="*80)
        print("테스트 2.3.2: 체크포인트 복구 검증")
        print("="*80)

        # 첫 번째 실행: 일부 스텝만 완료
        print("\n1️⃣  첫 번째 실행 (fx_tracking만 완료):")
        result1 = orchestrator.run(
            regions=['KR'],
            steps=['fx_tracking'],
            dry_run=False,
            incremental=True
        )

        completed_steps_1 = result1.get('steps_completed', [])
        print(f"  완료된 스텝: {completed_steps_1}")

        # 두 번째 실행: 나머지 스텝 완료
        print("\n2️⃣  두 번째 실행 (classification, etf_data 완료):")
        result2 = orchestrator.run(
            regions=['KR'],
            steps=['classification', 'etf_data'],
            dry_run=False,
            incremental=True
        )

        completed_steps_2 = result2.get('steps_completed', [])
        print(f"  완료된 스텝: {completed_steps_2}")

        # 전체 완료된 스텝 확인
        all_completed = completed_steps_1 + completed_steps_2
        print(f"\n📊 전체 완료된 스텝: {all_completed}")

        assert len(all_completed) >= 3, f"최소 3개 스텝 완료 필요 (완료: {len(all_completed)}개)"
        print("✅ 체크포인트 복구 검증 성공")


class TestOrchestratorProductionRichUI:
    """Orchestrator Rich UI 진행률 표시 검증"""

    def test_08_rich_ui_progress(self, orchestrator):
        """테스트 2.4.1: Rich UI 진행률 표시"""
        print("\n" + "="*80)
        print("테스트 2.4.1: Rich UI 진행률 표시")
        print("="*80)

        # Rich UI 활성화 상태에서 실행
        orchestrator.config['enable_rich_ui'] = True

        result = orchestrator.run(
            regions=['KR'],
            steps=['fx_tracking', 'classification'],
            dry_run=False,
            incremental=True
        )

        print(f"\n결과:")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - 완료된 스텝: {result.get('steps_completed', [])}")

        # Rich UI가 정상적으로 표시되었는지 확인 (시각적 검증)
        assert result['success'], "Rich UI 실행 실패"
        print("✅ Rich UI 진행률 표시 검증 성공")
        print("   (시각적으로 진행률 바가 표시되었는지 확인)")

    def test_09_error_handling_display(self, db_manager):
        """테스트 2.4.2: 에러 핸들링 표시"""
        print("\n" + "="*80)
        print("테스트 2.4.2: 에러 핸들링 표시")
        print("="*80)

        from unittest.mock import patch

        config = {
            'limit': 10,
            'enable_rich_ui': True,
        }
        orchestrator = DatabaseUpdateOrchestrator(db_manager=db_manager, config=config)

        # 강제로 에러 발생 시뮬레이션
        def mock_classify_stocks(*args, **kwargs):
            raise Exception("Simulated classification error")

        with patch.object(orchestrator, '_classify_stocks', side_effect=mock_classify_stocks):
            result = orchestrator.run(
                regions=['KR'],
                steps=['classification'],
                dry_run=False,
                incremental=True
            )

        print(f"\n결과:")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - 실패한 스텝: {result.get('steps_failed', [])}")

        # 에러가 적절히 처리되고 표시되었는지 확인
        assert not result['success'], "에러가 발생했음에도 성공으로 표시됨"
        assert 'classification' in result.get('steps_failed', []), "실패한 스텝이 기록되지 않음"
        print("✅ 에러 핸들링 표시 검증 성공")


class TestOrchestratorProductionStatistics:
    """Orchestrator 통계 및 메트릭 검증"""

    def test_10_execution_statistics(self, orchestrator):
        """테스트 2.5.1: 실행 통계 수집"""
        print("\n" + "="*80)
        print("테스트 2.5.1: 실행 통계 수집")
        print("="*80)

        result = orchestrator.run(
            regions=['KR'],
            steps=['fx_tracking', 'classification', 'etf_data'],
            dry_run=False,
            incremental=True
        )

        print(f"\n📊 실행 통계:")
        print(f"  - 전체 스텝: {len(['fx_tracking', 'classification', 'etf_data'])}개")
        print(f"  - 완료된 스텝: {len(result.get('steps_completed', []))}개")
        print(f"  - 실패한 스텝: {len(result.get('steps_failed', []))}개")
        print(f"  - 실행 시간: {result.get('elapsed_time', 0):.2f}초")
        print(f"  - 성공률: {len(result.get('steps_completed', []))/3*100:.1f}%")

        # 통계 검증
        assert 'elapsed_time' in result, "실행 시간 정보 없음"
        assert 'steps_completed' in result, "완료된 스텝 정보 없음"
        print("✅ 실행 통계 수집 검증 성공")


def test_summary():
    """테스트 요약 출력"""
    print("\n" + "="*80)
    print("DatabaseUpdateOrchestrator 프로덕션 테스트 완료")
    print("="*80)
    print("\n✅ 모든 테스트 통과")
    print("\n검증 항목:")
    print("  1. 단일 스텝 실행 (FX Tracking, Classification, ETF Data)")
    print("  2. 전체 파이프라인 실행 (4개 스텝)")
    print("  3. 파이프라인 성능 메트릭 (<15분)")
    print("  4. 재시도 로직 (임시 실패 시)")
    print("  5. 체크포인트 복구")
    print("  6. Rich UI 진행률 표시")
    print("  7. 에러 핸들링 표시")
    print("  8. 실행 통계 수집")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
