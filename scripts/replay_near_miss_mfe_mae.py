from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


DEFAULT_WINDOWS_MINUTES = (30, 60, 120, 240)


def main() -> None:
    args = parse_args()
    near_misses = read_jsonl(args.near_misses)
    decisions = read_jsonl(args.decisions)
    rows = replay_near_misses(near_misses, decisions, windows_minutes=args.windows_minutes)
    write_csv(args.output, rows)
    print(json.dumps({"status": "ok", "rows": len(rows)}, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay dry-run near misses and calculate hypothetical MFE/MAE.")
    parser.add_argument("--near-misses", required=True)
    parser.add_argument("--decisions", required=True, nargs="+")
    parser.add_argument("--output", required=True)
    parser.add_argument("--windows-minutes", type=int, nargs="+", default=list(DEFAULT_WINDOWS_MINUTES))
    return parser.parse_args()


def read_jsonl(paths: str | Path | Sequence[str | Path]) -> list[dict[str, Any]]:
    if isinstance(paths, (str, Path)):
        path_list = [paths]
    else:
        path_list = list(paths)
    rows: list[dict[str, Any]] = []
    for path_item in path_list:
        path = Path(path_item)
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                rows.append(json.loads(line))
    return rows


def replay_near_misses(
    near_misses: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    *,
    windows_minutes: Sequence[int] = DEFAULT_WINDOWS_MINUTES,
) -> list[dict[str, Any]]:
    by_symbol: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions:
        symbol = str(decision.get("symbol") or "").upper()
        kline = decision.get("kline")
        if symbol and isinstance(kline, Mapping):
            by_symbol[symbol].append(decision)
    for symbol_rows in by_symbol.values():
        symbol_rows.sort(key=lambda row: int(_timestamp(row)))

    output: list[dict[str, Any]] = []
    for near in near_misses:
        symbol = str(near.get("symbol") or "").upper()
        side = str(near.get("intended_side") or near.get("side") or "").upper()
        entry_price = _float(near.get("entry_price"))
        entry_ts = int(_timestamp(near))
        row = {
            "timestamp": entry_ts,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "score": near.get("score"),
            "primary_reason": near.get("primary_reason"),
        }
        if side not in {"LONG", "SHORT"} or entry_price <= 0:
            output.append(row)
            continue
        symbol_decisions = by_symbol.get(symbol, [])
        for minutes in windows_minutes:
            metrics = _window_metrics(symbol_decisions, entry_ts, side, entry_price, minutes)
            suffix = f"{minutes}m"
            row[f"mfe_{suffix}_pct"] = metrics["mfe_pct"]
            row[f"mae_{suffix}_pct"] = metrics["mae_pct"]
            row[f"bars_{suffix}"] = metrics["bars"]
        output.append(row)
    return output


def _window_metrics(decisions: Sequence[Mapping[str, Any]], entry_ts: int, side: str, entry_price: float, minutes: int) -> dict[str, Any]:
    end_ts = entry_ts + minutes * 60
    mfe = 0.0
    mae = 0.0
    bars = 0
    for decision in decisions:
        ts = int(_timestamp(decision))
        if ts <= entry_ts or ts > end_ts:
            continue
        kline = decision.get("kline")
        if not isinstance(kline, Mapping):
            continue
        high = _float(kline.get("high"))
        low = _float(kline.get("low"))
        if high <= 0 or low <= 0:
            continue
        if side == "LONG":
            favorable = (high - entry_price) / entry_price
            adverse = (low - entry_price) / entry_price
        else:
            favorable = (entry_price - low) / entry_price
            adverse = (entry_price - high) / entry_price
        mfe = max(mfe, favorable)
        mae = min(mae, adverse)
        bars += 1
    return {"mfe_pct": round(mfe, 6), "mae_pct": round(mae, 6), "bars": bars}


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _timestamp(row: Mapping[str, Any]) -> int:
    kline = row.get("kline")
    if isinstance(kline, Mapping) and kline.get("timestamp") is not None:
        return int(kline.get("timestamp") or 0)
    return int(row.get("timestamp") or row.get("kline_timestamp") or 0)


def _float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


if __name__ == "__main__":
    main()
