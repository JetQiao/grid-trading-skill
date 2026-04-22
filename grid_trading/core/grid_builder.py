"""Grid level construction for arithmetic and geometric grid strategies."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class GridLevel:
    """A single grid level with pricing and capital information."""

    level: int            # 格位编号（从下往上 1..n）
    buy_price: float      # 买入价
    sell_price: float     # 卖出价
    quantity: float       # 每格买入数量
    capital_required: float   # 该格所需资金
    expected_profit: float    # 预期单次利润
    profit_rate: float    # 单格收益率（小数，如 0.01 = 1%）


class GridBuilder:
    """Builds arithmetic or geometric grid levels from parameters.

    All prices are stored with 8-decimal precision (crypto-grade).
    """

    def __init__(self, fee_rate: float = 0.001) -> None:
        """
        Args:
            fee_rate: Taker fee as a decimal (e.g. 0.001 = 0.1%).
        """
        self.fee_rate = fee_rate

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_arithmetic(
        self,
        lower: float,
        upper: float,
        n: int,
        capital: float,
    ) -> list[GridLevel]:
        """Build an arithmetic (equal-spacing) grid.

        Args:
            lower: Lower price boundary.
            upper: Upper price boundary.
            n: Number of grid levels.
            capital: Total capital to allocate across all levels.

        Returns:
            List of GridLevel objects ordered from lowest to highest.

        Raises:
            ValueError: If n < 2, boundaries invalid, or grid spacing too
                small relative to fee_rate.
        """
        self._validate_inputs(lower, upper, n, capital)

        step = (upper - lower) / n
        self._check_min_spacing(step, lower, self.fee_rate)

        capital_per_grid = capital / n
        levels: list[GridLevel] = []

        for i in range(1, n + 1):
            buy_price = round(lower + (i - 1) * step, 8)
            sell_price = round(lower + i * step, 8)
            qty = round(capital_per_grid / buy_price, 8)
            expected_profit = round(
                qty * (sell_price - buy_price)
                - qty * buy_price * self.fee_rate
                - qty * sell_price * self.fee_rate,
                8,
            )
            profit_rate = round((sell_price - buy_price) / buy_price, 8)
            levels.append(
                GridLevel(
                    level=i,
                    buy_price=buy_price,
                    sell_price=sell_price,
                    quantity=qty,
                    capital_required=round(capital_per_grid, 8),
                    expected_profit=expected_profit,
                    profit_rate=profit_rate,
                )
            )

        return levels

    def build_geometric(
        self,
        lower: float,
        upper: float,
        n: int,
        capital: float,
    ) -> list[GridLevel]:
        """Build a geometric (equal-ratio) grid.

        Each level's sell/buy ratio is constant, producing a uniform
        profit rate regardless of price level.

        Args:
            lower: Lower price boundary.
            upper: Upper price boundary.
            n: Number of grid levels.
            capital: Total capital to allocate across all levels.

        Returns:
            List of GridLevel objects ordered from lowest to highest.

        Raises:
            ValueError: If n < 2, boundaries invalid, or grid spacing too
                small relative to fee_rate.
        """
        self._validate_inputs(lower, upper, n, capital)

        ratio = (upper / lower) ** (1.0 / n)
        # Verify minimum spacing at the lowest (tightest) level
        min_step = lower * (ratio - 1)
        self._check_min_spacing(min_step, lower, self.fee_rate)

        capital_per_grid = capital / n
        levels: list[GridLevel] = []

        for i in range(1, n + 1):
            buy_price = round(lower * (ratio ** (i - 1)), 8)
            sell_price = round(lower * (ratio ** i), 8)
            qty = round(capital_per_grid / buy_price, 8)
            expected_profit = round(
                qty * (sell_price - buy_price)
                - qty * buy_price * self.fee_rate
                - qty * sell_price * self.fee_rate,
                8,
            )
            profit_rate = round(ratio - 1.0, 8)
            levels.append(
                GridLevel(
                    level=i,
                    buy_price=buy_price,
                    sell_price=sell_price,
                    quantity=qty,
                    capital_required=round(capital_per_grid, 8),
                    expected_profit=expected_profit,
                    profit_rate=profit_rate,
                )
            )

        return levels

    def recommend_grid_count(self, lower: float, upper: float, fee_rate: float) -> int:
        """Return the minimum grid count so that each grid spacing > 2 × fee_rate.

        Uses arithmetic spacing as the conservative (tighter) estimate.

        Args:
            lower: Lower price boundary.
            upper: Upper price boundary.
            fee_rate: Taker fee as a decimal.

        Returns:
            Minimum recommended number of grid levels.
        """
        # Each arithmetic step as fraction of lower: step/lower > 2*fee_rate
        # (upper - lower) / (n * lower) > 2 * fee_rate
        # n < (upper - lower) / (lower * 2 * fee_rate)
        # Need strict inequality: step_ratio > 2*fee_rate
        # => n < (upper-lower)/(lower*2*fee_rate)
        # ceil-1 handles exact-integer boundaries correctly.
        max_n = (upper - lower) / (lower * 2 * fee_rate)
        return max(2, math.ceil(max_n) - 1)

    def summary(self, grids: list[GridLevel]) -> dict:
        """Return aggregate statistics for a built grid.

        Args:
            grids: List of GridLevel objects.

        Returns:
            Dict with keys: grid_count, total_capital, avg_profit_rate,
            min_profit, max_profit, total_expected_profit.
        """
        if not grids:
            return {}

        total_capital = sum(g.capital_required for g in grids)
        profit_rates = [g.profit_rate for g in grids]
        profits = [g.expected_profit for g in grids]

        return {
            "grid_count": len(grids),
            "price_lower": grids[0].buy_price,
            "price_upper": grids[-1].sell_price,
            "total_capital": round(total_capital, 8),
            "avg_profit_rate": round(sum(profit_rates) / len(profit_rates), 8),
            "min_profit_rate": round(min(profit_rates), 8),
            "max_profit_rate": round(max(profit_rates), 8),
            "total_expected_profit": round(sum(profits), 8),
            "estimated_annual_cycles": None,  # requires velocity data
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_inputs(lower: float, upper: float, n: int, capital: float) -> None:
        if lower <= 0 or upper <= 0:
            raise ValueError("Price boundaries must be positive.")
        if upper <= lower:
            raise ValueError(f"upper ({upper}) must be greater than lower ({lower}).")
        if n < 2:
            raise ValueError(f"Grid count must be >= 2, got {n}.")
        if capital <= 0:
            raise ValueError("Capital must be positive.")

    @staticmethod
    def _check_min_spacing(step: float, ref_price: float, fee_rate: float) -> None:
        """Ensure each grid step is wide enough to cover fees on both sides."""
        step_ratio = step / ref_price
        if step_ratio <= 2 * fee_rate:
            raise ValueError(
                f"Grid spacing ratio {step_ratio:.6f} is too small; "
                f"must be > 2 × fee_rate ({2 * fee_rate:.6f}). "
                "Reduce grid count or widen the price range."
            )


if __name__ == "__main__":
    builder = GridBuilder(fee_rate=0.001)

    print("=== Arithmetic Grid ===")
    arith = builder.build_arithmetic(lower=40000, upper=60000, n=10, capital=10000)
    for lvl in arith:
        print(
            f"  Level {lvl.level:2d} | buy={lvl.buy_price:>10.2f} "
            f"sell={lvl.sell_price:>10.2f} | qty={lvl.quantity:.6f} "
            f"| profit={lvl.expected_profit:.4f} | rate={lvl.profit_rate*100:.4f}%"
        )
    print(builder.summary(arith))

    print("\n=== Geometric Grid ===")
    geo = builder.build_geometric(lower=40000, upper=60000, n=10, capital=10000)
    for lvl in geo:
        print(
            f"  Level {lvl.level:2d} | buy={lvl.buy_price:>10.2f} "
            f"sell={lvl.sell_price:>10.2f} | qty={lvl.quantity:.6f} "
            f"| profit={lvl.expected_profit:.4f} | rate={lvl.profit_rate*100:.4f}%"
        )
    print(builder.summary(geo))

    print("\n=== Recommended Grid Count ===")
    rec = builder.recommend_grid_count(40000, 60000, fee_rate=0.001)
    print(f"  Recommended max grid count: {rec}")
