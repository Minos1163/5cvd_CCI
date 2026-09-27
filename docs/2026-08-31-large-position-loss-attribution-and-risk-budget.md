# 08-31 评审落实:三笔大额亏损归因 + 单笔风险预算反事实重算

**日期:** 2026-08-31
**对应评审:** 大仓亏损根因确认与头脑风暴补充建议(08-31,DEEPSEEK)
**窗口:** 2026-08-24 22:00 ~ 08-31(08-24 重启后)

---

## 1. 三笔大额亏损归因审查(评审 6.3 节"立即行动"结论)

| 日期 | 币 | side | quadrant | leverage | margin_used | MFE | exit_reason | margin_pnl | notional_pnl |
|---|---|---|---|---|---:|---:|---|---:|---:|
| 08-24 | BCHUSDT | **SHORT** | **Q1** | **4** | 486.28 | 0.69R | INITIAL_STOP_HIT | -94.08 | -23.52 |
| 08-24 | DOGEUSDT | **SHORT** | **Q1** | **4** | 486.18 | 0.75R | COST_BREAKEVEN_TIMEOUT | -60.81 | -15.20 |
| 08-28 | SOLUSDT | **SHORT** | **Q1** | **4** | 484.54 | 0.36R | INITIAL_STOP_HIT | -90.78 | -22.70 |

**三笔 100% 同一模式**:Q1 + SHORT + leverage 4 + margin≈486 + MFE<0.8R + 止损/超时。

**评审 6.3 的猜测成立**:三笔集中在同一象限(Q1)同一方向(SHORT)——不是泛泛的"主路径大仓问题",而是**具体可复现模式**。

## 2. 盈亏口径修正(重要)

`src/observability/paper_trading.py`:
- L341 `equity = initial_equity + realized_pnl`(**主口径 = notional**)
- L342 `margin_equity = initial_equity + realized_margin_pnl`(保证金报告口径)
- L201/324/365/416 `pnl_accounting_mode: "notional_primary_margin_reporting"`

| 口径 | 三笔合计 | 窗口合计 |
|---|---:|---:|
| `margin_pnl`(保证金报告口径,leverage 放大) | -245.67 | -226.64 |
| **`notional_pnl`(账户主口径)** | **-61.42** | ≈ -56.7 |

**修正:账户真实损失 ≈ -61.4(三笔),占 equity 10,000 的 0.61%**;`margin_pnl -226.64` 是保证金报告口径(4x 放大显示)。后续报告应以 notional 口径表述账户影响,避免夸大。

## 3. 三重缺口叠加链路(根因)

```
① SHORT 无 threshold offset(08-24 审计:long 10.0 / short 0.0)
     → Q1 SHORT 高分不需额外门槛即达 DIRECT(可执行率 19.64% vs LONG 3.66%)
② _select_leverage 4x 无质量门(src/signals/entry_chain.py L614-635)
     · 仅 5x 有 fib≥13/pa≥9/cci≥9/rr≥4 门
     · DIRECT 默认 return 4(除 atr>3%/sharpe<0 外无约束)
     → Q1 SHORT DIRECT 直接拿到 4x + margin≈486(接近满敞口)
③ 无单笔风险预算(仅总敞口 1.6/同向 1.1 上限)
     → 单笔 margin 486(接近上限)无"单笔最大损失"约束
④ 结果:上涨段逆势做空(MFE 0.36-0.75R 从未走对)+ 4x 放大
```

## 4. 单笔风险预算反事实重算(评审 4.3 节)

用三笔真实数据重算 `risk_capped_notional = (equity × max_risk_pct) / stop_distance_pct`:

| 币 | notional(≈margin×4) | stop_distance_pct(≈\|notional_pnl\|/notional) | risk_capped(equity 10000, max_risk 1.2%) | 是否裁剪 |
|---|---:|---:|---:|---|
| BCH | 1945 | 1.21% | 9,917 | **否** |
| DOGE | 1945 | 0.78% | 15,385 | **否** |
| SOL | 1938 | 1.17% | 10,256 | **否** |

**评审 4.3 的预判成立**:风险预算(1.2%)**不会裁剪这三笔**——因为止损距离小(0.78-1.21%),1945 notional 的实际风险仅约 15-24(账户 0.15-0.24%),远低于 1.2% 预算。

**结论:**
- 三笔亏损的**根因不是"仓位过大"**,而是**方向错误(Q1 SHORT 逆势)+ 入场位置差(MFE<0.8R)**,leverage 4x 主要放大了"保证金报告口径"的显示(而非账户 notional 损失);
- 单笔风险预算**作为基础风控护栏仍应立即加入**(评审 7.1:结构性缺口,不受样本门槛),但**不能被表述为"加了它就能避免这三笔"**——需与方向治理(SHORT 非对称)+ 入场质量(行为确认)配合;
- 评审 5.2 的杠杆质量门控(4x 加门)是**更直接命中**这三笔的修复。

## 5. 后续(见实施记录)

- 单笔风险预算硬约束(Phase 2):护栏层,收紧而非放宽;
- 4x 杠杆质量门控(Phase 3):shadow 先行(数值需回测校准);
- 归因字段补充(Phase 4):`entry_channel` 非 null + 杠杆档位理由,消除可观测性缺口。
