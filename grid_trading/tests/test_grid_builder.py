"""Unit tests for core/grid_builder.py."""

from __future__ import annotations

import math
import unittest

from grid_trading.core.grid_builder import GridBuilder, GridLevel


class TestArithmeticGrid(unittest.TestCase):
    """Tests for build_arithmetic."""

    def setUp(self) -> None:
        self.builder = GridBuilder(fee_rate=0.001)

    def test_level_count(self) -> None:
        grids = self.builder.build_arithmetic(40000, 60000, 10, 10000)
        self.assertEqual(len(grids), 10)

    def test_level_numbers_are_sequential(self) -> None:
        grids = self.builder.build_arithmetic(40000, 60000, 10, 10000)
        self.assertEqual([g.level for g in grids], list(range(1, 11)))

    def test_equal_price_spacing(self) -> None:
        """Each step should be exactly (upper - lower) / n."""
        grids = self.builder.build_arithmetic(40000, 60000, 10, 10000)
        steps = [round(g.sell_price - g.buy_price, 4) for g in grids]
        expected_step = (60000 - 40000) / 10
        for step in steps:
            self.assertAlmostEqual(step, expected_step, places=2)

    def test_capital_allocation_error_below_threshold(self) -> None:
        """Total allocated capital must be within 0.01% of requested capital."""
        capital = 10000.0
        grids = self.builder.build_arithmetic(40000, 60000, 10, capital)
        total = sum(g.capital_required for g in grids)
        relative_error = abs(total - capital) / capital
        self.assertLess(relative_error, 0.0001)

    def test_buy_price_less_than_sell_price(self) -> None:
        grids = self.builder.build_arithmetic(40000, 60000, 10, 10000)
        for g in grids:
            self.assertLess(g.buy_price, g.sell_price)

    def test_contiguous_levels(self) -> None:
        """sell_price of level i == buy_price of level i+1."""
        grids = self.builder.build_arithmetic(40000, 60000, 10, 10000)
        for a, b in zip(grids, grids[1:]):
            self.assertAlmostEqual(a.sell_price, b.buy_price, places=4)

    def test_quantity_positive(self) -> None:
        grids = self.builder.build_arithmetic(40000, 60000, 10, 10000)
        for g in grids:
            self.assertGreater(g.quantity, 0)

    def test_too_few_grids_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.builder.build_arithmetic(40000, 60000, 1, 10000)

    def test_invalid_bounds_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.builder.build_arithmetic(60000, 40000, 10, 10000)

    def test_spacing_too_tight_raises(self) -> None:
        """A grid with 10,000 levels will have spacing < 2 × fee_rate."""
        with self.assertRaises(ValueError):
            self.builder.build_arithmetic(40000, 40010, 10000, 10000)

    def test_expected_profit_positive_when_fees_low(self) -> None:
        """With wide enough grid, profit after fees should be positive."""
        grids = self.builder.build_arithmetic(40000, 60000, 5, 10000)
        for g in grids:
            self.assertGreater(g.expected_profit, 0)


class TestGeometricGrid(unittest.TestCase):
    """Tests for build_geometric."""

    def setUp(self) -> None:
        self.builder = GridBuilder(fee_rate=0.001)

    def test_level_count(self) -> None:
        grids = self.builder.build_geometric(40000, 60000, 10, 10000)
        self.assertEqual(len(grids), 10)

    def test_constant_profit_rate(self) -> None:
        """All levels must have the same profit_rate (ratio - 1)."""
        grids = self.builder.build_geometric(40000, 60000, 10, 10000)
        rates = [g.profit_rate for g in grids]
        for rate in rates:
            self.assertAlmostEqual(rate, rates[0], places=6)

    def test_capital_allocation_error_below_threshold(self) -> None:
        capital = 10000.0
        grids = self.builder.build_geometric(40000, 60000, 10, capital)
        total = sum(g.capital_required for g in grids)
        relative_error = abs(total - capital) / capital
        self.assertLess(relative_error, 0.0001)

    def test_geometric_ratio_consistency(self) -> None:
        """sell_price / buy_price should be constant across all levels."""
        grids = self.builder.build_geometric(40000, 60000, 10, 10000)
        ratios = [round(g.sell_price / g.buy_price, 5) for g in grids]
        for r in ratios:
            self.assertAlmostEqual(r, ratios[0], places=4)

    def test_price_boundaries_match(self) -> None:
        grids = self.builder.build_geometric(40000, 60000, 10, 10000)
        self.assertAlmostEqual(grids[0].buy_price, 40000, places=0)
        self.assertAlmostEqual(grids[-1].sell_price, 60000, places=0)

    def test_too_few_grids_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.builder.build_geometric(40000, 60000, 1, 10000)


class TestRecommendGridCount(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = GridBuilder(fee_rate=0.001)

    def test_returns_at_least_two(self) -> None:
        count = self.builder.recommend_grid_count(40000, 60000, 0.001)
        self.assertGreaterEqual(count, 2)

    def test_recommended_count_passes_spacing_check(self) -> None:
        """The recommended count should not trigger a spacing ValueError."""
        count = self.builder.recommend_grid_count(40000, 60000, 0.001)
        # Should not raise
        self.builder.build_arithmetic(40000, 60000, count, 10000)

    def test_higher_fee_rate_means_fewer_max_grids(self) -> None:
        low_fee = self.builder.recommend_grid_count(40000, 60000, 0.001)
        high_fee = self.builder.recommend_grid_count(40000, 60000, 0.005)
        self.assertGreater(low_fee, high_fee)


class TestSummary(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = GridBuilder(fee_rate=0.001)

    def test_summary_keys_present(self) -> None:
        grids = self.builder.build_arithmetic(40000, 60000, 10, 10000)
        s = self.builder.summary(grids)
        for key in (
            "grid_count", "price_lower", "price_upper", "total_capital",
            "avg_profit_rate", "total_expected_profit",
        ):
            self.assertIn(key, s)

    def test_summary_grid_count(self) -> None:
        grids = self.builder.build_arithmetic(40000, 60000, 10, 10000)
        self.assertEqual(self.builder.summary(grids)["grid_count"], 10)

    def test_summary_empty_returns_empty_dict(self) -> None:
        self.assertEqual(self.builder.summary([]), {})


if __name__ == "__main__":
    unittest.main()
