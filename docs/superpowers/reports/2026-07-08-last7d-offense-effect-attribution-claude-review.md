# AI300 最近 7 天 Dry-Run 进攻态势执行效果归因报告

**用途:** 提交 Claude 复审  
**分析时间:** 2026-07-08  
**分析窗口:** 北京时间 2026-07-01 至 2026-07-08 19:15 左右  
**日志目录:** `logs/2026-07/2026-07-01/` 至 `logs/2026-07/2026-07-08/`  
**说明:** `2026-07-08` 不是完整自然日，最后一批可见日志写入约为北京时间 19:15。本文按可见日志聚合，结论偏向工程归因，不构成投资建议。

---

## 0. 结论摘要

最近 7 天“扩大盈利点”的执行效果不理想，核心不是订单链路故障，而是**新增优化主要提高了防御、纯度与可观测性，却没有真正恢复 PROBE 层吞吐，也没有让 SCOUT 层形成正期望样本。**

关键事实如下：

| 指标 | 最近 7 天可见日志 |
|---|---:|
| 总决策数 | 9272 |
| `PROBE` 决策 | 3 |
| `DIRECT` 决策 | 1 |
| 主交易开仓 | 4 |
| SCOUT_MICRO 开仓 | 6 |
| 主交易完整平仓 | 4 |
| SCOUT 完整平仓 | 6 |
| 主交易胜率 | 25.0% |
| SCOUT 胜率 | 33.3% |
| 主交易事件口径 PnL | -8.5478 USDT |
| SCOUT 事件口径 PnL | -1.7938 USDT |
| score >= 70 候选 | 1056 |
| score >= 80 候选 | 189 |
| score >= 85 候选 | 62 |

一句话归因：**系统从“会乱开仓”进化到了“会少量开仓和记录近失”，但尚未进化到“稳定筛出可盈利的新增进攻点”。主交易被 symbol/side/Fib/RR/elite 组合门持续压缩，SCOUT 虽有开火但命中率和样本量都不足。**

---

## 1. 数据与口径

### 1.1 数据源

本次只读分析使用以下文件：

- `logs/2026-07/YYYY-MM-DD/decisions.jsonl`
- `logs/2026-07/YYYY-MM-DD/near_misses.jsonl`
- `logs/2026-07/YYYY-MM-DD/paper_trades.jsonl`
- `logs/2026-07/YYYY-MM-DD/paper_summary.json`
- `logs/2026-07/YYYY-MM-DD/scout_micro/paper_trades.jsonl`
- `logs/2026-07/YYYY-MM-DD/scout_micro/paper_summary.json`
- `logs/2026-07/YYYY-MM-DD/summary.json`
- `configs/entry_chain.dry_run_fib_pa_v1.json`
- `docs/superpowers/plans/2026-07-01*` 至 `2026-07-07*`

### 1.2 重要口径风险

1. `paper_summary.json` 是累计账本状态，不是单日绩效。本文的 7 日 PnL 和胜率主要由 `paper_trades.jsonl` 事件重算。
2. `summary.json` 在 2026-07-07 之后才包含 Stage 0 新增的 `gate_rejections_by_layer`，早期窗口只能从 `decisions.jsonl` 的 reasons 反推。
3. `2026-07-08` 是未完整日，不能与前 7 个完整日志日等权比较。

---

## 2. 最近 7 天执行效果总览

### 2.1 按日开仓与结果

| 日志日 | 决策数 | 主交易开仓 | 主交易结果 | SCOUT 开仓 | SCOUT 结果 | near-miss |
|---|---:|---:|---|---:|---|---:|
| 2026-07-01 | 1152 | 1 | HYPE 初始止损，约 -6.16 | 0 | - | 0 |
| 2026-07-02 | 1152 | 1 | LINK 开仓，次日成本超时亏损 | 0 | - | 7 |
| 2026-07-03 | 1152 | 0 | LINK 平仓，约 -2.30 完整仓位 | 0 | - | 7 |
| 2026-07-04 | 1241 | 0 | - | 2 | XLM 一盈一亏，合计约 -0.40 | 14 |
| 2026-07-05 | 1334 | 0 | - | 2 | ZEC 两笔初始止损，约 -1.01 | 28 |
| 2026-07-06 | 1344 | 2 | BCH 一亏一盈，合计约 -0.09 | 1 | XLM targeted-long 初始止损，约 -0.54 | 23 |
| 2026-07-07 | 1299 | 0 | - | 0 | - | 16 |
| 2026-07-08 | 598 | 0 | - | 1 | XMR TP1 后保本，约 +0.16 | 5 |

### 2.2 完整交易明细

#### 主交易

| 时间 CST | symbol | side | score | 类型 | 结果 |
|---|---|---|---:|---|---:|
| 2026-07-01 09:00 | HYPEUSDT | SHORT | 83.19 | HIGH_BETA PROBE | `INITIAL_STOP_HIT`, -6.1561 |
| 2026-07-03 01:30 | LINKUSDT | SHORT | 72.00 | 低分 PROBE | `COST_BREAKEVEN_TIMEOUT`, 完整仓位约 -2.3034 |
| 2026-07-06 08:15 | BCHUSDT | SHORT | 72.75 | 低分 PROBE | `INITIAL_STOP_HIT`, -7.1539 |
| 2026-07-06 17:30 | BCHUSDT | SHORT | 90.30 | 高分 DIRECT/主力 | `TP1_HIT` 后 `BREAKEVEN_STOP_HIT`, +7.0657 |

主交易结论：**低分/降级 PROBE 是主要亏损来源；高分 BCH 证明退出管理有效，但样本只有 1 笔，不能承担 300-600 次/月的吞吐目标。**

#### SCOUT_MICRO

| 时间 CST | symbol | side | score | mission | 结果 |
|---|---|---|---:|---|---:|
| 2026-07-04 19:45 | XLMUSDT | SHORT | 83.30 | 早期 RR-gap SCOUT | TP1 后保本，约 +0.2043 |
| 2026-07-04 21:30 | XLMUSDT | SHORT | 90.69 | 早期 RR-gap SCOUT | `INITIAL_STOP_HIT`, -0.6051 |
| 2026-07-05 10:30 | ZECUSDT | SHORT | 87.75 | `NON_RR_HIGH_SCORE` | `INITIAL_STOP_HIT`, -0.5576 |
| 2026-07-06 07:00 | ZECUSDT | LONG | 90.59 | `NON_RR_HIGH_SCORE` | `INITIAL_STOP_HIT`, -0.4554 |
| 2026-07-07 05:00 | XLMUSDT | LONG | 90.20 | `TARGETED_LONG_OFFSET` | `INITIAL_STOP_HIT`, -0.5404 |
| 2026-07-08 16:15 | XMRUSDT | SHORT | 88.80 | `NON_RR_HIGH_SCORE` | TP1 后保本，约 +0.1605 |

SCOUT 结论：**SCOUT 已经能采样，但当前样本是 2 胜 4 负，且盈利样本都是小盈利，亏损样本以初始止损为主。它还没有成为可晋级的盈利发现层。**

---

## 3. 候选信号供给与拦截结构

### 3.1 分数供给并不少

| score 区间 | 数量 |
|---|---:|
| <70 | 8216 |
| 70-75 | 497 |
| 75-80 | 370 |
| 80-85 | 127 |
| 85-90 | 45 |
| >=90 | 17 |

最近 7 天至少有 `1056` 条 score >= 70 的候选，`189` 条 score >= 80，`62` 条 score >= 85。也就是说，问题不是完全没有评分供给，而是**这些供给被策略门压缩后，能真正转换为开仓的比例极低。**

### 3.2 最大拦截来源

| 拦截原因 | 次数 | 解释 |
|---|---:|---|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 2772 | LONG 侧 +10 偏移仍是最大过滤器 |
| `SYMBOL_BLACKLISTED` | 1319 | ZEC/XRP 等高分信号被黑名单阻断 |
| `SYMBOL_WATCH_ONLY` | 1243 | ADA/XMR 等观察池高分信号不能进主交易 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 856 | Fib 延展衰竭过滤大量信号 |
| `PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0` | 117 | PROBE 主要卡在 Fib 位置 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 85 | RR 几何仍是 PROBE 瓶颈 |
| `DAILY_TRADE_BUDGET_USED` | 55 | 预算不是全局主因，只在 7 月 6 日显著 |
| `SYMBOL_DAILY_TRADE_BUDGET_USED` | 37 | 同上 |

### 3.3 高分信号为什么没有转化

score >= 85 的拦截原因中，排名靠前的是：

| 高分拦截原因 | 次数 |
|---|---:|
| `SYMBOL_BLACKLISTED` | 13 |
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 13 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 13 |
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 12 |
| `SYMBOL_WATCH_ONLY` | 12 |
| `HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0` | 6 |

这说明高分 near-miss 的主要死因仍是三类：

1. **标的政策:** 黑名单、watch-only、observation-only。
2. **方向政策:** LONG offset。
3. **结构质量:** RR/Fib 几何不足。

这些都不是订单执行问题，而是准入层主动拦截。

---

## 4. 最近 7 天新增优化点及实际效果

### 4.1 2026-07-01: Direct -> Probe recheck hardening

**新增优化点**

- 修复 HIGH_BETA `DIRECT -> PROBE` 降级后绕过 PROBE 条件的问题。
- 提高 dry-run Fib/PA 配置透明度。
- 加入预算诊断。

**实际效果**

- 该优化针对 HYPEUSDT 83.19 分 HIGH_BETA PROBE 止损暴露出的漏洞。
- 修复后，高 beta 和降级路径更安全，但同时进一步压缩 PROBE 输出。

**归因**

这是必要防御，不是盈利扩张。它减少“错误开仓”，但不会增加“正确开仓”。

### 4.2 2026-07-02: SCOUT near-miss 记录与 MFE/MAE 回放

**新增优化点**

- 新增 `near_misses.jsonl`。
- summary 记录 near-miss 数量和原因。
- 新增离线 MFE/MAE 回放脚本。

**实际效果**

- 近失信号开始可见，7 天 near-miss 数量从 0 提升到可分析。
- 但最初只是观察层，没有增加交易。

**归因**

它解决了“看不见错过了什么”，但没有解决“如何把错过变成正期望开仓”。

### 4.3 2026-07-04: SCOUT micro + PROBE 质量门

**新增优化点**

- 关闭低质量 PROBE 后门：趋势/CCI 质量门、低分质量 veto。
- XLMUSDT 进入 SCOUT micro，50 USDT、1x。
- targeted LONG near-miss 打标签。

**实际效果**

- 主交易更干净，但 7 月 4 日主交易为 0。
- XLM 两笔 RR-gap SCOUT 一盈一亏，合计约 -0.40。
- 低成本验证了 RR-gap 模式不稳定。

**归因**

这一步是“止损式进攻实验”：成本低，情报有价值，但没有带来盈利扩张。

### 4.4 2026-07-05: SCOUT 火力侦察网

**新增优化点**

- SCOUT 增加 mission 配置。
- 增加 `NON_RR_HIGH_SCORE`、`TARGETED_LONG_OFFSET`、`SCOUT_ONLY_HIGH_SCORE`。
- 加入 2 小时同向冷却与 6 小时初始止损冷却。
- XMR/ZEC 等受限标的进入 SCOUT_ONLY 测试。

**实际效果**

- ZEC 两笔 `NON_RR_HIGH_SCORE` 均初始止损，合计约 -1.01。
- 说明“黑名单/受限标的高分”不能直接等同于可交易 alpha。

**归因**

SCOUT 火力确实扩大了，但前两个重要样本打在 ZEC 上，反馈为负。这不是执行故障，而是标的/模式假设被市场否定。

### 4.5 2026-07-06: 主交易精兵门 + 动态 targeted-long

**新增优化点**

- 对 PROBE 增加 `elite_probe_enabled`。
- `score < 75` 禁止主账本 PROBE。
- 强结构门：PA/Fib 或趋势-结构补偿。
- targeted-long 授权池从单点扩到 LINK/LAB/HYPE/DOGE/CC/XLM。
- ADA 进入 SCOUT_ONLY，ZEC 从当前 SCOUT 池移除。

**实际效果**

- 7 月 7 日主交易为 0；7 月 8 日截至 19:15 主交易仍为 0。
- Stage 0 新摘要显示 7 月 8 日 `probe` 层拒绝 58 次，但更大的仍是 `symbol_policy=323`, `side_policy=200`, `fib_policy=147`。
- targeted-long 只有 XLM 一笔实际开仓，结果初始止损。

**归因**

精兵门提升主账本纯度，但它不是吞吐引擎。动态 targeted-long 的授权池扩大了，但真正同时满足 score、PA、RR、symbol、冷却、data health 的样本仍少。

### 4.6 2026-07-07: Stage 0 PROBE 诊断

**新增优化点**

- `summary.json` 新增 `gate_rejections_by_layer`。
- 新增 `dry_run_assumptions`。
- 新增 `latest_portfolio_exposure`。
- 明确 `net_beta_exposure_model=not_configured`。

**实际效果**

- 诊断可观测性显著提升。
- 7 月 7 日、7 月 8 日都显示组合敞口不是堵点：`portfolio=0`，open positions 为 0。

**归因**

这是定位工具，不是进攻规则。它让问题更清楚：当前堵点在 symbol/side/Fib/PROBE 质量路径，不在仓位槽位或组合敞口。

---

## 5. 为什么“扩大盈利点”仍未达理想效果

### Finding 1: PROBE 没有恢复为吞吐层

**Evidence**

- 9272 条决策中，`PROBE=3`, `DIRECT=1`。
- 7 日主交易只有 4 笔。
- score >= 70 有 1056 条，但开仓转化率约 `4 / 1056 = 0.38%`。

**Impact**

如果目标仍是 300-600 次/月，当前主交易外推只有约 15-20 次/月级别；加上 SCOUT 也远低于目标。

**Root Cause**

最近 7 天的优化主要在关闭漏洞和提高质量门；PROBE 仍被设计成“更安全的主交易”，而不是“低仓位、可验证、可走量的中间层”。

### Finding 2: 主交易亏损集中在低分/降级 PROBE

**Evidence**

- HYPE 83.19 HIGH_BETA PROBE 初始止损。
- LINK 72.00 低分 PROBE 成本超时亏损。
- BCH 72.75 低分 PROBE 初始止损。
- BCH 90.30 高分主力信号盈利。

**Impact**

精兵化方向是对的，但它带来的自然结果是主账本频率下降。若不建立独立 PROBE 吞吐逻辑，就会继续在“高质量但低频”和“低质量但会亏”之间摇摆。

**Root Cause**

低分 PROBE 在 7 月 6 日前仍能进入主账本；修复后主交易明显变少，但这只是清理坏交易，不是生成好交易。

### Finding 3: SCOUT 扩张验证到的多是负反馈

**Evidence**

- SCOUT 6 笔，2 胜 4 负。
- ZEC 两笔高分 `NON_RR_HIGH_SCORE` 全部初始止损。
- XLM targeted-long 90.2 分初始止损。
- 最新累计 `scout_micro/paper_summary.json` 显示 `profit_factor=0.16897`, `win_rate=33.33%`, `realized_pnl=-1.7938`。

**Impact**

SCOUT 当前还不能作为“扩大盈利点”的证据，只能作为“否定若干假设”的实验层。

**Root Cause**

SCOUT 的 mission 仍在测试被主规则拒绝的信号，这类信号本来就可能带有结构性缺陷。高分不能抵消标的风险、RR 缺口、LONG offset 风险和初始止损脆弱性。

### Finding 4: 高分近失主要集中在不可交易政策与结构缺口

**Evidence**

score >= 85 的主要 blocker 是：

- 黑名单 13 次；
- watch-only 12 次；
- LONG offset 12 次；
- RR gap 多项合计超过 30 次。

**Impact**

直接放松主交易会重新打开前几轮刚修好的风险口。将这些高分近失全部放入主账本不是合理路径。

**Root Cause**

当前高分 near-miss 不是“只差一点就完美”，而是“常常差在交易许可或核心结构项”。这类信号需要 mission 级别验证，而不是直接晋级。

### Finding 5: LONG offset 仍是最大压力点，但唯一实仓样本为负

**Evidence**

- `SIDE_THRESHOLD_OFFSET_LONG_10.00` 7 天出现 2772 次。
- near-miss 里该原因出现 34 次。
- 唯一 targeted-long SCOUT 开仓为 XLMUSDT LONG 90.2，初始止损。

**Impact**

目前数据不支持直接降低 LONG offset。它可能过严，但唯一微仓反馈没有证明“错杀优质 LONG”。

**Root Cause**

LONG offset 的压力很大，但符合 SCOUT 条件的 LONG 样本少；样本少又首笔负反馈，使得它仍停留在待验证状态。

### Finding 6: 组合级敞口不是当前瓶颈

**Evidence**

Stage 0 summary：

- 7 月 7 日：`portfolio=0`, `open_position_count=0`
- 7 月 8 日：`portfolio=0`, `open_position_count=0`
- `max_total_exposure_pct=1.6`, `max_same_direction_exposure_pct=1.1`
- `net_beta_exposure_model=not_configured`

**Impact**

当前不是仓位槽位被占满，也不是组合敞口挡住机会。提高并发数、仓位或杠杆不会解决开仓稀少，反而会放大低命中率样本的亏损。

**Root Cause**

瓶颈在信号准入层，不在资金利用层。

---

## 6. 对“最近 7 天新增优化点未达理想效果”的总归因

### 6.1 优化方向没有错，但优化类型偏防御

最近 7 天新增优化的性质大致是：

| 优化类型 | 代表改动 | 对盈利扩张的作用 |
|---|---|---|
| 漏洞修复 | HIGH_BETA DIRECT->PROBE recheck | 减少错误交易 |
| 质量门 | PROBE trend/CCI、elite probe | 减少低质量交易 |
| 观测层 | near_miss、MFE/MAE、Stage0 summary | 提高可解释性 |
| 微仓实验 | SCOUT_MICRO | 低成本验证假设 |
| 动态任务池 | targeted-long 授权池 | 扩大采样面 |

这些优化共同提高了纪律性，但它们不是“PROBE 吞吐重建”。因此出现了看似矛盾的结果：**系统更健康，但盈利点没有明显扩大。**

### 6.2 当前进攻架构仍缺一个真正的中间层

现在的三层实际表现更像：

```text
DIRECT/精兵: 很少，但一旦高分可能有效
PROBE: 被质量门持续压缩，无法承担走量
SCOUT: 能采样，但样本小、胜率低、尚未证明正期望
```

缺失的是：

```text
小仓位、低杠杆、独立绩效统计、目标 5-10 笔/日的 PROBE_TIER
```

它应介于主账本精兵和 SCOUT 微仓之间，用来测试 score 72-85 的可交易模式，而不是让所有中低分信号直接进主账本或全部留在 WATCH。

### 6.3 当前最不该做的是直接加杠杆/仓位

最近 7 天主交易胜率 25%，SCOUT 胜率 33.3%。在这个命中率下，提高仓位/杠杆只会加速亏损。  
当前应先解决：

1. 哪些 score 72-85 模式可低仓位验证；
2. 哪些 near-miss mission 应继续、暂停或收紧；
3. 哪些 symbol policy 需要滚动复核，而不是永久凭单窗口调整。

---

## 7. 建议给 Claude 复审的问题

1. **是否同意“PROBE 没有恢复为吞吐层”是当前最大结构性瓶颈？**  
   如果同意，下一步应设计独立 `PROBE_TIER`，还是继续保持主账本精兵化、只扩大 SCOUT？

2. **低分 PROBE 的处理是否应从“主账本禁止”改为“进入小仓位 PROBE_TIER 验证”？**  
   最近亏损显示低分直接进主账本不合理，但完全禁止也会让吞吐归零。

3. **SCOUT 的哪些 mission 应暂停？**  
   ZEC `NON_RR_HIGH_SCORE` 连续两笔止损，XLM targeted-long 止损；是否应暂停这些 mission，保留 XMR/ADA 的 watch-only high-score 测试？

4. **LONG offset 是否继续保持主规则不变，只扩大观察？**  
   当前唯一 targeted-long 微仓为负，是否足以支持“不下调 offset”？

5. **是否需要把 symbol policy 从静态名单升级为滚动评分面板？**  
   黑名单/watch-only 是高分拦截大头，但 ZEC 的负反馈也证明不能简单放开。

6. **目标 300-600 次/月是否应拆成阶段目标？**  
   当前主交易 + SCOUT 外推远低于目标，是否应先设 `50-100 次/月小仓位有效样本` 作为下一阶段？

---

## 8. 下一阶段建议

### P0: 不调整仓位/杠杆

在主交易 25% 胜率、SCOUT 33.3% 胜率下，不建议提升仓位、杠杆或并发。

### P1: 设计独立 `PROBE_TIER` 观察层

建议将 score 72-85 的候选从主账本中拆出：

- 固定 1x-2x；
- 小仓位；
- 单独账本；
- 不占 DIRECT 主账本统计；
- 要求 RR/Fib 至少正向，但不使用 DIRECT/elite 同等门槛；
- 目标是积累 50 笔后评估 PF、MDD、胜率、MFE/MAE。

### P2: SCOUT mission 做停启清单

建议：

- 暂停 ZEC 相关开仓 mission，仅记录 near-miss。
- XLM targeted-long 保留观察但提高样本门槛，避免单一 RR 缺口反复试错。
- XMR 仅有一笔正反馈，继续小样本，但不能晋级。
- ADA watch-only high-score 继续观察，等待实际样本。

### P3: 建立 7-14 天滚动 symbol 面板

每个 symbol 输出：

- near-miss 数量；
- score >= 85 数量；
- RR/Fib 非零比例；
- SCOUT 交易数；
- SCOUT PF / win rate / MFE / MAE；
- 初始止损次数；
- 是否建议保留、暂停、晋级。

### P4: 把 Stage 0 诊断延伸到每日报告

每天固定输出：

- `gate_rejections_by_layer`;
- PROBE 专属拦截 top；
- DIRECT 专属拦截 top；
- 高分 blocker top；
- 组合敞口；
- 成本假设；
- 净 beta 是否仍未配置。

---

## 9. 最终判断

最近 7 天的优化没有失败，但它们完成的是**防御修复、样本采集和问题显影**，不是盈利扩张本身。

真正不理想的点有三个：

1. **主交易吞吐仍接近枯竭。** 4 笔/7 天远低于目标，且低分 PROBE 仍贡献主要亏损。
2. **SCOUT 仍未证明正期望。** 6 笔、2 胜 4 负，亏损样本多为初始止损。
3. **高分供给被拦截在 symbol/side/RR/Fib 政策层。** 直接放松会伤害防御，继续不动又无法扩张。

因此，下一步不应是直接放宽主防线，也不应是加杠杆仓位，而应是建立一个**独立、低风险、可统计的 PROBE_TIER 吞吐验证层**，同时对 SCOUT mission 做停启管理。这样才能把“扩大盈利点”从概念推进到可验证的交易产能。
