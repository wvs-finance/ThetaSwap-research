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

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.Econometrics import LiquidityState, LiquidityStateModel, beta, rho, state, result
from data.DataHandler import PoolEntryData, delta, tvlUSD, variance, priceUSD, div, lagged


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


class TestLiquidityStateModelStructure(unittest.TestCase):
    """Test LiquidityStateModel returns correct types and shapes with real data"""

    @classmethod
    def setUpClass(cls):
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolEntryData(pool_id)
        cls.pool_data = pool(90)
        cls.endog = div(delta(tvlUSD(cls.pool_data)), lagged(tvlUSD(cls.pool_data)))
        cls.exog = variance(div(delta(priceUSD(cls.pool_data)), lagged(priceUSD(cls.pool_data))), None)
        # Store clean length (after dropping NaN/inf from exog)
        mask = np.isfinite(cls.endog) & np.isfinite(cls.exog)
        cls.clean_len = int(mask.sum())
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
        self.assertEqual(len(state(self.ls)), self.clean_len)

    def test_ar2_returns_valid_state(self):
        ls2 = LiquidityStateModel()(endog=self.endog, exog=self.exog, ar=2)
        self.assertIsInstance(ls2, LiquidityState)
        self.assertIsInstance(beta(ls2), float)
        self.assertIsInstance(rho(ls2), float)


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
        cls.endog = div(delta(tvlUSD(cls.pool_data)), lagged(tvlUSD(cls.pool_data)))
        cls.exog = variance(div(delta(priceUSD(cls.pool_data)), lagged(priceUSD(cls.pool_data))), None)
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


if __name__ == "__main__":
    unittest.main()
