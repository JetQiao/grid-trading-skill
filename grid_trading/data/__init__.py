"""Real-data layer — multi-source, no-API-key fetchers.

Public surface (stable):

    from grid_trading.data import (
        normalize_symbol, detect_market,
        fetch_quote, fetch_kline,
        fetch_fundamentals, fetch_flows, fetch_disclosures,
        fetch_macro_news, fetch_social_hot,
    )

Each ``fetch_*`` function tries a primary source first, then falls back to
secondary sources. None of them require an API key. Network failures degrade
to ``None`` / ``[]`` rather than raising — callers are expected to check.
"""

from grid_trading.data.symbol import detect_market, normalize_symbol  # noqa: F401
from grid_trading.data.quote import fetch_quote  # noqa: F401
from grid_trading.data.kline import fetch_kline  # noqa: F401
from grid_trading.data.fundamentals import fetch_fundamentals  # noqa: F401
from grid_trading.data.flows import fetch_flows  # noqa: F401
from grid_trading.data.disclosures import fetch_disclosures  # noqa: F401
from grid_trading.data.macro import fetch_macro_news  # noqa: F401
from grid_trading.data.social import fetch_social_hot  # noqa: F401

__all__ = [
    "detect_market",
    "normalize_symbol",
    "fetch_quote",
    "fetch_kline",
    "fetch_fundamentals",
    "fetch_flows",
    "fetch_disclosures",
    "fetch_macro_news",
    "fetch_social_hot",
]
