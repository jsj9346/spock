"""
Concurrency control module for Spock platform.

Provides locking mechanisms to prevent duplicate operations
when multiple instances of spock_refresh.py are running.
"""

from .lock_manager import (
    LockManager,
    LockError,
    with_lock,
    cleanup_stale_locks,
    is_operation_locked,
    get_operation_info
)

__all__ = [
    'LockManager',
    'LockError',
    'with_lock',
    'cleanup_stale_locks',
    'is_operation_locked',
    'get_operation_info'
]
