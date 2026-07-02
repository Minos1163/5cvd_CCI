from __future__ import annotations

import json
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass
class DryRunSummary:
    target_tier: str
    decision_counts: Counter = field(default_factory=Counter)
    recent_decisions: deque = field(default_factory=lambda: deque(maxlen=5))
    stress_risk: deque = field(default_factory=lambda: deque(maxlen=20))
    near_miss_count: int = 0
    near_miss_by_reason: Counter = field(default_factory=Counter)
    recent_near_misses: deque = field(default_factory=lambda: deque(maxlen=10))

    def record_decision(self, decision: Mapping[str, object]) -> None:
        action = str(decision.get("action", "UNKNOWN"))
        self.decision_counts[action] += 1
        self.recent_decisions.append(
            {
                "timestamp": decision.get("timestamp"),
                "symbol": decision.get("symbol"),
                "action": action,
                "score": decision.get("score"),
                "reasons": decision.get("reasons", []),
            }
        )

    def record_stress(self, row: Mapping[str, object]) -> None:
        self.stress_risk.append(dict(row))

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
            "stress_risk": list(self.stress_risk),
            "near_miss_count": self.near_miss_count,
            "near_miss_by_reason": dict(self.near_miss_by_reason),
            "recent_near_misses": list(self.recent_near_misses),
            "data_health": data_health,
            "orders_submitted": orders_submitted,
            "updated_at": int(time.time()),
        }


def write_summary(path: str | Path, summary: DryRunSummary, *, orders_submitted: int, data_health: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(summary.to_dict(orders_submitted=orders_submitted, data_health=data_health), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
