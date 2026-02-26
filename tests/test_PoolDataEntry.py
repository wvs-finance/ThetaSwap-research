#!/usr/bin/env python3
"""
Tests for PoolEntryData - Uniswap V4 Pool Data Handler

Usage:
    source uhi8/bin/activate
    python -m pytest tests/test_PoolDataEntry.py -v

All tests use REAL subgraph data (no mocks).
"""

import os
import sys
import unittest
from typing import Dict, Any
import json
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.DataHandler import PoolEntryData, QueryParams, Timestamp, TimeRange, TimeSeries, query, args
from data.V4Client import V4Subgraph


class TestPoolEntryDataInitialization(unittest.TestCase):
    """Test PoolEntryData initialization with real subgraph data"""

    def test_init_with_pool_id(self):
        """Test initialization with pool_id parameter"""
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolEntryData(pool_id)
        self.assertEqual(pool.pool_id, pool_id)

    def test_init_with_injected_v4_client(self):
        """Test initialization with injected V4Subgraph client"""
        v4 = V4Subgraph()
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolEntryData(pool_id, v4=v4)
        self.assertEqual(pool.v4, v4)

    def test_init_sets_query_path(self):
        """Test that __query_path attribute is set"""
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolEntryData(pool_id)
        query_path = pool._PoolEntryData__query_path
        self.assertTrue(query_path.endswith("queries/PoolDataEntry.json"))

    def test_init_fetches_lifetime(self):
        """Test that lifetime is fetched from real subgraph with non-zero timestamp"""
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolEntryData(pool_id)
        self.assertIsInstance(pool.lifetime, tuple)
        self.assertEqual(len(pool.lifetime), 2)
        self.assertGreater(pool.lifetime[0], 0, "Start timestamp should be non-zero")
        self.assertGreater(pool.lifetime[1], 0, "End timestamp should be non-zero")


class TestPoolEntryDataCall(unittest.TestCase):
    """Test PoolEntryData.__call__ method with real subgraph data"""

    def setUp(self):
        """Set up test fixtures with real data"""
        self.pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        self.pool = PoolEntryData(self.pool_id)

    def test_call_returns_dataframe(self):
        """Test __call__ returns pandas DataFrame"""
        result = self.pool(10)
        self.assertIsInstance(result, pd.DataFrame)

    def test_call_with_number_observations(self):
        """Test __call__ uses numberObservations parameter"""
        result = self.pool(5)
        self.assertLessEqual(len(result), 5)

    def test_call_without_number_observations(self):
        """Test __call__ uses lifetimeLen when numberObservations not given"""
        result = self.pool()
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreater(len(result), 0)


class TestPoolEntryDataHelpers(unittest.TestCase):
    """Test PoolEntryData helper methods with real data"""

    def setUp(self):
        """Set up test fixtures"""
        self.pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        self.pool = PoolEntryData(self.pool_id)

    def test_days_between_static(self):
        """Test __daysBetween static method"""
        result = PoolEntryData._PoolEntryData__daysBetween(0, 86400 * 10)
        self.assertEqual(result, 10)

    def test_lifetime_len(self):
        """Test lifetimeLen returns positive integer from real lifetime"""
        result = self.pool.lifetimeLen()
        self.assertIsInstance(result, int)
        self.assertGreater(result, 0)

    def test_load_queries_from_json(self):
        """Test __loadQueries loads from JSON file"""
        query_path = os.path.join(os.path.dirname(__file__), "..", "queries", "PoolDataEntry.json")
        with open(query_path, "r") as f:
            expected_queries = json.load(f)

        result = self.pool._PoolEntryData__loadQueries("PoolEntryData._fetch_lifetime")
        self.assertIn("query", result)
        self.assertIn("args", result)
        self.assertEqual(result["query"], expected_queries["PoolEntryData._fetch_lifetime"])
        self.assertTrue(len(result["query"]) > 0, "Query string should not be empty")

    def test_to_time_range_conversion(self):
        """Test __toTimeRange converts timestamps correctly"""
        start_ts = 1234567890
        end_ts = 1234567900
        result = self.pool._PoolEntryData__toTimeRange(start_ts, end_ts)
        self.assertEqual(result, (start_ts, end_ts))

    def test_to_data_frame(self):
        """Test __toDataFrame converts query result to DataFrame"""
        result_data = {
            "poolDayDatas": [
                {"date": 1234567890, "tvlUSD": "1000", "volumeUSD": "100",
                 "pool": {"liquidityProviderCount": 5}}
            ]
        }
        df = self.pool._PoolEntryData__toDataFrame(result_data)
        self.assertIsInstance(df, pd.DataFrame)
        self.assertIn("tvlUSD", df.columns)
        self.assertIn("volumeUSD", df.columns)
        self.assertIn("pool_lpCount", df.columns)


class TestPoolEntryDataIntegration(unittest.TestCase):
    """Integration tests for PoolEntryData with real subgraph data"""

    def test_query_file_loading(self):
        """Test query file loading from /queries/PoolDataEntry.json"""
        query_path = os.path.join(os.path.dirname(__file__), "..", "queries", "PoolDataEntry.json")
        self.assertTrue(os.path.exists(query_path), f"Query file not found: {query_path}")

        with open(query_path, "r") as f:
            queries = json.load(f)

        self.assertIn("PoolEntryData._fetch_lifetime", queries)
        self.assertIn("PoolEntryData.poolTimeSeries", queries)

        for key, value in queries.items():
            self.assertTrue(len(value) > 0, f"Query '{key}' should not be empty")

    def test_pool_lifetime_from_subgraph(self):
        """Test pool lifetime from real subgraph with non-zero values"""
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolEntryData(pool_id)

        self.assertIsInstance(pool.lifetime, tuple)
        self.assertEqual(len(pool.lifetime), 2)

        start_ts, end_ts = pool.lifetime
        self.assertGreater(start_ts, 0, "Pool creation timestamp should be non-zero")
        self.assertGreater(end_ts, 0, "End timestamp should be non-zero")
        self.assertGreaterEqual(end_ts, start_ts, "End timestamp should be >= start timestamp")

    def test_pool_call_real_data(self):
        """Test __call__ with real subgraph data returns valid DataFrame"""
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolEntryData(pool_id)
        
        df = pool(30)
        
        self.assertIsInstance(df, pd.DataFrame)
        if len(df) > 0:
            self.assertIn("tvlUSD", df.columns)
            self.assertIn("volumeUSD", df.columns)
            self.assertIn("feesUSD", df.columns)


def run_integration_tests():
    """Run integration tests manually with real subgraph data"""
    print("=" * 60)
    print("PoolEntryData Integration Tests (Real Data)")
    print("=" * 60)
    print()

    print("Test 1: Query file exists")
    try:
        query_path = os.path.join(os.path.dirname(__file__), "..", "queries", "PoolDataEntry.json")
        with open(query_path, "r") as f:
            queries = json.load(f)
        print(f"  ✓ Loaded {len(queries)} queries from {query_path}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False
    print()

    print("Test 2: Pool initialization with real subgraph data")
    try:
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolEntryData(pool_id)
        print(f"  ✓ Pool initialized: {pool.pool_id[:20]}...")
        print(f"  ✓ Lifetime: {pool.lifetime}")
        assert pool.lifetime[0] > 0, "Start timestamp should be non-zero"
        assert pool.lifetime[1] > 0, "End timestamp should be non-zero"
        print(f"  ✓ Timestamps are non-zero")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False
    print()

    print("Test 3: Pool __call__ with real data")
    try:
        pool = PoolEntryData(pool_id)
        df = pool(10)
        print(f"  ✓ DataFrame returned: {len(df)} rows")
        if len(df) > 0:
            print(f"  ✓ Columns: {list(df.columns)[:5]}...")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False
    print()

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
