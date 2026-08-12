# AI300 08-11 评审落实:上轮建议实施回顾 + 管道一致性审计 + Task A

**日期:** 2026-08-11
**对应评审:** 08-07 ATOM 漏选审查(回滚建议)、08-11 管道一致性修复与分桶验证建议(audit_pipeline_coherence + Task A-D)

---

## 1. 上轮建议实施回顾(每轮报告开篇强制核对)

> 依据 08-04 报告第 8.3 节设计的"上轮建议实施回顾"表格;数据来源 `docs/recommendations_tracking.md` + 配置/代码核实。

| 建议来源 | 优先级 | 内容摘要 | 状态 | 核实证据 |
|---|---|---|---|---|
| 08-07 审查 | P0 | **rank_end 回滚 25**(原建议 90 过度) | ✅ 已落实 | 配置 `dry_run_rank_end: 25`;commit 59c123d |
| 08-07 审查 | P0 | **long_threshold_offset 回滚 10.0**(探针 3 笔 PF=0 未等数据) | ✅ 已落实 | 配置顶层 `long_threshold_offset: 10.0`(probe 层 7.0 保留);commit 59c123d |
| 08-07 审查 | P0 | **ATOM 显式白名单替代 rank 扩容** | ✅ 已落实(REJECT) | 完整链验证 08-02 那笔 1h 方向 NONE → NO_TRADE 不成立;90 天 LONG 0 可开;ATOM REJECT 未添加 |
| 08-07 审查 | P0 | **explicit_watchlist 机制** | ✅ 代码就绪 | `entry_chain_config.py` + `evaluate_watchlist_candidate.py` + 9 单测;配置未启用(无通过候选) |
| 08-02-TaskA / 08-04-P0-1 | P0 | q1_trend_launch 标签依赖移除 + 非极值追单 | ✅ VERIFIED | VPS 在线验证 08-05:决策数=1、废弃标签=0 |
| 08-02-TaskB | P0 | Q2 pending 阈值重校准(85→70) | ⚠️ 部分落地,本轮 Task A 修复 | 阈值已 70,但 Q2_PENDING_MOMENTUM 仍 **0 触发**(上游 near_miss_min_score=82 截断,08-11 报告"管道未对齐"核实成立) |
| 08-02-TaskC | P1 | Q3→Q1 确认 | ⚠️ 0 转化 | 与 Q2 同根因(上游截断),Task A 一并修复 |
| 08-04-P0-2 | P0 | LONG 非对称验证(probe 20 笔) | IN_PROGRESS | 08-11 报告累计 7 样本 +0.101R(弱正),继续观察 |
| 08-02-TaskD | P2 | REVERSAL_PIVOT_SCOUT | ⚠️ 本轮停用 | 08-02~08-11 实际累计:开仓 21、margin_pnl **-1.29**(08-11 报告记 13 笔 -0.91,口径差异,实际更差) |

**结论:08-07 审查 4 项建议全部落实(其中 ATOM 按验证 REJECT);08-04 追踪项中 TaskB/TaskC 为"建议写了但上游未同步"的典型案例,本轮 Task A 系统性修复。**

### 1.1 08-11 报告累计问题清单核对(第 11 节 8 条 + 10.2/10.3 + 5.1)

| 建议来源 | 优先级 | 内容摘要 | 状态 | 核实证据/阻塞原因 |
|---|---|---|---|---|
| 08-11-TaskA | P0 | Q2/Q3 pending 上游截断修复 | ✅ DEPLOYED | per-quadrant 采样(Q2=70)已实施(74cba24);反事实 108 候选(对照预测 36);待部署在线验证转 VERIFIED |
| 08-11-TaskB | P0 | LONG offset continuation 双层分桶(shadow/SCOUT,RR≥2 进真实 SCOUT) | ❌ 未实施 | 配置无 continuation 字段;窗口 LONG offset 事件 0(probe 通道仍未触发);P0-2 仅完成 probe 校准(quadrants/min_score/RR 2.0) |
| 08-11-TaskC | P1 | REVERSAL_PIVOT_SCOUT 停用/降级 | ✅ 已实施 | `scout_micro_reversal_pivot_enabled=false`(74cba24);实际累计 21 笔 margin_pnl -1.29;DEPRECATED 记录 |
| 08-11-S2 | P0(依赖TaskA) | q1_trend_launch_v2(重新要求"活"确认标签) | ❌ 未实施 | 强依赖 TaskA 部署后活标签(Q2/Q3 pending 确认开始生成);按 08-11 报告 4.2 节时序约束,不得早于 TaskA 部署验证 |
| 08-11-TaskD | P1 | 分桶 A/B 报告(按 source_reason/quadrant/side/symbol 独立 PF/MFE/MAE) | ❌ 未实施 | `evaluate_offense_buckets.py` 不存在;依赖各分桶(TaskB/S2 等)实际运行数据 |
| 08-07 审查 | P0 | rank_end 回滚 + 显式白名单 | ✅ VERIFIED | `dry_run_rank_end: 25`;explicit_watchlist 机制就绪;ATOM 完整链验证 REJECT 未添加 |
| 08-07 审查 | P0 | long_threshold_offset 回滚观察 | ✅ 已回滚 | 顶层 `long_threshold_offset: 10.0`;08-11 数据(7 样本 +0.101R 弱正)支持继续 shadow 观察,按 8.1 决策树等 20 笔 |
| pipeline_coherence 审计 | P0(新增) | 全量排查其他 mission 上游截断 | ✅ DEPLOYED | `audit_pipeline_coherence.py` 8 mission 排查:唯一 BLOCKING=Q2,已随 TaskA 修复;REVERSAL WARNING(冗余),其余 6 OK |

**08-11 报告附加要求核对:**
- **10.2 节(LONG offset 跨报告累计口径)**:08-04 2 笔 → 08-07 3 笔 → 08-11 7 笔,累计 **9 笔**(报告口径);`cumulative_sample_tracker`(加权 terminal 均值、去重累计)**未实现**——各报告数字关系仍有歧义,待 TaskD 或 tracker 补建;
- **10.3 节(rank_end/ATOM 现状)**:`rank_end=25` ✓;ATOM 未产生任何 SCOUT 候选(REJECT,90 天 LONG 0 可开)✓——08-07 审查意见确认被采纳;
- **5.1 节(部署后验证脚本)**:`verify_task_a_pending_pipeline_fix` / `verify_task_b_long_offset_routing_fix` / `verify_task_c_reversal_pivot_disabled` **均未实现**——TaskA 部署后核对 Q2 pending 创建的手段缺失,待补(与 TaskA 部署配套)。

## 2. 基线数据(本轮核对)

| 指标 | 值 | 来源 |
|---|---|---|
| Q2_PENDING_MOMENTUM_CONFIRMED / Q3_TO_Q1_CONFIRMED 事件 | **0 条**(08-02~08-11 decisions+near_misses) | 日志 grep |
| REVERSAL_PIVOT_SCOUT 开仓 | **21 笔**(08-02~08-11),margin_pnl 累计 **-1.2948** | `summarize_channel_stats.py` |
| near_miss_min_score 默认值 | **82.0**(run_live_dry_run.py L385) | 代码 |
| Q2 pending 自身门槛 | 70.0(已校准) | 配置 |
| Q2 分数分布(08-11 报告) | P90=69.69、max=78.87 | 08-11 报告 |
| LONG offset 样本(08-11 报告) | 7 样本 terminal +0.101R(累计 2+3+7=9) | 08-11 报告 |

**基线结论:** Q2/Q3 pending 因上游 82 截断永久 0 触发(第二次"管道未对齐");REVERSAL 持续负期望(21 笔 -1.29)支持停用。

## 3. 管道一致性全量审计(audit_pipeline_coherence)

实现 08-11 报告 3.2 规格 + 象限增强(`scripts/audit_pipeline_coherence.py`,6 单测):

| mission | 自身门槛 | 上游(82) | 判定 | 说明 |
|---|---:|---:|---|---|
| **Q2_PENDING_MOMENTUM** | 70 | 82 | **BLOCKING** | 象限特定(Q2 资金轴不过,分数天花板 <82)→ 候选被上游永久截断,第二次"管道未对齐" |
| REVERSAL_PIVOT_SCOUT | 70 | 82 | WARNING | 非象限特定,候选来自高分 near_miss(≥82),门槛冗余无实际截断 |
| Q3_TO_Q1_CONFIRMATION | 85 | 82 | OK | 门槛 ≥ 上游,不受采样截断(其 0 转化属确认标签问题,同 q1_trend_launch 旧 bug 族) |
| Q1_RR_GAP_SCOUT / HIGH_SCORE_LONG_OFFSET_PROBE / FIB_CONTINUATION_SCOUT | 82 | 82 | OK | 门槛 = 上游 |
| WATCH_ONLY_SYMBOL_PROMOTION_TEST / SCOUT_ONLY_HIGH_SCORE | 85 | 82 | OK | 门槛 > 上游 |

**结论:唯一上游截断实例 = Q2 pending**(与 08-11 报告核实一致);一次性排查避免了逐个修补。

## 4. Task A 修复与反事实验证

- **修复**:`build_near_miss_payload` 增加 `min_score_by_quadrant` 参数;主循环对 Q2 象限用 pending 门槛(70)采样,不再被全局 82 截断(Q1 等其余象限保持 82,不全局放松);
- **反事实验证**(08-11 方法论,部署前先证明):历史 decisions(08-02~08-11)统计修复后可建 Q2 pending 候选 **108 个**(score≥70+PA≥18+非 PROBE/DIRECT),对照 08-11 报告预测 36(窗口口径差异,远超修复前 0)→ 修复有效;
- 单测:Q2 72.3 分 + 覆盖 → 生成;无覆盖 → 截断;Q1 不受覆盖泄漏;84 个 live_dry_run 测试全过。

## 5. REVERSAL_PIVOT_SCOUT 停用

- `scout_micro_reversal_pivot_enabled: true → false`;实际累计(08-02~08-11)开仓 **21 笔、margin_pnl -1.2948**(08-11 报告记 13 笔 -0.91,口径更保守);
- 状态 DEPRECATED:持续负期望 + 路由抢占;反转假设本身未证伪,重启需先过显著性检验(08-02 报告 7.1 节二项检验)。

