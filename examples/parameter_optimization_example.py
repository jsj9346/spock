"""
Parameter Optimization Usage Examples

This file demonstrates how to use the ParameterOptimizer framework
for automated parameter tuning of trading strategies.

Examples:
  1. Basic grid search optimization
  2. Parameter importance analysis
  3. Multi-objective optimization
  4. Early stopping
  5. Result persistence (JSON export)
  6. Real-world workflow

Requirements:
  - Database with OHLCV data (250+ days for train/validation split)
  - BacktestConfig with strategy parameters to optimize
"""

from datetime import date
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.backtesting import (
    BacktestConfig,
    GridSearchOptimizer,
    ParameterSpec,
    OptimizationConfig,
)
from modules.db_manager_sqlite import SQLiteDatabaseManager


# ============================================================================
# Example 1: Basic Grid Search Optimization
# ============================================================================

def example_basic_grid_search():
    """
    Demonstrate basic grid search parameter optimization.

    This example optimizes two parameters:
      - kelly_multiplier: Position sizing aggressiveness
      - score_threshold: Minimum technical analysis score for entry
    """
    print("=" * 80)
    print("Example 1: Basic Grid Search Optimization")
    print("=" * 80)

    # Initialize database
    db = SQLiteDatabaseManager()

    # Define base backtest configuration
    base_config = BacktestConfig(
        start_date=date(2023, 1, 1),  # Will be overridden by optimization
        end_date=date(2023, 12, 31),
        regions=["KR"],
        tickers=None,  # Will scan all tickers
        initial_capital=100_000_000,
    )

    # Define parameter space to search
    parameter_space = {
        # Kelly multiplier: How aggressively to size positions
        'kelly_multiplier': ParameterSpec(
            type='float',
            min_value=0.25,
            max_value=1.0,
            step=0.25,  # Test: 0.25, 0.50, 0.75, 1.00
        ),
        # Score threshold: Minimum technical score for entry
        'score_threshold': ParameterSpec(
            type='int',
            min_value=60,
            max_value=80,
            step=5,  # Test: 60, 65, 70, 75, 80
        ),
    }

    # Total combinations: 4 kelly × 5 threshold = 20 trials

    # Create optimization config
    opt_config = OptimizationConfig(
        parameter_space=parameter_space,
        objective='sharpe_ratio',  # Optimize for risk-adjusted returns
        maximize=True,
        # Train/validation split (prevent overfitting)
        train_start_date=date(2023, 1, 1),
        train_end_date=date(2023, 6, 30),
        validation_start_date=date(2023, 7, 1),
        validation_end_date=date(2023, 12, 31),
        max_trials=100,
        n_jobs=4,  # Use 4 parallel workers
        random_seed=42,
        base_config=base_config,
    )

    # Run optimization
    print(f"\nRunning grid search: {4 * 5} parameter combinations")
    print(f"Parallel workers: {opt_config.n_jobs}")

    optimizer = GridSearchOptimizer(opt_config, db)
    result = optimizer.optimize()

    # Display results
    print(f"\n{'='*80}")
    print("Optimization Results")
    print(f"{'='*80}")
    print(f"Best parameters: {result.best_parameters}")
    print(f"Train Sharpe ratio: {result.train_objective:.4f}")
    print(f"Validation Sharpe ratio: {result.validation_objective:.4f}")
    print(f"Total trials: {len(result.all_trials)}")
    print(f"Execution time: {result.execution_time_seconds:.1f}s")

    # Show parameter importance
    print(f"\nParameter Importance:")
    for param_name, importance in result.parameter_importance.items():
        print(f"  {param_name}: {importance:.2%}")

    return result


# ============================================================================
# Example 2: Multi-Objective Optimization
# ============================================================================

def example_multi_objective_optimization():
    """
    Demonstrate optimization with different objectives.

    Compare results across multiple objectives:
      - sharpe_ratio: Risk-adjusted returns
      - sortino_ratio: Downside risk-adjusted returns
      - calmar_ratio: Return/max drawdown ratio
      - total_return: Absolute returns (not risk-adjusted)
    """
    print("\n" + "=" * 80)
    print("Example 2: Multi-Objective Optimization")
    print("=" * 80)

    db = SQLiteDatabaseManager()

    base_config = BacktestConfig(
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        regions=["KR"],
        initial_capital=100_000_000,
    )

    # Simple parameter space
    parameter_space = {
        'kelly_multiplier': ParameterSpec(
            type='float',
            min_value=0.25,
            max_value=0.75,
            step=0.25,  # 3 values
        ),
    }

    # Test different objectives
    objectives = ['sharpe_ratio', 'sortino_ratio', 'calmar_ratio', 'total_return']
    results = {}

    for objective in objectives:
        print(f"\nOptimizing for: {objective}")

        opt_config = OptimizationConfig(
            parameter_space=parameter_space,
            objective=objective,
            train_start_date=date(2023, 1, 1),
            train_end_date=date(2023, 6, 30),
            validation_start_date=date(2023, 7, 1),
            validation_end_date=date(2023, 12, 31),
            base_config=base_config,
        )

        optimizer = GridSearchOptimizer(opt_config, db)
        result = optimizer.optimize()
        results[objective] = result

        print(f"  Best kelly_multiplier: {result.best_parameters['kelly_multiplier']}")
        print(f"  Train objective: {result.train_objective:.4f}")
        print(f"  Validation objective: {result.validation_objective:.4f}")

    # Compare best parameters across objectives
    print(f"\n{'='*80}")
    print("Summary: Best Parameters by Objective")
    print(f"{'='*80}")
    for objective, result in results.items():
        print(f"{objective:20s}: kelly={result.best_parameters['kelly_multiplier']:.2f}, "
              f"train={result.train_objective:.4f}, val={result.validation_objective:.4f}")

    return results


# ============================================================================
# Example 3: Early Stopping
# ============================================================================

def example_early_stopping():
    """
    Demonstrate early stopping to save computation.

    Early stopping terminates optimization if no improvement
    is detected for N consecutive trials.
    """
    print("\n" + "=" * 80)
    print("Example 3: Early Stopping")
    print("=" * 80)

    db = SQLiteDatabaseManager()

    base_config = BacktestConfig(
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        regions=["KR"],
        initial_capital=100_000_000,
    )

    # Large parameter space (would take long time)
    parameter_space = {
        'kelly_multiplier': ParameterSpec(
            type='float',
            min_value=0.1,
            max_value=1.0,
            step=0.05,  # 19 values
        ),
        'score_threshold': ParameterSpec(
            type='int',
            min_value=50,
            max_value=85,
            step=1,  # 36 values
        ),
    }

    # Total combinations: 19 × 36 = 684 trials!
    # With early stopping, we can terminate much earlier

    opt_config = OptimizationConfig(
        parameter_space=parameter_space,
        objective='sharpe_ratio',
        train_start_date=date(2023, 1, 1),
        train_end_date=date(2023, 6, 30),
        validation_start_date=date(2023, 7, 1),
        validation_end_date=date(2023, 12, 31),
        early_stopping_patience=20,  # Stop if no improvement for 20 trials
        n_jobs=4,
        base_config=base_config,
    )

    print(f"\nTotal parameter combinations: {19 * 36}")
    print(f"Early stopping patience: {opt_config.early_stopping_patience} trials")

    optimizer = GridSearchOptimizer(opt_config, db)
    result = optimizer.optimize()

    print(f"\n{'='*80}")
    print(f"Early stopping saved {19 * 36 - len(result.all_trials)} trials!")
    print(f"Trials executed: {len(result.all_trials)} / {19 * 36}")
    print(f"Best parameters: {result.best_parameters}")
    print(f"Execution time: {result.execution_time_seconds:.1f}s")

    return result


# ============================================================================
# Example 4: Categorical Parameters
# ============================================================================

def example_categorical_parameters():
    """
    Demonstrate optimization with categorical parameters.

    Categorical parameters allow testing discrete choices like:
      - Risk profiles (conservative/moderate/aggressive)
      - Pattern types (Stage2/VCP/CupHandle)
      - Exit strategies (trailing_stop/profit_target/hybrid)
    """
    print("\n" + "=" * 80)
    print("Example 4: Categorical Parameters")
    print("=" * 80)

    db = SQLiteDatabaseManager()

    base_config = BacktestConfig(
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        regions=["KR"],
        initial_capital=100_000_000,
    )

    # Mix of continuous and categorical parameters
    parameter_space = {
        # Continuous parameter
        'kelly_multiplier': ParameterSpec(
            type='float',
            min_value=0.25,
            max_value=0.75,
            step=0.25,
        ),
        # Categorical parameter
        'risk_profile': ParameterSpec(
            type='categorical',
            values=['conservative', 'moderate', 'aggressive'],
        ),
    }

    # Total combinations: 3 kelly × 3 risk = 9 trials

    opt_config = OptimizationConfig(
        parameter_space=parameter_space,
        objective='sharpe_ratio',
        train_start_date=date(2023, 1, 1),
        train_end_date=date(2023, 6, 30),
        validation_start_date=date(2023, 7, 1),
        validation_end_date=date(2023, 12, 31),
        base_config=base_config,
    )

    print(f"\nOptimizing categorical + continuous parameters")
    print(f"Total combinations: {3 * 3}")

    optimizer = GridSearchOptimizer(opt_config, db)
    result = optimizer.optimize()

    print(f"\n{'='*80}")
    print(f"Best parameters:")
    print(f"  kelly_multiplier: {result.best_parameters['kelly_multiplier']}")
    print(f"  risk_profile: {result.best_parameters['risk_profile']}")
    print(f"Train Sharpe: {result.train_objective:.4f}")
    print(f"Validation Sharpe: {result.validation_objective:.4f}")

    return result


# ============================================================================
# Example 5: Result Persistence
# ============================================================================

def example_result_persistence(result):
    """
    Demonstrate saving optimization results to JSON.

    Args:
        result: OptimizationResult from previous optimization
    """
    print("\n" + "=" * 80)
    print("Example 5: Result Persistence")
    print("=" * 80)

    # Convert to dictionary
    result_dict = result.to_dict()

    # Save to JSON file
    output_path = "optimization_results.json"

    with open(output_path, 'w') as f:
        json.dump(result_dict, f, indent=2, default=str)

    print(f"\nResults saved to: {output_path}")
    print(f"File size: {os.path.getsize(output_path)} bytes")

    # Display summary
    print(f"\nSummary:")
    print(f"  Best parameters: {result_dict['best_parameters']}")
    print(f"  Train objective: {result_dict['train_objective']:.4f}")
    print(f"  Validation objective: {result_dict['validation_objective']:.4f}")
    print(f"  Total trials: {result_dict['n_trials']}")
    print(f"  Execution time: {result_dict['execution_time_seconds']:.1f}s")
    print(f"  Optimization method: {result_dict['optimization_method']}")


# ============================================================================
# Example 6: Real-World Workflow
# ============================================================================

def example_real_world_workflow():
    """
    Demonstrate complete real-world optimization workflow.

    Steps:
      1. Define parameter space based on domain knowledge
      2. Run coarse grid search
      3. Analyze parameter importance
      4. Run fine grid search on important parameters
      5. Validate on test set
      6. Save results and deploy
    """
    print("\n" + "=" * 80)
    print("Example 6: Real-World Optimization Workflow")
    print("=" * 80)

    db = SQLiteDatabaseManager()

    base_config = BacktestConfig(
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        regions=["KR"],
        initial_capital=100_000_000,
    )

    # Step 1: Coarse grid search (wide ranges, large steps)
    print("\nStep 1: Coarse Grid Search (Exploration)")
    print("-" * 80)

    coarse_parameter_space = {
        'kelly_multiplier': ParameterSpec(
            type='float',
            min_value=0.2,
            max_value=1.0,
            step=0.2,  # Coarse: 5 values
        ),
        'score_threshold': ParameterSpec(
            type='int',
            min_value=50,
            max_value=80,
            step=10,  # Coarse: 4 values
        ),
        'max_position_size': ParameterSpec(
            type='float',
            min_value=0.10,
            max_value=0.20,
            step=0.05,  # Coarse: 3 values
        ),
    }

    # Total: 5 × 4 × 3 = 60 trials

    coarse_config = OptimizationConfig(
        parameter_space=coarse_parameter_space,
        objective='sharpe_ratio',
        train_start_date=date(2023, 1, 1),
        train_end_date=date(2023, 6, 30),
        validation_start_date=date(2023, 7, 1),
        validation_end_date=date(2023, 12, 31),
        n_jobs=4,
        base_config=base_config,
    )

    print(f"Parameter combinations: {5 * 4 * 3}")

    coarse_optimizer = GridSearchOptimizer(coarse_config, db)
    coarse_result = coarse_optimizer.optimize()

    print(f"\nCoarse search results:")
    print(f"  Best params: {coarse_result.best_parameters}")
    print(f"  Train Sharpe: {coarse_result.train_objective:.4f}")
    print(f"  Validation Sharpe: {coarse_result.validation_objective:.4f}")

    # Step 2: Analyze parameter importance
    print("\nStep 2: Parameter Importance Analysis")
    print("-" * 80)

    for param_name, importance in coarse_result.parameter_importance.items():
        bar = '█' * int(importance * 50)
        print(f"  {param_name:20s}: {importance:.2%} {bar}")

    # Step 3: Fine grid search (narrow ranges around best values)
    print("\nStep 3: Fine Grid Search (Exploitation)")
    print("-" * 80)

    # Focus on region around best parameters from coarse search
    best_kelly = coarse_result.best_parameters['kelly_multiplier']
    best_score = coarse_result.best_parameters['score_threshold']

    fine_parameter_space = {
        'kelly_multiplier': ParameterSpec(
            type='float',
            min_value=max(0.1, best_kelly - 0.1),
            max_value=min(1.0, best_kelly + 0.1),
            step=0.05,  # Fine: ~5 values
        ),
        'score_threshold': ParameterSpec(
            type='int',
            min_value=max(50, best_score - 5),
            max_value=min(85, best_score + 5),
            step=2,  # Fine: ~6 values
        ),
    }

    # Note: Only optimize most important parameters in fine search

    fine_config = OptimizationConfig(
        parameter_space=fine_parameter_space,
        objective='sharpe_ratio',
        train_start_date=date(2023, 1, 1),
        train_end_date=date(2023, 6, 30),
        validation_start_date=date(2023, 7, 1),
        validation_end_date=date(2023, 12, 31),
        n_jobs=4,
        base_config=base_config,
    )

    print(f"Refining around best coarse parameters")

    fine_optimizer = GridSearchOptimizer(fine_config, db)
    fine_result = fine_optimizer.optimize()

    print(f"\nFine search results:")
    print(f"  Best params: {fine_result.best_parameters}")
    print(f"  Train Sharpe: {fine_result.train_objective:.4f}")
    print(f"  Validation Sharpe: {fine_result.validation_objective:.4f}")

    # Step 4: Compare improvement
    print(f"\n{'='*80}")
    print("Improvement from Coarse → Fine")
    print(f"{'='*80}")
    train_improvement = ((fine_result.train_objective - coarse_result.train_objective)
                        / abs(coarse_result.train_objective) * 100)
    val_improvement = ((fine_result.validation_objective - coarse_result.validation_objective)
                      / abs(coarse_result.validation_objective) * 100)

    print(f"Train Sharpe improvement: {train_improvement:+.1f}%")
    print(f"Validation Sharpe improvement: {val_improvement:+.1f}%")

    # Step 5: Save final results
    print("\nStep 5: Save Results")
    print("-" * 80)

    example_result_persistence(fine_result)

    print("\n✅ Optimization workflow complete!")
    print("   Next steps:")
    print("   - Deploy best parameters to production")
    print("   - Monitor performance on live data")
    print("   - Re-optimize quarterly with new data")

    return fine_result


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    print("\n")
    print("="* 80)
    print("Parameter Optimization Examples for Spock Trading System")
    print("=" * 80)

    # Example 1: Basic optimization
    result1 = example_basic_grid_search()

    # Example 2: Multi-objective
    results2 = example_multi_objective_optimization()

    # Example 3: Early stopping
    result3 = example_early_stopping()

    # Example 4: Categorical parameters
    result4 = example_categorical_parameters()

    # Example 5: Save results
    example_result_persistence(result1)

    # Example 6: Real-world workflow
    result6 = example_real_world_workflow()

    print("\n" + "=" * 80)
    print("All examples completed successfully!")
    print("=" * 80)
