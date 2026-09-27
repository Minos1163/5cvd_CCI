# -*- coding: utf-8 -*-
"""verify_five_factor_orthogonality.py — 五正交因子验收(P1 阶段,task S)。

对 `decisions.jsonl` 中的 P0 影子字段 `component_points_v2.normalized_values`
执行:标准化 → 相关矩阵 → PCA(SVD)→ 硬指标判定,并单独输出 F2/F3 相关系数
(裁定报告第九节收敛预案的触发依据)。

硬指标(裁定报告第五节,五因子版):
  两两 |Pearson r| 最大值 ≤ 0.30
  Kaiser 有效维数(特征值 >1) ≥ 4 / 5
  前 2 个 PC 累积解释方差 ≤ 40%
  单因子有效取值档位 ≥ 10
  单因子零值占比 ≤ 15%
  F2/F3 相关性 > 0.30 → 触发收敛预案(合并为 STRUCTURE_PAYOFF)

用法:
  python scripts/verify_five_factor_orthogonality.py --start 2026-09-27 --end 2026-10-04
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FACTORS = (
    "trend_persistence",
    "structure_location",
    "payoff_geometry",
    "volatility_regime",
    "order_flow",
)

MIN_SAMPLES_FOR_VERDICT = 10  # SAMPLE_SIZE_DECISION_RULES:<10 不定性
MIN_UNIQUE_VALUES = 10
MAX_ZERO_SHARE = 0.15
MAX_ABS_PAIRWISE_R = 0.30
MIN_KAISER = 4
MAX_PC1_PC2_CUMULATIVE = 0.40
F2_F3_PLAN_THRESHOLD = 0.30


def iter_shadow_rows(log_root: Path, start: str, end: str) -> list[dict[str, float]]:
    """按日读取窗口内带 P0 影子字段的决策记录(仅取 0-1 归一化分量)。"""
    rows: list[dict[str, float]] = []
    day = dt.date.fromisoformat(start)
    final = dt.date.fromisoformat(end)
    while day <= final:
        path = log_root / day.strftime("%Y-%m") / day.strftime("%Y-%m-%d") / "decisions.jsonl"
        if path.exists():
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        payload = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    normalized = (payload.get("component_points_v2_meta") or {}).get("normalized_values")
                    if not isinstance(normalized, dict):
                        continue
                    if all(name in normalized for name in FACTORS):
                        rows.append({name: float(normalized[name]) for name in FACTORS})
        day += dt.timedelta(days=1)
    return rows


def evaluate_orthogonality(rows: list[dict[str, float]]) -> dict:
    if not rows:
        return {
            "samples": 0,
            "verdict": "INSUFFICIENT_SAMPLE",
            "reason": "no component_points_v2 records in window (P0 影子尚未产生数据)",
            "checks": [],
        }

    matrix = np.asarray([[row[name] for name in FACTORS] for row in rows], dtype=float)
    samples = int(matrix.shape[0])

    # 第一步:z-score 标准化(消除量级差异,否则 PCA 会被大量级因子主导)
    std = matrix.std(axis=0, ddof=1) if samples > 1 else np.zeros(matrix.shape[1])
    usable = std > 1e-12
    z = np.zeros_like(matrix)
    z[:, usable] = (matrix[:, usable] - matrix[:, usable].mean(axis=0)) / std[usable]

    if samples > 1 and usable.sum() >= 2:
        pearson = np.corrcoef(z[:, usable], rowvar=False)
        _, singular, vt = np.linalg.svd(z[:, usable], full_matrices=False)
        eigenvalues = (singular**2) / max(1, samples - 1)
        explained = eigenvalues / eigenvalues.sum() if eigenvalues.sum() > 0 else eigenvalues
        loadings = vt.T * np.sqrt(eigenvalues)
    else:
        pearson = np.eye(int(usable.sum()))
        eigenvalues = np.zeros(int(usable.sum()))
        explained = np.zeros(int(usable.sum()))
        loadings = np.zeros((int(usable.sum()), int(usable.sum())))

    active = [name for name, ok in zip(FACTORS, usable) if ok]
    matrix_by_name = {
        active[i]: {active[j]: round(float(pearson[i, j]), 4) for j in range(len(active))}
        for i in range(len(active))
    }

    pairwise_max = 0.0
    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            pairwise_max = max(pairwise_max, abs(float(pearson[i, j])))

    f2_f3 = None
    if "structure_location" in active and "payoff_geometry" in active:
        f2_f3 = round(
            float(
                pearson[active.index("structure_location"), active.index("payoff_geometry")]
            ),
            4,
        )

    unique_values = {name: len({round(float(row[name]), 4) for row in rows}) for name in FACTORS}
    zero_share = {
        name: round(float(np.mean(matrix[:, index] == 0.0)), 4) for index, name in enumerate(FACTORS)
    }
    kaiser = int((eigenvalues > 1.0).sum())
    pc1_pc2 = round(float(explained[:2].sum()), 4) if explained.size else 0.0

    checks = [
        {
            "name": "max_abs_pairwise_r",
            "target": f"<= {MAX_ABS_PAIRWISE_R}",
            "actual": round(pairwise_max, 4),
            "passed": pairwise_max <= MAX_ABS_PAIRWISE_R,
        },
        {
            "name": "kaiser_components",
            "target": f">= {MIN_KAISER}",
            "actual": kaiser,
            "passed": kaiser >= MIN_KAISER,
        },
        {
            "name": "pc1_pc2_cumulative",
            "target": f"<= {MAX_PC1_PC2_CUMULATIVE}",
            "actual": pc1_pc2,
            "passed": pc1_pc2 <= MAX_PC1_PC2_CUMULATIVE,
        },
        {
            "name": "min_unique_values",
            "target": f">= {MIN_UNIQUE_VALUES}",
            "actual": min(unique_values.values()),
            "passed": min(unique_values.values()) >= MIN_UNIQUE_VALUES,
        },
        {
            "name": "max_zero_share",
            "target": f"<= {MAX_ZERO_SHARE}",
            "actual": max(zero_share.values()),
            "passed": max(zero_share.values()) <= MAX_ZERO_SHARE,
        },
    ]

    verdict = "PASS" if all(check["passed"] for check in checks) else "FAIL"
    if samples < MIN_SAMPLES_FOR_VERDICT:
        verdict = "INSUFFICIENT_SAMPLE"

    return {
        "samples": samples,
        "verdict": verdict,
        "correlation_matrix": matrix_by_name,
        "eigenvalues": [round(float(value), 4) for value in eigenvalues],
        "explained_variance_ratio": [round(float(value), 4) for value in explained],
        "loadings": {
            f"PC{index + 1}": {
                active[row]: round(float(loadings[row, index]), 4) for row in range(len(active))
            }
            for index in range(len(active))
        },
        "unique_values": unique_values,
        "zero_share": zero_share,
        "f2_f3_correlation": f2_f3,
        "convergence_plan_triggered": bool(
            f2_f3 is not None and abs(f2_f3) > F2_F3_PLAN_THRESHOLD
        ),
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output-dir", default="logs/analysis/five-factor-orthogonality")
    args = parser.parse_args()

    rows = iter_shadow_rows(PROJECT_ROOT / args.log_root, args.start, args.end)
    result = evaluate_orthogonality(rows)
    result["window"] = f"{args.start}~{args.end}"
    result["min_samples_for_verdict"] = MIN_SAMPLES_FOR_VERDICT

    out_dir = PROJECT_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"orthogonality-{args.start}_{args.end}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({key: result[key] for key in ("window", "samples", "verdict")}, ensure_ascii=False))
    for check in result["checks"]:
        flag = "PASS" if check["passed"] else "FAIL"
        print(f"[{flag}] {check['name']}: actual={check['actual']} target={check['target']}")
    if result.get("f2_f3_correlation") is not None:
        print(
            f"[F2/F3] correlation={result['f2_f3_correlation']} "
            f"convergence_plan_triggered={result['convergence_plan_triggered']}"
        )
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
