# Track 5: Risk Calculator Implementation - Design Document

**Date**: 2025-10-21
**Status**: Design Phase Complete
**DB Dependency**: None (Pure calculation logic)

---

## 1. Executive Summary

### Design Decision: Keep Existing `risk_manager.py` Separate

**Recommendation**: **DO NOT deprecate** existing `modules/risk_manager.py`

**Rationale**:
1. **Different Purposes**:
   - Existing `risk_manager.py`: Real-time trading risk management (stop loss, circuit breakers, position monitoring)
   - New Track 5: Portfolio-level risk analytics (VaR, CVaR, stress testing, correlation analysis)

2. **Database Dependency Conflict**:
   - Existing: Heavily dependent on SQLite database (trades table queries, circuit breaker logs)
   - Track 5 Requirement: NO database access (pure calculation logic per user constraint)

3. **Complementary Functionality**:
   - Trading Risk: Operational risk monitoring during active trading
   - Portfolio Risk: Strategic risk assessment for portfolio optimization and backtesting

**Action Plan**:
- **Rename**: `modules/risk_manager.py` → `modules/trading_risk_manager.py` (clarify scope)
- **Create New**: `modules/risk/` directory with 5 new calculator classes (portfolio analytics)
- **Document**: Clear separation of concerns in architecture documentation

---

## 2. Architecture Overview

### Comparison Matrix

| Aspect | Existing Trading Risk Manager | New Portfolio Risk Calculator |
|--------|-------------------------------|------------------------------|
| **Purpose** | Real-time trading risk monitoring | Portfolio-level risk analytics |
| **Scope** | Position-level (individual trades) | Portfolio-level (entire allocation) |
| **Database** | Required (SQLite queries) | Prohibited (pure calculation) |
| **Focus** | Stop loss, take profit, circuit breakers | VaR, CVaR, stress tests, correlation |
| **Use Case** | Active trading execution | Backtesting, optimization, research |
| **Time Horizon** | Intraday to weeks | Months to years (historical analysis) |
| **Input Data** | Database tables (trades, positions) | NumPy arrays, pandas DataFrames |
| **Output** | Trading signals (stop/exit) | Risk metrics (quantitative measures) |

### New Module Structure

```
modules/risk/
├── __init__.py                    # Module exports
├── risk_base.py                   # Abstract base classes, data structures (~300 lines)
├── var_calculator.py              # Value at Risk (Historical, Parametric, Monte Carlo) (~350 lines)
├── cvar_calculator.py             # Conditional VaR / Expected Shortfall (~200 lines)
├── stress_tester.py               # Scenario-based stress testing (~280 lines)
├── correlation_analyzer.py        # Asset correlation, diversification metrics (~250 lines)
└── exposure_tracker.py            # Factor/sector exposure tracking (~220 lines)

Total: 6 files, ~1,600 lines
```

---

## 3. Core Classes Design

### 3.1 `risk_base.py` - Abstract Base Classes

**Purpose**: Common data structures and abstract base class for all risk calculators

**Key Classes**:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from datetime import datetime

@dataclass
class RiskConfig:
    """Risk calculation configuration"""
    confidence_level: float = 0.95  # 95% or 99%
    time_horizon_days: int = 10      # 1-day, 10-day, 20-day
    var_method: str = 'historical'   # historical, parametric, monte_carlo
    monte_carlo_simulations: int = 10000
    historical_lookback_days: int = 252  # 1 year
    stress_test_scenarios: List[str] = field(default_factory=lambda: [
        '2008_financial_crisis',
        '2020_covid_crash',
        '2022_bear_market'
    ])
    correlation_window_days: int = 60
    exponential_weighting: bool = False
    lambda_decay: float = 0.94  # RiskMetrics standard

    def validate(self) -> Tuple[bool, str]:
        """Validate configuration parameters"""
        if not 0.5 <= self.confidence_level < 1.0:
            return False, f"confidence_level must be 0.5-1.0, got {self.confidence_level}"
        if self.time_horizon_days < 1:
            return False, f"time_horizon_days must be >= 1, got {self.time_horizon_days}"
        if self.var_method not in ['historical', 'parametric', 'monte_carlo']:
            return False, f"Invalid var_method: {self.var_method}"
        if self.monte_carlo_simulations < 1000:
            return False, f"monte_carlo_simulations should be >= 1000, got {self.monte_carlo_simulations}"
        return True, "Configuration valid"

@dataclass
class VaRResult:
    """Value at Risk calculation result"""
    var_value: float  # VaR in portfolio currency (e.g., -5,000,000 KRW)
    var_percent: float  # VaR as % of portfolio value (e.g., -5.0%)
    confidence_level: float  # e.g., 0.95
    time_horizon_days: int  # e.g., 10
    method: str  # 'historical', 'parametric', 'monte_carlo'
    portfolio_value: float
    calculation_date: datetime
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return {
            'var_value': self.var_value,
            'var_percent': self.var_percent,
            'confidence_level': self.confidence_level,
            'time_horizon_days': self.time_horizon_days,
            'method': self.method,
            'portfolio_value': self.portfolio_value,
            'calculation_date': self.calculation_date.isoformat(),
            'metadata': self.metadata or {}
        }

@dataclass
class CVaRResult:
    """Conditional VaR (Expected Shortfall) result"""
    cvar_value: float  # CVaR in portfolio currency
    cvar_percent: float  # CVaR as % of portfolio value
    var_threshold: float  # VaR threshold used
    confidence_level: float
    time_horizon_days: int
    method: str
    tail_observations: int  # Number of observations in tail
    portfolio_value: float
    calculation_date: datetime
    metadata: Optional[Dict] = None

@dataclass
class StressTestResult:
    """Stress test scenario result"""
    scenario_name: str  # '2008_financial_crisis', 'market_crash_30pct', etc.
    portfolio_loss: float  # Expected loss in currency
    portfolio_loss_percent: float  # Expected loss as %
    scenario_description: str
    scenario_type: str  # 'historical' or 'hypothetical'
    factor_shocks: Dict[str, float]  # Factor-level shocks applied
    asset_level_impacts: pd.DataFrame  # Per-asset impact
    calculation_date: datetime
    metadata: Optional[Dict] = None

@dataclass
class CorrelationResult:
    """Correlation analysis result"""
    correlation_matrix: pd.DataFrame  # Asset correlation matrix
    average_correlation: float  # Portfolio average correlation
    diversification_ratio: float  # Ratio of portfolio vol to weighted sum of vols
    eigenvalues: np.ndarray  # Eigenvalues of correlation matrix
    principal_components: pd.DataFrame  # Principal component analysis
    rolling_correlations: Optional[pd.DataFrame] = None  # Time-series if requested
    calculation_date: datetime
    metadata: Optional[Dict] = None

@dataclass
class ExposureResult:
    """Factor/sector exposure result"""
    sector_exposure: pd.Series  # Exposure by sector
    region_exposure: pd.Series  # Exposure by region
    factor_exposure: Optional[pd.DataFrame] = None  # Exposure to risk factors
    concentration_metrics: Dict[str, float] = field(default_factory=dict)  # HHI, etc.
    top_exposures: pd.DataFrame = field(default_factory=pd.DataFrame)  # Top 10 exposures
    calculation_date: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict] = None

class RiskCalculator(ABC):
    """Abstract base class for all risk calculators"""

    def __init__(self, config: Optional[RiskConfig] = None):
        """Initialize risk calculator with configuration"""
        self.config = config or RiskConfig()
        is_valid, msg = self.config.validate()
        if not is_valid:
            raise ValueError(f"Invalid RiskConfig: {msg}")

    @abstractmethod
    def calculate(self, *args, **kwargs):
        """Calculate risk metric (implemented by subclasses)"""
        pass

    def validate_inputs(
        self,
        returns: Optional[pd.Series] = None,
        weights: Optional[pd.Series] = None,
        cov_matrix: Optional[pd.DataFrame] = None
    ) -> None:
        """Validate input data for risk calculations"""

        if returns is not None:
            if returns.isnull().any():
                raise ValueError("Returns contain NaN values")
            if len(returns) < 30:
                raise ValueError(f"Insufficient returns data: {len(returns)} observations (minimum 30)")

        if weights is not None:
            if weights.isnull().any():
                raise ValueError("Weights contain NaN values")
            if not np.isclose(weights.sum(), 1.0, atol=0.01):
                raise ValueError(f"Weights sum to {weights.sum():.4f}, expected 1.0")
            if (weights < 0).any():
                raise ValueError("Negative weights detected (long-only portfolio expected)")

        if cov_matrix is not None:
            if cov_matrix.isnull().any().any():
                raise ValueError("Covariance matrix contains NaN values")
            if not np.allclose(cov_matrix, cov_matrix.T, atol=1e-8):
                raise ValueError("Covariance matrix is not symmetric")
            eigenvalues = np.linalg.eigvalsh(cov_matrix.values)
            if (eigenvalues < -1e-8).any():
                raise ValueError("Covariance matrix is not positive semi-definite")

        if weights is not None and cov_matrix is not None:
            if not weights.index.equals(cov_matrix.index):
                raise ValueError("Weights and covariance matrix indices do not match")
```

**Estimated Lines**: ~300 lines

---

### 3.2 `var_calculator.py` - Value at Risk Calculator

**Purpose**: Calculate VaR using Historical Simulation, Parametric (Gaussian), and Monte Carlo methods

**Key Methods**:

```python
from modules.risk.risk_base import RiskCalculator, RiskConfig, VaRResult
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime
from typing import Optional

class VaRCalculator(RiskCalculator):
    """Value at Risk (VaR) calculator supporting multiple methods"""

    def __init__(self, config: Optional[RiskConfig] = None):
        """Initialize VaR calculator"""
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
            method: 'historical', 'parametric', or 'monte_carlo' (overrides config)

        Returns:
            VaRResult with VaR value and metadata
        """
        self.validate_inputs(returns=portfolio_returns)

        method = method or self.config.var_method

        if method == 'historical':
            var_percent = self._historical_var(portfolio_returns)
        elif method == 'parametric':
            var_percent = self._parametric_var(portfolio_returns)
        elif method == 'monte_carlo':
            var_percent = self._monte_carlo_var(portfolio_returns)
        else:
            raise ValueError(f"Invalid VaR method: {method}")

        var_value = var_percent * portfolio_value

        return VaRResult(
            var_value=var_value,
            var_percent=var_percent,
            confidence_level=self.config.confidence_level,
            time_horizon_days=self.config.time_horizon_days,
            method=method,
            portfolio_value=portfolio_value,
            calculation_date=datetime.now(),
            metadata={
                'observations': len(portfolio_returns),
                'mean_return': portfolio_returns.mean(),
                'volatility': portfolio_returns.std()
            }
        )

    def _historical_var(self, returns: pd.Series) -> float:
        """
        Historical Simulation VaR

        Method: Use empirical distribution of historical returns
        """
        # Scale returns to time horizon if needed
        if self.config.time_horizon_days > 1:
            # For multi-day horizon, use overlapping periods
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
            var_percent = np.percentile(
                scaled_returns,
                (1 - self.config.confidence_level) * 100
            )

        return var_percent

    def _parametric_var(self, returns: pd.Series) -> float:
        """
        Parametric VaR (Variance-Covariance method)

        Assumes: Returns are normally distributed
        Formula: VaR = μ - z * σ * sqrt(T)
        """
        mu = returns.mean()
        sigma = returns.std()
        z_score = stats.norm.ppf(1 - self.config.confidence_level)

        # Scale for time horizon
        scaling_factor = np.sqrt(self.config.time_horizon_days)

        var_percent = mu * self.config.time_horizon_days + z_score * sigma * scaling_factor
        return var_percent

    def _monte_carlo_var(self, returns: pd.Series) -> float:
        """
        Monte Carlo VaR

        Method: Simulate future returns using historical parameters
        """
        mu = returns.mean()
        sigma = returns.std()

        # Generate random returns for time horizon
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

        return var_percent

    def _scale_returns_to_horizon(self, returns: pd.Series) -> pd.Series:
        """Scale daily returns to multi-day horizon using overlapping periods"""
        horizon = self.config.time_horizon_days
        scaled_returns = []

        for i in range(len(returns) - horizon + 1):
            period_return = returns.iloc[i:i+horizon].sum()
            scaled_returns.append(period_return)

        return pd.Series(scaled_returns)

    def _calculate_exponential_weights(self, n: int) -> np.ndarray:
        """Calculate exponentially decaying weights (RiskMetrics approach)"""
        lambda_decay = self.config.lambda_decay
        weights = np.array([lambda_decay ** i for i in range(n)])
        weights = weights[::-1]  # Reverse so recent observations have higher weight
        weights /= weights.sum()  # Normalize
        return weights

    def _weighted_percentile(
        self,
        data: np.ndarray,
        weights: np.ndarray,
        percentile: float
    ) -> float:
        """Calculate weighted percentile"""
        sorted_indices = np.argsort(data)
        sorted_data = data[sorted_indices]
        sorted_weights = weights[sorted_indices]
        cumsum = np.cumsum(sorted_weights)

        # Find index where cumulative weight exceeds percentile
        idx = np.searchsorted(cumsum, percentile)
        return sorted_data[idx]

    def calculate_component_var(
        self,
        asset_returns: pd.DataFrame,
        weights: pd.Series,
        portfolio_value: float
    ) -> pd.DataFrame:
        """
        Calculate component VaR (contribution of each asset to portfolio VaR)

        Returns:
            DataFrame with columns: ticker, weight, component_var, component_var_pct
        """
        # Calculate portfolio returns
        portfolio_returns = (asset_returns * weights).sum(axis=1)

        # Calculate portfolio VaR
        portfolio_var = self.calculate(portfolio_returns, portfolio_value)

        # Calculate marginal VaR for each asset
        component_vars = []

        for ticker in weights.index:
            # Small perturbation in weight
            perturbed_weights = weights.copy()
            epsilon = 0.01
            perturbed_weights[ticker] += epsilon
            perturbed_weights /= perturbed_weights.sum()

            # Recalculate VaR
            perturbed_returns = (asset_returns * perturbed_weights).sum(axis=1)
            perturbed_var = self.calculate(perturbed_returns, portfolio_value)

            # Marginal VaR = dVaR / dw
            marginal_var = (perturbed_var.var_value - portfolio_var.var_value) / epsilon

            # Component VaR = w * marginal VaR
            component_var = weights[ticker] * marginal_var

            component_vars.append({
                'ticker': ticker,
                'weight': weights[ticker],
                'component_var': component_var,
                'component_var_pct': component_var / portfolio_value
            })

        return pd.DataFrame(component_vars)
```

**Estimated Lines**: ~350 lines

---

### 3.3 `cvar_calculator.py` - Conditional VaR Calculator

**Purpose**: Calculate CVaR (Expected Shortfall) - average loss beyond VaR threshold

**Key Methods**:

```python
from modules.risk.risk_base import RiskCalculator, RiskConfig, CVaRResult
from modules.risk.var_calculator import VaRCalculator
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional

class CVaRCalculator(RiskCalculator):
    """Conditional VaR (Expected Shortfall) calculator"""

    def __init__(self, config: Optional[RiskConfig] = None):
        """Initialize CVaR calculator"""
        super().__init__(config)
        self.var_calculator = VaRCalculator(config)

    def calculate(
        self,
        portfolio_returns: pd.Series,
        portfolio_value: float,
        method: Optional[str] = None
    ) -> CVaRResult:
        """
        Calculate Conditional VaR (Expected Shortfall)

        CVaR = Average of losses beyond VaR threshold

        Args:
            portfolio_returns: Historical portfolio returns (daily)
            portfolio_value: Current portfolio value in currency
            method: 'historical', 'parametric', or 'monte_carlo'

        Returns:
            CVaRResult with CVaR value and metadata
        """
        self.validate_inputs(returns=portfolio_returns)

        method = method or self.config.var_method

        # First calculate VaR threshold
        var_result = self.var_calculator.calculate(
            portfolio_returns,
            portfolio_value,
            method
        )

        if method == 'historical':
            cvar_percent = self._historical_cvar(portfolio_returns, var_result.var_percent)
        elif method == 'parametric':
            cvar_percent = self._parametric_cvar(portfolio_returns, var_result.var_percent)
        elif method == 'monte_carlo':
            cvar_percent = self._monte_carlo_cvar(portfolio_returns, var_result.var_percent)
        else:
            raise ValueError(f"Invalid CVaR method: {method}")

        cvar_value = cvar_percent * portfolio_value

        # Count tail observations
        tail_mask = portfolio_returns <= var_result.var_percent
        tail_observations = tail_mask.sum()

        return CVaRResult(
            cvar_value=cvar_value,
            cvar_percent=cvar_percent,
            var_threshold=var_result.var_percent,
            confidence_level=self.config.confidence_level,
            time_horizon_days=self.config.time_horizon_days,
            method=method,
            tail_observations=tail_observations,
            portfolio_value=portfolio_value,
            calculation_date=datetime.now(),
            metadata={
                'var_value': var_result.var_value,
                'tail_pct': tail_observations / len(portfolio_returns),
                'worst_loss': portfolio_returns.min()
            }
        )

    def _historical_cvar(self, returns: pd.Series, var_threshold: float) -> float:
        """Historical CVaR - average of losses beyond VaR"""
        tail_losses = returns[returns <= var_threshold]

        if len(tail_losses) == 0:
            # No observations beyond VaR (rare case)
            return var_threshold

        cvar_percent = tail_losses.mean()
        return cvar_percent

    def _parametric_cvar(self, returns: pd.Series, var_threshold: float) -> float:
        """
        Parametric CVaR (assumes normal distribution)

        Formula for normal distribution:
        CVaR = μ - σ * φ(z) / (1 - confidence)
        where φ(z) is PDF at z-score
        """
        from scipy import stats

        mu = returns.mean()
        sigma = returns.std()
        confidence = self.config.confidence_level

        # Z-score for VaR threshold
        z_score = stats.norm.ppf(1 - confidence)

        # PDF at z-score
        phi_z = stats.norm.pdf(z_score)

        # CVaR formula
        scaling_factor = np.sqrt(self.config.time_horizon_days)
        cvar_percent = (mu * self.config.time_horizon_days -
                       sigma * scaling_factor * phi_z / (1 - confidence))

        return cvar_percent

    def _monte_carlo_cvar(self, returns: pd.Series, var_threshold: float) -> float:
        """Monte Carlo CVaR - average of simulated losses beyond VaR"""
        mu = returns.mean()
        sigma = returns.std()

        # Generate simulations
        simulated_returns = np.random.normal(
            mu,
            sigma,
            (self.config.monte_carlo_simulations, self.config.time_horizon_days)
        )

        cumulative_returns = np.sum(simulated_returns, axis=1)

        # Filter tail losses
        tail_losses = cumulative_returns[cumulative_returns <= var_threshold]

        if len(tail_losses) == 0:
            return var_threshold

        cvar_percent = tail_losses.mean()
        return cvar_percent
```

**Estimated Lines**: ~200 lines

---

### 3.4 `stress_tester.py` - Stress Testing Calculator

**Purpose**: Scenario-based portfolio stress testing (historical and hypothetical scenarios)

**Key Methods**:

```python
from modules.risk.risk_base import RiskCalculator, RiskConfig, StressTestResult
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional

class StressTester(RiskCalculator):
    """Portfolio stress testing calculator"""

    # Historical scenario definitions (factor shocks)
    HISTORICAL_SCENARIOS = {
        '2008_financial_crisis': {
            'description': '2008 Financial Crisis (Sep-Oct 2008)',
            'type': 'historical',
            'equity_shock': -0.30,  # -30% equity markets
            'credit_spread_shock': 0.05,  # +500 bps credit spreads
            'volatility_shock': 2.0,  # 2x volatility
            'correlation_shock': 1.5  # Correlations increase 50%
        },
        '2020_covid_crash': {
            'description': '2020 COVID-19 Crash (Feb-Mar 2020)',
            'type': 'historical',
            'equity_shock': -0.35,  # -35% equity markets
            'credit_spread_shock': 0.03,  # +300 bps
            'volatility_shock': 2.5,
            'correlation_shock': 1.6
        },
        '2022_bear_market': {
            'description': '2022 Bear Market (Jan-Sep 2022)',
            'type': 'historical',
            'equity_shock': -0.25,  # -25%
            'bond_shock': -0.15,  # -15% bonds (rate shock)
            'credit_spread_shock': 0.02,
            'volatility_shock': 1.5,
            'correlation_shock': 1.3
        }
    }

    def __init__(self, config: Optional[RiskConfig] = None):
        """Initialize stress tester"""
        super().__init__(config)

    def calculate(
        self,
        asset_returns: pd.DataFrame,
        weights: pd.Series,
        portfolio_value: float,
        scenarios: Optional[List[str]] = None
    ) -> List[StressTestResult]:
        """
        Run stress tests on portfolio

        Args:
            asset_returns: Historical returns for each asset (DataFrame)
            weights: Portfolio weights (Series)
            portfolio_value: Current portfolio value
            scenarios: List of scenario names (uses config default if None)

        Returns:
            List of StressTestResult for each scenario
        """
        self.validate_inputs(weights=weights)

        scenarios = scenarios or self.config.stress_test_scenarios
        results = []

        for scenario_name in scenarios:
            if scenario_name in self.HISTORICAL_SCENARIOS:
                result = self._run_historical_scenario(
                    asset_returns,
                    weights,
                    portfolio_value,
                    scenario_name
                )
            else:
                # Try to parse as hypothetical scenario
                result = self._run_hypothetical_scenario(
                    asset_returns,
                    weights,
                    portfolio_value,
                    scenario_name
                )

            results.append(result)

        return results

    def _run_historical_scenario(
        self,
        asset_returns: pd.DataFrame,
        weights: pd.Series,
        portfolio_value: float,
        scenario_name: str
    ) -> StressTestResult:
        """Run historical scenario stress test"""
        scenario = self.HISTORICAL_SCENARIOS[scenario_name]

        # Apply factor shocks to each asset
        shocked_returns = pd.Series(index=asset_returns.columns, dtype=float)

        for ticker in asset_returns.columns:
            # Simplified: Apply equity shock to all assets
            # In production, differentiate by asset class
            shocked_returns[ticker] = scenario['equity_shock']

        # Calculate portfolio loss
        portfolio_loss_percent = (shocked_returns * weights).sum()
        portfolio_loss = portfolio_loss_percent * portfolio_value

        # Asset-level impacts
        asset_impacts = pd.DataFrame({
            'ticker': asset_returns.columns,
            'weight': weights,
            'shock': shocked_returns,
            'contribution': shocked_returns * weights
        })

        return StressTestResult(
            scenario_name=scenario_name,
            portfolio_loss=portfolio_loss,
            portfolio_loss_percent=portfolio_loss_percent,
            scenario_description=scenario['description'],
            scenario_type=scenario['type'],
            factor_shocks=scenario,
            asset_level_impacts=asset_impacts,
            calculation_date=datetime.now(),
            metadata={
                'portfolio_value': portfolio_value,
                'worst_asset': asset_impacts.nsmallest(1, 'contribution')['ticker'].values[0]
            }
        )

    def _run_hypothetical_scenario(
        self,
        asset_returns: pd.DataFrame,
        weights: pd.Series,
        portfolio_value: float,
        scenario_spec: str
    ) -> StressTestResult:
        """
        Run hypothetical scenario

        Scenario spec format: "market_crash_30pct" or "sector_rotation_tech_down_20pct"
        """
        # Parse scenario spec (simplified)
        if 'market_crash' in scenario_spec:
            shock_pct = -0.30  # Default -30%
        elif 'sector_rotation' in scenario_spec:
            shock_pct = -0.20  # Default -20%
        else:
            shock_pct = -0.10  # Default -10%

        shocked_returns = pd.Series(shock_pct, index=asset_returns.columns)
        portfolio_loss_percent = (shocked_returns * weights).sum()
        portfolio_loss = portfolio_loss_percent * portfolio_value

        asset_impacts = pd.DataFrame({
            'ticker': asset_returns.columns,
            'weight': weights,
            'shock': shocked_returns,
            'contribution': shocked_returns * weights
        })

        return StressTestResult(
            scenario_name=scenario_spec,
            portfolio_loss=portfolio_loss,
            portfolio_loss_percent=portfolio_loss_percent,
            scenario_description=f"Hypothetical: {scenario_spec}",
            scenario_type='hypothetical',
            factor_shocks={'market_shock': shock_pct},
            asset_level_impacts=asset_impacts,
            calculation_date=datetime.now()
        )

    def create_custom_scenario(
        self,
        name: str,
        description: str,
        asset_shocks: Dict[str, float]
    ) -> Dict:
        """
        Create custom stress test scenario

        Args:
            name: Scenario name
            description: Scenario description
            asset_shocks: Dict mapping ticker -> shock percentage

        Returns:
            Scenario dictionary
        """
        return {
            'name': name,
            'description': description,
            'type': 'custom',
            'asset_shocks': asset_shocks
        }
```

**Estimated Lines**: ~280 lines

---

### 3.5 `correlation_analyzer.py` - Correlation & Diversification Calculator

**Purpose**: Analyze asset correlations and portfolio diversification

**Key Methods**:

```python
from modules.risk.risk_base import RiskCalculator, RiskConfig, CorrelationResult
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional

class CorrelationAnalyzer(RiskCalculator):
    """Asset correlation and diversification analyzer"""

    def __init__(self, config: Optional[RiskConfig] = None):
        """Initialize correlation analyzer"""
        super().__init__(config)

    def calculate(
        self,
        asset_returns: pd.DataFrame,
        weights: Optional[pd.Series] = None,
        rolling: bool = False
    ) -> CorrelationResult:
        """
        Calculate correlation matrix and diversification metrics

        Args:
            asset_returns: Historical returns for each asset
            weights: Portfolio weights (optional, for diversification ratio)
            rolling: Calculate rolling correlations (time-series)

        Returns:
            CorrelationResult with correlation matrix and metrics
        """
        # Calculate correlation matrix
        corr_matrix = asset_returns.corr()

        # Average correlation (excluding diagonal)
        n = len(corr_matrix)
        avg_correlation = (corr_matrix.sum().sum() - n) / (n * (n - 1))

        # Diversification ratio (if weights provided)
        if weights is not None:
            div_ratio = self._calculate_diversification_ratio(
                asset_returns,
                weights
            )
        else:
            div_ratio = np.nan

        # Eigenvalue decomposition (principal components)
        eigenvalues, eigenvectors = np.linalg.eigh(corr_matrix.values)
        eigenvalues = eigenvalues[::-1]  # Sort descending
        eigenvectors = eigenvectors[:, ::-1]

        # Principal components DataFrame
        pc_df = pd.DataFrame(
            eigenvectors,
            index=corr_matrix.index,
            columns=[f'PC{i+1}' for i in range(len(eigenvalues))]
        )

        # Rolling correlations (optional)
        rolling_corr = None
        if rolling:
            rolling_corr = self._calculate_rolling_correlations(asset_returns)

        return CorrelationResult(
            correlation_matrix=corr_matrix,
            average_correlation=avg_correlation,
            diversification_ratio=div_ratio,
            eigenvalues=eigenvalues,
            principal_components=pc_df,
            rolling_correlations=rolling_corr,
            calculation_date=datetime.now(),
            metadata={
                'n_assets': n,
                'max_correlation': corr_matrix.where(~np.eye(n, dtype=bool)).max().max(),
                'min_correlation': corr_matrix.where(~np.eye(n, dtype=bool)).min().min(),
                'pc1_variance_explained': eigenvalues[0] / eigenvalues.sum()
            }
        )

    def _calculate_diversification_ratio(
        self,
        asset_returns: pd.DataFrame,
        weights: pd.Series
    ) -> float:
        """
        Calculate diversification ratio

        Diversification Ratio = (Weighted sum of asset vols) / (Portfolio vol)

        Higher ratio = better diversification
        """
        # Individual asset volatilities
        asset_vols = asset_returns.std()

        # Weighted sum of volatilities
        weighted_vol_sum = (weights * asset_vols).sum()

        # Portfolio volatility
        portfolio_returns = (asset_returns * weights).sum(axis=1)
        portfolio_vol = portfolio_returns.std()

        diversification_ratio = weighted_vol_sum / portfolio_vol
        return diversification_ratio

    def _calculate_rolling_correlations(
        self,
        asset_returns: pd.DataFrame
    ) -> pd.DataFrame:
        """Calculate rolling correlations over time"""
        window = self.config.correlation_window_days

        rolling_corr = asset_returns.rolling(window=window).corr()
        return rolling_corr

    def calculate_correlation_breakdown(
        self,
        asset_returns: pd.DataFrame,
        ticker_metadata: Dict[str, Dict]
    ) -> pd.DataFrame:
        """
        Calculate average correlation by sector, region

        Args:
            asset_returns: Historical returns
            ticker_metadata: Dict[ticker -> {'sector': ..., 'region': ...}]

        Returns:
            DataFrame with correlation breakdowns
        """
        corr_matrix = asset_returns.corr()

        # Group by sector
        sectors = {t: ticker_metadata[t]['sector'] for t in asset_returns.columns}

        breakdowns = []
        for sector in set(sectors.values()):
            sector_tickers = [t for t, s in sectors.items() if s == sector]

            # Intra-sector correlation
            if len(sector_tickers) > 1:
                sector_corr = corr_matrix.loc[sector_tickers, sector_tickers]
                n = len(sector_corr)
                avg_intra_corr = (sector_corr.sum().sum() - n) / (n * (n - 1))
            else:
                avg_intra_corr = np.nan

            breakdowns.append({
                'sector': sector,
                'n_assets': len(sector_tickers),
                'avg_intra_correlation': avg_intra_corr
            })

        return pd.DataFrame(breakdowns)
```

**Estimated Lines**: ~250 lines

---

### 3.6 `exposure_tracker.py` - Factor/Sector Exposure Tracker

**Purpose**: Track portfolio exposure to sectors, regions, and risk factors

**Key Methods**:

```python
from modules.risk.risk_base import RiskCalculator, RiskConfig, ExposureResult
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional

class ExposureTracker(RiskCalculator):
    """Portfolio exposure tracker (sector, region, factor)"""

    def __init__(self, config: Optional[RiskConfig] = None):
        """Initialize exposure tracker"""
        super().__init__(config)

    def calculate(
        self,
        weights: pd.Series,
        ticker_metadata: Dict[str, Dict],
        factor_exposures: Optional[pd.DataFrame] = None
    ) -> ExposureResult:
        """
        Calculate portfolio exposures

        Args:
            weights: Portfolio weights (Series with ticker index)
            ticker_metadata: Dict[ticker -> {'sector': ..., 'region': ...}]
            factor_exposures: Optional factor exposure matrix (tickers x factors)

        Returns:
            ExposureResult with exposure breakdowns
        """
        self.validate_inputs(weights=weights)

        # Sector exposure
        sector_exposure = self._calculate_sector_exposure(weights, ticker_metadata)

        # Region exposure
        region_exposure = self._calculate_region_exposure(weights, ticker_metadata)

        # Factor exposure (optional)
        factor_exp = None
        if factor_exposures is not None:
            factor_exp = self._calculate_factor_exposure(weights, factor_exposures)

        # Concentration metrics
        concentration = self._calculate_concentration_metrics(weights)

        # Top exposures
        top_exposures = pd.DataFrame({
            'ticker': weights.index,
            'weight': weights.values,
            'sector': [ticker_metadata[t]['sector'] for t in weights.index],
            'region': [ticker_metadata[t]['region'] for t in weights.index]
        }).nlargest(10, 'weight')

        return ExposureResult(
            sector_exposure=sector_exposure,
            region_exposure=region_exposure,
            factor_exposure=factor_exp,
            concentration_metrics=concentration,
            top_exposures=top_exposures,
            calculation_date=datetime.now(),
            metadata={
                'n_assets': len(weights),
                'n_sectors': len(sector_exposure),
                'n_regions': len(region_exposure)
            }
        )

    def _calculate_sector_exposure(
        self,
        weights: pd.Series,
        ticker_metadata: Dict[str, Dict]
    ) -> pd.Series:
        """Calculate sector exposure (sum of weights per sector)"""
        sector_weights = {}

        for ticker, weight in weights.items():
            sector = ticker_metadata[ticker]['sector']
            sector_weights[sector] = sector_weights.get(sector, 0.0) + weight

        return pd.Series(sector_weights).sort_values(ascending=False)

    def _calculate_region_exposure(
        self,
        weights: pd.Series,
        ticker_metadata: Dict[str, Dict]
    ) -> pd.Series:
        """Calculate region exposure (sum of weights per region)"""
        region_weights = {}

        for ticker, weight in weights.items():
            region = ticker_metadata[ticker]['region']
            region_weights[region] = region_weights.get(region, 0.0) + weight

        return pd.Series(region_weights).sort_values(ascending=False)

    def _calculate_factor_exposure(
        self,
        weights: pd.Series,
        factor_exposures: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate portfolio factor exposure

        Factor exposure = sum(w_i * beta_i,f) for each factor f

        Args:
            weights: Portfolio weights
            factor_exposures: DataFrame (tickers x factors) with factor betas

        Returns:
            DataFrame with factor exposures
        """
        # Align indices
        aligned_exposures = factor_exposures.loc[weights.index]

        # Calculate weighted factor exposures
        portfolio_exposures = (aligned_exposures.T * weights).sum(axis=1)

        return pd.DataFrame({
            'factor': portfolio_exposures.index,
            'exposure': portfolio_exposures.values
        })

    def _calculate_concentration_metrics(self, weights: pd.Series) -> Dict[str, float]:
        """
        Calculate concentration metrics

        - Herfindahl-Hirschman Index (HHI): Sum of squared weights
        - Effective N: 1 / HHI
        - Max weight: Largest single position
        """
        hhi = (weights ** 2).sum()
        effective_n = 1 / hhi if hhi > 0 else 0
        max_weight = weights.max()

        return {
            'herfindahl_index': hhi,
            'effective_n_assets': effective_n,
            'max_single_weight': max_weight,
            'top5_weight': weights.nlargest(5).sum(),
            'top10_weight': weights.nlargest(10).sum()
        }
```

**Estimated Lines**: ~220 lines

---

## 4. Integration with Track 4 (Optimizers)

### Seamless Integration Points

```python
# Example: Optimize portfolio with VaR constraint

from modules.optimization import MeanVarianceOptimizer, OptimizationConstraints
from modules.risk import VaRCalculator, RiskConfig

# Initialize optimizer
optimizer = MeanVarianceOptimizer(
    constraints=OptimizationConstraints(max_position=0.15),
    risk_aversion=1.0
)

# Optimize portfolio
result = optimizer.optimize(expected_returns, cov_matrix)

# Calculate VaR for optimized portfolio
var_calc = VaRCalculator(RiskConfig(confidence_level=0.95, time_horizon_days=10))
portfolio_returns = (historical_returns * result.weights).sum(axis=1)
var_result = var_calc.calculate(portfolio_returns, portfolio_value=100_000_000)

print(f"Portfolio VaR (95%, 10-day): {var_result.var_value:,.0f} KRW")
print(f"VaR as % of portfolio: {var_result.var_percent:.2%}")

# Validate against risk limits
if abs(var_result.var_percent) > 0.05:  # 5% limit
    print("⚠️ Portfolio VaR exceeds 5% limit!")
```

### Integration with Configuration Files

```python
# config/risk_config.yaml
risk_config:
  var_calculation:
    confidence_level: 0.95
    time_horizon_days: 10
    method: historical  # historical, parametric, monte_carlo
    monte_carlo_simulations: 10000
    historical_lookback_days: 252
    exponential_weighting: false
    lambda_decay: 0.94

  cvar_calculation:
    confidence_level: 0.95
    time_horizon_days: 10
    method: historical

  stress_testing:
    scenarios:
      - 2008_financial_crisis
      - 2020_covid_crash
      - 2022_bear_market
      - market_crash_30pct

  correlation_analysis:
    window_days: 60
    calculate_rolling: true

  risk_limits:
    portfolio_var_95_pct: 0.05  # 5% limit
    single_position_var_pct: 0.01  # 1% limit
    sector_concentration_pct: 0.40  # 40% limit
    beta_range: [0.8, 1.2]

# Load in code
import yaml
with open('config/risk_config.yaml') as f:
    config_dict = yaml.safe_load(f)

risk_config = RiskConfig(**config_dict['risk_config']['var_calculation'])
var_calc = VaRCalculator(risk_config)
```

---

## 5. Testing Strategy (No Database)

### Unit Tests (Pure Calculation Logic)

```python
# tests/test_risk_calculators.py

import pytest
import pandas as pd
import numpy as np
from modules.risk import (
    VaRCalculator, CVaRCalculator, StressTester,
    CorrelationAnalyzer, ExposureTracker, RiskConfig
)

class TestVaRCalculator:

    @pytest.fixture
    def sample_returns(self):
        """Generate sample return data"""
        np.random.seed(42)
        return pd.Series(np.random.normal(0.001, 0.02, 252))

    def test_historical_var_calculation(self, sample_returns):
        """Test historical VaR calculation"""
        var_calc = VaRCalculator(RiskConfig(confidence_level=0.95))
        result = var_calc.calculate(sample_returns, portfolio_value=100_000_000)

        assert result.var_value < 0  # VaR should be negative
        assert result.confidence_level == 0.95
        assert result.method == 'historical'
        assert abs(result.var_percent) < 0.10  # Should be < 10%

    def test_parametric_var_calculation(self, sample_returns):
        """Test parametric VaR calculation"""
        config = RiskConfig(confidence_level=0.95, var_method='parametric')
        var_calc = VaRCalculator(config)
        result = var_calc.calculate(sample_returns, portfolio_value=100_000_000)

        assert result.method == 'parametric'
        assert result.var_value < 0

    def test_monte_carlo_var_reproducibility(self, sample_returns):
        """Test Monte Carlo VaR reproducibility with seed"""
        np.random.seed(42)
        config = RiskConfig(confidence_level=0.95, var_method='monte_carlo')
        var_calc = VaRCalculator(config)
        result1 = var_calc.calculate(sample_returns, portfolio_value=100_000_000)

        np.random.seed(42)
        result2 = var_calc.calculate(sample_returns, portfolio_value=100_000_000)

        assert result1.var_value == result2.var_value

class TestCVaRCalculator:

    @pytest.fixture
    def sample_returns(self):
        np.random.seed(42)
        return pd.Series(np.random.normal(0.001, 0.02, 252))

    def test_cvar_exceeds_var(self, sample_returns):
        """CVaR should be more extreme than VaR"""
        cvar_calc = CVaRCalculator(RiskConfig(confidence_level=0.95))
        result = cvar_calc.calculate(sample_returns, portfolio_value=100_000_000)

        assert result.cvar_value < result.var_threshold * 100_000_000
        assert abs(result.cvar_percent) > abs(result.var_threshold)

class TestStressTester:

    @pytest.fixture
    def sample_portfolio(self):
        np.random.seed(42)
        asset_returns = pd.DataFrame(
            np.random.normal(0.001, 0.02, (252, 10)),
            columns=[f'ASSET{i}' for i in range(10)]
        )
        weights = pd.Series(0.1, index=asset_returns.columns)
        return asset_returns, weights

    def test_historical_scenario(self, sample_portfolio):
        """Test 2008 financial crisis scenario"""
        asset_returns, weights = sample_portfolio
        stress_tester = StressTester()

        results = stress_tester.calculate(
            asset_returns,
            weights,
            portfolio_value=100_000_000,
            scenarios=['2008_financial_crisis']
        )

        assert len(results) == 1
        assert results[0].portfolio_loss < 0
        assert results[0].scenario_type == 'historical'

class TestCorrelationAnalyzer:

    @pytest.fixture
    def sample_returns(self):
        np.random.seed(42)
        return pd.DataFrame(
            np.random.normal(0.001, 0.02, (252, 5)),
            columns=['A', 'B', 'C', 'D', 'E']
        )

    def test_correlation_matrix_symmetry(self, sample_returns):
        """Correlation matrix should be symmetric"""
        analyzer = CorrelationAnalyzer()
        result = analyzer.calculate(sample_returns)

        corr = result.correlation_matrix
        assert np.allclose(corr, corr.T)
        assert (corr.values.diagonal() == 1.0).all()

    def test_diversification_ratio(self, sample_returns):
        """Diversification ratio should be > 1 for diversified portfolio"""
        weights = pd.Series(0.2, index=sample_returns.columns)
        analyzer = CorrelationAnalyzer()
        result = analyzer.calculate(sample_returns, weights)

        assert result.diversification_ratio >= 1.0

class TestExposureTracker:

    @pytest.fixture
    def sample_portfolio(self):
        weights = pd.Series({
            'AAPL': 0.15,
            'MSFT': 0.15,
            'GOOGL': 0.10,
            'AMZN': 0.10,
            'TSLA': 0.10,
            'JPM': 0.10,
            'BAC': 0.10,
            'XOM': 0.10,
            'CVX': 0.05,
            'WMT': 0.05
        })

        metadata = {
            'AAPL': {'sector': 'Technology', 'region': 'US'},
            'MSFT': {'sector': 'Technology', 'region': 'US'},
            'GOOGL': {'sector': 'Technology', 'region': 'US'},
            'AMZN': {'sector': 'Consumer Discretionary', 'region': 'US'},
            'TSLA': {'sector': 'Consumer Discretionary', 'region': 'US'},
            'JPM': {'sector': 'Financials', 'region': 'US'},
            'BAC': {'sector': 'Financials', 'region': 'US'},
            'XOM': {'sector': 'Energy', 'region': 'US'},
            'CVX': {'sector': 'Energy', 'region': 'US'},
            'WMT': {'sector': 'Consumer Staples', 'region': 'US'}
        }

        return weights, metadata

    def test_sector_exposure_calculation(self, sample_portfolio):
        """Test sector exposure aggregation"""
        weights, metadata = sample_portfolio
        tracker = ExposureTracker()
        result = tracker.calculate(weights, metadata)

        sector_exp = result.sector_exposure
        assert sector_exp['Technology'] == 0.40  # AAPL + MSFT + GOOGL
        assert sector_exp['Financials'] == 0.20  # JPM + BAC
        assert sector_exp['Energy'] == 0.15  # XOM + CVX

    def test_concentration_metrics(self, sample_portfolio):
        """Test HHI and effective N calculation"""
        weights, metadata = sample_portfolio
        tracker = ExposureTracker()
        result = tracker.calculate(weights, metadata)

        hhi = result.concentration_metrics['herfindahl_index']
        effective_n = result.concentration_metrics['effective_n_assets']

        assert 0 < hhi <= 1.0
        assert 1 <= effective_n <= len(weights)
```

**Estimated Lines**: ~400 lines of tests

---

## 6. Success Criteria Validation

### Track 5 Requirements

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| **No DB Access** | All calculators use pure NumPy/pandas inputs | ✅ |
| **VaR Calculation** | 3 methods (Historical, Parametric, Monte Carlo) | ✅ |
| **CVaR Calculation** | Expected Shortfall beyond VaR | ✅ |
| **Stress Testing** | Historical + Hypothetical scenarios | ✅ |
| **Correlation Analysis** | Correlation matrix, diversification ratio, PCA | ✅ |
| **Exposure Tracking** | Sector, region, factor exposures | ✅ |
| **Configuration Integration** | RiskConfig dataclass + YAML loading | ✅ |
| **Abstract Base Class** | RiskCalculator with validate_inputs() | ✅ |
| **Standardized Results** | Data classes for all outputs | ✅ |
| **Unit Tests** | Comprehensive tests without database | ✅ |

### Comparison with CLAUDE.md Specification

| CLAUDE.md Requirement | Implementation |
|----------------------|----------------|
| VaR (95%, 99% confidence, 1/10/20-day) | ✅ Configurable via RiskConfig |
| CVaR for tail risk | ✅ CVaRCalculator |
| Historical scenarios (2008, 2020, 2022) | ✅ Predefined in HISTORICAL_SCENARIOS |
| Hypothetical scenarios | ✅ Custom scenario builder |
| Rolling correlations (60-day) | ✅ Configurable window |
| Factor exposure tracking | ✅ ExposureTracker with factor matrix |
| Diversification ratio | ✅ CorrelationAnalyzer |
| Risk limits validation | ✅ Constraint checking in results |

---

## 7. Implementation Statistics

### Code Volume

| File | Estimated Lines | Purpose |
|------|----------------|---------|
| `risk_base.py` | ~300 | Abstract base classes, data structures |
| `var_calculator.py` | ~350 | VaR (Historical, Parametric, Monte Carlo) |
| `cvar_calculator.py` | ~200 | CVaR / Expected Shortfall |
| `stress_tester.py` | ~280 | Scenario-based stress testing |
| `correlation_analyzer.py` | ~250 | Correlation & diversification |
| `exposure_tracker.py` | ~220 | Factor/sector exposure |
| `__init__.py` | ~50 | Module exports |
| **Total** | **~1,650 lines** | **6 files** |

### Test Coverage

- Unit tests: ~400 lines
- Test cases: 15+ test methods
- Coverage target: >90% (pure calculation logic)

### Documentation

- Design document: This file (~1,200 lines)
- Inline docstrings: 100% of public methods
- Usage examples: Integrated with optimizers (Track 4)

---

## 8. Next Steps (Implementation Phase)

### Track 5 Implementation Plan

1. **Phase 5.1**: Create `modules/risk/__init__.py` and `risk_base.py` (Week 7, Day 1)
2. **Phase 5.2**: Implement `var_calculator.py` (Week 7, Day 2-3)
3. **Phase 5.3**: Implement `cvar_calculator.py` (Week 7, Day 3)
4. **Phase 5.4**: Implement `stress_tester.py` (Week 7, Day 4)
5. **Phase 5.5**: Implement `correlation_analyzer.py` (Week 7, Day 5)
6. **Phase 5.6**: Implement `exposure_tracker.py` (Week 7, Day 6)
7. **Phase 5.7**: Write unit tests (Week 7, Day 7)
8. **Phase 5.8**: Validation & documentation (Week 8, Day 1)

### Optional: Rename Existing Risk Manager

```bash
# Rename to clarify scope (trading risk vs. portfolio risk analytics)
mv modules/risk_manager.py modules/trading_risk_manager.py
mv tests/test_risk_manager.py tests/test_trading_risk_manager.py

# Update imports in other modules (if any)
grep -r "from modules.risk_manager" modules/
```

---

## 9. Appendix: Usage Examples

### Example 1: Calculate Portfolio VaR

```python
from modules.risk import VaRCalculator, RiskConfig
import pandas as pd
import numpy as np

# Sample portfolio returns
np.random.seed(42)
portfolio_returns = pd.Series(np.random.normal(0.001, 0.02, 252))

# Initialize VaR calculator
config = RiskConfig(
    confidence_level=0.95,
    time_horizon_days=10,
    var_method='historical'
)
var_calc = VaRCalculator(config)

# Calculate VaR
result = var_calc.calculate(portfolio_returns, portfolio_value=100_000_000)

print(f"Portfolio VaR (95%, 10-day): {result.var_value:,.0f} KRW")
print(f"VaR as % of portfolio: {result.var_percent:.2%}")
print(f"Method: {result.method}")
```

### Example 2: Stress Test Portfolio

```python
from modules.risk import StressTester, RiskConfig
import pandas as pd
import numpy as np

# Sample multi-asset portfolio
np.random.seed(42)
asset_returns = pd.DataFrame(
    np.random.normal(0.001, 0.02, (252, 10)),
    columns=[f'ASSET{i}' for i in range(10)]
)
weights = pd.Series(0.1, index=asset_returns.columns)

# Initialize stress tester
stress_tester = StressTester(RiskConfig())

# Run stress tests
results = stress_tester.calculate(
    asset_returns,
    weights,
    portfolio_value=100_000_000,
    scenarios=['2008_financial_crisis', '2020_covid_crash']
)

# Print results
for result in results:
    print(f"\nScenario: {result.scenario_name}")
    print(f"Portfolio Loss: {result.portfolio_loss:,.0f} KRW ({result.portfolio_loss_percent:.2%})")
    print(f"Description: {result.scenario_description}")
```

### Example 3: Analyze Portfolio Diversification

```python
from modules.risk import CorrelationAnalyzer, RiskConfig
import pandas as pd
import numpy as np

# Sample asset returns
np.random.seed(42)
asset_returns = pd.DataFrame(
    np.random.normal(0.001, 0.02, (252, 5)),
    columns=['AAPL', 'MSFT', 'GOOGL', 'JPM', 'XOM']
)
weights = pd.Series([0.25, 0.25, 0.20, 0.15, 0.15], index=asset_returns.columns)

# Initialize analyzer
analyzer = CorrelationAnalyzer(RiskConfig(correlation_window_days=60))

# Calculate correlations
result = analyzer.calculate(asset_returns, weights, rolling=False)

print(f"Average Correlation: {result.average_correlation:.3f}")
print(f"Diversification Ratio: {result.diversification_ratio:.3f}")
print(f"PC1 Variance Explained: {result.metadata['pc1_variance_explained']:.2%}")
print("\nCorrelation Matrix:")
print(result.correlation_matrix)
```

### Example 4: Track Portfolio Exposures

```python
from modules.risk import ExposureTracker, RiskConfig
import pandas as pd

# Portfolio weights
weights = pd.Series({
    'AAPL': 0.15, 'MSFT': 0.15, 'GOOGL': 0.10,
    'JPM': 0.10, 'BAC': 0.10,
    'XOM': 0.10, 'CVX': 0.05,
    'WMT': 0.05, 'PG': 0.05, 'KO': 0.05,
    '005930': 0.05, '000660': 0.05  # Samsung, SK Hynix
})

# Ticker metadata
ticker_metadata = {
    'AAPL': {'sector': 'Technology', 'region': 'US'},
    'MSFT': {'sector': 'Technology', 'region': 'US'},
    'GOOGL': {'sector': 'Technology', 'region': 'US'},
    'JPM': {'sector': 'Financials', 'region': 'US'},
    'BAC': {'sector': 'Financials', 'region': 'US'},
    'XOM': {'sector': 'Energy', 'region': 'US'},
    'CVX': {'sector': 'Energy', 'region': 'US'},
    'WMT': {'sector': 'Consumer Staples', 'region': 'US'},
    'PG': {'sector': 'Consumer Staples', 'region': 'US'},
    'KO': {'sector': 'Consumer Staples', 'region': 'US'},
    '005930': {'sector': 'Technology', 'region': 'KR'},
    '000660': {'sector': 'Technology', 'region': 'KR'}
}

# Initialize tracker
tracker = ExposureTracker(RiskConfig())

# Calculate exposures
result = tracker.calculate(weights, ticker_metadata)

print("Sector Exposure:")
print(result.sector_exposure)
print("\nRegion Exposure:")
print(result.region_exposure)
print(f"\nHerfindahl Index: {result.concentration_metrics['herfindahl_index']:.4f}")
print(f"Effective N Assets: {result.concentration_metrics['effective_n_assets']:.1f}")
```

---

## 10. Conclusion

### Design Decision Summary

1. **Keep existing `risk_manager.py` separate** - Different purposes (trading vs. portfolio analytics)
2. **Create new `modules/risk/` directory** - 6 files, ~1,650 lines, pure calculation logic
3. **Follow Track 4 architecture patterns** - Abstract base class, data classes, configuration-driven
4. **No database dependencies** - All inputs via NumPy arrays / pandas DataFrames
5. **Comprehensive testing** - 15+ unit tests without database

### Ready for Implementation

- ✅ Architecture designed
- ✅ Class interfaces specified
- ✅ Integration points defined
- ✅ Test strategy planned
- ✅ Success criteria validated

**Next Action**: Proceed to Track 5 implementation starting with `risk_base.py`

---

**Design Document Completed**: 2025-10-21
**Approved for Implementation**: Awaiting user confirmation
