# 08-18 评审落实记录 — mirror shadow-only + 小样本纪律固化

**日期:** 2026-08-18
**对应评审:** 管道修复验证与小样本纪律建议(08-18)

---

## 1. 落实摘要

| 评审建议 | 落实 | 状态 |
|---|---|---|
| **P0-1 mirror A/B 降级 shadow-only**(三轮 98 笔负期望) | `mirror_ab_mode: "shadow_only"`(配置);账本继续记录假设成交(诊断),不计入实验熔断统计/敞口(`experiment_ledgers` L223 排除);reactivation 需连续 3 batch 转正 | ✅ DEPLOYED |
| **P0-2 q1_trend_launch 特征提炼方法论风险**(N=2 不能提炼) | 累计 7 笔 <10:仅记录、不提炼特征、不资源倾斜、notional 62.5 不变 | ✅ 纪律应用 |
| **P1-1 Q3→Q1 唯一正通道同等谨慎**(3 笔不优先) | 与 Q2 pending 平等对待(四通道平等表),<10 仅记录 | ✅ 纪律应用 |
| **5.2 小样本决策框架固化** | `SAMPLE_SIZE_DECISION_RULES` 固化为 `channel_cumulative_tracker.py` 常量:<10 不"证明有效/提炼特征"、<20 不调参数/不资源倾斜、负信号 2 窗口一致可停用 | ✅ DEPLOYED |
| **6.2 ChannelCumulativeTracker** | `scripts/channel_cumulative_tracker.py`:按通道累计样本/PnL/距 20 笔,输出四通道平等表 | ✅ DEPLOYED |

## 2. 四通道累计表(08-02~08-18,tracker 输出)

| 通道 | 累计样本 | 累计PnL | 距20笔 | 判定 |
|---|---:|---:|---:|---|
| q1_trend_launch | 7 | -1.453 | 13 | 仅记录(不提炼/不优先) |
| scout_q2_pending_momentum | 3 | -0.139 | 17 | 仅记录(不提炼/不优先) |
| scout_q3_to_q1_confirmation | 3 | +0.389 | 17 | 仅记录(不提炼/不优先) |
| scout_high_score_long_offset_probe | 9 | -2.116 | 11 | 仅记录(不提炼/不优先) |
| mirror_ab_sample(shadow) | 290 | -32.116 | — | 达20笔,负期望(已 shadow) |

**口径说明:** q1_trend_launch 累计 7 笔 = 主账本 7(08-04/07/08/09×2/14/16),含 08-12 22:00 窗口的 2 笔;mirror 镜像记录已从主账本通道统计中排除(CHANNEL_LEDGER_SCOPE)。

## 3. 纪律固化(SAMPLE_SIZE_DECISION_RULES)

```python
SAMPLE_SIZE_DECISION_RULES = {
    "min_samples_for_any_narrative": 10,     # <10:不"证明有效/提炼特征",仅陈述结果
    "min_samples_for_parameter_adjustment": 20,  # <20:不调门槛/权重/仓位
    "min_samples_for_priority_boost": 20,    # <20:不给予路由优先级/资源倾斜
    "negative_signal_special_case_windows": 2,   # 负信号 2 窗口一致:可停用/降级(mirror 案例)
}
```

**应用:** mirror(三轮一致)→ 停用/降级 ✓;q1_trend_launch(7)/Q2(3)/Q3→Q1(3)/probe(9)全部 <10 → 仅记录;达 20 笔前不做任何参数调整。

## 4. 护栏维持

- 不全局放宽 RR/极值追单门槛;不解除黑名单;
- mirror shadow 期间 PnL 为假设成交(不含真实滑点/冲击/保证金占用),reactivation 从最小仓位开始;
- 四通道每轮报告用 tracker 更新累计表(不突出"唯一正"),达 20 笔后按 08-11 TaskD 分桶评估。
