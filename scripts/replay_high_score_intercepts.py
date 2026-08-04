from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from statistics import mean
from typing import Any, Callable, Iterable


TP_LEVELS = (1.2, 2.0, 3.0)
TP_FRACTIONS = (0.40, 0.35, 0.25)
BAR_ORDER_ASSUMPTIONS = {"stop_first", "tp_first"}


@dataclass(frozen=True)
class DecisionRow:
    day: str
    timestamp: int
    symbol: str
    side: str
    action: str
    score: float
    reasons: tuple[str, ...]
    close: float
    high: float
    low: float
    stop_pct: float
    component_points: dict[str, float]


@dataclass(frozen=True)
class ReplayResult:
    day: str
    timestamp: int
    symbol: str
    side: str
    action: str
    score: float
    primary_reason: str
    reasons: tuple[str, ...]
    entry: float
    stop_pct: float
    horizon_bars: int
    bars_seen: int
    mfe_r: float
    mae_r: float
    final_r: float
    blended_final_r: float
    max_tp_hit: int
    stop_hit: bool
    first_terminal: str
    component_points: dict[str, float]


def date_range(start: str, end: str) -> Iterable[str]:
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    while current <= final:
        yield current.isoformat()
        current += timedelta(days=1)


def decision_path(log_root: Path, day: str) -> Path:
    return log_root / day[:7] / day / "decisions.jsonl"


def load_decision_rows(log_root: Path, start: str, end: str) -> list[DecisionRow]:
    rows: list[DecisionRow] = []
    for day in date_range(start, end):
        path = decision_path(log_root, day)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            row = parse_decision(day, payload)
            if row is not None:
                rows.append(row)
    return sorted(rows, key=lambda item: (item.timestamp, item.symbol))


def parse_decision(day: str, payload: dict[str, Any]) -> DecisionRow | None:
    kline = payload.get("kline") if isinstance(payload.get("kline"), dict) else {}
    context = payload.get("entry_context") if isinstance(payload.get("entry_context"), dict) else {}
    close = _float(kline.get("close"))
    high = _float(kline.get("high"))
    low = _float(kline.get("low"))
    timestamp = _int(kline.get("timestamp") or payload.get("timestamp"))
    symbol = str(payload.get("symbol") or "").strip().upper()
    side = str(context.get("side") or payload.get("side") or "").strip().upper()
    if not symbol or side not in {"LONG", "SHORT"} or close <= 0 or high <= 0 or low <= 0 or timestamp <= 0:
        return None
    reasons = payload.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    component_points = payload.get("component_points")
    if not isinstance(component_points, dict):
        component_points = {}
    return DecisionRow(
        day=day,
        timestamp=timestamp,
        symbol=symbol,
        side=side,
        action=str(payload.get("action") or "").strip().upper(),
        score=_float(payload.get("score")),
        reasons=tuple(str(item) for item in reasons),
        close=close,
        high=high,
        low=low,
        stop_pct=max(0.0001, _float(context.get("stop_pct"), default=0.01)),
        component_points={str(key): _float(value) for key, value in component_points.items()},
    )


def select_intercepts(
    rows: list[DecisionRow],
    min_score: float,
    include_reasons: tuple[str, ...] = (),
) -> list[DecisionRow]:
    return [
        row
        for row in rows
        if (row.score >= min_score or any(reason in row.reasons for reason in include_reasons))
        and row.action not in {"PROBE", "DIRECT"}
        and primary_reason(row.reasons)
    ]


def group_future_rows(rows: list[DecisionRow]) -> dict[str, list[DecisionRow]]:
    grouped: dict[str, list[DecisionRow]] = defaultdict(list)
    for row in rows:
        grouped[row.symbol].append(row)
    return {symbol: sorted(items, key=lambda item: item.timestamp) for symbol, items in grouped.items()}


def replay_intercept(
    row: DecisionRow,
    future_rows: list[DecisionRow],
    horizon_bars: int,
    bar_order_assumption: str = "stop_first",
) -> ReplayResult | None:
    if bar_order_assumption not in BAR_ORDER_ASSUMPTIONS:
        raise ValueError(f"bar_order_assumption must be one of {sorted(BAR_ORDER_ASSUMPTIONS)}")
    future = [item for item in future_rows if item.timestamp > row.timestamp][:horizon_bars]
    if not future:
        return None
    risk = row.close * row.stop_pct
    if risk <= 0:
        return None

    mfe = 0.0
    mae = 0.0
    final_r = 0.0
    max_tp_hit = 0
    stop_hit = False
    first_terminal = "HORIZON_END"
    remaining_fraction = 1.0
    blended_final_r = 0.0
    consumed_tps: set[int] = set()

    for bar in future:
        if row.side == "LONG":
            favorable = (bar.high - row.close) / risk
            adverse = (row.close - bar.low) / risk
            close_r = (bar.close - row.close) / risk
            hit_stop = bar.low <= row.close - risk
        else:
            favorable = (row.close - bar.low) / risk
            adverse = (bar.high - row.close) / risk
            close_r = (row.close - bar.close) / risk
            hit_stop = bar.high >= row.close + risk

        mfe = max(mfe, favorable)
        mae = max(mae, adverse)
        final_r = close_r
        tp_hits = [
            index
            for index, level in enumerate(TP_LEVELS)
            if index not in consumed_tps and favorable >= level
        ]
        if hit_stop and first_terminal == "HORIZON_END":
            if bar_order_assumption == "stop_first" or not tp_hits:
                stop_hit = True
                first_terminal = "INITIAL_STOP_HIT"
                final_r = -1.0
                blended_final_r += remaining_fraction * -1.0
                remaining_fraction = 0.0
                break
            for index in tp_hits:
                fraction = min(remaining_fraction, TP_FRACTIONS[index])
                blended_final_r += fraction * TP_LEVELS[index]
                remaining_fraction = round(max(0.0, remaining_fraction - fraction), 10)
                consumed_tps.add(index)
                max_tp_hit = max(max_tp_hit, index + 1)
            stop_hit = True
            first_terminal = "TP_THEN_INITIAL_STOP_HIT"
            final_r = -1.0
            if remaining_fraction > 0:
                blended_final_r += remaining_fraction * -1.0
                remaining_fraction = 0.0
            break
        for index in tp_hits:
            fraction = min(remaining_fraction, TP_FRACTIONS[index])
            blended_final_r += fraction * TP_LEVELS[index]
            remaining_fraction = round(max(0.0, remaining_fraction - fraction), 10)
            consumed_tps.add(index)
            max_tp_hit = max(max_tp_hit, index + 1)
        if remaining_fraction <= 0:
            first_terminal = "TP3_FILLED"
            final_r = TP_LEVELS[-1]
            break

    if max_tp_hit > 0 and first_terminal == "HORIZON_END":
        first_terminal = f"TP{max_tp_hit}_TOUCHED"
    if remaining_fraction > 0 and first_terminal != "INITIAL_STOP_HIT":
        blended_final_r += remaining_fraction * final_r

    return ReplayResult(
        day=row.day,
        timestamp=row.timestamp,
        symbol=row.symbol,
        side=row.side,
        action=row.action,
        score=row.score,
        primary_reason=primary_reason(row.reasons),
        reasons=row.reasons,
        entry=row.close,
        stop_pct=row.stop_pct,
        horizon_bars=horizon_bars,
        bars_seen=len(future),
        mfe_r=round(mfe, 4),
        mae_r=round(mae, 4),
        final_r=round(final_r, 4),
        blended_final_r=round(blended_final_r, 4),
        max_tp_hit=max_tp_hit,
        stop_hit=stop_hit,
        first_terminal=first_terminal,
        component_points=dict(row.component_points),
    )


def primary_reason(reasons: tuple[str, ...]) -> str:
    return next((reason for reason in reasons if reason != "FIB_PA_ARCHITECTURE_WEIGHTS"), "")


def replay_all(
    rows: list[DecisionRow],
    min_score: float,
    horizon_bars: int,
    include_reasons: tuple[str, ...] = (),
    bar_order_assumption: str = "stop_first",
) -> list[ReplayResult]:
    grouped = group_future_rows(rows)
    results: list[ReplayResult] = []
    for row in select_intercepts(rows, min_score, include_reasons):
        result = replay_intercept(row, grouped.get(row.symbol, []), horizon_bars, bar_order_assumption)
        if result is not None:
            results.append(result)
    return results


def summarize_results(results: list[ReplayResult]) -> dict[str, Any]:
    return {
        "total": len(results),
        "overall": summarize_bucket(results),
        "by_primary_reason": summarize_group(results, lambda item: item.primary_reason),
        "by_symbol": summarize_group(results, lambda item: item.symbol),
        "by_side": summarize_group(results, lambda item: item.side),
    }


def summarize_group(results: list[ReplayResult], key_fn: Callable[[ReplayResult], str]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[ReplayResult]] = defaultdict(list)
    for item in results:
        grouped[str(key_fn(item))].append(item)
    return {key: summarize_bucket(items) for key, items in sorted(grouped.items())}


def summarize_bucket(items: list[ReplayResult]) -> dict[str, Any]:
    if not items:
        return {"count": 0}
    tp1 = [item for item in items if item.max_tp_hit >= 1]
    tp2 = [item for item in items if item.max_tp_hit >= 2]
    tp3 = [item for item in items if item.max_tp_hit >= 3]
    stopped = [item for item in items if item.stop_hit]
    return {
        "count": len(items),
        "avg_mfe_r": round(mean(item.mfe_r for item in items), 4),
        "avg_mae_r": round(mean(item.mae_r for item in items), 4),
        "avg_final_r": round(mean(item.final_r for item in items), 4),
        "avg_blended_final_r": round(mean(item.blended_final_r for item in items), 4),
        "tp1_touch_rate": round(len(tp1) / len(items), 4),
        "tp2_touch_rate": round(len(tp2) / len(items), 4),
        "tp3_touch_rate": round(len(tp3) / len(items), 4),
        "stop_hit_rate": round(len(stopped) / len(items), 4),
        "false_negative_rate_tp2": round(len(tp2) / len(items), 4),
    }


def write_outputs(
    results: list[ReplayResult],
    output_dir: Path,
    *,
    start: str,
    end: str,
    min_score: float,
    horizon_bars: int,
    bar_order_assumption: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "assumptions": {
            "start": start,
            "end": end,
            "min_score": min_score,
            "horizon_bars": horizon_bars,
            "entry": "logged closed 15m kline close",
            "stop": "logged entry_context.stop_pct",
            "tp_levels_r": list(TP_LEVELS),
            "tp_fractions": list(TP_FRACTIONS),
            "bar_order_assumption": bar_order_assumption,
            "final_r_note": "final_r is a whole-position path diagnostic; blended_final_r applies the 40/35/25 TP ladder.",
            "mode": "offline replay; not live-executable and intentionally uses future bars",
        },
        "summary": summarize_results(results),
        "results": [asdict(item) for item in results],
    }
    (output_dir / "high_score_intercept_replay.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "high_score_intercept_replay.md").write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    assumptions = payload["assumptions"]
    lines = [
        "# High-Score Intercept Replay Report",
        "",
        f"Window: {assumptions['start']} to {assumptions['end']}",
        f"Min score: {assumptions['min_score']}",
        f"Horizon bars: {assumptions['horizon_bars']} closed 15m bars",
        f"Bar order assumption: {assumptions['bar_order_assumption']}",
        "",
        "This is offline attribution and intentionally uses future bars. It must not be used as live entry logic.",
        "",
        "Note: `final_r` is a whole-position path diagnostic; `blended_final_r` applies the 40/35/25 TP ladder.",
        "",
        "## Overall",
        "",
        markdown_table(summary["overall"]),
        "",
        "## By Primary Reason",
        "",
        markdown_group(summary["by_primary_reason"]),
        "",
        "## By Symbol",
        "",
        markdown_group(summary["by_symbol"]),
        "",
        "## By Side",
        "",
        markdown_group(summary["by_side"]),
        "",
    ]
    return "\n".join(lines)


def markdown_group(group: dict[str, dict[str, Any]]) -> str:
    rows = [{"name": name, **stats} for name, stats in group.items()]
    return markdown_rows(rows)


def markdown_table(stats: dict[str, Any]) -> str:
    return markdown_rows([stats])


def markdown_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows._"
    keys = list(rows[0].keys())
    lines = [
        "| " + " | ".join(keys) + " |",
        "| " + " | ".join("---" for _ in keys) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(key, "")) for key in keys) + " |")
    return "\n".join(lines)


def _float(value: Any, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay high-score intercepted entry-chain signals.")
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--min-score", type=float, default=85.0)
    parser.add_argument("--horizon-bars", type=int, default=96)
    parser.add_argument("--bar-order-assumption", choices=sorted(BAR_ORDER_ASSUMPTIONS), default="stop_first")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument(
        "--include-reason",
        action="append",
        default=[],
        help="Also replay intercepted rows with this reason even when score is below --min-score.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_decision_rows(Path(args.log_root), args.start, args.end)
    results = replay_all(rows, args.min_score, args.horizon_bars, tuple(args.include_reason), args.bar_order_assumption)
    write_outputs(
        results,
        Path(args.output_dir),
        start=args.start,
        end=args.end,
        min_score=args.min_score,
        horizon_bars=args.horizon_bars,
        bar_order_assumption=args.bar_order_assumption,
    )
    print(json.dumps({"rows": len(rows), "replayed": len(results), "output_dir": args.output_dir}, ensure_ascii=False))


if __name__ == "__main__":
    main()
