# 闸门控制审计

- 配置:`configs/entry_chain.dry_run_fib_pa_v1.json`
- 日志窗口:`2026-09,2026-10`(共 49 个 decisions.jsonl)
- 生成时间:2026-10-19T15:07:18Z

## 1. 阴性控制(每道闸门必须拒绝,且 reason 唯一)

| # | 闸门 | 期望 reason | 实际 | 结果 |
|---|---|---|---|---|
| 1 | blacklist | `SYMBOL_BLACKLISTED` | `SYMBOL_BLACKLISTED` | PASS |
| 2 | watch_only | `SYMBOL_WATCH_ONLY` | `SYMBOL_WATCH_ONLY` | PASS |
| 3 | macro_weekly | `MACRO_WEEKLY_RISK` | `MACRO_WEEKLY_RISK` | PASS |
| 4 | wick_anomaly | `DATA_WICK_ANOMALY` | `DATA_WICK_ANOMALY` | PASS |
| 5 | data_pollution | `DATA_POLLUTION_COOLDOWN` | `DATA_POLLUTION_COOLDOWN` | PASS |
| 6 | position_open | `SYMBOL_POSITION_ALREADY_OPEN` | `SYMBOL_POSITION_ALREADY_OPEN` | PASS |
| 7 | max_active_symbols | `MAX_ACTIVE_SYMBOLS` | `MAX_ACTIVE_SYMBOLS` | PASS |
| 8 | daily_budget | `DAILY_TRADE_BUDGET_USED` | `DAILY_TRADE_BUDGET_USED` | PASS |
| 9 | symbol_daily_budget | `SYMBOL_DAILY_TRADE_BUDGET_USED` | `SYMBOL_DAILY_TRADE_BUDGET_USED` | PASS |
| 10 | symbol_cooldown | `SYMBOL_COOLDOWN_ACTIVE` | `SYMBOL_COOLDOWN_ACTIVE` | PASS |
| 11 | total_exposure | `TOTAL_EXPOSURE_CAP` | `TOTAL_EXPOSURE_CAP` | PASS |
| 12 | same_direction_exposure | `SAME_DIRECTION_EXPOSURE_CAP` | `SAME_DIRECTION_EXPOSURE_CAP` | PASS |
| 13 | margin_buffer | `MARGIN_BUFFER_TOO_LOW` | `MARGIN_BUFFER_TOO_LOW` | PASS |
| 14 | account_equity | `ACCOUNT_EQUITY_INVALID` | `ACCOUNT_EQUITY_INVALID` | PASS |
| 15 | side_not_allowed | `SIDE_NOT_ALLOWED` | `SIDE_NOT_ALLOWED` | PASS |

## 2. 阳性对照(干净上下文必须产出入场动作)

- `hard_block_reason` = `None`
- action = `DIRECT`, side = `LONG`, score = `100.0`
- leverage = `5`, notional_hint = `1500.0`
- 结论:PASS

## 3. 门槛可达性(真实日志)

| 侧 | 样本数 | 最高分 | direct 门槛 | ≥direct | 占比 | ≥probe | 占比 | 历史动作 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| LONG | 33522 | 96.15 | 92.00 | 6 | 0.0179% | 1311 | 3.9109% | NO_TRADE:31663, PROBE:43, WATCH:1816 |
| SHORT | 34318 | 96.15 | 82.00 | 584 | 1.7017% | 4401 | 12.8242% | DIRECT:26, NO_TRADE:28682, PROBE:59, WATCH:5551 |

**结构上不可达的侧**:无

> 判据:该侧「≥direct 门槛的样本数 = 0」且「历史 DIRECT 动作数 = 0」。只满足前一条时,可能是样本窗口不够;两条同时满足才判定为不可达。

## 4. 结论

- 闸门控制失败数:0
- 退出码:0
