# 管道一致性修复与分桶验证建议
> 2026-08-07 22:00 至 2026-08-11 18:45 | 五个评审问题回答与工程补充
> 日期：2026-08-11

---

## 目录

1. [总体评估：诊断质量确认](#1-总体评估诊断质量确认)
2. [直接回答五个评审问题](#2-直接回答五个评审问题)
3. [元模式：这是第二次"管道未对齐"缺陷](#3-元模式这是第二次管道未对齐缺陷)
4. [重要澄清：q1_trend_launch_v2 不是推翻 08-04 的修复](#4-重要澄清q1_trend_launch_v2-不是推翻-08-04-的修复)
5. [Task A-D 验证协议补充](#5-task-a-d-验证协议补充)
6. [LONG offset continuation 证据强度校准](#6-long-offset-continuation-证据强度校准)
7. [REVERSAL_PIVOT_SCOUT 停用的正式化处理](#7-reversal_pivot_scout-停用的正式化处理)
8. [路线图](#8-路线图)

---

## 1. 总体评估：诊断质量确认

### 1.1 这份报告延续了上一轮建立的严谨性

```
上一轮（08-04）报告提出的两个方法论要求，在本轮都得到了体现：

  要求一："建议→实现→验证"闭环协议
  本轮体现：验收脚本复现（第1节）明确区分"有转化"和"进攻有效"，
           没有把q1_trend_launch的4笔转化误判为成功

  要求二：拦截规则要区分"位置质量问题"还是"粗粒度分类问题"
  本轮体现：R2对Q2 pending 0触发的诊断，精确定位到是
           near_miss_min_score=82这个上游采样阈值截断了下游mission，
           而非Q2 pending自身的70分门槛设计有误——这是对同一诊断
           框架的正确延伸应用
```

### 1.2 本轮最有价值的新方法论：反事实扫描先行验证

```
Q2 pending的修复建议附带了一个反事实扫描：
  若移除上游截断，36个pending会被创建，19个确认转Q1，
  4h前向MFE均值1.585R，11/19触及+1R

这个做法值得作为标准流程固化：任何管道修复在正式部署前，
先用历史数据反事实验证"修复后会发生什么"，
而不是修复完就直接上线观察

这比08-04报告的verify_q1_trend_launch_fix()（部署后验证）更进一步——
是部署前就先证明修复有意义，两者应该结合使用
```

---

## 2. 直接回答五个评审问题

### Q1：q1_trend_launch 已从"不开仓"转为"低RR Q1追单负期望"，应改为pending/source-confirmed？

**同意。且这个判断本身是本轮诊断中最重要的一步。**

```
证据链完整：4笔全部满足PA/Fib/CVD但RR仅0.5-2.0，
前向复盘0/4触及+1R、3/4触及-1R——
这精确证明了"Q1状态本身"不是进场理由，
"如何进入Q1状态"（是否经历过回调蓄势）才是关键区分变量

这个结论与第4节的历史脉络高度吻合：
08-04报告修复的是"标签永远不生成导致0转化"的工程问题，
本轮发现的是"移除标签依赖后，需要一个新的、真正有效的
确认机制来替代它"——这是同一个问题在不同阶段的正确演进，
而不是来回摇摆
```

### Q2：Q2 pending 0触发根因是上游near_miss_min_score=82截断，而非70分门槛不合理？

**同意，证据充分。**

```
Q2 P90=69.69，max=78.87——这两个数字本身就说明
82分的上游采样阈值会截断几乎全部Q2样本（因为Q2定义上
资金动能轴不通过，分数天花板本来就低于Q1）

这与08-02报告诊断Q2 pending"85分门槛不可达"是同一类错误的重现：
先是mission自身门槛设错，修复后又发现上游采样门槛没有同步调整
```

### Q3：LONG offset continuation应先shadow/SCOUT验证，不直接改主账本long_threshold_offset？

**强烈同意，且这个立场需要与08-07（ATOM报告）的审查结论衔接。**

```
08-07审查报告曾经指出：HIGH_SCORE_LONG_OFFSET_PROBE三日仅3笔且PF=0，
但同一份报告却直接把long_threshold_offset从10.0改为0.0——
这是一个未经充分验证就执行的全局参数改动，当时建议回滚观察

本轮数据（7个LONG offset样本，score>=82，terminal均值+0.101R）
应该被理解为"回滚观察期"内继续积累的新证据，而非独立的新发现

结论：继续shadow/SCOUT验证的方向完全正确，
     且这次的方案（S3设计的LONG_OFFSET_CONTINUATION_SCOUT/SHADOW
     双层结构，RR>=2进真实SCOUT，RR<2进shadow）
     比简单的全局offset改动更精细、风险更可控
```

### Q4：REVERSAL_PIVOT_SCOUT应暂停或降级？

**同意，且建议正式记录停用决策而非静默关闭（见第7节）。**

### Q5：trend_capture A/B失败主因是入场池MFE不足，不应触发自动切换或继续调出场参数？

**同意。**

```
mirror样本平均MFE仅0.521R，MFE>=1.5的样本仅3/33（9%）——
在这种入场质量下，无论出场规则如何设计，
可分配的"趋势捕捉空间"本身就不存在

这与08-04报告第7节的判断一致：出场payoff改善的前提是
入场质量已经过滤掉大部分噪音，当前入场池显然还没有做到这一点
```

---

## 3. 元模式：这是第二次"管道未对齐"缺陷

### 3.1 两次缺陷的对比

```
缺陷一（08-04发现）：
  q1_trend_launch要求确认标签，但标签生成逻辑本身有bug（从未生成）
  性质：下游逻辑依赖一个从未被正确实现的上游产物

缺陷二（本轮发现）：
  Q2 pending门槛已修复为70，但上游near_miss采样仍用全局82分截断
  性质：下游逻辑正确，但被一个未同步调整的上游全局参数挡住

两者的共同特征：都是"修改了A组件的配置，但没有检查A组件
是否依赖B组件的某个未被同步修改的参数或产物"
```

### 3.2 建议的系统性预防机制

```python
def audit_pipeline_coherence(config: dict, mission_registry: list[str]) -> dict:
    """
    每次修改任何mission相关阈值后，运行此审计
    检查该mission的候选来源是否会被更上游的全局参数提前截断
    """
    issues = []

    global_near_miss_threshold = config.get('near_miss_min_score', 82.0)

    for mission_name in mission_registry:
        mission_config = config.get(mission_name, {})
        mission_score_min = mission_config.get('min_score')

        if mission_score_min is None:
            continue

        # 核心检查：mission自身门槛是否低于上游全局截断阈值
        if mission_score_min < global_near_miss_threshold:
            issues.append({
                'mission': mission_name,
                'mission_threshold': mission_score_min,
                'upstream_global_threshold': global_near_miss_threshold,
                'severity': 'BLOCKING',
                'explanation': (
                    f"{mission_name}门槛({mission_score_min})低于上游"
                    f"near_miss_min_score({global_near_miss_threshold})，"
                    f"该mission的候选会在到达自身评估前被上游截断"
                )
            })

    return {'coherent': len(issues) == 0, 'issues': issues}

# 建议：作为CI检查项，或至少作为每次修改mission配置后的强制手动检查步骤
```

### 3.3 为什么这比逐一修复更重要

```
本轮已经识别并计划修复Q2 pending的这个具体实例（Task A）
但Q3_TO_Q1_CONFIRMATION是否存在同样的问题？

报告第3.2节R2的分析逻辑同样适用：如果Q3_TO_Q1_CONFIRMATION
的pending创建条件（score>=82，见原始08-02报告）本身就等于或
高于全局near_miss阈值，可能不受影响；但如果任何未来新增的
mission使用了低于82的门槛，同样的bug会再次出现

audit_pipeline_coherence()应该在Task A修复的同时运行一次全量检查，
而不是只修复被发现的这一个实例
```

---

## 4. 重要澄清：q1_trend_launch_v2 不是推翻 08-04 的修复

### 4.1 需要明确说明的历史脉络

```
08-04报告的修复内容：移除对Q2_PENDING_MOMENTUM_CONFIRMED/
                    Q3_TO_Q1_CONFIRMED标签的依赖，
                    因为这两个标签当时从未被生成过（纯粹的死代码路径）

本轮S2建议：q1_trend_launch_v2重新要求
           source_required: [Q2_PENDING_MOMENTUM_CONFIRMED,
                              Q3_TO_Q1_CONFIRMED,
                              LONG_OFFSET_CONTINUATION_CONFIRMED]

表面上看，这像是"删除标签依赖→又要求标签"的反复
但两者有本质区别，需要在实施时明确记录：

  08-04之前：标签依赖是"死"的——生成标签的代码路径本身有bug，
            要求一个永远不会出现的东西，等于永久关闭通道

  本轮建议：标签依赖是"活"的——前提是Task A先修复Q2/Q3 pending
           的上游截断问题，让这些标签能够被正确生成
           （反事实扫描已证明：19个Q2 pending会成功确认）
```

### 4.2 实施顺序的强约束

```
这个区别决定了实施顺序不能颠倒：

  正确顺序：
    1. 先完成Task A（修复Q2/Q3 pending上游截断）
    2. 验证标签确实开始被生成（用类似08-04第2.4节的验证脚本）
    3. 再部署q1_trend_launch_v2（S2），使其依赖这些"活"标签

  错误顺序（需要避免）：
    若在Task A完成前就部署S2，会立刻重现08-04发现的问题——
    q1_trend_launch再次因为标签不存在而完全空转，
    这次的"空转"和上次是同一个根因的重复发作

建议：本轮报告的Task列表应该明确标注S2依赖Task A完成，
     而非并行推进
```

---

## 5. Task A-D 验证协议补充

### 5.1 为每个Task补充部署后验证脚本（复用08-04模式）

```python
def verify_task_a_pending_pipeline_fix(decisions_log: str, hours: int = 24) -> dict:
    """Task A验证：Q2/Q3 pending是否开始正确产生候选"""
    q2_pending_created = count_events(decisions_log, event_type='Q2_PENDING_CREATED', hours=hours)
    q2_pending_confirmed = count_events(decisions_log, event_type='Q2_PENDING_MOMENTUM_CONFIRMED', hours=hours)

    if q2_pending_created == 0:
        raise RuntimeError("Task A未生效：24h内仍无Q2 pending创建记录")

    return {
        'pending_created': q2_pending_created,
        'pending_confirmed': q2_pending_confirmed,
        'conversion_rate': q2_pending_confirmed / max(1, q2_pending_created),
        'fix_verified': q2_pending_created > 0,
    }


def verify_task_b_long_offset_routing_fix(scout_decisions_log: str, hours: int = 24) -> dict:
    """Task B验证：LONG offset候选是否不再被REVERSAL_PIVOT_SCOUT抢占"""
    long_offset_candidates = filter_candidates(
        scout_decisions_log, reason_contains='SIDE_THRESHOLD_OFFSET_LONG', hours=hours
    )
    stolen_by_reversal = [
        c for c in long_offset_candidates
        if c['assigned_mission'] == 'REVERSAL_PIVOT_SCOUT'
    ]

    return {
        'total_long_offset_candidates': len(long_offset_candidates),
        'stolen_by_reversal_pivot': len(stolen_by_reversal),
        'fix_verified': len(stolen_by_reversal) == 0,
    }


def verify_task_c_reversal_pivot_disabled(scout_decisions_log: str, hours: int = 24) -> dict:
    """Task C验证：REVERSAL_PIVOT_SCOUT真实开仓是否为0（shadow记录应继续）"""
    real_opens = count_real_opens(scout_decisions_log, mission='REVERSAL_PIVOT_SCOUT', hours=hours)
    shadow_records = count_shadow_records(scout_decisions_log, mission='REVERSAL_PIVOT_SCOUT', hours=hours)

    return {
        'real_opens': real_opens,
        'shadow_records': shadow_records,
        'fix_verified': real_opens == 0 and shadow_records > 0,
    }
```

### 5.2 强制执行顺序（补充报告未明确说明的依赖关系）

```
Task A（Q2/Q3 pending上游截断修复）
  ↓ 必须先验证通过
Task B（LONG offset continuation分桶 + 路由优先级调整）
  ↓ 可与Task C并行
Task C（REVERSAL_PIVOT_SCOUT暂停/降级）
  ↓ 
S2（q1_trend_launch_v2，依赖Task A产生的"活"标签）
  ↓
Task D（分桶A/B报告，需要前面所有分桶都已独立运行产生数据）
```

---

## 6. LONG offset continuation 证据强度校准

### 6.1 当前样本的诚实评估

```
本窗口7个样本：4/7触及+1R，3/7触及-1R，terminal均值+0.101R

这个数字需要被谨慎解读：
  +0.101R是"勉强为正"，不是"明确的正期望"
  样本量7仍然远低于S3自己设定的验收标准（shadow>=10, real scout>=3）

累计视角（结合08-04的2个样本 + 本轮7个样本 = 9个样本）：
  样本量正在朝着有意义的方向增长，但尚未达到20笔的
  最小可靠评估门槛（这是08-04报告设定的标准）
```

### 6.2 不应过早得出结论

```
建议在下一轮报告前，明确统计累计样本量而非仅报告当前窗口：
  若9个样本的累计terminal均值仍然只是"勉强为正"（如+0.1R量级），
  这至少说明LONG offset continuation不是一个强边际信号，
  即使最终验证通过，其贡献可能也是"小幅正期望"而非"显著Alpha来源"

这不改变"继续shadow验证"的建议方向，但建议管理预期：
  即使Task B完全按计划实施，也不应期待LONG offset continuation
  单独解决当前account level的整体负期望问题
  （legacy PF 0.0426，这个缺口远大于LONG offset单一分桶能填补的量级）
```

---

## 7. REVERSAL_PIVOT_SCOUT 停用的正式化处理

### 7.1 不建议静默关闭，建议记录完整决策依据

```
REVERSAL_PIVOT_SCOUT曾是最早期跑通的SCOUT通道之一
（追溯至更早的报告，它是第一个产生真实交易样本的实验mission）

累计表现（跨多个窗口）：
  更早窗口：4笔，净-0.26
  本窗口：9笔，净-0.6524
  累计：13笔，净约-0.91

停用理由已经充分（持续负期望 + 抢占路由优先级），
但建议正式记录为"已验证无效并停用"的结论，而非简单改配置：

decision_log_entry = {
    'mission': 'REVERSAL_PIVOT_SCOUT',
    'status': 'DEPRECATED',
    'deprecation_date': '2026-08-11',
    'cumulative_samples': 13,
    'cumulative_pnl': -0.91,
    'rationale': '持续负期望且路由优先级抢占更有潜力的LONG_OFFSET_CONTINUATION候选',
    'alternative': 'Q4极值反转假设若需继续研究，应重新设计为独立shadow-only通道，'
                   '不复用当前REVERSAL_PIVOT_SCOUT的触发逻辑'
}
```

### 7.2 Q4极值反转假设本身尚未被证伪，只是当前实现方式失败

```
需要区分两件事：
  "REVERSAL_PIVOT_SCOUT这个具体实现"失败了（13笔负期望）
  "拐点反转"这个假设本身是否被证伪，尚不确定

08-02报告提出Q4反转研究时，曾要求先做统计显著性检验
（第7.1节：二项检验判断匹配率是否显著非随机）
如果这个前置检验从未被执行，那么当前REVERSAL_PIVOT_SCOUT的失败
可能只是说明"当前的触发条件设计不对"，而非"反转研究方向错误"

建议：在正式停用REVERSAL_PIVOT_SCOUT的同时，
     若未来仍有兴趣重启反转研究，应回到08-02报告设计的
     显著性检验前置步骤，而不是简单复用旧mission的触发逻辑
```

---

## 8. 路线图

```
┌──────────────────────────────────────────────────────────────┐
│ 立即（0.5天）：全量管道一致性审计                               │
│  → 运行 audit_pipeline_coherence()（第3.2节），全面检查        │
│    是否还有其他mission存在类似Q2 pending的上游截断问题          │
│  → 正式记录REVERSAL_PIVOT_SCOUT停用决策（第7.1节）              │
├──────────────────────────────────────────────────────────────┤
│ 1-2天：Task A 优先实施                                         │
│  → 修复Q2/Q3 pending上游near_miss_min_score截断                │
│  → 运行verify_task_a_pending_pipeline_fix()确认标签开始生成    │
│  → 确认前必须先看到反事实扫描预测的36个pending实际被创建         │
├──────────────────────────────────────────────────────────────┤
│ 2-3天：Task B + Task C 并行实施                                │
│  → LONG_OFFSET_CONTINUATION_SCOUT/SHADOW双层分桶                │
│  → 路由优先级调整（若Task C未完全停用reversal pivot，
│    至少确保continuation优先）                                  │
│  → REVERSAL_PIVOT_SCOUT改为shadow-only或完全停用                │
├──────────────────────────────────────────────────────────────┤
│ Task A验证通过后：部署 q1_trend_launch_v2（S2）                │
│  → 依赖Task A产生的"活"标签，不能提前部署（第4.2节强约束）       │
├──────────────────────────────────────────────────────────────┤
│ 1周后：Task D 分桶A/B报告 + 累计样本评估                       │
│  → LONG offset continuation累计样本达20笔时正式评估             │
│  → 各分桶（SHORT+RR gap / LONG offset / Q2 pending confirmed /  │
│    watch-only晋级）独立产出PF/MFE/MAE报告                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 9. 一句话结论

```
本轮报告的诊断质量延续了上一轮建立的标准，且新增的反事实扫描方法论
（部署前先验证修复是否有意义）是值得固化的流程改进。

五个评审问题的答案全部为"同意"，因为报告自身的证据链已经充分支撑
这些结论。真正需要补充的不是方向判断，而是三个执行层面的细节：

  一是用audit_pipeline_coherence()系统性排查是否还有其他
     "配置改了但上游未同步"的隐藏实例，而不只是修复已发现的这一个；

  二是明确q1_trend_launch_v2必须在Task A验证通过后才能部署，
     避免重蹈"标签永远不生成"的覆辙；

  三是对LONG offset continuation的+0.101R保持谦逊的预期——
     这是值得继续验证的方向，但不太可能单独解决当前账本
     整体负期望的量级问题。
```

---

## 10. 与 08-07 ATOM 审查报告的交叉验证

### 10.1 两份报告之间的一致性检查

```
08-07报告（ATOM漏选审查）的核心建议是：
  回滚long_threshold_offset至10.0，因为HIGH_SCORE_LONG_OFFSET_PROBE
  探针通道当时只有3笔且PF=0，不足以支持直接归零offset

本轮（08-11）报告的数据：
  LONG offset样本增加到7个（score>=82，SIDE_THRESHOLD_OFFSET_LONG拦截），
  terminal均值转为+0.101R（弱正）

这两份报告放在一起看，形成了一个完整的证据演化链：
  08-07时点：3笔全负 → 建议回滚，继续观察
  08-11时点：累计7笔（含新增4笔），转为弱正 → 支持继续shadow验证

这个演化本身验证了"不要在小样本上做全局参数改动"的谨慎立场是正确的——
如果08-07时直接采纳了offset归零的决定，且后续样本像08-07看到的3笔
一样持续为负，回滚的政治成本和信任成本会远高于现在这种
"全程保持谨慎、让证据自然积累"的路径
```

### 10.2 建议下一轮报告明确标注跨报告样本的累计口径

```
当前问题：不同报告的"LONG offset样本数"可能存在窗口重叠或不重叠的歧义
  08-04报告：2个样本
  08-07报告：3个样本（HIGH_SCORE_LONG_OFFSET_PROBE三日验收口径）
  08-11报告：7个样本（本窗口口径，terminal均值+0.101R）

这些数字之间的关系（是否有重叠、是否是累计还是各自独立窗口）
在报告中没有被明确说明，容易造成"样本量到底是多少"的混淆

建议：未来涉及LONG offset continuation的报告，统一使用
     cumulative_sample_tracker，明确列出：
       本窗口新增样本数
       累计总样本数（去重后）
       累计terminal均值（加权，而非简单窗口平均值的平均）

这样才能准确判断是否已经达到20笔的最小可靠评估门槛
```

### 10.3 rank_end 与显式白名单机制的后续追踪

```
08-07报告建议：rank_end应恢复为25，改用显式白名单机制添加ATOM

本轮报告的四象限统计（第2节）显示的symbol覆盖范围
未明确说明当前rank_end是25还是90，也未提及ATOM是否已
按显式白名单方式添加（scout_only起步）

建议下一轮报告明确回答：
  当前rank_end实际配置值是多少？
  ATOM是否已经产生任何SCOUT层面的候选或样本？
  若已添加，其表现如何（哪怕只是1-2个样本的初步观察）？

这样才能确认08-07报告的审查意见是否被采纳，
避免出现类似q1_trend_launch标签依赖那样"建议写了但未落地"的情况
```

---

## 11. 累计问题清单（供下一轮报告开篇核对）

```
基于本轮报告的分析，建议下一轮归因报告的开篇"上轮建议实施回顾"
表格（08-04报告第8.3节设计的强制字段）应包含以下条目：

| 建议来源 | 优先级 | 内容摘要 | 本轮状态 |
|---|---|---|---|
| 08-11-TaskA | P0 | Q2/Q3 pending上游截断修复 | 待确认部署 |
| 08-11-TaskB | P0 | LONG offset continuation双层分桶 | 待确认部署 |
| 08-11-TaskC | P1 | REVERSAL_PIVOT_SCOUT停用/降级 | 待确认部署 |
| 08-11-S2 | P0(依赖TaskA) | q1_trend_launch_v2 | 不应早于TaskA部署 |
| 08-11-TaskD | P1 | 分桶A/B报告 | 待确认部署 |
| 08-07-审查意见 | P0 | rank_end回滚+显式白名单 | 本轮未提及，需追踪 |
| 08-07-审查意见 | P0 | long_threshold_offset回滚观察 | 本轮数据support继续观察 |
| pipeline_coherence审计 | P0(新增) | 全量排查其他mission是否有类似截断 | 本轮建议新增，待执行 |

这份清单本身也应该被固化为一个可执行的追踪文件
（而非仅存在于报告文本中），供每轮分析开始前直接核对。
```

---

*报告结束 | 管道一致性修复与分桶验证建议 v1.0 — 2026-08-11*
*最高优先行动：运行全量管道一致性审计（第3.2节），在修复Q2 pending这一个已知实例的同时，排查是否有其他mission存在同样的"上游未同步"问题——这类缺陷已经连续两轮出现，值得一次性系统性解决而非逐个修补。*

