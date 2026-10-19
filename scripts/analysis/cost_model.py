"""向后兼容 shim: 成本模型已收敛到 `scripts/analysis/fwdlib/cost.py`。

保留 `cost_model` 这个顶层模块名, 是因为 `cost_sensitivity_20261019.py` /
`tf_uplift_20261019.py` 以 `import cost_model as CM` 的方式引用它。
本文件只做转发, 不含任何业务逻辑。
"""

from __future__ import annotations

import sys
from pathlib import Path

try:  # 仓库根在 sys.path 上(pytest / 包内导入)
    from scripts.analysis.fwdlib import cost as _cost
except ImportError:  # 以脚本方式运行: 只有 scripts/analysis 在 sys.path 上
    # `fwdlib/__init__.py` 自己用 `scripts.*` 绝对导入, 所以必须补回仓库根。
    _REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from scripts.analysis.fwdlib import cost as _cost

LegCost = _cost.LegCost
CostModel = _cost.CostModel
CostScenario = _cost.CostScenario

TAKER_FEE_BPS = _cost.TAKER_FEE_BPS
MAKER_FEE_BPS = _cost.MAKER_FEE_BPS
RESIDUAL_SLIP_BPS = _cost.RESIDUAL_SLIP_BPS
MAKER_RESIDUAL_SLIP_BPS = _cost.MAKER_RESIDUAL_SLIP_BPS

TAKER_20 = _cost.TAKER_20
ENTRY_MAKER_13 = _cost.ENTRY_MAKER_13
HYBRID_8 = _cost.HYBRID_8
AGGRESSIVE_4 = _cost.AGGRESSIVE_4
ALL_MODELS = _cost.ALL_MODELS

SCENARIOS = _cost.SCENARIOS

get = _cost.get
breakeven_stop_pct = _cost.breakeven_stop_pct
cost_r = _cost.cost_r
cost_r_distribution = _cost.cost_r_distribution
describe_scenarios = _cost.describe_scenarios

__all__ = [
    "AGGRESSIVE_4",
    "ALL_MODELS",
    "CostModel",
    "CostScenario",
    "ENTRY_MAKER_13",
    "HYBRID_8",
    "LegCost",
    "MAKER_FEE_BPS",
    "MAKER_RESIDUAL_SLIP_BPS",
    "RESIDUAL_SLIP_BPS",
    "SCENARIOS",
    "TAKER_20",
    "TAKER_FEE_BPS",
    "breakeven_stop_pct",
    "cost_r",
    "cost_r_distribution",
    "describe_scenarios",
    "get",
]
