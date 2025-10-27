"""
CVaR (Conditional Value at Risk) Calculator

Also known as Expected Shortfall (ES) or Tail VaR, CVaR measures the average
loss in the worst (1 - confidence_level) % of cases. Unlike VaR which only
captures the threshold, CVaR captures the severity of tail losses.

Mathematical Definition:
    CVaR = E[Loss | Loss > VaR]

Key Properties:
- CVaR >= VaR (always more conservative)
- Captures tail risk severity (fat-tail distributions)
- Coherent risk measure (satisfies sub-additivity)
- Preferred by Basel III for regulatory capital

Implements three calculation methods:
1. Historical Simulation: Average of empirical tail losses
2. Parametric (Gaussian): Analytical formula assuming normal distribution
3. Monte Carlo: Average of simulated tail losses

NO database dependencies - pure calculation logic using NumPy/pandas.

Author: Quant Platform Development Team
Version: 1.0.0
Status: Phase 5 - Track 5 Implementation
"""

from modules.risk.risk_base import RiskCalculator, RiskConfig, CVaRResult
from modules.risk.var_calculator import VaRCalculator
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime
from typing import Optional, Tuple


class CVaRCalculator(RiskCalculator):
    """
    Conditional Value at Risk (CVaR) calculator

    CVaR measures the expected loss beyond the VaR threshold, providing
    a more comprehensive view of tail risk than VaR alone.

    Supported Methods:
    - Historical Simulation: Average of empirical tail losses
    - Parametric (Gaussian): Analytical formula for normal distribution
    - Monte Carlo: Average of simulated tail losses

    Example:
        >>> from modules.risk import CVaRCalculator, RiskConfig
        >>> import pandas as pd
        >>> import numpy as np
        >>>
        >>> # Sample portfolio returns
        >>> np.random.seed(42)
        >>> portfolio_returns = pd.Series(np.random.normal(0.001, 0.02, 252))
        >>>
        >>> # Calculate CVaR
        >>> config = RiskConfig(confidence_level=0.95, time_horizon_days=10)
        >>> cvar_calc = CVaRCalculator(config)
        >>> result = cvar_calc.calculate(portfolio_returns, portfolio_value=100_000_000)
        >>>
        >>> print(f"CVaR (95%, 10-day): {result.cvar_value:,.0f} KRW")
        >>> print(f"CVaR as %: {result.cvar_percent:.2%}")
        >>> print(f"VaR threshold: {result.var_threshold:.2%}")
    """

    def __init__(self, config: Optional[RiskConfig] = None):
        """
        Initialize CVaR calculator

        Args:
            config: Risk calculation configuration (uses defaults if None)

        Raises:
            ValueError: If configuration is invalid
        """
        super().__init__(config)
        # Initialize VaR calculator for threshold calculation
        self.var_calculator = VaRCalculator(config)

    def calculate(
        self,
        portfolio_returns: pd.Series,
        portfolio_value: float,
        method: Optional[str] = None
    ) -> CVaRResult:
        """
        Calculate Conditional Value at Risk (Expected Shortfall)

        CVaR represents the average loss in scenarios where losses exceed VaR.

        Args:
            portfolio_returns: Historical portfolio returns (daily)
            portfolio_value: Current portfolio value in currency
            method: CVaR method ('historical', 'parametric', 'monte_carlo')
                   Overrides config if provided

        Returns:
            CVaRResult with CVaR value and metadata

        Raises:
            ValueError: If inputs are invalid

        Example:
            >>> result = cvar_calc.calculate(returns, 100_000_000, method='historical')
            >>> print(result)
            CVaR(95%, 10d): -6,543,210 (-6.54%) [historical, 13 tail obs]

        Note:
            CVaR is always more extreme (more negative) than VaR for the same
            confidence level. This represents the average severity of tail losses.
        """
        # Validate inputs
        self.validate_inputs(returns=portfolio_returns)

        # Use provided method or config default
        calc_method = method or self.config.var_method

        # First calculate VaR threshold
        var_result = self.var_calculator.calculate(
            portfolio_returns,
            portfolio_value,
            calc_method
        )

        # Calculate CVaR based on method
        if calc_method == 'historical':
            cvar_percent = self._historical_cvar(portfolio_returns, var_result.var_percent)
        elif calc_method == 'parametric':
            cvar_percent = self._parametric_cvar(portfolio_returns)
        elif calc_method == 'monte_carlo':
            cvar_percent = self._monte_carlo_cvar(portfolio_returns, var_result.var_percent)
        else:
            raise ValueError(
                f"Invalid CVaR method: {calc_method}. "
                f"Must be 'historical', 'parametric', or 'monte_carlo'"
            )

        # Convert to currency value
        cvar_value = cvar_percent * portfolio_value

        # Count tail observations (losses beyond VaR)
        if calc_method == 'historical':
            # Scale returns to time horizon for accurate tail count
            if self.config.time_horizon_days > 1:
                scaled_returns = self._scale_returns_to_horizon(portfolio_returns)
            else:
                scaled_returns = portfolio_returns

            tail_mask = scaled_returns <= var_result.var_percent
            tail_observations = int(tail_mask.sum())
        else:
            # For parametric and Monte Carlo, estimate expected tail count
            expected_tail_pct = 1 - self.config.confidence_level
            tail_observations = int(len(portfolio_returns) * expected_tail_pct)

        # Create result with metadata
        return CVaRResult(
            cvar_value=cvar_value,
            cvar_percent=cvar_percent,
            var_threshold=var_result.var_percent,
            confidence_level=self.config.confidence_level,
            time_horizon_days=self.config.time_horizon_days,
            method=calc_method,
            tail_observations=tail_observations,
            portfolio_value=portfolio_value,
            calculation_date=datetime.now(),
            metadata={
                'var_value': var_result.var_value,
                'var_percent': var_result.var_percent,
                'tail_pct': tail_observations / len(portfolio_returns),
                'worst_loss': float(portfolio_returns.min()),
                'cvar_var_ratio': abs(cvar_percent / var_result.var_percent) if var_result.var_percent != 0 else 1.0
            }
        )

    def _historical_cvar(self, returns: pd.Series, var_threshold: float) -> float:
        """
        Calculate Historical Simulation CVaR

        Method:
        1. Scale returns to time horizon if needed
        2. Filter returns beyond VaR threshold (tail losses)
        3. CVaR = mean(tail_losses)

        Args:
            returns: Historical returns series
            var_threshold: VaR threshold (percentile value)

        Returns:
            CVaR as percentage of portfolio value (negative)

        Note:
            If no observations fall in the tail (rare for large datasets),
            CVaR defaults to VaR threshold.
        """
        # Scale returns to time horizon if multi-day
        if self.config.time_horizon_days > 1:
            scaled_returns = self._scale_returns_to_horizon(returns)
        else:
            scaled_returns = returns

        # Filter tail losses (returns <= VaR threshold)
        tail_losses = scaled_returns[scaled_returns <= var_threshold]

        if len(tail_losses) == 0:
            # No observations beyond VaR (rare case)
            # Return VaR threshold as conservative estimate
            return var_threshold

        # CVaR is the average of tail losses
        cvar_percent = float(tail_losses.mean())

        return cvar_percent

    def _parametric_cvar(self, returns: pd.Series) -> float:
        """
        Calculate Parametric CVaR (Variance-Covariance method)

        Assumes returns are normally distributed.

        Formula for normal distribution:
            CVaR = μ * T - σ * sqrt(T) * φ(z) / (1 - confidence)

        where:
            μ = mean return
            σ = standard deviation
            T = time horizon (days)
            z = z-score at confidence level
            φ(z) = PDF of standard normal at z

        Args:
            returns: Historical returns series

        Returns:
            CVaR as percentage of portfolio value (negative)

        Note:
            This method is fast but assumes normal distribution.
            May underestimate CVaR for fat-tailed distributions.
        """
        # Calculate parameters from historical data
        mu = returns.mean()
        sigma = returns.std()

        # Z-score for confidence level
        z_score = stats.norm.ppf(1 - self.config.confidence_level)

        # PDF at z-score
        phi_z = stats.norm.pdf(z_score)

        # Scaling factor for time horizon
        scaling_factor = np.sqrt(self.config.time_horizon_days)

        # Parametric CVaR formula
        cvar_percent = (mu * self.config.time_horizon_days -
                       sigma * scaling_factor * phi_z / (1 - self.config.confidence_level))

        return float(cvar_percent)

    def _monte_carlo_cvar(self, returns: pd.Series, var_threshold: float) -> float:
        """
        Calculate Monte Carlo CVaR

        Method:
        1. Generate N simulations using historical mean and volatility
        2. Calculate cumulative returns for each simulation
        3. Filter simulations beyond VaR threshold
        4. CVaR = mean(tail_simulations)

        Args:
            returns: Historical returns series
            var_threshold: VaR threshold from Monte Carlo simulations

        Returns:
            CVaR as percentage of portfolio value (negative)

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

        # Filter tail losses (simulations <= VaR threshold)
        tail_losses = cumulative_returns[cumulative_returns <= var_threshold]

        if len(tail_losses) == 0:
            # No simulations beyond VaR (very rare)
            return var_threshold

        # CVaR is the average of tail simulations
        cvar_percent = float(tail_losses.mean())

        return cvar_percent

    def calculate_cvar_by_confidence(
        self,
        portfolio_returns: pd.Series,
        portfolio_value: float,
        confidence_levels: Optional[list] = None,
        method: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Calculate CVaR at multiple confidence levels

        Useful for understanding tail risk at different probability thresholds.

        Args:
            portfolio_returns: Historical portfolio returns
            portfolio_value: Current portfolio value
            confidence_levels: List of confidence levels (e.g., [0.90, 0.95, 0.99])
            method: CVaR calculation method (uses config if None)

        Returns:
            DataFrame with CVaR at each confidence level

        Example:
            >>> cvars_df = cvar_calc.calculate_cvar_by_confidence(
            ...     returns, 100_000_000,
            ...     confidence_levels=[0.90, 0.95, 0.99]
            ... )
            >>> print(cvars_df)
            #   confidence_level  cvar_value  var_value  cvar_percent
            # 0             0.90 -4,200,000 -3,500,000       -4.20%
            # 1             0.95 -6,500,000 -5,200,000       -6.50%
            # 2             0.99 -9,800,000 -8,100,000       -9.80%
        """
        if confidence_levels is None:
            confidence_levels = [0.90, 0.95, 0.99]

        results = []
        original_confidence = self.config.confidence_level

        for conf_level in confidence_levels:
            # Temporarily update confidence level
            self.config.confidence_level = conf_level

            # Calculate CVaR
            result = self.calculate(portfolio_returns, portfolio_value, method)

            results.append({
                'confidence_level': conf_level,
                'cvar_value': result.cvar_value,
                'cvar_percent': result.cvar_percent,
                'var_value': result.metadata['var_value'],
                'var_percent': result.metadata['var_percent']
            })

        # Restore original confidence level
        self.config.confidence_level = original_confidence

        return pd.DataFrame(results)

    def calculate_cvar_by_horizon(
        self,
        portfolio_returns: pd.Series,
        portfolio_value: float,
        horizons: Optional[list] = None,
        method: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Calculate CVaR at multiple time horizons

        Shows how CVaR increases with longer holding periods.

        Args:
            portfolio_returns: Historical portfolio returns
            portfolio_value: Current portfolio value
            horizons: List of time horizons in days (e.g., [1, 10, 20])
            method: CVaR calculation method (uses config if None)

        Returns:
            DataFrame with CVaR at each horizon

        Example:
            >>> cvars_df = cvar_calc.calculate_cvar_by_horizon(
            ...     returns, 100_000_000,
            ...     horizons=[1, 10, 20]
            ... )
            >>> print(cvars_df)
            #   horizon_days  cvar_value  var_value  cvar_percent
            # 0            1 -2,100,000 -1,800,000       -2.10%
            # 1           10 -6,500,000 -5,200,000       -6.50%
            # 2           20 -9,200,000 -7,500,000       -9.20%
        """
        if horizons is None:
            horizons = [1, 10, 20]

        results = []
        original_horizon = self.config.time_horizon_days

        for horizon in horizons:
            # Temporarily update time horizon
            self.config.time_horizon_days = horizon

            # Calculate CVaR
            result = self.calculate(portfolio_returns, portfolio_value, method)

            results.append({
                'horizon_days': horizon,
                'cvar_value': result.cvar_value,
                'cvar_percent': result.cvar_percent,
                'var_value': result.metadata['var_value'],
                'var_percent': result.metadata['var_percent']
            })

        # Restore original horizon
        self.config.time_horizon_days = original_horizon

        return pd.DataFrame(results)

    def compare_with_var(
        self,
        portfolio_returns: pd.Series,
        portfolio_value: float,
        method: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Compare CVaR with VaR side-by-side

        Useful for understanding the difference between threshold (VaR)
        and average tail loss (CVaR).

        Args:
            portfolio_returns: Historical portfolio returns
            portfolio_value: Current portfolio value
            method: Calculation method (uses config if None)

        Returns:
            DataFrame with VaR and CVaR comparison

        Example:
            >>> comparison = cvar_calc.compare_with_var(returns, 100_000_000)
            >>> print(comparison)
            #   metric       value     percent  observations
            # 0 VaR   -5,200,000     -5.20%          13
            # 1 CVaR  -6,500,000     -6.50%          13
            # 2 Diff  -1,300,000     -1.30%          --

        Note:
            CVaR is always >= VaR in absolute value.
            The difference shows the severity of tail losses beyond VaR.
        """
        # Calculate CVaR (includes VaR calculation internally)
        cvar_result = self.calculate(portfolio_returns, portfolio_value, method)

        comparison_data = [
            {
                'metric': 'VaR',
                'value': cvar_result.metadata['var_value'],
                'percent': cvar_result.metadata['var_percent'],
                'observations': f"{cvar_result.tail_observations} (tail)"
            },
            {
                'metric': 'CVaR',
                'value': cvar_result.cvar_value,
                'percent': cvar_result.cvar_percent,
                'observations': f"{cvar_result.tail_observations} (tail)"
            },
            {
                'metric': 'Difference',
                'value': cvar_result.cvar_value - cvar_result.metadata['var_value'],
                'percent': cvar_result.cvar_percent - cvar_result.metadata['var_percent'],
                'observations': 'CVaR - VaR'
            }
        ]

        return pd.DataFrame(comparison_data)
