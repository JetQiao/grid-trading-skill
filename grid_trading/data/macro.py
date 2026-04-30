"""Macro / policy / sentiment / 杀猪盘 search via DuckDuckGo.

DuckDuckGo HTML endpoint is the only source per spec — no API key, no
crawl-rate enforcement beyond a polite UA. Results are best-effort and
should be treated as advisory signals, not facts.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any

from grid_trading.data.cache import cached
from grid_trading.data.http import http_get


def fetch_macro_news(
    query: str,
    *,
    limit: int = 10,
    cache_ttl: float = 600.0,
) -> list[dict[str, Any]]:
    """Search DuckDuckGo HTML for ``query`` and return parsed result rows.

    Args:
        query: Free-text search, e.g. ``"央行 降息 2026"`` or
            ``"贵州茅台 杀猪盘 风险"``.
        limit: Max rows to return.
        cache_ttl: File cache TTL in seconds (default 10 min).
    """
    key = f"macro:{query}:{limit}"
    return cached(key, cache_ttl, lambda: _ddg_search(query, limit)) or []


def _ddg_search(query: str, limit: int) -> list[dict[str, Any]]:
    q = urllib.parse.quote_plus(query)
    body = http_get(
        f"https://html.duckduckgo.com/html/?q={q}",
        headers={"Referer": "https://duckduckgo.com/"},
    )
    if not body:
        return []
    rows = _parse_ddg(body, limit)
    return rows


_RESULT_RE = re.compile(
    r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>'
    r'.*?(?:class="result__snippet"[^>]*>(.*?)</a>)?',
    re.DOTALL,
)


def _parse_ddg(body: str, limit: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in _RESULT_RE.finditer(body):
        if len(out) >= limit:
            break
        url = _unwrap(m.group(1))
        title = _strip_tags(m.group(2) or "")
        snippet = _strip_tags(m.group(3) or "")
        if not url or not title:
            continue
        out.append({"title": title, "url": url, "snippet": snippet})
    return out


def _strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s).strip()


def _unwrap(url: str) -> str:
    """DDG wraps redirects as ``//duckduckgo.com/l/?uddg=...`` — pull out target."""
    if url.startswith("//"):
        url = "https:" + url
    parsed = urllib.parse.urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs:
            return urllib.parse.unquote(qs["uddg"][0])
    return url
