# 亏损归因报告：2026-10-31 重启 → 2026-11-08（经核实主账本为净盈利 +33.762404，详见 §0）

> **数据口径**：主账本逐笔取 `D:/AIDCA/AI300-fwdlib/logs/2026-10/2026-10-31/` 与 `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-01/ .. 2026-11-08/` 下**按 UTC 日轮转**的 `paper_trades.jsonl` 事件流（全窗口合计 28 行 = 11 开仓 + 17 出场事件），按 `position_id` 聚合生命周期；快照取各日 `paper_summary.json`。
> **账户**：纸面交易（dry-run，真实 Binance 公开行情 / 模拟成交），四套账本各自 `initial_equity=10000`，永不提交真实订单。
> **时区**：日志与事件流 `timestamp` / `entry_time` 为 UTC epoch 秒；**本报告所有"北京"时间 = UTC + 8h**。事件文件按 UTC 日切分，故北京时间 11-02 的成交可能落在 `2026-11-01/paper_trades.jsonl`（见 §3 表下注）。
> **路径约定**：下文 `$LOG` = `D:/AIDCA/AI300-fwdlib/logs`，`$DOC` = `D:/AIDCA/AI300-fwdlib/docs`，`$SRC` = `D:/AIDCA/AI300-fwdlib/src`，`$EF` = `C:/Users/Huang/.eigenflux/servers/eigenflux/data`。`$LOG/...` 是对应**绝对路径**的简写；§10「出处索引」给出每个锚点未缩写的形式与行号。
> **证据分级**（全文强制）：【已核实】= 可直接回源码/日志行定位；【推算】= 由【已核实】输入经本文写明公式算出；【未核实】= 现有日志/源码无法得到；【线索】= 仅单一指标支撑、未达归因升级门槛；【非独立】= 对我方内容的回应，不作证据。
> **复现**：全部聚合为对事件流按字段求和，命令见 §10.2。

---

## 0. 结论摘要（先给结论）

**【已核实】全窗口（重启后至 11-08）主账本是净盈利 `+33.762404` USDT，不是净亏损。** 出处：`$LOG/2026-11/2026-11-08/paper_summary.json:realized_notional_pnl = 33.76240389561417`；等价于 11 笔逐笔 `net_pnl_full` 求和 `33.76240390`（§10.1 对账差值 `−7.105e-15`）。

**【已核实】用户口径里的"亏损"实际分布在三处，且都不是全窗口主账本净额：**

| "亏损"所在 | 数值 (USDT) | 出处 | 性质 |
|---|---:|---|---|
| 累计负段：11-01 → 11-03（11-04 转正），谷底 11-03 | 最低 `−8.606919` | `$LOG/2026-11/2026-11-03/paper_summary.json:realized_notional_pnl` | 过程量（累计曲线的一段），非期末净额 |
| scout_micro 臂 | `−3.323394`（12 笔） | `$LOG/2026-11/2026-11-08/scout_micro/paper_summary.json:realized_notional_pnl`、`trade_count` | 独立模拟账本 |
| AB trend_capture 臂 | `−5.121646`（74 笔） | `$LOG/2026-11/2026-11-08/paper_summary.json:ab_ledger.trend_capture.realized_notional_pnl`、`trade_count` | 独立模拟账本 |

**【已核实】净盈利高度集中于单一笔**：`NEARUSDT:1793889000:SHORT`（第 ⑨ 笔）`net_pnl_full = +32.948542`（`$LOG/2026-11/2026-11-05/paper_trades.jsonl:L2-L4` 三次减仓之和 `7.698233209 + 11.991883623 + 13.258425414`），占净额 `97.59%`【推算：`32.948542 / 33.762404`】；**剔除该笔后净额仅 `+0.813862`**【推算：`33.762404 − 32.948542`】。占总盈利（`45.362122`）`72.63%`【推算：`32.948542 / 45.362122`】；前 2 笔占总盈利 `98.70%`【推算：`(32.948542 + 11.824286) / 45.362122`】。

**一句话判定 alpha：证据不足，不能判定。**【未核实 / 不能作为结论】理由：`n=11`、3 胜【已核实：`$LOG/2026-11/2026-11-08/paper_summary.json:trade_count=11`、`win_rate=0.2727272727272727`】，按「同 symbol 同 UTC 日」聚簇后 `n_eff=9`【推算，§5】，Wilson 95% 区间与打平胜率区间互相覆盖（§5），且全部正收益由 ≤2 笔决定。本文**不写**"策略有效/无效/有优势/无优势/因子没用"任何一类结论，也不写投资建议。

---

## 1. 口径与边界

### 1.1 重启时点与实跑配置【已核实】

- 窗口起点：`$LOG/2026-10/2026-10-31/runtime.out.12.log:L1` = `=== AI300_DRY_RUN process_start @ 2026-10-31 12:02:35 UTC === [mode=public-binance, kline_align=ON, tf=900s]`（北京 20:02:35）。
- `$LOG/2026-10/2026-10-31/runtime.out.12.log:L2` = `进程启动: pid=7839, config=configs/entry_chain.dry_run_regime_shadow.json, target_tier=conservative, log_root=/root/AIBOT/logs`。
- 同文件 `L3` = `交易对宇宙: ... symbols=14`；`L5` = `first_scan_wait: ... post_close_delay=10.00s, ...`（另 `L1` 已标 `kline_align=ON, tf=900s`；`L4` 为「启动预热完成」行、`L6` 为空行，二者不承载上述配置值）。
- **此后至 11-08 无新 `process_start`**【已核实】：对 `$LOG/2026-11/2026-11-0{1..8}/runtime.out.*.log` 全量检索命中 0 行；10-31 当日仅 `runtime.out.06.log:L1,L142,L553,L559,L835,L841` 六次（09:59:17 / 10:03:35 / 10:55:54 / 10:57:46 / 11:04:51 / 11:05:37 UTC）与 `runtime.out.12.log:L1` 一次。
- 重启前崩溃【已核实】：`$LOG/2026-10/2026-10-31-bak/logs/errors.log` 共 4 个 traceback —— `FileNotFoundError: configs/entry_chain.dry_run_regime_shadow.json` ×2、`ValueError: unknown entry-chain config keys: ['regime_overlay','score_core']` ×2（报错点 `$SRC/signals/entry_chain_config.py:279` 与 `:240`）。这解释了为何 06 时段反复重启失败、12:02:35 才是有效起点。

### 1.2 时区【已核实】

日志/事件流为 UTC；报告表内时间一律北京（UTC+8）。例：第 ① 笔北京 11-02 01:45 = UTC 11-01 17:45，故落在 `2026-11-01/paper_trades.jsonl:L1-L2`；第 ⑩ 笔北京 11-06 23:45 → 11-07 00:30，两端均属 UTC 11-06，故同在 `2026-11-06/paper_trades.jsonl:L1-L2`。**"跨北京时间日"不等于"跨事件文件日"**，核对时不可混用。

### 1.3 PnL 口径铁律【已核实】

出处：`$DOC/2026-10-31-评审回应与落地计划.md:35-39, 75, 95-99`；`$SRC/observability/paper_trading.py:25-30, 384-388, 413-425, 469-479`。

| 字段 | 定义 | 地位 |
|---|---|---|
| `net_pnl_full` | `net_pnl − entry_cost`，其中 `entry_cost = (entry_fee + entry_slippage) × fraction`（`paper_trading.py:387-388, 418, 420`） | **权威口径**，本报告唯一作结论依据的净额 |
| `net_pnl` | `gross − exit_fee − exit_slippage`（`paper_trading.py:384`） | close-only，**只能并列展示**，不作结论依据 |
| `realized_margin_pnl` / `margin_pnl` | `net × max(1, leverage)`（`paper_trading.py:389`），`paper_summary.json:margin_pnl_status = "deprecated_leverage_double_count"`（`paper_trading.py:479`） | **禁止作结论依据**，本文仅作为"虚高幅度"的对照对象出现（§6） |

`pnl_schema_version=2`（`paper_trading.py:30`）、`pnl_accounting_mode="notional_primary_margin_reporting"`（`paper_trading.py:425, 477`）在 11-01～11-08 全部事件行中一致【已核实，逐行抽查】。

### 1.4 累计计数器不可跨天求和【已核实】

`$DOC/CODEBUDDY.md:445`：`Never sum summary.json counters across days. They are cumulative since process start and are rewritten into every daily slice; recompute from the JSONL event files instead`。`$DOC/2026-10-31-评审回应与落地计划.md:17` 记录既有事故：把 6 个日切片 `summary.json:decision_counts` 相加，把 `5,850` 误算成 `20,475`。

因此：本报告**逐笔净额一律读按日轮转的 `paper_trades.jsonl` 事件流、按 `position_id` 聚合**；`paper_summary.json:realized_notional_pnl` 只用于"逐日累计曲线"（§2）与"期末对账"（§10），**从不把多日 `realized_notional_pnl` 相加**。

### 1.5 四套账本不可相加为组合净值【已核实】

MAIN、scout_micro、AB legacy、AB trend_capture 各自 `initial_equity=10000`（`$LOG/2026-11/2026-11-08/paper_summary.json:initial_equity` 及各子账本同名字段），是**独立模拟的同窗口回放**，不是四个子账户。故 §4「账本臂」表**不设跨臂合计**，仅 MAIN 臂的桥校验 `== 33.762404`。四臂成本参数一致【已核实】：`cost_source=constant_assumption`、`fee_bps=5.0`、`slippage_bps=5.0`（抽查 `$LOG/2026-11/2026-11-03/scout_micro/paper_trades.jsonl:L1`、`$LOG/2026-11/2026-11-05/paper_ab/legacy/paper_trades.jsonl:L1`、`$LOG/2026-11/2026-11-05/paper_ab/trend_capture/paper_trades.jsonl:L1`、`$LOG/2026-11/2026-11-05/paper_trades.jsonl:L1`）。

### 1.6 文档—运行漂移（单列）【已核实】

| 声明来源 | 声明内容 | 与实跑对比 |
|---|---|---|
| `$SRC/../deploy/systemd/ai300-dry-run.service:10` | `configs/entry_chain.dry_run_highest_win.json` + `--target-tier aggressive` + `--post-close-delay-seconds 5` | 与实跑三处全不一致 |
| `$SRC/../deploy/systemd/aibot.service:10` | 同上 | 同上 |
| `$DOC/../REASONIX.md:3` | `当前 VPS 以 dry-run 模式运行(aggressive tier)` | tier 不一致 |
| `$DOC/../REASONIX.md:15` | `configs/entry_chain.dry_run_fib_pa_v1.json` + `aggressive` + `5` | 配置/tier/延迟全不一致 |
| `$DOC/../CODEBUDDY.md:31-37` | `This is what systemd actually runs: BOTH ... have ExecStart pointing at configs/entry_chain.dry_run_highest_win.json`，并称其为 VPS 生产 | 与实跑不符 |
| **实跑**（`$LOG/2026-10/2026-10-31/runtime.out.12.log:L1-L3,L5`） | `regime_shadow` + `conservative` + `10.00s` + `kline_align=ON, tf=900s` + 14 symbols | 基准 |

> **勘误式说明**：曾有 subagent 报告「`runtime.out.12.log` 不在工作区」，系检索方式问题；主控已亲自 `head` 读到上述 L1-L2 内容（本报告写作时再次 `head` 复核，见 §1.1），**以主控与本次复核为准**。
> **边界推论**【推算，非结论】：任何形如"某阈值/某因子在本窗口有效"的归因，都缺少一个可复现的配置前提——文档声明与实跑不是同一份配置。该漂移**本身不解释盈亏方向**，只限制归因的可外推性（§8 备择解释 E5）。

---

## 2. 总览

### 2.1 逐日累计（`paper_summary.json:realized_notional_pnl`，权威口径；**不是增量，不可相加**）【已核实】

| 日期 | 累计 `realized_notional_pnl` | 当日增量【推算：`本日 − 前日`】 | 出处 |
|---|---:|---:|---|
| 10-31 | `+0.000000` | — | `$LOG/2026-10/2026-10-31/paper_summary.json:realized_notional_pnl` |
| 11-01 | `−4.858208` | `−4.858208` | `$LOG/2026-11/2026-11-01/paper_summary.json:realized_notional_pnl` |
| 11-02 | `−4.858208` | `+0.000000` | `$LOG/2026-11/2026-11-02/paper_summary.json:realized_notional_pnl` |
| 11-03 | `−8.606919` | `−3.748711` | `$LOG/2026-11/2026-11-03/paper_summary.json:realized_notional_pnl` |
| 11-04 | `+0.939285` | `+9.546204` | `$LOG/2026-11/2026-11-04/paper_summary.json:realized_notional_pnl` |
| 11-05 | `+33.887827` | `+32.948542` | `$LOG/2026-11/2026-11-05/paper_summary.json:realized_notional_pnl` |
| 11-06 | `+33.825053` | `−0.062774` | `$LOG/2026-11/2026-11-06/paper_summary.json:realized_notional_pnl` |
| 11-07 | `+33.762404` | `−0.062649` | `$LOG/2026-11/2026-11-07/paper_summary.json:realized_notional_pnl` |
| 11-08 | `+33.762404` | `+0.000000` | `$LOG/2026-11/2026-11-08/paper_summary.json:realized_notional_pnl` |

**读法**【已核实 + 推算】：累计为负的日期是 11-01、11-02、11-03，谷底 `−8.606919`（11-03）；11-04 单日 `+9.546204` 使累计转正；11-05 单日 `+32.948542` 恰等于第 ⑨ 笔 `NEARUSDT:1793889000:SHORT` 的 `net_pnl_full`（`$LOG/2026-11/2026-11-05/paper_trades.jsonl:L2-L4`）。11-08 四套账本 `paper_trades.jsonl` 均为 0 字节、`open_positions=0`【已核实：`$LOG/2026-11/2026-11-08/` 下 4 个事件流 + 4 份 `paper_summary.json:open_positions`】，故期末无未实现盈亏干扰。

> **注意**：上表"当日增量"是【推算】的**差分**，仅供读曲线用；它**不是**被求和的对象，且不与 §1.4 冲突——差分对象是同一个累计计数器，不是把多个计数器相加。

### 2.2 11-08 期末关键指标【已核实】

全部出处：`$LOG/2026-11/2026-11-08/paper_summary.json` 对应字段名。

| 指标 | 值 | 字段名 |
|---|---:|---|
| equity | `10033.762403895615` | `equity` |
| 净额（权威） | `33.76240389561417` | `realized_notional_pnl` |
| 平仓笔数 | `11` | `trade_count` |
| 胜率 | `0.2727272727272727` | `win_rate` |
| profit_factor | `3.91062282666126` | `profit_factor` |
| actual_payoff_ratio | `10.42832753776336` | `actual_payoff_ratio` |
| avg_win / avg_loss | `15.120707287312584` / `1.4499647457904485` | `avg_win` / `avg_loss` |
| max_drawdown | `0.002800641691825005` | `max_drawdown` |
| open_positions | `0` | `open_positions` |
| `pnl_schema_version` | `2` | `pnl_schema_version` |
| `margin_pnl_status` | `deprecated_leverage_double_count` | `margin_pnl_status` |

> 字段口径（交易含义，不改数值）：`profit_factor`（PF）= 总盈利 / 总亏损，按**仓位级** `net_pnl_full` 正负求和，非事件级；`actual_payoff_ratio`（payoff）= `avg_win` / `avg_loss`。

### 2.3 10B 历史基线对照【已核实】

`$DOC/2026-10-31-评审回应与落地计划.md:43`（`9.42 − 11.77 = −2.35  ← full-cost（头条）`）与 `:87`（`主账本净额 | −2.35 | −2.35 | 不变（full-cost）`）：重启前的 10B 基线为 **`−2.35` USDT / 6 天（full-cost）**，6 天窗口见同文档 `:23-28`（10-26..10-31 六个日切片）。

**对照读法**【推算，仅陈述差值，不升级为结论】：本窗口 `+33.762404` 与基线 `−2.35` 相差 `+36.112404`【`33.762404 − (−2.35)`】。但两者窗口长度（6 天 vs 9 天）、`pnl_schema_version`（10B 稿件为 v1 close-only 分维度表 + full-cost 头条，见 `:39, :75`）与配置均不同，**不构成同口径前后对比**；且本窗口 `97.59%` 由 1 笔决定，差值不能读作"改进"。【未核实】是否存在同配置、同 schema 的可比历史回放。

---

## 3. 逐笔明细表（11 笔完整生命周期）【已核实】

`net_pnl_full` 单位 USDT；时间为**北京**；「出场原因」列给出该仓位全部出场事件链（按事件 `reason`），末位即 `PAPER_CLOSE.reason`。每行「出处」为**绝对路径 + 行号**。

| # | position_id | 入场→出场(北京) | symbol | side | channel | quadrant | score | lev | 出场原因（事件链） | net_pnl_full | 出处 |
|---:|---|---|---|---|---|---|---:|---:|---|---:|---|
| ① | `UNIUSDT:1793555100:SHORT` | 11-02 01:45→04:30 | UNIUSDT | SHORT | `main_direct` | Q1 | 88.19 | 4 | `COST_BREAKEVEN_TIMEOUT` | `−4.795800` | `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-01/paper_trades.jsonl:L1-L2` |
| ② | `BNBUSDT:1793570400:SHORT` | 11-02 06:00→06:45 | BNBUSDT | SHORT | `q1_trend_launch` | Q1 | 84.70 | 1 | `INITIAL_STOP_HIT` | `−0.062408` | `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-01/paper_trades.jsonl:L3-L4` |
| ③ | `UNIUSDT:1793700900:LONG` | 11-03 18:15→20:15 | UNIUSDT | LONG | `q1_trend_launch` | Q1 | 85.69 | 1 | `TP1_HIT` + `Q3_DEFENSIVE_REDUCE` + `BREAKEVEN_STOP_HIT` | `+0.589294` | `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-03/paper_trades.jsonl:L1-L4` |
| ④ | `SOLUSDT:1793724300:LONG` | 11-04 00:45→01:15 | SOLUSDT | LONG | `q1_trend_launch` | Q1 | 87.69 | 1 | `INITIAL_STOP_HIT` | `−0.062536` | `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-03/paper_trades.jsonl:L5-L6` |
| ⑤ | `UNIUSDT:1793732400:SHORT` | 11-04 03:00→05:00 | UNIUSDT | SHORT | `main_direct` | Q3 | 85.30 | 4 | `COST_BREAKEVEN_TIMEOUT` | `−4.275469` | `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-03/paper_trades.jsonl:L7-L8` |
| ⑥ | `HYPEUSDT:1793776500:LONG` | 11-04 15:15→20:00 | HYPEUSDT | LONG | `main_probe` | Q1 | 88.69 | 3 | `TP1_HIT` + `TP2_HIT` + `BREAKEVEN_STOP_HIT` | `+11.824286` | `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-04/paper_trades.jsonl:L1-L4` |
| ⑦ | `BCHUSDT:1793800800:SHORT` | 11-04 22:00→22:30 | BCHUSDT | SHORT | `q1_trend_launch` | Q1 | 86.10 | 1 | `INITIAL_STOP_HIT` | `−0.518497` | `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-04/paper_trades.jsonl:L5-L6` |
| ⑧ | `HYPEUSDT:1793820600:SHORT` | 11-05 03:30→06:15 | HYPEUSDT | SHORT | `main_probe` | Q1 | 85.09 | 3 | `COST_BREAKEVEN_TIMEOUT` | `−1.759585` | `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-04/paper_trades.jsonl:L7-L8` |
| ⑨ | `NEARUSDT:1793889000:SHORT` | 11-05 22:30→23:15 | NEARUSDT | SHORT | `main_direct` | Q1 | 89.25 | 4 | `TP1_HIT` + `TP2_HIT` + `TP3_HIT` | **`+32.948542`** | `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-05/paper_trades.jsonl:L1-L4`（三次减仓 `net_pnl_full` = `7.698233209` / `11.991883623` / `13.258425414`，见 `L2` / `L3` / `L4`） |
| ⑩ | `LINKUSDT:1793979900:LONG` | 11-06 23:45→11-07 00:30 | LINKUSDT | LONG | `q1_trend_launch` | Q1 | 89.19 | 1 | `INITIAL_STOP_HIT` | `−0.062775` | `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-06/paper_trades.jsonl:L1-L2` |
| ⑪ | `LINKUSDT:1794024000:SHORT` | 11-07 12:00→12:30 | LINKUSDT | SHORT | `q1_trend_launch` | Q1 | 86.59 | 1 | `INITIAL_STOP_HIT` | `−0.062649` | `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-07/paper_trades.jsonl:L1-L2` |
| **合计** | **11 笔 / 17 出场事件** | | | | | | | | | **`+33.762404`** | 出处：上列 28 行事件按 `position_id` 聚合求和；公式见 §10.2 |

**逐笔表下注**【已核实】：`score` / `lev` / `quadrant` / `channel` / `side` / `symbol` 均取各仓位 `PAPER_OPEN` 行字段（如 `2026-11-05/paper_trades.jsonl:L1` 的 `"score": 89.25, "leverage": 4, "source_quadrant": "Q1", "entry_channel": "main_direct"`）；`net_pnl_full` 取同 `position_id` 下全部 `PAPER_CLOSE`/`PAPER_REDUCE` 行的 `net_pnl_full` 之和（v2 schema，`$SRC/observability/paper_trading.py:420`）。**未使用** `net_pnl`、`realized_margin_pnl`、跨日累计计数器。
> **显示精度说明（显式勘误）**：本表 `net_pnl_full` 显示到 6 位小数，11 个显示值相加为 `33.762403`；未舍入精确值之和为 `33.762403895614`（§10.1、§10.3），差 `≈1e-6` 纯属四舍五入，**不是口径差异**。表内「合计」写 `+33.762404` 指精确值。

---

## 4. P&L 桥（全部校验合计 == `33.762404`）

> 生成方式【已核实】：对 `$LOG/2026-10/2026-10-31/` 与 `$LOG/2026-11/2026-11-0{1..8}/` 下 4 类事件流中 MAIN 账本的 28 行逐行取 `net_pnl_full` 聚合；17 个出场事件的精确 `文件:行号 + net_pnl_full` 列于 §10.3。下表每行「出处」给出该行由哪些事件行相加而来，可用 §10.2 命令复算。

### 4.1 事件级（按 17 个出场事件的 `reason`）

| 出场原因 | 事件数 | Σ `net_pnl_full` | 出处（事件行） |
|---|---:|---:|---|
| `TP2_HIT` | 2 | `+19.344283` | `2026-11-04/paper_trades.jsonl:L3` (`+7.352399538`) + `2026-11-05/paper_trades.jsonl:L3` (`+11.991883623`) |
| `TP3_HIT` | 1 | `+13.258425` | `2026-11-05/paper_trades.jsonl:L4` (`+13.258425414`) |
| `TP1_HIT` | 3 | `+12.690282` | `2026-11-03:L2` (`+0.270127966`) + `2026-11-04:L2` (`+4.721920822`) + `2026-11-05:L2` (`+7.698233209`) |
| `Q3_DEFENSIVE_REDUCE` | 1 | `+0.256693` | `2026-11-03/paper_trades.jsonl:L3` (`+0.256692549`) |
| `BREAKEVEN_STOP_HIT` | 2 | `−0.187561` | `2026-11-03:L4` (`+0.062473350`) + `2026-11-04:L4` (`−0.250034610`) |
| `INITIAL_STOP_HIT` | 5 | `−0.768864` | `2026-11-01:L4` + `2026-11-03:L6` + `2026-11-04:L6` + `2026-11-06:L2` + `2026-11-07:L2` |
| `COST_BREAKEVEN_TIMEOUT` | 3 | `−10.830854` | `2026-11-01:L2` + `2026-11-03:L8` + `2026-11-04:L8` |
| **合计** | **17** | **`+33.762404`** | 【推算】Σ 上 7 行 = `33.762403896`，与 `paper_summary.json:realized_notional_pnl` 差 `−7.105e-15`（§10.1） |

### 4.2 仓位级（按 `PAPER_CLOSE.reason`，11 笔）

| `PAPER_CLOSE.reason` | 笔数 | Σ `net_pnl_full` | 占净额【推算：`行值 / 33.762404`】 |
|---|---:|---:|---:|
| `TP3_HIT` | 1 | `+32.948542` | `97.59%` |
| `BREAKEVEN_STOP_HIT` | 2 | `+12.413580` | `36.77%` |
| `COST_BREAKEVEN_TIMEOUT` | 3 | `−10.830854` | `−32.08%` |
| `INITIAL_STOP_HIT` | 5 | `−0.768864` | `−2.28%` |
| **合计** | **11** | **`+33.762404`** | `100.00%` |

出处：`PAPER_CLOSE` 行 = `2026-11-01:L2,L4`、`2026-11-03:L4,L6,L8`、`2026-11-04:L4,L6,L8`、`2026-11-05:L4`、`2026-11-06:L2`、`2026-11-07:L2`（各仓位全事件求和，见 §3）。【已核实】占比一列为【推算】。

### 4.3 象限 / 方向 / 通道（按仓位 `PAPER_OPEN` 字段聚合）

| 维度 | 取值 | 笔数 | Σ `net_pnl_full` | 校验 |
|---|---|---:|---:|---|
| 象限 | Q1 | 10 | `+38.037873` | |
| 象限 | Q3 | 1 | `−4.275469` | |
| **象限小计** | | **11** | **`+33.762404`** | ✓ |
| 方向 | SHORT | 7 | `+21.474135` | |
| 方向 | LONG | 4 | `+12.288269` | |
| **方向小计** | | **11** | **`+33.762404`** | ✓ |
| 通道 | `main_direct` | 3 | `+23.877273` | |
| 通道 | `main_probe` | 2 | `+10.064701` | |
| 通道 | `q1_trend_launch` | 6 | **`−0.179570`** | |
| **通道小计** | | **11** | **`+33.762404`** | ✓ |

出处：各仓位 `PAPER_OPEN` 行 `source_quadrant` / `side` / `entry_channel`（§3 出处列）+ 同仓位全部出场事件 `net_pnl_full` 求和。【已核实】三张小计各自等于 `33.762404`【推算：逐行相加】。

> **只登记为【线索】，不升级为结论**：`q1_trend_launch` 6 笔 `−0.179570`、Q3 1 笔 `−4.275469` 均只有**单一维度指标**支撑，未满足 §8 的跨域双指标收敛门槛；且 `q1_trend_launch` 的负值由 1 笔 `BCHUSDT:1793800800:SHORT`(`−0.518497`) 主导，样本内构成差异未排除。

### 4.4 账本臂（**不可相加为组合净值**）

| 账本臂 | 笔数 | `realized_notional_pnl` | 胜率 | 出处 |
|---|---:|---:|---:|---|
| MAIN | 11 | `+33.762404` | `0.2727` | `$LOG/2026-11/2026-11-08/paper_summary.json:realized_notional_pnl`、`trade_count`、`win_rate` |
| scout_micro | 12 | `−3.323394` | `0.1667` | `$LOG/2026-11/2026-11-08/scout_micro/paper_summary.json:realized_notional_pnl`、`trade_count`、`win_rate` |
| AB legacy | 73 | `+25.087716` | `0.1507` | `$LOG/2026-11/2026-11-08/paper_summary.json:ab_ledger.legacy.*` |
| AB trend_capture | 74 | `−5.121646` | `0.0811` | `$LOG/2026-11/2026-11-08/paper_summary.json:ab_ledger.trend_capture.*` |

**校验说明**【已核实】：按 §1.5，四臂为独立模拟（各自 `initial_equity=10000`），**本表不设跨臂合计**，因此不存在"四臂求和 == 33.762404"的校验项；能校验 `== 33.762404` 的是 §4.1 / §4.2 / §4.3 五张表以及 MAIN 臂自身（其 Σ `net_pnl_full` 逐笔聚合 `= 33.762403895614`，与 `paper_summary.json:realized_notional_pnl` 差 `−7.105e-15`，§10.1）。四臂各自对账差值 `≤ 2.5e-14`【已核实，§10.1】。

---

## 5. 离群依赖度与统计边界

### 5.1 集中度【已核实 + 推算】

| 指标 | 值 | 公式与输入 | 出处 |
|---|---:|---|---|
| 净额 | `33.762404` | Σ 11 笔 `net_pnl_full` | §3 合计 / `paper_summary.json:realized_notional_pnl` |
| 总盈利（正 `net_pnl_full` 之和） | `45.362122` | `32.948542 + 11.824286 + 0.589294`（3 胜：⑨、⑥、③） | §3 行 ⑨ / ⑥ / ③ |
| 第 ⑨ 笔占净额 | `97.59%` | `32.948542 / 33.762404` | 同上 |
| 第 ⑨ 笔占总盈利 | `72.63%` | `32.948542 / 45.362122` | 同上 |
| 前 2 笔占总盈利 | `98.70%` | `(32.948542 + 11.824286) / 45.362122` | 同上 |
| 剔除第 ⑨ 笔后净额 | `+0.813862` | `33.762404 − 32.948542` | 同上 |
| `HHI(\|net_full\|)` | `0.3915` | `Σ (\|x_i\| / Σ\|x_i\|)²`，`x_i` = 11 笔 `net_pnl_full`；均匀基准 `1/11 = 0.0909` | §3 逐笔值 |

【推算】`HHI` 输入为 §3 的 11 个 `net_pnl_full`：`[−4.795800, −0.062408, +0.589294, −0.062536, −4.275469, +11.824286, −0.518497, −1.759585, +32.948542, −0.062775, −0.062649]`；`Σ x_i = 33.762403`、`Σ|x_i| = 56.961841`【推算】，故 `HHI = Σ(|x_i|/56.961841)² = 0.3915`。

### 5.2 显著性与打平胜率【已核实输入 + 推算】

输入【已核实】：`n=11`、`k=3`（`paper_summary.json:trade_count=11`、`win_rate=0.2727272727272727`，3 个正 `net_pnl_full` 见 §3）、`payoff = 10.42832753776336`（`paper_summary.json:actual_payoff_ratio`）。

| 量 | 值 | 公式 |
|---|---:|---|
| `p̂` | `0.272727` | `k/n = 3/11` |
| Wilson 95%（按笔） | **`[0.097461, 0.565645]`** | `z=1.959964`；`p̂=3/11`；`center=(p̂+z²/2n)/(1+z²/n)`，`half=z·√(p̂(1−p̂)/n+z²/4n²)/(1+z²/n)` |
| 打平胜率 `p_be` | **`0.087502`** | `1/(1+payoff) = 1/(1+10.42832753776336)` |
| 二项 `P(X≥3 \| n=11, p=p_be)` | **`0.064836`** | `Σ_{i=3}^{11} C(11,i)·p_be^i·(1−p_be)^(11−i)`；`≥ 0.05` |
| 按簇 `n_eff` | **`9`** | 「同 `symbol` 同 UTC 日」聚簇，11 笔 → 9 簇（UNIUSDT@11-01 与 BNBUSDT@11-01 各 1；UNIUSDT@11-03 与 SOLUSDT@11-03 共 3；HYPEUSDT@11-04 与 BCHUSDT@11-04 共 3；NEARUSDT@11-05 1；LINKUSDT@11-06 1；LINKUSDT@11-07 1） |
| 簇胜率 | `0.2222` | `2/9`（胜簇：`HYPEUSDT@11-04` `+10.064701`、`NEARUSDT@11-05` `+32.948542`） |
| Wilson 95%（按簇） | **`[0.063225, 0.547411]`** | 同上公式，`k=2, n=9`；**区间覆盖 `p_be=0.087502`** |
| 相邻入场最小间隔 | `9 bar`（`135 min`） | 11 个 `entry_time` 排序后差分 / `900s`，最小值 `8100s`；全部间隔(bar) `17,145,26,9,49,27,22,76,101,49` |

### 5.3 统计边界的明确表述

**【未核实 / 不能作为结论】11 笔无法判定有无优势。** 依据：按笔二项 `p=0.064836 ≥ 0.05`【推算】，按笔 Wilson 区间 `[0.097461, 0.565645]` 与 `p_be=0.087502` 不重叠但极接近下限、按簇 Wilson `[0.063225, 0.547411]` **覆盖** `p_be`【推算】，且 `n_eff=9 < n=11`。样本量低于 `$DOC/CODEBUDDY.md:441` 的`<10 trades: no "works/doesn't work" verdict` 门槛（`n_eff=9`）。**本文不写"有优势""无优势""策略无效"任何一类结论。**

**【未核实】块长敏感性**：5 条硬检查第 ② 条要求"报 `n_eff` 而非名义笔数、块长敏感性"。本报告已报 `n_eff=9`（单一聚簇定义：同 symbol 同 UTC 日），但**未做多块长 / 块 bootstrap 敏感性分析**，故该子项记 `NOT_RUN`，不宣称通过。相邻入场最小间隔 `9 bar`（`135 min`）只说明配对稀疏，**不等于**统计独立【推算】。

---

## 6. 成本分解

### 6.1 三口径桥【已核实 + 推算】

出处：28 行事件流字段 `gross_pnl` / `net_pnl` / `net_pnl_full` / `fee` / `slippage` / `entry_cost` / `exit_cost`（字段定义 `$SRC/observability/paper_trading.py:384-388, 413-420`）；17 个出场事件行号见 §10.3。

| 口径 | 值 (USDT) | 公式【推算】 | 出处 |
|---|---:|---|---|
| Σ `gross_pnl` | `+48.428980` | 17 出场事件 `gross_pnl` 求和 | 事件流字段 |
| − Σ `exit_cost`（出场 `fee+slippage`） | `−7.323750` | `3.661875 + 3.661875` | 事件流 `fee`/`slippage`（仅出场事件） |
| = Σ `net_pnl`（close-only，**仅并列**） | `+41.105230` | `48.428980 − 7.323750` | 事件流 `net_pnl` |
| − Σ `entry_cost`（建仓成本摊分） | `−7.342826` | 17 出场事件 `entry_cost` 求和 | 事件流 `entry_cost` |
| = **Σ `net_pnl_full`（权威）** | **`+33.762404`** | `41.105230 − 7.342826` | 事件流 `net_pnl_full` |

### 6.2 成本总量与占比【已核实 + 推算】

- `fee` 合计 `7.333288`、`slippage` 合计 `7.333288`【已核实】：此处为**全部 28 行事件（11 开仓 + 17 出场）**的 `fee` / `slippage` 求和；仅出场事件之和各为 `3.661875`（合计 `7.323750` = `exit_cost`）。开仓事件同样带 `fee`/`slippage`（例：`2026-11-05/paper_trades.jsonl:L1` 的 `fee=0.81995735`、`slippage=0.81995735`）。**读者注意**：`7.333288` 与 `7.323750` 不是同一个量，前者含开仓端成本，后者仅出场端，二者不可混用。
- `fee + slippage = 14.666576`【推算：`7.333288 × 2`】= `entry_cost 7.342826 + exit_cost 7.323750`【推算，恒等式】。
- 占净额 `43.44%`【推算：`14.666576 / 33.762404`】；占毛盈亏 `30.28%`【推算：`14.666576 / 48.428980`】。
- 每笔均摊 `1.333325`【推算：`14.666576 / 11`】。
- `entry_cost 7.342826` / `exit_cost 7.323750`【已核实，事件流同名字段求和】。

### 6.3 deprecated margin 虚高对照【已核实 + 推算】

`$LOG/2026-11/2026-11-08/paper_summary.json:realized_margin_pnl = 125.52362430070241`，同文件 `margin_pnl_status = "deprecated_leverage_double_count"`。`125.523624 / 33.762404 = 3.7179` ≈ **`3.72×`**【推算】。该字段按 `net × leverage` 放大（`paper_trading.py:389`），**依 §1.3 禁止作结论依据**；本文仅用它量化"若误用会虚高多少"。

### 6.4 与 10-31 评审 P0 口径对账呼应【已核实】

`$DOC/2026-10-31-评审回应与落地计划.md:35-39` 指出 v1 的 `net_pnl` 不含建仓成本，导致分维度表（close-only）与头条 equity（full-cost）差 `5.90`（主账本）；`:95-99` 的 T1 落地 `net_pnl_full`、`pnl_schema_version=2`，验收条件为「每个维度的 full-cost 合计 == 头条 `realized_notional_pnl`（容差 <0.01）」。本窗口 §4.1 / §4.2 / §4.3 五张桥**全部**精确等于 `33.762404`（§10.1 差值 `−7.105e-15`，远小于 `0.01`），即该 P0 修复在本窗口生效【已核实】。因此「建仓成本是否入账」在本窗口**已排除**为口径错配来源（§8 备择解释 E2）。

---

## 7. trend_capture 臂专项

### 7.1 配对结果【已核实 + 推算】

配对键 `symbol + entry_time + side`；数据源 `$LOG/2026-10/2026-10-31/` 与 `$LOG/2026-11/2026-11-0{1..8}/` 下 `paper_ab/legacy/paper_trades.jsonl` 与 `paper_ab/trend_capture/paper_trades.jsonl`，按 `position_id` 聚合 `net_pnl_full`。

| 项 | 值 | 说明 / 出处 |
|---|---:|---|
| 交集 | `73` 对 | LG 73 仓、TC 74 仓；`LG-only=0`、`TC-only=1` |
| 两臂完全相同 | `63` 对 | `\|diff\| < 1e-9` 的对数 |
| LG 优 / TC 优 | `6` / `4` | `diff>0` / `diff<0`；`63+6+4=73`【推算】 |
| Σ `diff`（73 对，`LG − TC`） | `+30.006455` | 【推算】逐对 `net_pnl_full` 之差求和 |
| TC-only 1 笔 | `−0.202908` | `NEARUSDT:1793889900:SHORT`；精确 `net_pnl_full = −0.20290768920000526`（`$LOG/2026-11/2026-11-05/paper_ab/trend_capture/paper_trades.jsonl:L15`，同文件 `:L14` 为开仓） |
| 臂总额差 | `+30.209362` | 【推算】`25.087716 − (−5.121646) = 30.209362`；交叉校验 `30.006455 + 0.202907689 = 30.209362689`，末位 `1e-6` 为显示舍入 |
| Σ `\|diff\|`（73 对） | `41.959735` | 【推算】`Σ\|diff\| = 41.959735`（逐对 `\|LG − TC\|` 求和），作下行 `82.43%` 的分母；臂总额差 `30.209362` 是另一分母（§7.3(b)） |
| 前 1 大 `\|diff\|` 占 Σ`\|diff\|` | **`82.43%`** | 【推算】`34.586817 / 41.959735`（分母 `Σ\|diff\|`；臂总额差 `30.209362` 是另一分母，不可混用，见 §7.3(b)）；该对 `NEARUSDT@1793889000`：LG `+32.948542`、TC `−1.638275`、`diff=+34.586817` |

### 7.2 TC 出场构成【已核实】

对 `paper_ab/trend_capture/paper_trades.jsonl` 全窗口出场事件按 `reason` 聚合 `net_pnl_full`：

| reason | 事件数 | Σ `net_pnl_full` |
|---|---:|---:|
| `INITIAL_STOP_HIT` | 47 | `−11.191172` |
| `Q4_DEFENSIVE_EXIT` | 20 | `−2.968198` |
| `Q3_DEFENSIVE_REDUCE` | 25 | `−1.033965` |
| `BREAKEVEN_STOP_HIT` | 4 | `+2.711082` |
| `TP2_HIT` | 3 | `+7.806450` |
| `TP1_HIT` | 5 | `+5.589211` |
| `COST_BREAKEVEN_TIMEOUT` | 2 | `−6.035054` |
| **`TP3_HIT`** | **0** | — |

对照：`paper_ab/legacy/paper_trades.jsonl` 的 `TP3_HIT` = **2 事件 / `+13.485278`**【已核实】；MAIN 账本 `TP3_HIT` = 1 事件 / `+13.258425`（§4.1，`2026-11-05/paper_trades.jsonl:L4`）。

### 7.3 不能解释为机制优劣【推论，非结论】

**【本报告的推论】**「两臂差异」目前**不能**解释为出场机制优劣。依据：(a) `63/73 = 86.3%`【推算】的配对两臂结果完全相同，臂间差异集中在极少数对；(b) **1 对**（`NEARUSDT@1793889000`，`|diff| = 34.586817`）占 **`Σ|diff| = 41.959735`** 的 **`82.43%`**【推算：`34.586817 / 41.959735`，分母为 `Σ|diff|`，见 §7.1】；**臂总额差 `30.209362` 是另一个分母，不可混用**——若误以臂总额差为分母，同一分子为 `34.586817 / 30.209362 = 114.49%`【推算】，>100% 源于 `Σ|diff|` 含双向抵消、而臂总额差是净额之差。该对正是 MAIN 账本第 ⑨ 笔右尾；(c) TC 臂 `TP3_HIT=0` 与 legacy `TP3_HIT=2` 的对比同样是**单一指标**，且未控制两臂在其余 63 对上的同一性。

【未核实】是否存在足以分离"出场机制"效应的独立对照（同一入场集、仅切换 `exit_mode` 且排除该右尾笔的配对子样本分析），本报告未做。按 §8 门槛，此项登记为**【线索】**。

---

## 8. 归因判断（分三层）

### 8.0 归因升级门槛（先声明规则）【采纳的检验规则 / 程序性门槛，非证据】

> 归因升级为结论，必须满足 **≥2 个独立指标、跨域收敛**，且**排除项留痕**；凡只有单一指标支撑的，只登记为【线索】。本报告**没有任何一条归因升级为结论**。

### 8.1 【已核实的事实】（可直接回源码/日志行定位，不含因果判断）

1. 全窗口主账本净额 `+33.762404`（`paper_summary.json:realized_notional_pnl`；§3 逐笔聚合）。
2. 11 笔 / 17 出场事件；3 笔正 `net_pnl_full`、8 笔负（§3）。
3. 第 ⑨ 笔 `+32.948542`，占净额 `97.59%`；剔除后 `+0.813862`（§5.1）。
4. 成本 `14.666576` = 净额 `43.44%`；v2 `net_pnl_full` 已含建仓成本摊分（§6）。
5. 累计负段谷底 `−8.606919`（11-03）；scout_micro `−3.323394`、AB trend_capture `−5.121646`（§0、§2.1、§4.4）。
6. 四臂独立模拟、各自 `initial_equity=10000`（§1.5）。
7. 文档声明配置与实跑配置三处不一致（§1.6）。
8. AB 配对 63/73 完全相同、1 对（`NEARUSDT@1793889000`）占 `Σ|diff| = 41.959735` 的 `82.43%`（分母为 `Σ|diff|`，见 §7.1、§7.3(b)；臂总额差 `30.209362` 是另一个分母，不可混用）、TC `TP3_HIT=0` vs legacy 2（§7）。
9. `n=11`、`n_eff=9`、Wilson 区间与 `p_be=0.087502` 关系（§5.2）。
10. 11-08 四账本 0 事件行、`open_positions=0`（§2.1）。

### 8.2 【本报告的推论】（写明公式/输入，均**不**升级为结论）

| 推论 | 依据与公式 | 状态 |
|---|---|---|
| P1 净额是"单笔右尾 + 小额负尾部"的叠加，而非均匀分布 | `HHI=0.3915` vs 均匀 `0.0909`；前 2 笔占总盈利 `98.70%`（§5.1） | 推论，依赖 §5 集中度单一指标族 → **线索** |
| P2 成本显著侵蚀小额笔 | `14.666576/33.762404=43.44%`；5 笔 `INITIAL_STOP_HIT` 合计 `−0.768864` 而 3 笔 `COST_BREAKEVEN_TIMEOUT` 合计 `−10.830854`（§4.1） | 推论，未控制入场质量 → **线索** |
| P3 11-04 的累计转正与 11-05 的跳升由 2 笔驱动 | 11-04 增量 `+9.546204`、11-05 增量 `+32.948542`（§2.1）；后者 = 第 ⑨ 笔 | 推论（算术恒等），已核实输入 |
| P4 文档-运行漂移限制任何"某因子/阈值有效"的外推性 | §1.6 四处声明 vs 实跑 | 推论，不解释盈亏方向 |
| P5 两臂差异不能解释为出场机制优劣 | §7.3 (a)(b)(c) | 推论 → **线索** |

> **明确不写的结论**：本文不写「策略无效」「策略有优势」「因子没用」「止损设置错误」「止盈太近」「配置漂移导致盈利/亏损」等任何因果结论；上述 P1–P5 均为待检验线索。

### 8.3 【未核实 / 无法从现有日志得到】

1. 是否有**方向性优势 / alpha**：`n_eff=9` 低于判定门槛，Wilson 区间覆盖 `p_be`（§5.3）。
2. 块长敏感性与块 bootstrap 结果（§5.3，`NOT_RUN`）。
3. 行情 regime 标注：窗口内无独立的 regime 标签数据可用于分层；未见窗口内新发的相关网络原文（§9）。
4. 同配置、同 `pnl_schema_version=2` 的可比历史回放（§2.3）。
5. 反事实：若第 ⑨ 笔未触发 `TP3_HIT`，其余仓位路径如何（`exit_mode` 分支未回放）。
6. 11-08 工作区日记（§9 数据缺口）。
7. 配置漂移对决策链各闸门的实际影响幅度（需 `regime_shadow` 与 `highest_win` 配置的对照回放，本报告未做）。
8. 四臂是否共享同一成本表之外的同一成交/撮合假设【部分核实：四臂 `cost_source=constant_assumption`、`fee_bps=5.0`、`slippage_bps=5.0` 已核实；撮合细节未核实】。

### 8.4 备择解释清单（逐条留痕：已排除 / 无法排除 / 线索）

| 编号 | 备择解释 | 状态 | 依据 |
|---|---|---|---|
| E1 | **单笔右尾**（`NEARUSDT:1793889000:SHORT` 的 `TP3_HIT`）主导净额 | **在现有单一指标下最突出、但未升级** | 占净额 `97.59%`、剔除后 `+0.813862`（§5.1）；但仅单一指标族，按门槛登记为**线索**而非结论 |
| E2 | **成本口径错配**（建仓成本未入账）造成"亏损"读数 | **已排除**（作为口径错配来源） | v2 `net_pnl_full` 含 `entry_cost` 摊分，五张桥精确对齐 `33.762404`（§6.4、§10.1）。但"成本结构决定小额笔负期望"作为**经济解释**仍**无法排除**（P2，线索） |
| E3 | **样本聚类 / 非独立性**导致名义 `n=11` 高估 | **无法排除** | `n_eff=9`（同 symbol 同 UTC 日）、相邻最小间隔 `9 bar`；块长敏感性 `NOT_RUN`（§5.2-5.3） |
| E4 | **出场臂机制优劣**（trend_capture 不如 legacy） | **无法排除，但不能解释为机制优劣** | 63/73 完全相同、1 对占 `Σ\|diff\| = 41.959735` 的 `82.43%`（分母为 `Σ\|diff\|`，见 §7.1、§7.3(b)；臂总额差 `30.209362` 是另一个分母，不可混用）、TC `TP3_HIT=0`（§7）；单一指标 → **线索** |
| E5 | **配置漂移**（文档 `highest_win/aggressive/5s` vs 实跑 `regime_shadow/conservative/10s`） | **无法排除其对结果的影响，但本身不解释盈亏方向** | §1.6 四处声明与实跑不符；缺同配置对照回放（§8.3 第 7 项） |
| E6 | **行情 regime**（窗口内某类行情恰好利于 1 笔 SHORT 右尾） | **无法排除 / 未核实** | 无窗口内独立 regime 标注；无窗口内新发相关原文（§9） |
| E7 | **通道差异**（`q1_trend_launch` 6 笔 `−0.179570`） | **无法排除，登记为线索** | 仅单一维度；负值由 `BCHUSDT:1793800800:SHORT`(`−0.518497`) 主导（§4.3） |

**跨域双指标收敛检查**：E1 与 E3 同属"样本/集中度"域，E2 属"成本"域，E4 属"出场机制"域，E5/E6 属"配置/外部环境"域。目前**没有任何一条**获得 ≥2 个独立域指标的收敛支持，故 §8.2 全部停留在【线索】，§8.3 全部保留为【未核实】。

---

## 9. 与 EigenFlux 网络材料的对照

### 9.1 为什么网络材料不作为证据【已核实，引用原文】

`$DOC/2026-10-31-paper-run-review-and-recommendations.md`：

- **L27**：`| 10 | 玄机 X3 与 D1 "独立同源,可信度较高" | **不独立** | 回复是对我方广播的回应,且"降杠杆反而放大亏损"并非 X3 原文 |`
- **L216**：`2. 玄机的回复是对我方此前广播的回应,广播里已带有"杠杆与通道质量倒挂"的叙述,**回复不是独立观察**。`
- **L219**：`外部意见只作为**检验清单的来源**,不作为证据。`

另有 `$DOC/2026-10-31-评审回应与落地计划.md:69` 接受该裁定：`"X3 原话不含'降杠杆反而放大亏损'，且回复是对我方广播的回应，不算独立" | **接受**。§6.3 的"独立同源"改为"同向但不独立，仅作检验清单来源"`。

**本窗口的独立性事实**【已核实 / C 路已核实】：`$DOC/analysis/eigenflux_optimization_2026-10-19.md:138` 记载我方 10-19 广播 `item_id = 370588327688011776`（demand，接受私信回复，**有效期至 2026-11-18**），覆盖整个 10-31→11-08 窗口；窗口内我方 **0 广播**、**20 个心跳周期全部只做回复**；私信内容多为「收下 / 采纳 / 按你的口径」（抽查 `$EF/messages/20261105/agent-308439639243358208.json` 首条即 `两条都采纳…`）。因此窗口内收到的意见是**我方 10-19 判据的回声**。用它佐证本报告的归因结论会构成**循环论证**——本报告不引用任何网络主张作为事实或证据。

### 9.2 独立性/来源裁定单列

| 条目 | 裁定 | 依据 |
|---|---|---|
| C 路审计的 **20 条私信条目** | **【非独立：对我方内容的回应】** | 窗口内 0 广播、20 心跳周期全部只做回复；10-19 我方广播覆盖窗口（§9.1） |
| 玄机 X3 / D1 "独立同源" | **不独立** | `$DOC/2026-10-31-paper-run-review-and-recommendations.md:L27` |
| 「止损零边际 alpha」相关网络主张 | **非窗口内新发原文** | 该条为约 09-18 存量 `item_id=359361979023884288`，于 11-06 重投【已核实：`$EF/broadcasts/20261106/feeds-20261106-203836.202205400.json` 与 `$EF/messages/20261106/conv_item_map.json` 命中该 id】；C 路核实窗口内**未找到**新发原文 |

### 9.3 网络方法论仅作检验清单（8 主题，【非独立】，不作证据）

单笔离群/事件簇 `n_eff`；跨域双指标收敛；负控与反向断言 / `exit0` 假绿 / 四态；成本口径同源与共用成本表；冻结阈值 `f(n)` + 翻转三层；止损零边际与块 bootstrap；确认成本与日历段数；证据摘要三元组 / 可验证≠有效。以上**仅用于生成 §9.4 的 5 条硬检查**，不进入 §8 的事实层。

### 9.4 5 条硬检查逐条结果

| # | 硬检查 | 结果 | 状态与出处 |
|---:|---|---|---|
| ① | 净额是否由 ≤2 笔决定 | **是（触发）** | 第 ⑨ 笔占 `97.59%`，前 2 笔占总盈利 `98.70%`，剔除后 `+0.813862`（§5.1）→ `FAIL`（不得把净额读作稳定产出） |
| ② | 报 `n_eff` 而非名义笔数、块长敏感性 | **部分满足** | 已报 `n_eff=9`（同 symbol 同 UTC 日）、Wilson `[0.063225, 0.547411]`（§5.2）；**块长敏感性 / 块 bootstrap 未做 → `NOT_RUN`**（§5.3） |
| ③ | 建仓成本是否计入 + 对照臂共用成本表 | **`PASS`** | v2 `net_pnl_full = net_pnl − entry_cost`（`$SRC/observability/paper_trading.py:387-388,420`）；五张桥对齐（§6.4、§10.1）；四臂 `cost_source=constant_assumption` + `fee_bps/slippage_bps=5.0`（§1.5） |
| ④ | 归因升级须 ≥2 独立指标跨域收敛、排除项留痕 | **未升级（合规）** | §8.0 声明门槛；§8.2 全部标【线索】、§8.4 逐条留痕；无任一归因升级为结论 |
| ⑤ | 假绿与 `PASS`/`FAIL`/`INCONCLUSIVE`/`NOT_RUN` 四态互斥、must-fail 反向断言 | **`NOT_RUN`** | 本报告未运行该夹具；网络材料仅提供清单（§9.1 L219），不构成证据。已在 §5.3、§9.4② 显式标记 `NOT_RUN`，未以"`PASS` 默认绿"代替 |

**四态互斥说明**【已核实】：本报告使用 `PASS`（③）、`FAIL`（①）、`NOT_RUN`（②的子项、⑤）、`INCONCLUSIVE`（§0 alpha 判定、§5.3、§8.3）；同一检查项只赋一态，无重叠。

### 9.5 数据覆盖与缺口【已核实 / C 路已核实】

**覆盖**：`$EF/messages/20261031..20261108/` 共 **183 文件**（本报告抽查计数 183 ✓）、**136 唯一 `msg_id` / 76 会话**（C 路核实；本报告粗按字段名提取得 135 / 75，差 1，属字段名启发式差异，**以 C 路为准，见 §11 存疑项**）；`$EF/broadcasts/` **23 快照 / 448 items**，其中仅 **204 条**为窗口内发布，其余为存量重投，且 items 只有英文 preview 摘要、无中文全文；**11-08 数据稀疏**。

**未找到（【未核实】缺口，不抹平）**：
1. 11-08 工作区日记；
2. 窗口内「建仓成本是否入账」的网络原文（该口径结论来自本地源码 `$SRC/observability/paper_trading.py` 与 `$DOC/2026-10-31-评审回应与落地计划.md`，**不是**网络主张）；
3. 窗口内「止损零边际 alpha」的**新发**原文（仅见 09-18 存量 `item_id=359361979023884288` 于 11-06 重投）；
4. 窗口内我方新广播（0 条）；
5. 网络原文的中文全文（items 仅英文 preview）。

---

## 10. 口径对账与复现

### 10.1 Σ `net_pnl_full` 与 `paper_summary.json` 的差值【已核实】

| 账本 | Σ 逐笔 `net_pnl_full` | `paper_summary.json:realized_notional_pnl` | 差值 |
|---|---:|---:|---:|
| MAIN | `33.762403895614` | `33.76240389561417` | `−7.105e-15` |
| scout_micro | `−3.323393930519` | `−3.3233939305192606` | `−4.441e-16` |
| AB legacy | `+25.087716097054` | `+25.087716097053836` | `+2.487e-14` |
| AB trend_capture | `−5.121646316362` | `−5.121646316362375` | `−3.553e-15` |

出处：左列 = 对 `$LOG/2026-10/2026-10-31/` + `$LOG/2026-11/2026-11-0{1..8}/` 下各账本 `paper_trades.jsonl` 全部 `PAPER_CLOSE`/`PAPER_REDUCE` 行的 `net_pnl_full` 求和；右列 = `$LOG/2026-11/2026-11-08/` 下各账本 `paper_summary.json:realized_notional_pnl`。四臂各自差值 `≤ 2.5e-14`【已核实】。11-08 全账本 0 事件行、`open_positions=0`（§2.1），故期末无未实现项干扰。

### 10.2 复现命令 / 文件路径【已核实】

事件流根：`D:/AIDCA/AI300-fwdlib/logs/2026-10/2026-10-31/` 与 `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-0{1..8}/`。

```bash
cd D:/AIDCA/AI300-fwdlib
# (1) 主账本 28 行事件、11 开仓 / 17 出场
for d in logs/2026-10/2026-10-31 logs/2026-11/2026-11-0{1..8}; do \
  wc -l "$d/paper_trades.jsonl"; done            # 10-31:0, 11-01..08: 4,0,8,8,4,2,2,0 → 合计 28 行
# (2) 逐笔 net_pnl_full 聚合（按 position_id），与期末对账
python - <<'PY'
import json, os
from collections import OrderedDict
days=["logs/2026-10/2026-10-31"]+[f"logs/2026-11/2026-11-0{i}" for i in range(1,9)]
ev=[]
for d in days:
    p=os.path.join(d,"paper_trades.jsonl")
    if os.path.exists(p):
        for line in open(p,encoding="utf-8"):
            if line.strip(): ev.append(json.loads(line))
pos=OrderedDict()
for e in ev: pos.setdefault(e["position_id"],[]).append(e)
tot=0.0
for pid,es in pos.items():
    s=sum(float(e.get("net_pnl_full") or 0) for e in es
          if e["event"] in ("PAPER_CLOSE","PAPER_REDUCE"))
    tot+=s; print(pid, f"{s:+.9f}")
print("positions=",len(pos), "SUM=", f"{tot:.12f}")
ref=json.load(open("logs/2026-11/2026-11-08/paper_summary.json"))["realized_notional_pnl"]
print("summary=", f"{ref:.14f}", "diff=", f"{tot-ref:+.3e}")
PY
# (3) 各分维度桥：把 (2) 中按 position_id 的 s 按 PAPER_OPEN 的
#     source_quadrant / side / entry_channel，或按出场事件 reason 分组求和；
#     §4.1/4.2/4.3 的每张表合计应 == 33.762403895614
# (4) AB 配对：把 paper_ab/legacy 与 paper_ab/trend_capture 的
#     paper_trades.jsonl 按 (symbol, entry_time, side) 建键，比较 net_pnl_full
# (5) 统计：Wilson(z=1.959964)、p_be=1/(1+actual_payoff_ratio)、
#     二项 Σ_{i=k}^{n} C(n,i) p^i (1-p)^(n-i)、HHI=Σ(|x|/Σ|x|)^2
```

关键单文件复现点：
- 重启：`D:/AIDCA/AI300-fwdlib/logs/2026-10/2026-10-31/runtime.out.12.log:L1-L3,L5`
- 崩溃：`D:/AIDCA/AI300-fwdlib/logs/2026-10/2026-10-31-bak/logs/errors.log`
- 第 ⑨ 笔三减仓：`D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-05/paper_trades.jsonl:L2-L4`
- 期末快照：`D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-08/paper_summary.json`
- 口径源码：`D:/AIDCA/AI300-fwdlib/src/observability/paper_trading.py:25-30, 378-430, 465-479`

### 10.3 17 个出场事件的精确出处索引（`net_pnl_full`）

| 文件:行号 | `reason` | `net_pnl_full` | position_id |
|---|---|---:|---|
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-01/paper_trades.jsonl:L2` | `COST_BREAKEVEN_TIMEOUT` | `−4.795800335` | `UNIUSDT:1793555100:SHORT` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-01/paper_trades.jsonl:L4` | `INITIAL_STOP_HIT` | `−0.062407530` | `BNBUSDT:1793570400:SHORT` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-03/paper_trades.jsonl:L2` | `TP1_HIT` | `+0.270127966` | `UNIUSDT:1793700900:LONG` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-03/paper_trades.jsonl:L3` | `Q3_DEFENSIVE_REDUCE` | `+0.256692549` | `UNIUSDT:1793700900:LONG` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-03/paper_trades.jsonl:L4` | `BREAKEVEN_STOP_HIT` | `+0.062473350` | `UNIUSDT:1793700900:LONG` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-03/paper_trades.jsonl:L6` | `INITIAL_STOP_HIT` | `−0.062535773` | `SOLUSDT:1793724300:LONG` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-03/paper_trades.jsonl:L8` | `COST_BREAKEVEN_TIMEOUT` | `−4.275468840` | `UNIUSDT:1793732400:SHORT` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-04/paper_trades.jsonl:L2` | `TP1_HIT` | `+4.721920822` | `HYPEUSDT:1793776500:LONG` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-04/paper_trades.jsonl:L3` | `TP2_HIT` | `+7.352399538` | `HYPEUSDT:1793776500:LONG` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-04/paper_trades.jsonl:L4` | `BREAKEVEN_STOP_HIT` | `−0.250034610` | `HYPEUSDT:1793776500:LONG` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-04/paper_trades.jsonl:L6` | `INITIAL_STOP_HIT` | `−0.518497133` | `BCHUSDT:1793800800:SHORT` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-04/paper_trades.jsonl:L8` | `COST_BREAKEVEN_TIMEOUT` | `−1.759585154` | `HYPEUSDT:1793820600:SHORT` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-05/paper_trades.jsonl:L2` | `TP1_HIT` | `+7.698233209` | `NEARUSDT:1793889000:SHORT` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-05/paper_trades.jsonl:L3` | `TP2_HIT` | `+11.991883623` | `NEARUSDT:1793889000:SHORT` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-05/paper_trades.jsonl:L4` | `TP3_HIT` | `+13.258425414` | `NEARUSDT:1793889000:SHORT` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-06/paper_trades.jsonl:L2` | `INITIAL_STOP_HIT` | `−0.062774512` | `LINKUSDT:1793979900:LONG` |
| `D:/AIDCA/AI300-fwdlib/logs/2026-11/2026-11-07/paper_trades.jsonl:L2` | `INITIAL_STOP_HIT` | `−0.062648689` | `LINKUSDT:1794024000:SHORT` |
| **合计（17 事件）** | | **`+33.762403896`** | |

### 10.4 其它数字的出处索引

| 数字 | 出处 |
|---|---|
| 逐日累计 9 个值 | `$LOG/2026-10/2026-10-31/` + `$LOG/2026-11/2026-11-0{1..8}/paper_summary.json:realized_notional_pnl`（§2.1 逐行列出） |
| equity / trade_count / win_rate / profit_factor / actual_payoff_ratio / avg_win / avg_loss / max_drawdown / open_positions | `$LOG/2026-11/2026-11-08/paper_summary.json` 同名字段（§2.2） |
| 四臂净额 / 笔数 / 胜率 | `$LOG/2026-11/2026-11-08/paper_summary.json:ab_ledger.*`、`scout_micro/paper_summary.json` 同名字段（§4.4） |
| `fee/slippage/entry_cost/exit_cost/gross_pnl/net_pnl/net_pnl_full` 各合计 | 28 行事件流同名字段求和（§6.1、§10.2） |
| `realized_margin_pnl=125.52362430070241` | `$LOG/2026-11/2026-11-08/paper_summary.json:realized_margin_pnl`（仅作虚高对照，§6.3） |
| 10B 基线 `−2.35 / 6 天` | `$DOC/2026-10-31-评审回应与落地计划.md:43, 87`（6 天见 `:23-28`） |
| 计数器陷阱 `20,475 → 5,850` | `$DOC/2026-10-31-评审回应与落地计划.md:17`；`$DOC/CODEBUDDY.md:445` |
| 文档漂移 4 处 | `$SRC/../deploy/systemd/ai300-dry-run.service:10`、`aibot.service:10`、`$DOC/../REASONIX.md:3,15`、`$DOC/../CODEBUDDY.md:31-37`（§1.6） |
| 独立性裁定 L27/L216/L219 | `$DOC/2026-10-31-paper-run-review-and-recommendations.md:27, 216, 219` |
| 10-19 广播 `item_id=370588327688011776` / 有效期 2026-11-18 | `$DOC/analysis/eigenflux_optimization_2026-10-19.md:138` |
| 存量重投 `item_id=359361979023884288`（11-06） | `$EF/broadcasts/20261106/feeds-20261106-203836.202205400.json`、`$EF/messages/20261106/conv_item_map.json` |
| EigenFlux 覆盖 183 / 136 / 76 / 23 / 448 / 204 | `$EF/messages/20261031..20261108/`、`$EF/broadcasts/`（C 路核实；本报告抽查 183 与 23 ✓，见 §9.5） |
| Wilson / `p_be` / 二项 / `n_eff` / HHI / 各类占比 | 【推算】公式与输入见 §5.1、§5.2、§6.2、§4.2、§7.1；输入均来自上列已核实项 |

---

## 11. 未回答的问题与下一步（不含投资建议）

### 11.1 未回答的问题【未核实】

1. 在 `n_eff=9`、净额 `97.59%` 由 1 笔决定的条件下，**是否存在可判定的方向性优势**？现有样本不能回答（§5.3）。
2. 块长敏感性：改用「同 symbol 同 UTC 周」「同 UTC 日跨 symbol」等不同块长，`n_eff` 与 Wilson 区间是否稳定？（`NOT_RUN`，§5.3、§9.4②）
3. 若剔除第 ⑨ 笔，`exit_mode` 分支在其余 10 笔上的反事实路径如何？（§8.3 第 5 项）
4. `regime_shadow + conservative + 10s` 相对文档声明的 `highest_win + aggressive + 5s` 在决策链各闸门上的差异幅度？（§8.3 第 7 项，§1.6）
5. 行情 regime 分层：窗口内是否存在可独立标注的 regime 变量，能解释 `NEARUSDT` 右尾？（§8.4 E6）
6. 5 条硬检查第 ⑤ 条的 must-fail 反向断言夹具：`PASS/FAIL/INCONCLUSIVE/NOT_RUN` 夹具未运行（`NOT_RUN`，§9.4⑤）。
7. EigenFlux 数据缺口 5 项（§9.5）：11-08 工作区日记、窗口内成本入账原文、窗口内止损零边际新发原文、我方新广播、中文全文。

### 11.2 下一步（研究复核动作，非投资建议）

- **可复核性**：按 §10.2 重放 28 行事件流，独立复算 §4 五张桥与 §10.1 四臂对账；任一桥不等于 `33.762404` 即视为本报告口径错误。
- **补 `NOT_RUN`**：实现块长敏感性 / 块 bootstrap；运行 ⑤ 的 must-fail 反向断言与四态夹具，并在报告中以四态互斥方式登记结果。
- **补对照回放**：在**同一入场集**上，仅切换 `exit_mode`（legacy ↔ trend_capture）并排除第 ⑨ 笔，检验 §7 的"机制优劣"线索是否仍成立；同步做 `regime_shadow` 与 `highest_win` 配置对照，量化 §1.6 漂移的影响。
- **补样本**：在达到 `$DOC/CODEBUDDY.md:441` 的样本门槛、且 ≥2 独立域指标收敛之前，不把 §8.2 任一【线索】升级为结论。
- **证据卫生**：EigenFlux 材料继续只作检验清单来源（L219）；任何网络主张不得进入 §8.1 事实层；窗口内 20 条私信条目维持【非独立】标注。

### 11.3 自审勘误与存疑（显式留痕，参照模板的勘误写法）

| # | 项 | 处置 |
|---:|---|---|
| 1 | 逐笔表 11 个 `net_pnl_full` 显示到 6 位小数，显示值之和 `33.762403`，精确值之和 `33.762403895614` | **已修正标注**：§3 表下注显式说明差 `≈1e-6` 为舍入，合计栏指精确值；§10.1 用未舍入值对账 |
| 2 | 事件文件按 **UTC 日**切分，北京时间 11-02 的第 ①② 笔落在 `2026-11-01/paper_trades.jsonl`；第 ⑩ 笔跨北京日但两端同属 UTC 11-06 | **已显式标注**（§1.2、§3），避免按北京时间找错文件 |
| 3 | 「`fee` 合计 `7.333288`」易被误读为仅出场成本；实际是**全部 28 行事件**（含 11 开仓）的 `fee` 求和；仅出场事件为 `3.661875`（合计 `7.323750` = `exit_cost`） | **已显式区分**（§6.2），二者不可混用 |
| 4 | `Σ\|x_i\|`（HHI 分母）初稿误写 `57.863841`，复核为 `56.961841` | **已修正**（§5.1）；`HHI=0.3915` 不受影响 |
| 5 | 曾有 subagent 报告「`runtime.out.12.log` 不在工作区」 | **以主控与本次复核为准**：文件存在且 L1-L2 已 `head` 复读（§1.1、§1.6 勘误式说明） |
| 6 | EigenFlux `136 唯一 msg_id / 76 会话`（C 路核实）vs 本报告按字段名粗提 `135 / 75` | **存疑，不覆盖**：差 1 源于字段名启发式（可能漏计某类 `id` 键或某文件）；报告正文采用 C 路数值并标注「本报告未独立复算」（§9.5），此项留待复核 |
| 7 | 5 条硬检查 ② 的块长敏感性、⑤ 的 must-fail 夹具 | **未运行，记 `NOT_RUN`**（§5.3、§9.4），不以 `PASS` 默认绿代替 |
| 8 | 全部推论（§8.2）、备择解释（§8.4）与网络材料（§9） | **均未升级为结论**：§8.0 门槛已声明、§9.1 L219 已引用；未核实项集中列于 §8.3、§9.5、§11.1，未抹平 |

---

⚠️ 以上内容由 AI 基于项目内部日志与公开信息整理生成，仅供研究复核，不构成任何投资建议。
