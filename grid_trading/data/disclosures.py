"""Company disclosures and research reports.

Source priority:
    巨潮资讯 (cninfo) — primary, covers A-share announcements + filings
    eastmoney research center — analyst reports
"""

from __future__ import annotations

from typing import Any

from grid_trading.data.http import http_get_json
from grid_trading.data.symbol import Symbol, normalize_symbol


def fetch_disclosures(
    raw_symbol: str,
    *,
    kind: str = "announcements",
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Fetch recent disclosures for ``raw_symbol``.

    Args:
        kind: ``announcements`` (公告) or ``research`` (研报).
        limit: Max rows.
    """
    sym = normalize_symbol(raw_symbol)
    if sym.market != "a-share":
        # cninfo only covers China A; skip rather than fake data
        return []
    if kind == "announcements":
        return _cninfo_announcements(sym, limit)
    if kind == "research":
        return _eastmoney_research(sym, limit)
    return []


# ---------------------------------------------------------------------------
# 巨潮资讯 公告
# ---------------------------------------------------------------------------

def _cninfo_announcements(sym: Symbol, limit: int) -> list[dict[str, Any]]:
    # cninfo expects code prefix mapping: 'sh' / 'sz'
    pre = "9900" if sym.code.startswith(("9", "6", "5")) else "9901"
    # Use the fixed-list endpoint that doesn't need login
    data = http_get_json(
        "http://www.cninfo.com.cn/new/disclosure/stock",
        params={
            "stockCode": sym.code,
            "orgId": pre,
            "pageNum": 1, "pageSize": limit, "tabName": "fulltext",
        },
        headers={"Referer": "http://www.cninfo.com.cn/"},
    )
    rows = (data or {}).get("announcements") if isinstance(data, dict) else None
    if not rows:
        # fallback: free-text search endpoint
        data = http_get_json(
            "http://www.cninfo.com.cn/new/fulltextSearch/full",
            params={
                "searchkey": sym.code, "sdate": "", "edate": "",
                "isfulltext": "false", "sortName": "", "sortType": "",
                "pageNum": 1, "pageSize": limit,
            },
            headers={"Referer": "http://www.cninfo.com.cn/"},
        )
        rows = (data or {}).get("announcements") if isinstance(data, dict) else None
    if not rows:
        return []
    return [
        {
            "title": r.get("announcementTitle"),
            "date": (r.get("adjunctUrl", "") or "")[:10] or r.get("announcementTime"),
            "url": "http://www.cninfo.com.cn" + ("/" + r.get("adjunctUrl", "") if r.get("adjunctUrl") else ""),
            "type": r.get("announcementType"),
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# eastmoney 研报中心
# ---------------------------------------------------------------------------

def _eastmoney_research(sym: Symbol, limit: int) -> list[dict[str, Any]]:
    data = http_get_json(
        "https://reportapi.eastmoney.com/report/list",
        params={
            "industryCode": "*", "pageSize": limit, "industry": "*",
            "rating": "*", "ratingChange": "*", "beginTime": "",
            "endTime": "", "pageNo": 1, "fields": "",
            "qType": 0, "orgCode": "", "code": sym.code,
            "rcode": "", "_": "0",
        },
        headers={"Referer": "https://data.eastmoney.com/report/"},
    )
    try:
        rows = data["data"]
    except (KeyError, TypeError):
        return []
    return [
        {
            "title": r.get("title"),
            "org": r.get("orgSName"),
            "rating": r.get("emRatingName"),
            "target_price": r.get("targetPrice"),
            "date": (r.get("publishDate") or "")[:10],
            "url": f"https://data.eastmoney.com/report/{(r.get('publishDate') or '')[:10].replace('-', '')}/{r.get('infoCode', '')}.html",
            "summary": r.get("title"),
        }
        for r in rows or []
    ]
