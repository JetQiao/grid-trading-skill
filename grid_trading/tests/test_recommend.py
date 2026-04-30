"""Unit tests for recommend/auto_grid.py — pure deterministic logic."""

from __future__ import annotations

import math
import random
import unittest

from grid_trading.core.grid_builder import GridBuilder
from grid_trading.data.kline import Bar
from grid_trading.recommend import recommend_from_bars


def _osc_bars(
    base: float, amplitude_pct: float, n: int = 200, seed: int = 42
) -> list[Bar]:
    """Synthetic oscillating daily bars around ``base``."""
    rng = random.Random(seed)
    out = []
    for i in range(n):
        anchor = base * (1.0 + amplitude_pct * math.sin(i / 11.0))
        o = anchor * (1 + rng.uniform(-0.005, 0.005))
        c = anchor * (1 + rng.uniform(-0.008, 0.008))
        h = max(o, c) * (1 + rng.uniform(0, 0.008))
        l = min(o, c) * (1 - rng.uniform(0, 0.008))
        out.append(Bar(timestamp=1700000000 + i * 86400, date="-",
                       open=o, high=h, low=l, close=c, volume=1e6))
    return out


class TestRecommendFromBars(unittest.TestCase):

    def setUp(self) -> None:
        self.bars = _osc_bars(base=100.0, amplitude_pct=0.06, n=180)

    def test_mid_price_is_within_window(self):
        rec = recommend_from_bars(symbol="X", bars=self.bars, capital=10_000)
        win_lo = min(b.low for b in self.bars[-120:])
        win_hi = max(b.high for b in self.bars[-120:])
        self.assertGreaterEqual(rec.mid_price, win_lo)
        self.assertLessEqual(rec.mid_price, win_hi)

    def test_lower_below_mid_below_upper(self):
        rec = recommend_from_bars(symbol="X", bars=self.bars, capital=10_000)
        self.assertLess(rec.price_lower, rec.mid_price)
        self.assertLess(rec.mid_price, rec.price_upper)

    def test_lower_positive(self):
        rec = recommend_from_bars(symbol="X", bars=self.bars, capital=10_000)
        self.assertGreater(rec.price_lower, 0)

    def test_grid_count_passes_spacing_check(self):
        """Recommended (lower, upper, count, fee) must build successfully."""
        rec = recommend_from_bars(symbol="X", bars=self.bars,
                                  capital=10_000, fee_rate=0.001)
        builder = GridBuilder(fee_rate=0.001)
        fn = (builder.build_geometric if rec.grid_type == "geometric"
              else builder.build_arithmetic)
        # Should not raise — confirms step_ratio > 2 * fee
        levels = fn(rec.price_lower, rec.price_upper, rec.grid_count, 10_000)
        self.assertEqual(len(levels), rec.grid_count)

    def test_grid_count_capped_by_max_grids(self):
        rec = recommend_from_bars(symbol="X", bars=self.bars,
                                  capital=10_000, max_grids=12)
        self.assertLessEqual(rec.grid_count, 12)

    def test_safety_widens_band(self):
        rec_neutral = recommend_from_bars(symbol="X", bars=self.bars,
                                          capital=10_000, safety=1.0)
        rec_wide = recommend_from_bars(symbol="X", bars=self.bars,
                                       capital=10_000, safety=1.5)
        # 1.5x safety should not narrow the band
        band_neutral = rec_neutral.price_upper - rec_neutral.price_lower
        band_wide = rec_wide.price_upper - rec_wide.price_lower
        self.assertGreaterEqual(band_wide, band_neutral)

    def test_methods_all_produce_valid_bounds(self):
        for method in ("sigma", "atr", "quantile"):
            rec = recommend_from_bars(symbol="X", bars=self.bars,
                                      capital=10_000, method=method)
            self.assertLess(rec.price_lower, rec.price_upper, f"method={method}")
            self.assertGreater(rec.grid_count, 1)

    def test_arithmetic_for_narrow_range(self):
        bars = _osc_bars(base=100.0, amplitude_pct=0.03)
        rec = recommend_from_bars(symbol="X", bars=bars, capital=10_000)
        # ratio < 1.5 → arithmetic
        self.assertEqual(rec.grid_type, "arithmetic")

    def test_recommendation_is_serializable(self):
        rec = recommend_from_bars(symbol="X", bars=self.bars, capital=10_000)
        d = rec.to_dict()
        self.assertIn("mid_price", d)
        self.assertIn("price_lower", d)
        self.assertIn("price_upper", d)
        self.assertIn("notes", d)

    def test_empty_bars_raises(self):
        with self.assertRaises(ValueError):
            recommend_from_bars(symbol="X", bars=[], capital=10_000)


if __name__ == "__main__":
    unittest.main()
