# -*- coding: utf-8 -*-
"""T7:P0 影子只读契约(裁定报告 Task S 的 `test_component_points_v2_readonly`)。

强制三件事:
1. 五因子只写记录字段,不改动 context / component_scores / decision;
2. 决策层源码(entry_chain*.py、entry_chain_scoring.py)不得引用
   `component_points_v2` 或五因子键;
3. 配置开关关闭时不产生任何影子字段。
"""
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_live_dry_run import (  # noqa: E402
    attach_five_factor_shadow,
    build_context,
    synthetic_shadow_bars,
)
from src.signals.entry_chain import EntryChainContext, evaluate_entry_chain  # noqa: E402
from src.signals.entry_chain_config import EntryChainConfig  # noqa: E402
from src.signals.entry_chain_scoring import FIB_PA_WEIGHTS  # noqa: E402
from src.signals.orthogonal_factors import FIVE_FACTOR_POINT_KEYS  # noqa: E402

DECISION_LAYER_FILES = (
    "src/signals/entry_chain.py",
    "src/signals/entry_chain_scoring.py",
    "src/signals/entry_chain_gates.py",
)


def _context() -> EntryChainContext:
    return EntryChainContext(
        symbol="TESTUSDT",
        timestamp=0,
        side="LONG",
        component_scores={"trend_ema_context": 0.8, "risk_reward_geometry": 0.6},
        quote_volume_24h=1e9,
        atr_pct=0.01,
        expected_order_size=1_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
        stop_pct=0.015,
    )


def _shadow_histories():
    return {"15m": synthetic_shadow_bars("TESTUSDT", 0)}


def test_shadow_does_not_change_decision():
    config = EntryChainConfig(use_fib_pa_architecture=True)
    context = _context()
    before = evaluate_entry_chain(context, config).to_dict()
    debug: dict = {}
    attach_five_factor_shadow(
        debug, side="LONG", histories=_shadow_histories(), atr_pct_value=0.01, config=config
    )
    after = evaluate_entry_chain(context, config).to_dict()
    assert before == after
    assert set(debug) == {"component_points_v2", "component_points_v2_meta"}


def test_shadow_does_not_mutate_component_scores_namespace():
    """影子字段与旧评分字段键名互不重叠,不污染 component_scores 命名空间。"""
    assert set(FIVE_FACTOR_POINT_KEYS).isdisjoint(FIB_PA_WEIGHTS)
    config = EntryChainConfig(use_fib_pa_architecture=True)
    context = _context()
    debug: dict = {}
    attach_five_factor_shadow(
        debug, side="LONG", histories=_shadow_histories(), atr_pct_value=0.01, config=config
    )
    assert set(context.component_scores) == {"trend_ema_context", "risk_reward_geometry"}


def test_decision_layer_has_no_reference_to_shadow_field():
    """只读契约的源码级强制:决策层不得读取影子字段。"""
    for relative in DECISION_LAYER_FILES:
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        assert "component_points_v2" not in source, relative
    scoring_source = (PROJECT_ROOT / "src/signals/entry_chain_scoring.py").read_text(encoding="utf-8")
    for key in FIVE_FACTOR_POINT_KEYS:
        assert key not in scoring_source, key


def test_shadow_disabled_writes_nothing():
    config = EntryChainConfig(five_factor_shadow_enabled=False)
    debug: dict = {}
    attach_five_factor_shadow(
        debug, side="LONG", histories=_shadow_histories(), atr_pct_value=0.01, config=config
    )
    assert debug == {}


def test_shadow_failure_is_recorded_not_raised():
    """影子异常绝不冒泡到主决策链路(与 08-13 教训一致:不因影子失败影响决策)。"""
    config = EntryChainConfig()
    debug: dict = {}
    attach_five_factor_shadow(
        debug, side="LONG", histories=None, atr_pct_value=0.01, config=config
    )
    assert "component_points_v2" not in debug
    assert debug["component_points_v2_meta"]["error"] == "AttributeError"


def test_shadow_contract_keys_present():
    config = EntryChainConfig()
    debug: dict = {}
    attach_five_factor_shadow(
        debug, side="LONG", histories=_shadow_histories(), atr_pct_value=0.01, config=config
    )
    points = debug["component_points_v2"]
    assert set(points) == set(FIVE_FACTOR_POINT_KEYS) | {"volatility_regime_leverage_mult"}
    assert debug["component_points_v2_meta"]["schema_version"] == "v2-p0-shadow"


def test_build_context_synthetic_attaches_shadow_field():
    """端到端接线:本地 synthetic 模式下 decisions 载荷会带上影子字段。"""
    args = SimpleNamespace(market_data_source="synthetic")
    config = EntryChainConfig()
    context, health, debug = build_context("TESTUSDT", 0, args, config)
    assert health == "OK"
    assert context.symbol == "TESTUSDT"
    assert "component_points_v2" in debug
    assert debug["component_points_v2_meta"]["schema_version"] == "v2-p0-shadow"


def test_build_context_synthetic_respects_disabled_switch():
    args = SimpleNamespace(market_data_source="synthetic")
    config = EntryChainConfig(five_factor_shadow_enabled=False)
    _, _, debug = build_context("TESTUSDT", 0, args, config)
    assert "component_points_v2" not in debug
    assert "component_points_v2_meta" not in debug
