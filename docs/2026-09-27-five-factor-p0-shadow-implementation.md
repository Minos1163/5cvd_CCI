# 五正交因子 P0 影子并轨:实施记录

**日期:** 2026-09-27
**分支:** `09-27-5factor`(基线 `aba3500`)
**依据:** `docs/2026-09-27-five-orthogonal-factor-strategy-decision.md`(裁定报告)
**范围:** 严格 P0 —— 新因子只计算与记录,**不参与任何决策**

---

## 一、交付清单

| # | 内容 | 文件 |
|---|---|---|
| T1 | `BacktestBar` 贯通 `taker_buy_volume` | `src/backtest/engine.py`、`scripts/run_live_dry_run.py::fetch_public_klines` |
| T2-T6 | 五因子 F1-F5 实现 | `src/signals/orthogonal_factors.py` |
| T7 | P0 影子接线 + 只读契约 | `scripts/run_live_dry_run.py`、`src/signals/entry_chain_config.py`、`configs/entry_chain.dry_run_fib_pa_v1.json` |
| T8 | 正交性验收脚本 | `scripts/verify_five_factor_orthogonality.py` |
| — | 单测 | `tests/test_backtest_bar_taker_volume.py`(5)、`tests/test_orthogonal_factors.py`(19)、`tests/test_five_factor_shadow_readonly.py`(8)、`tests/test_verify_five_factor_orthogonality.py`(7) |

## 二、与批准计划的三处偏离(均为实施中发现的事实约束)

### 1. 五因子放入独立模块(计划写的是 `entry_chain_features.py`)

`entry_chain_features.py` 已承担旧体系职责(400+ 行)。五因子是**并行影子体系**,独立成 `src/signals/orthogonal_factors.py` 可避免污染旧命名空间,也便于 P4 阶段整体切换/回滚。函数语义与计划一致。

### 2. F4 回看门槛从 960 根下调到 200 根(**实质修正,影响数据可用性**)

- **发现**:`--public-kline-limit` 默认 **240** → live 实际只拉约 241 根 15m(≈2.5 天),而 F4 原设门槛为 960 根(10 天)→ **F4 将永远回退中性 0.5,影子数据形同虚设**(端到端验证实测 `volatility_fallback: true`);
- **不能提高取数**:增加 15m 历史会改变 `EMA200` 计算 → 间接改变旧评分 → **违反 P0「决策不变」红线**;
- **处理**:按计划"在可得历史内计算分位"的原则,门槛设为 200 根,并在 `meta` 如实记录 `volatility_lookback_bars` 与 `volatility_lookback_days`;
- **残留限制(已记录)**:P0 阶段 F4 的分位窗口约 2.5 天而非设计的 30 天,语义弱于设计。P4 切换评分体系时(EMA 变化已被接受)再解除该限制。

### 3. 配置文件不写注释键

`EntryChainConfig.from_mapping` 对未知键抛错,`_comment_*` 一类注释键会直接导致配置加载失败(已实测)。故配置仅加 `five_factor_shadow_enabled: true`。

## 三、验证证据

| 验证 | 结果 |
|---|---|
| 全量测试 | `python -m pytest tests/ -q` → **723 passed + 1 既有无关失败**(`test_describe_indicator_rules` EMA/RSI 契约漂移,baseline 已知) |
| 新增单测 | 39 项全部通过 |
| 配置审计 | `python scripts/audit_duplicate_json_keys.py` → 全部 `[OK]` |
| 配置加载 | `tests/test_dry_run_configs.py` → 7 passed |
| **端到端落盘** | `run_live_dry_run.py --market-data-source synthetic --once` → `decisions.jsonl` 14/14 行含 `component_points_v2` |
| **只读契约** | 源码级断言:决策层(`entry_chain.py` / `entry_chain_scoring.py` / `entry_chain_gates.py`)不含 `component_points_v2` 与五因子键;影子开启/关闭下 `evaluate_entry_chain` 输出逐字段一致 |
| 验收脚本 | `verify_five_factor_orthogonality.py` 在真实影子数据上端到端跑通(14 样本 → `INSUFFICIENT_SAMPLE`,符合 <10/未达门槛的预期行为) |

**落盘字段实测样例**:

```json
"component_points_v2": {
  "trend_persistence": 12.771, "structure_location": 9.0, "payoff_geometry": 9.0,
  "volatility_regime_score": 10.0, "volatility_regime_leverage_mult": 1.0, "order_flow": 16.72
},
"component_points_v2_meta": {
  "schema_version": "v2-p0-shadow",
  "normalized_values": {"trend_persistence": 0.5805, "structure_location": 0.5,
    "payoff_geometry": 0.5, "volatility_regime": 0.5, "order_flow": 0.76},
  "weights": {"trend_persistence": 22.0, "structure_location": 18.0, "payoff_geometry": 18.0,
    "volatility_regime": 20.0, "order_flow": 22.0},
  "structure_fallback": true, "order_flow_data_gap": false,
  "volatility_fallback": false, "volatility_lookback_bars": 246, "volatility_lookback_days": 2.56,
  "shadow_total": 57.491
}
```

## 四、P0 红线复核(全部保持)

- `total_score` / `component_points` / 象限轴 / `q1_trend_launch` / scout 各通道门槛 / `_select_leverage` **均未改动**;
- 旧六因子与旧函数**全部保留**(P0 是并列,不是替换;回滚只需 `five_factor_shadow_enabled: false`);
- F6(资金费率/OI)**未触碰**;黑名单、单笔风险预算、RR 全局门槛不动;
- F4 的 `volatility_regime_leverage_mult` **只记录不生效**。

## 五、边界与失败处理(按裁定报告 4.6)

退化输入一律回退**中性 0.5**(而非最低分或阻断决策),并由 meta 标记:`structure_fallback` / `order_flow_data_gap` / `volatility_fallback` / `trend_fallback` / `payoff_fallback`。影子计算抛异常时只写 `{"error": ...}` 标记,绝不冒泡影响主决策(呼应 2026-08-13 事故教训)。

F5 数据缺口**明确不零填充** —— 零填充会伪造"无主动买盘"这一比不计分更危险的静默错误(有专门单测锁定)。

## 六、下一步(P1,需积累数据)

1. 影子数据累计 ≥10 笔后,跑 `python scripts/verify_five_factor_orthogonality.py --start <日期> --end <日期>`;
2. 硬指标:两两 |r| ≤ 0.30、Kaiser ≥ 4/5、前 2 PC ≤ 40%、档位 ≥10、零值占比 ≤15%;
3. **首个裁决点**:F2/F3 相关系数 > 0.30 则触发裁定报告第九节的收敛预案(合并为 `STRUCTURE_PAYOFF`,降为 4 因子);
4. 30 天波动率分位的限制在 P4 阶段随评分体系重构一并解除。
