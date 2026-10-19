"""统计工具层:把 ``fwd_label_20261019.py`` 里散落的 spearman / bootstrap / 日 IC
收敛成唯一实现,且保持与旧脚本逐位可比的数值。

设计约束:
* 本模块**零内部依赖**(不 import ``fwdlib.config``),可被单测直接引用;
* 旧实现中会被下游脚本按位比对的算法(秩、分位索引、重采样顺序)一律保留原样,
  只把 bootstrap 的内层聚合从"摊平后求均值"改成按块 ``(sum, count)`` 累加。
"""

from __future__ import annotations

import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Sequence

__all__ = [
    "TestLedger",
    "bh_adjust",
    "block_bootstrap",
    "block_bootstrap_mean",
    "boot_p",
    "cross_sectional_ic",
    "daily_pooled_ic",
    "mde",
    "neff",
    "partial_spearman",
    "spearman",
]


# --- 秩与相关 -------------------------------------------------------------

def _ranks(values: Sequence[float]) -> list[float]:
    """平均秩(1 基)。并列取组内位置均值,与旧脚本 ``spearman`` 内嵌实现逐位一致。"""
    n = len(values)
    order = sorted(range(n), key=lambda i: values[i])
    r = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """朴素 Pearson(两侧零方差返回 ``None``)。

    分母取 ``sqrt(Σdx²·Σdy²)``(一次开方)而不是 ``sqrt(Σdx²)·sqrt(Σdy²)``,
    使完全单调/完全反单调的输入精确返回 ±1.0;与旧脚本两次开方的写法只差
    末位 1 ulp。
    """
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sx = sum((a - mx) ** 2 for a in xs)
    sy = sum((b - my) ** 2 for b in ys)
    if sx == 0 or sy == 0:
        return None
    return num / math.sqrt(sx * sy)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman 秩相关(平均秩处理并列)。

    返回 ``None`` 的情形:样本数 < 3、两侧长度不等、任一侧秩零方差。
    数值结果与 ``fwd_label_20261019.spearman`` 完全一致(同一秩算法与累加顺序)。
    """
    xs = list(xs)
    ys = list(ys)
    n = len(xs)
    if n < 3 or len(ys) != n:
        return None
    return _pearson(_ranks(xs), _ranks(ys))


def partial_spearman(xs, ys, zs) -> float | None:
    """控制 ``zs`` 后的偏 Spearman:秩残差法。

    对 ``rank(xs)``、``rank(ys)`` 分别关于 ``rank(zs)`` 做带截距的最小二乘回归,
    取残差后再求 Pearson。``zs`` 秩零方差(常量)时回归无定义,返回 ``None``
    ——本模块选定的口径是 ``None`` 而不是退化成原始相关。
    """
    xs = list(xs)
    ys = list(ys)
    zs = list(zs)
    n = len(xs)
    if n < 3 or len(ys) != n or len(zs) != n:
        return None
    rx, ry, rz = _ranks(xs), _ranks(ys), _ranks(zs)
    mz = sum(rz) / n
    var_z = sum((v - mz) ** 2 for v in rz)
    if var_z == 0:
        return None
    mrx, mry = sum(rx) / n, sum(ry) / n
    cov_xz = sum((a - mrx) * (c - mz) for a, c in zip(rx, rz))
    cov_yz = sum((b - mry) * (c - mz) for b, c in zip(ry, rz))
    bx = cov_xz / var_z
    by = cov_yz / var_z
    ax = mrx - bx * mz
    ay = mry - by * mz
    ex = [a - (ax + bx * c) for a, c in zip(rx, rz)]
    ey = [b - (ay + by * c) for b, c in zip(ry, rz)]
    return _pearson(ex, ey)


# --- Bootstrap ------------------------------------------------------------

def block_bootstrap_mean(values_by_block, iters=2000, seed=7):
    """按块重采样,返回 80% 分位区间 ``(lo, hi)``;块数 < 5 返回 ``None``。

    与旧实现的差异**仅在内层聚合**:旧版把每次重采样的块摊平成一个 list 再求
    ``sum/len``,本版预先把每块折成 ``(sum, count)``,内层只做 ``Σsum/Σcount``,
    复杂度从 ``O(iters·n)`` 降到 ``O(iters·n_blocks)``。浮点差异在 1e-12 相对
    量级内。分位口径保持旧版原样的**整数索引** ``means[int(0.10*len)]`` /
    ``means[int(0.90*len)]``(非插值);需要插值分位请用 :func:`block_bootstrap`。
    """
    blocks = [list(v) for v in values_by_block.values() if v]
    if len(blocks) < 5:
        return None
    sums = [sum(b) for b in blocks]
    counts = [len(b) for b in blocks]
    nb = len(blocks)
    rng = random.Random(seed)
    randrange = rng.randrange
    # 一次性抽完,调用次数与顺序和旧版 [blocks[randrange] for _ in blocks] 完全一致
    picks_all = [randrange(nb) for _ in range(nb * iters)]
    get_sum = sums.__getitem__
    get_cnt = counts.__getitem__
    means = []
    for it in range(iters):
        picks = picks_all[it * nb:(it + 1) * nb]
        cnt = sum(map(get_cnt, picks))
        if cnt:
            means.append(sum(map(get_sum, picks)) / cnt)
    if not means:
        return None
    means.sort()
    return means[int(0.10 * len(means))], means[int(0.90 * len(means))]


def _quantile_linear(sorted_vals: Sequence[float], p: float) -> float:
    """线性插值分位(h = (n-1)·p),用于可配置置信水平的区间。"""
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    h = (len(sorted_vals) - 1) * p
    lo = math.floor(h)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = h - lo
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * frac


def block_bootstrap(values_by_block, *, iters=2000, seed=7, ci=0.95) -> dict:
    """块 bootstrap 的完整结果。

    返回 ``{"stat", "se", "lo", "hi", "n_blocks", "n_obs", "samples"}``:

    * ``stat``:全部观测的均值(点估计);
    * ``se``:重采样均值的样本标准差(``len(samples) < 2`` 时为 ``None``);
    * ``lo``/``hi``:重采样均值的 ``ci`` 区间,用**线性插值**分位
      ``h = (n-1)·p``。注意这与 :func:`block_bootstrap_mean` 的整数索引口径
      不同(后者的 80% 区间不等于本函数 ``ci=0.80`` 的结果);
    * ``samples``:重采样均值列表(未排序)。

    块数 < 5 时沿用旧阈值:``stat`` 仍给出(若有点),``se``/``lo``/``hi`` 为
    ``None``,``samples`` 为空列表。
    """
    if not 0.0 < ci < 1.0:
        raise ValueError(f"ci 必须落在 (0,1): {ci!r}")
    blocks = [list(v) for v in values_by_block.values() if v]
    n_blocks = len(blocks)
    n_obs = sum(len(b) for b in blocks)
    stat = (sum(sum(b) for b in blocks) / n_obs) if n_obs else None
    out = {
        "stat": stat,
        "se": None,
        "lo": None,
        "hi": None,
        "n_blocks": n_blocks,
        "n_obs": n_obs,
        "samples": [],
    }
    if n_blocks < 5:
        return out

    sums = [sum(b) for b in blocks]
    counts = [len(b) for b in blocks]
    nb = n_blocks
    rng = random.Random(seed)
    randrange = rng.randrange
    get_sum = sums.__getitem__
    get_cnt = counts.__getitem__
    samples = []
    for _ in range(iters):
        picks = [randrange(nb) for _ in range(nb)]
        cnt = sum(map(get_cnt, picks))
        if cnt:
            samples.append(sum(map(get_sum, picks)) / cnt)
    if not samples:
        return out

    srt = sorted(samples)
    tail = (1.0 - ci) / 2.0
    out["samples"] = samples
    out["lo"] = _quantile_linear(srt, tail)
    out["hi"] = _quantile_linear(srt, 1.0 - tail)
    out["se"] = statistics.stdev(samples) if len(samples) >= 2 else None
    return out


def boot_p(samples, null=0.0) -> float:
    """双尾 bootstrap p 值:``2 * min(P(x<=null), P(x>=null))``,clamp 到 [0,1]。

    样本为空时返回 ``0.0``(无证据即不拒绝的保守缺省,由调用方决定是否使用)。
    """
    vals = list(samples)
    if not vals:
        return 0.0
    n = len(vals)
    le = sum(1 for v in vals if v <= null) / n
    ge = sum(1 for v in vals if v >= null) / n
    return min(1.0, max(0.0, 2.0 * min(le, ge)))


# --- 效应量与有效样本 -----------------------------------------------------

def mde(se, alpha=0.05, power=0.80) -> float:
    """最小可检测效应:``(z_{1-alpha/2} + z_{power}) · se``。

    ``se`` 非正或 ``None`` 返回 ``0.0``。α=0.05 / power=0.80 时系数为
    2.801585…(由 ``statistics.NormalDist().inv_cdf`` 现算,不硬编码)。
    """
    if se is None or se <= 0:
        return 0.0
    nd = statistics.NormalDist()
    return (nd.inv_cdf(1.0 - alpha / 2.0) + nd.inv_cdf(power)) * se


def neff(per_obs, se) -> float:
    """有效样本数 ``(stdev(per_obs)/se)^2``,clamp 到 ``[1, len(per_obs)]``。

    ``se`` 非正/``None`` 或样本 < 2 时返回 ``1.0``。
    """
    vals = list(per_obs)
    if se is None or se <= 0 or len(vals) < 2:
        return 1.0
    sd = statistics.stdev(vals)
    raw = (sd / se) ** 2
    if not math.isfinite(raw):
        return 1.0
    return float(min(max(raw, 1.0), float(len(vals))))


# --- 横截面 / 池化 IC -----------------------------------------------------

def cross_sectional_ic(rows, value_key, target_key, *, ts_key="ts", date_key="date",
                       min_cs=8, block_key="date", iters=2000, seed=7) -> dict:
    """逐 bar 横截面 IC + 按时间块 bootstrap 的显著性。

    按 ``ts_key`` 分组,每组样本数 ``>= min_cs`` 才计算 spearman,得到逐 bar IC
    序列,再对时间取 ``fmean``;``se`` 由 ``block_key``(默认按日)分块 bootstrap
    得到,``neff``/``mde`` 复用本模块实现,``p`` 为双尾 bootstrap p 值。

    ``skipped_bars`` 同时计入"样本不足 ``min_cs``"与"秩零方差导致 IC 为 None"
    的 bar。``n_bars == 0`` 时除 ``n_obs``/``skipped_bars`` 外的统计量均为
    ``None``,``ics`` 为空列表。
    """
    groups: dict[Any, list[tuple[Any, Any, Any]]] = {}
    for r in rows:
        v = r.get(value_key)
        t = r.get(target_key)
        if v is None or t is None:
            continue
        groups.setdefault(r.get(ts_key), []).append((v, t, r.get(block_key)))

    ics: list[tuple[Any, float, int]] = []
    by_block: dict[Any, list[float]] = {}
    n_obs = 0
    skipped = 0
    for ts, items in groups.items():
        if len(items) < min_cs:
            skipped += 1
            continue
        ic = spearman([it[0] for it in items], [it[1] for it in items])
        if ic is None:
            skipped += 1
            continue
        ics.append((ts, ic, len(items)))
        n_obs += len(items)
        by_block.setdefault(items[0][2], []).append(ic)

    out = {
        "n_bars": len(ics),
        "n_obs": n_obs,
        "mean_ic": None,
        "se": None,
        "neff": None,
        "mde": None,
        "p": None,
        "ics": ics,
        "skipped_bars": skipped,
    }
    if not ics:
        return out

    vals = [ic for _ts, ic, _n in ics]
    bb = block_bootstrap(by_block, iters=iters, seed=seed)
    se = bb["se"]
    out["mean_ic"] = statistics.fmean(vals)
    out["se"] = se
    out["p"] = boot_p(bb["samples"]) if bb["samples"] else None
    if se is not None:
        out["neff"] = neff(vals, se)
        out["mde"] = mde(se)
    return out


def daily_pooled_ic(rows, value_key, target_key, *, date_key="date", min_rows=20) -> dict:
    """旧口径日度 IC:按 ``date_key`` 把当天**全部行池化**后算 spearman,再对日取均值。

    日行数 ``< min_rows`` 或 IC 为 ``None`` 的日子跳过。保留旧脚本
    ``daily_ic`` 的语义,便于与 :func:`cross_sectional_ic` 并列对照;
    返回值不做四舍五入(旧脚本在展示层 ``round(...,4)``)。
    """
    groups: dict[Any, list[tuple[float, float]]] = {}
    for r in rows:
        v = r.get(value_key)
        t = r.get(target_key)
        if v is None or t is None:
            continue
        groups.setdefault(r.get(date_key), []).append((v, t))

    ics: list[float] = []
    for items in groups.values():
        if len(items) < min_rows:
            continue
        ic = spearman([it[0] for it in items], [it[1] for it in items])
        if ic is not None:
            ics.append(ic)
    if not ics:
        return {"days": 0, "mean_ic": None, "positive_days": 0}
    return {
        "days": len(ics),
        "mean_ic": statistics.fmean(ics),
        "positive_days": sum(1 for x in ics if x > 0),
    }


# --- 多重检验 -------------------------------------------------------------

def bh_adjust(pvals, q=0.10) -> dict:
    """Benjamini-Hochberg 校正。

    返回 ``{"m", "q", "reject"}``:``q`` 与输入同序、单调不减并 clamp ≤ 1,
    ``reject[i]`` 等价于 ``q[i] <= q``。
    """
    ps = list(pvals)
    m = len(ps)
    if m == 0:
        return {"m": 0, "q": [], "reject": []}
    order = sorted(range(m), key=lambda i: ps[i])
    adj = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        idx = order[rank - 1]
        value = ps[idx] * m / rank
        running = min(running, value)
        adj[idx] = min(running, 1.0)
    return {"m": m, "q": adj, "reject": [v <= q for v in adj]}


# --- 检验台账 -------------------------------------------------------------

def _check_finite(name: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, bool):
        return
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} 必须是数值或 None: {value!r}") from None
    if not math.isfinite(f):
        raise ValueError(f"{name} 不允许 NaN/Inf: {value!r}")


class TestLedger:
    """检验台账:每行一个 (family, label) 唯一检验,可写 jsonl 再合并回来。

    ``add`` 对重复 ``(family, label)`` 抛 ``ValueError``(防止同一检验被记两次);
    数值字段与 ``meta`` 在入账时即做有限性校验,避免写盘时
    ``json.dumps(..., allow_nan=False)`` 才炸。
    """

    # 名字以 Test 开头,避免被 pytest 当成测试类收集
    __test__ = False

    def __init__(self):
        self._rows: list[dict] = []
        self._keys: set[tuple[str, str]] = set()

    def add(self, family, label, *, stat, se=None, p=None, n=None, n_eff=None,
            mde=None, meta=None) -> None:
        key = (str(family), str(label))
        if key in self._keys:
            raise ValueError(f"重复的检验键: {key!r}")
        for name, value in (("stat", stat), ("se", se), ("p", p), ("n", n),
                            ("n_eff", n_eff), ("mde", mde)):
            _check_finite(name, value)
        row = {
            "family": key[0],
            "label": key[1],
            "stat": stat,
            "se": se,
            "p": p,
            "n": n,
            "n_eff": n_eff,
            "mde": mde,
            "meta": {} if meta is None else meta,
        }
        try:
            json.dumps(row, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"检验 {key!r} 不可 JSON 序列化(含 NaN/Inf 或非法类型): {exc}") from None
        self._rows.append(row)
        self._keys.add(key)

    def rows(self) -> list[dict]:
        return [dict(r, meta=dict(r["meta"]) if isinstance(r["meta"], dict) else r["meta"])
                for r in self._rows]

    def __len__(self) -> int:
        return len(self._rows)

    def write(self, path) -> None:
        p = Path(path)
        if p.parent and not p.parent.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8", newline="\n") as fh:
            for row in self._rows:
                fh.write(json.dumps(row, ensure_ascii=False, allow_nan=False))
                fh.write("\n")

    @staticmethod
    def merge(paths) -> "TestLedger":
        if isinstance(paths, (str, Path)):
            paths = [paths]
        ledger = TestLedger()
        for path in paths:
            with Path(path).open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    row = json.loads(line)
                    ledger.add(
                        row["family"],
                        row["label"],
                        stat=row.get("stat"),
                        se=row.get("se"),
                        p=row.get("p"),
                        n=row.get("n"),
                        n_eff=row.get("n_eff"),
                        mde=row.get("mde"),
                        meta=row.get("meta") or {},
                    )
        return ledger
