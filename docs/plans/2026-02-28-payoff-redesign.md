# CongestionToken Payoff Redesign

**Date:** 2026-02-28
**Status:** Approved

---

## Problem

The current backtest (`notebooks/backtest.ipynb`) shows the congestionToken hedge **amplifies** tail risk:
- CVaR 1%: unhedged $14 → hedged -$82 (-670% worse)
- Median hedge ratio N = 2,246 (wildly unstable)
- Unconditional variance reduction: 2% (negligible)

## Root Cause

The backtest defines `I_t = cumsum(state(ls))`. But `state(ls)` is the smoothed AR(1) latent component from the UnobservedComponents model — it IS the congestion level `s_t`, satisfying `s_t = ρ s_{t-1} + η_t` with ρ = 0.78. This process is **stationary and mean-reverting**.

Cumsumming a stationary process creates an I(1) random walk:
1. `I_t` drifts unboundedly → sigmoid saturates at 1
2. `Δφ` becomes tiny → `Var(Δφ)` → 0 → hedge ratio `N = -Cov/Var` explodes
3. The hedge amplifies exactly the tail events it should protect against

## Fix

Use `s_t = state(ls)` directly as the congestion level. No cumsum.

- `s_t` is bounded (std ≈ 0.043, range roughly [-0.15, 0.15])
- Sigmoid operates in its non-linear region on this range
- `Δφ` has meaningful variance → hedge ratio is stable
- Mean reversion provides natural solvency bounds

## Deliverables

1. **`notes/payoff_notes.md`** — complete rewrite with rigorous derivations
2. **`notebooks/backtest.ipynb`** — fixed hedge showing significant tail risk improvement

## Payoff Notes Structure

### Section 1: Claim Design
- Define `s_t` as the AR(1) latent congestion state from the econometric model
- Connect to `LiquidityStateModel`: `s_t` captures liquidity changes orthogonal to price and activity
- γ = 0.78 means persistent but mean-reverting
- δ₂ = -0.002 means each unit of congestion costs 0.2 bps of fee yield
- 1 congestionToken = 1 unit of delta exposure to `s_t`
- LP token = collateral (SHORT by design — LP value decreases when congestion rises)
- congestionToken = LONG (pays when congestion rises)

### Section 2: Claim Pricing
- Desirable properties: increasing in s, convex in s, bounded (solvency)
- Marginal price: `p(s) = σ(s/λ) = 1/(1 + e^{-s/λ})`
- λ calibrated from data: λ = P75(|s_t|) so sigmoid activates in the tail
- At low congestion: price near 0 (cheap to buy protection)
- At high congestion: price approaches 1 (expensive, but LP needs it most)
- This IS a tail risk hedge: convexity means large shocks get disproportionate payoff

### Section 3: Payoff Functional
- Integrate price: `φ(s) = ∫p(s)ds = λ·ln(1 + e^{s/λ})` (softplus)
- Per Angeris et al. (2021), replicable by CFMM if:
  1. Monotone nondecreasing: ✓ (φ' = σ > 0)
  2. Nonnegative: ✓ (softplus > 0)
  3. Sublinear growth: ✓ (φ(s)/s → 1 as s → ∞, bounded slope)
- No oracle needed — CFMM reserves track φ(s) directly

### Section 4: Solvency / Margin
- Mean reversion of s_t naturally bounds exposure
- Maximum congestion level: s_max = max(|s_t|) over rolling window W
- Margin requirement: M ≥ N · φ(s_max)
- LP token itself serves as collateral
- Auto-liquidation if: LP token value < congestion payoff

### Section 5: CFMM Invariant
- From φ(s) = λ·ln(1 + e^{s/λ}), the trading function:
  `ψ(x, y) = y - λ·ln(1 + e^{x/λ}) = k`
- x = congestionToken reserves, y = collateral reserves
- Price: p(x) = dy/dx = σ(x/λ)
- Reserves bounded: x ∈ (-∞, ∞), y ∈ (k, ∞)

### Section 6: Hedge Ratio
- Structural, derived from δ₂ (not statistical minimum-variance):
  `N = |δ₂| × Notional / σ(s_t/λ)`
- With δ₂ = -0.002, Notional = $1M, σ ≈ 0.5: N ≈ 4,000
- Bounded and smooth (sigmoid denominator never zero)
- Adapts to congestion level: higher congestion → lower N (sigmoid closer to 1)
- Targets specifically the adverse competition channel, not all fee volatility

## Backtest Fix

Cell 2 changes:
```python
# BEFORE (wrong):
I_t = delta_I.cumsum()
lam = I_t.std()

# AFTER (correct):
s_t = delta_I  # AR(1) state IS the congestion level, no cumsum
lam = s_t.abs().quantile(0.75)  # activate sigmoid in tail
```

Hedge ratio changes:
```python
# BEFORE (statistical, unstable):
N_t = -(rolling_cov / rolling_var)

# AFTER (structural, bounded):
delta_2 = -0.002  # from AdverseCompetitionModel
sigma_s = 1 / (1 + np.exp(-s_t / lam))
N_t = abs(delta_2) * NOTIONAL / sigma_s
```

## References

- Angeris, Evans, Chitra. "Replicating Monotonic Payoffs Without Oracles." arXiv:2111.13740, 2021.
- Stage 1 & 2 econometric results from `notebooks/econometrics.ipynb`
