"""Fetch PoolHourData from Uniswap V3 subgraph with keyset pagination.

PoolHourData provides historical hourly snapshots of:
- liquidity (active liquidity at hour boundary)
- feeGrowthGlobal0X128, feeGrowthGlobal1X128 (cumulative fee accumulators)
- volumeUSD, txCount (hourly aggregates)

These are NOT available per-swap — the swap entity's nested pool{}
returns the current snapshot, not the historical state.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Final, Sequence

from data.UniswapClient import UniswapClient
from data.hdrn_usdc.types import (
    PoolId, Timestamp, Liquidity, FeeGrowthX128,
)

PAGE_SIZE: Final = 1000
RATE_LIMIT_SEC: Final = 0.3

HOURLY_QUERY: Final = """
{{
  poolHourDatas(
    first: {page_size},
    where: {{
      pool: "{pool_id}",
      id_gt: "{last_id}"
    }},
    orderBy: id,
    orderDirection: asc
  ) {{
    id
    periodStartUnix
    liquidity
    feeGrowthGlobal0X128
    feeGrowthGlobal1X128
    volumeUSD
    txCount
  }}
}}
"""


@dataclass(frozen=True)
class HourlySnapshot:
    """One hour of pool state from PoolHourData."""
    id: str
    period_start: Timestamp
    liquidity: Liquidity
    fee_growth_global0_x128: FeeGrowthX128
    fee_growth_global1_x128: FeeGrowthX128
    volume_usd: float
    tx_count: int


def _parse_hourly(raw: dict) -> HourlySnapshot:
    return HourlySnapshot(
        id=raw["id"],
        period_start=int(raw["periodStartUnix"]),
        liquidity=int(raw["liquidity"]),
        fee_growth_global0_x128=int(raw["feeGrowthGlobal0X128"]),
        fee_growth_global1_x128=int(raw["feeGrowthGlobal1X128"]),
        volume_usd=float(raw["volumeUSD"]),
        tx_count=int(raw["txCount"]),
    )


def fetch_hourly_page(
    client: UniswapClient,
    pool_id: PoolId,
    last_id: str = "",
    page_size: int = PAGE_SIZE,
) -> Sequence[HourlySnapshot]:
    """Fetch one page of PoolHourData using keyset pagination."""
    query = HOURLY_QUERY.format(
        page_size=page_size, pool_id=pool_id, last_id=last_id,
    )
    data = client.query(query)
    return tuple(_parse_hourly(h) for h in data.get("poolHourDatas", []))


def fetch_all_hourly(
    client: UniswapClient,
    pool_id: PoolId,
    start_id: str = "",
    max_pages: int | None = None,
) -> Sequence[HourlySnapshot]:
    """Paginate through all PoolHourData for a pool."""
    all_hours: list[HourlySnapshot] = []
    last_id = start_id
    page = 0

    while True:
        batch = fetch_hourly_page(client, pool_id, last_id)
        if not batch:
            break

        all_hours.extend(batch)
        last_id = batch[-1].id
        page += 1

        if page % 10 == 0:
            print(f"  Hourly page {page}: {len(all_hours)} snapshots")

        if max_pages and page >= max_pages:
            break

        time.sleep(RATE_LIMIT_SEC)

    return tuple(all_hours)
