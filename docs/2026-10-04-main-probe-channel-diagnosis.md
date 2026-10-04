# main_probe 通道专项诊断(Task P)

**日期:** 2026-10-04
**依据:** 2026-10-04 评审裁定 3.5 / 3.6 节(四项诊断范围)
**窗口:** 2026-09-16 ~ 2026-10-04(跨两个完整窗口)
**命令:** `python scripts/diagnose_main_probe_channel.py --start 2026-09-16 --end 2026-10-04`
**产出:** `logs/analysis/main-probe-diagnosis/main-probe-2026-09-16_2026-10-04.json`
**性质:** 描述性诊断,**不含代码变更、不是上线批准**

---

## 〇、样本量警告(先说)

| 通道 | 跨两窗口笔数 | 门槛 |
|---|---:|---|
| **main_probe** | **18** | < 20 → 仅记录,不定性 |
| main_direct | 10 | 距 20 差 10 |

按 `2026-08-18-纪律`(SAMPLE_SIZE_DECISION_RULES),本报告**不构成"通道质量更差"的统计结论**。下述所有差异均为**描述性**,统计功效不足。五因子横向对比的可用样本更少(probe 6 / direct 5),更不可作结论。

---

## 一、结论摘要

| # | 结论 | 证据强度 |
|---|---|---|
| 1 | **方向混淆被排除**:`main_probe` 在 LONG 与 SHORT **两个方向上都是负期望** | 较强(两方向一致) |
| 2 | **Q1 本身不是问题**:Q1 同时是 main_probe(亏)与 main_direct(赚)的主战场,差异在**通道层**而非象限层 | 较强 |
| 3 | **"降杠杆"是方向不确定的动作**:main_probe 的 `binding_cap` 三者混合(raw 4 / leveraged 5 / remaining 9) | 强(机制性证据) |
| 4 | main_direct 的 `binding_cap` **100% 为 leveraged_cap_notional** —— 高杠杆确实总撞上限 | 强 |
| 5 | 五因子影子分在通道间有差异(如 `trend_persistence` probe 0.559 vs direct 0.831),但 n=6/5,**不可作结论** | 弱(样本不足) |

---

## 二、诊断 1:方向控制(排除"方向混淆")

| 通道 | 方向 | 笔数 | notional_pnl | **场均** | 平均 MFE |
|---|---|---:|---:|---:|---:|
| **main_probe** | **LONG** | 12 | -185.37 | **-15.45** | 0.652 |
| **main_probe** | **SHORT** | 6 | -48.80 | **-8.13** | 0.821 |
| main_direct | SHORT | 10 | +59.50 | +5.95 | 1.757 |
| q1_trend_launch | LONG | 11 | -0.83 | -0.08 | 0.729 |
| q1_trend_launch | SHORT | 16 | -1.31 | -0.08 | 0.485 |

**这是本报告最重要的一行**:评审 3.2 节担心"本窗口 main_probe 的 0% 胜率可能只是方向混淆"(该窗口 LONG 整体差),但**跨两窗口合并后,main_probe 的 LONG 与 SHORT 场均都是负的**(-15.45 / -8.13)。方向混淆已被排除。

反观 `main_direct`:**10 笔全部是 SHORT**——它没有在 LONG 上被检验过。样本量决定现在无法判断"main_direct 是否也主要是方向运气"。

---

## 三、诊断 3:象限分布(**Q1 不是问题**)

| 通道 | 象限 | 笔数 | notional_pnl | 平均 MFE |
|---|---|---:|---:|---:|
| **main_probe** | **Q1** | 14 | **-199.80** | 0.675 |
| main_probe | Q2 | 2 | -23.77 | 0.681 |
| main_probe | Q4 | 2 | -10.59 | 0.974 |
| **main_direct** | **Q1** | 7 | **+51.44** | **1.952** |
| main_direct | Q3 | 3 | +8.07 | 1.302 |
| q1_trend_launch | Q1 | 27 | -2.14 | 0.584 |

**评审 3.6 第三项的假设得到证实**:Q1 **同时**是亏损通道(main_probe)与盈利通道(main_direct)的主战场。因此不存在"Q1 本身对 probe 层不友好"的结构性差异——**同一个象限里,两个通道的 MFE 差了近 3 倍**(0.675 vs 1.952)。

**含义**:把矛盾定位在"Q1"是错的,应定位在**通道层的入场质量筛选强度**。main_direct 的准入门槛(DIRECT 阈值 82 + LONG offset 10 + 组件最低分 + 5x 质量门)确实筛出了明显更好的入场点,而 main_probe 的较松门槛没有。

---

## 四、诊断 4:binding_cap 分布(**决定"调杠杆"是否有效**)

| 通道 | `raw_notional` | `leveraged_cap_notional` | `remaining_exposure_notional` |
|---|---:|---:|---:|
| **main_probe** | **4** | **5** | **9** |
| main_direct | 0 | **10** | 0 |
| q1_trend_launch | 0 | 1 | 26 |

**回答评审 3.4 节的疑问**:数据支持"降杠杆是方向不确定的动作"这一判断,而且比预期更细:

- **main_probe 的 18 笔中,只有 5 笔由 `leveraged_cap_notional` 约束** → 对**这 5 笔**降杠杆会**放大**名义仓位(因该 cap 与杠杆成反比);
- 另 **4 笔由 `raw_notional` 约束** → 对它们,本轮的 `probe_risk_pct` 下调(0.0025→0.0015)**直接有效**;
- 余 **9 笔由 `remaining_exposure_notional` 约束** → 两个参数都不起作用,受单币敞口上限支配。

**即:任何单一参数调整都只能覆盖约 1/4 ~ 1/2 的 main_probe 交易。** 想要系统性收紧,需要按 `binding_cap` 分层处理,而不是调一个全局参数。

**附带发现**:`main_direct` 10/10 全部撞 `leveraged_cap_notional` → `max_single_trade_risk_pct`(0.75%)**确实是 DIRECT 层的实际约束**,这解释了为何 4-5x 未失控,也说明**调 DIRECT 杠杆倍数会直接改变名义仓位**。`q1_trend_launch` 26/27 撞 `remaining_exposure_notional`(1x 小仓,受单币敞口支配)。

---

## 五、诊断 2:五因子影子横向对比(样本不足,仅记录)

| 因子 | main_probe 均值 | main_direct 均值 | 差值 |
|---|---:|---:|---:|
| `trend_persistence` | 0.5591 | 0.8308 | -0.2717 |
| `structure_location` | 0.8570 | 0.0000 | **+0.8570** ⚠️ |
| `payoff_geometry` | 0.4179 | 0.5000 | -0.0821 |
| `volatility_regime` | 0.7869 | 0.2583 | +0.5286 |
| `order_flow` | 0.4238 | 0.6699 | -0.2461 |

**可用样本仅 probe 6 / direct 5**——上述任何一行都**不具备统计意义**,仅作为"下一轮做这件事的可行性证明"。

⚠️ **`structure_location` 的 +0.857 差值存疑**:main_direct 侧全部为 0.0000,这更像**关联误差**(交易与入场决策按"同日 + 同 symbol"近似匹配,同日多条可执行记录时可能匹配到非入场时刻的那条),而非真实的因子差异。**在建立稳定的 `decision_id` 关联之前,这一项不应被引用。**

**建议**:下一轮若要正式做通道间因子对比,必须先补齐交易↔决策的稳定关联 ID(评审 3.6 与 09-15 报告 8.6 节均提过这一点)。

---

## 六、对评审 3.4 / 3.5 节的回应

| 评审判断 | 本诊断的实证 |
|---|---|
| "降杠杆是方向不确定的动作,需先核实 binding_cap" | **成立**。main_probe 三种 cap 混合(4/5/9),降杠杆对其中 5 笔会放大仓位 |
| "下调 `probe_risk_pct` 方向明确、可立即执行" | **成立**。`raw_notional` 与 `probe_risk_pct` 线性正比,且是三重 min 之一 → 只会收紧或不变(已有单测 `test_probe_risk_pct_linear_scaling` 锁定) |
| "提高 PA/Fib/RR 门槛暂不可做(entry_score 无预测力证据)" | **成立**。本诊断未发现可支撑"提高哪个分量门槛"的证据 |
| "全面停用 main_probe 暂不可做" | **成立**。方向混淆虽已排除,但 18 笔仍低于门槛,且 Q1 在两个通道都出现 → 矛盾在通道层筛选强度,需更多样本 |

---

## 七、下一步建议(供评审)

1. **分层收紧而非统一调参**:既然 main_probe 的 18 笔由三种 cap 分摊约束,建议按 `binding_cap` 分层设计——对 `raw` 生效的样本用 `probe_risk_pct`,对 `remaining` 生效的样本考虑单币敞口上限。**但 18 笔样本不支持现在拍板**。
2. **补齐交易↔决策稳定关联 ID**(`decision_id` / `position_id`),这是做通道间因子对比的前置条件;当前"同日 + 同 symbol"近似关联已产生明显误差(`structure_location` 一行)。
3. **main_direct 从未在 LONG 上被检验**(10/10 SHORT),下一轮应特别关注其 LONG 侧表现,避免把它当作"已验证的优质通道"。
4. **Q1 本身无需处理**:诊断 3 已排除"Q1 结构性不友好"这一假设。

---

## 八、可复现

```powershell
python scripts/diagnose_main_probe_channel.py --start 2026-09-16 --end 2026-10-04
# JSON: logs/analysis/main-probe-diagnosis/main-probe-2026-09-16_2026-10-04.json
python scripts/analyze_0916_0927_window.py --start 2026-09-27 --end 2026-10-04 --output-dir logs/analysis/2026-10-04-window
```

**数据来源**:`logs/2026-09/{16..30}/paper_trades.jsonl`(交易)与 `decisions.jsonl`(入场时刻影子分 + `metadata.risk_budget.binding_cap`)。

> `binding_cap` **已存在于历史日志**(`decisions.jsonl` 的 `metadata.risk_budget.binding_cap`,跨两窗口 59 条可执行记录全部有值),无需补字段即可核查——这项发现修正了 2026-10-04 归因报告第 2 节的初判("主决策路径未落盘")。
