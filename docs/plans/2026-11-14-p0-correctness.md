# 20261114 实施计划：P0 正确性修复（零行为变化优先）

> 依据：《AI300 策略优化评审与实施建议（2026-11-14 评审版）》§14 P0 清单、§16 任务拆分、§17 验收条件。
> 硬约束：**韩国 VPS 上 `/root/AIBOT` 正在跑，用户手动重启。拉取后行为不得突变。**
> 因此本计划把 P0 拆成两类：**A 类零行为变化（本轮上线）**、**B 类有行为变化（本轮只做开关，默认关闭）**。

## 0. 事实基线（已核实）

| 项 | 值 | 证据 |
|---|---|---|
| 当前分支 / HEAD | `20261109-v2` / `f260b1a` | `git log` |
| 生产配置 | `configs/entry_chain.dry_run_regime_shadow.json`（149 键） | 配置读取 |
| `use_fib_pa_architecture` | `True` | 同上 |
| `use_ema_architecture` | **`True`（与上者冲突）** | 同上 |
| `scoring_architecture` | **不存在该字段** | 同上 |
| `dry_run_q1_trend_launch_enabled` | `True`（q1 会替换主决策） | 同上 |
| `risk_first_sizing_enabled` | 缺省 → `False` | 同上 |
| `direct_risk_pct` / `max_single_trade_risk_pct` | 0.006 / 0.0075 | 同上 |
| RR 公式 | `net_tp1_r = 1.2 − 0.001/stop_pct`，值域 [1.000, 1.167] | `entry_chain_features.py:170-180` |
| 仓位公式 | `leveraged_cap = equity×0.0075/(stop_pct×lev)`，除以杠杆 | `entry_chain.py:733-736` |
| run_manifest | 已存在，含 config_sha256 / git commit | `src/observability/run_manifest.py` |
| 全量测试基线 | **988 passed** | 上轮实测 |

## 1. 分层原则

**A 类判据**：改完后，同一根 15m K 线、同一份配置、同一份行情，`action` / `score` / `final_notional` / `leverage` 四个值逐位不变。
**B 类判据**：会改变上述四个值中任意一个 → 只能做成默认关闭的开关，或只写诊断字段。

任何一项无法证明落在 A 类，一律降级为 B 类。

## 2. A 类（本轮上线）

### A1 架构枚举化 + 配置去冲突

- 新增 `scoring_architecture: str = "auto"`（取值 `auto|fib_pa|ema|base`）
- `resolve_architecture` 扩展：`auto` 时按旧布尔开关推断（保持现有行为）；显式值时以它为准
- 两布尔开关同 true 时**仍只告警不抛异常**（历史配置兼容），但新增启动期 `CONFIG_ARCHITECTURE_CONFLICT` 到 manifest
- **生产配置**：`use_ema_architecture` 由 `true` 改为 `false`，并显式写 `scoring_architecture: "fib_pa"`
- **等价性证明**：旧路径两 true → fib_pa；新路径 fib_pa=true、ema=false、explicit=fib_pa → fib_pa。权重表相同。
- 测试：`resolve_architecture` 在 6 种开关组合 + 3 种显式值下的返回值；`dynamic_weights` 权重表逐键相等

### A2 TradeGeometry 统一对象（等价重构）

- 新增 `src/signals/trade_geometry.py`：
  ```
  TradeGeometry(entry_price, side, atr, stop_mult, tp_levels, cost_bps)
    .stop_pct .stop_dist .stop_price
    .tp_prices .gross_r .net_r
  ```
- `risk_reward_geometry_detail` 改为调用它取 `stop_dist`，**保留当前 clamp 与评分阈值不变**
- 新增诊断字段（不参与打分）：
  - `geometry_version`
  - `net_tp1_r_at_20bps` = `1.2 − 0.002/stop_pct`（正确往返成本）
  - `cost_bps_used` = 10（当前实际）与 `cost_bps_ledger` = 20 的对照
- 测试：`stop_pct ∈ {0.5, 1.0, 2.0, 3.0}%` 下 geometry 与实际交易止损一致；LONG/SHORT 镜像

### A3 RR 可达性锁死

- 新增测试 `test_rr_bands.py`：在当前公式下，`net_tp1_r >= 1.3` 在整个合法 stop 区间**不可达**，`>= 1.1` 仅在 `stop_pct <= 1.0%` 可达
- 决策 payload 新增 `rr_band` 字段（`GE_1_3 / GE_1_1 / GE_0_9 / LT_0_9`）
- 目的：把"满分不可达"变成**会红的测试**，而不是文档里的一句话

### A4 风险反算与 shadow 诊断

- `sizing_trace` 新增：
  - `expected_stop_loss` = `final_notional × stop_pct`
  - `risk_budget_pct_configured`（action 对应 risk_pct）
  - `risk_budget_pct_effective` = `expected_stop_loss / equity`
  - `risk_first_shadow_notional`（用 `risk_budget / stop_pct` 算一遍，只记录）
- 零行为变化：不改 `final_notional`

### A5 q1 通道 shadow 开关（默认关闭）

- 新增配置 `q1_trend_launch_shadow_only: bool = False`
- 为 `False` 时行为**与现在逐位一致**
- 为 `True` 时：q1 决策写入 `shadow_decision`，主决策不被替换，`decision_origin` 仍为 `primary`
- 测试：开关为 False 时事件序列与当前一致；为 True 时主决策 hash 不变

### A6 账本标识

- 每笔 PAPER_OPEN/CLOSE 事件新增 `ledger_id`（`main` / `ab_legacy` / `ab_trend_capture` / `ab_pure_ladder` / `scout_micro`）
- 纯新增字段，读取侧无影响

### A7 报告口径守卫

- 新增测试：`report_strategy_review.py` 与 `ledger_metrics.py` 源码中不得出现 `margin_pnl`（防回退）
- 已有 `net_pnl_full` 口径不动

## 3. B 类（本轮只记录，不启用）

| 项 | 为什么不做 | 以什么形式留痕 |
|---|---|---|
| RR 公式真正改为 20bps 并重设阈值 | 会改 score → 改 action → 改交易 | `net_tp1_r_at_20bps` 诊断字段 + 文档 |
| CVD 连续化 / 真实 taker flow 接入 | 会改 18% 权重 → 改全部分数 | 不动 |
| 杠杆公式切换为风险优先 | 会改 notional → 改风险 | `risk_first_shadow_notional` 只记录 |
| q1 通道默认改 shadow | 会改主账本样本构成 | 开关存在，默认关闭 |
| 六因子权重重拟合 | 16 笔无功效 | 不动 |

## 4. 验收

1. 全量 `pytest` 全绿（基线 988 + 新增）
2. **等价性证明**：同一批 `decisions.jsonl`（`logs/2026-11/2026-11-13`）在改动前后，用同一份配置重放，`action` / `score` / `notional` / `leverage` 四列逐行相同
3. `git diff --stat` 不得触碰 `src/api/binance_client.py`
4. 生产配置只改 `use_ema_architecture` 一个布尔 + 新增 `scoring_architecture` 一个键
5. 部署单元不变（`deploy/systemd/ai300-dry-run.service` 零改动）

## 5. 交付与上线

- 分支 `20261114`，推送 `origin`
- 韩国 VPS：`/root/AIBOT`，`git fetch` + 快进 + `systemctl restart`
- 回滚：记录拉取前 HEAD，`git reset --hard <old>` + 重启
