"""Compute (mid_price, lower, upper, grid_count, grid_type) from real K-line data.

Method (deterministic, transparent — no ML black box):

    1. Use the most recent ``window`` daily bars (default 120 ~ 6 months).
    2. Mid-line price (建议中线价):
         - Take the median of closes (robust to spikes).
         - Blend with the latest close 30% so it tracks the present:
             mid = 0.7 * median + 0.3 * last_close.
    3. Volatility — use ATR-style true-range over the window.
    4. Bounds:
         - σ-mode (default): mid ± k * stdev_of_close, k=2.0.
         - atr-mode: mid ± k * mean_atr, k=8.0.
         - quantile-mode: 10%/90% close percentiles, anchored on mid.
       Final bounds are also clamped to ``[min_low, max_high]`` of window.
    5. Grid type:
         - geometric for prices spanning > 1.5x or with ratio >5%/level.
         - arithmetic otherwise (small price ranges, e.g. bonds, rate-bound).
    6. Grid count: largest integer N such that step_ratio > 2 × fee_rate
       (matches GridBuilder.recommend_grid_count). Capped to ``max_grids``.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from grid_trading.core.grid_builder import GridBuilder
from grid_trading.data import fetch_kline, fetch_quote
from grid_trading.data.kline import Bar
from grid_trading.data.quote import Quote


@dataclass
class GridRecommendation:
    """Result of an auto-grid analysis."""

    symbol: str
    market: str
    current_price: float
    mid_price: float          # 建议中线价
    price_lower: float        # 建议网格下限
    price_upper: float        # 建议网格上限
    grid_type: Literal["arithmetic", "geometric"]
    grid_count: int
    fee_rate: float
    method: str               # "sigma" | "atr" | "quantile"

    # diagnostics
    bars_analyzed: int
    window_high: float
    window_low: float
    median_close: float
    mean_close: float
    stdev_close: float
    atr: float
    min_step_ratio: float
    max_grid_count: int

    quote: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Plain dict (asdict) — for HTML report and JSON output."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def recommend_grid(
    symbol: str,
    *,
    capital: float = 10000.0,
    fee_rate: float = 0.001,
    window: int = 120,
    method: Literal["sigma", "atr", "quantile"] = "sigma",
    max_grids: int = 60,
    safety: float = 1.0,
) -> GridRecommendation | None:
    """Fetch real data for ``symbol`` and produce a grid recommendation.

    Args:
        symbol: Any cross-market symbol (see ``data.symbol.normalize_symbol``).
        capital: Used only to validate grid count yields a sensible per-grid
            capital — does not affect the price recommendation itself.
        fee_rate: Taker fee as decimal. Constrains grid count.
        window: Number of recent daily bars to analyze.
        method: Bound-derivation method.
        max_grids: Hard cap on returned grid count.
        safety: Multiplier on bound width (1.0 = neutral, 1.2 = 20% wider).

    Returns:
        :class:`GridRecommendation` or ``None`` if data couldn't be fetched.
    """
    bars = fetch_kline(symbol, period="daily", bars=max(window, 60))
    if not bars:
        return None
    quote = fetch_quote(symbol)
    return recommend_from_bars(
        symbol=symbol,
        bars=bars,
        quote=quote,
        capital=capital,
        fee_rate=fee_rate,
        window=window,
        method=method,
        max_grids=max_grids,
        safety=safety,
    )


def recommend_from_bars(
    *,
    symbol: str,
    bars: list[Bar],
    quote: Quote | None = None,
    capital: float = 10000.0,
    fee_rate: float = 0.001,
    window: int = 120,
    method: Literal["sigma", "atr", "quantile"] = "sigma",
    max_grids: int = 60,
    safety: float = 1.0,
) -> GridRecommendation:
    """Pure form usable from a backtest or precomputed data.

    Same parameters as :func:`recommend_grid` except ``bars`` and ``quote``
    are passed in directly. ``window`` is clamped to ``len(bars)``.
    """
    if not bars:
        raise ValueError("bars must be non-empty")

    bars = bars[-window:] if len(bars) > window else bars
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]

    last_close = closes[-1]
    median_close = statistics.median(closes)
    mean_close = statistics.fmean(closes)
    stdev_close = statistics.pstdev(closes) if len(closes) > 1 else 0.0
    atr = _atr(bars)

    # ---- Mid line: blend median with current ----
    current_price = quote.price if (quote and quote.price > 0) else last_close
    mid = 0.7 * median_close + 0.3 * current_price

    # ---- Bounds ----
    if method == "atr":
        half = 8.0 * atr * safety
    elif method == "quantile":
        sorted_c = sorted(closes)
        n = len(sorted_c)
        q10 = sorted_c[max(0, int(0.10 * n))]
        q90 = sorted_c[min(n - 1, int(0.90 * n))]
        # anchor q-band around mid, then re-widen by safety
        half = max(mid - q10, q90 - mid) * safety
    else:  # sigma
        half = 2.0 * stdev_close * safety

    if half <= 0 or half / mid < 0.02:   # safety floor 2%
        half = mid * 0.06

    lower = mid - half
    upper = mid + half

    # Clamp to window extremes — but never narrower than 80% of the σ band
    win_low, win_high = min(lows), max(highs)
    lower = max(lower, win_low * 0.97)
    upper = min(upper, win_high * 1.03)
    if lower <= 0:
        lower = mid * 0.5
    if upper <= lower:
        upper = lower * 1.1

    # ---- Grid type: geometric for >1.5x range, else arithmetic ----
    grid_type: Literal["arithmetic", "geometric"] = (
        "geometric" if (upper / lower) > 1.5 else "arithmetic"
    )

    # ---- Grid count: max N such that step_ratio > 2*fee_rate ----
    builder = GridBuilder(fee_rate=fee_rate)
    rec_n = builder.recommend_grid_count(lower, upper, fee_rate)
    grid_count = min(rec_n, max_grids)
    grid_count = max(grid_count, 6)

    # ---- Min step ratio (informational) ----
    if grid_type == "geometric":
        min_step_ratio = (upper / lower) ** (1.0 / grid_count) - 1.0
    else:
        min_step_ratio = (upper - lower) / (grid_count * lower)

    notes = _build_notes(
        method=method, fee_rate=fee_rate, atr=atr,
        stdev_close=stdev_close, mid=mid, lower=lower, upper=upper,
        current=current_price, grid_count=grid_count, capital=capital,
    )

    return GridRecommendation(
        symbol=symbol,
        market=(quote.source if quote else "") or "",
        current_price=round(current_price, 6),
        mid_price=round(mid, 6),
        price_lower=round(lower, 6),
        price_upper=round(upper, 6),
        grid_type=grid_type,
        grid_count=grid_count,
        fee_rate=fee_rate,
        method=method,
        bars_analyzed=len(bars),
        window_high=round(win_high, 6),
        window_low=round(win_low, 6),
        median_close=round(median_close, 6),
        mean_close=round(mean_close, 6),
        stdev_close=round(stdev_close, 6),
        atr=round(atr, 6),
        min_step_ratio=round(min_step_ratio, 6),
        max_grid_count=rec_n,
        quote=_quote_to_dict(quote),
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _atr(bars: list[Bar]) -> float:
    """Average True Range over all available bars (simple mean, not EMA)."""
    if len(bars) < 2:
        return 0.0
    trs: list[float] = []
    for i in range(1, len(bars)):
        b, prev = bars[i], bars[i - 1]
        tr = max(b.high - b.low,
                 abs(b.high - prev.close),
                 abs(b.low - prev.close))
        trs.append(tr)
    return statistics.fmean(trs) if trs else 0.0


def _quote_to_dict(q: Quote | None) -> dict[str, Any] | None:
    if q is None:
        return None
    return {
        "name": q.name,
        "price": q.price,
        "change_pct": q.change_pct,
        "open": q.open,
        "high": q.high,
        "low": q.low,
        "prev_close": q.prev_close,
        "pe_ttm": q.pe_ttm,
        "pb": q.pb,
        "market_cap": q.market_cap,
        "currency": q.currency,
        "source": q.source,
    }


def _build_notes(
    *, method: str, fee_rate: float, atr: float, stdev_close: float,
    mid: float, lower: float, upper: float, current: float,
    grid_count: int, capital: float,
) -> list[str]:
    notes: list[str] = []
    band_pct = (upper - lower) / mid * 100 if mid > 0 else 0
    notes.append(f"method={method}, band_width={band_pct:.2f}% of mid")
    notes.append(f"σ(close)={stdev_close:.4f}, ATR={atr:.4f}")
    if current < lower:
        notes.append(
            "⚠️ 当前价低于建议下限 — 趋势可能仍在下行，建议先观察止跌信号或缩小仓位再开网。"
        )
    elif current > upper:
        notes.append(
            "⚠️ 当前价高于建议上限 — 短期偏强，等回踩中线再开网或先开半仓。"
        )
    else:
        pos_pct = (current - lower) / (upper - lower) * 100
        notes.append(f"当前价处于网格区间 {pos_pct:.1f}% 位置（0=下限，100=上限）。")

    notes.append(
        f"按 {grid_count} 格分配，单格资金 ≈ {capital / grid_count:,.2f}，"
        f"单格收益率约 {(upper / lower) ** (1 / grid_count) - 1:.2%}（geo 等价）。"
    )
    if fee_rate * 2 * grid_count > 0.05:
        notes.append("提示: 当前格数下手续费占比较高，建议减少格数或选择低费率账户。")
    return notes
