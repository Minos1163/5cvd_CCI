# 2026-06-27 最新 22 小时 Dry-Run 频率与开仓链路审查报告
> 用途：提交 Claude 评审  
> 窗口：2026-06-27 00:15:05 CST -> 2026-06-27 22:15:05 CST  
> 日志目录：`logs/2026-06/2026-06-26` + `logs/2026-06/2026-06-27`  
> 当前目标：月开仓 300-600 次，日开仓 10-20 次；3x/4x/5x 浮动杠杆；单交易对 20%-30% 浮动仓位；同时最多 5 个持仓交易对；30 天收益 50%+；胜率 80%+

---

## 1. 执行摘要

当前脚本运行健康，但开仓频率远低于采样目标。

```text
22h 决策数：1157
15m 周期：89
交易对：13

Action 分布：
  NO_TRADE 1054
  WATCH      97
  PROBE       6
  DIRECT      0

approved order drafts：6
paper 实际新开仓：3
paper 减仓：2
paper 平仓：3
窗口内已实现净 PnL：+9.02 USDT
窗口内 closed position 结果：HYPE -8.99，LAB -8.77，LAB +26.78
```

与目标差距：

```text
目标日开仓：10-20 次
当前 22h paper 实际开仓：3 次
折算 24h：约 3.27 次/日

目标月开仓：300-600 次
当前折算月开仓：约 98 次/月

需要提升倍数：
  达到 10 次/日：约 3.1x
  达到 20 次/日：约 6.1x
```

核心不足：

1. 当前开仓仍几乎只有 PROBE，22h 内没有 DIRECT。
2. RR 几何是最大压制项，平均只有 `0.93/8`，`NET_TP1_R_TOO_LOW` 出现 752 次。
3. `LONG +10` 仍显著压制多头候选，`SIDE_THRESHOLD_OFFSET_LONG_10.00` 出现 389 次。
4. 黑名单/观察名单拦截很多高分信号，尤其 ZEC、XMR。
5. dry-run 的风险状态没有完整回填到 entry context，导致 approved draft 与 paper 实际开仓不一致。
6. PROBE 仓位仍是 500 notional、3x、10% max exposure，不符合目标中的 20%-30% 单交易对浮动仓位。

---

## 2. 窗口数据

### 2.1 决策分布

| 项目 | 数值 |
|---|---:|
| 决策总数 | 1157 |
| 15m cycle | 89 |
| symbol 数 | 13 |
| NO_TRADE | 1054 |
| WATCH | 97 |
| PROBE | 6 |
| DIRECT | 0 |

### 2.2 分数分布

| score 区间 | count |
|---|---:|
| < 50 | 594 |
| 50-59.99 | 269 |
| 60-69.99 | 169 |
| 70-79.99 | 96 |
| 80-89.99 | 28 |
| 90+ | 1 |

解释：

```text
80+ 信号只有 29 次，占 2.5%。
90+ 信号只有 1 次，而且是 XMRUSDT，被 watch_only 拦截。
因此 DIRECT=0 不是偶然，而是当前评分和门控组合下的必然结果。
```

### 2.3 组件平均分

| component | avg points | 满分 | 结论 |
|---|---:|---:|---|
| trend_ema_context | 14.15 | 20 | 趋势环境不是主要瓶颈 |
| flow_cvd_confirmation | 12.82 | 18 | 资金流一般可用 |
| cci_momentum_quality | 3.60 | 14 | 动量质量较弱 |
| price_action_structure | 7.04 | 22 | PA 结构偏弱但不是最低 |
| fibonacci_location | 11.08 | 18 | Fib 位置中等 |
| risk_reward_geometry | 0.93 | 8 | 最大瓶颈 |

关键判断：

```text
EMA/CVD 可以给方向，但 CCI/PA/Fib/RR 负责位置质量。
当前真正卡住开仓频率的是 RR，其次是 CCI 和 Fib。
```

---

## 3. 亏损结果归因

### 3.1 窗口内 paper trade 明细

| 时间 CST | event | symbol | side | score | lev | notional | reason | PnL |
|---|---|---|---|---:|---:|---:|---|---:|
| 02:45 | OPEN | HYPE | SHORT | 72.00 | 3 | 500 | PROBE | -0.50 |
| 03:30 | CLOSE | HYPE | SHORT | - | 3 | - | INITIAL_STOP_HIT | -8.49 |
| 05:00 | OPEN | LAB | SHORT | 81.30 | 3 | 500 | PROBE | -0.50 |
| 05:30 | CLOSE | LAB | SHORT | - | 3 | - | INITIAL_STOP_HIT | -8.27 |
| 16:15 | OPEN | LAB | SHORT | 89.25 | 3 | 500 | PROBE | -0.50 |
| 17:15 | REDUCE | LAB | SHORT | - | 3 | - | TP1_HIT | +5.81 |
| 18:00 | REDUCE | LAB | SHORT | - | 3 | - | TP2_HIT | +10.34 |
| 20:00 | CLOSE | LAB | SHORT | - | 3 | - | TP3_HIT | +11.14 |

### 3.2 按标的归因

| symbol | closed position result |
|---|---:|
| LABUSDT | +18.01 |
| HYPEUSDT | -8.99 |

LABUSDT 两笔：

```text
05:00 LAB SHORT：-8.77，INITIAL_STOP_HIT
16:15 LAB SHORT：+26.78，TP1 -> TP2 -> TP3
净：+18.01
```

HYPEUSDT 一笔：

```text
02:45 HYPE SHORT：score=72.00，3x，500 notional
03:30 INITIAL_STOP_HIT
净：-8.99
```

### 3.3 按退出原因归因

| reason | PnL |
|---|---:|
| TP1_HIT | +5.81 |
| TP2_HIT | +10.34 |
| TP3_HIT | +11.14 |
| INITIAL_STOP_HIT | -16.76 |

### 3.4 亏损模式判断

本窗口亏损不是高杠杆造成的，所有开仓都是 PROBE 3x、500 notional。亏损来自两类：

```text
HYPE 72 分低边缘 PROBE：
  分数刚好过线，trend_ema_context 只有 8/20。
  说明 72 分 PROBE 下限会放入较弱趋势上下文信号。

LAB 05:00 初始止损：
  score=81.30，Fib/PA/RR 均较好，但 30 分钟内止损。
  说明即使 Fib/PA 位置良好，仍需考虑短时波动/入场 bar 追空问题。
```

盈利来自 LAB 16:15：

```text
score=89.25
CCI=14, Fib=18, PA=21, RR=5
虽然 action 被 HIGH_BETA_PROBE_ONLY 降为 PROBE，但路径完整走到 TP3。
这说明 Fib/PA 高质量结构能够捕获趋势，但当前仓位太小，收益贡献被压低。
```

---

## 4. 为什么开仓数量不足

### 4.1 门控原因分布

| reason | count |
|---|---:|
| FIB_PA_ARCHITECTURE_WEIGHTS | 1157 |
| SIDE_THRESHOLD_OFFSET_LONG_10.00 | 389 |
| SYMBOL_BLACKLISTED | 177 |
| SYMBOL_WATCH_ONLY | 166 |
| FIB_EXTENSION_EXHAUSTION_BLOCK | 45 |
| PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0 | 29 |
| PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0 | 7 |
| DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0 | 3 |

### 4.2 RR 是最大频率瓶颈

RR 诊断：

```text
NET_TP1_R_TOO_LOW：752
OPPOSITION_STRUCTURE_TOO_CLOSE：3
NO_DIAG：402
```

这说明大部分 RR=0 不是因为支撑/阻力太近，而是净 TP1 R 不足。

当前 RR 公式近似：

```text
stop_dist = clamp(ATR * 1.5, 0.5%, 3.0%)
tp1_dist = stop_dist
fee/slippage estimate = close * 0.1%
net_tp1_r = (tp1_dist - fee) / stop_dist
```

问题：

```text
在低 ATR 或 stop_dist 被压缩时，手续费/滑点占 R 的比例变大。
大量候选因此 RR=0，导致 PROBE/DIRECT 都被降级。
```

### 4.3 LONG +10 抑制了多头采样

当前：

```text
SHORT:
  DIRECT >= 82
  PROBE  >= 70
  WATCH  >= 62

LONG:
  DIRECT >= 92
  PROBE  >= 77  # probe_conditions 中 long offset=+7
  WATCH  >= 72  # watch 仍使用 long_threshold_offset=+10
```

影响：

```text
LONG 候选不少，但大多落在 80-85。
这些信号无法进入 DIRECT，且经常被 RR minimum 再次压成 WATCH。
```

### 4.4 高分信号被名单拦截

高分拦截案例：

```text
XMRUSDT 90.69 SHORT -> SYMBOL_WATCH_ONLY
ZECUSDT 88.69 SHORT -> SYMBOL_BLACKLISTED
ZECUSDT 86.09 SHORT -> SYMBOL_BLACKLISTED
XRPUSDT 82.70 LONG  -> SYMBOL_BLACKLISTED
```

结论：

```text
名单机制保护了旧亏损标的，但也显著减少样本。
如果目标是增加 dry-run 样本，不建议直接解除黑名单；
更好的方式是增加 shadow paper track，记录“若允许开仓”的纸面路径。
```

### 4.5 Approved draft 与 paper open 不一致

22h 内：

```text
approved order drafts：6
paper actual opens：3
```

原因：

```python
PaperTradingLedger.on_decision():
    if symbol in self.positions:
        update existing position
    if draft approved and symbol not in self.positions:
        open new position
```

也就是说：

```text
17:15、18:00 的 LABUSDT approved draft 发生时，paper 已有 LAB 持仓。
paper ledger 不重复开仓，但 order_drafts 仍然 approved。
```

这暴露出一个链路不足：

```text
entry_chain context 没有从 paper/live position state 回填：
  active_symbols
  symbol_trades_today
  symbol_exposure_pct
  total_exposure_pct
  same_direction_exposure_pct

因此 entry gate 没有阻止同标的重复 draft。
paper ledger 最后挡住了实际重复开仓，但 audit 上会出现“approved 但未 open”的错位。
```

这是当前最重要的数据质量问题之一。

---

## 5. 当前实盘开仓链路

### 5.1 链路总览

```text
1. 拉取 public Binance K 线
2. warmup 检查 15m/30m/1h/4h
3. 生成 side：优先 1h direction_from_history，NONE 时用 15m 最近变化兜底
4. 计算 atr_pct、quote_volume、long flags
5. 计算 Fib/PA 架构 component_scores
6. evaluate_entry_chain:
   a. 动态权重
   b. Fib extension hard block
   c. hard block gates
   d. score -> action
   e. component minimum gates
   f. liquidity/high beta/profit day gates
   g. leverage select
   h. notional hint
7. apply_dry_run_decision_controls:
   a. observation_only
   b. rolling initial stop cooldown
   c. weak edge direct demotion
8. build_live_entry_order_draft
9. stress_decision
10. paper.on_decision
```

### 5.2 当前权重

| component | weight |
|---|---:|
| trend_ema_context | 20 |
| flow_cvd_confirmation | 18 |
| cci_momentum_quality | 14 |
| price_action_structure | 22 |
| fibonacci_location | 18 |
| risk_reward_geometry | 8 |

### 5.3 当前门槛

Base thresholds：

```json
{
  "direct_threshold": 82,
  "probe_threshold": 70,
  "watch_threshold": 62
}
```

Side offsets：

```text
SHORT direct/probe/watch offset = 0
LONG direct offset = +10
LONG probe offset = +7
LONG watch offset = +10
```

实际门槛：

| side | DIRECT | PROBE | WATCH |
|---|---:|---:|---:|
| SHORT | 82 | 70 | 62 |
| LONG | 92 | 77 | 72 |

### 5.4 DIRECT component minimums

```text
PA >= 6 / 22
Fib >= 6 / 18
RR >= 2 / 8
```

若不满足：

```text
DIRECT -> PROBE
记录：
  DIRECT_BELOW_PRICE_ACTION_STRUCTURE_MINIMUM_GAP_x
  DIRECT_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_x
  DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_x
```

### 5.5 PROBE component minimums

当前 dry-run config：

```json
{
  "enabled": true,
  "min_score": 72,
  "min_fib_score": 12,
  "min_pa_score": 6,
  "min_rr_net_r": 0.9,
  "min_rr_score": 2,
  "long_threshold_offset": 7,
  "short_threshold_offset": 0,
  "max_active_probes": 2
}
```

重要 caveat：

```text
entry_chain 当前没有把 rr_detail 传入 check_probe_conditions。
因此实际用于 PROBE gate 的是 min_rr_score=2，而不是 min_rr_net_r=0.9。
min_rr_net_r 目前主要作为 diagnostics 字段供日志分析。
```

### 5.6 杠杆选择

当前逻辑：

```text
如果 action 不是 PROBE/DIRECT -> leverage=0
rolling_sharpe_20 < 0 -> leverage=2
atr_pct > 3.0% -> leverage=3
atr_pct > 1.5% -> DIRECT=4, PROBE=3
score >= 90 且 DIRECT:
  若 Fib/PA 5x 条件满足 -> 5
  否则 -> 4
其他：
  DIRECT=4
  PROBE=3
```

5x 条件：

```text
score >= 90
action == DIRECT
fib >= 13
pa >= 9
cci >= 7
rr >= 4
```

本窗口没有 4x/5x，因为没有 DIRECT，全部开仓都是 PROBE 3x。

### 5.7 仓位管理

当前 `_notional_hint`：

```text
DIRECT:
  exposure_pct = base_direct_exposure_pct + min(10%, (score - direct_threshold)/100)

PROBE:
  exposure_pct = base_direct_exposure_pct * probe_fraction

notional_hint = min(
  score_based = equity * exposure_pct,
  risk_based = equity * risk_pct / stop_pct,
  cap_remaining
)
```

当前 config：

```text
base_direct_exposure_pct = 20%
probe_fraction = 25%
direct_risk_pct = 0.006
probe_risk_pct = 0.0025
max_large_cap_exposure_pct = default 30%
max_mainstream_exposure_pct = default 20%
max_high_beta_exposure_pct = default 10%
```

结果：

```text
PROBE notional 通常为 500 USDT
HIGH_BETA_SYMBOLS = HYPE/LAB/CC
high beta max exposure = 10%

目标中的“单交易对 20%-30% 浮动仓位”当前只可能在 DIRECT 上接近；
PROBE 不会达到这个仓位。
```

### 5.8 风控逻辑

Hard gates：

```text
SYMBOL_BLACKLISTED
SYMBOL_WATCH_ONLY
MACRO_WEEKLY_RISK
DATA_WICK_ANOMALY
DATA_POLLUTION_COOLDOWN
MAX_ACTIVE_SYMBOLS
DAILY_TRADE_BUDGET_USED
SYMBOL_DAILY_TRADE_BUDGET_USED
SYMBOL_COOLDOWN_ACTIVE
TOTAL_EXPOSURE_CAP
SAME_DIRECTION_EXPOSURE_CAP
MARGIN_BUFFER_TOO_LOW
ACCOUNT_EQUITY_INVALID
SIDE_NOT_ALLOWED
FIB_EXTENSION_EXHAUSTION_BLOCK
```

Soft/demotion gates：

```text
MACRO_DAILY_RISK_DIRECT_BLOCK：DIRECT -> PROBE
LIQUIDITY_DIRECT_BLOCK：DIRECT -> PROBE
HIGH_BETA_PROBE_ONLY：DIRECT -> PROBE
PROFIT_DAY_DIRECT_PLUS_THREE：DIRECT -> PROBE
PROFIT_DAY_PROBE_DISABLED：PROBE -> WATCH
component minimum failed：DIRECT -> PROBE 或 PROBE -> WATCH
```

Stress check：

```text
estimated_loss_pct = exposure_pct * leverage * adverse_move_pct
default adverse_move_pct = 20%
max_loss_pct = 25%

本窗口 PROBE:
  exposure=10%
  leverage=3
  stress_loss=0.1 * 3 * 0.2 = 6%
  低于 25%，ALLOW
```

---

## 6. 当前脚本不足

### 6.1 频率不足

当前实际 paper 开仓约 3.27 次/日，距离 10-20 次/日明显不足。

关键压制：

```text
RR 平均 0.93/8
CCI 平均 3.60/14
LONG direct/probe threshold 偏高
黑名单/观察名单拦截高分样本
High beta 被强制 PROBE，导致无 DIRECT/4x/5x 样本
```

### 6.2 风险状态未回填，导致 approved draft 与 paper open 错位

这是本窗口最清晰的工程问题：

```text
approved drafts = 6
paper opens = 3
```

原因是 paper 已有持仓时不重复开仓，但 entry_chain 仍然批准同 symbol draft。

建议 P0 修复：

```text
build_context 时从 PaperTradingLedger 回填：
  active_symbols
  symbol_trades_today
  portfolio_trades_today
  symbol_exposure_pct
  total_exposure_pct
  same_direction_exposure_pct
  daily_profit_pct

否则 MAX_ACTIVE_SYMBOLS / SYMBOL_DAILY_TRADE_BUDGET_USED / SYMBOL_EXPOSURE_CAP 在 dry-run 里不可信。
```

### 6.3 当前无法验证 3x/4x/5x 动态杠杆

本窗口：

```text
3x：全部开仓
4x：0
5x：0
```

原因：

```text
没有 DIRECT。
5x 只可能在 DIRECT 且 score >= 90 且 Fib/PA/CCI/RR 条件满足时出现。
```

所以当前日志无法判断 4x/5x 是否有效。

### 6.4 当前无法验证 20%-30% 单交易对仓位

所有实际开仓都是 PROBE，notional=500，约 5% equity。  
目标中的 20%-30% 仓位只会发生在 DIRECT，当前没有 DIRECT 样本。

### 6.5 目标胜率 80% 与当前数据差距大

当前累计 paper summary：

```text
equity=9844.31
realized_pnl=-155.69
return=-1.56%
max_drawdown=3.51%
profit_factor=0.678
win_rate=51.28%
trade_count=39
```

本窗口 closed positions：

```text
HYPE：loss
LAB：loss
LAB：win
位置级胜率约 33%
```

要达到 80% 胜率和 50% 月收益，目前不是“稍微调参”的问题，而是需要：

```text
更高样本量
更准确的亏损归因
DIRECT/4x/5x 的真实样本
分层统计不同 entry mode 的 expectancy
```

---

## 7. 为达到 10-20 次/日的参数建议

以下建议仅针对 dry-run 采样，不建议直接用于实盘。

### 7.1 频率目标换算

当前：

```text
13 symbols * 96 cycles/day = 1248 symbol-decisions/day
目标 10-20 opens/day = 0.8%-1.6% decision-to-open conversion
当前 3.27 opens/day = 0.26%
```

需要把 conversion 提升约 3-6 倍。

### 7.2 推荐调整顺序

P0：先修正状态回填，不然频率统计会被 approved/open mismatch 污染。

```text
目标：approved drafts 与 paper opens 的差异可解释。
```

P1：增加“sampling profile”，不要直接改生产风控 profile。

建议新建：

```text
configs/entry_chain.dry_run_fib_pa_sampling.json
```

用途：

```text
仅 dry-run 采样，目标 10-20 opens/day。
不用于实盘。
```

P2：放宽 PROBE，而不是先放宽 DIRECT。

建议：

```json
{
  "probe_threshold": 66,
  "probe_conditions": {
    "min_score": 68,
    "min_fib_score": 9,
    "min_pa_score": 6,
    "min_rr_score": 0,
    "long_threshold_offset": 4,
    "short_threshold_offset": 0
  }
}
```

理由：

```text
当前 RR 是最大瓶颈。
如果目标是采样，先允许 RR=0/1.5 的高 PA+Fib 信号进入 PROBE，
再用结果判断 RR 是否真的有预测力。
```

P3：允许部分高分 DIRECT，但必须有保护。

建议：

```json
{
  "direct_threshold": 80,
  "long_threshold_offset": 7,
  "pa_min_direct_score": 9,
  "fib_min_direct_score": 12,
  "rr_min_direct_score": 0
}
```

注意：

```text
这会让 DIRECT 数量增加，但可能显著增加亏损。
必须保留 paper-only，至少跑 3-7 天再评估。
```

P4：名单策略改为 shadow track，而不是直接解除。

```text
ZEC/XRP blacklist 不直接解除。
XMR/ADA watch_only 不直接解除。
但为这些标的记录 shadow_paper：
  若非名单拦截，是否会 OPEN?
  后续 1R/2R/3R 或 stop 结果如何?
```

### 7.3 不建议为了频率做的事

```text
不要直接取消 RR 组件。
不要直接解除 ZEC/XRP 黑名单。
不要直接允许 high beta 5x。
不要同时降低 DIRECT 和 PROBE 门槛并扩大仓位。
不要在状态回填修复前相信 approved draft 数量。
```

---

## 8. 给 Claude 的审查问题

1. 当前 RR 平均 `0.93/8`，且 `NET_TP1_R_TOO_LOW` 占绝对多数。RR 是真实保护，还是因为 TP1=1R 与费用/滑点假设导致过度压制？
2. 为提高 dry-run 样本量，是否应在 sampling profile 中把 `min_rr_score` 从 2 降到 0，同时保留 PA/Fib minimum？
3. LONG direct offset 是否应从 +10 降至 +7，LONG probe offset 从 +7 降至 +4？
4. 当前 high beta 标的全部被 DIRECT -> PROBE，导致无法验证 4x/5x。是否允许 high beta 在 Fib/PA/CCI/RR 全部强时进入 4x DIRECT？
5. 黑名单/观察名单是否应保持硬拦截，同时新增 shadow paper track？
6. dry-run entry context 未回填 paper position/trade state，导致 approved draft 和 paper open 不一致。是否应把这个列为 P0 工程修复？
7. 若目标是月开仓 300-600，是否应拆分两个配置：
   - `fib_pa_v1_strict`：策略真实性能评估
   - `fib_pa_v1_sampling`：扩大样本，仅用于归因

---

## 9. 建议下一步

优先级：

```text
P0 工程修复：
  将 paper/live position state 回填到 EntryChainContext。
  修复 approved draft 与 paper open 不一致。

P1 报告增强：
  每个被 RR 拦截的信号记录 net_tp1_r、stop_pct、tp1_pct、opposition_dist_r。
  当前已有 diagnostics，但 gate 内部还没有直接使用 rr_detail。

P2 采样配置：
  新建 dry-run sampling config。
  目标 10-20 opens/day。
  仅在 dry-run 使用。

P3 观察 48h：
  统计 PROBE/DIRECT 分层 PF、胜率、INITIAL_STOP_RATE、TP3_RATE。

P4 再决定是否扩大仓位：
  在 PF > 1、win rate > 60%、initial stop rate < 35% 前，不建议追求 20%-30% 仓位和 5x。
```

---

*报告结束 | 2026-06-27 latest 22h dry-run frequency + entry-chain review*
