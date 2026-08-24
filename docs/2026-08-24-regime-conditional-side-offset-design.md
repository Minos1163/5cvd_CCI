# regime_conditional_side_offset 设计(shadow) — 08-24 DEEPSEEK 3.3 节

**状态:** 设计 + shadow 实施(不改 live 门槛)
**依据:** 08-24 SHORT 偏向审计——confirmed bullish regime(08-19 19:15 起)下高分 SHORT 可执行率 16.67%(12/72)vs LONG 4.12%(4/97);Q1 主导(SHORT 19.64% vs LONG 3.66%)。

---

## 1. 问题本质

- LONG 有 `long_threshold_offset=10.0`(direct 门槛 82→92),SHORT **无对称机制**(direct 82);
- 静态的 LONG 专属门槛在"无 regime 判断"时是合理的保守默认(DEEPSEEK 3.3 节认可);
- 但 regime 转牛后,对称逻辑应是"bullish 下 SHORT 才需额外谨慎",而非维持静态 LONG 门槛。

## 2. 设计

### 2.1 regime 判定来源(breadth)
- **breadth ≥ 5 symbols / 6h**(08-24 报告建议,保守 5/6h 而非 4/6h——shadow 期误报成本低,宽松门槛会让 regime_gate 形同虚设);
- 判定基于已收盘 15m K 线(单 symbol 突破定义见 BULL_REGIME_BREAKOUT_V1:close > 前 32-bar close high + volume ≥ 1.15x 中位);
- 首次确认时间(08-19 19:15 北京)作为本轮 regime 起点,shadow 期用同一口径。

### 2.2 SHORT 对称 offset(shadow)
- 配置(shadow 参数):`regime_conditional_short_offset_shadow` = {enabled, short_offset_candidates: [5.0, 10.0], min_score: 80};
- 反事实(`scripts/regime_conditional_short_offset_shadow.py`):bullish 窗口高分 SHORT 若 direct 门槛 = 82 + offset,统计被拦截样本;
- **shadow 结果(offset=10):12/12 高分 SHORT 全被拦截,可执行率降 16.67pp**——非对称修复的上界验证;
- offset 取值:5.0 与 10.0 并行 shadow 记录(校准用),不预先拍板。

### 2.3 验证协议(shadow 期)
- shadow 期 ≥ 20 笔被拦样本后,对比被拦样本的 MFE/MAE(被拦的是否真为亏损 SHORT);
- 若被拦样本 MFE 显著为负(即拦住的是亏损单)→ 对称 offset 有效,可考虑进入 live(需评审);
- 若被拦样本含盈利 → 过度拦截,调低 offset;
- **live 决策不变**(纯 shadow 观测)。

## 3. 现状(不改 live)

- `long_threshold_offset` 保持 10.0;SHORT 门槛 82 不变;
- shadow 脚本输出:logs/analysis/2026-08-24-short-bias/regime_conditional_short_offset_shadow.json。

## 4. 后续(待评审)

- breadth 历史回测(180 天多 regime 事件)为 5/6 vs 4/6 提供证据(08-24 评审 5.2 节);
- 若 shadow 验证通过,`regime_conditional_side_offset` 以配置化方式进入 live(regime 状态驱动),需单测 + 评审。
