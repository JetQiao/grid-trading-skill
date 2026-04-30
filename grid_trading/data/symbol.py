"""Symbol parsing and per-source code mapping.

A single user-facing symbol like ``600519`` or ``BTC/USDT`` is rewritten
into the codes each upstream API expects:

    - Eastmoney secid:  ``1.600519`` (SH) / ``0.000001`` (SZ) / ``116.00700`` (HK) / ``105.AAPL`` (US)
    - Sina list code:   ``sh600519`` / ``sz000001`` / ``hk00700`` / ``gb_aapl``
    - Tencent code:     same as sina
    - Yahoo / yfinance: ``600519.SS`` / ``000001.SZ`` / ``0700.HK`` / ``AAPL``
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Market = Literal["a-share", "hk", "us", "crypto", "fund", "index", "unknown"]


@dataclass(frozen=True)
class Symbol:
    """Normalized cross-market identifier."""

    raw: str               # original user input
    market: Market
    code: str              # bare numeric / ticker code, no prefix
    base: str = ""         # crypto base, e.g. ``BTC``
    quote: str = ""        # crypto quote, e.g. ``USDT``
    name: str = ""         # display name (filled in opportunistically)

    # ---- per-source codes ----
    @property
    def eastmoney_secid(self) -> str:
        if self.market == "a-share":
            return f"{_sh_or_sz(self.code)}.{self.code}"
        if self.market == "hk":
            return f"116.{self.code.zfill(5)}"
        if self.market == "us":
            return f"105.{self.code.upper()}"
        if self.market == "index":
            return f"{_index_market(self.code)}.{self.code}"
        return ""

    @property
    def sina_code(self) -> str:
        if self.market == "a-share":
            return f"{'sh' if _sh_or_sz(self.code) == '1' else 'sz'}{self.code}"
        if self.market == "hk":
            return f"hk{self.code.zfill(5)}"
        if self.market == "us":
            return f"gb_{self.code.lower()}"
        return ""

    @property
    def yahoo_code(self) -> str:
        if self.market == "a-share":
            return f"{self.code}.{'SS' if _sh_or_sz(self.code) == '1' else 'SZ'}"
        if self.market == "hk":
            return f"{self.code.lstrip('0').zfill(4)}.HK"
        if self.market == "us":
            return self.code.upper()
        if self.market == "crypto":
            return f"{self.base}-{self.quote}"
        return ""


def normalize_symbol(raw: str) -> Symbol:
    """Parse a user symbol into a :class:`Symbol` with market routing.

    Accepted forms:
        - ``600519`` / ``sh600519`` / ``600519.SH``       → A-share
        - ``000001`` / ``sz000001`` / ``000001.SZ``       → A-share (SZ)
        - ``00700`` / ``hk00700`` / ``0700.HK``           → HK
        - ``AAPL`` / ``aapl`` / ``us_AAPL``               → US
        - ``BTC/USDT`` / ``BTCUSDT`` / ``BTC-USDT``       → crypto
    """
    s = raw.strip()
    if not s:
        return Symbol(raw=raw, market="unknown", code="")

    upper = s.upper()
    # crypto: contains / or - between known quote currencies, or ends in USDT/USDC/USD
    if "/" in upper or "-" in upper:
        base, _, quote = upper.replace("-", "/").partition("/")
        if base and quote:
            return Symbol(raw=raw, market="crypto", code=f"{base}{quote}",
                          base=base, quote=quote)
    for q in ("USDT", "USDC", "USD", "BUSD", "FDUSD"):
        if upper.endswith(q) and len(upper) > len(q):
            base = upper[: -len(q)]
            return Symbol(raw=raw, market="crypto", code=upper,
                          base=base, quote=q)

    # explicit prefix / suffix
    low = s.lower()
    if low.startswith("sh") and s[2:].isdigit():
        return Symbol(raw=raw, market="a-share", code=s[2:])
    if low.startswith("sz") and s[2:].isdigit():
        return Symbol(raw=raw, market="a-share", code=s[2:])
    if low.startswith("hk") and s[2:].lstrip("0").isdigit():
        return Symbol(raw=raw, market="hk", code=s[2:])
    if upper.endswith(".SS") or upper.endswith(".SH"):
        return Symbol(raw=raw, market="a-share", code=upper.split(".")[0])
    if upper.endswith(".SZ"):
        return Symbol(raw=raw, market="a-share", code=upper.split(".")[0])
    if upper.endswith(".HK"):
        return Symbol(raw=raw, market="hk", code=upper.split(".")[0].zfill(5))

    # bare digits
    if s.isdigit():
        if len(s) == 6:
            return Symbol(raw=raw, market="a-share", code=s)
        if 4 <= len(s) <= 5:
            return Symbol(raw=raw, market="hk", code=s.zfill(5))

    # bare alpha → US ticker
    if upper.isalpha() and 1 <= len(upper) <= 6:
        return Symbol(raw=raw, market="us", code=upper)

    return Symbol(raw=raw, market="unknown", code=s)


def detect_market(raw: str) -> Market:
    """Lightweight wrapper returning just the market for a raw symbol."""
    return normalize_symbol(raw).market


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _sh_or_sz(code: str) -> str:
    """Eastmoney secid prefix: '1' for SH, '0' for SZ.

    Heuristic by leading digit:
        - 6 / 9                     → Shanghai (1)
        - 5 (ETF/LOF on SH)         → Shanghai (1)
        - 0 / 1 / 2 / 3 / 4 / 7 / 8 → Shenzhen (0)
    """
    if not code:
        return "0"
    head = code[0]
    if head in ("6", "9"):
        return "1"
    if head == "5":
        return "1"
    return "0"


def _index_market(code: str) -> str:
    """Eastmoney secid prefix for indices."""
    if code.startswith(("000", "880")):
        return "1"
    return "0"
