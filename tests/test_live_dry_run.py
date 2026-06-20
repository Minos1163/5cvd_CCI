import json
import subprocess
import sys
from pathlib import Path

from scripts.run_live_dry_run import next_kline_run_timestamp


def test_live_dry_run_once_writes_audit_files(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            "configs/entry_chain.dry_run.json",
            "--once",
            "--output-dir",
            str(tmp_path),
            "--symbols",
            "BNBUSDT",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "dry_run_completed" in result.stdout
    assert (tmp_path / "decisions.jsonl").exists()
    assert (tmp_path / "order_drafts.jsonl").exists()
    assert (tmp_path / "attribution.jsonl").exists()
    assert (tmp_path / "gate_rejections.csv").exists()
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "paper_positions.json").exists()
    assert (tmp_path / "paper_trades.jsonl").exists()
    assert (tmp_path / "paper_equity.json").exists()
    assert (tmp_path / "paper_summary.json").exists()
    runtime_log = tmp_path / "runtime.out.log"
    assert runtime_log.exists()
    runtime_text = runtime_log.read_text(encoding="utf-8")
    assert "AI300_DRY_RUN cycle" in runtime_text
    assert "K线预热" in runtime_text
    assert "评分明细" in runtime_text
    assert "决策原因" in runtime_text
    assert "PAPER账本" in runtime_text
    health = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert health["mode"] == "dry_run"
    assert health["orders_submitted"] == 0
    assert summary["orders_submitted"] == 0
    assert summary["data_health"] == "OK"
    paper_summary = json.loads((tmp_path / "paper_summary.json").read_text(encoding="utf-8"))
    assert paper_summary["open_positions"] >= 0
    assert "realized_pnl" in paper_summary
    assert "profit_factor" in paper_summary
    assert "updated_at" in paper_summary
    assert "latest_kline_timestamp" in paper_summary
    paper_equity = json.loads((tmp_path / "paper_equity.json").read_text(encoding="utf-8"))
    assert "updated_at" in paper_equity
    assert "latest_kline_timestamp" in paper_equity


def test_live_dry_run_decision_json_contains_warmup_and_context_snapshot(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            "configs/entry_chain.dry_run_highest_win.json",
            "--target-tier",
            "aggressive",
            "--market-data-source",
            "synthetic",
            "--once",
            "--output-dir",
            str(tmp_path),
            "--symbols",
            "SOLUSDT",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    row = json.loads((tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["warmup"]["source"] == "synthetic"
    assert row["kline"]["timeframe"] == "15m"
    assert "scores" in row["score_detail"]
    assert "points" in row["score_detail"]


def test_live_dry_run_paper_ledger_records_open_position_when_draft_is_approved(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            "configs/entry_chain.dry_run.json",
            "--once",
            "--output-dir",
            str(tmp_path),
            "--symbols",
            "BNBUSDT",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    positions = json.loads((tmp_path / "paper_positions.json").read_text(encoding="utf-8"))
    trade_rows = [json.loads(line) for line in (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()]
    assert positions["BNBUSDT"]["entry_price"] > 0
    assert trade_rows[0]["event"] == "PAPER_OPEN"


def test_live_dry_run_uses_configured_symbols_when_cli_symbols_are_omitted(tmp_path):
    config_path = tmp_path / "entry_chain.json"
    config_path.write_text(
        json.dumps(
            {
                "direct_threshold": 99,
                "probe_threshold": 98,
                "watch_threshold": 97,
                "dry_run_symbols": ["dogeusdt", " solusdt ", "BNBUSDT"],
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            str(config_path),
            "--once",
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    health = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
    assert health["symbols"] == ["DOGEUSDT", "SOLUSDT", "BNBUSDT"]
    assert [row["symbol"] for row in rows] == ["DOGEUSDT", "SOLUSDT", "BNBUSDT"]


def test_live_dry_run_attribution_json_contains_decision_and_execution_events(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            "configs/entry_chain.dry_run_highest_win.json",
            "--target-tier",
            "aggressive",
            "--market-data-source",
            "synthetic",
            "--once",
            "--output-dir",
            str(tmp_path),
            "--symbols",
            "SOLUSDT",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    rows = [json.loads(line) for line in (tmp_path / "attribution.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [row["event"] for row in rows] == ["decision", "execution"]
    assert rows[0]["decision"]["operation"] in {"hold", "watch", "probe", "direct"}
    assert rows[0]["decision"]["metadata"]["signal_score"] is not None
    assert "score_detail" in rows[0]["decision"]["metadata"]
    assert rows[0]["context"]["warmup"]["source"] == "synthetic"
    assert rows[1]["result"]["orders_submitted"] == 0
    assert rows[1]["result"]["status"] in {"noop", "draft_ready"}


def test_live_dry_run_log_root_uses_month_and_day_directories(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            "configs/entry_chain.dry_run_highest_win.json",
            "--target-tier",
            "aggressive",
            "--market-data-source",
            "synthetic",
            "--once",
            "--log-root",
            str(tmp_path),
            "--log-date",
            "2026-06-20",
            "--symbols",
            "SOLUSDT",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    output_dir = tmp_path / "2026-06" / "2026-06-20"
    assert (output_dir / "runtime.out.log").exists()
    assert (output_dir / "attribution.jsonl").exists()
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["orders_submitted"] == 0


def test_next_kline_run_timestamp_aligns_after_quarter_hour_close():
    assert next_kline_run_timestamp(0, 900, 5) == 5
    assert next_kline_run_timestamp(4.5, 900, 5) == 5
    assert next_kline_run_timestamp(5, 900, 5) == 905
    assert next_kline_run_timestamp(899, 900, 5) == 905
    assert next_kline_run_timestamp(900, 900, 5) == 905
    assert next_kline_run_timestamp(905.1, 900, 5) == 1805


def test_highest_win_dry_run_once_accepts_synthetic_market_source(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            "configs/entry_chain.dry_run_highest_win.json",
            "--target-tier",
            "aggressive",
            "--market-data-source",
            "synthetic",
            "--once",
            "--output-dir",
            str(tmp_path),
            "--symbols",
            "SOLUSDT",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    health = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert "dry_run_completed" in result.stdout
    assert health["orders_submitted"] == 0
    assert summary["target_tier"] == "aggressive"
    assert summary["orders_submitted"] == 0


def test_live_dry_run_source_has_no_exchange_mutation_calls():
    source = Path("scripts/run_live_dry_run.py").read_text(encoding="utf-8")

    assert "submit_order(" not in source
    assert "cancel_order(" not in source


def test_vps_healthcheck_accepts_dry_run_config():
    result = subprocess.run(
        [
            sys.executable,
            "scripts/vps_dry_run_healthcheck.py",
            "--config",
            "configs/entry_chain.dry_run.json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["dry_run_safe"] is True


def test_vps_healthcheck_accepts_all_dry_run_tiers():
    for config in [
        "configs/entry_chain.dry_run_conservative.json",
        "configs/entry_chain.dry_run_balanced.json",
        "configs/entry_chain.dry_run_aggressive.json",
        "configs/entry_chain.dry_run_highest_win.json",
    ]:
        result = subprocess.run(
            [sys.executable, "scripts/vps_dry_run_healthcheck.py", "--config", config],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["dry_run_safe"] is True
