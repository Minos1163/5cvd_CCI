"""日志瘦身（2026-11-21）：log_profile=lean 的写入面与字段裁剪。

覆盖：
- lean 停写哪些文件（attribution / order_drafts / scout_decisions / gate_rejections.csv）；
- full 保持全部 7 个输出，且不做任何字段裁剪；
- T3 三处瘦身：warmup 仅首行、s1_core 整字段、gauss 敏感性中间值；
- T5 log_profile 取值校验；
- load_stops 改读 decisions.jsonl 后与 attribution 旧路径结果一致。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_DIR = ROOT / "scripts" / "analysis"
if str(ANALYSIS_DIR) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_DIR))

import attr_20261018 as attr_mod  # noqa: E402

from scripts import run_live_dry_run as runner  # noqa: E402
from src.observability.decision_audit import DecisionAuditWriter  # noqa: E402
from src.signals.entry_chain_config import EntryChainConfig  # noqa: E402


FULL_OUTPUTS = {
    "decisions.jsonl",
    "order_drafts.jsonl",
    "attribution.jsonl",
    "near_misses.jsonl",
    "scout_decisions.jsonl",
    "gate_rejections.jsonl",
    "gate_rejections.csv",
}
LEAN_OUTPUTS = {
    "decisions.jsonl",
    "near_misses.jsonl",
    "gate_rejections.jsonl",
}


def _write_all(writer: DecisionAuditWriter) -> None:
    writer.write_decision(
        {
            "timestamp": 1,
            "symbol": "SOLUSDT",
            "action": "NO_TRADE",
            "score": 58,
            "reasons": ["PROBE_COMPONENT_MINIMUM_FAILED"],
        }
    )
    writer.write_order_draft({"timestamp": 1, "symbol": "SOLUSDT", "approved": False})
    writer.write_attribution({"ts": "2026-11-21T00:00:00+00:00", "event": "decision"})
    writer.write_near_miss({"timestamp": 1, "symbol": "SOLUSDT", "score": 86.5})
    writer.write_scout_decision({"timestamp": 1, "symbol": "SOLUSDT", "candidate": True})
    writer.close()


def test_full_profile_writes_all_seven_outputs(tmp_path):
    _write_all(DecisionAuditWriter(tmp_path))
    assert {p.name for p in tmp_path.iterdir()} == FULL_OUTPUTS


def test_lean_profile_skips_files_without_readers(tmp_path):
    _write_all(DecisionAuditWriter(tmp_path, lean=True))
    assert {p.name for p in tmp_path.iterdir()} == LEAN_OUTPUTS
    # gate_rejections.jsonl 必须保留（漏斗分析在读）
    gate_rows = [json.loads(line) for line in (tmp_path / "gate_rejections.jsonl").read_text(encoding="utf-8").splitlines()]
    assert gate_rows[0]["primary_reason"] == "PROBE_COMPONENT_MINIMUM_FAILED"


def test_lean_skips_writes_do_not_raise(tmp_path):
    writer = DecisionAuditWriter(tmp_path, lean=True)
    writer.write_order_draft({"symbol": "X"})
    writer.write_attribution({"event": "decision"})
    writer.write_scout_decision({"symbol": "X"})
    writer.close()


def _rich_row(timestamp: int) -> dict:
    return {
        "timestamp": timestamp,
        "symbol": "BNBUSDT",
        "action": "HOLD",
        "reasons": ["WAITING_TRIGGER"],
        "warmup": {"15m": 240, "30m": 240, "1h": 240, "4h": 240, "required_15m": 240},
        "s1_core": {"state": "LONG", "payload": "x" * 100},
        "component_points_v2": {"volatility_regime": 0.4},
        "component_points_v2_meta": {
            "normalized_values": {"trend": 0.5},
            "volatility_regime_clip_v1": 1.0,
            "volatility_regime_gauss_v2": {"0.5": 0.1, "1.0": 0.2, "2.0": 0.3},
            "schema_version": "v2",
        },
        "score_detail": {"total_score": 61},
        "entry_context": {"stop_pct": 0.009673041092425097},
        "metadata": {"signal_score": 61},
        "sizing_trace": {"conversion": "test"},
        "weights": {"trend": 20},
        "kline": {"open": 1.0, "close": 1.1},
    }


def test_lean_trims_three_heavy_fields(tmp_path):
    writer = DecisionAuditWriter(tmp_path, lean=True)
    writer.write_decision(_rich_row(1))
    writer.write_decision(_rich_row(2))
    writer.close()

    rows = [json.loads(line) for line in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["warmup"] == {"15m": 240, "30m": 240, "1h": 240, "4h": 240, "required_15m": 240}
    assert rows[1]["warmup"] is None
    assert "s1_core" not in rows[0] and "s1_core" not in rows[1]
    meta = rows[0]["component_points_v2_meta"]
    # 2026-11-21 回退：这一项只值 103 B/行（21 天 3.6 MB），但
    # scripts/analysis/stage_c_20261019.py:329 把它当描述性列 v2_vol_gauss 读走，
    # 缺失会静默变 None。为 3.6 MB 让分析列无声变空不值得，故保留。
    assert "volatility_regime_gauss_v2" in meta, "gauss_v2 必须保留（stage_c 描述性列依赖）"
    assert meta["volatility_regime_clip_v1"] == 1.0
    assert meta["normalized_values"] == {"trend": 0.5}
    # 有分析依赖的字段必须原样保留
    for key in ("component_points_v2", "score_detail", "entry_context", "metadata", "sizing_trace", "weights", "kline", "reasons"):
        assert rows[0][key] == _rich_row(1)[key]


def test_lean_does_not_mutate_caller_row(tmp_path):
    row = _rich_row(1)
    before = json.loads(json.dumps(row))
    writer = DecisionAuditWriter(tmp_path, lean=True)
    writer.write_decision(row)
    writer.close()
    assert row == before
    assert "volatility_regime_gauss_v2" in row["component_points_v2_meta"]


def test_full_keeps_all_fields_verbatim(tmp_path):
    writer = DecisionAuditWriter(tmp_path)
    writer.write_decision(_rich_row(1))
    writer.write_decision(_rich_row(2))
    writer.close()

    rows = [json.loads(line) for line in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["warmup"] == rows[1]["warmup"] == _rich_row(1)["warmup"]
    assert rows[0]["s1_core"] == rows[1]["s1_core"] == _rich_row(1)["s1_core"]
    assert rows[0]["component_points_v2_meta"]["volatility_regime_gauss_v2"] == {
        "0.5": 0.1,
        "1.0": 0.2,
        "2.0": 0.3,
    }


@pytest.mark.parametrize("profile", ["full", "lean", "LEAN"])
def test_log_profile_accepts_known_values(profile):
    assert EntryChainConfig.from_mapping({"log_profile": profile}).log_profile in {"full", "lean"}


@pytest.mark.parametrize("bad", ["verbose", "quiet", 1])
def test_log_profile_rejects_unknown_values(bad):
    with pytest.raises(ValueError, match="log_profile"):
        EntryChainConfig.from_mapping({"log_profile": bad})
    with pytest.raises(ValueError, match="log_profile"):
        EntryChainConfig(log_profile=bad)


def test_log_profile_defaults_to_full():
    assert EntryChainConfig().log_profile == "full"
    assert EntryChainConfig.from_mapping({}).log_profile == "full"


def test_production_regime_shadow_config_is_lean():
    payload = json.loads((ROOT / "configs" / "entry_chain.dry_run_regime_shadow.json").read_text(encoding="utf-8"))
    assert payload["log_profile"] == "lean"


# ---------------------------------------------------------------- runtime 过滤


@pytest.fixture()
def lean_logger():
    runner.set_log_profile("lean")
    try:
        yield
    finally:
        runner.set_log_profile("full")


def test_lean_runtime_filter_drops_detail_lines(lean_logger):
    detail_lines = [
        "   K线预热: source=synthetic ready=True 15m=240",
        "   K线价格(15m): open=1.0 | close=1.1",
        "   风险检查: liquidity_ratio=20",
        "   评分明细: score=58",
        "   规则上下文: side=LONG atr_pct=0.01",
        "   HOLD归因: entry chain action does not allow, lock=-",
        "   决策原因: WAITING_TRIGGER",
    ]
    for line in detail_lines:
        assert runner.should_write_runtime_line(line) is False


def test_lean_runtime_filter_keeps_operational_and_error_lines(lean_logger):
    kept = [
        "=== AI300_DRY_RUN process_start @ 2026-11-19 ===",
        "交易对宇宙: source=market_cap_rank",
        "启动预热完成: 25/25",
        "当前权益: equity=1000",
        "本轮扫描完成: processed=25/25",
        "调度等待: next=...",
        "   风险检查: liquidity_ratio=ERROR",  # 含 ERROR -> 必须保留
        "SIZING_TRACE_ASSERT: trace mismatch",
        "RUN_MANIFEST_WRITE_FAILED: permission denied",
        "WARN data_health=DEGRADED",
        "Traceback (most recent call last):",
        "Exception: boom",
    ]
    for line in kept:
        assert runner.should_write_runtime_line(line) is True


def test_full_runtime_filter_keeps_everything(tmp_path):
    runner.set_log_profile("full")
    try:
        lines = ["   K线预热: source=synthetic", "WARN x", "任意行"]
        assert runner.filter_runtime_lines(lines) == lines
        runner.write_runtime_log(tmp_path, lines, timestamp=0)
        written = (tmp_path / runner.runtime_log_name(0)).read_text(encoding="utf-8")
        assert all(line in written for line in lines)
    finally:
        runner.set_log_profile("full")


# ---------------------------------------------------------------- load_stops


def _decisions_row(symbol: str, stop_pct: float) -> dict:
    return {"symbol": symbol, "entry_context": {"stop_pct": stop_pct}}


def _attribution_row(symbol: str, stop_pct: float) -> dict:
    return {"decision": {"symbol": symbol, "metadata": {"entry_context": {"stop_pct": stop_pct}}}}


def _day(tmp_path: Path, name: str, files: dict[str, list[dict]]) -> Path:
    d = tmp_path / name
    d.mkdir(parents=True)
    for filename, rows in files.items():
        (d / filename).write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return d


def test_load_stops_reads_decisions_jsonl(tmp_path, monkeypatch):
    _day(
        tmp_path,
        "2026-01-01",
        {
            "decisions.jsonl": [
                _decisions_row("BTCUSDT", 0.005),
                _decisions_row("BTCUSDT", 0.010),
                _decisions_row("ETHUSDT", 0.020),
            ]
        },
    )
    monkeypatch.setattr(attr_mod, "LOG_ROOT", str(tmp_path))
    monkeypatch.setattr(attr_mod, "START", "2026-01-01")
    monkeypatch.setattr(attr_mod, "END", "2026-01-01")
    stops = attr_mod.load_stops()
    assert stops == {"BTCUSDT": pytest.approx(0.0075), "ETHUSDT": pytest.approx(0.020)}


def test_load_stops_falls_back_to_attribution_when_decisions_missing(tmp_path, monkeypatch):
    _day(
        tmp_path,
        "2026-01-01",
        {
            "attribution.jsonl": [
                _attribution_row("BTCUSDT", 0.005),
                _attribution_row("BTCUSDT", 0.005),
                _attribution_row("BTCUSDT", 0.010),
            ]
        },
    )
    monkeypatch.setattr(attr_mod, "LOG_ROOT", str(tmp_path))
    monkeypatch.setattr(attr_mod, "START", "2026-01-01")
    monkeypatch.setattr(attr_mod, "END", "2026-01-01")
    assert attr_mod.load_stops() == {"BTCUSDT": pytest.approx(0.005)}


def test_load_stops_same_result_from_both_sources(tmp_path, monkeypatch):
    rows = [_decisions_row("BTCUSDT", p) for p in (0.005, 0.006, 0.02)]
    _day(tmp_path / "decisions", "2026-01-01", {"decisions.jsonl": rows})
    _day(tmp_path / "attr", "2026-01-01", {"attribution.jsonl": [_attribution_row("BTCUSDT", p) for p in (0.005, 0.006, 0.02)]})
    monkeypatch.setattr(attr_mod, "START", "2026-01-01")
    monkeypatch.setattr(attr_mod, "END", "2026-01-01")

    monkeypatch.setattr(attr_mod, "LOG_ROOT", str(tmp_path / "decisions"))
    from_decisions = attr_mod.load_stops()
    monkeypatch.setattr(attr_mod, "LOG_ROOT", str(tmp_path / "attr"))
    from_attribution = attr_mod.load_stops()
    assert from_decisions == from_attribution
