# Adverse Competition Impact Test — Design

**Date:** 2026-02-28
**Status:** Approved

---

## Goal

Prove that the congestion index ΔI_t (large LP repositioning unexplained by market state) has a **negative, statistically significant** impact on LP fee-adjusted returns, **orthogonal to LVR** (adverse selection from informed traders).

## Core Claim

Large LPs capture fee revenue inequitably by concentrating liquidity around the active tick. This is **adverse competition** (LP-vs-LP), distinct from **adverse selection** (trader-vs-LP / LVR). The congestion index ΔI_t captures this repositioning signal. When ΔI_t rises, fee income that passive LPs *should* earn — given the volume being traded — is reduced.

## Two-Stage Estimation

### Stage 1: Extract ΔI_t (already implemented — `LiquidityStateModel`)

```
ΔL_t/L_{t-1} = β₁(ΔP_t/P_{t-1}) + β₂(txActivity_t) + e_t
e_t = γe_{t-1} + v_t
ΔI_t ≡ e_t
```

- Market state A_t = β₁(ΔP/P) + β₂(txActivity) strips out price-driven liquidity changes
- γ = 0.78 confirms ΔI_t is persistent and stationary (structural parameter)
- Both β coefficients significant at p < 0.001 on V3 USDC/WETH (1,731 obs)

### Stage 2: Adverse competition impact (new — `AdverseCompetitionModel`)

**Step 2a — Residualize fee yield on volume (strip LVR-correlated component):**

```
fee_yield_t = α + δ₁(volume_t/TVL_t) + η_t
```

- fee_yield_t = feesUSD_t / tvlUSD_t
- volume_t/TVL_t is the LVR-correlated driver of fee income
- η_t = fee yield unexplained by volume — orthogonal to LVR by construction

**Step 2b — Test congestion impact on residual fee yield:**

```
η_t = μ + δ₂·ΔI_t + ε_t
```

- **Success criterion: δ₂ < 0 and p < 0.05**
- δ₂ < 0 means: when congestion rises, fee income drops beyond what volume explains
- This is the adverse competition risk premium — pure LP-vs-LP effect

## Why Orthogonal to LVR

- Stage 1 strips ΔP/P from liquidity changes → ΔI_t is orthogonal to price movement
- Stage 2a strips volume/TVL from fee yield → η_t is orthogonal to volume-driven fees
- LVR depends on price movement and volume. Both are removed.
- What remains: the pure effect of LP repositioning (ΔI_t) on fee capture quality (η_t)

## Components

### AdverseCompetition (frozen dataclass)

```python
@dataclass(frozen=True)
class AdverseCompetition:
    _delta: float              # δ₂ — congestion impact on residual fee yield
    _residual: TimeSeries      # η_t — fee yield orthogonal to LVR
    _result: object            # raw statsmodels OLS result (Step 2b)
```

### Free function accessors

```python
def delta_coeff(ac: AdverseCompetition) -> float
def residual(ac: AdverseCompetition) -> TimeSeries
def ols_result(ac: AdverseCompetition) -> object
```

### AdverseCompetitionModel (callable)

```python
class AdverseCompetitionModel:
    def __call__(
        self,
        fee_yield: TimeSeries,      # feesUSD / tvlUSD
        volume_ratio: TimeSeries,   # volumeUSD / tvlUSD
        congestion: TimeSeries      # ΔI_t from Stage 1
    ) -> AdverseCompetition
```

Internally:
1. OLS: fee_yield ~ volume_ratio → extract η_t
2. OLS with HC1 robust SEs: η_t ~ ΔI_t → extract δ₂
3. Return frozen AdverseCompetition

### Caller composition (notebook / tests)

```python
from data.DataHandler import PoolEntryData, feesUSD, tvlUSD, volumeUSD, div, delta, priceUSD, lagged, txCount, normalize
from data.Econometrics import LiquidityStateModel, AdverseCompetitionModel, state, delta_coeff, residual
from data.UniswapClient import UniswapClient, v3

pool_data = PoolEntryData(V3_USDC_WETH, client=UniswapClient(v3()))(n)

# Stage 1
endog = div(delta(tvlUSD(pool_data)), lagged(tvlUSD(pool_data)))
exog = market_state(pool_data)
ls = LiquidityStateModel()(endog=endog, exog=exog)

# Stage 2
fy = div(feesUSD(pool_data), tvlUSD(pool_data))
vr = div(volumeUSD(pool_data), tvlUSD(pool_data))
ac = AdverseCompetitionModel()(fee_yield=fy, volume_ratio=vr, congestion=state(ls))

delta_coeff(ac)  # δ₂ < 0 ?
```

## Tests

### TestAdverseCompetitionAccessors (unit, mock data)
- `test_delta_returns_float`
- `test_residual_returns_series`
- `test_ols_result_returns_value`
- `test_frozen`

### TestAdverseCompetition (real V3 USDC/WETH data)
- `test_delta_negative` — δ₂ < 0
- `test_delta_significant` — p < 0.05
- `test_residual_orthogonal_to_volume` — corr(η_t, volume/TVL) ≈ 0

## Data

- Pool: V3 USDC/WETH `0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640`
- 1,760 days, 11M transactions
- All pool-level daily data — no position reconstruction needed

## Files

- Modify: `data/Econometrics.py` — add AdverseCompetition, AdverseCompetitionModel, accessors
- Modify: `tests/test_Econometrics.py` — add TestAdverseCompetitionAccessors, TestAdverseCompetition
- Modify: `notebooks/econometrics.ipynb` — add Stage 2 results + plots
