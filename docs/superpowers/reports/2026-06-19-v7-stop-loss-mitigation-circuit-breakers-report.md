# V7 Stop Loss Mitigation Circuit Breakers Report

Date: 2026-06-19

Purpose: test whether leveraged stop-loss damage can be reduced by adding lifecycle partial de-risk exits and daily/weekly loss circuit breakers. This is research evidence only. It does not approve live trading.

---

## Frozen Controls

- Entry config: `configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json`
- Leverage: dynamic signal leverage, clamped `3x-5x`
- Data: `data/raw/binance_futures/latest_30d`
- Timeframe: `15m`
- Fill: `NEXT_BAR_OPEN`
- Exit model: `atr_tp`
- Hold cap: `32`
- Fee: `5 bps`
- Slippage: `5 bps`, including exit-side partial slippage
- TP levels: `1R / 2R / 3R`
- TP fractions: `40% / 35% / 25%`
- ATR stop multiplier: `1.5`
- Probe: disabled
- Blacklist: `XRPUSDT`

V7 changed lifecycle de-risking and optional entry circuit breakers only. V5 entry acceptance and V6 leverage accounting remained frozen.

---

## Runs

| Run ID | Change |
| --- | --- |
| `latest_30d_v6_v5_combined_dynamic_3x5x` | V6 dynamic 3x-5x benchmark |
| `latest_30d_v7_dynamic_3x5x_adverse_reduce` | 0.6R adverse 50% reduction only |
| `latest_30d_v7_dynamic_3x5x_time_reduce` | 12-bar stalled-trade 50% reduction only |
| `latest_30d_v7_dynamic_3x5x_derisk_circuit` | adverse + time reduction + daily/weekly hard-loss circuit |

V7 rules:

- Adverse reduction: close 50% at `0.6R` adverse move if volume spike is present.
- Time reduction: close 50% after 12 bars if TP1 has not been reached and profit is below `0.3R`.
- Circuit breakers: daily hard loss `5%`, weekly hard loss `12%`, blocking new entries only.

---

## Headline Comparison

| Run | Return | Trades | Win Rate | PF | Max DD | Sharpe | Sortino | Expectancy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V6 Dynamic 3-5x | +40.21% | 113 | 76.99% | 2.1277 | 6.09% | 2.7812 | 5.1004 | +35.5805 |
| V7 Adverse Reduce | +19.32% | 113 | 69.91% | 1.5939 | 5.71% | 1.6421 | 2.3273 | +17.0983 |
| V7 Time Reduce | +39.06% | 113 | 76.99% | 2.2299 | 6.09% | 2.8546 | 5.2557 | +34.5672 |
| V7 Combined + Circuit | +18.03% | 112 | 69.64% | 1.6022 | 5.71% | 1.6319 | 2.4444 | +16.0994 |

Best return remains:

```text
latest_30d_v6_v5_combined_dynamic_3x5x
```

Best V7 risk-adjusted candidate:

```text
latest_30d_v7_dynamic_3x5x_time_reduce
```

---

## Stop-Loss Attribution

| Run | Stop Trades | Stop Net | TP3 Count | De-risk Count |
| --- | ---: | ---: | ---: | ---: |
| V6 Dynamic 3-5x | 25 | -3520.65 | 25 | 0 |
| V7 Adverse Reduce | 25 | -3178.05 | 19 | 23 adverse |
| V7 Time Reduce | 25 | -3128.43 | 22 | 14 time |
| V7 Combined + Circuit | 25 | -2823.40 | 17 | 23 adverse, 14 time |

Interpretation:

- V7 did reduce stop net loss.
- But adverse reduction cut too much profitable continuation.
- The adverse-only run reduced stop damage by about `342.59` USDT versus V6, but total net PnL fell by about `2088.49` USDT.
- The combined run reduced stop damage the most, but TP3 completions collapsed from `25` to `17`, and total return fell to `18.03%`.
- Time reduction is less destructive: it reduces stop damage by about `392.22` USDT while keeping win rate unchanged and improving PF/Sharpe.

---

## Cost Drag

| Run | Gross PnL | Fees | Slippage | Net PnL | Cost / Gross |
| --- | ---: | ---: | ---: | ---: | ---: |
| V6 Dynamic 3-5x | 6403.83 | 1191.52 | 1191.71 | 4020.60 | 37.22% |
| V7 Adverse Reduce | 4190.78 | 1129.25 | 1129.42 | 1932.10 | 53.90% |
| V7 Time Reduce | 6259.71 | 1176.72 | 1176.90 | 3906.09 | 37.60% |
| V7 Combined + Circuit | 4016.79 | 1106.74 | 1106.91 | 1803.13 | 55.11% |

Interpretation:

- Adverse reduction lowered gross PnL much faster than it lowered costs.
- Time reduction preserved gross edge and kept cost/gross close to V6.
- Combined V7 is not viable with current adverse reduction parameters.

---

## Circuit Breakers

| Run | Risk Blocks | Reason |
| --- | ---: | --- |
| V6 Dynamic 3-5x | 0 | none |
| V7 Adverse Reduce | 0 | none |
| V7 Time Reduce | 0 | none |
| V7 Combined + Circuit | 1 | `DAILY_HARD_LOSS_CIRCUIT` |

Interpretation:

- Daily hard-loss circuit triggered once in the combined run.
- The circuit did not rescue the run because most damage came from adverse de-risking reducing gross upside, not from an uncontrolled cluster of new entries.
- Circuit breakers should remain in the framework for rolling-window risk control, but they do not solve this latest-30D target gap.

---

## Side Attribution

| Run | Long Net | Long Win | Short Net | Short Win |
| --- | ---: | ---: | ---: | ---: |
| V6 Dynamic 3-5x | +1842.73 | 73.68% | +2177.87 | 77.66% |
| V7 Adverse Reduce | +851.34 | 68.42% | +1080.76 | 70.21% |
| V7 Time Reduce | +1745.00 | 73.68% | +2161.09 | 77.66% |
| V7 Combined + Circuit | +764.94 | 68.42% | +1038.19 | 69.89% |

Interpretation:

- Adverse reduction harms both sides and lowers win rate.
- Time reduction preserves side quality and only modestly reduces net.
- The current adverse trigger is too aggressive for this lifecycle geometry.

---

## Target Gap

User target:

- 30D return: `50%+`
- Win rate: `80%+`
- Trades: `90-120`
- Dynamic leverage: `3x / 4x / 5x`

Best V7 result:

- Return: `+39.06%`
- Win rate: `76.99%`
- Trades: `113`

Result:

- Trade count remains target-compliant.
- Win rate remains below `80%`.
- Return remains below `50%`.
- V7 does not beat V6 dynamic 3-5x on return.

---

## Decision

Reject for current promotion:

```text
0.6R adverse 50% reduction with volume spike
```

Reason:

- It reduces stop damage but destroys too much upside.
- It drops win rate from `76.99%` to `69.91%`.
- It increases cost/gross from `37.22%` to `53.90%`.

Keep for further research:

```text
12-bar stalled time reduction
```

Reason:

- It keeps win rate unchanged.
- It improves PF from `2.1277` to `2.2299`.
- It improves Sharpe from `2.7812` to `2.8546`.
- It slightly lowers return from `40.21%` to `39.06%`, which may be acceptable if rolling windows show lower tail risk.

Current best baseline remains:

```text
latest_30d_v6_v5_combined_dynamic_3x5x
```

Current best V7 candidate:

```text
latest_30d_v7_dynamic_3x5x_time_reduce
```

---

## Root Cause

The thesis "reduce stop damage to cross 50%" was only partially correct.

What happened:

- Stop damage fell.
- But adverse reduction also reduced the payoff of trades that would later reach TP2/TP3 or recover through breakeven.
- This cut gross edge and lowered win rate.
- The strategy's current edge depends on allowing many trades enough room to recover after moderate adverse excursion.

The practical lesson:

```text
V7 should not cut at 0.6R simply because volume expands.
The trigger must distinguish genuine failure from normal noise before reducing size.
```

---

## Next Research Step

Use time reduction as the conservative candidate and redesign adverse reduction:

1. Raise adverse trigger from `0.6R` to `0.8R` or `1.0R`.
2. Require no TP1 and weak MFE before adverse reduction.
3. Require side-specific trigger:
   - stricter for longs,
   - looser or disabled for shorts.
4. Test reduced fraction `25%` instead of `50%`.
5. Run rolling windows before accepting time reduction despite its better PF/Sharpe.

---

## Bottom Line

V7 is useful but not a promotion over V6.

The best V7 variant improves risk-adjusted metrics but does not increase return:

```text
V7 Time Reduce: +39.06%, PF 2.2299, Sharpe 2.8546
```

The current best latest-30D return remains:

```text
V6 Dynamic 3-5x: +40.21%, PF 2.1277, Sharpe 2.7812
```

The target is still not met. The next useful move is not more aggressive de-risking; it is better adverse-trigger selectivity plus rolling-window validation.
