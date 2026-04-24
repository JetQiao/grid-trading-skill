# 🎨 v1.2.0 — HTML Report + One-Command Run

**亮点：深色主题 HTML 报告 + `npx grid-trading-skill run "..."` 一行出图。**

## ✨ 新增

- 🌑 **深色主题 HTML 报告**（`grid_trading/report/html_report.py`）
  - 单文件、内联 CSS、无外部依赖、离线可用
  - 参数卡片、网格分布表（斑马纹 + 悬停高亮 + 买绿卖红）
  - 回测关键指标卡（总收益/年化/回撤/夏普/胜率）
  - **SVG 资金曲线**（涨绿跌红自适应）
  - 风险告警分级展示
- ⚡ **`npx grid-trading-skill run "<中文/英文>"`**
  - 自然语言解析（`40k~60k`、`20格`、`本金10000`、`0.1%`、`等差/等比`）
  - 自动跑 sine-wave 回测 + 用系统默认浏览器打开 HTML
  - 新增 `--no-open` / `--no-backtest` / `--out` 选项
- 🐍 **`python -m grid_trading.cli`** 直连命令行入口（支持 `--backtest sine | trending-down | volatile`）
- 📦 **修复 Codex 集成**：源码部署到 `~/.codex/skills/grid-trading/`，指令合并进 `~/.codex/AGENTS.md`（用 `<!-- BEGIN/END grid-trading-skill -->` 标记实现幂等安装/卸载，保留用户自定义内容）
- 📝 **重写 AGENTS.md**：强指令式，要求 agent 必须 shell 调用 Python 生成 HTML，不得自己心算输出 CSV

## 🐛 修复

- Codex 跑出来输出为裸 CSV / 手算网格价 —— 现在 AGENTS.md 明确要求调用 Python 包产 HTML
- 旧版 `~/.codex/agents/grid-trading/` 路径不被 Codex CLI 识别 —— 改为 `~/.codex/skills/` + 合并 AGENTS.md

## 📦 升级

```bash
# 一键（重装会自动清理 v1.1 遗留路径）
npx github:JetQiao/grid-trading-skill uninstall
npx grid-trading-skill@latest

# 或
npm i -g grid-trading-skill@1.2.0
```

## 🚀 试一下

```bash
npx grid-trading-skill run "BTC/USDT 40000~60000 20格 本金10000 手续费0.1%"
```

## 🔗 完整变更

<https://github.com/JetQiao/grid-trading-skill/compare/v1.1.0...v1.2.0>
