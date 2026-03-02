# Backtest Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix `notebooks/backtest.ipynb` so the congestionToken hedge shows significant tail risk improvement by using the corrected congestion state (no cumsum) and structural hedge ratio (from δ₂).

**Architecture:** Modify cells 1-2 of existing notebook. The fix is in the hedge construction (cell 2): use `s_t = state(ls)` directly instead of `cumsum(state(ls))`, calibrate λ from tail quantile, and replace statistical hedge ratio with structural one.

**Tech Stack:** Same as existing — pandas, numpy, plotly, statsmodels, existing data infrastructure.

---

### Task 1: Fix cell 2 — congestion state and hedge ratio

**Files:**
- Modify: `notebooks/backtest.ipynb` (cell 2)
- Read-only: `notes/payoff_notes.md` (Section 6 hedge ratio), `data/Econometrics.py`

**Step 1: Replace cell 2 with corrected hedge construction**

```python
# ── LP Position: passive full-range, $1M notional ──────────────
NOTIONAL = 1_000_000  # $1M
fee_yield = div(feesUSD(pool_data), tvlUSD(pool_data))  # daily fee yield
pnl_fees = fee_yield * NOTIONAL                          # daily fee P&L ($)

# ── Congestion state: use AR(1) state directly (NOT cumsum) ────
s_t = delta_I  # s_t IS the congestion level — mean-reverting, stationary

# ── Sigmoid payoff: φ(s) = λ·ln(1 + e^{s/λ}) ──────────────────
lam = s_t.abs().quantile(0.75)  # sigmoid activates at tail events
phi = lam * np.log(1 + np.exp(s_t / lam))
delta_phi = phi.diff().fillna(0)

# ── Structural hedge ratio from δ₂ ───────────────────────────
DELTA_2 = -0.002  # from AdverseCompetitionModel (p = 0.0002)
sigma_s = 1 / (1 + np.exp(-s_t / lam))  # sigmoid of congestion state
N_t = (abs(DELTA_2) * NOTIONAL / sigma_s)

# Align series on common index
common = pnl_fees.index.intersection(delta_phi.index).intersection(N_t.index)
pnl_aligned = pnl_fees.loc[common]
dphi_aligned = delta_phi.loc[common]
N_aligned = N_t.loc[common]

# ── Hedged P&L ─────────────────────────────────────────────────
pnl_hedge = N_aligned * dphi_aligned
pnl_hedged = pnl_aligned + pnl_hedge

# Drop first observation (NaN from diff)
valid = pnl_hedged.dropna().index
pnl_aligned = pnl_aligned.loc[valid]
pnl_hedged = pnl_hedged.loc[valid]
pnl_hedge = pnl_hedge.loc[valid]
N_aligned = N_aligned.loc[valid]

print(f"Notional: ${NOTIONAL:,.0f}")
print(f"λ (sigmoid scale): {lam:.4f}")
print(f"δ₂ = {DELTA_2} (fee yield sensitivity to congestion)")
print(f"Backtested days: {len(valid)}")
print(f"Hedge ratio N range: [{N_aligned.min():.0f}, {N_aligned.max():.0f}]")
print(f"Median hedge ratio N: {N_aligned.median():.0f}")
```

**Step 2: Update cell 3 markdown to reflect structural hedge**

Update the hedge mechanics markdown to explain the structural hedge ratio.

**Step 3: Update cell 6 — fix delta_I reference**

The regime analysis cell uses `delta_I_aligned = delta_I.loc[valid]`. Since we renamed the variable semantics, ensure `delta_I` (which is `state(ls)`) is used consistently for regime splits.

**Step 4: Run notebook end-to-end**

Run: `cd /home/jmsbpp/apps/ThetaSwap/ThetaSwap-research && source uhi8/bin/activate && jupyter nbconvert --to notebook --execute notebooks/backtest.ipynb --output backtest_executed.ipynb 2>&1 | tail -20`

Expected: Variance reduction significantly higher. CVaR improvement positive (not -670%).

**Step 5: Commit**

```bash
git add notebooks/backtest.ipynb notes/payoff_notes.md docs/plans/2026-02-28-payoff-redesign.md docs/plans/2026-02-28-backtest-fix.md
git commit -m "fix(backtest): use AR(1) state directly + structural hedge ratio from δ₂"
```

---

### Task 2: Verify stress analysis shows significant improvement

**Files:**
- Read-only: `notebooks/backtest.ipynb` (executed output)

**Step 1: Check results**

Verify from the executed notebook output:
- Conditional variance reduction in high-congestion regime > 10%
- CVaR 1% improvement is POSITIVE (hedge reduces tail risk, not amplifies)
- Worst episodes show meaningful P&L savings

**Step 2: If results still unsatisfactory, adjust λ calibration**

If variance reduction is still low, try λ = P90(|s_t|) or λ = P50(|s_t|) and re-run.

**Step 3: Clean up**

```bash
rm -f notebooks/backtest_executed.ipynb
```
