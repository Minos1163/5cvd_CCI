# V4 Side Symbol Entry Quality Report

Date: 2026-06-19

Purpose: test whether side-specific entry confirmation and simple symbol buckets reduce early stop-hit losses while keeping V3 lifecycle accounting frozen. This is research evidence only and does not approve live trading.

---

## Frozen Controls

- Exit model: `atr_tp`
- Hold cap: `32`
- Fee: `5 bps`
- Slippage: `5 bps`, including exit-side partial slippage
- TP levels: `1R / 2R / 3R`
- TP fractions: `40% / 35% / 25%`
- ATR stop multiplier: `1.5`
- Breakeven buffer: `0.1%`
- Probe: disabled
- XRPUSDT: blacklisted
- Fill: next bar open

Only entry acceptance changed.

---

## Runs

| Run ID | Change |
| --- | --- |
| `latest_30d_lifecycle_v3_hold32` | V3 benchmark |
| `latest_30d_v4_side_split` | Stricter long total/component thresholds |
| `latest_30d_v4_side_symbol_bucket` | Side split plus ADA/XMR watch-only |

V4 side split:

- Long score offset: `+14`
- Long 30m quality direct minimum: `0.80`
- Long 15m trigger direct minimum: `0.95`
- Long CVD direct minimum: `0.70`
- Short side: unchanged from V3

V4 symbol bucket:

- Same side split
- `ADAUSDT`, `XMRUSDT` watch-only

---

## Headline Comparison

| Run | Return | Trades | Win Rate | PF | Max DD | Sharpe | Expectancy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| V3 Hold32 | +3.98% | 115 | 70.43% | 1.4332 | 1.03% | 1.4569 | +3.4578 |
| V4 Side Split | +1.79% | 115 | 67.83% | 1.1823 | 1.82% | 0.6876 | +1.5602 |
| V4 Side + Symbol | +2.73% | 113 | 69.91% | 1.3050 | 1.73% | 1.0719 | +2.4153 |

Result:

- V4 side split regressed materially.
- Symbol bucket recovered part of the regression, but still did not beat V3.
- V3 remains the current best latest-30D research baseline.

---

## Cost Drag

| Run | Gross PnL | Fees | Slippage | Net PnL | Cost / Gross |
| --- | ---: | ---: | ---: | ---: | ---: |
| V3 Hold32 | 889.96 | 246.14 | 246.17 | 397.64 | 55.32% |
| V4 Side Split | 667.19 | 243.86 | 243.90 | 179.43 | 73.11% |
| V4 Side + Symbol | 752.43 | 239.73 | 239.77 | 272.93 | 63.73% |

Interpretation:

- Side split reduced gross PnL more than it reduced costs.
- Cost/gross got worse, not better.
- Symbol bucket helped by removing weak symbols, but not enough.

---

## Side Attribution

| Run | Long Trades | Long Net | Long Win | Short Trades | Short Net | Short Win |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V3 Hold32 | 24 | +80.43 | 54.17% | 91 | +317.21 | 74.73% |
| V4 Side Split | 22 | -99.98 | 45.45% | 93 | +279.41 | 73.12% |
| V4 Side + Symbol | 22 | -99.98 | 45.45% | 91 | +372.91 | 75.82% |

Interpretation:

- The stricter long profile did not repair longs; it made them worse.
- Short side stayed broadly strong and improved in the symbol-bucket run.
- The issue is not solved by bluntly raising long thresholds.

---

## Stop-Hit Attribution

| Run | Stop Trades | Stop Net |
| --- | ---: | ---: |
| V3 Hold32 | 32 | -879.04 |
| V4 Side Split | 35 | -946.24 |
| V4 Side + Symbol | 33 | -884.94 |

Interpretation:

- V4 did not reduce early stop-hit pressure.
- The side split increased stop-hit count.
- The next long-side fix should target trigger quality and timing, not only score thresholds.

---

## Symbol Bucket Finding

Watch-only symbols:

- `ADAUSDT`
- `XMRUSDT`

Effect:

- Trade count fell only from `115` to `113`.
- Net PnL improved from V4 side split `+179.43` to `+272.93`.
- Short side improved from `+279.41` to `+372.91`.
- Still below V3 benchmark `+397.64`.

Interpretation:

- ADA/XMR demotion is directionally useful.
- Symbol bucketing has value.
- But bucketing should be tested independently from stricter long thresholds in the next round.

---

## Target Gap

User target:

- 30D return: `50%+`
- Win rate: `80%+`
- Trades: `90-120`

Best V4 result:

- Return: `+2.73%`
- Win rate: `69.91%`
- Trades: `113`

Result:

- Trade count remains in range.
- Return and win-rate targets are not met.
- V4 does not move toward the target compared with V3.

---

## Decision

Reject:

- `configs/entry_chain.dry_run_v4_side_split.json` as a promotion candidate.
- The current blunt long-threshold tightening design.

Keep for further research:

- Watch-only symbol bucket idea.
- ADA/XMR demotion hypothesis.
- V3 hold32 lifecycle accounting baseline.

Current best baseline remains:

```text
latest_30d_lifecycle_v3_hold32
```

---

## Root Cause

V4 regressed because:

- Long threshold tightening reduced useful long trades without eliminating enough bad long trades.
- Stop-hit count did not fall.
- Cost drag worsened because gross PnL fell while fees/slippage stayed similar.
- The short profile remained the real edge anchor, but V4 did not materially improve it.

The mistake was assuming that stricter long thresholds would selectively remove bad longs. In this window, they removed too much useful gross edge and did not solve the stop-hit cluster.

---

## Next Best Experiment

Run symbol buckets independently from side split:

```text
V3 hold32 + ADA/XMR watch-only
```

Reason:

- Symbol bucket helped V4 side split.
- It should be isolated without the damaging stricter-long changes.

Second next experiment:

```text
Long trigger-quality test, not total-threshold test
```

Examples:

- Require stronger 30m quality only when long 15m trigger is marginal.
- Require stronger CVD only for long setups with low MFE history.
- Keep long total score closer to V3 until trigger-specific evidence exists.

---

## Bottom Line

V4 is a useful negative result.

It shows:

```text
simple side-threshold tightening is not enough,
symbol demotion has promise,
V3 remains the best baseline,
and early stop-hit reduction needs a more precise trigger-quality fix.
```

Do not promote V4.
