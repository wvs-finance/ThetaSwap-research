"""
Compute FeeVarianceX128 on a sampled subset of days for model validation.

Strategy: Every 7th day from Multicall3 deployment onward (~210 samples).
Pre-Multicall3 blocks are skipped — they're slow and have few positions.
Uses Multicall3 batching (~45s/day) → ~3 hours total.
"""
import csv
import json
import os
import time
import numpy as np
from web3 import Web3
from eth_abi import encode, decode

RPC_URL = "https://eth-mainnet.g.alchemy.com/v2/fd_m2oikp78msnnQGxO6H"
DAILY_BLOCKS_PATH = "data/daily_blocks.csv"
POSITION_REGISTRY_PATH = "data/position_registry.csv"
OUTPUT_PATH = "data/fee_variance_sample.csv"

NPM_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
POOL_ADDRESS = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"
MULTICALL3_DEPLOY_BLOCK = 14_353_601

SAMPLE_INTERVAL = 7  # every Nth day

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 120}))

Q128 = 2**128
Q192 = 2**192
UINT256_MAX = 2**256

# Function selectors
POSITIONS_SIG = Web3.keccak(text="positions(uint256)")[:4]
SLOT0_SIG = Web3.keccak(text="slot0()")[:4]
TICKS_SIG = Web3.keccak(text="ticks(int24)")[:4]
FEE_GROWTH0_SIG = Web3.keccak(text="feeGrowthGlobal0X128()")[:4]
FEE_GROWTH1_SIG = Web3.keccak(text="feeGrowthGlobal1X128()")[:4]
AGGREGATE3_SIG = Web3.keccak(text="aggregate3((address,bool,bytes)[])")[:4]


def multicall(calls, block_num, batch_size=200):
    """Execute batched calls via Multicall3."""
    results = []
    for i in range(0, len(calls), batch_size):
        batch = calls[i:i + batch_size]
        encoded_calls = [(Web3.to_checksum_address(t), True, cd) for t, cd in batch]
        multicall_data = AGGREGATE3_SIG + encode(
            ["(address,bool,bytes)[]"], [encoded_calls]
        )
        try:
            raw = w3.eth.call(
                {"to": MULTICALL3, "data": multicall_data},
                block_identifier=block_num
            )
            decoded = decode(["(bool,bytes)[]"], raw)[0]
            results.extend(decoded)
        except Exception as e:
            results.extend([(False, b"")] * len(batch))
            print(f"    Multicall batch failed: {e}", flush=True)
        time.sleep(0.05)
    return results


def load_daily_blocks():
    with open(DAILY_BLOCKS_PATH) as f:
        return [(r["date"], int(r["block_number"])) for r in csv.DictReader(f)]


def load_positions():
    with open(POSITION_REGISTRY_PATH) as f:
        return [(int(r["tokenId"]), int(r["tickLower"]), int(r["tickUpper"]))
                for r in csv.DictReader(f)]


def compute_variance_at_block(block_num, positions):
    """Compute FeeVarianceX128 at a specific block using Multicall3."""

    # Step 1: Pool state
    pool_calls = [
        (POOL_ADDRESS, SLOT0_SIG),
        (POOL_ADDRESS, FEE_GROWTH0_SIG),
        (POOL_ADDRESS, FEE_GROWTH1_SIG),
    ]
    pool_results = multicall(pool_calls, block_num, batch_size=10)

    for pr in pool_results:
        if not pr[0] or len(pr[1]) < 32:
            return 0, 0

    slot0_data = decode(
        ["uint160", "int24", "uint16", "uint16", "uint16", "uint8", "bool"],
        pool_results[0][1]
    )
    sqrt_price_x96 = slot0_data[0]
    tick_current = slot0_data[1]
    price_x128 = (sqrt_price_x96 * sqrt_price_x96 * Q128) // Q192

    fg_global0 = decode(["uint256"], pool_results[1][1])[0]
    fg_global1 = decode(["uint256"], pool_results[2][1])[0]

    # Step 2: Filter to in-range positions
    in_range = [(tid, tl, tu) for tid, tl, tu in positions
                if tl <= tick_current < tu]

    if len(in_range) < 2:
        return 0, len(in_range)

    # Step 3: Batch-read position data
    pos_calls = [
        (NPM_ADDRESS, POSITIONS_SIG + encode(["uint256"], [tid]))
        for tid, _, _ in in_range
    ]
    pos_results = multicall(pos_calls, block_num, batch_size=150)

    # Step 4: Collect active positions and unique ticks
    ticks_needed = set()
    active_positions = []

    for (tid, tl, tu), (success, data) in zip(in_range, pos_results):
        if not success or len(data) < 32:
            continue
        try:
            pos = decode(
                ["uint96", "address", "address", "address", "uint24",
                 "int24", "int24", "uint128", "uint256", "uint256",
                 "uint128", "uint128"],
                data
            )
            liq = pos[7]
            if liq == 0:
                continue
            active_positions.append((tid, tl, tu, liq, pos[8], pos[9], pos[10], pos[11]))
            ticks_needed.add(tl)
            ticks_needed.add(tu)
        except Exception:
            continue

    if len(active_positions) < 2:
        return 0, len(active_positions)

    # Step 5: Batch-read tick data
    tick_list = sorted(ticks_needed)
    tick_calls = [
        (POOL_ADDRESS, TICKS_SIG + encode(["int24"], [t]))
        for t in tick_list
    ]
    tick_results = multicall(tick_calls, block_num, batch_size=200)

    tick_fgo = {}
    for t, (success, data) in zip(tick_list, tick_results):
        if success and len(data) >= 32:
            try:
                td = decode(
                    ["uint128", "int128", "uint256", "uint256",
                     "int56", "uint160", "uint32", "bool"],
                    data
                )
                tick_fgo[t] = (td[2], td[3])
            except Exception:
                tick_fgo[t] = (0, 0)
        else:
            tick_fgo[t] = (0, 0)

    # Step 6: Compute per-position fees and variance
    fees_list = []
    liq_list = []

    for tid, tl, tu, liq, fg_inside0_last, fg_inside1_last, owed0, owed1 in active_positions:
        lower_fgo0, lower_fgo1 = tick_fgo.get(tl, (0, 0))
        upper_fgo0, upper_fgo1 = tick_fgo.get(tu, (0, 0))

        if tick_current < tl:
            fg_inside0 = (lower_fgo0 - upper_fgo0) % UINT256_MAX
            fg_inside1 = (lower_fgo1 - upper_fgo1) % UINT256_MAX
        elif tick_current < tu:
            fg_inside0 = (fg_global0 - lower_fgo0 - upper_fgo0) % UINT256_MAX
            fg_inside1 = (fg_global1 - lower_fgo1 - upper_fgo1) % UINT256_MAX
        else:
            fg_inside0 = (upper_fgo0 - lower_fgo0) % UINT256_MAX
            fg_inside1 = (upper_fgo1 - lower_fgo1) % UINT256_MAX

        fees0 = ((fg_inside0 - fg_inside0_last) % UINT256_MAX) * liq // Q128 + owed0
        fees1 = ((fg_inside1 - fg_inside1_last) % UINT256_MAX) * liq // Q128 + owed1

        fees_usd = float(fees0) * Q128 + float(fees1) * float(price_x128)

        if fees_usd > 0:
            fees_list.append(fees_usd)
            liq_list.append(float(liq))

    if len(fees_list) < 2:
        return 0, len(fees_list)

    fees_arr = np.array(fees_list)
    liq_arr = np.array(liq_list)

    fee_share = fees_arr / fees_arr.sum()
    liq_share = liq_arr / liq_arr.sum()
    c = fee_share - liq_share

    variance = float(np.mean(c**2))
    variance_x128 = int(variance * Q128)

    return variance_x128, len(fees_list)


def main():
    daily_blocks = load_daily_blocks()
    positions = load_positions()

    # Filter to Multicall3-era only, sample every Nth day
    eligible = [(d, b) for d, b in daily_blocks if b >= MULTICALL3_DEPLOY_BLOCK]
    sampled = eligible[::SAMPLE_INTERVAL]
    print(f"Loaded {len(positions)} positions, {len(daily_blocks)} total days", flush=True)
    print(f"Multicall3-era: {len(eligible)} days, sampling every {SAMPLE_INTERVAL}th → {len(sampled)} days", flush=True)

    # Resume support
    completed_dates = set()
    if os.path.exists(OUTPUT_PATH) and os.path.getsize(OUTPUT_PATH) > 0:
        with open(OUTPUT_PATH) as f:
            for row in csv.DictReader(f):
                completed_dates.add(row["date"])
        print(f"Resuming: {len(completed_dates)} days already computed", flush=True)

    remaining = [(d, b) for d, b in sampled if d not in completed_dates]
    print(f"Computing fee variance for {len(remaining)} remaining days", flush=True)

    mode = "a" if completed_dates else "w"
    fieldnames = ["date", "block_number", "fee_variance_x128", "num_positions"]
    with open(OUTPUT_PATH, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not completed_dates:
            writer.writeheader()

        for i, (date, block) in enumerate(remaining):
            t0 = time.time()
            try:
                variance, num_pos = compute_variance_at_block(block, positions)
                elapsed = time.time() - t0
                row = {
                    "date": date,
                    "block_number": block,
                    "fee_variance_x128": variance,
                    "num_positions": num_pos,
                }
                writer.writerow(row)
                f.flush()

                if (i + 1) % 5 == 0 or i == 0:
                    remaining_days = len(remaining) - i - 1
                    eta_hours = elapsed * remaining_days / 3600
                    print(f"  [{i+1}/{len(remaining)}] {date} "
                          f"variance={variance} pos={num_pos} "
                          f"time={elapsed:.1f}s ETA={eta_hours:.1f}h", flush=True)

            except Exception as e:
                print(f"  ERROR {date} block={block}: {e}", flush=True)
                writer.writerow({
                    "date": date, "block_number": block,
                    "fee_variance_x128": 0, "num_positions": 0,
                })
                f.flush()

    print(f"Done. {len(remaining)} days written to {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
