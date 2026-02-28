# Econometrics Module Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement `data/Econometrics.py` with a structural state-space model (ΔL_t = β₁σ²_t + e_t, AR(1) residuals) using functional DDD style, tested with real subgraph data, and demonstrated in the notebook with plots.

**Architecture:** Callable class `LiquidityStateModel` wraps statsmodels `UnobservedComponents`. Returns frozen dataclass `LiquidityState` with private fields. Free function accessors (`beta()`, `rho()`, `state()`, `result()`) match DataHandler.py's functional style. Caller composes input series from DataHandler functions. Notebook displays results with Plotly charts using classic monochrome styling.

**Tech Stack:** Python 3.14, statsmodels, plotly, pandas, numpy. venv at `uhi8/`. Tests use real V4 subgraph data.

**Design doc:** `docs/plans/2026-02-28-econometrics-module-design.md`

---

### Task 1: Install dependencies

**Files:**
- None (venv only)

**Step 1: Install statsmodels and plotly in uhi8 venv**

```bash
source uhi8/bin/activate && pip install statsmodels plotly
```

**Step 2: Verify imports work**

```bash
source uhi8/bin/activate && python -c "from statsmodels.tsa.statespace.structural import UnobservedComponents; import plotly.graph_objects as go; print('OK')"
```

Expected: `OK`

**Step 3: Commit**

```bash
git add -A
git commit -m "chore: add statsmodels and plotly to uhi8 venv"
```

---

### Task 2: Write failing tests for LiquidityState dataclass and accessors

**Files:**
- Create: `tests/test_Econometrics.py`

**Step 1: Write the failing tests**

```python
#!/usr/bin/env python3
"""
Tests for Econometrics module — Structural state-space model

Usage:
    source uhi8/bin/activate
    python -m pytest tests/test_Econometrics.py -v

All tests use REAL subgraph data (no mocks).
"""

import os
import sys
import unittest

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.Econometrics import LiquidityState, beta, rho, state, result


class TestLiquidityStateAccessors(unittest.TestCase):
    """Test LiquidityState dataclass and free function accessors"""

    def setUp(self):
        self.ls = LiquidityState(
            _beta=-0.5,
            _rho=0.7,
            _state=pd.Series([1.0, 2.0, 3.0]),
            _result="mock_result"
        )

    def test_beta_returns_float(self):
        self.assertIsInstance(beta(self.ls), float)

    def test_beta_returns_value(self):
        self.assertEqual(beta(self.ls), -0.5)

    def test_rho_returns_float(self):
        self.assertIsInstance(rho(self.ls), float)

    def test_rho_returns_value(self):
        self.assertEqual(rho(self.ls), 0.7)

    def test_state_returns_series(self):
        self.assertIsInstance(state(self.ls), pd.Series)

    def test_state_returns_value(self):
        pd.testing.assert_series_equal(state(self.ls), pd.Series([1.0, 2.0, 3.0]))

    def test_result_returns_value(self):
        self.assertEqual(result(self.ls), "mock_result")

    def test_frozen(self):
        with self.assertRaises(AttributeError):
            self.ls._beta = 999


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run tests to verify they fail**

```bash
source uhi8/bin/activate && python -m pytest tests/test_Econometrics.py::TestLiquidityStateAccessors -v
```

Expected: FAIL with `ImportError` (current Econometrics.py has wrong imports and no free function accessors)

---

### Task 3: Implement LiquidityState and accessors

**Files:**
- Modify: `data/Econometrics.py` (replace entire file)

**Step 1: Write minimal implementation**

```python
from dataclasses import dataclass
from typing import Optional

import pandas as pd
from statsmodels.tsa.statespace.structural import UnobservedComponents

TimeSeries = pd.Series


@dataclass(frozen=True)
class LiquidityState:
    _beta: float
    _rho: float
    _state: TimeSeries
    _result: object


def beta(ls: LiquidityState) -> float:
    return ls._beta


def rho(ls: LiquidityState) -> float:
    return ls._rho


def state(ls: LiquidityState) -> TimeSeries:
    return ls._state


def result(ls: LiquidityState) -> object:
    return ls._result
```

**Step 2: Run tests to verify they pass**

```bash
source uhi8/bin/activate && python -m pytest tests/test_Econometrics.py::TestLiquidityStateAccessors -v
```

Expected: All 8 tests PASS

**Step 3: Commit**

```bash
git add data/Econometrics.py tests/test_Econometrics.py
git commit -m "feat: add LiquidityState dataclass with free function accessors"
```

---

### Task 4: Write failing tests for LiquidityStateModel structural validity

**Files:**
- Modify: `tests/test_Econometrics.py`

**Step 1: Add the structural validity test class**

Append to `tests/test_Econometrics.py`:

```python
from data.Econometrics import LiquidityStateModel
from data.DataHandler import PoolEntryData, delta, tvlUSD, variance, priceUSD


class TestLiquidityStateModelStructure(unittest.TestCase):
    """Test LiquidityStateModel returns correct types and shapes with real data"""

    @classmethod
    def setUpClass(cls):
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolEntryData(pool_id)
        cls.pool_data = pool(90)
        cls.endog = delta(tvlUSD(cls.pool_data))
        cls.exog = variance(priceUSD(cls.pool_data))
        cls.ls = LiquidityStateModel()(endog=cls.endog, exog=cls.exog)

    def test_call_returns_liquidity_state(self):
        self.assertIsInstance(self.ls, LiquidityState)

    def test_beta_is_float(self):
        self.assertIsInstance(beta(self.ls), float)

    def test_rho_is_float(self):
        self.assertIsInstance(rho(self.ls), float)

    def test_state_is_series(self):
        self.assertIsInstance(state(self.ls), pd.Series)

    def test_state_length_matches_endog(self):
        self.assertEqual(len(state(self.ls)), len(self.endog))

    def test_ar2_returns_valid_state(self):
        ls2 = LiquidityStateModel()(endog=self.endog, exog=self.exog, ar=2)
        self.assertIsInstance(ls2, LiquidityState)
        self.assertIsInstance(beta(ls2), float)
        self.assertIsInstance(rho(ls2), float)
```

**Step 2: Run tests to verify they fail**

```bash
source uhi8/bin/activate && python -m pytest tests/test_Econometrics.py::TestLiquidityStateModelStructure -v
```

Expected: FAIL with `ImportError: cannot import name 'LiquidityStateModel'`

---

### Task 5: Implement LiquidityStateModel

**Files:**
- Modify: `data/Econometrics.py`

**Step 1: Add the callable class**

Append to `data/Econometrics.py` after the accessor functions:

```python
class LiquidityStateModel:
    def __call__(
        self,
        endog: TimeSeries,
        exog: TimeSeries,
        ar: Optional[int] = 1
    ) -> LiquidityState:
        model = UnobservedComponents(
            endog,
            exog=exog,
            autoregressive=ar
        )
        results = model.fit(disp=False)

        return LiquidityState(
            _beta=float(results.params["beta.x1"]),
            _rho=float(results.params["ar.L1"]),
            _state=pd.Series(results.smoothed_state[0], index=endog.index),
            _result=results
        )
```

**Step 2: Run tests to verify they pass**

```bash
source uhi8/bin/activate && python -m pytest tests/test_Econometrics.py::TestLiquidityStateModelStructure -v
```

Expected: All 6 tests PASS

**Step 3: Commit**

```bash
git add data/Econometrics.py tests/test_Econometrics.py
git commit -m "feat: add LiquidityStateModel callable wrapping UnobservedComponents"
```

---

### Task 6: Write and run economic expectation tests

**Files:**
- Modify: `tests/test_Econometrics.py`

**Step 1: Add the economic expectations test class**

Append to `tests/test_Econometrics.py`:

```python
class TestLiquidityStateModelEconomics(unittest.TestCase):
    """Test economic hypotheses on real pool data.

    These tests validate the structural model's predictions:
    - β < 0: volatility compresses liquidity
    - 0 < γ < 1: residual is persistent but stationary
    """

    @classmethod
    def setUpClass(cls):
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolEntryData(pool_id)
        cls.pool_data = pool(90)
        cls.endog = delta(tvlUSD(cls.pool_data))
        cls.exog = variance(priceUSD(cls.pool_data))
        cls.ls = LiquidityStateModel()(endog=cls.endog, exog=cls.exog)

    def test_beta_negative(self):
        """β₁ < 0: volatility compresses liquidity changes"""
        self.assertLess(beta(self.ls), 0,
            f"Expected β < 0 (volatility compresses liquidity), got β = {beta(self.ls)}")

    def test_rho_persistent_and_stationary(self):
        """0 < γ < 1: AR(1) residual is persistent but stationary"""
        self.assertGreater(rho(self.ls), 0,
            f"Expected γ > 0 (persistent residual), got γ = {rho(self.ls)}")
        self.assertLess(rho(self.ls), 1,
            f"Expected γ < 1 (stationary residual), got γ = {rho(self.ls)}")
```

**Step 2: Run tests**

```bash
source uhi8/bin/activate && python -m pytest tests/test_Econometrics.py::TestLiquidityStateModelEconomics -v
```

Expected: PASS if the hypothesis holds on this pool's data. If FAIL, the test output tells you what the actual values are — that's a research finding.

**Step 3: Commit**

```bash
git add tests/test_Econometrics.py
git commit -m "test: add economic expectation tests for LiquidityStateModel"
```

---

### Task 7: Build notebook with Plotly charts (classic monochrome)

**Files:**
- Modify: `notebooks/econometrics.ipynb`

**Step 1: Replace cell-1 (the commented-out code cell) with data loading**

```python
import sys
sys.path.insert(0, '..')

from data.DataHandler import PoolEntryData, delta, tvlUSD, variance, priceUSD
from data.Econometrics import LiquidityStateModel, beta, rho, state, result

pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
pool = PoolEntryData(pool_id)
poolData = pool(90)

endog = delta(tvlUSD(poolData))
exog = variance(priceUSD(poolData))

ls = LiquidityStateModel()(endog=endog, exog=exog)

print(f"β₁ = {beta(ls):.6f}  (expect < 0)")
print(f"γ  = {rho(ls):.6f}  (expect 0 < γ < 1)")
print(f"State length: {len(state(ls))}")
```

**Step 2: Replace cell-2 with classic monochrome Plotly template + time series**

```python
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

# Classic monochrome template
classic = go.layout.Template()
classic.layout = go.Layout(
    font=dict(family="Courier New, monospace", size=12, color="#1a1a1a"),
    paper_bgcolor="#fafaf5",
    plot_bgcolor="#fafaf5",
    title=dict(font=dict(size=16, family="Courier New, monospace")),
    xaxis=dict(
        showgrid=True, gridcolor="#cccccc", gridwidth=0.5,
        linecolor="#1a1a1a", linewidth=1, mirror=True,
        zeroline=True, zerolinecolor="#999999", zerolinewidth=0.8
    ),
    yaxis=dict(
        showgrid=True, gridcolor="#cccccc", gridwidth=0.5,
        linecolor="#1a1a1a", linewidth=1, mirror=True,
        zeroline=True, zerolinecolor="#999999", zerolinewidth=0.8
    ),
    colorway=["#1a1a1a", "#666666", "#999999", "#bbbbbb"],
)
pio.templates["classic"] = classic
pio.templates.default = "classic"

fig = make_subplots(
    rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
    subplot_titles=("ΔL_t  (TVL change)", "σ²_t  (price variance)",
                    f"e_t  (structural residual,  γ = {rho(ls):.4f})")
)

fig.add_trace(go.Scatter(
    x=endog.index, y=endog.values, mode="lines",
    line=dict(color="#1a1a1a", width=1), showlegend=False
), row=1, col=1)
fig.add_hline(y=0, line_dash="dash", line_color="#999999", line_width=0.5, row=1, col=1)

fig.add_trace(go.Scatter(
    x=exog.index, y=exog.values, mode="lines",
    line=dict(color="#1a1a1a", width=1), showlegend=False
), row=2, col=1)

fig.add_trace(go.Scatter(
    x=state(ls).index, y=state(ls).values, mode="lines",
    line=dict(color="#1a1a1a", width=1), showlegend=False
), row=3, col=1)
fig.add_hline(y=0, line_dash="dash", line_color="#999999", line_width=0.5, row=3, col=1)

fig.update_layout(height=750, margin=dict(t=40, b=30))
fig.show()
```

**Step 3: Replace cell-3 with scatter plot and regression summary**

```python
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=exog.values, y=endog.values, mode="markers",
    marker=dict(color="#1a1a1a", size=5, opacity=0.5,
                line=dict(color="#1a1a1a", width=0.5)),
    showlegend=False
))

fig.update_layout(
    title=f"Volatility vs Liquidity Changes  (β₁ = {beta(ls):.4f})",
    xaxis_title="σ²_t  (price variance)",
    yaxis_title="ΔL_t  (TVL change)",
    height=500
)

fig.show()

print(result(ls).summary())
```

**Step 4: Run the notebook**

```bash
source uhi8/bin/activate && jupyter nbconvert --to notebook --execute notebooks/econometrics.ipynb --output econometrics.ipynb
```

Expected: Notebook executes without errors, produces 2 interactive Plotly figures and a statsmodels summary table.

**Step 5: Commit**

```bash
git add notebooks/econometrics.ipynb
git commit -m "feat: add econometrics notebook with state-space model and Plotly charts"
```

---
