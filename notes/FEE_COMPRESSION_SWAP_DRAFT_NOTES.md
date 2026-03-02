# Requirements

- structural econometrics --> CFMM implementation


## [MACRA24](../refs/ma_cost_permissionless_2024.pdf)

(0) --> FeeRevenueAllocationRule(CFMM) = <PRO-RATA> ==> LPing competes for feeRevenue ==>
Liquidity Output above pareto frontier ==> Less Technical Efficient (Capital Efficient)

This is a claim that needs validation and is accompanied by:


(1)     \partial \sum L_i      / \partial numberOfLPs  > 0
         totalLiquidity
          on a tickRange


	  \partial \pi^i       / \partial numberOfLPs < 0
(2)         per-capita
            LP profit


(1) ^ (2) ==> (0)


(This is a definition from the paper)

### Claim:

Fixing time, fixing a market and fixing a tickSpread.

For all positions on the optimal tickSpread


We define \Delta L_t - \mathbb{E}(\Delta L_t | "market state")
...


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
│              Competition Swap Protocol               │
├─────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Oracle     │  │    Payoff    │  │     Vault    │  │
│  │  (UniswapV3) │─▶│   Registry   │─▶│   (ERC6909)  │  │
│  │  ────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### **Implementation Plan Structure:**
- **Phase 0:** Econometrics Exercise
- **Phase 1:** Oracle & Data Infrastructure (Tasks 1-2)
- **Phase 2:** Payoff Function Registry (Task 3)
- **Phase 3:** Perpetual CFMM Core (Task 4)
- **Phase 4:** Integration & Testing (Task 5)

---



