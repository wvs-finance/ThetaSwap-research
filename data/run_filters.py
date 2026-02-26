#!/usr/bin/env python3
"""
V4Client Filter Demo - Uniswap V4 Pool Screening

Usage:
    source uhi8/bin/activate
    python data/run_filters.py

Filters:
    1. Stable/Stable pairs (USDC, USDT, DAI)
    2. High TVL threshold
    3. High turnover ratio (Volume/TVL)
    4. High mint/burn activity (txCount)
    5. Low fee tier
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.V4Client import V4Client, create_client


def main():
    client = create_client()
    
    print("=" * 70)
    print("Uniswap V4 Pool Filter Analysis")
    print("=" * 70)
    print()
    
    # Get ETH price
    bundle = client.get_bundle()
    eth_price = float(bundle.get("ethPriceUSD", 0)) if bundle else 0
    print(f"ETH Price: ${eth_price:,.2f}")
    print()
    
    # Overview
    print("Pool Overview (first 200 pools)")
    print("-" * 70)
    pools = client.get_pools(first=200)
    pools_with_tvl = [p for p in pools if p.get("_estimatedTvlUSD", 0) > 0]
    print(f"  Total pools: {len(pools)}")
    print(f"  Pools with TVL > $0: {len(pools_with_tvl)}")
    print()
    
    # Top pools by TVL
    print("Top 10 Pools by TVL")
    print("-" * 70)
    sorted_by_tvl = sorted(pools, key=lambda p: p.get("_estimatedTvlUSD", 0), reverse=True)
    for i, p in enumerate(sorted_by_tvl[:10], 1):
        t0 = p.get("token0", {}).get("symbol", "N/A")
        t1 = p.get("token1", {}).get("symbol", "N/A")
        tvl = p.get("_estimatedTvlUSD", 0)
        fee = p.get("feeTier", "N/A")
        tx = int(p.get("txCount") or 0)
        print(f"  {i}. {t0}/{t1}")
        print(f"     TVL: ${tvl:,.2f} | Fee: {fee}bps | Tx: {tx:,}")
    print()
    
    # Filter 1: Stable/Stable
    print("Filter 1: Stable/Stable Pairs")
    print("-" * 70)
    stable_pools = client.get_stable_stable_pools(first=100)
    print(f"  Found: {len(stable_pools)} pools")
    for p in stable_pools[:5]:
        t0 = p.get("token0", {}).get("symbol", "N/A")
        t1 = p.get("token1", {}).get("symbol", "N/A")
        tvl = p.get("_estimatedTvlUSD", 0)
        print(f"    {t0}/{t1} - TVL: ${tvl:,.2f}")
    if not stable_pools:
        print("  (No stable/stable pools with current data)")
    print()
    
    # Filter 2: High TVL
    print("Filter 2: High TVL Pools (>$1,000)")
    print("-" * 70)
    high_tvl = client.get_high_tvl_pools(min_tvl_usd=1_000, first=100)
    print(f"  Found: {len(high_tvl)} pools")
    for p in high_tvl[:5]:
        t0 = p.get("token0", {}).get("symbol", "N/A")
        t1 = p.get("token1", {}).get("symbol", "N/A")
        tvl = p.get("_estimatedTvlUSD", 0)
        print(f"    {t0}/{t1} - TVL: ${tvl:,.2f}")
    print()
    
    # Filter 3: High Turnover
    print("Filter 3: High Turnover Ratio (>0.1/day)")
    print("-" * 70)
    high_turnover = client.get_high_turnover_pools(min_turnover=0.1, first=100)
    print(f"  Found: {len(high_turnover)} pools")
    for p in high_turnover[:5]:
        t0 = p.get("token0", {}).get("symbol", "N/A")
        t1 = p.get("token1", {}).get("symbol", "N/A")
        turnover = p.get("turnover_ratio", 0)
        print(f"    {t0}/{t1} - Turnover: {turnover:.3f}/day")
    print()
    
    # Filter 4: High Activity
    print("Filter 4: High Activity (Top 10% by txCount)")
    print("-" * 70)
    high_activity = client.get_high_activity_pools(top_percentile=0.1, first=100)
    print(f"  Found: {len(high_activity)} pools")
    for p in high_activity[:5]:
        t0 = p.get("token0", {}).get("symbol", "N/A")
        t1 = p.get("token1", {}).get("symbol", "N/A")
        tx = int(p.get("txCount") or 0)
        tvl = p.get("_estimatedTvlUSD", 0)
        print(f"    {t0}/{t1} - Tx: {tx:,} | TVL: ${tvl:,.2f}")
    print()
    
    # Filter 5: Low Fee Tier
    print("Filter 5: Low Fee Tier (≤500 bps)")
    print("-" * 70)
    low_fee = client.get_low_fee_pools(max_fee_tier=500, first=100)
    print(f"  Found: {len(low_fee)} pools")
    for p in low_fee[:5]:
        t0 = p.get("token0", {}).get("symbol", "N/A")
        t1 = p.get("token1", {}).get("symbol", "N/A")
        fee = p.get("feeTier", "N/A")
        tvl = p.get("_estimatedTvlUSD", 0)
        print(f"    {t0}/{t1} - Fee: {fee}bps | TVL: ${tvl:,.2f}")
    print()
    
    # Combined Filters
    print("Combined Filters (TVL>$10 + Low Fee ≤3000bps)")
    print("-" * 70)
    filtered = client.get_pools_with_all_filters(
        stable_pairs_only=False,
        min_tvl_usd=10,
        min_turnover=0,
        max_fee_tier=3000,
        first=100
    )
    print(f"  Found: {len(filtered)} pools")
    for p in filtered[:5]:
        t0 = p.get("token0", {}).get("symbol", "N/A")
        t1 = p.get("token1", {}).get("symbol", "N/A")
        tvl = p.get("_estimatedTvlUSD", 0)
        fee = p.get("feeTier", "N/A")
        tx = int(p.get("txCount") or 0)
        print(f"    {t0}/{t1} - TVL: ${tvl:,.2f} | Fee: {fee}bps | Tx: {tx:,}")
    print()
    
    print("=" * 70)
    print("Analysis Complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
