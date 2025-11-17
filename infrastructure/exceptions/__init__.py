"""
Infrastructure Exceptions Module

Spock 플랫폼의 모든 커스텀 예외 클래스를 제공합니다.

주요 예외 카테고리:
- Base: 기본 예외 클래스
- Database: 데이터베이스 관련 예외
- API: 외부 API 호출 관련 예외
- Validation: 데이터 검증 관련 예외

사용법:
    from infrastructure.exceptions import (
        SpockBaseException,
        DatabaseException,
        APIException,
        ValidationException
    )

    try:
        # 작업 수행
        ...
    except SpockBaseException as e:
        # 모든 Spock 예외 처리
        print(e.to_dict())
"""

# ============================================================================
# Base Exceptions
# ============================================================================
from .base import (
    SpockBaseException,
    SpockWarning,
    SpockConfigurationError,
    SpockNotImplementedError,
    InfrastructureException,
)

# ============================================================================
# Database Exceptions
# ============================================================================
from .database import (
    # Base
    DatabaseException,

    # Connection
    ConnectionException,
    ConnectionPoolExhausted,
    ConnectionTimeout,
    ConnectionNotInitialized,
    ConnectionClosed,

    # Query
    QueryException,
    QueryTimeout,
    QuerySyntaxError,
    QueryExecutionError,
    RecordNotFoundError,
    MultipleRecordsFoundError,

    # Transaction
    TransactionException,
    TransactionRollbackError,
    TransactionCommitError,
    DeadlockException,

    # Integrity
    IntegrityException,
    UniqueViolationError,
    ForeignKeyViolationError,
    CheckConstraintViolationError,
    NotNullViolationError,

    # Migration
    MigrationException,
    MigrationAlreadyApplied,
    MigrationNotFound,
    MigrationRollbackError,

    # Schema
    SchemaException,
    TableNotFoundError,
    ColumnNotFoundError,
    InvalidSchemaError,
)

# ============================================================================
# API Exceptions
# ============================================================================
from .api import (
    # Base
    APIException,

    # Rate Limit
    RateLimitExceeded,
    QuotaExceeded,

    # Authentication
    AuthenticationFailed,
    TokenExpired,
    InvalidAPIKey,
    PermissionDenied,

    # Request
    APITimeout,
    ConnectionError,
    InvalidRequest,

    # Response
    InvalidAPIResponse,
    MissingRequiredField,
    UnexpectedDataFormat,

    # HTTP Status
    ResourceNotFound,
    ServerError,
    ServiceUnavailable,

    # API-Specific
    KISAPIException,
    KISTokenGenerationFailed,
    KISMarketClosed,
    DARTAPIException,
    DARTRateLimitExceeded,
    YFinanceException,
    YFinanceDataNotAvailable,

    # Market Data
    MarketDataException,
    NoDataAvailable,
    DataQualityIssue,
    StalDataError,
)

# ============================================================================
# Validation Exceptions
# ============================================================================
from .validation import (
    # Base
    ValidationException,

    # Input
    InvalidInputError,
    MissingRequiredParameter,
    InvalidParameterType,
    ValueOutOfRange,

    # Date
    InvalidDateError,
    InvalidDateRangeError,
    FutureDateNotAllowed,

    # Ticker
    InvalidTickerError,
    TickerNotFoundError,
    InactiveTickerError,

    # Region
    InvalidRegionError,

    # Configuration
    ConfigurationValidationError,
    InvalidConfigFormat,
    MissingConfigParameter,

    # Data
    DataValidationError,
    EmptyDataError,
    IncompleteDataError,
    DuplicateDataError,
    InvalidDataFormat,

    # Business Logic
    BusinessRuleViolation,
    InsufficientDataError,
    ConstraintViolation,
)


# ============================================================================
# Public API
# ============================================================================
__all__ = [
    # Base
    "SpockBaseException",
    "SpockWarning",
    "SpockConfigurationError",
    "SpockNotImplementedError",
    "InfrastructureException",

    # Database
    "DatabaseException",
    "ConnectionException",
    "ConnectionPoolExhausted",
    "ConnectionTimeout",
    "ConnectionNotInitialized",
    "ConnectionClosed",
    "QueryException",
    "QueryTimeout",
    "QuerySyntaxError",
    "QueryExecutionError",
    "RecordNotFoundError",
    "MultipleRecordsFoundError",
    "TransactionException",
    "TransactionRollbackError",
    "TransactionCommitError",
    "DeadlockException",
    "IntegrityException",
    "UniqueViolationError",
    "ForeignKeyViolationError",
    "CheckConstraintViolationError",
    "NotNullViolationError",
    "MigrationException",
    "MigrationAlreadyApplied",
    "MigrationNotFound",
    "MigrationRollbackError",
    "SchemaException",
    "TableNotFoundError",
    "ColumnNotFoundError",
    "InvalidSchemaError",

    # API
    "APIException",
    "RateLimitExceeded",
    "QuotaExceeded",
    "AuthenticationFailed",
    "TokenExpired",
    "InvalidAPIKey",
    "PermissionDenied",
    "APITimeout",
    "ConnectionError",
    "InvalidRequest",
    "InvalidAPIResponse",
    "MissingRequiredField",
    "UnexpectedDataFormat",
    "ResourceNotFound",
    "ServerError",
    "ServiceUnavailable",
    "KISAPIException",
    "KISTokenGenerationFailed",
    "KISMarketClosed",
    "DARTAPIException",
    "DARTRateLimitExceeded",
    "YFinanceException",
    "YFinanceDataNotAvailable",
    "MarketDataException",
    "NoDataAvailable",
    "DataQualityIssue",
    "StalDataError",

    # Validation
    "ValidationException",
    "InvalidInputError",
    "MissingRequiredParameter",
    "InvalidParameterType",
    "ValueOutOfRange",
    "InvalidDateError",
    "InvalidDateRangeError",
    "FutureDateNotAllowed",
    "InvalidTickerError",
    "TickerNotFoundError",
    "InactiveTickerError",
    "InvalidRegionError",
    "ConfigurationValidationError",
    "InvalidConfigFormat",
    "MissingConfigParameter",
    "DataValidationError",
    "EmptyDataError",
    "IncompleteDataError",
    "DuplicateDataError",
    "InvalidDataFormat",
    "BusinessRuleViolation",
    "InsufficientDataError",
    "ConstraintViolation",
]


# ============================================================================
# Exception Hierarchy Summary
# ============================================================================
"""
예외 계층 구조:

SpockBaseException
├── SpockWarning
├── SpockConfigurationError
├── SpockNotImplementedError
│
├── DatabaseException
│   ├── ConnectionException
│   │   ├── ConnectionPoolExhausted
│   │   ├── ConnectionTimeout
│   │   ├── ConnectionNotInitialized
│   │   └── ConnectionClosed
│   ├── QueryException
│   │   ├── QueryTimeout
│   │   ├── QuerySyntaxError
│   │   ├── QueryExecutionError
│   │   ├── RecordNotFoundError
│   │   └── MultipleRecordsFoundError
│   ├── TransactionException
│   │   ├── TransactionRollbackError
│   │   ├── TransactionCommitError
│   │   └── DeadlockException
│   ├── IntegrityException
│   │   ├── UniqueViolationError
│   │   ├── ForeignKeyViolationError
│   │   ├── CheckConstraintViolationError
│   │   └── NotNullViolationError
│   ├── MigrationException
│   │   ├── MigrationAlreadyApplied
│   │   ├── MigrationNotFound
│   │   └── MigrationRollbackError
│   └── SchemaException
│       ├── TableNotFoundError
│       ├── ColumnNotFoundError
│       └── InvalidSchemaError
│
├── APIException
│   ├── RateLimitExceeded
│   ├── QuotaExceeded
│   ├── AuthenticationFailed
│   │   ├── TokenExpired
│   │   ├── InvalidAPIKey
│   │   └── PermissionDenied
│   ├── APITimeout
│   ├── ConnectionError
│   ├── InvalidRequest
│   ├── InvalidAPIResponse
│   │   ├── MissingRequiredField
│   │   └── UnexpectedDataFormat
│   ├── ResourceNotFound
│   ├── ServerError
│   │   └── ServiceUnavailable
│   ├── KISAPIException
│   │   ├── KISTokenGenerationFailed
│   │   └── KISMarketClosed
│   ├── DARTAPIException
│   │   └── DARTRateLimitExceeded
│   ├── YFinanceException
│   │   └── YFinanceDataNotAvailable
│   └── MarketDataException
│       ├── NoDataAvailable
│       ├── DataQualityIssue
│       └── StalDataError
│
└── ValidationException
    ├── InvalidInputError
    ├── MissingRequiredParameter
    ├── InvalidParameterType
    ├── ValueOutOfRange
    ├── InvalidDateError
    │   ├── InvalidDateRangeError
    │   └── FutureDateNotAllowed
    ├── InvalidTickerError
    │   ├── TickerNotFoundError
    │   └── InactiveTickerError
    ├── InvalidRegionError
    ├── ConfigurationValidationError
    │   ├── InvalidConfigFormat
    │   └── MissingConfigParameter
    ├── DataValidationError
    │   ├── EmptyDataError
    │   ├── IncompleteDataError
    │   ├── DuplicateDataError
    │   └── InvalidDataFormat
    ├── BusinessRuleViolation
    ├── InsufficientDataError
    └── ConstraintViolation
"""
