import json
import subprocess
import sys
from pathlib import Path

from argparse import Namespace

from scripts.run_live_dry_run import (
    apply_paper_state_to_context,
    apply_dry_run_decision_controls,
    build_context,
    next_kline_run_timestamp,
    public_market_context,
    render_symbol_log,
    render_paper_account_header,
    render_schedule_wait_log,
    render_startup_log,
    resolve_paper_state_dir,
    resolve_market_cap_rank_symbols,
    resolve_output_dir,
    resolve_runtime_symbols,
    runtime_log_name,
    warmup_summary,
    warmup_symbols,
)
from src.backtest.engine import BacktestBar
from src.observability.paper_trading import PaperTradingLedger
from src.signals.entry_chain import EntryChainContext, EntryChainDecision, evaluate_entry_chain
from src.signals.entry_chain_config import EntryChainConfig


def direct_decision(symbol: str = "SOLUSDT", score: float = 88.0) -> EntryChainDecision:
    return EntryChainDecision(
        action="DIRECT",
        side="SHORT",
        score=score,
        weights={},
        component_points={},
        reasons=(),
        risk_allowed=True,
        leverage=4,
        max_symbol_exposure_pct=0.2,
        notional_hint=2000.0,
        liquidity_ratio=100.0,
        metadata={"symbol": symbol},
    )


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
    runtime_logs = sorted(tmp_path.glob("runtime.out.*.log"))
    assert len(runtime_logs) == 1
    runtime_log = runtime_logs[0]
    assert runtime_log.exists()
    runtime_text = runtime_log.read_text(encoding="utf-8")
    assert "AI300_DRY_RUN cycle" in runtime_text
    assert "AI300_DRY_RUN process_start" in runtime_text
    assert "进程启动:" in runtime_text
    assert "first_scan_wait:" in runtime_text
    assert "当前权益: equity=" in runtime_text
    assert "realized=" in runtime_text
    assert "win_rate=" in runtime_text
    assert "open_positions=" in runtime_text
    assert "K线预热" in runtime_text
    assert "评分明细" in runtime_text
    assert "决策原因" in runtime_text
    assert "PAPER账本" in runtime_text
    assert "cycle_started_utc=" in runtime_text
    assert "cycle_finished_utc=" in runtime_text
    health = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert health["mode"] == "dry_run"
    assert health["orders_submitted"] == 0
    assert summary["orders_submitted"] == 0
    assert summary["data_health"] == "OK"
    paper_summary = json.loads((tmp_path / "paper_summary.json").read_text(encoding="utf-8"))
    assert paper_summary["open_positions"] >= 0
    assert "realized_pnl" in paper_summary
    assert "realized_notional_pnl" in paper_summary
    assert "realized_margin_pnl" in paper_summary
    assert paper_summary["pnl_accounting_mode"] == "notional_primary_margin_reporting"
    assert "profit_factor" in paper_summary
    assert "updated_at" in paper_summary
    assert "latest_kline_timestamp" in paper_summary
    paper_equity = json.loads((tmp_path / "paper_equity.json").read_text(encoding="utf-8"))
    assert "updated_at" in paper_equity
    assert "latest_kline_timestamp" in paper_equity
    assert "margin_equity" in paper_equity


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


def test_fib_pa_dry_run_once_emits_new_score_components_without_orders(tmp_path):
    subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            "configs/entry_chain.dry_run_fib_pa_v1.json",
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
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    scores = row["score_detail"]["scores"]

    assert summary["orders_submitted"] == 0
    assert "trend_ema_context" in scores
    assert "flow_cvd_confirmation" in scores
    assert "cci_momentum_quality" in scores
    assert "price_action_structure" in scores
    assert "fibonacci_location" in scores
    assert "risk_reward_geometry" in scores


def test_render_symbol_log_uses_fib_pa_score_detail_when_enabled():
    context = EntryChainContext(
        symbol="SOLUSDT",
        timestamp=1000,
        side="LONG",
        component_scores={},
        quote_volume_24h=100_000_000.0,
        atr_pct=0.01,
        expected_order_size=1000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
        stop_pct=0.015,
    )
    decision_payload = {
        "action": "WATCH",
        "score": 77.49,
        "leverage": 0,
        "max_symbol_exposure_pct": 0.2,
        "liquidity_ratio": 1000.0,
        "reasons": ["FIB_PA_ARCHITECTURE_WEIGHTS"],
        "score_detail": {
            "scores": {
                "trend_ema_context": 0.80,
                "flow_cvd_confirmation": 1.00,
                "cci_momentum_quality": 0.20,
                "price_action_structure": 0.95,
                "fibonacci_location": 1.00,
                "risk_reward_geometry": 0.1875,
                "fib_action_cap": 1.0,
            },
            "points": {
                "trend_ema_context": 16.0,
                "flow_cvd_confirmation": 18.0,
                "cci_momentum_quality": 2.8,
                "price_action_structure": 21.0,
                "fibonacci_location": 18.0,
                "risk_reward_geometry": 1.5,
            },
            "weights": {
                "trend_ema_context": 20.0,
                "flow_cvd_confirmation": 18.0,
                "cci_momentum_quality": 14.0,
                "price_action_structure": 22.0,
                "fibonacci_location": 18.0,
                "risk_reward_geometry": 8.0,
            },
            "diagnostics": {
                "risk_reward_geometry": {
                    "net_tp1_r": 0.87,
                    "rr_zero_reason": "NET_TP1_R_TOO_LOW",
                }
            },
        },
    }

    lines = render_symbol_log(
        "SOLUSDT",
        context,
        decision_payload,
        {"approved": False, "reason": "waiting"},
        {"action": "ALLOW", "estimated_loss_pct": 0.0},
        {"kline": {}, "warmup": {}},
    )

    score_line = next(line for line in lines if "评分明细" in line)
    assert "ema=0.8000->16.0000" in score_line
    assert "cvd=1.0000->18.0000" in score_line
    assert "cci=0.2000->2.8000" in score_line
    assert "pa=0.9500->21.0000" in score_line
    assert "fib=1.0000->18.0000" in score_line
    assert "rr=0.1875->1.5000" in score_line
    assert "fib_cap=1.0000" in score_line
    assert "rr_net=0.8700" in score_line
    assert "rr_zero=NET_TP1_R_TOO_LOW" in score_line


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


def test_live_dry_run_injects_paper_state_before_duplicate_symbol_approval(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision_payload = {
        "action": "DIRECT",
        "side": "SHORT",
        "score": 88,
        "leverage": 3,
        "entry_context": {"atr_pct": 0.01},
        "reasons": ["TEST_DIRECT"],
    }
    draft_payload = {
        "approved": True,
        "request": {"position_side": "SHORT", "quantity": 10, "price": 100},
    }
    ledger.on_decision(
        symbol="LABUSDT",
        decision_payload=decision_payload,
        draft_payload=draft_payload,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )
    next_day = 1000 + 86400
    context = EntryChainContext(
        symbol="LABUSDT",
        timestamp=next_day,
        side="SHORT",
        component_scores={
            "background_4h": 1.0,
            "direction_1h": 1.0,
            "quality_30m": 1.0,
            "trigger_15m": 1.0,
            "cvd_flow": 1.0,
            "volatility_stop": 1.0,
            "liquidity_execution": 1.0,
            "market_regime": 1.0,
        },
        quote_volume_24h=200_000_000.0,
        atr_pct=0.018,
        expected_order_size=1_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
    )

    hydrated = apply_paper_state_to_context(context, ledger, next_day)
    decision = evaluate_entry_chain(hydrated, EntryChainConfig(max_symbol_trades_per_day=1))

    assert hydrated.active_symbols == 1
    assert hydrated.active_symbol_names == frozenset({"LABUSDT"})
    assert hydrated.symbol_trades_today == 0
    assert hydrated.symbol_exposure_pct > 0
    assert decision.action == "NO_TRADE"
    assert "SYMBOL_POSITION_ALREADY_OPEN" in decision.reasons


def test_dry_run_decision_controls_cap_observation_only_symbol_to_watch(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision = direct_decision("XLMUSDT", score=94.0)
    config = EntryChainConfig(observation_only_symbols=("XLMUSDT",))

    controlled = apply_dry_run_decision_controls(decision, config=config, paper=ledger, timestamp=5000)

    assert controlled.action == "WATCH"
    assert controlled.side == "NONE"
    assert controlled.risk_allowed is False
    assert controlled.leverage == 0
    assert controlled.notional_hint == 0.0
    assert "SYMBOL_OBSERVATION_ONLY" in controlled.reasons


def test_dry_run_decision_controls_demote_weak_edge_without_positive_history(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision = direct_decision("LINKUSDT", score=83.58)
    config = EntryChainConfig(weak_edge_direct_min_score=82.0, weak_edge_direct_max_score=85.0)

    controlled = apply_dry_run_decision_controls(decision, config=config, paper=ledger, timestamp=5000)

    assert controlled.action == "WATCH"
    assert "DIRECT_WEAK_EDGE_DEMOTED" in controlled.reasons


def test_dry_run_decision_controls_keep_weak_edge_with_positive_history(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision_payload = {
        "action": "DIRECT",
        "side": "LONG",
        "score": 88,
        "leverage": 4,
        "entry_context": {"atr_pct": 0.01},
        "reasons": ["TEST_DIRECT"],
    }
    draft_payload = {
        "approved": True,
        "request": {"position_side": "LONG", "quantity": 10, "price": 100},
    }
    ledger.on_decision(symbol="LINKUSDT", decision_payload=decision_payload, draft_payload=draft_payload, kline={"close": 100, "high": 100, "low": 100}, timestamp=1000)
    ledger.on_decision(symbol="LINKUSDT", decision_payload={"action": "NO_TRADE"}, draft_payload={"approved": False}, kline={"close": 103, "high": 103, "low": 101}, timestamp=1900)
    ledger.on_decision(symbol="LINKUSDT", decision_payload={"action": "NO_TRADE"}, draft_payload={"approved": False}, kline={"close": 105, "high": 105, "low": 103}, timestamp=2800)
    ledger.on_decision(symbol="LINKUSDT", decision_payload={"action": "NO_TRADE"}, draft_payload={"approved": False}, kline={"close": 106, "high": 106, "low": 104}, timestamp=3700)

    controlled = apply_dry_run_decision_controls(
        direct_decision("LINKUSDT", score=83.58),
        config=EntryChainConfig(weak_edge_direct_min_score=82.0, weak_edge_direct_max_score=85.0),
        paper=ledger,
        timestamp=5000,
    )

    assert controlled.action == "DIRECT"
    assert "DIRECT_WEAK_EDGE_DEMOTED" not in controlled.reasons


def test_dry_run_decision_controls_apply_rolling_initial_stop_cooldown(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision_payload = {
        "action": "DIRECT",
        "side": "LONG",
        "score": 88,
        "leverage": 4,
        "entry_context": {"atr_pct": 0.01},
        "reasons": ["TEST_DIRECT"],
    }
    draft_payload = {
        "approved": True,
        "request": {"position_side": "LONG", "quantity": 10, "price": 100},
    }
    ledger.on_decision(symbol="XLMUSDT", decision_payload=decision_payload, draft_payload=draft_payload, kline={"close": 100, "high": 100, "low": 100}, timestamp=1000)
    ledger.on_decision(symbol="XLMUSDT", decision_payload={"action": "NO_TRADE"}, draft_payload={"approved": False}, kline={"close": 100, "high": 103, "low": 98}, timestamp=1900)
    ledger.on_decision(symbol="XLMUSDT", decision_payload=decision_payload, draft_payload=draft_payload, kline={"close": 100, "high": 100, "low": 100}, timestamp=3000)
    ledger.on_decision(symbol="XLMUSDT", decision_payload={"action": "NO_TRADE"}, draft_payload={"approved": False}, kline={"close": 100, "high": 103, "low": 98}, timestamp=3900)
    config = EntryChainConfig(
        rolling_symbol_cooldown_enabled=True,
        rolling_symbol_cooldown_stop_threshold=2,
        rolling_symbol_cooldown_window_hours=48,
        rolling_symbol_cooldown_hours=24,
    )

    controlled = apply_dry_run_decision_controls(direct_decision("XLMUSDT", score=94.0), config=config, paper=ledger, timestamp=4000)

    assert controlled.action == "WATCH"
    assert "SYMBOL_ROLLING_INITIAL_STOP_COOLDOWN" in controlled.reasons


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


def test_highest_win_market_cap_fallback_symbols_match_rank_universe(monkeypatch):
    def raise_fetch_json(_url, _params):
        raise TimeoutError("offline")

    monkeypatch.setattr("scripts.run_live_dry_run.fetch_json", raise_fetch_json)

    args = Namespace(symbols=None, market_data_source="public-binance")
    config = EntryChainConfig.from_mapping(
        json.loads(Path("configs/entry_chain.dry_run_highest_win.json").read_text(encoding="utf-8"))
    )
    symbols, meta = resolve_runtime_symbols(args, config)

    assert meta["source"] == "configured_fallback"
    assert symbols == [
        "BNBUSDT",
        "XRPUSDT",
        "SOLUSDT",
        "TRXUSDT",
        "HYPEUSDT",
        "DOGEUSDT",
        "ZECUSDT",
        "XLMUSDT",
        "ADAUSDT",
        "XMRUSDT",
        "LINKUSDT",
        "CCUSDT",
        "TONUSDT",
    ]


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


def test_public_market_context_accepts_240_closed_15m_bars_for_warmup():
    bars_15m = [
        BacktestBar(symbol="SOLUSDT", timestamp=1000 + index * 900, open=100, high=101, low=99, close=100 + index * 0.01, volume=1000)
        for index in range(240)
    ]
    histories = {
        "15m": bars_15m,
        "30m": bars_15m[-12:],
        "1h": bars_15m[-8:],
        "4h": bars_15m[-4:],
    }

    context, debug = public_market_context("SOLUSDT", bars_15m[-1].timestamp, histories, EntryChainConfig(dry_run_warmup_15m_bars=240))

    assert context.symbol == "SOLUSDT"
    assert debug["warmup"]["ready"] is True
    assert debug["warmup"]["15m"] == 240
    assert debug["warmup"]["required_15m"] == 240
    assert debug["warmup"]["ema200_ready"] is True
    assert warmup_summary({"SOLUSDT": histories}, ["SOLUSDT"], 240)["SOLUSDT"]["ready_15m"] is True


def test_public_market_context_degrades_below_240_closed_15m_bars():
    bars_15m = [
        BacktestBar(symbol="SOLUSDT", timestamp=1000 + index * 900, open=100, high=101, low=99, close=100, volume=1000)
        for index in range(239)
    ]
    histories = {"15m": bars_15m, "30m": bars_15m[-12:], "1h": bars_15m[-8:], "4h": bars_15m[-4:]}

    context, debug = public_market_context("SOLUSDT", bars_15m[-1].timestamp, histories, EntryChainConfig(dry_run_warmup_15m_bars=240))

    assert context.polluted_until_ts > 0
    assert debug["warmup"]["ready"] is False
    assert debug["warmup"]["15m"] == 239


def test_warmup_symbols_fetches_ema_safe_limit(monkeypatch):
    calls = []

    def fake_fetch_public_market_histories(symbol, *, limit):
        calls.append((symbol, limit))
        return {"15m": []}

    monkeypatch.setattr("scripts.run_live_dry_run.fetch_public_market_histories", fake_fetch_public_market_histories)

    args = Namespace(public_kline_limit=84)
    warmup_symbols(["BNBUSDT", "SOLUSDT"], args, EntryChainConfig(use_ema_architecture=True, dry_run_warmup_15m_bars=240))

    assert calls == [("BNBUSDT", 241), ("SOLUSDT", 241)]


def test_build_context_uses_warmup_cache_when_current_fetch_fails(monkeypatch):
    bars_15m = [
        BacktestBar(symbol="SOLUSDT", timestamp=1000 + index * 900, open=100, high=101, low=99, close=100 + index * 0.01, volume=1000)
        for index in range(240)
    ]
    histories = {"15m": bars_15m, "30m": bars_15m[-12:], "1h": bars_15m[-8:], "4h": bars_15m[-4:]}

    def raise_fetch(_symbol, *, limit):
        raise TimeoutError("offline")

    monkeypatch.setattr("scripts.run_live_dry_run.fetch_public_market_histories", raise_fetch)

    args = Namespace(market_data_source="public-binance", public_kline_limit=84)
    context, health, debug = build_context("SOLUSDT", bars_15m[-1].timestamp, args, EntryChainConfig(dry_run_warmup_15m_bars=240), histories)

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
    assert len(list(output_dir.glob("runtime.out.*.log"))) == 1
    assert (output_dir / "attribution.jsonl").exists()
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["orders_submitted"] == 0


def test_log_root_output_dir_rolls_by_cycle_timestamp(tmp_path):
    args = Namespace(output_dir=None, log_root=str(tmp_path), log_date=None)

    first = resolve_output_dir(args, timestamp=1781999999)
    second = resolve_output_dir(args, timestamp=1782000000)

    assert first == tmp_path / "2026-06" / "2026-06-20"
    assert second == tmp_path / "2026-06" / "2026-06-21"


def test_log_root_output_dir_rolls_across_utc_day_boundary(tmp_path):
    args = Namespace(output_dir=None, log_root=str(tmp_path), log_date=None)

    before_midnight = resolve_output_dir(args, timestamp=1781999999)
    after_midnight = resolve_output_dir(args, timestamp=1782000000)

    assert before_midnight == tmp_path / "2026-06" / "2026-06-20"
    assert after_midnight == tmp_path / "2026-06" / "2026-06-21"


def test_paper_state_dir_defaults_next_to_log_root(tmp_path):
    args = Namespace(output_dir=None, log_root=str(tmp_path / "logs"), log_date=None, paper_state_dir=None)

    assert resolve_paper_state_dir(args) == tmp_path / "state" / "paper"


def test_paper_state_dir_uses_output_dir_for_explicit_one_shot_output(tmp_path):
    args = Namespace(output_dir=str(tmp_path / "out"), log_root=str(tmp_path / "logs"), log_date=None, paper_state_dir=None)

    assert resolve_paper_state_dir(args) == tmp_path / "out"


def test_paper_state_dir_can_be_overridden(tmp_path):
    args = Namespace(output_dir=None, log_root=str(tmp_path / "logs"), log_date=None, paper_state_dir=str(tmp_path / "custom-paper"))

    assert resolve_paper_state_dir(args) == tmp_path / "custom-paper"


def test_render_paper_account_header_uses_ledger_state(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    decision = {
        "action": "DIRECT",
        "side": "LONG",
        "score": 88,
        "leverage": 4,
        "entry_context": {"atr_pct": 0.01},
        "reasons": ["TEST_DIRECT"],
    }
    draft = {
        "approved": True,
        "request": {
            "position_side": "LONG",
            "quantity": 10,
            "price": 100,
        },
    }
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload=decision,
        draft_payload=draft,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=1000,
    )
    ledger.on_decision(
        symbol="SOLUSDT",
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline={"close": 101, "high": 101, "low": 100.5},
        timestamp=1900,
    )

    header = render_paper_account_header(ledger, 1900)

    assert header.startswith("当前权益: equity=")
    assert "available=7750.00 USDT" in header
    assert "realized=" in header
    assert "unrealized=" in header
    assert "max_dd=" in header
    assert "pf=" in header
    assert "trades=0" in header
    assert "open_positions=1" in header


def test_next_kline_run_timestamp_aligns_after_quarter_hour_close():
    assert next_kline_run_timestamp(0, 900, 5) == 5
    assert next_kline_run_timestamp(4.5, 900, 5) == 5
    assert next_kline_run_timestamp(5, 900, 5) == 905
    assert next_kline_run_timestamp(899, 900, 5) == 905
    assert next_kline_run_timestamp(900, 900, 5) == 905
    assert next_kline_run_timestamp(905.1, 900, 5) == 1805


def test_runtime_log_name_uses_utc_six_hour_buckets():
    assert runtime_log_name(0) == "runtime.out.00.log"
    assert runtime_log_name(5 * 3600 + 3599) == "runtime.out.00.log"
    assert runtime_log_name(6 * 3600) == "runtime.out.06.log"
    assert runtime_log_name(11 * 3600 + 3599) == "runtime.out.06.log"
    assert runtime_log_name(12 * 3600) == "runtime.out.12.log"
    assert runtime_log_name(18 * 3600) == "runtime.out.18.log"
    assert runtime_log_name(23 * 3600 + 3599) == "runtime.out.18.log"


def test_startup_log_reports_first_aligned_scan_wait():
    args = Namespace(
        market_data_source="public-binance",
        align_to_kline_close=True,
        kline_interval_seconds=900,
        post_close_delay_seconds=5.0,
        interval_seconds=60.0,
        config="configs/entry_chain.dry_run_highest_win.json",
        target_tier="aggressive",
        log_root="/root/AIBOT/logs",
    )
    symbol_meta = {"source": "market_cap_rank", "rank_start": 3, "rank_end": 25, "fallback_used": False, "error": None}

    lines = render_startup_log(args, 906, ["SOLUSDT"], symbol_meta, {"SOLUSDT": {"15m": []}}, 240)

    assert lines[0].startswith("=== AI300_DRY_RUN process_start @ 1970-01-01 00:15:06 UTC")
    assert "进程启动: pid=" in lines[1]
    assert "symbols=1" in lines[2]
    assert "启动预热完成:" in lines[3]
    assert lines[4] == "first_scan_wait: next_review_utc=1970-01-01 00:30:05 UTC, post_close_delay=5.00s, sleep_until_first_scan=899.00s"


def test_schedule_wait_log_includes_alignment_sleep_seconds():
    args = Namespace(
        once=False,
        align_to_kline_close=True,
        kline_interval_seconds=900,
        post_close_delay_seconds=5.0,
        interval_seconds=60.0,
    )

    line = render_schedule_wait_log(args, 900, 906.25, 4.5)

    assert line.startswith("调度等待: kline_align=ON")
    assert "next_review_utc=1970-01-01 00:30:05 UTC" in line
    assert "post_close_delay=5.00s" in line
    assert "cycle_started_utc=1970-01-01 00:15:00 UTC" in line
    assert "cycle_finished_utc=1970-01-01 00:15:06 UTC" in line
    assert "elapsed=4.50s" in line
    assert "sleep_until_next=898.75s" in line


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
