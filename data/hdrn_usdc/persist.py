"""CSV persistence for RawSwap data with resume support.

Pattern from data/compute_fee_compression.py: append mode + flush after write.
"""
from __future__ import annotations

import csv
import os
from typing import Sequence

from data.hdrn_usdc.types import RawSwap, SwapId

FIELDNAMES = [
    "id", "timestamp", "block_number", "tick", "sqrt_price_x96",
    "amount0", "amount1", "amount_usd", "gas_price",
    "pool_liquidity", "fee_growth_global0_x128", "fee_growth_global1_x128",
]


def _swap_to_row(swap: RawSwap) -> dict[str, str]:
    return {
        "id": swap.id,
        "timestamp": str(swap.timestamp),
        "block_number": str(swap.block_number),
        "tick": str(swap.tick),
        "sqrt_price_x96": str(swap.sqrt_price_x96),
        "amount0": str(swap.amount0),
        "amount1": str(swap.amount1),
        "amount_usd": str(swap.amount_usd),
        "gas_price": str(swap.gas_price),
        "pool_liquidity": str(swap.pool_liquidity),
        "fee_growth_global0_x128": str(swap.fee_growth_global0_x128),
        "fee_growth_global1_x128": str(swap.fee_growth_global1_x128),
    }


def _row_to_swap(row: dict[str, str]) -> RawSwap:
    return RawSwap(
        id=row["id"],
        timestamp=int(row["timestamp"]),
        block_number=int(row["block_number"]),
        tick=int(row["tick"]),
        sqrt_price_x96=int(row["sqrt_price_x96"]),
        amount0=float(row["amount0"]),
        amount1=float(row["amount1"]),
        amount_usd=float(row["amount_usd"]),
        gas_price=int(row["gas_price"]),
        pool_liquidity=int(row["pool_liquidity"]),
        fee_growth_global0_x128=int(row["fee_growth_global0_x128"]),
        fee_growth_global1_x128=int(row["fee_growth_global1_x128"]),
    )


def save_raw_swaps(
    swaps: Sequence[RawSwap],
    path: str,
    append: bool = False,
) -> None:
    """Write swaps to CSV. Append mode for incremental fetching."""
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    mode = "a" if (append and file_exists) else "w"
    with open(path, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if mode == "w":
            writer.writeheader()
        for swap in swaps:
            writer.writerow(_swap_to_row(swap))
        f.flush()


def load_raw_swaps(path: str) -> tuple[RawSwap, ...]:
    """Load all swaps from CSV."""
    with open(path) as f:
        return tuple(_row_to_swap(row) for row in csv.DictReader(f))


def last_swap_id(path: str) -> SwapId:
    """Get the last swap ID for resume support."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return ""
    last_id = ""
    with open(path) as f:
        for row in csv.DictReader(f):
            last_id = row["id"]
    return last_id
