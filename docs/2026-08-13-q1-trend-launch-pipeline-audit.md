# AI300 q1_trend_launch 确认链路审计与修复 — 响应 08-13 审查报告

**日期:** 2026-08-13
**对应审查:** BNB 漏选分析审查与管道问题升级(08-13,最高优先行动:直接代码审查而非日志反推)
**上一轮状态:** 08-11 评审落实(上轮建议回顾 / audit / Task A / REVERSAL 停用)已推送 08-11-0per

---

## 1. 代码现状核对表(审查报告 §6.2/§7 强制开篇字段,直接代码/配置审查)

| 检查项 | 直接代码/配置审查结果 | 状态 |
|---|---|---|
| `_q1_trend_launch_eligible()` 标签依赖 | `scripts/run_live_dry_run.py` L866-896 无 `Q2_PENDING_MOMENTUM_CONFIRMED`/`Q3_TO_Q1_CONFIRMED` 检查;CONFIRMED 标签仅存于 `confirm_q2_to_q1_pending`/`confirm_q3_to_q1_pending`(L1351/1359/1434/1465)——**已修复**(2e64232+2ac62df) | ✅ 已修复 |
| Q2/Q3 pending 上游截断 | `build_near_miss_payload` 有 `min_score_by_quadrant` 参数(L783/819),主循环对 Q2 传 pending 门槛 70(L196)——**Task A 已实现**(74cba24) | ✅ 已修复 |
| REVERSAL_PIVOT_SCOUT enabled 状态 | 配置 `scout_micro_reversal_pivot_enabled: false`(L144)——**已停用**(74cba24) | ✅ 已停用 |
| 最新 q1_trend_launch 转化数(48H) | `logs/2026-08/2026-08-12/decisions.jsonl` 与 `2026-08-13`:DRY_RUN_Q1_TREND_LAUNCH 计数 **0**(与审查报告一致) | ❌ 仍 0 |

## 2. 部署指纹(判定 Task A/C 是否已部署到 VPS,而非仅代码存在)

| 指纹 | 08-12/13 观测 | 结论 |
|---|---|---|
| REVERSAL_PIVOT_SCOUT 开仓 | scout_micro paper_trades 中 reversal_pivot 开仓 **0 笔**(仅 high_score_long_offset_probe 2 + q3_to_q1_confirmation 2) | ✅ Task C 已部署生效 |
| Q2_PENDING_MOMENTUM mission | scout_decisions 出现 **1 次**(修复前全窗口 0 触发) | ✅ Task A 已部署生效 |

**结论:代码修复与部署均已完成;q1_trend_launch 0 转化问题不在部署层,而在"确认→eligible"链路(Phase 2 审计)。**

## 3. 48H 关键样本(审计铺垫)

08-12/13 `Q2_PENDING_MOMENTUM` scout 记录(1 条):
- `mission: Q2_PENDING_MOMENTUM`、`quadrant: Q1`(pending 已确认转 Q1,确认链路通)
- `accepted: false`、`primary_reason: DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0`(被 RR 几何闸门拦截)

**初步判断:确认标签已能生成;q1_trend_launch 0 转化的下一候选原因 = 确认样本未通过 `_q1_trend_launch_eligible`(extreme ratio 范围 / long_overextension / RR≥0.5)或 RR 几何闸门,待 Phase 2 逐条对照。**

## 4. 断裂点结论(Phase 2 审计)

### 4.1 审计结果
- 48H(08-12~08-13)56 条 near_miss 逐条跑真实 `_q1_trend_launch_eligible`(audit_q1_trend_launch_hits.py):
  - **1 条 ALL_PASS**:LINKUSDT SHORT 88.7(extreme 0.411,PA/Fib/CVD/RR/防追单全过);
  - first_fail 分布:q1=37、extreme_range=10、not_blacklisted=4(ZEC/XRP)、rr_min=3、no_overext=1;
- **但 decisions.jsonl 48H 无 DRY_RUN_Q1_TREND_LAUNCH(0 转化)**——eligible 纯函数通过 ≠ 主循环转化,矛盾指向主循环实际环境。

### 4.2 根因(断裂点 = 数据健康粘滞闸门)
1. 08-12/13 `health.json` `data_health: "DEGRADED"`(两天);
2. 配置 `dry_run_q1_trend_launch_allow_degraded_data: false` → `_q1_trend_launch_eligible` 第 3 步(`data_health != "OK" 且不允许降级 → return False`)**永久返回 False**;
3. **粘滞性**:主循环 `data_health` 仅 L104 初始化一次,per-symbol 只置不恢复(L165-166 `if context_health != "OK": data_health = context_health`)——**一次 Binance 拉取抖动 → 永久 DEGRADED → 锁死 q1_trend_launch(直到进程重启)**;
4. 排除:非标签 bug(确认标签已生成,TRX SHORT 88.7 被路由)、非部署缺失(Task A/C 部署指纹确认)、非熔断(实验账本累计 -29.09 ≫ -150);
5. 佐证:decisions 的 warmup 显示 public-binance 当前拉取正常(ready=true)——**数据实际已恢复,粘滞 DEGRADED 是主因**。

## 5. 修复(Phase 3,周期级重置)

- 代码(`scripts/run_live_dry_run.py`):`data_health = "OK"` 移入 while 循环内每 cycle 重置——一次降级只影响当周期,下周期恢复评估;**`allow_degraded_data=false` 保持不变**(降级周期内仍保护,不全局放宽);
- 单测:`test_q1_trend_launch_fix.py` 新增 2 个(DEGRADED+allow=false → False;OK → True;allow=true → True);
- 反事实验证:48H 的 LINK SHORT 88.7 在数据健康=OK 周期可走完整链路(build_q1_green_channel_decision → PROBE,entry_channel=q1_trend_launch)——修复后数据正常周期候选 >0(对照修复前 48H=0);
- 全量测试:615 passed(1 个既有无关失败)。

## 6. 部署后验证协议(48-72h 观察窗)

- 部署 08-13 修复(周期级重置)后,运行:
  `python scripts/verify_q1_trend_launch_fix.py --mode online --log-root logs --hours 48`
- 目标:q1_trend_launch 真实转化 **≥1 笔**且可评估(decision 级;对照此前 48H=0);
- 若仍 0:核查是否持续 DEGRADED(health.json)或 eligible 条件(extreme/组件)在窗口内无样本——区分"数据问题"与"样本不足";
- 观察期后:`evaluate_offense_fixes.py` 评估转化质量(win_rate/PF),达 08-11 评审标准后再谈 S2/source_requirement 叠加。
