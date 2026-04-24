# grid-trading-skill

> 一个开箱即用的**网格交易策略** Skill —— 支持等差/等比网格、完整回测引擎、
> 持仓追踪、风控告警。同时适配 **Claude Code** 与 **OpenAI Codex CLI**。

![tests](https://img.shields.io/badge/tests-48%20passing-brightgreen)
![python](https://img.shields.io/badge/python-3.11+-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## 📦 一键安装（零代码经验也能用）

### 🌟 方式一：npx（**推荐**，跨平台一条命令）

```bash
# 通用（直接从 GitHub 拉取，无需发布到 npm）
npx github:JetQiao/grid-trading-skill

# 或（npm 发布后）
npx grid-trading-skill
```

仅需 Node.js 16+，无需 Python，**Mac / Linux / Windows 通用**。
默认会同时部署到：

| 目标 | 路径 |
|---|---|
| Claude Code skill | `~/.claude/skills/grid-trading/` |
| OpenAI Codex agent | `~/.codex/agents/grid-trading/` |

常用命令：

```bash
npx grid-trading-skill                    # 全部安装（默认）
npx grid-trading-skill install --claude-only
npx grid-trading-skill install --codex-only
npx grid-trading-skill status             # 查看安装状态
npx grid-trading-skill uninstall          # 全部卸载
npx grid-trading-skill help
```

也可以全局安装：

```bash
npm install -g grid-trading-skill
grid-trading-skill status
```

### 🔧 方式二：Shell 脚本（无需 Node）

```bash
# macOS / Linux
git clone https://github.com/JetQiao/grid-trading-skill.git
cd grid-trading-skill && bash install.sh

# Windows
powershell -ExecutionPolicy Bypass -File install.ps1
```

### 🐍 方式三：pip（仅作为 Python 库使用）

```bash
pip install git+https://github.com/JetQiao/grid-trading-skill.git
```

### 前置要求

| 安装方式 | 需要 |
|---|---|
| `npx` / `npm` | Node.js 16+ |
| `bash install.sh` | macOS/Linux + bash（pip 自动调用） |
| `install.ps1` | Windows + PowerShell |
| `pip install` | Python 3.11+ |

---

## 🚀 快速使用

### ⚡ 一条命令生成 HTML 报告（v1.2+ 推荐）

```bash
npx grid-trading-skill run "BTC/USDT 40000~60000 20格 本金10000 手续费0.1%"
```

自动完成：解析中文/英文指令 → 构建网格 → 跑 sine-wave 回测 → 生成**深色主题
HTML 报告**（单文件内联 CSS + SVG 资金曲线）→ 用默认浏览器打开。

可选：`--no-open` / `--no-backtest` / `--out path.html`

### 在 Claude Code 中调用

安装完成后，打开 Claude Code 输入：

```
帮我用 BTC/USDT 从 40000 到 60000 做 20 格等比网格，本金 10000，手续费 0.1%
```

Claude 会自动加载 skill 并输出网格分布表 + 回测结果。

### 在 OpenAI Codex CLI 中调用

Codex 检测到 `AGENTS.md` 后会自动识别 `grid-trading` 这个 agent，
触发关键词与 Claude 一致。

### 纯 Python 调用

```python
from grid_trading.strategy.grid_strategy import GridConfig, GridStrategy
from grid_trading.backtest.simulator import BacktestSimulator
from grid_trading.tests.mock_data import sine_wave

config = GridConfig(
    symbol="BTC/USDT",
    grid_type="arithmetic",       # 或 "geometric"
    price_lower=44000,
    price_upper=56000,
    grid_count=12,
    total_capital=10000,
    fee_rate=0.001,
)

sim = BacktestSimulator(GridStrategy(config))
result = sim.run(sine_wave(base_price=50000, amplitude=5000))
sim.print_report(result)
```

输出示例：

```
=======================================================
  Backtest Report — BTC/USDT
=======================================================
  Total return        : 3.97%
  Max drawdown        : 1.78%
  Sharpe ratio        : 2.18
  Total trades        : 49
  Win rate            : 58.33%
=======================================================
```

---

## 📂 项目结构

```
grid_trading/
├── SKILL.md                    # Skill 说明（Claude Code 识别）
├── core/
│   ├── grid_builder.py         # 网格构建（等差/等比）
│   ├── order_manager.py        # 挂单状态管理（幂等保护）
│   ├── position_tracker.py     # 持仓与资金追踪
│   └── pnl_calculator.py       # 盈亏/绩效计算
├── strategy/
│   ├── grid_strategy.py        # 主策略（组合所有模块）
│   └── rebalance.py            # 越界重置逻辑
├── risk/
│   └── risk_checker.py         # 风控规则（7 条）
├── backtest/
│   ├── simulator.py            # 事件驱动回测引擎
│   └── metrics.py              # 总收益/回撤/夏普
└── tests/                      # 48 个单元 + 集成测试
```

---

## ✨ 核心特性

- ✅ **等差 / 等比**两种网格，自动校验 `step > 2 × fee`
- ✅ **事件驱动回测**，保证 `equity_curve 长度 == 价格序列长度`
- ✅ **自动补对手单**：买单成交后自动在对应卖价挂卖单，反之亦然
- ✅ **7 条风控规则**：止损、止盈、越下界、越上界、资金不足、最大回撤
- ✅ **无交易所 SDK 依赖**，行情通过 `[(timestamp, price), ...]` 输入
- ✅ **8 位小数精度**（加密货币友好）
- ✅ **零全局状态**，多策略实例可并行运行

---

## 🧪 运行测试

```bash
python3 -m unittest discover -s grid_trading/tests -p "test_*.py" -v
```

预期：`Ran 48 tests in ~0.03s OK`

---

## 📖 完整文档

详见 [`grid_trading/SKILL.md`](grid_trading/SKILL.md)。

## 📜 License

[MIT](LICENSE) © JetQiao
