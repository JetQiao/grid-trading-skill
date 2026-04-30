# grid-trading-skill v1.2.1

**Real-data auto-recommendation** — fetch live market data with zero API
keys, then output a recommended center price plus grid upper/lower bounds.

## Highlights

- **`--auto SYMBOL`** — one command pulls real data and emits a complete
  HTML report with **建议中线价、建议网格下限、建议网格上限、建议格数 / 类型**.
  Works for A-share / HK / US / crypto.
- **Multi-source fetcher chain** — every data category has a primary plus
  fallbacks. A failed source falls through to the next without raising.
- **No paid APIs** — pure stdlib HTTP. `akshare` / `yfinance` are optional
  upgrades; the default path uses only public web endpoints.
- **5-minute file cache** for hot lists (social, macro), per spec.
- **Real K-line backtest replay** via `--backtest auto`.
- **`--json` output** for chaining the recommendation into other tools.

## New CLI flags

```
--auto SYMBOL            real-data mode; overrides --lower/--upper/--count
--window N               bars analyzed (default 120 ≈ 6 months daily)
--method {sigma,atr,quantile}
--safety F               1.0=neutral, 1.2=wider band
--max-grids N            cap on auto-recommended grid count (default 60)
--backtest auto          replay real K-line history (auto mode only)
--json                   emit JSON instead of HTML
```

## New modules

```
grid_trading/data/        — http, cache, symbol, quote, kline,
                            fundamentals, flows, disclosures, macro, social
grid_trading/recommend/   — recommend_grid + GridRecommendation
```

## Data sources (all free, all key-less)

| 类别                     | 主源                               | 备用                                |
|--------------------------|------------------------------------|-------------------------------------|
| 实时行情 / PE / 市值     | 东方财富 push2                     | 雪球 → 腾讯 → 新浪 → Yahoo          |
| K 线 / 技术指标          | akshare（可选）                    | 东方财富 push2his → Yahoo           |
| 财报 / PE / PB / ROE     | akshare（可选）                    | 东方财富 F10 → Yahoo                |
| 龙虎榜 / 北向 / 两融     | akshare（可选）                    | 东方财富 datacenter                 |
| 公告 / 研报              | 巨潮 cninfo                        | 东方财富 报告中心                   |
| 港股                     | akshare hk / 东方财富               | Yahoo `.HK`                         |
| 美股                     | Yahoo Finance                      | akshare us                          |
| 加密                     | Binance public ticker / klines     | —                                   |
| 宏观 / 政策 / 舆情       | DuckDuckGo HTML 搜索               | —                                   |
| 社交热榜（v2.12）        | 微博/知乎/百度/抖音/头条/B 站 官方 JSON | 5 分钟文件缓存，单平台失败隔离       |

## Recommendation algorithm (deterministic)

1. Mid price = `0.7 × median(closes) + 0.3 × current_price`.
2. Bounds:
   - `sigma`: `mid ± 2σ_close` (default)
   - `atr`:   `mid ± 8 × ATR`
   - `quantile`: anchor 10–90% percentile around mid
3. Clamp to `[0.97 × window_min, 1.03 × window_max]`; minimum 2% half-width.
4. Grid type: geometric for >1.5x range, else arithmetic.
5. Grid count: largest N such that `step_ratio > 2 × fee_rate`,
   capped by `--max-grids`, floored at 6.

## Tests

77 tests pass, up from 48:
- `test_data_symbol.py` — 16 cross-market symbol parsing tests
- `test_data_cache.py` — 4 TTL cache tests
- `test_recommend.py` — 9 deterministic recommender tests

## Compatibility

- No new required dependencies. `akshare` / `yfinance` remain optional.
- All v1.2.0 manual-mode commands keep working unchanged.
- Python 3.11+ (unchanged).
