"""fwdlib 标注器测试用的合成行情构造器。

所有构造器都是**纯函数 + 固定参数**,不读磁盘、不依赖网络,保证测试离线可跑。
决策行的字段与 ``features.load_decisions`` 对齐:``symbol / ts / side / open /
high / low / close / stop_pct / atr_pct``。
"""

from __future__ import annotations

import random

BAR_SECONDS = 900
#: 一个真实存在的 15m 对齐时间戳(2025-10-09 08:53:20 UTC 附近),避免用 0 触发
#: 日期格式化 / 时区边界问题。
BASE_TS = 1_760_000_000 - (1_760_000_000 % BAR_SECONDS)


def make_bar(symbol, ts, ohlc, *, side="LONG", stop_pct=0.01, atr_pct=0.004, **extra):
    """单根决策行(决策行内嵌该 bar 的 OHLC)。"""
    o, h, l, c = ohlc
    row = {
        "symbol": symbol,
        "ts": ts,
        "side": side,
        "stop_pct": stop_pct,
        "atr_pct": atr_pct,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
    }
    row.update(extra)
    return row


def make_series(symbol, ohlc_list, *, side="LONG", stop_pct=0.01, atr_pct=0.004, **extra):
    """把一串 ``(open, high, low, close)`` 变成同 symbol 的连续决策行。"""
    return [
        make_bar(symbol, BASE_TS + i * BAR_SECONDS, ohlc,
                 side=side, stop_pct=stop_pct, atr_pct=atr_pct, **extra)
        for i, ohlc in enumerate(ohlc_list)
    ]


def flat_ohlc(n, price=100.0):
    """完全无波动的横盘:三重障碍都不会触发,必然 TIMEOUT。"""
    return [(price, price, price, price)] * n


def geometric_ohlc(n, p0=100.0, step=0.01):
    """每根固定涨幅 ``step`` 的几何上涨;收盘=最高、开盘=最低。"""
    out = []
    px = p0
    for _ in range(n):
        o = px
        c = px * (1.0 + step)
        out.append((o, c, o, c))
        px = c
    return out


def mirror_ohlc(block=6):
    """四种行情块,用于多空镜像:横盘 / 单向上行 / 双向大幅 / 单向下行。

    * 横盘  → 超时,R = 0;
    * 上行  → LONG 目标 / SHORT 止损;
    * 大幅  → 同根同时触及上下障碍,LONG 与 SHORT 都 AMBIGUOUS;
    * 下行  → LONG 止损 / SHORT 目标。

    所有 bar 的开盘价都是 100,因此 ``next_open`` 入场价与所处块无关。
    """
    blocks = [
        [(100.0, 100.0, 100.0, 100.0)] * block,
        [(100.0, 101.5, 100.0, 101.5)] * block,
        [(100.0, 102.0, 98.0, 100.0)] * block,
        [(100.0, 100.0, 98.5, 98.5)] * block,
    ]
    return [row for blk in blocks for row in blk]


def random_walk_paths(seed, n_paths=2000, n_bars=34, sigma=0.002, price0=100.0):
    """零漂移随机游走。返回 ``[(symbol, [(o,h,l,c), ...]), ...]``。

    ``n_bars=34`` 时,对第 0 根决策行 ``next_open`` 入场:entry=bar1 开盘、
    start=bar2,32 根 horizon 恰好用满,不会因为末尾截断而破坏对称性。
    """
    rnd = random.Random(seed)
    paths = []
    for k in range(n_paths):
        symbol = f"RW{k:04d}"
        px = price0
        bars = []
        for _ in range(n_bars):
            ret = rnd.gauss(0.0, sigma)
            o = px
            c = px * (1.0 + ret)
            bars.append((o, max(o, c), min(o, c), c))
            px = c
        paths.append((symbol, bars))
    return paths
