# AI300 07-22 21:30 后四象限进攻失效归因报告

**提交对象:** DeepSeek / Claude 复核
**分析窗口:** 2026-07-22 21:30 至 2026-07-27 约 11:15，北京时间。
**运行模式:** dry-run / paper ledger。
**数据来源:** `logs/2026-07/2026-07-22` 至 `logs/2026-07/2026-07-27` 下的 `decisions.jsonl`、`near_misses.jsonl`、`paper_trades.jsonl`、`scout_micro/paper_trades.jsonl`、`paper_ab/*/paper_trades.jsonl`、`summary.json`、`paper_summary.json`。
**重要口径:** 本报告中的 near-miss 未来收益与拐点统计均为事后归因，不可直接作为 live 信号；策略修改仍应先在 dry-run / paper / scout 层验证。

---

## 0. 结论摘要

1. **上次四象限进攻策略没有形成有效进攻，核心不是“完全没行情”，而是“象限标签没有解决入场方向、交易位置和执行转化”。** 窗口内共有 5,720 条决策，仅 1 笔 `PROBE`，594 条 `WATCH`，5,125 条 `NO_TRADE`。Q1 有 595 条，但只有 1 笔进入主账本。
2. **Q1 并不等于可交易机会。** Q1 平均总分 71.68，虽然趋势/结构轴与资金/动能轴较强，但 `risk_reward_geometry` 平均只有 1.16/8，`fibonacci_location` 平均 9.00/18。也就是说，Q1 多数只是“动能环境好”，不是“入场位置好”。
3. **行情拐点没有被抓住的关键原因是方向判断在拐点附近多数反向。** 事后识别 183 个局部拐点后，系统方向与未来 8 根 15m K 线的主要运动方向匹配 56 次，错误 127 次。Q1 拐点 28 个中只有 2 个方向匹配，Q3 拐点 31 个中只有 3 个方向匹配。
4. **A/B 镜像账本证明“多开仓”本身不是答案。** A/B legacy 与 trend_capture 各有 27 笔平仓，事件口径 PnL 分别约 `-19.0858` 与 `-19.1828`。首份自动报告中 legacy PF 为 0.0291，trend_capture PF 为 0.0498，trend_capture 略好但两者都不可用。
5. **SCOUT 任务在本窗口没有产生新增交易样本，这是执行链路缺口。** `summary.json` 显示 Q1 RR gap、Q2 pending、Q3 to Q1、mission stop circuit 等开关已启用，但 `scout_micro/paper_trades.jsonl` 在 07-22 21:30 后为 0 开 0 平。near-miss 中存在 `scout_candidate=true`，但没有转成 SCOUT ledger 事件。
6. **真正有价值的机会集中在少数类型，不支持全局放宽。** 48 个 near-miss 的 4 小时后验显示，RR gap 类几乎没有趋势延伸；相对更有价值的是少数 `SIDE_THRESHOLD_OFFSET_LONG_10.00` 的 BCH/CC 多头，以及部分 `SYMBOL_BLACKLISTED` 的 ZEC/XRP 样本。该证据支持“窄通道进攻”，不支持全局激进。

---

## 1. 策略开关是否已经生效

从 2026-07-27 最新 `summary.json` 看，上一轮建议中的主要开关已经出现在运行摘要中：

| 模块 | 日志状态 | 说明 |
|---|---:|---|
| `dry_run_q1_green_channel_enabled` | true | Q1 绿色通道配置存在 |
| `mirror_ab_enabled` | true | A/B 镜像样本池存在 |
| `paper_ab_auto_report_enabled` | true | 自动报告开关存在 |
| `paper_ab_auto_switch_enabled` | true | 自动切换开关存在 |
| `scout_micro_q1_rr_gap_enabled` | true | Q1 RR gap SCOUT 配置存在 |
| `scout_micro_q2_pending_enabled` | true | Q2 pending 配置存在 |
| `scout_micro_q3_to_q1_enabled` | true | Q3 to Q1 配置存在 |
| `scout_micro_mission_stop_circuit_enabled` | true | mission 三连止损熔断配置存在 |
| `effective_paper_exit_mode` | `legacy` | 未触发自动切换 |
| `data_health` | `DEGRADED` | 07-23 起持续退化 |

结论：**配置层面大多已经落盘，但执行效果没有达到“每天产生足够可评估交易样本”的目标。**

---

## 2. 总体执行表现

| 项目 | 数值 |
|---|---:|
| 决策总数 | 5,720 |
| `NO_TRADE` | 5,125 |
| `WATCH` | 594 |
| `PROBE` | 1 |
| Q1 / Q2 / Q3 / Q4 | 595 / 724 / 1,141 / 3,260 |
| near-miss | 48 |
| 主账本交易 | 1 开 / 1 平 |
| SCOUT 交易 | 0 开 / 0 平 |
| A/B legacy | 27 开 / 27 平 / 8 次减仓 |
| A/B trend_capture | 27 开 / 27 平 / 6 次减仓 |

每日摘要显示，07-23 起 `data_health=DEGRADED` 持续存在，且 `effective_paper_exit_mode` 始终为 `legacy`：

| 日期 | data health | 决策累计摘要 | near-miss | effective exit |
|---|---|---|---:|---|
| 2026-07-22 | OK | WATCH 51 / NO_TRADE 455 / PROBE 1 | 0 | legacy |
| 2026-07-23 | DEGRADED | WATCH 199 / NO_TRADE 1555 / PROBE 1 | 11 | legacy |
| 2026-07-24 | DEGRADED | WATCH 344 / NO_TRADE 2658 / PROBE 1 | 17 | legacy |
| 2026-07-25 | DEGRADED | WATCH 473 / NO_TRADE 3777 / PROBE 1 | 32 | legacy |
| 2026-07-26 | DEGRADED | WATCH 575 / NO_TRADE 4923 / PROBE 1 | 47 | legacy |
| 2026-07-27 | DEGRADED | WATCH 589 / NO_TRADE 5091 / PROBE 1 | 47 | legacy |

---

## 3. 四象限得分结构

当前象限可以理解为：

- **Q1:** 趋势/结构轴通过，资金/动能轴通过。
- **Q2:** 趋势/结构轴通过，资金/动能轴未通过。
- **Q3:** 趋势/结构轴未通过，资金/动能轴通过。
- **Q4:** 两条轴均未通过。

最新配置阈值为：`trend_ema_min=15`、`price_action_min=10`、`flow_cvd_min=14`、`cci_min=7`。

| 象限 | 样本数 | 动作分布 | 平均分 | 中位分 | Trend | PA | CVD | CCI | Fib | RR |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Q1 | 595 | WATCH 296 / NO_TRADE 298 / PROBE 1 | 71.68 | 72.10 | 16.95 | 16.47 | 18.00 | 10.10 | 9.00 | 1.16 |
| Q2 | 724 | NO_TRADE 633 / WATCH 91 | 58.56 | 58.59 | 17.03 | 16.62 | 13.23 | 2.16 | 8.29 | 1.24 |
| Q3 | 1,141 | NO_TRADE 959 / WATCH 182 | 59.02 | 58.00 | 14.39 | 5.22 | 18.00 | 9.49 | 11.11 | 0.81 |
| Q4 | 3,260 | NO_TRADE 3235 / WATCH 25 | 41.24 | 41.50 | 13.43 | 3.78 | 10.75 | 1.12 | 11.26 | 0.89 |

### 3.1 Q1 失效点

Q1 的 CVD 和 CCI 均较强，但交易质量短板非常集中：

| Q1 主要拦截原因 | 次数 |
|---|---:|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 161 |
| `SYMBOL_BLACKLISTED` | 85 |
| `SYMBOL_WATCH_ONLY` | 71 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 66 |
| `PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0` | 63 |
| `PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_6.0` | 27 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 21 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0` | 17 |

解释：Q1 绿色通道虽然存在，但 Q1 里大量样本仍然被 LONG offset、symbol policy、Fib exhaustion 和 RR/Fib 缺口截断。Q1 不是最终准入，只是 regime 标签。

### 3.2 Q2 失效点

Q2 的趋势和 PA 平均并不差，但 CCI 极低，说明“结构存在但启动动能不足”：

| Q2 主要拦截原因 | 次数 |
|---|---:|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 203 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 131 |
| `SYMBOL_BLACKLISTED` | 100 |
| `SYMBOL_WATCH_ONLY` | 91 |

解释：Q2 pending 方向是合理的，但本窗口没有看到 SCOUT ledger 转化。该任务如果要证明有效，必须记录 pending 创建、确认、过期、拒绝原因，否则无法知道是行情未确认还是执行链断裂。

### 3.3 Q3 失效点

Q3 的 CVD/CCI 强，但 PA 很弱，说明很多是资金流异动或追动能，不是结构完成：

| Q3 主要拦截原因 | 次数 |
|---|---:|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 391 |
| `SYMBOL_WATCH_ONLY` | 151 |
| `SYMBOL_BLACKLISTED` | 136 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 76 |
| `PROBE_BELOW_ELITE_STRUCTURE_GATE` | 13 |

解释：Q3 不应直接做趋势开仓，应做“二次确认”或“反向拐点侦察”。直接把 Q3 当突破延续，很容易追在局部高低点。

### 3.4 Q4 失效点

Q4 占全部决策 56.99%，平均分 41.24，绝大多数为不可交易环境。值得注意的是，拐点后验里大量真实拐点发生在 Q4，但系统即使方向匹配也因为低分不交易。

---

## 4. near-miss 后验表现

48 个 near-miss 的原因分布：

| primary reason | 次数 |
|---|---:|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 25 |
| `SYMBOL_WATCH_ONLY` | 10 |
| `SYMBOL_BLACKLISTED` | 5 |
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 5 |
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0` | 3 |

near-miss 仅出现在 Q1 与 Q3：

| 象限 | 数量 | 平均分 | 主要原因 |
|---|---:|---:|---|
| Q1 | 31 | 83.95 | LONG offset 15、watch-only 8、blacklist 4、RR gap 4 |
| Q3 | 17 | 82.94 | LONG offset 10、watch-only 2、RR gap 4、blacklist 1 |

### 4.1 未来 4 小时 MFE/MAE

| 分组 | n | 平均 MFE | 中位 MFE | 平均 MAE | 平均收益 | MFE >= 1% | MFE >= 2% | MAE <= -1% |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Q1 near-miss | 31 | 0.76% | 0.38% | -0.74% | -0.05% | 10 | 2 | 10 |
| Q3 near-miss | 17 | 0.41% | 0.26% | -0.70% | -0.13% | 1 | 1 | 4 |

按原因看：

| 原因 | n | 平均 MFE | 中位 MFE | 平均收益 | MFE >= 1% | MAE <= -1% | 结论 |
|---|---:|---:|---:|---:|---:|---:|---|
| LONG offset | 25 | 0.64% | 0.38% | +0.07% | 4 | 6 | 有少数强机会，但不能全放 |
| SYMBOL_BLACKLISTED | 5 | 1.61% | 1.80% | +0.56% | 4 | 2 | 值得单独复核标的政策 |
| SYMBOL_WATCH_ONLY | 10 | 0.50% | 0.30% | -0.71% | 3 | 6 | 不支持广泛晋级 |
| RR gap 2.0 | 5 | 0.17% | 0.19% | -0.14% | 0 | 0 | 不支持放宽 |
| RR gap 4.0 | 3 | 0.23% | 0.19% | -0.20% | 0 | 0 | 不支持放宽 |

### 4.2 最值得复核的错过样本

| 时间 | Symbol | 方向 | 象限 | 分数 | 拦截原因 | 4h MFE | 4h MAE | 4h 收益 |
|---|---|---|---|---:|---|---:|---:|---:|
| 07-26 23:00 | BCHUSDT | LONG | Q1 | 84.10 | LONG offset | 3.53% | -0.12% | 3.37% |
| 07-24 02:45 | ZECUSDT | SHORT | Q1 | 82.09 | BLACKLIST | 2.51% | -0.63% | 1.21% |
| 07-25 17:30 | CCUSDT | LONG | Q3 | 82.30 | LONG offset | 2.23% | -0.05% | 2.16% |
| 07-26 22:30 | BCHUSDT | LONG | Q1 | 82.70 | LONG offset | 1.90% | -0.01% | 1.79% |
| 07-24 22:15 | ZECUSDT | SHORT | Q1 | 84.59 | BLACKLIST | 1.86% | -0.69% | 0.04% |
| 07-24 21:15 | ZECUSDT | SHORT | Q1 | 83.09 | BLACKLIST | 1.80% | -1.10% | 1.32% |
| 07-25 19:00 | CCUSDT | LONG | Q1 | 85.19 | LONG offset | 1.48% | -0.16% | 1.33% |

归因：真正错过的趋势机会不是 RR gap，而是 **少数高分 LONG offset 突破** 和 **被标的政策阻断的 ZEC/XRP 样本**。因此下一步应做窄通道实验，而不是全局降低 RR 或全局打开观察池。

---

## 5. 账本表现

### 5.1 主账本

窗口内主账本只有一笔交易：

| 时间 | Symbol | 方向 | 象限 | exit mode | 平仓原因 | 事件 PnL |
|---|---|---|---|---|---|---:|
| 07-23 04:00 -> 07-23 06:00 | HYPEUSDT | LONG | Q1 | legacy | `COST_BREAKEVEN_TIMEOUT` | -16.3530 |

这笔交易最高 favorable R 只有 0.2841，说明没有进入趋势捕捉区间，问题在入场质量或入场时机，不在 trend_capture 是否启用。

### 5.2 SCOUT

窗口内 SCOUT 微仓为 0 开 / 0 平。

这是重要缺口：日志中 near-miss 已有 `scout_candidate=true` 与 `scout_tags=["TARGETED_LONG_OFFSET"]` 等字段，但 `scout_micro/paper_trades.jsonl` 没有新增事件。当前缺少“候选 -> mission 入场 -> 被拒绝原因”的完整链路日志，因此无法判断是任务门槛过窄、预算/熔断阻断，还是代码路径没有调用 SCOUT ledger。

### 5.3 A/B 镜像账本

| 账本 | 事件数 | 开仓 | 平仓 | 减仓 | 事件 PnL | 主要平仓原因 |
|---|---:|---:|---:|---:|---:|---|
| legacy | 62 | 27 | 27 | 8 | -19.0858 | Q4 防御退出 18、初始止损 3、保本止损 3、TP3 2 |
| trend_capture | 60 | 27 | 27 | 6 | -19.1828 | Q4 防御退出 18、保本止损 5、初始止损 3 |

自动报告已经产生：`logs/2026-07/2026-07-25/paper_ab/reports/ab_report_batch_0001.json`。

| 报告 | closed trades | legacy PF | legacy payoff | trend PF | trend payoff | 结论 |
|---|---:|---:|---:|---:|---:|---|
| batch 0001 | 20 | 0.0291 | 0.1165 | 0.0498 | 0.1991 | trend 略好，但两组均极差 |

自动切换没有触发是合理的：配置要求至少 2 份报告、40 笔平仓、trend payoff 至少 1.3 倍优势。当前只有 1 份报告，且两组绝对收益质量都不合格。

---

## 6. 行情拐点后验分析

**方法:** 对每个 symbol 的 15m kline 序列做事后局部极值识别：以当前 bar 前后各 4 根作为局部高/低点判断，并要求未来 8 根 15m K 线最大运动幅度 >= 1%。这是归因工具，不可用于 live 交易。

| 项目 | 数值 |
|---|---:|
| 后验拐点总数 | 183 |
| 未来方向 LONG | 91 |
| 未来方向 SHORT | 92 |
| 系统方向匹配 | 56 |
| 系统方向错误 | 127 |
| 拐点处 `NO_TRADE` | 160 |
| 拐点处 `WATCH` | 23 |
| 拐点处 `PROBE` | 0 |

按象限拆分：

| 象限 | 拐点数 | 平均未来运动 | 方向匹配 | 方向错误 |
|---|---:|---:|---:|---:|
| Q1 | 28 | 1.48% | 2 | 26 |
| Q2 | 19 | 1.44% | 3 | 16 |
| Q3 | 31 | 1.49% | 3 | 28 |
| Q4 | 105 | 1.42% | 48 | 57 |

典型错误方向样本：

| 时间 | Symbol | 后验方向 | 系统方向 | 未来幅度 | 象限 | 动作 | 分数 | 原因 |
|---|---|---|---|---:|---|---|---:|---|
| 07-23 19:15 | DOGEUSDT | SHORT | LONG | 3.20% | Q3 | NO_TRADE | 49.00 | LONG offset |
| 07-27 04:30 | ZECUSDT | LONG | SHORT | 2.93% | Q4 | NO_TRADE | 24.10 | BLACKLIST |
| 07-23 00:00 | HYPEUSDT | LONG | SHORT | 2.87% | Q1 | WATCH | 72.59 | Fib gap |
| 07-27 05:00 | XLMUSDT | LONG | SHORT | 2.57% | Q3 | WATCH | 68.30 | 无主要硬拦截 |
| 07-23 00:30 | ADAUSDT | SHORT | LONG | 2.50% | Q1 | NO_TRADE | 65.65 | WATCH_ONLY |
| 07-23 18:15 | XMRUSDT | SHORT | LONG | 2.42% | Q4 | NO_TRADE | 56.59 | WATCH_ONLY |
| 07-26 23:00 | ZECUSDT | LONG | SHORT | 2.38% | Q4 | NO_TRADE | 31.60 | BLACKLIST |

关键结论：**四象限解决的是环境分类，不是拐点方向识别。** 在 Q1/Q3 拐点附近，系统往往沿用既有动能方向，实际后续却发生反向运动。因此简单用 Q1 绿色通道开仓，会把部分“动能尾端”当成“趋势启动”。

---

## 7. 为什么没有抓住机会

### 7.1 Q1 被误当成“开仓信号”

Q1 只说明趋势/结构与资金/动能同时较强，但不保证：

- 入场没有追高/追空；
- opposition structure 足够远；
- Fib 位置不是延伸衰竭；
- 当前方向不是局部拐点前的最后一段动能。

本窗口 Q1 的 RR 平均仅 1.16/8，这是最直接证据。

### 7.2 方向模型在拐点处偏追随

后验拐点中系统方向错误 127/183。尤其 Q1 与 Q3 的错误比例很高，说明强动能象限常常出现在局部高低点附近。当前策略缺少“趋势延续”和“衰竭反转”的分流器。

### 7.3 SCOUT 执行链没有提供真实小仓样本

如果 SCOUT 目标是“用小亏损换情报”，本窗口应该至少记录若干 Q1_RR_GAP、LONG_OFFSET、Q2/Q3 pending 交易。但实际 SCOUT 0 交易，导致系统仍主要依赖 mirror A/B。mirror A/B 能评估假设出场，但不能替代 mission 层实际开仓链路。

### 7.4 A/B 显示出场不是主矛盾

trend_capture 相比 legacy 略有改善，但 PF 仍远低于 1。18/27 个 A/B 样本被 `Q4_DEFENSIVE_EXIT` 退出，说明入场后很快进入弱环境。出场优化无法弥补方向和时机错误。

### 7.5 全局放宽 RR 的证据不足

RR gap near-miss 的 4 小时 MFE 很低，未出现 MFE >= 1% 的样本。放宽 RR 只会增加低质量交易，不会解决趋势捕捉问题。

### 7.6 标的政策可能错杀少数机会，但不能直接放开

`SYMBOL_BLACKLISTED` 样本的后验表现最好，但样本只有 5 个，且涉及标的风险政策。该结果支持单独复核 ZEC/XRP 的政策状态，不支持绕过黑名单。

### 7.7 数据健康退化削弱进攻可信度

07-23 起 `data_health=DEGRADED` 持续存在。即使 warmup 数据足够，系统摘要仍处于退化状态。在没有解释退化原因前，扩大主账本激进权限的风险不可忽略。

---

## 8. 如何开启盈利的进攻：建议方向

### 8.1 不要继续全局激进，改为三条窄通道

下一轮进攻应分成三条独立实验通道，每条通道独立统计 PF、胜率、平均 R、MFE/MAE、最大回撤和样本数。

| 通道 | 目的 | 允许对象 | 不允许对象 |
|---|---|---|---|
| `CONTINUATION_LONG_OFFSET_SCOUT` | 捕捉少数被 LONG offset 错杀的顺势延续 | Q1/Q3 高分、低 MAE 历史簇、BCH/CC 类 | 全量 LONG offset |
| `REVERSAL_PIVOT_SCOUT` | 专门捕捉 Q2/Q3/Q4 局部拐点 | 衰竭后确认反向突破 | 无确认的摸顶摸底 |
| `SYMBOL_POLICY_REVIEW_SHADOW` | 复核 ZEC/XRP/观察池是否错杀 | 只做 shadow/paper，不进主账本 | 直接解除 blacklist |

### 8.2 新增反转拐点 SCOUT，而不是让 Q1 继续追动能

建议新增 `REVERSAL_PIVOT_SCOUT`：

**假设:** 当前系统在拐点附近常常给出错误方向，因此需要一个独立反转通道捕捉“动能衰竭后确认”的机会。

**入场候选:**

- 最近 6 根 15m K 线出现局部极端波动或长影线；
- 当前方向的 CCI 从极值回落，或 CCI 动能连续 2 根减弱；
- CVD 不再支持原方向，至少不强烈反向；
- 价格收盘突破最近 2 根 K 线的反向确认位；
- 原 continuation 方向被 Fib exhaustion、upper/lower wick risk、opposition too close 等原因拦截。

**执行约束:**

- 只进 SCOUT，不进主账本；
- 单笔 25-50 USDT，1x；
- 止损以确认 K 线的局部高/低点外侧为准；
- 20 笔前不晋级，50 笔后再评估；
- 若 PF < 0.8 或连续 3 次初始止损，暂停 12 小时；
- 所有样本记录 `pivot_setup_type`、`confirmation_bars`、`pre_pivot_quadrant`、`entry_quadrant`、`side_flip`。

该通道要解决的是“拐点方向判断错误”，不是复用 Q1 绿色通道。

### 8.3 收窄 LONG offset 进攻

后验证据显示 LONG offset 有少数好样本，但全量质量一般。建议只开以下子集：

- `side=LONG`；
- `primary_reason=SIDE_THRESHOLD_OFFSET_LONG_10.00`；
- `quadrant in [Q1, Q3]`；
- `score >= 82`；
- `flow_cvd_confirmation >= 18`；
- `price_action_structure >= 18`，若 Q3 则必须在 3 根 K 内转 Q1 或出现结构确认；
- `fibonacci_location >= 15`；
- `risk_reward_geometry > 0`，且 `rr_zero_reason != OPPOSITION_STRUCTURE_TOO_CLOSE`；
- 标的先限定 BCHUSDT、CCUSDT、HYPEUSDT、SOLUSDT 中已出现后验 MFE 的簇，其他标的不开放。

这条通道的目标不是扩大交易次数，而是验证“LONG offset 是否对高分强流入多头过度保守”。

### 8.4 RR gap 不应作为主攻方向

本窗口 RR gap near-miss：

- `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0`: 5 个，平均 MFE 0.17%，无 MFE >= 1%；
- `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0`: 3 个，平均 MFE 0.23%，无 MFE >= 1%。

因此不建议继续降低 RR 门槛。更合理的做法是保留 RR 硬约束，并把 RR gap 样本只放入 mirror/回放，不进入 SCOUT。

### 8.5 单独做标的政策 shadow 复核

`SYMBOL_BLACKLISTED` 的 5 个 near-miss 平均 MFE 1.61%，表现优于其他分组，但这可能来自短窗口和少数 ZEC 样本。

建议：

- 新增 `SYMBOL_POLICY_SHADOW`，只记录 shadow A/B，不实际进入主账本或 SCOUT；
- 对 ZECUSDT、XRPUSDT 单独输出 14 天 policy review；
- 晋级条件至少要求 20 个 shadow 样本、PF > 1.0、MAE 分布可控；
- 未完成复核前不要解除 blacklist。

### 8.6 修复 SCOUT 候选到开仓的可观测性

当前最大工程缺口是：near-miss 有 `scout_candidate=true`，但 SCOUT ledger 没有事件。建议立即补充一条 `scout_decisions.jsonl`，每个候选都记录：

- `candidate=true/false`；
- `mission`；
- `accepted=true/false`；
- `reject_reason`；
- `budget_state`；
- `mission_stop_circuit_state`；
- `war_fund_state`；
- `position_conflict_state`；
- `pending_created/confirmed/expired`。

没有这条链路，下一轮仍会出现“配置开启但没有交易”的黑箱。

### 8.7 A/B 增加 Q4 防御退出反事实

当前 A/B 两组都大量被 `Q4_DEFENSIVE_EXIT` 关闭，导致 trend_capture 无法真正展示尾部盈利能力。建议在分析层新增第三个反事实账本：

- `legacy_no_q4_exit_counterfactual`
- `trend_capture_no_q4_exit_counterfactual`

该账本只用于分析，不影响主账本风控。目的不是取消 Q4 防御，而是判断 Q4 退出是否过早截断了少数趋势样本。

---

## 9. 下一轮验收标准

| 项目 | 成功标准 | 失败/停止条件 |
|---|---|---|
| SCOUT 链路可观测性 | 每个 near-miss 候选都有 mission 接受/拒绝日志 | 仍然只有 near-miss、没有 scout_decisions |
| LONG offset 窄通道 | 20 笔后 PF > 1.0，平均 MFE/MAE 比 > 1.5 | 20 笔后 PF < 0.8 或连续 3 次初始止损 |
| REVERSAL_PIVOT_SCOUT | 30 笔后方向命中率 > 45%，PF > 0.9 | 30 笔后 PF < 0.7 |
| SYMBOL_POLICY_SHADOW | 20 个 shadow 样本后 PF > 1.0 | MAE <= -1% 的比例超过 40% |
| A/B 出场 | trend_capture PF 和 payoff 连续两批优于 legacy | 两组 PF 均 < 0.5 时不得自动切主账本 |
| 数据健康 | `data_health=OK` 持续 24 小时 | `DEGRADED` 未解释前，不扩大主账本仓位 |

---

## 10. 给评审的核心问题

1. 当前 Q1/Q3 的方向判断是否过度依赖动能延续，是否需要独立的反转/衰竭模型？
2. `SIDE_THRESHOLD_OFFSET_LONG_10.00` 是否应改为静态硬拦截 + 窄通道 SCOUT，而不是全局 offset？
3. `Q4_DEFENSIVE_EXIT` 是必要风控，还是在 A/B 分析中掩盖了 trend_capture 的真实尾部表现？
4. `SYMBOL_BLACKLISTED` 的 ZEC/XRP 样本是否足以启动 shadow policy review？
5. 在 `data_health=DEGRADED` 的情况下，哪些进攻实验可以继续，哪些必须暂停？

---

## 11. 最终判断

四象限策略已经成为“地图”，但还没有成为能盈利的“进攻系统”。本窗口证明：

- Q1 绿色通道只解决了“能不能开”的一小部分问题，没有解决“是否在正确方向、正确位置开”；
- A/B 镜像样本已经说明，单纯扩大样本会亏；
- SCOUT 任务没有生成真实交易，导致最重要的实验层没有发挥作用；
- 拐点机会存在，但当前方向模型在拐点处多数站错边。

下一轮优化应停止“全局激进”，转向 **窄通道 continuation + 独立 reversal scout + 标的政策 shadow + SCOUT 可观测性修复**。真正的盈利进攻不是更多开仓，而是把开仓限制在有明确因果假设、可统计复盘、能在失败时自动暂停的实验通道内。
