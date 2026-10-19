# AI300 策略全链路审计（2026-10-19）

> 只读审计产出，供 CODEBUDDY.md 更新使用。所有数值后括号为 `文件:行号`。
> 简写：`CFG`=src/signals/entry_chain_config.py，`EC`=src/signals/entry_chain.py，`ECS`=src/signals/entry_chain_scoring.py，
> `GATE`=src/signals/entry_chain_gates.py，`FEAT`=src/signals/entry_chain_features.py，`MTF`=src/context/multi_tf_rules.py，
> `RUN`=scripts/run_live_dry_run.py，`SPEC`=src/indicators/indicator_spec.py，`DC`=src/data/data_contract.py，
> `ENG`=src/indicators/indicator_engine.py，`PS`=src/risk/position_sizer.py，`RE`=src/risk/risk_engine.py，
> `PT`=src/observability/paper_trading.py，`NBE`=src/risk/net_beta_exposure_model.py，`SS`=src/risk/stress_simulator.py，
> `LEA`=src/execution/live_entry_chain_adapter.py

---

# 上篇：指标体系与开仓决策链

> 重要口径提醒：仓库里存在**两套架构开关**（`use_ema_architecture` / `use_fib_pa_architecture`）。当前 fib_pa_v1 配置两者都为 true，实际生效的是 **fib_pa 权重 + fib_pa 组件最低分**，EMA 权重表与 EMA 组件最低分**不生效**（ECS:56-61 先判 fib_pa 并 early-return；EC:366-371 fib_pa 分支 early-return，跳过 EC:372 的 EMA200 硬门槛与 EC:390-397 的 EMA50 最低分）。

## 1. 指标体系

### 1.1 六指标默认参数（代码实际默认值，与 SPEC 声明一致）

| 指标 | 默认参数 | 职责（SPEC:19-26） | 参数证据 |
|---|---|---|---|
| MACD | fast=12, slow=26, signal=9 | trend_momentum | SPEC:10；src/indicators/macd.py:14 |
| CCI | period=20 | strength_deviation_recovery | SPEC:11；src/indicators/cci.py:6 |
| BOLL | period=20, std_mult=2.0 | volatility_structure | SPEC:12；src/indicators/boll.py:6 |
| EMA | 9/21/50/200，slope_lookback=5 | trend_direction_quality_momentum | SPEC:13；ENG:24-27,46 |
| CVD | 无参数 | active_buy_sell_pressure | SPEC:14；src/indicators/cvd.py:6-11 |
| ATR | period=14 | volatility_stop_position_risk | SPEC:15；src/indicators/atr.py:6 |

指标列表硬编码顺序：`("MACD","CCI","BOLL","EMA","CVD","ATR")`（SPEC:18）。`compute_indicator_results` 一次产出 6 个 IndicatorResult（ENG:68-75）。

### 1.2 输入/输出契约

- 输入字段 15 个：symbol/timeframe/open_time/close_time/open/high/low/close/volume/quote_volume/trade_count/taker_buy_base_volume/taker_buy_quote_volume/is_closed/quality_flag（SPEC:27-43）。
- 输入校验：`is_closed is not True` 直接拒（SPEC:109-110）；quality_flag 必须属于 `[True, False, "degraded", "stale"]`（SPEC:60/DC:60）；signal 层允许 `True` 与 `"degraded"`（SPEC:101-102），但**直连入场只允许 True**（DC:334-335 `quality_allows_direct_entry`）。
- 输出字段 10 个：name/symbol/timeframe/timestamp/value/signal/trend/strength/quality_flag/metadata（SPEC:44-55）。
- 各指标必需输出键（DC:74-98）：MACD=macd_line/signal_line/histogram/histogram_slope/cross_state；EMA=ema_9/ema_21/ema_50/ema_200/ema50_slope/ema9_21_gap/bars_since_ema50_cross/bars_since_ema200_cross；CCI=cci/cci_slope/extreme_flag/recovery_flag；BOLL=middle/upper/lower_band/band_width/band_expansion_flag/band_contraction_flag/price_position；CVD=cvd/cvd_delta/cvd_slope/cvd_divergence_flag/buy_pressure/sell_pressure；ATR=atr/atr_pct/volatility_state。缺键即 `validate_indicator_result` 失败（DC:338-344）。

### 1.3 禁止用法（SPEC:75-88）

| 指标 | 禁止用法 |
|---|---|
| MACD | sole_entry, position_size, unfinished_bar_final, execution_reinterpretation |
| CCI | sole_direction, risk_control, only_trend_proof |
| BOLL | sole_direction, position_size, replace_trend_logic |
| EMA | sole_entry, position_size, countertrend_direct, unfinished_bar_final |
| CVD | sole_direction, replace_price_structure, force_signal_without_data, execution_priority |
| ATR | direction, long_short_signal, replace_trend, non_risk_module_mixing |

全局禁止（任何指标层）：create_order / final_position_size / bypass_state_machine / must_trade（SPEC:83-88，校验入口 `validate_indicator_usage` SPEC:118-127）。

### 1.4 冲突优先级（SPEC:56-67，`INDICATOR_PRIORITY` 是同一元组别名）

1 data_quality → 2 cvd_divergence → 3 ema200_direction_gate → 4 macd_trend_direction → 5 ema50_trend_quality → 6 cci_strength → 7 boll_structure → 8 ema9_21_momentum → 9 atr_risk（SPEC:56-66）。

各周期启用指标（SPEC:68-73）：4h=EMA/MACD/BOLL/CCI；1h=EMA/MACD/CCI/CVD；30m=EMA/MACD/BOLL/CCI/CVD；15m=EMA/MACD/CVD/BOLL。

### 1.5 EMA200 硬门槛 vs `use_ema_architecture`

- 默认 `use_ema_architecture=False`（CFG:60）、`ema200_gate_mode="hard"`（CFG:61）、`ema200_buffer_pct=0.003`（CFG:62）、`ema200_min_bars_stable=3`（CFG:63）。
- 门函数 `ema_direction_gate`（src/signals/ema_scorer.py:30-52）：先算 buffer 带 `ema200*(1±0.003)`，`in_buffer` 或 `bars_since_ema200_cross < 3` 或 counter 方向 → `mode="hard"` 返回 `allowed=False`（reason=EMA200_COUNTER_DIRECTION / EMA200_UNSTABLE），`mode="soft"` 返回 `allowed=True` 且 **penalty=-0.20**（ema_scorer.py:49-51）。EMA200 缺失 → `EMA200_UNAVAILABLE`（ema_scorer.py:39-40）。
- 三条生效路径**互斥**：
  1. `use_ema_architecture=False`（代码默认）：`component_scores` 不产出 `ema_200_gate/ema_50_quality/ema_momentum`（FEAT:54-68 仅在该开关 true 时计算），EC:372 的硬门槛因 `scores.get("ema_200_gate",1.0)` 缺键取 1.0 而永不触发。
  2. `use_ema_architecture=True` 且 `use_fib_pa_architecture=False`（highest_win）：EMA_WEIGHTS（ECS:30-41），且 EC:372-374 在 `ema200_gate_mode=="hard"` 时 score<=0 → 直接 NO_TRADE；EC:390-397 追加 EMA50 最低分（direct 0.60 / probe 0.40，CFG:64-65）。最高胜配置用 `soft`（configs/entry_chain.dry_run_highest_win.json:14），故硬门槛实际不阻断，只扣 0.20。
  3. `use_fib_pa_architecture=True`（fib_pa_v1）：EMA200 只作为 `trend_ema_context`（20 分制）的输入（FEAT:116-124：门 8 分 + EMA50 质量×7 + 动能×5，再 /20 归一）；EC:372/390 两段被 fib_pa early-return 跳过。fib_pa_v1 用 `soft`（fib_pa_v1:18）→ 逆势不阻断，仅 trend_ema_context 少 8 分并叠加 -0.20 penalty。
- 结论：**"EMA200 硬门槛"只在路径 2 + hard 模式下真实存在**；当前主用配置下它是"软化扣分"而非闸门。

### 1.6 多周期规则（MTF）与 live 链的真实方向来源

- 角色（MTF:10-15）：4h=background_reference；1h=direction_confirmation；30m=trend_quality_confirmation；15m=execution_trigger。
- 优先级（MTF:16-25）：data_quality → risk_constraints → 4h_background → 1h_direction → 30m_quality → 15m_trigger → position_executability → execution_layer。
- 禁止（MTF:37-44）：4h_hard_veto、15m_direction_override、independent_timeframe_commands、unfinished_high_tf_final_signal、nested_patch_conditions、execution_reinterprets_context。
- 状态集（MTF:45-50）：4h∈{BULL,BEAR,NEUTRAL}；1h∈{LONG_ALLOWED,SHORT_ALLOWED,NO_TRADE}；30m∈{CONFIRMED,WEAK,INVALID,TRANSITION}；15m∈{DIRECT,PROBE,WAIT,NO_TRADE}。
- 判定逻辑：4h BULL 需 macd>0 且 cci>100 且 cvd_delta>=0（MTF:107-108）；1h 需 macd>0 且 cci>100 且 cvd_delta>0 才 LONG_ALLOWED（MTF:115-116）；30m 用 cci±100 判 CONFIRMED/WEAK，`macd_hist`≈0 或 cci 缺失 → TRANSITION（MTF:122-136）；15m 用 RSI 上穿/下穿 50 + cvd_delta 同号（MTF:139-148）；合成决策见 MTF:194-234（1h 允许 + 30m/15m 同向 → DIRECT；4h 反向则降 PROBE，MTF:216-218）。
- **关键实现偏差**：`MTF` / `src/context/multi_tf_context.py` 在 live 干跑链里**未被引用**（只有 scripts/describe_multi_tf_rules.py 与 scaffold 引用）。run_live_dry_run 实际用 `FEAT.agreement_score` 的 K 线涨跌幅近似（FEAT:264-270），lookback 分别 4h→3、1h→4、30m→6 根（FEAT:45-47）。
- `direction_from_history`（FEAT:22-32）读的是**传入的哪个周期**：RUN:2581 传 `histories.get("1h")` → **方向来源是 1h**（最近收盘 vs 4 根前，±0.3% 阈值）；返回 NONE 时退化用 15m 最近 3 根比较（RUN:2582-2583）。即"方向"与"1h 权限"耦合在同一条 1h 序列上。
- 每周期取 241 根 K 线（RUN:2505-2507 `max(--public-kline-limit=240, 240)+1`；GET 见 RUN:2464-2467）。EMA 计算需 ≥200 根（FEAT:238-240），故 15m 侧刚好可用；4h/30m/1h 各 241 根约等于 40 天/5 天/10 天。

### 1.7 `component_scores` 组件映射（FEAT:35-71）

| 组件 | 计算依据 | 取值 | 行号 |
|---|---|---|---|
| background_4h | agreement_score(side, 4h, 3)：`clamp(0.5 + 涨跌×50)`（LONG）/`0.5-涨跌×50`（SHORT） | [0,1] | FEAT:45, 264-270 |
| direction_1h | agreement_score(side, 1h, 4) | [0,1] | FEAT:46 |
| quality_30m | agreement_score(side, 30m, 6) | [0,1] | FEAT:47 |
| trigger_15m | 最近 1 根 15m 涨跌：>0.0015→1.0；>0→0.4；反之 0 | {0,0.4,1.0} | FEAT:48, 273-279 |
| cvd_flow | 最近 6 根 15m 的"方向×volume"求和（close>=open 记 +vol）；同号→1.0，异号→0.2，和=0→0.5。**注意：不是真实 taker CVD** | {0.2,0.5,1.0} | FEAT:49, 282-293 |
| volatility_stop | `0.005 <= atr_pct <= 0.04` → 1.0，否则 0.2 | {0.2,1.0} | FEAT:50 |
| liquidity_execution | 常量 1.0 | 1.0 | FEAT:51 |
| market_regime | 常量 0.8 | 0.8 | FEAT:52 |
| trend_ema_context | (gate 8 + ema50×7 + momentum×5)/20，gate 不过则全 0 | [0,1] | FEAT:106, 116-124 |
| flow_cvd_confirmation | 同 cvd_flow | {0.2,0.5,1.0} | FEAT:107 |
| cci_momentum_quality | `min(1, cci_score/14)` | [0,1] | FEAT:108 |
| price_action_structure | `min(1, pa_score/22)` | [0,1] | FEAT:109 |
| fibonacci_location | `min(1, fib_score/18)` | [0,1] | FEAT:110 |
| risk_reward_geometry | `min(1, rr_score/8)` | [0,1] | FEAT:111, 154-226 |
| fib_action_cap | fib_result.action_cap=="NO_TRADE" → 0.0，否则 1.0 | {0,1} | FEAT:112 |

`risk_reward_geometry_detail`（FEAT:154-226）：stop_dist=`clamp(atr×1.5, close×0.5%, close×3.0%)`（FEAT:170）；tp1=stop×1.2（FEAT:171，`TP1_R_MULTIPLIER=1.2` at FEAT:15）；`net_tp1_r=(tp1-close×0.001)/stop`（FEAT:172）；分数阶梯 1.3→5.0 / 1.1→3.5 / 0.9→2.0 / 否则 0（FEAT:173-180）；反向结构太近（<0.7×stop）扣 3.0，<1×stop 扣 1.5（FEAT:191-195）；ATR 区间加分 0.008–0.025→+3.0、0.005–0.008→+1.5、>0.030→+1.0（FEAT:198-205）；最终 clamp 到 [0,8]（FEAT:207）；归零原因 NET_TP1_R_TOO_LOW / OPPOSITION_STRUCTURE_TOO_CLOSE / ATR_OUT_OF_RANGE / UNKNOWN（FEAT:209-217）。

辅助特征：
- `atr_pct` = 最近 20 根 15m 的 TR 均值 / 最新 close（FEAT:296-305；RUN:2584）。
- `quote_volume_24h` = 最近 96 根 15m 的 Σ(close×volume)（FEAT:308-309；RUN:2610）。
- `extreme_position_ratio` = 最新 close 在近 8 根 [low,high] 的归一化位置（FEAT:343-359；RUN:2622）。**唯一消费方是 Q1 trend-launch 的 0.20–0.80 区间检查**（RUN:1038-1050）。
- `wick_anomaly` = high/low>1.05 且当前 volume < 前根×0.5（FEAT:373-378；RUN:2615）→ 硬闸门 `DATA_WICK_ANOMALY`。
- `long_overextension_active` = close ≥ 近 20 根均值+2σ（FEAT:312-319）；`long_upper_wick_risk_active` = 上影 ≥ 2×实体（FEAT:322-330）；`long_chase_risk_active` = 近 8 根涨幅 > 2×atr_pct（FEAT:333-340）；`long_low_liquidity_session_active` = UTC 22/23/0 点且近 8 根均量 < 前 32 根×0.8（FEAT:362-370）。四者只在 LONG 侧生效。
- dry-run 固定注入：`expected_order_size=1000.0`、`account_equity=10000.0`、`available_margin=8000.0`（RUN:2612-2614）、`stop_pct=clamp(atr×1.5, 0.005, 0.04)`（RUN:2616）、`current_volatility_scale=max(0.1, atr_pct/0.01)`、`normal_volatility_scale=1.0`（RUN:2623-2624）。

## 2. 开仓决策链（`evaluate_entry_chain`，EC:86-205）

### 2.1 严格执行顺序

| 步 | 动作 | 行号 | 说明 |
|---|---|---|---|
| 0 | `max_symbol_exposure_pct = symbol_exposure_cap(symbol,cfg)` | EC:91 | 大市值 0.30 / 主流 0.20 / 高beta 0.10（GATE:9-11, 90-98；CFG:52-54） |
| 1 | `dynamic_weights(atr_pct)` → weights + reasons | EC:92 | 见第 4 节 |
| 2 | `_apply_long_context_discounts` 折扣组件分 | EC:94 | 仅 `enable_long_context_discounts` 且 LONG（EC:328-329） |
| 3 | `component_points` = clamp(score,0,1)×weight，四舍五入 4 位 | EC:95 / ECS:86-90 | — |
| 4 | `score = round(sum(points),4)` | EC:96 | 总分 0–100 |
| 5 | `ratio = liquidity_ratio(context)` | EC:97 / GATE:82-87 | `QV24h / (max(1,atr_pct×100) × expected_order_size)` |
| 6 | fib_pa 且 `fib_action_cap<=0` → NO_TRADE(`FIB_EXTENSION_EXHAUSTION_BLOCK`) | EC:99-110 | 1.618 延伸耗尽 |
| 7 | `hard_block_reason` → NO_TRADE | EC:112-114 | 见 2.2 |
| 8 | `_score_to_action`（side 偏移） | EC:116 / EC:282-296 | watch/probe/direct 三段 |
| 9 | `_apply_component_minimums` → 可降级 | EC:117-121 | direct→probe→watch |
| 10 | `_apply_probe_disable`（`disable_probe` → NO_TRADE） | EC:117-121 / EC:351-355 | — |
| 11 | LONG overextension/chase → WATCH（fib_pa 且开关开启） | EC:123-133 | `LONG_OVEREXTENSION_OR_CHASE_RISK_WATCH` |
| 12 | LONG chase 且 PA 点 < `long_chase_min_pa_score`(12.0) → WATCH | EC:135-139 | — |
| 13 | LONG 低流动性时段 → `min_action(WATCH)` | EC:141-143 | 需 `enable_long_context_discounts` |
| 14 | 宏观日跌 ≤ `macro_daily_drop_block_pct` 或 USDT 异常：DIRECT→PROBE | EC:145-148 | **不是硬阻断** |
| 15 | websocket 重连 → `min_action(WATCH)` | EC:150-152 | — |
| 16 | `ratio < probe_liquidity_ratio` → NO_TRADE | EC:154-155 | — |
| 17 | `ratio < direct_liquidity_ratio` 且 DIRECT → PROBE | EC:156-159 | — |
| 18 | 高beta 且 DIRECT → PROBE，并**重跑** fib_pa probe 条件，失败→WATCH | EC:161-169 | — |
| 19 | 当日盈利 >3%：PROBE→WATCH；DIRECT 且 score < direct+3 → PROBE | EC:171-178 | — |
| 20 | 符号敞口 ≥ 上限 → NO_TRADE | EC:180-181 | — |
| 21 | `_select_leverage` + `_notional_hint` | EC:183-191 | 见第 5 节 |
| 22 | 组装 `EntryChainDecision` | EC:193-205 / EC:763-814 | side 非 PROBE/DIRECT 时置 "NONE"（EC:797） |

### 2.2 全部硬闸门（GATE:38-70，按判定顺序）

| # | reason | 条件 | 行号 |
|---|---|---|---|
| 1 | SYMBOL_BLACKLISTED | symbol ∈ `blacklist_symbols` | GATE:40-41 |
| 2 | SYMBOL_WATCH_ONLY | symbol ∈ `watch_only_symbols` | GATE:42-43 |
| 3 | MACRO_WEEKLY_RISK | `macro_weekly_drop_pct <= cfg.macro_weekly_drop_block_pct`（默认 -0.15） | GATE:44-45 |
| 4 | DATA_WICK_ANOMALY | `wick_anomaly_active` | GATE:46-47 |
| 5 | DATA_POLLUTION_COOLDOWN | `timestamp <= polluted_until_ts` | GATE:48-49 |
| 6 | SYMBOL_POSITION_ALREADY_OPEN | symbol ∈ `active_symbol_names` | GATE:50-51 |
| 7 | MAX_ACTIVE_SYMBOLS | `active_symbols >= max_active_symbols`（默认 5） | GATE:52-53 |
| 8 | DAILY_TRADE_BUDGET_USED | `portfolio_trades_today >= daily_max_trades(context,cfg)` | GATE:54-55, 73-79 |
| 9 | SYMBOL_DAILY_TRADE_BUDGET_USED | `symbol_trades_today >= max_symbol_trades_per_day`（默认 1） | GATE:56-57 |
| 10 | SYMBOL_COOLDOWN_ACTIVE | `timestamp < cooldown_until_ts` | GATE:58-59 |
| 11 | TOTAL_EXPOSURE_CAP | `total_exposure_pct >= max_total_exposure_pct`（默认 1.50） | GATE:60-61 |
| 12 | SAME_DIRECTION_EXPOSURE_CAP | `same_direction_exposure_pct >= 1.20` | GATE:62-63 |
| 13 | MARGIN_BUFFER_TOO_LOW | `available_margin < equity × margin_buffer_pct(0.20)` | GATE:64-65 |
| 14 | ACCOUNT_EQUITY_INVALID | `account_equity <= 0` | GATE:66-67 |
| 15 | SIDE_NOT_ALLOWED | side ∉ {LONG,SHORT} | GATE:68-69 |

日内额度动态公式（GATE:73-79）：`max(min_daily_trades, floor(daily_max_trades_base × current_vol/ normal_vol))`；当日盈利>3% 再整除 2。EC:262-279 有等价实现（`_daily_max_trades`/`_daily_budget_detail`，被 metadata 使用，EC:809-810）。

**审计发现（实现偏差）**：EC:232-259 存在本地 `_hard_block_reason`、EC:603-618 存在本地 `_liquidity_ratio`/`_symbol_exposure_cap`、EC:212-229 存在本地 `_rescale_weights`/`_component_points` —— 全为**未被引用的重复实现**（`evaluate_entry_chain` 用的是 GATE/ECS 版本，EC:91-97, 112）。本地 `_hard_block_reason` 少了黑名单/watch_only 两闸（EC:232-259 vs GATE:40-43）。

### 2.3 四象限与通道（RUN）

- `quadrant_axes`（RUN:1481-1490）两轴：
  - 轴A trend_structure_ok = `trend_ema_context >= 15.0` 且 `price_action_structure >= 10.0`（RUN:1482-1485）
  - 轴B flow_momentum_ok = `flow_cvd_confirmation >= 14.0` 且 `cci_momentum_quality >= 7.0`（RUN:1486-1489）
  - 阈值来源 CFG:95-98，fib_pa_v1:83-86 显式重写为同值。
- `decision_quadrant`（RUN:1493-1501）：A&B→Q1；A only→Q2；B only→Q3；都不是→Q4。

| 通道 | 关键条件（阈值） | 行号 | 当前状态 |
|---|---|---|---|
| q1_green_channel / q1_trend_launch（同一实现） | `dry_run_q1_trend_launch_enabled`；data_health=="OK"；符号非黑名单/watch_only/observation_only；象限=Q1；side∈{LONG,SHORT}；`0.20 <= extreme_position_ratio <= 0.80`；LONG 三风险标志任一→拒；score ≥ 82.0；PA ≥ 18.0；fib ≥ 15.0；CVD ≥ 16.0；RR ≥ 0.5 | RUN:1014-1064, 873-935, 984-993 | 开启；green_channel 字段为死配置 |
| q1_trend_launch 仓位 | `exposure_pct = 0.025 × clamp(rr_points/8, 0.25, 1.0)`；与 `_notional_cap_diagnostics` 取 min；leverage 固定 1 | RUN:886-900, 931 | exit_mode=trend_capture |
| q2_pending | 象限=Q2；score ≥ 70.0；PA ≥ 18.0；有效期 6×900s；确认需 `Q2_PENDING_MOMENTUM_CONFIRMED` 且 CCI ≥ 9.0 | RUN:1566-1586, 1620-1650 | 开启 |
| q3_to_q1 | 源 Q3；score ≥ 85.0；CVD ≥ 16.0；有效期 3×900s；确认需象限变 Q1 且 PA ≥ 15.0 | RUN:1543-1563, 1589-1617 | 开启 |
| reversal_pivot | 方向反转；score ≥ 70.0；象限∈{Q1,Q2,Q3}；需 exhaustion/opposition；CVD ≤ 16 或 CCI ≤ 10 | RUN:1328-1355 | **停用** |
| q1_rr_gap | 象限=Q1；score ≥ 82.0；CVD ≥ 16.0；含 `_BELOW_RISK_REWARD_GEOMETRY` | RUN:1513-1524 | **停用** |

其他通道：HIGH_SCORE_LONG_OFFSET_PROBE（RUN:1358-1376）、FIB_CONTINUATION_SCOUT、SCOUT_ONLY_HIGH_SCORE、WATCH_ONLY_SYMBOL_PROMOTION_TEST，mission 优先级 RUN:1295-1315。near_miss 全局门槛 `--near-miss-min-score` 默认 82.0（RUN:434），Q2 用 70.0 覆盖（RUN:212, 864-869）。

---

# 下篇：门槛分数、权重评分、杠杆名义仓位

## 3. 门槛分数

### 3.1 类默认值（`EntryChainConfig`）

| 字段 | 默认值 | 行号 |
|---|---|---|
| direct_threshold | 82.0 | CFG:27 |
| probe_threshold | 70.0 | CFG:28 |
| watch_threshold | 60.0 | CFG:29 |
| min_direction_direct_score | 0.64 | CFG:30 |
| min_quality_direct_score | 0.73 | CFG:31 |
| min_trigger_direct_score | 0.92 | CFG:32 |
| min_cvd_direct_score | 0.61 | CFG:33 |
| min_direction_probe_score | 0.56 | CFG:34 |
| min_quality_probe_score | 0.45 | CFG:35 |
| min_trigger_probe_score | 0.67 | CFG:36 |
| min_cvd_probe_score | 0.45 | CFG:37 |
| high_vol_atr_pct | 0.035 | CFG:38 |
| low_vol_atr_pct | 0.010 | CFG:39 |
| macro_daily_drop_block_pct | -0.05 | CFG:40 |
| macro_weekly_drop_block_pct | -0.15 | CFG:41 |
| direct_liquidity_ratio | 20.0 | CFG:42 |
| probe_liquidity_ratio | 8.0 | CFG:43 |
| max_active_symbols | 5 | CFG:44 |
| daily_max_trades_base | 4 | CFG:45 |
| min_daily_trades | 1 | CFG:46 |
| max_symbol_trades_per_day | 1 | CFG:47 |
| max_same_direction_exposure_pct | 1.20 | CFG:48 |
| max_total_exposure_pct | 1.50 | CFG:49 |
| margin_buffer_pct | 0.20 | CFG:50 |
| max_single_trade_risk_pct | 0.0075 | CFG:221 |
| direct_risk_pct / probe_risk_pct | 0.008 / 0.003 | CFG:56-57 |
| min_stop_pct / max_stop_pct | 0.005 / 0.04 | CFG:58-59 |
| max_large_cap / mainstream / high_beta 敞口 | 0.30 / 0.20 / 0.10 | CFG:52-54 |
| pa_min_direct / fib_min_direct / rr_min_direct（点数） | 6.0 / 6.0 / 2.0 | CFG:181-183 |
| leverage_5x fib/pa/cci/rr 最低分 | 13.0 / 9.0 / 7.0 / 4.0 | CFG:184-187 |
| weak_edge direct 区间 / probe 区间 | 82–85 / 77–85 | CFG:188-191 |
| long_threshold_offset / short_threshold_offset | 0.0 / 0.0 | CFG:196-197 |
| use_ema_architecture / use_fib_pa_architecture | False / False | CFG:60, 173 |
| ema200_gate_mode | "hard" | CFG:61 |
| ema50_min_for_direct / probe | 0.60 / 0.40 | CFG:64-65 |
| disable_probe | False | CFG:66 |
| probe_conditions | None | CFG:67 |
| five_factor_shadow_enabled | True | CFG:224 |
| entry_gates | () | CFG:228 |

### 3.2 两份 dry-run 配置 vs 默认值（只列被覆盖字段）

| 字段 | 类默认 | fib_pa_v1 | highest_win |
|---|---|---|---|
| direct_threshold | 82.0 | 82.0（:2） | 82.0（:2） |
| probe_threshold | 70.0 | 70.0（:3） | 70.0（:3） |
| watch_threshold | 60.0 | **62.0**（:4） | 60.0（:4） |
| long_threshold_offset | 0.0 | **10.0**（:177） | **10.0**（:34） |
| short_threshold_offset | 0.0 | 0.0（:178） | 0.0（:35） |
| probe_conditions.enabled | None | **true**（:25） | 未配置 |
| probe_conditions.long_threshold_offset | — | **7.0**（:47） | — |
| probe_conditions.short_threshold_offset | — | 0.0（:48） | — |
| probe_conditions.min_score | — | 72.0（:26） | — |
| probe_conditions.min_fib_score / min_pa_score | — | 12.0 / 10.0（:27-28） | — |
| probe_conditions.min_rr_net_r | — | 1.3（:29）**live 链不生效** | — |
| probe_conditions.min_rr_score | — | 4.0（:30） | — |
| probe_conditions.elite_* | — | enabled=true, min_score=75, pa≥18, fib≥15, ema≥15, sum≥30（:36-41） | — |
| probe_conditions.high_beta_* | — | pa 12 / rr 5 / cci 9 / ema 12（:42-45） | — |
| probe_conditions.low_score_quality_veto | — | 75 / ema 10 / cci 7（:33-35） | — |
| daily_max_trades_base | 4 | **16**（:5） | 4（:5） |
| min_daily_trades | 1 | **2**（:6） | 未配置 |
| max_symbol_trades_per_day | 1 | **2**（:7） | 1（:6） |
| max_active_symbols | 5 | **8**（:8） | 5（:7） |
| direct_risk_pct | 0.008 | **0.006**（:9） | **0.006**（:8） |
| probe_risk_pct | 0.003 | **0.0015**（:10） | **0.0025**（:9） |
| max_total_exposure_pct | 1.50 | **1.6**（:12） | **1.2**（:10） |
| max_same_direction_exposure_pct | 1.20 | **1.1**（:13） | **0.9**（:11） |
| margin_buffer_pct | 0.20 | **0.30**（:14） | **0.30**（:12） |
| use_ema_architecture | False | **true**（:15） | **true**（:13） |
| use_fib_pa_architecture | False | **true**（:16） | False |
| ema200_gate_mode | "hard" | **"soft"**（:18） | **"soft"**（:14） |
| disable_probe | False | false（:23） | **true**（:19） |
| fib_min_direct_score | 6.0 | **9.0**（:187） | 6.0 |
| rr_min_direct_score | 2.0 | **4.0**（:188） | 2.0 |
| weak_edge_probe_max_score | 85.0 | **82.0**（:163） | 未配置 |
| enable_long_context_discounts | False | False | **true**（:36，倍率 0.70/0.60/0.75/0.80，:37-41） |

**生效阈值（LONG / SHORT）**

| 配置 | LONG direct | LONG probe | LONG watch | SHORT direct | SHORT probe | SHORT watch |
|---|---|---|---|---|---|---|
| 类默认 | 82.0 | 70.0 | 60.0 | 82.0 | 70.0 | 60.0 |
| fib_pa_v1 | **92.0** | **77.0** | **72.0** | 82.0 | 70.0 | 62.0 |
| highest_win | **92.0** | 80.0（disable_probe=true → NO_TRADE） | **70.0** | 82.0 | 70.0（同上） | 60.0 |

### 3.3 双层偏移叠加规则（EC:282-317）

- `_side_threshold_offset`（EC:299-305）：LONG→`long_threshold_offset`，SHORT→`short_threshold_offset`。
- `_probe_threshold_offset`（EC:308-317）：`probe_conditions.enabled=true` 且存在对应键时**替换**（不是相加），否则沿用 side 偏移。
- 应用（EC:287-289）：direct = direct + offset；probe = probe + probe_offset；watch = watch + offset。
- 因此 7.0 与 10.0 **不叠加**：10.0 来自顶层，7.0 来自 `probe_conditions`。LONG probe 实际比 side 偏移低 3 分（77 < 80）。SHORT 两层都是 0。
- 留痕：`SIDE_THRESHOLD_OFFSET_{side}_{offset:.2f}`（EC:284-285），是 HIGH_SCORE_LONG_OFFSET_PROBE 的准入依据（RUN:1368）。

## 4. 权重评分

### 4.1 三档波动权重（仅当两个架构开关都为 false 时生效）

| 组件 | 基础（0.010 ≤ atr% ≤ 0.035）ECS:19-28 | 低波动（atr% < 0.010） | 高波动（atr% > 0.035） |
|---|---|---|---|
| background_4h | 8.0 | 7.314286 | 7.777777 |
| direction_1h | 25.0 | 22.857143 | 24.305556 |
| quality_30m | 22.0 | 20.114286 | 21.388889 |
| trigger_15m | 12.0 | 18.0（固定） | 11.666667 |
| cvd_flow | 18.0 | 18.0（固定） | 10.0（固定） |
| volatility_stop | 10.0 | 9.142857 | 20.0（固定） |
| liquidity_execution | 3.0 | 2.742857 | 2.916667 |
| market_regime | 2.0 | 1.828571 | 1.944444 |
| 合计 | 100.0 | 100.0 | 100.0 |

固定权重表：
- EMA_WEIGHTS（ECS:30-41）：background_4h 5 / direction_1h 18 / quality_30m 12 / trigger_15m 7 / ema_50_quality 15 / ema_momentum 10 / cvd_flow 18 / volatility_stop 10 / liquidity_execution 3 / market_regime 2 = 100。
- FIB_PA_WEIGHTS（ECS:43-50）：trend_ema_context 20 / flow_cvd_confirmation 18 / cci_momentum_quality 14 / price_action_structure 22 / fibonacci_location 18 / risk_reward_geometry 8 = 100。归一化分母（FEAT:108-111）与该表权重一一对应。

`_rescale_weights`（ECS:73-83）：先固定指定组件绝对权重，剩余按 BASE 比例线性缩放，drift 补给剩余键中第一个（background_4h），合计恒 100.000000。

点数：`points[c] = round(clamp(score_c,0,1) × weight_c, 4)`（ECS:86-90，EC:95）；`score = round(Σ points, 4)`（EC:96）。每个组件理论最高点数 = 其权重。

### 4.2 direct / probe 组件最低分

（A）传统路径（`use_fib_pa_architecture=False`，比较归一化分 0–1）：

| 架构 | 检查键 | direct 最低 | probe 最低 | 失败后果 | 行号 |
|---|---|---|---|---|---|
| BASE/EMA | direction_1h | 0.64 | 0.56 | direct→PROBE；probe→WATCH | EC:401-407, 381-389 |
| BASE/EMA | quality_30m | 0.73 | 0.45 | 同上 | 同上 |
| BASE/EMA | trigger_15m | 0.92 | 0.67 | 同上 | 同上 |
| BASE/EMA | cvd_flow | 0.61 | 0.45 | 同上 | 同上 |
| EMA 附加 | ema_200_gate | ==0 且 hard → NO_TRADE | — | NO_TRADE | EC:372-374 |
| EMA 附加 | ema_50_quality | 0.60 | 0.40 | direct→PROBE；probe→WATCH | EC:390-397 |
| 多空覆盖 | `long_*/short_min_*_direct_score` | 默认 None | — | SIDE_COMPONENT_MINIMUMS_* | EC:409-428 |

（B）fib_pa 路径（比较点数）：

| 阶段 | 组件 | 权重 | 最低点数 | 来源 |
|---|---|---|---|---|
| direct | price_action_structure | 22.0 | 6.0 | EC:438-447（CFG:181） |
| direct | fibonacci_location | 18.0 | **9.0**（默认 6.0） | fib_pa_v1:187；EC:445 |
| direct | risk_reward_geometry | 8.0 | **4.0**（默认 2.0） | fib_pa_v1:188；EC:446 |
| probe | trend_ema_context / cci / fib / pa / rr | — | 由 check_probe_conditions 组合判定 | EC:468-474 |

direct 失败 → PROBE（EC:450-452）；probe 失败 → WATCH（EC:483-485）。`probe_conditions.enabled=false` 时 `_apply_fib_pa_probe_minimums` 原样返回（EC:465-467）。

（C）`check_probe_conditions` 判定顺序（EC:513-600，全部点数）：

| # | 判定 | 阈值/条件 | 行号 |
|---|---|---|---|
| 1 | enabled | false → `PROBE_DISABLED` | EC:520-521 |
| 2 | 总分 | `min_score`（fib_pa_v1:26 = 72.0） | EC:523-526 |
| 3 | 结构最低分 | fib≥12.0、pa≥6.0（fib_pa_v1 pa=10.0）；high_beta 用 pa 12/rr 5/cci 9/ema 12 | EC:528-550 |
| 4 | 低分质量否决 | score < 75 且（ema<10 或 cci<7） | EC:552-560 |
| 5 | 趋势或 CCI | ema<10 且 cci<9 → 拒 | EC:562-565 |
| 6 | elite | score≥75 且（(pa≥18 且 fib≥15) 或 (ema≥15 且 pa+fib≥30)） | EC:567-580 |
| 7 | RR | 有 net_tp1_r 用 min_rr_net_r；否则用 min_rr_score(=4.0) | EC:582-599 |

**重要发现**：live 链调用时 `rr_detail=None`（EC:480 硬编码），`min_rr_net_r=1.3` 永不生效，实际生效 `min_rr_score=4.0`。

（D）LONG 上下文折扣（EC:320-343，需 `enable_long_context_discounts=true` 且 LONG）：overextension → quality_30m 与 ema_50_quality ×0.70（CFG:207）；upper_wick → trigger_15m ×0.60（CFG:208）；chase → trigger_15m ×0.75（CFG:209）；cvd 弱 → cvd_flow ×0.80（CFG:210-211）；再 clamp [0,1]（EC:343）。
**重要发现**：被折扣的 4 个键在 fib_pa 权重表中全部不存在，fib_pa 分支也不检查它们 → 对 fib_pa 配置无实际效果；只在 EMA/BASE 架构（highest_win 已开启）真实生效。

### 4.3 五因子影子不参与评分的证据

1. 模块声明 P0 硬约束（src/signals/orthogonal_factors.py:2-6）。
2. `FIVE_FACTOR_WEIGHTS` 自注"仅用于影子展示"（orthogonal_factors.py:54-61）。
3. 唯一入口 `attach_five_factor_shadow` 只写 debug 两键，异常不冒泡（RUN:2537-2562）。
4. 下游只转存（RUN:202-206）。
5. 唯一被读取的数值是 `shadow_total` → `build_gate_features` 的 `shadow_pct`（RUN:1090；entry_gate.py:148-149）；`apply_entry_gates` 在 `entry_gates` 为空时直接返回（RUN:1083-1084），两份配置都未设置 → 当前零决策影响。若将来配置 `entry_gates`，影子分会变成闸门特征（隐患点）。
6. 强制只读测试（tests/test_five_factor_shadow_readonly.py:82, 63, 104, 134）。

## 5. 杠杆与名义仓位

### 5.1 `_select_leverage`（EC:621-642，短路顺序）

| # | 条件 | 杠杆 | 行号 |
|---|---|---|---|
| 1 | action ∉ {PROBE,DIRECT} | 0 | EC:628-629 |
| 2 | `rolling_sharpe_20 < 0` | **2**（ROLLING_SHARPE_LEVERAGE_CAP） | EC:630-632 |
| 3 | `atr_pct > 0.03` | **3** | EC:633-634 |
| 4 | `atr_pct > 0.015` | DIRECT→**4**，PROBE→**3** | EC:635-636 |
| 5 | `score ≥ 90` 且 DIRECT | fib_pa 且 5x 不满足 → **4**；否则 **5** | EC:637-641 |
| 6 | 兜底 | DIRECT→4，PROBE→3 | EC:642 |

`_fib_pa_5x_requirements_met`（EC:645-652）：fibonacci_location ≥ 13/18=0.7222、price_action_structure ≥ 9/22=0.4091、cci ≥ 7/14=0.5、rr ≥ 4/8=0.5（CFG:184-187）。

### 5.2 `_notional_cap_diagnostics` / `_notional_hint`

| 项 | 公式 | 行号 |
|---|---|---|
| stop_pct | `context.stop_pct`；缺失 `clamp(atr×1.5, 0.005, 0.04)` | EC:696-698 |
| raw_notional | `equity × risk_pct / stop_pct` | EC:723-724 |
| leveraged_cap_notional | `equity × max_single_trade_risk_pct(0.0075) / (stop_pct × leverage)` | EC:725-727 |
| remaining_exposure_notional | `max(0, (max_symbol_exposure_pct − symbol_exposure_pct) × equity)` | EC:728-730 |
| final_notional | `min(三者)`，`binding_cap` = 对应键名 | EC:746-747 |

`_decision` 二次封顶（EC:783-794）；action 非 PROBE/DIRECT 返回全 0（EC:677-686）。
算例：equity=10000、stop=0.03、DIRECT leverage=4、ETH 敞口上限 0.30：raw=2000；leveraged_cap=625；remaining=3000 → final=625，binding_cap=`leveraged_cap_notional`。

### 5.3 dry-run 的额外决策改写

`apply_dry_run_decision_controls`（RUN:2017-2044）：observation_only、post-initial-stop 冷却、rolling 冷却、组合连续止损熔断、组合日亏熔断、弱边际降级 → 命中即整体降 WATCH 并清零 leverage/notional（RUN:2088-2097）。q1_trend_launch 强制 leverage=1（RUN:931-933）。

## 6. 上篇不确定项

1. "线上主用配置"冲突：两份 systemd service 的 ExecStart 都指向 `configs/entry_chain.dry_run_highest_win.json`，而本地分析默认 `dry_run_fib_pa_v1.json`。倾向：VPS=highest_win，本地分析=fib_pa_v1。
2. fib/pa/cci 三个打分函数内部分档未展开（src/signals/fib_location.py、pa_structure.py、cci_quality.py）。
3. BOLL 与真实 CVD 在 live 链不参与打分（market_regime 是常量 0.8，cvd_flow 是涨跌符号成交量近似）。
4. `max_active_probes`、`dry_run_q1_green_channel_*`、`min_rr_net_r` 为死配置/不生效。
5. exit/组合状态机/scout 仓位属任务 #2 范围。
6. `apply_dry_run_decision_controls` 只在 dry-run 脚本内，src/ 下无等价实现。
7. `probe_conditions.enabled=false` 时 probe 偏移回退为 side offset（highest_win 的 LONG probe 门为 80，但 disable_probe=true 无观察效果）。

---

# 仓位管理与风控审计

> **头号结论（架构事实）**：`src/risk/` 下 6 个模块中，**只有 `net_beta_exposure_model` 与 `stress_simulator` 被 live 干跑链引用**（RUN:27-32），且二者都是**纯观测**。`position_sizer` / `risk_engine` / `exit_engine` / `stop_engine` / `portfolio_guard` / `cooldown_guard` **不在 live 链上**——引用它们的只有 `scripts/describe_*.py`、`tests/` 与 `scripts/scaffold_ai300_framework.py`。线上真实的仓位、止损、出场、熔断全部在 `entry_chain.py` + `paper_trading.py` + `run_live_dry_run.py` 里实现。

## 7. 仓位计算（两条互不相通的路径）

### 7.1 live 真链路：notional_hint → quantity

| 步 | 逻辑 | 行号 |
|---|---|---|
| 1 | `notional_hint` = min(raw_notional, leveraged_cap_notional, remaining_exposure_notional) | EC:669-754 |
| 2 | `quantity = decision.notional_hint / price` | LEA:46 |
| 3 | action ∉ {PROBE,DIRECT} 或 risk_allowed=False → 拒；price≤0 → 拒；quantity ≤ 0 或 < min_quantity → 拒 | LEA:37-48 |
| 4 | `min_quantity` 默认 **0.0**（LEA:34），RUN 未传（RUN:312-320）→ **不校验交易所最小下单量** | LEA:34,46-48 |
| 5 | 单类型 MARKET，reduce_only=False | LEA:51-65 |
| 6 | 账本 `notional = price × quantity`、`leverage = int(leverage or 1)` | PT:208, 217 |
| 7 | 建仓即计成本：`-(fee + slippage)`，各 5bps；`realized_margin_pnl` 再 ×leverage | PT:13-14, 223-226 |
| 8 | 保证金占用 `notional / leverage`；`available_margin = 0.8×initial_equity − Σ(notional×remaining/leverage)` | PT:838-839；RUN:2055, 2968-2969 |

### 7.2 `src/risk/position_sizer.py`（离线规格，未接线）

| 项 | 取值/公式 | 行号 |
|---|---|---|
| DIRECT / PROBE 乘数 | 1.0 / 0.25 | PS:7 |
| 市值分层乘数 | A 2.0 / B 1.0 / C 0.75 | PS:9 |
| 波动乘数 | NORMAL 1.0 / HIGH 0.5 / EXTREME 0.0 | PS:10, 250-269 |
| 风险金额 | `equity × risk_pct` | PS:211 |
| 标准名义 | `risk_amount / stop_pct` | PS:212 |
| 原始名义 | `standard × sig × tier × account_risk_factor × portfolio_risk_factor × vol` | PS:215-222 |
| 数量取整 | 向下取整到 `quantity_step` | PS:196-200, 224 |
| NO_TRADE 门 | 7 条（entry_mode/数据质量/状态机/冷却/leverage 未设/>max_leverage(5.0)/持仓数≥5） | PS:501-516 |
| 最小名义/保证金 | 不足拒单而非放大；`> available_margin` 拒 | PS:150-153, 271-353 |
| 敞口四道 | total、symbol 0.20、side 0.75、correlation group 0.50 | PS:92-99, 354-435 |

### 7.3 `risk_engine.py` 默认风控限额（离线规格）

`DEFAULT_RISK_LIMITS`（RE:102-114）：日亏 5%、周亏 12%、最大回撤 20%、单符号敞口 20%、组合敞口 75%、最大持仓 5、单笔风险 1%、最小止损 0.5%、最大止损 8%、ATR 倍数 1.5、常规冷却 4 bar。
阻断顺序（RE:194-220）；软风险等级（RE:478-518）；仓位因子（RE:521-529）：EXTREME/BLOCKED→0，HIGH→0.25，DIRECT+LOW→1.0。

## 8. 风险预算与敞口上限（live 生效值）

| 概念 | 类默认 | fib_pa_v1 | highest_win | 实现位置 |
|---|---|---|---|---|
| 单笔风险 DIRECT | 0.008 | **0.006** | **0.006** | EC:723 |
| 单笔风险 PROBE | 0.003 | **0.0015** | **0.0025** | EC:723 |
| 单笔硬上限 | 0.0075 | 0.0075 | 0.0075 | EC:725-727 |
| 组合总敞口 | 1.50 | **1.6** | **1.2** | GATE:60 |
| 同向敞口 | 1.20 | **1.1** | **0.9** | GATE:62 |
| 单符号：大市值/主流/高beta | 0.30/0.20/0.10 | 同默认 | 同默认 | GATE:90-98 |
| 保证金缓冲 | 0.20 | **0.30** | **0.30** | GATE:64 |
| 最大同时持仓 | 5 | **8** | 5 | GATE:52 |
| 单符号日交易数 | 1 | **2** | 1 | GATE:56 |
| 日内总交易数 | 4×波动比 | **16×波动比**，下限 **2** | 4×波动比 | GATE:73-79 |
| `base_direct_exposure_pct` | 0.20 | 未覆盖 | 未覆盖 | 仅定义，live 未见消费 |

敞口分母口径：`get_portfolio_state_snapshot` 的敞口与当日收益一律以 `initial_equity` 为分母（PT:561-563, 592），RUN 再按 `exposure_scale = initial_equity / current_equity` 放大（RUN:2073-2083）→ 盈利后更保守、亏损后更宽松。

## 9. 止损 / 止盈 / 出场（`paper_trading.py` 真实现）

### 9.1 常量（PT:12-22）

`INITIAL_EQUITY=10000`、`FEE_BPS=5`、`SLIPPAGE_BPS=5`、`ATR_STOP_MULT=1.5`、`MIN_STOP_PCT=0.005`、`MAX_STOP_PCT=0.03`、`MAX_HOLD_BARS=32`、`COST_BREAKEVEN_CHECK_BARS=8`、`COST_BREAKEVEN_BUFFER_MULT=0.5`、`TP_LEVELS=(1.2,2.0,3.0)`、`TP_FRACTIONS=(0.40,0.35,0.25)`。
`MAX_STOP_PCT=0.03` 只是 dataclass 默认，运行时被 `PaperExitConfig(min_stop_pct=config.min_stop_pct, max_stop_pct=config.max_stop_pct)` 覆盖为 0.005/0.04（RUN:555-570）→ 建仓与出场止损口径一致（PT:32-38 注释记录了历史 3% vs 4% bug）。

### 9.2 止损宽度解析（PT:25-56）

1. `decision_payload["stop_pct"]`（live 链不产出）；
2. `metadata.risk_budget.stop_pct`（**实际命中**，来源 EC:751）；
3. 兜底 `atr_pct × 1.5`，clamp `[min,max]`；atr 缺失用 0.01（PT:55）。

### 9.3 建仓价格结构（PT:202-219）

`risk_distance = price × stop_pct`；`stop_price = price ∓ risk_distance`；`tp_prices = price ± risk_distance × {1.2, 2.0, 3.0}`。

### 9.4 出场判定顺序（PT:287-351）

| # | 触发 | 动作 | 行号 |
|---|---|---|---|
| 0 | 时间戳不新于 entry / last_processed | 跳过（幂等） | PT:294-295 |
| 1 | 更新 best_price / MFE-R | — | PT:298-299, 722-734 |
| 2 | 早保本（试点）：MFE ≥ trigger(默认 1.0) 且未 TP → 止损移保本 | 改 stop | PT:300, 786-804 |
| 3 | 已有 TP 成交 → `_apply_post_tp_stop` | 改 stop | PT:301-302 |
| 4 | 止损被 high/low 穿越 | 全平 `INITIAL_STOP_HIT` / `BREAKEVEN_STOP_HIT` | PT:306-310 |
| 5 | Q2 → 止损抬保本；Q4 streak≥2 且净亏 → 全平 `Q4_DEFENSIVE_EXIT` | 改 stop / 平仓 | PT:312-318 |
| 6 | Q3 首次 → 减 50% `Q3_DEFENSIVE_REDUCE` | 减仓 | PT:319-326 |
| 7 | TP 命中（命中即 break）→ 按 40%/35%/25% 减仓 `TP{n}_HIT`；TP1 后止损移保本 | 减仓 | PT:327-340 |
| 8 | 剩余为 0 → 移出持仓 | — | PT:341-342 |
| 9 | `COST_BREAKEVEN_TIMEOUT`：hold≥8 且从未 TP 且 gross < 0.5×往返成本 | 全平 | PT:343-346, 705-719 |
| 10 | `MAX_HOLD_EXIT`：hold ≥ 32 bar（8 小时） | 全平 | PT:347-350 |

第 5/6 步前置条件：`position.experiment_id` 非空（PT:748, 761, 771）→ 只有实验通道仓位（q1_trend_launch / scout_micro / mirror）享象限防御，主 PROBE/DIRECT 仓位不享受。

### 9.5 止盈后止损（PT:807-825）

非 trend_capture → 一律移保本。trend_capture：MFE-R < 1.5 → 保本；否则按 `best_price ∓ risk_distance × 1.0` 追踪，只收紧不放宽。保本价 = `entry × (1.001/0.999)`（PT:828-829，10bps 缓冲）。

### 9.6 成本口径（PT:362-420）

每次减仓独立计 fee + slippage 各 5bps；`net = gross − fees`；`margin_net = net × max(1,leverage)`；`cost_source="constant_assumption"`。往返约 0.2% 名义。

### 9.7 出场模式来源

`paper_exit_config()`（RUN:555-570）：主账本 `paper_exit_mode`（默认 legacy；fib_pa_v1 legacy）、`paper_exit_trend_trigger_r=1.5`、`paper_exit_trailing_r_mult=1.0`；scout 账本 `scout_micro_exit_mode`（fib_pa_v1 = **trend_capture**）。AB 账本强制 legacy vs trend_capture 双跑（RUN:573-580）。

## 10. 组合敞口、净 beta、冷却与熔断

### 10.1 组合快照（PT:556-594）

symbol_exposure_pct = `notional × remaining_fraction / initial_equity`（PT:563）；total 为各符号求和（不做多空净额，PT:587）；same_direction 按方向累加（PT:565-568）；`portfolio_trades_today` 按天统计 `PAPER_OPEN`（PT:570-591）；`daily_profit_pct = realized_pnl / initial_equity`（PT:592）。

### 10.2 净 beta（仅观测）

`STATIC_BTC_BETA`：BTC 1.00 / ETH 1.05 / BNB 0.90 / SOL 1.25 / ADA 1.20 / LINK 1.15 / DOGE 1.30 / XRP 1.10 / TRX 0.85 / BCH 1.10 / XLM 1.15 / XMR 0.75 / ZEC 1.35 / TON 1.05 / HYPE 1.80 / LAB 1.80 / CC 1.80；未知 1.20（NBE:7-26）。净 beta = `Σ signed × beta × notional × remaining / equity`（NBE:45）；`NET_BETA_EXPOSURE_CAP_PCT=0.50`、`static_v1_observation_only`（NBE:27-28）。RUN:808-823 只写 summary；`net_beta_exposure_within_limit`（NBE:49-50）**未调用**。

### 10.3 冷却与熔断（全部在 RUN，命中即整体降 WATCH）

| 机制 | 条件 | fib_pa_v1 | 行号 |
|---|---|---|---|
| 单符号止损后冷却 | 该符号 4h 内出现过 `INITIAL_STOP_HIT` | 开，4h | RUN:2101-2119 |
| 滚动冷却 | 48h 内止损 ≥2 → 冷却 24h | 开，2/48/24 | RUN:2122-2141 |
| 组合连续止损熔断 | 最近 N 笔全为 `INITIAL_STOP_HIT` → H 小时禁新单 | 开，2 次/2h | RUN:2144-2160 |
| 组合日亏熔断 | 当日 Σ`position_realized_pnl` ≤ 阈值 | 开，−30 | RUN:2163-2174 |
| 实验 war-fund / 日亏熔断 | 仅统计 experiment_id 匹配：累计 ≤−150 或当日 ≤−200 | 同 | RUN:1670-1683 |
| scout 冷却 | 同向 2h；止损后 6h | 同 | RUN:1418-1438 |
| scout mission 熔断 | 同 mission 连续 3 次止损 → 停 12h | 开 | RUN:1441-1462 |
| 弱边际降级 | DIRECT 82–85 / PROBE 77–82（probe 上限 82）且该符号无盈利史 → WATCH | 82-85 / 77-82 | RUN:2177-2202 |

降级实现 `_cap_decision_to_watch`：action=WATCH、side=NONE、risk_allowed=False、leverage=0、notional_hint=0（RUN:2088-2097）。

### 10.4 未被使用的守卫

`portfolio_guard.exposure_allowed`、`cooldown_guard.is_cooldown_active` 仅定义无调用，功能被 GATE:60-61 / GATE:58-59 取代。

## 11. 压力测试（纯观测，不阻断）

`estimate_stress_loss_pct = exposure_pct × leverage × adverse_move_pct`（SS:4-5）；超过 max 给 `action="BLOCK"`（SS:8-23）。live 调用传 `exposure_pct = decision.max_symbol_exposure_pct`（**符号敞口上限，不是本笔名义/权益**）、leverage、adverse 0.20、max_loss 0.25（RUN:303-308, 432-433）。结果只写 summary / draft / 日志（RUN:310, 322, 3007-3008），**没有代码读 `stress["action"]` 决定下单**。例：BTC 0.30×4×0.20=0.24<0.25 ALLOW；杠杆 5 → 0.30>0.25 BLOCK，但 BLOCK 不阻止成交。

## 12. 未覆盖项

1. `src/risk/position_sizer.py`、`risk_engine.py`、`exit_engine.py`、`stop_engine.py` 是否有接线计划未知；文档不可写成"线上风控层"。
2. `exit_engine.plan_take_profit_actions` 默认 (1.0/2.0/3.0)、(0.30/0.40/0.30) 与 paper_trading 的 (1.2/2.0/3.0)、(0.40/0.35/0.25) 不一致，且 live 未使用。
3. `stop_engine.atr_stop` 不做 clamp，live 侧 clamp 到 [0.005,0.04]。
4. `max_symbol_trades_per_day` 计数来自各账本 `PAPER_OPEN`，跨账本是否合并未逐一核对。
5. `cooldown_until_ts` 在 `apply_paper_state_to_context` 中未见显式赋值（RUN:2075-2085）→ 硬闸门 `SYMBOL_COOLDOWN_ACTIVE` 在 dry-run 中可能恒不触发，冷却实际由 10.3 的 RUN 侧函数承担，建议复核。
6. 未覆盖：scout mission 仓位细节（50 USDT / 1x，高beta 五折，RUN:1758-1778）、mirror_ab shadow、fee_model、paper_ab 自动切换。

---

# 补充包：约束矩阵 / 风控模块分工 / 出场配置对照 / 调用点证据

## A.1 调用点证据：`src/risk/*` 与 live 链的接线情况

`run_live_dry_run.py` 从 `src.risk` 只 import 两个模块（RUN:27-32）：`net_beta_exposure_model`（3 个符号）与 `stress_simulator.stress_decision`。

| 模块 / 函数 | 生产调用点 | 其它调用点 | 是否在 live 链 |
|---|---|---|---|
| `position_sizer.calculate_position_size` 等 9 个导出符号 | **无** | scripts/describe_position_sizing.py、tests/、scaffold | ❌ |
| `risk_engine.evaluate_risk` 等 8 个导出符号 | **无** | scripts/describe_risk_engine.py、tests/ | ❌ |
| `exit_engine.EXIT_PRIORITY` 等 | **无**（仅被 risk_engine 内部调用：RE:227-234, 384） | scripts/describe_risk_exit_rules.py | ❌ |
| `stop_engine.initial_atr_stop` | **无**（仅被 risk_engine 内部调用：RE:435） | tests/test_risk_exit_engine.py | ❌ |
| `portfolio_guard.exposure_allowed` | **无** | 无 | ❌ |
| `cooldown_guard.is_cooldown_active` | **无** | 无 | ❌ |
| `compute_net_beta_exposure` | RUN:808 | tests/ | ✅（仅记录） |
| `stress_decision` | RUN:303 | tests/ | ✅（仅记录） |

另一条关键事实：RUN **直接 import 了 entry_chain 的私有函数** `_notional_cap_diagnostics`（RUN:33），并在 3 处调用它做仓位上限计算（RUN:891 q1_trend_launch、1769 scout_micro、1879 mirror_ab）→ **entry_chain 是唯一仓位来源**，不存在"两套并行生效"的实现；`position_sizer` 只是文档级规格。

## A.3 三层约束矩阵

| 约束 | 生效值 | 生效层 | 位置 | 失败后果 |
|---|---|---|---|---|
| 单笔风险 direct/probe risk_pct | 0.006 / 0.0015（fib_pa_v1:9-10）；默认 0.008/0.003 | entry_chain：算 `raw_notional` | EC:723-724 | 不阻断，只决定名义上限 |
| max_single_trade_risk_pct | 0.0075（CFG:221） | entry_chain：`leveraged_cap_notional` | EC:725-727 | 不阻断，压名义（多数情况下是绑定项） |
| 单符号敞口 cap | 0.30 / 0.20 / 0.10 | entry_chain 两处：remaining min + 硬闸门 | EC:728-730；EC:180-181 | NO_TRADE(`SYMBOL_EXPOSURE_CAP`) |
| 组合总敞口 | 1.6（fib_pa_v1）/ 1.2（highest_win）；默认 1.50 | 硬闸门 | GATE:60-61 → EC:112-114 | NO_TRADE(`TOTAL_EXPOSURE_CAP`) |
| 同向敞口 | 1.1 / 0.9；默认 1.20 | 硬闸门 | GATE:62-63 | NO_TRADE(`SAME_DIRECTION_EXPOSURE_CAP`) |
| 保证金缓冲 | 0.30（两配置）/ 0.20 | 硬闸门，比较 `available_margin` | GATE:64-65 | NO_TRADE(`MARGIN_BUFFER_TOO_LOW`) |
| available_margin 来源 | `0.8×initial_equity − Σ(notional×remaining/leverage)` | dry-run 侧覆写 context | RUN:2055, 2968-2969 | 决定上一行是否触发 |
| 最大同时持仓 | 8 / 5 | 硬闸门 | GATE:52-53 | NO_TRADE(`MAX_ACTIVE_SYMBOLS`) |
| 单符号日交易数 | 2 / 1 | 硬闸门（计数来自 paper 快照） | GATE:56-57；PT:570-582 | NO_TRADE(`SYMBOL_DAILY_TRADE_BUDGET_USED`) |
| 日内总交易数 | 16 / 4 倍波动比，下限 2 / 1 | 硬闸门 | GATE:73-79 | NO_TRADE(`DAILY_TRADE_BUDGET_USED`) |
| 组合级冷却/熔断/弱边际 | 见第 10.3 节 | dry-run controls（entry_chain 之外） | RUN:2017-2044 | 整体降 WATCH + leverage/notional 清零（RUN:2088-2097） |
| 持仓时长 / 成本保本 / TP 节奏 | 32 bar / 8 bar / 1.2-2-3R | paper ledger（与入场决策解耦） | PT:18-22 | 平仓或减仓 |

一句话：**入场前**所有约束在 entry_chain（纯计算 + 硬闸门）；**入场事件的最终否决**在 dry-run controls；**入场之后**的一切在 paper ledger。

## B.4 `risk_engine` / `stop_engine` / `exit_engine` 分工（均为离线规格）

`evaluate_risk`（RE:188-282）返回 `RiskResult`（RE:165-185），字段：`allow_trade / allow_add / allow_reduce / allow_exit / risk_level / risk_reason / risk_score / position_size_factor / stop_distance / stop_pct / take_profit_plan / cooldown_required / cooldown_bars / portfolio_blocked / metrics_snapshot / metadata`。

| 能力 | 归属 | 规则 | 行号 |
|---|---|---|---|
| 初始止损 | stop_engine | `entry ∓ atr × 1.5`；`ctx.stop_pct>0` 优先 | stop_engine.py:14-33；RE:432-437 |
| 止损合法性 | risk_engine | ATR 缺失 / stop_pct≤0 / <0.005 / >0.08 → 阻断 | RE:466-475 |
| 止盈计划 | exit_engine | R 档 (1.0, 2.0, 3.0)，比例 (0.30, 0.40, 0.30) | exit_engine.py:42-69；RE:374-385 |
| 移动止损 | exit_engine | `structure×(1∓buffer)`，只在更优时返回 | exit_engine.py:87-106 |
| 强制退出 | exit_engine | stop_hit / portfolio_risk / direction_reversal / volatility_anomaly(减 50%) | exit_engine.py:109-124 |
| 退出优先级 | exit_engine | FORCED_STOP > PORTFOLIO_RISK > DIRECTION_REVERSAL > VOLATILITY_ANOMALY > TRAILING_STOP > PARTIAL_TAKE_PROFIT | exit_engine.py:16-23 |
| 强制执行判定 | risk_engine | `portfolio_exposure ≥ 0.75×0.95` 或 volatility EXTREME 或 stop_hit 或 direction_reversal → `FORCED_EXIT_REQUIRED`，`position_size_factor=0` | RE:226-252 |
| 时间止损 | — | 三者都没有；真正的时间止损是 paper 的 `MAX_HOLD_BARS=32` | PT:18 |
| 冷却时长 | risk_engine | `cooldown_bars=4` | RE:419；exit_engine.py:127-130 |

## B.8 出场/风控配置对照（两份 dry-run 配置 vs 类默认）

| 字段 | 类默认 | fib_pa_v1 | highest_win | 消费点 |
|---|---|---|---|---|
| `paper_exit_mode` | legacy（:161） | legacy（:154） | 未配置 → legacy | RUN:565 |
| `paper_exit_trend_trigger_r` | 1.5（:162） | 1.5（:155） | 未配置 | RUN:566 → PT:816 |
| `paper_exit_trailing_r_mult` | 1.0（:163） | 1.0（:156） | 未配置 | RUN:567 → PT:819 |
| `scout_micro_exit_mode` | legacy（:164） | **trend_capture**（:157） | 未配置 | RUN:558 |
| `scout_micro_exit_trend_trigger_r` | 1.5（:165） | 1.5（:158） | 未配置 | RUN:559 |
| `scout_micro_exit_trailing_r_mult` | 1.0（:166） | 1.0（:159） | 未配置 | RUN:560 |
| `min_stop_pct` / `max_stop_pct` | 0.005 / 0.04（:58-59） | 未覆盖 | 未覆盖 | RUN:561-562,568-569 → PT:50/55 |
| `mirror_ab_payoff_pilot_enabled` | False（:126） | **True**（:114） | 未配置 | RUN:585-588 |
| `mirror_ab_payoff_early_breakeven_trigger_r` | 1.0（:127） | 1.0（:115） | 未配置 | RUN:588 |
| `mirror_ab_payoff_trend_trigger_r` | 1.2（:128） | 1.2（:116） | 未配置 | RUN:585 |
| `scout_micro_mission_stop_circuit_*` | 关 / 3 / 12h | **开 / 3 / 12h**（:143-145） | 未配置 | RUN:1441-1462 |
| `post_initial_stop_cooldown_*` | 关 / 4h | **开 / 4h**（:168-169） | 未配置 | RUN:2101-2119 |
| `rolling_symbol_cooldown_*` | 关 / 2 / 48h / 24h | **开**（:164-167） | **开**（:30-33） | RUN:2122-2141 |
| `portfolio_stop_circuit_*` | 关 / 3 / 4h | **开 / 2 / 2h**（:170-172） | 未配置 | RUN:2144-2160 |
| `portfolio_daily_loss_circuit_*` | 关 / −30 | **开 / −30**（:173-174） | 未配置 | RUN:2163-2174 |
| `experiment_war_fund_loss_limit` / `experiment_daily_loss_limit` | −150 / −200 | −150 / −200（:139-140） | 未配置 | RUN:1670-1683 |
| `scout_micro_same_side_cooldown_hours` / `initial_stop` | 2 / 6 | 2 / 6（:141-142） | 未配置 | RUN:1418-1438 |
| `scout_micro_allow_degraded_data` | False | **True**（:146） | 未配置 | scout 准入 |
| `weak_edge_direct_*` / `weak_edge_probe_*` | 82–85 / 77–85 | 82–85 / **77–82**（:163） | 无覆盖 | RUN:2177-2202 |
| **max_hold_bars** | **硬编码 32，不可配置** | 32 | 32 | PT:18, 347-350 |
| **成本保本** | **硬编码 8 bar + buffer 0.5** | 同 | 同 | PT:19-20, 705-719 |

**修正**：早保本（`early_breakeven_enabled`）不是"永不启用"。主账本恒 False（RUN:555-570 未传该字段），但 **AB 研究账本的 trend_capture 分支**用 `config.mirror_ab_payoff_pilot_enabled` 打开它（RUN:583-589）；fib_pa_v1:114 = true → 该研究账本对每笔走到 1.0R（:115）的仓位把止损移到保本。主账本不受影响。

## 增补未覆盖项

1. `max_hold_bars` 与成本保本阈值是硬编码常量，两配置均无法覆盖；文档不可写"可通过配置调持仓时长"。
2. `risk_engine.take_profit_plan` 用 1.0/2.0/3.0 + 30/40/30%，与线上 paper 的 1.2/2.0/3.0 + 40/35/25% 不一致（规格 vs 实现第二处数值分叉，第一处是 stop 上限 0.08 vs 0.04）。
3. `portfolio_guard` / `cooldown_guard` 全仓 0 调用点，语义被 GATE 取代。
4. `_experimental_risk_context`（RUN:1700-1744）与 `_q1_risk_context_from_near_miss`（RUN:938-965）手工重建 EntryChainContext，且把 `available_margin` 直接设为 `current_equity`（RUN:1741、959）→ scout/q1 通道的保证金缓冲闸门比主账本宽松（不做 0.8 折算）。是否有意无法从代码判断。
5. 未核对：`decision_audit.py` 对 stress/net_beta 字段的落盘结构、`dry_run_summary` 聚合口径。
