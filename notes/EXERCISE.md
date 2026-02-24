## Requirements

R1. **Single RAN token** (not two separate LONG/SHORT tokens)
R2. **Pricing follows priceRangeAccrual.pdf formulas**: RAN pricing as series of cash-or-nothing delayed options
R3. **CFMM trading function** uses digital option replication (angeris paper + primitivefinance implementation)
R4. **Initial liquidity** comes from Seller minting and lending
R5. **Price movement outside interval** is captured in the path realization

## Numerical Example: wsETTH/WBTC Range Accrual Market

### Contract Specification
- **Underlying**: wsETH/wBTC Uniswap V3 pool (0.03% fee tier)
- **Strike Interval**: tickLower = -120000, tickUpper = -80000
- **Accrual Frequency**: 1 block (non-default)
- **Observation Length**: Perpetual, capitalization at 1 block
- **Contract Size**: 1.0 LP position unit
- **Fee Rate**: 0.3% per swap
- **Initial Price**: $30,000 (tick = -100000)

### Parties and Initial Balances

#### Seller (LONG Position - believes price stays in band)
- **Address**: `0xSeller`
- **Initial wsETH Balance**:  √(L² × P) = √(1² × 30000) = 173.205 wsETH
- **Initial wBTC  Balance**:  L / √P = 1 / √30000 = 0.0057735 wBTC
- **Initial LP Position**: 1.0 unit of wsETH/wBTC liquidity
- **Position**: Long X  units of wsETH/wBTC 0.03% 25-40 1-2 (Range Accrual Note token)
> X is determined by the initial amount that guarantees fair initial price in the CFMM(RANGE_ACCRUAL_NOTE_TOKEN)

   0     1 
>  (wsETH, wBTC) --> P_{wBTC}{wsETH} --> wBTC quotes wsETH

#### Market Maker (CFMM Pool)
- **Address**: `0xMM`
- **Pool Reserves**:
  (1.0 unit of wsETH/BTC 0.03%liquidity , X wsETH/BTC 0.03% 25-40 1-2)
      |                                           -----> tokenized tick range accrual
      |
  (units of liquidity)


### Scenario Timeline: Perpetual
#### Block 0: Contract Creation

- 0xSeller mints 1.0 unit of wsETH/BTC 0.03% liquidity on CLAMM  [liquidity]  
- 0xSeller mints X wsETH/BTC 0.03% 25-40 1-2 isLong        [unitOfAccount]/ [liquidity]

- 0xSeller lends X unit of wsETH/BTC 0.03% liquidity to CFMM(TICK_RANGE_ACCRUAL_NOTE)
- 0xSeller deposits X wsETH/BTC 0.03% 25-40 1-2 in CFMM(TICK_RANGE_ACCRUAL_NOTE)

#### Market Maker (CFMM Pool) --> (Buyer (SHORT Position))
- **Address**: `0xMM`
- **Pool Reserves**: (1.0 LP token, 0.9091 RAN tokens)
- **Initial Price**: RAN = LP / ... (fair no-arbitrage)

#### Arbitrageur (CFMM Rebalancer)
- **Address**: `0xArb`
- **Initial position**: Provides liquidity to CFMM to enable rebalancing


Initial price, (WHICH ALSO DETERMINES THE AMOUNT X) must MATCH fair no-arbitrage
TICK_RANGE_ACCRUAL_NOTE price (There NEEDS a mechanism fo initial price enforcement)

From `priceRangeAccrual.pdf` and the digital option decomposition:
```
Π^RAN = Θ × ∑(1_{P_i > ψ_b} - 1_{P_i > ψ_a}) / N
      = Θ/N × ∑ digital_call(ψ_b) - digital_call(ψ_a)
```

Where each digital call is a cash-or-nothing option paying 1 if price > strike.

From the digital option replication:
- Each RAN token represents a portfolio of digital calls
- The CFMM must hold the underlying LP position to replicate
- The **funding fee** = cost of maintaining the replication portfolio

Thus the RAN pricing is :


#### Digital Option Pricing (from priceRangeAccrual.pdf)
- Digital call at ψ_b = -120000: price = D_b
- Digital call at ψ_a = -80000: price = D_a
- RAN price = Θ × (D_b - D_a)

For initial conditions (price = -100000, in band):
- D_b ≈ 0.7 (70% probability price > ψ_b)  --> These (70, 30) are related to implied volatility
Then one can proxy this values gathering implied volatility data
- D_a ≈ 0.3 (30% probability price > ψ_a)
- RAN price = Θ × (0.7 - 0.3) = Θ × 0.4

So **X = 1.0 / 0.4 = 2.5** RAN tokens per 1.0 LP token

#### Block 1: After Accrual
- Total feeGrowth = 0.003
- Observations: 4 in band, 6 out of band
- New probabilities: D_b' = 0.6, D_a' = 0.4
- New RAN price = 0.003 × (0.6 - 0.4) = 0.0006

The funding fee is the difference:
- Initial RAN value: 2.5 × 0.0012 = 0.003 (for the feeGrowth portion)
- Final RAN value: 0.0006
- **Funding fee paid to CFMM: 0.003 - 0.0006 = 0.0024**



#### Blocks 1: Price stays in band ($30,000)

#### Block 1: After 10 Swaps (4 in band, 6 out of band)
- **Total feeGrowthInside** = 0.3% × 10 = 0.003 units of liquidity
- **RAN payoff** = 0.003 × (4/10 - 6/10) = 0.003 × (-0.2) = -0.0006
- **Funding fee to CFMM** = |RAN payoff| = 0.0006 (replication cost)

- 10 swaps occur within the block
- 4 swaps occur within price band
- Accrual calculation at block 1:
  - Observations in band: 4/10*1 = 40%
                     (feeGrowthInside)  (observationsInBand) (contractSize)
  - Coupon accrued:      0.3%             × 40.0%                × 1.0       =  0.0012 feeGrowth

 This is realized. Thus the CFMM(RANGE_ACCRUAL_NOTE) inventory(wsETH/BTC 0.03% 25-40 1-2,wsETH/BTC 0.03%) MUST be-rabalanced such that if the LP (0xBuyer) where to burn his (X shares of wsETH/BTC 0.03% 25-40 1-2) we will realize a 0.0012 feeGrowth payoff.

Thus, the seller of such payoff RANGE_ACCRUAL_NOTE here is the CFMM that allows an arbitragaur to re-balance  on the CFMM(TICK_RANGE_ACCRUAL_NOTE) that plays as the other side of the market got 6 out of 10:
                       (feeGrowthInside) (observationsOutOFBand) (contractSize)
		       	    0.3%          x 60.0% x                  1.0    =  0.0018 feeGrowth	 

   - The arbitragur realizes a gain of 0.006 feeGrowth
   - The 0xBuyer (LP) a payoff of 0.0012 feeGrowth
   - And the CFMM of  0.0018 feeGowth


##### Accrual Calculation:
```
Coupon_LONG = totalFee × (inBand/total) = 0.003 × (4/10) = 0.0012
Coupon_SHORT = totalFee × (outOfBand/total) = 0.003 × (6/10) = 0.0018
```

##### Three-Party Realization:
The key insight from your correction: **the arbitrageur extracts the difference**

- **Buyer (SHORT)** realizes: 0.0018 feeGrowth (60% of total)
- **Seller (LONG)** realizes: 0.0012 feeGrowth (40% of total)
- **Arbitrageur** extracts: -0.0006 feeGrowth (the "extra" value) --> replication cost

The CFMM pricing mechanism creates an additional +0.0006 through the rebalancing process
- This is the "arbitrage gain" from maintaining no-arbitrage pricing.

**Block 1 Results (10 swaps: 4 in band, 6 out of band):**
- Total feeGrowth = 0.003
- RAN payoff = 0.003 × (4/10 - 6/10) = -0.0006
- Funding fee to CFMM = 0.0006 (the absolute value)
- Seller net: -0.0006 (pays funding fee)
- CFMM net: +0.0006 (receives funding fee for replication)

#### Seller (LONG Position)
- **Initial**: 173.205 wsETH + 0.0057735 wBTC + 2.5 RAN tokens
- **After accrual**: 
  - The RAN tokens appreciate by the LONG portion: +0.0012 feeGrowth
  - But Seller pays funding fee: -0.0006 feeGrowth
  - Net gain: +0.0006 feeGrowth
- **Final balances**:
  - wsETH: 173.205 - 0.0006 × √30000 = 173.205 - 0.1039 = **173.1011 wsETH**
  - wBTC: 0.0057735 - 0.0006 / √30000 = 0.0057735 - 0.0000001039 = **0.0057734 wBTC**
  - RAN tokens: 2.5 tokens (now worth 0.0006 more total)
  - **Net position value**: 173.1011 wsETH + 0.0057734 wBTC

#### Buyer (SHORT Position)
- **Initial**: 2.5 RAN tokens (short position)
- **After accrual**:
  - The RAN tokens depreciate by the SHORT portion: -0.0018 feeGrowth
  - But Buyer receives funding fee: +0.0006 feeGrowth (from CFMM)
  - Net loss: -0.0012 feeGrowth
- **Final balances**:
  - wsETH: 0 + 0.0012 × √30000 = **0.2078 wsETH** (realized from short position closure)
  - wBTC: 0 + 0.0012 / √30000 = **0.0000002078 wBTC**
  - RAN tokens: 0 tokens (position closed)
  - **Net position value**: 0.2078 wsETH + 0.0000002078 wBTC

#### Market Maker (CFMM Pool)
- **Initial**: (1.0 LP token, 2.5 RAN tokens)
- **After accrual**:
  - Receives funding fee: +0.0006 feeGrowth
  - The LP token value unchanged: 1.0 LP
  - RAN tokens value adjusted: 2.5 RAN tokens now worth 0.0006 less total
- **Final reserves**:
  - LP tokens: 1.0 LP token
  - RAN tokens: 2.5 RAN tokens
  - **CFMM net gain**: +0.0006 feeGrowth (funding fee for replication)

### Verification of No-Arbitrage Invariant

The key invariant must hold:
```
Value(LONG position) + Value(SHORT position) = Value(LP position) + Funding fee
```

- LONG value: 173.1011 wsETH + 0.0057734 wBTC
- SHORT value: 0.2078 wsETH + 0.0000002078 wBTC  
- LP position: 173.205 wsETH + 0.0057735 wBTC
- Funding fee: 0.0006 feeGrowth = 0.1039 wsETH + 0.0000001039 wBTC

Check:
- LONG + SHORT = 173.3089 wsETH + 0.0057736 wBTC
- LP + Funding = 173.3089 wsETH + 0.0057736 wBTC ✓


### Summary of Corrected Balances

| Party | wsETH | wBTC | RAN Tokens | Net Change |
|-------|-------|------|------------|------------|
| **Seller (LONG)** | 173.1011 | 0.0057734 | 2.5 | +0.0006 feeGrowth |
| **Buyer (SHORT)** | 0.2078 | 0.0000002078 | 0 | -0.0012 feeGrowth |
| **CFMM Pool** | 0 | 0 | 2.5 | +0.0006 feeGrowth |
