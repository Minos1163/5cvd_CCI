"""``fwdlib.labeler`` 的不变式回归测试。

历史事故:首版标注器把做空的目标价写反,SHORT 命中率被算成 0.4%,靠人眼发现。
本文件用**合成行情**把标注器必须永远满足的性质钉死:

1. 多空镜像(同一批 bar、同一止损宽度);
2. 单调行情的确定性结果(目标 / 止损 / 超时);
3. 零漂移随机游走的命中率 ≈ 0.5、同 seed 可复现;
4. 无前视(改动 ``start`` 之前任何 bar 不影响结果);
5. 时间戳字段自洽。

全部离线:不读 ``D:/AIDCA/AI300/logs``。
"""

from __future__ import annotations

import math

import pytest

from scripts.analysis.fwdlib.labeler import (
    build_bars,
    entry_and_start,
    label_barrier,
    run_labeling,
)
from tests.fixtures.fwdlib.synthetic_bars import (
    flat_ohlc,
    geometric_ohlc,
    make_series,
    mirror_ohlc,
    random_walk_paths,
)

STOP = 0.01
HORIZON = 32


# --------------------------------------------------------------------------- #
# (1) 多空镜像
# --------------------------------------------------------------------------- #

def test_long_short_labels_are_exact_mirror_images() -> None:
    ohlc = mirror_ohlc()
    long_rows = make_series("MIRROR", ohlc, side="LONG", stop_pct=STOP)
    # 同一批 bar,只翻转方向;build_bars 不看 side,可直接复用同一面板
    short_rows = [dict(d, side="SHORT") for d in long_rows]
    bars, per_symbol, index = build_bars(long_rows)

    total = nonambiguous = ambiguous = 0
    for i in range(len(ohlc) - 2):  # 至少要有入场次根 + 一根可平仓 bar
        r_long = label_barrier(bars, per_symbol, index, long_rows[i], STOP)
        r_short = label_barrier(bars, per_symbol, index, short_rows[i], STOP)
        assert r_long is not None and r_short is not None
        total += 1

        if r_long["ambiguous"] or r_short["ambiguous"]:
            # 同根上穿下穿:两边都必须按最不利结算,且单独计数
            assert r_long["ambiguous"] and r_short["ambiguous"]
            assert r_long["R"] == -1.0
            assert r_short["R"] == -1.0
            assert abs((r_long["R"] + r_short["R"]) - (-2.0)) < 1e-12
            ambiguous += 1
        else:
            assert abs(r_long["R"] + r_short["R"]) < 1e-12
            nonambiguous += 1

    # 两类都要真的出现,否则「全是超时 R=0」也能让镜像断言通过
    assert ambiguous > 0
    assert nonambiguous > 0
    # 一条不漏:两类之和 == 总对数
    assert nonambiguous + ambiguous == total == len(ohlc) - 2


# --------------------------------------------------------------------------- #
# (2) 单调行情
# --------------------------------------------------------------------------- #

def test_monotonic_rise_hits_target_for_long_and_stop_for_short() -> None:
    # 每根上涨 1%(= 0.01,与 stop_pct 同量纲),首根可平仓 bar 即越界
    decisions = make_series("UP", geometric_ohlc(40, p0=100.0, step=STOP), stop_pct=STOP)
    bars, per_symbol, index = build_bars(decisions)

    r_long = label_barrier(bars, per_symbol, index, decisions[0], STOP)
    assert r_long is not None
    assert r_long["reason"] == "TARGET_HIT"
    assert r_long["R"] == 1.0
    assert r_long["bars"] == 1

    short = dict(decisions[0], side="SHORT")
    r_short = label_barrier(bars, per_symbol, index, short, STOP)
    assert r_short is not None
    assert r_short["reason"] == "STOP_HIT"
    assert r_short["R"] == -1.0
    assert r_short["bars"] == 1


def test_quiet_series_times_out_at_exactly_horizon() -> None:
    # ±0.1% 的微小波动,远小于 5% 止损 / 目标 → 只能超时
    ohlc = [(100.0, 100.1, 99.9, 100.0)] * 40
    decisions = make_series("QUIET", ohlc, stop_pct=0.05)
    bars, per_symbol, index = build_bars(decisions)

    res = label_barrier(bars, per_symbol, index, decisions[0], 0.05)
    assert res is not None
    assert res["reason"] == "TIMEOUT"
    assert res["bars"] == HORIZON
    assert res["R"] == 0.0


# --------------------------------------------------------------------------- #
# (3) 零漂移随机游走
# --------------------------------------------------------------------------- #

def _label_random_walk(seed: int, n_paths: int = 2000):
    """对每条路径的第 0 根决策行做 next_open barrier 标注。"""
    paths = random_walk_paths(seed, n_paths=n_paths)
    decisions = []
    firsts = []
    for symbol, ohlc in paths:
        rows = make_series(symbol, ohlc, side="LONG", stop_pct=STOP)
        decisions.extend(rows)
        firsts.append(rows[0])
    bars, per_symbol, index = build_bars(decisions)
    results = [label_barrier(bars, per_symbol, index, d, STOP) for d in firsts]
    return paths, results


def test_zero_drift_random_walk_hit_rate_is_half_and_reproducible() -> None:
    n = 2000
    paths_a, results_a = _label_random_walk(seed=11, n_paths=n)
    _, results_b = _label_random_walk(seed=11, n_paths=n)

    assert all(r is not None for r in results_a)
    # 同 seed 必须逐位可复现(浮点运算路径完全相同)
    assert results_a == results_b

    band = 3.0 * math.sqrt(0.25 / n)
    hit_rate = sum(1 for r in results_a if r["R"] > 0.0) / n
    assert abs(hit_rate - 0.5) <= band, (hit_rate, band)

    # 换 seed:路径确实不同,但统计性质仍在带内
    paths_c, results_c = _label_random_walk(seed=12, n_paths=n)
    closes_a = [ohlc[-1][3] for _sym, ohlc in paths_a]
    closes_c = [ohlc[-1][3] for _sym, ohlc in paths_c]
    assert any(a != c for a, c in zip(closes_a, closes_c))
    assert all(r is not None for r in results_c)
    hit_rate_c = sum(1 for r in results_c if r["R"] > 0.0) / n
    assert abs(hit_rate_c - 0.5) <= band, (hit_rate_c, band)


# --------------------------------------------------------------------------- #
# (4) 无前视
# --------------------------------------------------------------------------- #

def _relabel(bars, per_symbol, index, decision, entry_mode: str):
    return label_barrier(bars, per_symbol, index, decision, STOP, entry_mode)


@pytest.mark.parametrize("entry_mode", ["next_open", "bar_close"])
def test_future_bars_do_not_leak_into_label(entry_mode: str) -> None:
    ohlc = flat_ohlc(12)
    decisions = make_series("NOLEAK", ohlc, stop_pct=STOP)
    i = 2
    decision = decisions[i]
    bars, per_symbol, index = build_bars(decisions)
    base = _relabel(bars, per_symbol, index, decision, entry_mode)
    assert base is not None and base["reason"] == "TIMEOUT"

    # start 是「首根可平仓 bar」;入场 bar 在 start-1。
    _entry, start, _last, _order = entry_and_start(
        bars, per_symbol, index, decision, entry_mode, HORIZON
    )
    assert start == i + (1 if entry_mode == "bar_close" else 2)

    # (a) 严格早于入场 bar 的所有 bar:整根改掉也不影响结果
    early = [dict(d) for d in decisions]
    for j in range(start - 1):
        o, h, l, c = decisions[j]["open"], decisions[j]["high"], decisions[j]["low"], decisions[j]["close"]
        early[j].update(open=o * 1.7, high=h * 1.7, low=l * 1.7, close=c * 1.7)
    early_bars, early_ps, early_ix = build_bars(early)
    assert _relabel(early_bars, early_ps, early_ix, early[i], entry_mode) == base

    # (b) 入场 bar 本身:只允许改不参与入场定价的字段。
    #     next_open 的入场价 = 该 bar 开盘;bar_close 的入场价 = 该 bar 收盘。
    entry_bar = start - 1
    entry_only = [dict(d) for d in decisions]
    o, h, l, c = (decisions[entry_bar][k] for k in ("open", "high", "low", "close"))
    if entry_mode == "next_open":
        entry_only[entry_bar].update(high=h * 1.6, low=l * 0.4, close=c * 1.3)
    else:
        entry_only[entry_bar].update(open=o * 1.6, high=h * 1.6, low=l * 0.4)
    entry_bars, entry_ps, entry_ix = build_bars(entry_only)
    assert _relabel(entry_bars, entry_ps, entry_ix, entry_only[i], entry_mode) == base

    # (c) 首根可平仓 bar 变化,结果必须变
    entry_price = base["entry_price"]
    later = [dict(d) for d in decisions]
    later[start].update(open=entry_price, high=entry_price * 1.05,
                        low=entry_price, close=entry_price)
    later_bars, later_ps, later_ix = build_bars(later)
    changed = _relabel(later_bars, later_ps, later_ix, later[i], entry_mode)
    assert changed is not None
    assert changed != base
    assert changed["reason"] == "TARGET_HIT"
    assert changed["R"] == 1.0
    assert changed["bars"] == 1


# --------------------------------------------------------------------------- #
# (5) 时间戳一致性
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("entry_mode", ["next_open", "bar_close"])
def test_entry_exit_timestamps_are_consistent(entry_mode: str) -> None:
    decisions = make_series("TS", mirror_ohlc(), stop_pct=STOP)
    labeled, bars, per_symbol, index, _quad = run_labeling(
        decisions, entry_mode=entry_mode
    )
    assert labeled

    for row in labeled:
        symbol = row["symbol"]
        order = per_symbol[symbol]
        i = index[symbol][row["ts"]]

        entry, start, last, _order = entry_and_start(
            bars, per_symbol, index, row, entry_mode, HORIZON
        )
        # entry_ts 是入场 bar(next_open 为次根开盘,bar_close 为当根收盘)
        assert row["entry_ts"] == order[start - 1]
        # exit_ts 必须是该 symbol 序列里真实存在的时间戳
        assert row["exit_ts"] in set(order)
        assert row["exit_ts"] == order[start + row["bars"] - 1]
        # 持有秒数 = 两个真实 bar 时间戳之差(15m bar 的整数倍)
        assert row["hold_seconds"] == row["exit_ts"] - row["entry_ts"]
        assert row["hold_seconds"] == row["bars"] * 900
        assert 1 <= row["bars"] <= HORIZON
