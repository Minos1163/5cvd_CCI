"""`fwdlib.features` 的特征抽取与降级路径测试。

核心回归锁:v2 五因子必须真正进入特征矩阵(旧脚本因取错层级 + 循环不含
v2 键名,五个分量从未被抽出来)。
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.analysis.fwdlib import features
from scripts.analysis.fwdlib.features import (
    FEATURE_KEYS,
    V2_FACTORS,
    V2_KEYS,
    extract_features,
    feature_coverage,
    load_decisions,
    rebuild_price_levels,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_GLOB = "D:/AIDCA/AI300/logs/2026-10/*/decisions.jsonl"

TS = int(datetime(2026, 10, 19, tzinfo=timezone.utc).timestamp())

V2_VALUES = {
    "trend_persistence": 0.3125,
    "structure_location": 0.6403,
    "order_flow": 0.2519,
    "payoff_geometry": 0.3592,
    "volatility_regime": 0.2863,
}


def _row(with_v2: bool = True) -> dict:
    meta = {"shadow_total": 35.7266}
    if with_v2:
        meta["normalized_values"] = dict(V2_VALUES)
    return {
        "symbol": "BTCUSDT",
        "side": "LONG",
        "kline": {
            "timestamp": TS,
            "open": 100.0,
            "high": 110.0,
            "low": 90.0,
            "close": 105.0,
        },
        "entry_context": {
            "side": "LONG",
            "atr_pct": 0.008,
            "stop_pct": 0.012,
            "quote_volume_24h": 5_000_000_000.0,
            "extreme_position_ratio": 0.23,
            "symbol_exposure_pct": 1.5,
            "total_exposure_pct": 4.5,
            "daily_profit_pct": -0.4,
            "current_volatility_scale": 0.9,
        },
        "score_detail": {
            "total_score": 68.5,
            "scores": {"trend_ema_context": 0.8, "ema_50_quality": 0.6},
        },
        "component_points": {"trend_ema_context": 50.0, "ema_momentum": 40.0},
        "component_points_v2": {
            "trend_persistence": 6.875,
            "order_flow": 5.542,
        },
        "component_points_v2_meta": meta,
        "market_snapshot": {"btc_daily_return": 1.2, "btc_weekly_return": -2.4},
        "weights": dict(features.SIX_FACTOR_WEIGHTS),
    }


def _extract(row: dict) -> dict:
    return extract_features(
        row,
        row["entry_context"],
        row["score_detail"],
        float(row["entry_context"]["atr_pct"]),
        TS,
    )


# --------------------------------------------------------------------------- #
# 1. 回归锁: normalized_values 在 meta 下,且必须落成 v2_* 列
# --------------------------------------------------------------------------- #

def test_v2_normalized_values_land_in_feature_matrix() -> None:
    feat = _extract(_row(with_v2=True))
    for name in V2_FACTORS:
        key = "v2_" + name
        assert key in feat, f"缺少 v2 特征列 {key}"
        assert feat[key] == pytest.approx(V2_VALUES[name], abs=1e-12)
    assert set(V2_KEYS) <= set(feat)
    # component_points_v2 里的点数不是归一化值,不能被误用
    assert feat["v2_trend_persistence"] != 6.875


# --------------------------------------------------------------------------- #
# 2. 缺失必须写 nan,不能退化成 0.0
# --------------------------------------------------------------------------- #

def test_v2_missing_normalized_values_yield_nan() -> None:
    feat = _extract(_row(with_v2=False))
    for key in V2_KEYS:
        assert key in feat
        assert math.isnan(feat[key]), f"{key} 应为 nan, 实际 {feat[key]!r}"


def test_include_v2_false_skips_v2_keys() -> None:
    row = _row(with_v2=True)
    feat = extract_features(
        row, row["entry_context"], row["score_detail"], 0.008, TS, include_v2=False
    )
    assert not (set(V2_KEYS) & set(feat))


# --------------------------------------------------------------------------- #
# 3. 旧 18 键取值逻辑不变
# --------------------------------------------------------------------------- #

def test_legacy_keys_score_shadow_and_bar_pos() -> None:
    feat = _extract(_row())
    assert feat["score_pct"] == pytest.approx(0.685)
    assert feat["shadow_pct"] == pytest.approx(0.357266)
    assert feat["bar_pos"] == pytest.approx((105.0 - 90.0) / (110.0 - 90.0))
    assert feat["atr_pct"] == pytest.approx(0.008)
    assert feat["hour"] == 0
    assert feat["weekday"] == 0  # 2026-10-19 是周一
    assert feat["log_qv"] == pytest.approx(math.log10(5_000_000_000.0))
    assert feat["btc_daily"] == pytest.approx(1.2)
    assert feat["btc_weekly"] == pytest.approx(-2.4)


def test_legacy_scores_take_precedence_over_points() -> None:
    feat = _extract(_row())
    # trend_ema_context 同时在 scores(0.8) 与 points(50 → 0.5) 里,应取 scores
    assert feat["trend_ema_context"] == pytest.approx(0.8)
    # 只在 points 里 → /100
    assert feat["ema_momentum"] == pytest.approx(0.4)
    # 两边都没有 → nan
    assert math.isnan(feat["ema_200_gate"])
    assert tuple(FEATURE_KEYS) == features.FEATURE_KEYS
    assert len(FEATURE_KEYS) == 18


def test_feature_families_partition_matches_keys() -> None:
    fams = features.FEATURE_FAMILIES
    assert fams["v2"] == V2_KEYS
    assert fams["score"] == ("score_pct",)
    assert fams["shadow"] == ("shadow_pct",)
    assert set(fams["six_factor"]) <= set(FEATURE_KEYS)


# --------------------------------------------------------------------------- #
# 4. 真实日志覆盖率(无日志则跳过)
# --------------------------------------------------------------------------- #

def test_real_log_v2_coverage() -> None:
    paths = sorted(str(p) for p in Path("D:/AIDCA/AI300/logs").glob("2026-10/*/decisions.jsonl"))
    if not paths:
        pytest.skip("无 2026-10 决策日志,跳过覆盖率检查")

    rows = load_decisions(paths)
    if not rows:
        pytest.skip("日志解析后无有效决策行")
    cov = feature_coverage(rows)
    for key in V2_KEYS:
        assert cov[key]["nonnull_pct"] > 0.99, f"{key} 覆盖率 {cov[key]['nonnull_pct']:.4f}"
    assert cov["score_pct"]["nonnull_pct"] > 0.99
    assert cov["score_pct"]["n"] == len(rows)


# --------------------------------------------------------------------------- #
# 5. rebuild_price_levels 三条止损来源 + 方向
# --------------------------------------------------------------------------- #

SYM = "ETHUSDT"
BARS = {
    (SYM, 1000): (100.0, 105.0, 99.0, 104.0),
    (SYM, 1900): (104.0, 108.0, 103.0, 107.0),
    (SYM, 2800): (107.0, 109.0, 106.0, 106.5),
}
PER_SYMBOL = {SYM: [1000, 1900, 2800]}
INDEX = {SYM: {1000: 0, 1900: 1, 2800: 2}}


def _decision(**over) -> dict:
    d = {
        "symbol": SYM,
        "ts": 1000,
        "side": "LONG",
        "atr_pct": 0.004,
        "entry_context": {"side": "LONG", "stop_pct": 0.02, "atr_pct": 0.004},
        "kline": {"open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0},
    }
    d.update(over)
    return d


def test_rebuild_uses_risk_budget_first() -> None:
    d = _decision(metadata={"risk_budget": {"stop_pct": 0.011}})
    lv = rebuild_price_levels(d, BARS, PER_SYMBOL, INDEX, "next_open")
    assert lv["stop_pct_source"] == "risk_budget"
    assert lv["stop_pct"] == pytest.approx(0.011)
    assert lv["entry_price_source"] == "next_open"
    assert lv["entry_price"] == pytest.approx(104.0)
    assert lv["stop_price"] == pytest.approx(104.0 * (1 - 0.011))


def test_rebuild_falls_back_to_entry_context() -> None:
    d = _decision()
    lv = rebuild_price_levels(d, BARS, PER_SYMBOL, INDEX, "bar_close")
    assert lv["stop_pct_source"] == "entry_context"
    assert lv["stop_pct"] == pytest.approx(0.02)
    assert lv["entry_price_source"] == "bar_close"
    assert lv["entry_price"] == pytest.approx(104.0)
    assert lv["stop_price"] == pytest.approx(104.0 * (1 - 0.02))


def test_rebuild_atr_fallback_clamps() -> None:
    d = _decision(entry_context={"side": "LONG", "atr_pct": 0.004})
    lv = rebuild_price_levels(d, BARS, PER_SYMBOL, INDEX, "next_open")
    assert lv["stop_pct_source"] == "atr_fallback"
    # 0.004 * 1.5 = 0.006 落在 [0.005, 0.03]
    assert lv["stop_pct"] == pytest.approx(0.006)

    # 极低 ATR 命中下限
    d2 = _decision(atr_pct=0.0001, entry_context={"side": "LONG", "atr_pct": 0.0001})
    assert rebuild_price_levels(d2, BARS, PER_SYMBOL, INDEX)["stop_pct"] == pytest.approx(0.005)
    # 极高 ATR 命中上限
    d3 = _decision(atr_pct=0.5, entry_context={"side": "LONG", "atr_pct": 0.5})
    assert rebuild_price_levels(d3, BARS, PER_SYMBOL, INDEX)["stop_pct"] == pytest.approx(0.03)


def test_rebuild_short_stop_above_entry() -> None:
    d = _decision(
        side="SHORT",
        entry_context={"side": "SHORT", "stop_pct": 0.015},
        metadata={"risk_budget": {"stop_pct": 0.015}},
    )
    lv = rebuild_price_levels(d, BARS, PER_SYMBOL, INDEX, "next_open")
    assert lv["entry_price"] == pytest.approx(104.0)
    assert lv["stop_price"] == pytest.approx(104.0 * (1 + 0.015))
    assert lv["stop_price"] > lv["entry_price"]


def test_rebuild_missing_entry_returns_none() -> None:
    d = _decision(symbol="NOPE")
    lv = rebuild_price_levels(d, BARS, PER_SYMBOL, INDEX, "next_open")
    assert lv["entry_price"] is None
    assert lv["entry_price_source"] == "missing"
    assert lv["stop_price"] is None
    # 止损宽度仍可还原
    assert lv["stop_pct"] == pytest.approx(0.02)
