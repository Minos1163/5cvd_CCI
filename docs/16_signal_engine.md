下面是重新生成的 `docs/16_signal_engine.md` 完整版本，直接可放进仓库。

````md
# Signal Engine

Version: V1.0

---

# 1. 目的

本文件定义信号引擎的职责、输入、输出、决策边界与行为约束，确保：

- 信号生成逻辑统一、可解释、可回放
- 不同周期的判断能够被稳定合并
- 策略层只生成交易意图，不直接执行下单
- direct / probe / wait / no-trade 的含义明确
- 回测与实盘使用同一套信号逻辑
- 避免旧系统那种“信号层、watchlist 层、promotion 层、仓位层互相打架”的问题

信号引擎只负责回答一个问题：

这根 bar 现在该不该交易，若要交易，是 probe 还是 direct。

---

# 2. 总原则

1. 信号必须可解释。
2. 信号必须结构化。
3. 信号必须来自已完成数据。
4. 信号必须服从多周期上下文。
5. 信号不得越权决定仓位以外的事情。
6. 信号不得在执行层被重新解释。
7. 信号不得依赖隐式全局状态。
8. 信号不得引入多层补丁和例外逻辑。
9. 信号必须和状态机强绑定。
10. 信号必须与风控、仓位、执行保持契约一致。

---

# 3. 信号引擎职责边界

信号引擎负责：

- 接收多周期上下文
- 读取指标结果
- 识别趋势、动量、波动、资金流结构
- 输出交易意图
- 输出信号强度
- 输出 probe / direct / wait / no-trade 决策
- 输出原因和证据字段
- 为状态机提供标准化输入

信号引擎不负责：

- 计算最终仓位
- 设置止损止盈
- 下单
- 撤单
- 持仓同步
- 账户余额更新
- 风险级别最终裁决
- 交易所适配

---

# 4. 输入数据

信号引擎的输入必须来自标准化的策略上下文对象。

建议输入结构：

```text
StrategyContext
````

至少包含：

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
* `quality_flag`

---

# 5. 输出数据

信号引擎必须输出标准化信号对象。

建议对象：

```text
SignalResult
```

至少包含：

* `symbol`
* `timestamp`
* `signal_type`
* `signal_side`
* `entry_mode`
* `score`
* `confidence`
* `reason`
* `sub_reasons`
* `required_state`
* `quality_flag`
* `metadata`

其中：

* `signal_type` 取值示例：

  * `LONG`
  * `SHORT`
  * `WAIT`
  * `NO_TRADE`
* `signal_side` 取值示例：

  * `LONG`
  * `SHORT`
  * `NONE`
* `entry_mode` 取值示例：

  * `PROBE`
  * `DIRECT`
  * `NONE`

---

# 6. 信号层级

信号分为四个等级：

## 6.1 NO_TRADE

明确不交易。

适用场景：

* 方向冲突
* 数据质量差
* 波动异常
* 风险超限
* 冷却期未结束
* 高周期不成立
* 资金流明显反向

## 6.2 WAIT

暂时观察，不进场。

适用场景：

* 高周期方向成立
* 但低周期触发未完成
* 或结构尚未确认
* 或价格位置仍不理想

## 6.3 PROBE

小仓试探。

适用场景：

* 高周期同向
* 中周期已确认
* 低周期已有触发迹象
* 但入场结构仍不够完美
* 适合用 25% 标准仓去验证

## 6.4 DIRECT

正式开仓。

适用场景：

* 多周期同向
* 方向、确认、触发三层齐备
* 资金流同向
* 结构完整
* 风险允许
* 可执行仓位满足最小名义额

---

# 7. 信号引擎的决策流程

推荐决策流程如下：

1. 读取多周期上下文
2. 检查数据质量
3. 检查冷却状态
4. 检查组合风险
5. 判断 4H 背景
6. 判断 1H 方向
7. 判断 30m 确认
8. 判断 15m 触发
9. 判断 CVD 资金流
10. 判断 MACD、CCI、RSI、BOLL 的结构状态
11. 汇总为信号结果
12. 输出 WAIT / PROBE / DIRECT / NO_TRADE
13. 记录证据字段

这个顺序必须固定，不得随意调整。

---

# 8. 多周期职责

## 8.1 4H

4H 只负责市场背景，不负责最终开仓。

4H 输出仅应包含：

* `BULL`
* `BEAR`
* `NEUTRAL`

4H 的作用：

* 识别大方向
* 识别震荡背景
* 过滤极端反向环境

4H 不得成为硬性 veto 的唯一来源。

---

## 8.2 1H

1H 负责方向确认。

1H 输出：

* `LONG_ALLOWED`
* `SHORT_ALLOWED`
* `NO_TRADE`

1H 是信号引擎的重要门槛，但不是唯一门槛。

---

## 8.3 30m

30m 负责趋势质量确认。

30m 主要看：

* MACD 动量方向
* CCI 强弱
* BOLL 中轨与带宽
* CVD 是否持续同向

30m 的作用是告诉系统：

这不是一个短暂脉冲，而是一个可跟随的方向。

---

## 8.4 15m

15m 负责触发。

15m 主要看：

* 是否回踩后重新恢复
* 是否脱离震荡区
* 是否突破或重新站上关键位
* 是否出现入场所需的微结构确认

15m 只负责“现在能不能进”，不负责“长期方向是否正确”。

---

# 9. 指标职责

本系统只允许以下指标承担明确职责。

## 9.1 MACD

职责：

* 趋势方向
* 动量变化
* 金叉/死叉
* 动量减弱

MACD 适合判断：

* 当前方向是否持续
* 趋势是否开始衰弱
* 多周期是否同向

---

## 9.2 CCI

职责：

* 趋势强度
* 极端偏离
* 回归中枢
* 动量恢复

CCI 适合判断：

* 趋势是否足够强
* 当前是否过热
* 回调后是否重新恢复

---

## 9.3 BOLL

职责：

* 波动收缩
* 波动扩张
* 中轨重测
* 突破结构

BOLL 适合判断：

* 是否处于 squeeze 后启动阶段
* 是否已脱离中轨压制
* 是否在扩张趋势中

---

## 9.4 RSI

职责：

* 超买超卖
* 回调质量
* 中轴恢复
* 是否过热

RSI 适合判断：

* 进场是否过度追涨杀跌
* 回调是否足够健康
* 是否有重新站回 50 附近的力量

---

## 9.5 CVD

职责：

* 主动买卖力量
* 资金流方向
* 背离
* 吸筹 / 派发痕迹

CVD 是方向确认的重要辅助指标。

若价格上涨但 CVD 持续走弱，则信号应降级。

---

## 9.6 ATR

职责：

* 波动率判断
* 止损距离
* 仓位缩放

ATR 不允许直接决定方向，只能参与风险与仓位。

---

# 10. 信号评分

信号引擎可以使用评分，但评分必须是辅助，而不是黑箱。

推荐评分结构：

```text
signal_score =
  trend_score
  + confirm_score
  + trigger_score
  + flow_score
  + volatility_score
```

建议拆分为五部分：

* `trend_score`：来自 4H / 1H
* `confirm_score`：来自 30m
* `trigger_score`：来自 15m
* `flow_score`：来自 CVD
* `volatility_score`：来自 ATR 与 BOLL

总分只用于分类，不直接替代状态机。

---

# 11. 信号分类规则

## 11.1 LONG 信号

满足以下基本条件时，才允许生成 LONG 候选：

* 4H 非明显反向
* 1H 为 long allowed
* 30m 趋势质量为正
* 15m 已触发
* CVD 同向
* 风险未超限

LONG 候选再分为：

* `WAIT_LONG`
* `PROBE_LONG`
* `DIRECT_LONG`

---

## 11.2 SHORT 信号

与 LONG 对称。

满足：

* 4H 非明显反向
* 1H 为 short allowed
* 30m 趋势质量为负
* 15m 已触发
* CVD 同向
* 风险未超限

SHORT 候选再分为：

* `WAIT_SHORT`
* `PROBE_SHORT`
* `DIRECT_SHORT`

---

## 11.3 WAIT 信号

满足方向，但触发不足。

典型场景：

* 1H 已成立
* 30m 尚可
* 15m 还没完成触发
* 或 RSI / CCI 仍偏热
* 或 BOLL 结构未完成

---

## 11.4 NO_TRADE 信号

明确禁止交易。

典型场景：

* 方向冲突
* 资金流反向
* 波动异常
* 数据质量差
* 冷却期未结束
* 组合风险触发
* 低周期假突破

---

# 12. Probe 与 Direct 判定

## 12.1 Probe

Probe 是小仓验证，不是弱化版 direct。

允许条件：

* 高周期方向成立
* 中周期确认尚未完全成熟
* 15m 已出现触发迹象
* 资金流同向，但尚未达到最强确认
* 当前适合先试探

Probe 的意义是用更低成本验证方向是否继续。

---

## 12.2 Direct

Direct 是正式开仓。

允许条件：

* 4H 背景不反向
* 1H 方向确认
* 30m 质量确认
* 15m 触发确认
* CVD 同向
* RSI 未过热
* BOLL 结构合理
* 风险模块通过

Direct 必须是“多层确认后的正式动作”。

---

# 13. 信号证据字段

每个信号都必须记录证据字段，便于复盘。

建议字段：

* `symbol`
* `timestamp`
* `signal_type`
* `signal_side`
* `entry_mode`
* `score`
* `confidence`
* `market_state_4h`
* `trend_state_1h`
* `confirm_state_30m`
* `trigger_state_15m`
* `macd_state`
* `cci_state`
* `boll_state`
* `rsi_state`
* `cvd_state`
* `atr_state`
* `reason`
* `sub_reasons`

这些字段必须能解释为什么是这个信号，而不是别的信号。

---

# 14. 常见子原因

建议标准化子原因集合。

示例：

* `TREND_ALIGNED`
* `TREND_CONFLICT`
* `MOMENTUM_STRONG`
* `MOMENTUM_WEAK`
* `FLOW_CONFIRMED`
* `FLOW_DIVERGENCE`
* `VOLATILITY_TOO_HIGH`
* `VOLATILITY_TOO_LOW`
* `TRIGGER_READY`
* `TRIGGER_NOT_READY`
* `RSI_OVERHEATED`
* `RSI_RECOVERY`
* `CCI_STRONG`
* `CCI_EXTREME`
* `BOLL_EXPANSION`
* `BOLL_CONTRACTION`
* `COOLDOWN_ACTIVE`
* `RISK_BLOCKED`
* `DATA_INVALID`

---

# 15. 与状态机的关系

信号引擎输出的是意图，状态机决定是否进入对应状态。

对应关系：

* `WAIT` -> `WATCH_*`
* `PROBE` -> `PROBE_*`
* `DIRECT` -> `DIRECT_*`
* `NO_TRADE` -> `FLAT` 或保持当前状态

信号引擎不得跳过状态机直接下单。

---

# 16. 与仓位模块的关系

信号引擎只告诉仓位模块：

* 是 probe 还是 direct
* 是 long 还是 short
* 允许不允许交易
* 证据是什么

仓位模块根据：

* entry mode
* stop distance
* 账户风险
* 组合暴露
* 最小名义额

计算最终数量。

---

# 17. 与执行层的关系

执行层只执行信号和状态机联合生成的订单指令。

执行层不得：

* 修改信号类型
* 重写 entry mode
* 擅自把 probe 升格成 direct
* 擅自改变 long / short
* 擅自添加新的交易理由

---

# 18. 数据质量门

若任一关键输入质量不足，则信号必须降级。

质量门包括：

* K 线缺失
* 指标缺失
* 周期错位
* CVD 数据不完整
* ATR 不可用
* 风控快照过期

降级结果可能是：

* 直接 `NO_TRADE`
* 仅 `WAIT`
* 仅允许 `PROBE`
* 禁止 `DIRECT`

---

# 19. 反追涨杀跌约束

信号引擎必须禁止无脑追单。

典型限制：

* RSI 过热时禁止直接开多
* RSI 过冷时禁止直接开空
* 价格远离 BOLL 中轨时若无资金流确认，降级为 WAIT
* 价格已大幅偏离均值时只允许更高确认度的信号

---

# 20. 反背离约束

若价格和 CVD、MACD、CCI 出现明显背离，信号必须降级。

例如：

* 价格创新高
* 但 CVD 未创新高
* 且 MACD 动量减弱

则不允许直接开多，必要时进入 WAIT 或 NO_TRADE。

---

# 21. 信号生成顺序

建议先后顺序：

1. 数据质量检查
2. 风险检查
3. 4H 背景判断
4. 1H 方向判断
5. 30m 确认判断
6. 15m 触发判断
7. CVD / RSI / CCI / BOLL 联合确认
8. 生成信号结果
9. 分配 entry mode
10. 写入事件与日志

---

# 22. 禁止项

禁止：

* 多层 watchlist / promotion 套路
* 方向分与执行分互相冲突
* 低周期单独推翻高周期背景
* 将信号层当成仓位层
* 将信号层当成执行层
* 把临时例外写进信号主逻辑
* 用“看起来像趋势”的模糊描述代替结构化判断

---

# 23. 单元测试要求

信号引擎必须覆盖以下测试：

* LONG / SHORT / WAIT / NO_TRADE
* probe / direct 分类
* 方向冲突
* 资金流背离
* 低波动压缩
* 高波动扩张
* 数据缺失
* 冷却期阻断
* 风险超限
* 高周期反向
* 追涨杀跌阻断

---

# 24. 示例信号

示例一：Direct Long

```text
signal_type = LONG
signal_side = LONG
entry_mode = DIRECT
score = 0.86
reason = ALL_LAYERS_ALIGNED
```

示例二：Probe Short

```text
signal_type = SHORT
signal_side = SHORT
entry_mode = PROBE
score = 0.61
reason = HIGHER_TF_CONFIRMED_LOWER_TF_PARTIAL
```

示例三：Wait

```text
signal_type = WAIT
signal_side = NONE
entry_mode = NONE
score = 0.44
reason = 1H_CONFIRMED_15M_NOT_READY
```

示例四：No Trade

```text
signal_type = NO_TRADE
signal_side = NONE
entry_mode = NONE
score = 0.12
reason = FLOW_DIVERGENCE_AND_RISK_BLOCKED
```

---

# 25. 结论

信号引擎不是预测器。

它只是把多周期、多指标、多风险约束下的交易意图表达清楚。

信号越简单，策略越可维护。

信号越清晰，系统越不容易再次变成屎山。