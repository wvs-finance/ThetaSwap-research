from dataclasses import dataclass
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.structural import UnobservedComponents

TimeSeries = pd.Series
Exogenous = Union[pd.Series, pd.DataFrame]


@dataclass(frozen=True)
class LiquidityState:
    _beta: Dict[str, float]
    _rho: float
    _state: TimeSeries
    _result: object


def beta(ls: LiquidityState) -> Dict[str, float]:
    return ls._beta


def rho(ls: LiquidityState) -> float:
    return ls._rho


def state(ls: LiquidityState) -> TimeSeries:
    return ls._state


def result(ls: LiquidityState) -> object:
    return ls._result


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


class LiquidityStateModel:
    def __call__(
        self,
        endog: TimeSeries,
        exog: Exogenous,
        ar: Optional[int] = 1,
        window: Optional[int] = None
    ) -> LiquidityState:
        if window is None:
            return self._fit_full(endog, exog, ar)
        return self._fit_rolling(endog, exog, ar, window)

    @staticmethod
    def _standardize_series(series: TimeSeries):
        mu = series.mean()
        sigma = series.std()
        if sigma == 0:
            return series - mu, mu, sigma
        return (series - mu) / sigma, mu, sigma

    @staticmethod
    def _standardize_exog(exog: Exogenous):
        if isinstance(exog, pd.DataFrame):
            return (exog - exog.mean()) / exog.std()
        return (exog - exog.mean()) / exog.std()

    @staticmethod
    def _finite_mask(endog: TimeSeries, exog: Exogenous) -> pd.Series:
        endog_ok = np.isfinite(endog)
        if isinstance(exog, pd.DataFrame):
            exog_ok = exog.apply(np.isfinite).all(axis=1)
        else:
            exog_ok = np.isfinite(exog)
        return endog_ok & exog_ok

    @staticmethod
    def _extract_betas(res) -> Dict[str, float]:
        param_names = list(res.params.index)
        beta_keys = [k for k in param_names if "beta" in k.lower() or "x1" in k.lower()]
        return {k: float(res.params[k]) for k in beta_keys}

    @staticmethod
    def _extract_rho(res) -> float:
        param_names = list(res.params.index)
        rho_key = [k for k in param_names if "ar" in k.lower()][0]
        return float(res.params[rho_key])

    def _fit_full(
        self,
        endog: TimeSeries,
        exog: Exogenous,
        ar: int
    ) -> LiquidityState:
        mask = self._finite_mask(endog, exog)
        endog_clean = endog[mask]
        exog_clean = exog[mask]

        endog_z, endog_mu, endog_sigma = self._standardize_series(endog_clean)
        exog_z = self._standardize_exog(exog_clean)

        model = UnobservedComponents(
            endog_z,
            exog=exog_z,
            autoregressive=ar
        )
        results = model.fit(disp=False)

        smoothed_z = pd.Series(results.smoothed_state[0], index=endog_clean.index)
        smoothed = smoothed_z * endog_sigma + endog_mu if endog_sigma > 0 else smoothed_z

        return LiquidityState(
            _beta=self._extract_betas(results),
            _rho=self._extract_rho(results),
            _state=smoothed,
            _result=results
        )

    def _fit_rolling(
        self,
        endog: TimeSeries,
        exog: Exogenous,
        ar: int,
        window: int
    ) -> LiquidityState:
        mask = self._finite_mask(endog, exog)
        endog_clean = endog[mask]
        exog_clean = exog[mask]

        n = len(endog_clean)
        all_betas = []
        rhos = []
        state_pieces = []

        for start in range(0, n - window + 1, window):
            end = start + window
            e_win = endog_clean.iloc[start:end]
            x_win = exog_clean.iloc[start:end]

            if len(e_win) < ar + 2:
                continue

            try:
                e_z, e_mu, e_sigma = self._standardize_series(e_win)
                x_z = self._standardize_exog(x_win)

                model = UnobservedComponents(
                    e_z,
                    exog=x_z,
                    autoregressive=ar
                )
                res = model.fit(disp=False)

                all_betas.append(self._extract_betas(res))
                rhos.append(self._extract_rho(res))

                smoothed_z = pd.Series(res.smoothed_state[0], index=e_win.index)
                smoothed = smoothed_z * e_sigma + e_mu if e_sigma > 0 else smoothed_z
                state_pieces.append(smoothed)
            except Exception:
                continue

        if not rhos:
            raise ValueError(f"No windows of size {window} could be estimated from {n} observations")

        beta_keys = all_betas[0].keys()
        median_betas = {k: float(np.median([b[k] for b in all_betas])) for k in beta_keys}

        return LiquidityState(
            _beta=median_betas,
            _rho=float(np.median(rhos)),
            _state=pd.concat(state_pieces),
            _result={"betas": all_betas, "rhos": rhos, "n_windows": len(rhos)}
        )
