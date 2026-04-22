"""Main grid trading strategy — wires all core modules together."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from grid_trading.core.grid_builder import GridBuilder, GridLevel
from grid_trading.core.order_manager import Order, OrderManager
from grid_trading.core.position_tracker import PositionTracker
from grid_trading.strategy.rebalance import GridRebalancer


@dataclass
class GridConfig:
    """All parameters required to run a grid strategy."""

    symbol: str
    grid_type: Literal["arithmetic", "geometric"]
    price_lower: float
    price_upper: float
    grid_count: int
    total_capital: float
    fee_rate: float = 0.001
    stop_loss_price: float | None = None
    take_profit_price: float | None = None

    def __post_init__(self) -> None:
        if self.price_lower <= 0 or self.price_upper <= self.price_lower:
            raise ValueError("price_lower must be > 0 and < price_upper.")
        if self.grid_count < 2:
            raise ValueError("grid_count must be >= 2.")
        if self.total_capital <= 0:
            raise ValueError("total_capital must be positive.")
        if not 0 <= self.fee_rate < 1:
            raise ValueError("fee_rate must be in [0, 1).")


class GridStrategy:
    """Stateful grid trading strategy.

    Lifecycle:
        1. ``__init__`` — validate config and wire up sub-modules.
        2. ``initialize(current_price)`` — build grids, place initial orders.
        3. ``on_price_update(price, timestamp)`` — call on every tick;
           returns list of orders filled in that tick.
        4. ``get_status()`` — inspect current state at any time.
    """

    def __init__(self, config: GridConfig) -> None:
        """
        Args:
            config: Validated GridConfig dataclass.
        """
        self.config = config
        self._builder = GridBuilder(fee_rate=config.fee_rate)
        self._order_mgr = OrderManager()
        self._position = PositionTracker(total_capital=config.total_capital)
        self._rebalancer = GridRebalancer()

        self._grids: list[GridLevel] = []
        self._initialized = False
        self._stopped = False          # True after stop-loss / take-profit fires
        self._stop_reason: str = ""
        self._current_price: float = 0.0
        self._tick_count: int = 0
        self._trade_log: list[dict] = []

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self, current_price: float) -> None:
        """Build the grid and place initial orders around current_price.

        Buy orders are placed at every level below current_price.
        Sell orders are placed at every level above current_price.
        Levels that straddle current_price get both a buy at their
        buy_price and a sell at their sell_price.

        Args:
            current_price: The market price at strategy launch.
        """
        if self._initialized:
            raise RuntimeError("Strategy already initialized. Call reset() first.")

        cfg = self.config
        if cfg.grid_type == "arithmetic":
            self._grids = self._builder.build_arithmetic(
                cfg.price_lower, cfg.price_upper, cfg.grid_count, cfg.total_capital
            )
        else:
            self._grids = self._builder.build_geometric(
                cfg.price_lower, cfg.price_upper, cfg.grid_count, cfg.total_capital
            )

        self._current_price = current_price
        self._position.update_market_price(current_price)
        self._place_initial_orders(current_price)
        self._initialized = True

    def _place_initial_orders(self, price: float) -> None:
        """Place buy orders below price and sell orders above price."""
        for grid in self._grids:
            if grid.buy_price < price:
                # Price is above this level — place buy order
                self._order_mgr.place_order(
                    level=grid.level,
                    side="buy",
                    price=grid.buy_price,
                    qty=grid.quantity,
                )
            if grid.sell_price > price:
                # Price is below this level's sell — place sell order
                # (only if we don't already have a pending sell here)
                if not self._order_mgr.has_pending(grid.level, "sell"):
                    self._order_mgr.place_order(
                        level=grid.level,
                        side="sell",
                        price=grid.sell_price,
                        qty=grid.quantity,
                    )

    # ------------------------------------------------------------------
    # Core tick driver
    # ------------------------------------------------------------------

    def on_price_update(self, price: float, timestamp: float) -> list[Order]:
        """Process one price tick and return any orders filled this tick.

        Internal flow:
            1. Update market price in position tracker.
            2. Scan PENDING buy orders — fill if price <= buy_price.
            3. Scan PENDING sell orders — fill if price >= sell_price.
            4. For each fill, place the counter-side order.
            5. Evaluate stop-loss / take-profit conditions.

        Args:
            price: Current market price.
            timestamp: UNIX timestamp for this tick.

        Returns:
            List of Order objects that were filled during this tick.
        """
        if not self._initialized:
            raise RuntimeError("Call initialize() before on_price_update().")
        if self._stopped:
            return []

        self._current_price = price
        self._position.update_market_price(price)
        self._tick_count += 1
        filled_orders: list[Order] = []

        # --- Check buy orders (price dropped to or below buy_price) ---
        for order in self._order_mgr.get_pending_buy_orders():
            if price <= order.price:
                fee = round(order.price * order.quantity * self.config.fee_rate, 8)
                try:
                    filled = self._order_mgr.fill_order(
                        order.order_id, fill_price=order.price, timestamp=timestamp
                    )
                    self._position.on_buy_filled(
                        price=order.price, qty=order.quantity, fee=fee
                    )
                    filled_orders.append(filled)
                    self._log_trade(filled, fee, timestamp)
                    # Counter-side: place sell at this level's sell_price
                    self._place_counter_sell(filled)
                except (ValueError, KeyError):
                    pass

        # --- Check sell orders (price rose to or above sell_price) ---
        for order in self._order_mgr.get_pending_sell_orders():
            if price >= order.price:
                fee = round(order.price * order.quantity * self.config.fee_rate, 8)
                try:
                    filled = self._order_mgr.fill_order(
                        order.order_id, fill_price=order.price, timestamp=timestamp
                    )
                    self._position.on_sell_filled(
                        price=order.price, qty=order.quantity, fee=fee
                    )
                    filled_orders.append(filled)
                    self._log_trade(filled, fee, timestamp)
                    # Counter-side: place buy at this level's buy_price
                    self._place_counter_buy(filled)
                except (ValueError, KeyError):
                    pass

        # --- Risk gates ---
        self._check_stop_conditions(price, timestamp)

        return filled_orders

    # ------------------------------------------------------------------
    # Counter-order placement
    # ------------------------------------------------------------------

    def _place_counter_sell(self, buy_order: Order) -> None:
        """After a buy fill, place the matching sell at this level's sell_price."""
        grid = self._grid_by_level(buy_order.level)
        if grid is None:
            return
        if not self._order_mgr.has_pending(grid.level, "sell"):
            try:
                self._order_mgr.place_order(
                    level=grid.level,
                    side="sell",
                    price=grid.sell_price,
                    qty=grid.quantity,
                )
            except ValueError:
                pass

    def _place_counter_buy(self, sell_order: Order) -> None:
        """After a sell fill, place the matching buy at this level's buy_price."""
        grid = self._grid_by_level(sell_order.level)
        if grid is None:
            return
        if not self._order_mgr.has_pending(grid.level, "buy"):
            try:
                self._order_mgr.place_order(
                    level=grid.level,
                    side="buy",
                    price=grid.buy_price,
                    qty=grid.quantity,
                )
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Stop conditions
    # ------------------------------------------------------------------

    def _check_stop_conditions(self, price: float, timestamp: float) -> None:
        cfg = self.config
        if cfg.stop_loss_price is not None and price <= cfg.stop_loss_price:
            self._halt("stop_loss", price, timestamp)
        elif cfg.take_profit_price is not None and price >= cfg.take_profit_price:
            self._halt("take_profit", price, timestamp)

    def _halt(self, reason: str, price: float, timestamp: float) -> None:
        """Cancel all orders and mark the strategy as stopped."""
        self._order_mgr.cancel_all_pending()
        self._stopped = True
        self._stop_reason = reason

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return a full snapshot of strategy state.

        Returns:
            Dict with keys: symbol, initialized, stopped, stop_reason,
            current_price, tick_count, pending_orders, position, grid_summary.
        """
        snap = self._position.snapshot()
        pending = self._order_mgr.get_pending_orders()
        order_stats = self._order_mgr.stats()

        return {
            "symbol": self.config.symbol,
            "initialized": self._initialized,
            "stopped": self._stopped,
            "stop_reason": self._stop_reason,
            "current_price": self._current_price,
            "tick_count": self._tick_count,
            "pending_buy_count": sum(1 for o in pending if o.side == "buy"),
            "pending_sell_count": sum(1 for o in pending if o.side == "sell"),
            "order_stats": order_stats,
            "position": {
                "holdings": snap.holdings,
                "avg_cost": snap.avg_cost,
                "available_capital": snap.available_capital,
                "unrealized_pnl": snap.unrealized_pnl,
                "realized_pnl": snap.realized_pnl,
                "total_trades": snap.total_trades,
                "fee_paid": snap.fee_paid,
            },
            "equity": self._position.equity(),
            "grid_count": len(self._grids),
            "trade_log_count": len(self._trade_log),
        }

    def trade_log(self) -> list[dict]:
        """Return the full trade log."""
        return list(self._trade_log)

    def equity_curve(self) -> list[float]:
        """Return equity value after each fill event."""
        return [self._position.equity()] if not self._position.history() else [
            # Recompute equity from each historical snapshot
            snap.available_capital + snap.holdings * snap.market_price
            for snap in self._position.history()
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _grid_by_level(self, level: int) -> GridLevel | None:
        for g in self._grids:
            if g.level == level:
                return g
        return None

    def _log_trade(self, order: Order, fee: float, timestamp: float) -> None:
        self._trade_log.append({
            "timestamp": timestamp,
            "level": order.level,
            "side": order.side,
            "price": order.price,
            "quantity": order.quantity,
            "fee": fee,
            "order_id": order.order_id,
        })


if __name__ == "__main__":
    config = GridConfig(
        symbol="BTC/USDT",
        grid_type="arithmetic",
        price_lower=40000,
        price_upper=60000,
        grid_count=10,
        total_capital=10000,
        fee_rate=0.001,
    )
    strategy = GridStrategy(config)
    strategy.initialize(current_price=50000)

    status = strategy.get_status()
    print(f"Initialized | pending_buy={status['pending_buy_count']} "
          f"pending_sell={status['pending_sell_count']}")

    # Simulate price dropping through two buy levels
    import time as _time
    ts = _time.time()
    for price in [49000, 47000, 45000, 43000, 47000, 51000, 55000]:
        fills = strategy.on_price_update(price, ts)
        ts += 60
        if fills:
            print(f"  price={price} -> filled {len(fills)} order(s): "
                  f"{[f'{o.side}@{o.price}' for o in fills]}")

    final = strategy.get_status()
    print(f"\nFinal status:")
    print(f"  realized_pnl  = {final['position']['realized_pnl']:.4f}")
    print(f"  unrealized_pnl= {final['position']['unrealized_pnl']:.4f}")
    print(f"  equity        = {final['equity']:.2f}")
    print(f"  total_trades  = {final['position']['total_trades']}")
