"""
Database Module

PostgreSQL + TimescaleDB 데이터베이스 관리 모듈

Modules:
    pool_manager: 연결 풀 관리
    transaction: 트랜잭션 관리

사용법:
    from infrastructure.database import ConnectionPoolManager, TransactionManager

    # 연결 풀 생성
    pool_mgr = ConnectionPoolManager(min_conn=10, max_conn=30)

    # 트랜잭션 관리자 생성
    tx_mgr = TransactionManager(pool_mgr)

    # 트랜잭션 사용
    with tx_mgr.transaction() as cursor:
        cursor.execute("INSERT INTO tickers ...")
        cursor.execute("UPDATE ticker_fundamentals ...")
"""

from .pool_manager import (
    ConnectionPoolManager,
    PoolStatistics
)

from .transaction import (
    TransactionManager,
    TransactionStatistics
)

__all__ = [
    # Pool Manager
    "ConnectionPoolManager",
    "PoolStatistics",

    # Transaction Manager
    "TransactionManager",
    "TransactionStatistics",
]
