下面补齐 `docs/14_event_bus_spec.md` 的完整版本，按你当前的工程架构直接可放进仓库。

````md
# Event Bus Specification

Version: V1.0

---

# 1. 目的

本文件定义项目内部事件总线规范，确保：

- 各模块之间解耦
- 策略、风控、执行、回测、报告之间通过统一事件通信
- 所有关键动作都可追踪、可审计、可回放
- 回测与实盘共享同一事件模型
- 不依赖隐式调用链，不依赖临时补丁逻辑

事件总线的目标不是“更复杂”，而是“更清晰”。

---

# 2. 设计原则

1. 事件是系统内部的标准通信单位。
2. 事件必须结构化，禁止散乱字符串拼接。
3. 事件必须可序列化，便于落盘和回放。
4. 事件必须带时间戳和版本信息。
5. 事件必须可追踪到来源模块和业务上下文。
6. 事件总线不负责策略判断，只负责消息传递。
7. 不允许事件总线里塞业务补丁逻辑。
8. 不允许模块直接跨层修改彼此状态，必须通过事件驱动。

---

# 3. 事件总线的职责边界

事件总线负责：

- 注册事件监听器
- 发布事件
- 分发事件
- 记录事件日志
- 支持事件回放
- 支持同步或异步派发
- 支持事件过滤、分组、订阅

事件总线不负责：

- 计算指标
- 判断交易方向
- 计算仓位
- 生成订单
- 修改交易策略
- 修正风控规则

---

# 4. 事件生命周期

标准事件生命周期如下：

1. created
2. published
3. dispatched
4. handled
5. persisted
6. archived

若事件处理失败，则进入：

- failed
- retried
- dead_lettered

每个状态变化都必须写日志。

---

# 5. 事件命名规范

事件名称必须统一采用大写下划线格式。

示例：

- `MARKET_DATA_UPDATED`
- `INDICATOR_UPDATED`
- `MULTI_TF_CONTEXT_READY`
- `SIGNAL_CREATED`
- `WATCH_ENTERED`
- `PROBE_ENTERED`
- `DIRECT_ENTERED`
- `ORDER_SUBMITTED`
- `ORDER_FILLED`
- `ORDER_REJECTED`
- `POSITION_OPENED`
- `POSITION_REDUCED`
- `POSITION_CLOSED`
- `STOP_HIT`
- `TP_HIT`
- `RISK_BLOCKED`
- `COOLDOWN_STARTED`
- `COOLDOWN_ENDED`
- `BACKTEST_STEP_COMPLETED`
- `REPORT_GENERATED`

禁止：

- 随意混用大小写
- 使用无语义缩写
- 使用同名不同义事件
- 在不同模块中对同一事件使用不同含义

---

# 6. 事件类型分类

事件分为以下几类：

## 6.1 Market Events
市场数据相关事件。

例如：

- K线更新
- 多周期数据完成
- 行情异常

## 6.2 Indicator Events
指标计算结果事件。

例如：

- MACD 更新
- RSI 更新
- CCI 更新
- BOLL 更新
- CVD 更新
- ATR 更新

## 6.3 Context Events
多周期上下文事件。

例如：

- 4H 背景状态完成
- 1H 方向确认完成
- 30m 中继确认完成
- 15m 触发确认完成

## 6.4 Signal Events
策略信号事件。

例如：

- 发出观望信号
- 进入 probe
- 进入 direct
- 信号失效

## 6.5 Risk Events
风险控制事件。

例如：

- 止损触发
- 止盈触发
- 风险超限
- 冷却开始

## 6.6 Execution Events
执行层事件。

例如：

- 订单提交
- 订单成交
- 订单拒绝
- 订单撤销

## 6.7 Backtest Events
回测事件。

例如：

- 回测步骤完成
- 回测交易模拟完成
- 回测结束

## 6.8 Reporting Events
报告生成事件。

例如：

- 日报生成
- 周报生成
- 月报生成

---

# 7. 标准事件结构

所有事件都必须使用统一结构。

建议基础字段如下：

```text
Event {
  event_id
  event_type
  ts
  source
  symbol
  timeframe
  version
  payload
  priority
  correlation_id
  parent_event_id
  trace_id
  status
}
````

字段说明：

* `event_id`：事件唯一ID
* `event_type`：事件类型
* `ts`：事件时间戳，统一 UTC
* `source`：来源模块
* `symbol`：交易标的
* `timeframe`：事件关联周期
* `version`：事件结构版本
* `payload`：事件数据体
* `priority`：事件优先级
* `correlation_id`：关联同一策略链路的ID
* `parent_event_id`：上游事件ID
* `trace_id`：全链路追踪ID
* `status`：事件处理状态

---

# 8. Payload 规范

`payload` 必须结构化，不能只放字符串。

示例：

```text
payload = {
  "price": 0.1801,
  "direction": "LONG",
  "score": 0.72,
  "reason": "1H_CONFIRMATION_OK",
  "quality_flag": true
}
```

要求：

* 所有关键字段必须命名清晰
* 复合对象必须显式嵌套
* 不能把关键业务信息丢进纯文本
* 不能让不同模块各自解释 payload

---

# 9. 事件优先级

建议事件优先级如下：

* `CRITICAL`
* `HIGH`
* `NORMAL`
* `LOW`

优先级适用范围：

## CRITICAL

* 风险超限
* 止损触发
* 执行异常
* 账户异常

## HIGH

* 开仓信号
* 平仓信号
* 订单成交
* 保护单失败

## NORMAL

* 指标更新
* 上下文更新
* 状态机转移

## LOW

* 统计类事件
* 报告类事件
* 调试辅助事件

---

# 10. 事件源与订阅者

事件源是发布事件的模块。

常见事件源：

* `data_loader`
* `indicator_engine`
* `context_engine`
* `signal_engine`
* `state_machine`
* `risk_engine`
* `execution_engine`
* `backtest_engine`
* `report_engine`

订阅者是消费事件的模块。

常见订阅者：

* 策略状态机
* 风控模块
* 执行模块
* 日志模块
* 回测模块
* 报告模块
* 监控模块

---

# 11. 事件总线工作模式

事件总线支持两种模式：

## 11.1 Sync Mode

同步模式。

特点：

* 事件发布后立即处理
* 适合回测和单线程调试
* 行为简单、可追踪性高

## 11.2 Async Mode

异步模式。

特点：

* 事件发布后进入队列
* 适合实盘和高频更新
* 允许多个监听器并行消费

默认建议：

* 回测使用 Sync Mode
* 实盘可使用 Async Mode
* 但策略核心链路必须保持确定性

---

# 12. 事件队列约束

若使用队列，必须满足：

* 队列有最大长度
* 队列有优先级策略
* 队列溢出时有明确处理
* 不能无限缓存事件
* 不能因队列堵塞导致策略失真

推荐行为：

* 高优先级事件优先出队
* 低优先级统计事件可丢弃或降级
* 关键风险事件不得丢失

---

# 13. 事件去重

同一业务动作不得重复生成多个等价事件。

建议去重键：

```text
symbol + event_type + strategy_event_id + timeframe
```

去重规则：

* 同一策略事件只允许一次有效处理
* 重发事件必须带相同 correlation_id
* 若事件已处理，重复事件应被标记为 duplicate 并忽略

---

# 14. 事件幂等性

事件处理必须幂等。

要求：

* 重复消费同一事件不能改变最终状态
* 重试不能导致重复下单
* 重放不能导致重复平仓
* 事件失败后重试必须安全

幂等实现建议：

* event_id 唯一
* handler 记录已处理事件ID
* 关键状态变化前做状态校验

---

# 15. 事件回放

事件总线必须支持回放。

用途：

* 回测复现
* 实盘故障复盘
* 策略审计
* 模拟测试

回放要求：

* 按时间顺序回放
* 可指定时间范围
* 可指定 symbol
* 可指定 event_type
* 回放时可选择忽略低优先级事件

---

# 16. 事件持久化

关键事件必须落盘。

建议存储内容：

* event_id
* event_type
* ts
* source
* symbol
* timeframe
* trace_id
* parent_event_id
* payload
* status
* version

持久化要求：

* JSON 结构化存储
* 可导出 CSV / Parquet
* 可按天分片
* 可按 symbol 分片

---

# 17. 错误处理

事件处理失败时，必须明确分类。

常见错误分类：

* `INVALID_PAYLOAD`
* `UNKNOWN_EVENT_TYPE`
* `HANDLER_ERROR`
* `TIMEOUT`
* `DUPLICATE_EVENT`
* `STATE_CONFLICT`
* `DEPENDENCY_UNAVAILABLE`

处理原则：

* 不吞错
* 不静默失败
* 不自动歪曲业务含义
* 不允许 handler 内部偷偷修状态

---

# 18. Dead Letter Queue

若事件多次处理失败，应进入死信队列。

进入死信队列条件：

* 重试次数超限
* 关键依赖不可用
* 数据结构非法
* 状态冲突无法恢复

死信队列要求：

* 记录失败原因
* 记录原始 payload
* 记录重试历史
* 记录处理模块
* 可人工复查

---

# 19. 关键事件定义

以下事件属于系统主干事件，必须严格一致。

## 19.1 `MARKET_DATA_UPDATED`

市场数据更新事件。

触发时机：

* 新 K 线完成
* 行情流刷新

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "close": 65000.12,
  "volume": 1234.56
}
```

---

## 19.2 `INDICATOR_UPDATED`

指标计算完成事件。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "macd": {...},
  "rsi": {...},
  "cci": {...},
  "boll": {...},
  "cvd": {...},
  "atr": {...}
}
```

---

## 19.3 `MULTI_TF_CONTEXT_READY`

多周期上下文准备完成。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "market_state_4h": "BULL",
  "trend_state_1h": "LONG_ALLOWED",
  "confirm_state_30m": "CONFIRMED",
  "trigger_state_15m": "READY"
}
```

---

## 19.4 `SIGNAL_CREATED`

策略信号产生。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "signal": "DIRECT_LONG",
  "score": 0.78,
  "reason": "ALL_LAYERS_ALIGNED"
}
```

---

## 19.5 `WATCH_ENTERED`

进入观察状态。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "watch_side": "LONG",
  "reason": "1H_CONFIRMED_BUT_15M_NOT_READY"
}
```

---

## 19.6 `PROBE_ENTERED`

进入试探仓状态。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "side": "LONG",
  "probe_ratio": 0.25,
  "reason": "HIGHER_TF_CONFIRMED_LOWER_TF_PARTIAL"
}
```

---

## 19.7 `DIRECT_ENTERED`

进入正式开仓状态。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "side": "LONG",
  "notional": 5000,
  "reason": "FULL_CONFIRMATION"
}
```

---

## 19.8 `ORDER_SUBMITTED`

订单已提交。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "order_type": "LIMIT",
  "side": "BUY",
  "quantity": 0.1
}
```

---

## 19.9 `ORDER_FILLED`

订单成交。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "filled_qty": 0.1,
  "avg_price": 65000.5
}
```

---

## 19.10 `ORDER_REJECTED`

订单拒绝。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "reason": "MIN_NOTIONAL_FAILED"
}
```

---

## 19.11 `POSITION_OPENED`

持仓建立。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "side": "LONG",
  "qty": 0.1,
  "entry_price": 65000.5
}
```

---

## 19.12 `POSITION_REDUCED`

持仓减小。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "reduced_qty": 0.05,
  "reason": "RISK_REDUCTION"
}
```

---

## 19.13 `POSITION_CLOSED`

持仓平仓。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "reason": "STOP_HIT",
  "pnl": -35.2
}
```

---

## 19.14 `STOP_HIT`

止损触发。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "stop_price": 64700.0
}
```

---

## 19.15 `TP_HIT`

止盈触发。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "tp_level": "TP1",
  "tp_price": 65500.0
}
```

---

## 19.16 `RISK_BLOCKED`

风险阻断。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "reason": "DAILY_LOSS_LIMIT_REACHED"
}
```

---

## 19.17 `COOLDOWN_STARTED`

冷却开始。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "side": "LONG",
  "bars": 6
}
```

---

## 19.18 `COOLDOWN_ENDED`

冷却结束。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "side": "LONG"
}
```

---

## 19.19 `BACKTEST_STEP_COMPLETED`

回测单步完成。

payload 示例：

```text
{
  "symbol": "BTCUSDT",
  "timeframe": "15m",
  "step": 1024
}
```

---

## 19.20 `REPORT_GENERATED`

报告生成完成。

payload 示例：

```text
{
  "report_type": "daily",
  "path": "reports/daily_report.html"
}
```

---

# 20. Handler 规范

每个事件处理器必须遵守统一接口。

建议接口：

```python
handle(event: Event) -> HandlerResult
```

`HandlerResult` 至少包含：

* `success`
* `next_events`
* `logs`
* `errors`
* `metadata`

要求：

* handler 必须显式返回结果
* handler 不得悄悄吞掉异常
* handler 不得跨层调用未知模块
* handler 不得直接修改不属于自己的状态

---

# 21. 事件链路追踪

每个事件必须能串成完整链路。

要求：

* `parent_event_id` 指向上游事件
* `correlation_id` 串联同一业务链
* `trace_id` 串联全局链路

示例链路：

```text
MARKET_DATA_UPDATED
  -> INDICATOR_UPDATED
  -> MULTI_TF_CONTEXT_READY
  -> SIGNAL_CREATED
  -> PROBE_ENTERED
  -> ORDER_SUBMITTED
  -> ORDER_FILLED
  -> POSITION_OPENED
```

---

# 22. 调试与审计要求

事件日志必须支持以下维度查询：

* 按时间
* 按 symbol
* 按 event_type
* 按 trace_id
* 按 correlation_id
* 按状态
* 按优先级
* 按模块

---

# 23. 测试要求

事件总线必须有单元测试和集成测试。

至少覆盖：

* 事件发布
* 事件订阅
* 事件去重
* 事件幂等
* 事件回放
* 死信队列
* 优先级调度
* handler 异常处理
* 状态冲突处理

---

# 24. 禁止项

禁止：

* 事件名称随意变化
* payload 不结构化
* 事件处理依赖隐式全局变量
* 事件总线变成业务逻辑仓库
* 同一个事件被不同模块赋予不同含义
* 忽略死信队列
* 重放事件时走另一套逻辑

---

# 25. 结论

事件总线是系统神经网络。

如果事件不统一，模块之间就会互相污染。

如果事件可追踪，整个系统就可审计、可回放、可维护。
