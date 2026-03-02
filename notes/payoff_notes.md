# CongestionToken: Payoff Design and CFMM Replication

## 1. Claim Design

### 1.1 The Congestion State Variable

The econometric model (Stage 1) decomposes daily liquidity changes into an explained component and a latent congestion state. The observed variable is the relative liquidity change:

$$\frac{\Delta L_t}{L_{t-1}} = X_t \beta + s_t + \varepsilon_t$$

where $X_t$ includes price returns $\Delta P_t / P_{t-1}$ and normalized transaction activity, and $s_t$ is the latent AR(1) congestion state:

$$s_t = \gamma \, s_{t-1} + \eta_t, \qquad \gamma = 0.78$$

The smoothed state $s_t$ captures liquidity repositioning orthogonal to observable market conditions. It is the structural residual — the component of liquidity dynamics unexplained by price movement and trading volume. Persistence ($\gamma = 0.78$) means congestion builds over multiple days but is stationary and mean-reverting.

### 1.2 Economic Significance

Stage 2 of the econometric model establishes that congestion causally compresses fee yields. After residualizing fee yields on LVR (loss-versus-rebalancing), the orthogonal fee component $\eta_t$ satisfies:

$$\eta_t = \alpha + \delta_2 \, s_t + u_t, \qquad \delta_2 = -0.002, \quad p = 0.0002$$

Each unit increase in $s_t$ reduces fee yield by 0.2 basis points. For a $1M position, this is $-\$2{,}000$ per unit of congestion per day. The effect is statistically significant with robust (HC1) standard errors and orthogonal to adverse selection (LVR).

### 1.3 Token Structure

The congestionToken is a fungible claim (ERC-6909 or ERC-1155) that provides delta exposure to the congestion state $s_t$.

**Positions:**
- **LP token = collateral (SHORT).** The LP's fee revenue decreases when congestion rises. By depositing LP tokens as collateral, the LP is naturally short congestion risk.
- **CongestionToken = LONG.** The token pays off when congestion rises, hedging the LP's short exposure.

**Update rule.** The state $s_t$ updates at each state-changing event: `addLiquidity`, `removeLiquidity`, tick crossing, or large swap. The congestionToken is event-driven — its value changes only when pool state changes.

---

## 2. Claim Pricing

### 2.1 Desirable Properties

The marginal price $p(s)$ of the congestionToken must satisfy three properties for it to function as a tail risk hedge with bounded liability:

1. **Increasing in $s$.** Higher congestion → higher price. LPs pay more for protection when they need it most.
2. **Convex in $s$.** Large congestion shocks produce disproportionately higher prices. This is the tail risk hedge property: the payoff accelerates precisely when fee compression is most severe.
3. **Bounded.** $p(s) \in (0, 1)$. The marginal price cannot exceed 1 unit of collateral per unit of congestion exposure, ensuring solvency of the protocol.

### 2.2 Sigmoid Pricing Function

The sigmoid satisfies all three properties:

$$p(s) = \sigma\!\left(\frac{s}{\lambda}\right) = \frac{1}{1 + e^{-s/\lambda}}$$

The scale parameter $\lambda$ controls where the sigmoid transitions from its flat region (low price, low congestion) to its steep region (rapidly increasing price, high congestion). Calibration:

$$\lambda = Q_{75}\!\left(|s_t|\right)$$

Setting $\lambda$ at the 75th percentile of the absolute congestion state ensures the sigmoid activates — enters its convex region — at tail events. Below $\lambda$, the price is nearly linear and cheap. Above $\lambda$, convexity kicks in: the buyer pays rapidly increasing prices for protection against extreme congestion.

### 2.3 Tail Risk Hedge Interpretation

At low congestion ($|s| \ll \lambda$): $p(s) \approx \frac{1}{2} + \frac{s}{4\lambda}$. The price moves approximately linearly — small, predictable cost. This is the "insurance premium" regime.

At high congestion ($s \gg \lambda$): $p(s) \to 1$. The price saturates — the hedge provides maximum protection per unit of exposure. The convex transition between these regimes is where the tail risk hedge operates.

The sigmoid price guarantees:
- Cheap protection during normal conditions (most days)
- Expensive but available protection during stress (when LPs need it)
- Bounded total cost (never exceeds 1 per unit)

---

## 3. Payoff Functional

### 3.1 Integration of Price

The accumulated payoff $\varphi(s)$ — the total value of holding 1 congestionToken as $s$ changes from 0 to its current level — is the integral of the marginal price:

$$\varphi(s) = \int_0^s p(u) \, du = \lambda \cdot \ln\!\left(1 + e^{s/\lambda}\right) - \lambda \ln 2$$

This is the **softplus function** (shifted so $\varphi(0) = 0$). In practice, the constant shift $-\lambda \ln 2$ can be absorbed into the CFMM invariant, so we write:

$$\varphi(s) = \lambda \cdot \ln\!\left(1 + e^{s/\lambda}\right)$$

### 3.2 CFMM Replicability (Angeris et al., 2021)

Angeris, Evans, and Chitra prove that any payoff replicable by a CFMM without oracles must satisfy three conditions. The softplus $\varphi$ satisfies all of them:

**Condition 1 — Monotone nondecreasing:**
$$\varphi'(s) = \sigma(s/\lambda) > 0 \quad \forall s \qquad \checkmark$$

The derivative is the sigmoid, which is strictly positive everywhere.

**Condition 2 — Nonnegative:**
$$\varphi(s) = \lambda \ln(1 + e^{s/\lambda}) > 0 \quad \forall s \qquad \checkmark$$

The logarithm of a quantity greater than 1 is positive.

**Condition 3 — Sublinear growth:**
$$\lim_{s \to \infty} \frac{\varphi(s)}{s} = 1, \qquad \lim_{s \to -\infty} \frac{\varphi(s)}{|s|} = 0 \qquad \checkmark$$

The payoff grows at most linearly, and the growth rate is bounded by 1.

By Theorem 1 of Angeris et al., there exists a convex CFMM trading function whose LP shares replicate $\varphi$ — no external oracle is required to maintain the payoff.

### 3.3 Payoff Behavior

| Regime | $s$ range | $\varphi(s)$ | Interpretation |
|--------|-----------|-------------|----------------|
| Low congestion | $s \ll -\lambda$ | $\approx 0$ | No payoff — hedge dormant |
| Transition | $|s| \leq \lambda$ | Convex growth | Hedge activating |
| High congestion | $s \gg \lambda$ | $\approx s$ | Near-linear payoff — full protection |

The convex transition is the operating region of the tail risk hedge.

---

## 4. Solvency and Margin

### 4.1 Natural Bounds from Mean Reversion

Because $s_t$ is AR(1) with $\gamma = 0.78 < 1$, the unconditional distribution of $s_t$ is bounded in probability. The unconditional variance is:

$$\text{Var}(s_t) = \frac{\sigma_\eta^2}{1 - \gamma^2} \approx (0.043)^2 = 0.00185$$

The 99th percentile of $|s_t|$ provides a structural bound on maximum congestion.

### 4.2 Margin Requirement

An LP depositing collateral to SHORT the congestionToken must post margin sufficient to cover the maximum payoff:

$$M \geq N \cdot \varphi(s_{\max})$$

where $s_{\max} = \sup_{t \in [t-W, t]} |s_t|$ is the rolling maximum congestion over window $W$, and $N$ is the hedge ratio (number of tokens).

### 4.3 Collateral and Liquidation

- The LP deposits LP tokens as collateral. LP token value and congestion move inversely: when congestion rises, LP fee yield falls, reducing LP token value — but the congestionToken payoff rises. The LP token is natural collateral because its value decline is the risk being hedged.

- **Liquidation condition:** If LP token value falls below the accrued congestion payoff:

$$\text{LP token value} < N \cdot \varphi(s_t) \implies \text{auto-liquidate}$$

### 4.4 Exposure Accumulation

The sigmoid bounds the *marginal* price at 1, but the *total* payoff $\varphi(s)$ grows linearly for large $s$. However, mean reversion of $s_t$ prevents unbounded drift. The key invariant:

$$|\varphi(s_t)| \leq \lambda \cdot \ln(1 + e^{s_{\max}/\lambda})$$

which is finite and computable on-chain from the rolling maximum.

---

## 5. CFMM Invariant

### 5.1 Trading Function

From the payoff $\varphi(s) = \lambda \ln(1 + e^{s/\lambda})$, the CFMM trading function is:

$$\psi(x, y) = y - \lambda \ln\!\left(1 + e^{x/\lambda}\right) = k$$

where:
- $x$ = congestionToken reserves (units of congestion exposure)
- $y$ = collateral reserves (units of value)
- $k$ = invariant constant set at pool initialization

### 5.2 Price from Reserves

The marginal price of congestionTokens in terms of collateral:

$$p(x) = -\frac{\partial \psi / \partial x}{\partial \psi / \partial y} = \frac{\lambda^{-1} e^{x/\lambda}}{1 + e^{x/\lambda}} = \sigma(x/\lambda)$$

This recovers the sigmoid pricing function from Section 2. A trade that changes reserves by $(\Delta x, \Delta y)$ must satisfy:

$$\psi(x + \Delta x, \, y + \Delta y) = k$$

### 5.3 Reserve Domains

- $x \in \mathbb{R}$ — congestionToken reserves can be positive or negative (protocol can be net long or short)
- $y > k$ — collateral reserves must exceed the invariant (solvency)
- As $x \to +\infty$: $y \to x + k$ (linear regime, full congestion pricing)
- As $x \to -\infty$: $y \to k$ (flat regime, minimal congestion pricing)

### 5.4 Initialization

At pool creation with reserves $(x_0, y_0)$:

$$k = y_0 - \lambda \ln(1 + e^{x_0/\lambda})$$

The parameter $\lambda$ is set from the econometric calibration: $\lambda = Q_{75}(|s_t|)$ over the estimation window.

---

## 6. Hedge Ratio

### 6.1 Structural Derivation

The hedge ratio is derived from the economic relationship, not from statistical estimation. From Stage 2:

$$\Delta \text{PnL}_{\text{fees}} = \delta_2 \cdot \Delta s_t \cdot \text{Notional} + \text{other terms}$$

The congestionToken payoff change:

$$\Delta \varphi_t = \varphi(s_t) - \varphi(s_{t-1}) \approx \sigma(s_t / \lambda) \cdot \Delta s_t$$

For the hedge to neutralize the congestion channel:

$$N \cdot \Delta \varphi_t + \delta_2 \cdot \Delta s_t \cdot \text{Notional} = 0$$

Solving:

$$\boxed{N_t = \frac{|\delta_2| \cdot \text{Notional}}{\sigma(s_t / \lambda)}}$$

### 6.2 Properties

With $\delta_2 = -0.002$ and Notional $= \$1{,}000{,}000$:

- At $s = 0$: $\sigma = 0.5$, so $N = 4{,}000$
- At $s = \lambda$ (75th percentile): $\sigma \approx 0.73$, so $N \approx 2{,}740$
- At $s = 2\lambda$ (extreme): $\sigma \approx 0.88$, so $N \approx 2{,}273$

The hedge ratio is:
- **Bounded**: $N \in (|\delta_2| \cdot \text{Notional}, \, 2|\delta_2| \cdot \text{Notional})$ since $\sigma \in (0.5, 1)$ for $s \geq 0$
- **Smooth**: sigmoid denominator is infinitely differentiable
- **Adaptive**: automatically reduces position size when congestion is high (sigmoid closer to 1) — buys less protection when it is most expensive
- **Structural**: derived from the econometrically estimated $\delta_2$, not from noisy rolling covariances

### 6.3 Hedged P&L

The daily hedged fee P&L:

$$\Delta \text{PnL}_{\text{hedged}} = \Delta \text{PnL}_{\text{fees}} + N_t \cdot \Delta \varphi_t$$

This construction ensures that the congestion-attributable component of fee P&L is neutralized, while other sources of fee variation (market conditions, volume, LVR) pass through unhedged. The hedge targets the $\delta_2$ channel specifically — it is not a blanket volatility reduction tool.

---

## References

- Angeris, G., Evans, A., Chitra, T. (2021). "Replicating Monotonic Payoffs Without Oracles." arXiv:2111.13740.
- Stage 1: `LiquidityStateModel` — UnobservedComponents AR(1), `data/Econometrics.py`
- Stage 2: `AdverseCompetitionModel` — OLS with HC1 robust SEs, orthogonal to LVR, `data/Econometrics.py`
- Empirical results: `notebooks/econometrics.ipynb` — γ = 0.78, δ₂ = -0.002, p = 0.0002, R² = 5.2%, 1,731 obs
