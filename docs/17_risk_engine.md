下面是重新生成的 `docs/17_risk_engine.md` 完整版本，直接可放进仓库。

````md
# Risk Engine

Version: V1.0

---

# 1. 目的

本文件定义风险引擎的职责、输入、输出、约束与执行边界，确保：

- 每一笔交易的风险在开仓前就被量化
- 仓位、止损、止盈、减仓、冷却、组合暴露有统一约束
- 风险模块不与信号模块、执行模块职责混淆
- 回测与实盘使用同一套风险逻辑
- 系统不会再次出现“信号层一套、仓位层一套、止损层一套、执行层一套”的割裂状态

风险引擎只负责回答一个问题：

这笔交易是否值得承担，承担多少，如何退出，什么时候必须停。

---

# 2. 风险引擎总原则

1. 风险优先于收益。
2. 先定义亏损边界，再定义盈利目标。
3. 风险必须可计算、可记录、可复盘。
4. 风险必须和波动率、账户规模、仓位模式联动。
5. 风险引擎不得越权生成交易信号。
6. 风险引擎不得直接下单。
7. 风险引擎不得偷偷修改策略意图。
8. 风险引擎不得依赖隐式全局变量。
9. 风险引擎不得使用与回测不同的规则。
10. 风险引擎必须保持简洁和单一职责。

---

# 3. 风险引擎职责边界

风险引擎负责：

- 计算单笔风险预算
- 计算止损距离
- 计算建议仓位
- 判断是否允许开仓
- 判断是否允许加仓
- 判断是否需要减仓
- 判断是否需要强制退出
- 维护冷却规则
- 维护组合暴露限制
- 维护日内/周内亏损限制
- 输出风险决策结果

风险引擎不负责：

- 判断趋势方向
- 判断具体入场结构
- 生成买卖信号
- 生成订单
- 执行交易
- 维护交易所连接
- 重新解释信号层的含义

---

# 4. 风险输入

风险引擎必须接收标准化输入对象。

建议输入结构：

```text
RiskContext
````

至少包含：

* `symbol`
* `timestamp`
* `signal_type`
* `signal_side`
* `entry_mode`
* `account_equity`
* `available_margin`
* `used_margin`
* `open_positions`
* `portfolio_exposure`
* `symbol_exposure`
* `daily_pnl`
* `weekly_pnl`
* `max_drawdown`
* `atr`
* `stop_pct`
* `quality_flag`
* `cooldown_state`
* `market_state_4h`
* `trend_state_1h`
* `confirm_state_30m`
* `trigger_state_15m`

---

# 5. 风险输出

风险引擎必须输出标准化结果对象。

建议对象：

```text
RiskResult
```

至少包含：

* `allow_trade`
* `allow_add`
* `allow_reduce`
* `allow_exit`
* `risk_level`
* `risk_reason`
* `risk_score`
* `position_size_factor`
* `stop_distance`
* `stop_pct`
* `take_profit_plan`
* `cooldown_required`
* `cooldown_bars`
* `portfolio_blocked`
* `metrics_snapshot`
* `metadata`

其中：

* `allow_trade` 表示是否允许开新仓
* `allow_add` 表示是否允许加仓
* `allow_reduce` 表示是否建议减仓
* `allow_exit` 表示是否允许/建议退出
* `risk_level` 表示风险等级
* `risk_reason` 表示阻断或允许的理由
* `position_size_factor` 表示最终仓位缩放系数

---

# 6. 风险等级定义

建议使用以下风险等级：

* `LOW`
* `NORMAL`
* `HIGH`
* `EXTREME`
* `BLOCKED`

含义：

## LOW

* 可正常交易
* 风险处于可接受区间

## NORMAL

* 可交易
* 但仍需遵守标准仓位和止损规则

## HIGH

* 可以交易，但必须缩小仓位或转为 probe
* 可能需要更严格的止损或更短的持有期

## EXTREME

* 不建议开新仓
* 已有持仓应考虑减仓或收紧止损

## BLOCKED

* 直接禁止交易
* 只允许退出或减仓

---

# 7. 风险决策顺序

风险引擎的评估顺序必须固定：

1. 数据质量检查
2. 冷却检查
3. 账户层风险检查
4. 组合层风险检查
5. 单币层风险检查
6. 波动率检查
7. 止损距离检查
8. 仓位可执行性检查
9. 加仓/减仓/退出检查
10. 输出最终风险结果

这个顺序不得随意改变。

---

# 8. 数据质量风险

如果输入数据质量差，风险引擎必须降级或阻断。

常见情况：

* K 线缺失
* 指标缺失
* 周期错位
* CVD 不完整
* ATR 不可用
* 持仓快照过期
* 风险快照过期

处理原则：

* 关键字段缺失 -> `BLOCKED`
* 非关键字段缺失 -> 降级
* 数据陈旧 -> `BLOCKED` 或 `HIGH`
* 数据不一致 -> `BLOCKED`

---

# 9. 冷却风险

冷却是防止连续错误交易的重要机制。

触发场景：

* 刚止损
* 连续亏损
* 高波动异常退出
* 方向反转后的保护期
* 交易所异常导致的重试失败

冷却期间：

* 禁止同方向立即重开
* 默认禁止 probe 升级
* 仅允许恢复后重新评估

建议冷却单位：

* 以 15m bar 计数

建议默认值：

* 普通止损后：`3 ~ 6` 根 15m bar
* 高波动止损后：更长
* 极端异常后：按人工或系统恢复

---

# 10. 账户层风险

账户层风险用于控制总资产安全。

必须监控以下指标：

* account equity
* available margin
* realized pnl
* unrealized pnl
* daily pnl
* weekly pnl
* max drawdown
* margin usage

账户层规则示例：

* 日亏损达到阈值 -> 禁止新开仓
* 周亏损达到阈值 -> 禁止新开仓并考虑减仓
* 总回撤超过阈值 -> 进入保护模式
* 可用保证金不足 -> 拒绝新仓

建议默认参数：

* `daily_loss_limit_pct = 0.05`
* `weekly_loss_limit_pct = 0.12`
* `max_drawdown_pct = 0.20`

---

# 11. 组合层风险

组合层风险用于防止多个仓位叠加失控。

至少监控：

* 总暴露
* 单币暴露
* 同方向暴露
* 高相关组暴露
* 同时持仓数量
* 单日总风险暴露

建议默认限制：

* 单币最大暴露：`20%`
* 账户总暴露：`75%`
* 同时持仓数量：`5`
* 单笔风险：`1%`

若组合风险触发：

* 禁止新开仓
* 可以减仓
* 极端情况下强制退出部分仓位

---

# 12. 单币风险

单币风险用于防止某个币种把组合拖死。

需要重点监控：

* 该币种当前持仓数量
* 该币种累计风险
* 该币种与其他持仓的相关性
* 该币种的波动率
* 该币种近期是否连续亏损

若同一币种短时间内多次亏损：

* 提高风险等级
* 缩小下一笔仓位
* 或进入冷却

---

# 13. 波动率风险

波动率是决定风险大小的重要因素。

波动率指标主要使用：

* ATR
* BOLL 带宽
* 价格对均值偏离
* 长影线比例
* 突发跳动

规则：

* 波动越大，仓位越小
* 波动越大，止损越宽
* 波动太小，可能无趋势或无效率
* 波动异常放大时，不建议直接开新仓

---

# 14. 止损风险

止损必须由风险引擎统一控制。

止损计算建议：

```text
stop_distance = ATR * stop_atr_mult
stop_pct = stop_distance / entry_price
```

要求：

* 止损不能太小，小到被噪声轻易扫掉
* 止损不能太大，大到使风险失控
* 止损距离必须与仓位大小反向联动
* 止损必须在开仓前确定

默认建议：

* `stop_atr_mult = 1.2 ~ 2.0`
* 最小止损比例：`0.5%`

若止损不合理：

* 过小 -> 风险引擎应缩小仓位或阻断
* 过大 -> 风险引擎应缩小仓位或阻断

---

# 15. 仓位风险

仓位风险由以下因素共同决定：

* account equity
* stop distance
* entry mode
* symbol tier
* leverage
* portfolio exposure
* volatility state

基础公式：

```text
risk_amount = account_equity * risk_per_trade_pct
standard_notional = risk_amount / stop_pct
```

再根据：

* `probe`
* `direct`
* `tier factor`
* `account risk factor`
* `portfolio risk factor`

得到最终仓位。

风险引擎只给出建议，仓位模块负责最终数量计算。

---

# 16. Probe 风险规则

Probe 是受控试探，不是随便缩小的 direct。

Probe 风险特点：

* 风险预算更低
* 允许在趋势未完全确认时尝试
* 失败后应快速退出
* 成功后可重新评估是否升级

Probe 建议仓位：

* `25% standard size`

Probe 风险限制：

* 不能因为 floor/cap 被抬成大仓
* 不能因为补单逻辑变成伪 direct
* 不能在冷却未结束时继续试探

---

# 17. Direct 风险规则

Direct 是正式开仓。

Direct 允许前提：

* 多周期方向同向
* 15m 触发成立
* 30m 确认成立
* 资金流方向同向
* 波动率可接受
* 账户与组合风险允许

Direct 风险特点：

* 使用标准风险预算
* 允许正常持有与管理
* 可参与后续分批止盈与移动止损

---

# 18. 加仓风险

加仓只能在风险可控且原方向继续成立时进行。

允许条件：

* 持仓已经盈利
* 多周期方向未反转
* 15m/30m 继续支持
* 组合暴露仍可承受
* 当前波动率未失控

禁止场景：

* 亏损加仓
* 逆势摊平
* 试图用加仓修复错误入场
* 组合暴露已高时继续加仓

---

# 19. 减仓风险

减仓用于保护本金，而不是为了“赌更大”。

触发条件：

* 风险等级提升
* 方向开始衰弱
* 价格结构被破坏
* 波动异常
* 组合风险超限
* BTC 或市场整体风险急剧上升

默认减仓比例：

* `25%`
* `50%`

建议：

* 风险高时优先减仓
* 若减仓后风险仍高，再考虑退出
* 不要用复杂分层减仓把系统搞得不可验证

---

# 20. 强制退出风险

强制退出是最高优先级动作。

触发条件包括：

* 止损触发
* 方向彻底反转
* 组合风险严重超限
* 单币异常波动
* 交易所执行异常
* 账户异常
* 风控模块不可用

强制退出后：

* 必须写日志
* 必须更新状态
* 必须触发冷却
* 必须保留审计信息

---

# 21. 退出优先级

风险动作优先级从高到低：

1. 强制退出
2. 组合风险退出
3. 单币风险退出
4. 波动异常退出
5. 方向反转退出
6. 减仓
7. 移动止损
8. 分批止盈

低优先级动作不得覆盖高优先级动作。

---

# 22. 风险评分

风险引擎可以输出风险分数，但分数只用于分类，不用于黑箱决策。

建议评分组成：

* `account_risk_score`
* `portfolio_risk_score`
* `symbol_risk_score`
* `volatility_risk_score`
* `cooldown_risk_score`
* `data_quality_risk_score`

总风险分示例：

```text
risk_score = account + portfolio + symbol + volatility + cooldown + data_quality
```

建议映射：

* `0 ~ 1` -> `LOW`
* `2 ~ 3` -> `NORMAL`
* `4 ~ 5` -> `HIGH`
* `6 ~ 7` -> `EXTREME`
* `>= 8` -> `BLOCKED`

---

# 23. 风险快照

每次风险评估必须生成快照。

建议字段：

* `symbol`
* `timestamp`
* `account_equity`
* `available_margin`
* `daily_pnl`
* `weekly_pnl`
* `max_drawdown`
* `portfolio_exposure`
* `symbol_exposure`
* `atr`
* `stop_pct`
* `risk_score`
* `risk_level`
* `allow_trade`
* `allow_add`
* `allow_reduce`
* `allow_exit`
* `risk_reason`

快照必须落库，供回测与实盘复盘使用。

---

# 24. 与信号引擎的关系

信号引擎负责告诉风险引擎：

* 方向
* entry mode
* 证据
* 候选意图

风险引擎负责告诉信号引擎：

* 是否允许
* 风险等级
* 是否降级为 probe
* 是否阻断
* 是否需要冷却

风险引擎不得反过来生成信号，也不得把自己的阻断重新解释成另一个信号。

---

# 25. 与仓位模块的关系

风险引擎负责输出风险约束，仓位模块负责计算最终数量。

风险引擎提供：

* `stop_pct`
* `position_size_factor`
* `allow_trade`
* `allow_add`
* `allow_reduce`
* `allow_exit`

仓位模块接收这些值后再计算：

* `final_notional`
* `final_qty`

风险引擎不得替仓位模块做最终精度修正。

---

# 26. 与执行层的关系

执行层只执行风险引擎和仓位模块已经确认的结果。

执行层不得：

* 自己修改止损
* 自己修改仓位
* 自己重算风险
* 自己推测是否应该继续交易

执行层只负责把风险决定变成订单和日志。

---

# 27. 保护模式

当风险引擎进入保护模式时，应采取以下动作之一或多个：

* 禁止新开仓
* 仅允许退出
* 仅允许减仓
* 进入冷却
* 强化风控日志
* 通知上层系统或人工

保护模式应在以下情况触发：

* 连续风控失败
* 数据质量持续异常
* 账户风险严重超限
* 组合暴露失控
* 交易所异常导致风险不可评估

---

# 28. 常见错误模式

必须避免以下错误：

## 28.1 风险与信号混合

风险引擎不应承担趋势判断责任。

## 28.2 仓位与风险脱节

止损变宽但仓位不缩小，风险失控。

## 28.3 多套风险规则互相覆盖

fixed SL、ATR SL、beta risk、exit guard 多头并行。

## 28.4 风险模块偷偷改策略意图

本来是 probe，被改成 direct。

## 28.5 风险模块与执行层重复计算

同一个风险在不同模块里被算两次，结果不一致。

---

# 29. 测试要求

风险引擎必须覆盖以下测试：

* 日亏损阈值触发
* 周亏损阈值触发
* 总回撤阈值触发
* 单币暴露超限
* 组合暴露超限
* 高波动阻断
* 冷却阻断
* probe 风险缩放
* direct 风险通过
* 减仓触发
* 强制退出触发
* 数据质量阻断

---

# 30. 示例决策

示例一：允许 direct

```text
allow_trade = true
risk_level = NORMAL
position_size_factor = 1.0
risk_reason = "FULL_CONFIRMATION_AND_RISK_OK"
```

示例二：只允许 probe

```text
allow_trade = true
risk_level = HIGH
position_size_factor = 0.25
risk_reason = "TREND_OK_BUT_VOLATILITY_HIGH"
```

示例三：禁止交易

```text
allow_trade = false
risk_level = BLOCKED
risk_reason = "DAILY_LOSS_LIMIT_REACHED"
```

示例四：建议减仓

```text
allow_reduce = true
risk_level = EXTREME
risk_reason = "DIRECTION_WEAKENED_AND_PORTFOLIO_EXPOSURE_HIGH"
```

---

# 31. 禁止项

禁止：

* 风险模块自己下单
* 风险模块自己生成信号
* 风险模块和执行模块各自独立改仓位
* 风险模块把 probe 悄悄升成 direct
* 风险模块为“方便执行”降低风控标准
* 风险模块在不同路径上使用不同公式

---

# 32. 结论

风险引擎的价值不在于让系统更多交易，而在于让系统少犯错、少失控、少出现不可解释行为。

风险引擎必须像闸门一样清晰：

能过就是能过，不能过就是不能过。

不能再出现旧系统那种：

信号能过、仓位卡住、执行修正、止损另算、最后没人知道到底是谁决定了这笔交易。

