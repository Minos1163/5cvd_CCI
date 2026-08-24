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
import sys
from collections import defaultdict
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", default="2026-08-18")
    parser.add_argument("--end", default="2026-08-24")
    parser.add_argument("--regime-start", default="2026-08-19 19:15")  # 北京时间
    parser.add_argument("--min-score", type=float, default=80.0)
    parser.add_argument("--shadow-short-offset", type=float, default=10.0)
    parser.add_argument("--output-dir", default="logs/analysis/2026-08-24-short-bias")
    args = parser.parse_args()

    import datetime as dt

    # regime 起点 → UTC 秒(北京 = UTC+8)
    regime_ts = int(
        (dt.datetime.fromisoformat(args.regime_start.replace(" ", "T")).replace(tzinfo=dt.timezone(dt.timedelta(hours=8)))).timestamp()
    )
    rows = load_decisions(PROJECT_ROOT / args.log_root, args.start, args.end)

    high = []
    for payload in rows:
        context = payload.get("entry_context") if isinstance(payload.get("entry_context"), dict) else {}
        kline = payload.get("kline") if isinstance(payload.get("kline"), dict) else {}
        ts = int(kline.get("timestamp") or payload.get("timestamp") or 0)
        if ts < regime_ts:
            continue
        side = str(context.get("side") or payload.get("side") or "").strip().upper()
        if side not in {"LONG", "SHORT"}:
            continue
        score = float(payload.get("score") or 0.0)
        if score < args.min_score:
            continue
        action = str(payload.get("action") or "").upper()
        high.append(
            {
                "timestamp": ts, "symbol": str(payload.get("symbol") or ""),
                "side": side, "score": score, "action": action,
                "quadrant": str(payload.get("quadrant") or ""),
                "executable": action in EXECUTABLE_ACTIONS,
            }
        )

    long_rows = [r for r in high if r["side"] == "LONG"]
    short_rows = [r for r in high if r["side"] == "SHORT"]

    # shadow 反事实:SHORT direct 门槛升到 82 + shadow_short_offset(对称 LONG)
    shadow_direct_threshold = 82.0 + args.shadow_short_offset
    short_exec_before = [r for r in short_rows if r["executable"]]
    short_exec_after = [
        r for r in short_rows
        if r["executable"] and r["score"] >= shadow_direct_threshold
    ]
    blocked = shadow_blocked(short_exec_before, shadow_direct_threshold)

    out = {
        "assumptions": {
            "regime_start_bj": args.regime_start,
            "regime_start_utc_ts": regime_ts,
            "min_score": args.min_score,
            "shadow_short_offset": args.shadow_short_offset,
            "shadow_direct_threshold": shadow_direct_threshold,
            "scope": "SHADOW ONLY - no live logic change",
        },
        "high_score": {"LONG": len(long_rows), "SHORT": len(short_rows)},
        "executable": {
            "LONG": len([r for r in long_rows if r["executable"]]),
            "SHORT_before": len(short_exec_before),
            "SHORT_after_shadow_offset": len(short_exec_after),
        },
        "blocked_by_shadow_offset": {
            "count": len(blocked),
            "rate_reduction_pp": round(
                (len(short_exec_before) - len(short_exec_after)) / max(1, len(short_rows)) * 100, 2
            ),
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
