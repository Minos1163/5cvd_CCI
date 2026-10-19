#!/usr/bin/env python
"""Stage B：在 1h 周期上重算六因子，检验 1h 是否存在真 alpha。

与 Stage A（`tf_uplift_20261019.py`）的分工：
  Stage A = 「15m 因子 + 1h 出场」，只测成本上限；
  Stage B = 「1h 因子 + 1h 出场」，唯一能检验真 alpha 的一步。

五个臂共用同一批锚点、同一 labeler、同一止损规则、同一成本，逐级只加一个变化：

  A0  base_15m      日志里该小时最后一根 15m 的 score_detail.scores   side 取日志
  B1  h1_raw        1h 重算，ATR% 绝对，无高周期结构                  side 取日志
  B2  h1_norm       1h 重算，ATR% 归一到 15m 量级（scale=0.5）        side 取日志
  B3  h1_norm_4h    1h 重算，ATR% 归一 + 4h fib 作高周期结构          side 取日志
  B4  h1_e2e        1h 重算，ATR% 归一 + 4h 结构 + side 由 1h 自推    主口径

判据（预登记，见 `PREREG`）：
  G0  管线校准：手写装配 ≡ fib_pa_component_scores（逐位）；与日志比对 ≥95%
  G0b 交叉校验：A0 臂 E[R] 应落在 Stage A 的 +0.0040 ± 0.010
  G1  覆盖：可打分锚点 ≥ 20,000 且标的 ≥ 12
  G2  漂移：报告 Δscore，|Δ|>3 时结论只能引用配对 Δ
  G3  主判据：top-decile E[R] 的 80% 分块下界 > 0 且十分位 Spearman ≥ 0.5
  G4  经济性：non_overlap 子集 top-decile E[R] > cost_R
  G5  停手：G3 ∧ G4 全过才进 Stage C
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
for _p in (_ROOT, Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import tf_uplift_20261019 as T  # noqa: E402

from src.backtest.engine import BacktestBar  # noqa: E402
from src.signals.cci_quality import cci_series, score_cci_momentum_quality  # noqa: E402
from src.signals.entry_chain_features import (  # noqa: E402
    atr_pct as feat_atr_pct,
    direction_from_history,
    fib_pa_component_scores,
    latest_fib_from_bars,
    risk_reward_geometry_detail,
    trend_ema_context_score,
    volume_flow_score,
)
from src.signals.entry_chain_scoring import FIB_PA_WEIGHTS, component_points  # noqa: E402
from src.signals.fib_location import (  # noqa: E402
    detect_fractal_swings,
    score_fibonacci_location,
)
from src.signals.pa_structure import score_price_action_structure  # noqa: E402

# --------------------------------------------------------------------------- #
# 0. 常量（输出里逐条回显）
# --------------------------------------------------------------------------- #
HOUR = 3600
BAR_15M = 900
BARS_PER_HOUR = 4
BARS_PER_4H = 4

SIX_FACTOR_WEIGHTS = {
    "cci_momentum_quality": 14.0,
    "fibonacci_location": 18.0,
    "flow_cvd_confirmation": 18.0,
    "price_action_structure": 22.0,
    "risk_reward_geometry": 8.0,
    "trend_ema_context": 20.0,
}

WINDOW_1H = 240          # 对齐线上 --public-kline-limit 240（EMA 路径依赖，必须固定）
WINDOW_4H = 60
CCI_WINDOW = 48          # CCI 只看尾部，48 = 20 周期 + 28 个可用值（评分只用末 5 个）
HORIZON_1H = 8           # 8h，对齐 15m 的 32×15m
COST_BREAKEVEN_1H = 2    # horizon // 4
STOP_CLAMP = (0.015, 0.040)
STOP_CLAMP_SENS = (0.005, 0.040)
ROUND_TRIP_BPS = 20.0
COST_ALT_BPS = 7.75
ATR_SCALE_NORM = 0.5
QUAD_MIN = (15.0, 10.0, 14.0, 7.0)
DECILES = 10
SCORE_GATES = (70.0, 82.0)
STAGE_A_E_R = 0.0040
STAGE_A_TOL = 0.010

PREREG = {
    "G0_assembly_max_abs_diff": 1e-9,
    "G0_vs_log_excl_trend_min": 0.95,
    "G0b_stage_a_E_R": STAGE_A_E_R,
    "G0b_tolerance": STAGE_A_TOL,
    "G1_min_anchors": 20_000,
    "G1_min_symbols": 12,
    "G2_score_drift_limit": 3.0,
    "G3_top_decile_ci80_lower_gt": 0.0,
    "G3_spearman_min": 0.5,
    "G4_top_decile_R_gt_cost_R": True,
}

ARMS = (
    ("A0", "base_15m", dict(source="log", atr_scale=1.0, high="none", side="log")),
    ("B1", "h1_raw", dict(source="h1", atr_scale=1.0, high="none", side="log")),
    ("B2", "h1_norm", dict(source="h1", atr_scale=ATR_SCALE_NORM, high="none", side="log")),
    ("B3", "h1_norm_4h", dict(source="h1", atr_scale=ATR_SCALE_NORM, high="4h", side="log")),
    ("B4", "h1_e2e", dict(source="h1", atr_scale=ATR_SCALE_NORM, high="4h", side="h1")),
)
PRIMARY_ARM = "B4"

EXIT_CFG = {
    "exit_mode": "ladder",
    "entry_mode": "bar_close",
    "post_tp_mode": "trend_capture",
    "quadrant_defense": True,
    "q2_tighten": True,
}


# --------------------------------------------------------------------------- #
# 1. 数据层
# --------------------------------------------------------------------------- #
def load_panel(paths):
    """直读 decisions.jsonl，保留 volume 与 score_detail.scores。

    不复用 `fwd_label.load_decisions`：它把 volume 丢了，而
    `flow_cvd_confirmation` 需要 volume（6 根 `sign(close-open)×volume` 之和）。
    """
    seen = set()
    out = []
    skipped = Counter()
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    skipped["bad_json"] += 1
                    continue
                weights = raw.get("weights") or {}
                try:
                    is_six = (
                        {k: round(float(v), 1) for k, v in weights.items()}
                        == SIX_FACTOR_WEIGHTS
                    )
                except (TypeError, ValueError):
                    skipped["bad_weights"] += 1
                    continue
                if not is_six:
                    skipped["not_six_factor"] += 1
                    continue
                kline = raw.get("kline") or {}
                ts = kline.get("timestamp")
                symbol = raw.get("symbol")
                if ts is None or not symbol:
                    skipped["no_kline"] += 1
                    continue
                if not (1_000_000_000 <= int(ts) <= 2_000_000_000):
                    # 秒级 UTC 的合理区间；毫秒时间戳会在这里被挡住，
                    # 否则每小时会被切成 4 个「独立小时」，anchors 静默变 0。
                    skipped["bad_ts"] += 1
                    continue
                try:
                    bar = (
                        float(kline["open"]),
                        float(kline["high"]),
                        float(kline["low"]),
                        float(kline["close"]),
                    )
                except (KeyError, TypeError, ValueError):
                    skipped["bad_ohlc"] += 1
                    continue
                ec = raw.get("entry_context") or {}
                side = (ec.get("side") or "").strip().upper()
                if side not in {"LONG", "SHORT"}:
                    skipped["no_side"] += 1
                    continue
                key = (symbol, int(ts))
                if key in seen:
                    skipped["dup"] += 1
                    continue
                seen.add(key)
                sd = raw.get("score_detail") or {}
                scores = sd.get("scores") or {}
                volume = float(kline.get("volume") or 0.0)
                if volume <= 0:
                    skipped["zero_volume"] += 1
                out.append(
                    {
                        "symbol": symbol,
                        "ts": int(ts),
                        "side": side,
                        "open": bar[0],
                        "high": bar[1],
                        "low": bar[2],
                        "close": bar[3],
                        "volume": volume,
                        "atr_pct": float(ec.get("atr_pct") or 0.0),
                        "stop_pct": float(ec.get("stop_pct") or 0.0),
                        "score": sd.get("total_score"),
                        "quadrant": raw.get("quadrant"),
                        "action": raw.get("action"),
                        "risk_allowed": bool(raw.get("risk_allowed")),
                        "scores": {
                            k: float(scores[k])
                            for k in SIX_FACTOR_WEIGHTS
                            if scores.get(k) is not None
                        },
                    }
                )
    out.sort(key=lambda r: (r["symbol"], r["ts"]))
    return out, dict(skipped)


def aggregate_1h(rows):
    """15m → 1h，只保留 4/4 齐全的小时。返回 {(sym, hour): (o,h,l,c,v)}。"""
    buckets = defaultdict(dict)
    for r in rows:
        buckets[(r["symbol"], r["ts"] // HOUR * HOUR)][r["ts"]] = r
    bars = {}
    for (sym, hour), m in buckets.items():
        if len(m) != BARS_PER_HOUR:
            continue
        if any(hour + k * BAR_15M not in m for k in range(BARS_PER_HOUR)):
            continue
        legs = [m[hour + k * BAR_15M] for k in range(BARS_PER_HOUR)]
        bars[(sym, hour)] = (
            legs[0]["open"],
            max(x["high"] for x in legs),
            min(x["low"] for x in legs),
            legs[-1]["close"],
            sum(x["volume"] for x in legs),
        )
    return bars


def aggregate_4h(bars_1h):
    """1h → 4h，只保留 4/4 齐全的 4 小时。返回 {(sym, h4): (o,h,l,c,v)}。"""
    buckets = defaultdict(dict)
    for (sym, ts), bar in bars_1h.items():
        buckets[(sym, ts // (4 * HOUR) * (4 * HOUR))][ts] = bar
    bars = {}
    for (sym, h4), m in buckets.items():
        if len(m) != BARS_PER_4H:
            continue
        if any(h4 + k * HOUR not in m for k in range(BARS_PER_4H)):
            continue
        legs = [m[h4 + k * HOUR] for k in range(BARS_PER_4H)]
        bars[(sym, h4)] = (
            legs[0][0],
            max(x[1] for x in legs),
            min(x[2] for x in legs),
            legs[-1][3],
            sum(x[4] for x in legs),
        )
    return bars


def to_objects(ts_list, bars, symbol):
    """[(ts, o,h,l,c,v)] → (ts 列表, BacktestBar 列表)，只构造一次。"""
    return [
        BacktestBar(symbol, t, *bars[(symbol, t)]) for t in ts_list
    ]


def build_label_frames(segments, real_of, bars_1h):
    """按段名建 `label_ladder` 需要的 bars / per_symbol / index。

    用段名（`SYM@i`）而不是真实标的：`_entry_and_start` 用 `order[i+1]` 取下一根，
    不校验 `Δts`，跨缺口会把远端 bar 当成下一小时。
    """
    bars = {}
    per_symbol = {}
    index = {}
    for name, ts_list in segments.items():
        real = real_of[name]
        per_symbol[name] = list(ts_list)
        index[name] = {t: i for i, t in enumerate(ts_list)}
        for t in ts_list:
            o, h, l, c, _v = bars_1h[(real, t)]
            bars[(name, t)] = (o, h, l, c)
    return bars, per_symbol, index


# --------------------------------------------------------------------------- #
# 2. 打分层
# --------------------------------------------------------------------------- #
def quadrant_of(points):
    trend_ok = (
        points["trend_ema_context"] >= QUAD_MIN[0]
        and points["price_action_structure"] >= QUAD_MIN[1]
    )
    flow_ok = (
        points["flow_cvd_confirmation"] >= QUAD_MIN[2]
        and points["cci_momentum_quality"] >= QUAD_MIN[3]
    )
    if trend_ok and flow_ok:
        return "Q1"
    if trend_ok:
        return "Q2"
    if flow_ok:
        return "Q3"
    return "Q4"


def score_h1(side, w_entry, w_high, atr_scale=1.0, atr_pct_value=None):
    """在一条 1h 序列上重算六因子。

    与 `fib_pa_component_scores` 的差别只有一处：`atr_pct_value` 先按 `atr_scale`
    归一，再喂给 RR 的 ATR 分档。除此之外逐行等价（G0 用等价性测试钉住）。

    `atr_pct_value` 由调用方传入时直接使用（保证打分与止损用的是同一个 ATR 值，
    不在两处各算一次）；不传则从 `w_entry[-20:]` 现算。

    `w_high` 是「高一级周期」窗口，充当 `fib_1h`；`w_entry` 同时充当 `fib_15m`
    的角色。传 `w_high=None` 时 `fib_1h=None`——**不要**把同一条序列塞进两个槽：
    `score_fibonacci_location` 会对两者各做一次 SHORT 支撑邻近惩罚。
    """
    close = w_entry[-1].close
    if atr_pct_value is None:
        atr_pct_value = feat_atr_pct(w_entry[-20:])
    atr_value_pct = atr_pct_value
    atr_value = close * atr_value_pct
    swings = detect_fractal_swings(w_entry, atr=atr_value)

    scores = {
        "trend_ema_context": trend_ema_context_score(side, w_entry, "soft"),
        "flow_cvd_confirmation": volume_flow_score(side, w_entry),
        # CCI 只在尾部窗口上取值（评分只用 series[-5:]），传入 w[-48:] 与传入
        # 整条 240 根的末 29 个值逐位相同，但省掉 8 倍窗口重算（实测 10.9ms → 1.3ms）。
        "cci_momentum_quality": max(
            0.0,
            min(
                1.0,
                score_cci_momentum_quality(cci_series(w_entry[-CCI_WINDOW:]), side).score
                / 14.0,
            ),
        ),
        "price_action_structure": max(
            0.0,
            min(
                1.0,
                score_price_action_structure(w_entry, side, swings, atr=atr_value).score
                / 22.0,
            ),
        ),
    }

    fib_high = latest_fib_from_bars(w_high, side, atr_value) if w_high else None
    fib_entry = latest_fib_from_bars(w_entry, side, atr_value)
    fib = score_fibonacci_location(
        close=close, side=side, fib_1h=fib_high, fib_15m=fib_entry, atr=atr_value
    )
    scores["fibonacci_location"] = max(0.0, min(1.0, fib.score / 18.0))

    rr = risk_reward_geometry_detail(
        close, side, atr_value, atr_value_pct * atr_scale, swings
    )
    scores["risk_reward_geometry"] = max(0.0, min(1.0, float(rr["score"]) / 8.0))

    points = component_points(scores, FIB_PA_WEIGHTS)
    return {
        "scores": scores,
        "points": points,
        "total": round(sum(points.values()), 4),
        "quadrant": quadrant_of(points),
        "fib_block": fib.action_cap == "NO_TRADE",
        "atr_pct": atr_value_pct,
    }


def prepare_windows(segments, real_of, bars_1h, bars_4h):
    """为每个段预先构造 1h 对象列表、1h ATR%、以及（可选）4h 对象列表。"""
    per_seg = {}
    high_by_symbol = defaultdict(list)
    for (sym, h4) in sorted(bars_4h):
        high_by_symbol[sym].append(h4)
    for name, ts_list in segments.items():
        real = real_of[name]
        objs = to_objects(ts_list, bars_1h, real)
        atr_map = {}
        for i in range(WINDOW_1H - 1, len(ts_list)):
            atr_map[i] = feat_atr_pct(objs[i - 19 : i + 1])
        per_seg[name] = {
            "ts": ts_list,
            "objs": objs,
            "atr": atr_map,
            "high_ts": high_by_symbol.get(real, []),
            "high_objs": [
                BacktestBar(real, t, *bars_4h[(real, t)])
                for t in high_by_symbol.get(real, [])
            ],
        }
    return per_seg


def window_high(seg, ts):
    """取「入场时点已收盘」的 4h bar。

    入场是 anchor bar 的收盘 `ts + HOUR`（`entry_mode="bar_close"`），所以
    `h4 + 4h <= ts + HOUR` 才是正确边界；用 `<= ts` 会平白滞后一根（约 25% 的
    锚点刚好卡在 4h 边界上）。
    """
    hts = seg["high_ts"]
    limit = ts + HOUR
    lo, hi = 0, len(hts)
    while lo < hi:
        mid = (lo + hi) // 2
        if hts[mid] + 4 * HOUR <= limit:
            lo = mid + 1
        else:
            hi = mid
    if lo == 0:
        return None
    return seg["high_objs"][max(0, lo - WINDOW_4H) : lo]


def score_arm(per_seg, cfg, side_by_key=None):
    """按臂配置给段内每个「历史 ≥ WINDOW_1H」的小时打分。"""
    score_map = {}
    quad_map = {}
    for name, seg in per_seg.items():
        ts_list = seg["ts"]
        for i in range(WINDOW_1H - 1, len(ts_list)):
            ts = ts_list[i]
            w_entry = seg["objs"][i - WINDOW_1H + 1 : i + 1]
            w_high = window_high(seg, ts) if cfg["high"] == "4h" else None
            if cfg["side"] == "h1":
                side = direction_from_history(w_entry)
            else:
                side = (side_by_key or {}).get((name, ts))
            if side not in {"LONG", "SHORT"}:
                continue
            res = score_h1(side, w_entry, w_high, cfg["atr_scale"], seg["atr"][i])
            score_map[(name, ts)] = dict(res, side=side)
            quad_map[(name, ts)] = res["quadrant"]
    return score_map, quad_map


def logged_by_hour(rows):
    """(symbol, 小时起点) → 该小时最后一根 15m（`ts % 3600 == 2700`）的决策行。

    键必须是 1h bar 的 **open time**：后续一律用 1h 时间戳查表，不能混用收盘时间。
    """
    out = {}
    for r in rows:
        if r["ts"] % HOUR == HOUR - BAR_15M:
            out[(r["symbol"], r["ts"] - (HOUR - BAR_15M))] = r
    return out


# --------------------------------------------------------------------------- #
# 3. 校准
# --------------------------------------------------------------------------- #
def check_assembly_equivalence(per_seg, limit=12):
    """G0a：手写装配 ≡ `fib_pa_component_scores`，并钉住三条分支不变量。

    1. `atr_scale=1.0` 时六因子逐位等于生产函数；
    2. `atr_scale=0.5` 只允许 `risk_reward_geometry` 变化，其余五项必须不变；
    3. `w_high=None` 不得抛错，且 `fibonacci_location` 仍可算出（走本级结构）。

    `w_high` 传 60 根是安全的：`detect_fractal_swings` 只看末 `lookback=50` 根
    （`fib_location.py:57-66`），60 与线上 240 根等价。
    """
    worst = 0.0
    branch_worst = 0.0
    checked = 0
    for _name, seg in list(per_seg.items())[:limit]:
        ts_list = seg["ts"]
        if len(ts_list) < WINDOW_1H:
            continue
        for i in (WINDOW_1H - 1, len(ts_list) - 1):
            w = seg["objs"][i - WINDOW_1H + 1 : i + 1]
            atr = feat_atr_pct(w[-20:])
            for side in ("LONG", "SHORT"):
                ref = fib_pa_component_scores(
                    side, {"15m": w, "1h": w}, atr, ema200_gate_mode="soft"
                )
                got = score_h1(side, w, w, 1.0)
                for key in SIX_FACTOR_WEIGHTS:
                    worst = max(worst, abs(ref[key] - got["scores"][key]))

                norm = score_h1(side, w, w, ATR_SCALE_NORM)
                for key in SIX_FACTOR_WEIGHTS:
                    if key == "risk_reward_geometry":
                        continue
                    branch_worst = max(
                        branch_worst, abs(norm["scores"][key] - got["scores"][key])
                    )

                no_high = score_h1(side, w, None, ATR_SCALE_NORM)
                for key in SIX_FACTOR_WEIGHTS:
                    branch_worst = max(
                        branch_worst,
                        abs(no_high["scores"][key] - norm["scores"][key])
                        if key != "fibonacci_location"
                        else 0.0,
                    )
                checked += 1
    return {"checked": checked, "max_abs_diff": worst, "branch_max_abs_diff": branch_worst}


def calibrate_vs_log(rows, bars_1h, limit_rows=4000):
    """用 15m 序列 + 日志 side/atr_pct 复算，与日志 `score_detail.scores` 逐位比对。

    只抽前 `limit_rows` 个位置（15m 序列长度是 1h 的 4 倍，全量太慢且无必要）。
    """
    by_symbol = defaultdict(list)
    for r in rows:
        by_symbol[r["symbol"]].append(r)
    for sym in by_symbol:
        by_symbol[sym].sort(key=lambda x: x["ts"])
        by_symbol[sym] = [
            BacktestBar(sym, x["ts"], x["open"], x["high"], x["low"], x["close"], x["volume"])
            for x in by_symbol[sym]
        ]
    row_by_symbol = defaultdict(dict)
    for r in rows:
        row_by_symbol[r["symbol"]][r["ts"]] = r

    per_factor = defaultdict(lambda: [0, 0])
    worst = defaultdict(float)
    n = 0
    for sym, objs in by_symbol.items():
        if len(objs) < WINDOW_1H:
            continue
        step = max(1, (len(objs) - WINDOW_1H) // max(1, limit_rows // max(1, len(by_symbol))))
        for i in range(WINDOW_1H - 1, len(objs), step):
            bar = objs[i]
            row = row_by_symbol[sym].get(bar.timestamp)
            if not row or not row["scores"]:
                continue
            w_entry = objs[i - WINDOW_1H + 1 : i + 1]
            hour = bar.timestamp // HOUR * HOUR
            high_ts = [
                t for t in range(hour - WINDOW_4H * HOUR, hour, HOUR) if (sym, t) in bars_1h
            ]
            w_high = (
                [BacktestBar(sym, t, *bars_1h[(sym, t)]) for t in high_ts[-WINDOW_4H:]]
                if high_ts
                else None
            )
            got = score_h1(row["side"], w_entry, w_high, 1.0)["scores"]
            for key in SIX_FACTOR_WEIGHTS:
                if key not in row["scores"]:
                    continue
                per_factor[key][1] += 1
                diff = abs(row["scores"][key] - got[key])
                worst[key] = max(worst[key], diff)
                if diff <= 1e-6:
                    per_factor[key][0] += 1
            n += 1
    table = {
        key: {
            "n": tot,
            "exact_rate": round(hit / tot, 4) if tot else None,
            "max_abs_diff": round(worst[key], 6),
        }
        for key, (hit, tot) in per_factor.items()
    }
    total = sum(v["n"] for v in table.values()) or 1
    overall = sum((v["exact_rate"] or 0) * v["n"] for v in table.values()) / total
    stable = {k: v for k, v in table.items() if k != "trend_ema_context"}
    stable_total = sum(v["n"] for v in stable.values()) or 1
    stable_rate = sum((v["exact_rate"] or 0) * v["n"] for v in stable.values()) / stable_total
    return {
        "rows": n,
        "overall_exact_rate": round(overall, 4),
        "excl_trend_exact_rate": round(stable_rate, 4),
        "by_factor": table,
    }


# --------------------------------------------------------------------------- #
# 4. 评估层
# --------------------------------------------------------------------------- #
def make_stop_rule(stop_clamp):
    def _stop(d):
        return T.clamp(d["atr_pct"] * 1.5, stop_clamp[0], stop_clamp[1])

    return _stop


def run_arm(anchors, quad_map, frames, stop_clamp=STOP_CLAMP):
    bars, per_symbol, index = frames
    rows = T.label_rows(
        anchors,
        bars,
        per_symbol,
        index,
        quad_map,
        make_stop_rule(stop_clamp),
        EXIT_CFG,
        ROUND_TRIP_BPS,
        horizon=HORIZON_1H,
        cost_breakeven_bars=COST_BREAKEVEN_1H,
    )
    for r in rows:
        r["real_symbol"] = r.get("real_symbol") or r["symbol"]
    return rows


def non_overlap(rows, fixed_bars=None):
    """同标的上笔未平仓则跳过。

    `fixed_bars` 为 None 时用已实现持仓根数推进（逐笔可解释，但与交易结果相关）；
    传入数值时用固定冷却（不受结果影响，用于敏感性分析）。
    """
    by_symbol = defaultdict(list)
    for r in rows:
        by_symbol[r["real_symbol"]].append(r)
    kept = []
    for _sym, seq in by_symbol.items():
        seq.sort(key=lambda r: r["ts"])
        next_free = -1
        for r in seq:
            if r["ts"] < next_free:
                continue
            kept.append(r)
            hold = fixed_bars if fixed_bars is not None else max(1, int(r["bars"]))
            next_free = r["ts"] + hold * HOUR
    kept.sort(key=lambda r: (r["real_symbol"], r["ts"]))
    return kept


def spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else None


def decile_table(rows):
    if not rows:
        return []
    ordered = sorted(rows, key=lambda r: r["score"])
    n = len(ordered)
    out = []
    for d in range(DECILES):
        lo = d * n // DECILES
        hi = (d + 1) * n // DECILES
        chunk = ordered[lo:hi]
        if not chunk:
            continue
        out.append(
            {
                "decile": d + 1,
                "n": len(chunk),
                "score_lo": round(chunk[0]["score"], 2),
                "score_hi": round(chunk[-1]["score"], 2),
                "E_R": round(statistics.fmean([r["R"] for r in chunk]), 4),
                "E_Rnet": round(statistics.fmean([r["R_net"] for r in chunk]), 4),
                "hit": round(sum(1 for r in chunk if r["R"] > 0) / len(chunk), 4),
            }
        )
    return out


def _group_summary(rows, key):
    return {
        k: {
            "n": len(v),
            "E_R": round(statistics.fmean([r["R"] for r in v]), 4),
            "E_Rnet": round(statistics.fmean([r["R_net"] for r in v]), 4),
        }
        for k, v in T.L._group(rows, key).items()
    }


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sx = (sum((a - mx) ** 2 for a in xs) / n) ** 0.5
    sy = (sum((b - my) ** 2 for b in ys) / n) ** 0.5
    if not sx or not sy:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / (n * sx * sy)


def score_agreement(a_rows, b_rows):
    """两套打分在同一批锚点上有多像 —— 判断「换周期重算」是否真的换了信息。"""
    amap = {(r["real_symbol"], r["ts"]): r["score"] for r in a_rows}
    bmap = {(r["real_symbol"], r["ts"]): r["score"] for r in b_rows}
    common = sorted(set(amap) & set(bmap))
    if len(common) < 3:
        return None
    xs = [amap[k] for k in common]
    ys = [bmap[k] for k in common]
    return {
        "n": len(common),
        "pearson": round(pearson(xs, ys) or 0.0, 4),
        "spearman": round(spearman(xs, ys) or 0.0, 4),
        "mean_diff": round(statistics.fmean(ys) - statistics.fmean(xs), 3),
        "abs_mean_diff": round(statistics.fmean([abs(a - b) for a, b in zip(xs, ys)]), 3),
    }


def subset_stats(rows):
    if not rows:
        return None
    base = T.stats(rows)
    deciles = decile_table(rows)
    base["deciles"] = deciles
    # 逐行秩相关只作描述：3 万级样本上 0.01–0.05 是常态，不能当判据。
    base["spearman"] = spearman([r["score"] for r in rows], [r["R"] for r in rows])
    # 判据用的是「十分位 Spearman」：分位序号 vs 分位 E[R] 的秩相关。
    base["decile_spearman"] = (
        spearman([d["decile"] for d in deciles], [d["E_R"] for d in deciles])
        if len(deciles) >= 3
        else None
    )
    ordered = sorted(rows, key=lambda r: r["score"])
    top_rows = ordered[int(len(rows) * (DECILES - 1) / DECILES) :]
    top = T.stats(top_rows) if top_rows else None
    base["top_decile"] = {
        "n": len(top_rows),
        "score_lo": round(top_rows[0]["score"], 2) if top_rows else None,
        "E_R": top["E_R"] if top else None,
        "E_R_ci80": top["E_R_ci80"] if top else None,
        "E_Rnet": top["E_Rnet"] if top else None,
        "cost_R": top["cost_R"] if top else None,
    }
    base["by_side"] = _group_summary(rows, lambda d: d["side"])
    base["by_month"] = dict(sorted(_group_summary(rows, lambda d: d["month"]).items()))
    return base


# --------------------------------------------------------------------------- #
# 5. 主流程
# --------------------------------------------------------------------------- #
def derive_reading(g0_pass, g1_pass, g3, g4):
    """裁决文案只由四个门的布尔值决定，保证「重渲染」与「重跑」给出同一句话。"""
    if not g0_pass:
        return "G0 未过：管线不可信，结论作废"
    if g3 and g4 and g1_pass:
        return "G3∧G4 全过：1h 存在可交易 alpha，进 Stage C"
    if g3 and g4:
        return "G3∧G4 过但 G1 未过：样本不足，需扩样本再裁决"
    failed = []
    if not g1_pass:
        failed.append("G1 覆盖")
    if not g3:
        failed.append("G3 单调性")
    if not g4:
        failed.append("G4 经济性")
    out = f"未观察到 1h alpha（未过：{'、'.join(failed)}）"
    if not g1_pass:
        out += "；样本低于预登记下限，结论按描述性处理"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--months", default="2026-06,2026-07,2026-08,2026-09,2026-10")
    ap.add_argument("--out", default="reports/analysis/six-factor-1h-20261019")
    ap.add_argument("--stage", default="full", choices=["calib", "full", "rerender"])
    ap.add_argument("--arms", default=",".join(a[0] for a in ARMS))
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.stage == "rerender":
        # 只重画报告：数值来自 metrics.json。用于改文案/表格时不重跑 5 分钟。
        m = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
        v = m["verdict"]
        v["reading"] = derive_reading(
            v["G0_pass"], v["G1"]["pass"], v["G3"]["pass"], v["G4"]["pass"]
        )
        (out_dir / "metrics.json").write_text(
            json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (out_dir / "report.md").write_text(
            render(m, m.get("arms") or {}), encoding="utf-8"
        )
        print(f"rerendered: {v['reading']}", flush=True)
        return

    paths = []
    for m in [x.strip() for x in args.months.split(",") if x.strip()]:
        paths += sorted(Path(args.logs).glob(f"{m}/*/decisions.jsonl"))
    print(f"files={len(paths)}", flush=True)

    rows, skipped = load_panel([str(p) for p in paths])
    print(
        f"15m rows={len(rows):,} symbols={len({r['symbol'] for r in rows})} skipped={skipped}",
        flush=True,
    )
    if not rows:
        raise SystemExit("no rows")

    bars_1h = aggregate_1h(rows)
    bars_4h = aggregate_4h(bars_1h)
    segments, real_of, gaps = T.build_segments(bars_1h)
    print(
        f"1h bars={len(bars_1h):,} 4h bars={len(bars_4h):,} segments={len(segments)} gaps={gaps}",
        flush=True,
    )

    per_seg = prepare_windows(segments, real_of, bars_1h, bars_4h)

    # ---- G0 第一层：手写装配与生产函数逐位等价 ----
    equiv = check_assembly_equivalence(per_seg)
    print(f"G0 assembly equivalence: {equiv}", flush=True)

    # ---- G0 第二层：与日志 score_detail.scores 比对 ----
    calib = calibrate_vs_log(rows, bars_1h) if args.stage == "full" else None
    if calib:
        print(
            f"G0 vs log: rows={calib['rows']:,} overall={calib['overall_exact_rate']:.3f} "
            f"excl_trend={calib['excl_trend_exact_rate']:.3f}",
            flush=True,
        )

    g0_pass = (
        equiv["checked"] >= 8
        and equiv["max_abs_diff"] <= PREREG["G0_assembly_max_abs_diff"]
        and equiv["branch_max_abs_diff"] <= PREREG["G0_assembly_max_abs_diff"]
        and calib is not None
        and calib["excl_trend_exact_rate"] >= PREREG["G0_vs_log_excl_trend_min"]
    )

    metrics = {
        "preregistered": PREREG,
        "constants": {
            "WINDOW_1H": WINDOW_1H,
            "WINDOW_4H": WINDOW_4H,
            "HORIZON_1H": HORIZON_1H,
            "COST_BREAKEVEN_1H": COST_BREAKEVEN_1H,
            "STOP_CLAMP": STOP_CLAMP,
            "STOP_CLAMP_SENS": STOP_CLAMP_SENS,
            "CCI_WINDOW": CCI_WINDOW,
            "ROUND_TRIP_BPS": ROUND_TRIP_BPS,
            "COST_ALT_BPS": COST_ALT_BPS,
            "ATR_SCALE_NORM": ATR_SCALE_NORM,
            "QUAD_MIN": QUAD_MIN,
            "DECILES": DECILES,
            "SCORE_GATES": SCORE_GATES,
            "EXIT_CFG": EXIT_CFG,
        },
        "universe": {
            "files": len(paths),
            "rows_15m": len(rows),
            "symbols_15m": len({r["symbol"] for r in rows}),
            "bars_1h": len(bars_1h),
            "bars_4h": len(bars_4h),
            "segments": len(segments),
            "gaps": gaps,
            "skipped": skipped,
        },
        "g0": {"assembly": equiv, "vs_log": calib, "pass": g0_pass},
    }
    if args.stage == "calib":
        (out_dir / "calib.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("calib written", flush=True)
        return

    # ---- 打分 ----
    log_by_hour = logged_by_hour(rows)
    side_by_key = {}
    for name, seg in per_seg.items():
        for i in range(WINDOW_1H - 1, len(seg["ts"])):
            ts = seg["ts"][i]
            hit = log_by_hour.get((real_of[name], ts))
            if hit:
                side_by_key[(name, ts)] = hit["side"]

    frames = build_label_frames(segments, real_of, bars_1h)
    wanted = [x.strip() for x in args.arms.split(",") if x.strip()]
    results = {}
    arm_rows = {}

    for arm_id, arm_name, cfg in ARMS:
        if arm_id not in wanted:
            continue
        if cfg["source"] == "log":
            anchors = []
            quad_map = {}
            quad_match = [0, 0, 0]
            for name, seg in per_seg.items():
                real = real_of[name]
                for i in range(WINDOW_1H - 1, len(seg["ts"])):
                    ts = seg["ts"][i]
                    hit = log_by_hour.get((real, ts))
                    if not hit or hit["score"] is None:
                        continue
                    # 象限必须与 B 臂走**同一条代码路径**（log 分 → points → quadrant_of），
                    # 否则 A0→B1 会同时改变「分数来源」和「象限来源」两个变量。
                    points = (
                        component_points(hit["scores"], FIB_PA_WEIGHTS)
                        if len(hit["scores"]) == len(SIX_FACTOR_WEIGHTS)
                        else None
                    )
                    if points is None:
                        # 只有 6 个因子分齐全时才能复现象限；否则退回日志值，
                        # 但**不**计入复现率（否则会人为抬高一致率）。
                        quad = hit["quadrant"]
                        quad_match[2] += 1
                    else:
                        quad = quadrant_of(points)
                        quad_match[0] += int(quad == hit["quadrant"])
                        quad_match[1] += 1
                    o, h, l, c, _v = bars_1h[(real, ts)]
                    anchors.append(
                        {
                            "symbol": name,
                            "real_symbol": real,
                            "ts": ts,
                            "side": hit["side"],
                            "score": float(hit["score"]),
                            "quadrant": quad,
                            "action": hit["action"],
                            "risk_allowed": bool(hit["risk_allowed"]),
                            "atr_pct": seg["atr"][i],
                            "open": o,
                            "high": h,
                            "low": l,
                            "close": c,
                            "fib_block": None,
                        }
                    )
                    quad_map[(name, ts)] = quad
            metrics.setdefault("diagnostics", {})["A0_quadrant_match"] = {
                "reproduced": quad_match[0],
                "comparable": quad_match[1],
                "fallback": quad_match[2],
                "rate": round(quad_match[0] / quad_match[1], 4) if quad_match[1] else None,
            }
            print(
                f"   A0 quadrant reproduced from log points: "
                f"{quad_match[0]:,}/{quad_match[1]:,} (fallback {quad_match[2]:,})",
                flush=True,
            )
        else:
            score_map, quad_map = score_arm(per_seg, cfg, side_by_key)
            anchors = []
            for (name, ts), hit in score_map.items():
                real = real_of[name]
                o, h, l, c, _v = bars_1h[(real, ts)]
                anchors.append(
                    {
                        "symbol": name,
                        "real_symbol": real,
                        "ts": ts,
                        "side": hit["side"],
                        "score": hit["total"],
                        "quadrant": hit["quadrant"],
                        "action": "SCORE_ONLY",
                        "risk_allowed": None,
                        "atr_pct": hit["atr_pct"],
                        "open": o,
                        "high": h,
                        "low": l,
                        "close": c,
                        "fib_block": hit["fib_block"],
                    }
                )
        anchors.sort(key=lambda d: (d["symbol"], d["ts"]))
        blocked_keys = {(a["symbol"], a["ts"]) for a in anchors if a.get("fib_block")}
        labeled = run_arm(anchors, quad_map, frames)
        identity = T.check_identity(labeled, ROUND_TRIP_BPS)
        if identity > 1e-9:
            # 成本注入一旦脱钩，「净盈亏」与 `cost_R` 列就会静默错配，
            # 表面有差异实则没生效 —— 直接停，不允许带病出报告。
            raise SystemExit(f"{arm_id}: R_net != R - cost_r (residual {identity:.3e})")
        print(
            f"{arm_id} {arm_name}: anchors={len(anchors):,} labeled={len(labeled):,} "
            f"identity={identity:.2e}",
            flush=True,
        )
        arm_rows[arm_id] = labeled
        results[arm_id] = {
            "name": arm_name,
            "cfg": dict(cfg),
            "anchors": len(anchors),
            "labeled": len(labeled),
            "identity_max_residual": identity,
            "raw": subset_stats(labeled),
            # 主口径：按已实现持仓释放名额（逐笔可解释）；另给固定 8h 冷却作敏感性，
            # 避免「快速止损的单子更早释放名额」这种结果内生的选择偏差。
            "non_overlap": subset_stats(non_overlap(labeled)),
            "non_overlap_fixed": subset_stats(non_overlap(labeled, fixed_bars=HORIZON_1H)),
            "fib_block_excluded": subset_stats(
                [r for r in labeled if (r["symbol"], r["ts"]) not in blocked_keys]
            ),
            "gates": {
                f"score>={int(t)}": subset_stats([r for r in labeled if r["score"] >= t])
                for t in SCORE_GATES
            },
        }
        if arm_id == PRIMARY_ARM:
            sens = run_arm(anchors, quad_map, frames, STOP_CLAMP_SENS)
            results[arm_id]["stop_sensitivity"] = {
                "clamp": list(STOP_CLAMP_SENS),
                "identity_max_residual": T.check_identity(sens, ROUND_TRIP_BPS),
                "raw": subset_stats(sens),
                "non_overlap": subset_stats(non_overlap(sens)),
            }
            print(
                f"   {arm_id} stop-sens clamp={STOP_CLAMP_SENS}: "
                f"E[R]={results[arm_id]['stop_sensitivity']['raw']['E_R']:+.4f}",
                flush=True,
            )

    # ---- 漂移 ----
    drift = []
    for arm_id in wanted:
        rr = arm_rows.get(arm_id)
        if not rr:
            continue
        drift.append(
            {
                "arm": arm_id,
                "name": results[arm_id]["name"],
                "n": len(rr),
                "score_mean": round(statistics.fmean([r["score"] for r in rr]), 3),
                "E_R": round(statistics.fmean([r["R"] for r in rr]), 4),
                "E_Rnet": round(statistics.fmean([r["R_net"] for r in rr]), 4),
                "cost_R": round(statistics.fmean([r["cost_r"] for r in rr]), 4),
            }
        )
    metrics["drift"] = drift

    agree = {}
    if "A0" in arm_rows:
        for other in wanted:
            if other == "A0" or other not in arm_rows:
                continue
            hit = score_agreement(arm_rows["A0"], arm_rows[other])
            if hit:
                agree[f"A0_vs_{other}"] = hit
    metrics["score_agreement"] = agree
    for key, val in agree.items():
        print(f"{key}: {val}", flush=True)

    # ---- 判据 ----
    primary = results.get(PRIMARY_ARM)
    g0b = None
    if results.get("A0") and results["A0"]["raw"]:
        a0_R = results["A0"]["raw"]["E_R"]
        g0b = {
            "E_R": a0_R,
            "expected": STAGE_A_E_R,
            "tolerance": STAGE_A_TOL,
            "pass": abs(a0_R - STAGE_A_E_R) <= STAGE_A_TOL,
        }
    # G1 按**主口径自己的已标注行数**判，不取各臂最大值：B4 因 side 自推丢掉
    # `direction_from_history == NONE` 的行，这是臂的设计而不是数据缺口，
    # 所以面板锚点数另列 `panel_anchors` 供对照，不参与判定。
    n_primary = primary["labeled"] if primary else 0
    n_anchor = n_primary
    n_panel = max((results[a]["labeled"] for a in wanted if a in results), default=0)
    n_symbols = len({r["real_symbol"] for a in wanted for r in arm_rows.get(a, [])})
    score_drift = None
    base_score = next((d["score_mean"] for d in drift if d["arm"] == "A0"), None)
    cur_score = next((d["score_mean"] for d in drift if d["arm"] == PRIMARY_ARM), None)
    if base_score is not None and cur_score is not None:
        score_drift = round(cur_score - base_score, 3)
    # 配对 Δ：只在两臂共有的 (real_symbol, ts) 上算，避免锚点集不同造成的伪差异。
    paired_drift = None
    if "A0" in arm_rows and PRIMARY_ARM in arm_rows:
        a0_map = {(r["real_symbol"], r["ts"]): r["score"] for r in arm_rows["A0"]}
        cur_map = {(r["real_symbol"], r["ts"]): r["score"] for r in arm_rows[PRIMARY_ARM]}
        common = set(a0_map) & set(cur_map)
        if common:
            paired_drift = {
                "n_common": len(common),
                "delta_score": round(
                    statistics.fmean([cur_map[k] for k in common])
                    - statistics.fmean([a0_map[k] for k in common]),
                    3,
                ),
            }

    top = primary["raw"]["top_decile"] if primary and primary["raw"] else None
    top_no = primary["non_overlap"]["top_decile"] if primary and primary["non_overlap"] else None
    decile_rho = primary["raw"]["decile_spearman"] if primary and primary["raw"] else None
    g3 = bool(
        top
        and top["E_R_ci80"]
        and top["E_R_ci80"][0] > PREREG["G3_top_decile_ci80_lower_gt"]
        and decile_rho is not None
        and decile_rho >= PREREG["G3_spearman_min"]
    )
    g4 = bool(
        top_no
        and top_no.get("cost_R") is not None
        and top_no.get("E_R") is not None
        and top_no["E_R"] > top_no["cost_R"]
    )

    verdict = {
        "G0_pass": g0_pass,
        "G0_assembly_max_abs_diff": equiv["max_abs_diff"],
        "G0_assembly_branch_max_abs_diff": equiv["branch_max_abs_diff"],
        "G0_assembly_checked": equiv["checked"],
        "G0_vs_log_excl_trend": calib["excl_trend_exact_rate"] if calib else None,
        "G0b": g0b,
        "G1": {
            "anchors": n_anchor,
            "panel_anchors": n_panel,
            "min_anchors": PREREG["G1_min_anchors"],
            "symbols": n_symbols,
            "min_symbols": PREREG["G1_min_symbols"],
            "pass": n_anchor >= PREREG["G1_min_anchors"]
            and n_symbols >= PREREG["G1_min_symbols"],
        },
        "G2": {
            "score_drift": score_drift,
            "paired_drift": paired_drift,
            "limit": PREREG["G2_score_drift_limit"],
        },
        "G3": {
            "top_decile": top,
            "decile_spearman": decile_rho,
            "row_spearman": primary["raw"]["spearman"] if primary and primary["raw"] else None,
            "pass": g3,
        },
        "G4": {"top_decile_non_overlap": top_no, "pass": g4},
    }
    verdict["G5_proceed_to_stage_c"] = bool(g3 and g4 and verdict["G1"]["pass"])
    verdict["reading"] = derive_reading(g0_pass, verdict["G1"]["pass"], g3, g4)
    metrics["verdict"] = verdict

    # 逐臂明细落盘，报告只是它的渲染视图；避免「报告是旧版、数值是新版」无法反查。
    metrics["arms"] = {
        arm_id: {
            "name": r["name"],
            "cfg": r["cfg"],
            "anchors": r["anchors"],
            "labeled": r["labeled"],
            "identity_max_residual": r["identity_max_residual"],
            "raw": _slim(r["raw"]),
            "non_overlap": _slim(r["non_overlap"]),
            "non_overlap_fixed": _slim(r["non_overlap_fixed"]),
            "fib_block_excluded": _slim(r["fib_block_excluded"]),
            "gates": {k: _slim(v) for k, v in r["gates"].items()},
            "stop_sensitivity": (
                {
                    "clamp": r["stop_sensitivity"]["clamp"],
                    "raw": _slim(r["stop_sensitivity"]["raw"]),
                    "non_overlap": _slim(r["stop_sensitivity"]["non_overlap"]),
                }
                if r.get("stop_sensitivity")
                else None
            ),
        }
        for arm_id, r in results.items()
    }

    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_trades(out_dir / "trades.csv", arm_rows)
    write_drift(out_dir / "drift.csv", drift)
    (out_dir / "report.md").write_text(
        render(metrics, results), encoding="utf-8"
    )
    print(json.dumps(verdict, ensure_ascii=False, indent=2), flush=True)


def _slim(stats):
    """metrics.json 只留关键数字：deciles 太长，留 top/top_decile/spearman 即可。"""
    if not stats:
        return None
    keep = (
        "n", "hit", "E_R", "E_R_ci80", "cost_R", "E_Rnet", "E_Rnet_ci80",
        "bars_median", "stop_pct_median", "spearman", "decile_spearman",
        "top_decile", "reasons", "by_month", "by_side",
    )
    out = {k: stats.get(k) for k in keep if k in stats}
    out["deciles"] = stats.get("deciles")
    return out


def write_trades(path, arm_rows):
    fields = [
        "arm", "symbol", "real_symbol", "ts", "date", "month", "side", "score",
        "quadrant", "stop_pct", "cost_r", "R", "R_net", "bars", "reason",
        "entry_price", "stop_price", "mfe_r",
    ]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for arm, rows in arm_rows.items():
            for r in rows:
                writer.writerow(dict(r, arm=arm))


def write_drift(path, drift):
    if not drift:
        return
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(drift[0].keys()))
        writer.writeheader()
        for d in drift:
            writer.writerow(d)


# --------------------------------------------------------------------------- #
# 6. 报告
# --------------------------------------------------------------------------- #
def _ci(ci):
    return "—" if not ci else f"[{ci[0]:+.4f}, {ci[1]:+.4f}]"


def render(m, results):
    """把 `metrics` 渲染成 markdown。**只读 m / results**，不依赖 main 的局部变量——
    之前直接引用 `arm_rows` 导致 NameError，metrics 已写而报告没更新。"""
    u = m["universe"]
    v = m["verdict"]
    lines = [
        "# Stage B：1h 上重算六因子的 alpha 检验",
        "",
        "> 与 Stage A（15m 因子 + 1h 出场）严格区分：本表是 **1h 因子 + 1h 出场**。",
        "",
        "## 0. 数据与口径",
        "",
        f"- 15m 面板 **{u['rows_15m']:,}** 行 / {u['symbols_15m']} 标的；合成 1h **{u['bars_1h']:,}** 根、"
        f"4h **{u['bars_4h']:,}** 根；连续段 {u['segments']} 个（内部缺口 {u['gaps']} 处）",
        f"- 窗口：1h 固定 {WINDOW_1H} 根（对齐线上 `--public-kline-limit 240`，EMA 路径依赖）、"
        f"4h {WINDOW_4H} 根",
        f"- 出场：ladgex、`horizon={HORIZON_1H}`、`cost_breakeven_bars={COST_BREAKEVEN_1H}`、"
        f"往返 {ROUND_TRIP_BPS:.0f}bps",
        f"- 止损：`clamp(ATR_1h×1.5, {STOP_CLAMP[0]:.3f}, {STOP_CLAMP[1]:.3f})`；象限门槛 {QUAD_MIN}",
    ]
    diag = (m.get("diagnostics") or {}).get("A0_quadrant_match")
    if diag and diag.get("comparable"):
        lines.append(
            f"- A0 的象限用「log 分 → points → 与 B 臂同一函数」重算，与日志 `quadrant` 字段一致 "
            f"**{diag['reproduced']:,}/{diag['comparable']:,}（{diag['rate']:.1%}）**；"
            "差额来自线上象限带 pending 状态机（有滞后），不是重算错误"
        )
    lines += [
        "",
        "## 1. 五臂（逐级只加一个变化）",
        "",
        "| 臂 | 六因子来源 | ATR% | 高周期 | side | 锚点 | 已标注 | `E[R]` | `cost_R` | `E[R_net]` | 80% CI |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for arm_id, _name, cfg in ARMS:
        if arm_id not in results:
            continue
        r = results[arm_id]["raw"]
        if not r:
            continue
        lines.append(
            f"| **{arm_id}** `{results[arm_id]['name']}` | {cfg['source']} | ×{cfg['atr_scale']:.1f} "
            f"| {cfg['high']} | {cfg['side']} | {results[arm_id]['anchors']:,} | {r['n']:,} "
            f"| {r['E_R']:+.4f} | {r['cost_R']:.4f} | {r['E_Rnet']:+.4f} | {_ci(r['E_R_ci80'])} |"
        )

    if m.get("drift"):
        lines += [
            "",
            "> **读法**：全样本 `E[R]` 由出场模拟决定，不是打分的函数——A0–B3 共用同一批锚点与止损，"
            "只通过「象限防御」间接受打分影响，所以差异很小；B4 换了 side，锚点集也变了。"
            "**真正区分各臂的是「选股」**，见下一节。",
            "",
            "## 2. 选股质量（唯一能区分各臂的维度）",
            "",
            "| 臂 | n | top10% `E[R]` | 80% CI | ρ（行） | ρ（十分位） | `≥70` n | `≥70` `E[R]` | `≥82` n | `≥82` `E[R]` |",
            "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|",
        ]
        for arm_id, _n, _cfg in ARMS:
            if arm_id not in results or not results[arm_id]["raw"]:
                continue
            raw = results[arm_id]["raw"]
            top = raw["top_decile"]
            g70 = results[arm_id]["gates"].get("score>=70") or {}
            g82 = results[arm_id]["gates"].get("score>=82") or {}
            rho10 = raw.get("decile_spearman")
            lines.append(
                f"| **{arm_id}** | {raw['n']:,} | {top['E_R']:+.4f} | {_ci(top['E_R_ci80'])} "
                f"| {raw['spearman']:+.3f} | {'n/a' if rho10 is None else f'{rho10:+.3f}'} "
                f"| {g70.get('n', 0):,} | {g70.get('E_R', 0):+.4f} "
                f"| {g82.get('n', 0):,} | {g82.get('E_R', 0):+.4f} |"
            )
        lines += [
            "",
            "### 全样本与漂移",
            "",
            "| 臂 | 名称 | n | score 均值 | `E[R]` | `E[R_net]` | `cost_R` |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for d in m["drift"]:
            lines.append(
                f"| {d['arm']} | `{d['name']}` | {d['n']:,} | {d['score_mean']:.2f} "
                f"| {d['E_R']:+.4f} | {d['E_Rnet']:+.4f} | {d['cost_R']:.4f} |"
            )
        if v["G2"]["score_drift"] is not None:
            lines += [
                "",
                f"`Δscore({PRIMARY_ARM}−A0) = {v['G2']['score_drift']:+.2f}`"
                f"（阈值 ±{v['G2']['limit']:.1f}）",
            ]
        paired = v["G2"].get("paired_drift")
        if paired:
            lines.append(
                f"配对 Δ（{paired['n_common']:,} 个共有锚点，消除锚点集差异）= "
                f"**{paired['delta_score']:+.2f}**"
            )
        if m.get("score_agreement"):
            lines += [
                "",
                "### 两套分数有多像（同锚点配对）",
                "",
                "| 对照 | n | Pearson | Spearman | 均值差 | 平均绝对差 |",
                "|---|---:|---:|---:|---:|---:|",
            ]
            for key, val in m["score_agreement"].items():
                lines.append(
                    f"| `{key}` | {val['n']:,} | {val['pearson']:+.3f} | {val['spearman']:+.3f} "
                    f"| {val['mean_diff']:+.2f} | {val['abs_mean_diff']:.2f} |"
                )
            lines.append(
                "\n> 相关性越低，说明「1h 重算」确实换了信息源，而不是把同一套分数换个算法再算一遍。"
            )

    primary = results.get(PRIMARY_ARM, {}).get("raw")
    sens = results.get(PRIMARY_ARM, {}).get("stop_sensitivity")
    if sens and sens["raw"]:
        lines += [
            "",
            "### 止损敏感性（主口径）",
            "",
            "| 止损 | `cost_R` | `E[R]` | 80% CI | `E[R_net]` |",
            "|---|---:|---:|---|---:|",
            f"| `clamp{tuple(STOP_CLAMP)}` | {primary['cost_R']:.4f} | {primary['E_R']:+.4f} "
            f"| {_ci(primary['E_R_ci80'])} | {primary['E_Rnet']:+.4f} |",
            f"| `clamp{tuple(sens['clamp'])}` | {sens['raw']['cost_R']:.4f} "
            f"| {sens['raw']['E_R']:+.4f} | {_ci(sens['raw']['E_R_ci80'])} "
            f"| {sens['raw']['E_Rnet']:+.4f} |",
        ]

    if primary and primary.get("deciles"):
        lines += [
            "",
            f"## 3. 主口径 {PRIMARY_ARM} 的十分位",
            "",
            "| 分位 | n | score 区间 | `E[R]` | `E[R_net]` | 命中率 |",
            "|---:|---:|---|---:|---:|---:|",
        ]
        for d in primary["deciles"]:
            lines.append(
                f"| {d['decile']} | {d['n']:,} | {d['score_lo']:.1f}–{d['score_hi']:.1f} "
                f"| {d['E_R']:+.4f} | {d['E_Rnet']:+.4f} | {d['hit']:.1%} |"
            )
        if primary.get("spearman") is not None:
            lines += ["", f"Spearman(score, R) = **{primary['spearman']:+.3f}**"]

    if primary and primary.get("by_month"):
        lines += ["", "### 分月", "", "| 月 | n | `E[R]` | `E[R_net]` |", "|---|---:|---:|---:|"]
        for k, val in primary["by_month"].items():
            lines.append(f"| {k} | {val['n']:,} | {val['E_R']:+.4f} | {val['E_Rnet']:+.4f} |")

    lines += ["", "## 4. 判据", "", "| 门 | 判据 | 实测 | 结果 |", "|---|---|---|---|"]
    lines.append(
        f"| G0a | 手写装配 ≡ 生产函数，且归一/无高周期分支不越界 | "
        f"main {v['G0_assembly_max_abs_diff']:.2e} / branch "
        f"{v['G0_assembly_branch_max_abs_diff']:.2e}（{v['G0_assembly_checked']} 组） | "
        f"{'通过' if v['G0_pass'] else '未过'} |"
    )
    if v.get("G0b"):
        lines.append(
            f"| G0b | A0 的 `E[R]` ∈ +0.0040 ± 0.010 | {v['G0b']['E_R']:+.4f} | "
            f"{'通过' if v['G0b']['pass'] else '未过'} |"
        )
    lines.append(
        f"| G0c | 与日志逐位比对（除 trend）≥ 0.95 | {v['G0_vs_log_excl_trend']} | "
        f"{'通过' if (v['G0_vs_log_excl_trend'] or 0) >= PREREG['G0_vs_log_excl_trend_min'] else '未过'} |"
    )
    lines.append(
        f"| G1 | 主口径锚点 ≥ {v['G1']['min_anchors']:,}，标的 ≥ {v['G1']['min_symbols']} | "
        f"{v['G1']['anchors']:,}（面板 {v['G1']['panel_anchors']:,}）/ {v['G1']['symbols']} "
        f"| {'通过' if v['G1']['pass'] else '未过'} |"
    )
    if v["G3"]["top_decile"]:
        td = v["G3"]["top_decile"]
        rho = v["G3"]["decile_spearman"]
        rho_txt = f"{rho:+.3f}" if rho is not None else "n/a"
        lines.append(
            f"| G3 | top-decile `E[R]` 80% 下界 > 0 且十分位 Spearman ≥ 0.5 | "
            f"{td['E_R']:+.4f} {_ci(td['E_R_ci80'])} / ρ10={rho_txt} "
            f"| {'通过' if v['G3']['pass'] else '未过'} |"
        )
    if v["G4"]["top_decile_non_overlap"]:
        td = v["G4"]["top_decile_non_overlap"]
        lines.append(
            f"| G4 | non_overlap top-decile `E[R]` > `cost_R` | {td['E_R']:+.4f} vs "
            f"{td['cost_R']:.4f} | {'通过' if v['G4']['pass'] else '未过'} |"
        )
    lines += ["", f"**裁决：{v['reading']}**", ""]

    gate = [r for r in results.get(PRIMARY_ARM, {}).get("gates", {}).items()]
    if gate:
        lines += ["## 5. 门槛子集（描述性）", "", "| 门槛 | n | `E[R]` | `E[R_net]` | 80% CI |", "|---|---:|---:|---:|---|"]
        for name, s in gate:
            if not s:
                continue
            lines.append(
                f"| `{name}` | {s['n']:,} | {s['E_R']:+.4f} | {s['E_Rnet']:+.4f} | {_ci(s['E_R_ci80'])} |"
            )
        lines.append("")

    prim = results.get(PRIMARY_ARM) or {}
    subs = [
        ("全样本（raw）", prim.get("raw")),
        ("非重叠 · 按已实现持仓", prim.get("non_overlap")),
        ("非重叠 · 固定 8h 冷却", prim.get("non_overlap_fixed")),
        ("剔除 fib 阻断", prim.get("fib_block_excluded")),
    ]
    subs = [(label, s) for label, s in subs if s]
    if subs:
        lines += [
            "",
            "## 5b. 样本构造敏感性（主口径）",
            "",
            "| 子集 | n | `E[R]` | 80% CI | `E[R_net]` |",
            "|---|---:|---:|---|---:|",
        ]
        for label, s in subs:
            lines.append(
                f"| {label} | {s['n']:,} | {s['E_R']:+.4f} | {_ci(s['E_R_ci80'])} "
                f"| {s['E_Rnet']:+.4f} |"
            )
        lines.append("")

    lines += ["", "## 6. 打平门槛（用主口径实测止损中位数）", ""]
    stop_med = (results.get(PRIMARY_ARM) or {}).get("raw", {})
    stop_med = (stop_med or {}).get("stop_pct_median")
    if stop_med:
        lines += [
            f"主口径止损中位数 **{stop_med * 100:.2f}%** → 打平所需 `E[R]`：",
            "",
            "| 成本 | 盈亏平衡 `E[R]` | 主口径实测 `E[R]` | 缺口 |",
            "|---|---:|---:|---:|",
        ]
        for label, bps in (
            ("20bps（现状）", ROUND_TRIP_BPS),
            ("11bps（hybrid_11）", 11.0),
            (f"{COST_ALT_BPS}bps（hybrid_8 真实值）", COST_ALT_BPS),
        ):
            cost = bps / 10000.0 / stop_med
            got = primary["E_R"] if primary else None
            gap = f"{got - cost:+.4f}" if got is not None else "—"
            lines.append(f"| {label} | {cost:.4f} | {got:+.4f} | {gap} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
