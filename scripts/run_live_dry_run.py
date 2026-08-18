from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from dataclasses import replace
from pathlib import Path
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.execution.live_entry_chain_adapter import build_live_entry_order_draft
from src.backtest.engine import BacktestBar
from src.observability.decision_audit import DecisionAuditWriter
from src.observability.dry_run_summary import DryRunSummary, write_summary
from src.observability.paper_trading import FEE_BPS, SLIPPAGE_BPS, TP_FRACTIONS, TP_LEVELS, PaperExitConfig, PaperTradingLedger, PortfolioStateSnapshot
from src.risk.net_beta_exposure_model import (
    NET_BETA_EXPOSURE_CAP_PCT,
    NET_BETA_EXPOSURE_MODEL_NAME,
    compute_net_beta_exposure,
)
from src.risk.stress_simulator import stress_decision
from src.signals.entry_chain import EntryChainContext, EntryChainDecision, evaluate_entry_chain
from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config
from src.signals.entry_chain_features import (
    atr_pct,
    component_scores,
    direction_from_history,
    extreme_position_ratio,
    long_chase_risk_active,
    long_low_liquidity_session_active,
    long_overextension_active,
    long_upper_wick_risk_active,
    quote_volume,
    risk_reward_geometry_detail,
    wick_anomaly,
)
from src.signals.entry_chain_gates import HIGH_BETA_SYMBOLS
from src.signals.fib_location import detect_fractal_swings


COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
BINANCE_EXCHANGE_INFO_URL = "https://fapi.binance.com/fapi/v1/exchangeInfo"
STABLE_SYMBOLS = {
    "USDT",
    "USDC",
    "USDS",
    "DAI",
    "USD1",
    "USDE",
    "TUSD",
    "FDUSD",
    "PYUSD",
    "BUSD",
    "USDP",
    "FRAX",
}
STABLE_IDS = {
    "tether",
    "usd-coin",
    "usds",
    "dai",
    "usd1-wlfi",
    "ethena-usde",
    "true-usd",
    "first-digital-usd",
    "paypal-usd",
    "binance-usd",
    "paxos-standard",
    "frax",
}
FOUR_QUADRANT_EXPERIMENT_ID = "four_quadrant_navigation_v1"
COINGECKO_BASE_OVERRIDES = {
    "binancecoin": "BNB",
    "the-open-network": "TON",
}


def main() -> None:
    args = parse_args()
    output_dir = resolve_output_dir(args)
    try:
        run(args)
    except Exception:
        write_error(output_dir, traceback.format_exc())
        raise


def run(args: argparse.Namespace) -> None:
    config = load_entry_chain_config(args.config)
    symbols, symbol_meta = resolve_runtime_symbols(args, config)
    warmup_state = warmup_symbols(symbols, args, config) if args.market_data_source == "public-binance" else synthetic_warmup_state(symbols, config)
    orders_submitted = 0
    summary = DryRunSummary(target_tier=args.target_tier, assumptions=dry_run_assumptions(config))
    data_health = "OK"  # 启动默认;每 cycle 重置见 while 循环内(粘滞降级修复 08-13)
    cycle = 0
    output_dir: Path | None = None
    audit: DecisionAuditWriter | None = None
    paper: PaperTradingLedger | None = None
    scout_paper: PaperTradingLedger | None = None
    paper_exit_ab_ledgers: dict[str, PaperTradingLedger] = {}
    quadrant_pending_by_symbol: dict[str, dict[str, Any]] = {}
    quadrant_pending_path: Path | None = None
    startup_ts = int(time.time())
    startup_output_dir = resolve_output_dir(args, timestamp=startup_ts)
    write_runtime_log(
        startup_output_dir,
        render_startup_log(args, startup_ts, symbols, symbol_meta, warmup_state, config.dry_run_warmup_15m_bars),
        timestamp=startup_ts,
    )
    try:
        while True:
            # 周期级 data_health 重置(08-13 修复):一次 Binance 拉取抖动不再
            # 永久置 DEGRADED 锁死 q1_trend_launch(allow_degraded_data=false 时);
            # 降级仍只影响降级发生的当周期,下周期恢复评估。
            data_health = "OK"
            alignment_lines = wait_for_kline_alignment(args)
            cycle += 1
            cycle_started = time.perf_counter()
            now = int(time.time())
            current_output_dir = resolve_output_dir(args, timestamp=now)
            if current_output_dir != output_dir:
                if audit is not None:
                    audit.close()
                output_dir = current_output_dir
                audit = DecisionAuditWriter(output_dir)
                paper_state_dir = resolve_paper_state_dir(args)
                quadrant_pending_path = paper_state_dir / "quadrant_pending.json"
                if config.quadrant_pending_state_enabled:
                    quadrant_pending_by_symbol = load_quadrant_pending_state(quadrant_pending_path)
                paper_mode = effective_paper_exit_mode(config, paper_state_dir)
                paper = PaperTradingLedger(output_dir, state_dir=paper_state_dir, exit_config=paper_exit_config(config, scout=False, mode_override=paper_mode))
                scout_paper = PaperTradingLedger(
                    output_dir / "scout_micro",
                    state_dir=paper_state_dir / "scout_micro",
                    exit_config=paper_exit_config(config, scout=True),
                )
                paper_exit_ab_ledgers = build_paper_exit_ab_ledgers(output_dir, paper_state_dir, config)
            assert output_dir is not None
            assert audit is not None
            assert paper is not None
            assert scout_paper is not None
            runtime_lines = render_cycle_header(
                cycle,
                now,
                args,
                symbols,
                symbol_meta,
                warmup_state,
                config.dry_run_warmup_15m_bars,
                paper,
            )
            runtime_lines.extend(alignment_lines)
            processed = 0
            for symbol in symbols:
                started = time.perf_counter()
                context, context_health, debug = build_context(symbol, now, args, config, warmup_state.get(symbol))
                context = apply_paper_state_to_context(context, paper, now)
                debug["entry_context"] = context_snapshot(context)
                if context_health != "OK":
                    data_health = context_health
                decision = apply_dry_run_decision_controls(
                    evaluate_entry_chain(context, config),
                    config=config,
                    paper=paper,
                    timestamp=now,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                market_snapshot = synthetic_market_snapshot()
                decision_payload = decision.to_dict()
                decision_payload["timestamp"] = now
                decision_payload["symbol"] = symbol
                decision_payload["model_version"] = f"entry-chain-vps-dry-run:{args.target_tier}"
                decision_payload["market_snapshot"] = market_snapshot
                decision_payload["latency_ms"] = latency_ms
                decision_payload["warmup"] = debug.get("warmup", {})
                decision_payload["kline"] = debug.get("kline", {})
                decision_payload["score_detail"] = {
                    "scores": debug.get("scores", {}),
                    "points": decision_payload.get("component_points", {}),
                    "weights": decision_payload.get("weights", {}),
                    "diagnostics": debug.get("score_diagnostics", {}),
                    "total_score": decision_payload.get("score"),
                }
                decision_payload["entry_context"] = debug.get("entry_context", {})
                decision_payload = annotate_quadrant(decision_payload, config)
                near_miss = build_near_miss_payload(
                    decision_payload,
                    min_score=args.near_miss_min_score,
                    # Task A:Q2 pending 候选不被全局 82 截断(08-11 报告管道未对齐修复)
                    min_score_by_quadrant={"Q2": float(config.scout_micro_q2_pending_min_score)},
                )
                kline_timestamp = int(debug.get("kline", {}).get("timestamp") or now)
                if near_miss is not None:
                    confirmed = confirm_q3_to_q1_pending(symbol, near_miss, config, quadrant_pending_by_symbol.get(symbol), kline_timestamp)
                    if confirmed is None:
                        confirmed = confirm_q2_to_q1_pending(symbol, near_miss, config, quadrant_pending_by_symbol.get(symbol), kline_timestamp)
                    if confirmed is not None:
                        near_miss = confirmed
                        quadrant_pending_by_symbol.pop(symbol, None)
                    else:
                        pending = build_q3_pending_candidate(near_miss, config, kline_timestamp)
                        if pending is None:
                            pending = build_q2_pending_candidate(near_miss, config, kline_timestamp)
                        if pending is not None:
                            quadrant_pending_by_symbol[symbol] = pending
                        elif symbol in quadrant_pending_by_symbol and kline_timestamp > int(quadrant_pending_by_symbol[symbol].get("expires_at") or 0):
                            quadrant_pending_by_symbol.pop(symbol, None)
                if near_miss is not None:
                    near_miss = annotate_quadrant(near_miss, config)
                # mirror_ab_mode=shadow_only(08-18 评审):mirror 账本继续记录假设成交(诊断),
                # 但不计入实验熔断统计/敞口——停止实质亏损,保留 reactivation 观察。
                _mirror_ledgers = [] if str(config.mirror_ab_mode).lower() == "shadow_only" else list(paper_exit_ab_ledgers.values())
                experiment_circuit_active = experiment_entry_circuit_active(
                    config=config,
                    timestamp=now,
                    experiment_ledgers=[paper, scout_paper, *_mirror_ledgers],
                    daily_ledgers=[paper, scout_paper],
                )
                entry_near_miss = None if experiment_circuit_active else near_miss
                green_channel_decision = build_q1_green_channel_decision(
                    base_decision=decision,
                    near_miss=entry_near_miss,
                    config=config,
                    data_health=data_health,
                    paper=paper,
                )
                if green_channel_decision is not None:
                    decision = apply_dry_run_decision_controls(
                        green_channel_decision,
                        config=config,
                        paper=paper,
                        timestamp=now,
                    )
                    decision_payload = annotate_quadrant(
                        enrich_decision_payload(
                            decision.to_dict(),
                            symbol=symbol,
                            timestamp=now,
                            target_tier=args.target_tier,
                            market_snapshot=market_snapshot,
                            latency_ms=latency_ms,
                            debug=debug,
                        ),
                        config,
                    )
                decision, decision_payload = apply_experimental_quadrant_entry_rules(
                    decision=decision,
                    decision_payload=decision_payload,
                    paper=paper,
                )
                audit.write_decision(decision_payload)
                summary.record_decision(decision_payload)
                if near_miss is not None:
                    audit.write_near_miss(near_miss)
                    summary.record_near_miss(near_miss)
                stress = stress_decision(
                    exposure_pct=decision.max_symbol_exposure_pct if decision.action in {"PROBE", "DIRECT"} else 0.0,
                    leverage=decision.leverage,
                    adverse_move_pct=args.stress_move_pct,
                    max_loss_pct=args.max_stress_loss_pct,
                )
                stress["symbol"] = symbol
                summary.record_stress(stress)
                price = float(debug.get("kline", {}).get("close") or synthetic_price(symbol))
                draft = build_live_entry_order_draft(
                    decision,
                    event_id=f"dry-run-{symbol}-{now}",
                    trace_id=f"dry-run-{now}",
                    correlation_id=f"dry-run-{symbol}",
                    price=price,
                    timestamp=now,
                    strategy_version="entry-chain-vps-dry-run",
                )
                draft_payload = draft.to_dict()
                draft_payload["stress"] = stress
                audit.write_order_draft(draft_payload)
                for attribution_row in attribution_events(symbol, now, decision_payload, draft_payload, price):
                    audit.write_attribution(attribution_row)
                paper_events = paper.on_decision(
                    symbol=symbol,
                    decision_payload=decision_payload,
                    draft_payload=draft_payload,
                    kline=debug.get("kline", {}),
                    timestamp=int(debug.get("kline", {}).get("timestamp") or now),
                )
                for ab_ledger in paper_exit_ab_ledgers.values():
                    ab_ledger.on_decision(
                        symbol=symbol,
                        decision_payload=decision_payload,
                        draft_payload=draft_payload,
                        kline=debug.get("kline", {}),
                        timestamp=kline_timestamp,
                    )
                mirror_ab_events = update_mirror_ab_ledgers(
                    ab_ledgers=paper_exit_ab_ledgers,
                    symbol=symbol,
                    near_miss=entry_near_miss,
                    config=config,
                    kline=debug.get("kline", {}),
                    timestamp=kline_timestamp,
                )
                scout_events = update_scout_micro_ledger(
                    scout_paper=scout_paper,
                    symbol=symbol,
                    near_miss=entry_near_miss,
                    config=config,
                    data_health=data_health,
                    kline=debug.get("kline", {}),
                    timestamp=kline_timestamp,
                )
                if near_miss is not None:
                    audit.write_scout_decision(
                        build_scout_decision_audit(
                            symbol=symbol,
                            near_miss=near_miss,
                            config=config,
                            data_health=data_health,
                            scout_paper=scout_paper,
                            timestamp=kline_timestamp,
                            experiment_circuit_active=experiment_circuit_active,
                            accepted=bool(scout_events and any(event.startswith("PAPER_OPEN:") for event in scout_events)),
                        )
                    )
                runtime_lines.extend(render_symbol_log(symbol, context, decision_payload, draft_payload, stress, debug))
                runtime_lines.extend(render_paper_log(symbol, paper_events))
                runtime_lines.extend(render_mirror_ab_log(symbol, mirror_ab_events))
                runtime_lines.extend(render_scout_micro_log(symbol, scout_events))
                processed += 1
            elapsed = time.perf_counter() - cycle_started
            cycle_finished_ts = time.time()
            runtime_lines.append(f"本轮扫描完成: processed={processed}/{len(symbols)}, elapsed={elapsed:.2f}s, orders_submitted={orders_submitted}")
            runtime_lines.append(render_schedule_wait_log(args, now, cycle_finished_ts, elapsed))
            write_runtime_log(output_dir, runtime_lines)
            write_health(output_dir, symbols, orders_submitted, data_health, symbol_meta, warmup_state, config.dry_run_warmup_15m_bars)
            summary.record_portfolio_snapshot(portfolio_exposure_snapshot(paper.get_portfolio_state_snapshot(now), config, paper.positions))
            if config.quadrant_pending_state_enabled and quadrant_pending_path is not None:
                write_quadrant_pending_state(quadrant_pending_path, quadrant_pending_by_symbol)
            ab_report = maybe_write_paper_ab_auto_report(
                output_dir=output_dir,
                state_dir=resolve_paper_state_dir(args),
                config=config,
                ab_ledgers=paper_exit_ab_ledgers,
                timestamp=now,
            )
            effective_mode = effective_paper_exit_mode(config, resolve_paper_state_dir(args))
            if paper.exit_config.mode != effective_mode:
                paper.exit_config = paper_exit_config(config, scout=False, mode_override=effective_mode)
            summary.assumptions = {
                **dict(summary.assumptions),
                "effective_paper_exit_mode": paper.exit_config.mode,
                "paper_ab_last_report": {
                    "batch": ab_report.get("batch"),
                    "closed_trade_count": ab_report.get("closed_trade_count"),
                }
                if isinstance(ab_report, Mapping)
                else None,
                "paper_ab_switch_state": load_paper_ab_state(paper_ab_switch_state_path(resolve_paper_state_dir(args))),
            }
            write_summary(output_dir / "summary.json", summary, orders_submitted=orders_submitted, data_health=data_health)
            write_paper_summary_with_ab(output_dir, paper, paper_exit_ab_ledgers, now)
            if args.once:
                break
            if not args.align_to_kline_close:
                time.sleep(args.interval_seconds)
    finally:
        if audit is not None:
            audit.close()
    print(json.dumps({"status": "dry_run_completed", "orders_submitted": orders_submitted}, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI300 entry-chain in dry-run mode without exchange mutation.")
    parser.add_argument("--config", default="configs/entry_chain.dry_run.json")
    parser.add_argument("--output-dir")
    parser.add_argument("--log-root", default="reports/dry_run/local")
    parser.add_argument("--log-date")
    parser.add_argument("--paper-state-dir")
    parser.add_argument("--symbols")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--align-to-kline-close", action="store_true")
    parser.add_argument("--kline-interval-seconds", type=int, default=900)
    parser.add_argument("--post-close-delay-seconds", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--target-tier", default="conservative", choices=["conservative", "balanced", "aggressive"])
    parser.add_argument("--stress-move-pct", type=float, default=0.20)
    parser.add_argument("--max-stress-loss-pct", type=float, default=0.25)
    parser.add_argument("--near-miss-min-score", type=float, default=82.0)
    parser.add_argument("--market-data-source", default="synthetic", choices=["synthetic", "public-binance"])
    parser.add_argument("--public-kline-limit", type=int, default=240)
    return parser.parse_args()


def dry_run_assumptions(config: EntryChainConfig) -> dict[str, Any]:
    return {
        "direct_risk_pct": config.direct_risk_pct,
        "probe_risk_pct": config.probe_risk_pct,
        "max_active_symbols": config.max_active_symbols,
        "max_total_exposure_pct": config.max_total_exposure_pct,
        "max_same_direction_exposure_pct": config.max_same_direction_exposure_pct,
        "max_symbol_trades_per_day": config.max_symbol_trades_per_day,
        "daily_max_trades_base": config.daily_max_trades_base,
        "min_daily_trades": config.min_daily_trades,
        "paper_fee_bps": FEE_BPS,
        "paper_slippage_bps": SLIPPAGE_BPS,
        "paper_tp_levels": list(TP_LEVELS),
        "paper_tp_fractions": list(TP_FRACTIONS),
        "pnl_accounting_mode": "notional_primary_margin_reporting",
        "net_beta_exposure_model": NET_BETA_EXPOSURE_MODEL_NAME,
        "paper_exit_mode": config.paper_exit_mode,
        "paper_exit_trend_trigger_r": config.paper_exit_trend_trigger_r,
        "paper_exit_trailing_r_mult": config.paper_exit_trailing_r_mult,
        "scout_micro_exit_mode": config.scout_micro_exit_mode,
        "scout_micro_exit_trend_trigger_r": config.scout_micro_exit_trend_trigger_r,
        "scout_micro_exit_trailing_r_mult": config.scout_micro_exit_trailing_r_mult,
        "quadrant_thresholds": {
            "trend_ema_min": config.quadrant_trend_ema_min,
            "price_action_min": config.quadrant_price_action_min,
            "flow_cvd_min": config.quadrant_flow_cvd_min,
            "cci_min": config.quadrant_cci_min,
        },
        "scout_micro_q1_rr_gap_enabled": config.scout_micro_q1_rr_gap_enabled,
        "scout_micro_q1_rr_gap_min_score": config.scout_micro_q1_rr_gap_min_score,
        "scout_micro_q1_rr_gap_min_cvd_score": config.scout_micro_q1_rr_gap_min_cvd_score,
        "scout_micro_q3_to_q1_enabled": config.scout_micro_q3_to_q1_enabled,
        "scout_micro_q3_to_q1_min_score": config.scout_micro_q3_to_q1_min_score,
        "scout_micro_q3_to_q1_confirm_bars": config.scout_micro_q3_to_q1_confirm_bars,
        "scout_micro_q2_pending_enabled": config.scout_micro_q2_pending_enabled,
        "scout_micro_q2_pending_min_score": config.scout_micro_q2_pending_min_score,
        "scout_micro_q2_pending_min_pa_score": config.scout_micro_q2_pending_min_pa_score,
        "scout_micro_q2_pending_confirm_bars": config.scout_micro_q2_pending_confirm_bars,
        "scout_micro_q2_pending_confirm_cci_score": config.scout_micro_q2_pending_confirm_cci_score,
        "quadrant_pending_state_enabled": config.quadrant_pending_state_enabled,
        "dry_run_q1_trend_launch_enabled": config.dry_run_q1_trend_launch_enabled,
        "dry_run_q1_trend_launch_min_score": config.dry_run_q1_trend_launch_min_score,
        "dry_run_q1_trend_launch_min_pa_score": config.dry_run_q1_trend_launch_min_pa_score,
        "dry_run_q1_trend_launch_min_fib_score": config.dry_run_q1_trend_launch_min_fib_score,
        "dry_run_q1_trend_launch_min_cvd_score": config.dry_run_q1_trend_launch_min_cvd_score,
        "dry_run_q1_trend_launch_min_rr_score": config.dry_run_q1_trend_launch_min_rr_score,
        "dry_run_q1_trend_launch_base_exposure_pct": config.dry_run_q1_trend_launch_base_exposure_pct,
        "dry_run_q1_trend_launch_exit_mode": config.dry_run_q1_trend_launch_exit_mode,
        "dry_run_q1_trend_launch_allow_degraded_data": config.dry_run_q1_trend_launch_allow_degraded_data,
        "mirror_ab_enabled": config.mirror_ab_enabled,
        "mirror_ab_min_score": config.mirror_ab_min_score,
        "mirror_ab_notional": config.mirror_ab_notional,
        "mirror_ab_allowed_reasons": list(config.mirror_ab_allowed_reasons),
        "mirror_ab_include_q1_watch": config.mirror_ab_include_q1_watch,
        "paper_ab_auto_report_enabled": config.paper_ab_auto_report_enabled,
        "paper_ab_report_closed_trade_interval": config.paper_ab_report_closed_trade_interval,
        "paper_ab_auto_switch_enabled": config.paper_ab_auto_switch_enabled,
        "paper_ab_auto_switch_min_reports": config.paper_ab_auto_switch_min_reports,
        "paper_ab_auto_switch_min_closed_trades": config.paper_ab_auto_switch_min_closed_trades,
        "paper_ab_auto_switch_payoff_mult": config.paper_ab_auto_switch_payoff_mult,
        "dry_run_q1_green_channel_enabled": config.dry_run_q1_green_channel_enabled,
        "dry_run_q1_green_channel_notional_mult": config.dry_run_q1_green_channel_notional_mult,
        "dry_run_q1_green_channel_min_score": config.dry_run_q1_green_channel_min_score,
        "dry_run_q1_green_channel_min_pa_score": config.dry_run_q1_green_channel_min_pa_score,
        "dry_run_q1_green_channel_min_cvd_score": config.dry_run_q1_green_channel_min_cvd_score,
        "dry_run_q1_green_channel_base_exposure_pct": config.dry_run_q1_green_channel_base_exposure_pct,
        "dry_run_q1_green_channel_exit_mode": config.dry_run_q1_green_channel_exit_mode,
        "experiment_war_fund_loss_limit": config.experiment_war_fund_loss_limit,
        "experiment_daily_loss_limit": config.experiment_daily_loss_limit,
        "scout_micro_mission_stop_circuit_enabled": config.scout_micro_mission_stop_circuit_enabled,
        "scout_micro_mission_stop_circuit_count": config.scout_micro_mission_stop_circuit_count,
        "scout_micro_mission_stop_circuit_hours": config.scout_micro_mission_stop_circuit_hours,
        "scout_micro_allow_degraded_data": config.scout_micro_allow_degraded_data,
        "scout_micro_reversal_pivot_enabled": config.scout_micro_reversal_pivot_enabled,
        "scout_micro_reversal_pivot_min_score": config.scout_micro_reversal_pivot_min_score,
        "scout_micro_reversal_pivot_max_cvd_score": config.scout_micro_reversal_pivot_max_cvd_score,
        "scout_micro_reversal_pivot_max_cci_score": config.scout_micro_reversal_pivot_max_cci_score,
        "scout_micro_reversal_pivot_notional": config.scout_micro_reversal_pivot_notional,
    }


def enrich_decision_payload(
    payload: Mapping[str, Any],
    *,
    symbol: str,
    timestamp: int,
    target_tier: str,
    market_snapshot: Mapping[str, Any],
    latency_ms: int,
    debug: Mapping[str, Any],
) -> dict[str, Any]:
    enriched = dict(payload)
    enriched["timestamp"] = timestamp
    enriched["symbol"] = symbol
    enriched["model_version"] = f"entry-chain-vps-dry-run:{target_tier}"
    enriched["market_snapshot"] = dict(market_snapshot)
    enriched["latency_ms"] = latency_ms
    enriched["warmup"] = debug.get("warmup", {})
    enriched["kline"] = debug.get("kline", {})
    enriched["score_detail"] = {
        "scores": debug.get("scores", {}),
        "points": enriched.get("component_points", {}),
        "weights": enriched.get("weights", {}),
        "diagnostics": debug.get("score_diagnostics", {}),
        "total_score": enriched.get("score"),
    }
    enriched["entry_context"] = debug.get("entry_context", {})
    metadata = enriched.get("metadata", {})
    if isinstance(metadata, Mapping):
        for key in ("experiment_id", "entry_channel", "source_quadrant", "exit_mode"):
            if key in metadata:
                enriched[key] = metadata[key]
    return enriched


def paper_exit_config(config: EntryChainConfig, *, scout: bool, mode_override: str | None = None) -> PaperExitConfig:
    if scout:
        return PaperExitConfig(
            mode=config.scout_micro_exit_mode,
            trend_trigger_r=config.scout_micro_exit_trend_trigger_r,
            trailing_r_mult=config.scout_micro_exit_trailing_r_mult,
        )
    return PaperExitConfig(
        mode=mode_override or config.paper_exit_mode,
        trend_trigger_r=config.paper_exit_trend_trigger_r,
        trailing_r_mult=config.paper_exit_trailing_r_mult,
    )


def build_paper_exit_ab_ledgers(output_dir: Path, state_dir: Path, config: EntryChainConfig) -> dict[str, PaperTradingLedger]:
    return {
        "legacy": PaperTradingLedger(
            output_dir / "paper_ab" / "legacy",
            state_dir=state_dir / "paper_ab" / "legacy",
            exit_config=PaperExitConfig(mode="legacy"),
        ),
        "trend_capture": PaperTradingLedger(
            output_dir / "paper_ab" / "trend_capture",
            state_dir=state_dir / "paper_ab" / "trend_capture",
            exit_config=PaperExitConfig(
                mode="trend_capture",
                trend_trigger_r=config.mirror_ab_payoff_trend_trigger_r if config.mirror_ab_payoff_pilot_enabled else config.paper_exit_trend_trigger_r,
                trailing_r_mult=config.paper_exit_trailing_r_mult,
                early_breakeven_enabled=config.mirror_ab_payoff_pilot_enabled,
                early_breakeven_trigger_r=config.mirror_ab_payoff_early_breakeven_trigger_r,
            ),
        ),
    }


def paper_ab_state_dir(state_dir: Path) -> Path:
    return state_dir / "paper_ab"


def paper_ab_report_state_path(state_dir: Path) -> Path:
    return paper_ab_state_dir(state_dir) / "ab_report_state.json"


def paper_ab_switch_state_path(state_dir: Path) -> Path:
    return paper_ab_state_dir(state_dir) / "ab_switch_state.json"


def load_paper_ab_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_paper_ab_state(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def effective_paper_exit_mode(config: EntryChainConfig, state_dir: Path) -> str:
    state = load_paper_ab_state(paper_ab_switch_state_path(state_dir))
    override = str(state.get("paper_exit_mode_override") or "").strip().lower()
    if config.paper_ab_auto_switch_enabled and override == "trend_capture":
        return "trend_capture"
    return config.paper_exit_mode


def paper_exit_ab_summary(ab_ledgers: Mapping[str, PaperTradingLedger], timestamp: int) -> dict[str, Any]:
    return {name: ledger.summary(timestamp) for name, ledger in sorted(ab_ledgers.items())}


def paper_ab_closed_stats(ledger: PaperTradingLedger) -> dict[str, Any]:
    closed = [row for row in ledger.trade_events() if row.get("event") == "PAPER_CLOSE"]
    pnls = [float(row.get("position_margin_realized_pnl") or row.get("position_realized_pnl") or row.get("net_pnl") or 0.0) for row in closed]
    wins = [item for item in pnls if item > 0.0]
    losses = [item for item in pnls if item < 0.0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    avg_win = gross_profit / len(wins) if wins else 0.0
    avg_loss = gross_loss / len(losses) if losses else 0.0
    return {
        "closed_trades": len(pnls),
        "realized_margin_pnl": sum(pnls),
        "win_rate": len(wins) / len(pnls) if pnls else 0.0,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "actual_payoff_ratio": avg_win / avg_loss if avg_loss > 0.0 else (avg_win if avg_win > 0.0 else 0.0),
        "profit_factor": gross_profit / gross_loss if gross_loss > 0.0 else (gross_profit if gross_profit > 0.0 else 0.0),
    }


def maybe_write_paper_ab_auto_report(
    *,
    output_dir: Path,
    state_dir: Path,
    config: EntryChainConfig,
    ab_ledgers: Mapping[str, PaperTradingLedger],
    timestamp: int,
) -> dict[str, Any] | None:
    if not config.paper_ab_auto_report_enabled:
        return None
    if "legacy" not in ab_ledgers or "trend_capture" not in ab_ledgers:
        return None
    interval = max(1, int(config.paper_ab_report_closed_trade_interval))
    stats = {name: paper_ab_closed_stats(ledger) for name, ledger in sorted(ab_ledgers.items())}
    closed_count = min(int(item["closed_trades"]) for item in stats.values())
    batch = closed_count // interval
    report_state_path = paper_ab_report_state_path(state_dir)
    report_state = load_paper_ab_state(report_state_path)
    last_batch = int(report_state.get("last_report_batch") or 0)
    if batch <= 0 or batch <= last_batch:
        return None

    report = {
        "timestamp": timestamp,
        "batch": batch,
        "closed_trade_interval": interval,
        "closed_trade_count": closed_count,
        "ledgers": stats,
        "assumptions": {
            "auto_report_enabled": config.paper_ab_auto_report_enabled,
            "auto_switch_enabled": config.paper_ab_auto_switch_enabled,
            "auto_switch_min_reports": config.paper_ab_auto_switch_min_reports,
            "auto_switch_min_closed_trades": config.paper_ab_auto_switch_min_closed_trades,
            "auto_switch_payoff_mult": config.paper_ab_auto_switch_payoff_mult,
        },
    }
    trend = stats["trend_capture"]
    legacy = stats["legacy"]
    qualifies = _paper_ab_trend_capture_qualifies(trend, legacy, config)
    report_state["last_report_batch"] = batch
    report_state["report_count"] = int(report_state.get("report_count") or 0) + 1
    report_state["qualifying_streak"] = int(report_state.get("qualifying_streak") or 0) + 1 if qualifies else 0
    report_state["last_report"] = {
        "timestamp": timestamp,
        "batch": batch,
        "closed_trade_count": closed_count,
        "trend_capture_qualified": qualifies,
    }
    switch_payload = maybe_update_paper_ab_auto_switch(
        state_dir=state_dir,
        config=config,
        report_state=report_state,
        report=report,
        timestamp=timestamp,
    )
    if switch_payload:
        report["auto_switch"] = switch_payload
    write_paper_ab_state(report_state_path, report_state)
    report_dir = output_dir / "paper_ab" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = f"ab_report_batch_{batch:04d}"
    (report_dir / f"{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (report_dir / f"{stem}.md").write_text(render_paper_ab_report_markdown(report), encoding="utf-8")
    return report


def maybe_update_paper_ab_auto_switch(
    *,
    state_dir: Path,
    config: EntryChainConfig,
    report_state: Mapping[str, Any],
    report: Mapping[str, Any],
    timestamp: int,
) -> dict[str, Any] | None:
    if not config.paper_ab_auto_switch_enabled:
        return None
    closed_trade_count = int(report.get("closed_trade_count") or 0)
    if closed_trade_count < int(config.paper_ab_auto_switch_min_closed_trades):
        return None
    if int(report_state.get("qualifying_streak") or 0) < int(config.paper_ab_auto_switch_min_reports):
        return None
    switch_path = paper_ab_switch_state_path(state_dir)
    switch_state = load_paper_ab_state(switch_path)
    if str(switch_state.get("paper_exit_mode_override") or "").lower() == "trend_capture":
        return switch_state
    switch_state = {
        "paper_exit_mode_override": "trend_capture",
        "triggered_at": timestamp,
        "trigger_report_batch": report.get("batch"),
        "trigger_closed_trade_count": closed_trade_count,
        "trigger_reason": "trend_capture_payoff_ratio_advantage",
        "auto_switch_min_reports": config.paper_ab_auto_switch_min_reports,
        "auto_switch_payoff_mult": config.paper_ab_auto_switch_payoff_mult,
    }
    write_paper_ab_state(switch_path, switch_state)
    return switch_state


def _paper_ab_trend_capture_qualifies(
    trend: Mapping[str, Any],
    legacy: Mapping[str, Any],
    config: EntryChainConfig,
) -> bool:
    trend_payoff = float(trend.get("actual_payoff_ratio") or 0.0)
    legacy_payoff = float(legacy.get("actual_payoff_ratio") or 0.0)
    if trend_payoff <= 0.0:
        return False
    if legacy_payoff <= 0.0:
        return True
    return trend_payoff >= legacy_payoff * float(config.paper_ab_auto_switch_payoff_mult)


def render_paper_ab_report_markdown(report: Mapping[str, Any]) -> str:
    ledgers = report.get("ledgers", {})
    lines = [
        "# Paper Exit A/B Auto Report",
        "",
        f"- batch: {report.get('batch')}",
        f"- closed_trade_count: {report.get('closed_trade_count')}",
        "",
        "| ledger | closed_trades | pnl | win_rate | payoff_ratio | profit_factor |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    if isinstance(ledgers, Mapping):
        for name, stats in sorted(ledgers.items()):
            if not isinstance(stats, Mapping):
                continue
            lines.append(
                "| "
                f"{name} | {stats.get('closed_trades')} | {float(stats.get('realized_margin_pnl') or 0.0):.4f} | "
                f"{float(stats.get('win_rate') or 0.0):.4f} | {float(stats.get('actual_payoff_ratio') or 0.0):.4f} | "
                f"{float(stats.get('profit_factor') or 0.0):.4f} |"
            )
    if report.get("auto_switch"):
        lines.extend(["", "## Auto Switch", "", "triggered: true"])
    return "\n".join(lines) + "\n"


def write_paper_summary_with_ab(
    output_dir: Path,
    paper: PaperTradingLedger,
    ab_ledgers: Mapping[str, PaperTradingLedger],
    timestamp: int,
) -> None:
    payload = paper.summary(timestamp)
    payload["ab_ledger"] = paper_exit_ab_summary(ab_ledgers, timestamp)
    (output_dir / "paper_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def portfolio_exposure_snapshot(
    snapshot: PortfolioStateSnapshot,
    config: EntryChainConfig,
    positions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    net_side_exposure_pct = snapshot.same_direction_long_pct - snapshot.same_direction_short_pct
    net_beta_exposure_pct = compute_net_beta_exposure(positions or {})
    return {
        "active_symbols": sorted(snapshot.active_symbols),
        "open_position_count": snapshot.open_position_count,
        "total_exposure_pct": snapshot.total_exposure_pct,
        "same_direction_long_pct": snapshot.same_direction_long_pct,
        "same_direction_short_pct": snapshot.same_direction_short_pct,
        "net_side_exposure_pct": net_side_exposure_pct,
        "max_total_exposure_pct": config.max_total_exposure_pct,
        "max_same_direction_exposure_pct": config.max_same_direction_exposure_pct,
        "portfolio_trades_today": snapshot.portfolio_trades_today,
        "daily_profit_pct": snapshot.daily_profit_pct,
        "symbol_exposure_pct": dict(sorted(snapshot.symbol_exposure_pct.items())),
        "net_beta_exposure_pct": net_beta_exposure_pct,
        "net_beta_exposure_cap_pct": NET_BETA_EXPOSURE_CAP_PCT,
        "net_beta_exposure_model": NET_BETA_EXPOSURE_MODEL_NAME,
    }


def build_near_miss_payload(
    decision_payload: Mapping[str, Any],
    *,
    min_score: float,
    min_score_by_quadrant: Mapping[str, float] | None = None,
) -> dict[str, Any] | None:
    action = str(decision_payload.get("action") or "").upper()
    if action in {"PROBE", "DIRECT"}:
        return None
    score = float(decision_payload.get("score") or 0.0)
    reasons = decision_payload.get("reasons", [])
    reason_list = [str(item) for item in reasons] if isinstance(reasons, list) else [str(reasons)]
    primary_reason = next((item for item in reason_list if item != "FIB_PA_ARCHITECTURE_WEIGHTS"), reason_list[0] if reason_list else "")
    kline = decision_payload.get("kline", {}) if isinstance(decision_payload.get("kline"), Mapping) else {}
    entry_context = decision_payload.get("entry_context", {}) if isinstance(decision_payload.get("entry_context"), Mapping) else {}
    score_detail = decision_payload.get("score_detail", {}) if isinstance(decision_payload.get("score_detail"), Mapping) else {}
    component_points = decision_payload.get("component_points", {})
    diagnostics = score_detail.get("diagnostics", {}) if isinstance(score_detail, Mapping) else {}
    payload = {
        "timestamp": decision_payload.get("timestamp"),
        "symbol": decision_payload.get("symbol"),
        "action": action,
        "score": score,
        "reasons": reason_list,
        "primary_reason": primary_reason,
        "scout_candidate": True,
        "intended_side": str(entry_context.get("side") or decision_payload.get("side") or "NONE").upper(),
        "entry_price": kline.get("close"),
        "kline_timestamp": kline.get("timestamp"),
        "component_points": dict(component_points) if isinstance(component_points, Mapping) else {},
        "diagnostics": dict(diagnostics) if isinstance(diagnostics, Mapping) else {},
        "entry_context": dict(entry_context),
    }
    if _is_targeted_long_offset_near_miss(payload):
        payload["targeted_long_offset"] = True
        payload["scout_tags"] = ["TARGETED_LONG_OFFSET"]
    else:
        # per-quadrant 采样覆盖(Task A 修复):Q2/Q3 等象限特定 mission 的候选
        # 不被全局 near_miss_min_score 截断;其余象限用全局门槛。
        quadrant = str(decision_payload.get("quadrant") or "").upper()
        effective_min = float((min_score_by_quadrant or {}).get(quadrant, min_score))
        if score < effective_min:
            return None
    return payload


def build_q1_green_channel_decision(
    *,
    base_decision: EntryChainDecision,
    near_miss: Mapping[str, Any] | None,
    config: EntryChainConfig,
    data_health: str,
    paper: PaperTradingLedger,
) -> EntryChainDecision | None:
    if not _q1_trend_launch_eligible(near_miss, config, data_health):
        return None
    assert near_miss is not None
    side = str(near_miss.get("intended_side") or "").upper()
    rr_points = _component_point(near_miss, "risk_reward_geometry")
    rr_factor = max(0.25, min(1.0, rr_points / 8.0))
    exposure_pct = float(config.dry_run_q1_trend_launch_base_exposure_pct) * rr_factor
    notional = round(max(0.0, paper.initial_equity * exposure_pct), 4)
    reasons = tuple(
        dict.fromkeys(
            [
                *base_decision.reasons,
                "DRY_RUN_Q1_TREND_LAUNCH",
                f"EXPERIMENT_{FOUR_QUADRANT_EXPERIMENT_ID}",
                *[str(item) for item in near_miss.get("reasons", [])],
            ]
        )
    )
    metadata = dict(base_decision.metadata)
    metadata.update(
        {
            "symbol": str(near_miss.get("symbol") or metadata.get("symbol") or "").strip().upper(),
            "experiment_id": FOUR_QUADRANT_EXPERIMENT_ID,
            "entry_channel": "q1_trend_launch",
            "source_quadrant": "Q1",
            "exit_mode": config.dry_run_q1_trend_launch_exit_mode,
            "q1_trend_launch_rr_factor": rr_factor,
            "q1_trend_launch_source": near_miss.get("q2_pending_source") or near_miss.get("q3_pending_source"),
        }
    )
    return replace(
        base_decision,
        action="PROBE",
        side=side,
        reasons=reasons,
        risk_allowed=True,
        leverage=1,
        notional_hint=notional,
        max_symbol_exposure_pct=exposure_pct,
        metadata=metadata,
    )


def _q1_green_channel_eligible(
    near_miss: Mapping[str, Any] | None,
    config: EntryChainConfig,
    data_health: str,
) -> bool:
    # 说明:green channel 与 trend-launch 为同一通道的两套命名(08-02 报告将两者合并)。
    # 实现无条件委托 _q1_trend_launch_eligible,实际门槛/仓位全部取自
    # dry_run_q1_trend_launch_* 字段;dry_run_q1_green_channel_* 字段为兼容保留(死配置),
    # 调整它们不产生任何效果——若要独立配置 green channel 需先接线独立逻辑。
    return _q1_trend_launch_eligible(near_miss, config, data_health)


def _q1_trend_launch_eligible(
    near_miss: Mapping[str, Any] | None,
    config: EntryChainConfig,
    data_health: str,
) -> bool:
    if not config.dry_run_q1_trend_launch_enabled:
        return False
    if near_miss is None:
        return False
    if str(data_health).upper() != "OK" and not config.dry_run_q1_trend_launch_allow_degraded_data:
        return False
    symbol = str(near_miss.get("symbol") or "").strip().upper()
    if not symbol or symbol in config.blacklist_symbols:
        return False
    if decision_quadrant(near_miss, config) != "Q1":
        return False
    if str(near_miss.get("intended_side") or "").upper() not in {"LONG", "SHORT"}:
        return False
    if float(near_miss.get("entry_price") or 0.0) <= 0.0:
        return False
    side = str(near_miss.get("intended_side") or "").upper()
    # 非极值追单检查(08-02 报告 Task A 量化定义: close 不在近8根极值区间最外20%)
    # 极值位置比例由 build_context 基于近 8 根 15m K 线计算, 经 entry_context 传入
    entry_ctx = near_miss.get("entry_context")
    entry_ctx = dict(entry_ctx) if isinstance(entry_ctx, Mapping) else {}
    raw_extreme = entry_ctx.get("extreme_position_ratio")
    # 保留合法测量值 0.0(close 恰为窗口最低价时会被极值下限检查拒绝);
    # 仅当字段缺失/为 None/非数值(防御 'abc' 等脏数据)时才回退中性值 0.5。
    try:
        extreme_ratio = float(raw_extreme) if raw_extreme is not None else 0.5
    except (TypeError, ValueError):
        extreme_ratio = 0.5
    if not (
        float(config.dry_run_q1_trend_launch_extreme_ratio_min)
        <= extreme_ratio
        <= float(config.dry_run_q1_trend_launch_extreme_ratio_max)
    ):
        return False
    # LONG 方向防反转/追单(复用已有 entry_context 标志; SHORT 方向由通用极值检查覆盖)
    if side == "LONG" and (
        entry_ctx.get("long_overextension_active")
        or entry_ctx.get("long_upper_wick_risk_active")
        or entry_ctx.get("long_chase_risk_active")
    ):
        return False
    return (
        float(near_miss.get("score") or 0.0) >= float(config.dry_run_q1_trend_launch_min_score)
        and _component_point(near_miss, "price_action_structure") >= float(config.dry_run_q1_trend_launch_min_pa_score)
        and _component_point(near_miss, "fibonacci_location") >= float(config.dry_run_q1_trend_launch_min_fib_score)
        and _component_point(near_miss, "flow_cvd_confirmation") >= float(config.dry_run_q1_trend_launch_min_cvd_score)
        and _component_point(near_miss, "risk_reward_geometry") >= float(config.dry_run_q1_trend_launch_min_rr_score)
    )


def apply_experimental_quadrant_entry_rules(
    *,
    decision: EntryChainDecision,
    decision_payload: Mapping[str, Any],
    paper: PaperTradingLedger,
) -> tuple[EntryChainDecision, dict[str, Any]]:
    payload = dict(decision_payload)
    if decision.action not in {"PROBE", "DIRECT"}:
        return decision, payload
    symbol = str(payload.get("symbol") or decision.metadata.get("symbol") or "").strip().upper()
    position = paper.positions.get(symbol)
    quadrant = str(payload.get("quadrant") or "").upper()
    if position is None or not position.experiment_id or quadrant not in {"Q2", "Q3"}:
        return decision, payload
    reasons = list(dict.fromkeys([*decision.reasons, "Q2_Q3_EXPERIMENT_ADD_BLOCK"]))
    metadata = dict(decision.metadata)
    metadata["q2_q3_add_blocked"] = True
    blocked = replace(
        decision,
        action="WATCH",
        reasons=tuple(reasons),
        risk_allowed=False,
        leverage=0,
        max_symbol_exposure_pct=0.0,
        notional_hint=0.0,
        metadata=metadata,
    )
    payload.update(
        {
            "action": "WATCH",
            "risk_allowed": False,
            "leverage": 0,
            "max_symbol_exposure_pct": 0.0,
            "notional_hint": 0.0,
            "reasons": reasons,
            "q2_q3_experiment_add_blocked": True,
        }
    )
    return blocked, payload


def _is_targeted_long_offset_near_miss(payload: Mapping[str, Any]) -> bool:
    reasons = payload.get("reasons", [])
    reason_list = [str(item) for item in reasons] if isinstance(reasons, list) else [str(reasons)]
    component_points = payload.get("component_points", {})
    pa_score = 0.0
    if isinstance(component_points, Mapping):
        pa_score = float(component_points.get("price_action_structure") or 0.0)
    return (
        "SIDE_THRESHOLD_OFFSET_LONG_10.00" in reason_list
        and str(payload.get("intended_side") or "").upper() == "LONG"
        and float(payload.get("score") or 0.0) >= 80.0
        and pa_score >= 18.0
    )


def should_open_scout_micro(
    *,
    symbol: str,
    near_miss: Mapping[str, Any] | None,
    config: EntryChainConfig,
    data_health: str,
    scout_paper: PaperTradingLedger,
    timestamp: int | None = None,
) -> bool:
    return (
        scout_micro_open_reject_reason(
            symbol=symbol,
            near_miss=near_miss,
            config=config,
            data_health=data_health,
            scout_paper=scout_paper,
            timestamp=timestamp,
        )
        is None
    )


def scout_micro_open_reject_reason(
    *,
    symbol: str,
    near_miss: Mapping[str, Any] | None,
    config: EntryChainConfig,
    data_health: str,
    scout_paper: PaperTradingLedger,
    timestamp: int | None = None,
) -> str | None:
    normalized_symbol = symbol.strip().upper()
    if normalized_symbol not in config.scout_micro_symbols:
        return "SCOUT_SYMBOL_NOT_ENABLED"
    if str(data_health).upper() != "OK" and not config.scout_micro_allow_degraded_data:
        return "SCOUT_DATA_HEALTH_DEGRADED"
    if normalized_symbol in scout_paper.positions:
        return "SCOUT_POSITION_ALREADY_OPEN"
    if near_miss is None:
        return "SCOUT_NO_NEAR_MISS"
    if str(near_miss.get("symbol") or "").strip().upper() != normalized_symbol:
        return "SCOUT_SYMBOL_MISMATCH"
    mission = scout_micro_mission(normalized_symbol, near_miss, config)
    if mission is None:
        return "SCOUT_NO_MISSION"
    if mission != "REVERSAL_PIVOT_SCOUT" and float(near_miss.get("score") or 0.0) < float(config.scout_micro_min_score):
        return "SCOUT_BELOW_MIN_SCORE"
    side = scout_micro_entry_side(near_miss, mission)
    if side not in {"LONG", "SHORT"}:
        return "SCOUT_INVALID_SIDE"
    if float(near_miss.get("entry_price") or 0.0) <= 0.0:
        return "SCOUT_INVALID_ENTRY_PRICE"
    mission_reason = _scout_micro_mission_stop_cooldown_reason(mission, config, scout_paper, timestamp)
    if mission_reason is not None:
        return mission_reason
    return _scout_micro_cooldown_reason(normalized_symbol, side, config, scout_paper, timestamp)


def build_scout_decision_audit(
    *,
    symbol: str,
    near_miss: Mapping[str, Any],
    config: EntryChainConfig,
    data_health: str,
    scout_paper: PaperTradingLedger,
    timestamp: int,
    experiment_circuit_active: bool,
    accepted: bool,
) -> dict[str, Any]:
    normalized_symbol = symbol.strip().upper()
    mission = scout_micro_mission(normalized_symbol, near_miss, config)
    if experiment_circuit_active:
        reject_reason = "EXPERIMENT_ENTRY_CIRCUIT_ACTIVE"
    else:
        reject_reason = scout_micro_open_reject_reason(
            symbol=normalized_symbol,
            near_miss=near_miss,
            config=config,
            data_health=data_health,
            scout_paper=scout_paper,
            timestamp=timestamp,
        )
    side = scout_micro_entry_side(near_miss, mission)
    return {
        "timestamp": timestamp,
        "symbol": normalized_symbol,
        "candidate": True,
        "accepted": bool(accepted),
        "mission": mission,
        "side": side,
        "source_side": str(near_miss.get("intended_side") or "").upper(),
        "reject_reason": None if accepted else reject_reason,
        "score": float(near_miss.get("score") or 0.0),
        "primary_reason": near_miss.get("primary_reason"),
        "quadrant": str(near_miss.get("quadrant") or decision_quadrant(near_miss, config)),
        "budget_state": {
            "experiment_circuit_active": bool(experiment_circuit_active),
        },
        "mission_stop_circuit_state": {
            "enabled": config.scout_micro_mission_stop_circuit_enabled,
            "reject_reason": _scout_micro_mission_stop_cooldown_reason(mission, config, scout_paper, timestamp) if mission else None,
        },
        "cooldown_state": {
            "reject_reason": _scout_micro_cooldown_reason(normalized_symbol, side, config, scout_paper, timestamp)
            if side in {"LONG", "SHORT"}
            else None,
        },
        "position_conflict_state": {
            "symbol_open": normalized_symbol in scout_paper.positions,
        },
        "war_fund_state": {
            "limit": config.experiment_war_fund_loss_limit,
        },
    }


def scout_micro_mission(symbol: str, near_miss: Mapping[str, Any], config: EntryChainConfig) -> str | None:
    normalized_symbol = symbol.strip().upper()
    if _reversal_pivot_scout_eligible(near_miss, config):
        return "REVERSAL_PIVOT_SCOUT"
    if _q2_pending_momentum_eligible(near_miss, config):
        return "Q2_PENDING_MOMENTUM"
    if _q3_to_q1_confirmation_eligible(near_miss, config):
        return "Q3_TO_Q1_CONFIRMATION"
    if _q1_rr_gap_scout_eligible(near_miss, config):
        return "Q1_RR_GAP_SCOUT"
    if _high_score_long_offset_probe_eligible(normalized_symbol, near_miss, config):
        return "HIGH_SCORE_LONG_OFFSET_PROBE"
    if _fib_continuation_scout_eligible(near_miss, config):
        return "FIB_CONTINUATION_SCOUT"
    if _watch_only_symbol_promotion_eligible(normalized_symbol, near_miss, config):
        return "WATCH_ONLY_SYMBOL_PROMOTION_TEST"
    if _scout_only_high_score_eligible(normalized_symbol, near_miss, config):
        return "SCOUT_ONLY_HIGH_SCORE"
    if normalized_symbol in config.scout_micro_rr_gap_block_symbols and _has_rr_gap_reason(near_miss):
        return None
    return None


def scout_micro_entry_side(near_miss: Mapping[str, Any], mission: str | None) -> str:
    side = str(near_miss.get("intended_side") or "").upper()
    if mission == "REVERSAL_PIVOT_SCOUT":
        if side == "LONG":
            return "SHORT"
        if side == "SHORT":
            return "LONG"
    return side


def _reversal_pivot_scout_eligible(near_miss: Mapping[str, Any], config: EntryChainConfig) -> bool:
    if not config.scout_micro_reversal_pivot_enabled:
        return False
    side = str(near_miss.get("intended_side") or "").upper()
    if side not in {"LONG", "SHORT"}:
        return False
    if float(near_miss.get("score") or 0.0) < float(config.scout_micro_reversal_pivot_min_score):
        return False
    if decision_quadrant(near_miss, config) not in {"Q1", "Q2", "Q3"}:
        return False
    if not _has_exhaustion_or_opposition_warning(near_miss):
        return False
    return (
        _component_point(near_miss, "flow_cvd_confirmation") <= float(config.scout_micro_reversal_pivot_max_cvd_score)
        or _component_point(near_miss, "cci_momentum_quality") <= float(config.scout_micro_reversal_pivot_max_cci_score)
    )


def _has_exhaustion_or_opposition_warning(near_miss: Mapping[str, Any]) -> bool:
    if "FIB_EXTENSION_EXHAUSTION_BLOCK" in _near_miss_reasons(near_miss):
        return True
    diagnostics = near_miss.get("diagnostics", {})
    if not isinstance(diagnostics, Mapping):
        return False
    rr = diagnostics.get("risk_reward_geometry", {})
    if not isinstance(rr, Mapping):
        return False
    return str(rr.get("rr_zero_reason") or "").upper() == "OPPOSITION_STRUCTURE_TOO_CLOSE"


def _high_score_long_offset_probe_eligible(symbol: str, near_miss: Mapping[str, Any], config: EntryChainConfig) -> bool:
    if symbol not in config.scout_micro_targeted_long_symbols:
        return False
    if decision_quadrant(near_miss, config) not in (config.scout_micro_high_score_long_offset_quadrants or ("Q1",)):
        return False
    if str(near_miss.get("intended_side") or "").upper() != "LONG":
        return False
    reasons = _near_miss_reasons(near_miss)
    tags = near_miss.get("scout_tags", [])
    tag_list = [str(item) for item in tags] if isinstance(tags, list) else [str(tags)]
    if "SIDE_THRESHOLD_OFFSET_LONG_10.00" not in reasons and "TARGETED_LONG_OFFSET" not in tag_list:
        return False
    return (
        float(near_miss.get("score") or 0.0) >= float(config.scout_micro_high_score_long_offset_min_score)
        and _component_point(near_miss, "price_action_structure") >= float(config.scout_micro_high_score_long_offset_min_pa_score)
        and _component_point(near_miss, "fibonacci_location") >= float(config.scout_micro_high_score_long_offset_min_fib_score)
        and _component_point(near_miss, "flow_cvd_confirmation") >= float(config.scout_micro_high_score_long_offset_min_cvd_score)
        and _component_point(near_miss, "risk_reward_geometry") >= float(config.scout_micro_high_score_long_offset_min_rr_score)
    )


def _fib_continuation_scout_eligible(near_miss: Mapping[str, Any], config: EntryChainConfig) -> bool:
    if "FIB_EXTENSION_EXHAUSTION_BLOCK" not in _near_miss_reasons(near_miss):
        return False
    if str(near_miss.get("intended_side") or "").upper() not in {"LONG", "SHORT"}:
        return False
    return (
        float(near_miss.get("score") or 0.0) >= float(config.scout_micro_fib_continuation_min_score)
        and _component_point(near_miss, "trend_ema_context") >= float(config.scout_micro_fib_continuation_min_ema_score)
        and _component_point(near_miss, "flow_cvd_confirmation") >= float(config.scout_micro_fib_continuation_min_cvd_score)
        and _component_point(near_miss, "price_action_structure") >= float(config.scout_micro_fib_continuation_min_pa_score)
    )


def _watch_only_symbol_promotion_eligible(symbol: str, near_miss: Mapping[str, Any], config: EntryChainConfig) -> bool:
    if symbol not in config.watch_only_symbols:
        return False
    if "SYMBOL_WATCH_ONLY" not in _near_miss_reasons(near_miss):
        return False
    if float(near_miss.get("score") or 0.0) < float(config.scout_micro_watch_only_promotion_min_score):
        return False
    probe_conditions = config.probe_conditions if isinstance(config.probe_conditions, Mapping) else {}
    return (
        _component_point(near_miss, "fibonacci_location") >= float(probe_conditions.get("min_fib_score", config.scout_micro_scout_only_min_fib_score))
        and _component_point(near_miss, "price_action_structure") >= float(probe_conditions.get("min_pa_score", config.scout_micro_scout_only_min_pa_score))
        and _component_point(near_miss, "risk_reward_geometry") >= float(probe_conditions.get("min_rr_score", config.scout_micro_scout_only_min_rr_score))
    )


def _scout_only_high_score_eligible(symbol: str, near_miss: Mapping[str, Any], config: EntryChainConfig) -> bool:
    if symbol not in config.scout_micro_scout_only_symbols:
        return False
    return (
        float(near_miss.get("score") or 0.0) >= float(config.scout_micro_scout_only_min_score)
        and _component_point(near_miss, "fibonacci_location") >= float(config.scout_micro_scout_only_min_fib_score)
        and _component_point(near_miss, "price_action_structure") >= float(config.scout_micro_scout_only_min_pa_score)
        and _component_point(near_miss, "risk_reward_geometry") >= float(config.scout_micro_scout_only_min_rr_score)
    )


def _scout_micro_cooldown_reason(
    symbol: str,
    side: str,
    config: EntryChainConfig,
    scout_paper: PaperTradingLedger,
    timestamp: int | None,
) -> str | None:
    if timestamp is None:
        return None
    initial_stop_hours = int(config.scout_micro_initial_stop_cooldown_hours)
    if initial_stop_hours > 0:
        since_ts = int(timestamp) - initial_stop_hours * 3600
        if scout_paper.recent_closed_trades(symbol, reason="INITIAL_STOP_HIT", since_ts=since_ts, until_ts=int(timestamp)):
            return "SCOUT_MICRO_INITIAL_STOP_COOLDOWN"
    same_side_hours = int(config.scout_micro_same_side_cooldown_hours)
    if same_side_hours > 0:
        since_ts = int(timestamp) - same_side_hours * 3600
        for row in scout_paper.recent_closed_trades(symbol, since_ts=since_ts, until_ts=int(timestamp)):
            if str(row.get("side") or "").upper() == side:
                return "SCOUT_MICRO_SAME_SIDE_COOLDOWN"
    return None


def _scout_micro_mission_stop_cooldown_reason(
    mission: str,
    config: EntryChainConfig,
    scout_paper: PaperTradingLedger,
    timestamp: int | None,
) -> str | None:
    if not config.scout_micro_mission_stop_circuit_enabled or timestamp is None:
        return None
    required = max(1, int(config.scout_micro_mission_stop_circuit_count))
    since_ts = int(timestamp) - max(1, int(config.scout_micro_mission_stop_circuit_hours)) * 3600
    rows = [
        row
        for row in scout_paper.recent_closed_trades_all(since_ts=since_ts, until_ts=int(timestamp))
        if str(row.get("scout_mission") or "") == mission
    ]
    rows.sort(key=lambda row: int(row.get("timestamp") or 0), reverse=True)
    recent = rows[:required]
    if len(recent) < required:
        return None
    if all(row.get("reason") == "INITIAL_STOP_HIT" for row in recent):
        return f"SCOUT_MICRO_MISSION_INITIAL_STOP_CIRCUIT_{mission}"
    return None


def _has_rr_gap_reason(near_miss: Mapping[str, Any]) -> bool:
    return any("_BELOW_RISK_REWARD_GEOMETRY" in reason for reason in _near_miss_reasons(near_miss))


def _near_miss_reasons(near_miss: Mapping[str, Any]) -> list[str]:
    reasons = near_miss.get("reasons", [])
    return [str(item) for item in reasons] if isinstance(reasons, list) else [str(reasons)]


def _component_point(near_miss: Mapping[str, Any], component: str) -> float:
    points = near_miss.get("component_points", {})
    if not isinstance(points, Mapping):
        return 0.0
    return float(points.get(component) or 0.0)


def quadrant_axes(payload: Mapping[str, Any], config: EntryChainConfig) -> tuple[bool, bool]:
    trend_structure_ok = (
        _component_point(payload, "trend_ema_context") >= float(config.quadrant_trend_ema_min)
        and _component_point(payload, "price_action_structure") >= float(config.quadrant_price_action_min)
    )
    flow_momentum_ok = (
        _component_point(payload, "flow_cvd_confirmation") >= float(config.quadrant_flow_cvd_min)
        and _component_point(payload, "cci_momentum_quality") >= float(config.quadrant_cci_min)
    )
    return trend_structure_ok, flow_momentum_ok


def decision_quadrant(payload: Mapping[str, Any], config: EntryChainConfig) -> str:
    trend_structure_ok, flow_momentum_ok = quadrant_axes(payload, config)
    if trend_structure_ok and flow_momentum_ok:
        return "Q1"
    if trend_structure_ok:
        return "Q2"
    if flow_momentum_ok:
        return "Q3"
    return "Q4"


def annotate_quadrant(payload: Mapping[str, Any], config: EntryChainConfig) -> dict[str, Any]:
    enriched = dict(payload)
    trend_structure_ok, flow_momentum_ok = quadrant_axes(enriched, config)
    enriched["trend_structure_axis_ok"] = trend_structure_ok
    enriched["flow_momentum_axis_ok"] = flow_momentum_ok
    enriched["quadrant"] = decision_quadrant(enriched, config)
    return enriched


def _q1_rr_gap_scout_eligible(near_miss: Mapping[str, Any], config: EntryChainConfig) -> bool:
    if not config.scout_micro_q1_rr_gap_enabled:
        return False
    if decision_quadrant(near_miss, config) != "Q1":
        return False
    side = str(near_miss.get("intended_side") or "").upper()
    return (
        side in {"LONG", "SHORT"}
        and float(near_miss.get("score") or 0.0) >= float(config.scout_micro_q1_rr_gap_min_score)
        and _component_point(near_miss, "flow_cvd_confirmation") >= float(config.scout_micro_q1_rr_gap_min_cvd_score)
        and _has_rr_gap_reason(near_miss)
    )


def _q3_to_q1_confirmation_eligible(near_miss: Mapping[str, Any], config: EntryChainConfig) -> bool:
    if not config.scout_micro_q3_to_q1_enabled:
        return False
    tags = near_miss.get("scout_tags", [])
    tag_list = [str(item) for item in tags] if isinstance(tags, list) else [str(tags)]
    return "Q3_TO_Q1_CONFIRMED" in tag_list


def _q2_pending_momentum_eligible(near_miss: Mapping[str, Any], config: EntryChainConfig) -> bool:
    if not config.scout_micro_q2_pending_enabled:
        return False
    tags = near_miss.get("scout_tags", [])
    tag_list = [str(item) for item in tags] if isinstance(tags, list) else [str(tags)]
    return "Q2_PENDING_MOMENTUM_CONFIRMED" in tag_list


def build_q3_pending_candidate(near_miss: Mapping[str, Any], config: EntryChainConfig, timestamp: int) -> dict[str, Any] | None:
    if not config.scout_micro_q3_to_q1_enabled:
        return None
    if decision_quadrant(near_miss, config) != "Q3":
        return None
    side = str(near_miss.get("intended_side") or "").upper()
    if side not in {"LONG", "SHORT"}:
        return None
    if float(near_miss.get("score") or 0.0) < float(config.scout_micro_q3_to_q1_min_score):
        return None
    if _component_point(near_miss, "flow_cvd_confirmation") < float(config.scout_micro_q3_to_q1_min_cvd_score):
        return None
    expires_at = int(timestamp) + max(1, int(config.scout_micro_q3_to_q1_confirm_bars)) * 900
    return {
        "symbol": str(near_miss.get("symbol") or "").strip().upper(),
        "side": side,
        "created_at": int(timestamp),
        "expires_at": expires_at,
        "source_score": float(near_miss.get("score") or 0.0),
        "source_quadrant": "Q3",
    }


def build_q2_pending_candidate(near_miss: Mapping[str, Any], config: EntryChainConfig, timestamp: int) -> dict[str, Any] | None:
    if not config.scout_micro_q2_pending_enabled:
        return None
    if decision_quadrant(near_miss, config) != "Q2":
        return None
    side = str(near_miss.get("intended_side") or "").upper()
    if side not in {"LONG", "SHORT"}:
        return None
    if float(near_miss.get("score") or 0.0) < float(config.scout_micro_q2_pending_min_score):
        return None
    if _component_point(near_miss, "price_action_structure") < float(config.scout_micro_q2_pending_min_pa_score):
        return None
    expires_at = int(timestamp) + max(1, int(config.scout_micro_q2_pending_confirm_bars)) * 900
    return {
        "symbol": str(near_miss.get("symbol") or "").strip().upper(),
        "side": side,
        "created_at": int(timestamp),
        "expires_at": expires_at,
        "source_score": float(near_miss.get("score") or 0.0),
        "source_quadrant": "Q2",
    }


def confirm_q3_to_q1_pending(
    symbol: str,
    near_miss: Mapping[str, Any],
    config: EntryChainConfig,
    pending: Mapping[str, Any] | None,
    timestamp: int,
) -> dict[str, Any] | None:
    if not config.scout_micro_q3_to_q1_enabled or pending is None:
        return None
    if str(pending.get("source_quadrant") or "") != "Q3":
        return None
    if int(timestamp) > int(pending.get("expires_at") or 0):
        return None
    normalized_symbol = symbol.strip().upper()
    if normalized_symbol != str(pending.get("symbol") or "").strip().upper():
        return None
    side = str(near_miss.get("intended_side") or "").upper()
    if side != str(pending.get("side") or "").upper():
        return None
    if decision_quadrant(near_miss, config) != "Q1":
        return None
    if _component_point(near_miss, "price_action_structure") < float(config.scout_micro_q3_to_q1_confirm_pa_score):
        return None
    confirmed = dict(near_miss)
    tags = confirmed.get("scout_tags", [])
    tag_list = [str(item) for item in tags] if isinstance(tags, list) else [str(tags)]
    confirmed["scout_tags"] = list(dict.fromkeys([*tag_list, "Q3_TO_Q1_CONFIRMED"]))
    confirmed["q3_pending_source"] = dict(pending)
    return confirmed


def confirm_q2_to_q1_pending(
    symbol: str,
    near_miss: Mapping[str, Any],
    config: EntryChainConfig,
    pending: Mapping[str, Any] | None,
    timestamp: int,
) -> dict[str, Any] | None:
    if not config.scout_micro_q2_pending_enabled or pending is None:
        return None
    if str(pending.get("source_quadrant") or "") != "Q2":
        return None
    if int(timestamp) > int(pending.get("expires_at") or 0):
        return None
    normalized_symbol = symbol.strip().upper()
    if normalized_symbol != str(pending.get("symbol") or "").strip().upper():
        return None
    side = str(near_miss.get("intended_side") or "").upper()
    if side != str(pending.get("side") or "").upper():
        return None
    if decision_quadrant(near_miss, config) != "Q1":
        return None
    if _component_point(near_miss, "cci_momentum_quality") < float(config.scout_micro_q2_pending_confirm_cci_score):
        return None
    confirmed = dict(near_miss)
    tags = confirmed.get("scout_tags", [])
    tag_list = [str(item) for item in tags] if isinstance(tags, list) else [str(tags)]
    confirmed["scout_tags"] = list(dict.fromkeys([*tag_list, "Q2_PENDING_MOMENTUM_CONFIRMED"]))
    confirmed["q2_pending_source"] = dict(pending)
    return confirmed


def load_quadrant_pending_state(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        return {}
    pending: dict[str, dict[str, Any]] = {}
    for symbol, payload in data.items():
        if isinstance(payload, Mapping):
            pending[str(symbol).strip().upper()] = dict(payload)
    return pending


def write_quadrant_pending_state(path: Path, pending: Mapping[str, Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {str(symbol).strip().upper(): dict(value) for symbol, value in pending.items()}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def experiment_entry_circuit_active(
    *,
    config: EntryChainConfig,
    timestamp: int,
    experiment_ledgers: Sequence[PaperTradingLedger],
    daily_ledgers: Sequence[PaperTradingLedger],
) -> bool:
    war_fund_limit = float(config.experiment_war_fund_loss_limit)
    daily_limit = float(config.experiment_daily_loss_limit)
    if war_fund_limit < 0 and _experiment_pnl(experiment_ledgers) <= war_fund_limit:
        return True
    if daily_limit < 0 and _experiment_pnl(daily_ledgers, since_ts=_day_start(timestamp), until_ts=timestamp) <= daily_limit:
        return True
    return False


def _experiment_pnl(
    ledgers: Sequence[PaperTradingLedger],
    *,
    since_ts: int | None = None,
    until_ts: int | None = None,
) -> float:
    total = 0.0
    for ledger in ledgers:
        for row in ledger.trade_events():
            if row.get("experiment_id") != FOUR_QUADRANT_EXPERIMENT_ID:
                continue
            ts = int(row.get("timestamp") or 0)
            if since_ts is not None and ts < since_ts:
                continue
            if until_ts is not None and ts > until_ts:
                continue
            total += float(row.get("margin_pnl") or row.get("net_pnl") or 0.0)
    return total


def _day_start(timestamp: int) -> int:
    return int(timestamp) - (int(timestamp) % 86400)


def build_scout_micro_payloads(
    *,
    symbol: str,
    near_miss: Mapping[str, Any],
    price: float,
    config: EntryChainConfig,
    timestamp: int,
    mission: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    side = scout_micro_entry_side(near_miss, mission)
    notional = float(config.scout_micro_reversal_pivot_notional if mission == "REVERSAL_PIVOT_SCOUT" else config.scout_micro_notional)
    if mission == "HIGH_SCORE_LONG_OFFSET_PROBE" and symbol.strip().upper() in HIGH_BETA_SYMBOLS:
        notional *= 0.5
    quantity = notional / float(price)
    entry_context = near_miss.get("entry_context", {})
    entry_context_payload = dict(entry_context) if isinstance(entry_context, Mapping) else {}
    entry_context_payload["side"] = side
    reasons = near_miss.get("reasons", [])
    reason_list = [str(item) for item in reasons] if isinstance(reasons, list) else [str(reasons)]
    mission_reason = f"SCOUT_MISSION_{mission}" if mission else "SCOUT_MISSION_UNCLASSIFIED"
    audit_reasons = ["SCOUT_MICRO", mission_reason, *reason_list]
    if mission == "HIGH_SCORE_LONG_OFFSET_PROBE":
        audit_reasons.append("LONG_OFFSET_Q1_PROBE")
    if mission == "REVERSAL_PIVOT_SCOUT":
        audit_reasons.append("REVERSAL_PIVOT_SIDE_FLIP")
    decision_payload = {
        "timestamp": timestamp,
        "symbol": symbol,
        "action": "PROBE",
        "side": side,
        "score": float(near_miss.get("score") or 0.0),
        "leverage": int(config.scout_micro_leverage),
        "notional_hint": notional,
        "max_symbol_exposure_pct": 0.0,
        "risk_allowed": True,
        "reasons": list(dict.fromkeys(audit_reasons)),
        "entry_context": entry_context_payload,
        "scout_micro": True,
        "scout_mission": mission,
        "scout_tags": _scout_payload_tags(mission),
        "experiment_id": FOUR_QUADRANT_EXPERIMENT_ID,
        "entry_channel": f"scout_{str(mission or 'unknown').lower()}",
        "source_quadrant": str(near_miss.get("quadrant") or decision_quadrant(near_miss, config)),
    }
    draft_payload = {
        "approved": True,
        "reason": "SCOUT_MICRO",
        "request": {
            "position_side": side,
            "quantity": quantity,
            "price": float(price),
        },
    }
    return decision_payload, draft_payload


def _scout_payload_tags(mission: str | None) -> list[str]:
    if mission == "HIGH_SCORE_LONG_OFFSET_PROBE":
        return ["LONG_OFFSET_Q1_PROBE"]
    if mission == "REVERSAL_PIVOT_SCOUT":
        return ["REVERSAL_PIVOT_SIDE_FLIP"]
    return []


def should_open_mirror_ab_sample(
    near_miss: Mapping[str, Any] | None,
    config: EntryChainConfig,
    ab_ledgers: Mapping[str, PaperTradingLedger],
) -> bool:
    if not config.mirror_ab_enabled or near_miss is None:
        return False
    if float(near_miss.get("score") or 0.0) < float(config.mirror_ab_min_score):
        return False
    side = str(near_miss.get("intended_side") or "").upper()
    if side not in {"LONG", "SHORT"}:
        return False
    if float(near_miss.get("entry_price") or 0.0) <= 0.0:
        return False
    reasons = _near_miss_reasons(near_miss)
    allowed = tuple(str(item).upper() for item in config.mirror_ab_allowed_reasons)
    reason_allowed = bool(allowed) and any(any(pattern in reason.upper() for pattern in allowed) for reason in reasons)
    q1_watch_allowed = (
        config.mirror_ab_include_q1_watch
        and str(near_miss.get("action") or "").upper() == "WATCH"
        and decision_quadrant(near_miss, config) == "Q1"
    )
    if not reason_allowed and not q1_watch_allowed:
        return False
    symbol = str(near_miss.get("symbol") or "").strip().upper()
    return bool(symbol) and all(symbol not in ledger.positions for ledger in ab_ledgers.values())


def build_mirror_ab_payloads(
    *,
    symbol: str,
    near_miss: Mapping[str, Any],
    price: float,
    config: EntryChainConfig,
    timestamp: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    side = str(near_miss.get("intended_side") or "").upper()
    notional = float(config.mirror_ab_notional)
    quantity = notional / float(price)
    entry_context = near_miss.get("entry_context", {})
    entry_context_payload = dict(entry_context) if isinstance(entry_context, Mapping) else {}
    entry_context_payload["side"] = side
    reasons = _near_miss_reasons(near_miss)
    source_reason = str(near_miss.get("primary_reason") or next((reason for reason in reasons if reason != "FIB_PA_ARCHITECTURE_WEIGHTS"), "UNKNOWN"))
    source_quadrant = str(near_miss.get("quadrant") or decision_quadrant(near_miss, config))
    decision_payload = {
        "timestamp": timestamp,
        "symbol": symbol,
        "action": "PROBE",
        "side": side,
        "score": float(near_miss.get("score") or 0.0),
        "leverage": 1,
        "notional_hint": notional,
        "max_symbol_exposure_pct": 0.0,
        "risk_allowed": True,
        "reasons": ["MIRROR_AB_SAMPLE", f"MIRROR_AB_SOURCE_{source_reason}", *reasons],
        "entry_context": entry_context_payload,
        "mirror_ab_sample": True,
        "scout_mission": "MIRROR_AB_SAMPLE",
        "experiment_id": FOUR_QUADRANT_EXPERIMENT_ID,
        "entry_channel": "mirror_ab_sample",
        "source_quadrant": source_quadrant,
    }
    draft_payload = {
        "approved": True,
        "reason": "MIRROR_AB_SAMPLE",
        "request": {
            "position_side": side,
            "quantity": quantity,
            "price": float(price),
        },
    }
    return decision_payload, draft_payload


def update_mirror_ab_ledgers(
    *,
    ab_ledgers: Mapping[str, PaperTradingLedger],
    symbol: str,
    near_miss: Mapping[str, Any] | None,
    config: EntryChainConfig,
    kline: Mapping[str, Any],
    timestamp: int,
) -> list[str]:
    normalized_symbol = symbol.strip().upper()
    if not should_open_mirror_ab_sample(near_miss, config, ab_ledgers):
        return []
    near_miss_price = near_miss.get("entry_price") if near_miss is not None else None
    price = float(kline.get("close") or near_miss_price or 0.0)
    if price <= 0.0:
        return []
    decision_payload, draft_payload = build_mirror_ab_payloads(
        symbol=normalized_symbol,
        near_miss=near_miss or {},
        price=price,
        config=config,
        timestamp=timestamp,
    )
    events: list[str] = []
    for name, ledger in sorted(ab_ledgers.items()):
        ledger_events = ledger.on_decision(
            symbol=normalized_symbol,
            decision_payload=decision_payload,
            draft_payload=draft_payload,
            kline=kline,
            timestamp=timestamp,
        )
        events.extend(f"{name}:{event}" for event in ledger_events)
    return events


def update_scout_micro_ledger(
    *,
    scout_paper: PaperTradingLedger,
    symbol: str,
    near_miss: Mapping[str, Any] | None,
    config: EntryChainConfig,
    data_health: str,
    kline: Mapping[str, Any],
    timestamp: int,
) -> list[str]:
    normalized_symbol = symbol.strip().upper()
    if normalized_symbol not in config.scout_micro_symbols and normalized_symbol not in scout_paper.positions:
        return []
    near_miss_price = near_miss.get("entry_price") if near_miss is not None else None
    price = float(kline.get("close") or near_miss_price or 0.0)
    if should_open_scout_micro(
        symbol=normalized_symbol,
        near_miss=near_miss,
        config=config,
        data_health=data_health,
        scout_paper=scout_paper,
        timestamp=timestamp,
    ):
        mission = scout_micro_mission(normalized_symbol, near_miss or {}, config)
        decision_payload, draft_payload = build_scout_micro_payloads(
            symbol=normalized_symbol,
            near_miss=near_miss or {},
            price=price,
            config=config,
            timestamp=timestamp,
            mission=mission,
        )
    else:
        decision_payload = {
            "timestamp": timestamp,
            "symbol": normalized_symbol,
            "action": "NO_TRADE",
            "side": "NONE",
            "reasons": ["SCOUT_MICRO_NO_OPEN"],
            "entry_context": {},
        }
        draft_payload = {"approved": False, "reason": "SCOUT_MICRO_NO_OPEN"}
    return scout_paper.on_decision(
        symbol=normalized_symbol,
        decision_payload=decision_payload,
        draft_payload=draft_payload,
        kline=kline,
        timestamp=timestamp,
    )


def apply_dry_run_decision_controls(
    decision: EntryChainDecision,
    *,
    config: EntryChainConfig,
    paper: PaperTradingLedger,
    timestamp: int,
) -> EntryChainDecision:
    symbol = str(decision.metadata.get("symbol") or "").strip().upper()
    if decision.action not in {"PROBE", "DIRECT"}:
        return decision
    reasons: list[str] = []
    if symbol in config.observation_only_symbols:
        reasons.append("SYMBOL_OBSERVATION_ONLY")
    if _post_initial_stop_cooldown_active(symbol, config, paper, timestamp):
        reasons.append("SYMBOL_POST_INITIAL_STOP_COOLDOWN")
    if _rolling_initial_stop_cooldown_active(symbol, config, paper, timestamp):
        reasons.append("SYMBOL_ROLLING_INITIAL_STOP_COOLDOWN")
    if _portfolio_consecutive_stop_circuit_active(config, paper, timestamp):
        reasons.append("PORTFOLIO_CONSECUTIVE_INITIAL_STOP_CIRCUIT_BREAKER")
    if _portfolio_daily_loss_circuit_active(config, paper, timestamp):
        reasons.append("PORTFOLIO_DAILY_LOSS_CIRCUIT_BREAKER")
    if _weak_edge_direct_without_positive_history(decision, config, paper, timestamp):
        reasons.append("DIRECT_WEAK_EDGE_DEMOTED")
    if _weak_edge_probe_without_positive_history(decision, config, paper, timestamp):
        reasons.append("PROBE_WEAK_EDGE_DEMOTED")
    if not reasons:
        return decision
    return _cap_decision_to_watch(decision, reasons)


def apply_paper_state_to_context(
    context: EntryChainContext,
    paper: PaperTradingLedger,
    timestamp: int,
) -> EntryChainContext:
    snapshot = paper.get_portfolio_state_snapshot(timestamp)
    enriched = apply_paper_snapshot_to_context(context, snapshot, paper.initial_equity)
    return enriched.with_updates(
        available_margin=max(0.0, paper.initial_equity * 0.8 - _paper_margin_used(paper)),
    )


def apply_paper_snapshot_to_context(
    context: EntryChainContext,
    snapshot: PortfolioStateSnapshot,
    initial_equity: float,
) -> EntryChainContext:
    symbol = context.symbol.strip().upper()
    side = context.side.strip().upper()
    same_direction_exposure = (
        snapshot.same_direction_long_pct
        if side == "LONG"
        else snapshot.same_direction_short_pct
        if side == "SHORT"
        else 0.0
    )
    equity = max(0.0, initial_equity * (1.0 + snapshot.daily_profit_pct))
    return context.with_updates(
        active_symbols=snapshot.open_position_count,
        active_symbol_names=frozenset(snapshot.active_symbols),
        portfolio_trades_today=snapshot.portfolio_trades_today,
        symbol_trades_today=snapshot.daily_trades_by_symbol.get(symbol, 0),
        daily_profit_pct=snapshot.daily_profit_pct,
        symbol_exposure_pct=snapshot.symbol_exposure_pct.get(symbol, 0.0),
        total_exposure_pct=snapshot.total_exposure_pct,
        same_direction_exposure_pct=same_direction_exposure,
        account_equity=equity if equity > 0 else context.account_equity,
    )


def _cap_decision_to_watch(decision: EntryChainDecision, reasons: Sequence[str]) -> EntryChainDecision:
    merged_reasons = tuple(dict.fromkeys([*decision.reasons, *reasons]))
    return replace(
        decision,
        action="WATCH",
        side="NONE",
        reasons=merged_reasons,
        risk_allowed=False,
        leverage=0,
        notional_hint=0.0,
    )


def _post_initial_stop_cooldown_active(
    symbol: str,
    config: EntryChainConfig,
    paper: PaperTradingLedger,
    timestamp: int,
) -> bool:
    if not config.post_initial_stop_cooldown_enabled:
        return False
    cooldown_seconds = max(1, int(config.post_initial_stop_cooldown_hours)) * 3600
    stops = paper.recent_closed_trades(
        symbol,
        reason="INITIAL_STOP_HIT",
        since_ts=timestamp - cooldown_seconds,
        until_ts=timestamp,
    )
    if not stops:
        return False
    latest_stop_ts = max(int(row.get("timestamp") or 0) for row in stops)
    return timestamp < latest_stop_ts + cooldown_seconds


def _rolling_initial_stop_cooldown_active(
    symbol: str,
    config: EntryChainConfig,
    paper: PaperTradingLedger,
    timestamp: int,
) -> bool:
    if not config.rolling_symbol_cooldown_enabled:
        return False
    window_seconds = max(1, int(config.rolling_symbol_cooldown_window_hours)) * 3600
    cooldown_seconds = max(1, int(config.rolling_symbol_cooldown_hours)) * 3600
    stops = paper.recent_closed_trades(
        symbol,
        reason="INITIAL_STOP_HIT",
        since_ts=timestamp - window_seconds,
        until_ts=timestamp,
    )
    if len(stops) < max(1, int(config.rolling_symbol_cooldown_stop_threshold)):
        return False
    latest_stop_ts = max(int(row.get("timestamp") or 0) for row in stops)
    return timestamp < latest_stop_ts + cooldown_seconds


def _portfolio_consecutive_stop_circuit_active(
    config: EntryChainConfig,
    paper: PaperTradingLedger,
    timestamp: int,
) -> bool:
    if not config.portfolio_stop_circuit_enabled:
        return False
    required = max(1, int(config.portfolio_stop_circuit_count))
    cooldown_seconds = max(1, int(config.portfolio_stop_circuit_hours)) * 3600
    closed = paper.recent_closed_trades_all(until_ts=timestamp)
    if len(closed) < required:
        return False
    recent = sorted(closed, key=lambda row: int(row.get("timestamp") or 0))[-required:]
    if any(row.get("reason") != "INITIAL_STOP_HIT" for row in recent):
        return False
    latest_stop_ts = int(recent[-1].get("timestamp") or 0)
    return timestamp < latest_stop_ts + cooldown_seconds


def _portfolio_daily_loss_circuit_active(
    config: EntryChainConfig,
    paper: PaperTradingLedger,
    timestamp: int,
) -> bool:
    if not config.portfolio_daily_loss_circuit_enabled:
        return False
    day_start = int(timestamp) - (int(timestamp) % 86400)
    realized = 0.0
    for row in paper.recent_closed_trades_all(since_ts=day_start, until_ts=timestamp):
        realized += float(row.get("position_realized_pnl") or row.get("net_pnl") or 0.0)
    return realized <= float(config.portfolio_daily_loss_limit)


def _weak_edge_direct_without_positive_history(
    decision: EntryChainDecision,
    config: EntryChainConfig,
    paper: PaperTradingLedger,
    timestamp: int,
) -> bool:
    if decision.action != "DIRECT":
        return False
    if decision.score < config.weak_edge_direct_min_score or decision.score > config.weak_edge_direct_max_score:
        return False
    symbol = str(decision.metadata.get("symbol") or "").strip().upper()
    return not paper.has_positive_closed_trade(symbol, until_ts=timestamp)


def _weak_edge_probe_without_positive_history(
    decision: EntryChainDecision,
    config: EntryChainConfig,
    paper: PaperTradingLedger,
    timestamp: int,
) -> bool:
    if decision.action != "PROBE":
        return False
    if decision.score < config.weak_edge_probe_min_score or decision.score > config.weak_edge_probe_max_score:
        return False
    symbol = str(decision.metadata.get("symbol") or "").strip().upper()
    return not paper.has_positive_closed_trade(symbol, until_ts=timestamp)


def resolve_output_dir(args: argparse.Namespace, *, timestamp: int | None = None) -> Path:
    if args.output_dir:
        return Path(args.output_dir)
    if args.log_date:
        day = datetime.strptime(args.log_date, "%Y-%m-%d").date()
    elif timestamp is not None:
        day = datetime.fromtimestamp(timestamp, tz=UTC).date()
    else:
        day = datetime.now(UTC).date()
    month = day.strftime("%Y-%m")
    return Path(args.log_root) / month / day.isoformat()


def resolve_paper_state_dir(args: argparse.Namespace) -> Path:
    if args.paper_state_dir:
        return Path(args.paper_state_dir)
    if args.output_dir:
        return Path(args.output_dir)
    return Path(args.log_root).parent / "state" / "paper"


def resolve_runtime_symbols(args: argparse.Namespace, config) -> tuple[list[str], dict[str, Any]]:
    if args.symbols:
        symbols = resolve_symbols(args.symbols, ())
        return symbols, {"source": "cli", "rank_start": None, "rank_end": None, "fallback_used": False, "error": None}
    if args.market_data_source == "synthetic":
        symbols = resolve_symbols(None, config.dry_run_symbols)
        return symbols, {"source": "configured_synthetic", "rank_start": None, "rank_end": None, "fallback_used": False, "error": None}
    if config.dry_run_symbol_source == "market_cap_rank":
        try:
            symbols, assets = resolve_market_cap_rank_symbols(config.dry_run_rank_start, config.dry_run_rank_end)
            if symbols:
                return symbols, {
                    "source": "market_cap_rank",
                    "rank_start": config.dry_run_rank_start,
                    "rank_end": config.dry_run_rank_end,
                    "fallback_used": False,
                    "error": None,
                    "assets": assets,
                }
        except Exception as exc:
            fallback_symbols = resolve_symbols(None, config.dry_run_symbols)
            return fallback_symbols, {
                "source": "configured_fallback",
                "rank_start": config.dry_run_rank_start,
                "rank_end": config.dry_run_rank_end,
                "fallback_used": True,
                "error": exc.__class__.__name__,
            }
    symbols = resolve_symbols(None, config.dry_run_symbols)
    return symbols, {"source": "configured", "rank_start": None, "rank_end": None, "fallback_used": False, "error": None}


def resolve_symbols(value: str | None, config_symbols: Sequence[str]) -> list[str]:
    source = value if value is not None else ",".join(config_symbols)
    symbols = [item.strip().upper() for item in source.split(",") if item.strip()]
    return symbols or ["BNBUSDT"]


def resolve_market_cap_rank_symbols(rank_start: int, rank_end: int) -> tuple[list[str], list[dict[str, Any]]]:
    markets = fetch_json(
        COINGECKO_MARKETS_URL,
        {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": max(rank_end, 30),
            "page": 1,
            "sparkline": "false",
        },
    )
    exchange_info = fetch_json(BINANCE_EXCHANGE_INFO_URL, {})
    tradable = {
        item["baseAsset"].upper(): item["symbol"]
        for item in exchange_info.get("symbols", [])
        if item.get("quoteAsset") == "USDT" and item.get("contractType") == "PERPETUAL" and item.get("status") == "TRADING"
    }
    assets: list[dict[str, Any]] = []
    symbols: list[str] = []
    for asset in markets:
        rank = int(asset.get("market_cap_rank") or 0)
        if rank < rank_start or rank > rank_end:
            continue
        coin_id = str(asset.get("id", ""))
        base = COINGECKO_BASE_OVERRIDES.get(coin_id, str(asset.get("symbol", "")).upper())
        if coin_id in STABLE_IDS or base in STABLE_SYMBOLS:
            continue
        symbol = tradable.get(base)
        if symbol is None:
            continue
        symbols.append(symbol)
        assets.append({"market_cap_rank": rank, "id": coin_id, "base_asset": base, "symbol": symbol})
    return symbols, assets


def fetch_json(url: str, params: Mapping[str, Any]) -> Any:
    query = f"?{urlencode(params)}" if params else ""
    with urlopen(f"{url}{query}", timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_kline_alignment(args: argparse.Namespace) -> list[str]:
    if not args.align_to_kline_close:
        return []
    now = time.time()
    target_ts = next_kline_run_timestamp(now, args.kline_interval_seconds, args.post_close_delay_seconds)
    sleep_seconds = max(0.0, target_ts - now)
    if sleep_seconds > 0:
        time.sleep(sleep_seconds)
    return [
        "K线时间对齐: "
        f"interval={args.kline_interval_seconds}s, post_close_delay={args.post_close_delay_seconds:.2f}s, "
        f"target_utc={utc_text(target_ts)}, slept={sleep_seconds:.2f}s"
    ]


def next_kline_run_timestamp(now: float, interval_seconds: int, post_close_delay_seconds: float) -> int:
    interval = max(1, int(interval_seconds))
    delay = max(0.0, float(post_close_delay_seconds))
    current_boundary = int(now // interval) * interval
    candidate = current_boundary + delay
    if now < candidate:
        return int(candidate)
    return int(current_boundary + interval + delay)


def render_schedule_wait_log(args: argparse.Namespace, cycle_started_ts: int, cycle_finished_ts: float, elapsed: float) -> str:
    if args.once:
        return (
            "调度等待: once=true, exit_after_current_cycle, "
            f"cycle_started_utc={utc_text(cycle_started_ts)}, "
            f"cycle_finished_utc={utc_text(int(cycle_finished_ts))}, elapsed={elapsed:.2f}s"
        )
    if args.align_to_kline_close:
        next_ts = next_kline_run_timestamp(cycle_finished_ts, args.kline_interval_seconds, args.post_close_delay_seconds)
        sleep_seconds = max(0.0, next_ts - cycle_finished_ts)
        return (
            f"调度等待: kline_align=ON, next_review_utc={utc_text(next_ts)}, "
            f"post_close_delay={args.post_close_delay_seconds:.2f}s, "
            f"cycle_started_utc={utc_text(cycle_started_ts)}, cycle_finished_utc={utc_text(int(cycle_finished_ts))}, "
            f"elapsed={elapsed:.2f}s, sleep_until_next={sleep_seconds:.2f}s"
        )
    sleep_seconds = float(args.interval_seconds)
    next_ts = int(cycle_finished_ts + sleep_seconds)
    return (
        f"调度等待: utc_now={utc_text(int(cycle_finished_ts))}, sleep={sleep_seconds:.2f}s, "
        f"next_review_utc={utc_text(next_ts)}, cycle_started_utc={utc_text(cycle_started_ts)}, "
        f"cycle_finished_utc={utc_text(int(cycle_finished_ts))}, elapsed={elapsed:.2f}s"
    )


def synthetic_context(symbol: str, timestamp: int, config: EntryChainConfig | None = None) -> EntryChainContext:
    cfg = config or EntryChainConfig()
    scores = synthetic_component_scores(symbol, timestamp, cfg)
    return EntryChainContext(
        symbol=symbol,
        timestamp=timestamp,
        side="LONG",
        component_scores=scores,
        quote_volume_24h=200_000_000.0,
        atr_pct=0.018,
        expected_order_size=1_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
    )


def synthetic_component_scores(symbol: str, timestamp: int, config: EntryChainConfig) -> dict[str, float]:
    if not config.use_fib_pa_architecture:
        return {
            "background_4h": 0.8,
            "direction_1h": 0.8,
            "quality_30m": 0.75,
            "trigger_15m": 0.7,
            "cvd_flow": 0.6,
            "volatility_stop": 0.9,
            "liquidity_execution": 1.0,
            "market_regime": 0.8,
        }
    price = synthetic_price(symbol)
    bars = [
        BacktestBar(
            symbol=symbol.upper(),
            timestamp=timestamp - (240 - index) * 900,
            open=price + index * 0.01,
            high=price + index * 0.01 + 0.2,
            low=price + index * 0.01 - 0.2,
            close=price + index * 0.01,
            volume=1000.0,
        )
        for index in range(240)
    ]
    histories = {"15m": bars, "30m": bars[-80:], "1h": bars[-80:], "4h": bars[-80:]}
    return component_scores(
        "LONG",
        histories,
        0.01,
        use_ema_architecture=config.use_ema_architecture,
        ema200_gate_mode=config.ema200_gate_mode,
        use_fib_pa_architecture=config.use_fib_pa_architecture,
    )


def build_context(
    symbol: str,
    timestamp: int,
    args: argparse.Namespace,
    config,
    warmup_history: Mapping[str, Sequence[BacktestBar]] | None = None,
) -> tuple[EntryChainContext, str, dict[str, Any]]:
    if args.market_data_source == "synthetic":
        context = synthetic_context(symbol, timestamp, config)
        return context, "OK", synthetic_debug_snapshot(symbol, timestamp, context)
    try:
        histories = fetch_public_market_histories(symbol, limit=public_history_limit(args, config))
        context, debug = public_market_context(symbol, timestamp, histories, config)
        return context, "OK", debug
    except Exception as exc:
        if warmup_history:
            context, debug = public_market_context(symbol, timestamp, warmup_history, config)
            debug["warmup"]["cache_fallback"] = True
            debug["warmup"]["error"] = exc.__class__.__name__
            return context, "DEGRADED", debug
        context = degraded_context(symbol, timestamp)
        debug = synthetic_debug_snapshot(symbol, timestamp, context)
        debug["warmup"]["error"] = exc.__class__.__name__
        debug["warmup"]["ready"] = False
        return context, "DEGRADED", debug


def fetch_public_market_histories(symbol: str, *, limit: int) -> dict[str, list[BacktestBar]]:
    return {
        timeframe: fetch_public_klines(symbol, timeframe, limit=limit)
        for timeframe in ("15m", "30m", "1h", "4h")
    }


def warmup_symbols(symbols: Sequence[str], args: argparse.Namespace, config) -> dict[str, dict[str, list[BacktestBar]]]:
    limit = public_history_limit(args, config)
    warmed: dict[str, dict[str, list[BacktestBar]]] = {}
    for symbol in symbols:
        try:
            warmed[symbol] = fetch_public_market_histories(symbol, limit=limit)
        except Exception:
            warmed[symbol] = {}
    return warmed


def synthetic_warmup_state(symbols: Sequence[str], config) -> dict[str, dict[str, list[BacktestBar]]]:
    count = max(int(config.dry_run_warmup_15m_bars), 240)
    now = int(time.time())
    state: dict[str, dict[str, list[BacktestBar]]] = {}
    for symbol in symbols:
        price = synthetic_price(symbol)
        state[symbol] = {
            "15m": [
                BacktestBar(
                    symbol=symbol,
                    timestamp=now - (count - index) * 900,
                    open=price,
                    high=price,
                    low=price,
                    close=price,
                    volume=1.0,
                )
                for index in range(count)
            ]
        }
    return state


def public_history_limit(args: argparse.Namespace, config) -> int:
    required = max(int(config.dry_run_warmup_15m_bars), 200 if config.use_ema_architecture else 240)
    return max(int(args.public_kline_limit), required) + 1


def fetch_public_klines(symbol: str, interval: str, *, limit: int) -> list[BacktestBar]:
    params = urlencode({"symbol": symbol.upper(), "interval": interval, "limit": max(2, min(limit, 1500))})
    url = f"https://fapi.binance.com/fapi/v1/klines?{params}"
    with urlopen(url, timeout=10) as response:
        rows = json.loads(response.read().decode("utf-8"))
    now_ms = int(time.time() * 1000)
    bars: list[BacktestBar] = []
    for row in rows:
        close_time_ms = int(row[6])
        if close_time_ms >= now_ms:
            continue
        bars.append(
            BacktestBar(
                symbol=symbol.upper(),
                timestamp=int(row[0]) // 1000,
                open=float(row[1]),
                high=float(row[2]),
                low=float(row[3]),
                close=float(row[4]),
                volume=float(row[5]),
            )
        )
    return bars


def public_market_context(
    symbol: str,
    timestamp: int,
    histories: Mapping[str, Sequence[BacktestBar]],
    config,
) -> tuple[EntryChainContext, dict[str, Any]]:
    bars_15m = list(histories.get("15m", []))
    required_15m = max(1, int(getattr(config, "dry_run_warmup_15m_bars", 240) or 240))
    if len(bars_15m) < required_15m or len(histories.get("1h", [])) < 4:
        context = degraded_context(symbol, timestamp)
        return context, public_debug_snapshot(symbol, context, histories, {}, ready=False, required_15m=required_15m)
    side = direction_from_history(histories.get("1h", []))
    if side == "NONE":
        side = "LONG" if bars_15m[-1].close >= bars_15m[-4].close else "SHORT"
    atr_pct_value = atr_pct(bars_15m[-20:])
    scores = component_scores(
        side,
        histories,
        atr_pct_value,
        use_ema_architecture=config.use_ema_architecture,
        ema200_gate_mode=config.ema200_gate_mode,
        use_fib_pa_architecture=config.use_fib_pa_architecture,
    )
    score_diagnostics = {}
    if config.use_fib_pa_architecture:
        atr_value = bars_15m[-1].close * max(0.0, atr_pct_value)
        score_diagnostics["risk_reward_geometry"] = risk_reward_geometry_detail(
            bars_15m[-1].close,
            side,
            atr_value,
            atr_pct_value,
            detect_fractal_swings(bars_15m, atr=atr_value),
        )
    previous_bar = bars_15m[-2]
    current_bar = bars_15m[-1]
    context = EntryChainContext(
        symbol=symbol.upper(),
        timestamp=current_bar.timestamp,
        side=side,
        component_scores=scores,
        quote_volume_24h=quote_volume(bars_15m[-96:]),
        atr_pct=atr_pct_value,
        expected_order_size=1_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
        wick_anomaly_active=wick_anomaly(current_bar, previous_bar),
        stop_pct=max(0.005, min(0.04, atr_pct_value * 1.5)),
        long_overextension_active=long_overextension_active(bars_15m),
        long_upper_wick_risk_active=long_upper_wick_risk_active(bars_15m),
        long_chase_risk_active=long_chase_risk_active(bars_15m, atr_pct_value),
        long_low_liquidity_session_active=long_low_liquidity_session_active(current_bar.timestamp, bars_15m),
        long_cvd_weak_active=scores.get("cvd_flow", 0.0) < config.long_cvd_weak_threshold,
        extreme_position_ratio=extreme_position_ratio(bars_15m),
        current_volatility_scale=max(0.1, atr_pct_value / 0.01),
        normal_volatility_scale=1.0,
    )
    debug = public_debug_snapshot(symbol, context, histories, scores, ready=True, required_15m=required_15m)
    debug["score_diagnostics"] = score_diagnostics
    return context, debug


def degraded_context(symbol: str, timestamp: int) -> EntryChainContext:
    return EntryChainContext(
        symbol=symbol.upper(),
        timestamp=timestamp,
        side="LONG",
        component_scores={},
        quote_volume_24h=0.0,
        atr_pct=0.0,
        expected_order_size=1_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
        polluted_until_ts=timestamp + 900,
    )


def synthetic_debug_snapshot(symbol: str, timestamp: int, context: EntryChainContext) -> dict[str, Any]:
    diagnostics = {}
    if "risk_reward_geometry" in context.component_scores:
        diagnostics["risk_reward_geometry"] = {
            "score": round(float(context.component_scores.get("risk_reward_geometry", 0.0)) * 8.0, 4),
            "net_tp1_r": None,
            "stop_pct": context.stop_pct,
            "tp1_pct": context.stop_pct,
            "opposition_dist_r": None,
            "rr_zero_reason": "SYNTHETIC_CONTEXT",
        }
    return {
        "warmup": {
            "source": "synthetic",
            "ready": True,
            "15m": 240,
            "30m": 240,
            "1h": 240,
            "4h": 240,
            "required_15m": 240,
            "ema200_ready": True,
        },
        "kline": {
            "timeframe": "15m",
            "timestamp": timestamp,
            "open": synthetic_price(symbol),
            "close": synthetic_price(symbol),
            "change_pct": 0.0,
        },
        "scores": dict(context.component_scores),
        "score_diagnostics": diagnostics,
        "entry_context": context_snapshot(context),
    }


def public_debug_snapshot(
    symbol: str,
    context: EntryChainContext,
    histories: Mapping[str, Sequence[BacktestBar]],
    scores: Mapping[str, float],
    *,
    ready: bool,
    required_15m: int,
) -> dict[str, Any]:
    bars_15m = list(histories.get("15m", []))
    latest = bars_15m[-1] if bars_15m else None
    change_pct = ((latest.close - latest.open) / latest.open) if latest and latest.open else 0.0
    return {
        "warmup": {
            "source": "public-binance",
            "ready": ready,
            "15m": len(histories.get("15m", [])),
            "30m": len(histories.get("30m", [])),
            "1h": len(histories.get("1h", [])),
            "4h": len(histories.get("4h", [])),
            "required_15m": required_15m,
            "ema200_ready": len(histories.get("15m", [])) >= 200,
        },
        "kline": {
            "timeframe": "15m",
            "timestamp": latest.timestamp if latest else context.timestamp,
            "open": latest.open if latest else None,
            "high": latest.high if latest else None,
            "low": latest.low if latest else None,
            "close": latest.close if latest else None,
            "volume": latest.volume if latest else None,
            "change_pct": change_pct,
        },
        "scores": dict(scores),
        "entry_context": context_snapshot(context),
    }


def context_snapshot(context: EntryChainContext) -> dict[str, Any]:
    return {
        "side": context.side,
        "atr_pct": context.atr_pct,
        "quote_volume_24h": context.quote_volume_24h,
        "stop_pct": context.stop_pct,
        "active_symbols": context.active_symbols,
        "active_symbol_names": sorted(context.active_symbol_names),
        "portfolio_trades_today": context.portfolio_trades_today,
        "symbol_trades_today": context.symbol_trades_today,
        "symbol_exposure_pct": context.symbol_exposure_pct,
        "total_exposure_pct": context.total_exposure_pct,
        "same_direction_exposure_pct": context.same_direction_exposure_pct,
        "daily_profit_pct": context.daily_profit_pct,
        "available_margin": context.available_margin,
        "long_overextension_active": context.long_overextension_active,
        "long_upper_wick_risk_active": context.long_upper_wick_risk_active,
        "long_chase_risk_active": context.long_chase_risk_active,
        "long_low_liquidity_session_active": context.long_low_liquidity_session_active,
        "long_cvd_weak_active": context.long_cvd_weak_active,
        "extreme_position_ratio": context.extreme_position_ratio,
    }


def synthetic_price(symbol: str) -> float:
    prices = {"BNBUSDT": 600.0, "SOLUSDT": 150.0}
    return prices.get(symbol.upper(), 100.0)


def synthetic_market_snapshot() -> dict[str, float]:
    return {
        "btc_daily_return": 0.0,
        "btc_weekly_return": 0.0,
        "usdt_premium": 0.0,
    }


def attribution_events(
    symbol: str,
    timestamp: int,
    decision_payload: Mapping[str, Any],
    draft_payload: Mapping[str, Any],
    price: float,
) -> list[dict[str, Any]]:
    decision = attribution_decision(symbol, decision_payload)
    decision_ts = datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
    return [
        {
            "ts": decision_ts,
            "event": "decision",
            "decision": decision,
            "context": {
                "symbol": symbol,
                "price": price,
                "kline": decision_payload.get("kline", {}),
                "warmup": decision_payload.get("warmup", {}),
            },
        },
        {
            "ts": decision_ts,
            "event": "execution",
            "decision": {
                **decision,
                "time_in_force": "Ioc",
                "tp_execution": "dry_run_none",
                "sl_execution": "dry_run_none",
            },
            "result": attribution_result(decision_payload, draft_payload),
        },
    ]


def attribution_decision(symbol: str, decision_payload: Mapping[str, Any]) -> dict[str, Any]:
    action = str(decision_payload.get("action", "NO_TRADE"))
    executable = action in {"PROBE", "DIRECT"}
    target_pct = float(decision_payload.get("max_symbol_exposure_pct") or 0.0) if executable else 0.0
    return {
        "operation": action_to_operation(action),
        "symbol": symbol,
        "target_portion_of_balance": target_pct,
        "leverage": int(decision_payload.get("leverage") or 1),
        "reason": primary_reason(decision_payload),
        "metadata": {
            "signal_score": decision_payload.get("score"),
            "action": action,
            "side": decision_payload.get("side"),
            "risk_allowed": decision_payload.get("risk_allowed"),
            "model_version": decision_payload.get("model_version"),
            "latency_ms": decision_payload.get("latency_ms"),
            "score_detail": decision_payload.get("score_detail", {}),
            "entry_context": decision_payload.get("entry_context", {}),
            "reasons": decision_payload.get("reasons", []),
        },
    }


def attribution_result(decision_payload: Mapping[str, Any], draft_payload: Mapping[str, Any]) -> dict[str, Any]:
    if draft_payload.get("approved"):
        return {
            "status": "draft_ready",
            "message": "dry-run order draft only; exchange mutation disabled",
            "approved": True,
            "orders_submitted": 0,
        }
    return {
        "status": "noop",
        "message": str(draft_payload.get("reason") or primary_reason(decision_payload)),
        "approved": False,
        "orders_submitted": 0,
    }


def action_to_operation(action: str) -> str:
    if action == "DIRECT":
        return "direct"
    if action == "PROBE":
        return "probe"
    if action == "WATCH":
        return "watch"
    return "hold"


def primary_reason(decision_payload: Mapping[str, Any]) -> str:
    reasons = decision_payload.get("reasons", [])
    if isinstance(reasons, list) and reasons:
        return str(reasons[0])
    if reasons:
        return str(reasons)
    return str(decision_payload.get("action", "NO_TRADE")).lower()


def write_health(
    output_dir: Path,
    symbols: list[str],
    orders_submitted: int,
    data_health: str,
    symbol_meta: Mapping[str, Any],
    warmup_state: Mapping[str, Mapping[str, Sequence[BacktestBar]]],
    required_15m: int,
) -> None:
    payload = {
        "mode": "dry_run",
        "symbols": symbols,
        "symbol_universe": dict(symbol_meta),
        "warmup": warmup_summary(warmup_state, symbols, required_15m),
        "orders_submitted": orders_submitted,
        "exchange_mutation_enabled": False,
        "data_health": data_health,
        "timestamp": int(time.time()),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "health.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_runtime_log(output_dir: Path, lines: Sequence[str], *, timestamp: int | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / runtime_log_name(int(time.time()) if timestamp is None else timestamp)).open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line)
            handle.write("\n")
        handle.write("\n")


def runtime_log_name(timestamp: int) -> str:
    hour = datetime.fromtimestamp(timestamp, tz=UTC).hour
    bucket = (hour // 6) * 6
    return f"runtime.out.{bucket:02d}.log"


def render_cycle_header(
    cycle: int,
    timestamp: int,
    args: argparse.Namespace,
    symbols: Sequence[str],
    symbol_meta: Mapping[str, Any],
    warmup_state: Mapping[str, Mapping[str, Sequence[BacktestBar]]],
    required_15m: int,
    paper: PaperTradingLedger,
) -> list[str]:
    return [
        f"=== AI300_DRY_RUN cycle {cycle} @ {utc_text(timestamp)} === [mode={args.market_data_source}, kline_align=ON, tf=900s]",
        render_paper_account_header(paper, timestamp),
        f"DRY-RUN安全: exchange_mutation_enabled=False, orders_submitted=0, symbols={len(symbols)}, config={args.config}",
        "交易对宇宙: "
        f"source={symbol_meta.get('source')} rank={symbol_meta.get('rank_start')}-{symbol_meta.get('rank_end')} "
        f"fallback={symbol_meta.get('fallback_used')} error={symbol_meta.get('error')}",
        f"启动预热: {format_warmup_summary(warmup_state, symbols, required_15m)}",
    ]


def render_startup_log(
    args: argparse.Namespace,
    startup_ts: int,
    symbols: Sequence[str],
    symbol_meta: Mapping[str, Any],
    warmup_state: Mapping[str, Mapping[str, Sequence[BacktestBar]]],
    required_15m: int,
) -> list[str]:
    lines = [
        f"=== AI300_DRY_RUN process_start @ {utc_text(startup_ts)} === [mode={args.market_data_source}, kline_align={'ON' if args.align_to_kline_close else 'OFF'}, tf={args.kline_interval_seconds}s]",
        f"进程启动: pid={os.getpid()}, config={args.config}, target_tier={args.target_tier}, log_root={args.log_root}",
        "交易对宇宙: "
        f"source={symbol_meta.get('source')} rank={symbol_meta.get('rank_start')}-{symbol_meta.get('rank_end')} "
        f"fallback={symbol_meta.get('fallback_used')} error={symbol_meta.get('error')} symbols={len(symbols)}",
        f"启动预热完成: {format_warmup_summary(warmup_state, symbols, required_15m)}",
    ]
    if args.align_to_kline_close:
        next_ts = next_kline_run_timestamp(float(startup_ts), args.kline_interval_seconds, args.post_close_delay_seconds)
        lines.append(
            "first_scan_wait: "
            f"next_review_utc={utc_text(next_ts)}, post_close_delay={args.post_close_delay_seconds:.2f}s, "
            f"sleep_until_first_scan={max(0.0, next_ts - startup_ts):.2f}s"
        )
    else:
        lines.append(f"first_scan_wait: align_to_kline_close=OFF, first_cycle_starts_immediately=True, interval_seconds={args.interval_seconds:.2f}s")
    return lines


def render_paper_account_header(paper: PaperTradingLedger, timestamp: int) -> str:
    summary = paper.summary(timestamp)
    equity = float(summary.get("equity") or 0.0)
    initial_equity = float(summary.get("initial_equity") or 0.0)
    open_positions = int(summary.get("open_positions") or 0)
    margin_equity = float(summary.get("margin_equity") or equity)
    realized = float(summary.get("realized_pnl") or 0.0)
    unrealized = float(summary.get("unrealized_pnl") or 0.0)
    return_pct = float(summary.get("return_pct") or 0.0)
    max_drawdown = float(summary.get("max_drawdown") or 0.0)
    win_rate = float(summary.get("win_rate") or 0.0)
    profit_factor = float(summary.get("profit_factor") or 0.0)
    trade_count = int(summary.get("trade_count") or 0)
    available = max(0.0, initial_equity * 0.8 - _paper_margin_used(paper))
    return (
        "当前权益: "
        f"equity={equity:.2f} USDT, available={available:.2f} USDT, "
        f"unrealized={unrealized:+.2f} USDT, realized={realized:+.2f} USDT, "
        f"return={return_pct * 100:+.2f}%, max_dd={max_drawdown * 100:.2f}%, "
        f"win_rate={win_rate * 100:.2f}%, pf={profit_factor:.4f}, trades={trade_count}, "
        f"open_positions={open_positions}, margin_equity={margin_equity:.2f} USDT"
    )


def _paper_margin_used(paper: PaperTradingLedger) -> float:
    return sum(position.notional * position.remaining_fraction / max(1, int(position.leverage)) for position in paper.positions.values())


def render_symbol_log(
    symbol: str,
    context: EntryChainContext,
    decision_payload: Mapping[str, Any],
    draft_payload: Mapping[str, Any],
    stress: Mapping[str, Any],
    debug: Mapping[str, Any],
) -> list[str]:
    action = str(decision_payload.get("action", "UNKNOWN"))
    state = "draft_ready" if draft_payload.get("approved") else "noop"
    target_pct = float(decision_payload.get("max_symbol_exposure_pct") or 0.0) if action in {"PROBE", "DIRECT"} else 0.0
    leverage = int(decision_payload.get("leverage") or 0)
    kline = debug.get("kline", {})
    warmup = debug.get("warmup", {})
    score_detail = decision_payload.get("score_detail", {})
    points = score_detail.get("points", {})
    scores = score_detail.get("scores", {})
    weights = score_detail.get("weights", {})
    diagnostics = score_detail.get("diagnostics", {})
    reasons = decision_payload.get("reasons", [])
    reason_text = ",".join(str(item) for item in reasons) if reasons else "-"
    hold_reason = "approved_order_draft" if draft_payload.get("approved") else str(draft_payload.get("reason", "waiting_rule_confirmation"))
    return [
        f"[{symbol}] 决策={action} | 状态={state} | 目标占比={target_pct:.2f} | 当前占比=0.00 | 杠杆(请求/实际)={leverage}x/{leverage}x",
        "   K线预热: "
        f"source={warmup.get('source')} ready={warmup.get('ready')} "
        f"15m={warmup.get('15m')} 30m={warmup.get('30m')} 1h={warmup.get('1h')} 4h={warmup.get('4h')} required_15m={warmup.get('required_15m')}",
        "   K线价格(15m): "
        f"open={fmt(kline.get('open'))} | close={fmt(kline.get('close'))} | change={fmt_pct(kline.get('change_pct'))}",
        "   规则上下文: "
        f"side={context.side}, atr_pct={context.atr_pct:.4f}, stop_pct={fmt_pct(context.stop_pct)}, "
        f"long_flags=overext:{int(context.long_overextension_active)}/wick:{int(context.long_upper_wick_risk_active)}/"
        f"chase:{int(context.long_chase_risk_active)}/lowliq:{int(context.long_low_liquidity_session_active)}/cvdweak:{int(context.long_cvd_weak_active)}",
        render_score_detail_line(decision_payload.get("score"), scores, points, weights, diagnostics),
        "   风险检查: "
        f"liquidity_ratio={decision_payload.get('liquidity_ratio')} | stress={stress.get('action')} "
        f"est_loss={fmt_pct(stress.get('estimated_loss_pct'))} | approved={draft_payload.get('approved')}",
        f"   决策原因: {reason_text}",
        f"   HOLD归因: {hold_reason}, lock=-",
    ]


def render_score_detail_line(
    score: Any,
    scores: Mapping[str, Any],
    points: Mapping[str, Any],
    weights: Mapping[str, Any],
    diagnostics: Mapping[str, Any] | None = None,
) -> str:
    if "trend_ema_context" in weights:
        rr_detail = (diagnostics or {}).get("risk_reward_geometry", {})
        rr_suffix = ""
        if rr_detail:
            rr_suffix = (
                f", rr_net={fmt(rr_detail.get('net_tp1_r'))}"
                f", rr_zero={rr_detail.get('rr_zero_reason') or '-'}"
            )
        return (
            "   评分明细: "
            f"score={score} | "
            f"ema={fmt(scores.get('trend_ema_context'))}->{fmt(points.get('trend_ema_context'))}, "
            f"cvd={fmt(scores.get('flow_cvd_confirmation'))}->{fmt(points.get('flow_cvd_confirmation'))}, "
            f"cci={fmt(scores.get('cci_momentum_quality'))}->{fmt(points.get('cci_momentum_quality'))}, "
            f"pa={fmt(scores.get('price_action_structure'))}->{fmt(points.get('price_action_structure'))}, "
            f"fib={fmt(scores.get('fibonacci_location'))}->{fmt(points.get('fibonacci_location'))}, "
            f"rr={fmt(scores.get('risk_reward_geometry'))}->{fmt(points.get('risk_reward_geometry'))}, "
            f"fib_cap={fmt(scores.get('fib_action_cap'))}"
            f"{rr_suffix}"
        )
    return (
        "   评分明细: "
        f"score={score} | "
        f"direction={fmt(scores.get('direction_1h'))}->{fmt(points.get('direction_1h'))}, "
        f"quality={fmt(scores.get('quality_30m'))}->{fmt(points.get('quality_30m'))}, "
        f"trigger={fmt(scores.get('trigger_15m'))}->{fmt(points.get('trigger_15m'))}, "
        f"cvd={fmt(scores.get('cvd_flow'))}->{fmt(points.get('cvd_flow'))}, "
        f"ema50={fmt(scores.get('ema_50_quality'))}->{fmt(points.get('ema_50_quality'))}"
    )


def render_paper_log(symbol: str, events: Sequence[str]) -> list[str]:
    if not events:
        return [f"   PAPER账本: symbol={symbol}, event=NO_CHANGE"]
    return [f"   PAPER账本: symbol={symbol}, event={event}" for event in events]


def render_scout_micro_log(symbol: str, events: Sequence[str]) -> list[str]:
    if not events:
        return []
    return [f"   SCOUT_MICRO账本: symbol={symbol}, event={event}" for event in events]


def render_mirror_ab_log(symbol: str, events: Sequence[str]) -> list[str]:
    if not events:
        return []
    return [f"   MIRROR_AB账本: symbol={symbol}, event={event}" for event in events]


def warmup_summary(
    warmup_state: Mapping[str, Mapping[str, Sequence[BacktestBar]]],
    symbols: Sequence[str],
    required_15m: int,
) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        histories = warmup_state.get(symbol, {})
        bars_15m = list(histories.get("15m", []))
        summary[symbol] = {
            "15m": len(bars_15m),
            "30m": len(histories.get("30m", [])),
            "1h": len(histories.get("1h", [])),
            "4h": len(histories.get("4h", [])),
            "latest_15m_timestamp": bars_15m[-1].timestamp if bars_15m else None,
            "required_15m": required_15m,
            "ready_15m": len(bars_15m) >= required_15m,
        }
    return summary


def format_warmup_summary(
    warmup_state: Mapping[str, Mapping[str, Sequence[BacktestBar]]],
    symbols: Sequence[str],
    required_15m: int,
) -> str:
    parts = []
    for symbol, item in warmup_summary(warmup_state, symbols, required_15m).items():
        ready = "OK" if item["ready_15m"] else "MISS"
        parts.append(f"{symbol}:15m={item['15m']}/{required_15m},{ready}")
    return "; ".join(parts)


def fmt(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def fmt_pct(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value) * 100:+.2f}%"
    except (TypeError, ValueError):
        return str(value)


def utc_text(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


def write_error(output_dir: Path, text: str) -> None:
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / "errors.log").open("a", encoding="utf-8") as handle:
        handle.write(text)
        handle.write("\n")


if __name__ == "__main__":
    main()
