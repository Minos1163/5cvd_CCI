# 20261121 实施计划：口径校正 + 评分缺陷修复

> 依据：用户提供的《AI300 策略优化建议》（A–E 五主题）+ 本地复算（`logs/2026-11/*`）。
> 硬约束：VPS `/root/AIBOT` 在跑，用户手动重启；推送 `20261121` 分支。

## 0. 先校正三个事实（复算结果，与建议文档有出入）

### 0.1 "重启后"的口径实际跨了两套代码

建议文档的 47 笔 / −76.72 / 21.28% / PF 0.727，复算**逐位吻合**，但起点是 **2026-11-14 00:00 UTC**，而最后一次 `process_start` 在 **11-14 22:05:37 UTC**。

| 分组 | 笔数 | 净额 | 胜率 |
|---|---:|---:|---:|
| 全部（11-14 00:00 起） | 47 | **−76.72** | 21.3% |
| 旧代码（<22:05） | 5 | **+108.44** | 80.0% |
| **新代码（≥22:05）** | **42** | **−185.16** | **14.3%** |

**结论：−76.72 被 5 笔旧代码（+108.44）掩盖了。新代码的真实表现是 −185.16、胜率 14.3%、PF 0.327。** 后续任何结论都必须按 `entry_ts` 与重启点切分，不能混算。

其余分组复算与文档一致：TP3 6 笔 +177.58、COST_BREAKEVEN_TIMEOUT 14 笔 −69.23、INITIAL_STOP_HIT 16 笔 −208.71、main_direct +58.09 / q1 −5.58 / main_probe −129.23、有减仓 12 笔 +203.70 / 无减仓 35 笔 −280.41。

### 0.2 "时间对齐事故"不在生产代码里

| 匹配 offset | Spearman(score, net) |
|---|---:|
| **0（`entry_time == kline.timestamp`）** | **−0.0051** |
| −900s（前一根 K 线） | −0.3316 |
| +900s | +0.1168 |

`paper_trades` 的 `entry_time` 与 `decisions` 的 `kline.timestamp` **差 0 秒**（49 笔抽样全命中）。ρ=−0.332 是**分析脚本**用了 `timestamp − 900` 造成的伪相关，生产链路无此问题。

**所以"修正对齐"不是代码任务。** 但要在分析脚本里锁死正确口径，防止再次误用。

### 0.3 CVD 不是"不参与计算"，是零方差

47 笔 `flow_cvd_confirmation` **全部 18.0**，方差 0。秩相关里它贡献恒为 0。18% 权重对已成交样本完全无效——但它在**准入**上起作用（3.6 档的候选进不来），所以不能简单删除，只能改造。

## 1. 诊断：四个真问题

| # | 问题 | 证据 | 性质 |
|---|---|---|---|
| D1 | **总分无判别力** | ρ=−0.005 (p=0.97, n=47)；分项中仅 RR 有信号且为负 | 结构性 |
| D2 | **RR 因子方向反了** | ρ=−0.250；且该因子对止损宽度单调递增（11-14 已证：Spearman(stop_pct, rr)=+0.859） | 实现缺陷 |
| D3 | **CVD 零方差** | 47/47 = 18.0 | 实现缺陷 |
| D4 | **入场即错占主导** | 16 笔初始止损 −208.71；MFE < 0.4R 是主群；能到 TP1 的 12 笔赚 +203.70 | 信号质量问题 |

D4 不是一两周能解决的（需要换信号源）。本轮聚焦 D1–D3 的**可修部分**。

## 2. 修复方案（分层，全部可回滚）

### P0：口径与工具（零行为变化）

- **P0-1 账本分段**：报告与归因脚本必须支持按 `process_start` 切分新旧代码，禁止混算。新增 `--since-utc` / `--since-restart` 参数到 `scripts/analysis/` 归因脚本。
- **P0-2 负控套件**（建议文档 §3 要求）：新增 `tests/test_negative_controls.py`，至少三条 must-fail：
  1. **方向反转**：把 SIGNAL 方向取反后重算 net R，期望显著为负
  2. **分数打乱**：把 score 随机置换后，ρ 应回落至 0±噪声
  3. **常量 CVD**：把 CVD 固定为 18 后，总分排序应与原排序**完全一致**（证明该分量零信息）
- **P0-3 统计工具**：`scripts/analysis/stat_tools.py` — Spearman（含并列秩）、block bootstrap（按 `symbol|utc_day`）、置换检验。纯标准库。
- **P0-4 对齐守卫**：分析脚本入口断言 `entry_time == kline.timestamp`，不等则报错而非静默偏移。

### P1：评分缺陷修复（**改行为**，三态开关，默认 shadow）

新增配置 `scoring_repair_v2: str = "shadow"`，三态：

| 值 | 行为 |
|---|---|
| `off` | 与当前逐位一致，不计算新分数 |
| **`shadow`（默认）** | 计算新分数并写入 payload（`repair_v2_score` / `repair_v2_components`），**`action` 与 `score` 仍用旧值** |
| `on` | 新分数生效 |

**为什么默认 shadow 而不是直接 on**：47 笔（新代码 42 笔）不足以支撑任何评分改动的效果判断；而 `opposition_dist_r` 在 `decisions.jsonl` 里根本没记录（只 `near_misses` 有），无法用历史成交预演影响面。先跑一周 shadow 收集"新分数 vs 实际结果"，再决定是否 `on`。

#### P1-1 RR 因子重定义（两段式，解决 50% 缺失）

可行性检查结果：`near_misses` 91 个样本里 `opposition_dist_r` **49.5% 为 null**（找不到最近反向结构位）；有值的 46 个中位 1.10R、p75 1.44R、max 3.08R。

因此**不能**用 `opposition_dist_r` 单独做主打分（一半样本归零）。改为：

```
base = 4.0  if 0.008 <= atr_pct <= 0.025
     = 2.0  if 0.005 <= atr_pct < 0.008
     = 1.0  otherwise
# base 保留"ATR 是否在可交易区间"的判断，与当前实现同源

bonus = 0.0                                  if opposition_dist_r is None
      = 4.0 if opposition_dist_r >= 2.0
      = 3.0 if >= 1.5
      = 1.5 if >= 1.0
      = 0.5 if >= 0.7
      = 0.0 otherwise

rr_score_v2 = clamp(base + bonus, 0, 8)
```

- 缺失只损失"加分"，不归零
- 方向正确：到反向结构位之前的 R 空间越大，分越高
- 与止损宽度**解耦**（旧公式 `1.2 − cost/stop_pct` 是止损宽度代理，ρ=+0.859 已证）

#### P1-2 CVD 连续化

旧实现只输出 1.0 / 0.2（二值）；47 笔全部落在 1.0（18 分），方差 0。

新实现：

```
signed_ratio = Σ(sign(close-open) × volume) / Σ(volume)   # 最近 6 根 15m，值域 [-1,1]
aligned = signed_ratio if side==LONG else -signed_ratio    # 与持仓方向一致性
score_norm = clamp(0.5 + 0.5×aligned, 0, 1)
cvd_score_v2 = score_norm × 18
```

保留原始 `signed_ratio` 到日志。**不接真实 taker flow**：Binance K 线接口不直接给 taker buy volume，需另找数据源（P2）。

#### P1-3 权重再分配

| 因子 | 当前 | v2 |
|---|---:|---:|
| `risk_reward_geometry` | 8 | **12** |
| `flow_cvd_confirmation` | 18 | **14** |
| `price_action_structure` | 22 | **20** |
| 其余三项 | 52 | 52 |
| 合计 | 100 | 100 |

**理由**：RR 是唯一有信号的因子（虽然方向是负的），改造后应给更大话语权；CVD 改造后仍是最弱环，降权；PA 区分度（ρ=+0.120）不足以支撑 22 分。

### P2：不做（登记）

- 权重重拟合（47 笔无功效）
- 阈值调整（会砍右尾）
- main_probe 停用（19 笔不足以判死）
- RSI/MACD/BOLL 接线（无增量证据）
- 真实 taker flow 接入（Binance K 线不直接给 taker buy volume，需另找数据源）

## 3. 验证要求

1. 全量 pytest 全绿（基线 1107 + 新增）
2. **P0 零行为变化**：47 笔重放，`action`/`score`/`notional`/`leverage` 逐位相同（`scoring_repair_v2=false`）
3. **负控必红**：三条 must-fail 在 `scoring_repair_v2=true` 与 `false` 下都必须给出"预期方向"的负结果——若负控变正，说明修复引入了伪信号
4. **P1 影响面量化**：`scoring_repair_v2=true/false` 两版在同一批 47 笔上，给出 action 变化数、score 分布差异、若重放会多/少几笔
5. 配置只改一处：新增 `scoring_repair_v2`（默认 `false`）

## 4. 上线与回滚

- 分支 `20261121`，推送 origin
- VPS：`/root/AIBOT`，`git fetch` + 切分支 + 用户手动重启
- **默认 `scoring_repair_v2=false`**，重启后行为与当前一致；确认无异常后再单独打开
- 回滚：`git reset --hard <记录点>` + 重启
