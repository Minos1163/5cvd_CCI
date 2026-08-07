# AI300 ATOM 牛市漏选归因与进攻优化 — 待 Claude 评审

**提交对象:** Claude 评审
**分析窗口:** 2026-08-02 04:00 ~ 2026-08-05 11:00(北京时间,ATOM 牛市段);基线统计覆盖 08-02~08-07。
**目标:** 为什么开仓这么少、为什么没选出 ATOM 这段牛市;优化到能选出并盈利。
**版本:** v2(2026-08-07)—— 已按 Claude 评审意见修订:三项改动全部回滚,ATOM 改走完整链验证后**不予准入**。

---

## 0. v2 修订摘要(响应 Claude 评审)

评审结论:诊断部分(符号层/分数层/闸门层逐层定位)认可;方案部分批评三点——①`long_threshold_offset` 归零与 HIGH_SCORE_LONG_OFFSET_PROBE 探针 3 笔 PF=0 直接矛盾(决策没等数据);②rank_end 90 用大炮打蚊子(13→83 币);③N=1 回放证据不足且为简化闸门链。

v2 修订(全部落实):
1. **回滚三项改动**:`dry_run_rank_end` 90→**25**、顶层 `long_threshold_offset` 0→**10.0**、`scout_micro_targeted_long_symbols` 移除 ATOMUSDT;
2. **完整链重放(评审 8.2)**:用 `run_offline_backtest --strategy entry-chain`(完整闸门链)重放 ATOM 08-02~08-05——**那笔 PROBE_OPEN 不成立**:引擎方向判定用 1h 序列(`direction_from_history(completed["1h"])`),08-02 09:45 北京 1h 方向 NONE → 引擎输出 NO_TRADE(score 17.6)。简化回放用 15m 方向,高估了信号确定性——**评审的担忧被证实**;
3. **90 天扩大回放**:ATOM 回滚后配置下 LONG 0 可开、仅 1 笔 SHORT PROBE_OPEN(07-31),候选数远低于准入最小样本 20;
4. **显式白名单机制(评审 7.2)已代码实现**:`explicit_watchlist` 配置结构 + 校验 + `evaluate_watchlist_candidate.py`(样本≥20 且 PF≥1.0 → scout_only 准入);
5. **ATOM 准入决策:REJECT**(完整链不成立 + 候选 1 笔 + 无 PF 证据)——不添加白名单、不扩 rank;
6. **TONUSDT 零行排查**:数据完整(384 根无缺口),根因是窗口内价格波动近零(1 根变化率 p90=0.0)→ 方向判定 100% NONE → rows=0 是**正确行为**,非缺陷。

---

## 1. 结论摘要

1. **ATOM 从未进入系统扫描宇宙**:08-01~08-07 `decisions.jsonl` 中 `ATOMUSDT` **0 条决策**。系统 `market_cap_rank` 取 rank 3-25,而 ATOM(Cosmos Hub)实时市值排名**第 83 位**(CoinGecko 2026-08 确认,价格 1.34 USD)——符号层排除是第一根因。
2. **即使纳入,策略层也会拦住**:用系统评分链(FIB-PA 架构)离线回放 ATOM 08-02~08-05,牛市段 96 个 LONG 周期中:
   - 最高分 87.3(08-02 09:45 北京,Q3),而 LONG 的 direct 门槛 = 82 + `long_threshold_offset 10.0` = **92 → 结构性不可达**;
   - 唯一 87.3 高分样本的 `risk_reward_geometry` 组件仅 2.0/8(满分 8),被 DIRECT 闸门(`rr_min_direct_score=4.0`)**降级为 PROBE**。
3. **优化三项配置后,ATOM 牛市段可选出 1 笔 PROBE_OPEN**(08-02 09:45 LONG,87.3 分),按系统出场规则模拟**盈利 +1.44R**(4 根内 TP 1.2/2/3R 全中,快进快出)。
4. 优化方向遵守既有护栏:**不降 RR 几何门槛**(DIRECT 仍需 rr≥4),高分低 rr 样本走 SCOUT probe 小仓验证;**不解除黑名单**。
5. 全宇宙对比(13 币 + ATOM,08-02~08-05 回放):见第 5 节表格(回放产出后填写)。

## 2. 现状:为什么开仓这么少

72H 实际运行(VPS `evaluate_offense_fixes.py`,08-05 前后)与 6 天日志统计:

| 通道 | 开仓 | 平仓 | PnL | 说明 |
|---|---:|---:|---:|---|
| 主账本 q1_trend_launch | 1 | 1 | -0.0001 | 唯一主账本开仓,近乎打平 |
| HIGH_SCORE_LONG_OFFSET_PROBE | 3 | 3 | -0.5684 | PF 0 |
| A/B mirror legacy | 32 | 32 | -1.2723 | PF 0.2266 |
| A/B mirror trend | 32 | 32 | -1.5799 | PF 0.0397 |
| **基线统计(08-02~08-07,6 天)** | | | | |
| decisions | 6890 | — | — | Q1=794/Q2=972/Q3=1419/Q4=3705 |
| 主账本 paper_trades 开仓 | **2** | — | — | WATCH=794 / NO_TRADE=6094 / PROBE=2 |
| ≥85 高分决策 | 30 | — | — | 全部未开仓 |

主账本进攻通道近乎空转 + 实验通道全部负期望 = "进攻策略未实现"。

## 3. ATOM 牛市段复盘(数据核对)

用 Binance 真实 15m K 线 + 系统 CCI(period=20)重建 08-02~08-05:

| 关键节点(北京时间) | 数据核对 |
|---|---|
| 起涨 08-02 04:00 | close=1.219,CCI≈13(接近 0,起涨点吻合) |
| 价格 08-02→08-05 | 1.219 → 1.376,**+12.9%**,明确牛市段 |
| CCI 峰值 | 08-02 21:00,cci=310(用户称 08-04 00:00 见顶;该点系统 CCI=94.9——**口径差异**,用户可能用不同周期/平台 CCI) |
| 08-05 11:00 | close=1.366,cci=-96.3(用户称跌穿 -100;系统首次跌穿在 08-02 13:30) |
| CCI 谷 | 08-05 06:30,cci=-379.5 |

结论:行情客观存在(价格 +12.9%),用户对 CCI 顶/跌穿时点的描述与系统 20 周期 CCI 有偏差(周期/平台差异),不影响"这是明确多头段"的判断。

## 4. 根因逐层定位

### 4.1 符号层(0 决策的直接原因)
- 运行时 symbol 宇宙 = `market_cap_rank` rank 3-25(过滤后 13 币),`fallback=False` 源正常;
- ATOM 排名 83 → 从未被扫描 → 任何周期 0 决策。

### 4.2 分数层(纳入后仍不可达)
ATOM 离线回放(旧配置)牛市段 LONG 96 个周期:
- 门槛敏感性:direct=82/85 可开 1 笔;88/90/92 均 0 笔;
- 最高分 87.3 < LONG direct 门槛 92(LONG offset +10)→ **结构性不可达**;
- Q1 的 LONG 周期(13 个)最高仅 72.59;趋势轴 80/96 达标,不是主瓶颈;
- 组件层:`fibonacci_location` 牛市启动段频繁 0 分(价格在 fib 区间外=防追高,设计使然)、CCI 过热段 `cci_momentum_quality` 低分。

### 4.3 闸门层(分数够也被降级)
- DIRECT 最低组件要求:pa≥6、fib≥9、**rr≥4**;
- ATOM 87.3 样本:pa=21 ✓、fib=18 ✓、**rr=2.0 ✗** → DIRECT 降级;
- PROBE 门槛:score≥72、fib≥12、pa≥6 → **全部通过 → PROBE_OPEN(小仓)**;
- ATOM 不在 HIGH_BETA(仅 HYPE/LAB/CC),无额外 rr 门槛。

## 5. 优化改动与验证

> **v2 状态:本节描述的改动(5.1)已全部回滚**(评审 7.1),保留历史记录供对照;5.2-5.4 的验证证据更新为完整链结论。

### 5.1 配置改动(3 项,`configs/entry_chain.dry_run_fib_pa_v1.json`)— 已回滚
| 键 | 原值 | 曾改为 | 回滚至 | 评审理由 |
|---|---|---|---|---|
| `dry_run_rank_end` | 25 | 90 | **25** | 13→83 币影响面过大,唯一价值点是 ATOM 单符号 → 改显式白名单 |
| 顶层 `long_threshold_offset` | 10.0 | 0.0 | **10.0** | 与探针 3 笔 PF=0 矛盾,决策没等数据 → 恢复,等 probe 20 笔 |
| `scout_micro_targeted_long_symbols` | (9 币) | +ATOMUSDT | **(9 币)** | ATOM 完整链验证不成立 → 移除 |

### 5.2 ATOM 完整链验证(评审 8.2,取代简化回放)
- **简化回放结论(已作废)**:08-02 09:45 LONG 87.3 → PROBE_OPEN,模拟 +1.44R;
- **完整链重放(`run_offline_backtest --strategy entry-chain`)**:同一时刻引擎输出 `NO_TRADE`(side=NONE, score=17.6)——差异根源:引擎方向判定用 **1h 序列**(`direction_from_history(completed["1h"])`),08-02 09:45 北京 1h 方向未确认;简化回放用 15m 方向,高估了信号确定性;
- **结论:该笔在真实链路下不成立**,+1.44R 属简化回放的方向误判(评审:"简化版和完整版之间的差异可能恰好决定这笔交易能否真正触发"——已被证实)。
- 完整链 8 天回放(signal_events.csv 633 条)全部 SIGNAL_REJECTED,trade_count=0。

### 5.3 90 天扩大回放(回滚后配置,数据覆盖 07-08~08-05)
- LONG 侧:**0 笔可开**(92 门槛结构性不可达,与回滚一致);
- SHORT 侧:1 笔 PROBE_OPEN(07-31 04:30,86.7 分);
- 候选数 1 ≪ 20(准入最小样本),无 PF 证据——**非牛市段无机会,牛市段样本又不成立**。

### 5.4 全宇宙对比(历史记录,新配置回放)
<!-- 保留 v1 回放表供评审对照,结论已被 5.2/5.3 取代 -->
| symbol | rows | DIRECT_OPEN | PROBE_OPEN | WATCH | NO_TRADE |
|---|---:|---:|---:|---:|---:|
| ADAUSDT | 236 | 0 | 3 | 75 | 158 |
| ATOMUSDT | 170 | 0 | **1** | 24 | 145 |
| BNBUSDT | 60 | 0 | 3 | 14 | 43 |
| CCUSDT | 156 | 0 | 0 | 42 | 114 |
| DOGEUSDT | 96 | 0 | 2 | 35 | 59 |
| HYPEUSDT | 184 | 0 | 0 | 57 | 127 |
| LABUSDT | 253 | 0 | 0 | 40 | 213 |
| LINKUSDT | 133 | 0 | 3 | 45 | 85 |
| SOLUSDT | 121 | 0 | 1 | 38 | 82 |
| TONUSDT | 0 | 0 | 0 | 0 | 0 |
| TRXUSDT | 16 | 0 | 0 | 5 | 11 |
| XLMUSDT | 142 | 0 | 1 | 44 | 97 |
| XMRUSDT | 103 | 0 | 1 | 28 | 74 |
| XRPUSDT | 81 | 0 | 3 | 27 | 51 |
| ZECUSDT | 199 | 1 | 0 | 72 | 126 |
| **合计** | | **1** | **18** | **546** | |

- 对比基线(实际运行 6 天主账本 **2 笔**开仓):新配置 4 天回放产生 **1 DIRECT + 18 PROBE 候选**;
- 需过滤:ZEC 的 DIRECT 与 XRP 的 PROBE 会被符号策略(黑名单)拦截 → 净可执行 ≈ **17 PROBE + 0 DIRECT**;
- 候选集中在 Q1/Q3 高分样本(SOL 90.1、XRP 90.1、BNB 87.3 等),符合"进攻"目标;probe 单笔小仓,`max_active_probes=2` 限制并发;
- TONUSDT 窗口内 rows=0(方向长期 NONE 或数据边界,待查);
- **口径声明**:回放为"候选数"(分数+关键闸门),未模拟 symbol policy/SCOUT 路由/max_active_probes 等完整链,实际成交会小于候选数。

## 6. 残留风险与待评审问题(v2 已更新)

1. ~~**rank_end 90 影响面**~~ **已解决**:回滚至 25;新增 `explicit_watchlist` 显式白名单机制(评审 7.2 规格,代码已实现:配置结构 + 校验 + `evaluate_watchlist_candidate.py`),未来错失案例逐一走"样本≥20 且 PF≥1.0 → scout_only 准入"流程,不再批量扩 rank。
2. ~~**LONG offset 归零**~~ **已解决**:恢复 10.0(probe 层 7.0 保留);按评审 8.1 决策树,继续 HIGH_SCORE_LONG_OFFSET_PROBE 至 20 笔后(PF>1.0 且 blended_R>0.3 → 考虑校准;PF<0.8 → 维持 10.0;中间 → 观察至 30 笔)。
3. **87.3 样本方向可靠性(新)**:完整链验证显示该样本在 1h 方向确认下不成立——**15m 方向的高分信号不可直接信任**,后续分析统一用完整链口径(方向=1h 确认);这是本次评审最重要的方法学收获。
4. **fib 启动段 0 分**:不改(防追高设计;08-02 13:00 fib=0 后确实先回调),避免过拟合单段。
5. **样本量**:ATOM 完整链 90 天候选仅 1 笔,统计显著性不足;白名单机制以 min_samples=20 强制样本门槛,不达标一律 REJECT。
6. **TONUSDT**:排查结论为非缺陷(窗口内价格波动近零 → 方向 NONE → 0 决策),维持 observation_only 观察。

## 7. 数据口径与局限(v2 更新)
- 时间:北京=UTC+8;ATOM K 线 30d/90d 由 Binance fapi 拉取(2026-08-07 本地);
- **完整链重放**:`run_offline_backtest --strategy entry-chain`(真实 evaluate_entry_chain + 闸门链),方向判定为 1h 确认(与线上一致);
- **简化回放(replay_symbol_chain.py)仅作候选筛选上限参考**:其 15m 方向判定高估信号确定性,凡与完整链冲突处以完整链为准;
- 完整链 8 天 ATOM 回放 633 条信号全 REJECTED、trade_count=0(该窗口 ATOM 在真实链路下无可执行信号);
- 90 天回放数据源为最近 30 天 K 线(07-08~08-05 有效窗口),结论不构成长期统计。
