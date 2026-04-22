"""PnL calculation utilities, decoupled from live state."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass
class TradeRecord:
    """Minimal description of a completed round-trip (buy + sell)."""

    level: int
    buy_price: float
    sell_price: float
    quantity: float
    buy_fee: float
    sell_fee: float

    @property
    def gross_profit(self) -> float:
        """Profit before fees."""
        return round((self.sell_price - self.buy_price) * self.quantity, 8)

    @property
    def net_profit(self) -> float:
        """Profit after both-side fees."""
        return round(self.gross_profit - self.buy_fee - self.sell_fee, 8)

    @property
    def profit_rate(self) -> float:
        """Net return as fraction of capital deployed."""
        capital = self.buy_price * self.quantity + self.buy_fee
        return round(self.net_profit / capital, 8) if capital > 0 else 0.0


class PnlCalculator:
    """Stateless helper for PnL and performance metrics.

    Accepts lists of TradeRecord objects and equity-curve data.
    All methods are pure functions — no internal state.
    """

    # ------------------------------------------------------------------
    # Per-trade metrics
    # ------------------------------------------------------------------

    @staticmethod
    def net_profit(trade: TradeRecord) -> float:
        """Net profit for a single completed round-trip."""
        return trade.net_profit

    @staticmethod
    def total_net_profit(trades: Sequence[TradeRecord]) -> float:
        """Sum of net profits across all round-trips."""
        return round(sum(t.net_profit for t in trades), 8)

    @staticmethod
    def total_fees(trades: Sequence[TradeRecord]) -> float:
        """Total fees paid across all round-trips."""
        return round(sum(t.buy_fee + t.sell_fee for t in trades), 8)

    @staticmethod
    def win_rate(trades: Sequence[TradeRecord]) -> float:
        """Fraction of round-trips with net_profit > 0."""
        if not trades:
            return 0.0
        winners = sum(1 for t in trades if t.net_profit > 0)
        return round(winners / len(trades), 8)

    @staticmethod
    def avg_profit_per_trade(trades: Sequence[TradeRecord]) -> float:
        """Mean net profit per round-trip."""
        if not trades:
            return 0.0
        return round(PnlCalculator.total_net_profit(trades) / len(trades), 8)

    # ------------------------------------------------------------------
    # Portfolio-level metrics from equity curve
    # ------------------------------------------------------------------

    @staticmethod
    def total_return(equity_curve: Sequence[float]) -> float:
        """(final - initial) / initial as a fraction."""
        if len(equity_curve) < 2 or equity_curve[0] == 0:
            return 0.0
        return round((equity_curve[-1] - equity_curve[0]) / equity_curve[0], 8)

    @staticmethod
    def annualized_return(equity_curve: Sequence[float], trading_days: float) -> float:
        """Compound annualized return given a number of trading days elapsed.

        Args:
            equity_curve: Portfolio value at each time step.
            trading_days: Calendar days covered by the backtest.

        Returns:
            Annualized return as a fraction (e.g. 0.15 = 15%).
        """
        if len(equity_curve) < 2 or equity_curve[0] == 0 or trading_days <= 0:
            return 0.0
        total_r = equity_curve[-1] / equity_curve[0]
        years = trading_days / 365.0
        return round(total_r ** (1.0 / years) - 1.0, 8)

    @staticmethod
    def max_drawdown(equity_curve: Sequence[float]) -> float:
        """Maximum peak-to-trough drawdown as a positive fraction.

        Returns:
            Max drawdown (e.g. 0.15 means 15% drawdown from peak).
        """
        if not equity_curve:
            return 0.0
        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
        return round(max_dd, 8)

    @staticmethod
    def sharpe_ratio(
        equity_curve: Sequence[float],
        risk_free_rate: float = 0.0,
        periods_per_year: int = 365,
    ) -> float:
        """Annualized Sharpe ratio from an equity curve.

        Args:
            equity_curve: Portfolio value at each time step.
            risk_free_rate: Annual risk-free rate (fraction).
            periods_per_year: Number of data points per year.

        Returns:
            Sharpe ratio (higher is better; NaN if std == 0).
        """
        if len(equity_curve) < 2:
            return 0.0

        returns = [
            (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
            for i in range(1, len(equity_curve))
            if equity_curve[i - 1] > 0
        ]
        if not returns:
            return 0.0

        n = len(returns)
        mean_r = sum(returns) / n
        variance = sum((r - mean_r) ** 2 for r in returns) / n
        std_r = math.sqrt(variance)

        if std_r == 0:
            return 0.0

        daily_rf = risk_free_rate / periods_per_year
        sharpe = (mean_r - daily_rf) / std_r * math.sqrt(periods_per_year)
        return round(sharpe, 4)

    @staticmethod
    def calmar_ratio(equity_curve: Sequence[float], trading_days: float) -> float:
        """Annualized return divided by max drawdown.

        Returns 0.0 if max drawdown is zero (risk-free scenario).
        """
        ann_r = PnlCalculator.annualized_return(equity_curve, trading_days)
        mdd = PnlCalculator.max_drawdown(equity_curve)
        if mdd == 0:
            return 0.0
        return round(ann_r / mdd, 4)

    @staticmethod
    def profit_factor(trades: Sequence[TradeRecord]) -> float:
        """Gross profit / gross loss.  > 1 is profitable."""
        gross_profit = sum(t.net_profit for t in trades if t.net_profit > 0)
        gross_loss = abs(sum(t.net_profit for t in trades if t.net_profit < 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return round(gross_profit / gross_loss, 4)


if __name__ == "__main__":
    # Quick sanity check
    trades = [
        TradeRecord(level=1, buy_price=40000, sell_price=42000,
                    quantity=0.025, buy_fee=1.0, sell_fee=1.05),
        TradeRecord(level=2, buy_price=42000, sell_price=44000,
                    quantity=0.024, buy_fee=1.008, sell_fee=1.056),
        TradeRecord(level=3, buy_price=44000, sell_price=43000,
                    quantity=0.023, buy_fee=1.012, sell_fee=0.989),  # loss
    ]

    calc = PnlCalculator()
    print(f"Total net profit : {calc.total_net_profit(trades):.4f}")
    print(f"Win rate         : {calc.win_rate(trades):.2%}")
    print(f"Avg profit/trade : {calc.avg_profit_per_trade(trades):.4f}")
    print(f"Total fees       : {calc.total_fees(trades):.4f}")
    print(f"Profit factor    : {calc.profit_factor(trades):.4f}")

    equity = [10000, 10050, 10120, 10080, 10200, 10350, 10300, 10500]
    print(f"Total return     : {calc.total_return(equity):.2%}")
    print(f"Max drawdown     : {calc.max_drawdown(equity):.2%}")
    print(f"Sharpe ratio     : {calc.sharpe_ratio(equity):.4f}")
    print(f"Annualized return: {calc.annualized_return(equity, 30):.2%}")
