# 牛市漏选复盘：SHORT偏向审计与Regime通道纪律
> 2026-08-18 12:00 至 2026-08-24 19:45 | BULL_REGIME_BREAKOUT_V1 评估
> 日期：2026-08-24

---

## 目录

1. [最重要的判断：SHORT偏向应独立于"识别太晚"优先处理](#1-最重要的判断short偏向应独立于识别太晚优先处理)
2. [直接回答五个评审问题](#2-直接回答五个评审问题)
3. [全系统LONG/SHORT非对称性审计（不止Q1）](#3-全系统longshort非对称性审计不止q1)
4. [BULL_REGIME_BREAKOUT_V1设计评估](#4-bull_regime_breakout_v1设计评估)
5. [breadth参数选择：拒绝凭N=1事件拍板](#5-breadth参数选择拒绝凭n1事件拍板)
6. [第六个候选通道的纳管方式](#6-第六个候选通道的纳管方式)
7. [流程缺口：缺少上轮建议实施回顾](#7-流程缺口缺少上轮建议实施回顾)
8. [路线图](#8-路线图)

---

## 1. 最重要的判断：SHORT偏向应独立于"识别太晚"优先处理

### 1.1 两个问题的性质完全不同，不应合并处理

```
本报告的结论摘要把三层问题并列呈现：
  一、牛市识别太晚（breadth 08-19转正，q1_trend_launch 08-22才落地）
  二、主账本方向偏空（SHORT 10笔-83.19，LONG 4笔+1.25）
  三、象限规则把上涨段当成追单/噪声

但这三层的严重程度和处理路径完全不同：

  "识别太晚"是一个时效性问题——系统最终识别对了，只是慢了3天
  "方向偏空"是一个方向性问题——在确认的牛市窗口里，
  系统仍然持续开出亏钱的SHORT仓位，这不是慢，是系统性地做反了
```

### 1.2 为什么方向偏空问题更紧迫

```
如果只是"识别太晚"，解决方案是优化regime检测速度
（本报告提出的breadth门槛正是针对这一点）

但"10笔SHORT里亏了83.19，4笔LONG却赚了1.25"这个数据，
说明的是一个更根本的问题：即使在系统已经正确识别出Q1/regime
信号之后，为什么还会持续开出SHORT仓位并持续亏损？

这意味着：即使BULL_REGIME_BREAKOUT_V1把识别时机提前3天，
如果不同时解决"为什么系统在牛市里还在开SHORT"这个问题，
提前识别出来的时间窗口，很可能仍然被同样比例的SHORT亏损蚕食
```

### 1.3 建议的优先级重排

```
本报告本身建议的第一优先级是"新增regime selector"（第5节）
建议调整为：

  真正的P0应该是：审计为什么Q1/Q2/Q3的评分链路在confirmed
  bullish regime下依然会持续产出高分SHORT信号并被执行
  （而不是只在q1_trend_launch这一个通道里打补丁）

  BULL_REGIME_BREAKOUT_V1作为P1，在P0审计结果出来后，
  可以同步开发shadow版本，但不应该被当作"解决了识别太晚"
  就等于"解决了这轮亏损"的完整方案
```

---

## 2. 直接回答五个评审问题

### Q1：根因是"识别太晚+主账本偏空+Q1/Q2/Q3无regime链路"？

**同意三点都是根因，但需要按第1节调整优先级——方向偏空应该被列为最需要立即审计的一项，而非与"识别太晚"并列。**

### Q2：q1_trend_launch必须增加source/regime约束，不能只看分数？

**同意方向，但需要指出这是在一个尚未积累足够样本的通道上叠加新约束。**

```
08-18报告确认的q1_trend_launch累计样本此前只有2笔（SOL +6.25，
BNB -0.155）；本报告披露的08-22 17:45之后又新增4笔close
（LINK SHORT, XMR LONG, DOGE LONG, HYPE SHORT，净亏）

累计到本轮约6笔，仍然远低于08-18报告设定的20笔评估门槛

建议：source/regime约束的设计方向是对的（Q1状态本身不该是
     开仓理由，这是项目从08-11就开始坚持的原则），
     但落地顺序应该是：
       先让当前source_confirmed版本（08-11的S2设计）
       积累到20笔进行评估，
       再叠加regime约束（避免同时改两个变量，
       导致未来无法归因是source约束起作用还是regime约束起作用）
```

### Q3：BULL_REGIME_BREAKOUT_V1应该先做shadow/scout？

**强烈同意，且这正是本报告设计中最值得认可的部分（详见第4节）。**

### Q4：REVERSAL_PIVOT_SCOUT在bullish regime里应降级？

**需要澄清一个状态确认问题——这个mission从08-13起已经被确认enabled=false。**

```
08-18报告的"上轮建议实施回顾"表格明确写着：
  REVERSAL_PIVOT_SCOUT停用 ✅ enabled=false+部署生效
  (窗口0笔reversal开仓)

如果这个状态在08-18~08-24窗口内没有变化，那么本报告
问题4实际上在问一个已经被回答过的问题——除非：

  a) 08-18之后这个mission被重新启用（需要本报告明确说明为何）
  b) 或者本报告观察到的SHORT偏向另有来源，与REVERSAL_PIVOT_SCOUT无关
     （更符合实际情况——第1.3节和第3节的分析支持这个解读）

建议：下一轮报告需要明确注明REVERSAL_PIVOT_SCOUT在本窗口的
     真实mission-level统计（real_opens是否仍为0），
     以确认第4个问题问的究竟是"重新评估已停用的mission"
     还是"确认停用状态在regime转换后依然生效"
```

### Q5：breadth门槛5/6h还是4/6h？

**两者都不应该现在决定，见第5节。**

---

## 3. 全系统LONG/SHORT非对称性审计（不止Q1）

### 3.1 本报告已经指出的线索

```
本报告原文："Q1 仍然允许 SHORT。在上涨段里，这直接把系统推向负期望。"

这句话点出了一个此前几轮报告都没有直接触碰的问题：
  项目此前的全部努力都集中在"如何让LONG更容易通过"
  （降offset、加continuation通道、shadow验证LONG offset等）
  却没有审视"为什么SHORT在明显的regime转牛之后依然容易通过"
```

### 3.2 建议的审计范围

```python
def audit_long_short_asymmetry_in_bullish_regime(
    decisions_log: str, regime_confirmed_start: str, regime_confirmed_end: str
) -> dict:
    """
    在已确认的bullish regime窗口内（本例08-19 19:15起），
    审计各象限/各mission对SHORT信号的实际放行情况
    """
    window_decisions = filter_by_time(decisions_log, regime_confirmed_start, regime_confirmed_end)

    result = {}
    for quadrant in ['Q1', 'Q2', 'Q3', 'Q4']:
        q_decisions = [d for d in window_decisions if d['quadrant'] == quadrant]
        short_high_score = [d for d in q_decisions if d['side'] == 'SHORT' and d['score'] >= 80]
        long_high_score = [d for d in q_decisions if d['side'] == 'LONG' and d['score'] >= 80]

        result[quadrant] = {
            'short_high_score_count': len(short_high_score),
            'short_actionable_count': sum(1 for d in short_high_score if d['action'] in ('DIRECT', 'PROBE')),
            'long_high_score_count': len(long_high_score),
            'long_actionable_count': sum(1 for d in long_high_score if d['action'] in ('DIRECT', 'PROBE')),
        }

    return result

# 核心问题：在同一个已确认的bullish regime窗口内，
# 高分SHORT的"可执行率"是否显著高于高分LONG的"可执行率"？
# 如果是，说明当前SIDE_THRESHOLD_OFFSET_LONG等设计
# 只对LONG单向加了门槛，SHORT一直是"默认无额外门槛"的状态——
# 这在震荡市或熊市或许合理，但在confirmed bullish regime下
# 需要一个对称的机制来抑制SHORT
```

### 3.3 建议的对称化设计方向（先审计，再决定是否实施）

```yaml
# 仅在审计确认存在显著非对称后才考虑实施，不预先假设需要
regime_conditional_side_offset:
  enabled_only_when: "regime_state == BULLISH_CONFIRMED"
  short_threshold_offset_in_bull_regime: "待审计结果确定，可能需要正offset"
  rationale: |
    当前long_threshold_offset的设计逻辑是"默认更谨慎对待LONG"，
    这个逻辑在没有明确regime判断时是合理的默认保守立场。
    但一旦regime模块确认当前是bullish（如本次breadth门槛设计），
    对称的逻辑应该是"在bullish regime下，SHORT才是需要额外谨慎的方向"，
    而非维持一个静态的、不随regime变化的LONG专属门槛
```

---

## 4. BULL_REGIME_BREAKOUT_V1设计评估

### 4.1 设计质量认可

```
这个规则设计延续了BNB报告（08-13）建立的良好实践：
  只用已收盘K线（completed_15m_only）
  明确的量化确认条件（32bar高点+成交量+次根收盘验证+实体位置）
  安全机制包括：早追失败后要求新32bar高点、抑制REVERSAL_PIVOT_SCOUT
  路由建议：先scout/shadow，不直接主账本

这些都是过去几轮报告反复强调的正确实践，本报告全部遵循，
说明这个反事实规则设计方法论已经在项目内部形成了稳定的标准
```

### 4.2 与BNB报告规则的关系需要明确

```
08-13报告已经设计过BNB_TREND_CONTINUATION_AFTER_PULLBACK，
本报告的BULL_REGIME_BREAKOUT_V1在单symbol突破确认逻辑上
高度相似（32bar高点、成交量倍数、实体位置、上影线限制），
主要新增的是regime_gate层（多symbol breadth确认）

建议：不要把这两个规则做成两套独立实现，应该重构为：
  底层：单symbol突破确认逻辑（复用BNB报告的规格）
  上层：regime_gate作为可选的额外过滤层
       （bull_regime模式下要求breadth确认，
        非regime模式下退化为08-13报告的单symbol continuation）

这样可以避免维护两份几乎相同的突破检测代码，
且如果breadth confirmation本身有效性存疑（见第5节），
不会影响底层单symbol逻辑已经积累的验证数据
```

### 4.3 该通道加入累计样本追踪框架

```
按08-18报告建立的框架，BULL_REGIME_BREAKOUT_V1一旦开始产生
shadow样本，必须遵循相同纪律：

  少于10个样本：不使用"证明有效""识别出规律"类表述
  少于20个样本：不调整任何参数，不给予mission路由优先权
  即使6个反事实符号案例（SOL/DOGE/LINK/BNB/XLM/BCH/HYPE）
  看起来"都对"，这仍然只是N=1个regime事件下的7个同源样本，
  不是7个独立验证——它们高度相关（同一波牛市），
  不能视为7次独立的假设检验
```

---

## 5. breadth参数选择：拒绝凭N=1事件拍板

### 5.1 为什么5/6h vs 4/6h不能靠这一次牛市决定

```
本报告用来设计breadth_gate的数据，全部来自这一次牛市事件
（08-19晚到08-22的这一段行情）。用同一个事件的数据
去"验证"用哪个参数更好，本质上是同一份数据被同时用于
"发现规律"和"验证规律"，这在方法论上是循环论证——
无论选5/6还是4/6，都能在这一次事件里找到"合理"的解释
```

### 5.2 正确的验证路径

```python
def backtest_breadth_threshold_across_historical_regimes(
    symbol_universe: list[str], lookback_days: int = 180,
    breadth_thresholds_to_test: list[tuple] = [(4, 6), (5, 6), (3, 6)]
) -> dict:
    """
    在过去180天的历史数据中，识别所有"确认转为多头regime"的历史事件
    （不止这一次），分别用不同breadth门槛回测：
      - 早捕捉程度（相对于事后确认的regime起点，提前了多少）
      - 误报率（门槛触发但后续没有形成真实regime的比例）
    """
    historical_regime_events = identify_historical_bullish_transitions(
        symbol_universe, lookback_days
    )

    results = {}
    for threshold in breadth_thresholds_to_test:
        min_symbols, window_hours = threshold
        early_capture_stats = []
        false_positive_count = 0

        for event in historical_regime_events:
            trigger_time = find_breadth_trigger_time(event, min_symbols, window_hours)
            if trigger_time is None:
                continue
            lead_time = event['confirmed_regime_start'] - trigger_time
            early_capture_stats.append(lead_time)

            if not event['regime_actually_sustained']:
                false_positive_count += 1

        results[threshold] = {
            'events_captured': len(early_capture_stats),
            'avg_lead_time_hours': sum(early_capture_stats) / max(1, len(early_capture_stats)),
            'false_positive_rate': false_positive_count / max(1, len(historical_regime_events)),
        }

    return results

# 只有在至少覆盖3-5次独立的历史regime转换事件后，
# 才能对5/6 vs 4/6做出有意义的选择——
# 本次事件（08-19转牛）应该作为这个历史样本集里的第一个数据点，
# 而不是唯一的决策依据
```

### 5.3 短期内的临时处理建议

```
在完成上述历史回测之前，若急需部署BULL_REGIME_BREAKOUT_V1的shadow版本，
建议：
  使用较保守的门槛（5/6h，而非4/6h）
  理由：shadow阶段的误报成本很低（不实际开仓），
       但如果breadth判断过于宽松（4/6h），会导致regime_gate
       形同虚设，退化为普通的单symbol突破确认，
       无法验证"breadth确认"这个新增维度本身是否有额外价值

  同时并行运行两个门槛的shadow记录（5/6h和4/6h各一份），
  为将来的历史回测提供更多这次事件内部的对照数据
  （虽然仍是N=1事件，但至少能观察两个门槛在这唯一一次
  事件中的具体差异，作为历史回测的补充参考）
```

---

## 6. 第六个候选通道的纳管方式

### 6.1 当前通道数量已经不少

```
截至本轮，项目内已经存在或正在提议的实验性mission包括：
  q1_trend_launch（含source约束）
  Q2_PENDING_MOMENTUM
  Q3_TO_Q1_CONFIRMATION
  HIGH_SCORE_LONG_OFFSET_PROBE
  BNB_TREND_CONTINUATION_AFTER_PULLBACK（08-13提出，状态未知）
  BULL_REGIME_BREAKOUT_V1（本轮提出）

六个通道，每个都在各自的样本积累期，这本身对"哪个通道占用了
多少mission路由优先级""是否存在通道间抢占候选"这类协调问题
提出了更高的管理要求
```

### 6.2 建议：在新增BULL_REGIME_BREAKOUT_V1之前，先确认现有通道的路由协调

```
问题：如果同一个候选（比如某个符号的高分LONG信号）同时满足
     q1_trend_launch的source条件和BULL_REGIME_BREAKOUT_V1的
     breakout条件，当前系统如何决定路由给哪一个？

这个问题在通道数量还少时不明显，但六个通道并存后，
路由冲突的复杂度会明显上升。建议在部署BULL_REGIME_BREAKOUT_V1
之前，先产出一份完整的mission路由优先级表和互斥规则，
而不是每次新增一个mission时零散地补充"suppress XXX on this sample"
这类局部规则
```

### 6.3 统一的累计追踪器扩展

```
延续08-18报告设计的ChannelCumulativeTracker，
新增BULL_REGIME_BREAKOUT_V1（及若已启动的BNB通道）：

| 通道 | 累计样本 | 累计PnL | 距20笔评估门槛还差 |
|---|---:|---:|---:|
| q1_trend_launch | ~6 | 净负(需精确数字) | 14 |
| Q2_PENDING_MOMENTUM | ~15-18 | -3.7378(累计) | 2-5 |
| Q3_TO_Q1_CONFIRMATION | ~3-6 | 待更新 | 14-17 |
| HIGH_SCORE_LONG_OFFSET_PROBE | ~11-12 | -1.3389(本窗口mission close 6笔) | 8-9 |
| BNB_TREND_CONTINUATION | 0(shadow未知) | — | 20 |
| BULL_REGIME_BREAKOUT_V1 | 0(新提出) | — | 20 |

建议：下一轮报告必须包含这张完整表格的更新版本，
而不是只报告本轮新增的通道数据
```

---

## 7. 流程缺口：缺少上轮建议实施回顾

### 7.1 本报告未包含08-04报告要求的强制字段

```
08-04报告第8.3节明确要求：每份归因报告开篇必须包含
"上轮建议实施回顾"表格，列出上一轮P0/P1建议的实施状态

本报告（08-24）没有包含这个表格，直接跳到新的分析内容。
考虑到08-18报告刚刚才因为遵循这个协议、验证了四项修复
全部落地生效，本轮报告应该同样确认：

  08-18报告的P0-1（mirror降级为shadow-only）是否已部署？
  08-18报告提出的ChannelCumulativeTracker是否已建立？
  08-18报告的SAMPLE_SIZE_DECISION_RULES是否被遵循
  （本报告中HIGH_SCORE_LONG_OFFSET_PROBE的"仍是负期望，
   样本数也还不够"这句表述符合纪律，但没有明确引用
   累计样本数字，无法确认是否真的在追踪）
```

### 7.2 建议立即补充

```
下一轮报告的开篇，应包含：

| 08-18建议 | 优先级 | 实施状态 |
|---|---|---|
| mirror A/B降级为shadow-only | P0 | ？需确认 |
| ChannelCumulativeTracker建立 | P0 | ？需确认 |
| 20笔评估门槛纪律执行 | 持续 | 部分体现，需明确数字 |

这不是形式主义要求——本项目已经用四轮报告的血泪教训
（08-04到08-18）证明了这个表格能防止问题被反复诊断
却不落地。停止使用它的风险不应该被低估。
```

---

## 8. 路线图

```
┌──────────────────────────────────────────────────────────────┐
│ 立即（0.5-1天）：SHORT偏向审计（新P0，优先于新mission开发）      │
│  → 运行audit_long_short_asymmetry_in_bullish_regime()          │
│  → 明确回答：Q1/Q2/Q3是否存在SHORT默认无门槛而LONG有门槛的       │
│    结构性非对称，还是仅Q1如此                                   │
│  → 若确认非对称，设计regime_conditional_side_offset（第3.3节）  │
├──────────────────────────────────────────────────────────────┤
│ 并行（0.5天）：流程缺口补齐                                      │
│  → 补充"上轮建议实施回顾"表格（第7.2节）                        │
│  → 核实08-18的mirror降级和ChannelCumulativeTracker状态          │
├──────────────────────────────────────────────────────────────┤
│ 1-2天：mission路由协调 + BULL_REGIME_BREAKOUT_V1 shadow部署     │
│  → 先产出六通道路由优先级/互斥规则表（第6.2节）                  │
│  → 部署BULL_REGIME_BREAKOUT_V1 shadow版本，                    │
│    并行记录5/6h和4/6h两个门槛（第5.3节）                       │
│  → 复用BNB报告的单symbol突破逻辑，避免重复实现（第4.2节）        │
├──────────────────────────────────────────────────────────────┤
│ 持续：历史breadth门槛回测（非阻塞，可与shadow并行）              │
│  → 覆盖过去180天的历史regime转换事件                            │
│  → 为5/6 vs 4/6提供超越N=1事件的证据基础                        │
├──────────────────────────────────────────────────────────────┤
│ 20笔shadow样本后：BULL_REGIME_BREAKOUT_V1正式评估               │
│  → 遵循08-18建立的纪律，不提前下结论                            │
└──────────────────────────────────────────────────────────────┘
```

---

## 9. 一句话结论

```
这份报告最有价值的一句话，是它自己写下却没有充分展开的：
"Q1 仍然允许 SHORT"。

过去几轮报告的全部注意力都在"如何让LONG更容易通过"上——
校准offset、设计continuation通道、shadow验证——
但从未系统性审视"为什么SHORT在confirmed bullish regime下
依然畅通无阻"。这次10笔SHORT亏83.19、4笔LONG赚1.25的数据，
应该被当作一个信号：下一步最紧迫的不是再新增一个
"更早识别牛市"的通道，而是先搞清楚系统当前的方向性默认设置
本身是否存在从未被审计过的结构性偏向。
```

---

*报告结束 | 牛市漏选复盘：SHORT偏向审计与Regime通道纪律 v1.0 — 2026-08-24*
*最高优先行动：运行全系统LONG/SHORT非对称性审计（第3.2节），这应该先于BULL_REGIME_BREAKOUT_V1的开发——提前识别牛市却依然在系统性做空，比识别得晚更值得立即处理。*
