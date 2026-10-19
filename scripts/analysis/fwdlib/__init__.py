"""前向标注库:从一次性脚本重构出的可复用、可指纹化标注组件。"""

from __future__ import annotations

from scripts.analysis.fwdlib.config import (
    ATR_STOP_MULT,
    BAR_SECONDS,
    COST_BREAKEVEN_BUFFER_MULT,
    COST_BREAKEVEN_CHECK_BARS,
    DEFAULT_COST_BPS,
    FEE_BPS,
    HORIZON_BARS,
    MAX_STOP_PCT,
    MIN_STOP_PCT,
    POST_TP_STOP_OFFSET,
    ROUND_TRIP_BPS,
    SLIPPAGE_BPS,
    TP_FRACTIONS,
    TP_LEVELS,
    TRAILING_R_MULT,
    TREND_TRIGGER_R,
    LabelConfig,
)

__all__ = [
    "ATR_STOP_MULT",
    "BAR_SECONDS",
    "COST_BREAKEVEN_BUFFER_MULT",
    "COST_BREAKEVEN_CHECK_BARS",
    "DEFAULT_COST_BPS",
    "FEE_BPS",
    "HORIZON_BARS",
    "LabelConfig",
    "MAX_STOP_PCT",
    "MIN_STOP_PCT",
    "POST_TP_STOP_OFFSET",
    "ROUND_TRIP_BPS",
    "SLIPPAGE_BPS",
    "TP_FRACTIONS",
    "TP_LEVELS",
    "TRAILING_R_MULT",
    "TREND_TRIGGER_R",
]
