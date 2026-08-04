"""Threshold calibration utilities.

Implements the "calibrate thresholds from actual distributions" methodology
(docs/2026-08-02-attack-channel-engineering-recommendations.md, section 4.2):
any ``score >= X`` style rule must be checked against the historical
distribution of scores before shipping, so that "configured but structurally
unreachable" rules (e.g. Q2 pending requiring 85 when the Q2 max is 79.35)
cannot recur.

Pure Python — the project has no pandas dependency.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence


class InsufficientSamplesError(ValueError):
    """Raised when too few historical samples exist for a reliable calibration."""


def percentile(sorted_values: Sequence[float], pct: float) -> float:
    """Linear-interpolated percentile (numpy ``quantile`` default semantics).

    ``pct`` is in [0, 100]. ``sorted_values`` must be sorted ascending.
    """
    if not 0.0 <= pct <= 100.0:
        raise ValueError(f"percentile must be in [0, 100], got {pct}")
    if not sorted_values:
        raise ValueError("cannot compute percentile of an empty sequence")
    position = (len(sorted_values) - 1) * (pct / 100.0)
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def calibrate_threshold_from_distribution(
    historical_scores: Iterable[float],
    target_pass_rate: float = 0.05,
    min_absolute_floor: float | None = None,
    min_samples: int = 100,
) -> float:
    """Derive a threshold from the historical score distribution.

    The returned threshold is the ``(1 - target_pass_rate)`` quantile, i.e.
    approximately ``target_pass_rate`` of historical samples score **at or
    above** it. A 10% pass rate therefore maps to P90.

    Parameters
    ----------
    historical_scores:
        Observed scores for the population the rule will filter (e.g. all Q2
        candidates for a Q2 pending rule). Empty / short samples raise
        ``InsufficientSamplesError`` — a threshold must not be set on gut feel
        or on a handful of points.
    target_pass_rate:
        Desired fraction of samples that clear the threshold (scarcity).
        Default 5% matches the original "reasonable scarcity" intent.
    min_absolute_floor:
        Optional hard lower bound; the result is ``max(quantile, floor)``.
        Used when domain knowledge says a calibrated value would otherwise be
        too lax (e.g. never below a Q1 direct threshold).
    min_samples:
        Minimum number of historical samples required for calibration.
    """
    if not (0.0 < target_pass_rate < 1.0):
        raise ValueError(f"target_pass_rate must be in (0, 1), got {target_pass_rate}")
    values = sorted(float(value) for value in historical_scores)
    if len(values) < min_samples:
        raise InsufficientSamplesError(
            f"insufficient samples for reliable calibration: {len(values)} < {min_samples}; accumulate data first"
        )
    calibrated = percentile(values, 100.0 * (1.0 - target_pass_rate))
    if min_absolute_floor is not None:
        calibrated = max(calibrated, float(min_absolute_floor))
    return calibrated
