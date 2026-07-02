import csv
import json
import subprocess
import sys

from scripts.replay_near_miss_mfe_mae import replay_near_misses


def test_replay_near_misses_calculates_long_mfe_mae():
    near = [{"timestamp": 1000, "symbol": "SOLUSDT", "intended_side": "LONG", "entry_price": 100.0}]
    decisions = [
        {"timestamp": 1000, "symbol": "SOLUSDT", "kline": {"timestamp": 1000, "high": 100.5, "low": 99.5}},
        {"timestamp": 1900, "symbol": "SOLUSDT", "kline": {"timestamp": 1900, "high": 103.0, "low": 98.0}},
        {"timestamp": 2801, "symbol": "SOLUSDT", "kline": {"timestamp": 2801, "high": 104.0, "low": 97.0}},
    ]

    rows = replay_near_misses(near, decisions, windows_minutes=[30])

    assert rows[0]["mfe_30m_pct"] == 0.03
    assert rows[0]["mae_30m_pct"] == -0.02
    assert rows[0]["bars_30m"] == 1


def test_replay_near_misses_calculates_short_mfe_mae():
    near = [{"timestamp": 1000, "symbol": "BNBUSDT", "intended_side": "SHORT", "entry_price": 100.0}]
    decisions = [
        {"timestamp": 1900, "symbol": "BNBUSDT", "kline": {"timestamp": 1900, "high": 102.0, "low": 96.0}},
    ]

    rows = replay_near_misses(near, decisions, windows_minutes=[30])

    assert rows[0]["mfe_30m_pct"] == 0.04
    assert rows[0]["mae_30m_pct"] == -0.02


def test_replay_near_miss_cli_writes_csv(tmp_path):
    near_path = tmp_path / "near_misses.jsonl"
    decisions_path = tmp_path / "decisions.jsonl"
    output_path = tmp_path / "mfe.csv"
    near_path.write_text(json.dumps({"timestamp": 1000, "symbol": "SOLUSDT", "intended_side": "LONG", "entry_price": 100.0}) + "\n", encoding="utf-8")
    decisions_path.write_text(json.dumps({"timestamp": 1900, "symbol": "SOLUSDT", "kline": {"timestamp": 1900, "high": 101.0, "low": 99.0}}) + "\n", encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/replay_near_miss_mfe_mae.py",
            "--near-misses",
            str(near_path),
            "--decisions",
            str(decisions_path),
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    rows = list(csv.DictReader(output_path.open(newline="", encoding="utf-8")))
    assert rows[0]["symbol"] == "SOLUSDT"
    assert rows[0]["mfe_30m_pct"] == "0.01"
