"""
HTML report generator for backtest results.

Integrates Jinja2 templates with Plotly charts to create
comprehensive, interactive HTML reports for backtest analysis.
"""

from typing import Dict, Optional, List, Any
from pathlib import Path
from datetime import datetime
import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from cli.utils.chart_generator import ChartGenerator


class ReportGenerator:
    """
    HTML report generator for quant platform analytics.

    Features:
    - Jinja2 template rendering with Plotly charts
    - Comprehensive backtest reports
    - Portfolio analytics reports
    - Custom theme support
    - Export to HTML

    Usage:
        generator = ReportGenerator()
        generator.generate_backtest_report(
            portfolio_returns=returns,
            metrics=metrics,
            output_path='report.html'
        )
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize report generator.

        Args:
            template_dir: Path to Jinja2 templates directory
                         (default: cli/templates/)
        """
        if template_dir is None:
            # Default to cli/templates/ directory
            template_dir = Path(__file__).parent.parent / 'templates'

        self.template_dir = template_dir

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )

        # Initialize chart generator
        self.chart_generator = ChartGenerator(theme='plotly_dark')

    def generate_backtest_report(
        self,
        portfolio_returns: pd.Series,
        metrics: Dict[str, float],
        tickers: List[str],
        strategy_name: str,
        start_date: str,
        end_date: str,
        initial_cash: float,
        commission: float,
        trades: Optional[pd.DataFrame] = None,
        benchmark_returns: Optional[pd.Series] = None,
        output_path: str = 'backtest_report.html',
        title: str = 'Backtest Report'
    ) -> str:
        """
        Generate comprehensive backtest HTML report.

        Args:
            portfolio_returns: Series of portfolio returns
            metrics: Dictionary of performance metrics
            tickers: List of ticker symbols
            strategy_name: Name of the strategy
            start_date: Backtest start date (YYYY-MM-DD)
            end_date: Backtest end date (YYYY-MM-DD)
            initial_cash: Initial portfolio cash
            commission: Commission rate
            trades: Optional DataFrame with trade data
            benchmark_returns: Optional benchmark returns
            output_path: Output HTML file path
            title: Report title

        Returns:
            Path to generated HTML file
        """
        # Generate charts
        equity_curve = self.chart_generator.create_equity_curve(
            portfolio_returns,
            benchmark_returns,
            title="Portfolio Equity Curve"
        )

        drawdown = self.chart_generator.create_drawdown_chart(
            portfolio_returns,
            title="Portfolio Drawdown"
        )

        monthly_returns = self.chart_generator.create_monthly_returns_heatmap(
            portfolio_returns,
            title="Monthly Returns"
        )

        # Convert charts to HTML
        equity_curve_html = equity_curve.to_html(
            include_plotlyjs=False,
            div_id='equity-curve'
        )

        drawdown_html = drawdown.to_html(
            include_plotlyjs=False,
            div_id='drawdown'
        )

        monthly_returns_html = monthly_returns.to_html(
            include_plotlyjs=False,
            div_id='monthly-returns'
        )

        trade_analysis_html = None
        trade_stats = None

        # Generate trade analysis if trades provided
        if trades is not None and len(trades) > 0:
            if 'PnL' in trades.columns:
                trade_analysis = self.chart_generator.create_trade_analysis(
                    trades,
                    title="Trade P&L Distribution"
                )

                trade_analysis_html = trade_analysis.to_html(
                    include_plotlyjs=False,
                    div_id='trade-analysis'
                )

                # Calculate trade statistics
                winning_trades = trades[trades['PnL'] > 0]
                losing_trades = trades[trades['PnL'] < 0]

                trade_stats = {
                    'total_trades': len(trades),
                    'winning_trades': len(winning_trades),
                    'losing_trades': len(losing_trades),
                    'win_rate': (len(winning_trades) / len(trades) * 100) if len(trades) > 0 else 0,
                    'avg_pnl': trades['PnL'].mean(),
                    'best_trade': trades['PnL'].max(),
                    'worst_trade': trades['PnL'].min(),
                    'profit_factor': abs(winning_trades['PnL'].sum() / losing_trades['PnL'].sum()) if len(losing_trades) > 0 else 0
                }

        # Load template
        template = self.env.get_template('backtest_report.html')

        # Render template with data
        html_content = template.render(
            title=title,
            strategy_name=strategy_name,
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            initial_cash=initial_cash,
            commission=commission,
            metrics=metrics,
            equity_curve_html=equity_curve_html,
            drawdown_html=drawdown_html,
            monthly_returns_html=monthly_returns_html,
            trade_analysis_html=trade_analysis_html,
            trade_stats=trade_stats,
            generation_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return str(output_file.absolute())

    def generate_portfolio_report(
        self,
        holdings: pd.DataFrame,
        portfolio_value: float,
        allocation: Dict[str, float],
        risk_metrics: Dict[str, float],
        output_path: str = 'portfolio_report.html',
        title: str = 'Portfolio Report'
    ) -> str:
        """
        Generate portfolio analytics HTML report.

        Args:
            holdings: DataFrame with current holdings
            portfolio_value: Total portfolio value
            allocation: Dictionary of asset allocations
            risk_metrics: Dictionary of risk metrics
            output_path: Output HTML file path
            title: Report title

        Returns:
            Path to generated HTML file
        """
        # TODO: Implement portfolio report template
        # This is a placeholder for future implementation
        raise NotImplementedError("Portfolio report generation coming in future update")


if __name__ == '__main__':
    # Test report generator
    import numpy as np

    print("Testing ReportGenerator...")

    # Create sample data
    dates = pd.date_range('2023-01-01', '2023-12-31', freq='D')
    returns = pd.Series(np.random.randn(len(dates)) * 0.01, index=dates)
    benchmark_returns = pd.Series(np.random.randn(len(dates)) * 0.008, index=dates)

    # Create sample trades
    trades = pd.DataFrame({
        'Entry Date': pd.date_range('2023-01-15', periods=50, freq='W'),
        'Exit Date': pd.date_range('2023-01-22', periods=50, freq='W'),
        'PnL': np.random.randn(50) * 500000
    })

    # Sample metrics
    metrics = {
        'total_return': 15.5,
        'annualized_return': 16.8,
        'sharpe_ratio': 1.8,
        'max_drawdown': -12.3,
        'win_rate': 58.5,
        'profit_factor': 1.65,
        'total_trades': 50,
        'final_value': 11550000
    }

    # Generate report
    generator = ReportGenerator()

    report_path = generator.generate_backtest_report(
        portfolio_returns=returns,
        metrics=metrics,
        tickers=['005930', '000660', '035420'],
        strategy_name='Momentum + Value',
        start_date='2023-01-01',
        end_date='2023-12-31',
        initial_cash=10000000,
        commission=0.0015,
        trades=trades,
        benchmark_returns=benchmark_returns,
        output_path='/tmp/test_backtest_report.html',
        title='Test Backtest Report'
    )

    print(f"✓ Report generated: {report_path}")
    print("\nReport generation test passed!")
