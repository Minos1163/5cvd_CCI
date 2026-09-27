# -*- coding: utf-8 -*-
"""T8:五因子正交性验收脚本单测(裁定报告 Task S)。

覆盖:窗口读取、样本量门槛、正交性判定、F2/F3 收敛预案触发。
"""
import json
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.verify_five_factor_orthogonality import (  # noqa: E402
    FACTORS,
    evaluate_orthogonality,
    iter_shadow_rows,
)


def _payload(values: dict[str, float]) -> str:
    return json.dumps(
        {"action": "NO_TRADE", "component_points_v2_meta": {"normalized_values": values}},
        ensure_ascii=False,
    )


def _independent_rows(seed: int = 7, samples: int = 60) -> list[dict[str, float]]:
    rng = np.random.default_rng(seed)
    data = rng.random((samples, len(FACTORS)))
    return [
        {name: float(data[row, index]) for index, name in enumerate(FACTORS)}
        for row in range(samples)
    ]


def _correlated_rows(seed: int = 11, samples: int = 60) -> list[dict[str, float]]:
    rng = np.random.default_rng(seed)
    base = rng.random(samples)
    return [
        {
            name: float(min(1.0, max(0.0, base[row] + rng.normal(0.0, 0.0005))))
            for name in FACTORS
        }
        for row in range(samples)
    ]


def test_iter_shadow_rows_reads_window(tmp_path):
    day_dir = tmp_path / "2026-10" / "2026-10-01"
    day_dir.mkdir(parents=True)
    values = {name: 0.5 for name in FACTORS}
    (day_dir / "decisions.jsonl").write_text(
        _payload(values) + "\n" + json.dumps({"action": "NO_TRADE"}) + "\n",
        encoding="utf-8",
    )
    rows = iter_shadow_rows(tmp_path, "2026-10-01", "2026-10-01")
    assert len(rows) == 1
    assert rows[0] == values


def test_iter_shadow_rows_ignores_window_outside(tmp_path):
    day_dir = tmp_path / "2026-10" / "2026-10-05"
    day_dir.mkdir(parents=True)
    (day_dir / "decisions.jsonl").write_text(
        _payload({name: 0.5 for name in FACTORS}) + "\n", encoding="utf-8"
    )
    assert iter_shadow_rows(tmp_path, "2026-10-01", "2026-10-02") == []


def test_empty_rows_reports_insufficient():
    result = evaluate_orthogonality([])
    assert result["verdict"] == "INSUFFICIENT_SAMPLE"
    assert result["samples"] == 0


def test_small_sample_is_insufficient_not_verdict():
    result = evaluate_orthogonality(_independent_rows(samples=5))
    assert result["samples"] == 5
    assert result["verdict"] == "INSUFFICIENT_SAMPLE"
    assert result["checks"]  # 仍输出指标供观察


def test_independent_factors_produce_metric_report():
    result = evaluate_orthogonality(_independent_rows())
    assert result["samples"] == 60
    assert {check["name"] for check in result["checks"]} == {
        "max_abs_pairwise_r",
        "kaiser_components",
        "pc1_pc2_cumulative",
        "min_unique_values",
        "max_zero_share",
    }
    assert result["eigenvalues"]
    assert set(result["correlation_matrix"]) == set(FACTORS)


def test_correlated_factors_fail_orthogonality():
    result = evaluate_orthogonality(_correlated_rows())
    assert result["verdict"] == "FAIL"
    kaiser = next(check for check in result["checks"] if check["name"] == "kaiser_components")
    assert kaiser["actual"] < 4


def test_f2_f3_convergence_plan_trigger():
    rng = np.random.default_rng(3)
    samples = 60
    shared = rng.random(samples)
    rows = []
    for row in range(samples):
        values = {name: float(rng.random()) for name in FACTORS}
        values["structure_location"] = float(shared[row])
        values["payoff_geometry"] = float(shared[row])
        rows.append(values)
    result = evaluate_orthogonality(rows)
    assert abs(result["f2_f3_correlation"]) > 0.3
    assert result["convergence_plan_triggered"] is True
