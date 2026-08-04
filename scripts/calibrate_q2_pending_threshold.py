"""Calibrate the Q2 pending record threshold from the actual score distribution.

Phase 0 action from docs/2026-08-02-attack-channel-engineering-recommendations.md:
the Q2 pending rule previously required score >= 85 while the observed Q2 max was
79.35 — a structurally unreachable threshold. This script extracts Q2 scores from
``logs/**/decisions.jsonl`` within a window and derives the threshold from the
real distribution (P90 by default, i.e. ~10% pass rate).

Usage::

    python scripts/calibrate_q2_pending_threshold.py --window-days 7 --pass-rate 0.10

Exit code 2 when there are insufficient samples — calibration must not happen on
thin data.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.signals.entry_chain_config import load_entry_chain_config
from src.utils.threshold_calibration import (
    InsufficientSamplesError,
    calibrate_threshold_from_distribution,
    percentile,
)


def iter_decision_rows(log_root: Path, window_days: int) -> Iterable[tuple[Path, dict[str, Any]]]:
    """Yield (source_file, row) for decisions.jsonl within the trailing window."""
    start_ts = int((datetime.now(UTC) - timedelta(days=window_days)).timestamp())
    for path in sorted(log_root.rglob("decisions.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            if int(payload.get("timestamp") or 0) < start_ts:
                continue
            yield path, payload


def extract_q2_scores(
    log_root: Path,
    window_days: int,
    config,
) -> list[float]:
    """Scores of rows whose quadrant (per production axis logic) is Q2."""
    from scripts.run_live_dry_run import decision_quadrant

    scores: list[float] = []
    for _source, row in iter_decision_rows(log_root, window_days):
        try:
            if decision_quadrant(row, config) == "Q2":
                scores.append(float(row.get("score") or 0.0))
        except (TypeError, ValueError):
            continue
    return scores


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-root", type=Path, default=ROOT / "logs", help="log tree root (default: logs/)")
    parser.add_argument("--window-days", type=int, default=7, help="trailing window in days (default: 7)")
    parser.add_argument("--pass-rate", type=float, default=0.10, help="target pass rate, fraction of samples above threshold (default: 0.10)")
    parser.add_argument("--min-samples", type=int, default=100, help="minimum samples required (default: 100)")
    parser.add_argument("--floor", type=float, default=None, help="optional hard absolute floor for the threshold")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "entry_chain.dry_run_fib_pa_v1.json", help="entry-chain config (quadrant thresholds)")
    args = parser.parse_args(argv)

    config = load_entry_chain_config(args.config)
    scores = extract_q2_scores(args.log_root, args.window_days, config)
    if not scores:
        print(f"no Q2 samples found under {args.log_root} in the last {args.window_days} days", file=sys.stderr)
        return 2

    try:
        threshold = calibrate_threshold_from_distribution(
            scores,
            target_pass_rate=args.pass_rate,
            min_absolute_floor=args.floor,
            min_samples=args.min_samples,
        )
    except InsufficientSamplesError as exc:
        print(f"calibration aborted: {exc}", file=sys.stderr)
        return 2

    ordered = sorted(scores)
    print(f"Q2 samples in window: {len(scores)}")
    print(f"score min/mean/max: {ordered[0]:.2f} / {fmean(ordered):.2f} / {ordered[-1]:.2f}")
    print(f"P80/P90/P95: {percentile(ordered, 80):.2f} / {percentile(ordered, 90):.2f} / {percentile(ordered, 95):.2f}")
    print(f"calibrated threshold (pass rate {args.pass_rate:.0%}): {threshold:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
