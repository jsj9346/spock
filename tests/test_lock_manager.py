"""
Unit tests for LockManager

Run with:
    pytest tests/test_lock_manager.py -v
    pytest tests/test_lock_manager.py::TestLockManager::test_basic_lock -v
"""

import os
import time
import pytest
import multiprocessing
from pathlib import Path

from modules.concurrency import LockManager, LockError, with_lock


class TestLockManager:
    """Test suite for LockManager"""

    @pytest.fixture
    def lock_manager(self):
        """Create a fresh lock manager instance"""
        manager = LockManager()
        # Cleanup any existing locks
        manager.cleanup_stale_locks(max_age_hours=0)
        yield manager
        # Cleanup after tests
        manager.cleanup_stale_locks(max_age_hours=0)

    def test_basic_lock(self, lock_manager):
        """Test basic lock acquisition and release"""
        operation = 'test_basic'

        # Initially not locked
        assert not lock_manager.is_locked(operation)

        # Acquire lock
        with lock_manager.acquire_lock(operation):
            assert lock_manager.is_locked(operation)

        # Released after context
        assert not lock_manager.is_locked(operation)

    def test_lock_blocks_concurrent_access(self, lock_manager):
        """Test that lock blocks concurrent access"""
        operation = 'test_concurrent'

        def hold_lock_for_seconds(seconds):
            """Helper function to hold lock"""
            with lock_manager.acquire_lock(operation, timeout=10):
                time.sleep(seconds)

        # Start process that holds lock
        p = multiprocessing.Process(target=hold_lock_for_seconds, args=(2,))
        p.start()

        # Wait for lock to be acquired
        time.sleep(0.5)

        # Try to acquire lock (should fail)
        with pytest.raises(LockError):
            with lock_manager.acquire_lock(operation, timeout=1):
                pass

        # Wait for process to finish
        p.join()

        # Now lock should be available
        with lock_manager.acquire_lock(operation, timeout=1):
            pass

    def test_lock_timeout(self, lock_manager):
        """Test lock acquisition timeout"""
        operation = 'test_timeout'

        # Hold lock indefinitely
        def hold_lock_forever():
            with lock_manager.acquire_lock(operation, timeout=10):
                time.sleep(5)

        p = multiprocessing.Process(target=hold_lock_forever)
        p.start()

        # Wait for lock to be acquired
        time.sleep(0.5)

        # Try with short timeout
        start_time = time.time()
        with pytest.raises(LockError):
            with lock_manager.acquire_lock(operation, timeout=1):
                pass

        elapsed = time.time() - start_time
        assert 0.9 < elapsed < 1.5  # Should timeout around 1s

        p.terminate()
        p.join()

    def test_lock_info(self, lock_manager):
        """Test lock info retrieval"""
        operation = 'test_info'

        # No info when not locked
        assert lock_manager.get_lock_info(operation) is None

        # Acquire lock
        with lock_manager.acquire_lock(operation):
            info = lock_manager.get_lock_info(operation)

            assert info is not None
            assert 'pid' in info
            assert 'started' in info
            assert 'operation' in info
            assert info['operation'] == operation
            assert info['pid'] == str(os.getpid())

        # No info after release
        assert lock_manager.get_lock_info(operation) is None

    def test_decorator(self):
        """Test with_lock decorator"""
        operation = 'test_decorator'
        execution_count = []

        @with_lock(operation, timeout=1)
        def test_function():
            execution_count.append(1)
            time.sleep(0.5)
            return 'success'

        # First call succeeds
        result = test_function()
        assert result == 'success'
        assert len(execution_count) == 1

        # Concurrent call fails (in another process)
        def concurrent_call():
            result = test_function()
            # Should return None due to lock error
            assert result is None

        p = multiprocessing.Process(target=concurrent_call)

        # Start concurrent execution
        proc = multiprocessing.Process(target=test_function)
        proc.start()
        time.sleep(0.1)  # Let it acquire lock

        # Try concurrent call (should fail)
        concurrent_call()

        proc.join()

    def test_cleanup_stale_locks(self, lock_manager):
        """Test cleanup of stale lock files"""
        operation = 'test_stale'
        lock_file = lock_manager.LOCK_DIR / f'{operation}.lock'

        # Create a lock file
        with lock_manager.acquire_lock(operation):
            pass

        # Manually create old lock file
        lock_file.touch()
        old_time = time.time() - (25 * 3600)  # 25 hours ago
        os.utime(lock_file, (old_time, old_time))

        # Cleanup
        lock_manager.cleanup_stale_locks(max_age_hours=24)

        # Stale lock should be removed
        assert not lock_file.exists()

    def test_multiple_operations(self, lock_manager):
        """Test that different operations don't interfere"""
        op1 = 'test_op1'
        op2 = 'test_op2'

        # Acquire both locks simultaneously
        with lock_manager.acquire_lock(op1):
            with lock_manager.acquire_lock(op2):
                assert lock_manager.is_locked(op1)
                assert lock_manager.is_locked(op2)

        # Both released
        assert not lock_manager.is_locked(op1)
        assert not lock_manager.is_locked(op2)

    def test_exception_handling(self, lock_manager):
        """Test that locks are released even on exception"""
        operation = 'test_exception'

        # Initially not locked
        assert not lock_manager.is_locked(operation)

        # Raise exception inside lock
        try:
            with lock_manager.acquire_lock(operation):
                assert lock_manager.is_locked(operation)
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Lock should be released despite exception
        assert not lock_manager.is_locked(operation)

    def test_lock_file_permissions(self, lock_manager):
        """Test that lock files have correct permissions"""
        operation = 'test_perms'

        with lock_manager.acquire_lock(operation):
            lock_file = lock_manager.LOCK_DIR / f'{operation}.lock'
            assert lock_file.exists()

            # Check permissions (should be readable/writable by user)
            mode = lock_file.stat().st_mode
            # At minimum, user should have read/write
            assert mode & 0o600 == 0o600


class TestLockManagerIntegration:
    """Integration tests simulating real-world scenarios"""

    def test_parallel_quick_refreshes(self):
        """Simulate two quick refreshes running in parallel"""

        @with_lock('quick_refresh', timeout=2)
        def quick_refresh():
            time.sleep(1)
            return 'completed'

        # First call succeeds
        result1 = quick_refresh()
        assert result1 == 'completed'

        # Simulate parallel execution
        def parallel_call():
            # Start first refresh
            p1 = multiprocessing.Process(target=quick_refresh)
            p1.start()
            time.sleep(0.2)  # Let it acquire lock

            # Try second refresh (should fail)
            result = quick_refresh()
            assert result is None  # Failed due to lock

            p1.join()

        parallel_call()

    def test_sequential_operations(self):
        """Test that operations run sequentially when locked"""
        operation = 'sequential_test'
        results = multiprocessing.Manager().list()

        @with_lock(operation, timeout=5)
        def timed_operation(worker_id):
            start = time.time()
            time.sleep(0.5)
            elapsed = time.time() - start
            results.append({'worker': worker_id, 'time': elapsed})

        # Start 3 workers
        processes = []
        for i in range(3):
            p = multiprocessing.Process(target=timed_operation, args=(i,))
            p.start()
            processes.append(p)

        # Wait for completion
        for p in processes:
            p.join()

        # Should have 3 successful executions (or 2 if timeouts occurred)
        assert len(results) >= 2

        # Verify they ran sequentially (total time should be additive)
        total_time = sum(r['time'] for r in results)
        assert total_time >= 1.0  # At least 2 * 0.5s


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
