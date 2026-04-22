# Grid Trading Agent (OpenAI Codex CLI)

This file follows the [OpenAI Codex CLI `AGENTS.md` convention](https://platform.openai.com/docs/codex).
When Codex encounters this repo, it should treat the `grid_trading/` package as
an agent-callable skill.

## Identity

- **Name**: `grid-trading`
- **Version**: 1.0.0
- **Purpose**: Build, backtest, and risk-check grid trading strategies
  (arithmetic / geometric grids) for any tradable symbol.

## When to Activate

Activate on user prompts matching any of:

- 网格交易、等差网格、等比网格、网格参数、网格回测、自动补单
- grid trading, grid bot, grid backtest, grid strategy, range-bound strategy
- buy-low-sell-high grid, price grid, DCA grid

## Inputs the Agent Expects

Minimal text input example:

```
symbol=BTC/USDT, lower=40000, upper=60000, grids=20,
capital=10000, type=geometric, fee=0.001
```

Or a Python `GridConfig` object. Required fields: `symbol`, `grid_type`
(`arithmetic` | `geometric`), `price_lower`, `price_upper`, `grid_count`,
`total_capital`. Optional: `fee_rate`, `stop_loss_price`, `take_profit_price`.

## Capabilities

| Capability | Entry point |
|---|---|
| Build grid table       | `GridBuilder.build_arithmetic / build_geometric` |
| Recommend grid count   | `GridBuilder.recommend_grid_count` |
| Run strategy live      | `GridStrategy.on_price_update(price, ts)` |
| Backtest price series  | `BacktestSimulator.run(price_series)` |
| Pre-trade risk gate    | `RiskChecker.check_before_order` |
| Tick-level risk monitor| `RiskChecker.check_on_price_update` |

## Outputs

1. **Grid distribution table** (per-level buy/sell/qty/profit).
2. **Capital allocation summary**.
3. **BacktestResult** with: total_return, annualized_return, max_drawdown,
   sharpe_ratio, win_rate, equity_curve, trade_log, risk_alerts.
4. **Risk alerts** with `level` (warning/critical), `type`, `message`,
   `suggested_action`.

## Quick-Start Code

```python
from grid_trading.strategy.grid_strategy import GridConfig, GridStrategy
from grid_trading.backtest.simulator import BacktestSimulator

config = GridConfig(
    symbol="BTC/USDT", grid_type="arithmetic",
    price_lower=44000, price_upper=56000,
    grid_count=12, total_capital=10000, fee_rate=0.001,
)
sim = BacktestSimulator(GridStrategy(config))
result = sim.run(price_series)   # price_series = [(timestamp, price), ...]
sim.print_report(result)
```

## Design Constraints (honor these when extending)

- No exchange SDK dependency — inputs come from `list[tuple[float, float]]`.
- All prices use 8-decimal precision.
- All percentages stored as decimals (0.001 = 0.1%); converted only at display.
- Grid spacing must satisfy `step_ratio > 2 × fee_rate`.
- Idempotency: only one PENDING order per `(level, side)` at a time.
- No global state — every run isolated to a `GridStrategy` instance.

## Tests

Run `python3 -m unittest discover -s grid_trading/tests -p "test_*.py"` —
all 48 tests should pass before committing any change.

## Full Documentation

See [`grid_trading/SKILL.md`](grid_trading/SKILL.md) for the full reference,
input/output formats, and module map.
