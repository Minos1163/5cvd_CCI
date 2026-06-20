# Backtest Loss Attribution And Live Entry Chain Review

Date: 2026-06-19

Purpose: explain the first offline 30D backtest loss, then define a reviewable live-entry contract for DeepSeek. This document is diagnostic and design guidance only; it does not claim the strategy target is already validated.

---

## 1. Current Backtest Context

Backtest run:

- Run ID: `latest_30d_round1`
- Data range UTC: `2026-05-20T03:25:19` to `2026-06-19T03:25:19`
- Data source: Binance Futures public klines downloaded offline
- Timeframe used in run: `15m`
- Symbols: `BNBUSDT`, `XRPUSDT`, `SOLUSDT`, `TRXUSDT`, `HYPEUSDT`, `DOGEUSDT`, `XLMUSDT`, `ZECUSDT`, `CCUSDT`, `ADAUSDT`, `XMRUSDT`, `LINKUSDT`, `LABUSDT`, `TONUSDT`
- Fill model: next bar open
- Fee: 5 bps per side
- Slippage: 5 bps
- Strategy callback: simple 15m momentum baseline, not the full AI300 strategy

Important interpretation:

- This run validates the offline data and backtest pipeline.
- This run does not validate the final multi-timeframe strategy.
- The result is still useful because it exposes what happens when live-entry gates, position limits, exits, cooldown, and risk controls are absent.

---

## 2. Observed Result

Portfolio result:

- Initial capital: `10000`
- Final equity: `-22215.43`
- Net PnL: `-32215.43`
- Total return: `-322.15%`
- Max drawdown: `322.20%`
- Trades: `24695`
- Win rate: `29.76%`
- Profit factor: `0.5241`
- Sharpe: `-20.43`
- Sortino: `-28.88`
- Expectancy: `-1.3045` per trade

PnL decomposition:

- Gross PnL before costs: `-9088.65`
- Fees: `15418.34`
- Slippage: `7708.44`
- Fees plus slippage: `23126.78`
- Net PnL: `-32215.43`

Direction split:

- Long trades: `12213`, net PnL `-14328.51`, win rate `29.48%`
- Short trades: `12482`, net PnL `-17886.93`, win rate `30.04%`

Entry mode split:

- Direct trades: `12324`, net PnL `-26020.74`, win rate `34.23%`
- Probe trades: `12371`, net PnL `-6194.69`, win rate `25.32%`

Worst net contributors:

- `LABUSDT`: `-4490.34`
- `HYPEUSDT`: `-3530.41`
- `ZECUSDT`: `-3403.96`
- `XLMUSDT`: `-3196.25`
- `TONUSDT`: `-3060.54`

---

## 3. Root Cause Attribution

### 3.1 Primary Root Cause: No Real Entry Gate

The first run used a simple 15m momentum baseline:

- If 15m move exceeded a small threshold, it entered.
- It did not require 4H background, 1H direction, 30m quality, 15m trigger, CVD confirmation, volatility fit, or risk score approval.
- It did not wait for a complete multi-timeframe chain.

Result:

- The callback traded noise as if it were signal.
- Both long and short directions lost, showing the problem is not one-sided market bias.
- Win rate stayed near `30%`, far below the target `80%+`.

### 3.2 Secondary Root Cause: Trade Count Exploded

Target trade count:

- `90-120` trades per 30 days

Observed trade count:

- `24695` trades per 30 days

This is about `206x` to `274x` above the target range.

Result:

- Even if gross edge were close to flat, fees and slippage would dominate.
- The system effectively became a high-frequency churn machine.
- Current run has no cooldown, no per-symbol re-entry throttle, no daily trade budget, and no max active symbols enforcement in the callback.

### 3.3 Cost Drag Was Fatal

Fees plus slippage:

- `23126.78`

Gross PnL:

- `-9088.65`

The strategy lost before costs, and costs made the loss more than 3.5x worse. Cost drag alone is larger than 231% of initial capital.

Conclusion:

- Any future strategy must reduce trade count first.
- A 30D target of `90-120` trades implies roughly `3-4` trades per day across the whole portfolio, not per symbol.

### 3.4 No Position Lifecycle

The baseline run exits after a short synthetic holding window from the current backtest engine. It does not yet express:

- Initial ATR stop
- TP1 / TP2 / TP3
- Breakeven after 1R
- Trailing stop after 2R
- Direction reversal exit
- Portfolio risk exit
- Cooldown after stop
- Max active symbol count

Result:

- The run measures a fill/cost pipeline more than a real strategy lifecycle.
- It cannot yet determine whether the intended risk/exit design can reach target return and win rate.

### 3.5 Position And Leverage Target Not Enforced

User target:

- Floating leverage: `3x`, `4x`, `5x`
- Per-symbol floating position: `20%-30%`
- Max active symbols: `5`

Observed run:

- Uses fixed notional per signal.
- Does not model leverage-based margin usage.
- Does not cap active positions at 5.
- Does not block additional entries when exposure is already high.

Result:

- The backtest is not yet aligned with the requested live capital model.
- Any performance result from this baseline must be treated as pipeline evidence, not portfolio strategy evidence.

---

## 4. Strategy Target Reality Check

Target:

- 30D return: `50%+`
- Win rate: `80%+`
- 30D trade count: `90-120`
- Leverage: `3x-5x`
- Per-symbol exposure: `20%-30%`
- Max active symbols: `5`

This is an aggressive target. To be plausible, the strategy needs all of the following:

- Very selective entries.
- High-quality trend continuation or reversal confirmation.
- Strong cost discipline.
- Average loss tightly controlled.
- Winners allowed to reach at least `1R-3R`.
- Low overlap among correlated symbols.
- Hard daily and weekly loss stops.

Mathematically, an 80% win rate is not enough by itself. If average win is small and average loss is large, expectancy can still be poor. The minimum review target should be:

```text
expectancy = win_rate * avg_win - loss_rate * avg_loss - costs
```

For a real target, after fees and slippage:

- Win rate should be evaluated together with payoff ratio.
- Profit factor should be above `1.8` before considering live deployment.
- Max drawdown should remain within the configured account risk budget.
- Trade count must stay near `90-120`, not thousands.

---

## 5. Proposed Live Opening Chain

The live entry chain must be sequential. Any failed hard gate returns `NO_TRADE`.

Recommended order:

1. Universe gate
2. Data quality gate
3. Portfolio availability gate
4. Multi-timeframe direction gate
5. Indicator scoring gate
6. CVD and liquidity gate
7. Volatility and stop-distance gate
8. Entry mode decision
9. Risk approval
10. Position sizing
11. State machine transition
12. Execution pre-check
13. Order submission
14. Protection order confirmation

Forbidden shortcuts:

- 15m trigger cannot override 1H direction.
- CVD cannot force an entry alone.
- Execution cannot upgrade probe to direct.
- Position sizing cannot raise a too-small probe into direct.
- Risk cannot be bypassed for a high score.
- Backtest cannot use a different entry chain than live.

---

## 6. Hard Gates

### 6.1 Universe Gate

Required:

- Binance USDT perpetual.
- Not stablecoin.
- Market-cap rank in configured universe.
- Sufficient 24h quote volume.
- No delisting or trading suspension flag.
- Spread and slippage acceptable.

Suggested threshold:

```text
quote_volume_24h >= 100,000,000 USDT for direct
quote_volume_24h >= 50,000,000 USDT for probe
```

If volume is below threshold:

- Direct forbidden.
- Probe allowed only if all other scores are strong.

### 6.2 Data Quality Gate

Required:

- 15m bars continuous.
- 30m / 1H / 4H derived only from completed bars.
- No duplicate timestamps.
- Missing bar ratio below threshold.
- OHLCV valid.
- CVD source present or degraded flag explicit.

Suggested threshold:

```text
missing_bar_ratio <= 0.1%
zero_volume_bar_ratio <= 0.1%
all higher timeframe bars closed
```

If failed:

- `NO_TRADE`

### 6.3 Portfolio Availability Gate

Required:

- Active symbols `< 5`
- Total exposure below cap.
- Same correlation group not overloaded.
- Daily and weekly loss limits not reached.
- Symbol not in cooldown.

Suggested thresholds:

```text
max_active_symbols = 5
max_total_notional_exposure = 150% account equity
max_same_direction_exposure = 100% account equity
max_symbol_exposure = 30% account equity
max_correlation_group_exposure = 60% account equity
```

Note:

- Because target leverage is `3x-5x`, notional exposure can exceed account equity.
- Margin and loss-at-stop must still remain within account risk limits.

---

## 7. Detailed Score System

The score has two layers:

- Hard gates: must pass.
- Weighted score: decides `NO_TRADE`, `WATCH`, `PROBE`, or `DIRECT`.

Total score: `100`

Recommended weights:

| Component | Weight |
| --- | ---: |
| 4H background | 10 |
| 1H direction | 20 |
| 30m trend quality | 20 |
| 15m trigger | 15 |
| CVD / active flow | 15 |
| Volatility and stop fit | 10 |
| Liquidity / execution quality | 5 |
| Market regime / BTC pressure | 5 |

### 7.1 4H Background Score: 10

Purpose:

- Background reference only.
- Should downgrade confidence, not act as a hard veto by itself.

Scoring:

```text
10 = 4H aligned with intended direction
6  = 4H neutral / compression
3  = 4H weak conflict
0  = 4H strong opposite trend
```

### 7.2 1H Direction Score: 20

Purpose:

- Main direction permission.

Long example:

```text
MACD histogram > 0 and rising: +5
CCI > 100 or recovering above 100: +5
Price above BOLL mid and midline rising: +4
CVD delta positive over recent window: +4
RSI between 45 and 68, not overheated: +2
```

Short example mirrors the long side.

Hard rule:

- If 1H direction is `NO_TRADE`, total entry must be `NO_TRADE`.

### 7.3 30m Trend Quality Score: 20

Purpose:

- Confirm whether trend quality is good enough for direct.

Scoring:

```text
Trend structure clean: +5
MACD momentum confirms: +4
CCI confirms strength: +4
BOLL expansion or controlled retest: +3
CVD not diverging: +3
No large reversal wick: +1
```

Quality states:

- `CONFIRMED`: 16-20
- `WEAK`: 10-15
- `TRANSITION`: 6-9
- `INVALID`: 0-5

### 7.4 15m Trigger Score: 15

Purpose:

- Timing only.

Scoring:

```text
Breakout or pullback trigger complete: +5
RSI reclaim / rejection in correct zone: +3
MACD low-timeframe turn confirms: +3
CVD aligns on trigger candle cluster: +3
Entry not extended from BOLL mid / VWAP proxy: +1
```

Hard rule:

- 15m cannot create direction.
- 15m can only time an entry already allowed by 1H.

### 7.5 CVD / Active Flow Score: 15

Purpose:

- Confirm whether active flow supports the move.

Scoring:

```text
CVD slope aligns with side: +5
CVD makes higher high/lower low with price: +4
No bearish/bullish divergence against entry: +4
Taker imbalance supports direction: +2
```

Hard rule:

- Strong CVD divergence against entry blocks direct.
- Probe may remain possible only if higher timeframe trend is strong and risk is reduced.

### 7.6 Volatility And Stop Fit Score: 10

Purpose:

- Confirm that stop distance and expected move are tradable.

Scoring:

```text
ATR stop_pct within configured band: +4
Expected TP1 distance >= fee + slippage + safety: +2
No volatility shock / abnormal wick cluster: +2
BOLL width regime supports the entry type: +2
```

Suggested stop band:

```text
min_stop_pct = 0.5%
normal_stop_pct = 0.8% - 2.5%
max_stop_pct = 4.0%
```

### 7.7 Liquidity / Execution Quality Score: 5

Scoring:

```text
High quote volume and low spread: +3
Expected slippage <= configured limit: +2
```

### 7.8 Market Regime / BTC Pressure Score: 5

Scoring:

```text
BTC and total market do not conflict: +3
Sector/regime supports symbol: +2
```

---

## 8. Score To Action Mapping

Recommended mapping:

```text
score < 60:
  NO_TRADE

60 <= score < 70:
  WATCH only

70 <= score < 82:
  PROBE candidate

score >= 82:
  DIRECT candidate
```

Additional direct requirements:

```text
1H direction score >= 16 / 20
30m quality score >= 16 / 20
15m trigger score >= 11 / 15
CVD score >= 11 / 15
risk approval = true
portfolio availability = true
```

Additional probe requirements:

```text
1H direction score >= 14 / 20
30m quality score >= 10 / 20
15m trigger score >= 8 / 15
CVD score >= 8 / 15
risk approval = true
portfolio availability = true
```

Watch requirements:

```text
1H direction score >= 12 / 20
total score >= 60
missing component can plausibly complete within next 3-6 15m bars
```

---

## 9. Trade Count Control

Target:

- `90-120` trades per 30 days

Recommended controls:

```text
max_portfolio_new_entries_per_day = 4
max_symbol_new_entries_per_day = 1
max_portfolio_new_entries_per_4h = 2
cooldown_after_loss = 4 to 8 bars on 15m
cooldown_after_two_losses_same_symbol = 24h
cooldown_after_portfolio_daily_loss = rest of day
```

If trade count exceeds target pace:

- Raise direct threshold by 3-5 points.
- Disable probe for weak-liquidity symbols.
- Require CVD score >= 12 for new entries.
- Reduce max new entries per day until trade count normalizes.

---

## 10. Position Management

User target:

- Floating leverage: `3x`, `4x`, `5x`
- Single-symbol floating position: `20%-30%`
- Max active symbols: `5`

### 10.1 Leverage Selection

Suggested leverage table:

```text
score >= 90 and risk LOW:
  leverage = 5x

82 <= score < 90 and risk NORMAL:
  leverage = 4x

70 <= score < 82 or risk HIGH:
  leverage = 3x

risk EXTREME or BLOCKED:
  no trade
```

Volatility override:

```text
ATR_pct > 3.0%:
  max leverage = 3x

ATR_pct 1.5% - 3.0%:
  max leverage = 4x

ATR_pct < 1.5%:
  max leverage = 5x if score permits
```

### 10.2 Exposure Sizing

Direct exposure:

```text
base_symbol_exposure = 20% account equity
high_score_bonus = up to +10%
max_symbol_exposure = 30% account equity
```

Probe exposure:

```text
probe_exposure = direct_exposure * 0.25
```

Risk-based cap:

```text
risk_amount = account_equity * risk_per_trade_pct
risk_based_notional = risk_amount / stop_pct
final_notional = min(score_based_notional, risk_based_notional, portfolio_cap_remaining)
```

Suggested risk per trade:

```text
probe_risk_per_trade = 0.25% - 0.40%
direct_risk_per_trade = 0.60% - 1.00%
```

Hard cap:

```text
loss_at_stop for one direct trade <= 1% account equity
loss_at_stop for all active positions <= 3% account equity
```

### 10.3 Active Position Limits

Required:

```text
max_active_symbols = 5
max_same_direction_positions = 4
max_same_correlation_group_positions = 2
max_new_positions_during_high_volatility = 2
```

Correlation examples:

- Large caps: BTC, ETH, BNB
- L1 beta: SOL, ADA, TON
- Payment / legacy: XRP, XLM, BCH, LTC
- High-beta / new listings: HYPE, LAB, CC

---

## 11. Risk Logic

### 11.1 Pre-Trade Risk Checks

All must pass:

```text
account_equity > 0
available_margin sufficient
daily_pnl > -5% account equity
weekly_pnl > -12% account equity
max_drawdown < 20%
open_positions < 5
symbol_exposure_after_trade <= 30%
portfolio_exposure_after_trade <= 150%
loss_at_stop_after_trade <= configured risk budget
cooldown inactive
data quality valid
```

### 11.2 Stop Logic

Initial stop:

```text
stop_distance = ATR * stop_atr_mult
stop_pct = stop_distance / entry_price
```

Suggested:

```text
stop_atr_mult = 1.2 - 2.0
min_stop_pct = 0.5%
max_stop_pct = 4.0%
```

If stop is too small:

- Reject or widen stop and reduce size.

If stop is too large:

- Reduce size or reject.

### 11.3 Take-Profit Logic

Default:

```text
TP1 = 1R, reduce 30%
TP2 = 2R, reduce 40%
TP3 = 3R to 4R, trail remainder
```

Breakeven:

```text
after TP1 or price >= 1R:
  stop = entry_price + fee_buffer + slippage_buffer for long
  stop = entry_price - fee_buffer - slippage_buffer for short
```

Trailing:

```text
after 2R:
  trail by 15m/30m structure or ATR trail
```

### 11.4 Forced Exit Priority

Priority from high to low:

1. Exchange or position sync abnormality
2. Initial stop hit
3. Portfolio risk exceeded
4. Direction reversal on 1H
5. CVD strong divergence against position
6. Volatility shock
7. Trailing stop
8. Take-profit schedule

Lower-priority actions cannot override higher-priority exits.

### 11.5 Daily Protection

Recommended:

```text
daily_loss_soft_stop = -3%
daily_loss_hard_stop = -5%
weekly_loss_hard_stop = -12%
consecutive_loss_stop = 3 losses in same symbol
portfolio_consecutive_loss_stop = 5 losses in one day
```

Soft stop:

- Disable direct.
- Allow only strongest probe if portfolio risk is normal.

Hard stop:

- No new entries.
- Manage existing exits only.

---

## 12. Backtest Acceptance Criteria Before Live

Before live use, require at least:

```text
30D trade_count between 90 and 120
win_rate >= 70% before optimization, target 80% after validation
profit_factor >= 1.8
max_drawdown <= 15%
expectancy > 0 after fees and slippage
no single symbol contributes > 25% of total profit
no single symbol contributes > 25% of total loss
long and short both non-catastrophic
probe and direct reported separately
all rejected / blocked samples recorded
```

For the user target:

```text
30D return >= 50%
win_rate >= 80%
trade_count 90-120
```

Do not accept a single lucky 30D window. Require:

- Rolling 30D windows.
- At least 6-12 months of historical data.
- Walk-forward validation.
- Out-of-sample month.
- Stress windows with high volatility and range markets.

---

## 13. DeepSeek Review Questions

Please review:

1. Are the proposed score weights reasonable for a 15m/30m/1H/4H crypto futures strategy?
2. Is the target `50%+` 30D return with `80%+` win rate internally consistent with `90-120` trades and `3x-5x` leverage?
3. Should direct threshold be `82`, or should it be higher given the aggressive leverage target?
4. Is `20%-30%` per-symbol exposure too high with max 5 simultaneous positions?
5. Should portfolio exposure cap be `150%` notional, or lower for volatile altcoins?
6. Should CVD divergence be a hard direct blocker or only a score penalty?
7. Should 4H conflict block direct completely, or only downgrade to probe?
8. Are the cooldown rules strong enough to force trade count into the `90-120` range?
9. Are TP1/TP2/TP3 levels suitable for high win-rate target, or should exits be more conservative?
10. What minimum walk-forward evidence is required before live trading?

---

## 14. Immediate Next Engineering Work

Recommended next steps:

1. Replace the simple 15m baseline callback with the full multi-timeframe signal chain.
2. Add portfolio state to the backtest runner so max active symbols and max exposure are enforced.
3. Add ATR stop, TP ladder, breakeven, trailing stop, and cooldown to the backtest lifecycle.
4. Add score breakdown logs per candidate signal.
5. Add trade-budget controls to keep 30D trades near `90-120`.
6. Re-run the same latest 30D dataset.
7. Then run at least 6-12 months before interpreting performance.

---

## 15. Bottom Line

The loss was not caused by Binance data, not by one symbol, and not by one trade direction.

The root cause is structural:

- no real entry gate,
- too many trades,
- no portfolio active-position cap,
- no full position lifecycle,
- costs overwhelming weak signals,
- backtest callback not yet matching the intended live strategy.

Before targeting `50%+` monthly return and `80%+` win rate, the next backtest must enforce the same gates, scoring, sizing, risk, exits, cooldown, and max-position rules that live trading will use.
