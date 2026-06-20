# Entry Chain Optimization Backtest Attribution

Date: 2026-06-19

Purpose: record the latest AI300 entry-chain parameter calibration, rerun the latest 30D offline backtest, and attribute why the current implementation still does not meet the target.

---

## 1. User Target

Target profile:

- Floating leverage: `3x`, `4x`, `5x`
- Single-symbol exposure: `20%-30%` of account equity
- Max active symbols: `5`
- 30D return target: `50%+`
- Win rate target: `80%+`
- 30D opening count: `90-120`

This target remains aggressive and is not validated by the current backtest.

---

## 2. Implementation Correction Before Rerun

The prior refined run, `latest_30d_round3_entry_chain_refined`, produced only `13` trades. Root cause:

- `PortfolioState` recorded active symbols and exposure after each entry.
- The current backtest engine closes positions synthetically after a short fixed window.
- The strategy callback did not receive a real close event, so `PortfolioState` never released active symbols or exposure.
- Later signals were blocked by stale `MAX_ACTIVE_SYMBOLS`, `SYMBOL_EXPOSURE_CAP`, or exposure caps.

Correction made for research backtests:

- Added explicit synthetic release support in `src/signals/portfolio_state.py`.
- Added `--entry-chain-config`, `--simulated-hold-bars`, and `--cooldown-bars` to `scripts/run_offline_backtest.py`.
- The offline entry-chain callback now expires synthetic positions before each signal evaluation.

Live execution was not changed.

Binance client was not intentionally touched.

---

## 3. Latest 30D Backtest Context

Dataset:

- Data directory: `data/raw/binance_futures/latest_30d`
- Source: Binance Futures public klines downloaded offline
- Timeframe: `15m`
- Fill model: `NEXT_BAR_OPEN`
- Exit model: current engine synthetic one-bar exit after entry fill
- Fee: `5 bps` per side
- Slippage: `5 bps`
- Funding: `0 bps`
- Data range: inherited from downloaded manifest and run artifacts

Important limitation:

- This run tests the entry-chain gate, sizing hint, costs, and a simple fill path.
- It does not yet test the full intended lifecycle: ATR stop, TP1/TP2/TP3, breakeven, trailing stop, direction reversal exit, or portfolio-level forced exit.

---

## 4. Run Comparison

| Run | Profile | Trades | Return | Max DD | Win Rate | Profit Factor | Sharpe | Expectancy |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `latest_30d_round1` | baseline 15m momentum | 24695 | -322.15% | 322.20% | 29.76% | 0.5241 | -20.43 | -1.3045 |
| `latest_30d_round2_entry_chain` | entry-chain no state release issue | 124 | -1.36% | 1.46% | 26.61% | 0.5444 | -2.00 | -1.0967 |
| `latest_30d_round3_entry_chain_refined` | stale exposure state | 13 | -0.018% | 0.142% | 15.38% | 0.8864 | -0.12 | -0.1387 |
| `latest_30d_round4_entry_chain_conservative_cd8` | conservative, cooldown 8 bars | 93 | -1.08% | 1.34% | 27.96% | 0.5222 | -1.78 | -1.1649 |
| `latest_30d_round4_entry_chain_balanced` | balanced, cooldown 8 bars | 124 | -1.36% | 1.46% | 26.61% | 0.5444 | -2.00 | -1.0967 |
| `latest_30d_round4_entry_chain_aggressive` | aggressive, cooldown 4 bars | 155 | -2.35% | 2.35% | 26.45% | 0.5220 | -2.69 | -1.5182 |

Best aligned with trade-count target:

- `latest_30d_round4_entry_chain_conservative_cd8`
- Trades: `93`, inside the target `90-120`
- Return and win rate still fail target materially.

---

## 5. Best Run Cost Attribution

Best target-count run:

- Run ID: `latest_30d_round4_entry_chain_conservative_cd8`
- Initial capital: `10000`
- Final equity: `9891.6654`
- Net PnL: `-108.3346`
- Total return: `-1.0833%`
- Max drawdown: `1.3440%`
- Trades: `93`
- Win rate: `27.96%`
- Profit factor: `0.5222`
- Sharpe: `-1.7754`
- Sortino: `-2.1101`
- Expectancy: `-1.1649` per trade

PnL decomposition:

- Gross PnL before costs: `+69.1715`
- Fees: `118.3329`
- Slippage: `59.1732`
- Fees plus slippage: `177.5061`
- Net PnL: `-108.3346`

Interpretation:

- The conservative gate reduced churn from `24695` trades to `93` trades.
- Gross PnL became slightly positive.
- Costs were still `2.57x` gross PnL, so the strategy lost after realistic fee and slippage assumptions.
- This is a cost/exit-quality problem more than a catastrophic entry-frequency problem.

---

## 6. Direction, Mode, And Symbol Attribution

For `latest_30d_round4_entry_chain_conservative_cd8`:

Direction split:

- Long: `47` trades, net PnL `-64.3098`, win rate `27.66%`
- Short: `46` trades, net PnL `-44.0248`, win rate `28.26%`

Mode split:

- Direct: `43` trades, net PnL `-63.8024`, win rate `46.51%`
- Probe: `50` trades, net PnL `-44.5322`, win rate `12.00%`

Symbol split:

- `BNBUSDT`: `31` trades, net PnL `-13.6847`, win rate `29.03%`
- `XRPUSDT`: `31` trades, net PnL `-40.0443`, win rate `22.58%`
- `SOLUSDT`: `31` trades, net PnL `-54.6057`, win rate `32.26%`

Interpretation:

- Both long and short lose, so this is not a one-direction bias only.
- Probe quality is poor under the current one-bar exit assumption.
- Direct trades are better than probe trades but still far from the `80%+` win-rate target.
- Conservative gating selected only three symbols, each roughly once per day, which explains why trade count landed at `93`.

---

## 7. Parameter Findings

Conservative profile:

- Trade count: acceptable.
- Drawdown: controlled.
- Win rate and profit factor: unacceptable.
- Best current candidate for dry-run safety, not for return target.

Balanced profile:

- Trade count: `124`, slightly above target.
- Performance: similar to round2, still negative.
- Adds more symbols but does not improve expectancy.

Aggressive profile:

- Trade count: `155`, above target.
- Return, drawdown, profit factor, and expectancy worsen.
- Lowering thresholds increases churn without improving signal edge.

Conclusion:

- Threshold-only optimization is insufficient.
- The next meaningful improvement is not to lower entry thresholds.
- The next engineering priority is a real position lifecycle backtest with ATR stop, TP ladder, breakeven, trailing stop, and cooldown based on actual trade outcomes.

---

## 8. Why The Target Is Not Met

Target gap:

| Metric | Target | Best Current |
| --- | ---: | ---: |
| 30D return | `50%+` | `-1.08%` |
| Win rate | `80%+` | `27.96%` |
| Trades | `90-120` | `93` |
| Max active symbols | `5` | enforced by gate |
| Per-symbol exposure | `20%-30%` target | capped by config and risk notional |

Root causes:

1. The one-bar synthetic exit does not match the intended strategy.
2. Probe entries are too weak and should be disabled or heavily tightened until lifecycle backtests prove they add value.
3. Direct entries are better than probes but still not strong enough after costs.
4. Fees and slippage dominate small short-horizon moves.
5. The current CVD proxy is derived from OHLCV features, not true exchange trade flow.
6. The current backtest does not model leverage, margin, liquidation buffer, protection orders, or stop/TP sequencing.

---

## 9. Recommendations

Immediate research settings:

- Use conservative profile for dry-run observation.
- Treat `93` trades as frequency calibration only, not profit validation.
- Disable real money trading until lifecycle backtest is implemented.

Next engineering work:

1. Implement a lifecycle backtest mode:
   - next-bar entry,
   - ATR initial stop,
   - TP1 at `1R`,
   - TP2 at `2R`,
   - TP3/trailing at `3R-4R`,
   - breakeven after `1R`,
   - max holding time,
   - outcome-based cooldown.
2. Report MFE/MAE for every trade.
3. Separate direct-only and probe-only performance.
4. Re-test latest 30D, then rolling 30D windows over at least 6-12 months.
5. Only after the lifecycle model shows positive expectancy should leverage be evaluated.

---

## 10. Bottom Line

The latest parameter optimization succeeded at the first safety goal:

- trade count moved from `24695` to `93`,
- drawdown stayed near `1.34%`,
- stale exposure state was fixed.

It failed the performance target:

- return is negative,
- win rate is far below `80%`,
- profit factor is below `1`,
- costs still overwhelm the current edge.

Do not interpret this as a deployable strategy yet. Interpret it as a safer backtest harness and a clearer diagnosis: the entry gate alone cannot reach the target without a real exit and risk lifecycle.

