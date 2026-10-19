"""``fwdlib.baseline`` 的配对安慰剂基线测试。

全部用合成 bar 序列,不依赖真实日志;随机行情固定 seed,保证可重复。
"""

from __future__ import annotations

import math
import random

import pytest

from scripts.analysis.fwdlib.baseline import (
    lift_summary,
    matched_placebo,
    placebo_pool,
)
from scripts.analysis.fwdlib.labeler import run_labeling

# 某个 UTC 日零点,96 根 15m bar 恰好覆盖一整天
DAY_START = 1_759_968_000
SCORES = (95.0, 85.0, 80.0, 72.0, 60.0)
STOPS = (0.005, 0.01, 0.015, 0.02)


def _panel(*, n_bars=96, seed=11, drift=0.0, sigma=0.004):
    """确定性 OHLC 面板;字段与 ``load_decisions`` 对齐。"""
    rng = random.Random(seed)
    rows = []
    px = 100.0
    for i in range(n_bars):
        o = px
        c = o * (1.0 + drift + rng.gauss(0.0, sigma))
        hi = max(o, c) * (1.0 + abs(rng.gauss(0.0, 0.0015)))
        lo = min(o, c) * (1.0 - abs(rng.gauss(0.0, 0.0015)))
        rows.append({
            "symbol": "AAAUSDT",
            "ts": DAY_START + i * 900,
            "side": "LONG" if i % 2 == 0 else "SHORT",
            "score": SCORES[i % len(SCORES)],
            "stop_pct": STOPS[i % len(STOPS)],
            "atr_pct": 0.004,
            "open": o,
            "high": hi,
            "low": lo,
            "close": c,
        })
        px = c
    return rows


def _labeled(n_decisions=40, **panel_kw):
    decisions = _panel(**panel_kw)
    rows, bars, per_symbol, index, _quad = run_labeling(decisions)
    assert len(rows) >= n_decisions
    return rows[:n_decisions], bars, per_symbol, index


def _means(placebo):
    return [p["placebo_R_mean"] for p in placebo]


def _same(a, b):
    return all(
        (math.isnan(x) and math.isnan(y)) or x == y for x, y in zip(a, b)
    )


# --------------------------------------------------------------------------- #
# 1. 跑通
# --------------------------------------------------------------------------- #

def test_matched_placebo_runs_and_shapes():
    rows, bars, ps, ix = _labeled()
    placebo = matched_placebo(rows, bars, ps, ix, draws=5, seed=7)

    assert len(placebo) == len(rows) == 40
    for item in placebo:
        assert set(item) == {
            "placebo_R_mean", "placebo_R_sd", "placebo_n_valid",
            "placebo_valid", "delta_R", "delta_R_net",
        }
        assert 0 <= item["placebo_n_valid"] <= 5
        assert isinstance(item["placebo_valid"], bool)

    # 合成面板足够长,几乎每行都应拿到有效对照
    assert sum(1 for p in placebo if p["placebo_valid"]) >= 38


def test_matched_placebo_keep_sd_false_omits_sd():
    rows, bars, ps, ix = _labeled(n_decisions=5)
    placebo = matched_placebo(rows, bars, ps, ix, draws=2, seed=7, keep_sd=False)
    assert all("placebo_R_sd" not in p for p in placebo)


# --------------------------------------------------------------------------- #
# 2. 可复现
# --------------------------------------------------------------------------- #

def test_same_seed_reproduces_and_other_seed_differs():
    rows, bars, ps, ix = _labeled()

    a = matched_placebo(rows, bars, ps, ix, draws=5, seed=7)
    b = matched_placebo(rows, bars, ps, ix, draws=5, seed=7)
    c = matched_placebo(rows, bars, ps, ix, draws=5, seed=8)

    assert _same(_means(a), _means(b))
    assert not _same(_means(a), _means(c))


def test_sampling_independent_of_row_order():
    """逐条 RNG 由 (seed, symbol, ts, side) 派生,重排行序结果不变。"""
    rows, bars, ps, ix = _labeled(n_decisions=12)
    forward = matched_placebo(rows, bars, ps, ix, draws=4, seed=7)
    backward_rows = list(reversed(rows))
    backward = matched_placebo(backward_rows, bars, ps, ix, draws=4, seed=7)

    by_ts = {r["ts"]: m for r, m in zip(backward_rows, backward)}
    for row, item in zip(rows, forward):
        assert item["placebo_R_mean"] == by_ts[row["ts"]]["placebo_R_mean"]


# --------------------------------------------------------------------------- #
# 3. 同 stop_pct ⇒ 成本恒等
# --------------------------------------------------------------------------- #

def test_identity_between_delta_gross_and_net():
    rows, bars, ps, ix = _labeled()
    placebo = matched_placebo(rows, bars, ps, ix, draws=5, seed=7)
    diff = max(
        abs(p["delta_R"] - p["delta_R_net"])
        for p in placebo if p["placebo_valid"]
    )
    assert diff < 1e-9


# --------------------------------------------------------------------------- #
# 4. 无漂移随机游走上安慰剂无 edge
# --------------------------------------------------------------------------- #

def test_placebo_has_no_edge_on_zero_drift_walk():
    # draws 取大一些:零漂移路径上安慰剂的期望应为 0,draws 太少时
    # 「随机抽哪几根 bar」的噪声本身就有 ~0.06R 量级,会盖住这条性质。
    rows, bars, ps, ix = _labeled(n_decisions=40, seed=3, drift=0.0)
    placebo = matched_placebo(rows, bars, ps, ix, draws=40, seed=7)
    values = [p["placebo_R_mean"] for p in placebo if p["placebo_valid"]]
    assert len(values) >= 35
    assert abs(sum(values) / len(values)) < 0.05


# --------------------------------------------------------------------------- #
# 5. lift_summary
# --------------------------------------------------------------------------- #

def test_lift_summary_buckets_and_identity():
    rows, bars, ps, ix = _labeled()
    placebo = matched_placebo(rows, bars, ps, ix, draws=5, seed=7)
    merged = [{**r, **p} for r, p in zip(rows, placebo)]

    summary = lift_summary(merged)

    assert len(summary["by_score"]) == 5
    assert sum(b["n"] for b in summary["by_score"]) == len(merged)
    assert summary["identity_max_abs_diff"] < 1e-9
    assert summary["overall"]["n"] == len(merged)
    assert summary["overall"]["n_valid"] == sum(
        1 for p in placebo if p["placebo_valid"]
    )
    for bucket in summary["by_score"]:
        assert bucket["lift_gross"] == pytest.approx(bucket["lift_net"], abs=1e-12)


def test_lift_summary_matches_manual_means():
    rows, bars, ps, ix = _labeled()
    placebo = matched_placebo(rows, bars, ps, ix, draws=5, seed=7)
    merged = [{**r, **p} for r, p in zip(rows, placebo)]
    summary = lift_summary(merged, iters=200)

    top = summary["by_score"][0]  # score >= 92
    subset = [m for m in merged if m["score"] >= 92]
    assert top["n"] == len(subset)
    assert top["E_R"] == pytest.approx(
        sum(m["R"] for m in subset) / len(subset)
    )
    assert top["lift_gross"] == pytest.approx(
        sum(m["delta_R"] for m in subset) / len(subset)
    )


def test_placebo_pool_excludes_self_and_only_same_day():
    decisions = _panel(n_bars=96)
    _rows, _bars, ps, ix = _labeled()
    day = "2025-10-09"
    pool = placebo_pool(_bars, ps, ix, "AAAUSDT", day, exclude_ts=decisions[0]["ts"])

    assert len(pool) == 95
    assert decisions[0]["ts"] not in pool
    assert sorted(pool) == pool
    assert all(ts // 86_400 == DAY_START // 86_400 for ts in pool)


# --------------------------------------------------------------------------- #
# 6. 边界
# --------------------------------------------------------------------------- #

def test_empty_labeled_returns_empty_list():
    _rows, bars, ps, ix = _labeled(n_decisions=3)
    assert matched_placebo([], bars, ps, ix, draws=5, seed=7) == []


def test_zero_draws_marks_every_row_invalid():
    rows, bars, ps, ix = _labeled(n_decisions=4)
    placebo = matched_placebo(rows, bars, ps, ix, draws=0, seed=7)

    assert len(placebo) == 4
    for item in placebo:
        assert item["placebo_valid"] is False
        assert item["placebo_n_valid"] == 0
        assert math.isnan(item["placebo_R_mean"])
        # delta 置 0 而非 nan:保证批量 max/求和不被 NaN 污染
        assert item["delta_R"] == 0.0
        assert item["delta_R_net"] == 0.0


def test_unknown_symbol_yields_invalid_rows():
    rows, bars, ps, ix = _labeled(n_decisions=2)
    fake = [dict(r, symbol="ZZZUSDT") for r in rows]
    placebo = matched_placebo(fake, bars, ps, ix, draws=3, seed=7)
    assert all(not p["placebo_valid"] for p in placebo)
