"""Tests for sampling strategy — pure functions."""
from data.hdrn_usdc.sampling import (
    filter_active_period,
    compute_swap_density,
    ActivePeriod,
)
from data.hdrn_usdc.types import RawSwap, Q128


def _make_swap(id: str, timestamp: int) -> RawSwap:
    return RawSwap(
        id=id, timestamp=timestamp, block_number=100,
        tick=0, sqrt_price_x96=2**96,
        amount0=1.0, amount1=1.0, amount_usd=100.0,
        gas_price=30_000_000_000, pool_liquidity=10**18,
        fee_growth_global0_x128=Q128, fee_growth_global1_x128=Q128,
    )


def test_filter_active_period_drops_sparse():
    # 10 swaps in Q1, 1 swap in Q2
    q1_swaps = [_make_swap(f"0x{i}", 1640000000 + i * 3600) for i in range(10)]
    q2_swaps = [_make_swap("0xsparse", 1650000000)]
    all_swaps = q1_swaps + q2_swaps
    period = ActivePeriod(min_swaps_per_quarter=5)
    filtered = filter_active_period(all_swaps, period)
    assert len(filtered) == 10  # only Q1 retained


def test_compute_swap_density():
    swaps = [_make_swap(f"0x{i}", 1640000000 + i * 86400) for i in range(100)]
    density = compute_swap_density(swaps, window_days=30)
    assert len(density) > 0
    assert all(d >= 0 for _, d in density)
