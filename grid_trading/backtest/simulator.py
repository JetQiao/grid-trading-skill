"""Backtest engine: feeds a price series into a GridStrategy and collects results."""

from __future__ import annotations

from dataclasses import dataclass, field

from grid_trading.backtest import metrics as m
from grid_trading.risk.risk_checker import RiskAlert, RiskChecker
from grid_trading.strategy.grid_strategy import GridConfig, GridStrategy


@dataclass
class BacktestResult:
    """Aggregated result of a completed backtest run."""

    total_return: float           # 总收益率（小数）
    annualized_return: float      # 年化收益率（小数）
    max_drawdown: float           # 最大回撤（正小数）
    sharpe_ratio: float           # 夏普比率
    total_trades: int             # 总成交次数（买+卖）
    win_rate: float               # 盈利卖出占比
    avg_profit_per_trade: float   # 平均每笔卖出利润
    fee_total: float              # 累计手续费
    equity_curve: list[float]     # 每个 tick 的净值
    trade_log: list[dict]         # 完整交易明细
    risk_alerts: list[RiskAlert]  # 触发的风控告警列表
    trading_days: float           # 回测天数


class BacktestSimulator:
    """Feed a price series through a GridStrategy and produce BacktestResult.

    Usage::

        config = GridConfig(...)
        strategy = GridStrategy(config)
        simulator = BacktestSimulator(strategy)
        result = simulator.run(price_series)
    """

    def __init__(self, strategy: GridStrategy) -> None:
        """
        Args:
            strategy: A freshly created (not yet initialized) GridStrategy.
        """
        self._strategy = strategy
        self._risk_checker = RiskChecker()

    def run(
        self,
        price_series: list[tuple[float, float]],
    ) -> BacktestResult:
        """Execute the backtest over ``price_series``.

        Args:
            price_series: List of (timestamp, price) tuples in chronological
                order.  At least two data points are required.

        Returns:
            A BacktestResult containing metrics, equity curve, and trade log.

        Raises:
            ValueError: If price_series has fewer than 2 points.
        """
        if len(price_series) < 2:
            raise ValueError("price_series must contain at least 2 data points.")

        start_ts, start_price = price_series[0]
        end_ts = price_series[-1][0]
        trading_days = (end_ts - start_ts) / 86400.0 if end_ts > start_ts else 1.0

        # Initialize strategy at the first price
        self._strategy.initialize(current_price=start_price)

        equity_curve: list[float] = []
        enriched_log: list[dict] = []
        risk_alerts: list[RiskAlert] = []
        cfg = self._strategy.config

        for ts, price in price_series:
            # Risk check before processing tick
            snap = self._strategy._position.snapshot()
            alert = self._risk_checker.check_on_price_update(price, snap, cfg)
            if alert is not None:
                risk_alerts.append(alert)

            # Drive the strategy
            filled = self._strategy.on_price_update(price, ts)

            # Enrich trade log entries with per-trade pnl
            for order in filled:
                if order.side == "sell":
                    pos_snap = self._strategy._position.snapshot()
                    # pnl for this sell = net realized delta since last snapshot
                    # approximation: (sell_price - avg_cost_at_buy) * qty - fees
                    buy_cost = self._strategy._position._avg_cost  # avg cost before sell
                    fee = order.price * order.quantity * cfg.fee_rate
                    pnl = round(
                        (order.price - buy_cost) * order.quantity - fee * 2, 8
                    )
                    enriched_log.append({
                        "timestamp": ts,
                        "level": order.level,
                        "side": order.side,
                        "price": order.price,
                        "quantity": order.quantity,
                        "fee": fee,
                        "pnl": pnl,
                        "order_id": order.order_id,
                    })
                else:
                    fee = order.price * order.quantity * cfg.fee_rate
                    enriched_log.append({
                        "timestamp": ts,
                        "level": order.level,
                        "side": order.side,
                        "price": order.price,
                        "quantity": order.quantity,
                        "fee": fee,
                        "pnl": 0.0,
                        "order_id": order.order_id,
                    })

            # Record equity at this tick
            equity_curve.append(self._strategy._position.equity())

        # Collect final position metrics
        final_snap = self._strategy._position.snapshot()

        return BacktestResult(
            total_return=m.total_return(equity_curve),
            annualized_return=m.annualized_return(equity_curve, trading_days),
            max_drawdown=m.max_drawdown(equity_curve),
            sharpe_ratio=m.sharpe_ratio(equity_curve),
            total_trades=final_snap.total_trades,
            win_rate=m.win_rate(enriched_log),
            avg_profit_per_trade=m.avg_profit_per_trade(enriched_log),
            fee_total=round(final_snap.fee_paid, 8),
            equity_curve=equity_curve,
            trade_log=enriched_log,
            risk_alerts=risk_alerts,
            trading_days=round(trading_days, 2),
        )

    def print_report(self, result: BacktestResult) -> None:
        """Print a formatted summary of a BacktestResult."""
        print("=" * 55)
        print(f"  Backtest Report — {self._strategy.config.symbol}")
        print("=" * 55)
        print(f"  Trading days        : {result.trading_days:.1f}")
        print(f"  Total return        : {result.total_return:.2%}")
        print(f"  Annualized return   : {result.annualized_return:.2%}")
        print(f"  Max drawdown        : {result.max_drawdown:.2%}")
        print(f"  Sharpe ratio        : {result.sharpe_ratio:.4f}")
        print(f"  Total trades        : {result.total_trades}")
        print(f"  Win rate            : {result.win_rate:.2%}")
        print(f"  Avg profit/trade    : {result.avg_profit_per_trade:.4f}")
        print(f"  Total fees paid     : {result.fee_total:.4f}")
        print(f"  Risk alerts fired   : {len(result.risk_alerts)}")
        criticals = [a for a in result.risk_alerts if a.level == "critical"]
        if criticals:
            print(f"  Critical alerts     : {len(criticals)}")
            for a in criticals[:3]:
                print(f"    [{a.type}] {a.message[:60]}")
        print("=" * 55)


if __name__ == "__main__":
    from grid_trading.tests.mock_data import sine_wave, trending_down

    print("\n--- Sine wave (ideal grid market) ---")
    cfg = GridConfig(
        symbol="BTC/USDT",
        grid_type="arithmetic",
        price_lower=44000,
        price_upper=56000,
        grid_count=12,
        total_capital=10000,
        fee_rate=0.001,
    )
    sim = BacktestSimulator(GridStrategy(cfg))
    result = sim.run(sine_wave(base_price=50000, amplitude=5000, periods=5, points=500))
    sim.print_report(result)

    print("\n--- Trending down (worst case) ---")
    cfg2 = GridConfig(
        symbol="BTC/USDT",
        grid_type="arithmetic",
        price_lower=36000,
        price_upper=58000,
        grid_count=10,
        total_capital=10000,
        fee_rate=0.001,
    )
    sim2 = BacktestSimulator(GridStrategy(cfg2))
    result2 = sim2.run(trending_down(start_price=55000, end_price=38000, points=500))
    sim2.print_report(result2)
