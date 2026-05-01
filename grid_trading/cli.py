"""Command-line entry point: build grid + optional backtest + HTML report.

Manual mode (explicit lower/upper):
    python -m grid_trading.cli \\
        --symbol BTC/USDT --lower 40000 --upper 60000 \\
        --count 20 --capital 10000 --fee 0.001 \\
        --type geometric --backtest sine --out report.html --open

Auto mode (real data + auto-recommended bounds):
    python -m grid_trading.cli --auto 600519 --capital 50000 --open
    python -m grid_trading.cli --auto BTC/USDT --capital 10000 --backtest auto --open
    python -m grid_trading.cli --auto AAPL --capital 5000 --method atr --open
"""

from __future__ import annotations

import argparse
import json
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
    # ---- manual mode ----
    p.add_argument("--symbol", default="BTC/USDT", help="Trading pair label (for display).")
    p.add_argument("--lower",  type=float, help="Lower price boundary (manual mode).")
    p.add_argument("--upper",  type=float, help="Upper price boundary (manual mode).")
    p.add_argument("--count",  type=int,   help="Grid count (manual mode).")
    p.add_argument("--capital", type=float, default=10000.0, help="Total capital to allocate.")
    p.add_argument("--fee",    type=float, default=0.001, help="Fee rate as decimal (0.001 = 0.1%%).")
    p.add_argument("--type",   choices=["arithmetic", "geometric"], default="geometric",
                   dest="grid_type", help="Grid type.")
    p.add_argument("--stop-loss",   type=float, default=None, dest="stop_loss_price")
    p.add_argument("--take-profit", type=float, default=None, dest="take_profit_price")

    # ---- auto mode ----
    p.add_argument(
        "--auto",
        metavar="SYMBOL",
        help=(
            "Fetch real data for SYMBOL (A/HK/US/crypto) and auto-recommend "
            "bounds, grid type & count. Overrides --lower/--upper/--count/--type/--symbol."
        ),
    )
    p.add_argument("--window", type=int, default=120,
                   help="Bars analyzed in auto mode (default 120 ≈ 6 months daily).")
    p.add_argument("--method", choices=["sigma", "atr", "quantile"], default="sigma",
                   help="Bound-derivation method (auto mode).")
    p.add_argument("--safety", type=float, default=1.0,
                   help="Bound safety multiplier (auto mode, 1.0=neutral, 1.2=wider).")
    p.add_argument("--max-grids", type=int, default=60,
                   help="Hard cap on auto-recommended grid count.")

    # ---- backtest / output ----
    p.add_argument(
        "--backtest",
        choices=["none", "sine", "trending-down", "volatile", "auto"],
        default="none",
        help="Run a backtest. 'auto' replays real K-line history (auto mode only).",
    )
    p.add_argument("--out", default="grid_report.html", help="Output HTML file path.")
    p.add_argument("--open", action="store_true", help="Open the report in default browser after write.")
    p.add_argument("--quiet", action="store_true", help="Suppress stdout chatter; only print the output path.")
    p.add_argument("--json", action="store_true",
                   help="Print the params + recommendation as JSON instead of generating HTML.")
    return p


# ---------------------------------------------------------------------------
# Auto mode: fetch real data + recommend bounds
# ---------------------------------------------------------------------------

def _resolve_auto(args, params: dict) -> dict | None:
    """Mutate ``params`` in-place with auto-recommended values. Return rec dict."""
    from grid_trading.recommend import recommend_grid

    rec = recommend_grid(
        symbol=args.auto,
        capital=args.capital,
        fee_rate=args.fee,
        window=args.window,
        method=args.method,
        max_grids=args.max_grids,
        safety=args.safety,
    )
    if rec is None:
        print(f"[ERROR] Failed to fetch real data for symbol: {args.auto}", file=sys.stderr)
        print("[HINT]  Check network access. Verify symbol format "
              "(A=600519, HK=00700, US=AAPL, crypto=BTC/USDT).", file=sys.stderr)
        return None

    quote_name = (rec.quote or {}).get("name") if rec.quote else None
    params["symbol"] = quote_name or args.auto
    params["price_lower"] = rec.price_lower
    params["price_upper"] = rec.price_upper
    params["grid_count"] = rec.grid_count
    params["grid_type"] = rec.grid_type
    return rec.to_dict()


# ---------------------------------------------------------------------------
# Backtest dispatch
# ---------------------------------------------------------------------------

def _run_backtest(kind: str, params: dict, *, auto_symbol: str | None = None) -> dict | None:
    if kind == "none":
        return None
    from grid_trading.strategy.grid_strategy import GridConfig, GridStrategy
    from grid_trading.backtest.simulator import BacktestSimulator
    from grid_trading.tests.mock_data import sine_wave, trending_down, volatile_spike

    if kind == "auto":
        if not auto_symbol:
            print("[WARN] --backtest auto requires --auto; falling back to sine.", file=sys.stderr)
            kind = "sine"
        else:
            from grid_trading.data import fetch_kline
            # Replay the same window the recommender used so that bounds
            # match the historical price range — otherwise older bars
            # outside the analysis window can spuriously breach the upper /
            # lower bound and pollute the report. Pass --window to widen.
            bt_bars = params.get("window") or 120
            bars = fetch_kline(auto_symbol, period="daily", bars=bt_bars)
            if not bars:
                print("[WARN] couldn't fetch K-line for backtest; falling back to sine.", file=sys.stderr)
                kind = "sine"
            else:
                series = [(b.timestamp, b.close) for b in bars]

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
    elif kind == "volatile":
        series = volatile_spike(base_price=mid, points=500)
    # else: kind == "auto" — series already prepared above

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


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

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
        "window": args.window,
    }

    recommendation: dict | None = None
    if args.auto:
        recommendation = _resolve_auto(args, params)
        if recommendation is None:
            return 3
    else:
        # manual mode: enforce required args
        missing = [k for k, v in {"--lower": args.lower, "--upper": args.upper,
                                  "--count": args.count}.items() if v is None]
        if missing:
            print(f"[ERROR] Manual mode requires {', '.join(missing)} "
                  "(or use --auto SYMBOL for real-data mode).", file=sys.stderr)
            return 2

    builder = GridBuilder(fee_rate=args.fee)
    build_fn = (
        builder.build_geometric if params["grid_type"] == "geometric"
        else builder.build_arithmetic
    )
    try:
        grids = build_fn(
            lower=params["price_lower"], upper=params["price_upper"],
            n=params["grid_count"], capital=args.capital,
        )
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        rec_n = builder.recommend_grid_count(
            params["price_lower"], params["price_upper"], args.fee
        )
        print(f"[HINT]  Try --count {rec_n} or widen the range.", file=sys.stderr)
        return 2

    summary = builder.summary(grids)
    backtest = _run_backtest(args.backtest, params, auto_symbol=args.auto)
    risk_alerts = backtest.pop("risk_alerts", None) if backtest else None

    if args.json:
        print(json.dumps({
            "params": params,
            "summary": summary,
            "recommendation": recommendation,
            "backtest": backtest,
        }, ensure_ascii=False, indent=2, default=str))
        return 0

    html_doc = render_html_report(
        params=params,
        grids=grids,
        summary=summary,
        backtest=backtest,
        risk_alerts=risk_alerts,
        recommendation=recommendation,
    )

    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_doc, encoding="utf-8")

    if not args.quiet:
        if recommendation:
            print(f"✓ Auto: {recommendation.get('symbol', args.auto)} "
                  f"current={recommendation['current_price']:.4f} "
                  f"mid={recommendation['mid_price']:.4f} "
                  f"range=[{recommendation['price_lower']:.4f}, "
                  f"{recommendation['price_upper']:.4f}] "
                  f"({recommendation['grid_count']} grids, {recommendation['grid_type']})")
        print(f"✓ Grid built: {len(grids)} levels, type={params['grid_type']}")
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
