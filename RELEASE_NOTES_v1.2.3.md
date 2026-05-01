# grid-trading-skill v1.2.3

**用户体验修复版** —— 解决 v1.2.2 在自动模式回测里报告刷出大量 `above_upper /
below_lower` 告警的问题。

## 修了什么

### 1. 回测窗口对齐 (`--window`)

之前推荐器用最近 120 根日线（6 个月）算上下限，但 `--backtest auto`
回放 250 根（约 1 年），结果 6~12 个月前的"老价"频频越界，触发一堆
重复告警。

**v1.2.3 起**：`--backtest auto` 默认使用与 `--window` 同样长度的 K 线，
所以推荐区间覆盖回测区间，告警只在真实越界时出现。

```bash
# 默认：6 个月推荐 + 6 个月回测
npx grid-trading-skill auto 600519 50000 --backtest

# 想看 1 年视角：推荐和回测都用 1 年数据
npx grid-trading-skill auto 600519 50000 --window 260 --backtest
```

### 2. 告警边沿触发去重

`BacktestSimulator` 现在做"状态变化时才告警"的语义去重：
价格连续 N 根日线越界，只在**进入越界时**告警一次，回到区间内会
重置，下次再越界又会重新告警。

之前同类型告警可能在屏幕上重复几十次，现在最多看到几条真实事件。

## 不变

- 数据接口、推荐算法、HTML 报告样式都不变
- 所有 v1.2.0 / v1.2.1 / v1.2.2 命令继续工作
- 告警去重不影响 `total_return / sharpe / max_drawdown` 等回测指标计算

## 测试

78 项全部通过（77 + 1 新增 `test_consecutive_same_alerts_deduplicated`）。
