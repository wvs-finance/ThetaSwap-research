"""Pure functions: RawSwap sequence -> SwapObservation sequence.

All functions are pure — no IO, no mutation, no side effects.
"""
from __future__ import annotations

import math
from typing import Sequence

from data.hdrn_usdc.types import (
    RawSwap, SwapObservation, FeeGrowthX128, Liquidity, Q128,
)

GWEI: float = 1e9
UINT256_MAX: int = 2**256


def _fee_growth_delta(curr: FeeGrowthX128, prev: FeeGrowthX128) -> float:
    """Compute feeGrowthGlobal delta handling uint256 overflow."""
    return float((curr - prev) % UINT256_MAX) / Q128


def compute_pi_n(curr: RawSwap, prev: RawSwap) -> float:
    """Fee per unit active liquidity between two consecutive swaps.

    pi_n = delta(feeGrowthGlobal0X128) + delta(feeGrowthGlobal1X128)
    Both token0 and token1 fee growth contribute.
    """
    dfg0 = _fee_growth_delta(curr.fee_growth_global0_x128, prev.fee_growth_global0_x128)
    dfg1 = _fee_growth_delta(curr.fee_growth_global1_x128, prev.fee_growth_global1_x128)
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
    # price = (sqrtPriceX96)^2, so log(price) = 2*log(sqrtPriceX96)
    return 2.0 * (math.log(curr_sqrt) - math.log(prev_sqrt))


def to_observation(curr: RawSwap, prev: RawSwap) -> SwapObservation:
    """Transform a pair of consecutive raw swaps into one observation."""
    return SwapObservation(
        swap_id=curr.id,
        timestamp=curr.timestamp,
        block_number=curr.block_number,
        pi_n=compute_pi_n(curr, prev),
        l_active_n=float(curr.pool_liquidity),
        dlog_l_n=_dlog_l(curr.pool_liquidity, prev.pool_liquidity),
        volume_n=abs(curr.amount_usd),
        gas_n=curr.gas_price / GWEI,
        dp_n=_dp(curr.sqrt_price_x96, prev.sqrt_price_x96),
        tick_n=curr.tick,
        fee_growth0=curr.fee_growth_global0_x128,
        fee_growth1=curr.fee_growth_global1_x128,
    )


def to_observations(swaps: Sequence[RawSwap]) -> tuple[SwapObservation, ...]:
    """Transform sorted swap sequence into observation sequence.

    First swap is consumed as the baseline (no predecessor), yielding N-1 observations.
    """
    return tuple(
        to_observation(swaps[i], swaps[i - 1])
        for i in range(1, len(swaps))
    )
