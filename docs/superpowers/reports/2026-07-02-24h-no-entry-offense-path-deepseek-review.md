# 2026-07-01 20:00 CST 至 2026-07-02 19:45 CST 无开仓归因与进攻路径评审稿

> 目的：分析北京时间 `2026-07-01 20:00` 至日志最新 `2026-07-02 19:45:05` 约 23.75 小时 dry-run / paper trading 日志，解释“为什么一直没有开仓”，并评估从“堵漏洞”的防御态势转向“扩大盈利点”的可行路径，供 DeepSeek 评审。本文只分析日志并新增文档，不修改策略代码或配置。

## 1. 分析范围与假设

- 窗口开始：`2026-07-01 20:00:00 CST`，对应 UTC `2026-07-01 12:00:00`。
- 窗口结束：日志最新 `2026-07-02 19:45:05 CST`。
- 覆盖文件：
  - `logs/2026-07/2026-07-01/decisions.jsonl`
  - `logs/2026-07/2026-07-02/decisions.jsonl`
  - `logs/2026-07/2026-07-01/gate_rejections.jsonl`
  - `logs/2026-07/2026-07-02/gate_rejections.jsonl`
  - `logs/2026-07/2026-07-01/order_drafts.jsonl`
  - `logs/2026-07/2026-07-02/order_drafts.jsonl`
  - `logs/2026-07/2026-07-01/paper_trades.jsonl`
  - `logs/2026-07/2026-07-02/paper_trades.jsonl`
  - `logs/2026-07/2026-07-02/summary.json`
  - `logs/2026-07/2026-07-02/paper_summary.json`
  - `logs/2026-07/2026-07-02/health.json`
- 本报告按 Asia/Shanghai 时间解释“昨晚 20:00”。
- 本窗口没有产生新交易，因此无法计算本窗口新增 Sharpe、单窗口 profit factor、MFE/MAE、expectancy 和 tail risk。报告只引用截至最新 summary 的累计账户状态，并对“无开仓”做归因。

## 2. 总结论

本窗口不是“开仓后没有砍仓”，而是**从未进入开仓链路**。

关键证据：

| 指标 | 结果 |
|---|---:|
| decisions | 1152 |
| NO_TRADE | 994 |
| WATCH | 158 |
| PROBE | 0 |
| DIRECT | 0 |
| approved order drafts | 0 |
| paper_trades | 0 |
| approved executions | 0 |
| latest open_positions | 0 |
| latest orders_submitted | 0 |
| latest data_health | OK |

因此，“一直没有开仓”的直接原因不是交易所接口、paper executor、仓位管理或退出逻辑故障，而是**决策层没有任何信号通过到 PROBE / DIRECT，order draft / execution 审计全部为未获批 noop，未生成可提交订单**。

执行链路补充证据：

- `attribution.jsonl` 在窗口内有 `1152` 条 decision 与 `1152` 条 execution 审计。
- `execution.result.approved=false` 共 `1152` 次。
- `execution.result.status=noop` 共 `1152` 次。
- 典型拒绝消息：`entry chain action does not allow live order draft`。
- `order_drafts.jsonl` 记录的是未获批草稿审计，`request=null`；它不代表真实下单请求已生成。

上一轮防线已经生效，系统从“PROBE 低质量交易造成亏损”转为“几乎所有机会都被门槛压在 WATCH / NO_TRADE”。这对止血是好事，但对 24 小时 10 到 20 次开仓目标而言，已经进入信号饥饿状态。

## 3. 最新账户状态

`logs/2026-07/2026-07-02/paper_summary.json` 最新值：

| 指标 | 数值 |
|---|---:|
| equity | 9787.7461 |
| initial_equity | 10000.0000 |
| realized_pnl | -212.2539 |
| return_pct | -2.1225% |
| trade_count | 56 |
| win_rate | 42.8571% |
| profit_factor | 0.6284 |
| max_drawdown | 3.7464% |
| open_positions | 0 |
| unrealized_pnl | 0 |

这组亏损是历史累计状态，不是本窗口新增亏损。本窗口从 `2026-07-01 20:00` 开始没有任何 paper trade，因此新增交易 PnL 为 `0`。

## 4. 决策统计

窗口内每 15 分钟扫描 12 个 symbol，共 `96 * 12 = 1152` 条决策：

| Action | 次数 | 占比 |
|---|---:|---:|
| NO_TRADE | 994 | 86.28% |
| WATCH | 158 | 13.72% |
| PROBE | 0 | 0.00% |
| DIRECT | 0 | 0.00% |

每个 symbol 各 `96` 次决策：

`BNBUSDT`、`XRPUSDT`、`SOLUSDT`、`TRXUSDT`、`HYPEUSDT`、`DOGEUSDT`、`XLMUSDT`、`ZECUSDT`、`XMRUSDT`、`CCUSDT`、`ADAUSDT`、`LINKUSDT`。

Top reasons：

| Reason | 次数 | 解释 |
|---|---:|---|
| FIB_PA_ARCHITECTURE_WEIGHTS | 1152 | 全窗口使用 Fib/PA 权重体系 |
| SIDE_THRESHOLD_OFFSET_LONG_10.00 | 357 | 多头阈值上调拦截较多 |
| SYMBOL_BLACKLISTED | 186 | 黑名单标的禁止交易 |
| SYMBOL_WATCH_ONLY | 152 | watch-only 标的只观察 |
| FIB_EXTENSION_EXHAUSTION_BLOCK | 102 | Fib 延伸耗尽拦截 |
| PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0 | 18 | PROBE RR 差 2 分 |
| PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0 | 10 | PROBE RR 差 4 分 |
| PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0 | 9 | PROBE Fib 差 3 分 |
| DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0 | 9 | DIRECT RR 差 2 分 |
| HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0 | 6 | 高 beta PROBE RR 差 3 分 |

原因族汇总：

| 原因族 | 次数 | 解释 |
|---|---:|---|
| SIDE_OFFSET | 357 | 多头侧阈值偏移是最大常规拦截 |
| SYMBOL_SCOPE | 342 | 黑名单、watch-only、observation-only 限制 |
| FIB_EXHAUSTION | 102 | Fib 延伸耗尽 |
| PROBE_BELOW_RR | 33 | 普通 PROBE 风险收益比不足 |
| HIGH_BETA_PROBE_BELOW | 17 | 高 beta PROBE 额外门槛不足 |
| PROBE_BELOW_FIB | 14 | PROBE Fib 位置不足 |
| DIRECT_BELOW_RR | 10 | DIRECT 风险收益比不足 |
| PROBE_BELOW_SCORE | 10 | 总分接近但低于 PROBE |
| PROBE_BELOW_PA | 1 | PA 结构不足 |

本窗口没有出现 `DAILY_TRADE_BUDGET_USED` 作为主要阻断原因。与上一窗口不同，这次不是日预算压制开仓，主要是准入门槛与 symbol 范围限制压制开仓。

## 5. 高分近失机会

窗口内 `score >= 80` 但仍被 WATCH / NO_TRADE 的候选共有 `27` 个。代表样本如下：

| 时间 CST | Symbol | Action | Score | RR | Fib | PA | CCI | EMA | 主要拦截 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 07-01 20:15 | SOLUSDT | WATCH | 83.30 | 2.0 | 18.0 | 21.0 | 10.0 | 14.3 | DIRECT / PROBE RR 不足 |
| 07-01 22:00 | SOLUSDT | WATCH | 83.09 | 3.5 | 9.0 | 21.0 | 14.0 | 17.59 | PROBE Fib 不足 |
| 07-01 23:00 | LINKUSDT | WATCH | 86.59 | 2.0 | 18.0 | 21.0 | 10.0 | 17.59 | PROBE RR 不足 |
| 07-02 00:00 | BNBUSDT | WATCH | 86.59 | 2.0 | 18.0 | 21.0 | 10.0 | 17.59 | PROBE RR 不足 |
| 07-02 00:00 | CCUSDT | WATCH | 85.69 | 2.0 | 18.0 | 21.0 | 10.0 | 16.69 | 高 beta RR 不足 |
| 07-02 00:30 | SOLUSDT | WATCH | 80.15 | 6.5 | 6.0 | 21.0 | 10.0 | 18.65 | PROBE Fib 不足 |
| 07-02 05:30 | XMRUSDT | NO_TRADE | 80.19 | 2.0 | 13.0 | 21.0 | 10.0 | 16.19 | SYMBOL_WATCH_ONLY |
| 07-02 12:45 | HYPEUSDT | WATCH | 85.19 | 2.0 | 18.0 | 21.0 | 10.0 | 16.19 | 高 beta RR 不足 |
| 07-02 12:45 | ADAUSDT | NO_TRADE | 83.09 | 3.5 | 9.0 | 21.0 | 14.0 | 17.59 | SYMBOL_WATCH_ONLY |
| 07-02 13:30 | CCUSDT | WATCH | 90.59 | 2.0 | 18.0 | 21.0 | 14.0 | 17.59 | 高 beta RR 不足 |
| 07-02 15:00 | XLMUSDT | WATCH | 89.69 | 6.5 | 18.0 | 21.0 | 10.0 | 16.19 | SYMBOL_OBSERVATION_ONLY |

这些近失机会说明：模型不是完全没有识别到高共振信号，而是绝大多数高分信号都卡在某一个硬门槛上，尤其是 RR、Fib、高 beta 附加门槛和 symbol 交易范围。

## 6. “一直没有开仓”的根因归因

### 6.1 一级归因：决策层零放行

`PROBE=0`、`DIRECT=0` 是本窗口最重要事实。没有动作进入可交易层，所以后续链路全部为空：

1. 没有 PROBE / DIRECT。
2. order draft / execution 审计全部未获批，`request=null`。
3. 没有 paper open。
4. 没有 open position。
5. 没有 TP / SL / breakeven / max hold 退出。

因此不要把“没有砍仓”或“没有开仓”归因到退出模块。本窗口没有可退出的仓位。

### 6.2 二级归因：防御门槛从止血变成频率瓶颈

上一轮修补的方向是正确的：高 beta、RR、Fib、追涨/延伸等防线明显减少了低质量 PROBE。但本窗口的副作用是所有候选都被压制。

典型结构：

- 总分高，Fib / PA / CCI / EMA 很漂亮，但 RR 只有 `2/8`，被拦。
- RR 很好，例如 `6.5/8`，但 Fib 只有 `6/18`，被拦。
- 高 beta 标的总分超过 `85`，但 RR 不满足高 beta 额外门槛，被拦。
- XMR、ADA、XLM 等出现高分，但被 watch-only / observation-only 限制。

结论：当前系统已经从“过滤不够”切到“过滤过强或样本池不够大”。这不是坏事，但它意味着下一阶段不能继续只靠加门槛解决问题。

### 6.3 三级归因：当前不是预算问题

上一窗口 `DAILY_TRADE_BUDGET_USED` 曾大量出现。本窗口 top reasons 中没有日预算阻断，且 order draft / execution 审计均因 action 不允许开仓而未获批，说明不是“预算满了导致本来能开的交易开不了”。

当前瓶颈更靠前：在预算检查之前，信号已经因为硬门槛、symbol scope 或 Fib exhaustion 被压回 NO_TRADE / WATCH。

### 6.4 四级归因：symbol universe 和交易权限限制影响频率

12 个 symbol 中，每个都扫描 96 次，但 `SYMBOL_BLACKLISTED=186`、`SYMBOL_WATCH_ONLY=152`、`SYMBOL_OBSERVATION_ONLY=4`。这说明相当一部分市场覆盖只用于观察，不参与交易。

高分样本里：

- `XMRUSDT score=80.19/84.59` 被 `SYMBOL_WATCH_ONLY` 拦截。
- `ADAUSDT score=83.09` 被 `SYMBOL_WATCH_ONLY` 拦截。
- `XLMUSDT score=89.69` 被 `SYMBOL_OBSERVATION_ONLY` 拦截。

如果目标是 24 小时 10 到 20 次开仓，单纯在 12 个 symbol 中保持大量 watch-only / observation-only，会天然压低可交易候选数。

### 6.5 五级归因：RR 门槛可能拦截了部分潜在盈利，但尚不能直接放松

高分近失中大量交易卡在 `RR=2/8`。这可能有两种解释：

1. 防线正确：这些都是过去导致亏损的弱边缘交易，继续拦截是正期望。
2. 防线过硬：部分高 PA / 高 Fib / 高 CCI 的信号虽然静态 RR 低，但短周期 MFE 足够，适合更快的分批止盈模型。

仅凭本窗口日志无法判断哪一种为真，因为没有真实开仓结果。需要对 `27` 个高分近失做假设入场 MFE/MAE 回放，才能决定是否设计 SCOUT 层或分 regime 放宽。

## 7. 从防御转向进攻的可行路径

### 路径 A：建立高分近失回放队列，先量化“被错杀”的机会

这是最优先的进攻准备，不会破坏现有防线。

建议把所有 `score >= 80` 且 action 为 WATCH / NO_TRADE 的候选写入 near-miss 数据集，字段包括：

- timestamp、symbol、side、score、action、reasons。
- Fib / PA / RR / CCI / EMA 组件分。
- long_chase_risk、long_overextension、fib_extension_exhaustion、data_health。
- 假设 entry 后 0.5h、1h、2h、4h 的 MFE / MAE。
- 是否先触及 TP1、TP2、SL、breakeven。

DeepSeek 评审重点：如果 `RR=2/8` 的高分近失在回放里 MFE 普遍不足，继续保持拦截；如果 MFE 明显高于 MAE，可考虑专门的快进快出 SCOUT 模式。

### 路径 B：新增 SCOUT / EXPLORATION 观察层，而不是直接放松 PROBE

PROBE 已经承担真实 dry-run 仓位。如果直接放松 PROBE，会把系统带回上一轮低质量交易溃败。

建议新增一个不影响主账户统计或极小仓位的 SCOUT 层：

- 触发条件：`score >= 84`，且只缺一个组件门槛。
- 禁止条件：高 beta 且 RR 不足、data_health degraded、long chase / overextension。
- 仓位：paper-only 标记，或 PROBE 名义本金的 `10% 到 20%`。
- 目的：收集 MFE/MAE，不以盈利为首要目标。
- 晋级规则：某 symbol / pattern 连续 N 次 SCOUT 的 MFE/MAE 和净期望达标后，再允许进入 PROBE。

这条路径把“扩大盈利点”拆成数据采集和仓位放大两步，避免为了频率牺牲风控。

### 路径 C：扩大可交易标的池，而不是降低核心门槛

本窗口显示，当前 12 个 symbol 的高质量可交易机会不足。要达到 10 到 20 次/24h，更合理的方式是扩大可交易样本池：

- 将 watch-only / observation-only 中表现稳定的 symbol 纳入小仓 dry-run 候选，例如 ADA、XLM。
- 对新增 symbol 先运行 3 到 7 天 WATCH_ONLY，统计近失频率、MFE/MAE、滑点风险。
- 避免把黑名单 symbol 直接解禁；黑名单应逐个复核原因。
- 高 beta 扩展必须更慢，保持 RR、CCI、EMA 和 Fib 的额外门槛。

这条路径的核心逻辑是：维持单笔质量，靠更多市场横截面提高频率。

### 路径 D：按 regime 差异化 RR，而不是统一放宽 RR

当前 RR 是最大硬门槛之一。可以研究但不应马上放松：

- 趋势延续 regime：高 EMA、CCI、PA，允许较低静态 RR，但要求更快 TP1 和更短超时。
- 震荡回归 regime：必须保持高 RR 和清晰 Fib 位置。
- 高 beta regime：RR 不能放松，甚至继续保持更严。
- 多头追涨 / overextension regime：继续禁止或只允许 SCOUT 观察。

任何 RR 放宽都必须通过 MFE/MAE 回放验证，不能由单个高分样本推动。

### 路径 E：把 offense 目标定义成“质量调整后的开仓数”

建议不要把 10 到 20 次/24h 作为唯一目标。更合理的进攻 KPI：

| KPI | 建议阈值 |
|---|---|
| 主 PROBE / DIRECT | 4 到 8 次/24h，先恢复频率 |
| SCOUT / observation | 10 到 30 次/24h，收集样本 |
| INITIAL_STOP_HIT 占比 | 低于 25% |
| cost breakeven timeout 占比 | 低于 30% |
| profit factor | 先稳定高于 1.1，再追求频率 |
| MFE/MAE 中位数 | MFE 必须明显高于 MAE |

先让系统有可解释的正期望，再逐步放大交易次数。

## 8. 建议下一步代码方向

本报告不改代码，但建议下一轮实现优先级如下：

1. 近失样本导出：将 `score >= 80` 且未开仓的 WATCH / NO_TRADE 写入独立 JSONL 或 CSV。
2. MFE/MAE 回放：对近失样本做假设入场回放，区分“正确拦截”和“错杀机会”。
3. SCOUT 层：只用于 dry-run / paper 观察，不直接进入真实执行。
4. symbol 晋级机制：watch-only symbol 通过回放和观察后，才能进入小仓 dry-run。
5. regime 标签：给 RR 放宽提供条件，而不是全局放宽。

暂不建议：

- 直接降低 HIGH_BETA PROBE 门槛。
- 直接把 RR 最低分从 4/8 放回 2/8。
- 为了凑 10 到 20 次/24h 解除黑名单。
- 在没有 MFE/MAE 证据前提高杠杆或名义本金。

## 9. DeepSeek 评审问题

1. 本窗口 `PROBE=0`、`DIRECT=0`，是否可以确认“无开仓”是准入层主动拦截，而非下单链路故障？
2. 当前防线是否已经从“止血必要”进入“信号饥饿”？判断标准应该看开仓数、近失数，还是 MFE/MAE？
3. 对 `27` 个 `score >= 80` 的近失候选，应优先回放哪些：RR 不足、Fib 不足、高 beta 不足，还是 watch-only 高分候选？
4. 是否同意新增 SCOUT / EXPLORATION 层，而不是直接放松 PROBE？
5. SCOUT 应该完全不计入交易 PnL，还是以极小 paper 仓位计入单独统计？
6. `RR=2/8` 但 Fib/PA/CCI/EMA 很强的候选，是否存在快进快出策略价值？需要哪些 MFE/MAE 阈值证明？
7. 对 `XLMUSDT score=89.69` 这类 observation-only 高分信号，是否应设计 symbol 晋级机制？
8. 为达到 10 到 20 次/24h，优先扩标的池还是扩策略类型？哪个更不容易引入过拟合？
9. 多头 `SIDE_THRESHOLD_OFFSET_LONG_10.00` 出现 357 次，是否说明多头阈值过度保守，还是当前市场多头追涨风险确实较大？
10. 从防御转进攻的第一阶段，目标应设为“主交易 4 到 8 次 + SCOUT 10 到 30 次”，还是继续坚持主交易 10 到 20 次？

## 10. 一句话结论

本窗口没有新增亏损，也没有任何开仓；“一直没有开仓”的根因是防御规则生效后，1152 条信号全部被压在 WATCH / NO_TRADE，主要瓶颈为 RR、Fib、高 beta 附加门槛、symbol scope 和 Fib exhaustion。下一阶段不应直接放松 PROBE，而应通过高分近失 MFE/MAE 回放、SCOUT 观察层和标的池晋级机制，把系统从“堵漏洞”稳妥转向“扩大盈利点”。
