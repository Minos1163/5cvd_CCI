# Fib+PA 消融实验模板

> 日期：2026-06-26  
> 用途：A/B/C/D/E 对比实验记录模板，供后续 Claude 评审  
> 原则：单变量推进；先验证 entry quality，再讨论 5x 放大

## 1. 实验组定义

| 实验 | 名称 | 配置 / 架构 | 目的 | 备注 |
|---|---|---|---|---|
| A | baseline | 当前 dry-run baseline / highest-win config | 建立对照组，确认原始 score 与 PnL 分布 | 不引入 Fib/PA/CCI 新逻辑 |
| B | EMA+CVD+CCI | EMA + CVD + CCI + RR | 验证 CCI 动量质量是否改善追单问题 | 不接 PA，不接 Fib |
| C | +PA | EMA + CVD + CCI + PA + RR | 衡量 PA 结构对 late-entry 和 initial stop 的影响 | 重点看 `pa_structure_win_rate` |
| D | +Fib | EMA + CVD + CCI + PA + Fib + RR | 验证完整位置优先架构 | 重点看 `fib_optimal_win_rate` 与 90+ 胜率 |
| E | +5x constrained | D + 5x constrained | 验证 Fib/PA/CCI/RR 约束能否修复 5x 亏损来源 | 5x 需要额外门槛，不允许 score-only 触发 |

建议 run id：

```text
fib_pa_refactor_exp_a_baseline
fib_pa_refactor_exp_b_ema_cvd_cci
fib_pa_refactor_exp_c_add_pa
fib_pa_refactor_exp_d_add_fib
fib_pa_refactor_exp_e_5x_constrained
```

## 2. 统一实验假设

| 实验 | 假设 | 主要失败模式 |
|---|---|---|
| A | 原 baseline 作为对照，预期暴露 90+ 分和 5x 的亏损问题 | 若 A 表现显著好于问题窗口，需要检查样本窗口是否不可比 |
| B | CCI 可识别过度延伸，降低部分追空/追多 | CCI 单独不足以识别结构位置 |
| C | PA 能过滤无结构追单，降低 initial stop | PA 标签噪音导致 trade_count 降低或误杀 continuation |
| D | Fib 能识别回撤/扩展位置，使高分更接近高质量入场 | Fib swing 参数过拟合或 hard block 过严 |
| E | 5x 只在 Fib/PA/CCI/RR 同时合格时启用，降低杠杆亏损 | 5x 交易数过低，收益贡献不足 |

## 3. 指标表格模板

| Experiment | Config / Run ID | win_rate | PF | realized_pnl | max_drawdown | trade_count | initial_stop_rate | breakeven_stop_rate | tp3_rate | 5x_pnl | score_90plus_win_rate | fib_optimal_win_rate | pa_structure_win_rate |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A baseline | `fib_pa_refactor_exp_a_baseline` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | N/A | N/A |
| B EMA+CVD+CCI | `fib_pa_refactor_exp_b_ema_cvd_cci` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | N/A | N/A |
| C +PA | `fib_pa_refactor_exp_c_add_pa` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | N/A | TBD |
| D +Fib | `fib_pa_refactor_exp_d_add_fib` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
| E +5x constrained | `fib_pa_refactor_exp_e_5x_constrained` | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

## 4. 分桶分析模板

### 4.1 Score 分桶

| Experiment | score_bin | trade_count | win_rate | PF | realized_pnl | initial_stop_rate |
|---|---|---:|---:|---:|---:|---:|
| A | 82-85 | TBD | TBD | TBD | TBD | TBD |
| A | 85-90 | TBD | TBD | TBD | TBD | TBD |
| A | 90+ | TBD | TBD | TBD | TBD | TBD |
| B | 82-85 | TBD | TBD | TBD | TBD | TBD |
| B | 85-90 | TBD | TBD | TBD | TBD | TBD |
| B | 90+ | TBD | TBD | TBD | TBD | TBD |
| C | 82-85 | TBD | TBD | TBD | TBD | TBD |
| C | 85-90 | TBD | TBD | TBD | TBD | TBD |
| C | 90+ | TBD | TBD | TBD | TBD | TBD |
| D | 82-85 | TBD | TBD | TBD | TBD | TBD |
| D | 85-90 | TBD | TBD | TBD | TBD | TBD |
| D | 90+ | TBD | TBD | TBD | TBD | TBD |
| E | 82-85 | TBD | TBD | TBD | TBD | TBD |
| E | 85-90 | TBD | TBD | TBD | TBD | TBD |
| E | 90+ | TBD | TBD | TBD | TBD | TBD |

### 4.2 杠杆分桶

| Experiment | leverage | trade_count | win_rate | PF | realized_pnl | initial_stop_rate |
|---|---:|---:|---:|---:|---:|---:|
| A | 3x | TBD | TBD | TBD | TBD | TBD |
| A | 4x | TBD | TBD | TBD | TBD | TBD |
| A | 5x | TBD | TBD | TBD | TBD | TBD |
| B | 3x | TBD | TBD | TBD | TBD | TBD |
| B | 4x | TBD | TBD | TBD | TBD | TBD |
| B | 5x | TBD | TBD | TBD | TBD | TBD |
| C | 3x | TBD | TBD | TBD | TBD | TBD |
| C | 4x | TBD | TBD | TBD | TBD | TBD |
| C | 5x | TBD | TBD | TBD | TBD | TBD |
| D | 3x | TBD | TBD | TBD | TBD | TBD |
| D | 4x | TBD | TBD | TBD | TBD | TBD |
| D | 5x | TBD | TBD | TBD | TBD | TBD |
| E | 3x | TBD | TBD | TBD | TBD | TBD |
| E | 4x | TBD | TBD | TBD | TBD | TBD |
| E | 5x | TBD | TBD | TBD | TBD | TBD |

## 5. 必填记录项

每个实验至少记录：

- `win_rate`
- `PF`
- `realized_pnl`
- `max_drawdown`
- `trade_count`
- `initial_stop_rate`
- `breakeven_stop_rate`
- `tp3_rate`
- `5x_pnl`
- `score_90plus_win_rate`
- `fib_optimal_win_rate`
- `pa_structure_win_rate`

建议额外记录：

- exposure / time in market
- expectancy
- average win / average loss
- tail loss
- MFE / MAE
- symbol bucket PnL
- LONG / SHORT split
- 90+ 分亏损样本截图或 candle context

## 6. 验收阈值草案

| 指标 | 最低要求 | 说明 |
|---|---:|---|
| `score_90plus_win_rate` | > 60% | 高分必须重新具备预测意义 |
| `PF` | > 1.2 | 最低可行门槛，不代表可上线 |
| `initial_stop_rate` | < 40% | 本次重构首要目标之一 |
| `5x_pnl` | > 0 | 5x 不应继续成为主要亏损来源 |
| `trade_count` | 不低于 baseline 的可解释范围 | 防止靠过度过滤制造虚假胜率 |
| `max_drawdown` | 不高于 baseline | 若收益改善但回撤扩大，需要单独评审 |

## 7. 评审结论模板

```text
结论日期：
评审人：
样本窗口：
数据源：

最佳实验：
是否优于 baseline：
是否满足 dry-run only 安全边界：

主要改善：
- 

主要退化：
- 

是否建议进入 VPS dry-run opt-in 观察：
是否允许放宽 5x：
是否需要新增 F 组 BTC regime filter：

未解决问题：
- 
```
