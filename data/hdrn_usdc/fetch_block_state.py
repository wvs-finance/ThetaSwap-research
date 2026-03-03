"""Fetch pool state (liquidity, feeGrowthGlobal) at specific blocks via RPC.

Combines Multicall3 (3 reads in 1 eth_call = 26 CU) with JSON-RPC batch
requests (50 blocks per HTTP POST). This gives ~1.9M CU for 74K blocks,
within Alchemy free tier (500 CU/s, 30M CU/month).

For pre-Multicall3 blocks (<14,353,601), falls back to individual eth_call.

CSV persistence with resume: saves after each batch, skips already-fetched
blocks on restart.
"""
from __future__ import annotations

import csv
import os
import time
from typing import Final, Sequence

import requests as http_requests
from dotenv import load_dotenv
from eth_abi import decode, encode
from web3 import Web3

from data.hdrn_usdc.types import BlockNumber, BlockState, FeeGrowthX128, Liquidity

load_dotenv()

# --- Constants ---

RPC_URL: Final = os.environ["ETH_RPC_URL"]

MULTICALL3: Final = "0xcA11bde05977b3631167028862bE2a173976CA11"
MULTICALL3_DEPLOY_BLOCK: Final[BlockNumber] = 14_353_601

# Function selectors (4-byte keccak prefixes)
LIQUIDITY_SIG: Final = Web3.keccak(text="liquidity()")[:4]
FEE_GROWTH0_SIG: Final = Web3.keccak(text="feeGrowthGlobal0X128()")[:4]
FEE_GROWTH1_SIG: Final = Web3.keccak(text="feeGrowthGlobal1X128()")[:4]
AGGREGATE3_SIG: Final = Web3.keccak(text="aggregate3((address,bool,bytes)[])")[:4]

# Rate limiting — 500 CU/s free tier, 26 CU per eth_call
# 50 blocks/batch = 50 × 26 CU = 1,300 CU → need 2.6s between batches
BLOCKS_PER_BATCH: Final = 50
BATCH_DELAY_SEC: Final = 2.8  # slightly above 1300/500 for safety margin
INDIVIDUAL_DELAY_SEC: Final = 0.06

# CSV schema
BLOCK_STATE_FIELDNAMES: Final = [
    "block_number", "liquidity",
    "fee_growth_global0_x128", "fee_growth_global1_x128",
]

# Reusable HTTP session
_SESSION: http_requests.Session | None = None


def _get_session() -> http_requests.Session:
    """Get or create a reusable HTTP session."""
    global _SESSION
    if _SESSION is None:
        _SESSION = http_requests.Session()
        _SESSION.headers.update({"Content-Type": "application/json"})
    return _SESSION


# --- Multicall3 encoding ---

def _encode_multicall3(pool_address: str) -> bytes:
    """Pre-encode the Multicall3 aggregate3 calldata for 3 pool reads.

    Returns the full calldata bytes to pass as `data` to eth_call.
    """
    addr = Web3.to_checksum_address(pool_address)
    encoded_calls = [
        (addr, True, LIQUIDITY_SIG),
        (addr, True, FEE_GROWTH0_SIG),
        (addr, True, FEE_GROWTH1_SIG),
    ]
    return AGGREGATE3_SIG + encode(
        ["(address,bool,bytes)[]"],
        [encoded_calls],
    )


def _parse_multicall3_response(
    block_num: BlockNumber,
    hex_result: str,
) -> BlockState | None:
    """Parse a Multicall3 aggregate3 response into a BlockState."""
    try:
        raw_bytes = bytes.fromhex(hex_result[2:])  # strip 0x
        decoded = decode(["(bool,bytes)[]"], raw_bytes)[0]
        if len(decoded) != 3:
            return None
        for success, data in decoded:
            if not success or len(data) < 32:
                return None

        liquidity: Liquidity = decode(["uint128"], decoded[0][1])[0]
        fg0: FeeGrowthX128 = decode(["uint256"], decoded[1][1])[0]
        fg1: FeeGrowthX128 = decode(["uint256"], decoded[2][1])[0]
        return BlockState(
            block_number=block_num,
            liquidity=liquidity,
            fee_growth_global0_x128=fg0,
            fee_growth_global1_x128=fg1,
        )
    except Exception:
        return None


# --- JSON-RPC batch ---

def _send_batch(payload: list[dict]) -> dict[int, str | None]:
    """Send a JSON-RPC batch request. Returns {id: result_hex_or_None}."""
    session = _get_session()
    for attempt in range(5):
        try:
            resp = session.post(RPC_URL, json=payload, timeout=120)
            if resp.status_code == 429:
                wait = 3.0 * (attempt + 1)
                print(f"  429 rate-limited, waiting {wait:.0f}s...", flush=True)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            results = resp.json()
            if isinstance(results, list):
                return {
                    r.get("id"): r.get("result")
                    for r in results
                }
            return {results.get("id"): results.get("result")}
        except Exception as e:
            if attempt < 4:
                time.sleep(2.0 * (attempt + 1))
            else:
                print(f"  Batch failed after 5 attempts: {e}", flush=True)
    return {}


def _fetch_batch_multicall3(
    blocks: Sequence[BlockNumber],
    multicall_data_hex: str,
) -> list[BlockState]:
    """Fetch pool state for multiple blocks via JSON-RPC batch of Multicall3 calls.

    Each block gets one eth_call to Multicall3 (26 CU), all in one HTTP POST.
    """
    payload = [
        {
            "jsonrpc": "2.0",
            "id": i,
            "method": "eth_call",
            "params": [
                {"to": MULTICALL3, "data": multicall_data_hex},
                hex(block_num),
            ],
        }
        for i, block_num in enumerate(blocks)
    ]

    results = _send_batch(payload)
    if not results:
        return []

    states: list[BlockState] = []
    for i, block_num in enumerate(blocks):
        hex_result = results.get(i)
        if hex_result is None:
            continue
        state = _parse_multicall3_response(block_num, hex_result)
        if state is not None:
            states.append(state)

    return states


# --- Individual call fallback (pre-Multicall3) ---

def _make_web3() -> Web3:
    """Create Web3 instance (IO boundary)."""
    return Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 120}))


def _fetch_individual_blocks(
    w3: Web3,
    blocks: Sequence[BlockNumber],
    pool_address: str,
    output_path: str,
) -> None:
    """Fetch pre-Multicall3 blocks one at a time via eth_call."""
    addr = Web3.to_checksum_address(pool_address)
    batch_buf: list[BlockState] = []

    for i, block_num in enumerate(blocks):
        results: list[bytes] = []
        for sig in [LIQUIDITY_SIG, FEE_GROWTH0_SIG, FEE_GROWTH1_SIG]:
            for attempt in range(4):
                try:
                    raw = w3.eth.call(
                        {"to": addr, "data": sig},
                        block_identifier=block_num,
                    )
                    results.append(raw)
                    break
                except Exception as e:
                    if "429" in str(e) or "Too Many" in str(e):
                        time.sleep(2.0 * (attempt + 1))
                    else:
                        results.append(b"")
                        break
            time.sleep(INDIVIDUAL_DELAY_SEC)

        if len(results) == 3 and all(len(r) >= 32 for r in results):
            batch_buf.append(BlockState(
                block_number=block_num,
                liquidity=decode(["uint128"], results[0])[0],
                fee_growth_global0_x128=decode(["uint256"], results[1])[0],
                fee_growth_global1_x128=decode(["uint256"], results[2])[0],
            ))

        if len(batch_buf) >= 100:
            _append_block_states(batch_buf, output_path)
            batch_buf = []

        if (i + 1) % 500 == 0:
            print(f"  Individual: {i + 1}/{len(blocks)}", flush=True)

    if batch_buf:
        _append_block_states(batch_buf, output_path)


# --- CSV persistence ---

def _load_completed_blocks(path: str) -> set[BlockNumber]:
    """Load already-fetched block numbers from CSV for resume."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return set()
    with open(path) as f:
        return {int(row["block_number"]) for row in csv.DictReader(f)}


def _append_block_states(states: Sequence[BlockState], path: str) -> None:
    """Append block states to CSV, creating header if needed."""
    file_exists = os.path.exists(path) and os.path.getsize(path) > 0
    mode = "a" if file_exists else "w"
    with open(path, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BLOCK_STATE_FIELDNAMES)
        if mode == "w":
            writer.writeheader()
        for s in states:
            writer.writerow({
                "block_number": str(s.block_number),
                "liquidity": str(s.liquidity),
                "fee_growth_global0_x128": str(s.fee_growth_global0_x128),
                "fee_growth_global1_x128": str(s.fee_growth_global1_x128),
            })
        f.flush()


def load_block_states(path: str) -> dict[BlockNumber, BlockState]:
    """Load all block states from CSV into a dict keyed by block number."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return {}
    with open(path) as f:
        return {
            int(row["block_number"]): BlockState(
                block_number=int(row["block_number"]),
                liquidity=int(row["liquidity"]),
                fee_growth_global0_x128=int(row["fee_growth_global0_x128"]),
                fee_growth_global1_x128=int(row["fee_growth_global1_x128"]),
            )
            for row in csv.DictReader(f)
        }


# --- Main fetcher ---

def fetch_block_states(
    blocks: Sequence[int],
    pool_address: str,
    output_path: str,
    blocks_per_batch: int = BLOCKS_PER_BATCH,
) -> None:
    """Fetch pool state at each block via Multicall3 + JSON-RPC batching.

    Post-Multicall3 blocks: 50 blocks per HTTP POST (each is one Multicall3
    eth_call at 26 CU). Paced at 2.8s/batch to stay under 500 CU/s.

    Pre-Multicall3 blocks: individual eth_call with retry.

    Saves to CSV after each batch for resume support.
    """
    completed = _load_completed_blocks(output_path)
    remaining = sorted(b for b in blocks if b not in completed)

    if not remaining:
        print("All blocks already fetched.", flush=True)
        return

    print(f"Fetching {len(remaining)} blocks ({len(completed)} already done)", flush=True)

    pre_mc = [b for b in remaining if b < MULTICALL3_DEPLOY_BLOCK]
    post_mc = [b for b in remaining if b >= MULTICALL3_DEPLOY_BLOCK]

    # Pre-encode Multicall3 calldata (same for every block)
    multicall_data_hex = "0x" + _encode_multicall3(pool_address).hex()

    # --- Post-Multicall3: JSON-RPC batch of Multicall3 calls ---
    total_batches = (len(post_mc) + blocks_per_batch - 1) // blocks_per_batch
    t0 = time.time()

    for batch_idx in range(0, len(post_mc), blocks_per_batch):
        batch_blocks = post_mc[batch_idx : batch_idx + blocks_per_batch]
        batch_states = _fetch_batch_multicall3(batch_blocks, multicall_data_hex)

        if batch_states:
            _append_block_states(batch_states, output_path)

        batch_num = batch_idx // blocks_per_batch + 1
        if batch_num % 50 == 0 or batch_num == 1 or batch_num == total_batches:
            elapsed = time.time() - t0
            rate = batch_num / elapsed if elapsed > 0 else 0
            eta = (total_batches - batch_num) / rate if rate > 0 else 0
            print(
                f"  Batch {batch_num}/{total_batches}: "
                f"{len(batch_states)}/{len(batch_blocks)} ok  "
                f"({elapsed:.0f}s elapsed, ~{eta:.0f}s remaining)",
                flush=True,
            )

        time.sleep(BATCH_DELAY_SEC)

    # --- Pre-Multicall3: individual calls ---
    if pre_mc:
        print(f"Fetching {len(pre_mc)} pre-Multicall3 blocks individually...", flush=True)
        w3 = _make_web3()
        _fetch_individual_blocks(w3, pre_mc, pool_address, output_path)

    total = len(_load_completed_blocks(output_path))
    print(f"Done. {total} block states saved to {output_path}", flush=True)
