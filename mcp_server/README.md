# Spock MCP Server

AI-powered quant analysis interface for the Spock quantitative investment platform.

## Overview

The Spock MCP (Model Context Protocol) server provides a secure, high-performance interface for AI assistants to access quantitative investment data and backtesting capabilities.

**Version**: 0.1.0
**Protocol**: MCP (Model Context Protocol)
**Language**: Python 3.11+

## Features

### Core Capabilities
- **OHLCV Data Queries**: Historical price and volume data for KR/US markets
- **Backtesting**: Run strategy simulations with vectorbt or custom engines
- **Portfolio Optimization**: Parameter optimization and walk-forward analysis
- **System Health**: Database statistics and data freshness monitoring

### Security Features
- **Project Path Restriction**: Server operates only within designated project directory
- **Path Traversal Prevention**: Blocks `../` and absolute path attacks
- **Symlink Protection**: Resolves symlinks to prevent directory escape
- **Input Validation**: Comprehensive validation for all inputs

### Performance
- **OHLCV Queries**: <100ms cache hit, <500ms cache miss
- **Backtesting**: <1s for 5-year vectorbt backtest
- **Path Validation**: <1ms overhead per operation
- **Cache Hit Rate**: >80% for typical workloads

## Installation

### Prerequisites
- Python 3.11+
- PostgreSQL 15+ with TimescaleDB extension
- Spock quantitative platform installed

### Setup
```bash
# Install dependencies
cd /Users/13ruce/spock
pip install -r requirements_quant.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Test MCP server
python -m mcp_server.server
```

## Configuration

### Environment Variables

The MCP server is configured via environment variables:

```bash
# Database Configuration
POSTGRES_HOST=localhost          # PostgreSQL host (default: localhost)
POSTGRES_PORT=5432              # PostgreSQL port (default: 5432)
POSTGRES_DB=quant_platform      # Database name (default: quant_platform)
POSTGRES_USER=bruce             # Database user (default: bruce)
POSTGRES_PASSWORD=              # Database password (default: empty)

# Performance Configuration
CACHE_MAX_SIZE_MB=500           # Cache size in MB (default: 500)
CACHE_TTL_SECONDS=3600          # Cache TTL in seconds (default: 3600)
BATCH_SIZE=100                  # Batch query size (default: 100)

# Logging Configuration
LOG_LEVEL=INFO                  # Logging level (default: INFO)
LOG_DIR=logs                    # Log directory (default: logs)

# Security Configuration
SPOCK_PROJECT_PATH=/Users/13ruce/spock  # Allowed project path (default)
SPOCK_MCP_API_KEY=              # API key for authentication (optional, Phase 2)
RATE_LIMIT_PER_MINUTE=60        # Rate limit (default: 60)
```

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "spock": {
      "command": "/Users/13ruce/anaconda3/bin/python3",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/Users/13ruce/spock",
      "env": {
        "PYTHONPATH": "/Users/13ruce/spock",
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "quant_platform",
        "POSTGRES_USER": "13ruce",
        "SPOCK_PROJECT_PATH": "/Users/13ruce/spock"
      }
    }
  }
}
```

### Claude Code Configuration (VSCode Extension)

**IMPORTANT**: Claude Code uses a different configuration file than Claude Desktop.

Add to `~/.claude.json` under the project path:

```json
{
  "projects": {
    "/Users/13ruce/spock": {
      "mcpServers": {
        "spock": {
          "type": "stdio",
          "command": "/Users/13ruce/anaconda3/bin/python3",
          "args": ["-m", "mcp_server.server"],
          "cwd": "/Users/13ruce/spock",
          "env": {
            "PYTHONPATH": "/Users/13ruce/spock",
            "POSTGRES_HOST": "localhost",
            "POSTGRES_PORT": "5432",
            "POSTGRES_DB": "quant_platform",
            "POSTGRES_USER": "13ruce",
            "SPOCK_PROJECT_PATH": "/Users/13ruce/spock"
          }
        }
      }
    }
  }
}
```

**Key Differences from Claude Desktop Configuration**:
1. Configuration is nested under `projects` → `[project-path]` → `mcpServers`
2. Must include `"type": "stdio"` field
3. Project-specific configuration (different MCP servers per project)

**Note**: After adding or modifying MCP server configuration:
- **Claude Desktop**: Restart the application
- **Claude Code**: Restart VSCode or use Command Palette (Cmd+Shift+P → "Developer: Reload Window")
- **Verification**: Run `/mcp` command in Claude Code to see available MCP servers

## Security: Project Path Restriction

### Overview

The Spock MCP server enforces **project path restriction** to ensure it operates only within the designated Spock project directory. This prevents unauthorized access to files and data outside the project.

### How It Works

1. **Server Initialization Validation**
   - Server validates current working directory on startup
   - Fails immediately if started outside allowed project path
   - Logs validation success/failure with paths

2. **Path Resolution**
   - All paths are resolved to canonical form using `os.path.realpath()`
   - Symlinks are followed to their targets
   - Relative paths are converted to absolute paths

3. **Validation Logic**
   ```python
   resolved_current = os.path.realpath(os.getcwd())
   resolved_allowed = os.path.realpath(allowed_path)

   if not resolved_current.startswith(resolved_allowed):
       raise PathValidationError(...)
   ```

### Attack Vectors Mitigated

✅ **Path Traversal**: `../../../etc/passwd` blocked by path resolution
✅ **Symlink Attacks**: Symlinks resolved to real paths before validation
✅ **Absolute Paths**: Absolute paths outside project rejected
✅ **Directory Escape**: Cannot escape project directory through any means

### Configuration

**Default Allowed Path**: `/Users/13ruce/spock`

**Override with Environment Variable**:
```bash
export SPOCK_PROJECT_PATH=/path/to/your/project
python -m mcp_server.server
```

**Note**: Server must be started from within the allowed path.

### Error Handling

When path validation fails, the server raises `PathValidationError`:

```json
{
  "success": false,
  "error": {
    "code": "PATH_VALIDATION_ERROR",
    "message": "MCP server must operate within allowed project path",
    "details": {
      "current_path": "/tmp",
      "allowed_path": "/Users/13ruce/spock",
      "reason": "Current working directory is outside allowed project"
    }
  }
}
```

## Available Tools

### 1. query_ohlcv_data

Get OHLCV (Open, High, Low, Close, Volume) historical data.

**Input Schema**:
```json
{
  "tickers": ["005930"],           // Required: 1-1000 tickers
  "start_date": "2024-01-01",      // Required: YYYY-MM-DD format
  "end_date": "2024-12-31",        // Required: YYYY-MM-DD format
  "region": "KR",                  // Optional: KR or US (default: KR)
  "timeframe": "1d"                // Optional: 1d (default: 1d)
}
```

**Example Response**:
```json
{
  "success": true,
  "data": {
    "005930": [
      {
        "date": "2024-01-02",
        "open": 75000,
        "high": 76000,
        "low": 74500,
        "close": 75500,
        "volume": 12500000
      }
    ]
  },
  "ticker_count": 1,
  "record_count": 245
}
```

### 2. run_backtest

Run backtesting simulation for a strategy.

**Input Schema**:
```json
{
  "strategy_type": "momentum",         // Required: momentum, value, momentum_value
  "tickers": ["005930"],              // Required: ticker list
  "start_date": "2023-01-01",         // Required: YYYY-MM-DD
  "end_date": "2023-12-31",           // Required: YYYY-MM-DD
  "region": "KR",                     // Optional (default: KR)
  "engine": "vectorbt",               // Optional: vectorbt or custom (default: vectorbt)
  "initial_capital": 100000000,       // Optional (default: 100M KRW)
  "risk_profile": "moderate",         // Optional: conservative, moderate, aggressive
  "parameters": {}                    // Optional: strategy parameters
}
```

**Example Response**:
```json
{
  "success": true,
  "engine": "vectorbt",
  "performance": {
    "total_return": 0.245,
    "annual_return": 0.245,
    "sharpe_ratio": 1.82,
    "max_drawdown": -0.087
  },
  "trades": {
    "total_trades": 45,
    "win_rate": 0.622,
    "profit_factor": 2.14
  },
  "execution": {
    "execution_time": 0.456,
    "start_date": "2023-01-01",
    "end_date": "2023-12-31"
  }
}
```

### 3. optimize_strategy

Optimize strategy parameters using walk-forward analysis.

**Input Schema**:
```json
{
  "strategy_type": "momentum",
  "tickers": ["005930"],
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "optimization_method": "walk_forward",
  "parameter_space": {
    "rsi_period": [10, 14, 20],
    "ma_period": [20, 50, 100]
  }
}
```

### 4. list_available_tickers

List tickers in database with optional filtering.

**Input Schema**:
```json
{
  "region": "KR",              // Optional: KR, US
  "ticker_type": "stock",      // Optional: stock, etf
  "limit": 100                 // Optional: max results (default: all)
}
```

### 5. get_system_status

Get system health status and database statistics.

**Input**: None

**Example Response**:
```json
{
  "success": true,
  "status": "healthy",
  "database": {
    "version": "PostgreSQL 15.4",
    "size": "2.5 GB",
    "connected": true
  },
  "data": {
    "ticker_counts": {"KR": 2850, "US": 450},
    "total_tickers": 3300,
    "ohlcv_records": 1369467,
    "latest_date": "2024-10-30",
    "days_since_update": 1,
    "data_fresh": true
  }
}
```

## Error Handling

### Error Response Format

All errors follow MCP standard format:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "key": "Additional context"
    }
  }
}
```

### Error Codes

| Code | Description | Common Causes |
|------|-------------|---------------|
| `VALIDATION_ERROR` | Input validation failed | Invalid tickers, dates, or parameters |
| `DATA_NOT_FOUND` | Requested data unavailable | Missing OHLCV data for ticker/date range |
| `DATABASE_ERROR` | Database operation failed | Connection timeout, query error |
| `BACKTEST_ERROR` | Backtest execution failed | Insufficient data, strategy error |
| `PATH_VALIDATION_ERROR` | Path validation failed | Operation outside allowed project |
| `INTERNAL_ERROR` | Unexpected server error | Bug or system issue |

## Development

### Running Tests

```bash
# Run all MCP server tests
pytest tests/mcp_server/ -v

# Run specific test suite
pytest tests/mcp_server/test_path_validation.py -v

# Run with coverage
pytest tests/mcp_server/ --cov=mcp_server --cov-report=html
```

### Project Structure

```
mcp_server/
├── __init__.py              # Package initialization with logging setup
├── server.py                # Main MCP server (153 lines)
├── config.py                # Configuration management (108 lines)
├── logging_config.py        # Logging configuration (66 lines)
│
├── adapters/                # Business logic adapters
│   ├── data_adapter.py      # OHLCV queries (211 lines)
│   ├── backtest_adapter.py  # Backtesting (328 lines)
│   ├── system_adapter.py    # System info (277 lines)
│   └── optimization_adapter.py  # Parameter optimization
│
├── tools/                   # MCP tool definitions
│   ├── data_query.py        # OHLCV data tools (302 lines)
│   └── _tool_helpers.py     # Tool helper functions
│
├── utils/                   # Shared utilities
│   ├── errors.py            # Error hierarchy (183 lines)
│   ├── validators.py        # Input validation (307 lines)
│   └── formatters.py        # Response formatting (135 lines)
│
└── resources/               # MCP resources (future)
```

### Adding New Tools

1. **Define Tool Schema** in `tools/your_tool.py`:
```python
def get_your_tool_def() -> Tool:
    return Tool(
        name="your_tool",
        description="Tool description",
        inputSchema={...}
    )
```

2. **Implement Handler**:
```python
async def handle_your_tool(adapter, arguments):
    # Validate inputs
    # Execute logic
    # Format response
    return [TextContent(type="text", text=response)]
```

3. **Register in Server** (`server.py`):
```python
@self.server.list_tools()
async def list_tools_handler():
    tools.append(get_your_tool_def())
    return tools

@self.server.call_tool()
async def call_tool_handler(name, arguments):
    if name == "your_tool":
        return await handle_your_tool(...)
```

## Performance Tuning

### Cache Configuration

```bash
# Increase cache size for heavy workloads
export CACHE_MAX_SIZE_MB=1000

# Decrease TTL for real-time data
export CACHE_TTL_SECONDS=300
```

### Database Optimization

- Use connection pooling (handled by `PostgresDatabaseManager`)
- Enable TimescaleDB continuous aggregates for large date ranges
- Monitor query performance with `EXPLAIN ANALYZE`

### Batch Operations

```bash
# Adjust batch size for bulk operations
export BATCH_SIZE=200  # Increase for better throughput
```

## Troubleshooting

### Common Issues

**Issue**: `PathValidationError: outside allowed project`
**Solution**: Ensure server is started from within allowed project directory

**Issue**: `DatabaseError: connection timeout`
**Solution**: Check PostgreSQL service is running and credentials are correct

**Issue**: `DataNotFoundError: No OHLCV data`
**Solution**: Verify tickers exist in database and date range has data

**Issue**: `ModuleNotFoundError: No module named 'vectorbt'`
**Solution**: Install vectorbt or use custom engine instead

### Logging

**Log Location**: `log/YYYYMMDD_mcp_server.log`
**Log Level**: Set via `LOG_LEVEL` environment variable (DEBUG, INFO, WARNING, ERROR)

**Enable Debug Logging**:
```bash
export LOG_LEVEL=DEBUG
python -m mcp_server.server
```

## Roadmap

### Phase 1 (Current - v0.1.0)
- ✅ Core OHLCV data queries
- ✅ Basic backtesting interface
- ✅ System health monitoring
- ✅ Project path restriction
- ✅ Comprehensive error handling

### Phase 2 (v0.2.0)
- 🔄 API key authentication
- 🔄 Rate limiting enforcement
- 🔄 Advanced caching strategies
- 🔄 Multi-user support

### Phase 3 (v0.3.0)
- 📋 Real-time data streaming
- 📋 Advanced portfolio analytics
- 📋 Custom strategy DSL
- 📋 Performance monitoring dashboard

## License

MIT License - See LICENSE file for details

## Support

- **Issues**: https://github.com/your-org/spock/issues
- **Documentation**: See `docs/` directory
- **Email**: support@example.com

---

**Last Updated**: 2024-10-31
**Version**: 0.1.0
