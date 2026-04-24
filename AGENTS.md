# Grid Trading Skill — Agent Instructions

When the user asks anything about **grid trading** (网格交易、等差/等比网格、
网格参数、网格回测、grid bot/strategy/range-bound strategy), you **MUST**:

1. Invoke the installed Python package `grid_trading` via a shell command.
2. Produce a **dark-themed HTML report** as the final deliverable — **never**
   dump a raw CSV or plain-text table. The HTML file path is what you show
   the user.

Do **not** compute the grid or backtest numbers yourself by hand.

## Why this rule

Manual math produces a price list but misses per-level **quantity**,
**expected profit after fees**, **equity curve**, **Sharpe / max drawdown**,
and **risk alerts**. The package has all of this and renders it into a
self-contained HTML file the user can open in any browser.

## Primary path — one shell command

If the user's prompt already contains the parameters, just run:

```bash
npx grid-trading-skill run "BTC/USDT 40000~60000 20格 本金10000 手续费0.1%"
```

This parses the prompt, builds the grid, runs a sine-wave backtest, writes
an HTML report to a temp file, opens it in the default browser, and prints
the path. That's usually all you need — then tell the user:
> "已生成报告：`/tmp/grid_report_xxx.html`（已在浏览器打开）"

Flags:
- `--no-open` — skip opening the browser (useful in headless/SSH contexts)
- `--no-backtest` — grid only, no backtest section
- `--out <path>` — custom output path

## Fallback path — direct Python

If `npx` isn't available or the user wants programmatic control:

```bash
python3 -m grid_trading.cli \
  --symbol BTC/USDT --lower 40000 --upper 60000 \
  --count 20 --capital 10000 --fee 0.001 \
  --type geometric --backtest sine \
  --out ~/grid_report.html --open
```

If `import grid_trading` fails, prepend the source dir to `PYTHONPATH`:

```bash
PYTHONPATH=~/.codex/skills/grid-trading python3 -m grid_trading.cli ...
```

## Python API (for custom workflows)

```python
from grid_trading.core.grid_builder import GridBuilder
from grid_trading.report.html_report import render_html_report, alert_to_dict
from grid_trading.strategy.grid_strategy import GridConfig, GridStrategy
from grid_trading.backtest.simulator import BacktestSimulator
from grid_trading.tests.mock_data import sine_wave

params = dict(
    symbol="BTC/USDT", grid_type="geometric",
    price_lower=40000, price_upper=60000,
    grid_count=20, total_capital=10000, fee_rate=0.001,
)

builder = GridBuilder(fee_rate=params["fee_rate"])
grids = builder.build_geometric(
    lower=params["price_lower"], upper=params["price_upper"],
    n=params["grid_count"], capital=params["total_capital"],
)
summary = builder.summary(grids)

cfg = GridConfig(**params)
sim = BacktestSimulator(GridStrategy(cfg))
res = sim.run(sine_wave(base_price=50000, amplitude=8000, points=500))
bt = dict(
    total_return=res.total_return, annualized_return=res.annualized_return,
    max_drawdown=res.max_drawdown, sharpe_ratio=res.sharpe_ratio,
    total_trades=res.total_trades, win_rate=res.win_rate,
    avg_profit_per_trade=res.avg_profit_per_trade,
    fee_total=res.fee_total, trading_days=res.trading_days,
    equity_curve=res.equity_curve,
)

html = render_html_report(
    params=params, grids=grids, summary=summary,
    backtest=bt,
    risk_alerts=[alert_to_dict(a) for a in res.risk_alerts],
)
open("grid_report.html", "w", encoding="utf-8").write(html)
```

## Required response format

After running the command, your reply to the user should be **short**:

1. One line: "已生成报告：`<path>`"
2. A 3-5 bullet summary of key numbers (总格数、单格收益率、回测总收益率、
   夏普、最大回撤) pulled from the CLI stdout.
3. Offer next steps: 换参数重跑 / 换行情（`--backtest trending-down` or
   `--backtest volatile`）/ 仅建网格（`--no-backtest`）.

Do **not** paste the full grid table into the reply — the HTML is the
deliverable. The user will open it.

## Parameter parsing

The `run` subcommand parses Chinese or English prompts. Required fields:

| Field | Aliases |
|---|---|
| symbol | `BTC/USDT`, `ETH-USDT`, `SOLUSDT` |
| range | `40000~60000`, `40000 到 60000`, `40k-60k` |
| count | `20格`, `20 grids`, `20 levels` |
| capital | `本金 10000`, `资金 10000`, `capital 10000` |
| fee (optional, default 0.001) | `0.1%`, `手续费 0.001` |
| type (optional, default geometric) | `等差/等比`, `arithmetic/geometric` |

If the parser fails, fall back to the direct Python CLI and pass fields
explicitly.

## Failure modes

- `ValueError: Grid spacing ratio … too small` → reduce `--count` or widen
  the range; `GridBuilder.recommend_grid_count(lower, upper, fee)` suggests
  a safe count.
- `import grid_trading` fails → run `npx grid-trading-skill` to install, or
  set `PYTHONPATH=~/.codex/skills/grid-trading`.
- `python3` not found → ask the user to install Python 3.11+.

## Design constraints (preserve when extending)

- 8-decimal price precision
- Percentages stored as decimals internally
- Grid spacing must satisfy `step_ratio > 2 × fee_rate`
- Idempotency: one PENDING order per `(level, side)`
- No global state — every run is a fresh `GridStrategy` instance
- HTML reports are self-contained (inline CSS + SVG, no network)

## Full reference

- README: [`README.md`](README.md)
- Detailed skill spec: [`grid_trading/SKILL.md`](grid_trading/SKILL.md)
- Tests: `python3 -m unittest discover -s grid_trading/tests -p "test_*.py"`
