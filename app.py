import streamlit as st
import pandas as pd
import os
import time
from rbr_logic import run_analysis, analyze_security
from dbd_logic import analyze_security_dbd
from patterns_logic import analyze_security_patterns, find_retests_rbr, find_retests_dbd

st.set_page_config(page_title="RBR Demand Zones", layout="wide")

st.title("📈 Stocks Patterns Analyzer")
st.markdown(
    "Discover and analyze **technical patterns** for stocks. Use the sidebar to analyze a **single stock** for multiple stocks symbols."
)

# Use bundled scrip master by default
csv_default = os.path.join(os.path.dirname(__file__), "api-scrip-master.csv")
csv_path = csv_default

# Load scrip master if available
scrips = None
symbol_col = None
if os.path.exists(csv_path):
    try:
        scrips = pd.read_csv(csv_path, dtype=str)
        candidates = [
            "SM_SYMBOL_NAME",
            "SEM_SMST_SECURITY_NAME",
            "SM_SYMBOL",
            "SYMBOL",
            "symbol",
        ]
        for c in candidates:
            if c in scrips.columns:
                symbol_col = c
                break
        if symbol_col is None and "SEM_SMST_SECURITY_ID" in scrips.columns:
            scrips["_symbol_label"] = scrips["SEM_SMST_SECURITY_ID"]
            symbol_col = "_symbol_label"
    except Exception:
        scrips = None

# Sidebar controls and branding
st.sidebar.title("Controls")
st.sidebar.markdown("Search & analyze a single stock symbol.")
st.sidebar.caption(f"Scrip master: {os.path.basename(csv_path)}")
# Mode selector: RBR (default) or DBD
mode = st.sidebar.selectbox("Mode", ["RBR", "DBD"], index=0, help="Choose analysis mode: Rally-Base-Rally or Drop-Base-Drop")
# run_batch = st.sidebar.button("▶ Run Batch Analysis", help="Fetch + compute for all securities (may take a while)")

# Single-symbol controls in sidebar
analyze_single_clicked = False
sidebar_sel_label = None
sidebar_selected_id = None
if scrips is None:
    st.sidebar.info("Scrip master CSV not found. Place api-scrip-master.csv next to the app.")
else:
    sb_filtered = scrips[
        (scrips.get("SEM_EXM_EXCH_ID") == "NSE") &
        (scrips.get("SEM_INSTRUMENT_NAME") == "EQUITY") &
        (scrips.get("SEM_SEGMENT") == "E")
    ]
    if sb_filtered.empty:
        st.sidebar.info("No matching NSE/EQUITY/E rows in scrip master.")
    else:
        sb_labels = sb_filtered[symbol_col].fillna(sb_filtered.get("SEM_SMST_SECURITY_ID", "")).astype(str).tolist()
        sb_ids = sb_filtered["SEM_SMST_SECURITY_ID"].astype(str).tolist()
        sb_mapping = dict(zip(sb_labels, sb_ids))

        sb_search = st.sidebar.text_input("Search symbol", value="", help="Type to filter symbols (case-insensitive)")
        if sb_search:
            sb_filtered_labels = [l for l in sb_labels if sb_search.lower() in l.lower()]
        else:
            sb_filtered_labels = sb_labels

        if not sb_filtered_labels:
            st.sidebar.warning("No symbols match your search. Showing full list.")
            sb_filtered_labels = sb_labels

        sidebar_sel_label = st.sidebar.selectbox("Select symbol", options=sb_filtered_labels)
        analyze_single_clicked = st.sidebar.button("Analyze Selected Symbol")
        sidebar_selected_id = sb_mapping.get(sidebar_sel_label)

st.markdown("---")
# Prepare a single display area: center column will show exactly one DataFrame result at a time
col_left, col_center, col_right = st.columns([1, 3, 1])

# Variables to hold what to display in the center
display_df = None
display_title = None

# Left column: batch controls and selection (triggers only)
# with col_left:
#     st.header("Batch")
#     if run_batch:
#         with st.spinner("Fetching + computing (this may take a while)..."):
#             # Two modes: RBR uses existing run_analysis helper which aggregates across CSV.
#             if mode == "RBR":
#                 try:
#                     final = run_analysis(csv_path=csv_path)
#                 except Exception as e:
#                     st.error(f"Error during analysis: {e}")
#                     final = pd.DataFrame()
#             else:
#                 # DBD mode: iterate securities from scrips and call analyze_security_dbd
#                 final = None
#                 all_results = []
#                 if scrips is None:
#                     st.error("Scrip master not available; cannot run DBD batch.")
#                 else:
#                     filtered = scrips[
#                         (scrips.get("SEM_EXM_EXCH_ID") == "NSE") &
#                         (scrips.get("SEM_INSTRUMENT_NAME") == "EQUITY") &
#                         (scrips.get("SEM_SEGMENT") == "E")
#                     ]
#                     security_ids = filtered["SEM_SMST_SECURITY_ID"].dropna().astype(str).unique().tolist()
#                     for sid in security_ids:
#                         try:
#                             df, retests = analyze_security_dbd(sid)
#                         except Exception as e:
#                             print(f"Error fetching/analyzing DBD for {sid}: {e}")
#                             continue
#                         if retests is None or retests.empty:
#                             time.sleep(0.05)
#                             continue
#                         for _, r in retests.iterrows():
#                             out = r.to_dict()
#                             out["security_id"] = sid
#                             row_meta = filtered[filtered["SEM_SMST_SECURITY_ID"] == sid]
#                             if not row_meta.empty:
#                                 first = row_meta.iloc[0]
#                                 out["symbol_name"] = first.get("SEM_SMST_SECURITY_NAME", None) if "SEM_SMST_SECURITY_NAME" in first.index else None
#                             all_results.append(out)
#                         time.sleep(0.05)
#                 if all_results:
#                     final = pd.DataFrame(all_results)

#         if final is None or final.empty:
#             st.warning("No results produced.")
#         else:
#             st.success("✅ Batch complete")
#             # Set the display to show aggregated results in the center
#             display_df = final
#             display_title = "📋 Aggregated Results (batch)"

#             # Provide a selector to inspect a security from the batch; selecting will replace the center display
#             security_list = sorted(final["security_id"].unique().tolist())
#             sel = st.selectbox("Inspect security (from batch results)", options=security_list)
#             if sel:
#                 if mode == "RBR":
#                     df, retests = analyze_security(sel)
#                 else:
#                     df, retests = analyze_security_dbd(sel)
#                 if df is None or df.empty:
#                     st.warning("No data available for selected security.")
#                 else:
#                     display_df = retests if retests is not None else pd.DataFrame()
#                     display_title = f"📋 Detected retests for {sel}"

# Right column: single symbol info and trigger
with col_right:
    st.header("Single")
    st.write("Use the sidebar to choose a symbol and run analysis.")
    if analyze_single_clicked:
        if not sidebar_selected_id:
            st.error("Could not find security id for selected symbol.")
        else:
            with st.spinner(f"Fetching data for {sidebar_sel_label} ({sidebar_selected_id})..."):
                try:
                    if mode == "RBR":
                        df, retests = analyze_security_patterns(sidebar_selected_id, "bullish")
                        # df, retests = analyze_security(sidebar_selected_id)
                    else:
                        df, retests = analyze_security_patterns(sidebar_selected_id, "bearish")
                        # df, retests = analyze_security_dbd(sidebar_selected_id)
                except Exception as e:
                    st.error(f"Error fetching data for {sidebar_selected_id}: {e}")
                    df, retests = None, pd.DataFrame()

            if df is None or df.empty:
                st.warning("No data available for selected security.")
            else:
                st.success("✅ Analysis complete for selected symbol")
                display_df = retests if retests is not None else pd.DataFrame()
                display_title = f"📋 Detected retests for {sidebar_sel_label} ({sidebar_selected_id})"

# Center column: render whichever DataFrame was requested
with col_left:
    st.header("Result")
    if display_df is None:
        st.info("No results to show. Run a batch or analyze a single symbol from the sidebar.")
    else:
        if display_title:
            st.subheader(display_title)
        st.dataframe(display_df)
