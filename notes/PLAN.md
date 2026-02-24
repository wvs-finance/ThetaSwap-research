# ThetaSwap Range Accrual Note Implementation Plan

Based on existing product documentation (payoff-spec.tex, payoff-pricing.tex, payoff-replication.tex) and the requirement to start with numerical examples and build progressively.

## Phase 1: Mathematical Foundation & Specification

### Task 1: Complete wsETH/wBTC Numerical Example
- [ ] Use exact parameters from payoff-spec.tex: strikeInterval = [-120000, -80000], accrualFrequency = 1 block, observationLength = perpetual
- [ ] Calculate initial LP position: √(1² × 30000) = 173.205 wsETH, 1/√30000 = 0.0057735 wBTC
- [ ] Determine fair X multiplier using digital option pricing: X = 1.0 / (D_b - D_a)
- [ ] Simulate 10 swaps: 4 in band, 6 out of band
- [ ] Calculate total feeGrowth = 0.3% × 10 = 0.003
- [ ] Verify RAN payoff = 0.003 × (4/10 - 6/10) = -0.0006
- [ ] Document funding fee = |RAN payoff| = 0.0006 as replication cost

### Task 2: Formalize Digital Option Decomposition
- [ ] Implement formula from payoff-pricing.tex: Π^TAN = Θ/N × ∑(1_{P_i > ψ_b} - 1_{P_i > ψ_a})
- [ ] Define digital call pricing function using martingale argument
- [ ] Specify discounted pricing: P_Π(0,T) = e^{-rT} × Θ/N × ∑e^{r·T_i} × (P_D(0,T_i,ψ_b) - P_D(0,T_i,ψ_a))
- [ ] Document calibration requirements for implied volatility

### Task 3: No-Arbitrage Pricing Invariant
- [ ] Implement rule from payoff-replication.tex: price(RAN) = price(LP) - price(perpetual) + price(call)
- [ ] Verify alternative formulation: price(RAN) = sum(discounted(price(option,tickLower)) - discounted(price(option,tickUpper)))
- [ ] Define invariant for CFMM trading function
- [ ] Document how this ensures perpetual market stability

## Phase 2: Core Instrument Specification

### Task 4: Range Accrual Note Structure (R1-R7)
- [ ] R1: Accrues coupon in each period (Uniswap design fulfillment)
- [ ] R2: Pays out coupon at end of block (start of new block)
- [ ] R3: strikeInterval can be changed dynamically
- [ ] R4: Accrued coupon can change across periods (Dynamic Fees)
- [ ] R5: Entitles holder to coupon payments
- [ ] R6: Entitles holder to payment of principal
- [ ] R7: Calculates payoff requiring whole trajectory of underlying price

### Task 5: Single-Period Payoff Specification
- [ ] Implement Π^TAN = Θ × (∑ⁿ 1_{ψ_b ≤ P(Δ_i) ≤ ψ_a}) / N
- [ ] Define variables: Θ = feeGrowthInside, N = observation periods
- [ ] Specify requirements for price trajectory calculation
- [ ] Document example: 6 block wsETTH/WBTC feeGrowth

### Task 6: Multi-Period Extension
- [ ] Implement Π^TAN = ∑ʲ Θ_j × (∑ⱼ ∑ᵢ 1_{ψ_b ≤ P(Δ_ij) ≤ ψ_a}) / N_j
- [ ] Define hierarchical observation periods N = (N_j)^d
- [ ] Specify dynamic fee adjustment across periods
- [ ] Document extension requirements for time-frequency conversion

## Phase 3: Implementation Architecture

### Task 7: CFMM Integration Pattern
- [ ] Design trading function based on primitivefinance/rmm-core replication math
- [ ] Specify pool reserves: (1.0 LP token, X RAN tokens)
- [ ] Define initial price enforcement mechanism
- [ ] Document how trading fees serve as funding rate

### Task 8: LP Position Integration
- [ ] Specify hook for CLAMM liquidity provision
- [ ] Define lending mechanism: LP position → CFMM(TICK_RANGE_ACCRUAL_NOTE)
- [ ] Document collateral-free structure (per requirements)
- [ ] Specify how feeGrowthInside is captured from Uniswap V3

### Task 9: Tokenization Strategy
- [ ] Evaluate ERC1155 vs ERC6909 for range accrual notes
- [ ] Define token metadata structure for strike interval, accrual frequency
- [ ] Specify how X multiplier is encoded in token supply
- [ ] Document minting/burning mechanics for position closure

## Phase 4: Progressive Development

### Task 10: Minimal Viable Specification
- [ ] Start with single-period, fixed strike interval
- [ ] Implement basic accrual calculation
- [ ] Verify no-arbitrage invariant
- [ ] Create first numerical example validation

### Task 11: Multi-Period Support
- [ ] Add observation frequency parameter
- [ ] Implement dynamic fee calculation
- [ ] Test with 6-block and 24-block examples
- [ ] Verify path-dependent payoff calculation

### Task 12: Extension Mechanisms
- [ ] Barriers extension: knock-in/knock-out barriers
- [ ] Callable extension: short call options on RAN
- [ ] BasketUnderlier extension: multi-asset vault integration
- [ ] FloatingRangeAccrual extension: dynamic fee policies

### Task 13: Verification Framework
- [ ] Create mathematical verification checklist
- [ ] Define test scenarios for different market views
- [ ] Document three-party balance verification (Seller, Buyer, CFMM)
- [ ] Specify invariant testing procedures

## Deliverables
- [ ] Complete numerical example with exact calculations
- [ ] Formal specification document in @notes/PLAN.md
- [ ] Updated product documentation in product/ directory
- [ ] Implementation roadmap with bite-sized tasks
- [ ] Verification checklist for financial correctness

This plan follows the sequence implied by the existing product documents and focuses on building the financial instrument specification progressively, starting from the mathematical foundations and moving to implementation architecture.