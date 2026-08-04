# AI300 四象限 Dry-Run 缺口复核与落盘报告

**分析窗口:** 2026-07-21 19:45:00 至 2026-07-22 当前日志，北京时间。  
**运行模式:** dry-run / paper ledger。  
**目标:** 复核昨日指出的 4 类缺口是否影响运行，并将 `A/B 自动报告`、`自动切换`、`mission 级三连止损熔断`、`显式策略规则`落盘。  

---

## 1. 日志结论

从 `logs/2026-07/2026-07-21` 与 `logs/2026-07/2026-07-22` 统计，19:45 后共有：

| 项目 | 数值 |
|---|---:|
| 决策总数 | 1,300 |
| `NO_TRADE` | 1,158 |
| `WATCH` | 141 |
| `PROBE` | 1 |
| Q1/Q2/Q3/Q4 | 122 / 180 / 290 / 708 |
| near-miss | 11 |
| 主账本开平 | 1 开 / 1 平 |
| SCOUT 开平 | 3 开 / 3 平 |
| A/B legacy 平仓 | 7 |
| A/B trend_capture 平仓 | 7 |

主账本唯一平仓为 `INITIAL_STOP_HIT`，事件 PnL 合计约 `-0.8744`。  
SCOUT 3 笔已平：`COST_BREAKEVEN_TIMEOUT=2`、`INITIAL_STOP_HIT=1`，事件 PnL 合计约 `-0.7153`。  
A/B legacy 与 trend_capture 各 7 笔已平，trend_capture 略好但两者仍为负：legacy 约 `-1.6956`，trend_capture 约 `-1.5020`。

主要拦截原因仍集中在：

| 原因 | 次数 |
|---|---:|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 393 |
| `SYMBOL_BLACKLISTED` | 182 |
| `SYMBOL_WATCH_ONLY` | 174 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 115 |
| RR/PROBE 质量类缺口 | 多项合计约 50+ |

## 2. 缺陷归因

1. **A/B 有样本，但旧代码没有自动报告。**  
   日志目录下没有 `paper_ab/reports/`，`summary.json` 中也没有 `paper_ab_auto_report_enabled`、`paper_ab_auto_switch_enabled`、`effective_paper_exit_mode` 字段。结果是 A/B 账本虽然在运行，但不会在满 20 笔后生成可审阅报告。

2. **自动切换未落盘，主 paper ledger 仍固定 `legacy`。**  
   `logs/2026-07/2026-07-22/summary.json` 显示 `paper_exit_mode=legacy`。即使 trend_capture 在 A/B 中优于 legacy，旧运行也没有状态文件或逻辑把 dry-run 主账本切到 trend_capture。

3. **SCOUT 只有 symbol 级初始止损冷却，没有 mission 级三连止损熔断。**  
   旧逻辑只能按 symbol 查近期 `INITIAL_STOP_HIT`，无法识别同一 mission 在不同 symbol 上连续失败。

4. **部分策略规则仍是隐式或未限定。**  
   `HIGH_SCORE_LONG_OFFSET_PROBE` 过去依赖 LONG offset、分数、PA/Fib/CVD/RR，但未显式要求 Q1。Q2/Q3 禁止实验加仓过去也主要依赖 ledger 同 symbol 不重复开仓，审计上不够明确。

## 3. 本次落盘内容

### 3.1 A/B 自动报告

新增配置：

- `paper_ab_auto_report_enabled`
- `paper_ab_report_closed_trade_interval`

新增运行逻辑：

- 当 `paper_ab/legacy` 与 `paper_ab/trend_capture` 都达到同一个 20 笔平仓批次时，自动写出：
  - `paper_ab/reports/ab_report_batch_XXXX.json`
  - `paper_ab/reports/ab_report_batch_XXXX.md`
- 报告包含每个账本的 closed trades、PnL、win rate、actual payoff ratio、profit factor。

### 3.2 dry-run 主账本自动切换

新增配置：

- `paper_ab_auto_switch_enabled`
- `paper_ab_auto_switch_min_reports`
- `paper_ab_auto_switch_min_closed_trades`
- `paper_ab_auto_switch_payoff_mult`

新增状态文件：

- `paper_ab/ab_report_state.json`
- `paper_ab/ab_switch_state.json`

触发条件：

- 至少 2 份连续合格 A/B 报告；
- 至少 40 笔 A/B 已平仓样本；
- `trend_capture.actual_payoff_ratio >= legacy.actual_payoff_ratio * 1.3`；
- 触发后只覆盖 dry-run 主 paper ledger 的有效 `exit_mode`，不改生产配置，不触碰真实下单。

### 3.3 mission 级三连初始止损熔断

新增配置：

- `scout_micro_mission_stop_circuit_enabled`
- `scout_micro_mission_stop_circuit_count`
- `scout_micro_mission_stop_circuit_hours`

规则：

- 对同一 `scout_mission`，在最近 12 小时内取最新 3 笔已平仓交易；
- 如果这 3 笔全是 `INITIAL_STOP_HIT`，该 mission 暂停新开仓；
- 这是 mission 级别，跨 symbol 生效；原 symbol 级冷却保留。

### 3.4 显式策略规则

1. `HIGH_SCORE_LONG_OFFSET_PROBE` 现在显式要求 `decision_quadrant == Q1`。  
2. LONG offset SCOUT 订单审计新增 `LONG_OFFSET_Q1_PROBE` reason/tag，保留原 mission 名以兼容旧账本。  
3. 已有实验仓位时，同 symbol 若处于 Q2/Q3 且产生新的 `PROBE`/`DIRECT`，会显式降级为 `WATCH`，并写入 `Q2_Q3_EXPERIMENT_ADD_BLOCK`。

## 4. 验证

已运行：

```bash
pytest tests/test_live_dry_run.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_paper_trading.py -q
```

结果：

```text
110 passed in 12.08s
```

active config smoke：

```bash
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json --once --output-dir <temp> --symbols SOLUSDT --market-data-source synthetic
```

结果：

```text
{"status": "dry_run_completed", "orders_submitted": 0}
```

smoke 生成的 `summary.json` 已包含：

- `paper_ab_auto_report_enabled=true`
- `paper_ab_auto_switch_enabled=true`
- `scout_micro_mission_stop_circuit_enabled=true`
- `effective_paper_exit_mode=legacy`
- `paper_ab_switch_state={}`

## 5. 评审关注点

本次修复解决的是“实验控制未落盘”的工程问题，不代表策略已盈利。19:45 后日志仍显示：Q4 占比高、LONG offset 拦截强、主账本样本少、SCOUT 与 A/B 仍为负。接下来应重点观察：

1. A/B 是否能累计到 20/40 笔并自动产出报告；
2. trend_capture 是否持续达到 1.3x payoff 优势；
3. `HIGH_SCORE_LONG_OFFSET_PROBE` 显式 Q1 后，样本量是否进一步下降；
4. mission 级熔断是否能阻止同一实验任务跨 symbol 连续失血。
