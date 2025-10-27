"""
VaR (Value at Risk) Calculator

Implements three industry-standard VaR calculation methods:
1. Historical Simulation: Empirical distribution of returns
2. Parametric (Variance-Covariance): Assumes normal distribution
3. Monte Carlo: Simulates future returns using historical parameters

NO database dependencies - pure calculation logic using NumPy/pandas.

Author: Quant Platform Development Team
Version: 1.0.0
Status: Phase 5 - Track 5 Implementation
"""

from modules.risk.risk_base import RiskCalculator, RiskConfig, VaRResult
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime
from typing import Optional, Tuple


class VaRCalculator(RiskCalculator):
    """
    Value at Risk (VaR) calculator supporting multiple methods

    VaR represents the maximum expected loss over a given time horizon
    at a specified confidence level (e.g., 95% or 99%).

    Supported Methods:
    - Historical Simulation: Uses empirical distribution of historical returns
    - Parametric (Gaussian): Assumes returns are normally distributed
    - Monte Carlo: Simulates future returns using historical parameters

    Example:
        >>> from modules.risk import VaRCalculator, RiskConfig
        >>> import pandas as pd
        >>> import numpy as np
        >>>
        >>> # Sample portfolio returns
        >>> np.random.seed(42)
        >>> portfolio_returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        >>>
        >>> # Calculate VaR
        >>> config = RiskConfig(confidence_level=0.95, time_horizon_days=10)
        >>> var_calc = VaRCalculator(config)
        >>> result = var_calc.calculate(portfolio_returns, portfolio_value=100_000_000)
        >>>
        >>> print(f"VaR (95%, 10-day): {result.var_value:,.0f} KRW")
        >>> print(f"VaR as %: {result.var_percent:.2%}")
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        """
        Initialize VaR calculator

        Args:
            config: Risk calculation configuration (uses defaults if None)

        Raises:
            ValueError: If configuration is invalid
        """
        super().__init__(config)

    def calculate(
        self,
        portfolio_returns: pd.Series,
        portfolio_value: float,
        method: Optional[str] = None
    ) -> VaRResult:
        """
        Calculate Value at Risk

        Args:
            portfolio_returns: Historical portfolio returns (daily)
            portfolio_value: Current portfolio value in currency
            method: VaR method ('historical', 'parametric', 'monte_carlo')
                   Overrides config if provided

        Returns:
            VaRResult with VaR value and metadata

        Raises:
            ValueError: If inputs are invalid

        Example:
            >>> result = var_calc.calculate(returns, 100_000_000, method='historical')
            >>> print(result)
            VaR(95%, 10d): -5,234,567 (-5.23%) [historical]
        """
        # Validate inputs
        self.validate_inputs(returns=portfolio_returns)

        # Use provided method or config default
        calc_method = method or self.config.var_method

        # Calculate VaR based on method
        if calc_method == 'historical':
            var_percent = self._historical_var(portfolio_returns)
        elif calc_method == 'parametric':
            var_percent = self._parametric_var(portfolio_returns)
        elif calc_method == 'monte_carlo':
            var_percent = self._monte_carlo_var(portfolio_returns)
        else:
            raise ValueError(
                f"Invalid VaR method: {calc_method}. "
                f"Must be 'historical', 'parametric', or 'monte_carlo'"
            )

        # Convert to currency value
        var_value = var_percent * portfolio_value

        # Create result with metadata
        return VaRResult(
            var_value=var_value,
            var_percent=var_percent,
            confidence_level=self.config.confidence_level,
            time_horizon_days=self.config.time_horizon_days,
            method=calc_method,
            portfolio_value=portfolio_value,
            calculation_date=datetime.now(),
            metadata={
                'observations': len(portfolio_returns),
                'mean_return': float(portfolio_returns.mean()),
                'volatility': float(portfolio_returns.std()),
                'min_return': float(portfolio_returns.min()),
                'max_return': float(portfolio_returns.max())
            }
        )

    def _historical_var(self, returns: pd.Series) -> float:
        """
        Calculate Historical Simulation VaR

        Uses empirical distribution of historical returns without
        assuming any specific distribution.

        Method:
        1. Scale returns to time horizon if needed (overlapping periods)
        2. Apply exponential weighting if configured
        3. Calculate percentile at (1 - confidence_level)

        Args:
            returns: Historical returns series

        Returns:
            VaR as percentage of portfolio value (negative)
        """
        # Scale returns to time horizon if multi-day
        if self.config.time_horizon_days > 1:
            scaled_returns = self._scale_returns_to_horizon(returns)
        else:
            scaled_returns = returns

        # Apply exponential weighting if configured
        if self.config.exponential_weighting:
            weights = self._calculate_exponential_weights(len(scaled_returns))
            var_percent = self._weighted_percentile(
                scaled_returns.values,
                weights,
                1 - self.config.confidence_level
            )
        else:
            # Simple percentile calculation
            var_percent = np.percentile(
                scaled_returns,
                (1 - self.config.confidence_level) * 100
            )

        return float(var_percent)

    def _parametric_var(self, returns: pd.Series) -> float:
        """
        Calculate Parametric VaR (Variance-Covariance method)

        Assumes returns are normally distributed.

        Formula:
            VaR = μ * T - z * σ * sqrt(T)

        where:
            μ = mean return
            σ = standard deviation
            T = time horizon (days)
            z = z-score at confidence level

        Args:
            returns: Historical returns series

        Returns:
            VaR as percentage of portfolio value (negative)

        Note:
            This method is fast but sensitive to distribution assumptions.
            May underestimate VaR if returns have fat tails.
        """
        # Calculate parameters from historical data
        mu = returns.mean()
        sigma = returns.std()

        # Z-score for confidence level
        z_score = stats.norm.ppf(1 - self.config.confidence_level)

        # Scaling factor for time horizon
        scaling_factor = np.sqrt(self.config.time_horizon_days)

        # Parametric VaR formula
        var_percent = (mu * self.config.time_horizon_days +
                      z_score * sigma * scaling_factor)

        return float(var_percent)

    def _monte_carlo_var(self, returns: pd.Series) -> float:
        """
        Calculate Monte Carlo VaR

        Simulates future returns using historical mean and volatility,
        then calculates empirical percentile from simulations.

        Method:
        1. Estimate μ and σ from historical data
        2. Generate N simulations of T-day returns
        3. Calculate cumulative return for each simulation
        4. Extract percentile at (1 - confidence_level)

        Args:
            returns: Historical returns series

        Returns:
            VaR as percentage of portfolio value (negative)

        Note:
            Assumes returns are normally distributed but captures
            variability through simulation. More robust than parametric
            for multi-day horizons.
        """
        mu = returns.mean()
        sigma = returns.std()

        # Generate random returns for time horizon
        # Shape: (num_simulations, time_horizon_days)
        simulated_returns = np.random.normal(
            mu,
            sigma,
            (self.config.monte_carlo_simulations, self.config.time_horizon_days)
        )

        # Calculate cumulative returns for each simulation
        cumulative_returns = np.sum(simulated_returns, axis=1)

        # VaR is the percentile of simulated returns
        var_percent = np.percentile(
            cumulative_returns,
            (1 - self.config.confidence_level) * 100
        )

        return float(var_percent)

    def calculate_component_var(
        self,
        asset_returns: pd.DataFrame,
        weights: pd.Series,
        portfolio_value: float,
        method: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Calculate component VaR (contribution of each asset to portfolio VaR)

        Component VaR shows how much each asset contributes to total
        portfolio VaR. Useful for risk budgeting and position sizing.

        Method:
        1. Calculate portfolio VaR
        2. For each asset, calculate marginal VaR using finite differences
        3. Component VaR = weight * marginal VaR

        Args:
            asset_returns: Historical returns for each asset (DataFrame)
            weights: Portfolio weights (Series)
            portfolio_value: Current portfolio value
            method: VaR calculation method (uses config if None)

        Returns:
            DataFrame with columns:
            - ticker: Asset ticker
            - weight: Portfolio weight
            - component_var: Contribution to portfolio VaR (currency)
            - component_var_pct: Contribution as % of portfolio value

        Example:
            >>> component_vars = var_calc.calculate_component_var(
            ...     asset_returns, weights, 100_000_000
            ... )
            >>> print(component_vars.nlargest(5, 'component_var'))
            # Shows top 5 contributors to portfolio VaR
        """
        # Validate inputs
        self.validate_inputs(weights=weights)

        if not weights.index.equals(asset_returns.columns):
            raise ValueError(
                "Weights index must match asset_returns columns"
            )

        # Calculate portfolio returns
        portfolio_returns = (asset_returns * weights).sum(axis=1)

        # Calculate portfolio VaR
        portfolio_var = self.calculate(
            portfolio_returns,
            portfolio_value,
            method
        )

        # Calculate marginal VaR for each asset using finite differences
        component_vars = []
        epsilon = 0.001  # Small perturbation in weight

        for ticker in weights.index:
            # Calculate marginal contribution using finite differences
            # Increase weight slightly, decrease all others proportionally
            delta_weight = epsilon

            # Create perturbed weights: increase this asset, decrease others
            perturbed_weights = weights.copy()
            other_assets = weights.index != ticker

            # Add delta to target asset
            perturbed_weights[ticker] += delta_weight

            # Subtract proportionally from other assets to maintain sum = 1
            reduction_factor = delta_weight / weights[other_assets].sum()
            perturbed_weights[other_assets] -= weights[other_assets] * reduction_factor

            # Recalculate portfolio returns and VaR with perturbed weights
            perturbed_returns = (asset_returns * perturbed_weights).sum(axis=1)
            perturbed_var = self.calculate(
                perturbed_returns,
                portfolio_value,
                method
            )

            # Marginal VaR = dVaR / dw (change in VaR per unit change in weight)
            marginal_var = (perturbed_var.var_value - portfolio_var.var_value) / delta_weight

            # Component VaR = w * marginal VaR
            component_var = weights[ticker] * marginal_var

            component_vars.append({
                'ticker': ticker,
                'weight': weights[ticker],
                'component_var': component_var,
                'component_var_pct': component_var / portfolio_value
            })

        # Create DataFrame
        result_df = pd.DataFrame(component_vars)

        # Sort by absolute contribution (largest risk contributors first)
        result_df = result_df.sort_values(
            'component_var',
            key=abs,
            ascending=False
        ).reset_index(drop=True)

        return result_df

    def calculate_var_by_confidence(
        self,
        portfolio_returns: pd.Series,
        portfolio_value: float,
        confidence_levels: Optional[list] = None,
        method: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Calculate VaR at multiple confidence levels

        Useful for understanding tail risk at different probability thresholds.

        Args:
            portfolio_returns: Historical portfolio returns
            portfolio_value: Current portfolio value
            confidence_levels: List of confidence levels (e.g., [0.90, 0.95, 0.99])
            method: VaR calculation method (uses config if None)

        Returns:
            DataFrame with VaR at each confidence level

        Example:
            >>> vars_df = var_calc.calculate_var_by_confidence(
            ...     returns, 100_000_000,
            ...     confidence_levels=[0.90, 0.95, 0.99]
            ... )
            >>> print(vars_df)
            #   confidence_level  var_value  var_percent
            # 0             0.90 -3,500,000      -3.50%
            # 1             0.95 -5,200,000      -5.20%
            # 2             0.99 -8,100,000      -8.10%
        """
        if confidence_levels is None:
            confidence_levels = [0.90, 0.95, 0.99]

        results = []
        original_confidence = self.config.confidence_level

        for conf_level in confidence_levels:
            # Temporarily update confidence level
            self.config.confidence_level = conf_level

            # Calculate VaR
            result = self.calculate(portfolio_returns, portfolio_value, method)

            results.append({
                'confidence_level': conf_level,
                'var_value': result.var_value,
                'var_percent': result.var_percent
            })

        # Restore original confidence level
        self.config.confidence_level = original_confidence

        return pd.DataFrame(results)

    def calculate_var_by_horizon(
        self,
        portfolio_returns: pd.Series,
        portfolio_value: float,
        horizons: Optional[list] = None,
        method: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Calculate VaR at multiple time horizons

        Shows how VaR increases with longer holding periods.

        Args:
            portfolio_returns: Historical portfolio returns
            portfolio_value: Current portfolio value
            horizons: List of time horizons in days (e.g., [1, 10, 20])
            method: VaR calculation method (uses config if None)

        Returns:
            DataFrame with VaR at each horizon

        Example:
            >>> vars_df = var_calc.calculate_var_by_horizon(
            ...     returns, 100_000_000,
            ...     horizons=[1, 10, 20]
            ... )
            >>> print(vars_df)
            #   horizon_days  var_value  var_percent
            # 0            1 -1,800,000      -1.80%
            # 1           10 -5,200,000      -5.20%
            # 2           20 -7,500,000      -7.50%
        """
        if horizons is None:
            horizons = [1, 10, 20]

        results = []
        original_horizon = self.config.time_horizon_days

        for horizon in horizons:
            # Temporarily update time horizon
            self.config.time_horizon_days = horizon

            # Calculate VaR
            result = self.calculate(portfolio_returns, portfolio_value, method)

            results.append({
                'horizon_days': horizon,
                'var_value': result.var_value,
                'var_percent': result.var_percent
            })

        # Restore original horizon
        self.config.time_horizon_days = original_horizon

        return pd.DataFrame(results)

    def backtest_var(
        self,
        portfolio_returns: pd.Series,
        portfolio_value: float,
        method: Optional[str] = None,
        window_size: int = 252
    ) -> Tuple[float, pd.DataFrame]:
        """
        Backtest VaR model using rolling window

        Calculates how often actual losses exceed VaR predictions.
        A well-calibrated model should have violations approximately
        equal to (1 - confidence_level).

        Args:
            portfolio_returns: Historical portfolio returns
            portfolio_value: Portfolio value for each period
            method: VaR calculation method (uses config if None)
            window_size: Rolling window size for VaR calculation

        Returns:
            Tuple of (violation_rate, backtest_df)
            - violation_rate: % of observations where loss > VaR
            - backtest_df: DataFrame with date, actual_loss, var_prediction, violation

        Example:
            >>> violation_rate, backtest_df = var_calc.backtest_var(returns, 100_000_000)
            >>> print(f"Violation rate: {violation_rate:.2%}")
            >>> print(f"Expected: {1-0.95:.2%}")
            # Violation rate: 5.2%
            # Expected: 5.0%
        """
        if len(portfolio_returns) < window_size + self.config.time_horizon_days:
            raise ValueError(
                f"Insufficient data for backtesting. "
                f"Need at least {window_size + self.config.time_horizon_days} observations"
            )

        backtest_results = []

        # Rolling window backtest
        for i in range(window_size, len(portfolio_returns) - self.config.time_horizon_days):
            # Use window_size historical data for VaR calculation
            historical_window = portfolio_returns.iloc[i-window_size:i]

            # Calculate VaR
            var_result = self.calculate(historical_window, portfolio_value, method)

            # Actual forward-looking loss
            future_returns = portfolio_returns.iloc[i:i+self.config.time_horizon_days]
            actual_return = future_returns.sum()
            actual_loss = actual_return * portfolio_value

            # Check if violation occurred (actual loss worse than VaR)
            violation = actual_loss < var_result.var_value

            backtest_results.append({
                'date': portfolio_returns.index[i] if hasattr(portfolio_returns.index, '__getitem__') else i,
                'actual_loss': actual_loss,
                'var_prediction': var_result.var_value,
                'violation': violation
            })

        # Create DataFrame
        backtest_df = pd.DataFrame(backtest_results)

        # Calculate violation rate
        violation_rate = backtest_df['violation'].mean()

        return violation_rate, backtest_df
