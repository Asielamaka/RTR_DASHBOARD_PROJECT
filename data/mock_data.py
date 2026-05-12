import pandas as pd
import numpy as np
from datetime import datetime, timedelta


# ─────────────────────────────────────────────
#  POOL DEFINITIONS
#  These mirror the 4 deRWA pools we saw on
#  the Centrifuge platform screenshot.
# ─────────────────────────────────────────────

POOLS = [
    {
        "pool_id":    "JAAA",
        "pool_name":  "DeFi JAAA Token",
        "asset_type": "AAA Collateralized Loans",
        "apy":        4.26,
        "tvl":        4_929_045,
        "nav":        4_328_845,
        "total_issuance": 4_192_581,
        "token_price": 1.03,
    },
    {
        "pool_id":    "JTRSY",
        "pool_name":  "DeFi JTRSY Token",
        "asset_type": "US Treasury Bills",
        "apy":        3.32,
        "tvl":        2_632_911,
        "nav":        2_580_000,
        "total_issuance": 2_510_000,
        "token_price": 1.02,
    },
    {
        "pool_id":    "CRDX",
        "pool_name":  "DeFi CRDX Token",
        "asset_type": "Corporate Credit",
        "apy":        8.18,
        "tvl":        99_613,
        "nav":        91_000,
        "total_issuance": 95_000,
        "token_price": 0.97,   # slightly stressed
    },
    {
        "pool_id":    "SPXA",
        "pool_name":  "DeFi SPXA Token",
        "asset_type": "Equities",
        "apy":        0.0,     # 0% APY is a risk flag
        "tvl":        3_118_202,
        "nav":        3_050_000,
        "total_issuance": 3_000_000,
        "token_price": 1.00,
    },
]


# ─────────────────────────────────────────────
#  NETWORK BREAKDOWN
#  Each pool exists on multiple blockchains.
#  This mirrors the expanded JAAA view we saw.
# ─────────────────────────────────────────────

NETWORK_DATA = [
    # JAAA across networks
    {"pool_id": "JAAA", "network": "Ethereum",  "nav": 4_328_845, "total_issuance": 4_192_581, "token_price": 1.03},
    {"pool_id": "JAAA", "network": "Arbitrum",  "nav": 7_658,    "total_issuance": 7_417,    "token_price": 1.03},
    {"pool_id": "JAAA", "network": "Avalanche", "nav": 2_621,    "total_issuance": 2_539,    "token_price": 1.03},
    {"pool_id": "JAAA", "network": "Base",      "nav": 589_919,  "total_issuance": 571_349,  "token_price": 1.03},
    # JTRSY across networks
    {"pool_id": "JTRSY", "network": "Ethereum", "nav": 2_400_000, "total_issuance": 2_340_000, "token_price": 1.02},
    {"pool_id": "JTRSY", "network": "Base",     "nav": 180_000,   "total_issuance": 170_000,   "token_price": 1.02},
    # CRDX across networks
    {"pool_id": "CRDX",  "network": "Ethereum", "nav": 91_000,   "total_issuance": 95_000,   "token_price": 0.97},
    # SPXA across networks
    {"pool_id": "SPXA",  "network": "Ethereum", "nav": 3_050_000, "total_issuance": 3_000_000, "token_price": 1.00},
]


# ─────────────────────────────────────────────
#  HISTORICAL TREND DATA (30 days)
#  We simulate 30 days of TVL history per pool.
#  This is what makes the risk trend chart work.
#  np.random.seed() ensures the same "random"
#  data every time (reproducible results).
# ─────────────────────────────────────────────

def generate_historical_data() -> pd.DataFrame:
    np.random.seed(42)
    records = []
    today = datetime.today()

    for pool in POOLS:
        base_tvl = pool["tvl"]
        base_price = pool["token_price"]

        for i in range(30):
            date = today - timedelta(days=29 - i)

            # Simulate gradual TVL change with small daily noise
            tvl_noise = np.random.normal(0, base_tvl * 0.008)
            tvl = base_tvl * (1 + (i - 15) * 0.002) + tvl_noise

            # Simulate token price hovering near its base with noise
            price_noise = np.random.normal(0, 0.003)
            price = base_price + price_noise

            records.append({
                "date":       date.strftime("%Y-%m-%d"),
                "pool_id":    pool["pool_id"],
                "pool_name":  pool["pool_name"],
                "tvl":        round(tvl, 2),
                "token_price": round(price, 4),
            })

    return pd.DataFrame(records)


# ─────────────────────────────────────────────
#  PUBLIC LOADER FUNCTIONS
#  These are what the rest of the app imports.
#  Clean, simple, predictable interfaces.
# ─────────────────────────────────────────────

def get_pools_df() -> pd.DataFrame:
    """Return current pool snapshot as a DataFrame."""
    return pd.DataFrame(POOLS)

def get_network_df() -> pd.DataFrame:
    """Return per-network breakdown as a DataFrame."""
    return pd.DataFrame(NETWORK_DATA)

def get_historical_df() -> pd.DataFrame:
    """Return 30-day historical TVL and price data."""
    return generate_historical_data()


# ─────────────────────────────────────────────
#  QUICK TEST
#  Run this file directly to verify it works:
#  python data/mock_data.py
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Pools ===")
    print(get_pools_df().to_string(index=False))
    print("\n=== Networks ===")
    print(get_network_df().to_string(index=False))
    print("\n=== Historical (first 5 rows) ===")
    print(get_historical_df().head().to_string(index=False))
