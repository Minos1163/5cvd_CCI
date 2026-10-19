"""前向标注的配置层:把旧分析脚本里散落的常量收成一个可指纹化的不可变对象。

常量取值与 ``scripts/analysis/fwd_label_20261019.py`` 逐位一致,便于新库对旧结果做回归。
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass

# --- 成本与时间粒度 -------------------------------------------------------
FEE_BPS = 5.0
SLIPPAGE_BPS = 5.0
ROUND_TRIP_BPS = 2.0 * (FEE_BPS + SLIPPAGE_BPS)
DEFAULT_COST_BPS = 20.0

HORIZON_BARS = 32
BAR_SECONDS = 900

# --- 线上出场常量,与 src/observability/paper_trading.py:16-22 逐项对齐 ---
MIN_STOP_PCT = 0.005
MAX_STOP_PCT = 0.03
ATR_STOP_MULT = 1.5
COST_BREAKEVEN_CHECK_BARS = 8
COST_BREAKEVEN_BUFFER_MULT = 0.5
TP_LEVELS = (1.2, 2.0, 3.0)
TP_FRACTIONS = (0.40, 0.35, 0.25)
POST_TP_STOP_OFFSET = 0.001

# --- trend_capture 出场模式 ----------------------------------------------
TREND_TRIGGER_R = 1.5
TRAILING_R_MULT = 1.0

_ENTRY_MODES = frozenset({"next_open", "bar_close"})
_EXIT_MODES = frozenset({"barrier", "ladder"})
_POST_TP_MODES = frozenset({"legacy", "trend_capture"})

_FRACTION_TOLERANCE = 1e-9


@dataclass(frozen=True, slots=True)
class LabelConfig:
    """一次标注运行的全部口径参数。"""

    horizon_bars: int = 32
    bar_seconds: int = 900
    entry_mode: str = "next_open"
    exit_mode: str = "barrier"
    cost_bps: float = 20.0
    cost_version: str = "taker_20"
    cost_breakeven_bars: int | None = None
    stop_floor: float | None = None
    stop_scale: float | None = None
    min_stop_pct: float = 0.005
    max_stop_pct: float = 0.03
    atr_stop_mult: float = 1.5
    tp_levels: tuple[float, float, float] = (1.2, 2.0, 3.0)
    tp_fractions: tuple[float, float, float] = (0.40, 0.35, 0.25)
    post_tp_mode: str = "legacy"
    quadrant_defense: bool = False
    q2_tighten: bool = False

    def __post_init__(self) -> None:
        if self.horizon_bars < 1:
            raise ValueError(f"horizon_bars 必须 >= 1, 实际 {self.horizon_bars!r}")
        if self.bar_seconds <= 0:
            raise ValueError(f"bar_seconds 必须 > 0, 实际 {self.bar_seconds!r}")
        if self.cost_bps < 0:
            raise ValueError(f"cost_bps 必须 >= 0, 实际 {self.cost_bps!r}")
        if self.entry_mode not in _ENTRY_MODES:
            raise ValueError(f"entry_mode 必须是 {sorted(_ENTRY_MODES)}, 实际 {self.entry_mode!r}")
        if self.exit_mode not in _EXIT_MODES:
            raise ValueError(f"exit_mode 必须是 {sorted(_EXIT_MODES)}, 实际 {self.exit_mode!r}")
        if self.post_tp_mode not in _POST_TP_MODES:
            raise ValueError(
                f"post_tp_mode 必须是 {sorted(_POST_TP_MODES)}, 实际 {self.post_tp_mode!r}"
            )
        if abs(sum(self.tp_fractions) - 1.0) >= _FRACTION_TOLERANCE:
            raise ValueError(f"tp_fractions 之和必须为 1, 实际 {sum(self.tp_fractions)!r}")
        if not 0 < self.min_stop_pct <= self.max_stop_pct:
            raise ValueError(
                f"需满足 0 < min_stop_pct <= max_stop_pct, "
                f"实际 min={self.min_stop_pct!r} max={self.max_stop_pct!r}"
            )

    def resolved_breakeven_bars(self) -> int:
        """成本打平检查的持有根数阈值。默认取 horizon 的 1/4,至少 1 根。"""
        if self.cost_breakeven_bars is None:
            return max(1, self.horizon_bars // 4)
        return self.cost_breakeven_bars

    def replaced(self, **kw: object) -> "LabelConfig":
        """基于当前配置派生新配置(走 __post_init__ 校验)。"""
        return dataclasses.replace(self, **kw)

    def fingerprint(self) -> str:
        """配置内容指纹,用于结果目录命名与实验对照。"""
        fields = {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}
        payload = json.dumps(fields, sort_keys=True, default=str)
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


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
