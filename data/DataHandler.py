
from data.V4Client import V4Subgraph
from data.UniswapClient import UniswapClient
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
        v4: Optional[V4Subgraph] = None,
        client: Optional[UniswapClient] = None
    ) -> None:
        """
        Initialize PoolEntryData.

        Args:
            pool_id: The pool contract address or ID
            v4: Optional V4Subgraph client (backward compat)
            client: Optional UniswapClient (preferred — works with v3 or v4)
        """
        object.__setattr__(self, "v4", client or v4 or V4Subgraph())
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
             "liquidity": float(day.get("liquidity") or 0)
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

        
def load_fee_compression(path: str = "data/fee_compression_sample.csv", interpolate: bool = True) -> TimeSeries:
    """Load fee compression time series, optionally interpolate to daily."""
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    series = pd.to_numeric(df["fee_compression"], errors="coerce")
    if interpolate:
        daily_idx = pd.date_range(series.index.min(), series.index.max(), freq="D")
        series = series.reindex(daily_idx).interpolate(method="cubic")
    return series


def volumeUSD(poolData:pd.DataFrame) -> TimeSeries:
    """
    Get USD volume time series.
    It must return the volumeUSD column only
    """    
    return poolData["volumeUSD"]

def priceUSD(poolData:pd.DataFrame) -> TimeSeries:
    """Get USD price time series."""
    return poolData["token0Price"]

def tvlUSD(poolData:pd.DataFrame) -> TimeSeries:
    """Get USD TVL time series."""
    return poolData["tvlUSD"]

def liquidity(poolData: pd.DataFrame) -> TimeSeries:
    """Get in-range liquidity time series (liquidity at active tick)."""
    return poolData["liquidity"]

def delta(series:TimeSeries) -> TimeSeries:
    diff = series.diff()
    return diff.fillna({diff.index[0]: series.mean()})


def div(numerator: TimeSeries, denominator: TimeSeries) -> TimeSeries:
    return numerator/ denominator

def forward(series: TimeSeries) -> TimeSeries:
    return series.shift(-1)

def lagged(series: TimeSeries) -> TimeSeries:
    return series.shift(1)

def txCount(poolData: pd.DataFrame) -> TimeSeries:
    return poolData["txCount"]


def feesUSD(poolData: pd.DataFrame) -> TimeSeries:
    return poolData["feesUSD"]


def normalize(series: TimeSeries, window: int = 30) -> TimeSeries:
    return series / series.rolling(window).mean()


def variance(series: TimeSeries, libraryPointer:Optional[str]) -> TimeSeries:
    strategy = VarianceStrategy()
    return strategy(series,libraryPointer)

class VarianceStrategy:
    """Strategy pattern for variance calculation."""
    
    def __call__(self, series: TimeSeries, libraryPointer: Optional[str] = None) -> TimeSeries:
        """
        Calculate cumulative variance at each timestamp.
        
        Args:
            series: Input time series
            libraryPointer: Library to use ("numpy", "pandas", or None for default)
            
        Returns:
            TimeSeries with cumulative variance at each timestamp
        """
        if libraryPointer is None or libraryPointer == "pandas":
            return series.expanding().var()
        elif libraryPointer == "numpy":
            import numpy as np
            return pd.Series([np.var(series.iloc[:i+1].values) for i in range(len(series))], 
                           index=series.index)
        else:
            return series.expanding().var()

 
