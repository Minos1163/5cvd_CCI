# 四象限进攻失效归因建议报告
> 2026-07-22 21:30 至 2026-07-27 | 窄通道实验设计与工程修复
> 日期：2026-07-27

---

## 目录

1. [核心诊断](#1-核心诊断)
2. [回答五个评审问题](#2-回答五个评审问题)
3. [P0：SCOUT 可观测性修复](#3-p0scout-可观测性修复)
4. [窄通道一：CONTINUATION_LONG_OFFSET_SCOUT](#4-窄通道一continuation_long_offset_scout)
5. [窄通道二：REVERSAL_PIVOT_SCOUT](#5-窄通道二reversal_pivot_scout)
6. [窄通道三：SYMBOL_POLICY_REVIEW_SHADOW](#6-窄通道三symbol_policy_review_shadow)
7. [Q4 防御退出反事实分析](#7-q4-防御退出反事实分析)
8. [数据健康退化调查](#8-数据健康退化调查)
9. [验收标准与熔断机制](#9-验收标准与熔断机制)
10. [路线图与禁止事项](#10-路线图与禁止事项)

---

## 1. 核心诊断

### 1.1 本报告最重要的一句话结论

```
四象限标签回答的是"当前环境好不好"，
不回答"现在这个方向、这个位置、这个时机是否该开仓"。

Q1（趋势强+资金强）595 个样本，主账本只有 1 笔成交。
不是执行链路堵塞，是 Q1 内部的 RR（1.16/8）和 Fib（9.00/18）
本来就在告诉系统"环境好，位置不好"。
```

### 1.2 三个独立但相互印证的证据链

```
证据链 A（象限内部结构）：
  Q1 CVD=18.00（满分），CCI=10.10（中等），但 RR=1.16/8，Fib=9.00/18
  → Q1 是"资金流向对，入场位置错"的组合

证据链 B（拐点方向准确率）：
  183 个后验拐点，系统方向匹配仅 56 次（30.6%）
  Q1 拐点 28 个，匹配仅 2 次（7.1%）
  Q3 拐点 31 个，匹配仅 3 次（9.7%）
  → 在强动能象限（Q1/Q3），系统几乎总是在拐点处方向做反

证据链 C（放宽验证已被证伪）：
  A/B 镜像账本（27+27 笔）：legacy PF 0.0291，trend_capture PF 0.0498
  两者均远低于 1.0，证明"多开仓+改出场"不能挽救糟糕的入场
  → 出场优化的天花板由入场质量决定，当前入场质量是负数级别
```

### 1.3 诊断与上一轮建议的关系

```
上一轮建议的核心目标：修复 RR 公式 + 提高开仓频率
本轮观察到的结果：Q1 RR 平均分依然只有 1.16/8

这不是修复失败，而是修复方向不完全对：
  RR 计算问题确实存在（费用占比、TP1 距离）
  但即使 RR 公式修复，Q1 本身的入场时机问题（拐点误判）依然存在
  两个问题需要分别解决，不能用同一个改动覆盖
```

---

## 2. 回答五个评审问题

### Q1：Q1/Q3 方向判断是否需要独立反转/衰竭模型？

**答：是，且这是本轮最高优先级的架构缺口。**

```
当前架构的方向来源：
  1h direction_from_history（趋势延续假设）
  15m trigger（动量延续假设）

这两个来源共享同一个假设："过去在动，未来继续往同一方向动"

问题：
  拐点处，恰好是"过去的动能"和"未来的方向"分道扬镳的时刻
  Q1/Q3 的高分恰恰来自"过去动能强"，因此在拐点处最容易给出错误方向

需要的不是修改现有方向判断，而是新增一个独立的正交判断层：
  衰竭确认（CCI 从极值回落 + 连续减弱）
  反向确认K线（收盘突破最近反向确认位）
  CVD 不再支持原方向

这正是 REVERSAL_PIVOT_SCOUT 要解决的问题（见第 5 节）
它不修改 Q1/Q3 的现有评分，而是作为独立通道运行
```

### Q2：LONG offset 应改为静态硬拦截 + 窄通道，还是继续全局 offset？

**答：改为"全局保守 + 窄通道精准"的双层结构，而非二选一。**

```
证据支持：
  LONG offset near-miss 25 个，平均 MFE 0.64%，MFE≥1% 有 4 个，MAE≤-1% 有 6 个
  这是一个"少数强、多数弱"的分布，全局放开会引入更多 MAE≤-1% 的样本

正确处理：
  全局 LONG offset +10（或 strict 配置的 +7）保持不变
  新增 CONTINUATION_LONG_OFFSET_SCOUT 通道（第 4 节），
  只针对特定标的簇（BCH/CC/HYPE/SOL）+ 严格附加条件开放小额验证

这不是"改阈值"，是"在阈值之外开一个可关闭的实验窗口"
全局阈值继续保护账本，窄通道验证假设
```

### Q3：Q4_DEFENSIVE_EXIT 是必要风控还是掩盖了 trend_capture 真实表现？

**答：两者都是，需要反事实账本才能区分，不能单靠现有 A/B 数据判断。**

```
现状：18/27（legacy）和 18/27（trend_capture）都被 Q4_DEFENSIVE_EXIT 关闭
这个比例（66.7%）异常高，需要拆解：

情况 A（Q4 退出是正确的）：
  若这 18 笔如果不退出，后续都进一步恶化 → Q4 退出是正确风控

情况 B（Q4 退出过早）：
  若这 18 笔中有相当比例后续出现盈利路径（TP1+）→ Q4 退出扼杀了 trend_capture 的价值

当前 A/B 数据无法区分这两种情况，因为退出已经发生，后续路径未被记录
必须新增反事实账本（第 7 节）才能回答这个问题
```

### Q4：ZEC/XRP 的 SYMBOL_BLACKLISTED 样本是否足以启动 shadow policy review？

**答：5 个样本不足以做出决策，但表现足以启动为期 14 天的正式 shadow 复核（而非直接解除）。**

```
5 个 near-miss 平均 MFE 1.61%，中位 1.80%，是全部分组中表现最好的
但样本量过小（n=5），且都集中在 07-24 附近（时间聚集，非独立样本）

正确行动：
  不是"看到 5 个好样本就解除黑名单"
  是"5 个好样本给了启动 14 天正式复核的理由"

区别在于：
  启动复核 = 开始系统性收集 shadow 数据，不改变当前黑名单状态
  解除黑名单 = 立即让 ZEC/XRP 重新进入主账本，风险敞口重新打开

本报告建议启动复核（第 6 节 SYMBOL_POLICY_REVIEW_SHADOW），不建议解除
```

### Q5：data_health=DEGRADED 期间，哪些实验可以继续，哪些必须暂停？

**答：只读、不影响资金的实验（shadow track、后验分析）可以继续；任何涉及主账本或 SCOUT 实际下单的通道必须暂停，直到退化原因查明。**

```
可以继续（不受 DEGRADED 影响）：
  near-miss 事后 MFE/MAE 分析（本报告第 4 章方法论）
  拐点后验研究
  SYMBOL_POLICY_REVIEW_SHADOW（纯 shadow，不下单）
  REVERSAL_PIVOT_SCOUT 的候选记录（先只记录，不实际开仓）

必须暂停（直到 data_health=OK 持续 24h）：
  任何新窄通道的实际 SCOUT 下单
  CONTINUATION_LONG_OFFSET_SCOUT 的实盘验证阶段
  A/B 自动切换（本身已因样本不足未触发，保持关闭）

理由：
  DEGRADED 状态下不确定是数据延迟、缺失还是错误
  若基于错误数据做出"某窄通道有效"的结论，后续修正成本远高于多等 24-48 小时
```

---

## 3. P0：SCOUT 可观测性修复

### 3.1 问题的严重性

```
本窗口最大的工程缺口：
  near-miss 中存在 scout_candidate=true 和 scout_tags 字段
  但 scout_micro/paper_trades.jsonl 完全没有对应事件（0 开 0 平）

这意味着：
  配置层面 scout_micro_q1_rr_gap_enabled=true 等开关全部显示"已启用"
  但没有任何证据表明代码路径真的从"候选识别"走到了"决策"

这是一个黑箱：无法区分三种可能性：
  可能性 A：任务门槛过窄，所有候选都被内部逻辑拒绝
  可能性 B：预算/熔断机制过度保守，候选达标但被外层拦截
  可能性 C：代码路径存在缺陷，候选根本没有传递到 SCOUT ledger
```

### 3.2 修复规格：scout_decisions.jsonl

```python
@dataclass
class ScoutDecisionRecord:
    """每个 SCOUT 候选的完整生命周期记录"""
    timestamp:       datetime
    symbol:          str
    side:            str
    mission:         str      # 'Q1_RR_GAP' | 'Q2_PENDING' | 'Q3_TO_Q1' | 'REVERSAL_PIVOT'

    candidate:       bool     # 是否被识别为候选
    candidate_score: float
    candidate_reason: str     # 触发候选的原始 gate 原因

    accepted:        bool     # 是否被 SCOUT 接受
    reject_reason:   str      # 若拒绝，原因（见下方枚举）

    budget_state:    dict     # {"used": int, "limit": int, "remaining": int}
    mission_stop_circuit_state:  str   # 'ACTIVE' | 'TRIPPED' | 'COOLING_DOWN'
    war_fund_state:  dict     # {"available": float, "allocated": float}
    position_conflict_state: str  # 'NONE' | 'SYMBOL_CONFLICT' | 'MAX_SCOUT_POSITIONS'

    pending_created:   bool = False
    pending_confirmed: bool = False
    pending_expired:   bool = False

# reject_reason 枚举（必须覆盖所有拒绝路径）
class ScoutRejectReason(str, Enum):
    BUDGET_EXHAUSTED         = "BUDGET_EXHAUSTED"
    MISSION_CIRCUIT_TRIPPED  = "MISSION_CIRCUIT_TRIPPED"
    WAR_FUND_INSUFFICIENT    = "WAR_FUND_INSUFFICIENT"
    POSITION_CONFLICT        = "POSITION_CONFLICT"
    CANDIDATE_SCORE_TOO_LOW  = "CANDIDATE_SCORE_TOO_LOW"
    MISSION_DISABLED         = "MISSION_DISABLED"
    NONE                     = ""   # 已接受
```

### 3.3 集成逻辑（依次检查，第一个失败即记录返回）

```python
def process_scout_candidate(candidate, mission_config, scout_state) -> ScoutDecisionRecord:
    """每个 near-miss 候选都必须经过此函数，无论最终是否开仓"""
    record = ScoutDecisionRecord(
        timestamp=now(), symbol=candidate['symbol'], side=candidate['side'],
        mission=candidate['mission'], candidate=True,
        candidate_score=candidate['score'], candidate_reason=candidate['gate_reason'],
        budget_state=scout_state.get_budget_snapshot(candidate['mission']),
        mission_stop_circuit_state=scout_state.get_circuit_state(candidate['mission']),
        war_fund_state=scout_state.get_war_fund_snapshot(),
        position_conflict_state=scout_state.check_position_conflict(candidate['symbol']),
    )

    checks = [
        (scout_state.is_mission_disabled(candidate['mission']), ScoutRejectReason.MISSION_DISABLED),
        (record.mission_stop_circuit_state == "TRIPPED", ScoutRejectReason.MISSION_CIRCUIT_TRIPPED),
        (record.budget_state['remaining'] <= 0, ScoutRejectReason.BUDGET_EXHAUSTED),
        (record.position_conflict_state != "NONE", ScoutRejectReason.POSITION_CONFLICT),
    ]
    for failed, reason in checks:
        if failed:
            record.accepted, record.reject_reason = False, reason
            return log_and_return(record)

    record.accepted, record.reject_reason = True, ScoutRejectReason.NONE
    return log_and_return(record)  # 通过 → 进入 SCOUT ledger 实际开仓流程
```

### 3.4 修复验证清单

```
修复完成后的验证标准（P0 完成的定义）：

□ scout_decisions.jsonl 每 15m 周期都有新记录（即使 accepted=false）
□ 每条 near-miss（scout_candidate=true）都能在 scout_decisions.jsonl 中找到对应条目
□ 若连续 24h scout_decisions 显示全部 accepted=false，
  reject_reason 分布应能清楚指向具体瓶颈（预算/熔断/冲突/门槛）
□ 若 reject_reason 中 MISSION_CIRCUIT_TRIPPED 占比 > 50%，
  需要复核熔断触发条件是否过度敏感
□ 若 reject_reason 分布均匀且无主导原因，需要复查代码路径是否遗漏调用
```

---

## 4. 窄通道一：CONTINUATION_LONG_OFFSET_SCOUT

### 4.1 目标假设

```
假设：LONG offset 全局阈值对"高分+强流入+特定标的簇"的多头信号过度保守
验证方法：只对满足严格附加条件的候选开放小额 SCOUT 验证
```

### 4.2 准入条件（全部满足，AND 关系）

```yaml
continuation_long_offset_scout:
  side: LONG
  primary_reason: SIDE_THRESHOLD_OFFSET_LONG_10.00

  quadrant: [Q1, Q3]

  score_min: 82
  flow_cvd_confirmation_min: 18       # CVD 必须满分（已在 Q1/Q3 定义中隐含）
  price_action_structure_min: 18      # 结构分要求高（vs 普通 DIRECT 的 6）
  fibonacci_location_min: 15          # 位置分要求高（vs 普通 DIRECT 的 6）
  risk_reward_geometry_min: 0.1       # RR 大于 0 且非结构性拒绝
  rr_zero_reason_exclude: ["OPPOSITION_STRUCTURE_TOO_CLOSE"]

  symbol_whitelist: ["BCHUSDT", "CCUSDT", "HYPEUSDT", "SOLUSDT"]
  # 仅这四个标的开放，因为它们是 near-miss 后验中出现正 MFE 的簇

  q3_additional_requirement:
    # Q3 候选额外要求：3 根 K 线内确认转为 Q1，或出现独立结构确认
    must_transition_to_q1_within_bars: 3
    or_structure_confirmation: true
```

### 4.3 执行约束

```yaml
execution_constraints:
  ledger: SCOUT_ONLY           # 不进主账本
  position_size_usdt: [25, 50]
  leverage: 1
  max_concurrent: 2

  promotion_rule:
    min_samples_before_review: 20
    min_samples_before_promotion: 50

  circuit_breaker:
    pf_threshold: 1.0            # 20 笔后 PF < 1.0 → 暂停复核
    consecutive_stop_limit: 3    # 连续 3 次初始止损 → 暂停 12 小时

  required_fields_per_trade:
    [side_flip_check, pre_signal_quadrant, entry_quadrant, confirmation_bars_used]
```


### 4.4 与 REVERSAL_PIVOT_SCOUT 的边界

```
CONTINUATION_LONG_OFFSET_SCOUT 假设："这是真实趋势延续，只是被 offset 误伤"
REVERSAL_PIVOT_SCOUT 假设：       "这是趋势末端，需要独立反转确认"

同一个候选不应同时进两个通道。分流规则：

  if candidate.side == "LONG" and candidate.reason == "LONG_OFFSET":
      if is_at_or_near_recent_pivot(candidate):
          route_to = "REVERSAL_PIVOT_SCOUT"   # 优先反转通道
      else:
          route_to = "CONTINUATION_LONG_OFFSET_SCOUT"
```

---

## 5. 窄通道二：REVERSAL_PIVOT_SCOUT

### 5.1 核心假设

```
假设：系统在 Q1/Q3 强动能象限的拐点附近，方向判断准确率远低于随机（7-10%）
      需要一个独立于现有方向模型的反转确认层，专门捕捉动能衰竭后的确认反转
```

### 5.2 入场候选识别规则（五个条件，AND 关系）

```python
def detect_reversal_pivot_candidate(ohlcv, current_side_signal, cci_series, cvd_series, config):
    """识别"动能衰竭后确认反转"的候选，与现有 continuation 逻辑独立运行"""

    # 条件 1：最近 6 根 15m K 线出现局部极端波动或长影线
    if not detect_extreme_move_or_wick(ohlcv.iloc[-6:], atr=compute_atr(ohlcv, 14).iloc[-1]):
        return None

    # 条件 2：CCI 从极值回落，或连续 2 根 K 线动能减弱
    cci_now, cci_3ago = cci_series.iloc[-1], cci_series.iloc[-4]
    if current_side_signal == "LONG":
        cci_weakening = cci_now < cci_3ago and cci_3ago > 100
    else:
        cci_weakening = cci_now > cci_3ago and cci_3ago < -100
    if not cci_weakening:
        return None

    # 条件 3：CVD 不再支持原方向
    cvd_slope = (cvd_series.iloc[-1] - cvd_series.iloc[-4]) / (abs(cvd_series.iloc[-4]) + 1e-9)
    if current_side_signal == "LONG" and cvd_slope > 0.02:   return None
    if current_side_signal == "SHORT" and cvd_slope < -0.02: return None

    # 条件 4：价格收盘突破最近 2 根 K 线的反向确认位
    reversal_side = "SHORT" if current_side_signal == "LONG" else "LONG"
    confirmation_level = ohlcv.iloc[-3:-1]['low' if reversal_side == "SHORT" else 'high']
    close = ohlcv['close'].iloc[-1]
    confirmed = (close < confirmation_level.min()) if reversal_side == "SHORT" \
                else (close > confirmation_level.max())
    if not confirmed:
        return None

    # 条件 5：原 continuation 方向被特定原因拦截（系统已识别环境不佳）
    valid_block_reasons = {"FIB_EXTENSION_EXHAUSTION_BLOCK", "REVERSAL_WICK_DISCOUNT",
                            "PROXIMITY_TO_SUPPORT_BLOCK", "ANTI_EXHAUSTION_SEVERE"}
    if get_last_gate_reason(current_side_signal) not in valid_block_reasons:
        return None

    return ReversalPivotCandidate(
        symbol=ohlcv.attrs.get('symbol'), side=reversal_side,
        pivot_setup_type="EXHAUSTION_REVERSAL", confirmation_bars=2,
        pre_pivot_quadrant=get_current_quadrant(current_side_signal),
        entry_quadrant=get_current_quadrant(reversal_side),
    )
```

### 5.3 执行约束

```yaml
reversal_pivot_scout:
  ledger: SCOUT_ONLY
  position_size_usdt: [25, 50]
  leverage: 1

  stop_placement: "beyond_confirmation_bar_extreme"
  # 止损设在确认K线的局部高/低点之外，而非固定 ATR 倍数

  promotion_gate:
    min_samples_before_evaluation: 20
    min_samples_before_promotion: 50
    direction_accuracy_target: 0.45   # 目标方向命中率 > 45%（vs 当前 7-10%）
    pf_target: 0.9

  circuit_breaker:
    pf_threshold_at_50: 0.7
    pause_hours_on_trip: 12

  required_logging_fields:
    - pivot_setup_type
    - confirmation_bars
    - pre_pivot_quadrant
    - entry_quadrant
    - side_flip                # 与原方向是否相反
```

### 5.4 预期收益的量化基础

```
本窗口后验数据支持：

  183 个拐点，未来平均运动幅度约 1.42%-1.49%（各象限接近）
  系统当前方向匹配率仅 30.6%
  若 REVERSAL_PIVOT_SCOUT 能将方向匹配率提升至 45%+
  即使胜率不到 50%，配合 1:1.5 以上盈亏比，仍可能产生正期望

  这个通道的价值不在于"抓住所有拐点"
  而在于"当现有 continuation 逻辑明确失效时（被 exhaustion/wick 类原因拦截），
  提供一个独立视角重新评估方向"
```

---

## 6. 窄通道三：SYMBOL_POLICY_REVIEW_SHADOW

### 6.1 复核范围

```
标的：ZECUSDT、XRPUSDT（当前黑名单）
观察期：14 天
性质：纯 shadow track，不影响主账本或 SCOUT 实际持仓
```

### 6.2 Shadow 记录规格（复用既有设计并强化）

```python
@dataclass
class SymbolPolicyShadowRecord:
    symbol: str; signal_time: datetime; side: str; score: float
    quadrant: str; component_scores: dict

    shadow_entry_price: float
    shadow_stop_price:  float
    shadow_tp_prices:   list[float]

    # 结果（周期性更新）
    resolution:      str = ""   # TP1_HIT / TP2_HIT / TP3_HIT / STOP_HIT / TIMEOUT
    shadow_pnl_pct:  float = 0.0
    mfe_4h_pct:      float = 0.0
    mae_4h_pct:      float = 0.0
```


### 6.3 晋级/维持/延长的量化标准

```
14 天后的三种结果：

结果 A（晋级为观察名单，非直接解除黑名单）：
  条件：shadow 样本数 ≥ 20，PF > 1.0，MAE ≤ -1% 的比例 < 40%
  行动：ZEC/XRP 从 blacklist 移至 observation_only
        允许小额 PROBE（而非直接恢复完整 DIRECT 权限）

结果 B（维持黑名单，继续复核）：
  条件：样本不足 20 个，或指标接近边界（PF 0.8-1.0 之间）
  行动：延长复核期至 28 天，不改变当前状态

结果 C（强化黑名单依据）：
  条件：PF < 0.7，或 MAE ≤ -1% 的比例 > 50%
  行动：记录复核结论，暂停复核（除非未来出现结构性变化，如新流动性事件）
```

### 6.4 与本窗口证据的衔接

```
本窗口 5 个 SYMBOL_BLACKLISTED near-miss：
  平均 MFE 1.61%，中位 1.80%，表现优于所有其他分组

这 5 个样本不足以做决策，但作为 14 天复核的起点数据点，
应该被纳入同一个 shadow track 数据集，而非重新开始计数

实现：
  将本报告中已识别的 5 个 near-miss（07-24 附近的 ZEC 样本）
  直接作为 shadow_decisions 表的历史记录导入
  14 天复核窗口从这些样本的信号时间开始计算，而非本报告提交时间
```

---

## 7. Q4 防御退出反事实分析

### 7.1 反事实账本设计

```python
@dataclass
class CounterfactualLedger:
    """
    与 A/B 账本平行运行，记录"若不触发 Q4_DEFENSIVE_EXIT 会怎样"
    只用于分析，不影响任何实际持仓或风控决策
    """
    base_ledger_name: str        # "legacy" or "trend_capture"
    positions: dict[str, CounterfactualPosition]

@dataclass
class CounterfactualPosition:
    symbol:             str
    side:               str
    entry_price:        float
    entry_time:         datetime
    actual_exit_time:   datetime      # 真实账本中 Q4 退出的时间
    actual_exit_reason: str           # "Q4_DEFENSIVE_EXIT"

    # 反事实延续（假设不退出，继续跟踪至 TP/SL/timeout）
    cf_resolution:      str = ""      # TP1_HIT / TP2_HIT / TP3_HIT / STOP_HIT / TIMEOUT
    cf_resolution_time: datetime = None
    cf_pnl_pct:         float = 0.0
    cf_max_favorable_r: float = 0.0
    cf_max_adverse_r:   float = 0.0
```

### 7.2 分析产出

```
14 天后（或累计 ≥ 30 个 Q4 退出样本后）生成对比报告：

  实际 Q4 退出的样本数：N
  反事实继续持有后达到 TP1+ 的比例：X%
  反事实继续持有后达到更深止损（比 Q4 退出时更差）的比例：Y%

  判断规则：
  若 X% > 40%：Q4_DEFENSIVE_EXIT 可能过早，掩盖了 trend_capture 的真实能力
              → 建议为 trend_capture 账本单独放宽 Q4 退出条件，重新对比
  若 X% < 20% 且 Y% > 50%：Q4_DEFENSIVE_EXIT 是必要且有效的风控
              → 维持现状，A/B 的低 PF 归因于入场质量，而非出场机制
```

---

## 8. 数据健康退化调查

### 8.1 优先级说明

```
07-23 起持续 DEGRADED，这个状态本身可能污染本报告的部分结论：

需要立即核实：
  DEGRADED 期间的 Q1/Q3 evaluate_entry_chain 输入数据是否完整
  DEGRADED 是否只影响部分标的（若是，near-miss 样本可能存在标的偏差）
  DEGRADED 是否与 07-23 后决策量激增（455→1555→2658...）有关
  （决策量增长可能意味着更多标的被纳入扫描，或警报阈值发生了变化）
```

### 8.2 调查清单

```
□ 检查 data_health 退化的具体子系统（K线延迟/缺失/API限流/其他）
□ 对比 DEGRADED 前后（07-22 vs 07-23+）的 warmup ready 标的数量
□ 检查退化是否与本轮新增的 SCOUT/Q1绿色通道/A-B镜像账本部署时间吻合
  （若吻合，可能是新增模块引入的性能问题，而非外部数据源问题）
□ 在 DEGRADED 解决前，为本报告中所有基于 07-23 后数据的结论
  标注"待数据健康确认后复核"
```

---

## 9. 验收标准与熔断机制

### 9.1 四个通道的统一验收框架

```
通道                          最小样本  成功阈值           失败/暂停阈值
──────────────────────────────────────────────────────────────────
SCOUT 可观测性修复             N/A      每周期都有记录      连续24h无记录
CONTINUATION_LONG_OFFSET      20笔     PF>1.0, MFE/MAE>1.5  PF<0.8或连续3次止损
REVERSAL_PIVOT_SCOUT          30笔     方向命中率>45%,PF>0.9 30笔后PF<0.7
SYMBOL_POLICY_REVIEW_SHADOW   20样本   PF>1.0,MAE≤-1%<40%   MAE≤-1%>50%
```

### 9.2 全局熔断条件（任一触发，暂停所有窄通道实验）

```
条件 1：data_health 连续 48h 无法恢复 OK
条件 2：任意窄通道触发熔断后，24h 内未完成归因分析
条件 3：主账本（非窄通道）出现任何非预期的大额亏损事件
条件 4：SCOUT 可观测性修复后，reject_reason 分布显示系统性缺陷
        （例如 MISSION_CIRCUIT_TRIPPED 占比持续 > 80%）
```

---

## 10. 路线图与禁止事项

### 10.1 实施顺序

```
┌──────────────────────────────────────────────────────────────┐
│ Phase 0（立即，1-2天）：可观测性与诊断                        │
│  → 实现 scout_decisions.jsonl（第 3 节）                      │
│  → 调查 data_health DEGRADED 根因（第 8 节）                  │
│  → 导入历史 5 个 ZEC near-miss 至 shadow track（第 6.4 节）   │
├──────────────────────────────────────────────────────────────┤
│ Phase 1（3-5天，需 data_health=OK）：窄通道启动                │
│  → 启动 SYMBOL_POLICY_REVIEW_SHADOW（纯 shadow，无数据依赖）  │
│  → 启动 REVERSAL_PIVOT_SCOUT 候选记录（先只记录，暂不下单）   │
│  → 启动反事实账本（第 7 节），与现有 A/B 并行记录             │
├──────────────────────────────────────────────────────────────┤
│ Phase 2（data_health=OK 确认后）：实际验证                    │
│  → REVERSAL_PIVOT_SCOUT 开始实际 SCOUT 下单                  │
│  → CONTINUATION_LONG_OFFSET_SCOUT 开始实际 SCOUT 下单         │
│  → 两个通道独立累积至各自最小样本量                            │
├──────────────────────────────────────────────────────────────┤
│ Phase 3（14-30天后）：评估与决策                              │
│  → 基于验收标准评估三个窄通道是否晋级                          │
│  → 基于反事实账本决定 Q4_DEFENSIVE_EXIT 是否需要调整           │
│  → 基于 shadow policy review 决定 ZEC/XRP 状态                │
└──────────────────────────────────────────────────────────────┘
```

### 10.2 禁止事项

```
❌ 不要在 data_health=DEGRADED 期间启动任何实际下单的新通道
❌ 不要解除 ZEC/XRP 黑名单（无论 shadow 数据多好，先移至 observation_only）
❌ 不要全局放宽 RR 阈值（RR gap near-miss 已证明无正 MFE 支持）
❌ 不要在 SCOUT 可观测性未修复前评估任何"任务是否有效"的结论
❌ 不要用 Q1 绿色通道的现有逻辑处理拐点附近的信号
   （必须路由至 REVERSAL_PIVOT_SCOUT 独立评估）
❌ 不要同时启动全部三个窄通道并放松验收标准
   （每个通道独立熔断，不互相借用样本量或延长复核期）
```

### 10.3 本轮最重要的单一判断

```
上一轮的教训是：更多开仓 ≠ 更好结果（A/B 数据已经证明）
本轮的教训应该是：更多象限标签 ≠ 更准确的方向判断

四象限系统的真正价值在于筛选"环境"，
但环境好不等于时机对，尤其是在动能即将衰竭的时刻。

下一轮的核心任务不是让 Q1 开更多仓，
而是在 Q1/Q3 内部，把"动能延续"和"动能衰竭"两种情况分离开——
这正是 REVERSAL_PIVOT_SCOUT 存在的意义。
```

---

*报告结束 | 四象限进攻失效归因建议 v1.0 — 2026-07-27*
*最高优先行动：Phase 0 的 scout_decisions.jsonl 实现 + data_health 根因排查。没有这两项，后续所有窄通道实验的结果都无法被正确归因。*
