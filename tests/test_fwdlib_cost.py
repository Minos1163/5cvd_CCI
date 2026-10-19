"""`fwdlib.cost` 的迁移等价性与场景口径测试。"""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.analysis.fwdlib import cost

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# 1. 迁移等价: 4 个预置模型的 round_trip_bps 与旧 cost_model.py 完全一致
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("taker_20", 20.0),
        ("entry_maker_13", 13.0),
        ("hybrid_8", 7.75),
        ("aggressive_4", 4.25),
    ],
)
def test_preset_models_round_trip_bps(version: str, expected: float) -> None:
    assert cost.get(version).round_trip_bps() == expected


def test_all_models_order_and_leg_weights_unchanged() -> None:
    assert [m.version for m in cost.ALL_MODELS] == [
        "taker_20", "entry_maker_13", "hybrid_8", "aggressive_4",
    ]
    # tp_leg_share 的加权公式不能被改动
    assert cost.get("hybrid_8").round_trip_bps(tp_leg_share=0.0) == 13.0
    assert cost.get("hybrid_8").round_trip_bps(tp_leg_share=1.0) == 6.0


def test_unknown_model_raises_keyerror() -> None:
    with pytest.raises(KeyError):
        cost.get("nope")


def test_breakeven_stop_pct_semantics_unchanged() -> None:
    model = cost.get("taker_20")
    assert cost.breakeven_stop_pct(model, 0.5) == pytest.approx(0.002 / 0.5)
    assert cost.breakeven_stop_pct(model, 0.0) is None
    assert cost.breakeven_stop_pct(model, -1.0) is None


# --------------------------------------------------------------------------- #
# 2. cost_r
# --------------------------------------------------------------------------- #

def test_cost_r_reference_values() -> None:
    assert abs(cost.cost_r(20, 0.00877) - 0.22799) < 1e-4
    assert abs(cost.cost_r(10, 0.00877) - 0.11399) < 1e-4
    assert cost.cost_r(20, 0.00877) == pytest.approx(20 / 1e4 / 0.00877)


def test_cost_r_zero_bps_is_zero() -> None:
    assert cost.cost_r(0, 0.00877) == 0.0


@pytest.mark.parametrize("bad_stop", [0.0, -0.01])
def test_cost_r_rejects_non_positive_stop(bad_stop: float) -> None:
    with pytest.raises(ValueError):
        cost.cost_r(20, bad_stop)


def test_cost_r_rejects_negative_bps() -> None:
    with pytest.raises(ValueError):
        cost.cost_r(-1, 0.01)


# --------------------------------------------------------------------------- #
# 3. cost_r_distribution
# --------------------------------------------------------------------------- #

STOPS = [0.005, 0.0075, 0.01, 0.02]


def test_cost_r_distribution_taker_20_mean_and_breakeven() -> None:
    dist = cost.cost_r_distribution(STOPS)
    expected = sum(0.002 / s for s in STOPS) / len(STOPS)
    assert dist["taker_20"]["mean"] == pytest.approx(expected, abs=1e-12)
    assert dist["taker_20"]["mean"] == pytest.approx(0.2416666666666667, abs=1e-12)
    assert dist["taker_20"]["breakeven_required_E_R"] == dist["taker_20"]["mean"]
    assert dist["taker_20"]["n"] == len(STOPS)


def test_cost_r_distribution_ordering_and_percentiles() -> None:
    dist = cost.cost_r_distribution(STOPS)
    for key in ("maker_6", "hybrid_10", "taker_20"):
        stats = dist[key]
        assert stats["p10"] <= stats["median"] <= stats["p90"]
        assert stats["bps"] == cost.SCENARIOS[key].bps
    # 同一止损宽度下, 成本档越高 cost_R 越大
    assert dist["maker_6"]["mean"] < dist["hybrid_10"]["mean"] < dist["taker_20"]["mean"]
    # 止损越宽 cost_R 越小 -> 中位数低于均值(右偏)
    assert dist["taker_20"]["median"] == pytest.approx(
        (0.002 / 0.01 + 0.002 / 0.0075) / 2, abs=1e-12
    )
    assert dist["taker_20"]["median"] < dist["taker_20"]["mean"]


def test_cost_r_distribution_empty_stops() -> None:
    dist = cost.cost_r_distribution([])
    for key in ("maker_6", "hybrid_10", "taker_20"):
        stats = dist[key]
        assert stats["n"] == 0
        for field in ("mean", "median", "p10", "p90", "breakeven_required_E_R"):
            assert stats[field] is None


def test_cost_r_distribution_accepts_custom_keys() -> None:
    dist = cost.cost_r_distribution(STOPS, keys=("maker_6",))
    assert list(dist) == ["maker_6"]


def test_describe_scenarios_dumpable() -> None:
    rows = cost.describe_scenarios()
    assert [r["key"] for r in rows] == ["maker_6", "hybrid_10", "taker_20"]
    assert rows[2]["bps"] == 20.0
    assert all(math.isfinite(r["bps"]) for r in rows)
    assert all(r["provenance"] for r in rows)


# --------------------------------------------------------------------------- #
# 4. shim 兼容
# --------------------------------------------------------------------------- #

def test_cost_model_shim_forwards_public_names() -> None:
    import scripts.analysis.cost_model as CM

    assert CM.ALL_MODELS[0].round_trip_bps() == 20.0
    assert len(CM.ALL_MODELS) == 4
    assert CM.breakeven_stop_pct is not None
    assert CM.get("hybrid_8").round_trip_bps() == 7.75
    assert CM.LegCost is cost.LegCost
    assert CM.CostModel is cost.CostModel


def test_cost_model_shim_works_as_top_level_module_in_script_mode() -> None:
    """`import cost_model as CM` 场景: 只有 scripts/analysis 在 sys.path 上。"""
    code = (
        "import sys; sys.path.insert(0, 'scripts/analysis'); "
        "import cost_model as CM; "
        "print(CM.get('taker_20').round_trip_bps(), "
        "CM.get('hybrid_8').round_trip_bps(), "
        "CM.breakeven_stop_pct(CM.get('taker_20'), 0.5))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.split()[:2] == ["20.0", "7.75"]
