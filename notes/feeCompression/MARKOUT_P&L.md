
// the X timeUnit  markout = the unrealized PnL X timeUnit  after the trade occurs
x       |
       |
       v
    B(X) blockNUmber markout = the unrealized PnL B(X) blocks after the trade ocurred
   
// ===
SELECT
  *,
  SUM(fees) OVER (ORDER BY date DESC NULLS FIRST rows BETWEEN current row AND unbounded following)
  = feeCommulativeOutside(tick)

 AVG(fees) OVER (ORDER BY date DESC NULLS FIRST rows BETWEEN current row AND 7 following)
   =  avg(feeCummulative, BlockWindow)
AVG(pnl_5m_negative / (pnl_5m_negative + pnl_5m_positive)) OVER (ORDER BYdate DESC NULLS FIRST rows BETWEEN current row AND 7 following) AS percent_toxic_flow_moving_avg_7d,

= movingAvg(pnlSeries:Checkpoint, BlockWindow)


AVG(volume) OVER (ORDER BY date DESC NULLS FIRST rows BETWEEN current row AND 7 following) AS moving_avg_7d_volume
= avg(VolumeSeries: Checkpoint, BlockWindow)

SUM(pnl_5m) OVER (ORDER BY date DESC NULLS FIRST rows BETWEEN current row AND unbounded following) AS markout_5m,

= pnlGrowthX<numberRepresentation>(position,BlockWindow)
= sum(isBuy(swap)*(markout(position, BlockWindow)- realizedPrice(swap))*amountOut(swap))

SUM(volume) OVER (ORDER BY date DESC NULLS FIRST rows BETWEEN current row AND unbounded following) AS volume_cumul
= volumeGrowthX<numberRepresentation>(PoolKey, BlockWindow)


FROM
  (SELECT DATE_TRUNC('day', block_time) AS date, SUM(fees_collected_usd) AS fees,
      SUM(protocol_buySell * (markout5m - swapPrice) * eth_swapped) AS pnl_5m,

      SUM(
        CASE
          WHEN protocol_buySell * (markout5m - swapPrice) * eth_swapped >= 0 THEN swapPrice * eth_swapped
          ELSE 0
        END
      ) AS pnl_5m_positive,

      SUM(
        CASE
          WHEN protocol_buySell * (markout5m - swapPrice) * eth_swapped < 0 THEN swapPrice * eth_swapped
          ELSE 0
        END
      ) AS pnl_5m_negative,

      SUM(swapPrice * eth_swapped) AS volume
    FROM
      (SELECT t.block_time,t.exchange_contract_address,t.tx_hash, CAST(amount_usd AS DOUBLE),c.fee
          CAST(amount_usd AS DOUBLE) * (c.fee / 1e6) AS fees_collected_usd,
          CASE
    WHEN t.token_b_symbol = 'USDC' THEN CAST(token_b_amount AS DOUBLE) / CAST(token_a_amount AS DOUBLE)
        WHEN t.token_b_symbol = 'WETH' THEN CAST(token_a_amount AS DOUBLE) / CAST(token_b_amount AS DOUBLE)
          END AS swapPrice,
          CASE
            WHEN t.token_b_symbol = 'WETH' THEN 1
            WHEN t.token_b_symbol = 'USDC' THEN -1
          END AS protocol_buySell,
          LAST_VALUE(
            CASE
              WHEN t.token_b_symbol = 'USDC'
	      THEN CAST(token_b_amount AS DOUBLE) / CAST(token_a_amount AS DOUBLE)
              WHEN t.token_b_symbol = 'WETH'
	      THEN CAST(token_a_amount AS DOUBLE) / CAST(token_b_amount AS DOUBLE)
            END
          ) OVER (
            ORDER BY
              block_time range BETWEEN current row
              AND INTERVAL '5' minute
          ) AS markout5m,
          CASE
            WHEN token_b_symbol = 'WETH' THEN CAST(token_b_amount AS DOUBLE)
            WHEN token_a_symbol = 'WETH' THEN CAST(token_a_amount AS DOUBLE)
            ELSE 0
          END AS eth_swapped
        FROM
          dex."trades" AS t
          LEFT JOIN uniswap_v3_ethereum.Factory_call_createPool AS c ON t.exchange_contract_address = c.output_pool
        WHERE
          t.project = 'Uniswap'
          AND t.version = '3'
          AND t.block_time >= '05-05-2021 17:00' /* Uni v3 launch date/hr */
          AND t.block_time >= CAST('2021-08-01' AS TIMESTAMP)
          AND (
            t.token_a_address = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
            AND t.token_b_address = '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
            OR (
              t.token_a_address = '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
              AND t.token_b_address = '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
            )
          )
          AND CASE
            WHEN t.token_b_symbol = 'USDC' THEN CAST(token_b_amount AS DOUBLE) / CAST(token_a_amount AS DOUBLE)
            WHEN t.token_b_symbol = 'WETH' THEN CAST(token_a_amount AS DOUBLE) / CAST(token_b_amount AS DOUBLE)
          END BETWEEN 500 AND 5000
        ORDER BY
          t.block_time DESC NULLS FIRST
      ) AS X
    WHERE
      1 = 1
      AND eth_swapped > 1e-8
    GROUP BY
      1
    ORDER BY
      1
  ) AS Y