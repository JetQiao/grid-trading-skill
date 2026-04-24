"""Command-line entry point: build grid + optional backtest + HTML report.

Usage:
    python -m grid_trading.cli \\
        --symbol BTC/USDT --lower 40000 --upper 60000 \\
        --count 20 --capital 10000 --fee 0.001 \\
        --type geometric --backtest sine --out report.html --open

All numeric args are plain numbers (fees as decimals: 0.001 = 0.1%).
"""

from __future__ import annotations

import argparse
import os
import sys
import webbrowser
from pathlib import Path

from grid_trading.core.grid_builder import GridBuilder
from grid_trading.report.html_report import alert_to_dict, render_html_report


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m grid_trading.cli",
        description="Build grid trading plan, optionally backtest, and render HTML report.",
    )
    p.add_argument("--symbol", default="BTC/USDT", help="Trading pair label (for display).")
    p.add_argument("--lower",  type=float, required=True, help="Lower price boundary.")
    p.add_argument("--upper",  type=float, required=True, help="Upper price boundary.")
    p.add_argument("--count",  type=int,   required=True, help="Grid count.")
    p.add_argument("--capital", type=float, required=True, help="Total capital to allocate.")
    p.add_argument("--fee",    type=float, default=0.001, help="Fee rate as decimal (0.001 = 0.1%%).")
    p.add_argument("--type",   choices=["arithmetic", "geometric"], default="geometric",
                   dest="grid_type", help="Grid type.")
    p.add_argument("--stop-loss",   type=float, default=None, dest="stop_loss_price")
    p.add_argument("--take-profit", type=float, default=None, dest="take_profit_price")
    p.add_argument(
        "--backtest",
        choices=["none", "sine", "trending-down", "volatile"],
        default="none",
        help="Run a backtest on built-in mock data.",
    )
    p.add_argument("--out", default="grid_report.html", help="Output HTML file path.")
    p.add_argument("--open", action="store_true", help="Open the report in default browser after write.")
    p.add_argument("--quiet", action="store_true", help="Suppress stdout chatter; only print the output path.")
    return p


def _run_backtest(kind: str, params: dict) -> dict | None:
    if kind == "none":
        return None
    from grid_trading.strategy.grid_strategy import GridConfig, GridStrategy
    from grid_trading.backtest.simulator import BacktestSimulator
    from grid_trading.tests.mock_data import sine_wave, trending_down, volatile_spike

    mid = (params["price_lower"] + params["price_upper"]) / 2
    amp = (params["price_upper"] - params["price_lower"]) / 2 * 0.85

    if kind == "sine":
        series = sine_wave(base_price=mid, amplitude=amp, points=500)
    elif kind == "trending-down":
        series = trending_down(
            start_price=params["price_upper"],
            end_price=params["price_lower"],
            points=500,
        )
    else:
        series = volatile_spike(base_price=mid, points=500)

    cfg = GridConfig(
        symbol=params["symbol"],
        grid_type=params["grid_type"],
        price_lower=params["price_lower"],
        price_upper=params["price_upper"],
        grid_count=params["grid_count"],
        total_capital=params["total_capital"],
        fee_rate=params["fee_rate"],
        stop_loss_price=params.get("stop_loss_price"),
        take_profit_price=params.get("take_profit_price"),
    )
    sim = BacktestSimulator(GridStrategy(cfg))
    res = sim.run(series)
    return {
        "total_return": res.total_return,
        "annualized_return": res.annualized_return,
        "max_drawdown": res.max_drawdown,
        "sharpe_ratio": res.sharpe_ratio,
        "total_trades": res.total_trades,
        "win_rate": res.win_rate,
        "avg_profit_per_trade": res.avg_profit_per_trade,
        "fee_total": res.fee_total,
        "trading_days": res.trading_days,
        "equity_curve": res.equity_curve,
        "risk_alerts": [alert_to_dict(a) for a in res.risk_alerts],
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    params = {
        "symbol": args.symbol,
        "grid_type": args.grid_type,
        "price_lower": args.lower,
        "price_upper": args.upper,
        "grid_count": args.count,
        "total_capital": args.capital,
        "fee_rate": args.fee,
        "stop_loss_price": args.stop_loss_price,
        "take_profit_price": args.take_profit_price,
    }

    builder = GridBuilder(fee_rate=args.fee)
    build_fn = builder.build_geometric if args.grid_type == "geometric" else builder.build_arithmetic
    try:
        grids = build_fn(lower=args.lower, upper=args.upper, n=args.count, capital=args.capital)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        rec = builder.recommend_grid_count(args.lower, args.upper, args.fee)
        print(f"[HINT]  Try --count {rec} or widen the range.", file=sys.stderr)
        return 2

    summary = builder.summary(grids)
    backtest = _run_backtest(args.backtest, params)
    risk_alerts = backtest.pop("risk_alerts", None) if backtest else None

    html_doc = render_html_report(
        params=params,
        grids=grids,
        summary=summary,
        backtest=backtest,
        risk_alerts=risk_alerts,
    )

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_doc, encoding="utf-8")

    if not args.quiet:
        print(f"✓ Grid built: {len(grids)} levels, type={args.grid_type}")
        print(f"✓ Total capital: {args.capital:,.2f}")
        if backtest:
            print(f"✓ Backtest ({args.backtest}): return={backtest['total_return']*100:.2f}%, "
                  f"sharpe={backtest['sharpe_ratio']:.2f}, max_dd={backtest['max_drawdown']*100:.2f}%")
    print(str(out_path))

    if args.open:
        webbrowser.open(out_path.as_uri())

    return 0


if __name__ == "__main__":
    sys.exit(main())
