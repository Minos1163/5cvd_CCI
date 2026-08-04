# AI300 08-02 21:00 后进攻窗口归因报告 — 为什么没抓住机会 & 如何开启盈利进攻

**提交对象:** Claude 复核
**分析窗口:** 2026-08-02 21:45 至 2026-08-04 19:00,北京时间(UTC+8)。
**运行模式:** dry-run / paper ledger / SCOUT micro / paper A-B mirror(进攻配置)。
**数据来源:** `logs/2026-08/{2026-08-02,2026-08-03,2026-08-04}/` 下 `decisions.jsonl`、`near_misses.jsonl`、`scout_decisions.jsonl`、`gate_rejections.jsonl`、`paper_trades.jsonl`、`scout_micro/paper_trades.jsonl`、`paper_ab/{legacy,trend_capture}/paper_trades.jsonl`、`paper_ab/reports/*`、`summary.json`、`paper_equity.json`、`runtime.out.*.log`。
**重要口径:**
- 窗口起点以进攻配置实际生效点为准:配置 `configs/entry_chain.dry_run_fib_pa_v1.json` 于 **08-02 21:16:52(+0800)** 保存,进程于 **21:45:05(+0800)重启**(runtime 日志 `cycle 1 @ 2026-08-02 13:45:05 UTC`,cycle 重新计数);21:00-21:45 为旧配置最后 3 个 cycle,归入基线。
- 数据截止: **08-04 19:00(+0800)**(decisions.jsonl 最后一条 timestamp=1785841205)。08-04 19:15 周期已在 runtime 日志运行但结构化数据未同步,为保证各表口径一致统一排除。
- 报告中的"拐点""被拒机会 MFE/MAE""高分拦截 replay"均为**事后复盘**,使用系统当时实际可见的 kline 数据(decisions.jsonl 内嵌快照),不含未来函数;但任何进攻修改仍必须先经 dry-run / paper / SCOUT 层验证。
- 分析脚本与中间数据:`logs/analysis/scripts/`、`logs/analysis/*.json`(git-ignored),全部可复现。

---

## 0. 结论摘要

1. **进攻配置确实生效了,但"开仓"只发生在实验账本,主账本零开仓。** 窗口内 2,366 条决策,主账本 `paper_trades.jsonl` **0 行**、`order_drafts` **0 批准**;开仓全部集中在 A/B mirror(58 事件)与 SCOUT(8 事件),且**均为负期望**。
2. **Q1 高分机会充足但 100% 被拦截。** Q1 有 46 个 `score>=80`、14 个 `score>=85`、最高 90.10(SOLUSDT);37 条 near-miss(均值 84.85,全部 ≥80)无一放行。
3. **主账本进攻通道存在一个结构性死规则:** `_q1_trend_launch_eligible()`(run_live_dry_run.py L866-896)仍强制要求 `Q2_PENDING_MOMENTUM_CONFIRMED` / `Q3_TO_Q1_CONFIRMED` 确认标签,而**窗口内该标签出现次数为 0** → `q1_trend_launch`/`q1_green_channel` 在配置 `enabled=true` 的情况下也**永远不可能触发**。这正是 08-02 工程报告 Task A 要求移除的"确认标签依赖",代码未落实。
4. **LONG 侧阈值偏移 +10 使主账本 LONG 入口结构性不可达。** 配置 `long_threshold_offset=10.0` → LONG 的 direct 门槛 = 82+10 = **92**,高于窗口最高分 90.1;`SIDE_THRESHOLD_OFFSET_LONG_10.00` 拦截 747 次(31.6% 决策)。
5. **被拦截的高分机会,事后证明大多是真亏损。** 19 条 `score>=85` 拦截信号按 `stop_first` 假设复盘:**止损命中率 89.5%**、平均终局 -0.69R;37 条 near-miss 在 2h 内仅 21.6% 触及 +1R。唯一明显盈利子集是 **LONG 侧被 `SIDE_THRESHOLD_OFFSET_LONG` 拦下的样本**(blended +0.465R)。
6. **A/B mirror 正是"放行这些候选会怎样"的受控实验,结果是亏损。** mirror 以 50 名义本金交易被拦候选:legacy -1.68 / trend -1.74,胜率 59% 但负期望(payoff<1);批次累计 PF 0.345/0.370。→ **简单放行不盈利,盈利进攻必须同时修入口(位置/几何/方向分层)与出口(止盈/移动止损)。**
7. **行情拐点存在但方向质量不稳。** 窗口识别 148 个局部拐点(低点 111 ≫ 高点 37,市场偏空);系统方向与后续 8 根运动匹配率 60.6%,但 70-80 分段仅 42.9%;唯一触发的 REVERSAL_PIVOT_SCOUT 4 笔净亏 -0.26。
8. **当前最需要的不是"放开闸门",而是三条动作:** ①修复 q1_trend_launch 死规则(按 Task A 改位置质量约束);②LONG 阈值按分布校准并分层放行(区分 SHORT/RR-gap 亏损子集与 LONG 盈利子集);③改善出场(payoff 结构),让已开仓通道转正。

---

## 1. 本轮进攻是否真正生效

### 1.1 已生效的部分

| 模块 | 日志证据 | 结论 |
|---|---:|---|
| 进攻配置加载 | 三日 `summary.json.dry_run_assumptions` 中 `mirror_ab / q1_green_channel / q1_trend_launch / q2_pending / q3_to_q1 / reversal_pivot` 全部 `enabled=true` | 已生效 |
| 四象限标注 | 2,366 条决策均有 Q1-Q4 标注 | 已生效 |
| 侦察评估 | 37 条 `scout_decisions.jsonl` | 已生效 |
| REVERSAL_PIVOT_SCOUT | 4 笔开仓(entry_channel=`scout_reversal_pivot_scout`) | 已生效 |
| A/B mirror | 27 对开仓(entry_channel=`mirror_ab_sample`) | 已生效 |
| A/B 批次报告 | batch 6 输出 | 已生效 |

### 1.2 未达到目标的部分

| 目标 | 实际 | 判断 |
|---|---:|---|
| 主账本进攻开仓 | **0 笔**(paper_trades 0 行、order_drafts 0 批准) | 未达标 |
| `q1_trend_launch`/`q1_green_channel` 主账本转化 | 0 条(确认标签 0 次出现) | 结构性不可触发 |
| Q2 pending 捕捉 | 0 确认 | 通道空转 |
| Q3→Q1 确认 | 0 确认 | 通道空转 |
| SCOUT 盈利验证 | 4 笔, -0.2622 | 未通过 |
| mirror 盈利验证 | legacy -1.6839 / trend -1.7405 | 未通过 |
| 自动切换 trend_capture | 未触发(批次 PF<1) | 合理 |

**结论:配置"已加载、已接线、已评估",但主账本转化=0;开仓集中在实验账本且负期望。**

---

## 2. 总体执行表现

### 2.1 决策分布(窗口 2,366 条)

| 日期(北京) | 决策数 | NO_TRADE | WATCH | PROBE |
|---|---:|---:|---:|---:|
| 08-02 21:45 起 | 533 | 486 | 47 | 0 |
| 08-03 | 1,248 | 1,063 | 185 | 0 |
| 08-04(至 19:00) | 585 | 527 | 58 | 0 |
| **合计** | **2,366** | **2,076** | **290** | **0** |

### 2.2 闸门分层(从 `gate_rejections.jsonl` reasons 拆分,窗口口径)

| 层 | 计数 | 占比 |
|---|---:|---:|
| side_policy(`SIDE_THRESHOLD_OFFSET_LONG_10.00`) | 747 | 31.6% |
| symbol_policy(`BLACKLISTED` 325 + `WATCH_ONLY` 354) | 679 | 28.7% |
| architecture_only(仅架构权重,无具体闸门) | 655 | 27.7% |
| fib_policy(`FIB_EXTENSION_EXHAUSTION_BLOCK`) | 152 | 6.4% |
| probe(各 RR/Fib/PA/score gap) | 139 | 5.9% |
| direct(`DIRECT_BELOW_RISK_REWARD_GEOMETRY_*`) | 25 | 1.1% |
| other | 9 | 0.4% |

高分被拒(≥80,共 57 条决策)按原因:`PROBE_BELOW_RR_GEOMETRY_*` 30、`DIRECT_BELOW_RR_GEOMETRY_*` 25、`SYMBOL_BLACKLISTED` 14、`SYMBOL_WATCH_ONLY` 8、`SIDE_THRESHOLD_OFFSET_LONG` 5、`PROBE_BELOW_ELITE_STRUCTURE` 3、`HIGH_BETA_PROBE_RR` 2。

### 2.3 三账本结果(窗口)

| 账本 | 开仓 | 平/减仓 | 窗口事件 PnL | 胜率 | 主要结论 |
|---|---:|---:|---:|---:|---|
| 主账本 | 0 | 0 | — | — | 零开仓 |
| SCOUT micro | 4 | 4 | -0.2622 | 50% | REVERSAL_PIVOT 唯一通道 |
| A/B mirror legacy | 27 | 39 | -1.6839 | 58.97% | 放行被拦候选=负期望 |
| A/B mirror trend | 27 | 39 | -1.7405 | 58.97% | 同上 |

A/B 批次累计口径(batch 6,自实验启动):legacy 120 笔平仓 **PF 0.345**、trend_capture 120 笔 **PF 0.370**;窗口口径与批次口径统计口径不同(胜率定义差异),两者均指向负期望。

账户累计状态(含 06-19 以来全部 dry-run):equity 9,770.75,return **-2.29%**,max_dd 3.94%,win_rate 40.62%,PF 0.616。

---

## 3. 四象限得分结构

象限定义(轴判定阈值:`quadrant_trend_ema_min=15`、`quadrant_price_action_min=10`、`quadrant_flow_cvd_min=14`、`quadrant_cci_min=7`):

- **Q1:** 趋势/结构轴通过 + 资金/动能轴通过
- **Q2:** 趋势/结构轴通过,资金/动能轴未通过
- **Q3:** 趋势/结构轴未通过,资金/动能轴通过
- **Q4:** 两轴均未通过

### 3.1 象限数量与总分(窗口,2,366 决策)

| 象限 | 样本 | 平均 | 中位 | P90 | 最大 | >=80 | >=85 | >=90 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Q1 | 277 | 72.58 | 72.10 | 81.7 | 90.10 | 46 | 14 | 1 |
| Q2 | 364 | 59.82 | 60.19 | 70.79 | 80.24 | 1 | 0 | 0 |
| Q3 | 455 | 60.95 | 60.10 | 72.7 | 87.30 | 10 | 2 | 0 |
| Q4 | 1,270 | 42.15 | 43.10 | 55.69 | 78.64 | 0 | 0 | 0 |

### 3.2 象限 × 行为

| 象限 | NO_TRADE | WATCH |
|---|---:|---:|
| Q1 | 149 | 128 |
| Q2 | 289 | 75 |
| Q3 | 380 | 75 |
| Q4 | 1,258 | 12 |

### 3.3 高分样本(≥85,16 条,全部 WATCH/NO_TRADE)

| 时间(UTC) | 标的 | 象限 | 方向 | 分数 | 主因 |
|---|---|---|---|---:|---|
| 08-03 02:45 | SOLUSDT | Q1 | SHORT | 90.1 | `DIRECT_BELOW_RR_GEOMETRY_2.0` |
| 08-03 00:15 | BCHUSDT | Q1 | SHORT | 88.7 | `DIRECT_BELOW_RR_GEOMETRY_2.0` |
| 08-03 00:15 | ZECUSDT | Q1 | SHORT | 87.7 | `SYMBOL_BLACKLISTED` |
| 08-02 22:30 | BNBUSDT | Q3 | SHORT | 87.3 | `DIRECT_BELOW_RR_GEOMETRY_2.0` |
| 08-03 07:00 | BCHUSDT | Q3 | LONG | 87.3 | `SIDE_THRESHOLD_OFFSET_LONG_10.00` |
| 08-02 23:30 | TRXUSDT | Q1 | SHORT | 86.7 | `DIRECT_BELOW_RR_GEOMETRY_4.0` |
| 08-03 03:45 | ADAUSDT | Q1 | SHORT | 86.69 | `SYMBOL_WATCH_ONLY` |
| 08-03 02:15~04:45 | DOGE/SOL/BCH/BNB | Q1 | SHORT | 86.1~86.59 | `DIRECT_BELOW_RR_GEOMETRY_2.0`(×5) |
| 08-03 02:45 | XRPUSDT | Q1 | SHORT | 85.19 | `SYMBOL_BLACKLISTED`(×2) |
| 08-03 02:45 | LINK/BCH | Q1 | SHORT | 85.19 | `DIRECT_BELOW_RR_GEOMETRY_2.0`(×2) |

**结论:Q1 高分样本充足,但方向几乎全是 SHORT 且被 RR 几何门槛拦截;LONG 高分样本极少且被 side 阈值/符号政策拦截。**

---

## 4. 行情拐点与近失机会复盘

### 4.1 局部拐点与方向匹配(事后,基于 decisions.jsonl 内嵌 15m kline)

- 识别方法: fractal 2-bar(±2 根内最高/最低),窗口内 13 symbol 连续序列。
- 结果:**148 个局部拐点**(高点 37 / 低点 111)→ 市场整体偏空/下行,低点远多于高点。
- 方向匹配(有决策方向 + 后续 8 根运动,142 条):总体 **60.56%**(86/142)。

| 分象限 | n | 匹配率 |
|---|---:|---:|
| Q1 | 16 | 56.3% |
| Q2 | 29 | 62.1% |
| Q3 | 21 | 66.7% |
| Q4 | 76 | 59.2% |

| 分分数段 | n | 匹配率 |
|---|---:|---:|
| <60 | 102 | 59.8% |
| 60-70 | 21 | 71.4% |
| 70-80 | 14 | 42.9% |
| 80-85 | 3 | 100% |
| >=85 | 2 | 50% |

> 注:此口径与 08-02 报告(6.5 天窗口,匹配率 34.5%)不同,因窗口更短且方法取 entry_context.side。**高分段的匹配率并不比低分段好**(70-80 段甚至最差),说明"高分=方向准"不成立。

### 4.2 被拒机会 MFE/MAE(near-miss 37 条,事后)

全部 37 条 near-miss 均为高分(≥80,均值 84.85,最大 90.1),象限 Q1=29 / Q3=8,主因 DIRECT_RR_GEOMETRY 25、BLACKLISTED 5、SIDE 4、WATCH_ONLY 3。

| 前向视域 | 触及 +1R | 触及 -1R | 终局为正 | 终局为负 |
|---|---:|---:|---:|---:|
| 2h(8 根) | 21.6%(8) | 10.8%(4) | 48.7%(18) | 51.3%(19) |
| 4h(16 根) | 40.5%(15) | 18.9%(7) | 54.1%(20) | 45.9%(17) |

代表样本:HYPEUSDT LONG +2.48R、XLMUSDT SHORT +2.08R(盈利);LINKUSDT SHORT -2.06R、ADAUSDT SHORT -2.37R(亏损)。**盈利与亏损机会并存,净期望不显著为正。**

### 4.3 高分拦截信号 replay(≥85,19 条,stop_first,96 根视域)

| 指标 | 值 |
|---|---:|
| 平均 MFE | +1.31R |
| 平均 MAE | -1.37R |
| 平均终局(整仓) | **-0.69R** |
| 平均终局(40/35/25 阶梯) | **-0.22R** |
| TP1 触及率 | 63.2% |
| TP2 触及率 | 10.5% |
| **止损命中率** | **89.5%** |
| LONG(2 条) | 终局 +1.0R / blended **+0.465R** / 止损 50% |
| SHORT(17 条) | 终局 -0.89R / blended -0.30R / **止损 94.1%** |

> 决定性证据:被拦截的高分候选在"先碰止损"的保守假设下 **89.5% 会止损**;但按原因分层后,LONG 侧样本(SIDE_THRESHOLD 拦)明显优于 SHORT 侧(RR 几何拦)。**"放行"不能一刀切。**

---

## 5. 为什么没有抓住机会(根因诊断)

### R1 【结构性死规则】q1_trend_launch 仍依赖确认标签(最高优先级)

`scripts/run_live_dry_run.py` `_q1_trend_launch_eligible()`(L866-896)第 888 行:

```python
if "Q2_PENDING_MOMENTUM_CONFIRMED" not in tag_list and "Q3_TO_Q1_CONFIRMED" not in tag_list:
    return False
```

窗口证据:`near_misses.jsonl` 与 `decisions.jsonl` 中上述两个标签出现次数**均为 0**。→ `q1_green_channel`/`q1_trend_launch` 即使 `enabled=true` 也**永远不触发**。08-02 工程报告 Task A 明确要求"移除确认标签依赖,加入位置质量约束替代",**代码未落实**(沿用 07-27 版)。

### R2 【结构性不可达】LONG 阈值偏移 +10

- 配置:`direct_threshold=82`、`watch_threshold=62`、`long_threshold_offset=10.0`(配置文件出现两次键 `7.0`/`10.0`,JSON 解析后者生效;建议清理重复键)。
- 语义(src/signals/entry_chain.py `_score_to_action`):LONG 的 direct 门槛 = 82+10 = **92**,watch = 72。
- 窗口最高分 90.1 < 92 → **LONG 主账本入口结构性不可达**;`SIDE_THRESHOLD_OFFSET_LONG_10.00` 出现 747 次(31.6%)。
- 反例:被 SIDE 拦的 LONG 样本 replay blended **+0.465R**(见 4.3)。

### R3 【符号政策】高分被黑名单/watch-only 拦截

- `SYMBOL_BLACKLISTED` 325 次(高分:ZEC 87.7、XRP 85.19×3);`SYMBOL_WATCH_ONLY` 354 次(ADA 86.69)。
- replay 显示 XRP/ZEC 被拦样本止损 100% → **维持黑名单是正确护栏**(08-02 报告约束),但 watch_only 晋级路径(WATCH_ONLY_SYMBOL_PROMOTION)全窗口 0 触发,需数据积累。

### R4 【拦截对象多为真亏损】RR 几何门槛挡的是亏钱机会

- 高分 near-miss 主因 DIRECT/PROBE RR 几何 gap(合计 ~55 次)。
- 实测:≥85 拦截信号止损 89.5%、终局 -0.69R;near-miss 2h 仅 21.6% 达 +1R。
- **结论:RR 几何门槛当前是"防亏"的主要贡献者,直接放宽 = 稳定亏损;应保留并分层。**

### R5 【通道空转】配置已加载、已接线,但转化=0

| 通道 | 接线点 | 窗口转化 | 卡点 |
|---|---|---|---|
| Q1 green/trend-launch | L217 `build_q1_green_channel_decision` | 0 | R1 标签门槛 |
| Q2 pending(70 分已重校准) | L203 `build_q2_pending_candidate` | 0 确认 | Q2 高分稀少(P90=70.79)+确认条件 |
| Q3→Q1 确认 | L194 `confirm_q3_to_q1_pending` | 0 确认 | 确认标签 0 次 |
| REVERSAL_PIVOT_SCOUT | L1073 `scout_micro_mission` | 4 笔 -0.26 | 唯一触发的侦察任务 |
| A/B mirror | L291 `update_mirror_ab_ledgers` | 27 对 -1.68/-1.74 | 候选池本身负期望 |

### R6 【侦察任务单一化】37 个候选只产生一种任务

SCOUT 拒绝原因:`SCOUT_NO_MISSION` 26、`SCOUT_SYMBOL_NOT_ENABLED` 7;任务分布:`REVERSAL_PIVOT_SCOUT` 5、其余任务(Q2_PENDING_MOMENTUM / Q3_TO_Q1_CONFIRMATION / HIGH_SCORE_LONG_OFFSET_PROBE / FIB_CONTINUATION / WATCH_ONLY_PROMOTION)全窗口 **0 触发**。侦察层探索能力严重不足。

### R7 【机会质量】市场偏空 + 反转玩法不盈利

- 148 拐点中低点 111 个 → 空头市况;方向匹配 60.6% 但高分段无优势。
- REVERSAL_PIVOT(反转方向)4 笔:胜率 50%、净 -0.26 → 当前反转信号无正期望。

### R8 熔断/战备金状态

`experiment_war_fund_loss_limit=-150`、`experiment_daily_loss_limit=-200` 窗口内未触发(实验账本累计亏损远小于阈值),`mission_stop_circuit` 未熔断——**不是熔断导致的不开仓**。

---

## 6. 如何开启盈利进攻(建议)

总原则(遵循 08-02 工程化报告约束):**禁止全局放宽 RR、禁止解除 ZEC/XRP 黑名单、禁止实盘配置越级变更;一切改动先经 dry-run / paper / SCOUT 验证。**

### S1 【P0 · 立即可开】修复 q1_trend_launch 确认标签死门槛

- **动作:** 修改 `_q1_trend_launch_eligible()`,移除 L888 标签强制要求,按 08-02 报告 Task A 规格以位置质量约束替代:`score>=85 且 PA>=18 且 Fib>=15 且 CVD>=16 且 RR>=0.5 且非极值追单(overextension/wick/chase 均关闭)`。
- **数据依据:** R1;Q1 有 14 个 ≥85 样本全被标签卡死;Task A 预期解锁 15-25 笔/周。
- **验收标准:** 下一窗口出现 ≥3 条 `DRY_RUN_Q1_TREND_LAUNCH` 决策且进入独立实验账本(不直接主账本);账户仍为 dry-run。
- **熔断护栏:** 前 20 笔实验 PF<0.5 即关闭该通道;`scout_micro_mission_stop_circuit` 保持启用。

### S2 【P0 · 立即可开】LONG 阈值按分布校准 + 分层放行

- **动作:** ①将 `long_threshold_offset` 从 10.0 校准为与 SHORT 对称的 0.0(或按 LONG 得分分布重新标定,如 P90+2);②清理配置重复键(`7.0`/`10.0` 并存);③对 LONG 高分被拦样本(≥85)先进入 `HIGH_SCORE_LONG_OFFSET_PROBE` 侦察任务收集数据。
- **数据依据:** R2;LONG 被拦样本 replay blended +0.465R、止损仅 50%(4.3 节),是全窗口唯一明显盈利子集。
- **验收标准:** LONG 侧 near-miss 转化 ≥1 笔且事件 PnL 为正;SHORT 侧门槛不变。
- **熔断护栏:** LONG 方向连续 5 笔止损即暂停 LONG 侧 12h。

### S3 【P1 · 需先回测】按"原因 × 方向"分层评估放行,不做一刀切

- **动作:** 对 ≥85 拦截信号按(主因 × 方向 × 象限)分桶回测(数据已齐,见 4.3),只对"回测 PF>1 且样本 ≥30"的分桶开设独立实验账本;SHORT/RR-geometry 分桶维持拦截或提高门槛(当前就是防亏主力)。
- **数据依据:** R4;replay 显示 SHORT 止损 94.1% vs LONG 50%,分层差异显著。
- **验收标准:** 分层回测报告产出(每桶 n/PF/终局R);≥1 个分桶满足准入。
- **熔断护栏:** 单桶日亏 -50 或累计 -150 即停;沿用战备金体系。

### S4 【P1 · 立即可开】侦察任务多样化

- **动作:** 校准 Q2_PENDING_MOMENTUM(当前 70 分门槛 vs Q2 分布 P90=70.79,可放宽确认条件)与 HIGH_SCORE_LONG_OFFSET_PROBE、FIB_CONTINUATION 的触发条件,让 37 个候选中的更多样本获得任务;为每个任务建独立小账本与日落条款。
- **数据依据:** R6;全窗口仅 REVERSAL_PIVOT 一种任务触发,26 次 SCOUT_NO_MISSION。
- **验收标准:** 下一窗口侦察任务 ≥3 种、候选任务覆盖率 ≥40%。
- **熔断护栏:** mission stop circuit 保持 3 次/12h。

### S5 【P1 · 需先回测】改善出场 payoff 结构(已开通道转正的关键)

- **动作:** mirror 胜率 59% 却亏损 → payoff<1(小赢大亏)。当前 TP 阶梯 1.2/2.0/3.0 下 replay TP2 触及率仅 10.5%、TP3 5.3%;研究缩短首目标、更早移动止损(如 +1R 后止损移至成本)或提高趋势跟踪灵敏度(`paper_exit_trend_trigger_r` 1.5→1.2 试点)。
- **数据依据:** 4.2/4.3 mirror 负期望 + TP 触及率。
- **验收标准:** 回测 PF>1 且样本 ≥30;A/B 自动切换门槛(payoff≥1.3x)保持。
- **熔断护栏:** 出场改动同样走 A/B 对比,禁止直接切换主账本。

### S6 【护栏维持】不做的三件事

- 不解除 ZEC/XRP 黑名单(XRP/ZEC 拦截样本止损 100%,blacklist 是正确护栏)。
- 不全局放宽 RR 门槛(R4:当前是防亏主力)。
- 不把实验账本(mirror/SCOUT)直接升级为主账本仓位;主账本任何新通道必须先经独立实验账本验证 ≥20 笔。

### 优先级与预期

| 动作 | 优先级 | 类型 | 预期效果 |
|---|---|---|---|
| S1 修 q1_trend_launch 死规则 | P0 | 立即可开 | 解锁 Q1 主账本实验通道(14+ ≥85 样本/窗口) |
| S2 LONG 阈值校准+分层 | P0 | 立即可开 | 解锁 LONG 盈利子集 |
| S5 出场 payoff 改善 | P1 | 需先回测 | 已开通道(mirror/SCOUT)转正 |
| S3 分层放行评估 | P1 | 需先回测 | 决定哪些分桶值得开 |
| S4 侦察任务多样化 | P1 | 立即可开 | 扩大侦察层样本 |
| S6 护栏 | — | 维持 | 防回撤 |

---

## 7. 数据口径与局限

1. **时间口径:** 窗口 = 08-02 21:45(+0800) → 08-04 19:00(+0800);epoch 过滤边界顶层 timestamp ∈ [1785678305, 1785841205];北京时 = UTC+8(日志为真实 UTC)。
2. **summary.json 口径:** 为"进程重启后累计"滚动计数(非按日),本报告一律改用 JSONL 按窗口过滤计算。
3. **同步滞后:** 08-04 19:15 周期已运行(runtime 日志/闸门文件可见)但 decisions.jsonl 未同步,统一排除;进程仍在 VPS 运行,后续数据可能与本文略有出入。
4. **复盘性质:** 拐点方向匹配、near-miss MFE/MAE、高分拦截 replay 均为事后统计,使用系统实际可见数据;`stop_first` 为保守假设,若按 `tp_first` 结果会略好,但止损率仍高。
5. **口径差异:** A/B 批次报告(胜率 25.8%/PF 0.345)与窗口事件统计(胜率 58.97%)定义不同(批次按系统报告,窗口按 margin_pnl 符号),两者均负期望,不混用。
6. **样本量:** 全窗口仅 58 个实验开仓事件、37 条 near-miss、19 条 ≥85 拦截信号,统计显著性有限;结论用于指导实验设计,不作实盘决策依据。
