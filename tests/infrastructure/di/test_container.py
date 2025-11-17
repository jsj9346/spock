"""
DIContainer 단위 테스트

Tests:
    - 서비스 등록 및 검색
    - 싱글톤 패턴
    - 트랜지언트 패턴
    - 순환 의존성 감지
    - 에러 처리
"""

import pytest
from infrastructure.di import DIContainer
from infrastructure.exceptions import (
    SpockConfigurationError,
    InfrastructureException
)


# ========================================
# Test Fixtures
# ========================================

class SimpleService:
    """간단한 테스트 서비스"""
    def __init__(self):
        self.value = "simple"


class DependentService:
    """의존성을 가진 테스트 서비스"""
    def __init__(self, simple_service: SimpleService):
        self.simple = simple_service


class CounterService:
    """호출 횟수를 추적하는 서비스"""
    call_count = 0

    def __init__(self):
        CounterService.call_count += 1
        self.instance_id = CounterService.call_count


@pytest.fixture
def container():
    """빈 컨테이너 생성"""
    return DIContainer()


@pytest.fixture
def configured_container():
    """미리 설정된 컨테이너 생성"""
    container = DIContainer()

    # SimpleService 등록
    container.register(
        'simple',
        lambda: SimpleService(),
        singleton=True
    )

    # DependentService 등록
    container.register(
        'dependent',
        lambda: DependentService(container.get('simple')),
        singleton=True
    )

    return container


# ========================================
# Basic Registration Tests
# ========================================

def test_register_service(container):
    """서비스 등록 테스트"""
    # Given: 빈 컨테이너
    # When: 서비스 등록
    result = container.register('test', lambda: SimpleService())

    # Then: 등록 성공 및 체이닝 지원
    assert result is container
    assert container.has('test')


def test_register_duplicate_service_fails(container):
    """중복 서비스 등록 실패 테스트"""
    # Given: 이미 등록된 서비스
    container.register('test', lambda: SimpleService())

    # When/Then: 중복 등록 시 예외 발생
    with pytest.raises(SpockConfigurationError) as exc_info:
        container.register('test', lambda: SimpleService())

    assert "already registered" in str(exc_info.value)


# ========================================
# Service Retrieval Tests
# ========================================

def test_get_service(configured_container):
    """서비스 가져오기 테스트"""
    # Given: 설정된 컨테이너
    # When: 서비스 요청
    service = configured_container.get('simple')

    # Then: 올바른 인스턴스 반환
    assert isinstance(service, SimpleService)
    assert service.value == "simple"


def test_get_unregistered_service_fails(container):
    """등록되지 않은 서비스 요청 실패 테스트"""
    # Given: 빈 컨테이너
    # When/Then: 존재하지 않는 서비스 요청 시 예외 발생
    with pytest.raises(SpockConfigurationError) as exc_info:
        container.get('nonexistent')

    assert "not registered" in str(exc_info.value)


# ========================================
# Singleton Pattern Tests
# ========================================

def test_singleton_returns_same_instance(container):
    """싱글톤 패턴 테스트 - 같은 인스턴스 반환"""
    # Given: 싱글톤으로 등록된 서비스
    CounterService.call_count = 0
    container.register(
        'counter',
        lambda: CounterService(),
        singleton=True
    )

    # When: 여러 번 요청
    service1 = container.get('counter')
    service2 = container.get('counter')
    service3 = container.get('counter')

    # Then: 모두 같은 인스턴스
    assert service1 is service2
    assert service2 is service3
    assert CounterService.call_count == 1


# ========================================
# Transient Pattern Tests
# ========================================

def test_transient_returns_new_instance(container):
    """트랜지언트 패턴 테스트 - 새 인스턴스 반환"""
    # Given: 트랜지언트로 등록된 서비스
    CounterService.call_count = 0
    container.register(
        'counter',
        lambda: CounterService(),
        singleton=False
    )

    # When: 여러 번 요청
    service1 = container.get('counter')
    service2 = container.get('counter')
    service3 = container.get('counter')

    # Then: 모두 다른 인스턴스
    assert service1 is not service2
    assert service2 is not service3
    assert CounterService.call_count == 3
    assert service1.instance_id == 1
    assert service2.instance_id == 2
    assert service3.instance_id == 3


# ========================================
# Dependency Injection Tests
# ========================================

def test_dependency_injection(configured_container):
    """의존성 자동 주입 테스트"""
    # Given: 의존성을 가진 서비스 등록
    # When: 서비스 요청
    dependent = configured_container.get('dependent')

    # Then: 의존성이 자동으로 주입됨
    assert isinstance(dependent, DependentService)
    assert isinstance(dependent.simple, SimpleService)
    assert dependent.simple.value == "simple"


def test_nested_dependencies(container):
    """중첩된 의존성 테스트"""
    # Given: A -> B -> C 의존성 구조
    container.register('c', lambda: SimpleService(), singleton=True)
    container.register(
        'b',
        lambda: DependentService(container.get('c')),
        singleton=True
    )
    container.register(
        'a',
        lambda: DependentService(container.get('b').simple),
        singleton=True
    )

    # When: 최상위 서비스 요청
    service_a = container.get('a')

    # Then: 모든 의존성이 올바르게 주입됨
    assert isinstance(service_a, DependentService)
    assert isinstance(service_a.simple, SimpleService)


# ========================================
# Circular Dependency Detection Tests
# ========================================

def test_circular_dependency_detected(container):
    """순환 의존성 감지 테스트"""
    # Given: A -> B -> A 순환 의존성
    container.register(
        'a',
        lambda: {'b': container.get('b')},
        singleton=True
    )
    container.register(
        'b',
        lambda: {'a': container.get('a')},
        singleton=True
    )

    # When/Then: 순환 의존성 감지
    with pytest.raises(InfrastructureException) as exc_info:
        container.get('a')

    assert "Circular dependency" in str(exc_info.value)


# ========================================
# Cache Management Tests
# ========================================

def test_clear_specific_singleton(container):
    """특정 싱글톤 캐시 제거 테스트"""
    # Given: 싱글톤 서비스
    CounterService.call_count = 0
    container.register('counter', lambda: CounterService(), singleton=True)

    # When: 첫 호출, 캐시 제거, 두 번째 호출
    service1 = container.get('counter')
    container.clear('counter')
    service2 = container.get('counter')

    # Then: 다른 인스턴스 반환
    assert service1 is not service2
    assert CounterService.call_count == 2


def test_clear_all_singletons(container):
    """모든 싱글톤 캐시 제거 테스트"""
    # Given: 여러 싱글톤 서비스
    CounterService.call_count = 0
    container.register('counter1', lambda: CounterService(), singleton=True)
    container.register('counter2', lambda: CounterService(), singleton=True)

    # When: 모든 서비스 호출, 캐시 제거, 다시 호출
    service1 = container.get('counter1')
    service2 = container.get('counter2')

    container.clear()

    service3 = container.get('counter1')
    service4 = container.get('counter2')

    # Then: 모두 새로운 인스턴스
    assert service1 is not service3
    assert service2 is not service4
    assert CounterService.call_count == 4


# ========================================
# Utility Methods Tests
# ========================================

def test_has_method(container):
    """has() 메서드 테스트"""
    # Given: 서비스 등록
    container.register('test', lambda: SimpleService())

    # Then: has() 올바르게 동작
    assert container.has('test') is True
    assert container.has('nonexistent') is False


def test_get_registered_services(container):
    """get_registered_services() 테스트"""
    # Given: 여러 서비스 등록
    container.register('service1', lambda: SimpleService())
    container.register('service2', lambda: SimpleService())
    container.register('service3', lambda: SimpleService())

    # When: 등록된 서비스 목록 요청
    services = container.get_registered_services()

    # Then: 모든 서비스 이름 반환
    assert len(services) == 3
    assert 'service1' in services
    assert 'service2' in services
    assert 'service3' in services


def test_get_statistics(container):
    """get_statistics() 테스트"""
    # Given: 싱글톤/트랜지언트 서비스 혼합 등록
    container.register('singleton1', lambda: SimpleService(), singleton=True)
    container.register('singleton2', lambda: SimpleService(), singleton=True)
    container.register('transient1', lambda: SimpleService(), singleton=False)

    # When: 싱글톤 하나 인스턴스화
    container.get('singleton1')

    # When: 통계 요청
    stats = container.get_statistics()

    # Then: 올바른 통계 반환
    assert stats['total_registered'] == 3
    assert stats['singleton_count'] == 2
    assert stats['transient_count'] == 1
    assert stats['instantiated_singletons'] == 1
    assert len(stats['registered_services']) == 3
    assert len(stats['singleton_services']) == 2


# ========================================
# Context Manager Tests
# ========================================

def test_context_manager(container):
    """컨텍스트 매니저 테스트"""
    # Given: 싱글톤 서비스 등록
    CounterService.call_count = 0
    container.register('counter', lambda: CounterService(), singleton=True)

    # When: 컨텍스트 매니저 사용
    with container as ctx:
        service1 = ctx.get('counter')
        assert CounterService.call_count == 1

    # Then: 컨텍스트 종료 후 캐시 제거
    service2 = container.get('counter')
    assert CounterService.call_count == 2


# ========================================
# String Representation Tests
# ========================================

def test_repr(container):
    """__repr__() 테스트"""
    # Given: 서비스 등록
    container.register('test1', lambda: SimpleService())
    container.register('test2', lambda: SimpleService())

    # When: repr 호출
    repr_str = repr(container)

    # Then: 정보 포함
    assert 'DIContainer' in repr_str
    assert 'registered=2' in repr_str


# ========================================
# Integration Tests
# ========================================

def test_method_chaining(container):
    """메서드 체이닝 테스트"""
    # When: 여러 서비스 연속 등록
    result = (
        container
        .register('service1', lambda: SimpleService())
        .register('service2', lambda: SimpleService())
        .register('service3', lambda: SimpleService())
    )

    # Then: 체이닝 성공 및 모든 서비스 등록됨
    assert result is container
    assert len(container.get_registered_services()) == 3
