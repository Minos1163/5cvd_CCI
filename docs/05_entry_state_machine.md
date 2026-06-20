# Entry State Machine

Version: V1.0

---

# 1. 目的

本文件定义系统的开仓状态机规则，规定：

- 交易从观察到开仓再到持仓管理，必须经过哪些状态
- 每个状态的职责是什么
- 状态之间如何转换
- 哪些转换允许，哪些转换禁止
- 状态机如何与信号层、风控层、仓位层、执行层协作
- 如何避免旧系统那种“信号、watchlist、promotion、仓位、执行各自乱跳”的问题

状态机是系统开仓逻辑的主骨架。

如果状态机不清晰，整个策略一定会再次变成屎山。

---

# 2. 状态机总原则

1. 每次只能处于一个主状态。
2. 状态转移必须有明确原因。
3. 状态转移必须可记录、可回放、可审计。
4. 状态机不得直接做趋势判断。
5. 状态机不得直接计算仓位。
6. 状态机不得直接下单。
7. 状态机必须服从多周期结果、信号结果和风控结果。
8. 状态机不得靠补丁逻辑维持。
9. 状态机必须和回测、实盘保持一致。
10. 状态机必须尽量简单、稳定、可解释。

---

# 3. 状态机职责边界

状态机负责：

- 维护当前交易状态
- 接收信号层输出
- 根据风控结果决定是否允许转移
- 决定进入 probe 还是 direct
- 决定是否进入持仓管理
- 决定是否进入退出状态
- 决定是否回到 FLAT
- 记录每次状态转移

状态机不负责：

- 计算指标
- 判断趋势方向
- 决定最终仓位
- 生成订单
- 处理交易所返回
- 自己发明新的信号逻辑
- 自己修正仓位或风险规则

---

# 4. 状态定义

系统的主状态集如下：

- `FLAT`
- `WATCH_LONG`
- `WATCH_SHORT`
- `PROBE_LONG`
- `PROBE_SHORT`
- `DIRECT_LONG`
- `DIRECT_SHORT`
- `MANAGE_LONG`
- `MANAGE_SHORT`
- `EXIT_LONG`
- `EXIT_SHORT`

下面分别定义。

---

# 5. FLAT

## 5.1 定义

`FLAT` 表示当前没有持仓，且当前不处于任何已执行交易链路中。

这是状态机的默认初始状态。

---

## 5.2 职责

在 `FLAT` 状态下，系统负责：

- 观察信号
- 等待多周期确认
- 判断是否进入 WATCH
- 检查风控是否允许开新仓
- 检查是否处于冷却期

---

## 5.3 允许转移

`FLAT` 可以转移到：

- `WATCH_LONG`
- `WATCH_SHORT`
- `PROBE_LONG`
- `PROBE_SHORT`
- `DIRECT_LONG`
- `DIRECT_SHORT`

具体取决于信号和风控结果。

---

## 5.4 禁止行为

`FLAT` 状态下不允许：

- 直接进入持仓管理
- 直接进入退出状态
- 跳过信号和风控直接下单
- 同时进入多个方向状态

---

# 6. WATCH_LONG

## 6.1 定义

`WATCH_LONG` 表示：

- 市场出现潜在多头机会
- 但当前仍缺少完整确认
- 需要继续观察
- 暂不正式开仓

---

## 6.2 职责

在 `WATCH_LONG` 状态下，系统负责：

- 持续观察 1H / 30m / 15m 的变化
- 评估是否升级为 PROBE_LONG
- 评估是否升级为 DIRECT_LONG
- 若条件恶化，则降级回 FLAT
- 若冷却或风险变化，则终止观察

---

## 6.3 允许转移

`WATCH_LONG` 可以转移到：

- `PROBE_LONG`
- `DIRECT_LONG`
- `FLAT`

---

## 6.4 禁止行为

`WATCH_LONG` 不允许：

- 直接进入 MANAGE_LONG
- 直接进入 EXIT_LONG
- 无条件生成订单
- 与 WATCH_SHORT 同时存在
- 不经过风控直接升级

---

# 7. WATCH_SHORT

## 7.1 定义

`WATCH_SHORT` 表示：

- 市场出现潜在空头机会
- 但当前仍缺少完整确认
- 需要继续观察
- 暂不正式开仓

---

## 7.2 职责

在 `WATCH_SHORT` 状态下，系统负责：

- 持续观察 1H / 30m / 15m 的变化
- 评估是否升级为 PROBE_SHORT
- 评估是否升级为 DIRECT_SHORT
- 若条件恶化，则降级回 FLAT
- 若冷却或风险变化，则终止观察

---

## 7.3 允许转移

`WATCH_SHORT` 可以转移到：

- `PROBE_SHORT`
- `DIRECT_SHORT`
- `FLAT`

---

## 7.4 禁止行为

`WATCH_SHORT` 不允许：

- 直接进入 MANAGE_SHORT
- 直接进入 EXIT_SHORT
- 无条件生成订单
- 与 WATCH_LONG 同时存在
- 不经过风控直接升级

---

# 8. PROBE_LONG

## 8.1 定义

`PROBE_LONG` 表示：

- 多头方向已具备基础条件
- 但确认还不完整
- 允许用小仓试探
- 试探仓是有约束的，不是弱信号硬做

---

## 8.2 职责

在 `PROBE_LONG` 状态下，系统负责：

- 按 probe 仓规则下单
- 持续跟踪后续是否继续确认
- 判断是否升级到 DIRECT_LONG
- 判断是否提前退出
- 判断是否进入 MANAGE_LONG
- 判断是否触发风控减仓或退出

---

## 8.3 允许转移

`PROBE_LONG` 可以转移到：

- `MANAGE_LONG`
- `EXIT_LONG`
- `FLAT`

在极少数情况下，如果系统设计允许，也可以通过重新评估后升级到：

- `DIRECT_LONG`

但升级必须重新经过信号与风控检查，不能直接“补成” direct。

---

## 8.4 禁止行为

`PROBE_LONG` 不允许：

- 直接跳过风控进入 MANAGE_LONG
- 自动变成 full size 而无重新评估
- 因为仓位太小就被执行层硬抬大
- 与 PROBE_SHORT 同时存在
- 被执行层解释成 direct

---

# 9. PROBE_SHORT

## 9.1 定义

`PROBE_SHORT` 表示：

- 空头方向已具备基础条件
- 但确认还不完整
- 允许用小仓试探
- 试探仓受严格约束

---

## 9.2 职责

在 `PROBE_SHORT` 状态下，系统负责：

- 按 probe 仓规则下单
- 观察空头方向是否继续成立
- 判断是否升级到 DIRECT_SHORT
- 判断是否提前退出
- 判断是否进入 MANAGE_SHORT
- 判断是否触发风控减仓或退出

---

## 9.3 允许转移

`PROBE_SHORT` 可以转移到：

- `MANAGE_SHORT`
- `EXIT_SHORT`
- `FLAT`

在少数情况下，也可重新评估后升级到：

- `DIRECT_SHORT`

---

## 9.4 禁止行为

`PROBE_SHORT` 不允许：

- 自动升格为 full size
- 被执行层改成 direct
- 直接跳过状态管理
- 与 PROBE_LONG 同时存在
- 因为仓位太小就被抬仓执行

---

# 10. DIRECT_LONG

## 10.1 定义

`DIRECT_LONG` 表示：

- 多头方向已经完整确认
- 允许正式开仓
- 使用标准仓位
- 进入持仓管理流程

---

## 10.2 职责

在 `DIRECT_LONG` 状态下，系统负责：

- 执行正式开仓
- 挂止损和止盈保护单
- 监控持仓后续表现
- 判断是否进入 MANAGE_LONG
- 判断是否减仓或退出

---

## 10.3 允许转移

`DIRECT_LONG` 可以转移到：

- `MANAGE_LONG`
- `EXIT_LONG`
- `FLAT`

---

## 10.4 禁止行为

`DIRECT_LONG` 不允许：

- 被视为试探仓
- 未经风控直接持久持有
- 与 DIRECT_SHORT 同时存在
- 跳过保护单挂单
- 跳过持仓同步

---

# 11. DIRECT_SHORT

## 11.1 定义

`DIRECT_SHORT` 表示：

- 空头方向已经完整确认
- 允许正式开仓
- 使用标准仓位
- 进入持仓管理流程

---

## 11.2 职责

在 `DIRECT_SHORT` 状态下，系统负责：

- 执行正式开空
- 挂止损和止盈保护单
- 监控持仓后续表现
- 判断是否进入 MANAGE_SHORT
- 判断是否减仓或退出

---

## 11.3 允许转移

`DIRECT_SHORT` 可以转移到：

- `MANAGE_SHORT`
- `EXIT_SHORT`
- `FLAT`

---

## 11.4 禁止行为

`DIRECT_SHORT` 不允许：

- 被视为试探仓
- 未经风控直接持久持有
- 与 DIRECT_LONG 同时存在
- 跳过保护单挂单
- 跳过持仓同步

---

# 12. MANAGE_LONG

## 12.1 定义

`MANAGE_LONG` 表示：

- 多头仓位已经建立
- 当前进入持仓管理阶段
- 系统需要监控止盈、止损、减仓、加仓和反转风险

---

## 12.2 职责

在 `MANAGE_LONG` 状态下，系统负责：

- 维护止损和止盈
- 根据风控判断是否减仓
- 根据趋势延续判断是否允许加仓
- 根据反转信号判断是否退出
- 根据冷却和风险状态调整行为

---

## 12.3 允许转移

`MANAGE_LONG` 可以转移到：

- `EXIT_LONG`
- `FLAT`

在某些扩展设计中，也可以由风控与信号共同允许后重新进入加仓子流程，但不应在状态机主线中复杂化。

---

## 12.4 禁止行为

`MANAGE_LONG` 不允许：

- 再次被当作未开仓状态
- 生成新的独立方向信号
- 在未完成同步前继续加仓
- 忽略止损与风控
- 与 MANAGE_SHORT 同时存在

---

# 13. MANAGE_SHORT

## 13.1 定义

`MANAGE_SHORT` 表示：

- 空头仓位已经建立
- 当前进入持仓管理阶段
- 系统需要监控止盈、止损、减仓、加仓和反转风险

---

## 13.2 职责

在 `MANAGE_SHORT` 状态下，系统负责：

- 维护止损和止盈
- 根据风控判断是否减仓
- 根据趋势延续判断是否允许加仓
- 根据反转信号判断是否退出
- 根据冷却和风险状态调整行为

---

## 13.3 允许转移

`MANAGE_SHORT` 可以转移到：

- `EXIT_SHORT`
- `FLAT`

---

## 13.4 禁止行为

`MANAGE_SHORT` 不允许：

- 再次被当作未开仓状态
- 生成新的独立方向信号
- 在未完成同步前继续加仓
- 忽略止损与风控
- 与 MANAGE_LONG 同时存在

---

# 14. EXIT_LONG

## 14.1 定义

`EXIT_LONG` 表示：

- 多头仓位即将或正在退出
- 系统要完成平仓动作
- 退出后应回到 FLAT
- 同时启动必要的冷却或保护

---

## 14.2 职责

在 `EXIT_LONG` 状态下，系统负责：

- 执行平仓
- 取消相关未成交保护单
- 记录退出原因
- 更新持仓状态
- 开始冷却

---

## 14.3 允许转移

`EXIT_LONG` 完成后应转移到：

- `FLAT`

---

## 14.4 禁止行为

`EXIT_LONG` 不允许：

- 再次变成开仓状态
- 退出过程中再补新的长仓
- 不记录退出原因
- 不更新状态直接返回 FLAT

---

# 15. EXIT_SHORT

## 15.1 定义

`EXIT_SHORT` 表示：

- 空头仓位即将或正在退出
- 系统要完成平仓动作
- 退出后应回到 FLAT
- 同时启动必要的冷却或保护

---

## 15.2 职责

在 `EXIT_SHORT` 状态下，系统负责：

- 执行平仓
- 取消相关未成交保护单
- 记录退出原因
- 更新持仓状态
- 开始冷却

---

## 15.3 允许转移

`EXIT_SHORT` 完成后应转移到：

- `FLAT`

---

## 15.4 禁止行为

`EXIT_SHORT` 不允许：

- 再次变成开仓状态
- 退出过程中再补新的空仓
- 不记录退出原因
- 不更新状态直接返回 FLAT

---

# 16. 状态转移总图

推荐主路径如下：

```text
FLAT
  -> WATCH_LONG
  -> PROBE_LONG
  -> MANAGE_LONG
  -> EXIT_LONG
  -> FLAT
```

```text
FLAT
  -> WATCH_SHORT
  -> PROBE_SHORT
  -> MANAGE_SHORT
  -> EXIT_SHORT
  -> FLAT
```

正式开仓路径如下：

```text
FLAT
  -> DIRECT_LONG
  -> MANAGE_LONG
  -> EXIT_LONG
  -> FLAT
```

```text
FLAT
  -> DIRECT_SHORT
  -> MANAGE_SHORT
  -> EXIT_SHORT
  -> FLAT
```

---

# 17. 状态转移规则

状态转移必须满足以下规则：

1. 必须有信号支持。
2. 必须有风控支持。
3. 必须有数据质量支持。
4. 必须有仓位可执行性支持。
5. 必须记录转移原因。
6. 必须记录转移前后状态。
7. 必须记录对应时间和 symbol。

没有理由的状态跳转一律禁止。

---

# 18. 状态转移来源

状态转移只能来自以下来源：

* 信号引擎
* 风控引擎
* 执行结果
* 持仓同步结果
* 冷却状态变化
* 数据质量状态变化

禁止：

* 手工在运行中强行改状态
* 执行层自己发明状态转移
* 风控层绕过状态机直接改仓
* 信号层跳过状态机直接下单

---

# 19. 状态机与 probe/direct 的关系

状态机必须明确区分：

* `WATCH`：只观察，不执行
* `PROBE`：小仓试探
* `DIRECT`：标准仓执行
* `MANAGE`：持仓管理
* `EXIT`：退出流程

这五类行为不能混成一类。

---

# 20. 状态机与风控的关系

风控可以阻断状态转移，但不能改写状态语义。

例如：

* 允许进入 PROBE_LONG，但风控不通过 -> 阻断
* 允许进入 DIRECT_LONG，但仓位不满足 -> 阻断
* 进入 MANAGE_LONG 后触发止损 -> 转入 EXIT_LONG

---

# 21. 状态机与执行层的关系

执行层只执行状态机给出的动作，不负责重写状态。

例如：

* 状态机决定 `PROBE_LONG`
* 执行层只负责按 probe 仓执行
* 订单成交后回报状态机
* 状态机再决定是否进入 MANAGE_LONG

执行层不得：

* 把 probe 单当成 direct 单
* 把拒单当成已进入持仓
* 自行决定状态跳转

---

# 22. 状态机与回测的关系

回测必须严格回放状态机。

要求：

* 每次状态变化都要记录
* 每次状态变化都要能复盘
* 回测和实盘状态名称必须一致
* 回测不能用简化状态机替代真实状态机

---

# 23. 状态记录字段

每次状态转移至少记录：

* `symbol`
* `timestamp`
* `state_before`
* `state_after`
* `reason`
* `signal_type`
* `entry_mode`
* `risk_level`
* `quality_flag`
* `price`
* `version`

---

# 24. 状态机日志示例

示例一：

```text id="t9m4l2"
symbol: BTCUSDT
timestamp: 2026-06-19T00:00:00Z
state_before: FLAT
state_after: WATCH_LONG
reason: 1H_LONG_ALLOWED_30M_WEAK
signal_type: WAIT
entry_mode: NONE
risk_level: NORMAL
quality_flag: true
```

示例二：

```text id="p3k0as"
symbol: ETHUSDT
timestamp: 2026-06-19T01:00:00Z
state_before: WATCH_LONG
state_after: PROBE_LONG
reason: 15M_TRIGGER_READY_CVD_SUPPORT
signal_type: LONG
entry_mode: PROBE
risk_level: HIGH
quality_flag: true
```

示例三：

```text id="m1qk8v"
symbol: SOLUSDT
timestamp: 2026-06-19T02:00:00Z
state_before: MANAGE_LONG
state_after: EXIT_LONG
reason: STOP_HIT
signal_type: NO_TRADE
entry_mode: NONE
risk_level: BLOCKED
quality_flag: true
```

---

# 25. 禁止项

禁止：

* 同时存在多个主状态
* 状态名称随意变化
* 用状态机代替信号层做方向判断
* 用状态机代替风控层做风险判断
* 用状态机代替仓位层做数量计算
* 状态转移不留日志
* 状态转移无法复现
* 状态机变成补丁收容器

---

# 26. 测试要求

状态机必须至少覆盖以下测试：

* FLAT 到 WATCH_LONG / WATCH_SHORT
* WATCH 到 PROBE
* WATCH 到 DIRECT
* PROBE 到 MANAGE
* DIRECT 到 MANAGE
* MANAGE 到 EXIT
* EXIT 到 FLAT
* 风控阻断转移
* 数据质量阻断转移
* 冷却阻断转移
* 拒单后的状态回滚
* 同一 symbol 上下文连续推进
* 多 symbol 独立状态互不污染

---

# 27. 设计目标

理想状态机应该满足：

* 简单
* 有限
* 稳定
* 可审计
* 可回测
* 可实盘
* 易维护

如果状态机开始越来越复杂，说明前面的信号、风控、仓位和执行边界已经失控。

---

# 28. 结论

状态机是策略执行的中枢。

它不是补丁层，不是回收站，不是临时容错机制。

它的使命只有一个：

把“能不能做、做多少、何时退出”以清晰、稳定、可追踪的方式串起来。

如果状态机混乱，整个系统就一定会再次回到不可维护状态。

