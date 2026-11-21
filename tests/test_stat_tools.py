"""`scripts/analysis/stat_tools.py` 的已知答案验证。

原则：**每条断言都用"能手算的构造数据"**，不拿实现去验证实现。
- `spearman` 的并列分支用手算的 ρ = 15/√262.5 校验（见用例 docstring 推导）；
- t 分布的 p 值用公开临界值（t=2.0/df=10 → 0.0734；t=2.228/df=10 → 0.05）；
- 自助法的区间用"退化样本"（所有值相同 → 区间必须收成一个点）和"块数<2"两种边界，
  而不是只看区间宽窄是否"像"个区间。
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))

from stat_tools import (  # noqa: E402
    assert_alignment,
    average_ranks,
    block_bootstrap,
    pearson,
    permutation_test,
    profit_factor,
    spearman,
    t_two_sided_p,
)


# ---------------------------------------------------------------- 秩


def test_average_ranks_handles_ties_with_average():
    assert average_ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]
    assert average_ranks([5, 5, 5]) == [2.0, 2.0, 2.0]
    assert average_ranks([]) == []


# ---------------------------------------------------------------- Spearman


def test_spearman_perfect_monotone_is_one():
    rho, p = spearman([1, 2, 3, 4], [2, 4, 6, 8])
    assert rho == pytest.approx(1.0)
    assert p == 0.0


def test_spearman_perfect_reverse_is_minus_one():
    rho, _ = spearman([1, 2, 3, 4], [8, 6, 4, 2])
    assert rho == pytest.approx(-1.0)


def test_spearman_with_ties_matches_hand_computation():
    """手算：xr=[2,2,2,4.5,4.5,6]、yr=[1..6]，均值都 3.5

    sxy = 3.75+2.25+0.75+0.5+1.5+6.25 = 15.0
    sxx = 2.25*3+1+1+6.25 = 15.0；syy = 6.25+2.25+0.25+0.25+2.25+6.25 = 17.5
    ρ = 15/√(15×17.5) = 15/√262.5
    """
    rho, p = spearman([1, 1, 1, 2, 2, 3], [1, 2, 3, 4, 5, 6])
    assert rho == pytest.approx(15.0 / math.sqrt(262.5))
    assert 0.0 < p < 0.05


def test_spearman_does_not_pretend_all_ties_are_a_strong_relation():
    """一侧全同值 → ρ 无定义，必须返回 nan 而不是 0（0 会被读成"无相关"）。"""
    rho, p = spearman([1, 1, 1, 1, 1, 1], [1, 2, 3, 4, 5, 6])
    assert math.isnan(rho) and math.isnan(p)


def test_spearman_returns_nan_below_three_points_or_on_length_mismatch():
    assert math.isnan(spearman([1, 2], [2, 4])[0])
    assert math.isnan(spearman([1, 2, 3], [1, 2])[0])


def test_spearman_without_ties_matches_the_textbook_d_squared_formula():
    """无并列时 ρ = 1 − 6Σd²/(n(n²−1))。这里 n=10、只交换最后两名 → Σd²=2。

    ρ = 1 − 6×2/(10×99) = 1 − 12/990 = 0.987878…
    """
    rho, p = spearman(list(range(1, 11)), [1, 2, 3, 4, 5, 6, 7, 8, 10, 9])
    assert rho == pytest.approx(1.0 - 6 * 2 / (10 * 99))
    assert p < 1e-6


def test_spearman_p_value_shrinks_as_relation_strengthens():
    x = list(range(1, 11))
    _, p_weak = spearman(x, [9, 1, 6, 11, 2, 8, 0, 5, 10, 3])  # 近乎无关
    _, p_mid = spearman(x, [1, 2, 3, 4, 6, 5, 7, 8, 9, 10])     # Σd²=2
    _, p_strong = spearman(x, x)
    assert p_strong < p_mid < p_weak


# ---------------------------------------------------------------- t 分布


@pytest.mark.parametrize(("t", "df", "expected"), [(2.0, 10, 0.0734), (2.228, 10, 0.05), (0.0, 10, 1.0)])
def test_t_two_sided_p_matches_published_critical_values(t: float, df: int, expected: float):
    assert t_two_sided_p(t, df) == pytest.approx(expected, abs=5e-3)


def test_pearson_zero_variance_is_nan():
    assert math.isnan(pearson([1, 1, 1], [1, 2, 3]))


# ---------------------------------------------------------------- 分块自助


def test_block_bootstrap_point_estimates_match_direct_computation():
    values = [1.0, -2.0, 3.0, -4.0, 5.0, -6.0]
    ids = ["a|d1", "a|d1", "b|d1", "b|d1", "a|d2", "c|d2"]
    out = block_bootstrap(values, ids, n_boot=200, seed=7)
    assert out["n"] == 6
    assert out["n_blocks"] == 4
    assert out["mean"]["point"] == pytest.approx(sum(values) / len(values))
    assert out["pf"]["point"] == pytest.approx(profit_factor(values))
    assert out["mean"]["ci_low"] <= out["mean"]["ci_high"]
    assert out["pf"]["ci_low"] <= out["pf"]["ci_high"]


def test_block_bootstrap_is_seed_deterministic():
    values = [1.0, -2.0, 3.0, -4.0, 5.0, -6.0, 7.5, -1.5, 2.5, -3.5, 4.5, -0.5, 6.5, -5.5, 0.5, -7.5]
    ids = [f"blk{i // 2}" for i in range(16)]
    first = block_bootstrap(values, ids, n_boot=200, seed=11)
    second = block_bootstrap(values, ids, n_boot=200, seed=11)
    assert first == second
    third = block_bootstrap(values, ids, n_boot=200, seed=12)
    assert (third["mean"]["ci_low"], third["mean"]["ci_high"]) != (
        first["mean"]["ci_low"],
        first["mean"]["ci_high"],
    )


def test_block_bootstrap_degenerate_sample_collapses_interval():
    """所有值相同 → 无论怎么重抽区间都必须收成一个点（真值 2.0 被覆盖）。"""
    out = block_bootstrap([2.0] * 8, ["a", "a", "b", "b", "c", "c", "d", "d"], n_boot=100, seed=3)
    assert out["mean"]["ci_low"] == pytest.approx(2.0)
    assert out["mean"]["ci_high"] == pytest.approx(2.0)
    assert out["mean"]["ci_low"] <= 2.0 <= out["mean"]["ci_high"]


def test_block_bootstrap_needs_at_least_two_blocks():
    """单块时区间无意义——返回 None，不伪造一个零宽区间。"""
    out = block_bootstrap([1.0, -1.0, 2.0], ["only", "only", "only"], n_boot=50, seed=1)
    assert out["n_blocks"] == 1
    assert out["mean"]["ci_low"] is None and out["mean"]["ci_high"] is None
    assert out["n_boot"] == 0


def test_block_bootstrap_rejects_mismatched_inputs():
    with pytest.raises(ValueError):
        block_bootstrap([1.0, 2.0], ["a"], n_boot=10)


def test_profit_factor_is_none_without_losses():
    assert profit_factor([1.0, -1.0, 2.0]) == pytest.approx(3.0)
    assert profit_factor([1.0, 2.0]) is None


# ---------------------------------------------------------------- 置换检验


def test_permutation_test_small_p_for_strong_relation_and_large_p_for_none():
    x = list(range(12))
    strong = permutation_test(x, [v * 2 + 0.1 for v in x], n_perm=500, seed=5)
    assert strong < 0.01
    # 与 x 近乎无关的排列（实测 ρ=−0.0909）→ p 应很大
    unrelated = [9, 1, 6, 11, 2, 8, 0, 5, 10, 3, 7, 4]
    weak = permutation_test(x, unrelated, n_perm=500, seed=5)
    assert weak > 0.2


def test_permutation_test_is_deterministic_and_bounded():
    x = [1, 2, 3, 4, 5, 6, 7, 8]
    y = [2, 1, 4, 3, 6, 5, 8, 7]
    p1 = permutation_test(x, y, n_perm=200, seed=42)
    p2 = permutation_test(x, y, n_perm=200, seed=42)
    assert p1 == p2
    assert 1.0 / 201.0 <= p1 <= 1.0


# ---------------------------------------------------------------- 对齐守卫


def test_assert_alignment_accepts_equal_timestamps():
    assert_alignment(1794618900, 1794618900)
    assert_alignment(1794618900, 1794618900, tol=0)


def test_assert_alignment_rejects_one_bar_offset_and_names_both_values():
    with pytest.raises(ValueError) as excinfo:
        assert_alignment(1794618900, 1794618000)
    message = str(excinfo.value)
    assert "1794618900" in message and "1794618000" in message
    assert "-900" in message


def test_assert_alignment_rejects_missing_values():
    with pytest.raises(ValueError):
        assert_alignment(None, 1794618900)
    with pytest.raises(ValueError):
        assert_alignment(1794618900, None)
