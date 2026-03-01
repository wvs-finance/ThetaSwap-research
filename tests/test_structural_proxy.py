#!/usr/bin/env python3
"""
Tests for structural fee compression proxy.

Usage:
    source uhi8/bin/activate
    python -m pytest tests/test_structural_proxy.py -v
"""
import os
import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestFeeCompressionDailyLoader(unittest.TestCase):
    """Test the daily fee compression loader."""

    @classmethod
    def setUpClass(cls):
        path = "data/fee_compression_daily.csv"
        if not os.path.exists(path):
            raise unittest.SkipTest(f"{path} not found — run structural_proxy.py first")

    def test_load_returns_series(self):
        from data.DataHandler import load_fee_compression_daily
        fc = load_fee_compression_daily()
        self.assertIsInstance(fc, pd.Series)
        self.assertGreater(len(fc), 1000)

    def test_no_all_nan(self):
        from data.DataHandler import load_fee_compression_daily
        fc = load_fee_compression_daily()
        self.assertLess(fc.isna().mean(), 0.1, "More than 10% NaN")

    def test_values_finite(self):
        from data.DataHandler import load_fee_compression_daily
        fc = load_fee_compression_daily().dropna()
        self.assertTrue(np.all(np.isfinite(fc.values)), "Non-finite values found")


class TestStructuralProxyCalibration(unittest.TestCase):
    """Test that the structural proxy produces valid calibration."""

    @classmethod
    def setUpClass(cls):
        path = "data/fg_inside_range_sample.csv"
        if not os.path.exists(path):
            raise unittest.SkipTest(f"{path} not found — run compute_fg_inside_range.py first")
        cls.train = pd.read_csv(path, parse_dates=["date"], index_col="date")

    def test_actual_pcr_bounded(self):
        """actual_pcr should be between 0 and 1 for most observations."""
        pcr = self.train["actual_pcr"]
        valid = pcr[(pcr >= 0) & (pcr <= 1)]
        self.assertGreater(len(valid) / len(pcr), 0.6,
                           "Less than 60% of pcr values in [0, 1]")

    def test_sufficient_observations(self):
        """Need at least 100 training points."""
        self.assertGreater(len(self.train), 100)


class TestEconometricIntegration(unittest.TestCase):
    """Test that FeeCompression integrates into the two-stage model."""

    @classmethod
    def setUpClass(cls):
        path = "data/fee_compression_daily.csv"
        if not os.path.exists(path):
            raise unittest.SkipTest(f"{path} not found — run structural_proxy.py first")
        from data.DataHandler import load_fee_compression_daily
        cls.fc = load_fee_compression_daily()

    def test_series_stationary_proxy(self):
        """FeeCompression changes should be roughly stationary (ADF p < 0.1)."""
        from statsmodels.tsa.stattools import adfuller
        changes = self.fc.pct_change().dropna().replace([np.inf, -np.inf], np.nan).dropna()
        if len(changes) < 100:
            self.skipTest("Too few observations")
        adf_stat, pvalue, *_ = adfuller(changes.values[:1000])
        self.assertLess(pvalue, 0.1, f"ADF p-value {pvalue:.4f} — not stationary")


if __name__ == "__main__":
    unittest.main()
