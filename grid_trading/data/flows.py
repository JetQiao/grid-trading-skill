"""Capital-flow signals: 龙虎榜 / 北向资金 / 两融 / 主力资金.

Source priority:
    akshare (if installed) → eastmoney push2

Returns plain dicts so downstream code (HTML report, recommender) can
consume them without importing akshare.
"""

from __future__ import annotations

from typing import Any

from grid_trading.data.http import http_get_json


def fetch_flows(*, kind: str = "north") -> list[dict[str, Any]]:
    """Fetch capital-flow rows for a given category.

    Args:
        kind: One of:
            ``north``       — 北向资金 (Stock Connect, last ~30 days)
            ``lhb``         — 龙虎榜 most recent day
            ``margin``      — 两融余额 (last ~30 days)
            ``main_flow``   — 沪深京 主力资金净流入 (last 1 day)
    """
    if kind == "north":
        return _north_money()
    if kind == "lhb":
        return _lhb()
    if kind == "margin":
        return _margin()
    if kind == "main_flow":
        return _main_flow()
    return []


# ---------------------------------------------------------------------------
# 北向资金 (Hu/Shen Stock Connect — eastmoney public endpoint)
# ---------------------------------------------------------------------------

def _north_money() -> list[dict[str, Any]]:
    data = http_get_json(
        "https://push2his.eastmoney.com/api/qt/kamt.kline/get",
        params={"fields1": "f1,f3,f5", "fields2": "f51,f52", "klt": 101, "lmt": 30},
        headers={"Referer": "https://data.eastmoney.com/hsgt/index.html"},
    )
    try:
        rows = data["data"]["s2n"]
    except (KeyError, TypeError):
        return []
    out = []
    for line in rows:
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            out.append({"date": parts[0], "net_inflow_yi": float(parts[1])})
        except ValueError:
            continue
    return out


# ---------------------------------------------------------------------------
# 龙虎榜
# ---------------------------------------------------------------------------

def _lhb() -> list[dict[str, Any]]:
    # eastmoney 龙虎榜 list endpoint
    data = http_get_json(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params={
            "sortColumns": "SECURITY_CODE",
            "sortTypes": "1",
            "pageSize": 50,
            "pageNumber": 1,
            "reportName": "RPT_DAILYBILLBOARD_DETAILS",
            "columns": "ALL",
            "source": "WEB",
            "client": "WEB",
        },
        headers={"Referer": "https://data.eastmoney.com/stock/tradedetail.html"},
    )
    try:
        rows = data["result"]["data"]
    except (KeyError, TypeError):
        return []
    return [
        {
            "date": r.get("TRADE_DATE", "")[:10],
            "code": r.get("SECURITY_CODE"),
            "name": r.get("SECURITY_NAME_ABBR"),
            "close": r.get("CLOSE_PRICE"),
            "change_pct": r.get("CHANGE_RATE"),
            "net_buy": r.get("BILLBOARD_NET_AMT"),
            "explain": r.get("EXPLAIN"),
        }
        for r in rows or []
    ]


# ---------------------------------------------------------------------------
# 两融余额 (Margin & Short Balance)
# ---------------------------------------------------------------------------

def _margin() -> list[dict[str, Any]]:
    data = http_get_json(
        "https://datacenter-web.eastmoney.com/api/data/v1/get",
        params={
            "sortColumns": "DATE",
            "sortTypes": "-1",
            "pageSize": 30,
            "pageNumber": 1,
            "reportName": "RPTA_RZRQ_LSHJ",
            "columns": "ALL",
            "source": "WEB",
            "client": "WEB",
        },
        headers={"Referer": "https://data.eastmoney.com/rzrq/total.html"},
    )
    try:
        rows = data["result"]["data"]
    except (KeyError, TypeError):
        return []
    return [
        {
            "date": (r.get("DATE") or "")[:10],
            "rzye": r.get("RZYE"),
            "rzrqye": r.get("RZRQYE"),
            "rqye": r.get("RQYE"),
        }
        for r in rows or []
    ]


# ---------------------------------------------------------------------------
# 主力资金净流入 (top movers)
# ---------------------------------------------------------------------------

def _main_flow() -> list[dict[str, Any]]:
    data = http_get_json(
        "https://push2.eastmoney.com/api/qt/clist/get",
        params={
            "pn": 1, "pz": 50, "po": 1, "fid": "f62",
            "fs": "m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,"
                  "m:1+t:2+f:!2,m:1+t:23+f:!2,m:0+t:7+f:!2,m:1+t:3+f:!2",
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
        },
        headers={"Referer": "https://data.eastmoney.com/zjlx/detail.html"},
    )
    try:
        rows = data["data"]["diff"]
    except (KeyError, TypeError):
        return []
    return [
        {
            "code": r.get("f12"),
            "name": r.get("f14"),
            "price": r.get("f2"),
            "change_pct": r.get("f3"),
            "main_net_inflow": r.get("f62"),
            "main_net_inflow_pct": r.get("f184"),
        }
        for r in rows or []
    ]
