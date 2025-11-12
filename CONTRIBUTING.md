# Contributing to Quant Investment Platform

**Thank you for your interest in contributing!**

We welcome contributions from the community to make this platform better for everyone. This document provides guidelines for contributing to the project.

---

## 📋 Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [How Can I Contribute?](#how-can-i-contribute)
3. [Development Setup](#development-setup)
4. [Coding Standards](#coding-standards)
5. [Commit Guidelines](#commit-guidelines)
6. [Pull Request Process](#pull-request-process)
7. [Testing Requirements](#testing-requirements)
8. [Documentation Guidelines](#documentation-guidelines)

---

## 🤝 Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of:
- Experience level
- Background
- Identity
- Nationality

### Expected Behavior

✅ **Do**:
- Be respectful and considerate
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other contributors

❌ **Don't**:
- Use inappropriate language or imagery
- Make personal attacks or insults
- Harass or intimidate others
- Publish others' private information

### Reporting Issues

If you experience or witness unacceptable behavior, please report it to: **jsj9346@gmail.com**

---

## 💡 How Can I Contribute?

### 1. Reporting Bugs 🐛

**Before submitting a bug report**:
- Check existing [GitHub Issues](https://github.com/jsj9346/spock/issues)
- Verify the bug is reproducible
- Collect relevant information (logs, error messages, environment details)

**Bug Report Template**:
```markdown
**Describe the bug**
A clear and concise description of the bug.

**To Reproduce**
Steps to reproduce the behavior:
1. Run command '...'
2. See error '...'

**Expected behavior**
What you expected to happen.

**Environment**:
- OS: [e.g., macOS 14.0, Ubuntu 22.04]
- Python version: [e.g., 3.11.5]
- PostgreSQL version: [e.g., 15.3]
- TimescaleDB version: [e.g., 2.11.1]

**Additional context**
Add any other context, logs, or screenshots.
```

### 2. Suggesting Features 💡

**Feature Request Template**:
```markdown
**Problem Statement**
Describe the problem this feature would solve.

**Proposed Solution**
Describe your proposed solution.

**Alternatives Considered**
Other solutions you've considered.

**Impact**
- Who benefits from this feature?
- What are the performance/complexity trade-offs?
```

### 3. Improving Documentation 📚

Documentation improvements are always welcome:
- Fix typos or unclear explanations
- Add missing documentation
- Improve examples
- Translate documentation (Korean/English)

### 4. Contributing Code 💻

See sections below for detailed guidelines on code contributions.

---

## 🛠️ Development Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- TimescaleDB 2.11+
- Git

### Setup Steps

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/spock.git
cd spock

# 3. Add upstream remote
git remote add upstream https://github.com/jsj9346/spock.git

# 4. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 5. Install dependencies (development mode)
pip install -r requirements_quant.txt
pip install -r requirements_dev.txt  # If available

# 6. Install pre-commit hooks (recommended)
pre-commit install

# 7. Set up database
createdb quant_platform_dev
psql -d quant_platform_dev -c "CREATE EXTENSION IF NOT EXISTS timescaledb;"
python3 scripts/init_postgres_schema.py

# 8. Configure environment
cp .env.example .env.dev
# Edit .env.dev with your development credentials
```

### Verify Setup

```bash
# Run tests to verify setup
pytest tests/ -v

# Run linter
flake8 modules/

# Run type checker
mypy modules/
```

---

## 📐 Coding Standards

### Python Style Guide

We follow **PEP 8** with some modifications:

```python
# Line length: 100 characters (not 79)
# Use type hints for all functions
# Use docstrings for all public functions/classes

def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """
    Calculate annualized Sharpe ratio.

    Args:
        returns: Series of period returns
        risk_free_rate: Annual risk-free rate (default: 0.0)
        periods_per_year: Number of periods per year (default: 252 for daily)

    Returns:
        Annualized Sharpe ratio

    Example:
        >>> returns = pd.Series([0.01, 0.02, -0.01, 0.03])
        >>> calculate_sharpe_ratio(returns)
        1.23
    """
    excess_returns = returns - risk_free_rate / periods_per_year
    return np.sqrt(periods_per_year) * excess_returns.mean() / excess_returns.std()
```

### Code Quality Tools

**Linting** (flake8):
```bash
flake8 modules/ --max-line-length=100 --ignore=E203,W503
```

**Type Checking** (mypy):
```bash
mypy modules/ --ignore-missing-imports
```

**Formatting** (black):
```bash
black modules/ --line-length=100
```

**Import Sorting** (isort):
```bash
isort modules/
```

### File Structure Conventions

```
modules/
├── __init__.py              # Package initialization
├── backtest/
│   ├── __init__.py
│   ├── backtest_engine.py   # Main engine class
│   ├── vectorbt_adapter.py  # vectorbt integration
│   └── tests/               # Module-specific tests
│       ├── __init__.py
│       └── test_backtest_engine.py
```

---

## 📝 Commit Guidelines

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

- **feat**: New feature
- **fix**: Bug fix
- **docs**: Documentation changes
- **style**: Code formatting (no logic changes)
- **refactor**: Code refactoring (no behavior changes)
- **perf**: Performance improvements
- **test**: Adding or updating tests
- **chore**: Build process, dependency updates

### Examples

```
feat(backtest): add walk-forward optimization support

Implement walk-forward optimization with rolling and anchored windows.
Includes parameter grid search and out-of-sample validation.

Closes #123
```

```
fix(database): resolve connection pool exhaustion

Fix connection pool leak in PostgresDataProvider by ensuring
connections are properly released after each query.

Fixes #456
```

```
docs(getting-started): add FAQ section

Add 15 frequently asked questions covering installation,
usage, and troubleshooting.
```

### Commit Best Practices

✅ **Do**:
- Write clear, concise commit messages
- Keep commits focused on a single change
- Reference related issues/PRs

❌ **Don't**:
- Commit large, unrelated changes together
- Use vague messages like "fix stuff" or "updates"
- Commit sensitive information (API keys, passwords)

---

## 🔄 Pull Request Process

### Before Submitting

1. **Update from upstream**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all tests**:
   ```bash
   pytest tests/ -v --cov=modules --cov-report=html
   ```

3. **Run linters**:
   ```bash
   flake8 modules/
   mypy modules/
   black modules/ --check
   ```

4. **Update documentation**:
   - Update relevant `.md` files
   - Add docstrings to new functions/classes
   - Update examples if API changed

### Pull Request Template

```markdown
## Description
Brief description of the changes.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing
- [ ] All existing tests pass
- [ ] New tests added for new features
- [ ] Manual testing performed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests added and passing
- [ ] Dependent changes merged

## Related Issues
Closes #(issue number)
```

### Review Process

1. **Automated Checks**: CI/CD pipeline runs automatically
2. **Code Review**: Maintainers will review your PR
3. **Feedback**: Address review comments
4. **Approval**: PR approved by maintainer
5. **Merge**: Maintainer merges PR

### After Merge

```bash
# Update your local repository
git checkout main
git pull upstream main

# Delete feature branch
git branch -d feature/your-feature-name
git push origin --delete feature/your-feature-name
```

---

## 🧪 Testing Requirements

### Test Coverage Requirements

- **Minimum coverage**: 80% for new code
- **Critical modules**: 90%+ coverage (backtest, factors, risk)

### Writing Tests

```python
import pytest
import pandas as pd
from modules.backtest import BacktestEngine


class TestBacktestEngine:
    """Test suite for BacktestEngine."""

    @pytest.fixture
    def sample_data(self):
        """Fixture providing sample OHLCV data."""
        return pd.DataFrame({
            'open': [100, 102, 101, 103],
            'high': [101, 103, 102, 104],
            'low': [99, 101, 100, 102],
            'close': [100.5, 102.5, 101.5, 103.5],
            'volume': [1000, 1100, 1050, 1150]
        })

    def test_backtest_execution(self, sample_data):
        """Test basic backtest execution."""
        engine = BacktestEngine()
        results = engine.run_backtest(
            strategy='momentum_value',
            data=sample_data,
            start_date='2020-01-01',
            end_date='2023-12-31'
        )

        assert results['total_return'] > 0
        assert 'sharpe_ratio' in results
        assert len(results['trades']) > 0

    def test_invalid_strategy(self):
        """Test error handling for invalid strategy."""
        engine = BacktestEngine()
        with pytest.raises(ValueError, match="Unknown strategy"):
            engine.run_backtest(strategy='invalid_strategy')
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_backtest_engine.py -v

# Run with coverage
pytest tests/ --cov=modules --cov-report=html

# Run only unit tests (fast)
pytest tests/ -m unit

# Run only integration tests (slow)
pytest tests/ -m integration
```

---

## 📚 Documentation Guidelines

### Documentation Types

1. **Inline Comments**: Explain complex logic
2. **Docstrings**: Document all public functions/classes
3. **README Files**: Module-level documentation
4. **Guides**: User-facing documentation in `docs/`

### Docstring Format (Google Style)

```python
def calculate_portfolio_var(
    returns: pd.DataFrame,
    confidence_level: float = 0.95,
    method: str = 'historical'
) -> float:
    """
    Calculate Value at Risk (VaR) for a portfolio.

    Uses either historical, parametric, or Monte Carlo methods to estimate
    the maximum expected loss at a given confidence level.

    Args:
        returns: DataFrame with portfolio returns (rows=dates, cols=assets)
        confidence_level: Confidence level for VaR calculation (default: 0.95)
        method: Calculation method ('historical', 'parametric', 'monte_carlo')

    Returns:
        Value at Risk as a positive float (e.g., 0.05 means 5% loss)

    Raises:
        ValueError: If method is not recognized
        ValueError: If confidence_level not in (0, 1)

    Example:
        >>> import pandas as pd
        >>> returns = pd.DataFrame({'Asset1': [0.01, -0.02, 0.03]})
        >>> var = calculate_portfolio_var(returns, confidence_level=0.95)
        >>> print(f"95% VaR: {var:.2%}")
        95% VaR: 2.15%

    Note:
        - Historical method requires at least 100 data points
        - Monte Carlo method runs 10,000 simulations by default
        - VaR does not account for tail risk beyond the confidence level

    References:
        - Jorion, P. (2006). Value at Risk: The New Benchmark for Managing Financial Risk
    """
    # Implementation...
```

### Documentation Best Practices

✅ **Do**:
- Write clear, concise explanations
- Include examples for complex functions
- Keep documentation up-to-date with code changes
- Use consistent terminology
- Add diagrams for complex architectures

❌ **Don't**:
- Duplicate information across documents
- Write overly technical documentation without context
- Forget to update documentation when code changes
- Use jargon without explanation

---

## 🏷️ Issue Labels

We use the following labels to organize issues:

**Type**:
- `bug` - Something isn't working
- `feature` - New feature request
- `enhancement` - Improvement to existing feature
- `documentation` - Documentation improvements

**Priority**:
- `priority: critical` - Urgent, blocking
- `priority: high` - Important
- `priority: medium` - Normal priority
- `priority: low` - Nice to have

**Status**:
- `status: needs-triage` - Needs initial review
- `status: in-progress` - Work in progress
- `status: blocked` - Blocked by dependency
- `status: ready` - Ready for implementation

**Component**:
- `component: backtest` - Backtesting engine
- `component: factors` - Factor library
- `component: optimization` - Portfolio optimization
- `component: database` - Database layer
- `component: api` - API endpoints

---

## 🎯 Development Priorities

### High Priority
- Backtesting engine improvements
- Factor library expansion
- Performance optimization
- Test coverage improvements

### Medium Priority
- Documentation enhancements
- UI/UX improvements
- New data sources integration
- Example strategies

### Low Priority
- Code refactoring
- Developer tooling
- Experimental features

---

## 📞 Getting Help

### Resources
- **Documentation**: [DOCUMENTATION_INDEX.md](DOCUMENTATION_INDEX.md)
- **Troubleshooting**: [TROUBLESHOOTING_INDEX.md](TROUBLESHOOTING_INDEX.md)
- **Discussions**: [GitHub Discussions](https://github.com/jsj9346/spock/discussions)
- **Email**: jsj9346@gmail.com

### Questions?

If you have questions that aren't covered by the documentation:
1. Check [GitHub Discussions](https://github.com/jsj9346/spock/discussions)
2. Search [existing issues](https://github.com/jsj9346/spock/issues)
3. Ask in a new discussion or issue

---

## 🙏 Recognition

Contributors will be recognized in:
- README.md Contributors section
- Release notes for their contributions
- Project documentation credits

---

## 📜 License

By contributing to this project, you agree that your contributions will be licensed under the [MIT License](LICENSE).

---

**Thank you for contributing to the Quant Investment Platform! 🎉**

Every contribution, no matter how small, makes a difference.

---

**Last Updated**: 2025-11-12
**Version**: 1.0.0
**Maintainer**: jsj9346@gmail.com
