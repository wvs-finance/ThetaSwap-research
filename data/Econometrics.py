from dataclasses import dataclass
from typing import Optional

import numpy as np
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


class LiquidityStateModel:
    def __call__(
        self,
        endog: TimeSeries,
        exog: TimeSeries,
        ar: Optional[int] = 1,
        window: Optional[int] = None
    ) -> LiquidityState:
        if window is None:
            return self._fit_full(endog, exog, ar)
        return self._fit_rolling(endog, exog, ar, window)

    @staticmethod
    def _standardize(series: TimeSeries):
        mu = series.mean()
        sigma = series.std()
        if sigma == 0:
            return series - mu, mu, sigma
        return (series - mu) / sigma, mu, sigma

    def _fit_full(
        self,
        endog: TimeSeries,
        exog: TimeSeries,
        ar: int
    ) -> LiquidityState:
        mask = np.isfinite(endog) & np.isfinite(exog)
        endog_clean = endog[mask]
        exog_clean = exog[mask]

        endog_z, endog_mu, endog_sigma = self._standardize(endog_clean)
        exog_z, _, _ = self._standardize(exog_clean)

        model = UnobservedComponents(
            endog_z,
            exog=exog_z,
            autoregressive=ar
        )
        results = model.fit(disp=False)

        param_names = list(results.params.index)
        beta_key = [k for k in param_names if "beta" in k.lower() or "x1" in k.lower()][0]
        rho_key = [k for k in param_names if "ar" in k.lower()][0]

        smoothed_z = pd.Series(results.smoothed_state[0], index=endog_clean.index)
        smoothed = smoothed_z * endog_sigma + endog_mu if endog_sigma > 0 else smoothed_z

        return LiquidityState(
            _beta=float(results.params[beta_key]),
            _rho=float(results.params[rho_key]),
            _state=smoothed,
            _result=results
        )

    def _fit_rolling(
        self,
        endog: TimeSeries,
        exog: TimeSeries,
        ar: int,
        window: int
    ) -> LiquidityState:
        mask = np.isfinite(endog) & np.isfinite(exog)
        endog_clean = endog[mask]
        exog_clean = exog[mask]

        n = len(endog_clean)
        betas = []
        rhos = []
        state_pieces = []

        for start in range(0, n - window + 1, window):
            end = start + window
            e_win = endog_clean.iloc[start:end]
            x_win = exog_clean.iloc[start:end]

            if len(e_win) < ar + 2:
                continue

            try:
                e_z, e_mu, e_sigma = self._standardize(e_win)
                x_z, _, _ = self._standardize(x_win)

                model = UnobservedComponents(
                    e_z,
                    exog=x_z,
                    autoregressive=ar
                )
                res = model.fit(disp=False)

                param_names = list(res.params.index)
                beta_key = [k for k in param_names if "beta" in k.lower() or "x1" in k.lower()][0]
                rho_key = [k for k in param_names if "ar" in k.lower()][0]

                betas.append(float(res.params[beta_key]))
                rhos.append(float(res.params[rho_key]))

                smoothed_z = pd.Series(res.smoothed_state[0], index=e_win.index)
                smoothed = smoothed_z * e_sigma + e_mu if e_sigma > 0 else smoothed_z
                state_pieces.append(smoothed)
            except Exception:
                continue

        if not betas:
            raise ValueError(f"No windows of size {window} could be estimated from {n} observations")

        return LiquidityState(
            _beta=float(np.median(betas)),
            _rho=float(np.median(rhos)),
            _state=pd.concat(state_pieces),
            _result={"betas": betas, "rhos": rhos, "n_windows": len(betas)}
        )
