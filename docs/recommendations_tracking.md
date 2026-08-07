# 建议实施追踪表(Recommendation Tracker)

> 本表是"上轮建议实施回顾"的唯一事实来源,由 `scripts/recommendation_tracker.py` 解析。
> 规则(2026-08-04 实施追踪协议):每份新诊断报告开篇必须包含本表;任何 P0 若未达到 DEPLOYED/VERIFIED,新报告必须说明阻塞原因,不得默默跳过。
> 状态枚举:PENDING / IN_PROGRESS / DEPLOYED / VERIFIED / ABANDONED。

| 建议ID | 报告日期 | 优先级 | 内容摘要 | 目标代码位置 | 实施状态 | 验证结果 |
|---|---|---|---|---|---|---|
| 2026-08-02-TaskA | 2026-08-02 | P0 | 移除 q1_trend_launch 确认标签依赖,改位置质量约束(Q1 直接强结构通道) | scripts/run_live_dry_run.py:888 `_q1_trend_launch_eligible` | VERIFIED | 代码修复(2e64232+2ac62df)+ VPS 在线验证通过(2026-08-05):verify_q1_trend_launch_fix.py --mode online 输出 q1_trend_launch 决策数=1、废弃标签残留=0,通道已产生转化 |
| 2026-08-02-TaskB | 2026-08-02 | P0 | Q2 pending 阈值重校准(85 结构性不可达→分布校准) | configs/entry_chain.dry_run_fib_pa_v1.json `scout_micro_q2_pending_min_score` | IN_PROGRESS | 阈值已从 85 改为 70(部分落地),但 Q2_PENDING_MOMENTUM mission 仍 0 触发;Phase 4 诊断中 |
| 2026-08-02-TaskC | 2026-08-02 | P1 | Q3 双轨道设计(Q3 动能延续 + Q3→Q1 确认) | scripts/run_live_dry_run.py L194/L421 `q3_to_q1` | IN_PROGRESS | 已接线(enabled=true)但确认标签 0 次,窗口 0 转化;与 TaskA 标签根因联动 |
| 2026-08-02-Q1_RR_GAP | 2026-08-02 | P0 | Q1_RR_GAP_SCOUT 收紧(负期望来源) | configs/entry_chain.dry_run_fib_pa_v1.json `scout_micro_q1_rr_gap_enabled` | VERIFIED | 已禁用(enabled=false);窗口无该通道开仓 |
| 2026-08-02-TaskD | 2026-08-02 | P2 | Q4 极值反转研究通道(严格护栏) | configs/entry_chain.dry_run_fib_pa_v1.json `scout_micro_reversal_pivot_enabled` | DEPLOYED | 已启用;窗口 4 笔开仓 PnL -0.2622(负期望,样本不足,需继续观察) |
| 2026-08-02-SymbolShadow | 2026-08-02 | P1 | Symbol policy shadow 晋级路径数据积累 | scripts/run_live_dry_run.py L1168 `_watch_only_symbol_promotion_eligible` | IN_PROGRESS | 已接线(`min_score=87`)但窗口 0 触发;Phase 4 诊断中 |
| 2026-08-02-TaskE | 2026-08-02 | P1 | 每日漏斗诊断报告(DailyFunnelDiagnosticReport) | scripts/(无实现) | PENDING | 未实现;summary.json 有部分计数但非 TaskE 规格的完整下钻报告 |
| 2026-08-02-AB加固 | 2026-08-02 | P1 | A/B 切换规则加固与自动报告 | configs/entry_chain.dry_run_fib_pa_v1.json `paper_ab_*` | DEPLOYED | 已启用(自动报告/切换门槛 payoff 1.3x);窗口 batch6 输出,PF<1 未触发切换(合理) |
| 2026-08-04-P0-1 | 2026-08-04 | P0 | q1_trend_launch 代码级修复:删 L888 标签 + 非极值追单检查(close 不在近8根极值最外20%) | scripts/run_live_dry_run.py L866-896 + src/signals/entry_chain_features.py extreme_position_ratio | VERIFIED | 17 单测通过 + 反事实 5/33 解锁 + VPS 在线验证通过(2026-08-05,决策数=1、废弃标签=0);通道已产生转化,标签依赖解耦 |
| 2026-08-04-P0-2 | 2026-08-04 | P0 | LONG 非对称验证:先 SCOUT-only HIGH_SCORE_LONG_OFFSET_PROBE 收集 20 笔,offset 不直接降 0 | scripts/run_live_dry_run.py L1134 `_high_score_long_offset_probe_eligible` | IN_PROGRESS | 诊断完成:0 触发=Q1硬编码+min_score85 与真实分布错配(≥85 LONG 在 Q3);已校准 quadrants=["Q1","Q3"]+min_score=82,RR 门槛 2.0 维持(护栏),6 单测通过;待部署后观察触发 |
| 2026-08-07-ATOM | 2026-08-07 | P0 | ATOM 牛市漏选:诊断三层根因(符号层 rank83 排除/分数层 92 门槛/闸门层 rr 2.0<4.0);Claude 评审后**三项改动全部回滚**,改走完整链验证 + 显式白名单机制 | configs/entry_chain.dry_run_fib_pa_v1.json(已回滚)+ src/signals/entry_chain_config.py(白名单) | VERIFIED | 回滚(rank_end 25/offset 10.0/targeted_long 无 ATOM);完整链验证:08-02 那笔 1h 方向 NONE → NO_TRADE 不成立;90 天 LONG 0 可开;ATOM **REJECT**(候选 1<20、无 PF);白名单机制代码就绪(9 单测);TON 零行=非缺陷(价格波动近零) |
| 2026-08-04-P0-3 | 2026-08-04 | P0 | 实施追踪协议(本表 + recommendation_tracker.py) | scripts/recommendation_tracker.py | DEPLOYED | 已实现并提交(commit 2e64232):list/check/show 可用,check 识别 5 条未解决 P0 并返回退出码 1,4 单测通过;作为新报告开篇强制门禁 |
| 2026-08-04-P0-4 | 2026-08-04 | P0 | 配置"重复键"核实与审计:long_threshold_offset 7.0/10.0 位于不同对象(probe_conditions vs 顶层),系设计意图非重复键,删除任一将改变行为 | scripts/audit_duplicate_json_keys.py | VERIFIED | 审计脚本确认全部 15 个配置无同一对象内重复键;对 08-02 报告的"重复键"诊断予以修正(不同对象同名键仅 info) |
| 2026-08-04-S1 | 2026-08-04 | P1 | SCOUT 任务多样化:mission 可达性诊断与门槛校准 | scripts/run_live_dry_run.py L1071 `scout_micro_mission` + scripts/diagnose_scout_mission_reachability.py | DEPLOYED | 诊断完成:probe 校准后恢复可达(BCH 87.3),watch_only min_score 87→85(分布依据),RR 护栏保留;标签依赖/FIB 入口不重叠记录为结构性低触发,不强行触发 |
| 2026-08-04-S2 | 2026-08-04 | P1 | Payoff 改善:early breakeven(+1R 移成本)+ trailing 1.2 试点(trend_capture_mirror only) | src/observability/paper_trading.py + scripts/run_live_dry_run.py build_paper_exit_ab_ledgers | IN_PROGRESS | 代码已落地(4 单测通过,试点受 mirror_ab_payoff_pilot_enabled 控制,legacy 纯净对照);待部署后 30 笔 A/B 评估(evaluate_offense_fixes.py) |

---

## 核对日期与依据

- 本表状态基于 2026-08-04 对代码与配置的静态核对 + 08-02 21:45~08-04 19:00 窗口日志证据,由 `scripts/recommendation_tracker.py` 可复现解析。
- 更新方式:直接编辑本表(保持 7 列);`check` 命令将 P0 且非 DEPLOYED/VERIFIED/ABANDONED 视为阻塞。
