# P1 测量层落地报告（2026-11-09）

> 依据：`docs/AI300_strategy_optimization_advice.md`（ChatGPT 建议 V1.0）§12(E0/E1/E6/E7)、
> §16.5、附录 A/B；以及 `docs/analysis/2026-10-31_to_11-08_loss_attribution.md`（已封版）。
> 分支 `20261109-v1`，基线 `5e2a2e0`（P0 总验收）。
> **本文件只做测量与登记，不改任何交易参数、不碰 `binance_client.py`。**

## 0. 一句话结论

建议文档要求的"可复核度量"已经落成两层：**账本度量报告器**（仓位级重建 + 集中度 + 成本压力 + 块 bootstrap）
与**配置接线审计器**（静态+动态两遍扫描）。在 2026-10-31→11-08 窗口上，前者**逐位复现**了已封版归因报告的
全部头条数字；后者查出 **16 个配置字段两遍扫描都不可见**，其中 `fib_swing_*` 五个键与建议文档 §13.5.9
的怀疑完全吻合。

同时发现**一处文档与数据不一致**，需要显式裁决：建议文档 §2.2 称"聚类后 Wilson 区间仍覆盖打平胜率"，
本地复算**不支持**这个表述（详见 §4.3）。总体结论"未确立边际"不变，但要换依据。

---

## 1. 交付物

| 类型 | 路径 | 作用 |
|---|---|---|
| 模块 | `src/reporting/ledger_metrics.py` | 事件流→仓位级记录；集中度/成本/样本/区间的纯函数 |
| 脚本 | `scripts/report_strategy_review.py` | CLI：按 ledger + 窗口出 JSON/Markdown |
| 脚本 | `scripts/audit_config_wiring.py` | CLI：`EntryChainConfig` 字段→读取点三态矩阵 |
| 测试 | `tests/test_ledger_metrics.py` (16) | 口径锁：full-cost、双分母、块 bootstrap、INCONCLUSIVE |
| 测试 | `tests/test_config_wiring_audit.py` (16) | 三态分类、getattr/vars 识别、未知键 |
| 产物 | `reports/review_{main,ab-legacy,ab-trend}_1031_1108.{json,md}` | 三个独立账本的度量 |
| 产物 | `docs/audit/config-wiring-20261109.{json,md}` | 接线矩阵 |

---

## 2. 复现验收：与已封版归因报告逐位对齐

窗口取 `2026-10-31T12:02:35Z`（重启时点）→ `2026-11-08T23:59:59Z`，**按建仓时间**筛选 `main` 账本。

| 指标 | 归因报告 | 本报告 | 结论 |
|---|---:|---:|---|
| 完整平仓笔数 | 11 | **11** | ✅ |
| 净额 `net_pnl_full` | +33.762404 | **+33.762404** | ✅ 分毫不差 |
| 最大赢家贡献 | +32.948542 | **+32.948542** | ✅ |
| 最大赢家占净额 | 97.59% | **97.5894%** | ✅ |
| 剔除最大赢家后 | +0.813862 | **+0.813862** | ✅ |
| 胜率 | 27.27% | **27.2727%**（3 胜 8 负） | ✅ |
| PF | 3.91 | **3.910623** | ✅ |
| HHI(\|net\|) | 0.3915 | **0.391545** | ✅（均匀基准 0.0909） |
| 有效样本 `n_eff` | 9 | **9**（块 = symbol\|utc_date） | ✅ |
| fee 合计 | 7.333288 | **7.333288** | ✅ |
| slippage 合计 | 7.333288 | **7.333288** | ✅ |
| 成本合计 | 14.666576 | **14.666576** | ✅ |
| 成本/净额 | 43.44% | **43.44%** | ✅ |
| 成本/毛利 | 30.28% | **30.2847%** | ✅ |

**这条对账是本报告可信的前提**：如果重建口径与已封版数字不一致，后面所有新指标都不该被引用。
复现命令：

```bash
.venv/Scripts/python.exe scripts/report_strategy_review.py --ledger main \
  --since 2026-10-31T12:02:35Z --until 2026-11-08T23:59:59Z \
  --out reports/review_main_1031_1108
```

---

## 3. 三个账本的独立度量（**不合并**）

| 账本 | 已平仓 | 净额 | 胜率 | PF | 期望/笔 | 有效块 | 样本判定 | 边际判定 |
|---|---:|---:|---:|---:|---:|---:|---|---|
| `main` | 11 | +33.762404 | 27.27% | 3.9106 | +3.0693 | 9 | INCONCLUSIVE | NOT_ESTABLISHED |
| `ab-legacy` | 73 | +25.087716 | 15.07% | 2.1011 | +0.3437 | 50 | SUFFICIENT | NOT_ESTABLISHED |
| `ab-trend` | 74 | −5.121646 | 8.11% | 0.7638 | −0.0692 | 50 | SUFFICIENT | NOT_ESTABLISHED |

三点必须注意：

1. **三个账本不能相加。** 各自独立初始权益、独立回放。上表任何两列相加都不构成"组合收益"。
2. **`main` 的样本判定是 INCONCLUSIVE**（9 块 < 30），所以它的 +33.76 只能记为"单窗口已核实净收益"，
   不能记为"策略已证明盈利"。
3. **`ab-legacy` 样本够了（50 块），但边际仍不成立**：期望的块 bootstrap 95% CI 跨 0，且剔除最大赢家后为
   **−7.860826**。这是本窗口最干净的一条负面证据——它不依赖 `main` 那 11 笔的小样本。

判定规则写在 `decide_verdict()`：`edge_verdict=ESTABLISHED` 需要同时满足
"样本达标 + 期望 CI 下界 > 0 + 剔除最大赢家后仍为正"，缺一即 NOT_ESTABLISHED。

---

## 4. 四个需要裁决的发现

### 4.1 成本安全边际：全样本 +230%，剔除最大赢家只剩 +7.1%

| 口径 | 净额 | 成本 | 成本整体上升多少归零 |
|---|---:|---:|---:|
| 全样本 | +33.762404 | 14.666576 | **+230.2%** |
| 剔除最大赢家 | **+0.813862** | 11.422939 | **+7.1%** |

按建议文档 §12.7 E6 的四档压力测试（剔除最大赢家口径）：

| 情景 | 净额 | 仍盈利 |
|---|---:|---|
| 滑点 +25% | −0.611866 | 否 |
| 滑点 +50% | −2.037594 | 否 |
| fee +25% | −0.611866 | 否 |
| 两者 +50% | −4.889050 | 否 |

**读法**：全样本那个 230% 完全由 NEAR 一笔撑着，没有外推价值。可外推的口径是 **7.1%**——比常见交易所费率
档次差异还小。**这条比"PF 3.91"重要得多，应该进任何对外材料的首段。**

（近似：出场名义按建仓名义计，忽略持仓期价格变动，误差量级 ≈ 单笔毛收益率 ~1%，远小于 25% 成本档位。）

### 4.2 集中度有两个分母，差 25 个百分点

| 口径 | 值 | 回答的问题 |
|---|---:|---|
| `top1_share_of_net` | **97.59%** | 净收益是否靠一笔撑着 |
| `top1_share_of_gross_profit` | **72.63%** | 盈利单之间是否集中 |

归因报告的 97.59% 用的是前者，但原文没写分母。**建议以后引用集中度必须带分母**，否则同一个窗口能报出
"97.59%"和"72.63%"两个都算对的数字。报告器已同时输出两列并附 `share_basis_note`。

### 4.3 【需裁决】Wilson 区间与 bootstrap 给出相反结论，且与建议文档不一致

| 检验 | 结果 | 说明 |
|---|---|---|
| 打平胜率（由实测赔率 10.43 反解） | **8.75%** | `p = avg_loss/(avg_win+avg_loss)` |
| 胜率 Wilson 95%（名义 n=11） | [9.75%, 56.57%] | 下界 > 8.75% |
| 胜率 Wilson 95%（按块数 n=9） | [12.06%, 64.58%] | 下界 > 8.75% |
| 期望的块 bootstrap 95% CI | **[−1.457, +10.710]** | **跨 0** |

**建议文档 §2.2 写的是"聚类后 Wilson 95% 区间仍覆盖打平胜率"，本地两种 n 下都不成立**——区间下界都高于
打平线。我无法复现该表述，猜测它用的是另一套打平胜率定义（例如把成本重复计入或改用 R 单位）。

但这**不改变**"未确立边际"的结论，理由是另一个：**期望的 bootstrap 区间跨 0**。两个检验回答的是不同问题：

- Wilson 只问"胜率是否高于赔率要求的门槛"，不管赢的幅度；
- bootstrap 问"期望是否为正"，对幅度敏感。

本窗口 3 笔盈利里 1 笔独占 97.59%，胜率看起来显著高于打平线，但期望的区间被这一笔撑得很宽。
**建议：以后报告里两个都出，冲突时以区间更宽的那个为准**（已写入 `wilson_win_rate.note`）。
请裁决：是否接受"以 bootstrap 为准"，并在建议文档修订时改掉 §2.2 的表述。

### 4.4 配置接线：16 个字段两遍扫描都不可见

`entry_chain_config.py` 共 **201** 个字段：`LIVE_READ` 181、`DYNAMIC_READ` 4、`DECLARED_ONLY` **16**、
未知键 0。

`DECLARED_ONLY`（静态属性访问与 `getattr`/`vars` 两遍都没命中）：

```
fib_swing_fractal_k          fib_swing_lookback_15m     fib_swing_lookback_1h
fib_swing_min_atr_mult       fib_swing_min_spacing_bars
fib_extension_exhaustion_mult  fib_level_tolerance_atr_mult
ema200_buffer_pct            ema200_min_bars_stable
base_direct_exposure_pct     probe_fraction
explicit_watchlist
scout_micro_non_rr_min_score
scout_micro_targeted_long_min_score
scout_micro_targeted_long_min_pa_score
scout_micro_targeted_long_min_rr_score
```

逐个 grep 复核（排除配置文件本身）后确认：这些键在 `src/`、`scripts/` 下的引用数为 **0**。
其中两组特别值得看：

- **`fib_swing_*` 五个键**：建议文档 §13.5.9 已经怀疑"配置显示 lookback 30，而函数实际用 50"。
  实测更彻底——**整组参数根本没被读取**。fibonacci 定位的 swing 识别用的是写死的常量。
- **`ema200_buffer_pct` / `ema200_min_bars_stable`**：EMA200 闸门只读 `ema200_gate_mode` 与
  `use_ema_architecture`（`src/signals/entry_chain.py:372`），buffer 与稳定性根数是死键。
  所谓"soft penalty −0.20"不在这些参数里，改配置不会改变闸门行为。

`DYNAMIC_READ`（只有 getattr，运行时是否命中取决于数据）：`entry_gates`、`five_factor_shadow_enabled`、
`risk_first_sizing_enabled`、`score_core`。

**注意措辞**：`DECLARED_ONLY` 是"静态+动态两遍都不可见"，**不是**"确定未使用"。
持有者变量名不以 `cfg`/`config` 结尾、或经 `**cfg` 展开读取时仍会漏检。删键前仍需一次人工确认。

---

## 5. 没做的，以及为什么

| 建议文档条目 | 状态 | 理由 |
|---|---|---|
| Task 6 出场默认值切到 canonical | **不做** | P0 已裁定：改默认会让所有历史离线结论静默换口径。四条前置步骤见 `2026-11-09-p0-baseline.md` §6.3，属 P1-E8 |
| §12.3 架构改单选枚举 | **不做** | 需改 4 份配置的 schema；当前 `resolve_architecture` 已单值化并告警，先观察 |
| §12.4 Q1 通道 shadow-only 对照 | **不做** | 需要新增账本与重放，属 P1-E3，本轮不扩 |
| §16.5 滚动窗口 | 已实现但 **INCONCLUSIVE** | 窗口仅 8 天，30 日滚动只有 1 个可用窗口，出不了中位数 |
| §12.7 E6 成本压力 | **已做**（§4.1） | 四档齐备，含剔除最大赢家口径 |
| §12.8 E7 块 bootstrap | **已做** | 按 `symbol\|utc_date` 分块，seed 固定可复现 |

---

## 6. 复现

```bash
# 账本度量（三个账本分别跑，不要合并）
.venv/Scripts/python.exe scripts/report_strategy_review.py --ledger main \
  --since 2026-10-31T12:02:35Z --until 2026-11-08T23:59:59Z --out reports/review_main_1031_1108
.venv/Scripts/python.exe scripts/report_strategy_review.py --ledger ab-legacy --since 2026-10-31T12:02:35Z
.venv/Scripts/python.exe scripts/report_strategy_review.py --ledger ab-trend --since 2026-10-31T12:02:35Z

# 配置接线矩阵
.venv/Scripts/python.exe scripts/audit_config_wiring.py

# 口径与分类的锁
.venv/Scripts/python.exe -m pytest tests/test_ledger_metrics.py tests/test_config_wiring_audit.py -q
```

**已知局限（与结论同读）**

1. bootstap / Wilson 都是频率派近似，n_eff=9 时区间宽度本身就决定了识别不了 <0.4R 的差异。
2. 成本为常数假设 5+5bps，不含 funding；`cost_source=constant_assumption`。
3. 出场名义近似为建仓名义（§4.1 已声明误差量级）。
4. 接线审计看不到 `**cfg` 展开与非常规命名，`DECLARED_ONLY` 需人工确认后才可判死。
5. 全部结论基于 8 天窗口 + 已封版归因报告，样本外未验证。

---

> ⚠️ 本报告由脚本从事件流重建，仅供参考，不构成任何投资建议。样本不足时结论为 INCONCLUSIVE，
> 不得当作策略有效的证据；同理，NOT_ESTABLISHED 也不等于"策略无效"，只表示当前样本无法确立。
