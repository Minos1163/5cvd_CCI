import json

from scripts.audit_4x_short_q1_overlap import load_decision_index, load_trade_closes, select_4x_short, summarize


def _close(symbol, quadrant="Q1", leverage=4, nominal=-10.0, leveraged=-40.0, channel=None):
    return {
        "event": "PAPER_CLOSE",
        "symbol": symbol,
        "side": "SHORT",
        "leverage": leverage,
        "source_quadrant": quadrant,
        "entry_channel": channel,
        "remaining_fraction": 0.0,
        "position_realized_pnl": nominal,
        "position_margin_realized_pnl": leveraged,
        "timestamp": 100,
    }


def _open(symbol, timestamp, notional, quadrant, channel, side="SHORT"):
    return {
        "event": "PAPER_OPEN",
        "symbol": symbol,
        "side": side,
        "timestamp": timestamp,
        "notional": notional,
        "source_quadrant": quadrant,
        "entry_channel": channel,
    }


def test_select_4x_short_excludes_other_leverage_side_and_partial_rows():
    rows = [
        _close("SOLUSDT"),
        _close("BNBUSDT", leverage=3),
        {**_close("ETHUSDT"), "side": "LONG"},
        {**_close("LINKUSDT"), "remaining_fraction": 0.5},
    ]
    selected = select_4x_short(rows)
    assert [row["symbol"] for row in selected] == ["SOLUSDT"]


def test_select_preserves_entry_association_fields():
    row = _close("SOLUSDT")
    row.update({"entry_timestamp": 50, "entry_notional": 1234.5, "entry_channel_at_open": "main_direct"})
    selected = select_4x_short([row])
    assert selected[0]["entry_timestamp"] == 50
    assert selected[0]["notional"] == 1234.5
    assert selected[0]["entry_channel"] == "main_direct"


def test_summary_reports_q1_overlap_and_nominal_vs_leveraged_pnl():
    selected = select_4x_short([_close("SOLUSDT"), _close("LINKUSDT", quadrant="Q3", nominal=-5, leveraged=-20)])
    summary = summarize(selected)
    assert summary["trade_count"] == 2
    assert summary["nominal_pnl"] == -15.0
    assert summary["leveraged_pnl"] == -60.0
    assert summary["q1_overlap"]["count"] == 1
    assert summary["by_symbol"]["SOLUSDT"]["leveraged_pnl"] == -40.0


def test_summary_does_not_match_risk_metadata_without_entry_association():
    selected = select_4x_short([_close("SOLUSDT")])
    decisions = {("SOLUSDT", 100): {"metadata": {"risk_budget": {"final_notional": 1}}}}
    assert selected[0]["entry_timestamp"] == 0
    assert summarize(selected, decisions)["risk_budget_comparison"]["matched_decision_metadata_count"] == 0


def test_load_trade_closes_reads_final_closes_only(tmp_path):
    day = tmp_path / "2026-08" / "2026-08-24"
    day.mkdir(parents=True)
    (day / "paper_trades.jsonl").write_text(
        "\n".join(
            [
                json.dumps(_open("SOLUSDT", 50, 100.0, "Q1", "main_direct")),
                json.dumps(_close("SOLUSDT")),
                json.dumps({**_close("SOLUSDT"), "event": "PAPER_REDUCE", "remaining_fraction": 0.5}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert len(load_trade_closes(tmp_path, "2026-08-24", "2026-08-24")) == 1


def test_load_trade_closes_excludes_unmatched_final_close(tmp_path):
    day = tmp_path / "2026-08" / "2026-08-24"
    day.mkdir(parents=True)
    (day / "paper_trades.jsonl").write_text(json.dumps(_close("SOLUSDT")) + "\n", encoding="utf-8")

    assert load_trade_closes(tmp_path, "2026-08-24", "2026-08-24") == []


def test_load_trade_closes_associates_cross_day_repeated_symbol_side_fifo_and_risk_metadata(tmp_path):
    first_day = tmp_path / "2026-08" / "2026-08-24"
    second_day = tmp_path / "2026-08" / "2026-08-25"
    first_day.mkdir(parents=True)
    second_day.mkdir(parents=True)
    (first_day / "paper_trades.jsonl").write_text(
        "\n".join(
            [
                json.dumps(_open("SOLUSDT", 100, 111.0, "Q1", "main_direct")),
                json.dumps(_open("SOLUSDT", 200, 222.0, "Q3", "main_probe")),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (second_day / "paper_trades.jsonl").write_text(
        "\n".join(
            [
                json.dumps({**_close("SOLUSDT", quadrant=None, nominal=-1.0, leveraged=-4.0), "timestamp": 300}),
                json.dumps({**_close("SOLUSDT", quadrant=None, nominal=-2.0, leveraged=-8.0), "timestamp": 400}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (first_day / "decisions.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "symbol": "SOLUSDT",
                        "kline": {"timestamp": 100},
                        "metadata": {"risk_budget": {"final_notional": 111.0}},
                    }
                ),
                json.dumps(
                    {
                        "symbol": "SOLUSDT",
                        "kline": {"timestamp": 200},
                        "metadata": {"risk_budget": {"final_notional": 222.0}},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    closes = load_trade_closes(tmp_path, "2026-08-24", "2026-08-25")
    selected = select_4x_short(closes)
    decisions = load_decision_index(tmp_path, "2026-08-24", "2026-08-25")
    summary = summarize(selected, decisions)

    assert [(row["entry_timestamp"], row["entry_notional"]) for row in closes] == [(100, 111.0), (200, 222.0)]
    assert [row["entry_channel"] for row in selected] == ["main_direct", "main_probe"]
    assert [row["source_quadrant"] for row in selected] == ["Q1", "Q3"]
    assert summary["risk_budget_comparison"]["matched_decision_metadata_count"] == 2
