# 分量 × 周期 IC 期限结构（2026-10-19）

> 脚本 `scripts/analysis/ic_term_20261019.py`（矩阵）与
> `scripts/analysis/fwd_label_audit_merge_20261019.py`（BH 汇总与三份产物合并）；
> 产物 `reports/analysis/ic-term-20261019/`、`reports/analysis/fwd-label-audit-20261019/`。

## 一、口径

- 决策面：`six_factor` profile，`2026-09`、`2026-10`，48 个 `decisions.jsonl`；
  决策 `66295` 行 → 可标注 `66263` 行，16 个标的、4564 个时间戳、50 个 UTC 日，
  截面中位宽度 14 个标的。
- 特征 13 个：六因子 6 + v2 5 + `score_pct` + `shadow_pct`；周期 6 档：1/2/4/8/16/32 根 15m。
- 目标列：**毛 `R`**（`exit_mode=barrier`、`entry_mode=next_open`），不扣成本。
- IC：**逐 UTC 时间戳横截面** Spearman（同一根 bar 上至少 8 个标的，`min_cs=8`），
  再对时间取均值。**不做日池化**，也不把日内时间序列效应混进截面。
- 标准误：按 **UTC 日** 分块 bootstrap，2000 次；`neff = (sd(ic_t)/se_boot)^2`，
  `design_effect = n_obs / neff`。
- 显著性：族内 BH，`q=0.10`（IC 族 78 格内校正），另要求 `|IC| > MDE` 且 `neff >= 50`。
- 稳健性两列：`ic_partial_stop` 为逐 bar 对 `stop_pct` 秩做偏 Spearman 后取均值；
  `ic_nonoverlap` 为按 UTC 8 小时网格（每 32 根）子采样的同口径 IC。
- **与旧口径的差别**：旧报告按**日池化**算 Spearman，目标列用**净 `R_net`**。
  当分数与 `stop_pct` 相关时，净口径会把「分数–成本」相关混进 IC；日池化则把
  跨标的与跨时段两种变异混在一起。本次两处都改掉，故新旧数字不可直接相减。

## 二、预登记

| 项 | 预登记值 |
|---|---|
| alpha / power | 0.05 / 0.80 |
| 多重检验 | BH `q=0.10`，IC 族与 tercile 族各自 78 格内校正 |
| 最小截面 | `min_cs=8` 个标的 |
| 最小样本 | 每格 `min_bars_per_cell=200`；`min_neff=50` |
| bootstrap | 2000 次，块键 `date`（UTC 日） |
| 目标列 | `gross_R`（barrier，`entry=next_open`） |
| 非重叠子采样 | 固定 stride 32 根 |
| 判定 | 仅 `BH q<0.10` 且 `|IC|>MDE` 且 `neff>=50` 的格子计为证据 |

形态判定规则（描述性，不参与显著性）：`|IC|` 峰值 <0.01 或极差 ≤ 峰值的 30% 记 `flat`；
内部周期最大且高出两端 ≥0.005 记 `mid_peak`；`h=32` 的 `|IC| ≤ h=1` 的 75% 记 `monotonic_decay`，
≥125% 记 `monotonic_rise`；其余 `mixed`。门槛与形态规则在跑全样本前写死。

## 三、结果

### 3.1 矩阵完整性

78 格（13×6）**全部 `ok`**，无一格因样本不足被剔除。`neff` 中位数随周期单调下降：
h=1 `2120` → h=2 `2013` → h=4 `1578` → h=8 `1251` → h=16 `833` → h=32 `878`；
对应 `design_effect` 中位 `18.4 → 25.3 → 33.6 → 36.0 → 42.8 → 43.3`。
即前向窗口每加长一档，重叠带来的有效样本损失就更大，长周期格子的检验力显著更弱。

### 3.2 通过全部门槛的 11 格（全部为负）

| 特征 | h | IC | MDE | q_bh | neff |
|---|---:|---:|---:|---:|---:|
| `score_pct` | 1 | -0.0281 | 0.0176 | 0.0000 | 2856 |
| `price_action_structure` | 1 | -0.0239 | 0.0143 | 0.0000 | 4562 |
| `flow_cvd_confirmation` | 1 | -0.0236 | 0.0183 | 0.0000 | 2894 |
| `price_action_structure` | 4 | -0.0229 | 0.0166 | 0.0000 | 3616 |
| `score_pct` | 2 | -0.0226 | 0.0201 | 0.0156 | 2195 |
| `score_pct` | 4 | -0.0226 | 0.0217 | 0.0325 | 1927 |
| `flow_cvd_confirmation` | 2 | -0.0224 | 0.0206 | 0.0156 | 2301 |
| `price_action_structure` | 2 | -0.0209 | 0.0169 | 0.0000 | 3528 |
| `price_action_structure` | 16 | -0.0196 | 0.0170 | 0.0000 | 3462 |
| `price_action_structure` | 8 | -0.0176 | 0.0171 | 0.0156 | 3455 |
| `cci_momentum_quality` | 1 | -0.0148 | 0.0131 | 0.0156 | 4532 |

- **11/11 全部为负**，无一格为正；`9/11` 集中在 `h<=4`（另 1 格 h=8、1 格 h=16）。
- 最强三格：`score_pct h=1 IC=-0.0281（MDE 0.0176）`、`price_action_structure h=1 -0.0239`、
  `flow_cvd_confirmation h=1 -0.0236`。
- **`h=32` 无一格显著**。这与「32 根聚合 `E[R]≈0`」并不矛盾：短周期存在稳定的负向预测，
  随周期拉长逐步衰减到 0——聚合后正负抵消，净期望自然接近零，不是「没有信号」。
- BH 层面：IC 族 78 格中 `q<0.10` 共 23 格；tercile 族 78 格中 16 格。
  `q=0.0` 只是 2000 次重采样的分辨率下限，不是数学上的 0。

### 3.3 期限结构形态：无 `mid_peak`

| 形态 | 格数 | 特征 |
|---|---:|---|
| `monotonic_decay` | 5 | `trend_ema_context`、`flow_cvd_confirmation`、`cci_momentum_quality`、`price_action_structure`、`score_pct` |
| `flat` | 6 | `fibonacci_location`、`risk_reward_geometry`、`v2_trend_persistence`、`v2_structure_location`、`v2_payoff_geometry`、`v2_volatility_regime` |
| `monotonic_rise` | 1 | `shadow_pct` |
| `mixed` | 1 | `v2_order_flow` |
| `mid_peak` | **0** | — |

`max|IC| >= 0.015` 的 5 个特征里：`monotonic_decay` 3、`flat` 1、`monotonic_rise` 1。
近零分量会机械地被归入 `flat`，故单列这一组以免稀释结论。

**这里要明确写清：`mid_peak=0` 意味着「短周期有正漂移、出场才是杠杆」这条假设
（即 IC 在中间周期见顶、说明入场方向对但持有太久）没有拿到任何支持。**
观测到的方向是**负的**：短周期 IC 最负，随周期衰减到 0，而不是先正后负。
`shadow_pct` 是唯一的 `monotonic_rise`，但它本身是影子分，不是可交易信号。

### 3.4 稳健性：方向不稳健于最保守推断

- `ic_partial_stop`：11 格**全部与主列同号**，绝对值比值 `0.94–1.10`。
  说明负 IC **不是止损宽度带出来的**——控制 `stop_pct` 后关系仍在。
- 保守双 SE：取 `max(主 SE, 非重叠 SE)` 重算 MDE 后，**11 格全部归零**（`n_sig_conservative_two_se=0`），
  且非重叠子样本上 `9/11` 符号翻转。
- 但非重叠子样本只有 `143` 个时间戳（4564 的 1/32），且固定落在 00/08/16 UTC 三个时点，
  既损失样本量又混入时段差异，**不足以独立推翻主列**，只能说明结论对抽样密度与时段敏感。
- 结论：**符号方向在预登记口径下稳定，但不稳健于最保守推断，需在更大样本上复核。**
  引用时应同时给出两列，不能只报主列。

## 四、结论

在逐时间戳横截面、毛 `R`、UTC 日块 bootstrap 的预登记口径下，78 格全部达到样本门槛，
其中 11 格同时满足 `BH q<0.10`、`|IC|>MDE`、`neff>=50`，且**11/11 全为负**、9 格集中在 `h<=4`；
最强的 `score_pct h=1` 为 `IC=-0.0281`（MDE `0.0176`）。期限结构上 `mid_peak=0`
（`monotonic_decay` 5、`flat` 6、`monotonic_rise` 1、`mixed` 1），即「短周期有正漂移、
出场才是杠杆」这条假设**未被支持**——方向是负的，不是正的；`h=32` 无显著格也与
「32 根聚合 `E[R]≈0`」自洽：短周期有稳定负向预测，长周期衰减到零后正负抵消。
因此可以说「现有六因子分数在 15m 短周期上是稳定的**反向**指标」，但**不可以说「反向使用就能盈利」**——
`ic_partial_stop` 与主列同号同量级（11/11，比值 0.94–1.10）排除了止损宽度的解释，
可保守双 SE 下 11 格全部归零、9/11 符号翻转（非重叠子样本仅 143 个时间戳），
方向不稳健于最保守推断，须在更大样本上复核；且即便反向，`maker_6` 档的 `E[R_net]` CI 上界仍为
`-0.0736`，成本墙没有因为换方向而消失。

## 五、复现命令

```bash
# 1) IC 矩阵：ic_matrix.csv / tercile_spread.csv / tests_ledger.jsonl / report.md
python D:/AIDCA/AI300-fwdlib/scripts/analysis/ic_term_20261019.py \
  --logs D:/AIDCA/AI300/logs \
  --months 2026-09,2026-10 \
  --horizons 1,2,4,8,16,32 \
  --min-cs 8 --bh-q 0.10 --iters 2000 --profile six_factor \
  --out D:/AIDCA/AI300/reports/analysis/ic-term-20261019

# 2) BH 汇总与三份产物合并：bh_table.csv / metrics.json（含 window_sensitivity）
python D:/AIDCA/AI300-fwdlib/scripts/analysis/fwd_label_audit_merge_20261019.py \
  --l1 D:/AIDCA/AI300/reports/analysis/fwd-label-v2-20261019 \
  --l2 D:/AIDCA/AI300/reports/analysis/cost-audit-20261019 \
  --l3 D:/AIDCA/AI300/reports/analysis/ic-term-20261019 \
  --bh-q 0.10 \
  --out D:/AIDCA/AI300/reports/analysis/fwd-label-audit-20261019
```

- 预期耗时：矩阵约 42s（同机 41.77s），合并脚本秒级。
- `ic_by_bar.csv` 只落 `h=32` 的逐 bar IC（其余周期未落盘，复算单格逐 bar 序列需改脚本）；
  第 2 步依赖第 1 步与成本审计目录同时存在，缺一会直接报错退出。
