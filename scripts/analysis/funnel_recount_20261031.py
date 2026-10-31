"""T3 漏斗重算:直接从 decisions.jsonl / gate_rejections.jsonl 统计,不用 summary.json 的累计字段。

背景(2026-10-31 评审 D10 + 自查):
  `summary.json` 里的 decision_counts / gate_rejections_by_layer / near_miss_count
  是**运行以来的累计计数器**,每个日切片都重写一遍。把它们按日相加 =
  同一批决策被计入 6 次(稿件因此把 5,850 写成 20,475、把 190 写成 602)。
  本脚本以事件级日志为准重算,并与 summary 的末次快照交叉校验。

用法: python scripts/analysis/funnel_recount_20261031.py
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.observability.dry_run_summary import rejection_layer  # noqa: E402

LOGS = ROOT / "logs" / "2026-10B"
DAYS = ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-10-31"]


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    decisions: list[dict] = []
    rejections: list[dict] = []
    near_miss: list[dict] = []
    per_day = {}
    for d in DAYS:
        day_dec = load(LOGS / d / "decisions.jsonl")
        day_rej = load(LOGS / d / "gate_rejections.jsonl")
        day_nm = load(LOGS / d / "near_misses.jsonl")
        decisions.extend(day_dec)
        rejections.extend(day_rej)
        near_miss.extend(day_nm)
        per_day[d] = dict(decisions=len(day_dec), rejections=len(day_rej), near_miss=len(day_nm),
                          bars=len({(r.get("symbol"), (r.get("kline") or {}).get("timestamp")) for r in day_dec}))

    # 去重(评审要求:按 (symbol, bar_ts, side) 唯一)
    dedup = {(r.get("symbol"), (r.get("kline") or {}).get("timestamp"), r.get("side")) for r in decisions}
    dedup_sym_bar = {(r.get("symbol"), (r.get("kline") or {}).get("timestamp")) for r in decisions}
    action = Counter(r.get("action") for r in decisions)

    # 拒绝分层:一条记录的 reasons 是 "|" 连接的多原因串。
    # 采用"首个可归层的原因"归因(与 summary 的 side_policy/fib/budget/direct 完全一致),
    # 同时保留 primary_reason 归因作对照,两者的差额单独列出。
    layer = Counter()
    layer_primary = Counter()
    layer_reason: dict[str, Counter] = defaultdict(Counter)
    unmatched = 0
    for r in rejections:
        reasons = [x for x in str(r.get("reasons") or "").split("|") if x]
        layers = [x for x in (rejection_layer(s) for s in reasons) if x]
        prim = r.get("primary_reason") or ""
        prim_layer = rejection_layer(prim)
        if prim_layer:
            layer_primary[prim_layer] += 1
        if not layers:
            unmatched += 1
            continue
        layer[layers[0]] += 1
        layer_reason[layers[0]][prim] += 1

    # 与 summary 末次快照交叉校验
    last = json.loads((LOGS / DAYS[-1] / "summary.json").read_text(encoding="utf-8"))
    last_counts = last.get("decision_counts") or {}
    last_layer = last.get("gate_rejections_by_layer") or {}
    last_nm = last.get("near_miss_count")

    result = {
        "window": DAYS,
        "per_day": per_day,
        "totals": {
            "decision_rows": len(decisions),
            "unique_symbol_bar_side": len(dedup),
            "unique_symbol_bar": len(dedup_sym_bar),
            "expected_symbol_bar": len({r.get("symbol") for r in decisions}) * len({(r.get("kline") or {}).get("timestamp") for r in decisions}),
            "rejection_rows": len(rejections),
            "near_miss_rows": len(near_miss),
        },
        "action_counts": dict(action),
        "rejection_layers": dict(layer),
        "rejection_layers_primary_only": dict(layer_primary),
        "rejection_unmatched": unmatched,
        "rejection_layer_reasons": {k: dict(v.most_common()) for k, v in layer_reason.items()},
        "summary_last_snapshot": {
            "decision_counts": last_counts,
            "gate_rejections_by_layer": last_layer,
            "near_miss_count": last_nm,
        },
        "cross_check": {
            "decisions_match": sum(last_counts.values()) == len(decisions),
            "layers_match": dict(last_layer) == dict(layer),
            "near_miss_match": last_nm == len(near_miss),
        },
    }

    out = ROOT / "reports" / "2026-10B_funnel_recount.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    t = result["totals"]
    print(f"决策行 {t['decision_rows']} | 唯一(sym,bar) {t['unique_symbol_bar']} | 唯一(sym,bar,side) {t['unique_symbol_bar_side']}")
    print(f"拒绝行 {t['rejection_rows']} | 近似单 {t['near_miss_rows']}")
    print("动作分布", dict(action))
    print("拒绝分层", dict(layer))
    print("与 summary 末次快照交叉校验:", result["cross_check"])
    print(f"written {out}")

    rows_per_bar = t["decision_rows"] / max(1, t["unique_symbol_bar"])
    if abs(rows_per_bar - 1.0) > 0.01:
        print(f"WARN 每 bar 平均 {rows_per_bar:.2f} 行,需检查是否重复记录")


if __name__ == "__main__":
    main()
