import json
import subprocess
import sys
from pathlib import Path

from argparse import Namespace

from scripts.run_live_dry_run import (
    build_context,
    next_kline_run_timestamp,
    public_market_context,
    resolve_market_cap_rank_symbols,
    resolve_runtime_symbols,
    warmup_summary,
    warmup_symbols,
)
from src.backtest.engine import BacktestBar
from src.signals.entry_chain_config import EntryChainConfig


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


def test_market_cap_rank_symbols_exclude_stables_and_require_binance_perpetual(monkeypatch):
    def fake_fetch_json(url, params):
        if "coingecko" in url:
            return [
                {"market_cap_rank": 2, "id": "ethereum", "symbol": "eth"},
                {"market_cap_rank": 3, "id": "tether", "symbol": "usdt"},
                {"market_cap_rank": 4, "id": "binancecoin", "symbol": "bnb"},
                {"market_cap_rank": 5, "id": "solana", "symbol": "sol"},
                {"market_cap_rank": 26, "id": "chainlink", "symbol": "link"},
            ]
        return {
            "symbols": [
                {"baseAsset": "BNB", "symbol": "BNBUSDT", "quoteAsset": "USDT", "contractType": "PERPETUAL", "status": "TRADING"},
                {"baseAsset": "SOL", "symbol": "SOLUSDT", "quoteAsset": "USDT", "contractType": "PERPETUAL", "status": "TRADING"},
                {"baseAsset": "LINK", "symbol": "LINKUSDT", "quoteAsset": "USDT", "contractType": "PERPETUAL", "status": "TRADING"},
            ]
        }

    monkeypatch.setattr("scripts.run_live_dry_run.fetch_json", fake_fetch_json)

    symbols, assets = resolve_market_cap_rank_symbols(3, 25)

    assert symbols == ["BNBUSDT", "SOLUSDT"]
    assert [item["market_cap_rank"] for item in assets] == [4, 5]


def test_runtime_symbols_fall_back_to_config_when_market_cap_lookup_fails(monkeypatch):
    def raise_fetch_json(_url, _params):
        raise TimeoutError("offline")

    monkeypatch.setattr("scripts.run_live_dry_run.fetch_json", raise_fetch_json)

    args = Namespace(symbols=None, market_data_source="public-binance")
    symbols, meta = resolve_runtime_symbols(
        args,
        EntryChainConfig(
            dry_run_symbol_source="market_cap_rank",
            dry_run_rank_start=3,
            dry_run_rank_end=25,
            dry_run_symbols=("BNBUSDT", "SOLUSDT"),
        ),
    )

    assert symbols == ["BNBUSDT", "SOLUSDT"]
    assert meta["fallback_used"] is True
    assert meta["source"] == "configured_fallback"
    assert meta["error"] == "TimeoutError"


def test_synthetic_runtime_symbols_use_config_without_market_cap_lookup(monkeypatch):
    def fail_if_called(_url, _params):
        raise AssertionError("market-cap lookup should not run for synthetic source")

    monkeypatch.setattr("scripts.run_live_dry_run.fetch_json", fail_if_called)

    args = Namespace(symbols=None, market_data_source="synthetic")
    symbols, meta = resolve_runtime_symbols(
        args,
        EntryChainConfig(dry_run_symbol_source="market_cap_rank", dry_run_symbols=("DOGEUSDT", "SOLUSDT")),
    )

    assert symbols == ["DOGEUSDT", "SOLUSDT"]
    assert meta["source"] == "configured_synthetic"


def test_public_market_context_accepts_84_closed_15m_bars_for_warmup():
    bars_15m = [
        BacktestBar(symbol="SOLUSDT", timestamp=1000 + index * 900, open=100, high=101, low=99, close=100 + index * 0.01, volume=1000)
        for index in range(84)
    ]
    histories = {
        "15m": bars_15m,
        "30m": bars_15m[-12:],
        "1h": bars_15m[-8:],
        "4h": bars_15m[-4:],
    }

    context, debug = public_market_context("SOLUSDT", bars_15m[-1].timestamp, histories, EntryChainConfig(dry_run_warmup_15m_bars=84))

    assert context.symbol == "SOLUSDT"
    assert debug["warmup"]["ready"] is True
    assert debug["warmup"]["15m"] == 84
    assert debug["warmup"]["required_15m"] == 84
    assert debug["warmup"]["ema200_ready"] is False
    assert warmup_summary({"SOLUSDT": histories}, ["SOLUSDT"])["SOLUSDT"]["ready_15m_84"] is True


def test_public_market_context_degrades_below_84_closed_15m_bars():
    bars_15m = [
        BacktestBar(symbol="SOLUSDT", timestamp=1000 + index * 900, open=100, high=101, low=99, close=100, volume=1000)
        for index in range(83)
    ]
    histories = {"15m": bars_15m, "30m": bars_15m[-12:], "1h": bars_15m[-8:], "4h": bars_15m[-4:]}

    context, debug = public_market_context("SOLUSDT", bars_15m[-1].timestamp, histories, EntryChainConfig(dry_run_warmup_15m_bars=84))

    assert context.polluted_until_ts > 0
    assert debug["warmup"]["ready"] is False
    assert debug["warmup"]["15m"] == 83


def test_warmup_symbols_fetches_ema_safe_limit(monkeypatch):
    calls = []

    def fake_fetch_public_market_histories(symbol, *, limit):
        calls.append((symbol, limit))
        return {"15m": []}

    monkeypatch.setattr("scripts.run_live_dry_run.fetch_public_market_histories", fake_fetch_public_market_histories)

    args = Namespace(public_kline_limit=84)
    warmup_symbols(["BNBUSDT", "SOLUSDT"], args, EntryChainConfig(use_ema_architecture=True, dry_run_warmup_15m_bars=84))

    assert calls == [("BNBUSDT", 201), ("SOLUSDT", 201)]


def test_build_context_uses_warmup_cache_when_current_fetch_fails(monkeypatch):
    bars_15m = [
        BacktestBar(symbol="SOLUSDT", timestamp=1000 + index * 900, open=100, high=101, low=99, close=100 + index * 0.01, volume=1000)
        for index in range(84)
    ]
    histories = {"15m": bars_15m, "30m": bars_15m[-12:], "1h": bars_15m[-8:], "4h": bars_15m[-4:]}

    def raise_fetch(_symbol, *, limit):
        raise TimeoutError("offline")

    monkeypatch.setattr("scripts.run_live_dry_run.fetch_public_market_histories", raise_fetch)

    args = Namespace(market_data_source="public-binance", public_kline_limit=84)
    context, health, debug = build_context("SOLUSDT", bars_15m[-1].timestamp, args, EntryChainConfig(dry_run_warmup_15m_bars=84), histories)

    assert context.symbol == "SOLUSDT"
    assert health == "DEGRADED"
    assert debug["warmup"]["cache_fallback"] is True
    assert debug["warmup"]["error"] == "TimeoutError"


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
