# Structural Fee Variance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a two-phase pipeline that computes daily `FeeVarianceX128` (cross-sectional variance of fee-share-minus-liquidity-share) across all NPM positions on V3 USDC/WETH, outputting a CSV time series for the econometric model.

**Architecture:** Phase 1 (Python) indexes all NPM positions for the pool from event logs → `data/position_registry.csv`. Phase 2 (Foundry script) replays 1,760 daily blocks via `vm.rollFork()`, computes per-position fees via `PositionValue.fees()`, calculates `FeeVarianceX128`, writes to `data/fee_variance.csv` via FFI. Phase 3 integrates the CSV into the econometrics pipeline.

**Tech Stack:** Python (web3.py), Foundry (forge script), Uniswap V3 periphery (`PositionValue`, `NonfungiblePositionManager`), Alchemy archive RPC.

**Constants:**
- V3 USDC/WETH Pool: `0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640`
- NonfungiblePositionManager (NPM): `0xC36442b4a4522E871399CD717aBDD847Ab11FE88`
- ETH RPC: `https://eth-mainnet.g.alchemy.com/v2/fd_m2oikp78msnnQGxO6H`
- Pool created: block ~12376729 (2021-05-04)

---

### Task 1: Initialize Foundry project

**Files:**
- Create: `contracts/fee-variance/foundry.toml`
- Create: `contracts/fee-variance/src/.gitkeep`
- Create: `contracts/fee-variance/script/.gitkeep`

**Step 1: Create the Foundry project**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research
mkdir -p contracts/fee-variance
cd contracts/fee-variance
forge init --no-git --no-commit
```

**Step 2: Configure `foundry.toml`**

Replace the generated `foundry.toml` with:

```toml
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
evm_version = "shanghai"
ffi = true

[rpc_endpoints]
mainnet = "${ETH_RPC_URL}"
```

**Step 3: Install Uniswap V3 dependencies**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research/contracts/fee-variance
forge install Uniswap/v3-periphery --no-git --no-commit
forge install Uniswap/v3-core --no-git --no-commit
forge install OpenZeppelin/openzeppelin-contracts@v3.4.2-solc-0.7 --no-git --no-commit
```

**Step 4: Add remappings**

Create `contracts/fee-variance/remappings.txt`:

```
@uniswap/v3-periphery/=lib/v3-periphery/
@uniswap/v3-core/=lib/v3-core/
@openzeppelin/=lib/openzeppelin-contracts/
```

**Step 5: Create `.env`**

```bash
echo 'ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/fd_m2oikp78msnnQGxO6H' > contracts/fee-variance/.env
```

**Step 6: Verify setup compiles**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research/contracts/fee-variance
forge build
```

Expected: Compiles with no errors.

**Step 7: Commit**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research
git add contracts/fee-variance/foundry.toml contracts/fee-variance/remappings.txt contracts/fee-variance/src/ contracts/fee-variance/script/
git commit -m "feat: initialize Foundry project for fee variance computation"
```

---

### Task 2: Build daily block number mapping (Python)

**Files:**
- Create: `data/build_daily_blocks.py`
- Output: `data/daily_blocks.csv`

**Step 1: Create the script**

Create `data/build_daily_blocks.py`:

```python
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
```

**Step 2: Run the script**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research
source uhi8/bin/activate
pip install web3 2>/dev/null
python3 data/build_daily_blocks.py
```

Expected: Creates `data/daily_blocks.csv` with ~1,760 rows. Takes 5-15 minutes (binary search RPC calls). Output like:
```
date,block_number
2021-05-05,12376800
2021-05-06,12383200
...
```

**Step 3: Verify output**

```bash
head -5 data/daily_blocks.csv
wc -l data/daily_blocks.csv
```

Expected: ~1,761 lines (header + ~1,760 days). Block numbers increase monotonically.

**Step 4: Commit**

```bash
git add data/build_daily_blocks.py data/daily_blocks.csv
git commit -m "feat: build daily block number mapping for V3 USDC/WETH"
```

---

### Task 3: Build position registry (Python)

**Files:**
- Create: `data/build_position_registry.py`
- Output: `data/position_registry.csv`

**Step 1: Create the script**

Create `data/build_position_registry.py`:

```python
"""
Build registry of all NPM positions on V3 USDC/WETH pool.
Scans IncreaseLiquidity events and checks which tokenIds belong to our pool.
"""
import csv
import json
import time
from web3 import Web3

RPC_URL = "https://eth-mainnet.g.alchemy.com/v2/fd_m2oikp78msnnQGxO6H"
NPM_ADDRESS = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
POOL_ADDRESS = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
START_BLOCK = 12_369_621  # NPM deployment block
OUTPUT_PATH = "data/position_registry.csv"
CHUNK_SIZE = 10_000  # blocks per getLogs call

w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Minimal NPM ABI for positions() call
NPM_ABI = json.loads("""[
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "positions",
        "outputs": [
            {"name": "nonce", "type": "uint96"},
            {"name": "operator", "type": "address"},
            {"name": "token0", "type": "address"},
            {"name": "token1", "type": "address"},
            {"name": "fee", "type": "uint24"},
            {"name": "tickLower", "type": "int24"},
            {"name": "tickUpper", "type": "int24"},
            {"name": "liquidity", "type": "uint128"},
            {"name": "feeGrowthInside0LastX128", "type": "uint256"},
            {"name": "feeGrowthInside1LastX128", "type": "uint256"},
            {"name": "tokensOwed0", "type": "uint128"},
            {"name": "tokensOwed1", "type": "uint128"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]""")

npm = w3.eth.contract(address=NPM_ADDRESS, abi=NPM_ABI)

# IncreaseLiquidity event signature
INCREASE_LIQUIDITY_TOPIC = w3.keccak(
    text="IncreaseLiquidity(uint256,uint128,uint256,uint256)"
).hex()

# USDC and WETH addresses (token0=USDC, token1=WETH for this pool)
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48".lower()
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2".lower()
POOL_FEE = 500  # 5 bps


def get_token_ids_from_events() -> set:
    """Scan IncreaseLiquidity events to find all tokenIds that ever existed."""
    latest = w3.eth.block_number
    token_ids = set()
    block = START_BLOCK

    print(f"Scanning IncreaseLiquidity events from block {block} to {latest}")

    while block < latest:
        end = min(block + CHUNK_SIZE, latest)
        try:
            logs = w3.eth.get_logs({
                "address": NPM_ADDRESS,
                "fromBlock": block,
                "toBlock": end,
                "topics": [INCREASE_LIQUIDITY_TOPIC]
            })
            for log in logs:
                # tokenId is the first indexed topic (topic[1])
                token_id = int(log["topics"][1].hex(), 16)
                token_ids.add(token_id)
        except Exception as e:
            print(f"  Error at block {block}: {e}, retrying with smaller chunk")
            CHUNK_SIZE_LOCAL = CHUNK_SIZE // 2
            end = min(block + CHUNK_SIZE_LOCAL, latest)
            continue

        if len(token_ids) % 5000 == 0 and len(token_ids) > 0:
            print(f"  Block {end}: {len(token_ids)} unique tokenIds so far")

        block = end + 1
        time.sleep(0.02)

    print(f"Found {len(token_ids)} unique tokenIds across all pools")
    return token_ids


def filter_pool_positions(token_ids: set) -> list:
    """Filter tokenIds to only those belonging to our USDC/WETH pool."""
    pool_positions = []
    total = len(token_ids)

    print(f"\nFiltering {total} tokenIds for USDC/WETH 5bps pool...")

    for i, token_id in enumerate(sorted(token_ids)):
        try:
            pos = npm.functions.positions(token_id).call()
            token0 = pos[2].lower()
            token1 = pos[3].lower()
            fee = pos[4]

            if token0 == USDC and token1 == WETH and fee == POOL_FEE:
                pool_positions.append({
                    "tokenId": token_id,
                    "tickLower": pos[5],
                    "tickUpper": pos[6],
                    "liquidity": pos[7],
                })
        except Exception:
            # Position may have been burned (NFT transferred to zero address)
            pass

        if (i + 1) % 1000 == 0:
            print(f"  Checked {i+1}/{total}, found {len(pool_positions)} pool positions")

        time.sleep(0.01)

    print(f"Found {len(pool_positions)} positions on USDC/WETH pool")
    return pool_positions


def main():
    token_ids = get_token_ids_from_events()
    positions = filter_pool_positions(token_ids)

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["tokenId", "tickLower", "tickUpper", "liquidity"])
        writer.writeheader()
        writer.writerows(positions)

    print(f"\nDone. {len(positions)} positions written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

**Step 2: Run the script**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research
source uhi8/bin/activate
python3 data/build_position_registry.py
```

Expected: This takes 30-60 minutes (scanning events + filtering positions). Creates `data/position_registry.csv` with ~5K-20K rows.

**IMPORTANT:** If event scanning is too slow, an alternative is to use The Graph V3 subgraph:
```bash
python3 -c "
# Quick alternative using subgraph
import requests, csv, time
url = 'https://gateway.thegraph.com/api/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV'
positions = []
skip = 0
while True:
    r = requests.post(url, json={'query': '{positions(first:1000, skip:' + str(skip) + ', where:{pool:\"0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640\"}) {id tickLower{tickIdx} tickUpper{tickIdx} liquidity}}'})
    data = r.json()['data']['positions']
    if not data: break
    positions.extend(data)
    skip += 1000
    time.sleep(0.5)
print(f'Found {len(positions)} positions')
"
```

**Step 3: Verify output**

```bash
head -5 data/position_registry.csv
wc -l data/position_registry.csv
```

Expected: Header + ~5K-20K rows. Each row has `tokenId,tickLower,tickUpper,liquidity`.

**Step 4: Commit**

```bash
git add data/build_position_registry.py data/position_registry.csv
git commit -m "feat: build NPM position registry for V3 USDC/WETH"
```

---

### Task 4: Write the FeeVariance Solidity library

**Files:**
- Create: `contracts/fee-variance/src/FeeVariance.sol`

**Step 1: Create the library**

Create `contracts/fee-variance/src/FeeVariance.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity >=0.7.5;
pragma abicoder v2;

import "@uniswap/v3-periphery/contracts/libraries/PositionValue.sol";
import "@uniswap/v3-periphery/contracts/interfaces/INonfungiblePositionManager.sol";
import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";
import "@uniswap/v3-core/contracts/libraries/FullMath.sol";
import "@uniswap/v3-core/contracts/libraries/FixedPoint128.sol";

library FeeVariance {
    uint256 internal constant Q128 = FixedPoint128.Q128;

    struct PositionData {
        uint256 feesUSD_X128;  // fees in USD terms, X128 fixed point
        uint256 liquidity;
    }

    /// @notice Compute FeeVarianceX128 for a set of positions at current block
    /// @param npm The NonfungiblePositionManager
    /// @param pool The Uniswap V3 pool
    /// @param tokenIds Array of NPM tokenIds to include
    /// @return varianceX128 Cross-sectional variance of (fee_share - liquidity_share), in X128
    /// @return numPositions Number of positions with nonzero liquidity
    function compute(
        INonfungiblePositionManager npm,
        IUniswapV3Pool pool,
        uint256[] memory tokenIds
    ) internal view returns (uint256 varianceX128, uint256 numPositions) {
        (uint160 sqrtPriceX96, , , , , , ) = pool.slot0();

        // Compute price as X128: price = (sqrtPriceX96)^2 / 2^192 * 2^128
        // = sqrtPriceX96^2 / 2^64
        // This gives token1/token0 price in X128
        uint256 priceX128 = FullMath.mulDiv(
            uint256(sqrtPriceX96) * uint256(sqrtPriceX96),
            Q128,
            1 << 192
        );

        // Pass 1: collect fees (USD) and liquidity for each active position
        PositionData[] memory positions = new PositionData[](tokenIds.length);
        uint256 totalFeesX128;
        uint256 totalLiquidity;
        uint256 count;

        for (uint256 i = 0; i < tokenIds.length; i++) {
            try npm.positions(tokenIds[i]) returns (
                uint96, address, address, address, uint24,
                int24, int24, uint128 liq,
                uint256, uint256, uint128, uint128
            ) {
                if (liq == 0) continue;

                // Get fees using PositionValue
                (uint256 fees0, uint256 fees1) = PositionValue.fees(npm, tokenIds[i]);

                // USD-denominate: for USDC/WETH pool, token0=USDC (6 dec), token1=WETH
                // fees0 is already in USDC units
                // fees1 in WETH, convert: fees1 * price (USDC per WETH)
                // priceX128 = USDC/WETH in X128
                // But token0Price from sqrtPrice gives token1/token0 ratio
                // For this pool: sqrtPrice encodes WETH/USDC
                // So priceX128 = WETH price in USDC terms = what we want for fees1->USD
                uint256 feesUSD_X128 = fees0 * Q128 + FullMath.mulDiv(fees1, priceX128, 1);

                positions[count] = PositionData({
                    feesUSD_X128: feesUSD_X128,
                    liquidity: uint256(liq)
                });
                totalFeesX128 += feesUSD_X128;
                totalLiquidity += uint256(liq);
                count++;
            } catch {
                continue;
            }
        }

        if (count < 2 || totalFeesX128 == 0 || totalLiquidity == 0) {
            return (0, count);
        }

        // Pass 2: compute variance of (fee_share - liq_share)
        // C_i = fees_i/totalFees - liq_i/totalLiq
        // Both computed in X128 for precision
        // Var = (1/N) * sum(C_i^2)   [note: sum(C_i) = 0 by construction]
        uint256 sumSquaresX128;

        for (uint256 i = 0; i < count; i++) {
            // fee_share in X128
            uint256 feeShareX128 = FullMath.mulDiv(
                positions[i].feesUSD_X128, Q128, totalFeesX128
            );
            // liq_share in X128
            uint256 liqShareX128 = FullMath.mulDiv(
                positions[i].liquidity, Q128, totalLiquidity
            );

            // C_i = feeShare - liqShare (can be negative)
            // We need signed arithmetic for the difference
            int256 ci;
            if (feeShareX128 >= liqShareX128) {
                ci = int256(feeShareX128 - liqShareX128);
            } else {
                ci = -int256(liqShareX128 - feeShareX128);
            }

            // ci^2 / Q128 to keep in X128 scale
            uint256 ciAbs = uint256(ci >= 0 ? ci : -ci);
            sumSquaresX128 += FullMath.mulDiv(ciAbs, ciAbs, Q128);
        }

        varianceX128 = sumSquaresX128 / count;
        numPositions = count;
    }
}
```

**Step 2: Verify it compiles**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research/contracts/fee-variance
forge build
```

Expected: Compiles. May need remapping adjustments — fix any import resolution errors.

**Step 3: Commit**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research
git add contracts/fee-variance/src/FeeVariance.sol
git commit -m "feat: add FeeVariance library — cross-sectional fee dispersion"
```

---

### Task 5: Write the Foundry script

**Files:**
- Create: `contracts/fee-variance/script/ComputeFeeVariance.s.sol`

**Step 1: Create the script**

Create `contracts/fee-variance/script/ComputeFeeVariance.s.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity >=0.7.5;
pragma abicoder v2;

import "forge-std/Script.sol";
import "../src/FeeVariance.sol";
import "@uniswap/v3-periphery/contracts/interfaces/INonfungiblePositionManager.sol";
import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";

contract ComputeFeeVariance is Script {
    INonfungiblePositionManager constant NPM =
        INonfungiblePositionManager(0xC36442b4a4522E871399CD717aBDD847Ab11FE88);
    IUniswapV3Pool constant POOL =
        IUniswapV3Pool(0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640);

    function run() external {
        // Read position registry via FFI
        string[] memory readCmd = new string[](3);
        readCmd[0] = "bash";
        readCmd[1] = "-c";
        readCmd[2] = "cut -d',' -f1 ../../data/position_registry.csv | tail -n +2";
        bytes memory tokenIdBytes = vm.ffi(readCmd);
        string memory tokenIdStr = string(tokenIdBytes);

        // Read daily blocks via FFI
        string[] memory blockCmd = new string[](3);
        blockCmd[0] = "bash";
        blockCmd[1] = "-c";
        blockCmd[2] = "cat ../../data/daily_blocks.csv | tail -n +2";
        bytes memory blockBytes = vm.ffi(blockCmd);
        string memory blockStr = string(blockBytes);

        // Write CSV header
        string[] memory headerCmd = new string[](3);
        headerCmd[0] = "bash";
        headerCmd[1] = "-c";
        headerCmd[2] = "echo 'date,block_number,fee_variance_x128,num_positions' > ../../data/fee_variance.csv";
        vm.ffi(headerCmd);

        // Parse and iterate would be done here
        // NOTE: Solidity string parsing is limited.
        // In practice, the daily loop is better driven from a Python wrapper
        // that calls `forge script` per day or passes block numbers as env vars.
    }
}
```

**IMPORTANT NOTE:** Parsing CSVs in Solidity is impractical. The real architecture should be:

**Step 2: Create a Python driver that calls Foundry per day**

Create `data/run_fee_variance.py`:

```python
"""
Driver script: for each day, calls a Foundry script at the target block
to compute FeeVarianceX128. Writes results to data/fee_variance.csv.
"""
import csv
import os
import subprocess
import json

DAILY_BLOCKS_PATH = "data/daily_blocks.csv"
POSITION_REGISTRY_PATH = "data/position_registry.csv"
OUTPUT_PATH = "data/fee_variance.csv"
FOUNDRY_DIR = "contracts/fee-variance"
RPC_URL = "https://eth-mainnet.g.alchemy.com/v2/fd_m2oikp78msnnQGxO6H"


def load_daily_blocks():
    with open(DAILY_BLOCKS_PATH) as f:
        reader = csv.DictReader(f)
        return [(row["date"], int(row["block_number"])) for row in reader]


def load_position_token_ids():
    with open(POSITION_REGISTRY_PATH) as f:
        reader = csv.DictReader(f)
        return [int(row["tokenId"]) for row in reader]


def compute_fee_variance_at_block(block_number: int, token_ids: list) -> dict:
    """
    Call Foundry script at a specific block to compute FeeVarianceX128.
    Uses forge script with --fork-block-number.
    """
    # Write tokenIds to a temp file for the script to read
    ids_str = ",".join(str(t) for t in token_ids)
    env = os.environ.copy()
    env["TOKEN_IDS"] = ids_str
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
        timeout=300
    )

    # Parse output for FeeVarianceX128 and numPositions
    # The script should emit these via console.log
    output = result.stdout + result.stderr
    # Parse from forge output
    # Look for lines like: FeeVariance: 12345, Positions: 2000
    variance = 0
    num_pos = 0
    for line in output.split("\n"):
        if "FeeVariance:" in line:
            variance = int(line.split("FeeVariance:")[1].strip().split(",")[0].strip())
        if "Positions:" in line:
            num_pos = int(line.split("Positions:")[1].strip())

    return {"fee_variance_x128": variance, "num_positions": num_pos}


def main():
    daily_blocks = load_daily_blocks()
    token_ids = load_position_token_ids()

    print(f"Computing FeeVariance for {len(daily_blocks)} days, {len(token_ids)} positions")

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "block_number", "fee_variance_x128", "num_positions"])
        writer.writeheader()

        for i, (date, block) in enumerate(daily_blocks):
            try:
                result = compute_fee_variance_at_block(block, token_ids)
                row = {
                    "date": date,
                    "block_number": block,
                    **result
                }
                writer.writerow(row)
                f.flush()

                if (i + 1) % 10 == 0:
                    print(f"  [{i+1}/{len(daily_blocks)}] {date} block={block} "
                          f"variance={result['fee_variance_x128']} "
                          f"positions={result['num_positions']}")
            except Exception as e:
                print(f"  ERROR at {date} block={block}: {e}")
                writer.writerow({
                    "date": date, "block_number": block,
                    "fee_variance_x128": 0, "num_positions": 0
                })
                f.flush()

    print(f"Done. Results written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

**Step 3: Update the Foundry script to read tokenIds from env and emit results**

Replace `contracts/fee-variance/script/ComputeFeeVariance.s.sol`:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity >=0.7.5;
pragma abicoder v2;

import "forge-std/Script.sol";
import "../src/FeeVariance.sol";
import "@uniswap/v3-periphery/contracts/interfaces/INonfungiblePositionManager.sol";
import "@uniswap/v3-core/contracts/interfaces/IUniswapV3Pool.sol";

contract ComputeFeeVariance is Script {
    INonfungiblePositionManager constant NPM =
        INonfungiblePositionManager(0xC36442b4a4522E871399CD717aBDD847Ab11FE88);
    IUniswapV3Pool constant POOL =
        IUniswapV3Pool(0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640);

    function run() external view {
        // Read tokenIds from FFI (position_registry.csv)
        string[] memory cmd = new string[](3);
        cmd[0] = "bash";
        cmd[1] = "-c";
        cmd[2] = "cut -d',' -f1 ../../data/position_registry.csv | tail -n +2 | tr '\\n' ','";
        bytes memory result = vm.ffi(cmd);

        // Parse comma-separated tokenIds
        uint256[] memory tokenIds = _parseTokenIds(string(result));

        // Compute fee variance at current fork block
        (uint256 varianceX128, uint256 numPositions) = FeeVariance.compute(
            NPM, POOL, tokenIds
        );

        // Emit results for the Python driver to parse
        console.log("FeeVariance:", varianceX128);
        console.log("Positions:", numPositions);
    }

    function _parseTokenIds(string memory csv) internal pure returns (uint256[] memory) {
        // Count commas to determine array size
        bytes memory b = bytes(csv);
        uint256 count = 0;
        for (uint256 i = 0; i < b.length; i++) {
            if (b[i] == ",") count++;
        }
        if (count == 0) return new uint256[](0);

        uint256[] memory ids = new uint256[](count);
        uint256 idx = 0;
        uint256 num = 0;

        for (uint256 i = 0; i < b.length; i++) {
            if (b[i] == ",") {
                if (num > 0) {
                    ids[idx++] = num;
                    num = 0;
                }
            } else if (uint8(b[i]) >= 48 && uint8(b[i]) <= 57) {
                num = num * 10 + (uint8(b[i]) - 48);
            }
        }
        // Last element if no trailing comma
        if (num > 0 && idx < count) {
            ids[idx++] = num;
        }

        // Trim array to actual count
        uint256[] memory trimmed = new uint256[](idx);
        for (uint256 i = 0; i < idx; i++) {
            trimmed[i] = ids[i];
        }
        return trimmed;
    }
}
```

**Step 4: Verify the script compiles**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research/contracts/fee-variance
forge build
```

Expected: Compiles without errors.

**Step 5: Test on a single block**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research/contracts/fee-variance
source ../../.env 2>/dev/null || true
forge script script/ComputeFeeVariance.s.sol \
  --fork-url https://eth-mainnet.g.alchemy.com/v2/fd_m2oikp78msnnQGxO6H \
  --fork-block-number 18000000 \
  --ffi \
  -vvv 2>&1 | tail -20
```

Expected: Outputs `FeeVariance: <some number>` and `Positions: <some number>`. May take 30-120 seconds for a single block due to the number of position queries.

**Step 6: Commit**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research
git add contracts/fee-variance/script/ComputeFeeVariance.s.sol data/run_fee_variance.py
git commit -m "feat: add FeeVariance Foundry script and Python driver"
```

---

### Task 6: Run full fee variance computation

**Files:**
- Read-only: `data/daily_blocks.csv`, `data/position_registry.csv`
- Output: `data/fee_variance.csv`

**Step 1: Run the driver**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research
source uhi8/bin/activate
python3 data/run_fee_variance.py 2>&1 | tee data/fee_variance_log.txt
```

Expected: Runs for 1-3 hours. Outputs progress every 10 days. Creates `data/fee_variance.csv`.

**STOP condition:** If more than 10% of days produce errors or zero variance, investigate. Common issues:
- RPC rate limiting → add `time.sleep()` between calls
- Position not found at historical block → filter positions by `blockCreated <= target_block`
- Memory limits → reduce position batch size

**Step 2: Verify output**

```bash
head -5 data/fee_variance.csv
wc -l data/fee_variance.csv
python3 -c "
import pandas as pd
df = pd.read_csv('data/fee_variance.csv')
print(df.describe())
print(f'Zero variance days: {(df.fee_variance_x128 == 0).sum()}')
print(f'Non-zero days: {(df.fee_variance_x128 > 0).sum()}')
"
```

Expected: ~1,760 rows. Most days have nonzero variance. The variance values should show meaningful variation over time.

**Step 3: Commit**

```bash
git add data/fee_variance.csv
git commit -m "data: add computed daily FeeVarianceX128 time series"
```

---

### Task 7: Integrate fee variance into econometrics pipeline

**Files:**
- Modify: `data/DataHandler.py` (add `load_fee_variance`, `fee_variance` functions)
- Modify: `notebooks/econometrics.ipynb` (change endog to fee variance)
- Read-only: `data/fee_variance.csv`

**Step 1: Add accessor functions to DataHandler**

In `data/DataHandler.py`, after the `liquidity()` function (line ~148), add:

```python
def load_fee_variance(path: str = None) -> pd.DataFrame:
    """Load precomputed daily FeeVarianceX128 time series."""
    import os
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "fee_variance.csv")
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    return df


def fee_variance(fv_data: pd.DataFrame) -> TimeSeries:
    """Get FeeVarianceX128 time series."""
    return fv_data["fee_variance_x128"]
```

**Step 2: Update econometrics notebook cell 2 (imports)**

Add to the import line:

```python
from data.DataHandler import (
    PoolEntryData, delta, tvlUSD, priceUSD, volumeUSD, feesUSD,
    div, lagged, txCount, normalize, liquidity,
    load_fee_variance, fee_variance
)
```

**Step 3: Update econometrics notebook cell 4 (Stage 1 estimation)**

Change the `endog` variable:

```python
# ── Stage 1: Congestion Index ΔI_t ─────────────────────────────
# Structural: use cross-sectional fee dispersion (FeeVarianceX128)
fv_data = load_fee_variance()
endog = div(delta(fee_variance(fv_data)), lagged(fee_variance(fv_data)))
```

**Step 4: Run the notebook**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research
source uhi8/bin/activate
jupyter nbconvert --to notebook --execute notebooks/econometrics.ipynb --output econometrics_executed.ipynb --ExecutePreprocessor.timeout=300 2>&1 | tail -20
```

**STOP condition:** If R² is not meaningfully higher than 5.16%, or if δ₂ is not significant (p > 0.05), STOP and report. Check if the fee variance time series needs different preprocessing (log transform, detrending, etc.).

Expected: R² significantly higher than 5.2%. δ₂ negative and significant.

**Step 5: Record new metrics**

From the executed output, record:
- γ (AR persistence): should be < 1 (stationary)
- δ₂ (congestion impact): should be negative
- p-value: should be < 0.05
- R² (Stage 2b): should be >> 5.16%

**Step 6: Clean up and commit**

```bash
rm -f notebooks/econometrics_executed.ipynb
git add data/DataHandler.py notebooks/econometrics.ipynb
git commit -m "feat(econometrics): use structural FeeVarianceX128 as congestion variable"
```

---

### Task 8: Update backtest with new congestion variable

**Files:**
- Modify: `notebooks/backtest.ipynb` (cells 1, 2)
- Read-only: `data/fee_variance.csv`, `notes/payoff_notes.md`

**Step 1: Update cell 1 imports and Stage 1**

Add `load_fee_variance, fee_variance` to imports. Change endog:

```python
fv_data = load_fee_variance()
endog = div(delta(fee_variance(fv_data)), lagged(fee_variance(fv_data)))
```

**Step 2: Update cell 2 δ₂**

Replace `DELTA_2 = -0.002` with the new δ₂ value from Task 7.

**Step 3: Run the full notebook**

```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research
source uhi8/bin/activate
jupyter nbconvert --to notebook --execute notebooks/backtest.ipynb --output backtest_executed.ipynb --ExecutePreprocessor.timeout=300 2>&1 | tail -20
```

**STOP condition:** If CVaR 1% improvement is negative (hedge makes tail risk WORSE), STOP immediately. Do not commit.

Expected:
- Variance reduction > 5%
- CVaR 1% improvement POSITIVE
- High congestion regime shows meaningful variance reduction

**Step 4: Clean up and commit**

```bash
rm -f notebooks/backtest_executed.ipynb
git add notebooks/backtest.ipynb
git commit -m "feat(backtest): use structural FeeVarianceX128 for congestion hedge"
```
