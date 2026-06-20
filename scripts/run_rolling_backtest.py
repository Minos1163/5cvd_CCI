from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_offline_backtest import (
    build_entry_chain_strategy,
    load_bars,
    load_multi_timeframe_bars,
    to_plain,
    write_artifacts,
)
from src.backtest.engine import BacktestBar, BacktestRequest, run_backtest
from src.signals.entry_chain_config import load_entry_chain_config


SECONDS_PER_DAY = 86400
DEFAULT_V5_CONFIG = "configs/entry_chain.dry_run_v5_symbol_bucket_long_context.json"


def coverage_days(start_ts: int, end_ts: int) -> float:
    return max(0, end_ts - start_ts) / SECONDS_PER_DAY


def generate_windows(start_ts: int, end_ts: int, *, window_days: int, step_days: int) -> list[tuple[int, int]]:
    window_seconds = window_days * SECONDS_PER_DAY
    step_seconds = step_days * SECONDS_PER_DAY
    windows: list[tuple[int, int]] = []
    current = start_ts
    while current + window_seconds <= end_ts:
        windows.append((current, current + window_seconds))
        current += step_seconds
    return windows


def max_consecutive_negative(values: list[float]) -> int:
    longest = 0
    current = 0
    for value in values:
        if value < 0:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def summarize_windows(rows: list[dict[str, float]]) -> dict[str, float | int | None]:
    if not rows:
        return {
            "window_count": 0,
            "median_return": None,
            "iqr_return": None,
            "worst_return": None,
            "best_return": None,
            "negative_window_count": 0,
            "max_consecutive_negative_windows": 0,
            "median_win_rate": None,
            "worst_win_rate": None,
            "median_max_drawdown": None,
            "max_drawdown": None,
            "median_sharpe": None,
        }
    returns = [float(row["total_return"]) for row in rows]
    win_rates = [float(row["win_rate"]) for row in rows if row.get("win_rate") is not None]
    drawdowns = [float(row["max_drawdown"]) for row in rows if row.get("max_drawdown") is not None]
    sharpes = [float(row["sharpe"]) for row in rows if row.get("sharpe") is not None]
    return {
        "window_count": len(rows),
        "median_return": median(returns),
        "iqr_return": _percentile(returns, 75) - _percentile(returns, 25),
        "worst_return": min(returns),
        "best_return": max(returns),
        "negative_window_count": sum(1 for value in returns if value < 0),
        "max_consecutive_negative_windows": max_consecutive_negative(returns),
        "median_win_rate": median(win_rates) if win_rates else None,
        "worst_win_rate": min(win_rates) if win_rates else None,
        "median_max_drawdown": median(drawdowns) if drawdowns else None,
        "max_drawdown": max(drawdowns) if drawdowns else None,
        "median_sharpe": median(sharpes) if sharpes else None,
    }


def load_manifest(data_dir: Path) -> dict[str, object]:
    return json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))


def manifest_coverage_seconds(manifest: Mapping[str, object]) -> tuple[int, int]:
    return int(manifest["start_time_ms"]) // 1000, int(manifest["end_time_ms"]) // 1000


def validate_coverage(*, available_days: float, required_days: int) -> dict[str, object]:
    rounded = round(available_days, 2)
    return {
        "ok": rounded >= required_days,
        "available_days": rounded,
        "required_days": required_days,
    }


def filter_bars_by_window(bars: Sequence[BacktestBar], start_ts: int, end_ts: int) -> list[BacktestBar]:
    return [bar for bar in bars if start_ts <= bar.timestamp <= end_ts]


def main() -> int:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_root = Path(args.output_dir) / args.run_id
    output_root.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(data_dir)
    coverage_start, coverage_end = manifest_coverage_seconds(manifest)
    available_days = coverage_days(coverage_start, coverage_end)
    coverage = validate_coverage(available_days=available_days, required_days=args.required_days)
    if not coverage["ok"] and not args.allow_short_coverage:
        summary = {
            "run_id": args.run_id,
            "status": "insufficient_coverage",
            "candidate": args.candidate,
            **coverage,
        }
        write_json(output_root / "rolling_summary.json", summary)
        (output_root / "rolling_summary.md").write_text(render_summary_md(summary, []), encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 2

    windows = generate_windows(
        coverage_start,
        coverage_end,
        window_days=args.window_days,
        step_days=args.step_days,
    )
    symbols = list(manifest["symbols"])
    bars_by_symbol = {symbol: load_bars(data_dir / symbol / f"{args.timeframe}.csv") for symbol in symbols}
    multi_tf_bars = load_multi_timeframe_bars(data_dir, symbols)
    rows: list[dict[str, Any]] = []

    for index, (start_ts, end_ts) in enumerate(windows, start=1):
        window_id = f"w{index:03d}_{_date_id(start_ts)}_{_date_id(end_ts)}"
        result = run_window(
            args,
            manifest,
            symbols,
            bars_by_symbol,
            multi_tf_bars,
            window_id,
            start_ts,
            end_ts,
        )
        window_output = output_root / window_id
        write_artifacts(window_output, result)
        rows.append(window_row(window_id, start_ts, end_ts, result))

    write_csv(output_root / "rolling_windows.csv", rows)
    metric_rows = [
        {
            "total_return": float(row["total_return"]),
            "win_rate": row["win_rate"],
            "max_drawdown": row["max_drawdown"],
            "sharpe": row["sharpe"],
        }
        for row in rows
    ]
    summary = {
        "run_id": args.run_id,
        "status": "completed" if rows else "no_windows",
        "candidate": args.candidate,
        **coverage,
        **summarize_windows(metric_rows),
    }
    write_json(output_root / "rolling_summary.json", summary)
    (output_root / "rolling_summary.md").write_text(render_summary_md(summary, rows), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if rows else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run rolling 30D robustness backtests.")
    parser.add_argument("--data-dir", default="data/raw/binance_futures/latest_30d")
    parser.add_argument("--output-dir", default="reports/backtests")
    parser.add_argument("--run-id", default="v8_rolling")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--step-days", type=int, default=7)
    parser.add_argument("--required-days", type=int, default=365)
    parser.add_argument("--candidate", choices=["v6_dynamic", "v7_time_reduce"], default="v6_dynamic")
    parser.add_argument("--allow-short-coverage", action="store_true")
    return parser.parse_args()


def run_window(
    args: argparse.Namespace,
    manifest: Mapping[str, Any],
    symbols: Sequence[str],
    bars_by_symbol: Mapping[str, Sequence[BacktestBar]],
    multi_tf_bars: Mapping[str, Mapping[str, Sequence[BacktestBar]]],
    window_id: str,
    start_ts: int,
    end_ts: int,
):
    window_bars = {
        symbol: filter_bars_by_window(bars_by_symbol[symbol], start_ts, end_ts)
        for symbol in symbols
    }
    window_multi_tf = {
        symbol: {
            timeframe: filter_bars_by_window(bars, start_ts, end_ts)
            for timeframe, bars in frames.items()
        }
        for symbol, frames in multi_tf_bars.items()
    }
    missing = [symbol for symbol, bars in window_bars.items() if len(bars) < 64]
    if missing:
        return empty_rejected_result(args, window_id, manifest, symbols, start_ts, end_ts, missing)

    strategy = build_entry_chain_strategy(
        window_multi_tf,
        10_000.0,
        load_entry_chain_config(DEFAULT_V5_CONFIG),
        simulated_hold_bars=2,
        cooldown_bars=8,
    )
    request = BacktestRequest(
        run_id=f"{args.run_id}_{window_id}",
        strategy_name="ai300_deepseek_entry_chain",
        strategy_version="entry-chain-v1-lite",
        config_version="v8-rolling-v1",
        data_version=str(manifest.get("downloaded_at", "unknown")),
        symbols=list(symbols),
        timeframes=[args.timeframe],
        start_time=start_ts,
        end_time=end_ts,
        initial_capital=10_000.0,
        fee_model={"fee_bps": 5.0},
        slippage_model={"slippage_bps": 5.0},
        funding_model={"funding_bps": 0.0},
        fill_model="NEXT_BAR_OPEN",
        capital_constraints={"notional_per_trade": 1_000.0},
        risk_constraints=candidate_risk_constraints(args.candidate),
        entry_modes=["PROBE", "DIRECT"],
        source="offline_csv_rolling_window",
    )
    return run_backtest(request, window_bars, strategy_callback=strategy)


def candidate_risk_constraints(candidate: str) -> dict[str, Any]:
    return {
        "strategy": "entry-chain",
        "entry_chain_config": DEFAULT_V5_CONFIG,
        "simulated_hold_bars": 2,
        "cooldown_bars": 8,
        "exit_model": "atr_tp",
        "atr_stop_mult": 1.5,
        "tp_levels": (1.0, 2.0, 3.0),
        "tp_fractions": (0.4, 0.35, 0.25),
        "max_hold_bars": 32,
        "default_atr_pct": 0.010,
        "enable_leverage_simulation": True,
        "fixed_leverage": None,
        "min_leverage": 3.0,
        "max_leverage": 5.0,
        "maintenance_margin_pct": 0.005,
        "adverse_reduce_enabled": False,
        "adverse_reduce_r": 0.6,
        "adverse_reduce_fraction": 0.5,
        "adverse_volume_spike_mult": 1.5,
        "adverse_volume_lookback": 20,
        "time_reduce_enabled": candidate == "v7_time_reduce",
        "time_reduce_bars": 12,
        "time_reduce_min_profit_r": 0.3,
        "time_reduce_fraction": 0.5,
        "daily_hard_loss_pct": 0.0,
        "weekly_hard_loss_pct": 0.0,
    }


def window_row(window_id: str, start_ts: int, end_ts: int, result: Any) -> dict[str, Any]:
    payload = to_plain(result)
    return {
        "window_id": window_id,
        "start_ts": start_ts,
        "end_ts": end_ts,
        "total_return": payload["total_return"],
        "win_rate": payload["win_rate"],
        "max_drawdown": payload["max_drawdown"],
        "profit_factor": payload["profit_factor"],
        "sharpe": payload["sharpe"],
        "sortino": payload["sortino"],
        "expectancy": payload["expectancy"],
        "trade_count": payload["trade_count"],
        "margin_call_proxy_count": sum(1 for trade in payload["trades"] if trade.get("margin_call_proxy")),
    }


def empty_rejected_result(
    args: argparse.Namespace,
    window_id: str,
    manifest: Mapping[str, Any],
    symbols: Sequence[str],
    start_ts: int,
    end_ts: int,
    missing: Sequence[str],
):
    request = BacktestRequest(
        run_id=f"{args.run_id}_{window_id}",
        strategy_name="ai300_deepseek_entry_chain",
        strategy_version="entry-chain-v1-lite",
        config_version="v8-rolling-v1",
        data_version=str(manifest.get("downloaded_at", "unknown")),
        symbols=list(symbols),
        timeframes=[args.timeframe],
        start_time=start_ts,
        end_time=end_ts,
        initial_capital=10_000.0,
        risk_constraints={"missing_symbols": list(missing)},
    )
    return run_backtest(request, {}, strategy_callback=None)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def render_summary_md(summary: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> str:
    lines = [
        "# Rolling Backtest Summary",
        "",
        f"- run_id: {summary['run_id']}",
        f"- status: {summary['status']}",
        f"- candidate: {summary['candidate']}",
        f"- available_days: {summary['available_days']}",
        f"- required_days: {summary['required_days']}",
        f"- window_count: {summary.get('window_count', 0)}",
        f"- median_return: {summary.get('median_return')}",
        f"- iqr_return: {summary.get('iqr_return')}",
        f"- worst_return: {summary.get('worst_return')}",
        f"- best_return: {summary.get('best_return')}",
        f"- median_win_rate: {summary.get('median_win_rate')}",
        f"- worst_win_rate: {summary.get('worst_win_rate')}",
        f"- max_drawdown: {summary.get('max_drawdown')}",
        f"- median_sharpe: {summary.get('median_sharpe')}",
        "",
    ]
    if rows:
        lines.extend(["## Windows", ""])
        for row in rows:
            lines.append(
                f"- {row['window_id']}: return={row['total_return']}, "
                f"win_rate={row['win_rate']}, trades={row['trade_count']}, "
                f"max_dd={row['max_drawdown']}"
            )
    return "\n".join(lines) + "\n"


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * percentile / 100
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _date_id(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y%m%d")


if __name__ == "__main__":
    raise SystemExit(main())
