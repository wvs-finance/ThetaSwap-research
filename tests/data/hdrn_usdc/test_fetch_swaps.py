"""Tests for swap fetcher — uses live subgraph (integration test)."""
from data.hdrn_usdc.fetch_swaps import fetch_swap_page, SWAP_QUERY
from data.hdrn_usdc.types import RawSwap, HDRN_USDC_POOL
from data.UniswapClient import UniswapClient, v3


def test_fetch_swap_page_returns_raw_swaps():
    client = UniswapClient(v3())
    swaps = fetch_swap_page(client, HDRN_USDC_POOL, last_id="")
    assert len(swaps) > 0
    assert isinstance(swaps[0], RawSwap)
    assert swaps[0].pool_liquidity > 0
    assert swaps[0].fee_growth_global0_x128 >= 0


def test_fetch_swap_page_pagination():
    client = UniswapClient(v3())
    page1 = fetch_swap_page(client, HDRN_USDC_POOL, last_id="")
    assert len(page1) > 0
    page2 = fetch_swap_page(client, HDRN_USDC_POOL, last_id=page1[-1].id)
    assert len(page2) > 0
    assert page2[0].id != page1[0].id
