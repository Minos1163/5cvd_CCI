# Exit Lifecycle Probe Hardening Backtest Report

Date: 2026-06-19

Purpose: validate the hypothesis that EMA Soft improved entries, while the synthetic two-bar exit was suppressing realized edge. This is a research result only and does not approve live trading.

---

## Runs Compared

| Run ID | Entry Config | Exit Model | Purpose |
| --- | --- | --- | --- |
| `latest_30d_ema_exp_c_soft` | EMA Soft | synthetic two-bar exit | Prior best ablation baseline |
| `latest_30d_ema_soft_lifecycle_hardened` | EMA Soft hardened | ATR stop + TP1/TP2/TP3 | Test exit lifecycle plus Probe/XRP/long hardening |

Shared assumptions:

- Data: `data/raw/binance_futures/latest_30d`
- Timeframe: `15m`
- Fill: `NEXT_BAR_OPEN`
- Fee: `5 bps` per side
- Slippage: `5 bps`
- ATR stop multiplier: `1.5`
- TP ladder: `1R / 2R / 3R`
- TP fractions: `30% / 40% / 30%`
- Max holding time: `96` 15m bars

Hardened entry changes:

- Probe disabled.
- `XRPUSDT` blacklisted.
- Long-side thresholds raised by `+10` score points.
- EMA200 remains soft penalty, not hard gate.

---

## Summary Metrics

| Metric | EMA Soft Synthetic | EMA Soft Lifecycle Hardened |
| --- | ---: | ---: |
| Trades | 116 | 115 |
| 30D Return | -0.86% | +6.36% |
| Max Drawdown | 0.93% | 0.99% |
| Win Rate | 25.00% | 70.43% |
| Profit Factor | 0.6239 | 1.7085 |
| Sharpe | -1.4251 | 2.0533 |
| Sortino | -1.9924 | 4.7705 |
| Expectancy | -0.7435 | +5.5323 |
| Final Equity | 9913.75 | 10636.21 |

Interpretation:

- The exit lifecycle changed the strategy from negative expectancy to positive expectancy on this 30D window.
- Trade count stayed inside the user target range of `90-120`.
- The strategy still does not meet the user target of `50%+` 30D return and `80%+` win rate.

---

## Cost Attribution

| Metric | EMA Soft Synthetic | EMA Soft Lifecycle Hardened |
| --- | ---: | ---: |
| Gross PnL | 96.63 | 1009.90 |
| Fees | 121.90 | 249.01 |
| Slippage | 60.98 | 124.68 |
| Total Costs | 182.88 | 373.68 |
| Net PnL | -86.25 | +636.21 |
| Cost / Gross PnL | 189.25% | 37.00% |

Root finding:

- The prior synthetic exit did not allow winners to expand enough to cover friction.
- The lifecycle exit increased gross PnL by more than 10x while trade count stayed nearly unchanged.
- Costs remain material, but they no longer exceed gross edge.

---

## Side Attribution

| Side | Trades | Net PnL | Win Rate |
| --- | ---: | ---: | ---: |
| LONG | 24 | +149.90 | 54.17% |
| SHORT | 91 | +486.31 | 74.73% |

Interpretation:

- Short signals remain the stronger side.
- Long hardening helped reduce weak long exposure, but long win rate is still below target.
- The next calibration should keep long-side thresholds separate from short-side thresholds.

---

## Mode Attribution

| Mode | Trades | Net PnL | Win Rate |
| --- | ---: | ---: | ---: |
| DIRECT | 115 | +636.21 | 70.43% |

Interpretation:

- Disabling Probe did not collapse trade count.
- Given the prior Probe result of 77 trades, -64.86 net PnL, and 16.88% win rate, Probe should remain disabled until the full lifecycle engine proves a positive Probe expectancy separately.

---

## Symbol Attribution

| Symbol | Trades | Net PnL | Win Rate |
| --- | ---: | ---: | ---: |
| SOLUSDT | 26 | +230.46 | 80.77% |
| DOGEUSDT | 26 | +165.69 | 76.92% |
| BNBUSDT | 20 | +140.38 | 75.00% |
| XLMUSDT | 21 | +130.28 | 61.90% |
| ZECUSDT | 7 | +45.46 | 57.14% |
| TRXUSDT | 11 | +30.56 | 72.73% |
| ADAUSDT | 2 | -36.90 | 0.00% |
| XMRUSDT | 2 | -69.71 | 0.00% |

Interpretation:

- `SOLUSDT`, `DOGEUSDT`, and `BNBUSDT` carried the run.
- `XRPUSDT` removal was justified for this window; it was the largest prior drag.
- `ADAUSDT` and `XMRUSDT` need monitoring, but sample size is too small to permanently blacklist.

---

## Exit Attribution

| Exit Reason | Trades | Net PnL | Win Rate |
| --- | ---: | ---: | ---: |
| `atr_tp_tp_ladder_complete` | 35 | +1300.28 | 100.00% |
| `atr_tp_breakeven_stop_hit` | 44 | +220.89 | 100.00% |
| `atr_tp_stop_hit` | 33 | -869.62 | 0.00% |
| `atr_tp_max_hold_exit` | 3 | -15.33 | 66.67% |

Interpretation:

- The profitable structure came from allowing full TP ladders and preserving partial gains after TP1.
- Initial stops remain expensive. Stop quality and entry timing still need improvement.
- Max-hold exits are rare, so the `96` bar timeout is not dominating the result.

---

## Target Gap

User target:

- Floating leverage: `3x`, `4x`, `5x`
- Single-symbol floating exposure: `20%-30%`
- Max active symbols: `5`
- 30D return: `50%+`
- Win rate: `80%+`
- 30D openings: `90-120`

Current hardened research run:

- 30D return: `+6.36%`
- Win rate: `70.43%`
- Trades: `115`
- Profit factor: `1.7085`
- Max drawdown: `0.99%`

Conclusion:

- Trade count target is met.
- Profitability is now positive.
- Win rate is still about `9.57` percentage points below target.
- Return is still far below the aggressive `50%+` target.

---

## Remaining Limitations

- `BacktestTrade` still stores one weighted average exit price, not separate child fills for TP1/TP2/TP3.
- The engine processes symbols sequentially, so portfolio concurrency is still an approximation.
- Funding remains approximated as zero in this run.
- Exit ordering is conservative when stop and TP hit in the same bar, but true intrabar path is unknown from OHLCV.
- This is a single 30D window. It is not enough evidence for live deployment.

---

## Deployment Decision

Decision:

- Do not deploy to live trading.
- Keep EMA Soft plus ATR/TP lifecycle as the current best research direction.
- Keep Probe disabled until separately validated.
- Keep XRPUSDT blacklisted for the next research round.
- Keep EMA200 as a soft penalty, not a hard gate.

Next work:

1. Convert weighted average exits into explicit child fills so TP1/TP2/TP3 are auditable.
2. Run rolling 30D windows across at least 6 months.
3. Test a short-biased profile and a stricter long profile separately.
4. Add MFE/MAE and stop-distance attribution.
5. Revisit leverage only after out-of-sample profit factor exceeds `1.8` and win rate approaches `75%-80%`.

---

## Bottom Line

The user's diagnosis was correct: the entry architecture had improved, but the synthetic exit architecture was erasing the edge.

Replacing the two-bar exit with ATR stop plus a three-stage TP ladder moved the best 30D run from:

```text
-0.86% return, 25.00% win rate, 0.6239 profit factor
```

to:

```text
+6.36% return, 70.43% win rate, 1.7085 profit factor
```

This is a meaningful research breakthrough, but it is not the final strategy target. The system is now worth deeper validation; it is not yet ready for real capital.
