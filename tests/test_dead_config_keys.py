"""死键登记表（DEAD_CONFIG_KEYS）的守卫测试。

背景见 docs/audit/2026-11-09-dead-config-keys.md：一批 `EntryChainConfig` 字段声明后
从无任何读取点。它们不能删（`from_mapping` 对未知键 raise，会让历史/生产配置启动失败），
也不该接线（接线等于改策略行为）。本文件锁定三件事：

1. 声明仍在（兼容性前提）；
2. tracked 配置里已清理干净（治理结果）；
3. 登记表与静态审计报告一致（防止互相漂移）。
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from src.signals.entry_chain_config import DEAD_CONFIG_KEYS, EntryChainConfig

ROOT = Path(__file__).resolve().parents[1]
AUDIT_REPORT = ROOT / "docs" / "audit" / "config-wiring-20261109.json"

# 审计工具排除了 entry_chain_config.py 自身，因此"在配置模块内部被解析、但无业务消费"
# 的字段会被误报为 DECLARED_ONLY。当前唯一的已知例外是 explicit_watchlist。
KNOWN_AUDIT_EXCEPTION = {"explicit_watchlist"}

EXPECTED_DEFAULTS = {
    "base_direct_exposure_pct": 0.20,
    "probe_fraction": 0.25,
    "ema200_buffer_pct": 0.003,
    "ema200_min_bars_stable": 3,
    "fib_extension_exhaustion_mult": 1.618,
    "fib_level_tolerance_atr_mult": 0.5,
    "fib_swing_fractal_k": 2,
    "fib_swing_lookback_15m": 50,
    "fib_swing_lookback_1h": 30,
    "fib_swing_min_atr_mult": 1.2,
    "fib_swing_min_spacing_bars": 6,
    "scout_micro_non_rr_min_score": 85.0,
    "scout_micro_targeted_long_min_score": 82.0,
    "scout_micro_targeted_long_min_pa_score": 18.0,
    "scout_micro_targeted_long_min_rr_score": 3.0,
}


def test_dead_keys_are_declared() -> None:
    """死键必须仍是 dataclass 字段——删字段会让带这些键的配置加载失败。"""
    declared = {item.name for item in dataclasses.fields(EntryChainConfig)}
    missing = sorted(DEAD_CONFIG_KEYS - declared)
    assert not missing, f"这些死键的字段声明被删了，会破坏配置兼容性: {missing}"
    assert len(DEAD_CONFIG_KEYS) == 15


def test_dead_keys_absent_from_tracked_configs() -> None:
    """tracked 配置中不得再出现死键（写了也不生效，只会误导维护者）。"""
    offenders: dict[str, list[str]] = {}
    paths = sorted((ROOT / "configs").glob("entry_chain*.json"))
    assert paths, "未找到任何 entry_chain 配置，测试前提被破坏"
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        hit = sorted(set(payload) & DEAD_CONFIG_KEYS)
        if hit:
            offenders[path.name] = hit
    assert not offenders, f"以下配置仍含死键: {offenders}"


def test_dead_keys_match_audit() -> None:
    """登记表必须与静态审计报告的 DECLARED_ONLY 集合对得上。

    DECLARED_ONLY 减去 DEAD_CONFIG_KEYS 必须恰好等于已知例外集合；新增差异说明有人
    新增了无读取点字段却没登记，或删了字段却没更新报告。
    """
    report = json.loads(AUDIT_REPORT.read_text(encoding="utf-8"))
    declared_only = {item["name"] for item in report["fields"] if item["status"] == "DECLARED_ONLY"}

    assert DEAD_CONFIG_KEYS <= declared_only, (
        f"登记了审计未标记为 DECLARED_ONLY 的键: {sorted(DEAD_CONFIG_KEYS - declared_only)}"
    )
    assert declared_only - DEAD_CONFIG_KEYS == KNOWN_AUDIT_EXCEPTION, (
        f"审计报告中的非死键例外发生变化: {sorted(declared_only - DEAD_CONFIG_KEYS)}"
    )


def test_explicit_watchlist_is_not_dead() -> None:
    """explicit_watchlist 不属于死键。

    它在 entry_chain_config.py 内有完整的 `_parse_explicit_watchlist` 解析与校验
    （重复符号 / 非法 scan_scope / 与黑名单冲突），只是解析结果暂无业务消费方。
    这与"连解析都没有"的 15 个字段性质不同：审计工具排除配置模块自身，才把它
    误报为 DECLARED_ONLY。
    """
    assert "explicit_watchlist" not in DEAD_CONFIG_KEYS
    source = (ROOT / "src" / "signals" / "entry_chain_config.py").read_text(encoding="utf-8")
    assert "_parse_explicit_watchlist" in source


def test_dead_keys_defaults_unchanged() -> None:
    """死键默认值必须保持原样：它们虽不生效，但仍是配置缺省答案的一部分。"""
    config = EntryChainConfig()
    actual = {name: getattr(config, name) for name in EXPECTED_DEFAULTS}
    assert actual == EXPECTED_DEFAULTS
    assert set(EXPECTED_DEFAULTS) == set(DEAD_CONFIG_KEYS)
