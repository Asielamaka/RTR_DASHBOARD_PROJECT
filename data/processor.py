"""
data/processor.py
-----------------
Cleans, validates, and enriches raw DataFrames from fetcher.load_data().
Returns analysis-ready DataFrames for risk_engine.py.

Usage (from data/ folder):
    from processor import process_all

Usage (from project root via app.py):
    from data.processor import process_all
"""

import pandas as pd
import numpy as np
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Output container
# ---------------------------------------------------------------------------

class ProcessedData(NamedTuple):
    pools: pd.DataFrame         # Enriched pool snapshot
    networks: pd.DataFrame      # Enriched per-chain breakdown
    historical: pd.DataFrame    # Cleaned 30-day history
    tvl_trends: pd.DataFrame    # 30-day TVL trend summary per pool


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APY_ANOMALY_HIGH = 15.0   # % — suspiciously high APY threshold
APY_ANOMALY_LOW  = 0.0    # % — zero APY flag
STABLE_PRICE_TARGET = 1.0 # Expected token price for stable/debt pools


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_float(series: pd.Series, col_name: str) -> pd.Series:
    """Coerce a column to float64, warning on any conversion failures."""
    converted = pd.to_numeric(series, errors="coerce")
    n_bad = converted.isna().sum() - series.isna().sum()
    if n_bad > 0:
        print(f"  [processor] WARNING: {n_bad} non-numeric value(s) in '{col_name}' → set to NaN")
    return converted.astype("float64")


def _to_date(series: pd.Series, col_name: str) -> pd.Series:
    """Coerce a column to datetime64[ns], warning on failures."""
    converted = pd.to_datetime(series, errors="coerce", utc=True)
    n_bad = converted.isna().sum() - series.isna().sum()
    if n_bad > 0:
        print(f"  [processor] WARNING: {n_bad} unparseable date(s) in '{col_name}' → set to NaT")
    # Strip timezone info for cleaner downstream handling
    return converted.dt.tz_localize(None)


# ---------------------------------------------------------------------------
# Step 1 — Clean & type-cast pools DataFrame
# ---------------------------------------------------------------------------

def _process_pools(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Validates and enriches the pool snapshot DataFrame.

    Adds:
        collateral_ratio  — nav / total_issuance (NaN if total_issuance == 0)
        price_deviation   — token_price - 1.0
        apy_anomaly       — True when APY is 0 % or above 15 %
    """
    df = raw.copy()

    # --- Type coercion ---
    float_cols = ["apy", "tvl", "nav", "total_issuance", "token_price"]
    for col in float_cols:
        if col in df.columns:
            df[col] = _to_float(df[col], col)
        else:
            print(f"  [processor] WARNING: expected column '{col}' missing from pools DataFrame")
            df[col] = np.nan

    # Ensure string columns are clean
    for col in ["pool_id", "pool_name", "asset_type"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # --- Derived metrics ---

    # Collateral ratio: how well NAV covers total issuance
    df["collateral_ratio"] = np.where(
        df["total_issuance"] > 0,
        df["nav"] / df["total_issuance"],
        np.nan,
    )

    # Price deviation from the $1.00 stable target
    df["price_deviation"] = df["token_price"] - STABLE_PRICE_TARGET

    # APY anomaly flag: zero APY or suspiciously high APY
    df["apy_anomaly"] = (df["apy"] <= APY_ANOMALY_LOW) | (df["apy"] >= APY_ANOMALY_HIGH)

    # --- Drop duplicates (keep latest snapshot per pool) ---
    df = df.drop_duplicates(subset=["pool_id"], keep="last").reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Step 2 — Clean & type-cast networks DataFrame
# ---------------------------------------------------------------------------

def _process_networks(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Validates and enriches the per-chain breakdown DataFrame.

    Adds:
        collateral_ratio  — nav / total_issuance per network row
        price_deviation   — token_price - 1.0 per network row
    """
    df = raw.copy()

    float_cols = ["nav", "total_issuance", "token_price"]
    for col in float_cols:
        if col in df.columns:
            df[col] = _to_float(df[col], col)
        else:
            print(f"  [processor] WARNING: expected column '{col}' missing from networks DataFrame")
            df[col] = np.nan

    for col in ["pool_id", "network"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Derived metrics (same logic as pools, per-chain granularity)
    df["collateral_ratio"] = np.where(
        df["total_issuance"] > 0,
        df["nav"] / df["total_issuance"],
        np.nan,
    )
    df["price_deviation"] = df["token_price"] - STABLE_PRICE_TARGET

    df = df.drop_duplicates(subset=["pool_id", "network"], keep="last").reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Step 3 — Clean historical DataFrame
# ---------------------------------------------------------------------------

def _process_historical(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Validates and cleans the 30-day historical DataFrame.

    Ensures:
        - 'date' is a proper datetime column (no timezone, date-only)
        - 'tvl' and 'token_price' are float64
        - Rows are sorted by pool_id, then date (ascending)
        - No exact duplicate (pool_id, date) rows
    """
    df = raw.copy()

    if "date" in df.columns:
        df["date"] = _to_date(df["date"], "date")
        # Normalise to date-only (midnight) for consistent grouping
        df["date"] = df["date"].dt.normalize()
    else:
        print("  [processor] WARNING: 'date' column missing from historical DataFrame")
        df["date"] = pd.NaT

    for col in ["tvl", "token_price"]:
        if col in df.columns:
            df[col] = _to_float(df[col], col)
        else:
            print(f"  [processor] WARNING: expected column '{col}' missing from historical DataFrame")
            df[col] = np.nan

    for col in ["pool_id", "pool_name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df = (
        df
        .drop_duplicates(subset=["pool_id", "date"], keep="last")
        .sort_values(["pool_id", "date"])
        .reset_index(drop=True)
    )

    return df


# ---------------------------------------------------------------------------
# Step 4 — Compute 30-day TVL trends per pool
# ---------------------------------------------------------------------------

def _compute_tvl_trends(historical: pd.DataFrame) -> pd.DataFrame:
    """
    Summarises the 30-day TVL trend for each pool.

    Returns a DataFrame with one row per pool_id containing:
        tvl_start       — TVL on the earliest date in the window
        tvl_end         — TVL on the most recent date in the window
        tvl_change      — Absolute change  (tvl_end − tvl_start)
        tvl_change_pct  — Percentage change (NaN if tvl_start == 0)
        tvl_trend       — 'up', 'down', or 'flat' (within ±1 % is flat)
        tvl_volatility  — Std deviation of daily TVL (proxy for instability)
    """
    if historical.empty or "tvl" not in historical.columns:
        return pd.DataFrame(columns=[
            "pool_id", "tvl_start", "tvl_end",
            "tvl_change", "tvl_change_pct", "tvl_trend", "tvl_volatility",
        ])

    records = []

    for pool_id, grp in historical.groupby("pool_id"):
        grp = grp.sort_values("date").dropna(subset=["tvl"])

        if grp.empty:
            continue

        tvl_start = float(grp["tvl"].iloc[0])
        tvl_end   = float(grp["tvl"].iloc[-1])
        tvl_change = tvl_end - tvl_start

        if tvl_start != 0:
            tvl_change_pct = (tvl_change / tvl_start) * 100.0
        else:
            tvl_change_pct = np.nan

        # Flat = within ±1 % of starting value
        if pd.isna(tvl_change_pct):
            trend = "flat"
        elif tvl_change_pct > 1.0:
            trend = "up"
        elif tvl_change_pct < -1.0:
            trend = "down"
        else:
            trend = "flat"

        tvl_volatility = float(grp["tvl"].std()) if len(grp) > 1 else 0.0

        records.append({
            "pool_id":        pool_id,
            "tvl_start":      round(tvl_start, 2),
            "tvl_end":        round(tvl_end, 2),
            "tvl_change":     round(tvl_change, 2),
            "tvl_change_pct": round(tvl_change_pct, 4) if not np.isnan(tvl_change_pct) else np.nan,
            "tvl_trend":      trend,
            "tvl_volatility": round(tvl_volatility, 2),
        })

    return pd.DataFrame(records).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def process_all(raw_data: dict) -> ProcessedData:
    """
    Entry point for the processing pipeline.

    Parameters
    ----------
    raw_data : dict
        The dict returned by fetcher.load_data(), containing keys:
        "pools", "networks", "historical" — each a pd.DataFrame.

    Returns
    -------
    ProcessedData
        A NamedTuple with four enriched DataFrames:
        .pools, .networks, .historical, .tvl_trends
    """
    print("[processor] Starting data processing pipeline...")

    # --- Validate input ---
    for key in ("pools", "networks", "historical"):
        if key not in raw_data:
            raise KeyError(f"[processor] Expected key '{key}' not found in raw_data dict.")
        if not isinstance(raw_data[key], pd.DataFrame):
            raise TypeError(f"[processor] raw_data['{key}'] must be a pd.DataFrame.")

    # --- Run each processing step ---
    pools_df      = _process_pools(raw_data["pools"])
    networks_df   = _process_networks(raw_data["networks"])
    historical_df = _process_historical(raw_data["historical"])
    tvl_trends_df = _compute_tvl_trends(historical_df)

    print(f"[processor] ✅ pools      — {len(pools_df)} rows | "
          f"columns: {list(pools_df.columns)}")
    print(f"[processor] ✅ networks   — {len(networks_df)} rows | "
          f"columns: {list(networks_df.columns)}")
    print(f"[processor] ✅ historical — {len(historical_df)} rows")
    print(f"[processor] ✅ tvl_trends — {len(tvl_trends_df)} rows | "
          f"columns: {list(tvl_trends_df.columns)}")
    print("[processor] Pipeline complete.\n")

    return ProcessedData(
        pools=pools_df,
        networks=networks_df,
        historical=historical_df,
        tvl_trends=tvl_trends_df,
    )


# ---------------------------------------------------------------------------
# Quick smoke-test  (run: python processor.py  from inside the data/ folder)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os

    # Allow running from either the data/ folder or the project root
    sys.path.insert(0, os.path.dirname(__file__))

    try:
        from mock_data import get_pools_df, get_network_df, get_historical_df
        print("Using mock data for smoke-test...\n")

        raw = {
            "pools":      get_pools_df(),
            "networks":   get_network_df(),
            "historical": get_historical_df(),
        }
    except ImportError:
        print("mock_data not found — run this from the data/ folder.")
        sys.exit(1)

    result = process_all(raw)

    print("=" * 60)
    print("POOLS (enriched):")
    print(result.pools[["pool_id", "apy", "token_price",
                          "collateral_ratio", "price_deviation", "apy_anomaly"]].to_string())

    print("\nNETWORKS (enriched):")
    print(result.networks[["pool_id", "network", "nav",
                             "collateral_ratio", "price_deviation"]].to_string())

    print("\nTVL TRENDS:")
    print(result.tvl_trends.to_string())

    print("\nHISTORICAL (first 5 rows):")
    print(result.historical.head().to_string())