"""
Backtest Reporter

Purpose: Generate comprehensive backtest reports in multiple formats.

Key Features:
  - Console summary (quick feedback)
  - JSON export (machine-readable)
  - CSV trade log (Excel compatibility)
  - HTML report with charts (professional presentation)
  - Database persistence (historical tracking)

Design Philosophy:
  - Multi-format output for different use cases
  - Professional presentation for stakeholders
  - Machine-readable formats for automation
  - Historical tracking for comparison
"""

import json
import csv
from pathlib import Path
from typing import Optional
import logging
from datetime import datetime
import hashlib

from .backtest_config import BacktestResult
from modules.db_manager_sqlite import SQLiteDatabaseManager


logger = logging.getLogger(__name__)


class BacktestReporter:
    """
    Generate comprehensive backtest reports in multiple formats.

    Attributes:
        result: BacktestResult to generate reports from
    """

    def __init__(self, result: BacktestResult):
        """
        Initialize reporter with backtest result.

        Args:
            result: BacktestResult object from BacktestEngine
        """
        self.result = result
        logger.info(f"BacktestReporter initialized for backtest: {result.config.start_date} to {result.config.end_date}")

    def print_console_summary(self):
        """
        Print formatted summary to console.

        Output Sections:
            1. Configuration summary
            2. Performance metrics
            3. Risk metrics
            4. Trading metrics
            5. Pattern analysis
            6. Success criteria validation
        """
        m = self.result.metrics
        config = self.result.config

        print("\n" + "=" * 80)
        print("Spock Backtest Report")
        print("=" * 80)
        print()

        # Configuration
        print("Configuration:")
        print(f"  Period: {config.start_date} to {config.end_date} ({(config.end_date - config.start_date).days} days)")
        print(f"  Regions: {', '.join(config.regions)}")
        print(f"  Initial Capital: ₩{config.initial_capital:,.0f}")
        print(f"  Risk Profile: {config.risk_profile.capitalize()}")
        print()

        # Strategy Parameters
        print("Strategy Parameters:")
        print(f"  Score Threshold: {config.score_threshold}")
        print(f"  Kelly Multiplier: {config.kelly_multiplier} ({'Half Kelly' if config.kelly_multiplier == 0.5 else 'Full Kelly' if config.kelly_multiplier == 1.0 else f'{config.kelly_multiplier}x Kelly'})")
        print(f"  Stop Loss: {config.stop_loss_atr_multiplier} × ATR ({config.stop_loss_min:.0%}-{config.stop_loss_max:.0%} range)")
        print(f"  Profit Target: {config.profit_target:.0%}")
        print()

        print("=" * 80)
        print("Performance Summary")
        print("=" * 80)
        print()

        # Return Metrics
        print("Return Metrics:")
        print(f"  Total Return:           {m.total_return:+.1%}")
        print(f"  Annualized Return:      {m.annualized_return:+.1%}")
        print(f"  CAGR:                   {m.cagr:+.1%}")
        print()

        # Risk Metrics
        success_marker = lambda val, target, higher_is_better: "✅" if (val >= target if higher_is_better else val <= target) else "❌"

        print("Risk Metrics:")
        print(f"  Sharpe Ratio:           {m.sharpe_ratio:.2f}   {success_marker(m.sharpe_ratio, 1.5, True)} (Target: ≥1.5)")
        print(f"  Sortino Ratio:          {m.sortino_ratio:.2f}")
        print(f"  Calmar Ratio:           {m.calmar_ratio:.2f}")
        print(f"  Max Drawdown:          {m.max_drawdown:.1%}  {success_marker(abs(m.max_drawdown), 0.15, False)} (Target: ≤15%)")
        print(f"  Std Dev (Annual):       {m.std_returns:.1%}")
        print()

        # Trading Metrics
        print("Trading Metrics:")
        print(f"  Total Trades:           {m.total_trades}")
        print(f"  Win Rate:               {m.win_rate:.1%}  {success_marker(m.win_rate, 0.55, True)} (Target: ≥55%)")
        print(f"  Profit Factor:          {m.profit_factor:.2f}")
        print(f"  Avg Win:               {m.avg_win_pct:+.1%}")
        print(f"  Avg Loss:              {m.avg_loss_pct:.1%}")
        print(f"  Win/Loss Ratio:         {m.avg_win_loss_ratio:.2f}")
        print(f"  Avg Hold Time:          {m.avg_holding_period_days:.1f} days")
        print()

        # Kelly Validation
        print("Kelly Validation:")
        print(f"  Kelly Accuracy:         {m.kelly_accuracy:.1%}  {success_marker(m.kelly_accuracy, 0.80, True)}")
        print()

        # Pattern Analysis
        if self.result.pattern_metrics:
            print("=" * 80)
            print("Performance by Pattern Type")
            print("=" * 80)
            print()
            print(f"{'Pattern':<20} {'Trades':>7} {'Win Rate':>10} {'Avg Return':>12} {'Total P&L':>15}")
            print("─" * 80)
            for pattern, pm in sorted(self.result.pattern_metrics.items(), key=lambda x: x[1].total_pnl, reverse=True):
                print(f"{pattern:<20} {pm.total_trades:>7} {pm.win_rate:>9.1%} {pm.avg_return:>11.1%} ₩{pm.total_pnl:>13,.0f}")
            print()

        # Region Analysis
        if self.result.region_metrics:
            print("=" * 80)
            print("Performance by Region")
            print("=" * 80)
            print()
            print(f"{'Region':<10} {'Trades':>7} {'Win Rate':>10} {'Total Return':>14} {'Profit Factor':>15}")
            print("─" * 80)
            for region, rm in sorted(self.result.region_metrics.items()):
                print(f"{region:<10} {rm.total_trades:>7} {rm.win_rate:>9.1%} {rm.total_return:>13.1%} {rm.profit_factor:>14.2f}")
            print()

        # Top Winners/Losers
        print("=" * 80)
        print("Top 10 Winners")
        print("=" * 80)
        print()
        winning_trades = sorted([t for t in self.result.winning_trades], key=lambda x: x.pnl, reverse=True)[:10]
        if winning_trades:
            print(f"{'Ticker':<8} {'Entry Date':<12} {'Exit Date':<12} {'Hold Days':>10} {'Return':>10} {'P&L':>15}")
            print("─" * 80)
            for trade in winning_trades:
                print(f"{trade.ticker:<8} {trade.entry_date} {trade.exit_date} {trade.holding_period_days:>10} {trade.pnl_pct:>9.1%} ₩{trade.pnl:>13,.0f}")
        print()

        print("=" * 80)
        print("Top 10 Losers")
        print("=" * 80)
        print()
        losing_trades = sorted([t for t in self.result.losing_trades], key=lambda x: x.pnl)[:10]
        if losing_trades:
            print(f"{'Ticker':<8} {'Entry Date':<12} {'Exit Date':<12} {'Hold Days':>10} {'Return':>10} {'P&L':>15}")
            print("─" * 80)
            for trade in losing_trades:
                print(f"{trade.ticker:<8} {trade.entry_date} {trade.exit_date} {trade.holding_period_days:>10} {trade.pnl_pct:>9.1%} ₩{trade.pnl:>13,.0f}")
        print()

        # Success Criteria Summary
        print("=" * 80)
        print("Success Criteria Validation (from spock_PRD.md)")
        print("=" * 80)
        print()
        criteria_met = self.result.metrics.meets_success_criteria()
        print(f"  Total Return ≥15%:      {m.annualized_return:.1%}  {success_marker(m.annualized_return, 0.15, True)}")
        print(f"  Sharpe Ratio ≥1.5:      {m.sharpe_ratio:.2f}  {success_marker(m.sharpe_ratio, 1.5, True)}")
        print(f"  Max Drawdown ≤15%:     {abs(m.max_drawdown):.1%}  {success_marker(abs(m.max_drawdown), 0.15, False)}")
        print(f"  Win Rate ≥55%:          {m.win_rate:.1%}  {success_marker(m.win_rate, 0.55, True)}")
        print()
        if criteria_met:
            print("✅ ALL SUCCESS CRITERIA MET!")
        else:
            print("⚠️  Some success criteria not met")
        print()

        print("=" * 80)
        print(f"Final Portfolio Value: ₩{self.result.final_portfolio_value:,.0f}")
        print(f"Total Profit: ₩{self.result.total_profit:,.0f} ({m.total_return:+.1%})")
        print(f"Execution Time: {self.result.execution_time_seconds:.1f} seconds")
        print("=" * 80)

    def export_json(self, filepath: str):
        """
        Export full results to JSON.

        Args:
            filepath: Path to save JSON file

        Output Format:
            {
                "config": {...},
                "metrics": {...},
                "trades": [...],
                "equity_curve": {...},
                "pattern_metrics": {...},
                "region_metrics": {...}
            }
        """
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        # Convert result to JSON-serializable dict
        result_dict = {
            "config": {
                "start_date": str(self.result.config.start_date),
                "end_date": str(self.result.config.end_date),
                "regions": self.result.config.regions,
                "tickers": self.result.config.tickers,
                "score_threshold": self.result.config.score_threshold,
                "risk_profile": self.result.config.risk_profile,
                "kelly_multiplier": self.result.config.kelly_multiplier,
                "max_position_size": self.result.config.max_position_size,
                "initial_capital": self.result.config.initial_capital,
            },
            "metrics": {
                "total_return": self.result.metrics.total_return,
                "annualized_return": self.result.metrics.annualized_return,
                "cagr": self.result.metrics.cagr,
                "sharpe_ratio": self.result.metrics.sharpe_ratio,
                "sortino_ratio": self.result.metrics.sortino_ratio,
                "calmar_ratio": self.result.metrics.calmar_ratio,
                "max_drawdown": self.result.metrics.max_drawdown,
                "max_drawdown_duration_days": self.result.metrics.max_drawdown_duration_days,
                "std_returns": self.result.metrics.std_returns,
                "downside_deviation": self.result.metrics.downside_deviation,
                "total_trades": self.result.metrics.total_trades,
                "win_rate": self.result.metrics.win_rate,
                "profit_factor": self.result.metrics.profit_factor,
                "avg_win_pct": self.result.metrics.avg_win_pct,
                "avg_loss_pct": self.result.metrics.avg_loss_pct,
                "avg_win_loss_ratio": self.result.metrics.avg_win_loss_ratio,
                "avg_holding_period_days": self.result.metrics.avg_holding_period_days,
                "kelly_accuracy": self.result.metrics.kelly_accuracy,
                "success_criteria_met": self.result.metrics.meets_success_criteria(),
            },
            "trades": [
                {
                    "ticker": t.ticker,
                    "region": t.region,
                    "entry_date": str(t.entry_date),
                    "exit_date": str(t.exit_date) if t.exit_date else None,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "shares": t.shares,
                    "commission": t.commission,
                    "slippage": t.slippage,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "pattern_type": t.pattern_type,
                    "exit_reason": t.exit_reason,
                    "entry_score": t.entry_score,
                    "sector": t.sector,
                }
                for t in self.result.trades if t.is_closed
            ],
            "equity_curve": {
                str(date): float(value)
                for date, value in self.result.equity_curve.items()
            },
            "pattern_metrics": {
                pattern: {
                    "total_trades": pm.total_trades,
                    "win_rate": pm.win_rate,
                    "avg_return": pm.avg_return,
                    "total_pnl": pm.total_pnl,
                    "avg_holding_days": pm.avg_holding_days,
                }
                for pattern, pm in self.result.pattern_metrics.items()
            },
            "region_metrics": {
                region: {
                    "total_trades": rm.total_trades,
                    "win_rate": rm.win_rate,
                    "profit_factor": rm.profit_factor,
                    "total_return": rm.total_return,
                }
                for region, rm in (self.result.region_metrics or {}).items()
            },
            "execution_time_seconds": self.result.execution_time_seconds,
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, indent=2, ensure_ascii=False)

        logger.info(f"JSON export saved to: {filepath}")
        print(f"✅ JSON export saved to: {filepath}")

    def export_csv_trades(self, filepath: str):
        """
        Export trade log to CSV.

        Args:
            filepath: Path to save CSV file

        CSV Columns:
            ticker, region, entry_date, exit_date, entry_price, exit_price,
            shares, commission, slippage, pnl, pnl_pct, pattern_type,
            exit_reason, entry_score, sector, holding_period_days
        """
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        closed_trades = [t for t in self.result.trades if t.is_closed]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'ticker', 'region', 'entry_date', 'exit_date', 'entry_price', 'exit_price',
                'shares', 'commission', 'slippage', 'pnl', 'pnl_pct', 'pattern_type',
                'exit_reason', 'entry_score', 'sector', 'holding_period_days'
            ])

            # Data rows
            for trade in closed_trades:
                writer.writerow([
                    trade.ticker,
                    trade.region,
                    trade.entry_date,
                    trade.exit_date,
                    trade.entry_price,
                    trade.exit_price,
                    trade.shares,
                    trade.commission,
                    trade.slippage,
                    trade.pnl,
                    trade.pnl_pct,
                    trade.pattern_type,
                    trade.exit_reason,
                    trade.entry_score,
                    trade.sector,
                    trade.holding_period_days,
                ])

        logger.info(f"CSV trade log saved to: {filepath} ({len(closed_trades)} trades)")
        print(f"✅ CSV trade log saved to: {filepath} ({len(closed_trades)} trades)")

    def generate_html_report(self, filepath: str):
        """
        Generate HTML report with charts.

        Args:
            filepath: Path to save HTML file

        Report Sections:
            1. Executive Summary
            2. Equity Curve Chart
            3. Drawdown Chart
            4. Monthly Returns Heatmap
            5. Pattern Performance Table
            6. Trade Log Table

        Note:
            Requires matplotlib, mplfinance for chart generation.
            This is a simplified version - full implementation would include
            interactive charts using plotly or bokeh.
        """
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        # Generate HTML (simplified version without charts)
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Spock Backtest Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 5px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ecf0f1;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .metric {{
            display: inline-block;
            margin: 10px 20px;
            padding: 15px;
            background-color: #ecf0f1;
            border-radius: 5px;
        }}
        .metric-label {{
            font-weight: bold;
            color: #7f8c8d;
        }}
        .metric-value {{
            font-size: 1.5em;
            color: #2c3e50;
        }}
        .success {{
            color: #27ae60;
        }}
        .warning {{
            color: #e74c3c;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Spock Backtest Report</h1>
        <p><strong>Period:</strong> {self.result.config.start_date} to {self.result.config.end_date}</p>
        <p><strong>Regions:</strong> {', '.join(self.result.config.regions)}</p>
        <p><strong>Initial Capital:</strong> ₩{self.result.config.initial_capital:,.0f}</p>

        <h2>Performance Summary</h2>
        <div>
            <div class="metric">
                <div class="metric-label">Total Return</div>
                <div class="metric-value {'success' if self.result.metrics.total_return > 0 else 'warning'}">{self.result.metrics.total_return:+.1%}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Sharpe Ratio</div>
                <div class="metric-value {'success' if self.result.metrics.sharpe_ratio >= 1.5 else 'warning'}">{self.result.metrics.sharpe_ratio:.2f}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Max Drawdown</div>
                <div class="metric-value {'success' if abs(self.result.metrics.max_drawdown) <= 0.15 else 'warning'}">{self.result.metrics.max_drawdown:.1%}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value {'success' if self.result.metrics.win_rate >= 0.55 else 'warning'}">{self.result.metrics.win_rate:.1%}</div>
            </div>
        </div>

        <h2>Pattern Performance</h2>
        <table>
            <tr>
                <th>Pattern</th>
                <th>Trades</th>
                <th>Win Rate</th>
                <th>Avg Return</th>
                <th>Total P&L</th>
            </tr>
"""
        for pattern, pm in self.result.pattern_metrics.items():
            html += f"""
            <tr>
                <td>{pattern}</td>
                <td>{pm.total_trades}</td>
                <td>{pm.win_rate:.1%}</td>
                <td>{pm.avg_return:+.1%}</td>
                <td>₩{pm.total_pnl:,.0f}</td>
            </tr>
"""

        html += """
        </table>

        <h2>Trade Log</h2>
        <table>
            <tr>
                <th>Ticker</th>
                <th>Entry Date</th>
                <th>Exit Date</th>
                <th>Return</th>
                <th>P&L</th>
                <th>Pattern</th>
            </tr>
"""
        for trade in [t for t in self.result.trades if t.is_closed][:50]:  # Top 50 trades
            html += f"""
            <tr>
                <td>{trade.ticker}</td>
                <td>{trade.entry_date}</td>
                <td>{trade.exit_date}</td>
                <td class="{'success' if trade.pnl > 0 else 'warning'}">{trade.pnl_pct:+.1%}</td>
                <td>₩{trade.pnl:,.0f}</td>
                <td>{trade.pattern_type}</td>
            </tr>
"""

        html += f"""
        </table>

        <p><em>Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
    </div>
</body>
</html>
"""

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)

        logger.info(f"HTML report saved to: {filepath}")
        print(f"✅ HTML report saved to: {filepath}")

    def save_to_database(self, db: SQLiteDatabaseManager):
        """
        Persist results to backtest_results table.

        Args:
            db: SQLiteDatabaseManager instance

        Database Tables:
            - backtest_results: Configuration and metrics
            - backtest_trades: Trade log
            - backtest_equity_curve: Daily portfolio values

        Note:
            Config hash is used to prevent duplicate entries.
        """
        # Generate config hash for deduplication
        config_str = json.dumps({
            "start_date": str(self.result.config.start_date),
            "end_date": str(self.result.config.end_date),
            "regions": self.result.config.regions,
            "score_threshold": self.result.config.score_threshold,
            "kelly_multiplier": self.result.config.kelly_multiplier,
            "risk_profile": self.result.config.risk_profile,
        }, sort_keys=True)
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()

        conn = db._get_connection()
        cursor = conn.cursor()

        try:
            # Insert into backtest_results
            cursor.execute("""
                INSERT OR REPLACE INTO backtest_results (
                    config_hash, start_date, end_date, regions, config_json,
                    total_return, annualized_return, cagr, sharpe_ratio, sortino_ratio,
                    calmar_ratio, max_drawdown, total_trades, win_rate, profit_factor,
                    avg_win_loss_ratio, execution_time_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                config_hash,
                str(self.result.config.start_date),
                str(self.result.config.end_date),
                json.dumps(self.result.config.regions),
                json.dumps({
                    "score_threshold": self.result.config.score_threshold,
                    "kelly_multiplier": self.result.config.kelly_multiplier,
                    "max_position_size": self.result.config.max_position_size,
                    "risk_profile": self.result.config.risk_profile,
                }),
                self.result.metrics.total_return,
                self.result.metrics.annualized_return,
                self.result.metrics.cagr,
                self.result.metrics.sharpe_ratio,
                self.result.metrics.sortino_ratio,
                self.result.metrics.calmar_ratio,
                self.result.metrics.max_drawdown,
                self.result.metrics.total_trades,
                self.result.metrics.win_rate,
                self.result.metrics.profit_factor,
                self.result.metrics.avg_win_loss_ratio,
                self.result.execution_time_seconds,
            ))

            backtest_id = cursor.lastrowid

            # Insert trades
            for trade in [t for t in self.result.trades if t.is_closed]:
                cursor.execute("""
                    INSERT INTO backtest_trades (
                        backtest_id, ticker, region, entry_date, exit_date,
                        entry_price, exit_price, shares, commission, slippage,
                        pnl, pnl_pct, pattern_type, entry_score, exit_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    backtest_id, trade.ticker, trade.region, str(trade.entry_date),
                    str(trade.exit_date), trade.entry_price, trade.exit_price,
                    trade.shares, trade.commission, trade.slippage, trade.pnl,
                    trade.pnl_pct, trade.pattern_type, trade.entry_score, trade.exit_reason
                ))

            # Insert equity curve
            for date, value in self.result.equity_curve.items():
                cursor.execute("""
                    INSERT INTO backtest_equity_curve (
                        backtest_id, date, portfolio_value, cash, positions_value, daily_return
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (backtest_id, str(date), float(value), 0.0, float(value), 0.0))

            conn.commit()
            logger.info(f"Backtest results saved to database (ID: {backtest_id})")
            print(f"✅ Backtest results saved to database (ID: {backtest_id})")

            return backtest_id

        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to save backtest results to database: {e}")
            print(f"❌ Failed to save to database: {e}")
            raise
        finally:
            conn.close()
