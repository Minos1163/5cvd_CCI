# 策略重构建议：Fibonacci + Price Action 替换 MACD/BOLL
> Entry Chain Architecture Refactor — CCI + CVD + EMA + PA + Fibonacci
> 日期：2026-06-26 | 基于 2026-06-22 至 2026-06-26 dry-run 数据

---

## 目录

1. [重构决策依据](#1-重构决策依据)
2. [回答 Claude 审查问题（七题）](#2-回答-claude-审查问题七题)
3. [新评分架构总览](#3-新评分架构总览)
4. [组件 1：EMA 趋势上下文（20分）](#4-组件-1ema-趋势上下文20分)
5. [组件 2：CVD 资金流向确认（18分）](#5-组件-2cvd-资金流向确认18分)
6. [组件 3：CCI 动量质量（14分）](#6-组件-3cci-动量质量14分)
7. [组件 4：价格行为结构（22分）](#7-组件-4价格行为结构22分)
8. [组件 5：斐波那契位置过滤（18分）](#8-组件-5斐波那契位置过滤18分)
9. [组件 6：风险回报几何（8分）](#9-组件-6风险回报几何8分)
10. [位置优先门控顺序](#10-位置优先门控顺序)
11. [杠杆选择重设计](#11-杠杆选择重设计)
12. [消融实验设计（A→E）](#12-消融实验设计ae)
13. [配置规格与参数边界](#13-配置规格与参数边界)
14. [实施计划与测试覆盖](#14-实施计划与测试覆盖)
15. [禁止事项与路线图](#15-禁止事项与路线图)

---

## 1. 重构决策依据

### 1.1 核心数据证据

```
Dry-run 2026-06-22 20:00 → 2026-06-26 09:30（22 笔封闭交易）：

  胜率：54.55%     盈亏比：0.77     净亏损：-67.38 USDT

  按分数区间损益（最关键数据）：
  ─────────────────────────────────────────────────
  分数 82-85   3 笔    -27.26    胜率 33%
  分数 85-90   5 笔    +13.04    胜率 80%
  分数 90+    14 笔    -53.15    胜率 50%
  ─────────────────────────────────────────────────

  分数 90+ 亏损 53.15（最高分区间是最大亏损来源）
  5x 杠杆亏损 53.15，4x 杠杆亏损 14.23

结论：当前评分体系是趋势"同意度"的量化，不是入场"位置质量"的量化。
```

### 1.2 代表性失败案例归纳

```
BNB SHORT 95.67分 5x → -41.69（22:15）
BNB SHORT 95.67分 5x → -46.96（23:00）
LINK SHORT 90.13分 5x → -26.77（-3.61% 大阴线后追空）
TON LONG 96.85分 → -27.35（空头反转前方向做多）
TON SHORT 87.65分 → -27.23（两小时后反向做空又止损）

共同特征：
  所有组件满分（direction=1.0, cvd=1.0, trigger=1.0）
  但入场时价格已在动量末期、局部支撑附近、或大波动后缺乏回撤确认
  MACD/BOLL 不能识别此类位置问题（它们测量的也是"趋势状态"）
```

### 1.3 MACD 和 BOLL 为何无法解决位置问题

```
MACD 的信息内核：
  快线/慢线 EMA 交叉 = 两个不同周期的动量比较
  与 EMA50/EMA200 高度相关 → 冗余（已有 EMA 架构）
  在大幅下跌后 MACD 继续维持空头状态 = 确认"趋势对齐"，不是确认"位置合理"

BOLL 的信息内核：
  价格相对 ± 2σ 的位置 = 统计超卖/超买
  问题：在趋势行情中价格可沿布林带外侧运行数十根 K 线
  替换 BOLL 的更精确工具：Fib 扩展目标 + 价格行为结构

替换后的信息增量：
  Price Action 识别"该位置是否有有效的做空理由"
  Fibonacci 识别"当前价格是否已处于合理的扩展/回撤目标区"
  两者回答的是 MACD/BOLL 从未回答的问题：你站在哪里
```

---

## 2. 回答 Claude 审查问题（七题）

### Q1：Fibonacci 应作为硬门控还是乘数？

**建议：分层处理（既不是纯硬门控，也不是纯乘数）。**

```
层级 1 — 硬门控（REJECT，不进入评分）：
  条件：SHORT 时价格已在 1.618 扩展目标以下 0.5×ATR 内
  解释：价格已超越正常扩展目标，追空风险极高
  标签：FIB_EXTENSION_EXHAUSTION_BLOCK

层级 2 — 重度乘数（评分 × 0.50）：
  条件：SHORT 时价格在 1.272–1.618 扩展区间内，无回撤确认
  解释：价格在扩展区但未看到明确的继续动量信号
  标签：FIB_EXTENSION_ZONE_PENALTY

层级 3 — 轻度乘数（评分 × 0.75）：
  条件：SHORT 时价格不在任何已知的回撤/支撑位附近
  解释：位置中性，非最优入场点
  标签：FIB_NEUTRAL_LOCATION

层级 4 — 正常权重（评分 × 1.0 + 加分）：
  条件：SHORT 时价格在 0.382–0.618 回撤区重新确认下行
  解释：最优做空位置（回撤后续跌）
  标签：FIB_PULLBACK_RETEST_VALID

理由：纯硬门控会过度减少开仓次数；
      纯乘数在极端情况下（1.618+）仍可能允许高分通过。
      分层处理在极端情况用硬门控保护，正常情况用乘数调节。
```

### Q2：哪种 Swing 算法最不容易过拟合 15m 加密数据？

```
建议：分形摆动算法（Fractal Swing）+ 时间约束 + ATR 有效性过滤

核心规则：
  确认摆动高点：第 N 根 K 线的 high > 前后各 K 根 K 线（K=2 或 3）
  确认摆动低点：第 N 根 K 线的 low < 前后各 K 根 K 线

过拟合防护：
  a. ATR 有效性：摆动幅度 >= 1.5×ATR，否则视为噪音摆动
  b. 最小时间间隔：相邻同向摆动之间至少 6 根 K 线（90分钟）
  c. 最大回溯：只用最近 50 根 K 线内的摆动（防止远期结构干扰）
  d. 时间框架：优先使用 1h 摆动用于 Fib 计算，15m 摆动用于局部确认

对比其他方法：
  ZigZag（固定百分比）：参数敏感，不同币种需要不同参数 ❌
  HH/HL/LH/LL：简单但易产生假结构 ❌
  ATR 通道突破：噪音过多 ❌
  分形+ATR 过滤：参数少（仅 K 值和 ATR 乘数），泛化能力强 ✅
```

### Q3：Fib 应从 1h、15m 还是两者计算？

```
建议：双层 Fib，优先使用 1h，用 15m 进行局部确认。

1h Fib（主 Fib，权重 60%）：
  用途：确定大级别回撤/扩展区间，防止在大级别扩展目标追空
  参数：最近 3 个 1h 摆动点
  优点：噪音少，结构更可靠

15m Fib（辅助 Fib，权重 40%）：
  用途：确认局部入场位置，检测是否在近期 15m 低点附近做空
  参数：最近 2 个 15m 摆动点（最近的一个完整脉冲）
  优点：更精细，但需要 ATR 过滤防止假摆动

集成逻辑：
  if 1h_fib_exhaustion:     FIB_BLOCK（优先级最高）
  elif 1h_fib_optimal:      +score_bonus（最优位置）
  elif 15m_fib_support_near: -score_penalty（局部支撑风险）
```

### Q4：CCI 应完全替换 MACD 还是仅作为上限？

```
建议：CCI 替换 MACD 作为独立组件，但承担不同职责（不是 MACD 的简单替代）。

CCI 的正确职责（动量质量层）：
  ✅ 识别动量耗竭（CCI < -150 后不再创新低 = 熊方疲软）
  ✅ 识别回撤质量（CCI 从 -150 回升至 -100 但价格未回升 = 空方控制有效）
  ✅ 识别失败延续（CCI 无法突破 +100/-100 的方向确认失败）
  ✅ 配合 Fib 使用（价格在 Fib 回撤区 + CCI 二次走弱 = 最优入场）

CCI 不应承担的职责（已由其他层处理）：
  ❌ 趋势方向判断（由 EMA 层处理）
  ❌ 整体信号打分（由 Fib/PA 位置层处理）
  ❌ 代替 CVD 资金流向（CVD 是量价关系，CCI 是纯价格）

结论：CCI 替换 MACD 是正确的，但 CCI 只作为第三层（动量质量确认），
      不能成为主要驱动因子（Fib + PA 是主要驱动）。
```

### Q5：5x 是否应暂停直到 Fib/PA 验证产生 PF > 1.2？

```
建议：是，但不是完全暂停，而是条件化使用。

过渡期（Fib/PA 实装后前 30 笔封闭交易）：
  5x 额外要求：
    a. Fib 位置必须在 0.382-0.618 回撤区（最优位置）
    b. Price Action 必须有明确的重测失败（非追趋势）
    c. CCI 二次走弱确认（非首次突破极端值）
    d. 防反转过滤器全部通过

解除 5x 限制的条件：
  前 30 笔包含 5x 的交易中，5x 子集 PF > 1.2
  且 90+ 分区间胜率 > 60%（目前仅 50%）
```

### Q6：TONUSDT 是否应进入 observation_only？

```
建议：是，但理由不是两次止损，而是"方向快速翻转模式"。

TON 的特殊性：
  4 小时内 LONG → SHORT（两次方向相反的高分信号都止损）
  这表明 TON 在该时段处于快速震荡状态
  高分信号在震荡市中的特点：两个方向都会得到高分（各有支持的短期动量）

处置：
  observation_only（7天），同时增加 TON 的 market_regime 检测要求
  只有当 TON 的 4h 趋势方向稳定超过 12 根 K 线才允许 DIRECT 开仓
```

### Q7：BNB 集群是否意味着需要市场级别机制过滤器？

```
建议：是，应实现 BTC/宏观同步衰减机制。

BNB 2026-06-25 集群的背景：
  多个符号同日失败（LINK、SOL、DOGE 也在 06-25 出现 INITIAL_STOP_HIT）
  这不是单个符号问题，是该时段市场整体行为的表达
  → 可能是 BTC 在某时段出现技术性反弹，带动多数 altcoin 同步反转

市场级别过滤器规格：
  BTC 15m 动量衰减：若 BTC 最近 4 根 K 线方向与空头信号相反，全局降分 15%
  BTC 短期拉升：若 BTC 1h 涨幅 > 1.5%，SHORT 信号全局加 -20 分惩罚
  BTC 整体方向：作为 background_4h 组件的输入之一（4h BTC 方向）
```

---

## 3. 新评分架构总览

### 3.1 旧架构 vs 新架构

```
旧架构（被替换）：                新架构（建议）：
─────────────────────              ─────────────────────
background_4h        5             trend_ema_context      20
direction_1h        18             flow_cvd_confirmation  18
quality_30m         12             cci_momentum_quality   14
trigger_15m          7             price_action_structure 22
ema_50_quality      15             fibonacci_location     18
ema_momentum        10             risk_reward_geometry    8
cvd_flow            18             ─────────────────────────
volatility_stop     10             合计                  100
liquidity_execution  3
market_regime        2
─────────────────────
合计               100

移除：MACD（已无此组件），BOLL（已无此组件）
     background_4h/direction_1h/quality_30m/trigger_15m 合并至 EMA+PA 两层
     volatility_stop/liquidity 合并至 risk_reward_geometry 层
     market_regime 移至 BTC 同步机制（前置检查）
```

### 3.2 信息层次关系

```
┌───────────────────────────────────────────────────────────────┐
│  信息维度           原来由谁负责        现在由谁负责          │
├───────────────────────────────────────────────────────────────┤
│  趋势方向合法性     EMA50/200           EMA 趋势上下文        │
│  趋势强度/质量      EMA斜率/30m质量     EMA 趋势上下文        │
│  短期动量触发       trigger_15m/MACD    Price Action 结构     │
│  价格位置合理性     BOLL（不足）        Fibonacci 位置        │
│  入场结构有效性     无                  Price Action 结构     │
│  动量是否耗竭       CCI（旧）→RSI被移除 CCI 动量质量（新）    │
│  资金流向确认       CVD                 CVD（保留，调整权重）  │
│  风险几何可行性     volatility_stop     Risk/Reward Geometry  │
└───────────────────────────────────────────────────────────────┘
```

---

## 4. 组件 1：EMA 趋势上下文（20分）

### 4.1 职责边界

```
负责：趋势环境是否允许该方向开仓（软约束，不再是硬门控）
不负责：具体价格位置（由 Fib 负责）/ 入场结构（由 PA 负责）
```

### 4.2 评分规则（三子组件）

```
A. EMA200 方向合法性（8分）
   SHORT + 价格在 EMA200 下方：8 分
   SHORT + 在 EMA200 上方 0.3% 缓冲内：4 分（模糊区）
   SHORT + 明显在 EMA200 上方：0 分（不再硬拒绝，由总分决定）

B. EMA50 趋势质量（7分）
   价格在 EMA50 下方 + 斜率陡峭（> 0.3%/5bar）：7 分
   价格在 EMA50 下方 + 斜率温和（> 0.1%/5bar）：5 分
   价格在 EMA50 下方 + 斜率接近平：3 分
   价格在 EMA50 上方但斜率向下（回撤中）：1.5 分
   价格在 EMA50 上方且斜率向上：0 分

C. EMA9/21 短期动量排列（5分）
   EMA9 < EMA21 < EMA50（完美空头排列）：5 分
   EMA9 < EMA21 仅短期空头：3 分
   EMA9 > EMA21（逆向）：0 分
```

### 4.3 重要变化：EMA200 不再是硬门控

```
旧架构：EMA200 方向违反 → 直接 REJECT
新架构：EMA200 方向违反 → EMA 组件得 0 分（最多失去 20 分总分）
        只有当 Fib + PA + CVD 均极强时，总分才可能通过阈值

理由：Fib/PA 层已承担了位置合法性检查
      允许极少数在"EMA 方向模糊区"存在超强 PA/Fib 信号的入场
      保留的唯一硬门控：Fib 扩展耗竭（FIB_EXTENSION_EXHAUSTION）
```

---

## 5. 组件 2：CVD 资金流向确认（18分）

### 5.1 职责变化（关键）

```
旧：CVD 是主要驱动因子，可以独立支撑开仓决策
新：CVD 是确认层——只有在 Fib/PA 位置有效后，CVD 才有意义
    CVD 强 + Fib 无效 → 被 Fib 截止，CVD 加分不传递至总分
    CVD 背离 → 无论 Fib/PA 多优秀，上限降为 WATCH
```

### 5.2 评分规则（四子组件，合计 18 分）

```
A. CVD 方向一致性（8分）
   CVD 6根K线斜率明显向下（SHORT）：8 分
   CVD 温和向下：4 分
   CVD 不支持空头：0 分

B. CVD 背离检测（负向，最高 -6分）
   价格创新低但 CVD 未同步（看涨背离）+ 计划做空：-6 分
   触发后行动上限降为 WATCH（不开仓）

C. CVD 冲量（6分）
   最后 3 根 K 线 CVD 连续向下：6 分
   2 根：4 分 / 1 根：2 分 / 0 根：0 分

D. 成交量放大确认（4分）
   最近 3 根 K 线 CVD 绝对值均值 > 历史 9 根均值 × 1.5：4 分
   > 1.0：2 分 / 否则：0 分
```

### 5.3 CVD 背离作为行动上限

```python
def cvd_action_cap(cvd_series, price_series, side, current_action) -> str:
    """
    CVD 背离时，无论总分多高，动作上限为 WATCH
    """
    price_new_extreme = is_new_extreme(price_series, side, lookback=12)
    cvd_not_new_extreme = not is_new_extreme(cvd_series, side, lookback=12)

    if price_new_extreme and cvd_not_new_extreme:
        # 背离：价格创新低但 CVD 未同步
        return "WATCH"  # 强制降级
    return current_action
```

---

## 6. 组件 3：CCI 动量质量（14分）

### 6.1 CCI 的新职责：不是方向判断，是质量判断

```
旧 CCI 用法：CCI < -100 → 空头动量存在 → 加分（越极端越高分）
新 CCI 用法：评估动量状态的可持续性（越极端反而越低分）

四种 CCI 状态（以 SHORT 为例）：

状态 1 — 健康下行（CCI -80 至 -150）：
  趋势初始阶段，中等质量，还有下跌空间
  得分：7 分

状态 2 — 回撤后二次走弱（CCI 从 -150 回升至 -80 后再次走弱）：
  最优做空信号：回撤确认支撑失效，方向有效但不超卖
  配合 Fib 0.382-0.618 回撤区使用
  得分：10 分（满分）

状态 3 — 过度延伸（CCI < -150 持续）：
  超卖，反弹风险高，LINK -3.61% 大阴线的 CCI 特征
  新规则：越极端越低分（-150 → 3分，-200 → 1分）
  得分：0-3 分

状态 4 — 失败延续（CCI 无法维持在 -100 以下）：
  方向疲软，不应开新仓
  额外惩罚：-4 分
  得分：0 分（可能为负）
```

### 6.2 评分规则表

```
状态             条件                           CCI 分数（满分14）
────────────────────────────────────────────────────────────────
二次走弱（最优）  -150 ≤ CCI ≤ -80 且近期曾回撤    10
健康下行         -150 ≤ CCI ≤ -100 且未回撤         7
回撤中（向下）   -100 < CCI < -50 且斜率向下         5
方向不支持       CCI ≥ -50                          0
过度延伸         CCI < -150                         max(0, 3+(CCI+150)×0.02)
失败延续（惩罚） 曾 < -120，现在 > -80              base - 4
```

---

## 7. 组件 4：价格行为结构（22分）

### 7.1 职责边界（最重要的新组件）

```
PA 结构层回答的问题："此时此刻开仓，是否有结构理由支持？"

有效的空头 PA 结构（从高到低质量）：
  最高：下降趋势中低点重测失败（LH retest 失败）          → 12/12 结构分
  高：  突破后回踩确认（breakdown retest）                 → 9/12 结构分
  中：  强势阴线延续（非超卖末期）                         → 6/12 结构分
  低：  单纯追随已发生的大幅下跌（无结构支撑）             → 0/12 结构分
  无效：大上影线、包阳线、明显吸收K线后做空                → -4分惩罚

合计 22 分 = 结构分（12）+ 入场K线质量（6）+ 趋势摆动一致性（4）
```

### 7.2 摆动点检测规范

```
分形摆动算法（低过拟合风险）：
  摆动高点：第 N 根 K 线的 high > 前后各 K 根 K 线（K=2）
  摆动低点：第 N 根 K 线的 low  < 前后各 K 根 K 线（K=2）

过拟合防护：
  ① ATR 有效性：摆动幅度 ≥ 1.2×ATR，否则视为噪音
  ② 最小间隔：相邻同向摆动之间至少 6 根 K 线（90分钟）
  ③ 最大回溯：仅用最近 50 根 15m K 线
  ④ 只保留最近 5 个有效摆动点

Fib 计算优先使用 1h 摆动（减少噪音），PA 结构使用 15m 摆动（局部确认）
```

### 7.3 PA 评分规则

```python
def score_price_action_structure(ohlcv, side, swing_highs, swing_lows, atr):
    # A. 结构类型识别（最高 12分）
    if side == "SHORT":
        if detect_lower_high_retest(ohlcv, swing_highs, atr):
            a_score, pa_type = 12.0, 'LOWER_HIGH_RETEST'      # 最优
        elif detect_breakdown_retest(ohlcv, swing_lows, atr):
            a_score, pa_type = 9.0, 'BREAKDOWN_RETEST'        # 良好
        elif detect_continuation_structure(ohlcv, side, atr):
            a_score, pa_type = 6.0, 'CONTINUATION'            # 中等
        else:
            a_score, pa_type = 0.0, 'NO_STRUCTURE'            # 追涨杀跌

    # B. 入场K线质量（最高 6分，最低 -4分）
    body       = abs(ohlcv['close'].iloc[-1] - ohlcv['open'].iloc[-1])
    upper_wick = ohlcv['high'].iloc[-1] - max(ohlcv['close'].iloc[-1], ohlcv['open'].iloc[-1])
    if side == "SHORT":
        if body > atr * 0.3 and upper_wick < body * 0.5:  b_score = 6.0   # 实体阴线
        elif upper_wick > body * 1.5:                      b_score = -4.0  # 大上影线
        else:                                              b_score = 2.0

    # C. 摆动趋势一致性（最高 4分）
    c_score = detect_hh_hl_structure(swing_highs, swing_lows, side) * 4.0

    return max(0.0, min(22.0, a_score + b_score + c_score))
```

### 7.4 关键场景举例

```
LINK -3.61% 大阴线追空（本次亏损案例）：
  detect_lower_high_retest = False（价格直接突破低点，无回测）
  detect_breakdown_retest  = False（刚突破，无回踩确认）
  detect_continuation      = False（不是合理延续，是追杀）
  → a_score = 0，total PA = 0 + K线质量（阴线6分）= 6分
  → 满足组件最低分 6 分，但无结构支撑
  → 若 Fib 同时不在最优区，总分很可能低于 DIRECT 阈值
```

---

## 8. 组件 5：斐波那契位置过滤（18分）

### 8.1 Fib 计算

```python
def compute_fib_levels(
    swing_high: float, swing_low: float, trend: str
) -> dict:
    """
    计算关键 Fib 层位（回撤 + 扩展）
    trend: "DOWN" 对应空头场景（从高点向低点的 Fib）
    """
    diff = swing_high - swing_low

    if trend == "DOWN":
        return {
            # 回撤层位（做空回撤入场）
            'r382': swing_low + diff * 0.382,   # 38.2% 回撤（黄金比例入场区下沿）
            'r500': swing_low + diff * 0.500,   # 50.0% 回撤（中位入场）
            'r618': swing_low + diff * 0.618,   # 61.8% 回撤（黄金比例入场区上沿）
            'r786': swing_low + diff * 0.786,   # 78.6% 回撤（深度回撤，风险升高）

            # 扩展层位（从低点向下）
            'e1000': swing_low,                            # 0% 扩展 = 原低点
            'e1272': swing_low - diff * 0.272,             # 127.2% 扩展目标
            'e1618': swing_low - diff * 0.618,             # 161.8% 扩展目标
            'e2000': swing_low - diff * 1.000,             # 200% 扩展目标
        }
    else:  # UP（对称）
        return {
            'r382': swing_high - diff * 0.382,
            'r500': swing_high - diff * 0.500,
            'r618': swing_high - diff * 0.618,
            'r786': swing_high - diff * 0.786,
            'e1000': swing_high,
            'e1272': swing_high + diff * 0.272,
            'e1618': swing_high + diff * 0.618,
            'e2000': swing_high + diff * 1.000,
        }
```

### 8.2 Fib 位置评分

```python
def score_fibonacci_location(
    close: float, side: str,
    fib_1h: dict,        # 1h 级别的 Fib 层位
    fib_15m: dict,       # 15m 级别的 Fib 层位
    atr: float,
    config: dict
) -> tuple[float, str, dict]:
    """
    返回：(分数, 门控标签, 详情)
    """
    tolerance = atr * 0.5   # 接近 Fib 层位的容差

    # ── 硬门控（直接 BLOCK）────────────────────────────────────
    if side == "SHORT":
        # 价格在 1h 1.618 扩展目标附近或以下
        if fib_1h and close <= fib_1h['e1618'] + tolerance:
            return 0.0, "FIB_1H_EXTENSION_EXHAUSTION_BLOCK", {}

        # 价格在 15m 1.618 扩展目标附近
        if fib_15m and close <= fib_15m['e1618'] + tolerance:
            return 0.0, "FIB_15M_EXTENSION_EXHAUSTION_BLOCK", {}

    else:  # LONG
        if fib_1h and close >= fib_1h['e1618'] - tolerance:
            return 0.0, "FIB_1H_EXTENSION_EXHAUSTION_BLOCK", {}
        if fib_15m and close >= fib_15m['e1618'] - tolerance:
            return 0.0, "FIB_15M_EXTENSION_EXHAUSTION_BLOCK", {}

    # ── 评分层（乘数 → 转换为 0-18 分）────────────────────────
    score = 9.0   # 基础中性分（无信息 = 中性）
    tag   = "FIB_NEUTRAL"

    if side == "SHORT" and fib_1h:
        fib = fib_1h
        if fib['r382'] - tolerance <= close <= fib['r618'] + tolerance:
            # 最优：在 38.2%–61.8% 回撤区（即做空 retest 区）
            score = 18.0;  tag = "FIB_1H_PULLBACK_OPTIMAL"
        elif fib['r618'] < close <= fib['r786'] + tolerance:
            # 深度回撤区，稍差但可接受
            score = 13.0;  tag = "FIB_1H_DEEP_PULLBACK"
        elif fib['e1272'] - tolerance <= close < fib['e1000']:
            # 1.272 扩展区：已到目标，但还没到 1.618
            score = 6.0;   tag = "FIB_1H_EXTENSION_1272"
        elif close < fib['e1272'] - tolerance:
            # 1.272 以下，接近 1.618 目标区
            score = 2.0;   tag = "FIB_1H_EXTENSION_ZONE_PENALTY"

    # 15m Fib 辅助调整（±3分）
    if fib_15m:
        if side == "SHORT":
            # 15m 支撑位接近（做空风险）
            dist_to_15m_low = close - fib_15m['e1000']   # 距 15m 近期低点
            if 0 < dist_to_15m_low < tolerance:
                score -= 3.0   # 接近 15m 支撑，做空位置差
                tag += "_15M_SUPPORT_NEARBY"

    return max(0.0, min(18.0, score)), tag, {}
```

---

## 9. 组件 6：风险回报几何（8分）

### 9.1 职责

```
计算：在当前位置开仓，TP1 的可达性是否合理

输入：
  stop_pct   = ATR × 1.5（已有）
  tp1_pct    = stop_pct × 1.0（TP1 = 1R，已有）
  nearby_resistance = 最近的阻力位（PA/Fib 层输出）

规则：
  DIRECT 要求：TP1 可达路径 >= 1.1R（扣除手续费后）
  5x 要求：TP1 可达路径 >= 1.3R
  若 TP1 之前存在明显支撑/阻力位 → 扣分
```

### 9.2 评分规则

```python
def score_risk_reward_geometry(
    close: float, side: str,
    atr: float, atr_stop_mult: float,
    nearby_opposition_price: float,  # 最近的支撑（空头）或阻力（多头）
    fee_pct: float = 0.001           # 总手续费估计（进出合计）
) -> tuple[float, dict]:

    stop_dist  = atr * atr_stop_mult
    stop_dist  = max(close * 0.005, min(close * 0.030, stop_dist))  # 0.5%–3% 限制
    tp1_dist   = stop_dist * 1.0    # TP1 = 1R
    tp1_target = close - tp1_dist if side == "SHORT" else close + tp1_dist

    # 有效 TP1 路径（扣除手续费）
    net_tp1_r  = (tp1_dist - fee_pct * close) / stop_dist

    score = 0.0

    # ── A. TP1 净 R 值（最高 5 分）──────────────────────────────
    if net_tp1_r >= 1.3:
        a_score = 5.0
    elif net_tp1_r >= 1.1:
        a_score = 3.5
    elif net_tp1_r >= 0.9:
        a_score = 2.0
    else:
        a_score = 0.0   # 净 R < 0.9，几乎无优势
    score += a_score

    # ── B. 对立结构接近度（最高扣 3 分）────────────────────────
    if nearby_opposition_price is not None:
        if side == "SHORT":
            # 空头中，支撑位在 TP1 之前
            dist_to_support = close - nearby_opposition_price
            if 0 < dist_to_support < tp1_dist * 0.7:
                score -= 3.0   # 支撑位在 TP1 之前 → 大幅扣分
            elif 0 < dist_to_support < tp1_dist:
                score -= 1.5
        else:  # LONG
            dist_to_resist = nearby_opposition_price - close
            if 0 < dist_to_resist < tp1_dist * 0.7:
                score -= 3.0
            elif 0 < dist_to_resist < tp1_dist:
                score -= 1.5

    # ── C. ATR 合理性（最高 3 分）──────────────────────────────
    atr_pct = atr / close
    if 0.008 <= atr_pct <= 0.025:    # 合理波动区间
        c_score = 3.0
    elif 0.005 <= atr_pct < 0.008:   # 低波动（止损易被穿刺）
        c_score = 1.5
    elif atr_pct > 0.030:            # 高波动（止损偏大，费用占比高）
        c_score = 1.0
    else:
        c_score = 0.0
    score += c_score

    return max(0.0, min(8.0, score)), {
        'net_tp1_r': round(net_tp1_r, 3),
        'stop_pct':  round(stop_dist / close, 4),
        'atr_pct':   round(atr_pct, 4)
    }
```

---

## 10. 位置优先门控顺序

### 10.1 新门控架构（强制位置优先）

```
当前（错误）：
  趋势对齐 → 评分 → 风险草案

建议（位置优先）：
  Step 0: 数据就绪检查（240 bars warmup，无陈旧数据）
  Step 1: EMA 合法性（软检查，0-8分，非硬门控）
  Step 2: 滚动标的冷却（SYMBOL_COOLDOWN 硬门控）
  Step 3: Fib 扩展耗竭（EXTENSION_EXHAUSTION 硬门控）→ REJECT
  Step 4: PA 结构有效性（最低分要求：≥ 6 分，否则降为 WATCH）
  Step 5: CVD 方向确认（背离检测：CVD 背离 → 降为 WATCH）
  Step 6: CCI 动量质量（失败延续 → 降分）
  Step 7: 风险回报几何（净 TP1 R < 0.9 → 降为 WATCH）
  Step 8: 加权总分计算
  Step 9: 阈值判定（DIRECT / WATCH）
  Step 10: 杠杆选择（Fib 位置 + 总分）
```

### 10.2 组件最低分要求（防止"低质量组件高总分"）

```python
COMPONENT_MINIMUMS = {
    "DIRECT": {
        "price_action_structure": 6.0,   # 必须有某种 PA 结构（满分 22）
        "fibonacci_location":     6.0,   # 不能处于极端扩展区（满分 18）
        "risk_reward_geometry":   2.0,   # 净 TP1 R 至少合格
    },
    "DIRECT_5X": {
        "price_action_structure": 9.0,   # 需要中等以上 PA 结构
        "fibonacci_location":    13.0,   # 需要在回撤区
        "risk_reward_geometry":   4.0,   # 净 TP1 R 需要充分
    }
}

def check_component_minimums(scores: dict, action: str) -> tuple[bool, str]:
    mins = COMPONENT_MINIMUMS.get(action, {})
    for component, min_score in mins.items():
        if scores.get(component, 0) < min_score:
            return False, f"{component.upper()}_BELOW_MINIMUM_{action}"
    return True, ""
```

---

## 11. 杠杆选择重设计

### 11.1 新杠杆选择矩阵

```
旧逻辑：Score ≥ 90 → 5x（问题：95分 5x 是最大亏损来源）

新逻辑（Fib + PA + Score 三重条件）：

  5x 要求（全部满足）：
    total_score >= 90
    fib_location_score >= 13.0    # 在最优回撤区（0.382-0.618）
    pa_structure_score >= 9.0     # 至少 breakdown retest 质量
    cci_momentum_quality >= 7.0   # CCI 在健康动量区（非过度延伸）
    risk_reward_net_tp1_r >= 1.3  # 净 TP1 R 充足
    no_anti_reversal_flags        # 防反转过滤器全部通过
    
  4x 要求（全部满足）：
    total_score >= 85
    fib_location_score >= 6.0     # 不在扩展耗竭区
    pa_structure_score >= 6.0     # 至少有某种结构
    
  3x（默认）：
    满足 DIRECT 阈值，但未满足 4x 或 5x 条件
```

### 11.2 杠杆与 Fib 位置的对应关系

```
Fib 位置               → 允许杠杆上限
─────────────────────────────────────
最优回撤区（0.382-0.618）→ 5x（若其他条件满足）
深度回撤区（0.618-0.786）→ 4x
中性区（无 Fib 信号）   → 4x
1.272 扩展区            → 3x（扩张目标附近风险高）
1.618+ 扩展区           → 0x（硬门控，不开仓）
```

---

## 12. 消融实验设计（A→E）

### 12.1 五组实验规格

```
实验 A（基准）：当前 EMA+CVD 权重架构，不变
  目的：建立对比基准
  Run ID: fib_pa_refactor_exp_a_baseline

实验 B：EMA+CVD+CCI（移除 MACD/BOLL，不加 PA/Fib）
  权重：EMA 38, CVD 28, CCI 22, RR 12
  目的：量化仅添加 CCI 的边际贡献
  Run ID: fib_pa_refactor_exp_b_ema_cvd_cci

实验 C：EMA+CVD+CCI+价格行为结构
  权重：EMA 25, CVD 20, CCI 16, PA 30, RR 9
  目的：量化 PA 结构的边际贡献
  Run ID: fib_pa_refactor_exp_c_add_pa

实验 D：EMA+CVD+CCI+PA+Fibonacci（完整新架构）
  权重：EMA 20, CVD 18, CCI 14, PA 22, FIB 18, RR 8
  5x 无额外约束
  Run ID: fib_pa_refactor_exp_d_full

实验 E：实验 D + 5x 杠杆 Fib/PA 强制约束
  同实验 D，但 5x 需要 Fib >= 13 且 PA >= 9
  Run ID: fib_pa_refactor_exp_e_5x_constrained
```

### 12.2 必须记录的评估指标

```
基础指标（全部实验都需要）：
  win_rate / profit_factor / realized_pnl / max_drawdown / trade_count

新增指标（本次重构的核心评估）：
  initial_stop_rate        初始止损率（全额亏损 / 总封闭）
  breakeven_stop_rate      保本止损率（TP1 后止损 / 总封闭）
  tp3_rate                 到达 TP3 的比例
  avg_initial_stop_pnl     每笔初始止损的平均亏损
  avg_tp_path_pnl          每笔 TP 路径的平均盈利
  5x_pnl_contribution      5x 杠杆交易的净 PnL
  score_90plus_win_rate    90+ 分区间的胜率（目标：> 60%）
  fib_optimal_win_rate     Fib 最优位置的胜率
  pa_structure_win_rate    有 PA 结构 vs 无 PA 结构的胜率差

验收标准（部署前必须满足）：
  score_90plus_win_rate  > 60%（当前 50%，不可接受）
  5x_pnl_contribution    > 0（当前 5x 是亏损来源）
  profit_factor          > 1.2（最低可行）
  initial_stop_rate      < 40%（当前约 57%）
```

---

## 13. 配置规格与参数边界

### 13.1 新架构配置文件

```json
{
  "version": "fib_pa_v1",
  "description": "CCI+CVD+EMA+PA+Fibonacci 完整新架构",

  "score_weights": {
    "trend_ema_context":       20,
    "flow_cvd_confirmation":   18,
    "cci_momentum_quality":    14,
    "price_action_structure":  22,
    "fibonacci_location":      18,
    "risk_reward_geometry":     8
  },

  "thresholds": {
    "direct_short":  82,
    "direct_long":   92,
    "watch":         62
  },

  "ema_config": {
    "ema200_mode":          "score",
    "ema200_legality_pts":    8,
    "ema50_quality_pts":      7,
    "ema_momentum_pts":       5,
    "slope_steep_threshold":  0.003,
    "slope_mild_threshold":   0.001
  },

  "fib_config": {
    "swing_fractal_k":           2,
    "swing_min_atr_mult":        1.2,
    "swing_lookback_15m":       50,
    "swing_lookback_1h":        30,
    "extension_exhaustion_mult": 1.618,
    "optimal_pullback_min":      0.382,
    "optimal_pullback_max":      0.618,
    "level_tolerance_atr_mult":  0.5
  },

  "pa_config": {
    "fractal_k":             2,
    "min_body_atr_mult":     0.3,
    "wick_body_ratio_block": 1.5,
    "continuation_lookback": 6
  },

  "cci_config": {
    "period":                   20,
    "healthy_short_min":      -150,
    "healthy_short_max":       -80,
    "exhaustion_threshold":   -150,
    "failed_continuation_bars":  3
  },

  "leverage_config": {
    "base":   3,
    "mid":    4,
    "high":   5,
    "5x_fib_min":        13.0,
    "5x_pa_min":          9.0,
    "5x_cci_min":         7.0,
    "5x_rr_net_r_min":    1.3,
    "5x_score_min":      90.0
  },

  "component_minimums": {
    "DIRECT": {
      "price_action_structure":  6.0,
      "fibonacci_location":      6.0,
      "risk_reward_geometry":    2.0
    },
    "DIRECT_5X": {
      "price_action_structure":  9.0,
      "fibonacci_location":     13.0,
      "risk_reward_geometry":    4.0
    }
  },

  "disable_probe":           true,
  "blacklist_symbols":       ["XRPUSDT", "ZECUSDT"],
  "observation_only_symbols":["XLMUSDT", "TONUSDT"],
  "long_threshold_offset":   10.0,
  "short_threshold_offset":   0.0
}
```

---

## 14. 实施计划与测试覆盖

### 14.1 文件变更清单

```
新建文件：
  src/signals/pa_structure.py         # PA 结构检测
  src/signals/fib_location.py         # Fibonacci 层位计算与评分
  src/signals/cci_quality.py          # CCI 动量质量评分
  tests/test_pa_structure.py          # PA 组件单元测试
  tests/test_fib_location.py          # Fib 组件单元测试
  tests/test_cci_quality.py           # CCI 组件单元测试
  configs/entry_chain.dry_run_fib_pa_v1.json  # 新配置文件

修改文件：
  src/signals/entry_chain.py          # 集成新组件 + 门控顺序调整
  src/signals/entry_chain_config.py   # 新增 fib_config, pa_config, cci_config
  src/signals/entry_chain_gates.py    # 新增 FIB_EXTENSION_EXHAUSTION 门控
  src/signals/ema_scorer.py           # 权重调整（20分 = 重新分配）
  src/signals/cvd_scorer.py           # 添加 CVD 背离检测

不变文件：
  src/api/binance_client.py           # ⛔ 零改动
```

### 14.2 必须覆盖的测试用例

```python
# tests/test_fib_location.py

def test_extension_exhaustion_returns_zero_and_block():
    """价格在 1.618 扩展区 → 评分 0，标签 BLOCK"""

def test_optimal_pullback_returns_max_score():
    """价格在 0.382-0.618 回撤区 → 评分 18"""

def test_neutral_location_returns_mid_score():
    """无 Fib 信息 → 评分约 9（中性）"""

def test_1h_fib_overrides_15m_fib_for_block():
    """1h Fib 耗竭 → 即使 15m 位置好也 BLOCK"""

# tests/test_pa_structure.py

def test_lower_high_retest_scores_max():
    """低高位重测失败 → PA 分接近满分"""

def test_large_move_no_structure_scores_zero():
    """大跌后无结构直接追空 → PA 分为 0"""

def test_reversal_wick_applies_negative():
    """大上影线 → 入场K线质量 -4 分"""

def test_breakdown_retest_scores_high():
    """突破后回踩确认 → PA 分 9"""

# tests/test_cci_quality.py

def test_cci_exhaustion_below_150_penalized():
    """CCI < -150 的空头信号得分低于 CCI 在 -100 至 -150"""

def test_cci_secondary_weakness_scores_max():
    """CCI 回升后二次走弱 → 10 分（最优）"""

def test_cci_failed_continuation_deducts():
    """CCI 从极端区回升后未再突破 → 扣 4 分"""

# 集成测试
def test_bnb_short_after_sharp_move_blocked():
    """
    模拟 BNB 2026-06-25 22:15 场景：
    价格大跌 → CCI < -180（过度延伸）+ Fib 接近 1.272 扩展区
    → 总分应低于 DIRECT 阈值（即使 EMA/CVD 完美对齐）
    """

def test_link_minus_361_pct_candle_blocked_by_pa():
    """
    模拟 LINK -3.61% 大阴线后追空场景：
    PA 结构得分 = 0（无有效结构，仅追大阴线）
    → PA 组件最低分要求 6 未达到 → 降为 WATCH
    """
```

---

## 15. 禁止事项与路线图

### 15.1 禁止事项（本重构期间不做）

```
❌ 不要在 Fib/PA 组件单元测试完成前接入 dry-run
❌ 不要在消融实验 B/C/D 完成前跳过到 E（每层必须单独验证）
❌ 不要在 score_90plus_win_rate > 60% 之前重新启用 5x 无约束
❌ 不要在实装过程中同时修改 TP/SL 设置（单变量原则）
❌ 不要在 observe_only 期间对 XLM/TON 的信号质量下结论
❌ src/api/binance_client.py 零改动（任何时候）
```

### 15.2 实施路线图

```
┌──────────────────────────────────────────────────────────────┐
│ Phase 1（第 1-3 天）：组件实现与单元测试                      │
│  → 实现 fib_location.py（含摆动检测 + 层位计算 + 评分）      │
│  → 实现 pa_structure.py（含结构识别 + K线质量 + 趋势一致）   │
│  → 实现 cci_quality.py（含状态分类 + 失败延续检测）          │
│  → 单元测试：全部组件的核心场景 + 边界条件                   │
│  → 验收：所有测试通过，compile 无错误                        │
├──────────────────────────────────────────────────────────────┤
│ Phase 2（第 4-5 天）：消融回测（离线）                        │
│  → 运行实验 A/B/C/D/E                                        │
│  → 重点验证：score_90plus_win_rate / 5x_pnl / PA有无的胜率差 │
│  → 验收：实验 D 或 E 的 profit_factor > 1.2                 │
├──────────────────────────────────────────────────────────────┤
│ Phase 3（第 6-7 天）：dry-run 集成                            │
│  → 将最优实验配置接入 dry-run                                 │
│  → 观察 7 天（≥ 30 笔封闭交易）                              │
│  → 验收：profit_factor > 1.0，initial_stop_rate < 40%       │
├──────────────────────────────────────────────────────────────┤
│ Phase 4（14天后）：评估与决策                                 │
│  → 基于 Phase 3 数据重新评估 5x 约束是否可放宽               │
│  → 评估 XLM/TON 是否从 observation_only 恢复                │
│  → 如 KPI 满足，进入小额实盘讨论                              │
└──────────────────────────────────────────────────────────────┘
```

### 15.3 成功的单一指标

```
本次重构的成功判据只有一个：

  90+ 分信号的胜率从当前的 50% 提升至 > 60%

这意味着高分信号再次具有预测意义——价格行为结构和 Fibonacci 位置
让"高分"真正等同于"高概率"，而不仅仅是"高度同意当前趋势"。

达到此目标后，动态杠杆系统才有意义：
因为只有当分数是真实的边际质量信号时，
5x 杠杆给高分信号才能创造价值。
```

---

*报告结束 | Fib + PA 策略重构建议 v1.0 — 2026-06-26*
*下一步：Phase 1 组件实现。建议从 fib_location.py 的 swing 检测入手，先跑单元测试确认摆动算法在 15m 数据上的噪音率，再接入评分层。*
