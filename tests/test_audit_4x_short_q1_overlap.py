import json

from scripts.audit_4x_short_q1_overlap import load_trade_closes, select_4x_short, summarize


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


def test_load_trade_closes_reads_final_closes_only(tmp_path):
    day = tmp_path / "2026-08" / "2026-08-24"
    day.mkdir(parents=True)
    (day / "paper_trades.jsonl").write_text(
        "\n".join(
            [
                json.dumps(_close("SOLUSDT")),
                json.dumps({**_close("SOLUSDT"), "event": "PAPER_REDUCE", "remaining_fraction": 0.5}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert len(load_trade_closes(tmp_path, "2026-08-24", "2026-08-24")) == 1
