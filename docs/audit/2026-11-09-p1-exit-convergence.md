# P1-E8 出场 spec 收敛报告（2026-11-09）

> 分支 `20261109-v1`，基线 `2048ef2`。**只收敛默认口径，不改任何交易阈值/权重/仓位。**

离线回测默认出场参数已从 legacy 切到 `CANONICAL_EXIT_SPEC`，与 paper 主账本同构；
`KNOWN_EXIT_SPEC_DIVERGENCE` 随之删除。**历史离线结论未重跑（NOT_RUN）**，
原因是本地缺 `data/raw/binance_futures/latest_30d`。

## 1. 变更前后对照

| 项 | 变更前（legacy 回测默认） | 变更后（= canonical / paper） |
|---|---|---|
| TP1 | 1.0R | **1.2R** |
| TP2 / TP3 | 2.0R / 3.0R | 不变 |
| 分批 | 0.40 / 0.35 / 0.25 | 不变 |
| `max_hold_bars` | 16 | **32** |
改动点：`src/backtest/lifecycle_exit.py` 的 `AtrTpExitConfig` 默认值。

## 2. 影响面

**受影响**：任何直接 `AtrTpExitConfig()`（不显式传参）的离线调用方。**不受影响**：

- `src/backtest/engine.py:645` —— 构造时**自带 fallback**（`tp_levels` 读
  `risk_constraints` 否则 `(1.0,2.0,3.0)`；`max_hold_bars` 否则 16），不依赖数据类默认值，
  行为完全不变。本次未改该文件。
- `paper_trading.py` 本就引用 `CANONICAL_EXIT_SPEC`，口径未变；`from_spec(...)` 参数显式给出。

## 3. 测试调整

`tests/test_lifecycle_exit.py` 的 10 处 `AtrTpExitConfig(...)` 全部改为 `legacy_cfg(...)`。
这些用例 bar 高点卡在 1.0R/2.0R/3.0R（如 `101.1`；`stop_pct=1%` → 1R=101.0、1.2R=101.2），
测的是 **legacy 阶梯语义**；不显式声明则切默认后会"打不到 1.2R"假红。helper 只补
`tp_levels`/`tp_fractions`/`max_hold_bars`，其余参数（`atr_stop_mult=1.5`、
`min/max_stop_pct=0.005/0.03`、`max_hold_bars=1` 等）逐字保留原语义。

`tests/test_exit_spec_isomorphism.py`：`test_backtest_default_stays_legacy` →
`test_backtest_default_is_canonical`；新增 `test_legacy_spec_still_reproducible`；删除
`test_divergence_is_registered_not_hidden`。
## 4. 历史结论重跑状态：**NOT_RUN**

`ls -d data/raw/binance_futures/latest_30d` 不存在，而 `scripts/run_offline_backtest.py
--data-dir` 默认指向该目录，**离线回测无法执行**。尚未重跑：
| 文档 | 涉及内容 |
|---|---|
| `docs/analysis/stop_floor_and_edge_scan_2026-10-19.md` | ladder 出场复刻、离线回测脚本 |
| `docs/analysis/stage_c_2026-10-19.md` | V0/V5/V6/V10 出场阶梯与 32 根上限变体 |
| `docs/analysis/eigenflux_optimization_2026-10-19.md` | TP 阶梯与保本触发实验 |
| `docs/analysis/baseline/2026-10-19/` | 上述文档快照副本 |

> `2026-10-31_to_11-08_loss_attribution.md` 基于 paper 账本（本已 canonical），不受影响。

## 5. 复现旧结论

```python
from src.backtest.lifecycle_exit import AtrTpExitConfig
from src.observability.exit_spec import LEGACY_BACKTEST_EXIT_SPEC
cfg = AtrTpExitConfig.from_spec(LEGACY_BACKTEST_EXIT_SPEC)  # (1.0,2.0,3.0) / 16
```

拿到 `latest_30d` 后按上表重跑并补登差异，届时才能把第 4 节改为 PASS。
