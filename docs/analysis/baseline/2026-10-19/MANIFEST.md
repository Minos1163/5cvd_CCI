# 基线冻结 2026-10-19

- 冻结时间:2026-10-19 15:35:39 UTC
- 冻结时 HEAD:`d774b0f943961159ca4550369519e6adfb878f62`
- 冻结原因:下一步要做**成本分档**(20bps → 12/20/30 按流动性分档)与**日块置换**(显著性独立单元由 `symbol|utc_date` 改为 UTC 日)。两者都会改变结论口径,改之前先把旧口径结论原样存档。
- `logs/` 被 .gitignore 排除,所以冻结副本放在 `docs/analysis/baseline/` 才会进版本库。

## 旧口径的两个前提(新口径下不再成立)

1. **成本**:全部标的统一 20bps(单边,含费+滑点)。新口径下低流动性标的更贵,所有 `E[R_net]` 整体下移约 0.02R,**跨报告数字不可直接比较**。
2. **显著性**:以 `symbol|utc_date` 为独立单元的 bootstrap。同日多标的存在截面相关,该口径会低估 p 值;日块置换后 p 值系统性变大。

## 清单(sha256 校验源与副本一致)

| 源文件 | 冻结副本 | sha256 前 16 位 |
|---|---|---|
| `docs/analysis/cost_audit_2026-10-19.md` | `docs/cost_audit_2026-10-19.md` | `996d671524c2ae84` |
| `docs/analysis/fwd_label_v2_2026-10-19.md` | `docs/fwd_label_v2_2026-10-19.md` | `6412d410c046ffa7` |
| `docs/analysis/ic_term_structure_2026-10-19.md` | `docs/ic_term_structure_2026-10-19.md` | `834994c2a9cfe20e` |
| `docs/analysis/stage_c_2026-10-19.md` | `docs/stage_c_2026-10-19.md` | `f4b799ce5fc788ca` |
| `docs/analysis/six_factor_1h_2026-10-19.md` | `docs/six_factor_1h_2026-10-19.md` | `4007592f6d0ea17f` |
| `docs/analysis/stop_floor_and_edge_scan_2026-10-19.md` | `docs/stop_floor_and_edge_scan_2026-10-19.md` | `9394ce5a2f9b9f43` |
| `docs/analysis/stop_floor_cost_tf_uplift_2026-10-19.md` | `docs/stop_floor_cost_tf_uplift_2026-10-19.md` | `3b71383063a4058a` |
| `docs/analysis/relabel_2026-10-19.md` | `docs/relabel_2026-10-19.md` | `a0b031aafa7fbb7b` |
| `docs/analysis/2026-10-04_to_10-18_loss_attribution.md` | `docs/2026-10-04_to_10-18_loss_attribution.md` | `7f69dd91e4966cf3` |
| `docs/analysis/2026-10-18-review-erratum-and-revision.md` | `docs/2026-10-18-review-erratum-and-revision.md` | `63d359c914ce72a7` |
| `logs/analysis/strategy-audit-2026-10-19.md` | `snapshots/strategy-audit-2026-10-19.md` | `46868854283782fd` |
| `logs/analysis/gate-controls/2026-10-19/report.md` | `snapshots/gate-controls-report.md` | `e1f9651fc5e70397` |
| `logs/analysis/risk-first/2026-10-19/report.md` | `snapshots/risk-first-report.md` | `51f9c4d47f07bb08` |

## 回退方式

```bash
git show HEAD:docs/analysis/baseline/2026-10-19/docs/cost_audit_2026-10-19.md
```
