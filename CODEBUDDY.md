# CODEBUDDY.md — AI300 项目指南

> **行号约定**：本文所有 `路径:行号` 均**相对仓库根 `D:/AIDCA/AI300-fwdlib/`**，行号为 2026-11-08 工作树实测值。代码一改行号就漂，定位请以符号名为准：`grep -n "def <symbol>" <路径>`。
> **证据分级**（存疑处必须标）：【代码事实】【配置声明】【日志实跑】【未能确认】。**配置声明 ≠ 生效机制**；**日志现象 ≠ 代码结论**。

_最后重生成：2026-11-08，分支 `20261031-v2`，HEAD `73388a5`；工作树含未提交改动，见 §2.4。_

**改代码前 5 条铁律**（每条一句话，展开见对应节）：

1. **实跑 ≠ systemd 声明**：当前实跑是 `regime_shadow`/conservative/10s/14，systemd 写的是 `highest_win`/aggressive/5s → §2。
2. **PnL 只认 `net_pnl_full`**：`net_pnl` 是 close-only（少一笔建仓成本），`margin_pnl` deprecated（杠杆双计）→ §18.1。
3. **账本成本是常数假设 5+5bps**（`PT:14-15`），不分 maker/taker，与 fwdlib 的 `maker_6/hybrid_10/taker_20` 不同口径 → §18.1。
4. **别在死代码里"修 bug"**：`EC:232-259` 是缺两条闸门的副本，`src/risk/*` 多数未接线 → §13.2、§17.4。
5. **`stop_pct` 入场/出场必须同源**：四处 clamp 并存，只改一侧会让仓位与止损对不上 → §16.3。

## 1. 这个仓库是什么

AI300 是面向 Binance USDT 永续（市值前 20）的多周期趋势交易系统，运行时是 **dry-run / paper only**：主循环 `scripts/run_live_dry_run.py` 拉真实公开行情、走完整决策链、写订单草稿，但**永不提交真实订单**：`orders_submitted = 0` 在进程启动时初始化（`run_live_dry_run.py:118`）、全程无自增，且**不存在交易所下单客户端**（`exchange_mutation_enabled=False`，`run_live_dry_run.py:3025`）——该值只被写进日志与 summary（`:407-444`）。

仓库有三层内容，别混为一谈：

| 层 | 位置 | 性质 |
|---|---|---|
| 在线 dry-run 回路 | `scripts/run_live_dry_run.py` + `src/` | 唯一"在跑"的部分；决策链、四象限、闸门、纸面账本、审计 JSONL |
| 离线研究层 | `scripts/analysis/`（`fwdlib` 前向标注 + 一批 log-only 审计脚本）、`src/backtest/` | 只读日志/公开 K 线，不碰运行时状态 |
| 文档体系 | `REASONIX.md`（中文权威 prose）、`docs/00..20_*.md`（编号规格）、两份 2026-10-31 评审、2026-11-08 归因报告与策略评审稿 | 规格与裁决来源；与代码的已知漂移见 §20 |

权威 prose 先读 `REASONIX.md`（52 行，短，但其中"aggressive tier"与"fib_pa_v1"两处属**声明口径**，与实跑不符，见 §2）。策略数字的一手底座是 2026-11-08 的两份新文档：`docs/analysis/2026-10-31_to_11-08_loss_attribution.md`（已封版）与 `docs/AI300_策略指标因子与决策逻辑_评审稿_20261108.md`。P0 口径契约来自 `docs/2026-10-31-评审回应与落地计划.md`；外部评审为 `docs/2026-10-31-paper-run-review-and-recommendations.md`。

## 2. 运行现状（声明 vs 实跑）——先读这一节

### 2.1 四套口径并列，互不相同，且**尚未裁决**

| 口径来源 | config | `target_tier` | `post_close_delay` | symbols | 证据 |
|---|---|---|---|---|---|
| systemd 单元（2 份） | `entry_chain.dry_run_highest_win.json` | `aggressive` | 5s | 未传 `--symbols` | `deploy/systemd/ai300-dry-run.service:10`、`deploy/systemd/aibot.service:10` |
| `REASONIX.md` | `entry_chain.dry_run_fib_pa_v1.json` | `aggressive` | 5s | 未传 | `REASONIX.md:3`、`REASONIX.md:15` |
| 影子启动脚本默认 | `entry_chain.dry_run_regime_shadow.json` | **不传** → 走 CLI 默认 `conservative`（`run_live_dry_run.py:462`） | 10s（`run_shadow_regime.sh:74`） | **默认传 13 个**（`run_shadow_regime.sh:43,85-86`） | `scripts/run_shadow_regime.sh` |
| **2026-10-31 实跑** | `configs/entry_chain.dry_run_regime_shadow.json` | `conservative` | `10.00s` | `14`，`source=market_cap_rank rank=3-25` | `logs/2026-10/2026-10-31/runtime.out.12.log:L1-L5`【日志实跑】 |

**四套口径只以启动日志 `logs/2026-10/2026-10-31/runtime.out.12.log` 为唯一事实基线，其余三套均为声明口径。**

【日志实跑】重启时点 `2026-10-31 12:02:35 UTC`（北京 20:02:35），`kline_align=ON, tf=900s`、`target_tier=conservative`、`log_root=/root/AIBOT/logs`（`runtime.out.12.log:L1-L2`）。**此后至 11-08 无新 `process_start`**：`logs/2026-11/*/runtime.out.*.log` 全量检索命中 0 行（本次复核）。

【推论，非结论】该次启动**既不是**两个 systemd 单元（配置/tier/延迟三处都不符），**也不是** `run_shadow_regime.sh`（该脚本会传 `--symbols`，日志应显示 `source=cli`，但日志 L3 是 `source=market_cap_rank`）。即实跑来自第三种调用方式，其启动命令**未能确认**。三套口径谁"应该"是生产，仓库内没有裁决记录。

**`target_tier` 不参与任何判定**，只写 `model_version`（`run_live_dry_run.py:198`）、summary（`run_live_dry_run.py:119`）与启动日志（`run_live_dry_run.py:3043`）。它出现在日志里不代表任何门槛被切换。

### 2.2 实跑 symbols 的成员与配置不一致

【日志实跑】预热列表 14 个：`BNB/XRP/SOL/TRX/ZEC/HYPE/DOGE/XMR/LINK/ADA/XLM/BCH/NEAR/UNI`（`runtime.out.12.log:L4`）。
【配置声明】`regime_shadow` 的 `dry_run_symbols` 也是 14 个但成员不同：含 `CC/LAB/TON`、无 `BCH/NEAR/UNI`（`configs/entry_chain.dry_run_regime_shadow.json:55-70`）。
**成因【未能确认】**：日志 L3 标 `source=market_cap_rank`，与 `resolve_runtime_symbols` 的 `market_cap_rank` 分支一致（`run_live_dry_run.py:2307-2318`），该分支用 CoinGecko 实时排名（rank 3-25）而非配置列表。两处都是 14 个，但**不是同一份清单**。

### 2.3 CLI `--symbols` 会覆盖配置

`if args.symbols: return resolve_symbols(args.symbols, ())`（`run_live_dry_run.py:2300-2303`）——`--symbols` 一旦传入，`config.dry_run_symbols` 被完全忽略。`run_shadow_regime.sh:85-86` 默认就传，所以脚本的默认 `SYMBOLS`（13 个）**覆盖**配置里的 14 个。这是脚本级事实，不是"跟随配置"。

另注意 `run_shadow_regime.sh` 的注释与实际默认值不一致：`:42` 点名"与 highest_win 的 13 个一致"，`:44` 又提 fib_pa_v1 的 14 个，而默认 `CFG=regime_shadow`（`:47`，研究配置，14 个含 LABUSDT）、默认 `SYMBOLS` 只有 13 个且不含 LABUSDT。想按配置跑，必须显式传 `SYMBOLS=""`（`${SYMBOLS-…}` 形式允许空串，`:43`）。

### 2.4 工作树未提交改动（本次重生成时）

- 已修改：`CODEBUDDY.md`、`configs/entry_chain.dry_run_fib_pa_v1.json`、`scripts/run_live_dry_run.py`、`scripts/vps_dry_run_healthcheck.py`、`tests/test_dry_run_configs.py`、`tests/test_entry_chain_config.py`、`tests/test_live_dry_run.py`
- 已删除：`configs/entry_chain.dry_run.json`（HEAD 仍在，见 §4.3）
- 未跟踪：`configs/entry_chain.dry_run - 副本.json`、`configs/trading_config_fund_flow.json`、`docs/2026-10-20-restructuring-plan-v2-review.md`、`docs/2026-10-31-paper-run-review-and-recommendations.md`、`docs/AI300_策略指标因子与决策逻辑_评审稿_20261108.md`、`docs/analysis/2026-10-31_to_11-08_loss_attribution.md`、`logs_parallel/`

**引用任何行号前先确认自己在 HEAD 还是工作树**：`run_live_dry_run.py` 等文件有未提交改动。本节只是 2026-11-08 的工作树快照，**勿作长期事实引用**；重生成时按文末 checklist 逐项刷新。

## 3. 命令（每条可直接复制）

```bash
# 环境：系统 python 是 3.13 且无 pytest，必须用仓库 venv（Linux 把 Scripts 换成 bin）
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt
# requirements.txt 只有 requests/urllib3 + pytest>=8,<9；numpy/pandas 不在里面（见 §22）

# 全量测试（2026-11-08 实测：1 failed, 870 passed；耗时 ≈50s，随机器波动，复核区间 46.06s–56.04s）
.venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/test_verify_five_factor_orthogonality.py
# 单文件 / 单用例
.venv/Scripts/python.exe -m pytest tests/test_entry_chain_scoring.py -q
.venv/Scripts/python.exe -m pytest tests/test_fwdlib_labeler_parity.py::test_cost_bps_shifts_r_net_only -q

# 离线单周期 smoke（无网络，~3s，实测输出 {"status": "dry_run_completed", "orders_submitted": 0}）
.venv/Scripts/python.exe scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json \
  --target-tier aggressive --market-data-source synthetic --once --log-root logs/_smoke

# VPS 式调用 —— A. systemd 声明口径（不是当前实跑）
.venv/Scripts/python.exe scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_highest_win.json \
  --target-tier aggressive --market-data-source public-binance --log-root logs \
  --align-to-kline-close --post-close-delay-seconds 5
# VPS 式调用 —— B. 2026-10-31 实跑口径（无 --symbols，symbols 走 market_cap_rank）
.venv/Scripts/python.exe scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_regime_shadow.json \
  --market-data-source public-binance --log-root logs \
  --align-to-kline-close --post-close-delay-seconds 10

# 回测（与 dry-run 共用决策链；先下数据）
.venv/Scripts/python.exe scripts/download_latest_30d_market_data.py
.venv/Scripts/python.exe scripts/run_offline_backtest.py --strategy entry-chain \
  --entry-chain-config configs/entry_chain.dry_run_fib_pa_v12.json --exit-model atr_tp

# fwdlib 前向标注 v2（研究线；FWD_LOGS / FWD_REPORTS 可覆盖根目录）
.venv/Scripts/python.exe scripts/analysis/fwd_label_v2_20261019.py --logs logs \
  --months 2026-09,2026-10 --out reports/analysis/fwd-label-v2-20261019

# 账本 / 退出臂校验（log-only，随时可跑）
.venv/Scripts/python.exe scripts/analysis/ledger_reconcile_20261031.py --selftest   # Σ net_pnl_full == 账本 realized
.venv/Scripts/python.exe scripts/analysis/verify_pure_ladder_arm.py                # pure_ladder 四断言

# 部署后体检
.venv/Scripts/python.exe scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run_regime_shadow.json
.venv/Scripts/python.exe scripts/verify_q1_trend_launch_fix.py --mode online --log-root logs --hours 24
.venv/Scripts/python.exe scripts/recommendation_tracker.py check    # 退出码 1 = 有未解决 P0
.venv/Scripts/python.exe scripts/audit_duplicate_json_keys.py <config.json>
```

**`--config` 默认值**已改为 conservative：`run_live_dry_run.py:451`、`scripts/vps_dry_run_healthcheck.py:49`。conservative 只有 11 个顶层键、且无 `dry_run_symbols`，所以**不带 `--symbols` 跑 public-binance 只会跑 `BNBUSDT`**（`resolve_symbols` 空列表回退，`run_live_dry_run.py:2335`）。synthetic 分支同理（`:2304-2306`）。

## 4. 配置体制（四套策略配置 + CLI 默认，不可混用）

### 4.1 主用配置（4 套策略配置 + conservative 作 CLI 默认）

| 配置 | 架构 | 关键差异 | 用途 |
|---|---|---|---|
| `entry_chain.dry_run_regime_shadow.json` | `use_ema=true` + `use_fib_pa=true`（短路后走 fib_pa，`entry_chain_scoring.py:56-58`） | 与 `fib_pa_v1` **完全等价**；`regime_overlay: "shadow"`、`score_core: "s1_shadow"`（`:247-248`，只记录） | 2026-10-31 实跑用的就是它 |
| `entry_chain.dry_run_fib_pa_v1.json` | 同上 | 研究基线；probe 开启、暴露预算更宽（相对 highest_win：`max_total_exposure_pct` 1.6 vs 1.2、`max_active_symbols` 8 vs 5） | 研究 / 回测 |
| `entry_chain.dry_run_fib_pa_v12.json` | 同上 | `v12 = v1 + paper_ab_pure_ladder_enabled:true − {regime_overlay, score_core}` | 研究（含第三臂） |
| `entry_chain.dry_run_highest_win.json` | `use_ema=true`、`use_fib_pa` 默认 false、`disable_probe: true`、`enable_long_context_discounts: true` | 40 个顶层键；无 `probe_conditions` / `scout_micro_*` / `mirror_ab_*` | **systemd 声明口径**（不是实跑口径） |
| `entry_chain.dry_run_conservative.json` | 两个架构开关都默认 false → BASE 三档权重 | 11 个顶层键（旧格式）：`direct 86 / probe 74 / watch 62` | CLI 默认值 |

**等价性复核（2026-11-08，展开 186 键、键集合相同、0 值差）**：`regime_shadow` ≡ `fib_pa_v1`。**v12 复核**：185 键，相对 v1 只删 `regime_overlay`/`score_core`、只加 `paper_ab_pure_ladder_enabled`，其余 0 值差。

`configs/` 下还有 `aggressive/balanced/ema_hard/ema_soft/no_rsi/risk_first/s1_shadow/v4_*/v5_*` 等试验配置，**不被任何 unit 或脚本引用**，别当生效配置读。

### 4.2 改配置的硬约束

- 任何配置改动都要同步 `tests/test_dry_run_configs.py`（tier 顺序、每配置不变量）。那里红了是**设计上的绊线**，不是障碍。
- 改 `src/signals/entry_chain_config.py` 的默认值会**同时**改变所有未显式覆盖该键的配置——包括 conservative 与 highest_win。
- `from_mapping` 拒绝未知键（`entry_chain_config.py:253-258`）；`entry_gates` 只接受 list[dict]（`:285-292`）。

### 4.3 已退役与易误读的文件

- `configs/entry_chain.dry_run.json`：**已退役**。工作树 `D`、HEAD 仍在；本次复核 `git show HEAD:…` 与 `conservative` **完全相等**（11 键，0 值差）。CLI 默认与其等价，故退役是零行为变更。
- `configs/entry_chain.dry_run - 副本.json`：未跟踪备份，与 `conservative` **完全相等**（11 键）。**不是生效配置**，不要拿它当基线引用。
- v12 **不是**退役配置的替代品：v12 在合成 BNBUSDT 上评 59.2（`NO_TRADE`），conservative 到 75.7（`PROBE`）；v12 的 `scout_micro_exit_mode` 是 `trend_capture`，conservative 是 `legacy`。

## 5. 架构分层

### 5.1 分层契约

`src/core/module_spec.py` 冻结 14 层与各层职责（`:8-40`）：`config, data, indicators, context, signals, state_machine, risk, execution, portfolio, backtest, reporting, observability, deployment, utils`。依赖链单向（`:41-53`），跨层穿透、循环依赖、上帝工具类被显式禁止（`:24`）；`execution` 不得调 `signals`、`risk` 不得调 `backtest`（`:141-144`）。`validate_module_structure` 只检查目录是否存在（`:156-161`）——**它不校验真实 import**，别把它当架构守卫。

### 5.2 缩写表（行数为 2026-11-08 实测）

| 缩写 | 文件 | 行数 | 职责 |
|---|---|---|---|
| `EC` | `src/signals/entry_chain.py` | 825 | 决策链主体 `evaluate_entry_chain` |
| `ECS` | `src/signals/entry_chain_scoring.py` | 90 | 三套权重 + 分量点数 |
| `FEAT` | `src/signals/entry_chain_features.py` | 378 | 真实特征计算（**不存在 `src/signals/features.py`**） |
| `GATES` | `src/signals/entry_chain_gates.py` | 98 | **15 个硬闸门** + 每日预算 + 敞口上限映射 |
| `EG` | `src/signals/entry_gate.py` | 169 | **声明式** `EntryGate`/`GateRule`/`build_gate_features`（不是硬闸门） |
| `CFG` | `src/signals/entry_chain_config.py` | 352 | 冻结 dataclass + `from_mapping` + 加载器 |
| `PT` | `src/observability/paper_trading.py` | 905 | 纸面账本、出场生命周期、PnL v2 字段 |
| `RUN` | `scripts/run_live_dry_run.py` | 3251 | 主循环、通道、实验账本、审计写入 |
| `LEA` | `src/execution/live_entry_chain_adapter.py` | 97 | 决策 → 订单草稿 |
| `LCE` | `src/backtest/lifecycle_exit.py` | 248 | 回测用 ATR/TP 退出模拟器 |
| `ENG` | `src/backtest/engine.py` | 980 | 回测引擎（与 dry-run 同构） |
| `NBE` | `src/risk/net_beta_exposure_model.py` | 69 | 净 beta（**只观测**） |
| `SS` | `src/risk/stress_simulator.py` | 24 | 压力损失（**只观测**） |
| `RE` | `src/risk/risk_engine.py` | 557 | **spec only，未接线** |

**锚点纪律**：旧稿自述的"RUN 后半段偏移 +70~+110"已不可靠（该文件已 3251 行，且带未提交改动）。一律按符号名 grep 定位，不信任何转述的行号——包括本文的：本文给的行号只保证"2026-11-08 工作树"这一刻成立。

## 6. 在线 dry-run 主循环

一个周期（`run_live_dry_run.py:137-413`）按序：

1. 周期级重置 `data_health="OK"`（`:141`）→ 等 K 线对齐（`:142`）→ 跨日则重建 `DecisionAuditWriter` 与三/四本账本（`:147-163`）
2. 逐 symbol：`build_context`（`:182`）→ 注入纸面组合状态（`:183`）→ `apply_dry_run_decision_controls(evaluate_entry_chain(...))`（`:187-192`）
3. 组装 `decision_payload`（`:195-220`，含 `score_detail`、`entry_context`、`component_points_v2`、`s1_core`、`regime_overlay`）→ 象限标注（`:221`）→ near-miss（`:222`）
4. Q3→Q1 / Q2→Q1 pending 确认链（`:229-245`）→ Q1 通道覆盖决策（`:256-263`，命中则整条替换并重新走 controls）
5. 实验象限入场规则（`:299-303`）→ **声明式闸门**（`:304-311`）→ `regime_overlay` 组合层仓位上限（`:312-326`）
6. 写审计：`audit.write_decision`（`:327`）、`write_near_miss`（`:330`）→ 压力观测（`:332-339`）→ 订单草稿（`:341-352`）→ 归因行（`:353-354`）
7. 主账本 `paper.on_decision`（`:355`）→ A/B 臂（`:362-369`）→ mirror（`:370`）→ scout（`:378`）
8. 周期末：runtime 日志（`:409`）、health（`:410`）、组合快照（`:411`）、pending 状态（`:412-413`）、A/B 自动报告（`:414-420`）、summary（`:435`）、`paper_summary.json`（`:436`）

**审计只有单一入口**：`src/observability/decision_audit.py::DecisionAuditWriter` 是 `decisions.jsonl` / `order_drafts.jsonl` / `attribution.jsonl` / `near_misses.jsonl` / `scout_decisions.jsonl` / `gate_rejections.jsonl` / `gate_rejections.csv` 的唯一写者（`decision_audit.py:16-22`）。别在别处 append 这些文件。

**日志布局**：`<log_root>/<YYYY-MM>/<YYYY-MM-DD>/` 下放日切 JSONL + `paper_*` + `runtime.out.HH.log`（6h 一段）；账本状态在 `<log_root>/../state/paper/`（`run_live_dry_run.py:2297`），含主账本、`scout_micro/`、`paper_ab/{legacy,trend_capture[,pure_ladder]}/`、`quadrant_pending.json`。第三臂只在 `paper_ab_pure_ladder_enabled` 为真时存在（`run_live_dry_run.py:630-637`）。

**回测同构**：`ENG` 复用同一决策链与同一 `TP_LEVELS/TP_FRACTIONS` 常量族，`BacktestBar.taker_buy_volume` 来自 klines 第 10 列（`run_live_dry_run.py:2648`），是 F5 真实订单流的唯一入口；协议常量在 `src/backtest/protocol.py`。

## 7. 五因子影子契约（动 signals 前必读）

`src/signals/orthogonal_factors.py`（493 行，F1–F5：`trend_persistence` / `structure_location` / `payoff_geometry` / `volatility_regime` / `order_flow`）是 **shadow-only**：

- 只由 `RUN::attach_five_factor_shadow`（`run_live_dry_run.py:2654-2679`）写入 `decisions.jsonl` 的 `component_points_v2` + `component_points_v2_meta`；
- **不得**影响 `total_score` / `component_points` / 象限 / 通道门槛 / 杠杆 / `action`；
- 由 `tests/test_five_factor_shadow_readonly.py` 用**源码级断言**守护（决策层文件清单 `entry_chain.py` / `entry_chain_scoring.py` / `entry_chain_gates.py`，`:26-30`）；
- 回滚开关：`five_factor_shadow_enabled: false`（`entry_chain_config.py:237`，默认 true）；
- 影子计算抛异常只写错误标记、不冒泡（`run_live_dry_run.py:2670-2677`）。

**唯一读取点**：`shadow_total → build_gate_features.shadow_pct`（`run_live_dry_run.py:1161`；`entry_gate.py:148-149`）。而 `apply_entry_gates` 在 `entry_gates` 为空时**立即返回**（`run_live_dry_run.py:1154-1155`），四套配置均无 `entry_gates` 键 → 影子分当前**零行为影响**。若有人真配了 `entry_gates`，影子分就会变成闸门特征；这需要显式决策记录。

**红线**：不要为了提高 F4 波动率窗口去调大 `--public-kline-limit`——会增加 15m 历史、移动 EMA200、改变旧评分（`REASONIX.md:49`）。

## 8. 研究层 fwdlib（`scripts/analysis/fwdlib/`）

把"这条决策后来赚钱了吗"从一次性脚本里抽出来：`config.py`（冻结 `LabelConfig` + `fingerprint()`，用于结果目录）、`labeler.py`（`build_bars`/`resolve_stop`/`label_barrier`/`label_ladder`/`label_at_horizons`/`run_labeling`/`timeout_profile`，要求与旧脚本**逐位一致**，含浮点运算顺序）、`cost.py`（`maker_6`/`hybrid_10`/`taker_20`、`cost_r(bps, stop_pct)`）、`baseline.py`（逐决策**配对安慰剂** + `lift_summary` 块 bootstrap）、`stats.py`（Spearman/偏 Spearman、块 bootstrap、MDE/有效 n、BH 校正、`TestLedger` 拒绝 NaN/Inf）、`ledger.py`（`paper_trades.jsonl` 的 FIFO 归因）、`features.py`（决策日志加载，`profile="six_factor"` 有语义差异）。

三个会咬人的点：

- **双导入路径**：先试 `from fwdlib…`（`python scripts/analysis/x.py` 可用），失败回退 `from scripts.analysis.fwdlib…`；测试一律用后者。
- **参数优先级**：`labeler._pick`（`labeler.py:79-83`）把"值等于旧默认"当成"调用方没覆盖"，于是 `cfg` 生效。**显式传一个恰好等于旧默认的数不会覆盖配置**。
- **shim 陷阱**：`scripts/analysis/fwd_label_20261019.py` 是薄壳（仍有 7 个下游脚本用）。它在调用时读自己的 `ROUND_TRIP_BPS`；直接 `import` 那个名字会静默按 20bps 标注全部样本。

## 9. log-only 审计脚本

这一族只读 `logs/`、写报告，不触运行时状态、不下单，可反复重跑。**引用其数字前先学会它编码的那个陷阱**：

| 脚本 | 回答什么问题 | 它编码的陷阱 / 范围 |
|---|---|---|
| `pnl_review_20261031.py` | 6 日 PnL、成本分解、MFE/capture、止损宽度分布 | 范围仅 `logs/2026-10B/2026-10-26..31`；**排除 `01/`**（10-26 的整份副本，会双计）与 `02/2026-10-26/regime`（独立 regime 实验） |
| `funnel_recount_20261031.py` | 从原始 JSONL 重算决策/拒单/near-miss | `summary.json` 的 `decision_counts`、`gate_rejections_by_layer`、`near_miss_count` 是**进程启动以来累计**并写进每个日切片；跨天相加会乘切片数（这就是 5,850 变 20,475、190 变 602 的来路） |
| `ledger_reconcile_20261031.py` | `Σ net_pnl_full` vs 账本 `realized_notional_pnl`，逐账本 | `net_pnl` 不含建仓成本，close-only 行永远对不上；`--selftest` 造一笔开→平并断言恒等式 |
| `s2_gate_audit_20261031.py` | 同一入场集上 `legacy` vs `trend_capture` 的配对符号检验 + 闸门反选检验 | 配对净差 + exact binomial + 块 bootstrap（块 = `symbol\|utc_date`）；大比例配对**完全相同** → 不是决策级证据 |
| `factorial_exit_replay_20261031.py` | 固定入场、重放出场：2×3×2 析因（`stop_floor` × `be_trigger` × `bar_rule`） | 第三个旋钮**只改同根 K 线冲突仲裁**；抬升后的止损在**下一根**生效；`stop_first` 与账本约定一致 |
| `nearmiss_counterfactual_20261031.py` | 被闸门拒掉的信号按账本规则会怎样（同止损、3 档 TP、32 根上限、20bps 往返 = `(FEE_BPS+SLIPPAGE_BPS)×2`，`nearmiss_counterfactual_20261031.py:33`） | `near_misses.jsonl` **按日轮转**，覆盖是 190/190，不是 190/602 |
| `verify_pure_ladder_arm.py` | 第三臂的四条断言 | 配置可载入、三本账、`defensive_overlay` 门控、同序列与 legacy 对照 |

**10-31 之后到 11-08 没有新增审计脚本**（`scripts/analysis/` 内文件未增；未跟踪项为文档与配置、无脚本：4 份文档 + 2 个配置 JSON + `logs_parallel/`）。这段时间新增的是文档：归因报告与 11-08 策略评审稿。所以"脚本里没有某结论"不等于"没人算过"，也可能只写在文档里。

## 10. spec-as-code 与配置加载

每份编号规格有一个机器可读孪生体：`src/**/*_spec.py`（如 `src/indicators/indicator_spec.py`）+ `scripts/describe_*.py`（打印 JSON）+ `tests/test_describe_*.py`（断言文档契约）。改一个 spec 常量要同时改**spec 模块、文档、测试**三处。

- **运行时配置是 JSON**：`configs/entry_chain.*.json` 由 `load_entry_chain_config`（`entry_chain_config.py:296-300`）读入冻结 dataclass；未知键直接 `ValueError`（`:253-258`）。
- **`configs/*.yaml` 是 schema 期遗留**：只被 `src/config/config_schema.py` 与 `tests/test_config_schema.py` 校验，运行时无人加载。
- **没有策略常量的 CLI 覆盖**：`--target-tier` 不参与判定（§2.1），`--symbols` 只覆盖标的清单（§2.3）。想改阈值只能改配置或改 dataclass 默认。
- **`regime_overlay` / `score_core` 的 `ValueError` 属时点差异【未能确认】**：`backups`/`errors.log` 记录重启前报 `unknown entry-chain config keys: ['regime_overlay','score_core']`，但当前工作树已把二者定义为字段（`entry_chain_config.py:246,251`）、配置也含这两个键，所以**当前状态下无法复现**该报错。别据此推断当前代码会拒绝它们。

## 11. 策略流水线一览（数据 → 订单草稿）

| # | 阶段 | 函数 / 产物（位置） |
|---|---|---|
| 1 | 上下文 + 辅助特征 | 每 TF 240 根已收盘 K 线、`atr_pct`、`quote_volume_24h`、`extreme_position_ratio`、wick/过extend/追单标志（`RUN:2533-2752`；`FEAT:296-378`） |
| 2 | 分量 → 权重 → 总分 | 8 个 BASE 键 **或** 6 个 fib_pa 键（`FEAT:35-71`）；`dynamic_weights(atr_pct)` 三分支（`ECS:53-70`）；`points[c]=round(clamp(s,0,1)×w,4)`、`score=round(Σpoints,4)` → 0–100（`EC:92-96`；`ECS:86-90`） |
| 3 | fib 耗尽封顶 | 仅 fib_pa：`fib_action_cap<=0` → `NO_TRADE` `FIB_EXTENSION_EXHAUSTION_BLOCK`（`EC:99-110`） |
| 4 | 硬闸门 | `hard_block_reason`，首个命中即 `NO_TRADE`（`EC:112-114`；`GATES:38-70`） |
| 5 | 动作 + 最低分量 | `_score_to_action` + 侧向偏移；分量最低值降档；`check_probe_conditions`（`EC:116-121,282-296,351-600`） |
| 6 | LONG 风险修正 + 上限 | 过extend/追单/弱 PA/低流动性时段 → 封顶 WATCH（`EC:123-143`）；`liquidity_ratio` 8/20、宏观降级、ws 重连→WATCH、高 beta、+3% 日、`_select_leverage`、`_notional_hint`（`EC:145-191,655-765`） |
| 7 | 控制层 + 订单草稿 | `apply_dry_run_decision_controls` → WATCH；`build_live_entry_order_draft` → 账本 + 审计（`RUN:187,2091`；`LEA:25-81`；`PT:179-196`） |

总分确定之后，每一步**只能保持或降低**动作等级。

## 12. 指标

`src/indicators/indicator_spec.py` 是契约：恰好 6 个指标，硬编码顺序 `("MACD","CCI","BOLL","EMA","CVD","ATR")`（`indicator_spec.py:18`；构建顺序 `indicator_engine.py:59-77`）。

逐项（`indicator_spec.py:19-26`；必需输出键见 `src/data/data_contract.py:74-98`），"指标 参数 → 职责 → 必需键"：

- MACD 12/26/9 → trend_momentum → `macd_line, signal_line, histogram, histogram_slope, cross_state`；CCI 20 → strength_deviation_recovery → `cci, cci_slope, extreme_flag, recovery_flag`
- BOLL 20/2.0 → volatility_structure → `middle_band, upper_band, lower_band, band_width, band_expansion_flag, band_contraction_flag, price_position`；EMA 9/21/50/200（slope 5）→ trend_direction_quality_momentum → `ema_9, ema_21, ema_50, ema_200, ema50_slope, ema9_21_gap, bars_since_ema50_cross, bars_since_ema200_cross`
- CVD（无参）→ active_buy_sell_pressure → `cvd, cvd_delta, cvd_slope, cvd_divergence_flag, buy_pressure, sell_pressure`；ATR 14 → volatility_stop_position_risk → `atr, atr_pct, volatility_state`

**每 TF 启用集**（`indicator_spec.py:68-73`）：`4h` = EMA/MACD/BOLL/CCI；`1h` = EMA/MACD/CCI/CVD；`30m` = EMA/MACD/BOLL/CCI/CVD；`15m` = EMA/MACD/CVD/BOLL。**没有一个 TF 是六指标全开**（4h 无 CVD，15m 无 CCI）。缺任一必需键则 `validate_indicator_result` 失败；`is_closed is not True` 直接拒（`indicator_spec.py:109-110`）；`quality_flag` 允许 `True`/`"degraded"` 用于信号，但**直接入场只接受 `True`**。

**冲突优先级**（`indicator_spec.py:56-67`，别名 `INDICATOR_PRIORITY`）从高到低：`data_quality → cvd_divergence → ema200_direction_gate → macd_trend_direction → ema50_trend_quality → cci_strength → boll_structure → ema9_21_momentum → atr_risk`。

**禁用用法**（`indicator_spec.py:75-88`，`validate_indicator_usage` 强制执行）：MACD/EMA 不得 `sole_entry`；CCI/BOLL/CVD 不得 `sole_direction`；MACD/BOLL/EMA 不得驱动 `position_size`；EMA 不得 `countertrend_direct`；ATR 不产方向。指标层全局禁用：`create_order`、`final_position_size`、`bypass_state_machine`、`must_trade`。

**两条必须知道的实况**：

1. **RSI 不在 6 指标契约内，且未被 live 调用**。`indicator_engine.py:12,41` 会算 RSI 放进内部 snapshot，但 `run_live_dry_run.py` **完全不 import 指标引擎**（全库 grep 仅 `scripts/scaffold_ai300_framework.py` 命中）。live 链的特征全在 `FEAT` 里另算。
2. **CVD 是伪 CVD**：`volume_flow_score` = 6 根 15m K 线的 `direction × volume` 求和，映射到 `1.0 / 0.2 / 0.5`（`FEAT:282-293`），不是 taker 主动买卖量。真实订单流只在回测侧经 `BacktestBar.taker_buy_volume` 进入 F5。

**方向从哪来（硬事实）**：`direction_from_history` 喂的是 `histories["1h"]`（`RUN:2698`）——1h 收盘相对 4 根前的涨跌，阈值 ±0.3%（`FEAT:22-32`）；返回 NONE 时回退 15m 最近 3 根（`RUN:2699-2700`）。`src/context/multi_tf_rules.py` 是 4h/1h/30m/15m 角色+否决规则引擎，但**live 链一句都没引用**（只被 `multi_tf_context.py:3` 引用，而后者也没人用；其余引用是 `scripts/describe_multi_tf_rules.py` 与 scaffold）。真正在跑的是 `agreement_score` 的近似：`clamp(0.5 + ret×50)`（LONG），回看 3/4/6 根（4h/1h/30m，`FEAT:264-270`）。另外 `market_regime` 恒为 `0.8`（`FEAT:52`），BOLL 实际不参与评分。

**方向与入场分两套口径**：`EntryChainContext.stop_pct` 由 live 构造（`RUN:2733`），但 `FEAT.risk_reward_geometry_detail` 内部另有一套 clamp `max(close×0.005, min(close×0.030, atr×1.5))`（`FEAT:170`）与 `TP1_R_MULTIPLIER=1.2`（`FEAT:15`）——这是第三套止损宽度口径，见 §22。

## 13. 入场链：阶段与闸门

### 13.1 `evaluate_entry_chain` 的分支块（`EC:86-205`）

不给"步数"——分支块内部还有子条件，任何"N 步"的说法都会随改动失真。按块读：

| 块 | 行 | 做什么 |
|---|---|---|
| A 预处理 | `EC:91-97` | 取 symbol 敞口上限；`dynamic_weights`；LONG 上下文折扣；`points`；`score`；`liquidity_ratio` |
| B fib 耗尽 | `EC:99-110` | 仅 fib_pa：`fib_action_cap<=0` → `NO_TRADE` |
| C 硬闸门 | `EC:112-114` | `hard_block_reason` 首个命中即 `NO_TRADE` |
| D 分数→动作 | `EC:116-121` | `_score_to_action` → 分量最低值降档 → `disable_probe` |
| E LONG 风险封顶 | `EC:123-139` | 过extend/追单 → WATCH；追单且 PA<12 → WATCH |
| F 低流动性时段 + 宏观/数据健康 | `EC:141-152` | `enable_long_context_discounts` 且 LONG → `_min_action(WATCH)`；日跌幅/USDT 异常：DIRECT→PROBE（**不是**阻断）；ws 重连→WATCH |
| G 流动性 · 高 beta · +3% 日 | `EC:154-178` | `< probe_ratio` → `NO_TRADE`；`< direct_ratio` 且 DIRECT → PROBE（再过 `disable_probe`）；高 beta 下 DIRECT→PROBE、fib_pa 重跑 probe 条件（失败→WATCH）；+3% 日 PROBE→WATCH、DIRECT 且 `score < direct+3` → PROBE |
| H 单标的敞口 | `EC:180-181` | `symbol_exposure_pct >= cap` → `NO_TRADE` |
| I 杠杆 + 仓位 | `EC:183-191` | `_select_leverage` → `_notional_hint` |
| J 组装 | `EC:193-205` | `_decision(...)`，写 `metadata.risk_budget` |

### 13.2 15 个硬闸门（**在 `src/signals/entry_chain_gates.py:38-70`**，不在 `entry_gate.py`）

| # | reason | 条件 | 默认 / 配置 |
|---|---|---|---|
| 1 | `SYMBOL_BLACKLISTED` | symbol ∈ `blacklist_symbols` | 类默认空；两套主配置 `XRPUSDT/ZECUSDT`（`regime_shadow.json:71`、`highest_win.json:25`） |
| 2 | `SYMBOL_WATCH_ONLY` | symbol ∈ `watch_only_symbols` | 两套主配置 `ADAUSDT/XMRUSDT` |
| 3 | `MACRO_WEEKLY_RISK` | `macro_weekly_drop_pct <= -0.15` | `CFG:41` |
| 4 | `DATA_WICK_ANOMALY` | `wick_anomaly_active`（高低比>1.05 且量<前根 0.5×，`FEAT:373-378`） | — |
| 5 | `DATA_POLLUTION_COOLDOWN` | `timestamp <= polluted_until_ts` | — |
| 6 | `SYMBOL_POSITION_ALREADY_OPEN` | symbol ∈ `active_symbol_names` | — |
| 7 | `MAX_ACTIVE_SYMBOLS` | `active_symbols >= max_active_symbols` | 5 / **8**（fib_pa 系） |
| 8 | `DAILY_TRADE_BUDGET_USED` | `portfolio_trades_today >= daily_max_trades` | `4×vol_ratio`，地板 1 / **16，地板 2** |
| 9 | `SYMBOL_DAILY_TRADE_BUDGET_USED` | `symbol_trades_today >= max_symbol_trades_per_day` | 1 / **2** |
| 10 | `SYMBOL_COOLDOWN_ACTIVE` | `timestamp < cooldown_until_ts` | — |
| 11 | `TOTAL_EXPOSURE_CAP` | `total_exposure_pct >= max_total_exposure_pct` | 1.50 / **1.6** / **1.2** |
| 12 | `SAME_DIRECTION_EXPOSURE_CAP` | `same_direction_exposure_pct >= max_same_direction_exposure_pct` | 1.20 / **1.1** / **0.9** |
| 13 | `MARGIN_BUFFER_TOO_LOW` | `available_margin < equity × margin_buffer_pct` | 0.20 / **0.30**（两套主配置） |
| 14 | `ACCOUNT_EQUITY_INVALID` | `account_equity <= 0` | — |
| 15 | `SIDE_NOT_ALLOWED` | side ∉ {LONG, SHORT} | — |

**每日预算公式**：`max(min_daily_trades, floor(daily_max_trades_base × current_vol/normal_vol))`，+3% 日后**再减半**（`GATES:73-79`）。

**不要改重复死实现**：`EC:232-259` 有一份本地 `_hard_block_reason`，**缺黑名单与 watch_only 两条**；`EC:212-222`（`_rescale_weights`）、`EC:225-229`（`_component_points`）、`EC:603-608`（`_liquidity_ratio`）、`EC:611-618`（`_symbol_exposure_cap`）全是无调用的死副本。`evaluate_entry_chain` 调用的是 `GATES`/`ECS` 版本（`EC:91-97,112`）。在 EC 副本里"修 bug"不会有任何效果，而且那份闸门清单本身是错的。

## 14. 通道

| 通道 | 资格 | 仓位/杠杆 | 位置 |
|---|---|---|---|
| `q1_green_channel` | **与 trend_launch 同实现**，无条件委托 | 完全取 `dry_run_q1_trend_launch_*` | `RUN:1055-1064` |
| `q1_trend_launch` | 数据健康 OK（或允许降级）、symbol 不在黑名单/watch_only/observation_only、象限 Q1、`intended_side` 合法、`entry_price>0`、`0.20<=extreme_ratio<=0.80`、LONG 三重风险标志全清、`score>=82`、PA>=18、fib>=15、CVD>=16、RR>=0.5 | `exposure_pct = 0.025 × clamp(rr/8, 0.25, 1.0)`；`equity × exposure_pct` 再与 `_notional_cap_diagnostics` 取 min；**杠杆硬 1** | `RUN:1085-1135`；sizing `RUN:957-971,1002` |
| `q2_pending` | 源象限 Q2、`score>=70`、PA>=18；有效 6×900s；确认需翻到 Q1 且 CCI>=9 | scout 名义 50（高 beta 减半） | `RUN:1637-1657`；确认 `RUN:1691-1719` |
| `q3_to_q1` | 源象限 Q3、`score>=85`、CVD>=16；有效 3×900s；确认需翻到 Q1 且 PA>=15 | 同上 | `RUN:1614-1634`；确认 `RUN:1660-1688` |
| `reversal_pivot` / `q1_rr_gap` | **默认关闭**（不是死代码）：入口即 `if not config.scout_micro_reversal_pivot_enabled: return False`（`RUN:1399-1401`）/ `if not config.scout_micro_q1_rr_gap_enabled: return False`（`RUN:1584-1586`）；两个开关默认 False（`CFG:159`、`CFG:99`），故判定恒 False；**置 true 后会真正参与判定** | — | `RUN:1399-1401,1584-1586` |
| `SCOUT` | `scout_micro_symbols` 内、near-miss 命中任务条件 | 配置名义（50 / reversal 25），杠杆取 `scout_micro_leverage=1` | `RUN:2039-2088`；payload `RUN:1821-1895` |
| `mirror_ab` | `mirror_ab_enabled` + 分数/理由/象限条件 | `shadow_only`：**记录假设成交、不计入实验熔断、不增加主账本敞口**——`_mirror_ledgers = []`（`RUN:248`）把 mirror 账本排除在 `experiment_entry_circuit_active` 之外，账本仍照写（`RUN:362-369`） | `RUN:1906-1931` |
| `pure_ladder` | 仅 `paper_ab_pure_ladder_enabled` 为真（**只有 v12**） | 第三本 A/B 账本，`defensive_overlay=False` | `RUN:630-637` |

**通道陷阱**——(a) `q1_trend_launch` 的 sizing 是**第二套叠加**：先按 `rr_points` 缩放 `0.025`，再与 `_notional_cap_diagnostics` 取 min，杠杆强制 1。它**不走 `raw_notional` 路径**，所以别用 `_notional_hint` 公式估算它的名义。
(b) 旧稿称 `q2_pending` 用"目标侧价带"、`q1_trend_launch` 用"斐波回撤区"——**【代码事实】已证伪**：`grep "band" scripts/run_live_dry_run.py` 命中 0（全库唯一 `band` 是 `orthogonal_factors.py:349` 的 BOLL 带宽 `band_expansion`，与入场无关）；两个 pending 构造器只落 `symbol/side/created_at/expires_at/source_score/source_quadrant` 六个字段、**无价格字段**（`RUN:1614-1634,1637-1657`）；入场价全部取当根收盘（`RUN:925,340,2053`；`PT:209`）。

## 15. 评分、阈值与权重

### 15.1 三套架构共存（两个开关决定跑哪套）

`use_ema_architecture` / `use_fib_pa_architecture` 选**评分架构**；`ema200_gate_mode` 只决定 EMA200 是拦还是罚。

| `use_ema` | `use_fib_pa` | `ema200_gate_mode` | 权重 | EMA200 闸门 | EMA50 最低值 | 谁在用 |
|---|---|---|---|---|---|---|
| false | false | 任意 | BASE 三档 `dynamic_weights` | **永不触发**：键不存在，`scores.get(...,1.0)` → 1.0（`EC:372`） | 跳过 | conservative / 类默认 |
| true | false | hard | `EMA_WEIGHTS` | `score<=0` → **NO_TRADE**（`EC:372-374`） | direct 0.60 / probe 0.40（`EC:390-397`） | 无（仅 `ema_hard` 试验配置） |
| true | false | soft | `EMA_WEIGHTS` | 允许，罚 −0.20（`src/signals/ema_scorer.py:49-51`） | direct 0.60 / probe 0.40 | **highest_win** |
| true | true | soft | `FIB_PA_WEIGHTS` | **跳过**：fib_pa 提前返回（`EC:366-371`）；EMA200 只喂 `trend_ema_context`（20 分里的 8 分） | 跳过 | fib_pa_v1 / v12 / regime_shadow |
| true | true | hard | `FIB_PA_WEIGHTS` | 不作闸门，但 `trend_ema_context` 在闸门失败时整块归零（`FEAT:116-124`） | 跳过 | 未使用 |

**"EMA200 硬闸"只在第 2 行真正存在**。fib_pa 下 EMA200 阻断与 EMA50 最低值都不可达——在 live 配置上调它们等于改死逻辑。

### 15.2 类默认值（`CFG:27-43`）

`direct/probe/watch_threshold` 82.0/70.0/60.0；DIRECT 分量最低值 `direction/quality/trigger/cvd` 0.64/0.73/0.92/0.61；PROBE 0.56/0.45/0.67/0.45；波动带 0.010/0.035；宏观 −0.05/−0.15；流动性 20.0/8.0。

### 15.3 配置覆盖（有差异的键）

| 字段 | 类默认 | fib_pa_v1（≡ regime_shadow） | highest_win |
|---|---|---|---|
| `watch_threshold` | 60.0 | **62.0** | 60.0 |
| `long_threshold_offset` | 0.0 | **10.0** | **10.0** |
| `probe_conditions`（enabled / long_threshold_offset） | None / — | **true**（min_score 72、min_fib 12、min_pa 10、min_rr_score 4）/ **7.0** | 未配置 / — |
| `disable_probe` | false | false | **true** |
| `use_ema / use_fib_pa / ema200_gate_mode` | F / F / hard | **T / T / soft** | **T / F / soft** |
| `fib_min_direct_score / rr_min_direct_score` | 6.0 / 2.0 | **9.0 / 4.0** | 6.0 / 2.0 |
| `direct_risk_pct / probe_risk_pct` | 0.008 / 0.003 | **0.006 / 0.0015** | **0.006 / 0.0025** |
| `enable_long_context_discounts` | false | false | **true**（0.70/0.60/0.75/0.80） |

### 15.4 有效 LONG / SHORT 阈值（**推导值**：由 §15.2 类默认与 §15.3 覆盖值叠加侧向偏移算出，代码未落盘）

- 类默认与 conservative：两侧同值，类默认 82/70/60、conservative 86/74/62（direct/probe/watch）。
- fib_pa_v1 / regime_shadow：LONG **92/77/72**、SHORT 82/70/62；highest_win：LONG **92**/80/70（`disable_probe` → probe 直接 NO_TRADE）、SHORT 82/70/60（probe 同上）。

两层**替换，不相加**（`EC:282-317`）：`_side_threshold_offset` 取 `long_threshold_offset=10.0`；`_probe_threshold_offset` 在 `probe_conditions.enabled` 且键存在时**覆盖**为 7.0（`EC:308-317`）。所以 LONG probe 落在 77.0——**比 LONG 侧向偏移低 3 分**；"7+10=17"是错的。SHORT 两层都是 0。生效偏移会写进 reason `SIDE_THRESHOLD_OFFSET_{side}_{offset:.2f}`（`EC:284-285`）。

### 15.5 权重

`FIB_PA_WEIGHTS`（`ECS:43-50`，合计 100，`FEAT:105-113` 的归一化分母与之一一对应）：`trend_ema_context` 20 =（闸门 8 + ema50×7 + 动量×5）/20；`flow_cvd_confirmation` 18 = `cvd_flow`；`cci_momentum_quality` 14 = `min(1, cci/14)`；`price_action_structure` 22 = `min(1, pa/22)`；`fibonacci_location` 18 = `min(1, fib/18)`；`risk_reward_geometry` 8 = `min(1, rr/8)`。

**BASE 三档**（`ECS:19-28,62-70`，仅两个架构开关都为 false 时生效）：中波动 8/25/22/12/18/10/3/2；低波动（atr<0.010）固定 `trigger_15m=18.0`、`cvd_flow=18.0`，其余按 BASE 比例重标定；高波动（atr>0.035）固定 `volatility_stop=20.0`、`cvd_flow=10.0`，其余重标定。"重标定"= `rescale_weights` 线性缩放、漂移记到首个剩余键，合计恒 100（`ECS:73-83`）。`EMA_WEIGHTS`（`ECS:30-41`）：5/18/12/7/**15/10**/18/10/3/2（含 `ema_50_quality`、`ema_momentum`）。

### 15.6 fib_pa 分量最低值与 probe 条件

DIRECT 最低值比的是**点数**（`EC:432-453`）：PA 6.0（权重 22）、fib 9.0（默认 6.0，v1 覆盖）、RR 4.0（默认 2.0，v1 覆盖）。失败降 direct→PROBE（`EC:450-452`）；probe 失败降 PROBE→WATCH（`EC:483-485`）；`probe_conditions.enabled=false` 时 `_apply_fib_pa_probe_minimums` 原样返回（`EC:465-467`）。`check_probe_conditions`（`EC:513-600`）按序：① `enabled` 否则 `PROBE_DISABLED`；② `min_score=72`；③ 结构最低值 fib≥12、pa≥10（高 beta 变体 pa 12 / rr 5 / cci 9 / ema 12）；④ 低分质量否决：`score<75` 且（ema<10 或 cci<7）；⑤ ema<10 **且** cci<9；⑥ elite 规则（`score>=75` 且 [(pa>=18 且 fib>=15) 或 (ema>=15 且 pa+fib>=30)]）；⑦ RR：`min_rr_score=4.0`。

### 15.7 死开关与无效配置

- `probe_conditions.min_rr_net_r`（1.3）：live 链硬编码 `rr_detail=None`（`EC:480`），`net_tp1_r` 分支永不执行，只有 `min_rr_score` 有效；`probe_conditions.max_active_probes` 无读取点，闸门用 `max_active_symbols`。
- `dry_run_q1_green_channel_*`（7 个键，`CFG:144-150`）：`q1_green_channel` 走的是 trend_launch 代码路径，这 7 个键只写进 summary 假设表。
- `base_direct_exposure_pct`（0.20，`CFG:51`）live 无消费者；`fib_swing_*` / `fib_extension_exhaustion_mult` / `fib_level_tolerance_atr_mult`（`CFG:179-185`）`src/` 内无运行时读取点（`fib_location.py` 用自己的函数默认值）。
- `enable_long_context_discounts` 在 fib_pa 下是**空转**：`_apply_long_context_discounts`（`EC:320-343`）只缩放 `quality_30m`/`ema_50_quality`/`trigger_15m`/`cvd_flow`，这四个键都不在 `FIB_PA_WEIGHTS` 里；只有 highest_win（EMA 架构）真正生效。

## 16. 仓位与杠杆

### 16.1 两条互不相通的路径

**路径 A —— live（真正决定下单名义）**：`_notional_hint` → `_notional_cap_diagnostics`（`EC:655-765`）。

`stop_pct` = `context.stop_pct`，否则 `clamp(atr×1.5, 0.005, 0.04)`（`EC:696-698`）；旧口径分支下 `raw_notional = equity × risk_pct / stop_pct`（`EC:735`），`leveraged_cap_notional = equity × max_single_trade_risk_pct(0.0075) / (stop_pct × leverage)`（`EC:736-738`）；`remaining_exposure_notional = max(0, (symbol_cap − symbol_exposure) × equity)`（`EC:739-741`）；`final_notional` 取三者 min、`binding_cap` 记胜者名（`EC:757-758`）。

**`risk_first_sizing_enabled` 分支（默认 `False`，四套主配置均未设置）**：`EC:724-733`。打开后 `raw = equity × min(risk_pct, 0.0075) / stop_pct`，`leveraged_cap_notional` 改算**保证金可支撑的名义**（`(available_margin − equity×margin_buffer) × leverage`）——键名不变，语义变了。打开会让同 `risk_pct` 下名义显著变大（旧口径被杠杆压掉约 3 倍，`CFG:227-234` 的注释写明了），必须先用独立配置验证。

**算例**（fib_pa_v1 的 `direct_risk_pct=0.006`；equity 10000、`stop_pct` 0.03、DIRECT 杠杆 4、ETH 上限 0.30）：raw 2000、leveraged 625、remaining 3000 → **final 625**，`binding_cap=leveraged_cap_notional`。类默认 0.008 时 raw 会变成 2666.67。决策组装时还有一次 min（`EC:794-805`），非 PROBE/DIRECT 直接返回全 0（`EC:677-686`）。`quantity = notional_hint / price`（`LEA:46`）；`min_quantity` 默认 **0.0**（`LEA:34`）且 RUN 从不传（`RUN:341-349`），所以**交易所最小下单量从未被校验**——`quantity > 0` 是唯一检查（`LEA:47-48`）。只有 MARKET 单、`reduce_only=False`（`LEA:58,61`）。

**路径 B —— `src/risk/position_sizer.py`（585 行）：spec only，未接线。** 实现了 DIRECT/PROBE 乘数、tier 乘数、波动乘数、`quantity_step` 取整、7 个 NO_TRADE 闸门、四个敞口上限——**没有一个在 live 路径上跑**。不要把它描述为生产风控层，也不要在那里"修"仓位。

### 16.2 杠杆短路表（`_select_leverage`，`EC:621-642`）

| # | 条件 | 杠杆 |
|---|---|---|
| 1 | action ∉ {PROBE, DIRECT} | 0 |
| 2 | `rolling_sharpe_20 < 0` | **2**（`ROLLING_SHARPE_LEVERAGE_CAP`） |
| 3 | `atr_pct > 0.03` | **3** |
| 4 | `atr_pct > 0.015` | DIRECT 4 / PROBE 3 |
| 5 | `score >= 90` 且 DIRECT（**仅 fib_pa 架构**；EMA 架构下此条件下恒 5，`EC:637-641`） | 满足 `_fib_pa_5x_requirements_met`（fib≥13/18、pa≥9/22、cci≥7/14、rr≥4/8）→ 5，否则 4 |
| 6 | 兜底 | DIRECT 4 / PROBE 3 |

`q1_trend_launch` 绕过整张表，硬 1（`RUN:1002`）。

### 16.3 `0.005–0.04` vs `0.03` 陷阱

`_notional_hint` 的分母是**入场侧** `stop_pct`，clamp 到 `[min_stop_pct=0.005, max_stop_pct=0.04]`（`CFG:58-59`；`RUN:2733`）——**不是** `paper_trading.MAX_STOP_PCT=0.03`（`PT:18`），也不是 `FEAT:170` 里的 0.03。三处口径并存，混用会让名义与止损距离差 33%。动任何 stop 常量前先 `grep -n "0.03\|0.04"` 看清自己在入场侧还是出场侧。

## 17. 风控三层与出场

### 17.1 三层不可逆

`entry_chain` 在草稿存在前就用 `NO_TRADE` 拦（adapter 随后 `approved=False`，`LEA:37-43`）→ `apply_dry_run_decision_controls` 只能把**已批准**的决策降为 WATCH 并把杠杆/名义清零（`RUN:2091-2118`，`_cap_decision_to_watch` 在 `RUN:2162-2172`）→ 纸面账本接管成交后的一切。下游无法反向撤销。

| 约束 | 生效值 | 层 | 位置 |
|---|---|---|---|
| 单笔风险 `direct/probe risk_pct` → `max_single_trade_risk_pct` | 0.006/0.0015（fib_pa 系）、0.006/0.0025（highest_win）；硬顶 0.0075 | entry_chain | `EC:723,735,736-738` |
| 单标的敞口 | 0.30 大盘 / 0.20 主流 / 0.10 高 beta | entry_chain + 硬闸门 | `EC:180-181,739-741`；`GATES:90-98` |
| 组合总敞口 / 同向敞口 | 1.6·1.1（fib_pa 系）/ 1.2·0.9（highest_win） | 硬闸门 | `GATES:60-63` |
| 保证金缓冲 | 0.30（两套主配置，默认 0.20），`available_margin = initial×0.8 − 已占用` | 硬闸门 | `GATES:64-65`；`RUN:2129,2731` |
| 持仓数 / 每日笔数 | 8/5 并发；2/1 每标的每日；16×/4× 波动比，地板 2/1 | 硬闸门（从纸面快照计数） | `GATES:52-57,73-79`；`PT:592-630` |
| 冷却 / 熔断 / 弱边际 | 见 17.3 | dry-run controls | `RUN:2091-2118` |
| 持仓时长 / 成本保本 / TP 节奏 | 32 根 / 8 根 / 1.2-2-3R | 纸面账本（与入场决策解耦） | `PT:18-22` |

改代码前先定位层：改 `CFG` 的阈值同时影响 entry_chain 行与闸门行；breaker 行有自己的一组字段（`CFG:193-225`），两组都要看。改 `apply_dry_run_decision_controls` 不会改变账本对已开仓位的处理。

### 17.2 `_update_position` 首匹配胜（`PT:301-366`）

| # | 触发 | 动作 | 位置 |
|---|---|---|---|
| 0 | 时间不新于入场/上次处理 → 跳过；否则更新 `best_price` / MFE-R | 幂等 + 记账 | `PT:308-313` |
| 1 | 未 TP 且 MFE-R ≥ 触发值且早保本开启 → 止损移保本；已有 TP 成交 → `_apply_post_tp_stop` | 移保本 / 收紧 | `PT:314-316,857-875` |
| 2 | 止损被打（high/low） | 全平 `INITIAL_STOP_HIT` / `BREAKEVEN_STOP_HIT` | `PT:320-324,904-905` |
| 3 | Q2 → 止损收紧；Q4 且 `streak>=2` 且净亏 **且 `defensive_overlay`** → 全平 `Q4_DEFENSIVE_EXIT`；Q3 首次 **且 `defensive_overlay`** → 减半 `Q3_DEFENSIVE_REDUCE` | 收紧 / 全平 / 减半 | `PT:326-341` |
| 4 | TP 命中（1.2/2.0/3.0R） | 减 40%/35%/25%；TP1 后止损移保本 | `PT:343-355` |
| 5 | 超时：`COST_BREAKEVEN_TIMEOUT`（≥8 根、从未 TP、毛利 < 0.5×往返成本）或 `MAX_HOLD_EXIT`（≥32 根） | 全平 | `PT:358-365,755-761` |

**同根 K 线止损优先**：第 2 步先于第 3–4 步判定（`PT:320` 在 `:326` 之前），所以同一根既触止损又触 TP 时按止损全平。这与 `LCE` 的顺序一致（`LCE:93-107` 先判止损，`:140` 再判 TP）。

**作用域**：第 3 步只在 `position.experiment_id` 存在时生效（`PT:798,811,821`）——象限防御是**实验账本专属**（`q1_trend_launch` / `scout_micro` / mirror），主账本的 PROBE/DIRECT 仓位没有 Q2/Q3/Q4 保护。`defensive_overlay` 再叠一层，只关 Q3/Q4（`PT:328-341`），**不关 Q2 收紧**（`PT:327` 无条件）——`pure_ladder` = "无 Q3/Q4 防御"，不是"无防御"。

**early breakeven 不是"永远关着"**：主账本默认关（RUN 不传该标志），但 A/B 的 `trend_capture` 臂通过 `mirror_ab_payoff_pilot_enabled` 打开、触发 1.0R（`RUN:618-628`）。fib_pa 系配置把它设为 true，所以 arm 里 1.0R 移保本，主账本不动。

**别在没 grep 赋值点前改出场逻辑**：Q3 减半依赖 `PaperPosition.q4_streak` / `q3_reduced`（`PT:128-129`）与每周期重供的 `decision_payload["quadrant"]`。`consecutive_negative_bars` 这个字段**不存在**，grep 不到；若重供断掉，防御会静默失效——不报错、不减半。

**保本价**：`entry × 1.001 / 0.999`（±10bps 缓冲，`PT:878-879`；数值等于单边成本 10bps，但是**独立硬编码常量**，不要互相推导）。**TP 后止损**：非 `trend_capture` 一律移保本（`PT:858-860`）；`trend_capture` 的 `trend_trigger_r` **按账本不同**——A/B 臂 = **1.2**（`config.mirror_ab_payoff_trend_trigger_r`，`RUN:623`；v1/v12/regime_shadow 均 `pilot=True`，`pilot=False` 的配置如 highest_win 回落到 `paper_exit_trend_trigger_r` 默认 1.5），scout 账本 = **1.5**（`scout_micro_exit_trend_trigger_r`，`RUN:594-601`），主账本 `paper_exit_mode=legacy` **根本不进该分支**（`RUN:602-608`；只有状态文件写了 `paper_exit_mode_override=trend_capture` 才会切过来，`RUN:668-673`）。触发后按 `best ∓ risk_distance × trailing_r_mult` 只收紧（`PT:865-875`，两份 fib_pa 配置 `trailing_r_mult=1.0`）。**"1.5"只属于 scout 账本，不是 `trend_capture` 的通用值。**

**`stop_pct` 三级回退**（`_resolve_stop_pct`，`PT:33-64`）：
1. `decision_payload["stop_pct"]`（`PT:47-48`）
2. `metadata.risk_budget.stop_pct` —— **实际命中的是这条**：`metadata.risk_budget` 由 `EC:823` 的 `"risk_budget": cap_diagnostics` 写入；`stop_pct` 字段在兜底 return（`EC:748-756`）与正常 return（`EC:759-765`）各写一次（`PT:50-56`）
3. `atr_pct × 1.5` clamp 到 `[min_stop_pct, max_stop_pct]`，ATR 缺失默认 0.01（`PT:59-64`）

运行时 clamp 是 0.005–0.04，因为 `PaperExitConfig` 由入场配置构造（`RUN:593-608`），覆盖了 `PT:18` 的 0.03 默认。函数 docstring 记录了历史上的 3% vs 4% bug（`PT:44-45`）。

### 17.3 组合冷却与熔断（全在 `RUN`）

| 机制 | 条件 | fib_pa 系 |
|---|---|---|
| 观察标的 | symbol ∈ `observation_only_symbols` → `SYMBOL_OBSERVATION_ONLY`（`RUN:2102-2103`） | `XLMUSDT/TONUSDT`（highest_win 仅 `XLMUSDT`） |
| 止损后冷却 | 该 symbol 4h 内有 `INITIAL_STOP_HIT` | 开，4h（`RUN:2175-2193`） |
| 滚动冷却 | 48h 内 ≥2 次止损 → 24h 冷却 | 开（2/48/24） |
| 连续止损熔断 | 最近 N 笔全 `INITIAL_STOP_HIT` → H 小时禁新开 | 开（2/2h） |
| 日内亏损熔断 | 当日 Σ`position_realized_pnl` ≤ −30 | 开 |
| 弱边际降级 | DIRECT 82–85 / PROBE 77–82 且该 symbol 无盈利史 → WATCH | 82-85 / 77-82 |
| 实验战备金熔断 | 同 `experiment_id` 累计 ≤ −150 或当日 ≤ −200 | 开（读 `net_pnl_full`，`RUN:1757-1777`） |
| Scout 冷却 / 任务熔断 | 同向 2h、止损后 6h 冷却；单任务连续 3 次止损 → 12h 暂停 | 开 |

前六类经 `_cap_decision_to_watch` 落地（action=WATCH、side=NONE、`risk_allowed=False`、杠杆/名义归零）；战备金熔断与 scout 行在实验/scout 入口就拒绝（`RUN:255`）。`apply_dry_run_decision_controls` 在 `src/` **没有对应物**——回测与任何非 dry-run 调用都拿不到这些保护。

### 17.4 `src/risk/` 大部分未接线

只有 `net_beta_exposure_model` 与 `stress_simulator` 被 live 链 import（`RUN:27-32`），**且都是纯观测**：

- **净 beta**：静态 beta 表（BTC 1.00、ETH 1.05、BNB 0.90、SOL 1.25、HYPE/LAB/CC 1.80，未知 1.20；`NBE:7-26`），`Σ signed×beta×notional×remaining/equity`（`NBE:31-46`），cap 0.50、模型名 `static_v1_observation_only`（`NBE:27-28`）。RUN 只写汇总（`RUN:873-895`）；`net_beta_exposure_within_limit`（`NBE:49-50`）**从未被调用**。
- **stress**：`exposure × leverage × adverse`（`SS:4-5`），传入的是 `decision.max_symbol_exposure_pct`（**单标的上限，不是本笔名义/权益**），adverse 0.20、max 0.25（`RUN:332-339`）。它会产出 `action="BLOCK"`，但**没有任何代码读 `stress["action"]` 来拦单**。

`position_sizer` / `risk_engine` / `exit_engine` / `stop_engine` / `portfolio_guard` / `cooldown_guard` 只被 `scripts/describe_*.py`、`tests/`、scaffold 引用；`risk_engine` 内部再调 `exit_engine`/`stop_engine`，这不等于上生产。`portfolio_guard.exposure_allowed` 与 `cooldown_guard.is_cooldown_active` 无任何调用点。两处 spec-vs-实现分叉可以作证：`exit_engine` 的 TP 计划是 **1.0/2.0/3.0R @ 30/40/30%**（`src/risk/exit_engine.py:46-47`），live 账本是 **1.2/2.0/3.0R @ 40/35/25%**（`PT:22-23`）；`risk_engine` 的日亏 5% / 周亏 12% / 最大回撤 20% / 单标 20%（`RE:103-106`）是**意图**，不是行为。

**唯一仓位来源是 `entry_chain`**：RUN 直接 import 私有 `_notional_cap_diagnostics`（`RUN:33`），并在 3 处调用——`q1_trend_launch`（`RUN:962`）、`scout_micro`（`RUN:1843`）、mirror（`RUN:1953`）。没有任何并行的第二套 sizing。已知**宽松点**：scout 与 q1 通道手工重建 `EntryChainContext`，把 `available_margin` 直接设为 `current_equity`（`RUN:1030,1815`），而不是主账本的 `0.8×initial − 已占用`，所以它们的保证金缓冲闸门宽了 0.8 倍。是否有意，代码无法判定。**敞口分母**：`get_portfolio_state_snapshot` 的敞口与日收益都除以 `initial_equity`（`PT:597`），RUN 再用 `exposure_scale = initial/current` 缩放（`RUN:2147-2157`）——盈利账户更保守、亏损账户更宽松。新指标必须用同一分母，否则与闸门不可比。

## 18. PnL 口径契约与三 A/B 臂

### 18.1 两个口径，一张表只能选一个

`PNL_SCHEMA_VERSION = 2`（`PT:30`）。每个 `PAPER_CLOSE` / `PAPER_REDUCE` 事件都带 `gross_pnl` / `entry_cost` / `exit_cost` / `net_pnl` / `net_pnl_full` / `pnl_schema_version`（`PT:401-421`），并带 `"pnl_accounting_mode": "notional_primary_margin_reporting"`（`PT:276,425,477,530`；summary 侧 `RUN:492`）——**名义口径为主、保证金口径仅展示**，二者不是并列可选。

| 字段 | 公式 | 位置 |
|---|---|---|
| `net_pnl`（=`notional_pnl`） | `gross − exit_fee − exit_slippage`，**只含出场成本** | `PT:384,416-417` |
| `entry_cost` | `(entry_fee + entry_slippage) × fraction`，按平仓比例摊分 | `PT:387,418` |
| `net_pnl_full` | `net_pnl − entry_cost`，**唯一能与权益对账的口径** | `PT:388,420` |
| `margin_pnl` / `realized_margin_pnl` | `net × max(1, leverage)`，**deprecated**：状态戳字面为 `"margin_pnl_status": "deprecated_leverage_double_count"` | `PT:389,422`；状态戳 `PT:479,532` |

**账本成本是常数假设**：`FEE_BPS = 5.0`、`SLIPPAGE_BPS = 5.0`（`PT:14-15`）——单边 10bps、往返 20bps，事件里标 `cost_source: "constant_assumption"`（`PT:296,444`），**不分 maker/taker**。fwdlib 研究线的 `maker_6 / hybrid_10 / taker_20`（`fwdlib/cost.py:187-191`）是**另一套口径**，不可与账本成本互相代入。

**关键不变量**：任意切片的 `Σ net_pnl_full` = 账本权益变动；`Σ net_pnl` 系统性地乐观一个建仓成本。`ledger_reconcile_20261031.py --selftest` 断言 `abs(full − realized) < 1e-6`，其 `:177` 还**硬断言** `margin_pnl_status == "deprecated_leverage_double_count"`（改文案即让 selftest 红）。任何对外表格都要在表头写口径；close-only 不是"错"，只是窄。

`_load_positions` 不再静默造 deprecated 字段：旧状态缺 `realized_margin_pnl` 时按同额回填（**不再乘杠杆**）、计数 `derived_margin_backfill_count`、打 WARN（`PT:666-688`）。`summary()` 里这个计数非 0 表示状态文件早于修复，那些行是重建值，不是记录值。要看保证金视角收益率用 `realized_margin_return = Σ(net / margin_used)`（`PT:535`）。

### 18.2 被修过的读取点（曾经是真 bug）

| 位置 | 改前 | 改后 | 后果 |
|---|---|---|---|
| `_experiment_pnl`（`RUN:1757-1777`） | 读 `margin_pnl`（被杠杆放大 3–4 倍） | 读 `net_pnl_full`，退回 `net_pnl` | 战备金/日亏熔断（−150 / −200）原本在真实亏 40–50 USDT 时就触发；现在按字面值触发 |
| `paper_ab_closed_stats`（`RUN:680-721`） | close-only，全样本 | 全成本 + `excluding_mirror` 子块（`RUN:714-720`） | `mirror_ab_sample` 以固定 50 USDT 名义记录、占比极高；含它们的臂对比是在比采样，不是比出场 |

### 18.3 三条 A/B 退出臂（`build_paper_exit_ab_ledgers`，`RUN:611-638`）

| 臂 | `PaperExitConfig` | `defensive_overlay` | 存在于 |
|---|---|---|---|
| `legacy` | `mode="legacy"` | **on**（默认） | 所有配置 |
| `trend_capture` | `mode="trend_capture"`，`mirror_ab_payoff_pilot_enabled` 时 1.0R 早保本 | on | fib_pa 系（v1/v12/regime_shadow） |
| `pure_ladder` | `mode="legacy"`，`defensive_overlay=False` | **off** | 仅 `paper_ab_pure_ladder_enabled`（`CFG:143` 默认 False；**v12 true、v1 false**） |

`defensive_overlay` 只门控两个分支：`Q4_DEFENSIVE_EXIT`、`Q3_DEFENSIVE_REDUCE`（`PT:328-341`），**不关 Q2 收紧**（`PT:327`）。`legacy` 与 `trend_capture` 的退出参数与模式字符串相对 10-31 之前未变【配置声明】（未见逐字节 diff 证据）；`verify_pure_ladder_arm.py` 断言新账本 `defensive_overlay is False`、legacy 为 `True`，并用同一决策序列回放证明事件流只在这两个 reason 上分叉。

## 19. 11 月窗口结论（2026-10-31 重启 → 11-08，已封版归因）

以下全部来自 `docs/analysis/2026-10-31_to_11-08_loss_attribution.md`（已核实项），**只陈述事实与口径，不含投资建议，不判定策略优劣**。

| 项 | 值 |
|---|---|
| 窗口 / 重启 | 2026-10-31 12:02:35 UTC 起；至 11-08 无新 `process_start` |
| 主账本（MAIN） | 11 笔完整生命周期，`Σ net_pnl_full = +33.762404`，胜率 27.27%，PF 3.9106，`actual_payoff_ratio` 10.4283，MaxDD 0.28%，11-08 `open_positions=0` |
| 单笔集中度 | `NEARUSDT:1793889000:SHORT` 贡献 `+32.948542` = 净额 **97.59%**；剔除后仅 `+0.813862` |
| 四账本（**各自 `initial_equity=10000`，独立模拟，不可相加**） | MAIN `+33.762404`（11 笔）/ `scout_micro` `−3.323394`（12 笔）/ AB `legacy` `+25.087716`（73 笔）/ AB `trend_capture` `−5.121646`（74 笔） |
| 成本 | `fee+slippage` 合计 `14.666576` = 净额 **43.44%**；`entry_cost` 7.342826 + `exit_cost` 7.323750 |
| deprecated margin | `realized_margin_pnl = 125.523624` ≈ 权威口径 **3.72×** |
| 统计边界 | 按笔 Wilson 95% `[0.0975, 0.5656]`；簇 `n_eff=9`（同 symbol 同 UTC 日）；打平胜率 `p_be=0.087502`；二项检验 `p=0.0648`；按簇 Wilson `[0.063225, 0.547411]`（覆盖 `p_be`） |
| AB 配对 | 73 对中 **63 对两臂完全相同**；臂总额差 `30.209362`；**1 对**占 `Σ\|diff\| = 41.959735` 的 **82.43%**（分母是 `Σ\|diff\|`，不是臂总额差） |
| 出场构成 | `trend_capture` 的 `TP3_HIT = 0`，`legacy` = 2 事件 |
| 口径对账 | `Σ net_pnl_full`(33.76240390) 与 `paper_summary.json:realized_notional_pnl`(33.76240389561417) 差 `−7.1e-15` |
| 过程量 | 累计曲线谷底 `−8.606919`（11-03），11-04 转正 |

**三条判读纪律**：

1. **单笔占 97.59% → 不能称"alpha"**。剔除后剩 `+0.813862`，且前 2 笔占总盈利 98.70%。
2. **四账本不可相加成组合净值**。它们是同一窗口的四次独立模拟，不是四个子账户；跨臂只有"对比"，没有"合计"。
3. **报 `n_eff` 而不是名义笔数**。`n=11` 但 `n_eff=9`，低于 `<10 笔不判定` 的样本门槛（§21），故该窗口只能登记线索，不能升级为结论。

## 20. 文档-代码漂移登记（9 类 + 2 条附）

| # | 漂移项 | 文档侧原文（旧稿，行号不可复核） | 代码或实跑侧事实/行号 | 状态 |
|---|---|---|---|---|
| 1 | VPS 运行口径 | 旧稿称 systemd 跑 `highest_win`+aggressive+5s，并称其为 "VPS production config"（旧稿行号不可复核） | 实跑 `regime_shadow`/conservative/10s/14（`logs/2026-10/2026-10-31/runtime.out.12.log:L1-L5`）；systemd 只是**声明口径**（`deploy/systemd/ai300-dry-run.service:10`） | 已修正（§2） |
| 2 | `FEAT:` 指向不存在的文件 | 旧稿写 `FEAT: src/signals/features.py`（旧稿行号不可复核） | 实际 `src/signals/entry_chain_features.py`（378 行）；`src/signals/features.py` 不存在 | 已修正（§5.2） |
| 3 | `GATE:` 张冠李戴 | 旧稿把 15 硬闸门归 `entry_gate.py`（旧稿行号不可复核） | 硬闸门在 `src/signals/entry_chain_gates.py:38-70`；`entry_gate.py` 是声明式 `EntryGate`（`:68`）/`build_gate_features`（`:116`） | 已修正（§5.2、§13.2） |
| 4 | RUN 行数与锚点漂移 | 旧稿写 "3249 行"、称后半段有 +70~+110 偏移（旧稿行号不可复核） | 实测 3251 行；旧稿自述的偏移量已不可靠，锚点一律按符号名 grep | 已修正（§5.2） |
| 5 | sizing 行号与漏项 | 旧稿记 `EC:723-724 / 725-727 / 728-730 / 746-747`（旧稿行号不可复核） | 实测 `735 / 736-738 / 739-741 / 757-758`；旧稿漏了 `risk_first_sizing_enabled` 分支（`EC:724-733`，默认 False、四套主配置均未设） | 已修正（§16.1） |
| 6 | `stop_pct` 来源 | 旧稿称 "the live chain does not produce it"（旧稿行号不可复核） | `run_live_dry_run.py:2733` 明确构造 `EntryChainContext.stop_pct`；三级回退 `payload → metadata.risk_budget → atr×1.5 clamp`（`PT:33-64`；`metadata.risk_budget` 由 `EC:823` 写入，`stop_pct` 字段在兜底 return `EC:748-756`、正常 return `EC:759-765`） | 已修正（§17.2） |
| 7 | shadow / entry_gate 行号 | 旧稿记 `RUN:1159`、`RUN:1136`、`entry_gate.py:148-149` 为"立即返回"（旧稿行号不可复核） | 实测 `shadow_total → build_gate_features.shadow_pct` 在 `RUN:1161`；`apply_entry_gates` 定义 `RUN:1138`、立即返回 `1154-1155`；`entry_gate.py:148-149` 是 `build_gate_features` 里的 `shadow_pct` 赋值 | 已修正（§7） |
| 8 | `run_shadow_regime.sh` 自相矛盾 | `run_shadow_regime.sh:42-44` 注释称 13 个与 highest_win 一致、研究配置 14 个 | 默认 `SYMBOLS` 串决定实跑标的并**覆盖**配置的 `dry_run_symbols`（CLI `--symbols` 优先，`run_live_dry_run.py:2300-2303`）；且默认串不含 LABUSDT | 已修正（§2.3） |
| 9 | `log_only` 机制 | `docs/2026-10-31-评审回应与落地计划.md:134` 的落地项 L6"`q1_trend_launch` 标记 `log_only`，从汇总剔除" | 代码/配置/脚本全库 grep **无此标记**，只出现在 3 份评审 MD；L6 **未能确认**已落地 | 【未能确认】 |
| 附-1 | `evaluate_entry_chain` 步数 | 旧稿称 "strict 22-step sequence"（旧稿行号不可复核） | 无法逐条给出 22 项行号；本稿只给分支块（`EC:86-205`） | 已修正（§13.1） |
| 附-2 | 通道价带 | 旧稿称 `q2_pending` 用"目标侧价带"、`q1_trend_launch` 用"斐波回撤区"（旧稿行号不可复核） | **【代码事实】已证伪**：`grep "band" scripts/run_live_dry_run.py` 命中 0（全库唯一的 `band` 是 `orthogonal_factors.py:349` 的 BOLL 带宽 `band_expansion`，与入场无关）；两个 pending 构造器只落 6 个字段、**无价格字段**——`build_q3_pending_candidate`（`RUN:1614-1634`）/`build_q2_pending_candidate`（`RUN:1637-1657`）返回 `symbol/side/created_at/expires_at/source_score/source_quadrant`；入场价全部取当根收盘：`near_miss["entry_price"] = kline["close"]`（`RUN:925`）、草案 `price` 取 `kline.close`（`RUN:340`）、scout `price = kline.close or near_miss_price`（`RUN:2053`）、纸面开仓 `_open_position` 取 `kline.close`（`PT:209`） | 已修正（§14 陷阱 b） |

**旧稿行号为什么一律不引**：本文已覆盖旧稿，`git show HEAD:CODEBUDDY.md` 只剩 381 行且内容对不上（22-step 说法在 `HEAD:124`、`stop_pct` 断言在 `HEAD:329`、sizing 行号在 `HEAD:268-270`），故只保留可辨识的原文片段并括注"旧稿行号不可复核"，不提供任何旧行号。

## 21. 约定

- **时间**：数据与日志用真实 UTC；报告与分析 prose 用北京时间（UTC+8）。`decisions.jsonl` 顶层 `timestamp` = 决策时刻，`kline.timestamp` = K 线开盘；按日归档看顶层 `timestamp`。事件文件按 **UTC 日**切分，所以"北京 11-02"的成交可能落在 `2026-11-01/` 里。
- **PnL**：三口径并存——`net_pnl_full` 与权益对账、是新表默认；`net_pnl` 只含出场成本、表头必须注明；`margin_pnl` deprecated（杠杆双计），**永不引用、永不据此给标的排序**。任何数字出门前，`Σ net_pnl_full` 与账本 `realized_notional_pnl` 必须对到 0.0000。
- **测试**：新逻辑必须带 pytest。碰风控/进攻的改动，先经 dry-run / paper / SCOUT / A-B 验证，再说"修好了"。
- **配置锚定**：`tests/test_dry_run_configs.py` 是每份配置 JSON 的断言面。改阈值不同步更新它 = 让绊线失效。
- **`stop_pct` 单一来源**：入场算仓位与出场摆止损必须解析到同一个值。历史 bug 是入场允许 4%、账本按 3% 止损，导致 4% 止损仓位在 3% 被平。**永远不要只改一侧**。
- **样本纪律**：`<10` 笔不判"有效/无效"，`<20` 笔不调参、不重新分配资源（`scripts/channel_cumulative_tracker.py` 常量）。小窗口的 `lift` 同样不是决策级证据；轮次报告落 `docs/`（中文），状态记 `docs/recommendations_tracking.md`，开篇跑 `recommendation_tracker.py check`，做完改 DEPLOYED/VERIFIED，结论绑定预登记的完整样本窗口。
- **交付纪律**：分析脚本放 `scripts/` 或 `scripts/analysis/`；**禁止**用内联 `python -c` 产出交付物；中间产物放 `logs/analysis/` 或 `reports/`（均 git-ignored）。
- **合并前最小测试集**：`python -m pytest tests/test_dry_run_configs.py tests/test_entry_chain.py tests/test_paper_trading.py -q`。源码级审计只逐 hunk 复核，这三个文件才是行为网。
- **部署流程**：本地交付 → 用户同步 VPS（`docs/runbooks/offense-fix-deploy.md`）→ systemd 重启 → 跑 `vps_dry_run_healthcheck.py --config <unit 用的同一个配置>` 与 `verify_q1_trend_launch_fix.py --mode online`。三个 unit：`ai300-dry-run.service`、`aibot.service`（声明口径 highest_win）、`ai300-shadow-regime.service`（跑 `run_shadow_regime.sh`，工作目录 `/root/AIBOT-shadow`，账本完全隔离）。**影子结果永远不进生产 PnL 表**。
- **绝不跨天求和 `summary.json` 计数器**：它们是进程启动以来累计、且被重写进每个日切片。要从 JSONL 事件重算（参考实现：`funnel_recount_20261031.py`）。
- **git**：分支按主题/日期命名（`09-27-5factor`、`20261031-v2`、`workbuddy/feat-…`）。github.com 不通时：`git -c http.proxy=http://127.0.0.1:12334 push`。不要提交 `.reasonix/`、`.pytest_tmp_*`、`docs/80-07-00.txt`（历史遗留）。`logs/`、`data/`、`reports/`、`.env*`、密钥已被忽略。

## 22. 已知基线问题（别"顺手"修）

**2026-11-08 实测（计数与失败用例固定；耗时 ≈50s，随机器波动，多次复核落在 46.06s–56.04s）**：

```bash
.venv/Scripts/python.exe -m pytest tests/ -q --ignore=tests/test_verify_five_factor_orthogonality.py
→ 1 failed, 870 passed
```

- **唯一失败**：`tests/test_describe_indicator_rules.py::test_describe_indicator_rules_outputs_completed_03_contract`——spec 写 `EMA`，文档期测试期望 `RSI`。这是**契约漂移，不是回归**；`tests/` 共 104 个 `test_*.py`。
- **`numpy` / `pandas` 不在 `requirements.txt`**：import numpy 的只有 3 个文件——`scripts/analyze_0916_0927_window.py`、`scripts/verify_five_factor_orthogonality.py`、`tests/test_verify_five_factor_orthogonality.py`；`scripts/analysis/` 内 **0 个**（只有 `fwd_label_v2_20261019.py:132`、`fwdlib/cost.py:209` 的 docstring 提及 numpy 口径）。import pandas 的 7 个全部在 `scripts/analysis/`。缺 numpy 会让 collection 直接中止，这就是上面必须 `--ignore` 的原因。要么装，要么保持忽略。
- **系统 `python` 是 3.13 且没有 pytest**，`python -m pytest` 会 `No module named pytest`。一律用 `.venv/Scripts/python.exe`。
- **`stop_pct` clamp 不一致（已知，故意不修）**：`EntryChainConfig` 允许 `[0.005, 0.04]`（`CFG:58-59`），`paper_trading` 的 dataclass 默认 `0.03`（`PT:18`，运行时被配置覆盖成 0.04），`entry_chain_features.risk_reward_geometry_detail` 又硬编码 `[close×0.005, close×0.030]`（`FEAT:170`），`lifecycle_exit` 默认 `[0.005, 0.03]`（`LCE:27-28`）。四处并存，见 `docs/analysis/fwd_label_v2_2026-10-19.md` §3.5。**动一处必须同时想清另外三处**。
- **`mirror_ab` 只在 fib_pa 系跑 `shadow_only`**：`mirror_ab_enabled: true` + `mirror_ab_mode: "shadow_only"`；`highest_win` 完全没有 `mirror_ab` 块（默认 `mirror_ab_enabled=false`）。`reversal_pivot` 与 `q1_rr_gap` 是**开关默认关闭**（置 true 即参与判定，见 §14），不是死代码。
- **`pure_ladder` 在 v1 关、v12 开**。报"第三臂缺失"通常是你在读 v1 的账本树。
- **两类死代码**：① `entry_chain.py` 里的重复实现——`_hard_block_reason`（缺两条闸门）、`_liquidity_ratio`、`_symbol_exposure_cap`、`_rescale_weights`、`_component_points`（`EC:212-229,232-259,603-618`）；② 死配置键——`min_rr_net_r`、`max_active_probes`、`base_direct_exposure_pct`、7 个 `dry_run_q1_green_channel_*`、`fib_swing_*` 一族（见 §15.7）。
- **`lifecycle_exit` 与 `paper_trading` 口径不同，且前者未接入 live**：TP 阶梯 `1.0/2.0/3.0`（`LCE:30`）vs `1.2/2.0/3.0`（`PT:22`）；`max_hold_bars` 16（`LCE:32`）vs 32（`PT:19`）；两者都止损优先（`LCE:93` 先于 `:140`；`PT:320` 先于 `PT:326`）。`simulate_atr_tp_exit` 只被 `src/backtest/engine.py:10,664` 与测试引用，**live 主循环无引用**——回测的 `--exit-model atr_tp` 走它，paper 账本不走。是否为设计意图【未能确认】，**不要写成"已接入"**。
- **`log_only` 不存在**（§20 第 9 条）。看到任何"该通道已标记 log_only"的说法，先 grep。

**重生成 checklist**（每次重生成逐项刷新；值取不到就留空，别抄旧值）：

1. §2.4 工作树状态（`git status --porcelain`）。
2. §5.2 缩写表各文件行数（`wc -l`）。
3. §16.1 sizing 算例（`direct_risk_pct` / 杠杆 / `stop_pct` 三者联动）。
4. §19 窗口数字（`paper_summary.json` + 归因报告）。
5. §20 漂移表（旧稿已被覆盖，只保留原文片段）。
6. §22 测试计数与失败用例名（`.venv/Scripts/python.exe -m pytest tests/ -q --ignore=…`）。
