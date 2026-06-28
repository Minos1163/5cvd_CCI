````md
# V4 当前不开仓问题评审与下一阶段修复建议
版本：Review-R3
日期：2026-06-12

---

# 1. 执行摘要（Executive Summary）

根据本轮审计结果：

- 2026-06-11 13:00 至 2026-06-12 21:00
- 无任何新开仓
- 无任何平仓
- 无任何成交记录

统计结果：

```text
post_execution = 1280

hold = 1280

buy = 0

sell = 0

close = 0

execution.noop = 1280

fills = 0
````

这意味着：

```text
交易所没拒单
IOC没失败
保护单没失败
仓位计算没失败
执行器没崩溃
下单模块没丢单
```

真正的问题发生在：

```text
策略层
↓
候选生成层
↓
watchlist层
↓
promotion层
```

而不是：

```text
执行层
```

因此：

当前优先级已经从：

```text
P0 执行故障
```

转变为：

```text
P0 策略结构问题
```

---

# 2. 这次发现了什么

过去很多轮研究都在怀疑：

```text
是不是交易所没成交
是不是执行器漏下单
是不是 sizing=0
是不是 protection order 出错
```

但本轮证据已经足够明确：

```text
根本没有产生 buy/sell
```

即：

```text
AI没下决策
策略没发信号
执行器没收到订单
```

因此：

```text
问题上移
```

从：

```text
Execution Layer
```

变成：

```text
Signal Layer
```

---

# 3. 当前系统真实状态

系统并非完全没有候选。

日志已经出现：

```text
direction_transition_watch_only

slow_bull_transition_long_watch

long_15m_momentum_watch

slow_bull_long_momentum_watch

slow_bull_long_entry_watch
```

说明：

```text
市场不是完全没机会
```

而是：

```text
候选已经出现
但是无法转化成开仓
```

这两个是完全不同的问题。

---

# 4. 最大发现

本轮最重要发现：

SHORT链路已经形成闭环。

LONG链路没有形成闭环。

即：

```text
SHORT:

候选
↓
watch
↓
promotion
↓
probe
↓
open
```

已经存在。

而：

```text
LONG:

候选
↓
watch
↓
???
↓
pending
↓
expired
```

缺失 promotion。

这是结构性问题。

---

# 5. LONG与SHORT出现不对称

目前系统中已经存在：

```text
short_15m_preconfirm_watch

short_non_slow_bear_watch
```

这些状态最终可以触发：

```text
promotion
```

然后：

```text
small probe
```

最终：

```text
open
```

但是LONG侧：

```text
slow_bull_transition_long_watch

long_15m_momentum_watch
```

并没有对应promotion。

于是产生：

```text
watch
↓
watch
↓
watch
↓
expired
```

永远无法进入：

```text
entry
```

---

# 6. 当前最危险误判

如果只看结果：

```text
0开仓
```

很容易得出：

```text
市场没有机会
```

但这是错误的。

正确结论是：

```text
市场机会很少

但不是没有
```

而系统对于：

```text
边缘机会
```

没有处理能力。

---

# 7. 为什么会出现这个问题

原因来自过去几轮优化。

过去主要目标：

```text
减少假突破

减少逆势单

减少追涨杀跌
```

因此不断提高：

```text
direction gate

entry gate

watch gate

promotion gate
```

最终形成：

```text
候选越来越少
```

同时：

```text
转正概率越来越低
```

---

# 8. 当前方向门已经过强

统计显示：

```text
multi_bar_no_direction
1179 / 1280

占比92.1%
```

说明：

绝大多数时间：

```text
方向层直接否决
```

根本到不了：

```text
entry quality
```

阶段。

这属于：

```text
过滤过度
```

现象。

---

# 9. 但不建议降低Direction Gate

这里需要特别强调。

不要直接做：

```text
direction score
0.6
↓
0.3
```

不要做：

```text
aligned threshold
0.2
↓
0
```

不要做：

```text
watch score
0.75
↓
0.3
```

原因很简单：

之前所有亏损：

```text
大部分来自错误方向
```

而不是：

```text
方向正确但进场太晚
```

因此：

```text
方向门是对的
```

不能拆。

---

# 10. 真正应该修改哪里

应该修改：

```text
transition层
```

而不是：

```text
direction层
```

即：

```text
强趋势
→ direct open

弱趋势
→ transition watch

transition成熟
→ promotion

promotion成功
→ probe

probe成功
→ add

add成功
→ full position
```

形成完整闭环。

---

# 11. 当前缺失的核心模块

建议新增：

```text
Long Transition Promotion Engine
```

负责：

```text
watch
→
probe
```

转化。

---

# 12. 建议新增状态机

新增：

```text
LONG_TRANSITION_PENDING

LONG_TRANSITION_READY

LONG_TRANSITION_PROBE

LONG_TRANSITION_CONFIRMED
```

形成明确生命周期。

---

# 13. 建议新增评分体系

当前：

```text
entry_score
```

很多地方缺失。

建议统一：

```text
direction_score

momentum_score

quality_score

entry_score
```

全部落审计。

例如：

```json
{
  "direction":0.55,
  "momentum":0.67,
  "quality":0.71,
  "entry":0.63
}
```

---

# 14. 审计系统需要升级

新增字段：

```text
candidate_reason

candidate_score

watch_reason

watch_reject_reason

promotion_reason

promotion_reject_reason
```

否则以后依然会：

```text
知道没开仓

不知道为什么
```

---

# 15. 当前最缺失的数据

日志里最缺：

```text
entry_score_source
```

例如：

```text
current

candidate

missing
```

必须记录。

否则无法判断：

```text
没有entry_score

还是entry_score不够
```

---

# 16. Direction Transition问题

当前：

```text
direction_transition_watch_only
```

经常出现。

但后面直接消失。

说明：

```text
watchlist接收失败
```

或者：

```text
promotion缺失
```

必须定位。

---

# 17. Watchlist阈值问题

当前：

```text
watchlist_min_signal_score
0.75
```

明显用于：

```text
成熟候选
```

不适合：

```text
transition候选
```

因此建议拆分。

---

# 18. 建议双阈值

新增：

```text
watchlist_mature_score

watchlist_transition_score
```

例如：

```text
0.75

0.30
```

分别管理。

---

# 19. 为什么不能共用

因为：

```text
成熟趋势
```

和：

```text
方向转折
```

本质不同。

如果共用：

```text
0.75
```

那么：

```text
transition永远进不去
```

---

# 20. LONG需要对称结构

SHORT已经拥有：

```text
preconfirm
```

LONG必须补：

```text
preconfirm_long
```

否则：

```text
结构失衡
```

长期统计会偏空。

---

# 21. 建议增加Long Probe

参数建议：

```text
position_mult = 0.25

max_add = 0

tight_stop = true
```

目标：

```text
验证方向
```

而不是：

```text
赚大钱
```

---

# 22. Probe的定位

Probe不是盈利工具。

Probe是：

```text
验证工具
```

作用：

```text
证明趋势正在形成
```

---

# 23. Probe成功后

才允许：

```text
confirmed add
```

流程：

```text
watch

↓

probe

↓

confirmed

↓

add

↓

full position
```

---

# 24. 建议增加Age机制

当前很多候选：

```text
出现
消失
```

非常快。

因此：

```text
age >= 2 cycle
```

再promotion。

避免噪音。

---

# 25. 建议增加Momentum检查

promotion前增加：

```text
15m momentum improvement
```

例如：

```text
当前 > 前一周期
```

才能晋升。

---

# 26. 建议增加Regime检查

要求：

```text
not slow bear
```

否则禁止LONG promotion。

---

# 27. 建议增加冷却机制

失败probe：

```text
cooldown = 6~12 cycle
```

避免重复试错。

---

# 28. 不建议立即扩大仓位

当前阶段：

```text
验证 > 收益
```

因此：

```text
小仓优先
```

不要直接：

```text
0.25
→
1.0
```

---

# 29. 当前研发重点

建议优先级：

```text
P0
审计补全

P1
Long Promotion

P1
Transition Watch

P2
Probe Risk

P3
参数优化
```

---

# 30. 最终判断

当前系统已经证明：

```text
执行层正常

交易所正常

订单层正常

保护单正常
```

真正问题已经收敛到：

```text
LONG中间态候选
无法完成
watch
→ promotion
→ probe
→ open
闭环
```

因此下一阶段不应继续排查：

```text
下单BUG
成交BUG
保护单BUG
```

而应集中资源完成：

```text
Long Transition Framework
```

建设。

完成后预计能够回答三个关键问题：

```text
市场真的没有机会？

还是候选被过滤掉？

还是候选无法晋升？
```

只有把这条链路补齐，V4 才能从：

```text
只会拒绝交易
```

进化为：

```text
能够识别并验证趋势形成过程
```

这将是 V4 从“防守型过滤器”向“可交易策略引擎”演进的关键一步。