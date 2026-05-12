"""
analysis/risk_engine.py
-----------------------
Computes composite risk scores (0–100) for each pool using the
three-factor weighted model defined in the PRD:


   Risk Score =
       Price Deviation Score  × 40 %
     + TVL Trend Score        × 35 %
     + APY Anomaly Score      × 25 %


Tiers:
   0 – 30   →  Low Risk    🟢
   31 – 60  →  Medium Risk 🟡
   61 – 100 →  High Risk   🔴


Usage (from analysis/ folder):
   from risk_engine import compute_risk


Usage (from project root via app.py):
   from analysis.risk_engine import compute_risk
"""


import pandas as pd
import numpy as np
from typing import NamedTuple





# ---------------------------------------------------------------------------
# Weights (must sum to 1.0)
# ---------------------------------------------------------------------------


W_PRICE_DEVIATION = 0.40
W_TVL_TREND       = 0.35
W_APY_ANOMALY     = 0.25


assert abs(W_PRICE_DEVIATION + W_TVL_TREND + W_APY_ANOMALY - 1.0) < 1e-9, \
   "Risk weights must sum to 1.0"




# ---------------------------------------------------------------------------
# Tier thresholds
# ---------------------------------------------------------------------------


TIER_LOW_MAX    = 30
TIER_MEDIUM_MAX = 60


TIER_LABELS  = {0: "Low Risk",    1: "Medium Risk",  2: "High Risk"}
TIER_COLOURS = {0: "green",       1: "yellow",        2: "red"}
TIER_EMOJI   = {0: "🟢",          1: "🟡",            2: "🔴"}




# ---------------------------------------------------------------------------
# Output container
# ---------------------------------------------------------------------------


class RiskData(NamedTuple):
   scores:  pd.DataFrame   # One row per pool — full risk breakdown
   summary: pd.DataFrame   # Lightweight table for dashboard Overview page




# ---------------------------------------------------------------------------
# Factor scorers  (each returns a float 0–100)
# ---------------------------------------------------------------------------


def _score_price_deviation(price_deviation: float) -> float:
   """
   Converts token_price deviation from $1.00 into a 0–100 score.


   Logic:
       - Deviation of 0.00  →   0  (perfect peg)
       - Deviation of −0.05 →  50  (5 % below peg, moderate stress)
       - Deviation of −0.10 →  100 (10 %+ below peg, severe stress)
       - Positive deviation (premium) → low but non-zero score (0–10)
         because premiums can signal liquidity imbalances too.


   Clamped to [0, 100].
   """
   if pd.isna(price_deviation):
       return 50.0  # Unknown → neutral score


   if price_deviation < 0:
       # Below peg: scale 0 → −0.10 linearly to 0 → 100
       raw = abs(price_deviation) / 0.10 * 100.0
   else:
       # Above peg: small positive score (0–10 for 0–5 % premium)
       raw = min(price_deviation / 0.05 * 10.0, 10.0)


   return float(np.clip(raw, 0.0, 100.0))




def _score_tvl_trend(
   tvl_change_pct: float,
   tvl_volatility: float,
   tvl_end: float,
) -> float:
   """
   Converts 30-day TVL movement into a 0–100 risk score.


   Logic:
       - Strong growth  (> +10 %)  →   0–10   (healthy)
       - Flat           (±1 %)     →  20–30   (neutral)
       - Moderate drop  (−10 %)    →  50      (watch)
       - Severe drop    (−25 %+)   →  90–100  (alarm)


   Volatility adds up to 15 points on top (high std-dev = instability).
   Clamped to [0, 100].
   """
   if pd.isna(tvl_change_pct):
       return 50.0


   # Trend component: map change_pct to [0, 85]
   # Linear: −25 % or worse → 85 pts, +10 % or better → 0 pts
   trend_score = np.interp(
       tvl_change_pct,
       xp=[-25.0, -10.0, -1.0, 1.0, 10.0],
       fp=[ 85.0,  50.0,  30.0, 20.0,  0.0],
   )


   # Volatility component: scale against the pool's own TVL
   # If std-dev > 20 % of average TVL, max volatility penalty (15 pts)
   vol_ratio = (tvl_volatility / tvl_end) if tvl_end > 0 else 0.0
   vol_score = float(np.clip(vol_ratio / 0.20 * 15.0, 0.0, 15.0))


   return float(np.clip(trend_score + vol_score, 0.0, 100.0))




def _score_apy_anomaly(apy: float) -> float:
   """
   Converts APY into a 0–100 risk score.


   Logic:
       - APY == 0 %          → 80  (zero yield is a strong red flag)
       - APY 0–3 %           → 10–30 (very low, worth watching)
       - APY 3–15 % (normal) →  0–20 (healthy range)
       - APY > 15 %          → 70–100 (unsustainably high)
       - APY > 30 %          → 100   (almost certainly distressed)


   Clamped to [0, 100].
   """
   if pd.isna(apy):
       return 50.0


   if apy == 0.0:
       return 80.0


   if apy < 0.0:
       # Negative yield is extremely distressed
       return 100.0


   if 0.0 < apy <= 3.0:
       # Low end: linear 30 → 10 as APY goes 0 → 3
       return float(np.interp(apy, [0.0, 3.0], [30.0, 10.0]))


   if 3.0 < apy <= 15.0:
       # Normal range: linear 10 → 20 (slight uptick reflects concentration risk)
       return float(np.interp(apy, [3.0, 15.0], [10.0, 20.0]))


   if 15.0 < apy <= 30.0:
       # High: linear 70 → 90
       return float(np.interp(apy, [15.0, 30.0], [70.0, 90.0]))


   # > 30 %: max alarm
   return float(np.clip((apy - 30.0) / 10.0 * 10.0 + 90.0, 90.0, 100.0))




# ---------------------------------------------------------------------------
# Tier classifier
# ---------------------------------------------------------------------------


def _classify(score: float) -> tuple[str, str, str]:
   """Returns (tier_label, colour, emoji) for a given composite score."""
   if score <= TIER_LOW_MAX:
       key = 0
   elif score <= TIER_MEDIUM_MAX:
       key = 1
   else:
       key = 2
   return TIER_LABELS[key], TIER_COLOURS[key], TIER_EMOJI[key]




# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_risk(
   pools: pd.DataFrame,
   tvl_trends: pd.DataFrame,
) -> RiskData:
   """
   Computes composite risk scores for every pool.


   Parameters
   ----------
   pools : pd.DataFrame
       Enriched pools DataFrame from processor.process_all().pools.
       Required columns: pool_id, pool_name, asset_type, apy,
                         token_price, price_deviation, apy_anomaly.


   tvl_trends : pd.DataFrame
       TVL trend summary from processor.process_all().tvl_trends.
       Required columns: pool_id, tvl_change_pct, tvl_volatility, tvl_end.


   Returns
   -------
   RiskData
       .scores  — full breakdown DataFrame (one row per pool)
       .summary — lightweight overview table for the dashboard
   """
   print("[risk_engine] Computing risk scores...")


   # --- Validate inputs ---
   required_pools = {"pool_id", "pool_name", "asset_type",
                     "apy", "price_deviation", "apy_anomaly"}
   required_trends = {"pool_id", "tvl_change_pct", "tvl_volatility", "tvl_end"}


   missing_p = required_pools - set(pools.columns)
   missing_t = required_trends - set(tvl_trends.columns)


   if missing_p:
       raise ValueError(f"[risk_engine] pools DataFrame missing columns: {missing_p}")
   if missing_t:
       raise ValueError(f"[risk_engine] tvl_trends DataFrame missing columns: {missing_t}")


   # --- Merge pools with tvl_trends on pool_id ---
   merged = pools.merge(tvl_trends, on="pool_id", how="left")


   records = []


   for _, row in merged.iterrows():
       pool_id   = row["pool_id"]
       pool_name = row.get("pool_name", pool_id)
       asset_type = row.get("asset_type", "Unknown")


       # --- Raw factor scores (0–100 each) ---
       price_score = _score_price_deviation(row.get("price_deviation", np.nan))
       tvl_score   = _score_tvl_trend(
           tvl_change_pct=row.get("tvl_change_pct", np.nan),
           tvl_volatility=row.get("tvl_volatility", 0.0),
           tvl_end=row.get("tvl_end", 1.0),
       )
       apy_score = _score_apy_anomaly(row.get("apy", np.nan))


       # --- Composite weighted score ---
       composite = (
           price_score * W_PRICE_DEVIATION
           + tvl_score * W_TVL_TREND
           + apy_score * W_APY_ANOMALY
       )
       composite = round(float(np.clip(max(composite, price_score, tvl_score, apy_score), 0.0, 100.0)), 2)


       # --- Tier classification ---
       tier_label, colour, emoji = _classify(composite)


       # --- Key flags for the Risk Signals dashboard page ---
       price_deviation = row.get("price_deviation", np.nan)
       apy_anomaly     = bool(row.get("apy_anomaly", False))
       tvl_trend       = row.get("tvl_trend", "flat")


       price_flag = not pd.isna(price_deviation) and abs(price_deviation) >= 0.02
       tvl_flag   = tvl_trend == "down"


       records.append({
           # Identity
           "pool_id":          pool_id,
           "pool_name":        pool_name,
           "asset_type":       asset_type,
           # Raw inputs used for scoring
           "apy":              round(float(row.get("apy", np.nan)), 4),
           "token_price":      round(float(row.get("token_price", np.nan)), 4),
           "price_deviation":  round(float(price_deviation), 4) if not pd.isna(price_deviation) else np.nan,
           "tvl_change_pct":   round(float(row.get("tvl_change_pct", np.nan)), 4) if not pd.isna(row.get("tvl_change_pct")) else np.nan,
           "tvl_trend":        tvl_trend,
           # Factor scores (0–100)
           "price_score":      round(price_score, 2),
           "tvl_score":        round(tvl_score, 2),
           "apy_score":        round(apy_score, 2),
           # Composite
           "risk_score":       composite,
           "risk_tier":        tier_label,
           "risk_colour":      colour,
           "risk_emoji":       emoji,
           # Boolean flags for dashboard callouts
           "flag_price":       price_flag,
           "flag_tvl":         tvl_flag,
           "flag_apy":         apy_anomaly,
       })


   scores_df = (
       pd.DataFrame(records)
       .sort_values("risk_score", ascending=False)
       .reset_index(drop=True)
   )


   # --- Lightweight summary for the Overview page ---
   summary_df = scores_df[[
       "pool_id", "pool_name", "asset_type",
       "risk_score", "risk_tier", "risk_emoji",
       "flag_price", "flag_tvl", "flag_apy",
   ]].copy()


   # Active flag count per pool (how many signals are firing)
   summary_df["active_flags"] = (
       summary_df[["flag_price", "flag_tvl", "flag_apy"]].sum(axis=1)
   )


   print(f"[risk_engine] ✅ Scored {len(scores_df)} pools.")
   for _, r in scores_df.iterrows():
       print(f"  {r['risk_emoji']}  {r['pool_id']:6s}  "
             f"score={r['risk_score']:5.1f}  tier={r['risk_tier']}")
   print()


   return RiskData(scores=scores_df, summary=summary_df)




# ---------------------------------------------------------------------------
# Quick smoke-test  (run: python risk_engine.py  from inside analysis/ folder)
# ---------------------------------------------------------------------------


if __name__ == "__main__":
   import sys
   import os


   # Allow imports from the data/ and analysis/ sibling folders
   project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
   sys.path.insert(0, os.path.join(project_root, "data"))
   sys.path.insert(0, os.path.join(project_root, "analysis"))


   try:
       from data.mock_data import get_pools_df, get_network_df, get_historical_df
       from data.processor import process_all
   except ImportError as e:
       print(f"Import error: {e}")
       print("Make sure you have data/mock_data.py and data/processor.py in the project.")
       sys.exit(1)


   raw = {
       "pools":      get_pools_df(),
       "networks":   get_network_df(),
       "historical": get_historical_df(),
   }


   processed = process_all(raw)
   risk      = compute_risk(processed.pools, processed.tvl_trends)


   print("=" * 65)
   print("FULL RISK SCORES:")
   print(risk.scores[[
       "pool_id", "price_score", "tvl_score", "apy_score",
       "risk_score", "risk_tier", "risk_emoji",
   ]].to_string(index=False))


   print("\nSUMMARY TABLE (for Overview page):")
   print(risk.summary.to_string(index=False))


   print("\nFLAG DETAILS:")
   for _, r in risk.scores.iterrows():
       flags = []
       if r["flag_price"]: flags.append(f"price deviation {r['price_deviation']:+.3f}")
       if r["flag_tvl"]:   flags.append(f"TVL trending {r['tvl_trend']}")
       if r["flag_apy"]:   flags.append(f"APY anomaly ({r['apy']:.2f}%)")
       flag_str = " | ".join(flags) if flags else "none"
       print(f"  {r['risk_emoji']}  {r['pool_id']:6s}  flags: {flag_str}")

