import streamlit as st
import pandas as pd
import os
# import time
# from rbr_logic import run_analysis, analyze_security
# from dbd_logic import analyze_security_dbd
from patterns_logic import analyze_security_patterns, find_retests_rbr, find_retests_dbd

st.set_page_config(page_title="Supply & Demand Pattern Analyzer", layout="wide")

st.title("📈 Stocks Patterns Analyzer")
st.markdown(
    "Discover and analyze **technical patterns** for stocks. "
    "Use the sidebar to configure thresholds and analyze a single stock."
)

# --- Load CSV for symbol lookup ---
csv_default = os.path.join(os.path.dirname(__file__), "api-scrip-master.csv")
csv_path = csv_default

scrips = None
symbol_col = None
if os.path.exists(csv_path):
    try:
        scrips = pd.read_csv(csv_path, dtype=str)
        candidates = ["SM_SYMBOL_NAME", "SEM_SMST_SECURITY_NAME", "SM_SYMBOL", "SYMBOL", "symbol"]
        for c in candidates:
            if c in scrips.columns:
                symbol_col = c
                break
        if symbol_col is None and "SEM_SMST_SECURITY_ID" in scrips.columns:
            scrips["_symbol_label"] = scrips["SEM_SMST_SECURITY_ID"]
            symbol_col = "_symbol_label"
    except Exception:
        scrips = None

# --- Sidebar Controls ---
st.sidebar.title("Controls")
st.sidebar.markdown("Search & analyze a single stock symbol.")
st.sidebar.caption(f"Scrip master: {os.path.basename(csv_path)}")

# Pattern mode selection
mode = st.sidebar.selectbox("Mode", ["RBR", "DBD", "RBD", "DBR"], index=0, help="Choose pattern type to analyze")

# --- Add user-adjustable thresholds ---
st.sidebar.markdown("### Candle Thresholds")
body_percent = st.sidebar.slider(
    "Minimum Body %", 10, 100, 65,
    help="Minimum body percentage of the total candle length"
)
wick_percent = st.sidebar.slider(
    "Maximum Wick %", 0, 100, 35,
    help="Maximum wick (upper + lower) percentage of the total candle length"
)

# Max Base Candles
max_bases = st.sidebar.slider(
    "Maximum Base Candles",
    min_value=1,
    max_value=4,
    value=4,
    step=1,
    help="Maximum number of base candles allowed between impulse candles"
)

# --- Symbol Search ---
analyze_single_clicked = False
sidebar_sel_label = None
sidebar_selected_id = None

if scrips is None:
    st.sidebar.info("Scrip master CSV not found.")
else:
    sb_filtered = scrips[
        (scrips.get("SEM_EXM_EXCH_ID") == "NSE") &
        (scrips.get("SEM_INSTRUMENT_NAME") == "EQUITY") &
        (scrips.get("SEM_SEGMENT") == "E") &
        (scrips.get("SEM_EXCH_INSTRUMENT_TYPE") == "ES")
    ]
    sb_labels = sb_filtered[symbol_col].astype(str).tolist()
    sb_ids = sb_filtered["SEM_SMST_SECURITY_ID"].astype(str).tolist()
    sb_mapping = dict(zip(sb_labels, sb_ids))

    sb_search = st.sidebar.text_input("Search symbol", value="")
    if sb_search:
        sb_filtered_labels = [l for l in sb_labels if sb_search.lower() in l.lower()]
    else:
        sb_filtered_labels = sb_labels

    sidebar_sel_label = st.sidebar.selectbox("Select symbol", options=sb_filtered_labels)
    analyze_single_clicked = st.sidebar.button("Analyze Selected Symbol")
    sidebar_selected_id = sb_mapping.get(sidebar_sel_label)

st.markdown("---")
col_left, col_center, col_right = st.columns([1, 3, 1])

display_df = None
display_title = None

with col_right:
    st.header("Single Analysis")
    if analyze_single_clicked:
        if not sidebar_selected_id:
            st.error("Could not find security id for selected symbol.")
        else:
            with st.spinner(f"Analyzing {sidebar_sel_label} ({sidebar_selected_id})..."):
                try:
                    body_threshold = body_percent / 100.0
                    wick_threshold = wick_percent / 100.0

                    if mode == "RBR":
                        df, retests = analyze_security_patterns(sidebar_selected_id, "bullish", body_threshold, wick_threshold, max_bases)
                    elif mode == "DBD":
                        df, retests = analyze_security_patterns(sidebar_selected_id, "bearish", body_threshold, wick_threshold, max_bases)
                    elif mode == "RBD":
                        df, retests = analyze_security_patterns(sidebar_selected_id, "rbd", body_threshold, wick_threshold, max_bases)
                    elif mode == "DBR":
                        df, retests = analyze_security_patterns(sidebar_selected_id, "dbr", body_threshold, wick_threshold, max_bases)
                    else:
                        df, retests = None, pd.DataFrame()
                except Exception as e:
                    st.error(f"Error fetching data for {sidebar_selected_id}: {e}")
                    df, retests = None, pd.DataFrame()

            if df is None or df.empty:
                st.warning("No data available for selected security.")
            else:
                st.success("✅ Analysis complete")
                display_df = retests if retests is not None else pd.DataFrame()
                display_title = f"📋 Detected zones for {sidebar_sel_label}"
                st.caption(f"Using thresholds: Body ≥ {body_percent}% | Wick ≤ {wick_percent}%")

with col_left:
    st.header("Result")
    if display_df is None:
        st.info("No results yet. Choose a symbol and click analyze.")
    else:
        if display_title:
            st.subheader(display_title)
        st.dataframe(display_df)
