"""
Build a mapping of (date, blockNumber) — first block after midnight UTC each day.
Uses binary search on block timestamps via archive RPC with proper timeouts.
"""
import csv
import datetime as dt
import sys
from web3 import Web3

RPC_URL = "https://eth-mainnet.g.alchemy.com/v2/fd_m2oikp78msnnQGxO6H"
POOL_CREATED_DATE = dt.date(2021, 5, 5)
OUTPUT_PATH = "data/daily_blocks.csv"
BLOCKS_PER_DAY = 7200

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 30}))
LATEST_BLOCK = w3.eth.block_number


def get_block_ts(block_num: int) -> int:
    return w3.eth.get_block(block_num).timestamp


def block_at_timestamp(target_ts: int, hint: int) -> int:
    """Narrowed binary search for the first block >= target_ts."""
    lo = max(hint - 500, 0)
    hi = min(hint + BLOCKS_PER_DAY + 500, LATEST_BLOCK)

    # Ensure lo < target
    if get_block_ts(lo) >= target_ts:
        lo = max(lo - BLOCKS_PER_DAY, 0)
    # Ensure hi >= target
    if get_block_ts(hi) < target_ts:
        hi = min(hi + BLOCKS_PER_DAY, LATEST_BLOCK)

    while lo < hi:
        mid = (lo + hi) // 2
        if get_block_ts(mid) < target_ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def main():
    latest_ts = get_block_ts(LATEST_BLOCK)
    latest_date = dt.datetime.fromtimestamp(latest_ts, tz=dt.timezone.utc).date()
    end_date = min(dt.date.today(), latest_date)

    print(f"Building daily block mapping from {POOL_CREATED_DATE} to {end_date}", flush=True)
    print(f"Latest block: {LATEST_BLOCK}", flush=True)

    current = POOL_CREATED_DATE
    rows = []
    prev_block = 12_370_863

    while current <= end_date:
        midnight_utc = int(dt.datetime.combine(current, dt.time.min,
                                                tzinfo=dt.timezone.utc).timestamp())
        try:
            block = block_at_timestamp(midnight_utc, hint=prev_block)
            rows.append({"date": current.isoformat(), "block_number": block})
            prev_block = block + BLOCKS_PER_DAY
        except Exception as e:
            print(f"  ERROR {current}: {e}", flush=True)
            # Use hint as fallback
            rows.append({"date": current.isoformat(), "block_number": prev_block})
            prev_block += BLOCKS_PER_DAY

        if len(rows) % 50 == 0:
            # Verify accuracy
            actual_ts = get_block_ts(rows[-1]["block_number"])
            actual_dt = dt.datetime.fromtimestamp(actual_ts, tz=dt.timezone.utc)
            print(f"  {current} -> block {rows[-1]['block_number']} "
                  f"(actual: {actual_dt.strftime('%Y-%m-%d %H:%M:%S')})  "
                  f"({len(rows)} days)", flush=True)

        current += dt.timedelta(days=1)

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "block_number"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. {len(rows)} days written to {OUTPUT_PATH}", flush=True)


if __name__ == "__main__":
    main()
