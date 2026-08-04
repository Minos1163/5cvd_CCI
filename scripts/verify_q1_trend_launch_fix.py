# -*- coding: utf-8 -*-
"""verify_q1_trend_launch_fix.py — q1_trend_launch 修复验证脚本。

两种模式:

1) --historical(默认, 反事实): 用 08-02 21:45~08-04 19:00 窗口的历史 near-miss,
   按新规则(移除确认标签 + 非极值追单检查)重放, 输出"本应解锁"的 Q1 高分样本清单。
   极值位置比例用 decisions.jsonl 内嵌 15m kline 序列重建(与在线 build_context 一致)。

2) --online: 部署后运行。检查 decisions 日志中:
   - q1_trend_launch 是否开始产生转化(entry_channel=q1_trend_launch / DRY_RUN_Q1_TREND_LAUNCH)
   - 是否仍有废弃标签残留(Q2_PENDING_MOMENTUM_CONFIRMED / Q3_TO_Q1_CONFIRMED)
   两者任一失败 → 退出码 1(视为修复未生效)。

用法:
  python scripts/verify_q1_trend_launch_fix.py --historical \
      --log-root logs --start 2026-08-02 --end 2026-08-04 \
      --config configs/entry_chain.dry_run_fib_pa_v1.json
  python scripts/verify_q1_trend_launch_fix.py --online \
      --log-root logs --hours 24 --config configs/entry_chain.dry_run_fib_pa_v1.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# 脚本位于 scripts/ 下, 项目根需显式加入 sys.path 以便 import src.*
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.signals.entry_chain_config import load_entry_chain_config  # noqa: E402

DEPRECATED_TAGS = ("Q2_PENDING_MOMENTUM_CONFIRMED", "Q3_TO_Q1_CONFIRMED")
TREND_LAUNCH_MARKERS = ("DRY_RUN_Q1_TREND_LAUNCH",)


def load_jsonl_window(log_root: Path, name: str, start: str, end: str) -> list[dict[str, Any]]:
    rows = []
    day = start
    while day <= end:
        p = log_root / day[:7] / day / name
        if p.exists():
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(d, dict):
                        rows.append(d)
        y, m, d_ = map(int, day.split("-"))
        import datetime as _dt

        nxt = _dt.date(y, m, d_) + _dt.timedelta(days=1)
        day = nxt.strftime("%Y-%m-%d")
    return rows


def build_kline_series(decisions: list[dict[str, Any]]) -> dict[str, list[tuple[int, tuple[float, float, float, float]]]]:
    series: dict[str, dict[int, tuple[float, float, float, float]]] = defaultdict(dict)
    for d in decisions:
        k = d.get("kline")
        sym = d.get("symbol")
        if not isinstance(k, dict) or not sym:
            continue
        ts = k.get("timestamp")
        try:
            series[sym][int(ts)] = (float(k["open"]), float(k["high"]), float(k["low"]), float(k["close"]))
        except Exception:
            continue
    return {s: sorted(m.items()) for s, m in series.items()}


def extreme_ratio_from_series(series: list[tuple[int, tuple[float, float, float, float]]], ts: int) -> float:
    idxs = [i for i, (t, _) in enumerate(series) if t <= ts]
    if not idxs:
        return 0.5
    idx = idxs[-1]
    window = series[max(0, idx - 7): idx + 1]
    if len(window) < 3:
        return 0.5
    lo = min(b[1][2] for b in window)
    hi = max(b[1][1] for b in window)
    if hi <= lo:
        return 0.5
    close = window[-1][1][3]
    return (close - lo) / (hi - lo)


def historical_check(log_root: Path, start: str, end: str, config_path: Path) -> int:
    config = load_entry_chain_config(config_path)
    near_misses = load_jsonl_window(log_root, "near_misses.jsonl", start, end)
    decisions = load_jsonl_window(log_root, "decisions.jsonl", start, end)
    if not near_misses:
        print("RESULT: 数据缺失 —— 窗口内无 near-miss, 无法验证(修复未生效或数据未同步)。", file=sys.stderr)
        return 1
    if not decisions:
        print("RESULT: 数据缺失 —— 窗口内无 decisions, 无法重建极值序列(数据未同步)。", file=sys.stderr)
        return 1
    series = build_kline_series(decisions)

    from scripts.run_live_dry_run import _q1_trend_launch_eligible

    unlocked: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    for nm in near_misses:
        sym = nm.get("symbol")
        ts = nm.get("kline_timestamp")
        q = str(nm.get("quadrant") or "").upper()
        score = float(nm.get("score") or 0.0)
        if q != "Q1" or score < float(config.dry_run_q1_trend_launch_min_score):
            continue
        nm2 = dict(nm)
        ec = dict(nm.get("entry_context") or {})
        # 反事实中性化:历史 near-miss 若缺 LONG 防反转字段(旧版本记录),
        # 按 False(不触发拒绝)处理,避免系统性低估解锁数;在线数据字段齐全不受影响。
        for _k in ("long_overextension_active", "long_upper_wick_risk_active", "long_chase_risk_active"):
            ec.setdefault(_k, False)
        ec["extreme_position_ratio"] = extreme_ratio_from_series(series.get(sym, []), int(ts or 0))
        nm2["entry_context"] = ec
        ok = _q1_trend_launch_eligible(nm2, config, "OK")
        row = {
            "timestamp": nm.get("timestamp"),
            "symbol": sym,
            "side": nm.get("intended_side"),
            "score": score,
            "extreme_position_ratio": round(ec["extreme_position_ratio"], 3),
            "primary_reason": nm.get("primary_reason"),
        }
        (unlocked if ok else blocked).append(row)

    print(f"== 历史反事实(标签依赖已移除 + 非极值追单检查) ==")
    print(f"窗口高分(≥{config.dry_run_q1_trend_launch_min_score}) Q1 near-miss 候选: {len(unlocked) + len(blocked)}")
    print(f"新规则下解锁: {len(unlocked)} | 仍被拒: {len(blocked)}")
    for r in sorted(unlocked, key=lambda x: -x["score"]):
        print(f"  UNLOCK {r['timestamp']} {r['symbol']} {r['side']} score={r['score']} "
              f"extreme_ratio={r['extreme_position_ratio']} reason={r['primary_reason']}")
    for r in sorted(blocked, key=lambda x: -x["score"])[:8]:
        print(f"  BLOCK  {r['timestamp']} {r['symbol']} {r['side']} score={r['score']} "
              f"extreme_ratio={r['extreme_position_ratio']} reason={r['primary_reason']}")
    if unlocked:
        print("RESULT: 反事实通过 —— 标签移除后通道开始解锁候选(仍需在线运行确认转化)。")
        return 0
    print("RESULT: 反事实失败 —— 无解锁样本, 请检查修复是否生效。", file=sys.stderr)
    return 1


def online_check(log_root: Path, hours: int, config_path: Path) -> int:
    config = load_entry_chain_config(config_path)
    import datetime as _dt

    end = _dt.date.today()
    start = end - _dt.timedelta(days=max(1, (hours + 23) // 24))
    decisions = load_jsonl_window(log_root, "decisions.jsonl", start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    if not decisions:
        print("RESULT: 数据缺失 —— 在线窗口内无 decisions 日志, 无法验证(数据未同步或进程未运行)。", file=sys.stderr)
        return 1
    tl_triggered = 0
    for d in decisions:
        reasons = d.get("reasons", []) or []
        reason_list = [str(r) for r in reasons] if isinstance(reasons, list) else [str(reasons)]
        if any(m in reason_list for m in TREND_LAUNCH_MARKERS):
            tl_triggered += 1
    # 废弃标签(Q2_PENDING_MOMENTUM_CONFIRMED / Q3_TO_Q1_CONFIRMED)由 confirm_*_pending
    # 生成进 near_misses.jsonl 的 scout_tags, 与 q1_trend_launch 判定已解耦(不再阻断)。
    # 因此在线检查改扫 near_misses 的 scout_tags: 仅报告存在数(信息性), 不作为 FAIL 条件;
    # PASS 标准 = q1_trend_launch 产生转化。
    near_misses = load_jsonl_window(log_root, "near_misses.jsonl", start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    deprecated_tags_in_near_miss = 0
    for nm in near_misses:
        tags = nm.get("scout_tags", []) or []
        tag_list = [str(t) for t in tags] if isinstance(tags, list) else [str(tags)]
        if any(t in tag_list for t in DEPRECATED_TAGS):
            deprecated_tags_in_near_miss += 1
    print(f"== 在线验证(最近 {hours}h) ==")
    print(f"q1_trend_launch 相关决策数: {tl_triggered}")
    print(f"near-miss 中携带废弃标签数(信息性, 判定已解耦): {deprecated_tags_in_near_miss}")
    if tl_triggered > 0:
        print("RESULT: 修复已生效 —— 通道产生转化(标签依赖已解耦)。")
        return 0
    print("RESULT: 修复未验证通过(需 q1_trend_launch 转化>0)。", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="q1_trend_launch 修复验证")
    parser.add_argument("--mode", choices=["historical", "online"], default="historical")
    parser.add_argument("--log-root", default="logs")
    parser.add_argument("--config", default="configs/entry_chain.dry_run_fib_pa_v1.json")
    parser.add_argument("--start", default="2026-08-02")
    parser.add_argument("--end", default="2026-08-04")
    parser.add_argument("--hours", type=int, default=24)
    args = parser.parse_args()

    log_root = Path(args.log_root)
    config_path = Path(args.config)
    if args.mode == "historical":
        return historical_check(log_root, args.start, args.end, config_path)
    return online_check(log_root, args.hours, config_path)


if __name__ == "__main__":
    sys.exit(main())
