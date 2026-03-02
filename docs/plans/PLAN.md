
## Part III: Data, Assumptions, and Equations

### 3.1 Resources
- source -> **On-Chain Data (Uniswap V4 Subgraph):**
- resources -> github MCP, docker, uniswap-ai, uniswap-v4-subgraph


### 3.2 Workflow
1. Select the most optimal pool we are looking  largest consistent TVL and trading volume


---> (ethereum,0x395f91b34aa34a477ce3bc6505639a821b286a62b1a164fc1887fa3a5ef713a5)
2. For this pool, we need to get it's lifetime
3. What data do we need ?


For the time series analyisis we just need to make one query for the entire lifespan of the pool and
store it on a dataFrame.

1. Derive the rigth schema
2. build the data model on how ius to be saved on dataStructures locally
3. test with small obsrevation sizes
4. get all the data
5. test it stored it correctly

1. Deriva the right schema.

{
  poolDayDatas(
    first: len(sef.lifetime),
    	   "difference between the days of each timestamp"
	   
    orderBy: date, 
    where: {
      pool: (This is the pool),
      date_gt: day(startDat(self.lifetime))
    } 
  ) {
    date
    tvlUSD
    volumeUSD
    feesUSD
    token0Price
    token1Price
    sqrtPrice
    txCount
    pool{
	txCount
	collectedFeesUSD
	liquidityProviderCount
    }
  }
}


---> This is from v4-subgraph 