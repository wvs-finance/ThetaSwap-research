"""
Structural proxy for fee compression.

Calibrates passive_capture_rate from MACRA24 structural model + volatility regime,
then generates daily FeeCompression = feeGrowthInside(range) * (1 - pcr).

Two-step calibration:
  Step 1 (MACRA24): actual_pcr ~ alpha * baseDemand / (1 + beta * N)
  Step 2 (regime):  residuals ~ gamma1 * meanrev + gamma2 * vol_trending

Design doc: docs/plans/2026-03-01-structural-fee-compression-proxy-design.md
"""
import os
import sys
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
import statsmodels.api as sm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.DataHandler import PoolEntryData, volumeUSD, liquidity, priceUSD
from data.UniswapClient import UniswapClient, v3

V3_USDC_WETH = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"
FG_INSIDE_PATH = "data/fg_inside_range_sample.csv"
OUTPUT_PATH = "data/fee_compression_daily.csv"


def load_training_data():
    """Load actual_pcr observations from on-chain RPC output."""
    df = pd.read_csv(FG_INSIDE_PATH, parse_dates=["date"], index_col="date")
    return df


def load_pool_data():
    """Load full daily PoolEntryData from The Graph."""
    client = UniswapClient(v3())
    pool = PoolEntryData(V3_USDC_WETH, client=client)
    return pool(pool.lifetimeLen())


def compute_base_demand(pool_data):
    """baseDemand = volumeUSD / liquidityInRangeUSD.

    liquidityInRangeUSD approximated from PoolEntryData `liquidity` field
    (in-range liquidity at active tick) converted to USD via sqrtPrice.

    For USDC/WETH pool (token0=USDC, token1=WETH):
    liquidityInRangeUSD ~ 2 * liquidity * sqrtPrice / 2^96
    """
    vol = volumeUSD(pool_data)
    liq = liquidity(pool_data)
    sqrt_price = pool_data["sqrtPrice"]

    Q96 = 2**96
    liq_usd = 2.0 * liq * sqrt_price / Q96
    liq_usd = liq_usd.replace(0, np.nan)

    return vol / liq_usd


def compute_meanrev(pool_data, window=30):
    """Mean-reversion indicator: -autocorr(delta_P/P, lag=1, window)."""
    price = priceUSD(pool_data)
    returns = price.pct_change()
    meanrev = -returns.rolling(window).apply(
        lambda x: x.autocorr(lag=1) if len(x.dropna()) > 2 else 0,
        raw=False
    )
    return meanrev


def compute_vol_trending(pool_data, window=30):
    """Excess volatility: |delta_P/P| - rolling_mean(|delta_P/P|, window)."""
    price = priceUSD(pool_data)
    abs_ret = price.pct_change().abs()
    return abs_ret - abs_ret.rolling(window).mean()


def calibrate_step1(actual_pcr, baseDemand, N):
    """Non-linear least squares: actual_pcr ~ alpha * baseDemand / (1 + beta * N).

    Returns (alpha, beta, residuals, finite_mask).
    """
    mask = np.isfinite(actual_pcr) & np.isfinite(baseDemand) & np.isfinite(N)
    y = actual_pcr[mask].values
    bd = baseDemand[mask].values
    n = N[mask].values

    if len(y) < 10:
        raise ValueError(f"Too few finite observations for calibration: {len(y)}")

    def model(X, alpha, beta_param):
        bd_, n_ = X
        return alpha * bd_ / (1.0 + beta_param * n_)

    popt, pcov = curve_fit(model, (bd, n), y, p0=[1.0, 0.001],
                           bounds=([0, 0], [np.inf, np.inf]), maxfev=10000)
    alpha, beta_param = popt
    fitted = model((bd, n), alpha, beta_param)
    residuals = y - fitted
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((y - y.mean())**2)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    print(f"Step 1: alpha={alpha:.6f}, beta={beta_param:.8f}, R2={r2:.4f}")
    print(f"  N obs: {len(y)}, baseDemand range: [{bd.min():.4f}, {bd.max():.4f}]")
    print(f"  N range: [{n.min():.0f}, {n.max():.0f}]")
    return alpha, beta_param, r2, residuals, mask


def calibrate_step2(residuals, meanrev, vol_trending, mask):
    """OLS on Step 1 residuals: residuals ~ gamma1*meanrev + gamma2*vol_trending.

    Returns (gamma1, gamma2, ols_result).
    """
    mr = meanrev[mask].values
    vt = vol_trending[mask].values

    finite = np.isfinite(mr) & np.isfinite(vt)
    if finite.sum() < 10:
        print("Step 2: Too few finite observations, skipping regime correction")
        return 0.0, 0.0, None

    X = sm.add_constant(np.column_stack([mr[finite], vt[finite]]))
    y = residuals[finite]

    ols = sm.OLS(y, X).fit(cov_type="HC1")
    gamma1, gamma2 = ols.params[1], ols.params[2]

    print(f"Step 2: gamma1={gamma1:.6f} (p={ols.pvalues[1]:.4f}), "
          f"gamma2={gamma2:.6f} (p={ols.pvalues[2]:.4f})")
    print(f"  Signs: gamma1>0={gamma1 > 0} (expected +), gamma2<0={gamma2 < 0} (expected -)")
    return gamma1, gamma2, ols


def generate_daily_series(pool_data, alpha, beta_param, gamma1, gamma2,
                          N_sparse, fg_range_sparse):
    """Apply fitted model to full daily data and compute FeeCompression.

    N_sparse and fg_range_sparse are sparse (208 obs) — interpolated to daily.
    """
    bd = compute_base_demand(pool_data)
    mr = compute_meanrev(pool_data)
    vt = compute_vol_trending(pool_data)

    daily_idx = pool_data.index

    # Interpolate N to daily
    N_interp = N_sparse.reindex(daily_idx).interpolate(method="linear").ffill().bfill()

    # Compute passive_capture_rate
    pcr_struct = alpha * bd / (1.0 + beta_param * N_interp)
    pcr_correct = gamma1 * mr + gamma2 * vt
    pcr = pcr_struct + pcr_correct
    pcr = pcr.clip(0, 1)

    # Interpolate feeGrowthInside(range) to daily
    fg_interp = fg_range_sparse.reindex(daily_idx).interpolate(method="cubic").ffill().bfill()

    # FeeCompression = feeGrowthInside(range) * (1 - pcr)
    fee_compression = fg_interp * (1.0 - pcr)

    return fee_compression, pcr


def main():
    print("Loading training data...")
    train = load_training_data()
    print(f"  {len(train)} observations from {train.index.min()} to {train.index.max()}")

    print("Loading pool data from The Graph...")
    pool_data = load_pool_data()
    print(f"  {len(pool_data)} daily observations")

    # Align training data to pool_data dates
    common_idx = train.index.intersection(pool_data.index)
    if len(common_idx) == 0:
        # Try normalizing dates
        train.index = train.index.normalize()
        pool_data.index = pool_data.index.normalize()
        common_idx = train.index.intersection(pool_data.index)
    train = train.loc[common_idx]
    print(f"  {len(train)} training observations after alignment")

    # Compute covariates on full daily data
    bd_full = compute_base_demand(pool_data)
    mr_full = compute_meanrev(pool_data)
    vt_full = compute_vol_trending(pool_data)

    # N_t from training data (num_in_range at each sample block)
    N_sparse = train["num_in_range"].astype(float)

    # Align covariates to training dates
    bd_train = bd_full.reindex(train.index)
    mr_train = mr_full.reindex(train.index)
    vt_train = vt_full.reindex(train.index)

    actual_pcr = train["actual_pcr"].astype(float)

    # Step 1: NLLS calibration
    print("\n--- Step 1: MACRA24 structural base ---")
    alpha, beta_param, r2, residuals, mask = calibrate_step1(
        actual_pcr, bd_train, N_sparse
    )

    # Step 2: OLS on residuals
    print("\n--- Step 2: Volatility regime correction ---")
    gamma1, gamma2, ols = calibrate_step2(residuals, mr_train, vt_train, mask)

    # Generate daily series
    print("\n--- Generating daily FeeCompression series ---")
    # Use range_fg0 (token0/USDC-denominated) as primary
    fg_range = pd.to_numeric(train["range_fg0"], errors="coerce")

    fee_compression, pcr = generate_daily_series(
        pool_data, alpha, beta_param, gamma1, gamma2, N_sparse, fg_range
    )

    # Save output
    out = pd.DataFrame({
        "fee_compression": fee_compression,
        "passive_capture_rate": pcr,
    })
    out.index.name = "date"
    out.to_csv(OUTPUT_PATH)
    print(f"\nSaved {len(out)} daily observations to {OUTPUT_PATH}")

    # Summary stats
    fc = out["fee_compression"].dropna()
    print(f"FeeCompression: mean={fc.mean():.6e}, std={fc.std():.6e}")
    print(f"  min={fc.min():.6e}, max={fc.max():.6e}")
    print(f"  NaN count: {out['fee_compression'].isna().sum()}")

    pcr_clean = out["passive_capture_rate"].dropna()
    print(f"PCR: mean={pcr_clean.mean():.4f}, std={pcr_clean.std():.4f}")

    # Acceptance criteria
    print("\n--- Acceptance Criteria ---")
    print(f"  R2 > 0.3: {r2:.4f} {'PASS' if r2 > 0.3 else 'FAIL'}")
    print(f"  beta > 0: {beta_param:.8f} {'PASS' if beta_param > 0 else 'FAIL'}")
    if ols is not None:
        print(f"  gamma1 > 0: {gamma1:.6f} {'PASS' if gamma1 > 0 else 'WARN'}")
        print(f"  gamma2 < 0: {gamma2:.6f} {'PASS' if gamma2 < 0 else 'WARN'}")


if __name__ == "__main__":
    main()
