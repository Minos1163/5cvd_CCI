"""``fwdlib.stats`` 的单测:秩相关 / bootstrap / MDE / BH / 台账 / 性能。

旧实现 ``_legacy_block_bootstrap_mean`` 是从
``scripts/analysis/fwd_label_20261019.py:423-438`` 逐字复制的回归基准,
用来锁定重构后分位索引口径不变。
"""

from __future__ import annotations

import json
import math
import random
import statistics
import time

import pytest

from scripts.analysis.fwdlib.stats import (
    TestLedger,
    bh_adjust,
    block_bootstrap,
    block_bootstrap_mean,
    boot_p,
    cross_sectional_ic,
    daily_pooled_ic,
    mde,
    neff,
    partial_spearman,
    spearman,
)


# --- 旧实现基准(逐字复制,勿改) -----------------------------------------

def _legacy_block_bootstrap_mean(values_by_block, iters=2000, seed=7):
    """按 (symbol,date) 分块重采样,返回 80% 区间。"""
    blocks = [v for v in values_by_block.values() if v]
    if len(blocks) < 5:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(iters):
        pick = [blocks[rng.randrange(len(blocks))] for _ in blocks]
        flat = [x for b in pick for x in b]
        if flat:
            means.append(sum(flat) / len(flat))
    if not means:
        return None
    means.sort()
    return means[int(0.10 * len(means))], means[int(0.90 * len(means))]


# --- 1. spearman ----------------------------------------------------------

def test_spearman_monotone_both_directions():
    assert spearman([1, 2, 3], [10, 20, 30]) == 1.0
    assert spearman([1, 2, 3], [10, 20, 30]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [30, 20, 10]) == -1.0


def test_spearman_ties_match_hand_computation():
    # rx=[1,2,3], ry=[1,2.5,2.5]; num=1.5, dx=sqrt(2), dy=sqrt(1.5)
    expected = 1.5 / (math.sqrt(2.0) * math.sqrt(1.5))
    got = spearman([1, 2, 3], [1, 2, 2])
    assert got is not None
    assert abs(got - expected) < 1e-12
    # 全并列 -> 秩零方差
    assert spearman([1, 2, 3], [7, 7, 7]) is None


def test_spearman_degenerate_inputs_return_none():
    assert spearman([1, 2], [1, 2]) is None
    assert spearman([1, 2, 3], [1, 2]) is None
    assert spearman([5, 5, 5], [1, 2, 3]) is None


def test_spearman_matches_legacy_implementation():
    rng = random.Random(19)
    xs = [rng.gauss(0, 1) for _ in range(50)]
    ys = [0.4 * x + rng.gauss(0, 1) for x in xs]
    legacy = _legacy_spearman(xs, ys)
    assert abs(spearman(xs, ys) - legacy) < 1e-15


def _legacy_spearman(xs, ys):
    """旧脚本 spearman 的逐字副本(用于数值回归)。"""
    n = len(xs)
    if n < 3:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


# --- 2. partial_spearman --------------------------------------------------

def test_partial_spearman_removes_confounder():
    """z 是共同驱动时,控制 z 后相关应大幅下降。

    注:规格里的 ``y = x + z`` 在数学上会让偏相关趋近 1(控制 z 后 y 只剩 x),
    因此这里用等价的混杂结构 ``x = 2z + e1`` / ``y = 3z + e2`` 展示同一性质;
    下面另有一条断言把 ``y = x + z`` 的这种必然结果写清楚。
    """
    rng = random.Random(11)
    zs = [rng.gauss(0, 1) for _ in range(300)]
    xs = [2.0 * z + rng.gauss(0, 1) for z in zs]
    ys = [3.0 * z + rng.gauss(0, 1) for z in zs]

    raw = spearman(xs, ys)
    part = partial_spearman(xs, ys, zs)
    assert raw is not None and part is not None
    assert raw > 0.7
    assert abs(part) < 0.15
    assert abs(part) < abs(raw) - 0.5


def test_partial_spearman_matches_closed_form():
    """残差法与偏相关闭式解 ``(r_xy-r_xz·r_yz)/sqrt(...)`` 等价。"""
    rng = random.Random(23)
    zs = [rng.gauss(0, 1) for _ in range(120)]
    xs = [z + rng.gauss(0, 1) for z in zs]
    ys = [2.0 * z + rng.gauss(0, 1) for z in zs]
    rxy, rxz, ryz = spearman(xs, ys), spearman(xs, zs), spearman(ys, zs)
    expected = (rxy - rxz * ryz) / math.sqrt((1 - rxz**2) * (1 - ryz**2))
    assert abs(partial_spearman(xs, ys, zs) - expected) < 1e-12


def test_partial_spearman_constant_z_is_none():
    """z 秩方差为 0 时选定口径:返回 None(不退化回原始相关)。"""
    xs = [1.0, 2.0, 4.0, 8.0, 16.0]
    ys = [2.0, 1.0, 5.0, 7.0, 9.0]
    assert partial_spearman(xs, ys, [3.0] * 5) is None
    # 长度不等 / 样本不足同样返回 None
    assert partial_spearman([1, 2, 3], [1, 2, 3], [1, 2]) is None
    assert partial_spearman([1, 2], [1, 2], [1, 2]) is None


# --- 3. 新旧 block_bootstrap_mean 等价 -----------------------------------

def test_block_bootstrap_mean_matches_legacy_gaussian():
    rng = random.Random(3)
    data = {f"b{i}": [rng.gauss(0, 1) for _ in range(90)] for i in range(300)}
    old = _legacy_block_bootstrap_mean(data)
    new = block_bootstrap_mean(data)
    assert old is not None and new is not None
    assert abs(new[0] - old[0]) < 1e-9
    assert abs(new[1] - old[1]) < 1e-9


def test_block_bootstrap_mean_matches_legacy_lognormal():
    rng = random.Random(4)
    data = {f"b{i}": [rng.lognormvariate(0.0, 0.6) for _ in range(rng.randint(20, 140))]
            for i in range(400)}
    old = _legacy_block_bootstrap_mean(data)
    new = block_bootstrap_mean(data)
    assert old is not None and new is not None
    assert abs(new[0] - old[0]) < 1e-9
    assert abs(new[1] - old[1]) < 1e-9


def test_block_bootstrap_mean_threshold_and_ordering():
    assert block_bootstrap_mean({f"b{i}": [float(i), 1.0] for i in range(4)}) is None
    # 空块被过滤;剩下的块不足 5 个仍返回 None
    mixed = {f"b{i}": [float(i)] for i in range(4)}
    mixed["empty"] = []
    assert block_bootstrap_mean(mixed) is None
    lo, hi = block_bootstrap_mean({f"b{i}": [float(i)] for i in range(20)})
    assert lo <= hi


# --- 4. mde / neff / boot_p ----------------------------------------------

def test_mde_default_constant():
    assert abs(mde(0.01) - 2.801585 * 0.01) < 1e-6
    assert mde(0.0) == 0.0
    assert mde(None) == 0.0
    assert mde(0.02) == pytest.approx(2 * mde(0.01))


def test_neff_clamps_and_degenerate():
    vals = [0.05, -0.02, 0.08, 0.01, 0.03]
    v = neff(vals, se=0.01)
    assert 1.0 <= v <= len(vals)
    assert neff(vals, se=0.0) == 1.0
    assert neff(vals, se=None) == 1.0
    assert neff([0.1], se=0.01) == 1.0


def test_boot_p_two_sided():
    assert boot_p([0.1, 0.2, 0.3]) == 0.0
    assert boot_p([-0.1, -0.2, -0.3]) == 0.0
    assert boot_p([-1.0, 0.5, 0.6, 0.7]) == pytest.approx(0.5)
    assert boot_p([]) == 0.0
    assert 0.0 <= boot_p([0.0, 0.0, 0.0]) <= 1.0


# --- 5. BH ---------------------------------------------------------------

def test_bh_adjust_matches_reference():
    res = bh_adjust([0.001, 0.01, 0.02, 0.5])
    assert res["m"] == 4
    q = res["q"]
    assert q == sorted(q), "q 必须单调不减(与输入同序)"
    assert abs(q[0] - 0.004) < 1e-6
    assert all(v <= 1.0 for v in q)
    assert res["reject"] == [v <= 0.10 for v in q]


def test_bh_adjust_single_and_empty():
    assert bh_adjust([0.37])["q"] == pytest.approx([0.37])
    assert bh_adjust([0.37])["reject"] == [False]
    assert bh_adjust([]) == {"m": 0, "q": [], "reject": []}


def test_bh_adjust_monotone_on_unsorted_input():
    res = bh_adjust([0.5, 0.001, 0.02, 0.01])
    q = res["q"]
    assert q[0] <= 1.0 and q[1] < q[3] < q[2] < q[0]


# --- 6. cross_sectional_ic / daily_pooled_ic -----------------------------

def _synthetic_rows(sign=1.0, bars=20, n_sym=10, seed=5, small_bar=False):
    rng = random.Random(seed)
    rows = []
    for b in range(bars):
        for s in range(n_sym):
            x = rng.gauss(0, 1)
            y = sign * x + rng.gauss(0, 0.5)
            rows.append({"ts": b, "date": f"d{b}", "sym": s, "x": x, "y": y})
    if small_bar:
        for s in range(5):  # 只有 5 个标的,< min_cs=8
            rows.append({"ts": 999, "date": "d999", "sym": s, "x": float(s), "y": float(s)})
    return rows


def test_cross_sectional_ic_positive_signal():
    out = cross_sectional_ic(_synthetic_rows(1.0), "x", "y")
    assert out["n_bars"] == 20
    assert out["mean_ic"] > 0.5
    assert out["n_obs"] == 200
    assert out["skipped_bars"] == 0
    assert len(out["ics"]) == 20
    assert out["se"] > 0
    assert out["neff"] >= 1.0
    assert out["mde"] > 0
    assert 0.0 <= out["p"] <= 1.0


def test_cross_sectional_ic_negative_signal():
    out = cross_sectional_ic(_synthetic_rows(-1.0), "x", "y")
    assert out["n_bars"] == 20
    assert out["mean_ic"] < -0.5


def test_cross_sectional_ic_skips_small_bars():
    out = cross_sectional_ic(_synthetic_rows(1.0, small_bar=True), "x", "y")
    assert out["n_bars"] == 20
    assert out["skipped_bars"] == 1


def test_cross_sectional_ic_empty():
    out = cross_sectional_ic([], "x", "y")
    assert out["n_bars"] == 0 and out["ics"] == []
    for key in ("mean_ic", "se", "neff", "mde", "p"):
        assert out[key] is None


def test_daily_pooled_ic_legacy_semantics():
    rows = _synthetic_rows(1.0, bars=10, n_sym=10, seed=7)
    # 每天只有 10 行 < min_rows=20 -> 全部跳过
    assert daily_pooled_ic(rows, "x", "y") == {"days": 0, "mean_ic": None, "positive_days": 0}
    out = daily_pooled_ic(rows, "x", "y", min_rows=8)
    assert out["days"] == 10
    assert out["mean_ic"] > 0.5
    assert out["positive_days"] == 10


# --- 7. TestLedger -------------------------------------------------------

def _filled_ledger() -> TestLedger:
    led = TestLedger()
    led.add("ic", "cs_6f", stat=0.12, se=0.03, p=0.001, n=200, n_eff=12.5, mde=0.08,
            meta={"side": "long", "note": "横截面"})
    led.add("ic", "pooled_6f", stat=0.08, n=200, meta={"side": "long"})
    led.add("bootstrap", "E_Rnet", stat=0.02, se=0.01, p=0.04)
    return led


def test_ledger_rejects_duplicate_keys():
    led = _filled_ledger()
    assert len(led) == 3
    with pytest.raises(ValueError):
        led.add("ic", "cs_6f", stat=0.5)


def test_ledger_write_and_merge_roundtrip(tmp_path):
    led = _filled_ledger()
    path = tmp_path / "ledger.jsonl"
    led.write(path)
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == len(led)
    assert all(json.loads(ln)["family"] for ln in lines)
    assert "横截面" in path.read_text(encoding="utf-8"), "ensure_ascii=False"

    merged = TestLedger.merge([path])
    assert len(merged) == len(led)
    assert merged.rows() == led.rows()


def test_ledger_rejects_nonfinite():
    led = TestLedger()
    with pytest.raises(ValueError):
        led.add("x", "y", stat=float("nan"))
    with pytest.raises(ValueError):
        led.add("x", "y", stat=0.1, meta={"se": float("inf")})
    with pytest.raises(ValueError):
        led.add("x", "y", stat=0.1, meta={"obj": object()})
    assert len(led) == 0


def test_ledger_merge_rejects_duplicate_across_files(tmp_path):
    led = _filled_ledger()
    p1 = tmp_path / "a.jsonl"
    p2 = tmp_path / "b.jsonl"
    led.write(p1)
    led.write(p2)
    with pytest.raises(ValueError):
        TestLedger.merge([p1, p2])  # 两个文件都含同一批键 -> 重复入账应报错


# --- 8. 性能 --------------------------------------------------------------

def test_block_bootstrap_mean_performance():
    rng = random.Random(29)
    data = {f"b{i}": [rng.gauss(0, 1) for _ in range(90)] for i in range(715)}
    start = time.perf_counter()
    out = block_bootstrap_mean(data, iters=2000, seed=7)
    elapsed = time.perf_counter() - start
    print(f"\nblock_bootstrap_mean 715 块 x 90 值 x 2000 iters: {elapsed:.3f}s")
    assert out is not None
    assert elapsed < 2.0, f"性能回退:{elapsed:.3f}s >= 2s"
    # block_bootstrap(带完整统计量)同一量级
    start2 = time.perf_counter()
    bb = block_bootstrap(data, iters=2000, seed=7)
    elapsed2 = time.perf_counter() - start2
    print(f"block_bootstrap 同规模: {elapsed2:.3f}s")
    assert bb["n_blocks"] == 715 and bb["n_obs"] == 715 * 90
    assert bb["lo"] <= bb["stat"] <= bb["hi"]
    assert len(bb["samples"]) == 2000
