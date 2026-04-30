"""Social hot lists across mainland Chinese platforms.

Per user spec (v2.12): each platform has its own official JSON endpoint;
we use a 5-minute file cache and isolate failures so one dead source
never blocks the others.

Supported platforms:
    weibo, zhihu, baidu, douyin, toutiao, bilibili
"""

from __future__ import annotations

from typing import Any

from grid_trading.data.cache import cached
from grid_trading.data.http import http_get_json


# 5-minute TTL per spec
_DEFAULT_TTL = 300.0


def fetch_social_hot(
    platform: str = "all",
    *,
    limit: int = 20,
    cache_ttl: float = _DEFAULT_TTL,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch hot-list items.

    Args:
        platform: One of ``weibo``, ``zhihu``, ``baidu``, ``douyin``,
            ``toutiao``, ``bilibili``, or ``all``.
        limit: Max rows per platform.
        cache_ttl: File cache TTL (default 5 min, matches v2.12 spec).

    Returns:
        Mapping ``platform -> [ {title, url, score, rank}, ... ]``.
        Failed platforms simply get an empty list — single-platform
        failures do not affect others.
    """
    plats = _PLATFORMS if platform == "all" else [platform]
    out: dict[str, list[dict[str, Any]]] = {}
    for p in plats:
        if p not in _FETCHERS:
            out[p] = []
            continue
        key = f"hot:{p}:{limit}"
        try:
            rows = cached(key, cache_ttl, lambda p=p: _FETCHERS[p](limit)) or []
        except Exception:
            rows = []
        out[p] = rows
    return out


# ---------------------------------------------------------------------------
# Per-platform fetchers
# ---------------------------------------------------------------------------

def _weibo(limit: int) -> list[dict[str, Any]]:
    data = http_get_json(
        "https://weibo.com/ajax/side/hotSearch",
        headers={"Referer": "https://weibo.com/"},
    )
    try:
        rows = data["data"]["realtime"]
    except (KeyError, TypeError):
        return []
    return [
        {
            "rank": i + 1,
            "title": r.get("word") or r.get("note", ""),
            "url": "https://s.weibo.com/weibo?q=" + (r.get("word_scheme") or "%23" + (r.get("word") or "") + "%23"),
            "score": r.get("num"),
        }
        for i, r in enumerate(rows[:limit])
    ]


def _zhihu(limit: int) -> list[dict[str, Any]]:
    data = http_get_json(
        "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total",
        params={"limit": limit, "desktop": "true"},
        headers={"Referer": "https://www.zhihu.com/hot"},
    )
    rows = (data or {}).get("data") or []
    out = []
    for i, r in enumerate(rows[:limit]):
        target = r.get("target", {})
        out.append({
            "rank": i + 1,
            "title": target.get("title") or "",
            "url": target.get("url", "").replace("api.zhihu.com/questions",
                                                 "www.zhihu.com/question"),
            "score": (r.get("detail_text") or "").replace(" 万热度", "0000"),
            "excerpt": target.get("excerpt") or "",
        })
    return out


def _baidu(limit: int) -> list[dict[str, Any]]:
    data = http_get_json(
        "https://top.baidu.com/api/board",
        params={"platform": "wise", "tab": "realtime"},
        headers={"Referer": "https://top.baidu.com/board"},
    )
    try:
        rows = data["data"]["cards"][0]["content"]
    except (KeyError, IndexError, TypeError):
        return []
    return [
        {
            "rank": i + 1,
            "title": r.get("word"),
            "url": r.get("url") or r.get("appUrl"),
            "score": r.get("hotScore"),
            "excerpt": r.get("desc") or "",
        }
        for i, r in enumerate(rows[:limit])
    ]


def _douyin(limit: int) -> list[dict[str, Any]]:
    data = http_get_json(
        "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/",
        headers={"Referer": "https://www.iesdouyin.com/"},
    )
    rows = ((data or {}).get("word_list") or [])[:limit]
    return [
        {
            "rank": i + 1,
            "title": r.get("word"),
            "url": "https://www.douyin.com/search/" + (r.get("word") or ""),
            "score": r.get("hot_value"),
        }
        for i, r in enumerate(rows)
    ]


def _toutiao(limit: int) -> list[dict[str, Any]]:
    data = http_get_json(
        "https://www.toutiao.com/hot-event/hot-board/",
        params={"origin": "toutiao_pc"},
        headers={"Referer": "https://www.toutiao.com/"},
    )
    rows = ((data or {}).get("data") or [])[:limit]
    return [
        {
            "rank": i + 1,
            "title": r.get("Title"),
            "url": r.get("Url"),
            "score": r.get("HotValue"),
            "image": (r.get("Image") or {}).get("url"),
        }
        for i, r in enumerate(rows)
    ]


def _bilibili(limit: int) -> list[dict[str, Any]]:
    data = http_get_json(
        "https://api.bilibili.com/x/web-interface/popular",
        params={"ps": limit, "pn": 1},
        headers={"Referer": "https://www.bilibili.com/"},
    )
    rows = (((data or {}).get("data") or {}).get("list") or [])[:limit]
    return [
        {
            "rank": i + 1,
            "title": r.get("title"),
            "url": r.get("short_link_v2") or f"https://www.bilibili.com/video/{r.get('bvid','')}",
            "score": (r.get("stat") or {}).get("view"),
            "author": (r.get("owner") or {}).get("name"),
        }
        for i, r in enumerate(rows)
    ]


_FETCHERS = {
    "weibo": _weibo,
    "zhihu": _zhihu,
    "baidu": _baidu,
    "douyin": _douyin,
    "toutiao": _toutiao,
    "bilibili": _bilibili,
}
_PLATFORMS = list(_FETCHERS.keys())
