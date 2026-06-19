下面这个版本建议直接覆盖 `docs/02_market_universe.md`。

这个文档实际上是整个系统最容易被忽视、但后期最容易变成屎山的地方之一。

很多策略后期失控，并不是信号逻辑有问题，而是：

* 今天交易 BTC、ETH
* 明天加 SOL
* 后天加 100 个山寨币
* 某些币成交量很差
* 某些币被庄家操纵
* 某些币刚上线
* 某些币快下架

最终回测和实盘根本不是同一个市场。

因此：

**Market Universe 必须被视为风控模块的一部分，而不是配置文件。**

---

# docs/02_market_universe.md

````md
# Market Universe

Version: V1.0

---

# 1. 目的

本文件定义：

- 允许交易哪些币种
- 为什么允许交易
- 如何进入标的池
- 如何退出标的池
- 如何保证回测与实盘一致
- 如何避免流动性风险
- 如何避免幸存者偏差

Market Universe 是策略的一部分。

不是配置文件。

不是临时决定。

不是运营决策。

---

# 2. 核心原则

系统只交易：

- 流动性充足
- 市值靠前
- 成交活跃
- 长期存在
- 不容易被操纵

的主流资产。

---

# 3. 系统定位

本系统不是：

- 山寨币轮动系统
- Meme Coin 系统
- 小市值投机系统
- 新币冲刺系统

本系统是：

多周期趋势跟踪系统。

因此：

稳定性优先于爆发力。

---

# 4. 标的池目标

目标：

覆盖整个加密市场主要风险资产。

同时避免：

- 极端流动性风险
- 上下插针风险
- 交易所下架风险

---

# 5. 默认交易范围

仅限：

Binance USDT Perpetual

---

# 6. 允许交易品种

初始版本：

Top20 Market Cap

参考：

```text
BTC
ETH
BNB
SOL
XRP
DOGE
ADA
TRX
AVAX
LINK
DOT
TON
SHIB
BCH
LTC
NEAR
APT
ARB
SUI
ETC
````

注意：

名单只是示例。

实际名单由筛选器生成。

---

# 7. Universe Philosophy

系统不预测哪个币涨。

系统假设：

强趋势会在主流币中出现。

因此：

目标不是找到最强币。

目标是：

找到风险收益比最合理的趋势资产。

---

# 8. 标的进入条件

币种进入 Universe 必须满足：

全部条件。

---

# 9. 市值条件

最低要求：

```text
Market Cap Rank <= 30
```

推荐：

```text
Market Cap Rank <= 20
```

---

# 10. 流动性条件

24h成交额：

```text
>= 100M USD
```

推荐：

```text
>= 300M USD
```

---

# 11. 永续合约条件

必须存在：

```text
USDT Perpetual
```

禁止：

季度合约

---

# 12. 上线时间条件

上市时间：

```text
>= 180天
```

推荐：

```text
>= 365天
```

---

# 13. 数据完整性条件

必须拥有：

* 15m
* 30m
* 1H
* 4H

完整历史。

---

# 14. K线质量要求

禁止：

连续缺失

例如：

```text
missing bars > 0.5%
```

---

# 15. 点差条件

平均点差：

```text
<= 0.10%
```

推荐：

```text
<= 0.05%
```

---

# 16. 异常波动过滤

禁止进入：

频繁出现：

* 20%
* 30%
* 50%

瞬时插针资产。

---

# 17. 杠杆风险过滤

禁止：

高风险实验性资产。

例如：

* 刚上线
* 流动性不足
* 长期异常波动

---

# 18. 下架风险过滤

禁止：

已进入观察名单资产。

例如：

Binance Monitoring Tag

---

# 19. Universe Size

推荐：

```text
10 ~ 20个币
```

上限：

```text
30个币
```

不建议：

```text
50+
100+
```

---

# 20. 为什么限制数量

原因：

信号质量下降。

组合风险增加。

管理复杂度增加。

回测难度增加。

维护成本增加。

---

# 21. Universe 更新频率

禁止：

实时更新。

推荐：

```text
每周一次
```

或者：

```text
每月一次
```

---

# 22. 更新原则

Universe 更新必须：

慢。

稳定。

可追踪。

---

# 23. 更新流程

步骤：

1. 获取市场数据
2. 计算排名
3. 过滤异常资产
4. 生成候选列表
5. 保存版本
6. 人工审核（可选）
7. 生效

---

# 24. Universe Version

必须存在：

```text
universe_version
```

例如：

2026W01

2026W02

---

# 25. 回测一致性

回测必须使用：

历史Universe。

不能使用：

当前Universe。

---

# 26. 禁止幸存者偏差

错误：

2026回测2019数据。

然后：

使用2026 Top20。

这是幸存者偏差。

---

# 27. 正确做法

2019使用：

2019 Universe

2020使用：

2020 Universe

以此类推。

---

# 28. Universe Snapshot

每次更新必须保存：

```text
symbol
market_cap_rank
volume_rank
added_time
removed_time
reason
version
```

---

# 29. Universe 数据结构

```text
UniverseMember
```

字段：

```text
symbol

market_cap_rank

volume_rank

status

added_time

removed_time

version
```

---

# 30. Active 状态

允许：

```text
ACTIVE
```

表示：

可交易。

---

# 31. Suspended 状态

表示：

暂停交易。

原因：

* 数据异常
* 风控异常
* 流动性下降

---

# 32. Removed 状态

表示：

移出Universe。

不再开仓。

---

# 33. 已有持仓处理

如果币种被移出：

禁止新开仓。

允许：

管理已有仓位。

直到退出。

---

# 34. Universe 与信号层

Universe决定：

哪些币允许生成信号。

信号层不得绕过Universe。

---

# 35. Universe 与风控层

Universe属于第一层风控。

优先级：

高于信号。

---

# 36. Universe 与执行层

执行层只接受：

Universe内资产。

否则拒单。

---

# 37. Universe 与回测

回测必须记录：

```text
universe_version
```

---

# 38. Universe 与数据库

必须持久化：

* 当前Universe
* 历史Universe
* 更新日志

---

# 39. Universe 与监控

监控：

* 新增资产
* 删除资产
* 流动性下降
* 数据质量下降

---

# 40. Universe 风险控制

Universe是第一道过滤器。

如果Universe失控：

后面所有策略都会失控。

---

# 41. 推荐V1配置

推荐：

```yaml
max_symbols: 20

min_market_cap_rank: 20

max_market_cap_rank: 30

min_24h_volume_usd: 300000000

min_listing_days: 365

max_spread_pct: 0.05

update_frequency: weekly
```

---

# 42. V1最终建议

V1不要追求覆盖市场。

V1追求：

只交易最容易赚钱的那20个币。

宁可少。

不要杂。

宁可稳定。

不要花哨。

---

# 43. 结论

Market Universe 不是币种列表。

它是：

策略的第一层风控。

它决定：

系统看见什么市场。

如果Universe设计错误，

后面的信号层、风控层、仓位层、执行层都会被污染。

因此：

Universe 必须版本化。

必须可审计。

必须可回测。

必须长期稳定。

```

### 我建议你接下来让 Codex 重写的顺序

目前最关键的还不是代码，而是把剩余几个核心设计文档彻底钉死：

1. `03_indicator_spec.md`
2. `04_multi_timeframe_context.md`
3. `05_entry_state_machine.md`
4. `06_position_sizing.md`
5. `07_risk_and_exit.md`

这五个文档决定了未来 90% 的收益曲线和 90% 的屎山概率。尤其是 `03~05`，实际上就是这套系统的“交易宪法”。
```
