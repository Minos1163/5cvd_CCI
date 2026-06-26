# Fib+PA Entry-Chain Refactor 实现说明

> 日期：2026-06-26  
> 范围：文档侧实现记录，供后续 Claude 评审  
> 安全边界：dry-run only；不触碰 `src/api/binance_client.py`

## 1. 本次实现范围

本次 Fib+PA entry-chain refactor 的目标，是把 dry-run 入场评分从“趋势同意度优先”调整为“位置质量优先”。新增的研究组件为：

| 组件 | 责任 | 预期输出 |
|---|---|---|
| `fib_location` | 识别 1h/15m swing 后的 Fibonacci 回撤区、扩展区、耗竭区 | `fibonacci_location` 分数、Fib 标签、极端扩展 block/cap |
| `pa_structure` | 识别价格行为结构，如 lower-high retest、breakdown retest、无结构追单、反转影线 | `price_action_structure` 分数、结构标签、K 线质量理由 |
| `cci_quality` | 识别 CCI 健康动量、过度延伸、回撤后二次走弱、失败延续 | `cci_momentum_quality` 分数、动量质量标签 |

新增配置采用 opt-in 方式接入，目标配置为：

```text
configs/entry_chain.dry_run_fib_pa_v1.json
```

该配置应显式开启：

```text
use_fib_pa_architecture = true
```

并保留 dry-run 风险边界，例如：

- `disable_probe = true`
- dry-run symbol universe 明确可控
- blacklist / watch-only / observation-only 继续生效
- 不改变 live 下单、撤单、账户、凭证路径

## 2. Component / Entry-Chain / Dry-Run 集成状态

本轮重构按三层接入：

| 层级 | 状态措辞 | 说明 |
|---|---|---|
| Component | 新增 / 正在验证 | `fib_location`、`pa_structure`、`cci_quality` 作为独立可测组件存在，优先通过单元测试验证边界条件。 |
| Entry-chain scoring | 计划接入 / 正在接入 | 新组件应通过 opt-in config 进入 `component_scores` 和动态权重，不影响默认 dry-run/highest-win 架构。 |
| Dry-run integration | 计划接入 / 正在接入 | `scripts/run_live_dry_run.py` 应仅在配置开启 `use_fib_pa_architecture` 时输出 Fib/PA/CCI 分数详情。 |

若代码侧集成尚未完全完成，评审时请按“计划接入/正在接入”理解，不应假设 fib_pa_v1 已替换现有 VPS dry-run 服务配置。

## 3. 研究假设

核心假设：

当前高分亏损主要来自“已经走完一段动量后追入”，而不是 EMA/CVD 方向判断完全错误。Fib 位置和 PA 结构能够降低 late-entry，尤其是：

- 降低 `INITIAL_STOP_HIT` 率。
- 改善 `score >= 90` 桶的胜率。
- 降低 5x 在错误位置放大亏损的概率。
- 让高分重新代表入场质量，而不是仅代表趋势组件一致。

预期适用市场状态：

- 流动性较好的 altcoin 趋势行情。
- 有可识别 pullback / retest / swing 结构。
- EMA/CVD 已提供方向背景，但入场位置仍需二次过滤。

## 4. 失败模式

已知失败模式和评审重点：

| 风险 | 表现 | 需要观察的指标 |
|---|---|---|
| Swing 检测过敏 | 15m 上产生太多噪音 swing，Fib 层位频繁漂移 | trade_count、fib_optimal_win_rate、initial_stop_rate |
| Swing 检测过钝 | 有效 pullback 被漏掉，交易数量过低 | trade_count、exposure、missed setup examples |
| PA 结构标签噪音 | 大阴线 continuation 被误判为有效结构 | pa_structure_win_rate、INITIAL_STOP_HIT 案例复盘 |
| Fib hard block 过严 | 真趋势延续被挡掉 | realized_pnl、TP3 missed cases |
| CCI 过度惩罚极端动量 | 强趋势行情中错过 continuation | win_rate vs trade_count、trend day subset |
| 5x 约束过严 | 杠杆风险下降但收益贡献消失 | `5x_pnl`、5x trade_count |
| 过拟合单窗口 | 只改善 2026-06-25 附近失败簇 | rolling windows、symbol buckets、out-of-sample |

## 5. 验证命令

组件与集成的聚焦验证命令：

```bash
pytest tests/test_fib_location.py tests/test_pa_structure.py tests/test_cci_quality.py tests/test_entry_chain.py tests/test_entry_chain_features.py tests/test_entry_chain_config.py tests/test_dry_run_configs.py tests/test_live_dry_run.py -q
```

dry-run 安全不变量：

```bash
pytest tests/test_live_dry_run.py::test_live_dry_run_source_has_no_exchange_mutation_calls -q
```

确认 Binance client 未被修改：

```bash
git diff -- src/api/binance_client.py
```

dry-run config 健康检查：

```bash
python scripts/vps_dry_run_healthcheck.py --config configs/entry_chain.dry_run_fib_pa_v1.json
```

如需离线对比，应先跑消融实验 A/B/C/D/E，再考虑是否替换 VPS dry-run config。

## 6. 上线限制

本重构当前仅允许：

- dry-run
- synthetic / offline / backtest
- observation and score-detail logging
- opt-in config 验证

明确禁止：

- 不触碰 `src/api/binance_client.py`
- 不改 live 下单、撤单、改单逻辑
- 不改 exchange credential 或账户路径
- 不把 fib_pa_v1 直接切到实盘
- 不在消融实验完成前放宽 5x 约束
- 不把单窗口结果当作可上线结论

上线前最低要求：

- `score_90plus_win_rate` 明显高于当前问题窗口。
- `initial_stop_rate` 下降。
- `5x_pnl` 不再是主要亏损来源。
- PF、max drawdown、trade count、exposure 不出现不可接受退化。
- dry-run 安全测试通过，且 `src/api/binance_client.py` 无 diff。

## 7. 给 Claude 的评审问题

1. 当前 Fib swing 参数是否过敏或过钝？
2. 1h Fib hard block 是否应覆盖 15m 局部结构？
3. CCI exhaustion 应作为纯评分项，还是应成为 action cap？
4. PA minimum 是否应该按 LONG/SHORT 分开设置？
5. 5x 约束是否应在 30 笔 closed trades 前完全禁用？
6. A/B/C/D/E 消融中，是否需要加入 BTC regime filter 的 F 组？
7. 当前 dry-run only 边界是否足够清晰，是否还有 live path 需要额外断言？
