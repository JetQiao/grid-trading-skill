"""Order placement, tracking, and lifecycle management."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class OrderStatus(Enum):
    """Lifecycle states of a grid order."""

    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"


@dataclass
class Order:
    """A single grid order with full lifecycle metadata."""

    order_id: str
    level: int
    side: Literal["buy", "sell"]
    price: float
    quantity: float
    status: OrderStatus = OrderStatus.PENDING
    created_at: float = field(default_factory=time.time)
    filled_at: float | None = None
    fill_price: float | None = None  # actual execution price (may differ from limit)

    def __repr__(self) -> str:
        return (
            f"Order(id={self.order_id[:8]}, level={self.level}, "
            f"side={self.side}, price={self.price}, qty={self.quantity}, "
            f"status={self.status.value})"
        )


class OrderManager:
    """Manages grid order lifecycle: placement, fills, cancellations.

    Idempotency rule: only one PENDING order per (level, side) at a time.
    The strategy layer is responsible for placing the counter-side order
    after a fill event.
    """

    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}
        # Maps (level, side) -> order_id for quick pending-order lookup
        self._pending_index: dict[tuple[int, str], str] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def place_order(
        self,
        level: int,
        side: Literal["buy", "sell"],
        price: float,
        qty: float,
    ) -> Order:
        """Create a new PENDING order.

        Args:
            level: Grid level number.
            side: "buy" or "sell".
            price: Limit price for the order.
            qty: Order quantity.

        Returns:
            The newly created Order.

        Raises:
            ValueError: If a PENDING order for this (level, side) already exists.
        """
        key = (level, side)
        if key in self._pending_index:
            existing_id = self._pending_index[key]
            raise ValueError(
                f"PENDING {side} order already exists at level {level} "
                f"(id={existing_id[:8]}). Cancel it before placing a new one."
            )
        if price <= 0:
            raise ValueError(f"Order price must be positive, got {price}.")
        if qty <= 0:
            raise ValueError(f"Order quantity must be positive, got {qty}.")

        order = Order(
            order_id=str(uuid.uuid4()),
            level=level,
            side=side,
            price=round(price, 8),
            quantity=round(qty, 8),
        )
        self._orders[order.order_id] = order
        self._pending_index[key] = order.order_id
        return order

    def fill_order(
        self,
        order_id: str,
        fill_price: float,
        timestamp: float,
    ) -> Order:
        """Mark an order as FILLED.

        Args:
            order_id: The order to fill.
            fill_price: Actual execution price.
            timestamp: UNIX timestamp of the fill event.

        Returns:
            The updated Order.

        Raises:
            KeyError: If order_id is not found.
            ValueError: If the order is not in PENDING status.
        """
        order = self._get_or_raise(order_id)
        if order.status != OrderStatus.PENDING:
            raise ValueError(
                f"Cannot fill order {order_id[:8]}: status is {order.status.value}."
            )
        order.status = OrderStatus.FILLED
        order.fill_price = round(fill_price, 8)
        order.filled_at = timestamp
        self._pending_index.pop((order.level, order.side), None)
        return order

    def cancel_order(self, order_id: str) -> Order:
        """Cancel a PENDING order.

        Args:
            order_id: The order to cancel.

        Returns:
            The updated Order.

        Raises:
            KeyError: If order_id is not found.
            ValueError: If the order is not in PENDING status.
        """
        order = self._get_or_raise(order_id)
        if order.status != OrderStatus.PENDING:
            raise ValueError(
                f"Cannot cancel order {order_id[:8]}: status is {order.status.value}."
            )
        order.status = OrderStatus.CANCELLED
        self._pending_index.pop((order.level, order.side), None)
        return order

    def cancel_all_pending(self) -> list[Order]:
        """Cancel every currently PENDING order.

        Returns:
            List of cancelled orders.
        """
        cancelled: list[Order] = []
        for order_id in list(self._pending_index.values()):
            cancelled.append(self.cancel_order(order_id))
        return cancelled

    def get_pending_orders(self) -> list[Order]:
        """Return all orders currently in PENDING status."""
        return [
            self._orders[oid]
            for oid in self._pending_index.values()
        ]

    def get_orders_by_level(self, level: int) -> list[Order]:
        """Return all orders (any status) associated with a grid level.

        Args:
            level: Grid level number to query.

        Returns:
            List of orders for that level, chronological by creation time.
        """
        return sorted(
            [o for o in self._orders.values() if o.level == level],
            key=lambda o: o.created_at,
        )

    def get_pending_buy_orders(self) -> list[Order]:
        """Return all PENDING buy orders sorted by price descending."""
        return sorted(
            [o for o in self.get_pending_orders() if o.side == "buy"],
            key=lambda o: o.price,
            reverse=True,
        )

    def get_pending_sell_orders(self) -> list[Order]:
        """Return all PENDING sell orders sorted by price ascending."""
        return sorted(
            [o for o in self.get_pending_orders() if o.side == "sell"],
            key=lambda o: o.price,
        )

    def has_pending(self, level: int, side: Literal["buy", "sell"]) -> bool:
        """Return True if a PENDING order exists for this (level, side)."""
        return (level, side) in self._pending_index

    def get_order(self, order_id: str) -> Order | None:
        """Return an order by ID, or None if not found."""
        return self._orders.get(order_id)

    def all_orders(self) -> list[Order]:
        """Return all orders regardless of status."""
        return list(self._orders.values())

    def stats(self) -> dict:
        """Return aggregate counts by status."""
        from collections import Counter
        counts = Counter(o.status.value for o in self._orders.values())
        return dict(counts)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_or_raise(self, order_id: str) -> Order:
        order = self._orders.get(order_id)
        if order is None:
            raise KeyError(f"Order {order_id} not found.")
        return order


if __name__ == "__main__":
    import time as _time

    mgr = OrderManager()

    # Place initial buy orders
    o1 = mgr.place_order(level=1, side="buy", price=40000.0, qty=0.025)
    o2 = mgr.place_order(level=2, side="buy", price=42000.0, qty=0.0238)
    o3 = mgr.place_order(level=1, side="sell", price=42000.0, qty=0.025)

    print(f"Pending orders: {len(mgr.get_pending_orders())}")

    # Try duplicate — should raise
    try:
        mgr.place_order(level=1, side="buy", price=40000.0, qty=0.025)
    except ValueError as e:
        print(f"Idempotency guard: {e}")

    # Fill o1 — triggers counter-side placement in strategy layer
    filled = mgr.fill_order(o1.order_id, fill_price=39950.0, timestamp=_time.time())
    print(f"Filled: {filled}")

    # Now we can place a new buy at level 1 again
    o1b = mgr.place_order(level=1, side="buy", price=40000.0, qty=0.025)
    print(f"Re-placed buy at level 1: {o1b.order_id[:8]}")

    print(f"Stats: {mgr.stats()}")
    print(f"Level 1 orders: {mgr.get_orders_by_level(1)}")
