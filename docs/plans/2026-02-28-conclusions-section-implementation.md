# Conclusions Section — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Append a two-cell Section 6 to `notebooks/econometrics.ipynb` covering hedge utility scenarios and minimum pricing requirements, grounded strictly in the fitted $\gamma$, $\delta_2$, tail table, and annualised impact already computed in the notebook.

**Architecture:** Two `NotebookEdit insert` calls on the last cell of the existing 15-cell notebook. Cell 15 is markdown (narrative). Cell 16 is code (quantitative parameters + bar chart). All variables (`rho(ls)`, `delta_coeff(ac)`, `congestion`, `pool_data`, `go`) are already defined in earlier cells — no new imports needed.

**Tech Stack:** Python 3, Jupyter (ipynb), Plotly, numpy

**Design doc:** `docs/plans/2026-02-28-conclusions-section-design.md`

---

## Background

### Last cell in notebook
After the Task 4 implementation, the notebook has 15 cells (0–14). Cell 14 (`tynki01xxnr`) is the "Connection to Product Design" markdown. New cells insert after it.

### Key variables already in scope (from earlier cells)
- `rho(ls)` → $\gamma = 0.78$
- `delta_coeff(ac)` → $\delta_2$
- `congestion` → `state(ls)` time series
- `pool_data` → full pool DataFrame
- `fy_mean` → defined in cell 12 (economic significance code)
- `d2` → defined in cell 12
- `go`, `np`, `pd` → imported in cell 2

### Verification command
```bash
source uhi8/bin/activate && jupyter nbconvert --to notebook --execute notebooks/econometrics.ipynb --output /tmp/econ_check.ipynb --ExecutePreprocessor.timeout=300 2>&1 | tail -3
```
Expected: `[NbConvertApp] Writing ... /tmp/econ_check.ipynb`

---

## Task 1: Add Cell 15 — Conclusions markdown

**Files:**
- Modify: `notebooks/econometrics.ipynb` (insert after cell `tynki01xxnr`)

**Step 1: Insert the markdown cell**

Use `NotebookEdit` with `cell_id=tynki01xxnr`, `edit_mode=insert`, `cell_type=markdown`:

```markdown
## 6. Conclusions: Hedge Utility and Pricing Requirements

### When is the hedge useful?

The empirical results identify three scenarios where the congestionToken delivers meaningful protection:

**Scenario 1 — Tail congestion day (P95+).** The tail impact table shows fee yield drops of ~45% of the daily mean at P99 congestion. These are the events where the congestionToken produces its largest single-period payoff. At P75 and below the impact is small — the hedge costs relatively little in normal conditions and pays out sharply in the tail.

**Scenario 2 — Sustained crowding episode (3–7 days).** $\gamma = 0.78$ implies a shock half-life of ~2.8 days: a congestion event persists before mean-reverting. The expected cumulative fee compression over a $T$-day episode starting at congestion $I_0$ is:

$$E\left[\sum_{t=0}^{T-1} \delta_2 I_t \,\Big|\, I_0\right] = \delta_2 \cdot I_0 \cdot \frac{1 - \gamma^T}{1 - \gamma}$$

For $T = 30$ days this multiplier is $\frac{1 - 0.78^{30}}{1 - 0.78} \approx 4.5\times$ the single-day impact — the hedge is structurally more valuable over episodes than over single events.

**Scenario 3 — As a complement to an LVR hedge.** By construction, $\delta_2$ is orthogonal to $|\Delta P/P|$. An LP running a delta-hedge or options strategy to manage LVR can add the congestionToken with no redundant exposure. It targets the $5.2\%$ of fee yield variance that LVR instruments structurally cannot reach.

### Minimum pricing requirements

The fitted model imposes four constraints on any instrument designed to transfer this risk:

**1. Price the AR(1) persistence ($\gamma = 0.78$).** An i.i.d. model underestimates cumulative exposure by $\frac{1}{1-\gamma} \approx 4.5\times$. The correct pricing kernel must embed AR(1) dynamics — an Ornstein-Uhlenbeck process admits closed-form solutions directly parameterised by $\gamma$ and the innovation variance $\sigma_v^2 = \sigma_{\Delta I}^2 (1 - \gamma^2)$.

**2. Floor the risk premium at the annualised fee compression cost.** The annual fee compression from a 1-std congestion shock is the minimum premium LPs require for hedging to be rational. Below this floor the instrument offers negative expected value to buyers.

**3. Enforce stationarity ($\gamma < 1$) in the pricing kernel.** The index mean-reverts. A random-walk assumption produces unbounded expected payoffs and requires reserves that price out demand. Stationarity is the structural property that keeps the instrument solvent and the premium finite.

**4. Reflect the left-skew of the impact distribution.** P50 impact $\approx 0$; P99 $\approx -45\%$ of mean daily yield. Symmetric (e.g. Gaussian) pricing underprices tail events. The pricing distribution must assign excess mass to large negative realisations of $\delta_2 \cdot \Delta I_t$.
```

**Step 2: Read the notebook to confirm the new cell ID**

```bash
python3 -c "
import json
with open('notebooks/econometrics.ipynb') as f:
    nb = json.load(f)
for i, c in enumerate(nb['cells']):
    src = c['source']
    text = (src[0] if isinstance(src, list) and src else src)[:60]
    print(i, c.get('id','?'), repr(text))
"
```
Expected: 16 cells, last cell id is the newly inserted markdown.

---

## Task 2: Add Cell 16 — Quantitative pricing parameters code + bar chart

**Files:**
- Modify: `notebooks/econometrics.ipynb` (insert after cell from Task 1)

**Step 1: Insert the code cell** (use cell id returned from Task 1 Step 2)

Use `NotebookEdit` with `cell_id=<new-cell-id>`, `edit_mode=insert`, `cell_type=code`:

```python
# ── Conclusions: Quantitative pricing parameters ────────────────
gamma_est = rho(ls)
d2_val = delta_coeff(ac)
cong_std_val = congestion.std()
fy_mean_val = div(feesUSD(pool_data), tvlUSD(pool_data)).mean()

# ── 1. Shock half-life ──────────────────────────────────────────
half_life = -np.log(2) / np.log(gamma_est)

# ── 2. Breakeven annual premium ─────────────────────────────────
shock_1std = d2_val * cong_std_val
annual_premium_pp  = abs(shock_1std) * 365 * 100
annual_premium_usd = abs(shock_1std) * 365 * 1_000_000

# ── 3. Expected cumulative 30-day impact (closed-form AR(1)) ────
T = 30
multiplier = (1 - gamma_est**T) / (1 - gamma_est)

percentiles_dict = {
    "P75": congestion.quantile(0.75),
    "P95": congestion.quantile(0.95),
    "P99": congestion.quantile(0.99),
}

print("Quantitative Pricing Parameters")
print("=" * 50)
print(f"AR(1) shock half-life:       {half_life:.1f} days")
print(f"  → a P95+ event persists ~{half_life:.0f} days before mean-reverting")
print()
print(f"Breakeven annual premium (1-std congestion shock):")
print(f"  Fee compression / year:    {annual_premium_pp:.2f} pp of fee yield")
print(f"  Per $1M TVL:               ${annual_premium_usd:,.0f} / year")
print(f"  → Instrument premium must exceed this for LP hedging to be rational")
print()
print(f"AR(1) multiplier over {T} days: {multiplier:.2f}×  (vs single-day impact)")
print()
print(f"Expected {T}-day cumulative fee compression by starting congestion percentile:")
print(f"{'Scenario':>10}  {'ΔI₀':>8}  {'Cumulative impact':>20}")
print("-" * 44)
for label, I0 in percentiles_dict.items():
    impact = d2_val * I0 * multiplier
    pct = 100 * impact / fy_mean_val
    print(f"{label:>10}  {I0:>8.4f}  {pct:>19.1f}% of mean daily yield")

# ── Bar chart ────────────────────────────────────────────────────
labels_p  = list(percentiles_dict.keys())
impacts_p = [
    100 * d2_val * I0 * multiplier / fy_mean_val
    for I0 in percentiles_dict.values()
]

fig = go.Figure()
fig.add_trace(go.Bar(
    x=labels_p, y=impacts_p,
    marker=dict(
        color=["#999999", "#444444", "#1a1a1a"],
        line=dict(color="#1a1a1a", width=1)
    ),
    text=[f"{v:.1f}%" for v in impacts_p],
    textposition="outside",
    textfont=dict(family="Courier New, monospace", size=11)
))
fig.add_hline(y=0, line_color="#999999", line_width=0.8)
fig.update_layout(
    title=f"Expected {T}-day Cumulative Fee Compression  (AR(1), γ={gamma_est:.2f})",
    xaxis_title="Starting Congestion Percentile",
    yaxis_title=f"Cumulative {T}-day Impact (% of mean daily fee yield)",
    height=420,
    margin=dict(t=60, b=40),
    yaxis=dict(range=[min(impacts_p) * 1.3, 5])
)
fig.show()
```

**Step 2: Verify notebook runs clean**

```bash
source uhi8/bin/activate && jupyter nbconvert --to notebook --execute notebooks/econometrics.ipynb --output /tmp/econ_check.ipynb --ExecutePreprocessor.timeout=300 2>&1 | tail -3
```
Expected: `[NbConvertApp] Writing ... /tmp/econ_check.ipynb`

**Step 3: Confirm 17 cells on disk**

```bash
python3 -c "
import json
with open('notebooks/econometrics.ipynb') as f:
    nb = json.load(f)
print(f'Total cells: {len(nb[\"cells\"])}')
"
```
Expected: `Total cells: 17`

**Step 4: Commit and push**

```bash
git add notebooks/econometrics.ipynb
git commit -m "notebook: add Section 6 — conclusions on hedge utility and pricing requirements"
git push
```
