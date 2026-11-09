"""指标/因子接线矩阵：把"接没接进 live 评分链"从文档里的一句话变成可机检的注册表。

设计原则：
- `status` 只有一个真值，七个取值互斥（见 ``FeatureStatus``）。
- 有 ``weight`` 的条目必须是 ``LIVE_FEATURE`` **且**有 ``read_point``；``read_point``
  精确到行，`tests/test_feature_registry.py::test_read_points_are_real` 会逐行核对
  该行是否真的出现 ``read_point_symbol``。行号漂了测试就红，不允许文档腐坏。
- 权重合计必须为 100（`assert_registry_consistent`），防止改权重时漏改这里。

读法：
- ``LIVE_FEATURE`` → 进 ``total_score``
- ``COMPUTED`` → live 周期在算，但不进评分
- ``IMPLEMENTED`` → 代码可算，没有 live 调用点
- ``SPEC_ONLY`` → 只有规格，无 live 计算
- ``LOGGED_ONLY`` → 只写日志/影子
- ``RISK_INPUT`` → 进风险/仓位，不进评分
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FeatureStatus(str, Enum):
    SPEC_ONLY = "SPEC_ONLY"          # 规格声明存在，无 live 计算
    IMPLEMENTED = "IMPLEMENTED"      # 代码可算，未接入 live
    COMPUTED = "COMPUTED"            # live 周期在算，但不进评分
    LOGGED_ONLY = "LOGGED_ONLY"      # 写日志/影子，不影响决策
    LIVE_FEATURE = "LIVE_FEATURE"    # 进 total_score
    RISK_INPUT = "RISK_INPUT"        # 进风险/仓位
    DISABLED = "DISABLED"            # 显式关闭


@dataclass(frozen=True)
class FeatureEntry:
    name: str
    kind: str
    status: FeatureStatus
    weight: float | None = None
    read_point: str | None = None
    read_point_symbol: str | None = None
    source_field: str | None = None
    timeframe: str | None = None
    note: str = ""


FIB_PA_COMPONENTS = (
    "trend_ema_context",
    "flow_cvd_confirmation",
    "cci_momentum_quality",
    "price_action_structure",
    "fibonacci_location",
    "risk_reward_geometry",
)

FEATURE_REGISTRY: tuple[FeatureEntry, ...] = (
    FeatureEntry(
        name="trend_ema_context",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=20.0,
        read_point="src/signals/entry_chain_features.py:116",
        read_point_symbol="trend_ema_context_score",
        timeframe="15m/1h",
        note="EMA200 方向闸在 soft 模式下只扣分，hard 模式才 veto。",
    ),
    FeatureEntry(
        name="flow_cvd_confirmation",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=18.0,
        read_point="src/signals/entry_chain_features.py:282",
        read_point_symbol="volume_flow_score",
        source_field="candle_signed_volume_flow",
        timeframe="15m",
        note=(
            "不是真主动买卖流。取值仅 {0.0,0.2,0.5,1.0}，乘权重 18 后只可能得 "
            "{0,3.6,9.0,18.0}，实际只有 3 个有效档位。"
        ),
    ),
    FeatureEntry(
        name="cci_momentum_quality",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=14.0,
        read_point="src/signals/entry_chain_features.py:108",
        read_point_symbol='"cci_momentum_quality"',
        timeframe="15m",
        note="离散档位 14/10/7/3/0 先除 14 归一到 0-1，再乘权重。",
    ),
    FeatureEntry(
        name="price_action_structure",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=22.0,
        read_point="src/signals/entry_chain_features.py:109",
        read_point_symbol='"price_action_structure"',
        timeframe="15m",
        note="PA 原始分 0-22，除 22 归一到 0-1。",
    ),
    FeatureEntry(
        name="fibonacci_location",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=18.0,
        read_point="src/signals/entry_chain_features.py:110",
        read_point_symbol='"fibonacci_location"',
        timeframe="15m",
        note="交易层 fib 参数取函数默认值，配置键未被读取。",
    ),
    FeatureEntry(
        name="risk_reward_geometry",
        kind="component",
        status=FeatureStatus.LIVE_FEATURE,
        weight=8.0,
        read_point="src/signals/entry_chain_features.py:111",
        read_point_symbol='"risk_reward_geometry"',
        timeframe="15m",
        note="净 TP1 R 的计算在 risk_reward_geometry_detail，net_tp1_r 于该函数内求得。",
    ),
    FeatureEntry(
        name="rsi14",
        kind="indicator",
        status=FeatureStatus.IMPLEMENTED,
        read_point=None,
        timeframe="15m",
        note="src/indicators/rsi.py 可算；_build_rsi_result 无调用点，live 评分链不读 RSI。",
    ),
    FeatureEntry(
        name="macd",
        kind="indicator",
        status=FeatureStatus.SPEC_ONLY,
        timeframe="15m",
        note="仅存在于 src/indicators/indicator_spec.py 的规格与 indicator_engine 的计算；不进 fib_pa 六分量。",
    ),
    FeatureEntry(
        name="boll",
        kind="indicator",
        status=FeatureStatus.SPEC_ONLY,
        timeframe="15m",
        note="同上；无 live 读取点。",
    ),
    FeatureEntry(
        name="taker_flow_cvd",
        kind="indicator",
        status=FeatureStatus.COMPUTED,
        read_point="src/indicators/cvd.py:6",
        read_point_symbol="def cvd_delta",
        source_field="taker_buy_base_volume",
        timeframe="15m",
        note="真 CVD，用 taker_buy_volume 减卖出量；live 评分不读它，评分用的是 candle_signed_volume_flow。",
    ),
    FeatureEntry(
        name="five_factor_shadow",
        kind="model",
        status=FeatureStatus.LOGGED_ONLY,
        read_point="src/signals/orthogonal_factors.py:491",
        read_point_symbol="shadow_total",
        note="只写 component_points_v2 与 meta，不参与 total_score/象限/通道/杠杆。",
    ),
    FeatureEntry(
        name="net_beta_exposure",
        kind="model",
        status=FeatureStatus.RISK_INPUT,
        read_point="src/risk/net_beta_exposure_model.py:28",
        read_point_symbol="static_v1_observation_only",
        note="命名即 observation_only；cap 值不参与下单阻断。",
    ),
    FeatureEntry(
        name="stress_simulation",
        kind="model",
        status=FeatureStatus.LOGGED_ONLY,
        read_point="src/risk/stress_simulator.py:8",
        read_point_symbol="def stress_decision",
        note="stress 的 action 无代码据此拦单。",
    ),
)


def assert_registry_consistent() -> None:
    names = [entry.name for entry in FEATURE_REGISTRY]
    if len(names) != len(set(names)):
        raise AssertionError("feature registry 存在重名")
    weighted = [entry for entry in FEATURE_REGISTRY if entry.weight]
    total = sum(entry.weight or 0.0 for entry in weighted)
    if abs(total - 100.0) > 1e-9:
        raise AssertionError(f"分量权重合计应为 100，实际 {total}")
    for entry in weighted:
        if entry.status is not FeatureStatus.LIVE_FEATURE:
            raise AssertionError(f"{entry.name} 有权重但状态不是 LIVE_FEATURE")


def registry_snapshot() -> list[dict[str, object]]:
    return [
        {
            "name": entry.name,
            "kind": entry.kind,
            "status": entry.status.value,
            "weight": entry.weight,
            "read_point": entry.read_point,
            "source_field": entry.source_field,
            "timeframe": entry.timeframe,
            "note": entry.note,
        }
        for entry in FEATURE_REGISTRY
    ]
