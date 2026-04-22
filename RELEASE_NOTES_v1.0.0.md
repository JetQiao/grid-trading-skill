# 🎉 Grid Trading Skill v1.0.0 — First Stable Release

**一个开箱即用的网格交易策略 Skill，同时支持 Claude Code 与 OpenAI Codex CLI。**

---

## ✨ 核心功能

- **等差 / 等比网格**构建，自动校验 `step_ratio > 2 × fee`
- **事件驱动回测引擎**：`equity_curve` 长度严格等于价格序列
- **自动补对手单**：买成交补卖，卖成交补买，幂等保护
- **7 条风控规则**：止损、止盈、越上下界、资金不足、最大回撤
- **完整绩效指标**：总收益、年化、最大回撤、夏普、胜率、盈利因子
- **零外部依赖**（仅标准库 + 可选 matplotlib/pandas）

## 📦 安装方式

### 一键安装脚本（推荐）

```bash
# macOS / Linux
curl -L https://github.com/JetQiao/grid-trading-skill/archive/refs/tags/v1.0.0.tar.gz | tar xz
cd grid-trading-skill-1.0.0
bash install.sh

# Windows
# 下载 zip 解压后执行：
powershell -ExecutionPolicy Bypass -File install.ps1
```

### pip 安装

```bash
pip install grid_trading_skill-1.0.0-py3-none-any.whl
# 或
pip install git+https://github.com/JetQiao/grid-trading-skill.git@v1.0.0
```

## 🎯 Skill 安装位置

| 目标 | 路径 |
|---|---|
| Claude Code | `~/.claude/skills/grid-trading/` |
| OpenAI Codex CLI | `~/.codex/agents/grid-trading/` |

## 📊 验证

48 个单元/集成测试全部通过：

```
Ran 48 tests in 0.031s — OK
```

## 📖 文档

- 用户入门：[README.md](README.md)
- 完整 API：[grid_trading/SKILL.md](grid_trading/SKILL.md)
- Codex 接入：[AGENTS.md](AGENTS.md)

## 📥 Assets

- `grid-trading-skill-1.0.0.zip` — 完整源码压缩包
- `grid_trading_skill-1.0.0-py3-none-any.whl` — pip wheel
- `grid_trading_skill-1.0.0.tar.gz` — pip sdist

---

**Full Changelog**: First release.
