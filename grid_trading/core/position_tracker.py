"""Holdings and capital state tracking for grid strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Position:
    """Immutable snapshot of account state at a point in time."""

    total_capital: float       # 总资金（初始投入，不变）
    used_capital: float        # 已买入消耗的资金（持仓成本）
    available_capital: float   # 可用资金（未入场）
    holdings: float            # 当前持仓数量（币数量）
    avg_cost: float            # 平均持仓成本（每币）
    unrealized_pnl: float      # 浮动盈亏（按最新市价）
    realized_pnl: float        # 已实现盈亏（含手续费扣除）
    total_trades: int          # 总成交次数（买+卖）
    fee_paid: float            # 累计手续费
    market_price: float        # 快照时的市价


class PositionTracker:
    """Tracks capital, holdings, and PnL as orders are filled.

    All state mutates in place; call ``snapshot()`` to get a frozen copy.
    ``history()`` returns every post-fill snapshot for equity-curve plotting.
    """

    def __init__(self, total_capital: float) -> None:
        """
        Args:
            total_capital: Starting capital (USDT / quote currency).
        """
        if total_capital <= 0:
            raise ValueError("total_capital must be positive.")
        self._total_capital = total_capital
        self._available_capital = total_capital
        self._holdings = 0.0
        self._avg_cost = 0.0
        self._realized_pnl = 0.0
        self._fee_paid = 0.0
        self._total_trades = 0
        self._market_price = 0.0
        self._history: List[Position] = []

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_buy_filled(self, price: float, qty: float, fee: float) -> None:
        """Update state after a buy fill.

        Args:
            price: Execution price.
            qty: Quantity purchased.
            fee: Fee charged for this trade (in quote currency).
        """
        cost = price * qty
        if cost + fee > self._available_capital + 1e-9:
            raise ValueError(
                f"Insufficient capital: need {cost + fee:.4f}, "
                f"have {self._available_capital:.4f}."
            )

        # Weighted average cost — fee absorbed into cost basis
        total_prev_cost = self._avg_cost * self._holdings
        self._holdings = round(self._holdings + qty, 8)
        self._avg_cost = (
            round((total_prev_cost + cost + fee) / self._holdings, 8)
            if self._holdings > 0
            else 0.0
        )
        self._available_capital = round(self._available_capital - cost - fee, 8)
        self._fee_paid = round(self._fee_paid + fee, 8)
        self._total_trades += 1
        self._record_snapshot()

    def on_sell_filled(self, price: float, qty: float, fee: float) -> None:
        """Update state after a sell fill.

        Args:
            price: Execution price.
            qty: Quantity sold.
            fee: Fee charged for this trade (in quote currency).
        """
        if qty > self._holdings + 1e-9:
            raise ValueError(
                f"Cannot sell {qty} — only {self._holdings} held."
            )

        proceeds = price * qty
        # Realized PnL = proceeds - cost_basis - fees
        cost_basis = self._avg_cost * qty
        trade_pnl = proceeds - cost_basis - fee

        self._holdings = round(max(0.0, self._holdings - qty), 8)
        self._realized_pnl = round(self._realized_pnl + trade_pnl, 8)
        self._available_capital = round(self._available_capital + proceeds - fee, 8)
        self._fee_paid = round(self._fee_paid + fee, 8)
        self._total_trades += 1

        # avg_cost stays the same when selling (FIFO/avg-cost invariant)
        if self._holdings == 0.0:
            self._avg_cost = 0.0

        self._record_snapshot()

    def update_market_price(self, price: float) -> None:
        """Refresh the current market price for unrealized PnL calculation.

        Does NOT append a history snapshot (only fills do that).
        """
        self._market_price = price

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def snapshot(self) -> Position:
        """Return a frozen Position reflecting the current state."""
        unrealized = round(
            (self._market_price - self._avg_cost) * self._holdings, 8
        ) if self._holdings > 0 and self._market_price > 0 else 0.0

        used = round(self._avg_cost * self._holdings, 8)

        return Position(
            total_capital=self._total_capital,
            used_capital=used,
            available_capital=self._available_capital,
            holdings=self._holdings,
            avg_cost=self._avg_cost,
            unrealized_pnl=unrealized,
            realized_pnl=self._realized_pnl,
            total_trades=self._total_trades,
            fee_paid=self._fee_paid,
            market_price=self._market_price,
        )

    def history(self) -> list[Position]:
        """Return all post-fill snapshots in chronological order."""
        return list(self._history)

    def equity(self) -> float:
        """Current total equity = available + market_value_of_holdings."""
        market_value = self._holdings * self._market_price if self._market_price > 0 else 0.0
        return round(self._available_capital + market_value, 8)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _record_snapshot(self) -> None:
        self._history.append(self.snapshot())


if __name__ == "__main__":
    tracker = PositionTracker(total_capital=10000.0)
    tracker.update_market_price(50000.0)

    # Buy 0.1 BTC at 50000, fee = 5
    tracker.on_buy_filled(price=50000.0, qty=0.1, fee=5.0)
    snap = tracker.snapshot()
    print(f"After buy : holdings={snap.holdings}, avg_cost={snap.avg_cost}, "
          f"available={snap.available_capital:.2f}, unrealized={snap.unrealized_pnl}")

    # Price moves up
    tracker.update_market_price(52000.0)
    snap = tracker.snapshot()
    print(f"Price 52k : unrealized={snap.unrealized_pnl:.2f}")

    # Sell 0.1 BTC at 52000, fee = 5.2
    tracker.on_sell_filled(price=52000.0, qty=0.1, fee=5.2)
    snap = tracker.snapshot()
    print(f"After sell: realized_pnl={snap.realized_pnl:.2f}, "
          f"available={snap.available_capital:.2f}, total_trades={snap.total_trades}")

    print(f"Equity: {tracker.equity():.2f}")
    print(f"History snapshots: {len(tracker.history())}")
