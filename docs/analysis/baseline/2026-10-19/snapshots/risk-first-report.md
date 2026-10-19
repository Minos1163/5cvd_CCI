# 风险优先 vs 旧口径:反事实回放

- 窗口:2026-08,2026-09,2026-10
- 配置:configs/entry_chain.dry_run_fib_pa_v1.json(risk_first 仅切换 `risk_first_sizing_enabled`)
- 回放口径:真实入场意图 + barrier 标注(32 根 / 20bps / next_open),权益按单笔风险复利

| 指标 | 旧口径 | 风险优先 |
|---|---:|---:|
| 入场意图数 | 172 | 172 |
| 单笔风险 中位数 | 0.1500% | 0.1500% |
| 单笔风险 P90 | 0.1875% | 0.2595% |
| 单笔风险 最大值 | 0.1875% | 0.5854% |
| 名义 中位数 | 1401 | 1670 |
| ΣR_net | -53.65 | -53.65 |
| 期末权益 | 9299 | 9182 |
| 区间收益 | -7.01% | -8.18% |
| 最大回撤 | -7.01% | -8.18% |

- 单笔风险倍数(中位数):**1.0×**
- 回撤倍数:**1.1668×**(回撤为负,倍数取绝对值)
- 旧口径 binding caps:{'raw_notional': 91, 'remaining_exposure_notional': 47, 'leveraged_cap_notional': 34}
- 风险优先 binding caps:{'raw_notional': 91, 'remaining_exposure_notional': 81}

**判定**:`risk_increase_small`

> 这份回放**不能**回答「换仓控后是否更赚钱」——入场集与 R 都相同,只放大/缩小了每笔的权益暴露。它只用于判断 3.2 倍风险放大是否可接受;收益结论必须来自 paper 并行或独立回测。
