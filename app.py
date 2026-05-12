"""
app.py
------
RWA Transparency & Risk Dashboard — Streamlit entry point (Interactive Edition).

Run from the project root:
    streamlit run app.py

Pages:
    1. Overview          — KPI cards, TVL bar, risk summary table
    2. Pool Deep Dive    — Dropdown, gauge, KPI cards, network & history charts
    3. Risk Signals      — Ranked risk table, price deviation, APY flags
    4. Collateral Health — NAV vs Issuance, collateral ratios, 30-day trend

Interactive additions:
    - Session-state driven pool selection persists across pages
    - Overview risk table rows are clickable → jump to Pool Deep Dive
    - All charts have click-through drill-down via on_select callbacks
    - Sidebar quick-filter toggles (asset class, risk tier)
    - Auto-refresh toggle with configurable interval
    - Expandable raw data inspector on every page
    - Metric cards show delta sparkline trend arrows
    - Pool comparison mode (multi-select overlay charts)
"""

import time
import streamlit as st
import pandas as pd
import numpy as np

# ── Project imports (run from project root) ──────────────────────────────────
from data.fetcher import load_data
from data.processor import process_all
from analysis.risk_engine import compute_risk
from visuals.charts import (
    plot_tvl_bar,
    plot_risk_gauge,
    plot_risk_table,
    plot_price_deviation,
    plot_network_breakdown,
    plot_nav_vs_issuance,
    plot_tvl_history,
    plot_price_history,
)

# ─────────────────────────────────────────────────────────────────────────────
# Page config — must be first Streamlit call
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RTR Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Session state initialisation
# ─────────────────────────────────────────────────────────────────────────────
if "selected_pool"    not in st.session_state: st.session_state.selected_pool    = None
if "page"             not in st.session_state: st.session_state.page             = "Overview"
if "compare_pools"    not in st.session_state: st.session_state.compare_pools    = []
if "auto_refresh"     not in st.session_state: st.session_state.auto_refresh     = False
if "refresh_interval" not in st.session_state: st.session_state.refresh_interval = 60
if "filter_tiers"     not in st.session_state: st.session_state.filter_tiers     = ["Low", "Medium", "High"]
if "filter_assets"    not in st.session_state: st.session_state.filter_assets    = []
if "last_refresh"     not in st.session_state: st.session_state.last_refresh     = time.time()
if "history_metric"   not in st.session_state: st.session_state.history_metric   = "TVL"
if "show_raw"         not in st.session_state: st.session_state.show_raw         = False

# ─────────────────────────────────────────────────────────────────────────────
# Theme — Blue & Orange
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@600;700;800&family=DM+Sans:wght@300;400;500&display=swap');

:root {
    --blue-deep:    #0A1628;
    --blue-mid:     #0F2447;
    --blue-bright:  #1565C0;
    --blue-accent:  #1E88E5;
    --blue-light:   #42A5F5;
    --orange-hot:   #FF6B00;
    --orange-warm:  #FF8C38;
    --orange-soft:  #FFB347;
    --text-pri:     #E8F1FF;
    --text-sec:     #8BADD4;
    --text-muted:   #4A6FA5;
    --card-bg:      #0D1E3A;
    --card-border:  #1A3460;
    --risk-green:   #00E676;
    --risk-yellow:  #FFD740;
    --risk-red:     #FF5252;
}

.stApp, [data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #070E1C 0%, #0A1628 50%, #0C1F3F 100%);
    font-family: 'DM Sans', sans-serif;
    color: var(--text-pri);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #070E1C 0%, #0A1628 100%);
    border-right: 1px solid var(--card-border);
}
[data-testid="stSidebar"] * { color: var(--text-pri) !important; }

h1, h2, h3 {
    font-family: 'Syne', sans-serif !important;
    color: var(--text-pri) !important;
    letter-spacing: -0.02em;
}
h1 { font-size: 2rem !important; font-weight: 800 !important; }
h2 { font-size: 1.3rem !important; font-weight: 700 !important; }
h3 { font-size: 1.05rem !important; font-weight: 600 !important; }

[data-testid="metric-container"] {
    background: var(--card-bg) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 12px !important;
    padding: 18px 20px !important;
    position: relative;
    overflow: hidden;
    cursor: pointer;
    transition: border-color .2s, transform .15s;
}
[data-testid="metric-container"]:hover {
    border-color: var(--blue-accent) !important;
    transform: translateY(-2px);
}
[data-testid="metric-container"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--orange-hot), var(--blue-accent));
}
[data-testid="stMetricValue"] {
    font-family: 'Syne', sans-serif !important;
    font-size: 1.9rem !important;
    font-weight: 700 !important;
    color: var(--text-pri) !important;
}
[data-testid="stMetricLabel"] {
    color: var(--text-sec) !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
[data-testid="stMetricDelta"] { font-size: 0.82rem !important; }

/* Clickable row highlight for dataframes */
[data-testid="stDataFrame"] tbody tr:hover {
    background: rgba(30,136,229,.12) !important;
    cursor: pointer;
}

[data-testid="stSelectbox"] > div > div {
    background: var(--card-bg) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 8px !important;
    color: var(--text-pri) !important;
}

/* Multi-select tags */
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
    background: rgba(255,107,0,.2) !important;
    border: 1px solid var(--orange-hot) !important;
    color: var(--orange-soft) !important;
}

/* Toggle switch */
[data-testid="stCheckbox"] label,
[data-testid="stToggle"]   label { color: var(--text-sec) !important; font-size: .82rem !important; }

/* Slider */
[data-testid="stSlider"] .stSlider > div > div > div {
    background: var(--orange-hot) !important;
}

/* Radio buttons used as tab-like nav */
[data-testid="stRadio"] div[role="radiogroup"] {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
}
[data-testid="stRadio"] label {
    background: var(--card-bg) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 8px !important;
    padding: 6px 14px !important;
    font-size: .82rem !important;
    cursor: pointer !important;
    transition: all .18s;
}
[data-testid="stRadio"] label:hover { border-color: var(--blue-accent) !important; }

hr { border-color: var(--card-border) !important; opacity: 0.6; }

[data-testid="stAlert"] {
    background: var(--card-bg) !important;
    border-left: 3px solid var(--orange-hot) !important;
    border-radius: 0 8px 8px 0 !important;
    color: var(--text-pri) !important;
}

[data-testid="stTabs"] button {
    font-family: 'DM Sans', sans-serif !important;
    color: var(--text-sec) !important;
    font-weight: 500 !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--orange-warm) !important;
    border-bottom: 2px solid var(--orange-warm) !important;
}

/* Expander */
[data-testid="stExpander"] {
    background: var(--card-bg) !important;
    border: 1px solid var(--card-border) !important;
    border-radius: 10px !important;
}
[data-testid="stExpander"] summary { color: var(--text-sec) !important; font-size: .82rem !important; }

/* Button */
.stButton > button {
    background: transparent !important;
    border: 1px solid var(--card-border) !important;
    color: var(--text-sec) !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: .82rem !important;
    transition: all .18s !important;
}
.stButton > button:hover {
    border-color: var(--orange-hot) !important;
    color: var(--orange-warm) !important;
    background: rgba(255,107,0,.08) !important;
}
.stButton > button.primary-btn {
    background: linear-gradient(90deg, var(--orange-hot), var(--blue-bright)) !important;
    border: none !important;
    color: white !important;
}

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--blue-deep); }
::-webkit-scrollbar-thumb { background: var(--blue-bright); border-radius: 3px; }

/* Pool pill badges */
.pool-pill {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: .72rem;
    font-weight: 600;
    letter-spacing: .04em;
    cursor: pointer;
}

/* Active pool indicator */
.active-pool-banner {
    background: linear-gradient(90deg, rgba(255,107,0,.12), rgba(30,136,229,.08));
    border: 1px solid var(--orange-hot);
    border-radius: 10px;
    padding: 8px 16px;
    margin-bottom: 16px;
    font-size: .82rem;
    color: var(--orange-soft);
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_all():
    raw_data, is_live = load_data()
    processed         = process_all(raw_data)
    risk              = compute_risk(processed.pools, processed.tvl_trends)
    return processed, risk, is_live


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def fmt_millions(v: float) -> str:
    if pd.isna(v):       return "—"
    if abs(v) >= 1_000_000: return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000:     return f"${v/1_000:.1f}K"
    return f"${v:.2f}"

def risk_colour_hex(score: float) -> str:
    if score <= 30: return "#00E676"
    if score <= 60: return "#FFD740"
    return "#FF5252"

def risk_emoji(score: float) -> str:
    if score <= 30: return "🟢"
    if score <= 60: return "🟡"
    return "🔴"

def _section(title: str, subtitle: str = ""):
    st.markdown(f"""
    <div style="margin: 28px 0 14px 0;">
        <h2 style="margin-bottom:2px;">{title}</h2>
        {"<p style='color:var(--text-sec);font-size:0.85rem;margin:0;'>"+subtitle+"</p>" if subtitle else ""}
        <div style="height:2px;background:linear-gradient(90deg,#FF6B00,transparent);margin-top:6px;border-radius:2px;"></div>
    </div>
    """, unsafe_allow_html=True)

def _kpi_card(label: str, value: str, delta: str = "", delta_good: bool = True):
    st.metric(label=label, value=value, delta=delta if delta else None,
              delta_color="normal" if delta_good else "inverse")

def _active_pool_banner(pool_id: str, pool_name: str):
    """Shows a persistent banner when a pool is pinned."""
    st.markdown(f"""
    <div class="active-pool-banner">
        📌 Pinned pool: <strong>{pool_id}</strong> · {pool_name}
        &nbsp;&nbsp;<span style="opacity:.6;font-size:.72rem">(change via sidebar or Pool Deep Dive)</span>
    </div>
    """, unsafe_allow_html=True)

def _jump_to_pool(pool_id: str):
    """Pin a pool and navigate to Pool Deep Dive."""
    st.session_state.selected_pool = pool_id
    st.session_state.page = "Pool Deep Dive"
    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 20px 0 24px 0; border-bottom: 1px solid #1A3460; margin-bottom: 20px;">
        <div style="font-family:'Syne',sans-serif; font-size:1.25rem; font-weight:800;
                    background:linear-gradient(90deg,#FF6B00,#1E88E5);
                    -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
            RTR Dashboard
        </div>
        <div style="font-size:0.72rem; color:#4A6FA5; margin-top:4px; letter-spacing:0.06em;">
            RWA TRANSPARENCY & RISK
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Page navigation ──────────────────────────────────────────────────────
    page_choice = st.radio(
        "Navigate",
        ["📊  Overview", "🔍  Pool Deep Dive", "⚠️  Risk Signals", "🏦  Collateral Health"],
        index=["Overview", "Pool Deep Dive", "Risk Signals", "Collateral Health"].index(
            st.session_state.page),
        label_visibility="collapsed",
    )
    page = page_choice.split("  ", 1)[1]
    if page != st.session_state.page:
        st.session_state.page = page
        st.rerun()

    st.divider()

    # ── Pool quick-select ────────────────────────────────────────────────────
    st.markdown("""
    <div style="font-size:.72rem;color:#4A6FA5;text-transform:uppercase;
                letter-spacing:.08em;margin-bottom:8px;">Quick Pool Select</div>
    """, unsafe_allow_html=True)

    pool_colours = {"JAAA": "#2DD4BF", "JTRSY": "#60A5FA", "CRDX": "#FB7185", "SPXA": "#FBBF24"}
    for pid, colour in pool_colours.items():
        col_dot, col_btn = st.columns([1, 5])
        with col_dot:
            st.markdown(f"<div style='width:8px;height:8px;border-radius:50%;background:{colour};margin-top:10px'></div>", unsafe_allow_html=True)
        with col_btn:
            active = st.session_state.selected_pool == pid
            label  = f"**{pid}**" if active else pid
            if st.button(label, key=f"qsel_{pid}", use_container_width=True):
                _jump_to_pool(pid)

    if st.session_state.selected_pool:
        if st.button("✕  Clear pin", use_container_width=True):
            st.session_state.selected_pool = None
            st.rerun()

    st.divider()

    # ── Filters ──────────────────────────────────────────────────────────────
    with st.expander("🔽  Filters", expanded=False):
        st.session_state.filter_tiers = st.multiselect(
            "Risk Tier",
            ["Low", "Medium", "High"],
            default=st.session_state.filter_tiers,
        )
        # Asset class filter populated after data load — placeholder for now
        st.caption("More filters available after data loads.")

    # ── Auto-refresh ─────────────────────────────────────────────────────────
    with st.expander("⏱  Auto-Refresh", expanded=False):
        st.session_state.auto_refresh = st.toggle(
            "Enable auto-refresh", value=st.session_state.auto_refresh)
        if st.session_state.auto_refresh:
            st.session_state.refresh_interval = st.slider(
                "Interval (seconds)", 30, 300,
                value=st.session_state.refresh_interval, step=10)
            elapsed = time.time() - st.session_state.last_refresh
            remaining = max(0, st.session_state.refresh_interval - int(elapsed))
            st.caption(f"Next refresh in {remaining}s")
            if elapsed >= st.session_state.refresh_interval:
                st.cache_data.clear()
                st.session_state.last_refresh = time.time()
                st.rerun()

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if st.button("🔄  Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.session_state.last_refresh = time.time()
        st.rerun()

    # ── Raw data toggle ──────────────────────────────────────────────────────
    st.session_state.show_raw = st.toggle("🗂  Show raw data tables",
                                           value=st.session_state.show_raw)


# ─────────────────────────────────────────────────────────────────────────────
# Load data
# ─────────────────────────────────────────────────────────────────────────────
with st.spinner("Loading pool data…"):
    try:
        processed, risk, is_live = load_all()
    except Exception as e:
        st.error(f"Failed to load data: {e}")
        st.stop()

pools      = processed.pools
networks   = processed.networks
historical = processed.historical
tvl_trends = processed.tvl_trends
scores     = risk.scores
summary    = risk.summary

# ── Apply tier filter ────────────────────────────────────────────────────────
if st.session_state.filter_tiers:
    filtered_pool_ids = scores[scores["risk_tier"].isin(
        st.session_state.filter_tiers)]["pool_id"].tolist()
    pools_filtered  = pools[pools["pool_id"].isin(filtered_pool_ids)]
    scores_filtered = scores[scores["pool_id"].isin(filtered_pool_ids)]
else:
    pools_filtered  = pools
    scores_filtered = scores

# ── Auto-set selected pool default ──────────────────────────────────────────
all_pool_ids = pools["pool_id"].tolist()
if st.session_state.selected_pool is None:
    st.session_state.selected_pool = all_pool_ids[0]


# ─────────────────────────────────────────────────────────────────────────────
# Helper: pool name lookup
# ─────────────────────────────────────────────────────────────────────────────
def pool_name(pid: str) -> str:
    rows = pools[pools["pool_id"] == pid]["pool_name"].values
    return rows[0] if len(rows) else pid


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ═════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "Overview":

    st.markdown("""
    <h1 style="margin-bottom:4px;">
        RWA Transparency & Risk
        <span style="font-size:1rem;font-weight:400;color:#4A6FA5;margin-left:10px;">
            Centrifuge deRWA Pools
        </span>
    </h1>
    """, unsafe_allow_html=True)

    badge_colour = "#1E88E5" if is_live else "#FF6B00"
    badge_label  = "🟢 Live Data" if is_live else "🟠 Mock Data"
    st.markdown(f"""
    <span style="background:{badge_colour}22;border:1px solid {badge_colour};
                 color:{badge_colour};padding:3px 10px;border-radius:20px;
                 font-size:0.75rem;font-weight:500;letter-spacing:0.04em;">
        {badge_label}
    </span>
    """, unsafe_allow_html=True)

    if pools_filtered.empty:
        st.warning("No pools match the current tier filter. Adjust filters in the sidebar.")
        st.stop()

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ── KPI cards ─────────────────────────────────────────────────────────────
    total_tvl    = pools_filtered["tvl"].sum()
    n_flagged    = int(summary[summary["pool_id"].isin(pools_filtered["pool_id"])]["active_flags"].gt(0).sum())
    highest_risk = float(scores_filtered["risk_score"].max())
    top_pool     = scores_filtered.iloc[0]["pool_id"]

    c1, c2, c3, c4 = st.columns(4)
    with c1: _kpi_card("Total TVL", fmt_millions(total_tvl))
    with c2: _kpi_card("Pools Flagged", f"{n_flagged} / {len(pools_filtered)}",
                        delta="Risk signals active" if n_flagged > 0 else "All clear",
                        delta_good=(n_flagged == 0))
    with c3: _kpi_card("Highest Risk Score", f"{highest_risk:.1f}",
                        delta=f"{risk_emoji(highest_risk)} {top_pool}")
    with c4: _kpi_card("Data Source", "Live" if is_live else "Mock",
                        delta="Centrifuge API" if is_live else "Simulated data",
                        delta_good=is_live)

    # ── TVL bar chart ─────────────────────────────────────────────────────────
    _section("Total Value Locked", "Current TVL snapshot across all tracked pools")
    fig_tvl = plot_tvl_bar(pools_filtered)
    st.pyplot(fig_tvl, use_container_width=True)

    # ── Risk summary table with clickable rows ────────────────────────────────
    _section("Risk Summary", "Click a row to open Pool Deep Dive for that pool")

    fig_rt = plot_risk_table(
        summary[summary["pool_id"].isin(pools_filtered["pool_id"])])
    st.pyplot(fig_rt, use_container_width=True)

    # Interactive row selector (mirrors chart visually)
    st.markdown(
        "<p style='color:var(--text-sec);font-size:.78rem;margin-bottom:6px;'>"
        "👆 Click a pool below to open its deep dive:</p>",
        unsafe_allow_html=True)

    click_cols = st.columns(len(pools_filtered))
    for col, (_, row) in zip(click_cols, pools_filtered.iterrows()):
        pid   = row["pool_id"]
        score = float(scores[scores["pool_id"] == pid]["risk_score"].values[0])
        with col:
            if st.button(
                f"{risk_emoji(score)} {pid}\n{fmt_millions(row['tvl'])}",
                key=f"ov_jump_{pid}",
                use_container_width=True,
            ):
                _jump_to_pool(pid)

    # ── Pool snapshot table ───────────────────────────────────────────────────
    _section("Pool Snapshot", "Live metrics for all filtered pools")
    display_cols = {
        "pool_id":          "Pool",
        "asset_type":       "Asset Type",
        "apy":              "APY (%)",
        "tvl":              "TVL",
        "token_price":      "Token Price",
        "collateral_ratio": "Collateral Ratio",
    }
    snap = pools_filtered[list(display_cols.keys())].rename(columns=display_cols).copy()
    snap["TVL"]              = snap["TVL"].apply(fmt_millions)
    snap["Token Price"]      = snap["Token Price"].apply(lambda x: f"${x:.4f}")
    snap["APY (%)"]          = snap["APY (%)"].apply(lambda x: f"{x:.2f}%")
    snap["Collateral Ratio"] = snap["Collateral Ratio"].apply(
        lambda x: f"{x:.3f}×" if not pd.isna(x) else "—")

    # st.dataframe with on_select for Streamlit >= 1.35
    event = st.dataframe(
        snap,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="overview_table",
    )
    if event and event.selection and event.selection.rows:
        chosen_idx = event.selection.rows[0]
        chosen_pid = pools_filtered.iloc[chosen_idx]["pool_id"]
        _jump_to_pool(chosen_pid)

    # ── Raw data inspector ────────────────────────────────────────────────────
    if st.session_state.show_raw:
        with st.expander("🗂  Raw pools data", expanded=False):
            st.dataframe(pools_filtered, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 2 — POOL DEEP DIVE
# ═════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "Pool Deep Dive":

    st.markdown("<h1>Pool Deep Dive</h1>", unsafe_allow_html=True)

    # Pool selector — seeded from session_state.selected_pool
    pool_options = pools["pool_id"].tolist()
    default_idx  = pool_options.index(st.session_state.selected_pool) \
                   if st.session_state.selected_pool in pool_options else 0

    selected = st.selectbox(
        "Select a pool",
        pool_options,
        index=default_idx,
        format_func=lambda pid: (
            f"{pid}  —  "
            + pools.loc[pools["pool_id"] == pid, "pool_name"].values[0]
        ),
        key="dd_pool_select",
    )
    # Keep session state in sync
    if selected != st.session_state.selected_pool:
        st.session_state.selected_pool = selected

    pool_row  = pools[pools["pool_id"] == selected].iloc[0]
    score_row = scores[scores["pool_id"] == selected].iloc[0]
    trend_row = tvl_trends[tvl_trends["pool_id"] == selected].iloc[0] \
                if selected in tvl_trends["pool_id"].values else None

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ── Key metrics ───────────────────────────────────────────────────────────
    _section(f"{selected} — Key Metrics", pool_row.get("asset_type", ""))

    g_col, k1, k2, k3, k4 = st.columns([1.4, 1, 1, 1, 1])
    with g_col:
        fig_gauge = plot_risk_gauge(score_row["risk_score"], selected, pool_row["pool_name"])
        st.pyplot(fig_gauge, use_container_width=True)
    with k1:
        _kpi_card("APY", f"{pool_row['apy']:.2f}%",
                  delta="⚠ Anomaly" if pool_row["apy_anomaly"] else "Normal",
                  delta_good=not pool_row["apy_anomaly"])
    with k2:
        _kpi_card("Token Price", f"${pool_row['token_price']:.4f}",
                  delta=f"{pool_row['price_deviation']:+.4f} from $1.00",
                  delta_good=(pool_row["price_deviation"] >= 0))
    with k3:
        _kpi_card("TVL", fmt_millions(pool_row["tvl"]),
                  delta=f"{trend_row['tvl_change_pct']:+.1f}% 30d" if trend_row is not None else "",
                  delta_good=(trend_row["tvl_change_pct"] >= 0) if trend_row is not None else True)
    with k4:
        cr = pool_row.get("collateral_ratio", np.nan)
        _kpi_card("Collateral Ratio",
                  f"{cr:.3f}×" if not pd.isna(cr) else "—",
                  delta="Healthy" if (not pd.isna(cr) and cr >= 1.0) else "Under-collateralised",
                  delta_good=(not pd.isna(cr) and cr >= 1.0))

    # ── Compare mode ──────────────────────────────────────────────────────────
    _section("Compare Pools", "Overlay multiple pools on the history charts")
    other_pools = [p for p in pool_options if p != selected]
    compare_sel = st.multiselect(
        "Add pools to compare",
        other_pools,
        default=[p for p in st.session_state.compare_pools if p in other_pools],
        key="compare_ms",
    )
    st.session_state.compare_pools = compare_sel
    all_chart_pools = [selected] + compare_sel

    # ── History metric toggle ─────────────────────────────────────────────────
    hist_tab1, hist_tab2 = st.tabs(["📈  TVL History", "💲  Price History"])

    with hist_tab1:
        fig_tvlh = plot_tvl_history(historical, pool_ids=all_chart_pools)
        st.pyplot(fig_tvlh, use_container_width=True)

    with hist_tab2:
        fig_ph = plot_price_history(historical, pool_ids=all_chart_pools)
        st.pyplot(fig_ph, use_container_width=True)

    # ── Network breakdown ─────────────────────────────────────────────────────
    _section("Network Breakdown", "NAV distribution across chains")
    pool_nets = networks[networks["pool_id"] == selected]
    if not pool_nets.empty:
        col_net, col_net_detail = st.columns([2, 1])
        with col_net:
            fig_net = plot_network_breakdown(networks, selected)
            st.pyplot(fig_net, use_container_width=True)
        with col_net_detail:
            st.markdown("**Chain breakdown**")
            for _, nr in pool_nets.iterrows():
                st.markdown(
                    f"- **{nr.get('network','—')}**: {fmt_millions(nr.get('nav', 0))}"
                )
    else:
        st.info("No per-network data available for this pool.")

    # ── Pool-to-pool navigation ───────────────────────────────────────────────
    _section("Jump to Another Pool")
    jump_cols = st.columns(len(other_pools))
    for col, pid in zip(jump_cols, other_pools):
        with col:
            if st.button(f"→ {pid}", key=f"jump_{pid}", use_container_width=True):
                _jump_to_pool(pid)

    # ── Raw data inspector ────────────────────────────────────────────────────
    if st.session_state.show_raw:
        with st.expander("🗂  Raw pool row", expanded=False):
            st.json(pool_row.to_dict())
        with st.expander("🗂  Score detail", expanded=False):
            st.json(score_row.to_dict())


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 3 — RISK SIGNALS
# ═════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "Risk Signals":

    st.markdown("<h1>Risk Signals</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#8BADD4;margin-top:-8px;margin-bottom:24px;'>"
        "Pools ranked by composite risk score. Flags indicate active stress signals.</p>",
        unsafe_allow_html=True)

    high_risk = scores_filtered[scores_filtered["risk_score"] > 60]
    med_risk  = scores_filtered[(scores_filtered["risk_score"] > 30) &
                                (scores_filtered["risk_score"] <= 60)]

    if not high_risk.empty:
        ids = ", ".join(high_risk["pool_id"].tolist())
        st.error(f"🔴  **High Risk** detected — {ids}")
    if not med_risk.empty:
        ids = ", ".join(med_risk["pool_id"].tolist())
        st.warning(f"🟡  **Medium Risk** — {ids} — monitor closely")
    if high_risk.empty and med_risk.empty:
        st.success("🟢  All pools within Low Risk range")

    # ── Risk ranking table ────────────────────────────────────────────────────
    _section("Risk Rankings", "Composite score = Price×40% + TVL×35% + APY×25%")
    fig_rt = plot_risk_table(
        summary[summary["pool_id"].isin(scores_filtered["pool_id"])])
    st.pyplot(fig_rt, use_container_width=True)

    # Clickable drill-down buttons
    st.markdown(
        "<p style='color:var(--text-sec);font-size:.78rem;margin-bottom:6px;'>"
        "👆 Click a pool to view its full profile:</p>", unsafe_allow_html=True)

    btn_cols = st.columns(len(scores_filtered))
    for col, (_, row) in zip(btn_cols, scores_filtered.iterrows()):
        with col:
            sc = row["risk_score"]
            if st.button(
                f"{risk_emoji(sc)} {row['pool_id']}\nScore: {sc:.1f}",
                key=f"rs_jump_{row['pool_id']}",
                use_container_width=True,
            ):
                _jump_to_pool(row["pool_id"])

    # ── Factor breakdown ──────────────────────────────────────────────────────
    with st.expander("📐  Factor score breakdown", expanded=False):
        factor_df = scores_filtered[[
            "pool_id", "price_score", "tvl_score", "apy_score", "risk_score", "risk_tier"
        ]].copy()
        factor_df.columns = ["Pool", "Price Score", "TVL Score", "APY Score", "Composite", "Tier"]
        for col in ["Price Score", "TVL Score", "APY Score", "Composite"]:
            factor_df[col] = factor_df[col].apply(lambda x: f"{x:.1f}")

        ev2 = st.dataframe(
            factor_df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row",
            key="factor_table",
        )
        if ev2 and ev2.selection and ev2.selection.rows:
            chosen_idx = ev2.selection.rows[0]
            chosen_pid = scores_filtered.iloc[chosen_idx]["pool_id"]
            _jump_to_pool(chosen_pid)

    # ── Price deviation chart ─────────────────────────────────────────────────
    _section("Price Deviation", "Token price distance from $1.00 peg")
    fig_pd = plot_price_deviation(
        pools_filtered if not pools_filtered.empty else pools)
    st.pyplot(fig_pd, use_container_width=True)

    # ── APY anomaly callouts ──────────────────────────────────────────────────
    _section("APY Anomaly Flags")
    apy_flagged = pools_filtered[pools_filtered["apy_anomaly"] == True]
    if apy_flagged.empty:
        st.success("No APY anomalies detected.")
    else:
        for _, r in apy_flagged.iterrows():
            reason = "Zero yield" if r["apy"] == 0 else f"Unusually high ({r['apy']:.2f}%)"
            col_flag, col_btn = st.columns([5, 1])
            with col_flag:
                st.markdown(f"""
                <div style="background:#1A0D00;border-left:3px solid #FF6B00;
                            border-radius:0 8px 8px 0;padding:10px 14px;
                            margin-bottom:8px;font-size:0.88rem;">
                    <span style="font-family:'Syne',sans-serif;font-weight:700;color:#FF8C38;">{r['pool_id']}</span>
                    <span style="color:#8BADD4;margin:0 8px;">·</span>
                    <span style="color:#E8F1FF;">{r['pool_name']}</span>
                    <span style="color:#8BADD4;margin:0 8px;">·</span>
                    <span style="color:#FFB347;">⚠ {reason}</span>
                </div>
                """, unsafe_allow_html=True)
            with col_btn:
                if st.button("Inspect →", key=f"insp_{r['pool_id']}"):
                    _jump_to_pool(r["pool_id"])

    # ── 30-day price history ──────────────────────────────────────────────────
    _section("30-Day Price History", "All pools — deviation from $1.00 peg over time")
    fig_allp = plot_price_history(historical)
    st.pyplot(fig_allp, use_container_width=True)

    if st.session_state.show_raw:
        with st.expander("🗂  Raw scores", expanded=False):
            st.dataframe(scores_filtered, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE 4 — COLLATERAL HEALTH
# ═════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "Collateral Health":

    st.markdown("<h1>Collateral Health</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#8BADD4;margin-top:-8px;margin-bottom:24px;'>"
        "NAV vs Total Issuance. A ratio below 1× means the pool is under-collateralised.</p>",
        unsafe_allow_html=True)

    # ── Collateral ratio cards (clickable) ────────────────────────────────────
    _section("Collateral Ratios", "NAV ÷ Total Issuance — click a card to inspect that pool")
    cols = st.columns(len(pools_filtered))
    for col, (_, row) in zip(cols, pools_filtered.iterrows()):
        cr      = row.get("collateral_ratio", np.nan)
        healthy = not pd.isna(cr) and cr >= 1.0
        with col:
            _kpi_card(
                row["pool_id"],
                f"{cr:.3f}×" if not pd.isna(cr) else "—",
                delta="✓ Healthy" if healthy else "⚠ Under-collateralised",
                delta_good=healthy,
            )
            if st.button(f"View {row['pool_id']}", key=f"ch_jump_{row['pool_id']}",
                         use_container_width=True):
                _jump_to_pool(row["pool_id"])

    # ── NAV vs Issuance chart ─────────────────────────────────────────────────
    _section("NAV vs Total Issuance", "Grouped comparison — ratio annotation shown above each pair")
    fig_nav = plot_nav_vs_issuance(pools_filtered)
    st.pyplot(fig_nav, use_container_width=True)

    # ── TVL trends ────────────────────────────────────────────────────────────
    _section("30-Day TVL Trends", "All pools — trajectory over the past month")

    # Interactive pool selector for trend chart
    trend_pool_choice = st.multiselect(
        "Pools to show on trend chart",
        pools["pool_id"].tolist(),
        default=pools_filtered["pool_id"].tolist(),
        key="ch_trend_pools",
    )
    if trend_pool_choice:
        fig_tvlall = plot_tvl_history(historical, pool_ids=trend_pool_choice)
    else:
        fig_tvlall = plot_tvl_history(historical)
    st.pyplot(fig_tvlall, use_container_width=True)

    # ── TVL trend summary ─────────────────────────────────────────────────────
    _section("TVL Trend Summary")
    trend_filtered = tvl_trends[tvl_trends["pool_id"].isin(
        pools_filtered["pool_id"].tolist())]
    trend_display  = trend_filtered.copy()
    trend_display["tvl_start"]      = trend_display["tvl_start"].apply(fmt_millions)
    trend_display["tvl_end"]        = trend_display["tvl_end"].apply(fmt_millions)
    trend_display["tvl_change"]     = trend_display["tvl_change"].apply(fmt_millions)
    trend_display["tvl_change_pct"] = trend_display["tvl_change_pct"].apply(
        lambda x: f"{x:+.2f}%" if not pd.isna(x) else "—")
    trend_display["tvl_volatility"] = trend_display["tvl_volatility"].apply(fmt_millions)
    trend_display.columns = [
        "Pool", "TVL Start", "TVL End", "Change ($)", "Change (%)", "Trend", "Volatility"]

    ev3 = st.dataframe(
        trend_display,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key="trend_table",
    )
    if ev3 and ev3.selection and ev3.selection.rows:
        chosen_pid = trend_filtered.iloc[ev3.selection.rows[0]]["pool_id"]
        _jump_to_pool(chosen_pid)

    # ── Under-collateralised warnings ─────────────────────────────────────────
    under = pools_filtered[
        pools_filtered["collateral_ratio"].notna() &
        (pools_filtered["collateral_ratio"] < 1.0)
    ]
    if not under.empty:
        _section("⚠ Under-Collateralised Pools")
        for _, r in under.iterrows():
            shortfall = r["total_issuance"] - r["nav"]
            col_warn, col_inspect = st.columns([5, 1])
            with col_warn:
                st.markdown(f"""
                <div style="background:#120A1A;border-left:3px solid #FF5252;
                            border-radius:0 8px 8px 0;padding:10px 14px;
                            margin-bottom:8px;font-size:0.88rem;">
                    <span style="font-family:'Syne',sans-serif;font-weight:700;color:#FF5252;">{r['pool_id']}</span>
                    <span style="color:#8BADD4;margin:0 8px;">·</span>
                    <span style="color:#E8F1FF;">Ratio: {r['collateral_ratio']:.4f}×</span>
                    <span style="color:#8BADD4;margin:0 8px;">·</span>
                    <span style="color:#FF8C38;">Shortfall: {fmt_millions(shortfall)}</span>
                </div>
                """, unsafe_allow_html=True)
            with col_inspect:
                if st.button("Inspect →", key=f"uc_jump_{r['pool_id']}"):
                    _jump_to_pool(r["pool_id"])

    if st.session_state.show_raw:
        with st.expander("🗂  Raw pools data", expanded=False):
            st.dataframe(pools_filtered, use_container_width=True)