from __future__ import annotations

"""Read-only audit for 4x SHORT concentration and Q1 overlap.

The audit consumes paper ledger close events and optional decision metadata. It
does not call an exchange, alter logs, or change live routing.
"""

import argparse
import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def date_range(start: str, end: str) -> Iterable[str]:
    current = date.fromisoformat(start)
    final = date.fromisoformat(end)
    while current <= final:
        yield current.isoformat()
        current += timedelta(days=1)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def load_trade_closes(log_root: Path, start: str, end: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for day in date_range(start, end):
        rows.extend(load_jsonl(log_root / day[:7] / day / "paper_trades.jsonl"))
    rows.sort(key=lambda row: _safe_int(row.get("timestamp")))
    open_queues: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    closes: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("symbol") or "").upper(), str(row.get("side") or "").upper())
        event = str(row.get("event") or "").upper()
        if event == "PAPER_OPEN":
            open_queues[key].append(row)
            continue
        if event != "PAPER_CLOSE" or _safe_float(row.get("remaining_fraction"), 1.0) != 0.0:
            continue
        opening = open_queues[key].pop(0) if open_queues[key] else {}
        enriched = dict(row)
        enriched["entry_timestamp"] = _safe_int(opening.get("timestamp"))
        enriched["entry_notional"] = _safe_float(opening.get("notional"), 0.0)
        enriched["entry_channel_at_open"] = opening.get("entry_channel")
        enriched["entry_source_quadrant"] = opening.get("source_quadrant")
        closes.append(enriched)
    return closes


def load_decision_index(log_root: Path, start: str, end: str) -> dict[tuple[str, int], dict[str, Any]]:
    index: dict[tuple[str, int], dict[str, Any]] = {}
    for day in date_range(start, end):
        for row in load_jsonl(log_root / day[:7] / day / "decisions.jsonl"):
            kline = row.get("kline") if isinstance(row.get("kline"), dict) else {}
            symbol = str(row.get("symbol") or "").strip().upper()
            timestamp = _safe_int(kline.get("timestamp") or row.get("timestamp"))
            if symbol and timestamp > 0:
                index[(symbol, timestamp)] = row
    return index


def select_4x_short(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("event") or "").upper() != "PAPER_CLOSE":
            continue
        if _safe_float(row.get("remaining_fraction"), 1.0) != 0.0:
            continue
        if str(row.get("side") or "").upper() != "SHORT":
            continue
        if _safe_int(row.get("leverage")) != 4:
            continue
        nominal = _safe_float(row.get("position_realized_pnl"), _safe_float(row.get("notional_pnl"), 0.0))
        leveraged = _safe_float(row.get("position_margin_realized_pnl"), nominal * 4.0)
        selected.append(
            {
                "timestamp": _safe_int(row.get("timestamp")),
                "entry_timestamp": _safe_int(row.get("entry_timestamp")),
                "symbol": str(row.get("symbol") or "").strip().upper(),
                "side": "SHORT",
                "leverage": 4,
                "source_quadrant": str(row.get("source_quadrant") or row.get("entry_source_quadrant") or row.get("quadrant") or "UNKNOWN").upper(),
                "entry_channel": str(row.get("entry_channel") or row.get("entry_channel_at_open") or "UNKNOWN"),
                "nominal_pnl": round(nominal, 8),
                "leveraged_pnl": round(leveraged, 8),
                "notional": round(_safe_float(row.get("entry_notional"), _safe_float(row.get("notional"), 0.0)), 8),
                "reason": str(row.get("reason") or ""),
            }
        )
    return selected


def summarize(rows: list[dict[str, Any]], decisions: dict[tuple[str, int], dict[str, Any]] | None = None) -> dict[str, Any]:
    decisions = decisions or {}
    by_quadrant = _group(rows, "source_quadrant")
    by_symbol = _group(rows, "symbol")
    by_channel = _group(rows, "entry_channel")
    q1 = [row for row in rows if row["source_quadrant"] == "Q1"]
    comparisons = []
    for row in rows:
        entry_timestamp = _safe_int(row.get("entry_timestamp"))
        decision = decisions.get((row["symbol"], entry_timestamp)) if entry_timestamp > 0 else None
        budget = decision.get("metadata", {}).get("risk_budget") if isinstance(decision, dict) else None
        if isinstance(budget, dict):
            comparisons.append(
                {
                    "symbol": row["symbol"],
                    "timestamp": row["timestamp"],
                    "raw_notional": budget.get("raw_notional"),
                    "leveraged_cap_notional": budget.get("leveraged_cap_notional"),
                    "final_notional": budget.get("final_notional"),
                    "binding_cap": budget.get("binding_cap"),
                }
            )
    return {
        "trade_count": len(rows),
        "nominal_pnl": round(sum(row["nominal_pnl"] for row in rows), 8),
        "leveraged_pnl": round(sum(row["leveraged_pnl"] for row in rows), 8),
        "q1_overlap": {
            "count": len(q1),
            "nominal_pnl": round(sum(row["nominal_pnl"] for row in q1), 8),
            "leveraged_pnl": round(sum(row["leveraged_pnl"] for row in q1), 8),
        },
        "by_quadrant": by_quadrant,
        "by_symbol": by_symbol,
        "by_entry_channel": by_channel,
        "risk_budget_comparison": {
            "matched_decision_metadata_count": len(comparisons),
            "max_single_trade_risk_pct": 0.0075,
            "formula": "equity * 0.0075 / (stop_pct * selected_leverage)",
            "samples": comparisons[:20],
        },
        "trades": rows,
    }


def _group(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "UNKNOWN")].append(row)
    return {
        label: {
            "count": len(items),
            "nominal_pnl": round(sum(item["nominal_pnl"] for item in items), 8),
            "leveraged_pnl": round(sum(item["leveraged_pnl"] for item in items), 8),
        }
        for label, items in sorted(grouped.items())
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError, OverflowError):
        return default


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit 4x SHORT/Q1 overlap from paper logs.")
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", default="2026-08-24")
    parser.add_argument("--end", default="2026-09-15")
    parser.add_argument("--output-dir", default="logs/analysis/2026-09-15-4x-short-q1")
    args = parser.parse_args()
    log_root = PROJECT_ROOT / args.log_root
    closes = load_trade_closes(log_root, args.start, args.end)
    decisions = load_decision_index(log_root, args.start, args.end)
    selected = select_4x_short(closes)
    output = {
        "assumptions": {
            "window": f"{args.start}~{args.end}",
            "source": "final PAPER_CLOSE rows only; partial PAPER_REDUCE rows excluded",
            "scope": "read-only offline audit; no exchange calls and no live routing changes",
            "nominal_pnl": "position_realized_pnl, fallback notional_pnl",
            "leveraged_pnl": "position_margin_realized_pnl, fallback nominal_pnl * leverage",
        },
        "input_counts": {"paper_close_rows": len(closes), "decision_rows_indexed": len(decisions)},
        "summary": summarize(selected, decisions),
    }
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "4x_short_q1_overlap.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
