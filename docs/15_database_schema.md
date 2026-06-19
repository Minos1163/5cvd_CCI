下面是重新生成的 `docs/15_database_schema.md` 完整版本，按你当前这套交易系统架构补齐了表结构、主键、索引、写入边界、审计与保留策略，直接可放进仓库。

````md
# Database Schema

Version: V1.0

---

# 1. 目的

本文件定义系统的数据库结构与数据持久化规范，确保：

- 行情、指标、信号、状态机、风控、执行、回测、报告都有统一存储
- 所有关键业务动作可审计、可复盘、可追踪
- 回测与实盘的数据模型一致
- 数据库只承担持久化职责，不承载策略逻辑
- 不同模块写入边界清晰，不互相污染

数据库的目标不是“什么都存”，而是“每一类数据都知道该存在哪里”。

---

# 2. 设计原则

1. 结构化优先，禁止把核心业务塞进大字符串。
2. 实盘与回测共享同一套核心表结构。
3. 数据表职责单一，禁止一个表同时承担多种语义。
4. 所有表都必须有主键、时间字段、版本字段。
5. 所有关键事件都必须可追踪到来源模块。
6. 所有写操作必须可审计。
7. 大表必须考虑分区、归档和保留期。
8. 不允许模块私自建表存临时数据进入主链路。
9. 不允许策略逻辑依赖数据库隐式副作用。
10. 任何 schema 变更都必须可迁移、可回滚。

---

# 3. 数据库选型建议

建议主库使用 PostgreSQL。

原因：

- 事务可靠
- 索引和分区能力强
- 适合结构化审计数据
- 易于和回测、报告、监控联动

可选配套：

- Redis：热缓存、限频、临时状态
- Parquet/CSV：离线回测与历史归档
- Object Storage：大体量日志和报表存储

---

# 4. 数据分层

系统数据分为四层：

- 热层：当前行情、当前持仓、当前状态机、当前风控
- 温层：最近交易、最近事件、最近执行日志
- 冷层：历史回测、长期审计、历史报表
- 归档层：长期保存的压缩历史数据

---

# 5. 命名规范

数据库命名统一使用小写下划线风格。

示例：

- `market_candles`
- `indicator_results`
- `strategy_events`
- `orders`
- `positions`
- `risk_snapshots`

字段命名规则：

- 使用清晰业务语义
- 避免缩写过度
- 避免同义字段重复
- 同一语义在全库中保持一致

---

# 6. 通用字段规范

建议所有核心表都包含以下通用字段：

- `id`
- `symbol`
- `timeframe`
- `ts`
- `version`
- `source`
- `created_at`
- `updated_at`

说明：

- `id`：主键
- `symbol`：交易标的
- `timeframe`：周期
- `ts`：事件或数据时间
- `version`：记录版本
- `source`：数据来源
- `created_at`：写入时间
- `updated_at`：更新时间

---

# 7. 时间规范

所有时间统一使用 UTC。

要求：

- 数据库存储 UTC 时间
- 不在数据库层混用本地时区
- 查询层再进行显示转换
- 分区键优先使用日期或小时级 UTC 字段

---

# 8. 核心表总览

建议至少包含以下表：

- `symbols`
- `market_candles`
- `indicator_results`
- `multi_tf_contexts`
- `strategy_events`
- `signals`
- `orders`
- `order_fills`
- `positions`
- `risk_snapshots`
- `account_snapshots`
- `cooldowns`
- `backtest_runs`
- `backtest_steps`
- `backtest_trades`
- `performance_metrics`
- `audit_logs`
- `reports`
- `config_versions`
- `event_bus_messages`
- `system_health`

---

# 9. `symbols` 表

用于维护交易标的池。

```sql
CREATE TABLE symbols (
  id BIGSERIAL PRIMARY KEY,
  symbol VARCHAR(32) NOT NULL UNIQUE,
  base_asset VARCHAR(16) NOT NULL,
  quote_asset VARCHAR(16) NOT NULL,
  market_cap_rank INT,
  volume_rank INT,
  tier VARCHAR(8) NOT NULL,
  tradable BOOLEAN NOT NULL DEFAULT TRUE,
  listed_time TIMESTAMP WITH TIME ZONE,
  delisting_flag BOOLEAN NOT NULL DEFAULT FALSE,
  correlation_group VARCHAR(32),
  source VARCHAR(64),
  version VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
````

建议索引：

* `symbol`
* `tradable`
* `tier`
* `correlation_group`

---

# 10. `market_candles` 表

用于存储标准化 K 线数据。

```sql
CREATE TABLE market_candles (
  id BIGSERIAL PRIMARY KEY,
  symbol VARCHAR(32) NOT NULL,
  timeframe VARCHAR(8) NOT NULL,
  open_time TIMESTAMP WITH TIME ZONE NOT NULL,
  close_time TIMESTAMP WITH TIME ZONE NOT NULL,
  open NUMERIC(24, 12) NOT NULL,
  high NUMERIC(24, 12) NOT NULL,
  low NUMERIC(24, 12) NOT NULL,
  close NUMERIC(24, 12) NOT NULL,
  volume NUMERIC(30, 12) NOT NULL,
  quote_volume NUMERIC(30, 12),
  trade_count BIGINT,
  taker_buy_base_volume NUMERIC(30, 12),
  taker_buy_quote_volume NUMERIC(30, 12),
  is_closed BOOLEAN NOT NULL DEFAULT TRUE,
  quality_flag VARCHAR(16) NOT NULL DEFAULT 'true',
  source VARCHAR(64) NOT NULL,
  version VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE(symbol, timeframe, open_time)
);
```

建议索引：

* `(symbol, timeframe, open_time)`
* `(timeframe, open_time)`
* `(symbol, open_time)`

建议分区：

* 按 `timeframe`
* 再按月分区或日分区

---

# 11. `indicator_results` 表

用于存储指标计算结果。

```sql
CREATE TABLE indicator_results (
  id BIGSERIAL PRIMARY KEY,
  symbol VARCHAR(32) NOT NULL,
  timeframe VARCHAR(8) NOT NULL,
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  indicator_name VARCHAR(32) NOT NULL,
  value_json JSONB NOT NULL,
  signal VARCHAR(32),
  trend VARCHAR(16),
  strength NUMERIC(18, 8),
  quality_flag VARCHAR(16) NOT NULL DEFAULT 'true',
  source VARCHAR(64) NOT NULL,
  version VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE(symbol, timeframe, ts, indicator_name, version)
);
```

`value_json` 用于保存多字段指标结果，例如 MACD、BOLL、CVD。

建议索引：

* `(symbol, timeframe, ts)`
* `(indicator_name, ts)`
* `(quality_flag)`

---

# 12. `multi_tf_contexts` 表

用于存储多周期上下文结果。

```sql
CREATE TABLE multi_tf_contexts (
  id BIGSERIAL PRIMARY KEY,
  symbol VARCHAR(32) NOT NULL,
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  market_state_4h VARCHAR(16),
  trend_state_1h VARCHAR(32),
  confirm_state_30m VARCHAR(32),
  trigger_state_15m VARCHAR(32),
  direction_bias VARCHAR(16),
  entry_mode VARCHAR(16),
  confidence_score NUMERIC(18, 8),
  quality_flag VARCHAR(16) NOT NULL DEFAULT 'true',
  context_json JSONB NOT NULL,
  source VARCHAR(64),
  version VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE(symbol, ts, version)
);
```

建议索引：

* `(symbol, ts)`
* `(trend_state_1h, ts)`
* `(direction_bias, ts)`

---

# 13. `strategy_events` 表

用于存储策略事件流，是系统审计核心表之一。

```sql
CREATE TABLE strategy_events (
  id BIGSERIAL PRIMARY KEY,
  event_id VARCHAR(64) NOT NULL UNIQUE,
  correlation_id VARCHAR(64),
  parent_event_id VARCHAR(64),
  trace_id VARCHAR(64),
  symbol VARCHAR(32),
  timeframe VARCHAR(8),
  event_type VARCHAR(64) NOT NULL,
  state_before VARCHAR(32),
  state_after VARCHAR(32),
  reason VARCHAR(256),
  priority VARCHAR(16) NOT NULL DEFAULT 'NORMAL',
  payload JSONB NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'created',
  source VARCHAR(64) NOT NULL,
  version VARCHAR(32),
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(symbol, ts)`
* `(event_type, ts)`
* `(trace_id)`
* `(correlation_id)`
* `(status, ts)`

建议分区：

* 按月分区

---

# 14. `signals` 表

用于存储交易信号结果。

```sql
CREATE TABLE signals (
  id BIGSERIAL PRIMARY KEY,
  signal_id VARCHAR(64) NOT NULL UNIQUE,
  event_id VARCHAR(64),
  symbol VARCHAR(32) NOT NULL,
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  signal_side VARCHAR(16) NOT NULL,
  signal_type VARCHAR(32) NOT NULL,
  entry_mode VARCHAR(16) NOT NULL,
  score NUMERIC(18, 8),
  confidence_score NUMERIC(18, 8),
  reason VARCHAR(256),
  quality_flag VARCHAR(16) NOT NULL DEFAULT 'true',
  signal_json JSONB NOT NULL,
  source VARCHAR(64),
  version VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(symbol, ts)`
* `(signal_side, ts)`
* `(signal_type, ts)`

---

# 15. `orders` 表

用于存储订单主记录。

```sql
CREATE TABLE orders (
  id BIGSERIAL PRIMARY KEY,
  order_id VARCHAR(64) UNIQUE,
  client_order_id VARCHAR(64) UNIQUE,
  event_id VARCHAR(64),
  symbol VARCHAR(32) NOT NULL,
  side VARCHAR(16) NOT NULL,
  order_type VARCHAR(32) NOT NULL,
  position_side VARCHAR(16),
  reduce_only BOOLEAN NOT NULL DEFAULT FALSE,
  time_in_force VARCHAR(16),
  quantity NUMERIC(30, 12) NOT NULL,
  price NUMERIC(24, 12),
  stop_price NUMERIC(24, 12),
  take_profit_price NUMERIC(24, 12),
  status VARCHAR(32) NOT NULL,
  requested_notional NUMERIC(30, 12),
  executed_notional NUMERIC(30, 12),
  strategy_state VARCHAR(32),
  strategy_version VARCHAR(32),
  risk_tag VARCHAR(32),
  exchange_payload JSONB,
  exchange_response JSONB,
  source VARCHAR(64) NOT NULL,
  version VARCHAR(32),
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(symbol, ts)`
* `(status, ts)`
* `(client_order_id)`
* `(event_id)`

---

# 16. `order_fills` 表

用于存储订单成交明细。

```sql
CREATE TABLE order_fills (
  id BIGSERIAL PRIMARY KEY,
  order_id VARCHAR(64) NOT NULL,
  client_order_id VARCHAR(64),
  symbol VARCHAR(32) NOT NULL,
  fill_id VARCHAR(64),
  side VARCHAR(16) NOT NULL,
  price NUMERIC(24, 12) NOT NULL,
  qty NUMERIC(30, 12) NOT NULL,
  quote_qty NUMERIC(30, 12),
  commission NUMERIC(30, 12),
  commission_asset VARCHAR(16),
  trade_time TIMESTAMP WITH TIME ZONE NOT NULL,
  is_maker BOOLEAN,
  source VARCHAR(64),
  version VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE(order_id, fill_id)
);
```

建议索引：

* `(order_id)`
* `(symbol, trade_time)`
* `(client_order_id)`

---

# 17. `positions` 表

用于存储当前或历史持仓状态。

```sql
CREATE TABLE positions (
  id BIGSERIAL PRIMARY KEY,
  position_id VARCHAR(64) UNIQUE,
  symbol VARCHAR(32) NOT NULL,
  side VARCHAR(16) NOT NULL,
  qty NUMERIC(30, 12) NOT NULL,
  entry_price NUMERIC(24, 12) NOT NULL,
  mark_price NUMERIC(24, 12),
  leverage NUMERIC(18, 8),
  unrealized_pnl NUMERIC(30, 12),
  realized_pnl NUMERIC(30, 12),
  stop_price NUMERIC(24, 12),
  take_profit_price NUMERIC(24, 12),
  position_age_bars INT,
  state VARCHAR(32) NOT NULL DEFAULT 'OPEN',
  strategy_state VARCHAR(32),
  entry_event_id VARCHAR(64),
  exit_event_id VARCHAR(64),
  source VARCHAR(64),
  version VARCHAR(32),
  open_ts TIMESTAMP WITH TIME ZONE,
  close_ts TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(symbol, state)`
* `(symbol, open_ts)`
* `(entry_event_id)`
* `(exit_event_id)`

---

# 18. `risk_snapshots` 表

用于存储风控快照。

```sql
CREATE TABLE risk_snapshots (
  id BIGSERIAL PRIMARY KEY,
  snapshot_id VARCHAR(64) UNIQUE,
  symbol VARCHAR(32),
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  account_equity NUMERIC(30, 12),
  available_margin NUMERIC(30, 12),
  used_margin NUMERIC(30, 12),
  daily_pnl NUMERIC(30, 12),
  weekly_pnl NUMERIC(30, 12),
  max_drawdown NUMERIC(18, 8),
  exposure_pct NUMERIC(18, 8),
  portfolio_exposure_pct NUMERIC(18, 8),
  risk_state VARCHAR(32),
  cooldown_state VARCHAR(32),
  risk_json JSONB NOT NULL,
  source VARCHAR(64),
  version VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(symbol, ts)`
* `(risk_state, ts)`
* `(cooldown_state, ts)`

---

# 19. `account_snapshots` 表

用于存储账户层快照。

```sql
CREATE TABLE account_snapshots (
  id BIGSERIAL PRIMARY KEY,
  snapshot_id VARCHAR(64) UNIQUE,
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  account_equity NUMERIC(30, 12) NOT NULL,
  available_margin NUMERIC(30, 12),
  used_margin NUMERIC(30, 12),
  unrealized_pnl NUMERIC(30, 12),
  realized_pnl NUMERIC(30, 12),
  daily_pnl NUMERIC(30, 12),
  weekly_pnl NUMERIC(30, 12),
  total_exposure_pct NUMERIC(18, 8),
  max_drawdown_pct NUMERIC(18, 8),
  account_state VARCHAR(32),
  account_json JSONB NOT NULL,
  source VARCHAR(64),
  version VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(ts)`
* `(account_state, ts)`

---

# 20. `cooldowns` 表

用于记录冷却窗口。

```sql
CREATE TABLE cooldowns (
  id BIGSERIAL PRIMARY KEY,
  cooldown_id VARCHAR(64) UNIQUE,
  symbol VARCHAR(32) NOT NULL,
  side VARCHAR(16),
  started_at TIMESTAMP WITH TIME ZONE NOT NULL,
  ended_at TIMESTAMP WITH TIME ZONE,
  duration_bars INT,
  reason VARCHAR(256),
  status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
  source VARCHAR(64),
  version VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(symbol, status)`
* `(started_at)`
* `(ended_at)`

---

# 21. `backtest_runs` 表

用于存储回测任务元信息。

```sql
CREATE TABLE backtest_runs (
  id BIGSERIAL PRIMARY KEY,
  run_id VARCHAR(64) NOT NULL UNIQUE,
  strategy_name VARCHAR(64) NOT NULL,
  strategy_version VARCHAR(32) NOT NULL,
  config_version VARCHAR(32),
  data_version VARCHAR(32),
  start_time TIMESTAMP WITH TIME ZONE NOT NULL,
  end_time TIMESTAMP WITH TIME ZONE NOT NULL,
  symbols_json JSONB NOT NULL,
  timeframe_json JSONB NOT NULL,
  initial_capital NUMERIC(30, 12) NOT NULL,
  status VARCHAR(32) NOT NULL,
  summary_json JSONB,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(strategy_name, strategy_version)`
* `(status, created_at)`
* `(start_time, end_time)`

---

# 22. `backtest_steps` 表

用于记录回测每一步的事件或状态。

```sql
CREATE TABLE backtest_steps (
  id BIGSERIAL PRIMARY KEY,
  run_id VARCHAR(64) NOT NULL,
  step_index BIGINT NOT NULL,
  symbol VARCHAR(32) NOT NULL,
  timeframe VARCHAR(8) NOT NULL,
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  state_before VARCHAR(32),
  state_after VARCHAR(32),
  event_type VARCHAR(64),
  payload JSONB,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE(run_id, step_index)
);
```

建议索引：

* `(run_id, step_index)`
* `(run_id, symbol, ts)`

---

# 23. `backtest_trades` 表

用于记录回测交易明细。

```sql
CREATE TABLE backtest_trades (
  id BIGSERIAL PRIMARY KEY,
  run_id VARCHAR(64) NOT NULL,
  trade_id VARCHAR(64) UNIQUE,
  symbol VARCHAR(32) NOT NULL,
  side VARCHAR(16) NOT NULL,
  entry_time TIMESTAMP WITH TIME ZONE NOT NULL,
  entry_price NUMERIC(24, 12) NOT NULL,
  exit_time TIMESTAMP WITH TIME ZONE,
  exit_price NUMERIC(24, 12),
  qty NUMERIC(30, 12) NOT NULL,
  leverage NUMERIC(18, 8),
  pnl NUMERIC(30, 12),
  pnl_pct NUMERIC(18, 8),
  fees NUMERIC(30, 12),
  slippage NUMERIC(30, 12),
  reason_enter VARCHAR(256),
  reason_exit VARCHAR(256),
  entry_mode VARCHAR(16),
  exit_mode VARCHAR(16),
  state_before VARCHAR(32),
  state_after VARCHAR(32),
  trade_json JSONB,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(run_id, symbol)`
* `(entry_time)`
* `(exit_time)`

---

# 24. `performance_metrics` 表

用于存储回测或实盘绩效统计。

```sql
CREATE TABLE performance_metrics (
  id BIGSERIAL PRIMARY KEY,
  run_id VARCHAR(64),
  metric_scope VARCHAR(32) NOT NULL,
  metric_name VARCHAR(64) NOT NULL,
  metric_value NUMERIC(30, 12),
  metric_json JSONB,
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  source VARCHAR(64),
  version VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE(run_id, metric_scope, metric_name)
);
```

`metric_scope` 示例：

* `global`
* `symbol`
* `side`
* `entry_mode`
* `timeframe`

---

# 25. `audit_logs` 表

用于长期审计。

```sql
CREATE TABLE audit_logs (
  id BIGSERIAL PRIMARY KEY,
  audit_id VARCHAR(64) UNIQUE,
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  module VARCHAR(64) NOT NULL,
  action VARCHAR(64) NOT NULL,
  symbol VARCHAR(32),
  event_id VARCHAR(64),
  trace_id VARCHAR(64),
  severity VARCHAR(16) NOT NULL,
  message TEXT NOT NULL,
  payload JSONB,
  source VARCHAR(64),
  version VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(ts)`
* `(module, ts)`
* `(severity, ts)`
* `(trace_id)`

---

# 26. `reports` 表

用于报表索引。

```sql
CREATE TABLE reports (
  id BIGSERIAL PRIMARY KEY,
  report_id VARCHAR(64) UNIQUE,
  report_type VARCHAR(32) NOT NULL,
  run_id VARCHAR(64),
  title VARCHAR(256),
  file_path TEXT NOT NULL,
  file_format VARCHAR(16) NOT NULL,
  summary_json JSONB,
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(report_type, ts)`
* `(run_id)`

---

# 27. `config_versions` 表

用于记录配置版本快照。

```sql
CREATE TABLE config_versions (
  id BIGSERIAL PRIMARY KEY,
  config_version VARCHAR(32) NOT NULL,
  config_name VARCHAR(64) NOT NULL,
  config_json JSONB NOT NULL,
  checksum VARCHAR(128),
  source VARCHAR(64),
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
  UNIQUE(config_version, config_name)
);
```

用途：

* 回测参数复现
* 实盘配置审计
* 历史版本追踪

---

# 28. `event_bus_messages` 表

用于持久化事件总线消息。

```sql
CREATE TABLE event_bus_messages (
  id BIGSERIAL PRIMARY KEY,
  message_id VARCHAR(64) NOT NULL UNIQUE,
  event_id VARCHAR(64) NOT NULL,
  event_type VARCHAR(64) NOT NULL,
  trace_id VARCHAR(64),
  correlation_id VARCHAR(64),
  source VARCHAR(64) NOT NULL,
  target VARCHAR(64),
  priority VARCHAR(16) NOT NULL,
  payload JSONB NOT NULL,
  status VARCHAR(32) NOT NULL,
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(event_type, ts)`
* `(trace_id)`
* `(correlation_id)`
* `(status, ts)`

---

# 29. `system_health` 表

用于记录系统运行健康状态。

```sql
CREATE TABLE system_health (
  id BIGSERIAL PRIMARY KEY,
  ts TIMESTAMP WITH TIME ZONE NOT NULL,
  component VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  latency_ms NUMERIC(18, 8),
  error_count INT,
  warning_count INT,
  health_json JSONB,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
```

建议索引：

* `(component, ts)`
* `(status, ts)`

---

# 30. 写入边界

不同模块只允许写入自己负责的表。

建议边界如下：

* data layer：`market_candles`, `symbols`
* indicator layer：`indicator_results`
* context layer：`multi_tf_contexts`
* signal layer：`signals`
* state machine：`strategy_events`
* risk layer：`risk_snapshots`, `cooldowns`, `positions`
* execution layer：`orders`, `order_fills`, `positions`
* backtest layer：`backtest_runs`, `backtest_steps`, `backtest_trades`, `performance_metrics`
* audit layer：`audit_logs`, `event_bus_messages`, `system_health`
* config layer：`config_versions`
* reporting layer：`reports`

禁止跨层乱写。

---

# 31. 事务要求

关键写入必须具备事务一致性。

例如：

* 开仓单创建 + 策略事件记录 + 订单记录，必须尽量同事务提交
* 成交回报 + 持仓更新 + 风控快照，必须保持一致
* 止损触发 + 平仓记录 + 冷却开启，必须关联一致

若某一步失败，必须有补偿日志或重试机制。

---

# 32. 幂等性要求

数据库写入必须支持幂等。

建议：

* 事件表使用 `event_id`
* 订单表使用 `client_order_id`
* 回测运行使用 `run_id`
* 快照表使用 `snapshot_id`

对于重复写入：

* 先查唯一键
* 再决定插入或更新
* 不允许重复生成业务记录

---

# 33. 分区与归档

大表建议分区：

* `market_candles`
* `strategy_events`
* `orders`
* `order_fills`
* `audit_logs`
* `event_bus_messages`

建议归档策略：

* 热数据保留 30 ~ 90 天
* 温数据保留 6 ~ 12 个月
* 冷数据长期保留
* 归档数据压缩存储

归档后仍应可查询审计关键字段。

---

# 34. 索引原则

索引只加在高频查询字段上。

优先索引：

* `symbol`
* `ts`
* `event_type`
* `status`
* `trace_id`
* `run_id`
* `client_order_id`
* `order_id`

禁止：

* 无节制加索引
* 对大 JSON 字段盲目建索引
* 只为图省事而创建冗余索引

---

# 35. JSON 字段使用规范

JSON 字段只用于承载扩展结构，不用于核心过滤逻辑。

适用场景：

* 指标复合结果
* 策略上下文附加信息
* 执行原始回包
* 回测摘要
* 审计扩展字段

禁止：

* 用 JSON 代替核心字段
* 把核心查询逻辑藏进 JSON
* 不断扩散无结构 JSON

---

# 36. 数据保留建议

建议默认保留策略：

* K 线原始数据：长期
* 指标结果：6 ~ 12 个月
* 策略事件：12 个月以上
* 订单与成交：长期
* 回测结果：长期
* 审计日志：长期
* 系统健康：3 ~ 6 个月

可按存储成本和合规要求调整。

---

# 37. 版本迁移要求

任何 schema 变更都必须满足：

* 有 migration 脚本
* 有回滚脚本
* 有版本号
* 有兼容说明
* 有测试验证

禁止直接改生产表结构而无迁移记录。

---

# 38. 数据一致性检查

系统启动或任务执行前，应做以下检查：

* 表是否存在
* 索引是否存在
* 版本是否匹配
* 必要字段是否齐全
* 数据是否可写
* 连接是否正常

若不一致，应进入安全模式或拒绝启动。

---

# 39. 查询模式建议

高频查询通常包括：

* 最近 N 根 K 线
* 最近指标结果
* 当前持仓状态
* 最近策略事件
* 最近订单与成交
* 当前风险快照
* 当前冷却状态
* 当前回测结果

因此应优先围绕这些查询模式设计索引。

---

# 40. 禁止项

禁止：

* 用一个超级大表塞所有业务
* 把执行层临时状态写进长期主表
* 把回测和实盘记录混在一起不区分来源
* 用数据库字段补丁修业务逻辑
* 让策略模块直接修改原始历史数据
* 把 JSON 当成万能存储
* 没有唯一键就写业务主记录

---

# 41. 推荐扩展表

如后续需要更细粒度分析，可扩展：

* `market_regime_history`
* `signal_scores`
* `trade_decisions`
* `slippage_records`
* `funding_rates`
* `open_interest_snapshots`
* `correlation_matrix_snapshots`

这些表可作为增强模块，不应破坏核心 schema。

---

# 42. 结论

数据库是系统记忆，不是系统大脑。

大脑在策略层，记忆在数据库层。

数据库必须稳定、简洁、可审计、可迁移。

任何脱离契约的写入，最终都会变成新的屎山。


