"""Tests for swap transformation — pure functions, no network."""
from data.hdrn_usdc.transform import to_observations, compute_pi_n
from data.hdrn_usdc.types import RawSwap, SwapObservation, Q128
import math


def _make_swap(
    id: str = "0x1",
    timestamp: int = 1000,
    block_number: int = 100,
    tick: int = 0,
    sqrt_price_x96: int = 2**96,
    amount_usd: float = 100.0,
    gas_price: int = 30_000_000_000,
    pool_liquidity: int = 10**18,
    fg0: int = 10 * Q128,
    fg1: int = 5 * Q128,
) -> RawSwap:
    return RawSwap(
        id=id, timestamp=timestamp, block_number=block_number,
        tick=tick, sqrt_price_x96=sqrt_price_x96,
        amount0=1.0, amount1=1.0, amount_usd=amount_usd,
        gas_price=gas_price, pool_liquidity=pool_liquidity,
        fee_growth_global0_x128=fg0, fee_growth_global1_x128=fg1,
    )


def test_compute_pi_n_positive_fee_growth():
    prev = _make_swap(fg0=10 * Q128)
    curr = _make_swap(fg0=15 * Q128, pool_liquidity=10**18)
    pi = compute_pi_n(
        curr.fee_growth_global0_x128, curr.fee_growth_global1_x128,
        prev.fee_growth_global0_x128, prev.fee_growth_global1_x128,
    )
    assert pi > 0


def test_to_observations_length():
    swaps = [_make_swap(id=f"0x{i}", fg0=i * Q128) for i in range(5)]
    obs = to_observations(swaps)
    # First swap has no predecessor, so N-1 observations
    assert len(obs) == 4


def test_to_observations_dlog_l_sign():
    s1 = _make_swap(id="0x1", pool_liquidity=10**18)
    s2 = _make_swap(id="0x2", pool_liquidity=2 * 10**18)
    obs = to_observations([s1, s2])
    assert obs[0].dlog_l_n > 0  # liquidity doubled


def test_to_observations_gas_in_gwei():
    s1 = _make_swap(id="0x1", gas_price=30_000_000_000)
    s2 = _make_swap(id="0x2", gas_price=30_000_000_000)
    obs = to_observations([s1, s2])
    assert abs(obs[0].gas_n - 30.0) < 0.01  # 30 Gwei
