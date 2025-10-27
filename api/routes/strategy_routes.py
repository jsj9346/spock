#!/usr/bin/env python3
"""
strategy_routes.py - RESTful API Routes for Strategy Management

Purpose:
- Provide CRUD operations for investment strategies
- Validate factor weights and constraints
- Integrate with Factor Library and Backtesting Engine

Endpoints:
- POST   /api/v1/strategies          Create new strategy
- GET    /api/v1/strategies          List all strategies (paginated)
- GET    /api/v1/strategies/{id}     Get single strategy
- PUT    /api/v1/strategies/{id}     Full update strategy
- PATCH  /api/v1/strategies/{id}     Partial update strategy
- DELETE /api/v1/strategies/{id}     Delete strategy (with dependency check)

Design Philosophy:
- Follow auth_routes.py pattern for consistency
- Use dependency injection for database connections
- Comprehensive error handling with proper HTTP status codes
- Logging for debugging and monitoring
- Prometheus metrics via existing middleware
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import logging
from datetime import datetime

from api.models.strategy_models import (
    StrategyCreate,
    StrategyUpdate,
    StrategyResponse,
    StrategyListResponse,
    ErrorResponse
)

# Router setup
router = APIRouter()

# Logging setup
logger = logging.getLogger(__name__)


# Database dependency (follows auth_routes.py pattern)
def get_db():
    """
    Get database connection from pool.

    Yields:
        psycopg2 connection object

    Note:
        Uses connection pool from api.main for consistency
    """
    from api.main import get_db_connection, release_db_connection

    conn = get_db_connection()
    try:
        yield conn
    finally:
        release_db_connection(conn)


# Helper function to convert DB row to StrategyResponse
def db_row_to_strategy_response(row: dict) -> StrategyResponse:
    """
    Convert database row to StrategyResponse Pydantic model

    Args:
        row: Database row as dictionary (from RealDictCursor)

    Returns:
        StrategyResponse object
    """
    return StrategyResponse(
        id=row['id'],
        name=row['name'],
        description=row['description'],
        factor_weights=row['factor_weights'] if row['factor_weights'] else {},
        constraints=row['constraints'] if row['constraints'] else {},
        created_at=row['created_at'],
        updated_at=row['updated_at']
    )


@router.post(
    "",
    response_model=StrategyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new strategy",
    description="Create a new investment strategy with factor weights and constraints",
    responses={
        201: {"description": "Strategy created successfully"},
        400: {"description": "Invalid factor weights or constraints"},
        409: {"description": "Strategy name already exists"},
        500: {"description": "Internal server error"}
    }
)
def create_strategy(
    strategy: StrategyCreate,
    db=Depends(get_db)
):
    """
    Create new investment strategy

    Validation:
    - Factor weights must sum to 1.0 (±0.01 tolerance) - enforced by Pydantic
    - Strategy name must be unique
    - All constraints must be within valid ranges - enforced by Pydantic

    Args:
        strategy: StrategyCreate model with factor weights and constraints
        db: Database connection (injected)

    Returns:
        Created strategy with ID and timestamps

    Raises:
        HTTPException 409: Strategy name already exists
        HTTPException 500: Database error
    """
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)

        # Check if strategy name already exists
        cur.execute(
            "SELECT id FROM strategies WHERE name = %s",
            (strategy.name,)
        )
        existing = cur.fetchone()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Strategy with name '{strategy.name}' already exists (ID: {existing['id']})"
            )

        # Insert new strategy
        cur.execute(
            """
            INSERT INTO strategies (name, description, factor_weights, constraints, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            RETURNING id, name, description, factor_weights, constraints, created_at, updated_at
            """,
            (
                strategy.name,
                strategy.description,
                json.dumps(strategy.factor_weights.dict()),
                json.dumps(strategy.constraints.dict()) if strategy.constraints else None
            )
        )

        row = cur.fetchone()
        db.commit()

        logger.info(f"Created strategy: {strategy.name} (ID: {row['id']})")

        return db_row_to_strategy_response(row)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating strategy: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create strategy: {str(e)}"
        )
    finally:
        cur.close()


@router.get(
    "",
    response_model=StrategyListResponse,
    summary="List all strategies",
    description="Get paginated list of all strategies with optional name filtering",
    responses={
        200: {"description": "Strategies retrieved successfully"},
        500: {"description": "Internal server error"}
    }
)
def list_strategies(
    skip: int = Query(default=0, ge=0, description="Number of strategies to skip (offset)"),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum strategies per page"),
    name: Optional[str] = Query(default=None, description="Filter by strategy name (case-insensitive partial match)"),
    db=Depends(get_db)
):
    """
    List all strategies with pagination and filtering

    Args:
        skip: Number of strategies to skip (pagination offset)
        limit: Maximum strategies per page (default: 50, max: 200)
        name: Optional name filter (case-insensitive partial match)
        db: Database connection (injected)

    Returns:
        StrategyListResponse with total count and strategy list

    Raises:
        HTTPException 500: Database error
    """
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)

        # Build WHERE clause for name filtering
        where_clause = ""
        params = []

        if name:
            where_clause = "WHERE name ILIKE %s"
            params.append(f"%{name}%")

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM strategies {where_clause}"
        cur.execute(count_query, params)
        total = cur.fetchone()['total']

        # Get paginated strategies
        list_query = f"""
            SELECT id, name, description, factor_weights, constraints, created_at, updated_at
            FROM strategies
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        cur.execute(list_query, params + [limit, skip])
        rows = cur.fetchall()

        strategies = [db_row_to_strategy_response(row) for row in rows]

        logger.info(f"Listed {len(strategies)} strategies (total: {total}, skip: {skip}, limit: {limit})")

        return StrategyListResponse(
            total=total,
            skip=skip,
            limit=limit,
            strategies=strategies
        )

    except Exception as e:
        logger.error(f"Error listing strategies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list strategies: {str(e)}"
        )
    finally:
        cur.close()


@router.get(
    "/{strategy_id}",
    response_model=StrategyResponse,
    summary="Get single strategy",
    description="Retrieve a specific strategy by ID",
    responses={
        200: {"description": "Strategy retrieved successfully"},
        404: {"description": "Strategy not found"},
        500: {"description": "Internal server error"}
    }
)
def get_strategy(
    strategy_id: int,
    db=Depends(get_db)
):
    """
    Get single strategy by ID

    Args:
        strategy_id: Strategy ID
        db: Database connection (injected)

    Returns:
        StrategyResponse object

    Raises:
        HTTPException 404: Strategy not found
        HTTPException 500: Database error
    """
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)

        cur.execute(
            """
            SELECT id, name, description, factor_weights, constraints, created_at, updated_at
            FROM strategies
            WHERE id = %s
            """,
            (strategy_id,)
        )

        row = cur.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy with ID {strategy_id} not found"
            )

        logger.info(f"Retrieved strategy: {row['name']} (ID: {strategy_id})")

        return db_row_to_strategy_response(row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving strategy {strategy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve strategy: {str(e)}"
        )
    finally:
        cur.close()


@router.put(
    "/{strategy_id}",
    response_model=StrategyResponse,
    summary="Update strategy (full)",
    description="Fully update an existing strategy (all fields required)",
    responses={
        200: {"description": "Strategy updated successfully"},
        404: {"description": "Strategy not found"},
        409: {"description": "Strategy name already exists"},
        500: {"description": "Internal server error"}
    }
)
def update_strategy_full(
    strategy_id: int,
    strategy: StrategyCreate,  # Use StrategyCreate for full update (all fields required)
    db=Depends(get_db)
):
    """
    Fully update existing strategy (PUT)

    All fields are required. Use PATCH for partial updates.

    Args:
        strategy_id: Strategy ID
        strategy: Complete strategy data (all fields required)
        db: Database connection (injected)

    Returns:
        Updated StrategyResponse

    Raises:
        HTTPException 404: Strategy not found
        HTTPException 409: Strategy name already exists (if changing name)
        HTTPException 500: Database error
    """
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)

        # Check if strategy exists
        cur.execute("SELECT id, name FROM strategies WHERE id = %s", (strategy_id,))
        existing = cur.fetchone()

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy with ID {strategy_id} not found"
            )

        # Check if new name conflicts with another strategy
        if strategy.name != existing['name']:
            cur.execute(
                "SELECT id FROM strategies WHERE name = %s AND id != %s",
                (strategy.name, strategy_id)
            )
            name_conflict = cur.fetchone()

            if name_conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Strategy with name '{strategy.name}' already exists (ID: {name_conflict['id']})"
                )

        # Update strategy
        cur.execute(
            """
            UPDATE strategies
            SET name = %s,
                description = %s,
                factor_weights = %s,
                constraints = %s,
                updated_at = NOW()
            WHERE id = %s
            RETURNING id, name, description, factor_weights, constraints, created_at, updated_at
            """,
            (
                strategy.name,
                strategy.description,
                json.dumps(strategy.factor_weights.dict()),
                json.dumps(strategy.constraints.dict()) if strategy.constraints else None,
                strategy_id
            )
        )

        row = cur.fetchone()
        db.commit()

        logger.info(f"Updated strategy (full): {strategy.name} (ID: {strategy_id})")

        return db_row_to_strategy_response(row)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating strategy {strategy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update strategy: {str(e)}"
        )
    finally:
        cur.close()


@router.patch(
    "/{strategy_id}",
    response_model=StrategyResponse,
    summary="Update strategy (partial)",
    description="Partially update an existing strategy (only provided fields are updated)",
    responses={
        200: {"description": "Strategy updated successfully"},
        404: {"description": "Strategy not found"},
        409: {"description": "Strategy name already exists"},
        500: {"description": "Internal server error"}
    }
)
def update_strategy_partial(
    strategy_id: int,
    strategy: StrategyUpdate,
    db=Depends(get_db)
):
    """
    Partially update existing strategy (PATCH)

    Only provided fields are updated. Omitted fields remain unchanged.

    Args:
        strategy_id: Strategy ID
        strategy: Partial strategy data (all fields optional)
        db: Database connection (injected)

    Returns:
        Updated StrategyResponse

    Raises:
        HTTPException 404: Strategy not found
        HTTPException 409: Strategy name already exists (if changing name)
        HTTPException 500: Database error
    """
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)

        # Check if strategy exists
        cur.execute("SELECT id, name FROM strategies WHERE id = %s", (strategy_id,))
        existing = cur.fetchone()

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy with ID {strategy_id} not found"
            )

        # Build dynamic UPDATE query for non-None fields
        update_fields = []
        params = []

        if strategy.name is not None:
            # Check name conflict
            cur.execute(
                "SELECT id FROM strategies WHERE name = %s AND id != %s",
                (strategy.name, strategy_id)
            )
            name_conflict = cur.fetchone()

            if name_conflict:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Strategy with name '{strategy.name}' already exists (ID: {name_conflict['id']})"
                )

            update_fields.append("name = %s")
            params.append(strategy.name)

        if strategy.description is not None:
            update_fields.append("description = %s")
            params.append(strategy.description)

        if strategy.factor_weights is not None:
            update_fields.append("factor_weights = %s")
            params.append(json.dumps(strategy.factor_weights.dict()))

        if strategy.constraints is not None:
            update_fields.append("constraints = %s")
            params.append(json.dumps(strategy.constraints.dict()))

        # Always update updated_at
        update_fields.append("updated_at = NOW()")

        if not update_fields:
            # No fields to update, just return current strategy
            cur.execute(
                """
                SELECT id, name, description, factor_weights, constraints, created_at, updated_at
                FROM strategies
                WHERE id = %s
                """,
                (strategy_id,)
            )
            row = cur.fetchone()
            return db_row_to_strategy_response(row)

        # Execute update
        update_query = f"""
            UPDATE strategies
            SET {', '.join(update_fields)}
            WHERE id = %s
            RETURNING id, name, description, factor_weights, constraints, created_at, updated_at
        """
        params.append(strategy_id)

        cur.execute(update_query, params)
        row = cur.fetchone()
        db.commit()

        logger.info(f"Updated strategy (partial): {row['name']} (ID: {strategy_id})")

        return db_row_to_strategy_response(row)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error partially updating strategy {strategy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update strategy: {str(e)}"
        )
    finally:
        cur.close()


@router.delete(
    "/{strategy_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete strategy",
    description="Delete a strategy after checking for dependencies (backtests, holdings)",
    responses={
        204: {"description": "Strategy deleted successfully"},
        404: {"description": "Strategy not found"},
        409: {"description": "Strategy is in use (has dependencies)"},
        500: {"description": "Internal server error"}
    }
)
def delete_strategy(
    strategy_id: int,
    db=Depends(get_db)
):
    """
    Delete strategy with dependency check

    Checks for dependencies before deletion:
    - backtest_results
    - portfolio_holdings
    - portfolio_transactions
    - walk_forward_results

    Args:
        strategy_id: Strategy ID
        db: Database connection (injected)

    Returns:
        204 No Content on success

    Raises:
        HTTPException 404: Strategy not found
        HTTPException 409: Strategy has dependencies (cannot delete)
        HTTPException 500: Database error
    """
    try:
        cur = db.cursor(cursor_factory=RealDictCursor)

        # Check if strategy exists
        cur.execute("SELECT id, name FROM strategies WHERE id = %s", (strategy_id,))
        existing = cur.fetchone()

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Strategy with ID {strategy_id} not found"
            )

        # Check dependencies
        dependencies = []

        # Check backtest_results
        cur.execute(
            "SELECT COUNT(*) as count FROM backtest_results WHERE strategy_id = %s",
            (strategy_id,)
        )
        backtest_count = cur.fetchone()['count']
        if backtest_count > 0:
            dependencies.append(f"{backtest_count} backtest result(s)")

        # Check portfolio_holdings
        cur.execute(
            "SELECT COUNT(*) as count FROM portfolio_holdings WHERE strategy_id = %s",
            (strategy_id,)
        )
        holdings_count = cur.fetchone()['count']
        if holdings_count > 0:
            dependencies.append(f"{holdings_count} portfolio holding(s)")

        # Check portfolio_transactions (if table exists)
        try:
            cur.execute(
                "SELECT COUNT(*) as count FROM portfolio_transactions WHERE strategy_id = %s",
                (strategy_id,)
            )
            transactions_count = cur.fetchone()['count']
            if transactions_count > 0:
                dependencies.append(f"{transactions_count} transaction(s)")
        except psycopg2.errors.UndefinedTable:
            # Table doesn't exist yet, skip
            pass

        # Check walk_forward_results (if table exists)
        try:
            cur.execute(
                "SELECT COUNT(*) as count FROM walk_forward_results WHERE strategy_id = %s",
                (strategy_id,)
            )
            wf_count = cur.fetchone()['count']
            if wf_count > 0:
                dependencies.append(f"{wf_count} walk-forward result(s)")
        except psycopg2.errors.UndefinedTable:
            # Table doesn't exist yet, skip
            pass

        if dependencies:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete strategy '{existing['name']}' (ID: {strategy_id}). "
                       f"Dependencies exist: {', '.join(dependencies)}. "
                       f"Delete dependent records first or use soft delete."
            )

        # Delete strategy
        cur.execute("DELETE FROM strategies WHERE id = %s", (strategy_id,))
        db.commit()

        logger.info(f"Deleted strategy: {existing['name']} (ID: {strategy_id})")

        return None  # 204 No Content

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting strategy {strategy_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete strategy: {str(e)}"
        )
    finally:
        cur.close()
