from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.observability.run_manifest import (
    MANIFEST_SCHEMA_VERSION,
    RunManifest,
    build_run_manifest,
    git_state,
    sha256_file,
)

ROOT = Path(__file__).resolve().parents[1]


def _manifest(tmp_path: Path, config_text: str = '{"a": 1}', **overrides) -> RunManifest:
    config_path = tmp_path / "cfg.json"
    config_path.write_text(config_text, encoding="utf-8")
    kwargs = dict(
        root=ROOT,
        config_path=config_path,
        resolved_config={"a": 1},
        cli_args={"config": str(config_path)},
        target_tier="conservative",
        post_close_delay_seconds=10.0,
        kline_align=True,
        base_timeframe_seconds=900,
        universe_source="cli",
        universe_version=None,
        resolved_symbols=("BTCUSDT", "ETHUSDT"),
        pnl_schema_version=2,
        pnl_accounting_mode="notional_primary_margin_reporting",
        fee_bps=5.0,
        slippage_bps=5.0,
        exit_mode="legacy",
        paper_or_backtest_mode="paper",
        started_at_utc="2026-11-09T02:00:00Z",
    )
    kwargs.update(overrides)
    return build_run_manifest(**kwargs)


def test_config_sha_is_content_based(tmp_path):
    a = tmp_path / "a.json"
    a.write_text('{"x": 1}', encoding="utf-8")
    b = tmp_path / "b.json"
    b.write_text('{"x": 1}', encoding="utf-8")
    assert sha256_file(a) == sha256_file(b)


def test_config_sha_changes_with_content(tmp_path):
    a = tmp_path / "a.json"
    a.write_text('{"x": 1}', encoding="utf-8")
    first = sha256_file(a)
    a.write_text('{"x": 2}', encoding="utf-8")
    assert sha256_file(a) != first


def test_run_id_embeds_config_hash(tmp_path):
    manifest = _manifest(tmp_path)
    assert manifest.run_id.endswith(manifest.config_sha256[:8])
    assert manifest.run_id.startswith("20261109T020000Z")


def test_run_id_changes_when_config_changes(tmp_path):
    first = _manifest(tmp_path, '{"a": 1}')
    second = _manifest(tmp_path, '{"a": 2}')
    assert first.run_id != second.run_id


def test_manifest_has_all_required_fields(tmp_path):
    payload = _manifest(tmp_path).to_dict()
    required = {
        "run_id", "started_at_utc", "ended_at_utc", "git_commit", "git_branch",
        "working_tree_dirty", "config_path", "config_sha256", "resolved_config",
        "cli_args", "target_tier", "post_close_delay_seconds", "kline_align",
        "base_timeframe_seconds", "universe_source", "universe_version",
        "resolved_symbols", "pnl_schema_version", "pnl_accounting_mode",
        "fee_bps", "slippage_bps", "exit_mode", "paper_or_backtest_mode",
    }
    assert required <= set(payload)
    assert payload["schema_version"] == MANIFEST_SCHEMA_VERSION


def test_write_roundtrip(tmp_path):
    manifest = _manifest(tmp_path)
    target = manifest.write(tmp_path / "out" / "run_manifest.json")
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded["run_id"] == manifest.run_id
    assert loaded["resolved_symbols"] == ["BTCUSDT", "ETHUSDT"]


def test_write_refuses_different_config_hash(tmp_path):
    first = _manifest(tmp_path, '{"a": 1}')
    target = first.write(tmp_path / "run_manifest.json")
    second = _manifest(tmp_path, '{"a": 2}', started_at_utc="2026-11-09T02:00:00Z")
    with pytest.raises(ValueError, match="refusing to overwrite"):
        second.write(target)


def test_git_state_reports_repo(tmp_path):
    state = git_state(ROOT)
    assert set(state) == {"git_commit", "git_branch", "working_tree_dirty"}
    assert state["git_commit"]


def test_pnl_accounting_mode_is_single_sourced():
    """`pnl_accounting_mode` 的字面量只允许出现在常量定义那一行。

    改动前该字面量在 paper_trading.py 里被抄了四处（:276/:425/:477/:530）。
    任一处重新写死字面量都会让本测试变红——这是"单一权威口径"的守门人。
    """
    from src.observability import paper_trading

    assert paper_trading.PNL_ACCOUNTING_MODE == "notional_primary_margin_reporting"
    source = (ROOT / "src/observability/paper_trading.py").read_text(encoding="utf-8")
    assert source.count('"notional_primary_margin_reporting"') == 1
