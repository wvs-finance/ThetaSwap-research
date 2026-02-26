#!/usr/bin/env python3
"""
Tests for V4Client - Uniswap V4 Subgraph Wrapper

Usage:
    source uhi8/bin/activate
    python tests/V4Client.test.py
"""

import os
import sys
import unittest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.V4Client import V4Subgraph


class TestV4SubgraphInitialization(unittest.TestCase):
    """Test V4Subgraph initialization"""

    def test_init_with_api_key_from_env(self):
        """Test initialization uses GRAPH_API_KEY from environment"""
        client = V4Subgraph()
        self.assertIsNotNone(client.subgraph_url, "subgraph_url should be set from GRAPH_API_KEY env var")
        self.assertIn("gateway.thegraph.com", client.subgraph_url)
        self.assertIn("DiYPVdygkfjDWhbxGSqAQxwBKmfKnkWQojqeM2rkLb3G", client.subgraph_url)

    def test_init_with_custom_api_key(self):
        """Test initialization with explicit api_key parameter"""
        client = V4Subgraph(api_key="test_key_123")
        self.assertIn("test_key_123", client.subgraph_url)

    def test_init_with_custom_subgraph_url(self):
        """Test initialization with custom subgraph_url parameter"""
        custom_url = "https://custom.example.com/subgraph"
        client = V4Subgraph(subgraph_url=custom_url)
        self.assertEqual(client.subgraph_url, custom_url)


class TestV4SubgraphQueries(unittest.TestCase):
    """Test V4Subgraph query functionality"""

    def setUp(self):
        """Create a V4Subgraph client for testing"""
        self.client = V4Subgraph()

    def test_query_basic_pool_fetch(self):
        """Test basic pool query"""
        query = """
        query GetPools($first: Int!) {
            pools(first: $first) {
                id
                feeTier
            }
        }
        """
        result = self.client.query(query, {"first": 5})
        
        self.assertIn("pools", result)
        self.assertIsInstance(result["pools"], list)
        self.assertLessEqual(len(result["pools"]), 5)

    def test_query_returns_data_structure(self):
        """Test that query returns proper data structure"""
        query = """
        {
            pools(first: 1) {
                id
                feeTier
                liquidity
                totalValueLockedUSD
            }
        }
        """
        result = self.client.query(query)
        
        self.assertIsInstance(result, dict)
        if result.get("pools"):
            pool = result["pools"][0]
            self.assertIn("id", pool)
            self.assertIn("feeTier", pool)

    def test_query_with_variables(self):
        """Test query with variables"""
        query = """
        query GetPools($first: Int!, $skip: Int!) {
            pools(first: $first, skip: $skip) {
                id
            }
        }
        """
        result = self.client.query(query, {"first": 3, "skip": 0})
        
        self.assertIn("pools", result)
        self.assertLessEqual(len(result["pools"]), 3)

    def test_query_invalid_query_raises_error(self):
        """Test that invalid GraphQL query raises exception"""
        query = "query { invalidField }"
        
        with self.assertRaises(Exception):
            self.client.query(query)


class TestV4SubgraphConnection(unittest.TestCase):
    """Test connection to subgraph"""

    def setUp(self):
        """Create a V4Subgraph client for testing"""
        self.client = V4Subgraph()

    def test_subgraph_responds(self):
        """Test that subgraph endpoint responds"""
        query = "{ pools(first: 1) { id } }"
        result = self.client.query(query)
        self.assertIn("pools", result)

    def test_can_fetch_pool_count(self):
        """Test that we can fetch and count pools"""
        query = """
        query GetPools($first: Int!) {
            pools(first: $first) {
                id
            }
        }
        """
        result = self.client.query(query, {"first": 100})
        
        self.assertIn("pools", result)
        self.assertGreater(len(result["pools"]), 0, "Should have at least one pool")


def run_integration_tests():
    """Run integration tests manually (without unittest discovery)"""
    print("=" * 60)
    print("V4Client Integration Tests")
    print("=" * 60)
    print()

    # Test 1: Initialization
    print("Test 1: Initialization")
    try:
        client = V4Subgraph()
        print(f"  ✓ Client initialized")
        print(f"  ✓ Subgraph URL: {client.subgraph_url[:50]}...")
    except Exception as e:
        print(f"  ✗ Initialization failed: {e}")
        return False
    print()

    # Test 2: Basic Query
    print("Test 2: Basic Pool Query")
    try:
        query = """
        query GetPools($first: Int!) {
            pools(first: $first) {
                id
                feeTier
                totalValueLockedUSD
            }
        }
        """
        result = client.query(query, {"first": 5})
        pool_count = len(result.get("pools", []))
        print(f"  ✓ Fetched {pool_count} pools")
        if result.get("pools"):
            sample_pool = result["pools"][0]
            print(f"  ✓ Sample pool: {sample_pool.get('id', 'N/A')[:20]}...")
    except Exception as e:
        print(f"  ✗ Query failed: {e}")
        return False
    print()

    # Test 3: TVL Data
    print("Test 3: TVL Data Available")
    try:
        query = """
        query GetPools($first: Int!) {
            pools(first: $first) {
                id
                totalValueLockedUSD
                volumeUSD
            }
        }
        """
        result = client.query(query, {"first": 10})
        pools_with_tvl = [
            p for p in result.get("pools", []) 
            if float(p.get("totalValueLockedUSD") or 0) > 0
        ]
        print(f"  ✓ {len(pools_with_tvl)}/{len(result.get('pools', []))} pools have TVL data")
    except Exception as e:
        print(f"  ✗ TVL query failed: {e}")
        return False
    print()

    # Test 4: Token Data
    print("Test 4: Token Data Available")
    try:
        query = """
        query GetPools($first: Int!) {
            pools(first: $first) {
                id
                token0 {
                    symbol
                    name
                }
                token1 {
                    symbol
                    name
                }
            }
        }
        """
        result = client.query(query, {"first": 5})
        for pool in result.get("pools", [])[:2]:
            t0 = pool.get("token0", {}).get("symbol", "N/A")
            t1 = pool.get("token1", {}).get("symbol", "N/A")
            print(f"  ✓ Pool: {t0}/{t1}")
    except Exception as e:
        print(f"  ✗ Token query failed: {e}")
        return False
    print()

    print("=" * 60)
    print("All tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    # Run integration tests when executed directly
    success = run_integration_tests()
    sys.exit(0 if success else 1)
