# Structural Fee Compression Proxy: Design

## Problem

The direct on-chain computation of `FeeCompression = feeGrowthInside(range) - avg(feeGrowthInside(position_i))` fails because:
1. Per-position `feeGrowthInside` values are up to 2^256 — float64 arithmetic loses ~130 bits of precision in weighted averages
2. Full position-level batched RPC takes ~2.5 hours per 208-sample run
3. JIT LPs are invisible at daily snapshots (liq=0), so cross-sectional data only captures passive LP heterogeneity — which is tiny (variance CV < 1e-3)

## Solution: Hybrid Structural Proxy

Compute `feeGrowthInside(range)` exactly on-chain (5 RPC calls, seconds per block), then estimate `passive_capture_rate` from structural parameters — all derivable from existing data.

```
FeeCompression_t = feeGrowthInside(range_t) × (1 - passive_capture_rate_t)
```

### Theoretical Foundation

**MACRA24:** Competitive LP profit `Π^competitive ∝ baseDemand / N_LPs`.
- **baseDemand** (informed trading flow from volume) is POSITIVE for passive LP revenue — more volume = more fees to capture
- **N_LPs** is NEGATIVE — more LPs = revenue split more ways = lower per-LP profit
- JIT LPs temporarily inflate effective N during high-fee moments, depressing per-unit returns for passive LPs

**AQFOGAKRE24:** Under competition, passive LPs optimally consider only "base demand." Sophisticated/monopolistic LPs optimally consider volatility. The gap = fee compression from JIT.

### passive_capture_rate: Two-Step Decomposition

**Step 1 — MACRA24 structural base:**
```
pcr_structural = α · baseDemand_t / (1 + β·N_t)
```

| Variable | Definition | Sign | Source |
|----------|-----------|------|--------|
| `baseDemand_t` | `volumeUSD_t / liquidityInRangeUSD_t` | **+** (numerator: more volume = more fees for passive LPs) | PoolEntryData (liquidity × sqrtPrice conversion) |
| `N_t` | Active non-zero-liquidity position count | **-** (denominator: more LPs = lower per-LP share) | position_registry + NPM.totalSupply |
| `α, β` | Structural parameters | Calibrated from 208 sample points | |

**Step 2 — Volatility regime correction:**
```
pcr_correction = γ₁·meanrev_t + γ₂·vol_trending_t
```

| Variable | Definition | Sign | Source |
|----------|-----------|------|--------|
| `meanrev_t` | `-autocorr(ΔP/P, lag=1, window=30)` — negative autocorr = mean-reverting | **+** (mean-reversion benefits passive LPs — fees on both legs) | PoolEntryData price |
| `vol_trending_t` | `\|ΔP/P\|_t - rolling_mean(\|ΔP/P\|, 30)` — excess vol above baseline | **-** (excess vol = informed edge, JIT extraction, passive LPs lose share) | PoolEntryData price |
| `γ₁, γ₂` | Regime coefficients | OLS on Step 1 residuals | |

**Combined:**
```
passive_capture_rate_t = pcr_structural + pcr_correction
```

**Sign summary:**
- `∂pcr/∂baseDemand > 0` — more volume = more fees = higher passive capture
- `∂pcr/∂N < 0` — more LPs = more competition = lower passive capture
- `∂pcr/∂meanrev > 0` — mean-reversion benefits passive LPs
- `∂pcr/∂vol_trending < 0` — excess vol benefits informed/JIT, not passive

## Calibration Pipeline

### Training Data

The 208 `fee_variance_sample.csv` observations provide ground truth. Since cross-sectional variance is tiny, `avg(feeGrowthInside per position) ≈ feeGrowthInside(any single position)`. We compute `feeGrowthInside` for a single reference position (median-liquidity position) as the proxy.

### Steps

1. **One-time lightweight RPC run (~15 min):**
   At each of 208 sample blocks, read 7 values:
   - `slot0` (current tick)
   - `feeGrowthGlobal0X128`, `feeGrowthGlobal1X128`
   - `feeGrowthOutside` at P10 tick and P90 tick (from position_registry)
   - `feeGrowthOutside` at reference position's `tickLower` and `tickUpper`

   Total: 7 calls × 208 blocks = 1,456 RPC calls ≈ 15 min at Alchemy free tier

2. **Compute training targets (arbitrary-precision int arithmetic):**
   - `fgInside_range = feeGrowthInside(P10, P90)` — monopolist rate for implied range
   - `fgInside_ref = feeGrowthInside(ref_tl, ref_tu)` — representative passive LP rate
   - `actual_passive_rate = fgInside_ref / fgInside_range` — ratio computed in Python ints, no float64 loss

3. **Fetch PoolEntryData** for matching 208 dates: volumeUSD, liquidity (in-range), sqrtPrice, priceUSD
   - `liquidityInRangeUSD` derived from PoolEntryData `liquidity` field (active tick liquidity, not TVL which includes out-of-range capital per FLAR feedback)

4. **Step 1 calibration:**
   - Non-linear least squares: `actual_passive_rate ~ α · baseDemand / (1 + β·N)`
   - `scipy.optimize.curve_fit` with bounds `α > 0`, `β > 0`

5. **Step 2 calibration:**
   - Residuals from Step 1
   - OLS: `residuals ~ γ₁·meanrev + γ₂·vol_trending`
   - Verify signs: `γ₁ > 0`, `γ₂ < 0`

6. **Generate daily FeeCompression series:**
   - Apply fitted model to ALL daily PoolEntryData (1760 days)
   - For `feeGrowthInside(range)`: interpolate from 208 on-chain observations (cubic spline) or compute cheaply (5 calls × 1760 days = ~30 min)
   - `FeeCompression_t = feeGrowthInside(range_t) × (1 - passive_capture_rate_t)`

## Integration into Econometrics

Same two-stage model, `FeeCompression_t` replaces TVL-based `ΔL/L`:

**Stage 1:** UnobservedComponents AR(1)
- Observable: `FeeCompression_t`
- Exogenous: `ΔP/P`
- Output: congestion index `s_t`

**Stage 2:** OLS with HC1
- `feeYield ~ |ΔP/P| (LVR proxy) + s_t (congestion)`
- Acceptance: `δ₂ < 0`, `p < 0.05`

## Files

| File | Purpose | Status |
|------|---------|--------|
| `data/compute_fg_inside_range.py` | Lightweight RPC: 5-7 calls/block for feeGrowthInside(range) + reference position | Create |
| `data/structural_proxy.py` | Calibrate passive_capture_rate, generate daily FeeCompression | Create |
| `data/DataHandler.py` | `load_fee_compression()` already exists | Keep |
| `notebooks/econometrics.ipynb` | Add cells for new model run | Modify |

## Acceptance Criteria

1. Calibration R² for `actual_passive_rate ~ structural model` > 0.3
2. `β` coefficient has correct sign (positive = more LPs lowers passive capture via denominator)
3. `γ₁ > 0` (mean-reversion helps passive), `γ₂ < 0` (excess vol hurts passive)
4. Stage 2 `δ₂` statistically significant (p < 0.05) with negative sign
5. Full pipeline runs in < 30 min (vs. 2.5+ hours for direct computation)
