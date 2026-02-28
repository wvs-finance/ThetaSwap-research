#!/usr/bin/env python3
"""
Tests for Econometrics module — Structural state-space model

    ΔL_t/L_{t-1} = β₁(ΔP_t/P_{t-1}) + β₂(txActivity_t) + e_t
    e_t = γe_{t-1} + v_t

    e_t = ΔI_t  (congestion index — microstructure risk premium)

Usage:
    source uhi8/bin/activate
    python -m pytest tests/test_Econometrics.py -v

All tests use REAL subgraph data (no mocks).
"""

import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.Econometrics import LiquidityState, LiquidityStateModel, beta, rho, state, result
from data.DataHandler import (
    PoolEntryData, delta, tvlUSD, priceUSD, div, lagged, txCount, normalize
)
from data.UniswapClient import UniswapClient, v3


# ── V3 USDC/WETH pool — 1760 days, 11M txns ──────────────────
V3_USDC_WETH = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"


def _market_state(pool_data: pd.DataFrame) -> pd.DataFrame:
    """E[ΔL_t | ΔP_t, ticksCrossing] — market state from payoff notes."""
    return pd.DataFrame({
        "delta_price": div(delta(priceUSD(pool_data)), lagged(priceUSD(pool_data))),
        "tx_activity": normalize(txCount(pool_data), window=30),
    })


class TestLiquidityStateAccessors(unittest.TestCase):
    """Test LiquidityState dataclass and free function accessors"""

    def setUp(self):
        self.ls = LiquidityState(
            _beta={"beta.x1": -0.5},
            _rho=0.7,
            _state=pd.Series([1.0, 2.0, 3.0]),
            _result="mock_result"
        )

    def test_beta_returns_dict(self):
        self.assertIsInstance(beta(self.ls), dict)

    def test_beta_returns_value(self):
        self.assertEqual(beta(self.ls)["beta.x1"], -0.5)

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


class TestLiquidityStateModelStructure(unittest.TestCase):
    """Test LiquidityStateModel returns correct types and shapes with real V3 data"""

    @classmethod
    def setUpClass(cls):
        client = UniswapClient(v3())
        pool = PoolEntryData(V3_USDC_WETH, client=client)
        cls.pool_data = pool(pool.lifetimeLen())
        cls.endog = div(delta(tvlUSD(cls.pool_data)), lagged(tvlUSD(cls.pool_data)))
        cls.exog = _market_state(cls.pool_data)
        mask = np.isfinite(cls.endog) & cls.exog.apply(np.isfinite).all(axis=1)
        cls.clean_len = int(mask.sum())
        cls.ls = LiquidityStateModel()(endog=cls.endog, exog=cls.exog)

    def test_call_returns_liquidity_state(self):
        self.assertIsInstance(self.ls, LiquidityState)

    def test_beta_is_dict(self):
        self.assertIsInstance(beta(self.ls), dict)

    def test_beta_has_market_state_keys(self):
        keys = beta(self.ls)
        self.assertTrue(any("delta_price" in k for k in keys))
        self.assertTrue(any("tx_activity" in k for k in keys))

    def test_rho_is_float(self):
        self.assertIsInstance(rho(self.ls), float)

    def test_state_is_series(self):
        self.assertIsInstance(state(self.ls), pd.Series)

    def test_state_length_matches_clean_endog(self):
        self.assertEqual(len(state(self.ls)), self.clean_len)

    def test_ar2_returns_valid_state(self):
        ls2 = LiquidityStateModel()(endog=self.endog, exog=self.exog, ar=2)
        self.assertIsInstance(ls2, LiquidityState)
        self.assertIsInstance(beta(ls2), dict)
        self.assertIsInstance(rho(ls2), float)


class TestCongestionIndex(unittest.TestCase):
    """Test economic hypotheses — congestion index ΔI_t from payoff notes.

    ΔI_t = ΔL_t - E[ΔL_t | market state]
         = structural residual e_t

    Hypothesis:
    - 0 < γ < 1: ΔI_t is persistent (captures microstructure risk premium)
                  but stationary (sigmoid pricing stays bounded)
    """

    @classmethod
    def setUpClass(cls):
        client = UniswapClient(v3())
        pool = PoolEntryData(V3_USDC_WETH, client=client)
        cls.pool_data = pool(pool.lifetimeLen())
        cls.endog = div(delta(tvlUSD(cls.pool_data)), lagged(tvlUSD(cls.pool_data)))
        cls.exog = _market_state(cls.pool_data)
        cls.ls = LiquidityStateModel()(endog=cls.endog, exog=cls.exog)

    def test_rho_persistent(self):
        """γ > 0: congestion carries over — large LP repositioning creates lasting effects"""
        self.assertGreater(rho(self.ls), 0,
            f"Expected γ > 0 (persistent congestion), got γ = {rho(self.ls)}")

    def test_rho_stationary(self):
        """γ < 1: congestion mean-reverts — sigmoid pricing p(I) stays bounded"""
        self.assertLess(rho(self.ls), 1,
            f"Expected γ < 1 (stationary congestion), got γ = {rho(self.ls)}")

    def test_market_state_significant(self):
        """Market state coefficients are significant (p < 0.05)"""
        res = result(self.ls)
        for k in beta(self.ls):
            pval = res.pvalues[k]
            self.assertLess(pval, 0.05,
                f"Expected {k} significant (p < 0.05), got p = {pval:.4f}")

    def test_congestion_index_mean_zero(self):
        """ΔI_t has mean ≈ 0 (centered structural residual)"""
        s = state(self.ls)
        self.assertAlmostEqual(s.mean(), 0, delta=0.5,
            msg=f"Expected ΔI_t mean ≈ 0, got {s.mean():.4f}")


if __name__ == "__main__":
    unittest.main()
