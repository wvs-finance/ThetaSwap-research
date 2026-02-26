"""
V4Client - Uniswap V4 Subgraph Wrapper

Subgraph endpoint:

https://gateway.thegraph.com/api/{API_KEY}/subgraphs/id/DiYPVdygkfjDWhbxGSqAQxwBKmfKnkWQojqeM2rkLb3G
"""

import os
import requests
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


class V4Subgraph:
    """Client for Uniswap V4 subgraph queries with filtering capabilities"""
    
    # Uniswap V4 subgraph ID on The Graph
    V4_SUBGRAPH_ID = "DiYPVdygkfjDWhbxGSqAQxwBKmfKnkWQojqeM2rkLb3G"

    def __init__(self, subgraph_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize V4Client.

        Args:
            subgraph_url: Optional custom subgraph URL
            api_key: Optional The Graph API key (or set GRAPH_API_KEY env var)
        """
        graph_api_key = api_key or os.getenv("GRAPH_API_KEY")
        if subgraph_url:
            self.subgraph_url = subgraph_url
        elif graph_api_key:
            self.subgraph_url = f"https://gateway.thegraph.com/api/{graph_api_key}/subgraphs/id/{self.V4_SUBGRAPH_ID}"
        else:
            # No API key - will fall back to RPC-only mode
            self.subgraph_url = None

        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json"
        })

    def query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute a GraphQL query against the subgraph.

        Args:
            query: GraphQL query string
            variables: Optional query variables

        Returns:
            JSON response data

        Raises:
            ValueError: If subgraph URL is not configured (set GRAPH_API_KEY env var)
        """
        if not self.subgraph_url:
            raise ValueError(
                "Subgraph URL not configured. Set GRAPH_API_KEY environment variable "
                "or provide api_key parameter. Get a key at https://thegraph.com/studio"
            )

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        response = self._session.post(self.subgraph_url, json=payload)
        response.raise_for_status()

        result = response.json()
        if "errors" in result:
            raise Exception(f"Subgraph query failed: {result['errors']}")

        return result.get("data", {})
