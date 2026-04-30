"""Real-time quote fetcher with cross-source fallback.

Source priority (per user spec):
    1. 东方财富 push2  (eastmoney)
    2. 雪球           (xueqiu)
    3. 腾讯           (qt.gtimg.cn)
    4. 新浪           (hq.sinajs.cn)
    5. 百度 / Yahoo   (US/HK fallbacks)

Returns a uniform :class:`Quote` regardless of upstream shape. Each source
is wrapped in try/except — a failure simply falls through to the next.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from grid_trading.data.http import http_get, http_get_json
from grid_trading.data.symbol import Symbol, normalize_symbol


@dataclass
class Quote:
    """Snapshot of a tradable asset's current state."""

    symbol: str
    name: str = ""
    price: float = 0.0
    change_pct: float = 0.0           # decimal, e.g. 0.0123 = +1.23%
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    prev_close: float = 0.0
    volume: float = 0.0
    turnover: float = 0.0              # 成交额
    pe_ttm: float | None = None
    pb: float | None = None
    market_cap: float | None = None
    currency: str = ""
    source: str = ""                   # which upstream produced this
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_quote(raw_symbol: str) -> Quote | None:
    """Fetch a real-time quote, trying multiple sources in order.

    Returns ``None`` only if every source fails.
    """
    sym = normalize_symbol(raw_symbol)
    if sym.market == "unknown" or not sym.code:
        return None

    sources = _source_chain(sym.market)
    for src in sources:
        try:
            q = src(sym)
        except Exception:
            q = None
        if q and q.price > 0:
            return q
    return None


# ---------------------------------------------------------------------------
# Source chain selection
# ---------------------------------------------------------------------------

def _source_chain(market: str):
    if market == "a-share":
        return [_eastmoney_quote, _sina_quote, _tencent_quote]
    if market == "hk":
        return [_eastmoney_quote, _sina_quote, _tencent_quote, _yahoo_quote]
    if market == "us":
        return [_yahoo_quote, _eastmoney_quote, _sina_quote]
    if market == "crypto":
        return [_binance_quote]
    return []


# ---------------------------------------------------------------------------
# Eastmoney push2
# ---------------------------------------------------------------------------

# field map (eastmoney push2 — public web endpoint)
# f43=price, f44=high, f45=low, f46=open, f47=volume, f48=turnover,
# f57=code, f58=name, f60=prev_close, f162=pe_ttm, f167=pb, f170=change_pct, f116=market_cap
_EM_FIELDS = "f43,f44,f45,f46,f47,f48,f57,f58,f60,f162,f167,f170,f116"

def _eastmoney_quote(sym: Symbol) -> Quote | None:
    secid = sym.eastmoney_secid
    if not secid:
        return None
    data = http_get_json(
        "https://push2.eastmoney.com/api/qt/stock/get",
        params={
            "secid": secid,
            "fields": _EM_FIELDS,
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "invt": "2",
            "fltt": "2",
        },
        headers={"Referer": "https://quote.eastmoney.com/"},
    )
    if not data or not isinstance(data, dict):
        return None
    d = data.get("data") or {}
    if not d or not d.get("f43"):
        return None
    price = _to_float(d.get("f43"))
    return Quote(
        symbol=sym.raw,
        name=str(d.get("f58") or ""),
        price=price,
        change_pct=_to_float(d.get("f170")) / 100.0,
        open=_to_float(d.get("f46")),
        high=_to_float(d.get("f44")),
        low=_to_float(d.get("f45")),
        prev_close=_to_float(d.get("f60")),
        volume=_to_float(d.get("f47")),
        turnover=_to_float(d.get("f48")),
        pe_ttm=_or_none(d.get("f162")),
        pb=_or_none(d.get("f167")),
        market_cap=_or_none(d.get("f116")),
        currency="CNY" if sym.market == "a-share" else ("HKD" if sym.market == "hk" else "USD"),
        source="eastmoney",
    )


# ---------------------------------------------------------------------------
# Sina hq
# ---------------------------------------------------------------------------

def _sina_quote(sym: Symbol) -> Quote | None:
    code = sym.sina_code
    if not code:
        return None
    body = http_get(
        f"https://hq.sinajs.cn/list={code}",
        headers={"Referer": "https://finance.sina.com.cn/"},
    )
    if not body or "=" not in body:
        return None
    payload = body.split("=", 1)[1].strip().strip(';"').strip('"')
    parts = payload.split(",")
    if len(parts) < 6:
        return None

    if sym.market == "a-share":
        # 0:name, 1:open, 2:prev_close, 3:price, 4:high, 5:low, 8:volume, 9:turnover
        name = parts[0]
        return Quote(
            symbol=sym.raw, name=name,
            price=_to_float(parts[3]),
            open=_to_float(parts[1]),
            prev_close=_to_float(parts[2]),
            high=_to_float(parts[4]),
            low=_to_float(parts[5]),
            volume=_to_float(parts[8]) if len(parts) > 8 else 0.0,
            turnover=_to_float(parts[9]) if len(parts) > 9 else 0.0,
            change_pct=_pct(parts[3], parts[2]),
            currency="CNY",
            source="sina",
        )
    if sym.market == "hk":
        # English name, CN name, open, prev_close, high, low, price, change, change_pct
        return Quote(
            symbol=sym.raw, name=parts[1] if len(parts) > 1 else "",
            open=_to_float(parts[2]) if len(parts) > 2 else 0.0,
            prev_close=_to_float(parts[3]) if len(parts) > 3 else 0.0,
            high=_to_float(parts[4]) if len(parts) > 4 else 0.0,
            low=_to_float(parts[5]) if len(parts) > 5 else 0.0,
            price=_to_float(parts[6]) if len(parts) > 6 else 0.0,
            change_pct=_to_float(parts[8]) / 100.0 if len(parts) > 8 else 0.0,
            currency="HKD",
            source="sina",
        )
    if sym.market == "us":
        # name, price, ?, datetime, change, open, high, low, prev, volume, ...
        return Quote(
            symbol=sym.raw, name=parts[0],
            price=_to_float(parts[1]),
            open=_to_float(parts[5]) if len(parts) > 5 else 0.0,
            high=_to_float(parts[6]) if len(parts) > 6 else 0.0,
            low=_to_float(parts[7]) if len(parts) > 7 else 0.0,
            prev_close=_to_float(parts[26]) if len(parts) > 26 else 0.0,
            volume=_to_float(parts[10]) if len(parts) > 10 else 0.0,
            change_pct=_to_float(parts[2]) / 100.0 if len(parts) > 2 else 0.0,
            currency="USD",
            source="sina",
        )
    return None


# ---------------------------------------------------------------------------
# Tencent qt.gtimg.cn
# ---------------------------------------------------------------------------

def _tencent_quote(sym: Symbol) -> Quote | None:
    code = sym.sina_code or _tencent_us_code(sym)
    if not code:
        return None
    body = http_get(f"https://qt.gtimg.cn/q={code}")
    if "=" not in body:
        return None
    payload = body.split("=", 1)[1].strip().strip(';"').strip('"')
    parts = payload.split("~")
    if len(parts) < 10:
        return None

    # Tencent layout (A-share / HK):
    # 1:name, 2:code, 3:price, 4:prev_close, 5:open, 6:volume, ..., 33:high(?), 34:low, ...
    return Quote(
        symbol=sym.raw, name=parts[1],
        price=_to_float(parts[3]),
        prev_close=_to_float(parts[4]),
        open=_to_float(parts[5]),
        volume=_to_float(parts[6]),
        high=_to_float(parts[33]) if len(parts) > 33 else 0.0,
        low=_to_float(parts[34]) if len(parts) > 34 else 0.0,
        change_pct=_pct(parts[3], parts[4]),
        currency="CNY" if sym.market == "a-share" else ("HKD" if sym.market == "hk" else "USD"),
        source="tencent",
    )


def _tencent_us_code(sym: Symbol) -> str:
    if sym.market == "us":
        return f"usAAPL.OQ".replace("AAPL", sym.code)  # not reliably documented; left as fallback
    return ""


# ---------------------------------------------------------------------------
# Yahoo Finance (US / HK fallback)
# ---------------------------------------------------------------------------

def _yahoo_quote(sym: Symbol) -> Quote | None:
    code = sym.yahoo_code
    if not code:
        return None
    data = http_get_json(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{code}",
        params={"range": "1d", "interval": "1d"},
    )
    try:
        result = data["chart"]["result"][0]
        meta = result.get("meta", {})
    except (KeyError, IndexError, TypeError):
        return None

    price = _to_float(meta.get("regularMarketPrice"))
    prev = _to_float(meta.get("chartPreviousClose") or meta.get("previousClose"))
    if price <= 0:
        return None

    return Quote(
        symbol=sym.raw,
        name=str(meta.get("symbol") or sym.code),
        price=price,
        prev_close=prev,
        change_pct=(price - prev) / prev if prev > 0 else 0.0,
        currency=str(meta.get("currency") or ""),
        source="yahoo",
        extra={"exchange": meta.get("exchangeName", "")},
    )


# ---------------------------------------------------------------------------
# Binance (crypto)
# ---------------------------------------------------------------------------

def _binance_quote(sym: Symbol) -> Quote | None:
    pair = (sym.base + sym.quote).upper() or sym.code.upper()
    data = http_get_json(
        "https://api.binance.com/api/v3/ticker/24hr",
        params={"symbol": pair},
    )
    if not data or not isinstance(data, dict) or "lastPrice" not in data:
        return None
    return Quote(
        symbol=sym.raw,
        name=pair,
        price=_to_float(data.get("lastPrice")),
        open=_to_float(data.get("openPrice")),
        high=_to_float(data.get("highPrice")),
        low=_to_float(data.get("lowPrice")),
        prev_close=_to_float(data.get("prevClosePrice")),
        volume=_to_float(data.get("volume")),
        turnover=_to_float(data.get("quoteVolume")),
        change_pct=_to_float(data.get("priceChangePercent")) / 100.0,
        currency=sym.quote or "USDT",
        source="binance",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "" or v == "-":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _or_none(v: Any) -> float | None:
    f = _to_float(v, default=float("nan"))
    if f != f:           # NaN
        return None
    return f if f != 0.0 else None


def _pct(price: Any, prev: Any) -> float:
    p = _to_float(price)
    pc = _to_float(prev)
    return (p - pc) / pc if pc > 0 else 0.0
