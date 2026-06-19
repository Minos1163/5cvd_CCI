下面是重新生成的 `docs/09_data_contract.md`，按你现在的整体架构补完整了，直接可放进仓库。

````md
# Data Contract

Version: V1.0

---

# 1. 目的

本文件定义策略系统所需的全部数据契约，确保：

- 数据格式统一
- 多周期对齐一致
- 回测与实盘共用同一份数据结构
- 指标计算不依赖非标准字段
- 任何模块都能明确知道自己读什么、写什么、依赖什么

数据契约的目标不是“尽量兼容”，而是“尽量稳定”。

---

# 2. 契约总原则

1. 所有数据必须使用统一时间基准。
2. 所有周期必须能追溯到原始来源。
3. 所有字段必须有明确语义。
4. 所有缺失值必须有明确处理方式。
5. 所有模块不得随意增加隐式字段。
6. 所有策略逻辑必须依赖已定义的数据结构。
7. 回测与实盘必须使用同一套字段名与语义。
8. 任何不在契约中的数据不得进入主链路。

---

# 3. 数据分层

系统数据分为五层：

- 原始市场数据
- 标准化行情数据
- 多周期聚合数据
- 指标结果数据
- 策略上下文数据

各层职责如下：

- 原始市场数据：保存交易所返回的原始行情
- 标准化行情数据：统一字段、统一时区、统一精度
- 多周期聚合数据：生成 15m / 30m / 1H / 4H
- 指标结果数据：保存 MACD、CCI、BOLL、RSI、CVD、ATR 结果
- 策略上下文数据：输出给信号引擎和状态机

---

# 4. 数据源范围

系统至少需要以下数据源：

- K 线数据
- 成交量数据
- 主动买卖方向数据
- 资金费率数据
- 持仓量数据
- 标的池数据
- 交易执行数据
- 账户与持仓快照数据

其中：

- K 线数据是主数据源
- 主动买卖方向数据用于 CVD
- 资金费率和持仓量用于风险过滤
- 标的池数据用于交易范围筛选
- 交易执行数据用于实盘审计
- 账户与持仓快照用于风险管理

---

# 5. 时间基准

统一使用 UTC 时间戳。

要求：

- 所有时间字段必须是 UTC
- 所有周期边界必须严格对齐
- 禁止本地时区混用
- 禁止字符串时间与时间戳混杂不清
- 禁止不同模块各自解释时间含义

建议字段：

- `open_time`
- `close_time`
- `ts`
- `event_time`

其中：

- `open_time` 表示 K 线开始时间
- `close_time` 表示 K 线结束时间
- `ts` 表示事件记录时间
- `event_time` 表示业务事件发生时间

---

# 6. 标准 K 线格式

所有周期的 K 线必须至少包含以下字段：

```text
symbol
timeframe
open_time
close_time
open
high
low
close
volume
quote_volume
trade_count
taker_buy_base_volume
taker_buy_quote_volume
is_closed
source
````

字段说明：

* `symbol`：交易标的，如 BTCUSDT
* `timeframe`：周期，如 15m、30m、1h、4h
* `open_time`：K 线起始时间
* `close_time`：K 线结束时间
* `open`：开盘价
* `high`：最高价
* `low`：最低价
* `close`：收盘价
* `volume`：基础币成交量
* `quote_volume`：计价币成交量
* `trade_count`：成交笔数
* `taker_buy_base_volume`：主动买入基础币量
* `taker_buy_quote_volume`：主动买入计价币量
* `is_closed`：是否已收盘
* `source`：数据来源标识

---

# 7. 标准化行情对象

所有行情数据在进入策略前，必须转换为统一对象。

建议对象字段如下：

```text
MarketCandle
```

字段包括：

* `symbol`
* `timeframe`
* `open_time`
* `close_time`
* `open`
* `high`
* `low`
* `close`
* `volume`
* `quote_volume`
* `trade_count`
* `taker_buy_base_volume`
* `taker_buy_quote_volume`
* `is_closed`
* `source`
* `quality_flag`

其中：

* `quality_flag` 用于标记数据是否可用
* `quality_flag=false` 的数据不得进入策略主链路

---

# 8. 多周期数据契约

系统至少支持四个周期：

* 15m：执行周期
* 30m：确认周期
* 1H：方向周期
* 4H：背景周期

多周期契约要求：

1. 15m 是最小粒度基准。
2. 30m 必须由已完成的 15m 聚合得到。
3. 1H 必须由已完成的 15m 或 30m 聚合得到。
4. 4H 必须由已完成的 1H 聚合得到。
5. 高周期数据必须晚于低周期数据完成后再输出。
6. 不能使用未闭合高周期 bar 作为最终信号依据。

---

# 9. 聚合规则

聚合 K 线时必须遵守以下规则：

* `open` 取首根子 K 线开盘价
* `high` 取区间最高
* `low` 取区间最低
* `close` 取末根子 K 线收盘价
* `volume` 做累加
* `quote_volume` 做累加
* `trade_count` 做累加
* `taker_buy_base_volume` 做累加
* `taker_buy_quote_volume` 做累加

聚合过程中必须保留：

* 原始来源
* 聚合来源周期
* 聚合版本号

---

# 10. 缺失数据处理

缺失数据分三类：

## 10.1 单根缺失

单根缺失可以通过补齐空 bar 表示。

规则：

* 价格字段延续上一根 close
* 成交量置零
* `quality_flag=false`

## 10.2 连续短缺

连续缺失少量 bar 时，可标记为局部不可交易。

规则：

* 策略可暂时跳过该标的
* 不允许伪造真实成交数据
* 不允许直接用邻近周期硬插值作为正式信号

## 10.3 严重缺失

严重缺失时必须剔除标的或暂停该标的交易。

规则：

* 缺失超过阈值后不得继续回测
* 实盘必须暂停该 symbol
* 必须写入数据异常日志

---

# 11. 异常数据处理

以下数据必须被识别并标记：

* 重复时间戳
* 倒序时间戳
* 极端长影线
* 价格为负或零
* 成交量异常放大或归零
* 精度错误
* 交易所临时异常返回值

异常处理原则：

* 能修复则修复
* 不能修复则剔除
* 不能静默忽略
* 不能进入主策略通道

---

# 12. 指标输入契约

所有指标模块必须接收统一输入：

```text
candles: list[MarketCandle]
```

每个指标模块输出统一结果对象：

```text
IndicatorResult
```

推荐字段：

* `name`
* `symbol`
* `timeframe`
* `value`
* `signal`
* `trend`
* `strength`
* `timestamp`
* `metadata`
* `quality_flag`

其中：

* `value` 表示指标主值
* `signal` 表示离散信号
* `trend` 表示趋势方向
* `strength` 表示强度
* `metadata` 保存附加说明
* `quality_flag` 表示结果是否可信

---

# 13. MACD 数据契约

MACD 模块至少输出：

* `macd_line`
* `signal_line`
* `histogram`
* `histogram_slope`
* `cross_state`

用于判断：

* 趋势方向
* 动量变化
* 是否发生金叉/死叉
* 是否出现动量减弱

---

# 14. RSI 数据契约

RSI 模块至少输出：

* `rsi`
* `rsi_slope`
* `overbought_flag`
* `oversold_flag`
* `midline_state`

用于判断：

* 超买超卖
* 回调质量
* 趋势恢复
* 入场是否过热

---

# 15. CCI 数据契约

CCI 模块至少输出：

* `cci`
* `cci_slope`
* `extreme_flag`
* `recovery_flag`

用于判断：

* 趋势强度
* 极端偏离
* 回归中枢
* 动量恢复

---

# 16. BOLL 数据契约

BOLL 模块至少输出：

* `middle_band`
* `upper_band`
* `lower_band`
* `band_width`
* `band_expansion_flag`
* `band_contraction_flag`
* `price_position`

用于判断：

* 波动收缩
* 波动扩张
* 是否突破中轨
* 是否处于压缩后启动阶段

---

# 17. CVD 数据契约

CVD 模块至少输出：

* `cvd`
* `cvd_delta`
* `cvd_slope`
* `cvd_divergence_flag`
* `buy_pressure`
* `sell_pressure`

用于判断：

* 主动买卖压力
* 资金流方向
* 与价格是否背离
* 是否存在吸筹或派发迹象

---

# 18. ATR 数据契约

ATR 模块至少输出：

* `atr`
* `atr_pct`
* `volatility_state`

用于判断：

* 波动率水平
* 止损距离
* 仓位大小
* 市场是否过热

ATR 只允许用于风控，不允许作为主方向信号。

---

# 19. 策略上下文契约

策略上下文对象用于把多周期、多指标整合成统一输入。

建议对象字段：

```text
StrategyContext
```

包含：

* `symbol`
* `timestamp`
* `market_state_4h`
* `trend_state_1h`
* `confirm_state_30m`
* `trigger_state_15m`
* `indicators_15m`
* `indicators_30m`
* `indicators_1h`
* `indicators_4h`
* `risk_snapshot`
* `position_snapshot`
* `cooldown_state`
* `signal_candidate`
* `quality_flag`

---

# 20. 策略事件契约

所有策略事件必须结构化。

建议字段：

* `event_id`
* `symbol`
* `timeframe`
* `event_type`
* `state_before`
* `state_after`
* `reason`
* `score`
* `timestamp`
* `metadata`

常见 `event_type`：

* `SIGNAL_CREATED`
* `WATCH_ENTERED`
* `PROBE_ENTERED`
* `DIRECT_ENTERED`
* `POSITION_MANAGED`
* `EXIT_TRIGGERED`
* `RISK_BLOCKED`
* `DATA_INVALID`

---

# 21. 执行数据契约

执行层必须记录：

* `order_id`
* `client_order_id`
* `symbol`
* `side`
* `order_type`
* `quantity`
* `price`
* `reduce_only`
* `position_side`
* `status`
* `filled_qty`
* `avg_price`
* `commission`
* `latency_ms`
* `reject_reason`
* `raw_response`

执行数据必须与策略事件可关联。

---

# 22. 账户与持仓快照契约

账户快照至少包含：

* `account_equity`
* `available_margin`
* `used_margin`
* `unrealized_pnl`
* `realized_pnl`
* `max_drawdown`
* `daily_pnl`
* `weekly_pnl`

持仓快照至少包含：

* `symbol`
* `side`
* `position_qty`
* `entry_price`
* `mark_price`
* `unrealized_pnl`
* `leverage`
* `stop_price`
* `take_profit_price`
* `position_age`

---

# 23. 标的池数据契约

每个交易标的至少应包含：

* `symbol`
* `base_asset`
* `quote_asset`
* `market_cap_rank`
* `volume_rank`
* `tier`
* `tradable`
* `listed_time`
* `delisting_flag`
* `correlation_group`

---

# 24. 数据质量标记

每条数据、每个指标结果、每个策略上下文都必须带质量标记。

建议值：

* `true`：可用
* `false`：不可用
* `degraded`：降级可用
* `stale`：过期不可用

任何 `false` 或 `stale` 数据不得驱动直接开仓。

---

# 25. 缓存契约

允许缓存，但缓存不能改变逻辑。

缓存内容可以包括：

* 最近 N 根 K 线
* 指标结果
* 多周期上下文
* 风控快照
* 执行状态

缓存要求：

* 过期时间明确
* 更新频率明确
* 命中条件明确
* 不得读取未来缓存

---

# 26. 数据版本契约

所有数据处理流程必须带版本号。

至少记录：

* 原始数据版本
* 聚合版本
* 指标版本
* 策略版本
* 风控版本
* 执行版本

目的：

* 回测可复现
* 实盘可审计
* 版本变动可追踪

---

# 27. 存储契约

建议将数据分为三类存储：

## 27.1 热数据

* 最近行情
* 当前持仓
* 当前信号
* 当前风控状态

## 27.2 温数据

* 最近交易记录
* 最近策略事件
* 最近执行日志

## 27.3 冷数据

* 历史回测数据
* 长期交易审计
* 历史绩效报表

---

# 28. 禁止项

禁止：

* 混用不同时区
* 在不同模块中各自定义相同字段但含义不同
* 让指标模块直接读取交易所原始回包
* 让策略模块绕过标准化对象
* 用展示层数据替代策略层数据
* 用补丁字段参与主决策
* 让回测与实盘使用不同字段集

---

# 29. 示例结构

一个标准的策略输入对象应类似如下结构：

```text
StrategyContext {
  symbol: "BTCUSDT",
  timestamp: 1710000000,
  market_state_4h: "BULL",
  trend_state_1h: "LONG_ALLOWED",
  confirm_state_30m: "CONFIRMED",
  trigger_state_15m: "DIRECT",
  indicators_15m: {...},
  indicators_30m: {...},
  indicators_1h: {...},
  indicators_4h: {...},
  risk_snapshot: {...},
  position_snapshot: {...},
  cooldown_state: {...},
  signal_candidate: {...},
  quality_flag: true
}
```

---

# 30. 结论

数据契约是整个系统的地基。

地基不统一，后面所有层都会漂。

因此，任何模块的第一准则都是：

先看数据契约，再写逻辑。

```

如果你要，我下一步可以把 :contentReference[oaicite:0]{index=0}，方便你直接交给 Codex。
```
