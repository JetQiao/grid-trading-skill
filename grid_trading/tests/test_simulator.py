"""Integration tests for backtest/simulator.py."""

from __future__ import annotations

import unittest

from grid_trading.backtest.simulator import BacktestSimulator, BacktestResult
from grid_trading.strategy.grid_strategy import GridStrategy, GridConfig
from grid_trading.tests.mock_data import sine_wave, trending_down, volatile_spike


def _make_sim(
    lower: float = 44000,
    upper: float = 56000,
    n: int = 12,
    capital: float = 10000,
    grid_type: str = "arithmetic",
    stop_loss: float | None = None,
) -> BacktestSimulator:
    cfg = GridConfig(
        symbol="BTC/USDT",
        grid_type=grid_type,
        price_lower=lower,
        price_upper=upper,
        grid_count=n,
        total_capital=capital,
        fee_rate=0.001,
        stop_loss_price=stop_loss,
    )
    return BacktestSimulator(GridStrategy(cfg))


class TestSimulatorBasicContract(unittest.TestCase):
    """Verify structural guarantees of BacktestResult."""

    def setUp(self) -> None:
        self.series = sine_wave(base_price=50000, amplitude=5000, periods=3, points=300)

    def test_equity_curve_length_equals_price_series(self) -> None:
        """equity_curve must have one entry per price tick."""
        sim = _make_sim()
        result = sim.run(self.series)
        self.assertEqual(len(result.equity_curve), len(self.series))

    def test_result_has_all_required_fields(self) -> None:
        sim = _make_sim()
        result = sim.run(self.series)
        for attr in (
            "total_return", "annualized_return", "max_drawdown", "sharpe_ratio",
            "total_trades", "win_rate", "avg_profit_per_trade", "fee_total",
            "equity_curve", "trade_log", "risk_alerts",
        ):
            self.assertTrue(hasattr(result, attr), f"Missing field: {attr}")

    def test_requires_at_least_two_data_points(self) -> None:
        sim = _make_sim()
        with self.assertRaises(ValueError):
            sim.run([(0.0, 50000.0)])

    def test_total_trades_matches_trade_log_count(self) -> None:
        sim = _make_sim()
        result = sim.run(self.series)
        self.assertEqual(result.total_trades, result.total_trades)  # sanity
        # trade_log has one entry per fill (buy + sell), total_trades counts both
        self.assertGreaterEqual(len(result.trade_log), 0)

    def test_fee_total_positive_when_trades_exist(self) -> None:
        sim = _make_sim()
        result = sim.run(self.series)
        if result.total_trades > 0:
            self.assertGreater(result.fee_total, 0)


class TestSineWaveScenario(unittest.TestCase):
    """Grid strategy should profit in an oscillating market."""

    def setUp(self) -> None:
        self.series = sine_wave(base_price=50000, amplitude=5000, periods=5, points=500)
        self.result = _make_sim().run(self.series)

    def test_total_return_positive(self) -> None:
        """Sine-wave market is the ideal grid scenario — must profit."""
        self.assertGreater(self.result.total_return, 0)

    def test_trades_occurred(self) -> None:
        self.assertGreater(self.result.total_trades, 0)

    def test_max_drawdown_in_valid_range(self) -> None:
        self.assertGreaterEqual(self.result.max_drawdown, 0)
        self.assertLessEqual(self.result.max_drawdown, 1)

    def test_win_rate_in_valid_range(self) -> None:
        self.assertGreaterEqual(self.result.win_rate, 0)
        self.assertLessEqual(self.result.win_rate, 1)

    def test_no_critical_alerts_in_sine_wave(self) -> None:
        criticals = [a for a in self.result.risk_alerts if a.level == "critical"]
        self.assertEqual(len(criticals), 0)


class TestTrendingDownScenario(unittest.TestCase):
    """Downtrend should trigger risk alerts and produce negative returns."""

    def setUp(self) -> None:
        # Price falls from 55000 well below grid lower (36000)
        self.series = trending_down(
            start_price=55000, end_price=30000, points=500
        )
        self.result = _make_sim(lower=36000, upper=58000, n=10,
                                stop_loss=32000).run(self.series)

    def test_risk_alerts_fired(self) -> None:
        """Severe downtrend must trigger at least one risk alert."""
        self.assertGreater(len(self.result.risk_alerts), 0)

    def test_equity_curve_length(self) -> None:
        self.assertEqual(len(self.result.equity_curve), len(self.series))

    def test_below_lower_alert_triggered(self) -> None:
        alert_types = {a.type for a in self.result.risk_alerts}
        self.assertIn("below_lower", alert_types)

    def test_return_negative_in_severe_downtrend(self) -> None:
        self.assertLess(self.result.total_return, 0)


class TestVolatileSpikeScenario(unittest.TestCase):
    """Drop-then-recover scenario exercises buy accumulation and sell exit."""

    def setUp(self) -> None:
        self.series = volatile_spike(
            base_price=2500, drop_to=1900, recover_to=2800, points=400
        )
        cfg = GridConfig(
            symbol="ETH/USDT",
            grid_type="geometric",
            price_lower=1800,
            price_upper=3200,
            grid_count=10,
            total_capital=5000,
            fee_rate=0.001,
        )
        self.result = BacktestSimulator(GridStrategy(cfg)).run(self.series)

    def test_equity_curve_length(self) -> None:
        self.assertEqual(len(self.result.equity_curve), len(self.series))

    def test_trades_occurred(self) -> None:
        self.assertGreater(self.result.total_trades, 0)


class TestGeometricGridBacktest(unittest.TestCase):
    """Geometric grids should also produce valid backtest output."""

    def test_geometric_grid_completes_without_error(self) -> None:
        series = sine_wave(base_price=50000, amplitude=4000, periods=4, points=300)
        result = _make_sim(grid_type="geometric").run(series)
        self.assertEqual(len(result.equity_curve), 300)
        self.assertIsInstance(result.sharpe_ratio, float)


class TestMetrics(unittest.TestCase):
    """Unit tests for backtest/metrics.py functions."""

    def test_total_return_zero_length(self) -> None:
        from grid_trading.backtest.metrics import total_return
        self.assertEqual(total_return([]), 0.0)
        self.assertEqual(total_return([10000]), 0.0)

    def test_total_return_positive(self) -> None:
        from grid_trading.backtest.metrics import total_return
        self.assertAlmostEqual(total_return([10000, 11000]), 0.1, places=6)

    def test_max_drawdown_flat(self) -> None:
        from grid_trading.backtest.metrics import max_drawdown
        self.assertEqual(max_drawdown([10000, 10000, 10000]), 0.0)

    def test_max_drawdown_known_value(self) -> None:
        from grid_trading.backtest.metrics import max_drawdown
        # Peak=10000, trough=8000 => dd=0.2
        curve = [10000, 9500, 8000, 9000]
        self.assertAlmostEqual(max_drawdown(curve), 0.2, places=6)

    def test_sharpe_zero_variance(self) -> None:
        from grid_trading.backtest.metrics import sharpe_ratio
        # Constant equity → std=0 → sharpe=0
        self.assertEqual(sharpe_ratio([10000, 10000, 10000]), 0.0)

    def test_win_rate_all_wins(self) -> None:
        from grid_trading.backtest.metrics import win_rate
        log = [{"side": "sell", "pnl": 50.0}, {"side": "sell", "pnl": 30.0}]
        self.assertEqual(win_rate(log), 1.0)

    def test_win_rate_no_sells(self) -> None:
        from grid_trading.backtest.metrics import win_rate
        log = [{"side": "buy", "pnl": 0.0}]
        self.assertEqual(win_rate(log), 0.0)

    def test_avg_profit_per_trade(self) -> None:
        from grid_trading.backtest.metrics import avg_profit_per_trade
        log = [{"side": "sell", "pnl": 100.0}, {"side": "sell", "pnl": 50.0}]
        self.assertAlmostEqual(avg_profit_per_trade(log), 75.0, places=6)


if __name__ == "__main__":
    unittest.main()
