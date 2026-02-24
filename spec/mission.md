# Fee Compression Swap Research Mission

**Version:** 1.0  
**Last Updated:** 2026-02-24  
**Status:** Active Research

---

## Executive Summary

**Goal:** Develop a research framework to validate the fee compression swap hypothesis by implementing econometric analysis of LP profitability under monopolistic vs competitive conditions in CFMMs.

**Purpose:** Enable hedging of crowd-sourced competition externalities from sophisticated liquidity providers to retail/passive liquidity providers. The higher goal is creating hedging mechanisms, enhancing DeFi composability, and promoting DeFi democratization.

**Core Innovation:** Define and tokenize the **Price of Competition** in CFMMs as tradable payoffs.

---

## Part I: Purpose and Model Development Implications

### 1.1 The Fundamental Problem

**Observation:** In CFMMs with pro-rata fee allocation:
- More LPs → More total liquidity but lower per-LP profit
- Sophisticated LPs (JIT, active managers) extract rents from passive LPs
- No existing instrument allows passive LPs to hedge this competition risk

**Research Question:**
Can we construct an observable,tradable measure of LP competition that enables hedging?

### 1.2 The Proposed Solution

**Fee Compression Swap (FCS):** A derivative that pays based on realized fee compression:

```
Π^FCS = f(variance of fee compression ratio)

where:
fee compression ratio = feeGrowth_monopolistic / feeGrowth_competitive
```

**Key Insight:** The variance of fee compression across positions at a point in time captures the
**Price of Anarchy** (P_{#LP}):

```
ln(variance_t(fee_ratio)) ≈ ln(P_{#LP_t})

where:
P_{#LP} = E^Q[π^monopolistic / π^competitive]
```

### 1.3 Model Development Implications

**From this purpose, the model must:**

1. **Observable Construction:** Build on-chain observables from Uniswap V3 state variables
   - `feeGrowthOutside` (monopolistic counterfactual)
   - `feeGrowthInside` (competitive reality)
   - Combine into fee compression ratio

2. **Classification Framework:** Distinguish monopolistic vs competitive LPs
   - JIT detection (monopolistic)
   - Passive detection (competitive)
   - Cross-sectional filters (size, duration, volatility-awareness)

3. **Variance Calculation:** Compute cross-sectional variance at each time point
   - Across all positions in a tick range
   - Time-series of variance captures competition dynamics

4. **Validation Mechanism:** Test the core claim
   - Regress ln(variance) on ln(P_{#LP})
   - Verify coefficient ≈ 1, intercept ≈ 0

5. **Payoff Design:** Enable CFMM implementation
   - Linear variance swap (MVP)
   - Log payoff (theoretical match)
   - Digital (binary hedging)

---


