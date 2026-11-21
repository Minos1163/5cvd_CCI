"""离线统计工具（纯标准库，零依赖）。

为什么单独成模块：归因脚本、负控测试、以及后续的评审复算都要用同一套统计口径。
过去每个脚本各写一份 `spearman`（大多直接 import numpy/scipy 或用简化公式且**不处理并列**），
结果是"同一批数据不同脚本给出不同 ρ"。本模块是唯一出处。

适用边界（**先读再信**）：

- `spearman` 的 p 值用 t 近似（`t = rho*sqrt((n-2)/(1-rho^2))`，df = n-2）。
  n < 10 时 p 值不可信（t 近似 + 并列秩双重误差），只能当"量级参考"；
  n < 3 或任一侧方差为 0 时 ρ 无定义，返回 `(nan, nan)` 而不是 0——
  0 会被误读成"无相关"，而 nan 会强制调用方处理。
- `block_bootstrap` 假设"块之间近似独立"。本项目按 `symbol|utc_day` 分块，理由是
  同一标的同一天的持仓共享行情与同日预算（同向敞口、日交易上限），**不是**独立样本。
  块数为 1 或 0 时区间无意义，直接返回 `None` 区间而不是伪造一个窄区间。
- `permutation_test` 的 p 值分辨率下限是 `1/(n_perm+1)`；n_perm=2000 时最小 0.0005。
  本项目的 47 笔样本远小于此，别把 p=0.0005 当"极显著"。
- 所有函数都**不做**多重比较校正：6 个分量 × 3 个口径 = 18 次比较，
  单看某个 p<0.05 毫无意义，必须配合 block bootstrap 区间与负控一起读。
"""

from __future__ import annotations

import math
import random
from statistics import mean
from typing import Iterable, Sequence


# ---------------------------------------------------------------- 秩与相关


def average_ranks(values: Sequence[float]) -> list[float]:
    """1-based 平均秩（并列取平均），Spearman 必须用它，否则并列会被系统性高估相关。

    例：[10, 20, 20, 30] → [1.0, 2.5, 2.5, 4.0]。
    """
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        shared = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = shared
        i = j + 1
    return ranks


def pearson(x: Sequence[float], y: Sequence[float]) -> float:
    """皮尔逊相关；任一侧方差为 0 时返回 nan（不返回 0，见模块 docstring）。"""
    if len(x) != len(y) or len(x) < 2:
        return float("nan")
    mx, my = mean(x), mean(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx <= 0.0 or syy <= 0.0:
        return float("nan")
    return sxy / math.sqrt(sxx * syy)


def _betacf(a: float, b: float, x: float, max_iter: int = 200, eps: float = 3e-16) -> float:
    """不完全 Beta 函数的连分式（Numerical Recipes 6.4 的 Lentz 变体）。"""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betainc(a: float, b: float, x: float) -> float:
    """正则化不完全 Beta 函数 I_x(a,b)。"""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t: float, df: float) -> float:
    """t 分布双侧 p 值（df>0）。用 I_{df/(df+t²)}(df/2, 1/2) 的恒等式，纯标准库。"""
    if df <= 0 or math.isnan(t):
        return float("nan")
    if math.isinf(t):
        return 0.0
    x = df / (df + t * t)
    return _betainc(df / 2.0, 0.5, x)


def spearman(x: Sequence[float], y: Sequence[float]) -> tuple[float, float]:
    """Spearman 秩相关 + 双侧 p 值（t 近似，df = n-2）。

    并列用**平均秩**处理（见 `average_ranks`）；不处理并列会把"大量同值"误算成高分相关——
    本项目 `flow_cvd_confirmation` 47 笔全是同一值，正是这种情形。

    返回 `(rho, p)`。n < 3、长度不等、任一侧方差为 0 时返回 `(nan, nan)`。
    n < 10 时 p 值不可信（见模块 docstring），只能看 rho 的符号与量级。
    """
    if len(x) != len(y) or len(x) < 3:
        return float("nan"), float("nan")
    rho = pearson(average_ranks(x), average_ranks(y))
    if math.isnan(rho):
        return float("nan"), float("nan")
    rho = max(-1.0, min(1.0, rho))
    n = len(x)
    if abs(rho) >= 1.0:
        return rho, 0.0
    t = rho * math.sqrt((n - 2) / (1.0 - rho * rho))
    return rho, t_two_sided_p(t, n - 2)


# ---------------------------------------------------------------- 分块自助


def profit_factor(values: Iterable[float]) -> float | None:
    """PF = Σ盈利 / |Σ亏损|。无亏损时 PF 无定义（返回 None，不返回 inf/1e9）。"""
    wins = sum(v for v in values if v > 0)
    losses = -sum(v for v in values if v < 0)
    if losses <= 0:
        return None
    return wins / losses


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    """线性插值分位数（与 numpy 默认口径一致：位置 = (n-1)*q）。"""
    if not sorted_values:
        return float("nan")
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    pos = (len(sorted_values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(sorted_values[lo])
    frac = pos - lo
    return float(sorted_values[lo] * (1.0 - frac) + sorted_values[hi] * frac)


def block_bootstrap(
    values: Sequence[float],
    block_ids: Sequence[str],
    *,
    n_boot: int = 2000,
    seed: int = 42,
    alpha: float = 0.05,
) -> dict:
    """按块重抽样的自助区间（净额均值 + PF）。

    为什么必须分块：本项目同一标的同一天的持仓共享行情、同向敞口上限与当日交易预算，
    逐笔独立重抽样会把区间算窄（假装有 47 个独立样本）。按 `symbol|utc_day` 分块后，
    每次重抽**整块**，块内相关性因此保留。

    `block_ids` 与 `values` 等长；相同 id 的样本被视为同一块。

    返回::

        {
          "n": 逐笔样本数, "n_blocks": 块数, "n_boot": 实际有效重抽样次数,
          "mean": {"point":..., "ci_low":..., "ci_high":...},
          "pf":   {"point":..., "ci_low":..., "ci_high":...},   # 无亏损重抽样被跳过，见下
          "skipped_pf": PF 在重抽样中无定义的次数,
          "alpha": alpha,
        }

    边界：块数 < 2 时区间无意义，`ci_low/ci_high` 返回 None 而不是伪造窄区间。
    若某次重抽样里没有亏损笔（PF 无定义），该次不计入 PF 区间，并记入 `skipped_pf`。
    """
    if len(values) != len(block_ids):
        raise ValueError("values 与 block_ids 长度必须一致")
    if n_boot <= 0:
        raise ValueError("n_boot 必须为正")

    blocks: dict[str, list[float]] = {}
    for value, bid in zip(values, block_ids):
        blocks.setdefault(str(bid), []).append(float(value))
    block_keys = sorted(blocks)
    n_blocks = len(block_keys)

    point_mean = mean(values) if values else float("nan")
    point_pf = profit_factor(values)

    report = {
        "n": len(values),
        "n_blocks": n_blocks,
        "n_boot": 0,
        "mean": {"point": point_mean, "ci_low": None, "ci_high": None},
        "pf": {"point": point_pf, "ci_low": None, "ci_high": None},
        "skipped_pf": 0,
        "alpha": alpha,
    }
    if n_blocks < 2 or not values:
        return report

    rng = random.Random(seed)
    means: list[float] = []
    pfs: list[float] = []
    for _ in range(n_boot):
        draw = [rng.choice(block_keys) for _ in range(n_blocks)]
        sample: list[float] = []
        for key in draw:
            sample.extend(blocks[key])
        means.append(mean(sample))
        pf = profit_factor(sample)
        if pf is None:
            report["skipped_pf"] += 1
        else:
            pfs.append(pf)

    report["n_boot"] = n_boot
    means.sort()
    report["mean"]["ci_low"] = _percentile(means, alpha / 2.0)
    report["mean"]["ci_high"] = _percentile(means, 1.0 - alpha / 2.0)
    if pfs:
        pfs.sort()
        report["pf"]["ci_low"] = _percentile(pfs, alpha / 2.0)
        report["pf"]["ci_high"] = _percentile(pfs, 1.0 - alpha / 2.0)
    return report


# ---------------------------------------------------------------- 置换检验


def permutation_test(
    x: Sequence[float],
    y: Sequence[float],
    *,
    n_perm: int = 2000,
    seed: int = 42,
) -> float:
    """置换 y 的双侧 p 值（统计量 = |Spearman ρ|）。

    p = (1 + #{|ρ_perm| ≥ |ρ_obs|}) / (n_perm + 1)——把观测值算进分母，避免 p=0
    这种"无穷显著"的假象（分辨率下限即 1/(n_perm+1)）。

    `x` 固定、只置换 `y`：这对应"分数与盈亏的配对是否可被随机重排复现"。
    n < 3 或 ρ 无定义时返回 nan。
    """
    obs, _ = spearman(x, y)
    if math.isnan(obs) or n_perm <= 0:
        return float("nan")
    rng = random.Random(seed)
    shuffled = list(y)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(shuffled)
        rho, _p = spearman(list(x), shuffled)
        if not math.isnan(rho) and abs(rho) >= abs(obs):
            hits += 1
    return (1.0 + hits) / (n_perm + 1.0)


# ---------------------------------------------------------------- 对齐守卫


def assert_alignment(entry_time: int | None, kline_ts: int | None, tol: int = 0) -> None:
    """断言"账本入场时间"与"决策 K 线时间"同源同刻（默认要求完全相等）。

    为什么需要它：2026-11-14 的一次归因把 `decisions.timestamp`（周期收盘后 10 秒的
    **处理时刻**）当成了 K 线时间，整批样本因此偏移一根 15m K 线，算出 ρ=−0.332 的假象。
    正确键是 `decisions.kline.timestamp`（与 `paper_trades.entry_time` 差 0 秒）。

    **只在离线分析脚本里调用**。不要加到生产链路：生产那边的对齐本来就是对的，
    加断言只会让一次脏数据把正在跑的进程打挂。
    """
    if entry_time is None or kline_ts is None:
        raise ValueError(f"对齐校验需要两个时间戳，收到 entry_time={entry_time!r} kline_ts={kline_ts!r}")
    delta = int(kline_ts) - int(entry_time)
    if abs(delta) > tol:
        raise ValueError(
            f"时间未对齐：paper entry_time={int(entry_time)} 与 decisions kline.timestamp={int(kline_ts)} "
            f"相差 {delta} 秒（容差 {tol}）。常见原因：用了 decisions.timestamp（周期处理时刻，"
            f"通常比 K 线晚 10 秒）而不是 decisions.kline.timestamp。"
        )
