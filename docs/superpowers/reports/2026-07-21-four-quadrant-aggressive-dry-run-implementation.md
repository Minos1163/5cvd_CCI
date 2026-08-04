# AI300 四象限激进 Dry-Run 实验框架实施报告

**实施日期:** 2026-07-21  
**范围:** 仅 dry-run / paper ledger / SCOUT / mirror A-B；未修改交易所 mutation 路径。  
**配置:** `configs/entry_chain.dry_run_fib_pa_v1.json`

---

## 已落实内容

### 1. 主账本 Q1 绿色通道

- `dry_run_q1_green_channel_enabled=true` 已开启。
- 新增实际转换逻辑：符合条件的 Q1 near-miss 会被转换为 dry-run paper `PROBE`。
- 准入条件：
  - `quadrant=Q1`
  - `score >= 85`
  - `price_action_structure >= 18`
  - `flow_cvd_confirmation >= 16`
  - 原拒绝原因包含 `_BELOW_RISK_REWARD_GEOMETRY`
  - 非黑名单标的
  - `data_health=OK`
- 仓位：
  - `notional = initial_equity * 0.05 * max(0.25, risk_reward_geometry / 8.0)`
  - active 配置中 `dry_run_q1_green_channel_notional_mult=1.0`
- 标签：
  - `experiment_id=four_quadrant_aggressive_v1`
  - `entry_channel=q1_green_channel`
  - `source_quadrant=Q1`
  - `exit_mode=trend_capture`
- 转换后仍经过 `apply_dry_run_decision_controls()`，继续受冷却、组合熔断、日亏损等 dry-run 风控约束。

### 2. 四象限 SCOUT 火力侦察

- `Q1_RR_GAP_SCOUT` 保留并加严：新增 `flow_cvd_confirmation >= 16`。
- 新增 `Q2_PENDING_MOMENTUM`：
  - Q2、`score>=85`、`PA>=18` 进入 pending。
  - 6 根 15m K 内转 Q1 且 `CCI>=9` 后确认开 SCOUT。
- `Q3_TO_Q1_CONFIRMATION` 保留。
- pending 状态持久化到 `quadrant_pending.json`，避免 VPS 重启丢失。
- SCOUT payload 增加 `experiment_id`、`entry_channel`、`source_quadrant`。

### 3. Mirror A/B 扩采样

- `mirror_ab_min_score` 从 85 降为 82。
- 新增 `mirror_ab_include_q1_watch=true`。
- mirror A/B 现在支持：
  - 原 allowed reason 采样；
  - Q1 WATCH 样本采样。
- mirror payload 增加：
  - `experiment_id=four_quadrant_aggressive_v1`
  - `entry_channel=mirror_ab_sample`
  - `source_quadrant`

### 4. 象限感知持仓保护

- `PaperPosition` 新增：
  - `experiment_id`
  - `entry_channel`
  - `source_quadrant`
  - `q4_streak`
- 仅实验仓位启用 Q4 防御退出：
  - 连续 2 根已处理 K 线为 Q4；
  - 当前剩余仓位按收盘价估算为浮亏；
  - 未先触发初始止损；
  - 则以 `Q4_DEFENSIVE_EXIT` 关闭。
- 普通非实验仓位不受 Q4 规则影响。

### 5. 实验预算熔断

- 新增实验入口熔断：
  - `experiment_war_fund_loss_limit=-150`
  - `experiment_daily_loss_limit=-200`
- 熔断依据为账本事件中 `experiment_id=four_quadrant_aggressive_v1` 的累计 PnL。
- 熔断触发后：
  - 禁止新增 Q1 绿色通道；
  - 禁止新增 SCOUT 实验；
  - 禁止新增 mirror A/B 样本；
  - 已有仓位仍继续更新和平仓。

---

## 修改文件

| 文件 | 变更 |
|---|---|
| `src/signals/entry_chain_config.py` | 新增四象限实验配置字段 |
| `configs/entry_chain.dry_run_fib_pa_v1.json` | 开启 Q1 绿色通道、Q2 pending、A/B 扩采样、实验预算 |
| `scripts/run_live_dry_run.py` | 接入 Q1 绿色通道、Q2/Q3 pending 持久化、SCOUT/A-B 路由、预算熔断 |
| `src/observability/paper_trading.py` | 增加实验元数据、per-position exit mode、Q4 防御退出 |
| `tests/test_entry_chain_config.py` | 配置字段覆盖 |
| `tests/test_dry_run_configs.py` | active dry-run 配置覆盖 |
| `tests/test_live_dry_run.py` | 绿色通道、pending、SCOUT/A-B、预算熔断覆盖 |
| `tests/test_paper_trading.py` | 实验元数据和 Q4 退出覆盖 |

---

## 验证结果

已运行：

```powershell
pytest tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py tests/test_paper_trading.py -q
```

结果：

```text
106 passed in 8.30s
```

已运行 active 配置冒烟：

```powershell
python scripts/run_live_dry_run.py --config configs/entry_chain.dry_run_fib_pa_v1.json --once --output-dir <temp> --symbols SOLUSDT --market-data-source synthetic
```

结果：

```json
{"status": "dry_run_completed", "orders_submitted": 0}
```

冒烟输出确认 `summary.json` 包含：

- `dry_run_q1_green_channel_enabled=true`
- `mirror_ab_min_score=82.0`
- `mirror_ab_include_q1_watch=true`
- `quadrant_pending_state_enabled=true`
- `experiment_war_fund_loss_limit=-150.0`

---

## VPS 替换注意

1. 这是 dry-run/paper 实验改动，仍然没有提交真实交易订单。
2. 替换 VPS 脚本时至少同步：
   - `scripts/run_live_dry_run.py`
   - `src/signals/entry_chain_config.py`
   - `src/observability/paper_trading.py`
   - `configs/entry_chain.dry_run_fib_pa_v1.json`
3. 若 VPS 使用 persistent paper state，新增文件 `quadrant_pending.json` 会在 state dir 自动生成。
4. 下一次日志评审应重点看：
   - 主账本 `PAPER_OPEN` 是否出现 `entry_channel=q1_green_channel`
   - SCOUT 是否出现 `Q2_PENDING_MOMENTUM`
   - A/B 样本是否明显增加且带 `source_quadrant`
   - 是否出现 `Q4_DEFENSIVE_EXIT`
   - 实验累计亏损是否接近 `-150 USDT`
