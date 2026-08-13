# BNB 2026-08-07~08-10 上涨段进攻漏选分析

> 生成日期: 2026-08-13
> 范围: 最新 48H 日志 + BNBUSDT 2026-08-07 00:00 到 2026-08-10 12:00 北京时间 K 线与决策链
> 目标: 解释为什么四象限进攻策略没有把该段 BNB 多头选出来,并提出下一轮可评审的策略修正方向。

## 0. 结论摘要

BNB 这段不是完全没有被系统看到。日志显示系统至少三次识别到 BNB 高分 LONG 候选:

| 时间(北京) | 象限 | 方向 | 分数 | 系统处理 | 结果 |
|---|---:|---:|---:|---|---|
| 08-07 08:30 | Q3 | LONG | 81.3 | 被 `REVERSAL_PIVOT_SCOUT` 翻成 SHORT | scout 空单 2h 后小亏超时出场 |
| 08-08 00:00 | Q1 | LONG | 88.7 | 只进 `HIGH_SCORE_LONG_OFFSET_PROBE` / mirror,没有进主账本 | 1.5h 后初始止损,随后才发生真正拉升 |
| 08-09 18:00 | Q1 | LONG | 82.7 | 因 `DAILY_TRADE_BUDGET_USED`; scout 又翻成 SHORT | scout 空单 2h 后小亏超时出场 |

真正的问题不是单个阈值太严,而是三层错配叠加:

1. **主账本没有进攻入口**: 8/7~8/10 BNB 主账本 `paper_trades.jsonl` 没有 BNB 交易; 高分 BNB 只进入 scout/mirror 观察账本。
2. **Q1 trend launch 没有转化**: 最近 48H 在线验证 `q1_trend_launch` 决策数为 0; BNB 窗口内两次 Q1 LONG 也都不满足 `_q1_trend_launch_eligible`。
3. **反转任务抢占了多头候选**: `REVERSAL_PIVOT_SCOUT` 会把带有 exhaustion/opposition warning 的 LONG 候选反向开 SHORT。BNB 在 08-07 08:30 和 08-09 18:00 都出现了这种方向翻转。
4. **当前评分链无法表达“回撤后二次突破”**: 8/8 下午真正有效的多头延续段,多数分数只有 50~78,原因集中在 RR=0/2、fib 不足、CCI 低、`SIDE_THRESHOLD_OFFSET_LONG_10.00` 和追单/过热标志,因此停留在 WATCH/NO_TRADE。

建议方向: 不要简单降低 `long_threshold_offset` 或放宽 Q1。应新增或重构一个 **BNB/大币种 trend continuation after failed early probe** 的候选机制: 只在早追失败后,等待回撤稳定并再次突破最近 32 根已收盘 K 线高点时,用小仓 scout 或 q1_trend_launch_v2 进多;同时禁止 `REVERSAL_PIVOT_SCOUT` 抢占高分 LONG continuation 样本。

## 1. 数据与假设

### 1.1 时间口径

用户指定窗口按本地运行环境 `Asia/Shanghai` 处理,即北京时间:

- 起点: 2026-08-07 00:00
- 终点: 2026-08-10 12:00

Binance K 线字段 `open_time` 是 Unix 毫秒时间戳。日志里的 `timestamp` / `kline_timestamp` 是 Unix 秒时间戳。本文展示均转为北京时间。

### 1.2 数据源

本仓库原始 `data/raw/binance_futures/latest_30d/BNBUSDT/15m.csv` 只到 2026-08-07 21:15 北京时间,不能覆盖用户指定完整窗口。因此本轮补拉了独立分析目录:

- `data/raw/binance_futures/bnb_20260813_analysis/BNBUSDT/15m.csv`
- `data/raw/binance_futures/bnb_20260813_analysis/BNBUSDT/1h.csv`
- `data/raw/binance_futures/bnb_20260813_analysis/BNBUSDT/4h.csv`

该目录位于 `/data/`,已被 `.gitignore` 忽略,不作为策略代码改动。

日志使用:

- `logs/2026-08/2026-08-07` 到 `logs/2026-08/2026-08-10`
- 最新 48H: `logs/2026-08/2026-08-12` 与 `logs/2026-08/2026-08-13`

### 1.3 交易安全假设

本报告只做研究与文档输出,不修改 live 执行、live 风控或生产配置。所有候选规则都只使用已收盘 K 线,不使用未来 candle、不使用 repaint 信号、不假设同 bar 成交。

## 2. BNB 实际 K 线结构

补拉的 15m 数据显示,窗口整体并非单边大牛,而是两段脉冲上涨夹杂回撤:

| 窗口 | Open | High | Low | Close | 区间收益 |
|---|---:|---:|---:|---:|---:|
| 08-07 00:00 ~ 08-10 12:00 | 592.71 | 612.46 | 585.60 | 603.38 | +1.80% |
| 窗口最高相对起点 | 592.71 | 612.46 | - | - | +3.33% |

12 小时分段:

| 分段 | Open | High | Low | Close | 收益 |
|---|---:|---:|---:|---:|---:|
| 08-07 00:00~11:45 | 592.71 | 594.93 | 590.11 | 593.15 | +0.07% |
| 08-07 12:00~23:45 | 593.15 | 593.83 | 585.60 | 592.71 | -0.07% |
| 08-08 00:00~11:45 | 592.71 | 594.85 | 591.08 | 593.78 | +0.18% |
| 08-08 12:00~23:45 | 593.77 | 612.46 | 593.03 | 605.53 | +1.98% |
| 08-09 00:00~11:45 | 605.54 | 607.92 | 599.34 | 600.76 | -0.79% |
| 08-09 12:00~23:45 | 600.76 | 612.09 | 600.69 | 608.97 | +1.37% |
| 08-10 00:00~11:45 | 608.97 | 611.95 | 601.60 | 602.87 | -1.00% |

可被已收盘 K 线识别的主要多头阶段:

1. **08-08 12:45~14:30**: 重新站上近 32 根收盘高点,成交量放大,之后进入 18:00 后续涨。
2. **08-08 18:15~20:00**: 突破持续,但系统评分仍偏低,主要被 RR/fib/CCI 拖累。
3. **08-08 21:30~22:15**: 爆发段,但属于偏追单位置,后续可用空间有限。
4. **08-09 14:00~18:00**: 第二段上行,系统在 18:00 识别到 Q1 LONG 82.7,但被预算与反转 scout 处理掉。

## 3. 最新 48H 日志概况

最新 48H 统计口径为 `2026-08-12` 和 `2026-08-13` 日志目录:

| 指标 | 全市场 | BNB |
|---|---:|---:|
| decisions | 1950 | 150 |
| near_misses | 56 | 3 |
| scout_decisions | 56 | 3 |
| trades | 99 | 0 |

最新 48H BNB 决策分布:

| 维度 | 分布 |
|---|---|
| action | NO_TRADE 128, WATCH 22 |
| side | LONG 62, SHORT 88 |
| quadrant | Q4 84, Q3 36, Q2 15, Q1 15 |

在线验证命令:

```powershell
python scripts\verify_q1_trend_launch_fix.py --mode online --log-root logs --hours 48 --config configs\entry_chain.dry_run_fib_pa_v1.json
```

输出结论:

```text
q1_trend_launch 相关决策数: 0
near-miss 中携带废弃标签数(信息性, 判定已解耦): 3
RESULT: 修复未验证通过(需 q1_trend_launch 转化>0)。
```

这说明当前进攻策略在最近 48H 仍没有主账本 trend-launch 转化。BNB 近 48H 的 3 条 near-miss 也全部被 `SCOUT_NO_MISSION` 拒绝,没有 BNB 交易。

## 4. 8/7~8/10 BNB 日志链

窗口内 BNB 决策统计:

| 指标 | 数量 |
|---|---:|
| BNB decisions | 384 |
| BNB near_misses | 4 |
| BNB scout_decisions | 4 |
| BNB 主账本 trades | 0 |
| BNB scout/mirror 相关 trade events | 12 |

BNB action / side / quadrant:

| 维度 | 分布 |
|---|---|
| action | NO_TRADE 319, WATCH 65, PROBE/DIRECT 0 |
| side | LONG 220, SHORT 164 |
| quadrant | Q4 212, Q3 77, Q2 47, Q1 48 |

### 4.1 BNB near-miss 明细

| 时间 | 象限 | 方向 | 分数 | 主原因 | 关键组件 | 系统结果 |
|---|---:|---:|---:|---|---|---|
| 08-07 08:30 | Q3 | LONG | 81.3 | `SIDE_THRESHOLD_OFFSET_LONG_10.00` | trend 14.3, PA 21, CVD 18, CCI 10, Fib 18, RR 0 | `REVERSAL_PIVOT_SCOUT` 翻 SHORT |
| 08-07 11:00 | Q3 | LONG | 81.3 | `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 同上, extreme 0.806 | 因 `SCOUT_MICRO_SAME_SIDE_COOLDOWN` 拒绝 |
| 08-08 00:00 | Q1 | LONG | 88.7 | `SIDE_THRESHOLD_OFFSET_LONG_10.00` | trend 15.7, PA 21, CVD 18, CCI 14, Fib 18, RR 2 | `HIGH_SCORE_LONG_OFFSET_PROBE` 小仓开多后止损 |
| 08-09 18:00 | Q1 | LONG | 82.7 | `DAILY_TRADE_BUDGET_USED` | trend 15.7, PA 21, CVD 18, CCI 10, Fib 18, RR 0 | `REVERSAL_PIVOT_SCOUT` 翻 SHORT |

### 4.2 实际 BNB 交易事件

| 时间 | 账本 | 方向 | 价格 | 通道 | 结果 |
|---|---|---:|---:|---|---|
| 08-07 08:30 | scout_micro | SHORT | 593.05 | `scout_reversal_pivot_scout` | 10:30 `COST_BREAKEVEN_TIMEOUT`, net -0.028, MFE 0.206R |
| 08-08 00:00 | scout_micro | LONG | 594.45 | `scout_high_score_long_offset_probe` | 01:30 `INITIAL_STOP_HIT`, net -0.300, MFE 0.017R |
| 08-08 00:00 | mirror A/B | LONG | 594.45 | `mirror_ab_sample` | 00:30 reduce, 01:00 close, net negative |
| 08-09 18:00 | scout_micro | SHORT | 604.60 | `scout_reversal_pivot_scout` | 20:00 `COST_BREAKEVEN_TIMEOUT`, net -0.011, MFE 0.218R |

主账本没有 BNB 多单。唯一正向尝试是 08-08 00:00 的 scout/mirror 小仓,但它在真正 08-08 下午拉升前被止损/防守退出。

## 5. 各象限策略为何没选出 BNB 多头

### 5.1 Q1: 状态高分但被定义为追单/低 RR,且 trend-launch 不接

BNB 的两个最高 LONG 样本都在 Q1:

| 时间 | 分数 | RR | extreme | long_overextension | 结果 |
|---|---:|---:|---:|---:|---|
| 08-08 00:00 | 88.7 | 2.0 | 0.904 | true | scout 小仓多,主账本不进;随后止损 |
| 08-09 18:00 | 82.7 | 0.0 | 0.966 | true | 主账本预算用完;scout 翻空 |

`_q1_trend_launch_eligible` 要求:

- quadrant = Q1
- score >= 82
- PA >= 18
- Fib >= 15
- CVD >= 16
- RR >= 0.5
- extreme ratio 在 [0.20, 0.80]
- LONG 不触发 overextension / upper wick / chase

BNB 两个 Q1 高分 LONG 都在近 8 根极值区间上沿,且 `long_overextension_active=true`,因此 trend launch 不转化。这是合理的防追单保护,但带来一个副作用:如果早追止损后市场回撤并再次突破,系统没有二次捕捉机制。

### 5.2 Q2: 趋势结构可以,但 CCI/动能轴弱,分数低于 near-miss/mission 输入

8/8 下午有效启动期间,Q2/Q1/WATCH 样本不少,但分数多在 50~78:

| 时间 | 象限 | 分数 | 关键缺口 |
|---|---:|---:|---|
| 08-08 18:00 | Q2 | 56.1 | CCI=0, RR=0, Fib=6 |
| 08-08 21:00 | Q1 | 70.1 | Fib=2, RR=2, 低于 scout/trend-launch |
| 08-09 22:00 | Q2 | 68.1 | CCI 近 0, 追单/过热, RR=2 |

Q2 pending 的当前逻辑要求 Q2 near-miss 被创建后,PA >= 18 且 score >= 70,再在若干 bar 内确认到 Q1。BNB 在 08-08 下午的 Q2 样本大多未达到 near-miss 输入门槛或 PA/score 同时达标,因此没有形成可确认的 pending。

### 5.3 Q3: 资金/动能轴强,但趋势结构轴不足,且被反转 scout 抢占

08-07 08:30 和 11:00 是 Q3 LONG,共同特征:

- CVD=18, CCI=10, Fib=18, PA=21
- trend=14.3,低于 `quadrant_trend_ema_min=15`
- RR=0,`OPPOSITION_STRUCTURE_TOO_CLOSE`
- score=81.3,低于 Q3 pending 默认 85
- 带 `TARGETED_LONG_OFFSET`,且 `SIDE_THRESHOLD_OFFSET_LONG_10.00`

因此它们没有成为 Q3->Q1 pending;其中 08-07 08:30 被 `REVERSAL_PIVOT_SCOUT` 反向成 SHORT。这里的错误不是没有记录 Q3,而是 Q3 长多候选被 “低 RR/阻力近 = 反转做空” 的规则解释了。

### 5.4 Q4: 组件不完整,但真实突破规则可能已可识别

BNB 大多数决策落在 Q4。8/8 下午启动初期,系统经常给出:

- CVD 强,但 PA=0/6/12 或 CCI=0
- RR 因 `OPPOSITION_STRUCTURE_TOO_CLOSE` 为 0
- `SIDE_THRESHOLD_OFFSET_LONG_10.00` 导致多头门槛更高

这说明当前象限评分是“形态质量评分”,不是“突破行为检测器”。一段刚从窄幅震荡突破的行情,在 PA/fib/CCI 还未全部转强前,可能已经具备可执行的突破特征。

## 6. 反事实候选规则: 已收盘突破确认

为了验证“策略能选出这段牛市”,我做了一个不改代码的反事实规则扫描。规则只使用已收盘 15m K 线:

1. 当前 bar 收盘价突破前 32 根已收盘 K 的收盘高点,且接近/突破前 32 根最高价。
2. 近 8 根收益或斜率为正。
3. 当前成交量大于前 32 根中位数的 1.15 倍。
4. 当前 K 线收盘在实体较强位置,无明显长上影假突破。
5. 下一根 15m 收盘守住突破位后,才在下一根收盘确认入场。

该规则在 BNB 窗口内触发的主要点:

| 触发收盘 | 确认入场 | 入场价 | vol 倍数 | 8根收益 | 到窗口高点 MFE | 后4h MAE |
|---|---|---:|---:|---:|---:|---:|
| 08-08 12:45 | 08-08 13:00 | 593.82 | 1.41 | +0.32% | +3.14% | -0.10% |
| 08-08 14:15 | 08-08 14:30 | 594.92 | 1.99 | +0.19% | +2.95% | -0.15% |
| 08-08 18:15 | 08-08 18:30 | 595.46 | 1.90 | +0.30% | +2.85% | -0.06% |
| 08-08 19:45 | 08-08 20:00 | 596.26 | 1.64 | +0.30% | +2.72% | -0.10% |
| 08-08 21:30 | 08-08 21:45 | 598.58 | 1.53 | +0.14% | +2.32% | ~0.00% |

但它也会触发失败/偏追点:

| 触发收盘 | 确认入场 | 问题 |
|---|---|---|
| 08-08 00:00 | 08-08 00:15 | 与实际 scout 多单类似,后续先回撤止损,说明仅靠突破不够 |
| 08-08 22:00 / 22:15 | 08-08 22:15 / 22:30 | 爆发后追高,剩余 MFE 低且 MAE 扩大 |
| 08-09 22:00 | 08-09 22:15 | 接近段尾,剩余空间不足 |

所以候选规则不能直接上线为主账本开仓。更合理的是把它作为 **二次确认 scout mission**:

```yaml
BNB_TREND_CONTINUATION_AFTER_PULLBACK:
  source: completed_15m_only
  side: LONG
  scope: scout_micro or q1_trend_launch_v2_shadow
  required:
    - previous early long-offset/probe failed or no position open
    - close breaks previous 32-bar close high
    - next closed bar holds breakout level
    - volume >= 1.15 * previous_32_bar_median_volume
    - close location >= 60% of candle range
    - upper wick <= max(1.2 * body, 0.15% price)
    - not in first 4 bars after a stop-loss on same symbol unless new 32-bar breakout occurs
  reject:
    - extreme_position_ratio > 0.90 unless breakout is post-pullback and not first spike
    - long_upper_wick_risk_active
    - two consecutive bars with close back below breakout level
    - daily trade budget blocks only main ledger, not shadow logging
  output:
    - create pending source with breakout_level, trigger_ts, confirm_ts, volume_mult
    - allow scout long; do not allow REVERSAL_PIVOT_SCOUT to flip this same sample
```

## 7. 为什么不能简单放宽现有参数

### 7.1 放宽 `long_threshold_offset` 风险大

BNB 的 08-08 00:00 样本分数 88.7,如果降低 long offset 或放宽主账本,会更容易把这个早追样本放大到主账本。但日志证明该样本很快止损,不是理想趋势入口。

### 7.2 放宽 RR 会扩大低质量追单

BNB 多数未入场样本 RR=0 或 2,常见原因是 `OPPOSITION_STRUCTURE_TOO_CLOSE`。08-09 18:00 的 Q1 LONG 就是典型:score 82.7,PA/Fib/CVD 都高,但 RR=0,extreme=0.966,随后系统还翻成空。放宽 RR 会把这类段尾/阻力贴脸样本放进来。

### 7.3 放宽 Q1 trend launch 会回到“泛 Q1 追单”

08-11 评审文档已经指出: q1_trend_launch 的问题从“不开仓”转成“低 RR Q1 追单负期望”。BNB 这个窗口再次证明,Q1 状态本身不是开仓理由,来源路径和二次确认才是关键。

## 8. 建议的下一步优化方案

### P0: 禁止反转任务抢占高分 LONG continuation

当前 `scout_micro_mission()` 中 `_reversal_pivot_scout_eligible()` 优先级最高。建议调整为:

- 如果 near-miss 是 LONG 且具备 continuation 标签或 breakout-confirmed source,不允许 `REVERSAL_PIVOT_SCOUT` 翻空。
- 对 BNB/SOL/DOGE/HYPE 等 targeted long symbols,`REVERSAL_PIVOT_SCOUT` 至少要 shadow-only,直到证明反向胜率和 PF 合格。

BNB 证据: 08-07 08:30 与 08-09 18:00 都把 LONG 候选翻成 SHORT,两笔 scout 空单均无趋势收益。

### P0: 给 Q1 trend launch v2 加 source requirement

不要让任意 Q1 near-miss 直接进主账本。只接受以下来源:

- Q2 pending -> Q1 confirmed
- Q3 pending -> Q1 confirmed
- LONG offset continuation -> breakout confirmed after pullback

并在 metadata 中写入:

- `source_quadrant`
- `source_reason`
- `breakout_level`
- `confirm_ts`
- `volume_mult`
- `previous_probe_outcome`

### P1: 新增 LONG_OFFSET_CONTINUATION_SCOUT / shadow

先不改主账本,把上面的已收盘突破确认规则作为 scout 或 shadow 记录。验收指标不能只看“有转化”,必须看:

- trade_count
- win_rate
- profit_factor
- expectancy
- max drawdown / consecutive stops
- MFE/MAE
- exposure
- tail loss

BNB 反事实显示 08-08 13:00/14:30/18:30/20:00/21:45 都能被这种规则捕获,且到窗口高点仍有约 +2.3%~+3.1% 空间。

### P1: 早追失败后的二次确认机制

08-08 00:00 的高分 LONG 先止损,但 12 小时后市场真正突破。当前同类失败可能触发冷却/预算/防守退出,导致后续没有重新入场。建议新增:

- 初始 long-offset stop 后,同方向禁开只阻止“立刻重试”,不阻止新 32-bar 突破确认。
- 二次确认开仓必须比止损点后的最高收盘更高,并有成交量确认。
- 二次确认使用更小仓位,直到 mission 样本 PF/MFE 通过。

### P2: 日志与审计增强

当前 pending 创建/过期没有独立日志事件,分析需要从 near_miss 和 state 反推。建议增加:

- `quadrant_pending_created.jsonl`
- `quadrant_pending_confirmed.jsonl`
- `quadrant_pending_expired.jsonl`
- 每条 scout rejection 输出 `mission_candidate_reasons`,而不是只有 `SCOUT_NO_MISSION`

## 9. 给 Claude 评审的问题

1. 是否同意 BNB 漏多根因不是“BNB 没被扫描到”,而是“高分 LONG 只进入 scout/mirror,主账本无 source-confirmed trend-launch 入口”?
2. 是否同意不应简单降低 `long_threshold_offset` 或 RR 门槛,因为 08-08 00:00 的早追样本已经实证止损?
3. 是否同意 `REVERSAL_PIVOT_SCOUT` 对 targeted long continuation 的优先级过高,应至少对 BNB 这类样本降级为 shadow-only?
4. `BNB_TREND_CONTINUATION_AFTER_PULLBACK` 的突破确认规则是否足够避免未来函数和同 bar 成交假设?
5. 对 08-08 13:00 / 14:30 / 18:30 / 20:00 / 21:45 这些反事实入场点,是否需要加入 1h/4h 同向过滤,还是先作为 scout shadow 收样本?
6. 最新 48H `q1_trend_launch=0` 是否说明 Task A 后仍缺少“source-confirmed conversion”的部署后验收项?

## 10. 本轮命令证据

```powershell
python scripts\fetch_symbol_klines.py --symbol BNBUSDT --interval 15m --days 10 --out-dir data\raw\binance_futures\bnb_20260813_analysis\BNBUSDT
python scripts\fetch_symbol_klines.py --symbol BNBUSDT --interval 1h --days 10 --out-dir data\raw\binance_futures\bnb_20260813_analysis\BNBUSDT
python scripts\fetch_symbol_klines.py --symbol BNBUSDT --interval 4h --days 10 --out-dir data\raw\binance_futures\bnb_20260813_analysis\BNBUSDT
python scripts\verify_q1_trend_launch_fix.py --mode online --log-root logs --hours 48 --config configs\entry_chain.dry_run_fib_pa_v1.json
python scripts\summarize_scout_trend_capture_diagnostics.py --log-root logs --start 2026-08-12 --end 2026-08-13
```

最新 48H scout trend-capture 摘要:

| 指标 | 值 |
|---|---:|
| closed_trades | 4 |
| win_rate | 0.25 |
| profit_factor | 0.0795 |
| net_pnl | -0.5776 |
| avg MFE | 0.7697R |
| >=1R rate | 25% |
| >=1.5R rate | 0% |

这进一步支持: 当前问题仍是入场池质量与转化机制,不是单纯出场参数。
