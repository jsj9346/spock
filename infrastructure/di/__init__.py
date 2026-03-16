"""
Dependency Injection Module

의존성 주입 컨테이너 및 팩토리 함수를 제공합니다.

Modules:
    container: DIContainer 클래스
    factory: 프로덕션 컨테이너 생성 함수

사용법:
    from infrastructure.di import DIContainer, create_production_container

    # 방법 1: 직접 생성
    container = DIContainer()
    container.register('config', lambda: RefreshConfig.load())

    # 방법 2: 프로덕션 컨테이너 사용 (권장)
    container = create_production_container()
    config = container.get('config')
"""

from .container import DIContainer

__all__ = [
    "DIContainer",
    "create_production_container",
]


def create_production_container() -> DIContainer:
    """
    프로덕션용 DI Container 생성

    모든 인프라 컴포넌트를 자동으로 등록하고 연결합니다:
    - Configuration (RefreshConfig, UIConfig)
    - Database (ConnectionPoolManager, TransactionManager)
    - Repositories (향후 추가 예정)
    - Services (향후 추가 예정)

    Returns:
        설정된 DIContainer 인스턴스

    Example:
        >>> container = create_production_container()
        >>> config = container.get('config')
        >>> pool_mgr = container.get('pool_manager')
        >>> tx_mgr = container.get('tx_manager')

    Note:
        싱글톤으로 등록되므로 여러 번 get()을 호출해도
        같은 인스턴스가 반환됩니다.
    """
    from infrastructure.config import RefreshConfig, UIConfig
    from infrastructure.database import ConnectionPoolManager, TransactionManager
    from modules.db_manager_postgres import PostgresDatabaseManager

    container = DIContainer()

    # ========================================
    # Configuration
    # ========================================
    container.register(
        'config',
        lambda: RefreshConfig.load(),
        singleton=True
    )

    container.register(
        'ui_config',
        lambda: UIConfig.load(),
        singleton=True
    )

    # ========================================
    # Database
    # ========================================
    container.register(
        'pool_manager',
        lambda: ConnectionPoolManager(
            min_conn=10,  # Default from ConnectionPoolManager
            max_conn=30   # Default from ConnectionPoolManager
        ),
        singleton=True
    )

    container.register(
        'tx_manager',
        lambda: TransactionManager(container.get('pool_manager')),
        singleton=True
    )

    # ========================================
    # Production Database Manager (modules layer)
    # ========================================
    container.register(
        'db',
        lambda: PostgresDatabaseManager(),
        singleton=True
    )

    # ========================================
    # Repositories (향후 추가 예정)
    # ========================================
    # container.register(
    #     'ticker_repo',
    #     lambda: TickerRepository(container.get('tx_manager')),
    #     singleton=True
    # )

    # ========================================
    # Services (향후 추가 예정)
    # ========================================
    # container.register(
    #     'refresh_service',
    #     lambda: DatabaseRefreshService(
    #         container.get('tx_manager'),
    #         container.get('ticker_repo'),
    #         container.get('config')
    #     ),
    #     singleton=True
    # )

    return container


def create_test_container() -> DIContainer:
    """
    테스트용 DI Container 생성

    프로덕션과 동일한 구조이지만, Mock 객체로 교체 가능합니다.

    Returns:
        설정된 DIContainer 인스턴스

    Example:
        >>> container = create_test_container()
        >>> # Mock 객체로 교체
        >>> container.clear('tx_manager')
        >>> container.register('tx_manager', lambda: MockTransactionManager())
    """
    # 기본적으로 프로덕션과 동일
    return create_production_container()
