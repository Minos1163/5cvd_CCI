# RSI To EMA Ablation Backtest Report

Date: 2026-06-19

Purpose: compare the RSI-to-EMA architecture change on the same latest 30D offline dataset. This is a research result only. It does not approve live trading.

---

## Runs

| Experiment | Run ID | Config | Purpose |
| --- | --- | --- | --- |
| A | `latest_30d_ema_exp_a_baseline` | conservative | Existing reference |
| B | `latest_30d_ema_exp_b_no_rsi` | no_rsi | Remove RSI-style timing weight / redistribute thresholds |
| C | `latest_30d_ema_exp_c_soft` | ema_soft | EMA200 soft penalty plus EMA50/EMA9-21 scoring |
| D | `latest_30d_ema_exp_d_hard` | ema_hard | EMA200 hard gate plus EMA50/EMA9-21 scoring |

Shared assumptions:

- Data: `data/raw/binance_futures/latest_30d`
- Timeframe: `15m`
- Fill: `NEXT_BAR_OPEN`
- Fee: `5 bps` per side
- Slippage: `5 bps`
- Simulated hold: `2` bars
- Cooldown: `8` bars
- Exit model: current synthetic short-hold exit, not full ATR stop / TP lifecycle

---

## Summary Metrics

| Experiment | Trades | Return | Max DD | Win Rate | Profit Factor | Sharpe | Sortino | Expectancy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A Baseline | 93 | -1.08% | 1.34% | 27.96% | 0.5222 | -1.7754 | -2.1101 | -1.1649 |
| B No RSI | 93 | -1.16% | 1.35% | 29.03% | 0.5190 | -1.8590 | -2.2388 | -1.2477 |
| C EMA Soft | 116 | -0.86% | 0.93% | 25.00% | 0.6239 | -1.4251 | -1.9924 | -0.7435 |
| D EMA Hard | 116 | -1.44% | 1.44% | 22.41% | 0.4259 | -2.5034 | -3.3245 | -1.2442 |

Best run by loss, drawdown, profit factor, and expectancy:

- `latest_30d_ema_exp_c_soft`

No experiment meets the user target:

- 30D return target: `50%+`
- Win rate target: `80%+`
- Trade count target: `90-120`

EMA soft meets only trade-count range.

---

## Cost Attribution

| Experiment | Gross PnL | Fees | Slippage | Total Costs | Net PnL |
| --- | ---: | ---: | ---: | ---: | ---: |
| A Baseline | 69.1715 | 118.3329 | 59.1732 | 177.5061 | -108.3346 |
| B No RSI | 78.4550 | 129.6565 | 64.8361 | 194.4926 | -116.0376 |
| C EMA Soft | 96.6293 | 121.8988 | 60.9765 | 182.8754 | -86.2461 |
| D EMA Hard | 27.2650 | 114.3823 | 57.2073 | 171.5896 | -144.3247 |

Interpretation:

- EMA soft improved gross PnL and reduced net loss versus baseline.
- Costs still exceed gross edge in every experiment.
- EMA hard reduced gross PnL sharply and did not reduce costs enough to compensate.

---

## Side And Mode Attribution

### Experiment C: EMA Soft

Direction split:

- Short: `77` trades, net PnL `-38.9295`, win rate `31.17%`
- Long: `39` trades, net PnL `-47.3166`, win rate `12.82%`

Mode split:

- Probe: `77` trades, net PnL `-64.8635`, win rate `16.88%`
- Direct: `39` trades, net PnL `-21.3826`, win rate `41.03%`

Symbol split:

- `BNBUSDT`: `28` trades, net PnL `+3.3075`, win rate `42.86%`
- `XRPUSDT`: `28` trades, net PnL `-48.4439`, win rate `14.29%`
- `SOLUSDT`: `28` trades, net PnL `-17.9837`, win rate `28.57%`
- `TRXUSDT`: `26` trades, net PnL `-9.1496`, win rate `19.23%`
- Tail symbols each had `1-2` trades and all lost.

Interpretation:

- EMA soft broadened the symbol set and improved total expectancy.
- Long signals remained very weak.
- Probe signals remained the largest drag.
- Direct trades are still better than probes but not profitable after costs.

---

## EMA Architecture Finding

No-RSI alone:

- Slightly improved win rate from `27.96%` to `29.03%`.
- Worsened return, profit factor, Sharpe, and expectancy.
- Conclusion: removing RSI without replacing it is not enough.

EMA soft:

- Best current variant.
- Trade count `116`, inside target range.
- Profit factor improved from `0.5222` to `0.6239`.
- Max drawdown improved from `1.34%` to `0.93%`.
- Expectancy improved from `-1.1649` to `-0.7435`.
- Still negative and far from target.

EMA hard:

- Worse than baseline and soft.
- Profit factor fell to `0.4259`.
- Win rate fell to `22.41%`.
- Conclusion: hard EMA200 gate should not be promoted from this 30D test.

---

## Deployment Decision

Decision:

- Reject EMA hard gate for now.
- Keep EMA soft for further research.
- Do not promote EMA soft to live trading.
- Do not use this result to justify real capital deployment.

Dry-run candidate:

- EMA soft may be observed in VPS dry-run only after full lifecycle backtest is implemented.

Required next work:

1. Add full lifecycle backtest:
   - ATR initial stop,
   - TP1/TP2/TP3,
   - breakeven,
   - trailing stop,
   - max holding time,
   - outcome-based cooldown.
2. Disable or sharply tighten probe entries until they show positive expectancy.
3. Separate long and short thresholds because EMA soft shorts performed materially better than longs.
4. Run rolling 30D windows across 6-12 months before any deployment decision.

---

## Bottom Line

EMA soft improved the system but did not solve the strategy.

The replacement from RSI to EMA is directionally useful as a research path because it improved cost-adjusted expectancy and drawdown, but the current entry-chain plus synthetic exit model still cannot reach:

- `50%+` 30D return,
- `80%+` win rate,
- profitable post-cost expectancy.

The next bottleneck is not another entry threshold tweak. The next bottleneck is the missing exit lifecycle.

