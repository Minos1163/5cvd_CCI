from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.signals.entry_chain_config import load_entry_chain_config


def main() -> None:
    args = parse_args()
    config = load_entry_chain_config(args.config)
    dry_run_source = Path("scripts/run_live_dry_run.py").read_text(encoding="utf-8")
    forbidden = [token for token in ("submit_order(", "cancel_order(") if token in dry_run_source]
    binance_client_exists = Path("src/api/binance_client.py").exists()
    output_dir_ok = True
    if args.output_dir:
        path = Path(args.output_dir)
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".healthcheck"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    payload = {
        "status": "ok" if not forbidden and output_dir_ok else "failed",
        "dry_run_safe": not forbidden,
        "binance_client_exists": binance_client_exists,
        "forbidden_tokens": forbidden,
        "config": {
            "direct_threshold": config.direct_threshold,
            "probe_threshold": config.probe_threshold,
            "daily_max_trades_base": config.daily_max_trades_base,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if payload["status"] != "ok":
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AI300 VPS dry-run deployment prerequisites.")
    parser.add_argument("--config", default="configs/entry_chain.dry_run.json")
    parser.add_argument("--output-dir")
    return parser.parse_args()


if __name__ == "__main__":
    main()
