"""
visuals/charts.py
-----------------
All Matplotlib / Seaborn charts for the RWA Transparency & Risk Dashboard.
Every function returns a Matplotlib Figure so Streamlit can render it via
st.pyplot(fig).

Chart inventory (one function per chart):
    1. plot_tvl_bar          — Overview: TVL by pool (bar)
    2. plot_risk_gauge       — Overview / Risk: single-pool risk score gauge
    3. plot_risk_table       — Risk Signals: ranked risk summary heatmap-table
    4. plot_price_deviation  — Risk Signals: price deviation bar (all pools)
    5. plot_network_breakdown— Pool Deep Dive: NAV by network (horizontal bar)
    6. plot_nav_vs_issuance  — Collateral Health: grouped bar NAV vs issuance
    7. plot_tvl_history      — Pool Deep Dive / Collateral: 30-day TVL line
    8. plot_price_history    — Pool Deep Dive: 30-day token price line

Design language
---------------
- Dark background (#0D1117) with off-white text (#E6EDF3)
- Accent palette: teal (#2DD4BF), amber (#FBBF24), rose (#FB7185), slate (#94A3B8)
- Risk colours: green (#22C55E), yellow (#EAB308), red (#EF4444)
- Font: DejaVu Sans (bundled with Matplotlib — no install needed)
- Tight layouts, minimal spines, subtle grid lines
"""

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for Streamlit

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.figure import Figure


# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

BG_PAGE   = "#0D1117"
BG_AXES   = "#161B22"
BG_CARD   = "#1C2128"
TEXT_PRI  = "#E6EDF3"
TEXT_SEC  = "#8B949E"
GRID_COL  = "#21262D"
BORDER    = "#30363D"

# Pool accent colours (consistent across charts)
POOL_COLOURS = {
    "JAAA":  "#2DD4BF",   # Teal
    "JTRSY": "#60A5FA",   # Blue
    "CRDX":  "#FB7185",   # Rose
    "SPXA":  "#FBBF24",   # Amber
}
FALLBACK_COLOURS = ["#A78BFA", "#34D399", "#F97316", "#E879F9"]

# Risk tier colours
RISK_GREEN  = "#22C55E"
RISK_YELLOW = "#EAB308"
RISK_RED    = "#EF4444"


def _risk_colour(score: float) -> str:
    if score <= 30:
        return RISK_GREEN
    elif score <= 60:
        return RISK_YELLOW
    return RISK_RED


def _pool_colour(pool_id: str, idx: int = 0) -> str:
    return POOL_COLOURS.get(pool_id, FALLBACK_COLOURS[idx % len(FALLBACK_COLOURS)])


def _apply_base_style(fig: Figure, axes) -> None:
    """Apply the dark theme to a figure and one or more axes."""
    fig.patch.set_facecolor(BG_PAGE)
    ax_list = axes if hasattr(axes, "__iter__") else [axes]
    for ax in ax_list:
        ax.set_facecolor(BG_AXES)
        ax.tick_params(colors=TEXT_SEC, labelsize=9)
        ax.xaxis.label.set_color(TEXT_SEC)
        ax.yaxis.label.set_color(TEXT_SEC)
        ax.title.set_color(TEXT_PRI)
        for spine in ax.spines.values():
            spine.set_color(BORDER)
        ax.grid(color=GRID_COL, linewidth=0.5, linestyle="--", alpha=0.7)


def _fmt_millions(x: float, _=None) -> str:
    """Format large numbers as $XM or $XK."""
    if abs(x) >= 1_000_000:
        return f"${x/1_000_000:.1f}M"
    if abs(x) >= 1_000:
        return f"${x/1_000:.0f}K"
    return f"${x:.0f}"


# ---------------------------------------------------------------------------
# 1. TVL Bar Chart  —  Overview page
# ---------------------------------------------------------------------------

def plot_tvl_bar(pools: pd.DataFrame) -> Figure:
    """
    Horizontal bar chart showing Total Value Locked per pool.
    Bars are coloured by pool identity.
    """
    df = pools[["pool_id", "tvl"]].dropna().sort_values("tvl", ascending=True)

    fig, ax = plt.subplots(figsize=(7, 3.2))
    _apply_base_style(fig, ax)

    colours = [_pool_colour(pid, i) for i, pid in enumerate(df["pool_id"])]
    bars = ax.barh(df["pool_id"], df["tvl"], color=colours,
                   height=0.55, edgecolor="none")

    # Value labels at end of each bar
    for bar, val in zip(bars, df["tvl"]):
        ax.text(
            bar.get_width() + bar.get_width() * 0.01,
            bar.get_y() + bar.get_height() / 2,
            _fmt_millions(val),
            va="center", ha="left", fontsize=8.5,
            color=TEXT_PRI, fontweight="semibold",
        )

    ax.set_xlabel("Total Value Locked", labelpad=6)
    ax.set_title("TVL by Pool", fontsize=11, fontweight="bold", pad=10)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_millions))
    ax.set_xlim(0, df["tvl"].max() * 1.18)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID_COL, linewidth=0.5, linestyle="--", alpha=0.7)

    plt.tight_layout(pad=1.0)
    return fig


# ---------------------------------------------------------------------------
# 2. Risk Gauge  —  Overview / Risk Signals page
# ---------------------------------------------------------------------------

def plot_risk_gauge(score: float, pool_id: str, pool_name: str) -> Figure:
    """
    Semi-circular gauge showing a single pool's composite risk score.
    """
    fig, ax = plt.subplots(figsize=(4, 2.4), subplot_kw={"aspect": "equal"})
    _apply_base_style(fig, ax)
    ax.set_facecolor(BG_PAGE)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)

    score = float(np.clip(score, 0, 100))
    colour = _risk_colour(score)

    # Background arc (full 180°)
    theta = np.linspace(np.pi, 0, 200)
    r = 1.0
    ax.plot(r * np.cos(theta), r * np.sin(theta),
            color=BORDER, linewidth=14, solid_capstyle="round")

    # Filled arc proportional to score
    fill_theta = np.linspace(np.pi, np.pi - (score / 100) * np.pi, 200)
    ax.plot(r * np.cos(fill_theta), r * np.sin(fill_theta),
            color=colour, linewidth=14, solid_capstyle="round")

    # Score text
    ax.text(0, 0.08, f"{score:.0f}", ha="center", va="center",
            fontsize=28, fontweight="bold", color=TEXT_PRI)
    ax.text(0, -0.22, "/ 100", ha="center", va="center",
            fontsize=9, color=TEXT_SEC)

    # Tier label
    if score <= 30:
        tier = "Low Risk"
    elif score <= 60:
        tier = "Medium Risk"
    else:
        tier = "High Risk"
    ax.text(0, -0.48, tier, ha="center", va="center",
            fontsize=9.5, fontweight="bold", color=colour)

    # Pool label
    ax.text(0, 0.60, f"{pool_id} — {pool_name}", ha="center", va="center",
            fontsize=8, color=TEXT_SEC)

    ax.set_xlim(-1.3, 1.3)
    ax.set_ylim(-0.7, 1.15)
    plt.tight_layout(pad=0.3)
    return fig


# ---------------------------------------------------------------------------
# 3. Risk Summary Table  —  Risk Signals page
# ---------------------------------------------------------------------------

def plot_risk_table(summary: pd.DataFrame) -> Figure:
    """
    Colour-coded summary table: pool | score | tier | flags.
    """
    cols_needed = ["pool_id", "risk_score", "risk_tier", "risk_emoji",
                   "flag_price", "flag_tvl", "flag_apy", "active_flags"]
    df = summary[cols_needed].sort_values("risk_score", ascending=False).reset_index(drop=True)

    n_rows = len(df)
    fig, ax = plt.subplots(figsize=(7, 0.55 * n_rows + 1.0))
    _apply_base_style(fig, ax)
    ax.set_facecolor(BG_PAGE)
    ax.axis("off")

    col_labels = ["Pool", "Risk Score", "Tier", "Price Flag", "TVL Flag", "APY Flag"]
    col_widths = [0.14, 0.18, 0.22, 0.15, 0.15, 0.15]
    x_positions = np.cumsum([0] + col_widths[:-1]) + 0.01

    # Header row
    header_y = 1.0
    for x, label in zip(x_positions, col_labels):
        ax.text(x, header_y, label, transform=ax.transAxes,
                fontsize=8.5, fontweight="bold", color=TEXT_SEC,
                va="top", ha="left")

    # Divider line
    ax.axhline(y=header_y - 0.04, color=BORDER, linewidth=0.8)

    row_height = (header_y - 0.06) / n_rows

    for i, row in df.iterrows():
        y = header_y - 0.08 - i * row_height
        score  = row["risk_score"]
        colour = _risk_colour(score)

        # Alternating row background
        bg_alpha = 0.3 if i % 2 == 0 else 0.0
        ax.add_patch(mpatches.FancyBboxPatch(
            (0, y - row_height * 0.85), 1, row_height,
            transform=ax.transAxes,
            boxstyle="square,pad=0",
            facecolor=BG_CARD, alpha=bg_alpha, zorder=0,
        ))

        values = [
            row["pool_id"],
            f"{score:.1f}",
            f"{row['risk_emoji']}  {row['risk_tier']}",
            "🚩" if row["flag_price"] else "✓",
            "🚩" if row["flag_tvl"]   else "✓",
            "🚩" if row["flag_apy"]   else "✓",
        ]
        cell_colours = [
            TEXT_PRI, colour, colour,
            RISK_RED if row["flag_price"] else RISK_GREEN,
            RISK_RED if row["flag_tvl"]   else RISK_GREEN,
            RISK_RED if row["flag_apy"]   else RISK_GREEN,
        ]

        for x, val, col in zip(x_positions, values, cell_colours):
            ax.text(x, y, val, transform=ax.transAxes,
                    fontsize=8.5, color=col, va="top", ha="left")

    ax.set_title("Risk Signal Summary", fontsize=11, fontweight="bold",
                 color=TEXT_PRI, pad=8)
    plt.tight_layout(pad=0.5)
    return fig


# ---------------------------------------------------------------------------
# 4. Price Deviation Bar  —  Risk Signals page
# ---------------------------------------------------------------------------

def plot_price_deviation(pools: pd.DataFrame) -> Figure:
    """
    Vertical bar chart showing token price deviation from $1.00 for each pool.
    Bars are red for negative deviations, green for positive.
    """
    df = pools[["pool_id", "price_deviation"]].dropna().sort_values("price_deviation")

    fig, ax = plt.subplots(figsize=(6, 3.2))
    _apply_base_style(fig, ax)

    colours = [RISK_RED if v < 0 else RISK_GREEN for v in df["price_deviation"]]
    bars = ax.bar(df["pool_id"], df["price_deviation"],
                  color=colours, width=0.5, edgecolor="none", alpha=0.9)

    # Reference line at 0
    ax.axhline(0, color=TEXT_SEC, linewidth=0.8, linestyle="-")

    # Value labels
    for bar, val in zip(bars, df["price_deviation"]):
        va = "bottom" if val >= 0 else "top"
        offset = 0.001 if val >= 0 else -0.001
        ax.text(bar.get_x() + bar.get_width() / 2,
                val + offset,
                f"{val:+.3f}",
                ha="center", va=va, fontsize=8.5,
                color=TEXT_PRI, fontweight="semibold")

    ax.set_ylabel("Deviation from $1.00", labelpad=6)
    ax.set_title("Token Price Deviation", fontsize=11, fontweight="bold", pad=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:+.2f}"))
    ax.xaxis.grid(False)
    plt.tight_layout(pad=1.0)
    return fig


# ---------------------------------------------------------------------------
# 5. Network Breakdown  —  Pool Deep Dive page
# ---------------------------------------------------------------------------

def plot_network_breakdown(networks: pd.DataFrame, pool_id: str) -> Figure:
    """
    Horizontal bar chart showing NAV contribution by network for a single pool.
    """
    df = networks[networks["pool_id"] == pool_id][["network", "nav"]].dropna()
    df = df.sort_values("nav", ascending=True)

    fig, ax = plt.subplots(figsize=(6, max(2.5, len(df) * 0.65)))
    _apply_base_style(fig, ax)

    network_colours = {
        "Ethereum":  "#627EEA",
        "Arbitrum":  "#28A0F0",
        "Avalanche": "#E84142",
        "Base":      "#0052FF",
    }
    colours = [network_colours.get(n, "#8B949E") for n in df["network"]]
    bars = ax.barh(df["network"], df["nav"],
                   color=colours, height=0.5, edgecolor="none", alpha=0.9)

    for bar, val in zip(bars, df["nav"]):
        ax.text(
            bar.get_width() + bar.get_width() * 0.01,
            bar.get_y() + bar.get_height() / 2,
            _fmt_millions(val),
            va="center", ha="left", fontsize=8.5,
            color=TEXT_PRI, fontweight="semibold",
        )

    ax.set_xlabel("NAV (Net Asset Value)", labelpad=6)
    ax.set_title(f"{pool_id} — NAV by Network", fontsize=11,
                 fontweight="bold", pad=10)
    ax.set_xlim(0, df["nav"].max() * 1.20)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(_fmt_millions))
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID_COL, linewidth=0.5, linestyle="--", alpha=0.7)
    plt.tight_layout(pad=1.0)
    return fig


# ---------------------------------------------------------------------------
# 6. NAV vs Total Issuance  —  Collateral Health page
# ---------------------------------------------------------------------------

def plot_nav_vs_issuance(pools: pd.DataFrame) -> Figure:
    """
    Grouped bar chart comparing NAV and Total Issuance per pool.
    A healthy pool has NAV ≥ Total Issuance (collateral ratio ≥ 1).
    """
    df = pools[["pool_id", "nav", "total_issuance"]].dropna()

    x     = np.arange(len(df))
    width = 0.38

    fig, ax = plt.subplots(figsize=(7, 3.5))
    _apply_base_style(fig, ax)

    bars_nav = ax.bar(x - width / 2, df["nav"],
                      width=width, label="NAV",
                      color="#2DD4BF", edgecolor="none", alpha=0.9)
    bars_iss = ax.bar(x + width / 2, df["total_issuance"],
                      width=width, label="Total Issuance",
                      color="#94A3B8", edgecolor="none", alpha=0.7)

    ax.set_xticks(x)
    ax.set_xticklabels(df["pool_id"], fontsize=9)
    ax.set_ylabel("Value", labelpad=6)
    ax.set_title("NAV vs Total Issuance", fontsize=11, fontweight="bold", pad=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_millions))

    # Collateral ratio annotation above each pair
    for xi, (_, row) in zip(x, df.iterrows()):
        ratio = row["nav"] / row["total_issuance"] if row["total_issuance"] > 0 else np.nan
        if not np.isnan(ratio):
            col = RISK_GREEN if ratio >= 1.0 else RISK_RED
            ax.text(xi, max(row["nav"], row["total_issuance"]) * 1.03,
                    f"{ratio:.2f}×",
                    ha="center", fontsize=8, color=col, fontweight="bold")

    legend = ax.legend(fontsize=8.5, facecolor=BG_CARD,
                       edgecolor=BORDER, labelcolor=TEXT_PRI)
    plt.tight_layout(pad=1.0)
    return fig


# ---------------------------------------------------------------------------
# 7. 30-Day TVL History  —  Pool Deep Dive / Collateral Health page
# ---------------------------------------------------------------------------

def plot_tvl_history(historical: pd.DataFrame, pool_ids: list[str] | None = None) -> Figure:
    """
    Line chart of 30-day TVL history.
    Pass pool_ids to filter; None plots all pools.
    """
    df = historical.copy()
    if pool_ids:
        df = df[df["pool_id"].isin(pool_ids)]

    df = df.dropna(subset=["date", "tvl"]).sort_values("date")

    fig, ax = plt.subplots(figsize=(8, 3.6))
    _apply_base_style(fig, ax)

    for i, (pool_id, grp) in enumerate(df.groupby("pool_id")):
        colour = _pool_colour(pool_id, i)
        ax.plot(grp["date"], grp["tvl"],
                color=colour, linewidth=2.0, label=pool_id,
                solid_capstyle="round")
        # Endpoint dot
        last = grp.iloc[-1]
        ax.scatter(last["date"], last["tvl"],
                   color=colour, s=40, zorder=5, edgecolors="none")

    ax.set_xlabel("Date", labelpad=6)
    ax.set_ylabel("TVL", labelpad=6)
    ax.set_title("30-Day TVL History", fontsize=11, fontweight="bold", pad=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(_fmt_millions))

    ax.legend(fontsize=8.5, facecolor=BG_CARD,
              edgecolor=BORDER, labelcolor=TEXT_PRI,
              loc="upper left")

    fig.autofmt_xdate(rotation=30, ha="right")
    plt.tight_layout(pad=1.0)
    return fig


# ---------------------------------------------------------------------------
# 8. 30-Day Token Price History  —  Pool Deep Dive page
# ---------------------------------------------------------------------------

def plot_price_history(historical: pd.DataFrame, pool_ids: list[str] | None = None) -> Figure:
    """
    Line chart of 30-day token price history with a $1.00 peg reference line.
    """
    df = historical.copy()
    if pool_ids:
        df = df[df["pool_id"].isin(pool_ids)]

    df = df.dropna(subset=["date", "token_price"]).sort_values("date")

    fig, ax = plt.subplots(figsize=(8, 3.2))
    _apply_base_style(fig, ax)

    # $1.00 peg reference
    ax.axhline(1.0, color=TEXT_SEC, linewidth=0.8,
               linestyle="--", alpha=0.6, label="$1.00 peg")

    for i, (pool_id, grp) in enumerate(df.groupby("pool_id")):
        colour = _pool_colour(pool_id, i)
        ax.plot(grp["date"], grp["token_price"],
                color=colour, linewidth=2.0, label=pool_id,
                solid_capstyle="round")
        last = grp.iloc[-1]
        ax.scatter(last["date"], last["token_price"],
                   color=colour, s=40, zorder=5, edgecolors="none")

    ax.set_xlabel("Date", labelpad=6)
    ax.set_ylabel("Token Price ($)", labelpad=6)
    ax.set_title("30-Day Token Price History", fontsize=11, fontweight="bold", pad=10)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:.3f}"))

    ax.legend(fontsize=8.5, facecolor=BG_CARD,
              edgecolor=BORDER, labelcolor=TEXT_PRI,
              loc="lower left")

    fig.autofmt_xdate(rotation=30, ha="right")
    plt.tight_layout(pad=1.0)
    return fig


# ---------------------------------------------------------------------------
# Smoke-test  (run: python charts.py  from inside visuals/ folder)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, os.path.join(project_root, "data"))
    sys.path.insert(0, os.path.join(project_root, "analysis"))

    try:
        from data.mock_data import get_pools_df, get_network_df, get_historical_df
        from data.processor import process_all
        from analysis.risk_engine import compute_risk
    except ImportError as e:
        print(f"Import error: {e}")
        sys.exit(1)

    raw       = {"pools": get_pools_df(), "networks": get_network_df(),
                 "historical": get_historical_df()}
    processed = process_all(raw)
    risk      = compute_risk(processed.pools, processed.tvl_trends)

    output_dir = os.path.join(project_root, "visuals", "test_output")
    os.makedirs(output_dir, exist_ok=True)

    charts = {
        "01_tvl_bar.png":          plot_tvl_bar(processed.pools),
        "02_risk_gauge_CRDX.png":  plot_risk_gauge(
            risk.scores[risk.scores["pool_id"] == "CRDX"]["risk_score"].iloc[0],
            "CRDX", "DeFi CRDX Token"),
        "03_risk_table.png":       plot_risk_table(risk.summary),
        "04_price_deviation.png":  plot_price_deviation(processed.pools),
        "05_network_JAAA.png":     plot_network_breakdown(processed.networks, "JAAA"),
        "06_nav_vs_issuance.png":  plot_nav_vs_issuance(processed.pools),
        "07_tvl_history.png":      plot_tvl_history(processed.historical),
        "08_price_history.png":    plot_price_history(processed.historical),
    }

    for fname, fig in charts.items():
        path = os.path.join(output_dir, fname)
        fig.savefig(path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        plt.close(fig)
        print(f"  ✅ Saved: {path}")

    print(f"\nAll {len(charts)} charts saved to visuals/test_output/")