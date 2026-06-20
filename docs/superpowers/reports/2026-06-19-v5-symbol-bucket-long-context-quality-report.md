# V5 Symbol Bucket Long Context Quality Report

Date: 2026-06-19

Purpose: test whether V3 hold32 can be improved by isolating symbol buckets and replacing V4's blunt long hard-threshold tightening with context-aware long discounts. This is research evidence only. It does not approve live trading.

---

## Frozen Controls

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
- Breakeven buffer: `0.1%`
- Probe: disabled
- Blacklist: `XRPUSDT`

Only entry acceptance changed.

---

## Runs

| Run ID | Change |
| --- | --- |
| `latest_30d_lifecycle_v3_hold32` | V3 benchmark |
| `latest_30d_v4_side_split` | Rejected V4 blunt long hard-threshold profile |
| `latest_30d_v4_side_symbol_bucket` | V4 side split plus ADA/XMR watch-only |
| `latest_30d_v5_symbol_bucket_only` | V3 plus ADA/XMR watch-only only |
| `latest_30d_v5_long_context_discount` | V3 plus long-only context discounts |
| `latest_30d_v5_symbol_bucket_long_context` | V5 symbol bucket plus long context discounts |

V5 long context discounts:

- Long overextension: completed 15m close above the 20-bar Bollinger upper band discounts `quality_30m` and `ema_50_quality`.
- Upper wick risk: latest completed 15m upper wick >= 2x body discounts `trigger_15m`.
- Chase risk: last 8 completed 15m bars move up more than `2 * ATR pct` discounts `trigger_15m`.
- Weak CVD: weak `cvd_flow` discounts the CVD component.
- Low-liquidity UTC session: UTC 22/23/00 with depressed recent volume caps long action at `WATCH`.

All V5 flags use completed 15m bars available at decision time.

---

## Headline Comparison

| Run | Return | Trades | Win Rate | PF | Max DD | Sharpe | Sortino | Expectancy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V3 Hold32 | +3.98% | 115 | 70.43% | 1.4332 | 1.03% | 1.4569 | 2.9911 | +3.4578 |
| V4 Side Split | +1.79% | 115 | 67.83% | 1.1823 | 1.82% | 0.6876 | 1.4095 | +1.5602 |
| V4 Side + Symbol | +2.73% | 113 | 69.91% | 1.3050 | 1.73% | 1.0719 | 2.1252 | +2.4153 |
| V5 Symbol Bucket | +4.93% | 113 | 72.57% | 1.5967 | 0.97% | 1.8544 | 3.6678 | +4.3641 |
| V5 Long Context | +6.71% | 115 | 74.78% | 1.8294 | 1.54% | 2.3287 | 4.4581 | +5.8362 |
| V5 Combined | +7.69% | 113 | 76.99% | 2.0752 | 1.54% | 2.7437 | 5.0026 | +6.8069 |

Best run:

```text
latest_30d_v5_symbol_bucket_long_context
```

V5 combined beats V3 on return, win rate, profit factor, Sharpe, Sortino, expectancy, and trade count remains inside the target range.

---

## Cost Drag

| Run | Gross PnL | Fees | Slippage | Net PnL | Cost / Gross |
| --- | ---: | ---: | ---: | ---: | ---: |
| V3 Hold32 | 889.96 | 246.14 | 246.17 | 397.64 | 55.32% |
| V4 Side Split | 667.19 | 243.86 | 243.90 | 179.43 | 73.11% |
| V4 Side + Symbol | 752.43 | 239.73 | 239.77 | 272.93 | 63.73% |
| V5 Symbol Bucket | 977.02 | 241.92 | 241.95 | 493.15 | 49.53% |
| V5 Long Context | 1164.79 | 246.79 | 246.83 | 671.16 | 42.38% |
| V5 Combined | 1254.14 | 242.46 | 242.50 | 769.18 | 38.67% |

Interpretation:

- V5 improved gross PnL while costs stayed roughly flat.
- Cost/gross fell from V3 `55.32%` to V5 combined `38.67%`.
- This is a real efficiency improvement, not merely a lower-trade-count artifact.

---

## Side Attribution

| Run | Long Trades | Long Net | Long Win | Short Trades | Short Net | Short Win |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V3 Hold32 | 24 | +80.43 | 54.17% | 91 | +317.21 | 74.73% |
| V4 Side Split | 22 | -99.98 | 45.45% | 93 | +279.41 | 73.12% |
| V4 Side + Symbol | 22 | -99.98 | 45.45% | 91 | +372.91 | 75.82% |
| V5 Symbol Bucket | 24 | +80.43 | 54.17% | 89 | +412.72 | 77.53% |
| V5 Long Context | 19 | +349.01 | 73.68% | 96 | +322.15 | 75.00% |
| V5 Combined | 19 | +349.01 | 73.68% | 94 | +420.17 | 77.66% |

Interpretation:

- V4's hard long tightening broke the long side.
- V5 long context discounts repaired the long side materially: long net improved from V3 `+80.43` to `+349.01`, with fewer long trades.
- Short remains the edge anchor and improves in the combined run.

---

## Stop-Hit Attribution

| Run | Stop Trades | Stop Net | Avg Stop Offset |
| --- | ---: | ---: | ---: |
| V3 Hold32 | 32 | -879.04 | 7.53 bars |
| V4 Side Split | 35 | -946.24 | 7.17 bars |
| V4 Side + Symbol | 33 | -884.94 | 7.21 bars |
| V5 Symbol Bucket | 30 | -816.43 | 7.60 bars |
| V5 Long Context | 27 | -769.62 | 8.44 bars |
| V5 Combined | 25 | -705.36 | 8.60 bars |

Interpretation:

- V5 reduces stop-hit count from V3 `32` to `25`.
- Stop-hit net loss improves by about `173.69` USDT.
- Average stop-hit offset shifts later, suggesting the worst immediate-failure entries were filtered more effectively.
- Early stop hits are still the dominant loss path and remain the next bottleneck.

---

## Symbol Attribution

V5 combined net PnL by symbol:

| Symbol | Trades | Net PnL | Win Rate |
| --- | ---: | ---: | ---: |
| DOGEUSDT | 25 | +185.01 | 84.00% |
| SOLUSDT | 26 | +183.15 | 80.77% |
| ZECUSDT | 9 | +149.72 | 66.67% |
| XLMUSDT | 21 | +131.67 | 71.43% |
| BNBUSDT | 19 | +115.12 | 78.95% |
| TRXUSDT | 11 | +17.83 | 72.73% |
| TONUSDT | 1 | +4.21 | 100.00% |
| LINKUSDT | 1 | -17.52 | 0.00% |

Interpretation:

- ADA/XMR watch-only was useful as a pure isolated change.
- V5 combined removed the two worst V3 symbols while preserving trade count inside target range.
- DOGE, SOL, ZEC, XLM, and BNB are the strongest latest-30D contributors.
- LINK/TON have only one trade each and should not be promoted based on this sample.

---

## Long Context Trigger Counts

Rejected long decisions in V5 combined included:

| Reason | Count |
| --- | ---: |
| `LONG_CHASE_TRIGGER_DISCOUNT` | 3986 |
| `LONG_CVD_WEAK_DISCOUNT` | 3831 |
| `LONG_UPPER_WICK_TRIGGER_DISCOUNT` | 2967 |
| `LONG_OVEREXTENSION_QUALITY_DISCOUNT` | 2184 |
| `LONG_LOW_LIQUIDITY_SESSION_WATCH` | 282 |

Accepted V5 trades did not carry these reason codes, because the affected candidates were downgraded below executable action before order creation. That is consistent with the intended research design.

---

## Target Gap

User target:

- 30D return: `50%+`
- Win rate: `80%+`
- Trades: `90-120`

Best V5 result:

- 30D return: `+7.69%`
- Win rate: `76.99%`
- Trades: `113`

Result:

- Trade-count target is met.
- Win rate is closer but still below `80%`.
- Return remains far below `50%`.
- This result should not be scaled with leverage to pretend the target is met.

---

## Decision

Promote as the current research baseline:

```text
latest_30d_v5_symbol_bucket_long_context
configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json
```

Keep:

- V3 lifecycle accounting discipline.
- ADA/XMR watch-only bucket.
- Long context discounts based on completed 15m bars.
- Probe disabled.
- XRP blacklist.

Reject:

- V4 blunt long hard-threshold tightening.
- Any claim that the 50% monthly return target is met.
- Any live deployment based on one latest-30D window.

---

## Root Cause Of Improvement

V5 improved because it did what V4 failed to do:

- It did not globally raise long hard minima.
- It selectively downgraded chase-prone long contexts.
- It preserved the short-side edge.
- It removed weak ADA/XMR tail losses.
- It reduced stop-hit count and stop-hit net damage.
- It improved gross PnL faster than costs increased.

The most important change is the long-context discount layer, not the symbol bucket alone.

---

## Remaining Blocker

The strategy is now much more credible than V3/V4 on this latest-30D window, but it is still a single-window research result.

Required next work:

1. Run rolling 30D windows across 6-12 months with the exact V5 accounting and config.
2. Report median, IQR, best window, worst window, and failed-regime notes.
3. Keep exit-side slippage and partial-exit fees frozen.
4. Add diagnostics for rejected long contexts to the report artifact, not only signal events.
5. Only after rolling validation, evaluate whether a conservative VPS dry-run sandbox is warranted.

---

## Bottom Line

V5 is a material improvement.

It moves the best latest-30D result from:

```text
V3: +3.98%, 70.43% win rate, PF 1.4332, 115 trades
```

to:

```text
V5 combined: +7.69%, 76.99% win rate, PF 2.0752, 113 trades
```

The target is still not met, but the path is clearer: symbol governance plus context-aware long filtering works better than blunt side thresholds. The next proof must come from rolling windows, not more single-window parameter tightening.
