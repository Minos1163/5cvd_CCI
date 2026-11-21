"""主账本盈亏归因（分窗口 + 分段对照）。

口径（与 2026-10-31 评审裁定一致）：
- 仓位级净额 = Σ(PAPER_CLOSE + PAPER_REDUCE 的 net_pnl_full)
- net_pnl_full 已含出场成本并摊分建仓成本，是本项目唯一权威口径
- 不使用 net_pnl（close-only，少一笔建仓成本）
- 不使用 margin_pnl（deprecated，net×leverage 双计）
- 不跨日累加 summary 计数器
- **窗口与分段都按 `entry_time`（入场 K 线时间）切**，不按出场时间：
  一笔 11-13 进、11-14 出的仓位属于"旧代码"，按出场时间切会把它算进新代码段。

## 三栏：全部 / 切分点之前 / 切分点之后

- 全部 = 窗口内已平仓仓位（窗口起点见 `--since-utc` / `--since-restart`）
- 切分点 = 生产进程最后一次 `process_start`（`--since-restart`）或显式 `--cut-utc`
- 硬校验：`之前.n + 之后.n == 全部.n` 且 `|之前.net + 之后.net − 全部.net| <= 1e-6`，
  否则**直接报错退出**。这是为了防止"改了切分逻辑却静默漏算"——2026-11-14 那次
  归因就是因为窗口/分段口径不一致，同一批数据在两份报告里差了 24 笔。

复现 2026-11-14 的"旧代码 5 笔 / 新代码 42 笔"：

    python scripts/analysis/attribution_20261114.py --since-utc 2026-11-14T00:00:00 --since-restart

## 对齐守卫

每笔仓位都要用 `decisions.kline.timestamp` 与 `paper_trades.entry_time` 做等值校验
（`stat_tools.assert_alignment`）。**不要**改成 `decisions.timestamp`：后者是周期处理时刻
（比 K 线晚约 10 秒），拿它 join 会让整批样本偏移一根 15m K 线，算出 ρ=−0.332 的假象
（真实值是 −0.005）。找不到对应决策行的仓位视为数据缺失，直接 raise，不静默跳过。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, pstdev

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "logs"
OUT_ROOT = ROOT / "reports" / "attribution_segments"

sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
from stat_tools import assert_alignment  # noqa: E402  同一目录的兄弟模块

DEFAULT_SINCE = "2026-11-08T00:00:00"
# 2026-11-08 → 2026-11-14 主账本复盘时用的起点；保留常量只为向后兼容旧调用。
LEGACY_START = int(datetime(2026, 11, 8, 0, 0, tzinfo=timezone.utc).timestamp())


# ---------------------------------------------------------------- 装载


def parse_utc(text: str) -> int:
    """把 `YYYY-MM-DDTHH:MM:SS` 解析成 UTC 秒。必须带 T，不猜时区。"""
    return int(datetime.strptime(text, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp())


def fmt(ts: int | None) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%m-%d %H:%M")


def iso(ts: int | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def load_events(paths) -> list[dict]:
    out: list[dict] = []
    for p in paths:
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def build_positions(events: list[dict]) -> list[dict]:
    """按 position_id 重建仓位级记录。"""
    by_pos: dict[str, dict] = {}
    for e in events:
        pid = e.get("position_id")
        if not pid:
            continue
        rec = by_pos.setdefault(
            pid,
            {
                "position_id": pid,
                "net_full": 0.0,
                "gross": 0.0,
                "entry_cost": 0.0,
                "exit_cost": 0.0,
                "closed": False,
                "reduces": 0,
                "exit_reasons": [],
            },
        )
        if e["event"] == "PAPER_OPEN":
            rec.update(
                {
                    "symbol": e.get("symbol"),
                    "side": e.get("side"),
                    "entry_time": e.get("entry_time") or e.get("timestamp"),
                    "entry_price": e.get("entry_price"),
                    "notional": e.get("notional"),
                    "stop_pct": (e.get("risk_distance") or 0) / (e.get("entry_price") or 1) or None,
                    "risk_distance": e.get("risk_distance"),
                    "leverage": e.get("leverage"),
                    "score": e.get("score"),
                    "source_quadrant": e.get("source_quadrant"),
                    "entry_channel": e.get("entry_channel"),
                    "exit_mode": e.get("exit_mode"),
                    "scout_mission": e.get("scout_mission"),
                    "entry_fee": (e.get("fee") or 0) + (e.get("slippage") or 0),
                }
            )
            rec["entry_cost"] += (e.get("fee") or 0) + (e.get("slippage") or 0)
        else:
            rec["net_full"] += e.get("net_pnl_full") or 0.0
            rec["gross"] += e.get("gross_pnl") or 0.0
            rec["exit_cost"] += (e.get("fee") or 0) + (e.get("slippage") or 0)
            rec["exit_reasons"].append(e.get("reason"))
            if e["event"] == "PAPER_CLOSE":
                rec["closed"] = True
                rec["exit_time"] = e.get("timestamp")
                rec["exit_reason"] = e.get("reason")
                rec["mfe"] = e.get("max_favorable_r_observed")
            else:
                rec["reduces"] += 1
                rec["mfe"] = e.get("max_favorable_r_observed")
    return [r for r in by_pos.values() if r.get("symbol")]


def _month_dirs(since_ts: int, logs: Path = LOGS) -> list[Path]:
    """窗口起点所在月及之后的月份目录（`logs/2026-11` 这种）。

    为什么不扫全部月份：全库有 20 万行决策（2026-06 起），逐行 `json.loads` 要 15 秒以上，
    而归因只需要**窗口起点之后**的月份——仓位不可能在入场日之前出场。月份目录名是
    `YYYY-MM`，字符串比较即时间顺序（`2026-10B` < `2026-11`，符合预期）。
    """
    floor = datetime.fromtimestamp(since_ts, timezone.utc).strftime("%Y-%m")
    return sorted(
        p for p in logs.iterdir() if p.is_dir() and p.name[:4].isdigit() and p.name >= floor
    )


def load_decision_frame(since_ts: int, logs: Path = LOGS) -> tuple[dict, dict]:
    """一次扫描同时产出 `(决策索引, K 线序列)`，并只保留需要的字段。

    - 索引键 `(symbol, kline.timestamp)`：见模块 docstring 的对齐说明。
    - 只保留 `kline` 的 OHLC + `score` + `score_detail.scores`：完整行带十几个大字段
      （component_points_v2 等），全量驻留会让 47 笔样本的分析吃掉几百 MB。
    """
    index: dict[tuple[str, int], dict] = {}
    bars: dict[str, dict[int, dict]] = defaultdict(dict)
    for month_dir in _month_dirs(since_ts, logs):
        for path in sorted(month_dir.glob("*/decisions.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                kline = row.get("kline") or {}
                ts = kline.get("timestamp")
                if ts is None:
                    continue
                ts = int(ts)
                slim = {
                    "timestamp": ts,
                    "open": kline.get("open"),
                    "high": kline.get("high"),
                    "low": kline.get("low"),
                    "close": kline.get("close"),
                }
                symbol = row.get("symbol")
                bars[symbol][ts] = slim
                index[(symbol, ts)] = {
                    "kline": slim,
                    "score": row.get("score"),
                    "scores": (row.get("score_detail") or {}).get("scores") or {},
                }
    return index, {symbol: dict(sorted(series.items())) for symbol, series in bars.items()}


def load_decision_index(since_ts: int = 0, logs: Path = LOGS) -> dict[tuple[str, int], dict]:
    """只要决策索引时用这个（内部复用 `load_decision_frame`，不重复解析）。"""
    index, _bars = load_decision_frame(since_ts, logs)
    return index


def load_bar_series(since_ts: int = 0, logs: Path = LOGS) -> dict[str, dict[int, dict]]:
    """只要 K 线序列时用这个（负控的 bracket 重放读它）。"""
    _index, bars = load_decision_frame(since_ts, logs)
    return bars


def last_restart_ts(logs: Path = LOGS) -> tuple[int, Path | None]:
    """grep 全部 `logs/*/*/runtime.out.*.log` 里**最后**一条 `process_start @ ... UTC`。

    返回 `(ts, 文件路径)`；找不到就 raise —— 静默回落到"无切分点"会让分段报告
    看起来正常却什么都没切，比报错危险。
    """
    marker = "process_start @ "
    latest: tuple[int, Path] | None = None
    for path in sorted(logs.glob("*/*/runtime.out.*.log")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if marker not in line:
                continue
            tail = line.split(marker, 1)[1]
            stamp = tail.split("UTC", 1)[0].strip()
            try:
                ts = int(datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
            except ValueError:
                continue
            if latest is None or ts >= latest[0]:
                latest = (ts, path)
    if latest is None:
        raise RuntimeError(f"在 {logs}/*/*/runtime.out.*.log 里找不到任何 process_start 行")
    return latest


# ---------------------------------------------------------------- 汇总


def summarize(rows: list[dict]) -> dict:
    nets = [r["net_full"] for r in rows]
    wins = [v for v in nets if v > 0]
    losses = [v for v in nets if v < 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    risks = [
        (r.get("notional") or 0.0) * (r.get("stop_pct") or 0.0)
        for r in rows
        if r.get("notional") and r.get("stop_pct")
    ]
    valid_risk = [x for x in risks if x > 0]
    return {
        "n": len(rows),
        "net_total": round(sum(nets), 6),
        "gross_total": round(sum(r["gross"] for r in rows), 6),
        "cost_total": round(sum(r["entry_cost"] + r["exit_cost"] for r in rows), 6),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(rows), 4) if rows else None,
        "avg_win": round(mean(wins), 4) if wins else None,
        "avg_loss": round(mean(losses), 4) if losses else None,
        "payoff": round(mean(wins) / abs(mean(losses)), 3) if wins and losses else None,
        "profit_factor": round(gross_win / gross_loss, 3) if gross_loss else None,
        "expectancy": round(mean(nets), 4) if rows else None,
        "sd": round(pstdev(nets), 4) if len(nets) > 1 else None,
        "median": round(median(nets), 4) if rows else None,
        "avg_risk_usdt": round(mean(valid_risk), 4) if valid_risk else None,
    }


def group(rows: list[dict], key: str) -> dict:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        buckets[str(r.get(key))].append(r)
    return {k: summarize(v) for k, v in sorted(buckets.items(), key=lambda kv: -sum(x["net_full"] for x in kv[1]))}


def segment(closed: list[dict], since_ts: int, cut_ts: int) -> dict:
    """窗口内三栏切分 + 硬校验（合计必须闭合）。

    断言不是"防御性编程"，而是本次修复的核心：分段口径曾经与窗口口径不一致，
    导致两份报告对同一批数据给出相差 24 笔的结论。任何一个数对不上就停下。
    """
    window = [p for p in closed if (p.get("entry_time") or 0) >= since_ts]
    before = [p for p in window if (p.get("entry_time") or 0) < cut_ts]
    after = [p for p in window if (p.get("entry_time") or 0) >= cut_ts]

    all_s, before_s, after_s = summarize(window), summarize(before), summarize(after)
    if before_s["n"] + after_s["n"] != all_s["n"] or before_s["n"] + after_s["n"] != all_s["n"]:
        raise SystemExit(
            f"分段笔数不闭合：之前 {before_s['n']} + 之后 {after_s['n']} != 全部 {all_s['n']}"
        )
    total = before_s["net_total"] + after_s["net_total"]
    if abs(total - all_s["net_total"]) > 1e-6:
        raise SystemExit(
            f"分段净额不闭合：之前 {before_s['net_total']} + 之后 {after_s['net_total']} "
            f"= {total} != 全部 {all_s['net_total']}（差 {total - all_s['net_total']:.9f}）"
        )
    return {
        "window_start_utc": iso(since_ts),
        "cut_point_utc": iso(cut_ts),
        "all": all_s,
        "before_cut": before_s,
        "after_cut": after_s,
        "closed_check": {
            "n_before_plus_after": before_s["n"] + after_s["n"],
            "n_all": all_s["n"],
            "net_before_plus_after": round(total, 6),
            "net_all": all_s["net_total"],
        },
        "_rows": {"all": window, "before_cut": before, "after_cut": after},
    }


def check_alignment(rows: list[dict], decisions: dict[tuple[str, int], dict]) -> dict:
    """对每笔仓位做 entry_time ↔ kline.timestamp 等值校验（缺行即 raise）。"""
    missing = []
    for p in rows:
        key = (p.get("symbol"), int(p.get("entry_time") or 0))
        row = decisions.get(key)
        if row is None:
            missing.append(key)
            continue
        assert_alignment(p.get("entry_time"), (row.get("kline") or {}).get("timestamp"))
    if missing:
        raise SystemExit(f"有 {len(missing)} 笔仓位找不到对应决策行（不许静默跳过）：{missing[:5]}")
    return {"checked": len(rows), "missing": 0}


# ---------------------------------------------------------------- 主流程


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="主账本盈亏归因（分窗口 + 分段对照）")
    parser.add_argument(
        "--since-utc",
        default=None,
        help=f"窗口起点（UTC，形如 2026-11-14T00:00:00）。缺省时：给了 --since-restart 用重启时刻，否则 {DEFAULT_SINCE}",
    )
    parser.add_argument(
        "--since-restart",
        action="store_true",
        help="以生产进程最后一次 process_start 作为**切分点**（未显式给 --since-utc 时也作为窗口起点）",
    )
    parser.add_argument(
        "--cut-utc",
        default=None,
        help="显式切分点（UTC）。与 --since-restart 同给时以本参数为准",
    )
    parser.add_argument("--out-dir", default=None, help="输出目录（默认 reports/attribution_segments/<since>_cut_<cut>）")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)

    restart_ts: int | None = None
    restart_src: Path | None = None
    if args.since_restart:
        restart_ts, restart_src = last_restart_ts()

    if args.since_utc:
        since_ts = parse_utc(args.since_utc)
    elif restart_ts is not None:
        since_ts = restart_ts
    else:
        since_ts = parse_utc(DEFAULT_SINCE)

    if args.cut_utc:
        cut_ts = parse_utc(args.cut_utc)
    elif restart_ts is not None:
        cut_ts = restart_ts
    else:
        cut_ts = since_ts  # 未给切分点：之前一栏为空，合计仍闭合

    paper_paths = [p for month in _month_dirs(since_ts) for p in sorted(month.glob("*/paper_trades.jsonl"))]
    events = load_events(paper_paths)
    positions_all = build_positions(events)
    closed_all = [p for p in positions_all if p.get("closed")]

    segments = segment(closed_all, since_ts, cut_ts)
    decisions, _bars = load_decision_frame(since_ts)
    alignment = check_alignment(segments["_rows"]["all"], decisions)

    out_dir = Path(args.out_dir) if args.out_dir else (
        OUT_ROOT / f"since_{datetime.fromtimestamp(since_ts, timezone.utc):%Y%m%dT%H%M%S}"
        f"_cut_{datetime.fromtimestamp(cut_ts, timezone.utc):%Y%m%dT%H%M%S}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows = segments["_rows"]["all"]
    report = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "window_start_utc": segments["window_start_utc"],
            "cut_point_utc": segments["cut_point_utc"],
            "cut_source": str(restart_src) if (args.since_restart and not args.cut_utc) else ("--cut-utc" if args.cut_utc else "since"),
            "log_days": len(paper_paths),
            "events": len(events),
            "positions_all": len(positions_all),
            "positions_closed": len(closed_all),
            "positions_in_window": len(all_rows),
            "pnl_basis": "sum(net_pnl_full) per position_id; full-cost",
            "segment_key": "entry_time（入场 K 线时间）",
            "alignment": alignment,
        },
        "segments": {
            "all": segments["all"],
            "before_cut": segments["before_cut"],
            "after_cut": segments["after_cut"],
            "closed_check": segments["closed_check"],
        },
        "by_symbol": group(all_rows, "symbol"),
        "by_side": group(all_rows, "side"),
        "by_quadrant": group(all_rows, "source_quadrant"),
        "by_channel": group(all_rows, "entry_channel"),
        "by_exit_reason": group(all_rows, "exit_reason"),
        "positions": [
            {
                "position_id": p["position_id"],
                "symbol": p.get("symbol"),
                "side": p.get("side"),
                "entry_utc": fmt(p["entry_time"]) if p.get("entry_time") else None,
                "exit_utc": fmt(p["exit_time"]) if p.get("exit_time") else None,
                "hold_min": round((p["exit_time"] - p["entry_time"]) / 60, 1)
                if p.get("exit_time") and p.get("entry_time")
                else None,
                "net_pnl_full": round(p["net_full"], 6),
                "gross": round(p["gross"], 6),
                "cost": round(p["entry_cost"] + p["exit_cost"], 6),
                "notional": p.get("notional"),
                "risk_usdt": round((p.get("notional") or 0) * (p.get("stop_pct") or 0), 4),
                "stop_pct": round(p["stop_pct"] * 100, 3) if p.get("stop_pct") else None,
                "leverage": p.get("leverage"),
                "score": p.get("score"),
                "quadrant": p.get("source_quadrant"),
                "channel": p.get("entry_channel"),
                "exit_reason": p.get("exit_reason"),
                "reduces": p.get("reduces"),
                "mfe_r": p.get("mfe"),
                "segment": "before_cut" if (p.get("entry_time") or 0) < cut_ts else "after_cut",
                "r_multiple": round(p["net_full"] / ((p.get("notional") or 0) * (p.get("stop_pct") or 1)), 3)
                if p.get("notional") and p.get("stop_pct")
                else None,
            }
            for p in sorted(all_rows, key=lambda x: -(x["net_full"]))
        ],
    }
    (out_dir / "attribution.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- 控制台输出：先三栏，再明细 ----
    print(f"窗口起点 {segments['window_start_utc']}  |  切分点 {segments['cut_point_utc']}")
    if args.since_restart:
        print(f"切分点来源: {restart_src}")
    print(f"对齐校验: {alignment['checked']} 笔全部 entry_time == decisions.kline.timestamp（差 0 秒）")
    print()
    header = f"{'分段':14s}{'n':>5s}{'净额':>10s}{'胜率':>8s}{'PF':>8s}{'期望':>9s}"
    print(header)
    print("-" * len(header))
    for label, key in (("全部", "all"), ("切分点之前", "before_cut"), ("切分点之后", "after_cut")):
        s = report["segments"][key]
        wr = f"{s['win_rate'] * 100:.1f}%" if s["win_rate"] is not None else "-"
        pf = f"{s['profit_factor']:.2f}" if s["profit_factor"] is not None else "-"
        exp = f"{s['expectancy']:+.2f}" if s["expectancy"] is not None else "-"
        print(f"{label:14s}{s['n']:>5d}{s['net_total']:>+10.2f}{wr:>8s}{pf:>8s}{exp:>9s}")
    chk = report["segments"]["closed_check"]
    print(
        f"\n闭合校验: 笔数 {chk['n_before_plus_after']} == {chk['n_all']}；"
        f"净额 {chk['net_before_plus_after']:+.6f} == {chk['net_all']:+.6f}"
    )

    print("\n=== 逐笔（窗口内）===")
    print(f"{'symbol':10s}{'side':7s}{'entry':12s}{'exit':12s}{'hold':>7s}{'net':>9s}{'R':>7s}{'stop%':>7s}{'seg':>12s}{'reason':22s}")
    for p in report["positions"]:
        print(
            f"{p['symbol']:10s}{p['side'] or '':7s}{p['entry_utc'] or '':12s}{p['exit_utc'] or '':12s}"
            f"{(p['hold_min'] or 0):7.0f}{p['net_pnl_full']:9.3f}{(p['r_multiple'] or 0):7.2f}"
            f"{(p['stop_pct'] or 0):7.2f}{p['segment']:>12s}  {p['exit_reason'] or '':22s}"
        )
    for title, key in (("按退出原因", "by_exit_reason"), ("按象限", "by_quadrant"), ("按通道", "by_channel"), ("按方向", "by_side")):
        print(f"\n=== {title} ===")
        for k, v in report[key].items():
            print(f"{k:26s} n={v['n']:2d} net={v['net_total']:+8.3f} exp={v['expectancy']:+.3f}")
    print(f"\n输出 → {out_dir / 'attribution.json'}")


if __name__ == "__main__":
    main()
