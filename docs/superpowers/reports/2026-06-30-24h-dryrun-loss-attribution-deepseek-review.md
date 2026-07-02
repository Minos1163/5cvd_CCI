# 2026-06-29 20:00 CST 至 2026-06-30 20:00 CST Dry-Run 亏损归因与 DeepSeek 评审稿

> 目的：分析北京时间 `2026-06-29 20:00` 至日志最新 `2026-06-30 20:00:05` 约 24 小时 dry-run / paper trading 结果，供 DeepSeek 评审。本文只分析日志并新增文档，不修改策略代码或配置。

## 1. 分析范围

- 窗口开始：`2026-06-29 20:00:00 CST`，对应 UTC `2026-06-29 12:00:00`。
- 窗口结束：日志最新 `2026-06-30 20:00:05 CST`。
- 主证据：
  - `logs/2026-06/2026-06-29/paper_trades.jsonl`
  - `logs/2026-06/2026-06-30/paper_trades.jsonl`
  - `logs/2026-06/2026-06-29/decisions.jsonl`
  - `logs/2026-06/2026-06-30/decisions.jsonl`
  - `logs/2026-06/2026-06-30/paper_summary.json`
  - `logs/2026-06/2026-06-30/summary.json`
  - `logs/2026-06/2026-06-30/runtime.out.06.log`
- 运行配置：runtime header 显示 `config=configs/entry_chain.dry_run_fib_pa_v1.json`，`target_tier=aggressive`，`market_data_source=public-binance`。
- 安全状态：日志显示 `exchange_mutation_enabled=False`，`orders_submitted=0`。这是 dry-run，没有真实交易所下单。

注意：当前工作区存在上一轮 dry-run 优化的未提交代码改动；本报告只读取日志。日志本身显示 6/30 运行已经使用 `entry_chain.dry_run_fib_pa_v1.json`，且决策原因中出现 `COST_BREAKEVEN_TIMEOUT`、`DIRECT_BELOW_RISK_REWARD_GEOMETRY...` 等优化后特征。

## 2. 总结论

本 24 小时窗口共 `8` 笔开仓，全部闭合，`0` 胜 `8` 负，窗口净 PnL `-46.9346 USDT`，胜率 `0%`，profit factor `0.0`。平仓前 gross PnL 已经是 `-39.1110 USDT`，费用加滑点为 `7.8237 USDT`，所以这次亏损的第一归因不是“小盈利被成本吞噬”，而是开仓方向/时机失败导致交易本身没有正毛利。

亏损结构非常集中：

- `INITIAL_STOP_HIT`：`5` 笔，净亏 `-43.7848 USDT`，占窗口亏损约 `93.3%`。
- `COST_BREAKEVEN_TIMEOUT`：`3` 笔，净亏 `-3.1499 USDT`，主要是小幅横盘/弱毛利被提前止血。
- `TP1/TP2/TP3`：`0` 笔。
- `BREAKEVEN_STOP_HIT`：`0` 笔。

这说明上一轮新增的成本保本超时逻辑确实在 3 笔交易上“减少继续持有”，但并没有解决核心问题：PROBE 开仓质量仍然不足，尤其是低 RR、低动能、高 overextension 的信号仍能入场，并且入场后很快止损。

## 3. 交易明细

| 开仓 CST | 平仓 CST | 标的 | 方向 | 动作 | 分数 | 杠杆 | 名义本金 | 净 PnL | 毛 PnL | 成本 | 退出原因 | 持仓 |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| 06-29 20:00 | 06-29 20:30 | BNBUSDT | LONG | PROBE | 87.30 | 3x | 491.91 | -3.6017 | -2.6205 | 0.9812 | INITIAL_STOP_HIT | 0.50h |
| 06-29 20:00 | 06-29 20:30 | DOGEUSDT | LONG | PROBE | 88.80 | 3x | 491.89 | -4.6938 | -3.7137 | 0.9801 | INITIAL_STOP_HIT | 0.50h |
| 06-29 22:45 | 06-30 00:15 | LABUSDT | LONG | PROBE | 78.5927 | 3x | 491.50 | -15.7132 | -14.7450 | 0.9683 | INITIAL_STOP_HIT | 1.50h |
| 06-30 08:45 | 06-30 11:15 | LINKUSDT | SHORT | PROBE | 73.0114 | 3x | 490.71 | -1.3177 | -0.3359 | 0.9818 | COST_BREAKEVEN_TIMEOUT | 2.50h |
| 06-30 10:00 | 06-30 12:30 | BNBUSDT | SHORT | PROBE | 84.70 | 3x | 490.69 | -0.0522 | +0.9283 | 0.9804 | COST_BREAKEVEN_TIMEOUT | 2.50h |
| 06-30 10:45 | 06-30 12:30 | LABUSDT | LONG | PROBE | 81.50 | 3x | 490.66 | -14.7648 | -13.7973 | 0.9675 | INITIAL_STOP_HIT | 1.75h |
| 06-30 16:30 | 06-30 19:00 | SOLUSDT | SHORT | PROBE | 84.19 | 3x | 489.91 | -1.7800 | -0.7994 | 0.9806 | COST_BREAKEVEN_TIMEOUT | 2.50h |
| 06-30 17:15 | 06-30 18:45 | HYPEUSDT | SHORT | PROBE | 86.69 | 3x | 489.88 | -5.0112 | -4.0275 | 0.9838 | INITIAL_STOP_HIT | 1.50h |

按标的聚合：

| 标的 | 笔数 | 净 PnL | 归因 |
|---|---:|---:|---|
| LABUSDT | 2 | -30.4780 | 最大亏损源，两笔 LONG 全部初始止损 |
| HYPEUSDT | 1 | -5.0112 | HIGH_BETA SHORT 初始止损 |
| DOGEUSDT | 1 | -4.6938 | LONG 初始止损 |
| BNBUSDT | 2 | -3.6539 | 一笔 LONG 初始止损，一笔 SHORT 成本保本超时 |
| SOLUSDT | 1 | -1.7800 | SHORT 成本保本超时 |
| LINKUSDT | 1 | -1.3177 | SHORT 成本保本超时 |

按方向聚合：

| 方向 | 笔数 | 净 PnL | 胜 | 负 |
|---|---:|---:|---:|---:|
| LONG | 4 | -38.7735 | 0 | 4 |
| SHORT | 4 | -8.1611 | 0 | 4 |

本窗口多头亏损更重，尤其 LABUSDT 两笔 LONG 贡献了窗口总亏损的约 `64.9%`。

## 4. 决策统计

窗口内 `decisions.jsonl` 共 `1261` 条：

- `NO_TRADE = 1137`
- `WATCH = 116`
- `PROBE = 8`
- `DIRECT = 0`

所有 8 笔开仓都是 PROBE，没有 DIRECT。Top reasons：

| Reason | 次数 | 含义 |
|---|---:|---|
| FIB_PA_ARCHITECTURE_WEIGHTS | 1261 | 全窗口使用 Fib/PA 权重体系 |
| SIDE_THRESHOLD_OFFSET_LONG_10.00 | 241 | 多头阈值加 10，但仍有多头 PROBE 放行 |
| DAILY_TRADE_BUDGET_USED | 211 | 交易预算仍频繁拦截 |
| SYMBOL_WATCH_ONLY | 179 | 观察名单拦截 |
| SYMBOL_BLACKLISTED | 170 | 黑名单拦截 |
| FIB_EXTENSION_EXHAUSTION_BLOCK | 131 | Fib 延伸耗尽拦截 |
| SYMBOL_POSITION_ALREADY_OPEN | 50 | 已有持仓拦截 |
| PROBE_BELOW_FIBONACCI_LOCATION... | 24 | Fib 位置不足导致 WATCH |
| SYMBOL_ROLLING_INITIAL_STOP_COOLDOWN | 4 | 滚动止损冷却触发 |

频率目标观察：用户目标是 `24h 10-20` 次开仓，实际只有 `8` 次。虽然开仓数低于目标，但 `DAILY_TRADE_BUDGET_USED` 仍出现 `211` 次。日志中的动态 `daily_max_trades` 从 `1` 到 `32` 都出现过，说明交易预算不是固定常数，而是受 `current_volatility_scale / normal_volatility_scale` 调整；某些时段 daily max 很低，仍会提前拦截机会。

## 5. 亏损归因

### 5.1 一级归因：低质量 PROBE 放量，8 笔无一正收益

8 笔开仓全是 PROBE，且全部亏损。窗口 gross PnL 已经为负，说明问题不只是成本，而是开仓后价格没有给出足够顺行空间。交易质量不足主要表现为：

- 多笔交易 `risk_reward_geometry` 只有 `2.0/8` 或 `3.5/8`。
- 多笔交易虽然总分较高，但依赖 `flow_cvd_confirmation=18/18`、`price_action_structure=21/22`、`fibonacci_location=18/18` 堆分，RR 和动能质量不足。
- 部分多头有 `long_overextension_active=True`，但仍开仓并快速止损。

典型例子：

- `BNBUSDT LONG score=87.3`：RR `2.0/8`，`risk_reward_geometry` normalized `0.25`，`long_overextension_active=True`，30 分钟初始止损。
- `DOGEUSDT LONG score=88.8`：RR `3.5/8`，`long_overextension_active=True`，30 分钟初始止损。
- `LABUSDT LONG score=78.5927`：`cci_momentum_quality=1.4027/14`，动能极弱，仍开 PROBE，最终初始止损。
- `LINKUSDT SHORT score=73.0114`：`cci=2.8214/14`，RR `2.0/8`，最终成本保本超时。

### 5.2 二级归因：LABUSDT 多头是最大单点亏损源

LABUSDT 两笔 LONG 净亏 `-30.4780 USDT`，是窗口最大亏损源：

- 06-29 22:45 开仓，score `78.5927`，`cci_momentum_quality=1.4027/14`，1.5 小时后 `INITIAL_STOP_HIT`，净亏 `-15.7132`。
- 06-30 10:45 开仓，score `81.5`，`trend_ema_context=8/20`，1.75 小时后 `INITIAL_STOP_HIT`，净亏 `-14.7648`。

这说明高 beta / LAB 的多头 PROBE 过滤仍不够。即使多头阈值有 `SIDE_THRESHOLD_OFFSET_LONG_10.00`，也不能阻止低动能或弱趋势上下文的 LAB 多头反复开仓。

### 5.3 三级归因：RR 几何门槛仍允许“刚过线”交易进场

窗口内多笔 PROBE 的 RR 很低：

- BNB LONG：RR `2.0/8`，net_tp1_r `1.012`。
- LINK SHORT：RR `2.0/8`，net_tp1_r `1.009`。
- BNB SHORT：RR `2.0/8`，net_tp1_r `1.000`。
- SOL SHORT：RR `2.0/8`，net_tp1_r `1.035`。
- HYPE SHORT：RR `3.5/8`，net_tp1_r `1.078`。

这些交易理论上能覆盖 TP1 的最小成本，但缺乏足够边际。结果是：要么直接初始止损，要么在 2.5 小时成本检查时仍没有足够利润空间。

### 5.4 四级归因：成本保本超时是在止血，不是盈利机制

`COST_BREAKEVEN_TIMEOUT` 出现 3 次：

- LINKUSDT SHORT：净亏 `-1.3177`
- BNBUSDT SHORT：毛利 `+0.9283`，但成本 `0.9804`，净亏 `-0.0522`
- SOLUSDT SHORT：净亏 `-1.7800`

这说明新退出规则有效避免了继续拖到 8 小时，但它只能减少尾部时间成本，不能把低质量入场变成盈利入场。它暴露了一个事实：部分交易在入场 2.5 小时后仍无法覆盖往返成本，说明入场预期没有兑现。

### 5.5 五级归因：放量目标和质量目标仍冲突

实际 24h 开仓 `8` 次，低于目标 `10-20`，但结果已经是 8 连亏。如果继续单纯放量，亏损大概率扩大。当前更合理的优先级应是：

1. 先提升 PROBE 质量，尤其高 beta、多头 overextension、低 CCI、低 RR。
2. 再评估开仓频率是否达到 `10-20/24h`。
3. 如果质量过滤后频率不足，应扩大交易对或改进信号，而不是降低 RR/PA/动能门槛。

## 6. 与上一轮优化目标的关系

上一轮目标是“大胆优化，同时将交易量提升到 24h 10-20 次开仓”。本窗口表现说明：

- 交易量：`8` 次，未达 `10-20`。
- 质量：更差，8 笔全部亏损。
- 风控：`COST_BREAKEVEN_TIMEOUT` 在 3 笔上减少了继续持有，但无法覆盖初始止损集中爆发。
- 日预算：仍频繁触发 `DAILY_TRADE_BUDGET_USED`，动态预算可能压低部分时段开仓机会，但已开仓机会质量不足更紧急。

因此，本轮不建议继续单纯提高 daily budget。需要先让 PROBE 通道变得更挑剔：

- 低 RR 只给 WATCH，不给 PROBE。
- 高 beta 的 PROBE 要求更高 CCI/趋势上下文。
- 多头 overextension 应进入硬门槛，而不是只作为原因记录。
- LABUSDT 这类高 beta 连续止损后应更快冷却，当前 48h 内 2 次初始止损才冷却，可能仍偏慢。

## 7. DeepSeek 评审问题

1. PROBE 是否应要求 `risk_reward_geometry >= 4/8`，而不是允许 `2/8` 或 `3.5/8`？
2. 对 `net_tp1_r` 是否应从 `>=1.0` 提升到 `>=1.2` 或更高，确保扣成本后仍有足够边际？
3. 对 LAB/HYPE/CC 等 HIGH_BETA 标的，是否应要求 `cci_momentum_quality >= 7/14` 或 `trend_ema_context >= 14/20` 才允许 PROBE？
4. 对 `long_overextension_active=True` 的多头，是否应直接 WATCH，或至少要求 RR/CCI/PA 全部高于普通门槛？
5. LABUSDT 两笔多头初始止损后，是否应把 rolling cooldown 从“48h 内 2 次”改为“同 symbol 任意 1 次初始止损后冷却 12-24h”？
6. `COST_BREAKEVEN_TIMEOUT` 现在 2.5h 左右触发，是否应该更早，例如 1.5h 或 2h？还是应该只对未达到 `0.5R` 的仓位触发？
7. 当前日预算动态值从 1 到 32 波动，是否需要把 `daily_max_trades_base` 和 `current_volatility_scale` 的关系写入日志，便于判断为何 `DAILY_TRADE_BUDGET_USED` 仍频繁出现？
8. 当前 8 笔全亏时，是否应触发“组合级熔断”：例如 rolling 24h 连续 3 笔初始止损或日内净亏超过某阈值后停止新仓？
9. 如果目标仍是 `10-20` 次/24h，是否应通过扩大可交易标的池或改善信号覆盖来实现，而不是放松 PROBE 门槛？
10. 是否需要立刻补 MFE/MAE 回放，区分这些初始止损是“入场后从未顺行”，还是“止损太近被扫后顺行”？

## 8. 建议给 DeepSeek 的一句话结论

本窗口不是成本小问题，而是 PROBE 放量后的信号质量问题：8 笔全部亏损，5 笔初始止损贡献约 93% 窗口亏损，LABUSDT 多头是最大亏损源；成本保本超时只是在止血，不能替代更严格的 RR、动能、高 beta、overextension 和连续止损冷却门槛。

