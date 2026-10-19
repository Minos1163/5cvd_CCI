"""特征层:从决策日志抽取六因子 / 影子因子 / v2 五因子特征。

从 ``scripts/analysis/fwd_label_20261019.py`` 抽出,行为与旧脚本逐位一致,
并修复两处 v2 缺陷:

1. ``normalized_values`` 位于 ``component_points_v2_meta`` 下,旧代码却从
   ``component_points_v2`` 里取,导致 v2 恒为空 dict;
2. 旧循环只遍历 ``FEATURE_KEYS``(不含任何 v2 因子名),即使修好 (1) 也不会
   产出新列。本模块显式写入 ``v2_*`` 键。

``rebuild_price_levels`` 是不部署新字段时的降级路径:直接用日志内嵌 K 线
重建入场价 / 止损价,供账本核对。
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from .config import ATR_STOP_MULT, MAX_STOP_PCT, MIN_STOP_PCT

# --- 六因子线上权重 profile(2026-06-26 起);此前是十因子旧架构,语义不同须排除
SIX_FACTOR_WEIGHTS: dict[str, float] = {
    "cci_momentum_quality": 14.0,
    "fibonacci_location": 18.0,
    "flow_cvd_confirmation": 18.0,
    "price_action_structure": 22.0,
    "risk_reward_geometry": 8.0,
    "trend_ema_context": 20.0,
}

# v2 五因子:键名以 src/signals/orthogonal_factors.py:five_factor_scores()
# 输出的 meta["normalized_values"] 为准。
V2_FACTORS = (
    "trend_persistence",
    "structure_location",
    "order_flow",
    "payoff_geometry",
    "volatility_regime",
)

FEATURE_KEYS: tuple[str, ...] = (
    "trend_ema_context",
    "ema_50_quality",
    "ema_momentum",
    "ema_200_gate",
    "direction_1h",
    "background_4h",
    "quality_30m",
    "trigger_15m",
    "market_regime",
    "volatility_stop",
    "liquidity_execution",
    "cvd_flow",
    "fib_action_cap",
    "fibonacci_location",
    "price_action_structure",
    "flow_cvd_confirmation",
    "cci_momentum_quality",
    "risk_reward_geometry",
)

V2_KEYS: tuple[str, ...] = tuple("v2_" + k for k in V2_FACTORS)

FEATURE_FAMILIES: dict[str, tuple[str, ...]] = {
    "six_factor": (
        "trend_ema_context",
        "flow_cvd_confirmation",
        "cci_momentum_quality",
        "price_action_structure",
        "fibonacci_location",
        "risk_reward_geometry",
    ),
    "v2": V2_KEYS,
    "score": ("score_pct",),
    "shadow": ("shadow_pct",),
}

_NAN = float("nan")


def _num(value) -> float:
    """None / 非数值一律返回 nan(不是 0.0),避免把缺失当成真实低分。"""
    if value is None:
        return _NAN
    try:
        return float(value)
    except (TypeError, ValueError):
        return _NAN


def is_six_factor(weights) -> bool:
    """权重表是否与当前六因子 profile 完全一致。"""
    if not isinstance(weights, dict):
        return False
    if len(weights) != len(SIX_FACTOR_WEIGHTS):
        return False
    return all(abs(float(weights.get(k, -1.0)) - v) < 1e-6 for k, v in SIX_FACTOR_WEIGHTS.items())


def _extract_features(
    r: dict, ec: dict, sd: dict, atr_pct: float, ts: int, *, include_v2: bool = True
) -> dict:
    """旧 18 键取值逻辑逐位保留,另加 v2 五因子归一化值。"""
    scores = sd.get("scores") or {}
    points = r.get("component_points") or {}
    # 旧代码写成 component_points_v2.normalized_values,该键不存在 ⇒ 恒为空 dict
    v2 = (r.get("component_points_v2_meta") or {}).get("normalized_values") or {}
    kline = r.get("kline") or {}
    open_px = kline.get("open")
    high = kline.get("high")
    low = kline.get("low")
    close = kline.get("close")
    bar_pos = None
    if open_px and high and low and close and high > low:
        bar_pos = (close - low) / (high - low)
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    feat = {
        "score_pct": (sd.get("total_score") or 0.0) / 100.0,
        "shadow_pct": ((r.get("component_points_v2_meta") or {}).get("shadow_total") or 0.0) / 100.0,
        "atr_pct": atr_pct,
        "log_qv": math.log10(max(1.0, float(ec.get("quote_volume_24h") or 1.0))),
        "extreme_pos": float(ec.get("extreme_position_ratio") or 0.0),
        "symbol_exposure": float(ec.get("symbol_exposure_pct") or 0.0),
        "total_exposure": float(ec.get("total_exposure_pct") or 0.0),
        "daily_profit": float(ec.get("daily_profit_pct") or 0.0),
        "vol_scale": float(ec.get("current_volatility_scale") or 0.0),
        "btc_daily": float((r.get("market_snapshot") or {}).get("btc_daily_return") or 0.0),
        "btc_weekly": float((r.get("market_snapshot") or {}).get("btc_weekly_return") or 0.0),
        "bar_pos": bar_pos if bar_pos is not None else 0.5,
        "hour": dt.hour,
        "weekday": dt.weekday(),
    }
    for k in FEATURE_KEYS:
        if k in scores:
            feat[k] = float(scores.get(k) or 0.0)
        elif k in points:
            feat[k] = float(points.get(k) or 0.0) / 100.0
        elif k in v2:
            feat[k] = float(v2.get(k) or 0.0)
        else:
            feat[k] = _NAN
    if include_v2:
        # FEATURE_KEYS 不含 v2 因子名,必须显式展开,否则修好上面那行也不会出新列
        for name in V2_FACTORS:
            feat["v2_" + name] = _num(v2.get(name))
    return feat


def extract_features(
    r: dict, ec: dict, sd: dict, atr_pct: float, ts: int, *, include_v2: bool = True
) -> dict:
    """`_extract_features` 的公开别名。"""
    return _extract_features(r, ec, sd, atr_pct, ts, include_v2=include_v2)


def load_decisions(
    paths: list[str], profile: str = "any", *, include_v2: bool = True
) -> list[dict]:
    """去重后返回候选决策。side 取 entry_context.side(方向候选),不是 decision.side。"""
    seen = set()
    out = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                kline = r.get("kline") or {}
                ts = kline.get("timestamp")
                sym = r.get("symbol")
                if ts is None or not sym:
                    continue
                ec = r.get("entry_context") or {}
                side = (ec.get("side") or "").upper()
                if side not in {"LONG", "SHORT"}:
                    continue
                if profile == "six_factor" and not is_six_factor(r.get("weights")):
                    continue
                key = (sym, int(ts))
                if key in seen:
                    continue
                seen.add(key)
                sd = r.get("score_detail") or {}
                meta = r.get("component_points_v2_meta") or {}
                atr_pct = float(ec.get("atr_pct") or 0.0)
                out.append(
                    {
                        "symbol": sym,
                        "ts": int(ts),
                        "side": side,
                        "score": sd.get("total_score"),
                        "shadow": meta.get("shadow_total"),
                        "stop_pct": ec.get("stop_pct"),
                        "quadrant": r.get("quadrant"),
                        "action": r.get("action"),
                        "risk_allowed": bool(r.get("risk_allowed")),
                        "open": kline.get("open"),
                        "high": kline.get("high"),
                        "low": kline.get("low"),
                        "close": kline.get("close"),
                        "atr_pct": atr_pct,
                        "reasons": r.get("reasons") or [],
                        "feat": _extract_features(
                            r, ec, sd, atr_pct, int(ts), include_v2=include_v2
                        ),
                    }
                )
    return out


def _nonnull(v) -> bool:
    if v is None:
        return False
    try:
        return not math.isnan(float(v))
    except (TypeError, ValueError):
        return True


def feature_coverage(rows: list[dict]) -> dict:
    """每个特征的样本数 / 非空数 / 非空占比。缺失 v2 记为 nan,因此能被正确统计。"""
    keys = tuple(FEATURE_KEYS) + tuple(V2_KEYS) + ("score_pct", "shadow_pct")
    n = len(rows)
    cov = {}
    for k in keys:
        nonnull = 0
        for row in rows:
            if _nonnull((row.get("feat") or {}).get(k)):
                nonnull += 1
        cov[k] = {
            "n": n,
            "nonnull": nonnull,
            "nonnull_pct": (nonnull / n) if n else 0.0,
        }
    return cov


def _risk_budget_stop_pct(d: dict):
    budget = ((d.get("metadata") or {}).get("risk_budget") or {})
    return budget.get("stop_pct")


def rebuild_price_levels(d, bars, per_symbol, index, entry_mode="next_open") -> dict:
    """用日志内嵌 K 线重建入场价/止损价,用于不部署新字段时的账本核对。

    止损宽度优先级: metadata.risk_budget.stop_pct → entry_context.stop_pct →
    clamp(atr_pct * 1.5, MIN_STOP_PCT, MAX_STOP_PCT)。取不到时对应字段为 None,
    并把 ``*_source`` 标成 ``"missing"``。
    """
    out = {
        "entry_price": None,
        "stop_price": None,
        "stop_pct": None,
        "entry_price_source": "missing",
        "stop_pct_source": "missing",
    }

    # --- 止损宽度 ---
    ec = d.get("entry_context") or {}
    raw_stop = _risk_budget_stop_pct(d)
    if raw_stop is not None and float(raw_stop) > 0:
        stop_pct = float(raw_stop)
        out["stop_pct_source"] = "risk_budget"
    else:
        ec_stop = ec.get("stop_pct")
        if ec_stop is not None and float(ec_stop) > 0:
            stop_pct = float(ec_stop)
            out["stop_pct_source"] = "entry_context"
        else:
            atr_pct = d.get("atr_pct")
            if atr_pct is None:
                atr_pct = ec.get("atr_pct")
            if atr_pct is None:
                return out
            stop_pct = min(MAX_STOP_PCT, max(MIN_STOP_PCT, float(atr_pct) * ATR_STOP_MULT))
            out["stop_pct_source"] = "atr_fallback"
    out["stop_pct"] = stop_pct

    # --- 入场价 ---
    sym, ts = d.get("symbol"), d.get("ts")
    entry = None
    if entry_mode == "bar_close":
        entry = (d.get("kline") or {}).get("close")
        if entry is None:
            entry = d.get("close")
        if entry is not None:
            out["entry_price_source"] = "bar_close"
    else:
        order = per_symbol.get(sym) or []
        i = index.get(sym, {}).get(ts)
        if i is not None and i + 1 < len(order):
            bar = bars.get((sym, order[i + 1]))
            if bar:
                entry = bar[0]
                out["entry_price_source"] = "next_open"
    if entry is None:
        return out
    out["entry_price"] = float(entry)

    # --- 止损价 ---
    side = (d.get("side") or ec.get("side") or "").upper()
    if side not in {"LONG", "SHORT"}:
        return out
    sign = -1.0 if side == "SHORT" else 1.0
    out["stop_price"] = float(entry) * (1.0 - sign * stop_pct)
    return out


__all__ = [
    "FEATURE_FAMILIES",
    "FEATURE_KEYS",
    "SIX_FACTOR_WEIGHTS",
    "V2_FACTORS",
    "V2_KEYS",
    "extract_features",
    "feature_coverage",
    "is_six_factor",
    "load_decisions",
    "rebuild_price_levels",
]
