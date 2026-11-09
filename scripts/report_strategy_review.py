"""账本度量报告：从日志事件流重建仓位级记录，输出 JSON + Markdown。

对应 2026-11-09 策略优化建议 §12(E0/E1/E7)、§16.5、附录 A/B。

用法::

    # 主账本，指定窗口（按建仓时间）
    python scripts/report_strategy_review.py --ledger main \
        --since 2026-10-31T12:02:35Z --out reports/review_main

    # A/B 两臂分别出报告（不合并）
    python scripts/report_strategy_review.py --ledger ab-legacy --out reports/review_ab_legacy
    python scripts/report_strategy_review.py --ledger ab-trend --out reports/review_ab_trend

设计约束：
- **只读**。不写任何运行状态，不参与交易判定。
- **不合并账本**。每个 ledger 独立初始化权益、独立统计，禁止相加。
- 结论只有 PASS / INCONCLUSIVE；样本不足时拒绝给方向性结论。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.reporting.ledger_metrics import (  # noqa: E402
    build_report,
    load_event_files,
    rebuild_positions,
    render_markdown,
    select_window,
)

LEDGER_PATHS = {
    "main": ("paper_trades.jsonl",),
    "ab-legacy": ("paper_ab", "legacy", "paper_trades.jsonl"),
    "ab-trend": ("paper_ab", "trend_capture", "paper_trades.jsonl"),
    "scout": ("scout_micro", "paper_trades.jsonl"),
}


def parse_ts(text: str | None) -> int | None:
    """接受 ``YYYY-MM-DD`` 或 ``YYYY-MM-DDTHH:MM:SSZ``，统一按 UTC 解释。"""
    if not text:
        return None
    raw = text.strip()
    if raw.endswith("Z"):
        raw = raw[:-1]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
    raise SystemExit(f"无法解析时间 '{text}'（支持 YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SSZ）")


def discover(ledger: str, logs_root: Path, since_ts: int | None, until_ts: int | None) -> list[Path]:
    """按月目录发现日切片文件；日期目录名就是 UTC 日期，可按窗口粗筛。"""
    parts = LEDGER_PATHS[ledger]
    since_day = datetime.fromtimestamp(since_ts, tz=timezone.utc).strftime("%Y-%m-%d") if since_ts else None
    until_day = datetime.fromtimestamp(until_ts, tz=timezone.utc).strftime("%Y-%m-%d") if until_ts else None
    found: list[Path] = []
    for month_dir in sorted(logs_root.glob("20??-??")):
        if not month_dir.is_dir():
            continue
        for day_dir in sorted(month_dir.glob("20??-??-??")):
            name = day_dir.name
            if since_day and name < since_day:
                continue
            if until_day and name > until_day:
                continue
            candidate = day_dir.joinpath(*parts)
            if candidate.exists():
                found.append(candidate)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description="从 paper 账本事件流生成可复核的度量报告")
    ap.add_argument(
        "--logs-root",
        default="logs",
        help="日志根目录，其下应为 <YYYY-MM>/<YYYY-MM-DD>/（默认 logs，相对当前目录）",
    )
    ap.add_argument("--ledger", default="main", choices=sorted(LEDGER_PATHS))
    ap.add_argument("--since", default=None, help="窗口起点（含），按建仓时间")
    ap.add_argument("--until", default=None, help="窗口终点（含），按建仓时间")
    ap.add_argument("--out", default=None, help="输出前缀；默认 reports/review_<ledger>")
    ap.add_argument("--min-effective-blocks", type=int, default=30)
    ap.add_argument("--fail-on-inconclusive", action="store_true", help="结论为 INCONCLUSIVE 时返回码 1")
    args = ap.parse_args()

    since_ts = parse_ts(args.since)
    until_ts = parse_ts(args.until)
    logs_root = Path(args.logs_root).expanduser()
    if not logs_root.is_absolute():
        # 相对路径按当前工作目录解释；在仓库根运行时与旧默认 ROOT/logs 完全等价
        logs_root = (Path.cwd() / logs_root).resolve()

    files = discover(args.ledger, logs_root, since_ts, until_ts)
    if not files:
        raise SystemExit(f"在 {logs_root} 下没找到 ledger={args.ledger} 的日切片文件")

    events = load_event_files(files)
    positions = rebuild_positions(events, ledger=args.ledger)
    window = select_window(positions, since_ts=since_ts, until_ts=until_ts, closed_only=True)

    report = build_report(
        window,
        ledger=args.ledger,
        window={
            "since": datetime.fromtimestamp(since_ts, tz=timezone.utc).isoformat() if since_ts else None,
            "until": datetime.fromtimestamp(until_ts, tz=timezone.utc).isoformat() if until_ts else None,
            "filter": "entry_ts",
        },
        source_files=[str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p) for p in files],
    )
    # 用命令行门槛覆盖默认
    from src.reporting import ledger_metrics as lm

    report["verdict"] = lm.decide_verdict(window, min_effective_blocks=args.min_effective_blocks)

    out_prefix = Path(args.out) if args.out else (ROOT / "reports" / f"review_{args.ledger}")
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    json_path = out_prefix.with_suffix(".json")
    md_path = out_prefix.with_suffix(".md")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    s, c, v = report["summary"], report["concentration"], report["verdict"]
    print(f"[{args.ledger}] 文件 {len(files)} 个，已平仓 {s['trade_count']} 笔，"
          f"净额(net_pnl_full) {s['net_pnl_full']:+.6f} USDT")
    print(f"  胜率 {s['win_rate']:.4f} | PF {s['profit_factor']} | 期望 {s['expectancy']:+.6f} | "
          f"成本/毛利 {s['cost_to_gross']}")
    print(f"  集中度：top1 占净额 {c['top1_share_of_net']} / 占毛利 {c['top1_share_of_gross_profit']}"
          f" | 剔除最大赢家后 {c['ex_top1_net_pnl']:+.6f} | HHI {c['hhi_abs']}")
    print(f"  有效块 {v['n_effective_blocks']} / 名义 {v['n_nominal']} → 样本 **{v['sample_verdict']}**，"
          f"边际 **{v['edge_verdict']}**"
          + (f"（{'；'.join(v['reasons'] + v['edge_reasons'])}）"
             if (v["reasons"] or v["edge_reasons"]) else ""))
    print(f"  写出 {json_path.name} / {md_path.name}")

    if args.fail_on_inconclusive and v["sample_verdict"] != "SUFFICIENT":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
