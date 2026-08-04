import json

from scripts.summarize_scout_trend_capture_diagnostics import load_rows, summarize_rows, write_outputs


def test_scout_trend_capture_summary_counts_metrics_and_missing_rows(tmp_path):
    day_dir = tmp_path / "logs" / "2026-07" / "2026-07-11" / "scout_micro"
    day_dir.mkdir(parents=True)
    rows = [
        {
            "event": "PAPER_CLOSE",
            "symbol": "ADAUSDT",
            "exit_mode": "trend_capture",
            "scout_mission": "NON_RR_HIGH_SCORE",
            "reason": "COST_BREAKEVEN_TIMEOUT",
            "position_realized_pnl": -0.2,
            "max_favorable_r_observed": 1.6,
        },
        {
            "event": "PAPER_CLOSE",
            "symbol": "XMRUSDT",
            "exit_mode": "trend_capture",
            "scout_mission": "NON_RR_HIGH_SCORE",
            "reason": "INITIAL_STOP_HIT",
            "position_realized_pnl": -0.3,
        },
        {
            "event": "PAPER_CLOSE",
            "symbol": "XLMUSDT",
            "exit_mode": "legacy",
            "scout_mission": "NONE",
            "reason": "BREAKEVEN_STOP_HIT",
            "position_realized_pnl": 0.2,
            "max_favorable_r_observed": 2.0,
        },
    ]
    (day_dir / "paper_trades.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    loaded = load_rows(tmp_path / "logs", "2026-07-11", "2026-07-11")
    summary = summarize_rows(loaded)

    assert summary["closed_trades"] == 2
    assert summary["closed_trades_with_max_favorable_r"] == 1
    assert summary["closed_trades_missing_max_favorable_r"] == 1
    assert summary["threshold_touch_counts"][">=1.5R"] == 1
    assert summary["by_mission"]["NON_RR_HIGH_SCORE"]["closed_trades"] == 2
    assert summary["by_symbol"]["ADAUSDT"]["max_favorable_r_observed"] == 1.6


def test_scout_trend_capture_summary_writes_json_and_markdown(tmp_path):
    summary = summarize_rows(
        [
            {
                "event": "PAPER_CLOSE",
                "symbol": "ADAUSDT",
                "exit_mode": "trend_capture",
                "reason": "MAX_HOLD_EXIT",
                "position_realized_pnl": 0.1,
                "max_favorable_r_observed": 2.2,
            }
        ]
    )

    write_outputs(summary, tmp_path / "out", start="2026-07-11", end="2026-07-11")

    assert (tmp_path / "out" / "scout_trend_capture_diagnostics.json").exists()
    markdown = (tmp_path / "out" / "scout_trend_capture_diagnostics.md").read_text(encoding="utf-8")
    assert "SCOUT Trend-Capture Diagnostics" in markdown
    assert ">=1.5R" in markdown
