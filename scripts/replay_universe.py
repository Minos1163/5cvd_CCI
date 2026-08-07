# -*- coding: utf-8 -*-
"""replay_universe.py — 对 data/raw/binance_futures/latest_30d 下全部 symbol
依次跑 replay_symbol_chain.py(新配置),汇总 DIRECT/PROBE 候选数,输出全宇宙对比。
用于验证优化(rank 扩围 + LONG offset 校准 + ATOM 入 targeted)后全宇宙不劣化。

用法: python scripts/replay_universe.py [--out logs/analysis/universe_replay_opt.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data" / "raw" / "binance_futures" / "latest_30d"
SCRIPT = PROJECT_ROOT / "scripts" / "replay_symbol_chain.py"
DEFAULT_OUT = PROJECT_ROOT / "logs" / "analysis" / "universe_replay_opt.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--start", default="2026-08-02")
    parser.add_argument("--end", default="2026-08-05")
    args = parser.parse_args()

    symbols = sorted(
        p.name for p in DATA_ROOT.iterdir()
        if p.is_dir() and (p / "15m.csv").exists() and not p.name.startswith(".")
    )
    results: list[dict] = []
    for sym in symbols:
        proc = subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--symbol", sym, "--start", args.start, "--end", args.end,
            ],
            capture_output=True, text=True, timeout=240,
        )
        if proc.returncode != 0:
            results.append({"symbol": sym, "error": proc.stderr.strip()[-200:]})
            continue
        try:
            results.append(json.loads(proc.stdout.strip()))
        except json.JSONDecodeError:
            results.append({"symbol": sym, "error": "parse failed"})

    out = {
        "config": "configs/entry_chain.dry_run_fib_pa_v1.json (优化后: rank_end=90, long_threshold_offset=0, ATOM 入 targeted)",
        "window": f"{args.start}~{args.end}",
        "symbols": len(results),
        "per_symbol": results,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
