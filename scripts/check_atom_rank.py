# -*- coding: utf-8 -*-
"""check_atom_rank.py — 查询 ATOM 当前市值排名(CoinGecko markets API,前 100)。
决定 rank 扩围方案:若 ATOM 排名 >25,需将 rank_end 扩大以覆盖。
"""
from __future__ import annotations

import json
import sys

import requests


def main() -> int:
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 100, "page": 1}
    headers = {"User-Agent": "Mozilla/5.0 (AI300 rank check)"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=25)
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    assets = resp.json()
    atom = next((a for a in assets if str(a.get("symbol", "")).upper() == "ATOM"), None)
    if atom is None:
        print(json.dumps({"found": False, "checked": len(assets), "note": "ATOM 不在前 100(排名 >100)"}, ensure_ascii=False))
        return 1
    out = {
        "found": True,
        "rank": atom.get("market_cap_rank"),
        "name": atom.get("name"),
        "price_usd": atom.get("current_price"),
        "market_cap": atom.get("market_cap"),
        "current_rank_range": "3-25",
        "in_scope": bool(atom.get("market_cap_rank") and 3 <= atom["market_cap_rank"] <= 25),
        "suggested_rank_end": max(40, (atom.get("market_cap_rank") or 0) + 10),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
