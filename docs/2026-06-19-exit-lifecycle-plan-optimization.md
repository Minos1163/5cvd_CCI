# 出场生命周期实现计划优化建议
> Exit Lifecycle + Probe + Symbol + Side Hardening Plan Review
> 日期：2026-06-19 | 基于实施计划 v1 的审查意见

---

## 目录

1. [计划总体评估](#1-计划总体评估)
2. [Critical：费用模型必须修正](#2-critical费用模型必须修正)
3. [高优先级：ATR/TP 设计缺陷](#3-高优先级atptp-设计缺陷)
4. [高优先级：交易次数崩溃风险](#4-高优先级交易次数崩溃风险)
5. [中优先级：Probe 禁用逻辑边界](#5-中优先级probe-禁用逻辑边界)
6. [中优先级：测试覆盖盲区](#6-中优先级测试覆盖盲区)
7. [低优先级：CLI 参数验证缺失](#7-低优先级cli-参数验证缺失)
8. [ATR/TP 生命周期推荐规格（修订版）](#8-atptp-生命周期推荐规格修订版)
9. [报告与验证补充要求](#9-报告与验证补充要求)
10. [实施顺序重排建议](#10-实施顺序重排建议)

---

## 1. 计划总体评估

### 1.1 计划核心逻辑的正确性

原始计划的架构方向完全正确：

```
✅ 合成出场 → ATR/TP 生命周期：解决费用结构性问题的唯一路径
✅ Probe 禁用 + XRPUSDT 黑名单：快速消除已量化的主要亏损来源
✅ 多头阈值 +10 偏移：回应测试数据中多头 vs 空头 18pp 胜率差距
✅ 保持 binance_client.py 零改动：执行层隔离原则执行正确
✅ 保守同柱处理（止损优先于 TP）：研究保守主义正确
✅ 默认行为不变（synthetic exit）：向后兼容设计正确
```

### 1.2 发现的问题分级

```
级别          数量    是否可能影响结论
─────────────────────────────────────────
CRITICAL       1      是（费用计算错误将使结论失效）
HIGH           3      是（设计缺陷导致数据失真）
MEDIUM         3      是（测试覆盖不足、逻辑边界）
LOW            2      否（CLI 验证、文档）
─────────────────────────────────────────
合计           9
```

---

## 2. Critical：费用模型必须修正

### 2.1 问题描述

计划中 ATR/TP 出场允许最多 **3 次分批平仓**（TP1 平 30%、TP2 平 40%、TP3 平 30%）。但现有费用模型按"单次出场 5bps"计算，将导致实验结果系统性高估净回报。

```
当前模型（错误）：
  每笔交易费用 = 进场 5bps + 出场 5bps = 10bps round trip
  
分批出场实际费用（正确）：
  进场 1 次  = 5bps
  TP1 出场   = 5bps（30% 仓位平仓）
  TP2 出场   = 5bps（40% 仓位平仓）
  TP3/止损出场= 5bps（30% 仓位平仓）
  总费用 = 4 × 5bps × nominal = 20bps round trip
  
错误量化：
  如果实验 C 116 笔使用 ATR/TP 出场
  每笔费用从 0.20% 增加到 0.40%（费用翻倍）
  按当前 nominal 计算，额外费用 = 121.90 USDT（实验 C 原费用 × 1倍）
  这将完全抵消 ATR/TP 带来的毛利润改善
```

### 2.2 修正方案

```python
# lifecycle_exit.py 内的费用计算（必须逐批次计入）

@dataclass(frozen=True)
class PartialExit:
    bar_index:     int
    exit_price:    float
    fraction:      float    # 本次平仓比例（相对初始仓位）
    reason:        str      # "TP1" | "TP2" | "TP3" | "STOP" | "TIMEOUT"

@dataclass(frozen=True)
class AtrTpExitResult:
    partial_exits:      tuple[PartialExit, ...]
    average_exit_price: float     # 加权均价（用于整体 PnL 计算）
    total_fee_pct:      float     # 已含所有批次费用（必须传出）
    reason_exit:        str       # 主要出场原因（最后一笔）
    events:             tuple[str, ...]

def compute_lifecycle_fees(
    entry_fee_pct:  float,    # 进场费用（例如 0.0005）
    partial_exits:  list[PartialExit],
    fee_per_side:   float     # 每次出场的费用率（例如 0.0005）
) -> float:
    """返回总费用（进场 + 所有批次出场）"""
    exit_fees = sum(pe.fraction * fee_per_side for pe in partial_exits)
    return entry_fee_pct + exit_fees
```

### 2.3 BacktestTrade 结构更新要求

```python
# 现有 BacktestTrade 存储单一出场价格，需扩展
# 建议：在 risk_constraints.exit_model == "atr_tp" 时，
# 额外存储 lifecycle 元数据，不改变原有字段语义

@dataclass
class BacktestTrade:
    # 原有字段保持不变
    entry_price:  float
    exit_price:   float    # 仍为加权均价（向后兼容）
    pnl:          float
    
    # 新增：lifecycle 附加元数据（仅 atr_tp 模式填充）
    exit_reason:      str = "one_bar_exit"
    partial_exits:    tuple = ()          # PartialExit 序列
    total_fees_pct:   float = 0.0         # 实际总费用（包含所有批次）
    tp1_reached:      bool = False
    breakeven_active: bool = False
    hold_bars:        int = 0
```

---

## 3. 高优先级：ATR/TP 设计缺陷

### 3.1 保本调整（Breakeven）缺少费用缓冲

**问题：** 计划将止损移至"入场价"（breakeven），但入场价不含已付手续费。实际上，保本价格应为：

```
多头保本价 = 入场价 × (1 + 进场费率 + 未来出场费率)
           = entry_price × (1 + 0.0005 + 0.0005)
           = entry_price × 1.001

短头保本价 = entry_price × (1 - 0.001)
```

若不包含此缓冲，"保本"实际上锁定了小额亏损（手续费）。

**修正：**

```python
@dataclass(frozen=True)
class AtrTpExitConfig:
    # 现有字段
    atr_stop_mult:     float = 1.5
    min_stop_pct:      float = 0.005
    max_stop_pct:      float = 0.040
    tp_levels:         tuple[float, float, float] = (1.0, 2.0, 3.0)
    tp_fractions:      tuple[float, float, float] = (0.30, 0.40, 0.30)
    max_hold_bars:     int   = 96
    breakeven_after_tp1: bool = True
    
    # 新增：保本缓冲（防止移到保本后仍亏手续费）
    breakeven_buffer_pct: float = 0.001   # 保本价 = entry ± 0.1%
    
    # 新增：默认 ATR 百分比（信号 payload 缺失时的 fallback）
    default_atr_pct:   float = 0.010      # 1.0% — 必须显式设定，禁止为 None
```

### 3.2 TP 分批比例设计建议调整

**当前计划：** TP1=30%，TP2=40%，TP3=30%

**问题：** 在趋势行情中，TP2 释放比 TP1 更多仓位（40% vs 30%），这意味着到达 TP1 时锁定的利润少于到达 TP2 时。在 TP1 被触发后止损移到保本，但仍有 70% 仓位处于市场风险中，而这 70% 只有在到达 TP2 才能回收更多。这种设计在最终到达止损（保本位）时，净回报接近于 0（仅 TP1 的 30%）。

**建议调整：**

```
方案 A（激进型，适合强趋势）：TP1=40%，TP2=35%，TP3=25%
  优点：TP1 锁定更多利润，保本后剩余 60% 风险更低
  
方案 B（保守型，适合当前回测阶段）：TP1=50%，TP2=30%，TP3=20%
  优点：超过一半仓位在第一档止盈兑现，保本后剩余 50% 风险最低
  
建议：研究阶段使用方案 B（保守），先验证生命周期逻辑正确性
     上线后根据实际数据再切换至方案 A
```

### 3.3 max_hold_bars=96 的合理性

`max_hold_bars=96`（15m × 96 = 24小时）对 altcoin 15m 策略过长：

```
风险：持仓 24 小时意味着会承受多次高波动时段（亚盘/欧盘/美盘三次）
     在合成出场实验中，平均 2 根K线持仓已经足够捕获信号的初始动量
     24 小时持仓更接近于"摆烂仓位"而非"趋势捕获"

建议值：
  强趋势模式：max_hold_bars = 32（8小时）
  默认模式：  max_hold_bars = 16（4小时）
  最大上限：  max_hold_bars = 48（12小时，作为硬上限）
  
调整后命令行默认值：
  --max-hold-bars 16
```

### 3.4 ATR 计算的前瞻性风险

计划中 `atr_pct from signal["atr_pct"] or risk_constraints["default_atr_pct"]`，ATR 必须在**信号产生时计算完成**，不能使用包含当前 K 线的 ATR（否则引入微小前瞻）。

```python
# 正确（仅使用已完成 K 线）
atr_14 = compute_atr(ohlcv.iloc[:-1], period=14)   # 不含当前 bar
atr_pct = atr_14.iloc[-1] / ohlcv['close'].iloc[-1]

# 错误（前瞻）
atr_14 = compute_atr(ohlcv, period=14)              # 含当前未完成 bar
```

要求：`test_lifecycle_exit.py` 中必须新增一个断言验证 ATR 来自信号时间点的已完成 K 线，而非当前 K 线。

---

## 4. 高优先级：交易次数崩溃风险

### 4.1 硬化配置的预估交易次数

```
实验 C EMA Soft 基准：116 笔 / 30D

硬化配置的级联削减：

  移除 XRPUSDT（28笔）：116 - 28 = 88笔
  禁用 Probe（77笔被降级为 WATCH）：88 × (39/116) = 约 30笔
  
  预估：30-35 笔 / 30D
  
  目标：90-120 笔 / 30D
  缺口：约 55-60 笔
```

**这比计划中估计的情况更严峻。** 计划仅在"低于 60 笔时"启动备选方案，但实际可能直接跌至 30 笔。

### 4.2 三级应急方案（计划仅有一级）

```
触发条件          措施                               预估交易次数
─────────────────────────────────────────────────────────────────
< 60 笔          收紧 Probe（阈值 78），不禁用         约 40-55 笔
< 40 笔          Probe 阈值 72，XRPUSDT 降权重（非黑名单）约 55-70 笔
< 30 笔          仅禁用 Probe，保留 XRPUSDT          约 60-80 笔
                 + 多头阈值偏移降至 +5（而非 +10）
─────────────────────────────────────────────────────────────────
```

### 4.3 交易次数与目标的关系重定义

在完整出场生命周期下，**30 笔高质量交易可能优于 120 笔低质量合成出场交易**。建议在本阶段对交易次数目标重新定义：

```
阶段性目标（出场生命周期测试期）：
  最低有效样本：≥ 30 笔（统计置信度可接受）
  研究目标：≥ 50 笔（更好的统计基础）
  原始目标 90-120 次推迟到出场验证完成后的下一个优化周期

决策逻辑：
  if trade_count < 30:
    触发三级应急方案第三档
  elif 30 <= trade_count < 50:
    接受数据，备注样本量局限
  elif trade_count >= 50:
    满足本阶段要求，继续分析
```

---

## 5. 中优先级：Probe 禁用逻辑边界

### 5.1 PROBE → WATCH 降级的副作用

计划中将 `PROBE` 降级为 `WATCH`（而非 `REJECT`）。这在逻辑上正确，但存在以下边界问题：

**问题 1：** WATCH 槽位是否有上限？若 WATCH 槽位无上限，被降级的 Probe 信号可能占满系统的观察队列，影响真正的 WATCH 信号处理效率。

**建议：** 将 PROBE 禁用时的降级改为 `REJECT`，加入拒绝原因 `PROBE_DISABLED`。保留 WATCH 槽位给真正的 WATCH 信号。

```python
# 修改建议：entry_chain.py 中的 Probe 禁用逻辑

if disable_probe and action == "PROBE":
    return EntryDecision(
        action="REJECT",               # 改为 REJECT，而非 WATCH
        score=total_score,
        reason="PROBE_DISABLED",
        audit_trail=audit_trail
    )
```

### 5.2 多头阈值偏移的方向验证

计划使用 `long_threshold_offset: float = 10.0`（0-100 分制），意为多头 Direct 阈值从 70 提升至 80。需要验证：

```python
# entry_chain.py 中的偏移应用逻辑（必须明确方向）

def get_effective_threshold(base_threshold: float, side: str, config) -> float:
    """
    注意：long_threshold_offset 是加法偏移（提高门槛），不是乘数
    正数 = 更严格（门槛提高）
    负数 = 更宽松（门槛降低）
    """
    if side == "LONG":
        return base_threshold + config.long_threshold_offset
    elif side == "SHORT":
        return base_threshold + config.short_threshold_offset
    return base_threshold

# 测试验证（必须加入 test_entry_chain.py）
def test_long_threshold_offset_raises_bar_for_long_signals():
    """多头 +10 偏移 → LONG DIRECT 需要 80 而非 70"""
    cfg = EntryChainConfig(long_threshold_offset=10.0)
    score_69 = make_signal(side="LONG", score=69.0)
    score_81 = make_signal(side="LONG", score=81.0)
    assert evaluate(score_69, cfg).action == "PROBE"   # 69 不满足新 DIRECT 门槛 80
    assert evaluate(score_81, cfg).action == "DIRECT"  # 81 满足

def test_long_threshold_offset_does_not_affect_short_signals():
    """long_threshold_offset 不影响空头信号"""
    cfg = EntryChainConfig(long_threshold_offset=10.0, short_threshold_offset=0.0)
    score_72 = make_signal(side="SHORT", score=72.0)
    assert evaluate(score_72, cfg).action == "DIRECT"  # 空头仍用原始阈值 70
```

### 5.3 黑名单符号的检查时机

计划在 `entry_chain_gates.py` 的 `hard_block_reason()` 中实现黑名单检查，这意味着**黑名单检查发生在评分之后**。

**问题：** 评分计算（EMA、CCI、MACD 等多个组件）已经运行，然后才被黑名单拒绝。在高频回测场景中浪费计算资源。

**建议：** 黑名单检查提升至评分流程**最前置**位置：

```python
# entry_chain.py 中评分入口（建议调整顺序）

def evaluate_entry_chain(symbol, signal_dir, ohlcv, config, ...):
    
    # Step 0: 黑名单检查（最低成本操作，最先执行）
    symbol_norm = symbol.upper().replace("-", "").replace("/", "")
    if symbol_norm in {s.upper() for s in config.blacklist_symbols}:
        return EntryDecision(action="REJECT", reason="SYMBOL_BLACKLISTED", score=0.0)
    
    # Step 1: 其他 Hard Gate（EMA200 方向等）
    # ...
    
    # Step 2: 指标计算 + 评分（最昂贵操作，最后执行）
    # ...
```

---

## 6. 中优先级：测试覆盖盲区

### 6.1 计划中缺失的关键测试

原始计划的测试用例设计覆盖了核心路径，但以下边界情况未包含：

**缺失测试 1：多批次费用计算验证**
```python
def test_partial_exit_fees_accumulate_per_batch():
    """
    验证：TP1 + TP2 + TP3 三次平仓的费用 = 3 × 单次平仓费用
    失败时：表明费用模型仍然只计算单次，将系统性高估净回报
    """
    result = simulate_atr_tp_exit(
        entry_price=100.0, side="LONG",
        bars=generate_trending_bars(target_rr=3.5),
        config=AtrTpExitConfig(tp_levels=(1.0, 2.0, 3.0)),
        fee_per_side=0.0005
    )
    assert len(result.partial_exits) == 3
    expected_total_fee = 0.0005 + (0.30 + 0.40 + 0.30) * 0.0005
    assert abs(result.total_fees_pct - expected_total_fee) < 1e-6
```

**缺失测试 2：ATR 前瞻性验证**
```python
def test_atr_computed_from_closed_bars_only():
    """验证：ATR 不包含当前未完成 bar 的数据"""
    # 在信号时间点，最后一根 bar 尚未关闭
    # ATR 必须基于 ohlcv.iloc[:-1] 计算
    pass
```

**缺失测试 3：保本缓冲价格计算**
```python
def test_breakeven_price_includes_fee_buffer():
    """验证：保本止损 = 入场价 + 手续费缓冲（不是精确入场价）"""
    config = AtrTpExitConfig(breakeven_buffer_pct=0.001)
    # 触发 TP1 后，止损应移至 entry × (1 + 0.001)，而非精确 entry
    pass
```

**缺失测试 4：最大持仓时间与冷却的交互**
```python
def test_timeout_exit_triggers_correct_cooldown():
    """
    timeout 出场（非止损亏损，非 TP 盈利）应触发怎样的冷却？
    计划中未定义 timeout 的冷却规则
    """
    pass
```

**缺失测试 5：Probe 禁用改为 REJECT（如采纳建议）**
```python
def test_probe_disabled_returns_reject_not_watch():
    """Probe 禁用后动作应为 REJECT，而非 WATCH"""
    cfg = EntryChainConfig(disable_probe=True)
    result = evaluate_entry_chain(score=65.0, ...)  # 65 → 通常为 PROBE
    assert result.action == "REJECT"
    assert result.reason == "PROBE_DISABLED"
```

---

## 7. 低优先级：CLI 参数验证缺失

### 7.1 tp-levels 与 tp-fractions 的一致性验证

```python
# scripts/run_offline_backtest.py 中必须加入的验证

def validate_lifecycle_cli_args(args) -> None:
    if args.exit_model != "atr_tp":
        return

    tp_levels   = [float(x) for x in args.tp_levels.split(",")]
    tp_fractions= [float(x) for x in args.tp_fractions.split(",")]

    if len(tp_levels) != len(tp_fractions):
        raise ValueError(
            f"--tp-levels 和 --tp-fractions 数量必须相同，"
            f"当前: {len(tp_levels)} vs {len(tp_fractions)}"
        )

    frac_sum = sum(tp_fractions)
    if abs(frac_sum - 1.0) > 1e-4:
        raise ValueError(
            f"--tp-fractions 之和必须为 1.0，当前为 {frac_sum:.4f}"
        )

    for i, lvl in enumerate(tp_levels):
        if lvl <= 0:
            raise ValueError(f"--tp-levels[{i}] 必须为正数，当前为 {lvl}")

    if args.atr_stop_mult <= 0 or args.atr_stop_mult > 5.0:
        raise ValueError(
            f"--atr-stop-mult 范围 (0, 5.0]，当前为 {args.atr_stop_mult}"
        )
```

### 7.2 default_atr_pct 必须显式要求

```
当前计划：atr_pct from signal["atr_pct"] or risk_constraints["default_atr_pct"]

问题：若两者均未提供，代码将 KeyError 或使用 None 进行浮点运算

要求：
  a. risk_constraints 中必须始终包含 default_atr_pct
  b. run_offline_backtest.py 中加入 --default-atr-pct 参数，默认 0.010（1%）
  c. lifecycle_exit.py 中：assert atr_pct is not None and atr_pct > 0
```

---

## 8. ATR/TP 生命周期推荐规格（修订版）

综合以上所有建议，生命周期配置修订版如下：

```python
@dataclass(frozen=True)
class AtrTpExitConfig:
    # ── 止损设置 ─────────────────────────────────────────────
    atr_stop_mult:        float = 1.5     # 初始止损 = 入场价 ± 1.5 × ATR
    min_stop_pct:         float = 0.005   # 止损最小 0.5%（防止 ATR 极小时过窄）
    max_stop_pct:         float = 0.030   # 止损最大 3.0%（原 4.0% 偏大，建议收紧）
    default_atr_pct:      float = 0.010   # fallback ATR（信号 payload 缺失时）

    # ── 止盈梯度（修订：TP1 比例提升至 40%）─────────────────
    tp_levels:    tuple[float, float, float] = (1.0, 2.0, 3.0)  # R 倍数
    tp_fractions: tuple[float, float, float] = (0.40, 0.35, 0.25)  # 修订

    # ── 保本调整（含费用缓冲）──────────────────────────────────
    breakeven_after_tp1:  bool  = True
    breakeven_buffer_pct: float = 0.001   # 保本 = entry ± 0.1%（补偿手续费）

    # ── 最大持仓时间（修订：从 96 降至 16，对应 4 小时）──────
    max_hold_bars:        int   = 16      # 研究阶段保守值

    # ── 同柱保守处理 ───────────────────────────────────────────
    # 同一 bar 若止损和 TP 均触发，默认止损优先（保守主义）
    conservative_same_bar: bool = True   # 明确字段化，便于测试切换
```

**推荐命令行（修订版）：**

```powershell
python scripts/run_offline_backtest.py \
  --data-dir data/raw/binance_futures/latest_30d \
  --timeframe 15m \
  --strategy entry-chain \
  --entry-chain-config configs/entry_chain.dry_run_ema_soft_lifecycle_hardened.json \
  --exit-model atr_tp \
  --atr-stop-mult 1.5 \
  --tp-levels 1,2,3 \
  --tp-fractions 0.4,0.35,0.25 \
  --max-hold-bars 16 \
  --default-atr-pct 0.010 \
  --simulated-hold-bars 2 \
  --cooldown-bars 8 \
  --run-id latest_30d_ema_soft_lifecycle_hardened_v2
```

---

## 9. 报告与验证补充要求

### 9.1 报告必须增加的对比项目

原始计划的报告模板已包含基本要素，但需补充以下内容：

```
必须新增的报告节：

A. 费用明细对比（修订后）
   ─────────────────────────────────────────────────────────
   | 实验           | 进场费  | 出场批次 | 出场费  | 总费用 |
   | EMA Soft 合成  |  60.5   |    1次   |  60.5   | 121.0 |
   | 生命周期硬化   |  XX.X   |  1-3次   |  XX.X   | XX.X  |

B. TP 到达率分布
   TP1 触发比例：XX%（目标：胜率 × 100% 的参考基准）
   TP2 触发比例：XX%（应 < TP1 触发比例）
   TP3 触发比例：XX%（应 < TP2 触发比例）
   止损触发比例：XX%（= 1 - TP3 触发比例，若有 breakeven 则分段）

C. 平均持仓时间
   胜利笔平均持仓（bars）：XX
   亏损笔平均持仓（bars）：XX
   Timeout 触发比例：XX%（高 timeout 比例说明 max_hold_bars 设置不合理）

D. ATR 止损触发分布（按 bar 序号）
   早期止损（bar 1-3）：XX%（信号质量问题 or ATR 过紧）
   中期止损（bar 4-16）：XX%（正常区间）
   晚期止损（bar 17+）：XX%（ATR 过宽 or max_hold_bars 过长）
```

### 9.2 部署决策门控（报告结论必须明确回答）

```
报告结论必须对以下问题给出明确的是/否：

  □ 期望值是否由负转正？（Critical Gate #1）
     是 → 继续，否 → 出场生命周期仍有根本问题，停止
     
  □ 交易次数是否 ≥ 30？（Statistical Minimum Gate）
     是 → 继续，否 → 启动应急方案，放宽硬化约束
     
  □ 盈亏比是否 ≥ 1.0？（Fee Coverage Gate）
     是 → 继续，否 → 调查费用结构（确认多批次费用计算正确）
     
  □ 最大回撤是否 ≤ 15%？（Risk Gate）
     是 → 继续，否 → 调整 ATR 乘数或降低杠杆
     
  □ src/api/binance_client.py 是否零改动？（Safety Gate）
     是 → 继续，否 → 立即停止，排查执行层渗透
```

---

## 10. 实施顺序重排建议

### 10.1 原始计划 vs 建议顺序对比

```
原始计划顺序：
  Task 1 ATR/TP 模型
  Task 2 引擎路由
  Task 3 入场硬化
  Task 4 CLI 扩展
  Task 5 30D 回测
  Task 6 报告 + 验证

建议顺序（修订后）：
  Step 0 费用模型审查（新增，1天）← Critical 修正，先做
  Task 1 ATR/TP 模型（含费用缓冲 + ATR 前瞻 + TP 比例修订）
  Task 3 入场硬化（Probe→REJECT + 黑名单前置）
  Task 2 引擎路由（费用模型确认后再接入引擎）
  Task 4 CLI 扩展（含参数验证）
  Task 5 30D 回测（先用 max_hold_bars=16 and tp_fractions=0.4,0.35,0.25）
  Task 6 报告（含新增三个分析节）
```

### 10.2 最小可验证单元（建议先独立跑通）

在整个任务链接之前，先验证生命周期模型的核心假设：

```python
# 独立验证脚本（不依赖回测引擎）
# scripts/verify_lifecycle_logic.py

def verify_tp_ladder_profitability():
    """
    验证：在 65% 胜率 + 多批次费用正确计入 下，ATR/TP 生命周期是否期望值 > 0

    假设：
      entry_price = 100
      ATR = 1.0%，stop_mult = 1.5 → 止损距离 = 1.5%
      TP1 = 1.0R = 1.5%，平 40%
      TP2 = 2.0R = 3.0%，平 35%
      TP3 = 3.0R = 4.5%，平 25%
      费用 = 0.05% × (1进 + 3出) = 0.20%
    """
    win_rate    = 0.65
    fees        = 0.0020    # 含3次平仓

    # 加权盈利回报
    avg_win_gross = 0.40*0.015 + 0.35*0.030 + 0.25*0.045  # = 0.02775 = 2.775%
    avg_loss_gross = -0.015    # 止损 1.5%

    ev = win_rate*avg_win_gross + (1-win_rate)*avg_loss_gross - fees
    print(f"期望值（含多批次费用）: {ev:.4f}")
    assert ev > 0, f"即使 65% 胜率，费用模型下仍为负期望：{ev:.4f}"
    # 若此验证失败：说明 ATR 止损需要收紧 or TP 需要拉大
```

此脚本应在 Task 1 之前运行，确认参数配置在理论上可以盈利，再投入实现。

---

*建议报告结束 | Exit Lifecycle Plan Review v1.0*
*最高优先行动：先运行 verify_lifecycle_logic.py 确认费用修正后的理论期望值 > 0，再进入 Task 1 实现阶段。*
