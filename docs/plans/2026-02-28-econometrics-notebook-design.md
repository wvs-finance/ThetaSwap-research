# Econometrics Notebook Update — Design

**Date:** 2026-02-28
**Status:** Approved

---

## Goal

Rewrite `notebooks/econometrics.ipynb` as a paper-style academic presentation of the two-stage adverse competition test, with model rationale, hypothesis tests, statistical and economic significance, relevant monochrome graphs, and explicit connection to the payoff_notes product design.

## Audience

Academic / peer review. Rigorous enough for technical economists.

## Structure

Paper-style: Introduction → Data → Stage 1 → Stage 2 → Economic Significance → Product Design Connection

## Sections

### 1. Introduction (markdown)

**Title:** "Adverse Competition in Concentrated Liquidity AMMs: Evidence from Uniswap V3"

Content:
- Research question: do large LPs capture fee revenue inequitably via liquidity concentration?
- Distinction: adverse competition (LP-vs-LP) vs adverse selection (LVR, trader-vs-LP)
- Two-stage approach: extract congestion index ΔI_t, then test its impact on fee yield orthogonal to LVR
- Key result preview: δ₂ = -0.002, p < 0.001, 1,731 daily observations
- Connection: ΔI_t is the state variable for the congestionToken sigmoid pricing p(I) = σ(I/λ)

### 2. Data (markdown + code)

**Markdown:**
- Pool: V3 USDC/WETH `0x88e6...5640`, 5 bps fee tier
- 1,760 days, 11M transactions
- Variables: tvlUSD, volumeUSD, feesUSD, token0Price, txCount
- Daily frequency, pool-level aggregates

**Code:**
- Load data via `PoolEntryData(V3_USDC_WETH, client=UniswapClient(v3()))` with full lifetime
- Summary statistics table: obs count, mean, std, min, max for all variables

### 3. Stage 1 — Congestion Index Extraction (markdown + code + plot + markdown)

**Markdown (specification):**
- Model: ΔL_t/L_{t-1} = β₁(ΔP_t/P_{t-1}) + β₂(txActivity_t) + e_t, e_t = γe_{t-1} + v_t
- ΔI_t ≡ e_t (congestion index = structural residual)
- Market state A_t strips price-driven and activity-driven liquidity changes
- Hypothesis: 0 < γ < 1 (persistent but stationary)
- Economic motivation: γ > 0 → LP repositioning persists; γ < 1 → sigmoid pricing stays bounded

**Code:**
- Compute endog (ΔL_t/L_{t-1}), exog (ΔP/P, txActivity)
- Fit `LiquidityStateModel()(endog, exog)`
- Display regression summary table
- Print γ with confidence interval

**Plot (3-panel time series, monochrome):**
- Panel 1: ΔL_t/L_{t-1} (liquidity changes)
- Panel 2: Market state E[ΔL_t | A_t] (predicted component)
- Panel 3: ΔI_t (congestion index — structural residual)
- All panels share x-axis (dates), horizontal dashed zero-lines

**Markdown (interpretation):**
- γ = 0.78 — persistent and stationary, confirming structural parameter
- Both β coefficients significant at p < 0.001
- ΔI_t mean ≈ 0 (centered residual)
- Connection to payoff_notes: ΔI_t feeds κ bound |ΔI_t| ≤ κΔL_t

### 4. Stage 2 — Adverse Competition Impact Test (markdown + code + plot + markdown)

**Markdown (specification):**
- Step 2a: Δfee_yield_t = α + δ₁|ΔP_t/P_{t-1}| + η_t
  - Strips LVR-correlated component from fee yield changes
  - Note: fee_yield = fee_rate × volume/TVL identically in V3 (R² = 1), so volume/TVL is degenerate. |ΔP/P| is the correct LVR proxy.
- Step 2b: η_t = μ + δ₂·ΔI_t + ε_t (HC1 robust standard errors)
  - Success criterion: δ₂ < 0 and p < 0.05
- Why orthogonal to LVR:
  - ΔI_t orthogonal to ΔP/P (removed in Stage 1)
  - η_t orthogonal to |ΔP/P| (removed in Step 2a)

**Code:**
- Compute Δfee_yield, |ΔP/P|, congestion from Stage 1
- Fit `AdverseCompetitionModel()(fee_yield=..., lvr_proxy=..., congestion=...)`
- Display OLS summary table (Step 2b)
- Print δ₂ with CI and p-value

**Plot (scatter, monochrome):**
- X-axis: ΔI_t (congestion index)
- Y-axis: η_t (residual fee yield change)
- OLS fit line overlaid
- Title includes δ₂ coefficient and p-value

**Markdown (interpretation):**
- δ₂ = -0.002, z = -3.74, p = 0.0002
- When congestion rises, fee yield drops beyond what LVR explains
- This is the adverse competition risk premium — pure LP-vs-LP effect

### 5. Economic Significance (markdown + code + plot)

**Markdown:**
- Statistical significance alone is insufficient for academic work
- Must demonstrate economic magnitude of δ₂

**Code:**
- 1-std congestion shock → -13.5% of mean fee yield
- Annualized: 3.4pp of 25% annual yield
- $34K/year per $1M TVL
- Tail impacts: P90, P95, P99

**Plot (bar chart or formatted table, monochrome):**
- Congestion percentile vs impact on fee yield (% of mean)
- Shows tail risk: P99 → -45% of mean yield

### 6. Connection to Product Design (markdown)

- ΔI_t is the congestionToken underlying state variable
- Sigmoid payoff: p(I) = 1/(1 + e^{-I/λ}), integrated: φ(I) = λ·ln(1 + e^{I/λ})
- Hedge ratio: N = ΔLP_fees / ΔcongestionToken × Notional
- δ₂ < 0 validates the economic mechanism: congestion creates measurable fee compression, generating hedging demand
- The 5.2% R² confirms congestion is a distinct risk factor, not dominant but real — exactly what a targeted hedge instrument should price

## Chart Aesthetics

- Font: Courier New, monospace, size 12
- Colors: monochrome palette `["#1a1a1a", "#666666", "#999999", "#bbbbbb"]`
- Background: `#fafaf5` (off-white)
- Grid: `#cccccc`, 0.5px
- Axes: black borders, mirror=True
- Zero-lines: dashed `#999999`
- Markers: `#1a1a1a`, opacity 0.5, thin border
- Use existing Plotly `classic` template from current notebook

## Cell Count

~15 cells total: 7 markdown, 5 code, 3 plots

## Files

- Rewrite: `notebooks/econometrics.ipynb`
- Read-only references: `notes/payoff_notes.md`, `data/Econometrics.py`, `data/DataHandler.py`
