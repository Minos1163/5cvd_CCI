# AI300 08-07 22:00 后进攻策略复盘与下一轮盈利进攻点建议

**提交对象:** Claude 评审  
**分析窗口:** 2026-08-07 22:00 至 2026-08-11 18:45 左右,北京时间(UTC+8)。  
**运行模式:** VPS dry-run / paper ledger / SCOUT micro / paper A-B mirror。  
**数据来源:** `logs/2026-08/2026-08-07` 至 `logs/2026-08/2026-08-11` 下 `decisions.jsonl`、`near_misses.jsonl`、`scout_decisions.jsonl`、`gate_rejections.jsonl`、`paper_trades.jsonl`、`scout_micro/paper_trades.jsonl`、`paper_ab/{legacy,trend_capture}/paper_trades.jsonl`;并复核 `scripts/evaluate_offense_fixes.py --log-root logs --days 3` 输出。  
**口径说明:** `evaluate_offense_fixes.py --days 3` 按日志日期目录加载,本文主体按 JSONL 内 timestamp 过滤。因此本文窗口会包含 08-07 目录中 timestamp 已进入 08-08 北京时间的样本,主账本 q1_trend_launch 统计为 4 笔;用户贴出的验收脚本三日口径为 3 笔。两者结论一致:通道有转化,但负期望。

---

## 0. 结论摘要

1. **上次更新确实增加了开仓,但没有找到盈利点。** 窗口内 4,467 条决策,Q1 trend launch 主账本 4 开 4 平,PNL **-0.8422**,4 笔前向 4h 均未达到 +1R,3 笔触及 -1R;这不是“样本不足”,而是当前 Q1 入口质量不成立。
2. **A/B mirror 继续证明“放行 near-miss 候选”整体亏损。** legacy 33 开 33 平,PNL **-2.9228**,PF 0.0426;trend 33 开 33 平,PNL **-3.0196**,PF 0.0109。trend_capture 没有改善,因为入场后平均 MFE 只有约 0.52R,多数交易根本没有给出趋势出场可发挥的空间。
3. **SCOUT micro 也为负。** 10 开 10 平,PNL **-0.9522**,PF 0.0256;其中 REVERSAL_PIVOT_SCOUT 9 平 **-0.6524**,HIGH_SCORE_LONG_OFFSET_PROBE 1 平 **-0.2998**。
4. **四象限有效地分类了环境,但当前进攻通道没有用好分类结果。** Q1 有 473 条,平均分 72.41,P90 82.70,最大 90.10;但 Q1 的 RR 均值仅 **1.08/8**,Fib 均值 **9.71/18**。高 PA/CVD 被低 RR/Fib 抵消,直接追 Q1 不是有效进攻。
5. **Q2 pending 的配置阈值已修到 70,但上游 near-miss 采样仍默认 82,导致 Q2 链路实际无输入。** 窗口内 Q2 决策 628 条,P90 69.69,max 78.87;若按 Q2 pending 自身规则(score>=70,PA>=18)扫描,有 36 个 pending 创建,其中 19 个在 6 根 15m 内转 Q1 并满足 CCI 确认。当前 0 触发是工程链路截断,不是市场没给机会。
6. **当前最像进攻点的是 LONG offset continuation,不是泛化 Q1。** `SIDE_THRESHOLD_OFFSET_LONG` 且 score>=82 的 LONG 样本 7 个,前向 4h:4 个触及 +1R,3 个触及 -1R,terminal 平均 +0.101R;这是全窗口少数不明显负期望的分桶。但现有路由被 `REVERSAL_PIVOT_SCOUT` 优先级和 RR>=2 门槛压制,导致三日验收中 HIGH_SCORE_LONG_OFFSET_PROBE 0 开仓。

---

## 1. 验收脚本复现

用户给出的 VPS 输出在本地复现:

```text
== 1) q1_trend_launch 通道 ==
   决策标记数: 3 | 主账本开仓: 3
   主账本事件: {'opens': 3, 'closes': 3, 'pnl': -0.3482, 'win_rate': 0.3333, 'pf': 0.0001, 'payoff_ratio': 0.0002}

== 2) HIGH_SCORE_LONG_OFFSET_PROBE ==
   开仓: 0 | 平仓: 0 | PnL: 0 | PF: None

== 3) Payoff A/B(trend_capture_mirror 试点 vs legacy 对照) ==
   legacy:  {'opens': 25, 'closes': 27, 'pnl': -2.2289, 'win_rate': 0.3333, 'pf': 0.0552, 'payoff_ratio': 0.1103}
   trend:   {'opens': 25, 'closes': 27, 'pnl': -2.3257, 'win_rate': 0.3704, 'pf': 0.0141, 'payoff_ratio': 0.024}
```

验收脚本显示 q1_trend_launch “PASS(有转化)”,但这只是“能开仓”的 PASS,不是“进攻有效”的 PASS。三项核心盈利指标全部失败:

| 模块 | 样本状态 | PnL/PF | 判断 |
|---|---:|---:|---|
| q1_trend_launch | 3-4 笔 | PnL 负,PF 近 0 | 有转化但负期望 |
| HIGH_SCORE_LONG_OFFSET_PROBE | 三日 0 笔 | 无法评估 | 工程/路由仍未给样本 |
| Payoff A/B | 27-33 平仓/组 | legacy/trend 均严重负 PF | 入场池无效,出场优化救不了 |

---

## 2. 四象限得分结构

窗口内 `decisions.jsonl` 共 4,467 条。

| 象限 | 样本 | 行为分布 | 平均分 | P50 | P90 | P95 | 最大 |
|---|---:|---|---:|---:|---:|---:|---:|
| Q1 | 473 | NO_TRADE 281 / WATCH 188 / PROBE 4 | 72.41 | 72.10 | 82.70 | 84.70 | 90.10 |
| Q2 | 628 | NO_TRADE 553 / WATCH 75 | 59.47 | 59.71 | 69.69 | 73.43 | 78.87 |
| Q3 | 862 | NO_TRADE 726 / WATCH 136 | 60.23 | 59.30 | 72.30 | 76.30 | 87.30 |
| Q4 | 2,504 | NO_TRADE 2477 / WATCH 27 | 41.94 | 42.19 | 55.69 | 59.92 | 75.34 |

组件均值:

| 象限 | EMA | PA | CVD | CCI | Fib | RR |
|---|---:|---:|---:|---:|---:|---:|
| Q1 | 16.80 | 16.68 | 18.00 | 10.14 | 9.71 | **1.08** |
| Q2 | 16.93 | 16.70 | 13.41 | 2.36 | 8.91 | **1.15** |
| Q3 | 14.31 | 5.91 | 18.00 | 9.61 | 11.59 | **0.79** |
| Q4 | 13.27 | 3.88 | 11.11 | 1.06 | 11.78 | **0.84** |

解释:

- Q1 不是“必然可开”的象限。它主要代表 CVD/CCI 与趋势结构强,但 RR 均值只有 1.08/8,Fib 均值 9.71/18,大量样本处于高动能但入场位置差的状态。
- Q2 的分数分布上限低于 near-miss 默认阈值 82。Q2 pending 配置降到 70 后,如果上游仍只记录 score>=82 的 near_miss,Q2 pending 永远没有输入。
- Q3 有资金/动能但结构弱,高分样本数量少且多为 RR/Fib 问题,不能作为主进攻入口。
- Q4 占比 56.1%,是弱环境主导窗口,不应扩展主账本进攻,最多作为极值反转研究通道。

---

## 3. 实际交易结果

### 3.1 主账本 q1_trend_launch

timestamp 过滤口径下:4 开 4 平,PNL **-0.8422**,胜率 25%,PF 0。

| 时间(北京) | 标的 | 方向 | 分数 | RR | 退出 | PnL | MFE |
|---|---|---|---:|---:|---|---:|---:|
| 08-08 05:15 | ADAUSDT | LONG | 85.09 | 0.5 | Q4_DEFENSIVE_EXIT | -0.4940 | 0.059R |
| 08-08 16:00 | TRXUSDT | SHORT | 84.70 | 2.0 | Q4_DEFENSIVE_EXIT | -0.0969 | 0.061R |
| 08-09 09:30 | DOGEUSDT | SHORT | 85.19 | 2.0 | INITIAL_STOP_HIT | 0.0000 | 0.514R |
| 08-09 11:45 | LINKUSDT | SHORT | 84.70 | 2.0 | Q4_DEFENSIVE_EXIT | -0.2513 | 0.121R |

前向 4h 复盘同样指向负期望:4 笔平均 MFE 0.343R,平均 MAE -1.308R,0 笔触及 +1R,3 笔触及 -1R。

结论:当前 q1_trend_launch 的问题不是出场,而是入场。它把 Q1 中的低 RR 追单也转成了主账本实验仓,没有真正识别“趋势启航”。

### 3.2 SCOUT micro

| 指标 | 值 |
|---|---:|
| 开仓/平仓 | 10 / 10 |
| PnL | -0.9522 |
| PF | 0.0256 |
| 平均 MFE | 0.666R |
| MFE>=1.0 / >=1.2 / >=1.5 | 3 / 2 / 1 |
| 主要退出 | INITIAL_STOP_HIT 5, COST_BREAKEVEN_TIMEOUT 3, BREAKEVEN_STOP_HIT 2 |

分任务:

| Mission | 平仓 | PnL | 结论 |
|---|---:|---:|---|
| REVERSAL_PIVOT_SCOUT | 9 | -0.6524 | 负期望,且抢占其他任务优先级 |
| HIGH_SCORE_LONG_OFFSET_PROBE | 1 | -0.2998 | 样本严重不足;三日验收口径为 0 |

### 3.3 A/B mirror

| 账本 | 开仓 | 平仓 | PnL | 胜率 | PF | 平均 MFE | MFE>=1.5 |
|---|---:|---:|---:|---:|---:|---:|---:|
| legacy | 33 | 33 | -2.9228 | 30.3% | 0.0426 | 0.555R | 3 |
| trend_capture | 33 | 33 | -3.0196 | 33.3% | 0.0109 | 0.521R | 3 |

主要亏损来源:

| 维度 | 亏损集中点 |
|---|---|
| 退出原因 | Q4_DEFENSIVE_EXIT 32 次,-3.9670;INITIAL_STOP_HIT 27 次,-2.1383 |
| 标的 | HYPEUSDT -2.0448,LINKUSDT -1.9868,ADAUSDT -1.0743 |
| 象限 | Q1 来源 -4.9649,Q3 来源 -0.9776 |
| 方向 | SHORT -4.1354,LONG -1.8071 |

结论:trend_capture 不应自动切换到主账本。当前 A/B 不是出场差异测试,而是在证明 mirror 入场池负期望。

---

## 4. 根因定位

### R1: q1_trend_launch 有转化,但转化对象不是盈利结构

当前 q1_trend_launch 条件实际筛出的 4 笔全部满足 PA/Fib/CVD,但 RR 只有 0.5 或 2.0。它绕过了原本 RR 几何拦截的一部分保护,结果是:

```text
平均 MFE 0.343R
平均 MAE -1.308R
触及 +1R: 0/4
触及 -1R: 3/4
```

这说明“Q1 + 强 PA/Fib/CVD + 低 RR”不是趋势启航,更像是强动能末端或局部反抽后的追单。

### R2: Q2 pending 阈值修正没有真正进入链路

配置层:

```json
"scout_micro_q2_pending_min_score": 70.0
```

但 `run_live_dry_run.py` 的链路是:

```python
near_miss = build_near_miss_payload(decision_payload, min_score=args.near_miss_min_score)
...
pending = build_q2_pending_candidate(near_miss, config, kline_timestamp)
```

而 CLI 默认:

```python
--near-miss-min-score default=82.0
```

Q2 分数分布:

```text
Q2 P90=69.69, P95=73.43, max=78.87
```

所以 Q2 pending 的 70 分门槛虽然合理,但绝大多数 Q2 样本在生成 pending 之前已被 `near_miss_min_score=82` 截断。反事实扫描显示:

```text
Q2 pending potential:
  创建: 36
  6根15m内转Q1确认: 19
  4h前向 MFE均值: 1.585R
  触及+1R: 11/19
  触及-1R: 9/19
  terminal为正: 11/19
```

这条链路是当前最明确的工程缺陷:配置已修,但入口采样未按 mission 分流。

### R3: HIGH_SCORE_LONG_OFFSET_PROBE 没有得到足够样本

窗口内 LONG offset score>=82 的样本有 7 个:

```text
触及 +1R: 4/7
触及 -1R: 3/7
terminal为正: 4/7
terminal均值: +0.101R
```

但三日验收中 HIGH_SCORE_LONG_OFFSET_PROBE 为 0 开仓。原因不是没有 LONG offset,而是:

1. `REVERSAL_PIVOT_SCOUT` 在 `scout_micro_mission()` 中优先级最高,会抢占部分带 `OPPOSITION_STRUCTURE_TOO_CLOSE` 的 LONG offset 样本并反向开仓;
2. HIGH_SCORE_LONG_OFFSET_PROBE 要求 `risk_reward_geometry >= 2.0`,而本窗口多个有 MFE 的 LONG offset 样本 RR=0.0;
3. 部分样本 extreme ratio 超出 q1 trend launch 区间,但这不应自动归入反转,需要单独的 continuation shadow 分桶验证。

结论:LONG offset 仍是可疑正向分桶,但现有 mission 规格没有充分采样。

### R4: REVERSAL_PIVOT_SCOUT 当前不应继续扩张

REVERSAL_PIVOT_SCOUT 9 笔平仓 -0.6524,其中 HYPE/BNB/DOGE 为主要亏损。该任务把部分原方向 LONG 的候选翻成 SHORT,但结果并未验证“拐点反转”假设。

更重要的是,它位于 mission 路由第一位:

```python
if _reversal_pivot_scout_eligible(...):
    return "REVERSAL_PIVOT_SCOUT"
```

这会抢走本该被 LONG_OFFSET_CONTINUATION 或 FIB_CONTINUATION 研究的候选。当前应降级为 shadow/mirror,而不是继续作为唯一活跃 SCOUT 主力。

### R5: A/B 出场不是当前主瓶颈

trend_capture 的逻辑需要价格先给出足够 MFE,但 mirror 样本平均 MFE 只有 0.521R,实际 MFE>=1.5 的样本仅 3/33。此时调 `trend_trigger_r` 或自动切换 exit mode 不会解决问题。

当前应先修入口分桶,再做出场 A/B。否则 A/B 只是持续验证一个负期望入场池。

---

## 5. 下一轮进攻策略建议

### S1 P0: 修复 Q2 pending 上游截断

**目标:** 让 Q2 pending 真正产生样本,而不是被 near-miss 82 分阈值截断。

**建议实现:**

1. 在 `build_near_miss_payload()` 之外新增 `build_quadrant_pending_source_payload()`。Q2/Q3 pending 的创建应直接从 `decision_payload` 读取,使用各自 mission 阈值,不共用全局 `near_miss_min_score`。
2. 或最小改动:在调用 `build_near_miss_payload()` 时,对 Q2/Q3 pending 使用 `min(args.near_miss_min_score, config.scout_micro_q2_pending_min_score, config.scout_micro_q3_to_q1_min_score)`。
3. 新增审计字段:
   - `pending_created`
   - `pending_source_quadrant`
   - `pending_expired`
   - `pending_confirmed`
   - `pending_reject_reason`

**验收标准:**

```text
24h 内 Q2_PENDING created > 0
72h 内 Q2_PENDING_MOMENTUM confirmed/open >= 3
20笔后按 PF/MFE/MAE 决定是否晋级
```

**风险护栏:** 仅 SCOUT/mirror,不进入主账本;若前 10 笔 PF<0.5 或 stop_hit>=60%,暂停。

### S2 P0: 把 q1_trend_launch 从“泛 Q1 追单”改为“Q2/Q3 pullback confirmed”

**目标:** 停止当前低 RR Q1 直接追单,改为只吃“先回调、再回到 Q1”的确认样本。

**建议规则:**

```yaml
q1_trend_launch_v2:
  source_required:
    - Q2_PENDING_MOMENTUM_CONFIRMED
    - Q3_TO_Q1_CONFIRMED
    - LONG_OFFSET_CONTINUATION_CONFIRMED
  score_min: 82
  pa_min: 18
  fib_min: 15
  cvd_min: 16
  rr_min: 0.5
  direct_q1_without_pending: false
```

**为什么不是简单关闭 q1_trend_launch:**  
Q1 本身仍有价值,但不能把“当前就在 Q1”当作开仓理由。需要从状态转换中找进攻点:Q2/Q3 回调/蓄势后重新进入 Q1,比静态 Q1 更接近“趋势启航”。

### S3 P0: LONG offset continuation 独立分桶,并调整路由优先级

**目标:** 继续验证本窗口最接近正期望的分桶:`LONG + SIDE_THRESHOLD_OFFSET_LONG + Q1/Q3 + PA/Fib/CVD强`。

**问题:** 当前 LONG offset 样本可能被 `REVERSAL_PIVOT_SCOUT` 先匹配并反向开仓;这与“验证 LONG continuation”目标冲突。

**建议实现:**

1. 在 `scout_micro_mission()` 中,将 `LONG_OFFSET_CONTINUATION_SCOUT` 放在 `REVERSAL_PIVOT_SCOUT` 之前。
2. 将现有 `HIGH_SCORE_LONG_OFFSET_PROBE` 拆成两层:

```yaml
LONG_OFFSET_CONTINUATION_SCOUT:
  side: LONG
  reason_contains: SIDE_THRESHOLD_OFFSET_LONG
  quadrant: [Q1, Q3]
  score_min: 82
  pa_min: 18
  fib_min: 15
  cvd_min: 14
  rr_min_for_real_scout: 2.0
  rr_min_for_shadow: 0.0
```

3. RR<2 的样本不进入真实 SCOUT,但必须进入 mirror/shadow,否则无法判断 `OPPOSITION_STRUCTURE_TOO_CLOSE` 在 LONG continuation 中是否过度保守。

**验收标准:**

```text
7天内 LONG_OFFSET_CONTINUATION shadow >= 10
真实 SCOUT >= 3
若 shadow PF>1 且 MFE/MAE>1.3,再放宽 real scout 的 rr_min
```

### S4 P1: 暂停或降级 REVERSAL_PIVOT_SCOUT

**目标:** 防止负期望任务继续消耗样本,并避免抢占 continuation 分桶。

**建议:**

```yaml
scout_micro_reversal_pivot_enabled: false
```

或更保守:

```yaml
reversal_pivot_scope: shadow_only
reversal_pivot_max_notional: 10
reversal_pivot_require:
  quadrant: Q4
  cci_extreme_abs_min: 150
  cvd_collapse_required: true
```

当前证据不足以支持 Q1/Q3 反向开仓。反转研究应收窄到 Q4 极值,并保持 shadow 优先。

### S5 P1: A/B 样本池按原因分桶,不要再混合评估

当前 A/B 把 `RR gap / watch-only / long offset / fib exhaustion` 混在一起,结论只能是“整体负期望”。下一步应按分桶出报告:

| 分桶 | 当前倾向 | 动作 |
|---|---|---|
| SHORT + RR geometry gap | 明显负向 | 保持拦截,不进入主账本 |
| LONG + side offset | 可疑正向 | continuation shadow/scout |
| WATCH_ONLY ADA/XMR | 样本少,混合 | 独立晋级账本 |
| FIB exhaustion | 未充分触发 | 单独 shadow |
| Q2 pending confirmed | 当前被截断 | 修链路后独立评估 |

**验收标准:** 每个分桶独立输出 `n / PnL / PF / win_rate / avg MFE / avg MAE / stop_hit / TP1 hit`。不再用总 A/B PF 判断所有进攻规则。

### S6 P1: 出场改动暂缓,只保留观测

当前问题是入场后 MFE 不足。建议:

- 不自动切换 `paper_exit_mode` 到 trend_capture;
- 不继续降低 trend trigger;
- 先等分桶入口有至少 20 笔且平均 MFE>1.0R 后,再评估出场。

如果必须试点出场,仅在 `LONG_OFFSET_CONTINUATION_SHADOW` 与 `Q2_PENDING_MOMENTUM_SHADOW` 两个相对更有 MFE 的分桶里试,不要在全量 mirror 池里试。

---

## 6. 下一轮最小工程清单

### Task A: Pending 输入链路修复

**Files:** `scripts/run_live_dry_run.py`, `tests/test_live_dry_run.py`  
**改动:** Q2/Q3 pending 创建不再依赖 `near_miss_min_score=82`。  
**验证:** 构造 Q2 score=70.5/PA=18 的 decision,证明会创建 pending;构造后续 Q1/CCI>=9,证明会确认为 `Q2_PENDING_MOMENTUM_CONFIRMED`。

### Task B: LONG offset continuation 分桶

**Files:** `scripts/run_live_dry_run.py`, `src/signals/entry_chain_config.py`, `configs/entry_chain.dry_run_fib_pa_v1.json`, tests  
**改动:** 新增 `LONG_OFFSET_CONTINUATION_SCOUT/SHADOW`,路由优先级高于 reversal pivot。  
**验证:** 构造 `SIDE_THRESHOLD_OFFSET_LONG_10.00` + Q1 + LONG + PA/Fib/CVD 强样本,证明不会被 reversal pivot 抢占。

### Task C: 暂停 reversal pivot 或改 shadow-only

**Files:** config first,必要时 run_live_dry_run。  
**改动:** `scout_micro_reversal_pivot_enabled=false`,或改为 shadow-only。  
**验证:** 下一窗口 `REVERSAL_PIVOT_SCOUT` real opens=0;shadow 仍记录。

### Task D: 分桶 A/B 报告

**Files:** `scripts/evaluate_offense_fixes.py` 或新增 `scripts/evaluate_offense_buckets.py`。  
**改动:** 按 `source_reason/source_quadrant/side/symbol/entry_channel` 输出独立 PF/MFE/MAE。  
**验证:** 能单独看到 LONG offset、Q2 pending、RR gap、watch-only 的表现,不再只看总账本。

---

## 7. 给 Claude 的评审问题

1. 是否同意:当前 q1_trend_launch 已从“不开仓问题”转为“低 RR Q1 追单负期望问题”,下一步应改为 pending/source-confirmed,而不是继续放宽 Q1?
2. 是否同意:Q2 pending 0 触发的根因是上游 `near_miss_min_score=82` 截断,不是 `scout_micro_q2_pending_min_score=70` 仍不合理?
3. 是否同意:LONG offset continuation 是当前最值得继续验证的进攻分桶,但应先 shadow/SCOUT,不直接改主账本 `long_threshold_offset`?
4. 是否同意:REVERSAL_PIVOT_SCOUT 当前应暂停或降级,因为它负期望且抢占 continuation 分桶?
5. 是否同意:trend_capture A/B 失败主要由入场池 MFE 不足导致,不应触发自动切换或继续调出场参数?

---

## 8. 一句话结论

本轮策略不是“没有生效”,而是**生效后证明当前打开的入口不是盈利入口**。下一轮进攻不应继续扩大泛 Q1 或泛 mirror,而应集中修复两条可验证链路: **Q2 pending 的上游截断** 和 **LONG offset continuation 的独立采样**;同时暂停负期望的 reversal pivot,把 A/B 从混合账本改成按原因分桶的因果评估。

