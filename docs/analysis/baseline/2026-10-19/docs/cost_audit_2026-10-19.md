# 成本审计：`20.98 USDT` 归因纠错与 6/10/20bps 敏感性（2026-10-19）

> 脚本 `scripts/analysis/ledger_audit_20261019.py`（账本核对）与
> `scripts/analysis/cost_sensitivity_v2_20261019.py`（成本敏感性）；
> 产物 `reports/analysis/cost-audit-20261019/`。数字取自同目录
> `reconciliation.json`、`cost_sensitivity.csv`、`metrics.json`。

## 一、口径

- 账本窗口：`1791156600..1792328405`（`2026-10-04 23:30 UTC` .. `2026-10-18 13:00 UTC`），
  闭区间，共 73 条 `paper_trades` 事件：`PAPER_OPEN` 31、`PAPER_REDUCE` 11、`PAPER_CLOSE` 31。
- 金额口径：直接取账本落账字段 `fee` 与 `slippage`（USDT），`notional = price × quantity`。
  不重算费率，不做四舍五入再还原。
- 隐含 bps：`sum(fee) / sum(notional) × 1e4`；`fee+slip` 同理按两者之和计算。
- 敏感性口径：在**同一批标签**上把往返成本替换为 6/10/20bps，
  `E[R_net] = E[R] - cost_R`，`cost_R` 由逐条的 `stop_bps` 折算，非按均值近似。
  出场 `barrier`、`horizon=32`、`entry=next_open`，n=`66263`。
- 全量对照：同上口径，但窗口取全部历史 `2026-06-20 07:15` .. `2026-10-18 11:30 UTC`。
- FIFO 配对：按 symbol 维护持仓队列，`PAPER_REDUCE` 按比例消耗最早开仓；
  账本对同一标的同时只保留一个持仓，**同标的重开仓即覆盖**（引擎不补 close 行）。

## 二、预登记

| 项 | 预登记值 |
|---|---|
| 问题 | 往返成本为 6 / 10 / 20bps 时，净期望分别是多少 |
| 成本轴 | `maker_6=6` / `hybrid_10=10` / `taker_20=20`（往返 bps） |
| 主指标 | `E_Rnet = E_R - cost_R`，barrier 口径 |
| 次指标 | `cost_R` 的 mean/median/p10/p90 与打平所需 `E[R]` |
| 区间 | `(symbol\|date)` 分块 80% bootstrap，2000 次，`seed=7` |
| 裁决 | 最便宜档 CI 上界 ≤0 ⇒ `COST_CANNOT_FIX`；跨 0 ⇒ `COST_BOUNDARY`；下界 >0 ⇒ `COST_CAN_FIX` |
| 不变量 | 三档 `R` 逐行相同（`max|diff|<1e-12`）；`E_Rnet(低)-E_Rnet(高) == mean(cost_R 高)-mean(cost_R 低)` |

判据只看**最便宜档**：若连理论下界都打不平，更贵的档位不必再看。反向也只在算术意义上成立，
不含队列、成交率与深度冲击。三档定义固化在 `fwdlib.cost.SCENARIOS`，运行前已定。

## 三、结果

### 3.1 纠错主体：旧归因有两处错

旧文档写「手续费 + 滑点 = `20.98 USDT` / 31 笔」。这个数**同时犯了两个错**：

1. **只算了平仓腿。** `20.988084 = 20988.08 × 10bps`，只取 `PAPER_CLOSE` 的名义；
   同一窗口还有 31 条 `PAPER_OPEN` 与 11 条 `PAPER_REDUCE`，它们的 `fee` 同样落账，被漏掉。
2. **同一笔钱算了两遍。** `fee` 与 `slippage` 由同一函数、同一常量生成（各 5bps），
   逐行相等（`fee_equals_slip_share=1.0`，`fee_bps_values=[5.0]`）；
   把两者相加不是「两种成本之和」，而是把一个常量假设重复计了一次。

真实分腿（窗口内，单位 USDT）：

| 事件 | n | fee | slippage | 名义 |
|---|---:|---:|---:|---:|
| PAPER_OPEN | 31 | 11.4981 | 11.4981 | 22996.17 |
| PAPER_REDUCE | 11 | 1.0488 | 1.0488 | 2097.57 |
| PAPER_CLOSE | 31 | 10.4940 | 10.4940 | 20988.08 |
| 合计 | 73 | 23.0409 | 23.0409 | — |

- 正确手续费（全腿）：`23.0409 USDT`；若把滑点也当真实成本：`46.0818 USDT`；旧口径 `20.9881`。
- 隐含往返：fee-only `10.02 bps`、fee+slip `20.04 bps`——与敏感性脚本的 10 / 20 两档吻合。
- 这说明旧数字既不等于真实手续费，也不构成往返成本口径；它只是一个「平仓腿名义 × 10bps」的巧合。

### 3.2 成本敏感性：三档都在 0 以下

| 场景 | 往返 bps | n | E[R]（毛） | cost_R 均值 | E[R_net] | CI80 |
|---|---:|---:|---:|---:|---:|---|
| `maker_6` | 6 | 66263 | -0.0020 | 0.0818 | **-0.0839** | [-0.0949, -0.0736] |
| `hybrid_10` | 10 | 66263 | -0.0020 | 0.1364 | **-0.1384** | [-0.1496, -0.1282] |
| `taker_20` | 20 | 66263 | -0.0020 | 0.2728 | **-0.2748** | [-0.2865, -0.2641] |

`cost_R` 分位数：6bps 档 `p10/median/p90 = 0.0411/0.0802/0.1200`；20bps 档 `0.1371/0.2673/0.4000`。
`stop_pct` 越窄，同样的 bps 折算成 R 越大，所以成本压力集中在窄止损样本上。

恒等式检查通过：左式 `+0.1909288` = 右式 `+0.1909288`，差 `2.78e-17`（阈值 1e-9）；
逐行 `max|diff| = 2.22e-16`。三档 `R` 逐行完全相同（`max|diff| = 0`），
说明成本只改 `R_net`，没有串进毛收益。

**关键结论：账面成本就是 20bps，不是先前猜测的 6–7bps。** `cost_R≈0.273` 站得住，
`E[R_net]≈-0.2748` 中成本占 `99.3%`（`0.2728/0.2748`），毛边际只剩 `-0.0020`。

### 3.3 滑点不可测：它是常量假设，不是实测

- 止损按 `stop_price` 直接成交、TP 按 `tp_price` 直接成交，标注与账本都不模拟穿价；
  价格序列里没有盘口深度，也没有 `reference_price` / `fill_price` 配对。
- `slippage` 字段与 `fee` 逐行相等，是同一个 5bps 常量乘名义，**不携带任何成交信息**。
- 因此「20bps 往返」中有一半（5bps/边）是**假设**。币安 U 本位 VIP0 taker 名义费率碰巧也是 5bps，
  但账本从未读过交易所实收流水。任何把这 20bps 称作「实测成本」的说法都不成立。

### 3.4 全量对照：缺陷贯穿全历史

| 范围 | 事件 | open | reduce | close | fee | slippage | 旧口径 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 窗口 | 73 | 31 | 11 | 31 | 23.0409 | 23.0409 | 20.9881 |
| 全量 | 573 | 233 | 110 | 230 | 211.3861 | 211.3861 | 167.2093 |

全量隐含往返 `9.86 / 19.72 bps`（fee-only / fee+slip），`fee_equals_slip_share` 仍为 1.0。
即「只算平仓腿 + fee/slip 重复计」不是某个窗口的偶发问题，而是**该归因写法在全历史上都成立**。
全量旧口径 `167.2093` 恰好等于全部 `PAPER_CLOSE` 名义 `167209.29 × 10bps`，可逐位复现。

### 3.5 FIFO 配对与幽灵 lot

- 全历史共 `340` 条出场腿，`match_ok_rate = 1.0`（340/340）。
- 语义：账本对同一标的只维护一个持仓，若旧仓未平就收到新的 `PAPER_OPEN`，
  引擎直接覆盖、不写 close 行。此时旧批次成为**幽灵 lot**，若不丢弃，平仓行会被配到更早的价格上。
- 纯 FIFO（不重置）时有 `8/340` 笔对不上，全部集中在 6 月 `ZEC/XLM` 这类重开仓；
  按「重开仓即替换」重置队列后 340/340 自洽。这 8 笔只影响配对价格，不影响本报告的费用合计
  （费用按事件逐条落账，与配对无关）。

## 四、结论

旧归因「手续费+滑点 20.98 USDT / 31 笔」有两处独立错误：`20.98 = 10.4940×2` 只覆盖了平仓腿，
漏掉开仓（11.50）与减仓（1.05）两条腿；且 `fee` 与 `slippage` 由同一函数、同一常量（各 5bps）
逐行生成，把两者相加等于把同一笔钱算两遍。按账本原始事件重算，窗口内真实手续费为
`23.0409 USDT`（73 条事件），隐含往返 fee-only `10.02bps`、fee+slip `20.04bps`。
因此**账面成本确实是 20bps 而非先前猜测的 6–7bps，`cost_R≈0.273` 的结论站得住**；
三档敏感性给出 `E[R_net] = -0.0839 / -0.1384 / -0.2748`，连最便宜的 6bps 档 CI 上界仍为
`-0.0736`，`verdict=COST_CANNOT_FIX`——仅靠降成本无法把期望拉回 0。需要强调的是，
其中 5bps/边的滑点是**常量假设而非实测**：止损/TP 均按障碍价直接成交，缺 `reference_price` /
`fill_price` 配对，这一点在使用 20bps 时必须一并披露。全量对照（573 事件、fee=slip=211.3861）
表明该口径缺陷贯穿全历史，此前所有基于旧归因的成本结论都应按本口径重述。

## 五、复现命令

```bash
# 1) 账本分腿核对：reconciliation.json / cost_ledger.csv / by_symbol_quantiles.csv
python D:/AIDCA/AI300-fwdlib/scripts/analysis/ledger_audit_20261019.py \
  --trades "D:/AIDCA/AI300/logs/*/*/paper_trades.jsonl" \
  --window 1791156600:1792328405 \
  --out D:/AIDCA/AI300/reports/analysis/cost-audit-20261019

# 2) 6/10/20bps 敏感性：cost_sensitivity.csv / metrics.json / report.md
python D:/AIDCA/AI300-fwdlib/scripts/analysis/cost_sensitivity_v2_20261019.py \
  --logs D:/AIDCA/AI300/logs --months 2026-09,2026-10 \
  --costs 6,10,20 --horizon 32 --exit-mode barrier --iters 2000 \
  --out D:/AIDCA/AI300/reports/analysis/cost-audit-20261019
```

- 说明：第 2 步会重写同目录的 `report.md`，`reconciliation.json` 由第 1 步独立生成，互不覆盖。
- 全量对照（573 事件）由第 1 步不带 `--window` 时输出，或直接读 `reconciliation.json` 的 `full` 段。
- 预期耗时：敏感性脚本约 9s（同机实测 9.2s）。
