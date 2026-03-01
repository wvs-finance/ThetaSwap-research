# Structural Fee Variance Measurement — Design

**Date:** 2026-02-28
**Status:** Approved

---

## Problem

The TVL-based congestion variable has R² = 5.2% — too weak for a viable hedge (backtest shows CVaR worsening). The subgraph `liquidity` field failed (R² = 0.01%) because tick-crossing noise dominates. We need a direct, on-chain measurement of LP competition.

## Solution

Compute **FeeVarianceX128** — the cross-sectional variance of `(fee_share_i - liquidity_share_i)` across all active LP positions on V3 USDC/WETH — at one block per day over the pool's 1,760-day history.

This metric directly measures the pro-rata fee allocation deviation: when concentrated/strategic LPs capture disproportionate fee share relative to their liquidity share, FeeVariance rises. It is orthogonal to LVR by construction (price movement affects all in-range positions proportionally).

## Architecture

Two-phase hybrid pipeline:

### Phase 1: Position Registry (Python)

Script `data/build_position_registry.py` queries the NonfungiblePositionManager (`0xC36442b4a4522E871399CD717aBDD847Ab11FE88`) for all positions on the USDC/WETH pool (`0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640`).

**Output:** `data/position_registry.csv`
```
tokenId,tickLower,tickUpper,blockCreated,blockClosed
```

Filters to NPM-managed positions only (~5K-20K unique tokenIds, ~1K-5K active at any given block).

### Phase 2: Foundry Fee Variance Script (Solidity)

Foundry project at `contracts/fee-variance/`.

**Dependencies:**
- `@uniswap/v3-periphery` — `PositionValue` library, `NonfungiblePositionManager` interface
- `@uniswap/v3-core` — `IUniswapV3Pool`

**Script:** `script/FeeVariance.s.sol`

For each daily block:

1. `vm.rollFork(blockNumber)` — set EVM state to historical block
2. Read active tokenIds from position registry (filtered by block range)
3. **Pass 1:** For each position, call `PositionValue.fees(npm, tokenId)` → `(fees0, fees1)`, read `liquidity` from `npm.positions(tokenId)`. USD-normalize fees using `sqrtPriceX96` from `pool.slot0()`. Accumulate `totalFees`, `totalLiquidity`.
4. **Pass 2:** For each position, compute:
   - `C_i = fees_i / totalFees - liquidity_i / totalLiquidity` (in X128 fixed-point)
   - `FeeVarianceX128 += C_i² / N`
5. `vm.ffi()` → append `(date, blockNumber, FeeVarianceX128, numPositions)` to CSV

**Input files:**
- `data/position_registry.csv` — from Phase 1
- `data/daily_blocks.csv` — mapping `(date, blockNumber)`, first block after midnight UTC each day

**Output:** `data/fee_variance.csv`

**Runtime:** ~1,760 fork calls × ~2-5K positions each. Estimated 1-2 hours with fast archive RPC.

## Metric Definition

At each daily snapshot block, for active NPM positions `{i}` on the pool:

$$C_i = \frac{\text{fees}_i}{\sum_j \text{fees}_j} - \frac{L_i}{\sum_j L_j}$$

$$\text{FeeVariance}_t = \frac{1}{N} \sum_i C_i^2$$

Note: `sum_i(C_i) = 0` by construction, so variance = mean of squares.

**Properties:**
- `FeeVariance = 0` ↔ perfectly pro-rata fee allocation (no competition)
- `FeeVariance` increases when concentrated positions capture disproportionate fee share
- Negatively correlated with LP returns (high variance = competition = fee compression)
- Orthogonal to LVR (price movement affects all in-range positions proportionally)

## Integration

### DataHandler (`data/DataHandler.py`)

```python
def load_fee_variance(path="data/fee_variance.csv") -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"]).set_index("date")
    return df

def fee_variance(df: pd.DataFrame) -> TimeSeries:
    return df["fee_variance_x128"]
```

### Econometrics (`notebooks/econometrics.ipynb`)

Replace endog:
```python
fv = load_fee_variance()
endog = delta(fee_variance(fv))
```

Everything downstream unchanged: `LiquidityStateModel` → AR(1) state → `AdverseCompetitionModel` → δ₂.

### Backtest (`notebooks/backtest.ipynb`)

Same substitution. New δ₂ feeds into sigmoid payoff and hedge ratio.

## References

- Uniswap V3 `PositionValue` library: [v3-periphery/contracts/libraries/PositionValue.sol](https://github.com/Uniswap/v3-periphery/blob/main/contracts/libraries/PositionValue.sol)
- Milionis, Wan, Adams (2023). "FLAIR: A Metric for Liquidity Provider Competitiveness in AMMs." arXiv:2306.09421.
- Angeris, Evans, Chitra (2021). "Replicating Monotonic Payoffs Without Oracles." arXiv:2111.13740.
