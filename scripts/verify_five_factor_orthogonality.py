# -*- coding: utf-8 -*-
"""verify_five_factor_orthogonality.py — 五正交因子验收(P1 阶段)。

对 `decisions.jsonl` 中的 P0 影子字段 `component_points_v2.normalized_values`
执行:标准化 → 相关矩阵 → PCA(SVD)→ **双层判定**,并单独输出 F2/F3 相关系数
(收敛预案的触发依据)。

**双层框架**(2026-10-04 评审裁定 1.3 节):

硬门 —— 决定因子能否用于决策:
  两两 |Pearson r| 最大值 ≤ 0.30(直接对应线性加权评分中的重复计权风险)
  单因子零值占比 ≤ 15%(直接对应档位坍缩/因子失效风险)
  单因子有效取值档位 ≥ 10(因子是否连续)

参考指标 —— 只监控、不否决:
  Kaiser 有效维数:对 p=5 **不再设固定门槛**。等相关模型下要让 4 个特征值同时 >1
    需要 ρ<0(负相关结构),故"Kaiser≥4/5"是数学上被错误移植的尺子;
  前 2 个 PC 累积解释方差:改用 parallel analysis(置换检验)判定,而非固定百分比
    —— 对 p 个独立变量,"前 2 名"的占比天然 ≥ 2/p,存在排序偏误。

F2/F3 相关性 > 0.30 → 触发收敛预案(合并为 STRUCTURE_PAYOFF)。

用法:
  python scripts/verify_five_factor_orthogonality.py --start 2026-09-27 --end 2026-10-04
  python scripts/verify_five_factor_orthogonality.py --start <起> --end <止> --parallel-iterations 2000
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
# —— 硬门(决定 verdict)——
MAX_ABS_PAIRWISE_R = 0.30
MAX_ZERO_SHARE = 0.15
MIN_UNIQUE_VALUES = 10
# —— 参考指标(不参与 verdict 否决)——
PARALLEL_ANALYSIS_ITERATIONS = 1000
PARALLEL_ANALYSIS_SEED = 20261004
F2_F3_PLAN_THRESHOLD = 0.30


def standardize(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """z-score 标准化 + 可用列掩码(必须第一步执行,否则 PCA 被大量级因子主导)。"""
    samples = matrix.shape[0]
    std = matrix.std(axis=0, ddof=1) if samples > 1 else np.zeros(matrix.shape[1])
    usable = std > 1e-12
    z = np.zeros_like(matrix)
    if usable.any():
        z[:, usable] = (matrix[:, usable] - matrix[:, usable].mean(axis=0)) / std[usable]
    return z, usable


def top2_explained_share(matrix: np.ndarray) -> float:
    """标准化后前 2 个主成分的累积解释方差占比。"""
    z, usable = standardize(matrix)
    if usable.sum() < 2:
        return 0.0
    _, singular, _ = np.linalg.svd(z[:, usable], full_matrices=False)
    eigenvalues = (singular**2) / max(1, z.shape[0] - 1)
    total = eigenvalues.sum()
    if total <= 0:
        return 0.0
    return float(eigenvalues[:2].sum() / total)


def parallel_analysis(
    matrix: np.ndarray,
    *,
    iterations: int = PARALLEL_ANALYSIS_ITERATIONS,
    seed: int = PARALLEL_ANALYSIS_SEED,
) -> dict[str, float | int | None]:
    """置换检验:逐列独立打乱以打断因子间关联、保留各自边际分布,
    得到"纯排序偏误"下前 2PC 占比的零分布,再与实测值比较。

    实测占比显著高于零分布(小 p 值)→ 存在两两相关之外的冗余结构;
    实测占比落在零分布内 → 观测值可由排序偏误完全解释。
    """
    if matrix.shape[0] < 2 or matrix.shape[1] < 2 or iterations <= 0:
        return {"iterations": 0, "observed": None, "null_mean": None, "null_p95": None, "p_value": None}

    observed = top2_explained_share(matrix)
    rng = np.random.default_rng(seed)
    samples, columns = matrix.shape
    null_shares: list[float] = []
    for _ in range(iterations):
        permuted = np.empty_like(matrix)
        for column in range(columns):
            permuted[:, column] = matrix[rng.permutation(samples), column]
        null_shares.append(top2_explained_share(permuted))

    array = np.asarray(null_shares, dtype=float)
    return {
        "iterations": int(iterations),
        "observed": round(observed, 4),
        "null_mean": round(float(array.mean()), 4),
        "null_p95": round(float(np.percentile(array, 95)), 4),
        "p_value": round(float((array >= observed).mean()), 4),
    }



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


def evaluate_orthogonality(
    rows: list[dict[str, float]],
    *,
    parallel_iterations: int = PARALLEL_ANALYSIS_ITERATIONS,
) -> dict:
    if not rows:
        return {
            "samples": 0,
            "verdict": "INSUFFICIENT_SAMPLE",
            "reason": "no component_points_v2 records in window (P0 影子尚未产生数据)",
            "hard_gates": [],
            "reference_metrics": [],
        }

    matrix = np.asarray([[row[name] for name in FACTORS] for row in rows], dtype=float)
    samples = int(matrix.shape[0])

    # 第一步:z-score 标准化(消除量级差异,否则 PCA 会被大量级因子主导)
    z, usable = standardize(matrix)

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

    hard_gates = [
        {
            "name": "max_abs_pairwise_r",
            "target": f"<= {MAX_ABS_PAIRWISE_R}",
            "actual": round(pairwise_max, 4),
            "passed": pairwise_max <= MAX_ABS_PAIRWISE_R,
        },
        {
            "name": "max_zero_share",
            "target": f"<= {MAX_ZERO_SHARE}",
            "actual": max(zero_share.values()),
            "passed": max(zero_share.values()) <= MAX_ZERO_SHARE,
        },
        {
            "name": "min_unique_values",
            "target": f">= {MIN_UNIQUE_VALUES}",
            "actual": min(unique_values.values()),
            "passed": min(unique_values.values()) >= MIN_UNIQUE_VALUES,
        },
    ]

    # 参考指标:只监控、不否决(2026-10-04 评审裁定 1.3 节)
    parallel = (
        parallel_analysis(matrix, iterations=parallel_iterations)
        if samples >= MIN_SAMPLES_FOR_VERDICT
        else {"iterations": 0, "observed": None, "null_mean": None, "null_p95": None, "p_value": None}
    )
    reference_metrics = [
        {
            "name": "kaiser_components",
            "value": kaiser,
            "note": "p=5 不设固定门槛;仅当某特征值显著跌破 0.5 时提示该因子可能被其余因子线性预测",
        },
        {
            "name": "pc1_pc2_cumulative",
            "value": pc1_pc2,
            "note": "保持记录;判定改由 parallel_analysis_p_value 承担(排序偏误)",
        },
        {
            "name": "parallel_analysis_p_value",
            "value": parallel.get("p_value"),
            "note": "置换检验:实测前2PC占比显著高于零分布(=小 p 值)才说明存在两两相关之外的冗余结构",
            **parallel,
        },
    ]

    verdict = "PASS" if all(gate["passed"] for gate in hard_gates) else "FAIL"
    if samples < MIN_SAMPLES_FOR_VERDICT:
        verdict = "INSUFFICIENT_SAMPLE"

    return {
        "samples": samples,
        "verdict": verdict,
        "verdict_basis": "hard_gates_only",
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
        "hard_gates": hard_gates,
        "reference_metrics": reference_metrics,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output-dir", default="logs/analysis/five-factor-orthogonality")
    parser.add_argument(
        "--parallel-iterations",
        type=int,
        default=PARALLEL_ANALYSIS_ITERATIONS,
        help="parallel analysis 的置换次数(默认 1000)",
    )
    args = parser.parse_args()

    rows = iter_shadow_rows(PROJECT_ROOT / args.log_root, args.start, args.end)
    result = evaluate_orthogonality(rows, parallel_iterations=max(0, args.parallel_iterations))
    result["window"] = f"{args.start}~{args.end}"
    result["min_samples_for_verdict"] = MIN_SAMPLES_FOR_VERDICT

    out_dir = PROJECT_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"orthogonality-{args.start}_{args.end}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({key: result[key] for key in ("window", "samples", "verdict")}, ensure_ascii=False))
    print("--- 硬门(决定 verdict)---")
    for gate in result["hard_gates"]:
        flag = "PASS" if gate["passed"] else "FAIL"
        print(f"[{flag}] {gate['name']}: actual={gate['actual']} target={gate['target']}")
    print("--- 参考指标(不否决,仅监控)---")
    for metric in result["reference_metrics"]:
        print(f"[ref ] {metric['name']}: value={metric['value']} — {metric['note']}")
    if result.get("f2_f3_correlation") is not None:
        print(
            f"[F2/F3] correlation={result['f2_f3_correlation']} "
            f"convergence_plan_triggered={result['convergence_plan_triggered']}"
        )
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
