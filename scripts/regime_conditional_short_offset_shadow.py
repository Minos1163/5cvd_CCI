# -*- coding: utf-8 -*-
"""regime_conditional_short_offset_shadow.py — regime_conditional_side_offset shadow 审计(08-24 DEEPSEEK 3.3 节)。

bullish regime 下高分 SHORT 可执行率(16.67%)显著高于 LONG(4.12%),且 LONG 有
long_threshold_offset +10 而 SHORT 无对称机制。本脚本做 SHADOW 反事实:
若 bullish regime 下 SHORT direct 门槛与 LONG 对称(82+10=92),高分 SHORT 中
会被额外拦截的样本数与反事实结果(不改任何 live 逻辑)。

用法: python scripts/regime_conditional_short_offset_shadow.py \
    --log-root logs --start 2026-08-18 --end 2026-08-24 \
    --regime-start "2026-08-19 19:15" --min-score 80 \
    --shadow-short-offset 10.0
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXECUTABLE_ACTIONS = {"DIRECT", "PROBE"}


def load_decisions(log_root: Path, start: str, end: str) -> list[dict]:
    rows: list[dict] = []
    import datetime as dt

    day = dt.date.fromisoformat(start)
    final = dt.date.fromisoformat(end)
    while day <= final:
        path = log_root / day.strftime("%Y-%m") / day.strftime("%Y-%m-%d") / "decisions.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
        day += dt.timedelta(days=1)
    return rows


def shadow_blocked(short_exec_before: list[dict], shadow_direct_threshold: float) -> list[dict]:
    """shadow 反事实:可执行的 SHORT 中,score 低于对称门槛的会被额外拦截。"""
    return [r for r in short_exec_before if r["score"] < shadow_direct_threshold]


def completed_15m_candle_timestamp(payload: dict) -> int | None:
    """Return a candle timestamp only when the decision was logged after close."""
    kline = payload.get("kline") if isinstance(payload.get("kline"), dict) else {}
    if str(kline.get("timeframe") or "") != "15m":
        return None
    candle_ts = _safe_int(kline.get("timestamp"))
    decision_ts = _safe_int(payload.get("timestamp"))
    if candle_ts <= 0 or decision_ts < candle_ts + 900:
        return None
    return candle_ts


def extract_breadth(payload: dict) -> tuple[float | None, float | None]:
    """Read optional 5h/6h breadth evidence without inventing missing values."""
    snapshot = payload.get("market_snapshot") if isinstance(payload.get("market_snapshot"), dict) else {}
    evidence = payload.get("regime_evidence") if isinstance(payload.get("regime_evidence"), dict) else {}
    values = {**snapshot, **evidence, **payload}

    def pick(*keys: str) -> float | None:
        for key in keys:
            value = _safe_float(values.get(key))
            if value is not None:
                return value
        return None

    return (
        pick("breadth_5h", "breadth_5h_ratio", "breadth5h"),
        pick("breadth_6h", "breadth_6h_ratio", "breadth6h"),
    )


def regime_evidence(payload: dict, regime_start_ts: int, breadth_min: float = 0.60) -> dict:
    candle_ts = completed_15m_candle_timestamp(payload)
    if candle_ts is None:
        return {"status": "INCOMPLETE_CANDLE", "completed_candle_ts": None, "breadth_5h": None, "breadth_6h": None}
    if candle_ts < regime_start_ts:
        return {"status": "OUTSIDE_REGIME_WINDOW", "completed_candle_ts": candle_ts, "breadth_5h": None, "breadth_6h": None}
    breadth_5h, breadth_6h = extract_breadth(payload)
    if breadth_5h is None or breadth_6h is None:
        status = "BULLISH_TIME_WINDOW_PROXY"
    elif breadth_5h >= breadth_min and breadth_6h >= breadth_min:
        status = "BULLISH_CONFIRMED"
    else:
        status = "NOT_BULLISH"
    return {
        "status": status,
        "completed_candle_ts": candle_ts,
        "breadth_5h": breadth_5h,
        "breadth_6h": breadth_6h,
    }


def reversal_confirmation_score(payload: dict) -> float:
    """Pure score from fields available at the completed-candle decision."""
    points = payload.get("component_points") if isinstance(payload.get("component_points"), dict) else {}
    components = (
        _safe_float(points.get("price_action_structure"), 0.0) / 22.0,
        _safe_float(points.get("flow_cvd_confirmation"), 0.0) / 18.0,
        _safe_float(points.get("cci_momentum_quality"), 0.0) / 14.0,
    )
    return round(max(0.0, min(1.0, sum(components) / len(components))), 4)


def shadow_rows(rows: list[dict], regime_start_ts: int, min_score: float, breadth_min: float) -> tuple[list[dict], dict]:
    candidates: list[dict] = []
    counts = {
        "completed_candles": 0,
        "outside_regime_window": 0,
        "breadth_confirmed": 0,
        "breadth_missing": 0,
        "not_bullish": 0,
    }
    for payload in rows:
        evidence = regime_evidence(payload, regime_start_ts, breadth_min)
        if evidence["status"] == "INCOMPLETE_CANDLE":
            continue
        counts["completed_candles"] += 1
        if evidence["status"] == "BULLISH_CONFIRMED":
            counts["breadth_confirmed"] += 1
        elif evidence["status"] == "BULLISH_TIME_WINDOW_PROXY":
            counts["breadth_missing"] += 1
        elif evidence["status"] == "NOT_BULLISH":
            counts["not_bullish"] += 1
        elif evidence["status"] == "OUTSIDE_REGIME_WINDOW":
            counts["outside_regime_window"] += 1
            continue
        else:
            continue
        context = payload.get("entry_context") if isinstance(payload.get("entry_context"), dict) else {}
        side = str(context.get("side") or payload.get("side") or "").strip().upper()
        quadrant = str(payload.get("quadrant") or "").strip().upper()
        action = str(payload.get("action") or "").strip().upper()
        score = _safe_float(payload.get("score"), 0.0)
        if side != "SHORT" or quadrant != "Q1" or score < min_score or action not in EXECUTABLE_ACTIONS:
            continue
        candidates.append(
            {
                "timestamp": evidence["completed_candle_ts"],
                "symbol": str(payload.get("symbol") or ""),
                "side": side,
                "score": score,
                "action": action,
                "quadrant": quadrant,
                "regime_status": evidence["status"],
                "breadth_5h": evidence["breadth_5h"],
                "breadth_6h": evidence["breadth_6h"],
                "reversal_confirmation_score": reversal_confirmation_score(payload),
            }
        )
    return candidates, counts


def _safe_float(value: object, default: float | None = None) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return parsed if math.isfinite(parsed) else default


def _safe_int(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", default="2026-08-24")
    parser.add_argument("--end", default="2026-09-15")
    parser.add_argument("--regime-start", default="2026-08-24 00:00")  # 北京时间
    parser.add_argument("--min-score", type=float, default=80.0)
    parser.add_argument("--shadow-short-offset", type=float, default=10.0)
    parser.add_argument("--breadth-min", type=float, default=0.60)
    parser.add_argument("--output-dir", default="logs/analysis/2026-08-24-short-bias")
    args = parser.parse_args()

    import datetime as dt

    # regime 起点 → UTC 秒(北京 = UTC+8)
    regime_ts = int(
        (dt.datetime.fromisoformat(args.regime_start.replace(" ", "T")).replace(tzinfo=dt.timezone(dt.timedelta(hours=8)))).timestamp()
    )
    rows = load_decisions(PROJECT_ROOT / args.log_root, args.start, args.end)

    candidates, regime_counts = shadow_rows(rows, regime_ts, args.min_score, args.breadth_min)

    # shadow 反事实:SHORT direct 门槛升到 82 + shadow_short_offset(对称 LONG)
    shadow_direct_threshold = 82.0 + args.shadow_short_offset
    blocked = shadow_blocked(candidates, shadow_direct_threshold)
    shadow_offsets = {}
    for offset in (5.0, 10.0):
        threshold = 82.0 + offset
        blocked_at_offset = shadow_blocked(candidates, threshold)
        shadow_offsets[str(int(offset))] = {
            "direct_threshold": threshold,
            "evaluated_q1_short_executable": len(candidates),
            "blocked_count": len(blocked_at_offset),
            "blocked_samples": blocked_at_offset[:10],
        }

    out = {
        "assumptions": {
            "regime_start_bj": args.regime_start,
            "regime_start_utc_ts": regime_ts,
            "min_score": args.min_score,
            "shadow_short_offset": args.shadow_short_offset,
            "shadow_direct_threshold": shadow_direct_threshold,
            "breadth_min": args.breadth_min,
            "candle_rule": "15m candle timestamp is eligible only when decision timestamp is at least 900 seconds later",
            "scope": "SHADOW ONLY - no live logic change",
        },
        "regime_evidence": regime_counts,
        "q1_short_executable_candidates": len(candidates),
        "shadow_offsets": shadow_offsets,
        "blocked_by_shadow_offset": {
            "count": len(blocked),
            "rate_reduction_pp": round(len(blocked) / max(1, len(candidates)) * 100, 2),
            "samples": blocked[:10],
        },
    }
    out_dir = PROJECT_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "regime_conditional_short_offset_shadow.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
