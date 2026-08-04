# AI300 近 7 天 Aggressive Dry-Run 进攻态势归因报告

**提交对象:** DeepSeek 评审  
**分析窗口:** 2026-07-13 11:00:00 至 2026-07-19 当前日志，北京时间。  
**核心问题:** Claude 上轮 Task A-E 是否完全执行到位；开启 aggressive / 扩大盈利点后，为什么 dry-run 仍没有积极结果；下一轮应往什么方向优化，才能在受控风险下增加可开仓、可盈利样本。  
**数据来源:** `logs/2026-07/2026-07-13` 至 `logs/2026-07/2026-07-19` 下 `decisions.jsonl`、`near_misses.jsonl`、`paper_trades.jsonl`、`scout_micro/paper_trades.jsonl`、`summary.json`、`paper_summary.json`。  
**辅助产物:** `reports/structured_offense/2026-07-19-*`。  
**重要口径:** 本报告只分析 dry-run / paper ledger，不构成投资建议；现有回放脚本 CLI 只支持日期级窗口，因此 7-13 11:00 的严格统计以本次直接解析日志为准，回放报告作为辅助证据。

---

## 0. 结论摘要

1. **Claude 五项优化没有完全执行到位。** Task A/B 已落地；Task D 只部分落地；Task C/E 缺失。尤其是 Task E 的 paper A/B 出场账本没有实现，导致现在仍不能回答“同一批主账本入场，legacy 与 trend_capture 谁更好”这个核心问题。
2. **aggressive 模式没有真正转化为主账本进攻。** 严格窗口内 8,099 条决策，`PROBE=1`、`DIRECT=0`、`order_drafts=0`，主账本动作转化率只有 `0.012%`。这不是“开仓多但亏”，而是“几乎没开到主账本”。
3. **主账本近 7 天只有 1 笔新增完整交易，结果亏损。** CCUSDT LONG 以 `COST_BREAKEVEN_TIMEOUT` 平仓，PnL `-5.5717 USDT`，`max_favorable_r_observed=0.295R`，没有接近 TP1，更没有进入趋势捕捉状态。
4. **SCOUT 的 trend_capture 有样本，但整体仍为负。** 11 笔完整 SCOUT，2 胜 9 负，净 PnL `-2.1835 USDT`，profit factor `0.3009`。只有 2 笔曾达到 `>=1.5R`，其余 9 笔连趋势触发门槛都没接近。
5. **当前最大瓶颈不是仓位和杠杆，而是“信号转化层”和“任务分层”仍断裂。** 高分信号 41 条，只有 1 条变成 `PROBE`；主要被 `SYMBOL_WATCH_ONLY`、`SIDE_THRESHOLD_OFFSET_LONG_10.00`、RR gap、黑名单等挡住。
6. **LONG 侧不宜全量放开，但高分 LONG 有小仓验证价值。** 日期级高分拦截回放中，`SIDE_THRESHOLD_OFFSET_LONG_10.00` 高分组 10 条，`avg_blended_final_r=0.8622`、TP2 触达率 60%、stop hit 率 40%；但全量 LONG offset 2,502 条，`avg_blended_final_r=-0.0647`、stop hit 率 65.55%。结论是“精准放开高分 LONG 小仓验证”，不是“降低所有 LONG 门槛”。
7. **Fib exhaustion 专项回放出现正信号，值得拆分而不是硬拦截。** `FIB_EXTENSION_EXHAUSTION_BLOCK` 日期级 718 条，`avg_blended_final_r=0.2211`、TP2 触达率 36.07%、stop hit 率 61.70%。这说明该规则可能混合了“真衰竭”和“顺势延续”，需要分流。

---

## 1. Claude Task A-E 执行状态核对

| Task | 执行状态 | 证据 | 评估 |
|---|---|---|---|
| A: 回放器 bar 顺序与 blended R | 已完成 | `scripts/replay_high_score_intercepts.py` 已有 `bar_order_assumption`、`blended_final_r`、JSON assumptions；测试包含同根 bar stop-first / tp-first 用例 | 满足核心验收 |
| B: SCOUT favorable R 诊断字段 | 已完成 | `src/observability/paper_trading.py` 写入 `max_favorable_r_observed`；`scripts/summarize_scout_trend_capture_diagnostics.py` 可输出阈值分布 | 满足核心验收 |
| C: 净 beta 静态模型 | 未完成 | `src/risk/net_beta_exposure_model.py`、`tests/test_net_beta_exposure_model.py` 不存在；最新 summary 仍为 `net_beta_exposure_model=not_configured` | 阻断仓位/杠杆上调评审 |
| D: 回放窗口扩展与专项扩样 | 部分完成 | 回放器有 `--include-reason`，但没有验收要求的 `--reason-filter` 前缀过滤；本轮只能用多个精确 reason 模拟 RR gap 专项 | 工具可用但不达完整规格 |
| E: Paper A/B 出场账本 | 未完成 | `scripts/run_paper_exit_ab.py`、`tests/test_run_paper_exit_ab.py` 不存在；主账本仍只有单账本 `paper_exit_mode=legacy` | 核心验证缺失 |

**判断:** 五项里只有 A/B 真正完成。C/E 缺失会直接影响下一轮优化质量：C 影响风险扩容前提，E 影响出场架构的因果判断。

---

## 2. 7-13 11:00 至今执行总览

### 2.1 决策动作分布

| 指标 | 数值 |
|---|---:|
| 决策总数 | 8,099 |
| NO_TRADE | 7,219 |
| WATCH | 879 |
| PROBE | 1 |
| DIRECT | 0 |
| 主账本动作转化率 | 0.012% |
| order drafts | 0 |

### 2.2 分数分布

| 分数区间 | 数量 |
|---|---:|
| <70 | 7,241 |
| 70-75 | 422 |
| 75-80 | 282 |
| 80-85 | 113 |
| 85-90 | 34 |
| >=90 | 7 |

score >=85 共 41 条，其中 `NO_TRADE=15`、`WATCH=25`、`PROBE=1`、`DIRECT=0`。高分信号主账本转化率仅 `2.44%`。

### 2.3 高分信号主要拦截原因

| 原因 | 次数 |
|---|---:|
| `SYMBOL_WATCH_ONLY` | 11 |
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 11 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 9 |
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 8 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0` | 7 |
| `SYMBOL_BLACKLISTED` | 3 |
| `HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0` | 3 |

### 2.4 全量主要拦截原因

| 原因 | 次数 |
|---|---:|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 2,474 |
| `SYMBOL_WATCH_ONLY` | 1,137 |
| `SYMBOL_BLACKLISTED` | 1,121 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 705 |
| `PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0` | 84 |
| `PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_6.0` | 64 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0` | 59 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 45 |

### 2.5 平均组件分

| 组件 | 平均分 |
|---|---:|
| `trend_ema_context` | 14.5388 / 20 |
| `flow_cvd_confirmation` | 13.1763 / 18 |
| `fibonacci_location` | 10.0447 / 18 |
| `price_action_structure` | 7.5559 / 22 |
| `cci_momentum_quality` | 3.8586 / 14 |
| `risk_reward_geometry` | 1.2908 / 8 |

**解释:** aggressive 模式下趋势背景和 CVD 并不差，但 CCI 动量、PA 结构、RR 几何仍是短板。系统经常“看见方向”，但不能形成可执行的风报比结构。

---

## 3. 逐日表现

| 日期 | 决策数 | PROBE | DIRECT | score>=85 | near-miss | 主账本开仓/平仓/PnL | SCOUT 开仓/平仓/PnL |
|---|---:|---:|---:|---:|---:|---|---|
| 07-13 11:00后 | 1,092 | 0 | 0 | 2 | 6 | 0 / 0 / 0 | 1 / 1 / +0.2855 |
| 07-14 | 1,248 | 0 | 0 | 9 | 19 | 0 / 0 / 0 | 1 / 1 / -0.1000 |
| 07-15 | 1,248 | 1 | 0 | 7 | 16 | 1 / 1 / -5.5717 | 3 / 3 / -1.7704 |
| 07-16 | 1,248 | 0 | 0 | 13 | 17 | 0 / 0 / 0 | 3 / 2 / -0.5546 |
| 07-17 | 1,248 | 0 | 0 | 1 | 11 | 0 / 0 / 0 | 0 / 1 / +0.6542 |
| 07-18 | 1,248 | 0 | 0 | 6 | 22 | 0 / 0 / 0 | 3 / 3 / -0.6982 |
| 07-19 当前 | 793 | 0 | 0 | 3 | 11 | 0 / 0 / 0 | 0 / 0 / 0 |

**判断:** 07-15 是唯一真正触发主账本的一天，但该笔 CCUSDT LONG 以成本超时亏损结束。除此之外，aggressive 模式主要增加的是 WATCH / near-miss 可见性，不是主账本开仓。

---

## 4. 主账本与 SCOUT 盈亏结构

### 4.1 主账本

| 指标 | 数值 |
|---|---:|
| 开仓 | 1 |
| 完整平仓 | 1 |
| 胜 / 负 | 0 / 1 |
| 净 PnL | -5.5717 USDT |
| exit mode | legacy |
| 平仓原因 | COST_BREAKEVEN_TIMEOUT |
| max favorable R | 0.2953 |

明细：

| 时间 | 标的 | 方向 | 平仓原因 | PnL | max favorable R |
|---|---|---|---|---:|---:|
| 07-16 04:15 | CCUSDT | LONG | COST_BREAKEVEN_TIMEOUT | -5.5717 | 0.2953 |

**归因:** 主账本近 7 天没有足够样本评估盈利能力。唯一入场连 1R 都没到，说明这笔不是“出场没放大”，而是“入场后没有产生可捕捉的 favorable excursion”。

### 4.2 SCOUT

| 指标 | 数值 |
|---|---:|
| 开仓 | 11 |
| 完整平仓 | 11 |
| 胜 / 负 | 2 / 9 |
| 胜率 | 18.18% |
| 净 PnL | -2.1835 USDT |
| gross win | 0.9397 |
| gross loss | 3.1232 |
| profit factor | 0.3009 |
| 平均盈利 | 0.4698 |
| 平均亏损 | 0.3470 |
| 实际盈亏比 | 1.3540 |
| 打平所需盈亏比 | 4.50 |

SCOUT favorable R 诊断：

| 阈值 | 触达笔数 | 比例 |
|---|---:|---:|
| >=1.0R | 2 / 11 | 18.18% |
| >=1.2R | 2 / 11 | 18.18% |
| >=1.5R | 2 / 11 | 18.18% |
| >=2.0R | 1 / 11 | 9.09% |
| >=3.0R | 0 / 11 | 0.00% |

按标的：

| 标的 | 笔数 | net PnL | max favorable R 特征 |
|---|---:|---:|---|
| ADAUSDT | 4 | -1.3471 | 最大 0.8389R，完全未接近 trend trigger |
| XMRUSDT | 5 | -0.7210 | 1 笔达到 1.9669R，其余较弱 |
| XLMUSDT | 1 | +0.6542 | 达到 2.0353R，是唯一较好的 trend_capture 样本 |
| CCUSDT | 1 | -0.7695 | 最大 0.1010R，入场后立即失败 |

**归因:** SCOUT 负反馈不是因为 `trend_trigger_r=1.5` 一定太高。11 笔中 9 笔连 1.0R 都没有到，核心问题更靠前：mission 选择和入场条件没有筛出足够强的趋势启动点。

---

## 5. 回放结果：拦截规则是否误伤趋势

本节使用现有回放器生成的日期级辅助报告，窗口为 2026-07-13 至 2026-07-19，`bar_order_assumption=stop_first`，`horizon_bars=96`。

### 5.1 高分拦截整体

| 组别 | 样本 | avg blended R | TP2 触达率 | stop hit 率 |
|---|---:|---:|---:|---:|
| score>=85 高分拦截 | 40 | +0.1590 | 37.50% | 62.50% |

**解释:** 高分拦截整体不是强正期望，但也不是完全无价值。它说明高分池里有趋势延伸样本，只是混杂严重。

### 5.2 LONG offset

| 组别 | 样本 | avg blended R | TP2 触达率 | stop hit 率 |
|---|---:|---:|---:|---:|
| 全量 `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 2,502 | -0.0647 | 24.22% | 65.55% |
| score>=85 且 primary reason 为 LONG offset | 10 | +0.8622 | 60.00% | 40.00% |

**归因:** LONG offset 全量放开会引入大量噪声；但高分 LONG offset 样本明显更有质量。当前主账本 LONG 几乎不开仓，可能错失了少数高质量上涨趋势。

### 5.3 Fib exhaustion

| 组别 | 样本 | avg blended R | TP2 触达率 | stop hit 率 |
|---|---:|---:|---:|---:|
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 718 | +0.2211 | 36.07% | 61.70% |

**归因:** Fib exhaustion 不是纯保护规则。它确实挡掉了大量会止损的样本，但也挡住一部分顺势延续。当前一刀切硬拦截会降低“扩大盈利点”的样本供给。

### 5.4 RR gap

| 组别 | 样本 | avg blended R | TP2 触达率 | stop hit 率 |
|---|---:|---:|---:|---:|
| RR gap 精确 reason 组合 | 122 | -0.0226 | 22.13% | 64.75% |

**归因:** RR gap 整体放开没有优势。部分子项有正样本，但噪声大于 LONG 高分组和 Fib exhaustion。下一轮不建议优先放松 RR gap 总门槛。

---

## 6. 为什么 aggressive 策略仍没有积极结果

### Findings

aggressive 模式没有把系统变成“能积极开仓的策略”，只是让系统更积极地产生 WATCH / near-miss。主账本仍被 legacy 出场和多层准入门控限制；SCOUT 虽然启用 trend_capture，但 mission 只剩 `NON_RR_HIGH_SCORE`，没有形成分任务验证。

### Evidence

- 8,099 条决策只有 1 条 `PROBE`、0 条 `DIRECT`、0 个 `order_drafts`。
- 最新 `summary.json` 显示 `paper_exit_mode=legacy`、`scout_micro_exit_mode=trend_capture`、`net_beta_exposure_model=not_configured`。
- 主账本唯一交易 `max_favorable_r_observed=0.295R`，没有任何趋势出场验证意义。
- SCOUT 11 笔里只有 2 笔达到 `>=1.5R`，其余 9 笔多数死在初始止损或成本超时。
- 高分信号 41 条中 40 条未进入主账本动作，拦截集中在 symbol policy、LONG offset、RR gap。

### Impact

如果继续只调整 aggressive 档位名称或单个阈值，结果大概率仍是两种极端之一：要么主账本继续不开仓；要么放开太多低质量样本后扩大亏损。当前缺的是“可控中间层”和“A/B 因果验证”，不是更高杠杆。

### Recommendation

下一轮优化应把目标从“全局 aggressive”改为“结构化进攻”：只在回放显示有正边际的子池里增加开仓，并且全部先走小仓 / paper A/B，不直接放大主账本风险。

---

## 7. 下一轮积极策略方向

### 方向一：建立 High-Score LONG Micro-Probe

**假设:** `score>=85` 且被 `SIDE_THRESHOLD_OFFSET_LONG_10.00` 拦截的 LONG 样本，比全量 LONG offset 样本质量显著更高。  
**证据:** 高分 LONG offset 10 条 `avg_blended_final_r=0.8622`、TP2 触达率 60%；全量 LONG offset 2,502 条 `avg_blended_final_r=-0.0647`。  
**建议:** 不下调全局 LONG offset。新增一个只走 50-100 USDT paper / micro 的 `HIGH_SCORE_LONG_OFFSET_PROBE` mission。

准入建议：

```text

side = LONG
score >= 85
primary_reason contains SIDE_THRESHOLD_OFFSET_LONG_10.00
PA >= 18
Fib >= 15
Flow CVD >= 14
Risk reward geometry >= 2
high beta symbol: notional 乘以 0.5

```

验收标准：连续 20 笔后，profit factor >= 1.0 且 avg blended R > 0；否则暂停。

### 方向二：拆分 Fib exhaustion 为“硬拦截”和“顺势延续降级”

**假设:** `FIB_EXTENSION_EXHAUSTION_BLOCK` 中混有趋势延续机会。  
**证据:** 718 条日期级回放 `avg_blended_final_r=0.2211`，TP2 触达率 36.07%。  
**建议:** 不再一律 hard block。拆成两类：

```text

逆势 / 弱趋势 / CVD 不确认: 继续 hard block
顺势 / EMA 强排列 / CVD 确认 / PA >= 18: 降级为 SCOUT micro，不进主账本

```

验收标准：Fib continuation micro 样本 30 笔，按 symbol 和 side 分层看 PF、MFE/MAE、stop hit 率。

### 方向三：停止泛化 NON_RR_HIGH_SCORE，改成子任务白名单

**假设:** 当前 `NON_RR_HIGH_SCORE` 太宽，导致 SCOUT 仍在消耗负期望样本。  
**证据:** 近 7 天 SCOUT 11 笔全部为 `NON_RR_HIGH_SCORE`，PF 0.3009；ADA 4 笔最大 favorable R 只有 0.8389R。  
**建议:** `NON_RR_HIGH_SCORE` 不应作为泛化 mission 继续开仓，只保留三个明确子任务：

```text

HIGH_SCORE_LONG_OFFSET_PROBE
FIB_CONTINUATION_SCOUT
WATCH_ONLY_SYMBOL_PROMOTION_TEST

```

每个 mission 必须有独立样本数、PF、avg favorable R、停机条件。没有 mission 标签的高分不自动开仓。

### 方向四：补齐 Paper Exit A/B，主账本不要直接切 trend_capture

**假设:** 当前无法证明 trend_capture 对主账本有效，因为主账本仍是 legacy，且近 7 天只有 1 笔样本。  
**建议:** 优先实现 Task E：对同一批入场并行维护 legacy / trend_capture 两套 paper 状态机。不要用 SCOUT 的负样本直接否定 trend_capture，因为 SCOUT 的入场池和主账本不同。

验收标准：

```text

同一入场流 >= 20 笔完整交易
trend_capture avg payoff ratio > legacy
trend_capture max drawdown 不显著劣化
至少出现 3 笔曾达到 >=1.5R 的样本

```

### 方向五：补齐 net beta 后再谈仓位

**假设:** 当前组合级低敞口来自低开仓率，不代表高仓位安全。  
**证据:** 最新 summary 仍为 `net_beta_exposure_model=not_configured`，open positions 多数时候为 0。  
**建议:** 完成 Task C，但只作为观测模型接入 summary，不直接进入 live hard block。等模型输出稳定后，再评审是否进入 `hard_block_reason`。

---

## 8. DeepSeek 评审问题

1. 对 `HIGH_SCORE_LONG_OFFSET_PROBE`，是否同意只放开 `score>=85` 的 LONG offset 小仓样本，而不是降低全局 LONG threshold？
2. 对 `FIB_EXTENSION_EXHAUSTION_BLOCK`，是否同意拆为“逆势硬拦截”和“顺势延续 SCOUT 降级”，而不是继续一刀切？
3. `NON_RR_HIGH_SCORE` 近 7 天 11 笔 PF 0.3009，是否应暂停泛化开仓，只保留可解释子任务？
4. 在 Task E 未完成前，是否应禁止把主账本直接切到 `trend_capture`，改为先做 paper A/B？
5. 在 Task C 未完成前，是否应禁止任何仓位/杠杆上调，即使 aggressive 档位继续运行？
6. RR gap 专项整体 `avg_blended_final_r=-0.0226`，是否应维持当前 RR 门，而只对少数高分子池做 micro 验证？

---

## 9. 最终归因

本轮 aggressive dry-run 不理想，不是因为系统完全没有趋势机会，而是因为进攻体系仍未闭环：

1. **执行转化不足:** 8,099 条决策只有 1 条 `PROBE`，0 条 `DIRECT`，0 个订单草稿。
2. **主账本验证缺失:** 近 7 天只有 1 笔主账本交易且亏损，无法产生趋势捕捉样本。
3. **SCOUT mission 过宽:** 11 笔全是 `NON_RR_HIGH_SCORE`，没有按 LONG offset / Fib continuation / watch-only promotion 分任务验证。
4. **出场因果无法判断:** 主账本仍是 legacy，Task E 缺失，无法对比 legacy 与 trend_capture。
5. **风险扩容前提缺失:** Task C 缺失，净 beta 仍未配置，不能合理提高仓位或杠杆。

下一轮应优先做三件事：

```text

1. 实现 Task E: paper legacy/trend_capture A/B 账本
2. 实现 Task C: net beta 静态观测模型
3. 新增两个 micro mission:
   - HIGH_SCORE_LONG_OFFSET_PROBE
   - FIB_CONTINUATION_SCOUT

```

策略方向不是“更激进地放开所有门”，而是把 aggressive 拆成可验证的、带日落条款的小仓进攻子池。只有这些子池在 20-30 笔样本里证明 PF 和 avg blended R 为正，才有资格进入主账本。
