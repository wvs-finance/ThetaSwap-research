"""
V4Client — Backward-compatible alias for UniswapClient(v4())

Existing code that imports V4Subgraph continues to work unchanged.
"""

from data.UniswapClient import UniswapClient, v4

from typing import Dict, Any, Optional


class V4Subgraph(UniswapClient):
    V4_SUBGRAPH_ID = "DiYPVdygkfjDWhbxGSqAQxwBKmfKnkWQojqeM2rkLb3G"

    def __init__(self, subgraph_url: Optional[str] = None, api_key: Optional[str] = None):
        super().__init__(config=v4(), api_key=api_key, subgraph_url=subgraph_url)

    @property
    def subgraph_url(self) -> Optional[str]:
        return self._url
