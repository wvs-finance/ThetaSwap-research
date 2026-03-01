# Conclusions Section Design — Econometrics Notebook

**Date:** 2026-02-28
**Notebook:** `notebooks/econometrics.ipynb`
**Goal:** Add a conclusive Section 6 (2 cells) grounded strictly in the empirical results of the two-stage adverse competition test.

---

## Context

The existing notebook establishes:
- $\gamma = 0.78$ (AR(1) persistence of congestion index)
- $\delta_2 < 0$, $p < 0.001$, $R^2 = 5.2\%$ (adverse competition impact, orthogonal to LVR)
- Tail table: P50 ≈ 0 impact, P99 ≈ −45% of mean daily fee yield
- Annualised fee compression from a 1-std congestion shock (computed in cell 12)

The conclusions section must draw only from these fitted quantities — no new data, no theoretical claims beyond what the model supports.

---

## Design

### Cell 15 — Markdown: `## 6. Conclusions: Hedge Utility and Pricing Requirements`

**Subsection: When is the hedge useful?**

Three scenarios, each grounded in a specific empirical result:

1. **P95+ congestion day** (from tail table): single-day fee yield drops ~45% of mean. The congestionToken produces its largest single-period payoff here.

2. **Sustained crowding episode (3–7 days)** (from $\gamma = 0.78$, half-life ≈ 2.8 days): congestion shocks cluster. The expected cumulative payoff over a $T$-day episode starting at congestion $I_0$ is:
   $$E\left[\sum_{t=0}^{T-1} \delta_2 I_t \mid I_0\right] = \delta_2 \cdot I_0 \cdot \frac{1 - \gamma^T}{1 - \gamma}$$
   Multi-day protection is structurally larger than a single-period hedge by factor $\frac{1-\gamma^T}{1-\gamma}$.

3. **LVR-orthogonal tail protection** (from orthogonality construction): $\delta_2$ is by construction uncorrelated with $|\Delta P/P|$. Adding this hedge to a standard delta-hedge creates no redundant exposure — it targets the residual $\eta_t$ that LVR instruments leave unaddressed.

**Subsection: Minimum pricing requirements**

Four constraints derived strictly from the fitted model:

1. **Price AR(1) persistence**: i.i.d. pricing underestimates cumulative exposure by $\frac{1}{1-\gamma} = \frac{1}{1-0.78} \approx 4.5\times$. Any model without AR(1) dynamics systematically underprices.

2. **Floor premium at annualised $|\delta_2| \times$ congestion cost**: the annual fee compression computed in cell 12 is the minimum risk premium LPs require. Below it, the instrument offers negative expected value to hedgers.

3. **Enforce stationarity ($\gamma < 1$) in the pricing kernel**: the index mean-reverts. A random-walk assumption generates unbounded expected payoffs, requiring excess reserves that price out demand. Stationarity is what makes the instrument solvent.

4. **Reflect left-skew of impact distribution**: P50 ≈ 0, P99 ≈ −45% of mean yield. Symmetric (e.g. Gaussian) pricing underprices tail events. The pricing kernel must capture the asymmetric payoff distribution.

---

### Cell 16 — Code: Quantitative pricing parameters

**Computes:**
- Shock half-life: $-\ln(2) / \ln(\gamma)$ days
- Breakeven annual premium: $|\delta_2| \times \text{cong\_std} \times 365$ as % of fee yield and $/year per $1M TVL
- Expected cumulative 30-day fee compression starting from P75, P95, P99 (closed-form AR(1), no simulation)
- Bar chart (monochrome palette) showing the 3 scenarios

**Key formula:**
$$\text{cumulative}(T, I_0) = \delta_2 \cdot I_0 \cdot \frac{1 - \gamma^T}{1 - \gamma}$$

---

## Files Modified

- `notebooks/econometrics.ipynb` — append 2 cells (markdown + code)

## Acceptance Criteria

- Notebook executes top-to-bottom without error
- All numerical claims in the markdown are produced by the code cell
- No quantities claimed that are not directly from the fitted $\gamma$, $\delta_2$, tail table, or annualised impact
