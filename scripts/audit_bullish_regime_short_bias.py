from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


TZ_CST = timezone(timedelta(hours=8))
EXECUTABLE_ACTIONS = {"DIRECT", "PROBE"}
SIDES = ("LONG", "SHORT")
QUADRANTS = ("Q1", "Q2", "Q3", "Q4")


@dataclass(frozen=True)
class DecisionAuditRow:
    day: str
    timestamp: int
    symbol: str
    side: str
    quadrant: str
    score: float
    action: str
    reasons: tuple[str, ...]


def date_range(start: str, end: str) -> Iterable[str]:
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    while current <= final:
        yield current.isoformat()
        current += timedelta(days=1)


def load_decisions(log_root: Path, start: str, end: str) -> list[DecisionAuditRow]:
    rows: list[DecisionAuditRow] = []
    for day in date_range(start, end):
        path = log_root / day[:7] / day / "decisions.jsonl"
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                row = parse_decision(day, payload)
                if row is not None:
                    rows.append(row)
    return sorted(rows, key=lambda item: (item.timestamp, item.symbol, item.side, item.quadrant))


def parse_decision(day: str, payload: dict[str, Any]) -> DecisionAuditRow | None:
    context = payload.get("entry_context") if isinstance(payload.get("entry_context"), dict) else {}
    kline = payload.get("kline") if isinstance(payload.get("kline"), dict) else {}
    side = str(context.get("side") or payload.get("side") or "").strip().upper()
    if side not in SIDES:
        return None
    symbol = str(payload.get("symbol") or "").strip().upper()
    timestamp = _int(kline.get("timestamp"))
    if timestamp <= 0:
        timestamp = _int(payload.get("timestamp"))
    if not symbol or timestamp <= 0:
        return None
    reasons = payload.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    return DecisionAuditRow(
        day=day,
        timestamp=timestamp,
        symbol=symbol,
        side=side,
        quadrant=str(payload.get("quadrant") or "UNKNOWN").strip().upper(),
        score=_float(payload.get("score")),
        action=str(payload.get("action") or "").strip().upper(),
        reasons=tuple(str(item) for item in reasons),
    )


def filter_rows(rows: list[DecisionAuditRow], start_ts: int, end_ts: int | None) -> list[DecisionAuditRow]:
    return [row for row in rows if _row_value(row, "timestamp") >= start_ts and (end_ts is None or _row_value(row, "timestamp") <= end_ts)]


def summarize_asymmetry(rows: list[DecisionAuditRow], min_score: float = 80.0) -> dict[str, Any]:
    high_score_rows = [row for row in rows if _row_value(row, "score") >= min_score]
    by_side = {side: _summarize_bucket([row for row in high_score_rows if _row_value(row, "side") == side]) for side in SIDES}
    by_quadrant: dict[str, dict[str, Any]] = {}
    quadrant_names = list(QUADRANTS)
    for quadrant in sorted({str(_row_value(row, "quadrant")) for row in high_score_rows if str(_row_value(row, "quadrant")) not in QUADRANTS}):
        quadrant_names.append(quadrant)
    for quadrant in quadrant_names:
        by_quadrant[quadrant] = {
            side: _summarize_bucket(
                [
                    row
                    for row in high_score_rows
                    if str(_row_value(row, "quadrant")) == quadrant and _row_value(row, "side") == side
                ]
            )
            for side in SIDES
        }
    long_bucket = by_side["LONG"]
    short_bucket = by_side["SHORT"]
    return {
        "min_score": min_score,
        "overall": by_side,
        "by_quadrant": by_quadrant,
        "short_bias": {
            "high_score_count_delta": short_bucket["high_score_count"] - long_bucket["high_score_count"],
            "executable_count_delta": short_bucket["executable_count"] - long_bucket["executable_count"],
            "executable_rate_delta": _round(short_bucket["executable_rate"] - long_bucket["executable_rate"]),
        },
    }


def _summarize_bucket(rows: list[DecisionAuditRow]) -> dict[str, Any]:
    total = len(rows)
    executable_count = sum(1 for row in rows if str(_row_value(row, "action")) in EXECUTABLE_ACTIONS)
    return {
        "high_score_count": total,
        "executable_count": executable_count,
        "executable_rate": _round(executable_count / total) if total else 0.0,
    }


def write_outputs(
    summary: dict[str, Any],
    output_dir: Path,
    *,
    start: str,
    end: str,
    regime_start: str,
    min_score: float,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "assumptions": {
            "start": start,
            "end": end,
            "regime_start": regime_start,
            "min_score": min_score,
            "executable_actions": sorted(EXECUTABLE_ACTIONS),
            "non_executable_actions": ["NO_TRADE", "WATCH"],
            "timestamp_source": "kline.timestamp with row.timestamp fallback",
            "scope": "offline attribution only",
        },
        "summary": summary,
    }
    (output_dir / "bullish_regime_short_bias_audit.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "bullish_regime_short_bias_audit.md").write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    assumptions = payload["assumptions"]
    summary = payload["summary"]
    lines = [
        "# Bullish Regime Short-Bias Audit",
        "",
        f"Window: {assumptions['start']} to {assumptions['end']}",
        f"Regime start: {assumptions['regime_start']}",
        f"Min score: {assumptions['min_score']}",
        "",
        "This is offline attribution only and does not alter live logic.",
        "",
        "## Overall",
        "",
        _markdown_table([
            {"side": side, **summary["overall"][side]} for side in SIDES
        ]),
        "",
        "## Short Bias",
        "",
        _markdown_table([summary["short_bias"]]),
    ]
    for quadrant, stats in summary["by_quadrant"].items():
        lines.extend([
            "",
            f"## {quadrant}",
            "",
            _markdown_table([{"side": side, **stats[side]} for side in SIDES]),
        ])
    lines.append("")
    return "\n".join(lines)


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


def _parse_regime_start(value: str) -> int:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TZ_CST)
    return int(parsed.timestamp())


def _round(value: float) -> float:
    return round(value, 4)


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _row_value(row: Any, field: str) -> Any:
    if isinstance(row, dict):
        if field == "side":
            context = row.get("entry_context") if isinstance(row.get("entry_context"), dict) else {}
            return str(context.get("side") or row.get("side") or "").strip().upper()
        if field == "timestamp":
            kline = row.get("kline") if isinstance(row.get("kline"), dict) else {}
            return _int(kline.get("timestamp") or row.get("timestamp"))
        if field in {"action", "quadrant"}:
            return str(row.get(field) or "").strip().upper()
        return row.get(field)
    return getattr(row, field)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit bullish-regime LONG/SHORT executable asymmetry.")
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--regime-start", required=True)
    parser.add_argument("--min-score", type=float, default=80.0)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = load_decisions(Path(args.log_root), args.start, args.end)
    filtered = filter_rows(rows, _parse_regime_start(args.regime_start), None)
    summary = summarize_asymmetry(filtered, min_score=args.min_score)
    write_outputs(
        summary,
        Path(args.output_dir),
        start=args.start,
        end=args.end,
        regime_start=args.regime_start,
        min_score=args.min_score,
    )
    print(json.dumps({"rows": len(rows), "filtered_rows": len(filtered), "output_dir": args.output_dir}, ensure_ascii=False))


if __name__ == "__main__":
    main()
