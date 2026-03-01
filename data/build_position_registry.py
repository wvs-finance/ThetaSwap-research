"""
Build registry of all NPM positions on V3 USDC/WETH 5bps pool.
Uses The Graph V3 subgraph to enumerate positions (avoids eth_getLogs Free tier limits).
"""
import csv
import time
import requests

POOL_ID = "0x88e6a0c2ddd26feeb64f039a2c41296fcb3f5640"
GRAPH_API_KEY = "7f16f0b767676e4df13e75fb963b9fab"
SUBGRAPH_URL = f"https://gateway.thegraph.com/api/{GRAPH_API_KEY}/subgraphs/id/5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV"
OUTPUT_PATH = "data/position_registry.csv"


def fetch_positions() -> list:
    """Paginate through all positions on the USDC/WETH pool via The Graph."""
    positions = []
    last_id = ""
    page = 0

    while True:
        query = """
        {
            positions(
                first: 1000,
                where: {
                    pool: "%s",
                    id_gt: "%s"
                },
                orderBy: id,
                orderDirection: asc
            ) {
                id
                tickLower { tickIdx }
                tickUpper { tickIdx }
                liquidity
            }
        }
        """ % (POOL_ID, last_id)

        try:
            resp = requests.post(SUBGRAPH_URL, json={"query": query}, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if "errors" in data:
                print(f"  GraphQL errors: {data['errors']}")
                break

            batch = data["data"]["positions"]
            if not batch:
                break

            positions.extend(batch)
            last_id = batch[-1]["id"]
            page += 1

            if page % 10 == 0:
                print(f"  Page {page}: {len(positions)} positions so far (last_id: {last_id})")

            time.sleep(0.3)  # rate limit

        except Exception as e:
            print(f"  Error on page {page}: {e}")
            time.sleep(2)
            continue

    return positions


def main():
    print("Fetching all positions on USDC/WETH 5bps pool from The Graph...")
    raw_positions = fetch_positions()
    print(f"Fetched {len(raw_positions)} total positions")

    # Convert to CSV format
    rows = []
    for pos in raw_positions:
        rows.append({
            "tokenId": pos["id"],
            "tickLower": pos["tickLower"]["tickIdx"],
            "tickUpper": pos["tickUpper"]["tickIdx"],
            "liquidity": pos["liquidity"],
        })

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["tokenId", "tickLower", "tickUpper", "liquidity"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. {len(rows)} positions written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
