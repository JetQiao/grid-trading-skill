"""K-line (candle) fetcher with cross-source fallback.

Source priority:
    A-share / HK / Index — 东方财富 push2his → akshare (optional) → yahoo
    US                   — yahoo → akshare (optional)
    Crypto               — binance

Returns a list of :class:`Bar` objects in chronological order. Empty list
on total failure (callers should check ``if bars:``).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from grid_trading.data.http import http_get_json
from grid_trading.data.symbol import Symbol, normalize_symbol


@dataclass
class Bar:
    """OHLC bar."""

    timestamp: float       # unix seconds (UTC midnight for daily bars)
    date: str              # YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    turnover: float = 0.0


# klt: 101=daily, 102=weekly, 103=monthly, 5/15/30/60=intraday minutes
_EM_KLT = {"daily": 101, "weekly": 102, "monthly": 103,
           "1m": 1, "5m": 5, "15m": 15, "30m": 30, "60m": 60}
_YH_INTERVAL = {"daily": "1d", "weekly": "1wk", "monthly": "1mo",
                "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "60m": "60m"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_kline(
    raw_symbol: str,
    *,
    period: str = "daily",
    bars: int = 180,
    adjust: str = "qfq",
) -> list[Bar]:
    """Fetch ``bars`` recent OHLC bars at the given ``period``.

    Args:
        raw_symbol: User symbol, e.g. ``600519``, ``00700``, ``AAPL``,
            ``BTC/USDT``.
        period: ``daily`` | ``weekly`` | ``monthly`` | ``1m`` | ``5m`` |
            ``15m`` | ``30m`` | ``60m``.
        bars: Approximate number of recent bars to return.
        adjust: For A-share/HK only — ``qfq`` (前复权) | ``hfq`` | ``none``.

    Returns:
        Chronologically ordered list of Bars; possibly empty.
    """
    sym = normalize_symbol(raw_symbol)
    if sym.market == "unknown" or not sym.code:
        return []

    chain = _source_chain(sym.market)
    for src in chain:
        try:
            out = src(sym, period=period, bars=bars, adjust=adjust)
        except Exception:
            out = []
        if out:
            return out
    return []


def _source_chain(market: str):
    if market == "a-share":
        return [_eastmoney_kline, _akshare_kline, _yahoo_kline]
    if market == "hk":
        return [_eastmoney_kline, _akshare_kline, _yahoo_kline]
    if market == "us":
        return [_yahoo_kline, _akshare_kline, _eastmoney_kline]
    if market == "index":
        return [_eastmoney_kline, _yahoo_kline]
    if market == "crypto":
        return [_binance_kline]
    return []


# ---------------------------------------------------------------------------
# Eastmoney push2his
# ---------------------------------------------------------------------------

# fields: f51=date, f52=open, f53=close, f54=high, f55=low, f56=volume, f57=turnover
_EM_KLINE_FIELDS = "f51,f52,f53,f54,f55,f56,f57"
_FQT = {"none": 0, "qfq": 1, "hfq": 2}

def _eastmoney_kline(sym: Symbol, *, period: str, bars: int, adjust: str) -> list[Bar]:
    secid = sym.eastmoney_secid
    klt = _EM_KLT.get(period, 101)
    if not secid:
        return []
    data = http_get_json(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        params={
            "secid": secid,
            "klt": klt,
            "fqt": _FQT.get(adjust, 1),
            "lmt": max(bars, 30),
            "fields1": "f1,f2,f3,f4,f5",
            "fields2": _EM_KLINE_FIELDS,
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "end": "20500101",
        },
        headers={"Referer": "https://quote.eastmoney.com/"},
    )
    try:
        rows = data["data"]["klines"]
    except (KeyError, TypeError):
        return []

    out: list[Bar] = []
    for line in rows:
        parts = line.split(",")
        if len(parts) < 6:
            continue
        try:
            d = parts[0]
            ts = _date_to_ts(d)
            out.append(Bar(
                timestamp=ts, date=d,
                open=float(parts[1]),
                close=float(parts[2]),
                high=float(parts[3]),
                low=float(parts[4]),
                volume=float(parts[5]),
                turnover=float(parts[6]) if len(parts) > 6 else 0.0,
            ))
        except (ValueError, IndexError):
            continue
    return out[-bars:]


# ---------------------------------------------------------------------------
# Yahoo Finance
# ---------------------------------------------------------------------------

_RANGE_FOR_BARS = [
    (5, "5d"), (22, "1mo"), (65, "3mo"), (130, "6mo"),
    (260, "1y"), (520, "2y"), (1300, "5y"), (10_000, "10y"),
]

def _yahoo_kline(sym: Symbol, *, period: str, bars: int, adjust: str) -> list[Bar]:
    code = sym.yahoo_code
    if not code:
        return []
    interval = _YH_INTERVAL.get(period, "1d")
    rng = next((r for limit, r in _RANGE_FOR_BARS if bars <= limit), "max")

    data = http_get_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{code}",
        params={"range": rng, "interval": interval, "includePrePost": "false"},
    )
    try:
        result = data["chart"]["result"][0]
        ts_list = result["timestamp"]
        ind = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError):
        return []

    opens = ind.get("open") or []
    highs = ind.get("high") or []
    lows = ind.get("low") or []
    closes = ind.get("close") or []
    vols = ind.get("volume") or []

    out: list[Bar] = []
    for i, ts in enumerate(ts_list):
        try:
            o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        except IndexError:
            continue
        if None in (o, h, l, c):
            continue
        d = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        out.append(Bar(
            timestamp=float(ts), date=d,
            open=float(o), high=float(h), low=float(l), close=float(c),
            volume=float(vols[i] or 0) if i < len(vols) else 0.0,
        ))
    return out[-bars:]


# ---------------------------------------------------------------------------
# Binance kline (crypto)
# ---------------------------------------------------------------------------

_BN_INTERVAL = {"daily": "1d", "weekly": "1w", "monthly": "1M",
                "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m", "60m": "1h"}

def _binance_kline(sym: Symbol, *, period: str, bars: int, adjust: str) -> list[Bar]:
    pair = (sym.base + sym.quote).upper() or sym.code.upper()
    interval = _BN_INTERVAL.get(period, "1d")
    data = http_get_json(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": pair, "interval": interval, "limit": min(bars, 1000)},
    )
    if not isinstance(data, list):
        return []
    out: list[Bar] = []
    for row in data:
        try:
            open_t = float(row[0]) / 1000.0
            d = datetime.utcfromtimestamp(open_t).strftime("%Y-%m-%d")
            out.append(Bar(
                timestamp=open_t, date=d,
                open=float(row[1]), high=float(row[2]),
                low=float(row[3]), close=float(row[4]),
                volume=float(row[5]),
                turnover=float(row[7]),
            ))
        except (ValueError, IndexError, TypeError):
            continue
    return out


# ---------------------------------------------------------------------------
# Optional: akshare (only used if installed)
# ---------------------------------------------------------------------------

def _akshare_kline(sym: Symbol, *, period: str, bars: int, adjust: str) -> list[Bar]:
    """Lazy akshare adapter — returns [] if akshare is not installed."""
    try:
        import akshare as ak  # type: ignore
    except ImportError:
        return []

    df = None
    try:
        if sym.market == "a-share":
            df = ak.stock_zh_a_hist(
                symbol=sym.code,
                period=period if period in ("daily", "weekly", "monthly") else "daily",
                adjust={"qfq": "qfq", "hfq": "hfq", "none": ""}.get(adjust, "qfq"),
            )
        elif sym.market == "hk":
            df = ak.stock_hk_hist(
                symbol=sym.code.zfill(5),
                period=period if period in ("daily", "weekly", "monthly") else "daily",
                adjust={"qfq": "qfq", "hfq": "hfq", "none": ""}.get(adjust, "qfq"),
            )
        elif sym.market == "us":
            df = ak.stock_us_hist(symbol=sym.code.upper(), period="daily")
    except Exception:
        return []

    if df is None or len(df) == 0:
        return []

    # Normalize column names — akshare uses Chinese column names
    cols = {c: c for c in df.columns}
    rename_map = {
        "日期": "date", "开盘": "open", "收盘": "close",
        "最高": "high", "最低": "low",
        "成交量": "volume", "成交额": "turnover",
    }
    out: list[Bar] = []
    for _, row in df.tail(bars).iterrows():
        try:
            d = str(row[cols.get("日期", "date")])
            d = d[:10]
            ts = _date_to_ts(d)
            out.append(Bar(
                timestamp=ts, date=d,
                open=float(row[cols.get("开盘", "open")]),
                high=float(row[cols.get("最高", "high")]),
                low=float(row[cols.get("最低", "low")]),
                close=float(row[cols.get("收盘", "close")]),
                volume=float(row.get(cols.get("成交量", "volume"), 0) or 0),
                turnover=float(row.get(cols.get("成交额", "turnover"), 0) or 0),
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return out


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_to_ts(d: str) -> float:
    """Parse ``YYYY-MM-DD`` (or ``YYYYMMDD``, with optional time) to UTC seconds."""
    s = d.replace("/", "-").strip()
    fmt_candidates = [
        "%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
        "%Y%m%d", "%Y%m%d%H%M",
    ]
    for fmt in fmt_candidates:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.timestamp()
        except ValueError:
            continue
    return time.time()
