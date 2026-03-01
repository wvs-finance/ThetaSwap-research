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
