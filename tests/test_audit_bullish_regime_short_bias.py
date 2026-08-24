import json

from scripts.audit_bullish_regime_short_bias import load_decisions, summarize_asymmetry, write_outputs


def _decision(symbol, side, quadrant, score, action, ts, reasons=None):
    return {
        "symbol": symbol,
        "quadrant": quadrant,
        "score": score,
        "action": action,
        "reasons": reasons or ["FIB_PA_ARCHITECTURE_WEIGHTS"],
        "entry_context": {"side": side},
        "kline": {"timestamp": ts, "close": 100.0, "high": 101.0, "low": 99.0},
    }


def test_summary_counts_high_score_executable_rate_by_quadrant_and_side():
    rows = [
        _decision("BNBUSDT", "LONG", "Q1", 85.0, "WATCH", 1),
        _decision("BNBUSDT", "LONG", "Q1", 86.0, "PROBE", 2),
        _decision("BNBUSDT", "SHORT", "Q1", 87.0, "DIRECT", 3),
        _decision("SOLUSDT", "SHORT", "Q1", 79.0, "DIRECT", 4),
        _decision("SOLUSDT", "SHORT", "Q2", 82.0, "NO_TRADE", 5),
        _decision("DOGEUSDT", "SHORT", "Q2", 83.0, "PROBE", 6),
    ]

    summary = summarize_asymmetry(rows, min_score=80.0)

    assert summary["overall"]["LONG"]["high_score_count"] == 2
    assert summary["overall"]["LONG"]["executable_count"] == 1
    assert summary["overall"]["LONG"]["executable_rate"] == 0.5
    assert summary["overall"]["SHORT"]["high_score_count"] == 3
    assert summary["overall"]["SHORT"]["executable_count"] == 2
    assert summary["by_quadrant"]["Q1"]["SHORT"]["executable_count"] == 1
    assert summary["by_quadrant"]["Q2"]["SHORT"]["executable_count"] == 1
    assert summary["short_bias"]["executable_count_delta"] == 1


def test_load_decisions_uses_kline_timestamp_and_filters_invalid_sides(tmp_path):
    day_dir = tmp_path / "logs" / "2026-08" / "2026-08-19"
    day_dir.mkdir(parents=True)
    payloads = [
        _decision("BNBUSDT", "LONG", "Q1", 85.0, "WATCH", 1787138100),
        {"symbol": "XRPUSDT", "side": "NONE", "kline": {"timestamp": 1787138100}},
    ]
    (day_dir / "decisions.jsonl").write_text("\n".join(json.dumps(item) for item in payloads) + "\n", encoding="utf-8")

    rows = load_decisions(tmp_path / "logs", "2026-08-19", "2026-08-19")

    assert len(rows) == 1
    assert rows[0].timestamp == 1787138100
    assert rows[0].side == "LONG"


def test_write_outputs_writes_json_and_markdown(tmp_path):
    summary = summarize_asymmetry([_decision("BNBUSDT", "SHORT", "Q1", 88.0, "DIRECT", 1)], min_score=80.0)

    write_outputs(summary, tmp_path, start="2026-08-19", end="2026-08-19", regime_start="2026-08-19 19:15", min_score=80.0)

    assert (tmp_path / "bullish_regime_short_bias_audit.json").exists()
    markdown = (tmp_path / "bullish_regime_short_bias_audit.md").read_text(encoding="utf-8")
    assert "Bullish Regime Short-Bias Audit" in markdown
    assert "Q1" in markdown
