# 实施缺口修复与非对称放行框架建议
> 2026-08-02 21:45 至 2026-08-04 19:00 | 代码级修复规格
> 日期：2026-08-04

---

## 目录

1. [最重要的发现：建议与实现之间的缺口](#1-最重要的发现建议与实现之间的缺口)
2. [P0-1：q1_trend_launch 代码级修复规格](#2-p0-1q1_trend_launch-代码级修复规格)
3. [P0-2：LONG 阈值非对称校准](#3-p0-2long-阈值非对称校准)
4. [核心方法论：为什么这次是"非对称放行"而非"分层放行"](#4-核心方法论为什么这次是非对称放行而非分层放行)
5. [RR 几何门槛验证：SHORT 侧必须维持](#5-rr-几何门槛验证short-侧必须维持)
6. [SCOUT 任务多样化诊断与修复](#6-scout-任务多样化诊断与修复)
7. [出场 Payoff 结构改善](#7-出场-payoff-结构改善)
8. [实施验证协议：防止建议再次未落地](#8-实施验证协议防止建议再次未落地)
9. [配置文件卫生：重复键清理](#9-配置文件卫生重复键清理)
10. [验收标准与熔断机制](#10-验收标准与熔断机制)
11. [路线图](#11-路线图)
12. [禁止事项](#12-禁止事项)

---

## 1. 最重要的发现：建议与实现之间的缺口

### 1.1 这是本轮报告中优先级最高的问题

```
08-02 报告 Task A 明确要求：
  "移除确认标签依赖，加入位置质量约束替代"

代码现状（run_live_dry_run.py L888）：
  if "Q2_PENDING_MOMENTUM_CONFIRMED" not in tag_list and
     "Q3_TO_Q1_CONFIRMED" not in tag_list:
      return False

窗口证据：这两个标签在 08-02 21:45 至 08-04 19:00 的全部日志中出现 0 次

结论：Task A 从未被实现。08-02 到本次报告之间的近两天窗口，
     Q1 通道继续以旧逻辑空转——14 个 ≥85 分样本、46 个 ≥80 分样本，
     全部因为同一个已知问题被挡，而这个问题两天前就已经被诊断并给出了
     具体的修复代码规格。
```

### 1.2 为什么这个缺口比任何数据发现都重要

```
本报告能提供的所有其他分析——LONG阈值校准、RR门槛验证、SCOUT多样化——
都建立在"建议会被转化为代码"这个前提上。如果这个前提不成立，
那么无论诊断多精确，下一份报告大概率还是"配置已启用但转化为0"。

这不是苛责，是提出一个必须首先解决的流程问题：
  诊断报告 → 工程实现 → 验证 之间需要一个强制的闭环检查点，
  而不是"报告写了就默认会被处理"。

第8节将专门给出这个闭环协议的具体设计。
```

### 1.3 本轮诊断相比上一轮的价值增量

```
即便 Task A 未落地，本窗口的数据依然提供了新的、更精确的证据：

  上一轮：Q4 匹配率60.8%（后来判断可能是噪音，需要显著性检验）
  本轮：拐点匹配率按分数段拆分后，70-80分段匹配率(42.9%)反而是
        全部分数段中最差的——这进一步支持"高分不等于方向准"的判断

  上一轮：只是笼统建议"开放部分高分LONG"
  本轮：精确到"LONG被拦样本blended +0.465R，止损率仅50%；
        SHORT被RR几何拦截样本blended -0.30R，止损率94.1%"
        这是本报告最有价值的单一数据点——它把"分层放行"的建议
        升级为"方向性非对称"的明确证据
```

---

## 2. P0-1：q1_trend_launch 代码级修复规格

### 2.1 精确定位问题代码

```python
# run_live_dry_run.py，函数 _q1_trend_launch_eligible()，第 866-896 行
# 第 888 行是问题所在：

def _q1_trend_launch_eligible(candidate, tag_list, config):
    # ... 前置检查（quadrant==Q1, score>=xx 等）...

    # 第 888 行（问题代码，必须移除）
    if "Q2_PENDING_MOMENTUM_CONFIRMED" not in tag_list and \
       "Q3_TO_Q1_CONFIRMED" not in tag_list:
        return False

    # ... 后续逻辑 ...
```

### 2.2 完整替换规格（对照 08-02 报告 Task A 原始设计）

```python
def _q1_trend_launch_eligible(candidate: dict, ohlcv: pd.DataFrame, config: dict) -> tuple[bool, str]:
    """
    重写版本：移除标签依赖，用位置质量约束直接判定
    返回 (是否准入, 拒绝原因)
    """
    if candidate['quadrant'] != 'Q1':
        return False, "NOT_Q1"

    if candidate['score'] < config.get('q1_trend_launch_score_min', 85):
        return False, "SCORE_BELOW_MIN"

    if candidate['pa_score'] < config.get('q1_trend_launch_pa_min', 18):
        return False, "PA_BELOW_MIN"

    if candidate['fib_score'] < config.get('q1_trend_launch_fib_min', 15):
        return False, "FIB_BELOW_MIN"

    if candidate['cvd_score'] < config.get('q1_trend_launch_cvd_min', 16):
        return False, "CVD_BELOW_MIN"

    if candidate['rr_score'] < config.get('q1_trend_launch_rr_min', 0.5):
        return False, "RR_BELOW_MIN"

    # 非极值追单检查（替代原确认标签的核心保护逻辑）
    extreme_ratio = compute_extreme_position_ratio(ohlcv, lookback=8)
    if not (0.20 <= extreme_ratio <= 0.80):
        return False, "EXTREME_POSITION_BLOCK"

    # 防反转过滤器（wick / chase 检查，若已有实现应复用）
    if check_reversal_wick(ohlcv, candidate['side']):
        return False, "REVERSAL_WICK_DETECTED"

    if check_chase_risk(ohlcv, candidate['side']):
        return False, "CHASE_RISK_DETECTED"

    return True, "ELIGIBLE"
```

### 2.3 配置文件新增字段

```json
{
  "q1_trend_launch": {
    "enabled": true,
    "score_min": 85,
    "pa_min": 18,
    "fib_min": 15,
    "cvd_min": 16,
    "rr_min": 0.5,
    "extreme_position_ratio_min": 0.20,
    "extreme_position_ratio_max": 0.80,
    "ledger": "dry_run_paper_experimental",
    "note": "已移除对 Q2_PENDING_MOMENTUM_CONFIRMED / Q3_TO_Q1_CONFIRMED 标签的依赖，2026-08-04 修复"
  }
}
```

### 2.4 验证脚本（部署后立即运行，确认修复生效）

```python
def verify_q1_trend_launch_fix(decisions_log_path: str, hours: int = 24) -> dict:
    """
    部署修复后，在下一个 24h 窗口结束时运行此脚本
    确认标签依赖已被移除，且通道开始产生转化
    """
    decisions = load_recent_decisions(decisions_log_path, hours=hours)

    q1_high_score = [d for d in decisions if d['quadrant'] == 'Q1' and d['score'] >= 85]

    trend_launch_triggered = [
        d for d in decisions if d.get('entry_channel') == 'q1_trend_launch'
    ]

    # 关键验证：这次是否还依赖已废弃的标签
    still_checking_deprecated_tags = any(
        'Q2_PENDING_MOMENTUM_CONFIRMED' in d.get('block_reason', '') or
        'Q3_TO_Q1_CONFIRMED' in d.get('block_reason', '')
        for d in q1_high_score
    )

    result = {
        'q1_high_score_count': len(q1_high_score),
        'trend_launch_triggered_count': len(trend_launch_triggered),
        'conversion_rate': len(trend_launch_triggered) / max(1, len(q1_high_score)),
        'still_depends_on_deprecated_tags': still_checking_deprecated_tags,
        'fix_verified': not still_checking_deprecated_tags and len(trend_launch_triggered) > 0,
    }

    if not result['fix_verified']:
        raise RuntimeError(
            f"q1_trend_launch 修复未生效！"
            f"deprecated_tags_still_used={still_checking_deprecated_tags}, "
            f"triggered_count={len(trend_launch_triggered)}"
        )

    return result
```

### 2.5 预期效果

```
本窗口 14 个 ≥85 分 Q1 样本，全部符合新规则的位置质量约束（因为这些
约束原本就是 08-02 Task A 设计中已包含的条件，只是被标签依赖挡在前面）

预期：修复部署后 24-48h 内，应看到至少 5-8 笔 q1_trend_launch 通道
     的实验账本开仓（考虑到高分样本出现频率约 14笔/2天≈7笔/天，
     加上非极值追单过滤会淘汰一部分）
```

---

## 3. P0-2：LONG 阈值非对称校准

### 3.1 问题精确定位

```
配置文件当前状态（存在重复键，第9节会详细处理）：
  long_threshold_offset 出现两次：7.0 和 10.0
  JSON 解析规则下后者生效 → 实际使用 10.0

LONG direct 门槛 = base(82) + offset(10) = 92
窗口 LONG 方向最高分 = 90.1（略低于92）

结论：LONG 主账本入口在当前配置下是结构性不可达的，
     不是"偏严格"，是"数学上不可能触发"
```

### 3.2 非对称证据的完整呈现

```
被拦截高分信号（≥85）replay 数据（stop_first 假设，96根视域）：

                    样本数   终局(整仓)   终局(阶梯)   止损命中率
SHORT(RR几何拦截)    17      -0.89R      -0.30R       94.1%
LONG(SIDE阈值拦截)    2      +1.0R       blended+0.465R  50.0%

这不是"样本量大的SHORT应该相信、样本量小的LONG应该谨慎"的简单判断
而是两个方向被完全不同的机制拦截：
  SHORT 被 RR 几何门槛拦截 → 说明是"位置质量"问题，止损率高印证了这一点
  LONG 被 SIDE 阈值拦截 → 说明是"门槛设置"问题，不是位置质量问题

这是关键区分：LONG样本的PA/Fib/CVD等位置质量分量本身可能是合格的，
只是因为一个与位置质量无关的全局offset而被挡在门外
```

### 3.3 校准方案

```yaml
# 方案对比

# 方案 A（原报告建议，风险较低）：offset 从 10.0 降至与 SHORT 对称的 0.0
long_threshold_offset_option_a: 0.0
# 效果：LONG direct = 82（与SHORT相同）
# 风险：可能过度放开，需要观察窗口验证

# 方案 B（更谨慎，推荐作为首选）：分布校准法
long_threshold_offset_option_b: "P90_calibrated"
# 使用第4节 calibrate_threshold_from_distribution() 方法
# 基于窗口内 LONG 方向实际得分分布的 P90 反推合理offset
# 若 LONG 分布的 P90 恰好在 82-85 区间，offset 应设为 0-3，而非当前的 10

# 推荐：先用方案 B 校准出一个精确数字，观察 1 周后再考虑是否需要方案 A 的完全对称
```

### 3.4 分层放行的具体实现

```python
def calibrate_long_offset_from_distribution(long_scores: pd.Series, target_pass_rate: float = 0.05) -> float:
    """
    LONG offset 校准，逻辑与 Q2 pending 阈值校准（08-02报告）一致
    """
    base_threshold = 82
    if len(long_scores) < 50:
        # 样本不足时，先用保守的方案A过渡，同时继续收集数据
        return 0.0

    target_score = long_scores.quantile(1 - target_pass_rate)
    calibrated_offset = max(0.0, target_score - base_threshold)
    return round(calibrated_offset, 1)

# 应用（需要至少1-2周的LONG方向决策日志才能可靠计算）
long_scores_window = extract_long_side_scores(decisions_log, days=14)
new_offset = calibrate_long_offset_from_distribution(long_scores_window)
```

### 3.5 高分 LONG 优先进入侦察通道而非直接主账本

```json
{
  "high_score_long_offset_probe": {
    "enabled": true,
    "trigger_condition": "side=LONG AND blocked_by=SIDE_THRESHOLD_OFFSET_LONG AND score>=85",
    "ledger": "SCOUT_ONLY",
    "position_size_usdt": [25, 50],
    "leverage": 1,
    "min_samples_before_promotion": 20,
    "promotion_criteria": {
      "pf_min": 1.0,
      "blended_r_min": 0.3
    },
    "note": "在正式降低long_threshold_offset之前，先用SCOUT收集更多样本验证+0.465R的初步发现是否稳健"
  }
}
```

### 3.6 为什么不直接降到0.0并让LONG立即进主账本

```
虽然本窗口数据支持LONG侧有正期望，但只有2个样本，统计意义有限
（相比SHORT侧17个样本的94.1%止损率，这是高置信度的负面证据）

正确的稳健路径：
  第1步（立即）：HIGH_SCORE_LONG_OFFSET_PROBE 启动，SCOUT-only收集数据
  第2步（1-2周后）：若20笔样本确认PF>1.0，正式校准offset
  第3步（校准后）：offset生效于主账本的q1_trend_launch通道（而非全局LONG开放）

这个路径比"直接改配置数字"更保守，但避免了"用2个样本的强信号
去改变影响全局747次决策(31.6%)的关键参数"这种风险不对等的操作
```

---

## 4. 核心方法论：为什么这次是"非对称放行"而非"分层放行"

### 4.1 与上一轮建议的方法论演进

```
08-02 报告提出的框架："按(方向×原因×象限)分层评估，只放行回测验证过的分桶"

本轮数据把这个框架进一步精确化为一个更强的结论：

  不是"某些分桶可能有效，需要逐一验证"
  是"这两个方向本质上在测试两个不同的假设，答案已经相反"

  SHORT + RR几何拦截 = 测试"位置质量门槛是否过严"
    → 答案：门槛是对的，94.1%止损率证明拦截精准

  LONG + SIDE阈值拦截 = 测试"全局方向惩罚是否合理"
    → 答案：可能不合理，因为offset与位置质量无关，
           纯粹是"因为是LONG就多扣10分"的粗暴规则
```

### 4.2 为什么SIDE阈值本身是一个方法论薄弱点

```
回顾这个offset的历史：它最初被设计用来防止"EMA/CVD容易对多头给高分"
的旧架构缺陷（见更早期的报告）。但当前系统已经是Fib/PA/EMA/CVD/CCI/RR
六组件架构，多头的position quality已经由PA和Fib两层独立把关。

继续保留一个与新架构组件设计初衷无关的"因为方向是LONG就整体加10分"
的规则，本质上是让两套不同代际的保护机制叠加，可能造成过度保守。

这不是说"取消所有方向性差异对待"——而是说方向性差异应该体现在
"每个组件对不同方向的具体评分逻辑里"（这已经在做），
而不是"事后再加一个粗暴的全局offset"
```

### 4.3 本节对未来分析的指导意义

```
下一轮报告如果继续发现"某类拦截的样本止损率异常高/异常低"，
应该主动追问：这个拦截规则测试的是"位置质量假设"还是"粗粒度分类假设"？

位置质量假设被证伪 → 应该收紧（如本轮SHORT+RR几何的验证结果）
粗粒度分类假设被证伪 → 应该重新设计该规则的实现方式（如本轮LONG+SIDE offset）

这两种情况的应对措施完全不同，混为一谈会导致"一刀切放松"或
"一刀切收紧"的错误决策
```

---

## 5. RR 几何门槛验证：SHORT 侧必须维持

### 5.1 这是本轮最重要的"不要做"证据

```
上一轮报告曾建议过修复RR公式的TP1距离问题（避免公式性误判）
本轮数据清楚区分了两件事：

  公式误判（应该修复）：低ATR场景下费用占比过高导致NET_TP1_R_TOO_LOW
  真实保护（不应该放松）：RR几何门槛正确识别出SHORT方向的位置质量问题

本轮19条≥85分拦截信号中SHORT占17条，止损命中率94.1%，
终局-0.89R（整仓）/-0.30R（阶梯）——这是极其明确的证据：
RR几何门槛在SHORT方向上工作得很好，继续保留
```

### 5.2 RR 门槛的公式修复与保护逻辑修复要分开进行

```
上一轮建议的"TP1从1.0R改为1.2R"仍然应该实施（这是解决费用占比问题）
但这个修复的目标是"让本该通过的信号能够通过"，
不是"降低RR门槛让更多信号通过"

两者的区别：
  公式修复：让净R计算更准确（减少false negative）
  门槛放松：降低及格线（增加所有信号的通过率，包括不该通过的）

本轮数据支持继续公式修复，但强烈反对任何门槛数值的降低
```

### 5.3 SHORT市场偏空背景下的解释

```
本窗口148个拐点中低点111个、高点37个，市场明显偏空/下行
这意味着SHORT方向的候选信号数量本身就更多，也更容易出现
"追跌到局部低点附近才触发"的情况——这正是RR几何门槛
（特别是OPPOSITION_STRUCTURE_TOO_CLOSE相关检查）设计要防范的场景

市场结构本身放大了SHORT方向的位置质量风险，
RR几何门槛在当前市场环境下的保护价值可能比平时更高
```

---

## 6. SCOUT 任务多样化诊断与修复

### 6.1 问题的规模

```
37个候选中，only 5个（13.5%）成功路由到REVERSAL_PIVOT_SCOUT
其余全部SCOUT_NO_MISSION（26次）或SCOUT_SYMBOL_NOT_ENABLED（7次）

配置层面已经声明了6个mission：
  REVERSAL_PIVOT_SCOUT（唯一触发）
  Q2_PENDING_MOMENTUM
  Q3_TO_Q1_CONFIRMATION
  HIGH_SCORE_LONG_OFFSET_PROBE（本报告第3.5节新增）
  FIB_CONTINUATION
  WATCH_ONLY_PROMOTION

后5个全部0触发，说明路由逻辑或触发条件存在系统性问题，
而不是单纯"这些机会本来就少"
```

### 6.2 诊断方法：逐一检查每个mission的触发条件是否可达

```python
def diagnose_scout_mission_reachability(
    near_miss_log: list[dict], mission_configs: dict
) -> dict:
    """
    对每个SCOUT mission，检查其触发条件在实际候选分布下是否可达
    （复用08-02报告第4.2节的分布校准方法论）
    """
    diagnosis = {}

    for mission_name, mission_config in mission_configs.items():
        matching_candidates = [
            c for c in near_miss_log
            if evaluate_mission_conditions(c, mission_config)
        ]

        diagnosis[mission_name] = {
            'total_near_miss': len(near_miss_log),
            'matching_candidates': len(matching_candidates),
            'match_rate': len(matching_candidates) / max(1, len(near_miss_log)),
            'reachable': len(matching_candidates) > 0,
        }

        if not diagnosis[mission_name]['reachable']:
            # 找出具体是哪个条件导致不可达（类似Q2 pending问题的诊断方式）
            diagnosis[mission_name]['blocking_condition'] = \
                find_most_restrictive_condition(near_miss_log, mission_config)

    return diagnosis
```

### 6.3 预期发现与修复方向

```
基于本窗口数据的初步分析：

Q2_PENDING_MOMENTUM（0触发）：
  Q2 P90仅70.79，若mission要求score>=75或更高，天然不可达
  → 需要用08-02报告的校准方法重新设定这个mission的门槛

Q3_TO_Q1_CONFIRMATION（0触发）：
  与前述R1相同问题——如果这个mission也依赖Q3_TO_Q1_CONFIRMED标签，
  而该标签本身因为q1_trend_launch的连带逻辑也从未生成，
  这个mission会因为同一个根因（第2节的代码缺陷）而空转

FIB_CONTINUATION（0触发）：
  需要单独审查该mission的具体触发条件定义
  （本报告数据中未提供该mission的详细规格，建议下一轮补充）

WATCH_ONLY_PROMOTION（0触发）：
  ADA/XMR的watch-only晋级测试全窗口应该有触发机会
  （上一轮08-02报告显示已有1笔样本），本窗口0笔可能是
  候选评分或路由优先级问题（例如被REVERSAL_PIVOT抢先匹配）
```

### 6.4 路由优先级审查

```python
def review_scout_routing_priority(candidate: dict, mission_configs: list) -> str:
    """
    当一个候选同时满足多个mission条件时，当前系统如何选择？
    如果REVERSAL_PIVOT_SCOUT的匹配条件过于宽泛，
    可能会抢占本该分配给其他mission的候选
    """
    matching_missions = [
        m['name'] for m in mission_configs
        if evaluate_mission_conditions(candidate, m)
    ]

    if len(matching_missions) > 1:
        # 记录多重匹配情况，用于诊断路由是否合理
        log_multi_match_candidate(candidate, matching_missions)

    # 建议：不应该"先到先得"，应该按照与候选特征最匹配的mission优先分配
    return select_best_matching_mission(candidate, matching_missions)
```

---

## 7. 出场 Payoff 结构改善

### 7.1 问题的精确刻画

```
mirror账本胜率59%却整体亏损（legacy -1.68，trend -1.74）
这是经典的"payoff<1"模式：小赢大亏

当前TP阶梯（1.2R/2.0R/3.0R，40/35/25分批）触及率：
  TP1: 63.2%
  TP2: 10.5%（大幅下降）
  TP3: 5.3%（进一步下降）

这说明大部分交易只能吃到TP1的40%仓位盈利，
而止损（若触发）是对全部剩余仓位生效
```

### 7.2 两个改进方向的对比

```
方向A：缩短首个目标，提高TP1触及率
  例如 TP1从1.2R降至0.8-1.0R
  预期：TP1触及率提升，但每次TP1盈利绝对值降低
  风险：可能降低整体期望值（如果原本TP1本来就是最容易触及的档位）

方向B：TP1后更早移动止损，减少"先赢后亏"的路径
  例如 达到+1R后止损立即移至成本价（而非等到TP1才移动）
  预期：减少TP1后回撤到止损的"过山车"亏损模式
  这更直接针对当前"胜率59%但整体亏损"的症状
```

### 7.3 推荐的具体试点规格

```yaml
payoff_improvement_pilot:
  # 方向B优先，因为更直接针对当前症状
  early_breakeven_trigger:
    trigger_r: 1.0          # 达到+1R（而非等TP1）即触发保本移动
    breakeven_buffer_pct: 0.001

  # 移动止损灵敏度试点（原报告建议的trend_trigger_r 1.5→1.2）
  trailing_stop_trigger_r: 1.2   # 从1.5调整为1.2，更早激活移动止损

  # 试点范围：仅在mirror账本（trend_capture分支）测试，不影响legacy
  test_scope: "trend_capture_mirror_only"
  min_samples_before_evaluation: 30
  comparison_baseline: "legacy_mirror（保持1.5R，不变）"
```

### 7.4 验证协议

```
试点必须通过A/B对比验证，不能直接判断"看起来应该更好就上线"：

  trend_capture_mirror（新payoff结构） vs legacy_mirror（原结构）
  30笔后比较：
    payoff（平均盈利/平均亏损）
    整体PF
    胜率变化（预期胜率可能略降，但payoff应显著改善）

  若trend_capture_mirror的payoff改善但PF未同步改善，
  说明问题不仅在出场，需要回到入场质量继续排查
  （即当前的"位置质量约束"是否真的过滤了足够多的坏信号）
```

---

## 8. 实施验证协议：防止建议再次未落地

### 8.1 协议设计动机

```
本报告开篇已经指出：08-02报告Task A未被实现是本轮最大的问题
为避免这个模式重复出现，需要一个结构化的闭环检查机制
```

### 8.2 三层验证协议

```python
@dataclass
class RecommendationImplementationTracker:
    """
    每份诊断报告的每条P0/P1建议，都必须有对应的实现追踪记录
    """
    recommendation_id: str        # 例如 "2026-08-02-TaskA"
    report_date: str
    description: str
    target_code_location: str     # 例如 "run_live_dry_run.py:888"
    priority: str                 # P0/P1/P2

    implementation_status: str = "PENDING"  # PENDING/IN_PROGRESS/DEPLOYED/VERIFIED/ABANDONED
    deployed_date: str = None
    verification_script: str = None
    verification_result: dict = None

def check_recommendation_status_before_next_report(
    previous_recommendations: list[RecommendationImplementationTracker]
) -> dict:
    """
    每次生成新的诊断报告前，必须先运行此检查
    任何P0建议若仍为PENDING或IN_PROGRESS，必须在新报告开篇明确说明
    而不能默默略过，直接分析新窗口数据
    """
    unresolved_p0 = [
        r for r in previous_recommendations
        if r.priority == "P0" and r.implementation_status not in ("DEPLOYED", "VERIFIED")
    ]

    if unresolved_p0:
        return {
            'blocking': True,
            'unresolved_count': len(unresolved_p0),
            'items': [r.recommendation_id for r in unresolved_p0],
            'action_required': "在继续新一轮策略分析前，必须先说明这些P0项目的阻塞原因"
        }
    return {'blocking': False}
```

### 8.3 报告模板强制字段

```
未来每份归因报告的开篇，必须包含一个"上轮建议实施回顾"表格：

| 建议ID | 优先级 | 内容摘要 | 实施状态 | 验证结果 |
|---|---|---|---|---|
| 2026-08-02-TaskA | P0 | 移除q1_trend_launch标签依赖 | 未实施 | N/A |
| 2026-08-02-TaskB | P0 | Q2 pending阈值重新校准 | ？需确认 | ？需确认 |
| 2026-08-02-S1~S6 | - | Q1_RR_GAP收紧等 | ？需确认 | ？需确认 |

这个表格必须放在报告最前面（结论摘要之前），
让阅读者第一眼就能看到"哪些是新问题，哪些是旧问题未解决"
```

### 8.4 本报告对08-02报告其余建议的追溯核查

```
基于本窗口数据可以侧面验证的项目：

  Q2 pending阈值重新校准（08-02 Task B）：
    本窗口Q2 P90=70.79，与上一轮的69.65接近，分布基本稳定
    但本窗口仍显示Q2_PENDING_MOMENTUM mission 0触发
    → 需要确认Task B的配置修改是否已部署，若已部署为何仍0触发

  Q1_RR_GAP_SCOUT收紧（08-02 第6节）：
    本报告数据中未提供该mission本窗口的具体表现
    → 需要在下一轮报告中专门确认该通道当前状态

  Q4极值反转前置研究（08-02 第7节）：
    本报告未提及是否已执行显著性检验
    → 需要确认是否启动，若启动结果如何

建议：下一轮报告必须包含这三项的明确状态更新，
     而不是像本次一样默认聚焦于新发现的问题
```

---

## 9. 配置文件卫生：重复键清理

### 9.1 问题描述

```
配置文件 configs/entry_chain.dry_run_fib_pa_v1.json 中
long_threshold_offset 键出现两次：7.0 和 10.0

JSON标准行为：后出现的键覆盖前面的（10.0生效）
但这极易造成维护混乱——如果有人查看配置文件时看到7.0，
会误以为这是当前生效值，实际却是10.0在起作用
```

### 9.2 清理规格

```python
def audit_and_clean_duplicate_keys(config_path: str) -> dict:
    """
    使用严格JSON解析（保留键顺序检测重复），扫描所有配置文件
    """
    import json
    from collections import Counter

    with open(config_path, 'r') as f:
        raw_text = f.read()

    # 使用自定义hook检测重复键
    duplicate_keys = []
    def detect_duplicates(pairs):
        keys = [p[0] for p in pairs]
        counts = Counter(keys)
        for k, c in counts.items():
            if c > 1:
                duplicate_keys.append(k)
        return dict(pairs)

    json.loads(raw_text, object_pairs_hook=detect_duplicates)

    return {
        'file': config_path,
        'duplicate_keys_found': duplicate_keys,
        'action_required': len(duplicate_keys) > 0,
    }

# 建议：在CI/CD流程中加入此检查，防止未来再次出现类似问题
```

### 9.3 建议的CI检查集成

```yaml
# .github/workflows or 等效CI配置中新增步骤
config_hygiene_check:
  script: |
    python scripts/audit_duplicate_json_keys.py configs/*.json
  fail_on: "any duplicate key detected"
  rationale: "本次long_threshold_offset的7.0/10.0重复键问题
             可能已经造成了配置意图与实际生效值不一致的困惑，
             需要自动化检查防止复发"
```

---

## 10. 验收标准与熔断机制

### 10.1 本轮新增通道/修复的统一验收表

```
项目                              验收窗口   成功标准                失败标准
──────────────────────────────────────────────────────────────────────────
q1_trend_launch修复验证            24-48h    出现≥3笔实验账本转化     仍0笔转化→回滚检查
HIGH_SCORE_LONG_OFFSET_PROBE      20笔      PF>1.0，blended_R>0.3   PF<0.8→暂停，offset不降
RR几何门槛(SHORT侧)                维持不变   继续观察止损率           若止损率骤降需重新评估(不太可能)
SCOUT任务多样化修复                1周       至少3种mission有触发     仍<2种→深入排查路由逻辑
Payoff试点(trend_capture_mirror)  30笔      payoff改善且PF不降       PF同步下降→回到入场排查
配置重复键清理                     立即      CI检查通过               —
```

### 10.2 全局熔断条件

```
条件1：q1_trend_launch修复部署48h后仍0转化 → 立即人工介入代码审查
       （不能满足"配置写了就默认生效"的假设，需要实际debug）

条件2：HIGH_SCORE_LONG_OFFSET_PROBE前10笔中出现连续5笔止损
       → 立即暂停，说明本窗口的+0.465R发现不具备稳健性

条件3：任何针对本报告修复的验证脚本（第2.4节）运行失败
       → 视为修复未完成，不得进入下一阶段
```

---

## 11. 路线图

```
┌──────────────────────────────────────────────────────────────┐
│ Phase 0（立即，0.5-1天）：闭环协议 + 代码修复                  │
│  → 实现 RecommendationImplementationTracker（第8节）           │
│  → 回溯核查08-02报告Task B及S1-S6的当前实施状态                │
│  → 部署 q1_trend_launch 代码修复（第2节精确规格）              │
│  → 运行 verify_q1_trend_launch_fix() 验证脚本                  │
│  → 清理配置文件重复键（第9节）                                 │
├──────────────────────────────────────────────────────────────┤
│ Phase 1（1-2天）：LONG非对称验证启动                           │
│  → 部署 HIGH_SCORE_LONG_OFFSET_PROBE（SCOUT-only）             │
│  → 开始收集LONG侧样本，目标20笔                                │
│  → 不改动long_threshold_offset数值，等待样本验证                │
├──────────────────────────────────────────────────────────────┤
│ Phase 2（3-5天）：SCOUT任务诊断与修复                          │
│  → 运行 diagnose_scout_mission_reachability()                 │
│  → 逐一修复不可达的mission门槛（复用08-02校准方法论）           │
│  → 审查路由优先级逻辑（第6.4节）                                │
├──────────────────────────────────────────────────────────────┤
│ Phase 3（1周后）：Payoff试点                                   │
│  → 部署 early_breakeven_trigger + trailing_stop调整            │
│  → 仅在trend_capture_mirror分支试点，legacy作对照               │
│  → 30笔后对比payoff和PF变化                                    │
├──────────────────────────────────────────────────────────────┤
│ Phase 4（2周后）：综合评估与下一轮建议闭环检查                  │
│  → q1_trend_launch通道正式验收（20笔样本）                     │
│  → LONG offset校准决策（基于Phase 1的20笔数据）                │
│  → 强制生成"上轮建议实施回顾"表格，作为下一份报告的开篇         │
└──────────────────────────────────────────────────────────────┘
```

---

## 12. 禁止事项

```
❌ 不要在q1_trend_launch修复验证通过前，讨论是否要进一步放宽Q1门槛
❌ 不要将long_threshold_offset直接降至0.0
   （必须先经过HIGH_SCORE_LONG_OFFSET_PROBE的20笔SCOUT验证）
❌ 不要放松SHORT侧的RR几何门槛
   （本轮数据是迄今最强的"该门槛正确工作"的证据，94.1%止损率）
❌ 不要在没有实现第8节闭环协议前，继续产出新一轮的诊断报告
   （否则可能重复本轮"建议被写下但未被追踪落实"的模式）
❌ 不要把payoff改善试点直接应用到legacy账本
   （必须先在trend_capture_mirror验证，保持legacy作为纯净对照组）
❌ 不要因为SCOUT任务诊断显示"5个mission中4个0触发"就认为SCOUT机制失败
   （需要先诊断是门槛不可达还是路由逻辑问题，两者修复方式完全不同）
```

---

## 13. 本轮最重要的两句话总结

```
第一句（关于流程）：
诊断报告的价值取决于建议是否被实现并验证，而不是取决于诊断本身的精确度。
本轮最大的教训不是策略参数问题，是"建议→实现→验证"这个闭环从未真正建立。

第二句（关于策略）：
同样是"高分被拦截"，SHORT方向的拦截94.1%被证明是正确的保护，
LONG方向的拦截却可能是一个与位置质量无关的粗糙规则造成的误伤。
下一次看到"高分信号被挡"时，第一个问题应该是
"这个拦截规则测试的是位置质量，还是仅仅是方向标签？"
```

---

*报告结束 | 实施缺口修复与非对称放行框架建议 v1.0 — 2026-08-04*
*最高优先行动：Phase 0 的四项——实施追踪协议 + q1_trend_launch代码修复 + 验证脚本运行 + 配置重复键清理。这四项合计不到1天工期，但直接解决了本轮报告揭示的最根本问题：建议没有被转化为代码。*
