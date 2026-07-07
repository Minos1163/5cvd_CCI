import json
import subprocess
import sys
from pathlib import Path

from argparse import Namespace

from scripts.run_live_dry_run import (
    apply_paper_state_to_context,
    apply_dry_run_decision_controls,
    build_scout_micro_payloads,
    build_near_miss_payload,
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
    scout_micro_mission,
    should_open_scout_micro,
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


def probe_decision(symbol: str = "SOLUSDT", score: float = 82.0) -> EntryChainDecision:
    return EntryChainDecision(
        action="PROBE",
        side="LONG",
        score=score,
        weights={},
        component_points={},
        reasons=("TEST_PROBE",),
        risk_allowed=True,
        leverage=3,
        max_symbol_exposure_pct=0.2,
        notional_hint=500.0,
        liquidity_ratio=100.0,
        metadata={"symbol": symbol},
    )


def open_and_stop(
    ledger: PaperTradingLedger,
    symbol: str,
    *,
    opened_at: int,
    stopped_at: int,
    side: str = "LONG",
) -> None:
    decision_payload = {
        "action": "PROBE",
        "side": side,
        "score": 88,
        "leverage": 3,
        "entry_context": {"atr_pct": 0.01},
        "reasons": ["TEST_PROBE"],
    }
    draft_payload = {
        "approved": True,
        "request": {"position_side": side, "quantity": 10, "price": 100},
    }
    ledger.on_decision(
        symbol=symbol,
        decision_payload=decision_payload,
        draft_payload=draft_payload,
        kline={"close": 100, "high": 100, "low": 100},
        timestamp=opened_at,
    )
    stop_kline = {"close": 99, "high": 100, "low": 98} if side == "LONG" else {"close": 101, "high": 102, "low": 100}
    ledger.on_decision(
        symbol=symbol,
        decision_payload={"action": "NO_TRADE"},
        draft_payload={"approved": False},
        kline=stop_kline,
        timestamp=stopped_at,
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
    assert "gate_rejections_by_layer" in summary
    assert "probe" in summary["gate_rejections_by_layer"]
    assert "dry_run_assumptions" in summary
    assert summary["dry_run_assumptions"]["paper_fee_bps"] == 5.0
    assert summary["dry_run_assumptions"]["paper_slippage_bps"] == 5.0
    assert summary["dry_run_assumptions"]["net_beta_exposure_model"] == "not_configured"
    assert "latest_portfolio_exposure" in summary
    assert summary["latest_portfolio_exposure"]["open_position_count"] >= 0
    assert "net_side_exposure_pct" in summary["latest_portfolio_exposure"]
    assert summary["latest_portfolio_exposure"]["net_beta_exposure_model"] == "not_configured"
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


def test_live_dry_run_records_near_miss_jsonl_and_summary(tmp_path):
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
            "--near-miss-min-score",
            "0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    rows = [json.loads(line) for line in (tmp_path / "near_misses.jsonl").read_text(encoding="utf-8").splitlines()]
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["scout_candidate"] is True
    assert rows[0]["action"] in {"WATCH", "NO_TRADE"}
    assert "component_points" in rows[0]
    assert summary["near_miss_count"] == 1


def test_live_dry_run_opens_observation_only_xlm_in_scout_micro_ledger(tmp_path):
    config_path = tmp_path / "entry_chain.scout_micro_test.json"
    config_payload = json.loads(Path("configs/entry_chain.dry_run_fib_pa_v1.json").read_text(encoding="utf-8"))
    config_payload["scout_micro_min_score"] = 0.0
    config_payload["scout_micro_non_rr_min_score"] = 0.0
    config_path.write_text(json.dumps(config_payload), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            "scripts/run_live_dry_run.py",
            "--config",
            str(config_path),
            "--target-tier",
            "aggressive",
            "--market-data-source",
            "synthetic",
            "--once",
            "--output-dir",
            str(tmp_path),
            "--symbols",
            "XLMUSDT",
            "--near-miss-min-score",
            "0",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    main_trades = (tmp_path / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()
    scout_trades = [
        json.loads(line)
        for line in (tmp_path / "scout_micro" / "paper_trades.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    scout_summary = json.loads((tmp_path / "scout_micro" / "paper_summary.json").read_text(encoding="utf-8"))

    assert main_trades == []
    assert scout_trades[0]["event"] == "PAPER_OPEN"
    assert scout_trades[0]["symbol"] == "XLMUSDT"
    assert scout_trades[0]["notional"] == 50.0
    assert scout_trades[0]["leverage"] == 1
    assert "SCOUT_MICRO" in scout_trades[0]["reasons"]
    assert scout_trades[0]["scout_mission"] == "NON_RR_HIGH_SCORE"
    assert scout_summary["open_positions"] == 1


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


def test_build_near_miss_payload_captures_high_score_rejected_signal():
    payload = build_near_miss_payload(
        {
            "timestamp": 1782992705,
            "symbol": "CCUSDT",
            "action": "WATCH",
            "side": "NONE",
            "score": 90.59,
            "reasons": [
                "FIB_PA_ARCHITECTURE_WEIGHTS",
                "HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0",
            ],
            "component_points": {
                "risk_reward_geometry": 2.0,
                "fibonacci_location": 18.0,
                "price_action_structure": 21.0,
            },
            "score_detail": {
                "diagnostics": {"risk_reward_geometry": {"net_tp1_r": 1.02}},
            },
            "entry_context": {"atr_pct": 0.01, "side": "SHORT"},
            "kline": {"close": 100.0, "high": 101.0, "low": 99.0, "timestamp": 1782991800},
        },
        min_score=82.0,
    )

    assert payload is not None
    assert payload["scout_candidate"] is True
    assert payload["primary_reason"] == "HIGH_BETA_PROBE_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_3.0"
    assert payload["intended_side"] == "SHORT"
    assert payload["entry_price"] == 100.0
    assert payload["component_points"]["risk_reward_geometry"] == 2.0
    assert payload["diagnostics"]["risk_reward_geometry"]["net_tp1_r"] == 1.02


def test_build_near_miss_payload_tags_targeted_long_offset_candidate():
    payload = build_near_miss_payload(
        {
            "timestamp": 1782992705,
            "symbol": "XLMUSDT",
            "action": "WATCH",
            "side": "NONE",
            "score": 80.5,
            "reasons": ["SIDE_THRESHOLD_OFFSET_LONG_10.00"],
            "component_points": {
                "price_action_structure": 18.0,
                "fibonacci_location": 13.0,
                "risk_reward_geometry": 4.0,
            },
            "entry_context": {"side": "LONG"},
            "kline": {"close": 0.25, "timestamp": 1782991800},
        },
        min_score=80.0,
    )

    assert payload is not None
    assert payload["targeted_long_offset"] is True
    assert payload["scout_tags"] == ["TARGETED_LONG_OFFSET"]


def test_build_near_miss_payload_records_targeted_long_below_global_min_score():
    payload = build_near_miss_payload(
        {
            "timestamp": 1782992705,
            "symbol": "CCUSDT",
            "action": "WATCH",
            "side": "NONE",
            "score": 80.5,
            "reasons": ["SIDE_THRESHOLD_OFFSET_LONG_10.00"],
            "component_points": {
                "price_action_structure": 18.0,
                "fibonacci_location": 18.0,
                "risk_reward_geometry": 3.0,
            },
            "entry_context": {"side": "LONG"},
            "kline": {"close": 0.25, "timestamp": 1782991800},
        },
        min_score=82.0,
    )

    assert payload is not None
    assert payload["targeted_long_offset"] is True
    assert payload["scout_tags"] == ["TARGETED_LONG_OFFSET"]


def test_build_near_miss_payload_does_not_tag_short_or_weak_pa_offset():
    short_payload = build_near_miss_payload(
        {
            "timestamp": 1782992705,
            "symbol": "XLMUSDT",
            "action": "WATCH",
            "score": 84.0,
            "reasons": ["SIDE_THRESHOLD_OFFSET_LONG_10.00"],
            "component_points": {"price_action_structure": 21.0},
            "entry_context": {"side": "SHORT"},
            "kline": {"close": 0.25, "timestamp": 1782991800},
        },
        min_score=80.0,
    )
    weak_pa_payload = build_near_miss_payload(
        {
            "timestamp": 1782992705,
            "symbol": "XLMUSDT",
            "action": "WATCH",
            "score": 84.0,
            "reasons": ["SIDE_THRESHOLD_OFFSET_LONG_10.00"],
            "component_points": {"price_action_structure": 17.9},
            "entry_context": {"side": "LONG"},
            "kline": {"close": 0.25, "timestamp": 1782991800},
        },
        min_score=80.0,
    )

    assert short_payload is not None
    assert weak_pa_payload is not None
    assert short_payload.get("targeted_long_offset") is not True
    assert weak_pa_payload.get("targeted_long_offset") is not True
    assert "scout_tags" not in short_payload
    assert "scout_tags" not in weak_pa_payload


def test_build_near_miss_payload_ignores_tradable_or_low_score_decisions():
    assert build_near_miss_payload({"action": "PROBE", "score": 90}, min_score=82.0) is None
    assert build_near_miss_payload({"action": "WATCH", "score": 81.99}, min_score=82.0) is None


def test_scout_micro_open_is_blocked_when_data_health_is_degraded(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    near_miss = {
        "symbol": "XLMUSDT",
        "intended_side": "LONG",
        "entry_price": 0.25,
        "score": 91.0,
    }
    config = EntryChainConfig(scout_micro_symbols=("XLMUSDT",))

    assert (
        should_open_scout_micro(
            symbol="XLMUSDT",
            near_miss=near_miss,
            config=config,
            data_health="DEGRADED",
            scout_paper=ledger,
        )
        is False
    )


def test_scout_micro_open_requires_configured_minimum_score(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    near_miss = {
        "symbol": "XLMUSDT",
        "intended_side": "LONG",
        "entry_price": 0.25,
        "score": 81.99,
    }
    config = EntryChainConfig(scout_micro_symbols=("XLMUSDT",), scout_micro_min_score=82.0)

    assert (
        should_open_scout_micro(
            symbol="XLMUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
        )
        is False
    )


def test_scout_micro_blocks_xlm_rr_gap_mission(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    near_miss = {
        "symbol": "XLMUSDT",
        "intended_side": "SHORT",
        "entry_price": 0.25,
        "score": 91.0,
        "reasons": ["DIRECT_BELOW_RISK_REWARD_GEOMETRY_MINIMUM_GAP_0.5"],
        "component_points": {"risk_reward_geometry": 3.5},
    }
    config = EntryChainConfig(
        scout_micro_symbols=("XLMUSDT",),
        scout_micro_rr_gap_block_symbols=("XLMUSDT",),
        scout_micro_non_rr_min_score=85.0,
    )

    assert (
        should_open_scout_micro(
            symbol="XLMUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
        )
        is False
    )


def test_scout_micro_allows_xlm_non_rr_high_score_mission(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    near_miss = {
        "symbol": "XLMUSDT",
        "intended_side": "SHORT",
        "entry_price": 0.25,
        "score": 86.0,
        "reasons": ["SYMBOL_OBSERVATION_ONLY"],
        "component_points": {
            "risk_reward_geometry": 4.0,
            "fibonacci_location": 18.0,
            "price_action_structure": 21.0,
        },
    }
    config = EntryChainConfig(
        scout_micro_symbols=("XLMUSDT",),
        scout_micro_rr_gap_block_symbols=("XLMUSDT",),
        scout_micro_non_rr_min_score=85.0,
    )

    assert (
        should_open_scout_micro(
            symbol="XLMUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
        )
        is True
    )


def test_scout_micro_allows_targeted_long_offset_mission(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    near_miss = {
        "symbol": "CCUSDT",
        "intended_side": "LONG",
        "entry_price": 1.0,
        "score": 82.0,
        "reasons": ["SIDE_THRESHOLD_OFFSET_LONG_10.00"],
        "component_points": {
            "price_action_structure": 18.0,
            "risk_reward_geometry": 3.0,
        },
        "scout_tags": ["TARGETED_LONG_OFFSET"],
    }
    config = EntryChainConfig(
        scout_micro_symbols=("CCUSDT",),
        scout_micro_targeted_long_symbols=("CCUSDT",),
    )

    assert (
        should_open_scout_micro(
            symbol="CCUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
        )
        is True
    )


def test_scout_micro_allows_targeted_long_offset_for_authorized_mission_pool_symbol(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    near_miss = {
        "symbol": "LINKUSDT",
        "intended_side": "LONG",
        "entry_price": 18.0,
        "score": 86.0,
        "reasons": ["FIB_PA_ARCHITECTURE_WEIGHTS", "SIDE_THRESHOLD_OFFSET_LONG_10.00"],
        "component_points": {
            "price_action_structure": 21.0,
            "risk_reward_geometry": 3.0,
        },
        "scout_tags": ["TARGETED_LONG_OFFSET"],
    }
    config = EntryChainConfig(
        scout_micro_symbols=("LINKUSDT",),
        scout_micro_targeted_long_symbols=("LINKUSDT",),
    )

    assert scout_micro_mission("LINKUSDT", near_miss, config) == "TARGETED_LONG_OFFSET"
    assert (
        should_open_scout_micro(
            symbol="LINKUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
        )
        is True
    )


def test_scout_micro_uses_targeted_long_tag_even_when_reason_list_is_compacted(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    near_miss = {
        "symbol": "LABUSDT",
        "intended_side": "LONG",
        "entry_price": 1.0,
        "score": 86.0,
        "reasons": ["FIB_PA_ARCHITECTURE_WEIGHTS"],
        "component_points": {
            "price_action_structure": 21.0,
            "risk_reward_geometry": 3.0,
        },
        "scout_tags": ["TARGETED_LONG_OFFSET"],
    }
    config = EntryChainConfig(
        scout_micro_symbols=("LABUSDT",),
        scout_micro_targeted_long_symbols=("LABUSDT",),
    )

    assert scout_micro_mission("LABUSDT", near_miss, config) == "TARGETED_LONG_OFFSET"
    assert (
        should_open_scout_micro(
            symbol="LABUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
        )
        is True
    )


def test_scout_micro_rejects_targeted_long_offset_with_low_rr(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    near_miss = {
        "symbol": "CCUSDT",
        "intended_side": "LONG",
        "entry_price": 1.0,
        "score": 84.0,
        "reasons": ["SIDE_THRESHOLD_OFFSET_LONG_10.00"],
        "component_points": {
            "price_action_structure": 21.0,
            "risk_reward_geometry": 2.0,
        },
        "scout_tags": ["TARGETED_LONG_OFFSET"],
    }
    config = EntryChainConfig(
        scout_micro_symbols=("CCUSDT",),
        scout_micro_targeted_long_symbols=("CCUSDT",),
    )

    assert (
        should_open_scout_micro(
            symbol="CCUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
        )
        is False
    )


def test_scout_micro_allows_scout_only_high_score_with_probe_minima(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    near_miss = {
        "symbol": "ZECUSDT",
        "intended_side": "LONG",
        "entry_price": 20.0,
        "score": 89.0,
        "reasons": ["SYMBOL_BLACKLISTED"],
        "component_points": {
            "fibonacci_location": 18.0,
            "price_action_structure": 21.0,
            "risk_reward_geometry": 5.0,
        },
    }
    config = EntryChainConfig(
        scout_micro_symbols=("ZECUSDT",),
        scout_micro_scout_only_symbols=("ZECUSDT",),
    )

    assert (
        should_open_scout_micro(
            symbol="ZECUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
        )
        is True
    )


def test_scout_micro_blocks_same_symbol_same_side_cooldown(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    open_and_stop(ledger, "XLMUSDT", opened_at=1000, stopped_at=1900, side="SHORT")
    near_miss = {
        "symbol": "XLMUSDT",
        "intended_side": "SHORT",
        "entry_price": 0.25,
        "score": 86.0,
        "reasons": ["SYMBOL_OBSERVATION_ONLY"],
    }
    config = EntryChainConfig(
        scout_micro_symbols=("XLMUSDT",),
        scout_micro_non_rr_min_score=85.0,
        scout_micro_same_side_cooldown_hours=2,
        scout_micro_initial_stop_cooldown_hours=0,
    )

    assert (
        should_open_scout_micro(
            symbol="XLMUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
            timestamp=1900 + 3600,
        )
        is False
    )


def test_scout_micro_blocks_symbol_after_initial_stop_cooldown(tmp_path):
    ledger = PaperTradingLedger(tmp_path / "scout_micro")
    open_and_stop(ledger, "XLMUSDT", opened_at=1000, stopped_at=1900, side="SHORT")
    near_miss = {
        "symbol": "XLMUSDT",
        "intended_side": "LONG",
        "entry_price": 0.25,
        "score": 86.0,
        "reasons": ["SYMBOL_OBSERVATION_ONLY"],
    }
    config = EntryChainConfig(
        scout_micro_symbols=("XLMUSDT",),
        scout_micro_non_rr_min_score=85.0,
        scout_micro_same_side_cooldown_hours=0,
        scout_micro_initial_stop_cooldown_hours=6,
    )

    assert (
        should_open_scout_micro(
            symbol="XLMUSDT",
            near_miss=near_miss,
            config=config,
            data_health="OK",
            scout_paper=ledger,
            timestamp=1900 + 3 * 3600,
        )
        is False
    )


def test_build_scout_micro_payloads_uses_fixed_notional_and_leverage():
    near_miss = {
        "timestamp": 1782992705,
        "symbol": "XLMUSDT",
        "score": 91.0,
        "reasons": ["SYMBOL_OBSERVATION_ONLY"],
        "intended_side": "SHORT",
        "entry_price": 0.25,
        "entry_context": {"atr_pct": 0.01, "side": "SHORT"},
    }
    config = EntryChainConfig(
        scout_micro_symbols=("XLMUSDT",),
        scout_micro_notional=50.0,
        scout_micro_leverage=1,
    )

    decision_payload, draft_payload = build_scout_micro_payloads(
        symbol="XLMUSDT",
        near_miss=near_miss,
        price=0.25,
        config=config,
        timestamp=1782992705,
    )

    assert decision_payload["action"] == "PROBE"
    assert decision_payload["side"] == "SHORT"
    assert decision_payload["notional_hint"] == 50.0
    assert decision_payload["leverage"] == 1
    assert "SCOUT_MICRO" in decision_payload["reasons"]
    assert "SCOUT_MISSION_UNCLASSIFIED" in decision_payload["reasons"]
    assert decision_payload["scout_mission"] is None
    assert draft_payload["approved"] is True
    assert draft_payload["request"]["position_side"] == "SHORT"
    assert draft_payload["request"]["quantity"] == 200.0
    assert draft_payload["request"]["price"] == 0.25


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


def test_dry_run_decision_controls_demote_weak_edge_probe_without_positive_history(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    config = EntryChainConfig(
        weak_edge_probe_min_score=77.0,
        weak_edge_probe_max_score=85.0,
    )

    controlled = apply_dry_run_decision_controls(
        probe_decision("SOLUSDT", score=82.0),
        config=config,
        paper=ledger,
        timestamp=5000,
    )

    assert controlled.action == "WATCH"
    assert controlled.side == "NONE"
    assert controlled.risk_allowed is False
    assert "PROBE_WEAK_EDGE_DEMOTED" in controlled.reasons


def test_dry_run_decision_controls_keep_probe_above_weak_edge_band(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    config = EntryChainConfig(
        weak_edge_probe_min_score=77.0,
        weak_edge_probe_max_score=82.0,
    )

    controlled = apply_dry_run_decision_controls(
        probe_decision("SOLUSDT", score=82.1),
        config=config,
        paper=ledger,
        timestamp=5000,
    )

    assert controlled.action == "PROBE"
    assert "PROBE_WEAK_EDGE_DEMOTED" not in controlled.reasons


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


def test_dry_run_decision_controls_apply_single_initial_stop_cooldown(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    open_and_stop(ledger, "LABUSDT", opened_at=1000, stopped_at=1900)
    config = EntryChainConfig(
        post_initial_stop_cooldown_enabled=True,
        post_initial_stop_cooldown_hours=4,
    )

    controlled = apply_dry_run_decision_controls(
        probe_decision("LABUSDT", score=90.0),
        config=config,
        paper=ledger,
        timestamp=1900 + 3 * 3600,
    )

    assert controlled.action == "WATCH"
    assert "SYMBOL_POST_INITIAL_STOP_COOLDOWN" in controlled.reasons


def test_dry_run_decision_controls_allows_symbol_after_single_stop_cooldown_expires(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    open_and_stop(ledger, "LABUSDT", opened_at=1000, stopped_at=1900)
    config = EntryChainConfig(
        post_initial_stop_cooldown_enabled=True,
        post_initial_stop_cooldown_hours=4,
    )

    controlled = apply_dry_run_decision_controls(
        probe_decision("LABUSDT", score=90.0),
        config=config,
        paper=ledger,
        timestamp=1900 + 4 * 3600,
    )

    assert controlled.action == "PROBE"
    assert "SYMBOL_POST_INITIAL_STOP_COOLDOWN" not in controlled.reasons


def test_dry_run_decision_controls_apply_portfolio_consecutive_stop_circuit(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    open_and_stop(ledger, "BNBUSDT", opened_at=1000, stopped_at=1900)
    open_and_stop(ledger, "DOGEUSDT", opened_at=2800, stopped_at=3700)
    open_and_stop(ledger, "LABUSDT", opened_at=4600, stopped_at=5500)
    config = EntryChainConfig(
        portfolio_stop_circuit_enabled=True,
        portfolio_stop_circuit_count=3,
        portfolio_stop_circuit_hours=4,
    )

    controlled = apply_dry_run_decision_controls(
        probe_decision("SOLUSDT", score=90.0),
        config=config,
        paper=ledger,
        timestamp=5500 + 2 * 3600,
    )

    assert controlled.action == "WATCH"
    assert "PORTFOLIO_CONSECUTIVE_INITIAL_STOP_CIRCUIT_BREAKER" in controlled.reasons


def test_dry_run_decision_controls_apply_daily_loss_circuit(tmp_path):
    ledger = PaperTradingLedger(tmp_path)
    open_and_stop(ledger, "LABUSDT", opened_at=1000, stopped_at=1900)
    config = EntryChainConfig(
        portfolio_daily_loss_circuit_enabled=True,
        portfolio_daily_loss_limit=-5.0,
    )

    controlled = apply_dry_run_decision_controls(
        probe_decision("SOLUSDT", score=90.0),
        config=config,
        paper=ledger,
        timestamp=2000,
    )

    assert controlled.action == "WATCH"
    assert "PORTFOLIO_DAILY_LOSS_CIRCUIT_BREAKER" in controlled.reasons


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
