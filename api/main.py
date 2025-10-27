"""
Quant Platform FastAPI Backend

Main application entry point with CORS, database connection pool,
and API route registration.

Author: Quant Platform Development Team
Date: 2025-10-22
Version: 2.0.0
"""

import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import psycopg2
from psycopg2 import pool
from loguru import logger
from prometheus_client import make_asgi_app

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.routes import auth_routes, metrics_demo_routes, strategy_routes
from api.middleware import PrometheusMiddleware
from api.utils.monitored_connection_pool import MonitoredConnectionPool


# Database connection pool (global)
db_pool = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Handles startup and shutdown events:
    - Startup: Initialize database connection pool
    - Shutdown: Close database connections
    """
    # Startup
    global db_pool

    logger.info("Starting Quant Platform API...")

    # Initialize monitored database connection pool (with Prometheus metrics)
    try:
        db_name = os.getenv('DB_NAME', 'quant_platform')
        db_pool = MonitoredConnectionPool(
            minconn=1,
            maxconn=10,
            database=db_name,  # Used for both metrics label and psycopg2 connection
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            user=os.getenv('DB_USER', os.getenv('USER', 'postgres')),
            password=os.getenv('DB_PASSWORD', '')
        )
        logger.info("✓ Monitored database connection pool initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize database pool: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down Quant Platform API...")

    if db_pool:
        db_pool.closeall()
        logger.info("✓ Database connections closed")


# Create FastAPI application
app = FastAPI(
    title="Quant Platform API",
    description="Quantitative Investment Research Platform API",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Prometheus Metrics Middleware
# Collects HTTP request metrics (duration, count, active requests)
app.add_middleware(
    PrometheusMiddleware,
    exclude_paths={'/metrics', '/metrics/'}
)


# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with user-friendly messages."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "message": str(exc) if os.getenv('DEBUG') else "An error occurred"
        }
    )


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns:
        Status and database connectivity
    """
    db_status = "healthy"

    # Check database connectivity
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.fetchone()
        cursor.close()
        release_db_connection(conn)
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "version": "2.0.0"
    }


# API v1 routes
app.include_router(
    auth_routes.router,
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

app.include_router(
    strategy_routes.router,
    prefix="/api/v1/strategies",
    tags=["Strategies"]
)

app.include_router(
    metrics_demo_routes.router,
    prefix="/api/v1",
    tags=["Metrics Demo"]
)


# Prometheus metrics endpoint
# Mount the Prometheus ASGI app to expose metrics at /metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# Database connection helpers
def get_db_connection():
    """
    Get database connection from pool.

    Returns:
        psycopg2 connection

    Raises:
        Exception: If pool not initialized or no connections available
    """
    if db_pool is None:
        raise Exception("Database pool not initialized")

    return db_pool.getconn()


def release_db_connection(conn):
    """
    Return database connection to pool.

    Args:
        conn: psycopg2 connection
    """
    if db_pool:
        db_pool.putconn(conn)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.

    Returns:
        API metadata
    """
    return {
        "name": "Quant Platform API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == '__main__':
    import uvicorn

    # Run with uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
