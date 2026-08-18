# BNB 漏选分析审查与管道问题升级处理
> 2026-08-07 至 2026-08-13 | q1_trend_launch 连续三轮0转化的升级建议
> 日期：2026-08-13

---

## 目录

1. [最重要的元发现：这是同一个管道问题的第三次确认](#1-最重要的元发现这是同一个管道问题的第三次确认)
2. [直接回答六个评审问题](#2-直接回答六个评审问题)
3. [REVERSAL_PIVOT_SCOUT 停用状态核查](#3-reversal_pivot_scout-停用状态核查)
4. [方法论认可：反事实回测的合规性](#4-方法论认可反事实回测的合规性)
5. [BNB_TREND_CONTINUATION_AFTER_PULLBACK 规格精化](#5-bnb_trend_continuation_after_pullback-规格精化)
6. [实施优先级重排：不要在破损管道上叠加新mission](#6-实施优先级重排不要在破损管道上叠加新mission)
7. [路线图](#7-路线图)

---

## 1. 最重要的元发现：这是同一个管道问题的第三次确认

### 1.1 时间线回顾

```
08-04报告：诊断q1_trend_launch标签依赖问题（第888行代码），给出精确修复规格
08-11报告：确认标签依赖类问题延伸至Q2/Q3 pending（上游near_miss_min_score=82截断），
          明确要求"q1_trend_launch_v2必须在Task A验证通过后才能部署"
08-13本报告：最新48H在线验证——

  python scripts\verify_q1_trend_launch_fix.py --mode online --log-root logs --hours 48
  RESULT: 修复未验证通过(需 q1_trend_launch 转化>0)

这是从08-04首次诊断至今约9天后，q1_trend_launch依然是0转化。
```

### 1.2 为什么这次必须升级处理方式，而非继续诊断

```
连续三轮报告都在诊断同一个通道的同一类问题（不同角度：
标签依赖→上游截断→在线验证仍为0），这个模式本身说明：

  继续"诊断→建议→下一轮报告发现建议未落地→再诊断"的循环
  不会自动收敛。需要的不是第四份诊断报告，是一次强制的
  实施状态核查——直接确认代码仓库当前状态，而非依赖
  下一轮observational report被动发现问题依旧存在。

建议的具体动作（见第6节）：暂停开发任何新的scout mission
（包括本报告提议的BNB_TREND_CONTINUATION_AFTER_PULLBACK），
先集中力量把q1_trend_launch这一条通道从"诊断了三次仍是0"
的状态里拉出来，哪怕只需要半天的代码审查时间。
```

### 1.3 这不代表本轮诊断没有价值

```
需要区分两件事：
  诊断能力：本轮报告的诊断质量依然很高（第4-5节会详细认可）
  实施闭环：诊断产出没有被有效转化为代码变更并验证

前者不是问题，后者才是需要立即处理的问题。
这份报告新增的BNB案例和反事实回测，为下一次真正部署时
提供了更丰富的验证数据，不是无用功——只是当前最紧迫的事
不是设计第四个新mission，是先让第一个通道真正工作起来。
```

---

## 2. 直接回答六个评审问题

### Q1：BNB漏多根因是"主账本无source-confirmed trend-launch入口"，而非"未被扫描到"？

**同意。这个区分本身是本轮报告最重要的贡献。**

```
ATOM案例（08-07报告）：symbol层面完全未进入扫描宇宙（rank过滤问题）
BNB案例（本报告）：symbol正常扫描，高分候选被正确识别（3次），
                  但主账本层面的转化机制（q1_trend_launch）本身空转

这是两种完全不同性质的"漏选"，混为一谈会导致错误的修复方向
（例如误以为BNB也需要类似ATOM那样的symbol层面调整，
 实际上BNB的问题纯粹在决策链路，不在symbol覆盖范围）
```

### Q2：不应简单降低long_threshold_offset或RR门槛？

**同意，且08-08 00:00样本是一个极好的反面教材，应该被固化为回归测试用例。**

```
88.7分、RR=2.0、extreme_ratio=0.904——这个样本已经满足很多"看起来该开仓"
的条件，但1.5小时后止损，MFE仅0.017R。如果当时降低了offset或RR门槛
让这笔进了主账本，会是一次典型的"看着合理但实际是追单顶点"的亏损

建议：将此样本（时间戳、各组件分数、后续MFE/MAE）加入
     test_entry_chain.py的负样本测试集，确保未来任何参数调整
     都不会让这个已知的坏样本重新变得"可开仓"
```

### Q3：REVERSAL_PIVOT_SCOUT对targeted long continuation优先级过高，应至少shadow-only？

**同意，但需要指出一个更紧迫的问题：这个建议在08-11报告的Task C中已经提出，本报告的数据显示它可能仍未部署（见第3节）。**

### Q4：BNB_TREND_CONTINUATION_AFTER_PULLBACK规则是否足够避免未来函数？

**基本合规，但有两处需要在代码实现时特别注意（详见第5节）。**

```
规则设计的核心约束是正确的：
  只用已收盘K线（completed_15m_only）
  突破发生在第N根收盘，确认要求第N+1根收盘仍守住突破位
  这是标准的"信号确认延迟一根"设计，避免了同bar假设

需要注意的细节（非否定性问题，是实现时的精度要求）：
  volume_mult和close_location的计算基准必须明确锁定在
  "trigger bar"（触发那一根），而非"confirm bar"，
  文档中的表格已经这样做了，但代码实现时容易搞混两根K线的归属
```

### Q5：反事实入场点是否需要加1h/4h同向过滤，还是先作为scout shadow收样本？

**建议先shadow收样本，不要在验证前就加多周期过滤条件。**

```
理由：本报告展示的5个正确案例和3个失败案例（08-08 00:00早追、
08-08 22:00追高、08-09 22:00段尾）已经提供了足够的初步样本
用于判断规则本身的基础有效性

如果现在就加1h/4h过滤，会同时改变两个变量：
  规则本身是否有效
  多周期过滤是否有帮助

应该先用当前规则收集15-20笔shadow样本，观察失败案例
（早追/追高/段尾）是否已经被现有的extreme_position_ratio和
"连续两根收盘跌破突破位"条件自然过滤掉。若shadow数据显示
这三类失败案例依然频繁出现，再考虑加1h/4h方向过滤作为下一层保护
```

### Q6：最新48H q1_trend_launch=0是否说明Task A后仍缺少"source-confirmed conversion"验收项？

**同意，且这是本报告最需要被优先处理的发现（见第1节）。**

```
补充一点：q1_trend_launch=0本身不能唯一确定是Task A未部署，
还是Task A已部署但source-confirmed的标签生成逻辑本身仍有其他
未被发现的bug。这两种可能性需要通过直接代码审查区分，
而非继续通过observational report的方式反复确认"仍然是0"
```

---

## 3. REVERSAL_PIVOT_SCOUT 停用状态核查

### 3.1 本报告的证据表明该mission可能仍在正常运行

```
08-07 08:30：BNB LONG 81.3分被REVERSAL_PIVOT_SCOUT翻成SHORT
08-09 18:00：BNB LONG 82.7分同样被REVERSAL_PIVOT_SCOUT翻成SHORT

这两次翻转都发生在08-11报告提出"应停用或shadow-only"建议
（Task C）之前的时间窗口（08-07~08-10），所以严格来说，
本报告的BNB窗口数据本身并不能证明Task C未被采纳——
时间上Task C的建议是在08-11提出的，而这些翻转发生在08-07~08-09
```

### 3.2 但最新48H数据需要单独确认

```
本报告第3节的最新48H统计（08-12~08-13）显示：
  BNB近48H的3条near-miss全部被SCOUT_NO_MISSION拒绝，没有交易

这个"SCOUT_NO_MISSION"结果本身是中性的——它既可能意味着
REVERSAL_PIVOT_SCOUT已经被正确地限制（不再抢占这些候选），
也可能只是因为这3条near-miss恰好不满足任何mission的触发条件
（包括被停用后没有else分支去处理它们）

建议：下一轮报告需要明确说明REVERSAL_PIVOT_SCOUT在
     08-12~08-13这个最新窗口内的mission-level统计
     （real opens=0且shadow records>0，才是Task C生效的证据；
      如果real opens和shadow records都是0，只能说明
      没有候选触发这个mission，不能证明修复已部署）
```

### 3.3 建议动作

```
在部署本报告任何新建议之前，先运行08-11报告设计的验证脚本：

  verify_task_c_reversal_pivot_disabled(scout_decisions_log, hours=48)

确认real_opens=0 AND shadow_records>0，才能确定Task C已生效。
如果这个验证也失败（real_opens>0），说明连Task C这样相对
简单的配置开关都还没有被执行，问题的严重性比q1_trend_launch
的复杂逻辑修复更值得警惕——因为这只是一个enabled=false的操作
```

---

## 4. 方法论认可：反事实回测的合规性

### 4.1 这份报告在工程纪律上做得很好，值得作为标准范例

```
几个值得认可的具体做法：

  一、数据溯源清晰：明确说明补拉了独立分析目录，与生产data目录区分，
     且标注该目录被.gitignore忽略，不作为策略代码改动
     （这避免了"分析用数据污染生产配置"的常见问题）

  二、诚实展示失败案例：反事实规则表格里同时列出了成功案例
     （5个，MFE 2.3%-3.1%）和失败案例（3个，追单/追高/段尾），
     没有选择性地只展示支持结论的数据

  三、明确声明规则未上线：第6节标题就是"不改代码的反事实规则扫描"，
     全程强调这是研究产出，不是已部署的行为
```

### 4.2 建议将这个方法论固化为标准流程文档

```
建议把本报告第1.3节的交易安全假设声明
（"只做研究与文档输出，不修改live执行/风控/生产配置，
  所有候选规则只使用已收盘K线，不使用未来candle，
  不假设同bar成交"）提炼为一个可复用的报告模板前言，
要求未来所有归因/反事实类报告都必须包含同等级别的声明
```

---

## 5. BNB_TREND_CONTINUATION_AFTER_PULLBACK 规格精化

### 5.1 需要补充的字段：与早追失败样本的关联

```yaml
# 在原规格基础上补充
BNB_TREND_CONTINUATION_AFTER_PULLBACK:
  # ... 原有字段保持不变 ...

  # 新增：与早追失败样本建立关联，用于验证"二次确认"假设
  linkage_tracking:
    early_probe_reference_id: "关联到导致止损的早追样本的原始candidate_id"
    bars_since_early_probe_stop: int
    breakout_level_vs_early_probe_entry: "突破位相对早追入场价的位置"

  # 明确"连续两根收盘跌破突破位"的具体判定时点
  invalidation_check_timing:
    check_at: "每根新收盘K线"
    condition: "连续2根收盘价 < breakout_level"
    action_on_trigger: "candidate作废，不再等待后续反弹"
```

### 5.2 关于"early_stop_cooldown不阻止新32-bar突破"的实现细节

```python
def check_reentry_after_stop_allowed(
    symbol: str, side: str, current_bar_idx: int,
    last_stop_bar_idx: int, breakout_level: float,
    ohlcv: pd.DataFrame
) -> bool:
    """
    第8.4节提出的"二次确认机制"的具体实现
    核心：止损后的常规冷却只应阻止"立即重试同样的入场逻辑"，
         不应阻止"基于全新32-bar突破确认的独立信号"
    """
    bars_since_stop = current_bar_idx - last_stop_bar_idx

    # 常规冷却期内，但如果出现了全新的32-bar突破确认，允许豁免
    if bars_since_stop < config.get('standard_cooldown_bars', 8):
        new_breakout_confirmed = detect_new_32bar_breakout(
            ohlcv, current_bar_idx, min_bars_since_last_signal=4
        )
        if not new_breakout_confirmed:
            return False   # 常规冷却仍然生效

    return True

# 关键设计原则：豁免条件必须是"独立的新证据"（新的32-bar突破），
# 而不是简单的"时间过去了就可以重试"——否则会退化为普通冷却机制
```

### 5.3 建议的样本追踪表（用于shadow阶段积累证据）

```
时间          触发/确认        入场价    结果      与早追样本关联
────────────────────────────────────────────────────────────────
08-08 12:45/13:00  593.82   [待观察]   早追(00:00,594.45)后12.75h
08-08 14:15/14:30  594.92   [待观察]   同一段延续
08-08 18:15/18:30  595.46   [待观察]   同一段延续
08-08 19:45/20:00  596.26   [待观察]   同一段延续
08-08 21:30/21:45  598.58   [待观察]   同一段延续（偏追）

这个表格结构应该成为shadow阶段的标准记录格式，
明确标注每个候选与该symbol近期止损事件的时间关联，
用于验证"二次确认"假设是否比"首次追单"表现更好
```

---

## 6. 实施优先级重排：不要在破损管道上叠加新mission

### 6.1 明确的优先级判断

```
本报告提出的P0/P1/P2建议中：
  P0-1（禁止反转任务抢占）：需要先核查是否已部署（第3节）
  P0-2（Q1 trend launch v2加source requirement）：
    不应在q1_trend_launch基础通道仍是0转化的情况下继续叠加新逻辑
  P1（LONG_OFFSET_CONTINUATION_SCOUT/shadow，含BNB突破确认规则）：
    应该降级为P2，等基础通道问题解决后再实施

理由：当前系统已经有多个精心设计但从未真正跑起来的mission
（q1_trend_launch、Q2_PENDING_MOMENTUM、Q3_TO_Q1_CONFIRMATION，
 见08-11报告第2节）。在这个基础上再新增
 BNB_TREND_CONTINUATION_AFTER_PULLBACK，如果核心管道问题
 仍未解决，大概率会重演同样的"设计完善但0转化"模式
```

### 6.2 建议的实际优先级

```
┌──────────────────────────────────────────────────────────────┐
│ 立即（0.5天）：代码仓库直接审查，而非等下一轮报告               │
│  → 直接检查_q1_trend_launch_eligible()当前代码状态             │
│  → 直接检查Q2/Q3 pending的near_miss_min_score截断是否已修复    │
│  → 直接检查REVERSAL_PIVOT_SCOUT的enabled状态                  │
│  → 产出一份"代码现状核对表"，而非依赖日志间接推断              │
├──────────────────────────────────────────────────────────────┤
│ 1天：若发现Task A/Task C确实未部署，立即部署并验证              │
│  → 部署后用verify_task_a_pending_pipeline_fix()确认            │
│  → 部署后用verify_task_c_reversal_pivot_disabled()确认         │
│  → 两者都通过后，才认为q1_trend_launch基础管道"可用"            │
├──────────────────────────────────────────────────────────────┤
│ 验证通过后：q1_trend_launch真实转化观察期（3-5天）              │
│  → 目标：产生>=5笔真实转化，且terminal结果可评估                │
│  → 只有这个阶段通过，才考虑叠加source_requirement（S2/Q1a）    │
├──────────────────────────────────────────────────────────────┤
│ 之后：BNB_TREND_CONTINUATION_AFTER_PULLBACK作为独立shadow mission│
│  → 使用第5节精化后的规格                                       │
│  → 目标15-20笔shadow样本后评估                                 │
└──────────────────────────────────────────────────────────────┘
```

---

## 7. 路线图

```
本轮不新增详细的多阶段路线图（已在第6.2节给出清晰的四步顺序），
仅补充一条跨报告的强制要求：

下一轮报告（无论主题是什么新symbol或新mission分析）开篇必须包含：

| 检查项 | 直接代码审查结果 | 状态 |
|---|---|---|
| _q1_trend_launch_eligible()标签依赖 | [直接贴代码片段] | 已修复/未修复 |
| Q2/Q3 pending上游截断 | [直接贴代码片段] | 已修复/未修复 |
| REVERSAL_PIVOT_SCOUT enabled状态 | [直接贴配置值] | true/false/shadow_only |
| 最新q1_trend_launch转化数(48h) | [脚本输出] | 数字 |

这个表格必须基于直接的代码/配置审查，而非仅从日志行为反推——
后者正是导致"诊断了三次仍不确定是否真的修复"这个循环的原因。
```

---

*报告结束 | BNB漏选分析审查与管道问题升级 v1.0 — 2026-08-13*
*最高优先行动：暂停一切新mission开发（包括本报告设计精良的BNB突破确认规则），先做一次直接的代码仓库审查，确认q1_trend_launch/Q2 pending/REVERSAL_PIVOT_SCOUT三项此前被诊断的问题当前的真实代码状态——这比第四次通过日志行为反推更快、更可靠。*

---

## 附录 A：三个待核查问题的具体审查清单

### A.1 _q1_trend_launch_eligible() 审查清单

```
□ 打开 run_live_dry_run.py，定位当前 _q1_trend_launch_eligible() 函数
□ 确认函数体中是否还存在对 Q2_PENDING_MOMENTUM_CONFIRMED /
  Q3_TO_Q1_CONFIRMED 标签的 "in tag_list" 式硬性检查
□ 若已移除，确认替代逻辑是否正确引用了 08-04 报告设计的
  position quality约束（score/pa/fib/cvd/rr/extreme_ratio）
□ 若替代逻辑存在但从未触发，检查每个子条件的具体数值边界
  是否与当前实际分数分布（Q1的P50/P90，非理论假设）匹配
□ 记录审查发现的commit hash（若已修复）或具体阻塞代码行（若未修复）
```

### A.2 Q2/Q3 pending 上游截断审查清单

```
□ 定位 build_near_miss_payload() 的调用点
□ 确认 min_score 参数在Q2/Q3 pending创建路径上是否仍然
  硬编码使用全局 near_miss_min_score（如82），
  还是已经改为按mission各自的min_score取值
□ 若已修复，运行一次24h在线统计，确认Q2_PENDING_CREATED事件
  数量是否 > 0（而非仅确认代码逻辑，还要确认代码正在被执行到）
```

### A.3 REVERSAL_PIVOT_SCOUT 状态审查清单

```
□ 查看当前生效配置文件中 scout_micro_reversal_pivot_enabled 的实际值
  （注意：可能存在类似此前long_threshold_offset的重复键问题，
   需要用严格JSON解析确认最终生效值，而非仅看某一处的文本）
□ 若enabled=false，确认scout_micro_mission()路由逻辑中
  是否有独立的硬编码判断绕过了这个配置开关
□ 若已改为shadow_only，确认shadow记录路径本身是否正常写入
  （即使real_opens=0，也应该能看到shadow_records>0的日志）
```

### A.4 审查产出格式建议

```
建议本次审查产出一份极简的状态确认文档（而非新的分析报告），
格式类似：

  | 检查项 | 代码位置 | 当前状态 | 证据 |
  |---|---|---|---|
  | q1_trend_launch标签依赖 | run_live_dry_run.py:XXX | 已移除/未移除 | [代码片段或commit] |
  | Q2/Q3 pending截断 | 同上:XXX | 已修复/未修复 | [代码片段或commit] |
  | REVERSAL_PIVOT_SCOUT | config:XXX | disabled/shadow/active | [配置值] |

这份文档的价值在于"直接可验证"，不需要经过日志行为推断，
是本轮升级建议（第1.3节）的具体落地形式。
```

---

## 附录 B：BNB 案例对未来同类分析的参考价值

### B.1 "早追失败后二次确认"模式的普适性

```
BNB本次的核心发现——08-08 00:00早追止损，
08-08 12:45~21:45才是真正有效的延续段——
这个"早追失败、回撤后二次突破才是真正机会"的模式，
很可能不是BNB独有的特征，而是当前评分体系
（偏重状态而非行为确认）在所有targeted long symbols上
都可能重复出现的共性问题

建议：在q1_trend_launch基础管道验证通过、样本积累到位后，
     BNB_TREND_CONTINUATION_AFTER_PULLBACK规则不必局限于BNB，
     应该设计为可以应用于SOL/DOGE/HYPE等其他targeted symbols
     的通用二次确认机制，而不是逐个symbol单独开发
```

### B.2 反事实回测方法论可以标准化为工具

```
本报告手动进行的"32根收盘高点突破+成交量确认+次根收盘验证"
反事实扫描，未来可以封装为一个通用的
scripts/backtest_breakout_continuation.py工具，
接受symbol、时间窗口、突破参数作为输入，
自动产出类似本报告第6节的触发点表格

这样未来任何"某symbol行情很好但系统没选出"的疑问，
都可以先用这个工具快速验证"是否存在可识别的、
不使用未来函数的突破确认信号"，而不需要每次
重新手写一遍反事实规则的代码逻辑
```
