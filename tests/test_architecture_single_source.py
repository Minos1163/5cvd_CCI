"""架构唯一性守卫（F1，2026-11-14 风控复核）。

## 问题

架构判定原先有**两个来源**：
- `resolve_architecture(cfg)` 读 `scoring_architecture` 枚举（决定用哪张权重表）；
- `entry_chain._apply_component_minimums` 读布尔开关 `cfg.use_fib_pa_architecture`
  （决定走谁的入场最小值闸门）。

两者在"枚举写 fib_pa、布尔写 false"时静默脱钩。风控复现的后果（同一根 K 线、
同样 fib_pa 权重、score 都是 100.000）：

| 配置 | 结果 |
|---|---|
| `enum=fib_pa, use_fib_pa=True` | DIRECT, lev=5, notional=1000 |
| `enum=fib_pa, use_fib_pa=False` | WATCH, lev=0, notional=0 |

本文件锁住 F1-a 的修复：`_apply_component_minimums` 改为
`resolve_architecture(cfg)[0] == "fib_pa"`，即枚举是唯一来源。

## 仍然存在的第二处来源（F1-b，未修，见 commit body）

`entry_chain.py` 还有 5 处读 `cfg.use_fib_pa_architecture`（fib 衰竭拦截、
LONG 追高/过热 watch、HIGH_BETA probe 复核、5x 杠杆要求），以及上游
`component_scores(..., use_fib_pa_architecture=...)` 决定**要不要算** fib_pa 六分量。
也就是说：枚举= fib_pa 但布尔=false 时，本文件第 1 条测试能过（闸门走 fib_pa），
但上游分数仍是 0（六分量没算）。**要彻底自洽必须把 8 处读点统一到一个 helper**。
本条测试只保证"闸门这一处不再自相矛盾"，并不宣称 F1 已完结。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.signals.entry_chain import EntryChainContext, _apply_component_minimums, evaluate_entry_chain
from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config
from src.signals.entry_chain_scoring import FIB_PA_WEIGHTS, resolve_architecture

ROOT = Path(__file__).resolve().parents[1]

# fib_pa 六分量全 1.0 → 乘 FIB_PA 权重（合计 100）→ score = 100.000，正是风控复现里的输入。
FIB_PA_PERFECT_SCORES = {
    "trend_ema_context": 1.0,
    "flow_cvd_confirmation": 1.0,
    "cci_momentum_quality": 1.0,
    "price_action_structure": 1.0,
    "fibonacci_location": 1.0,
    "risk_reward_geometry": 1.0,
    "fib_action_cap": 1.0,
}


def _context(scores: dict[str, float]) -> EntryChainContext:
    return EntryChainContext(
        symbol="BTCUSDT",
        timestamp=1_700_000_000,
        side="LONG",
        component_scores=scores,
        quote_volume_24h=5e9,
        atr_pct=0.01,
        expected_order_size=1_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
        stop_pct=0.015,
    )


def test_enum_fib_pa_wins_over_flag_in_component_minimums() -> None:
    """枚举=fib_pa 且布尔=False 时，闸门必须仍走 fib_pa 分支（不再 score=100 却 WATCH）。"""
    cfg = EntryChainConfig(
        scoring_architecture="fib_pa",
        use_fib_pa_architecture=False,
        use_ema_architecture=False,
    )
    reasons: list[str] = []

    action = _apply_component_minimums("DIRECT", 100.0, _context(FIB_PA_PERFECT_SCORES), cfg, reasons)

    assert action == "DIRECT", f"闸门没走 fib_pa 分支，reasons={reasons}"
    assert "DIRECT_COMPONENT_MINIMUM_FAILED" not in reasons, "落到了 base 的 DIRECT 最小值检查"


def test_explicit_base_still_uses_base_minimums() -> None:
    """对照：显式 base 时同样的输入必须被 base 闸门降级——证明这条闸门不是被整体关掉。

    若把 `_apply_component_minimums` 写成"永远返回 action"，上一条测试也会绿，
    这条就是为了排除那种假绿。
    """
    cfg = EntryChainConfig(scoring_architecture="base")
    reasons: list[str] = []

    action = _apply_component_minimums("DIRECT", 100.0, _context(FIB_PA_PERFECT_SCORES), cfg, reasons)

    assert action != "DIRECT"
    assert "DIRECT_COMPONENT_MINIMUM_FAILED" in reasons


def test_explicit_ema_wins_over_fib_pa_flag() -> None:
    """枚举=ema 且布尔 fib_pa=True 时，闸门必须走 ema/base 分支，而不是 fib_pa 分支。

    为了让 EMA50 闸门真的被走到，这里额外给基础四分量满分（否则 base 的 probe 最小值检查
    会先把 PROBE 降成 WATCH，EMA50 闸门就轮不到了——那是另一条路径，不是本测试的目标）。
    """
    cfg = EntryChainConfig(
        scoring_architecture="ema",
        use_fib_pa_architecture=True,
        use_ema_architecture=True,
        ema200_gate_mode="hard",
    )
    scores = {
        **FIB_PA_PERFECT_SCORES,
        "direction_1h": 1.0,
        "quality_30m": 1.0,
        "trigger_15m": 1.0,
        "cvd_flow": 1.0,
    }
    reasons: list[str] = []

    action = _apply_component_minimums("PROBE", 80.0, _context(scores), cfg, reasons)

    joined = "|".join(reasons)
    assert "PROBE_BELOW" not in joined, f"误走了 fib_pa 的 probe 最小值闸门: {joined}"
    assert "EMA50_PROBE_MINIMUM_FAILED" in reasons, f"没走 ema 分支: {joined}"
    assert action == "WATCH"


def test_full_decision_matches_between_flag_true_and_enum_only() -> None:
    """端到端：`enum=fib_pa + flag=True` 与 `enum=fib_pa + flag=False` 的四个值必须相同。

    输入固定为 fib_pa 满分分量（score=100），所以 5x 杠杆要求与各 fib_pa 专用 watch 都不
    触发，可以只观察闸门差异。**注意**：这正是 F1-b 的边界——上游分数由调用方注入，
    真实链路里 `component_scores()` 仍按布尔开关决定要不要算 fib_pa 六分量。
    """
    perfect = _context(FIB_PA_PERFECT_SCORES)
    with_flag = EntryChainConfig(use_fib_pa_architecture=True)
    enum_only = EntryChainConfig(scoring_architecture="fib_pa", use_fib_pa_architecture=False)

    left = evaluate_entry_chain(perfect, with_flag)
    right = evaluate_entry_chain(perfect, enum_only)

    assert (left.action, left.score, left.leverage, left.notional_hint) == (
        right.action,
        right.score,
        right.leverage,
        right.notional_hint,
    )
    assert left.action == "DIRECT"
    assert left.score == pytest.approx(sum(FIB_PA_WEIGHTS.values()), abs=1e-9)


def test_resolve_architecture_fib_pa_is_independent_of_atr_pct() -> None:
    """`resolve_architecture(cfg)[0] == "fib_pa"` 与 atr_pct 无关——这是传 0.0 的依据。

    闸门里 `resolve_architecture(cfg)` 用默认 atr_pct=0.0。若某天 fib_pa 的返回路径变得依赖
    atr_pct，这条会红，提醒人回去补参数而不是继续沿用 0.0。
    """
    atr_grid = (0.0, 0.001, 0.008, 0.009999, 0.01, 0.02, 0.0349, 0.035, 0.05, 0.2)
    configs = [
        EntryChainConfig(use_fib_pa_architecture=True),
        EntryChainConfig(scoring_architecture="fib_pa"),
        EntryChainConfig(scoring_architecture="fib_pa", use_fib_pa_architecture=False),
        EntryChainConfig(use_fib_pa_architecture=False),
        EntryChainConfig(use_ema_architecture=True),
        EntryChainConfig(scoring_architecture="base"),
    ]
    for cfg in configs:
        outcomes = {resolve_architecture(cfg, atr)[0] == "fib_pa" for atr in atr_grid}
        assert len(outcomes) == 1, f"fib_pa 判定随 atr_pct 变化: {cfg}"


TRACKED_CONFIG_PATHS = sorted((ROOT / "configs").glob("entry_chain*.json"))


@pytest.mark.parametrize("config_path", TRACKED_CONFIG_PATHS, ids=lambda p: p.name)
def test_tracked_configs_filter_agrees_with_enum_resolution(config_path: Path) -> None:
    """18 份配置上：`resolve_architecture(cfg)[0] == "fib_pa"` 与布尔开关恒等。

    这是 F1 改动的等价性前提。唯一会破坏它的写法是
    `scoring_architecture="fib_pa"` 配 `use_fib_pa_architecture=false`（当前不存在）；
    真出现时本测试会红，逼人先决定"以谁为准"，而不是让两套判定静默分叉。
    """
    cfg = load_entry_chain_config(config_path)
    assert (resolve_architecture(cfg)[0] == "fib_pa") == cfg.use_fib_pa_architecture


def test_all_tracked_configs_are_covered() -> None:
    """防止 configs 目录被清空或命名漂移导致上面那条参数化测试变成 0 用例。"""
    assert len(TRACKED_CONFIG_PATHS) >= 18, [p.name for p in TRACKED_CONFIG_PATHS]
