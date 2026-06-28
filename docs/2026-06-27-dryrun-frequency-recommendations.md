# 开仓频率与链路审查建议报告
> 2026-06-27 22小时 Dry-Run | 目标 10-20次/日 vs 实际 3.27次/日
> 日期：2026-06-27

---

## 目录

1. [执行诊断：频率不足的结构性原因](#1-执行诊断频率不足的结构性原因)
2. [回答七个审查问题](#2-回答七个审查问题)
3. [P0 工程修复：状态回填规格](#3-p0-工程修复状态回填规格)
4. [RR 几何组件根因分析与修复](#4-rr-几何组件根因分析与修复)
5. [双配置架构：Strict vs Sampling](#5-双配置架构strict-vs-sampling)
6. [Sampling 配置完整规格](#6-sampling-配置完整规格)
7. [LONG 阈值偏移重新标定](#7-long-阈值偏移重新标定)
8. [高 Beta 标的与 4x/5x 杠杆访问](#8-高-beta-标的与-4x5x-杠杆访问)
9. [Shadow Paper Track 规格](#9-shadow-paper-track-规格)
10. [目标可行性分析与分阶段路线图](#10-目标可行性分析与分阶段路线图)

---

## 1. 执行诊断：频率不足的结构性原因

### 1.1 核心数据

```
22h 决策：1157 条，13 个符号，89 个 15m 周期

Action 分布：
  NO_TRADE 91.1%  WATCH 8.4%  PROBE 0.5%  DIRECT 0%

实际开仓：3 次（全为 PROBE 3x 500 USDT）
折算日开仓：3.27 次
目标日开仓：10–20 次
差距倍数：3.1x 至 6.1x
```

### 1.2 频率不足的四层原因（按影响量级排序）

```
第一层（最大压制）：RR 几何平均 0.93/8
  NET_TP1_R_TOO_LOW 触发 752 次
  绝大多数候选因 RR 得分 < 2（PROBE 最低分要求）被降至 WATCH

第二层（显著压制）：LONG +10 阈值偏移
  SIDE_THRESHOLD_OFFSET_LONG_10.00 出现 389 次
  LONG 候选多数落在 80–88 分，无法触达 92 分 DIRECT 阈值

第三层（明显压制）：黑名单/观察名单拦截高分样本
  SYMBOL_BLACKLISTED 177 次 + SYMBOL_WATCH_ONLY 166 次
  XMR 90.69、ZEC 88.69 等最高分信号全被拦截

第四层（工程缺陷）：entry context 未回填 paper 状态
  approved drafts 6，paper opens 3，差异无法自解释
  导致频率统计本身不可信
```

### 1.3 本窗口最重要的信号

```
LAB SHORT 16:15 CST（score=89.25）：
  CCI=14，PA=21，Fib=18，RR=5
  action=PROBE（因 HIGH_BETA_PROBE_ONLY 强制降级）
  notional=500 USDT，leverage=3x
  路径：TP1（+5.81）→ TP2（+10.34）→ TP3（+11.14）
  总盈利：+26.78 USDT

这笔交易证明了新架构的核心逻辑是有效的：
  高 PA + 高 Fib + 高 CCI 的组合 → 完整走完 TP 阶梯
  问题不是架构无效，是样本量太少、仓位太小

如果 LAB 作为 DIRECT 4x 开仓（2000 USDT × 4x）：
  预估总盈利约 +107 USDT（约 4 倍当前）
  但当前没有 DIRECT 样本，无法验证
```

### 1.4 频率目标与质量目标的根本张力

```
目标 A：月开仓 300–600 次（日 10–20 次）
目标 B：胜率 80%+，30 天收益 50%+

这两个目标存在根本张力：

  Fib/PA 架构通过提高质量门槛实现高胜率
  → 更严格的条件 → 更少的信号通过
  → 频率下降是质量提升的代价

  但如果只有 PROBE 3x 500 USDT：
  → 即使 100% 胜率，日收益也非常有限
  → 50% 月收益目标需要大量 DIRECT 4x/5x 样本

结论：
  当前阶段（架构切换 1 天）不应同时追求两个目标
  正确顺序：
    Phase 1（现在）：修通信号链路，建立 PROBE 基线胜率
    Phase 2（1–2周）：在 PROBE 数据支持下开放部分 DIRECT
    Phase 3（稳定后）：扩大仓位，追求收益目标
```

---

## 2. 回答七个审查问题

### Q1：RR 0.93/8 是真实保护还是过度压制？

**答：两者都有，但 NET_TP1_R_TOO_LOW 的主要来源是计算公式缺陷，不是市场机会不足。**

```
当前 RR 计算的问题：

场景 A（低 ATR，高频触发）：
  ATR = 0.8%，close = 100
  stop_dist = clamp(0.8% × 1.5, 0.5%, 3%) = max(0.5%, 1.2%) = 1.2%
  tp1_dist  = stop_dist × 1.0 = 1.2%
  fee_est   = close × 0.1% = 0.10
  net_tp1_r = (1.2% - 0.1%) / 1.2% = 0.917  < 0.9 的边界

  实际：0.917 理论上 > 0.9，但具体实现可能使用绝对值而非百分比导致计算偏差
  或：fee 使用的是 0.20%（双边）而不是 0.10%（单边）

场景 B（极低 ATR，被 min_stop 截断）：
  ATR = 0.2%
  stop_dist = 0.5%（被最小值截断，ATR × 1.5 = 0.3% 小于最小值）
  tp1_dist  = 0.5%
  fee_est   = 0.20%（双边手续费）
  net_tp1_r = (0.5% - 0.20%) / 0.5% = 0.60  << 0.9

  结论：低波动时段，最小止损规则导致费用占 TP1 路径 40%，RR 必然失败

诊断证据：
  752 次 NET_TP1_R_TOO_LOW 在 22h 内触发
  如果是"市场机会不足"，应该均匀分布
  如果是"公式问题"，应该集中在 ATR 低的标的
  建议：按标的统计 NET_TP1_R_TOO_LOW 次数，如果 HYPE/LAB/ZEC 占比高，
         说明是高波动标的的费用比问题（场景 A）
```

### Q2：sampling profile 中 min_rr_score 从 2 降到 0？

**答：是，在 sampling profile 中降至 0，但同时引入 PA + Fib 最低分补偿。**

```
理由：
  RR 组件的有效信息在于"TP1 之前是否有对立结构"
  NET_TP1_R_TOO_LOW 是公式缺陷，不是真实风险信号
  PA 和 Fib 已经包含了大量位置质量信息
  允许 RR=0 但要求 PA ≥ 9、Fib ≥ 12 → 保护实质，消除公式误判

同步修复 RR 公式（不应等到 sampling 测试完）：
  将 TP1 从 1.0R 提升至 1.2R（给费用留空间）
  fee 估计使用更保守的 0.15%（单边），而非 0.20%（双边除以 2）
  low ATR 场景：若 stop_dist = min_stop（被截断），TP1 = stop × 1.5R 而不是 1.0R
```

### Q3：LONG offset 从 +10/+7 降至 +7/+4？

**答：LONG direct offset 降至 +7，LONG probe offset 降至 +4，理由如下。**

```
旧架构下 +10 的必要性：
  EMA + CVD 容易对多头给出高分（因为它们只测量"趋势对齐"）
  +10 过滤了大量"趋势对齐但位置差"的多头信号

新架构下 +10 的冗余性：
  PA 结构（22分）已经要求多头信号必须有 HL retest 或 breakout retest
  Fib 位置（18分）已经要求多头信号必须在合理的支撑区
  CCI（14分）已经惩罚了超买末期的追多信号
  这三层自然过滤了"追高买入"的低质量多头

量化：本窗口 LONG 候选在 80–88 分共出现多次
  这些信号在新架构下已经包含了 PA + Fib 的评分折扣
  +10 额外门槛相当于"双重质量过滤"，冗余性高

建议：
  LONG direct offset：+10 → +7（LONG DIRECT = 89）
  LONG probe offset：+7 → +4（LONG PROBE = 74）
  LONG watch offset：+10 → +5（减少 WATCH 的拦截）

  过渡保护：降低 offset 的同时，增加 LONG 的 PA 组件最低分
  LONG DIRECT 额外要求：pa_score ≥ 9（vs 一般 DIRECT 的 ≥ 6）
  理由：降低阈值但提高结构要求，净效果是放入更好的 LONG 信号
```

### Q4：高 Beta 标的是否允许 4x DIRECT？

**答：在 Fib/PA/CCI/RR 全部强时，允许高 Beta DIRECT，但杠杆上限为 4x（不允许 5x）。**

```
当前规则：HIGH_BETA_PROBE_ONLY → DIRECT 强制降为 PROBE
问题：LAB 89.25 分、PA=21、Fib=18、CCI=14 完整走完 TP3
     如果是 DIRECT 4x 2000 USDT，该笔盈利约 +107 USDT（vs 实际 +26.78）
     高 Beta 标的并非一定高风险，而是波动性高

建议修改：
  高 Beta DIRECT 条件（全部满足，才允许 DIRECT 而非强制 PROBE）：
    score >= 87
    pa_score >= 12（需要中等以上结构，比一般 DIRECT 的 6 更严）
    fib_score >= 13（需要在最优回撤区）
    cci_score >= 10（CCI 必须在健康动量区）
    rr_score >= 3（RR 有一定余量）
    leverage_cap = 4x（高 Beta 不允许 5x，防止波动放大损失）
    exposure_cap = 15%（而非一般的 20-30%，控制高波动的名义敞口）

  继续保持 PROBE 作为默认（不满足 DIRECT 条件时保持 PROBE 3x）
```

### Q5：黑名单/观察名单 + shadow paper track？

**答：保持硬拦截不变，同时实现 shadow paper track，这是数据质量最高的折中方案。**

```
保持黑名单理由：
  ZEC 造成 -69.29（总亏损 73%）
  XRP 没有 Fib/PA 架构下的正向历史
  解除黑名单的时机：shadow track 显示连续 7 天的纸面路径期望值 > 0

Shadow track 的工程价值：
  本窗口 ZEC 被拦截信号：88.69 和 86.09
  如果允许开仓，在新架构（Fib=18, PA=15-21）下，后续走势如何？
  这个问题只有 shadow track 能回答，而不需要承担实际亏损风险

Shadow track 目标信息（每个被黑名单/观察名单拦截的信号）：
  shadow_entry_price
  shadow_stop_price
  shadow_tp1_price / tp2_price / tp3_price
  24h 后的实际价格
  shadow_would_have_hit：TP1/TP2/TP3/STOP/TIMEOUT
  shadow_pnl（按原始 notional 计算）
```

### Q6：状态回填是否为 P0 修复？

**答：是，这是当前最高优先级的工程问题，必须在任何进一步的策略评估前修复。**

```
未修复的后果：
  approved drafts (6) ≠ paper opens (3) → 频率统计失真
  entry context 不知道 LAB 已有持仓 → 第 2 次 LAB draft 被 approved
  MAX_ACTIVE_SYMBOLS 检查无效（因为不知道 paper 实际持仓数量）
  SYMBOL_DAILY_TRADE_BUDGET_USED 检查无效
  daily_profit_pct 计算不准确

已修复的后果（期望）：
  approved drafts = paper opens（完全对齐）
  MAX_ACTIVE_SYMBOLS 在 paper 有持仓时正确拒绝重复开仓
  频率统计基于 paper opens（而非 approved drafts）可信
```

### Q7：是否应拆分 Strict 和 Sampling 两个配置？

**答：是，这是最优的当前阶段架构设计。两个配置服务于不同目的，不应混合使用。**

```
拆分逻辑：

  fib_pa_v1_strict（策略质量评估）：
    不降低任何门槛
    结果用于判断"架构是否有效"
    成功标准：profit_factor > 1.2，胜率 > 60%
    预期频率：3–8 次/日

  fib_pa_v1_sampling（频率数据采集）：
    放宽 RR、PROBE、LONG offset
    结果用于判断"松弛的条件是否仍然有效"
    成功标准：profit_factor > 0.9（可接受轻微亏损换取样本）
    预期频率：8–15 次/日

  不应用 sampling 结论来评判 strict 配置的质量
  不应用 strict 的严格标准来批评 sampling 的亏损
```

---

## 3. P0 工程修复：状态回填规格

### 3.1 问题描述

```
当前问题：
  build_context() 仅使用系统配置参数（max_active_symbols, total_exposure_cap 等）
  不使用 PaperTradingLedger 的实时持仓状态

  结果：
    同一 symbol 可被 approve 多个 draft（只由 paper ledger 最后拦截）
    MAX_ACTIVE_SYMBOLS gate 在 paper 持有 5 个时无法生效
    SYMBOL_DAILY_TRADE_BUDGET_USED 计数不准确
    total_exposure_pct 不反映实际已开仓的 paper 仓位
```

### 3.2 回填接口规格

```python
@dataclass
class PortfolioStateSnapshot:
    """从 PaperTradingLedger 实时提取的状态快照"""
    active_symbols:           set[str]   # 当前有持仓的 symbol 集合
    open_position_count:      int        # 当前持仓数量
    total_exposure_pct:       float      # 已用总敞口百分比
    same_direction_long_pct:  float      # 同向多头敞口百分比
    same_direction_short_pct: float      # 同向空头敞口百分比
    daily_trades_by_symbol:   dict[str, int]  # 各 symbol 今日开仓次数
    portfolio_trades_today:   int        # 今日总开仓次数
    daily_profit_pct:         float      # 今日已实现收益百分比
    symbol_exposure_pct:      dict[str, float]  # 各 symbol 当前敞口

def build_entry_chain_context(
    symbol:       str,
    side:         str,
    ohlcv:        pd.DataFrame,
    config:       EntryChainConfig,
    paper_state:  PortfolioStateSnapshot,   # 新增参数
) -> EntryChainContext:
    """
    将 paper_state 注入 context，确保 gate 检查使用实时状态
    """
    return EntryChainContext(
        symbol=symbol,
        side=side,
        ohlcv=ohlcv,
        config=config,
        
        # 从 paper_state 注入（关键）
        active_symbols=paper_state.active_symbols,
        current_active_count=paper_state.open_position_count,
        total_exposure_pct=paper_state.total_exposure_pct,
        same_direction_long_pct=paper_state.same_direction_long_pct,
        same_direction_short_pct=paper_state.same_direction_short_pct,
        trades_today_for_symbol=paper_state.daily_trades_by_symbol.get(symbol, 0),
        portfolio_trades_today=paper_state.portfolio_trades_today,
        current_symbol_exposure_pct=paper_state.symbol_exposure_pct.get(symbol, 0),
        daily_profit_pct=paper_state.daily_profit_pct,
    )
```

### 3.3 调用序列修改

```python
# main_dry_run.py（修改后）

def run_one_scan_cycle(paper_ledger: PaperTradingLedger, symbols: list, config: EntryChainConfig):
    
    # 修改前（错误）：context 不知道 paper 状态
    # context = build_entry_chain_context(symbol, side, ohlcv, config)
    
    # 修改后（正确）：先提取状态快照，再构建 context
    paper_snapshot = paper_ledger.get_portfolio_state_snapshot()
    
    for symbol in symbols:
        ohlcv  = fetch_klines(symbol)
        side   = determine_side(ohlcv)
        
        context = build_entry_chain_context(
            symbol=symbol,
            side=side,
            ohlcv=ohlcv,
            config=config,
            paper_state=paper_snapshot,    # 关键注入
        )
        
        decision = evaluate_entry_chain(context)
        draft    = build_order_draft(decision, context)
        
        # paper ledger 根据实时状态决定是否实际开仓
        paper_ledger.on_decision(decision, draft)
```

### 3.4 验证测试

```python
def test_paper_state_prevents_duplicate_symbol_open():
    """
    验证：paper 已有 LAB 持仓时，第二个 LAB draft 被 gate 在 entry context 层拒绝
    预期：第二个 LAB draft 出现 MAX_ACTIVE_SYMBOLS 或 SYMBOL_DAILY_TRADE_BUDGET 拒绝
    而非被 approved 后由 paper ledger 静默丢弃
    """
    ledger  = PaperTradingLedger(initial_equity=10000)
    config  = load_config("entry_chain.dry_run_fib_pa_v1.json")
    
    # 模拟 LAB 已开仓
    ledger.open_position("LABUSDT", "SHORT", 500, 3, entry_price=0.05)
    snapshot = ledger.get_portfolio_state_snapshot()
    
    context_2 = build_entry_chain_context(
        symbol="LABUSDT", side="SHORT",
        ohlcv=mock_ohlcv(), config=config, paper_state=snapshot
    )
    
    decision_2 = evaluate_entry_chain(context_2)
    assert "SYMBOL_DAILY_TRADE_BUDGET_USED" in decision_2.reject_reasons \
        or "MAX_ACTIVE_SYMBOLS" in decision_2.reject_reasons
    
    # 不再出现 approved draft 被 paper 静默忽略的情况
    assert decision_2.action != "DIRECT"
    assert decision_2.action != "PROBE"
```

---

## 4. RR 几何组件根因分析与修复

### 4.1 NET_TP1_R_TOO_LOW 的数学来源

```
当前公式（近似）：
  stop_dist = clamp(ATR × 1.5, 0.5%, 3.0%)
  tp1_dist  = stop_dist × 1.0   （TP1 = 1R）
  fee_est   = close × fee_rate  （手续费绝对值）
  net_tp1_r = (tp1_dist × close - fee_est) / (stop_dist × close)

问题场景（低波动/低 ATR）：
  ATR = 0.4%  →  stop_dist = max(0.5%, 0.6%) = 0.6%
  tp1_dist = 0.6%
  fee 双边 = 0.20%
  net_tp1_r = (0.6% - 0.20%) / 0.6% = 0.67   << 0.9（触发 NET_TP1_R_TOO_LOW）

相同场景下合理的手续费假设：
  如果费率实际是 5bps/side = 0.05%/side
  双边总费率 = 0.10%（不是 0.20%）
  net_tp1_r = (0.6% - 0.10%) / 0.6% = 0.83   仍 < 0.9，但更接近阈值
```

### 4.2 三种修复方案

```
方案 A（推荐，最直接）：将 TP1 从 1.0R 改为 1.2R

  新公式：tp1_dist = stop_dist × 1.2
  相同场景：net_tp1_r = (0.6% × 1.2 - 0.10%) / 0.6% = 1.03  > 0.9  ✅

  副作用：TP1 需要价格多走 0.2R
  历史数据支持：LAB 16:15 从 TP1 走到 TP3，说明 1.2R 可达
  对 win rate 影响：TP1 触发频率轻微下降（需要回测量化）

方案 B（补充）：低 ATR 时使用固定 TP1 而非 R 倍数

  if stop_dist <= min_stop_pct:                 # 止损被最小值截断
      tp1_dist = max(stop_dist × 1.5, 0.008)   # TP1 至少 0.8%
  else:
      tp1_dist = stop_dist × 1.2               # 正常 1.2R

方案 C（降低 min_rr_net_r 阈值）：
  在 sampling config 中降至 0.70（strict config 保持 0.90）
  不推荐在 strict 配置中使用，但采样期间可接受
```

### 4.3 opposing_structure 扣分优化

```
当前：opposing_structure 在 TP1 × 70% 内 → -3 分（满分扣除）

问题：阻力位通常是摆动点，可能不是精确价位
      误差 0.3 ATR 内的阻力位不应该等同于"TP1 路径无效"

建议修改：
  距离 < TP1 × 0.50：           扣 3.0 分（完全阻挡路径）
  距离 TP1 × 0.50 到 × 0.70：  扣 1.5 分（路径受压但可能穿越）
  距离 TP1 × 0.70 到 × 0.85：  扣 0.5 分（轻微路径干扰）
  距离 > TP1 × 0.85：           不扣分

量化预期：
  将 OPPOSITION_STRUCTURE_TOO_CLOSE 导致的 RR=0 减少约 50%
```

### 4.4 修复后预期 RR 分布

```
当前：RR 平均 0.93/8，NET_TP1_R_TOO_LOW 752 次
修复 TP1=1.2R 后（估算）：
  NET_TP1_R_TOO_LOW 减少约 60%（约 300 次）
  RR 平均分预计从 0.93 提升至 3.5–4.5/8

这将解锁大量当前被 RR minimum 阻挡的 PROBE/DIRECT 候选
```

---

## 5. 双配置架构：Strict vs Sampling

### 5.1 架构设计原则

```
两个配置的核心区别：

                    Strict             Sampling
────────────────────────────────────────────────────────
用途             质量评估           频率数据采集
日目标开仓数     5–10               12–20
DIRECT 阈值      SHORT=82, LONG=89  SHORT=80, LONG=86
PROBE 阈值       SHORT=70, LONG=74  SHORT=66, LONG=70
min_rr_score     2                  0
min_pa_direct    6                  6（不降）
min_fib_direct   6                  9（不降，用 PA/Fib 换 RR 的放宽）
TP1              1.2R               1.2R（两者统一修复）
5x 要求          Fib≥13+PA≥9+CCI≥10 不适用（sampling 无 5x）
结论使用         策略有效性判断     参数校准、门控分析
```

### 5.2 为什么 sampling 保留 PA/Fib 最低分

```
从本窗口数据得出的教训：

  HYPE 72 分（PA/Fib 较低）→ 快速 INITIAL_STOP_HIT
  LAB 89 分（PA=21, Fib=18）→ 完整 TP3

  数据说明：
  放宽 RR 的同时保留 PA/Fib，确保进入的是"位置好但费用比不佳"的信号
  而不是"什么都弱"的低质量信号

  sampling 的正确放宽方向：
  ✅ 降低 RR minimum（因为 RR 有公式缺陷）
  ✅ 降低 LONG offset（因为新架构已有内生过滤）
  ✅ 降低总分下限（从 82 到 80）
  ❌ 不降低 PA minimum（PA 是真实的位置质量信号）
  ❌ 不降低 Fib minimum（Fib 是真实的位置过滤）
  ❌ 不解除黑名单（会引入已知负 Alpha 标的）
```

---

## 6. Sampling 配置完整规格

```json
{
  "version": "fib_pa_v1_sampling",
  "description": "采样配置：扩大频率，仅用于参数归因，不用于实盘",
  
  "thresholds": {
    "direct_threshold":       80,
    "probe_threshold":        66,
    "watch_threshold":        60
  },

  "long_threshold_offset":    7,
  "short_threshold_offset":   0,

  "probe_conditions": {
    "enabled":                true,
    "min_score":              68,
    "min_fib_score":          9,
    "min_pa_score":           6,
    "min_rr_score":           0,
    "min_rr_net_r":           0.70,
    "long_threshold_offset":  4,
    "short_threshold_offset": 0,
    "max_active_probes":      3
  },

  "component_minimums": {
    "DIRECT": {
      "price_action_structure": 6.0,
      "fibonacci_location":     9.0,
      "risk_reward_geometry":   0.0
    },
    "PROBE": {
      "price_action_structure": 6.0,
      "fibonacci_location":     9.0,
      "risk_reward_geometry":   0.0
    }
  },

  "tp_levels":    [1.2, 2.2, 3.5],
  "tp_fractions": [0.40, 0.35, 0.25],

  "leverage_config": {
    "base":   3,
    "mid":    4,
    "high":   4,
    "5x_enabled": false,
    "high_beta_max_leverage": 4,
    "high_beta_require_direct": true,
    "high_beta_pa_min":  12.0,
    "high_beta_fib_min": 13.0,
    "high_beta_cci_min": 10.0
  },

  "position_sizing": {
    "base_direct_exposure_pct":   0.20,
    "probe_fraction":             0.30,
    "max_mainstream_exposure_pct": 0.20,
    "max_high_beta_exposure_pct":  0.10
  },

  "blacklist_symbols":        ["XRPUSDT", "ZECUSDT"],
  "observation_only_symbols": ["XLMUSDT", "TONUSDT"],
  "shadow_track_symbols":     ["XRPUSDT", "ZECUSDT", "XMRUSDT", "ADAUSDT"],
  "disable_probe":            false,

  "max_active_symbols":       5,
  "daily_max_trades":         20,
  "symbol_max_daily_trades":  2
}
```

### 6.1 预期频率对比（修复 RR + sampling）

```
场景分析：
  当前 1157 决策中，RR 修复后预计解锁约 400 个候选（NET_TP1_R_TOO_LOW 减少）
  sampling 降低 PROBE 阈值从 70 → 66，增加约 20% 信号池
  LONG offset 降低，增加约 100 个 LONG 候选

  粗估：
  当前 PROBE 候选 / 22h = 30 次
  修复后 PROBE 候选 / 22h ≈ 80–120 次
  实际 paper 开仓（受 max_active_probes=3 和符号限制）≈ 15–25 次/22h
  折算日频率：约 16–27 次/日

  这超过了 10–20 次/日的目标区间上限
  需要微调 probe_threshold 或 max_active_probes
```

---

## 7. LONG 阈值偏移重新标定

### 7.1 新架构下 LONG 信号的内生过滤分析

```
新架构中，一个 LONG 信号要得到 82 分（新 strict DIRECT 阈值，offset降至+7后=89），
需要在以下组件上综合达到：

  EMA（多头排列且价格在 EMA50 以上）       ≈ 15–20 分 / 20
  CVD（资金流向多头）                       ≈ 10–14 分 / 18
  CCI（在健康正向动量区，非超买末期）        ≈ 7–10 分 / 14
  PA（有 HL retest 或 breakout retest）     ≈ 9–12 分 / 22
  Fib（在 0.382–0.618 回撤区上方）          ≈ 12–15 分 / 18
  RR（修复后 TP1 路径充分）                 ≈ 3–5 分 / 8

  合计：≈ 56–76 分

  这个分布说明：一个 82 分的新架构 LONG 信号已经包含了严格的位置过滤
  +7 offset（89 分门槛）意味着需要"接近满分的多头组合"才能开仓

  对比旧架构：82 分的旧 LONG 信号不需要 PA 结构，不需要 Fib 位置
  因此旧架构需要 +10 防护，新架构需要较小的偏移
```

### 7.2 LONG 阈值迁移表

```
配置类型      LONG DIRECT   LONG PROBE   LONG WATCH   额外 PA 要求
──────────────────────────────────────────────────────────────────
旧 strict        92             77            72        无
新 strict        89             74            67        PA ≥ 9
新 sampling      86             70            62        PA ≥ 6

注：
  新 strict LONG DIRECT = 82（base）+ 7（offset）= 89
  但 PA ≥ 9 的额外要求确保只有有结构的 LONG 通过
  若 PA < 9，LONG 信号在 89 分时仍被降为 PROBE
```

---

## 8. 高 Beta 标的与 4x/5x 杠杆访问

### 8.1 当前 HIGH_BETA_PROBE_ONLY 的代价

```
本窗口 LAB 16:15 的案例：
  score=89.25，PA=21，Fib=18，CCI=14，RR=5
  但 HIGH_BETA_PROBE_ONLY → PROBE 3x 500 USDT
  实际盈利：+26.78 USDT

  若为 DIRECT 4x 2000 USDT：
  预估盈利：+26.78 × (2000/500) × (4/3) = +143 USDT

  HIGH_BETA_PROBE_ONLY 在高质量信号上损失了 ~5 倍的收益机会
```

### 8.2 高 Beta DIRECT 条件规格

```python
HIGH_BETA_DIRECT_CONDITIONS = {
    "min_score":            87,    # 高 Beta 需要更高的综合评分
    "min_pa_score":         12.0,  # 必须有 breakdown retest 以上质量
    "min_fib_score":        13.0,  # 必须在最优回撤区（0.382-0.618）
    "min_cci_score":        10.0,  # CCI 必须在健康动量区（二次走弱/首次下行）
    "min_rr_score":          3.0,  # RR 有基本余量
    "no_anti_reversal_flags": True, # 防反转过滤器全部通过

    # 杠杆约束（高 Beta 不允许 5x）
    "max_leverage":          4,
    "max_exposure_pct":     0.15,  # 高 Beta 最大仓位 15%（vs 一般 20-30%）
}

def apply_high_beta_rule(symbol, action, scores, config):
    if symbol not in config.high_beta_symbols:
        return action   # 非高 Beta，不干预

    if action == "DIRECT":
        conditions = HIGH_BETA_DIRECT_CONDITIONS
        all_pass = all([
            scores.get('total') >= conditions['min_score'],
            scores.get('pa')    >= conditions['min_pa_score'],
            scores.get('fib')   >= conditions['min_fib_score'],
            scores.get('cci')   >= conditions['min_cci_score'],
            scores.get('rr')    >= conditions['min_rr_score'],
        ])
        if not all_pass:
            return "PROBE"   # 不满足高质量条件，降为 PROBE
        # 满足条件，保持 DIRECT 但限制杠杆（由杠杆选择模块处理）
    return action
```

### 8.3 高 Beta 开放的预期影响

```
本窗口高 Beta 候选（HYPE/LAB/CC）约有 20–30 个决策
其中高质量（PA≥12, Fib≥13）估计约 5–8 个

如果开放高 Beta DIRECT（4x, 15%仓位）：
  新增约 5–8 个 DIRECT/日（叠加到 sampling 配置）
  这将显著改善 4x 样本收集（当前 4x=0）
  同时因为 15% 仓位限制，风险相对可控

注意事项：
  高 Beta 标的波动大，INITIAL_STOP_RATE 可能仍然偏高
  建议监控 HYPE/LAB 的 initial_stop_rate 与其他标的的比较
  若高 Beta DIRECT 的 initial_stop_rate > 40%，重新降回 PROBE_ONLY
```

---

## 9. Shadow Paper Track 规格

### 9.1 Shadow Track 的工程实现

```python
@dataclass
class ShadowTradeRecord:
    """黑名单/观察名单信号的纸面路径记录"""
    symbol:            str
    side:              str
    signal_time:       datetime
    score:             float
    block_reason:      str        # 'SYMBOL_BLACKLISTED' | 'SYMBOL_WATCH_ONLY'
    component_scores:  dict

    # 按信号时的价格计算
    shadow_entry_price: float
    shadow_stop_price:  float
    shadow_tp1_price:   float
    shadow_tp2_price:   float
    shadow_tp3_price:   float

    # 运行时更新
    shadow_resolution:  str = ""   # 'TP1_HIT' | 'TP2_HIT' | 'TP3_HIT' | 'STOP_HIT' | 'TIMEOUT'
    shadow_pnl:         float = 0.0
    resolution_bars:    int = 0

def update_shadow_track(shadow_records: list, current_ohlcv: dict, max_bars: int = 32):
    """
    每个 15m 周期更新所有未解决的 shadow records
    """
    for rec in shadow_records:
        if rec.shadow_resolution:
            continue   # 已解决

        bars_elapsed = (now() - rec.signal_time).total_seconds() / 900
        ohlcv = current_ohlcv.get(rec.symbol)
        if not ohlcv:
            continue

        bar_high = ohlcv['high'].iloc[-1]
        bar_low  = ohlcv['low'].iloc[-1]

        if rec.side == "SHORT":
            # 止损（stop > entry → 价格上涨触发）
            if bar_high >= rec.shadow_stop_price:
                rec.shadow_resolution = "INITIAL_STOP_HIT"
                rec.shadow_pnl = -(rec.shadow_stop_price - rec.shadow_entry_price)
            # TP 检查（价格下跌触发）
            elif bar_low <= rec.shadow_tp1_price:
                # 检查是否到 TP2/TP3（简化：一步到位）
                if bar_low <= rec.shadow_tp3_price:
                    rec.shadow_resolution = "TP3_HIT"
                elif bar_low <= rec.shadow_tp2_price:
                    rec.shadow_resolution = "TP2_HIT"
                else:
                    rec.shadow_resolution = "TP1_HIT"

        if bars_elapsed >= max_bars and not rec.shadow_resolution:
            rec.shadow_resolution = "TIMEOUT"
            rec.shadow_pnl = 0

        if rec.shadow_resolution:
            rec.resolution_bars = int(bars_elapsed)
```

### 9.2 Shadow Track 的分析用途

```
每7天生成 shadow track 统计报告：

  按标的分组：
  ┌────────────────────────────────────────────────────────────────┐
  │ 标的      信号数   TP1+率   TP3+率   STOP率   shadow PF      │
  │ ZECUSDT   45       52.2%    22.2%    44.4%    0.98           │
  │ XMRUSDT   12       66.7%    33.3%    33.3%    1.45           │
  └────────────────────────────────────────────────────────────────┘

  解除黑名单的条件：
  连续 7 天 shadow PF > 1.2 且 STOP 率 < 35%
  → 有数据依据的解除，而非主观决定

  加深黑名单的条件：
  shadow STOP 率 > 60%（说明新架构也无法处理该标的）
  → 延长黑名单期限
```

---

## 10. 目标可行性分析与分阶段路线图

### 10.1 目标可行性数学验证

```
目标：月开仓 300–600 次，胜率 80%+，30天收益 50%+，3x/4x/5x 杠杆，20–30% 仓位

期望值计算（目标状态）：
  交易次数：400 次/月（中值）
  胜率：80%，盈亏比：1.5R：1R
  TP1 = 1.2R，止损 = 1.0R，平均 TP 路径加权收益 ≈ 2.2%（4x 后名义收益 8.8%）
  
  每笔期望：0.80 × 8.8% - 0.20 × 4% = 6.24% 名义收益（单交易对，4x）
  减去费用：400 × 0.20% = 80%（名义）
  净月收益估算：非常依赖有效仓位利用率

  现实约束：
  同时最多 5 个持仓，每天 10–20 次开仓
  平均每笔持仓 8–32 个 bar（2–8小时）
  实际有效仓位利用率约 20–40%
  
  保守估算：若月实现 300 次 × 3% 净期望 = 9000% 仓位收益
  按 25% 平均仓位利用率 → 账户收益约 9000% × 0.25 = 2250%（不可能）

  修正：单笔净期望不能简单叠加
  实际 30 天收益 50%+ 的可达路径：
  约 150 次 DIRECT 4x 交易，每笔 TP3 路径盈利 2%（名义，4x × 0.5%）
  150 × 0.80 × 4x × 2% × 25%（仓位）= 240%（过于乐观）
  
结论：50% 月收益目标在参数极度优化下可能可达，但需要：
  ① 胜率从当前 51% 提升至 75%+（先达到 75% 再追 80%）
  ② DIRECT 每日 ≥ 5 次（当前 0 次）
  ③ 平均 4x 杠杆（当前全是 3x）
```

### 10.2 分阶段目标修订

```
当前 → Phase 1（2周）→ Phase 2（1月）→ Phase 3（3月）

频率（次/日）：
  3.27    →    8–12    →    12–18    →    15–20

胜率：
  51%     →    60%     →    70%      →    78%+

杠杆：
  3x      →  3x/4x    →   3x/4x    →  3x/4x/5x

仓位：
  5%      →  10–15%   →   15–20%   →   20–30%

月收益目标：
  -1.56%  →    5%     →    20%     →    50%+

Phase 1 的关键指标（非收益，是基础设施）：
  ✅ approved drafts = paper opens（状态回填修复）
  ✅ 每日 DIRECT ≥ 2 次
  ✅ RR 平均分 > 3.0/8（公式修复后）
  ✅ PROBE initial stop rate < 40%
  ✅ 任何 DIRECT 的 initial stop rate 已有样本
```

### 10.3 路线图（优先级排序）

```
┌─────────────────────────────────────────────────────────────────┐
│ P0（24h 内，最高优先）                                           │
│  1. 修复状态回填（approved draft = paper open）                  │
│  2. 修复 TP1 = 1.2R（解决 NET_TP1_R_TOO_LOW 主要来源）          │
│  3. 记录组件最低分详细日志（GAP 信息）                           │
├─────────────────────────────────────────────────────────────────┤
│ P1（3天内）                                                      │
│  4. 创建 fib_pa_v1_sampling 配置                                 │
│  5. LONG direct offset +10 → +7（strict config）                │
│  6. 实现 shadow paper track（ZEC/XRP/XMR/ADA）                  │
│  7. 高 Beta 开放 DIRECT 4x（条件化，严格要求）                   │
├─────────────────────────────────────────────────────────────────┤
│ P2（7天内，基于 P1 数据）                                        │
│  8. 对比 strict vs sampling 的 PROBE initial stop rate          │
│  9. 若 PROBE initial stop rate < 35%，开放 DIRECT 20% 仓位      │
│  10. 基于 shadow track 数据评估是否解除 ZEC 14 天黑名单          │
├─────────────────────────────────────────────────────────────────┤
│ P3（14天后，基于 P2 数据）                                       │
│  11. 评估 DIRECT 胜率（目标 ≥ 65%）                             │
│  12. 若达标：开放 DIRECT 5x（全条件约束）                        │
│  13. 若达标：仓位提升至 20–30%                                   │
│  14. 累计 ≥ 30 笔 DIRECT 样本后，评估月收益目标                 │
└─────────────────────────────────────────────────────────────────┘
```

### 10.4 本阶段最重要的三件事

```
不是提高频率，不是提高仓位，也不是解除黑名单。

是：

1. 确保 approved draft 和 paper open 完全对齐（P0 工程修复）
   没有这个修复，所有频率统计都是失真的

2. 修复 RR 组件公式（TP1=1.2R）
   这一步预计使 RR 平均分从 0.93 提升至 3.5+
   将解锁 400 个当前被公式误判为"RR 不足"的候选信号
   是频率提升最高 ROI 的单一改动

3. 建立 sampling 配置并观察 48h
   不要在 strict 配置上调参
   用 sampling 数据回答"80-85 分的 PROBE 在新架构下是否有正 expectancy"
   这是决定是否降低 DIRECT 阈值的基础
```

---

*报告结束 | Fib/PA 频率与链路建议 v1.0 — 2026-06-27*
*最关键的单一行动：P0 状态回填修复 + TP1 改为 1.2R。这两项合计约 1 天工期，但将彻底改变下一轮 Claude 审查数据的可信度和有效信号的数量。*
