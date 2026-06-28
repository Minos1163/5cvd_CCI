# 2026-06-26 13:15 后 Dry-Run 无开仓归因报告
> 用途：提交 Claude 审查  
> 日志窗口：2026-06-26 13:15:05 CST -> 2026-06-26 23:00:05 CST  
> 日志目录：`logs/2026-06/2026-06-26`  
> 当前配置：Fib/PA dry-run 架构，`configs/entry_chain.dry_run_fib_pa_v1.json`

---

## 1. 结论摘要

从 13:15 开始到本地最新同步日志，脚本运行本身正常，但没有任何模拟开仓。

核心事实：

```text
扫描周期：40 个 15m cycle
决策记录：520 条 decisions
交易对数量：13 个
DIRECT：0
PROBE：0
WATCH：45
NO_TRADE：475
13:15 后 paper_trades 新增：0
13:15 后 approved order_drafts：0
exchange_mutation_enabled：false
data_health：OK
```

这不是脚本卡死，也不是 paper 账本异常；主要原因是新 Fib/PA 架构已经生效后，候选信号被四类机制挡住：

1. LONG 候选较多，但 `long_threshold_offset=+10` 后 DIRECT 门槛为 92，本窗口最高分只有 87.60。
2. `disable_probe=true`，30 次 PROBE 候选被转成 `NO_TRADE`。
3. ZEC/XRP 黑名单和 ADA/XMR 观察模式继续拦截候选。
4. Fib 扩展耗竭硬门控触发 9 次，拦截 SOL/ADA/TRX 的追扩展信号。

策略层面的判断：本窗口无开仓符合“重构后更重视位置质量”的预期，但如果连续 24-48 小时仍然零开仓，需要评估 `disable_probe`、LONG 92 门槛、RR 几何评分是否过严。

---

## 2. 运行健康检查

`health.json` 显示：

```text
mode=dry_run
symbols=13
data_health=OK
orders_submitted=0
exchange_mutation_enabled=false
```

13 个 symbol 都有 warmup 数据：

```text
BNB/XRP/SOL/TRX/HYPE/DOGE/ZEC/XLM/XMR/CC/LAB/LINK/ADA
15m/30m/1h/4h 均为 240 bars
ready_15m=true
```

paper 账户最新累计状态：

```text
equity=9835.2877
initial_equity=10000
realized_pnl=-164.7123
unrealized_pnl=0
open_positions=0
return_pct=-1.6471%
max_drawdown=3.2788%
profit_factor=0.6466
win_rate=52.78%
trade_count=36
```

注意：以上 paper 指标是累计值，不是 13:15 后新增表现。13:15 后没有新增开仓和平仓。

---

## 3. 决策分布

### 3.1 Action 分布

| action | count | 占比 |
|---|---:|---:|
| NO_TRADE | 475 | 91.35% |
| WATCH | 45 | 8.65% |
| DIRECT | 0 | 0.00% |
| PROBE | 0 | 0.00% |

### 3.2 分数分布

| score 区间 | count |
|---|---:|
| < 50 | 198 |
| 50-59.99 | 127 |
| 60-69.99 | 113 |
| 70-79.99 | 70 |
| 80-89.99 | 12 |
| 90+ | 0 |

本窗口没有任何 90+ 信号。  
最高分为 ZECUSDT SHORT 87.60，但 ZEC 在黑名单内。

### 3.3 Reason 分布

| reason | count | 解释 |
|---|---:|---|
| FIB_PA_ARCHITECTURE_WEIGHTS | 520 | 新 Fib/PA 权重架构已覆盖全部决策 |
| SIDE_THRESHOLD_OFFSET_LONG_10.00 | 190 | LONG 阈值被 +10 偏移抬高 |
| SYMBOL_BLACKLISTED | 80 | XRP/ZEC 黑名单拦截 |
| SYMBOL_WATCH_ONLY | 79 | 观察模式标的拦截 |
| PROBE_DISABLED | 30 | PROBE 候选被禁用 |
| FIB_EXTENSION_EXHAUSTION_BLOCK | 9 | Fib 扩展耗竭硬拦截 |

---

## 4. Fib/PA 新组件行为

当前权重：

| component | weight |
|---|---:|
| trend_ema_context | 20 |
| flow_cvd_confirmation | 18 |
| cci_momentum_quality | 14 |
| price_action_structure | 22 |
| fibonacci_location | 18 |
| risk_reward_geometry | 8 |

13:15 后组件平均得分：

| component | avg points | min | max | 归因 |
|---|---:|---:|---:|---|
| trend_ema_context | 15.14 / 20 | 8.00 | 18.65 | EMA 环境总体支持，未成为主要阻力 |
| flow_cvd_confirmation | 14.04 / 18 | 3.60 | 18.00 | CVD 多数情况下支持 |
| cci_momentum_quality | 4.26 / 14 | 0.00 | 14.00 | CCI 是主要压分项之一 |
| price_action_structure | 6.51 / 22 | 0.00 | 21.00 | PA 多数时间缺少高质量结构 |
| fibonacci_location | 12.71 / 18 | 0.00 | 18.00 | Fib 位置多数尚可，但有 9 次硬阻断 |
| risk_reward_geometry | 1.68 / 8 | 0.00 | 5.00 | RR 几何是最低平均分组件 |

解释：

旧架构里 EMA/CVD 同向容易给出高分；现在 EMA/CVD 仍然经常支持，但 CCI、PA、RR 三层把很多“趋势同意”信号压低。这正是 Fib/PA 重构的目标：不再因为趋势已经发生就追进去，而是要求有位置、结构和 TP1 路径。

潜在问题是 RR 平均只有 1.68/8，可能过严，也可能说明本窗口确实缺少可交易空间。需要更多窗口验证。

---

## 5. 高分未开仓案例

| 时间 CST | symbol | 意图方向 | score | action | 主要原因 | 组件要点 |
|---|---|---|---:|---|---|---|
| 17:00:05 | ZECUSDT | SHORT | 87.60 | NO_TRADE | SYMBOL_BLACKLISTED | EMA 17.1, CVD 18, CCI 10, PA 21, Fib 18, RR 3.5 |
| 14:45:05 | DOGEUSDT | LONG | 86.30 | NO_TRADE | LONG +10, PROBE_DISABLED | EMA 14.3, CVD 18, CCI 10, PA 21, Fib 18, RR 5 |
| 17:15:05 | ZECUSDT | SHORT | 86.09 | NO_TRADE | SYMBOL_BLACKLISTED | EMA 17.59, CVD 18, CCI 14, PA 15, Fib 18, RR 3.5 |
| 16:30:05 | BNBUSDT | LONG | 84.59 | NO_TRADE | LONG +10, PROBE_DISABLED | EMA 17.59, CVD 18, CCI 10, PA 21, Fib 18, RR 0 |
| 14:45:05 | BNBUSDT | LONG | 82.80 | NO_TRADE | LONG +10, PROBE_DISABLED | EMA 14.3, CVD 18, CCI 10, PA 21, Fib 18, RR 1.5 |
| 14:45:05 | LINKUSDT | LONG | 81.80 | NO_TRADE | LONG +10, PROBE_DISABLED | EMA 14.3, CVD 18, CCI 10, PA 21, Fib 18, RR 0.5 |
| 21:15:05 | LABUSDT | LONG | 81.15 | NO_TRADE | LONG +10, PROBE_DISABLED | EMA 18.65, CVD 18, CCI 14, PA 21, Fib 6, RR 3.5 |

可以看到，分数最高的可交易型候选主要分两类：

1. ZEC SHORT：组件质量较好，但被黑名单拦截。
2. LONG 候选：分数在 81-86，达不到 LONG DIRECT 92，且 PROBE 被禁用。

所以“没开仓”的直接解释不是没有任何信号，而是没有任何信号通过当前配置的执行门槛。

---

## 6. Fib 扩展硬门控

`FIB_EXTENSION_EXHAUSTION_BLOCK` 共触发 9 次：

| symbol | count |
|---|---:|
| SOLUSDT | 5 |
| TRXUSDT | 3 |
| ADAUSDT | 1 |

这说明 Fib 扩展耗竭过滤器已经在阻止追扩展区入场。该行为符合本次重构目标：避免在价格已经接近或越过扩展目标时继续追趋势。

需要后续验证的问题不是“它有没有生效”，而是：

```text
这些被 block 的信号后续是否真的更容易反转？
如果是，硬门控有效。
如果不是，1.618/tolerance 参数可能过严。
```

---

## 7. 为什么没有开仓

### 7.1 分数层：没有任何信号达到 90+

本窗口最高 score 为 87.60，且属于 ZEC 黑名单。  
LONG 候选虽然多次达到 80+，但 LONG DIRECT 阈值为 92，因此无法开 DIRECT。

### 7.2 配置层：PROBE 被禁用

`PROBE_DISABLED` 出现 30 次。  
这些信号不是完全没有交易倾向，而是只够 PROBE，不够 DIRECT。当前配置禁用 PROBE 后，全部转为 `NO_TRADE`。

这对 dry-run 的影响很直接：  
安全性提高，但交易样本会明显减少。

### 7.3 符号层：黑名单和观察模式仍在起作用

`SYMBOL_BLACKLISTED` 出现 80 次，`SYMBOL_WATCH_ONLY` 出现 79 次。  
其中 ZEC 贡献了多个高分 SHORT 候选，但因为前期亏损集群已被加入黑名单，所以不允许开仓。

这属于预期行为，不是异常。

### 7.4 结构层：CCI/PA/RR 正在压低趋势信号

EMA 和 CVD 平均分较高，但 CCI、PA、RR 平均分显著偏低：

```text
CCI 平均：4.26 / 14
PA 平均：6.51 / 22
RR 平均：1.68 / 8
```

含义：

```text
趋势和资金流经常同意方向；
但动量质量、价格结构、风险回报路径不足；
因此新架构没有把这些趋势状态转化为开仓。
```

这符合“用 Fib + Price Action 替换 MACD/BOLL 后，避免趋势末端追单”的设计目标。

---

## 8. 是否正常

### 8.1 脚本运行层面：正常

证据：

```text
data_health=OK
warmup ready
每个 symbol 有连续 decisions
runtime 已输出 Fib/PA 专用评分明细
paper state 正常更新
orders_submitted=0 符合 dry-run + 无 approved draft
```

### 8.2 策略行为层面：短期正常，但需要观察交易频率

刚切换到 Fib/PA 位置优先架构后，第一段时间没有开仓可以接受。  
这说明新门控确实比旧 EMA/CVD 趋势同意模型更保守。

但如果接下来 24-48 小时仍然没有任何 DIRECT 或 paper trade，需要重点审查三件事：

1. `disable_probe=true` 是否导致 dry-run 缺少足够样本。
2. LONG 门槛 92 是否在 Fib/PA 架构下过高。
3. `risk_reward_geometry` 平均 1.68/8 是否过严，导致优质 PA/Fib 候选仍然无法通过。

---

## 9. 给 Claude 的审查问题

1. 在 Fib/PA 架构刚上线的 dry-run 阶段，是否应临时启用 PROBE，以获取更多“低风险候选样本”，还是继续保持 `disable_probe=true`？
2. LONG 阈值仍然使用旧架构的 `+10` 偏移是否合理？在 Fib/PA/CCI 已经显著压分后，LONG DIRECT 92 是否过严？
3. `risk_reward_geometry` 平均仅 1.68/8，是参数过严，还是本窗口确实缺少 TP1 可达路径？
4. ZEC 黑名单挡住了本窗口最高分信号 87.60。是否要继续将黑名单作为硬拦截，还是允许 observation-only 记录“如果不拦截会怎样”的纸面路径？
5. Fib 扩展硬门控触发 9 次。请重点评估 `1.618 + 0.5 ATR tolerance` 是否过严，是否需要改为只降级 WATCH 而非硬 block。
6. 当前组件最低分策略是否需要显式进入日志，例如记录“DIRECT_BELOW_COMPONENT_MINIMUM”，以便下一轮更容易归因。

---

## 10. 建议的下一步验证

本报告不建议立刻把门槛大幅放松。更稳妥的验证顺序：

```text
P0：继续 dry-run 观察到至少 24h，确认是否只是短窗口无机会。
P1：统计所有 PROBE_DISABLED 候选的后续 1R/2R 纸面表现。
P2：单独评估 LONG 候选，如果 80-90 分 LONG 后续表现良好，再考虑把 long_threshold_offset 从 +10 降到 +7。
P3：对 RR 几何做分布分析，确认 0 分/低分来自手续费、支撑阻力距离，还是 ATR stop 设置。
P4：不要同时放松 PROBE、LONG 阈值和 RR 参数；每次只改一个变量。
```

---

*报告结束 | 2026-06-26 Fib/PA Dry-Run No-Entry Analysis*
