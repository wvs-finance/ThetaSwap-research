# Requirements

- structural econometrics --> CFMM implementation


## [MACRA24](../refs/ma_cost_permissionless_2024.pdf)

- FeeRevenueAllocationRule(CFMM) = <PRO-RATA> ==> LPing competes for feeRevenue ==>
Liquidity Output above pareto frontier ==> Less Technical Efficient (Capital Efficient)

This is a claim that needs validation and is accompanied by:


(1)     \partial \sum L_i      / \partial numberOfLPs  > 0
         totalLiquidity
          on a tickRange


	  \partial \pi^i       / \partial numberOfLPs < 0
(2)         per-capita
            LP profit


(1) ^ (2) ==>  \partial \pi^i    / \partial \sum L_i < 0

(2) ==> LP's on a CFMM such that it's fee revenue is allocated pro-rata demand hedge agains numberOfLp's

===> \Pi^{H(#LP)} = f (P_{#(LP)}) --> [unitOfAccount] / [#LPs]

- Where P_{#(LP)} is the price of anarchy = O(#LP)

- P_{#(LP)} =  E^{Q} [\Pi^{monopolistic lp} / \Pi^{lp under competition}] = O(#LP)

(This is a definition from the paper)

> If we can track the monopolistc LP payoff and the LP under competition pay off at all times easily and not costly we could then track the P_{#(LP)} and build contigent claim payoff \Pi (P_{(#LP)}) (This payofs) standarizing this payoffs(through tokenization) and pricing them enable LP's to hedge the crowd-effetcs imposed by sophisticated LP's (or those who exhibit monopolistic behaviour)

### Claim:
Fixing time, fixing a market and fixing a tickSpread.

For all positions on the optimal tickSpread deducted from the market implied volatiltiy

The monopolistic feeGrowth should represent:
    "What would a single LP earn if they provided liquidity across this entire range alone?"

From the Uniswap V3 state variables if brough to the numeriare dimenssion is:

$monopolisticFeeGrowth(tickSpread) =sqrtPricex96*feeGrowthOutside0x128 + feeGrowthOutside0x128 T [ADZINSAKERO21](../refs/v3-core.pdf)

feeGrowthOutside(tickSpread)

We then compute per position on tickSpread:

$feeGrowthInside_{pos}(tickSpread) = sqrtPriceX96*feeGrowthInside0x128_{pos}(tickSpread) + feeGrowthInside0x128_{pos}(tickSpread)

Then if there are N positions in such tickSpread we have

volatility = (1/N)*\sqrt{(\sum^N ($monopolisticFeeGrowth(tickSpread)) - $feeGrowthInside_{pos} (tickSpread))^2}

variance = volatility^2


> The variance is additivve and all the proeprtiers that make variance great for pricing mechanics.

==> The claim is:

    variance = ln(\pi^{monopolistic}/pi^{lp under competition})= ln(P_{#LP})


- The monopolistic LP's since they are not directly obeservable are to be filtered and grouped based
on the model structure

From the model the optimal liquidity(tickSpread )*= (sum tick in tickSpread liquidityDelta(tick))


Iis given by:

liquidity(tickSpread)* = ((#Positions -1) / #Positions)* ("feeGrowth by fullfilling incformed trading orders"/"How much is needed for h3edgign th arbitrage flow and the opportunity cost using the p^2 perpetual" - "feeGrowth(revenue) for fullfilling non-informed trading orders")

The optimal expected profit of a monopolistic liquiditu provider is such that:


(This is theorem 1) of the paper interpreatation
\pi^{lp under competition} = "feeGrowth for fulfilling informed trading orders"

\pi^{monoopoly} = \pi^{lp under competition} + "controlled feeGowth for fulfilling non-informed trading roders, controllling by the determinants of arbitrage and opportunity cost with respect to hodl (imperement loss)"


From here the positions categorized as monopolistic must show reactions to volatiltty or impermanent loss and and also to arbitrage proxy observables

From there given this clustered data we eant to show

\pi^{monopoly} = priceOfAnarquy*pi^{competition} (This is a regression)
> normalize there


From the results of such regression we want to test wheter priceOfAnarquy = variance defined above
Or under which conditions it holds such equaility or is reasonable to consider such relation.

If we are successful proving the hypothesis, then the price of anarchy mentioned is fully observable on chain and can be used as prcing crowdiing out effects.


Building payoffs with this price allows LP's to hedge competition effects on ther positions


## [AQFOGAKRE24](../refs/aquilina_decentralised_dealers_2024.pdf)

- monopolistic --> sophisticated --> optimally* consider volatility
- under competition -->  PLP --> optimally* only consider "base demand"
                    ---> retail

- Define filters for retail versus institutional liquidity position at a pool level
- retail play the role of "under competition"
- institutional must be adapted or play the role of monopolistic on the other paper

- Are there any cross sectional filters , or they all require time series, panel data ?
They provide guidelines for such filters and  run regressions them selves that might be helpfull

## [](../refs)

## [](../)

# Fee Compression Swap Specification


Assume we prove or show the above or show the conditions, uner which the equality holds. Then the derivative is doable.** Here's why:

### **Key Viability Factors:**

| Factor | Status | Notes |
|--------|--------|-------|
| **Observable Underlying** | ✅ | FeeGrowth data is on-chain in Uniswap V3 |
| **Settlement** | ✅ | Oracle-based cash settlement in USDC |
| **Replication** | ✅ | Static range accrual portfolio backs vault |
| **Tokenization** | ✅ | ERC6909 for efficient position management |
| **Market Structure** | ✅ | Perpetual funding model with CFMM |
| **Extensibility** | ✅ | Payoff registry supports Linear/Log/Digital |

### **Architecture Overview:**

```
┌─────────────────────────────────────────────────────────┐
│              Fee Compression Swap Protocol               │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Oracle     │  │    Payoff    │  │     Vault    │  │
│  │  (UniswapV3) │─▶│   Registry   │─▶│   (ERC6909)  │  │
│  │  feeGrowth   │  │ Linear/Log/  │  │  Perpetual   │  │
│  │  variance    │  │   Digital    │  │   CFMM       │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### **Implementation Plan Structure:**
- **Phase 0:** Econometrics Exercise
- **Phase 1:** Oracle & Data Infrastructure (Tasks 1-2)
- **Phase 2:** Payoff Function Registry (Task 3)
- **Phase 3:** Perpetual CFMM Core (Task 4)
- **Phase 4:** Integration & Testing (Task 5)

---

