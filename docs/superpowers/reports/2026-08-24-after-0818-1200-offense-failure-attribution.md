# 08-18 12:00 后上涨段进攻漏选复盘

> 生成日期: 2026-08-24
> 范围: 2026-08-18 12:00 ~ 2026-08-24 19:45 北京时间
> 目标: 解释为什么这段上涨行情没有赚钱,并给出一个能把这段牛市选出来的无未来函数候选规则,供 Claude 评审。

## 0. 结论

这段行情不是“没看到”,而是“看到了但选错了”。

核心问题有三层:

1. **牛市识别太晚**: breadth 已经转正,但 `q1_trend_launch` 第一笔真正落地到 08-22 17:45,比主升段晚了约 3 天。
2. **主账本方向偏空**: 主账本 14 笔 close 里 10 笔是 SHORT, 总体亏损 `-81.94`, SHORT 合计亏 `-83.19`。
3. **象限规则把上涨段当成追单/低 RR/风控噪声**: 大量高分 LONG 被 `SIDE_THRESHOLD_OFFSET_LONG_10.00`、`OPPOSITION_STRUCTURE_TOO_CLOSE`、`SYMBOL_BLACKLISTED`、`SYMBOL_WATCH_ONLY`、`DAILY_TRADE_BUDGET_USED` 拦掉,或者被反转 scout 抢走。

根据后续评审,优先级需要重排:

- **P0 不是先新增主账本进攻通道,而是先审计 confirmed bullish regime 下为什么 SHORT 仍更容易被执行。**
- **P1 才是 `BULL_REGIME_BREAKOUT_V1` shadow/scout 化**,且必须先纳入累计样本追踪和 mission 路由优先级表。

本轮已补充离线审计脚本 `scripts/audit_bullish_regime_short_bias.py`,以 08-19 19:15 作为 confirmed bullish regime 起点复核高分 LONG/SHORT 可执行率。

## 1. 上轮建议实施回顾

| 08-18 建议 | 状态 | 证据 |
|---|---|---|
| mirror A/B 降级为 shadow-only | 已在配置中保持 `mirror_ab_mode=shadow_only` | `configs/entry_chain.dry_run_fib_pa_v1.json` |
| ChannelCumulativeTracker 建立 | 已建立,本轮继续扩展候选通道 | `scripts/channel_cumulative_tracker.py` |
| 20 笔评估门槛纪律 | 继续执行 | `<10 不提炼; <20 不调参/不资源倾斜` |
| REVERSAL_PIVOT_SCOUT 停用 | 已保持停用 | `scout_micro_reversal_pivot_enabled=false` |

## 2. 这段行情确实是牛市

窗口内主要标的涨幅:

| Symbol | Close 变动 |
|---|---:|
| ZECUSDT | +65.58% |
| XRPUSDT | +51.12% |
| BCHUSDT | +35.23% |
| HYPEUSDT | +35.06% |
| DOGEUSDT | +32.13% |
| ADAUSDT | +29.54% |
| XLMUSDT | +28.53% |
| SOLUSDT | +27.01% |
| LINKUSDT | +24.47% |
| BNBUSDT | +16.60% |

走势不是单根直线，而是两段脉冲式上冲:

- 08-19 晚到 08-20 早: SOL, LINK, DOGE, BNB, XRP 同时抬升
- 08-21 晚到 08-22: BCH, HYPE, ZEC 再次放量上行
- 08-23 ~ 08-24: 回撤后仍有二次抬升, breadth 没有彻底塌掉

一个关键事实:

- 对主交易子集,**5 个符号在 6 小时内同时出现确认突破**的 breadth 门槛,第一次出现在 **08-19 19:15**。
- 但 `q1_trend_launch` 第一笔落地是 **08-22 17:45**。

这说明系统不是没识别出牛市,而是识别得太晚。

## 3. 总体账本表现

| 账本 | close 数 | PnL | Win rate | PF |
|---|---:|---:|---:|---:|
| `paper_trades` | 14 | -81.94 | 35.71% | 0.424 |
| `scout_micro` | 24 | -4.93 | 33.33% | 0.414 |
| `paper_ab/legacy` | 66 | -84.68 | 19.70% | 0.349 |
| `paper_ab/trend_capture` | 68 | -138.45 | 14.71% | 0.119 |

主账本按方向看:

- LONG: `+1.25`
- SHORT: `-83.19`

所以不是“做多没赚”,而是“整个系统在上涨段里仍然持续做空”。

## 4. 按象限归因

### Q1

Q1 是最接近正确方向的象限,但它没有成为真正的牛市入口。

证据:

- Q1 long near-miss: 71
- Q1 short near-miss: 40
- Q1 仍然大量触发 `SIDE_THRESHOLD_OFFSET_LONG_10.00`
- 高分 LONG 常见附加阻断: `SYMBOL_BLACKLISTED`, `SYMBOL_WATCH_ONLY`, `SYMBOL_POSITION_ALREADY_OPEN`, `DAILY_TRADE_BUDGET_USED`

问题:

1. **Q1 不是 regime selector,只是局部高分区**。
2. 许多 Q1 LONG 的 `extreme_position_ratio` 已经很靠近区间上沿,被当成追单。
3. **Q1 仍然允许 SHORT**。在上涨段里,这直接把系统推向负期望。

`q1_trend_launch` 的实际落地也证明了这一点:

- 首次落地: 08-22 17:45
- 4 笔 close: LINK SHORT, XMR LONG, DOGE LONG, HYPE SHORT
- 结果: 仍然净亏

也就是说,Q1 不是不能用,而是不能单独决定“此刻是不是牛市”。

### Q2

Q2 是“结构未完全确认,但动能已经起来”的区域。

统计:

- Q2 long near-miss: 112
- Q2 short near-miss: 48
- `scout_micro/Q2_PENDING_MOMENTUM` close: 15
- 该 mission 的净 PnL: `-3.7378`

问题:

1. Q2 的确认太慢,经常在趋势已经走完一截之后才进。
2. 很多样本被 `SIDE_THRESHOLD_OFFSET_LONG_10.00`、`SYMBOL_WATCH_ONLY`、`SYMBOL_BLACKLISTED`、预算限制挡掉。
3. Q2 适合做“二次确认”,不适合单独当作主升段起点。

### Q3

Q3 是这轮里最能提早看到多头启动的象限,但它被设计成 probe,不是主入口。

统计:

- Q3 long near-miss: 14
- `HIGH_SCORE_LONG_OFFSET_PROBE` 7 笔全部是 LONG
- 该 mission close 6 笔,净 PnL `-1.3389`, PF `0.1136`

典型样本:

- BNB 08-19 08:15: Q3 LONG, score 87.3, volume 1.74x, 后续确实继续拉升,但 scout 入口仍然把它当成 early probe,不是 regime 入口

问题:

1. Q3 能抓到早期拐点,但太依赖小仓 probe。
2. 早期样本经常先回撤,容易被 stop/timeout 吃掉。
3. 它缺少“后续再确认进入主升段”的桥梁。

### Q4

Q4 基本是过滤层,不是赚钱层。

统计:

- Q4 decisions: 4158
- Q4 no_trade: 4123

它做到了不乱开仓,但没有把牛市从过滤层推进到进攻层。

## 5. 为什么没有赚钱

### 5.1 主账本方向在上涨段里偏空

主账本 14 笔 close:

- SHORT 10 笔,亏 `-83.19`
- LONG 4 笔,赚 `+1.25`

这不是“做多少了”,而是“空单太多且不该开”。

### 5.2 `q1_trend_launch` 太晚

breadth 首次确认在 08-19 19:15,但 `q1_trend_launch` 第一笔主账本动作在 08-22 17:45。

它错过的是主升段,不是回头段。

### 5.3 现有 gating 把上涨解释成追单

高分 LONG 的最常见拒绝理由是:

- `SIDE_THRESHOLD_OFFSET_LONG_10.00`
- `OPPOSITION_STRUCTURE_TOO_CLOSE`
- `SYMBOL_BLACKLISTED`
- `SYMBOL_WATCH_ONLY`
- `DAILY_TRADE_BUDGET_USED`

这套规则对单点追高是对的,但对“回撤后二次突破”的趋势段不够。

### 5.4 出场优化不是主矛盾

A/B 账本里 `trend_capture` 仍然比 `legacy` 好,但两者都明显负:

- legacy PF `0.034`
- trend_capture PF `0.0654`

说明问题不在单纯出场,而在入场池质量和方向选择。

## 6. SHORT 偏向审计

本轮新增 `scripts/audit_bullish_regime_short_bias.py`,以 08-19 19:15 作为 confirmed bullish regime 起点,统计 score >= 80 的 LONG/SHORT 可执行率。可执行定义为 `DIRECT` 或 `PROBE`;`WATCH` 与 `NO_TRADE` 不计为可执行。

| 方向 | 高分样本 | 可执行数 | 可执行率 |
|---|---:|---:|---:|
| LONG | 97 | 4 | 4.12% |
| SHORT | 72 | 12 | 16.67% |

SHORT 高分样本少 25 个,但可执行数多 8 个,可执行率高 12.55 个百分点。这支持评审里的判断:这轮最紧迫的问题不是继续让 LONG 更容易通过,而是先解释为什么 confirmed bullish regime 下 SHORT 更容易落地。

按象限看:

| 象限 | LONG 高分/可执行/率 | SHORT 高分/可执行/率 |
|---|---:|---:|
| Q1 | 82 / 3 / 3.66% | 56 / 11 / 19.64% |
| Q2 | 6 / 1 / 16.67% | 2 / 1 / 50.00% |
| Q3 | 9 / 0 / 0.00% | 14 / 0 / 0.00% |
| Q4 | 0 / 0 / 0.00% | 0 / 0 / 0.00% |

结论: SHORT 偏向主要来自 Q1,其次 Q2 样本很少但方向也不利。下一步如果设计 `regime_conditional_side_offset`,应先只作为 shadow 审计和离线回放,不能直接改 live 风控或生产配置。

## 7. 这段牛市应该怎么被选出来

不建议继续简单降 `long_threshold_offset`。

更合理的是先完成两层工作:

1. P0: 审计并控制 confirmed bullish regime 下 SHORT 执行非对称。
2. P1: 新增一个只用已收盘 K 线的 `BULL_REGIME_BREAKOUT_V1` shadow/scout 选择器。

```yaml
BULL_REGIME_BREAKOUT_V1:
  source: completed_15m_only
  side: LONG
  confirm:
    - close > previous_32_bar_close_high
    - volume >= 1.15 * previous_32_bar_median_volume
    - next_closed_bar holds breakout level
    - close_location >= 0.55
    - upper_wick <= max(1.5 * body, 0.15% price)
  regime_gate:
    - at least 5 symbols in the tradable universe have a confirmed breakout within 6h
    - or at least 3 core symbols if the symbol is targeted large-cap
  safety:
    - if there was a failed early probe, require a fresh 32-bar high after pullback
    - keep REVERSAL_PIVOT_SCOUT disabled or shadow-only on the same sample
    - route to scout/shadow first, not direct main book
```

为什么这条规则能选出这段牛市:

- 它只看已收盘数据,没有未来函数。
- 它把“单币突破”升级成“单币突破 + 市场宽度确认”。
- 它能识别 08-19 晚上的 breadth 转正,而不是等到 08-22 才进。

实际反事实扫描里,这类确认在多个符号上都能抓到:

- SOL 08-18 19:45
- DOGE 08-18 22:30
- LINK 08-18 23:15
- BNB 08-19 08:30
- XLM 08-19 13:00
- BCH / HYPE 08-19 19:15 附近

这说明“牛市”本来就是可被已收盘数据选出来的。

但该规则不能直接进入主账本。它必须先满足:

- mission 路由优先级和互斥规则明确。
- `scout_bull_regime_breakout_v1` 纳入 `ChannelCumulativeTracker`。
- 至少 20 笔 shadow/scout 样本后再评估 PF、胜率、最大回撤、MFE/MAE、尾部亏损和暴露。

## 8. 不该怎么修

1. **不要只降 `long_threshold_offset`**。那只会把早追样本放大。
2. **不要只放宽 RR**。那会把贴近阻力的追单放进主账本。
3. **不要把 Q1 当成单独的开仓理由**。Q1 必须依附 regime/source。
4. **不要重新启用 `REVERSAL_PIVOT_SCOUT` 去抢占高分 LONG continuation**。当前配置里它已经是 `enabled=false`,下一轮报告应继续明确 mission-level real opens 是否为 0。

## 9. 给 Claude 的评审问题

1. 是否同意这次失败的根因优先级应调整为“confirmed bullish regime 下 SHORT 执行偏向”高于“牛市识别太晚”?
2. 是否同意 `q1_trend_launch` 必须增加 source/regime 约束,不能只看分数?
3. 是否同意 `BULL_REGIME_BREAKOUT_V1` 应该先做 shadow/scout,再决定是否进主账本?
4. 是否同意当前应继续保持 `REVERSAL_PIVOT_SCOUT` disabled/shadow-only,并把本轮 SHORT 偏向归因重点转向 Q1/Q2 常规执行链路?
5. breadth 门槛更适合 5/6h 还是 4/6h? 哪个更平衡早捕捉和误报?

## 10. 复核命令

```powershell
python scripts\verify_q1_trend_launch_fix.py --mode online --log-root logs --hours 144 --config configs\entry_chain.dry_run_fib_pa_v1.json
python scripts\evaluate_offense_fixes.py --log-root logs --days 6
python scripts\summarize_scout_trend_capture_diagnostics.py --log-root logs --start 2026-08-18 --end 2026-08-24
python scripts\audit_bullish_regime_short_bias.py --log-root logs --start 2026-08-18 --end 2026-08-24 --regime-start "2026-08-19 19:15" --min-score 80 --output-dir reports\analysis\2026-08-24-short-bias
python scripts\channel_cumulative_tracker.py --start 2026-08-18 --end 2026-08-24
```

上述命令表明:

- `q1_trend_launch` 有转化,但仍旧晚且净负
- `HIGH_SCORE_LONG_OFFSET_PROBE` 仍是负期望,样本数也还不够
- `trend_capture` A/B 口径仍然明显落后于需要修复的目标
- confirmed bullish regime 下 score >= 80 的 SHORT 可执行率为 16.67%,LONG 为 4.12%
- `scout_bnb_trend_continuation_after_pullback` 与 `scout_bull_regime_breakout_v1` 已纳入累计追踪,当前样本均为 0
