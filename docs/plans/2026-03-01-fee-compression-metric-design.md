# Fee Compression Metric: Design & Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the cross-sectional variance metric (FeeVarianceX128 — too small, misses JIT) with a fee compression metric that measures the gap between tick-range-level fee revenue and what passive LPs actually captured.

**Architecture:** Modify `compute_fee_variance_sample.py` → `compute_fee_compression.py`. Same Multicall3 batched RPC pipeline, same position/tick data reads. Only Step 6 (the math at the end) changes. Zero additional RPC calls. Then integrate the resulting time series into the existing two-stage econometric model as the congestion proxy.

**Tech Stack:** Python, web3.py, eth_abi, numpy, scipy (interpolation), statsmodels (econometrics)

---

## Background

### Why the variance metric failed

`FeeVarianceX128 = Var(fee_share_i - liq_share_i)` across active positions at daily snapshots:
- Values are tiny (2.4e-6 to 7.8e-4 in unit scale) — insufficient signal
- Only captures heterogeneity among passive LPs (who are relatively homogeneous)
- JIT liquidity providers withdraw within the same block → `liquidity = 0` at snapshot → invisible
- Measures the wrong thing: dispersion among survivors, not fee extraction by JIT

### The correct metric

```
FeeCompression_t = feeGrowthInside(impliedTickRange) - weightedAvg(feeGrowthInside(position_i))
```

Where:
- `feeGrowthInside(impliedTickRange)` = fee revenue per unit liquidity for the liquidity-weighted [P10, P90] tick range. Computed from pool tick data: `feeGrowthGlobal - feeGrowthOutside(P10_tick) - feeGrowthOutside(P90_tick)`. This captures ALL fee revenue in the active region, including fees extracted by JIT LPs before withdrawal.
- `weightedAvg(feeGrowthInside(position_i))` = liquidity-weighted average of per-position fee growth inside each position's specific tick range. Since cross-sectional variance is tiny (validated: CV < 1e-3), this average is representative of what any passive LP earned.
- The **gap** = fee revenue that went to non-persistent (JIT) liquidity and tick-range mismatch losses.

### Why feeGrowthGlobal is wrong

`feeGrowthGlobal` includes fees accrued when the tick was outside the range of interest (out-of-range fee revenue). We want range-specific fee intensity, hence `feeGrowthInside(tickRange)`.

### Implied tick range: liquidity-weighted P10/P90

At each snapshot, from the set of active (in-range, liq > 0) positions:
- Sort `tickLower` values weighted by position liquidity
- `P10_tick` = 10th percentile of liquidity-weighted `tickLower` distribution
- `P90_tick` = 90th percentile of liquidity-weighted `tickUpper` distribution
- This covers the core 80% of liquidity, excluding outlier wide-range positions

The tick data for these percentile ticks is already available — they are position boundaries that we already batch-read via Multicall3.

### Data already available

| Data | Source | Status |
|------|--------|--------|
| Position tick ranges | `data/position_registry.csv` (83K positions) | Complete |
| Daily block numbers | `data/daily_blocks.csv` (1400+ days) | Complete |
| Pool state per block | Multicall3 batch reads | Existing code |
| Tick feeGrowthOutside | Multicall3 batch reads | Existing code |
| Per-position feeGrowthInsideLast | Multicall3 batch reads | Existing code |

---

## Part 1: Compute Fee Compression Time Series

### Task 1: Create `compute_fee_compression.py` from existing variance script

**Files:**
- Copy from: `data/compute_fee_variance_sample.py`
- Create: `data/compute_fee_compression.py`
- Output: `data/fee_compression_sample.csv`

**Step 1: Copy the existing script**

```bash
cp data/compute_fee_variance_sample.py data/compute_fee_compression.py
```

**Step 2: Add the implied tick range computation**

Replace the Step 6 block (lines 166-206) in `compute_variance_at_block()` with:

```python
def compute_fg_inside(tick_current, fg_global0, fg_global1, lower_fgo, upper_fgo):
    """Compute feeGrowthInside for a tick range [tl, tu] given outside values."""
    lower_fgo0, lower_fgo1 = lower_fgo
    upper_fgo0, upper_fgo1 = upper_fgo
    # current tick is between tl and tu (we only call this for in-range)
    fg_inside0 = (fg_global0 - lower_fgo0 - upper_fgo0) % UINT256_MAX
    fg_inside1 = (fg_global1 - lower_fgo1 - upper_fgo1) % UINT256_MAX
    return fg_inside0, fg_inside1
```

New Step 6 logic:

```python
# Step 6: Compute fee compression

# 6a: Per-position feeGrowthInside (from tick data, NOT from position's last checkpoint)
fg_inside_per_pos = []  # (fg_inside0, fg_inside1, liquidity)

for tid, tl, tu, liq, fg_inside0_last, fg_inside1_last, owed0, owed1 in active_positions:
    lower_fgo = tick_fgo.get(tl, (0, 0))
    upper_fgo = tick_fgo.get(tu, (0, 0))
    fg_in0, fg_in1 = compute_fg_inside(tick_current, fg_global0, fg_global1, lower_fgo, upper_fgo)
    fg_inside_per_pos.append((fg_in0, fg_in1, float(liq)))

# 6b: Implied tick range [P10_tickLower, P90_tickUpper] liquidity-weighted
liq_arr = np.array([x[2] for x in fg_inside_per_pos])
tl_arr = np.array([tl for _, tl, _, _, _, _, _, _ in active_positions])
tu_arr = np.array([tu for _, _, tu, _, _, _, _, _ in active_positions])

# Liquidity-weighted percentiles
total_liq = liq_arr.sum()
cum_weights_tl = np.cumsum(liq_arr[np.argsort(tl_arr)]) / total_liq
p10_tick = int(np.sort(tl_arr)[np.searchsorted(cum_weights_tl, 0.10)])

cum_weights_tu = np.cumsum(liq_arr[np.argsort(tu_arr)]) / total_liq
p90_tick = int(np.sort(tu_arr)[np.searchsorted(cum_weights_tu, 0.90)])

# 6c: feeGrowthInside for implied range (P10, P90 ticks are position boundaries → already in tick_fgo)
p10_fgo = tick_fgo.get(p10_tick, (0, 0))
p90_fgo = tick_fgo.get(p90_tick, (0, 0))
range_fg0, range_fg1 = compute_fg_inside(tick_current, fg_global0, fg_global1, p10_fgo, p90_fgo)

# 6d: Liquidity-weighted average of per-position feeGrowthInside
weighted_fg0 = sum(fg0 * l for fg0, _, l in fg_inside_per_pos) / total_liq
weighted_fg1 = sum(fg1 * l for _, fg1, l in fg_inside_per_pos) / total_liq

# 6e: Fee compression (in Q128 space, then USD-denominated)
compression0 = (range_fg0 - int(weighted_fg0)) % UINT256_MAX
compression1 = (range_fg1 - int(weighted_fg1)) % UINT256_MAX

# Convert to USD using price
compression_usd = float(compression0) / Q128 + float(compression1) * float(price_x128) / (Q128 * Q128)

return compression_usd, len(fg_inside_per_pos), p10_tick, p90_tick
```

**Step 3: Update CSV output fields**

```python
fieldnames = ["date", "block_number", "fee_compression", "num_positions", "p10_tick", "p90_tick"]
```

**Step 4: Run the computation**

```bash
python data/compute_fee_compression.py
```

Expected: ~208 rows, ~2.5 hours (same RPC load as variance script).

**Step 5: Validate output**

```python
import pandas as pd
df = pd.read_csv("data/fee_compression_sample.csv")
print(f"Rows: {len(df)}, Zeros: {(df.fee_compression == 0).sum()}")
print(df.fee_compression.describe())
print(f"Autocorrelation: {df.fee_compression.autocorr():.3f}")
```

**Step 6: Commit**

```bash
git add data/compute_fee_compression.py
git commit -m "feat: fee compression metric replacing cross-sectional variance"
```

---

## Part 2: Integrate into Econometrics Pipeline

### Task 2: Add fee compression loader to DataHandler

**Files:**
- Modify: `data/DataHandler.py`

**Step 1: Add `load_fee_compression()` function**

```python
def load_fee_compression(path="data/fee_compression_sample.csv", interpolate=True):
    """Load fee compression time series, optionally interpolate to daily."""
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    series = df["fee_compression"]
    if interpolate:
        daily_idx = pd.date_range(series.index.min(), series.index.max(), freq="D")
        series = series.reindex(daily_idx).interpolate(method="cubic")
    return series
```

**Step 2: Commit**

```bash
git add data/DataHandler.py
git commit -m "feat: add fee compression data loader with cubic interpolation"
```

### Task 3: Run two-stage econometric model with fee compression

**Files:**
- Modify: `notebooks/econometrics.ipynb` (add new cell block at end)

**Step 1: Add cells for fee compression integration**

```python
# === FEE COMPRESSION CONGESTION MODEL ===
from data.DataHandler import load_fee_compression

# Load and interpolate fee compression to daily
fee_compression = load_fee_compression()

# Align with existing pool data (inner join on dates)
aligned = pd.DataFrame({
    "feeYield": fee_yield_series,
    "lvr_proxy": lvr_proxy_series,
    "fee_compression": fee_compression,
}).dropna()

print(f"Aligned observations: {len(aligned)}")
print(f"Date range: {aligned.index.min()} to {aligned.index.max()}")
```

**Step 2: Run Stage 1 — UnobservedComponents AR(1)**

```python
from data.Econometrics import LiquidityStateModel

# Stage 1: Extract congestion index from fee compression
stage1 = LiquidityStateModel()
congestion_index = stage1(
    endog=aligned["fee_compression"],
    exog=aligned["lvr_proxy"],
    ar=1
)
print(f"Stage 1 AR(1) coefficient (gamma): {stage1.gamma:.4f}")
```

**Step 3: Run Stage 2 — OLS with HC1**

```python
from data.Econometrics import AdverseCompetitionModel

# Stage 2: Test fee compression impact on fee yield
stage2 = AdverseCompetitionModel()
results = stage2(
    fee_yield=aligned["feeYield"],
    lvr_proxy=aligned["lvr_proxy"],
    congestion=congestion_index
)
print(f"delta_2 (congestion): {results.params['congestion']:.6f}")
print(f"p-value: {results.pvalues['congestion']:.6f}")
print(f"R-squared: {results.rsquared:.4f}")
```

**Step 4: Acceptance criterion**

```python
delta2 = results.params["congestion"]
pval = results.pvalues["congestion"]
print(f"\n=== HYPOTHESIS TEST ===")
print(f"H0: delta_2 = 0 (no fee compression effect)")
print(f"H1: delta_2 < 0 (fee compression reduces fee yield)")
print(f"delta_2 = {delta2:.6f}, p = {pval:.6f}")
print(f"ACCEPT" if pval < 0.05 and delta2 < 0 else "REJECT")
```

**Step 5: Commit**

```bash
git add notebooks/econometrics.ipynb
git commit -m "feat: two-stage model with fee compression congestion proxy"
```

---

## Acceptance Criteria

1. `fee_compression_sample.csv` has ~208 rows with nonzero compression values
2. Fee compression time series is stationary (ADF p < 0.05)
3. Stage 2 δ₂ is statistically significant (p < 0.05) with negative sign
4. If δ₂ is significant → proceed to derivative pricing with fee compression as congestion input
5. If δ₂ is not significant → revisit metric definition (log transform, different percentile range, etc.)
