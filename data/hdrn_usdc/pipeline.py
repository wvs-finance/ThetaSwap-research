"""End-to-end pipeline: fetch HDRN/USDC swaps + hourly data, join, filter, transform, save.

Usage:
    python -m data.hdrn_usdc.pipeline
    python -m data.hdrn_usdc.pipeline --max-pages 5        # test run
    python -m data.hdrn_usdc.pipeline --block-level         # block-level RPC path
"""
from __future__ import annotations

import argparse
import csv
import os
from typing import Final

from data.UniswapClient import UniswapClient, v3
from data.hdrn_usdc.types import HDRN_USDC_POOL
from data.hdrn_usdc.fetch_swaps import fetch_all_swaps
from data.hdrn_usdc.fetch_hourly import fetch_all_hourly
from data.hdrn_usdc.persist import save_raw_swaps, load_raw_swaps, last_swap_id
from data.hdrn_usdc.sampling import filter_active_period, ActivePeriod, describe_sample
from data.hdrn_usdc.transform import to_observations_with_hourly, to_observations_block_level

RAW_CSV: Final = "data/hdrn_usdc/raw_swaps.csv"
OBS_CSV: Final = "data/hdrn_usdc/observations.csv"
BLOCK_STATE_CSV: Final = "data/hdrn_usdc/block_states.csv"
OBS_BLOCK_CSV: Final = "data/hdrn_usdc/observations_block.csv"

OBS_FIELDNAMES: Final = [
    "swap_id", "timestamp", "block_number", "pi_n", "l_active_n",
    "dlog_l_n", "volume_n", "gas_n", "dp_n", "tick_n",
    "fee_growth0", "fee_growth1",
]


def _save_observations(observations: tuple, path: str) -> None:
    """Write SwapObservation sequence to CSV."""
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OBS_FIELDNAMES)
        writer.writeheader()
        for obs in observations:
            writer.writerow({
                "swap_id": obs.swap_id,
                "timestamp": obs.timestamp,
                "block_number": obs.block_number,
                "pi_n": obs.pi_n,
                "l_active_n": obs.l_active_n,
                "dlog_l_n": obs.dlog_l_n,
                "volume_n": obs.volume_n,
                "gas_n": obs.gas_n,
                "dp_n": obs.dp_n,
                "tick_n": obs.tick_n,
                "fee_growth0": obs.fee_growth0,
                "fee_growth1": obs.fee_growth1,
            })


def _fetch_swaps(client: UniswapClient, max_pages: int | None) -> tuple:
    """Fetch raw swaps with resume support. Returns all swaps."""
    resume_id = last_swap_id(RAW_CSV)
    existing = load_raw_swaps(RAW_CSV) if resume_id else ()

    new_swaps = fetch_all_swaps(
        client, HDRN_USDC_POOL, start_id=resume_id, max_pages=max_pages,
    )

    if new_swaps:
        save_raw_swaps(new_swaps, RAW_CSV, append=bool(resume_id))
        return existing + tuple(new_swaps)
    return existing


def run(max_pages: int | None = None, block_level: bool = False) -> None:
    """Execute the full pipeline."""
    os.makedirs("data/hdrn_usdc", exist_ok=True)

    client = UniswapClient(v3())

    # Step 1: Fetch swaps (with resume)
    all_swaps = _fetch_swaps(client, max_pages)
    print(f"Total raw swaps: {len(all_swaps)}")

    # Step 2: Sample (filter active period)
    sampled = filter_active_period(all_swaps, ActivePeriod(min_swaps_per_quarter=50))
    print(f"After active period filter: {len(sampled)} swaps")
    print(describe_sample(sampled))

    if block_level:
        _run_block_level(sampled)
    else:
        _run_hourly(client, sampled, max_pages)


def _run_hourly(
    client: UniswapClient,
    sampled: tuple,
    max_pages: int | None,
) -> None:
    """Hourly path: fetch PoolHourData, bisect-join, save."""
    print("Fetching PoolHourData...")
    hourly = fetch_all_hourly(client, HDRN_USDC_POOL, max_pages=max_pages)
    print(f"Total hourly snapshots: {len(hourly)}")

    observations = to_observations_with_hourly(sampled, hourly)
    print(f"Observations (after hourly join): {len(observations)}")

    _save_observations(observations, OBS_CSV)
    print(f"Observations saved to {OBS_CSV}")


def _run_block_level(sampled: tuple) -> None:
    """Block-level path: fetch exact state per block via RPC, join, save."""
    from data.hdrn_usdc.fetch_block_state import fetch_block_states, load_block_states

    pool_address = HDRN_USDC_POOL

    # Extract unique block numbers from sampled swaps
    unique_blocks = sorted({s.block_number for s in sampled})
    print(f"Unique blocks to fetch: {len(unique_blocks)}")

    # Fetch block states (with resume)
    fetch_block_states(unique_blocks, pool_address, BLOCK_STATE_CSV)

    # Load and join
    block_states = load_block_states(BLOCK_STATE_CSV)
    print(f"Block states loaded: {len(block_states)}")

    observations = to_observations_block_level(sampled, block_states)
    print(f"Observations (after block-level join): {len(observations)}")

    _save_observations(observations, OBS_BLOCK_CSV)
    print(f"Block-level observations saved to {OBS_BLOCK_CSV}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument(
        "--block-level", action="store_true",
        help="Use block-level RPC data instead of hourly PoolHourData",
    )
    args = parser.parse_args()
    run(max_pages=args.max_pages, block_level=args.block_level)
