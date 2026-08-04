# AI300 四象限进攻策略 7/20 19:30 后 Dry-Run 执行效果归因报告

**提交对象:** Claude 评审
**分析窗口:** 2026-07-20 19:30:00 至 2026-07-21 18:45:07，北京时间。
**运行模式:** `DRY-RUN`，`target_tier=aggressive`，`exchange_mutation_enabled=False`。
**运行配置:** `configs/entry_chain.dry_run_fib_pa_v1.json`。
**数据来源:** `logs/2026-07/2026-07-20`、`logs/2026-07/2026-07-21` 下的 `decisions.jsonl`、`near_misses.jsonl`、`paper_trades.jsonl`、`scout_micro/paper_trades.jsonl`、`paper_ab/*/paper_trades.jsonl`、`summary.json`、`paper_summary.json`。
**重要口径:** 本报告仅基于 dry-run/paper ledger，不构成投资建议；日志按事件 Unix timestamp 过滤，不按目录名简单切分。

---

## 0. 结论摘要

1. **四象限策略只“部分发货”。** 当前代码已经给 `decision` 和 `near_miss` 增加 `quadrant`、`trend_structure_axis_ok`、`flow_momentum_axis_ok` 字段，并启用了 Q1/Q3 的 SCOUT/mirror 采样；但四象限没有接入主账本开仓、没有接入持仓 hold/平仓，也没有启用 Q1 主账本绿色通道。
2. **主账本完全没有被四象限撬动。** 窗口内 1,222 条决策，`NO_TRADE=1,120`、`WATCH=102`、`PROBE=0`、`DIRECT=0`；`risk_allowed=false` 共 1,222 条；主账本 `paper_trades.jsonl` 事件数为 0，`orders_submitted=0`。
3. **四象限改善的是“候选样本可见性”，不是“开仓转化率”。** Q1 有 166 条，Q3 有 222 条，near-miss 12 条只集中在 Q1/Q3；但这些只进入 SCOUT 或 mirror A/B，不会改变原始 `evaluate_entry_chain()` 的主交易结果。
4. **SCOUT 层有轻微采样效果，但没有形成正期望证据。** `Q1_RR_GAP_SCOUT` 开 3 笔、平 3 笔，1 胜 2 负，净 PnL `-0.006048 USDT`，接近打平但样本太少，且 2 笔为成本超时退出。
5. **Paper A/B 验证了 trend_capture 略优于 legacy，但两者仍为负。** A/B 各开 4 笔、平 4 笔；legacy 净 PnL `-0.659210`，trend_capture 净 PnL `-0.519556`，改善 `+0.139654`，主要来自 BCHUSDT 一笔赢家更早以更好价格退出。样本不足以证明稳定优势。
6. **主要堵点仍不是仓位/组合风控，而是准入层。** 最大拒绝来源为 `SIDE_THRESHOLD_OFFSET_LONG_10.00=543`、`SYMBOL_BLACKLISTED=179`、`SYMBOL_WATCH_ONLY=178`、`FIB_EXTENSION_EXHAUSTION_BLOCK=46`；Q1 内依然大量因为 LONG offset、symbol policy、RR gap 被截断。

---

## 1. 当前四象限如何实现

### 1.1 四象限定义

当前四象限不是基本面分区，而是**技术状态分区**。它只使用评分组件中的技术/资金流字段：

| 轴 | 通过条件 | 配置值 |
|---|---|---:|
| 趋势结构轴 | `trend_ema_context >= quadrant_trend_ema_min` 且 `price_action_structure >= quadrant_price_action_min` | `15.0`、`10.0` |
| 资金动能轴 | `flow_cvd_confirmation >= quadrant_flow_cvd_min` 且 `cci_momentum_quality >= quadrant_cci_min` | `14.0`、`7.0` |

四象限映射：

| 象限 | 趋势结构轴 | 资金动能轴 | 当前解释 |
|---|---|---|---|
| Q1 | 通过 | 通过 | 趋势结构与资金动能共振 |
| Q2 | 通过 | 不通过 | 结构已具备，资金/动能不足 |
| Q3 | 不通过 | 通过 | 资金/动能活跃，结构未确认 |
| Q4 | 不通过 | 不通过 | 结构和动能均不足 |

相关实现位置：

| 文件/函数 | 当前作用 |
|---|---|
| `scripts/run_live_dry_run.py::quadrant_axes()` | 计算趋势结构轴、资金动能轴 |
| `scripts/run_live_dry_run.py::decision_quadrant()` | 输出 `Q1/Q2/Q3/Q4` |
| `scripts/run_live_dry_run.py::annotate_quadrant()` | 给 decision 和 near-miss 增加象限字段 |
| `src/signals/entry_chain_scoring.py::FIB_PA_WEIGHTS` | 定义四象限依赖的加权组件 |

### 1.2 当前权重评分

当前启用 `use_fib_pa_architecture=true`，总分按以下 6 个组件加权：

| 组件 | 权重 |
|---|---:|
| `trend_ema_context` | 20 |
| `flow_cvd_confirmation` | 18 |
| `cci_momentum_quality` | 14 |
| `price_action_structure` | 22 |
| `fibonacci_location` | 18 |
| `risk_reward_geometry` | 8 |
| **合计** | **100** |

四象限只读取其中 4 个组件：`trend_ema_context`、`price_action_structure`、`flow_cvd_confirmation`、`cci_momentum_quality`。`fibonacci_location` 和 `risk_reward_geometry` 不参与象限划分，但仍参与总分和 PROBE/DIRECT 准入。

---

## 2. 四象限是否真正接入交易链路

### 2.1 主账本开仓链路

主账本实际链路为：

`evaluate_entry_chain(context, config)`
→ `apply_dry_run_decision_controls(...)`
→ `decision_payload = annotate_quadrant(decision_payload, config)`
→ `build_live_entry_order_draft(decision, ...)`
→ `paper.on_decision(...)`

关键点：

| 检查项 | 当前状态 |
|---|---|
| `annotate_quadrant()` 是否改变原始 `decision.action` | 否 |
| `build_live_entry_order_draft()` 是否读取 `quadrant` | 否 |
| `PaperTradingLedger.on_decision()` 是否读取 `quadrant` | 否 |
| `dry_run_q1_green_channel_enabled` 是否有执行分支 | 未发现执行分支 |
| 配置中 `dry_run_q1_green_channel_enabled` | `false` |

因此，**四象限没有真正进入主账本开仓链路**。主账本仍只接受原始 `decision.action in {"PROBE","DIRECT"}` 且 `risk_allowed=true` 的信号。

### 2.2 主账本出场/持仓链路

纸面出场由 `PaperTradingLedger._update_position()` 管理，逻辑包括：

| 出场类型 | 当前依据 |
|---|---|
| 初始止损 | K 线 high/low 触达 stop |
| TP 分批止盈 | K 线 high/low 触达 TP |
| 成本/保本止损 | TP 后或成本超时规则 |
| 最大持仓 bars | `MAX_HOLD_BARS` |
| trend_capture | `exit_config.mode`、`trend_trigger_r`、trailing 参数 |

当前未读取 `decision_payload["quadrant"]`，所以用户要求的：

- 持多时 Q1/Q2/Q3/Q4 下是否 hold；
- 持空时 Q1/Q2/Q3/Q4 下是否 hold；
- 拐点到来后平多/平空；

这些都**没有实盘/纸面出场实现**。

### 2.3 SCOUT 与 mirror A/B 链路

四象限当前主要影响两处：

| 链路 | 是否使用四象限 | 说明 |
|---|---|---|
| `Q1_RR_GAP_SCOUT` | 是 | Q1、score 达标、RR gap reason，可开 SCOUT 微仓 |
| `Q3_TO_Q1_CONFIRMATION` | 是 | Q3 near-miss 进入内存 pending，后续同标的同方向转 Q1 后可确认 |
| `mirror_ab` | 弱相关/不直接使用 | 只看 near-miss 分数、方向、价格和 allowed reasons，不直接读 `quadrant` |
| 主账本 | 否 | 不读象限 |
| 主账本出场 | 否 | 不读象限 |

---

## 3. 7/20 19:30 后执行统计

### 3.1 决策动作分布

| 指标 | 数值 |
|---|---:|
| 决策总数 | 1,222 |
| NO_TRADE | 1,120 |
| WATCH | 102 |
| PROBE | 0 |
| DIRECT | 0 |
| `risk_allowed=false` | 1,222 |
| 主账本交易事件 | 0 |
| `orders_submitted` | 0 |

窗口内没有任何主账本 `PAPER_OPEN`、`PAPER_REDUCE`、`PAPER_CLOSE`。

### 3.2 四象限分布

| 象限 | 总数 | 占比 | NO_TRADE | WATCH | WATCH 率 | score >=82 | score >=85 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Q1 | 166 | 13.58% | 111 | 55 | 33.13% | 8 | 6 |
| Q2 | 189 | 15.47% | 177 | 12 | 6.35% | 0 | 0 |
| Q3 | 222 | 18.17% | 191 | 31 | 13.96% | 4 | 3 |
| Q4 | 645 | 52.78% | 641 | 4 | 0.62% | 0 | 0 |

解释：

- Q1/Q3 能把强候选分出来，near-miss 也只出现在 Q1/Q3；
- 但 Q1 并没有成为主账本开仓绿色通道；
- Q2/Q4 基本只是审计标签，没有交易行为。

### 3.3 各象限平均组件分

| 象限 | trend EMA | PA 结构 | CVD | CCI | Fib | RR |
|---|---:|---:|---:|---:|---:|---:|
| Q1 | 17.29 | 17.28 | 18.00 | 9.40 | 8.36 | 1.07 |
| Q2 | 17.31 | 16.70 | 14.04 | 1.86 | 8.27 | 1.47 |
| Q3 | 15.15 | 4.73 | 18.00 | 9.57 | 11.00 | 0.91 |
| Q4 | 13.14 | 3.38 | 10.59 | 0.97 | 11.55 | 1.25 |

关键观察：

- Q1 的结构和动能确实强，但 `risk_reward_geometry` 平均只有 `1.07/8`；
- Q3 的资金动能强，但 PA 结构平均只有 `4.73/22`；
- Q2 的结构强，但 CCI 极低；
- 四象限没有解决 RR 几何低的问题。

### 3.4 near-miss 结构

| 指标 | 数值 |
|---|---:|
| near-miss 总数 | 12 |
| WATCH | 9 |
| NO_TRADE | 3 |
| Q1 | 8 |
| Q3 | 4 |
| score >=80 | 12 |
| score >=85 | 9 |

near-miss 主因：

| 主因 | 次数 |
|---|---:|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 4 |
| `SYMBOL_BLACKLISTED` | 3 |
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.5` | 2 |
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0` | 2 |
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 1 |

按象限看：

| 象限 | near-miss 数 | 主要原因 |
|---|---:|---|
| Q1 | 8 | LONG offset 3、黑名单 3、RR gap 2 |
| Q3 | 4 | RR gap 3、LONG offset 1 |
| Q2 | 0 | 无 |
| Q4 | 0 | 无 |

---

## 4. SCOUT 与 A/B 账本表现

### 4.1 主账本

| 指标 | 数值 |
|---|---:|
| 开仓 | 0 |
| 平仓 | 0 |
| PnL | 0 |
| 结论 | 四象限没有推动主账本产生样本 |

### 4.2 SCOUT 微仓

| 指标 | 数值 |
|---|---:|
| trade events | 7 |
| open / reduce / close | 3 / 1 / 3 |
| mission | `Q1_RR_GAP_SCOUT` |
| 胜 / 负 | 1 / 2 |
| 净 PnL | `-0.006048 USDT` |
| 最大 favorable R | `1.791050` |

SCOUT 明细：

| 时间(BJT) | 标的 | 方向 | 事件/原因 | PnL | max favorable R |
|---|---|---|---|---:|---:|
| 07-20 23:00 | BCHUSDT | LONG | OPEN | -0.050000 | 0.0000 |
| 07-20 23:45 | BCHUSDT | LONG | TP1_HIT | +0.151543 | 1.7911 |
| 07-21 00:00 | BCHUSDT | LONG | BREAKEVEN_STOP_HIT | +0.139624 | 1.7911 |
| 07-21 06:00 | DOGEUSDT | SHORT | OPEN | -0.050000 | 0.0000 |
| 07-21 08:00 | DOGEUSDT | SHORT | COST_BREAKEVEN_TIMEOUT | -0.001327 | 0.8330 |
| 07-21 13:30 | CCUSDT | LONG | OPEN | -0.050000 | 0.0000 |
| 07-21 15:30 | CCUSDT | LONG | COST_BREAKEVEN_TIMEOUT | -0.145889 | 0.1120 |

判断：

- `Q1_RR_GAP_SCOUT` 能开仓，说明四象限在 SCOUT 层有实际作用；
- 但 3 笔样本太少，且净 PnL 基本打平，不足以证明 Q1/RR gap 是正期望；
- DOGE 到过 `0.833R` 但未达 1R，CC 几乎没有有利波动，BCH 是唯一有效样本。

### 4.3 Paper Exit A/B

| 账本 | open | reduce | close | 胜/负 | 净 PnL | Profit Factor | 平均盈利 | 平均亏损 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| legacy | 4 | 1 | 4 | 1/3 | -0.659210 | 0.1334 | 0.1015 | 0.2536 |
| trend_capture | 4 | 1 | 4 | 1/3 | -0.519556 | 0.3170 | 0.2412 | 0.2536 |

主要差异：

| 标的 | 方向 | legacy 结果 | trend_capture 结果 | 差异 |
|---|---|---:|---:|---:|
| BCHUSDT | LONG | +0.101513 | +0.241167 | +0.139654 |

判断：

- trend_capture 在本窗口内优于 legacy；
- 但总样本只有 4 笔，且优势几乎完全来自 1 笔 BCH；
- 两个 A/B 账本仍均为负 PnL，不能证明出场架构已经解决盈利问题。

---

## 5. 四象限按“持仓/空仓/技术动作”的当前状态

### 5.1 Q1：趋势结构 + 资金动能共振

| 状态 | 用户期望动作 | 当前实现 |
|---|---|---|
| 空仓 | 可开多/开空，或等待小拐点后开仓 | 主账本不开；只有 Q1/RR gap 可进 SCOUT；mirror A/B 可采样 |
| 持多 | hold 或趋势延续持有 | 未实现，出场不读 Q1 |
| 持空 | 若 Q1 方向反向应平空或保护 | 未实现，出场不读 Q1 |

### 5.2 Q2：结构通过，资金/动能不足

| 状态 | 用户期望动作 | 当前实现 |
|---|---|---|
| 空仓 | 等资金/动能拐点后开多/开空 | 未实现 pending |
| 持多 | 可 hold，但需防动能不足回吐 | 未实现 |
| 持空 | 结构若反向可能减仓/平仓 | 未实现 |

### 5.3 Q3：资金/动能通过，结构不足

| 状态 | 用户期望动作 | 当前实现 |
|---|---|---|
| 空仓 | 等结构拐点转 Q1 后开仓 | 部分实现：内存 pending + Q3_TO_Q1_CONFIRMATION，但本窗口无该 mission 成交 |
| 持多 | 若 Q3 对多头不利，应减仓/平多 | 未实现 |
| 持空 | 若 Q3 对空头不利，应减仓/平空 | 未实现 |

### 5.4 Q4：结构与资金动能均不足

| 状态 | 用户期望动作 | 当前实现 |
|---|---|---|
| 空仓 | 继续空仓 | 间接实现：分数低，基本不会开仓 |
| 持多 | 弱势持续时平多或收紧止损 | 未实现 |
| 持空 | 弱势持续时是否 hold 取决于方向 | 未实现 |

---

## 6. 主要归因

### 6.1 不是“四象限分类失效”，而是“四象限没有控制主链路”

从日志看，四象限分类是存在的：

- Q1/Q2/Q3/Q4 都有输出；
- near-miss 集中在 Q1/Q3；
- SCOUT 产生了 `Q1_RR_GAP_SCOUT` 样本；
- summary 输出了象限阈值和实验开关。

但主账本开仓链路仍只看 `decision.action` 与 `risk_allowed`。窗口内 `risk_allowed=false` 全量成立，因此主账本无论 Q1 有多少，都不会开仓。

### 6.2 Q1 的问题是 RR 几何和政策阻断

Q1 平均分项显示：

- `trend_ema_context=17.29/20`；
- `price_action_structure=17.28/22`；
- `flow_cvd_confirmation=18.00/18`；
- `cci_momentum_quality=9.40/14`；
- 但 `risk_reward_geometry=1.07/8`。

这说明 Q1 把“趋势/动能共振”找出来了，但这些机会的静态 RR 很差，或存在近端反向结构压制。当前策略仍把 RR gap 当作硬门槛，所以 Q1 无法自然转化为 PROBE/DIRECT。

### 6.3 LONG 方向仍被系统性加严

窗口内最大拒绝原因是 `SIDE_THRESHOLD_OFFSET_LONG_10.00=543`。配置中：

- 全局 `long_threshold_offset=10.0`；
- `probe_conditions.long_threshold_offset=7.0`；
- `short_threshold_offset=0.0`。

结果是 LONG 方向比 SHORT 更难进入 WATCH/PROBE/DIRECT。若市场窗口偏多头，四象限 Q1 也会被 LONG offset 截断。

### 6.4 Q3-to-Q1 设计正确，但当前样本链条没打通

Q3 有 222 条，near-miss 有 4 条，但本窗口 SCOUT 没有 `Q3_TO_Q1_CONFIRMATION` 成交。可能原因：

- Q3 near-miss 数量少；
- 需要同标的同方向在 3 根 15m K 内转 Q1；
- pending 状态目前在内存中，进程重启会丢；
- 确认后仍只进入 SCOUT，不进入主账本。

### 6.5 出场优化还不能拯救低质量入场

trend_capture 相对 legacy 改善了 `+0.139654 USDT`，但两个账本仍为负。原因是入场样本本身多为 RR gap near-miss 和非主账本强信号；出场只能改善赢家保留，无法把低胜率、低 RR 的入口直接变成正期望。

---

## 7. 对 Claude 的评审问题

1. 当前四象限应继续定位为“技术状态四象限”，还是必须重构为用户要求的“基本面四象限”？如果是基本面四象限，请明确可实时执行的数据字段，避免未来函数。
2. Q1 是否应接入主账本 dry-run 绿色通道？若接入，建议是仅降低 RR 门槛、仅允许 reduced notional PROBE，还是继续只放 SCOUT？
3. Q1 平均 RR 分只有 `1.07/8`。是否应把 `risk_reward_geometry` 从硬门槛改为 Q1 内的仓位折扣因子，还是必须坚持硬门槛？
4. `SIDE_THRESHOLD_OFFSET_LONG_10.00` 是否过度压制多头？是否应只在 Q1 将 LONG offset 从 10 降到 7，或仅在 SCOUT 中验证？
5. Q2 是否应该实现 pending 状态：结构达标但资金/动能不足时，等待 CVD/CCI 拐点后再开仓？
6. Q3-to-Q1 pending 是否需要落盘持久化？当前内存状态对 VPS 重启敏感，可能错过确认链路。
7. Q4 是否应接入持仓管理，例如连续 N 根 Q4 时收紧止损、禁止加仓或主动平仓？
8. mirror A/B 当前不直接读 quadrant。是否应该把 A/B 样本按 Q1/Q2/Q3/Q4 分桶，分别比较 legacy 与 trend_capture？
9. 当前 SCOUT `Q1_RR_GAP_SCOUT` 3 笔基本打平。是否应扩大样本，还是先收紧为 `Q1 + PA>=18 + Fib>=15 + CVD=18`？
10. 若目标是“能开仓、能盈利”，Claude 是否建议优先改：主账本 Q1 绿色通道、SCOUT mission 扩样、LONG offset、RR 几何，还是出场 trend_trigger 参数？

---

## 8. 建议下一步

### 8.1 先承认当前发货边界

当前四象限已经完成：

- 日志标注；
- near-miss 分层；
- `Q1_RR_GAP_SCOUT`；
- Q3-to-Q1 pending 机制；
- mirror A/B 样本池；
- summary assumptions 输出。

当前四象限尚未完成：

- 主账本 Q1 绿色通道；
- Q2 pending；
- Q4 持仓退出；
- 四象限驱动的 hold/开多/开空/平多/平空状态机；
- mirror A/B 按象限分桶报告。

### 8.2 最小可验证优化方向

建议不要直接放开主账本全局开仓，而是执行三步：

1. **Q1 reduced-notional 主账本 paper 绿色通道，仅 dry-run。**
   条件建议：`quadrant=Q1`、`score>=85`、非黑名单、非 observation-only、`risk_reward_geometry>=1.0/8`、`price_action_structure>=18/22`、`flow_cvd_confirmation=18/18`。仓位为普通 PROBE 的 25%-50%。

2. **A/B 样本按象限分桶。**
   每笔 mirror A/B 写入 `source_quadrant`，报告按 Q1/Q2/Q3/Q4 输出 win rate、PF、平均 R、MFE/MAE。

3. **Q4 出场保护先只做观察报告。**
   对历史持仓回放：如果持仓后连续 2-3 根进入 Q4，比较“原出场”与“Q4 收紧/退出”的 PnL，确认无误后再接入纸面出场。

---

## 9. 最终判断

**四象限策略在 2026-07-20 19:30 之后确实开始产生观测和 SCOUT 样本，但没有真正对主账本开仓和持仓出场发挥作用。**

当前结果可以概括为：

- 能分类；
- 能记录；
- 能让少量 Q1/RR gap 进入 SCOUT；
- 能让 near-miss 进入 mirror A/B；
- 不能让主账本开仓；
- 不能按象限 hold；
- 不能按象限平多/平空；
- 尚未证明盈利能力。

因此，今天“还是没有看到好效果”的主因不是四象限分类本身完全错误，而是四象限仍停留在审计/侦察层，没有接入真正决定收益的两条链路：**主账本准入**与**持仓退出**。
