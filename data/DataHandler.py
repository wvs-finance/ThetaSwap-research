
from data.V4Client import V4Subgraph
import json
import os
from typing import Dict, Any, List, Optional, Tuple, Callable
import pandas as pd
import datetime as dt

# Type aliases
QueryParams = Dict[str, Any]
Timestamp = int
TimeRange = Tuple[Timestamp, Timestamp]
TimeSeries = pd.Series
PoolId = str
QueryResult = Dict[str, Any]


def query(params: QueryParams) -> str:
    """Extract query string from QueryParams."""
    return params.get("query", "")


def args(params: QueryParams) -> Dict[str, Any]:
    """Extract args dict from QueryParams."""
    return params.get("args", {})


class PoolDataEntry:
    '''
    The chain is ethereum
    '''
    def __init__(
        self,
        pool_id: PoolId,
        v4: Optional[V4Subgraph] = None
    ) -> None:
        """
        Initialize PoolDataEntry.

        Args:
            pool_id: The pool contract address or ID
            v4: Optional V4Subgraph client (injected for testability)
        """
        object.__setattr__(self, "v4", v4 or V4Subgraph())
        object.__setattr__(self, "pool_id", pool_id)
        # Query path relative to project root
        query_path = os.path.join(os.path.dirname(__file__), "..", "queries", "PoolDataEntry.json")
        object.__setattr__(self, "_PoolDataEntry__query_path", query_path)
        object.__setattr__(self, "lifetime", self._fetch_lifetime(pool_id, self.v4))
        
    def _fetch_lifetime(
        self,
        pool_id: PoolId,
        v4: V4Subgraph
    ) -> TimeRange:
        """Fetch pool creation timestamp and compute lifetime range."""
        queryParams: QueryParams = self.__loadQueries(self._fetch_lifetime.__qualname__)
        result: QueryResult = v4.query(query(queryParams), {**args(queryParams), "id": pool_id.lower()})
        createdAt: Timestamp = self.__toTimeStamp(result)
        endDate: Timestamp = int(dt.datetime.now().timestamp())
        return self.__toTimeRange(createdAt, endDate)

    def activePositions(self) -> TimeSeries:
        """Get active positions time series."""
        pass

    def volumeUSD(self) -> TimeSeries:
        """Get USD volume time series."""
        pass

    def priceUSD(self) -> TimeSeries:
        """Get USD price time series."""
        pass

    def tvlUSD(self) -> TimeSeries:
        """Get USD TVL time series."""
        pass

    def __loadQueries(self, sig: str) -> QueryParams:
        """Load query from JSON by method signature."""
        with open(self.__query_path, "r") as f:
            queries: Dict[str, str] = json.load(f)
        return {"query": queries.get(sig, ""), "args": {}}

    def __toTimeRange(self, startDate: Timestamp, endDate: Optional[Timestamp] = None) -> TimeRange:
        """Convert timestamps to TimeRange tuple."""
        start: Timestamp = int(startDate) if startDate else int(dt.datetime.now().timestamp())
        end: Timestamp = int(endDate) if endDate else int(dt.datetime.now().timestamp())
        return (start, end)

    def __toTimeStamp(self, res: QueryResult) -> Timestamp:
        """Extract timestamp from query result."""
        pool: Dict[str, Any] = res.get("pool", {})
        ts: Timestamp = int(pool.get("createdAtTimestamp", 0))
        return ts

    def _toTimeSeries(self, res: QueryResult) -> TimeSeries:
        """Convert query result to pandas TimeSeries."""
        pass

        
    
        
