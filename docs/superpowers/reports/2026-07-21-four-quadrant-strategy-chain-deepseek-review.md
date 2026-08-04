# AI300 当前四象限策略链路、门槛、仓位与风控说明

**提交对象:** DeepSeek 评审
**分析时间:** 2026-07-21，北京时间
**日志口径:** 本地 `logs/2026-07/2026-07-21` 当前可读原始日志覆盖约北京时间 08:00:05 至 10:30:05；`runtime.out.00.log` 首行显示 UTC 00:00:05，即北京时间 08:00:05。若 VPS 上存在 00:00-07:59 北京时间日志但尚未同步到本机，本报告未包含该段原始决策。
**运行口径:** 今日 runtime header 显示 `config=configs/entry_chain.dry_run_fib_pa_v1.json`、`target_tier=aggressive`、`market_data_source=public-binance`、`exchange_mutation_enabled=False`。
**重要发现:** `deploy/systemd/ai300-dry-run.service` 与 `deploy/systemd/aibot.service` 仍写着 `configs/entry_chain.dry_run_highest_win.json`，但今日日志实际显示使用 `entry_chain.dry_run_fib_pa_v1.json`。请优先核对 VPS 服务文件与启动命令，避免本地部署文件、VPS 实际运行参数和日志口径不一致。

---

## 0. 结论摘要

1. 当前所谓“四象限”并不是真正的基本面四象限。代码中没有链上、新闻、财报、宏观事件等基本面因子参与 Q1-Q4 分类；实际是用 Fib/PA 架构下的技术评分点数，把市场压成两个轴：`趋势/结构轴` 与 `资金/动能轴`。
2. 四象限当前主要是 dry-run 实验标签和 SCOUT/mirror A/B 采样条件，不是主账本开仓/平仓的核心驱动。主账本仍由 `evaluate_entry_chain()` 的总分、组件门槛、硬阻断、流动性、仓位与 dry-run 降级控制决定。
3. Q1 目前没有主账本“绿色通道”。配置里 `dry_run_q1_green_channel_enabled=false`，且代码中没有看到该字段实际改变主账本开仓链路。因此 Q1 只会在原有 PROBE/DIRECT 链路自然通过时开主账本；若被 RR gap 拦截，最多进入 SCOUT 或 mirror A/B。
4. Q3 有“等待转 Q1”实验，但只服务 SCOUT 微仓。Q3 near-miss 满足 `score>=85` 且 `CVD>=16` 后进入内存 pending，3 根 15m K 线内若同标的同方向转 Q1 且 PA>=15，才打 `Q3_TO_Q1_CONFIRMED` 并进入 SCOUT。
5. Q2/Q4 当前没有独立的象限开仓、持仓或平仓规则。Q2 不会自动等待动能拐点，Q4 也不会自动平多/平空；持仓出场仍由纸面账本的止损、TP、成本保本超时、最大持仓 bar 和 trend_capture trailing 决定。
6. 今日可读原始日志中：143 条决策，`NO_TRADE=129`、`WATCH=14`、主账本 `PROBE=0`、`DIRECT=0`。象限分布为 `Q1=10`、`Q2=16`、`Q3=29`、`Q4=88`。主账本无新开仓；SCOUT 只有 1 条 Q1 RR gap 旧仓平仓，`COST_BREAKEVEN_TIMEOUT`，PnL `-0.0513 USDT`；mirror A/B 开了 2 个 SHORT 样本。

---

## 1. 当前四象限是如何定义的

实现位置：

| 模块 | 作用 |
|---|---|
| `src/signals/entry_chain_config.py` | 定义四象限阈值与实验开关 |
| `scripts/run_live_dry_run.py::quadrant_axes()` | 计算两个轴是否通过 |
| `scripts/run_live_dry_run.py::decision_quadrant()` | 输出 `Q1/Q2/Q3/Q4` |
| `scripts/run_live_dry_run.py::annotate_quadrant()` | 给 decision 和 near-miss payload 增加象限字段 |
| `src/signals/entry_chain_scoring.py::FIB_PA_WEIGHTS` | 定义四象限所依赖的加权分值 |

当前使用的是加权后的 `component_points`，不是 0-1 原始分：

| 组件 | 权重/满分 |
|---|---:|
| `trend_ema_context` | 20 |
| `flow_cvd_confirmation` | 18 |
| `cci_momentum_quality` | 14 |
| `price_action_structure` | 22 |
| `fibonacci_location` | 18 |
| `risk_reward_geometry` | 8 |
| 合计 | 100 |

两个象限轴：

| 轴 | 通过条件 |
|---|---|
| 趋势/结构轴 `trend_structure_axis_ok` | `trend_ema_context >= 15` 且 `price_action_structure >= 10` |
| 资金/动能轴 `flow_momentum_axis_ok` | `flow_cvd_confirmation >= 14` 且 `cci_momentum_quality >= 7` |

四象限映射：

| 象限 | 趋势/结构轴 | 资金/动能轴 | 当前含义 |
|---|---|---|---|
| Q1 | 通过 | 通过 | 趋势结构与资金动能共振 |
| Q2 | 通过 | 不通过 | 结构存在，但资金/动能未确认 |
| Q3 | 不通过 | 通过 | 资金/动能活跃，但趋势结构尚未确认 |
| Q4 | 不通过 | 不通过 | 结构与动能均不足 |

**评审注意:** 这里的“基本面”只是用户策略描述中的概念。当前代码实际没有基本面数据层，只有 market cap rank 宇宙筛选、黑名单/观察名单、技术评分与资金流近似。

---

## 2. 每个象限当前如何处理空仓与持仓

### 2.1 Q1：趋势结构 + 资金动能共振

**空仓时当前处理:**

| 账本 | 当前行为 |
|---|---|
| 主账本 | 不因 Q1 自动开仓；仍走普通 PROBE/DIRECT 链路 |
| SCOUT 微仓 | 若是 Q1、`score>=82`、方向为 LONG/SHORT、拒绝原因含 `_BELOW_RISK_REWARD_GEOMETRY`，可进入 `Q1_RR_GAP_SCOUT` |
| mirror A/B | 若 `score>=85` 且 near-miss reason 命中允许列表，可在 legacy/trend_capture 两套 A/B 账本开镜像样本 |

**持仓时当前处理:**

| 持仓方向 | 当前代码行为 |
|---|---|
| 已持多 | Q1 不触发额外加仓或 hold 特权；继续按纸面出场规则管理 |
| 已持空 | Q1 不触发额外加仓或强平；继续按纸面出场规则管理 |

**技术动作解释:**

| 目标动作 | 当前是否由 Q1 直接触发 | 实际触发条件 |
|---|---|---|
| hold | 否 | 未触发止损/TP/超时/最大持仓 bar 时自然继续持有 |
| 开多 | 否 | 主链路自然输出 LONG PROBE/DIRECT，或 SCOUT/mirror 条件满足 |
| 开空 | 否 | 主链路自然输出 SHORT PROBE/DIRECT，或 SCOUT/mirror 条件满足 |
| 平多 | 否 | 纸面账本止损、TP、成本保本超时、最大持仓 bar |
| 平空 | 否 | 同上 |

**关键缺口:** Q1 在当前实现中没有成为主账本的开仓绿色通道。`dry_run_q1_green_channel_enabled=false`，且当前代码没有看到该字段实际改变主账本决策。

### 2.2 Q2：趋势结构通过，资金动能不足

**空仓时当前处理:**

| 账本 | 当前行为 |
|---|---|
| 主账本 | 不因 Q2 降级或等待动能；仍走普通评分链路 |
| SCOUT 微仓 | 没有 Q2 专属 mission |
| mirror A/B | 不直接看 Q2，只看 `score>=85` 和 allowed reason |

**持仓时当前处理:**

| 持仓方向 | 当前代码行为 |
|---|---|
| 已持多 | Q2 不触发“等待资金拐点”或减仓 |
| 已持空 | Q2 不触发“趋势结构反向”平仓 |

**技术动作解释:**

| 目标动作 | 当前是否由 Q2 直接触发 | 实际触发条件 |
|---|---|---|
| hold | 否 | 持仓未碰出场条件 |
| 拐点到来后开多 | 未实现 | 没有 Q2 pending 或二次确认逻辑 |
| 拐点到来后开空 | 未实现 | 没有 Q2 pending 或二次确认逻辑 |
| 平多/平空 | 未实现 | 出场不读取 `quadrant` |

**关键缺口:** Q2 只是标签，没有被实现为“结构已好，等资金/动能确认再开仓”的状态机。

### 2.3 Q3：资金动能通过，趋势结构不足

**空仓时当前处理:**

| 账本 | 当前行为 |
|---|---|
| 主账本 | 不因 Q3 开仓 |
| SCOUT 微仓 | 可触发 Q3 pending；确认转 Q1 后进入 `Q3_TO_Q1_CONFIRMATION` |
| mirror A/B | 不直接看 Q3，只看 `score>=85` 和 allowed reason |

Q3 pending 条件：

| 条件 | 阈值 |
|---|---:|
| `scout_micro_q3_to_q1_enabled` | true |
| 当前象限 | Q3 |
| `score` | >= 85 |
| `flow_cvd_confirmation` 点数 | >= 16 |
| 方向 | LONG 或 SHORT |
| 有效期 | 3 根 15m K 线，即约 45 分钟 |

Q3 转 Q1 确认条件：

| 条件 | 阈值 |
|---|---:|
| 同 symbol | 必须 |
| 同 side | 必须 |
| 未过期 | 必须 |
| 当前象限 | Q1 |
| `price_action_structure` 点数 | >= 15 |
| 确认标签 | `Q3_TO_Q1_CONFIRMED` |

**持仓时当前处理:**

| 持仓方向 | 当前代码行为 |
|---|---|
| 已持多 | Q3 不触发减仓或保护 |
| 已持空 | Q3 不触发减仓或保护 |

**关键缺口:** Q3 pending 是内存状态，进程重启会丢；当前未持久化。并且 Q3-to-Q1 只进入 SCOUT，不进入主账本。

### 2.4 Q4：趋势结构与资金动能均不足

**空仓时当前处理:**

| 账本 | 当前行为 |
|---|---|
| 主账本 | 没有 Q4 专属硬阻断，但通常分数低，难以通过普通链路 |
| SCOUT 微仓 | 没有 Q4 专属 mission |
| mirror A/B | 理论上若高分且 reason 命中仍可能开镜像样本，但今日 Q4 主要是低分 NO_TRADE |

**持仓时当前处理:**

| 持仓方向 | 当前代码行为 |
|---|---|
| 已持多 | Q4 不触发主动平多 |
| 已持空 | Q4 不触发主动平空 |

**关键缺口:** 用户要求中的“Q4 空仓/退出弱持仓”目前没有代码实现；出场层完全不读取 `quadrant`。

---

## 3. 当前主账本开仓链路

入口链路：

1. `scripts/run_live_dry_run.py` 加载 `EntryChainConfig`。
2. `build_context()` 从 public Binance K 线构造 `EntryChainContext`。
3. `direction_from_history()` 先用 1h 最近 4 根 K 线判断方向：涨幅 > 0.3% 为 LONG，跌幅 < -0.3% 为 SHORT；否则用最近 15m 收盘相对 4 根前收盘兜底。
4. `component_scores()` 生成 Fib/PA 架构分数。
5. `evaluate_entry_chain()` 计算总分、硬阻断、降级与仓位建议。
6. `apply_dry_run_decision_controls()` 做 dry-run 层降级，例如观察名单、冷却、组合熔断、弱边缘无盈利历史。
7. `build_live_entry_order_draft()` 只有在 `action in {"PROBE","DIRECT"}` 且 `risk_allowed=True` 时生成 order draft。
8. 当前是 dry-run，`orders_submitted=0`，不会提交交易所。

主账本动作门槛，按今日实际 Fib/PA 配置：

| 方向 | DIRECT 初始门槛 | PROBE 初始门槛 | WATCH 初始门槛 |
|---|---:|---:|---:|
| LONG | 92 | 77 | 72 |
| SHORT | 82 | 70 | 62 |

来源：

| 配置项 | 值 |
|---|---:|
| `direct_threshold` | 82 |
| `probe_threshold` | 70 |
| `watch_threshold` | 62 |
| global `long_threshold_offset` | 10 |
| `probe_conditions.long_threshold_offset` | 7 |
| `short_threshold_offset` | 0 |

DIRECT 二级组件门：

| 组件 | 最低点数 |
|---|---:|
| `price_action_structure` | 6 |
| `fibonacci_location` | 9 |
| `risk_reward_geometry` | 4 |

PROBE 二级组件门：

| 条件 | 阈值 |
|---|---:|
| `probe_conditions.enabled` | true |
| `min_score` | 72 |
| `min_fib_score` | 12 |
| `min_pa_score` | 10 |
| `min_rr_score` | 4 |
| `trend_or_cci_min_ema_score` | 10 |
| `trend_or_cci_min_cci_score` | 9 |
| `low_score_quality_veto_score` | 75 |
| `low_score_quality_min_ema_score` | 10 |
| `low_score_quality_min_cci_score` | 7 |

Elite PROBE 门：

| 条件 | 阈值 |
|---|---:|
| `elite_probe_enabled` | true |
| `elite_probe_min_score` | 75 |
| 强结构 PA | >= 18 |
| 强结构 Fib | >= 15 |
| 或趋势结构 EMA | >= 15 |
| 或 PA + Fib | >= 30 |

High beta 额外门，适用于 `HYPEUSDT/LABUSDT/CCUSDT`：

| 条件 | 阈值 |
|---|---:|
| `high_beta_min_pa_score` | 12 |
| `high_beta_min_rr_score` | 5 |
| `high_beta_min_cci_score` | 9 |
| `high_beta_min_ema_score` | 12 |
| DIRECT 行为 | 强制降为 PROBE |

---

## 4. SCOUT 与 mirror A/B 开仓链路

### 4.1 SCOUT 微仓通用准入

SCOUT 只读取 near-miss，不读取主账本已批准订单。

| 条件 | 当前值/逻辑 |
|---|---|
| symbol | 必须在 `scout_micro_symbols` 或已有 SCOUT 持仓 |
| data health | 必须为 `OK` |
| 同 symbol SCOUT 持仓 | 不允许重复开 |
| near-miss | 必须存在 |
| near-miss score | >= `scout_micro_min_score=82` |
| side | LONG 或 SHORT |
| entry price | > 0 |
| mission | 必须能被 `scout_micro_mission()` 分类 |
| same-side cooldown | 2 小时 |
| initial-stop cooldown | 6 小时 |
| notional | 50 USDT |
| leverage | 1x |
| exit mode | `trend_capture` |

SCOUT missions：

| mission | 当前准入 |
|---|---|
| `Q1_RR_GAP_SCOUT` | Q1、score>=82、reason 含 `_BELOW_RISK_REWARD_GEOMETRY` |
| `Q3_TO_Q1_CONFIRMATION` | 有 `Q3_TO_Q1_CONFIRMED` 标签 |
| `HIGH_SCORE_LONG_OFFSET_PROBE` | LONG、指定 scout target symbol、reason 含 `SIDE_THRESHOLD_OFFSET_LONG_10.00` 或 tag `TARGETED_LONG_OFFSET`、score>=85、PA>=18、Fib>=15、CVD>=14、RR>=2；high beta 名义本金减半 |
| `FIB_CONTINUATION_SCOUT` | reason 含 `FIB_EXTENSION_EXHAUSTION_BLOCK`、score>=82、EMA>=16、CVD>=14、PA>=18 |
| `WATCH_ONLY_SYMBOL_PROMOTION_TEST` | symbol 在 watch_only、reason 含 `SYMBOL_WATCH_ONLY`、score>=87，且 Fib/PA/RR 达 PROBE 最低门 |
| `SCOUT_ONLY_HIGH_SCORE` | symbol 在 scout_only、score>=85、Fib>=12、PA>=10、RR>=4 |

### 4.2 mirror A/B 样本池

mirror A/B 不影响主账本，只在 `paper_ab/legacy` 与 `paper_ab/trend_capture` 两套账本开相同入场样本。

| 条件 | 当前值/逻辑 |
|---|---|
| `mirror_ab_enabled` | true |
| score | >= 85 |
| side | LONG 或 SHORT |
| entry price | > 0 |
| allowed reasons | `BELOW_RISK_REWARD_GEOMETRY`、`SYMBOL_WATCH_ONLY`、`SIDE_THRESHOLD_OFFSET_LONG`、`FIB_EXTENSION_EXHAUSTION_BLOCK` |
| 同 symbol A/B 持仓 | 任一 A/B 账本已有则不开 |
| notional | 50 USDT |
| leverage | 1x |

---

## 5. 仓位管理

### 5.1 主账本名义本金

`evaluate_entry_chain()` 给出 `notional_hint`：

```text
stop_pct = context.stop_pct 或 clamp(atr_pct * 1.5, min_stop_pct=0.005, max_stop_pct=0.04)

DIRECT:
  exposure_pct = 0.20 + min(0.10, (score - direct_threshold) / 100)

PROBE:
  exposure_pct = 0.20 * probe_fraction(0.25) = 0.05

score_based = account_equity * exposure_pct
risk_based = account_equity * risk_pct / stop_pct
cap_remaining = (max_symbol_exposure_pct - current_symbol_exposure_pct) * account_equity
notional_hint = min(score_based, risk_based, cap_remaining)
```

当前 Fib/PA 配置：

| 参数 | 值 |
|---|---:|
| `direct_risk_pct` | 0.006 |
| `probe_risk_pct` | 0.0025 |
| `max_total_exposure_pct` | 1.6 |
| `max_same_direction_exposure_pct` | 1.1 |
| `margin_buffer_pct` | 0.30 |
| `max_active_symbols` | 8 |
| `max_symbol_trades_per_day` | 2 |
| `daily_max_trades_base` | 16 |
| `min_daily_trades` | 2 |

按 symbol bucket 的单标的上限：

| bucket | symbols | 上限 |
|---|---|---:|
| large cap | BTCUSDT, ETHUSDT, BNBUSDT | 30% equity |
| mainstream | SOLUSDT, ADAUSDT, LINKUSDT，以及默认其他 | 20% equity |
| high beta | HYPEUSDT, LABUSDT, CCUSDT | 10% equity |

### 5.2 杠杆选择

| 条件 | 杠杆 |
|---|---:|
| 非 PROBE/DIRECT | 0 |
| rolling Sharpe < 0 | 2x |
| ATR% > 3% | 3x |
| ATR% > 1.5%，DIRECT | 4x |
| ATR% > 1.5%，PROBE | 3x |
| score>=90 且 DIRECT，Fib/PA 5x 条件满足 | 5x |
| score>=90 且 DIRECT，Fib/PA 5x 条件不满足 | 4x |
| 默认 DIRECT | 4x |
| 默认 PROBE | 3x |

Fib/PA 5x 条件：

| 组件 | 最低点数 |
|---|---:|
| Fib | 13 |
| PA | 9 |
| CCI | 7 |
| RR | 4 |

### 5.3 SCOUT 与 mirror A/B 仓位

| 账本 | notional | leverage | 特殊规则 |
|---|---:|---:|---|
| SCOUT | 50 USDT | 1x | `HIGH_SCORE_LONG_OFFSET_PROBE` 且 high beta 时减半为 25 USDT |
| mirror A/B legacy | 50 USDT | 1x | 只做样本 |
| mirror A/B trend_capture | 50 USDT | 1x | 只做样本 |

---

## 6. 风控逻辑

### 6.1 Entry hard block

命中后直接 `NO_TRADE`：

| 原因 | 触发逻辑 |
|---|---|
| `SYMBOL_BLACKLISTED` | 标的在 blacklist |
| `SYMBOL_WATCH_ONLY` | 标的在 watch_only |
| `MACRO_WEEKLY_RISK` | 周级宏观跌幅 <= 配置阈值 |
| `DATA_WICK_ANOMALY` | 异常插针/低量 |
| `DATA_POLLUTION_COOLDOWN` | 数据污染冷却 |
| `SYMBOL_POSITION_ALREADY_OPEN` | 同标的已有主账本持仓 |
| `MAX_ACTIVE_SYMBOLS` | 活跃标的数达到上限 |
| `DAILY_TRADE_BUDGET_USED` | 当日组合交易预算用完 |
| `SYMBOL_DAILY_TRADE_BUDGET_USED` | 单标的当日预算用完 |
| `SYMBOL_COOLDOWN_ACTIVE` | 标的冷却中 |
| `TOTAL_EXPOSURE_CAP` | 总敞口达到上限 |
| `SAME_DIRECTION_EXPOSURE_CAP` | 同向敞口达到上限 |
| `MARGIN_BUFFER_TOO_LOW` | 可用保证金低于 equity * buffer |
| `ACCOUNT_EQUITY_INVALID` | 权益无效 |
| `SIDE_NOT_ALLOWED` | 方向不是 LONG/SHORT |

Fib/PA 特殊硬阻断：

| 原因 | 触发逻辑 |
|---|---|
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | Fib 位置进入 1H 或 15m 1.618 延伸衰竭区，`fib_action_cap=0` |

### 6.2 降级与观察

| 规则 | 行为 |
|---|---|
| DIRECT 组件最低分不过 | 降为 PROBE |
| PROBE 条件不过 | 降为 WATCH |
| `LIQUIDITY_PROBE_BLOCK` | NO_TRADE |
| `LIQUIDITY_DIRECT_BLOCK` | DIRECT 降为 PROBE |
| high beta DIRECT | 强制降为 PROBE |
| LONG 过度延伸/追高风险 | Fib/PA 下 PROBE/DIRECT 可降为 WATCH |
| LONG low liquidity session | 若启用 long context discounts，可降至 WATCH |
| daily profit > 3% | PROBE 禁用；低边际 DIRECT 降 PROBE |
| weak edge direct/probe 无盈利历史 | dry-run 后处理降为 WATCH |

### 6.3 Dry-run 熔断与冷却

| 规则 | 当前配置 |
|---|---:|
| `post_initial_stop_cooldown_enabled` | true |
| 单标的初始止损后冷却 | 4 小时 |
| `rolling_symbol_cooldown_enabled` | true |
| 48 小时内同标的初始止损阈值 | 2 次 |
| 滚动冷却时间 | 24 小时 |
| `portfolio_stop_circuit_enabled` | true |
| 连续初始止损组合熔断阈值 | 2 次 |
| 组合初始止损熔断时间 | 2 小时 |
| `portfolio_daily_loss_circuit_enabled` | true |
| 当日亏损熔断阈值 | -30 USDT |

### 6.4 净 beta 观测

当前 `summary.json` 已输出：

| 字段 | 当前值 |
|---|---|
| `net_beta_exposure_model` | `static_v1_observation_only` |
| `net_beta_exposure_cap_pct` | 0.5 |
| 今日最新 `net_beta_exposure_pct` | 0.0 |

说明：净 beta 当前是观测模型，不是生产硬阻断。

---

## 7. 出场与持仓管理

当前纸面出场不读取四象限。

| 出场规则 | 当前实现 |
|---|---|
| 初始止损 | `stop_pct = clamp(ATR% * 1.5, 0.5%, 3.0%)`，无 ATR 时默认 1% |
| TP | TP1=1.2R、TP2=2.0R、TP3=3.0R |
| 分批比例 | 40% / 35% / 25% |
| bar 内顺序 | 先检查 stop，再检查 TP |
| TP 后止损 legacy | 移至近似保本：LONG 为 entry*1.001，SHORT 为 entry*0.999 |
| trend_capture | TP 后若 `max_favorable_r_observed >= 1.5`，用 1R trailing stop |
| 成本保本超时 | 持仓 8 根 15m bar 后，若未 TP 且毛收益低于估算成本 0.5 倍，平剩余仓位 |
| 最大持仓 | 32 根 15m bar |

当前配置：

| 账本 | exit_mode |
|---|---|
| 主账本 paper | `legacy` |
| SCOUT micro | `trend_capture` |
| mirror A/B legacy | `legacy` |
| mirror A/B trend_capture | `trend_capture` |

---

## 8. 今日可读日志表现

### 8.1 决策分布

原始 `decisions.jsonl` 当前可读行数：143。

| 动作 | 数量 |
|---|---:|
| NO_TRADE | 129 |
| WATCH | 14 |
| PROBE | 0 |
| DIRECT | 0 |

象限分布：

| 象限 | 数量 |
|---|---:|
| Q1 | 10 |
| Q2 | 16 |
| Q3 | 29 |
| Q4 | 88 |

象限 x 动作：

| 象限 | NO_TRADE | WATCH | PROBE | DIRECT |
|---|---:|---:|---:|---:|
| Q1 | 8 | 2 | 0 | 0 |
| Q2 | 14 | 2 | 0 | 0 |
| Q3 | 20 | 9 | 0 | 0 |
| Q4 | 87 | 1 | 0 | 0 |

### 8.2 near-miss

当前 near-miss 共 5 条。

| 象限 | 数量 |
|---|---:|
| Q1 | 2 |
| Q3 | 3 |

near-miss 主因：

| primary_reason | 数量 |
|---|---:|
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0` | 2 |
| `SYMBOL_BLACKLISTED` | 2 |
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.5` | 1 |

### 8.3 账本表现

主账本：

| 指标 | 今日可读原始日志 |
|---|---:|
| 新开仓 | 0 |
| 平仓 | 0 |
| `paper_trades.jsonl` | 0 行 |

SCOUT：

| 事件 | 标的 | 方向 | mission | 平仓原因 | PnL | 最大 favorable R |
|---|---|---|---|---|---:|---:|
| PAPER_CLOSE | DOGEUSDT | SHORT | `Q1_RR_GAP_SCOUT` | `COST_BREAKEVEN_TIMEOUT` | -0.0513 | 0.8330 |

mirror A/B：

| 账本 | 今日事件 | 标的 |
|---|---:|---|
| legacy | 2 次 PAPER_OPEN | TRXUSDT SHORT, XLMUSDT SHORT |
| trend_capture | 2 次 PAPER_OPEN | TRXUSDT SHORT, XLMUSDT SHORT |

截至 `paper_summary.json`：

| 账本 | trade_count | open_positions | PF | realized PnL |
|---|---:|---:|---:|---:|
| 主账本累计 | 61 | 0 | 0.6197 | -224.6081 |
| A/B legacy | 2 | 2 | 0.2639 | -0.3832 |
| A/B trend_capture | 2 | 2 | 0.6269 | -0.2435 |

注意：A/B 样本只有 2 笔且仍有 2 个 open positions，不能据此判断出场优劣。

---

## 9. 对 DeepSeek 的评审问题

1. 是否认可当前“四象限”应被重新命名为“技术状态四象限”，而不是基本面四象限？如果要做基本面四象限，需要引入哪些稳定、可实时执行、非未来函数的数据字段？
2. Q1 是否应该真正接入主账本绿色通道？当前 `dry_run_q1_green_channel_enabled=false`，且代码未实现主账本放行。若要提高开仓率，应优先放宽 RR gap、LONG offset，还是只让 Q1 进入 SCOUT/mirror？
3. Q2 是否应该实现 pending 状态：结构已达标但 CVD/CCI 未达标时，等待 1-3 根 K 线资金动能确认再开仓？
4. Q3-to-Q1 当前只进 SCOUT 且 pending 不持久化。是否需要把 pending 状态落盘，避免进程重启丢失拐点链路？
5. Q4 是否应该接入持仓管理，例如 Q4 连续 N 根 K 线触发减仓或平仓，而不是只等待止损/超时？
6. 当前主账本仍是 legacy 出场。是否应在 dry-run 主账本上启用真实 A/B 分账，或将 `trend_capture` 只用于 mirror 样本继续观察？
7. 当前阻断最大来源仍可能是 RR 几何、LONG offset、symbol policy。是否应把 Q1 的 RR 阈值从 hard gate 改成 reduced notional scout，而不是直接放主账本？

---

## 10. 当前实现一句话归因

昨天的四象限修改已经把 Q1/Q3 标签到日志、SCOUT 和 mirror A/B 样本池中，但没有把四象限真正接入主账本开仓和持仓出场；因此今天仍然表现为“能分类、能记录、能少量侦察，但不能明显提高主账本开仓率，也不能基于象限主动 hold/开多/开空/平多/平空”。
