"""Grid rebalance (reset) logic — rebuilds orders when price exits the range."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from grid_trading.core.grid_builder import GridLevel
    from grid_trading.core.order_manager import OrderManager
    from grid_trading.core.position_tracker import PositionTracker


class GridRebalancer:
    """Decides whether a rebalance is needed and executes the order rebuild.

    A rebalance cancels all pending orders and re-places buy orders below
    the current price and a sell order above it, anchored to the new price.
    The strategy delegates to this class; it does not modify PositionTracker
    state (actual fills stay in the strategy's on_price_update loop).
    """

    def __init__(self, rebalance_threshold: float = 0.0) -> None:
        """
        Args:
            rebalance_threshold: Fractional distance outside range that
                triggers a rebalance.  0.0 means trigger immediately when
                price leaves [lower, upper].
        """
        self.rebalance_threshold = rebalance_threshold
        self.rebalance_count = 0

    def should_rebalance(
        self,
        price: float,
        lower: float,
        upper: float,
    ) -> bool:
        """Return True if price has moved outside the grid range + threshold."""
        margin = (upper - lower) * self.rebalance_threshold
        return price < lower - margin or price > upper + margin

    def rebalance(
        self,
        current_price: float,
        grids: list[GridLevel],
        order_manager: OrderManager,
    ) -> int:
        """Cancel all pending orders and re-place the initial grid around current_price.

        Buy orders are placed at all levels whose buy_price < current_price.
        A single sell order is placed at the first level whose sell_price > current_price.

        Args:
            current_price: Latest market price.
            grids: Full list of GridLevel objects.
            order_manager: Shared order manager instance.

        Returns:
            Number of new orders placed.
        """
        order_manager.cancel_all_pending()
        placed = 0

        for grid in grids:
            if grid.buy_price < current_price:
                try:
                    order_manager.place_order(
                        level=grid.level,
                        side="buy",
                        price=grid.buy_price,
                        qty=grid.quantity,
                    )
                    placed += 1
                except ValueError:
                    pass  # already pending (shouldn't happen after cancel_all)
            elif grid.sell_price > current_price and not order_manager.has_pending(
                grid.level, "sell"
            ):
                # Only place one sell order just above current price
                try:
                    order_manager.place_order(
                        level=grid.level,
                        side="sell",
                        price=grid.sell_price,
                        qty=grid.quantity,
                    )
                    placed += 1
                    break
                except ValueError:
                    pass

        self.rebalance_count += 1
        return placed
