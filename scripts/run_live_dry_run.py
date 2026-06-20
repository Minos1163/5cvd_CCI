from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
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
from src.observability.paper_trading import PaperTradingLedger
from src.risk.stress_simulator import stress_decision
from src.signals.entry_chain import EntryChainContext, evaluate_entry_chain
from src.signals.entry_chain_config import load_entry_chain_config
from src.signals.entry_chain_features import (
    atr_pct,
    component_scores,
    direction_from_history,
    long_chase_risk_active,
    long_low_liquidity_session_active,
    long_overextension_active,
    long_upper_wick_risk_active,
    quote_volume,
    wick_anomaly,
)


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
COINGECKO_BASE_OVERRIDES = {
    "binancecoin": "BNB",
    "the-open-network": "TON",
}


def main() -> None:
    args = parse_args()
    output_dir = resolve_output_dir(args)
    try:
        run(args, output_dir)
    except Exception:
        write_error(output_dir, traceback.format_exc())
        raise


def run(args: argparse.Namespace, output_dir: Path) -> None:
    config = load_entry_chain_config(args.config)
    symbols, symbol_meta = resolve_runtime_symbols(args, config)
    warmup_state = warmup_symbols(symbols, args, config) if args.market_data_source == "public-binance" else synthetic_warmup_state(symbols, config)
    orders_submitted = 0
    summary = DryRunSummary(target_tier=args.target_tier)
    data_health = "OK"
    cycle = 0
    with DecisionAuditWriter(output_dir) as audit:
        paper = PaperTradingLedger(output_dir)
        while True:
            alignment_lines = wait_for_kline_alignment(args)
            cycle += 1
            cycle_started = time.perf_counter()
            now = int(time.time())
            runtime_lines = render_cycle_header(cycle, now, args, symbols, symbol_meta, warmup_state, config.dry_run_warmup_15m_bars)
            runtime_lines.extend(alignment_lines)
            processed = 0
            for symbol in symbols:
                started = time.perf_counter()
                context, context_health, debug = build_context(symbol, now, args, config, warmup_state.get(symbol))
                if context_health != "OK":
                    data_health = context_health
                decision = evaluate_entry_chain(context, config)
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
                    "total_score": decision_payload.get("score"),
                }
                decision_payload["entry_context"] = debug.get("entry_context", {})
                audit.write_decision(decision_payload)
                summary.record_decision(decision_payload)
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
                runtime_lines.extend(render_symbol_log(symbol, context, decision_payload, draft_payload, stress, debug))
                runtime_lines.extend(render_paper_log(symbol, paper_events))
                processed += 1
            elapsed = time.perf_counter() - cycle_started
            runtime_lines.append(f"本轮扫描完成: processed={processed}/{len(symbols)}, elapsed={elapsed:.2f}s, orders_submitted={orders_submitted}")
            if args.once:
                runtime_lines.append("调度等待: once=true, exit_after_current_cycle")
            elif args.align_to_kline_close:
                next_ts = next_kline_run_timestamp(time.time(), args.kline_interval_seconds, args.post_close_delay_seconds)
                runtime_lines.append(
                    f"调度等待: kline_align=ON, next_review_utc={utc_text(next_ts)}, "
                    f"post_close_delay={args.post_close_delay_seconds:.2f}s"
                )
            else:
                next_ts = int(time.time() + args.interval_seconds)
                runtime_lines.append(
                    f"调度等待: utc_now={utc_text(int(time.time()))}, sleep={args.interval_seconds:.2f}s, next_review_utc={utc_text(next_ts)}"
                )
            write_runtime_log(output_dir, runtime_lines)
            write_health(output_dir, symbols, orders_submitted, data_health, symbol_meta, warmup_state, config.dry_run_warmup_15m_bars)
            write_summary(output_dir / "summary.json", summary, orders_submitted=orders_submitted, data_health=data_health)
            if args.once:
                break
            if not args.align_to_kline_close:
                time.sleep(args.interval_seconds)
    print(json.dumps({"status": "dry_run_completed", "orders_submitted": orders_submitted}, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI300 entry-chain in dry-run mode without exchange mutation.")
    parser.add_argument("--config", default="configs/entry_chain.dry_run.json")
    parser.add_argument("--output-dir")
    parser.add_argument("--log-root", default="reports/dry_run/local")
    parser.add_argument("--log-date")
    parser.add_argument("--symbols")
    parser.add_argument("--interval-seconds", type=float, default=60.0)
    parser.add_argument("--align-to-kline-close", action="store_true")
    parser.add_argument("--kline-interval-seconds", type=int, default=900)
    parser.add_argument("--post-close-delay-seconds", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--target-tier", default="conservative", choices=["conservative", "balanced", "aggressive"])
    parser.add_argument("--stress-move-pct", type=float, default=0.20)
    parser.add_argument("--max-stress-loss-pct", type=float, default=0.25)
    parser.add_argument("--market-data-source", default="synthetic", choices=["synthetic", "public-binance"])
    parser.add_argument("--public-kline-limit", type=int, default=240)
    return parser.parse_args()


def resolve_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        return Path(args.output_dir)
    if args.log_date:
        day = datetime.strptime(args.log_date, "%Y-%m-%d").date()
    else:
        day = datetime.now(UTC).date()
    month = day.strftime("%Y-%m")
    return Path(args.log_root) / month / day.isoformat()


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


def synthetic_context(symbol: str, timestamp: int) -> EntryChainContext:
    return EntryChainContext(
        symbol=symbol,
        timestamp=timestamp,
        side="LONG",
        component_scores={
            "background_4h": 0.8,
            "direction_1h": 0.8,
            "quality_30m": 0.75,
            "trigger_15m": 0.7,
            "cvd_flow": 0.6,
            "volatility_stop": 0.9,
            "liquidity_execution": 1.0,
            "market_regime": 0.8,
        },
        quote_volume_24h=200_000_000.0,
        atr_pct=0.018,
        expected_order_size=1_000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
    )


def build_context(
    symbol: str,
    timestamp: int,
    args: argparse.Namespace,
    config,
    warmup_history: Mapping[str, Sequence[BacktestBar]] | None = None,
) -> tuple[EntryChainContext, str, dict[str, Any]]:
    if args.market_data_source == "synthetic":
        context = synthetic_context(symbol, timestamp)
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
        current_volatility_scale=max(0.1, atr_pct_value / 0.01),
        normal_volatility_scale=1.0,
    )
    return context, public_debug_snapshot(symbol, context, histories, scores, ready=True, required_15m=required_15m)


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
        "long_overextension_active": context.long_overextension_active,
        "long_upper_wick_risk_active": context.long_upper_wick_risk_active,
        "long_chase_risk_active": context.long_chase_risk_active,
        "long_low_liquidity_session_active": context.long_low_liquidity_session_active,
        "long_cvd_weak_active": context.long_cvd_weak_active,
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


def write_runtime_log(output_dir: Path, lines: Sequence[str]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "runtime.out.log").open("a", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line)
            handle.write("\n")
        handle.write("\n")


def render_cycle_header(
    cycle: int,
    timestamp: int,
    args: argparse.Namespace,
    symbols: Sequence[str],
    symbol_meta: Mapping[str, Any],
    warmup_state: Mapping[str, Mapping[str, Sequence[BacktestBar]]],
    required_15m: int,
) -> list[str]:
    return [
        f"=== AI300_DRY_RUN cycle {cycle} @ {utc_text(timestamp)} === [mode={args.market_data_source}, kline_align=ON, tf=900s]",
        "当前权益: equity=10000.00 USDT, available=8000.00 USDT, unrealized=+0.00 USDT",
        f"DRY-RUN安全: exchange_mutation_enabled=False, orders_submitted=0, symbols={len(symbols)}, config={args.config}",
        "交易对宇宙: "
        f"source={symbol_meta.get('source')} rank={symbol_meta.get('rank_start')}-{symbol_meta.get('rank_end')} "
        f"fallback={symbol_meta.get('fallback_used')} error={symbol_meta.get('error')}",
        f"启动预热: {format_warmup_summary(warmup_state, symbols, required_15m)}",
    ]


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
        "   评分明细: "
        f"score={decision_payload.get('score')} | "
        f"direction={fmt(scores.get('direction_1h'))}->{fmt(points.get('direction_1h'))}, "
        f"quality={fmt(scores.get('quality_30m'))}->{fmt(points.get('quality_30m'))}, "
        f"trigger={fmt(scores.get('trigger_15m'))}->{fmt(points.get('trigger_15m'))}, "
        f"cvd={fmt(scores.get('cvd_flow'))}->{fmt(points.get('cvd_flow'))}, "
        f"ema50={fmt(scores.get('ema_50_quality'))}->{fmt(points.get('ema_50_quality'))}",
        "   风险检查: "
        f"liquidity_ratio={decision_payload.get('liquidity_ratio')} | stress={stress.get('action')} "
        f"est_loss={fmt_pct(stress.get('estimated_loss_pct'))} | approved={draft_payload.get('approved')}",
        f"   决策原因: {reason_text}",
        f"   HOLD归因: {hold_reason}, lock=-",
    ]


def render_paper_log(symbol: str, events: Sequence[str]) -> list[str]:
    if not events:
        return [f"   PAPER账本: symbol={symbol}, event=NO_CHANGE"]
    return [f"   PAPER账本: symbol={symbol}, event={event}" for event in events]


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
