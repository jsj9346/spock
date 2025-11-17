#!/usr/bin/env python3
"""
DI Container Usage Demo

DI Container를 사용하여 인프라 컴포넌트를 자동으로 관리하는 예제입니다.

실행 방법:
    python3 examples/di_container_demo.py

Features:
    - 자동 의존성 주입
    - 싱글톤 관리
    - 간소화된 코드
"""

import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# DI Container 사용
from infrastructure.di import create_production_container


def demo_basic_usage():
    """기본 사용법 데모"""
    print("=" * 60)
    print("1. 기본 사용법")
    print("=" * 60)

    # 컨테이너 생성 (한 번만!)
    container = create_production_container()

    # Config 가져오기
    config = container.get('config')
    print(f"✅ RefreshConfig 로드됨:")
    print(f"   - Log Level: {config.log_level}")
    print(f"   - Max Workers: {config.max_workers}")
    print(f"   - Lookback Days: {config.lookback_days}")
    print(f"   - Enabled Regions: {', '.join(config.enabled_regions)}")

    # UI Config 가져오기
    ui_config = container.get('ui_config')
    print(f"\n✅ UIConfig 로드됨:")
    print(f"   - App Name: {ui_config.app_name}")
    print(f"   - Version: {ui_config.version}")
    print(f"   - Emoji Enabled: {ui_config.emoji_enabled}")
    print(f"   - Colorama Enabled: {ui_config.colorama_enabled}")

    print()


def demo_singleton_pattern():
    """싱글톤 패턴 데모"""
    print("=" * 60)
    print("2. 싱글톤 패턴 (같은 인스턴스 재사용)")
    print("=" * 60)

    container = create_production_container()

    # 여러 번 get() 호출
    config1 = container.get('config')
    config2 = container.get('config')
    config3 = container.get('config')

    # 모두 같은 객체인지 확인
    print(f"✅ config1 is config2: {config1 is config2}")
    print(f"✅ config2 is config3: {config2 is config3}")
    print(f"✅ 메모리 주소: {id(config1)}")

    print()


def demo_dependency_injection():
    """의존성 자동 주입 데모"""
    print("=" * 60)
    print("3. 의존성 자동 주입")
    print("=" * 60)

    container = create_production_container()

    # Pool Manager는 Config에 의존함
    # 하지만 자동으로 주입됨!
    pool_mgr = container.get('pool_manager')
    print(f"✅ ConnectionPoolManager 생성됨:")
    print(f"   - Min Connections: {pool_mgr.min_conn}")
    print(f"   - Max Connections: {pool_mgr.max_conn}")
    print(f"   - Host: {pool_mgr.host}")
    print(f"   - Database: {pool_mgr.database}")

    # Transaction Manager는 Pool Manager에 의존함
    # 역시 자동으로 주입됨!
    tx_mgr = container.get('tx_manager')
    print(f"\n✅ TransactionManager 생성됨:")
    print(f"   - Pool Manager: {tx_mgr.pool_manager}")
    print(f"   - Statistics: {tx_mgr.statistics}")

    print()


def demo_container_statistics():
    """컨테이너 통계 데모"""
    print("=" * 60)
    print("4. 컨테이너 통계")
    print("=" * 60)

    container = create_production_container()

    # 몇 개 서비스 인스턴스화
    container.get('config')
    container.get('pool_manager')
    container.get('tx_manager')

    # 통계 확인
    stats = container.get_statistics()
    print(f"✅ 컨테이너 통계:")
    print(f"   - 등록된 서비스: {stats['total_registered']}")
    print(f"   - 싱글톤 서비스: {stats['singleton_count']}")
    print(f"   - 인스턴스화됨: {stats['instantiated_singletons']}")
    print(f"   - 생성 시각: {stats['created_at']}")

    print(f"\n✅ 등록된 서비스 목록:")
    for service in stats['registered_services']:
        print(f"   - {service}")

    print()


def demo_transaction_usage():
    """실제 트랜잭션 사용 예제"""
    print("=" * 60)
    print("5. 실제 트랜잭션 사용")
    print("=" * 60)

    container = create_production_container()

    # Transaction Manager 가져오기
    tx_mgr = container.get('tx_manager')

    try:
        # Health Check
        pool_mgr = container.get('pool_manager')
        if pool_mgr.health_check():
            print("✅ 데이터베이스 연결 정상")

            # 실제 트랜잭션 예제
            with tx_mgr.transaction() as cursor:
                cursor.execute("""
                    SELECT
                        region,
                        COUNT(*) as count
                    FROM tickers
                    GROUP BY region
                    ORDER BY count DESC
                    LIMIT 5
                """)
                results = cursor.fetchall()

                print("\n✅ Ticker 통계 (상위 5개 지역):")
                for region, count in results:
                    print(f"   - {region}: {count:,} tickers")

            # 트랜잭션 통계
            tx_stats = tx_mgr.get_statistics()
            print(f"\n✅ 트랜잭션 통계:")
            print(f"   - 총 트랜잭션: {tx_stats['total_transactions']}")
            print(f"   - 커밋됨: {tx_stats['committed_transactions']}")
            print(f"   - 성공률: {tx_stats['success_rate']:.1f}%")

        else:
            print("⚠️  데이터베이스 연결 실패 (정상 동작)")

    except Exception as e:
        print(f"⚠️  예상된 오류: {type(e).__name__}: {str(e)}")
        print("   (데이터베이스가 실행 중이 아닐 수 있습니다)")

    print()


def demo_without_di_vs_with_di():
    """DI Container 사용 전후 비교"""
    print("=" * 60)
    print("6. DI Container 사용 전후 비교")
    print("=" * 60)

    print("❌ DI Container 없이 (수동 연결):")
    print("""
    from infrastructure.config import RefreshConfig
    from infrastructure.database import ConnectionPoolManager, TransactionManager

    # 매번 이렇게 수동으로 생성해야 함
    config = RefreshConfig.load()
    pool_mgr = ConnectionPoolManager(
        min_conn=config.min_connections,
        max_conn=config.max_connections,
        host=config.db_host,
        # ... 더 많은 파라미터
    )
    tx_mgr = TransactionManager(pool_mgr)

    # 코드 중복!
    # 순서 관리 필요!
    # 테스트 어려움!
    """)

    print("\n✅ DI Container 사용:")
    print("""
    from infrastructure.di import create_production_container

    # 한 번만!
    container = create_production_container()

    # 간단하게 가져오기
    config = container.get('config')
    pool_mgr = container.get('pool_manager')
    tx_mgr = container.get('tx_manager')

    # 자동 연결!
    # 싱글톤 자동 관리!
    # 테스트 쉬움!
    """)

    print()


def main():
    """메인 함수"""
    print("\n" + "=" * 60)
    print("DI Container Demo - Phase 4 Infrastructure")
    print(f"실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    try:
        # 1. 기본 사용법
        demo_basic_usage()

        # 2. 싱글톤 패턴
        demo_singleton_pattern()

        # 3. 의존성 자동 주입
        demo_dependency_injection()

        # 4. 컨테이너 통계
        demo_container_statistics()

        # 5. 실제 트랜잭션 사용
        demo_transaction_usage()

        # 6. 사용 전후 비교
        demo_without_di_vs_with_di()

        print("=" * 60)
        print("✅ 모든 데모 완료!")
        print("=" * 60)
        print()

    except Exception as e:
        print(f"\n❌ 오류 발생: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
