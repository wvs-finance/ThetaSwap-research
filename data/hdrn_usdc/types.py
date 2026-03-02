"""Frozen value types for HDRN/USDC swap-level data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Sequence, TypeAlias

# Domain type aliases
SwapId: TypeAlias = str
PoolId: TypeAlias = str
Tick: TypeAlias = int
SqrtPriceX96: TypeAlias = int
FeeGrowthX128: TypeAlias = int
Liquidity: TypeAlias = int
WeiPerGas: TypeAlias = int
BlockNumber: TypeAlias = int
Timestamp: TypeAlias = int

Q128: Final = 2**128

HDRN_USDC_POOL: Final[PoolId] = "0xe859041c9c6d70177f83de991b9d757e13cea26e"
HDRN_FEE_BPS: Final = 10_000


@dataclass(frozen=True)
class RawSwap:
    """Single swap event with nested pool state, direct from subgraph."""
    id: SwapId
    timestamp: Timestamp
    block_number: BlockNumber
    tick: Tick
    sqrt_price_x96: SqrtPriceX96
    amount0: float
    amount1: float
    amount_usd: float
    gas_price: WeiPerGas
    pool_liquidity: Liquidity
    fee_growth_global0_x128: FeeGrowthX128
    fee_growth_global1_x128: FeeGrowthX128


@dataclass(frozen=True)
class SwapObservation:
    """Computed swap-level observation for the regression."""
    swap_id: SwapId
    timestamp: Timestamp
    block_number: BlockNumber
    pi_n: float          # fee per unit active liquidity
    l_active_n: float    # active liquidity at this swap
    dlog_l_n: float      # log liquidity growth since prev swap
    volume_n: float      # swap size in USD
    gas_n: float         # gas price in Gwei
    dp_n: float          # log price change since prev swap
    tick_n: Tick
    fee_growth0: FeeGrowthX128  # raw for delta computation
    fee_growth1: FeeGrowthX128
