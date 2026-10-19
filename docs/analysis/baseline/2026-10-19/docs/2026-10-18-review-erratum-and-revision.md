# MACD_V4 评审勘误与修订

**日期:** 2026-10-18
**对象:** `2026-10-18-macd-v4-review-and-recommendations.md`(外部评审,493 行)与 `2026-10-18 优化方案综合评审包`
**性质:** 复核回执。把两份文档里**用错误前提支撑的结论**替换为实测值,并据此重排优先级。
**方法:** 全部结论来自本地日志与源码复核,每条给出可复现的查询口径;无法用现有数据回答的,明确标注为"需埋点"而不是估计。

---

## 〇、结论

1. 评审指出的三处错误**全部成立**,其中"4.8σ"必须删除、"direct 降 1x"必须撤销。
2. 评审附录 A 查询 1 **可执行**,但必须读 `decisions.jsonl` 的 `metadata.risk_budget`——`attribution.jsonl` 不复制该字段,只读 attribution 会得出"从未落盘"的错误结论。查询 5(逐笔 `stop_price`)**确实不可执行**。
3. 逐笔复核推翻了本文初稿的一个判断:**`leveraged_cap` 不是唯一绑定量**。DIRECT 14/14 全部撞 `leveraged_cap`,PROBE 36 条里只有 2 条撞它,25 条撞 `remaining_exposure_notional`、9 条撞 `raw_notional`。所以"单笔风险恒定"只对 DIRECT 成立。
4. `direct_risk_pct` 从未生效(14/14 未绑定),但 `probe_risk_pct` 在 9/36 生效,**且实测值约 0.15%,与本地配置的 0.4% 不符**——线上 profile 与本地仓库文件存在漂移。
5. 复核对 `D1`、`D9` 给出了比评审更硬的判定:**都被证伪**,不是"证据不足"。

---

## 一、对评审三处指正的确认

### 1.1 "4.8 个标准差" — 确认错误

原文档:`31 笔 25.8% 胜率 vs 37.9% 打平线,差距是 4.8 个标准差量级`。

零假设 `p* = 1/(1+1.64) = 0.379`,实测 `8/31 = 0.258`:

```
SE = sqrt(0.379 × 0.621 / 31) = 0.0871
z  = (0.258 − 0.379) / 0.0871 = −1.39
单侧精确二项 p = 0.113
Wilson 95% 区间 = [13.7%, 43.2%]      ← 37.9% 落在区间内
```

**31 笔既不能证明有优势,也不能证明没优势。** 原文的"不是运气"删除。

跨三窗口合并(本轮独立复核,trades 逐笔重算):

| 窗口 | 笔数 | 胜笔 | net(position_realized) |
|---|---:|---:|---:|
| 09-16 → 09-27 | 32 | 5 | -136.28 |
| 09-27 → 10-04 | 21 | 7 | -25.92 |
| 10-04 → 10-18 | 31 | 8 | -175.96 |
| **合计** | **84** | **20(23.8%)** | **-338.16** |

```
合并 z = (0.238 − 0.379) / sqrt(0.379×0.621/84) = −2.65
单侧二项 p ≈ 0.005
```

方向仍倾向"无优势",但**必须承认强聚类**:NEAR+UNI 占 61%,四个交易日占 90% 亏损。有效独立样本 < 84,所以 −2.65 是上界,实际显著性应更低。**引用时必须写成"中等偏弱证据,需分块 bootstrap 复核",不能写成"确凿"。**

> 备注:本轮 W1/W2 笔数与评审所引(33 / 22)差 1 笔,系窗口边界取整不同,不影响方向。

### 1.2 杠杆与单笔亏损 — 确认反比,但只在 `leveraged_cap` 绑定时成立

评审的公式推导正确。本轮用**日志实测**独立验证(而不是沿用公式):`decisions.jsonl` 的 `metadata.risk_budget` 逐条落了 `raw_notional` / `leveraged_cap_notional` / `remaining_exposure_notional` / `binding_cap` / `stop_pct` / `selected_leverage`,共 50 条 DIRECT/PROBE 记录。

**绑定分布(这是关键,与"杠杆决定风险"的直觉不同):**

| binding_cap | 条数 | 占 50 | 出现位置 |
|---|---:|---:|---|
| `remaining_exposure_notional` | 25 | 50% | 全在 PROBE,主要是 1x |
| `leveraged_cap_notional` | 16 | 32% | **DIRECT 14/14 全部**;PROBE 仅 2 |
| `raw_notional` | 9 | 18% | 全在 PROBE |

**DIRECT 的 1R 确实被 `0.75%/杠杆` 锁死,且与 `stop_pct` 完全无关:**

| 通道 / 杠杆 / 绑定 | stop_pct 区间 | 1R (USDT) | 1R / 权益 |
|---|---|---:|---:|
| DIRECT 4x,**lev_cap**(11 条) | 1.08% – 2.93% | **17.4 – 17.7** | **0.1875%** |
| DIRECT 5x,**lev_cap**(1 条) | 1.64% | 14.1 | 0.150% |
| PROBE 3x,**lev_cap**(2 条) | 1.44% – 2.05% | 23.6 | 0.250% |
| PROBE **raw**(9 条) | 1.06% – 2.09% | 13.9 – 14.1 | 0.150% |
| PROBE 1x,**remaining**(25 条) | 0.50% – 1.75% | 5.1 – 18.8 | 0.05% – 0.20% |

`stop_pct` 从 1.08% 变到 2.93%,DIRECT 的 1R 始终是 17.4–17.7——因为 `leveraged_cap` 绑定时 `final_notional × stop_pct = equity × 0.0075 / leverage`,`stop_pct` 被消掉。

```python
# src/signals/entry_chain.py:723-727
raw_notional            = equity * risk_pct / stop_pct
leveraged_cap_notional  = equity * max_single_trade_risk_pct / (stop_pct * leverage)
final_notional = min(raw_notional, leveraged_cap_notional, remaining_exposure)
```

**因此,评审的结论对 DIRECT 完全成立、对 PROBE 不成立。** 精确表述应当是:

- **DIRECT:** 降 1x → 1R 从 17.6 变 **69**(4 倍);杠杆是反方向的旋钮,且实盘会被保证金拒单。
- **PROBE:** 25/36 的样本体积由 **标的敞口上限**(约 1,880 USDT ≈ 20% 权益)决定,与杠杆、`stop_pct`、`risk_pct` **都无关**。改杠杆对这部分样本没有作用。
- 真正的跨通道倒挂是:**PROBE 3x(23.6)> DIRECT 4x(17.6)**,而不是"4x 放大亏损"。

代入实测:DIRECT 平均亏损 -19.00 vs 理论 17.6(外溢 8%,来自跳空与滑点),吻合。

### 1.3 通道排名三窗口翻转 — 确认

本轮独立重算(逐笔 `position_realized_pnl`):

| 通道 | W1 09-16→09-27 | W2 09-27→10-04 | W3 10-04→10-18 |
|---|---|---|---|
| main_direct (4x) | 5 笔,1 胜,**-18.78** | 5 笔,**4 胜**,**+78.29**(全场最佳) | 12 笔,2 胜,**-153.80**(全场最差) |
| main_probe (3x) | 12 笔,2 胜,-116.13 | 5 笔,0 胜,-103.58(最差) | 8 笔,3 胜,-37.78 |
| q1_trend_launch (1x) | 15 笔,2 胜,-1.37 | 11 笔,3 胜,-0.63 | 13 笔,3 胜,+1.02 |

direct 从"全场最佳"翻到"全场最差"只隔一个窗口。**任何按滚动胜率分配杠杆的方案都会追着噪声跑**,评审 Q4 的判断成立。

同时注意:`q1_trend_launch` 三个窗口合计 +1.02 ≈ 权益的 0.011%。它不是"有优势",是"仓位太小(固定 58 USDT 名义)"。

---

## 二、评审自身需要修正的三处

### 2.1 Q6 第 1 条的旋钮找错了:`direct_risk_pct` 从未生效,`probe_risk_pct` 与线上不一致

评审写:「`raw_notional` 与 `risk_pct` 线性,下调只会让最终仓位变小或不变」。前半句对,后半句**只在 `raw_notional` 是三项最小值时成立**,而实测:

| 通道 | `raw_notional` 绑定的条数 | `risk_pct` 是否真的起作用 |
|---|---:|---|
| DIRECT | **0 / 14** | **完全无效**。`raw/lev_cap = 0.01×杠杆/0.0075` ≥ 5.3,永远不是最小值 |
| PROBE | 9 / 36 | 部分有效 |

更进一步:PROBE 那 9 条 `raw` 绑定样本的 1R 稳定在 **13.9–14.1 USDT = 权益的 0.150%**,反解 `probe_risk_pct ≈ 0.0015`。但本地 `configs/entry_chain.dry_run_aggressive.json` 写的是 **0.004**。

`2026-10-04-PROBE` 的追踪记录显示 `probe_risk_pct` 曾从 0.0025 下调到 **0.0015**——**线上 profile 采用了下调后的值,本地仓库的 aggressive 文件没有同步**。这说明:本地配置不能当作线上行为的依据,任何"改配置"的提案在实施前必须先拉线上 profile 核对。

**结论:评审 Q6 第 1 条"统一每 R 风险预算并下调"必须重新表述**,否则会做一次静默无效的改动,并让人误以为风险已降:

> 把 `risk_pct` 从仓位决定式中**移除**;每笔风险改由显式 `risk_budget_pct` 决定,`max_single_trade_risk_pct` 只作为保证金约束的上限。同时把 `remaining_exposure_notional`(实际支配 50% 样本)与风险预算解耦,否则改 `risk_pct` 对一半样本无效。

### 2.2 附录 A 查询 1 可执行(但要读对文件),查询 5 不可执行

| 查询 | 评审假设 | 实测 |
|---|---|---|
| 1 | 读 12 笔 direct 的 `binding_cap`、`final_notional` | **可执行。** 字段在 `decisions.jsonl` 的 `metadata.risk_budget` 下(50 条 DIRECT/PROBE 全有值)。**但 `attribution.jsonl` 不复制该字段**(grep 命中 0),只读 attribution 会误判为"未落盘"——本文初稿即犯此错,已更正 |
| 5 | 读 31 笔的 `entry_price`、`stop_price`、`exit_price`、`stop_pct` | **不可执行。** `paper_trades.jsonl` 只有 `price`(出场价)、`gross_pnl`、`quantity`,**没有 `entry_price` 与 `stop_price`** |

`account_equity` 也不直接落盘,但可由 `leveraged_cap_notional × stop_pct × leverage / 0.0075` 反解(实测稳定在 9,255–9,451,与 `paper_equity.json` 一致),所以查询 1 的结论**不需要**额外埋点。

**仍需埋点的是逐笔 `entry_price` / `stop_price` / `planned_r` / `cost_r`**——没有它,逐笔 R 只能靠 `stop_pct` 近似,D8 的度量误差无法消除。

### 2.3 "降杠杆 → 3.2 倍亏损"需要限定作用域,并暴露一个独立缺陷

评审的算术正确,但漏了一个下游事实:

```python
# src/execution/live_entry_chain_adapter.py:46
quantity = decision.notional_hint / price        # 直接由名义金额换算数量
```

这条路径**不经过** `src/risk/position_sizer.py` 的保证金检查(`required_margin > available_margin` → 拒单,line 314)。后果:

- 1x 时 `final_notional = 1.5 × equity`,需要 150% 权益的保证金;
- **paper 模式**没有保证金约束 → 会真的成交,并产生 4 倍亏损(评审的结论成立);
- **实盘** → 保证金不足,被交易所拒单 → 变成"批量拒单",而不是"小仓位"。

两种结果都不是"更安全"。**当前这个缺陷是潜伏的**:实测最大名义金额 1,886 USDT ≈ 20% 权益,保证金充裕,所以今天不会触发;但任何"降杠杆"动作会立刻把它变成活跃缺陷。正确结论是:**降杠杆不是风险旋钮;而且 `live_entry_chain_adapter` 缺少保证金上限本身是独立缺陷**,必须在任何杠杆/预算改动之前补上。

另外 `margin_buffer_pct`(0.25)只被用作**准入闸门**(`available_margin < equity × 0.25` 则拒绝),不参与仓位上限计算,`_notional_cap_diagnostics` 的三个 `limits` 里没有保证金项。

---

## 三、D1–D10 的复核判定(相对评审的增量)

评审已给出判定,复核做两件事:**把"证据不足"改成"已证伪"**,并把口径写死。

| # | 评审判定 | 复核判定 | 实测 |
|---|---|---|---|
| D1 | 部分成立,"不可达"未证实 | **偏置成立,"不可达"证伪** | 全窗口 LONG 共 65,668 条,其中 `total_score ≥ 92` 有 **12 条**;两侧最高分同为 **96.2**。[82, 92) 有 **828 条**——这才是 offset 真正压住的池子 |
| D9 | 大概率误读,待查询 | **确认误读,证伪** | DIRECT 的 `risk_reward_geometry` 子分只出现 **6.5(34 次)与 5.0(18 次)**;5.0 档存在;"最高只能到 3.5"不成立。`net_tp1_r` 实测 1.10–1.13 |
| D6 | 成立,建议上调 P1 | **成立,且更彻底** | 10 月 26,960 条决策,`reasons[0]` = `FIB_PA_ARCHITECTURE_WEIGHTS` **100%** |
| D5 | 机制存在,无跨日记忆 | **成立,机制已定位** | `portfolio_state.cooldown_until_by_symbol` 是纯内存 dict,无 `to_dict`/无落盘;`paper_positions.json` 为 2 字节空对象 → 进程重启即失效 |
| D2 | 撤销 P0-3 | **同意,并补正机制** | 见 §1.2;真正的异常是 **probe(3x) 单笔风险 0.250% > direct(4x) 0.1875%**,不是"4x 放大" |
| D4 | 成立 | 同意 | 三套口径差 27.41;仅 `position_realized_pnl` 进台账 |
| D7 | 处方无效 | 同意 | UNI 4 笔 -78.61 = 权益 0.84%,2% 阈值永不触发 |
| D8 | 证据不足 | 同意,且**不可修复于当前数据** | 缺 `stop_price`,R 只能用 `stop_pct` 近似;先埋点 |
| D3 | 部分成立 | 同意 | 权重表 6 键是真的;`direction_from_history()` 已决定方向 |
| D10 | P2 | 同意 | 窗口内 Q2 仅 2 笔 +5.41 |

新增一条(评审未提):

| # | 缺陷 | 证据 | 影响 |
|---|---|---|---|
| **D11** | **`direct_risk_pct` 从未生效** | DIRECT 14/14 的 `binding_cap` 都是 `leveraged_cap_notional`,`raw_notional` 从未进 min | 基于 `direct_risk_pct` 的任何调整都是空操作,会让人误以为风险已降 |
| **D13** | **线上 profile 与本地配置漂移** | PROBE `raw` 绑定样本的 1R=14.1 = 权益 0.150%,反解 `probe_risk_pct≈0.0015`;本地 aggressive 文件写 0.004 | 本地配置不能作为线上行为依据;任何配置提案实施前须先拉线上 profile |

---

## 四、目标函数改写

评审对"80% 胜率不自洽"的算术成立,但把它当第一问题不够。按 1R = 0.1875% 权益反推 30 天收益目标所需单笔期望:

| 30 天笔数 | 1R 风险 0.1875% | 0.25% | 0.60% |
|---:|---:|---:|---:|
| 66 | E[R] ≥ 4.04 | 3.03 | 1.26 |
| 100 | 2.67 | 2.00 | 0.83 |
| 120 | 2.22 | 1.67 | 0.69 |

**"30 天 50%" 在现行风险预算下需要单笔期望 2–4R,不可达。** 这比"80% 胜率"更早失效。

建议目标(写入配置前需你确认):

```
目标:    maximize  E[R_net]                  # 扣成本,逐笔 R
约束 1:  block-bootstrap 80% 下界(E[R_net]) > 0   # n ≥ 100 才评估
约束 2:  30 天滚动最大回撤 ≤ 8%
约束 3:  平仓笔数 ≥ 60 / 30 天
仅诊断:  PF、胜率、1–2R 区间笔数、cost_R
阶段验收: 先到 E[R_net] ≥ +0.10R
```

---

## 五、修订后的优先级

| 编号 | 动作 | 阶段 | 判据 |
|---|---|---|---|
| P0-A | 埋点:逐笔 `entry_price`/`stop_price`/`planned_r`/`cost_r`;`account_equity` 直接落盘(现在靠反解) | 1 | 新窗口能直接回答附录 A 查询 5 |
| P0-B | 前向标签检验(66,304 条决策,32,091 条带五因子) | 2 | 写死判据见 §6 |
| P0-C | 账本单一化 + `|net − position_realized| > 0.5` 告警 | 1 | 归因与台账差 < 0.01 |
| P0-D | 冷却状态持久化 + 跨日"标的-方向"次数规则 | 1 | 重启后 cooldown 不丢;能解释 W3 四个坏日为何未被拦 |
| P0-E | 每笔风险改由 `risk_budget_pct` 决定(**先影子**) | 1 | 影子字段与现行 `final_notional` 并列落盘 30 天 |
| P1-1 | 出场离线配对回放 | 3 | 配对差异 bootstrap 区间 |
| P1-2 | LONG offset 分阶段放开(12 条 ≥92 / 828 条 [82,92)) | 3 | SCOUT 20 笔,占比 ≤40% |
| P1-3 | `primary_reason` 语义修复 | 1 | 拒绝原因可分层 |
| P1-4 | adapter 保证金上限 | 3 | 与 P0-E 同批 |
| P1-5 | 4h 否决门 | 3 | 标注数据分层验证 |
| P2 | 流动性分层成本、R 分布监控、D10 失败用例先行 | 3 | — |

**不做:** direct 降 1x、下调 `risk_pct`、按滚动胜率调杠杆、UNI 黑名单、统一 `long_threshold_offset`、`-k` 绕 TLS、以胜率或月收益为目标。

---

## 六、前向标签检验的判据(事先写死)

| 结果 | 动作 |
|---|---|
| 六因子与五因子的 `lift` 下界 ≤0,且 `IC` 在 3 窗口中 ≥2 个不为正 | 入场重做,起点为五因子 |
| `lift` 下界 >0,但实盘 R 分布显著差于标注 R | 出场/规模在浪费信号 → 出场配对回放 |
| 两者皆正 | 瓶颈在频次与成本 |
| 三窗口不一致 | 先做 regime 门 |

标注口径:`entry = 决策时间之后第一根 15m 开盘`,`R = entry_context.stop_pct`,`up=+1R / down=−1R / horizon=32 bars`,同 bar 双触及按最不利并计数,`R_net = R − 往返成本bps / stop_bps`,聚类块 `(symbol, date)` 做 block bootstrap。

局限已在设计里接受:不含排队与深度冲击、双触及无法判先后。因此判据用**下界 >0**,不用均值 >0。

### 6.1 检验已执行(2026-10-19)

数据来源修正:不需要联网——`decisions.jsonl` 每行自带该时刻 15m OHLC,单标的单日覆盖 96/96,窗口 08-24→10-18 共 66,279 条。

| 指标 | 结果 |
|---|---|
| 命中率 / `E[R]` | 49.73% / **−0.002** |
| `cost_R` / `E[R_net]` | 0.273 / **−0.275** |
| 六因子 IC(按日横截面) | **0.0012**(48 天,23 正) |
| 五因子 IC | 0.0256(22 天,16 正) |
| 各分档 `lift` | **全部 80% 上界 < 0**;`score≥92` lift −0.30(n=27) |
| 方向 / 象限 | 四个象限 `E[R]` 全在 ±0.023;LONG −0.006 vs SHORT +0.002 |

**落入"入场重做"分支。** 详细表见 `reports/analysis/fwd-label-20261019/report.md`。

额外结论(检验副产品):**负期望主要来自成本而非信号**。`E[R]` 在六个止损宽度档上都≈0,而 `cost_R = 0.002/stop_pct`;28.7% 的决策落在 0.5% 钳位下限上,`cost_R = 0.40R`。所以"把 `stop_pct` 钳位下限从 0.5% 上调"在算术上比任何入场改动都更直接——但它只降摩擦,不产生 alpha。

---

## 七、EigenFlux 侧

1. **不发布。** 证书无有效 SAN、只有 `-k` 能通,更像链路中间设备替换证书;`publish` 携带 `--origin owner` 身份,不应经该通道发送。
2. 草稿中「4x 通道胜率 16.7%、吃掉 87% 亏损」「杠杆与通道质量反挂」两句**已失效**,替换为:"单笔风险恒定于 `0.75%/杠杆`(direct 0.1875%、probe 0.250%),杠杆不影响单笔美元风险,只影响保证金占用;通道表现三个窗口间翻转,不能用滚动胜率分配规模。"
3. 三个外呼问题里,breakeven 阈值、高胜率目标的出场结构、杠杆分配**都可用本地数据回答**,不再对外提问;只保留"日频交易成本与滑点实测"这一个真正需要外部样本的问题。

---

## 附:本轮全部查询口径(可复现)

| # | 口径 | 脚本/命令 |
|---|---|---|
| 1 | 逐笔 1R = `metadata.risk_budget.final_notional × stop_pct`;绑定分布直接读 `binding_cap` | `decisions.jsonl` 全量,DIRECT/PROBE 行(10 月共 50 条) |
| 2 | LONG 各分数档计数 | `deeps=score_detail.total_score`,按 `entry_context.side` 分组 |
| 3 | RR 子分分布 | `score_detail.points.risk_reward_geometry` |
| 4 | `reasons[0]` 分布 | `decisions.jsonl` 全量 |
| 5 | 三窗口通道表现 | `paper_trades.jsonl`,`position_realized_pnl` |
| 6 | 冷却状态持久化 | `src/signals/portfolio_state.py` + `paper_positions.json` 内容 |

**不可执行:附录 A 查询 5(逐笔 `stop_price`)、查询 6(三窗口 R 盈亏比,因 R 只能用 `stop_pct` 中位数近似)。** 两项转入 P0-A 埋点。查询 1 可执行,前提是读 `decisions.jsonl` 而非 `attribution.jsonl`。
