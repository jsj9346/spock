"""
Lock Manager for preventing duplicate operations in spock_refresh.py

Usage:
    from modules.concurrency import with_lock, LockError

    @with_lock('operation_name')
    def my_operation():
        # Your code here
        pass

    # Or use context manager:
    lock_manager = LockManager()
    try:
        with lock_manager.acquire_lock('operation_name'):
            # Your code here
            pass
    except LockError as e:
        print(f"Lock acquisition failed: {e}")
"""

import fcntl
import os
import time
import platform
from contextlib import contextmanager
from pathlib import Path
from typing import Optional
from datetime import datetime


class LockError(Exception):
    """Exception raised when lock acquisition fails"""
    pass


class LockManager:
    """
    File-based lock manager for operation synchronization.

    Features:
    - Per-operation lock files
    - Configurable timeouts
    - Automatic cleanup
    - Cross-platform support (Unix-based systems)
    - PID tracking for debugging

    Attributes:
        LOCK_DIR: Directory for lock files (~/.spock_locks)
        DEFAULT_TIMEOUT: Default lock acquisition timeout (300s)
    """

    # Lock directory in user home
    LOCK_DIR = Path.home() / '.spock_locks'
    DEFAULT_TIMEOUT = 300  # 5 minutes

    def __init__(self):
        """Initialize lock manager and create lock directory"""
        self.LOCK_DIR.mkdir(exist_ok=True, mode=0o755)
        self.active_locks = {}

        # Check platform compatibility
        if platform.system() == 'Windows':
            raise RuntimeError(
                "LockManager is not supported on Windows. "
                "Please use a Unix-based system (macOS, Linux)."
            )

    @contextmanager
    def acquire_lock(self, operation: str, timeout: Optional[int] = None):
        """
        Acquire exclusive lock for an operation.

        Args:
            operation: Operation name (e.g., 'quick_refresh', 'full_refresh')
            timeout: Lock acquisition timeout in seconds (default: DEFAULT_TIMEOUT)

        Yields:
            None when lock is successfully acquired

        Raises:
            LockError: If lock cannot be acquired within timeout

        Example:
            with lock_manager.acquire_lock('my_operation', timeout=60):
                # Your critical section here
                do_something()
        """
        timeout = timeout or self.DEFAULT_TIMEOUT
        lock_file = self.LOCK_DIR / f'{operation}.lock'
        fd = None

        try:
            # Open/create lock file
            fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR, 0o644)

            # Try to acquire non-blocking exclusive lock
            start_time = time.time()
            acquired = False
            last_update = 0

            while not acquired:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    # Lock is held by another process
                    elapsed = time.time() - start_time

                    # Show progress every 5 seconds
                    if int(elapsed) - last_update >= 5:
                        remaining = int(timeout - elapsed)
                        print(f"⏳ Waiting for lock '{operation}'... ({int(elapsed)}s elapsed, {remaining}s remaining)", end='\r', flush=True)
                        last_update = int(elapsed)

                    if elapsed > timeout:
                        # Clear progress line
                        print(" " * 100, end='\r')

                        # Read existing lock info
                        existing_info = self._read_lock_info(fd)
                        raise LockError(
                            f"Could not acquire lock for '{operation}' after {timeout}s.\n"
                            f"Another instance may be running:\n{existing_info}\n"
                            f"Wait for completion or manually remove: {lock_file}"
                        )

                    # Wait before retry
                    time.sleep(0.5)

            # Clear progress line when lock acquired
            if last_update > 0:
                print(" " * 100, end='\r')

            # Write lock metadata
            lock_info = (
                f"Operation: {operation}\n"
                f"PID: {os.getpid()}\n"
                f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Hostname: {platform.node()}\n"
            )

            # Truncate and write
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, lock_info.encode())
            os.fsync(fd)

            # Track active lock
            self.active_locks[operation] = fd

            # Yield control to caller
            yield

        finally:
            # Release lock
            if operation in self.active_locks:
                lock_fd = self.active_locks.pop(operation)

                try:
                    fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
                except OSError:
                    pass  # Already closed

                # Remove lock file
                try:
                    lock_file.unlink()
                except FileNotFoundError:
                    pass
            elif fd is not None:
                # Clean up if lock was never acquired
                try:
                    os.close(fd)
                except OSError:
                    pass

    def _read_lock_info(self, fd: int) -> str:
        """Read lock file metadata"""
        try:
            os.lseek(fd, 0, os.SEEK_SET)
            content = os.read(fd, 1024).decode('utf-8', errors='ignore')
            return content.strip() if content else "No lock info available"
        except Exception:
            return "Could not read lock info"

    def is_locked(self, operation: str) -> bool:
        """
        Check if operation is currently locked.

        Args:
            operation: Operation name

        Returns:
            True if locked, False otherwise
        """
        lock_file = self.LOCK_DIR / f'{operation}.lock'

        if not lock_file.exists():
            return False

        try:
            fd = os.open(str(lock_file), os.O_RDONLY)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fd, fcntl.LOCK_UN)
                return False
            except BlockingIOError:
                return True
            finally:
                os.close(fd)
        except OSError:
            return False

    def get_lock_info(self, operation: str) -> Optional[dict]:
        """
        Get information about a locked operation.

        Args:
            operation: Operation name

        Returns:
            Dictionary with lock info or None if not locked
        """
        lock_file = self.LOCK_DIR / f'{operation}.lock'

        if not lock_file.exists() or not self.is_locked(operation):
            return None

        try:
            with open(lock_file, 'r') as f:
                content = f.read()

            # Parse lock info
            info = {}
            for line in content.strip().split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip().lower()] = value.strip()

            return info
        except Exception:
            return None

    def cleanup_stale_locks(self, max_age_hours: int = 24):
        """
        Remove stale lock files (older than max_age_hours).

        Args:
            max_age_hours: Maximum age in hours before considering lock stale
        """
        if not self.LOCK_DIR.exists():
            return

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        for lock_file in self.LOCK_DIR.glob('*.lock'):
            try:
                # Check file age
                file_age = current_time - lock_file.stat().st_mtime

                if file_age > max_age_seconds:
                    # Try to acquire lock (will succeed if stale)
                    fd = os.open(str(lock_file), os.O_RDWR)
                    try:
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        fcntl.flock(fd, fcntl.LOCK_UN)
                        lock_file.unlink()
                        print(f"Removed stale lock: {lock_file.name}")
                    except BlockingIOError:
                        # Still in use, skip
                        pass
                    finally:
                        os.close(fd)
            except Exception:
                # Skip problematic files
                pass


# Global lock manager instance
_lock_manager = LockManager()


def with_lock(operation: str, timeout: Optional[int] = None):
    """
    Decorator for functions that require exclusive execution.

    Args:
        operation: Operation name for lock identification
        timeout: Lock acquisition timeout in seconds

    Returns:
        Decorated function

    Example:
        @with_lock('my_operation', timeout=60)
        def my_function():
            # This code will only run if lock is acquired
            do_something()
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                with _lock_manager.acquire_lock(operation, timeout):
                    return func(*args, **kwargs)
            except LockError as e:
                # Import here to avoid circular dependency
                try:
                    from colorama import Fore, Style
                    error_msg = f"{Fore.YELLOW}⚠️  Lock Error:{Style.RESET_ALL} {e}"
                    suggestion = f"{Fore.CYAN}💡 Suggestion:{Style.RESET_ALL} Wait for the other instance to complete or use a different operation."
                except ImportError:
                    error_msg = f"⚠️  Lock Error: {e}"
                    suggestion = "💡 Suggestion: Wait for the other instance to complete or use a different operation."

                print(f"\n{error_msg}")
                print(f"{suggestion}\n")

                # Pause in interactive mode
                import sys
                if sys.stdin.isatty():
                    try:
                        input("Press Enter to continue...")
                    except (KeyboardInterrupt, EOFError):
                        pass

                return None

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        return wrapper

    return decorator


# Convenience functions
def is_operation_locked(operation: str) -> bool:
    """Check if operation is locked"""
    return _lock_manager.is_locked(operation)


def get_operation_info(operation: str) -> Optional[dict]:
    """Get lock info for operation"""
    return _lock_manager.get_lock_info(operation)


def cleanup_stale_locks(max_age_hours: int = 24):
    """Cleanup stale lock files"""
    _lock_manager.cleanup_stale_locks(max_age_hours)
