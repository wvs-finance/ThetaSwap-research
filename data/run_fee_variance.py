"""
Driver script: for each day, calls a Foundry script at the target block
to compute FeeVarianceX128. Writes results to data/fee_variance.csv.
"""
import csv
import os
import subprocess
import time

DAILY_BLOCKS_PATH = "data/daily_blocks.csv"
POSITION_REGISTRY_PATH = "data/position_registry.csv"
OUTPUT_PATH = "data/fee_variance.csv"
FOUNDRY_DIR = "contracts/fee-variance"
RPC_URL = "https://eth-mainnet.g.alchemy.com/v2/fd_m2oikp78msnnQGxO6H"


def load_daily_blocks():
    with open(DAILY_BLOCKS_PATH) as f:
        reader = csv.DictReader(f)
        return [(row["date"], int(row["block_number"])) for row in reader]


def compute_fee_variance_at_block(block_number: int) -> dict:
    """
    Call Foundry script at a specific block to compute FeeVarianceX128.
    Uses forge script with --fork-block-number.
    """
    env = os.environ.copy()
    env["ETH_RPC_URL"] = RPC_URL

    result = subprocess.run(
        [
            "forge", "script",
            "script/ComputeFeeVariance.s.sol",
            "--fork-url", RPC_URL,
            "--fork-block-number", str(block_number),
            "--ffi",
            "-vvv"
        ],
        capture_output=True, text=True,
        cwd=FOUNDRY_DIR,
        env=env,
        timeout=600
    )

    # Parse output for FeeVarianceX128 and numPositions
    output = result.stdout + result.stderr
    variance = 0
    num_pos = 0
    for line in output.split("\n"):
        if "FeeVariance:" in line:
            parts = line.split("FeeVariance:")[1].strip().split()
            if parts:
                try:
                    variance = int(parts[0].rstrip(","))
                except ValueError:
                    pass
        if "Positions:" in line:
            parts = line.split("Positions:")[1].strip().split()
            if parts:
                try:
                    num_pos = int(parts[0])
                except ValueError:
                    pass

    return {"fee_variance_x128": variance, "num_positions": num_pos}


def main():
    daily_blocks = load_daily_blocks()

    # Resume support: skip already-computed days
    completed_dates = set()
    if os.path.exists(OUTPUT_PATH):
        with open(OUTPUT_PATH) as f:
            reader = csv.DictReader(f)
            for row in reader:
                completed_dates.add(row["date"])
        print(f"Resuming: {len(completed_dates)} days already computed")

    mode = "a" if completed_dates else "w"
    remaining = [(d, b) for d, b in daily_blocks if d not in completed_dates]

    print(f"Computing FeeVariance for {len(remaining)} remaining days")

    with open(OUTPUT_PATH, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "block_number", "fee_variance_x128", "num_positions"])
        if not completed_dates:
            writer.writeheader()

        for i, (date, block) in enumerate(remaining):
            try:
                result = compute_fee_variance_at_block(block)
                row = {
                    "date": date,
                    "block_number": block,
                    **result
                }
                writer.writerow(row)
                f.flush()

                if (i + 1) % 10 == 0:
                    print(f"  [{i+1}/{len(remaining)}] {date} block={block} "
                          f"variance={result['fee_variance_x128']} "
                          f"positions={result['num_positions']}")
            except Exception as e:
                print(f"  ERROR at {date} block={block}: {e}")
                writer.writerow({
                    "date": date, "block_number": block,
                    "fee_variance_x128": 0, "num_positions": 0
                })
                f.flush()

            time.sleep(0.1)  # small delay between fork calls

    print(f"Done. Results written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
