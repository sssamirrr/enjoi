import streamlit as st
import pandas as pd
import plotly.express as px
import os
import math

def run_owners_map():
    st.title("Timeshare Owners Map")

    file_path = "Owners home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    df = pd.read_excel(file_path)
    original_count = len(df)

    # We'll store (reason, removed_df) so we can display them afterwards
    filter_removals = []

    def apply_filter(df, mask, reason):
        kept = df[mask]
        removed = df[~mask]
        if len(removed) > 0:
            filter_removals.append((reason, removed.copy()))
        return kept

    # Rename lat/lon if needed
    if "Origin Latitude" in df.columns and "Origin Longitude" in df.columns:
        df.rename(columns={
            "Origin Latitude": "Latitude",
            "Origin Longitude": "Longitude"
        }, inplace=True)

    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    if "Latitude" in df.columns:
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    if "Longitude" in df.columns:
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    st.subheader("Filters")

    # ---------------------------------------------------------
    # State Filter
    # ---------------------------------------------------------
    if "State" in df.columns:
        unique_states = sorted(df["State"].dropna().unique())
        selected_states = st.multiselect("Filter by State(s)", unique_states, default=unique_states)
        mask = df["State"].isin(selected_states)
        df = apply_filter(df, mask, f"State filter: {selected_states}")

    # ---------------------------------------------------------
    # TSW Contract Status Filter
    # ---------------------------------------------------------
    if "TSWcontractStatus" in df.columns:
        status_options = ["Active", "Defaulted", "Both"]
        chosen_status = st.selectbox("Filter by Contract Status", status_options, index=2)
        if chosen_status != "Both":
            mask = (df["TSWcontractStatus"] == chosen_status)
            df = apply_filter(df, mask, f"TSWcontractStatus = {chosen_status}")

    # ---------------------------------------------------------
    # FICO
    # ---------------------------------------------------------
    if "FICO" in df.columns:
        min_fico_val = df["FICO"].min()
        max_fico_val = df["FICO"].max()
        # Round the min down and max up
        fico_min = math.floor(min_fico_val)
        fico_max = math.ceil(max_fico_val)

        fico_range = st.slider("FICO Range", fico_min, fico_max, (fico_min, fico_max))
        mask = (df["FICO"] >= fico_range[0]) & (df["FICO"] <= fico_range[1])
        df = apply_filter(df, mask, f"FICO in [{fico_range[0]}, {fico_range[1]}]")

    # ---------------------------------------------------------
    # Distance in Miles
    # ---------------------------------------------------------
    if "Distance in Miles" in df.columns:
        dist_min_val = df["Distance in Miles"].min()
        dist_max_val = df["Distance in Miles"].max()
        dmin = math.floor(dist_min_val)
        dmax = math.ceil(dist_max_val)

        dist_range = st.slider("Distance in Miles", dmin, dmax, (dmin, dmax))
        mask = (df["Distance in Miles"] >= dist_range[0]) & (df["Distance in Miles"] <= dist_range[1])
        df = apply_filter(df, mask, f"Distance in [{dist_range[0]}, {dist_range[1]}]")

    # ---------------------------------------------------------
    # TSW Payment Amount (fill blanks with 0)
    # ---------------------------------------------------------
    if "TSWpaymentAmount" in df.columns:
        df["TSWpaymentAmount"] = pd.to_numeric(df["TSWpaymentAmount"], errors="coerce").fillna(0)
        pay_min_val = df["TSWpaymentAmount"].min()
        pay_max_val = df["TSWpaymentAmount"].max()
        pmin = math.floor(pay_min_val)
        pmax = math.ceil(pay_max_val)

        pay_range = st.slider("TSW Payment Amount", pmin, pmax, (pmin, pmax))
        mask = (df["TSWpaymentAmount"] >= pay_range[0]) & (df["TSWpaymentAmount"] <= pay_range[1])
        df = apply_filter(df, mask, f"TSWpaymentAmount in [{pay_range[0]}, {pay_range[1]}]")

    # ---------------------------------------------------------
    # Sum of Amount Financed
    # ---------------------------------------------------------
    if "Sum of Amount Financed" in df.columns:
        fin_min_val = df["Sum of Amount Financed"].min()
        fin_max_val = df["Sum of Amount Financed"].max()
        fmin = math.floor(fin_min_val)
        fmax = math.ceil(fin_max_val)

        financed_range = st.slider("Sum of Amount Financed", fmin, fmax, (fmin, fmax))
        mask = (df["Sum of Amount Financed"] >= financed_range[0]) & (df["Sum of Amount Financed"] <= financed_range[1])
        df = apply_filter(df, mask, f"Sum of Amount Financed in [{financed_range[0]}, {financed_range[1]}]")

    # ---------------------------------------------------------
    # Home Value
    # ---------------------------------------------------------
    if "Home Value" in df.columns:
        # Convert, fill NaN => -1
        df["Home Value"] = pd.to_numeric(df["Home Value"], errors="coerce").fillna(-1)
        pos_mask = (df["Home Value"] > 0)
        if pos_mask.any():
            # round down/up for real min & max
            hv_min_val = df.loc[pos_mask, "Home Value"].min()
            hv_max_val = df.loc[pos_mask, "Home Value"].max()
            hvmin = math.floor(hv_min_val)
            hvmax = math.ceil(hv_max_val)
            hv_range = st.slider("Home Value (Positive Only)", float(hvmin), float(hvmax), (float(hvmin), float(hvmax)))
        else:
            hv_range = (0, 0)
            st.info("No positive Home Values found.")

        inc_neg = st.checkbox("Include Non-Numeric (Negative) Home Values?", True)
        # Build mask
        mask_pos = (df["Home Value"] >= hv_range[0]) & (df["Home Value"] <= hv_range[1]) & (df["Home Value"] > 0)
        mask_neg = (df["Home Value"] < 0) & inc_neg
        df = apply_filter(df, mask_pos | mask_neg,
                          f"HomeValue in [{hv_range[0]}, {hv_range[1]}], negative={inc_neg}")

    # ---------------------------------------------------------
    # Display final results
    # ---------------------------------------------------------
    final_count = len(df)
    removed_total = original_count - final_count
    st.write(f"**Filtered Results**: {final_count} row(s) out of {original_count} originally.")
    st.write(f"**Total Removed**: {removed_total} row(s).")

    # Show expansions for removed sets
    if filter_removals:
        st.write("### Rows Removed by Each Filter")
        for (reason, removed_df) in filter_removals:
            if len(removed_df) > 0:
                with st.expander(f"{len(removed_df)} row(s) removed by {reason}"):
                    st.dataframe(removed_df)

    st.dataframe(df.head(20))

    if df.empty:
        st.warning("No data left after filters.")
        return

    # -------------- MAP --------------
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        st.info("No latitude/longitude columns. Cannot map.")
        return

    before_map = len(df)
    map_df = df.dropna(subset=["Latitude","Longitude"])
    exclude_map = before_map - len(map_df)
    if exclude_map > 0:
        st.write(f"Excluded {exclude_map} row(s) missing lat/lon for map display.")

    if map_df.empty:
        st.warning("No rows with valid lat/lon to plot.")
        return

    # Color them by TSWcontractStatus using discrete map
    color_map = {
        "Active": "#90ee90",
        "Defaulted": "#ff9999"
    }
    hover_cols = [
        "OwnerName","Last Name 1","First Name 1","Last Name 2","First Name 2",
        "FICO","Home Value","Distance in Miles","Sum of Amount Financed",
        "TSWpaymentAmount","TSWcontractStatus","Address","City","State","Zip Code"
    ]
    hover_cols = [c for c in hover_cols if c in map_df.columns]

    fig = px.scatter_mapbox(
        map_df,
        lat="Latitude",
        lon="Longitude",
        hover_data=hover_cols,
        color="TSWcontractStatus",
        color_discrete_map=color_map,
        zoom=4,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)

# Streamlit entry
if __name__ == "__main__":
    run_owners_map()
