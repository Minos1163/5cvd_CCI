# VPS DRY-RUN Latest 19H PnL Attribution Report

Date: 2026-06-22

Window:

- Start: `2026-06-21 16:30:08 UTC` / `2026-06-22 00:30:08 CST`
- End: `2026-06-22 11:30:08 UTC` / `2026-06-22 19:30:08 CST`

Sources:

- `logs/2026-06/2026-06-22/paper_trades.jsonl`
- `logs/2026-06/2026-06-22/paper_summary.json`
- `logs/2026-06/2026-06-22/paper_positions.json`
- `logs/2026-06/2026-06-22/decisions.jsonl`
- `logs/2026-06/2026-06-22/order_drafts.jsonl`
- `logs/2026-06/2026-06-22/gate_rejections.jsonl`
- `logs/2026-06/2026-06-22/runtime.out.log`
- `logs/2026-06/2026-06-22/runtime.out.06.log`

Purpose: summarize the latest VPS dry-run paper account performance, attribute losses, and prepare Claude review questions before further strategy optimization. This is dry-run evidence only. It does not approve live trading.

---

## 1. Executive Summary

The latest 19-hour dry-run sample is losing.

| Metric | Value |
| --- | ---: |
| Equity | `9943.64` |
| Return | `-0.5636%` |
| Realized notional PnL | `-56.36` |
| Unrealized notional PnL | `0.00` |
| Margin-equity reporting view | `9745.72` |
| Realized margin PnL reporting view | `-254.28` |
| Open positions | `0` |
| Closed trades | `7` |
| Win rate | `42.86%` |
| Profit factor | `0.3993` |
| Max drawdown | `0.8483%` |
| Orders submitted | `0` |
| Exchange mutation enabled | `false` |

The main loss source is no longer ZEC. ZEC is now blocked by blacklist gates. The latest loss cluster is concentrated in **XLMUSDT** and **LINKUSDT** short trades.

All executable `DIRECT` signals in this window were `SHORT`. No long trade was opened.

---

## 2. Runtime Health

Runtime health looks good.

| Check | Result |
| --- | --- |
| Data health | `OK` |
| Exchange mutation | `false` |
| Orders submitted | `0` |
| Runtime cycles | `76` |
| Cycle interval | `900s` for all 75 intervals |
| First cycle | `2026-06-22 00:45:05 CST` |
| Last cycle | `2026-06-22 19:30:05 CST` |
| Restart marker | Present in `runtime.out.06.log` at `2026-06-22 19:27:02 CST` |

The 15m alignment is working. The split runtime log file is also present:

- Old file from earlier deployment: `runtime.out.log`
- New 6h bucket file after restart: `runtime.out.06.log`

The latest `process_start` block confirms the newer startup observability is deployed:

```text
=== AI300_DRY_RUN process_start @ 2026-06-22 11:27:02 UTC === [mode=public-binance, kline_align=ON, tf=900s]
```

---

## 3. Paper Event Summary

| Event | Count |
| --- | ---: |
| `PAPER_OPEN` | 7 |
| `PAPER_REDUCE` | 4 |
| `PAPER_CLOSE` | 7 |

Exit and reduction reasons:

| Reason | Count |
| --- | ---: |
| `STOP_HIT` | 6 |
| `TP1_HIT` | 3 |
| `TP2_HIT` | 1 |
| `TP3_HIT` | 1 |

Important interpretation: `STOP_HIT` is not always a losing event. After TP1, the stop is moved near breakeven. In this window, two `STOP_HIT` closes were positive because they happened after a TP1 partial exit.

Closed PnL:

| Bucket | PnL |
| --- | ---: |
| Gross profit from closed positions | `+37.47` |
| Gross loss from closed positions | `-93.83` |
| Net closed PnL | `-56.36` |

---

## 4. Trade Ledger

### Opens

| Time CST | Symbol | Side | Score | Leverage | Notional |
| --- | --- | --- | ---: | ---: | ---: |
| 2026-06-22 02:15:06 | XLMUSDT | SHORT | 89.6500 | 4x | 2000 |
| 2026-06-22 04:15:11 | TONUSDT | SHORT | 88.5902 | 4x | 2000 |
| 2026-06-22 06:00:07 | SOLUSDT | SHORT | 86.6500 | 4x | 2000 |
| 2026-06-22 06:00:08 | XLMUSDT | SHORT | 87.9006 | 4x | 2000 |
| 2026-06-22 07:15:11 | LINKUSDT | SHORT | 83.5826 | 4x | 2000 |
| 2026-06-22 12:00:07 | XLMUSDT | SHORT | 94.6500 | 5x | 2000 |
| 2026-06-22 12:00:08 | TONUSDT | SHORT | 87.1057 | 4x | 2000 |

### Reductions

| Time CST | Symbol | Side | Reason | Fraction | Net PnL | Remaining |
| --- | --- | --- | --- | ---: | ---: | ---: |
| 2026-06-22 05:15:08 | TONUSDT | SHORT | `TP1_HIT` | 0.40 | +6.29 | 0.60 |
| 2026-06-22 06:15:08 | TONUSDT | SHORT | `TP2_HIT` | 0.35 | +11.70 | 0.25 |
| 2026-06-22 07:45:05 | SOLUSDT | SHORT | `TP1_HIT` | 0.40 | +5.70 | 0.60 |
| 2026-06-22 07:45:07 | XLMUSDT | SHORT | `TP1_HIT` | 0.40 | +6.99 | 0.60 |

The TP repeat bug does not appear in this window. TON correctly progressed through `TP1`, `TP2`, and later `TP3`.

### Closes

| Time CST | Symbol | Side | Reason | Position PnL |
| --- | --- | --- | --- | ---: |
| 2026-06-22 02:45:06 | XLMUSDT | SHORT | `STOP_HIT` | -26.68 |
| 2026-06-22 08:30:05 | SOLUSDT | SHORT | `STOP_HIT` after TP1 | +3.70 |
| 2026-06-22 08:45:06 | XLMUSDT | SHORT | `STOP_HIT` after TP1 | +4.99 |
| 2026-06-22 08:45:07 | LINKUSDT | SHORT | `STOP_HIT` | -17.09 |
| 2026-06-22 11:15:11 | TONUSDT | SHORT | `TP3_HIT` | +28.78 |
| 2026-06-22 15:15:06 | XLMUSDT | SHORT | `STOP_HIT` | -28.83 |
| 2026-06-22 15:30:08 | TONUSDT | SHORT | `STOP_HIT` | -21.23 |

---

## 5. Symbol Attribution

| Symbol | Opens | Reduces | Closes | Stop Closes | Closed PnL |
| --- | ---: | ---: | ---: | ---: | ---: |
| XLMUSDT | 3 | 1 | 3 | 3 | -50.52 |
| LINKUSDT | 1 | 0 | 1 | 1 | -17.09 |
| TONUSDT | 2 | 2 | 2 | 1 | +7.55 |
| SOLUSDT | 1 | 1 | 1 | 1 | +3.70 |

Interpretation:

- **XLMUSDT is the dominant loss source** in this window. It opened three times and ended at `-50.52`.
- **LINKUSDT had one low-edge direct short** with score `83.5826` and lost `-17.09`.
- **TONUSDT is mixed but net positive**: one strong TP3 winner, then one later stop loss.
- **SOLUSDT was small positive** after TP1 and breakeven-style stop.

---

## 6. Loss Attribution

### 6.1 Primary Loss: XLM Repeated Shorts

XLM produced:

- 3 opens
- 3 closes
- 3 `STOP_HIT` labels
- Net closed PnL `-50.52`

One XLM trade did reach TP1 and closed positive after the stop moved near breakeven, but the two full-loss XLM shorts overwhelmed that gain.

This resembles the earlier ZEC problem in structure, though the sample is still small:

```text
Repeated high-score short entries on the same symbol
        ↓
One partial winner does not offset multiple full stops
        ↓
Symbol-level local alpha appears unstable
```

### 6.2 Secondary Loss: LINK Threshold-Edge Short

LINK opened once:

- Score: `83.5826`
- Side: SHORT
- Result: `-17.09`

This is close to the short direct threshold (`82`). It may indicate that low-margin direct signals between `82-85` are too weak for fresh dry-run deployment, especially when no symbol-specific positive evidence exists.

### 6.3 Stop-Hit Label Needs Better Subclassification

The paper ledger now avoids repeated TP fills, but `STOP_HIT` still mixes two very different cases:

1. **Full adverse stop before TP**: true losing stop.
2. **Post-TP breakeven stop**: often small positive or near-flat exit.

In this window:

- Losing `STOP_HIT`: XLM `-26.68`, LINK `-17.09`, XLM `-28.83`, TON `-21.23`
- Positive `STOP_HIT` after TP1: SOL `+3.70`, XLM `+4.99`

For future analysis, the ledger should record separate reasons such as:

- `INITIAL_STOP_HIT`
- `BREAKEVEN_STOP_HIT`
- `TRAILING_STOP_HIT`

That will make loss attribution much cleaner.

---

## 7. Decision And Gate Snapshot

Decision distribution:

| Action | Count |
| --- | ---: |
| `NO_TRADE` | 739 |
| `WATCH` | 308 |
| `DIRECT` | 17 |

All `DIRECT` decisions were shorts:

| Side | DIRECT Count |
| --- | ---: |
| SHORT | 17 |
| LONG | 0 |

DIRECT signals by symbol:

| Symbol | DIRECT Count |
| --- | ---: |
| XLMUSDT | 6 |
| TONUSDT | 6 |
| SOLUSDT | 3 |
| LINKUSDT | 2 |

Approved drafts:

| Symbol | Approved Drafts |
| --- | ---: |
| XLMUSDT | 6 |
| TONUSDT | 6 |
| SOLUSDT | 3 |
| LINKUSDT | 2 |

Score stats:

| Action | Count | Min | Avg | Max |
| --- | ---: | ---: | ---: | ---: |
| `DIRECT` | 17 | 83.5826 | 88.6800 | 94.6500 |
| `WATCH` | 308 | 60.1916 | 74.9101 | 90.4500 |
| `NO_TRADE` | 739 | 18.2051 | 60.6249 | 96.8500 |

Top gate combinations:

| Gate Combination | Count |
| --- | ---: |
| `EMA_ARCHITECTURE_WEIGHTS` | 200 |
| `EMA_ARCHITECTURE_WEIGHTS|SIDE_THRESHOLD_OFFSET_LONG_10.00` | 113 |
| `EMA_ARCHITECTURE_WEIGHTS|SYMBOL_BLACKLISTED` | 107 |
| `EMA_ARCHITECTURE_WEIGHTS|LONG_CVD_WEAK_DISCOUNT|SIDE_THRESHOLD_OFFSET_LONG_10.00` | 90 |
| `EMA_ARCHITECTURE_WEIGHTS|SYMBOL_WATCH_ONLY` | 85 |
| `EMA_ARCHITECTURE_WEIGHTS|PROBE_COMPONENT_MINIMUM_FAILED` | 81 |

ZEC/XRP blacklist behavior is active. `SYMBOL_BLACKLISTED` appears frequently, which is expected after ZEC was added to the temporary blacklist.

---

## 8. Current Position State

At the latest snapshot:

```json
{}
```

There are no open paper positions.

This makes the latest account state straightforward:

- Realized PnL equals total current PnL.
- Unrealized PnL is zero.
- No hidden open risk remains at snapshot time.

---

## 9. Key Findings

### Finding A: Latest Window Is Losing

The dry-run account lost `-56.36` notional PnL over the latest 19 hours. Margin reporting view shows `-254.28`, because leverage magnifies the PnL reporting lens.

This is not catastrophic in account terms (`-0.5636%` notional return), but it is not deployable evidence.

### Finding B: XLM Replaced ZEC As The Main Loss Cluster

After ZEC was blocked, the loss cluster moved to XLM.

This suggests that the problem is not only one bad symbol. The short entry chain may still over-trust high-score short continuation signals during local rebound or chop.

### Finding C: Long Side Is Still Effectively Dormant

There were zero long direct signals. Long filters are active and strict:

- Long threshold offset
- Weak CVD discount
- Upper wick discount
- Chase discount

This may be acceptable if the strategy is intentionally short-biased, but Claude should review whether the live dry-run objective still expects both sides to contribute.

### Finding D: TP Ladder Accounting Looks Better

TON shows:

```text
TP1 -> TP2 -> TP3
```

No repeated TP1 pattern appears in this latest window. The P0 TP-consumption fix appears to be reflected in the downloaded logs.

### Finding E: Stop Attribution Still Needs Better Labels

`STOP_HIT` currently includes both full losing stops and post-TP breakeven exits. This makes raw stop counts misleading.

In this window, `STOP_HIT` count is 6, but only 4 are truly losing closes.

---

## 10. Suggested Claude Review Questions

1. Should XLMUSDT be temporarily moved to observation-only or blacklist after this latest loss cluster, similar to the earlier ZEC response?

2. Should low-margin short `DIRECT` signals with scores below `85` be blocked or demoted to `WATCH`, given the LINK loss at score `83.5826`?

3. Should the strategy implement a rolling symbol-level cooldown after full adverse stops, separate from daily trade count?

4. Should short entries add an anti-reversal filter based on recent oversold movement, high-volume bullish reversal, or failed breakdown structure?

5. Should paper close reasons be split into `INITIAL_STOP_HIT` and `BREAKEVEN_STOP_HIT` before using stop counts for strategy judgment?

6. Is the current long-side suppression desirable, or is the strategy becoming an effectively short-only system in live dry-run?

7. Should leverage be reduced from 5x to 4x or 3x for symbols with weak recent local alpha, especially XLM?

---

## 11. Recommended Next Steps

Priority order:

1. Add stop-reason subtyping in paper ledger: initial stop vs breakeven stop.
2. Add rolling 48h symbol cooldown after 2 full adverse stops.
3. Consider temporary XLM observation-only status until at least 7 days of clean data or a specific XLM filter is added.
4. Review short anti-reversal filters before changing global thresholds.
5. Avoid live capital deployment until at least 14 days of continuous fixed paper-state data shows positive expectancy.

Do not tune for the latest 19h window alone. This sample is useful for identifying failure modes, not for proving strategy quality.

---

## 12. Conclusion

The system is operational and logging is healthy: 15m cadence is clean, dry-run safety is intact, startup logging is visible, and paper trading produces complete account metrics.

The strategy result in the latest 19 hours is negative. The loss is mainly caused by repeated XLM short failures and one LINK short failure. TON and SOL partially offset the damage, and the TP ladder now appears to behave correctly.

The next optimization should focus on short-side failure control, not profit expansion: symbol-level cooldown, short anti-reversal filters, and clearer stop attribution should come before any leverage increase or live deployment discussion.
