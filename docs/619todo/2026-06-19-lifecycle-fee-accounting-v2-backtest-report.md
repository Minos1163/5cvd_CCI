# Lifecycle Fee Accounting V2 Backtest Report

Date: 2026-06-19

Purpose: supersede the first lifecycle report with fee-audited partial exits, breakeven buffer, shorter max hold, and corrected Probe rejection semantics. This is research evidence only and does not approve live trading.

---

## What Changed From V1

V2 fixes the review's critical accounting concern:

- ATR/TP exits now record explicit `partial_exits`.
- Fees are computed from actual partial exit notional.
- Breakeven stop includes a `0.1%` buffer.
- TP fractions changed from `30/40/30` to `40/35/25`.
- Max hold changed from `96` bars to `16` bars.
- Probe disabled now returns `NO_TRADE` with `PROBE_DISABLED`.

Important clarification:

- V2 does not charge a full-position exit fee three times.
- It charges fees on the actual exited fraction at each partial fill.
- Full TP ladder round-trip fee is approximately one entry fee plus one full-position exit fee, distributed across TP1/TP2/TP3.

---

## Theory Check

Command:

```powershell
python scripts/verify_lifecycle_logic.py
```

Output:

```text
avg_win_gross=0.027750
avg_loss_gross=-0.015000
round_trip_fee=0.001000
expectancy=0.011787
```

Interpretation:

- At 65% win rate, 1.5% stop distance, 1R/2R/3R TP ladder, and 40/35/25 fractions, the theoretical expectancy remains positive after corrected fees.

---

## Runs Compared

| Run ID | Exit / Config | Status |
| --- | --- | --- |
| `latest_30d_ema_exp_c_soft` | EMA Soft, synthetic 2-bar exit | Prior ablation baseline |
| `latest_30d_ema_soft_lifecycle_hardened` | Lifecycle v1, 30/40/30, 96 bars | Superseded by v2 |
| `latest_30d_ema_soft_lifecycle_hardened_v2` | Lifecycle v2, 40/35/25, 16 bars, fee-audited partial exits | Current result |

V2 command:

```powershell
python scripts/run_offline_backtest.py --data-dir data/raw/binance_futures/latest_30d --timeframe 15m --strategy entry-chain --entry-chain-config configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json --exit-model atr_tp --atr-stop-mult 1.5 --tp-levels 1,2,3 --tp-fractions 0.4,0.35,0.25 --max-hold-bars 16 --default-atr-pct 0.010 --simulated-hold-bars 2 --cooldown-bars 8 --run-id latest_30d_ema_soft_lifecycle_hardened_v2
```

---

## Summary Metrics

| Metric | EMA Soft Synthetic | Lifecycle V1 | Lifecycle V2 |
| --- | ---: | ---: | ---: |
| Trades | 116 | 115 | 115 |
| 30D Return | -0.86% | +6.36% | +4.57% |
| Max Drawdown | 0.93% | 0.99% | 0.99% |
| Win Rate | 25.00% | 70.43% | 68.70% |
| Profit Factor | 0.6239 | 1.7085 | 1.5472 |
| Sharpe | -1.4251 | 2.0533 | 1.7579 |
| Sortino | -1.9924 | 4.7705 | 3.1854 |
| Expectancy | -0.7435 | +5.5323 | +3.9747 |

V2 interpretation:

- The lifecycle thesis still holds after fee-audited corrections.
- V1 was too optimistic and is superseded.
- V2 remains positive expectancy but still misses the aggressive user target.

---

## Fee Accounting

| Metric | Lifecycle V2 |
| --- | ---: |
| Gross PnL | 827.15 |
| Fees | 246.60 |
| Slippage | 123.46 |
| Net PnL | 457.09 |
| Cost / Gross PnL | 44.74% |
| Partial Exit Records | 224 |

Conclusion:

- Corrected costs are higher as a share of gross PnL than V1.
- Costs no longer invalidate the result, but they remain a large drag.
- Future work should add explicit exit-side slippage per partial fill; current slippage still only captures entry slippage.

---

## Exit Distribution

| Exit Reason | Trades | Net PnL | Win Rate |
| --- | ---: | ---: | ---: |
| `atr_tp_tp_ladder_complete` | 18 | +595.50 | 100.00% |
| `atr_tp_breakeven_stop_hit` | 35 | +211.27 | 100.00% |
| `atr_tp_max_hold_exit` | 35 | +356.49 | 74.29% |
| `atr_tp_stop_hit` | 27 | -706.17 | 0.00% |

Additional lifecycle stats:

- TP1 reached: `74 / 115`
- Breakeven active: `74 / 115`
- Average hold: `8.77` bars
- Winning trade average hold: `9.38` bars
- Losing trade average hold: `7.42` bars

Interpretation:

- Shorter max hold did not collapse profitability.
- Full TP ladder completion fell to 18 trades, but timeout exits became profitable in this window.
- Initial stop hits remain the main loss source.

---

## Side Attribution

| Side | Trades | Net PnL | Win Rate |
| --- | ---: | ---: | ---: |
| LONG | 24 | +80.34 | 50.00% |
| SHORT | 91 | +376.75 | 73.63% |

Interpretation:

- Shorts remain materially stronger than longs.
- Long trades are positive but still too weak for an 80% win-rate target.
- Keep side-specific thresholds.

---

## Symbol Attribution

| Symbol | Trades | Net PnL | Win Rate |
| --- | ---: | ---: | ---: |
| SOLUSDT | 26 | +150.58 | 73.08% |
| BNBUSDT | 20 | +119.99 | 75.00% |
| DOGEUSDT | 26 | +116.77 | 73.08% |
| XLMUSDT | 21 | +99.60 | 61.90% |
| ZECUSDT | 7 | +45.04 | 71.43% |
| TRXUSDT | 11 | +29.92 | 72.73% |
| ADAUSDT | 2 | -36.27 | 0.00% |
| XMRUSDT | 2 | -68.54 | 0.00% |

Interpretation:

- The profitable symbols are broad enough to avoid a single-symbol-only result.
- `ADAUSDT` and `XMRUSDT` remain small-sample drags.
- `XRPUSDT` blacklist remains justified for this research phase.

---

## Gate Answers

| Gate | Result | Pass |
| --- | --- | --- |
| Expectancy turned positive? | `+3.9747` per trade | Yes |
| Trade count >= 30? | `115` trades | Yes |
| Profit factor >= 1.0? | `1.5472` | Yes |
| Max drawdown <= 15%? | `0.99%` | Yes |
| `src/api/binance_client.py` unchanged? | Verified in final check | Yes |

Target gap:

- 30D return target: `50%+`; V2 result: `4.57%`.
- Win rate target: `80%+`; V2 result: `68.70%`.
- Trade count target: `90-120`; V2 result: `115`.

---

## Deployment Decision

Decision:

- Do not deploy live.
- Treat V2 as the corrected lifecycle baseline.
- Keep Probe disabled until it has a separate positive-expectancy test.
- Keep EMA200 soft, not hard.
- Keep XRPUSDT blacklisted for the next research window.

Next work:

1. Add exit-side slippage per partial exit.
2. Add MFE/MAE and stop-hit timing attribution.
3. Run rolling 30D windows across 6-12 months.
4. Compare max-hold values `8`, `16`, and `32` without changing entry rules.
5. Test long-only and short-only threshold profiles separately.

---

## Bottom Line

The review correctly forced a more conservative implementation. After adding partial-exit metadata, fee-audited lifecycle accounting, breakeven buffer, and a shorter hold cap, the strategy remains positive:

```text
+4.57% return, 68.70% win rate, 1.5472 profit factor, 115 trades
```

This validates the lifecycle direction but does not validate live deployment or the final `50%+ / 80%+` target.
