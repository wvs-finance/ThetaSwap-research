"""Sampling strategy: identify active periods and filter sparse tails.

The full HDRN/USDC swap history is ~90 pages (cheap to fetch).
This module determines WHICH observations to include in the regression.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, Sequence

from data.hdrn_usdc.types import RawSwap, Timestamp

SECONDS_PER_DAY: Final = 86_400
SECONDS_PER_QUARTER: Final = 90 * SECONDS_PER_DAY


@dataclass(frozen=True)
class ActivePeriod:
    """Configuration for active period detection.

    min_swaps_per_quarter: minimum swap count to consider a quarter active.
    Default 50 — quarters below this threshold are dropped as sparse noise.
    """
    min_swaps_per_quarter: int = 50


def _quarter_start(ts: Timestamp) -> Timestamp:
    """Round timestamp down to quarter boundary (approx 90 days)."""
    epoch = 1640995200  # 2022-01-01 00:00:00 UTC
    offset = ts - epoch
    quarter_idx = offset // SECONDS_PER_QUARTER
    return epoch + quarter_idx * SECONDS_PER_QUARTER


def _group_by_quarter(swaps: Sequence[RawSwap]) -> dict[Timestamp, list[RawSwap]]:
    """Group swaps by approximate quarter."""
    groups: dict[Timestamp, list[RawSwap]] = {}
    for s in swaps:
        q = _quarter_start(s.timestamp)
        groups.setdefault(q, []).append(s)
    return groups


def filter_active_period(
    swaps: Sequence[RawSwap],
    config: ActivePeriod = ActivePeriod(),
) -> tuple[RawSwap, ...]:
    """Keep only swaps from quarters with sufficient density.

    Drops the sparse tail (2024-H2 onward) where 79 swaps/half-year
    would add noise to the regression without statistical power.
    """
    quarters = _group_by_quarter(swaps)
    active_swaps: list[RawSwap] = []
    for q_start in sorted(quarters):
        q_swaps = quarters[q_start]
        if len(q_swaps) >= config.min_swaps_per_quarter:
            active_swaps.extend(q_swaps)
    return tuple(active_swaps)


def compute_swap_density(
    swaps: Sequence[RawSwap],
    window_days: int = 30,
) -> tuple[tuple[Timestamp, float], ...]:
    """Compute swap count per quarter-day for diagnostics.

    Returns (quarter_start, swaps_per_day) pairs for reporting.
    """
    if not swaps:
        return ()
    quarters = _group_by_quarter(swaps)
    return tuple(
        (q_start, len(q_swaps) / 90.0)
        for q_start, q_swaps in sorted(quarters.items())
    )


def describe_sample(swaps: Sequence[RawSwap]) -> str:
    """Human-readable summary of sample composition."""
    quarters = _group_by_quarter(swaps)
    lines = ["Quarter   | Swaps | Swaps/day"]
    lines.append("----------|-------|----------")
    for q_start in sorted(quarters):
        dt = datetime.fromtimestamp(q_start, tz=timezone.utc)
        n = len(quarters[q_start])
        lines.append(f"{dt.strftime('%Y-%m')}   | {n:>5} | {n/90:.1f}")
    lines.append(f"Total: {len(swaps)} swaps")
    return "\n".join(lines)
