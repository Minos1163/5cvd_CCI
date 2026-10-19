"""``fwd_label_20261019.py`` 薄 shim 的兼容性测试。

下游 7 个脚本仍通过这个模块工作,其中 ``cost_sensitivity_20261019.py`` /
``tf_uplift_20261019.py`` 会用 ``L.ROUND_TRIP_BPS = x`` 注入成本。shim 必须:

1. 保留全部公开名字;
2. 默认参数与旧脚本逐项一致(不回退);
3. **在调用时**读取模块级 ``ROUND_TRIP_BPS``(改副本会静默按 20bps 算);
4. 与 ``fwdlib.labeler`` 直调结果逐行等价。

全部用合成决策,不读真实日志。
"""

from __future__ import annotations

import importlib.util
import inspect
import statistics
import sys
from collections import Counter
from pathlib import Path

import pytest

from scripts.analysis.fwdlib import labeler as fwdlib_labeler
from tests.fixtures.fwdlib.synthetic_bars import make_series

REPO_ROOT = Path(__file__).resolve().parents[1]
SHIM_PATH = REPO_ROOT / "scripts" / "analysis" / "fwd_label_20261019.py"

LEGACY_SURFACE = (
    "COST_BREAKEVEN_BUFFER_MULT",
    "HORIZON_BARS",
    "POST_TP_STOP_OFFSET",
    "ROUND_TRIP_BPS",
    "_entry_and_start",
    "_extract_features",
    "_group",
    "_is_six_factor",
    "block_bootstrap_mean",
    "build_bars",
    "build_quadrant_map",
    "label_barrier",
    "label_ladder",
    "load_decisions",
    "resolve_stop",
    "run_labeling",
    "spearman",
)


def _load_shim():
    name = "fwd_label_shim_compat_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SHIM_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception:  # pragma: no cover - 导入失败时不要把半成品留在 sys.modules
        sys.modules.pop(name, None)
        raise
    return mod


@pytest.fixture(scope="module")
def L():
    return _load_shim()


# --------------------------------------------------------------------------- #
# (1) 公开表面
# --------------------------------------------------------------------------- #

def test_public_surface_is_complete(L) -> None:
    missing = [name for name in LEGACY_SURFACE if not hasattr(L, name)]
    assert missing == []


# --------------------------------------------------------------------------- #
# (2) 签名默认值
# --------------------------------------------------------------------------- #

def test_signature_defaults_do_not_regress(L) -> None:
    assert inspect.signature(L.label_barrier).parameters["entry_mode"].default == "next_open"
    assert inspect.signature(L.label_ladder).parameters["entry_mode"].default == "bar_close"
    assert inspect.signature(L.run_labeling).parameters["entry_mode"].default == "next_open"

    # stage_c_20261019.py: L.resolve_stop(stop, atr, None, None) —— 必须支持 4 个位置参数
    assert L.resolve_stop(0.012, 0.004, None, None) == 0.012
    assert L.resolve_stop(0.004, 0.10, 0.0075, None) == 0.0075
    assert L.resolve_stop(0.01, 0.0, None, 1.2) == pytest.approx(0.012, abs=1e-15)


# --------------------------------------------------------------------------- #
# 合成决策:三行,分别对成本敏感 / 初始止损 / TP 阶梯
# --------------------------------------------------------------------------- #

def _ladder_decisions():
    """三个独立 symbol 的完整 40 根面板(每根一行决策,由 ``run_labeling`` 逐行标注)。

    ``run_labeling`` 需要决策行自带 OHLC 才能拼出完整面板,所以这里给全量 bar;
    只有每个 symbol 的第 0 行承担关键语义:

    * ``COST``:入场后横盘在 +0.06%(0.06R)。8bps 时 0.06 >= 0.5*0.08,继续持有到
      MAX_HOLD;20bps 时 0.06 < 0.5*0.20,在第 8 根触发 COST_BREAKEVEN_TIMEOUT。
      两条路径的**离场价相同**,因此 gross R 相同,两次 ``E_Rnet`` 之差恰好是
      成本差 —— 这正好用来验证成本注入没有别的副作用。
    * ``STOP``:第 1 根直接击穿初始止损,成本不影响。
    * ``TP``  :第 1/2/3 根依次打满三档 TP,之后最大持仓离场,成本不影响。

    其余行(各 symbol 的 i>=1)在 8 根处 pnl 恰为 0,两种成本档都触发同一个
    保本超时,或已经 TP 完毕,因此 gross R 与成本无关。
    """
    cost = [(100.0, 100.0, 100.0, 100.0)] + [(100.06, 100.0601, 100.0599, 100.06)] * 39
    stop = [(100.0, 100.0, 100.0, 100.0), (100.0, 100.0, 98.0, 98.0)] + [(98.0, 98.0, 98.0, 98.0)] * 38
    tp = [
        (100.0, 100.0, 100.0, 100.0),
        (100.0, 102.0, 100.0, 101.5),
        (101.5, 103.0, 101.5, 102.5),
        (102.5, 104.0, 102.5, 103.5),
    ] + [(103.5, 103.6, 103.4, 103.5)] * 36

    decisions = []
    for symbol, ohlc in (("COST", cost), ("STOP", stop), ("TP", tp)):
        decisions.extend(make_series(symbol, ohlc, stop_pct=0.01))
    return decisions


def _run_ladder(L, decisions, bps: float):
    L.ROUND_TRIP_BPS = bps
    labeled, _, _, _, _ = L.run_labeling(
        decisions, exit_mode="ladder", entry_mode="bar_close"
    )
    return labeled


# --------------------------------------------------------------------------- #
# (3) monkeypatch 真的生效
# --------------------------------------------------------------------------- #

def test_round_trip_bps_injection_changes_cost_and_exits(L) -> None:
    decisions = _ladder_decisions()
    try:
        rows8 = _run_ladder(L, decisions, 8.0)
        rows20 = _run_ladder(L, decisions, 20.0)
    finally:
        # 下游依赖模块级默认值 20bps,必须复原
        L.ROUND_TRIP_BPS = 20.0
        assert L.ROUND_TRIP_BPS == 20.0

    assert len(rows8) == len(rows20)
    assert rows8  # 面板足够长,必须真的标注出行

    # 每行成本严格等于 bps/1e4/stop_pct_eff
    for row in rows8:
        assert abs(row["cost_r"] - 8.0 / 1e4 / row["stop_pct_eff"]) < 1e-12
    for row in rows20:
        assert abs(row["cost_r"] - 20.0 / 1e4 / row["stop_pct_eff"]) < 1e-12

    e_rnet8 = statistics.fmean(r["R_net"] for r in rows8)
    e_rnet20 = statistics.fmean(r["R_net"] for r in rows20)
    mean_cost8 = statistics.fmean(r["cost_r"] for r in rows8)
    mean_cost20 = statistics.fmean(r["cost_r"] for r in rows20)

    # R_net = gross_R - cost_R;gross_R 两次相同 ⇒ E8 - E20 == mean(cost20) - mean(cost8)
    assert abs((e_rnet8 - e_rnet20) - (mean_cost20 - mean_cost8)) < 1e-9
    assert e_rnet20 < e_rnet8

    # 成本确实改变了出场判定(不是只改了账面数字)
    reasons8 = Counter(r["reason"] for r in rows8)
    reasons20 = Counter(r["reason"] for r in rows20)
    assert reasons8 != reasons20
    assert reasons20["COST_BREAKEVEN_TIMEOUT"] > reasons8["COST_BREAKEVEN_TIMEOUT"]
    assert reasons8["MAX_HOLD"] > reasons20["MAX_HOLD"]


# --------------------------------------------------------------------------- #
# (4) shim 与 fwdlib 直调等价
# --------------------------------------------------------------------------- #

def test_shim_matches_fwdlib_direct_call(L) -> None:
    decisions = _ladder_decisions()
    original = L.ROUND_TRIP_BPS
    L.ROUND_TRIP_BPS = 20.0
    try:
        shim_rows, *_ = L.run_labeling(decisions, exit_mode="ladder", entry_mode="bar_close")
    finally:
        L.ROUND_TRIP_BPS = original

    lib_rows, *_ = fwdlib_labeler.run_labeling(
        decisions, exit_mode="ladder", entry_mode="bar_close"
    )

    assert len(shim_rows) == len(lib_rows)
    for a, b in zip(shim_rows, lib_rows):
        assert a["symbol"] == b["symbol"]
        assert a["ts"] == b["ts"]
        for key in ("R", "R_net", "reason"):
            assert a[key] == b[key], (a["symbol"], key)
