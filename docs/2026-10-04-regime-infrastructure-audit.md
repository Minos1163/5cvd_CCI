# Regime 基础设施核查备忘录(Task R0)

**日期:** 2026-10-04
**依据:** 2026-10-04 评审裁定第五节 R0("核查 BTC Beta Risk Scorer / Market Breadth Detector 代码现状,确认可复用范围")
**性质:** 只读核查,不含代码变更

---

## 一、核查结论(先给答案)

| 核查项 | 结论 |
|---|---|
| **BTC Beta Risk Scorer** | **代码已不存在**(架构迁移时移除) |
| **Market Breadth Detector** | **代码已不存在** |
| 历史设计文档 | **存在**(2026-06/07 多份 + 2026-08-24 两份专项设计) |
| 运行数据(breadth) | **从未落地**:全窗口 `decisions.jsonl` 中 `breadth` 出现 **0 次**,`slow_bull` **0 次** |
| 可复用的**现成输入** | **有**:`market_snapshot` 已含 `btc_daily_return` / `btc_weekly_return` / `usdt_premium` |

**核心判断**:评审 5.2 节设想的"零成本复用历史基础设施"**不成立**;但 regime 门**不必从零设计**——项目在 2026-08-24 已独立演进出一条 regime 赛道(设计 + shadow 脚本 + 追踪表条目),R1–R4 应**衔接**它,工程量可显著低于"完全新建"。

---

## 二、代码层核查(逐项)

```powershell
# 全库检索:以下模式在 src/ 中均无匹配(breadth / BetaRisk / beta_risk / regime_gate)
```

| 残留物 | 位置 | 性质 |
|---|---|---|
| `"market_regime": 0.8` | `src/signals/entry_chain_features.py:52` | **硬编码常量**(旧评分的一个分量,权重 2.0,恒为 0.8,不含任何真实计算) |
| `"market_regime"` 列名 | `src/backtest/protocol.py:77` | 协议字段残留 |
| `market_regime_history` 表名 | `src/data/database_schema.py:264` | schema 残留(无写入实现) |
| `market_regime` 权重键 | `src/signals/entry_chain_scoring.py:16/27/40` | 旧评分权重表条目 |

**运行期实测**:`state` 中当前 decisions.jsonl 的 `market_snapshot` 只有三个字段:

```json
{"btc_daily_return": 0.0, "btc_weekly_return": 0.0, "usdt_premium": 0.0}
```

> 注:本机 dry-run 的 synthetic 模式下这三项恒为 0;VPS 真实运行时会由 `synthetic_market_snapshot()` 之外的分支填充真实值。**无论哪种情况,breadth 都不在其中。**

**结论**:`market_regime` 这个键在旧评分里占 2 分,但它是一个**常量**,不携带任何市场状态信息 —— 这就是 2026-09-27 归因报告所说"评分完全基于单币种局部结构"的代码级证据之一。

---

## 三、文档层核查(设计存在)

| 文档 | 内容 | 与本任务的关系 |
|---|---|---|
| `docs/2026-06-19-ema-vs-rsi-indicator-recommendation.md:375` | 提及 "Market Breadth Detector ✅ 完全兼容" | 历史评估,**无实现** |
| `docs/2026-06-27-01-deep-research-report.md:134-140` | `slow_bull_transition_long_watch` / `slow_bull_long_momentum_watch` 等标签 | 历史 slow-bull 状态机设计 |
| **`docs/2026-08-24-bull-regime-breakout-design.md`** | **`BULL_REGIME_BREAKOUT_V1`**:breadth ≥5 symbols / 6h 确认突破;上层 `regime_gate` | **最接近本需求的既有设计** |
| **`docs/2026-08-24-regime-conditional-side-offset-design.md`** | regime 条件化的方向偏移设计 | 直接对应"按 regime 调整方向阈值" |
| `docs/2026-08-24-bull-regime-miss-and-short-bias-audit.md` | breadth 门槛为何取 5/6h 而非 4/6h 的论证;并明确"不凭 N=1 事件拍板" | **R1 可直接继承的参数论证** |
| `docs/superpowers/reports/2026-09-15-direction-asymmetry-risk-gate-implementation.md:64,76` | 实测:`market_snapshot` 没有 breadth 字段,`breadth confirmed = 0` 样本 | **数据缺失的直接证据** |

---

## 四、脚本与追踪表(已有 shadow 资产)

| 资产 | 状态 |
|---|---|
| `scripts/regime_conditional_short_offset_shadow.py` | 已实现(shadow 反事实:regime 条件下 SHORT offset 的拦截效果) |
| `scripts/audit_bullish_regime_short_bias.py` | 已实现(bullish 窗口 SHORT/LONG 可执行率审计) |
| `scripts/channel_cumulative_tracker.py` | 已纳管 2 条 shadow 通道(样本 0) |
| 追踪表 `2026-08-24-BULLREGIME` | **DEPLOYED**(设计完成 + tracker 纳管) |
| 追踪表 `2026-08-24-SHORTBIAS` | **DEPLOYED**(审计 + shadow 反事实;live 门槛未动) |

---

## 五、对 R1–R4 的工程量修正建议

| 阶段 | 评审原设想 | 核查后的修正 |
|---|---|---|
| **R0** | 核查能否复用 | ✅ 本备忘录:代码不存在;但既有赛道可衔接 |
| **R1** 定义最小信号集 | 从零定义 | **可继承**:breadth 5/6h 门槛论证已存在(08-24 报告第 5 节);**新增可用输入**:`market_snapshot.btc_daily_return` / `btc_weekly_return` 已现成 → "BTC 趋势方向与强度"信号无需新接口 |
| **R2** 影子记录 | 新增 `regime_context_v1` 字段 | 建议与 `component_points_v2` 同一批落盘;**须补 breadth 计算**(这是唯一真正新增的计算,但不需新外部接口——用现有 13 个 symbol 的 15m K 线即可算"多少标的同向") |
| **R3** 回溯验证 | 用 09-16~10-04 两窗口事后验证 | ⚠️ **有限制**:两窗口日志中 breadth 从未记录 → 回溯只能用 `btc_daily_return`/`btc_weekly_return`(若 VPS 有真实值)或**重算 breadth**;纯日志回溯不可行 |
| **R4** 评审接入 | 20 笔门槛 | 沿用;但需在 R1 明确统计单位(窗口级 regime 判断次数 vs 单笔交易) |

---

## 六、跨设计一致性提醒(评审 5.4 节)

`F6`(拥挤度/资金成本,已延后)与 regime 门在**资金费率**维度上重叠:

- F6 是**单币**拥挤度;**regime 门**若纳入资金费率则是**全市场均值**;
- 两者共用同一外部接口(`/fapi/v1/premiumIndex`)。

建议 **R1 阶段一并设计容错**,避免对同一新外部依赖做两次独立容错——呼应五因子裁定报告第二节"新增外部依赖须先证明容错"(2026-08-13 data_health 粘滞降级事故的教训)。

**当前建议**:R1 首版**不含资金费率**(只用 BTC 收益 + breadth 重算),把 funding 留给 F6 的单独接入,避免两个未验证的数据源同时上线。

---

## 七、可复现核查命令

```powershell
# 1) 代码层:以下模式均无匹配
Select-String -Path src/**/*.py -Pattern "breadth|BetaRisk|beta_risk|regime_gate"
# 2) 常量残留
Select-String -Path src/signals/entry_chain_features.py -Pattern "market_regime"
# 3) 运行数据:breadth 从未出现
Get-ChildItem logs/2026-09,logs/2026-10 -Recurse -Filter decisions.jsonl |
  ForEach-Object { Select-String -Path $_.FullName -Pattern '"breadth"' -AllMatches }
# 4) market_snapshot 现有字段
(Get-Content logs/2026-10/2026-10-02/decisions.jsonl -TotalCount 1 | ConvertFrom-Json).market_snapshot
```

---

## 八、结论一句话

**历史 BTC Beta / Breadth 基础设施已不可复用(代码不存在、数据从未落地),但 regime 门有既成的设计与 shadow 资产可以衔接,且"BTC 趋势"维度有现成输入(`market_snapshot`)——R1 的真实新增工作只剩"用现有 K 线重算 breadth"这一项。**
