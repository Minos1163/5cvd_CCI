from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backtest.engine import BacktestBar, BacktestRequest, run_backtest
from src.signals.entry_chain import EntryChainContext, evaluate_entry_chain
from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config
from src.signals.entry_chain_features import (
    atr_pct,
    completed_bars,
    component_scores,
    direction_from_history,
    long_chase_risk_active,
    long_low_liquidity_session_active,
    long_overextension_active,
    long_upper_wick_risk_active,
    quote_volume,
    wick_anomaly,
)
from src.signals.portfolio_state import PortfolioState


def main() -> None:
    args = parse_args()
    validate_lifecycle_args(args)
    data_dir = Path(args.data_dir)
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    symbols = list(manifest["symbols"])
    bars_by_symbol = {symbol: load_bars(data_dir / symbol / f"{args.timeframe}.csv") for symbol in symbols}
    multi_tf_bars = load_multi_timeframe_bars(data_dir, symbols) if args.strategy == "entry-chain" else {}
    first_ts = min(bars[0].timestamp for bars in bars_by_symbol.values() if bars)
    last_ts = max(bars[-1].timestamp for bars in bars_by_symbol.values() if bars)
    strategy_callback = baseline_momentum_strategy
    strategy_name = "ai300_offline_baseline"
    strategy_version = "offline-baseline-v1"
    if args.strategy == "entry-chain":
        entry_chain_config = (
            load_entry_chain_config(args.entry_chain_config)
            if args.entry_chain_config
            else EntryChainConfig()
        )
        strategy_callback = build_entry_chain_strategy(
            multi_tf_bars,
            args.initial_capital,
            entry_chain_config,
            simulated_hold_bars=args.simulated_hold_bars,
            cooldown_bars=args.cooldown_bars,
        )
        strategy_name = "ai300_deepseek_entry_chain"
        strategy_version = "entry-chain-v1-lite"

    request = BacktestRequest(
        run_id=args.run_id,
        strategy_name=strategy_name,
        strategy_version=strategy_version,
        config_version="local-script-v1",
        data_version=manifest["downloaded_at"],
        symbols=symbols,
        timeframes=[args.timeframe],
        start_time=first_ts,
        end_time=last_ts,
        initial_capital=args.initial_capital,
        fee_model={"fee_bps": args.fee_bps},
        slippage_model={"slippage_bps": args.slippage_bps},
        funding_model={"funding_bps": args.funding_bps},
        fill_model=args.fill_model,
        capital_constraints={"notional_per_trade": args.notional_per_trade},
        risk_constraints={
            "strategy": args.strategy,
            "entry_chain_config": args.entry_chain_config,
            "simulated_hold_bars": args.simulated_hold_bars,
            "cooldown_bars": args.cooldown_bars,
            "exit_model": args.exit_model,
            "atr_stop_mult": args.atr_stop_mult,
            "tp_levels": parse_float_triplet(args.tp_levels),
            "tp_fractions": parse_float_triplet(args.tp_fractions),
            "max_hold_bars": args.max_hold_bars,
            "default_atr_pct": args.default_atr_pct,
            "enable_leverage_simulation": args.enable_leverage_simulation,
            "fixed_leverage": args.fixed_leverage,
            "min_leverage": args.min_leverage,
            "max_leverage": args.max_leverage,
            "maintenance_margin_pct": args.maintenance_margin_pct,
            "adverse_reduce_enabled": args.adverse_reduce_enabled,
            "adverse_reduce_r": args.adverse_reduce_r,
            "adverse_reduce_fraction": args.adverse_reduce_fraction,
            "adverse_volume_spike_mult": args.adverse_volume_spike_mult,
            "adverse_volume_lookback": args.adverse_volume_lookback,
            "time_reduce_enabled": args.time_reduce_enabled,
            "time_reduce_bars": args.time_reduce_bars,
            "time_reduce_min_profit_r": args.time_reduce_min_profit_r,
            "time_reduce_fraction": args.time_reduce_fraction,
            "daily_hard_loss_pct": args.daily_hard_loss_pct,
            "weekly_hard_loss_pct": args.weekly_hard_loss_pct,
        },
        entry_modes=["PROBE", "DIRECT"],
        source="offline_csv",
    )
    result = run_backtest(request, bars_by_symbol, strategy_callback=strategy_callback)
    output_dir = Path(args.output_dir) / request.run_id
    write_artifacts(output_dir, result)
    print(json.dumps(summary(result, output_dir), ensure_ascii=False, indent=2))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run first offline backtest from downloaded CSV data.")
    parser.add_argument("--data-dir", default="data/raw/binance_futures/latest_30d")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--run-id", default="latest_30d_round1")
    parser.add_argument("--output-dir", default="reports/backtests")
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument("--notional-per-trade", type=float, default=1_000.0)
    parser.add_argument("--fee-bps", type=float, default=5.0)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    parser.add_argument("--funding-bps", type=float, default=0.0)
    parser.add_argument("--fill-model", default="NEXT_BAR_OPEN", choices=["NEXT_BAR_OPEN", "TRIGGER_PRICE", "CONSERVATIVE_LIMIT_FILL"])
    parser.add_argument("--strategy", default="baseline", choices=["baseline", "entry-chain"])
    parser.add_argument("--entry-chain-config", default=None)
    parser.add_argument("--simulated-hold-bars", type=int, default=2)
    parser.add_argument("--cooldown-bars", type=int, default=16)
    parser.add_argument("--exit-model", default="synthetic", choices=["synthetic", "atr_tp"])
    parser.add_argument("--atr-stop-mult", type=float, default=1.5)
    parser.add_argument("--tp-levels", default="1,2,3")
    parser.add_argument("--tp-fractions", default="0.4,0.35,0.25")
    parser.add_argument("--max-hold-bars", type=int, default=16)
    parser.add_argument("--default-atr-pct", type=float, default=0.010)
    parser.add_argument("--enable-leverage-simulation", action="store_true")
    parser.add_argument("--fixed-leverage", type=float, default=None)
    parser.add_argument("--min-leverage", type=float, default=1.0)
    parser.add_argument("--max-leverage", type=float, default=5.0)
    parser.add_argument("--maintenance-margin-pct", type=float, default=0.005)
    parser.add_argument("--adverse-reduce-enabled", action="store_true")
    parser.add_argument("--adverse-reduce-r", type=float, default=0.6)
    parser.add_argument("--adverse-reduce-fraction", type=float, default=0.5)
    parser.add_argument("--adverse-volume-spike-mult", type=float, default=1.5)
    parser.add_argument("--adverse-volume-lookback", type=int, default=20)
    parser.add_argument("--time-reduce-enabled", action="store_true")
    parser.add_argument("--time-reduce-bars", type=int, default=12)
    parser.add_argument("--time-reduce-min-profit-r", type=float, default=0.3)
    parser.add_argument("--time-reduce-fraction", type=float, default=0.5)
    parser.add_argument("--daily-hard-loss-pct", type=float, default=0.0)
    parser.add_argument("--weekly-hard-loss-pct", type=float, default=0.0)
    return parser.parse_args()


def parse_float_triplet(value: str) -> tuple[float, float, float]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("expected exactly three comma-separated numbers")
    return (float(parts[0]), float(parts[1]), float(parts[2]))


def validate_lifecycle_args(args: argparse.Namespace) -> None:
    validate_leverage_args(args)
    if args.exit_model != "atr_tp":
        return
    levels = parse_float_triplet(args.tp_levels)
    fractions = parse_float_triplet(args.tp_fractions)
    if len(levels) != len(fractions):
        raise ValueError("--tp-levels and --tp-fractions must have the same length")
    if any(level <= 0 for level in levels):
        raise ValueError("--tp-levels values must be positive")
    fraction_sum = sum(fractions)
    if abs(fraction_sum - 1.0) > 1e-4:
        raise ValueError(f"--tp-fractions must sum to 1.0, got {fraction_sum:.6f}")
    if args.atr_stop_mult <= 0 or args.atr_stop_mult > 5.0:
        raise ValueError("--atr-stop-mult must be in the range (0, 5.0]")
    if args.default_atr_pct <= 0:
        raise ValueError("--default-atr-pct must be positive")
    if args.max_hold_bars <= 0:
        raise ValueError("--max-hold-bars must be positive")


def validate_leverage_args(args: argparse.Namespace) -> None:
    if args.fixed_leverage is not None and args.fixed_leverage <= 0:
        raise ValueError("--fixed-leverage must be positive")
    if args.min_leverage <= 0 or args.max_leverage < args.min_leverage:
        raise ValueError("--min-leverage/--max-leverage range is invalid")
    if args.max_leverage > 5.0:
        raise ValueError("--max-leverage must be <= 5.0 for this research lane")
    if args.maintenance_margin_pct < 0:
        raise ValueError("--maintenance-margin-pct must be non-negative")
    for name in ("adverse_reduce_fraction", "time_reduce_fraction"):
        value = float(getattr(args, name))
        if value <= 0 or value > 1:
            raise ValueError(f"--{name.replace('_', '-')} must be in the range (0, 1]")
    if args.adverse_reduce_r <= 0:
        raise ValueError("--adverse-reduce-r must be positive")
    if args.adverse_volume_spike_mult <= 0:
        raise ValueError("--adverse-volume-spike-mult must be positive")
    if args.adverse_volume_lookback <= 0:
        raise ValueError("--adverse-volume-lookback must be positive")
    if args.time_reduce_bars <= 0:
        raise ValueError("--time-reduce-bars must be positive")
    if args.daily_hard_loss_pct < 0 or args.weekly_hard_loss_pct < 0:
        raise ValueError("--daily-hard-loss-pct and --weekly-hard-loss-pct must be non-negative")


def load_bars(path: Path) -> list[BacktestBar]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            BacktestBar(
                symbol=row["symbol"],
                timestamp=int(row["open_time"]) // 1000,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            for row in reader
        ]


def load_multi_timeframe_bars(data_dir: Path, symbols: Sequence[str]) -> dict[str, dict[str, list[BacktestBar]]]:
    payload: dict[str, dict[str, list[BacktestBar]]] = {}
    for symbol in symbols:
        payload[symbol] = {}
        for timeframe in ("15m", "30m", "1h", "4h"):
            path = data_dir / symbol / f"{timeframe}.csv"
            if path.exists():
                payload[symbol][timeframe] = load_bars(path)
    return payload


def baseline_momentum_strategy(
    request: BacktestRequest,
    symbol: str,
    current_bar: BacktestBar,
    context: Mapping[str, Any],
) -> Mapping[str, Any] | None:
    previous_bar = context.get("previous_bar")
    if previous_bar is None:
        return {"signal_type": "NO_TRADE", "signal_side": "NONE", "entry_mode": "NONE", "reason": "warmup"}
    previous_close = float(previous_bar.close)
    if previous_close <= 0:
        return {"signal_type": "NO_TRADE", "signal_side": "NONE", "entry_mode": "NONE", "reason": "invalid_previous_close"}
    change_pct = (current_bar.close - previous_close) / previous_close
    if abs(change_pct) < 0.0015:
        return {"signal_type": "WAIT", "signal_side": "NONE", "entry_mode": "NONE", "reason": "momentum_below_threshold"}
    side = "LONG" if change_pct > 0 else "SHORT"
    entry_mode = "DIRECT" if abs(change_pct) >= 0.004 else "PROBE"
    notional = float(request.capital_constraints.get("notional_per_trade", 1_000.0))
    if entry_mode == "PROBE":
        notional *= 0.25
    return {
        "signal_type": side,
        "signal_side": side,
        "entry_mode": entry_mode,
        "risk_allowed": True,
        "notional": notional,
        "reason": f"baseline_15m_momentum_{change_pct:.4f}",
    }


def build_entry_chain_strategy(
    multi_tf_bars: Mapping[str, Mapping[str, Sequence[BacktestBar]]],
    initial_capital: float,
    config: EntryChainConfig | None = None,
    *,
    simulated_hold_bars: int = 2,
    cooldown_bars: int = 16,
):
    state = PortfolioState()
    cfg = config or EntryChainConfig()
    hold_seconds = max(1, simulated_hold_bars) * 15 * 60
    cooldown_seconds = max(0, cooldown_bars) * 15 * 60

    def strategy(
        request: BacktestRequest,
        symbol: str,
        current_bar: BacktestBar,
        context: Mapping[str, Any],
    ) -> Mapping[str, Any] | None:
        state.expire_positions(current_bar.timestamp)
        previous_bar = context.get("previous_bar")
        if previous_bar is None:
            return _no_trade("warmup")
        histories = multi_tf_bars.get(symbol, {})
        completed = {
            timeframe: completed_bars(bars, current_bar.timestamp)
            for timeframe, bars in histories.items()
        }
        if len(completed.get("15m", [])) < 20 or len(completed.get("1h", [])) < 4:
            return _no_trade("entry_chain_warmup")
        side = direction_from_history(completed.get("1h", []))
        if side == "NONE":
            return _no_trade("entry_chain_1h_no_direction")
        account_equity = max(float(context.get("equity", initial_capital)), 1.0)
        expected_order_size = max(float(request.capital_constraints.get("notional_per_trade", 1_000.0)), 1.0)
        atr_pct_value = atr_pct(completed["15m"][-20:])
        quote_volume_24h = quote_volume(completed["15m"][-96:])
        scores = component_scores(
            side,
            completed,
            atr_pct_value,
            use_ema_architecture=cfg.use_ema_architecture,
            ema200_gate_mode=cfg.ema200_gate_mode,
        )
        bars_15m = completed["15m"]
        entry_context = EntryChainContext(
            symbol=symbol,
            timestamp=current_bar.timestamp,
            side=side,
            component_scores=scores,
            quote_volume_24h=quote_volume_24h,
            atr_pct=atr_pct_value,
            expected_order_size=expected_order_size,
            account_equity=account_equity,
            available_margin=account_equity * 0.8,
            wick_anomaly_active=wick_anomaly(current_bar, previous_bar),
            active_symbols=state.active_symbol_count(),
            portfolio_trades_today=state.portfolio_trades_today(current_bar.timestamp),
            symbol_trades_today=state.symbol_trades_today(symbol, current_bar.timestamp),
            cooldown_until_ts=state.cooldown_until(symbol),
            symbol_exposure_pct=state.symbol_exposure_pct(symbol, account_equity),
            total_exposure_pct=state.total_exposure_pct(account_equity),
            same_direction_exposure_pct=state.same_direction_exposure_pct(side, account_equity),
            rolling_sharpe_20=state.rolling_sharpe_20(),
            stop_pct=max(0.005, min(0.04, atr_pct_value * 1.5)),
            long_overextension_active=long_overextension_active(bars_15m),
            long_upper_wick_risk_active=long_upper_wick_risk_active(bars_15m),
            long_chase_risk_active=long_chase_risk_active(bars_15m, atr_pct_value),
            long_low_liquidity_session_active=long_low_liquidity_session_active(current_bar.timestamp, bars_15m),
            long_cvd_weak_active=scores.get("cvd_flow", 0.0) < cfg.long_cvd_weak_threshold,
        )
        decision = evaluate_entry_chain(entry_context, cfg)
        if decision.action not in {"PROBE", "DIRECT"}:
            return {
                "signal_type": "NO_TRADE" if decision.action == "NO_TRADE" else "WAIT",
                "signal_side": "NONE",
                "entry_mode": "NONE",
                "reason": "entry_chain_" + "|".join(decision.reasons or (decision.action,)),
                "entry_chain": decision.to_dict(),
            }
        state.record_entry(
            symbol,
            current_bar.timestamp,
            side,
            decision.notional_hint,
            expires_at_ts=current_bar.timestamp + hold_seconds,
        )
        if cooldown_seconds > 0:
            state.start_cooldown(symbol, current_bar.timestamp + cooldown_seconds)
        return {
            "signal_type": side,
            "signal_side": side,
            "entry_mode": decision.action,
            "risk_allowed": decision.risk_allowed,
            "notional": decision.notional_hint,
            "leverage": decision.leverage,
            "atr_pct": atr_pct_value,
            "reason": f"entry_chain_score_{decision.score:.2f}",
            "entry_chain": decision.to_dict(),
        }

    return strategy


def _no_trade(reason: str) -> Mapping[str, Any]:
    return {"signal_type": "NO_TRADE", "signal_side": "NONE", "entry_mode": "NONE", "reason": reason}


def write_artifacts(output_dir: Path, result: Any) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = to_plain(result)
    (output_dir / "backtest_result.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(output_dir / "trade_log.csv", payload["trades"])
    write_csv(output_dir / "equity_curve.csv", payload["equity_curve"])
    write_csv(output_dir / "drawdown_curve.csv", payload["drawdown_curve"])
    write_csv(output_dir / "state_transitions.csv", payload["state_transitions"])
    write_csv(output_dir / "risk_events.csv", payload["risk_events"])
    write_csv(output_dir / "signal_events.csv", payload["signal_events"])
    (output_dir / "performance_summary.md").write_text(render_summary_md(payload), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def render_summary_md(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Offline Backtest Summary",
            "",
            f"- run_id: {payload['run_id']}",
            f"- status: {payload['status']}",
            f"- final_equity: {payload['final_equity']:.4f}",
            f"- total_return: {payload['total_return']:.6f}",
            f"- annual_return: {payload['annual_return']:.6f}",
            f"- max_drawdown: {payload['max_drawdown']:.6f}",
            f"- win_rate: {payload['win_rate']}",
            f"- profit_factor: {payload['profit_factor']}",
            f"- sharpe: {payload['sharpe']}",
            f"- sortino: {payload['sortino']}",
            f"- expectancy: {payload['expectancy']}",
            f"- trade_count: {payload['trade_count']}",
            f"- degraded_assumptions: {payload['degraded_assumptions']}",
            "",
        ]
    )


def summary(result: Any, output_dir: Path) -> dict[str, Any]:
    payload = to_plain(result)
    return {
        "run_id": payload["run_id"],
        "status": payload["status"],
        "symbols": list(payload["symbol_breakdown"].keys()),
        "final_equity": payload["final_equity"],
        "total_return": payload["total_return"],
        "max_drawdown": payload["max_drawdown"],
        "win_rate": payload["win_rate"],
        "profit_factor": payload["profit_factor"],
        "sharpe": payload["sharpe"],
        "sortino": payload["sortino"],
        "expectancy": payload["expectancy"],
        "trade_count": payload["trade_count"],
        "report_dir": str(output_dir),
    }


def to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return to_plain(asdict(value))
    if isinstance(value, dict):
        return {key: to_plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_plain(item) for item in value]
    return value


if __name__ == "__main__":
    main()
