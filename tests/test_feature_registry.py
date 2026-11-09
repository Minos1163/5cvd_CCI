from __future__ import annotations

from pathlib import Path

import pytest

from src.signals.feature_registry import (
    FIB_PA_COMPONENTS,
    FEATURE_REGISTRY,
    FeatureStatus,
    assert_registry_consistent,
)

ROOT = Path(__file__).resolve().parents[1]


def test_component_weights_sum_to_100():
    total = sum(entry.weight or 0.0 for entry in FEATURE_REGISTRY if entry.weight)
    assert total == pytest.approx(100.0)


def test_every_component_is_live_with_read_point():
    for entry in FEATURE_REGISTRY:
        if entry.weight:
            assert entry.status is FeatureStatus.LIVE_FEATURE, entry.name
            assert entry.read_point, entry.name
            assert entry.read_point_symbol, entry.name


def test_read_points_are_real():
    """锚点必须**精确到行**：该行必须出现该符号。

    这是本计划唯一的防腐坏机关。行号漂了，测试就红，逼你回来改 registry，
    而不是让"接线矩阵"慢慢变成一份过期文档。
    """
    for entry in FEATURE_REGISTRY:
        if not entry.read_point:
            continue
        path_part, _, line_part = entry.read_point.partition(":")
        target = ROOT / path_part
        assert target.exists(), f"{entry.name}: {path_part} 不存在"
        assert line_part.isdigit(), f"{entry.name}: read_point 缺行号"
        lines = target.read_text(encoding="utf-8").split("\n")
        line_no = int(line_part)
        assert 1 <= line_no <= len(lines), f"{entry.name}: 行号 {line_no} 越界"
        assert entry.read_point_symbol in lines[line_no - 1], (
            f"{entry.name}: {entry.read_point} 该行不含 {entry.read_point_symbol!r}，"
            f"实际内容={lines[line_no - 1].strip()!r}"
        )


def test_rsi_is_not_live():
    rsi = next(e for e in FEATURE_REGISTRY if e.name == "rsi14")
    assert rsi.status is FeatureStatus.IMPLEMENTED
    assert rsi.read_point is None


def test_macd_and_boll_are_spec_only():
    for name in ("macd", "boll"):
        entry = next(e for e in FEATURE_REGISTRY if e.name == name)
        assert entry.status is FeatureStatus.SPEC_ONLY


def test_pseudo_cvd_is_named_distinctly():
    pseudo = next(e for e in FEATURE_REGISTRY if e.name == "flow_cvd_confirmation")
    assert pseudo.source_field == "candle_signed_volume_flow"
    real = next(e for e in FEATURE_REGISTRY if e.name == "taker_flow_cvd")
    assert real.status is FeatureStatus.COMPUTED
    assert real.source_field == "taker_buy_base_volume"


def test_registry_consistency_helper():
    assert_registry_consistent()


def test_fib_pa_component_names_match_scoring_module():
    from src.signals.entry_chain_scoring import FIB_PA_WEIGHTS

    assert set(FIB_PA_COMPONENTS) == set(FIB_PA_WEIGHTS)
