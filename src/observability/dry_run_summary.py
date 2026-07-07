from __future__ import annotations

import json
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


REJECTION_LAYERS = (
    "direct",
    "probe",
    "budget",
    "symbol_policy",
    "side_policy",
    "fib_policy",
    "portfolio",
    "other",
)


@dataclass
class DryRunSummary:
    target_tier: str
    assumptions: Mapping[str, object] = field(default_factory=dict)
    decision_counts: Counter = field(default_factory=Counter)
    recent_decisions: deque = field(default_factory=lambda: deque(maxlen=5))
    gate_rejections_by_layer: Counter = field(default_factory=Counter)
    gate_rejections_by_layer_reason: dict[str, Counter] = field(default_factory=dict)
    stress_risk: deque = field(default_factory=lambda: deque(maxlen=20))
    near_miss_count: int = 0
    near_miss_by_reason: Counter = field(default_factory=Counter)
    recent_near_misses: deque = field(default_factory=lambda: deque(maxlen=10))
    latest_portfolio_exposure: dict[str, object] = field(default_factory=dict)

    def record_decision(self, decision: Mapping[str, object]) -> None:
        action = str(decision.get("action", "UNKNOWN"))
        self.decision_counts[action] += 1
        if action not in {"PROBE", "DIRECT"}:
            self._record_gate_rejections(decision)
        self.recent_decisions.append(
            {
                "timestamp": decision.get("timestamp"),
                "symbol": decision.get("symbol"),
                "action": action,
                "score": decision.get("score"),
                "reasons": decision.get("reasons", []),
            }
        )

    def _record_gate_rejections(self, decision: Mapping[str, object]) -> None:
        reasons = decision.get("reasons", [])
        if not isinstance(reasons, (list, tuple)):
            reasons = [reasons]
        for raw_reason in reasons:
            reason = str(raw_reason)
            layer = rejection_layer(reason)
            if layer is None:
                continue
            self.gate_rejections_by_layer[layer] += 1
            self.gate_rejections_by_layer_reason.setdefault(layer, Counter())[reason] += 1

    def record_stress(self, row: Mapping[str, object]) -> None:
        self.stress_risk.append(dict(row))

    def record_portfolio_snapshot(self, row: Mapping[str, object]) -> None:
        self.latest_portfolio_exposure = dict(row)

    def record_near_miss(self, row: Mapping[str, object]) -> None:
        primary_reason = str(row.get("primary_reason") or "")
        self.near_miss_count += 1
        if primary_reason:
            self.near_miss_by_reason[primary_reason] += 1
        self.recent_near_misses.append(
            {
                "timestamp": row.get("timestamp"),
                "symbol": row.get("symbol"),
                "action": row.get("action"),
                "score": row.get("score"),
                "primary_reason": primary_reason,
            }
        )

    def to_dict(self, *, orders_submitted: int, data_health: str) -> dict:
        return {
            "target_tier": self.target_tier,
            "decision_counts": dict(self.decision_counts),
            "recent_decisions": list(self.recent_decisions),
            "gate_rejections_by_layer": self._gate_rejections_by_layer_dict(),
            "gate_rejections_by_layer_reason": {
                layer: dict(reasons) for layer, reasons in self.gate_rejections_by_layer_reason.items()
            },
            "stress_risk": list(self.stress_risk),
            "near_miss_count": self.near_miss_count,
            "near_miss_by_reason": dict(self.near_miss_by_reason),
            "recent_near_misses": list(self.recent_near_misses),
            "dry_run_assumptions": dict(self.assumptions),
            "latest_portfolio_exposure": dict(self.latest_portfolio_exposure),
            "data_health": data_health,
            "orders_submitted": orders_submitted,
            "updated_at": int(time.time()),
        }

    def _gate_rejections_by_layer_dict(self) -> dict[str, int]:
        payload = {layer: 0 for layer in REJECTION_LAYERS}
        payload.update(dict(self.gate_rejections_by_layer))
        return payload


def write_summary(path: str | Path, summary: DryRunSummary, *, orders_submitted: int, data_health: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary.to_dict(orders_submitted=orders_submitted, data_health=data_health), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def rejection_layer(reason: str) -> str | None:
    if reason == "FIB_PA_ARCHITECTURE_WEIGHTS":
        return None
    if reason.startswith("DIRECT_") or reason.startswith("WAITING_DIRECT_"):
        return "direct"
    if reason.startswith("PROBE_") or reason.startswith("HIGH_BETA_PROBE_"):
        return "probe"
    if reason in {"DAILY_TRADE_BUDGET_USED", "SYMBOL_DAILY_TRADE_BUDGET_USED"}:
        return "budget"
    if reason.startswith("SYMBOL_") or reason in {"SYMBOL_BLACKLISTED", "SYMBOL_WATCH_ONLY"}:
        return "symbol_policy"
    if reason.startswith("SIDE_THRESHOLD_OFFSET_"):
        return "side_policy"
    if reason.startswith("FIB_"):
        return "fib_policy"
    if "EXPOSURE" in reason or "MARGIN" in reason or "CIRCUIT" in reason:
        return "portfolio"
    if reason:
        return "other"
    return None
