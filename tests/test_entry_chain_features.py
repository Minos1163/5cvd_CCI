from src.backtest.engine import BacktestBar
from src.signals.entry_chain_features import completed_bars, component_scores, direction_from_history, trigger_score


def bar(ts, close, open_=None):
    return BacktestBar("SOLUSDT", ts, open_ if open_ is not None else close, close + 1, close - 1, close, 10)


def test_completed_bars_never_returns_future_timestamp():
    bars = [bar(100, 10), bar(200, 11), bar(300, 12)]

    result = completed_bars(bars, 200)

    assert [item.timestamp for item in result] == [100, 200]


def test_direction_from_history_uses_completed_history_only():
    bars = [bar(100, 100), bar(200, 100.2), bar(300, 100.5), bar(400, 101.0)]

    assert direction_from_history(bars) == "LONG"


def test_trigger_score_is_side_symmetric():
    long_bars = [bar(100, 100), bar(200, 100.1), bar(300, 100.4)]
    short_bars = [bar(100, 100), bar(200, 99.9), bar(300, 99.5)]

    assert trigger_score("LONG", long_bars) == 1.0
    assert trigger_score("SHORT", short_bars) == 1.0


def test_component_scores_include_ema_when_enabled():
    bars = [bar(index * 900, 100 + index * 0.2) for index in range(240)]
    completed = {"15m": bars, "30m": bars, "1h": bars, "4h": bars}

    scores = component_scores("LONG", completed, atr_pct_value=0.01, use_ema_architecture=True)

    assert "ema_50_quality" in scores
    assert "ema_momentum" in scores
    assert scores["ema_200_gate"] == 1.0
    assert scores["ema_50_quality"] > 0
    assert scores["ema_momentum"] > 0


def test_fib_pa_component_scores_are_present_when_enabled():
    bars_15m = [
        BacktestBar("SOLUSDT", 1000 + index * 900, 100 - index * 0.2, 101 - index * 0.2, 99 - index * 0.2, 100 - index * 0.2, 1000)
        for index in range(240)
    ]
    completed = {"15m": bars_15m, "1h": bars_15m[-80:], "30m": bars_15m[-80:], "4h": bars_15m[-80:]}

    scores = component_scores(
        "SHORT",
        completed,
        atr_pct_value=0.01,
        use_ema_architecture=True,
        ema200_gate_mode="soft",
        use_fib_pa_architecture=True,
    )

    assert "trend_ema_context" in scores
    assert "flow_cvd_confirmation" in scores
    assert "cci_momentum_quality" in scores
    assert "price_action_structure" in scores
    assert "fibonacci_location" in scores
    assert "risk_reward_geometry" in scores


def _sample_histories(direction: float):
    return {
        # 15m 至少 200 根，ema_context_from_bars 才会产出真实值（否则三个 ema 键恒为 0）
        "15m": [bar(index * 900, 100 + index * direction) for index in range(240)],
        "30m": [bar(index * 1800, 100 + index * direction) for index in range(240)],
        "1h": [bar(index * 3600, 100 + index * direction) for index in range(240)],
        "4h": [bar(index * 14400, 100 + index * direction) for index in range(240)],
    }


def test_component_scores_identical_regardless_of_ema_flag():
    """`use_ema_architecture` 只决定"要不要把这些键乘进总分"，不决定"要不要观测"。

    2026-11-14 之前 ema 子项是条件产出的：关掉开关后 `debug.scores` 里
    `ema_200_gate` / `ema_50_quality` / `ema_momentum` 三个键直接消失，
    `scripts/analysis/fwdlib/features.py` 的 FEATURE_KEYS 于是取到 NaN —— 那是
    观测口径变更，而不是"不使用该权重"。本测试锁死：同一根 K 线、同一侧，
    开关开/关两种调用返回的 dict **逐键相等**。
    """
    for side in ("LONG", "SHORT"):
        completed = _sample_histories(0.2 if side == "LONG" else -0.2)
        enabled = component_scores(side, completed, atr_pct_value=0.01, use_ema_architecture=True)
        disabled = component_scores(side, completed, atr_pct_value=0.01, use_ema_architecture=False)

        assert enabled == disabled, f"{side}: 开关开/关的 component_scores 出现差异"
        assert set(enabled) == set(disabled)
        for key in ("ema_200_gate", "ema_50_quality", "ema_momentum"):
            assert key in disabled, f"{side}: 关掉 use_ema_architecture 后仍必须保留 {key} 观测值"
        # 值本身不能退化成占位 0（否则"相等"就没意义了）
        assert disabled["ema_50_quality"] > 0
        assert disabled["ema_momentum"] > 0


def test_component_scores_identical_regardless_of_ema_flag_with_fib_pa():
    """fib_pa 架构下同样逐键相等（生产配置正是这一路）。"""
    completed = _sample_histories(0.2)
    kwargs = dict(atr_pct_value=0.01, ema200_gate_mode="soft", use_fib_pa_architecture=True)
    enabled = component_scores("LONG", completed, use_ema_architecture=True, **kwargs)
    disabled = component_scores("LONG", completed, use_ema_architecture=False, **kwargs)
    assert enabled == disabled
    for key in ("ema_200_gate", "ema_50_quality", "ema_momentum"):
        assert key in disabled


def test_component_scores_short_history_still_reports_ema_subitems():
    """15m 不足 200 根时三个 ema 键取 0——但键必须在（否则下游缺列）。"""
    short = {"15m": [bar(index * 900, 100 + index * 0.2) for index in range(20)], "1h": [bar(0, 100)]}
    scores = component_scores("LONG", short, atr_pct_value=0.01, use_ema_architecture=False)
    assert scores["ema_200_gate"] == 0.0
    assert scores["ema_50_quality"] == 0.0
    assert scores["ema_momentum"] == 0.0
