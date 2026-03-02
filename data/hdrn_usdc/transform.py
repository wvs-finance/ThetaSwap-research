"""Pure functions: RawSwap + HourlySnapshot -> SwapObservation sequence.

Swap-level data (price, volume, gas) comes from RawSwap.
Liquidity and feeGrowthGlobal come from the nearest PoolHourData snapshot
(floor of the swap's hour), since the subgraph's swap.pool{} returns
the current state, not the historical state at swap time.

All functions are pure — no IO, no mutation, no side effects.
"""
from __future__ import annotations

import bisect
import math
from typing import Sequence

from data.hdrn_usdc.fetch_hourly import HourlySnapshot
from data.hdrn_usdc.types import (
    RawSwap, SwapObservation, FeeGrowthX128, Liquidity, Timestamp, Q128,
)

GWEI: float = 1e9
UINT256_MAX: int = 2**256
SECONDS_PER_HOUR: int = 3600


def _fee_growth_delta(curr: FeeGrowthX128, prev: FeeGrowthX128) -> float:
    """Compute feeGrowthGlobal delta handling uint256 overflow."""
    return float((curr - prev) % UINT256_MAX) / Q128


def compute_pi_n(
    curr_fg0: FeeGrowthX128, curr_fg1: FeeGrowthX128,
    prev_fg0: FeeGrowthX128, prev_fg1: FeeGrowthX128,
) -> float:
    """Fee per unit active liquidity between two consecutive snapshots.

    pi_n = delta(feeGrowthGlobal0X128) + delta(feeGrowthGlobal1X128)
    Both token0 and token1 fee growth contribute.
    """
    dfg0 = _fee_growth_delta(curr_fg0, prev_fg0)
    dfg1 = _fee_growth_delta(curr_fg1, prev_fg1)
    return dfg0 + dfg1


def _dlog_l(curr_liq: Liquidity, prev_liq: Liquidity) -> float:
    """Log liquidity growth: log(L_n) - log(L_{n-1})."""
    if curr_liq <= 0 or prev_liq <= 0:
        return 0.0
    return math.log(curr_liq) - math.log(prev_liq)


def _dp(curr_sqrt: int, prev_sqrt: int) -> float:
    """Log price change from sqrtPriceX96."""
    if curr_sqrt <= 0 or prev_sqrt <= 0:
        return 0.0
    return 2.0 * (math.log(curr_sqrt) - math.log(prev_sqrt))


def _hour_floor(ts: Timestamp) -> Timestamp:
    """Round timestamp down to hour boundary."""
    return (ts // SECONDS_PER_HOUR) * SECONDS_PER_HOUR


def build_hourly_index(
    snapshots: Sequence[HourlySnapshot],
) -> tuple[list[Timestamp], dict[Timestamp, HourlySnapshot]]:
    """Build sorted timestamp list + lookup dict for bisect join.

    Returns (sorted_timestamps, timestamp_to_snapshot) for O(log n) lookup.
    """
    by_ts: dict[Timestamp, HourlySnapshot] = {}
    for s in snapshots:
        by_ts[s.period_start] = s
    sorted_ts = sorted(by_ts.keys())
    return sorted_ts, by_ts


def lookup_hourly(
    swap_ts: Timestamp,
    sorted_ts: list[Timestamp],
    by_ts: dict[Timestamp, HourlySnapshot],
) -> HourlySnapshot | None:
    """Find the hourly snapshot for a swap's timestamp (floor join).

    Uses bisect to find the largest period_start <= swap_ts.
    """
    idx = bisect.bisect_right(sorted_ts, swap_ts) - 1
    if idx < 0:
        return None
    return by_ts[sorted_ts[idx]]


def to_observations_with_hourly(
    swaps: Sequence[RawSwap],
    snapshots: Sequence[HourlySnapshot],
) -> tuple[SwapObservation, ...]:
    """Join swap-level data with hourly snapshots to produce observations.

    For each consecutive swap pair (prev, curr):
    - price change, volume, gas come from swap data
    - liquidity, feeGrowthGlobal come from the hourly snapshot at each swap's hour

    Swaps without a matching hourly snapshot are dropped.
    First swap consumed as baseline (N-1 observations).
    """
    sorted_ts, by_ts = build_hourly_index(snapshots)

    # CRITICAL: sort swaps by timestamp, not by ID (lexicographic hex).
    # Subgraph keyset pagination returns id_gt ordering, which is NOT time order.
    # Without this sort, consecutive swap deltas are between random time points,
    # causing overflow artifacts in feeGrowthGlobal differences.
    swaps_sorted = sorted(swaps, key=lambda s: s.timestamp)

    # Pre-compute hourly lookups for all swaps
    swap_hours: list[tuple[RawSwap, HourlySnapshot]] = []
    for s in swaps_sorted:
        h = lookup_hourly(s.timestamp, sorted_ts, by_ts)
        if h is not None:
            swap_hours.append((s, h))

    observations: list[SwapObservation] = []
    for i in range(1, len(swap_hours)):
        curr_swap, curr_hour = swap_hours[i]
        prev_swap, prev_hour = swap_hours[i - 1]

        pi_n = compute_pi_n(
            curr_hour.fee_growth_global0_x128, curr_hour.fee_growth_global1_x128,
            prev_hour.fee_growth_global0_x128, prev_hour.fee_growth_global1_x128,
        )

        observations.append(SwapObservation(
            swap_id=curr_swap.id,
            timestamp=curr_swap.timestamp,
            block_number=curr_swap.block_number,
            pi_n=pi_n,
            l_active_n=float(curr_hour.liquidity),
            dlog_l_n=_dlog_l(curr_hour.liquidity, prev_hour.liquidity),
            volume_n=abs(curr_swap.amount_usd),
            gas_n=curr_swap.gas_price / GWEI,
            dp_n=_dp(curr_swap.sqrt_price_x96, prev_swap.sqrt_price_x96),
            tick_n=curr_swap.tick,
            fee_growth0=curr_hour.fee_growth_global0_x128,
            fee_growth1=curr_hour.fee_growth_global1_x128,
        ))

    return tuple(observations)


# Keep backward-compatible interface for unit tests with mock data
def to_observations(swaps: Sequence[RawSwap]) -> tuple[SwapObservation, ...]:
    """Transform sorted swap sequence into observation sequence (legacy).

    Uses swap-embedded pool_liquidity and feeGrowth fields directly.
    Only valid when those fields contain historical (not current) values.
    """
    observations: list[SwapObservation] = []
    for i in range(1, len(swaps)):
        curr, prev = swaps[i], swaps[i - 1]
        pi_n = compute_pi_n(
            curr.fee_growth_global0_x128, curr.fee_growth_global1_x128,
            prev.fee_growth_global0_x128, prev.fee_growth_global1_x128,
        )
        observations.append(SwapObservation(
            swap_id=curr.id,
            timestamp=curr.timestamp,
            block_number=curr.block_number,
            pi_n=pi_n,
            l_active_n=float(curr.pool_liquidity),
            dlog_l_n=_dlog_l(curr.pool_liquidity, prev.pool_liquidity),
            volume_n=abs(curr.amount_usd),
            gas_n=curr.gas_price / GWEI,
            dp_n=_dp(curr.sqrt_price_x96, prev.sqrt_price_x96),
            tick_n=curr.tick,
            fee_growth0=curr.fee_growth_global0_x128,
            fee_growth1=curr.fee_growth_global1_x128,
        ))
    return tuple(observations)
