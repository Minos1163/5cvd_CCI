# 2026-06-27 23:30 CST 至 2026-06-29 19:00 CST 日志亏损归因与开仓链路评审稿

> 目的：供 DeepSeek 评审当前 AI300 dry-run / live-entry-chain 机制。本文只分析日志与代码，不修改策略、实盘执行或生产配置。

## 1. 分析范围与结论摘要

- 时间窗：北京时间 `2026-06-27 23:30` 至日志最新 `2026-06-29 19:00`，约 `43.5` 小时。
- 对应 UTC：`2026-06-27 15:30` 至 `2026-06-29 11:00`。
- 主证据：
  - `logs/2026-06/2026-06-27/paper_trades.jsonl`
  - `logs/2026-06/2026-06-28/paper_trades.jsonl`
  - `logs/2026-06/2026-06-29/paper_trades.jsonl`
  - `logs/2026-06/2026-06-28/decisions.jsonl`
  - `logs/2026-06/2026-06-29/decisions.jsonl`
  - `logs/2026-06/2026-06-29/paper_summary.json`
  - `logs/2026-06/2026-06-29/runtime.out.06.log`
- 当前运行配置：日志 runtime header 显示 `config=configs/entry_chain.dry_run_fib_pa_v1.json`，`target_tier=aggressive`，`market_data_source=public-binance`。
- 安全状态：本窗口是 dry-run，`exchange_mutation_enabled=False`，`orders_submitted=0`，没有真实交易所下单。

窗口内共 `7` 笔完整纸交易，`3` 胜 `4` 负，胜率 `42.86%`，净收益 `-6.0446 USDT`，利润因子 `0.8236`。表面看亏损不大，但结构很明确：平仓前 gross PnL 合计 `+4.1287 USDT`，手续费加滑点合计 `10.1733 USDT`，成本把毛盈利反转为净亏损。也就是说，本窗口的第一归因不是“方向全错”，而是弱边缘交易和小 R 退出不足以覆盖往返成本；其次才是 3 笔初始止损造成的方向/入场质量亏损。

累计账本在 `2026-06-29 19:00 CST` 附近显示：权益 `9838.26`，累计 realized notional PnL `-161.7364`，累计 return `-1.6174%`，累计 trade_count `46`，累计 win_rate `50.00%`，累计 profit_factor `0.6879`，max_drawdown `3.5095%`。累计指标不是本 43 小时窗口独有，但说明系统整体仍处在负期望状态。

## 2. 本窗口交易明细

| 开仓 CST | 平仓 CST | 标的 | 方向 | 动作来源 | 分数 | 杠杆 | 名义本金 | 净 PnL | 毛 PnL | 成本 | 退出原因 | 持仓 |
|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| 06-28 03:15 | 06-28 06:30 | HYPEUSDT | SHORT | PROBE | 82.09 | 3x | 492.22 | +1.6006 | +2.5825 | 0.9818 | BREAKEVEN_STOP_HIT | 3.25h |
| 06-28 07:45 | 06-28 11:45 | HYPEUSDT | SHORT | PROBE | 84.15 | 3x | 492.30 | -5.7119 | -4.7226 | 0.9893 | INITIAL_STOP_HIT | 4.00h |
| 06-28 07:45 | 06-28 09:30 | LABUSDT | LONG | PROBE | 82.7229 | 3x | 492.27 | +25.1070 | +26.1176 | 1.0107 | TP3_HIT | 1.75h |
| 06-28 09:00 | 06-28 17:00 | BNBUSDT | SHORT | DIRECT | 83.59 | 4x | 2126.88 | -5.5913 | -1.3362 | 4.2551 | MAX_HOLD_EXIT | 8.00h |
| 06-28 09:45 | 06-28 10:00 | LABUSDT | LONG | PROBE | 77.75 | 3x | 493.42 | -15.7746 | -14.8026 | 0.9720 | INITIAL_STOP_HIT | 0.25h |
| 06-29 08:45 | 06-29 10:00 | SOLUSDT | LONG | PROBE | 82.80 | 3x | 492.20 | -7.1833 | -6.2051 | 0.9782 | INITIAL_STOP_HIT | 1.25h |
| 06-29 10:30 | 06-29 18:30 | LINKUSDT | LONG | PROBE | 86.30 | 3x | 491.84 | +1.5088 | +2.4949 | 0.9862 | MAX_HOLD_EXIT | 8.00h |

按退出原因聚合：

| 退出原因 | 笔数 | 净 PnL | 毛 PnL | 成本 | 归因 |
|---|---:|---:|---:|---:|---|
| INITIAL_STOP_HIT | 3 | -28.6698 | -25.7302 | 2.9395 | 主要亏损源，入场后立即逆向或止损距离/触发质量不足 |
| MAX_HOLD_EXIT | 2 | -4.0825 | +1.1588 | 5.2413 | 小额毛盈利被费用滑点吞掉，或持有到期仍无足够波幅 |
| BREAKEVEN_STOP_HIT | 1 | +1.6006 | +2.5825 | 0.9818 | 保本止损保护有效，但净利润很薄 |
| TP3_HIT | 1 | +25.1070 | +26.1176 | 1.0107 | 唯一完整趋势延伸盈利，抵消多数亏损 |

按方向聚合：

| 方向 | 笔数 | 净 PnL | 胜 | 负 |
|---|---:|---:|---:|---:|
| LONG | 4 | +3.6579 | 2 | 2 |
| SHORT | 3 | -9.7025 | 1 | 2 |

按标的聚合：

| 标的 | 笔数 | 净 PnL | 胜 | 负 | 均分 |
|---|---:|---:|---:|---:|---:|
| BNBUSDT | 1 | -5.5913 | 0 | 1 | 83.59 |
| HYPEUSDT | 2 | -4.1112 | 1 | 1 | 83.12 |
| LABUSDT | 2 | +9.3324 | 1 | 1 | 80.24 |
| LINKUSDT | 1 | +1.5088 | 1 | 0 | 86.30 |
| SOLUSDT | 1 | -7.1833 | 0 | 1 | 82.80 |

## 3. 亏损结果归因

### 3.1 一级归因：交易毛利不足以覆盖成本

窗口内总毛 PnL 为 `+4.1287 USDT`，但总费用加滑点为 `10.1733 USDT`，净 PnL 因而变成 `-6.0446 USDT`。成本模型来自 `src/observability/paper_trading.py`：`FEE_BPS=5.0`，`SLIPPAGE_BPS=5.0`，开仓先扣一次费用和滑点，平仓/减仓再扣一次费用和滑点。

小额盈利问题最明显的是：

- `LINKUSDT LONG`：毛利 `+2.4949`，成本 `0.9862`，净利只剩 `+1.5088`，持仓 `8h` 后 MAX_HOLD_EXIT，收益/时间效率很低。
- `HYPEUSDT SHORT` 第一笔：毛利 `+2.5825`，成本 `0.9818`，净利 `+1.6006`，属于保本保护后的薄利。
- `BNBUSDT SHORT`：毛 PnL 已经接近持平但略负 `-1.3362`，由于名义本金 `2126.88` 且 4x，成本 `4.2551`，最终净亏 `-5.5913`。

结论：当前 TP/BE/MAX_HOLD 机制允许太多“接近持平或小幅盈利”的交易进入最终结算，但这些交易在当前 `5bps fee + 5bps slippage` 单边成本模型下无法覆盖往返成本。仅靠胜率 `42.86%` 或累计 `50%` 胜率不足以盈利，必须提高平均盈利幅度、降低交易成本假设、减少弱边缘开仓，或改进退出逻辑。

### 3.2 二级归因：PROBE 通道放行边缘交易

本窗口 7 笔开仓中 `6` 笔是 PROBE，只有 `1` 笔 DIRECT。PROBE 名义本金约 `492 USDT`，DIRECT 名义本金约 `2127 USDT`。PROBE 本应是试仓，但本窗口的亏损集中发生在 PROBE：

- HYPEUSDT PROBE：一胜一负，合计 `-4.1112`。
- LABUSDT PROBE：一大胜一快止损，合计 `+9.3324`，但第二笔 `score=77.75`，15 分钟初始止损。
- SOLUSDT PROBE：`score=82.80`，初始止损 `-7.1833`。
- LINKUSDT PROBE：盈利很薄，8 小时 MAX_HOLD_EXIT。

关键机制：`configs/entry_chain.dry_run_fib_pa_v1.json` 中 `probe_conditions.enabled=true`，`min_score=72`，多头 probe offset 为 `7`，直接导致多头 score 只要高于 `77` 且满足 fib/pa/rr 最低要求就可能进入 PROBE。典型证据是 `LABUSDT LONG score=77.75`：虽然多头 DIRECT 阈值是 `92`，但它仍通过 PROBE 条件开仓，15 分钟后 `INITIAL_STOP_HIT`，净亏 `-15.7746`。

### 3.3 三级归因：DIRECT 阈值不等于高质量直开

唯一 DIRECT 是 `BNBUSDT SHORT score=83.59`。它通过了 DIRECT，但分数组成显示：

- `risk_reward_geometry = 2.0 / 8`
- `cci_momentum_quality = 7.0 / 14`
- `trend_ema_context = 17.59 / 20`
- `fibonacci_location = 18 / 18`
- `price_action_structure = 21 / 22`
- `flow_cvd_confirmation = 18 / 18`

也就是说，BNB 的总分主要来自趋势、Fib、PA、CVD，但风险收益几何只刚好达到 DIRECT 最低线 `rr_min_direct_score=2.0`。这笔最终 `MAX_HOLD_EXIT`，毛亏 `-1.3362`，成本 `4.2551`，净亏 `-5.5913`。问题不是“分数低于阈值”，而是总分可由若干强项堆高，导致 RR 几何弱项仅过最低线也能直开较大仓位。

### 3.4 四级归因：多头长上下文折扣没有阻断部分追涨/过热风险

`LABUSDT LONG score=82.7229` 的入场上下文显示：

- `long_chase_risk_active=True`
- `long_low_liquidity_session_active=True`
- `long_overextension_active=True`
- `stop_pct=0.02749`
- 仍然开 PROBE，并最终 TP3 盈利。

这说明折扣不是总能阻断风险，它只是降低部分 component score。该笔盈利不能证明机制无风险，因为同日 `LABUSDT LONG score=77.75` 同样带 `long_chase_risk_active=True`，且 `price_action_structure` 只有 `8/22`，15 分钟初始止损。多头 offset 和长上下文折扣对“追涨、结构弱、快止损”的过滤仍不够稳定。

### 3.5 五级归因：滚动冷却是事后保护，不是首次止损保护

`rolling_symbol_cooldown_enabled=true`，逻辑是同一 symbol 在 `48h` 窗口内出现至少 `2` 次 `INITIAL_STOP_HIT` 后，触发 `24h` 冷却。该规则能降低连续止损，但对第一笔或第二笔止损之前没有保护。本窗口的 `HYPEUSDT` 第二笔、`LABUSDT` 第二笔、`SOLUSDT` 第一笔都能在首次或未达阈值时开仓并亏损。

### 3.6 缺失指标

日志可直接得出：交易数、胜率、profit factor、realized PnL、max drawdown、费用、滑点、退出原因、持仓时长、分数组成。

日志未直接提供或需另行回放 K 线计算：

- Sharpe / Sortino
- 逐笔 MFE / MAE
- 入场后最大逆行、最大顺行
- exposure time
- tail risk / VaR / CVaR
- 按市场 regime 的收益分解
- 真实交易所成交滑点与盘口冲击

## 4. 实盘/干跑开仓链路

### 4.1 入口与运行模式

入口文件：`scripts/run_live_dry_run.py`

主要链路：

1. `parse_args()` 读取配置、日志目录、数据源、target tier。
2. `run()` 调 `load_entry_chain_config(args.config)` 加载 entry-chain 配置。
3. `resolve_runtime_symbols()` 从配置或 CoinGecko market-cap rank 得到交易对。
4. `warmup_symbols()` 拉取 public Binance Futures 多周期 K 线。
5. 每个周期、每个 symbol：
   - `build_context()` 构建 `EntryChainContext`。
   - `apply_paper_state_to_context()` 注入纸交易状态：日内交易数、当前持仓、曝光、可用保证金、日内 PnL。
   - `evaluate_entry_chain(context, config)` 计算信号动作。
   - `apply_dry_run_decision_controls()` 做额外 dry-run 后处理：观察名单、滚动初始止损冷却、弱边缘 DIRECT 降级。
   - `build_live_entry_order_draft()` 把 PROBE/DIRECT 变成可执行订单草稿。
   - `DecisionAuditWriter` 写 `decisions.jsonl`、`order_drafts.jsonl`、`attribution.jsonl`。
   - `PaperTradingLedger.on_decision()` 按纸交易规则开仓、减仓、平仓，写 `paper_trades.jsonl` 和 `paper_summary.json`。

当前日志明确写出：`exchange_mutation_enabled=False`，`orders_submitted=0`。也就是说，这套链路生成的是 live order draft 和 paper ledger，不会真实提交 Binance 订单。

### 4.2 订单草稿到实盘执行的保护

`src/execution/live_entry_chain_adapter.py`：

- `build_live_entry_order_draft()` 只接受 `decision.action in {"PROBE", "DIRECT"}` 且 `decision.risk_allowed=True`。
- 订单数量来自 `decision.notional_hint / price`。
- 方向映射：`LONG -> BUY`，`SHORT -> SELL`。
- `ExecutionRequest.entry_chain_snapshot` 保留完整决策快照。

`src/execution/execution_engine.py`：

- `validate_entry_chain_execution()` 要求 entry order 必须有 entry-chain approval。
- `risk_allowed` 必须为 true。
- request 的 entry_mode 不能高于 entry-chain 批准等级。
- request 的 side 不能偏离 entry-chain 批准方向。
- request notional 不能超过 `notional_hint`。

## 5. 门槛分数与权重评分

### 5.1 当前配置门槛

来源：`configs/entry_chain.dry_run_fib_pa_v1.json`

- `direct_threshold = 82.0`
- `probe_threshold = 70.0`
- `watch_threshold = 62.0`
- `long_threshold_offset = 10.0`
- `short_threshold_offset = 0.0`
- `probe_conditions.enabled = true`
- `probe_conditions.min_score = 72.0`
- `probe_conditions.long_threshold_offset = 7.0`
- `probe_conditions.short_threshold_offset = 0.0`
- `probe_conditions.min_fib_score = 12.0`
- `probe_conditions.min_pa_score = 6.0`
- `probe_conditions.min_rr_net_r = 0.9`
- `probe_conditions.min_rr_score = 2.0`

实际阈值含义：

- SHORT DIRECT：`score >= 82`
- SHORT PROBE：`score >= 70`
- SHORT WATCH：`score >= 62`
- LONG DIRECT：`score >= 92`
- LONG PROBE：大致 `score >= 77`，并需满足 probe conditions
- LONG WATCH：`score >= 72`

注意：代码中 `_score_to_action()` 先用 offset 得到动作，再由 `_apply_component_minimums()` 做 Fib/PA component minimum 检查。若 DIRECT component minimum 失败，会降为 PROBE；若 PROBE minimum 失败，会降为 WATCH。

### 5.2 Fib/PA 权重

来源：`src/signals/entry_chain_scoring.py`

当 `use_fib_pa_architecture=true` 时，权重固定为：

| 组件 | 权重 |
|---|---:|
| trend_ema_context | 20 |
| flow_cvd_confirmation | 18 |
| cci_momentum_quality | 14 |
| price_action_structure | 22 |
| fibonacci_location | 18 |
| risk_reward_geometry | 8 |

本窗口所有 executable decisions 的 reason 都包含 `FIB_PA_ARCHITECTURE_WEIGHTS`，说明实际使用的是该权重体系。

### 5.3 Fib/PA component minimum

来源：`src/signals/entry_chain.py`

DIRECT 最低分：

- `price_action_structure >= 6.0 / 22`
- `fibonacci_location >= 6.0 / 18`
- `risk_reward_geometry >= 2.0 / 8`

PROBE 最低条件：

- `score >= 72.0`
- `fibonacci_location >= 12.0 / 18`
- `price_action_structure >= 6.0 / 22`
- 若有 `net_tp1_r`，要求 `net_tp1_r >= 0.9`
- 若无 `net_tp1_r`，要求 `risk_reward_geometry >= 2.0 / 8`

关键风险：DIRECT 的 RR minimum 只有 `2/8`，BNBUSDT 以 `risk_reward_geometry=2.0` 过线后拿到 DIRECT 和 4x，最终小亏加成本变成净亏。PROBE 的 PA minimum 只有 `6/22`，LABUSDT 第二笔 `price_action_structure=8/22` 过线后开仓，15 分钟止损。

### 5.4 窗口内 7 次开仓评分拆解

| 时间 CST | 标的 | 动作 | 方向 | 总分 | ema | cvd | cci | PA | Fib | RR | 备注 |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| 06-28 03:30 | HYPEUSDT | PROBE | SHORT | 82.09 | 17.59 | 18 | 10 | 15 | 18 | 3.5 | high beta DIRECT 降 PROBE |
| 06-28 08:00 | HYPEUSDT | PROBE | SHORT | 84.15 | 18.65 | 18 | 14 | 21 | 9 | 3.5 | Fib 只有 9/18，仍可 PROBE |
| 06-28 08:00 | LABUSDT | PROBE | LONG | 82.7229 | 16.69 | 18 | 2.5329 | 21 | 18 | 6.5 | chase/overextension/lowliq 风险仍放行 |
| 06-28 09:15 | BNBUSDT | DIRECT | SHORT | 83.59 | 17.59 | 18 | 7 | 21 | 18 | 2 | RR 刚过最低线，4x |
| 06-28 10:00 | LABUSDT | PROBE | LONG | 77.75 | 17.25 | 18 | 10 | 8 | 18 | 6.5 | PA 弱，15 分钟初始止损 |
| 06-29 09:00 | SOLUSDT | PROBE | LONG | 82.80 | 14.3 | 18 | 14 | 12 | 18 | 6.5 | overextension active，初始止损 |
| 06-29 10:45 | LINKUSDT | PROBE | LONG | 86.30 | 14.3 | 18 | 10 | 21 | 18 | 5 | 8h 后小利 MAX_HOLD |

## 6. 仓位管理

### 6.1 Entry-chain notional_hint

来源：`src/signals/entry_chain.py::_notional_hint()`

公式：

```text
if action not in {PROBE, DIRECT}: notional_hint = 0

exposure_pct = base_direct_exposure_pct
if DIRECT:
    exposure_pct += clamp((score - direct_threshold) / 100, 0, 0.10)
else PROBE:
    exposure_pct *= probe_fraction

exposure_pct = min(exposure_pct, symbol_exposure_cap)
score_based = account_equity * exposure_pct
stop_pct = context.stop_pct or clamp(atr_pct * 1.5, min_stop_pct, max_stop_pct)
risk_pct = direct_risk_pct if DIRECT else probe_risk_pct
risk_based = account_equity * risk_pct / stop_pct
cap_remaining = (symbol_exposure_cap - current_symbol_exposure) * account_equity
notional_hint = min(score_based, risk_based, cap_remaining)
```

当前配置关键参数：

- `direct_risk_pct = 0.006`
- `probe_risk_pct = 0.0025`
- `base_direct_exposure_pct` 使用代码默认 `0.20`
- `probe_fraction` 使用代码默认 `0.25`
- `max_total_exposure_pct = 1.2`
- `max_same_direction_exposure_pct = 0.9`
- `margin_buffer_pct = 0.30`

因此多数 PROBE 的 notional_hint 约为账户权益的 `5%`，约 `492 USDT`。BNB DIRECT 因大盘标的 exposure cap 和低 stop_pct，notional_hint 达 `2126.8776 USDT`。

### 6.2 symbol exposure cap

来源：`src/signals/entry_chain_gates.py::symbol_exposure_cap()`

- `LARGE_CAP_SYMBOLS = {"BTCUSDT", "ETHUSDT", "BNBUSDT"}`，cap 取 `max_large_cap_exposure_pct`，默认 `0.30`。
- `MAINSTREAM_SYMBOLS = {"SOLUSDT", "ADAUSDT", "LINKUSDT"}`，cap 取 `max_mainstream_exposure_pct`，默认 `0.20`。
- `HIGH_BETA_SYMBOLS = {"HYPEUSDT", "LABUSDT", "CCUSDT"}`，cap 取 `max_high_beta_exposure_pct`，默认 `0.10`。

### 6.3 杠杆选择

来源：`src/signals/entry_chain.py::_select_leverage()`

- 非 PROBE/DIRECT：`0x`
- rolling Sharpe < 0：`2x`
- `atr_pct > 0.03`：`3x`
- `atr_pct > 0.015`：DIRECT `4x`，PROBE `3x`
- `score >= 90 and DIRECT`：可 `5x`，但 Fib/PA 架构还需：
  - `fibonacci_location >= 13/18`
  - `price_action_structure >= 9/22`
  - `cci_momentum_quality >= 7/14`
  - `risk_reward_geometry >= 4/8`
- 其他 DIRECT：`4x`
- 其他 PROBE：`3x`

本窗口实际：6 笔 PROBE 为 `3x`，唯一 BNB DIRECT 为 `4x`。

### 6.4 Paper trading 出入场规则

来源：`src/observability/paper_trading.py`

- 初始权益：`10,000 USDT`
- 费用：`FEE_BPS=5.0`
- 滑点：`SLIPPAGE_BPS=5.0`
- stop distance：`stop_pct = clamp(atr_pct * 1.5, 0.005, 0.03)`
- TP：`1.2R / 2.0R / 3.0R`
- 分批：`40% / 35% / 25%`
- TP1 后止损移动到近似保本：
  - LONG：`entry * 1.001`
  - SHORT：`entry * 0.999`
- 最大持仓：`MAX_HOLD_BARS=32`，15m K 线即约 `8h`
- 若未 TP/SL 且达到最大持仓，执行 `MAX_HOLD_EXIT`

## 7. 风控逻辑

### 7.1 Entry-chain hard blocks

来源：`src/signals/entry_chain_gates.py::hard_block_reason()`

会直接 NO_TRADE 的条件包括：

- `SYMBOL_BLACKLISTED`
- `SYMBOL_WATCH_ONLY`
- `MACRO_WEEKLY_RISK`
- `DATA_WICK_ANOMALY`
- `DATA_POLLUTION_COOLDOWN`
- `SYMBOL_POSITION_ALREADY_OPEN`
- `MAX_ACTIVE_SYMBOLS`
- `DAILY_TRADE_BUDGET_USED`
- `SYMBOL_DAILY_TRADE_BUDGET_USED`
- `SYMBOL_COOLDOWN_ACTIVE`
- `TOTAL_EXPOSURE_CAP`
- `SAME_DIRECTION_EXPOSURE_CAP`
- `MARGIN_BUFFER_TOO_LOW`
- `ACCOUNT_EQUITY_INVALID`
- `SIDE_NOT_ALLOWED`

本窗口 decisions 统计：

- 总 decisions：`2275`
- `NO_TRADE=2228`
- `WATCH=40`
- `PROBE=6`
- `DIRECT=1`
- 最常见拒绝原因：
  - `DAILY_TRADE_BUDGET_USED=1050`
  - `SYMBOL_WATCH_ONLY=340`
  - `SYMBOL_BLACKLISTED=327`
  - `FIB_EXTENSION_EXHAUSTION_BLOCK=131`
  - `SYMBOL_DAILY_TRADE_BUDGET_USED=127`
  - `SYMBOL_POSITION_ALREADY_OPEN=102`

这说明交易频率层面已有硬限制，但开出的 7 笔质量仍不足。

### 7.2 交易预算

来源：`daily_max_trades()`

```text
dynamic_limit = floor(daily_max_trades_base * current_volatility_scale / normal_volatility_scale)
if daily_profit_pct > 0.03:
    dynamic_limit = dynamic_limit // 2
```

配置：

- `daily_max_trades_base = 4`
- `max_symbol_trades_per_day = 1`
- `max_active_symbols = 5`

注意：日内统计按 UTC day_start 计算，不是北京时间交易日。若评审关注“北京时间日内预算”，这里需要单独检查。

### 7.3 Dry-run 后处理风控

来源：`scripts/run_live_dry_run.py::apply_dry_run_decision_controls()`

额外把 PROBE/DIRECT 降为 WATCH 的条件：

- symbol 在 `observation_only_symbols`
- `_rolling_initial_stop_cooldown_active()`：48h 内同一 symbol 至少 2 次 `INITIAL_STOP_HIT`，冷却 24h
- `_weak_edge_direct_without_positive_history()`：DIRECT 分数在 `82-85`，且该 symbol 之前没有正收益闭合交易

当前配置：

- `rolling_symbol_cooldown_enabled=true`
- `rolling_symbol_cooldown_stop_threshold=2`
- `rolling_symbol_cooldown_window_hours=48`
- `rolling_symbol_cooldown_hours=24`
- `weak_edge_direct_min_score=82`
- `weak_edge_direct_max_score=85`

注意：该弱边缘保护只处理 DIRECT，不处理 PROBE。因此 `score=77.75` 的 LAB PROBE、`score=82.80` 的 SOL PROBE 不会被这条规则拦住。

### 7.4 Stress simulator

来源：`src/risk/stress_simulator.py`

runtime summary 记录 stress check：

- `adverse_move_pct = 0.20`
- `max_loss_pct = 0.25`
- `estimated_loss_pct = exposure_pct * leverage * adverse_move_pct`

但在非开仓动作里 leverage/exposure 为 0，stress 多显示 ALLOW。它更像观测记录，不是主要入场质量过滤器。

## 8. 待 DeepSeek 重点评审问题

1. 当前 Fib/PA 权重是否过度奖励 `flow_cvd_confirmation`、`fibonacci_location`、`price_action_structure`，导致 `risk_reward_geometry` 只要 `2/8` 就能 DIRECT？
2. DIRECT 最低 `risk_reward_geometry >= 2/8` 是否过低？是否应要求 DIRECT 至少 `4/8`，或要求 `net_tp1_r` 覆盖往返成本后仍高于指定阈值？
3. PROBE 的 `price_action_structure >= 6/22` 是否过低？`LABUSDT score=77.75, PA=8/22` 15 分钟初始止损，是否说明 PA minimum 应提高？
4. 多头 PROBE 实际阈值约 `77` 是否过松？尤其在 `long_chase_risk_active` 或 `long_overextension_active` 时，是否应从降分改为硬阻断或提高阈值？
5. HIGH_BETA_SYMBOLS 被 DIRECT 降为 PROBE 后仍可交易，是否应叠加更严格 RR、PA、MFE 历史或冷却规则？
6. `weak_edge_direct_without_positive_history` 只保护 DIRECT，不保护 PROBE，是否应扩展到弱边缘 PROBE？
7. 当前 `MAX_HOLD_BARS=32` 使部分交易 8h 后小盈/小亏退出，成本吞噬严重。是否应设置“若未达到覆盖成本的最小浮盈则提前退出/不入场”，或要求 TP1 距离覆盖 round-trip cost？
8. 交易预算按 UTC day 统计是否符合操盘预期？如果用户按北京时间观察，是否会产生预算理解偏差？
9. 当前 dry-run paper ledger 的 `fee=5bps + slippage=5bps` 是否符合目标交易所真实水平？如果偏保守，可以继续保守；如果偏乐观，则真实结果会更差。
10. 需要补充 MFE/MAE 回放。仅靠成交日志无法判断亏损交易是入场立即反向、噪音扫损，还是止损距离/同 bar 触发假设导致。

## 9. 我的初步建议，待评审后再改

这些不是本次已实施改动，只是基于日志的候选修正方向：

- 将 DIRECT 的 `risk_reward_geometry` minimum 从 `2/8` 提高到至少 `4/8`，或引入 `net_tp1_r` 硬门槛。
- 将 PROBE 的 `price_action_structure` minimum 从 `6/22` 提高，尤其对 LONG 和 HIGH_BETA 标的。
- 对 `long_chase_risk_active + PA 弱` 的组合设为 WATCH，而不是仅靠总分。
- 对 PROBE 增加弱边缘历史过滤：无正收益闭合交易时，`score < 85` 或 `PA/RR` 不强则 WATCH。
- 对 MAX_HOLD_EXIT 增加成本意识：若预期 TP1/持有到期收益不足以覆盖往返成本，不开仓或提前降级。
- 增加 MFE/MAE 回放脚本，按本窗口 7 笔交易复算入场后每根 15m K 的最大顺行/逆行，确认亏损是信号质量还是退出规则问题。

## 10. 复核命令

可用以下命令复核本报告的证据来源：

```powershell
Get-Content logs\2026-06\2026-06-29\runtime.out.06.log -TotalCount 20
Get-Content logs\2026-06\2026-06-29\paper_summary.json
Get-Content configs\entry_chain.dry_run_fib_pa_v1.json
rg -n "FIB_PA_WEIGHTS|def _score_to_action|def _notional_hint|def _select_leverage" src\signals
rg -n "FEE_BPS|SLIPPAGE_BPS|MAX_HOLD_BARS|TP_LEVELS" src\observability\paper_trading.py
```

