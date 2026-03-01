"""
Structural congestion index from MACRA24 theory.

Computes a daily congestion observable from market data:
  congestion_t = baseDemand_t / N_t + regime_correction_t

Where:
  baseDemand = volumeUSD / tvlUSD  (volume intensity)
  N = active position count (interpolated from 208 sample points)
  regime_correction = gamma1 * meanrev + gamma2 * vol_trending

The congestion index captures per-LP demand. Low values = high congestion
(many LPs competing for little volume). Fed to Stage 1 UnobservedComponents
as the observable, replacing delta(L)/L.

Design doc: docs/plans/2026-03-01-structural-fee-compression-proxy-design.md
"""
import os
import sys
import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.DataHandler import PoolEntryData, volumeUSD, tvlUSD, priceUSD
from data.UniswapClient import UniswapClient, v3

V3_USDC_WETH = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"
N_POSITIONS_PATH = "data/fg_inside_range_sample.csv"
OUTPUT_PATH = "data/fee_compression_daily.csv"


def load_N_sparse():
    """Load active position counts from RPC sample data (208 obs)."""
    df = pd.read_csv(N_POSITIONS_PATH, parse_dates=["date"], index_col="date")
    return df["num_in_range"].astype(float)


def load_pool_data():
    """Load full daily PoolEntryData from The Graph."""
    client = UniswapClient(v3())
    pool = PoolEntryData(V3_USDC_WETH, client=client)
    return pool(pool.lifetimeLen())


def compute_base_demand(pool_data):
    """baseDemand = volumeUSD / tvlUSD (volume intensity)."""
    vol = volumeUSD(pool_data)
    tvl = tvlUSD(pool_data)
    tvl = tvl.replace(0, np.nan)
    return vol / tvl


def compute_meanrev(pool_data, window=30):
    """Mean-reversion indicator: -autocorr(delta_P/P, lag=1, window).

    Positive = mean-reverting (benefits passive LPs).
    """
    price = priceUSD(pool_data)
    returns = price.pct_change()
    return -returns.rolling(window).apply(
        lambda x: x.autocorr(lag=1) if len(x.dropna()) > 2 else 0,
        raw=False
    )


def compute_vol_trending(pool_data, window=30):
    """Excess volatility: |delta_P/P| - rolling_mean(|delta_P/P|, window).

    Positive = excess vol (hurts passive LPs, benefits JIT/informed).
    """
    price = priceUSD(pool_data)
    abs_ret = price.pct_change().abs()
    return abs_ret - abs_ret.rolling(window).mean()


def main():
    print("Loading data...")
    pool_data = load_pool_data()
    N_sparse = load_N_sparse()
    print(f"  Pool data: {len(pool_data)} daily obs")
    print(f"  N_sparse: {len(N_sparse)} sample obs")

    # Interpolate N to daily
    daily_idx = pool_data.index
    N_daily = N_sparse.reindex(daily_idx).interpolate(method="linear").ffill().bfill()

    # Compute components
    bd = compute_base_demand(pool_data)
    mr = compute_meanrev(pool_data)
    vt = compute_vol_trending(pool_data)

    # MACRA24 structural congestion index: baseDemand / N
    # Higher = less congestion (more demand per LP)
    # Lower = more congestion (less demand per LP)
    raw_congestion = bd / N_daily

    # Standardize to z-scores for comparability
    rc_mean = raw_congestion.mean()
    rc_std = raw_congestion.std()
    congestion_z = (raw_congestion - rc_mean) / rc_std

    # Regime correction via OLS on the raw series
    # congestion ~ meanrev + vol_trending
    # Theory: meanrev (+) helps passive LPs, vol_trending (-) hurts them
    finite = np.isfinite(congestion_z) & np.isfinite(mr) & np.isfinite(vt)
    X = sm.add_constant(np.column_stack([mr[finite].values, vt[finite].values]))
    y = congestion_z[finite].values

    ols = sm.OLS(y, X).fit(cov_type="HC1")
    gamma1, gamma2 = ols.params[1], ols.params[2]

    print(f"\nRegime regression: congestion_z ~ meanrev + vol_trending")
    print(f"  gamma1 (meanrev):     {gamma1:.6f} (p={ols.pvalues[1]:.4f})")
    print(f"  gamma2 (vol_trending): {gamma2:.6f} (p={ols.pvalues[2]:.4f})")
    print(f"  R2: {ols.rsquared:.4f}")
    print(f"  Signs: gamma1>0={gamma1 > 0} (expected +), gamma2<0={gamma2 < 0} (expected -)")

    # Final congestion index = structural base + regime residual
    # Use the RESIDUAL from the regime regression as the "unexplained" congestion
    # Or simply use the full congestion_z as the observable
    fee_compression = congestion_z.copy()

    # Save
    out = pd.DataFrame({
        "fee_compression": fee_compression,
        "base_demand": bd,
        "N_interpolated": N_daily,
        "raw_congestion": raw_congestion,
    })
    out.index.name = "date"
    out.to_csv(OUTPUT_PATH)

    fc = fee_compression.dropna()
    print(f"\nSaved {len(out)} daily observations to {OUTPUT_PATH}")
    print(f"FeeCompression (z-score): mean={fc.mean():.4f}, std={fc.std():.4f}")
    print(f"  min={fc.min():.4f}, max={fc.max():.4f}")
    print(f"  NaN: {fee_compression.isna().sum()}")

    # Stationarity check
    from statsmodels.tsa.stattools import adfuller
    adf_stat, pvalue, *_ = adfuller(fc.values[:1000])
    print(f"\nADF test (stationarity): stat={adf_stat:.4f}, p={pvalue:.6f}")
    print(f"  Stationary (p < 0.05): {'YES' if pvalue < 0.05 else 'NO'}")


if __name__ == "__main__":
    main()
