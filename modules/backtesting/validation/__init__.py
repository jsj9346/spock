"""
Backtesting Validation Framework

Provides comprehensive validation infrastructure for ensuring backtesting
engine reliability, cross-engine consistency, and automated regression testing.

Key Components:
- EngineValidator: Cross-validation between vectorbt and custom engines
- RegressionTester: Automated regression testing against reference results
- PerformanceTracker: Performance benchmarking and profiling
- ConsistencyMonitor: Real-time consistency monitoring
- ValidationReportGenerator: Detailed validation reports

Usage:
    from modules.backtesting.validation import EngineValidator

    validator = EngineValidator(config, data_provider)
    report = validator.validate(signal_generator=rsi_signal_generator)
    print(report.validation_passed)  # True/False
"""

from .engine_validator import EngineValidator
from .regression_tester import RegressionTester
from .performance_tracker import PerformanceTracker
from .consistency_monitor import ConsistencyMonitor
from .validation_report_generator import ValidationReportGenerator

__all__ = [
    'EngineValidator',
    'RegressionTester',
    'PerformanceTracker',
    'ConsistencyMonitor',
    'ValidationReportGenerator',
]
