# AI300 08-12 22:00 后进攻效果归因 — 开仓改善达成、盈利仍未实现

**提交对象:** Claude 评审
**分析窗口:** 2026-08-12 22:00 ~ 2026-08-18(北京时间)
**运行模式:** VPS dry-run / paper ledger / SCOUT micro / paper A-B mirror
**数据来源:** `logs/2026-08/{2026-08-12..2026-08-18}/` 下 `decisions.jsonl`、`near_misses.jsonl`、`scout_decisions.jsonl`、`paper_trades.jsonl`、`scout_micro/paper_trades.jsonl`、`paper_ab/{legacy,trend_capture}/paper_trades.jsonl`、`health.json`、`summary.json`
**上一轮:** 08-13 q1_trend_launch 审计(根因=data_health 粘滞降级,已修复部署)

---

## 0. 结论摘要

1. **"改善开仓"部分达成**:08-13 修复(data_health 周期级重置)已部署生效——08-13/14 `data_health="OK"`(粘滞 DEGRADED 消除);q1_trend_launch 主账本从 08-12/13 的 **0 开仓**变为 **2 笔**(08-14 SOL SHORT、08-16 BNB SHORT);Q2_PENDING_MOMENTUM scout 从 **0 触发**变为 **3 笔开仓**(Task A per-quadrant 采样生效)。
2. **"实现盈利"未达成**:窗口主账本 **-0.90**、实验账本(experiment four_quadrant_navigation_v1)**-11.37**(7 天,最差日 -2.80)。
3. **最大亏损源 = mirror A/B(98 笔 -9.99,占实验亏损 88%)**——"放行被拦候选"实验已三轮(08-04/08-11/本轮)证实候选池负期望,本报告建议停用或降级。
4. **q1_trend_launch 出现盈利样本**:SOL SHORT **+6.25**(notional 62.5,+10%),证明通道可盈利;但 BNB SHORT -0.155 与主账本其他仓亏损抵消,整体仍负。
5. **唯一正的通道 = Q3_TO_Q1_CONFIRMATION scout(+0.39,3 笔)**——值得继续验证。
6. 改善方向(供评审):①mirror 停用/降级;②q1_trend_launch 盈利样本特征提炼与规模化;③Q3→Q1 通道验证路径;④probe/Q2 pending 按 08-11 决策树观察。**不全局放宽阈值**(延续评审纪律)。

## 1. 上轮建议实施回顾(08-13 审计修复)

| 检查项 | 结果 |
|---|---|
| `_q1_trend_launch_eligible` 标签依赖 | ✅ 已修复(2e64232;08-13 复核确认) |
| Q2 上游截断(Task A per-quadrant) | ✅ 已修复(74cba24)+ **部署生效**(Q2_PENDING mission 从 0 触发变为 3 笔开仓) |
| REVERSAL_PIVOT_SCOUT 停用 | ✅ enabled=false + 部署生效(窗口 0 笔 reversal 开仓) |
| **data_health 粘滞降级(08-13 新根因)** | ✅ 已修复(周期级重置,0db7a7e)+ **部署生效**(08-13/14 data_health=OK) |
| 48H q1_trend_launch 转化 | 08-12/13=0 → **08-14=1、08-16=1**(修复后转化出现) |

**结论:08-13 审计修复全部落地并部署;开仓通道恢复运转。**

## 2. 窗口数据(08-12 22:00 ~ 08-18)

| 指标 | 值 |
|---|---:|
| decisions | 7,605(Q1=848/Q2=920/Q3=1638/Q4=4199) |
| actions | NO_TRADE 6,745 / WATCH 857 / **PROBE 3** |
| score ≥80 / ≥85 | 150 / 43 |
| near_misses | 179 |
| 主账本 margin_pnl(paper_trades.jsonl) | **-0.899** |
| 实验账本 margin_pnl(含 scout+mirror) | **-11.37**(7 天) |
| 熔断状态 | 未触发(累计 -29.09 ≫ war_fund -150) |

## 3. 修复效果:开仓通道恢复

| 通道 | 08-12/13(修复前) | 08-14~18(修复后) |
|---|---|---|
| q1_trend_launch 主账本 | 0 开仓 | **2 笔**(08-14 SOL、08-16 BNB) |
| Q2_PENDING_MOMENTUM scout | 0 开仓(上游截断) | **3 笔** |
| Q3_TO_Q1_CONFIRMATION scout | — | 3 笔 |
| HIGH_SCORE_LONG_OFFSET_PROBE | — | 5 笔 |
| REVERSAL_PIVOT_SCOUT | — | 0 笔(停用生效) |

**"改善开仓"目标达成——通道从死锁恢复为运转。**

## 4. 按通道盈亏归因(窗口,08-12~08-18)

| 通道 | 开仓 | margin_pnl | 判定 |
|---|---:|---:|---|
| **mirror A/B** | 98 | **-9.99** | 最大亏损源(占实验亏损 88%),候选池负期望 |
| q1_trend_launch(主账本) | 2 | -0.56* | 有 SOL +6.25 盈利样本,整体负(BNB -0.155 抵消) |
| HIGH_SCORE_LONG_OFFSET_PROBE | 5 | -1.07 | 负,按 08-11 决策树观察 |
| Q2_PENDING_MOMENTUM | 3 | -0.14 | 新通道小亏,继续验证 |
| **Q3_TO_Q1_CONFIRMATION** | 3 | **+0.39** | **唯一正通道** |
| 主账本合计 | 3 | -0.90 | 含 CCUSDT 等其他仓 |

\* summarize_channel_stats 扫描 scout/mirror 路径,主账本 q1_trend_launch 以 paper_trades.jsonl 直接统计(2 笔)。

### 4.1 q1_trend_launch 盈利样本(SOL SHORT +6.25)

- 入场 08-14,notional 62.5(小仓),SHORT;
- 平仓 margin_pnl **+6.25**(+10% 仓本)——**通道可盈利的实证**;
- 对比 BNB SHORT -0.155:同通道不同结果,样本量 2 不足以归因,需提炼入场/出场特征(见改善方向 ②)。

## 5. 为什么仍不盈利(根因归因)

1. **mirror 持续失血(-9.99/7 天)**:"放行被拦候选"的候选池本身负期望——与 08-04(legacy PF 0.345/trend 0.370)、08-11(legacy 0.2266/trend 0.0397)结论一致;mirror 是当前最大的、证据最充分的亏损来源;
2. **主账本进攻通道样本仍不足**:q1_trend_launch 仅 2 笔(有 1 笔盈利),Q2/Q3 pending 各 3 笔——开仓改善是"从 0 到有",但样本量远未到可评估盈亏的量级;
3. **盈利样本被亏损抵消**:主账本 -0.90 中 SOL +6.25 被 BNB -0.155 与 CCUSDT 抵消;实验账本被 mirror 拖垮;
4. **数据健康已恢复**(08-13/14 OK),不再是 0 转化原因——问题已从"通道死锁"转为"通道样本质量与盈利结构"。

## 6. 改善方向(供 Claude 评审)

### P0-1 mirror 停用/降级(最大亏损源,证据三轮充分)
- 现状:`paper_ab_*` 自动报告/切换门槛 payoff 1.3x 已启用,但 mirror 本身 98 笔 -9.99 持续负期望;
- 建议:mirror 降级为 shadow-only(记录不实开)或按批次熔断(连续 batch PF<0.5 停 2 batch);主账本/实验账本不再被其拖累;
- 依据:08-04/08-11/本轮三轮一致;候选池负期望非出场问题(MFE 0.52R,08-11 报告)。

### P0-2 q1_trend_launch 盈利化(样本特征提炼与规模化)
- SOL SHORT +6.25 证明通道可盈利;提炼该样本的入场特征(象限/组件/extreme/出场)与 BNB -0.155 对比,形成"可盈利子集"假设;
- 当前 notional 62.5(小仓)——盈利样本验证后,评估暴露度提升路径;
- 不降低 eligible 门槛(保持 extreme/防追单保护)。

### P1-1 Q3→Q1 pending 通道验证(唯一正通道)
- Q3_TO_Q1_CONFIRMATION scout 3 笔 +0.39——继续积累样本至 20 笔,按 08-11 TaskD 分桶报告评估;
- 与 Q2 pending(3 笔 -0.14)对比,验证"Q3 动能确认→Q1"路径是否优于"Q2 pending"路径。

### P1-2 probe/Q2 pending 按决策树观察
- HIGH_SCORE_LONG_OFFSET_PROBE 5 笔 -1.07:按 08-11 8.1 决策树(累计 20 笔后 PF>1.0 再议),不提前动作;
- Q2_PENDING_MOMENTUM 3 笔 -0.14:新通道,继续积累。

### 护栏(维持)
- 不全局放宽 RR 几何/极值追单门槛;不解除黑名单;mirror 改动先经 shadow 验证;新通道先进独立实验账本。

## 7. 数据口径与局限
- 时间:北京=UTC+8;日志按 UTC 日归档,窗口=08-12 22:00 北京(08-12 14:00 UTC)~ 08-18 全量;
- summarize_channel_stats 默认扫 scout/mirror 路径,主账本(q1_trend_launch/CCUSDT)以 paper_trades.jsonl 直接统计(口径差异已注明);
- q1_trend_launch 仅 2 笔、Q2/Q3 pending 各 3 笔——样本量不足以作统计结论,用于实验方向设计;
- mirror 98 笔统计显著(连续三轮),是唯一可作"停止/降级"决策的通道;
- 本报告只分析不下发(供评审);优化实施按评审结论另立任务。
