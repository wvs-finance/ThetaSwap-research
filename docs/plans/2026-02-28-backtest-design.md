# Congestion Hedge Backtest — Design

**Date:** 2026-02-28
**Status:** Approved

---

## Goal

Demonstrate that a passive LP can hedge congestion risk using a congestionToken with sigmoid payoff, showing variance reduction and improved cumulative P&L on historical V3 USDC/WETH data.

## Audience

Investor / pitch deck. Visual, outcome-focused, dollar impacts, clean charts.

## Architecture

Notebook first, extract later. Everything in `notebooks/backtest.ipynb` — self-contained, investor-readable. Backtest module (`backtest/`) can be extracted once validated.

## Data

- Pool: V3 USDC/WETH `0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640`, 5 bps fee tier
- 1,760 days, 11M transactions
- Daily frequency, pool-level aggregates
- Uses existing `PoolEntryData` + `LiquidityStateModel` to extract ΔI_t

## LP Position

Passive full-range LP with $1M notional. No rebalancing, no tick-range assumptions.

- Daily fee income: `fee_yield_t × Notional` where `fee_yield_t = feesUSD_t / tvlUSD_t`
- Exposed to congestion risk: δ₂ = -0.002 per unit ΔI_t (proven in Stage 2)

## Hedge Mechanism

### Sigmoid Payoff

```
p(I) = 1 / (1 + e^{-I/λ})           — marginal price
φ(I) = λ·ln(1 + e^{I/λ})            — accumulated payoff (integrated sigmoid)
I_t  = Σ_{s=1}^{t} ΔI_s             — cumulative congestion index
```

λ calibrated from data: λ = std(I_t), so sigmoid operates in its non-linear region over the observed congestion range.

### Daily P&L Components

```
ΔPnL_fees_t  = fee_yield_t × Notional           — LP fee income
ΔPnL_hedge_t = N × [φ(I_t) - φ(I_{t-1})]       — congestionToken payoff
ΔPnL_hedged_t = ΔPnL_fees_t + ΔPnL_hedge_t      — net hedged P&L
```

### Hedge Ratio

Minimum variance hedge, estimated on 90-day rolling window:

```
N = -Cov(ΔPnL_fees, Δφ) / Var(Δφ)
```

This is a regression-based hedge ratio — the coefficient from regressing fee P&L changes on sigmoid payoff changes.

## Notebook Structure

~12 cells across 6 sections:

### 1. Setup & Data (code)
- Load pool data via `PoolEntryData(V3_USDC_WETH, client=UniswapClient(v3()))`
- Fit `LiquidityStateModel` on full sample
- Extract ΔI_t = `state(ls)`, compute cumulative I_t = cumsum(ΔI_t)

### 2. LP Position (code)
- Define Notional = $1M
- Compute `fee_yield_t = feesUSD / tvlUSD`
- Compute `ΔPnL_fees_t = fee_yield_t × Notional`

### 3. Sigmoid Payoff (code)
- Calibrate λ = std(I_t)
- Define `φ(I) = λ * np.log(1 + np.exp(I / λ))`
- Compute `Δφ_t = φ(I_t) - φ(I_{t-1})`

### 4. Hedge Construction (code)
- Rolling 90-day window: `N_t = -Cov(ΔPnL_fees, Δφ) / Var(Δφ)`
- Compute `ΔPnL_hedge_t = N_t × Δφ_t`
- Compute `ΔPnL_hedged_t = ΔPnL_fees_t + ΔPnL_hedge_t`

### 5. Cumulative P&L Chart (code + plot)
- Line chart: cumulative unhedged vs hedged P&L
- X-axis: Date, Y-axis: Cumulative P&L ($)
- Two lines: Unhedged (dark `#1a1a1a`), Hedged (gray `#666666`)
- Shows divergence during high-congestion periods

### 6. Variance Reduction (code + plot)
- Compute: `var_reduction = 1 - Var(hedged) / Var(unhedged)`
- Annualized volatility: unhedged vs hedged
- Bar chart or single stat display
- Summary markdown: "The congestionToken hedge reduces fee yield variance by X%"

## Chart Aesthetics

Same monochrome style as econometrics notebook:
- Font: Courier New, monospace, size 12
- Colors: `#1a1a1a`, `#666666`, `#999999`, `#bbbbbb`
- Background: `#fafaf5`
- Grid: `#cccccc`, 0.5px
- Axes: black borders, mirror=True

## Key Outputs

1. **Cumulative P&L chart** — visual proof the hedge works
2. **Variance reduction %** — quantified risk reduction
3. **Annualized volatility comparison** — unhedged vs hedged

## Files

- Create: `notebooks/backtest.ipynb`
- Read-only: `data/Econometrics.py`, `data/DataHandler.py`, `notes/payoff_notes.md`
