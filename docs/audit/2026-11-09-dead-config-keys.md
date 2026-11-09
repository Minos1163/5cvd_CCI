# 死配置键治理（2026-11-09）

`EntryChainConfig` 共 201 个字段。静态审计（`scripts/audit_config_wiring.py`，报告
`docs/audit/config-wiring-20261109.json`）标出 16 个 `DECLARED_ONLY`，逐个人工 grep 复核后
确认其中 **15 个是真死键**：声明之外，在 `src/`、`scripts/` 中零引用，配置模块内部也无解析逻辑。

## 1. 15 个死键

| 字段 | 默认值 | 声称的作用 | 实际状态 |
| --- | --- | --- | --- |
| `base_direct_exposure_pct` | 0.20 | 直接入场的基础仓位占比 | 无读取点；仓位由 `max_*_exposure_pct` 与 risk 口径决定 |
| `probe_fraction` | 0.25 | probe 相对 direct 的仓位比例 | 无读取点 |
| `ema200_buffer_pct` | 0.003 | EMA200 闸门缓冲带 | 无读取点；闸门只看 `ema200_gate_mode` / `use_ema_architecture` |
| `ema200_min_bars_stable` | 3 | EMA200 状态需稳定的 K 线数 | 无读取点 |
| `fib_extension_exhaustion_mult` | 1.618 | fib 扩展耗尽倍数 | 无读取点；耗尽判定用的是别的常量 |
| `fib_level_tolerance_atr_mult` | 0.5 | fib 位容差（ATR 倍数） | 无读取点 |
| `fib_swing_fractal_k` | 2 | 摆动点分形左右 K 线数 | 无读取点 |
| `fib_swing_lookback_15m` | 50 | 15m 摆动点回看根数 | 无读取点 |
| `fib_swing_lookback_1h` | 30 | 1h 摆动点回看根数 | 无读取点 |
| `fib_swing_min_atr_mult` | 1.2 | 摆动点最小幅度（ATR 倍数） | 无读取点 |
| `fib_swing_min_spacing_bars` | 6 | 相邻摆动点最小间隔 | 无读取点 |
| `scout_micro_non_rr_min_score` | 85.0 | 非 RR 路径 scout 最低总分 | 无读取点 |
| `scout_micro_targeted_long_min_score` | 82.0 | targeted long 最低总分 | 无读取点 |
| `scout_micro_targeted_long_min_pa_score` | 18.0 | targeted long 最低 PA 分 | 无读取点 |
| `scout_micro_targeted_long_min_rr_score` | 3.0 | targeted long 最低 RR 分 | 无读取点 |

处置：字段声明保留，`DEAD_CONFIG_KEYS` 集中登记；14 个 tracked 配置共删除 83 处键值
（另 4 个 tracked 配置本就不含这些键）。18 个 tracked + 1 个 untracked 副本共 19 个仍全部可加载。

## 2. `scout_micro` 是半接线，比纯死键更危险

名单**生效**：`scripts/run_live_dry_run.py:1495` 用 `config.scout_micro_targeted_long_symbols`
判断资格，`scripts/run_live_dry_run.py:1544` 用 `config.scout_micro_scout_only_symbols` 筛选
scout_only 高分放行，`scripts/diagnose_*.py` 也读这两份名单。

门槛**不生效**：`src/` 与 `scripts/` 对 `scout_micro_targeted_long_min_{score,pa_score,rr_score}`
与 `scout_micro_non_rr_min_score` 的引用数为 **0**；`_high_score_long_offset_probe_eligible`
（`run_live_dry_run.py:1493`）实际校验的是 `scout_micro_high_score_long_offset_min_*` 那组门槛。

后果：配置里"哪些符号享受 targeted long 待遇"真的生效，"门槛设在多少分"被静默忽略。维护者
看到名单与门槛成对出现，会以为整套机制在工作。删掉门槛是让这一事实显式化，而非修复（见第 6 节）。

## 3. `explicit_watchlist` 不是死键

它在 `src/signals/entry_chain_config.py` 内有完整的 `_parse_explicit_watchlist`：校验重复符号、
非法 `scan_scope`、与黑名单冲突，缺失 scope 时默认 `scout_only`。它属于"有解析、暂无业务消费"。

## 4. `ema200_*` 与 `configs/strategy.yaml` 是两个独立体系

`src/config/config_schema.py` 的 `entry.ema200_buffer_pct` / `entry.ema200_min_bars_stable` 是
yaml 白名单（`configs/strategy.yaml:32-33` 确有这两个键），走 pydantic 校验；entry-chain 的
同名字段走 `from_mapping`。两边只是同名，互不影响，本次不动 `config_schema.py`。

## 5. 为什么保留字段声明而不删除

`from_mapping` 对未知键 `raise ValueError("unknown entry-chain config keys: ...")`。VPS 上运行的
历史配置（如 `configs/entry_chain.dry_run_regime_shadow.json`）若仍带这些键，删字段会让实例
**启动失败**。正确顺序：保留声明 → 清理配置文件 → 确认无外部配置携带后再删声明。

## 6. 为什么接线是禁区

这 15 个参数分别影响 fib 摆动点识别、EMA200 闸门与 scout 准入。让它们真正生效会改变信号、
进而改变交易，属于"改策略参数"。本次只做"声明与配置的一致性"，不触碰任何决策路径。

## 7. 审计工具的已知假阳性

`scripts/audit_config_wiring.py` 的 `excluded_paths` 含 `src/signals/entry_chain_config.py`，
"在配置模块内部被解析、外部无消费"的字段会被误报为 `DECLARED_ONLY`；当前唯一实例是
`explicit_watchlist`，`test_dead_keys_match_audit` 把该差集写死，出现新差异会立即变红。
