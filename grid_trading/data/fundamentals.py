"""Financial fundamentals (PE/PB/ROE/profit history).

Source priority:
    A-share: akshare (if installed) → eastmoney f10
    HK / US: yfinance / yahoo quoteSummary
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from grid_trading.data.http import http_get_json
from grid_trading.data.symbol import Symbol, normalize_symbol


@dataclass
class Fundamentals:
    symbol: str
    name: str = ""
    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    roe: float | None = None
    eps: float | None = None
    bps: float | None = None
    market_cap: float | None = None
    revenue_yoy: float | None = None     # decimal (e.g. 0.124 = +12.4%)
    profit_yoy: float | None = None
    dividend_yield: float | None = None
    industry: str = ""
    source: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


def fetch_fundamentals(raw_symbol: str) -> Fundamentals | None:
    sym = normalize_symbol(raw_symbol)
    if sym.market == "unknown":
        return None
    chain = _chain(sym.market)
    for src in chain:
        try:
            f = src(sym)
        except Exception:
            f = None
        if f and (f.pe_ttm or f.pb or f.market_cap):
            return f
    return None


def _chain(market: str):
    if market == "a-share":
        return [_akshare_fund_a, _eastmoney_fund]
    if market == "hk":
        return [_eastmoney_fund, _yahoo_fund]
    if market == "us":
        return [_yahoo_fund, _akshare_fund_us]
    return []


# ---------------------------------------------------------------------------
# Eastmoney F10 (covers A and HK)
# ---------------------------------------------------------------------------

def _eastmoney_fund(sym: Symbol) -> Fundamentals | None:
    secid = sym.eastmoney_secid
    if not secid:
        return None
    # f43=price, f57=code, f58=name, f116=market_cap, f162=pe_ttm,
    # f167=pb, f164=industry(?), f173=roe, f184=eps
    fields = "f57,f58,f116,f162,f167,f164,f173,f184,f186,f191,f192,f168"
    data = http_get_json(
        "https://push2.eastmoney.com/api/qt/stock/get",
        params={"secid": secid, "fields": fields, "ut": "fa5fd1943c7b386f172d6893dbfba10b"},
        headers={"Referer": "https://quote.eastmoney.com/"},
    )
    try:
        d = data["data"]
    except (KeyError, TypeError):
        return None

    return Fundamentals(
        symbol=sym.raw,
        name=str(d.get("f58") or ""),
        pe_ttm=_or_none(d.get("f162")),
        pb=_or_none(d.get("f167")),
        roe=_or_none(d.get("f173")),
        eps=_or_none(d.get("f184")),
        market_cap=_or_none(d.get("f116")),
        industry=str(d.get("f164") or ""),
        source="eastmoney",
        extra={k: d.get(k) for k in ("f186", "f191", "f192", "f168") if d.get(k) is not None},
    )


# ---------------------------------------------------------------------------
# Yahoo quoteSummary (US / HK)
# ---------------------------------------------------------------------------

def _yahoo_fund(sym: Symbol) -> Fundamentals | None:
    code = sym.yahoo_code
    if not code:
        return None
    modules = "summaryDetail,defaultKeyStatistics,financialData,price"
    data = http_get_json(
        f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{code}",
        params={"modules": modules},
    )
    try:
        result = data["quoteSummary"]["result"][0]
    except (KeyError, IndexError, TypeError):
        return None

    sd = result.get("summaryDetail") or {}
    ks = result.get("defaultKeyStatistics") or {}
    fd = result.get("financialData") or {}
    pr = result.get("price") or {}

    return Fundamentals(
        symbol=sym.raw,
        name=str(pr.get("longName", {}).get("raw") or pr.get("shortName", {}).get("raw") or ""),
        pe_ttm=_yh(sd.get("trailingPE")),
        pb=_yh(ks.get("priceToBook")),
        ps_ttm=_yh(sd.get("priceToSalesTrailing12Months")),
        roe=_yh(fd.get("returnOnEquity")),
        eps=_yh(ks.get("trailingEps")),
        bps=_yh(ks.get("bookValue")),
        market_cap=_yh(pr.get("marketCap")),
        revenue_yoy=_yh(fd.get("revenueGrowth")),
        profit_yoy=_yh(fd.get("earningsGrowth")),
        dividend_yield=_yh(sd.get("dividendYield")),
        industry=str(pr.get("quoteType", {}).get("raw") or ""),
        source="yahoo",
    )


def _yh(field: Any) -> float | None:
    if not isinstance(field, dict):
        return None
    raw = field.get("raw")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Optional akshare paths
# ---------------------------------------------------------------------------

def _akshare_fund_a(sym: Symbol) -> Fundamentals | None:
    try:
        import akshare as ak  # type: ignore
    except ImportError:
        return None
    try:
        df = ak.stock_individual_info_em(symbol=sym.code)
    except Exception:
        return None
    if df is None or len(df) == 0:
        return None
    info = dict(zip(df["item"], df["value"]))
    return Fundamentals(
        symbol=sym.raw,
        name=str(info.get("股票简称") or ""),
        market_cap=_to_float_or_none(info.get("总市值")),
        industry=str(info.get("行业") or ""),
        source="akshare",
        extra={k: v for k, v in info.items() if v not in (None, "")},
    )


def _akshare_fund_us(sym: Symbol) -> Fundamentals | None:
    return None  # left as scaffold


def _to_float_or_none(v: Any) -> float | None:
    if v in (None, "", "-"):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _or_none(v: Any) -> float | None:
    try:
        if v in (None, "", "-"):
            return None
        f = float(v)
        return None if f == 0.0 else f
    except (TypeError, ValueError):
        return None
