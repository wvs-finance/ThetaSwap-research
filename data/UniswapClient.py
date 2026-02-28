"""
UniswapClient — Subgraph client with protocol version adapters

Usage:
    from data.UniswapClient import UniswapClient, v3, v4

    client = UniswapClient(v3())         # Uniswap V3 Ethereum
    client = UniswapClient(v4())         # Uniswap V4
    client = UniswapClient(v3(chain="arbitrum"))

    result = client.query("{ pools(first: 5) { id } }")
"""

import os
import requests
from dataclasses import dataclass
from typing import Dict, Any, Optional

from dotenv import load_dotenv

load_dotenv()

SubgraphId = str
GraphUrl = str
QueryResult = Dict[str, Any]

GRAPH_GATEWAY = "https://gateway.thegraph.com/api"


@dataclass(frozen=True)
class SubgraphConfig:
    subgraph_id: SubgraphId
    label: str


# ── Protocol adapters ──────────────────────────────────────────

def v3(chain: str = "ethereum") -> SubgraphConfig:
    ids: Dict[str, SubgraphId] = {
        "ethereum": "5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV",
        "arbitrum": "FbCGRftH4a3yZugY7TnbYgPJVEv2LvMT6oF1fxPe9aJM",
        "base": "43Hwfi3dJSoGpyas9VwNoDAv55yjgGrPpNSmbQZArzMG",
        "optimism": "Cghf4LfVqPiFw6fp6Y5X5Ubc8UpmUhSfJL82zwiBFLaj",
        "polygon": "3hCPRGf4z88VC5rsBKU5AA9FBBq5nF3jbKJG7VZCbhjm",
    }
    subgraph_id = ids.get(chain)
    if subgraph_id is None:
        raise ValueError(f"No V3 subgraph configured for chain '{chain}'. Available: {list(ids.keys())}")
    return SubgraphConfig(subgraph_id=subgraph_id, label=f"uniswap-v3-{chain}")


def v4(chain: str = "ethereum") -> SubgraphConfig:
    ids: Dict[str, SubgraphId] = {
        "ethereum": "DiYPVdygkfjDWhbxGSqAQxwBKmfKnkWQojqeM2rkLb3G",
    }
    subgraph_id = ids.get(chain)
    if subgraph_id is None:
        raise ValueError(f"No V4 subgraph configured for chain '{chain}'. Available: {list(ids.keys())}")
    return SubgraphConfig(subgraph_id=subgraph_id, label=f"uniswap-v4-{chain}")


# ── Free function accessors ────────────────────────────────────

def subgraph_id(config: SubgraphConfig) -> SubgraphId:
    return config.subgraph_id


def label(config: SubgraphConfig) -> str:
    return config.label


# ── Client ─────────────────────────────────────────────────────

class UniswapClient:
    def __init__(
        self,
        config: SubgraphConfig,
        api_key: Optional[str] = None,
        subgraph_url: Optional[GraphUrl] = None
    ):
        graph_api_key = api_key or os.getenv("GRAPH_API_KEY")
        if subgraph_url:
            self._url = subgraph_url
        elif graph_api_key:
            self._url = f"{GRAPH_GATEWAY}/{graph_api_key}/subgraphs/id/{subgraph_id(config)}"
        else:
            self._url = None

        self._config = config
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    def query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> QueryResult:
        if not self._url:
            raise ValueError(
                "Subgraph URL not configured. Set GRAPH_API_KEY environment variable "
                "or provide api_key parameter. Get a key at https://thegraph.com/studio"
            )

        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        response = self._session.post(self._url, json=payload)
        response.raise_for_status()

        result = response.json()
        if "errors" in result:
            raise Exception(f"Subgraph query failed ({label(self._config)}): {result['errors']}")

        return result.get("data", {})
