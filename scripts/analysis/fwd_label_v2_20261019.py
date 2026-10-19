"""前向标签 v2 正式报告:逐条配对安慰剂 + 超时披露 + ``stop_pct`` 审计。

与 ``fwd_label_20261019.py`` 的关系
----------------------------------
旧脚本的随机基线按 ``(symbol, date)`` 分块抽 ≤20 条决策,基线样本的
``stop_pct`` 分布与总体不同,而 ``cost_R = bps/1e4/stop_pct`` 对止损宽度极其
敏感,于是「每个分数档 lift 都为负」可能只是成本构成差异。本脚本改用
:func:`fwdlib.baseline.matched_placebo` 做**逐条配对**(同 symbol、同 UTC 日、
同 side、同 ``stop_pct``、随机 bar),成本逐条抵消;lift 的区间来自按
``symbol|date`` 分块的 bootstrap。

本文件只做编排,不复制任何标注/统计逻辑:

* 标注 :func:`fwdlib.labeler.run_labeling`
* 安慰剂 :func:`fwdlib.baseline.matched_placebo` / :func:`fwdlib.baseline.lift_summary`
* 超时画像 :func:`fwdlib.labeler.timeout_profile`
* 价格/止损降级覆盖率 :func:`fwdlib.features.rebuild_price_levels`
* 账本 FIFO 覆盖率 :func:`fwdlib.ledger.attribute_legs`

不变式的处理(重要)
------------------
随机游走命中率每条路径要跑 2000 条合成序列,那是 pytest 的职责
(``tests/test_fwdlib_labeler_invariance.py``),本脚本**不重跑**。脚本里实测两项:

* **多空镜像**:随机抽 300 条真实决策,把 side 翻转后按同 ``stop_pct`` 重新标注,
  断言 ``R_long + R_short ≈ 0``(同根双触的 AMBIGUOUS 行两边都记 -1R,单独计数、
  不进 max|diff|)。
* **无前视**:随机抽 200 条决策,在本次标注的 ``bars`` 面板上原地扰动 —— 入场
  bar 之前的 bar OHLC×1.5 后 ``R/reason/bars`` 必须完全不变;把入场后首根可平仓
  bar 改成必触 target / 必触 stop,结果必须改变。两个结论写进 ``invariance`` 的
  ``no_lookahead_prior_unchanged`` / ``no_lookahead_entry_changed``。

只有随机游走命中率与单调行情以字符串引用 pytest 结论与 ``source`` 路径,不伪造数字。
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

try:
    from fwdlib.baseline import lift_summary, matched_placebo
    from fwdlib.config import LabelConfig
    from fwdlib.features import load_decisions, rebuild_price_levels
    from fwdlib.labeler import (
        _SCORE_BUCKETS,
        _STOP_BUCKETS,
        entry_and_start,
        label_barrier,
        label_ladder,
        run_labeling,
        timeout_profile,
    )
    from fwdlib.ledger import attribute_legs, load_trade_events
    from fwdlib.stats import block_bootstrap_mean
except ImportError:  # 只把仓库根放进 sys.path 时走这条
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.analysis.fwdlib.baseline import lift_summary, matched_placebo
    from scripts.analysis.fwdlib.config import LabelConfig
    from scripts.analysis.fwdlib.features import load_decisions, rebuild_price_levels
    from scripts.analysis.fwdlib.labeler import (
        _SCORE_BUCKETS,
        _STOP_BUCKETS,
        entry_and_start,
        label_barrier,
        label_ladder,
        run_labeling,
        timeout_profile,
    )
    from scripts.analysis.fwdlib.ledger import attribute_legs, load_trade_events
    from scripts.analysis.fwdlib.stats import block_bootstrap_mean

#: 默认路径相对**仓库根**解析(worktree 里就是本仓库),换机器不会写死到别人的盘符;
#: 环境变量 ``FWD_LOGS`` / ``FWD_REPORTS`` 优先,便于把产物指回主工作区。
REPO_ROOT = Path(__file__).resolve().parents[2]


def _default_logs() -> str:
    return os.environ.get("FWD_LOGS") or str(REPO_ROOT / "logs")


def _default_out(slug: str) -> str:
    base = os.environ.get("FWD_REPORTS")
    return str(Path(base) / slug) if base else str(REPO_ROOT / "reports" / "analysis" / slug)


INVARIANCE_SOURCE = "tests/test_fwdlib_labeler_invariance.py"
MIRROR_SAMPLE = 300
MIRROR_TOL = 1e-9
#: 无前视实测:抽样条数,以及「入场 bar 之前的 bar」的扰动倍数。
#: 用 1.5 而不是 1.001 —— 0.1% 的价格漂移可能落在障碍阈值内,漏检比误报更危险。
NO_LOOKAHEAD_SAMPLE = 200
NO_LOOKAHEAD_PRIOR_FACTOR = 1.5

#: 与 ``fwdlib.labeler.timeout_profile`` 完全相同的分档,CSV 的 R 分位数按同一批行算
_SCORE_GROUPS = _SCORE_BUCKETS
_STOP_GROUPS = _STOP_BUCKETS


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #

def _r(value, nd=6):
    """四舍五入到 nd 位;None / nan / inf 原样返回(None→None, nan→nan)。"""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return value
    if not math.isfinite(f):
        return f
    return round(f, nd)


def _fmt_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _quantile(values, q: float):
    """线性插值分位数(与 numpy 默认 ``linear`` 同口径)。空序列返回 None。"""
    if not values:
        return None
    data = sorted(float(v) for v in values)
    if len(data) == 1:
        return data[0]
    pos = (len(data) - 1) * q
    lo = math.floor(pos)
    hi = min(lo + 1, len(data) - 1)
    return data[lo] + (data[hi] - data[lo]) * (pos - lo)


def _placebo_valid(row: dict) -> bool:
    """行级有效标记:``placebo_valid`` 为真**且**均值是有限数。

    双重条件是为了在口径漂移(比如无有效 draw 却忘了置 False)时,CSV 里的
    ``placebo_valid`` 仍不会把 ``delta_R=0`` 的占位行标成有效观测。
    """
    mean = row.get("placebo_R_mean")
    if not row.get("placebo_valid") or mean is None:
        return False
    try:
        return math.isfinite(float(mean))
    except (TypeError, ValueError):
        return False


def _ci(values_by_block, iters: int, seed: int):
    ci = block_bootstrap_mean(values_by_block, iters=iters, seed=seed)
    return None if ci is None else [_r(ci[0]), _r(ci[1])]


# --------------------------------------------------------------------------- #
# 决策加载:保留 rebuild_price_levels 需要的降级来源字段
# --------------------------------------------------------------------------- #

def _attach_price_context(decisions: list[dict], paths: list[str]) -> None:
    """把原始记录里的 ``entry_context.stop_pct / atr_pct`` 与 ``metadata.risk_budget``
    挂回决策行。

    ``load_decisions`` 已经把 ``entry_context.stop_pct`` 提成 ``stop_pct``,但
    ``rebuild_price_levels`` 是按**三级优先级**读原始结构的;不挂回去,它只能看到
    ``atr_fallback`` 一层,provenance 会失真。这里只挂这两个小字段,不改变任何
    标注输入(标注器只读 ``stop_pct`` / ``atr_pct``)。
    """
    ctx: dict[tuple[str, int], dict] = {}
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = (r.get("kline") or {}).get("timestamp")
                sym = r.get("symbol")
                if ts is None or not sym:
                    continue
                ec = r.get("entry_context") or {}
                rb = (r.get("metadata") or {}).get("risk_budget") or {}
                ctx[(sym, int(ts))] = {
                    "entry_context": {"stop_pct": ec.get("stop_pct"), "atr_pct": ec.get("atr_pct")},
                    "risk_budget": {"stop_pct": rb.get("stop_pct")} if rb else {},
                }

    for d in decisions:
        c = ctx.get((d["symbol"], d["ts"]))
        if not c:
            continue
        d["entry_context"] = c["entry_context"]
        d["metadata"] = {"risk_budget": c["risk_budget"]}


# --------------------------------------------------------------------------- #
# 不变式:廉价镜像检查
# --------------------------------------------------------------------------- #

def _mirror_check(labeled, bars, per_symbol, index, *, entry_mode: str, horizon: int,
                  cfg: LabelConfig, seed: int) -> dict:
    """随机抽 ``MIRROR_SAMPLE`` 条决策,翻转 side 重标注,断言 ``R_long + R_short == 0``。

    同根双触时两边都必须 AMBIGUOUS 且各记 -1R —— 这类行不进 max|diff|,只计数。
    """
    n = len(labeled)
    if n == 0:
        return {"mirror_max_abs_diff": None, "n_checked": 0, "n_ambiguous_pairs": 0}
    rng = random.Random(seed)
    picks = rng.sample(range(n), min(MIRROR_SAMPLE, n))

    diffs: list[float] = []
    ambiguous = 0
    for i in picks:
        row = labeled[i]
        stop = row["stop_pct_eff"]
        flip = "SHORT" if row["side"] == "LONG" else "LONG"
        a = label_barrier(bars, per_symbol, index, row, stop, entry_mode, cfg=cfg, horizon=horizon)
        b = label_barrier(bars, per_symbol, index, {"symbol": row["symbol"], "ts": row["ts"],
                                                    "side": flip}, stop, entry_mode,
                          cfg=cfg, horizon=horizon)
        if a is None or b is None:
            raise RuntimeError(f"镜像检查标注失败: {row['symbol']} {row['ts']} {row['side']}")
        if a["ambiguous"] or b["ambiguous"]:
            if not (a["ambiguous"] and b["ambiguous"]):
                raise AssertionError(
                    f"镜像歧义不对称: {row['symbol']} {row['ts']} "
                    f"long_amb={a['ambiguous']} short_amb={b['ambiguous']}"
                )
            if a["R"] != -1.0 or b["R"] != -1.0:
                raise AssertionError(
                    f"AMBIGUOUS 未按最不利结算: {row['symbol']} {row['ts']} "
                    f"R_long={a['R']} R_short={b['R']}"
                )
            ambiguous += 1
            continue
        diffs.append(abs(a["R"] + b["R"]))

    max_diff = max(diffs) if diffs else 0.0
    if max_diff > MIRROR_TOL:
        raise AssertionError(f"镜像检查失败: max|R_long+R_short|={max_diff!r} > {MIRROR_TOL}")

    return {
        "mirror_max_abs_diff": max_diff,
        "n_checked": len(picks),
        "n_pairs_nonambiguous": len(diffs),
        "n_ambiguous_pairs": ambiguous,
        "tolerance": MIRROR_TOL,
        "note": "AMBIGUOUS 对两边均记 -1R,不进 max|diff|;随机游走/单调行情仅引用 pytest",
    }


# --------------------------------------------------------------------------- #
# 不变式:无前视实测(不重跑 pytest)
# --------------------------------------------------------------------------- #

def _label_for_mode(bars, per_symbol, index, row, stop, *, entry_mode, horizon, cfg,
                    exit_mode):
    """按报告的出场口径重标一条决策。"""
    if exit_mode == "ladder":
        return label_ladder(bars, per_symbol, index, row, stop, entry_mode,
                            horizon=horizon, cfg=cfg)
    return label_barrier(bars, per_symbol, index, row, stop, entry_mode,
                         cfg=cfg, horizon=horizon)


def _forced_bar(entry: float, stop_pct: float, sign: float, hit: int) -> tuple:
    """构造一根「必然且只触发单侧障碍」的 bar,用于证明标签真的读了入场后首根 bar。

    ``hit=+1`` 打 target 一侧,``hit=-1`` 打 stop 一侧(上下轨由 ``sign`` 决定);
    另一侧留 1e-9 的相对缝隙,避免同根双触被记成 AMBIGUOUS。
    """
    gap = 1e-9
    inner = entry * (1.0 + sign * gap)
    if hit > 0:
        close = entry * (1.0 + sign * stop_pct)
        outer = entry * (1.0 + sign * 2.0 * stop_pct)
    else:
        close = entry * (1.0 - sign * stop_pct)
        outer = entry * (1.0 - sign * 2.0 * stop_pct)
    high, low = (outer, inner) if (sign > 0) == (hit > 0) else (inner, outer)
    return (entry, high, low, close)


def _no_lookahead_check(labeled, bars, per_symbol, index, *, entry_mode: str,
                        horizon: int, cfg: LabelConfig, exit_mode: str,
                        seed: int) -> dict:
    """实测无前视:改「入场 bar 之前的 bar」结果不变,改「入场后首根可平仓 bar」结果必变。

    与 pytest 里的不变量测试同构,但只抽 ``NO_LOOKAHEAD_SAMPLE`` 条真实决策,
    直接在本次标注的 ``bars`` 面板上做原地扰动(用完立即复原),代价可忽略。
    """
    n = len(labeled)
    base_out = {
        "no_lookahead_prior_unchanged": False,
        "no_lookahead_entry_changed": False,
        "no_lookahead_n_checked": 0,
        "no_lookahead_prior_mismatch": 0,
        "no_lookahead_entry_mismatch": 0,
        "no_lookahead_sample": 0,
        "no_lookahead_prior_factor": NO_LOOKAHEAD_PRIOR_FACTOR,
        "no_lookahead_note": "无前视实测失败:没有可检查的行",
    }
    if n == 0:
        return base_out

    rng = random.Random(seed)
    picks = rng.sample(range(n), min(NO_LOOKAHEAD_SAMPLE, n))

    checked = 0
    prior_bad = 0
    entry_bad = 0
    for i in picks:
        row = labeled[i]
        stop = row["stop_pct_eff"]
        base = _label_for_mode(bars, per_symbol, index, row, stop,
                               entry_mode=entry_mode, horizon=horizon,
                               cfg=cfg, exit_mode=exit_mode)
        anchor = entry_and_start(bars, per_symbol, index, row, entry_mode, horizon)
        if base is None or anchor is None:
            continue
        checked += 1
        symbol = row["symbol"]
        _entry_px, start, _last, order = anchor
        base_triple = (base["R"], base["reason"], base["bars"])

        # (a) 入场 bar 之前(position < start-1)的 bar 全乘 1.5:结果必须完全不变
        prior_positions = list(range(0, start - 1))
        if len(prior_positions) > 3:
            prior_positions = rng.sample(prior_positions, 3)
        saved: dict = {}
        try:
            for pos in prior_positions:
                key = (symbol, order[pos])
                saved[key] = bars[key]
                o, h, l, c = saved[key]
                f = NO_LOOKAHEAD_PRIOR_FACTOR
                bars[key] = (o * f, h * f, l * f, c * f)
            if saved:
                got = _label_for_mode(bars, per_symbol, index, row, stop,
                                      entry_mode=entry_mode, horizon=horizon,
                                      cfg=cfg, exit_mode=exit_mode)
                if got is None or (got["R"], got["reason"], got["bars"]) != base_triple:
                    prior_bad += 1
        finally:
            bars.update(saved)

        # (b) 入场后首根可平仓 bar 改成必触 target / 必触 stop:至少一种必须改变结果
        key = (symbol, order[start])
        saved_bar = bars[key]
        sign = 1.0 if row["side"] == "LONG" else -1.0
        try:
            changed = False
            for hit in (1, -1):
                bars[key] = _forced_bar(base["entry_price"], stop, sign, hit)
                got = _label_for_mode(bars, per_symbol, index, row, stop,
                                      entry_mode=entry_mode, horizon=horizon,
                                      cfg=cfg, exit_mode=exit_mode)
                if got is None or (got["R"], got["reason"], got["bars"]) != base_triple:
                    changed = True
                    break
            if not changed:
                entry_bad += 1
        finally:
            bars[key] = saved_bar

    return {
        "no_lookahead_prior_unchanged": prior_bad == 0 and checked > 0,
        "no_lookahead_entry_changed": entry_bad == 0 and checked > 0,
        "no_lookahead_n_checked": checked,
        "no_lookahead_prior_mismatch": prior_bad,
        "no_lookahead_entry_mismatch": entry_bad,
        "no_lookahead_sample": len(picks),
        "no_lookahead_prior_factor": NO_LOOKAHEAD_PRIOR_FACTOR,
        "no_lookahead_note": (
            f"抽 {checked} 条决策原地扰动:入场 bar 之前的 bar OHLC×"
            f"{NO_LOOKAHEAD_PRIOR_FACTOR:g} 后 R/reason/bars 必须不变;"
            "入场后首根可平仓 bar 改成必触 target 或必触 stop 后必须改变"
        ),
    }


# --------------------------------------------------------------------------- #
# 超时画像 CSV
# --------------------------------------------------------------------------- #

def _bucket_members(labeled, group: str) -> tuple[dict[str, list[dict]], str]:
    """按 ``timeout_profile`` 的同款分档把行分组,返回 ``(bucket→rows, na_key)``。"""
    if group == "score":
        defs, key, na = _SCORE_GROUPS, lambda r: r.get("score"), "score_na"
    else:
        defs, key, na = _STOP_GROUPS, lambda r: r.get("stop_pct_eff"), "stop_na"

    out: dict[str, list[dict]] = {}
    na_rows: list[dict] = []
    for row in labeled:
        v = key(row)
        if v is None:
            na_rows.append(row)
            continue
        fv = float(v)
        for name, pred in defs:
            if pred(fv):
                out.setdefault(name, []).append(row)
                break
    if na_rows:
        out[na] = na_rows
    return out, na


def _write_timeout_csv(path: Path, labeled, prof: dict) -> None:
    """超时占比 + 超时行 R 的 p10/p50/p90(三组:score / stop_pct / side)。"""
    header = ("group", "bucket", "n", "timeout_n", "timeout_pct",
              "timeout_R_p10", "timeout_R_p50", "timeout_R_p90", "E_R_excl_timeout")
    rows_out: list[tuple] = []

    timeout_reasons = {"TIMEOUT", "COST_BREAKEVEN_TIMEOUT", "MAX_HOLD"}
    for group, prof_key in (("score", "by_score"), ("stop_pct", "by_stop")):
        members, _na = _bucket_members(labeled, group)
        for bucket, stats in prof[prof_key].items():
            sel = members.get(bucket, [])
            tout_r = [r["R_net"] for r in sel if r["reason"] in timeout_reasons]
            rows_out.append((
                group, bucket, stats["n"], stats["timeout_n"], _r(stats["timeout_pct"]),
                _r(_quantile(tout_r, 0.10)), _r(_quantile(tout_r, 0.50)),
                _r(_quantile(tout_r, 0.90)), _r(stats["E_R_excl_timeout"]),
            ))

    by_side_rows: dict[str, list[dict]] = {}
    for row in labeled:
        by_side_rows.setdefault(str(row.get("side")), []).append(row)
    for side, stats in prof["by_side"].items():
        sel = by_side_rows.get(side, [])
        tout_r = [r["R_net"] for r in sel if r["reason"] in timeout_reasons]
        rows_out.append((
            "side", side, stats["n"], stats["timeout_n"], _r(stats["timeout_pct"]),
            _r(_quantile(tout_r, 0.10)), _r(_quantile(tout_r, 0.50)),
            _r(_quantile(tout_r, 0.90)), _r(stats["E_R_excl_timeout"]),
        ))

    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows_out)


def _timeout_consistency(labeled, prof: dict, exit_mode: str) -> dict:
    """三组 ``timeout_n`` 之和必须等于时间型离场行数(barrier 口径下 == TIMEOUT)。"""
    reasons = {"TIMEOUT"} if exit_mode == "barrier" else {
        "TIMEOUT", "COST_BREAKEVEN_TIMEOUT", "MAX_HOLD"
    }
    n_reason = sum(1 for r in labeled if r.get("reason") in reasons)
    sums = {
        "by_score": sum(v["timeout_n"] for v in prof["by_score"].values()),
        "by_stop": sum(v["timeout_n"] for v in prof["by_stop"].values()),
        "by_side": sum(v["timeout_n"] for v in prof["by_side"].values()),
    }
    ok = all(v == n_reason for v in sums.values())
    if not ok:
        raise AssertionError(f"timeout 分组不闭合: reason={n_reason} sums={sums}")
    return {"reason": "TIMEOUT" if exit_mode == "barrier" else "TIMEOUT|BREAKEVEN|MAX_HOLD",
            "n_reason_rows": n_reason, **sums, "consistent": ok}


# --------------------------------------------------------------------------- #
# 字段来源与覆盖率
# --------------------------------------------------------------------------- #

def _provenance(labeled, bars, per_symbol, index, *, entry_mode: str,
                trade_globs: list[str]) -> dict:
    entry_src: Counter[str] = Counter()
    stop_src: Counter[str] = Counter()
    for d in labeled:
        lv = rebuild_price_levels(d, bars, per_symbol, index, entry_mode)
        entry_src[lv["entry_price_source"]] += 1
        stop_src[lv["stop_pct_source"]] += 1

    n = len(labeled) or 1
    entry_cov = sum(c for s, c in entry_src.items() if s != "missing") / n
    stop_cov = sum(c for s, c in stop_src.items() if s != "missing") / n

    legs = attribute_legs(load_trade_events(trade_globs))
    n_legs = len(legs)
    n_match = sum(1 for leg in legs if leg["match_ok"] and leg["entry_price"] and leg["entry_price"] > 0)

    return {
        "entry_price": {
            "source": "kline.close(bar_close) | 下一根open(next_open)",
            "mode": entry_mode,
            "coverage": _r(entry_cov, 6),
            "by_source": dict(sorted(entry_src.items())),
            "n": len(labeled),
        },
        "stop_pct": {
            "source": "metadata.risk_budget.stop_pct → entry_context.stop_pct "
                      "→ clamp(atr*1.5, 0.005, 0.03)",
            "coverage": _r(stop_cov, 6),
            "by_source": dict(sorted(stop_src.items())),
            "n": len(labeled),
            "note": "resolve_stop 对已存在的 stop_pct 不做 clamp;>3% 子样本见 stop_pct_audit",
        },
        "trade_fill": {
            "source": "paper_trades.PAPER_OPEN.price (FIFO)",
            "coverage": _r(n_match / n_legs, 6) if n_legs else None,
            "n_legs": n_legs,
            "n_match_ok": n_match,
            "note": "coverage = match_ok 且 entry_price>0 的出场腿占比",
        },
    }


# --------------------------------------------------------------------------- #
# 判定文本
# --------------------------------------------------------------------------- #

def _verdict(e_r, e_ci, lift_net, lift_ci, timeout_pct, audit) -> str:
    lo, hi = (e_ci if e_ci else (None, None))
    ylo, yhi = (lift_ci if lift_ci else (None, None))
    tmo = "—" if timeout_pct is None else f"{timeout_pct * 100:.1f}%"
    head = (
        f"毛边际 E[R]={_f4(e_r)} (CI {_f4(lo)}..{_f4(hi)})；"
        f"配对安慰剂 lift={_f4(lift_net)} (CI {_f4(ylo)}..{_f4(yhi)})；"
        f"超时占比 {tmo}；"
        f"stop_pct>3% 子样本 {audit['n_gt_3pct']} 行 E_R={_f4(audit['E_R_gt_3pct'])}。"
    )
    if ylo is None or yhi is None:
        return head + "判定：lift 区间不可得(块数不足)。"
    if ylo <= 0.0 <= yhi:
        tail = "判定：lift 的 80% CI 跨 0，配对后分数与结果无关系(平坦)。"
    elif yhi < 0.0:
        tail = "判定：lift 的 80% CI 全负，配对后仍显著为负。"
    else:
        tail = "判定：lift 的 80% CI 全正，配对后显著为正。"
    return head + tail


def _fmt_ci(ci) -> str:
    return "—" if ci is None else f"[{ci[0]:+.4f}, {ci[1]:+.4f}]"


def _f4(value, signed=True) -> str:
    """``+.4f`` 文本;None / nan 输出 —,供空分档与空子样本的判定文本使用。"""
    if value is None:
        return "—"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(f):
        return "—"
    return f"{f:+.4f}" if signed else f"{f:.4f}"


# --------------------------------------------------------------------------- #
# 报告
# --------------------------------------------------------------------------- #

def _write_report(path: Path, m: dict) -> None:
    p = m["placebo"]
    inv = m["invariance"]
    prov = m["field_provenance"]
    au = m["stop_pct_audit"]
    tp = m["timeout_profile"]

    score_lines = "\n".join(
        f"| {b['bucket']} | {b['n']} | {b['n_valid']} | {_f4(b['E_R'])} | "
        f"{_f4(b['E_R_placebo'])} | {_f4(b['lift_gross'])} | {_fmt_ci(b['lift_gross_ci80'])} | "
        f"{_f4(b['lift_net'])} | {_fmt_ci(b['lift_net_ci80'])} |"
        for b in p["by_score"]
    )
    def _p50(v):
        x = v["timeout_R_p50"]
        return "—" if x is None else f"{x:+.4f}"

    timeout_lines = "\n".join(
        f"| {k} | {v['n']} | {v['timeout_n']} | {v['timeout_pct'] * 100:.2f}% | {_p50(v)} |"
        for k, v in tp["by_score"].items()
    )
    tp_c = tp["_consistency"]

    text = f"""# 前向标签 v2(配对安慰剂 / 超时披露 / stop_pct 审计)

窗口 `{m['window'][0]}` .. `{m['window'][1]}`；决策 {m['decisions_total']} 条，标注 {m['labeled']} 条，
AMBIGUOUS {m['ambiguous_pct']}%。口径 horizon={m['cfg']['horizon']} / cost={m['cfg']['cost_bps']}bps /
entry={m['cfg']['entry_mode']} / exit={m['cfg']['exit_mode']}，指纹 `{m['cfg']['fingerprint']}`。

## 1. 口径与不变式

随机抽 {inv['mirror_n_checked']} 条决策做多空镜像重标：`max|R_long+R_short| = {inv['mirror_max_abs_diff']!r}`
（非歧义对 {inv['mirror_n_pairs_nonambiguous']}，歧义对 {inv['mirror_n_ambiguous_pairs']}）。

无前视**本脚本实测**：抽 {inv['no_lookahead_n_checked']} 条决策，入场 bar 之前的 bar OHLC×{inv['no_lookahead_prior_factor']:g}
后 `prior_unchanged={inv['no_lookahead_prior_unchanged']}`（不一致 {inv['no_lookahead_prior_mismatch']} 条）；把入场后首根可平仓 bar
改成必触 target / 必触 stop 后 `entry_changed={inv['no_lookahead_entry_changed']}`（不一致 {inv['no_lookahead_entry_mismatch']} 条）。
随机游走命中率与单调行情两项**未在本脚本重跑**，结论以字符串引用 `{inv['source']}`（随机游走带宽 ±0.0335，见该测试）。

字段来源与实测覆盖率：entry_price `{prov['entry_price']['coverage']}`（{prov['entry_price']['by_source']}）；
stop_pct `{prov['stop_pct']['coverage']}`（{prov['stop_pct']['by_source']}）；
trade_fill `{prov['trade_fill']['coverage']}`（{prov['trade_fill']['n_match_ok']}/{prov['trade_fill']['n_legs']} 腿）。

## 2. 逐条配对安慰剂

安慰剂：同 symbol、同 UTC 日、同 side、同 stop_pct、随机 bar，每条 {m['placebo']['draws']} 个 draw，
seed={m['placebo']['seed']}；区间为 `symbol|date` 块 bootstrap（{m['placebo']['bootstrap_iters']} 次，80%）。
有效配对 {p['n_valid']}/{p['n_rows']}（valid_rate={p['valid_rate']:.4f}），`max|delta_R-delta_R_net| = {p['identity_max_abs_diff']!r}`。

| 分数档 | n | n_valid | E[R] | E[R]_placebo | lift_gross | CI80 | lift_net | CI80 |
|---|---|---|---|---|---|---|---|---|
{score_lines}

全体：lift_gross={_f4(p['lift_gross'])} {_fmt_ci(p['lift_gross_ci80'])}，
lift_net={_f4(p['lift_net'])} {_fmt_ci(p['lift_net_ci80'])}。

## 3. 超时画像与止损审计

超时行 {tp_c['n_reason_rows']} 条（三组求和 by_score={tp_c['by_score']} / by_stop={tp_c['by_stop']} /
by_side={tp_c['by_side']}，闭合={tp_c['consistent']}），占标注 {_f4((tp['overall']['timeout_pct'] or 0) * 100, signed=False)}%。

| 分数档 | n | 超时 | 占比 | 超时行 R_net 中位数 |
|---|---|---|---|---|
{timeout_lines}

`stop_pct_eff > 0.03`：{au['n_gt_3pct']} 行（{au['share'] * 100:.2f}%），E[R]={_f4(au['E_R_gt_3pct'])}；
全体 E[R]={_f4(au['E_R_all'])}。根因：`resolve_stop` 对已存在的 stop_pct 不 clamp，而模块常量上限 0.03、线上
config 上限 0.04。

**结论（代码生成）**：{m['verdict']}

局限：安慰剂只排除决策自身那根 bar，不排除邻域，32 根前向窗口可与真实样本重叠，故只用于抵消成本构成差异；
不作为独立随机样本做显著性推断。
"""
    path.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #

def main() -> None:
    t0 = time.time()
    ap = argparse.ArgumentParser(description="前向标签 v2:配对安慰剂正式报告")
    ap.add_argument("--logs", default=_default_logs())
    ap.add_argument("--months", default="2026-09,2026-10")
    ap.add_argument("--out", default=_default_out("fwd-label-v2-20261019"))
    ap.add_argument("--profile", default="any", choices=["any", "six_factor"])
    ap.add_argument("--exit-mode", default="barrier", choices=["barrier", "ladder"])
    ap.add_argument("--entry-price", default="next_open", choices=["next_open", "bar_close"])
    ap.add_argument("--horizon", type=int, default=32)
    ap.add_argument("--cost-bps", type=float, default=20.0)
    ap.add_argument("--placebo-draws", type=int, default=20)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--bootstrap-iters", type=int, default=2000)
    args = ap.parse_args()

    logs = Path(args.logs)
    months = [x.strip() for x in args.months.split(",") if x.strip()]
    paths = []
    for month in months:
        paths += sorted(logs.glob(f"{month}/*/decisions.jsonl"))
    paths = [str(p) for p in paths]
    if not paths:
        raise SystemExit(f"no decisions.jsonl under {logs} for {months}")

    print(f"[load] {len(paths)} files", flush=True)
    decisions = load_decisions(paths, profile=args.profile)
    _attach_price_context(decisions, paths)
    print(f"[load] decisions={len(decisions)} ({time.time() - t0:.1f}s)", flush=True)

    cfg = LabelConfig(
        horizon_bars=args.horizon,
        cost_bps=args.cost_bps,
        entry_mode=args.entry_price,
        exit_mode=args.exit_mode,
    )
    labeled, bars, per_symbol, index, _quad = run_labeling(
        decisions, exit_mode=args.exit_mode, entry_mode=args.entry_price,
        cfg=cfg, horizon=args.horizon,
    )
    if not labeled:
        raise SystemExit("no labeled rows")
    print(f"[label] labeled={len(labeled)} ({time.time() - t0:.1f}s)", flush=True)

    # --- 超时画像 ---
    tp = timeout_profile(labeled)
    tp["_consistency"] = _timeout_consistency(labeled, tp, args.exit_mode)
    print(f"[timeout] n={tp['_consistency']['n_reason_rows']}", flush=True)

    # --- 逐条配对安慰剂 ---
    t_pl = time.time()
    placebo = matched_placebo(
        labeled, bars, per_symbol, index,
        draws=args.placebo_draws, seed=args.seed,
        entry_mode=args.entry_price, horizon=args.horizon, cfg=cfg,
    )
    for row, pl in zip(labeled, placebo):
        row.update(pl)
    print(f"[placebo] rows={len(placebo)} ({time.time() - t_pl:.1f}s)", flush=True)

    summary = lift_summary(labeled, iters=args.bootstrap_iters, seed=args.seed)
    ov = summary["overall"]
    n_valid = ov["n_valid"]
    n_rows = ov["n"]
    valid_rate = n_valid / n_rows if n_rows else 0.0
    if valid_rate < 0.90:
        raise SystemExit(f"valid_rate={valid_rate:.4f} < 0.90")

    # --- 毛边际 E[R] 的块 bootstrap ---
    by_block = {}
    for row in labeled:
        by_block.setdefault(row["block"], []).append(row["R"])
    e_r_ci = _ci(by_block, args.bootstrap_iters, args.seed)

    # --- stop_pct 审计 ---
    gt = [row for row in labeled if row["stop_pct_eff"] > 0.03]
    stop_audit = {
        "n_gt_3pct": len(gt),
        "share": _r(len(gt) / len(labeled), 6),
        "E_R_gt_3pct": _r(statistics.fmean([r["R"] for r in gt]), 6) if gt else None,
        "E_R_all": _r(statistics.fmean([r["R"] for r in labeled]), 6),
        "n_total": len(labeled),
        "threshold": 0.03,
    }
    print(f"[audit] stop>3%: {len(gt)} rows, E_R={stop_audit['E_R_gt_3pct']}", flush=True)

    # --- 不变式(廉价镜像 + 无前视实测) ---
    inv_mirror = _mirror_check(
        labeled, bars, per_symbol, index,
        entry_mode=args.entry_price, horizon=args.horizon, cfg=cfg, seed=args.seed,
    )
    inv_lookahead = _no_lookahead_check(
        labeled, bars, per_symbol, index,
        entry_mode=args.entry_price, horizon=args.horizon, cfg=cfg,
        exit_mode=args.exit_mode, seed=args.seed,
    )
    print(f"[lookahead] n={inv_lookahead['no_lookahead_n_checked']} "
          f"prior_unchanged={inv_lookahead['no_lookahead_prior_unchanged']} "
          f"entry_changed={inv_lookahead['no_lookahead_entry_changed']}", flush=True)
    invariance = {
        "mirror_max_abs_diff": inv_mirror["mirror_max_abs_diff"],
        "mirror_n_checked": inv_mirror["n_checked"],
        "mirror_n_pairs_nonambiguous": inv_mirror["n_pairs_nonambiguous"],
        "mirror_n_ambiguous_pairs": inv_mirror["n_ambiguous_pairs"],
        "random_walk_hit": "pytest 通过:hit_rate 落在 0.5±3σ 内,同 seed 逐位可复现(本脚本不重跑)",
        "band": "±3*sqrt(0.25/2000)=±0.0335",
        # 无前视:本脚本实测(不是引用 pytest)。两个字段都要为 True 才算通过。
        **inv_lookahead,
        "no_lookahead_ok": (inv_lookahead["no_lookahead_prior_unchanged"]
                            and inv_lookahead["no_lookahead_entry_changed"]),
        "source": INVARIANCE_SOURCE,
        "note": inv_mirror["note"],
    }

    # --- 字段来源 ---
    trade_globs = [str(logs / m / "*" / "paper_trades.jsonl") for m in months]
    provenance = _provenance(labeled, bars, per_symbol, index,
                             entry_mode=args.entry_price, trade_globs=trade_globs)

    # --- 判定 ---
    verdict = _verdict(
        _r(ov["E_R"], 6), e_r_ci, _r(ov["lift_net"], 6), _ci_from(ov["lift_net_ci80"]),
        tp["overall"]["timeout_pct"], stop_audit,
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # --- placebo_pairs.csv ---
    # placebo_valid 必须落盘:无效行的 placebo_R_mean 是 NaN、delta_R 被置 0
    # (见 fwdlib.baseline._invalid_row),没有这一列,读表的人会把 delta_R=0
    # 当成「安慰剂与真实样本一致」的有效观测。
    cols = ("symbol", "ts", "side", "score", "stop_pct_eff", "R", "R_net",
            "placebo_R_mean", "placebo_R_sd", "placebo_n_valid", "placebo_valid",
            "delta_R", "delta_R_net")
    with (out / "placebo_pairs.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for row in labeled:
            values = [row.get(c) for c in cols]
            values[cols.index("placebo_valid")] = _placebo_valid(row)
            w.writerow(values)

    # --- timeout_profile.csv ---
    _write_timeout_csv(out / "timeout_profile.csv", labeled, tp)

    metrics = {
        "window": [_fmt_ts(min(r["ts"] for r in labeled)), _fmt_ts(max(r["ts"] for r in labeled))],
        "labeled": len(labeled),
        "decisions_total": len(decisions),
        "ambiguous_pct": round(
            sum(1 for r in labeled if r["ambiguous"]) / len(labeled) * 100, 2),
        "cfg": {
            "horizon": args.horizon,
            "cost_bps": args.cost_bps,
            "entry_mode": args.entry_price,
            "exit_mode": args.exit_mode,
            "fingerprint": cfg.fingerprint(),
        },
        "invariance": invariance,
        "placebo": {
            "valid_rate": _r(valid_rate, 6),
            "n_rows": n_rows,
            "n_valid": n_valid,
            "mean_placebo_R": _r(ov["E_R_placebo"], 6),
            "identity_max_abs_diff": summary["identity_max_abs_diff"],
            "lift_gross": _r(ov["lift_gross"], 6),
            "lift_gross_ci80": _ci_from(ov["lift_gross_ci80"]),
            "lift_net": _r(ov["lift_net"], 6),
            "lift_net_ci80": _ci_from(ov["lift_net_ci80"]),
            "by_score": [
                {
                    "bucket": b["bucket"],
                    "n": b["n"],
                    "n_valid": b["n_valid"],
                    "E_R": _r(b["E_R"]),
                    "E_R_placebo": _r(b["E_R_placebo"]),
                    "lift_gross": _r(b["lift_gross"]),
                    "lift_gross_ci80": _ci_from(b["lift_gross_ci80"]),
                    "lift_net": _r(b["lift_net"]),
                    "lift_net_ci80": _ci_from(b["lift_net_ci80"]),
                }
                for b in summary["by_score"]
            ],
            "draws": args.placebo_draws,
            "seed": args.seed,
            "bootstrap_iters": args.bootstrap_iters,
            "method": "matched_placebo:同 symbol/UTC日/side/stop_pct,随机 bar,逐条配对",
            "warning": None if args.exit_mode == "barrier" else
                       "ladder 口径下安慰剂仍按 barrier 标注,lift 仅作成本抵消参考",
        },
        "timeout_profile": tp,
        "stop_pct_audit": stop_audit,
        "field_provenance": provenance,
        "preregistered": {
            "score_buckets": [name for name, _p in _SCORE_GROUPS],
            "primary_metric": "lift_net(逐条配对安慰剂)",
            "placebo": {"draws": args.placebo_draws, "seed": args.seed,
                        "matched_on": ["symbol", "utc_date", "side", "stop_pct"]},
            "bootstrap": {"iters": args.bootstrap_iters, "block": "symbol|utc_date", "ci": 0.80},
            "decision_rule": "CI80 跨 0 ⇒ 平坦;全负 ⇒ 显著为负;全正 ⇒ 显著为正",
            "note": "分档/区间/seed 在全样本运行前固定",
        },
        "verdict": verdict,
        "runtime_seconds": _r(time.time() - t0, 1),
    }
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(out / "report.md", metrics)

    print(f"[done] out={out} ({time.time() - t0:.1f}s)", flush=True)
    print(verdict, flush=True)


def _ci_from(ci) -> list | None:
    """``lift_summary`` 已给出 (lo, hi) 或 None;统一保留 6 位。"""
    if ci is None:
        return None
    return [_r(ci[0]), _r(ci[1])]


if __name__ == "__main__":
    main()
