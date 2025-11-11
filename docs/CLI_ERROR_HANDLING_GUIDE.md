# CLI Error Handling Guide

Comprehensive error handling strategies for Quant Platform CLI.

## Error Handling Philosophy

**Core Principles**:
1. **Fail Fast**: Detect errors early and provide clear feedback
2. **User-Friendly**: Error messages in plain language, not technical jargon
3. **Actionable**: Include specific steps to resolve issues
4. **Recoverable**: Allow graceful degradation when possible
5. **Traceable**: Log errors for debugging without exposing to users

## Error Categories

### 1. User Input Errors

**Example**: Invalid ticker, date format, filter syntax

**Handling Strategy**:
```python
# cli/commands/query.py
try:
    parts = filter_expr.split()
    if len(parts) != 3:
        formatter.print_warning(
            f"Invalid filter format: {filter_expr}\n"
            f"Expected format: 'column operator value' (e.g., 'f.per < 15')"
        )
        return 1
except ValueError as e:
    formatter.print_error(f"Failed to parse filter: {e}")
    return 1
```

**Best Practices**:
- Validate inputs before processing
- Provide example of correct format
- Suggest similar valid inputs when possible

### 2. Database Errors

**Example**: Connection timeout, query failure, constraint violation

**Handling Strategy**:
```python
# cli/utils/database.py
try:
    rows = await self._pool.fetch(query, *params, timeout=timeout)
except asyncio.TimeoutError:
    raise ConnectionError(
        f"Database query timeout ({timeout}s). "
        f"Try reducing --top or simplifying filters."
    )
except asyncpg.PostgresError as e:
    if 'connection' in str(e).lower():
        raise ConnectionError(
            "Database connection failed. "
            "Check that PostgreSQL is running: "
            "brew services list"
        )
    else:
        raise
```

**Best Practices**:
- Distinguish connection vs query errors
- Provide recovery steps (restart service, check credentials)
- Include relevant diagnostic info (error code, query)

### 3. Data Validation Errors

**Example**: Missing required data, invalid date range, empty results

**Handling Strategy**:
```python
# cli/utils/ohlcv_loader.py
async def load_data(self, tickers, start_date, end_date):
    rows = await self.db.fetch(query, *params)

    if not rows:
        raise ValueError(
            f"No data found for tickers: {tickers}\n"
            f"  Region: {region}\n"
            f"  Timeframe: {timeframe}\n"
            f"  Date range: {start_date} to {end_date}\n"
            f"\nPossible causes:\n"
            f"  1. Tickers not in database (run data collection)\n"
            f"  2. Date range too narrow or in future\n"
            f"  3. Wrong region (try --region US for US stocks)"
        )
```

**Best Practices**:
- List specific validation failures
- Suggest likely causes
- Provide fix commands/steps

### 4. External Dependency Errors

**Example**: vectorbt not installed, missing Plotly, Jinja2 template missing

**Handling Strategy**:
```python
# cli/commands/backtest.py
try:
    from cli.utils.vectorbt_adapter import VectorbtAdapter
except ImportError:
    formatter.print_error(
        "vectorbt is required for backtesting.\n"
        "Install with: pip install vectorbt\n"
        "Or install all dependencies: pip install -r requirements_quant.txt"
    )
    return 1
```

**Best Practices**:
- Check dependencies at command start
- Provide exact install command
- Suggest alternative approaches if available

### 5. System Resource Errors

**Example**: Out of memory, disk full, too many connections

**Handling Strategy**:
```python
# cli/utils/database.py
try:
    self._pool = await asyncpg.create_pool(
        dsn=self.dsn,
        min_size=self.min_size,
        max_size=self.max_size
    )
except Exception as e:
    if 'too many connections' in str(e).lower():
        raise ConnectionError(
            "Database connection pool exhausted.\n"
            "Current max_size: {self.max_size}\n"
            "Active queries: {self._active_queries}\n"
            "\nSolutions:\n"
            "  1. Wait for running queries to complete\n"
            "  2. Increase pool size in .env: DATABASE_MAX_POOL_SIZE=20\n"
            "  3. Close unused connections"
        )
    raise
```

**Best Practices**:
- Monitor resource usage proactively
- Provide current state (pool size, active connections)
- Suggest immediate and long-term fixes

## Error Messages Format

### Template Structure

```python
"""
{ERROR_TYPE}: {BRIEF_DESCRIPTION}

Context:
  {KEY1}: {VALUE1}
  {KEY2}: {VALUE2}

Possible causes:
  1. {CAUSE_1}
  2. {CAUSE_2}

Solutions:
  1. {SOLUTION_1} (command: {COMMAND_1})
  2. {SOLUTION_2}

For more help: {DOCUMENTATION_LINK}
"""
```

### Examples

#### Good Error Message
```
Database Connection Failed

Context:
  Database: quant_platform
  Host: localhost:5432
  Timeout: 30s

Possible causes:
  1. PostgreSQL service not running
  2. Incorrect credentials in .env
  3. Database does not exist

Solutions:
  1. Start PostgreSQL: brew services start postgresql@17
  2. Check credentials: cat .env | grep DATABASE
  3. Create database: createdb quant_platform

For more help: docs/QUANT_DATABASE_SCHEMA.md
```

#### Bad Error Message
```
Error: psycopg2.OperationalError: FATAL: database "quant_platform" does not exist
```

## Error Handling Patterns

### 1. Try-Except-Finally Pattern

```python
async def query_command(args):
    db = DatabaseManager()

    try:
        # Connect
        await db.connect()

        # Execute query
        rows = await db.fetch(query, *params)

        # Process results
        formatter.print_table(rows)

        return 0

    except ConnectionError as e:
        formatter.print_error(f"Database connection failed: {e}")
        return 1

    except ValueError as e:
        formatter.print_error(f"Invalid input: {e}")
        return 1

    except Exception as e:
        formatter.print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Always disconnect
        await db.disconnect()
```

### 2. Context Manager Pattern

```python
class DatabaseManager:
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

# Usage
async def query_with_context():
    async with DatabaseManager() as db:
        rows = await db.fetch(query)
        # Automatic disconnect on exit or error
```

### 3. Retry Pattern

```python
async def fetch_with_retry(self, query, *params, max_retries=3):
    """Execute query with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            return await self._pool.fetch(query, *params, timeout=30.0)

        except asyncio.TimeoutError:
            if attempt == max_retries - 1:
                raise
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            await asyncio.sleep(wait_time)

        except asyncpg.PostgresConnectionError:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(1)
            await self.connect()  # Reconnect
```

### 4. Validation Pattern

```python
def validate_arguments(args):
    """Validate command arguments before execution"""
    errors = []

    # Date validation
    try:
        start = datetime.strptime(args.start_date, '%Y-%m-%d')
        end = datetime.strptime(args.end_date, '%Y-%m-%d')

        if start >= end:
            errors.append("start_date must be before end_date")

        if end > datetime.now():
            errors.append("end_date cannot be in the future")

    except ValueError:
        errors.append("Dates must be in YYYY-MM-DD format")

    # Ticker validation
    if not args.tickers:
        errors.append("At least one ticker is required")

    # Commission validation
    if args.commission < 0 or args.commission > 0.1:
        errors.append("commission must be between 0 and 0.1 (10%)")

    if errors:
        raise ValueError(
            "Validation failed:\n" +
            "\n".join(f"  - {e}" for e in errors)
        )
```

## Logging Strategy

### Log Levels

```python
# cli/utils/logger.py
import logging

logger = logging.getLogger('quant_platform')

# DEBUG: Detailed diagnostic info
logger.debug(f"Query built: {query}")

# INFO: General informational messages
logger.info(f"Query executed successfully ({len(rows)} rows)")

# WARNING: Unexpected but recoverable issues
logger.warning(f"Slow query detected ({elapsed:.1f}ms)")

# ERROR: Errors that prevent operation
logger.error(f"Query failed: {e}")

# CRITICAL: System failures requiring immediate attention
logger.critical(f"Database connection pool exhausted")
```

### Log Configuration

```python
# cli/utils/logger.py
def setup_logging(level=logging.INFO):
    """Configure logging with file and console handlers"""

    # Create logs directory
    log_dir = Path.home() / '.quant_platform' / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)

    # File handler (all logs)
    fh = logging.FileHandler(
        log_dir / f'cli_{datetime.now():%Y%m%d}.log'
    )
    fh.setLevel(logging.DEBUG)

    # Console handler (warnings and errors only)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)

    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # Configure root logger
    logger = logging.getLogger('quant_platform')
    logger.setLevel(level)
    logger.addHandler(fh)
    logger.addHandler(ch)
```

## Error Recovery Strategies

### 1. Graceful Degradation

```python
async def load_data_with_fallback(self, tickers, start_date, end_date):
    """Load data with fallback to cached data"""
    try:
        # Try database
        return await self._load_from_database(tickers, start_date, end_date)

    except ConnectionError:
        # Fall back to cache
        logger.warning("Database unavailable, using cached data")
        return self._load_from_cache(tickers, start_date, end_date)

    except Exception as e:
        # Last resort: empty DataFrame with warning
        logger.error(f"Data loading failed: {e}")
        formatter.print_warning(
            "Data loading failed. Returning empty dataset.\n"
            "Check logs for details: ~/.quant_platform/logs/"
        )
        return pd.DataFrame()
```

### 2. Automatic Retry

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True
)
async def fetch_with_auto_retry(self, query, *params):
    """Automatically retry failed queries"""
    return await self._pool.fetch(query, *params, timeout=30.0)
```

### 3. Circuit Breaker

```python
class CircuitBreaker:
    """Prevent cascading failures"""

    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.last_failure_time = None
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN

    async def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result

        except Exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'

    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
```

## Testing Error Handling

### Unit Tests

```python
# tests/test_error_handling.py
import pytest

@pytest.mark.asyncio
async def test_connection_error_handling():
    """Test graceful handling of database connection errors"""

    db = DatabaseManager(host='invalid_host')

    with pytest.raises(ConnectionError) as exc_info:
        await db.connect()

    assert 'Database connection failed' in str(exc_info.value)
    assert 'PostgreSQL' in str(exc_info.value)

@pytest.mark.asyncio
async def test_invalid_ticker_error():
    """Test validation error for invalid tickers"""

    loader = OHLCVLoader()
    await loader.connect()

    with pytest.raises(ValueError) as exc_info:
        await loader.load_data(
            tickers=['INVALID'],
            start_date='2023-01-01',
            end_date='2023-12-31'
        )

    assert 'No data found' in str(exc_info.value)
    await loader.disconnect()
```

## Monitoring and Alerts

### Error Rate Tracking

```python
# cli/utils/metrics.py
from collections import defaultdict

class ErrorMetrics:
    """Track error rates and types"""

    def __init__(self):
        self.error_counts = defaultdict(int)
        self.total_operations = 0

    def record_error(self, error_type: str):
        self.error_counts[error_type] += 1

    def record_success(self):
        self.total_operations += 1

    def get_error_rate(self) -> float:
        total = self.total_operations + sum(self.error_counts.values())
        return sum(self.error_counts.values()) / total if total > 0 else 0

    def get_report(self) -> str:
        report = ["\n=== Error Summary ==="]
        report.append(f"Total operations: {self.total_operations}")
        report.append(f"Error rate: {self.get_error_rate():.1%}")
        report.append("\nError breakdown:")

        for error_type, count in self.error_counts.items():
            report.append(f"  {error_type}: {count}")

        return "\n".join(report)
```

---

**Last Updated**: 2025-01-02
**Version**: 1.0.0
**Status**: Sprint 6.2 Complete
