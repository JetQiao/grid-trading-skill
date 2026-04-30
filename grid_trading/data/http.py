"""Stdlib-only HTTP helpers.

Keeps the data layer dependency-free (no requests / httpx). All public
helpers swallow network errors and return ``None`` / ``""`` so callers can
do clean fall-through across multiple data sources.
"""

from __future__ import annotations

import gzip
import io
import json
import ssl
import urllib.parse
import urllib.request
from typing import Any

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 6.0

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _decode(raw: bytes, encoding: str = "utf-8") -> str:
    """Decode response body, handling gzip transparently."""
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    for enc in (encoding, "utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def http_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    encoding: str = "utf-8",
) -> str:
    """GET ``url`` and return decoded body, or empty string on failure."""
    if params:
        # urlencode with safe="," keeps ``,`` separators intact (used by sina/tencent)
        qs = urllib.parse.urlencode(params, safe=",:.")
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{qs}"

    req_headers = {
        "User-Agent": DEFAULT_UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
            raw = resp.read()
            return _decode(raw, encoding)
    except Exception:
        return ""


def http_get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> Any:
    """GET + ``json.loads``. Returns ``None`` on network or parse failure.

    Some endpoints wrap JSON inside a JSONP callback like ``cb({...})`` —
    we strip a single outer ``ident(...);?`` if present.
    """
    body = http_get(url, params=params, headers=headers, timeout=timeout)
    if not body:
        return None
    body = body.strip()
    # Strip JSONP wrapper: ident(...) or ident(...);
    if body.endswith(";"):
        body = body[:-1].rstrip()
    if body.endswith(")") and "(" in body:
        first_paren = body.find("(")
        head = body[:first_paren]
        if head.replace("_", "").replace("-", "").isidentifier() or head.isalnum():
            body = body[first_paren + 1 : -1]
    try:
        return json.loads(body)
    except (ValueError, json.JSONDecodeError):
        return None
