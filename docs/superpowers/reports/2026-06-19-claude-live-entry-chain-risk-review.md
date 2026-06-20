# Claude Review: AI300 Live Entry Chain And Risk Contract

Date: 2026-06-19

Purpose: provide Claude with a precise review target for AI300 live-entry logic, score thresholds, position sizing, leverage, and risk controls. This document is for review and dry-run design. It is not approval for live trading.

---

## 1. Strategy Target

Requested target:

- Floating leverage: `3x`, `4x`, `5x`
- Single-symbol exposure: `20%-30%` of account equity
- Max active symbols: `5`
- 30D return target: `50%+`
- Win rate target: `80%+`
- 30D opening count: `90-120`

Current calibrated backtest best result:

- Run ID: `latest_30d_round4_entry_chain_conservative_cd8`
- 30D trades: `93`
- Return: `-1.08%`
- Win rate: `27.96%`
- Profit factor: `0.5222`
- Max drawdown: `1.34%`

Interpretation:

- Trade frequency is now in range.
- Profitability and win rate are not in range.
- Current engine still uses synthetic short exits, so the final stop/TP lifecycle is not validated.

---

## 2. Non-Negotiable Live Principles

Live and backtest must share the same decision contract:

- No same-bar fill assumptions.
- No unfinished higher-timeframe bars.
- No future candle data.
- No repainting indicator states.
- No entry if data quality is degraded.
- No execution upgrade from `PROBE` to `DIRECT`.
- No risk bypass for high score.
- No real order submission unless dry-run and lifecycle backtests pass review.

---

## 3. Live Opening Chain

Sequential chain. Any hard failure returns `NO_TRADE`.

1. Universe gate
2. Data quality gate
3. Market regime and BTC pressure gate
4. Portfolio availability gate
5. Symbol cooldown and trade-budget gate
6. Multi-timeframe direction gate
7. Weighted score calculation
8. Component-minimum gate
9. Liquidity and slippage gate
10. Volatility and stop-fit gate
11. Entry mode decision: `NO_TRADE`, `WATCH`, `PROBE`, `DIRECT`
12. Risk approval
13. Position sizing and leverage selection
14. Execution pre-check
15. Order draft or dry-run emission
16. Protection order plan confirmation

Forbidden shortcuts:

- `15m` trigger cannot override failed `1H` direction.
- CVD cannot create a trade alone.
- `4H` agreement can boost confidence but cannot rescue bad `1H` direction.
- Execution cannot increase notional above entry-chain `notional_hint`.
- Probe cannot be promoted to direct downstream.

---

## 4. Hard Gates

### 4.1 Universe Gate

Required:

- Binance USDT perpetual.
- Not stablecoin.
- Configured rank range, currently intended as market-cap rank `3-25`, excluding stablecoins.
- Sufficient 24h quote volume.
- No delisting, suspension, or symbol abnormality.

Suggested liquidity floors:

```text
direct quote_volume_24h >= 100,000,000 USDT
probe quote_volume_24h  >= 50,000,000 USDT
```

Implementation currently uses a liquidity ratio:

```text
liquidity_ratio = quote_volume_24h / (max(1, atr_pct * 100) * expected_order_size)
direct requires liquidity_ratio >= 20
probe requires liquidity_ratio >= 8
```

### 4.2 Data Quality Gate

Required:

```text
15m bars continuous
30m/1H/4H bars closed before use
no duplicate timestamps
missing_bar_ratio <= 0.1%
zero_volume_bar_ratio <= 0.1%
OHLC valid
CVD source present or explicitly degraded
```

Hard block reasons:

```text
DATA_WICK_ANOMALY
DATA_POLLUTION_COOLDOWN
WEBSOCKET_RECONNECT_WATCH
```

### 4.3 Market Risk Gate

Hard block:

```text
macro_weekly_drop_pct <= -15%
```

Direct downgrade:

```text
macro_daily_drop_pct <= -5%
USDT premium abnormal
```

### 4.4 Portfolio Gate

Hard constraints:

```text
max_active_symbols = 5
max_total_exposure_pct = 120%-150% depending profile
max_same_direction_exposure_pct = 90%-110% depending profile
available_margin >= account_equity * margin_buffer_pct
```

Current profile examples:

| Profile | Daily Trades | Direct Threshold | Probe Threshold | Total Exposure Cap | Same Direction Cap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Conservative | 3 | 86 | 74 | 120% | 90% |
| Balanced | 4 | 82 | 70 | 135% | 100% |
| Aggressive Research | 5 | 78 | 68 | 150% | 110% |

Dry-run should begin with conservative profile.

### 4.5 Trade Budget And Cooldown

Target:

```text
90-120 openings per 30D
about 3-4 portfolio openings per day
```

Recommended live controls:

```text
max_portfolio_new_entries_per_day = 3 conservative, 4 balanced, 5 research-aggressive
max_symbol_new_entries_per_day = 1 conservative/balanced
cooldown_after_entry = 8 to 16 bars on 15m
cooldown_after_loss = 16 to 32 bars on 15m
cooldown_after_two_losses_same_symbol = 24h
daily_loss_hard_stop = rest of day
```

If 7-day projected trade count exceeds `120/month`, raise direct/probe thresholds by `+2` and disable probes.

---

## 5. Weighted Score System

Total score: `100`.

Current base weights:

| Component | Weight | Purpose |
| --- | ---: | --- |
| `background_4h` | 8 | background alignment |
| `direction_1h` | 25 | primary direction permission |
| `quality_30m` | 22 | trend quality |
| `trigger_15m` | 12 | entry timing |
| `cvd_flow` | 18 | active-flow confirmation |
| `volatility_stop` | 10 | stop distance and volatility fit |
| `liquidity_execution` | 3 | execution quality |
| `market_regime` | 2 | BTC/market pressure |

Dynamic high-volatility weights:

```text
if atr_pct > 3.5%:
  volatility_stop = 20
  cvd_flow = 10
  all other weights rescaled to total 100
```

Dynamic low-volatility weights:

```text
if atr_pct < 1.0%:
  trigger_15m = 18
  cvd_flow = 18
  all other weights rescaled to total 100
```

Score calculation:

```text
component_points[key] = clamp(component_score[key], 0, 1) * component_weight[key]
total_score = sum(component_points)
```

---

## 6. Score To Action Mapping

Conservative profile:

```text
score >= 86: DIRECT candidate
74 <= score < 86: PROBE candidate
62 <= score < 74: WATCH
score < 62: NO_TRADE
```

Balanced profile:

```text
score >= 82: DIRECT candidate
70 <= score < 82: PROBE candidate
60 <= score < 70: WATCH
score < 60: NO_TRADE
```

Aggressive research profile:

```text
score >= 78: DIRECT candidate
68 <= score < 78: PROBE candidate
58 <= score < 68: WATCH
score < 58: NO_TRADE
```

Production recommendation:

- Conservative only for initial dry-run.
- Balanced only after 30D conservative dry-run passes quality metrics.
- Aggressive profile is research-only and should not be used live.

---

## 7. Component Minimums

Direct requires:

```text
direction_1h >= 0.64
quality_30m >= 0.73
trigger_15m >= 0.92
cvd_flow >= 0.61
```

Probe requires:

```text
direction_1h >= 0.56
quality_30m >= 0.45
trigger_15m >= 0.67
cvd_flow >= 0.45
```

If direct minimum fails:

- downgrade to `PROBE`.

If probe minimum fails:

- downgrade to `WATCH`.

Critical review point:

- Current backtest shows probe trades are weak. Proposed live revision: disable probes until lifecycle backtests prove positive expectancy.

---

## 8. Position Sizing

User target:

```text
single-symbol exposure = 20%-30% account equity
max active symbols = 5
```

Current sizing formula:

```text
score_based_notional = account_equity * exposure_pct
risk_based_notional = account_equity * risk_pct / stop_pct
cap_remaining = (max_symbol_exposure_pct - current_symbol_exposure_pct) * account_equity
notional_hint = min(score_based_notional, risk_based_notional, cap_remaining)
```

Direct exposure:

```text
base_direct_exposure_pct = 20%
score bonus = up to +10%
max large cap exposure = 30%
max mainstream exposure = 20%
max high-beta exposure = 10%
```

Probe exposure:

```text
probe_fraction = 25% of direct exposure
```

Risk per trade:

```text
direct_risk_pct = 0.60%-1.00% by profile
probe_risk_pct = 0.25%-0.40% by profile
```

Hard loss-at-stop target:

```text
single direct loss_at_stop <= 1% equity
all active loss_at_stop <= 3% equity
```

---

## 9. Leverage Selection

Allowed leverage:

```text
3x, 4x, 5x
```

Current selection:

```text
if action not in PROBE/DIRECT:
  leverage = 0

if rolling_sharpe_20 < 0:
  leverage capped to 2x in current code

if atr_pct > 3.0%:
  leverage = 3x

if atr_pct > 1.5%:
  direct leverage = 4x
  probe leverage = 3x

if score >= 90 and action == DIRECT:
  leverage = 5x

else:
  direct leverage = 4x
  probe leverage = 3x
```

Review note:

- The current negative-Sharpe cap returns `2x`, which is below the user target but safer.
- Claude should review whether this should remain a hard cap or become `NO_TRADE`.

---

## 10. Stop, Take Profit, And Exit Lifecycle

The intended live lifecycle:

Initial stop:

```text
stop_pct = clamp(ATR_pct * 1.5, 0.5%, 4.0%)
```

Take profit:

```text
TP1 = 1R, reduce 30%
TP2 = 2R, reduce 40%
TP3 = 3R-4R, trail remainder
```

Breakeven:

```text
after TP1 or price >= 1R:
  stop moves to entry +/- fee and slippage buffer
```

Trailing:

```text
after 2R:
  trail by 15m/30m structure or ATR trail
```

Max holding time:

```text
if no TP1 and no stop after 24h:
  reduce or close
```

Forced exit priority:

1. Exchange or position sync abnormality
2. Initial stop
3. Portfolio risk exceeded
4. 1H direction reversal
5. Strong CVD divergence against position
6. Volatility shock
7. Trailing stop
8. TP schedule

Current backtest limitation:

- The current offline engine still uses a synthetic short exit and does not validate this lifecycle yet.

---

## 11. Portfolio Risk

Pre-trade checks:

```text
account_equity > 0
available_margin sufficient
daily_pnl > -5%
weekly_pnl > -12%
max_drawdown < 20%
active_symbols < 5
symbol_exposure_after_trade <= symbol cap
portfolio_exposure_after_trade <= profile cap
same_direction_exposure_after_trade <= profile cap
loss_at_stop_after_trade <= risk budget
cooldown inactive
data quality valid
```

Daily protection:

```text
daily_loss_soft_stop = -3%
daily_loss_hard_stop = -5%
weekly_loss_hard_stop = -12%
portfolio_drawdown_hard_stop = -20%
consecutive_symbol_loss_stop = 2 losses in same symbol
portfolio_consecutive_loss_stop = 5 losses in one day
```

Soft stop:

- Disable probes.
- Direct only if score exceeds threshold by `+4`.

Hard stop:

- No new entries.
- Manage exits only.

Stress loss gate:

```text
stress_loss_pct = exposure_pct * leverage * adverse_move_pct
if portfolio stress_loss_pct > 25%:
  reject new entries or reduce leverage
```

---

## 12. Dry-Run Acceptance Criteria Before Any Live Trading

Minimum dry-run gate:

```text
duration >= 30D conservative profile
trade_count between 60 and 120
win_rate >= 65%
profit_factor >= 1.3
no data-health outage causing false entries
no execution pre-check bypass
no probe-to-direct promotion
decision logs complete
```

Before micro-live:

```text
duration >= 60D
win_rate >= 75%
profit_factor >= 1.8
average win/loss >= 1.5
max consecutive losses <= 4
max drawdown <= 12%
rolling 30D return positive in at least 2 windows
```

For the requested aggressive target:

```text
30D return >= 50%
win_rate >= 80%
trade_count 90-120
```

This should require:

- 6-12 months historical rolling windows,
- walk-forward validation,
- out-of-sample month,
- stress windows,
- parameter sensitivity scan.

---

## 13. Current Engineering Gaps

Open gaps before the target can be trusted:

1. Full lifecycle backtest is not implemented.
2. MFE/MAE reporting is missing.
3. True exchange CVD/trade-flow integration is not validated.
4. Leverage/margin/liquidation modeling is incomplete.
5. Correlation-group exposure is not fully enforced in the entry-chain context.
6. Probe trades are empirically weak in the current test.
7. Current 30D result is one window only and not enough for validation.

---

## 13.1 EMA Replacement Review Note

RSI has been removed from the main entry-chain scoring path because it overlaps with CCI as an oscillator-style momentum filter. The replacement architecture uses:

- EMA200 as the direction legality gate.
- EMA50 as trend-quality and direct/probe minimum score input.
- EMA9/21 as short-term momentum resonance.

Claude should specifically challenge:

- whether EMA200 should be hard gate or soft penalty,
- whether EMA lag creates unacceptable blind spots during fast reversals,
- whether EMA50 minimums are too strict for 90-120 monthly openings,
- whether CCI plus EMA is sufficiently orthogonal after removing RSI.

---

## 14. Questions For Claude

Please review and challenge:

1. Is the target `50%+` monthly return, `80%+` win rate, and `90-120` trades internally consistent under `3x-5x` leverage and realistic crypto futures costs?
2. Should probes be disabled entirely until direct-only lifecycle backtests prove positive expectancy?
3. Are the current base weights too heavily tilted toward `1H direction`, or is that appropriate for a 15m/30m/1H/4H system?
4. Are direct thresholds `86/82/78` sensible, or should production require `>= 88`?
5. Should the negative rolling-Sharpe leverage cap return `2x`, or should it force `NO_TRADE`?
6. Is `20%-30%` per-symbol exposure too high when max active symbols is `5`?
7. Should high-beta symbols be capped at `10%`, probe-only, or excluded entirely?
8. Should CVD divergence be a hard blocker for both direct and probe?
9. Is the stress loss cap of `25%` too loose for altcoin futures?
10. What minimum rolling-window evidence should be required before any real capital deployment?

---

## 15. Review Summary

Current system status:

- Safer than the first baseline.
- Trade count can be controlled.
- Entry-chain decisions are auditable.
- The latest target-count backtest still loses money.

Main recommendation:

- Do not deploy live trading yet.
- Use conservative dry-run only after the lifecycle backtest is implemented.
- Treat current results as evidence for harness improvement, not strategy profitability.

