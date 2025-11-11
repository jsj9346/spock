# Auto-Backfill Extensions - Implementation Guide

**Status**: Skeleton Only (Phase 2-3 features not yet implemented)

## Overview

This directory contains skeleton implementations for optional Phase 2-3 extensions to the auto-backfill system. All extensions are **disabled by default** and have **zero performance impact** when inactive.

## Directory Structure

```
extensions/
├── __init__.py           # Extension registry and availability checks
├── streaming.py          # Phase 2.1: Real-time data streaming
├── fundamentals.py       # Phase 2.2: Fundamental data backfill (DART/KIS)
├── batch.py              # Phase 2.3: Multi-threaded batch optimization
├── monitoring.py         # Phase 2.4: Grafana monitoring adapter
├── quality.py            # Phase 3.1: ML-based quality scoring
├── cache.py              # Phase 3.2-3.3: Predictive & distributed cache
└── README.md            # This file
```

## Extension Status

| Extension | Phase | Status | Complexity |
|-----------|-------|--------|------------|
| streaming | 2.1 | Skeleton | Medium |
| fundamentals | 2.2 | Skeleton | High |
| batch | 2.3 | Skeleton | Low |
| monitoring | 2.4 | Skeleton | Medium |
| quality | 3.1 | Skeleton | High |
| predictive_cache | 3.2 | Skeleton | High |
| distributed_cache | 3.3 | Skeleton | Medium |

## Quick Start

### Check Extension Availability

```python
from modules.backtesting.data_providers.extensions import (
    get_available_extensions,
    is_extension_available
)

# List all available extensions
available = get_available_extensions()
print(f"Available: {available}")  # []

# Check specific extension
if is_extension_available('streaming'):
    from .extensions.streaming import DataStreamManager
    stream = DataStreamManager({'enabled': True})
```

### Enable Extension

1. **Implement skeleton methods** in the extension file
2. **Update availability flag** in `extensions/__init__.py`:
   ```python
   EXTENSIONS_AVAILABLE = {
       'streaming': True,  # Change from False to True
       # ...
   }
   ```
3. **Configure** in `config/backfill_extensions.yaml`:
   ```yaml
   extensions:
     phase2:
       streaming:
         enabled: true
   ```
4. **Test** your implementation

## Implementation Guidelines

### For Each Extension

1. **Read Design Document**: `docs/AUTO_BACKFILL_SKELETON_DESIGN.md`
2. **Override ABC Methods**: Replace `raise NotImplementedError`
3. **Add Tests**: `tests/test_backfill_extensions.py`
4. **Update Documentation**: This README and design doc
5. **Performance Benchmark**: Measure actual vs target metrics

### Example: Implementing Streaming

**Step 1**: Implement skeleton methods

```python
# extensions/streaming.py

class DataStreamManager(DataStreamManager):  # Inherit from skeleton

    def connect(self, ticker: str, region: str) -> bool:
        """Implement WebSocket connection."""
        import websocket

        self.ws = websocket.WebSocketApp(
            f"{self.websocket_url}/{ticker}",
            on_message=self._on_message,
            on_error=self._on_error
        )
        self.ws.run_forever()
        return True

    def _on_message(self, ws, message):
        """Handle incoming messages."""
        data = json.loads(message)
        for callback in self.callbacks:
            callback(data)
```

**Step 2**: Update availability

```python
# extensions/__init__.py

EXTENSIONS_AVAILABLE = {
    'streaming': True,  # Now implemented!
    # ...
}
```

**Step 3**: Configure and test

```yaml
# config/backfill_extensions.yaml
extensions:
  phase2:
    streaming:
      enabled: true
      config:
        websocket_url: "wss://kis-api.com/stream"
```

```python
# Test
stream = DataStreamManager({'enabled': True})
assert stream.connect('005930', 'KR')
assert stream.is_enabled()
```

## Extension-Specific Notes

### Streaming (Phase 2.1)
- **Dependencies**: `websocket-client`
- **Complexity**: Medium (WebSocket handling, reconnection logic)
- **Integration Point**: Real-time validation of backtest results

### Fundamentals (Phase 2.2)
- **Dependencies**: DART API client, KIS API client
- **Complexity**: High (multiple APIs, data normalization)
- **Integration Point**: `BackfillOrchestrator.backfill_fundamentals()`

### Batch Optimization (Phase 2.3)
- **Dependencies**: None (uses stdlib `concurrent.futures`)
- **Complexity**: Low (straightforward ThreadPoolExecutor usage)
- **Expected Speedup**: 4x with 4 workers

### Monitoring (Phase 2.4)
- **Dependencies**: `prometheus-client`
- **Complexity**: Medium (Prometheus metrics, Grafana dashboard)
- **Integration Point**: All backfill operations emit metrics

### Quality Scoring (Phase 3.1)
- **Dependencies**: `scikit-learn`, `joblib`
- **Complexity**: High (ML model training, feature engineering)
- **Integration Point**: Post-backfill validation

### Predictive Cache (Phase 3.2)
- **Dependencies**: ML model for pattern prediction
- **Complexity**: High (query pattern analysis, ML prediction)
- **Expected Hit Rate**: >60%

### Distributed Cache (Phase 3.3)
- **Dependencies**: `redis`, `lz4`
- **Complexity**: Medium (Redis integration, serialization)
- **Expected Hit Rate**: >80% cluster-wide

## Testing Strategy

### Skeleton Tests (Already Passing)

```python
# tests/test_backfill_extensions.py

def test_all_extensions_disabled_by_default():
    """Verify zero performance impact when disabled."""
    orchestrator = BackfillOrchestrator(db_manager)
    assert len(orchestrator.extensions) == 0

def test_skeleton_raises_not_implemented():
    """Verify skeleton methods raise NotImplementedError."""
    stream = DataStreamManager({'enabled': True})
    with pytest.raises(NotImplementedError):
        stream.connect('005930', 'KR')
```

### Implementation Tests (Add When Implementing)

```python
def test_streaming_connection():
    """Test real WebSocket connection."""
    stream = DataStreamManager({'enabled': True, 'websocket_url': 'ws://test'})
    assert stream.connect('005930', 'KR')
    
def test_streaming_subscription():
    """Test subscription and callback."""
    messages = []
    stream.subscribe('005930', lambda msg: messages.append(msg))
    # ... trigger message ...
    assert len(messages) > 0
```

## Performance Targets

| Extension | Metric | Target | Skeleton |
|-----------|--------|--------|----------|
| Streaming | Latency | <50ms | N/A |
| Fundamentals | Coverage | >90% KR stocks | 0% |
| Batch | Speedup | 4x (4 workers) | 1x |
| Monitoring | Overhead | <5ms/call | 0ms |
| Quality Scorer | Accuracy | >95% anomaly detection | N/A |
| Predictive Cache | Hit Rate | >60% | 0% |
| Distributed Cache | Hit Rate | >80% | 0% |

## Common Issues

### "Extension not available"
**Solution**: Check `EXTENSIONS_AVAILABLE` in `__init__.py`

### "NotImplementedError"
**Solution**: This is expected for skeleton methods. Implement the method.

### "Import Error"
**Solution**: Install required dependencies (see Extension-Specific Notes)

### "Configuration not loaded"
**Solution**: Ensure `config/backfill_extensions.yaml` exists and is valid

## Contributing

1. Choose an extension to implement
2. Read design document thoroughly
3. Implement skeleton methods with tests
4. Benchmark performance vs targets
5. Update documentation
6. Submit for review

## References

- **Design Document**: `docs/AUTO_BACKFILL_SKELETON_DESIGN.md`
- **Core Implementation**: `modules/backtesting/data_providers/backfill_orchestrator.py`
- **Configuration**: `config/backfill_extensions.yaml`
- **Tests**: `tests/test_backfill_extensions.py`

---

**Last Updated**: 2025-10-29
**Status**: All extensions are skeletons - none implemented yet
**Next Steps**: Choose Phase 2.1 (Streaming) or Phase 2.3 (Batch) as first implementation
