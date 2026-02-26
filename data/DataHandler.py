
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


class PoolEntryData:
    '''
    The chain is ethereum
    '''
    def __init__(
        self,
        pool_id: PoolId,
        v4: Optional[V4Subgraph] = None
    ) -> None:
        """
        Initialize PoolEntryData.

        Args:
            pool_id: The pool contract address or ID
            v4: Optional V4Subgraph client (injected for testability)
        """
        object.__setattr__(self, "v4", v4 or V4Subgraph())
        object.__setattr__(self, "pool_id", pool_id)
        query_path = os.path.join(os.path.dirname(__file__), "..", "queries", "PoolDataEntry.json")
        object.__setattr__(self, "_PoolEntryData__query_path", query_path)
        object.__setattr__(self, "lifetime", self._fetch_lifetime(pool_id, self.v4))

    def __call__(self, numberObservations: Optional[int] = None) -> pd.DataFrame:
        """Fetch pool time series data as DataFrame."""
        n_obs = numberObservations if numberObservations else self.lifetimeLen()
        queryParams: QueryParams = self.__loadQueries("PoolEntryData.poolTimeSeries")
        result: QueryResult = self.v4.query(
            query(queryParams),
            {
                **args(queryParams), "id": self.pool_id.lower(),
                "startDate": self.lifetime[0],
                "first": n_obs
            }
        )
        return self.__toDataFrame(result)

    @staticmethod
    def __daysBetween(startDate: Timestamp, endDate: Timestamp) -> int:
        """Calculate days between two timestamps."""
        return (endDate - startDate) // 86400

    def lifetimeLen(self) -> int:
        """Get number of days in pool's lifetime."""
        return self.__daysBetween(self.lifetime[0], int(dt.datetime.now().timestamp()))
        
        
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
        with open(self._PoolEntryData__query_path, "r") as f:
            queries: Dict[str, str] = json.load(f)
        return {"query": queries.get(sig, ""), "args": {}}

    def __toTimeRange(self, startDate: Timestamp, endDate: Optional[Timestamp] = None) -> TimeRange:
        """Convert timestamps to TimeRange tuple."""
        start: Timestamp = int(startDate) if startDate else int(dt.datetime.now().timestamp())
        end: Timestamp = int(endDate) if endDate else int(dt.datetime.now().timestamp())
        return (start, end)

    def __toDataFrame(self, res: QueryResult) -> pd.DataFrame:
         data: List[Dict[str, Any]] = res.get("poolDayDatas", [])
         if not data:
             return pd.DataFrame()
         to_row = lambda day: {
             "date": pd.to_datetime(day.get("date"), unit="s"),
             "tvlUSD": float(day.get("tvlUSD") or 0),
             "volumeUSD": float(day.get("volumeUSD") or 0),
             "feesUSD": float(day.get("feesUSD") or 0),
             "token0Price": float(day.get("token0Price") or 0),
             "token1Price": float(day.get("token1Price") or 0),
             "sqrtPrice": float(day.get("sqrtPrice") or 0),
             "txCount": int(day.get("txCount") or 0),
             "open": float(day.get("open") or 0),
             "high": float(day.get("high") or 0),
             "low": float(day.get("low") or 0),
             "close": float(day.get("close") or 0),
             "pool_lpCount": int(day.get("pool", {}).get("liquidityProviderCount") or 0),
             "pool_txCount": int(day.get("pool", {}).get("txCount") or 0),
             "pool_collectedFeesUSD": float(day.get("pool", {}).get("collectedFeesUSD") or 0)
         }
         df = pd.DataFrame([to_row(day) for day in data]).set_index("date")

         return df
         
    def __toTimeStamp(self, res: QueryResult) -> Timestamp:
        """Extract timestamp from query result."""
        pool: Dict[str, Any] = res.get("pool", {})
        ts: Timestamp = int(pool.get("createdAtTimestamp", 0))
        return ts

    def _toTimeSeries(self, res: QueryResult) -> TimeSeries:
        """Convert query result to pandas TimeSeries."""
        pass

        
    
        
