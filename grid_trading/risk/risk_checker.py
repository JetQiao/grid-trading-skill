"""Risk rules evaluated before order placement and on every price tick."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from grid_trading.core.order_manager import Order
    from grid_trading.core.position_tracker import Position
    from grid_trading.strategy.grid_strategy import GridConfig


@dataclass
class RiskAlert:
    """A risk event raised by RiskChecker."""

    level: Literal["warning", "critical"]
    type: Literal[
        "below_lower",
        "above_upper",
        "capital_low",
        "drawdown_limit",
        "stop_loss_breach",
        "take_profit_reached",
    ]
    message: str
    suggested_action: str


class RiskChecker:
    """Stateless risk evaluator.

    Two entry points:
    - ``check_before_order`` — called before placing any order.
    - ``check_on_price_update`` — called on every tick; may return a RiskAlert.
    """

    # Fraction of total_capital below which capital is considered "low"
    CAPITAL_LOW_THRESHOLD = 0.10

    # Unrealized loss fraction that triggers a critical alert
    DRAWDOWN_CRITICAL_THRESHOLD = 0.20

    # ------------------------------------------------------------------
    # Pre-order gate
    # ------------------------------------------------------------------

    def check_before_order(
        self,
        order: "Order",
        position: "Position",
        config: "GridConfig",
    ) -> tuple[bool, str]:
        """Evaluate whether placing ``order`` is safe given current state.

        Args:
            order: The order about to be placed.
            position: Current position snapshot.
            config: Active GridConfig.

        Returns:
            (True, "") if safe, or (False, reason_string) if blocked.
        """
        if order.side == "buy":
            cost = order.price * order.quantity
            fee = cost * config.fee_rate
            required = cost + fee
            if required > position.available_capital:
                return False, (
                    f"Insufficient capital: need {required:.4f}, "
                    f"available {position.available_capital:.4f}."
                )

        if order.side == "sell" and order.quantity > position.holdings:
            return False, (
                f"Insufficient holdings: need {order.quantity}, "
                f"held {position.holdings}."
            )

        if order.price <= 0:
            return False, f"Invalid order price: {order.price}."

        return True, ""

    # ------------------------------------------------------------------
    # Tick-level monitoring
    # ------------------------------------------------------------------

    def check_on_price_update(
        self,
        price: float,
        position: "Position",
        config: "GridConfig",
    ) -> RiskAlert | None:
        """Evaluate market and position risk on a price tick.

        Checks are evaluated in priority order; the first triggered alert
        is returned (only one alert per tick).

        Args:
            price: Current market price.
            position: Current position snapshot.
            config: Active GridConfig.

        Returns:
            A RiskAlert if a condition is triggered, else None.
        """
        # 1. Stop-loss breach
        if config.stop_loss_price is not None and price <= config.stop_loss_price:
            return RiskAlert(
                level="critical",
                type="stop_loss_breach",
                message=(
                    f"Price {price} breached stop-loss at {config.stop_loss_price}."
                ),
                suggested_action="Close all positions and cancel all orders immediately.",
            )

        # 2. Take-profit reached
        if config.take_profit_price is not None and price >= config.take_profit_price:
            return RiskAlert(
                level="warning",
                type="take_profit_reached",
                message=(
                    f"Price {price} reached take-profit at {config.take_profit_price}."
                ),
                suggested_action="Consider closing positions and locking in profit.",
            )

        # 3. Price below lower boundary — grid out of range
        if price < config.price_lower:
            unrealized_fraction = (
                abs(position.unrealized_pnl) / position.total_capital
                if position.total_capital > 0
                else 0.0
            )
            level: Literal["warning", "critical"] = (
                "critical" if unrealized_fraction > self.DRAWDOWN_CRITICAL_THRESHOLD
                else "warning"
            )
            return RiskAlert(
                level=level,
                type="below_lower",
                message=(
                    f"Price {price} is below grid lower bound {config.price_lower}. "
                    f"Unrealized loss = {unrealized_fraction:.1%} of capital."
                ),
                suggested_action=(
                    "Stop adding positions. Consider rebalancing grid to new range "
                    "or activating stop-loss."
                ),
            )

        # 4. Price above upper boundary — suggests range exhausted
        if price > config.price_upper:
            return RiskAlert(
                level="warning",
                type="above_upper",
                message=(
                    f"Price {price} exceeded grid upper bound {config.price_upper}."
                ),
                suggested_action=(
                    "All sell orders may have filled. Consider taking profit or "
                    "rebalancing grid upward."
                ),
            )

        # 5. Available capital critically low
        capital_ratio = (
            position.available_capital / position.total_capital
            if position.total_capital > 0
            else 1.0
        )
        if capital_ratio < self.CAPITAL_LOW_THRESHOLD:
            return RiskAlert(
                level="warning",
                type="capital_low",
                message=(
                    f"Available capital is {capital_ratio:.1%} of total "
                    f"({position.available_capital:.2f} remaining). "
                    "No new buy orders can be placed."
                ),
                suggested_action=(
                    "Wait for sell orders to fill and free capital, or reduce position size."
                ),
            )

        # 6. Drawdown limit from holdings mark-to-market
        if position.holdings > 0 and position.unrealized_pnl < 0:
            drawdown = abs(position.unrealized_pnl) / position.total_capital
            if drawdown > self.DRAWDOWN_CRITICAL_THRESHOLD:
                return RiskAlert(
                    level="critical",
                    type="drawdown_limit",
                    message=(
                        f"Unrealized drawdown {drawdown:.1%} exceeds "
                        f"{self.DRAWDOWN_CRITICAL_THRESHOLD:.0%} threshold."
                    ),
                    suggested_action=(
                        "Consider reducing position or activating stop-loss to "
                        "limit further loss."
                    ),
                )

        return None


if __name__ == "__main__":
    from grid_trading.core.position_tracker import Position
    from grid_trading.strategy.grid_strategy import GridConfig

    checker = RiskChecker()

    cfg = GridConfig(
        symbol="BTC/USDT",
        grid_type="arithmetic",
        price_lower=40000,
        price_upper=60000,
        grid_count=10,
        total_capital=10000,
        fee_rate=0.001,
        stop_loss_price=38000,
    )

    healthy_pos = Position(
        total_capital=10000,
        used_capital=5000,
        available_capital=5000,
        holdings=0.1,
        avg_cost=50000,
        unrealized_pnl=200,
        realized_pnl=0,
        total_trades=2,
        fee_paid=10,
        market_price=52000,
    )

    # No alert in healthy state
    alert = checker.check_on_price_update(51000, healthy_pos, cfg)
    print(f"Healthy: alert={alert}")

    # Below lower bound with large loss
    distressed_pos = Position(
        total_capital=10000,
        used_capital=8000,
        available_capital=200,
        holdings=0.2,
        avg_cost=50000,
        unrealized_pnl=-2500,
        realized_pnl=0,
        total_trades=4,
        fee_paid=20,
        market_price=37500,
    )
    alert = checker.check_on_price_update(37500, distressed_pos, cfg)
    print(f"Distressed: level={alert.level} type={alert.type}")
    print(f"  message: {alert.message}")
    print(f"  action : {alert.suggested_action}")
