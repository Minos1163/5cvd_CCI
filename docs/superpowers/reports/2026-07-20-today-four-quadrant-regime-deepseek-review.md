# AI300 2026-07-20 日内日志复盘与四象限分区策略建议

**提交对象:** DeepSeek 评审  
**分析窗口:** 2026-07-20 00:00:00 至 18:45:05，北京时间。  
**运行模式:** VPS dry-run，`target_tier=aggressive`。  
**数据来源:** `logs/2026-07/2026-07-20/decisions.jsonl`、`near_misses.jsonl`、`order_drafts.jsonl`、`paper_trades.jsonl`、`scout_micro/paper_trades.jsonl`、`paper_ab/*`、`summary.json`、`paper_summary.json`。  
**重要口径:** 本报告只分析 dry-run/paper ledger，不构成投资建议；今日主账本、SCOUT 与 A/B paper ledger 均无成交样本，因此不能用今天数据判断出场模式优劣。

---

## 0. 结论摘要

1. **昨晚修改后的基础设施已在日志中可见，但今天没有形成可验证交易样本。** `summary.json` 已输出 `net_beta_exposure_model=static_v1_observation_only`，`paper_summary.json` 已出现 `ab_ledger.legacy` 与 `ab_ledger.trend_capture`，但两套 A/B 账本今日 `trade_count=0`。
2. **今天不是“开仓后亏损”，而是“没有开仓”。** 00:00 至 18:45 共 572 条决策，`NO_TRADE=502`、`WATCH=70`、`PROBE=0`、`DIRECT=0`；主账本、SCOUT、A/B 账本成交数全部为 0。
3. **aggressive 模式没有打通进攻通道。** 今日虽有 3 条 score >=85 高分信号，但 1 条被 `SYMBOL_WATCH_ONLY` 拦截，2 条 SOLUSDT SHORT 被 `DIRECT_BELOW_RISK_REWARD_GEOMETRY` 拦截，没有转化为 PROBE/DIRECT。
4. **按四象限划分，全天多数时间落在 Q4/Q3，而非可进攻的 Q1。** 全天 572 条决策中，Q4 有 334 条，Q3 有 109 条，Q2 有 78 条，Q1 只有 51 条。最新 13 个标的快照没有 Q1/Q2，只有 Q3/Q4。
5. **当前问题的主因不是 trend_capture 今天失败，而是入场层没有给出可执行样本。** A/B 出场账本需要同一批入场信号才能比较 legacy 与 trend_capture；今天入场为 0，因此出场架构无法被验证。
6. **建议回到四象限分区：先判断市场/标的处在哪个进攻象限，再区分持仓与空仓动作。** 只有 Q1 且通过 Fib/RR/标的政策门时，才允许主动开仓；Q2/Q3 主要等待拐点；Q4 以空仓或减仓为主。

---

## 1. 今日执行证据

### 1.1 决策与成交

| 指标 | 数值 |
|---|---:|
| 决策总数 | 572 |
| NO_TRADE | 502 |
| WATCH | 70 |
| PROBE | 0 |
| DIRECT | 0 |
| score >=85 高分信号 | 3 |
| near-miss | 3 |
| order draft 记录 | 572 |
| approved order draft | 0 |
| 主账本新增成交 | 0 |
| SCOUT 新增成交 | 0 |
| A/B legacy 账本成交 | 0 |
| A/B trend_capture 账本成交 | 0 |

### 1.2 分数分布

| 分数区间 | 数量 |
|---|---:|
| <70 | 527 |
| 70-75 | 30 |
| 75-80 | 7 |
| 80-85 | 5 |
| 85-90 | 3 |
| >=90 | 0 |

### 1.3 主要拦截原因

| 原因 | 次数 | 归类 |
|---|---:|---|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 147 | LONG 方向政策 |
| `SYMBOL_WATCH_ONLY` | 83 | 标的政策 |
| `SYMBOL_BLACKLISTED` | 73 | 标的政策 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 52 | Fib 防衰竭 |
| `PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_6.0` | 3 | PROBE 组件门 |
| `PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0` | 3 | PROBE 组件门 |
| `PROBE_LOW_SCORE_ELITE_VETO` | 2 | 精兵门 |
| `HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0` | 2 | high beta RR 门 |

### 1.4 今日 3 条高分信号

| 时间 | 标的 | 方向 | 分数 | 动作 | 四象限 | 拦截原因 | 关键说明 |
|---|---|---|---:|---|---|---|---|
| 10:30:05 | ADAUSDT | SHORT | 87.30 | NO_TRADE | Q3 | `SYMBOL_WATCH_ONLY` | 资金/动能强，趋势/结构轴未完全达 Q1，且标的政策拦截 |
| 13:15:05 | SOLUSDT | SHORT | 88.80 | WATCH | Q3 | `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_0.5` | 高分但 RR 不足，未转主账本 |
| 15:00:05 | SOLUSDT | SHORT | 85.19 | WATCH | Q1 | `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 当日最接近进攻样本，但仍被 RR gap 拦截 |

**归因:** 今天唯一进入 Q1 的高分样本是 SOLUSDT SHORT，但静态 RR 几何未达 DIRECT 门槛。随后最新 SOLUSDT 快照已退化为 Q4/LONG 侧弱结构，因此不能在最新状态追单。

---

## 2. 当前四象限定义

本报告只使用当前日志中已存在、可 live 执行的指标，不引入未来 K 线或事后信息。

### 2.1 轴定义

| 轴 | 使用指标 | 判定 |
|---|---|---|
| 趋势/结构轴 | `trend_ema_context`、`price_action_structure` | `trend_ema_context >= 15` 且 `price_action_structure >= 10` 视为趋势/结构有效 |
| 资金/动能轴 | `flow_cvd_confirmation`、`cci_momentum_quality` | `flow_cvd_confirmation >= 14` 且 `cci_momentum_quality >= 7` 视为资金/动能有效 |

### 2.2 象限定义

| 象限 | 定义 | 策略含义 |
|---|---|---|
| Q1 趋势+资金共振 | 趋势/结构有效，资金/动能有效 | 唯一主动进攻区 |
| Q2 有趋势但动能不足 | 趋势/结构有效，资金/动能不足 | 趋势背景存在，但等待资金/动能拐点 |
| Q3 有资金但结构不足 | 趋势/结构不足，资金/动能有效 | 有异动，但结构未确认，等待 PA/Fib 完成 |
| Q4 趋势与资金均弱 | 两轴均不足 | 噪声/弱势区，原则上不主动开仓 |

### 2.3 Fib/RR 的定位

`fibonacci_location` 与 `risk_reward_geometry` 不作为象限轴，而作为执行门：

- Q1 只代表“可以研究进攻”，不等于可以立刻开仓；
- 开仓仍需通过 Fib/RR、标的政策、仓位、冷却、组合风险；
- 今日 SOLUSDT 15:00 已进入 Q1，但被 RR gap 拦截，说明系统没有把 Q1 直接等同于可交易。

---

## 3. 今日四象限分布

| 象限 | 全天决策数 | 占比 | 最新标的数 | 当前含义 |
|---|---:|---:|---:|---|
| Q1 趋势+资金共振 | 51 | 8.92% | 0 | 盘中短暂出现，最新已消失 |
| Q2 有趋势但动能不足 | 78 | 13.64% | 0 | 盘中有趋势背景，但未持续到最新 |
| Q3 有资金但结构不足 | 109 | 19.06% | 5 | 最新仍有资金/动能，但 PA/结构不足 |
| Q4 趋势与资金均弱 | 334 | 58.39% | 8 | 今日主导状态，原则上不主动进攻 |

**判断:** 今天没有好效果的直接原因，是当前最新市场状态没有可交易 Q1。盘中 Q1 样本数量本身不多，且可疑进攻点仍被 RR/标的政策拦截。

---

## 4. 四象限持仓/空仓动作矩阵

### 4.1 Q1：趋势+资金共振

| 状态 | 建议动作 | 拐点后动作 |
|---|---|---|
| 空仓 | 不追市价；等待当前方向的回踩确认、结构突破确认或下一根 K 线收盘确认 | 若方向为 LONG，且 Fib/RR/政策通过，可开多；若方向为 SHORT，且 Fib/RR/政策通过，可开空 |
| 持有多单 | 若方向仍为 LONG，优先 hold，用 trend_capture 或结构止损让利润奔跑 | 若 CVD/CCI 转弱、PA 破位或方向翻为 SHORT，平多；若反向 Q1 确认，再考虑开空 |
| 持有空单 | 若方向仍为 SHORT，优先 hold，用 trend_capture 或结构止损让利润奔跑 | 若 CVD/CCI 转强、PA 破位或方向翻为 LONG，平空；若反向 Q1 确认，再考虑开多 |

**执行门槛建议:** Q1 不是直接开仓信号。建议开仓仍要求 `fibonacci_location >= 15`、`risk_reward_geometry >= 2`，主账本 DIRECT 继续要求更高 RR；对 high beta 标的保留更高 RR 与更低名义本金。

### 4.2 Q2：有趋势/结构，但资金或动能不足

| 状态 | 建议动作 | 拐点后动作 |
|---|---|---|
| 空仓 | 观察，不提前开仓；等待 CVD 与 CCI 向当前趋势方向恢复 | 资金/动能轴恢复后进入 Q1，再按 Q1 规则开多/开空 |
| 持有多单 | 若趋势仍支持 LONG 且止损已保护，可 hold；不加仓 | 若 CVD/CCI 继续走弱，平多；若恢复 Q1，可继续 hold |
| 持有空单 | 若趋势仍支持 SHORT 且止损已保护，可 hold；不加仓 | 若 CVD/CCI 继续走弱但价格结构反向，平空；若恢复 Q1，可继续 hold |

**风险点:** Q2 容易出现“结构看起来好，但没有成交量/资金流跟随”的假启动。今天 HYPE、LINK、SOL 最新都表现为趋势项不差但 PA/动能局部不足，不能直接作为 aggressive 开仓理由。

### 4.3 Q3：有资金/动能，但趋势/结构不足

| 状态 | 建议动作 | 拐点后动作 |
|---|---|---|
| 空仓 | 不抢跑；等待 PA 结构、Fib 位置和 RR 几何完成 | 若 PA 结构补齐并转入 Q1，再开多/开空；否则只记录 near-miss |
| 持有多单 | 不加仓；若当前方向仍为 LONG，可短时 hold，但必须有明确止损 | 若 PA 无法确认或方向转 SHORT，平多 |
| 持有空单 | 不加仓；若当前方向仍为 SHORT，可短时 hold，但必须有明确止损 | 若 PA 无法确认或方向转 LONG，平空 |

**今日对应:** ADA、BNB、CC、LINK、XLM 最新属于 Q3。它们不是“完全无机会”，但结构轴不足，不应直接从空仓开主账本。

### 4.4 Q4：趋势与资金均弱

| 状态 | 建议动作 | 拐点后动作 |
|---|---|---|
| 空仓 | 保持空仓；不因为 aggressive 模式而开仓 | 只有先转 Q2/Q3，再最终进入 Q1，才重新评估开多/开空 |
| 持有多单 | 原则上不新增风险；若未保护，优先按止损/成本超时/结构破位退出 | 若出现反向 SHORT Q1，先平多，再评估开空 |
| 持有空单 | 原则上不新增风险；若未保护，优先按止损/成本超时/结构破位退出 | 若出现反向 LONG Q1，先平空，再评估开多 |

**今日对应:** Q4 占全天 58.39%，最新 13 个标的中 8 个在 Q4。今天系统不给积极结果，与这个分布一致。

---

## 5. 最新标的快照与技术建议

当前主账本、SCOUT、A/B 账本均无持仓，因此下表以“空仓建议”为主，并补充若已有持仓时的处理规则。

| 标的 | 最新象限 | 最新方向 | 最新分数 | 今日最高分 | 最新动作/原因 | 空仓建议 | 若有持仓 |
|---|---|---|---:|---:|---|---|---|
| ADAUSDT | Q3 | LONG | 51.00 | 87.30 | `NO_TRADE` / `SYMBOL_WATCH_ONLY` | 不开；观察 watch-only 晋级，不在结构不足时抢跑 | 多单不加仓，结构不补齐则平多；空单只在重新出现 SHORT Q1 时 hold |
| BCHUSDT | Q4 | LONG | 40.50 | 80.09 | `NO_TRADE` / `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 不开；等待脱离 Q4 | 弱势区不 hold 未保护仓位，按止损/超时退出 |
| BNBUSDT | Q3 | LONG | 54.00 | 69.30 | `NO_TRADE` / `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 不开；等 PA 结构补齐 | 多单谨慎 hold，不加仓；结构失败平多 |
| CCUSDT | Q3 | SHORT | 64.15 | 79.19 | `WATCH` | 不开；SHORT 有资金/动能但 PA 不足 | 空单若已保护可 hold；结构不确认则平空 |
| DOGEUSDT | Q4 | LONG | 48.03 | 71.30 | `NO_TRADE` / `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 不开 | 未保护多单应退出；等待 Q1 |
| HYPEUSDT | Q4 | LONG | 56.10 | 74.80 | `NO_TRADE` / `SIDE_THRESHOLD_OFFSET_LONG_10.00` | high beta 不开；RR=0，不满足进攻 | 未保护多单应严格止损，不加仓 |
| LINKUSDT | Q3 | LONG | 63.10 | 70.80 | `NO_TRADE` / `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 不开；资金强但 PA=0 | 多单不加仓，等 PA 补齐；失败平多 |
| SOLUSDT | Q4 | LONG | 55.10 | 88.80 | `NO_TRADE` / `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 最新不追；盘中 SHORT Q1 已过期，需重新触发 | 若有多单，Q4 不应放任；若有空单，需看是否仍有 SHORT Q1 支撑 |
| TRXUSDT | Q4 | LONG | 29.60 | 74.30 | `NO_TRADE` / `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 不开 | 弱势区不 hold 未保护仓位 |
| XLMUSDT | Q3 | LONG | 62.30 | 81.70 | `NO_TRADE` / `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 不开；等待 PA/Fib/RR 同时成立 | 多单不加仓，结构确认前只观察 |
| XMRUSDT | Q4 | LONG | 54.87 | 78.30 | `NO_TRADE` / `SYMBOL_WATCH_ONLY` | 不开；watch-only 且 Q4 | 未保护多单应退出；晋级需要回放/SCOUT 证据 |
| XRPUSDT | Q4 | LONG | 66.48 | 76.70 | `NO_TRADE` / `SYMBOL_BLACKLISTED` | 不开；黑名单不因分数放行 | 若异常持仓，应优先退出而非加仓 |
| ZECUSDT | Q4 | LONG | 38.50 | 80.15 | `NO_TRADE` / `SYMBOL_BLACKLISTED` | 不开；黑名单且 Q4 | 若异常持仓，应优先退出 |

---

## 6. 对昨晚修改效果的归因

### 6.1 已生效的部分

| 项目 | 今日日志证据 | 评价 |
|---|---|---|
| aggressive dry-run | `summary.json` 显示 `target_tier=aggressive` | 已运行 |
| 净 beta 静态观测 | `net_beta_exposure_model=static_v1_observation_only`，`net_beta_exposure_pct=0.0` | 已输出；今日无持仓所以为 0 |
| 主账本 exit mode | `paper_exit_mode=legacy` | 主账本仍 legacy |
| SCOUT exit mode | `scout_micro_exit_mode=trend_capture` | 已配置，但今日无 SCOUT 成交 |
| Paper A/B | `paper_summary.json` 有 `ab_ledger.legacy` 与 `ab_ledger.trend_capture` | 已有账本结构，但今日两边成交均为 0 |

### 6.2 未能产生好效果的根因

1. **今日没有入场样本，导致所有“出场优化”无法被验证。** legacy 与 trend_capture 的差异只能在相同入场下比较，今天 A/B 两侧 `trade_count=0`。
2. **高分信号太少，且可执行性不足。** 572 条决策只有 3 条 >=85，且分别被 watch-only 与 RR gap 拦截。
3. **最新市场/标的状态不是进攻象限。** 最新 13 个标的没有 Q1/Q2，说明当前并非“应该强行开仓但系统胆小”，而是指标组合没有给出结构化进攻环境。
4. **LONG 侧仍被结构性压制。** `SIDE_THRESHOLD_OFFSET_LONG_10.00` 出现 147 次，最新多数标的为 LONG 意图但结构/动能不完整，不能简单降低 offset。
5. **RR 几何继续限制主账本转化。** 今日最接近的 SOLUSDT SHORT 高分样本被 RR gap 拦截，说明“有趋势+资金”仍可能缺乏足够 payoff 结构。

---

## 7. 建议的四象限策略方向

### 7.1 不建议做的事

- 不建议因为今天没有开仓就全局降低分数阈值；
- 不建议直接解除 `SIDE_THRESHOLD_OFFSET_LONG_10.00`；
- 不建议把 Q3 的资金/动能异动当作开仓信号；
- 不建议用今天的数据否定 trend_capture，因为今天没有触发任何可比较出场样本。

### 7.2 建议立即补充的日志与诊断

| 建议 | 目的 |
|---|---|
| 在 `decisions.jsonl` 中显式输出 `quadrant`、`trend_structure_axis_ok`、`flow_momentum_axis_ok` | 让每次不开仓能解释为“非进攻象限”或“执行门未通过” |
| 在 `summary.json` 输出各象限计数与最新标的象限分布 | 避免 aggressive 模式下无交易被误解为系统失灵 |
| 对 Q1 但被 RR gap 拦截的样本建立 near-miss 回放池 | 判断 RR 是否误杀趋势延续 |
| 对 Q3 高分 watch-only 样本建立 symbol promotion 面板 | 判断 ADA/XMR 等是否值得晋级到 SCOUT |

### 7.3 可给 DeepSeek 评审的策略假设

1. **Q1_RR_GAP_SCOUT:** 当信号进入 Q1、score >=85、仅因 RR gap 未达 DIRECT 时，是否允许进入 50 USDT SCOUT，而不是完全 WATCH？
2. **Q3_TO_Q1_CONFIRMATION:** 对 Q3 高分信号，不立刻开仓；若未来 1-3 根 15m K 线内 PA 结构补齐并进入 Q1，再允许 SCOUT。
3. **WATCH_ONLY_PROMOTION_TEST:** 对 ADA/XMR 等 watch-only 标的，只在 Q1 且 Fib/RR 达标时进行 SCOUT 晋级测试，避免在 Q3/Q4 放行。
4. **LONG_OFFSET_DYNAMIC:** LONG offset 不做全局降低；只在 Q1 且 `price_action_structure >=18`、`fibonacci_location >=15`、`risk_reward_geometry >=2` 时，允许 LONG_OFFSET 高分样本进入 SCOUT。
5. **NO_Q1_NO_OFFENSE_RULE:** 若最近 N 根 15m 周期内无 Q1 标的，系统应输出“非进攻窗口”，主动降低交易期待，而不是扩大 aggressive 权限。

---

## 8. DeepSeek 重点评审问题

1. 当前四象限轴是否合理：`trend_ema_context + price_action_structure` 作为趋势/结构轴，`flow_cvd_confirmation + cci_momentum_quality` 作为资金/动能轴，是否需要调整阈值？
2. 今日 SOLUSDT 15:00 的 SHORT Q1 高分样本被 RR gap 拦截，是否应进入 SCOUT 而非 WATCH？
3. 对 Q3 高分样本，是否应设计“等待结构补齐后的二次触发”机制，而不是在原 bar 上直接放弃？
4. `SIDE_THRESHOLD_OFFSET_LONG_10.00` 是否应只在 Q1 中动态降级为 SCOUT 权限，而不是全局下调？
5. 对 watch-only 标的，是否应要求“Q1 + Fib/RR 通过 + rolling 回放表现为正”才允许晋级？
6. A/B 出场账本已经建立但无入场样本，是否应增加一个“只服务 A/B 的镜像入场样本池”，在不影响主账本的情况下积累出场对比？
7. 是否应在 summary 中加入“今日进攻窗口质量评分”，当 Q1 低占比且最新无 Q1 时，明确建议保持空仓？

---

## 9. 最终归因

今天 00:00 至 18:45 的 dry-run 没有积极结果，根因不是单一参数问题，而是：

1. **市场/标的最新状态不在进攻象限。** 最新快照只有 Q3/Q4，没有 Q1/Q2。
2. **高分信号稀少且未通过执行门。** 全天只有 3 条 score >=85，其中 2 条被 RR gap 拦截，1 条被 watch-only 拦截。
3. **出场优化没有入场样本可验证。** A/B 账本存在，但今天 legacy/trend_capture 两边都是 0 笔。
4. **aggressive 模式没有解决“从高分到可执行仓位”的断裂。** 它没有把 Q1 near-miss、Q3 转 Q1、watch-only 晋级这三类机会转化为可控样本。

因此，下一轮优化不应继续做全局 aggressive，而应回到四象限：

- Q1：允许结构化进攻，但必须过 Fib/RR/政策门；
- Q2：等待资金/动能拐点；
- Q3：等待 PA/Fib/RR 结构补齐；
- Q4：空仓或退出弱持仓。

这个框架的目标不是增加随机开仓，而是让系统明确知道：什么时候该 hold，什么时候该等待拐点，什么时候才允许开多、开空、平多、平空。
