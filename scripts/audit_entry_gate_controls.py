"""闸门控制审计:为 15 道硬闸门生成机制化阳性/阴性样本,并检查门槛是否结构上可达。

背景
----
2026-10-19 的审计发现两个问题:

1. 日志里「闸门正常工作」与「闸门从未触发」完全同形(都是零次拒绝)。仅靠生产日志
   无法区分「降级通道有效」与「降级通道是装饰」。
2. LONG 侧 direct 门槛被 side offset 从 82 抬到 92,而 8 周历史里 >=92 只有 27 条,
   等于「永远拒绝」被当成「严格」。

本脚本做两件事:

* **控制样本**:对每道闸门构造一条只触发该闸门的上下文,断言返回的 reason 唯一且正确;
  再用一条干净上下文做阳性对照,证明决策链本身能产出入场动作。
* **可达性扫描**:读真实 ``decisions.jsonl``,按 side 统计 score 分布与生效门槛,
  给出「门槛以上样本数 / 占比」与「历史上是否真的出现过该侧的动作」。

只用公开函数与配置,不修改任何策略行为。退出码 1 表示有闸门控制失败。

用法::

    python scripts/audit_entry_gate_controls.py \
        --config configs/entry_chain.dry_run_fib_pa_v1.json \
        --logs logs --months 2026-09,2026-10 \
        --out logs/analysis/gate-controls/2026-10-19
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.signals.entry_chain import (
    EntryChainContext,
    _probe_threshold_offset,
    _side_threshold_offset,
    evaluate_entry_chain,
)
from src.signals.entry_chain_config import EntryChainConfig, load_entry_chain_config
from src.signals.entry_chain_gates import daily_max_trades, hard_block_reason


@dataclass(frozen=True)
class GateCase:
    """一条控制样本:只触发 ``expected`` 这一道闸门。"""

    gate: str
    expected: str
    updates: Mapping[str, Any]
    note: str = ""


def build_baseline_context(**overrides: Any) -> EntryChainContext:
    """构造一条能通过全部闸门的上下文(所有组件满分)。

    所有组件分给 1.0,是为了让阳性对照同时证明「分数的理论上限能触发 direct」;
    若这条都过不了,说明门槛在结构上不可达。
    """
    scores = {
        "trend_ema_context": 1.0,
        "flow_cvd_confirmation": 1.0,
        "cci_momentum_quality": 1.0,
        "price_action_structure": 1.0,
        "fibonacci_location": 1.0,
        "risk_reward_geometry": 1.0,
        # BASE 架构的键也填满,便于同一份基线跑两种权重表
        "background_4h": 1.0,
        "direction_1h": 1.0,
        "quality_30m": 1.0,
        "trigger_15m": 1.0,
        "cvd_flow": 1.0,
        "volatility_stop": 1.0,
        "liquidity_execution": 1.0,
        "market_regime": 1.0,
        "ema_200_gate": 1.0,
        "ema_50_quality": 1.0,
        "ema_momentum": 1.0,
    }
    base = dict(
        symbol="BTCUSDT",
        timestamp=1_800_000_000,
        side="LONG",
        component_scores=scores,
        quote_volume_24h=1_000_000_000.0,
        atr_pct=0.01,
        expected_order_size=1000.0,
        account_equity=10_000.0,
        available_margin=8_000.0,
        macro_daily_drop_pct=0.0,
        macro_weekly_drop_pct=0.0,
        usdt_premium_abnormal=False,
        wick_anomaly_active=False,
        polluted_until_ts=None,
        websocket_reconnect_recent=False,
        active_symbols=0,
        active_symbol_names=frozenset(),
        portfolio_trades_today=0,
        symbol_trades_today=0,
        current_volatility_scale=1.0,
        normal_volatility_scale=1.0,
        daily_profit_pct=0.0,
        cooldown_until_ts=None,
        symbol_exposure_pct=0.0,
        total_exposure_pct=0.0,
        same_direction_exposure_pct=0.0,
        rolling_sharpe_20=None,
        stop_pct=0.01,
        extreme_position_ratio=0.5,
    )
    base.update(overrides)
    return EntryChainContext(**base)


def gate_cases(cfg: EntryChainConfig) -> list[GateCase]:
    """按 ``hard_block_reason`` 的判定顺序构造控制样本。

    每个样本只改一个字段,且该字段至少比它前面的闸门更晚命中 —— 否则前面的闸门会
    先返回,测试就变成「验证前一道闸门」而不是当前这道。
    """
    ts = 1_800_000_000
    baseline = build_baseline_context()
    cases: list[GateCase] = []

    if cfg.blacklist_symbols:
        symbol = cfg.blacklist_symbols[0]
        cases.append(
            GateCase("blacklist", "SYMBOL_BLACKLISTED", {"symbol": symbol}, f"取配置内黑名单 {symbol}")
        )
    if cfg.watch_only_symbols:
        symbol = cfg.watch_only_symbols[0]
        cases.append(
            GateCase("watch_only", "SYMBOL_WATCH_ONLY", {"symbol": symbol}, f"取配置内观察名单 {symbol}")
        )

    cases.extend(
        [
            GateCase(
                "macro_weekly",
                "MACRO_WEEKLY_RISK",
                {"macro_weekly_drop_pct": cfg.macro_weekly_drop_block_pct},
            ),
            GateCase("wick_anomaly", "DATA_WICK_ANOMALY", {"wick_anomaly_active": True}),
            GateCase(
                "data_pollution",
                "DATA_POLLUTION_COOLDOWN",
                {"timestamp": ts, "polluted_until_ts": ts},
            ),
            GateCase(
                "position_open",
                "SYMBOL_POSITION_ALREADY_OPEN",
                {"active_symbol_names": frozenset({"BTCUSDT"})},
            ),
            GateCase(
                "max_active_symbols",
                "MAX_ACTIVE_SYMBOLS",
                {"active_symbols": cfg.max_active_symbols},
            ),
            GateCase(
                "daily_budget",
                "DAILY_TRADE_BUDGET_USED",
                {"portfolio_trades_today": daily_max_trades(baseline, cfg)},
            ),
            GateCase(
                "symbol_daily_budget",
                "SYMBOL_DAILY_TRADE_BUDGET_USED",
                {"symbol_trades_today": cfg.max_symbol_trades_per_day},
            ),
            GateCase(
                "symbol_cooldown",
                "SYMBOL_COOLDOWN_ACTIVE",
                {"timestamp": ts, "cooldown_until_ts": ts + 1},
            ),
            GateCase(
                "total_exposure",
                "TOTAL_EXPOSURE_CAP",
                {"total_exposure_pct": cfg.max_total_exposure_pct},
            ),
            GateCase(
                "same_direction_exposure",
                "SAME_DIRECTION_EXPOSURE_CAP",
                {"same_direction_exposure_pct": cfg.max_same_direction_exposure_pct},
            ),
            GateCase(
                "margin_buffer",
                "MARGIN_BUFFER_TOO_LOW",
                {"available_margin": 0.0},
            ),
            GateCase("account_equity", "ACCOUNT_EQUITY_INVALID", {"account_equity": 0.0}),
            GateCase("side_not_allowed", "SIDE_NOT_ALLOWED", {"side": "NONE"}),
        ]
    )
    return cases


def run_gate_controls(cfg: EntryChainConfig) -> dict[str, Any]:
    """逐条验证闸门,并做一次阳性对照。"""
    results: list[dict[str, Any]] = []
    failed = 0
    for case in gate_cases(cfg):
        ctx = build_baseline_context(**case.updates)
        reason = hard_block_reason(ctx, cfg)
        ok = reason == case.expected
        if not ok:
            failed += 1
        results.append(
            {
                "gate": case.gate,
                "expected": case.expected,
                "actual": reason,
                "ok": ok,
                "note": case.note,
            }
        )

    # 阳性对照:干净上下文必须不被任何闸门拦住,且真的产出入场动作。
    baseline_ctx = build_baseline_context()
    baseline_reason = hard_block_reason(baseline_ctx, cfg)
    decision = evaluate_entry_chain(baseline_ctx, cfg)
    positive_ok = baseline_reason is None and decision.action in {"DIRECT", "PROBE"}
    if not positive_ok:
        failed += 1

    return {
        "config": {
            "blacklist": list(cfg.blacklist_symbols),
            "watch_only": list(cfg.watch_only_symbols),
            "max_active_symbols": cfg.max_active_symbols,
            "max_total_exposure_pct": cfg.max_total_exposure_pct,
            "max_same_direction_exposure_pct": cfg.max_same_direction_exposure_pct,
            "margin_buffer_pct": cfg.margin_buffer_pct,
        },
        "gates": results,
        "positive_control": {
            "hard_block_reason": baseline_reason,
            "action": decision.action,
            "side": decision.side,
            "score": decision.score,
            "leverage": decision.leverage,
            "notional_hint": decision.notional_hint,
            "ok": positive_ok,
        },
        "failed": failed,
    }


def effective_thresholds(cfg: EntryChainConfig, side: str) -> dict[str, float]:
    """按 ``_score_to_action`` 的叠加规则算出该侧真正生效的三段门槛。"""
    side_upper = side.strip().upper()
    offset = _side_threshold_offset(side_upper, cfg)
    probe_offset = _probe_threshold_offset(side_upper, cfg, offset)
    return {
        "direct": cfg.direct_threshold + offset,
        "probe": cfg.probe_threshold + probe_offset,
        "watch": cfg.watch_threshold + offset,
    }


def _decision_files(log_root: Path, months: Sequence[str] | None) -> list[Path]:
    if months:
        files: list[Path] = []
        for month in months:
            files.extend(sorted((log_root / month).glob("*/decisions.jsonl")))
        return files
    return sorted(log_root.glob("*/*/decisions.jsonl"))


def threshold_reachability(
    files: Iterable[Path],
    cfg: EntryChainConfig,
) -> dict[str, Any]:
    """扫描真实决策,回答「门槛以上样本有多少、该侧动作是否真的出现过」。"""
    stats: dict[str, dict[str, Any]] = {
        side: {
            "n": 0,
            "max_score": None,
            "above_direct": 0,
            "above_probe": 0,
            "actions": {},
        }
        for side in ("LONG", "SHORT")
    }
    thresholds = {side: effective_thresholds(cfg, side) for side in stats}
    files = list(files)
    for path in files:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                side = str(row.get("side") or "").strip().upper()
                if side not in stats:
                    # 未被采纳的决策顶层 side 会被置为 NONE(EC:797),真实方向留在
                    # entry_context.side 里。只读顶层会把 95% 以上的样本静默丢掉。
                    context = row.get("entry_context")
                    if isinstance(context, Mapping):
                        side = str(context.get("side") or "").strip().upper()
                if side not in stats:
                    continue
                score = row.get("score")
                entry = stats[side]
                entry["n"] += 1
                if isinstance(score, (int, float)):
                    entry["max_score"] = score if entry["max_score"] is None else max(entry["max_score"], score)
                    if score >= thresholds[side]["direct"]:
                        entry["above_direct"] += 1
                    if score >= thresholds[side]["probe"]:
                        entry["above_probe"] += 1
                action = str(row.get("action") or "")
                entry["actions"][action] = entry["actions"].get(action, 0) + 1

    for side, entry in stats.items():
        n = entry["n"]
        entry["above_direct_pct"] = round(entry["above_direct"] / n, 6) if n else 0.0
        entry["above_probe_pct"] = round(entry["above_probe"] / n, 6) if n else 0.0
        entry["thresholds"] = thresholds[side]

    return {
        "files": len(files),
        "by_side": stats,
        "unreachable": {
            side: entry["above_direct"] == 0 and entry["actions"].get("DIRECT", 0) == 0
            for side, entry in stats.items()
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    gates = report["gate_controls"]["gates"]
    positive = report["gate_controls"]["positive_control"]
    reach = report["reachability"]
    lines = [
        "# 闸门控制审计",
        "",
        f"- 配置:`{report['config_path']}`",
        f"- 日志窗口:`{report['months'] or 'all'}`(共 {reach['files']} 个 decisions.jsonl)",
        f"- 生成时间:{report['generated_at']}",
        "",
        "## 1. 阴性控制(每道闸门必须拒绝,且 reason 唯一)",
        "",
        "| # | 闸门 | 期望 reason | 实际 | 结果 |",
        "|---|---|---|---|---|",
    ]
    for i, row in enumerate(gates, 1):
        mark = "PASS" if row["ok"] else "**FAIL**"
        lines.append(f"| {i} | {row['gate']} | `{row['expected']}` | `{row['actual']}` | {mark} |")
    lines += [
        "",
        "## 2. 阳性对照(干净上下文必须产出入场动作)",
        "",
        f"- `hard_block_reason` = `{positive['hard_block_reason']}`",
        f"- action = `{positive['action']}`, side = `{positive['side']}`, score = `{positive['score']}`",
        f"- leverage = `{positive['leverage']}`, notional_hint = `{positive['notional_hint']}`",
        f"- 结论:{'PASS' if positive['ok'] else '**FAIL**'}",
        "",
        "## 3. 门槛可达性(真实日志)",
        "",
        "| 侧 | 样本数 | 最高分 | direct 门槛 | ≥direct | 占比 | ≥probe | 占比 | 历史动作 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for side in ("LONG", "SHORT"):
        e = reach["by_side"][side]
        actions = ", ".join(f"{k}:{v}" for k, v in sorted(e["actions"].items())) or "-"
        max_score = "-" if e["max_score"] is None else f"{e['max_score']:.2f}"
        lines.append(
            f"| {side} | {e['n']} | {max_score} | {e['thresholds']['direct']:.2f} | "
            f"{e['above_direct']} | {e['above_direct_pct']:.4%} | "
            f"{e['above_probe']} | {e['above_probe_pct']:.4%} | {actions} |"
        )
    unreachable = [side for side, flag in reach["unreachable"].items() if flag]
    lines += [
        "",
        f"**结构上不可达的侧**:{', '.join(unreachable) if unreachable else '无'}",
        "",
        "> 判据:该侧「≥direct 门槛的样本数 = 0」且「历史 DIRECT 动作数 = 0」。"
        "只满足前一条时,可能是样本窗口不够;两条同时满足才判定为不可达。",
        "",
        "## 4. 结论",
        "",
        f"- 闸门控制失败数:{report['gate_controls']['failed']}",
        f"- 退出码:{1 if report['gate_controls']['failed'] else 0}",
    ]
    return "\n".join(lines) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="硬闸门控制审计 + 门槛可达性扫描")
    parser.add_argument("--config", default="configs/entry_chain.dry_run_fib_pa_v1.json")
    parser.add_argument("--logs", default="logs")
    parser.add_argument("--months", default="", help="逗号分隔的 YYYY-MM;留空扫描全部")
    parser.add_argument("--out", default="logs/analysis/gate-controls")
    args = parser.parse_args(argv)

    cfg = load_entry_chain_config(args.config)
    months = [m.strip() for m in args.months.split(",") if m.strip()] or None
    log_root = Path(args.logs)
    files = _decision_files(log_root, months)

    report = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "config_path": args.config,
        "months": args.months,
        "gate_controls": run_gate_controls(cfg),
        "reachability": threshold_reachability(files, cfg),
    }

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")

    print(json.dumps(
        {
            "gate_controls_failed": report["gate_controls"]["failed"],
            "positive_action": report["gate_controls"]["positive_control"]["action"],
            "unreachable": [s for s, f in report["reachability"]["unreachable"].items() if f],
            "out": str(out_dir),
        },
        ensure_ascii=False,
    ))
    return 1 if report["gate_controls"]["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
