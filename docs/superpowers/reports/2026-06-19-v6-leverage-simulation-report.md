# V6 Leverage Simulation Report

Date: 2026-06-19

Purpose: add research-only 3x-5x leverage accounting to the offline backtest and evaluate V5 combined under fixed and dynamic leverage. This does not approve live trading.

---

## Accounting Model

V6 changes only the research backtest accounting:

- `notional` remains margin notional.
- `effective_notional = margin_notional * leverage`.
- Quantity, gross PnL, fees, slippage, and funding use effective notional.
- `BacktestTrade` now records `leverage`, `margin_notional`, `effective_notional`, and `margin_call_proxy`.
- Margin-call proxy triggers when adverse excursion breaches an approximate liquidation buffer:

```text
abs(MAE) >= (1 / leverage) - maintenance_margin_pct
```

This is not a full exchange liquidation engine. It does not model exchange-specific maintenance tiers, mark-price liquidation, funding intervals, order-book depth, ADL, or forced liquidation fees.

---

## Frozen Strategy Controls

- Config: `configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json`
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

---

## Runs

| Run ID | Leverage |
| --- | --- |
| `latest_30d_v5_symbol_bucket_long_context` | Unlevered reference |
| `latest_30d_v6_v5_combined_fixed_3x` | Fixed 3x |
| `latest_30d_v6_v5_combined_fixed_4x` | Fixed 4x |
| `latest_30d_v6_v5_combined_fixed_5x` | Fixed 5x |
| `latest_30d_v6_v5_combined_dynamic_3x5x` | Entry-chain signal leverage, clamped 3x-5x |

---

## Headline Comparison

| Run | Return | Trades | Win Rate | PF | Max DD | Sharpe | Sortino | Expectancy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V5 Unlevered | +7.69% | 113 | 76.99% | 2.0752 | 1.54% | 2.7437 | 5.0026 | +6.8069 |
| V6 Fixed 3x | +24.61% | 113 | 76.99% | 2.0627 | 4.59% | 2.6943 | 4.8528 | +21.7775 |
| V6 Fixed 4x | +33.89% | 113 | 76.99% | 2.0566 | 6.09% | 2.6694 | 4.7763 | +29.9873 |
| V6 Fixed 5x | +43.74% | 113 | 76.99% | 2.0506 | 7.58% | 2.6445 | 4.6992 | +38.7119 |
| V6 Dynamic 3-5x | +40.21% | 113 | 76.99% | 2.1277 | 6.09% | 2.7812 | 5.1004 | +35.5805 |

Best nominal return:

```text
latest_30d_v6_v5_combined_fixed_5x
```

Best risk-adjusted leveraged candidate:

```text
latest_30d_v6_v5_combined_dynamic_3x5x
```

---

## Cost Drag

| Run | Gross PnL | Fees | Slippage | Net PnL | Cost / Gross |
| --- | ---: | ---: | ---: | ---: | ---: |
| V5 Unlevered | 1254.14 | 242.46 | 242.50 | 769.18 | 38.67% |
| V6 Fixed 3x | 4010.86 | 774.94 | 775.06 | 2460.86 | 38.65% |
| V6 Fixed 4x | 5521.88 | 1066.57 | 1066.75 | 3388.56 | 38.63% |
| V6 Fixed 5x | 7127.22 | 1376.28 | 1376.50 | 4374.44 | 38.62% |
| V6 Dynamic 3-5x | 6403.83 | 1191.52 | 1191.71 | 4020.60 | 37.22% |

Interpretation:

- Costs scale with effective notional as intended.
- Cost/gross stays stable in fixed leverage runs.
- Dynamic leverage has slightly better cost/gross because it does not apply 5x to every trade.

---

## Risk And Margin Proxy

| Run | Max DD | Stop Trades | Stop Net | Leverage Distribution | Margin Proxy |
| --- | ---: | ---: | ---: | --- | ---: |
| V5 Unlevered | 1.54% | 25 | -705.36 | 1x: 113 | 0 |
| V6 Fixed 3x | 4.59% | 25 | -2283.67 | 3x: 113 | 0 |
| V6 Fixed 4x | 6.09% | 25 | -3163.00 | 4x: 113 | 0 |
| V6 Fixed 5x | 7.58% | 25 | -4106.92 | 5x: 113 | 0 |
| V6 Dynamic 3-5x | 6.09% | 25 | -3520.65 | 4x: 71, 5x: 42 | 0 |

Interpretation:

- No margin-call proxy event occurred in this 30D sample.
- Stop-hit count stays at 25 because leverage does not change entry or exit path in this model.
- Stop-hit damage scales aggressively with leverage.
- Fixed 5x has the highest return but the worst drawdown and weakest leveraged Sharpe.
- Dynamic 3-5x keeps fixed-4x drawdown with higher return and better PF/Sharpe.

---

## Side Attribution

| Run | Long Net | Long Win | Short Net | Short Win |
| --- | ---: | ---: | ---: | ---: |
| V5 Unlevered | +349.01 | 73.68% | +420.17 | 77.66% |
| V6 Fixed 3x | +1160.42 | 73.68% | +1300.43 | 77.66% |
| V6 Fixed 4x | +1627.89 | 73.68% | +1760.67 | 77.66% |
| V6 Fixed 5x | +2140.07 | 73.68% | +2234.37 | 77.66% |
| V6 Dynamic 3-5x | +1842.73 | 73.68% | +2177.87 | 77.66% |

Interpretation:

- Win rate is unchanged because leverage affects accounting, not signal path.
- Both sides remain positive.
- Shorts remain the larger net contributor, but V5's repaired long side still scales well under leverage.

---

## Target Gap

User target:

- 30D return: `50%+`
- Win rate: `80%+`
- Trades: `90-120`
- Floating leverage: `3x / 4x / 5x`

Best V6 result:

- Fixed 5x return: `+43.74%`
- Dynamic 3-5x return: `+40.21%`
- Win rate: `76.99%`
- Trades: `113`

Result:

- Trade-count target is met.
- Leverage requirement is now modeled.
- Win-rate target is still not met.
- 50% return target is still not met, even at fixed 5x in this audited cost model.

---

## Decision

Best research candidate:

```text
latest_30d_v6_v5_combined_dynamic_3x5x
```

Reason:

- It delivers `+40.21%` return versus `+43.74%` for fixed 5x.
- It keeps max drawdown at `6.09%`, matching fixed 4x and materially below fixed 5x.
- It has the best leveraged PF, Sharpe, and Sortino in this set.
- It uses actual entry-chain leverage selection instead of forcing maximum leverage on every trade.

Reject for promotion:

- Fixed 5x as a default operating mode.
- Any claim that the 50% / 80% target is now achieved.
- Any live deployment based on a single latest-30D leveraged run.

---

## Required Next Work

1. Run rolling 30D windows across 6-12 months for:
   - V5 unlevered,
   - V6 fixed 3x,
   - V6 dynamic 3-5x.
2. Add a stricter drawdown gate:
   - If rolling max DD exceeds `10%` at 3x or `15%` at dynamic leverage, reject leverage promotion.
3. Add daily loss cut simulation:
   - 3% daily loss cuts leverage to 3x or disables new entries for the rest of day.
4. Add side exposure limits:
   - Long active symbols <= 2,
   - short active symbols <= 3,
   - long exposure <= 60% margin notional,
   - short exposure <= 80% margin notional.
5. Add exchange-like liquidation modeling before any live leverage discussion.

---

## Bottom Line

V6 successfully adds 3x-5x leverage simulation and shows that V5's edge scales, but not enough to honestly claim the target is reached.

The strongest result is:

```text
Fixed 5x: +43.74%, 76.99% win rate, 113 trades, 7.58% max DD
```

The better research candidate is:

```text
Dynamic 3-5x: +40.21%, 76.99% win rate, 113 trades, 6.09% max DD
```

This is close to the aggressive return target, but still short of `50%+` and `80%+`. The next proof must be rolling-window stability plus daily-loss and liquidation modeling.
