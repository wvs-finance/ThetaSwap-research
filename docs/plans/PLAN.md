## Part II: Paper Reading Guide - Questions by Category

### 2.1 Structural Econometrics Modeling

**Paper:** [To be identified - foundational econometrics]

**Purpose:** Establish requirements for specifying econometric models and running regressions.

**Questions to Answer:**

#### Modeling Questions:
1. What are the identification assumptions for structural econometric models?
5. What functional forms are appropriate for fee growth relationships?

**Deliverable:** Checklist of requirements before specifying econometric model.

---

### 2.2 JIT Liquidity - Capponi et al.

**Paper:** `refs/capponi_jit_liquidity_2024.pdf`

**Purpose:** Understand JIT liquidity as the monopolistic LP proxy.

**Questions to Answer:**

#### Modeling Questions:
1. How JIT relates to monopolisitc LP ?
2. What are the optimality conditions for JIT LPs?
4. What is the profit function for JIT vs passive LPs?
4.1 Does this profit ratios share the samee charactersitics as the ratios between monopolisitc/competiotive
5. What equations describe JIT impact on passive LP profitability?

**Key Equations to Extract:**
```
π^JIT = \pi^{monopoly}
π^passive = \pi^{under-competition}

Hypothesis: π^JIT / π^passive = \pi^{monopoly}/ \pi^{under competition} = P_{#LP}= O(#LP) (systematically)
```

**Deliverable:** JIT classification algorithm and profit estimation formula.

---

### 2.3 Implied Volatility of Fees

**Paper:** [To be identified - fee volatility / implied vol from options]

**Purpose:** Understand how to derive implied volatility from fee dynamics.

**Questions to Answer:**

#### Modeling Questions:
1. How is fee volatility defined in CFMMs?
2. How to extract implied volatility from pool data?
3. What is the relation between fee vol and the derivative we are bultding ?
5. How does optimal tick range relate to implied vol?

**Key Equations to Extract:**
```
optimal_tick_range = f(implied_volatility, fee_rate, volume)

Hypothesis: Sophisticated LPs set tick_range proportional to implied_vol
```

**Deliverable:** Implied volatility estimation procedure and optimality test.

---

### 2.4 FLAIR: Metric for LP Competitiveness

**Paper:** [To be identified - FLAIR or similar competitiveness metric]

**Purpose:** Connect LP competitiveness metrics to Price of Anarchy.

**Questions to Answer:**

#### Modeling Questions:
1. What is the FLAIR metric definition?
2. How does it measure LP competitiveness?
3. What is the theoretical relationship: FLAIR → P_{#LP}?
4. How does FLAIR relate to fee compression?
5. What is the structural model linking competitiveness to profits?

#### Econometrics Questions:
1. How to compute FLAIR from on-chain data?
2. What is the empirical distribution of FLAIR?
3. How does FLAIR vary with number of LPs?
4. What is the regression: π^i = α + β·FLAIR^i + ε^i?
5. How to validate FLAIR as competitiveness proxy?

**Key Equations to Extract:**
```
FLAIR^i = f(position characteristics, market conditions)

Hypothesis: FLAIR correlates with fee compression ratio
```

**Deliverable:** FLAIR calculation method and validation regression.

---

### 2.5 Structural Econometrics: Competition Modeling

**Paper:** [Synthesis - competition in structural models]

**Purpose:** Establish econometric modeling principles for competition.

**Questions to Answer:**

#### Modeling Questions:
1. What is the structural model of competition in CFMMs?
2. How does entry/exit affect equilibrium profits?
3. What is the equilibrium condition: π^i = π^j for all i,j?
4. How does pro-rata allocation affect competition intensity?
5. What is the dynamic model of LP positioning?

#### Econometrics Questions:
1. What is the baseline regression specification?
   ```
   log_fee_ratio_i = α + β·1_{retail(i)} + γ·X_i + ε_i
   ```
2. What are the identification assumptions?
3. How to handle selection bias (only observe active positions)?
4. What fixed effects are needed (position, time, pool)?
5. How to test for structural breaks?

**Key Equations to Extract:**
```
Baseline: log(π^i) = α + β·type_i + γ·controls_i + δ_t + ε_i

Competition effect: ∂π^i/∂#LPs < 0

Price of Anarchy: P_{#LP} = π^monopoly / π^competitive
```

**Deliverable:** Complete econometric specification with identification strategy.

---

## Part III: Data, Assumptions, and Equations

### 3.1 Data Requirements

**On-Chain Data (Uniswap V3 Subgraph):**

| Variable | Source | Frequency | Use |
|----------|--------|-----------|-----|
| `positions` | Position entity | Event-based | Position-level analysis |
| `liquidity` | Position.liquidity | Per position | Size classification |
| `tickLower`, `tickUpper` | Position | Per position | Tick range |
| `feeGrowthInside0LastX128` | Position | Per position | Competitive fee growth |
| `feeGrowthOutside0X128` | Tick | Per tick | Monopolistic fee growth |
| `sqrtPriceX96` | Pool.slot0 | Per block | Price conversion |
| `swaps` | Swap entity | Per swap | Volume, volatility |
| `mints`, `burns` | Mint/Burn entity | Event-based | JIT detection |

**Derived Variables:**

### 3.2 Assumptions

**Economic Assumptions:**

1. **Pro-Rata Fee Allocation:** CFMMs allocate fees proportionally to liquidity share
2. **Rational LPs:** LPs maximize expected profit (with heterogeneous beliefs/technology)
3. **Monopolistic Proxy:** JIT liquidity approximates monopolistic behavior
4. **Competitive Proxy:** Passive LPs approximate competitive outcome
5. **Efficient Tick Setting:** Sophisticated LPs set optimal tick ranges based on implied vol

**Econometric Assumptions:**

1. **Exogeneity:** Number of LPs is exogenous conditional on controls (or use IV)
2. **Stationarity:** Fee compression ratios are stationary (or cointegrated)
3. **No Measurement Error:** feeGrowth data is accurately reported on-chain
4. **Correct Classification:** JIT/passive filters correctly identify LP types
5. **Linear Approximation:** Log approximation holds for small deviations

**Technical Assumptions:**

1. **Oracle Reliability:** FeeGrowth oracle reports accurate data
2. **Tick Spacing:** Standard tick spacing (e.g., 10, 60) for interpolation
3. **Numeraire Conversion:** Q96/Q128 fixed-point arithmetic is sufficient
4. **Variance Calculation:** Cross-sectional variance is well-defined (N ≥ 2)

---

### 3.3 Core Equations

**Fee Growth Conversion (to numeraire):**

```
$monopolisticFeeGrowth = sqrtPriceX96 × feeGrowthOutside0x128 + feeGrowthOutside1x128

$feeGrowthInside_pos = sqrtPriceX96 × feeGrowthInside0x128_pos + feeGrowthInside1x128_pos
```

**Fee Compression Ratio:**

```
fee_ratio_i = $monopolisticFeeGrowth / $feeGrowthInside_pos

log_fee_ratio_i = ln(fee_ratio_i)
```

**Cross-Sectional Variance:**

```
variance_t = (1/N) × Σ^N (log_fee_ratio_i - mean_t)²

where: mean_t = (1/N) × Σ^N log_fee_ratio_i
```

**Price of Anarchy:**

```
P_{#LP_t} = π^monopolistic_t / π^competitive_t

where:
π^monopolistic_t = mean(feeGrowth for JIT positions at t)
π^competitive_t = mean(feeGrowth for passive positions at t)
```

**Core Claim (to validate):**

```
H0: ln(variance_t) = ln(P_{#LP_t}) + ε_t

Test: Regress ln(variance_t) on ln(P_{#LP_t})
Expected: coefficient ≈ 1, intercept ≈ 0, R² > 0.5
```

**Baseline Regression (determinants):**

```
log_fee_ratio_i = α + β·1_{retail(i)} + γ₁·log(tick_range_i) 
                + γ₂·log(size_i) + γ₃·moneyness_i + γ₄·volatility_t + δ_t + ε_i

Interpretation:
β > 0: Retail suffers more fee compression
γ₁: Effect of tick range width
γ₂: Effect of position size
γ₃: Effect of moneyness (ITM/OTM)
γ₄: Effect of market volatility
```

**Optimal Liquidity (from theory):**

```
liquidity*(tickSpread) = ((#Positions - 1) / #Positions) × 
    (feeGrowth_informed / feeGrowth_uninformed - hedging_cost)

Hypothesis: Optimal liquidity decreases with #LPs (competition effect)
```

**FCS Payoff (derivative specification):**

```
Linear: Π^FCS = Notional × (realized_variance - strike_variance)

Log: Π^FCS = Notional × (ln(realized_variance) - ln(strike_variance))

Digital: Π^FCS = Notional × 1_{realized_variance > strike_variance}
```

---

## Part IV: Econometric Modeling Principles

### 4.1 Model Specification Sequence

**Step 1: Exploratory Analysis**
```python
# Visualize distributions
hist(log_fee_ratio)
boxplot(log_fee_ratio by retail/institutional)

# Summary statistics
mean(log_fee_ratio_retail) vs mean(log_fee_ratio_institutional)
variance(log_fee_ratio) over time
```

**Step 2: Variance Claim Validation**
```python
# Time-series regression
ln(variance_t) = α + β·ln(P_{#LP_t}) + ε_t

# Hypothesis tests
H0: β = 1, α = 0
Test: F-test for joint hypothesis
```

**Step 3: Cross-Sectional Determinants**
```python
# Baseline regression
log_fee_ratio_i = α + β·1_{retail(i)} + γ·X_i + ε_i

# Inference
t-test on β (is retail coefficient significant?)
R² (how much variation explained?)
```

**Step 4: Panel Data (if available)**
```python
# Two-way fixed effects
log_fee_ratio_it = α_i + β·X_it + δ_t + ε_i

# Estimation
Within estimator (demeaning)
Clustered SEs (by position or time)
```

**Step 5: Robustness Checks**
```python
# Alternative classifications
- JIT threshold: 1 block vs 3 blocks
- Size thresholds: $10K vs $100K

# Alternative specifications
- Use fee_ratio instead of log_fee_ratio
- Use median instead of mean for P_{#LP}

# Subsample analysis
- High volatility periods
- Low volatility periods
- Different pools
```

---

### 4.2 Identification Strategy

**Threats to Identification:**

1. **Endogeneity:** #LPs may be correlated with unobservables
   - Solution: Instrument with exogenous shocks (e.g., protocol upgrades)

2. **Selection Bias:** Only observe active positions
   - Solution: Heckman correction or bounds analysis

3. **Measurement Error:** feeGrowth may be noisy
   - Solution: Use multiple observations, time-averaging

4. **Omitted Variables:** Unobserved LP heterogeneity
   - Solution: Fixed effects, rich controls

5. **Simultaneity:** Fees affect entry, entry affects fees
   - Solution: Lagged independent variables, IV estimation

**Validity Tests:**

1. **Balance Test:** Check if covariates are balanced across retail/institutional
2. **Placebo Test:** Test effect on outcomes that shouldn't be affected
3. **Pre-Trend Test:** Check parallel trends (if panel data)
4. **Overidentification Test:** Test validity of instruments (if IV)

---

### 4.3 Power Analysis

**Minimum Detectable Effect:**

Given:
- Sample size N (positions per day)
- Significance level α = 0.05
- Power 1-β = 0.80
- Standard deviation σ (from pilot data)

```
MDE = (t_α/2 + t_β) × σ / √N

Example:
N = 100 positions/day
σ = 0.5 (standard deviation of log_fee_ratio)
MDE ≈ 0.2 (can detect 20% difference)
```

**Sample Size Calculation:**

```
N = ((t_α/2 + t_β) × σ / δ)²

Where δ = effect size of interest

Example:
δ = 0.1 (want to detect 10% difference)
σ = 0.5
N ≈ 400 positions needed
```

---

## Part V: Implementation Roadmap

### 5.1 Phase 0 - Econometrics Exercise

**Duration:** 2-3 weeks

**Tasks:**
1. [ ] Set up Python environment (pandas, statsmodels, scipy)
2. [ ] Extract data from Uniswap V3 subgraph
3. [ ] Calculate fee compression ratios
4. [ ] Run exploratory analysis
5. [ ] Estimate baseline regressions
6. [ ] Validate variance claim
7. [ ] Document findings

**Deliverables:**
- Jupyter notebook with full analysis
- Summary report with coefficient estimates
- Validation result (does claim hold?)

---

### 5.2 Phase 1 - Oracle & Data Infrastructure

**Duration:** 2 weeks

**Tasks:**
1. [ ] Define fee growth oracle interface
2. [ ] Implement Uniswap V3 oracle (Solidity)
3. [ ] Write oracle tests
4. [ ] Deploy to testnet
5. [ ] Test with mainnet fork

**Deliverables:**
- Working oracle contract
- Test suite with >90% coverage
- Gas cost estimates

---

### 5.3 Phase 2 - Payoff Function Registry

**Duration:** 1 week

**Tasks:**
1. [ ] Define payoff function interface
2. [ ] Implement linear payoff (MVP)
3. [ ] Implement log payoff
4. [ ] Implement digital payoff
5. [ ] Write payoff tests

**Deliverables:**
- Payoff registry contract
- Test vectors for each payoff type
- Gas cost comparison

---

### 5.4 Phase 3 - Perpetual CFMM Core

**Duration:** 3 weeks

**Tasks:**
1. [ ] Design FCS vault architecture
2. [ ] Implement ERC6909 tokenization
3. [ ] Implement funding settlement
4. [ ] Write vault tests
5. [ ] Security audit (internal)

**Deliverables:**
- FCS vault contract
- Integration tests
- Security checklist

---

### 5.5 Phase 4 - Integration & Testing

**Duration:** 2 weeks

**Tasks:**
1. [ ] End-to-end integration tests
2. [ ] Mainnet fork simulations
3. [ ] Gas optimization
4. [ ] Documentation
5. [ ] Testnet deployment

**Deliverables:**
- Full test suite
- Deployment scripts
- User documentation

---

## Part VI: Success Criteria

### 6.1 Research Validation

**Success if:**
- [ ] Variance claim validated (coefficient ≈ 1, R² > 0.5)
- [ ] Retail/institutional difference significant (p < 0.05)
- [ ] Fee compression ratio is observable and calculable
- [ ] Classification algorithm achieves >80% accuracy

**Failure if:**
- Variance claim rejected (coefficient far from 1)
- No significant retail/institutional difference
- Fee growth data too noisy for reliable calculation

---

### 6.2 Derivative Viability

**Success if:**
- [ ] Payoff is replicable (static portfolio or oracle-settled)
- [ ] Market structure is sustainable (natural buyers and sellers)
- [ ] Pricing model is tractable (calibratable to market data)
- [ ] Smart contract implementation is feasible (gas costs < threshold)

**Failure if:**
- Replication is too costly or infeasible
- No natural counterparties (one-sided market)
- Pricing requires unobservable inputs
- Gas costs exceed user willingness to pay

---

### 6.3 Product-Market Fit

**Success if:**
- [ ] Passive LPs express demand for hedging instrument
- [ ] Sophisticated LPs willing to sell protection
- [ ] Risk/reward profile is attractive (Sharpe > 1)
- [ ] Regulatory clarity (not a security)

**Failure if:**
- No demand from either side
- Better alternatives exist (e.g., dynamic LP strategies)
- Regulatory uncertainty blocks deployment

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Fee Compression** | Reduction in per-LP fee revenue due to competition |
| **Price of Anarchy (P_{#LP})** | Ratio of monopolistic to competitive LP profits |
| **JIT Liquidity** | Liquidity minted and burned within same block |
| **Passive LP** | LP providing liquidity for extended periods |
| **feeGrowthOutside** | Fee growth outside a tick (monopolistic counterfactual) |
| **feeGrowthInside** | Fee growth inside a position (competitive reality) |
| **Fee Compression Ratio** | feeGrowth_monopolistic / feeGrowth_competitive |
| **Variance Claim** | ln(variance(fee_ratio)) ≈ ln(P_{#LP}) |

---

## Appendix B: Reference Implementation Checklist

**Before Starting Econometrics:**
- [ ] Understand structural model requirements
- [ ] Identify data sources and extraction method
- [ ] Define classification algorithm (JIT vs passive)
- [ ] Specify baseline regression
- [ ] Plan robustness checks

**Before Starting Implementation:**
- [ ] Econometric validation complete
- [ ] Variance claim supported by data
- [ ] Payoff specification finalized
- [ ] Oracle design reviewed
- [ ] Security model defined

---

## Appendix C: Open Questions

1. **Time Dimension:** Do we have panel data or just cross-sectional?
2. **Monopolistic Weight:** Use weighted average or simple average of feeGrowthOutside?
3. **Classification Threshold:** What JIT threshold (1 block, 3 blocks)?
4. **Size Thresholds:** What USD values for retail vs institutional?
5. **Volatility Measure:** Realized, implied, or Parkinson volatility?
6. **Pricing Model:** What stochastic process for variance dynamics?

---

**Document Status:** This mission document serves as the authoritative guide for Fee Compression Swap research and development. All modeling and implementation decisions should reference this document.

**Next Steps:**
1. Complete structural econometrics requirements checklist
2. Extract equations from Capponi et al. (JIT paper)
3. Begin data extraction from Uniswap V3 subgraph
4. Run exploratory analysis
5. Validate variance claim
