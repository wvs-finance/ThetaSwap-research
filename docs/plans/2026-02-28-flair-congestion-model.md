# FLAIR-Based Congestion Model Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the TVL-based congestion variable with in-range liquidity (`liquidity` from subgraph) so the econometric model captures LP competition at the active tick — the FLAIR insight — instead of aggregate TVL changes that conflate in-range and out-of-range positions.

**Architecture:** Surgical input variable change. Add `liquidity` field to GraphQL query and DataHandler, then change `endog` in the econometrics notebook from `ΔtvlUSD/tvlUSD` to `Δliquidity/liquidity`. The entire econometric pipeline (LiquidityStateModel, AdverseCompetitionModel) stays unchanged. Re-run to measure R² improvement.

**Tech Stack:** Same — pandas, numpy, statsmodels, plotly, existing DataHandler/Econometrics infrastructure, Uniswap V3 subgraph.

---

### Task 1: Add `liquidity` field to GraphQL query and DataHandler

**Files:**
- Modify: `queries/PoolDataEntry.json` (line 3 — add `liquidity` to poolDayDatas fields)
- Modify: `data/DataHandler.py:101-117` (add `liquidity` extraction in `__toDataFrame`)
- Modify: `data/DataHandler.py` (add `liquidity()` accessor after `tvlUSD()` on line 143)

**Step 1: Add `liquidity` to the GraphQL query**

In `queries/PoolDataEntry.json`, the `PoolEntryData.poolTimeSeries` query lists fields for `poolDayDatas`. Add `liquidity` after `txCount`:

```json
"PoolEntryData.poolTimeSeries": "query GetPoolTimeSeries($id: ID!, $startDate: Int!, $first: Int!) { poolDayDatas(first: $first, orderBy: date, orderDirection: asc, where: { pool: $id, date_gt: $startDate }) { date tvlUSD volumeUSD feesUSD token0Price token1Price sqrtPrice txCount liquidity open high low close pool { liquidityProviderCount txCount collectedFeesUSD } } }"
```

**Step 2: Add `liquidity` extraction in `__toDataFrame`**

In `data/DataHandler.py`, inside the `to_row` lambda (line 105-114), add:

```python
"liquidity": float(day.get("liquidity") or 0),
```

after the `"txCount"` line.

**Step 3: Add `liquidity()` accessor function**

After the `tvlUSD()` function (line 143), add:

```python
def liquidity(poolData: pd.DataFrame) -> TimeSeries:
    """Get in-range liquidity time series (liquidity at active tick)."""
    return poolData["liquidity"]
```

**Step 4: Verify the field loads**

Run:
```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research && source uhi8/bin/activate && python3 -c "
from data.DataHandler import PoolEntryData, liquidity
from data.UniswapClient import UniswapClient, v3
pool = PoolEntryData('0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640', client=UniswapClient(v3()))
df = pool(10)
print(df[['tvlUSD', 'liquidity']].head())
print(f'liquidity dtype: {df[\"liquidity\"].dtype}')
print(f'liquidity nonzero: {(df[\"liquidity\"] > 0).sum()} / {len(df)}')
"
```

Expected: DataFrame has `liquidity` column with positive values. If all zeros, the V3 subgraph may use a different field name — check and adjust.

**Step 5: Commit**

```bash
git add queries/PoolDataEntry.json data/DataHandler.py
git commit -m "feat: add in-range liquidity field from subgraph (FLAIR variable)"
```

---

### Task 2: Update econometrics notebook — use liquidity-based congestion

**Files:**
- Modify: `notebooks/econometrics.ipynb` (cells 0, 1, 2, 3, 4)
- Read-only: `data/DataHandler.py`, `data/Econometrics.py`, `notes/payoff_notes.md`

**Step 1: Update cell 0 (markdown — title and overview)**

Replace the current title cell with updated framing that references FLAIR and in-range liquidity. Key changes:
- Replace "liquidity changes" with "in-range liquidity changes"
- Add FLAIR reference: competition operates on L(p̃_t; t), not TVL
- Update the Stage 1 equation: `ΔL_active / L_active` instead of `ΔL / L`

Replace the Stage 1 equation block:

```markdown
**Stage 1 — Extract congestion index:**

$$\frac{\Delta L^{\text{active}}_t}{L^{\text{active}}_{t-1}} = \beta_1 \frac{\Delta P_t}{P_{t-1}} + \beta_2 \cdot \text{txActivity}_t + e_t, \quad e_t = \gamma e_{t-1} + v_t$$

$$\Delta I_t \equiv e_t$$

where $L^{\text{active}}_t$ is the in-range liquidity at the active tick — the FLAIR-relevant variable (Milionis, Wan, Adams 2023) that determines fee distribution among LPs.
```

**Step 2: Update cell 1 (markdown — data description)**

In the Variables table, add:

```markdown
| $L^{\text{active}}_t$ | In-range liquidity at active tick |
```

In the Derived series table, change:

```markdown
| $\Delta L^{\text{active}}_t / L^{\text{active}}_{t-1}$ | `delta(liquidity) / lagged(liquidity)` |
```

**Step 3: Update cell 2 (code — imports and data loading)**

Add `liquidity` to the import line:

```python
from data.DataHandler import (
    PoolEntryData, delta, tvlUSD, priceUSD, volumeUSD, feesUSD,
    div, lagged, txCount, normalize, liquidity
)
```

After the summary statistics block, add a check:

```python
print(f"In-range liquidity: {liquidity(pool_data).median():.0f} (median)")
print(f"Correlation(tvlUSD, liquidity): {pool_data['tvlUSD'].corr(pool_data['liquidity']):.4f}")
```

**Step 4: Update cell 3 (markdown — Stage 1 model specification)**

Change "daily liquidity changes" to "daily in-range liquidity changes" in the decomposition equation. Update the endog definition:

```markdown
- Endogenous: $\Delta L^{\text{active}}_t / L^{\text{active}}_{t-1}$
```

Add a paragraph explaining why in-range liquidity is the right variable:

```markdown
### Why In-Range Liquidity?

Total value locked (TVL) conflates four sources of variation: (1) in-range liquidity repositioning — the true competition signal, (2) out-of-range position changes — irrelevant to fee competition since out-of-range positions earn zero fees, (3) price effects on USD denomination of positions, and (4) fee accrual back into TVL. The in-range liquidity field $L^{\text{active}}_t$ isolates component (1), which is the FLAIR-relevant variable that determines each LP's share of fee revenue at the active tick (Milionis, Wan, Adams 2023).
```

**Step 5: Update cell 4 (code — Stage 1 estimation)**

Change the `endog` variable:

```python
# ── Stage 1: Congestion Index ΔI_t ─────────────────────────────
# FLAIR insight: use in-range liquidity, not TVL
endog = div(delta(liquidity(pool_data)), lagged(liquidity(pool_data)))
```

Keep `exog` the same. Keep the rest of the cell identical.

**Step 6: Run the notebook to verify Stage 1 works**

Run:
```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research && source uhi8/bin/activate && jupyter nbconvert --to notebook --execute notebooks/econometrics.ipynb --output econometrics_executed.ipynb --ExecutePreprocessor.timeout=300 2>&1 | tail -10
```

Expected: Notebook executes. γ may differ from 0.78 (that was TVL-based). Record the new γ value.

**Step 7: Commit**

```bash
git add notebooks/econometrics.ipynb
git commit -m "feat(econometrics): use in-range liquidity for congestion index (FLAIR-informed)"
```

---

### Task 3: Verify R² improvement and update interpretation

**Files:**
- Modify: `notebooks/econometrics.ipynb` (cells 6, 10, 14, 15)
- Read-only: executed output from Task 2

**Step 1: Check key metrics from executed output**

From the executed notebook, extract and compare:

| Metric | TVL-based (old) | Liquidity-based (new) |
|--------|-----------------|----------------------|
| γ (persistence) | 0.7804 | ? |
| δ₂ | -0.002138 | ? |
| p-value | 0.000184 | ? |
| R² (Stage 2b) | 0.0516 | ? |

**STOP condition:** If R² is NOT meaningfully higher than 5.16%, or if δ₂ is not significant (p > 0.05), STOP and report. The FLAIR insight may not translate to daily aggregated data from the subgraph.

**Step 2: Update interpretation markdowns**

Update cell 6 (Stage 1 interpretation) — replace TVL references with in-range liquidity. Update the γ value and interpretation.

Update cell 10 (Stage 2 interpretation) — update δ₂, R², and significance values. Note the improvement over TVL-based model.

Update cell 14 (product design connection) — update R² reference and note that in-range liquidity captures the FLAIR competition dimension.

Update cell 15 (conclusions) — update quantitative parameters with new estimates.

**Step 3: Update economic significance cell**

The economic significance computation (cell 11) uses `congestion = state(ls)` which is already correct — it adapts to whatever `endog` was used. No code changes needed, but verify the printed values make sense with the new estimates.

**Step 4: Clean up and commit**

```bash
rm -f notebooks/econometrics_executed.ipynb
git add notebooks/econometrics.ipynb
git commit -m "docs(econometrics): update interpretation for liquidity-based congestion model"
```

---

### Task 4: Update backtest with new congestion variable

**Files:**
- Modify: `notebooks/backtest.ipynb` (cells 1, 2)
- Read-only: `notes/payoff_notes.md`, `data/Econometrics.py`

**Step 1: Update cell 1 (code — imports and Stage 1)**

Add `liquidity` to imports:

```python
from data.DataHandler import (
    PoolEntryData, delta, tvlUSD, priceUSD, feesUSD,
    div, lagged, txCount, normalize, liquidity
)
```

Change the `endog` variable to use in-range liquidity:

```python
# ── Stage 1: Extract congestion index ΔI_t ─────────────────────
# FLAIR: use in-range liquidity at active tick, not TVL
endog = div(delta(liquidity(pool_data)), lagged(liquidity(pool_data)))
```

**Step 2: Update cell 2 (code — hedge construction)**

Use the δ₂ value from the NEW econometric estimation. Replace the hardcoded `DELTA_2 = -0.002` with the updated value from Task 3.

Keep the rest of cell 2 as-is (s_t = delta_I, sigmoid payoff, structural or fixed hedge ratio).

**Step 3: Run the full notebook**

Run:
```bash
cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research && source uhi8/bin/activate && jupyter nbconvert --to notebook --execute notebooks/backtest.ipynb --output backtest_executed.ipynb --ExecutePreprocessor.timeout=300 2>&1 | tail -20
```

**Step 4: Check results**

**STOP condition:** If CVaR 1% improvement is negative (hedge makes tail risk WORSE), STOP immediately and report. Do not proceed to commit.

Expected improvements (if FLAIR variable works):
- Variance reduction > 5% (was -3.1% with TVL-based)
- CVaR 1% improvement POSITIVE (hedge reduces tail risk)
- High congestion regime shows meaningful variance reduction

**Step 5: Clean up and commit**

```bash
rm -f notebooks/backtest_executed.ipynb
git add notebooks/backtest.ipynb
git commit -m "feat(backtest): use FLAIR-based congestion variable for hedge"
```

---

### Task 5: Update payoff notes with FLAIR reference

**Files:**
- Modify: `notes/payoff_notes.md` (Section 1.1)

**Step 1: Update Section 1.1 — The Congestion State Variable**

Add a paragraph after the current definition explaining why `L_active` is used instead of TVL:

```markdown
The observed variable uses **in-range liquidity** $L^{\text{active}}_t$ — the liquidity deployed at the active tick — rather than total value locked (TVL). Following Milionis, Wan, and Adams (2023), LP competition for fee revenue operates on $L^{\text{active}}$: each LP's fee share is proportional to $L_i(\\tilde{p}_t; t) / L(\\tilde{p}_t; t)$, their fraction of active liquidity at the current price. TVL conflates active and out-of-range positions; the latter earn zero fees and are irrelevant to competition dynamics.
```

Update the equation to use $L^{\text{active}}$:

```markdown
$$\frac{\Delta L^{\text{active}}_t}{L^{\text{active}}_{t-1}} = X_t \beta + s_t + \varepsilon_t$$
```

**Step 2: Update Section 1.2 — Economic Significance**

Update δ₂ value and R² with the new estimates from Task 3.

**Step 3: Add FLAIR reference**

Add to the References section:

```markdown
- Milionis, J., Wan, C., Adams, A. (2023). "FLAIR: A Metric for Liquidity Provider Competitiveness in Automated Market Makers." arXiv:2306.09421.
```

**Step 4: Commit**

```bash
git add notes/payoff_notes.md
git commit -m "docs(payoff): reference FLAIR and in-range liquidity variable"
```
