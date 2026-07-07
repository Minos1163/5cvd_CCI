# 2026-07-02 20:00 CST 至 2026-07-04 08:45 CST 进攻态势执行效果归因与 DeepSeek 评审稿

> 目的：分析北京时间 `2026-07-02 20:00` 至日志最新 `2026-07-04 08:45:05` 约 `36.75` 小时 dry-run / paper trading 结果，解释为什么“扩大盈利点”的进攻态势执行效果不理想，供 DeepSeek 评审。本文只分析日志并新增文档，不修改策略代码或配置。

## 1. 分析范围

- 窗口开始：`2026-07-02 20:00:00 CST`，对应 UTC `2026-07-02 12:00:00`。
- 窗口结束：日志最新 `2026-07-04 08:45:05 CST`。
- 覆盖文件：
  - `logs/2026-07/2026-07-02/decisions.jsonl`
  - `logs/2026-07/2026-07-03/decisions.jsonl`
  - `logs/2026-07/2026-07-04/decisions.jsonl`
  - `logs/2026-07/2026-07-02/near_misses.jsonl`
  - `logs/2026-07/2026-07-03/near_misses.jsonl`
  - `logs/2026-07/2026-07-04/near_misses.jsonl`
  - `logs/2026-07/2026-07-*/paper_trades.jsonl`
  - `logs/2026-07/2026-07-*/summary.json`
  - `logs/2026-07/2026-07-*/paper_summary.json`
  - `logs/2026-07/2026-07-*/health.json`
- 运行状态：`mode=dry_run`，`exchange_mutation_enabled=false`，`orders_submitted=0`。
- 注意：本窗口已有 `near_misses.jsonl`，说明上一轮 SCOUT / 近失记录器已经上线并运行。

## 2. 总结论

本窗口确实只有 `1` 次开仓，且该开仓最终 `COST_BREAKEVEN_TIMEOUT` 亏损退出。整体结果不是“进攻层没有记录机会”，而是：

1. **SCOUT 目前只是观察层，不是交易层**：它记录了 `14` 个高分近失，但不会生成 PROBE / DIRECT，也不会开 paper 微仓。
2. **主交易门槛仍然是防御体系**：`1776` 条决策里只有 `1` 条 PROBE、`0` 条 DIRECT；主交易频率约 `0.65` 次/24h，远低于目标。
3. **唯一开仓质量偏弱**：LINKUSDT SHORT 只是 `score=72.0` 的擦边 PROBE，`trend_ema_context=8/20`、`cci=7/14`，不是高质量进攻信号。
4. **near-miss 回放没有证明可以马上放宽**：14 个近失样本 60m 中位 MFE 只有 `0.1436%`，中位 MAE 为 `-0.2768%`；多数不支持立即升级为主交易。
5. **数据健康为 DEGRADED**：虽然 warmup ready，但最新 summary / health 均为 `data_health=DEGRADED`，在进攻阶段会降低对信号放大的信心。

一句话：**进攻态势执行效果不理想的核心原因，是“侦察系统上线了，但主力交易并未获得经过验证的新规则或新标的晋级”；唯一实际开仓又是低门槛擦边 PROBE，没能代表进攻层的高质量机会。**

## 3. 决策与交易统计

窗口内共有 `1776` 条决策：

| Action | 次数 | 占比 |
|---|---:|---:|
| NO_TRADE | 1654 | 93.13% |
| WATCH | 121 | 6.81% |
| PROBE | 1 | 0.06% |
| DIRECT | 0 | 0.00% |

执行审计：

| 指标 | 数值 |
|---|---:|
| attribution decision events | 1776 |
| attribution execution events | 1776 |
| execution noop | 1775 |
| execution draft_ready | 1 |
| approved executions | 1 |
| paper opens | 1 |
| paper closes | 1 |

最新账户状态：

| 指标 | 数值 |
|---|---:|
| equity | 9785.4427 |
| realized_pnl | -214.5573 |
| trade_count | 57 |
| win_rate | 42.1053% |
| profit_factor | 0.6259 |
| max_drawdown | 3.7690% |
| open_positions | 0 |
| data_health | DEGRADED |

本窗口新增净 PnL 来自 LINKUSDT 一笔完整交易，约 `-2.3034 USDT` notional primary PnL。

## 4. 唯一开仓明细

| 时间 CST | 事件 | Symbol | 方向 | 价格 | 分数 | 杠杆 | 名义本金 | 说明 |
|---|---|---|---|---:|---:|---:|---:|---|
| 07-03 01:45:05 | 决策 PROBE | LINKUSDT | SHORT | 7.766 | 72.0 | 3x | 489.39 | 刚过 PROBE 门槛 |
| 07-03 01:30:00 | PAPER_OPEN | LINKUSDT | SHORT | 7.766 | 72.0 | 3x | 489.39 | kline timestamp；recorded_at 为 01:45:07 |
| 07-03 09:00:00 | PAPER_CLOSE | LINKUSDT | SHORT | 7.787 | - | 3x | - | COST_BREAKEVEN_TIMEOUT；recorded_at 为 09:15:07 |

开仓组件分：

| 组件 | 分数 | 评价 |
|---|---:|---|
| price_action_structure | 21/22 | 很强 |
| flow_cvd_confirmation | 18/18 | 很强 |
| fibonacci_location | 13/18 | 合格 |
| risk_reward_geometry | 5/8 | 合格 |
| cci_momentum_quality | 7/14 | 中等 |
| trend_ema_context | 8/20 | 偏弱 |

诊断：

- 这笔并不是高分 near-miss 晋级后的进攻信号，而是普通 PROBE 低分擦边通过。
- `trend_ema_context=8/20`，说明趋势上下文不强。
- `cci=7/14`，动能不是爆发型。
- 持仓约 7.5 小时，没有触发 TP，最终按成本保本超时退出。
- 价格从 `7.766` 到 `7.787`，对 SHORT 不利，毛亏 `-1.3233`，加上费用和滑点后整笔 position realized PnL 为 `-2.3034`。

结论：唯一开仓不代表“扩大盈利点”的成功执行，反而说明当前主交易仍会放行少量低强度 PROBE，而不是优先捕捉 SCOUT 发现的高质量候选。

## 5. 阻断原因

Top reasons：

| Reason | 次数 | 解释 |
|---|---:|---|
| FIB_PA_ARCHITECTURE_WEIGHTS | 1776 | 全窗口使用 Fib/PA 权重体系 |
| SIDE_THRESHOLD_OFFSET_LONG_10.00 | 682 | 多头阈值偏移仍是最大阻断 |
| SYMBOL_WATCH_ONLY | 263 | watch-only 标的限制 |
| SYMBOL_BLACKLISTED | 245 | 黑名单限制 |
| FIB_EXTENSION_EXHAUSTION_BLOCK | 183 | Fib 延伸耗尽 |
| SYMBOL_POSITION_ALREADY_OPEN | 30 | LINK 持仓期间同 symbol 被阻断 |
| PROBE_BELOW_FIBONACCI_LOCATION_* | 23 | PROBE Fib 不足 |
| PROBE_BELOW_RISK_REWARD_GEOMETRY_* | 22 | PROBE RR 不足 |
| DIRECT_BELOW_RISK_REWARD_GEOMETRY_* | 6 | DIRECT RR 不足 |
| HIGH_BETA_PROBE_BELOW_* | 3 | 高 beta 额外门槛不足 |

原因族：

| 原因族 | 次数 | 解释 |
|---|---:|---|
| SIDE_OFFSET | 682 | 多头侧仍被强力压制 |
| SYMBOL_SCOPE | 541 | 黑名单、watch-only、observation-only、已有仓位 |
| FIB_EXHAUSTION | 183 | 结构位置耗尽 |
| PROBE_BELOW_FIB | 23 | Fib 不足 |
| PROBE_BELOW_RR | 22 | RR 不足 |
| DIRECT_BELOW_RR | 6 | DIRECT RR 不足 |
| HIGH_BETA_PROBE_BELOW | 3 | 高 beta 附加规则 |

本窗口没有看到日预算成为主阻断。频率低的主因不是预算满了，而是门槛和 symbol scope 把绝大多数候选留在 WATCH / NO_TRADE。

## 6. SCOUT / near-miss 执行效果

窗口内 near-miss 共 `14` 条，约 `9.14` 条/24h，低于原先“10-30 次 SCOUT / 24h”的下沿。

near-miss 主因：

| primary_reason | 次数 |
|---|---:|
| SIDE_THRESHOLD_OFFSET_LONG_10.00 | 4 |
| DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0 | 3 |
| DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0 | 3 |
| SYMBOL_OBSERVATION_ONLY | 2 |
| SYMBOL_BLACKLISTED | 1 |
| SYMBOL_POSITION_ALREADY_OPEN | 1 |

near-miss symbol：

| Symbol | 次数 |
|---|---:|
| XLMUSDT | 4 |
| TRXUSDT | 4 |
| BNBUSDT | 2 |
| HYPEUSDT | 1 |
| XRPUSDT | 1 |
| LINKUSDT | 1 |
| CCUSDT | 1 |

near-miss 回放摘要：

| 窗口 | 中位 MFE | 中位 MAE | MFE >= 0.5% | MFE >= 1.0% |
|---|---:|---:|---:|---:|
| 30m | 0.1015% | -0.1470% | 4/14 | 0/14 |
| 60m | 0.1436% | -0.2768% | 4/14 | 0/14 |
| 120m | 0.2446% | -0.3926% | 4/14 | 1/14 |
| 240m | 0.2446% | -0.7094% | 5/14 | 2/14 |

代表样本：

| 时间 CST | Symbol | Side | Score | Reason | 240m MFE | 240m MAE | 评价 |
|---|---|---|---:|---|---:|---:|---|
| 07-02 23:00 | HYPEUSDT | LONG | 82.65 | SIDE_OFFSET | +2.4284% | -1.0320% | 有机会，但高 beta 且先承受较大逆行 |
| 07-03 03:15 | XLMUSDT | SHORT | 91.80 | OBSERVATION_ONLY | +0.9513% | -0.7337% | 可进入 symbol 晋级观察 |
| 07-03 04:30 | BNBUSDT | SHORT | 84.70 | RR gap 2 | +0.3189% | -0.3081% | 边际，不足以放宽 |
| 07-03 06:15 | BNBUSDT | SHORT | 84.70 | RR gap 2 | +0.0305% | -0.9838% | 明显不适合放行 |
| 07-03 10:30 | TRXUSDT | SHORT | 87.30 | RR gap 2 | +0.0000% | -0.8939% | 几乎无顺行 |
| 07-03 15:15 | XLMUSDT | LONG | 83.10 | SIDE_OFFSET | +2.4589% | -0.3513% | 最值得复盘的错杀候选 |
| 07-03 17:15 | XLMUSDT | LONG | 83.09 | SIDE_OFFSET | +0.0788% | -1.8424% | 同 symbol 但时点失败 |
| 07-04 04:15 | CCUSDT | LONG | 83.19 | SIDE_OFFSET | +0.5923% | -0.6280% | 高 beta，收益不够稳定 |

结论：

- SCOUT 记录器已工作，但只记录，不开仓。
- 14 个 near-miss 中，少数有明显 MFE，但多数 MFE/MAE 不支持直接升级为 PROBE。
- XLMUSDT 是最有价值的 symbol 晋级候选，但同一 symbol 的不同时间点分化很大，需要更多样本。
- RR gap 组整体表现差，证明当前 RR 防线仍有价值。

## 7. 为什么“扩大盈利点”执行效果不理想

### 7.1 进攻层是“数据采集”，不是“仓位放大”

上一轮实现的是 `near_misses.jsonl` 和离线 MFE/MAE 回放。这是 SCOUT Phase 1，不是 SCOUT 微仓，也不是 FAST_PROBE。因此它不会提高 paper open 数。

如果预期是“上线后开仓次数明显增加”，那当前实现天然达不到。它的成功指标应该是：

- 是否记录高分近失。
- 是否能回放 MFE/MAE。
- 是否能区分可晋级与不可晋级模式。

这三点基本达成，但“盈利点扩大”还没有进入执行层。

### 7.2 主交易仍由防御门槛主导

`PROBE=1`、`DIRECT=0`，说明主力交易仍高度保守。主要拦截来自：

- 多头 `+10` offset：`682` 次。
- symbol scope：`541` 次。
- Fib exhaustion：`183` 次。
- Fib / RR 组件不足：`51` 次以上。

这些规则保护了账户，但也使主交易频率维持在极低水平。

### 7.3 唯一开仓不是高质量进攻信号

LINKUSDT 的 `score=72.0` 刚好等于 `probe_conditions.min_score=72`。它不是高分近失晋级，也没有 SCOUT 模式验证，属于普通低强度 PROBE。

这解释了为什么“唯一一枪”没有打出盈利：

- 趋势上下文弱。
- 动能一般。
- 没有快速顺行。
- 最终被成本保本超时处理。

### 7.4 symbol 晋级尚未执行

XLMUSDT 出现多个高分近失，其中：

- `07-03 03:15 SHORT score=91.8`，240m MFE `+0.9513%`。
- `07-03 15:15 LONG score=83.1`，240m MFE `+2.4589%`。

但 XLMUSDT 仍是 `SYMBOL_OBSERVATION_ONLY`，没有转入 SCOUT 微仓或可交易池。因此它只能证明“可能有机会”，不能贡献交易频率。

### 7.5 近失样本质量还不够稳定

SCOUT 数据并非全是错杀：

- BNBUSDT RR gap 近失中，一个 240m MFE 仅 `0.0305%`，MAE `-0.9838%`。
- TRXUSDT 10:30 近失 240m MFE `0`，MAE `-0.8939%`。
- XLMUSDT 17:15 LONG 近失 240m MFE `0.0788%`，MAE `-1.8424%`。

这些样本说明如果贸然把 near-miss 全部放进 PROBE，会重新引入亏损。

### 7.6 data_health=DEGRADED 降低进攻可信度

最新 `summary.json` 与 `health.json` 均显示 `data_health=DEGRADED`。虽然 warmup 数量 ready，但进攻阶段需要更高的数据可信度。若数据健康不稳，应该谨慎推进高 beta、低 RR 或 observation-only symbol 的晋级。

## 8. 归因分层

| 层级 | 归因 | 证据 | 影响 |
|---|---|---|---|
| 一级 | 主交易频率极低 | 1776 决策仅 1 PROBE | 开仓次数无法提升 |
| 二级 | SCOUT 只观察不交易 | near_misses=14，但 approved executions=1 | 进攻层未转化为仓位 |
| 三级 | 唯一 PROBE 质量偏弱 | LINK score=72，EMA=8/20，CCI=7/14 | 开仓后无顺行，超时亏损 |
| 四级 | 防御门槛仍压制候选 | SIDE_OFFSET=682，SYMBOL_SCOPE=541 | 机会覆盖不足 |
| 五级 | near-miss 质量参差 | 60m 中位 MFE 0.1436%，MAE -0.2768% | 不支持直接放宽 |
| 六级 | 数据健康降级 | data_health=DEGRADED | 放大风险时可信度不足 |

## 9. 建议给 DeepSeek 的评审问题

1. 当前 SCOUT Phase 1 只记录 near-miss，不开微仓；是否应进入 Phase 2 纸交易微仓？
2. SCOUT 频率 `14/36.75h` 是否过低？`near_miss_min_score=82` 是否应降到 `80` 以扩大样本，而不是扩大主交易？
3. LINKUSDT 这种 `score=72`、`EMA=8/20` 的擦边 PROBE 是否应被禁止，避免低质量主交易污染绩效？
4. 是否应为 PROBE 增加 `trend_ema_context >= 10/20` 或 `cci >= 9/14` 的普通门槛？
5. XLMUSDT 是否应从 `observation_only` 晋级为 `SCOUT_ONLY`，只做微仓/幽灵订单，不进入主 PROBE？
6. `SIDE_THRESHOLD_OFFSET_LONG_10.00` 是否过度保守？还是 near-miss 回放已经证明它只错杀少数、多数仍应拦截？
7. RR gap 组 near-miss 回放整体较差，是否应继续保持 RR 门槛，不做统一放宽？
8. 高 beta 的 HYPE/CC 是否仍应保持严格门槛，只允许 SCOUT 观察？
9. data_health=DEGRADED 时，是否应暂停所有 SCOUT 晋级，只记录不放大？
10. 下一阶段目标应设为“主交易继续严格 + SCOUT 微仓 5-10 次/24h”，还是先只扩大 near-miss 样本？

## 10. 一句话结论

本窗口“扩大盈利点”效果不理想，不是下单链路故障，而是进攻架构仍停在 SCOUT 观察阶段：`1776` 条决策只有 `1` 个 PROBE，唯一 LINKUSDT 开仓又是 `score=72` 的低强度擦边信号并超时亏损；near-miss 虽记录了 `14` 个候选，但回放显示多数 MFE 不足、MAE 偏大，尚不能直接升级为主交易。下一步应把 XLM 等候选推进 SCOUT 微仓/晋级评估，同时收紧低质量擦边 PROBE，而不是直接放松主门槛。
