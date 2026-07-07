# AI300 Dry-Run 进攻态势执行效果归因报告

**用途:** 提交 DeepSeek 复审  
**分析窗口:** 北京时间 2026-07-05 11:00:00 至 2026-07-06 19:00:05  
**日志目录:** `logs/2026-07/2026-07-05/`, `logs/2026-07/2026-07-06/`  
**策略状态:** 防御规则仍有效；主交易恢复少量开仓；SCOUT_MICRO 已启动但主要集中测试 ZEC，未形成预期的多路侦察网。

---

## 1. 核心结论

本窗口“扩大盈利点”的进攻态势已经开始执行，但效果仍不理想。根因不是数据源、预算或下单链路故障，而是：

1. **主交易恢复开火，但第一笔仍是最低合格线附近的 PROBE，开仓后初始止损。**  
   BCHUSDT SHORT `score=72.75` 于 2026-07-06 08:15 开仓，10:15 初始止损，单笔总净损约 `-7.15 USDT`。它不是完全劣质信号，RR/EMA/CCI 均过线，但它仍属于“刚过主交易准入”的最低合格样本。进攻期如果把这类信号当主火力，会继续消耗账户。

2. **真正高质量的主交易信号出现得更晚，但已被前一笔低分亏损改变了交易节奏。**  
   BCHUSDT 11:30 出现 `score=91.70` 的高分 SHORT near-miss，却因 `SYMBOL_POST_INITIAL_STOP_COOLDOWN` 被拦截。17:30 再次开出 BCHUSDT SHORT `score=90.30`，截至最新日志仍持仓，账面未实现亏损约 `-4.50 USDT`。这说明防御规则有效，但也暴露出一个问题：低分先手开仓可能消耗同 symbol 当日风险预算和冷却窗口，压制后续更优信号。

3. **SCOUT_MICRO 有运行，但火力投放与 near-miss 分布错位。**  
   本窗口 36 条 near-miss 中，`TARGETED_LONG_OFFSET` 有 15 条，分布在 LINK/HYPE/DOGE/LAB；但配置中定向 LONG SCOUT 只允许 `CCUSDT`，而本窗口没有 CCUSDT 定向 LONG near-miss。因此最需要验证的 LONG offset 压制问题，并没有被微仓测试。

4. **ZECUSDT 的 `NON_RR_HIGH_SCORE` / scout-only 黑名单测试初步表现较差。**  
   窗口内 ZEC scout 相关两次平仓均为 `INITIAL_STOP_HIT`：一笔是窗口前开仓、窗口内平仓的 SHORT，另一笔是窗口内 07:00 开仓、07:30 止损的 LONG。SCOUT 账本累计 `profit_factor=0.1262`, `win_rate=25%`，说明当前 ZEC 高分测试不能作为放宽黑名单的证据。

5. **最大瓶颈已从“完全不开枪”转为“开枪结构不够精确”。**  
   决策链路健康，预算不是主因；问题在于主交易仍允许最低合格 PROBE 开火，而 SCOUT 的实验矩阵没有覆盖到最多、最值得验证的 near-miss 区域。

一句话归因：**防御城墙还在，进攻也开始了，但主力第一枪打在最低合格信号上，侦察火力又打在 ZEC 单点，未覆盖 LONG offset 和观察池高分信号这两个真正的扩利方向。**

---

## 2. 运行链路健康性确认

### 2.1 数据范围

| 指标 | 结果 |
|---|---:|
| 决策行数 | 1806 |
| 扫描周期估算 | 129 |
| 覆盖 symbol | 14 |
| near-miss | 36 |
| gate rejection | 1804 |
| order draft | 1964 |
| 主账本事件 | 3 |
| SCOUT 账本事件 | 3 |
| 最新日志时间 | 2026-07-06 19:00:05 CST |

覆盖 symbol：

```text
ADAUSDT, BCHUSDT, BNBUSDT, CCUSDT, DOGEUSDT, HYPEUSDT, LABUSDT,
LINKUSDT, SOLUSDT, TRXUSDT, XLMUSDT, XMRUSDT, XRPUSDT, ZECUSDT
```

### 2.2 决策动作分布

| action | 次数 |
|---|---:|
| `NO_TRADE` | 1612 |
| `WATCH` | 192 |
| `PROBE` | 1 |
| `DIRECT` | 1 |

本窗口不是上一轮的“0 主交易”，而是少量恢复开仓：1 笔 PROBE、1 笔 DIRECT。

### 2.3 执行链路正常

`order_drafts.jsonl` 统计：

| approved | 次数 |
|---|---:|
| `true` | 2 |
| `false` | 1962 |

未批准原因几乎全部为：

```text
entry chain action does not allow live order draft
```

这说明系统在准入层没有给出交易动作时，执行层正确拒绝订单；当准入层给出 `PROBE/DIRECT` 时，也确实生成了主账本开仓。因此问题不在订单链路。

### 2.4 预算不是主要瓶颈

`DAILY_TRADE_BUDGET_USED` 仅出现 5 次。决策 metadata 中可见：

- `dynamic_limit` 覆盖 `2..15` 和 `27..42`；
- `used_today` 仅为 `0/1/2`；
- `current_volatility_scale` 范围约 `0.1` 到 `3.7532`。

因此本窗口交易少，不是因为日预算长期卡死。

---

## 3. 主交易表现

### 3.1 已发生主交易

| 时间 CST | 事件 | symbol | side | score | 杠杆 | 名义本金 | 结果 |
|---|---|---|---|---:|---:|---:|---|
| 2026-07-06 08:15 | `PAPER_OPEN` | BCHUSDT | SHORT | 72.75 | 3x | 489.27 | 开仓 |
| 2026-07-06 10:15 | `PAPER_CLOSE` | BCHUSDT | SHORT | - | 3x | - | `INITIAL_STOP_HIT`, net `-6.66`，含入场成本约 `-7.15` |
| 2026-07-06 17:30 | `PAPER_OPEN` | BCHUSDT | SHORT | 90.30 | 5x | 1955.66 | 截至 19:00 仍持仓，未实现约 `-4.50` |

最新 `paper_positions.json` 中 BCHUSDT SHORT：

| 字段 | 值 |
|---|---:|
| entry_price | 238.16 |
| last_price | 238.47 |
| stop_price | 240.6445 |
| tp_prices | 235.1786 / 233.1911 / 230.7066 |
| hold_bars | 5 |
| remaining_fraction | 1.0 |
| unrealized_pnl | -4.5038 |

### 3.2 第一笔 BCH PROBE 的问题

第一笔 BCHUSDT SHORT 决策：

| 组件 | 分数 |
|---|---:|
| cci_momentum_quality | 10.0 / 14 |
| fibonacci_location | 13.0 / 18 |
| flow_cvd_confirmation | 18.0 / 18 |
| price_action_structure | 12.0 / 22 |
| risk_reward_geometry | 6.5 / 8 |
| trend_ema_context | 13.25 / 20 |
| total score | 72.75 |

它通过了当前 `probe_conditions`：

- `min_score=72`
- `min_fib_score=12`
- `min_pa_score=10`
- `min_rr_score=4`
- `trend_or_cci` 组合门
- `low_score_quality_veto`

所以这不是代码短路，而是**策略准入定义允许了“最低合格 PROBE”**。问题在于：进攻阶段我们需要的是“精兵”，而不是所有刚过线的 PROBE 都参与主账本。

特别值得注意的是：该信号得分主要靠 RR、CVD、EMA/CCI 达标，PA 只有 `12/22`，Fib 也只有 `13/18`，属于结构刚过线，不是强结构。2 小时后初始止损，说明该类“最低合格但非强结构”的 PROBE 仍容易成为亏损入口。

### 3.3 低分先手消耗了后续更优机会

第一笔 BCH 止损后，同 symbol 出现了一个更强 near-miss：

| 时间 CST | symbol | side | score | reason | 核心分 |
|---|---|---|---:|---|---|
| 2026-07-06 11:30 | BCHUSDT | SHORT | 91.70 | `SYMBOL_POST_INITIAL_STOP_COOLDOWN` | Fib 18, PA 21, RR 5, EMA 15.7, CCI 14 |

这条高分信号被 4 小时 post-initial-stop cooldown 拦截。冷却规则本身是合理的，因为它防止同 symbol 连续止损。但从进攻效果看，**低分 first shot 触发止损后，反而把后续 91.70 的强信号锁在门外**。

这提出一个需要复审的问题：  
是否应对 `score < 75` 的主交易信号设置更严格的主账本准入，避免它们抢占 symbol 的后续更高质量交易窗口？

---

## 4. SCOUT_MICRO 表现

### 4.1 本窗口 SCOUT 事件

| 时间 CST | 事件 | symbol | side | mission | score | 结果 |
|---|---|---|---|---|---:|---|
| 2026-07-05 12:30 | `PAPER_CLOSE` | ZECUSDT | SHORT | 旧仓 | - | `INITIAL_STOP_HIT`, net `-0.5076` |
| 2026-07-06 07:00 | `PAPER_OPEN` | ZECUSDT | LONG | `NON_RR_HIGH_SCORE` | 90.59 | 开仓 |
| 2026-07-06 07:30 | `PAPER_CLOSE` | ZECUSDT | LONG | `NON_RR_HIGH_SCORE` | - | `INITIAL_STOP_HIT`, net `-0.4054` |

最新 `scout_micro/paper_summary.json`：

| 指标 | 值 |
|---|---:|
| trade_count | 4 |
| realized_pnl | -1.4138 |
| profit_factor | 0.1262 |
| win_rate | 25% |
| open_positions | 0 |

### 4.2 ZEC 测试的含义

ZECUSDT 是黑名单标的，同时在 `scout_micro_scout_only_symbols` 中。窗口内 07:00 的 LONG 开仓具备高分：

| 组件 | 分数 |
|---|---:|
| total score | 90.59 |
| Fib | 18 |
| PA | 21 |
| RR | 2 |
| EMA | 17.59 |
| CCI | 14 |

虽然总分极高，但 RR 只有 `2/8`，且 30 分钟后初始止损。这给出的初步结论是：

- ZEC 的黑名单/受限状态暂时不能解除；
- `NON_RR_HIGH_SCORE` 不能仅凭总分和强动能放行；
- scout-only 任务需要更明确地区分“非 RR 高分”和“真正满足 PROBE 组件最低分”的高分。

### 4.3 SCOUT 火力覆盖错位

本窗口 near-miss 共 36 条，其中 `TARGETED_LONG_OFFSET` 15 条，分布如下：

| symbol | TARGETED_LONG_OFFSET 数量 |
|---|---:|
| LINKUSDT | 7 |
| LABUSDT | 4 |
| HYPEUSDT | 2 |
| DOGEUSDT | 2 |

但当前配置：

```json
"scout_micro_symbols": ["XLMUSDT", "CCUSDT", "XMRUSDT", "ZECUSDT"],
"scout_micro_targeted_long_symbols": ["CCUSDT"]
```

结果是：本窗口真正出现的定向 LONG offset 高分候选，全部不在 `scout_micro_targeted_long_symbols` 中；而唯一允许定向 LONG 微仓的 `CCUSDT`，本窗口没有对应 near-miss。  

因此，上一轮“火力侦察网”的意图没有完全落地：**配置上允许了 CC 定向 LONG，但实际市场给出的可侦察目标在 LINK/LAB/HYPE/DOGE。**

---

## 5. Near-Miss 结构

### 5.1 拒绝原因分布

| 拒绝原因 | 次数 |
|---|---:|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 597 |
| `SYMBOL_BLACKLISTED` | 238 |
| `SYMBOL_WATCH_ONLY` | 234 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 162 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 19 |
| `SYMBOL_POSITION_ALREADY_OPEN` | 13 |
| `PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0` | 12 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0` | 12 |
| `DAILY_TRADE_BUDGET_USED` | 5 |

按问题族聚合：

| 问题族 | 次数 |
|---|---:|
| LONG offset | 597 |
| blacklist | 238 |
| watch-only | 234 |
| Fib exhaustion | 162 |
| RR / risk reward | 43 |
| Fib location | 16 |
| score minimum | 15 |
| position already open | 13 |
| CCI | 6 |
| PA | 5 |
| daily budget | 5 |

### 5.2 高分 near-miss 示例

| 时间 CST | symbol | side | score | reason | 观察 |
|---|---|---|---:|---|---|
| 2026-07-06 18:00 | ADAUSDT | SHORT | 93.15 | `SYMBOL_WATCH_ONLY` | Fib 18, PA 21, RR 3.5, EMA 18.65, CCI 14 |
| 2026-07-06 11:30 | BCHUSDT | SHORT | 91.70 | `SYMBOL_POST_INITIAL_STOP_COOLDOWN` | 低分 BCH 止损后出现的强信号 |
| 2026-07-06 02:00 | LABUSDT | LONG | 90.69 | `SIDE_THRESHOLD_OFFSET_LONG_10.00` + high-beta RR gap | 定向 LONG，但不在 SCOUT 微仓目标 |
| 2026-07-06 16:45 | HYPEUSDT | SHORT | 90.69 | DIRECT/HIGH_BETA RR gap | 高 beta 高分但 RR 缺口 |
| 2026-07-06 07:15 | ZECUSDT | LONG | 90.59 | `SYMBOL_BLACKLISTED` | 与 ZEC scout 测试相关，随后止损 |
| 2026-07-05 22:45 | LINKUSDT | LONG | 86.10 | `SIDE_THRESHOLD_OFFSET_LONG_10.00` + RR gap | 定向 LONG 标签，但不在 SCOUT 微仓目标 |

这些 near-miss 说明机会并非完全没有，但结构分为三类：

1. **观察池高分 SHORT:** ADA 等 `WATCH_ONLY` 标的出现多个 85+ 到 93+ 的 SHORT。
2. **定向 LONG offset 高分:** LINK/LAB/HYPE/DOGE 出现多条被 LONG offset 拦截的高分候选。
3. **高分 RR gap:** HYPE/ZEC 等总分很高，但 RR 几何不足，继续证明 RR 防线必要。

---

## 6. 归因层级

### 一级归因：进攻火力开始恢复，但主交易质量分层仍不够细

上一轮目标是从“堵漏洞”转入“扩大盈利点”。本窗口确实恢复了主交易开仓，但第一笔开在 `score=72.75` 的最低合格 PROBE 上，并迅速初始止损。  

这说明当前 `PROBE` 只有“是否合格”，没有进一步分成：

- 主账本可开火的强 PROBE；
- 只允许 SCOUT 的弱 PROBE；
- 需要继续 WATCH 的最低合格信号。

在 dry-run 里可以承担试错，但如果目标是尽快形成正期望，主交易最好只承接强 PROBE/DIRECT，最低合格信号应转入 SCOUT 或观察层。

### 二级归因：冷却规则有效，但会放大低质量 first shot 的机会成本

BCHUSDT 10:15 初始止损后，11:30 出现 `score=91.70` 高质量 SHORT，但被 `SYMBOL_POST_INITIAL_STOP_COOLDOWN` 拦截。  

冷却规则不是问题；问题是冷却规则触发源来自一笔 `72.75` 的低分 PROBE。即：**低分交易不仅亏钱，还占用了 symbol 冷却窗口，导致后续更强信号无法被主账本验证。**

### 三级归因：SCOUT 矩阵配置与真实 near-miss 分布不匹配

实际近失数据中，定向 LONG offset 候选集中在 LINK/LAB/HYPE/DOGE；配置只允许 CCUSDT 做 targeted-long 微仓。  

因此，SCOUT 层不是没有启动，而是没有采到本窗口最需要的数据。它采到的是 ZEC scout-only 高分测试，而不是 LONG offset 是否过度保守这个核心问题。

### 四级归因：ZEC scout-only 测试给出负反馈

ZEC 作为黑名单/受限标的，本窗口用 SCOUT_MICRO 测试后继续初始止损。  

这不是坏事，它以极小成本告诉我们：ZEC 至少不能因为“高总分”就解除限制。后续若继续测试，应要求 RR 达标，或把 ZEC 从 `NON_RR_HIGH_SCORE` 任务中移除。

### 五级归因：观察池高分机会未进入微仓闭环

ADAUSDT 多次出现 85+ 至 93+ 的 `SYMBOL_WATCH_ONLY` SHORT，其中 18:00 达到 `93.15`。但当前 `scout_micro_symbols` 不包含 ADA。  

如果扩大利润点的优先路径是“扩标的池而非放松规则”，那么 ADA 这类观察池高分 SHORT 应进入 SCOUT_ONLY / SCOUT_MICRO 的评估名单，否则观察池只会持续产生日志证据，不能形成可量化的交易样本。

---

## 7. 需要提交 DeepSeek 复审的问题

1. **是否应把 `score < 75` 的 PROBE 从主交易层降为 SCOUT 或 WATCH？**  
   BCHUSDT `72.75` 虽然通过所有最低条件，但止损后又压制了同 symbol 的 `91.70` 高分机会。是否应该新增规则：`75 <= score < 82` 只能在 Fib/PA 均强结构时主交易，否则转入 SCOUT？

2. **是否应给 PROBE 增加“强结构门”，而不是继续只看最低组件分？**  
   例如主交易 PROBE 要求 `price_action_structure >= 15` 或 `fib + pa >= 34`；低于该门槛但其他项优秀的信号进入 SCOUT。

3. **BCHUSDT 是否应被标记为“低分 first shot 风险”案例？**  
   需要复盘 08:15 这笔止损和 11:30 高分 near-miss 的 MFE/MAE。若 11:30 信号后续表现明显更优，说明主交易应等待更强确认。

4. **SCOUT targeted-long 是否应从 CC 单一 symbol 扩展为任务池？**  
   本窗口 `TARGETED_LONG_OFFSET` 实际分布在 LINK/LAB/HYPE/DOGE。是否应配置为 `scout_micro_targeted_long_symbols = ["LINKUSDT", "LABUSDT", "HYPEUSDT", "DOGEUSDT", "CCUSDT"]`，但保持 50 USDT / 1x / 独立冷却？

5. **ADAUSDT 是否应进入 `SCOUT_ONLY`？**  
   ADA 多次高分 SHORT 被 `SYMBOL_WATCH_ONLY` 拦截，最高 `93.15`。若目标是扩标的池，ADA 可能比继续测试 ZEC 更值得进入 SCOUT。

6. **ZECUSDT 是否应暂停 `NON_RR_HIGH_SCORE` 微仓任务？**  
   当前 ZEC scout-only 已连续给出初始止损负反馈。是否改为：ZEC 只记录 near-miss，不开微仓；或要求 RR 分数必须 `>=4/8` 才允许 scout-only？

7. **LONG offset 是否应保持主交易不变，但扩大 SCOUT 采样？**  
   当前主交易不应直接下调 `SIDE_THRESHOLD_OFFSET_LONG_10.00`。但可以扩大定向 LONG SCOUT，以回答 offset 是否过度保守。

---

## 8. 建议行动计划

### 第一阶段：主交易精兵化

1. **收紧低分 PROBE 主账本准入。**  
   建议把 `score < 75` 的 PROBE 默认降为 SCOUT/WATCH；若要主交易，要求 Fib/PA 强结构补偿，例如 `fib >= 15` 且 `pa >= 15`，或 `fib + pa >= 34`。

2. **把“最低合格 PROBE”与“强 PROBE”分层。**  
   主账本只执行强 PROBE；最低合格 PROBE 用 SCOUT_MICRO 验证。这样可以避免 BCH 08:15 这类信号抢占后续高分窗口。

3. **对 BCH 08:15 和 11:30 做 MFE/MAE 对照。**  
   验证是否存在“早开低分止损，晚开高分更优”的结构性问题。

### 第二阶段：修正 SCOUT 火力覆盖

4. **把 targeted-long 从单 symbol 改为任务池。**  
   优先加入本窗口真实出现信号的 `LINKUSDT`, `LABUSDT`, `HYPEUSDT`, `DOGEUSDT`，同时保留 `CCUSDT`。仓位仍为 `50 USDT`, `1x`。

5. **将 ADAUSDT 加入 SCOUT_ONLY 候选。**  
   ADA 的 watch-only 高分 SHORT 密度最高，适合作为“观察池晋级”测试对象。

6. **暂停或收紧 ZEC 的 `NON_RR_HIGH_SCORE` 微仓。**  
   ZEC 当前负反馈明显。建议改成 RR 达标才允许微仓，RR gap 仅记录 near-miss。

### 第三阶段：分任务统计

7. **按 mission 输出 SCOUT 绩效。**  
   至少拆分：
   - `TARGETED_LONG_OFFSET`
   - `SCOUT_ONLY_HIGH_SCORE`
   - `NON_RR_HIGH_SCORE`
   - `WATCH_ONLY_HIGH_SCORE`

8. **每个 mission 设独立晋级/淘汰标准。**  
   例如 20 笔或 7 天后，要求 profit factor、win rate、MFE/MAE 同时达标，否则停用该 mission。

---

## 9. 最终判断

本窗口不是“进攻失败”，而是“进攻执行暴露了两个精确问题”：

1. **主交易层仍会执行最低合格 PROBE。**  
   这类交易可能亏损，并且通过冷却机制压制后续更高质量信号。

2. **SCOUT 层的任务配置没有跟随真实 near-miss 分布。**  
   它测试了 ZEC，但没有测试本窗口最密集的 targeted-long offset 候选，也没有把 ADA 这类观察池高分 SHORT 转入微仓闭环。

因此，下一步不应简单提高交易次数，也不应直接放松 LONG offset 或 RR 门槛。更合理的方向是：

```text
主交易更精兵化：
  低分 PROBE 降为 SCOUT/WATCH，强 PROBE/DIRECT 才进主账本。

SCOUT 更网状化：
  targeted-long 按任务池采样，ADA 进入 watch-only 高分测试，ZEC 暂停或收紧 RR gap 微仓。
```

这会让系统从“能开仓”进一步进化为“把主账本留给更强信号，把试错交给 SCOUT”。
