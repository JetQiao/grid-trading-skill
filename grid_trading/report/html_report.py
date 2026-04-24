"""Self-contained dark-themed HTML report generator.

Produces a single HTML file with inlined CSS and SVG — no external assets,
no JavaScript frameworks, no network calls. Opens identically in any modern
browser, works offline, and can be emailed as a single attachment.
"""

from __future__ import annotations

import html
from dataclasses import asdict
from datetime import datetime
from typing import Any

from grid_trading.core.grid_builder import GridLevel


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_html_report(
    *,
    params: dict[str, Any],
    grids: list[GridLevel],
    summary: dict[str, Any],
    backtest: dict[str, Any] | None = None,
    risk_alerts: list[dict[str, Any]] | None = None,
) -> str:
    """Render a complete HTML report as a single string.

    Args:
        params: Echo of user-supplied parameters (symbol, range, count, ...).
        grids: List of GridLevel objects from GridBuilder.
        summary: Dict from GridBuilder.summary(grids).
        backtest: Optional dict with backtest fields (total_return, sharpe,
            max_drawdown, equity_curve, trade_log, trading_days, ...).
        risk_alerts: Optional list of dicts with keys level/type/message.

    Returns:
        Complete HTML document as a string.
    """
    parts = [
        _HEAD,
        _render_header(params),
        _render_params(params),
        _render_grid_table(grids),
        _render_summary(summary),
    ]
    if backtest:
        parts.append(_render_backtest(backtest, params.get("symbol", "")))
    if risk_alerts:
        parts.append(_render_risk_alerts(risk_alerts))
    parts.append(_render_footer())
    parts.append(_TAIL)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Document shell
# ---------------------------------------------------------------------------

_CSS = """
:root {
  --bg: #0b0d10;
  --panel: #12161c;
  --panel-2: #161b22;
  --border: #222832;
  --border-soft: #1a1f27;
  --text: #e6edf3;
  --muted: #8b949e;
  --accent: #58a6ff;
  --accent-2: #79c0ff;
  --green: #3fb950;
  --green-soft: #238636;
  --red: #f85149;
  --red-soft: #da3633;
  --amber: #d29922;
  --violet: #bc8cff;
  --grid-buy: rgba(63, 185, 80, 0.08);
  --grid-sell: rgba(248, 81, 73, 0.06);
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei",
    "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 14px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.container {
  max-width: 1180px;
  margin: 0 auto;
  padding: 40px 28px 80px;
}

/* Header */
.header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  padding-bottom: 20px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 28px;
}
.header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  letter-spacing: -0.01em;
}
.header .sub {
  margin-top: 6px;
  color: var(--muted);
  font-size: 13px;
}
.badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  border: 1px solid var(--border);
  color: var(--muted);
  background: var(--panel);
  margin-right: 6px;
}
.badge.accent { color: var(--accent-2); border-color: rgba(88,166,255,0.3); background: rgba(88,166,255,0.08); }
.badge.green  { color: var(--green);   border-color: rgba(63,185,80,0.3);  background: rgba(63,185,80,0.08); }

/* Section */
.section {
  margin-top: 36px;
}
.section h2 {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  font-weight: 600;
  margin: 0 0 14px;
}

/* Param grid */
.params {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}
.param-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
}
.param-card .label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 6px;
}
.param-card .value {
  font-size: 17px;
  font-weight: 600;
  font-feature-settings: "tnum";
}

/* Table */
.table-wrap {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}
table.grid {
  width: 100%;
  border-collapse: collapse;
  font-feature-settings: "tnum";
}
table.grid th {
  text-align: right;
  padding: 11px 14px;
  background: var(--panel-2);
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
}
table.grid th:first-child, table.grid td:first-child {
  text-align: center;
  width: 56px;
}
table.grid td {
  padding: 10px 14px;
  text-align: right;
  border-bottom: 1px solid var(--border-soft);
  color: var(--text);
}
table.grid tr:last-child td { border-bottom: none; }
table.grid tr:nth-child(even) td { background: rgba(255,255,255,0.015); }
table.grid tr:hover td { background: rgba(88,166,255,0.06); }

.buy-price  { color: var(--green); }
.sell-price { color: var(--red); }
.pos { color: var(--green); }
.neg { color: var(--red); }

/* Summary metrics */
.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 12px;
}
.metric-card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
}
.metric-card .label {
  color: var(--muted);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.metric-card .value {
  margin-top: 6px;
  font-size: 22px;
  font-weight: 600;
  font-feature-settings: "tnum";
}
.metric-card .value.big { font-size: 26px; }

/* Equity chart */
.chart-wrap {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px;
}
.chart-wrap svg { width: 100%; height: auto; display: block; }

/* Risk alerts */
.alert {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 8px;
  margin-bottom: 8px;
  border: 1px solid var(--border);
  background: var(--panel);
}
.alert.critical {
  border-color: rgba(248,81,73,0.4);
  background: rgba(248,81,73,0.08);
}
.alert.warning {
  border-color: rgba(210,153,34,0.4);
  background: rgba(210,153,34,0.06);
}
.alert .dot {
  width: 8px; height: 8px; border-radius: 50%;
  margin-top: 7px; flex-shrink: 0;
}
.alert.critical .dot { background: var(--red); }
.alert.warning  .dot { background: var(--amber); }
.alert .type {
  font-weight: 600;
  color: var(--text);
  margin-right: 6px;
}
.alert .msg { color: var(--muted); }

/* Footer */
.footer {
  margin-top: 60px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 12px;
  display: flex;
  justify-content: space-between;
}
.footer a { color: var(--accent); text-decoration: none; }
.footer a:hover { text-decoration: underline; }
"""

_HEAD = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Grid Trading Report</title>
  <style>{_CSS}</style>
</head>
<body>
  <div class="container">
"""

_TAIL = """
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_header(params: dict[str, Any]) -> str:
    symbol = html.escape(str(params.get("symbol", "—")))
    gtype = html.escape(str(params.get("grid_type", "geometric")))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""
    <div class="header">
      <div>
        <h1>网格交易报告 <span style="color:var(--muted);font-weight:400;">· {symbol}</span></h1>
        <div class="sub">
          <span class="badge accent">{gtype}</span>
          <span class="badge">{_fmt_num(params.get('grid_count', 0), 0)} 格</span>
          <span class="badge">手续费 {_fmt_pct(params.get('fee_rate', 0))}</span>
          生成于 {now}
        </div>
      </div>
    </div>
    """


def _render_params(params: dict[str, Any]) -> str:
    cards = [
        ("交易对",    html.escape(str(params.get("symbol", "—")))),
        ("网格类型",  "等差" if params.get("grid_type") == "arithmetic" else "等比"),
        ("价格下限",  _fmt_num(params.get("price_lower", 0), 2)),
        ("价格上限",  _fmt_num(params.get("price_upper", 0), 2)),
        ("格数",      _fmt_num(params.get("grid_count", 0), 0)),
        ("本金",      _fmt_num(params.get("total_capital", 0), 2)),
        ("手续费率",  _fmt_pct(params.get("fee_rate", 0))),
    ]
    if params.get("stop_loss_price"):
        cards.append(("止损价", _fmt_num(params["stop_loss_price"], 2)))
    if params.get("take_profit_price"):
        cards.append(("止盈价", _fmt_num(params["take_profit_price"], 2)))

    cells = "\n".join(
        f'<div class="param-card"><div class="label">{lbl}</div>'
        f'<div class="value">{val}</div></div>'
        for lbl, val in cards
    )
    return f"""
    <div class="section">
      <h2>参数</h2>
      <div class="params">{cells}</div>
    </div>
    """


def _render_grid_table(grids: list[GridLevel]) -> str:
    rows = []
    for g in grids:
        rows.append(
            "<tr>"
            f"<td>{g.level}</td>"
            f'<td class="buy-price">{_fmt_num(g.buy_price, 2)}</td>'
            f'<td class="sell-price">{_fmt_num(g.sell_price, 2)}</td>'
            f"<td>{_fmt_num(g.quantity, 8)}</td>"
            f"<td>{_fmt_num(g.capital_required, 2)}</td>"
            f'<td class="pos">{_fmt_num(g.expected_profit, 4)}</td>'
            f'<td class="pos">{_fmt_pct(g.profit_rate)}</td>'
            "</tr>"
        )
    return f"""
    <div class="section">
      <h2>网格分布</h2>
      <div class="table-wrap">
        <table class="grid">
          <thead>
            <tr>
              <th>Lv</th>
              <th>Buy</th>
              <th>Sell</th>
              <th>Qty</th>
              <th>Capital</th>
              <th>Profit</th>
              <th>Rate</th>
            </tr>
          </thead>
          <tbody>
            {"".join(rows)}
          </tbody>
        </table>
      </div>
    </div>
    """


def _render_summary(summary: dict[str, Any]) -> str:
    if not summary:
        return ""
    cards = [
        ("总格数",       _fmt_num(summary.get("grid_count", 0), 0)),
        ("总投入",       _fmt_num(summary.get("total_capital", 0), 2)),
        ("平均收益率",   _fmt_pct(summary.get("avg_profit_rate", 0))),
        ("单格最小收益率", _fmt_pct(summary.get("min_profit_rate", 0))),
        ("单格最大收益率", _fmt_pct(summary.get("max_profit_rate", 0))),
        ("总预期利润",   _fmt_num(summary.get("total_expected_profit", 0), 4)),
    ]
    cells = "\n".join(
        f'<div class="metric-card"><div class="label">{lbl}</div>'
        f'<div class="value">{val}</div></div>'
        for lbl, val in cards
    )
    return f"""
    <div class="section">
      <h2>资金分配概览</h2>
      <div class="metrics">{cells}</div>
    </div>
    """


def _render_backtest(bt: dict[str, Any], symbol: str) -> str:
    metric_cards = [
        ("总收益率",     _fmt_pct(bt.get("total_return", 0)),
         "pos" if bt.get("total_return", 0) >= 0 else "neg"),
        ("年化收益率",   _fmt_pct(bt.get("annualized_return", 0)),
         "pos" if bt.get("annualized_return", 0) >= 0 else "neg"),
        ("最大回撤",     _fmt_pct(bt.get("max_drawdown", 0)), "neg"),
        ("夏普比率",     _fmt_num(bt.get("sharpe_ratio", 0), 2), ""),
        ("胜率",         _fmt_pct(bt.get("win_rate", 0)), ""),
        ("总成交笔数",   _fmt_num(bt.get("total_trades", 0), 0), ""),
        ("均笔利润",     _fmt_num(bt.get("avg_profit_per_trade", 0), 4), ""),
        ("累计手续费",   _fmt_num(bt.get("fee_total", 0), 4), ""),
        ("回测天数",     _fmt_num(bt.get("trading_days", 0), 1), ""),
    ]
    cells = "\n".join(
        f'<div class="metric-card"><div class="label">{lbl}</div>'
        f'<div class="value big {cls}">{val}</div></div>'
        for lbl, val, cls in metric_cards
    )
    equity_chart = _render_equity_svg(bt.get("equity_curve") or [])
    return f"""
    <div class="section">
      <h2>回测结果 · {html.escape(symbol)}</h2>
      <div class="metrics">{cells}</div>
    </div>
    <div class="section">
      <h2>资金曲线</h2>
      <div class="chart-wrap">{equity_chart}</div>
    </div>
    """


def _render_equity_svg(curve: list[float]) -> str:
    if len(curve) < 2:
        return '<div style="color:var(--muted);text-align:center;padding:40px;">无资金曲线数据</div>'

    W, H = 1080, 280
    pad_l, pad_r, pad_t, pad_b = 56, 20, 18, 28
    iw = W - pad_l - pad_r
    ih = H - pad_t - pad_b

    cmin, cmax = min(curve), max(curve)
    span = cmax - cmin if cmax > cmin else max(abs(cmax), 1.0)
    n = len(curve)

    def x(i: int) -> float:
        return pad_l + (i / (n - 1)) * iw

    def y(v: float) -> float:
        return pad_t + ih - ((v - cmin) / span) * ih

    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(curve))
    area_pts = f"{pad_l:.1f},{pad_t + ih:.1f} " + pts + f" {pad_l + iw:.1f},{pad_t + ih:.1f}"
    is_profit = curve[-1] >= curve[0]
    stroke = "#3fb950" if is_profit else "#f85149"
    fill = "rgba(63,185,80,0.12)" if is_profit else "rgba(248,81,73,0.12)"

    # Y-axis ticks (5)
    ticks = []
    for k in range(5):
        v = cmin + span * k / 4
        ty = y(v)
        ticks.append(
            f'<line x1="{pad_l}" y1="{ty:.1f}" x2="{pad_l + iw}" y2="{ty:.1f}" '
            f'stroke="#1a1f27" stroke-width="1" />'
            f'<text x="{pad_l - 8}" y="{ty + 3:.1f}" fill="#8b949e" font-size="10" '
            f'text-anchor="end" font-family="-apple-system,sans-serif">{v:,.0f}</text>'
        )

    return f"""
<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <rect x="0" y="0" width="{W}" height="{H}" fill="transparent" />
  {"".join(ticks)}
  <polygon points="{area_pts}" fill="{fill}" />
  <polyline points="{pts}" fill="none" stroke="{stroke}" stroke-width="1.8"
    stroke-linejoin="round" stroke-linecap="round" />
  <text x="{pad_l}" y="{H - 8}" fill="#8b949e" font-size="10"
        font-family="-apple-system,sans-serif">起始 {curve[0]:,.2f}</text>
  <text x="{pad_l + iw}" y="{H - 8}" fill="#8b949e" font-size="10"
        text-anchor="end" font-family="-apple-system,sans-serif">终值 {curve[-1]:,.2f}</text>
</svg>
"""


def _render_risk_alerts(alerts: list[dict[str, Any]]) -> str:
    if not alerts:
        return ""
    items = []
    for a in alerts:
        lvl = a.get("level", "warning")
        items.append(
            f'<div class="alert {lvl}">'
            f'<div class="dot"></div>'
            f'<div><span class="type">{html.escape(str(a.get("type", "")))}</span>'
            f'<span class="msg">{html.escape(str(a.get("message", "")))}</span></div>'
            f'</div>'
        )
    return f"""
    <div class="section">
      <h2>风险告警 ({len(alerts)})</h2>
      {"".join(items)}
    </div>
    """


def _render_footer() -> str:
    return """
    <div class="footer">
      <div>Generated by <strong>grid-trading-skill</strong></div>
      <div><a href="https://github.com/JetQiao/grid-trading-skill">github.com/JetQiao/grid-trading-skill</a></div>
    </div>
    """


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt_num(v: float | int, decimals: int) -> str:
    try:
        return f"{float(v):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_pct(v: float) -> str:
    try:
        return f"{float(v) * 100:.4f}%"
    except (TypeError, ValueError):
        return str(v)


def alert_to_dict(alert) -> dict[str, Any]:
    """Convert a RiskAlert dataclass into a plain dict (for rendering)."""
    try:
        return asdict(alert)
    except TypeError:
        return {
            "level": getattr(alert, "level", "warning"),
            "type":  getattr(alert, "type", ""),
            "message": getattr(alert, "message", str(alert)),
        }
