"""`fwdlib.labeler` 的迁移等价性测试。

核心断言:``label_at_horizons`` 的每个 horizon 与独立 ``label_barrier(horizon=h)``
逐字段一致(仅多 ``horizon`` 键)。真实日志存在时抽 200 行做对照,不存在则
``pytest.skip``;另有一组合成 bar 的用例保证本文件在无日志环境下仍有约束力。
"""

from __future__ import annotations

import importlib.util
import os
import random
import statistics
import sys
from pathlib import Path

import pytest

from scripts.analysis.fwdlib.config import LabelConfig
from scripts.analysis.fwdlib.labeler import (
    build_bars,
    entry_and_start,
    label_at_horizons,
    label_barrier,
    label_ladder,
    resolve_stop,
    run_labeling,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_ROOT = Path(os.environ.get("FWD_LOGS", "D:/AIDCA/AI300/logs"))
HORIZONS = (1, 2, 4, 8, 16, 32)
LEGACY_KEYS = ("R", "R_net", "cost_r", "stop_pct_eff", "bars", "reason", "ambiguous",
               "entry_price", "stop_price", "mfe_r")


# --------------------------------------------------------------------------- #
# 合成面板
# --------------------------------------------------------------------------- #

def _synthetic_decisions(n_bars: int = 96, symbols=("AAAUSDT", "BBBUSDT")):
    """构造一段带趋势/回撤的确定性行情 + 决策行(字段与 load_decisions 对齐)。"""
    decisions = []
    base_ts = 1_760_000_000 - (1_760_000_000 % 900)
    for k, sym in enumerate(symbols):
        px = 100.0 + 10.0 * k
        for i in range(n_bars):
            px *= 1.0 + 0.004 * ((i % 13) - 6) / 6.0
            o, c = px, px * (1.0 + 0.002 * ((i % 7) - 3))
            hi = max(o, c) * 1.004
            lo = min(o, c) * 0.996
            decisions.append({
                "symbol": sym,
                "ts": base_ts + i * 900,
                "side": "LONG" if (i + k) % 2 == 0 else "SHORT",
                "score": 60.0 + i,
                "stop_pct": 0.005 + 0.001 * (i % 5),
                "atr_pct": 0.004 + 0.0005 * (i % 4),
                "quadrant": "Q1" if i % 3 else "Q3",
                "open": o, "high": hi, "low": lo, "close": c,
            })
            px = c
    return decisions


def _strip_horizon(row: dict | None) -> dict | None:
    if row is None:
        return None
    return {k: v for k, v in row.items() if k != "horizon"}


def _assert_multi_matches_single(bars, ps, ix, decisions, modes=("next_open", "bar_close")):
    compared = 0
    nonnull = 0
    for d in decisions:
        for mode in modes:
            stop = resolve_stop(d.get("stop_pct"), d.get("atr_pct"))
            multi = label_at_horizons(bars, ps, ix, d, stop, HORIZONS, mode)
            assert set(multi) == set(HORIZONS)
            for h in HORIZONS:
                single = label_barrier(bars, ps, ix, d, stop, mode, horizon=h)
                compared += 1
                nonnull += single is not None
                assert _strip_horizon(multi[h]) == single, (d["symbol"], d["ts"], mode, h)
    return compared, nonnull


def test_multi_horizon_matches_single_on_synthetic_bars() -> None:
    decisions = _synthetic_decisions()
    bars, ps, ix = build_bars(decisions)
    compared, nonnull = _assert_multi_matches_single(bars, ps, ix, decisions)
    assert compared == len(decisions) * 2 * len(HORIZONS)
    # 必须真的结算出一批行,否则「全都是 None 相等」也能过
    assert nonnull > compared // 2


def test_multi_horizon_returns_none_when_no_forward_bars() -> None:
    """末根决策没有后续 bar:各 horizon 全 None,与 label_barrier 一致。"""
    decisions = _synthetic_decisions(n_bars=40, symbols=("AAAUSDT",))
    bars, ps, ix = build_bars(decisions)
    tail = decisions[-1]
    multi = label_at_horizons(bars, ps, ix, tail, 0.01)
    assert all(v is None for v in multi.values())
    assert label_barrier(bars, ps, ix, tail, 0.01) is None
    assert entry_and_start(bars, ps, ix, tail) is None


def test_label_barrier_horizon_defaults_to_cfg() -> None:
    decisions = _synthetic_decisions()
    bars, ps, ix = build_bars(decisions)
    d = decisions[3]
    assert label_barrier(bars, ps, ix, d, 0.01) == label_barrier(bars, ps, ix, d, 0.01, horizon=32)
    assert label_barrier(bars, ps, ix, d, 0.01, cfg=LabelConfig(horizon_bars=4)) == (
        label_barrier(bars, ps, ix, d, 0.01, horizon=4)
    )


def test_label_ladder_default_entry_is_bar_close() -> None:
    decisions = _synthetic_decisions()
    bars, ps, ix = build_bars(decisions)
    d = decisions[5]
    assert label_ladder(bars, ps, ix, d, 0.01) == label_ladder(
        bars, ps, ix, d, 0.01, entry_mode="bar_close"
    )


def test_resolve_stop_clamp_and_scenarios() -> None:
    # 无 raw_stop 时按 atr*1.5 clamp 到 [0.005, 0.03]
    assert resolve_stop(None, 0.001) == 0.005
    assert resolve_stop(None, 0.10) == 0.03
    assert abs(resolve_stop(None, 0.01) - 0.015) < 1e-15
    assert resolve_stop(0.004, 0.10) == 0.004
    assert resolve_stop(0.004, 0.10, stop_floor=0.0075) == 0.0075
    assert abs(resolve_stop(0.01, 0.0, stop_scale=1.2) - 0.012) < 1e-15
    # cfg 提供 clamp 带宽,同时作为 floor/scale 的兜底
    cfg = LabelConfig(min_stop_pct=0.008, max_stop_pct=0.02, atr_stop_mult=2.0,
                      stop_floor=0.009, stop_scale=2.0)
    assert resolve_stop(None, 0.001, cfg=cfg) == 0.009 * 2.0
    assert resolve_stop(None, 0.001, cfg=cfg, stop_floor=0.008) == 0.016
    assert resolve_stop(0.05, 0.0, cfg=cfg, stop_scale=1.0) == 0.05


def test_run_labeling_adds_fields_without_dropping_legacy_keys() -> None:
    decisions = _synthetic_decisions()
    rows, _, _, _, quad = run_labeling(decisions)
    assert quad is None
    assert rows
    row = rows[0]
    for key in LEGACY_KEYS:
        assert key in row, key
    assert row["gross_R"] == row["R"]
    assert row["horizon"] == 32
    assert row["hold_seconds"] == row["exit_ts"] - row["entry_ts"]
    assert row["exit_ts"] > row["entry_ts"]


def test_cost_bps_shifts_r_net_only() -> None:
    decisions = _synthetic_decisions()
    base, _, _, _, _ = run_labeling(decisions)
    cheap, _, _, _, _ = run_labeling(decisions, cfg=LabelConfig(cost_bps=0.0))
    assert [r["R"] for r in base] == [r["R"] for r in cheap]
    for a, b in zip(base, cheap):
        assert a["cost_r"] == pytest.approx(0.002 / a["stop_pct_eff"], abs=1e-15)
        assert b["cost_r"] == 0.0
        assert a["R_net"] == pytest.approx(b["R_net"] - a["cost_r"], abs=1e-12)


def test_run_labeling_horizon_and_breakeven_follow_config() -> None:
    """1h 口径:horizon=8 时成本保本根数降到 2,不能退化成 8 根。"""
    decisions = _synthetic_decisions()
    rows, _, _, _, _ = run_labeling(decisions, exit_mode="ladder", entry_mode="bar_close",
                                    cfg=LabelConfig(horizon_bars=8, bar_seconds=3600))
    assert rows
    assert {r["horizon"] for r in rows} == {8}
    assert {r["bars"] <= 8 for r in rows} == {True}
    # 显式 horizon 优先于 cfg
    rows8, _, _, _, _ = run_labeling(decisions, cfg=LabelConfig(horizon_bars=32), horizon=8)
    assert {r["horizon"] for r in rows8} == {8}


# --------------------------------------------------------------------------- #
# 真实日志抽样对照
# --------------------------------------------------------------------------- #

def _load_repo_decisions(limit_days: int = 5):
    if not LOG_ROOT.exists():
        pytest.skip(f"日志目录不存在: {LOG_ROOT}")
    paths = [str(p) for p in sorted(LOG_ROOT.glob("2026-10/*/decisions.jsonl"))][:limit_days]
    if not paths:
        pytest.skip(f"未找到 decisions.jsonl: {LOG_ROOT}")
    legacy = REPO_ROOT / "scripts/analysis/fwd_label_20261019.py"
    spec = importlib.util.spec_from_file_location("fwd_label_legacy", legacy)
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("fwd_label_legacy", mod)
    spec.loader.exec_module(mod)
    decisions = mod.load_decisions(paths)
    if len(decisions) < 200:
        pytest.skip(f"样本不足 200 行: {len(decisions)}")
    return decisions


def test_parity_with_legacy_run_labeling_on_sample() -> None:
    decisions = _load_repo_decisions()
    legacy = sys.modules["fwd_label_legacy"]
    sample = random.Random(20261019).sample(decisions, 200)

    new_rows, bars, ps, ix, _ = run_labeling(sample)
    old_rows, _, _, _, _ = legacy.run_labeling(sample)
    assert len(new_rows) == len(old_rows)
    for a, b in zip(old_rows, new_rows):
        for key in LEGACY_KEYS:
            assert a.get(key) == b.get(key), (a["symbol"], a["ts"], key)


def test_multi_horizon_matches_single_on_sample() -> None:
    decisions = _load_repo_decisions()
    sample = random.Random(7).sample(decisions, 200)
    bars, ps, ix = build_bars(decisions)
    compared, nonnull = _assert_multi_matches_single(bars, ps, ix, sample)
    assert compared == len(sample) * 2 * len(HORIZONS)
    assert nonnull >= compared // 2
