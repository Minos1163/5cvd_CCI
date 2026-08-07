# -*- coding: utf-8 -*-
"""explicit_watchlist 配置机制单测(评审 7.2 规格)。

覆盖:解析、symbol 大写归一、非法 scan_scope、重复符号、黑名单冲突、
promotion_criteria 默认值、与主 dry-run 配置集成加载。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from src.signals.entry_chain_config import (  # noqa: E402
    EntryChainConfig,
    ExplicitWatchlistEntry,
    load_entry_chain_config,
)

BASE = {
    "direct_threshold": 82.0,
    "blacklist_symbols": ["XRPUSDT", "ZECUSDT"],
}


def _make(values: list) -> EntryChainConfig:
    return EntryChainConfig.from_mapping({**BASE, "explicit_watchlist": values})


def test_parse_valid_entry():
    cfg = _make(
        [
            {
                "symbol": "atomusdt",
                "added_date": "2026-08-07",
                "rationale": "08-02 bull miss case",
                "scan_scope": "scout_only",
            }
        ]
    )
    assert len(cfg.explicit_watchlist) == 1
    entry = cfg.explicit_watchlist[0]
    assert entry.symbol == "ATOMUSDT"  # 解析器已统一大写
    assert entry.normalized_symbol == "ATOMUSDT"
    assert entry.scan_scope == "scout_only"
    assert entry.review_period_days == 14
    assert entry.promotion_criteria == {"min_samples": 15, "pf_min": 1.0}


def test_parse_custom_promotion_and_scope():
    cfg = _make(
        [
            {
                "symbol": "ATOMUSDT",
                "scan_scope": "full_pipeline",
                "review_period_days": 7,
                "promotion_criteria": {"min_samples": 20, "pf_min": 1.2},
            }
        ]
    )
    entry = cfg.explicit_watchlist[0]
    assert entry.scan_scope == "full_pipeline"
    assert entry.review_period_days == 7
    assert entry.promotion_criteria == {"min_samples": 20, "pf_min": 1.2}


def test_invalid_scope_rejected():
    with pytest.raises(ValueError, match="invalid scan_scope"):
        _make([{"symbol": "ATOMUSDT", "scan_scope": "full"}])
    with pytest.raises(ValueError, match="invalid scan_scope"):
        _make([{"symbol": "ATOMUSDT", "scan_scope": ""}])


def test_duplicate_symbol_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        _make([{"symbol": "ATOMUSDT"}, {"symbol": "atomusdt"}])


def test_blacklist_conflict_rejected():
    with pytest.raises(ValueError, match="conflicts with blacklist"):
        _make([{"symbol": "XRPUSDT"}])


def test_missing_symbol_rejected():
    with pytest.raises(ValueError, match="missing symbol"):
        _make([{"rationale": "no symbol here"}])


def test_main_dry_run_config_loads_without_watchlist():
    # 主配置未加 explicit_watchlist 时正常加载(空元组)
    cfg = load_entry_chain_config("configs/entry_chain.dry_run_fib_pa_v1.json")
    assert cfg.explicit_watchlist == ()


def test_multi_entry_and_case_normalization():
    cfg = _make(
        [
            {"symbol": "ATOMUSDT", "rationale": "case-a"},
            {"symbol": "FETUSDT", "rationale": "case-b"},
        ]
    )
    assert [e.normalized_symbol for e in cfg.explicit_watchlist] == ["ATOMUSDT", "FETUSDT"]
