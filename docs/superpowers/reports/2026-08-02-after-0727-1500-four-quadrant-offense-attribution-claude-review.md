# AI300 07-27 15:00 后四象限进攻失效归因报告

**提交对象:** Claude 复核  
**分析窗口:** 2026-07-27 15:00 至 2026-08-02 20:30 左右，北京时间。  
**运行模式:** dry-run / paper ledger / SCOUT micro / paper A-B mirror。  
**数据来源:** `logs/2026-07/2026-07-27` 至 `logs/2026-08/2026-08-02` 下的 `decisions.jsonl`、`near_misses.jsonl`、`scout_decisions.jsonl`、`paper_trades.jsonl`、`scout_micro/paper_trades.jsonl`、`paper_ab/*/paper_trades.jsonl`、`paper_ab/reports/*`、`summary.json`、`paper_summary.json`。  
**重要口径:** 本报告中的“拐点”和 near-miss 后验收益均为事后复盘，不能直接作为 live 可见信号。任何进攻策略修改仍必须先在 dry-run / paper / SCOUT 层验证，禁止引入未来函数、同根 K 线乐观成交或实盘配置越级变更。

---

## 0. 结论摘要

1. **上次“开启进攻”的代码并非完全没运行，但主账本进攻没有真正打开。** 窗口内 7,787 条决策，只有 1 笔主账本 `PROBE`，没有任何 `q1_trend_launch` 主账本转化记录；SCOUT 有 25 笔开仓，A/B mirror 有 58 笔实验样本。
2. **Q1 有机会，但 `q1_trend_launch` 规则过窄。** Q1 共 803 条，其中 `score>=80` 有 117 条、`score>=85` 有 25 条；near-miss 中有 33 条 Q1 样本除“确认标签”外已满足 trend-launch 门槛，但被 `Q2_PENDING_MOMENTUM_CONFIRMED` / `Q3_TO_Q1_CONFIRMED` 标签要求挡住。
3. **Q2 pending 在本窗口几乎是死规则。** Q2 共 1,003 条，最高分仅 79.35，`score>=80` 和 `score>=85` 均为 0；而配置要求 `scout_micro_q2_pending_min_score=85`，导致 Q2 pending 无法生成有效候选。
4. **Q3 有动能拐点线索，但确认漏斗太窄。** Q3 near-miss 有 24 条，其中 10 条满足 `score>=85` 且 CVD 达标；最终只有 1 条进入 `Q3_TO_Q1_CONFIRMATION`。3 根 15m K 线的确认窗口偏短，且单 symbol pending 容易被后续候选覆盖。
5. **拐点识别的主要失败不是“没有波动”，而是方向与位置错配。** 事后识别 586 个局部拐点，系统当时方向与后续 8 根 15m 主要运动方向匹配 202 次、错误 384 次。高分拐点更严重：`score>=80` 的 19 个拐点方向全部错。
6. **SCOUT 不是没开，而是开了后质量不足。** 窗口内 SCOUT 25 笔开仓，事件口径 PnL `-1.9426`，PF `0.504`。其中 `Q1_RR_GAP_SCOUT` 明显拖累，`REVERSAL_PIVOT_SCOUT` 与 `Q3_TO_Q1_CONFIRMATION` 略正但样本太少。
7. **A/B 自动报告正常输出，但没有资格自动切换。** batch 2/3/4 的 trend_capture 均略优于 legacy，但两组累计 PF 仍明显小于 1，且 payoff 优势低于 `1.3x` 自动切换阈值，所以 `paper_exit_mode` 保持 `legacy` 是合理结果。
8. **当前最需要的不是全局放宽，而是把进攻拆成三条窄通道:** Q1 直接强结构小仓试验、Q3 动能延续试验、Q4/极值反转试验。每条通道独立账本、独立日落条款、独立熔断，不能混在一个“aggressive”开关里。

---

## 1. 本轮策略是否真正生效

### 1.1 已生效的部分

从日志证据看，以下模块已经进入运行链路：

| 模块 | 日志证据 | 结论 |
|---|---:|---|
| 四象限标注 | 7,787 条决策均有 Q1/Q2/Q3/Q4 | 已生效 |
| SCOUT audit | 87 条 `scout_decisions.jsonl` | 已生效 |
| SCOUT micro | 25 笔开仓 | 已生效 |
| A/B mirror | 58 笔 mirror 样本 | 已生效 |
| A/B auto report | batch 2/3/4 输出 | 已生效 |
| experiment id | SCOUT/A-B open 事件为 `four_quadrant_navigation_v1` | 已生效 |
| Q3/Q4 position state machine | A/B 中有 `Q3_DEFENSIVE_REDUCE`、`Q4_DEFENSIVE_EXIT` | 已生效 |

### 1.2 未达到目标的部分

| 目标 | 实际 | 判断 |
|---|---:|---|
| 主账本开启进攻样本 | 1 笔 `PROBE`，且非 `q1_trend_launch` | 未达标 |
| Q1 trend-launch 主账本转化 | 0 条 `DRY_RUN_Q1_TREND_LAUNCH` / `q1_trend_launch` 决策 | 未达标 |
| Q2 pending 捕捉“结构好、动能回归” | Q2 无 `score>=85` | 规则在本窗口不可触发 |
| Q3 to Q1 确认 | 10 个候选仅 1 个确认 | 转化率过低 |
| SCOUT 盈利验证 | PF `0.504` | 未通过 |
| 自动切换 trend_capture | 未触发 | 合理，因为 A/B 条件未满足 |

---

## 2. 总体执行表现

### 2.1 决策分布

| 项目 | 数值 |
|---|---:|
| 决策总数 | 7,787 |
| `NO_TRADE` | 6,972 |
| `WATCH` | 814 |
| `PROBE` | 1 |
| 主账本新开仓 | 1 |
| SCOUT 开仓 | 25 |
| A/B mirror 开仓 | 58 |

按日期：

| 日期 | 决策数 | NO_TRADE | WATCH | PROBE | Q1 | Q2 | Q3 | Q4 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-07-27 15:00 后 | 884 | 763 | 121 | 0 | 83 | 134 | 151 | 516 |
| 2026-07-28 | 1,248 | 1,163 | 85 | 0 | 122 | 161 | 228 | 737 |
| 2026-07-29 | 1,248 | 1,096 | 151 | 1 | 133 | 164 | 236 | 715 |
| 2026-07-30 | 1,248 | 1,136 | 112 | 0 | 127 | 158 | 256 | 707 |
| 2026-07-31 | 1,248 | 1,081 | 167 | 0 | 126 | 144 | 271 | 707 |
| 2026-08-01 | 1,248 | 1,133 | 115 | 0 | 121 | 153 | 271 | 703 |
| 2026-08-02 截至 20:30 | 663 | 600 | 63 | 0 | 91 | 89 | 158 | 325 |

### 2.2 主账本、SCOUT、A/B 结果

| 账本 | 开仓数 | 平/减仓事件 | 窗口事件 PnL | PF | 主要结论 |
|---|---:|---:|---:|---:|---|
| 主账本 | 1 | 2 | `+6.5288` | 极高但样本无效 | 只有 1 笔 CCUSDT，不能证明策略有效 |
| SCOUT micro | 25 | 35 | `-1.9426` | `0.504` | 侦察层仍为负期望 |
| A/B legacy | 59 | 109 | `+6.8426` | `2.233` | 含主账本 CCUSDT 贡献，mirror 本身仅小幅正 |
| A/B trend_capture | 59 | 102 | `+7.3879` | `2.332` | 略优于 legacy，但不够触发自动切换 |

剔除主账本那笔 CCUSDT 后，A/B mirror 事件口径为：

| A/B mirror | 事件 PnL | 结论 |
|---|---:|---|
| legacy mirror | `+0.3139` | 基本打平，依赖少数样本 |
| trend_capture mirror | `+0.8592` | 略优，但优势仍弱 |

---

## 3. 四象限得分结构

当前象限可解释为：

- **Q1:** 趋势/结构轴通过，资金/动能轴通过。
- **Q2:** 趋势/结构轴通过，资金/动能轴未通过。
- **Q3:** 趋势/结构轴未通过，资金/动能轴通过。
- **Q4:** 两条轴均未通过。

配置阈值见 `configs/entry_chain.dry_run_fib_pa_v1.json`：

- `quadrant_trend_ema_min=15`
- `quadrant_price_action_min=10`
- `quadrant_flow_cvd_min=14`
- `quadrant_cci_min=7`

### 3.1 象限数量与总分

| 象限 | 样本数 | 平均分 | 中位数 | P90 | 最大分 | `>=80` | `>=85` |
|---|---:|---:|---:|---:|---:|---:|---:|
| Q1 | 803 | 71.87 | 72.10 | 81.10 | 92.09 | 117 | 25 |
| Q2 | 1,003 | 59.14 | 59.39 | 69.65 | 79.35 | 0 | 0 |
| Q3 | 1,571 | 59.81 | 59.00 | 72.00 | 90.30 | 36 | 10 |
| Q4 | 4,410 | 41.36 | 41.20 | 55.48 | 76.11 | 0 | 0 |

### 3.2 各象限组件均值

| 象限 | trend EMA | PA | CVD | CCI | Fib | RR |
|---|---:|---:|---:|---:|---:|---:|
| Q1 | 17.10 | 16.79 | 18.00 | 10.02 | 8.48 | 1.47 |
| Q2 | 17.06 | 16.40 | 13.13 | 2.52 | 8.45 | 1.58 |
| Q3 | 14.65 | 5.70 | 18.00 | 9.65 | 10.69 | 1.12 |
| Q4 | 13.47 | 3.91 | 10.65 | 1.07 | 11.10 | 1.16 |

关键解释：

- Q1 的 CVD/CCI/PA 足够强，但 Fib 与 RR 均值偏低，说明多数 Q1 是“动能强”，不是“位置好”。
- Q2 的趋势/结构并不差，但 CCI 明显缺失；由于总分最高只有 79.35，当前 `min_score=85` 让 Q2 pending 基本失效。
- Q3 的资金/动能强，但 PA 结构很低；适合做“等待结构确认”或“动能延续小仓”，不适合直接主账本。
- Q4 数量最多，且事后拐点最多；这说明很多行情反弹/回落起点发生在系统最低分区，现有模型天然不擅长早期反转。

---

## 4. 为什么没有抓住机会

### 4.1 Q1 trend-launch 过窄，导致主账本 0 转化

代码层面，`build_q1_green_channel_decision()` 已经被改造成 `q1_trend_launch` 兼容 wrapper；真正准入在 `_q1_trend_launch_eligible()`。它要求：

- 当前象限必须是 Q1；
- `score>=82`;
- `PA>=18`;
- `Fib>=15`;
- `CVD>=16`;
- `RR>=0.5`;
- 必须带有 `Q2_PENDING_MOMENTUM_CONFIRMED` 或 `Q3_TO_Q1_CONFIRMED` 标签。

日志结果：

| 项目 | 数值 |
|---|---:|
| Q1 near-miss | 63 |
| 缺确认标签 | 62 |
| RR `<0.5` | 19 |
| Fib `<15` | 9 |
| 分数 `<82` | 3 |
| 除确认标签外满足 trend-launch | 33 |
| 实际 `q1_trend_launch` 主账本转化 | 0 |

结论：**当前主账本进攻通道不是“Q1 强信号开仓”，而是“必须先经历 Q2/Q3 pending 后再回 Q1 才开仓”。这个逻辑过于保守，导致 Q1 直接强结构样本完全没有主账本入口。**

典型被挡样本：

| 时间 | 标的 | 方向 | 象限 | 分数 | RR | 主因 |
|---|---|---|---|---:|---:|---|
| 07-27 21:30 | DOGEUSDT | LONG | Q1 | 88.70 | 2.0 | `SIDE_THRESHOLD_OFFSET_LONG_10.00` |
| 07-29 07:30 | ADAUSDT | LONG | Q1 | 92.09 | 3.5 | `SYMBOL_WATCH_ONLY` |
| 07-30 04:45 | ADAUSDT | SHORT | Q1 | 89.69 | 6.5 | `SYMBOL_WATCH_ONLY` |
| 07-31 17:15 | HYPEUSDT | SHORT | Q1 | 90.69 | 3.5 | RR gap |
| 08-02 13:15 | BCHUSDT | LONG | Q1 | 85.19 | 2.0 | `SIDE_THRESHOLD_OFFSET_LONG_10.00` |

这些不应直接放入实盘，但在 dry-run 中应进入一个独立的 `Q1_DIRECT_STRUCTURED_PROBE` 实验账本，而不是全部等待 pending 标签。

### 4.2 Q2 pending 在当前阈值下不可触发

配置为：

- `scout_micro_q2_pending_enabled=true`
- `scout_micro_q2_pending_min_score=85`
- `scout_micro_q2_pending_min_pa_score=18`
- `scout_micro_q2_pending_confirm_bars=6`
- `scout_micro_q2_pending_confirm_cci_score=9`

但日志中：

- Q2 总数 1,003；
- Q2 最大分 79.35；
- Q2 `score>=80` 为 0；
- Q2 `score>=85` 为 0。

结论：**Q2 pending 不是策略失败，而是门槛与评分分布矛盾。** 由于 Q2 的定义本身就是动能轴不通过，要求它 `score>=85` 不现实。

### 4.3 Q3 to Q1 有候选，但确认窗口与状态机太窄

Q3 near-miss 有 24 条，其中满足 `score>=85` 且 CVD 达标的候选有 10 条。实际只有 1 条转为 `Q3_TO_Q1_CONFIRMATION`。

典型 Q3 候选：

| 时间 | 标的 | 方向 | 分数 | PA | 主因 |
|---|---|---|---:|---:|---|
| 07-27 22:15 | BNBUSDT | SHORT | 87.30 | 21 | RR gap |
| 07-28 23:30 | ADAUSDT | LONG | 85.80 | 21 | `SYMBOL_WATCH_ONLY` |
| 07-31 09:45 | LINKUSDT | SHORT | 87.30 | 21 | RR gap |
| 07-31 15:45 | HYPEUSDT | SHORT | 88.80 | 21 | RR gap |
| 08-02 16:30 | TRXUSDT | SHORT | 87.30 | 21 | RR gap |

问题不在于 Q3 没信号，而在于：

- 3 根 15m K 线确认窗口可能太短；
- 每个 symbol 只保留一个 pending，后续候选可能覆盖前一个；
- 确认要求“回到 Q1”，但不少动能延续机会可能保持在 Q3 或直接进入 Q4 防御区；
- Q3 的低 PA 是象限定性的原因，但日志中 high-score Q3 的 PA 实际常为 21，说明当前 Q3 判定可能受 trend EMA 轴拖累，而不是结构本身差。

### 4.4 主账本仍被老门控主导

全局决策原因中，主要拦截为：

| 拦截原因 | 次数 |
|---|---:|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 2,333 |
| `SYMBOL_BLACKLISTED` | 1,124 |
| `SYMBOL_WATCH_ONLY` | 1,021 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 810 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_*` | 85+ |
| `PROBE_BELOW_FIBONACCI_LOCATION_*` | 130+ |

高分样本也被这些规则锁住：

| 象限 | `score>=80` | 主要去向 |
|---|---:|---|
| Q1 | 117 | 66 WATCH / 50 NO_TRADE / 1 PROBE |
| Q2 | 0 | 无 |
| Q3 | 36 | 26 WATCH / 10 NO_TRADE |
| Q4 | 0 | 无 |

结论：四象限标签虽然已进入日志，但主账本开仓链路仍以 symbol policy、LONG offset、RR/Fib 门槛为主。**四象限目前更多是“解释字段”，不是“主账本导航器”。**

### 4.5 Symbol policy 拦截了部分最有信息量的样本

窗口 near-miss 主因：

| 主因 | 次数 |
|---|---:|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 22 |
| `SYMBOL_WATCH_ONLY` | 21 |
| RR gap 类 | 31 |
| `SYMBOL_BLACKLISTED` | 12 |
| `HIGH_BETA_PROBE_ONLY` | 1 |

部分后验机会集中在 watch-only / blacklist / offset：

| 时间 | 标的 | 方向 | 象限 | 分数 | 后续 8 根 favorable move | 主因 |
|---|---|---|---|---:|---:|---|
| 07-30 20:45 | BCHUSDT | LONG | Q1 | 82.70 | 3.70% | LONG offset |
| 07-27 22:00 | HYPEUSDT | SHORT | Q3 | 84.29 | 3.23% | RR gap |
| 07-27 21:00 | XLMUSDT | SHORT | Q1 | 82.70 | 2.83% | RR gap |
| 07-29 14:30 | CCUSDT | LONG | Q1 | 86.70 | 1.94% | LONG offset |
| 07-29 07:30 | ADAUSDT | LONG | Q1 | 92.09 | 0.93% | WATCH_ONLY |
| 08-01 08:00 | XMRUSDT | LONG | Q1 | 86.59 | 1.11% | WATCH_ONLY |

注意：这些是后验 favorable move，不等于真实可获利。它们说明的是：**当前最可能的进攻突破口不在全市场放宽，而在被 policy 拦截的少数高分结构化样本。**

---

## 5. 行情拐点复盘

### 5.1 拐点定义

本报告使用一个保守的事后定义：

- 局部低点：当前 close 低于前 2 根，且不高于后 2 根，随后 8 根 15m 内最大反弹 `>=0.8%`；
- 局部高点：当前 close 高于前 2 根，且不低于后 2 根，随后 8 根 15m 内最大回落 `>=0.8%`；
- 局部低点后的正确方向为 LONG，局部高点后的正确方向为 SHORT。

该定义只用于复盘，不能用于 live。

### 5.2 拐点分布与方向匹配

| 项目 | 数值 |
|---|---:|
| 事后识别拐点 | 586 |
| 方向匹配 | 202 |
| 方向错误 | 384 |
| 低点反弹 | 292 |
| 高点回落 | 294 |

按象限：

| 象限 | 拐点数 | 方向匹配 | 方向错误 | 主要动作 |
|---|---:|---:|---:|---|
| Q1 | 87 | 2 | 85 | 52 NO_TRADE / 35 WATCH |
| Q2 | 91 | 4 | 87 | 85 NO_TRADE / 6 WATCH |
| Q3 | 107 | 13 | 94 | 90 NO_TRADE / 17 WATCH |
| Q4 | 301 | 183 | 118 | 297 NO_TRADE / 4 WATCH |

高分拐点：

| 条件 | 拐点数 | 方向匹配 | 方向错误 |
|---|---:|---:|---:|
| `score>=80` | 19 | 0 | 19 |

关键解释：

- Q1/Q3 的高分经常出现在局部高点或局部低点之后的错误方向上，追动能容易追到末端。
- Q4 捕获了最多拐点，且方向匹配率最高，但 Q4 的总分和结构分低，当前系统不会交易它。
- 这说明“盈利进攻”不能只依赖 Q1；必须把 Q4/极值反转作为独立的低仓位研究对象，但要用极小仓位和严格确认，不能直接主账本化。

### 5.3 典型错失 / 错向拐点

| 时间 | 标的 | 事后走势 | 象限 | 系统方向 | 分数 | 拦截原因 | 归因 |
|---|---|---|---|---|---:|---|---|
| 07-27 21:30 | DOGEUSDT | 高点后回落 3.04% | Q1 | LONG | 88.70 | LONG offset / RR gap | Q1 高分追多，实际为顶部 |
| 07-30 20:30 | BCHUSDT | 低点后反弹 3.95% | Q4 | LONG | 47.30 | LONG offset / RR=0 | 低分区出现反转，主系统不交易 |
| 07-31 15:45 | BCHUSDT | 高点后回落 3.81% | Q4 | LONG | 37.10 | LONG offset | 方向错误，反转早期无识别 |
| 08-02 08:30 | ADAUSDT | 低点后反弹 3.64% | Q4 | LONG | 39.60 | WATCH_ONLY | 标的政策和低分区双重阻断 |
| 07-27 22:00 | HYPEUSDT | SHORT favorable 3.23% | Q3 | SHORT | 84.29 | RR gap | 有效 Q3 动能延续，但主账本无通道 |

---

## 6. 各实验通道表现

### 6.1 SCOUT mission

| Mission | 开仓 | 事件 PnL | 主要退出 | 结论 |
|---|---:|---:|---|---|
| `Q1_RR_GAP_SCOUT` | 14 | `-1.3456` | 7 次初始止损 | 明确拖累，应暂停或重构 |
| `REVERSAL_PIVOT_SCOUT` | 8 | `+0.0888` | TP1/BE/初始止损混合 | 略正，但样本太少 |
| `Q3_TO_Q1_CONFIRMATION` | 1 | `+0.1936` | TP1 + BE | 值得扩样，但转化率太低 |
| `WATCH_ONLY_SYMBOL_PROMOTION_TEST` | 1 | `-0.7720` | 初始止损 | 单样本，不足以晋级 |
| `SCOUT_ONLY_HIGH_SCORE` | 1 | `-0.1075` | 成本保本超时 | 单样本 |

结论：**当前 SCOUT 的负期望主要来自 Q1 RR gap，而不是反转或 Q3 确认。** “只要 Q1 且 RR gap 就侦察”的规则仍然太粗。

### 6.2 A/B 出场测试

自动报告：

| Batch | closed trades | legacy PF | trend PF | legacy payoff | trend payoff | 是否可切换 |
|---|---:|---:|---:|---:|---:|---|
| 2 | 40 | 0.0641 | 0.0743 | 0.2565 | 0.2970 | 否 |
| 3 | 60 | 0.1766 | 0.2072 | 0.4121 | 0.4835 | 否 |
| 4 | 80 | 0.3556 | 0.3815 | 0.8296 | 0.8901 | 否 |

配置要求：

- `paper_ab_auto_switch_min_reports=2`
- `paper_ab_auto_switch_min_closed_trades=40`
- `paper_ab_auto_switch_payoff_mult=1.3`

trend_capture 相对 legacy 有小幅优势，但没有达到 1.3 倍 payoff，且两组 PF 都低于 1。**不自动切换是正确的。**

---

## 7. 根因判断

### 根因 1: 四象限仍是地图，不是主账本导航器

四象限已标注、SCOUT/A-B 已运行，但主账本的实际开仓仍由原有门控主导。`q1_trend_launch` 因确认标签要求过窄，没有成为“Q1 强信号小仓入口”。

### 根因 2: Q2/Q3 pending 阈值与真实分布不匹配

Q2 没有高分样本，却要求 `score>=85`。Q3 有候选，但确认窗口短、状态模型窄，导致转化不足。

### 根因 3: 当前进攻实验混合了“趋势延续”和“反转”

`Q1_RR_GAP_SCOUT` 做的是顺势/延续，但其中很多 Q1 高分位于局部高点，导致追末端。`REVERSAL_PIVOT_SCOUT` 又会反向开仓，但触发条件仍偏粗。两类信号的胜负逻辑不同，不应放在同一成功标准下评价。

### 根因 4: 位置质量仍被 RR/Fib 否决，但没有替代的“动态 R”模型

很多机会被 `OPPOSITION_STRUCTURE_TOO_CLOSE` 归零 RR。静态 RR 过近确实会过滤噪音，但在强趋势中也会错杀突破延续。当前没有用 MFE/MAE、ATR 扩张、突破后回踩等动态证据来替代静态 RR。

### 根因 5: watch-only / blacklist / observation-only 包含了强波动样本

ADA、XMR、ZEC、XRP、XLM 等提供了不少高分或拐点信息，但它们要么只进 mirror，要么被 SCOUT symbol 范围挡住，要么不允许主账本。策略研究上应该保留这些样本，但不能直接进入主账本。

---

## 8. 如何开启“盈利的进攻”：建议给 Claude 评审的下一步

### 8.1 立即停止或收紧 `Q1_RR_GAP_SCOUT`

证据：

- 14 笔开仓；
- PnL `-1.3456`；
- 7 次初始止损；
- 当前是 SCOUT 负期望主要来源。

建议：

- 暂停纯 `Q1_RR_GAP_SCOUT`；
- 重构为 `Q1_PULLBACK_RR_GAP_SCOUT`，必须满足至少一项位置确认：
  - 前 2-4 根出现回踩而非连续追涨/追跌；
  - 当前 close 不在近 8 根极值的最外 20%；
  - ATR 扩张但 wick risk 不激活；
  - 不能在事后拐点统计中高频错向的形态上触发。

### 8.2 新增 `Q1_DIRECT_STRUCTURED_PROBE`，但只在 dry-run 主账本小仓

目的：解决“Q1 有 33 条强结构样本却全部缺确认标签”的问题。

建议准入：

- `quadrant=Q1`;
- `score>=85`;
- `PA>=18`;
- `Fib>=15`;
- `CVD>=16`;
- `RR>=2.0`，或 `RR>=0.5` 且过去 3 根不是同向连续拉升/杀跌；
- 非 blacklist；
- watch-only 只进 SCOUT/mirror，不进主账本；
- 仓位为普通 PROBE 的 25%-50%；
- `entry_channel=q1_direct_structured_probe`;
- 独立日落：20 笔后 PF < 0.8 关闭，PF > 1.1 才考虑扩大。

理由：

- 本窗口有 33 条样本除确认标签外达标；
- A/B mirror 在当前窗口略正；
- 但高分拐点方向错误严重，所以必须加入“非极值追单”约束。

### 8.3 重设 Q2 pending 门槛

当前 `score>=85` 与 Q2 分布矛盾。建议改为：

- `Q2_PENDING_SETUP`: `score>=70`，`PA>=18`，`trend_ema>=16`，`CCI<7`;
- 不开仓，只记录 pending；
- 确认时要求进入 Q1，且 `CCI>=9`，`CVD>=16`，`RR>=1.0`;
- pending 窗口从 6 根扩到 8-12 根；
- pending 状态按 `symbol+side+setup_type` 存多条，避免覆盖。

验收：

- 一周内至少产生 10 个 Q2 pending；
- 至少 3 个确认，否则继续调低 pending 记录阈值但不降低开仓阈值。

### 8.4 扩展 Q3 通道：区分“Q3 延续”与“Q3 反转前兆”

Q3 候选有 10 个，但只确认 1 个。建议拆分：

**Q3_MOMENTUM_CONTINUATION_SCOUT**

- `quadrant=Q3`;
- `score>=85`;
- `PA>=18`;
- `CVD>=16`;
- `CCI>=10`;
- 不要求立刻回 Q1；
- 只做 SCOUT，25-50 USDT；
- 若 2 根内进入 Q4，立即退出；
- 样本 20 笔后评估。

**Q3_TO_Q1_CONFIRMATION**

- 保留原有确认逻辑；
- 窗口从 3 根扩到 6-8 根；
- pending 多实例化；
- 确认后可进入 SCOUT 或极小主账本，而不是只依赖 near-miss 继续出现。

### 8.5 建立 Q4 反转研究通道，但只允许超小 SCOUT

证据：

- 586 个事后拐点中，Q4 占 301；
- Q4 方向匹配 183、错误 118，是四象限中唯一方向匹配多于错误的区间；
- 但 Q4 总分低，不适合直接主账本。

建议新增：

**Q4_EXTREME_REVERSAL_SCOUT**

- 仅 25 USDT；
- 必须满足极值/衰竭条件：
  - Fib extension 或 opposition too close；
  - CCI 极值回落/回升；
  - 当前 K 线出现长下影/长上影或反包；
  - CVD 不再继续恶化；
- 不允许连续开仓；
- 单 mission 3 连初始止损暂停 24 小时；
- 30 笔后 PF > 0.9 才考虑扩大。

这条通道是为了研究反转，不是为了立刻赚钱。

### 8.6 Symbol policy 做“影子晋级”，不直接放开

建议：

- ADA、XMR 保持 watch-only，但允许 `WATCH_ONLY_SYMBOL_PROMOTION_TEST` 样本量提升到每标的 10 笔；
- ZEC/XRP 继续 blacklist，不进 SCOUT 实仓，但进入 mirror/回放样本池；
- XLM 当前 `scout_micro_rr_gap_block_symbols` 会挡住 RR gap，可保留，但要单独记录“如果未阻断”的 mirror 表现。

晋级条件：

- 单标的近 20 笔 mirror/SCOUT PF > 1.0；
- 最大回撤不过预算；
- 初始止损率 < 40%；
- favorable move 中位数 > 0.8%。

### 8.7 A/B 自动切换规则保持，不要强切

trend_capture 在本窗口略好，但不够强：

- batch 4 trend PF `0.3815`，legacy PF `0.3556`；
- trend payoff `0.8901`，legacy payoff `0.8296`；
- 两者都未达正期望。

建议：

- 不要因为“trend_capture 稍好”就切主账本；
- 先改善入场；
- 自动切换阈值保留 `payoff_mult>=1.3`，并新增硬条件：trend PF 必须 `>1.0` 或最近 40 笔 realized PnL 为正。

---

## 9. 建议的下一轮工程验收项

### Task A: Q1 直接强结构 dry-run 主账本通道

- 新增 `dry_run_q1_direct_structured_probe_enabled`;
- 不依赖 Q2/Q3 confirmed tag；
- 只允许 dry-run / paper；
- 写入 `entry_channel=q1_direct_structured_probe`;
- 独立统计 trade_count、PF、MFE/MAE。

验收：一周内产生 10-20 笔样本；若 PF < 0.8 自动关闭。

### Task B: Q2 pending 降低记录阈值，开仓阈值不降

- pending 记录阈值改为 score 70-75；
- confirmation 仍要求 Q1、CCI、CVD、RR；
- pending 支持多实例，不再单 symbol 覆盖。

验收：Q2 pending 数量从 0 提升到可审计样本；确认率和结果单独报告。

### Task C: Q3 momentum continuation SCOUT

- 新增 mission；
- 不要求回 Q1；
- 只做微仓；
- Q4 两根或亏损立即退。

验收：20 笔后对比 Q3_TO_Q1 与 Q3_CONTINUATION 的 PF、初始止损率、MFE。

### Task D: Q4 extreme reversal SCOUT

- 新增极小仓反转任务；
- 严格限制 25 USDT；
- 只在极值衰竭与 K 线反转同时出现时触发。

验收：30 笔后若 PF < 0.7 永久关闭；若 PF > 0.9 才继续。

### Task E: 进攻报告增加“漏斗诊断”

每日报告必须输出：

- Q1 直接达标但缺 confirmed tag 的数量；
- Q2 pending 候选、确认、过期数量；
- Q3 pending 候选、确认、过期数量；
- SCOUT mission 级 PF、初始止损率、连续止损熔断状态；
- A/B 切换未触发的具体原因；
- top 20 near-miss 的后验 MFE/MAE。

---

## 10. 最终判断

2026-07-27 15:00 之后，进攻策略“部分生效但没有形成盈利进攻”：

- SCOUT 和 A/B mirror 已经在采样；
- 主账本 Q1 trend-launch 没有转化；
- Q2 pending 因阈值不可达而失效；
- Q3 确认太窄；
- Q1 RR gap SCOUT 是当前主要负贡献；
- trend_capture 不是根因，入场质量才是根因；
- 最大的信息增量来自 Q1 强结构样本、Q3 高分动能样本、Q4 极值反转样本三条窄通道。

下一步不建议继续扩大“aggressive”总开关。建议按 Task A-E 做窄通道工程化，并要求每条通道独立账本、独立熔断、独立日落条款。盈利进攻的方向不是“多开仓”，而是让系统在 dry-run 中明确知道：**什么时候顺势、什么时候等确认、什么时候只做反转侦察、什么时候坚决不动。**
