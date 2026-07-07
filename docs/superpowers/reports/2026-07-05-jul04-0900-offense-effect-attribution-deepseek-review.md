# AI300 Dry-Run 进攻态势执行效果归因报告

**用途:** 提交 DeepSeek 复审  
**分析窗口:** 北京时间 2026-07-04 09:00:00 至 2026-07-05 09:30:05  
**日志目录:** `logs/2026-07/2026-07-04/`, `logs/2026-07/2026-07-05/`  
**策略状态:** 防御规则已生效，主交易无开仓；进攻层仅通过 `SCOUT_MICRO` 对 XLMUSDT 做了极小纸仓实验。

---

## 1. 核心结论

本窗口“扩大盈利点”的执行效果不理想，根因不是下单链路故障，也不是数据健康或交易预算限制，而是：

1. **主交易仍处于高防御状态，PROBE/DIRECT 完全没有触发。**  
   窗口内 `1284` 条决策全部为 `WATCH/NO_TRADE`，主账本 `paper_trades.jsonl` 无新增事件，`orders_submitted=0`。

2. **进攻层覆盖面过窄。**  
   `SCOUT_MICRO` 只配置了 `XLMUSDT`，18 条高分 near-miss 中只有 2 条具备 SCOUT 微仓资格，其余 XMR、BCH、LINK、SOL、HYPE、CC 等高分候选都只被观察或拦截。

3. **XLMUSDT SCOUT 的两笔样本不足以证明可晋级，且第二笔暴露了同向短间隔重入风险。**  
   第一笔 XLM SHORT 小赚 `+0.2043 USDT`，第二笔 XLM SHORT 初始止损 `-0.6051 USDT`，合计 `-0.4008 USDT`，`profit_factor=0.3376`。

4. **near-miss 仍主要是 RR 缺口，不是“可直接放行的优质机会”。**  
   18 条 near-miss 中，RR/风险回报相关主因占 12 条。高总分仍可能来自 Fib/PA/CCI/EMA 堆分，但 RR 分数不足导致实际容错空间很差。

5. **定向 LONG SCOUT 仍停留在标记层，没有变成微仓执行层。**  
   `SIDE_THRESHOLD_OFFSET_LONG_10.00` 出现 367 次，其中 CCUSDT 有 2 条 `TARGETED_LONG_OFFSET` near-miss，但 CCUSDT 不在 `scout_micro_symbols`，因此没有进入 Phase 2。

---

## 2. 运行链路健康性确认

### 2.1 数据与执行状态

| 指标 | 结果 |
|---|---:|
| 决策行数 | 1284 |
| 扫描周期估算 | 99 |
| 覆盖 symbol | 13 |
| `WATCH` | 169 |
| `NO_TRADE` | 1115 |
| `PROBE` / `DIRECT` | 0 |
| 主账本开仓事件 | 0 |
| SCOUT 微仓开仓事件 | 2 |
| `data_health` | OK |
| `orders_submitted` | 0 |

执行审计中 `order_drafts.jsonl` 全部为：

```text
approved=false
reason="entry chain action does not allow live order draft"
```

这说明没有开主仓是准入层主动拦截，不是订单生成或执行层故障。

### 2.2 预算不是瓶颈

从决策 metadata 中读取：

- `used_today` 始终为 `0`
- `dynamic_limit` 分布约为 `2` 到 `22`
- `current_volatility_scale` 约为 `0.1` 到 `1.6868`

因此主交易没有开仓，不是因为 `DAILY_TRADE_BUDGET_USED` 或预算耗尽，而是入场动作一直没有到 `PROBE/DIRECT`。

---

## 3. 主交易为什么仍然不开仓

### 3.1 决策拒绝原因分布

按非 `FIB_PA_ARCHITECTURE_WEIGHTS` 原因聚合：

| 拒绝原因族 | 次数 | 解释 |
|---|---:|---|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 367 | LONG 侧 offset 仍大量压制多头 |
| `SYMBOL_BLACKLISTED` | 198 | XRP/ZEC 等黑名单标的贡献大量 NO_TRADE |
| `SYMBOL_WATCH_ONLY` | 163 | ADA/XMR 等观察池不能主交易 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 90 | Fib 延伸耗尽过滤追涨/追空 |
| RR / `RISK_REWARD` 相关 | 54 | RR 几何不足，是高分近失主因 |
| `FIBONACCI_LOCATION` 相关 | 19 | Fib 位置不足 |
| `SCORE_MINIMUM` 相关 | 15 | 分数未达 PROBE |
| CCI 相关 | 6 | 动能不足 |
| PA 相关 | 3 | 价格结构不足 |
| `SYMBOL_OBSERVATION_ONLY` | 1 | XLM 主交易被观察层拦截 |

### 3.2 分数分布说明“优质候选密度不足”

| 分数门槛 | 数量 |
|---|---:|
| `score >= 70` | 151 |
| `score >= 72` | 117 |
| `score >= 75` | 83 |
| `score >= 80` | 25 |
| `score >= 82` | 18 |
| `score >= 85` | 8 |
| `score >= 90` | 1 |

虽然有 18 条 `score >= 82` 的 near-miss，但大多数不是被一个可安全放宽的小门槛挡住，而是被 RR、黑名单、观察池、LONG offset 等结构性规则挡住。

---

## 4. Near-Miss 结构复盘

### 4.1 Near-miss 总览

| 指标 | 数量 |
|---|---:|
| near-miss 总数 | 18 |
| RR/DIRECT 风险回报缺口 | 12 |
| 黑名单 | 3 |
| LONG offset | 2 |
| Watch-only | 1 |

### 4.2 关键候选

| 时间(BJT) | Symbol | Side | Score | RR分 | 主因 | 备注 |
|---|---|---|---:|---:|---|---|
| 07-04 10:00 | XMRUSDT | SHORT | 88.70 | 2.0 | `SYMBOL_WATCH_ONLY` | 高分但仍在观察池 |
| 07-04 20:00 | XLMUSDT | SHORT | 83.30 | 2.0 | RR 缺口 | 进入 SCOUT，最终小赚 |
| 07-04 21:45 | XLMUSDT | SHORT | 90.69 | 3.5 | RR 缺口 | 进入 SCOUT，初始止损 |
| 07-05 02:00 | ZECUSDT | LONG | 89.59 | 5.0 | `SYMBOL_BLACKLISTED` | 分数高但黑名单 |
| 07-05 02:00 | CCUSDT | LONG | 82.70 | 0.0 | LONG offset | 标记 `TARGETED_LONG_OFFSET` |
| 07-05 02:15 | CCUSDT | LONG | 84.70 | 2.0 | LONG offset | 标记 `TARGETED_LONG_OFFSET` |
| 07-05 07:15 | SOLUSDT | SHORT | 86.70 | 0.0 | RR 缺口 | 高结构分但 RR 极差 |
| 07-05 09:30 | BNBUSDT | SHORT | 88.70 | 2.0 | RR 缺口 | 高分近失 |

### 4.3 重要观察

`score >= 80` 的 LONG offset 信号共有 3 条，但 near-miss 只记录了 2 条，因为全局 `near_miss_min_score` 仍为 `82`。  
这意味着“定向 LONG SCOUT 条件 score>=80”的设计，在当前记录链路里仍被全局 near-miss 门槛截断。若要评估 80-82 分 LONG 偏移信号，必须把记录器的定向通道从全局 `near_miss_min_score` 中解耦，或运行时设为 `--near-miss-min-score 80`。

---

## 5. SCOUT Micro 执行效果

### 5.1 SCOUT 账本结果

`logs/2026-07/2026-07-04/scout_micro/paper_summary.json`:

| 指标 | 结果 |
|---|---:|
| trade_count | 2 |
| win_rate | 50% |
| realized_pnl | `-0.400839 USDT` |
| profit_factor | `0.3376` |
| max_drawdown | `0.0080%` |
| open_positions | 0 |

### 5.2 单笔交易明细

| 开仓时间(BJT) | Symbol | Side | Score | RR分 | 结果 | 净 PnL |
|---|---|---|---:|---:|---|---:|
| 07-04 19:45 | XLMUSDT | SHORT | 83.30 | 2.0 | TP1 后保本止损 | `+0.204277` |
| 07-04 21:30 | XLMUSDT | SHORT | 90.69 | 3.5 | 初始止损 | `-0.605117` |

两笔合计 `-0.400839 USDT`。第一笔证明 XLM 有短线顺行潜力；第二笔说明高总分和较高 CCI/EMA 仍不能抵消 RR 不足与短时间同向重入风险。

### 5.3 SCOUT 暴露的问题

1. **样本过少。**  
   24.5 小时只有 2 笔 SCOUT，远低于“10-30 次 SCOUT 观察/微仓”的研发目标。

2. **只验证了 XLM 一个 symbol。**  
   这不是“扩大盈利点”，更像“单点 XLM 实验”。XMR、CC、BCH、SOL、HYPE 等候选没有进入微仓。

3. **SCOUT 缺少同 symbol 同方向重入冷却。**  
   第一笔 XLM 在 21:15 保本止损，第二笔 21:30 再次 XLM SHORT 开仓，间隔仅 15 分钟，随后初始止损。  
   这提示 SCOUT 层也需要类似“post-close / post-stop / same-side cooldown”或信号簇去重，否则会在同一段行情里重复采样同质信号。

4. **SCOUT 仍在测试 RR 缺口信号，但 RR 缺口组并未证明正期望。**  
   两笔 XLM 都是 `DIRECT/PROBE_BELOW_RISK_REWARD_GEOMETRY`，并非完整通过主交易质量门的信号。结果一赢一亏但亏损更大，说明 RR 防线目前仍有价值。

---

## 6. 归因层级

### 一级归因：主交易无盈利点扩张

主交易 0 开仓，原因是入场链路全部停留在 `WATCH/NO_TRADE`。  
这是防御体系有效，不是下单失败。

### 二级归因：进攻层覆盖过窄

`SCOUT_MICRO` 只覆盖 `XLMUSDT`，而本窗口高分 near-miss 分布在 XMR、ZEC、BCH、LINK、HYPE、SOL、CC、BNB 等多个标的。  
因此横截面机会没有被真正转化为可统计的微仓实验。

### 三级归因：SCOUT 样本不够且质量未分层

XLM 两笔都属于 RR gap 信号。第一笔顺行，第二笔止损。  
当前 SCOUT 记录还不能区分：

- 低 RR 高动能是否适合快进快出；
- 高分 RR gap 是否只是总分堆砌；
- 同方向连续近失是否代表有效趋势延续，还是同质噪声聚集。

### 四级归因：LONG 进攻只标记、不执行

`SIDE_THRESHOLD_OFFSET_LONG_10.00` 是最大单项压制原因，出现 367 次。  
但 `TARGETED_LONG_OFFSET` 只记录了 CCUSDT 的 2 条 near-miss，且没有微仓。  
所以 LONG 侧是否被过度保守压制，仍没有足够数据回答。

### 五级归因：观察池/黑名单吸走高分候选

高分 XMR、ZEC 被 `WATCH_ONLY` / `BLACKLISTED` 拦截。  
这对主账本是安全的，但对“扩大盈利点”的研发目标来说，说明需要有明确的 `SCOUT_ONLY` 晋级机制，而不是只靠主池规则。

---

## 7. 对当前“进攻态势”的评价

本窗口不是进攻失败，而是进攻层仍处于过窄的实验状态：

- 防御侧：成功，没有主交易亏损，没有低质量 PROBE 后门复发。
- 主交易侧：没有扩张，0 开仓，收益贡献为 0。
- SCOUT 侧：启动了，但只跑 XLM 两笔，样本不足且小亏。
- 数据侧：near-miss 与 TARGETED_LONG_OFFSET 已经提供方向，但还没有形成可执行的多 symbol 微仓实验矩阵。

因此，“扩大盈利点”效果不理想的最准确表述是：

> 系统已经从“堵漏洞”进入“可控侦察”，但还没有进入真正的“多点进攻”。当前进攻层只验证了 XLM 单点 RR-gap 假设，且该假设暂未显示正期望。

---

## 8. 提交 DeepSeek 复审的问题

1. **XLMUSDT 是否应继续保留在 `SCOUT_MICRO`？**  
   两笔样本一赢一亏，净亏 `-0.4008 USDT`。是否继续采样到至少 20 笔，还是要求新增冷却后再继续？

2. **SCOUT 是否需要同 symbol 同方向冷却？**  
   本窗口第二笔 XLM 在第一笔退出后 15 分钟内同向重开并止损。建议评审是否加入 `same_symbol_same_side_scout_cooldown_hours=2`。

3. **CCUSDT 的 `TARGETED_LONG_OFFSET` 是否应进入 SCOUT 微仓？**  
   本窗口 CC LONG 有 `82.7` 和 `84.7` 两条高 PA/高 Fib 候选，但 RR 分别为 `0.0` 和 `2.0`。是否允许 50 USDT/1x 的 SCOUT 微仓，还是继续只观察？

4. **定向 LONG near-miss 是否应绕过全局 `near_miss_min_score=82`？**  
   规则设计写的是 `score>=80`，但当前全局 near-miss 门槛导致 80-82 的 LONG offset 信号没有记录完整。

5. **RR gap 组是否继续禁止主交易？**  
   本窗口高分 near-miss 多数仍是 RR gap；XLM SCOUT 的结果也未证明低 RR 可直接放行。是否继续维持主交易 RR 门槛不变？

6. **XMR/ZEC 这类高分但受 watch/blacklist 限制的标的，是否可以建立 `SCOUT_ONLY` 状态？**  
   XMR `88.7` 被 watch-only 拦截，ZEC `89.59` 被 blacklist 拦截。是否允许它们只进入微仓观察，而不进入主交易池？

---

## 9. 下一步建议草案

在 DeepSeek 复审前，不建议直接放宽主交易门槛。更稳妥的路线：

1. **保持主交易防线不变。**
2. **为 SCOUT 增加同 symbol 同方向冷却，避免短时间重复采样同质信号。**
3. **将 SCOUT 从单点 XLM 扩展为小型白名单矩阵：XLM + CC targeted-long + XMR watch-only scout。**
4. **把 SCOUT 统计按模式拆分：RR-gap、targeted-long-offset、watch-only-high-score。**
5. **定向 LONG near-miss 记录门槛与全局 near-miss 门槛解耦，确保 80-82 分样本不丢失。**

核心原则仍然是：不拆主防线，用 SCOUT 子账本收集可晋级证据。
