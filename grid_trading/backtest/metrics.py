"""Backtest performance metric helpers."""

from __future__ import annotations

import math
from typing import Sequence


def total_return(equity_curve: Sequence[float]) -> float:
    """(final - initial) / initial."""
    if len(equity_curve) < 2 or equity_curve[0] == 0:
        return 0.0
    return round((equity_curve[-1] - equity_curve[0]) / equity_curve[0], 8)


def annualized_return(equity_curve: Sequence[float], trading_days: float) -> float:
    """Compound annualized return given elapsed calendar days."""
    if len(equity_curve) < 2 or equity_curve[0] == 0 or trading_days <= 0:
        return 0.0
    ratio = equity_curve[-1] / equity_curve[0]
    years = trading_days / 365.0
    return round(ratio ** (1.0 / years) - 1.0, 8)


def max_drawdown(equity_curve: Sequence[float]) -> float:
    """Maximum peak-to-trough drawdown as a positive fraction."""
    if not equity_curve:
        return 0.0
    peak = equity_curve[0]
    mdd = 0.0
    for val in equity_curve:
        if val > peak:
            peak = val
        dd = (peak - val) / peak if peak > 0 else 0.0
        if dd > mdd:
            mdd = dd
    return round(mdd, 8)


def sharpe_ratio(
    equity_curve: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
) -> float:
    """Annualized Sharpe ratio from an equity curve."""
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
    return round((mean_r - daily_rf) / std_r * math.sqrt(periods_per_year), 4)


def win_rate(trade_log: list[dict]) -> float:
    """Fraction of sell trades where net proceeds > cost basis."""
    sells = [t for t in trade_log if t["side"] == "sell"]
    if not sells:
        return 0.0
    # A sell is a 'win' when the price > avg_cost recorded in the log
    winners = sum(1 for t in sells if t.get("pnl", 0) > 0)
    return round(winners / len(sells), 8)


def avg_profit_per_trade(trade_log: list[dict]) -> float:
    """Mean pnl per sell trade."""
    sells = [t for t in trade_log if t["side"] == "sell"]
    if not sells:
        return 0.0
    return round(sum(t.get("pnl", 0) for t in sells) / len(sells), 8)
