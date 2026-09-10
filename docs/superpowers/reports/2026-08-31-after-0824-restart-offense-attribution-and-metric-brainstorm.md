# AI300 08-24 重启后进攻复盘:开仓少且亏损的归因 + 开仓链路全量说明 + 指标头脑风暴

**提交对象:** DEEPSEEK 评审
**分析窗口:** 2026-08-24 22:00(进程重启 cycle 1 @ 08-24 14:00 UTC)~ 2026-08-31(本地日志末,北京时间为准)
**运行模式:** VPS dry-run / paper ledger / SCOUT micro / paper A-B mirror(shadow)
**数据来源:** `logs/2026-08/2026-08-{24..31}/` 下 `decisions.jsonl`、`near_misses.jsonl`、`paper_trades.jsonl`、`scout_micro/paper_trades.jsonl`、`paper_ab/*/paper_trades.jsonl`、`summary.json`、`health.json`;配置 `configs/entry_chain.dry_run_fib_pa_v1.json`;`scripts/analyze_baseline_window.py`、`summarize_experiment_pnl.py`、`summarize_channel_stats.py`
**口径:** 本地日志同步至 08-31(当前 09-10),本文止于 08-31;`summarize_channel_stats` 扫 scout/mirror 路径,主账本以 `paper_trades.jsonl` 直接统计。

---

## 0. 结论摘要

1. **"开仓少"成立**:8 天 10,637 条决策,可执行仅 **25**(PROBE 21 + DIRECT 4,占 0.24%);主账本实际开仓 **22 笔**(q1_trend_launch 9 笔 + 其他 13 笔)。
2. **"亏损"的主因不是次数,而是少数 4 倍杠杆大仓**:主账本窗口 `margin_pnl` 合计 **-226.64**,其中单笔 **-94.08 / -90.78 / -60.81**(均 `leverage=4`、`margin_used≈486`、`entry_channel=null`、`max_favorable_r_observed` 仅 0.36-0.75)占绝大部分;q1_trend_launch 的 9 笔小仓(notional 62.5)合计仅约 **-1.78**。
3. **入场质量先于出场**:大额亏损笔的共同特征是 **MFE 未达 1R(0.36-0.75)即被止损/出场**——即"入场时就已处在不利位置",杠杆只是放大后果。
4. **通道层**:mirror(shadow)192 笔 -23.14(仍持续负,已 shadow 不计熔断);scout 侧 Q2 pending 16 笔 -4.43、LONG offset probe 17 笔 -2.25、Q3→Q1 0 笔;q1_trend_launch 小仓近似打平。
5. **改善方向**:①高杠杆仓前置"行为确认"过滤(突破确认,而非仅状态评分);②把固定 `leverage=4` 换成波动率自适应仓位;③指标层评估替换 CCI(滞后/过热段失真)。详见第 5 节头脑风暴。

## 1. 窗口数据与亏损构成

| 指标 | 值 |
|---|---:|
| decisions | 10,637(Q1 1116 / Q2 1421 / Q3 2101 / Q4 5999) |
| actions | NO_TRADE 9458 / WATCH 1154 / **PROBE 21 / DIRECT 4** |
| score ≥80 / ≥85 | 299 / 84(最高 96.15) |
| near_misses | 391 |
| 主账本开仓/平仓/减仓 | 22 / 22 / 13 |
| 主账本 margin_pnl | **-226.64** |
| 实验账本 margin_pnl(含 scout+mirror shadow) | **-28.47**(最差日 08-24 -10.72) |
| 熔断 | 未触发(累计远高于 war_fund -150) |

### 1.1 大额亏损笔特征(主账本)

| 日期 | event | leverage | margin_used | margin_pnl | max_favorable_r |
|---|---|---:|---:|---:|---:|
| 08-24 | PAPER_CLOSE | 4 | 486.28 | **-94.08** | 0.69 |
| 08-24 | PAPER_CLOSE | 4 | 486.18 | **-60.81** | 0.75 |
| 08-28 | PAPER_CLOSE | 4 | 484.54 | **-90.78** | 0.36 |

- `entry_channel: null`、`experiment_id: null`、`exit_mode: "trend_capture"`——**非实验通道,是主账本常规开仓**;
- `margin_used ≈ 486` ≈ `max_total_exposure_pct(1.6)` 与账户权益的乘积量级 → 单笔接近满敞口;
- `max_favorable_r_observed ≤ 0.75` → 入场后从未走出 1R,**是入场位置问题而非出场过紧**。

### 1.2 通道盈亏(窗口)

| 通道 | 开仓 | margin_pnl | 说明 |
|---|---:|---:|---|
| q1_trend_launch(主账本) | 9 | ≈ -1.78 | 小仓 notional 62.5,近似打平(BCH +1.09/XMR +1.57/SOL +0.61 对 HYPE -1.49/BCH -3.13) |
| 主账本其他(leverage 4 大仓) | 13 | **-224.9** | 亏损主体 |
| scout_q2_pending_momentum | 16 | -4.43 | 负 |
| scout_high_score_long_offset_probe | 17 | -2.25 | 负 |
| scout_q3_to_q1_confirmation | 0 | 0.0 | 窗口无样本 |
| mirror_ab_sample(shadow) | 192 | -23.14 | 持续负,已 shadow(不计熔断) |

## 2. 实盘开仓链路(dry-run/paper 同构)

```
每 15m K 线收盘(align-to-kline-close + post-close delay)
  → 拉取多周期 K 线(15m/30m/1h/4h,public-binance)
  → build_context:方向(1h direction_from_history)+ 指标 + 特征
      · 组件分:trend_ema_context / flow_cvd_confirmation / cci_momentum_quality
                / price_action_structure / fibonacci_location / risk_reward_geometry
      · 特征标志:long_overextension / upper_wick / chase / extreme_position_ratio / cvd_weak
  → evaluate_entry_chain:dynamic_weights(FIB_PA 权重)→ component_points → total_score
  → _score_to_action:total_score 对比 direct(82)/probe(70)/watch(62)+ LONG offset(+10)
  → 组件最低分闸门:
      · DIRECT minimums:pa≥6、fib≥9、rr≥4 → 否则降 PROBE
      · PROBE conditions:score≥72、fib≥12、pa≥6(probe_conditions)
  → 四象限标注(annotate_quadrant):Q1/Q2/Q3/Q4(轴阈值见 §3.3)
  → 决策控制 apply_dry_run_decision_controls:每日预算、冷却、敞口、熔断
  → 仓位:_select_leverage + _notional_hint(exposure_pct × equity)
  → 纸面账本 on_decision 开仓 / 出场(TP 阶梯 + 止损 + 时间衰减)
  → SCOUT micro(独立小账本)/ mirror A-B(shadow)/ 策略审计
```

## 3. 详细门槛分数、权重评分

### 3.1 总分门槛(`configs/entry_chain.dry_run_fib_pa_v1.json`)

| 参数 | 值 | 语义 |
|---|---:|---|
| `direct_threshold` | 82.0 | DIRECT 最低总分 |
| `probe_threshold` | 70.0 | PROBE 最低总分 |
| `watch_threshold` | 62.0 | WATCH 最低总分 |
| `long_threshold_offset` | 10.0 | LONG 侧 direct/watch 门槛 +10(顶层);probe 层 7.0(有意两层) |
| `short_threshold_offset` | 0.0 | SHORT 无偏移(**08-24 审计确认非对称来源**) |

### 3.2 组件最低分(DIRECT / PROBE)

| 闸门 | 参数 | 值 |
|---|---|---:|
| DIRECT | `pa_min_direct_score` | 6.0 |
| DIRECT | `fib_min_direct_score` | 9.0 |
| DIRECT | `rr_min_direct_score` | 4.0 |
| PROBE | `probe_conditions.min_score` | 72.0 |
| PROBE | `probe_conditions.min_fib_score` / `min_pa_score` | 12.0 / 6.0 |
| 5x 杠杆 | `leverage_5x_fib_min` / `pa_min` / `rr_min` | 13.0 / 9.0 / 4.0 |

### 3.3 权重评分(FIB-PA 架构,满分 100)

| 组件 | 权重 | 含义 |
|---|---:|---|
| `price_action_structure` | 22.0 | 价格行为结构(swing/实体) |
| `trend_ema_context` | 20.0 | EMA 上下文趋势(含 EMA200 门控) |
| `flow_cvd_confirmation` | 18.0 | 资金流 CVD 确认 |
| `fibonacci_location` | 18.0 | 斐波位置(回撤/扩展) |
| `cci_momentum_quality` | 14.0 | CCI 动能质量(满分 14,过热段衰减) |
| `risk_reward_geometry` | 8.0 | RR 几何(支撑/阻力距离) |

`component_points = clamp(组件归一化分, 0, 1) × 权重`;`total_score = Σ points`。

**象限轴阈值**:`quadrant_trend_ema_min=15`、`quadrant_price_action_min=10`、`quadrant_flow_cvd_min=14`、`quadrant_cci_min=7`。
- Q1=趋势轴(ema≥15 且 pa≥10)+ 资金轴(cvd≥14 且 cci≥7);Q2=仅趋势轴;Q3=仅资金轴;Q4=都不过。

## 4. 仓位管理与详细风控逻辑

### 4.1 仓位

| 参数 | 值 | 语义 |
|---|---:|---|
| `daily_max_trades_base` | 16 | 每日基础最大开仓数 |
| `max_symbol_trades_per_day` | 2 | 单币每日上限 |
| `max_active_symbols` | 8 | 同时活跃币上限 |
| `max_total_exposure_pct` | 1.6 | 总敞口上限(账户权益倍数) |
| `max_same_direction_exposure_pct` | 1.1 | 同向敞口上限 |
| `dry_run_q1_trend_launch_base_exposure_pct` | 0.025 | q1_trend_launch 基础敞口 2.5% |
| `scout_micro_notional` / `mirror_ab_notional` | 50.0 / 50.0 | 实验账本名义本金 |
| `scout_micro_leverage` | 1 | SCOUT 杠杆 1(无杠杆) |
| 主账本杠杆 | **4(实测大仓)** | aggressive tier 下常规仓杠杆;`leverage_5x_*` 门槛存在但实测为 4 |

### 4.2 风控(逐层)

| 层 | 机制 | 参数/行为 |
|---|---|---|
| 数据健康 | `data_health` 周期级重置(08-13 修复) | DEGRADED 时按 `allow_degraded_data` 决定是否开仓 |
| 熔断(实验) | `experiment_war_fund_loss_limit` / `experiment_daily_loss_limit` | -150 / -200;mirror shadow 已不计入(L223) |
| 熔断(组合) | `portfolio_stop_circuit_enabled` / `count` / `hours` | 2 次止损 / 2h 冷却 |
| SCOUT mission | `scout_micro_mission_stop_circuit_enabled` / `count` / `hours` | 3 次止损 / 12h |
| 单币冷却 | `scout_micro_same_side_cooldown_hours` / `initial_stop_cooldown_hours` | 同向 2h / 初始止损后 6h |
| 滚动冷却 | `rolling_symbol_cooldown_enabled` / `stop_threshold` / `window_hours` / `cooldown_hours` | 2 次止损 / 48h 窗口 / 24h 冷却 |
| 止损 | 出场层 `stop = ATR×1.5` clamp[0.5%, 3%] | 初始止损 |
| 止盈 | TP 阶梯 1.2/2.0/3.0R,分批 40%/35%/25% | + 8 根移成本(early breakeven) |
| 时间衰减 | `MAX_HOLD_BARS=32`(8h)后强平 | paper_trading.py |
| 每日预算 | `DAILY_TRADE_BUDGET_USED` | 用尽则拦(08-24 报告 BNB 案例) |
| 敞口 | 总/同向敞口 pct 上限 | `max_total_exposure_pct` / `max_same_direction_exposure_pct` |

**风控缺口(本次归因)**:杠杆 4 + margin 486 的单笔大仓虽满足敞口上限(1.6),但**单笔即接近满敞口**,一次入场位置失误(-94)即抵消数十笔小仓盈利——缺少"单笔最大风险(如 ≤1% 账户权益)"的硬约束。

## 5. 头脑风暴:是否新增/替换指标

### 5.1 证据锚点
- 大额亏损笔 `max_favorable_r ≤ 0.75`(从未走出 1R)→ **入场位置/时机**而非出场是主因;
- 当前评分链是"**状态质量评分**"(EMA/CVD/CCI/PA/Fib/RR 都是横截面状态),**不含"行为确认"**(突破/量能/回撤后二次启动);
- CCI 权重 14,但 08-24 报告显示"过热段 cci_momentum_quality 低分",与趋势延续段正相关弱。

### 5.2 候选 1(推荐·新增):突破-量能行为确认指标
- **设计**:`breakout_confirmation_score`(0-1)——`close > 前 32 根收盘高点` + `volume ≥ 1.15× 前 32 根中位量` + 次根收盘守住 + `close_location ≥ 0.55` + 上影线限制(即 BULL_REGIME_BREAKOUT_V1 的底层逻辑);
- **用法**:作为**高杠杆仓(leverage ≥ 4)的前置门槛**(score 达标但无行为确认 → 降杠杆或降级 PROBE),而非直接改总分权重;
- **依据**:08-24 报告"SIDE_THRESHOLD/OPPOSITION 把上涨段当追单"与本次"大额仓 MFE<1R"同源——缺行为确认;
- **验证协议**:在 08-24~08-31 窗口离线回放(复用 `audit_bullish_regime_short_bias.py` 框架),对比"有/无行为确认"分桶的 MFE/MAE 与 PF;≥20 笔 shadow 后再议权重。

### 5.3 候选 2(推荐·替换):用波动率自适应仓位替换固定 leverage=4
- **设计**:`position_leverage = f(ATR 分位)`(如 ATR% 处于近 20 日 P80 以上 → 杠杆 2,否则 4);或把 `max_total_exposure_pct` 拆为**单笔风险预算**(单笔最大亏损 ≤ 账户 1%);
- **依据**:本次 -94/-90/-60 三笔均 leverage 4 + margin≈486 + MFE<1R——固定高杠杆放大入场失误;
- **落地**:属"仓位/风控"层(非指标层),可与候选 1 组合(行为确认 + 波动率仓位);
- **验证协议**:同窗口离线回放,margin_pnl 分布/最大回撤对比;不直接改 live。

### 5.4 候选 3(评估·替换 CCI)
- **问题**:CCI(权重 14)在趋势过热段给出低分(08-24 报告),对趋势延续段的判别力弱;
- **候选替换**:量价背离/OBV 斜率,或 `cci_momentum_quality` 改为"CCI 斜率 + 与价格一致性"复合;
- **建议**:先做**相关性审计**(CCI 组件 vs 后续 4h MFE),再决定替换;避免同时改两个变量。

### 5.5 优先级与纪律
1. 候选 1(行为确认,新增)→ 与 08-24 BULL_REGIME_BREAKOUT 合并实现(复用底层),shadow 先行;
2. 候选 2(波动率仓位,替换)→ 仓位层改动,离线回放验证;
3. 候选 3(CCI 替换)→ 先做相关性审计,后置;
- 全部遵循 08-18 纪律:<20 样本不调参、不资源倾斜;不全局放宽 RR/极值;不解除黑名单。

## 6. 数据口径与局限
- 日志本地同步至 08-31(当前 09-10),08-31 后数据未含;
- 主账本大额仓的 `entry_channel=null` 说明其来自常规 DIRECT/PROBE 链路,具体 action 与杠杆选择依据需下一步在 `_select_leverage`/`_notional_hint` 代码层核实(本文基于账本事件字段);
- mirror shadow 的 PnL 为假设成交(不计熔断,但账本仍记录),不宜与实盘亏损直接相加;
- 样本量:主账本 22 笔、大额亏损 3 笔——统计显著性有限,用于改善方向设计而非结论。
