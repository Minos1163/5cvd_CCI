# VPS DRY-RUN Two-Day Paper Trading Review

Date: 2026-06-21

Scope:

- `logs/2026-06/2026-06-20`
- `logs/2026-06/2026-06-21`

Purpose: review the latest VPS dry-run logs, attribute current paper-trading losses, and document the live opening chain for Claude strategy review. This is research and dry-run evidence only. It does not approve live trading.

---

## 1. Data Scope And Caveats

The VPS dry-run is running in non-mutating mode:

- `mode`: `dry_run`
- `exchange_mutation_enabled`: `false`
- `orders_submitted`: `0`
- Order outputs are drafts only; no real exchange order/cancel call is present in the dry-run path.

The latest 2026-06-21 snapshot was updated at `2026-06-21 22:00:10 CST`, using the latest completed 15m kline at `2026-06-21 21:45:00 CST`.

Important caveats:

- The 2026-06-20 and 2026-06-21 folders are daily log folders, not a confirmed continuous account ledger. Current paper state resets by daily log directory, so cross-day equity must not be treated as one exact continuous account curve.
- The paper ledger records leverage, but PnL is calculated directly from paper notional and price movement. It does not multiply PnL again by the recorded `leverage`.
- TP ladder accounting has a likely bug: TP1 can be triggered repeatedly across later bars because filled TP levels are not marked consumed. This can overstate realized wins, win rate, and profit factor.

---

## 2. Current Paper Trading Result

### Daily Folder Summaries

| Folder | Equity | Realized PnL | Unrealized PnL | Return | Max DD | Trade Count | Win Rate | PF | Open Positions |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `2026-06-20` | 9897.80 | -108.03 | +5.83 | -1.0220% | 1.0914% | 4 | 0.00% | 0.0000 | 2 |
| `2026-06-21` | 9983.68 | +7.18 | -23.50 | -0.1632% | 0.3326% | 3 | 66.67% | 1.3535 | 1 |

The latest standalone daily ledger is slightly losing after unrealized PnL: equity is `9983.68`, or `-0.1632%` from the `10000` paper initial equity.

Current open position in the latest folder:

| Symbol | Side | Entry | Last | Notional | Leverage | Hold Bars | Stop | Unrealized PnL |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ZECUSDT | SHORT | 447.96 | 452.77 | 2000.00 | 5x | 6 | 454.2947 | -23.50 |

### Cross-Folder Closed Event View

This view deduplicates closed position events across both folders. It is useful for loss attribution, but it is not a continuous equity curve because of the daily ledger caveat.

| Metric | Value |
| --- | ---: |
| Paper opens | 10 |
| Paper reduces | 4 |
| Paper closes | 7 |
| Closed wins | 2 |
| Closed losses | 5 |
| Closed win rate | 28.57% |
| Gross profit | +35.14 |
| Gross loss | -129.99 |
| Profit factor | 0.2703 |
| Closed-position PnL | -94.86 |
| STOP_HIT PnL | -114.88 |

Event counts:

| Event | Count |
| --- | ---: |
| `PAPER_OPEN` | 10 |
| `PAPER_REDUCE` | 4 |
| `PAPER_CLOSE` | 7 |

Close reasons:

| Reason | Count | Position Realized PnL |
| --- | ---: | ---: |
| `STOP_HIT` | 4 | -114.88 |
| `MAX_HOLD_EXIT` | 1 | -15.12 |
| `TP1_HIT` final close | 2 | +35.14 |

---

## 3. Trade Event Ledger

Closed positions:

| Folder | Symbol | Side | Reason | Position Realized PnL |
| --- | --- | --- | --- | ---: |
| `2026-06-20` | SOLUSDT | LONG | `MAX_HOLD_EXIT` | -15.12 |
| `2026-06-20` | ZECUSDT | SHORT | `STOP_HIT` | -26.78 |
| `2026-06-20` | XLMUSDT | SHORT | `STOP_HIT` | -25.42 |
| `2026-06-20` | ZECUSDT | SHORT | `STOP_HIT` | -36.72 |
| `2026-06-21` | ZECUSDT | SHORT | `STOP_HIT` | -25.96 |
| `2026-06-21` | ZECUSDT | SHORT | `TP1_HIT` | +20.16 |
| `2026-06-21` | TONUSDT | LONG | `TP1_HIT` | +14.97 |

Symbol attribution by closed position:

| Symbol | Closed Count | Closed PnL |
| --- | ---: | ---: |
| ZECUSDT | 4 | -69.29 |
| XLMUSDT | 1 | -25.42 |
| SOLUSDT | 1 | -15.12 |
| TONUSDT | 1 | +14.97 |

ZEC is the dominant loss source. It produced multiple high-score SHORT entries and three stop-hit closes across the sample, plus the current open ZEC SHORT is also unrealized negative.

---

## 4. Loss Attribution

The current dry-run loss is not caused by insufficient logging or missing warmup. The latest logs show the strategy is producing decisions, order drafts, paper opens, paper reduces, paper closes, paper equity, paper summary, and gate rejection files.

Primary loss drivers:

1. **Stop-hit losses dominate the sample.** Four `STOP_HIT` closes generated `-114.88`, while all final TP1 winners together generated only `+35.14`. One SOL time exit added another `-15.12`.

2. **Risk is concentrated in ZEC shorts.** ZEC alone accounts for `-69.29` closed PnL and the latest open position is another ZEC SHORT with `-23.50` unrealized PnL. The entry chain repeatedly interpreted ZEC downside continuation as high-quality, but price rebounded into stops.

3. **High conviction scores did not protect against reversal.** Several losing or stressed ZEC shorts had scores above 90 and leverage recorded as 5x. Direction, CVD, trigger, EMA quality, liquidity, and volatility components were strong, but there is no current penalty for repeated symbol-level stop failures within the dry-run day beyond normal active-position checks.

4. **TP1 winners are too small to offset full-stop losses.** Even before accounting-bug adjustment, the two winning closes reached only `+35.14`, far below the `-114.88` stop-hit loss bucket.

5. **Cost drag is visible in paper events.** Entry fee/slippage is about `2.00` per `2000` notional open. Exit/reduce events add further fee/slippage. The two-day sampled paper events paid roughly `24` units of combined fee/slippage drag.

6. **The paper ledger TP1 repeat bug likely overstates the upside.** On 2026-06-21, ZEC and TON each show TP1 reducing 40%, then reducing another 40%, then closing the remaining 20% at the same TP1 level. A normal 40/35/25 ladder should mark TP1 consumed after the first fill and wait for TP2/TP3 or another exit rule.

7. **Daily paper ledger reset weakens multi-day evaluation.** Because paper state lives under the daily log folder, the 2026-06-21 ledger starts as its own snapshot. This is fine for daily diagnostics, but unsuitable for continuous dry-run performance evaluation unless persistent paper state is moved outside the daily log directory or explicitly carried forward.

---

## 5. Runtime Health And Cadence

The 2026-06-21 folder shows clean 15m alignment:

- 44 scans from `2026-06-21 11:30:05 CST` to `2026-06-21 22:15:05 CST`
- 43 intervals of `900` seconds
- 13/13 symbols processed per full scan
- Warmup ready for all symbols
- `dry_run_warmup_15m_bars`: 240
- 15m, 30m, 1h, and 4h public Binance bars are available in health snapshots

The 2026-06-20 folder is mixed:

- Early logs include many 60-61 second cycles over a smaller or transitioning universe.
- Later logs show aligned 15m scans.
- This looks like deployment/run-mode transition noise rather than a current cadence failure.

The active universe in health is market-cap rank based and excludes stable assets by resolver output:

| Rank | Symbol |
| ---: | --- |
| 4 | BNBUSDT |
| 6 | XRPUSDT |
| 7 | SOLUSDT |
| 8 | TRXUSDT |
| 10 | HYPEUSDT |
| 11 | DOGEUSDT |
| 15 | ZECUSDT |
| 16 | XLMUSDT |
| 18 | ADAUSDT |
| 19/21 | XMRUSDT / CCUSDT order differs by snapshot |
| 20 | LINKUSDT |
| 24 | TONUSDT |

Config still contains `XRPUSDT`, `ADAUSDT`, and `XMRUSDT`, but live gates block `XRPUSDT` as blacklist and `ADAUSDT` / `XMRUSDT` as watch-only hard no-trade.

---

## 6. Live Opening Chain

### Source And Warmup

The VPS dry-run script uses:

- Config: `configs/entry_chain.dry_run_highest_win.json`
- Market data source: `public-binance`
- Universe source: `market_cap_rank`
- Rank range: `3` to `25`
- Required warmup: `240` completed 15m bars per symbol
- Time alignment: run after each 15m close at `00/15/30/45` plus post-close delay

For each symbol, the script:

1. Fetches completed klines and filters current unclosed bars.
2. Builds an `EntryChainContext`.
3. Calls `evaluate_entry_chain()`.
4. Runs stress logging.
5. Builds an order draft only when action is executable and risk allowed.
6. Updates paper ledger from the approved draft.

### Thresholds

Base thresholds:

| Action | Base Score |
| --- | ---: |
| `DIRECT` | 82 |
| `PROBE` | 70 |
| `WATCH` | 60 |

Side offsets:

| Side | Offset | Effective Direct | Effective Probe | Effective Watch |
| --- | ---: | ---: | ---: | ---: |
| LONG | +10 | 92 | 80 | 70 |
| SHORT | +0 | 82 | 70 | 60 |

`disable_probe=true`, so a final `PROBE` is converted to `NO_TRADE`. In practice, the live opening path is mostly `DIRECT` or no executable order.

### EMA Architecture Weights

Because `use_ema_architecture=true`, the scoring weights are:

| Component | Weight |
| --- | ---: |
| `background_4h` | 5 |
| `direction_1h` | 18 |
| `quality_30m` | 12 |
| `trigger_15m` | 7 |
| `ema_50_quality` | 15 |
| `ema_momentum` | 10 |
| `cvd_flow` | 18 |
| `volatility_stop` | 10 |
| `liquidity_execution` | 3 |
| `market_regime` | 2 |

Score contribution is `component_score * component_weight`, with component scores clamped to `0..1`.

### Key Feature Rules

Direction and trigger:

- 1h direction uses the last 4 completed 1h bars.
- A move above `+0.3%` favors LONG.
- A move below `-0.3%` favors SHORT.
- 15m trigger is `1.0` when latest completed 15m move exceeds `0.15%` in the candidate side direction.
- Smaller same-side 15m movement scores `0.4`; opposite movement scores `0`.

CVD and volatility:

- CVD proxy uses the last 6 candle signed volumes.
- Side-aligned CVD scores `1.0`; opposite CVD scores around `0.2`.
- `volatility_stop` is `1.0` when ATR pct is between `0.5%` and `4%`; otherwise it is penalized.

EMA gates:

- EMA200 mode is `soft`, not hard.
- EMA200 buffer is `0.3%`.
- EMA200 stability requirement is 3 bars.
- EMA50 minimum for `DIRECT`: `0.60`.
- EMA50 minimum for `PROBE`: `0.40`, but probe is disabled.

Long context discounts:

| Long Risk Flag | Effect |
| --- | --- |
| Overextension above upper Bollinger band | `quality_30m *= 0.70`, `ema_50_quality *= 0.70` |
| Upper wick risk | `trigger_15m *= 0.60` |
| Chase risk | `trigger_15m *= 0.75` |
| Weak CVD | `cvd_flow *= 0.80` |
| Low-liquidity UTC session | Cap long action at `WATCH` |

### Hard Gates And Demotions

Hard blocks:

- `XRPUSDT` is blacklisted.
- `ADAUSDT` and `XMRUSDT` are watch-only symbols but implemented as hard no-trade.
- Macro weekly BTC drop `<= -15%`.
- Wick anomaly.
- Data pollution cooldown.
- Active symbol count `>= 5`.
- Symbol daily trade count `>= 1`.
- Portfolio daily trade budget exceeded.
- Cooldown active.
- Total exposure `>= 1.2`.
- Same-direction exposure `>= 0.9`.
- Available margin below `30%` of equity.
- Invalid equity or invalid side.

Liquidity:

```text
liquidity_ratio = quote_volume_24h / (max(1, atr_pct * 100) * expected_order_size)
```

With dry-run `expected_order_size=1000`:

- Ratio `< 8`: block.
- Ratio `< 20`: demote `DIRECT` to `PROBE`; because probes are disabled, this becomes no executable trade.

High beta:

- `HYPEUSDT`, `LABUSDT`, and `CCUSDT` are high-beta.
- A `DIRECT` on these symbols is demoted to `PROBE`, then disabled to `NO_TRADE`.

---

## 7. Position Sizing, Leverage, And Risk

Dry-run account assumptions:

| Parameter | Value |
| --- | ---: |
| Paper initial equity | 10000 |
| Context account equity | 10000 |
| Context available margin | 8000 |
| Expected order size | 1000 |
| Max active symbols | 5 |
| Daily max trades base | 4 |
| Max symbol trades per day | 1 |
| Max total exposure pct | 1.2 |
| Max same-direction exposure pct | 0.9 |
| Margin buffer pct | 0.30 |

Risk sizing:

| Parameter | Value |
| --- | ---: |
| `direct_risk_pct` | 0.006 |
| `probe_risk_pct` | 0.0025 |
| Direct base exposure | 20% of equity |
| Direct score add-on | up to +10% of equity |
| Probe exposure | 5% of equity, but probe disabled |

Symbol exposure caps:

| Symbol Class | Cap |
| --- | ---: |
| BTC / ETH / BNB | 30% |
| SOL / ADA / LINK and default mainstream | 20% |
| HYPE / LAB / CC | 10% |

`notional_hint` for `DIRECT` is the minimum of:

1. Score-based exposure: `equity * (0.20 + min(0.10, (score - 82) / 100))`
2. Risk-based cap: `equity * direct_risk_pct / stop_pct`
3. Remaining symbol exposure cap

Leverage selection:

| Condition | Leverage |
| --- | ---: |
| Non-executable action | 0x |
| Rolling Sharpe < 0 | 2x |
| ATR pct > 3% | 3x |
| ATR pct > 1.5%, `DIRECT` | 4x |
| ATR pct > 1.5%, `PROBE` | 3x |
| Score >= 90 and `DIRECT` | 5x |
| Other `DIRECT` | 4x |
| Other `PROBE` | 3x |

Paper exit model:

| Rule | Value |
| --- | --- |
| Entry fee | 5 bps |
| Entry slippage | 5 bps |
| Exit fee | 5 bps |
| Exit slippage | 5 bps |
| Stop distance | `ATR * 1.5`, clamped `0.5%..3%` |
| TP levels | 1R / 2R / 3R |
| TP fractions | 40% / 35% / 25% |
| Stop after TP1 | LONG `entry * 1.001`, SHORT `entry * 0.999` |
| Max hold | 32 processed bars |
| Duplicate bar guard | `timestamp <= last_processed_kline_ts` ignored |

Within a bar, stop is checked before TP. This is conservative for bars that touch both stop and target.

---

## 8. Decision Quality Snapshot

Across both folders:

| Decision Action | Count |
| --- | ---: |
| `NO_TRADE` | 1185 |
| `WATCH` | 492 |
| `DIRECT` | 32 |

Approved order drafts:

| Metric | Count |
| --- | ---: |
| Approved drafts | 32 |
| Paper opens | 10 |

Approved drafts can repeat while a signal persists, but paper opens only when no current paper position exists for that symbol.

Top gate/rejection tags:

| Tag | Count |
| --- | ---: |
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 471 |
| `LONG_CVD_WEAK_DISCOUNT` | 197 |
| `SYMBOL_WATCH_ONLY` | 178 |
| `LONG_CHASE_TRIGGER_DISCOUNT` | 135 |
| `PROBE_COMPONENT_MINIMUM_FAILED` | 131 |
| `LONG_UPPER_WICK_TRIGGER_DISCOUNT` | 115 |
| `SYMBOL_BLACKLISTED` | 89 |

This indicates long-side context discounts are active, and blacklist/watch-only controls are visible in the logs.

---

## 9. Bugs And Optimization Targets

### Must Fix Before Strategy Judgement

1. **Fix TP-level consumption in paper ledger.** Once TP1 is filled, TP1 must be marked consumed or removed. Current repeated TP1 fills can overstate profits and win rate.

2. **Separate persistent paper state from daily log directories.** Keep daily logs under `logs/YYYY-MM/YYYY-MM-DD`, but store continuous paper state in a stable state directory such as `state/paper/`. Daily reports can snapshot from that state.

3. **Clarify leverage accounting.** Either paper PnL should explicitly use leveraged notional, or the report should label current paper PnL as notional-based and not comparable to V6 leveraged backtests.

### Strategy Risks To Review

1. **ZEC stop-hit cooldown.** Add a symbol-level penalty after repeated stop hits, for example reduce leverage by 1x or block new entries for 12-24 hours after 2 stops in the last 5 trades.

2. **High-score short reversal filter.** Current ZEC losses suggest that direction/CVD/EMA agreement can still fire into short squeeze or rebound conditions. Review pre-entry wick structure, local exhaustion, and recent adverse high-volume reversal bars.

3. **TP/SL asymmetry.** TP1 partials are too small to compensate for full stop losses under the current sampled path. Review whether breakeven-after-TP1 and max-hold exits are enough, after fixing TP accounting.

4. **Daily trade budget realism.** Logs show `daily_max_trades` can scale down to 2 or 3 in metadata. Confirm that this behavior is intended and that it matches the live deployment risk plan.

5. **Watch-only semantics.** `watch_only_symbols` currently hard-blocks symbols instead of returning `WATCH`. This may be intentional, but the naming is misleading for operators and reviewers.

---

## 10. Claude Review Questions

Recommended questions for Claude:

1. Given the ZEC/XLM short stop-hit cluster, should short entries require an additional anti-squeeze filter based on recent upper wick, reversal volume, or failed continuation after a large 15m red candle?

2. Should symbol-level cooldown after stop hits be implemented before any further leverage or entry-threshold tuning?

3. After fixing TP-level consumption, does the paper ledger still show positive expectancy on 2026-06-21, or does the apparent PF improvement disappear?

4. Should paper state be continuous across UTC day boundaries before evaluating win rate, max drawdown, PF, and return?

5. Should `watch_only_symbols` be renamed to `blocked_symbols` or changed to truly produce `WATCH` diagnostics without opening?

6. Should dry-run paper PnL be changed to leveraged PnL, or should the strategy continue using notional-based PnL for safer operator diagnostics?

---

## 11. Conclusion

The current VPS dry-run is operational: 240-bar warmup is present, the 2026-06-21 cadence is aligned to 15m closes, logs are rich enough for debugging, and paper trading records opens, reductions, closes, equity, realized/unrealized PnL, win rate, drawdown, PF, and trade counts.

The strategy is not currently demonstrating clean profitability in this two-day paper sample. The loss is mainly from repeated high-score ZEC/XLM short stop hits, while TP1 winners are too small and possibly overstated by a TP1 repeat-fill bug. Before optimizing the entry strategy, the paper accounting bugs should be fixed so Claude can review real expectancy rather than distorted dry-run ledger output.
