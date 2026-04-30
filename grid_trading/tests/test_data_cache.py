"""Unit tests for data/cache.py — TTL-based file cache."""

from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path


class TestFileCache(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="grid-cache-test-")
        os.environ["GRID_TRADING_CACHE_DIR"] = self.tmp
        # Re-import so module-level CACHE_DIR picks up the env var
        import importlib
        import grid_trading.data.cache as cache_mod
        importlib.reload(cache_mod)
        self.cache = cache_mod

    def tearDown(self) -> None:
        # Best-effort cleanup
        for p in Path(self.tmp).glob("*"):
            try:
                p.unlink()
            except OSError:
                pass
        try:
            os.rmdir(self.tmp)
        except OSError:
            pass
        os.environ.pop("GRID_TRADING_CACHE_DIR", None)

    def test_put_then_get(self):
        self.cache.cache_put("k1", {"x": 1, "y": [1, 2, 3]})
        v = self.cache.cache_get("k1", ttl=300)
        self.assertEqual(v, {"x": 1, "y": [1, 2, 3]})

    def test_miss_returns_none(self):
        self.assertIsNone(self.cache.cache_get("nonexistent", ttl=300))

    def test_ttl_expiry(self):
        self.cache.cache_put("k2", "hello")
        # Force mtime backwards so TTL appears expired
        p = Path(self.tmp) / next(iter(os.listdir(self.tmp)))
        old = time.time() - 1000
        os.utime(p, (old, old))
        self.assertIsNone(self.cache.cache_get("k2", ttl=300))

    def test_cached_helper_runs_producer_only_once(self):
        calls = {"n": 0}

        def producer():
            calls["n"] += 1
            return {"v": calls["n"]}

        v1 = self.cache.cached("k3", 300, producer)
        v2 = self.cache.cached("k3", 300, producer)
        self.assertEqual(v1, v2)
        self.assertEqual(calls["n"], 1)


if __name__ == "__main__":
    unittest.main()
