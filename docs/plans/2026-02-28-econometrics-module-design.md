# Econometrics.py Module Design

**Date:** 2026-02-28
**Status:** Approved

---

## Goal

Implement `data/Econometrics.py` as a structural econometrics module that estimates the state-space model:

```
ΔL_t = β₁σ²_t + e_t
e_t = γe_{t-1} + v_t
```

Where:
- `β < 0`: volatility consistently explains liquidity changes
- `γ` is persistent (structural, not noise)

## Design Decisions

### Style: Functional + DDD (matching DataHandler.py)

- **Callable class** `LiquidityStateModel` wraps `UnobservedComponents`
- **Frozen dataclass** `LiquidityState` holds results with private fields
- **Free function accessors** `beta(ls)`, `rho(ls)`, `state(ls)`, `result(ls)` — not attribute access
- **Caller composes inputs** — model is agnostic to what series are fed in

### API: Approach B — Series as inputs, caller composes

`LiquidityStateModel.__call__` takes pre-built `endog` and `exog` series. The caller uses DataHandler functions to compose:

```python
from data.DataHandler import delta, tvlUSD, variance, priceUSD
from data.Econometrics import LiquidityStateModel, beta, rho, state

ls = LiquidityStateModel()(
    endog=delta(tvlUSD(poolData)),
    exog=variance(priceUSD(poolData))
)

beta(ls)   # β₁ < 0 ?
rho(ls)    # γ persistent ?
state(ls)  # smoothed structural residual
```

### AR order: Configurable, default 1

`ar` parameter on `__call__` defaults to 1 (matching the structural model AR(1)), but allows experimentation with higher orders.

## Components

### LiquidityState (frozen dataclass)

```python
@dataclass(frozen=True)
class LiquidityState:
    _beta: float          # β₁ — exog coefficient
    _rho: float           # γ  — AR(1) persistence
    _state: pd.Series     # smoothed unobserved component
    _result: object       # raw statsmodels result
```

### Free function accessors

```python
def beta(ls: LiquidityState) -> float
def rho(ls: LiquidityState) -> float
def state(ls: LiquidityState) -> pd.Series
def result(ls: LiquidityState) -> object
```

### LiquidityStateModel (callable)

```python
class LiquidityStateModel:
    def __call__(self, endog: pd.Series, exog: pd.Series, ar: Optional[int] = 1) -> LiquidityState
```

Wraps `statsmodels.tsa.statespace.structural.UnobservedComponents`.

## Tests

Real data tests against pool `0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5`.

### Structural validity (types and shapes)

- `__call__` returns `LiquidityState`
- `beta(result)` returns `float`
- `rho(result)` returns `float`
- `state(result)` returns `pd.Series`
- `state(result)` length matches `endog` length
- `ar=2` returns valid `LiquidityState`

### Economic expectations (hypothesis)

- `beta(result) < 0` (volatility compresses liquidity)
- `0 < rho(result) < 1` (residual is persistent but stationary)

## Files

- Modify: `data/Econometrics.py`
- Create: `tests/test_Econometrics.py`
- Modify: `notebooks/econometrics.ipynb` (use the module)
