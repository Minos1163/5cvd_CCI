"""声明式入场闸门:把离线扫描出来的条件规则原样搬进线上,不做二次手调。

设计约束(对齐 docs/analysis/stop_floor_and_edge_scan_2026-10-19.md):
  - 规则只描述「特征 + 比较 + 阈值」,没有代码分支,参数来自扫描产物 selected.json;
  - 特征缺失时规则判定为 None(不放行、不算通过),并在 verdict.missing 里留痕;
  - 默认配置 entry_gates 为空 → 完全不改变现有行为。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite, log10
from typing import Any, Mapping

_OPERATORS = {
    ">=": lambda a, b: a >= b,
    ">": lambda a, b: a > b,
    "<=": lambda a, b: a <= b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


@dataclass(frozen=True)
class GateRule:
    feature: str
    op: str
    value: Any
    reason: str | None = None

    def matches(self, features: Mapping[str, Any]) -> bool | None:
        """True/False 为确定判定,None 表示特征缺失或无意义(NaN)。"""
        if self.op not in _OPERATORS:
            raise ValueError(f"unsupported gate operator: {self.op}")
        raw = features.get(self.feature)
        if raw is None:
            return None
        try:
            left, right = float(raw), float(self.value)
        except (TypeError, ValueError):
            return raw == self.value
        if not isfinite(left):
            return None
        return bool(_OPERATORS[self.op](left, right))

    def describe(self) -> str:
        return self.reason or f"{self.feature}{self.op}{self.value}"


@dataclass(frozen=True)
class GateVerdict:
    passed: bool
    rejected_by: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    trace: tuple[tuple[str, bool | None], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "rejected_by": list(self.rejected_by),
            "missing": list(self.missing),
            "trace": [[rule, result] for rule, result in self.trace],
        }


@dataclass
class EntryGate:
    """一组规则的合取闸门。rules 为空时恒通过。"""

    rules: tuple[GateRule, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_config(cls, payload: Any) -> "EntryGate":
        if not payload:
            return cls()
        rules = []
        for item in payload:
            if isinstance(item, GateRule):
                rules.append(item)
                continue
            if not isinstance(item, Mapping):
                raise ValueError(f"entry gate rule must be a mapping, got {type(item).__name__}")
            feature = str(item.get("feature") or "").strip()
            op = str(item.get("op") or "").strip()
            if not feature or op not in _OPERATORS:
                raise ValueError(f"invalid entry gate rule: {item!r}")
            if "value" not in item:
                raise ValueError(f"entry gate rule missing value: {item!r}")
            rules.append(GateRule(feature=feature, op=op, value=item["value"], reason=item.get("reason")))
        return cls(rules=tuple(rules))

    def evaluate(self, features: Mapping[str, Any]) -> GateVerdict:
        rejected: list[str] = []
        missing: list[str] = []
        trace: list[tuple[str, bool | None]] = []
        for rule in self.rules:
            result = rule.matches(features)
            trace.append((rule.describe(), result))
            if result is None:
                missing.append(rule.describe())
            elif not result:
                rejected.append(rule.describe())
        return GateVerdict(
            passed=not rejected and not missing,
            rejected_by=tuple(rejected),
            missing=tuple(missing),
            trace=tuple(trace),
        )

    def __bool__(self) -> bool:
        return bool(self.rules)


def build_gate_features(
    context: Any,
    scores: Mapping[str, float] | None = None,
    kline: Mapping[str, Any] | None = None,
    score_total: float | None = None,
    shadow_total: float | None = None,
    timestamp: int | None = None,
) -> dict[str, Any]:
    """把运行时上下文摊平成与离线扫描同名的特征字典。"""
    features: dict[str, Any] = {}
    for key in (
        "atr_pct",
        "extreme_position_ratio",
        "symbol_exposure_pct",
        "total_exposure_pct",
        "current_volatility_scale",
        "long_overextension_active",
        "long_chase_risk_active",
        "long_cvd_weak_active",
        "long_low_liquidity_session_active",
        "long_upper_wick_risk_active",
    ):
        if hasattr(context, key):
            features[key] = getattr(context, key)
    features["extreme_pos"] = features.get("extreme_position_ratio", 0.0) or 0.0
    features["symbol_exposure"] = features.get("symbol_exposure_pct", 0.0) or 0.0
    features["total_exposure"] = features.get("total_exposure_pct", 0.0) or 0.0
    features["vol_scale"] = features.get("current_volatility_scale", 0.0) or 0.0
    quote_volume = float(getattr(context, "quote_volume_24h", 0.0) or 0.0)
    features["log_qv"] = log10(max(1.0, quote_volume))
    if score_total is not None:
        features["score_pct"] = float(score_total) / 100.0
    if shadow_total is not None:
        features["shadow_pct"] = float(shadow_total) / 100.0
    for name, value in (scores or {}).items():
        try:
            features[name] = float(value)
        except (TypeError, ValueError):
            continue
    if kline:
        try:
            open_px = float(kline.get("open") or 0.0)
            high = float(kline.get("high") or 0.0)
            low = float(kline.get("low") or 0.0)
            close = float(kline.get("close") or 0.0)
            if high > low:
                features["bar_pos"] = (close - low) / (high - low)
            features["bar_change_pct"] = (close - open_px) / open_px if open_px > 0 else 0.0
        except (TypeError, ValueError):
            pass
    if timestamp is not None:
        features["hour"] = (int(timestamp) // 3600) % 24
        features["weekday"] = (int(timestamp) // 86400 + 3) % 7  # 1970-01-01 是周四
    return features
