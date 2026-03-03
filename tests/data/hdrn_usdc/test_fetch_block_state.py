"""Integration test for block-level RPC fetcher.

Fetches 1 recent block from mainnet to verify non-zero liquidity.
Requires ETH_RPC_URL or defaults to Alchemy endpoint.
"""
from __future__ import annotations

import os
import tempfile

import pytest

from data.hdrn_usdc.fetch_block_state import (
    fetch_block_states,
    load_block_states,
    _make_web3,
)
from data.hdrn_usdc.types import HDRN_USDC_POOL


@pytest.mark.skipif(
    os.environ.get("SKIP_RPC_TESTS", "0") == "1",
    reason="RPC tests disabled via SKIP_RPC_TESTS=1",
)
def test_fetch_single_block_returns_nonzero_liquidity() -> None:
    """Fetch state at a known recent block and verify non-zero liquidity."""
    # Block 19_000_000 is ~Jan 2024, well after pool creation and Multicall3
    test_block = 19_000_000

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        fetch_block_states(
            blocks=[test_block],
            pool_address=HDRN_USDC_POOL,
            output_path=tmp_path,
        )

        states = load_block_states(tmp_path)
        assert test_block in states, f"Block {test_block} not in results"

        state = states[test_block]
        assert state.block_number == test_block
        assert state.liquidity > 0, "Liquidity should be non-zero"
        assert state.fee_growth_global0_x128 >= 0
        assert state.fee_growth_global1_x128 >= 0
    finally:
        os.unlink(tmp_path)


@pytest.mark.skipif(
    os.environ.get("SKIP_RPC_TESTS", "0") == "1",
    reason="RPC tests disabled via SKIP_RPC_TESTS=1",
)
def test_resume_skips_completed_blocks() -> None:
    """Verify resume support: fetching already-completed blocks is a no-op."""
    test_block = 19_000_000

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # First fetch
        fetch_block_states(
            blocks=[test_block],
            pool_address=HDRN_USDC_POOL,
            output_path=tmp_path,
        )

        states_1 = load_block_states(tmp_path)
        assert len(states_1) == 1

        # Second fetch — same block, should skip
        fetch_block_states(
            blocks=[test_block],
            pool_address=HDRN_USDC_POOL,
            output_path=tmp_path,
        )

        states_2 = load_block_states(tmp_path)
        # Should still be exactly 1 row, not duplicated
        assert len(states_2) == 1
        assert states_2[test_block].liquidity == states_1[test_block].liquidity
    finally:
        os.unlink(tmp_path)


def test_block_state_type_is_frozen() -> None:
    """BlockState dataclass should be immutable."""
    from dataclasses import FrozenInstanceError
    from data.hdrn_usdc.types import BlockState

    bs = BlockState(
        block_number=100,
        liquidity=10**18,
        fee_growth_global0_x128=0,
        fee_growth_global1_x128=0,
    )
    with pytest.raises(FrozenInstanceError):
        bs.liquidity = 0  # type: ignore[misc]


def test_to_observations_block_level_basic() -> None:
    """Block-level transform produces correct observation count and values."""
    from data.hdrn_usdc.types import BlockState, RawSwap, Q128
    from data.hdrn_usdc.transform import to_observations_block_level

    bs1 = BlockState(block_number=100, liquidity=10**18,
                     fee_growth_global0_x128=10 * Q128,
                     fee_growth_global1_x128=5 * Q128)
    bs2 = BlockState(block_number=101, liquidity=2 * 10**18,
                     fee_growth_global0_x128=15 * Q128,
                     fee_growth_global1_x128=7 * Q128)
    bs3 = BlockState(block_number=102, liquidity=3 * 10**18,
                     fee_growth_global0_x128=20 * Q128,
                     fee_growth_global1_x128=9 * Q128)

    block_states = {bs.block_number: bs for bs in [bs1, bs2, bs3]}

    swaps = [
        RawSwap(id="0x1", timestamp=1000, block_number=100, tick=0,
                sqrt_price_x96=2**96, amount0=1.0, amount1=1.0,
                amount_usd=100.0, gas_price=30_000_000_000,
                pool_liquidity=10**18,
                fee_growth_global0_x128=10 * Q128,
                fee_growth_global1_x128=5 * Q128),
        RawSwap(id="0x2", timestamp=2000, block_number=101, tick=0,
                sqrt_price_x96=2**96, amount0=1.0, amount1=1.0,
                amount_usd=200.0, gas_price=30_000_000_000,
                pool_liquidity=2 * 10**18,
                fee_growth_global0_x128=15 * Q128,
                fee_growth_global1_x128=7 * Q128),
        RawSwap(id="0x3", timestamp=3000, block_number=102, tick=0,
                sqrt_price_x96=2**96, amount0=1.0, amount1=1.0,
                amount_usd=300.0, gas_price=30_000_000_000,
                pool_liquidity=3 * 10**18,
                fee_growth_global0_x128=20 * Q128,
                fee_growth_global1_x128=9 * Q128),
    ]

    obs = to_observations_block_level(swaps, block_states)
    assert len(obs) == 2  # N-1 from 3 swaps
    assert obs[0].pi_n > 0  # fee growth increased
    assert obs[0].dlog_l_n > 0  # liquidity doubled
    assert obs[0].l_active_n == float(2 * 10**18)  # from block 101


def test_to_observations_block_level_drops_missing_blocks() -> None:
    """Swaps without matching block states are dropped."""
    from data.hdrn_usdc.types import BlockState, RawSwap, Q128
    from data.hdrn_usdc.transform import to_observations_block_level

    bs1 = BlockState(block_number=100, liquidity=10**18,
                     fee_growth_global0_x128=10 * Q128,
                     fee_growth_global1_x128=5 * Q128)
    # Block 101 missing — swap at block 101 should be dropped
    bs3 = BlockState(block_number=102, liquidity=3 * 10**18,
                     fee_growth_global0_x128=20 * Q128,
                     fee_growth_global1_x128=9 * Q128)

    block_states = {bs.block_number: bs for bs in [bs1, bs3]}

    swaps = [
        RawSwap(id="0x1", timestamp=1000, block_number=100, tick=0,
                sqrt_price_x96=2**96, amount0=1.0, amount1=1.0,
                amount_usd=100.0, gas_price=30_000_000_000,
                pool_liquidity=10**18,
                fee_growth_global0_x128=10 * Q128,
                fee_growth_global1_x128=5 * Q128),
        RawSwap(id="0x2", timestamp=2000, block_number=101, tick=0,
                sqrt_price_x96=2**96, amount0=1.0, amount1=1.0,
                amount_usd=200.0, gas_price=30_000_000_000,
                pool_liquidity=2 * 10**18,
                fee_growth_global0_x128=15 * Q128,
                fee_growth_global1_x128=7 * Q128),
        RawSwap(id="0x3", timestamp=3000, block_number=102, tick=0,
                sqrt_price_x96=2**96, amount0=1.0, amount1=1.0,
                amount_usd=300.0, gas_price=30_000_000_000,
                pool_liquidity=3 * 10**18,
                fee_growth_global0_x128=20 * Q128,
                fee_growth_global1_x128=9 * Q128),
    ]

    obs = to_observations_block_level(swaps, block_states)
    # Only blocks 100 and 102 matched → 1 observation
    assert len(obs) == 1
