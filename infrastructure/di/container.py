"""
Dependency Injection Container

객체 간 의존성을 자동으로 관리하고 주입하는 컨테이너를 제공합니다.

Classes:
    DIContainer: 의존성 주입 컨테이너

Features:
    - 서비스 등록 및 관리
    - 싱글톤 패턴 지원
    - 의존성 자동 주입
    - 라이프사이클 관리

사용법:
    from infrastructure.di import DIContainer

    container = DIContainer()

    # 서비스 등록
    container.register('config', lambda: RefreshConfig.load())
    container.register(
        'pool_manager',
        lambda: ConnectionPoolManager(
            min_conn=container.get('config').min_connections
        )
    )

    # 서비스 사용
    config = container.get('config')
    pool_mgr = container.get('pool_manager')
"""

from typing import Dict, Callable, Any, Optional, List
from datetime import datetime
import logging

from infrastructure.exceptions import (
    InfrastructureException,
    SpockConfigurationError
)

logger = logging.getLogger(__name__)


class DIContainer:
    """
    의존성 주입 컨테이너

    객체 간 의존성을 자동으로 관리하고 주입합니다.

    Features:
        - 서비스 등록 및 검색
        - 싱글톤/트랜지언트 라이프사이클 지원
        - 의존성 그래프 관리
        - 순환 의존성 감지

    Example:
        >>> container = DIContainer()
        >>> container.register('config', lambda: RefreshConfig.load())
        >>> config = container.get('config')
        >>> print(config.min_connections)
        10
    """

    def __init__(self):
        """컨테이너 초기화"""
        self._factories: Dict[str, Callable] = {}
        self._singletons: Dict[str, Any] = {}
        self._singleton_flags: Dict[str, bool] = {}
        self._resolving: List[str] = []  # 순환 의존성 감지용
        self._created_at = datetime.now()

        logger.info(f"DIContainer initialized at {self._created_at}")

    def register(
        self,
        name: str,
        factory: Callable,
        singleton: bool = True
    ) -> 'DIContainer':
        """
        서비스 등록

        Args:
            name: 서비스 이름 (고유 식별자)
            factory: 객체 생성 함수
            singleton: 싱글톤 여부 (True면 한 번만 생성)

        Returns:
            self (메서드 체이닝 지원)

        Raises:
            SpockConfigurationError: 이미 등록된 서비스

        Example:
            >>> container.register('config', RefreshConfig.load)
            >>> container.register('pool_manager', lambda: ConnectionPoolManager())
        """
        if name in self._factories:
            raise SpockConfigurationError(
                f"Service '{name}' is already registered",
                details={
                    "service_name": name,
                    "existing_factory": str(self._factories[name])
                }
            )

        self._factories[name] = factory
        self._singleton_flags[name] = singleton

        logger.debug(
            f"Registered service: {name} "
            f"(singleton={singleton}, factory={factory.__name__})"
        )

        return self

    def get(self, name: str) -> Any:
        """
        서비스 가져오기

        Args:
            name: 서비스 이름

        Returns:
            등록된 서비스 인스턴스

        Raises:
            SpockConfigurationError: 등록되지 않은 서비스
            InfrastructureException: 순환 의존성 감지

        Example:
            >>> config = container.get('config')
            >>> pool_mgr = container.get('pool_manager')
        """
        if name not in self._factories:
            raise SpockConfigurationError(
                f"Service '{name}' not registered",
                details={
                    "service_name": name,
                    "registered_services": list(self._factories.keys())
                }
            )

        # 순환 의존성 감지
        if name in self._resolving:
            cycle = " -> ".join(self._resolving + [name])
            raise InfrastructureException(
                f"Circular dependency detected: {cycle}",
                details={
                    "service_name": name,
                    "dependency_chain": self._resolving.copy()
                }
            )

        # Singleton이면 캐시에서 반환
        if self._singleton_flags[name]:
            if name not in self._singletons:
                logger.debug(f"Creating singleton instance: {name}")

                # 순환 의존성 추적 시작
                self._resolving.append(name)
                try:
                    self._singletons[name] = self._factories[name]()
                    logger.info(f"Singleton created: {name}")
                finally:
                    # 추적 종료
                    self._resolving.remove(name)

            return self._singletons[name]

        # 매번 새로 생성 (Transient)
        logger.debug(f"Creating new instance: {name}")

        self._resolving.append(name)
        try:
            instance = self._factories[name]()
            logger.debug(f"Transient instance created: {name}")
            return instance
        finally:
            self._resolving.remove(name)

    def has(self, name: str) -> bool:
        """
        서비스 등록 여부 확인

        Args:
            name: 서비스 이름

        Returns:
            등록 여부

        Example:
            >>> if container.has('config'):
            ...     config = container.get('config')
        """
        return name in self._factories

    def clear(self, name: Optional[str] = None):
        """
        싱글톤 캐시 제거

        Args:
            name: 제거할 서비스 이름 (None이면 전체 제거)

        Example:
            >>> container.clear('pool_manager')  # 특정 서비스만 제거
            >>> container.clear()  # 모든 싱글톤 제거
        """
        if name is not None:
            if name in self._singletons:
                del self._singletons[name]
                logger.debug(f"Cleared singleton: {name}")
        else:
            count = len(self._singletons)
            self._singletons.clear()
            logger.info(f"Cleared all {count} singletons")

    def get_registered_services(self) -> List[str]:
        """
        등록된 모든 서비스 이름 반환

        Returns:
            서비스 이름 리스트

        Example:
            >>> services = container.get_registered_services()
            >>> print(services)
            ['config', 'pool_manager', 'tx_manager']
        """
        return list(self._factories.keys())

    def get_statistics(self) -> Dict[str, Any]:
        """
        컨테이너 통계 정보 반환

        Returns:
            통계 정보 딕셔너리

        Example:
            >>> stats = container.get_statistics()
            >>> print(f"Registered: {stats['total_registered']}")
            >>> print(f"Singletons: {stats['singleton_count']}")
        """
        singleton_services = [
            name for name, is_singleton in self._singleton_flags.items()
            if is_singleton
        ]

        return {
            "total_registered": len(self._factories),
            "singleton_count": len(singleton_services),
            "transient_count": len(self._factories) - len(singleton_services),
            "instantiated_singletons": len(self._singletons),
            "registered_services": self.get_registered_services(),
            "singleton_services": singleton_services,
            "created_at": self._created_at.isoformat()
        }

    def __repr__(self) -> str:
        """문자열 표현"""
        return (
            f"DIContainer("
            f"registered={len(self._factories)}, "
            f"singletons={len(self._singletons)})"
        )

    def __enter__(self):
        """컨텍스트 매니저 진입"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료 (정리)"""
        self.clear()
        return False
