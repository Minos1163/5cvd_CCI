from __future__ import annotations

from src.context.multi_tf_rules import MultiTimeframeDecision, build_multi_tf_decision
from src.core.models import IndicatorSnapshot


def build_context(tf_1h: str, tf_30m: str, tf_15m: str, tf_4h: str = "NEUTRAL") -> dict:
    return {
        "context": tf_4h,
        "permission": tf_1h,
        "quality": tf_30m,
        "trigger": tf_15m,
    }


def build_context_from_snapshots(
    tf_4h: IndicatorSnapshot,
    tf_1h: IndicatorSnapshot,
    tf_30m: IndicatorSnapshot,
    tf_15m: IndicatorSnapshot,
    previous_15m_rsi: float | None = None,
) -> MultiTimeframeDecision:
    return build_multi_tf_decision(tf_4h, tf_1h, tf_30m, tf_15m, previous_15m_rsi)
