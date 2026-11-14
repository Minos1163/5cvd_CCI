"""Universe 选取：按市值排名 + 数量收敛。

2026-11-14 需求："增加交易对到 25 个，取市值前 25 名（除开稳定币）"。

这里的核心事实是：**rank 区间是范围，不是数量**。当天实测 rank 3-25 共 23 个排名，
扣掉稳定币和"Binance 没有 USDT 永续"的，只命中 14 个；第 25 个可交易标的落在 rank 49。
所以"要 25 个"必须（a）放宽 rank_end 到 50 以上，（b）按数量截断。

本文件锁住四件事：
1. `select_universe_assets` 的过滤顺序（rank 区间 → 稳定币 → 有永续）
2. `target_size` 的"凑满即停"语义，且 `rank_end` 仍作为硬上限
3. 新增的稳定币符号真的被过滤（尤其 RLUSD/USDG 这类容易漏的）
4. 生产配置的三个数值满足"能稳定取到 25 个"的必要条件
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_live_dry_run import (
    STABLE_IDS,
    STABLE_SYMBOLS,
    select_universe_assets,
)

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "entry_chain.dry_run_regime_shadow.json"


def _mk(rank: int, symbol: str, coin_id: str, name: str = "") -> dict:
    return {"market_cap_rank": rank, "symbol": symbol, "id": coin_id, "name": name or symbol}


#: 模拟 2026-11-14 的真实分布：含稳定币、含无永续的大市值资产。
MARKETS = [
    _mk(1, "btc", "bitcoin"),
    _mk(2, "eth", "ethereum"),
    _mk(3, "usdt", "tether"),              # 稳定币
    _mk(4, "bnb", "binancecoin"),
    _mk(6, "xrp", "ripple"),
    _mk(7, "sol", "solana"),
    _mk(8, "trx", "tron"),
    _mk(9, "figr_heloc", "figure-heloc"),  # 大市值但 Binance 无永续
    _mk(10, "hype", "hyperliquid"),
    _mk(11, "zec", "zcash"),
    _mk(12, "xmr", "monero"),
    _mk(13, "doge", "dogecoin"),
    _mk(14, "leo", "leo-token"),           # 无永续
    _mk(17, "link", "chainlink"),
    _mk(18, "ada", "cardano"),
    _mk(19, "xlm", "stellar"),
    _mk(22, "bch", "bitcoin-cash"),
    _mk(23, "near", "near"),
    _mk(24, "ltc", "litecoin"),
    _mk(25, "avax", "avalanche-2"),
    _mk(26, "cc", "canton-network"),
    _mk(27, "uni", "uniswap"),
    _mk(28, "xaut", "tether-gold"),
    _mk(30, "sui", "sui"),
    _mk(32, "rlusd", "ripple-usd"),         # 稳定币（2026-11-14 新补）
    _mk(33, "usdg", "global-dollar"),       # 稳定币（新补）
    _mk(36, "hbar", "hedera-hashgraph"),
    _mk(39, "tao", "bittensor"),
    _mk(41, "qnt", "quant-network"),
    _mk(44, "m", "meme-core"),
    _mk(47, "paxg", "pax-gold"),
    _mk(49, "ena", "ethena"),
    _mk(55, "jup", "jupiter-exchange-solana"),
]

TRADABLE = {
    "BNB": "BNBUSDT", "XRP": "XRPUSDT", "SOL": "SOLUSDT", "TRX": "TRXUSDT",
    "HYPE": "HYPEUSDT", "ZEC": "ZECUSDT", "XMR": "XMRUSDT", "DOGE": "DOGEUSDT",
    "LINK": "LINKUSDT", "ADA": "ADAUSDT", "XLM": "XLMUSDT", "BCH": "BCHUSDT",
    "NEAR": "NEARUSDT", "LTC": "LTCUSDT", "AVAX": "AVAXUSDT", "CC": "CCUSDT",
    "UNI": "UNIUSDT", "XAUT": "XAUTUSDT", "SUI": "SUIUSDT", "HBAR": "HBARUSDT",
    "TAO": "TAOUSDT", "QNT": "QNTUSDT", "M": "MUSDT", "PAXG": "PAXGUSDT",
    "ENA": "ENAUSDT", "JUP": "JUPUSDT",
    "BTC": "BTCUSDT", "ETH": "ETHUSDT",
    "RLUSD": "RLUSDUSDT", "USDG": "USDGUSDT",   # 故意给稳定币也配上永续，验证过滤优先
}


def test_default_target_size_zero_keeps_range_behaviour() -> None:
    """target_size=0 时只按 rank 区间过滤，能做几个是几个（历史行为）。

    本 fixture 是裁剪过的（只保留关键 rank），所以数量是 15；
    2026-11-14 真实数据同样区间是 14 个——差异来自真实排名里还有别的不可交易项。
    这里要锁的是**语义**（不做数量截断），不是那个具体数字。
    """
    symbols, assets = select_universe_assets(MARKETS, TRADABLE, 3, 25, 0)
    assert len(symbols) == 15
    assert len(symbols) < 25, "target_size=0 不凑数"
    assert symbols[0] == "BNBUSDT"
    assert "BTCUSDT" not in symbols, "rank_start=3 应排除 BTC"
    assert all(a["market_cap_rank"] <= 25 for a in assets)


def test_target_size_stops_at_requested_count() -> None:
    """target_size=25 时凑满即停，会突破原来的 rank_end。"""
    symbols, assets = select_universe_assets(MARKETS, TRADABLE, 3, 60, 25)
    assert len(symbols) == 25
    assert symbols[-1] == "ENAUSDT", "第 25 个可交易标的应是 rank 49 的 ENA"
    assert max(a["market_cap_rank"] for a in assets) == 49
    assert "JUPUSDT" not in symbols, "凑满后不应继续往下取"


def test_rank_end_still_caps_even_if_target_unmet() -> None:
    """rank_end 是硬上限：区间内不够 25 个时，不会越界去取。"""
    symbols, _ = select_universe_assets(MARKETS, TRADABLE, 3, 30, 25)
    # rank<=30 可交易：BNB XRP SOL TRX HYPE ZEC XMR DOGE LINK ADA XLM BCH NEAR LTC AVAX CC UNI XAUT SUI = 19
    assert len(symbols) == 19
    assert all(s != "HBARUSDT" for s in symbols)


def test_stables_are_filtered_even_when_tradable_exists() -> None:
    """稳定币必须按 symbol 过滤，哪怕交易所有它的永续。"""
    symbols, _ = select_universe_assets(MARKETS, TRADABLE, 1, 100, 0)
    assert "RLUSDUSDT" not in symbols
    assert "USDGUSDT" not in symbols
    for sym in ("RLUSD", "USDG", "USDT"):
        assert sym in STABLE_SYMBOLS


def test_stable_ids_cover_new_entries() -> None:
    for coin_id in ("ripple-usd", "global-dollar", "ondo-us-dollar-yield", "falcon-finance", "bfusd"):
        assert coin_id in STABLE_IDS


def test_unknown_base_without_perp_is_skipped() -> None:
    """CoinGecko 有、Binance 没永续 → 跳过，不报错。"""
    markets = [_mk(4, "bnb", "binancecoin"), _mk(9, "figr_heloc", "figure-heloc")]
    symbols, assets = select_universe_assets(markets, TRADABLE, 3, 25, 0)
    assert symbols == ["BNBUSDT"]
    assert len(assets) == 1


def test_duplicate_free_and_ordered_by_rank() -> None:
    symbols, assets = select_universe_assets(MARKETS, TRADABLE, 3, 60, 25)
    assert len(set(symbols)) == len(symbols)
    ranks = [a["market_cap_rank"] for a in assets]
    assert ranks == sorted(ranks), "必须按市值从高到低"


# ---------------------------------------------------------------------------
# 生产配置的必要条件
# ---------------------------------------------------------------------------

def _load_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def test_production_config_requests_25_symbols() -> None:
    cfg = _load_config()
    assert cfg["dry_run_symbol_source"] == "market_cap_rank"
    assert cfg["dry_run_universe_size"] == 25
    assert cfg["dry_run_rank_start"] == 3, "需求明确排除 BTC/ETH（rank 1-2）"


def test_production_rank_end_is_deep_enough() -> None:
    """rank_end 必须 >= 50：2026-11-14 实测第 25 个可交易标的落在 rank 49。"""
    cfg = _load_config()
    assert cfg["dry_run_rank_end"] >= 50, (
        f"rank_end={cfg['dry_run_rank_end']} 会在排名漂移时凑不满 25 个"
    )


def test_production_fallback_symbols_match_target_size() -> None:
    """fallback 列表要与目标数量一致，否则 CoinGecko 挂掉时标的池会突然缩水。"""
    cfg = _load_config()
    syms = cfg["dry_run_symbols"]
    assert len(syms) == cfg["dry_run_universe_size"]
    assert len(set(syms)) == len(syms)
    assert all(s.endswith("USDT") for s in syms)


def test_production_daily_budget_scaled_with_universe() -> None:
    """标的 14→25，日预算必须同步放宽，否则单标的配额被摊薄。"""
    cfg = _load_config()
    assert cfg["daily_max_trades_base"] >= 24
    assert cfg["daily_max_trades_base"] <= 28


def test_production_config_loads_and_keeps_universe_size() -> None:
    from src.signals.entry_chain_config import load_entry_chain_config

    cfg = load_entry_chain_config(CONFIG)
    assert cfg.dry_run_universe_size == 25
    assert cfg.dry_run_rank_end >= 50
