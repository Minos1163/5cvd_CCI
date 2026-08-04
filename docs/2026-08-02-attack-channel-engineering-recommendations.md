# 窄通道工程化建议报告
> 2026-07-27 15:00 至 2026-08-02 20:30 | Task A-E 详细规格与优先级排序
> 日期：2026-08-02

---

## 目录

1. [核心诊断验证与新发现](#1-核心诊断验证与新发现)
2. [优先级重排序：三个最高杠杆修复](#2-优先级重排序三个最高杠杆修复)
3. [Task A：Q1 直接强结构通道完整规格](#3-task-aq1-直接强结构通道完整规格)
4. [Task B：Q2 Pending 阈值重新校准方法论](#4-task-bq2-pending-阈值重新校准方法论)
5. [Task C：Q3 双轨道设计](#5-task-cq3-双轨道设计)
6. [Q1_RR_GAP_SCOUT 收紧规格](#6-q1_rr_gap_scout-收紧规格)
7. [Task D：Q4 极值反转研究通道（高风险，需最严格护栏）](#7-task-dq4-极值反转研究通道高风险需最严格护栏)
8. [Symbol Policy Shadow 晋级路径](#8-symbol-policy-shadow-晋级路径)
9. [Task E：每日漏斗诊断报告规格](#9-task-e每日漏斗诊断报告规格)
10. [A/B 切换规则加固](#10-ab-切换规则加固)
11. [验收标准与熔断机制汇总](#11-验收标准与熔断机制汇总)
12. [路线图与禁止事项](#12-路线图与禁止事项)

---

## 1. 核心诊断验证与新发现

### 1.1 上一轮建议的落地验证

```
上一轮（07-27 之前）建议 vs 本窗口实际结果：

  建议：实现 scout_decisions.jsonl 可观测性     → ✅ 已生效（87 条记录）
  建议：启动 REVERSAL_PIVOT_SCOUT               → ✅ 已生效（8 笔，+0.0888）
  建议：启动 SYMBOL_POLICY_REVIEW_SHADOW        → 部分生效（WATCH_ONLY_SYMBOL_PROMOTION_TEST 1 笔）
  建议：建立 Q4 防御退出反事实账本              → 未在本报告中体现，需要确认状态
  建议：不要全局放宽 RR                         → ✅ 遵守（RR 门槛未变）
  建议：不要解除 ZEC/XRP 黑名单                 → ✅ 遵守（继续 blacklist）

结论：工程可观测性修复到位，这是本窗口能做出精确诊断的前提。
     "配置已生效但没有交易转化"的黑箱问题已经解决——
     现在我们能精确说出"33 条 Q1 样本因缺少 confirmation tag 被挡"，
     而不是笼统地说"Q1 没有转化"。这是可观测性投入的直接回报。
```

### 1.2 本窗口最重要的新发现：Q4 方向匹配率反常地高

```
这是本报告中最值得警惕、也最值得研究的数据点：

  象限    拐点数    方向匹配    方向错误    匹配率
  ─────────────────────────────────────────────────
  Q1       87         2          85        2.3%
  Q2       91         4          87        4.4%
  Q3      107        13          94       12.1%
  Q4      301       183         118       60.8%   ← 唯一匹配率 > 50% 的象限

这个数据不能简单解读为"Q4 应该开仓"。正确解读需要两层：

  层 1（表面现象）：Q4 定义为"趋势/结构弱 + 资金/动能弱"
       在这个环境下，事后看到的"匹配"很可能只是价格随机游走后
       恰好与系统方向一致的概率结果，而非系统对 Q4 有识别能力

  层 2（真实信号）：Q4 拐点占样本总数的一半以上（301/586=51.4%）
       这暗示很多真实的行情反转起点确实发生在低分区
       但这不等于"系统应该在低分区开仓"——
       而是"系统当前的评分体系可能系统性地低估了某些反转前兆"

结论：Q4 高匹配率不是"应该开仓的证据"，是"当前评分体系在识别
     反转前兆上存在盲区"的证据。这两者需要用完全不同的方式处理：
     前者会导致鲁莽地放宽 Q4 门槛，后者应该导致谨慎的独立反转研究通道
     （即 Task D 的设计初衷，但需要比原报告更严格的护栏）
```

### 1.3 三个"死规则"的共同模式

```
Q2 pending：要求 score>=85，但 Q2 实际最高分 79.35（结构性不可达）
Q1 trend-launch：要求确认标签，但确认标签生成率极低（33/803=4.1%可能达标却卡在标签）
Q3→Q1 确认：3 根K线窗口太短 + 单实例覆盖，10个候选仅1个确认（10%转化率）

共同模式：这三个规则都是"参数拍脑袋设定，未经过实际分布校准"

这是本报告要解决的核心方法论问题：
  不是逐一调整这三个数字，是建立一套"用实际分布校准阈值"的流程
  避免下一轮又出现"配置了却不可达"的规则
```

---

## 2. 优先级重排序：三个最高杠杆修复

### 2.1 排序依据：每项修复预期能解锁的样本量

```
修复项                        当前受阻样本    预期解锁    优先级
──────────────────────────────────────────────────────────────
Q1 direct structured probe    33 条           15-25笔/周    P0
Q2 pending 阈值重校准          1003条(全部)    5-10笔/周    P0
Q1_RR_GAP_SCOUT 收紧           14笔(负期望)    减少7-10笔亏损 P0
Q3 双轨道设计                  10条候选         5-8笔/周     P1
Q4 极值反转（谨慎）             301个拐点        3-5笔/周（严格限仓）P2
Symbol policy shadow晋级       55条(near-miss) 数据积累，非直接开仓 P1

排序逻辑：
  P0 三项合计能在一周内产生约 25-45 笔新增可评估样本，
  同时立即停止一项已确认的负期望来源（Q1_RR_GAP_SCOUT）
  这是"止血 + 造血"同时进行的最高性价比组合
```

### 2.2 为什么 Q4 通道设为 P2 而非 P0

```
尽管 Q4 拥有最多的拐点数量和最高的匹配率，仍然放在 P2：

原因 1：60.8% 的匹配率需要先排除"随机游走巧合"的可能性
       在没有额外统计检验的情况下，直接按此数字开仓风险很高

原因 2：Q4 是当前系统评分最低的区域，意味着如果反转判断错误，
       后续可能继续朝原方向恶化更远（因为原方向的"合理性"评分更高）

原因 3：P0/P1 通道的数据能为 Q4 通道提供额外的交叉验证信息
       （例如：Q1 强结构通道运行后，可以观察其止损点是否
        恰好对应 Q4 通道应该捕捉的反转起点）

结论：Q4 通道不是不做，是在 P0/P1 稳定运行 2 周后再启动，
     且必须使用本报告第 7 节设计的加强版护栏
```

---

## 3. Task A：Q1 直接强结构通道完整规格

### 3.1 设计原则：移除确认标签依赖，加入位置质量约束替代

```
原报告建议的准入条件已经合理，但需要补充两点：
  1. 明确"非极值追单"的量化定义（原报告只是定性提及）
  2. 加入与 Q1_RR_GAP_SCOUT 的分流规则，避免同一候选进两个通道
```

### 3.2 完整配置规格

```json
{
  "channel": "q1_direct_structured_probe",
  "enabled": true,
  "ledger": "dry_run_paper_only",

  "entry_conditions": {
    "quadrant": "Q1",
    "score_min": 85,
    "pa_score_min": 18,
    "fib_score_min": 15,
    "cvd_score_min": 16,

    "rr_condition": {
      "option_a": {"rr_score_min": 2.0},
      "option_b": {
        "rr_score_min": 0.5,
        "not_extreme_position": true
      },
      "logic": "OR"
    },

    "not_extreme_position_definition": {
      "lookback_bars": 8,
      "rule": "close 不在最近 8 根 K 线极值区间的最外 20%",
      "formula": "0.20 <= (close - range_low) / (range_high - range_low) <= 0.80"
    },

    "symbol_policy_gate": {
      "blacklist": "REJECT",
      "watch_only": "ROUTE_TO_SCOUT_OR_MIRROR_ONLY",
      "normal": "ALLOWED"
    }
  },

  "position_sizing": {
    "base_probe_fraction_min": 0.25,
    "base_probe_fraction_max": 0.50,
    "leverage": 1
  },

  "channel_isolation": {
    "exclude_if_flagged_for": ["q1_rr_gap_scout"],
    "priority_over_rr_gap_scout": true
  },

  "circuit_breaker": {
    "min_samples_for_review": 20,
    "close_if_pf_below": 0.8,
    "expand_if_pf_above": 1.1
  },

  "required_logging_fields": [
    "entry_channel", "rr_option_used", "extreme_position_ratio",
    "pre_entry_quadrant_history_3bars"
  ]
}
```

### 3.3 分流规则：与 Q1_RR_GAP_SCOUT 的边界

```python
def route_q1_candidate(candidate: dict) -> str:
    """
    同一个 Q1 高分候选，决定进入哪个通道，避免重复计分或冲突
    """
    if candidate['score'] < 85:
        return "Q1_RR_GAP_SCOUT" if candidate['score'] >= 80 else "NONE"

    extreme_ratio = compute_extreme_position_ratio(candidate['ohlcv'], lookback=8)
    is_extreme = not (0.20 <= extreme_ratio <= 0.80)

    rr_qualifies = (candidate['rr_score'] >= 2.0) or \
                   (candidate['rr_score'] >= 0.5 and not is_extreme)

    if candidate['pa_score'] >= 18 and candidate['fib_score'] >= 15 \
       and candidate['cvd_score'] >= 16 and rr_qualifies:
        return "Q1_DIRECT_STRUCTURED_PROBE"

    # 未满足直接通道，但仍是 RR gap 候选（走收紧后的 RR_GAP_SCOUT，见第6节）
    return "Q1_RR_GAP_SCOUT_TIGHTENED"
```

### 3.4 预期效果量化

```
本窗口 33 条"除确认标签外满足 trend-launch"的样本：

  预估其中约 60-70%（20-23条）会满足新通道条件
  （因为原 trend-launch 门槛 score>=82, PA>=18, Fib>=15, CVD>=16, RR>=0.5
   与本通道条件高度重叠，只是移除了确认标签要求）

  一周内（7天 × 803/6天≈134 Q1样本/天）预计新增：
  Q1 高分（score>=85）约 25笔/周（基于本窗口 25/6天≈4.2笔/天）
  扣除 blacklist/watch-only 路由和 extreme position 过滤后
  预计实际开仓约 15-20 笔/周
```

---

## 4. Task B：Q2 Pending 阈值重新校准方法论

### 4.1 为什么"score>=85"从一开始就是错误设计

```
根本问题：Q2 的定义是"趋势/结构轴通过，资金/动能轴未通过"
        资金/动能轴（CVD+CCI 相关分量）不通过意味着这部分分数天然缺失

        本窗口 Q2 组件均值：CVD=13.13（低于Q1的18.00），CCI=2.52（远低于Q1的10.02）
        这意味着 Q2 的总分上限天然低于 Q1

        要求 Q2 达到 score>=85（这是 Q1 的高分门槛）
        相当于要求"资金动能轴缺失的样本，总分还要达到资金动能轴完整的样本水平"
        这在数学上就是不可能任务，除非趋势结构轴异常强以完全补偿

本窗口实证：Q2 全部 1003 条样本中最高分只有 79.35
           这就是最有力的证据：85 分门槛从未经过实际分布校准
```

### 4.2 正确的校准方法论（可复用于未来所有新规则）

```python
def calibrate_threshold_from_distribution(
    historical_scores: pd.Series,
    target_pass_rate: float = 0.05,   # 目标：约5%的样本能通过（合理稀缺性）
    min_absolute_floor: float = None  # 可选：硬性最低要求
) -> float:
    """
    根据历史实际分布反推合理阈值，而非凭经验设定绝对数字
    """
    if len(historical_scores) < 100:
        raise ValueError("样本量不足，无法可靠校准，先积累数据")

    percentile = 100 * (1 - target_pass_rate)
    calibrated = historical_scores.quantile(target_pass_rate)

    if min_absolute_floor is not None:
        calibrated = max(calibrated, min_absolute_floor)

    return calibrated

# 应用示例：Q2 pending 记录阈值校准
q2_scores = extract_q2_scores_from_decisions(window_days=7)
# q2_scores 分布：最高 79.35，P90 约等于 69.65（来自原报告 3.1 表格）

q2_pending_record_threshold = calibrate_threshold_from_distribution(
    q2_scores, target_pass_rate=0.10   # 记录阈值应更宽松，允许更多候选进入观察
)
# 预期结果：约等于 P90 附近，即 65-70 分区间

q2_pending_confirm_threshold_in_q1 = 85   # 确认后开仓的门槛保持严格，这是安全的
# 因为确认要求"进入 Q1"，此时才应用 Q1 的正常高分标准
```

### 4.3 重新设计的 Q2 Pending 完整流程

```json
{
  "q2_pending_setup": {
    "record_threshold": {
      "score_min": 70,
      "pa_score_min": 18,
      "trend_ema_min": 16,
      "cci_score_max": 7,
      "rationale": "记录门槛用于捕捉'结构好但动能尚未确认'的候选，不代表开仓"
    },

    "pending_storage": {
      "key_format": "{symbol}_{side}_{setup_type}_{timestamp_bucket}",
      "allow_multiple_instances": true,
      "max_instances_per_symbol": 3,
      "rationale": "原设计单symbol覆盖导致后续候选覆盖前一个，改为多实例存储"
    },

    "confirmation_requirements": {
      "must_enter_quadrant": "Q1",
      "cci_score_min": 9,
      "cvd_score_min": 16,
      "rr_score_min": 1.0,
      "confirmation_window_bars": [8, 12],
      "rationale": "原3-6根窗口偏短，改为8-12根给动能回归留出合理时间"
    },

    "expiry": {
      "bars_without_confirmation": 16,
      "action_on_expiry": "log_as_expired_no_open"
    }
  }
}
```

### 4.4 一周验收标准

```
成功标准（一周后评估）：
  □ Q2 pending 记录数量 >= 10（相比当前 0 的实质性改善）
  □ 确认转化数量 >= 2（转化率 >= 20%，高于 Q3 当前的 10%）
  □ 若确认样本产生实际开仓，其 PF 应可评估（即使样本仍很少）

失败/调整信号：
  若记录数量仍 < 5：进一步降低 record_threshold 的 score_min 至 65
  若确认数量为 0 但记录数量充足：说明 confirmation_window 或
    quadrant 转换要求仍然过严，需要单独诊断确认失败的具体原因
    （建议：记录所有 pending 过期时的最终象限和分数，用于诊断）
```

---

## 5. Task C：Q3 双轨道设计

### 5.1 为什么需要拆分为两条独立通道

```
Q3 定义为"资金/动能轴通过，趋势/结构轴未通过"
本窗口 Q3 组件均值：CVD=18.00（满分），CCI=9.65（良好），PA=5.70（很弱），trend_ema=14.65（中等）

这个组合有两种合理解释，且需要用不同策略处理：

解释 A（动能延续）：
  资金流向强劲但结构还没跟上，价格可能正在形成新趋势的早期阶段
  策略：不必等待"回到Q1"，直接small size 跟随动能，设置更紧的止损

解释 B（趋势反转前兆）：
  资金流向的剧烈波动可能是行情反转初期的资金异动
  结构轴未通过恰恰因为旧结构正在被打破
  策略：等待"回到Q1"确认新结构成立后再开仓（原 Q3_TO_Q1_CONFIRMATION 逻辑）

原设计只覆盖了解释B（且窗口太窄），完全遗漏了解释A
两条通道应该独立运行、独立评估，因为它们测试的是两个不同假设
```

### 5.2 通道一：Q3_MOMENTUM_CONTINUATION_SCOUT

```json
{
  "mission": "Q3_MOMENTUM_CONTINUATION_SCOUT",
  "hypothesis": "Q3 高分资金流向可以直接捕捉动能延续，不必等待结构确认",

  "entry_conditions": {
    "quadrant": "Q3",
    "score_min": 85,
    "pa_score_min": 18,
    "cvd_score_min": 16,
    "cci_score_min": 10
  },

  "execution": {
    "ledger": "SCOUT_ONLY",
    "position_size_usdt": [25, 50],
    "leverage": 1
  },

  "exit_rules": {
    "immediate_exit_condition": "若2根K线内转入Q4，立即平仓",
    "rationale": "Q4转入说明动能延续假设已经证伪，及时止损而非等待常规止损位"
  },

  "evaluation": {
    "min_samples": 20,
    "compare_against": "Q3_TO_Q1_CONFIRMATION"
  }
}
```

### 5.3 通道二：Q3_TO_Q1_CONFIRMATION（重新设计）

```json
{
  "mission": "Q3_TO_Q1_CONFIRMATION",
  "hypothesis": "Q3 高分候选在结构确认后（进入Q1）提供更高质量入场",

  "pending_setup": {
    "quadrant": "Q3",
    "score_min": 82,
    "cvd_score_min": 16,
    "storage": "multi_instance_per_symbol"
  },

  "confirmation_window_bars": [6, 8],
  "confirmation_requirements": {
    "must_enter_quadrant": "Q1",
    "score_min_at_confirmation": 82
  },

  "execution_on_confirmation": {
    "route": "SCOUT_first_then_evaluate_for_direct_probe",
    "position_size_usdt": [25, 50]
  },

  "evaluation": {
    "min_samples": 15,
    "target_confirmation_rate": 0.25
  }
}
```

### 5.4 分流逻辑：候选不会同时进两个通道

```python
def route_q3_candidate(candidate: dict) -> str:
    """
    Q3 候选的分流：分数极高且各项均衡 → 尝试直接延续
    分数中等但有潜力 → 走 pending 确认路径
    """
    if candidate['score'] >= 85 and candidate['pa_score'] >= 18 \
       and candidate['cci_score'] >= 10:
        return "Q3_MOMENTUM_CONTINUATION_SCOUT"

    if candidate['score'] >= 82 and candidate['cvd_score'] >= 16:
        return "Q3_TO_Q1_CONFIRMATION_PENDING"

    return "NO_ROUTE"   # 记录为 near-miss，但不进入任何实验通道
```

### 5.5 两条通道的交叉验证价值

```
运行 4 周后，对比两条通道的表现，可以回答关键问题：

  若 Q3_MOMENTUM_CONTINUATION_SCOUT 的 PF 显著高于 Q3_TO_Q1_CONFIRMATION：
    → 说明"等待结构确认"反而错过了最佳时机，应该以直接延续为主

  若情况相反：
    → 说明结构确认确实过滤了噪音，应该保留确认流程，
      并可以考虑把确认窗口进一步优化（而非本次预设的6-8根）

  这个对比本身就是一个有价值的策略研究产出，
  不需要提前预判哪条通道会赢
```

---

## 6. Q1_RR_GAP_SCOUT 收紧规格

### 6.1 问题的精确诊断

```
14 笔开仓，PnL -1.3456，7次初始止损（止损率50%）
这是当前 SCOUT 层唯一的显著负期望来源

原报告已经提出了收紧方向（回踩确认、非极值位置、ATR扩张但无wick风险）
本节将其转化为可执行的精确规格
```

### 6.2 Q1_PULLBACK_RR_GAP_SCOUT 完整规格

```python
def check_q1_pullback_rr_gap_eligibility(
    candidate: dict, ohlcv: pd.DataFrame, atr: float
) -> tuple[bool, str]:
    """
    重构后的 RR gap 侦察准入检查
    核心变化：从"只要 RR gap 就侦察"改为"RR gap + 位置确认才侦察"
    """
    # 基础门槛（不变）
    if candidate['quadrant'] != 'Q1' or candidate['score'] < 80:
        return False, "BASE_THRESHOLD_NOT_MET"

    if candidate['rr_score'] >= 2.0:
        return False, "NOT_RR_GAP_CASE"   # RR充足，走直接通道而非侦察

    # 新增条件 1：前2-4根出现回踩，而非连续追涨/追跌
    pullback_detected = detect_pullback_pattern(ohlcv.iloc[-4:], candidate['side'])
    if not pullback_detected:
        return False, "NO_PULLBACK_CONFIRMATION"

    # 新增条件 2：当前 close 不在近8根极值最外20%
    extreme_ratio = compute_extreme_position_ratio(ohlcv, lookback=8)
    if not (0.20 <= extreme_ratio <= 0.80):
        return False, "EXTREME_POSITION_BLOCK"

    # 新增条件 3：ATR 扩张但 wick risk 未激活
    atr_expanding = check_atr_expansion(ohlcv, lookback=6)
    wick_risk_active = check_wick_risk_flag(ohlcv.iloc[-1], candidate['side'])
    if not atr_expanding or wick_risk_active:
        return False, "ATR_OR_WICK_CONDITION_FAILED"

    # 新增条件 4：排除历史高频错向形态
    is_known_bad_pattern = check_against_historical_reversal_patterns(
        ohlcv, candidate['side'], pattern_db=load_reversal_pattern_db()
    )
    if is_known_bad_pattern:
        return False, "MATCHES_HISTORICAL_FALSE_SIGNAL_PATTERN"

    return True, "ELIGIBLE"


def detect_pullback_pattern(recent_bars: pd.DataFrame, side: str) -> bool:
    """
    简化定义：最近4根中至少1根与主方向相反（即存在回撤），
    而非连续同向K线（说明是纯粹的追单，没有任何喘息）
    """
    if side == "LONG":
        opposite_bars = (recent_bars['close'] < recent_bars['open']).sum()
    else:
        opposite_bars = (recent_bars['close'] > recent_bars['open']).sum()
    return opposite_bars >= 1
```

### 6.3 历史错向形态库（新增机制）

```python
def build_historical_reversal_pattern_db(scout_decisions_log: str) -> dict:
    """
    从 Q1_RR_GAP_SCOUT 的历史7次止损案例中提取共性形态特征
    用于未来主动排除类似形态
    """
    losing_trades = load_losing_trades(scout_decisions_log, mission="Q1_RR_GAP_SCOUT")

    pattern_features = []
    for trade in losing_trades:
        pattern_features.append({
            'consecutive_same_direction_bars': count_consecutive_bars(trade.pre_entry_ohlcv),
            'distance_from_recent_extreme': trade.extreme_position_ratio,
            'atr_at_entry': trade.atr_pct,
            'wick_pattern': trade.entry_bar_wick_ratio,
        })

    # 简化：若7个亏损样本中 >=5个 consecutive_bars > 4，
    # 则"连续4根以上同向"被记入形态库作为拦截条件
    return summarize_common_features(pattern_features, min_occurrence_ratio=0.7)
```

### 6.4 预期效果

```
本窗口 14 笔中 7 笔止损，若收紧条件能过滤掉其中的"纯追单"案例
（预估至少 4-5 笔属于连续追单无回踩的情况）

保守估计：
  收紧后样本量减少至约 6-8 笔/2周（相比之前14笔/周的开仓频率显著下降）
  但止损率预期从 50% 降至 30% 以下
  这条通道的目标从"证明有效"改为"最小化负期望的同时保留少量样本"
```

---

## 7. Task D：Q4 极值反转研究通道（高风险，需最严格护栏）

### 7.1 启动前置条件（与原报告不同，本报告要求更严格）

```
原报告建议直接新增 Q4_EXTREME_REVERSAL_SCOUT
本报告认为该通道启动前必须先完成两项前置研究：

前置研究 1：Q4 拐点匹配率的统计显著性检验
  当前 183/301 = 60.8% 匹配率
  需要验证：这个比例是否显著高于"随机游走下的理论匹配率"
  简化方法：对无信息的随机方向分配（50%基准）做二项检验

  from scipy import stats
  n, k = 301, 183
  p_value = stats.binomtest(k, n, p=0.5, alternative='greater').pvalue
  # 若 p_value < 0.01，说明该匹配率显著非随机，值得研究
  # 若 p_value 较大，说明当前"匹配"很可能只是噪音，不应该投入资源开发此通道

前置研究 2：找出 Q4 高匹配拐点与低匹配拐点之间的可观测差异特征
  不能只看总体匹配率，需要拆解出"哪些 Q4 拐点更可能匹配"
  例如：是否 CCI 极值回落幅度、成交量突增、K线形态等特征
       在匹配成功的样本中显著不同于匹配失败的样本
```

### 7.2 若前置研究支持继续，则采用以下规格

```json
{
  "mission": "Q4_EXTREME_REVERSAL_SCOUT",
  "prerequisite": "前置研究1显著性检验通过 AND 前置研究2识别出可复现特征",

  "entry_conditions": {
    "quadrant": "Q4",
    "extreme_condition_required": {
      "fib_extension_or_opposition_too_close": true,
      "cci_extreme_reversal": "CCI从极值回落/回升，非首次触及极值",
      "candle_pattern": "长下影/长上影或反包K线",
      "cvd_stabilizing": "CVD不再继续恶化（斜率转平或反向）"
    },
    "all_conditions_required": true
  },

  "execution": {
    "ledger": "SCOUT_ONLY",
    "position_size_usdt": 25,
    "leverage": 1,
    "no_consecutive_opens": true
  },

  "circuit_breaker": {
    "mission_stop_after_consecutive_losses": 3,
    "cooldown_hours": 24,
    "min_samples_before_evaluation": 30,
    "close_permanently_if_pf_below": 0.7,
    "continue_if_pf_above": 0.9
  },

  "special_monitoring": {
    "compare_win_rate_against": "整体随机基准（50%）",
    "track_separately": ["fib_extension_trigger", "opposition_too_close_trigger", "cci_extreme_trigger"],
    "rationale": "分别追踪不同触发条件的表现，避免混合评估掩盖单项条件的有效性"
  }
}
```

### 7.3 为什么这条通道即使验证有效也不应该扩大到主账本

```
即使 Q4_EXTREME_REVERSAL_SCOUT 在 30 笔后 PF > 0.9：

理由 1：Q4 定义为系统评分最低区间，即使反转研究通道有效，
       这也只是"侦察级别"的边际价值，样本量注定很小
       （因为触发条件极其严格，是有意为之的稀缺性）

理由 2：反转研究的本质是与当前系统主逻辑相反的假设
       让它进入主账本会造成账本层面的逻辑混乱
       （主账本继续遵循"趋势跟随"哲学，此通道遵循"反转捕捉"哲学）

理由 3：这条通道更大的价值在于"诊断"而非"盈利"——
       它能帮助未来理解当前评分体系在哪里存在系统性盲区
       （例如：如果发现 Fib extension 触发的反转显著优于其他触发条件，
        这说明 Fib 位置层的判断逻辑本身可能需要重新校准，
        而不是"开发一个新的交易通道"）

结论：Task D 的目标定位为"研究工具"，长期保持 SCOUT-only 状态，
     不设置"表现好就晋级主账本"的路径
```

---

## 8. Symbol Policy Shadow 晋级路径

### 8.1 当前状态梳理

```
标的         当前状态           本窗口相关样本
────────────────────────────────────────────
ADAUSDT      watch-only         Q1 92.09分被挡，Q3 85.80分被挡（后验favorable 0.93%）
XMRUSDT      watch-only         Q1 86.59分（后验favorable 1.11%）
ZECUSDT      blacklist          继续观察期
XRPUSDT      blacklist          继续观察期
XLMUSDT      RR gap symbol block  单独记录

本窗口新增：WATCH_ONLY_SYMBOL_PROMOTION_TEST 已产生 1 笔样本（-0.7720，止损）
这是晋级路径已经开始运行的证据，但单样本远不足以做任何判断
```

### 8.2 晋级路径正式化

```json
{
  "symbol_policy_shadow_review": {
    "watch_only_symbols": {
      "list": ["ADAUSDT", "XMRUSDT"],
      "promotion_test": {
        "mission": "WATCH_ONLY_SYMBOL_PROMOTION_TEST",
        "target_samples_per_symbol": 10,
        "execution": "SCOUT_ONLY, 25 USDT",
        "promotion_criteria": {
          "pf_min": 1.0,
          "max_drawdown_within_budget": true,
          "initial_stop_rate_max": 0.40,
          "median_favorable_move_min": 0.008
        },
        "promotion_action": "移至 normal，允许 Q1_DIRECT_STRUCTURED_PROBE"
      }
    },

    "blacklist_symbols": {
      "list": ["ZECUSDT", "XRPUSDT"],
      "shadow_only": true,
      "no_scout_execution": true,
      "review_period_days": 14,
      "review_started": "追溯至最早的shadow样本信号时间，非报告提交时间"
    },

    "rr_gap_blocked_symbols": {
      "list": ["XLMUSDT"],
      "action": "保留阻断，但单独记录'若未阻断'的mirror表现",
      "purpose": "积累数据用于未来判断该标的的RR gap阻断是否过度保守"
    }
  }
}
```

### 8.3 本窗口 ADAUSDT/XMRUSDT 数据的初步观察

```
ADAUSDT 两次被挡（92.09分, 85.80分），后验favorable分别为0.93%和(数据未提供，需补充)
XMRUSDT 一次被挡（86.59分），后验favorable 1.11%

这三个样本的favorable move都不算极端强烈（相比BCH的3.70%、CC的1.94%）
初步观察：ADA/XMR 的机会强度可能确实不如已经放开的BCH/CC/HYPE/SOL簇
建议：继续晋级测试收集更多样本，但不应期望ADA/XMR会有和BCH同等的表现
```

---

## 9. Task E：每日漏斗诊断报告规格

### 9.1 报告目标

```
避免重蹈"配置已启用但不知道为什么没有转化"的覆辙
每日报告必须让人在5分钟内看懂：
  今天有多少机会？被什么原因挡住？各实验通道表现如何？
```

### 9.2 完整字段规格

```python
@dataclass
class DailyFunnelDiagnosticReport:
    report_date: str

    # ── 漏斗诊断（核心）───────────────────────────────────
    q1_qualified_but_missing_tag_count: int      # Q1达标但缺确认标签数量（应该趋近于0，因Task A已移除此依赖）
    q1_direct_structured_probe_candidates: int   # 进入新通道的候选数量
    q1_direct_structured_probe_opens: int        # 实际开仓数量

    q2_pending_created: int
    q2_pending_confirmed: int
    q2_pending_expired: int
    q2_pending_conversion_rate: float

    q3_continuation_candidates: int
    q3_continuation_opens: int
    q3_to_q1_pending_created: int
    q3_to_q1_confirmed: int
    q3_to_q1_conversion_rate: float

    q4_reversal_candidates: int      # 仅在Task D启动后统计
    q4_reversal_opens: int

    # ── SCOUT mission 级表现 ───────────────────────────────
    scout_mission_stats: dict[str, dict]   # {mission_name: {pf, win_rate, initial_stop_rate, circuit_state}}

    # ── A/B 切换诊断 ────────────────────────────────────────
    ab_switch_not_triggered_reason: str    # 具体是哪个条件未满足

    # ── near-miss 后验 ──────────────────────────────────────
    top_20_near_miss_summary: list[dict]   # 每条含 symbol, side, quadrant, score, block_reason, mfe_4h, mae_4h

    # ── 数据健康 ────────────────────────────────────────────
    data_health_status: str
```

### 9.3 报告生成逻辑要点

```python
def generate_daily_funnel_report(date: str, decisions_log, scout_log, ab_log) -> DailyFunnelDiagnosticReport:
    """
    核心原则：报告的每个数字都必须能追溯到具体的候选列表，
    而不是只给聚合统计——这样才能在需要时快速下钻诊断
    """
    q1_candidates = filter_decisions(decisions_log, quadrant="Q1", date=date)

    report = DailyFunnelDiagnosticReport(
        report_date=date,

        q1_direct_structured_probe_candidates=count_matching(
            q1_candidates, channel="q1_direct_structured_probe"
        ),
        q1_direct_structured_probe_opens=count_actual_opens(
            scout_log, channel="q1_direct_structured_probe", date=date
        ),

        q2_pending_created=count_pending_events(decisions_log, quadrant="Q2", event="created", date=date),
        q2_pending_confirmed=count_pending_events(decisions_log, quadrant="Q2", event="confirmed", date=date),
        q2_pending_expired=count_pending_events(decisions_log, quadrant="Q2", event="expired", date=date),

        # ... 其余字段类似填充

        scout_mission_stats=aggregate_scout_mission_stats(scout_log, date=date),
        ab_switch_not_triggered_reason=diagnose_ab_switch_gap(ab_log),
        top_20_near_miss_summary=get_top_near_miss_with_mfe(decisions_log, date=date, top_n=20),
        data_health_status=get_data_health_status(date),
    )
    return report
```

### 9.4 报告消费方式

```
每日报告不是给人"读完再决定"，而是给人"扫一眼异常项"：

  q2_pending_created == 0 连续3天 → 立即触发人工复核校准阈值
  任意 mission circuit_state == "TRIPPED" → 立即复核该mission
  ab_switch_not_triggered_reason 连续多日相同 → 说明当前迭代方向对A/B切换无实质推进，
    需要判断是否应该改变 legacy/trend_capture 的具体实现而非继续等待样本积累
```

---

## 10. A/B 切换规则加固

### 10.1 原报告建议的验证

```
原报告建议：payoff_mult>=1.3 保留，新增硬条件 trend PF > 1.0 或最近40笔正PnL

本报告完全同意这个方向，并补充一点：
  当前 batch 2/3/4 都显示 trend_capture 持续小幅优于 legacy
  这个"持续优于但幅度不足"的模式本身是有信息量的——
  它更可能说明两者的出场机制差异带来的边际改善是真实存在但较小的，
  而非纯噪音（纯噪音应该表现为忽正忽负，而非连续3个batch同向）
```

### 10.2 建议新增的诊断动作（而非仅仅是切换判断）

```yaml
ab_diagnostic_addon:
  # 不是为了决定是否切换，而是为了理解"为什么trend_capture只是略好"
  trend_capture_incremental_analysis:
    target: "拆解trend_capture相对legacy的改善具体来自出场的哪个环节"
    method:
      - 对比两组在 Q4_DEFENSIVE_EXIT 触发时点的差异
      - 对比两组在达到TP1后的后续处理差异（trailing vs fixed）
      - 输出："trend_capture的优势主要来自更晚的Q4退出" 或
              "trend_capture的优势主要来自TP1后的移动止损"

  # 这个诊断结果将指导下一版trend_capture的迭代方向
  # 而不是简单等待样本量堆到40筆后被动触发自动切换
```

---

## 11. 验收标准与熔断机制汇总

### 11.1 五个通道的统一验收表

```
通道                             最小样本  成功阈值                失败/暂停阈值
─────────────────────────────────────────────────────────────────────────────
Q1_DIRECT_STRUCTURED_PROBE       20笔     PF>1.1，扩大规模         PF<0.8，关闭
Q2_PENDING（确认转化）            10笔pending  转化率>=20%           连续2周记录<5，需再校准
Q3_MOMENTUM_CONTINUATION_SCOUT    20笔     PF可评估，与对照组对比    N/A（研究性质）
Q3_TO_Q1_CONFIRMATION            15笔     转化率>=25%              转化率<15%需重新设计窗口
Q1_RR_GAP_SCOUT(收紧后)          20笔     止损率<30%               止损率仍>40%，永久关闭该mission
Q4_EXTREME_REVERSAL_SCOUT(若启动) 30笔     PF>0.9                   PF<0.7，永久关闭
WATCH_ONLY_SYMBOL_PROMOTION_TEST 10笔/标的 PF>1.0 且止损率<40%       不满足则维持watch-only
```

### 11.2 全局熔断条件（任一触发，暂停当轮所有新通道扩展）

```
条件1：data_health 连续24h非OK状态
条件2：任意通道熔断后，48h内未完成书面归因分析
条件3：主账本（非实验通道）出现任何计划外的大额亏损
条件4：Q4_EXTREME_REVERSAL_SCOUT的前置统计显著性检验未通过（p>0.05）
       → 该通道直接不启动，不进入实施阶段
```

---

## 12. 路线图与禁止事项

### 12.1 实施顺序

```
┌──────────────────────────────────────────────────────────────┐
│ Phase 0（立即，1天）：止血 + 校准方法论                        │
│  → 暂停原始 Q1_RR_GAP_SCOUT（无条件暂停，等待收紧版重新上线）  │
│  → 实现 calibrate_threshold_from_distribution() 工具函数       │
│  → 用该工具重新校准 Q2 pending 阈值（第4.2节）                 │
├──────────────────────────────────────────────────────────────┤
│ Phase 1（3-5天）：P0 三项通道上线                              │
│  → 上线 Q1_DIRECT_STRUCTURED_PROBE（第3节）                   │
│  → 上线重校准后的 Q2_PENDING_SETUP（第4.3节）                 │
│  → 上线 Q1_PULLBACK_RR_GAP_SCOUT（第6节，替代原版本）         │
│  → 实现每日漏斗诊断报告（第9节）                                │
├──────────────────────────────────────────────────────────────┤
│ Phase 2（1周后）：P1 通道上线                                  │
│  → 上线 Q3 双轨道（第5节）                                     │
│  → 正式化 Symbol Policy Shadow 晋级路径（第8节）               │
│  → 启动 trend_capture 增量诊断分析（第10.2节）                 │
├──────────────────────────────────────────────────────────────┤
│ Phase 3（2周后，视Phase 1/2数据决定）：Q4 前置研究              │
│  → 执行 Q4 匹配率显著性检验（第7.1节）                         │
│  → 若通过：设计特征识别研究（前置研究2）                       │
│  → 若通过：谨慎上线 Q4_EXTREME_REVERSAL_SCOUT（第7.2节）      │
├──────────────────────────────────────────────────────────────┤
│ Phase 4（4周后）：综合评估                                      │
│  → 汇总所有通道的 PF/胜率/止损率数据                           │
│  → Q3双轨道交叉对比（哪种假设更成立）                          │
│  → 决定是否需要进一步的账本合并或架构调整                       │
└──────────────────────────────────────────────────────────────┘
```

### 12.2 禁止事项

```
❌ 不要在Q4显著性检验通过前启动任何Q4相关的实际SCOUT下单
❌ 不要因为"trend_capture连续3个batch略优"就手动强制切换
   （应该先做增量诊断，理解优势来源，而非仅凭趋势外推）
❌ 不要同时上线Q1/Q2/Q3三个新通道而不设置每日诊断报告
   （历史教训：没有可观测性的多通道并行会重新制造黑箱）
❌ 不要把Q2 pending确认阈值也下调
   （只下调记录阈值，确认阈值继续使用Q1标准的严格要求）
❌ 不要在同一候选样本上同时触发多个实验通道的开仓
   （必须遵循本报告第3.3/5.4节的分流逻辑，避免重复计入风险敞口）
❌ 不要将ADA/XMR的晋级测试结果与ZEC/XRP的shadow复核结果混合评估
   （前者是watch-only路径，后者是blacklist路径，历史严重程度不同）
```

### 12.3 本轮最重要的方法论产出

```
比五个具体通道更重要的是第4.2节提出的阈值校准方法论：

  calibrate_threshold_from_distribution()

这个函数应该成为未来所有新规则上线前的强制检查步骤——
任何"score>=X"式的门槛设定，都应该先用历史实际分布验证
"这个X在当前系统下是否存在足够密度的样本能够达到"。

Q2 pending 的"score>=85在实际最高79.35的分布下"教训，
本质上是一个可以完全避免的低级错误，
而这类错误在快速迭代中很容易重复发生。

建立这个校准习惯，比任何单一通道的PF数字都更有长期价值。
```

---

*报告结束 | 窄通道工程化建议 v1.0 — 2026-08-02*
*最高优先行动：Phase 0 的两项——暂停原版 Q1_RR_GAP_SCOUT（止血）+ 用实际分布重新校准 Q2 pending 阈值（方法论示范）。这两项合计不到1天工期，但分别解决了"当前唯一负期望来源"和"三个死规则的共同病因"。*
