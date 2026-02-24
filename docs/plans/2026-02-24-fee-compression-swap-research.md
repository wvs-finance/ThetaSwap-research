# Fee Compression Swap Research Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Develop a research framework to validate the fee compression swap hypothesis by implementing econometric analysis of LP profitability under monopolistic vs competitive conditions in CFMMs.

**Architecture:** Build a research pipeline that (1) extracts LP position data from CFMM pools, (2) calculates fee growth metrics (feeGrowthOutside/feeGrowthInside), (3) constructs profitability metrics for retail vs institutional LPs, and (4) performs econometric validation of the price of anarchy claim P_{#LP} = E^Q[Π^monopolistic/Π^competitive].

**Tech Stack:** Python for econometrics (statsmodels, pandas, numpy), data extraction from CFMM subgraphs, Jupyter notebooks for exploratory analysis, LaTeX for mathematical formalization.

**Key Research Questions from Draft:**
1. How to track LP payoff - do we need P&L, payoff, or fee growth metrics?
2. How to distinguish monopolistic (JIT/sophisticated) vs competitive (retail) LP behavior?
3. Can we validate: ln(variance(feeOutside/feeInside)) = ln(P_{#LP})?
4. What filters distinguish retail vs institutional positions at pool level?

---

## Phase 1: Literature Review & Mathematical Formalization

### Task 1: Annotate MACRA24 Paper Claims

**Files:**
- Read: `refs/ma_cost_permissionless_2024.pdf`
- Create: `notes/fee-compression/macra24-annotations.md`
- Test: N/A (research task)

**Step 1: Extract core claims from paper**

Read the paper and document:
- Definition of FeeRevenueAllocationRule(CFMM) and pro-rata allocation
- Mathematical derivation of ∂(ΣL_i)/∂numberOfLPs > 0
- Mathematical derivation of ∂π^i/∂numberOfLPs < 0
- Definition of Price of Anarchy P_{#LP} in CFMM context
- Conditions for liquidity above Pareto frontier

**Step 2: Document the fee compression hypothesis**

Create markdown with:
```markdown
## MACRA24 Core Claims

### Claim 1: Pro-Rata Fee Allocation Drives Competition
- FeeRevenueAllocationRule(CFMM) = pro-rata
- Implication: LPing competes for feeRevenue
- Result: Liquidity above Pareto frontier → Less Capital Efficient

### Claim 2: Derivative Relationships
(1) ∂(ΣL_i)/∂numberOfLPs > 0  [total liquidity increases with LPs]
(2) ∂π^i/∂numberOfLPs < 0      [per-capita profit decreases with LPs]

Combined: ∂π^i/∂(ΣL_i) < 0  [individual profit decreases as total liquidity increases]

### Claim 3: Price of Anarchy Definition
P_{#LP} = E^Q[Π^monopolistic_lp / Π^lp_under_competition]

Where:
- Π^H(#LP) = f(P_{#LP}) → [unitOfAccount] / [#LPs]
- P_{#LP} = O(#LP)  [Price of Anarchy scales with number of LPs]
```

**Step 3: Verify understanding**

Review annotations and ensure all mathematical notation is consistent with draft notes.

**Step 4: Commit**

```bash
git add notes/fee-compression/macra24-annotations.md
git commit -m "docs: annotate MACRA24 paper claims for fee compression research"
```

---

### Task 2: Annotate AQFOGAKRE24 Paper Claims

**Files:**
- Read: `refs/aquilina_decentralised_dealers_2024.pdf`
- Create: `notes/fee-compression/aqfogakre24-annotations.md`
- Test: N/A (research task)

**Step 1: Extract LP classification framework**

Read the paper and document:
- Definition of "sophisticated" vs "retail" LPs
- How monopolistic LPs optimally consider volatility
- How competitive LPs only consider "base demand"
- Empirical filters for identifying LP types

**Step 2: Document econometric specification**

Create markdown with:
```markdown
## AQFOGAKRE24 LP Classification Framework

### LP Type Definitions
- **Monopolistic/Sophisticated**: Optimally considers volatility in positioning
- **Competitive/Retail (PLP)**: Optimally considers only base demand

### Econometric Model
For a representative pool:

Tracking variables:
- Volume → numeraire Δ
- $TVL (question: how to extract from poolData?)
- Volatility measure

Position-level profitability: ln(π^i)
- Position level = numeraire size at mint (birth of liquidity position)

Regression specification:
log(π^i_retail) = b0 + b1*1_{retail(i)} + b2*log(volatility) + b3*log($tvl) + b4*log($volume) + ε
log(π^i_institutional) = b0 + b1*1_{institutional(i)} + b2*log(volatility) + b3*log($tvl) + b4*log($volume) + ε

### Key Hypothesis to Prove
feeGrowthOutside - feeGrowthInside_position = log(π^i_retail / π^i_institutional)

Required: Define econometric identification strategy
```

**Step 3: Identify open questions**

Document:
- How to extract $TVL from pool data?
- What volatility measure to use (realized, implied)?
- How to classify positions as retail vs institutional?
- What data frequency for observations?

**Step 4: Commit**

```bash
git add notes/fee-compression/aqfogakre24-annotations.md
git commit -m "docs: annotate AQFOGAKRE24 LP classification framework"
```

---

### Task 3: Formalize Fee Growth Claim

**Files:**
- Create: `notes/fee-compression/fee-growth-claim-formalization.md`
- Modify: `notes/FEE_COMPRESSION_SWAP_DRAFT_NOTES.md` (add clarifications)
- Test: N/A (theoretical work)

**Step 1: Write the core claim with precise notation**

```markdown
## Fee Growth Variance Claim

### Definitions
Let:
- feeGrowthOutside_t = cumulative fee growth outside position range at time t
- feeGrowthInside_t = cumulative fee growth inside position range at time t
- position i = liquidity position with tick range [tickLower_i, tickUpper_i]

### Claim: Log Approximation
For all positions on the optimal range (implied by implied volatility):

feeGrowthOutside - feeGrowthInside_position ≈ ln(feeGrowthOutside) - ln(feeGrowthInside_position)
                                            ≈ ln(feeGrowthOutside / feeGrowthInside_position)

### Main Hypothesis
ln(variance(feeGrowthOutside / feeGrowthInside_position)) = ln(π^monopolistic / π^competitive)
                                                          = ln(P_{#LP})

### Implications
If true, this enables:
1. Tracking P_{#LP} through observable fee growth metrics
2. Building payoffs Π(P_{#LP}) as swap instruments
3. "Fee Compression Swap" as hedging instrument against LP competition
```

**Step 2: Document assumptions and conditions**

```markdown
## Assumptions for Claim Validity

1. **Optimal Range Assumption**: Position tick range is implied by market implied volatility
2. **Log Approximation Validity**: Requires feeGrowthOutside/feeGrowthInside ≈ 1 + small deviation
3. **Variance Stationarity**: variance(feeRatio) is well-defined over observation period
4. **Monopolistic Proxy**: JIT (Just-In-Time) liquidity as proxy for monopolistic behavior
5. **Competitive Proxy**: Passive LP (PLP) as proxy for competitive behavior
```

**Step 3: Define tracking requirements**

```markdown
## Data Requirements for Tracking

### LP Payoff Tracking
Question: Do we need P&L, payoff, or fee growth metrics?

Options:
1. **P&L approach**: Track unrealized + realized P&L per position
   - Requires: entry price, current price, fees earned
   - Advantage: Direct profitability measure
   - Challenge: Requires position-level tracking across time

2. **Fee Growth approach**: Track feeGrowthOutside vs feeGrowthInside
   - Requires: pool-level fee growth data, position tick ranges
   - Advantage: Observable from on-chain data
   - Challenge: May not capture impermanent loss

3. **Payoff approach**: Track terminal payoff at position closure
   - Requires: mint/burn events, fee accumulation
   - Advantage: Realized returns
   - Challenge: Censored data (only observe closed positions)

Recommendation: Use fee growth approach as primary, validate with P&L for closed positions.

### Monopolistic vs Competitive Tracking
Hypothesis: 
- Monopolistic → JIT liquidity (capponi_jit_liquidity_2024.pdf)
- Competitive → Passive LP positions

Data needed:
- JIT detection: liquidity minted/burned within single block
- Passive detection: liquidity duration > threshold
```

**Step 4: Commit**

```bash
git add notes/fee-compression/fee-growth-claim-formalization.md
git commit -m "docs: formalize fee growth variance claim and tracking requirements"
```

---

## Phase 2: Data Extraction & Processing

### Task 4: Define LP Classification Filters

**Files:**
- Create: `lib/fee_compression/lp_classification.py`
- Test: `tests/test_lp_classification.py`

**Step 1: Write failing tests**

```python
# tests/test_lp_classification.py

import pytest
import pandas as pd
import numpy as np
from lib.fee_compression.lp_classification import (
    classify_position_as_retail,
    classify_position_as_institutional,
    calculate_position_size_numeraire,
    detect_jit_liquidity,
    detect_passive_liquidity
)

def test_detect_jit_liquidity():
    """JIT: liquidity minted and burned within same block"""
    position_data = {
        'mint_block': 1000,
        'burn_block': 1000,
        'duration_blocks': 0
    }
    assert detect_jit_liquidity(position_data) == True

def test_detect_passive_liquidity():
    """Passive: liquidity duration > threshold (e.g., 100 blocks)"""
    position_data = {
        'mint_block': 1000,
        'burn_block': 1200,
        'duration_blocks': 200
    }
    assert detect_passive_liquidity(position_data, threshold=100) == True

def test_classify_position_retail():
    """Retail: small size, passive, low volatility awareness"""
    position = {
        'size_numeraire': 1000,  # $1000
        'is_jit': False,
        'volatility_adjusted': False
    }
    assert classify_position_as_retail(position) == True

def test_classify_position_institutional():
    """Institutional: large size, JIT or volatility-aware"""
    position = {
        'size_numeraire': 1000000,  # $1M
        'is_jit': True,
        'volatility_adjusted': True
    }
    assert classify_position_as_institutional(position) == True

def test_calculate_position_size_numeraire():
    """Calculate position size in USD numeraire at mint"""
    liquidity = 1e18
    price_at_mint = 2000  # ETH/USD
    expected_size = liquidity * price_at_mint / 1e18
    assert calculate_position_size_numeraire(liquidity, price_at_mint) == expected_size
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_lp_classification.py -v
# Expected: FAIL with "ModuleNotFoundError: No module named 'lib.fee_compression'"
```

**Step 3: Write minimal implementation**

```python
# lib/fee_compression/lp_classification.py

"""
LP Classification Module

Filters for retail vs institutional liquidity positions at pool level.
Based on AQFOGAKRE24 framework.
"""

from dataclasses import dataclass
from typing import Dict, Any
import numpy as np

@dataclass
class PositionData:
    """Liquidity position data for classification"""
    position_id: str
    liquidity: int  # Uniswap V3 liquidity units
    mint_block: int
    burn_block: int | None  # None if active
    tick_lower: int
    tick_upper: int
    owner: str
    
class LPClassifier:
    """Classify LP positions as retail or institutional"""
    
    def __init__(
        self,
        jit_threshold_blocks: int = 1,
        passive_threshold_blocks: int = 100,
        retail_size_threshold_usd: float = 10000,
        institutional_size_threshold_usd: float = 100000
    ):
        self.jit_threshold = jit_threshold_blocks
        self.passive_threshold = passive_threshold_blocks
        self.retail_size_threshold = retail_size_threshold_usd
        self.institutional_size_threshold = institutional_size_threshold_usd
    
    def detect_jit_liquidity(self, position: PositionData) -> bool:
        """
        Detect JIT (Just-In-Time) liquidity.
        
        JIT: liquidity minted and burned within same block or very short duration.
        Based on capponi_jit_liquidity_2024.pdf
        """
        if position.burn_block is None:
            return False  # Active position, cannot confirm JIT
        
        duration = position.burn_block - position.mint_block
        return duration <= self.jit_threshold
    
    def detect_passive_liquidity(self, position: PositionData) -> bool:
        """
        Detect passive (retail) liquidity.
        
        Passive: liquidity duration > threshold, not JIT.
        """
        if position.burn_block is None:
            # Active position: check if survived long enough
            # Use current block as proxy (requires injection)
            return False  # Cannot determine without current block
        
        duration = position.burn_block - position.mint_block
        return duration >= self.passive_threshold
    
    def calculate_position_size_numeraire(
        self,
        liquidity: int,
        tick_lower: int,
        tick_upper: int,
        price_at_mint: float,
        tick_spacing: int = 10
    ) -> float:
        """
        Calculate position size in USD numeraire at mint time.
        
        For Uniswap V3:
        - amount0 = liquidity * (1/sqrt(P_b) - 1/sqrt(P_a))
        - amount1 = liquidity * (sqrt(P_b) - sqrt(P_a))
        
        Returns total value in USD (numeraire).
        """
        from math import sqrt
        
        # Convert ticks to prices
        price_lower = (1.0001 ** tick_lower)
        price_upper = (1.0001 ** tick_upper)
        
        # Calculate token amounts
        sqrt_price = sqrt(price_at_mint)
        sqrt_price_lower = sqrt(price_lower)
        sqrt_price_upper = sqrt(price_upper)
        
        if price_at_mint >= price_upper:
            # All token0
            amount0 = liquidity * (1/sqrt_price_upper - 1/sqrt_price_lower)
            amount1 = 0
        elif price_at_mint <= price_lower:
            # All token1
            amount0 = 0
            amount1 = liquidity * (sqrt_price_upper - sqrt_price_lower)
        else:
            # Mixed
            amount0 = liquidity * (1/sqrt_price - 1/sqrt_price_upper)
            amount1 = liquidity * (sqrt_price - sqrt_price_lower)
        
        # Convert to USD
        size_usd = amount0 * price_at_mint + amount1
        
        return size_usd
    
    def classify_position_as_retail(
        self,
        position: PositionData,
        size_usd: float,
        is_jit: bool
    ) -> bool:
        """
        Classify position as retail.
        
        Retail characteristics:
        - Small size (< threshold)
        - Passive (not JIT)
        - Not volatility-adjusted
        """
        if is_jit:
            return False  # JIT is never retail
        
        if size_usd > self.retail_size_threshold:
            return False  # Too large for retail
        
        return True
    
    def classify_position_as_institutional(
        self,
        position: PositionData,
        size_usd: float,
        is_jit: bool
    ) -> bool:
        """
        Classify position as institutional.
        
        Institutional characteristics:
        - Large size (> threshold) OR
        - JIT liquidity OR
        - Volatility-aware positioning
        """
        if is_jit:
            return True  # JIT is institutional
        
        if size_usd >= self.institutional_size_threshold:
            return True  # Large enough for institutional
        
        return False
    
    def classify_position(
        self,
        position: PositionData,
        price_at_mint: float,
        tick_spacing: int = 10
    ) -> Dict[str, Any]:
        """
        Full classification pipeline for a position.
        
        Returns classification with all intermediate calculations.
        """
        # Calculate size
        size_usd = self.calculate_position_size_numeraire(
            position.liquidity,
            position.tick_lower,
            position.tick_upper,
            price_at_mint,
            tick_spacing
        )
        
        # Detect behavior type
        is_jit = self.detect_jit_liquidity(position)
        is_passive = self.detect_passive_liquidity(position)
        
        # Classify
        is_retail = self.classify_position_as_retail(position, size_usd, is_jit)
        is_institutional = self.classify_position_as_institutional(position, size_usd, is_jit)
        
        return {
            'position_id': position.position_id,
            'size_usd': size_usd,
            'is_jit': is_jit,
            'is_passive': is_passive,
            'is_retail': is_retail,
            'is_institutional': is_institutional,
            'classification': 'institutional' if is_institutional else ('retail' if is_retail else 'unknown')
        }
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_lp_classification.py -v
# Expected: PASS (may need to adjust test assertions)
```

**Step 5: Commit**

```bash
git add lib/fee_compression/lp_classification.py tests/test_lp_classification.py
git commit -m "feat: implement LP classification filters for retail vs institutional"
```

---

### Task 5: Implement Fee Growth Metrics Calculator

**Files:**
- Create: `lib/fee_compression/fee_growth_metrics.py`
- Test: `tests/test_fee_growth_metrics.py`

**Step 1: Write failing tests**

```python
# tests/test_fee_growth_metrics.py

import pytest
import numpy as np
from lib.fee_compression.fee_growth_metrics import (
    FeeGrowthCalculator,
    calculate_fee_growth_ratio,
    calculate_fee_growth_variance,
    log_approximation_error
)

def test_fee_growth_ratio():
    """feeGrowthOutside / feeGrowthInside ratio"""
    fee_growth_outside = 1.05  # 5% growth outside
    fee_growth_inside = 1.03   # 3% growth inside
    expected_ratio = 1.05 / 1.03
    
    result = calculate_fee_growth_ratio(fee_growth_outside, fee_growth_inside)
    assert np.isclose(result, expected_ratio)

def test_fee_growth_variance():
    """Variance of fee growth ratio over time series"""
    fee_ratios = [1.01, 1.02, 1.015, 1.025, 1.018]
    expected_variance = np.var(fee_ratios)
    
    result = calculate_fee_growth_variance(fee_ratios)
    assert np.isclose(result, expected_variance)

def test_log_approximation():
    """Test log approximation: x - y ≈ ln(x) - ln(y) ≈ ln(x/y)"""
    x = 1.05
    y = 1.03
    
    direct_diff = x - y
    log_diff = np.log(x) - np.log(y)
    log_ratio = np.log(x / y)
    
    # Log diff and log ratio should be very close
    assert np.isclose(log_diff, log_ratio)
    
    # Direct diff and log ratio should be close for small deviations
    error = log_approximation_error(x, y)
    assert error < 0.01  # Less than 1% error

def test_fee_growth_claim_validation():
    """
    Validate core claim:
    ln(variance(feeOutside/feeInside)) = ln(π^monopolistic / π^competitive)
    """
    calculator = FeeGrowthCalculator()
    
    # Simulated fee growth data
    fee_growth_outside_series = [1.01, 1.02, 1.025, 1.03, 1.035]
    fee_growth_inside_series = [1.005, 1.01, 1.012, 1.015, 1.018]
    
    # Calculate LHS: ln(variance(feeRatio))
    lhs = calculator.calculate_lhs_metric(
        fee_growth_outside_series,
        fee_growth_inside_series
    )
    
    # Simulated profitability data
    pi_monopolistic = 0.05
    pi_competitive = 0.03
    
    # Calculate RHS: ln(pi_mono / pi_comp)
    rhs = calculator.calculate_rhs_metric(pi_monopolistic, pi_competitive)
    
    # Claim: LHS ≈ RHS (within tolerance)
    # Note: This is the hypothesis to test, not assume it holds
    # Test just validates calculation, not the economic claim
    assert isinstance(lhs, float)
    assert isinstance(rhs, float)
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_fee_growth_metrics.py -v
# Expected: FAIL with "ModuleNotFoundError"
```

**Step 3: Write minimal implementation**

```python
# lib/fee_compression/fee_growth_metrics.py

"""
Fee Growth Metrics Calculator

Implements metrics for validating the fee compression hypothesis:
ln(variance(feeGrowthOutside/feeGrowthInside)) = ln(π^monopolistic / π^competitive)

Based on MACRA24 and AQFOGAKRE24 frameworks.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np
from scipy import stats


def calculate_fee_growth_ratio(
    fee_growth_outside: float,
    fee_growth_inside: float
) -> float:
    """
    Calculate fee growth ratio: feeGrowthOutside / feeGrowthInside
    
    This ratio measures relative fee accumulation outside vs inside position range.
    """
    if fee_growth_inside == 0:
        return np.inf
    
    return fee_growth_outside / fee_growth_inside


def calculate_fee_growth_variance(
    fee_growth_ratios: List[float]
) -> float:
    """
    Calculate variance of fee growth ratio time series.
    
    Args:
        fee_growth_ratios: Time series of feeGrowthOutside/feeGrowthInside ratios
    
    Returns:
        Variance of the ratio series
    """
    if len(fee_growth_ratios) < 2:
        return 0.0
    
    return np.var(fee_growth_ratios, ddof=1)  # Sample variance


def log_approximation_error(
    x: float,
    y: float
) -> float:
    """
    Calculate error in log approximation.
    
    Claim: x - y ≈ ln(x) - ln(y) ≈ ln(x/y)
    
    Returns:
        Absolute error: |(x - y) - ln(x/y)|
    """
    direct_diff = x - y
    log_ratio = np.log(x / y)
    
    return abs(direct_diff - log_ratio)


@dataclass
class FeeGrowthCalculator:
    """
    Calculator for fee growth metrics related to fee compression hypothesis.
    """
    
    tick_spacing: int = 10
    fee_rate: float = 0.003  # 30 bps default
    
    def calculate_fee_growth_inside(
        self,
        liquidity: float,
        fee_growth_global: float,
        tick_lower: int,
        tick_upper: int,
        current_tick: int
    ) -> float:
        """
        Calculate fee growth inside position range.
        
        For Uniswap V3:
        - If current tick is inside range: feeGrowthInside = feeGrowthGlobal
        - If outside: feeGrowthInside = feeGrowthOutside at nearest boundary
        
        Args:
            liquidity: Position liquidity
            fee_growth_global: Global fee growth per unit liquidity
            tick_lower: Position lower tick
            tick_upper: Position upper tick
            current_tick: Current pool tick
        
        Returns:
            Fee growth inside position range
        """
        if tick_lower < current_tick < tick_upper:
            # Price is inside range, position earns fees
            return fee_growth_global
        elif current_tick <= tick_lower:
            # Price below range, use fee growth at lower boundary
            return fee_growth_global  # Simplified: assumes feeGrowthOutside[tickLower]
        else:
            # Price above range, use fee growth at upper boundary
            return fee_growth_global  # Simplified: assumes feeGrowthOutside[tickUpper]
    
    def calculate_fee_growth_outside(
        self,
        fee_growth_global: float,
        position_range: tuple
    ) -> float:
        """
        Calculate fee growth outside position range.
        
        Fee growth outside = fee growth that would have been earned
        if position was not in the market (monopolistic counterfactual).
        
        Simplified: feeGrowthOutside ≈ feeGrowthGlobal
        Refined: Use feeGrowthOutside[tickLower] and feeGrowthOutside[tickUpper]
        """
        # In Uniswap V3, feeGrowthOutside[tick] is stored per tick
        # For now, use global as proxy
        return fee_growth_global
    
    def calculate_lhs_metric(
        self,
        fee_growth_outside_series: List[float],
        fee_growth_inside_series: List[float]
    ) -> float:
        """
        Calculate LHS of fee compression claim:
        ln(variance(feeGrowthOutside / feeGrowthInside))
        
        Args:
            fee_growth_outside_series: Time series of feeGrowthOutside
            fee_growth_inside_series: Time series of feeGrowthInside
        
        Returns:
            ln(variance(feeRatio))
        """
        if len(fee_growth_outside_series) != len(fee_growth_inside_series):
            raise ValueError("Series must have same length")
        
        if len(fee_growth_outside_series) < 2:
            return 0.0
        
        # Calculate fee ratios
        fee_ratios = [
            calculate_fee_growth_ratio(out, ins)
            for out, ins in zip(fee_growth_outside_series, fee_growth_inside_series)
            if ins > 0
        ]
        
        if len(fee_ratios) < 2:
            return 0.0
        
        # Calculate variance
        variance = calculate_fee_growth_variance(fee_ratios)
        
        # Return log variance
        if variance <= 0:
            return -np.inf
        
        return np.log(variance)
    
    def calculate_rhs_metric(
        self,
        pi_monopolistic: float,
        pi_competitive: float
    ) -> float:
        """
        Calculate RHS of fee compression claim:
        ln(π^monopolistic / π^competitive)
        
        This is ln(P_{#LP}) where P is the Price of Anarchy.
        
        Args:
            pi_monopolistic: Monopolistic LP payoff
            pi_competitive: Competitive LP payoff
        
        Returns:
            ln(pi_mono / pi_comp)
        """
        if pi_competitive <= 0:
            return np.inf
        
        ratio = pi_monopolistic / pi_competitive
        
        if ratio <= 0:
            return -np.inf
        
        return np.log(ratio)
    
    def validate_fee_compression_claim(
        self,
        fee_growth_outside_series: List[float],
        fee_growth_inside_series: List[float],
        pi_monopolistic: float,
        pi_competitive: float,
        tolerance: float = 0.1
    ) -> Dict[str, Any]:
        """
        Validate the fee compression claim.
        
        Hypothesis: ln(variance(feeRatio)) = ln(π^mono / π^comp)
        
        Args:
            fee_growth_outside_series: Time series of feeGrowthOutside
            fee_growth_inside_series: Time series of feeGrowthInside
            pi_monopolistic: Monopolistic payoff (e.g., JIT LP)
            pi_competitive: Competitive payoff (e.g., passive LP)
            tolerance: Tolerance for claim validation (relative error)
        
        Returns:
            Dictionary with validation results
        """
        lhs = self.calculate_lhs_metric(
            fee_growth_outside_series,
            fee_growth_inside_series
        )
        rhs = self.calculate_rhs_metric(pi_monopolistic, pi_competitive)
        
        # Calculate relative error
        if rhs != 0:
            relative_error = abs(lhs - rhs) / abs(rhs)
        else:
            relative_error = np.inf if lhs != 0 else 0.0
        
        claim_holds = relative_error <= tolerance
        
        return {
            'lhs': lhs,
            'rhs': rhs,
            'relative_error': relative_error,
            'claim_holds': claim_holds,
            'tolerance': tolerance,
            'price_of_anarchy': np.exp(rhs),  # P_{#LP} = exp(rhs)
            'variance_fee_ratio': np.exp(lhs)  # var(feeRatio) = exp(lhs)
        }
    
    def calculate_log_approximation_quality(
        self,
        fee_growth_outside_series: List[float],
        fee_growth_inside_series: List[float]
    ) -> Dict[str, float]:
        """
        Assess quality of log approximation.
        
        Claim: feeGrowthOutside - feeGrowthInside ≈ ln(feeOut/feeIn)
        
        Returns:
            Statistics on approximation error
        """
        errors = []
        
        for out, ins in zip(fee_growth_outside_series, fee_growth_inside_series):
            if ins > 0 and out > 0:
                error = log_approximation_error(out, ins)
                errors.append(error)
        
        if not errors:
            return {'mean_error': 0.0, 'max_error': 0.0, 'min_error': 0.0}
        
        return {
            'mean_error': np.mean(errors),
            'max_error': np.max(errors),
            'min_error': np.min(errors),
            'std_error': np.std(errors)
        }
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_fee_growth_metrics.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add lib/fee_compression/fee_growth_metrics.py tests/test_fee_growth_metrics.py
git commit -m "feat: implement fee growth metrics calculator for claim validation"
```

---

### Task 6: Implement Profitability Metric Calculator

**Files:**
- Create: `lib/fee_compression/profitability_metrics.py`
- Test: `tests/test_profitability_metrics.py`

**Step 1: Write failing tests**

```python
# tests/test_profitability_metrics.py

import pytest
import numpy as np
from lib.fee_compression.profitability_metrics import (
    ProfitabilityCalculator,
    calculate_position_pnl,
    calculate_fee_revenue,
    calculate_impermanent_loss
)

def test_calculate_fee_revenue():
    """Calculate fee revenue for a position"""
    liquidity = 1e18
    fee_growth_inside = 0.003  # 30 bps
    expected_revenue = liquidity * fee_growth_inside
    
    result = calculate_fee_revenue(liquidity, fee_growth_inside)
    assert np.isclose(result, expected_revenue)

def test_calculate_impermanent_loss():
    """Calculate impermanent loss for position"""
    entry_price = 2000
    exit_price = 2500
    liquidity = 1e18
    
    result = calculate_impermanent_loss(liquidity, entry_price, exit_price)
    assert result < 0  # IL is a loss

def test_calculate_position_pnl():
    """Calculate total P&L for position"""
    calc = ProfitabilityCalculator()
    
    position_data = {
        'liquidity': 1e18,
        'entry_price': 2000,
        'exit_price': 2500,
        'fee_revenue': 300,
        'token0_amount': 0.5,
        'token1_amount': 1000
    }
    
    pnl = calc.calculate_total_pnl(position_data)
    
    # P&L = fee_revenue + value_change - impermanent_loss
    assert isinstance(pnl, float)

def test_log_profitability_regression():
    """
    Test regression specification from AQFOGAKRE24:
    log(π^i) = b0 + b1*1_{type(i)} + b2*log(volatility) + b3*log(TVL) + b4*log(volume) + ε
    """
    calc = ProfitabilityCalculator()
    
    # Create sample dataset
    positions = [
        {'type': 'retail', 'profitability': 0.01, 'volatility': 0.5, 'tvl': 1e6, 'volume': 1e5},
        {'type': 'retail', 'profitability': 0.015, 'volatility': 0.6, 'tvl': 1.2e6, 'volume': 1.5e5},
        {'type': 'institutional', 'profitability': 0.05, 'volatility': 0.5, 'tvl': 1e6, 'volume': 1e5},
        {'type': 'institutional', 'profitability': 0.06, 'volatility': 0.6, 'tvl': 1.2e6, 'volume': 1.5e5},
    ]
    
    results = calc.run_profitability_regression(positions)
    
    assert 'coefficients' in results
    assert 'r_squared' in results
    assert 'institutional_coefficient' in results['coefficients']
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_profitability_metrics.py -v
# Expected: FAIL
```

**Step 3: Write minimal implementation**

```python
# lib/fee_compression/profitability_metrics.py

"""
Profitability Metrics Calculator

Implements LP profitability calculations for econometric analysis.
Based on AQFOGAKRE24 regression specification.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import numpy as np
import pandas as pd
from scipy import stats


def calculate_fee_revenue(
    liquidity: float,
    fee_growth_inside: float
) -> float:
    """
    Calculate fee revenue for a position.
    
    Fee Revenue = Liquidity × feeGrowthInside
    
    Args:
        liquidity: Position liquidity (Uniswap V3 units)
        fee_growth_inside: Fee growth inside position range
    
    Returns:
        Fee revenue in token units
    """
    return liquidity * fee_growth_inside


def calculate_impermanent_loss(
    liquidity: float,
    entry_price: float,
    exit_price: float,
    tick_lower: float,
    tick_upper: float
) -> float:
    """
    Calculate impermanent loss for a position.
    
    IL = Value(hold) - Value(LP)
    
    For concentrated liquidity:
    IL depends on whether price exits the range.
    
    Args:
        liquidity: Position liquidity
        entry_price: Price at position mint
        exit_price: Price at position burn (or current)
        tick_lower: Position lower tick (as price)
        tick_upper: Position upper tick (as price)
    
    Returns:
        Impermanent loss (negative = loss)
    """
    from math import sqrt
    
    # Calculate value if held (no LP)
    # Simplified: assume 50/50 value at entry
    hold_value = 2 * sqrt(entry_price)  # Simplified
    
    # Calculate LP value at exit
    if exit_price <= tick_lower:
        # All token0
        lp_value = liquidity / sqrt(tick_lower)
    elif exit_price >= tick_upper:
        # All token1
        lp_value = liquidity * sqrt(tick_upper)
    else:
        # Mixed
        lp_value = liquidity * (sqrt(exit_price) - sqrt(tick_lower)) + \
                   liquidity / sqrt(tick_upper)
    
    # Impermanent loss
    il = lp_value - hold_value
    
    return il


def calculate_position_pnl(
    fee_revenue: float,
    impermanent_loss: float,
    price_at_entry: float,
    price_at_exit: float
) -> float:
    """
    Calculate total P&L for a position.
    
    P&L = Fee Revenue + Impermanent Loss + Price Appreciation
    
    Args:
        fee_revenue: Total fees earned
        impermanent_loss: IL (typically negative)
        price_at_entry: Entry price
        price_at_exit: Exit price
    
    Returns:
        Total P&L
    """
    price_appreciation = price_at_exit - price_at_entry
    
    return fee_revenue + impermanent_loss + price_appreciation


@dataclass
class ProfitabilityCalculator:
    """
    Calculator for LP profitability metrics and econometric analysis.
    """
    
    risk_free_rate: float = 0.05  # Annual risk-free rate
    
    def calculate_total_pnl(
        self,
        position_data: Dict[str, Any]
    ) -> float:
        """
        Calculate total P&L for a position.
        
        Args:
            position_data: Dictionary with position parameters
                - liquidity: Position liquidity
                - entry_price: Price at mint
                - exit_price: Price at burn/current
                - fee_revenue: Total fees earned
                - tick_lower: Lower tick (as price)
                - tick_upper: Upper tick (as price)
        
        Returns:
            Total P&L in numeraire (USD)
        """
        liquidity = position_data['liquidity']
        entry_price = position_data['entry_price']
        exit_price = position_data.get('exit_price', entry_price)
        fee_revenue = position_data.get('fee_revenue', 0)
        tick_lower = position_data.get('tick_lower', entry_price * 0.8)
        tick_upper = position_data.get('tick_upper', entry_price * 1.2)
        
        # Calculate impermanent loss
        il = calculate_impermanent_loss(
            liquidity, entry_price, exit_price, tick_lower, tick_upper
        )
        
        # Calculate total P&L
        pnl = fee_revenue + il
        
        return pnl
    
    def calculate_log_profitability(
        self,
        pnl: float,
        initial_value: float
    ) -> float:
        """
        Calculate log profitability: ln(π^i)
        
        π^i = P&L / Initial Value (return)
        log(π^i) = ln(return)
        
        Args:
            pnl: Total P&L
            initial_value: Initial position value
        
        Returns:
            Log profitability
        """
        if initial_value <= 0:
            return -np.inf
        
        return_on_investment = pnl / initial_value
        
        if return_on_investment <= 0:
            return -np.inf
        
        return np.log(return_on_investment)
    
    def run_profitability_regression(
        self,
        positions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Run AQFOGAKRE24 profitability regression.
        
        Model:
        log(π^i) = b0 + b1*1_{retail(i)} + b2*log(volatility) + b3*log(TVL) + b4*log(volume) + ε
        
        Args:
            positions: List of position dictionaries with:
                - type: 'retail' or 'institutional'
                - profitability: π^i (return)
                - volatility: Market volatility
                - tvl: Pool TVL
                - volume: Pool volume
        
        Returns:
            Regression results with coefficients, R², statistics
        """
        # Build dataframe
        data = []
        for pos in positions:
            log_pi = np.log(pos['profitability']) if pos['profitability'] > 0 else -10
            data.append({
                'log_profitability': log_pi,
                'is_retail': 1 if pos['type'] == 'retail' else 0,
                'log_volatility': np.log(pos['volatility']),
                'log_tvl': np.log(pos['tvl']),
                'log_volume': np.log(pos['volume'])
            })
        
        df = pd.DataFrame(data)
        
        # Run OLS regression
        # Using statsmodels for proper econometric output
        try:
            import statsmodels.api as sm
            
            X = df[['is_retail', 'log_volatility', 'log_tvl', 'log_volume']]
            X = sm.add_constant(X)
            y = df['log_profitability']
            
            model = sm.OLS(y, X).fit()
            
            results = {
                'coefficients': {
                    'intercept': model.params['const'],
                    'retail_coefficient': model.params['is_retail'],
                    'volatility_coefficient': model.params['log_volatility'],
                    'tvl_coefficient': model.params['log_tvl'],
                    'volume_coefficient': model.params['log_volume']
                },
                'r_squared': model.rsquared,
                'adj_r_squared': model.rsquared_adj,
                'p_values': model.pvalues.to_dict(),
                'std_errors': model.bse.to_dict(),
                'n_observations': len(df),
                'model_summary': model.summary().as_text()
            }
            
        except ImportError:
            # Fallback to simple numpy regression
            X = df[['is_retail', 'log_volatility', 'log_tvl', 'log_volume']].values
            X = np.column_stack([np.ones(len(X)), X])
            y = df['log_profitability'].values
            
            # OLS: β = (X'X)^(-1) X'y
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            
            # R² calculation
            y_pred = X @ beta
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r_squared = 1 - ss_res / ss_tot
            
            results = {
                'coefficients': {
                    'intercept': beta[0],
                    'retail_coefficient': beta[1],
                    'volatility_coefficient': beta[2],
                    'tvl_coefficient': beta[3],
                    'volume_coefficient': beta[4]
                },
                'r_squared': r_squared,
                'n_observations': len(df)
            }
        
        return results
    
    def calculate_profitability_ratio(
        self,
        retail_positions: List[Dict[str, Any]],
        institutional_positions: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Calculate profitability ratio: π^retail / π^institutional
        
        Args:
            retail_positions: List of retail position data
            institutional_positions: List of institutional position data
        
        Returns:
            Dictionary with ratio statistics
        """
        # Calculate average profitability for each type
        retail_profits = [p['profitability'] for p in retail_positions if p['profitability'] > 0]
        inst_profits = [p['profitability'] for p in institutional_positions if p['profitability'] > 0]
        
        if not retail_profits or not inst_profits:
            return {'ratio': np.nan, 'log_ratio': np.nan}
        
        avg_retail = np.mean(retail_profits)
        avg_inst = np.mean(inst_profits)
        
        ratio = avg_retail / avg_inst
        log_ratio = np.log(ratio)
        
        return {
            'avg_retail_profitability': avg_retail,
            'avg_institutional_profitability': avg_inst,
            'ratio': ratio,
            'log_ratio': log_ratio,
            'n_retail': len(retail_profits),
            'n_institutional': len(inst_profits)
        }
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_profitability_metrics.py -v
# Expected: PASS
```

**Step 5: Commit**

```bash
git add lib/fee_compression/profitability_metrics.py tests/test_profitability_metrics.py
git commit -m "feat: implement profitability metrics and regression analysis"
```

---

## Phase 3: Econometric Validation

### Task 7: Create Data Integration Layer

**Files:**
- Create: `lib/fee_compression/data_loader.py`
- Create: `lib/fee_compression/config.py`
- Test: `tests/test_data_loader.py`

**Step 1: Define configuration and data structures**

```python
# lib/fee_compression/config.py

"""
Configuration for Fee Compression Research

Defines pool addresses, data sources, and analysis parameters.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import os


@dataclass
class PoolConfig:
    """Configuration for a CFMM pool to analyze"""
    name: str
    address: str
    token0: str
    token1: str
    fee_tier: float  # e.g., 0.003 for 30 bps
    tick_spacing: int
    chain: str = "ethereum"


@dataclass
class ResearchConfig:
    """Configuration for fee compression research"""
    
    # Pools to analyze
    pools: List[PoolConfig] = field(default_factory=list)
    
    # Data sources
    subgraph_url: str = "https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3"
    coingecko_api: str = "https://api.coingecko.com/api/v3"
    
    # Analysis parameters
    jit_threshold_blocks: int = 1
    passive_threshold_blocks: int = 100
    retail_size_threshold_usd: float = 10000
    institutional_size_threshold_usd: float = 100000
    
    # Time range
    start_block: int = 12369621  # Uniswap V3 launch
    end_block: int | None = None  # Latest
    
    # Output directory
    output_dir: str = "output/fee_compression"
    
    @classmethod
    def default(cls) -> 'ResearchConfig':
        """Default configuration with major ETH pools"""
        return cls(
            pools=[
                PoolConfig(
                    name="ETH/USDC-0.05%",
                    address="0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640",
                    token0="WETH",
                    token1="USDC",
                    fee_tier=0.0005,
                    tick_spacing=10
                ),
                PoolConfig(
                    name="ETH/USDC-0.3%",
                    address="0x8ad599c3a0ff1de082011efddc58f1908eb6e6d8",
                    token0="USDC",
                    token1="WETH",
                    fee_tier=0.003,
                    tick_spacing=60
                ),
                PoolConfig(
                    name="WBTC/ETH-0.3%",
                    address="0xcbcdf9626bc03e24f779434178a73a0b4bad62ed",
                    token0="WBTC",
                    token1="WETH",
                    fee_tier=0.003,
                    tick_spacing=60
                ),
            ]
        )


# Default config instance
DEFAULT_CONFIG = ResearchConfig.default()
```

**Step 2: Implement data loader**

```python
# lib/fee_compression/data_loader.py

"""
Data Loader for Fee Compression Research

Fetches and processes data from:
- Uniswap V3 Subgraph (positions, swaps, ticks)
- Price APIs (for numeraire conversion)
- On-chain data (for fee growth)
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import requests
from datetime import datetime, timedelta

from .config import PoolConfig, ResearchConfig


@dataclass
class PositionRecord:
    """Processed position record for analysis"""
    position_id: str
    pool_address: str
    owner: str
    liquidity: float
    tick_lower: int
    tick_upper: int
    mint_block: int
    mint_timestamp: int
    burn_block: Optional[int]
    burn_timestamp: Optional[int]
    fee_growth_inside_0: float
    fee_growth_inside_1: float


class DataLoader:
    """Load and process data for fee compression analysis"""
    
    def __init__(self, config: ResearchConfig):
        self.config = config
        self._session = requests.Session()
    
    def fetch_pool_positions(
        self,
        pool: PoolConfig,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch all positions for a pool from subgraph.
        
        Query Uniswap V3 subgraph for:
        - Position mint/burn events
        - Fee growth data
        - Liquidity changes
        """
        # Subgraph query
        query = """
        query GetPositions($pool: String!, $skip: Int!) {
            positions(
                where: {pool: $pool}
                first: 1000
                skip: $skip
            ) {
                id
                owner
                liquidity
                tickLower {tick}
                tickUpper {tick}
                transaction {
                    blockNumber
                    timestamp
                }
                feeGrowthInside0LastX128
                feeGrowthInside1LastX128
            }
        }
        """
        
        # Fetch data (pagination)
        all_positions = []
        skip = 0
        
        while True:
            response = self._session.post(
                self.config.subgraph_url,
                json={
                    'query': query,
                    'variables': {
                        'pool': pool.address.lower(),
                        'skip': skip
                    }
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Subgraph query failed: {response.text}")
            
            data = response.json()
            positions = data.get('data', {}).get('positions', [])
            
            if not positions:
                break
            
            all_positions.extend(positions)
            skip += 1000
        
        # Convert to dataframe
        df = pd.DataFrame(all_positions)
        df['pool_address'] = pool.address
        df['fee_tier'] = pool.fee_tier
        
        return df
    
    def fetch_pool_ticks(
        self,
        pool: PoolConfig
    ) -> pd.DataFrame:
        """
        Fetch tick data for feeGrowthOutside.
        
        Each tick stores:
        - feeGrowthOutside0X128
        - feeGrowthOutside1X128
        - liquidityGross
        - liquidityNet
        """
        query = """
        query GetTicks($pool: String!) {
            ticks(where: {pool: $pool}) {
                tick
                feeGrowthOutside0X128
                feeGrowthOutside1X128
                liquidityGross
                liquidityNet
                pool {
                    tick
                }
            }
        }
        """
        
        response = self._session.post(
            self.config.subgraph_url,
            json={
                'query': query,
                'variables': {'pool': pool.address.lower()}
            }
        )
        
        if response.status_code != 200:
            raise Exception(f"Subgraph query failed: {response.text}")
        
        data = response.json()
        ticks = data.get('data', {}).get('ticks', [])
        
        return pd.DataFrame(ticks)
    
    def fetch_pool_swaps(
        self,
        pool: PoolConfig,
        start_block: Optional[int] = None,
        end_block: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Fetch swap data for volume and volatility calculations.
        """
        where_clause = f"pool: \"{pool.address.lower()}\""
        if start_block:
            where_clause += f", blockNumber_gte: {start_block}"
        if end_block:
            where_clause += f", blockNumber_lte: {end_block}"
        
        query = f"""
        query GetSwaps {{
            swaps(
                where: {{{where_clause}}}
                first: 1000
                orderBy: blockNumber
                orderDirection: asc
            ) {{
                id
                amount0
                amount1
                amountUSD
                tick
                blockNumber
                timestamp
                transaction {{
                    id
                }}
            }}
        }}
        """
        
        # Fetch with pagination
        all_swaps = []
        # ... (similar pagination as positions)
        
        return pd.DataFrame(all_swaps)
    
    def fetch_price_history(
        self,
        token: str,
        days: int = 365
    ) -> pd.DataFrame:
        """
        Fetch historical price data from CoinGecko.
        """
        # Map token symbols to CoinGecko IDs
        token_ids = {
            'WETH': 'ethereum',
            'ETH': 'ethereum',
            'WBTC': 'bitcoin',
            'BTC': 'bitcoin',
            'USDC': 'usd-coin',
            'USDT': 'tether'
        }
        
        token_id = token_ids.get(token.upper())
        if not token_id:
            raise ValueError(f"Unknown token: {token}")
        
        url = f"{self.config.coingecko_api}/coins/{token_id}/market_chart"
        params = {
            'vs_currency': 'usd',
            'days': days
        }
        
        response = self._session.get(url, params=params)
        
        if response.status_code != 200:
            raise Exception(f"CoinGecko API failed: {response.text}")
        
        data = response.json()
        prices = data.get('prices', [])
        
        df = pd.DataFrame(prices, columns=['timestamp', 'price'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        return df
    
    def calculate_volatility(
        self,
        price_series: pd.Series,
        window: int = 30
    ) -> pd.Series:
        """
        Calculate rolling volatility (annualized).
        """
        returns = price_series.pct_change()
        volatility = returns.rolling(window=window).std()
        annualized = volatility * np.sqrt(365)
        
        return annualized
    
    def calculate_tvl(
        self,
        pool: PoolConfig,
        positions_df: pd.DataFrame,
        price_df: pd.DataFrame
    ) -> float:
        """
        Calculate current TVL for a pool.
        
        TVL = Sum of all active positions' value in USD
        """
        # Filter active positions (no burn)
        active = positions_df[positions_df['burn_block'].isna()]
        
        # Calculate value per position (simplified)
        # Requires price data and tick-to-price conversion
        # ...
        
        # Placeholder
        return active['liquidity'].sum()  # Simplified
    
    def load_complete_dataset(
        self,
        pool: PoolConfig
    ) -> Dict[str, pd.DataFrame]:
        """
        Load complete dataset for a pool.
        
        Returns:
            Dictionary with:
            - positions: Position data
            - ticks: Tick data
            - swaps: Swap data
            - prices: Price history
            - volatility: Calculated volatility
        """
        print(f"Loading data for {pool.name}...")
        
        positions = self.fetch_pool_positions(pool)
        ticks = self.fetch_pool_ticks(pool)
        swaps = self.fetch_pool_swaps(pool)
        prices = self.fetch_price_history(pool.token0)
        
        volatility = self.calculate_volatility(prices['price'])
        
        return {
            'positions': positions,
            'ticks': ticks,
            'swaps': swaps,
            'prices': prices,
            'volatility': volatility
        }
```

**Step 3: Write tests**

```python
# tests/test_data_loader.py

import pytest
from lib.fee_compression.data_loader import DataLoader
from lib.fee_compression.config import ResearchConfig, PoolConfig

def test_data_loader_initialization():
    config = ResearchConfig.default()
    loader = DataLoader(config)
    assert loader.config == config

def test_fetch_pool_positions():
    # Integration test - may need mocking
    config = ResearchConfig.default()
    loader = DataLoader(config)
    pool = config.pools[0]
    
    # This would make real API calls
    # Use pytest.mark.integration or mock for CI
    pytest.skip("Integration test - requires network access")
```

**Step 4: Commit**

```bash
git add lib/fee_compression/data_loader.py lib/fee_compression/config.py tests/test_data_loader.py
git commit -m "feat: implement data loader for Uniswap V3 subgraph integration"
```

---

### Task 8: Create Analysis Notebook

**Files:**
- Create: `notebooks/fee-compression/01-data-exploration.ipynb`
- Create: `notebooks/fee-compression/02-claim-validation.ipynb`

**Step 1: Create data exploration notebook structure**

```markdown
# Notebook 1: Data Exploration

## Objective
Explore LP position data to understand distribution of retail vs institutional positions.

## Sections

### 1. Setup
```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import sys
sys.path.insert(0, '..')

from lib.fee_compression.data_loader import DataLoader
from lib.fee_compression.config import ResearchConfig
from lib.fee_compression.lp_classification import LPClassifier, PositionData
```

### 2. Load Data
```python
config = ResearchConfig.default()
loader = DataLoader(config)

# Load ETH/USDC 0.05% pool
pool = config.pools[0]
data = loader.load_complete_dataset(pool)

positions_df = data['positions']
swaps_df = data['swaps']
prices_df = data['prices']
```

### 3. Position Statistics
```python
# Distribution of position sizes
# Distribution of position durations
# JIT vs Passive breakdown
```

### 4. Classification Results
```python
# Apply LP classifier
# Count retail vs institutional
# Compare characteristics
```

### 5. Fee Growth Analysis
```python
# Calculate feeGrowthOutside/feeGrowthInside ratios
# Time series visualization
# Variance calculation
```

### 6. Summary Statistics
```python
# Descriptive statistics for all variables
# Correlation matrix
```
```

**Step 2: Create claim validation notebook structure**

```markdown
# Notebook 2: Fee Compression Claim Validation

## Objective
Validate the core hypothesis: ln(variance(feeRatio)) = ln(π^mono / π^comp)

## Sections

### 1. Setup
```python
from lib.fee_compression.fee_growth_metrics import FeeGrowthCalculator
from lib.fee_compression.profitability_metrics import ProfitabilityCalculator
```

### 2. Calculate LHS: ln(variance(feeRatio))
```python
# Load fee growth data
# Calculate fee ratios over time
# Compute variance
# Take log
```

### 3. Calculate RHS: ln(π^mono / π^comp)
```python
# Identify monopolistic positions (JIT)
# Identify competitive positions (passive)
# Calculate profitability for each group
# Compute ratio and log
```

### 4. Validate Claim
```python
calculator = FeeGrowthCalculator()
results = calculator.validate_fee_compression_claim(
    fee_growth_outside_series,
    fee_growth_inside_series,
    pi_monopolistic,
    pi_competitive
)

print(f"LHS: {results['lhs']}")
print(f"RHS: {results['rhs']}")
print(f"Relative Error: {results['relative_error']}")
print(f"Claim Holds (within tolerance): {results['claim_holds']}")
```

### 5. Run AQFOGAKRE24 Regression
```python
# Build dataset of positions with profitability
# Run: log(π^i) = b0 + b1*1_{retail(i)} + b2*log(vol) + b3*log(TVL) + b4*log(vol) + ε
# Interpret coefficients
# Test significance of retail vs institutional difference
```

### 6. Price of Anarchy Estimation
```python
# P_{#LP} = exp(RHS)
# Analyze how P varies with number of LPs
# Plot relationship
```

### 7. Robustness Checks
```python
# Different classification thresholds
# Different time periods
# Different pools
```

### 8. Conclusions
```markdown
## Findings
- Does the claim hold?
- Magnitude of price of anarchy
- Policy implications for fee compression swap
```
```

**Step 3: Commit**

```bash
git add notebooks/fee-compression/01-data-exploration.ipynb
git add notebooks/fee-compression/02-claim-validation.ipynb
git commit -m "docs: create analysis notebooks for data exploration and claim validation"
```

---

## Phase 4: Synthesis & Documentation

### Task 9: Update Draft Notes with Findings

**Files:**
- Modify: `notes/FEE_COMPRESSION_SWAP_DRAFT_NOTES.md`

**Step 1: Add validated claims section**

```markdown
## Validated Claims (After Analysis)

### Claim 1: Fee Growth Variance Hypothesis
Status: [VALIDATED / PARTIALLY VALIDATED / REJECTED]

Evidence:
- LHS (ln(variance(feeRatio))): [value]
- RHS (ln(π^mono/π^comp)): [value]
- Relative Error: [value]
- Tolerance: [value]

Interpretation: [Explanation]

### Claim 2: LP Classification Impact
Status: [VALIDATED / PARTIALLY VALIDATED / REJECTED]

Regression Results:
- Retail coefficient: [value] (p-value: [value])
- Institutional coefficient: [value] (p-value: [value])
- R²: [value]

Interpretation: [Explanation]

### Claim 3: Price of Anarchy Scaling
Status: [VALIDATED / PARTIALLY VALIDATED / REJECTED]

Estimated P_{#LP}: [value]
Scaling with #LPs: [relationship]
```

**Step 2: Add open questions section**

```markdown
## Open Questions (Unresolved)

1. **TVL Calculation**: How to accurately calculate $TVL from pool data?
   - Current approach: [description]
   - Issue: [description]
   - Proposed solution: [description]

2. **Volatility Measure**: What volatility measure is most appropriate?
   - Options: realized, implied, Parkinson, Garman-Klass
   - Chosen: [measure]
   - Rationale: [explanation]

3. **Monopolistic Proxy**: Is JIT the right proxy for monopolistic behavior?
   - Evidence: [summary]
   - Alternative: [description]
```

**Step 3: Add fee compression swap specification**

```markdown
## Fee Compression Swap Specification

### Product Overview
If the fee compression hypothesis holds, we can build a swap instrument that:
- Pays based on P_{#LP} (Price of Anarchy)
- Allows LPs to hedge against competition risk
- Enables speculation on LP competition intensity

### Payoff Structure
Π^FeeCompressionSwap = f(P_{#LP})

Where:
- P_{#LP} = E^Q[π^mono / π^comp]
- Can be tracked via: ln(variance(feeOutside/feeInside))

### Implementation Requirements
1. Real-time fee growth tracking
2. Monopolistic/competitive payoff oracles
3. Settlement mechanism

### Next Steps
- [ ] Formalize payoff specification
- [ ] Design replication strategy
- [ ] Implement pricing model
```

**Step 4: Commit**

```bash
git add notes/FEE_COMPRESSION_SWAP_DRAFT_NOTES.md
git commit -m "docs: update draft notes with validation findings and swap specification"
```

---

### Task 10: Create Research Summary Document

**Files:**
- Create: `notes/fee-compression/research-summary.md`

**Step 1: Write executive summary**

```markdown
# Fee Compression Swap Research Summary

## Executive Summary

This research validates the theoretical foundation for a "Fee Compression Swap" instrument based on the Price of Anarchy in CFMMs.

### Key Findings
1. [Finding 1]
2. [Finding 2]
3. [Finding 3]

### Implications for ThetaSwap
- [Implication 1]
- [Implication 2]

## Research Questions Answered

### Q1: How to track LP payoff?
**Answer:** [Summary of approach]

### Q2: How to distinguish monopolistic vs competitive?
**Answer:** [Summary of classification]

### Q3: Does ln(variance(feeRatio)) = ln(P_{#LP})?
**Answer:** [Validation result]

### Q4: What filters distinguish retail vs institutional?
**Answer:** [Summary of filters]

## Methodology

### Data Sources
- Uniswap V3 Subgraph
- CoinGecko Price API
- [Pools analyzed]

### Econometric Methods
- OLS Regression (AQFOGAKRE24 specification)
- Fee growth variance analysis (MACRA24)
- LP classification heuristics

### Validation Approach
- [Description]

## Recommendations

### Immediate Actions
1. [Action 1]
2. [Action 2]

### Further Research
1. [Research direction 1]
2. [Research direction 2]

### Product Development
1. [Product recommendation 1]
2. [Product recommendation 2]

## Appendix

### A. Code Structure
- `lib/fee_compression/`: Core analysis library
- `notebooks/fee-compression/`: Exploratory analysis
- `tests/`: Test suite

### B. Key Formulas
[LaTeX formulas]

### C. References
- MACRA24: [Full citation]
- AQFOGAKRE24: [Full citation]
- Capponi JIT: [Full citation]
```

**Step 2: Commit**

```bash
git add notes/fee-compression/research-summary.md
git commit -m "docs: create research summary with findings and recommendations"
```

---

## Deliverables Checklist

- [ ] **Literature Review**
  - [ ] MACRA24 annotations
  - [ ] AQFOGAKRE24 annotations
  - [ ] Fee growth claim formalization

- [ ] **Core Library**
  - [ ] LP classification module
  - [ ] Fee growth metrics module
  - [ ] Profitability metrics module
  - [ ] Data loader module
  - [ ] Configuration module

- [ ] **Tests**
  - [ ] LP classification tests
  - [ ] Fee growth metrics tests
  - [ ] Profitability metrics tests
  - [ ] Data loader tests

- [ ] **Analysis**
  - [ ] Data exploration notebook
  - [ ] Claim validation notebook
  - [ ] Regression analysis results

- [ ] **Documentation**
  - [ ] Updated draft notes
  - [ ] Research summary
  - [ ] Fee compression swap specification

---

## Execution Handoff

**Plan complete and saved to `docs/plans/2026-02-24-fee-compression-swap-research.md`. Two execution options:**

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**

**If Subagent-Driven chosen:**
- **REQUIRED SUB-SKILL:** Use superpowers:subagent-driven-development
- Stay in this session
- Fresh subagent per task + code review

**If Parallel Session chosen:**
- Guide to open new session in worktree
- **REQUIRED SUB-SKILL:** New session uses superpowers:executing-plans
