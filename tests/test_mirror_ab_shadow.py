# -*- coding: utf-8 -*-
"""mirror_ab_mode shadow_only 单测(08-18 评审 P0-1)。

覆盖:配置解析(active/shadow_only)、非法值拒绝、主配置加载、
shadow 模式语义(mirror 记录但不计实验熔断——由 L223 逻辑保证,此处测配置层)。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config  # noqa: E402


def _cfg(**overrides) -> EntryChainConfig:
    return EntryChainConfig(**overrides)


def test_mirror_ab_mode_default_active():
    assert _cfg().mirror_ab_mode == "active"


def test_mirror_ab_mode_parses_shadow_only():
    cfg = EntryChainConfig.from_mapping({"mirror_ab_mode": "SHADOW_ONLY"})
    assert cfg.mirror_ab_mode == "shadow_only"  # 大小写归一


def test_mirror_ab_mode_invalid_rejected():
    with pytest.raises(ValueError, match="invalid mirror_ab_mode"):
        EntryChainConfig.from_mapping({"mirror_ab_mode": "full"})


def test_mirror_ab_mode_valid_values_accepted():
    for mode in ("active", "shadow_only"):
        cfg = EntryChainConfig.from_mapping({"mirror_ab_mode": mode})
        assert cfg.mirror_ab_mode == mode


def test_main_config_loads_shadow_only():
    # 主 dry-run 配置已切换 shadow_only(08-18 评审部署)
    cfg = load_entry_chain_config("configs/entry_chain.dry_run_fib_pa_v1.json")
    assert cfg.mirror_ab_mode == "shadow_only"
    assert cfg.mirror_ab_enabled is True  # 记录路径保持(enabled 用于 should_open 判定)
