import requests
import pandas as pd
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from data.mock_data import get_pools_df, get_network_df, get_historical_df

load_dotenv()

# ─────────────────────────────────────────────
#  CONFIG
# ─────────────────────────────────────────────
API_URL = "https://api.centrifuge.io"
TIMEOUT = 15

# The 4 deRWA pool names we are tracking.
# We use name_contains filters to match them.
TARGET_POOLS = ["JAAA", "JTRSY", "CRDX", "SPXA"]


# ─────────────────────────────────────────────
#  GRAPHQL HELPER
#  All GraphQL calls go through this one
#  function. Returns parsed JSON or None.
# ─────────────────────────────────────────────
def run_query(query: str, variables: dict | None = None) -> dict | None:
    if variables is None:
        variables = {}
    try:
        response = requests.post(
            API_URL,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        result = response.json()
        if "errors" in result:
            print(f"[fetcher] GraphQL error: {result['errors']}")
            return None
        return result.get("data")
    except requests.exceptions.Timeout:
        print("[fetcher] Request timed out")
        return None
    except requests.exceptions.ConnectionError:
        print("[fetcher] No connection to API")
        return None
    except Exception as e:
        print(f"[fetcher] Unexpected error: {e}")
        return None


# ─────────────────────────────────────────────
#  QUERY 1: POOLS + TOKENS
#  Fetches active pools and their nested tokens.
#  TVL = totalIssuance * tokenPrice (per docs).
#  We filter to our 4 target pools by name.
# ─────────────────────────────────────────────
POOLS_QUERY = """
query GetActivePools {
  pools(
    where: { isActive: true, name_not: null }
    limit: 50
  ) {
    items {
      id
      name
      centrifugeId
      isActive
      tokens {
        items {
          id
          name
          symbol
          totalIssuance
          tokenPrice
        }
      }
    }
  }
}
"""

def fetch_pools() -> pd.DataFrame | None:
    """Fetch live pool + token data and return as a DataFrame."""
    data = run_query(POOLS_QUERY)
    if not data:
        return None

    pools = []
    for pool in data.get("pools", {}).get("items", []):
        # Only keep our 4 target pools
        if not any(t in pool["name"] for t in TARGET_POOLS):
            continue

        for token in pool.get("tokens", {}).get("items", []):
            # Decimals default to 18 for ERC-20 tokens
            decimals = 10 ** 18
            total_issuance = float(token.get("totalIssuance") or 0) / decimals
            token_price   = float(token.get("tokenPrice")    or 0) / decimals
            tvl = total_issuance * token_price

            pools.append({
                "pool_id":        token.get("symbol", pool["id"]),  # Keep this for your dashboard display
                "api_id":         pool["id"],                        # ADD THIS: Keep the pure numerical ID for the API
                "pool_name":      token.get("name", pool["name"]),
                "asset_type":     pool["name"],
                "token_id":       token["id"],
                "apy":            0.0,  # APY not in pools query; stays 0 for now
                "tvl":            round(tvl, 2),
                "nav":            round(total_issuance, 2),
                "total_issuance": round(total_issuance, 2),
                "token_price":    round(token_price, 4),
            })

    return pd.DataFrame(pools) if pools else None


# ─────────────────────────────────────────────
#  QUERY 2: VAULTS (network breakdown)
#  Uses pool IDs from Query 1 to fetch
#  which chains each pool is deployed on.
# ─────────────────────────────────────────────
VAULTS_QUERY = """
query GetVaultsByPool($poolId: BigInt!) {
  vaults(
    where: { poolId: $poolId, isActive: true }
    limit: 20
  ) {
    items {
      id
      poolId
      tokenId
      isActive
      blockchain {
        centrifugeId
        name
      }
    }
  }
}
"""

def fetch_networks(pools_df: pd.DataFrame) -> pd.DataFrame | None:
    """
    For each pool, fetch its vault/network breakdown.
    Requires pools_df to get pool IDs.
    """
    if pools_df is None or pools_df.empty:
        return None

    records = []
    seen_api_ids = set()

    for _, row in pools_df.iterrows():
        api_id = row.get("api_id")
        display_name = row.get("pool_id")

        if api_id in seen_api_ids:
            continue
        seen_api_ids.add(api_id)

        data = run_query(VAULTS_QUERY, {"poolId": int(api_id)})
        if not data:
            continue

        for vault in data.get("vaults", {}).get("items", []):
            chain = vault.get("blockchain") or {}
            records.append({
                "pool_id":        display_name,
                "network":        chain.get("name", "Unknown"),
                "nav":            row["nav"],         # pool-level nav for now
                "total_issuance": row["total_issuance"],
                "token_price":    row["token_price"],
            })

    return pd.DataFrame(records) if records else None


# ─────────────────────────────────────────────
#  QUERY 3: TOKEN INSTANCE SNAPSHOTS (history)
#  Uses token IDs from Query 1 to fetch
#  30 days of real historical price + issuance.
# ─────────────────────────────────────────────
SNAPSHOTS_QUERY = """
query GetTokenHistory($tokenId: String!) {
  tokenInstanceSnapshots(
    where: { tokenId: $tokenId }
    orderBy: "timestamp"
    orderDirection: "asc"
    limit: 30
  ) {
    items {
      tokenId
      timestamp
      totalIssuance
      tokenPrice
    }
  }
}
"""

def fetch_historical(pools_df: pd.DataFrame) -> pd.DataFrame | None:
    """
    For each token, fetch its historical snapshots.
    Requires pools_df to get token IDs.
    """
    if pools_df is None or "token_id" not in pools_df.columns:
       return None

    records = []
    decimals = 10 ** 18

    for _, row in pools_df.iterrows():
        token_id = row.get("token_id")
        if not token_id:
            continue

        data = run_query(SNAPSHOTS_QUERY, {"tokenId": token_id})
        if not data:
           continue

        for snap in data.get("tokenInstanceSnapshots", {}).get("items", []):
            ts = snap.get("timestamp", "")

            # Timestamp from API is a Unix int (seconds or ms) or ISO string
            try:
                if ts and str(ts).strip().lstrip("-").isdigit():
                    ts_val = int(ts)
                    if ts_val > 1e11:  # Likely milliseconds
                        ts_val = ts_val / 1000.0
                    date = datetime.fromtimestamp(ts_val, tz=timezone.utc).strftime("%Y-%m-%d")
                elif ts and len(str(ts)) >= 10:
                    date = str(ts)[:10]  # Already an ISO string like "2025-07-19T..."
                else:
                    date = "unknown"
            except Exception:
                date = "unknown"

            issuance    = float(snap.get("totalIssuance") or 0) / decimals
            token_price = float(snap.get("tokenPrice")    or 0) / decimals

            records.append({
               "date":        date,
               "pool_id":     row["pool_id"],
               "pool_name":   row["pool_name"],
               "tvl":         round(issuance * token_price, 2),
               "token_price": round(token_price, 4),
           })

    df = pd.DataFrame(records) if records else None
    if df is not None and not df.empty:
        df = df.sort_values(by=["pool_id", "date"]).reset_index(drop=True)
    return df



# ─────────────────────────────────────────────
#  MAIN LOADER — this is what app.py calls
#  Runs all 3 queries in order.
#  Each one falls back to mock independently.
# ─────────────────────────────────────────────
def load_data() -> tuple[dict, bool]:
    """
    Fetch all data. Falls back to mock per source.

    Returns:
        data   : dict with 'pools', 'networks', 'historical'
        is_live: True if at least pools came from the API
    """
    print("[fetcher] Fetching pools...")
    pools_df = fetch_pools()

    if pools_df is None:
        print("[fetcher] Pools failed — using full mock data")
        return {
            "pools":      get_pools_df(),
            "networks":   get_network_df(),
            "historical": get_historical_df(),
        }, False

    print(f"[fetcher] Got {len(pools_df)} pool-token rows. Fetching networks...")
    networks_df = fetch_networks(pools_df)
    if networks_df is None:
        print("[fetcher] Networks failed — using mock networks")
        networks_df = get_network_df()

    print("[fetcher] Fetching historical snapshots...")
    historical_df = fetch_historical(pools_df)
    if historical_df is None:
        print("[fetcher] History failed — using mock history")
        historical_df = get_historical_df()

    # Drop token_id column — it's internal plumbing, not needed downstream
    pools_clean = pools_df.drop(columns=["token_id"], errors="ignore")

    print("[fetcher] All data loaded successfully (LIVE)")
    return {
        "pools":      pools_clean,
        "networks":   networks_df,
        "historical": historical_df,
    }, True


# ─────────────────────────────────────────────
#  QUICK TEST
#  python data/fetcher.py
# ─────────────────────────────────────────────
if __name__ == "__main__":
    data, is_live = load_data()
    source = "LIVE" if is_live else "MOCK"
    print(f"\n=== Data source: {source} ===")
    print(f"\n--- Pools ({len(data['pools'])} rows) ---")
    print(data["pools"].to_string(index=False))
    print(f"\n--- Networks ({len(data['networks'])} rows) ---")
    print(data["networks"].to_string(index=False))
    print(f"\n--- Historical (first 5 rows) ---")
    print(data["historical"].head().to_string(index=False))