# Structural Fee Compression Proxy — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a structural proxy for fee compression that computes `FeeCompression_t = feeGrowthInside(range_t) × (1 - passive_capture_rate_t)` using on-chain range data + calibrated structural model, replacing the failed TVL-based congestion variable.

**Architecture:** Two new scripts: (1) lightweight RPC script reads 5-7 values per block to compute `feeGrowthInside(range)` for 208 sample blocks, (2) structural proxy script calibrates `passive_capture_rate` from MACRA24 structural base + volatility regime correction using PoolEntryData, then generates the full daily FeeCompression series. The econometrics notebook swaps in FeeCompression as the Stage 1 endogenous variable.

**Tech Stack:** Python 3.14, web3.py, eth_abi, scipy.optimize, statsmodels, pandas, numpy. Alchemy RPC (free tier). The Graph subgraph for PoolEntryData.

**Design doc:** `docs/plans/2026-03-01-structural-fee-compression-proxy-design.md`

---

### Task 1: Create `compute_fg_inside_range.py` — On-chain feeGrowthInside for implied range + reference position

**Files:**
- Create: `data/compute_fg_inside_range.py`
- Read: `data/compute_fee_compression.py` (reuse multicall, constants, loaders)
- Read: `data/position_registry.csv`, `data/daily_blocks.csv`
- Output: `data/fg_inside_range_sample.csv`

**Step 1: Write the script**

This script computes two values at each of 208 sample blocks:
- `fg_inside_range_0/1` — feeGrowthInside for the implied [P10, P90] tick range (monopolist rate)
- `fg_inside_ref_0/1` — feeGrowthInside for the median-liquidity reference position (representative passive LP)

It needs only 5-7 RPC calls per block (not hundreds like the full per-position approach):
1. `slot0()` → current tick
2. `feeGrowthGlobal0X128()`, `feeGrowthGlobal1X128()` → global accumulators
3. `ticks(p10_tick)` → feeGrowthOutside at P10 boundary
4. `ticks(p90_tick)` → feeGrowthOutside at P90 boundary
5. `ticks(ref_tickLower)` → feeGrowthOutside at reference position lower bound
6. `ticks(ref_tickUpper)` → feeGrowthOutside at reference position upper bound

The P10/P90 ticks and reference position are computed from position_registry.csv using liquidity-weighted percentiles (reuse `liquidity_weighted_percentile` from `compute_fee_compression.py`).

```python
"""
Lightweight RPC: compute feeGrowthInside for implied range and reference position.

Only 5-7 RPC calls per block (via Multicall3) → ~15 min for 208 blocks.
Outputs training data for the structural proxy calibration.
"""
import csv
import os
import time
import numpy as np
from web3 import Web3
from eth_abi import encode, decode

RPC_URL = os.getenv("ALCHEMY_RPC", "https://eth-mainnet.g.alchemy.com/v2/fd_m2oikp78msnnQGxO6H")
DAILY_BLOCKS_PATH = "data/daily_blocks.csv"
POSITION_REGISTRY_PATH = "data/position_registry.csv"
OUTPUT_PATH = "data/fg_inside_range_sample.csv"

POOL_ADDRESS = "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640"
MULTICALL3 = "0xcA11bde05977b3631167028862bE2a173976CA11"
MULTICALL3_DEPLOY_BLOCK = 14_353_601
SAMPLE_INTERVAL = 7

w3 = Web3(Web3.HTTPProvider(RPC_URL, request_kwargs={"timeout": 120}))

SLOT0_SIG = Web3.keccak(text="slot0()")[:4]
TICKS_SIG = Web3.keccak(text="ticks(int24)")[:4]
FEE_GROWTH0_SIG = Web3.keccak(text="feeGrowthGlobal0X128()")[:4]
FEE_GROWTH1_SIG = Web3.keccak(text="feeGrowthGlobal1X128()")[:4]
AGGREGATE3_SIG = Web3.keccak(text="aggregate3((address,bool,bytes)[])")[:4]

UINT256_MAX = 2**256


def multicall(calls, block_num):
    """Execute calls via Multicall3. Small batches — no splitting needed."""
    encoded_calls = [(Web3.to_checksum_address(t), True, cd) for t, cd in calls]
    multicall_data = AGGREGATE3_SIG + encode(
        ["(address,bool,bytes)[]"], [encoded_calls]
    )
    for attempt in range(4):
        try:
            raw = w3.eth.call(
                {"to": MULTICALL3, "data": multicall_data},
                block_identifier=block_num
            )
            return decode(["(bool,bytes)[]"], raw)[0]
        except Exception as e:
            if "429" in str(e) or "Too Many" in str(e):
                time.sleep(2.0 * (attempt + 1))
            else:
                raise
    raise RuntimeError(f"Multicall failed after 4 retries at block {block_num}")


def load_daily_blocks():
    with open(DAILY_BLOCKS_PATH) as f:
        return [(r["date"], int(r["block_number"])) for r in csv.DictReader(f)]


def load_positions():
    with open(POSITION_REGISTRY_PATH) as f:
        return [(int(r["tokenId"]), int(r["tickLower"]), int(r["tickUpper"]))
                for r in csv.DictReader(f)]


def liquidity_weighted_percentile(values, weights, percentile):
    """Compute liquidity-weighted percentile."""
    sorted_indices = np.argsort(values)
    sorted_values = values[sorted_indices]
    sorted_weights = weights[sorted_indices]
    cum_weights = np.cumsum(sorted_weights) / sorted_weights.sum()
    idx = np.searchsorted(cum_weights, percentile / 100.0)
    return int(sorted_values[min(idx, len(sorted_values) - 1)])


def compute_fg_inside(fg_global0, fg_global1, tick_current, tick_lower, tick_upper,
                       lower_fgo0, lower_fgo1, upper_fgo0, upper_fgo1):
    """Compute feeGrowthInside for a tick range using Python ints (no precision loss)."""
    if tick_current < tick_lower:
        fg0 = (lower_fgo0 - upper_fgo0) % UINT256_MAX
        fg1 = (lower_fgo1 - upper_fgo1) % UINT256_MAX
    elif tick_current < tick_upper:
        fg0 = (fg_global0 - lower_fgo0 - upper_fgo0) % UINT256_MAX
        fg1 = (fg_global1 - lower_fgo1 - upper_fgo1) % UINT256_MAX
    else:
        fg0 = (upper_fgo0 - lower_fgo0) % UINT256_MAX
        fg1 = (upper_fgo1 - lower_fgo1) % UINT256_MAX
    return fg0, fg1


def find_reference_position(positions, tick_current):
    """Find median-liquidity in-range position as reference."""
    # We need to batch-read liquidity for in-range positions
    # For efficiency, use position_registry liquidity column as proxy
    # (static value from creation, but good enough for median selection)
    in_range = [(tid, tl, tu) for tid, tl, tu in positions
                if tl <= tick_current < tu]
    if not in_range:
        return None
    # Use tick width as proxy for "typical" position — median tick range
    widths = [tu - tl for _, tl, tu in in_range]
    median_idx = np.argsort(widths)[len(widths) // 2]
    return in_range[median_idx]


def compute_at_block(block_num, positions):
    """Compute feeGrowthInside for implied range and reference position at one block."""
    # Step 1: Get pool state + determine ticks we need
    pool_calls = [
        (POOL_ADDRESS, SLOT0_SIG),
        (POOL_ADDRESS, FEE_GROWTH0_SIG),
        (POOL_ADDRESS, FEE_GROWTH1_SIG),
    ]
    results = multicall(pool_calls, block_num)

    slot0 = decode(["uint160", "int24", "uint16", "uint16", "uint16", "uint8", "bool"],
                    results[0][1])
    tick_current = slot0[1]
    fg_global0 = decode(["uint256"], results[1][1])[0]
    fg_global1 = decode(["uint256"], results[2][1])[0]

    # Step 2: Compute implied tick range [P10, P90] from in-range positions
    in_range = [(tid, tl, tu) for tid, tl, tu in positions
                if tl <= tick_current < tu]
    if len(in_range) < 2:
        return None

    tl_arr = np.array([tl for _, tl, _ in in_range])
    tu_arr = np.array([tu for _, _, tu in in_range])
    # Equal weight since we don't have per-block liquidity without extra RPC
    weights = np.ones(len(in_range))

    p10_tick = liquidity_weighted_percentile(tl_arr, weights, 10)
    p90_tick = liquidity_weighted_percentile(tu_arr, weights, 90)

    # Step 3: Find reference position (median tick-width in-range position)
    ref = find_reference_position(positions, tick_current)
    if ref is None:
        return None
    _, ref_tl, ref_tu = ref

    # Step 4: Batch-read tick feeGrowthOutside for all 4 ticks
    unique_ticks = sorted(set([p10_tick, p90_tick, ref_tl, ref_tu]))
    tick_calls = [
        (POOL_ADDRESS, TICKS_SIG + encode(["int24"], [t]))
        for t in unique_ticks
    ]
    tick_results = multicall(tick_calls, block_num)

    tick_fgo = {}
    for t, (success, data) in zip(unique_ticks, tick_results):
        if not success or len(data) < 32:
            return None
        td = decode(["uint128", "int128", "uint256", "uint256",
                      "int56", "uint160", "uint32", "bool"], data)
        tick_fgo[t] = (td[2], td[3])  # feeGrowthOutside0X128, feeGrowthOutside1X128

    # Step 5: Compute feeGrowthInside for range and reference
    range_fg0, range_fg1 = compute_fg_inside(
        fg_global0, fg_global1, tick_current, p10_tick, p90_tick,
        *tick_fgo[p10_tick], *tick_fgo[p90_tick]
    )
    ref_fg0, ref_fg1 = compute_fg_inside(
        fg_global0, fg_global1, tick_current, ref_tl, ref_tu,
        *tick_fgo[ref_tl], *tick_fgo[ref_tu]
    )

    # Step 6: Compute actual passive capture rate (ratio in Python ints)
    # pcr = ref_fg / range_fg (per token, then average)
    pcr0 = ref_fg0 / range_fg0 if range_fg0 > 0 else 0.0
    pcr1 = ref_fg1 / range_fg1 if range_fg1 > 0 else 0.0
    # Use token0 (USDC-denominated) as primary, token1 as secondary
    pcr = pcr0 if range_fg0 > 0 else pcr1

    return {
        "tick_current": tick_current,
        "p10_tick": p10_tick,
        "p90_tick": p90_tick,
        "ref_tl": ref_tl,
        "ref_tu": ref_tu,
        "range_fg0": str(range_fg0),
        "range_fg1": str(range_fg1),
        "ref_fg0": str(ref_fg0),
        "ref_fg1": str(ref_fg1),
        "actual_pcr": float(pcr),
        "num_in_range": len(in_range),
    }


def main():
    daily_blocks = load_daily_blocks()
    positions = load_positions()

    eligible = [(d, b) for d, b in daily_blocks if b >= MULTICALL3_DEPLOY_BLOCK]
    sampled = eligible[::SAMPLE_INTERVAL]

    # Resume support
    completed = set()
    if os.path.exists(OUTPUT_PATH) and os.path.getsize(OUTPUT_PATH) > 0:
        with open(OUTPUT_PATH) as f:
            for row in csv.DictReader(f):
                completed.add(row["date"])
        print(f"Resuming: {len(completed)} already done")

    remaining = [(d, b) for d, b in sampled if d not in completed]
    print(f"{len(remaining)} blocks to compute ({len(sampled)} total sampled)")

    fieldnames = ["date", "block_number", "tick_current", "p10_tick", "p90_tick",
                  "ref_tl", "ref_tu", "range_fg0", "range_fg1",
                  "ref_fg0", "ref_fg1", "actual_pcr", "num_in_range"]

    mode = "a" if completed else "w"
    with open(OUTPUT_PATH, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not completed:
            writer.writeheader()

        for i, (date, block) in enumerate(remaining):
            t0 = time.time()
            try:
                result = compute_at_block(block, positions)
                elapsed = time.time() - t0
                if result is None:
                    print(f"  [{i+1}/{len(remaining)}] {date} — skipped (no in-range positions)")
                    continue
                row = {"date": date, "block_number": block, **result}
                writer.writerow(row)
                f.flush()
                if (i + 1) % 10 == 0 or i == 0:
                    print(f"  [{i+1}/{len(remaining)}] {date} pcr={result['actual_pcr']:.6f} "
                          f"n={result['num_in_range']} time={elapsed:.1f}s")
            except Exception as e:
                print(f"  ERROR {date}: {e}")
                time.sleep(1)

    print(f"Done. Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
```

**Step 2: Run the script**

```bash
source uhi8/bin/activate
python data/compute_fg_inside_range.py
```

Expected: ~208 rows written to `data/fg_inside_range_sample.csv` in ~15 min. Each row has `actual_pcr` between 0 and 1 (fraction of range fees captured by the reference passive position).

**Step 3: Validate output**

```bash
python -c "
import pandas as pd
df = pd.read_csv('data/fg_inside_range_sample.csv')
print(f'Rows: {len(df)}')
print(f'actual_pcr stats:')
print(df['actual_pcr'].describe())
assert len(df) > 100, 'Too few rows'
assert 0 < df['actual_pcr'].median() < 1, 'pcr should be between 0 and 1'
print('PASS')
"
```

Expected: `actual_pcr` median between 0.3 and 0.95 (passive LPs capture a significant fraction but not all fees).

**Step 4: Commit**

```bash
git add data/compute_fg_inside_range.py
git commit -m "feat: add lightweight RPC script for feeGrowthInside range + reference position"
```

---

### Task 2: Create `data/structural_proxy.py` — Calibrate passive_capture_rate and generate daily FeeCompression

**Files:**
- Create: `data/structural_proxy.py`
- Read: `data/fg_inside_range_sample.csv` (from Task 1)
- Read: `data/DataHandler.py:29-118` (PoolEntryData class)
- Read: `docs/plans/2026-03-01-structural-fee-compression-proxy-design.md` (formulas)
- Output: `data/fee_compression_daily.csv`

**Step 1: Write the script**

This script:
1. Loads the 208 `actual_pcr` observations from Task 1
2. Loads matching PoolEntryData (volumeUSD, liquidity, priceUSD)
3. Computes structural covariates: `baseDemand`, `N_t`, `meanrev`, `vol_trending`
4. Step 1 calibration: NLLS `actual_pcr ~ α · baseDemand / (1 + β·N)`
5. Step 2 calibration: OLS on residuals `~ γ₁·meanrev + γ₂·vol_trending`
6. Applies fitted model to full daily PoolEntryData
7. Multiplies by interpolated `feeGrowthInside(range)` to get FeeCompression

```python
"""
Structural proxy for fee compression.

Calibrates passive_capture_rate from MACRA24 structural model + volatility regime,
then generates daily FeeCompression = feeGrowthInside(range) × (1 - pcr).
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
POSITION_REGISTRY_PATH = "data/position_registry.csv"
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


def count_active_positions_by_date():
    """Count in-range positions per date from position_registry + daily_blocks.

    Approximation: count all positions with non-zero tick range as a proxy for N_t.
    The position_registry is a static snapshot — N_t variation comes from
    the fee_variance_sample.csv num_positions column.
    """
    # Use num_in_range from fg_inside_range_sample.csv (computed at each block)
    df = pd.read_csv(FG_INSIDE_PATH, parse_dates=["date"], index_col="date")
    n_series = df["num_in_range"]
    return n_series


def compute_base_demand(pool_data):
    """baseDemand = volumeUSD / liquidityInRangeUSD.

    liquidityInRangeUSD approximated from PoolEntryData `liquidity` field
    (in-range liquidity at active tick) converted to USD via sqrtPrice.

    For USDC/WETH pool (token0=USDC, token1=WETH):
    liquidityInRangeUSD ≈ 2 × liquidity × sqrtPrice / 2^96
    (simplified — both tokens contribute roughly equally near the current price)
    """
    vol = volumeUSD(pool_data)
    liq = liquidity(pool_data)
    sqrt_price = pool_data["sqrtPrice"]

    # Convert liquidity to USD: L * sqrtPrice / 2^96 gives token0 (USDC) amount
    # Total ≈ 2× that (both sides of the position)
    Q96 = 2**96
    liq_usd = 2.0 * liq * sqrt_price / Q96
    liq_usd = liq_usd.replace(0, np.nan)  # avoid div by zero

    return vol / liq_usd


def compute_meanrev(pool_data, window=30):
    """Mean-reversion indicator: -autocorr(ΔP/P, lag=1, window)."""
    price = priceUSD(pool_data)
    returns = price.pct_change()
    meanrev = -returns.rolling(window).apply(
        lambda x: x.autocorr(lag=1) if len(x.dropna()) > 2 else 0,
        raw=False
    )
    return meanrev


def compute_vol_trending(pool_data, window=30):
    """Excess volatility: |ΔP/P| - rolling_mean(|ΔP/P|, window)."""
    price = priceUSD(pool_data)
    abs_ret = price.pct_change().abs()
    return abs_ret - abs_ret.rolling(window).mean()


def pcr_structural(baseDemand, N, alpha, beta_param):
    """MACRA24 structural base: α · baseDemand / (1 + β·N)."""
    return alpha * baseDemand / (1.0 + beta_param * N)


def calibrate_step1(actual_pcr, baseDemand, N):
    """Non-linear least squares: actual_pcr ~ α · baseDemand / (1 + β·N)."""
    mask = np.isfinite(actual_pcr) & np.isfinite(baseDemand) & np.isfinite(N)
    y = actual_pcr[mask].values
    bd = baseDemand[mask].values
    n = N[mask].values

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
    r2 = 1 - ss_res / ss_tot

    print(f"Step 1: α={alpha:.6f}, β={beta_param:.8f}, R²={r2:.4f}")
    return alpha, beta_param, residuals, mask


def calibrate_step2(residuals, meanrev, vol_trending, mask):
    """OLS on Step 1 residuals: residuals ~ γ₁·meanrev + γ₂·vol_trending."""
    mr = meanrev[mask].values
    vt = vol_trending[mask].values

    # Further filter to finite values in regime variables
    finite = np.isfinite(mr) & np.isfinite(vt)
    X = sm.add_constant(np.column_stack([mr[finite], vt[finite]]))
    y = residuals[finite]

    ols = sm.OLS(y, X).fit(cov_type="HC1")
    gamma1, gamma2 = ols.params[1], ols.params[2]

    print(f"Step 2: γ₁={gamma1:.6f} (p={ols.pvalues[1]:.4f}), "
          f"γ₂={gamma2:.6f} (p={ols.pvalues[2]:.4f})")
    print(f"  Signs OK: γ₁>0={gamma1 > 0}, γ₂<0={gamma2 < 0}")
    return gamma1, gamma2, ols


def generate_daily_series(pool_data, alpha, beta_param, gamma1, gamma2, N_daily,
                          fg_range_daily):
    """Apply fitted model to full daily data and compute FeeCompression."""
    bd = compute_base_demand(pool_data)
    mr = compute_meanrev(pool_data)
    vt = compute_vol_trending(pool_data)

    # Interpolate N to daily
    daily_idx = pool_data.index
    N_interp = N_daily.reindex(daily_idx).interpolate(method="linear").ffill().bfill()

    # Compute passive_capture_rate
    pcr_struct = alpha * bd / (1.0 + beta_param * N_interp)
    pcr_correct = gamma1 * mr + gamma2 * vt
    pcr = pcr_struct + pcr_correct
    pcr = pcr.clip(0, 1)  # bound to [0, 1]

    # Interpolate feeGrowthInside(range) to daily
    fg_interp = fg_range_daily.reindex(daily_idx).interpolate(method="cubic").ffill().bfill()

    # FeeCompression = feeGrowthInside(range) × (1 - pcr)
    fee_compression = fg_interp * (1.0 - pcr)

    return fee_compression, pcr


def main():
    print("Loading training data...")
    train = load_training_data()

    print("Loading pool data from The Graph...")
    pool_data = load_pool_data()

    # Align training data to pool_data dates
    common_idx = train.index.intersection(pool_data.index)
    train = train.loc[common_idx]

    # Compute covariates
    bd_full = compute_base_demand(pool_data)
    mr_full = compute_meanrev(pool_data)
    vt_full = compute_vol_trending(pool_data)
    N_full = count_active_positions_by_date()

    # Align to training dates
    bd_train = bd_full.reindex(train.index)
    mr_train = mr_full.reindex(train.index)
    vt_train = vt_full.reindex(train.index)
    N_train = N_full.reindex(train.index)

    actual_pcr = train["actual_pcr"]

    # Step 1: NLLS calibration
    print("\n--- Step 1: MACRA24 structural base ---")
    alpha, beta_param, residuals, mask = calibrate_step1(actual_pcr, bd_train, N_train)

    # Step 2: OLS on residuals
    print("\n--- Step 2: Volatility regime correction ---")
    gamma1, gamma2, ols = calibrate_step2(residuals, mr_train, vt_train, mask)

    # Generate daily series
    print("\n--- Generating daily FeeCompression series ---")
    # Use range_fg0 as primary (USDC-denominated)
    fg_range = pd.to_numeric(train["range_fg0"], errors="coerce")

    fee_compression, pcr = generate_daily_series(
        pool_data, alpha, beta_param, gamma1, gamma2, N_full, fg_range
    )

    # Save output
    out = pd.DataFrame({
        "fee_compression": fee_compression,
        "passive_capture_rate": pcr,
    })
    out.to_csv(OUTPUT_PATH)
    print(f"\nSaved {len(out)} daily observations to {OUTPUT_PATH}")

    # Summary stats
    fc = out["fee_compression"].dropna()
    print(f"FeeCompression: mean={fc.mean():.6e}, std={fc.std():.6e}, "
          f"min={fc.min():.6e}, max={fc.max():.6e}")


if __name__ == "__main__":
    main()
```

**Step 2: Run the script (after Task 1 output exists)**

```bash
source uhi8/bin/activate
python data/structural_proxy.py
```

Expected: Prints calibration results (R², α, β, γ₁, γ₂), generates `data/fee_compression_daily.csv` with ~1760 rows.

**Step 3: Validate calibration**

Check:
- Step 1 R² > 0.3
- β > 0 (more LPs → lower passive capture via denominator)
- γ₁ > 0 (mean-reversion helps passive), γ₂ < 0 (excess vol hurts passive)
- FeeCompression values are reasonable (not 1e45, not all zeros)

**Step 4: Commit**

```bash
git add data/structural_proxy.py
git commit -m "feat: add structural proxy calibration for passive_capture_rate"
```

---

### Task 3: Update `DataHandler.py` — Add `load_fee_compression_daily()` loader

**Files:**
- Modify: `data/DataHandler.py:131-138` (existing `load_fee_compression` or add new function)

**Step 1: Add the loader function**

Add after the existing `load_fee_compression` function (line 138):

```python
def load_fee_compression_daily(path: str = "data/fee_compression_daily.csv") -> TimeSeries:
    """Load daily structural fee compression series (from structural_proxy.py output)."""
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    return pd.to_numeric(df["fee_compression"], errors="coerce")
```

**Step 2: Verify it loads correctly**

```bash
python -c "
from data.DataHandler import load_fee_compression_daily
fc = load_fee_compression_daily()
print(f'Shape: {fc.shape}')
print(f'NaN: {fc.isna().sum()}')
print(fc.describe())
assert fc.shape[0] > 1000, 'Too few rows'
print('PASS')
"
```

**Step 3: Commit**

```bash
git add data/DataHandler.py
git commit -m "feat: add load_fee_compression_daily loader for structural proxy output"
```

---

### Task 4: Add econometrics notebook cells — Run Stage 1 + Stage 2 with FeeCompression

**Files:**
- Modify: `notebooks/econometrics.ipynb` (add new section after existing Stage 2)

**Step 1: Add cells to the notebook**

Add a new section "Stage 1b + Stage 2b: Structural FeeCompression Model" with these cells:

**Cell 1 — Load FeeCompression:**
```python
from data.DataHandler import load_fee_compression_daily

fee_compression = load_fee_compression_daily()
# Align to pool_data dates
fc_aligned = fee_compression.reindex(pool_data.index).dropna()
print(f"FeeCompression: {len(fc_aligned)} daily observations")
print(fc_aligned.describe())
```

**Cell 2 — Stage 1b: UnobservedComponents with FeeCompression:**
```python
# Stage 1b: Extract congestion index from FeeCompression
from data.Econometrics import LiquidityStateModel, state, beta, rho, result

# Endogenous: delta(FeeCompression) / lagged(FeeCompression)
fc_change = delta(fc_aligned) / lagged(fc_aligned)
fc_change = fc_change.replace([np.inf, -np.inf], np.nan).dropna()

# Exogenous: same as before — price returns
price_ret = delta(priceUSD(pool_data)) / lagged(priceUSD(pool_data))
price_ret = price_ret.reindex(fc_change.index)

# Fit
ls_fc = LiquidityStateModel()(endog=fc_change, exog=price_ret)
print(f"γ (persistence) = {rho(ls_fc):.4f}")
print(f"Market state β = {beta(ls_fc)}")
congestion_fc = state(ls_fc)
```

**Cell 3 — Stage 2b: Adverse Competition test:**
```python
from data.Econometrics import AdverseCompetitionModel, delta_coeff, ols_result

# Fee yield
fee_yield = delta(div(feesUSD(pool_data), tvlUSD(pool_data)))
fee_yield = fee_yield.reindex(congestion_fc.index)

# LVR proxy
lvr = price_ret.abs().reindex(congestion_fc.index)

# Test
ac_fc = AdverseCompetitionModel()(fee_yield=fee_yield, lvr_proxy=lvr, congestion=congestion_fc)
res = ols_result(ac_fc)
print(f"δ₂ = {delta_coeff(ac_fc):.6f}")
print(f"z-stat = {res.tvalues[1]:.4f}")
print(f"p-value = {res.pvalues[1]:.6f}")
print(f"Significant (p < 0.05): {res.pvalues[1] < 0.05}")
print(f"Correct sign (δ₂ < 0): {delta_coeff(ac_fc) < 0}")
```

**Cell 4 — Compare old vs new:**
```python
print("=" * 50)
print("COMPARISON: TVL-based vs FeeCompression-based")
print("=" * 50)
print(f"\nTVL-based:            δ₂ = {delta_coeff(ac):.6f}, p = {ols_result(ac).pvalues[1]:.6f}")
print(f"FeeCompression-based: δ₂ = {delta_coeff(ac_fc):.6f}, p = {ols_result(ac_fc).pvalues[1]:.6f}")
```

**Step 2: Run the notebook**

```bash
source uhi8/bin/activate
jupyter nbconvert --to notebook --execute notebooks/econometrics.ipynb --output econometrics_executed.ipynb
```

Or run interactively in Jupyter.

**Step 3: Verify acceptance criteria**

Check:
- δ₂ < 0 (negative sign = adverse competition)
- p < 0.05 (statistically significant)
- 0 < γ < 1 (persistent but mean-reverting congestion)

**Step 4: Commit**

```bash
git add notebooks/econometrics.ipynb
git commit -m "feat: add structural FeeCompression model to econometrics pipeline"
```

---

### Task 5: Write tests for structural proxy

**Files:**
- Create: `tests/test_structural_proxy.py`

**Step 1: Write the test file**

```python
#!/usr/bin/env python3
"""
Tests for structural fee compression proxy.

Usage:
    source uhi8/bin/activate
    python -m pytest tests/test_structural_proxy.py -v
"""
import os
import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFeeCompressionDailyLoader(unittest.TestCase):
    """Test the daily fee compression loader."""

    def test_load_returns_series(self):
        from data.DataHandler import load_fee_compression_daily
        fc = load_fee_compression_daily()
        self.assertIsInstance(fc, pd.Series)
        self.assertGreater(len(fc), 1000)

    def test_no_all_nan(self):
        from data.DataHandler import load_fee_compression_daily
        fc = load_fee_compression_daily()
        self.assertLess(fc.isna().mean(), 0.1, "More than 10% NaN")

    def test_values_finite(self):
        from data.DataHandler import load_fee_compression_daily
        fc = load_fee_compression_daily().dropna()
        self.assertTrue(np.all(np.isfinite(fc.values)), "Non-finite values found")


class TestStructuralProxyCalibration(unittest.TestCase):
    """Test that the structural proxy produces valid calibration."""

    @classmethod
    def setUpClass(cls):
        """Load the fg_inside_range_sample output and check it exists."""
        path = "data/fg_inside_range_sample.csv"
        if not os.path.exists(path):
            raise unittest.SkipTest(f"{path} not found — run compute_fg_inside_range.py first")
        cls.train = pd.read_csv(path, parse_dates=["date"], index_col="date")

    def test_actual_pcr_bounded(self):
        """actual_pcr should be between 0 and 1 for most observations."""
        pcr = self.train["actual_pcr"]
        valid = pcr[(pcr >= 0) & (pcr <= 1)]
        self.assertGreater(len(valid) / len(pcr), 0.8,
                           "Less than 80% of pcr values in [0, 1]")

    def test_sufficient_observations(self):
        """Need at least 100 training points."""
        self.assertGreater(len(self.train), 100)


class TestEconometricIntegration(unittest.TestCase):
    """Test that FeeCompression integrates into the two-stage model."""

    @classmethod
    def setUpClass(cls):
        path = "data/fee_compression_daily.csv"
        if not os.path.exists(path):
            raise unittest.SkipTest(f"{path} not found — run structural_proxy.py first")
        from data.DataHandler import load_fee_compression_daily
        cls.fc = load_fee_compression_daily()

    def test_series_stationary_proxy(self):
        """FeeCompression changes should be roughly stationary (ADF p < 0.1)."""
        from statsmodels.tsa.stattools import adfuller
        changes = self.fc.pct_change().dropna().replace([np.inf, -np.inf], np.nan).dropna()
        if len(changes) < 100:
            self.skipTest("Too few observations")
        adf_stat, pvalue, *_ = adfuller(changes.values[:1000])  # cap for speed
        self.assertLess(pvalue, 0.1, f"ADF p-value {pvalue:.4f} — not stationary")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests**

```bash
source uhi8/bin/activate
python -m pytest tests/test_structural_proxy.py -v
```

Expected: Tests that depend on output files will be skipped until Tasks 1-2 run. After Tasks 1-2, all tests should pass.

**Step 3: Commit**

```bash
git add tests/test_structural_proxy.py
git commit -m "test: add structural proxy validation tests"
```

---

## Execution Order

```
Task 1 (compute_fg_inside_range.py) → ~15 min RPC run
    ↓
Task 2 (structural_proxy.py) → depends on Task 1 output
    ↓
Task 3 (DataHandler loader) → can run in parallel with Task 2
    ↓
Task 4 (econometrics notebook) → depends on Tasks 2 + 3
    ↓
Task 5 (tests) → can be written any time, but full run needs Tasks 1-2 output
```

Tasks 1 and 5 (test file creation) can be done in parallel. Task 3 can be done in parallel with Task 2. Task 4 is the final integration step.
