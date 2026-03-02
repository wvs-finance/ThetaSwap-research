"""End-to-end pipeline: fetch HDRN/USDC swaps, filter, transform, save.

Usage:
    python -m data.hdrn_usdc.pipeline
    python -m data.hdrn_usdc.pipeline --max-pages 5  # test run
"""
from __future__ import annotations

import argparse
import csv
import os
from typing import Final

from data.UniswapClient import UniswapClient, v3
from data.hdrn_usdc.types import HDRN_USDC_POOL
from data.hdrn_usdc.fetch_swaps import fetch_all_swaps
from data.hdrn_usdc.persist import save_raw_swaps, load_raw_swaps, last_swap_id
from data.hdrn_usdc.sampling import filter_active_period, ActivePeriod, describe_sample
from data.hdrn_usdc.transform import to_observations

RAW_CSV: Final = "data/hdrn_usdc/raw_swaps.csv"
OBS_CSV: Final = "data/hdrn_usdc/observations.csv"

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


def run(max_pages: int | None = None) -> None:
    """Execute the full pipeline."""
    os.makedirs("data/hdrn_usdc", exist_ok=True)

    # Step 1: Fetch (with resume)
    resume_id = last_swap_id(RAW_CSV)
    if resume_id:
        print(f"Resuming from swap {resume_id}")
        existing = load_raw_swaps(RAW_CSV)
    else:
        existing = ()

    client = UniswapClient(v3())
    new_swaps = fetch_all_swaps(client, HDRN_USDC_POOL, start_id=resume_id, max_pages=max_pages)

    if new_swaps:
        save_raw_swaps(new_swaps, RAW_CSV, append=bool(resume_id))
        all_swaps = existing + tuple(new_swaps)
    else:
        all_swaps = existing

    print(f"Total raw swaps: {len(all_swaps)}")

    # Step 2: Sample (filter active period)
    sampled = filter_active_period(all_swaps, ActivePeriod(min_swaps_per_quarter=50))
    print(f"After active period filter: {len(sampled)} swaps")
    print(describe_sample(sampled))

    # Step 3: Transform
    observations = to_observations(sampled)
    print(f"Observations (N-1): {len(observations)}")

    # Step 4: Save observations
    _save_observations(observations, OBS_CSV)
    print(f"Observations saved to {OBS_CSV}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=None)
    args = parser.parse_args()
    run(max_pages=args.max_pages)
