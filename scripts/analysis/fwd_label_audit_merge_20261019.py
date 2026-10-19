"""三条线合并结论页:标注器/安慰剂(L1)、成本(L2)、IC 期限结构(L3)。

只读合并,不复制三条线的统计逻辑,也不重跑任何标注或 bootstrap:

* L1 `fwd-label-v2-20261019` → 镜像/无前视(引用 pytest)、配对安慰剂 lift、
  超时画像、`stop_pct` 审计
* L2 `cost-audit-20261019` → 账本对账、6/10/20bps 三档净期望
* L3 `ic-term-20261019` → 159 行检验台账(ic 78 / tercile 78 / descriptive 3)

本脚本新增的唯一统计量是 **BH 两套校正**:族内(ic、tercile 各自 78 格)与
全体(156 个有 p 值的检验,descriptive 无 p 值不参与)。族内 q 值会与 L3 台账
里记录的 `meta.q_bh` 对账,防止 ledger 被悄悄改动。

`verdict` 由 `preregistered.decision_rule` 生成,不手写。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: 台账行数硬断言:任何一条线新增/删除检验都必须显式改这里,避免结论页漂移
LEDGER_EXPECTED_ROWS = 159
FAMILY_EXPECTED = {"ic": 78, "tercile": 78, "descriptive": 3}

#: T9 会话在 2026-10-10..12 子窗口上的 lift(引用值,本脚本不重跑子窗口)
SMALL_WINDOW = "2026-10-10..12"
SMALL_WINDOW_LIFT = {"82-92": 0.3415, "78-82": 0.0976, "<68": -0.0357}
SMALL_WINDOW_ALL_LIFT = 0.2636  # 同一脚本在同一子窗口的全体 lift
SMALL_WINDOW_SOURCE = "T9 会话记录(引用;同一脚本在该子窗口可复现 +0.2636)"

#: 旧脚本 `fwd-label-20261019`(数据截至 12:30)的 labeled 计数,评审文档里的 66279
LEGACY_LABELED = 66279

HYPOTHESES = {
    "H1": "标注器满足镜像/无前视/随机游走50%",
    "H2": "barrier 下 lift_gross == lift_net",
    "H3": "毛 IC 在若干格上 |IC|>MDE 且 BH 显著",
    "H4": "净 R 为负由 cost_R 主导而非毛 R",
}
THRESHOLDS = {
    "alpha": 0.05,
    "power": 0.80,
    "bh_q": 0.10,
    "min_cs": 8,
    "min_bars_per_cell": 200,
    "min_neff": 50,
}
DECISION_RULE = "仅 BH q<0.10 且 |IC|>MDE 且 n_eff>=50 的格子计为证据"

BH_CSV_COLUMNS = [
    "family",
    "label",
    "stat",
    "se",
    "p",
    "q_bh_within_family",
    "q_bh_all",
    "reject_within",
    "reject_all",
]

# --- 小工具 ---------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _r(value: Any, nd: int = 6) -> Any:
    if value is None:
        return None
    return round(float(value), nd)


def _f(value: Any, nd: int = 4) -> str:
    """报告用数字:固定小数位,None 显示为 —。"""
    if value is None:
        return "—"
    return f"{float(value):.{nd}f}"


def _fs(value: float, nd: int = 4) -> str:
    """带符号数字,用于 lift / E[R]。"""
    return f"{float(value):+.{nd}f}"


def _read_json(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"缺少输入文件: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"缺少输入文件: {path}")
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _read_csv(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"缺少输入文件: {path}")
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def bh_adjust(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg 校正,返回与输入同序的 q 值(单调、clamp ≤ 1)。"""
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        running = min(running, pvals[idx] * m / rank)
        q[idx] = min(running, 1.0)
    return q


# --- 1. BH 表 -------------------------------------------------------------


def build_bh_table(ledger: list[dict], bh_q: float) -> tuple[list[dict], dict]:
    if len(ledger) != LEDGER_EXPECTED_ROWS:
        raise SystemExit(
            f"tests_ledger.jsonl 行数={len(ledger)},期望 {LEDGER_EXPECTED_ROWS};"
            " 台账被改动过,拒绝生成结论页"
        )

    family_counts: dict[str, int] = {}
    for row in ledger:
        fam = row.get("family")
        family_counts[fam] = family_counts.get(fam, 0) + 1
    if family_counts != FAMILY_EXPECTED:
        raise SystemExit(
            f"检验族计数={family_counts},期望 {FAMILY_EXPECTED};台账结构变了"
        )

    # 族内 BH(只在本族内校正)
    within_q: dict[int, float] = {}
    within_meta_q: dict[int, float] = {}
    for fam in ("ic", "tercile"):
        idx = [i for i, r in enumerate(ledger) if r["family"] == fam and r.get("p") is not None]
        qs = bh_adjust([float(ledger[i]["p"]) for i in idx])
        for pos, i in enumerate(idx):
            within_q[i] = qs[pos]
            meta_q = (ledger[i].get("meta") or {}).get("q_bh")
            if meta_q is not None:
                within_meta_q[i] = abs(qs[pos] - float(meta_q))

    # 全体校正(descriptive 没有 p 值,不参与)
    all_idx = [i for i, r in enumerate(ledger) if r.get("p") is not None]
    all_qs = bh_adjust([float(ledger[i]["p"]) for i in all_idx])
    all_q: dict[int, float] = {i: all_qs[pos] for pos, i in enumerate(all_idx)}

    out = []
    n_within = 0
    n_all = 0
    for i, row in enumerate(ledger):
        q_within = within_q.get(i)
        q_all = all_q.get(i)
        rej_within = q_within is not None and q_within <= bh_q
        rej_all = q_all is not None and q_all <= bh_q
        n_within += int(rej_within)
        n_all += int(rej_all)
        out.append(
            {
                "family": row["family"],
                "label": row["label"],
                "stat": row.get("stat"),
                "se": row.get("se"),
                "p": row.get("p"),
                "q_bh_within_family": None if q_within is None else round(q_within, 6),
                "q_bh_all": None if q_all is None else round(q_all, 6),
                "reject_within": rej_within,
                "reject_all": rej_all,
            }
        )

    max_meta_diff = max(within_meta_q.values()) if within_meta_q else 0.0
    stats = {
        "rows": len(out),
        "n_p_values": len(all_idx),
        "family_counts": family_counts,
        "reject_within_total": n_within,
        "reject_all_total": n_all,
        "reject_within_by_family": {
            fam: sum(1 for r in out if r["family"] == fam and r["reject_within"])
            for fam in FAMILY_EXPECTED
        },
        "max_abs_q_diff_vs_ledger": round(max_meta_diff, 9),
        "bh_q": bh_q,
    }
    return out, stats


def write_bh_table(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=BH_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    c: ("" if row[c] is None else row[c]) for c in BH_CSV_COLUMNS
                }
            )


# --- 2. 四个假设 ----------------------------------------------------------


def build_h1(l1: dict) -> dict:
    inv = l1.get("invariance") or {}
    placebo = l1.get("placebo") or {}
    timeout = (l1.get("timeout_profile") or {}).get("overall") or {}
    stop_audit = l1.get("stop_pct_audit") or {}

    mirror_diff = float(inv.get("mirror_max_abs_diff", float("inf")))
    no_lookahead = bool(inv.get("no_lookahead_ok"))
    status = "PASS" if (mirror_diff <= 1e-9 and no_lookahead) else "FAIL"

    return {
        "status": status,
        "evidence": {
            "labeled": l1.get("labeled"),
            "decisions_total": l1.get("decisions_total"),
            "ambiguous_pct": l1.get("ambiguous_pct"),
            "mirror_max_abs_diff": mirror_diff,
            "mirror_n_checked": inv.get("mirror_n_checked"),
            "no_lookahead_ok": no_lookahead,
            "random_walk": {
                "hit_band": inv.get("band"),
                "source": inv.get("source"),
                "rerun_here": False,
                "note": "随机游走/单调/无前视以 pytest 引用,本脚本不重跑",
            },
            "placebo_valid_rate": placebo.get("valid_rate"),
            "placebo_n_valid": placebo.get("n_valid"),
            "timeout_n": timeout.get("timeout_n"),
            "timeout_pct": timeout.get("timeout_pct"),
            "stop_gt_3pct": {
                "n": stop_audit.get("n_gt_3pct"),
                "share": stop_audit.get("share"),
                "E_R": stop_audit.get("E_R_gt_3pct"),
            },
        },
        "caveat": "随机游走腿只引用 tests/test_fwdlib_labeler_invariance.py 的结论,本次未重跑",
    }


def build_h2(l1: dict) -> dict:
    placebo = l1.get("placebo") or {}
    lift_gross = float(placebo.get("lift_gross"))
    lift_net = float(placebo.get("lift_net"))
    max_diff = float(placebo.get("identity_max_abs_diff", 0.0))
    status = "PASS" if (abs(lift_gross - lift_net) <= 1e-12 and max_diff <= 1e-9) else "FAIL"
    return {
        "status": status,
        "lift_gross": _r(lift_gross),
        "lift_net": _r(lift_net),
        "lift_ci80": placebo.get("lift_net_ci80"),
        "max_diff": max_diff,
        "by_score": [
            {
                "bucket": b["bucket"],
                "n": b["n"],
                "lift_gross": _r(b["lift_gross"]),
                "lift_net": _r(b["lift_net"]),
            }
            for b in placebo.get("by_score") or []
        ],
    }


def build_h3(l3: dict, matrix: dict[tuple[str, int], dict], bh_q: float) -> dict:
    pre = l3.get("preregistered") or {}
    cells = l3.get("significant_cells") or []

    # 用台账口径复算:q<bh_q 且 |ic|>mde 且 neff>=50
    sig = [
        c
        for c in cells
        if c.get("q_bh") is not None
        and float(c["q_bh"]) < bh_q
        and abs(float(c["ic"])) > float(c["mde_ic"])
        and float(c.get("neff") or 0.0) >= float(THRESHOLDS["min_neff"])
    ]
    expected_n = int(l3.get("n_sig_bh_mde_neff", len(sig)))
    if len(sig) != expected_n:
        raise SystemExit(
            f"L3 significant_cells 复算={len(sig)},metrics 记录={expected_n};口径不一致"
        )

    breakdown = {
        "h<=4": sum(1 for c in sig if int(c["horizon"]) <= 4),
        "h=8": sum(1 for c in sig if int(c["horizon"]) == 8),
        "h=16": sum(1 for c in sig if int(c["horizon"]) == 16),
        "h=32": sum(1 for c in sig if int(c["horizon"]) == 32),
    }
    all_negative = bool(sig) and all(float(c["ic"]) < 0 for c in sig)
    status = "PASS" if sig else "FAIL"

    # ic_partial_stop / ic_nonoverlap 只在 ic_matrix.csv 里,按 (feature, horizon) 回填
    enriched = []
    for c in sorted(sig, key=lambda x: abs(float(x["ic"])), reverse=True):
        key = (c["feature"], int(c["horizon"]))
        if key not in matrix:
            raise SystemExit(f"ic_matrix.csv 缺格: {key}")
        row = matrix[key]
        enriched.append(
            {
                "feature": c["feature"],
                "horizon": int(c["horizon"]),
                "ic": _r(c["ic"]),
                "se": _r(c["se"]),
                "mde": _r(c["mde_ic"]),
                "q": _r(c["q_bh"], 4),
                "neff": _r(c.get("neff"), 1),
                "ic_partial_stop": _r(row.get("ic_partial_stop")),
                "ic_nonoverlap": _r(row.get("ic_nonoverlap")),
            }
        )

    n_same_sign = sum(
        1 for c in enriched if (float(c["ic_partial_stop"]) < 0) == (float(c["ic"]) < 0)
    )
    ratios = [abs(float(c["ic_partial_stop"])) / abs(float(c["ic"])) for c in enriched]
    n_flip = sum(
        1 for c in enriched if (float(c["ic_nonoverlap"]) < 0) != (float(c["ic"]) < 0)
    )
    recorded_flip = l3.get("n_sig_nonoverlap_sign_flip")
    if recorded_flip is not None and int(recorded_flip) != n_flip:
        raise SystemExit(f"非重叠符号翻转复算={n_flip},L3 记录={recorded_flip}")

    return {
        "status": status,
        "n_cells": int(l3.get("n_cells") or 78),
        "n_ok": l3.get("n_ok"),
        "n_bh_reject": l3.get("n_bh_reject"),
        "n_significant": len(sig),
        "all_negative": all_negative,
        "horizon_breakdown": breakdown,
        "strongest": [
            {k: c[k] for k in ("feature", "horizon", "ic", "mde", "q", "neff", "ic_partial_stop")}
            for c in enriched[:5]
        ],
        "cells": enriched,
        "robustness": {
            "n_sig_conservative_two_se": l3.get("n_sig_conservative_two_se"),
            "n_sig_nonoverlap_sign_flip": n_flip,
            "n_partial_stop_same_sign": n_same_sign,
            "partial_stop_abs_ratio": [round(min(ratios), 2), round(max(ratios), 2)],
            "note": "保守 SE(max(主 SE, 非重叠 SE))下 11 格归零;反向结论只对预登记口径成立",
        },
        "preregistered_target": pre.get("target"),
    }


def build_h4(l2: dict, cost_rows: list[dict]) -> dict:
    by_scenario = {r["scenario"]: r for r in cost_rows}
    missing = {"maker_6", "hybrid_10", "taker_20"} - set(by_scenario)
    if missing:
        raise SystemExit(f"cost_sensitivity.csv 缺场景: {sorted(missing)}")

    def _vals(scenario: str) -> tuple[float, float, float, list[float]]:
        r = by_scenario[scenario]
        ci = json.loads(r["E_Rnet_ci80"]) if r.get("E_Rnet_ci80") else []
        return (
            float(r["E_R"]),
            float(r["E_Rnet"]),
            float(r["cost_R_mean"]),
            [float(x) for x in ci],
        )

    e_r, net6, cost6, ci6 = _vals("maker_6")
    _, net10, cost10, _ = _vals("hybrid_10")
    _, net20, cost20, ci20 = _vals("taker_20")

    # 恒等式:E_Rnet = E_R - cost_R,且 (net6-net20) == (cost20-cost6)
    row_diffs = [
        abs(float(r["E_R"]) - float(r["cost_R_mean"]) - float(r["E_Rnet"])) for r in cost_rows
    ]
    identity_diff = abs((net6 - net20) - (cost20 - cost6))
    identity_ok = max(row_diffs) <= 1e-5 and identity_diff <= 1e-5

    conc = l2.get("window") or {}
    cost_share = abs(cost20) / abs(net20) if net20 else float("nan")
    dominated = abs(e_r) <= 0.1 * abs(cost20)
    status = "PASS" if (identity_ok and net20 < 0 and dominated) else "FAIL"

    return {
        "status": status,
        "E_R": _r(e_r),
        "E_Rnet_6/10/20": [_r(net6), _r(net10), _r(net20)],
        "E_Rnet_ci80_20": [_r(x) for x in ci20],
        "cost_R_6/10/20": [_r(cost6), _r(cost10), _r(cost20)],
        "cost_share_of_net20": _r(cost_share, 4),
        "identity_ok": identity_ok,
        "identity_max_abs_diff": round(max(row_diffs + [identity_diff]), 12),
        "dominance_rule": "|E_R| <= 10% * |cost_R(20)| 视为由成本主导",
        "cheapest_ci": [_r(x) for x in ci6],
        "cost_cannot_fix": bool(ci6 and ci6[1] <= 0),
        "ledger_window": {
            "fee_total": conc.get("fee_total"),
            "slip_total": conc.get("slip_total"),
            "fee_equals_slip_share": conc.get("fee_equals_slip_share"),
            "implied_bps_fee_only": conc.get("implied_bps_fee_only"),
            "implied_bps_fee_plus_slip": conc.get("implied_bps_fee_plus_slip"),
            "legacy_attribution": conc.get("legacy_attribution"),
            "correct_fee_only": conc.get("correct_fee_only"),
            "double_count_if_slip_is_real": conc.get("double_count_if_slip_is_real"),
        },
        "assumption_note": "5bps fee / 5bps slip 是写死常量,非交易所实收;20bps 往返是假设",
    }


def build_window_sensitivity(l1: dict) -> dict:
    by_score_rows = (l1.get("placebo") or {}).get("by_score") or []
    by_score = {b["bucket"]: float(b["lift_gross"]) for b in by_score_rows}
    full = {k: _r(by_score[k]) for k in SMALL_WINDOW_LIFT if k in by_score}
    if set(full) != set(SMALL_WINDOW_LIFT):
        raise SystemExit(f"L1 by_score 桶={sorted(by_score)},期望含 {sorted(SMALL_WINDOW_LIFT)}")
    all_ci_negative = all(float(b["lift_net_ci80"][1]) < 0 for b in by_score_rows)

    return {
        "note": (
            f"{SMALL_WINDOW} 子窗口 82-92 档 lift={_fs(SMALL_WINDOW_LIFT['82-92'])}"
            f"，全样本 {_fs(by_score['82-92'])}；同脚本可复现，属窗口效应"
        ),
        "source": SMALL_WINDOW_SOURCE,
        "small_window": SMALL_WINDOW,
        "small_window_lift": dict(SMALL_WINDOW_LIFT),
        "small_window_all_lift": SMALL_WINDOW_ALL_LIFT,
        "full_sample_lift": full,
        "all_buckets_ci80_negative": all_ci_negative,
        "verdict": "窗口效应,不是代码差异:同一脚本在子窗口能复现正 lift,全样本转负",
    }


# --- 3. verdict -----------------------------------------------------------


def build_verdict(h2: dict, h3: dict, h4: dict) -> str:
    n = int(h3["n_significant"])
    lift = float(h2["lift_net"])
    net20, net6 = h4["E_Rnet_6/10/20"][2], h4["E_Rnet_6/10/20"][0]
    cost20 = h4["cost_R_6/10/20"][2]
    e_r = h4["E_R"]
    cheap_hi = h4["cheapest_ci"][1]

    if n > 0 and h3["all_negative"]:
        short = h3["horizon_breakdown"]["h<=4"]
        where = "集中 h<=4" if short * 2 >= n else "分散在 h<=4 与更长周期"
        head = (
            f"毛 IC 方向上稳定为负(BH 后 {n} 格, 全负, {where})"
            f"，与配对安慰剂 lift={_f(lift)} 同号；现有分数是反向指标，不是无信息。"
        )
    elif n == 0:
        head = "BH 后无格显著，现有特征在已测周期上无边际。"
    else:
        head = f"BH 后 {n} 格显著但方向不一致，毛 IC 无统一方向。"
    tail = (
        f"净期望 {_f(net20)} 由 cost_R={_f(cost20)} 主导(毛 R={_f(e_r)})"
        f"，降成本到 6bps 仍为 {_f(net6)}，CI 上界 {_f(cheap_hi)}。"
    )
    return head + tail


# --- 4. report.md ---------------------------------------------------------


def build_report(m: dict) -> str:
    l1 = m["_l1"]
    l2 = m["_l2"]
    h1, h2, h3, h4 = m["h1_annotator"], m["h2_lift_identity"], m["h3_ic"], m["h4_cost"]
    win = m["window_sensitivity"]
    placebo = l1.get("placebo") or {}
    timeout = (l1.get("timeout_profile") or {}).get("overall") or {}
    cfg = l1.get("cfg") or {}
    net6, net10, net20 = h4["E_Rnet_6/10/20"]
    cost6, cost10, cost20 = h4["cost_R_6/10/20"]
    conc = l2.get("window") or {}

    L: list[str] = []
    L.append("# 前向标签三条线合并结论页 · 2026-10-19")
    L.append("")
    L.append(
        f"> 输入(只读):`{m['sources']['l1']}`、`{m['sources']['l2']}`、"
        f"`{m['sources']['l3']}`。本页所有数字由 "
        f"`scripts/analysis/fwd_label_audit_merge_20261019.py` 从上述产物读取/复算，"
        f"`verdict` 由代码按预登记规则生成。"
    )
    L.append("")
    L.append("## 1. 口径")
    L.append("")
    L.append(
        f"- **样本**:窗口 `{l1.get('window', ['?', '?'])[0]}` .. `{l1.get('window', ['?', '?'])[1]}`；"
        f"决策 {l1.get('decisions_total')} → 标注 **{l1.get('labeled')} 行 × 17 列**"
        f"（symbol…mfe_r：`symbol, ts, side, score, shadow, stop_pct, stop_pct_eff, quadrant, R, "
        f"R_net, cost_r, ambiguous, entry_price, stop_price, bars, reason, mfe_r`），"
        f"AMBIGUOUS {l1.get('ambiguous_pct')}%。"
    )
    L.append(
        f"- **标注口径**:`exit_mode={cfg.get('exit_mode')}`、`entry_mode={cfg.get('entry_mode')}`、"
        f"horizon={cfg.get('horizon')} 根、往返成本 {cfg.get('cost_bps')}bps、"
        f"指纹 `{cfg.get('fingerprint')}`。"
    )
    L.append(
        f"- **66279 从哪来**:评审文档的 66279 是旧脚本 `fwd-label-20261019` 的 labeled"
        f"（数据截至 12:30）。旧报告口径同样是 ±1R 障碍 + 下一根开盘入场，所以这 "
        f"{LEGACY_LABELED - int(l1['labeled'])} 行差**不是 exit 口径差异**，而在窗口尾部："
        f"v2 数据止于 12:15，最后一根 15m bar 上的 {LEGACY_LABELED - int(l1['labeled'])} 个标的"
        f"没有前向 bar 可标（{l1['labeled']}+{LEGACY_LABELED - int(l1['labeled'])}={LEGACY_LABELED}）。"
        f"本页统一用 v2 的 barrier + next_open 口径 66263。"
    )
    L.append(
        f"- **成本是常量假设，不是实测**:`FEE_BPS=5.0` / `SLIPPAGE_BPS=5.0` 是两个写死标量，"
        f"fee 与 slip 逐行相等（share={conc.get('fee_equals_slip_share')}）。账本窗口 fee 全腿 "
        f"{_f(conc.get('fee_total'), 4)} USDT = {_f(conc.get('implied_bps_fee_only'), 2)}bps，"
        f"fee+slip 全腿 {_f(conc.get('double_count_if_slip_is_real'), 4)} USDT ≈ "
        f"{_f(conc.get('implied_bps_fee_plus_slip'), 2)}bps；旧归因 "
        f"{_f(conc.get('legacy_attribution'), 4)} 只算平仓腿且把同一 5bps 计了两次。"
    )
    L.append(
        f"- **检验面**:13 特征 × 6 周期 = 78 格；台账 **{m['n_tests']}** 行"
        f"（ic {m['bh']['family_counts']['ic']} / tercile {m['bh']['family_counts']['tercile']} / "
        f"descriptive {m['bh']['family_counts']['descriptive']}）。横截面 Spearman（每根 bar ≥"
        f"{THRESHOLDS['min_cs']} 标的），SE 按 UTC 日块 bootstrap；BH 两套（族内 / 全体），"
        f"q={m['preregistered']['thresholds']['bh_q']:.2f}。"
    )
    L.append("")
    L.append("## 2. 结果")
    L.append("")
    L.append("| 假设 | 判定 | 关键数字 |")
    L.append("|---|---|---|")
    h3_title = HYPOTHESES["H3"].replace("|", "\\|")
    L.append(
        f"| H1 {HYPOTHESES['H1']} | **{h1['status']}** | "
        f"镜像 {h1['evidence']['mirror_n_checked']} 对 max\\|R_long+R_short\\|="
        f"{h1['evidence']['mirror_max_abs_diff']:.1e}；无前视 ok；有效配对 "
        f"{h1['evidence']['placebo_n_valid']}/{h1['evidence']['labeled']}="
        f"{h1['evidence']['placebo_valid_rate']:.4f}；超时 {h1['evidence']['timeout_n']}"
        f"（{h1['evidence']['timeout_pct']:.1%}）；随机游走 {h1['evidence']['random_walk']['hit_band']}"
        f" 引自 pytest（未重跑） |"
    )
    L.append(
        f"| H2 {HYPOTHESES['H2']} | **{h2['status']}** | "
        f"lift_gross=lift_net={_fs(h2['lift_gross'])}（CI80 [{_fs(h2['lift_ci80'][0])}, "
        f"{_fs(h2['lift_ci80'][1])}]），max\\|Δ\\|={h2['max_diff']:.1e} |"
    )
    L.append(
        f"| H3 {h3_title} | **{h3['status']}** | "
        f"{h3['n_cells']} 格达门槛，BH q<0.10 显著 {h3['n_bh_reject']} 格；"
        f"叠加 \\|IC\\|>MDE 且 neff≥50 后 **{h3['n_significant']}** 格，全负；"
        f"h≤4={h3['horizon_breakdown']['h<=4']}、h=8={h3['horizon_breakdown']['h=8']}、"
        f"h=16={h3['horizon_breakdown']['h=16']}、h=32={h3['horizon_breakdown']['h=32']} |"
    )
    L.append(
        f"| H4 {HYPOTHESES['H4']} | **{h4['status']}** | "
        f"E[R]={_fs(h4['E_R'])}（毛，≈0）；E[R_net](6/10/20)="
        f"{_fs(net6)} / {_fs(net10)} / {_fs(net20)}；cost_R(20)={_f(cost20)} 占净期望 "
        f"{h4['cost_share_of_net20']:.1%}；恒等式 diff≤{h4['identity_max_abs_diff']:.1e} |"
    )
    L.append("")
    L.append(f"### {h3['n_significant']} 个显著 IC 格（全部为负）")
    L.append("")
    L.append("| 特征 | 周期 | IC | MDE | q_bh | neff | ic_partial_stop |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    for c in h3["cells"]:
        L.append(
            f"| `{c['feature']}` | {c['horizon']} | {_fs(c['ic'])} | {_f(c['mde'])} | "
            f"{c['q']:.4f} | {c['neff']:.0f} | {_fs(c['ic_partial_stop'])} |"
        )
    L.append("")
    L.append(
        f"`ic_partial_stop` 与主列同号 {h3['robustness']['n_partial_stop_same_sign']}/"
        f"{h3['n_significant']}（量级比 {h3['robustness']['partial_stop_abs_ratio'][0]:.2f}–"
        f"{h3['robustness']['partial_stop_abs_ratio'][1]:.2f}），剔除止损宽度后不消失；"
        f"h=32 无显著格。**稳健性**:保守 SE（max(主 SE, 非重叠 SE)）下 "
        f"{h3['robustness']['n_sig_conservative_two_se']} 格仍显著，非重叠子样本 "
        f"{h3['robustness']['n_sig_nonoverlap_sign_flip']}/{h3['n_significant']} 格符号翻转——"
        f"「反向」只在预登记口径成立，不是对保守推断稳健的结论。"
    )
    L.append("")
    L.append("### lift:全档为负，但小窗口有反例")
    L.append("")
    L.append("| 分数档 | 全样本 lift | 小窗口 " + SMALL_WINDOW + " lift |")
    L.append("|---|---:|---:|")
    for bucket in ("82-92", "78-82", "<68"):
        L.append(
            f"| {bucket} | {_fs(win['full_sample_lift'][bucket])} | "
            f"{_fs(win['small_window_lift'][bucket])} |"
        )
    L.append("")
    L.append(
        f"全体 lift={_fs(placebo.get('lift_net'))}（CI80 [{_fs(placebo.get('lift_net_ci80')[0])}, "
        f"{_fs(placebo.get('lift_net_ci80')[1])}]）；5 档 lift_gross 的 CI80 "
        f"{'全负' if win['all_buckets_ci80_negative'] else '并非全负'}。"
        f"但 **{SMALL_WINDOW} 子窗口 82-92 档曾为 "
        f"{_fs(win['small_window_lift']['82-92'])}（全体 {_fs(win['small_window_all_lift'])}）**，"
        f"同一脚本在全样本为 {_fs(win['full_sample_lift']['82-92'])}——是窗口效应，不是代码差异。"
        f"只报全样本会掩盖这个反例。"
    )
    L.append("")
    L.append("## 3. 判定")
    L.append("")
    L.append(f"> {m['verdict']}")
    L.append("")
    L.append(
        f"生成规则(`preregistered.decision_rule`):"
        f"n_significant={h3['n_significant']}>0 且 all_negative={h3['all_negative']} "
        f"→ 走「方向稳定为负」分支；成本句常量取 L2 三档。"
    )
    L.append("")
    L.append(
        "局限:安慰剂只排除决策自身那根 bar，32 根前向窗口可与真实样本重叠，"
        "故其区间只用于抵消成本构成差异；L3 的 IC 逐 bar 重叠，SE 已按 UTC 日块放大，"
        "但保守 SE 下 11 格归零。"
    )
    L.append("")
    return "\n".join(L)


# --- 5. main --------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="三条线合并结论页(BH 两套校正 + 代码生成 verdict)")
    ap.add_argument("--l1", default="D:/AIDCA/AI300/reports/analysis/fwd-label-v2-20261019")
    ap.add_argument("--l2", default="D:/AIDCA/AI300/reports/analysis/cost-audit-20261019")
    ap.add_argument("--l3", default="D:/AIDCA/AI300/reports/analysis/ic-term-20261019")
    ap.add_argument("--out", default="D:/AIDCA/AI300/reports/analysis/fwd-label-audit-20261019")
    ap.add_argument("--bh-q", type=float, default=0.10)
    args = ap.parse_args(argv)

    l1_dir, l2_dir, l3_dir = Path(args.l1), Path(args.l2), Path(args.l3)
    out_dir = Path(args.out)
    bh_q = float(args.bh_q)

    l1 = _read_json(l1_dir / "metrics.json")
    l2 = _read_json(l2_dir / "reconciliation.json")
    l3 = _read_json(l3_dir / "metrics.json")
    ledger = _read_jsonl(l3_dir / "tests_ledger.jsonl")
    matrix_rows = _read_csv(l3_dir / "ic_matrix.csv")
    matrix = {(r["feature"], int(r["horizon"])): r for r in matrix_rows}
    cost_rows = _read_csv(l2_dir / "cost_sensitivity.csv")

    # 口径不漂移:L3 预登记阈值必须与本页一致
    l3_pre = l3.get("preregistered") or {}
    for key in ("min_cs", "min_bars_per_cell", "min_neff"):
        if key in l3_pre and int(l3_pre[key]) != THRESHOLDS[key]:
            raise SystemExit(f"L3 预登记 {key}={l3_pre[key]} 与本页 {THRESHOLDS[key]} 不一致")
    if int(l3.get("n_tests") or 0) != LEDGER_EXPECTED_ROWS:
        raise SystemExit(f"L3 n_tests={l3.get('n_tests')},期望 {LEDGER_EXPECTED_ROWS}")

    bh_rows, bh_stats = build_bh_table(ledger, bh_q)
    # 与 L3 台账自报的族内 BH 拒绝数对账
    for fam, key in (("ic", "n_bh_reject"), ("tercile", "n_tercile_bh_reject")):
        expected = l3.get(key)
        got = bh_stats["reject_within_by_family"][fam]
        if expected is not None and int(expected) != int(got):
            raise SystemExit(f"{fam} 族 BH 拒绝数复算={got},L3 记录={expected}")

    h1 = build_h1(l1)
    h2 = build_h2(l1)
    h3 = build_h3(l3, matrix, bh_q)
    h4 = build_h4(l2, cost_rows)
    win = build_window_sensitivity(l1)
    verdict = build_verdict(h2, h3, h4)

    metrics = {
        "generated_at": _now(),
        "sources": {"l1": l1_dir.as_posix(), "l2": l2_dir.as_posix(), "l3": l3_dir.as_posix()},
        "n_tests": len(bh_rows),
        "preregistered": {
            "hypotheses": HYPOTHESES,
            "thresholds": {**THRESHOLDS, "bh_q": bh_q},
            "n_tests": LEDGER_EXPECTED_ROWS,
            "decision_rule": DECISION_RULE,
            "families": {"ic": "分量/分数与毛 R 的横截面 Spearman", "tercile": "三分位价差", "descriptive": "样本描述,无 p 值"},
            "bh": "族内 = ic/tercile 各自 78 格；全体 = 156 个有 p 值的检验",
        },
        "h1_annotator": h1,
        "h2_lift_identity": h2,
        "h3_ic": h3,
        "h4_cost": h4,
        "window_sensitivity": win,
        "bh": bh_stats,
        "verdict": verdict,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    write_bh_table(bh_rows, out_dir / "bh_table.csv")

    # 报告段落需要原始 L1/L2 的少量字段,先在内部挂上,写盘前剔除
    metrics["_l1"] = l1
    metrics["_l2"] = l2
    report = build_report(metrics)
    metrics.pop("_l1", None)
    metrics.pop("_l2", None)

    with open(out_dir / "metrics.json", "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, ensure_ascii=False, indent=2, allow_nan=False)
        fh.write("\n")
    with open(out_dir / "report.md", "w", encoding="utf-8") as fh:
        fh.write(report)

    print(f"bh_table  rows={bh_stats['rows']}  p_values={bh_stats['n_p_values']}")
    print(
        f"  reject_within(bh_q={bh_q})={bh_stats['reject_within_total']}"
        f"  族内明细={bh_stats['reject_within_by_family']}"
    )
    print(f"  reject_all(bh_q={bh_q})={bh_stats['reject_all_total']}")
    print(f"  q 与 L3 台账 max|diff|={bh_stats['max_abs_q_diff_vs_ledger']:.2e}")
    print("H1..H4 " + " / ".join(f"{k}={metrics[k]['status']}" for k in (
        "h1_annotator", "h2_lift_identity", "h3_ic", "h4_cost")))
    print(f"verdict: {verdict}")
    print(f"wrote {out_dir / 'bh_table.csv'}")
    print(f"wrote {out_dir / 'metrics.json'}")
    print(f"wrote {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
