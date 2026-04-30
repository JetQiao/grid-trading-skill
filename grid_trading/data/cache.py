"""Tiny file-based cache (TTL in seconds).

Used by hot-list fetchers (social, macro) to keep traffic bounded —
the user's spec calls for 5-minute caches on social hot endpoints.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

CACHE_DIR = Path(
    os.environ.get(
        "GRID_TRADING_CACHE_DIR",
        str(Path.home() / ".cache" / "grid-trading-skill"),
    )
)


def _path_for(key: str) -> Path:
    h = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return CACHE_DIR / f"{h}.json"


def cache_get(key: str, ttl: float = 300.0) -> Any:
    """Return cached value if newer than ``ttl`` seconds, else ``None``."""
    p = _path_for(key)
    if not p.exists():
        return None
    if (time.time() - p.stat().st_mtime) > ttl:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def cache_put(key: str, value: Any) -> None:
    """Persist ``value`` to disk under ``key``. Silently ignores I/O errors."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _path_for(key).write_text(
            json.dumps(value, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def cached(key: str, ttl: float, producer):
    """Convenience wrapper: read-or-produce-and-write."""
    hit = cache_get(key, ttl)
    if hit is not None:
        return hit
    value = producer()
    if value is not None:
        cache_put(key, value)
    return value
