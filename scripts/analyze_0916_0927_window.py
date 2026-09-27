# -*- coding: utf-8 -*-
"""analyze_0916_0927_window.py — 09-16 重启至 09-27 窗口:亏损归因 + 因子正交性诊断。

输出(默认 logs/analysis/2026-09-27-window/):
  window_attribution.json   交易层归因(通道/方向/象限/退出原因/实验)
  factor_orthogonality.json 因子层诊断(标准化、相关矩阵、PCA、载荷、Kaiser 有效维数)

用法:
  python scripts/analyze_0916_0927_window.py --start 2026-09-16 --end 2026-09-27
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FACTORS = [
    "trend_ema_context",
    "flow_cvd_confirmation",
    "cci_momentum_quality",
    "price_action_structure",
    "fibonacci_location",
    "risk_reward_geometry",
]
WEIGHTS = {
    "trend_ema_context": 20.0,
    "flow_cvd_confirmation": 18.0,
    "cci_momentum_quality": 14.0,
    "price_action_structure": 22.0,
    "fibonacci_location": 18.0,
    "risk_reward_geometry": 8.0,
}


def day_dirs(log_root: Path, start: str, end: str) -> list[Path]:
    import datetime as dt

    out: list[Path] = []
    day = dt.date.fromisoformat(start)
    final = dt.date.fromisoformat(end)
    while day <= final:
        path = log_root / day.strftime("%Y-%m") / day.strftime("%Y-%m-%d")
        if path.exists():
            out.append(path)
        day += dt.timedelta(days=1)
    return out


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _side(payload: dict) -> str:
    ctx = payload.get("entry_context") if isinstance(payload.get("entry_context"), dict) else {}
    return str(ctx.get("side") or payload.get("side") or "").upper() or "UNKNOWN"


def collect_trades(dirs: list[Path]) -> list[dict]:
    """按事件顺序配对 OPEN/CLOSE,还原逐笔交易(整笔口径)。"""
    trades: list[dict] = []
    open_positions: dict[str, dict] = {}
    for directory in dirs:
        for payload in iter_jsonl(directory / "paper_trades.jsonl"):
            event = str(payload.get("event") or "")
            symbol = str(payload.get("symbol") or "")
            if event == "PAPER_OPEN":
                open_positions[symbol] = {
                    "day": directory.name,
                    "symbol": symbol,
                    "side": str(payload.get("side") or "UNKNOWN").upper(),
                    "entry_channel": payload.get("entry_channel"),
                    "source_quadrant": payload.get("source_quadrant"),
                    "experiment_id": payload.get("experiment_id"),
                    "leverage": int(payload.get("leverage") or 0),
                    "notional": float(payload.get("notional") or 0.0),
                    "margin_used": float(payload.get("margin_used") or 0.0),
                    "entry_score": float(payload.get("score") or 0.0),
                    "stop_pct": float(payload.get("stop_pct") or 0.0),
                    "opened_at": payload.get("recorded_at"),
                    "mfe_r": 0.0,
                    "exit_reason": None,
                    "notional_pnl": 0.0,
                    "margin_pnl": 0.0,
                }
                continue
            position = open_positions.get(symbol)
            if position is None:
                continue
            if event in {"PAPER_CLOSE", "PAPER_REDUCE"}:
                position["mfe_r"] = max(
                    position["mfe_r"], float(payload.get("max_favorable_r_observed") or 0.0)
                )
                position["notional_pnl"] += float(payload.get("notional_pnl") or 0.0)
                position["margin_pnl"] += float(payload.get("margin_pnl") or 0.0)
                if event == "PAPER_CLOSE":
                    position["exit_reason"] = str(payload.get("reason") or "UNKNOWN")
                    position["closed_at"] = payload.get("recorded_at")
                    position["notional_pnl"] = float(
                        payload.get("position_realized_pnl") or position["notional_pnl"]
                    )
                    position["margin_pnl"] = float(
                        payload.get("position_margin_realized_pnl") or position["margin_pnl"]
                    )
                    trades.append(position)
                    open_positions.pop(symbol, None)
    return trades


def bucket_summary(trades: list[dict], key: str) -> dict:
    buckets: dict[str, dict] = defaultdict(
        lambda: {"count": 0, "notional_pnl": 0.0, "margin_pnl": 0.0, "wins": 0, "symbols": [], "mfe": []}
    )
    for trade in trades:
        name = str(trade.get(key) if trade.get(key) is not None else "null")
        bucket = buckets[name]
        bucket["count"] += 1
        bucket["notional_pnl"] += trade["notional_pnl"]
        bucket["margin_pnl"] += trade["margin_pnl"]
        bucket["wins"] += 1 if trade["notional_pnl"] > 0 else 0
        bucket["symbols"].append(f"{trade['symbol']}@{trade['day']}")
        bucket["mfe"].append(trade["mfe_r"])
    for bucket in buckets.values():
        mfe_values = bucket.pop("mfe")
        bucket["avg_mfe_r"] = round(sum(mfe_values) / max(1, len(mfe_values)), 3)
        sorted_mfe = sorted(mfe_values)
        bucket["median_mfe_r"] = round(
            sorted_mfe[len(sorted_mfe) // 2] if sorted_mfe else 0.0, 3
        )
        bucket["notional_pnl"] = round(bucket["notional_pnl"], 4)
        bucket["margin_pnl"] = round(bucket["margin_pnl"], 4)
        bucket["win_rate"] = round(bucket["wins"] / max(1, bucket["count"]), 4)
        bucket["symbols"] = sorted(bucket["symbols"])[:12]
    return dict(sorted(buckets.items(), key=lambda item: item[1]["notional_pnl"]))


def collect_decisions(dirs: list[Path]) -> tuple[list[dict], np.ndarray]:
    rows: list[dict] = []
    matrix: list[list[float]] = []
    for directory in dirs:
        for payload in iter_jsonl(directory / "decisions.jsonl"):
            points = payload.get("component_points") or {}
            ctx = payload.get("entry_context") if isinstance(payload.get("entry_context"), dict) else {}
            rows.append(
                {
                    "action": str(payload.get("action") or ""),
                    "quadrant": str(payload.get("quadrant") or ""),
                    "score": float(payload.get("score") or 0.0),
                    "side": _side(payload),
                    "atr_pct": float(ctx.get("atr_pct") or 0.0),
                }
            )
            matrix.append([float(points.get(name) or 0.0) for name in FACTORS])
    return rows, np.asarray(matrix, dtype=float)


def factor_diagnostics(matrix: np.ndarray) -> dict:
    if matrix.size == 0:
        return {"error": "no data"}
    maxima = np.asarray([WEIGHTS[name] for name in FACTORS], dtype=float)
    normalized = matrix / maxima  # 第一步:因子标准化(消除量级差异)

    std = normalized.std(axis=0, ddof=1)
    usable = std > 1e-9
    z = np.zeros_like(normalized)
    z[:, usable] = (normalized[:, usable] - normalized[:, usable].mean(axis=0)) / std[usable]

    pearson = np.corrcoef(z, rowvar=False)
    # SVD 求主成分(等价于协方差特征分解)
    u, s, vt = np.linalg.svd(z, full_matrices=False)
    eigenvalues = (s**2) / max(1, z.shape[0] - 1)
    explained = eigenvalues / eigenvalues.sum()
    loadings = vt.T * np.sqrt(eigenvalues)  # 变量在主成分上的载荷

    # Spearman(按秩)
    ranks = np.argsort(np.argsort(z, axis=0), axis=0).astype(float)
    spearman = np.corrcoef(ranks, rowvar=False)

    return {
        "n_samples": int(matrix.shape[0]),
        "weights": WEIGHTS,
        "raw_mean": {n: round(float(matrix[:, i].mean()), 4) for i, n in enumerate(FACTORS)},
        "raw_std": {n: round(float(matrix[:, i].std(ddof=1)), 4) for i, n in enumerate(FACTORS)},
        "zero_share": {
            n: round(float((matrix[:, i] == 0.0).mean()), 4) for i, n in enumerate(FACTORS)
        },
        "normalized_std": {n: round(float(std[i]), 4) for i, n in enumerate(FACTORS)},
        "pearson_matrix": {
            FACTORS[i]: {FACTORS[j]: round(float(pearson[i, j]), 4) for j in range(len(FACTORS))}
            for i in range(len(FACTORS))
        },
        "spearman_matrix": {
            FACTORS[i]: {FACTORS[j]: round(float(spearman[i, j]), 4) for j in range(len(FACTORS))}
            for i in range(len(FACTORS))
        },
        "pca": {
            "eigenvalues": [round(float(v), 4) for v in eigenvalues],
            "explained_variance_ratio": [round(float(v), 4) for v in explained],
            "cumulative_ratio": [round(float(v), 4) for v in np.cumsum(explained)],
            "kaiser_components": int((eigenvalues > 1.0).sum()),
            "pc1_2_variance": round(float(explained[:2].sum()), 4),
            "loadings": {
                f"PC{i + 1}": {FACTORS[j]: round(float(loadings[j, i]), 4) for j in range(len(FACTORS))}
                for i in range(len(FACTORS))
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--start", default="2026-09-16")
    parser.add_argument("--end", default="2026-09-27")
    parser.add_argument("--output-dir", default="logs/analysis/2026-09-27-window")
    args = parser.parse_args()

    dirs = day_dirs(PROJECT_ROOT / args.log_root, args.start, args.end)
    trades = collect_trades(dirs)
    rows, matrix = collect_decisions(dirs)

    actions = Counter(row["action"] for row in rows)
    quadrants = Counter(row["quadrant"] for row in rows)
    executable = [row for row in rows if row["action"] in {"PROBE", "DIRECT"}]

    attribution = {
        "window": f"{args.start}~{args.end}",
        "pnl_accounting": "notional_pnl (primary); margin_pnl reported separately",
        "totals": {
            "trades": len(trades),
            "notional_pnl": round(sum(t["notional_pnl"] for t in trades), 4),
            "margin_pnl": round(sum(t["margin_pnl"] for t in trades), 4),
            "wins": sum(1 for t in trades if t["notional_pnl"] > 0),
        },
        "by_entry_channel": bucket_summary(trades, "entry_channel"),
        "by_side": bucket_summary(trades, "side"),
        "by_source_quadrant": bucket_summary(trades, "source_quadrant"),
        "by_exit_reason": bucket_summary(trades, "exit_reason"),
        "by_experiment": bucket_summary(trades, "experiment_id"),
        "trades": [
            {
                "day": t["day"],
                "symbol": t["symbol"],
                "side": t["side"],
                "channel": t["entry_channel"],
                "quadrant": t["source_quadrant"],
                "leverage": t["leverage"],
                "notional": round(t["notional"], 2),
                "stop_pct": round(t["stop_pct"], 5),
                "entry_score": round(t["entry_score"], 2),
                "mfe_r": round(t["mfe_r"], 3),
                "exit_reason": t["exit_reason"],
                "notional_pnl": round(t["notional_pnl"], 4),
                "margin_pnl": round(t["margin_pnl"], 4),
            }
            for t in sorted(trades, key=lambda x: x["notional_pnl"])
        ],
        "decisions": {
            "total": len(rows),
            "actions": dict(actions),
            "executable": len(executable),
            "quadrants": dict(quadrants),
            "score_ge_82": sum(1 for row in rows if row["score"] >= 82.0),
            "score_ge_87": sum(1 for row in rows if row["score"] >= 87.0),
        },
    }

    factors = factor_diagnostics(matrix)

    out_dir = PROJECT_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "window_attribution.json").write_text(
        json.dumps(attribution, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "factor_orthogonality.json").write_text(
        json.dumps(factors, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(
        {
            "trades": attribution["totals"],
            "decisions": attribution["decisions"],
            "by_entry_channel": attribution["by_entry_channel"],
            "pca_eigenvalues": factors["pca"]["eigenvalues"],
            "pca_cumulative": factors["pca"]["cumulative_ratio"],
            "kaiser_components": factors["pca"]["kaiser_components"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
