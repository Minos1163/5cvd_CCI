# 08-24 重启至 09-15: 开仓少但亏损审计

**提交对象:** DEEPSEEK 评审
**报告性质:** 日志审计与策略研究，不是代码变更，也不是上线批准
**运行形态:** dry-run / paper ledger；本窗口 `orders_submitted=0`，没有真实交易所下单
**分析窗口:** `2026-08-24 14:00 UTC` 至 `2026-09-15` 最新日志

## 1. 结论摘要

本窗口的问题不是单纯的“信号太少”，而是三个问题叠加：

1. **开仓数量少且方向严重偏空。** 28,920 条决策中只有 53 条进入 `PROBE/DIRECT`，最终主账本开仓 50 笔；LONG 11 笔，SHORT 39 笔。已完成交易 50 笔，11 胜 39 负，胜率约 22%，名义 `position_realized_pnl` 为 `-91.4051`。
2. **牛市期间的“Q1”不是市场牛市象限。** Q1 只是单币种的 EMA/PA 与 CVD/CCI 两条轴同时达标，未检查 BTC、breadth 或跨品种市场 regime。因此局部回调可以被识别成高分 SHORT。Q1 开仓 42 笔，其中 SHORT 31 笔，Q1 合计名义 PnL `-76.7347`。
3. **少量 4x 主链仓位放大了损失。** 4x 只有 5 笔，但名义 PnL `-61.7293`；按 `position_realized_pnl * leverage` 的杠杆后口径为 `-246.9173`。其中两笔 SOL SHORT 和两笔 LINK SHORT 是主要尾部损失。当前总敞口上限并没有形成有效的单笔风险上限。

最重要的判断是：**当前评分链在测量“局部状态质量”，没有测量“方向是否符合市场 regime”与“入场是否得到行为确认”。** 先改方向门控、通道统一风控和单笔风险，再讨论替换 CCI；不建议仅继续调总分阈值。

## 2. 时间边界与数据口径

### 2.1 重启边界

实际重启日志显示：

```text
process_start: 2026-08-24 13:57:05 UTC
first_scan:    2026-08-24 14:00:05 UTC
```

另一次进程启动为 `2026-08-24 14:42:29 UTC`，首轮扫描为 `14:45:05 UTC`。因此本文从首轮有效扫描 `14:00 UTC` 开始，不把重启前残留决策混入窗口。

### 2.2 统计定义

- 决策统计来自每日日志的 `decisions.jsonl`。
- 主账本交易来自 `paper_trades.jsonl`，只统计窗口内的 `PAPER_OPEN`、`PAPER_CLOSE` 和对应 `REDUCE` 事件。
- “名义 PnL”使用平仓事件的 `position_realized_pnl`，该字段已经包含开仓成本影响。
- “杠杆后 PnL”使用 `position_realized_pnl * leverage`，用于比较保证金账户风险放大；它与日志中的 `margin_pnl` 可能不同，因为 `margin_pnl` 按净 PnL 和费用/滑点记录。
- 一笔交易按最终 `PAPER_CLOSE` 计数；部分止盈或减仓不重复计为新交易。
- 这是 paper/dry-run 结果，不应当被表述为真实成交收益。

## 3. 窗口总体结果

### 3.1 决策到成交的漏斗

| 层级 | 数量 | 占比/说明 |
|---|---:|---|
| 决策记录 | 28,920 | 每 15m 扫描，多币种累积 |
| `NO_TRADE` | 25,809 | 主要状态 |
| `WATCH` | 3,058 | 有观察价值但不可开仓 |
| `PROBE` | 47 | 原始可执行决策 |
| `DIRECT` | 6 | 原始可执行决策 |
| 主账本实际开仓 | 50 | 11 LONG / 39 SHORT |
| 主账本实际平仓 | 50 | 50 笔均已结束 |
| 减仓事件 | 24 | 不等同于 24 笔新交易 |

### 3.2 盈亏与方向

| 方向 | 笔数 | 胜/负 | 胜率 | 名义 PnL | 杠杆后 PnL |
|---|---:|---:|---:|---:|---:|
| LONG | 11 | 3 / 8 | 27.3% | -10.4752 | -36.4457 |
| SHORT | 39 | 8 / 31 | 20.5% | -80.9299 | -257.8773 |
| 合计 | 50 | 11 / 39 | 22.0% | **-91.4051** | **-294.3230** |

SHORT 占开仓数 78%，贡献约 88.5% 的名义亏损。该结果不是“LONG 没有机会”的证据，而是当前 LONG 侧门槛和 SHORT 侧门槛不对称的直接结果。

### 3.3 象限统计

决策象限分布：

| 象限 | 决策数 | 实际开仓 | 已平仓 | 胜/负 | 名义 PnL | 杠杆后 PnL |
|---|---:|---:|---:|---:|---:|---:|
| Q1 | 3,046 | 42 | 42 | 8 / 34 | **-76.7347** | **-253.0952** |
| Q2 | 3,977 | 1 | 1 | 0 / 1 | -5.8635 | -17.5904 |
| Q3 | 5,696 | 7 | 7 | 3 / 4 | -8.8070 | -23.6375 |
| Q4 | 16,201 | 0 | 0 | - | 0 | 0 |

Q1 实际开仓按方向拆分为：LONG 11 笔，名义 PnL `-10.4752`；SHORT 31 笔，名义 PnL `-66.2595`。所以 Q1 的主要问题不是“Q1 不够进攻”，而是它把局部 SHORT 状态误当成了可以在上涨市场中执行的趋势信号。

## 4. 开仓少但亏损的根因

### 4.1 开仓少的原因

#### 原因 A: LONG 有额外门槛，SHORT 没有对称门槛

实际配置为：

```json
"direct_threshold": 82.0,
"probe_threshold": 70.0,
"watch_threshold": 62.0,
"long_threshold_offset": 10.0,
"short_threshold_offset": 0.0
```

`PROBE` 条件又单独使用 `long_threshold_offset=7.0`、`short_threshold_offset=0.0`。因此同样的分数：

- LONG 的 DIRECT 要达到 92，WATCH 要达到 72；LONG PROBE 至少相当于 77 的分数门槛。
- SHORT 仍按 82/70/62 走。

日志中大量出现 `SIDE_THRESHOLD_OFFSET_LONG_10.00`，而 SHORT 没有对应的额外门槛。上涨行情中，回调通常先表现为局部 1h 下跌，系统便更容易形成 SHORT；真正的 LONG 还要经过更高门槛、追高保护和 Fibonacci exhaustion 约束。

#### 原因 B: FIB-PA 评分没有真正使用 4h/regime

配置启用 `use_fib_pa_architecture=true` 后，最终权重为六个 FIB-PA 组件。虽然代码仍计算 `background_4h`、`market_regime` 等字段，但 `dynamic_weights()` 直接返回 FIB-PA 权重，4h 背景和市场 regime 不进入最终总分。

这意味着当前总分可以回答“这个币种当前局部结构是否像一个 SHORT”，但不能回答“全市场是否正在上涨，SHORT 是否只是逆势回调”。

#### 原因 C: 方向判定只看单币种最近四根 1h K 线

当前 `direction_from_history()` 的核心规则是：

```text
最近 1h 收盘价相对四根之前上涨超过 0.3% -> LONG
下跌超过 0.3% -> SHORT
否则 NONE，再回退到 15m 方向
```

这是局部方向，不是市场状态。上涨行情中的币种轮动、短线回调、影线和不同币种节奏都会被独立解释成 SHORT。

#### 原因 D: Q4 过滤有效，但没有把剩余 Q1/Q2/Q3 变成可交易方向

Q4 没有开仓，说明轴门控确实减少了噪声；但 Q1/Q2/Q3 只描述组件组合，不描述市场 regime，也没有要求 SHORT 必须有反转证据。因此开仓数量少并没有换来正期望，剩下的少量交易仍可能集中在错误方向。

### 4.2 亏损的原因

#### 原因 A: Q1 放行了大量逆势 SHORT

Q1 定义为：趋势结构轴和流动量能轴同时通过。这里的“趋势”是对当前 `side` 的条件评分；当 `side=SHORT` 时，EMA/PA 也可能是看空结构。Q1 并不等于 bullish regime，也不等于 LONG。

窗口内 Q1 SHORT 31 笔，只有 5 笔盈利，名义 PnL `-66.2595`。这说明单纯提高 Q1 总分并不能解决问题，因为错误方向的局部结构也可以取得高分。

#### 原因 B: Q1 专用通道没有继承全部标的政策

`_q1_trend_launch_eligible()` 的显式检查包含黑名单，但没有检查 `watch_only_symbols`。窗口内 `q1_trend_launch` 实际开仓 29 笔，其中：

| 标的 | 开仓数 |
|---|---:|
| ADAUSDT（watch-only） | 7 |
| XMRUSDT（watch-only） | 6 |
| 其他 | 16 |

该通道的 29 笔交易只有 5 笔盈利，名义 PnL `-6.6365`。虽然该通道使用 1x 小仓，损失较小，但它破坏了“watch-only 是硬政策”的一致性，也会污染后续策略评估。

#### 原因 C: 高杠杆默认值与单笔风险不匹配

普通主链中，`_select_leverage()` 的实际逻辑是：

- rolling Sharpe 为负时上限 2x；
- ATR > 3% 时 3x；
- ATR > 1.5% 时 DIRECT 4x、PROBE 3x；
- 否则 DIRECT 默认 4x、PROBE 默认 3x；
- 只有分数 >= 90 且满足额外组件门槛时才可能 5x。

这使得分数刚过门槛的 DIRECT 仍可能使用 4x。窗口内 4x 的 5 笔交易杠杆后 PnL 为 `-246.9173`，而 1x 的 29 笔仅为 `-6.6365`。风险预算实际上被“杠杆选择”主导，而不是由每笔最大可承受损失主导。

#### 原因 D: 入场质量问题先于出场问题

50 笔已平仓中有 39 笔 `max_favorable_r_observed < 1R`。主要负向退出为：

| 退出原因 | 笔数 | 名义 PnL |
|---|---:|---:|
| `INITIAL_STOP_HIT` | 25 | -108.3358 |
| `COST_BREAKEVEN_TIMEOUT` | 5 | -26.2577 |
| `Q4_DEFENSIVE_EXIT` | 9 | -5.2696 |
| `BREAKEVEN_STOP_HIT` | 11 | +48.4579 |

这不是“止盈太早”能解释的样本：多数交易入场后没有先走出 1R，说明信号方向、入场位置或行为确认不足。调整 trailing 或 TP 不能替代入口质量修复。

#### 原因 E: 少量尾部交易抵消了大量小仓交易

按 `position_realized_pnl * leverage` 排序的主要损失为：

| 标的/方向 | 象限 | 通道 | 杠杆 | 名义 PnL | 杠杆后 PnL | 退出 |
|---|---|---|---:|---:|---:|---|
| SOL SHORT | Q3 | `main_direct` | 4x | -25.5652 | -102.2610 | INITIAL_STOP_HIT |
| SOL SHORT | Q1 | 历史通道缺失 | 4x | -24.6334 | -98.5335 | INITIAL_STOP_HIT |
| LINK SHORT | Q1 | `main_direct` | 4x | -11.3753 | -45.5014 | COST_BREAKEVEN_TIMEOUT |
| LINK SHORT | Q1 | 历史通道缺失 | 4x | -7.3461 | -29.3842 | COST_BREAKEVEN_TIMEOUT |

普通主链 `main_direct` 只有 2 笔，但杠杆后 PnL 为 `-147.7624`。因此本窗口不能用平均每笔交易来掩盖尾部风险。

## 5. 当前实盘同构开仓链路

下面描述的是当前 dry-run/paper 与预期实盘共用的决策链路；本窗口未向交易所提交订单。

```text
15m K 线收盘
  -> 等待 post-close delay 5s，避免读取未完成 K 线
  -> 拉取/更新 15m、30m、1h、4h 历史，15m 预热 240 根
  -> 方向判定: 1h 最近四根收盘变化，NONE 时回退 15m
  -> 计算 ATR、EMA、CVD、CCI、PA、Fibonacci、RR
  -> FIB-PA 权重评分，得到 component_points 和 total_score
  -> 计算 Q1/Q2/Q3/Q4
  -> 运行黑名单、数据、预算、敞口、保证金和冷却硬门
  -> score threshold + 组件最低分，得到 NO_TRADE/WATCH/PROBE/DIRECT
  -> 运行 LONG 保护、流动性、高 beta 和宏观降级逻辑
  -> 选择杠杆和名义仓位
  -> 运行 dry-run 后置控制和 paper order draft
  -> 通过时进入 paper ledger；真实环境还应进入 exchange order adapter
  -> 按止损、TP 阶梯、Q4 防守、成本保本和最大持仓时间管理
```

关键实现位置：

| 链路 | 文件/行 | 作用 |
|---|---|---|
| 入口评分 | `src/signals/entry_chain.py:86-120` | 计算权重、组件分、总分和基础动作 |
| FIB-PA 组件 | `src/signals/entry_chain_features.py:74-113` | EMA/CVD/CCI/PA/Fib/RR 组件 |
| 方向 | `src/signals/entry_chain_features.py:22-32` | 1h 四根变化阈值 |
| 线上上下文 | `scripts/run_live_dry_run.py:2249-2271` | 使用已收盘 K 线构造 context |
| 象限 | `scripts/run_live_dry_run.py:1307-1336` | 两条轴判定 Q1-Q4 |
| Q1 通道 | `scripts/run_live_dry_run.py:895-946` | 专用 Q1 条件 |
| 总门 | `src/signals/entry_chain_gates.py:38-70` | 标的、数据、预算、敞口、保证金硬门 |
| 后置风控 | `scripts/run_live_dry_run.py:1762-1790` | 冷却、止损熔断、日亏损和弱边降级 |
| paper 开仓/管理 | `src/observability/paper_trading.py:123-180`、`:229-293` | 纸面开仓、更新和出场 |

## 6. 门槛、权重与象限的完整说明

### 6.1 总分门槛

| 层级 | 配置值 | 方向调整后的有效门槛 |
|---|---:|---|
| DIRECT | 82 | LONG 92；SHORT 82 |
| PROBE 基础 | 70 | LONG 基础偏移 7；SHORT 0；同时还要求 `probe_conditions.min_score=72` |
| WATCH | 62 | LONG 72；SHORT 62 |

因此不能只看 `probe_threshold=70`，实际 FIB-PA PROBE 还会经过最小总分、组件、RR、趋势/CCI、elite 等二次检查。

### 6.2 FIB-PA 权重

当 `use_fib_pa_architecture=true` 时，实际权重固定为：

| 组件 | 权重 | 满分点数 | 作用 |
|---|---:|---:|---|
| `trend_ema_context` | 20 | 20 | EMA200 gate、EMA50 质量和动量 |
| `flow_cvd_confirmation` | 18 | 18 | CVD/量价流向 |
| `cci_momentum_quality` | 14 | 14 | CCI 动能质量和过热衰减 |
| `price_action_structure` | 22 | 22 | swing、实体、结构 |
| `fibonacci_location` | 18 | 18 | 1h/15m 回撤和扩展 |
| `risk_reward_geometry` | 8 | 8 | 止损、TP1、近端反向结构 |
| **合计** | **100** | **100** | `sum(component_points)` |

公式为：

```text
component_points = clamp(normalized_component_score, 0, 1) * weight
total_score = sum(component_points)
```

当前实际评分中，`background_4h` 和 `market_regime` 没有 FIB-PA 权重。因此它们不能阻止一个单币种 SHORT 在全市场上涨时取得高分。

### 6.3 普通 DIRECT/PROBE 组件门槛

| 层级 | 组件门槛 |
|---|---|
| DIRECT | PA >= 6，Fib >= 9，RR >= 4；不满足则降为 PROBE |
| PROBE | 总分 >= 72，Fib >= 12，PA >= 10，净 TP1 RR >= 1.3；无 RR 明细时 RR 点数 >= 4 |
| PROBE 趋势/动能 | EMA 点数 >= 10 或 CCI 点数 >= 9 |
| PROBE 低分质量 veto | 总分 < 75 且 EMA < 10 或 CCI < 7 时拒绝 |
| elite PROBE | 总分 >= 75，且 PA >= 18/Fib >= 15，或 EMA >= 15 且 PA+Fib >= 30 |
| high-beta PROBE | PA >= 12，RR >= 5，CCI >= 9，EMA >= 12 |

配置文件的 `probe_conditions.min_pa_score` 当前是 10；代码中的 6 是缺少配置字段时的 fallback，不是本运行配置的有效值。

### 6.4 四象限门槛

| 轴 | 条件 |
|---|---|
| 趋势结构轴 | EMA >= 15 且 PA >= 10 |
| 流动量能轴 | CVD >= 14 且 CCI >= 7 |
| Q1 | 两条轴均通过 |
| Q2 | 仅趋势结构轴通过 |
| Q3 | 仅流动量能轴通过 |
| Q4 | 两条轴均不通过 |

这里的轴是“相对于 intended side 的评分”，不是 BTC 或全市场方向。因此 Q1 SHORT 仍然完全可能出现。

### 6.5 Q1 trend launch 专用门槛

`q1_trend_launch` 使用独立的 near-miss 转化条件：

- 开关开启，数据健康必须为 `OK`；
- 标的非黑名单，Q1，方向为 LONG/SHORT，入场价有效；
- 近 8 根 15m 极值位置比例在 `0.20` 到 `0.80`；
- LONG 不能触发 overextension、upper-wick 或 chase；
- 总分 >= 82；PA >= 18；Fib >= 15；CVD >= 16；RR 点数 >= 0.5。

该通道没有检查 `watch_only_symbols`，也没有市场 regime 或 SHORT 逆势门槛。它应被视为实验通道，不应绕过中央标的策略和单笔风控。

## 7. 仓位管理与风控逻辑

### 7.1 名义仓位公式

当前 `_notional_hint()` 取以下上限的最小值：

```text
score_based = equity * exposure_pct
risk_based  = equity * risk_pct / stop_pct
cap_remaining = (symbol_cap - current_symbol_exposure) * equity
notional = min(score_based, risk_based, cap_remaining)
```

当前配置：

| 参数 | 值 |
|---|---:|
| `direct_risk_pct` | 0.006 |
| `probe_risk_pct` | 0.0025 |
| `base_direct_exposure_pct`（配置缺省，代码默认） | 0.20 |
| `probe_fraction`（代码默认） | 0.25 |
| 大盘币单标的上限 | 0.30 |
| 主流币单标的上限 | 0.20 |
| high-beta 单标的上限 | 0.10 |
| `max_total_exposure_pct` | 1.60 |
| `max_same_direction_exposure_pct` | 1.10 |
| `margin_buffer_pct` | 0.30 |

这套公式存在一个重要缺口：`risk_based` 是按止损距离推导名义仓位，但杠杆选择在后面可能直接给 3x/4x；没有一个独立的“单笔杠杆后损失不得超过账户 X%”硬门。因此 4x 交易可以在满足总敞口的情况下产生不成比例的账户损失。

### 7.2 杠杆选择

| 条件 | 杠杆结果 |
|---|---:|
| 非 PROBE/DIRECT | 0x |
| rolling Sharpe < 0 | 2x |
| ATR > 3% | 3x |
| ATR > 1.5% | DIRECT 4x；PROBE 3x |
| ATR <= 1.5%，DIRECT 且 score < 90 | 4x |
| ATR <= 1.5%，DIRECT 且 score >= 90，并满足 Fib13/18、PA9/22、CCI7/14、RR4/8 | 5x |
| ATR <= 1.5%，PROBE | 3x |

窗口实测分布为：1x 29 笔、3x 15 笔、4x 5 笔、5x 1 笔。Q1 专用小仓通道占大多数 1x 交易，但普通主链仍可能给刚过门槛的 DIRECT 4x。

### 7.3 总门和后置风控

中央硬门依次检查：

1. 黑名单和 watch-only；
2. 宏观周跌幅、异常 wick、数据污染冷却；
3. 已有同币持仓和活跃标的上限 8；
4. 动态每日交易预算，基础 16，最低 2；
5. 单币每日最多 2 笔；
6. 单币冷却；
7. 总敞口 1.6、同向敞口 1.1；
8. 可用保证金至少为权益的 30%；
9. 方向必须是 LONG 或 SHORT。

后置控制还会根据历史 paper 状态把决策降到 WATCH：

- observation-only 标的；
- 初始止损后 4 小时冷却；
- 48 小时内两次初始止损后 24 小时滚动冷却；
- 组合连续两次初始止损后 2 小时 circuit breaker；
- 当日已实现亏损 <= -30 时日亏损 circuit breaker；
- 没有正历史时对弱边 DIRECT/PROBE 降级。

配置中的实验熔断为 war fund `-150` 和 daily `-200`，主要用于实验账本，不应替代主账本的单笔风险限制。

### 7.4 Stress 检查缺口

stress 公式为：

```text
estimated_loss_pct = exposure_pct * leverage * adverse_move_pct
BLOCK only if estimated_loss_pct > 0.25
```

若按普通 DIRECT 的 20% 名义敞口、4x、20% 不利波动估算：

```text
0.20 * 4 * 0.20 = 0.16 <= 0.25 -> ALLOW
```

该检查会记录 `ALLOW/BLOCK`，但当前不是实际开仓硬阻断器；并且 25% 的组合最大损失阈值远高于单笔合理风险。应由 DeepSeek 重点评审是否改为单笔风险和组合压力的双重硬门。

### 7.5 出场与成本

当前 paper 生命周期参数：

| 机制 | 参数 |
|---|---|
| 费用 | 5 bps |
| 滑点 | 5 bps |
| 初始止损 | `ATR * 1.5`，限制在 0.5% 到 3% |
| TP 阶梯 | 1.2R / 2.0R / 3.0R |
| TP 分批 | 40% / 35% / 25% |
| 成本保本检查 | 持仓 8 根 K 线后 |
| 最大持仓 | 32 根 15m K 线 |
| trend capture 触发 | 1.5R |
| trailing | 1.0R |
| Q4 防守 | 满足连续 Q4 条件时退出 |
| Q3 防守 | 可减仓 50% |

窗口内退出分布说明，止损和成本超时是主要负向来源，不能先假定出场是主要 bug。

## 8. 指标和策略头脑风暴

以下全部是待评审、待 shadow 的研究假设，不是本次部署建议。

### 8.1 P0: 新增市场 regime/breadth 硬门

**假设:** 以已收盘 BTC 4h 结构、BTC EMA 斜率、主要币种上涨占比或 breadth 组合定义 `BULL_CONFIRMED/BEAR_CONFIRMED/NEUTRAL`。

**预期作用:**

- bullish regime 中，LONG 不再承受静态的 10 分额外惩罚；
- bullish regime 中，SHORT 必须具备明确反转/破位确认，或使用更高门槛；
- regime gate 必须同时作用于普通主链和 `q1_trend_launch`，不能只修补一个实验通道。

**纪律:** 只使用已完成 K 线；使用 regime 确认前的值，不使用未来 breadth；每个候选规则先离线回放和 shadow，不直接改 live。

### 8.2 P0: 新增突破/回撤后的行为确认

当前六个组件主要是状态评分，缺少“刚刚发生了什么”的确认。可新增独立的 `breakout_confirmation` 或作为高杠杆前置门：

- 15m 收盘突破前 32 根收盘高点/低点；
- 成交量达到前 32 根中位量的约 1.15 倍；
- 下一根已完成 K 线守住突破区域；
- 收盘位置、实体比例和上影线满足方向要求。

对于无法满足行为确认的高分信号，先降杠杆或降为 PROBE，不要通过继续提高总分让它直接 4x。

### 8.3 P0: 把单笔风险改成独立硬预算

这不是指标替换，但对本窗口最直接：

- 单笔杠杆后最大损失先限定为权益的 0.5% 到 1.0%（具体范围交由评审）；
- 先由 stop distance 计算名义仓位，再由杠杆后损失倒推上限；
- ATR 分位高时自动降杠杆，而不是只用总敞口限制；
- 4x/5x 必须同时满足行为确认、regime 一致和单笔风险预算。

验证时要看尾部损失、最大回撤、保证金 PnL，而不能只看平均收益。

### 8.4 P1: ADX/DMI shadow 对比 CCI

CCI 当前权重 14，且与局部动量和 PA 有一定重复。问题在于趋势延续阶段，CCI 过热可能给出低质量反馈；ADX/DMI 更适合拆分：

- `ADX`：趋势强度；
- `+DI/-DI`：方向一致性。

不建议立即删除 CCI。应先做 CCI 与 ADX/DMI 的 shadow/A-B，对比：

- trade count、expectancy、profit factor；
- win rate、最大回撤、Sharpe；
- LONG/SHORT 分方向结果；
- Q1/Q2/Q3/Q4 结果；
- exposure、MFE/MAE、尾部单笔损失。

如果只在一个窗口有效，不能替换。也可先把 CCI 改为“CCI 斜率 + 价格一致性”复合，而不是同时新增多个指标。

### 8.5 暂不优先替换 Fibonacci

本窗口的主故障是方向 regime、通道政策和杠杆，不是 Fibonacci 计算本身。Fib exhaustion 反而是当前高频的阻断来源之一。替换 Fib 会同时改变位置、追单和 RR 行为，增加归因难度，优先级低于 regime gate 和单笔风险。

### 8.6 必须修复的非指标问题

1. 所有实验通道都必须调用统一的 blacklist/watch-only/observation-only 和 exposure gate。
2. 每次 decision、order draft、open、reduce、close 写入稳定的 `decision_id`、`draft_id`、`position_id`，而不是依靠不同时间戳和 symbol 近邻匹配。
3. 历史交易中 `entry_channel=null` 的 18 笔无法直接追溯到具体入口；`paper_trading.py` 已有按 action 推断 `main_direct/main_probe` 的设计，但必须确保所有实际路径都写出显式值。
4. `dry_run_q1_green_channel_*` 在代码注释中标记为兼容保留/未接线字段，不能把配置存在误认为策略已经生效。

## 9. 建议的验证协议

在任何生产配置修改前，至少建立以下离线/影子对照：

| 组 | 方向门 | 行为确认 | 仓位 |
|---|---|---|---|
| Baseline | 当前 | 当前 | 当前 |
| A | regime gate | 当前 | 当前 |
| B | 当前 | breakout/pullback confirmation | 当前 |
| C | regime + confirmation | confirmation | 当前 |
| D | 当前 | 当前 | 单笔风险上限 + ATR 杠杆 |
| E | regime + confirmation | confirmation | 单笔风险上限 + ATR 杠杆 |

每组至少跨多个独立市场状态，不用本窗口单独调参。报告必须同时输出：

- trade count 和有效曝光时间；
- expectancy、win rate、profit factor、Sharpe；
- max drawdown、日内尾部损失、最大连续亏损；
- LONG/SHORT、Q1/Q2/Q3/Q4、symbol、entry channel 分层结果；
- MFE/MAE、`INITIAL_STOP_HIT` 占比、达到 1R 的比例；
- 名义 PnL、杠杆后 PnL、手续费/滑点敏感性；
- 开仓少时的统计不确定性和单窗口依赖。

**暂不部署条件:** 样本不足 20 笔时不调参数；任何规则只改善一个窗口、不改善其他 regime 时不纳入主链；不得通过放宽黑名单、RR 或数据质量门来制造交易数量。

## 10. 给 DEEPSEEK 的评审问题

1. 在 bullish regime 中，SHORT 是否应当拥有条件化的额外门槛，还是直接要求反转/破位行为确认？门槛应该作用于普通主链、Q1 专用通道，还是两者？
2. 当前“LONG 固定 +10、SHORT +0”的设计是否还合理？是否应改成 regime 条件化，而不是简单把 LONG offset 改小？
3. Q1 trend launch 是否应彻底取消独立入口，改为普通链路通过后只改变仓位/退出模式？
4. 单笔 4x 交易造成了主损失，合理的单笔杠杆后风险预算应是多少？总敞口 1.6 和同向敞口 1.1 是否需要重新定义为保证金口径？
5. ADX/DMI 相对 CCI 能否在多个 regime 中提升 SHORT 过滤和趋势延续识别？应采用替换、并行 shadow，还是 CCI 复合化？
6. 39 笔交易 MFE 未到 1R 的结果是否足以把“行为确认”列为入场硬门？需要怎样的样本量和反事实回放才能证伪？
7. `entry_channel=null` 的历史记录如何补齐关联 ID，确保下一轮审计能区分普通 DIRECT、普通 PROBE、Q1 实验和 scout？

## 11. 可复现来源

### 日志

```text
logs/2026-08/2026-08-24/runtime.out.12.log
logs/2026-08/2026-08-24/decisions.jsonl
logs/2026-08/2026-08-24/paper_trades.jsonl
...
logs/2026-09/2026-09-15/decisions.jsonl
logs/2026-09/2026-09-15/paper_trades.jsonl
logs/2026-09/2026-09-15/summary.json
```

### 配置和实现

```text
configs/entry_chain.dry_run_fib_pa_v1.json
src/signals/entry_chain.py
src/signals/entry_chain_config.py
src/signals/entry_chain_scoring.py
src/signals/entry_chain_gates.py
src/signals/entry_chain_features.py
scripts/run_live_dry_run.py
src/observability/paper_trading.py
src/risk/stress_simulator.py
src/risk/position_sizer.py
```

### 复核命令

```powershell
git diff --check
rg -n "direct_threshold|probe_threshold|long_threshold_offset|short_threshold_offset" configs src
rg -n "def direction_from_history|FIB_PA_WEIGHTS|def _select_leverage|def _notional_hint" src
rg -n "def _q1_trend_launch_eligible|def quadrant_axes|def apply_dry_run_decision_controls" scripts/run_live_dry_run.py
```

## 12. 最终判断

本窗口不能得出“应该放宽阈值，多开仓”的结论。可证据支持的顺序是：

1. 先统一所有入口的标的政策和可观测性；
2. 加入 completed-candle 的 market regime 和 SHORT 逆势保护；
3. 对高杠杆增加行为确认，并建立单笔杠杆后风险硬上限；
4. 再用跨 regime shadow 数据评估 ADX/DMI 是否替换或辅助 CCI；
5. 最后才讨论总分、LONG offset 或 Q1/Q2/Q3 的阈值微调。

在上述验证完成前，不能声称策略已经能够稳定选出牛市，也不能把单个窗口中的反事实信号当成可上线收益。
