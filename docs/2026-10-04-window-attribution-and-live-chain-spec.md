# 09-27 → 10-04 窗口:亏损归因 + 实盘同构链路与风控全说明

**窗口:** 2026-09-27 ~ 2026-10-04(承接上一份 `2026-09-27-window-loss-attribution-and-factor-diagnosis.md` 的终点)
**数据源:** `logs/2026-09/{27..30}/`、`logs/2026-10/{01..04}/`
**生成命令:** `python scripts/analyze_0916_0927_window.py --start 2026-09-27 --end 2026-10-04 --output-dir logs/analysis/2026-10-04-window`
**口径:** `notional_pnl` 为主(账户口径);`margin_pnl` 为保证金报告口径,两者并列给出
**报告性质:** 归因 + 现状说明书,供外部评审;**不含任何代码变更**,也不是上线批准

---

## 〇、追踪表状态(实施追踪协议合规)

`python scripts/recommendation_tracker.py check` 返回码 **1**,存在 5 项未解决 P0。与本报告的关系:

| 建议ID | 状态 | 本报告处理方式 / 阻塞原因 |
|---|---|---|
| 2026-09-27-FACTOR | IN_PROGRESS | **本报告第二节给出五因子影子体系的首批真实数据实证**,是 P1 正交性验收的第一次正式读数 |
| 2026-08-04-P0-2 | IN_PROGRESS | LONG 非对称验证依赖样本积累;本窗口 LONG 侧 10 笔 -115.53 已纳入第二节分析 |
| 2026-08-18-Q1TL | IN_PROGRESS | q1_trend_launch 本窗口 11 笔 -0.54(1x 小仓),仍 <20 笔,不调参 |
| 2026-08-11-TaskB | PENDING | 依赖 LONG probe 样本,与本报告无直接耦合 |
| 2026-08-11-S2 | PENDING | 同上 |

---

## 一、窗口归因

### 1.1 总量

| 指标 | 值 |
|---|---:|
| 交易笔数 | 22 |
| **notional_pnl(账户口径)** | **-40.29** |
| margin_pnl(报告口径) | **+2.46** |
| 胜率 | 31.8%(7/22) |
| 决策总数 | 11,441(NO_TRADE 10,017 / WATCH 1,399 / PROBE 20 / DIRECT 5) |
| 可执行率 | 25 / 11,441 = **0.22%** |
| score ≥82 / ≥87 | 179 / 49 |

**`margin_pnl` 为正而 `notional_pnl` 为负,不是数据错误**,而是杠杆放大后两股相反力量相抵:

```
main_probe(3x)   名义 -118.04 → 保证金口径 -354.13
main_direct(4-5x) 名义 +78.29 → 保证金口径 +357.13
                       合计         +2.46
```

> **含义:保证金口径的"微正"具有误导性。** 它掩盖了"多数小亏 + 少数大赢"的结构。评价策略必须用 `notional_pnl`。

### 1.2 按入场通道(亏损集中度最高的一维)

| 通道 | 笔数 | notional_pnl | margin_pnl | 胜率 | 平均 MFE |
|---|---:|---:|---:|---:|---:|
| **main_probe** | 6 | **-118.04** | -354.13 | **0.0%** | 0.467R |
| q1_trend_launch | 11 | -0.54 | -0.54 | 27.3% | 0.638R |
| **main_direct** | 5 | **+78.29** | +357.13 | **80.0%** | **2.494R** |

**`main_probe` 5 笔亏损吃掉了 `main_direct` 4 笔盈利**:单通道 6 笔全部亏损(0 胜率),且杠杆 3x。`q1_trend_launch` 因 1x 小仓几乎无损(-0.54)。

### 1.3 按方向(**本窗口出现方向反转**)

| 方向 | 笔数 | notional_pnl | 胜率 |
|---|---:|---:|---:|
| **LONG** | 10 | **-115.53** | **10.0%** |
| **SHORT** | 12 | **+75.23** | **50.0%** |

上一窗口(09-16~09-27)是 **LONG -70.67 / SHORT -65.84(两侧同亏)**;本窗口变成 **LONG 大亏 / SHORT 大赚**。这与 08-24 与 09-27 两轮讨论的「SHORT 偏向」方向**完全对调**——说明当时的偏向诊断是**市场状态依赖**的,而非策略恒定缺陷。

### 1.4 按退出原因(最强判据)

| 退出原因 | 笔数 | notional_pnl | 平均 MFE | 中位 MFE |
|---|---:|---:|---:|---:|
| **INITIAL_STOP_HIT** | 10 | **-121.06** | 0.377R | — |
| COST_BREAKEVEN_TIMEOUT | 2 | -17.43 | 0.690R | — |
| Q4_DEFENSIVE_EXIT | 3 | -0.76 | 0.034R | — |
| **BREAKEVEN_STOP_HIT** | 7 | **+98.95** | **2.434R** | — |

与上一窗口同构的结论:**所有亏损都伴随低 MFE(初始止损 10 笔平均 0.377R),所有盈利都来自高 MFE 被移动止损保住(2.434R)**。离场机制健康,失血点仍在**入场质量**。

### 1.5 逐笔明细(按 notional_pnl 升序)

| 日期 | 币 | 方向 | 通道 | 象限 | 杠杆 | entry_score | MFE | 退出 | notional_pnl |
|---|---|---|---|---:|---:|---:|---|---:|
| 09-29 | UNIUSDT | LONG | main_probe | Q1 | 3 | 81.75 | 0.85 | INITIAL_STOP_HIT | -26.83 |
| 10-01 | LINKUSDT | LONG | main_probe | Q1 | 3 | **91.70** | 0.42 | INITIAL_STOP_HIT | -26.42 |
| 10-02 | NEARUSDT | LONG | main_probe | Q1 | 3 | 84.75 | 0.09 | INITIAL_STOP_HIT | -25.84 |
| 09-29 | CCUSDT | LONG | main_probe | Q1 | 3 | 90.75 | 0.07 | INITIAL_STOP_HIT | -21.52 |
| 09-28 | NEARUSDT | SHORT | main_direct | Q1 | 4 | 87.15 | 0.53 | INITIAL_STOP_HIT | -19.16 |
| 10-04 | NEARUSDT | LONG | main_probe | Q1 | 3 | 88.65 | 0.45 | COST_BREAKEVEN_TIMEOUT | -14.46 |
| 09-30 | BCHUSDT | SHORT | main_probe | Q4 | 3 | 76.30 | 0.93 | COST_BREAKEVEN_TIMEOUT | -2.97 |
| … | q1_trend_launch 9 笔(1x) | — | — | Q1 | 1 | 82-87 | ≤0.96 | 各类 | 合计 -0.54 |
| 10-01 | NEARUSDT | SHORT | **main_direct** | Q1 | **5** | 90.75 | **4.97** | BREAKEVEN_STOP_HIT | **+38.75** |
| 10-02 | BCHUSDT | SHORT | main_direct | Q1 | 4 | 88.19 | 3.44 | BREAKEVEN_STOP_HIT | +31.14 |
| 09-28 | SOLUSDT | SHORT | main_direct | Q1 | 4 | 83.19 | 2.08 | BREAKEVEN_STOP_HIT | +22.33 |
| 09-27 | UNIUSDT | SHORT | main_direct | Q1 | 5 | 90.19 | 1.45 | BREAKEVEN_STOP_HIT | +5.23 |

### 1.6 两个可直接引用的结论

1. **赚钱与亏钱的组合完全分离**:盈利 = `SHORT + main_direct + 高 MFE`;亏损 = `(多数)LONG + main_probe + MFE<0.9`。
2. **`entry_score` 依旧无区分力**:`91.70` 的 LONG 亏 -26.42,而 `83.19` 的 SHORT 赚 +22.33;分数与结果仍不单调。**这与上一窗口的结论一致**,说明问题不在阈值高低,而在评分本身测的东西。

---

## 二、五因子影子体系:首批真实数据实测(重点)

2026-09-27 落地的五正交因子 P0 影子(`src/signals/orthogonal_factors.py`)已在 VPS 记录数据。本窗口首次用真实日志做验收:

```powershell
python scripts/verify_five_factor_orthogonality.py --start 2026-09-27 --end 2026-10-04
```

| 指标 | 实测 | 目标 | 判定 |
|---|---:|---|---|
| 样本量 | **10,685** | — | 数据充足 |
| 两两 \|Pearson r\| 最大 | **0.2647**(F1×F2) | ≤ 0.30 | ✅ |
| Kaiser 有效维数(特征值>1) | **2** | ≥ 4 | ❌ |
| 前 2 个 PC 累积解释方差 | **0.4847** | ≤ 0.40 | ❌ |
| 单因子有效取值档位(最小) | **352** | ≥ 10 | ✅ |
| 单因子零值占比(最大) | **0.3112** | ≤ 0.15 | ❌ |
| **F2 × F3 相关系数** | **0.0044** | >0.30 触发合并预案 | ✅ 预案不触发 |

### 2.1 特征值谱是「扁平」的——这使 Kaiser 准则失效

```
特征值: 1.3389  1.0848  0.9949  0.9215  0.6600
解释率: 0.2678  0.2170  0.1990  0.1843  0.1320
```

第三特征值 **0.9949** 与 1 只差 0.005。当 n 个因子彼此**真正独立**时,标准化后协方差矩阵的期望特征值全部等于 1,PCA 在这种「球面谱」上本就会给出 2-3 个略大于 1 的分量。**换言之:`Kaiser ≥ 4` 这条验收标准,恰好会惩罚"正交化成功"的结果。**

**两两相关矩阵**(除 F1×F2 外几乎全为 0):

```
trend_persistence  × structure_location   r =  0.2647
structure_location × order_flow           r = -0.2071
其余 8 对                                  |r| < 0.08
```

**结论(供评审裁决)**:五因子在「两两正交」这一真正目标上**基本达标**;失败的三项里,`Kaiser`/`前2PC` 属于**指标选择问题**,只有「F4 零值 31%」是**真实设计缺陷**(见 2.2)。**建议评审重新定义验收指标**,例如:改用平行分析(parallel analysis)或 Marchenko-Pastur 上界判定有效维度,并把「零值占比」与「因子间 |r|」作为硬门。

### 2.2 F4(波动率状态)的真实缺陷

| 因子 | 零值占比 | 有效档位 |
|---|---:|---:|
| trend_persistence | 0.0% | 5,846 |
| structure_location | 9.9% | 5,357 |
| payoff_geometry | 11.2% | 3,973 |
| **volatility_regime** | **31.1%** | **352** |
| order_flow | 0.0% | 1,858 |

F4 的评分映射是倒 U 型:`vol_score = clip(1 - |atr_percentile - 0.60| × 2.5)`。系数 2.5 使 `atr_percentile ≤ 0.20` 或 `≥ 1.00` 时直接**硬夹到 0**——即**约三成的决策里,这个"全新维度"完全不携带信息**。档位也只有 352(其他因子 1,858–5,846)。

**建议**:把倒 U 的衰减系数降到 ~1.0–1.25,或改用高斯型 `exp(-((p-0.6)/σ)²)`,使分数在两端渐近趋 0 而非硬夹断。

### 2.3 PC1 载荷结构(与旧体系对比)

| 因子 | PC1 载荷 | PC2 载荷 |
|---|---:|---:|
| structure_location | **-0.811** | -0.066 |
| trend_persistence | **-0.658** | +0.416 |
| order_flow | +0.479 | +0.611 |
| volatility_regime | -0.133 | **+0.639** |
| payoff_geometry | +0.037 | +0.355 |

对比旧六因子的 PC1(ema/cci/pa/cvd 四者同向捆绑,载荷 -0.55~-0.65):**PC1 现在的载荷更分散**,不再是"同一个信号被计四遍"。这是本次重构的正面证据。

---

## 三、实盘同构开仓链路

> 当前为 dry-run/paper 运行(`deploy/systemd/ai300-dry-run.service`,无实盘挂单),但下列链路与实盘共用同一套代码;`orders_submitted=0` 只体现在最后一步的交易所适配器。

```
① 15m K 线收盘
   └─ 等待 post-close delay 5s(--post-close-delay-seconds 5),避免读未完成 K 线
② 拉取/更新历史:15m/30m/1h/4h(warmup 15m = 240 根,--public-kline-limit 默认 240)
③ 方向判定 direction_from_history():最近 4 根 1h 收盘变化 >±0.3% → LONG/SHORT,否则 NONE 回退 15m
④ 计算 ATR / EMA / CCI / PA / Fibonacci / RR / 量价(以及五因子影子)
⑤ FIB-PA 权重评分 → component_points + total_score
⑥ 四象限标注 Q1-Q4
⑦ 硬门链(gate_rejections 记录每一处拒绝)
⑧ 阈值 + 组件最低分 → NO_TRADE / WATCH / PROBE / DIRECT
⑨ 方向偏移、LONG 保护、流动性、高 beta、宏观降级
⑩ 选择杠杆 _select_leverage()
⑪ 计算名义仓位 _notional_cap_diagnostics()(三重取 min)
⑫ dry-run 后置控制(冷却/熔断/弱边降级)+ paper order draft
⑬ 通过 → paper ledger(实盘则为 exchange order adapter)
⑭ 持仓管理:初始止损 / TP 阶梯 / 成本保本 / Q4 防守 / 最大持仓时间
```

**关键实现位置**:

| 环节 | 文件:行 | 作用 |
|---|---|---|
| 链入口 | `src/signals/entry_chain.py:86` `evaluate_entry_chain` | 权重→组件分→总分→动作→闸门→杠杆→仓位 |
| FIB-PA 组件 | `src/signals/entry_chain_features.py:74` `fib_pa_component_scores` | 6 因子原始分 |
| 五因子影子 | `src/signals/orthogonal_factors.py` | F1-F5(P0 只记录) |
| 影子接线 | `scripts/run_live_dry_run.py` `attach_five_factor_shadow` | 写入 `component_points_v2` |
| 线上上下文 | `scripts/run_live_dry_run.py` `public_market_context` / `build_context` | 用已收盘 K 线构造 context |
| 决策落盘 | `src/observability/decision_audit.py` `DecisionAuditWriter.write_decision` | 各 JSONL 唯一写入口 |
| 象限 | `scripts/run_live_dry_run.py:1405-1410` | 两条轴判定 |
| 杠杆 | `src/signals/entry_chain.py:621` `_select_leverage` | — |
| 仓位 | `src/signals/entry_chain.py:669` `_notional_cap_diagnostics` | 三重取 min |
| 硬门 | `src/signals/entry_chain_gates.py` | 标的/数据/预算/敞口/保证金 |
| 后置风控 | `scripts/run_live_dry_run.py` | 冷却/熔断/日亏损降级 |
| 持仓生命周期 | `src/observability/paper_trading.py` | 止损/TP/超时/防守退出 |

---

## 四、门槛分数(全表,取自 `configs/entry_chain.dry_run_fib_pa_v1.json`)

### 4.1 总分门槛

| 层级 | 配置值 | LONG 侧有效值 | SHORT 侧有效值 |
|---|---:|---:|---:|
| DIRECT | 82.0 | **92.0**(顶层 offset 10.0) | 82.0 |
| PROBE | 70.0 | **77.0**(probe_conditions offset 7.0) | 70.0 |
| WATCH | 62.0 | **72.0** | 62.0 |

> 两层 offset 是有意设计(顶层 10.0 与 probe 内 7.0 分别作用于不同判定),**不要合并或删除**。`short_threshold_offset` 为 0。

### 4.2 DIRECT 组件最低分

| 组件 | 门槛(点数) |
|---|---:|
| `price_action_structure` | 6.0 |
| `fibonacci_location` | **9.0** |
| `risk_reward_geometry` | 4.0 |

不满足则降级为 PROBE。

### 4.3 PROBE 条件(`probe_conditions`)

| 条件 | 阈值 |
|---|---:|
| `min_score` | 72.0 |
| `min_fib_score` | 12.0 |
| `min_pa_score` | 10.0 |
| `min_rr_net_r`(净 TP1 R) | 1.3 |
| `min_rr_score` | 4.0 |
| 趋势/动能(二者取一) | EMA ≥ 10.0 **或** CCI ≥ 9.0 |
| 低分质量否决:总分 < 75 时 | 需 EMA ≥ 10.0 **或** CCI ≥ 7.0 |
| **elite PROBE**(总分 ≥ 75) | (PA ≥ 18 且 Fib ≥ 15)**或**(EMA ≥ 15 且 PA+Fib ≥ 30) |
| **high-beta PROBE** | PA ≥ 12、RR ≥ 5、CCI ≥ 9、EMA ≥ 12 |
| LONG 追高风险 | `long_chase_min_pa_score` 12.0 |
| 并发上限 | `max_active_probes` 2 |

### 4.4 四象限门槛(两条轴)

| 轴 | 条件 |
|---|---|
| 趋势结构轴 | `quadrant_trend_ema_min` 15.0 **且** `quadrant_price_action_min` 10.0 |
| 流动量能轴 | `quadrant_flow_cvd_min` 14.0 **且** `quadrant_cci_min` 7.0 |

Q1 = 两轴皆过;Q2 = 仅趋势轴;Q3 = 仅量能轴;Q4 = 皆未过。

> ⚠️ 注意:这里的"趋势/量能"是**相对于 intended side** 的评分,**不是** BTC 或全市场 regime。因此 Q1 完全可能是 SHORT。

### 4.5 通道级门槛

| 通道 | 状态 | 关键门槛 |
|---|---|---|
| `q1_trend_launch` | 启用 | 总分 ≥82、PA ≥18、Fib ≥15、CVD ≥16、RR ≥0.5;近 8 根极值位置比 ∈[0.20,0.80];LONG 不得触发 overextension/upper-wick/chase;数据必须 OK;`base_exposure_pct` 0.025、杠杆 1x |
| `q1_green_channel` | 启用 | 总分 ≥85、PA ≥18、CVD ≥16;`notional_mult` 1.0、`base_exposure_pct` 0.05 |
| `q2_pending` | 启用 | 总分 ≥70、PA ≥18、确认 6 根、CCI ≥9 |
| `q3_to_q1` | 启用 | 总分 ≥85、CVD ≥16、确认 3 根、PA ≥15 |
| `q1_rr_gap` | **停用** | (enabled=false) |
| `reversal_pivot` | **停用** | (enabled=false) |
| `mirror_ab` | 启用但 **shadow_only** | 总分 ≥82;notional 50;记录不计敞口/熔断 |

---

## 五、权重评分

### 5.1 现行 FIB-PA 六因子权重(`entry_chain_scoring.py: FIB_PA_WEIGHTS`)

| 因子 | 权重(满分点数) | 实测信息量(归一化 std) | 零值占比 |
|---|---:|---:|---:|
| `price_action_structure` | **22** | 0.345 | 34.8% |
| `trend_ema_context` | **20** | **0.187(最低)** | 0% |
| `flow_cvd_confirmation` | 18 | **0.381(最高)** | 0% |
| `fibonacci_location` | 18 | 0.294 | 8.9% |
| `cci_momentum_quality` | 14 | 0.336 | 49.7% |
| `risk_reward_geometry` | **8** | 0.265 | 17.7% |
| **合计** | **100** | | |

**两处已知硬伤(上一窗口已记录,仍在)**:

1. `trend_ema_context` 权重 20(第二高)而实测 std 仅 0.187(近乎常量)——**权重与信息量错配**;
2. `risk_reward_geometry` 代码上限只有 5.0(`net_tp1_r >= 1.3 → 5.0` 为最高档),**永远拿不到满分 8**,等效被隐性降权到 62.5%。

公式:`component_points = clamp(归一化分量, 0, 1) × weight`;`total_score = Σ component_points`。

### 5.2 五因子影子权重(P0 占位,不参与决策)

```json
{"trend_persistence": 22, "structure_location": 18, "payoff_geometry": 18,
 "volatility_regime": 20, "order_flow": 22}
```

P2 阶段将由单因子 IC 重新裁决(裁定报告第六节)。

---

## 六、仓位管理

`src/signals/entry_chain.py:669 _notional_cap_diagnostics` —— **三重上限取最小值**:

```python
risk_pct = direct_risk_pct(0.006) if DIRECT else probe_risk_pct(0.0025)

raw_notional      = equity × risk_pct / stop_pct
                    # 风险预算:单笔风险 ≈ 0.6%(DIRECT)/ 0.25%(PROBE)

leveraged_cap_notional = equity × max_single_trade_risk_pct(0.0075) / (stop_pct × leverage)
                    # 杠杆化单笔上限:杠杆后亏损不得超过权益 0.75%

remaining_exposure_notional = (symbol_cap - current_symbol_exposure) × equity
                    # 单币敞口剩余

final_notional = min(三者)   # 记录 binding_cap 供审计
```

**关键参数**:

| 参数 | 值 | 说明 |
|---|---:|---|
| `direct_risk_pct` | 0.006 | DIRECT 单笔风险预算 |
| `probe_risk_pct` | 0.0025 | PROBE 单笔风险预算 |
| `max_single_trade_risk_pct` | **0.0075** | **杠杆化硬上限**(杠杆一起算的账户风险) |
| `max_total_exposure_pct` | 1.6 | 组合总敞口 |
| `max_same_direction_exposure_pct` | 1.1 | 同向敞口 |
| `margin_buffer_pct` | 0.30 | 可用保证金底线 |
| 单币上限 | 大盘 0.30 / 主流 0.20 / 高 beta 0.10 | `_symbol_exposure_cap` |

> **重要**:`leveraged_cap_notional` 是 2026-08-31 评审讨论的「单笔杠杆化风险硬约束」,**现已实现**。它解释了本窗口为何 `main_direct` 用到 4-5x 也未失控:5x 会把名义仓位压到约 1/5。

**杠杆选择**(`_select_leverage`,优先级自上而下):

| 条件 | 结果 |
|---|---:|
| 非 PROBE/DIRECT | 0x |
| `rolling_sharpe_20 < 0` | 2x |
| `atr_pct > 3%` | 3x |
| `atr_pct > 1.5%` | DIRECT 4x / PROBE 3x |
| `score ≥ 90` 且 DIRECT 且满足 5x 分量门(Fib≥13/18、PA≥9/22、CCI≥7/14、RR≥4/8) | 5x |
| 其他 DIRECT / PROBE | 4x / 3x |

> ⚠️ **`DIRECT` 默认给 4x,而 4x 没有质量门控**(只有 5x 有)。这是 2026-08-31 已识别、仍**未修**的缺口(见 `docs/2026-08-31-leverage-tier-quality-gate-design.md` 的 shadow 设计)。

---

## 七、风控逻辑(全链)

### 7.1 硬门(`entry_chain_gates.py`,顺序即优先级)

1. 黑名单 / watch-only 标的政策;2. 宏观周跌幅、异常 wick、数据污染冷却;3. 已有同币持仓与活跃标的上限 8;4. 动态每日交易预算(base 16,最低 2);5. 单币每日最多 2 笔;6. 单币冷却;7. 总敞口 1.6 / 同向 1.1;8. 可用保证金 ≥ 权益 30%;9. 方向必须 LONG/SHORT。

### 7.2 方向与结构相关的降级

| 规则 | 效果 |
|---|---|
| LONG 追高(`long_chase_risk_active`)且 PA < 12 | 降 WATCH |
| LONG overextension / chase(启用 watch) | 降 WATCH |
| 宏观日跌超 -5% 或 USDT 溢价异常 | DIRECT → PROBE |
| WebSocket 重连近期 | 降 WATCH |
| 流动性比 < 20(DIRECT)| DIRECT → PROBE |
| 高 beta 标的 | 强制 PROBE,并要求 high-beta 组件门 |
| 当日盈利 > 3% | PROBE 停;DIRECT 若 < 阈值+3 降 PROBE |

### 7.3 后置控制(基于历史 paper 状态)

| 机制 | 参数 |
|---|---|
| 初始止损后冷却 | 4 小时 |
| 滚动止损冷却 | 48h 内 2 次初始止损 → 冷却 24h |
| 组合止损熔断 | 连续 **2** 次初始止损 → 熔断 2h |
| 单日亏损熔断 | 当日已实现 ≤ **-30** |
| 弱边降级 | 无正历史时 DIRECT/PROBE 降级 |
| 实验熔断 | war fund -150 / daily -200(仅实验账本) |

### 7.4 持仓生命周期(`paper_trading.py`)

| 机制 | 参数 |
|---|---|
| 初始止损 | `ATR × 1.5`,夹在 **[0.5%, 3.0%]** |
| TP 阶梯 | **1.2R / 2.0R / 3.0R** |
| TP 分批 | **40% / 35% / 25%** |
| 成本保本检查 | 持仓 8 根(MAX_HOLD_BARS//4) |
| 最大持仓 | **32 根 15m K 线** |
| trend capture 触发 | 1.5R |
| trailing | 1.0R |
| 手续费/滑点 | 各 5 bps |
| 初始权益 | 10,000 |

### 7.5 已知未闭合项

| 项 | 状态 |
|---|---|
| 4x 杠杆无质量门控 | 已出 shadow 设计(`docs/2026-08-31-...`),**未上线** |
| F4 波动率杠杆调节分量 | 只记录,`_select_leverage` 未接入 |
| `volatility_regime` 零值 31% | 本轮新发现,待修 |
| F6(资金费率/OI) | 未实现(裁定延后) |

---

## 八、与上一窗口(09-16~09-27)对比

| 指标 | 09-16~09-27 | **09-27~10-04** | 变化 |
|---|---:|---:|---|
| 笔数 | 33 | 22 | — |
| notional_pnl | -136.51 | **-40.29** | 改善 |
| 胜率 | 15.2% | **31.8%** | 改善 |
| LONG / SHORT 盈亏 | -70.67 / -65.84 | **-115.53 / +75.23** | **方向反转** |
| MFE<1R 占比 | 28/33 = 85% | 15/22 ≈ 68% | 略改善 |
| 主要出血通道 | main_probe(12 笔 -116) | **main_probe(6 笔 -118)** | **未变** |
| INITIAL_STOP_HIT | 13 笔全亏 -137.70 | 10 笔 -121.06 | 同构 |
| BREAKEVEN_STOP_HIT | 5 笔 +74.62 | 7 笔 +98.95 | 同构 |

**核心不变式(跨两个窗口稳定)**:

1. **`main_probe` 始终是第一出血点**(两窗口合计 18 笔约 -234);
2. **胜负完全由 MFE 决定**(低 MFE 全亏、高 MFE 全盈),离场机制不是瓶颈;
3. **`entry_score` 与结果无单调关系**。

**唯一变化的是方向**:SHORT 由亏转赚、LONG 由小亏转大亏。这提示——**当前策略的方向收益高度依赖市场 regime**,而评分体系对此不敏感。

---

## 九、待评审开放问题

1. **验收指标是否要重新定义?** 五因子的 `Kaiser ≥ 4` 在前 2 PC 48.5% 的「扁平谱」下必然失败,而两两 `|r| ≤ 0.265` 说明正交性其实达标。建议改用 **parallel analysis / Marchenko-Pastur 上界**,或以「两两 |r| + 零值占比」为硬门。请评审裁决指标口径。
2. **F4 的倒 U 系数(2.5)是否过陡?** 造成 31% 零值。是否改为高斯型衰减或系数降到 1.0–1.25?
3. **`main_probe` 连续两个窗口是最大出血点**(18 笔约 -234),是否应对该通道单独收紧(提高 PA/Fib 门槛)或降低其杠杆?
4. **`DIRECT` 默认 4x 且无质量门控**是否应尽快按 08-31 的 shadow 设计上线(需要 20 笔以上回测校准)?
5. **`entry_score` 失去区分力**:是否应把评分重心从「局部状态质量」转向「行为确认 + regime 一致性」(即 09-15 报告 8.2 节的 breakout confirmation)?
6. **方向收益的 regime 依赖**:是否需要在评分之外引入独立的市场 regime 门(而非继续用单币种局部结构判断)?

---

## 十、可复现来源

```text
日志:   logs/2026-09/2026-09-{27..30}/、logs/2026-10/2026-10-{01..04}/
归因:   logs/analysis/2026-10-04-window/window_attribution.json
        logs/analysis/2026-10-04-window/factor_orthogonality.json
五因子: logs/analysis/five-factor-orthogonality/orthogonality-2026-09-27_2026-10-04.json
配置:   configs/entry_chain.dry_run_fib_pa_v1.json
代码:   src/signals/entry_chain.py(门槛/杠杆/仓位)、entry_chain_scoring.py(权重)
        src/signals/orthogonal_factors.py(五因子)
        src/observability/paper_trading.py(持仓风控)
        scripts/run_live_dry_run.py(主循环与通道)
```

**复核命令**:

```powershell
python scripts/recommendation_tracker.py check
python scripts/analyze_0916_0927_window.py --start 2026-09-27 --end 2026-10-04 --output-dir logs/analysis/2026-10-04-window
python scripts/verify_five_factor_orthogonality.py --start 2026-09-27 --end 2026-10-04
python scripts/audit_duplicate_json_keys.py configs/entry_chain.dry_run_fib_pa_v1.json
```
