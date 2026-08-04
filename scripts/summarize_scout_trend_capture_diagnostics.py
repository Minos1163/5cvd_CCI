from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable


DEFAULT_THRESHOLDS = (1.0, 1.2, 1.5, 2.0, 3.0)


def date_range(start: str, end: str) -> Iterable[str]:
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    while current <= final:
        yield current.isoformat()
        current += timedelta(days=1)


def scout_trade_path(log_root: Path, day: str) -> Path:
    return log_root / day[:7] / day / "scout_micro" / "paper_trades.jsonl"


def load_rows(log_root: Path, start: str, end: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day in date_range(start, end):
        path = scout_trade_path(log_root, day)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                payload.setdefault("day", day)
                rows.append(payload)
    return rows


def summarize_rows(rows: list[dict[str, Any]], thresholds: tuple[float, ...] = DEFAULT_THRESHOLDS) -> dict[str, Any]:
    trend_rows = [row for row in rows if row.get("exit_mode") == "trend_capture"]
    closes = [row for row in trend_rows if row.get("event") == "PAPER_CLOSE"]
    closes_with_metric = [row for row in closes if _optional_float(row.get("max_favorable_r_observed")) is not None]
    favorable_values = [float(row["max_favorable_r_observed"]) for row in closes_with_metric]
    pnls = [_float(row.get("position_realized_pnl") or row.get("net_pnl")) for row in closes]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    gross_loss = abs(sum(losses))
    summary = {
        "total_rows": len(rows),
        "trend_capture_rows": len(trend_rows),
        "closed_trades": len(closes),
        "closed_trades_with_max_favorable_r": len(closes_with_metric),
        "closed_trades_missing_max_favorable_r": len(closes) - len(closes_with_metric),
        "avg_max_favorable_r_observed": _round(mean(favorable_values)) if favorable_values else 0.0,
        "median_max_favorable_r_observed": _round(median(favorable_values)) if favorable_values else 0.0,
        "max_favorable_r_observed": _round(max(favorable_values)) if favorable_values else 0.0,
        "threshold_touch_counts": {
            _threshold_key(threshold): sum(1 for value in favorable_values if value >= threshold)
            for threshold in thresholds
        },
        "threshold_touch_rates": {
            _threshold_key(threshold): _round(sum(1 for value in favorable_values if value >= threshold) / len(favorable_values))
            if favorable_values
            else 0.0
            for threshold in thresholds
        },
        "win_rate": _round(len(wins) / len(pnls)) if pnls else 0.0,
        "profit_factor": _round(sum(wins) / gross_loss) if gross_loss > 0 else (_round(sum(wins)) if wins else 0.0),
        "net_pnl": _round(sum(pnls)),
        "by_mission": _summarize_group(closes, "scout_mission", thresholds),
        "by_symbol": _summarize_group(closes, "symbol", thresholds),
        "by_reason": dict(Counter(str(row.get("reason") or "UNKNOWN") for row in closes)),
    }
    return summary


def _summarize_group(rows: list[dict[str, Any]], key: str, thresholds: tuple[float, ...]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "NONE")].append(row)
    return {name: _summarize_bucket(items, thresholds) for name, items in sorted(grouped.items())}


def _summarize_bucket(rows: list[dict[str, Any]], thresholds: tuple[float, ...]) -> dict[str, Any]:
    values = [
        metric
        for row in rows
        if (metric := _optional_float(row.get("max_favorable_r_observed"))) is not None
    ]
    pnls = [_float(row.get("position_realized_pnl") or row.get("net_pnl")) for row in rows]
    return {
        "closed_trades": len(rows),
        "with_max_favorable_r": len(values),
        "avg_max_favorable_r_observed": _round(mean(values)) if values else 0.0,
        "max_favorable_r_observed": _round(max(values)) if values else 0.0,
        "net_pnl": _round(sum(pnls)),
        "threshold_touch_counts": {
            _threshold_key(threshold): sum(1 for value in values if value >= threshold)
            for threshold in thresholds
        },
    }


def write_outputs(summary: dict[str, Any], output_dir: Path, *, start: str, end: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "assumptions": {
            "start": start,
            "end": end,
            "source": "scout_micro/paper_trades.jsonl PAPER_CLOSE rows",
            "metric": "max_favorable_r_observed from dry-run paper ledger",
            "historical_note": "Rows written before this diagnostic field was deployed will be counted as missing.",
        },
        "summary": summary,
    }
    (output_dir / "scout_trend_capture_diagnostics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "scout_trend_capture_diagnostics.md").write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    assumptions = payload["assumptions"]
    summary = payload["summary"]
    lines = [
        "# SCOUT Trend-Capture Diagnostics",
        "",
        f"Window: {assumptions['start']} to {assumptions['end']}",
        "",
        "Rows written before `max_favorable_r_observed` was deployed are counted as missing.",
        "",
        "## Overall",
        "",
        _markdown_table(
            [
                {
                    key: value
                    for key, value in summary.items()
                    if key not in {"by_mission", "by_symbol", "by_reason", "threshold_touch_counts", "threshold_touch_rates"}
                }
            ]
        ),
        "",
        "## Threshold Counts",
        "",
        _markdown_table([{"threshold": key, "count": value, "rate": summary["threshold_touch_rates"].get(key, 0.0)} for key, value in summary["threshold_touch_counts"].items()]),
        "",
        "## By Mission",
        "",
        _markdown_group(summary["by_mission"]),
        "",
        "## By Symbol",
        "",
        _markdown_group(summary["by_symbol"]),
        "",
        "## By Close Reason",
        "",
        _markdown_table([{"reason": key, "count": value} for key, value in summary["by_reason"].items()]),
        "",
    ]
    return "\n".join(lines)


def _markdown_group(group: dict[str, dict[str, Any]]) -> str:
    rows = []
    for name, stats in group.items():
        rows.append({key: value for key, value in {"name": name, **stats}.items() if key != "threshold_touch_counts"})
    return _markdown_table(rows)


def _markdown_table(rows: list[dict[str, Any]]) -> str:
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


def _threshold_key(value: float) -> str:
    return f">={value:g}R"


def _optional_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float:
    number = _optional_float(value)
    return number if number is not None else 0.0


def _round(value: float) -> float:
    return round(value, 4)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize SCOUT trend_capture max favorable R diagnostics.")
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output-dir")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_rows(Path(args.log_root), args.start, args.end)
    summary = summarize_rows(rows)
    if args.output_dir:
        write_outputs(summary, Path(args.output_dir), start=args.start, end=args.end)
    print(json.dumps({"rows": len(rows), "summary": summary}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
