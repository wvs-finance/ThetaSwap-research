"""
Lightweight RPC script that computes feeGrowthInside for the implied [P10, P90]
tick range and a median-width reference position at each of ~208 sample blocks.

Total: 5-7 RPC calls per block (all batched in 1-2 Multicall3 calls).
Output: data/fg_inside_range_sample.csv
"""
import csv
import os
import time
import numpy as np
from web3 import Web3
from eth_abi import encode, decode

# ---------------------------------------------------------------------------
# Constants (reused from compute_fee_compression.py)
# ---------------------------------------------------------------------------
RPC_URL = "https://eth-mainnet.g.alchemy.com/v2/fd_m2oikp78msnnQGxO6H"
DAILY_BLOCKS_PATH = "data/daily_blocks.csv"
POSITION_REGISTRY_PATH = "data/position_registry.csv"
OUTPUT_PATH = "data/fg_inside_range_sample.csv"

NPM_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
POOL_ADDRESS = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"
MULTICALL3_DEPLOY_BLOCK = 14_353_601

SAMPLE_INTERVAL = 7  # every Nth day

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 120}))

UINT256_MAX = 2**256

# Function selectors
SLOT0_SIG = Web3.keccak(text="slot0()")[:4]
TICKS_SIG = Web3.keccak(text="ticks(int24)")[:4]
FEE_GROWTH0_SIG = Web3.keccak(text="feeGrowthGlobal0X128()")[:4]
FEE_GROWTH1_SIG = Web3.keccak(text="feeGrowthGlobal1X128()")[:4]
AGGREGATE3_SIG = Web3.keccak(text="aggregate3((address,bool,bytes)[])")[:4]


# ---------------------------------------------------------------------------
# Multicall helper (same pattern as compute_fee_compression.py)
# ---------------------------------------------------------------------------
def multicall(calls, block_num, batch_size=200):
    """Execute batched calls via Multicall3 with retry on rate limits."""
    results = []
    for i in range(0, len(calls), batch_size):
        batch = calls[i:i + batch_size]
        encoded_calls = [(Web3.to_checksum_address(t), True, cd) for t, cd in batch]
        multicall_data = AGGREGATE3_SIG + encode(
            ["(address,bool,bytes)[]"], [encoded_calls]
        )
        success = False
        for attempt in range(4):
            try:
                raw = w3.eth.call(
                    {"to": MULTICALL3, "data": multicall_data},
                    block_identifier=block_num
                )
                decoded = decode(["(bool,bytes)[]"], raw)[0]
                results.extend(decoded)
                success = True
                break
            except Exception as e:
                if "429" in str(e) or "Too Many" in str(e):
                    time.sleep(2.0 * (attempt + 1))
                else:
                    print(f"    Multicall batch failed: {e}", flush=True)
                    break
        if not success:
            results.extend([(False, b"")] * len(batch))
        time.sleep(0.1)
    return results


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
def load_daily_blocks():
    with open(DAILY_BLOCKS_PATH) as f:
        return [(r["date"], int(r["block_number"])) for r in csv.DictReader(f)]


def load_positions():
    with open(POSITION_REGISTRY_PATH) as f:
        return [(int(r["tokenId"]), int(r["tickLower"]), int(r["tickUpper"]),
                 int(r["liquidity"]))
                for r in csv.DictReader(f)]


# ---------------------------------------------------------------------------
# feeGrowthInside computation (pure Python int arithmetic)
# ---------------------------------------------------------------------------
def fee_growth_inside(tick_current, tick_lower, tick_upper,
                      fg_global0, fg_global1, lower_fgo0, lower_fgo1,
                      upper_fgo0, upper_fgo1):
    """Compute feeGrowthInside0X128 and feeGrowthInside1X128 using modular
    arithmetic, matching the Solidity implementation exactly."""
    if tick_current < tick_lower:
        fg0 = (lower_fgo0 - upper_fgo0) % UINT256_MAX
        fg1 = (lower_fgo1 - upper_fgo1) % UINT256_MAX
    elif tick_current < tick_upper:
        fg0 = (fg_global0 - lower_fgo0 - upper_fgo0) % UINT256_MAX
        fg1 = (fg_global1 - lower_fgo1 - upper_fgo1) % UINT256_MAX
    else:
        fg0 = (upper_fgo0 - lower_fgo0) % UINT256_MAX
        fg1 = (upper_fgo1 - lower_fgo1) % UINT256_MAX
    return fg0, fg1


# ---------------------------------------------------------------------------
# Core per-block computation
# ---------------------------------------------------------------------------
def compute_at_block(block_num, positions):
    """Compute feeGrowthInside for implied range and reference position.

    Returns a dict with all output fields, or None on failure.
    """

    # ------------------------------------------------------------------
    # Step 1: Pool state via Multicall3 (3 calls)
    # ------------------------------------------------------------------
    pool_calls = [
        (POOL_ADDRESS, SLOT0_SIG),
        (POOL_ADDRESS, FEE_GROWTH0_SIG),
        (POOL_ADDRESS, FEE_GROWTH1_SIG),
    ]
    pool_results = multicall(pool_calls, block_num, batch_size=10)

    for pr in pool_results:
        if not pr[0] or len(pr[1]) < 32:
            return None

    slot0_data = decode(
        ["uint160", "int24", "uint16", "uint16", "uint16", "uint8", "bool"],
        pool_results[0][1]
    )
    tick_current = slot0_data[1]
    fg_global0 = decode(["uint256"], pool_results[1][1])[0]
    fg_global1 = decode(["uint256"], pool_results[2][1])[0]

    # ------------------------------------------------------------------
    # Step 2: In-range positions from registry (equal-weighted, no RPC)
    # ------------------------------------------------------------------
    in_range = [(tid, tl, tu) for tid, tl, tu, _liq in positions
                if tl <= tick_current < tu]

    num_in_range = len(in_range)
    if num_in_range < 2:
        return None

    # ------------------------------------------------------------------
    # Step 3: Implied tick range — P10(tickLower), P90(tickUpper)
    #         equal-weighted since we don't have per-block liquidity
    # ------------------------------------------------------------------
    tl_arr = np.array([tl for _, tl, _ in in_range])
    tu_arr = np.array([tu for _, _, tu in in_range])

    p10_tick = int(np.percentile(tl_arr, 10, method="lower"))
    p90_tick = int(np.percentile(tu_arr, 90, method="higher"))

    # ------------------------------------------------------------------
    # Step 4: Reference position — median tick-width in-range position
    # ------------------------------------------------------------------
    widths = tu_arr - tl_arr
    median_width = np.median(widths)
    # Pick the position whose width is closest to the median
    closest_idx = int(np.argmin(np.abs(widths - median_width)))
    ref_tl = int(tl_arr[closest_idx])
    ref_tu = int(tu_arr[closest_idx])

    # ------------------------------------------------------------------
    # Step 5: Read feeGrowthOutside at up to 4 unique ticks (1-4 calls)
    # ------------------------------------------------------------------
    unique_ticks = sorted(set([p10_tick, p90_tick, ref_tl, ref_tu]))
    tick_calls = [
        (POOL_ADDRESS, TICKS_SIG + encode(["int24"], [t]))
        for t in unique_ticks
    ]
    tick_results = multicall(tick_calls, block_num, batch_size=10)

    tick_fgo = {}
    for t, (success, data) in zip(unique_ticks, tick_results):
        if success and len(data) >= 32:
            try:
                td = decode(
                    ["uint128", "int128", "uint256", "uint256",
                     "int56", "uint160", "uint32", "bool"],
                    data
                )
                tick_fgo[t] = (td[2], td[3])
            except Exception as e:
                print(f"    Failed to decode tick {t}: {e}", flush=True)
                return None  # abort this block — corrupted tick data
        else:
            return None  # abort this block — tick read failed

    # ------------------------------------------------------------------
    # Step 6: feeGrowthInside for implied range and reference position
    # ------------------------------------------------------------------
    p10_fgo0, p10_fgo1 = tick_fgo[p10_tick]
    p90_fgo0, p90_fgo1 = tick_fgo[p90_tick]
    range_fg0, range_fg1 = fee_growth_inside(
        tick_current, p10_tick, p90_tick,
        fg_global0, fg_global1,
        p10_fgo0, p10_fgo1, p90_fgo0, p90_fgo1,
    )

    ref_lower_fgo0, ref_lower_fgo1 = tick_fgo[ref_tl]
    ref_upper_fgo0, ref_upper_fgo1 = tick_fgo[ref_tu]
    ref_fg0, ref_fg1 = fee_growth_inside(
        tick_current, ref_tl, ref_tu,
        fg_global0, fg_global1,
        ref_lower_fgo0, ref_lower_fgo1, ref_upper_fgo0, ref_upper_fgo1,
    )

    # ------------------------------------------------------------------
    # Step 7: actual_pcr = ref_fg0 / range_fg0 (token0/USDC primary)
    # ------------------------------------------------------------------
    if range_fg0 > 0:
        actual_pcr = float(ref_fg0) / float(range_fg0)
    else:
        actual_pcr = 0.0

    return {
        "tick_current": tick_current,
        "p10_tick": p10_tick,
        "p90_tick": p90_tick,
        "ref_tl": ref_tl,
        "ref_tu": ref_tu,
        "range_fg0": str(range_fg0),
        "range_fg1": str(range_fg1),
        "ref_fg0": str(ref_fg0),
        "ref_fg1": str(ref_fg1),
        "actual_pcr": actual_pcr,
        "num_in_range": num_in_range,
    }


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
FIELDNAMES = [
    "date", "block_number", "tick_current",
    "p10_tick", "p90_tick", "ref_tl", "ref_tu",
    "range_fg0", "range_fg1", "ref_fg0", "ref_fg1",
    "actual_pcr", "num_in_range",
]


def main():
    daily_blocks = load_daily_blocks()
    positions = load_positions()

    # Filter to Multicall3-era, sample every Nth day
    eligible = [(d, b) for d, b in daily_blocks if b >= MULTICALL3_DEPLOY_BLOCK]
    sampled = eligible[::SAMPLE_INTERVAL]
    print(f"Loaded {len(positions)} positions, {len(daily_blocks)} total days",
          flush=True)
    print(f"Multicall3-era: {len(eligible)} days, sampling every "
          f"{SAMPLE_INTERVAL}th -> {len(sampled)} days", flush=True)

    # Resume support
    completed_dates = set()
    if os.path.exists(OUTPUT_PATH) and os.path.getsize(OUTPUT_PATH) > 0:
        with open(OUTPUT_PATH) as f:
            for row in csv.DictReader(f):
                completed_dates.add(row["date"])
        print(f"Resuming: {len(completed_dates)} days already computed",
              flush=True)

    remaining = [(d, b) for d, b in sampled if d not in completed_dates]
    print(f"Computing feeGrowthInside for {len(remaining)} remaining days",
          flush=True)

    mode = "a" if completed_dates else "w"
    with open(OUTPUT_PATH, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if not completed_dates:
            writer.writeheader()

        for i, (date, block) in enumerate(remaining):
            t0 = time.time()
            try:
                result = compute_at_block(block, positions)
                elapsed = time.time() - t0

                if result is None:
                    row = {k: "" for k in FIELDNAMES}
                    row["date"] = date
                    row["block_number"] = block
                    row["num_in_range"] = 0
                    writer.writerow(row)
                    f.flush()
                    if (i + 1) % 5 == 0 or i == 0:
                        print(f"  [{i+1}/{len(remaining)}] {date} "
                              f"SKIP (too few in-range) time={elapsed:.1f}s",
                              flush=True)
                    continue

                row = {"date": date, "block_number": block}
                row.update(result)
                writer.writerow(row)
                f.flush()

                if (i + 1) % 5 == 0 or i == 0:
                    remaining_days = len(remaining) - i - 1
                    eta_min = elapsed * remaining_days / 60
                    print(f"  [{i+1}/{len(remaining)}] {date} "
                          f"pcr={result['actual_pcr']:.4f} "
                          f"in_range={result['num_in_range']} "
                          f"p10={result['p10_tick']} p90={result['p90_tick']} "
                          f"ref=[{result['ref_tl']},{result['ref_tu']}] "
                          f"time={elapsed:.1f}s ETA={eta_min:.1f}m",
                          flush=True)

            except Exception as e:
                elapsed = time.time() - t0
                print(f"  ERROR {date} block={block}: {e} "
                      f"time={elapsed:.1f}s", flush=True)
                row = {k: "" for k in FIELDNAMES}
                row["date"] = date
                row["block_number"] = block
                row["num_in_range"] = 0
                writer.writerow(row)
                f.flush()

    print(f"Done. {len(remaining)} days written to {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
