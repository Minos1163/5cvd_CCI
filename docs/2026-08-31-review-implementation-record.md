# 08-31 评审落实记录(大仓亏损归因 / 风险预算 / 4x 门控 / 归因字段)

**日期:** 2026-08-31
**对应评审:** ①08-24 报告评审(SHORT 偏向 + regime offset)②08-31 报告评审(大仓亏损根因确认与头脑风暴补充)
**分支:** `08-24--08per`

---

## 1. 上轮建议实施回顾(本表为唯一事实来源的镜像:见 `docs/recommendations_tracking.md`)

| 建议ID | 来源 | 优先级 | 内容 | 状态 | 结果 |
|---|---|---|---|---|---|
| 2026-08-24-SHORTBIAS | 08-24 评审 3.3 | P0 | SHORT 执行非对称审计 + regime offset shadow | DEPLOYED | 审计确认 bullish 窗口 SHORT 可执行率 16.67% vs LONG 4.12%;shadow +10 offset 拦全部 12 笔高分 SHORT;live 门槛不变 |
| 2026-08-24-BULLREGIME | 08-24 评审 | P1 | BULL_REGIME_BREAKOUT_V1 设计 + shadow | DEPLOYED | 设计 + tracker 纳管(样本 0) |
| **2026-08-31-LOSSATTR** | 08-31 评审 6.3 | P0 | 三笔大额亏损归因审查 | **VERIFIED** | **三笔 100% 同一模式:Q1 + SHORT + leverage 4 + margin≈486 + MFE<0.8R** |
| **2026-08-31-RISKBUDGET** | 08-31 评审 4.2 | P0 | 单笔风险预算硬约束 | **VERIFIED(复核)** | **机制已存在**(`direct_risk_pct=0.006`),比评审建议 1.2% 更保守;三笔不会被裁剪 |
| **2026-08-31-4XGATE** | 08-31 评审 5.2 | P0 | 4x 杠杆质量门控 | **DEPLOYED** | 设计 + shadow 脚本 + 5 单测;live 未改(数值待回测) |
| **2026-08-31-ATTRIB** | 08-31 评审 6.2 | P1 | 归因字段补全 | **DEPLOYED** | `_resolve_entry_channel`:entry_channel 不再 null;4 单测 |

## 2. 本轮交付(6 项)

1. **三笔大额亏损归因**(`docs/2026-08-31-large-position-loss-attribution-and-risk-budget.md`):
   - BCH/DOGE 08-24 + SOL 08-28 → **Q1 + SHORT + leverage 4 + margin≈486 + MFE 0.36-0.75R + 止损/超时**;
   - 评审 6.3 的"Q1 SHORT 集中度"猜测**成立**。
2. **盈亏口径修正(重要)**:`equity = initial_equity + realized_pnl`(**notional 主口径**),`margin_pnl` 为保证金报告口径(杠杆放大)。三笔账户真实损失 **-61.4**(非 -226.64),占 equity 10,000 的 0.61%。
3. **单笔风险预算复核(对评审 4 的修正)**:机制**已存在**(`_notional_hint` L664-668,`risk_based = equity × risk_pct / stop_pct` 与 score_based/cap 取 min);配置 `direct_risk_pct=0.006`(=0.6%,**严于**评审建议的 1.2%)。**反事实:三笔均不会被裁剪**(实际风险 0.235% < 0.6%)→ 根因是**入场位置/方向**,不是仓位大小。新增 5 单测锁定行为。
4. **4x 杠杆质量门控设计 + shadow**(`docs/2026-08-31-leverage-tier-quality-gate-design.md` + `scripts/leverage_tier_gate_shadow.py`):三档全部质量门控(4x 需 fib≥10/pa≥7/**rr≥5**),live `_select_leverage` 未改;5 单测锁定门控逻辑。
5. **归因字段补全**:`_resolve_entry_channel`(显式优先,缺失时 DIRECT→`main_direct`/PROBE→`main_probe`);确认 `source_quadrant` 早已写入(L179),三笔的 Q1 即来自该字段。
6. **验证**:`python -m pytest tests/ -q` → **642 passed + 1 既有无关失败**(`test_describe_indicator_rules` EMA/RSI 契约漂移,baseline 已知)。

## 3. 对评审的两处修正(证据驱动)

| 评审论断 | 复核结论 |
|---|---|
| "无单笔风险预算硬约束,单笔可亏 4.7%" | **机制已存在且更保守**:`direct_risk_pct=0.006`(0.6%);三笔实际风险 0.235% 远低于预算 → 不裁剪 |
| "entry_channel=null 造成归因盲区" | 部分成立:`entry_channel` 确实为 null(已补);但 **`source_quadrant` 早已写入**——三笔的 Q1 归因即来自它,盲区小于预期 |
| "三笔 margin 486 = 单笔过大" | **报告口径放大**:margin 486 = notional 1945 / leverage 4;账户实际风险按 notional(0.235%) |

**根因收敛**:三笔 = **方向错误(Q1 SHORT 在上涨段逆势,MFE 从未走对)+ 4x 无质量门放大暴露**,而非仓位管理失效。

## 4. 未落实项与阻塞理由(遵循样本纪律)

| 建议 | 状态 | 阻塞理由 |
|---|---|---|
| 杠杆质量门控**数值**上线 | shadow | 需历史回测校准(评审 5.2 自述);遵 20 笔纪律 |
| 行为确认指标(候选 1)阈值 | 待样本 | 评审 5.1 已扩展为"通用诊断字段";阈值需 ≥20 笔 |
| CCI 消融实验(候选 3) | 待样本 | 评审 4 认可"先相关性审计";随消融一起做 |
| 波动率自适应仓位(候选 2) | 待样本 | 评审 4 判"先做候选 4";且风险预算已覆盖主要风险 |
| 全窗口 4x 门控反事实运行 | 脚本就绪 | `scripts/leverage_tier_gate_shadow.py` 可运行(本轮 bash 写入受限未执行) |

## 5. 下一步建议(交评审)

1. **Q1 SHORT 方向治理优先级提升**:三笔全在 Q1 SHORT,与 08-24 SHORT 偏向审计同源 → `regime_conditional_side_offset` 从 shadow 转 live 的决策应提前;
2. 4x 杠杆门控数值用历史窗口回测校准后上线(rr≥5 是否过严需数据);
3. 行为确认与 CCI 消融作为诊断字段先记录,累计 20 笔后再定性。
