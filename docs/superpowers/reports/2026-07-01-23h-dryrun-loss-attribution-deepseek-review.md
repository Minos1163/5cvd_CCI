# 2026-06-30 20:00 CST 至 2026-07-01 19:15 CST Dry-Run 亏损归因与 DeepSeek 评审稿

> 目的：分析北京时间 `2026-06-30 20:00` 至日志最新 `2026-07-01 19:15:05` 约 23.25 小时 dry-run / paper trading 结果，供 DeepSeek 评审。本文只分析日志并新增文档，不修改策略代码或配置。

## 1. 分析范围

- 窗口开始：`2026-06-30 20:00:00 CST`，对应 UTC `2026-06-30 12:00:00`。
- 窗口结束：日志最新 `2026-07-01 19:15:05 CST`。
- 覆盖文件：
  - `logs/2026-06/2026-06-30/paper_trades.jsonl`
  - `logs/2026-07/2026-07-01/paper_trades.jsonl`
  - `logs/2026-06/2026-06-30/decisions.jsonl`
  - `logs/2026-07/2026-07-01/decisions.jsonl`
  - `logs/2026-06/2026-06-30/summary.json`
  - `logs/2026-07/2026-07-01/summary.json`
  - `logs/2026-06/2026-06-30/paper_summary.json`
  - `logs/2026-07/2026-07-01/paper_summary.json`
- 运行配置：runtime header 显示 `config=configs/entry_chain.dry_run_fib_pa_v1.json`，`target_tier=aggressive`。
- 安全状态：`exchange_mutation_enabled=False`，`orders_submitted=0`。这是 dry-run，没有真实交易所下单。

注意：本窗口跨越上一轮防御规则上线后的阶段。日志中已出现 `HIGH_BETA_PROBE_BELOW_*`、`PROBE_BELOW_RISK_REWARD_GEOMETRY_*`、`SYMBOL_POST_INITIAL_STOP_COOLDOWN` 等新防线原因，因此不能直接和上一窗口的 8 连亏同口径比较。

## 2. 总结论

本窗口共 `1132` 条决策，只有 `2` 笔 PROBE 开仓，全部为 SHORT，`1` 赢 `1` 亏，窗口净 PnL `-3.5829 USDT`，profit factor `0.4180`。完整持仓生命周期口径下：

- 总毛 PnL：`-1.6227 USDT`
- 总成本：`1.9601 USDT`
- 总净 PnL：`-3.5829 USDT`
- 胜率：`50%`

这次亏损已经不是上一窗口那种 PROBE 通道全面溃败。亏损结果高度集中于一笔 `HYPEUSDT SHORT` 初始止损：该笔净亏 `-6.1561 USDT`，完全吞掉了 `SOLUSDT SHORT` 的 `+2.5733 USDT` 净盈利。

核心归因是：**高 beta 标的从 DIRECT 被降级为 PROBE 后，没有重新执行 PROBE 的高 beta 准入门槛，导致 `HYPEUSDT` 在 `fibonacci_location=9/18` 低于 PROBE 最低 `12/18` 的情况下仍然开仓。**

## 3. 交易明细

| 开仓 CST | 平仓 CST | 标的 | 方向 | 分数 | 杠杆 | 名义本金 | 毛 PnL | 成本 | 净 PnL | 退出原因 | 持仓 | 关键评分 |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| 06-30 20:00 | 06-30 21:45 | SOLUSDT | SHORT | 76.4408 | 3x | 489.5665 | +3.5489 | 0.9756 | +2.5733 | BREAKEVEN_STOP_HIT | 1.75h | RR 2/8, CCI 1.2508/14 |
| 07-01 09:00 | 07-01 09:30 | HYPEUSDT | SHORT | 83.19 | 3x | 489.6951 | -5.1716 | 0.9846 | -6.1561 | INITIAL_STOP_HIT | 0.50h | Fib 9/18, RR 5/8 |

SOLUSDT 生命周期：

- 20:00 开仓 SHORT。
- 20:30 TP1 减仓 `40%`，净增 `+1.1994`。
- 20:45 TP2 减仓 `35%`，净增 `+1.8633`。
- 21:45 剩余 `25%` 保本止损，最终整笔净赚 `+2.5733`。

HYPEUSDT 生命周期：

- 09:00 开仓 SHORT，开仓原因 `FIB_PA_ARCHITECTURE_WEIGHTS,HIGH_BETA_PROBE_ONLY`。
- 09:30 初始止损，整笔净亏 `-6.1561`。

## 4. 决策统计

窗口内 `decisions.jsonl` 共 `1132` 条：

| Action | 次数 |
|---|---:|
| NO_TRADE | 1023 |
| WATCH | 107 |
| PROBE | 2 |
| DIRECT | 0 |

Top reasons：

| Reason | 次数 | 含义 |
|---|---:|---|
| FIB_PA_ARCHITECTURE_WEIGHTS | 1132 | 全窗口使用 Fib/PA 权重体系 |
| SIDE_THRESHOLD_OFFSET_LONG_10.00 | 279 | 多头阈值上调仍频繁触发 |
| SYMBOL_BLACKLISTED | 182 | 黑名单标的拦截 |
| SYMBOL_WATCH_ONLY | 152 | watch-only 标的拦截 |
| FIB_EXTENSION_EXHAUSTION_BLOCK | 116 | Fib 延伸耗尽拦截 |
| DAILY_TRADE_BUDGET_USED | 115 | 日预算拦截 |
| SYMBOL_DAILY_TRADE_BUDGET_USED | 36 | 单 symbol 日预算拦截 |
| PROBE_BELOW_FIBONACCI_LOCATION_* | 14 | PROBE Fib 位置不足拦截 |
| HIGH_BETA_PROBE_BELOW_* | 14 | 高 beta PROBE 额外门槛拦截 |
| PROBE_BELOW_RISK_REWARD_GEOMETRY_* | 11 | PROBE RR 不足拦截 |

新增防线观察：

- `HIGH_BETA_PROBE_BELOW_*`：`14` 次，说明高 beta 额外门槛确实在工作。
- `PROBE_BELOW_RISK_REWARD_GEOMETRY_*`：`11` 次，说明 RR 加硬拦截了大量边缘交易。
- `SYMBOL_POST_INITIAL_STOP_COOLDOWN`：`1` 次。
- `SYMBOL_ROLLING_INITIAL_STOP_COOLDOWN`：`1` 次。
- `PORTFOLIO_DAILY_LOSS_CIRCUIT_BREAKER`：`0` 次。
- `PORTFOLIO_CONSECUTIVE_INITIAL_STOP_CIRCUIT_BREAKER`：`0` 次。

交易频率观察：实际 `2` 次开仓，远低于目标 `10-20` 次/24h。防线明显止血，但当前信号覆盖不足。

## 5. 亏损归因

### 5.1 一级归因：单笔 HYPE 初始止损吞掉 SOL 盈利

本窗口总亏 `-3.5829 USDT`，结构如下：

| 退出原因 | 笔数 | 毛 PnL | 成本 | 净 PnL |
|---|---:|---:|---:|---:|
| BREAKEVEN_STOP_HIT | 1 | +3.5489 | 0.9756 | +2.5733 |
| INITIAL_STOP_HIT | 1 | -5.1716 | 0.9846 | -6.1561 |

因此，亏损不是由小盈利被成本吞噬造成，而是 HYPE 的方向/入场质量失败造成。成本只是把 HYPE 的 `-5.1716` 毛亏扩大到 `-6.1561` 净亏。

### 5.2 二级归因：HIGH_BETA_PROBE_ONLY 降级后没有重新应用 PROBE 门槛

HYPEUSDT 09:15 决策：

- `action=PROBE`
- `score=83.19`
- `reasons=["FIB_PA_ARCHITECTURE_WEIGHTS","HIGH_BETA_PROBE_ONLY"]`
- `fibonacci_location=9/18`
- `price_action_structure=21/22`
- `risk_reward_geometry=5/8`
- `cci_momentum_quality=14/14`
- `trend_ema_context=16.19/20`

问题在于：dry-run 配置中普通 PROBE 要求 `min_fib_score=12/18`，HIGH_BETA 还应该更严格。但 HYPE 这笔 `fib=9/18` 仍然开仓。原因链推断如下：

1. 原始分数足以进入 DIRECT。
2. DIRECT 组件最低分只要求 `fib_min_direct_score=6/18`、`pa_min_direct_score=6/22`、`rr_min_direct_score=4/8`。
3. HYPE 是 HIGH_BETA，DIRECT 被规则降级为 PROBE。
4. 降级后没有重新调用 PROBE 条件检查，所以绕过了 `probe_conditions.min_fib_score=12/18`。

这不是参数问题，而是动作降级后的门槛复检缺口。

### 5.3 三级归因：SOL 盈利证明退出逻辑有改善，但低 RR 仍值得警惕

SOLUSDT 20:15 PROBE 的 `risk_reward_geometry=2/8`、`cci=1.2508/14`，按当前加强后的规则本应更可疑。但它最终 TP1/TP2 后保本止损，净赚 `+2.5733`。

这说明：

- 分批止盈 + 保本止损对顺行交易有效。
- 低 RR 并非每笔必亏，但它是风险暴露来源。
- 单笔盈利不能证明低 RR 门槛应放松；上一窗口大量低 RR 交易亏损，本窗口只是样本太少。

### 5.4 四级归因：止血规则有效，但把开仓频率压到极低

本窗口只有 2 笔开仓。大量信号被拦截：

- HIGH_BETA 额外门槛拦截 `14` 次。
- RR 不足拦截 `11` 次。
- Fib 不足拦截 `14` 次。
- 日预算仍拦截 `115` 次，单 symbol 预算拦截 `36` 次。

这说明上一轮防线有效地减少了亏损机会，但目标 `10-20` 次/24h 没有达成。当前状态更像“止血成功但交易覆盖不足”，不是“盈利模型已经稳定”。

### 5.5 五级归因：数据健康在 7/1 为 DEGRADED

`logs/2026-07/2026-07-01/summary.json` 显示 `data_health=DEGRADED`。本报告没有把它直接归因为亏损原因，因为 HYPE 的止损可由入场质量解释；但 DEGRADED 会降低对信号质量的信任，应在 DeepSeek 评审中重点确认 degraded 的具体来源。

## 6. 与上一轮优化目标的关系

上一轮目标是止住 PROBE 溃败，同时尽量提升到 `10-20` 次/24h。当前结果：

- 止血：明显改善。上一窗口 8 笔全亏，本窗口 2 笔 1 胜 1 负，总亏缩小到 `-3.5829`。
- 质量：仍有漏洞。HYPE 暴露了 HIGH_BETA DIRECT 降级后没有复检 PROBE 门槛。
- 频率：严重不足。23.25 小时只有 2 笔开仓。
- 风控：symbol stop cooldown 已触发过一次，证明应激冷却上线。

优先级建议：

1. 先修 HIGH_BETA DIRECT→PROBE 降级后复检 PROBE 条件。
2. 再研究如何扩大高质量信号来源，而不是放松 RR/Fib/HighBeta 门槛。
3. 对 `DAILY_TRADE_BUDGET_USED` 的 115 次拦截做更细日志，区分是真预算不足，还是已有持仓/单 symbol 预算/动态预算计算导致的机会损失。

## 7. DeepSeek 评审问题

1. HIGH_BETA 从 DIRECT 降为 PROBE 后，是否必须重新执行完整 `check_probe_conditions`？
2. DIRECT 的 `fib_min_direct_score=6/18` 是否过低？本窗口 HYPE 通过 DIRECT 的根源之一就是 DIRECT Fib 门槛远低于 PROBE。
3. 是否应规定：任何被 `HIGH_BETA_PROBE_ONLY` 降级的交易，必须同时满足 HIGH_BETA PROBE 的 `fib>=12`、`rr>=5`、`cci>=9`、`ema>=12`？
4. HYPE 这种 `fib=9/18`、`rr=5/8`、`cci=14/14` 的组合，是应该完全禁止，还是允许小仓试探？
5. SOLUSDT 低 RR/低 CCI 但盈利，是否说明低 RR 门槛过严会误杀？还是只是小样本中的幸运顺行？
6. 当前 `2` 次/23.25h 的开仓频率是否过低？如果过低，应优先扩展标的池、增加策略类型，还是放松现有门槛？
7. `DAILY_TRADE_BUDGET_USED=115` 是否仍在错误压制机会？需要哪些日志字段才能判断动态预算是否合理？
8. `data_health=DEGRADED` 的来源是否可能影响 Fib/PA/CCI 信号？是否应在 DEGRADED 时禁止 HIGH_BETA 开仓？
9. 组合级熔断本窗口没有触发，日亏阈值 `-30 USDT` 是否过宽？对于小样本 dry-run 是否应使用连续亏损/连续初始止损优先？
10. 下一步是否应补 MFE/MAE 回放，特别验证 HYPE 是入场后直接逆行，还是止损过近？

## 8. 建议给 DeepSeek 的一句话结论

本窗口亏损已从“PROBE 全面溃败”收敛为“单笔 HIGH_BETA 降级路径漏洞”：SOLUSDT 分批止盈后净赚 `+2.57`，但 HYPEUSDT 因 DIRECT→PROBE 降级后未复检 PROBE Fib 门槛，在 `fib=9/18` 下开仓并 30 分钟初始止损，净亏 `-6.16`；当前优先级是修复降级后复检，而不是继续单纯加宽或放松参数。
