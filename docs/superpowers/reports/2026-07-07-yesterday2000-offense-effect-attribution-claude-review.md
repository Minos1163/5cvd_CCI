# AI300 Dry-Run 进攻态势执行效果归因报告

**用途:** 提交 Claude 复审  
**分析窗口:** 北京时间 2026-07-06 20:00:00 至 2026-07-07 20:00:05  
**日志目录:** `logs/2026-07/2026-07-06/`, `logs/2026-07/2026-07-07/`  
**策略状态:** 第七轮“主交易精兵化 + SCOUT 动态化”已生效；主交易无新开仓，SCOUT_MICRO 仅产生一笔新实验仓。

---

## 1. 核心结论

本窗口“扩大盈利点”的执行效果仍不理想，但原因已经进一步清晰：**主交易从“低质量开枪”切换成了“完全不开新枪”，SCOUT 动态化开始生效但样本质量仍不足。**

1. **主交易没有新增开仓。**  
   1358 条决策中，`PROBE=0`, `DIRECT=0`，全部是 `NO_TRADE/WATCH`。窗口内主账本有两条 BCHUSDT 事件，但它们是上一窗口 17:30 已开 BCH SHORT 的 TP1 与保本止损收尾，不是新进攻信号。

2. **旧 BCH 仓位管理是正反馈，但不能证明新进攻层有效。**  
   BCHUSDT SHORT 在 20:00 触发 TP1，净 `+9.0202 USDT`；22:15 剩余仓位保本止损，净 `+0.0012 USDT`。该仓位完整生命周期净约 `+7.0657 USDT`。这证明分批止盈/保本逻辑有效，但它不是窗口内新开仓能力的结果。

3. **SCOUT 动态化确实工作，但第一笔 targeted-long 失败。**  
   XLMUSDT LONG `TARGETED_LONG_OFFSET` 于 2026-07-07 05:00 开仓，score `90.2`，但 07:00 初始止损。平仓净 `-0.4904 USDT`，含入场成本后该仓位约 `-0.5404 USDT`。这说明 targeted-long 任务池能开火，但“高分 + LONG offset + RR 小缺口”的组合仍不稳定。

4. **阻塞主交易的主因不是 elite gate 单点过严。**  
   `PROBE_BELOW_ELITE_STRUCTURE_GATE` 仅出现 7 次，`PROBE_LOW_SCORE_ELITE_VETO` 仅 3 次。更大的拦截来源是 `SIDE_THRESHOLD_OFFSET_LONG_10.00` 343 次、`SYMBOL_WATCH_ONLY` 183 次、`SYMBOL_BLACKLISTED` 179 次、`FIB_EXTENSION_EXHAUSTION_BLOCK` 91 次、Fib 位置不足 48 次。

5. **进攻层当前最大问题是“主交易过于空、SCOUT 过于少且首样本负反馈”。**  
   主交易已经足够防守；SCOUT 仍未形成足够样本量。窗口内 near-miss 只有 16 条，`TARGETED_LONG_OFFSET` 标签 4 条，其中仅 XLMUSDT 达到 SCOUT 开仓条件并实际开仓，且止损。

一句话归因：**防御和精兵门有效，但当前市场/配置组合没有给主交易新开仓；SCOUT 动态化只验证了一笔 XLM targeted-long，结果为初始止损，说明“扩大盈利点”仍停在低样本、低命中阶段。**

---

## 2. 链路健康确认

### 2.1 数据范围

| 指标 | 结果 |
|---|---:|
| 决策行数 | 1358 |
| 决策时间范围 | 2026-07-06 20:00:05 至 2026-07-07 20:00:05 |
| near-miss | 16 |
| gate rejection | 1358 |
| 主账本事件 | 2 |
| SCOUT_MICRO 账本事件 | 2 |
| 最新 `data_health` | OK |
| 交易对数量 | 14 |

### 2.2 决策动作分布

| action | 次数 |
|---|---:|
| `NO_TRADE` | 1190 |
| `WATCH` | 168 |
| `PROBE` | 0 |
| `DIRECT` | 0 |

没有任何主交易新开仓动作。

### 2.3 执行层不是故障点

7 月 7 日 `summary.json` 显示：

```text
orders_submitted=0
data_health=OK
exchange_mutation_enabled=False
```

`order_drafts.jsonl` 中 7 月 7 日全部为：

```text
approved=false
reason="entry chain action does not allow live order draft"
request=null
```

因此没有新主仓，不是订单链路故障，而是 entry-chain 准入层没有给出 `PROBE/DIRECT`。

---

## 3. 主交易表现

### 3.1 窗口内主账本事件

| 时间 CST | 事件 | symbol | side | 结果 |
|---|---|---|---|---:|
| 2026-07-06 20:00 | `PAPER_REDUCE` | BCHUSDT | SHORT | `TP1_HIT`, net `+9.0202` |
| 2026-07-06 22:15 | `PAPER_CLOSE` | BCHUSDT | SHORT | `BREAKEVEN_STOP_HIT`, net `+0.0012` |

该 BCH 仓位在上一窗口 2026-07-06 17:30 开仓，score `90.3`，5x。窗口内只是后续持仓管理。完整仓位的 `position_realized_pnl` 约 `+7.0657 USDT`。

### 3.2 结论：退出逻辑有效，入场扩张无新增

BCH 这笔说明：

- 分批止盈能捕捉顺行；
- 保本止损避免盈利回吐为亏损；
- 高分 DIRECT 的确比低分 PROBE 更有潜力。

但它不能证明“扩大盈利点”已进入稳定阶段，因为窗口内没有任何新主交易开仓。主交易扩张仍然停滞。

---

## 4. SCOUT_MICRO 表现

### 4.1 窗口内 SCOUT 事件

| 时间 CST | 事件 | symbol | side | mission | score | 结果 |
|---|---|---|---|---|---:|---|
| 2026-07-07 05:00 | `PAPER_OPEN` | XLMUSDT | LONG | `TARGETED_LONG_OFFSET` | 90.2 | 开仓 |
| 2026-07-07 07:00 | `PAPER_CLOSE` | XLMUSDT | LONG | `TARGETED_LONG_OFFSET` | - | `INITIAL_STOP_HIT`, net `-0.4904` |

开仓 reasons：

```text
SCOUT_MICRO
SCOUT_MISSION_TARGETED_LONG_OFFSET
FIB_PA_ARCHITECTURE_WEIGHTS
SIDE_THRESHOLD_OFFSET_LONG_10.00
PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_0.5
```

XLM 这笔的组件分：

| 组件 | 分数 |
|---|---:|
| total score | 90.2 |
| CCI | 14 |
| Fib | 18 |
| CVD | 18 |
| PA | 21 |
| RR | 3.5 |
| EMA | 15.7 |

### 4.2 SCOUT 账本最新状态

最新 `scout_micro/paper_summary.json`：

| 指标 | 值 |
|---|---:|
| trade_count | 5 |
| realized_pnl | -1.9543 |
| profit_factor | 0.0946 |
| win_rate | 20% |
| open_positions | 0 |

SCOUT 的累计绩效继续恶化。虽然单笔金额很小，但其研究信号是明确的：**当前 SCOUT 选择的 near-miss 模式还没有显示正期望。**

### 4.3 targeted-long 动态化已生效，但开仓条件仍需复审

本窗口 `TARGETED_LONG_OFFSET` 标签共 4 条：

| symbol | 数量 | 结果 |
|---|---:|---|
| XLMUSDT | 2 | 其中一笔 score 90.2 开仓后止损 |
| DOGEUSDT | 1 | score 81.69，未达 `scout_micro_min_score=82` 或结构/任务条件不足 |
| LINKUSDT | 1 | score 81.59，未达 `scout_micro_min_score=82` 且 RR/Fib 不足 |

这说明动态任务池不是完全失效，而是样本太少，且唯一达标样本带着 `RR=3.5/8` 的缺口进入实验，最终止损。

---

## 5. Near-Miss 与拦截结构

### 5.1 主拒绝原因

| 原因 | 次数 |
|---|---:|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 343 |
| `SYMBOL_WATCH_ONLY` | 183 |
| `SYMBOL_BLACKLISTED` | 179 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 91 |
| `PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0` | 48 |
| `DAILY_TRADE_BUDGET_USED` | 47 |
| `SYMBOL_DAILY_TRADE_BUDGET_USED` | 37 |
| `SYMBOL_POSITION_ALREADY_OPEN` | 11 |
| `PROBE_BELOW_ELITE_STRUCTURE_GATE` | 7 |
| `PROBE_LOW_SCORE_ELITE_VETO` | 3 |

精兵门不是最大拦截来源。真正的大头仍然是 LONG offset、受限标的、黑名单、Fib 结构、预算/单币预算。

### 5.2 分数分布

| 阈值 | 数量 |
|---|---:|
| `score >= 70` | 172 |
| `score >= 72` | 144 |
| `score >= 75` | 95 |
| `score >= 80` | 28 |
| `score >= 82` | 13 |
| `score >= 85` | 4 |
| `score >= 90` | 3 |
| 最高分 | 90.2 |

高分信号少于上一窗口，且大多仍带结构问题或标的状态限制。

### 5.3 高分 near-miss 样例

| 时间 CST | symbol | side | score | primary reason | 组件特征 |
|---|---|---|---:|---|---|
| 2026-07-07 04:45 | ZECUSDT | LONG | 90.2 | `SYMBOL_BLACKLISTED` | Fib 18, PA 21, RR 3.5, EMA 15.7, CCI 14 |
| 2026-07-07 05:15 | XLMUSDT | LONG | 90.2 | `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 进入 SCOUT，2小时止损 |
| 2026-07-07 10:45 | ZECUSDT | SHORT | 90.2 | `SYMBOL_BLACKLISTED` | Fib 18, PA 21, RR 3.5, EMA 15.7, CCI 14 |
| 2026-07-07 09:30 | LINKUSDT | SHORT | 87.3 | `DIRECT/PROBE RR gap` | RR 2.0，虽高分但 RR 缺口大 |
| 2026-07-07 11:45 | XMRUSDT | LONG | 84.59 | `SYMBOL_WATCH_ONLY` | RR 0.0，不适合直接放行 |
| 2026-07-07 10:15 | BCHUSDT | SHORT | 83.69 | `RR gap 0.5` | Fib 18, PA 21, RR 3.5 |

高分 near-miss 的质量并不统一：

- ZEC 高分但黑名单，且前几轮 ZEC scout 已给出负反馈；
- XLM 高分 targeted-long 实测止损；
- LINK/BCH 高分但 RR 缺口；
- XMR watch-only 但 RR 为 0。

这解释了为什么主交易没有新开仓：并不是简单“错杀一堆优质信号”，而是多数高分信号仍有硬伤。

---

## 6. 预算与冷却影响

### 6.1 日预算拦截

`DAILY_TRADE_BUDGET_USED` 出现 47 次，主要集中在 TRXUSDT。典型样例：

```text
TRXUSDT LONG, score=77.7, Fib=9, PA=21, RR=0, EMA=15.7, CCI=14
dynamic_limit=2, used_today=2
```

这些被预算拦截的信号并非高质量机会，通常 RR 很弱或 Fib 不足。因此预算不是本窗口主交易缺失的核心原因。

### 6.2 单币预算拦截

`SYMBOL_DAILY_TRADE_BUDGET_USED` 出现 37 次，主要来自 BCHUSDT。  
最高样例：

```text
BCHUSDT SHORT, score=81.3, Fib=9, PA=21, RR=5, EMA=14.3, CCI=14
```

这类信号也有 Fib 不足或分数未达强主交易标准的问题。单币预算有机会成本，但没有明显错杀 90+ 主交易信号。

---

## 7. 根因分层

### 一级根因：主交易扩张仍无新增样本

本窗口内 `PROBE/DIRECT=0`。  
旧 BCH 的正收益来自上一窗口开仓，不是本窗口“扩大盈利点”的新成果。

### 二级根因：高分 near-miss 数量少且硬伤明显

`score >= 85` 只有 4 条。最高分 90.2 的三条中：

- 两条是 ZEC，被黑名单拦截，且此前 ZEC SCOUT 负反馈明显；
- 一条是 XLM LONG targeted-long，进入 SCOUT 后止损。

因此当前还不能证明主交易门槛过严；更像是本窗口优质主交易机会本身不足。

### 三级根因：SCOUT targeted-long 的首个有效样本验证失败

XLMUSDT `90.2` 是完美的实验样本：高 CCI、高 Fib、高 PA、高 EMA，但 RR 只有 3.5 且被 LONG offset 拦截。它两小时后初始止损，说明：

- `TARGETED_LONG_OFFSET` 不能只看总分；
- RR 小缺口在 LONG 侧依然危险；
- LONG offset 防线目前仍有保留价值。

### 四级根因：SCOUT 样本量仍太低

动态化后只产生 1 笔 SCOUT 新开仓。  
这不足以判断任务池整体有效，但足以提示当前开仓条件还没有形成“火力侦察网”的密度。

### 五级根因：elite gate 有效但不是主要堵点

精兵门相关拦截仅 10 次。典型被拦信号：

- `XLMUSDT SHORT 79.3`: PA 12，结构不强；
- `HYPEUSDT SHORT 79.8`: PA 12，RR 3.5；
- `LINKUSDT SHORT 74.7`: 低于 75，PA 11，RR 2。

这些更像正确过滤，而非过度防御。

---

## 8. 给 Claude 的复审问题

1. **当前主交易 0 新开仓，是精兵门过严，还是市场窗口内确实没有合格主信号？**  
   我的初步判断：精兵门不是最大堵点，更多是 LONG offset、受限标的、Fib/RR 硬伤导致。

2. **XLMUSDT `TARGETED_LONG_OFFSET` 止损后，是否应收紧 targeted-long 的 RR 要求？**  
   这笔 score 90.2、Fib 18、PA 21、EMA 15.7、CCI 14，但 RR 3.5，最终初始止损。是否应要求 targeted-long micro 至少 `RR >= 4.0`，或 `RR >= 3.5` 但必须无 `PROBE_BELOW_RISK_REWARD` reason？

3. **ZECUSDT 是否继续完全退出 SCOUT 微仓池？**  
   本窗口 ZEC 又出现两条 90.2 高分 near-miss，但此前 ZEC scout 已负反馈。是否继续只记录 near-miss，不给微仓？

4. **ADA/XMR 的 `SCOUT_ONLY` 是否真正有机会？**  
   本窗口 XMR 最高 84.59 但 RR=0；ADA 没有突出高分 near-miss。是否应该维持观察，还是把 SCOUT_ONLY 资源转给更频繁产生 near-miss 的标的？

5. **日预算使用 UTC/自然日是否造成夜间窗口预算残留？**  
   20:00 后部分信号显示 `used_today=2`，`dynamic_limit=2`，说明晚间窗口可能继承了白天交易计数。虽然本窗口被预算拦截的多为弱信号，但长期看是否应改为北京时间交易日？

6. **下一阶段目标应继续追求主交易数量，还是先把 SCOUT mission 的命中率拉正？**  
   本窗口主交易无新样本，SCOUT 首样本止损。也许下一阶段更应优先评估 SCOUT mission 过滤条件，而不是放宽主交易。

---

## 9. 建议方向

### 9.1 主交易保持精兵门，不急于放松

当前没有证据说明 elite gate 错杀大量优质交易。  
`PROBE_BELOW_ELITE_STRUCTURE_GATE` 与 `PROBE_LOW_SCORE_ELITE_VETO` 的样本大多确实结构不强或分数偏低。

### 9.2 targeted-long SCOUT 增加 RR 质量约束

建议复审是否将 targeted-long micro 条件从：

```text
score >= 82, PA >= 18, RR >= 3
```

提高为：

```text
score >= 82, PA >= 18, RR >= 4
```

或：

```text
若 RR < 4，则仅记录 near-miss，不开微仓。
```

XLM 的止损说明 LONG offset + RR 缺口组合仍需谨慎。

### 9.3 将 SCOUT 任务按 reason 做绩效归因

目前 `scout_mission=TARGETED_LONG_OFFSET` 只说明任务类型，但还应在复盘中拆：

- `TARGETED_LONG_OFFSET_WITH_RR_GAP`
- `TARGETED_LONG_OFFSET_WITH_FIB_GAP`
- `TARGETED_LONG_OFFSET_FULL_COMPONENT_PASS`

这样才能判断到底是 LONG offset 本身无效，还是 RR/Fib 缺口拖累了实验。

### 9.4 保留 ZEC 黑名单，只做 near-miss 观察

ZEC 高分频繁出现，但前几轮 SCOUT 负反馈已足够。当前不建议重新开放微仓，除非它出现 `RR >= 4` 且连续多次 MFE/MAE 回放正向。

### 9.5 检查交易日计数时区

预算不是本窗口核心堵点，但 `used_today=2` 在北京时间夜间延续，可能影响未来 20:00 复盘窗口。建议确认交易计数是否按 UTC 日、日志日或北京时间日滚动。

---

## 10. 最终判断

这一窗口的进攻态势不理想，不能简单归因于“门槛太高”。更准确的判断是：

```text
主交易层：
  精兵门有效，但市场窗口内没有出现足够完整的强主交易信号。

SCOUT层：
  动态任务池已开始工作，但唯一新开仓 XLM targeted-long 初始止损，
  暴露出 LONG offset + RR 缺口组合仍然危险。

扩大利润点：
  当前还没有形成可扩张的正反馈样本；应先提高 SCOUT mission 的样本质量，
  再考虑把任何模式晋级为主交易。
```

因此，下一步不应拆掉主交易防线，而应把 SCOUT 从“高分 near-miss 微仓”进一步升级为“按缺陷类型分层的实验系统”。只有当 `TARGETED_LONG_OFFSET_FULL_COMPONENT_PASS` 或某个 watch-only 标的持续出现正 MFE/MAE，才值得扩大主交易开仓频率。
