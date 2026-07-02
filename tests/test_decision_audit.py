import csv
import json

from src.observability.decision_audit import DecisionAuditWriter


def test_decision_audit_writer_outputs_jsonl_and_gate_csv(tmp_path):
    writer = DecisionAuditWriter(tmp_path)
    writer.write_decision(
        {
            "timestamp": 1,
            "symbol": "SOLUSDT",
            "action": "NO_TRADE",
            "score": 58,
            "reasons": ["PROBE_COMPONENT_MINIMUM_FAILED"],
        }
    )
    writer.close()

    json_rows = [json.loads(line) for line in (tmp_path / "decisions.jsonl").read_text().splitlines()]
    csv_rows = list(csv.DictReader((tmp_path / "gate_rejections.csv").open(newline="", encoding="utf-8")))

    assert json_rows[0]["symbol"] == "SOLUSDT"
    assert csv_rows[0]["primary_reason"] == "PROBE_COMPONENT_MINIMUM_FAILED"
    gate_rows = [json.loads(line) for line in (tmp_path / "gate_rejections.jsonl").read_text(encoding="utf-8").splitlines()]
    assert gate_rows[0]["primary_reason"] == "PROBE_COMPONENT_MINIMUM_FAILED"


def test_decision_audit_gate_rejections_jsonl_is_visible_before_close(tmp_path):
    writer = DecisionAuditWriter(tmp_path)
    writer.write_decision(
        {
            "timestamp": 2,
            "symbol": "BNBUSDT",
            "action": "WATCH",
            "score": 61,
            "reasons": ["WAITING_DIRECT_THRESHOLD"],
        }
    )

    rows = [json.loads(line) for line in (tmp_path / "gate_rejections.jsonl").read_text(encoding="utf-8").splitlines()]
    csv_rows = list(csv.DictReader((tmp_path / "gate_rejections.csv").open(newline="", encoding="utf-8")))
    writer.close()

    assert rows == [
        {
            "timestamp": 2,
            "symbol": "BNBUSDT",
            "action": "WATCH",
            "score": 61,
            "primary_reason": "WAITING_DIRECT_THRESHOLD",
            "reasons": "WAITING_DIRECT_THRESHOLD",
        }
    ]
    assert csv_rows[0]["primary_reason"] == "WAITING_DIRECT_THRESHOLD"


def test_decision_audit_writer_outputs_order_drafts(tmp_path):
    writer = DecisionAuditWriter(tmp_path)
    writer.write_order_draft({"timestamp": 1, "symbol": "BNBUSDT", "approved": False})
    writer.close()

    rows = [json.loads(line) for line in (tmp_path / "order_drafts.jsonl").read_text().splitlines()]
    assert rows == [{"timestamp": 1, "symbol": "BNBUSDT", "approved": False}]


def test_decision_audit_writer_outputs_attribution_jsonl(tmp_path):
    writer = DecisionAuditWriter(tmp_path)
    writer.write_attribution(
        {
            "ts": "2026-06-20T00:00:00+00:00",
            "event": "decision",
            "decision": {
                "operation": "hold",
                "symbol": "SOLUSDT",
                "metadata": {"signal_score": 58},
            },
            "context": {"price": 150.0},
        }
    )
    writer.close()

    rows = [json.loads(line) for line in (tmp_path / "attribution.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["event"] == "decision"
    assert rows[0]["decision"]["metadata"]["signal_score"] == 58


def test_decision_audit_writer_outputs_near_misses(tmp_path):
    writer = DecisionAuditWriter(tmp_path)
    writer.write_near_miss(
        {
            "timestamp": 1,
            "symbol": "SOLUSDT",
            "action": "WATCH",
            "score": 86.5,
            "scout_candidate": True,
            "reasons": ["PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0"],
        }
    )
    writer.close()

    rows = [json.loads(line) for line in (tmp_path / "near_misses.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "action": "WATCH",
            "reasons": ["PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_2.0"],
            "score": 86.5,
            "scout_candidate": True,
            "symbol": "SOLUSDT",
            "timestamp": 1,
        }
    ]


def test_decision_audit_preserves_model_market_and_latency_fields(tmp_path):
    writer = DecisionAuditWriter(tmp_path)
    writer.write_decision(
        {
            "timestamp": 1,
            "symbol": "SOLUSDT",
            "action": "WATCH",
            "score": 62,
            "reasons": ["WAITING_TRIGGER"],
            "model_version": "entry-chain-vps-dry-run",
            "market_snapshot": {"btc_daily_return": -0.01},
            "latency_ms": 12,
        }
    )
    writer.close()

    row = json.loads((tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["model_version"] == "entry-chain-vps-dry-run"
    assert row["market_snapshot"] == {"btc_daily_return": -0.01}
    assert row["latency_ms"] == 12
