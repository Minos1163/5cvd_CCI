# VPS Dry-Run Loss Attribution And Fib/Price Action Refactor Review

> Window: 2026-06-22 20:00 CST to latest downloaded logs  
> Latest downloaded log update: 2026-06-26 09:45 CST  
> Latest paper summary business timestamp: 2026-06-26 09:30 CST  
> Data source: `logs/2026-06/2026-06-22` through `logs/2026-06/2026-06-26`

---

## 1. Executive Summary

This dry-run window still loses money even after the P0 data-quality fixes. The important conclusion is not that the strategy has no winning trades. It has winners. The problem is that the average initial stop is much larger than the average profitable path.

Using trade-level `position_realized_pnl` for positions closed after 2026-06-22 20:00 CST:

```text
Closed trades:       22
Wins / losses:       12 / 10
Win rate:            54.55%
Realized PnL:        -67.38 USDT
Gross profit:        +221.59 USDT
Gross loss:          -288.98 USDT
Profit factor:       0.77
```

The latest daily `paper_summary.json` reports cumulative paper state:

```text
Equity:              9883.20 USDT
Realized PnL:        -116.80 USDT
Return:              -1.17%
Max drawdown:        2.81%
Trade count:         34
Win rate:            55.88%
Profit factor:       0.72
Margin equity view:  9363.26 USDT
```

The main loss cause remains structural: high-score signals measure trend agreement, not trade location. Many losing shorts entered after a sharp move had already happened, exactly where price action and Fibonacci pullback/extension logic should have warned against continuation entry.

---

## 2. Data Quality Notes

P0 fixes are visible in the downloaded logs:

- `INITIAL_STOP_HIT` appears and separates true adverse stops from post-TP stops.
- `BREAKEVEN_STOP_HIT` appears and prevents TP1-then-stop trades from being counted as full initial stop failures.
- `SYMBOL_OBSERVATION_ONLY`, `SYMBOL_ROLLING_INITIAL_STOP_COOLDOWN`, and `DIRECT_WEAK_EDGE_DEMOTED` appear in decision logs.
- `XLMUSDT` is no longer opening trades; it is producing observation-only scoring records.

Important accounting note:

- Exit-event `net_pnl` alone is not the right trade-level PnL because entry fee/slippage is recorded on `PAPER_OPEN`.
- This report uses `position_realized_pnl` from `PAPER_CLOSE` as the main trade result.

---

## 3. Loss Attribution By Symbol

| Symbol | Closed Trades | PnL | Win Rate | Main Exit Reasons | Diagnosis |
|---|---:|---:|---:|---|---|
| TONUSDT | 2 | -54.57 | 0.00% | `INITIAL_STOP_HIT` x2 | Both long and short failed quickly. Direction scoring flipped, but location/timing was poor. |
| BNBUSDT | 4 | -50.13 | 50.00% | `INITIAL_STOP_HIT` x2, `TP3_HIT` x1, `MAX_HOLD_EXIT` x1 | Two late-window shorts caused most of the BNB damage. High score did not protect against reversal. |
| LINKUSDT | 6 | -10.76 | 50.00% | `INITIAL_STOP_HIT` x3, `TP3_HIT` x2, `MAX_HOLD_EXIT` x1 | Mixed symbol. Can trend, but also repeatedly triggers high-score shorts after overextension. |
| DOGEUSDT | 5 | +15.27 | 60.00% | `INITIAL_STOP_HIT` x2, `TP3_HIT` x1, `MAX_HOLD_EXIT` x1, `BREAKEVEN_STOP_HIT` x1 | Best net contributor after SOL, but weak-edge trades still create avoidable losses. |
| SOLUSDT | 5 | +32.81 | 80.00% | `TP3_HIT` x2, `BREAKEVEN_STOP_HIT` x2, `INITIAL_STOP_HIT` x1 | Best symbol in this window, but still suffered a high-score reversal stop on 2026-06-25 CST. |

By CST close date:

| Date CST | Closed Trades | PnL | Win Rate | Comment |
|---|---:|---:|---:|---|
| 2026-06-23 | 9 | +9.78 | 66.67% | Mostly stable, TON and LINK losses offset by SOL/LINK/DOGE winners. |
| 2026-06-24 | 4 | +24.30 | 75.00% | Strong TP3 cluster. |
| 2026-06-25 | 8 | -54.51 | 37.50% | Structural failure day. Multiple high-score shorts stopped. |
| 2026-06-26 | 1 | -46.96 | 0.00% | BNB short from late 6-25 CST closed as large initial stop. |

The loss is therefore not uniformly distributed. The failure cluster starts around 2026-06-25 CST and is dominated by initial stops in LINK, SOL, DOGE, and especially BNB.

---

## 4. Score And Leverage Diagnostics

Score bins based on open score:

| Score Bin | Trades | PnL | Avg PnL | Win Rate |
|---|---:|---:|---:|---:|
| 82-85 | 3 | -27.26 | -9.09 | 33.33% |
| 85-90 | 5 | +13.04 | +2.61 | 80.00% |
| 90+ | 14 | -53.15 | -3.80 | 50.00% |

Leverage:

| Leverage | Trades | PnL | Avg PnL | Win Rate |
|---:|---:|---:|---:|---:|
| 4x | 8 | -14.23 | -1.78 | 62.50% |
| 5x | 14 | -53.15 | -3.80 | 50.00% |

This is the central red flag: the 90+ score bucket lost money, and 5x lost more than 4x. The current score is not an edge-quality score. It is mostly an agreement score.

The 90+ losing trades often had near-perfect components:

```text
direction_1h = 1.0
quality_30m = 1.0
trigger_15m = 1.0
cvd_flow = 1.0
ema_50_quality = 0.95
ema_momentum = 0.8
```

That means the model was saying: "everything agrees with the current move." It was not asking: "is this a good location to enter?"

---

## 5. Representative Losing Trades

### 5.1 BNBUSDT Short, 2026-06-25 22:15 CST

```text
Open:       2026-06-25 22:15 CST
Side:       SHORT
Score:      95.6754
Leverage:   5x
Exit:       INITIAL_STOP_HIT
PnL:        -41.69 USDT
Kline:      open=554.18 high=554.83 low=548.99 close=552.50
ATR pct:    0.7923%
Stop pct:   1.1884%
```

The signal opened short after a meaningful down candle. All trend-agreement components were high, but there was no support-distance, Fibonacci extension, or reversal candle context.

### 5.2 BNBUSDT Short, 2026-06-25 23:00 CST

```text
Open:       2026-06-25 23:00 CST
Side:       SHORT
Score:      95.6754
Leverage:   5x
Exit:       INITIAL_STOP_HIT
PnL:        -46.96 USDT
Kline:      open=553.25 high=553.36 low=549.59 close=549.93
ATR pct:    0.9092%
Stop pct:   1.3638%
```

This is a repeat of the same structure. The score stayed high because the short-term trend was still aligned, but location was getting worse. A price-action layer should have asked whether price was extended into a local swing low or liquidity area.

### 5.3 LINKUSDT Short, 2026-06-25 21:45 CST

```text
Open:       2026-06-25 21:45 CST
Side:       SHORT
Score:      90.1338
Leverage:   5x
Exit:       INITIAL_STOP_HIT
PnL:        -26.77 USDT
Kline:      open=7.287 high=7.310 low=7.001 close=7.024
Change:     -3.61%
```

This is the cleanest example of "after-the-move shorting." A -3.61% 15m candle creates strong direction/trigger/CVD agreement, but it is exactly where continuation entry should require a pullback/retest or a Fibonacci continuation zone check.

### 5.4 TONUSDT Direction Flip Failure

TON had two initial stops:

```text
2026-06-23 04:00 CST LONG  score=96.85  PnL=-27.35
2026-06-23 11:00 CST SHORT score=87.65  PnL=-27.23
```

This is a different failure mode: the system flipped direction within hours and lost both sides. It suggests the current trend agreement layer can overreact to local momentum without a market-structure regime filter.

---

## 6. Current Scoring Architecture Problem

Current EMA architecture weights:

```text
background_4h        5
direction_1h        18
quality_30m         12
trigger_15m          7
ema_50_quality      15
ema_momentum        10
cvd_flow            18
volatility_stop     10
liquidity_execution  3
market_regime        2
```

The heaviest drivers are:

- 1h direction
- CVD flow
- EMA50 quality
- 30m quality
- volatility stop validity

The missing drivers are:

- Swing structure.
- Nearby support/resistance.
- Whether current price is at a Fibonacci extension, pullback, or invalid location.
- Whether the entry candle is a climax candle.
- Whether price has already moved too far from the last valid pullback.
- Whether the trade has a reasonable path to TP1 before hitting stop.

That is why perfect scores can lose. The score confirms the state after a move has already printed.

---

## 7. Recommendation: Replace MACD/BOLL Responsibilities With Price Action + Fibonacci

### 7.1 Hypothesis

MACD and BOLL are not solving the current live dry-run failure because the failures are not primarily "trend indicator disagreement" failures. They are entry-location failures.

The new stack should be:

```text
CCI + CVD + EMA + Price Action + Fibonacci
```

Roles:

| Layer | Responsibility | Should Not Do |
|---|---|---|
| EMA | Trend legality and trend quality | Predict continuation by itself |
| CVD | Active flow confirmation / divergence | Override bad price location |
| CCI | Exhaustion, recovery, overextension, momentum quality | Act as the only direction signal |
| Price Action | Swing structure, breakout/retest, rejection candle, support/resistance | Become subjective discretionary logic |
| Fibonacci | Location filter: pullback zone, extension exhaustion, risk/reward geometry | Create trades without EMA/CVD confirmation |

Expected regime:

- Works best in liquid altcoin trends where price respects swing pullbacks and extension zones.
- Should reduce late-entry shorts after sharp 15m down candles.
- Should reduce 5x entries when price is already at or beyond a 1.272/1.618 extension from the last swing.

Failure mode:

- May miss V-shaped continuation moves that never retest.
- May reduce trade count.
- Fibonacci swing detection can overfit if swing rules are too sensitive.
- Price action labels can become noisy if built from too few candles.

---

## 8. Proposed New Score And Weight Design

The main change: turn price location into a gate or heavy multiplier, not just a small additive score.

### 8.1 Proposed Components

```text
trend_ema_context        20
flow_cvd_confirmation    18
cci_momentum_quality     14
price_action_structure   22
fibonacci_location       18
risk_reward_geometry      8
```

Total: 100

### 8.2 Component Definitions

#### EMA Trend Context, 20 points

Inputs:

- EMA200 side legality.
- EMA50 slope.
- EMA9/21 short-term alignment.
- Distance from EMA50/EMA200.

Suggested rules:

- `EMA200` remains a hard or strong soft gate.
- `EMA50` slope must agree with side for DIRECT.
- If price is too far from EMA50 after a fast move, apply extension penalty.

#### CVD Flow Confirmation, 18 points

Inputs:

- CVD slope over last 6 to 12 bars.
- CVD divergence against price.
- Volume-adjusted CVD impulse.

Suggested rules:

- CVD may confirm an entry only after price-action location is valid.
- CVD divergence against entry side should cap action at WATCH.

#### CCI Momentum Quality, 14 points

Inputs:

- CCI value.
- CCI slope.
- CCI recovery from extreme.
- CCI failure to continue after extreme.

Suggested short-side interpretation:

- CCI below -150 after a large down move is not automatically bearish. It may mean exhaustion.
- Better short entry is often CCI recovery failure near -100 to 0 after pullback, not fresh CCI collapse below -150.

#### Price Action Structure, 22 points

Inputs:

- Swing high / swing low.
- Break of structure.
- Retest success/failure.
- Rejection candle.
- Engulfing or strong close beyond structure.
- Wick-to-body risk.

For SHORT:

- Prefer lower-high retest failure.
- Prefer breakdown followed by failed reclaim.
- Reject fresh shorts into an obvious swing low without retest.
- Penalize large lower wick or bullish reversal bar after sweep.

#### Fibonacci Location, 18 points

Inputs:

- Last confirmed impulse swing.
- Pullback levels: 0.382, 0.5, 0.618, 0.786.
- Extension levels: 1.272, 1.618, 2.0.
- Distance to nearest support/resistance.

For SHORT:

- Best entry zone: bearish retest around 0.382-0.618 pullback of the last down impulse.
- Avoid new shorts at or beyond 1.272/1.618 downside extension unless there is a fresh pullback.
- If price is within 0.3 ATR of a recent swing low or Fib extension target, cap to WATCH.

#### Risk/Reward Geometry, 8 points

Inputs:

- Distance to invalidation.
- Distance to TP1.
- Whether TP1 is before nearby support/resistance.
- Fee/slippage-adjusted R.

Suggested rule:

- DIRECT requires TP1 path >= 1.1R after fees and before nearest opposing structure.
- 5x requires TP1 path >= 1.3R and no Fib extension exhaustion.

---

## 9. Proposed Gate Order

The current system effectively does:

```text
trend agreement -> score -> risk/draft
```

Recommended new order:

```text
1. Data readiness: 240 closed 15m bars, no stale data
2. EMA legality: side must be legal or heavily penalized
3. Price-action structure: must have valid swing/retest/breakdown context
4. Fibonacci location: entry must not be at exhaustion extension or into support/resistance
5. CVD confirmation: flow must support the already-valid setup
6. CCI momentum quality: reject exhaustion, reward recovery failure/continuation quality
7. Risk/reward geometry: TP1 path must be large enough after fees
8. Score and leverage selection
```

This order matters. CVD and EMA should not be allowed to rescue a bad Fib/price-action location.

---

## 10. Immediate Strategy Changes For Claude Review

### P0 Research Changes

1. Add `price_action_structure_score`.
2. Add `fib_location_score`.
3. Add `cci_momentum_quality_score`.
4. Remove MACD and BOLL from entry scoring responsibilities.
5. Keep EMA and CVD, but make them confirmation layers after location gates.
6. Add a hard cap: if price is at downside Fib extension exhaustion, SHORT cannot be DIRECT.
7. Add 5x constraint: 5x requires valid Fib pullback/retest location plus no exhaustion.

### P1 Validation

Run dry-run and backtest variants:

```text
A: current EMA+CVD agreement baseline
B: EMA+CVD+CCI only
C: EMA+CVD+CCI+price_action
D: EMA+CVD+CCI+price_action+fib
E: D with 5x disabled unless Fib+PA location is valid
```

Metrics required:

- Win rate
- Profit factor
- Realized PnL
- Max drawdown
- Initial stop rate
- Breakeven stop rate
- TP3 rate
- Average initial stop loss
- Average TP path profit
- 5x PnL contribution
- Trade count
- Exposure time

Verification command placeholder for implementation phase:

```bash
pytest tests/test_entry_chain_features.py tests/test_entry_chain.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_highest_win.json --simulated-hold-bars 2 --cooldown-bars 8 --run-id fib_pa_refactor_baseline
```

The exact backtest command should be adjusted after the new config file exists.

---

## 11. Questions For Claude

1. Should Fibonacci be a hard gate or a multiplier?
2. What swing algorithm is least likely to overfit on 15m crypto data?
3. Should Fib be computed from 1h swings, 15m swings, or both?
4. Should CCI replace MACD fully as the momentum/exhaustion layer, or should CCI only be used as a cap?
5. Should 5x be disabled until Fib/PA validation produces at least 30 closed trades with PF > 1.2?
6. Should TONUSDT be put into observation-only after two opposite-side initial stops?
7. Does the BNB 2026-06-25 cluster imply a market-wide regime filter is needed in addition to symbol cooldown?

---

## 12. Bottom Line

The current strategy can find directional moves, but it still enters too late. The losing trades are not random symbol failures. They are mostly late-location failures after trend agreement becomes obvious.

Replacing MACD/BOLL responsibilities with price action and Fibonacci is directionally reasonable, but it must be implemented as a location-first architecture:

```text
Price location first.
Then EMA/CVD/CCI confirmation.
Then score.
Then leverage.
```

If this order is not enforced, the same problem will remain under new indicator names.

