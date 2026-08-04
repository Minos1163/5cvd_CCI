# AI300 最近 14 天 Dry-Run 进攻态势执行效果归因报告

**提交对象:** DeepSeek 评审  
**分析窗口:** 2026-06-30 至 2026-07-13 09:00 左右，北京时间；其中 2026-07-13 为不完整交易日。  
**目标问题:** 为什么“扩大盈利点 / 抓住大趋势”的进攻态势执行效果仍不理想；并补充实盘开仓链路、门槛分数、评分权重、仓位管理与风控逻辑。  
**数据来源:** `logs/2026-06/2026-06-30`、`logs/2026-07/2026-07-01` 至 `logs/2026-07/2026-07-13` 下的 `decisions.jsonl`、`paper_trades.jsonl`、`scout_micro/paper_trades.jsonl`、`summary.json`、`paper_summary.json`。  
**重要口径:** 本报告使用 dry-run/paper ledger 数据，不构成投资建议；2026-07-13 仅包含 65 条决策日志，不能按完整日解释。

---

## 0. 结论摘要

1. **进攻效果不理想的第一原因不是“完全没信号”，而是“高分信号到主账本盈利点的转化极低”。** 14 天 `decisions.jsonl` 共 16,183 条决策，动作分布为 `NO_TRADE=14,439`、`WATCH=1,733`、`PROBE=9`、`DIRECT=2`。score >= 85 的高分信号有 97 条，但只有 1 条 `PROBE`、2 条 `DIRECT`，其余 94 条被降级或拒绝。
2. **主账本新增交易的盈亏结构仍为负期望。** 14 天内主账本开平 11 笔，2 胜 9 负，净 PnL `-33.2913 USDT`，profit factor `0.2245`，平均盈利/平均亏损约 `1.01`。在 18.18% 胜率下，打平所需盈亏比约 `4.50`，当前只达到约 22% 的健康度。
3. **SCOUT 微仓没有证明“扩大盈利点”有效，反而继续给出负反馈。** 14 天 SCOUT 开平 9 笔，2 胜 7 负，净 PnL `-2.9352 USDT`，profit factor `0.1105`，平均盈利/平均亏损 `0.3869`。在 22.22% 胜率下，打平所需盈亏比约 `3.50`。
4. **新增优化多数是防御修复与观测增强，尚未转化为盈利扩张。** 07-08 后 SCOUT 已启用 `trend_capture`，但新增样本为 HYPE LONG 初始止损、ADA LONG 成本超时、XMR SHORT 初始止损，未出现“TP 后趋势延伸”的验证样本；主账本仍是 `paper_exit_mode=legacy`，因此主账本尚未受益于趋势捕捉出场。
5. **LONG 方向仍是趋势捕捉能力的最大空洞。** 14 天 LONG 决策中 `DIRECT=0`，`PROBE=1`；主账本唯一 LONG 交易 LABUSDT 初始止损 `-14.7648`。`SIDE_THRESHOLD_OFFSET_LONG_10.00` 在决策日志中出现 4,879 次，是最大单一拦截原因。
6. **RR 几何与 Fib 防追高机制正在成为“抓大趋势”的隐性天花板。** `risk_reward_geometry` 平均仅 `1.656/8`，`OPPOSITION_STRUCTURE_TOO_CLOSE` 出现 4,927 次；`FIB_EXTENSION_EXHAUSTION_BLOCK` 出现 1,467 次。它们可能保护系统少追高，但也可能让趋势延续行情无法进入样本。
7. **组合级风控观测已上线，但净 beta 风险仍未建模。** 最新 `summary.json` 输出 `max_total_exposure_pct=1.6`、`max_same_direction_exposure_pct=1.1`，但 `net_beta_exposure_model=not_configured`。当前低敞口主要来自低开仓率，不等于高仓位下安全。

---

## 1. 14 天执行数据总览

### 1.1 决策动作分布

| 指标 | 数值 |
|---|---:|
| 决策总数 | 16,183 |
| NO_TRADE | 14,439 |
| WATCH | 1,733 |
| PROBE | 9 |
| DIRECT | 2 |
| 主账本动作转化率(PROBE+DIRECT / 决策总数) | 0.068% |

### 1.2 分数分布

| 分数区间 | 数量 |
|---|---:|
| <70 | 14,369 |
| 70-75 | 848 |
| 75-80 | 627 |
| 80-85 | 242 |
| 85-90 | 77 |
| >=90 | 20 |

**解释:** score >= 85 共 97 条，不是“完全没有高分信号”。问题是高分信号没有稳定转化为可交易、可盈利的主账本交易。

### 1.3 主要拒绝原因

| 拒绝/原因 | 14 天次数 | 归类 |
|---|---:|---|
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 4,879 | 方向政策 |
| `SYMBOL_BLACKLISTED` | 2,308 | 标的政策 |
| `SYMBOL_WATCH_ONLY` | 2,211 | 标的政策 |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` | 1,467 | Fib 防衰竭 |
| `DAILY_TRADE_BUDGET_USED` | 266 | 预算 |
| `PROBE_BELOW_FIBONACCI_LOCATION_MINIMUM_GAP_3.0` | 196 | PROBE 组件门 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 110 | PROBE RR 门 |
| `SYMBOL_POSITION_ALREADY_OPEN` | 108 | 持仓冲突 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0` | 76 | PROBE RR 门 |
| `SYMBOL_DAILY_TRADE_BUDGET_USED` | 73 | 单标的预算 |
| `PROBE_BELOW_ELITE_STRUCTURE_GATE` | 27 | 精兵结构门 |
| `PROBE_LOW_SCORE_ELITE_VETO` | 22 | 低分一票否决 |

**判断:** 精兵门相关拦截存在，但不是最大堵点。最大的三类堵点是 LONG 方向偏移、标的静态政策、Fib/RR 几何。

### 1.4 高分信号被拦截的结构

score >= 85 的 97 条信号中：

| 动作 | 数量 |
|---|---:|
| NO_TRADE | 41 |
| WATCH | 53 |
| PROBE | 1 |
| DIRECT | 2 |

高分信号主要拦截原因：

| 高分信号原因 | 次数 |
|---|---:|
| `SYMBOL_BLACKLISTED` | 21 |
| `SYMBOL_WATCH_ONLY` | 18 |
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 17 |
| `PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 17 |
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0` | 16 |
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0` | 8 |
| `HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0` | 8 |

高分信号最多的标的：

| 标的 | score >=85 数量 |
|---|---:|
| ZECUSDT | 19 |
| ADAUSDT | 11 |
| HYPEUSDT | 11 |
| BCHUSDT | 8 |
| XMRUSDT | 7 |
| XLMUSDT | 7 |
| BNBUSDT | 7 |

**归因:** 高分供给集中在 ZEC/ADA/XMR 等黑名单或 watch-only 标的，以及 HYPE 这类 high beta 标的。系统不是缺高分，而是高分大多落在“当前政策不允许或需要额外验证”的区域。

---

## 2. 主账本与 SCOUT 盈亏结构

### 2.1 主账本 14 天新增交易

| 指标 | 数值 |
|---|---:|
| 开仓数 | 11 |
| 完整平仓数 | 11 |
| 胜 / 负 | 2 / 9 |
| 胜率 | 18.18% |
| 净 PnL | -33.2913 USDT |
| gross win | 9.6390 |
| gross loss | 42.9303 |
| profit factor | 0.2245 |
| 平均盈利 | 4.8195 |
| 平均亏损 | 4.7700 |
| 实际盈亏比 | 1.0104 |
| 打平所需盈亏比 | 4.50 |
| 单笔期望 | -3.0265 USDT |

主账本完整平仓明细：

| 日期 | 标的 | 方向 | 平仓原因 | PnL |
|---|---|---|---|---:|
| 06-30 | LINKUSDT | SHORT | COST_BREAKEVEN_TIMEOUT | -1.3177 |
| 06-30 | BNBUSDT | SHORT | COST_BREAKEVEN_TIMEOUT | -0.0522 |
| 06-30 | LABUSDT | LONG | INITIAL_STOP_HIT | -14.7648 |
| 06-30 | HYPEUSDT | SHORT | INITIAL_STOP_HIT | -5.0112 |
| 06-30 | SOLUSDT | SHORT | COST_BREAKEVEN_TIMEOUT | -1.7800 |
| 06-30 | SOLUSDT | SHORT | BREAKEVEN_STOP_HIT | +2.5733 |
| 07-01 | HYPEUSDT | SHORT | INITIAL_STOP_HIT | -6.1561 |
| 07-03 | LINKUSDT | SHORT | COST_BREAKEVEN_TIMEOUT | -2.3034 |
| 07-06 | BCHUSDT | SHORT | INITIAL_STOP_HIT | -7.1539 |
| 07-06 | BCHUSDT | SHORT | BREAKEVEN_STOP_HIT | +7.0657 |
| 07-10 | BCHUSDT | SHORT | COST_BREAKEVEN_TIMEOUT | -4.3909 |

主账本平仓原因分布：

| 原因 | 数量 |
|---|---:|
| COST_BREAKEVEN_TIMEOUT | 5 |
| INITIAL_STOP_HIT | 4 |
| BREAKEVEN_STOP_HIT | 2 |

**归因:** 主账本没有形成“少数大盈利覆盖多数小亏损”的趋势跟随结构。2 笔盈利都不是大趋势奔跑，4 笔初始止损和 5 笔成本超时持续消耗期望值。

### 2.2 SCOUT 微仓 14 天新增交易

| 指标 | 数值 |
|---|---:|
| 开仓数 | 9 |
| 完整平仓数 | 9 |
| 胜 / 负 | 2 / 7 |
| 胜率 | 22.22% |
| 净 PnL | -2.9352 USDT |
| profit factor | 0.1105 |
| 平均盈利 | 0.1824 |
| 平均亏损 | 0.4714 |
| 实际盈亏比 | 0.3869 |
| 打平所需盈亏比 | 3.50 |
| 单笔期望 | -0.3261 USDT |

SCOUT 完整平仓明细：

| 日期 | 标的 | 方向 | mission | 平仓原因 | PnL |
|---|---|---|---|---|---:|
| 07-04 | XLMUSDT | SHORT | NONE | BREAKEVEN_STOP_HIT | +0.2043 |
| 07-04 | XLMUSDT | SHORT | NONE | INITIAL_STOP_HIT | -0.6051 |
| 07-05 | ZECUSDT | SHORT | NON_RR_HIGH_SCORE | INITIAL_STOP_HIT | -0.5576 |
| 07-05 | ZECUSDT | LONG | NON_RR_HIGH_SCORE | INITIAL_STOP_HIT | -0.4554 |
| 07-06 | XLMUSDT | LONG | TARGETED_LONG_OFFSET | INITIAL_STOP_HIT | -0.5404 |
| 07-08 | XMRUSDT | SHORT | NON_RR_HIGH_SCORE | BREAKEVEN_STOP_HIT | +0.1605 |
| 07-08 | HYPEUSDT | LONG | TARGETED_LONG_OFFSET | INITIAL_STOP_HIT | -0.5422 |
| 07-11 | ADAUSDT | LONG | NON_RR_HIGH_SCORE | COST_BREAKEVEN_TIMEOUT | -0.2489 |
| 07-11 | XMRUSDT | SHORT | NON_RR_HIGH_SCORE | INITIAL_STOP_HIT | -0.3503 |

SCOUT mission 分布：

| mission | 数量 | 结果摘要 |
|---|---:|---|
| NON_RR_HIGH_SCORE | 5 | 1 胜 4 负 |
| TARGETED_LONG_OFFSET | 2 | 0 胜 2 负 |
| NONE | 2 | 1 胜 1 负 |

**归因:** SCOUT 的扩大采样还没有找到正期望 mission。`TARGETED_LONG_OFFSET` 两笔全亏，说明 LONG offset 被拦下的高分信号并不自动等于可交易 alpha；`NON_RR_HIGH_SCORE` 也没有证明“高分但非 RR 缺口”可以盈利。

---

## 3. 最近 14 天逐日变化

| 日期 | 决策数 | PROBE | DIRECT | 主账本开仓 | 主账本日 PnL | SCOUT 开仓 | SCOUT 日 PnL | near-miss 文件样本 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 06-30 | 1204 | 6 | 0 | 6 | -20.3526 | 0 | 0 | 0 |
| 07-01 | 1152 | 1 | 0 | 1 | -6.1561 | 0 | 0 | 0 |
| 07-02 | 1152 | 1 | 0 | 1 | 0 | 0 | 0 | 7 |
| 07-03 | 1152 | 0 | 0 | 0 | -2.3034 | 0 | 0 | 7 |
| 07-04 | 1241 | 0 | 0 | 0 | 0 | 2 | -0.4008 | 14 |
| 07-05 | 1334 | 0 | 0 | 0 | 0 | 2 | -1.0130 | 28 |
| 07-06 | 1344 | 1 | 1 | 2 | -0.0882 | 1 | -0.5404 | 23 |
| 07-07 | 1299 | 0 | 0 | 0 | 0 | 0 | 0 | 16 |
| 07-08 | 1248 | 0 | 0 | 0 | 0 | 2 | -0.3817 | 10 |
| 07-09 | 1248 | 0 | 0 | 0 | 0 | 0 | 0 | 12 |
| 07-10 | 1248 | 0 | 1 | 1 | -4.3909 | 0 | 0 | 11 |
| 07-11 | 1248 | 0 | 0 | 0 | 0 | 2 | -0.5992 | 22 |
| 07-12 | 1248 | 0 | 0 | 0 | 0 | 0 | 0 | 15 |
| 07-13 | 65 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

**解释:** 07-06 之后主账本明显精兵化，但 07-10 的 BCH DIRECT 仍以成本超时亏损结束；07-08 之后 SCOUT 切入 `trend_capture`，但新增样本没有触发趋势扩展获利。

---

## 4. 根因归因

### 根因一：高分信号转化率过低，进攻火力没有落到可交易仓位

14 天内 score >= 85 有 97 条，其中 `NO_TRADE/WATCH=94`。高分被拦截主要集中在标的政策、LONG offset、RR gap。也就是说，系统“看见”了机会，但主账本执行层只接收了极少数。

这并不必然说明要放松门槛。ZEC、ADA、XMR 的高分被拦截可能是正确风控。但从“扩大盈利点”的角度看，系统目前缺少一个可验证的中间层：既不把这些高分信号直接打入主账本，也没有足够有效的 SCOUT 样本证明哪些拦截值得解禁。

### 根因二：盈亏比结构没有支撑低胜率趋势捕捉

当前目标已从“开仓数量”转向“抓大趋势”。这种目标通常允许胜率较低，但要求盈利单足够大。实际结果相反：

- 主账本胜率 18.18%，打平所需盈亏比约 4.50，实际仅 1.01。
- SCOUT 胜率 22.22%，打平所需盈亏比约 3.50，实际仅 0.3869。

这说明当前不是“盈利扩得慢”，而是“每笔交易的盈亏结构方向仍错”。即便增加开仓数量，若结构不变，只会更快复制负期望。

### 根因三：出场优化尚未覆盖主账本，SCOUT 样本也没有触发趋势捕捉收益

当前配置：

- 主账本 `paper_exit_mode=legacy`
- SCOUT `scout_micro_exit_mode=trend_capture`

因此，主账本 07-08 后仍沿用 legacy 出场，不应把主账本不理想归咎于 `trend_capture` 无效。SCOUT 虽已启用 `trend_capture`，但新增样本为：

- HYPEUSDT LONG：INITIAL_STOP_HIT
- ADAUSDT LONG：COST_BREAKEVEN_TIMEOUT
- XMRUSDT SHORT：INITIAL_STOP_HIT

这些样本没有进入“TP 后 trend trailing”的分支，因此只能说明：新出场逻辑尚未获得有效验证样本，不能证明它能扩大盈利点。

### 根因四：LONG 方向被结构性压制，抓上涨大趋势的能力几乎没有样本

14 天 LONG 动作：

| LONG 动作 | 数量 |
|---|---:|
| NO_TRADE | 7,677 |
| WATCH | 449 |
| PROBE | 1 |
| DIRECT | 0 |

主账本唯一 LONG 是 06-30 的 LABUSDT，结果 `INITIAL_STOP_HIT -14.7648`。SCOUT 的 `TARGETED_LONG_OFFSET` 两笔也均亏损。

这带来两个同时成立的结论：

1. 主账本没有上涨趋势捕捉能力的实证样本；
2. 仅凭当前 SCOUT 负样本，也不能证明应该直接放宽 LONG offset。

正确归因不是“LONG offset 一定错”，而是“LONG 侧缺少可控、足量、带新出场逻辑的小仓位验证样本”。

### 根因五：RR 几何与 Fib exhaustion 保护了系统，但也可能拦截趋势延续

14 天平均组件分：

| 组件 | 平均得分 |
|---|---:|
| trend_ema_context | 14.834 / 20 |
| flow_cvd_confirmation | 13.174 / 18 |
| cci_momentum_quality | 3.954 / 14 |
| price_action_structure | 7.308 / 22 |
| fibonacci_location | 10.240 / 18 |
| risk_reward_geometry | 1.656 / 8 |

`risk_reward_geometry` 是显著短板，且 `OPPOSITION_STRUCTURE_TOO_CLOSE` 出现 4,927 次。`FIB_EXTENSION_EXHAUSTION_BLOCK` 出现 1,467 次。

这意味着系统经常看到趋势或流向，但认为上方/下方阻力太近、或 Fib 位置已衰竭，因此拒绝开仓。这个设计对防追高追空有价值，但在“抓大趋势”框架下，需要做事后误伤率审计：被这些规则拦下后，后续是否真的衰竭，还是继续趋势延伸。

### 根因六：标的政策仍是静态黑白名单，缺少滚动晋级/降级面板

高分信号最集中的 ZEC、ADA、XMR 大量落入黑名单或 watch-only。静态名单的风险是：

- 如果名单正确，系统避免了坏标的；
- 如果名单过期，系统错过一批高分机会；
- 当前没有足够的滚动 MFE/MAE 或拦截后收益回放来区分这两种情况。

因此，当前不能简单解禁，也不能无限期静态封存。需要用 14-21 天 rolling panel 管理 symbol policy。

### 根因七：组合敞口诊断是观测，不是已验证的高仓位安全

最新 dry-run assumptions 输出：

- `max_total_exposure_pct=1.6`
- `max_same_direction_exposure_pct=1.1`
- `net_beta_exposure_model=not_configured`

当前 open_positions 多数时候为 0，低敞口来自低活跃度。若未来提升仓位/杠杆或恢复 PROBE 吞吐，尚未配置的净 beta 模型会成为组合级风险缺口。

---

## 5. 对最近新增优化点的效果评估

| 优化点 | 实际效果 | 未达理想原因 |
|---|---|---|
| 精兵门 / 低分 PROBE veto | 07-06 后低分主账本交易减少 | 解决了部分劣质入场，但没有提升盈利单放大能力 |
| 动态 SCOUT mission | 扩大了 XLM/ZEC/XMR/HYPE/ADA 等侦察样本 | 样本总体负期望，mission 尚未证明可晋级 |
| `trend_capture` 出场 | 已覆盖 SCOUT，主账本未覆盖 | 新增 SCOUT 样本没有走到 TP 后趋势 trailing 分支 |
| Stage 0 gate/layer 诊断 | 清楚显示 side/symbol/fib/probe 是堵点 | 是观测能力，不直接增加盈利 |
| 组合敞口输出 | 已输出 total/same-direction exposure | `net_beta_exposure_model` 仍未配置，且低仓位环境未压测 |
| HIGH_BETA 更严 RR/结构门 | HYPE/LAB/CC 的高 beta 风险被更多拦截 | 06-30/07-01 的 HYPE/LAB 亏损说明旧样本已暴露波动风险，新规则仍需后验验证 |

---

## 6. 实盘 / Dry-Run 开仓链路说明

> 当前脚本是 live dry-run：会生成 `LiveEntryOrderDraft`，但 `orders_submitted=0`，没有真实交易所 mutation。若接入实盘执行，核心批准条件和订单草稿来自同一条 entry-chain 链路。

### 6.1 数据与上下文构建

入口脚本：`scripts/run_live_dry_run.py`

1. 按配置解析交易标的，当前配置使用 market cap rank 与 fallback symbols。
2. 使用 public Binance 读取 `15m/30m/1h/4h` K 线；当前 warmup 需要至少 240 根 15m。
3. 每轮在 K 线收盘后延迟执行，默认 `post_close_delay_seconds=5.0`，日志中记录 `latency_ms`。
4. 构造 `EntryChainContext`：
   - `symbol`
   - `side`：由 1h 趋势判断，回退 15m 趋势
   - `component_scores`
   - `quote_volume_24h`
   - `atr_pct`
   - `stop_pct = clamp(0.5%, 4%, atr_pct * 1.5)` 用于 entry risk hint
   - 当前 paper 持仓、当日交易数、同向敞口、总敞口、symbol 敞口
   - LONG chase / upper wick / overextension / low liquidity / weak CVD flags

### 6.2 评分权重

当前 `use_fib_pa_architecture=true`，实际使用 Fib/PA 权重：

| 组件 | 权重 | 含义 |
|---|---:|---|
| `trend_ema_context` | 20 | EMA / 趋势背景 |
| `flow_cvd_confirmation` | 18 | CVD / 资金流确认 |
| `cci_momentum_quality` | 14 | CCI 动量质量 |
| `price_action_structure` | 22 | PA 结构 |
| `fibonacci_location` | 18 | Fib 位置 |
| `risk_reward_geometry` | 8 | 风报比几何 |

计算方式：每个组件原始分 `0.0-1.0` clamp 后乘权重，总分为各组件点数之和，满分 100。

### 6.3 动作阈值

当前配置：

| 动作 | SHORT 阈值 | LONG 阈值 |
|---|---:|---:|
| WATCH | 62 | 72 (`62 + long_threshold_offset 10`) |
| PROBE | 70 | 77 (`70 + probe_conditions.long_threshold_offset 7`) |
| DIRECT | 82 | 92 (`82 + long_threshold_offset 10`) |

这解释了为什么 LONG 主账本几乎没有交易：LONG DIRECT 需要 92 分，同时还要通过组件门、风控门、SCOUT/黑名单/冷却等后续条件。

### 6.4 硬风控阻断顺序

`hard_block_reason` 的主要顺序：

1. `SYMBOL_BLACKLISTED`
2. `SYMBOL_WATCH_ONLY`
3. `MACRO_WEEKLY_RISK`
4. `DATA_WICK_ANOMALY`
5. `DATA_POLLUTION_COOLDOWN`
6. `SYMBOL_POSITION_ALREADY_OPEN`
7. `MAX_ACTIVE_SYMBOLS`
8. `DAILY_TRADE_BUDGET_USED`
9. `SYMBOL_DAILY_TRADE_BUDGET_USED`
10. `SYMBOL_COOLDOWN_ACTIVE`
11. `TOTAL_EXPOSURE_CAP`
12. `SAME_DIRECTION_EXPOSURE_CAP`
13. `MARGIN_BUFFER_TOO_LOW`
14. `ACCOUNT_EQUITY_INVALID`
15. `SIDE_NOT_ALLOWED`

当前静态政策：

| 类型 | 标的 |
|---|---|
| blacklist | XRPUSDT, ZECUSDT |
| watch_only | ADAUSDT, XMRUSDT |
| observation_only | XLMUSDT, TONUSDT |
| high beta | HYPEUSDT, LABUSDT, CCUSDT |

### 6.5 DIRECT 组件门

DIRECT 先由总分阈值产生，再经过 Fib/PA 最低组件门：

| 组件 | DIRECT 最低点数 |
|---|---:|
| price_action_structure | 6 / 22 |
| fibonacci_location | 9 / 18 |
| risk_reward_geometry | 4 / 8 |

未通过会从 `DIRECT` 降为 `PROBE`，再继续接受 PROBE 条件检查。

### 6.6 PROBE 条件门

当前 `probe_conditions`：

| 条件 | 当前值 |
|---|---:|
| enabled | true |
| min_score | 72 |
| min_fib_score | 12 / 18 |
| min_pa_score | 10 / 22 |
| min_rr_score | 4 / 8 |
| min_rr_net_r | 1.3 |
| trend_or_cci_min_ema_score | 10 / 20 |
| trend_or_cci_min_cci_score | 9 / 14 |
| low_score_quality_veto_score | 75 |
| low_score_quality_min_ema_score | 10 / 20 |
| low_score_quality_min_cci_score | 7 / 14 |
| elite_probe_enabled | true |
| elite_probe_min_score | 75 |
| elite_probe_min_pa_score | 18 / 22 |
| elite_probe_min_fib_score | 15 / 18 |
| elite_probe_trend_min_ema_score | 15 / 20 |
| elite_probe_trend_min_structure_sum | 30 |
| high_beta_min_pa_score | 12 / 22 |
| high_beta_min_rr_score | 5 / 8 |
| high_beta_min_cci_score | 9 / 14 |
| high_beta_min_ema_score | 12 / 20 |
| max_active_probes | 2 |

精兵结构门逻辑：

- `score < 75` 直接触发 `PROBE_LOW_SCORE_ELITE_VETO`；
- 或者满足 `PA >= 18 and Fib >= 15`；
- 或者满足 `EMA >= 15 and PA + Fib >= 30`；
- 否则 `PROBE_BELOW_ELITE_STRUCTURE_GATE`。

### 6.7 LONG 额外处理

当前配置开启：

- `long_threshold_offset=10`
- `long_overextension_watch_enabled=true`
- `long_chase_watch_enabled=true`

含义：

1. LONG 的主阈值整体更高；
2. 如果 LONG 已经过度延展或 chase risk active，即使动作达到 `PROBE/DIRECT`，也会降为 `WATCH`；
3. 当前配置没有显式开启 `enable_long_context_discounts`，因此 LONG 弱 CVD/追涨等更多体现为 watch gate，而不是评分折扣。

### 6.8 流动性与 HIGH_BETA 规则

流动性比率：

- `probe_liquidity_ratio=8`
- `direct_liquidity_ratio=20`

若低于 probe 门，直接 `LIQUIDITY_PROBE_BLOCK`；若低于 direct 门，`DIRECT` 降为 `PROBE`。

HIGH_BETA 标的：

- HYPEUSDT
- LABUSDT
- CCUSDT

若 high beta 信号达到 `DIRECT`，会先降为 `PROBE`，再用更高的 PA/RR/CCI/EMA 门槛复核。当前 14 天中 high beta 的 RR gap 是重要拦截来源。

### 6.9 杠杆选择

`_select_leverage` 当前逻辑：

| 条件 | 杠杆 |
|---|---:|
| 非 PROBE/DIRECT | 0 |
| rolling_sharpe_20 < 0 | 2 |
| atr_pct > 3% | 3 |
| atr_pct > 1.5%，DIRECT | 4 |
| atr_pct > 1.5%，PROBE | 3 |
| score >= 90 且 DIRECT，且 5x 组件要求通过 | 5 |
| score >= 90 且 DIRECT，但 5x 组件要求失败 | 4 |
| 普通 DIRECT | 4 |
| 普通 PROBE | 3 |

5x 组件要求：

| 组件 | 要求 |
|---|---:|
| fibonacci_location | >=13 / 18 |
| price_action_structure | >=9 / 22 |
| cci_momentum_quality | >=7 / 14 |
| risk_reward_geometry | >=4 / 8 |

### 6.10 仓位 / notional hint

当前仓位计算不是简单固定百分比，而是取多个上限的最小值：

1. 分数/动作暴露：
   - DIRECT 基础 `base_direct_exposure_pct=20%`，并随 score 高于 direct threshold 最多额外 +10%；
   - PROBE 使用 `base_direct_exposure_pct * probe_fraction = 20% * 25% = 5%`；
2. symbol cap：
   - large cap BTC/ETH/BNB：30%
   - mainstream SOL/ADA/LINK：20%
   - high beta HYPE/LAB/CC：10%
   - 其他默认 mainstream：20%
3. 风险预算：
   - DIRECT `direct_risk_pct=0.006`
   - PROBE `probe_risk_pct=0.0025`
   - `risk_based = equity * risk_pct / stop_pct`
4. 剩余 symbol cap：
   - `(max_symbol_exposure_pct - current_symbol_exposure_pct) * equity`

最终：

```text
notional_hint = min(score_based, risk_based, cap_remaining)
```

### 6.11 组合级约束

当前配置：

| 风控项 | 数值 |
|---|---:|
| max_active_symbols | 8 |
| daily_max_trades_base | 16 |
| min_daily_trades | 2 |
| max_symbol_trades_per_day | 2 |
| max_total_exposure_pct | 1.6 |
| max_same_direction_exposure_pct | 1.1 |
| margin_buffer_pct | 30% |
| net_beta_exposure_model | not_configured |

日预算是动态的：

```text
dynamic_limit = max(min_daily_trades, floor(daily_max_trades_base * current_volatility_scale / normal_volatility_scale))
```

若当日盈利超过 3%，预算减半。

### 6.12 Live order draft

`build_live_entry_order_draft` 批准条件：

1. `decision.action in {"PROBE", "DIRECT"}`；
2. `decision.risk_allowed == true`；
3. price > 0；
4. `quantity = notional_hint / price` 大于最小数量。

订单草稿：

- `order_type="MARKET"`
- LONG => BUY
- SHORT => SELL
- `reduce_only=false`
- 不在该草稿里直接设置 stop loss / take profit；
- `risk_snapshot` 写入 score 与 reasons。

当前 dry-run 不提交订单，`orders_submitted=0`。

---

## 7. Paper / SCOUT 仓位管理与出场逻辑

### 7.1 费用与滑点假设

| 项 | 数值 |
|---|---:|
| entry fee | 5 bps |
| entry slippage | 5 bps |
| exit fee | 5 bps |
| exit slippage | 5 bps |
| PnL 主口径 | notional primary, margin reporting |

### 7.2 初始止损与 TP 梯度

paper ledger 开仓后：

```text
stop_pct = clamp(0.5%, 3.0%, atr_pct * 1.5)
risk_distance = entry_price * stop_pct
```

TP 梯度：

| TP | R 倍数 | 平仓比例 |
|---|---:|---:|
| TP1 | 1.2R | 40% |
| TP2 | 2.0R | 35% |
| TP3 | 3.0R | 25% |

持仓限制：

- `MAX_HOLD_BARS=32`
- `COST_BREAKEVEN_CHECK_BARS=8`
- 未触发 TP 且持仓 8 根 bar 后，如果浮盈不足以覆盖成本缓冲，触发 `COST_BREAKEVEN_TIMEOUT`

### 7.3 legacy vs trend_capture

legacy：

- 触发 TP 后，剩余仓位止损移动到成本附近；
- 后续若回撤，记录 `BREAKEVEN_STOP_HIT`。

trend_capture：

- TP 后先计算 favorable R；
- 若 favorable R < `trend_trigger_r=1.5`，仍使用成本止损；
- 若 favorable R >= 1.5，使用 `trailing_r_mult=1.0` 的结构化跟踪止损；
- 当前 SCOUT 已启用，主账本未启用。

### 7.4 SCOUT 微仓规则

基础条件：

- symbol 必须在 `scout_micro_symbols`
- data health 必须 OK
- 无同 symbol 已有 scout 仓
- near-miss 存在
- score >= `scout_micro_min_score=82`
- intended side 必须为 LONG/SHORT
- entry price > 0
- mission 必须匹配

mission：

| mission | 条件 |
|---|---|
| TARGETED_LONG_OFFSET | symbol 在 targeted long 池；intended side LONG；包含 LONG offset reason 或 tag；score >=82；PA >=18；RR >=3 |
| SCOUT_ONLY_HIGH_SCORE | symbol 在 XMR/ADA scout-only 池；score >=85；Fib >=12；PA >=10；RR >=4 |
| NON_RR_HIGH_SCORE | score >=85，且不是 RR gap reason |

SCOUT 仓位：

- notional = 50 USDT
- leverage = 1
- same side cooldown = 2 小时
- initial stop cooldown = 6 小时

---

## 8. 当前缺失指标与复核建议

按 AGENTS.md 的量化研究要求，本轮能报告：

- trade count
- win rate
- profit factor
- expectancy
- max drawdown（ledger cumulative）
- fee/slippage assumptions
- exposure
- payoff ratio

当前缺失或不足：

| 指标 | 状态 |
|---|---|
| Sharpe | 当前日志未直接输出 |
| MFE/MAE | 当前平仓事件未直接输出；需另行回放 K 线 |
| tail risk | 未输出分位数亏损/极端滑点模拟 |
| funding rate | 未纳入 paper PnL |
| net beta exposure | `not_configured` |
| latency/fill slippage 实盘校准 | 只有固定 bps 假设和 latency_ms 记录，未做成交质量回放 |

建议下一轮补充：

1. 对 `FIB_EXTENSION_EXHAUSTION_BLOCK` 和 `SIDE_THRESHOLD_OFFSET_LONG_10.00` 做拦截后 N 根 K 线 MFE/MAE 回放，判断误伤率。
2. 对 score >=85 但被 symbol policy 拦截的 ZEC/ADA/XMR 做 rolling 14-21 天面板：near-miss 数、拦截后 MFE/MAE、是否达到 TP1/TP2/TP3、最大反向波动。
3. 将主账本小流量切到 `trend_capture` 前，先做离线回放或 A/B dry-run，避免仅凭 SCOUT 9 笔负样本否定出场逻辑。
4. 为 high beta 标的单独输出仓位、ATR、止损距离与滑点敏感性，避免 HYPE/LAB 类大波动样本继续贡献不成比例亏损。
5. 配置简化版 `net_beta_exposure_model`，至少按 BTC beta 静态表对同向组合做上限。

---

## 9. 给 DeepSeek 的重点评审问题

1. 在“抓大趋势、不限制开仓次数”的目标下，主账本是否应继续保持 LONG direct threshold = 92，还是应只在 SCOUT/PROBE_TIER 中主动采样 LONG？
2. `FIB_EXTENSION_EXHAUSTION_BLOCK` 是否应拆分为“逆势衰竭拦截”和“顺势突破延续降级处理”，而不是一律硬拦截？
3. 当前 `elite_probe_enabled=true` 是否过早把 PROBE 也做成精兵层，导致中间验证层不足？还是考虑到 14 天负期望，继续严格是正确的？
4. SCOUT 的 `NON_RR_HIGH_SCORE` 是否应该暂停开仓，仅保留 near-miss 回放？当前 5 笔 1 胜 4 负，PF 明显为负。
5. `TARGETED_LONG_OFFSET` 两笔全亏后，是应该暂停，还是继续用更严格 PA/RR + trend_capture 积累到 15-20 笔再判断？
6. 主账本是否应在极小仓位或 paper A/B 中启用 `trend_capture`，以验证“扩大盈利点”真正依赖的出场架构？
7. 在净 beta 未配置前，是否应禁止任何仓位/杠杆上调，即使信号质量有所改善？

---

## 10. 最终归因

本轮“扩大盈利点”不理想，不是单一阈值问题，而是四个层面的叠加：

1. **执行层转化不足:** 16,183 条决策仅 11 笔主账本开仓，score >=85 的 97 条只有 3 条成为主账本动作。
2. **盈亏结构未修复:** 主账本 PF 0.2245，SCOUT PF 0.1105，实际盈亏比远低于各自打平线。
3. **趋势捕捉出场未完成闭环:** SCOUT 已启用但样本没走到趋势 trailing，主账本仍是 legacy。
4. **进攻方向受政策约束:** LONG offset、symbol policy、Fib exhaustion、RR gap 同时压制最可能产生“扩大盈利点”的样本池。

因此，本阶段最优先的不是加杠杆、加仓位或简单放宽阈值，而是：

- 用 MFE/MAE 回放判断拦截规则是否误伤趋势；
- 用小仓位 A/B 验证 `trend_capture` 是否能提高 payoff ratio；
- 用 rolling symbol panel 替代静态名单；
- 补齐 net beta 风控后，再讨论扩大仓位。

---

## 11. 第八次评审后新增证据包

根据 DeepSeek 第八次评审，已新增离线“高分拦截信号回放器”。该回放器只用于事后归因，明确使用未来 K 线，不参与实盘决策。

输出文件：

- `reports/structured_offense/2026-07-13/high_score_intercept_replay.md`
- `reports/structured_offense/2026-07-13/high_score_intercept_replay.json`
- `reports/structured_offense/2026-07-13-with-fib-exhaustion/high_score_intercept_replay.md`
- `reports/structured_offense/2026-07-13-with-fib-exhaustion/high_score_intercept_replay.json`

本次回放覆盖 2026-06-30 至 2026-07-13 的 94 条 score >= 85 且未进入 `PROBE/DIRECT` 的高分拦截信号。假设入场价为日志中已收盘 15m K 线 close，初始止损使用 `entry_context.stop_pct`，观察窗口为后续 96 根 15m K 线。

关键初步结果：

| 分组 | 样本 | avg MFE R | avg MAE R | avg final R | TP2触达率 | stop hit率 |
|---|---:|---:|---:|---:|---:|---:|
| 全部高分拦截 | 94 | 1.6692 | 1.2561 | -0.2718 | 28.72% | 84.04% |
| `SIDE_THRESHOLD_OFFSET_LONG_10.00` | 17 | 2.8073 | 1.0949 | 0.4617 | 41.18% | 82.35% |
| `SYMBOL_BLACKLISTED` | 21 | 1.1310 | 1.2378 | -0.6597 | 19.05% | 85.71% |
| `SYMBOL_WATCH_ONLY` | 18 | 1.2313 | 1.2907 | -0.9099 | 27.78% | 94.44% |
| `DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_4.0` | 8 | 2.4384 | 1.0477 | 0.0013 | 50.00% | 75.00% |
| `FIB_EXTENSION_EXHAUSTION_BLOCK` 增强样本 | 1,466 | 1.8929 | 1.2111 | -0.3389 | 33.29% | 81.45% |

初步解读：

1. `SIDE_THRESHOLD_OFFSET_LONG_10.00` 的确存在较高的趋势误伤嫌疑，17 条样本中 41.18% 在 24 小时内触达过 2R，但同组 stop hit 率也有 82.35%，说明不能直接放宽主规则，更适合进入 SCOUT/PROBE_TIER 做条件化验证。
2. `FIB_EXTENSION_EXHAUSTION_BLOCK` 的增强样本显示 33.29% 曾触达 2R，但 stop hit 率也有 81.45%。这支持“拆分顺势延续与逆势衰竭场景”的方向，但不支持一刀切移除该拦截。
3. 黑名单与 watch-only 的整体回放仍偏弱，尤其 `SYMBOL_WATCH_ONLY` stop hit 率 94.44%，暂不支持直接晋级主账本。
4. RR gap 并非完全无效拦截。部分 RR gap 分组有较高 MFE，但同时也有高 stop hit，提示后续应评估“先止损还是先触达 TP”的时序，而不是只看窗口内最大 MFE。
5. 该证据包验证了 DeepSeek 提出的第三层“情报哨”方向：未来调整 LONG offset、Fib exhaustion、RR gap 前，应先用这类离线回放给出误伤率和风险率。
