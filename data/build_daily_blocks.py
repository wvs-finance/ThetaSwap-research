"""
Build a mapping of (date, blockNumber) — first block after midnight UTC each day.
Uses binary search on block timestamps via archive RPC.
"""
import csv
import datetime as dt
import time
from web3 import Web3

RPC_URL = "https://eth-mainnet.g.alchemy.com/v2/fd_m2oikp78msnnQGxO6H"
POOL_CREATED_DATE = dt.date(2021, 5, 5)  # first full day of V3 USDC/WETH
OUTPUT_PATH = "data/daily_blocks.csv"

w3 = Web3(Web3.HTTPProvider(RPC_URL))


def block_at_timestamp(target_ts: int) -> int:
    """Binary search for the first block at or after target_ts."""
    lo, hi = 12_000_000, w3.eth.block_number
    while lo < hi:
        mid = (lo + hi) // 2
        ts = w3.eth.get_block(mid).timestamp
        if ts < target_ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def main():
    today = dt.date.today()
    current = POOL_CREATED_DATE
    rows = []

    print(f"Building daily block mapping from {current} to {today}")

    while current <= today:
        midnight_utc = int(dt.datetime.combine(current, dt.time.min,
                                                tzinfo=dt.timezone.utc).timestamp())
        block = block_at_timestamp(midnight_utc)
        rows.append({"date": current.isoformat(), "block_number": block})

        if len(rows) % 100 == 0:
            print(f"  {current} -> block {block}  ({len(rows)} days)")

        current += dt.timedelta(days=1)
        time.sleep(0.05)  # rate limit

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "block_number"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. {len(rows)} days written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
