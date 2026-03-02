"""Tests for CSV persistence — uses tmp_path fixture."""
from data.hdrn_usdc.persist import save_raw_swaps, load_raw_swaps, last_swap_id
from data.hdrn_usdc.types import RawSwap, Q128


def _make_swap(id: str) -> RawSwap:
    return RawSwap(
        id=id, timestamp=1000, block_number=100, tick=0,
        sqrt_price_x96=2**96, amount0=1.0, amount1=1.0,
        amount_usd=100.0, gas_price=30_000_000_000,
        pool_liquidity=10**18,
        fee_growth_global0_x128=Q128,
        fee_growth_global1_x128=Q128,
    )


def test_round_trip(tmp_path):
    path = str(tmp_path / "swaps.csv")
    swaps = [_make_swap(f"0x{i}") for i in range(5)]
    save_raw_swaps(swaps, path)
    loaded = load_raw_swaps(path)
    assert len(loaded) == 5
    assert loaded[0].id == swaps[0].id
    assert loaded[0].pool_liquidity == swaps[0].pool_liquidity


def test_resume_from_last_id(tmp_path):
    path = str(tmp_path / "swaps.csv")
    swaps = [_make_swap(f"0x{i}") for i in range(3)]
    save_raw_swaps(swaps, path)
    assert last_swap_id(path) == "0x2"


def test_append_mode(tmp_path):
    path = str(tmp_path / "swaps.csv")
    batch1 = [_make_swap(f"0x{i}") for i in range(3)]
    save_raw_swaps(batch1, path)
    batch2 = [_make_swap(f"0x{i}") for i in range(3, 6)]
    save_raw_swaps(batch2, path, append=True)
    loaded = load_raw_swaps(path)
    assert len(loaded) == 6
