# BULL_REGIME_BREAKOUT_V1 设计 + 六通道路由优先级表 — 08-24 DEEPSEEK 评审

**状态:** 设计 + shadow 纳管(不进主账本)
**依据:** 08-24 报告(牛市漏选复盘)+ DEEPSEEK 评审(第 4/6 节)

---

## 1. BULL_REGIME_BREAKOUT_V1 设计(shadow/scout)

```yaml
BULL_REGIME_BREAKOUT_V1:
  source: completed_15m_only(无未来函数)
  side: LONG
  confirm:
    - close > previous_32_bar_close_high
    - volume >= 1.15 * previous_32_bar_median_volume
    - next_closed_bar holds breakout level(次根收盘守住)
    - close_location >= 0.55
    - upper_wick <= max(1.5 * body, 0.15% price)
  regime_gate:
    - breadth: >=5 symbols 在 6h 内确认突破(保守 5/6h,不凭 N=1 拍板)
    - 或 >=3 core symbols(若为目标大市值)
  safety:
    - 早追失败后要求新 32-bar 高点(非简单冷却豁免)
    - REVERSAL_PIVOT_SCOUT 保持 disabled/shadow(同一样本)
    - 先 shadow/scout,不进主账本;>=20 笔 shadow 样本后评估
  reuse:
    - 单 symbol 突破逻辑复用 08-13 BNB_TREND_CONTINUATION_AFTER_PULLBACK 规格
      (避免两套重复实现;regime_gate 作为可选上层过滤)
```

### 1.1 与 08-13 BNB 规则的关系
- 底层:单 symbol 突破确认(32-bar high + volume + 实体位置 + 上影线)——复用 BNB 规格;
- 上层:regime_gate(breadth 多 symbol 确认)——BULL_REGIME_BREAKOUT_V1 独有;
- 实现时重构为"底层突破检测 + 可选 regime 过滤",避免重复代码。

### 1.2 样本纪律(08-18 固化)
- 6 个反事实符号(SOL/DOGE/LINK/BNB/XLM/BCH/HYPE)是 N=1 个 regime 事件下的同源样本,非独立验证;
- <10 样本:不"证明有效";<20:不调参/不优先;达 20 笔后评估 PF/胜率/MFE/MAE/尾部亏损。

## 2. 六通道路由优先级/互斥表

| 优先级 | 通道 | 方向 | 候选来源 | 互斥/说明 |
|---|---|---|---|---|
| 1 | q1_trend_launch | LONG/SHORT | Q1 near-miss(score≥82+组件) | 主账本实验通道;待 source 约束(S2) |
| 2 | Q2_PENDING_MOMENTUM | LONG/SHORT | Q2 pending 确认 | 与 Q3→Q1 互斥(同 pending 只确认一次) |
| 3 | Q3_TO_Q1_CONFIRMATION | LONG/SHORT | Q3 pending 确认 | 与 Q2 pending 互斥 |
| 4 | HIGH_SCORE_LONG_OFFSET_PROBE | LONG | SIDE_THRESHOLD_OFFSET_LONG 高分 | 仅 LONG;RR≥2 进真实 scout |
| 5 | scout_bnb_trend_continuation_after_pullback | LONG | 早追失败后 32-bar 突破 | 与 BULL_REGIME 共用底层逻辑 |
| 6 | scout_bull_regime_breakout_v1 | LONG | 单 symbol 突破 + regime_gate | **shadow-only**;同一样本不被 REVERSAL_PIVOT 抢占(已停用) |

**路由规则:**
- 候选同时满足多通道时,按优先级表自上而下首个可执行者路由;
- q1_trend_launch 与 Q2/Q3 pending 的确认标签互斥(已由 confirm 链保证);
- BULL_REGIME_BREAKOUT_v1 先 shadow,不参与主账本路由,仅记录;
- 任何通道 20 笔评估前不调整路由优先级(08-18 纪律)。

## 3. tracker 纳管

`scripts/channel_cumulative_tracker.py` 已纳入 `scout_bnb_trend_continuation_after_pullback` + `scout_bull_regime_breakout_v1`(08-24 CHATGPT 更新),当前样本 0,随 shadow 开仓自动累计。
