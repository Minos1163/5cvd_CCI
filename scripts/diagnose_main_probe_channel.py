# -*- coding: utf-8 -*-
"""diagnose_main_probe_channel.py — main_probe 通道专项诊断(Task P)。

依据 2026-10-04 评审裁定 3.6 节的四项范围:

1. **跨窗口方向控制**:把 `(通道 × 方向)` 交叉表摆开,检验"通道"在控制方向后
   是否仍对 MFE / notional_pnl 有解释力(排除方向混淆);
2. **五因子影子横向对比**:关联入场时刻的 `component_points_v2`,比较
   main_probe 与 main_direct 的 F1-F5 分布差异;
3. **象限分布核查**:两通道的象限结构差异(是否 Q1 对 probe 层不友好);
4. **binding_cap 分布核查**:直读 `metadata.risk_budget.binding_cap`,
   判断调整杠杆倍数本身是否是有效动作(见裁定 3.4 节)。

**样本量警告**:截至 2026-10-04,main_probe 累计仅 18 笔(12+6)。
按 `SAMPLE_SIZE_DECISION_RULES`,本脚本输出**只作描述性记录**,不构成
"通道质量更差"的统计结论;报告须显式标注功效不足。

用法:
  python scripts/diagnose_main_probe_channel.py --start 2026-09-16 --end 2026-10-04
  python scripts/diagnose_main_probe_channel.py --start 2026-09-16 --end 2026-10-04 --baseline-channel main_direct
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.analyze_0916_0927_window import collect_trades, day_dirs, iter_jsonl  # noqa: E402

TARGET_CHANNEL = "main_probe"
FIVE_FACTORS = (
    "trend_persistence",
    "structure_location",
    "payoff_geometry",
    "volatility_regime",
    "order_flow",
)
EXECUTABLE_ACTIONS = {"PROBE", "DIRECT"}
BINDING_CAP_VALUES = (
    "raw_notional",
    "leveraged_cap_notional",
    "remaining_exposure_notional",
    "none",
)
MIN_SAMPLES_FOR_CLAIM = 20  # SAMPLE_SIZE_DECISION_RULES


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 4) if values else None


def load_shadow_index(dirs: list[Path]) -> dict[tuple[str, str], list[dict]]:
    """(day, symbol) → 入场时刻的可执行决策记录(含五因子影子与 risk_budget)。

    一笔交易与其入场决策按"同日 + 同 symbol"近似关联:同日内同币种可能有多条
    可执行记录,故保留全部并标注 `match_ambiguous`。
    """
    index: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for directory in dirs:
        for payload in iter_jsonl(directory / "decisions.jsonl"):
            action = str(payload.get("action") or "").upper()
            if action not in EXECUTABLE_ACTIONS:
                continue
            meta = payload.get("component_points_v2_meta")
            normalized = (meta or {}).get("normalized_values") if isinstance(meta, dict) else None
            # binding_cap 的落盘路径:主决策在 metadata.risk_budget;兼容顶层写法
            budget = payload.get("risk_budget")
            if not isinstance(budget, dict):
                budget = (payload.get("metadata") or {}).get("risk_budget")
            index[(directory.name, str(payload.get("symbol") or "").upper())].append(
                {
                    "action": action,
                    "side": str(payload.get("side") or "").upper(),
                    "score": float(payload.get("score") or 0.0),
                    "leverage": int(payload.get("leverage") or 0),
                    "quadrant": str(payload.get("quadrant") or ""),
                    "normalized_values": dict(normalized) if isinstance(normalized, dict) else None,
                    "binding_cap": (budget or {}).get("binding_cap"),
                    "raw_notional": (budget or {}).get("raw_notional"),
                    "leveraged_cap_notional": (budget or {}).get("leveraged_cap_notional"),
                    "remaining_exposure_notional": (budget or {}).get("remaining_exposure_notional"),
                    "final_notional": (budget or {}).get("final_notional"),
                }
            )
    return index


def cross_tab(trades: list[dict], key_a: str, key_b: str) -> dict:
    """按两个维度交叉汇总笔数 / notional_pnl / 平均 MFE。"""
    buckets: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {"count": 0, "notional_pnl": 0.0, "mfe": []}))
    for trade in trades:
        name_a = str(trade.get(key_a) or "null")
        name_b = str(trade.get(key_b) or "null")
        bucket = buckets[name_a][name_b]
        bucket["count"] += 1
        bucket["notional_pnl"] += trade["notional_pnl"]
        bucket["mfe"].append(trade["mfe_r"])
    return {
        a: {
            b: {
                "count": value["count"],
                "notional_pnl": round(value["notional_pnl"], 4),
                "avg_mfe_r": _mean(value["mfe"]),
                "avg_notional_pnl": round(value["notional_pnl"] / value["count"], 4)
                if value["count"]
                else None,
            }
            for b, value in inner.items()
        }
        for a, inner in buckets.items()
    }


def channel_factor_comparison(joined: list[dict], channel: str, baseline: str) -> dict:
    """五因子影子分在两个通道间的分布对比(入场时刻)。"""
    result: dict[str, dict] = {}
    for name in FIVE_FACTORS:
        target_values = [
            row["normalized_values"][name]
            for row in joined
            if row["channel"] == channel and row.get("normalized_values")
        ]
        base_values = [
            row["normalized_values"][name]
            for row in joined
            if row["channel"] == baseline and row.get("normalized_values")
        ]
        target_mean = _mean(target_values)
        base_mean = _mean(base_values)
        result[name] = {
            "target_mean": target_mean,
            "baseline_mean": base_mean,
            "delta": round(target_mean - base_mean, 4)
            if target_mean is not None and base_mean is not None
            else None,
            "target_n": len(target_values),
            "baseline_n": len(base_values),
        }
    return result


def binding_cap_distribution(joined: list[dict]) -> dict:
    """按通道统计 binding_cap 分布——决定"调杠杆倍数"是否有效动作(裁定 3.4)。"""
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in joined:
        cap = row.get("binding_cap") or "unknown"
        buckets[row["channel"]][cap] += 1
    return {channel: dict(counts) for channel, counts in buckets.items()}


def build_report(dirs: list[Path], *, channel: str, baseline: str) -> dict:
    trades = collect_trades(dirs)
    shadow = load_shadow_index(dirs)

    joined: list[dict] = []
    for trade in trades:
        key = (trade["day"].replace("-", "-"), trade["symbol"])
        candidates = shadow.get(key, [])
        matched = next(
            (item for item in candidates if item["side"] == trade["side"]),
            candidates[0] if candidates else None,
        )
        joined.append(
            {
                **trade,
                "channel": str(trade.get("entry_channel") or "null"),
                "normalized_values": (matched or {}).get("normalized_values"),
                "binding_cap": (matched or {}).get("binding_cap"),
                "decision_score": (matched or {}).get("score"),
                "match_ambiguous": len(candidates) > 1,
            }
        )

    target_trades = [row for row in joined if row["channel"] == channel]
    baseline_trades = [row for row in joined if row["channel"] == baseline]

    return {
        "window_dirs": [directory.name for directory in dirs],
        "total_trades": len(joined),
        "sample_warning": (
            f"{channel} 累计 {len(target_trades)} 笔 < {MIN_SAMPLES_FOR_CLAIM} 笔门槛:"
            "本输出仅作描述性记录,不构成通道质量结论"
        ),
        "diagnosis_1_direction_control": {
            "channel_x_side": cross_tab(joined, "channel", "side"),
            "note": "控制方向后比较 main_probe 与 baseline 的 avg_notional_pnl / avg_mfe_r",
        },
        "diagnosis_2_factor_comparison": channel_factor_comparison(joined, channel, baseline),
        "diagnosis_3_quadrant": {
            "channel_x_quadrant": cross_tab(joined, "channel", "source_quadrant"),
            "target_channel_quadrants": sorted(
                {str(row.get("source_quadrant") or "null") for row in target_trades}
            ),
        },
        "diagnosis_4_binding_cap": {
            "distribution": binding_cap_distribution(joined),
            "note": (
                "若 leveraged_cap_notional 很少成为 binding_cap,则调整杠杆倍数是无效动作;"
                "应转向调整真正生效的那个 cap 对应的参数"
            ),
        },
        "headline": {
            "target_count": len(target_trades),
            "target_notional_pnl": round(sum(row["notional_pnl"] for row in target_trades), 4),
            "target_avg_mfe_r": _mean([row["mfe_r"] for row in target_trades]),
            "baseline_count": len(baseline_trades),
            "baseline_notional_pnl": round(
                sum(row["notional_pnl"] for row in baseline_trades), 4
            ),
            "baseline_avg_mfe_r": _mean([row["mfe_r"] for row in baseline_trades]),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--channel", default=TARGET_CHANNEL)
    parser.add_argument("--baseline-channel", default="main_direct")
    parser.add_argument("--output-dir", default="logs/analysis/main-probe-diagnosis")
    args = parser.parse_args()

    dirs = day_dirs(PROJECT_ROOT / args.log_root, args.start, args.end)
    report = build_report(dirs, channel=args.channel, baseline=args.baseline_channel)
    report["window"] = f"{args.start}~{args.end}"
    report["target_channel"] = args.channel
    report["baseline_channel"] = args.baseline_channel

    out_dir = PROJECT_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"main-probe-{args.start}_{args.end}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report["headline"], ensure_ascii=False, indent=2))
    print(report["sample_warning"])
    print("--- 通道 × 方向 ---")
    for channel, inner in report["diagnosis_1_direction_control"]["channel_x_side"].items():
        for side, stats in inner.items():
            print(
                f"  {channel:<16} {side:<6} n={stats['count']:<3} "
                f"notional={stats['notional_pnl']:<10} avg_pnl={stats['avg_notional_pnl']:<10} mfe={stats['avg_mfe_r']}"
            )
    print("--- binding_cap 分布 ---")
    print(json.dumps(report["diagnosis_4_binding_cap"]["distribution"], ensure_ascii=False))
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
