# grid-trading-skill v1.2.2

**面向不会代码的用户** —— 在 v1.2.1 真实数据 + 自动推荐能力之上，再加两条
零代码入口，让任何会用浏览器和命令行的人都能一步出网格报告。

## 新增

### `npx grid-trading-skill ask` — 交互式向导

全中文问答，按回车用默认值，问完自动生成报告并打开浏览器：

```
? 股票代码 (A股=600519, 港股=00700, 美股=AAPL, 加密=BTC/USDT): 600519
? 本金 (默认 10000，可写 5万 或 50000): 5万
? 手续费率 (默认 0.001 = 0.1%，A 股可写 0.0003): 0.0003
? 上下限算法 [sigma/atr/quantile] (默认 sigma): ↵
? 是否用真实历史回测一次？[Y/n]: ↵
? 生成后用浏览器打开？[Y/n]: ↵
```

### `npx grid-trading-skill auto <代码> [本金]` — 一行命令

```bash
npx github:JetQiao/grid-trading-skill auto 600519 5万
npx github:JetQiao/grid-trading-skill auto 00700 20000 --backtest
npx github:JetQiao/grid-trading-skill auto BTC/USDT 10000 --method atr --safety 1.2
```

新增可选标志：`--no-open` / `--backtest` / `--fee` / `--method` / `--safety` /
`--max-grids` / `--window`。本金支持 `5万` / `5w` / `50000` 三种写法。

### Claude Code / Codex CLI 路径强化

`SKILL.md` / `AGENTS.md` 已包含触发关键字，安装后用大白话即可触发：

> 帮我看一下贵州茅台 5 万本金的网格怎么做

## 不变

- 所有 v1.2.1 命令（`python -m grid_trading.cli --auto ...`）继续工作。
- Python 测试 77 项全部通过，无回归。

## 内部变更

- `bin/cli.js` 新增 `auto` / `ask` 子命令，使用 Node 内置 `readline`，无新依赖。
- `package.json` 1.2.0 → 1.2.2（同步 pyproject 1.2.1 → 1.2.2）。
- README "快速使用" 重写为"零代码三选一"。
