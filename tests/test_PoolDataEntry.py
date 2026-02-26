#!/usr/bin/env python3
"""
Tests for PoolDataEntry - Uniswap V4 Pool Data Handler

Usage:
    source uhi8/bin/activate
    python -m pytest tests/test_PoolDataEntry.py -v

Note: Methods with `pass` implementation are NOT tested:
    - activePositions()
    - volumeUSD()
    - priceUSD()
    - tvlUSD()
    - _toTimeSeries()
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch
from typing import Dict, Any
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.DataHandler import PoolDataEntry, QueryParams, Timestamp, TimeRange, TimeSeries, query, args
from data.V4Client import V4Subgraph


class TestPoolDataEntryInitialization(unittest.TestCase):
    """Test PoolDataEntry initialization"""

    def test_init_with_pool_id(self):
        """Test initialization with pool_id parameter"""
        mock_v4 = Mock(spec=V4Subgraph)
        mock_v4.query.return_value = {"pool": {"createdAtTimestamp": "1234567890"}}
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolDataEntry(pool_id, v4=mock_v4)
        self.assertEqual(pool.pool_id, pool_id)

    def test_init_with_injected_v4_client(self):
        """Test initialization with injected V4Subgraph client"""
        mock_v4 = Mock(spec=V4Subgraph)
        mock_v4.query.return_value = {"pool": {"createdAtTimestamp": "1234567890"}}
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolDataEntry(pool_id, v4=mock_v4)
        self.assertEqual(pool.v4, mock_v4)

    def test_init_sets_query_path(self):
        """Test that __query_path attribute is set"""
        mock_v4 = Mock(spec=V4Subgraph)
        mock_v4.query.return_value = {"pool": {"createdAtTimestamp": "1234567890"}}
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolDataEntry(pool_id, v4=mock_v4)
        query_path = pool._PoolDataEntry__query_path
        self.assertTrue(query_path.endswith("queries/PoolDataEntry.json"))

    def test_init_fetches_lifetime(self):
        """Test that lifetime is fetched from real subgraph with non-zero timestamp"""
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolDataEntry(pool_id)
        self.assertIsInstance(pool.lifetime, tuple)
        self.assertEqual(len(pool.lifetime), 2)
        # Verify timestamps are non-zero (real subgraph data)
        self.assertGreater(pool.lifetime[0], 0, "Start timestamp should be non-zero")
        self.assertGreater(pool.lifetime[1], 0, "End timestamp should be non-zero")


class TestPoolDataEntryHelpers(unittest.TestCase):
    """Test PoolDataEntry helper methods"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_v4 = Mock(spec=V4Subgraph)
        self.mock_v4.query.return_value = {"pool": {"createdAtTimestamp": "1234567890"}}
        self.pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        self.pool = PoolDataEntry(self.pool_id, v4=self.mock_v4)

    def test_load_queries_from_json(self):
        """Test __loadQueries loads from JSON file"""
        query_path = os.path.join(os.path.dirname(__file__), "..", "queries", "PoolDataEntry.json")
        with open(query_path, "r") as f:
            expected_queries = json.load(f)

        result = self.pool._PoolDataEntry__loadQueries("PoolDataEntry._fetch_lifetime")
        self.assertIn("query", result)
        self.assertIn("args", result)
        self.assertEqual(result["query"], expected_queries["PoolDataEntry._fetch_lifetime"])
        # Verify query is non-empty
        self.assertTrue(len(result["query"]) > 0, "Query string should not be empty")

    def test_to_time_range_conversion(self):
        """Test __toTimeRange converts timestamps correctly"""
        start_ts = 1234567890
        end_ts = 1234567900
        result = self.pool._PoolDataEntry__toTimeRange(start_ts, end_ts)
        self.assertEqual(result, (start_ts, end_ts))

    def test_to_time_stamp_extraction(self):
        """Test __toTimeStamp extracts timestamp from result"""
        result_data = {"pool": {"createdAtTimestamp": "1234567890"}}
        ts = self.pool._PoolDataEntry__toTimeStamp(result_data)
        self.assertEqual(ts, 1234567890)
        self.assertGreater(ts, 0, "Extracted timestamp should be non-zero")
        self.assertIsInstance(ts, int)


class TestPoolDataEntryIntegration(unittest.TestCase):
    """Integration tests for PoolDataEntry"""

    def test_query_file_loading(self):
        """Test query file loading from /queries/PoolDataEntry.json"""
        query_path = os.path.join(os.path.dirname(__file__), "..", "queries", "PoolDataEntry.json")
        self.assertTrue(os.path.exists(query_path), f"Query file not found: {query_path}")

        with open(query_path, "r") as f:
            queries = json.load(f)

        self.assertIn("PoolDataEntry._fetch_lifetime", queries)
        self.assertIn("PoolDataEntry.activePositions", queries)
        self.assertIn("PoolDataEntry.volumeUSD", queries)
        self.assertIn("PoolDataEntry.priceUSD", queries)
        self.assertIn("PoolDataEntry.tvlUSD", queries)
        
        # Verify all queries are non-empty strings
        for key, value in queries.items():
            self.assertTrue(len(value) > 0, f"Query '{key}' should not be empty")

    def test_pool_lifetime_from_subgraph(self):
        """Test pool lifetime is retrieved from real subgraph with non-zero values"""
        pool_id = "0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5"
        pool = PoolDataEntry(pool_id)
        
        # Verify lifetime tuple structure
        self.assertIsInstance(pool.lifetime, tuple)
        self.assertEqual(len(pool.lifetime), 2)
        
        # Verify both timestamps are non-zero (real subgraph data)
        start_ts, end_ts = pool.lifetime
        self.assertGreater(start_ts, 0, "Pool creation timestamp should be non-zero")
        self.assertGreater(end_ts, 0, "End timestamp should be non-zero")
        
        # Verify end >= start
        self.assertGreaterEqual(end_ts, start_ts, "End timestamp should be >= start timestamp")


class TestQueryParams(unittest.TestCase):
    """Test QueryParams functional accessors"""

    def test_query_accessor(self):
        """Test query() accessor returns query string"""
        params: QueryParams = {"query": "SELECT * FROM pool", "args": {"id": "0x123"}}
        result = query(params)
        self.assertEqual(result, "SELECT * FROM pool")

    def test_args_accessor(self):
        """Test args() accessor returns args dict"""
        params: QueryParams = {"query": "SELECT * FROM pool", "args": {"id": "0x123"}}
        result = args(params)
        self.assertEqual(result, {"id": "0x123"})


def run_integration_tests():
    """Run integration tests manually"""
    print("=" * 60)
    print("PoolDataEntry Integration Tests")
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
        pool = PoolDataEntry(pool_id)
        print(f"  ✓ Pool initialized: {pool.pool_id[:20]}...")
        print(f"  ✓ Lifetime: {pool.lifetime}")
        # Verify non-zero (real subgraph data)
        assert pool.lifetime[0] > 0, "Start timestamp should be non-zero"
        assert pool.lifetime[1] > 0, "End timestamp should be non-zero"
        print(f"  ✓ Timestamps are non-zero")
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
