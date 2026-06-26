# VPS Dry-Run 19小时复盘建议报告
> 2026-06-22 | 窗口：00:30–19:30 CST | 净亏损 -56.36 / -0.56%

---

## 目录

1. [执行诊断：核心矛盾的识别](#1-执行诊断核心矛盾的识别)
2. [符号跳跃反模式：ZEC→XLM→?](#2-符号跳跃反模式zecxlm)
3. [高分信号在错误时机开仓的根因](#3-高分信号在错误时机开仓的根因)
4. [空头入场防反转过滤器（立即实施）](#4-空头入场防反转过滤器立即实施)
5. [弱边缘 DIRECT 信号识别与处置](#5-弱边缘-direct-信号识别与处置)
6. [5X 杠杆使用条件收紧](#6-5x-杠杆使用条件收紧)
7. [Stop 子类型分类（数据质量修复）](#7-stop-子类型分类数据质量修复)
8. [多头侧休眠诊断](#8-多头侧休眠诊断)
9. [滚动标的冷却规格（完整实现）](#9-滚动标的冷却规格完整实现)
10. [禁止事项与行动优先级](#10-禁止事项与行动优先级)

---

## 1. 执行诊断：核心矛盾的识别

### 1.1 本窗口数据摘要

```
窗口长度：19 小时（76 个 15m 扫描周期）
开仓：7 笔（全部 SHORT）    平仓：7 笔
胜率：42.86%（3/7）         盈亏比：0.3993
净亏损：-56.36              最大回撤：0.85%

获利来源：TON +7.55，SOL +3.70（合计 +11.25）
亏损来源：XLM -50.52，LINK -17.09（合计 -67.61）
```

### 1.2 最关键的单一发现

```
ZEC 被加入黑名单后，亏损集群立即转移至 XLM。
XLM 的失败模式与 ZEC 几乎完全相同：
  → 多次高分空头开仓（89.65、87.90、94.65）
  → 多次全额止损（-26.68、-28.83）
  → 部分介于两者之间的 TP1 后保本平仓

这不是 ZEC 的问题，也不是 XLM 的问题。
这是策略在趋势动量耗尽时仍然开仓的系统性问题。
```

### 1.3 三个层次的问题区分

```
层次 A（系统性，本报告的核心）:
  评分体系无法区分"趋势延续"和"超卖反弹起点"
  高分（94.65）不能保护策略免受反向运动
  需要实现防反转过滤器，而非更换符号黑名单

层次 B（数据质量，影响判断的准确性）:
  STOP_HIT 将全额亏损与 TP1 后保本混为一谈
  当前 6 次 STOP_HIT 实际上只有 4 次是真正亏损
  需要 Stop 子类型分类后才能准确评估胜率

层次 C（边界优化，层次 A 解决后处理）:
  LINK 83.58 分弱边缘 DIRECT 的可行性
  5X 杠杆使用条件是否足够严格
  多头侧完全休眠是否符合策略预期
```

---

## 2. 符号跳跃反模式：ZEC→XLM→?

### 2.1 反模式的本质

```
ZEC 黑名单之前：
  ZEC SHORT 4 笔 → 3 次止损 → 加入黑名单

ZEC 黑名单之后（本窗口）：
  XLM SHORT 3 笔 → 3 次止损 → 考虑加入黑名单?

如果 XLM 被加入黑名单，接下来是什么?
  系统还有：SOL、DOGE、BNB、LINK、TON、HYPE...
  相同的短时动量耗尽场景会在任意符号上重现
```

**逐符号黑名单是对系统性问题的局部缓解，不是解决方案。**

### 2.2 XLM 与 ZEC 的结构对比

```
ZEC SHORT 失败模式（2026-06-20/21）:
  - 多次高分（90+）
  - 1h 方向 ✅，CVD ✅，EMA 空头排列 ✅
  - 价格处于近期支撑位附近（事后归因）
  - 止损被正常波动触及

XLM SHORT 失败模式（2026-06-22）:
  - 多次高分（87-94）
  - 1h 方向 ✅，CVD ✅，EMA 评分 ✅
  - 第三次开仓（12:00 CST）分数最高（94.65 → 5x），亏损最大（-28.83）
  - 同样的止损被正常波动触及
```

**核心一致性：** 两个符号失败的机制相同——评分体系在局部超卖之后、反弹之前发出最强的做空信号。这是经典的"趋势末期高分"问题。

### 2.3 XLM 的正确处置

```
建议：XLM 进入 observation_only（观察模式），不建议进入 blacklist

理由：
  blacklist = 无条件封锁，无任何诊断价值
  observation_only = 仍然评分并记录决策，不执行开仓

  这样做的好处：
  a. 如果 XLM 在未来 7 天评分高于 85 但未开仓，记录此类信号的"纸面表现"
  b. 可以在不承担真实亏损的情况下验证防反转过滤器是否会正确拒绝这些信号
  c. 如果纸面表现显示持续盈利，有依据解除限制

blacklist_symbols:  ["XRPUSDT", "ZECUSDT"]       # 有足够证据的永久负 Alpha
observation_only:   ["XLMUSDT"]                   # 临时降级，7天后重评
```

### 2.4 防止损失集群转移的系统性解法

未来任何新的损失集群（XLM 之后的下一个）在发生之前，应该被以下机制拦截：

```
机制 1：滚动标的冷却（见第 9 节）
  48小时内 ≥ 2 次全额止损 → 自动触发该标的 24小时禁止开仓

机制 2：防反转过滤器（见第 4 节）
  超卖追空惩罚 + 上影线检测 → 在动量末期降低评分，系统性减少此类开仓

机制 3：标的 Alpha 衰减（见第 9.2 节）
  近期 3-5 笔在该标的亏损 → 动态降低该标的评分置信度
```

---

## 3. 高分信号在错误时机开仓的根因

### 3.1 TON 成功 vs XLM 失败的对比分析

```
TON SHORT（+7.55，成功走完 TP1→TP2→TP3）:
  开仓时间：02:15 CST（TON）和 12:00 CST（TON 第二笔，后来止损）
  第一笔 TON：价格处于 4h 趋势延续中段，尚有动量空间
  TP1→TP2→TP3 连续触发 = 趋势健康延续

XLM SHORT（-50.52，3 次全额止损）:
  三次开仓分别在：02:15、06:00、12:00 CST
  每次价格都是在近期局部低点附近再次做空
  反弹（不是趋势逆转）就足以触发 1.5×ATR 止损
```

**关键差异：** TON 在做空时仍有 2-3× ATR 的下跌空间。XLM 在做空时已经处于短期支撑位附近，1.5×ATR 的止损被正常技术性反弹触及。

### 3.2 评分系统的盲区

```
当前评分系统测量（状态）：
  direction_1h:    当前 1h 方向是否向下？    ✅ 已下跌
  ema_50_quality:  EMA50 是否空头排列？       ✅ 空头
  cvd_flow:        CVD 是否偏负？             ✅ 偏负
  trigger_15m:     15m 是否有向下动量？       ✅ 刚下跌

当前评分系统不测量（历史）：
  已运行了多远？ ❌ 未检测
  与近期低点距离？ ❌ 未检测
  近期 ATR 压缩？ ❌ 未检测（价格可能即将 range）
  超卖深度？     ❌ 未检测
```

**结果：** 当价格已经下跌 3-4× ATR 后仍然触发空头信号（因为技术指标全部指向空头），但此时最优的做空时机早已过去。

### 3.3 需要新增的评分维度

```
维度 1：近期趋势年龄惩罚（momentum_age_penalty）
  同向 K 线连续运行 > 2× ATR → 对进一步同向开仓施加惩罚
  公式：age_penalty = max(0, cumulative_move / (2 * atr_pct) - 1.0) * 0.15
  效果：趋势运行越长，同向信号的评分折扣越大

维度 2：与近期极值的距离（proximity_to_extreme）
  计算当前价格与最近 20 根 K 线低点的距离（做空场景）
  距离 < 0.5×ATR → 评分惩罚（价格接近近期支撑）
  距离 < 0.3×ATR → 直接阻止开仓

维度 3：ATR 压缩检测（volatility_contraction）
  最近 5 根 K 线 ATR < 历史 20 根 K 线 ATR 均值的 60%
  → 波动率压缩，趋势可能即将转变，降低评分 15%
```

---

## 4. 空头入场防反转过滤器（立即实施）

基于两日连续亏损集群（ZEC + XLM），以下防反转过滤器应作为最高优先级实施：

### 4.1 过滤器 1：超卖深度追空惩罚

```python
def anti_exhaustion_multiplier(
    ohlcv: pd.DataFrame, side: str, atr_pct: float,
    lookback: int = 6
) -> tuple[float, str]:
    """
    检测最近 N 根 K 线累积跌幅，防止在超卖后继续做空
    """
    if side != "SHORT":
        return 1.0, ""

    drop = (ohlcv['close'].iloc[-1] - ohlcv['close'].iloc[-1 - lookback]) \
           / ohlcv['close'].iloc[-1 - lookback]

    if drop < -(2.5 * atr_pct):    # 跌幅 > 2.5× ATR：完全阻止
        return 0.0, "ANTI_EXHAUSTION_BLOCK"
    if drop < -(1.8 * atr_pct):    # 跌幅 > 1.8× ATR：严重惩罚
        return 0.4, "ANTI_EXHAUSTION_SEVERE"
    if drop < -(1.2 * atr_pct):    # 跌幅 > 1.2× ATR：轻度惩罚
        return 0.7, "ANTI_EXHAUSTION_MILD"
    return 1.0, ""
```

### 4.2 过滤器 2：上影线反转结构（空头场景）

```python
def reversal_wick_multiplier(
    ohlcv: pd.DataFrame, side: str, atr: float
) -> tuple[float, str]:
    """
    最近 3 根 K 线出现大上影线时，做空信号打折
    大上影线 = 上影线 > 实体 × 2 AND 上影线 > ATR × 0.5
    """
    if side != "SHORT":
        return 1.0, ""

    for bar in ohlcv.iloc[-3:].itertuples():
        body       = abs(bar.close - bar.open)
        upper_wick = bar.high - max(bar.close, bar.open)
        if upper_wick > body * 2.0 and upper_wick > atr * 0.5:
            return 0.65, "REVERSAL_WICK_DISCOUNT"
    return 1.0, ""
```

### 4.3 过滤器 3：近期支撑位接近度检测

```python
def proximity_to_support_multiplier(
    ohlcv: pd.DataFrame, side: str, atr: float,
    lookback: int = 20
) -> tuple[float, str]:
    """
    做空时检测价格与近期低点的距离，避免在支撑位做空
    """
    if side != "SHORT":
        return 1.0, ""

    current_price  = ohlcv['close'].iloc[-1]
    recent_low     = ohlcv['low'].iloc[-lookback:].min()
    distance       = (current_price - recent_low) / current_price

    if distance < 0.3 * atr:    # 距近期低点 < 0.3× ATR：阻止
        return 0.0, "PROXIMITY_TO_SUPPORT_BLOCK"
    if distance < 0.6 * atr:    # 距近期低点 < 0.6× ATR：惩罚
        return 0.6, "PROXIMITY_TO_SUPPORT_DISCOUNT"
    return 1.0, ""
```

### 4.4 集成到评分链（后处理乘数）

```python
def apply_short_anti_reversal(
    raw_score: float, ohlcv: pd.DataFrame,
    side: str, atr_pct: float, atr: float
) -> tuple[float, list[str]]:
    m1, t1 = anti_exhaustion_multiplier(ohlcv, side, atr_pct)
    m2, t2 = reversal_wick_multiplier(ohlcv, side, atr)
    m3, t3 = proximity_to_support_multiplier(ohlcv, side, atr)

    final_mult  = m1 * m2 * m3
    tags        = [t for t in [t1, t2, t3] if t]
    return raw_score * final_mult, tags

# 注意：乘数作用于 raw_score，不是 component_score
# XLM 94.65 × 0.0（超卖阻止）= 0 → REJECT（不再开仓）
```

---

## 5. 弱边缘 DIRECT 信号识别与处置

### 5.1 LINK 案例分析

```
LINK SHORT 开仓参数：
  Score: 83.5826
  Threshold: 82（SHORT DIRECT）
  Margin above threshold: 1.58 points
  Result: -17.09（全额止损）

这是一笔"勉强过线"的交易：
  82 分阈值意味着 1.58 分的边缘
  评分系统的测量误差 / 市场噪音就可以使其跌至阈值以下
  在无正向符号历史的情况下，这类信号的期望值不明确
```

### 5.2 弱边缘阈值建议

```
当前：SHORT DIRECT 阈值 = 82

建议分层处理：

  Score 82–85（弱边缘 DIRECT）:
    要求：符号 7 天内历史 local alpha > 0（至少 1 笔 TP1+）
    若无正向历史：降级为 WATCH（不开仓，仅观察）
    标签：DIRECT_WEAK_EDGE_DEMOTED

  Score 85–90（标准 DIRECT）:
    正常开仓，leverage = 4x（不允许 5x）

  Score 90+（强信号 DIRECT）:
    正常开仓，leverage 按 EMA 斜率选择（4x 或 5x）

实际效果：
  LINK 83.58 → 无 LINK 正向历史 → WATCH → 不开仓 → 节省 17.09
  XLM 89.65 → 有 XLM 历史但近期全是止损 → 弱历史 → 降 4x（而非 5x）
```

### 5.3 当前窗口分数分布回顾

```
DIRECT 信号分数范围：83.58 – 94.65（均值 88.68）

按分段损益：
  83–85 区间（LINK 83.58）：-17.09        ← 弱边缘，建议屏蔽
  85–90 区间（XLM 87.90/89.65，SOL 86.65，TON 88.59/87.11）：
    XLM -50.52（2 笔），SOL +3.70，TON +7.55
    混合结果，取决于防反转过滤器
  90+ 区间（XLM 94.65）：-28.83          ← 高分但高风险（5x 杠杆放大）

结论：分数高低本身与本窗口的损益无明显相关
防反转过滤 > 分数门槛调整
```

---

## 6. 5X 杠杆使用条件收紧

### 6.1 当前 5X 触发条件

```
条件：Score ≥ 90 AND action == DIRECT
本窗口触发：XLM 94.65 → 5x → 2000 notional → 止损 -28.83
```

**问题：** 94.65 分是本窗口最高分，也是单笔最大亏损。5x 将损失放大 25%（相比 4x）。

### 6.2 建议的 5X 附加条件（AND 关系，全部满足）

```yaml
leverage_5x_conditions:
  score_min:             90.0     # 保持原有条件
  action:                DIRECT   # 保持原有条件
  
  # 新增条件（全部必须满足）
  ema50_slope_steep:     true     # EMA50 斜率 > SLOPE_STEEP 阈值
  anti_exhaustion_pass:  true     # 防反转过滤器通过（乘数 = 1.0）
  no_reversal_wick:      true     # 近 3 根 K 线无反转上影线
  symbol_recent_pnl_pos: true     # 该标的近 5 笔中至少 1 笔盈利
  atr_pct_range:                  # ATR 在合理区间
    min: 0.008                    # ATR > 0.8%（非超低波动）
    max: 0.030                    # ATR < 3.0%（非超高波动）

fallback_leverage:       4        # 不满足任一条件 → 降为 4x
```

### 6.3 量化影响

```
若以上条件在本窗口生效：
  XLM 94.65：anti_exhaustion 未通过（价格已超卖）→ 降为 4x
  本次 XLM 12:00 CST 止损损失：
    原：2000 × 1.5% × 5 = 实际 -28.83
    若 4x：约 -23 USDT（改善约 6 USDT）
    若被防反转过滤器阻止（乘数 = 0）：不开仓，节省 28.83

5x 条件收紧的最大价值不是降低 5x 损失，
而是强制每一笔 5x 交易通过防反转过滤器的审查。
```

---

## 7. Stop 子类型分类（数据质量修复）

### 7.1 当前问题

```
本窗口 6 次 STOP_HIT：
  真正亏损止损：XLM -26.68，LINK -17.09，XLM -28.83，TON -21.23（4 次）
  TP1 后保本止损：SOL +3.70，XLM +4.99（2 次）

现有日志无法区分这两类 → 对策略的误判

如果仅看 STOP_HIT 数量（6 次），会高估止损频率
真实"亏损止损"只有 4 次（66%），而非 6 次（100%）
```

### 7.2 止损子类型规格

```python
class StopExitReason(str, Enum):
    INITIAL_STOP_HIT    = "INITIAL_STOP_HIT"    # TP1 前被止损（真实亏损）
    BREAKEVEN_STOP_HIT  = "BREAKEVEN_STOP_HIT"  # TP1 后保本被止（通常小正/微负）
    TRAILING_STOP_HIT   = "TRAILING_STOP_HIT"   # 移动止损被触发（通常有一定利润）

def classify_stop_exit(position: PaperPosition) -> StopExitReason:
    if not position.tp1_reached:
        return StopExitReason.INITIAL_STOP_HIT
    elif position.trailing_stop_active:
        return StopExitReason.TRAILING_STOP_HIT
    else:
        return StopExitReason.BREAKEVEN_STOP_HIT
```

### 7.3 按子类型的有意义指标

```
正确的指标分层（修复后）：

  ── 真实亏损率 = INITIAL_STOP_HIT / total_closes
     本窗口：4/7 = 57.1%（而非当前呈现的 85.7%）

  ── 捕获盈利率 = (TP_CLOSES + BREAKEVEN_STOP) / total_closes
     本窗口：(2 TP3/TP1 + 2 BREAKEVEN) / 7 = 57.1%

  ── 每笔全额止损平均亏损 = sum(INITIAL_STOP_HIT PnL) / count
     本窗口：(-26.68 -17.09 -28.83 -21.23) / 4 = -23.46 USDT/笔

  ── 每笔 TP 路径平均盈利
     本窗口：(+7.55 TON + 3.70 SOL + 4.99 XLM_TP) / 3 = +5.41 USDT/笔

  盈亏比（正确计算）：5.41 / 23.46 = 0.23（非常差）
  → 需要防反转过滤器大幅降低 INITIAL_STOP_HIT 频率
```

---

## 8. 多头侧休眠诊断

### 8.1 现状与两种可能

```
本窗口：SHORT DIRECT 17 次，LONG DIRECT 0 次

场景 A（可接受）：当前市场整体偏空
  → BTC 横盘或下跌，多数 altcoin EMA200 压力重
  → 多头 92 分阈值确实无法满足，策略按预期工作

场景 B（需要修正）：参数叠加过度抑制多头
  → long_threshold_offset=+10 叠加 CVD 折扣 + 上影线折扣
  → 策略实质上已成为纯空头系统，方向性风险集中
```

### 8.2 最低限度的监控要求

```
下一轮 dry-run 报告必须增加：

  LONG WATCH 最高分：____（本窗口未记录）
  SHORT WATCH 最高分：____

  判断逻辑：
  若 LONG WATCH 最高分 < 80：市场确实无多头 Alpha，可接受
  若 LONG WATCH 最高分 > 85 但被 offset 阻挡：
    → 考虑将 long_threshold_offset 从 +10 降至 +7
    → 前提：防反转过滤器已实装（避免多头信号引发反向止损）
```

---

## 9. 滚动标的冷却规格（完整实现）

### 9.1 当前冷却机制的局限

```
现有：max_symbol_trades_per_day = 1（UTC 日切割）

局限：
  ZEC 在 2026-06-20 止损 → 2026-06-21 重新开仓（跨日重置）
  XLM 在本窗口 02:15 止损 → 06:00 重新开仓（同日但同标的第 2 笔）
  XLM 第 2 笔后 → 12:00 又开第 3 笔（共 3 次止损）

原因：daily trade count 按日计算，不是按滚动窗口
```

### 9.2 滚动冷却规格

```python
@dataclass
class SymbolCooldownConfig:
    # 止损次数触发冷却
    stop_count_threshold:  int   = 2      # 滚动窗口内 ≥ N 次全额止损 → 触发
    stop_window_hours:     int   = 48     # 滚动窗口长度（小时）
    cooldown_hours:        int   = 24     # 冷却时长
    
    # 冷却期间允许的行为
    allow_watch_during_cooldown: bool = True   # 允许 WATCH 诊断
    block_direct_during_cooldown: bool = True  # 阻止 DIRECT
    block_probe_during_cooldown:  bool = True  # 阻止 PROBE

def check_symbol_cooldown(
    symbol: str,
    paper_state: PaperState,
    config: SymbolCooldownConfig,
    now: datetime
) -> tuple[bool, str]:
    """
    返回 (is_in_cooldown, reason)
    """
    # 检查主动冷却状态
    if symbol in paper_state.symbol_cooldowns:
        cooldown_until = paper_state.symbol_cooldowns[symbol]
        if now < cooldown_until:
            remaining = (cooldown_until - now).seconds // 3600
            return True, f"SYMBOL_COOLDOWN_{remaining}H_REMAINING"

    # 检查是否需要触发新冷却
    window_start = now - timedelta(hours=config.stop_window_hours)
    recent_stops = [
        t for t in paper_state.closed_trades
        if t.symbol == symbol
        and t.exit_reason == StopExitReason.INITIAL_STOP_HIT
        and t.close_time > window_start
    ]

    if len(recent_stops) >= config.stop_count_threshold:
        # 触发冷却
        cooldown_until = now + timedelta(hours=config.cooldown_hours)
        paper_state.symbol_cooldowns[symbol] = cooldown_until
        return True, f"SYMBOL_COOLDOWN_TRIGGERED"

    return False, ""
```

### 9.3 与现有机制的交互

```
优先级顺序（从高到低）：
  1. SYMBOL_BLACKLISTED（黑名单 → 完全封锁，无诊断）
  2. SYMBOL_COOLDOWN（冷却 → 封锁 DIRECT/PROBE，保留 WATCH）
  3. SYMBOL_WATCH_ONLY（观察模式 → 保留 WATCH 诊断，封锁开仓）
  4. 正常评分流程

若 XLM 冷却生效（02:15 第一次止损 + 06:00 第二次止损 → 触发冷却）：
  12:00 CST 的 XLM SHORT（94.65，5x）→ 被 SYMBOL_COOLDOWN 阻止
  节省：28.83 USDT（本窗口最大单笔亏损）
```

---

## 10. 禁止事项与行动优先级

### 10.1 禁止事项（本轮不做）

```
❌ 不要立即把 XLMUSDT 加入 blacklist
   理由：应先通过防反转过滤器修复系统性问题；黑名单只是转移问题

❌ 不要把短线 DIRECT 阈值从 82 提高到 87 以上
   理由：阈值提升会减少开仓量，但不能解决"高分信号在错误时机触发"问题

❌ 不要根据本 19 小时窗口调整 TP 层级
   理由：TON 成功走完 TP1→TP2→TP3，表明 TP 结构是合理的
         问题在于有多少信号能到达 TP1，而非 TP 层级本身

❌ 不要全面降低杠杆（如把所有 DIRECT 改为 3x）
   理由：TON TP3 是本窗口的主要盈利来源，降低杠杆也会同比降低该收益

❌ 不要在防反转过滤器实装之前讨论实盘部署
   理由：当前系统在超卖后仍持续开仓，这个根本问题未解决前不应使用实金
```

### 10.2 行动优先级

```
┌───────────────────────────────────────────────────────────────┐
│ P0（24小时内）：立即实施                                       │
│  1. 实现 Stop 子类型分类（INITIAL / BREAKEVEN / TRAILING）     │
│  2. 实现滚动 48h 标的冷却（≥2 次 INITIAL_STOP_HIT → 24h 封）  │
│  3. XLMUSDT 进入 observation_only（不进黑名单）                │
│  4. 在每日报告中记录 LONG/SHORT WATCH 最高分                   │
├───────────────────────────────────────────────────────────────┤
│ P1（3-5天内）：核心修复                                        │
│  5. 实装防反转过滤器三层（超卖惩罚 + 上影线 + 支撑接近）       │
│  6. 弱边缘 DIRECT（82-85）加入历史 Alpha 要求                  │
│  7. 5X 杠杆附加防反转过滤器通过要求                            │
│  8. 新增 momentum_age_penalty 和 proximity_to_extreme 评分维度  │
├───────────────────────────────────────────────────────────────┤
│ P2（14天 dry-run 观察后评估）                                  │
│  9. 基于 Stop 子类型数据重新计算真实盈亏比                      │
│  10. 评估防反转过滤器的命中率和误杀率                           │
│  11. 重新审视 long_threshold_offset 是否需从 +10 降至 +7       │
│  12. 累计 ≥ 30 笔 INITIAL_STOP_HIT 数据后，重新校准 ATR 止损   │
├───────────────────────────────────────────────────────────────┤
│ 不进入日程（除非数据反证）                                      │
│  · 全面降杠杆                                                  │
│  · 提高空头阈值 > 85                                           │
│  · 实盘部署                                                    │
└───────────────────────────────────────────────────────────────┘
```

### 10.3 下一轮 Claude 审查的触发条件

```
提交下一轮 dry-run 审查的前提：

  必须项（全部满足）：
  □ paper state 已持久化（跨日连续）
  □ Stop 子类型分类已实现
  □ 滚动标的冷却已实现
  □ 防反转过滤器已实装

  数据要求（满足其一）：
  □ 连续 7 天 dry-run 数据（固定 paper state）
  □ 或：≥ 30 笔 INITIAL_STOP_HIT 封闭记录（足够的止损样本）

  可选但建议：
  □ XLMUSDT 在 observation_only 模式下的"纸面表现"记录
    （验证防反转过滤器是否会正确阻止 XLM 信号）
```

---

*报告结束 | 19H Dry-Run Review v1.0 — 2026-06-22*
*主要结论：ZEC 和 XLM 的连续亏损模式证明这是一个系统性问题，而非符号问题。防反转过滤器是当前最重要的单项优化，应优先于任何阈值调整和杠杆变更。*
