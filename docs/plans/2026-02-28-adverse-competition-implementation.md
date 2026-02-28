# Adverse Competition Impact Test — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `AdverseCompetitionModel` (Stage 2) that proves the congestion index ΔI_t has a negative, statistically significant impact on LP fee-adjusted returns, orthogonal to LVR.

**Architecture:** Two-step OLS inside a callable class. Step 2a regresses fee_yield on volume_ratio to extract the residual η_t (fee yield orthogonal to LVR). Step 2b regresses η_t on ΔI_t with HC1 robust standard errors to get δ₂. Returns a frozen dataclass `AdverseCompetition` with free function accessors matching the existing `LiquidityState` pattern.

**Tech Stack:** Python 3, statsmodels (OLS + HC1), pandas, numpy, unittest

**Design doc:** `docs/plans/2026-02-28-adverse-competition-design.md`

---

## Background

### What already exists

- **`data/Econometrics.py`** — contains `LiquidityState` (frozen dataclass), `LiquidityStateModel` (callable), and free function accessors `beta()`, `rho()`, `state()`, `result()`. This is Stage 1: it extracts the congestion index ΔI_t from a structural state-space model.

- **`tests/test_Econometrics.py`** — contains `TestLiquidityStateAccessors` (8 mock tests), `TestLiquidityStateModelStructure` (7 real-data tests), `TestCongestionIndex` (4 hypothesis tests). All 19 tests pass.

- **`data/DataHandler.py`** — provides `PoolEntryData`, `feesUSD()`, `tvlUSD()`, `volumeUSD()`, `div()`, `delta()`, `priceUSD()`, `lagged()`, `txCount()`, `normalize()`.

- **`data/UniswapClient.py`** — provides `UniswapClient`, `v3()`, `v4()`.

### What we're building

Stage 2 of the two-stage estimation. The design doc specifies:

1. `AdverseCompetition` — frozen dataclass with `_delta` (float), `_residual` (TimeSeries), `_result` (object)
2. `delta_coeff()`, `residual()`, `ols_result()` — free function accessors
3. `AdverseCompetitionModel` — callable class with `__call__(fee_yield, volume_ratio, congestion) -> AdverseCompetition`

### Codebase conventions

- **Frozen dataclasses** with underscore-prefixed private fields
- **Free function accessors** (not methods): `delta_coeff(ac)` not `ac.delta_coeff`
- **Callable classes**: `AdverseCompetitionModel()(fee_yield=..., ...)`
- **Caller-composed inputs**: the caller builds fee_yield, volume_ratio, congestion from DataHandler free functions — the model doesn't know about pool data
- **Real subgraph data in tests**: no mocks for integration/hypothesis tests (only for accessor unit tests)

### How to run tests

```bash
source uhi8/bin/activate
python -m pytest tests/test_Econometrics.py -v
```

### Existing test data setup pattern

Tests that need real data use `setUpClass` to fetch V3 USDC/WETH pool data once:

```python
V3_USDC_WETH = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"

@classmethod
def setUpClass(cls):
    client = UniswapClient(v3())
    pool = PoolEntryData(V3_USDC_WETH, client=client)
    cls.pool_data = pool(pool.lifetimeLen())
```

---

## Task 1: AdverseCompetition dataclass and accessor tests

**Files:**
- Modify: `tests/test_Econometrics.py` — add `TestAdverseCompetitionAccessors` class at end of file (before `if __name__`)

**Step 1: Write the failing tests**

Add this class to `tests/test_Econometrics.py` right before the `if __name__ == "__main__":` line. Also update the import on line 26 to include the new names.

Update line 26 from:
```python
from data.Econometrics import LiquidityState, LiquidityStateModel, beta, rho, state, result
```
to:
```python
from data.Econometrics import (
    LiquidityState, LiquidityStateModel, beta, rho, state, result,
    AdverseCompetition, delta_coeff, residual, ols_result
)
```

Then add the test class:

```python
class TestAdverseCompetitionAccessors(unittest.TestCase):
    """Test AdverseCompetition dataclass and free function accessors"""

    def setUp(self):
        self.ac = AdverseCompetition(
            _delta=-0.03,
            _residual=pd.Series([0.1, -0.2, 0.05]),
            _result="mock_ols"
        )

    def test_delta_returns_float(self):
        self.assertIsInstance(delta_coeff(self.ac), float)

    def test_delta_returns_value(self):
        self.assertAlmostEqual(delta_coeff(self.ac), -0.03)

    def test_residual_returns_series(self):
        self.assertIsInstance(residual(self.ac), pd.Series)

    def test_ols_result_returns_value(self):
        self.assertEqual(ols_result(self.ac), "mock_ols")

    def test_frozen(self):
        with self.assertRaises(AttributeError):
            self.ac._delta = 999
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_Econometrics.py::TestAdverseCompetitionAccessors -v`
Expected: FAIL — `ImportError: cannot import name 'AdverseCompetition'`

**Step 3: Commit failing tests**

```bash
git add tests/test_Econometrics.py
git commit -m "test: add AdverseCompetition accessor tests (failing)"
```

---

## Task 2: AdverseCompetition dataclass and accessors

**Files:**
- Modify: `data/Econometrics.py` — add `AdverseCompetition` dataclass and three free function accessors after the existing `result()` function (line 33) and before the `LiquidityStateModel` class (line 36)

**Step 1: Add the dataclass and accessors**

Insert the following after the `result()` function (after line 33) and before `class LiquidityStateModel:` (line 36):

```python

@dataclass(frozen=True)
class AdverseCompetition:
    _delta: float
    _residual: TimeSeries
    _result: object


def delta_coeff(ac: AdverseCompetition) -> float:
    return ac._delta


def residual(ac: AdverseCompetition) -> TimeSeries:
    return ac._residual


def ols_result(ac: AdverseCompetition) -> object:
    return ac._result

```

**Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_Econometrics.py::TestAdverseCompetitionAccessors -v`
Expected: 5 PASSED

**Step 3: Run ALL existing tests to verify no regressions**

Run: `python -m pytest tests/test_Econometrics.py -v`
Expected: 24 PASSED (19 existing + 5 new)

**Step 4: Commit**

```bash
git add data/Econometrics.py tests/test_Econometrics.py
git commit -m "feat: add AdverseCompetition dataclass and accessors"
```

---

## Task 3: AdverseCompetitionModel integration tests (failing)

**Files:**
- Modify: `tests/test_Econometrics.py` — add `TestAdverseCompetition` class with real V3 data, and update import to include `AdverseCompetitionModel`

**Step 1: Update imports and add integration test class**

Update the import to also include `AdverseCompetitionModel`:

```python
from data.Econometrics import (
    LiquidityState, LiquidityStateModel, beta, rho, state, result,
    AdverseCompetition, AdverseCompetitionModel, delta_coeff, residual, ols_result
)
```

Also add `feesUSD, volumeUSD` to the DataHandler import:

```python
from data.DataHandler import (
    PoolEntryData, delta, tvlUSD, priceUSD, div, lagged, txCount, normalize,
    feesUSD, volumeUSD
)
```

Add this test class before `if __name__ == "__main__":`:

```python
class TestAdverseCompetition(unittest.TestCase):
    """Test adverse competition hypothesis — Stage 2 of two-stage estimation.

    Stage 1: ΔI_t extracted by LiquidityStateModel (congestion index)
    Stage 2a: fee_yield ~ volume_ratio → η_t (fee yield orthogonal to LVR)
    Stage 2b: η_t ~ ΔI_t → δ₂ (adverse competition impact)

    Hypothesis:
    - δ₂ < 0: congestion reduces fee capture quality (adverse competition)
    - p < 0.05: statistically significant
    - corr(η_t, volume/TVL) ≈ 0: residual is orthogonal to LVR
    """

    @classmethod
    def setUpClass(cls):
        client = UniswapClient(v3())
        pool = PoolEntryData(V3_USDC_WETH, client=client)
        cls.pool_data = pool(pool.lifetimeLen())

        # Stage 1: extract congestion index ΔI_t
        endog = div(delta(tvlUSD(cls.pool_data)), lagged(tvlUSD(cls.pool_data)))
        exog = _market_state(cls.pool_data)
        ls = LiquidityStateModel()(endog=endog, exog=exog)

        # Stage 2: adverse competition impact
        cls.fee_yield = div(feesUSD(cls.pool_data), tvlUSD(cls.pool_data))
        cls.volume_ratio = div(volumeUSD(cls.pool_data), tvlUSD(cls.pool_data))
        cls.congestion = state(ls)
        cls.ac = AdverseCompetitionModel()(
            fee_yield=cls.fee_yield,
            volume_ratio=cls.volume_ratio,
            congestion=cls.congestion
        )

    def test_returns_adverse_competition(self):
        self.assertIsInstance(self.ac, AdverseCompetition)

    def test_delta_negative(self):
        """δ₂ < 0: congestion reduces fee capture beyond what volume explains"""
        self.assertLess(delta_coeff(self.ac), 0,
            f"Expected δ₂ < 0 (adverse competition), got δ₂ = {delta_coeff(self.ac):.6f}")

    def test_delta_significant(self):
        """δ₂ significant at p < 0.05"""
        res = ols_result(self.ac)
        pval = res.pvalues.iloc[1]  # second coefficient is δ₂ (first is constant)
        self.assertLess(pval, 0.05,
            f"Expected p < 0.05 for δ₂, got p = {pval:.4f}")

    def test_residual_orthogonal_to_volume(self):
        """η_t is orthogonal to volume/TVL by construction"""
        eta = residual(self.ac)
        # Align indices
        common = eta.index.intersection(self.volume_ratio.index)
        corr = eta.loc[common].corr(self.volume_ratio.loc[common])
        self.assertAlmostEqual(corr, 0, delta=0.05,
            msg=f"Expected corr(η_t, volume/TVL) ≈ 0, got {corr:.4f}")
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_Econometrics.py::TestAdverseCompetition -v`
Expected: FAIL — `ImportError: cannot import name 'AdverseCompetitionModel'`

**Step 3: Commit failing tests**

```bash
git add tests/test_Econometrics.py
git commit -m "test: add AdverseCompetition integration tests (failing)"
```

---

## Task 4: Implement AdverseCompetitionModel

**Files:**
- Modify: `data/Econometrics.py` — add `import statsmodels.api as sm` and `AdverseCompetitionModel` class at the end of the file

**Step 1: Add the OLS import**

Add this import at the top of `data/Econometrics.py`, after the existing `from statsmodels.tsa.statespace.structural import UnobservedComponents` line:

```python
import statsmodels.api as sm
```

**Step 2: Add AdverseCompetitionModel class**

Append this class at the end of `data/Econometrics.py`:

```python

class AdverseCompetitionModel:
    def __call__(
        self,
        fee_yield: TimeSeries,
        volume_ratio: TimeSeries,
        congestion: TimeSeries
    ) -> AdverseCompetition:
        # Align all series on common finite index
        combined = pd.DataFrame({
            "fee_yield": fee_yield,
            "volume_ratio": volume_ratio,
            "congestion": congestion
        }).dropna()
        mask = combined.apply(np.isfinite).all(axis=1)
        clean = combined[mask]

        # Step 2a: fee_yield ~ volume_ratio → extract η_t
        X_vol = sm.add_constant(clean["volume_ratio"])
        res_vol = sm.OLS(clean["fee_yield"], X_vol).fit()
        eta = pd.Series(res_vol.resid, index=clean.index)

        # Step 2b: η_t ~ ΔI_t with HC1 robust SEs
        X_cong = sm.add_constant(clean["congestion"])
        res_cong = sm.OLS(eta, X_cong).fit(cov_type="HC1")
        delta = float(res_cong.params.iloc[1])

        return AdverseCompetition(
            _delta=delta,
            _residual=eta,
            _result=res_cong
        )
```

**Step 3: Run the integration tests**

Run: `python -m pytest tests/test_Econometrics.py::TestAdverseCompetition -v`
Expected: 4 PASSED

**Step 4: Run ALL tests**

Run: `python -m pytest tests/test_Econometrics.py -v`
Expected: 28 PASSED (19 existing + 5 accessor + 4 integration)

**Step 5: Commit**

```bash
git add data/Econometrics.py tests/test_Econometrics.py
git commit -m "feat: add AdverseCompetitionModel — Stage 2 adverse competition test"
```

---

## Task 5: Verify results and commit final state

**Step 1: Run the full test suite one final time**

Run: `python -m pytest tests/test_Econometrics.py -v`
Expected: 28 PASSED

**Step 2: Review the key economic results**

Run this quick check in Python to confirm the results make sense:

```bash
python -c "
import sys; sys.path.insert(0, '.')
from data.Econometrics import LiquidityStateModel, AdverseCompetitionModel, state, delta_coeff, ols_result, residual
from data.DataHandler import PoolEntryData, feesUSD, tvlUSD, volumeUSD, div, delta, priceUSD, lagged, txCount, normalize
from data.UniswapClient import UniswapClient, v3
import pandas as pd

V3_USDC_WETH = '0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640'
client = UniswapClient(v3())
pool = PoolEntryData(V3_USDC_WETH, client=client)
pool_data = pool(pool.lifetimeLen())

endog = div(delta(tvlUSD(pool_data)), lagged(tvlUSD(pool_data)))
exog = pd.DataFrame({
    'delta_price': div(delta(priceUSD(pool_data)), lagged(priceUSD(pool_data))),
    'tx_activity': normalize(txCount(pool_data), window=30),
})
ls = LiquidityStateModel()(endog=endog, exog=exog)

fy = div(feesUSD(pool_data), tvlUSD(pool_data))
vr = div(volumeUSD(pool_data), tvlUSD(pool_data))
ac = AdverseCompetitionModel()(fee_yield=fy, volume_ratio=vr, congestion=state(ls))

print(f'delta_coeff (delta_2): {delta_coeff(ac):.6f}')
print(f'p-value: {ols_result(ac).pvalues.iloc[1]:.4f}')
print(f'residual length: {len(residual(ac))}')
print(f'delta_2 < 0: {delta_coeff(ac) < 0}')
print(f'p < 0.05: {ols_result(ac).pvalues.iloc[1] < 0.05}')
"
```

Expected output: δ₂ < 0 and p < 0.05 confirming adverse competition effect.

**Step 3: If all tests pass and results confirm, push**

```bash
git push
```
