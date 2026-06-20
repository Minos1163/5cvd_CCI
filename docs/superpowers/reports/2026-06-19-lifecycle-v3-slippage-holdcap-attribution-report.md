# Lifecycle V3 Slippage Holdcap Attribution Report

Date: 2026-06-19

Purpose: test whether the V2 lifecycle edge survives exit-side slippage and hold-cap variation. This is research evidence only and does not approve live trading.

---

## Fixed Assumptions

- Data: `data/raw/binance_futures/latest_30d`
- Timeframe: `15m`
- Entry config: `configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json`
- Probe: disabled
- XRPUSDT: blacklisted
- EMA200: soft penalty
- Fill: next bar open
- Fee: `5 bps`
- Base slippage: `5 bps`
- Stress slippage: `6.25 bps`
- ATR stop multiplier: `1.5`
- TP levels: `1R / 2R / 3R`
- TP fractions: `40% / 35% / 25%`
- Breakeven buffer: `0.1%`

V3 added:

- Exit-side slippage per partial exit.
- `entry_slippage` and `exit_slippage` fields.
- MFE / MAE attribution.
- Stop-hit bar-offset attribution.

---

## Experiment Grid

| Run ID | Hold Bars | Slippage |
| --- | ---: | ---: |
| `latest_30d_lifecycle_v3_hold8` | 8 | 5 bps |
| `latest_30d_lifecycle_v3_hold16` | 16 | 5 bps |
| `latest_30d_lifecycle_v3_hold32` | 32 | 5 bps |
| `latest_30d_lifecycle_v3_hold32_slip125` | 32 | 6.25 bps |

---

## Summary Metrics

| Run | Return | Trades | Win Rate | PF | Max DD | Sharpe | Sortino | Expectancy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Hold 8 | +2.91% | 115 | 63.48% | 1.3455 | 0.97% | 1.1901 | 1.9833 | +2.5339 |
| Hold 16 | +3.33% | 115 | 67.83% | 1.3828 | 1.03% | 1.2882 | 2.2746 | +2.8921 |
| Hold 32 | +3.98% | 115 | 70.43% | 1.4332 | 1.03% | 1.4569 | 2.9911 | +3.4578 |
| Hold 32 Slip +25% | +3.09% | 115 | 68.70% | 1.3213 | 1.05% | 1.1309 | 2.3401 | +2.6853 |

Interpretation:

- Positive expectancy survives exit-side slippage.
- Hold 32 is best in this latest-30D window.
- Slippage stress remains positive, but edge thins quickly.
- No run reaches the target of `50%+` 30D return or `80%+` win rate.

---

## Cost Drag

| Run | Gross PnL | Fees | Entry Slip | Exit Slip | Net PnL | Cost / Gross |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Hold 8 | 781.22 | 244.89 | 122.67 | 122.26 | 291.40 | 62.70% |
| Hold 16 | 822.90 | 245.13 | 122.73 | 122.44 | 332.59 | 59.58% |
| Hold 32 | 889.96 | 246.14 | 123.23 | 122.94 | 397.64 | 55.32% |
| Hold 32 Slip +25% | 860.17 | 245.02 | 153.35 | 152.99 | 308.81 | 64.10% |

Interpretation:

- Exit-side slippage materially reduces the headline result.
- Cost/gross remains above `55%` even in the best run.
- The strategy has positive edge, but the margin of safety is narrow.

---

## Best Run Details: Hold 32

Best run:

```text
latest_30d_lifecycle_v3_hold32
```

Headline:

- Return: `+3.98%`
- Win rate: `70.43%`
- Profit factor: `1.4332`
- Trade count: `115`
- Max drawdown: `1.03%`

Average path:

- Average MFE: `1.61%`
- Average MAE: `-0.66%`
- Average hold: `11.12` bars

---

## Side Attribution

| Side | Trades | Net PnL | Win Rate | Fees | Slippage | Avg MFE | Avg MAE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| LONG | 24 | +80.43 | 54.17% | 53.11 | 53.10 | 2.23% | -0.95% |
| SHORT | 91 | +317.21 | 74.73% | 193.03 | 193.08 | 1.45% | -0.58% |

Interpretation:

- Shorts remain the main edge source.
- Longs have larger favorable excursions but much weaker win rate, which suggests poor timing or wider adverse noise.
- Long and short should not share identical thresholds in later research.

---

## Symbol Attribution

| Symbol | Trades | Net PnL | Win Rate | Total Cost |
| --- | ---: | ---: | ---: | ---: |
| SOLUSDT | 26 | +176.62 | 80.77% | 105.60 |
| DOGEUSDT | 26 | +135.55 | 76.92% | 107.12 |
| BNBUSDT | 20 | +81.98 | 75.00% | 101.87 |
| XLMUSDT | 21 | +73.98 | 61.90% | 86.44 |
| ZECUSDT | 7 | +20.22 | 57.14% | 29.28 |
| TRXUSDT | 11 | +17.76 | 72.73% | 45.16 |
| ADAUSDT | 2 | -38.19 | 0.00% | 8.43 |
| XMRUSDT | 2 | -70.28 | 0.00% | 8.42 |

Interpretation:

- SOL, DOGE, and BNB are the current core contributors.
- ADA and XMR remain weak but small-sample.
- Symbol bucketing is now justified: core / secondary / watch-only.

---

## Exit Reason Attribution

| Exit Reason | Trades | Net PnL | Win Rate | Avg MFE | Avg MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| `atr_tp_tp_ladder_complete` | 26 | +818.98 | 100.00% | 3.47% | -0.42% |
| `atr_tp_breakeven_stop_hit` | 46 | +301.37 | 100.00% | 1.32% | -0.33% |
| `atr_tp_max_hold_exit` | 11 | +156.33 | 81.82% | 1.74% | -0.65% |
| `atr_tp_stop_hit` | 32 | -879.04 | 0.00% | 0.48% | -1.32% |

Interpretation:

- TP ladder and breakeven logic work.
- Stop hits are still the dominant loss engine.
- Stop-hit trades have very low MFE, meaning many failures did not get meaningful follow-through before adverse movement.

---

## TP Sequence Histogram

| Sequence | Trades |
| --- | ---: |
| `TP1_HIT>BREAKEVEN_STOP_HIT` | 34 |
| `STOP_HIT` | 32 |
| `TP1_HIT>TP2_HIT>TP3_HIT` | 26 |
| `TP1_HIT>TP2_HIT>BREAKEVEN_STOP_HIT` | 12 |
| `TP1_HIT>TP2_HIT>MAX_HOLD_EXIT` | 5 |
| `MAX_HOLD_EXIT` | 4 |
| `TP1_HIT>MAX_HOLD_EXIT` | 2 |

Interpretation:

- TP1 is frequently reached.
- The system often de-risks but does not always trend to TP3.
- The failure path is still large: 32 trades hit stop before TP1.

---

## Stop Timing

Early stop hits:

- Bar 1: `4` trades, `-102.31`
- Bar 2: `9` trades, `-122.53`
- Bar 3: `14` trades, `-78.64`
- Bar 4: `6` trades, `-101.72`
- Bar 6: `5` trades, `-130.84`

Interpretation:

- Many losses arrive within the first 3-6 bars.
- This points more toward entry timing / trigger quality than max-hold tuning.
- Widening stops would likely increase loss size unless position size is reduced.

---

## Target Gap

User target:

- 30D return: `50%+`
- Win rate: `80%+`
- Trades: `90-120`
- Floating leverage: `3x/4x/5x`
- Per-symbol exposure: `20%-30%`
- Max active symbols: `5`

Best V3 result:

- 30D return: `+3.98%`
- Win rate: `70.43%`
- Trades: `115`
- Profit factor: `1.4332`

Result:

- Trade count target is met.
- Win rate target is not met.
- Return target is not met.
- Increasing leverage to force the return target would amplify a still-unresolved stop-hit problem.

---

## Root Cause Attribution

The strategy did not reach target because:

- Cost drag is too high: best run cost/gross is `55.32%`.
- Stop-hit losses are too large: `32` stop-hit trades lose `-879.04`.
- Long-side win rate is weak: `54.17%`.
- The best run depends heavily on shorts and a few core symbols.
- Exit-side slippage cuts V2's apparent edge materially.

The positive finding:

- Even with exit-side slippage and a 25% slippage stress, expectancy stays positive.

The negative finding:

- The edge is not strong enough for the stated aggressive return and win-rate targets.

---

## Decision

Do not deploy live.

Keep as research baseline:

- Entry config fixed.
- Probe disabled.
- XRP blacklist active.
- Lifecycle with partial-exit accounting.
- Exit-side slippage enabled.

Best latest-30D research profile:

```text
hold cap = 32 bars
base slippage = 5 bps
return = +3.98%
win rate = 70.43%
PF = 1.4332
```

Next single experiment:

- Improve entry quality by splitting long and short thresholds while keeping hold32 and exit-side slippage fixed.

Why:

- The largest remaining weakness is not TP geometry.
- It is stop-hit before meaningful follow-through, especially around weaker side/symbol regimes.

---

## Bottom Line

V3 gives a more conservative and more useful answer than V2:

```text
The lifecycle edge survives exit-side slippage, but it is not yet strong enough.
```

The path to the target is not more leverage right now. The path is:

```text
reduce stop-hit rate,
separate long/short profiles,
rank symbols,
then validate across rolling windows.
```
