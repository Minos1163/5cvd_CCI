# VPS Dry-Run 两日复盘建议报告
> Paper Trading Review — 2026-06-20 至 2026-06-21
> 日期：2026-06-21 | 数据来源：logs/2026-06 两日折叠事件

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [P0 Bug 修复：必须先于策略评判](#2-p0-bug-修复必须先于策略评判)
3. [ZEC 止损集群：根因诊断](#3-zec-止损集群根因诊断)
4. [空头入场防反转过滤器](#4-空头入场防反转过滤器)
5. [评分体系与实盘的背离分析](#5-评分体系与实盘的背离分析)
6. [门控架构与开仓频率分析](#6-门控架构与开仓频率分析)
7. [TP/SL 收益结构问题](#7-tpsl-收益结构问题)
8. [持仓与风控管理改进](#8-持仓与风控管理改进)
9. [验证方法论改进](#9-验证方法论改进)
10. [优先级路线图](#10-优先级路线图)

---

## 1. 执行摘要

### 1.1 两日 dry-run 核心指标

```
跨日折叠事件（去重）：

  开仓次数：    10 次
  平仓次数：     7 次（含 4 次止损、1 次超时、2 次 TP1）
  已实现 PnL：  -94.86
  止损亏损：   -114.88（占总亏损 121%）
  TP1 盈利：    +35.14（可能虚高，存在重复触发 bug）
  胜率：         28.57%（2/7，且可能虚高）
  盈亏比：       0.2703

  当前开仓：ZECUSDT SHORT，未实现 -23.50
  主要亏损来源：ZECUSDT（4 笔，合计 -69.29）
```

### 1.2 三个层级问题的区分

```
层级 A（数据失真）: 先修 Bug，再评判策略
  → TP1 重复触发导致盈利虚高
  → 每日 paper state 重置导致跨日对比无效
  → 杠杆计算方式与回测不一致

层级 B（即时风险）: 现在就该停止的行为
  → ZEC 重复止损（4 笔内 3 次同向同标止损）
  → 高分信号在逆势行情中持续亏损（评分系统存在结构性盲区）

层级 C（中期优化）: Bug 修复后基于真实数据讨论
  → 门控架构与开仓频率
  → TP/SL 收益结构
  → 多头实际可用性
```

---

## 2. P0 Bug 修复：必须先于策略评判

### 2.1 Bug #1：TP1 重复触发（最高优先级）

**现象：** 2026-06-21 的 ZEC SHORT 和 TON LONG 事件日志均显示：
- TP1 触发（减仓 40%）
- 随后再次 TP1 触发（再减仓 40%）
- 最终以 TP1 名义平仓剩余 20%

正确行为：TP1 触发后该档位应标记为「已消耗」，后续只能触发 TP2（35%）或 TP3（25%）。

**影响量化：**
```
假设 TON LONG +14.97 = 正确单次 TP1（40% 仓位）
如果实际触发 3 次 TP1：
  第一次 TP1（40%）= 正确盈利
  第二次 TP1（40%，应为 TP2 价格）= 低估的盈利（价格比 TP2 更早）
  第三次 TP1（20%，应为 TP3 价格）= 更低估的盈利

修复后实际 PnL 可能低于当前账面 35.14，盈亏比 0.2703 可能进一步恶化
```

**修复规范：**
```python
# paper_ledger.py 中的 TP 状态机

@dataclass
class PaperPosition:
    symbol:          str
    side:            str
    entry_price:     float
    notional:        float
    remaining_frac:  float = 1.00          # 当前剩余仓位比例
    tp_consumed:     set[int] = field(default_factory=set)  # 已触发的 TP 档位

def apply_tp_event(position: PaperPosition, bar_high, bar_low, tp_config):
    """
    按顺序检查未消耗的 TP 档位，每 bar 最多触发一档
    """
    for idx, (level_r, fraction) in enumerate(zip(
        tp_config.tp_levels, tp_config.tp_fractions
    )):
        if idx in position.tp_consumed:
            continue   # 已消耗，跳过

        tp_price = compute_tp_price(position, level_r)
        if bar_hits_tp(position.side, bar_high, bar_low, tp_price):
            position.tp_consumed.add(idx)     # 标记消耗
            reduce_fraction = fraction / position.remaining_frac  # 占剩余仓位比
            position.remaining_frac -= fraction
            return PartialExitEvent(idx=idx, price=tp_price, fraction=fraction)
            # 每 bar 只返回一个事件，不继续检查后续 TP

    return None  # 当前 bar 未触发任何 TP
```

### 2.2 Bug #2：每日 Paper State 重置

**现象：** 2026-06-21 的 equity 从 10000 重新开始，而非从 2026-06-20 的 9897.80 延续。

**影响：** 无法评估多日累计回撤、连续亏损序列、整体 win rate。

**修复方案：**
```
文件结构重组：

  当前（有问题）：
    logs/2026-06/2026-06-20/paper_state.json  ← 每日重置
    logs/2026-06/2026-06-21/paper_state.json  ← 每日重置

  建议（修复后）：
    state/paper/paper_state.json              ← 持久化，跨日连续
    logs/2026-06/2026-06-20/daily_snapshot.json  ← 每日快照，只读
    logs/2026-06/2026-06-21/daily_snapshot.json

paper_state.json 包含：
  - 当前未平仓头寸（带完整状态包括 tp_consumed）
  - 累计 equity curve
  - 全周期已实现 PnL
  - 持久化的 daily_max_trades 计数器（配套UTC日期键）
```

### 2.3 Bug #3：杠杆计算方式未标明

**现象：** 账面记录 leverage=5x，但 PnL 按名义价值计算（非保证金 × 杠杆）。

**影响：** 当前 paper PnL 与回测结果不可直接对比。2000 notional 的 5x 开仓，保证金仅 400，若按保证金计算亏损，每笔止损相当于保证金的 6-7%。

**建议：** 在修复 paper state 的同时，添加双轨 PnL 记录：
```python
@dataclass
class PaperTradeRecord:
    notional_pnl:   float   # 当前已记录的基于名义价值的 PnL（保留兼容性）
    margin_pnl:     float   # 新增：基于保证金的 PnL（= notional_pnl × leverage）
    leverage:       int
    margin_used:    float   # = notional / leverage
```

---

## 3. ZEC 止损集群：根因诊断

### 3.1 ZEC 损失明细

```
日期        事件                  PnL
──────────────────────────────────────
2026-06-20  ZECUSDT SHORT STOP_HIT   -26.78
2026-06-20  ZECUSDT SHORT STOP_HIT   -36.72
2026-06-21  ZECUSDT SHORT STOP_HIT   -25.96
2026-06-21  ZECUSDT SHORT TP1_HIT    +20.16
            当前未平仓 SHORT           -23.50（未实现）
────────────────────────────────────────────
合计（含未实现）                       -92.80
占全部已实现亏损比例                    73.2%
```

三次 STOP_HIT 均为做空，方向相同，时间间隔短。这是**系统性重复开空**进入反弹行情，而非偶发亏损。

### 3.2 根因分析

```
假说 1（概率最高）：ZEC 处于局部超卖反弹
  → 15m/1h 下行动量使 direction + CVD 评分高
  → 但短期超卖后的修复式反弹触发了止损
  → EMA 空头排列 + CVD 负向 同时出现，但属于动量末期信号
  → 评分系统无法区分"趋势延续做空"和"超卖反弹起点"

假说 2（概率中等）：ZEC 24h 波动率与 ATR 止损不匹配
  → ZEC ATR 可能短期压缩（低波动）→ 止损设为 0.5% 下限 → 实际波幅 > 0.5%
  → 止损被正常 ZEC 价格噪音触及，而非真正趋势反转

假说 3（概率中等）：冷却机制未阻止同标的连续开仓
  → 当前配置 max_symbol_trades_per_day=1（每日上限）
  → 但分布在不同 UTC 日，冷却未跨日生效
  → 导致 ZEC SHORT 在 2026-06-20 和 2026-06-21 均能开仓
```

### 3.3 即时行动：ZEC 临时加入黑名单

```json
// configs/entry_chain.dry_run_highest_win.json 立即更新
{
  "blacklist_symbols": ["XRPUSDT", "ZECUSDT"],
  "blacklist_expiry": {
    "ZECUSDT": "2026-07-05"   // 临时黑名单，14天后重新评估
  }
}
```

**添加依据：** 4笔 ZEC 交易（含当前未平），3次止损，未实现也为负。14天内无历史正收益样本，与 XRPUSDT 在回测中的表现高度类似。

### 3.4 长期方案：标的级别动态冷却

```python
def should_apply_symbol_cooldown(symbol: str, recent_trades: list) -> bool:
    """
    连续止损触发标的级冷却（跨日有效）
    """
    recent_stops = [
        t for t in recent_trades
        if t.symbol == symbol
        and t.reason == "STOP_HIT"
        and t.close_time > now() - timedelta(hours=48)
    ]
    if len(recent_stops) >= 2:
        return True   # 48小时内 ≥ 2 次止损 → 触发 24 小时冷却
    return False

# 冷却期间的行为：
#   - 允许 WATCH 决策（保留信号日志）
#   - 阻止 DIRECT 和 PROBE 开仓
#   - 在日志中标记原因：SYMBOL_STOP_COOLDOWN
```

---

## 4. 空头入场防反转过滤器

### 4.1 当前评分对"超卖反弹"的盲区

当前空头评分的核心因子（direction_1h + CVD + EMA 排列）在以下情况下**全部错误一致看空**：
- 价格已大幅下跌，但即将出现技术性反弹
- 庄家止损猎杀，短暂下刺后反转
- 成交量放大（实际为空头踩踏，后续反向）

这类情况中，1h 方向为负、CVD 为负、EMA 空头排列——系统给出最高空头评分，却恰好在最糟糕的入场时机开仓。

### 4.2 防反转过滤器规格（三层）

```python
# 三个乘数，依次相乘作用于原始评分

# 过滤器 1：超卖追空惩罚
# 最近 6 根 15m K线累积跌幅 > 2×ATR → 乘数 0.0（阻止）
# 最近 6 根 15m K线累积跌幅 > 1.5×ATR → 乘数 0.5（严惩）
ANTI_EXHAUSTION: side="SHORT", lookback=6, atr_mult_block=2.0, atr_mult_warn=1.5

# 过滤器 2：上影线反转结构
# 最近 3 根 K线出现：上影线 > 实体 2 倍 AND 上影线 > ATR × 0.5
# 做空时触发 → 乘数 0.70（打折 30%）
REVERSAL_WICK: side="SHORT", lookback=3, wick_body_ratio=2.0, wick_atr_ratio=0.5

# 过滤器 3：高量反向 K线
# 最近一根 K线：量 > 20日均量 2 倍 且方向与信号相反
# 做空遇到高量阳线 → direction_1h 乘数 0.60
HIGH_VOLUME_REVERSAL: side="SHORT", volume_mult=2.0, score_discount=0.60

# 集成：在 evaluate_entry_chain() 完成基础评分后，
# 空头信号追加三层乘数，产生标签记录到日志
effective_score = raw_score × exhaustion_mult × wick_mult × volume_mult
```

### 4.3 过滤器预期效果

| 市场场景 | 触发过滤器 | 评分变化 |
|---|---|---|
| 6根K线累积跌 > 3% + ATR=1% | 超卖追空 | 评分归零，REJECT |
| 最近出现长上影线 + 计划做空 | 反转上影线 | 评分 × 0.70 |
| 前一根大阳线 + 计划做空 | 高量反向 | direction_1h × 0.60 |
| 三者同时出现（ZEC 典型情景） | 全部触发 | 评分大幅压缩，跌破阈值 |

---

## 5. 评分体系与实盘的背离分析

### 5.1 高分不等于高胜率的实证

```
ZEC SHORT 评分情况（据日志推断）：
  score ≥ 90（多次），leverage = 5x
  背景：direction_1h ✅，CVD ✅，EMA ✅，liquidity ✅
  结果：3/4 次止损

这表明当前评分体系存在一个关键盲区：
  所有组件测量的是"当前状态"，没有任何组件测量"信号发出时刻的市场疲劳度"

类比：
  一辆车时速 120km（当前状态）≠ 还能加速（未来趋势）
  评分体系测量的是时速 120km，但没有测量油箱余量
```

### 5.2 缺失的评分维度

| 缺失维度 | 描述 | 建议组件名称 |
|---|---|---|
| 动量持续性 | 同方向已运行多少根 K 线 | `momentum_age_penalty` |
| 超卖/超买深度 | 当前价格相对近期低点的距离 | `reversion_risk_score` |
| 近期失败率 | 同标的过去 5 笔信号的成功率 | `symbol_alpha_decay` |
| 大周期方向疲劳 | 4h 趋势持续时间 | `background_exhaustion` |

### 5.3 symbol_alpha_decay：动态标的质量衰减

```python
def compute_symbol_alpha_decay(
    symbol: str,
    recent_trades: list[dict],
    lookback: int = 5
) -> float:
    """
    基于近期同标的交易结果动态调整信号置信度
    返回乘数：1.0（全置信）到 0.5（半置信）
    """
    symbol_trades = [
        t for t in recent_trades
        if t['symbol'] == symbol
    ][-lookback:]

    if len(symbol_trades) < 2:
        return 1.0   # 样本不足，不惩罚

    win_count = sum(1 for t in symbol_trades if t['pnl'] > 0)
    local_wr  = win_count / len(symbol_trades)

    if local_wr < 0.20:      # 近期胜率不足 20%
        return 0.50          # 半置信
    elif local_wr < 0.40:    # 近期胜率 20-40%
        return 0.75          # 3/4 置信
    else:
        return 1.00          # 正常置信

# 集成方式：作为 score 的乘数，而非单独权重
effective_score = raw_score * compute_symbol_alpha_decay(symbol, recent_trades)
```

---

## 6. 门控架构与开仓频率分析

### 6.1 决策分布现状

```
两日总决策（~1700 次）：

  NO_TRADE  : 1185（69.7%）
  WATCH     :  492（28.9%）
  DIRECT    :   32（ 1.9%）
  DIRECT→开仓:  10（ 0.6%，约 5 次/天）

5 次/天 × 30天 = 150 次/月
但受 daily_max_trades=4 限制 → 实际上限 4 次/天 = 120 次/月
两日实际 7 次关闭（含一次超时），符合 90-120 次/月的数量目标
```

### 6.2 最大拒绝来源分析

```
Top 拒绝标签：

  SIDE_THRESHOLD_OFFSET_LONG_10.00  471次  多头 +10 阈值提升效果
  LONG_CVD_WEAK_DISCOUNT            197次  多头 CVD 不足
  SYMBOL_WATCH_ONLY                 178次  ADA/XMR 硬封锁
  LONG_CHASE_TRIGGER_DISCOUNT       135次  多头追涨惩罚
  PROBE_COMPONENT_MINIMUM_FAILED    131次  Probe 组件分不足（但 Probe 已禁用）
  LONG_UPPER_WICK_TRIGGER_DISCOUNT  115次  多头上影线惩罚
  SYMBOL_BLACKLISTED                 89次  XRP 黑名单

观察 1：多头几乎被完全屏蔽
  471 次 LONG 阈值拒绝 + 197 次 CVD 拒绝 + 135 次追涨 + 115 次上影线
  = 918 次多头相关拒绝，远超 NO_TRADE 总量 1185 次
  → 多头在当前设置下事实上无法开仓（需要 92 分 + CVD + 无追涨 + 无上影线）

观察 2：PROBE_COMPONENT_MINIMUM_FAILED 仍在记录
  Probe 已禁用，该标签应被 PROBE_DISABLED 完全替代
  目前可能存在逻辑顺序问题：
  组件最低分检查在 Probe 禁用标记之前运行，产生了不必要的日志噪音
```

### 6.3 watch_only_symbols 语义问题

```
当前行为：ADAUSDT 和 XMRUSDT 被 watch_only_symbols 标记，
          但实际执行的是硬封锁（等同于 blacklist）

建议区分两种语义：

  blacklist_symbols:
    - 完全拒绝，连 WATCH 记录都不生成
    - 用于：已知负 Alpha 的标的（XRPUSDT、ZECUSDT 临时）

  watch_only_symbols（语义修正）:
    - 允许评分和 WATCH 决策，产生诊断日志
    - 阻止 DIRECT 和 PROBE 开仓
    - 用于：待观察标的（ADAUSDT、XMRUSDT）

配置字段建议重命名：
  watch_only_symbols → observation_only_symbols（仅观察，不开仓）
  blacklist_symbols  → 保持不变（完全封锁）
```

---

## 7. TP/SL 收益结构问题

### 7.1 现有 TP1 尺寸与止损的对比

```
止损：ATR × 1.5，下限 0.5%，上限 3.0%
TP1：1R（= 止损距离 × 1.0）
TP1 平仓比例：40%

假设止损 = 1.5%（典型 ZEC ATR 场景）：
  止损触发：全仓亏损 1.5%（= 2000 × 1.5% = 30 USDT）
  TP1 触发：仅 40% 仓位盈利 1.5%（= 2000 × 40% × 1.5% = 12 USDT）

单次 TP1 + 后续止损（保本）：
  锁定：+12 USDT
  剩余 60% 仓位：保本平仓（理论 0 USDT，实际扣手续费 -6 USDT）
  实际净盈：+12 - 6 = +6 USDT

单次止损（未触 TP1）：
  损失：-30 USDT（全仓）

1次止损抵消 5次 TP1 盈利

当前样本中 4 次止损 vs 2 次 TP1：
  修复 bug 后真实比率可能更差
```

### 7.2 短期可行的 TP/SL 结构改进

```
方向：提高 TP1 后的潜在收益，或降低止损概率

方案 A（当前较合理）：维持 40/35/25 分批，加严 ATR 止损乘数
  现在：ATR × 1.5（止损偏宽，被 ZEC 噪音触发）
  建议：强趋势（EMA 斜率陡峭）→ ATR × 1.5
        弱趋势（EMA 斜率平缓）→ ATR × 1.2（止损收窄，防止噪音）

方案 B（更激进）：TP 层级拉宽
  TP1 = 1.5R（而非 1.0R），TP2 = 3.0R，TP3 = 5.0R
  代价：TP1 触发频率下降，但单次 TP1 盈利提升 50%
  需要回测验证触发率

方案 C（防御性）：入场后快速保本
  若持仓 6 根 K 线（1.5 小时）后未触 TP1，止损提升至 entry ± 0.5%
  防止长期持仓积累时间成本
  适用于当前 ZECUSDT 类型的高波动标的
```

---

## 8. 持仓与风控管理改进

### 8.1 当前 max_hold_bars = 32（已优于回测计划）

注意：dry-run 中已使用 `max_hold_bars=32`（8小时），优于此前回测计划建议的 96（24小时）。但 SOLUSDT 出现了 `MAX_HOLD_EXIT`（-15.12），说明在实际持仓路径中仍有无法自然出场的仓位。

**建议：** 保留 32 bars 上限，但加入方向衰减检测（持仓 16 bars 后若未触 TP1 且 EMA 斜率转平，主动出场）：

```python
def check_direction_decay_exit(
    position, current_bar_idx: int, ohlcv: pd.DataFrame
) -> bool:
    """
    持仓 16 bars（4小时）后，若 EMA50 斜率转平，提前出场
    防止持仓积累手续费和时间风险
    """
    hold_bars = current_bar_idx - position.entry_bar_idx
    if hold_bars < 16:
        return False

    ema50       = compute_ema(ohlcv['close'], 50)
    slope_now   = compute_ema_slope(ema50, lookback=3)
    slope_flat  = abs(slope_now) < SLOPE_FLAT_THRESHOLD

    if slope_flat and not position.tp1_reached:
        return True   # 持仓 4h 后方向衰减 + 未触 TP1 → 主动出场
    return False
```

### 8.2 单标的每日 1 笔限制的副作用

```
当前：max_symbol_trades_per_day = 1

副作用：
  - ZEC 在 2026-06-20 亏损后，2026-06-21 重新开仓了（跨日重置）
  - 跨日限制不起作用，每日独立计算

建议：使用滚动窗口而非 UTC 日切割：

  max_symbol_trades_per_rolling_48h = 1
  
  效果：某标的止损后，48小时内不再开仓（无论 UTC 日切割）
  实现：在 state/paper/symbol_trade_log.json 中记录每笔开仓时间，
       检查 now() - last_trade_time[symbol] > 48h
```

### 8.3 Daily Trade Budget 缩放逻辑确认

日志显示 `daily_max_trades` 可能自动缩减至 2-3。这需要明确确认是否符合预期：

```
建议记录在配置文档中：

  daily_max_trades_base:   4    # 正常日最大开仓数
  daily_drawdown_scaling:       # 当日亏损时自动收紧
    at_loss_pct: 0.50%          # 当日亏损 0.5%，max_trades → 3
    at_loss_pct: 1.00%          # 当日亏损 1.0%，max_trades → 2
    at_loss_pct: 1.50%          # 当日亏损 1.5%，max_trades → 1（仅观察）

以上行为若已实现，应在 dry-run report 中明确标出
若未实现，则 daily_max_trades 不应自动缩减
```

---

## 9. 验证方法论改进

### 9.1 现在就能判断的结论

```
即使不修复 Bug，以下结论已经成立：

  ✅ 运行健康：240-bar warmup 就绪，15m 对齐，13 个标的正常扫描
  ✅ 门控生效：XRP 黑名单可见，多头阈值 +10 效果可见，Probe 禁用生效
  ✅ EMA 架构运行：ema_50_quality + ema_momentum 权重在日志可见
  ✅ 费用模型运行：entry/exit fee 和 slippage 在 paper 事件中可见

  ❌ 不能判断真实胜率（TP1 bug 影响分子）
  ❌ 不能判断真实盈亏比（同上）
  ❌ 不能判断多日累积回撤（paper state 每日重置）
  ❌ 不能判断 ZEC 是真正的负 Alpha 还是 2 天样本噪音
```

### 9.2 修复 Bug 后的最小验证周期

```
阶段要求：

  Bug 修复后持续 dry-run 观察：最少 14 天（≥ 20 笔封闭交易）
  才能计算有意义的：
    - 胜率（±15pp 误差要求 ≥ 30 笔）
    - 盈亏比（需包含至少 5 笔盈利和 5 笔亏损）
    - 最大回撤（需要连续 equity 曲线）

  干预原则：
    14 天观察期内，若出现以下情况立即暂停：
    a. 累计亏损 > 5%（账户级）
    b. 任意单日亏损 > 2%
    c. 单标的在 7 天内出现 ≥ 3 次止损（启用临时黑名单）
    d. 盈亏比连续 5 笔 < 0.30（信号质量崩溃）
```

### 9.3 Claude 审查问题的建议回答

**问题 1（空头反转过滤器）：** 是，应实现本报告第 4 节的三个防反转过滤器，并在重新评估 ZEC 前先观察 7 天过滤器效果。

**问题 2（Symbol 级冷却）：** 是，建议先于任何杠杆或阈值调整实施。ZEC 的连续止损表明标的级 Alpha 已在短期衰减。

**问题 3（TP1 bug 修复后期望值）：** 修复后 2026-06-21 的 PF 很可能低于当前的 1.35，甚至可能 < 1.0。需要修复后重新评估。

**问题 4（跨日连续性）：** 是，应在 Bug #2 修复后（paper state 持久化）才能评估多日回撤和 win rate。

**问题 5（watch_only 语义）：** 建议重命名为 `observation_only_symbols`，并真正实现 WATCH 诊断（而非硬封锁），提高运营可读性。

**问题 6（杠杆化 PnL）：** 建议采用双轨记录（Bug #3 修复方案），报告中同时显示名义 PnL 和保证金 PnL，由运营者按需参考。

---

## 10. 优先级路线图

```
┌─────────────────────────────────────────────────────────────┐
│ P0：立即执行（24小时内）                                     │
│  → ZECUSDT 加入临时黑名单（14天）                            │
│  → 修复 TP1 重复触发 Bug                                     │
│  → 将 paper state 移至 state/paper/（跨日持久化）           │
│  → 添加双轨 PnL 记录（名义 + 保证金）                        │
├─────────────────────────────────────────────────────────────┤
│ P1：本周内完成（3-5天）                                      │
│  → 实现三个防反转过滤器（超卖惩罚 + 反转上影线 + 高量反向）  │
│  → 实现滚动 48h 单标的交易冷却（替代 UTC 日切割）            │
│  → 实现标的级 alpha_decay 乘数（近期连续亏损降低评分）        │
│  → 修正 PROBE_COMPONENT_MINIMUM_FAILED 日志顺序问题          │
│  → 重命名 watch_only → observation_only，修正语义            │
├─────────────────────────────────────────────────────────────┤
│ P2：14天 dry-run 观察期后（评估）                            │
│  → 基于修复后的真实胜率决定是否调整 TP 层级（方案 A/B/C）   │
│  → 基于 symbol_alpha_decay 数据决定哪些标的可从黑名单释放    │
│  → 评估多头是否在任何条件下能够盈利（92分门槛 + 当前市场环境）│
│  → 6 个月滚动回测（离线，不影响 dry-run）                    │
├─────────────────────────────────────────────────────────────┤
│ P3：不要做的事                                               │
│  → 在 P0 Bug 修复前讨论胜率和盈亏比是否改善                  │
│  → 在 ZEC 黑名单期间尝试调整 ZEC 止损距离                    │
│  → 在 14天观察期完成前上线实盘资金                           │
│  → 在 paper state 持久化前信任跨日累计 PnL 数据              │
└─────────────────────────────────────────────────────────────┘
```

---

*报告结束 | VPS Dry-Run Review v1.0 — 2026-06-21*
*下一步触发条件：P0 修复完成 → Codex 实施 → 重新运行 dry-run 24 小时 → 带修复后数据提交下一轮 Claude 审查*
