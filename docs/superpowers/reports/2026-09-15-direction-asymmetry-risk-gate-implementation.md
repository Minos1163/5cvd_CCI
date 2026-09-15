# 方向非对称与单笔风险硬上限实施记录

日期：2026-09-15

窗口：2026-08-24 重启后至 2026-09-15

## 1. 实施边界

本次进入主链的改动只有两类：

1. 单笔杠杆后风险上限：`max_single_trade_risk_pct=0.0075`，即账户权益的 0.75%。
2. Q1 专用入口的标的政策统一：blacklist、watch-only、observation-only 均拒绝进入 Q1 trend-launch/green-channel。

以下内容保持 shadow-only，没有改变主链 action、下单、账本或杠杆选择：

- bullish regime 下 SHORT offset/gate；
- 4x 质量门；
- Q1 SHORT 的 reversal confirmation 观测。

`short_threshold_offset=0.0` 和 `_select_leverage()` 的 4x 档位没有被修改。

## 2. 单笔风险 cap

最终名义规模现在按实际选定杠杆计算：

```text
raw_notional = equity * risk_pct / stop_pct
leveraged_cap = equity * 0.0075 / (stop_pct * selected_leverage)
final_notional = min(raw_notional, leveraged_cap, remaining_symbol_exposure)
```

`evaluate_entry_chain()` 将同一个 selected leverage 传入 notional 计算和 decision；`_decision()` 对外部传入的 notional hint 再做一次 cap，覆盖 Q1 等自定义入口。决策 metadata 增加：

- `selected_leverage`
- `stop_pct`
- `raw_notional`
- `leveraged_cap_notional`
- `remaining_exposure_notional`
- `final_notional`
- `binding_cap`

Q1 自定义 notional 也会复用中央 `_notional_cap_diagnostics`，并使用当前 `EntryChainContext` 的 equity、stop 和 symbol exposure。兼容性 fallback 使用 paper ledger 当前 summary/snapshot，而不是固定初始权益。

## 3. Q1 标的政策

Q1 eligibility 现在使用统一顺序记录拒绝原因：

```text
Q1_SYMBOL_BLACKLISTED
Q1_SYMBOL_WATCH_ONLY
Q1_SYMBOL_OBSERVATION_ONLY
```

策略拒绝只追加审计 reason，不把普通 `NO_TRADE` 改写成 `WATCH`，也不改变普通 DIRECT/PROBE/WATCH 语义。

数值字段对 `bad`、`NaN`、`Inf` fail-closed；极值比例保留原有“字段缺失/非数值回退 0.5”的历史兼容语义。

## 4. Shadow 结果

shadow 脚本要求 decision 记录的 15m K 线已经完成：decision timestamp 至少晚于 candle timestamp 900 秒。它只使用已记录的当前/已完成 candle 字段，不使用未来 candle，也不假设同 K 线成交。

本次日志中 `market_snapshot` 没有 breadth 5h/6h 字段，因此没有任何 `BULLISH_CONFIRMED` 样本。结果只能作为时间窗 proxy，不能作为 breadth 已确认的结论：

| 项目 | 结果 |
|---|---:|
| 完成的 15m candle | 29,592 |
| breadth confirmed | 0 |
| breadth 缺失的时间窗 proxy | 29,592 |
| Q1 SHORT 可执行 proxy 候选（score >= 80） | 36 |
| shadow offset 5 拦截 | 23 / 36 |
| shadow offset 10 拦截 | 34 / 36 |

shadow 记录了 `reversal_confirmation_score`，该分数由已记录的 PA、CVD、CCI component points 归一化得到，仅用于观测，未作为 live 阻断条件。

## 5. 4x SHORT/Q1 只读交叉审计

审计只统计最终 `PAPER_CLOSE`，排除中间 `PAPER_REDUCE`，并同时报告名义和杠杆后 PnL：

| 范围 | 笔数 | 名义 PnL | 杠杆后 PnL |
|---|---:|---:|---:|
| 4x SHORT 总计 | 7 | -104.3417 | -417.3670 |
| 其中 Q1 | 6 | -78.7765 | -315.1060 |
| 其中 Q3 | 1 | -25.5652 | -102.2610 |

按 symbol 的杠杆后 PnL：SOL `-200.7945`、BCH `-101.8570`、LINK `-74.8856`、DOGE `-39.8298`。入口通道分布为 `UNKNOWN` 5 笔、`main_direct` 2 笔；历史日志中 5 笔没有可靠的显式 channel 字段，因此没有强行推断具体入口。

风险 cap 对比字段已加入审计，但当前历史交易产生于 cap 部署前，匹配到的 `risk_budget` metadata 为 0 笔；不能用新 cap 的理论值冒充历史实际执行结果。

## 6. 验证

通过：

- Q1、dry-run 相关测试：`121 passed`；
- Task 3 shadow/审计/4x gate 测试：`16 passed`；
- shadow 实际日志运行成功；
- 4x SHORT/Q1 实际日志审计成功；
- 所有改动保持 dry-run/offline，不发起真实交易所请求。

仍需在后续窗口验证：

- 新日志是否开始写入 breadth 5h/6h，使 `BULLISH_CONFIRMED` 真正有样本；
- 新 cap 是否把 4x 单笔杠杆后风险限制在权益 0.75%；
- Q1 SHORT shadow 拦截样本的反事实 PnL，而不是只看拦截率；
- `entry_channel` 是否在所有主账本开仓中稳定落盘。

## 7. DeepSeek 评审重点

1. 0.75% 是按止损距离估算的杠杆后单笔风险，是否需要与组合 beta/相关性 cap 叠加。
2. Q1 SHORT gate 是否应只作用于 `BULLISH_CONFIRMED`，以及 breadth 缺失时应 fail-open 还是 fail-closed。
3. reversal confirmation 的 PA/CVD/CCI 组合是否有独立增量信息，是否需要改成 shadow-only 的统计字段而非分数。
4. Q1 专用入口使用 PROBE 风险率和 leverage=1 是否符合实验通道定位，是否应保留更低固定风险。
5. 历史 `UNKNOWN` entry_channel 是否需要通过 entry/open 关联进一步回填，避免把数据缺失误判为策略通道差异。

本记录不宣称 shadow 已证明策略有效；它只固化了主链风险修复、可重复的离线审计和下一轮评审所需的证据字段。
