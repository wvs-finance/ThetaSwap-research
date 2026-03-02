"""Fetch swap events from Uniswap V3 subgraph with keyset pagination.

Reuses UniswapClient (IO boundary) from data/UniswapClient.py.
Pagination pattern from data/build_position_registry.py.
"""
from __future__ import annotations

import time
from typing import Final, Sequence

from data.UniswapClient import UniswapClient
from data.hdrn_usdc.types import (
    RawSwap, PoolId, SwapId,
)

PAGE_SIZE: Final = 1000
RATE_LIMIT_SEC: Final = 0.3

SWAP_QUERY: Final = """
{{
  swaps(
    first: {page_size},
    where: {{
      pool: "{pool_id}",
      id_gt: "{last_id}"
    }},
    orderBy: id,
    orderDirection: asc
  ) {{
    id
    timestamp
    tick
    sqrtPriceX96
    amount0
    amount1
    amountUSD
    transaction {{ blockNumber gasPrice }}
    pool {{ liquidity feeGrowthGlobal0X128 feeGrowthGlobal1X128 }}
  }}
}}
"""


def _parse_swap(raw: dict) -> RawSwap:
    """Parse subgraph swap response dict into frozen RawSwap."""
    return RawSwap(
        id=raw["id"],
        timestamp=int(raw["timestamp"]),
        block_number=int(raw["transaction"]["blockNumber"]),
        tick=int(raw["tick"]),
        sqrt_price_x96=int(raw["sqrtPriceX96"]),
        amount0=float(raw["amount0"]),
        amount1=float(raw["amount1"]),
        amount_usd=float(raw["amountUSD"]),
        gas_price=int(raw["transaction"]["gasPrice"]),
        pool_liquidity=int(raw["pool"]["liquidity"]),
        fee_growth_global0_x128=int(raw["pool"]["feeGrowthGlobal0X128"]),
        fee_growth_global1_x128=int(raw["pool"]["feeGrowthGlobal1X128"]),
    )


def fetch_swap_page(
    client: UniswapClient,
    pool_id: PoolId,
    last_id: SwapId = "",
    page_size: int = PAGE_SIZE,
) -> Sequence[RawSwap]:
    """Fetch one page of swaps using keyset pagination."""
    query = SWAP_QUERY.format(
        page_size=page_size, pool_id=pool_id, last_id=last_id
    )
    data = client.query(query)
    return tuple(_parse_swap(s) for s in data.get("swaps", []))


def fetch_all_swaps(
    client: UniswapClient,
    pool_id: PoolId,
    start_id: SwapId = "",
    max_pages: int | None = None,
) -> Sequence[RawSwap]:
    """Paginate through all swaps for a pool.

    Args:
        client: UniswapClient IO boundary
        pool_id: target pool address
        start_id: resume from this swap id (keyset cursor)
        max_pages: cap total pages (None = fetch all)
    """
    all_swaps: list[RawSwap] = []
    last_id = start_id
    page = 0

    while True:
        batch = fetch_swap_page(client, pool_id, last_id)
        if not batch:
            break

        all_swaps.extend(batch)
        last_id = batch[-1].id
        page += 1

        if page % 10 == 0:
            print(f"  Page {page}: {len(all_swaps)} swaps (last_id: {last_id})")

        if max_pages and page >= max_pages:
            break

        time.sleep(RATE_LIMIT_SEC)

    return tuple(all_swaps)
