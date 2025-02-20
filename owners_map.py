import streamlit as st
import pandas as pd
import plotly.express as px
import os

def run_owners_map():
    st.title("Timeshare Owners Map")

    file_path = "Owners home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    # Read the spreadsheet
    df = pd.read_excel(file_path)
    original_count = len(df)

    # We'll store (reason, removed_df) in a list,
    # so we can show them at the end in clickable expanders.
    filter_removals = []

    def apply_filter(df, mask, reason):
        """Split DataFrame into kept vs removed, store the removed for later display."""
        kept_df = df[mask]
        removed_df = df[~mask]
        removed_count = len(removed_df)
        if removed_count > 0:
            filter_removals.append((reason, removed_df.copy()))
        return kept_df

    # Rename lat/lon if needed
    if "Origin Latitude" in df.columns and "Origin Longitude" in df.columns:
        df.rename(columns={"Origin Latitude": "Latitude",
                           "Origin Longitude": "Longitude"}, 
                  inplace=True)

    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    # Convert lat/lon but do NOT drop rows yet
    if "Latitude" in df.columns:
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    if "Longitude" in df.columns:
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    st.subheader("Filters")

    # 1) State Filter
    if "State" in df.columns:
        unique_states = sorted(df["State"].dropna().unique())
        selected_states = st.multiselect("Filter by State(s)", unique_states, default=unique_states)
        mask = df["State"].isin(selected_states)
        df = apply_filter(df, mask, f"State filter: {selected_states}")

    # 2) TSW Contract Status
    if "TSWcontractStatus" in df.columns:
        status_opts = ["Active", "Defaulted", "Both"]
        chosen_status = st.selectbox("Filter by Contract Status", status_opts, index=2)
        if chosen_status != "Both":
            mask = (df["TSWcontractStatus"] == chosen_status)
            df = apply_filter(df, mask, f"TSWcontractStatus = {chosen_status}")

    # 3) FICO
    if "FICO" in df.columns:
        min_fico = df["FICO"].min()
        max_fico = df["FICO"].max()
        fico_range = st.slider("FICO Range", int(min_fico), int(max_fico), (int(min_fico), int(max_fico)))
        mask = (df["FICO"] >= fico_range[0]) & (df["FICO"] <= fico_range[1])
        df = apply_filter(df, mask, f"FICO in [{fico_range[0]}, {fico_range[1]}]")

    # 4) Distance in Miles
    if "Distance in Miles" in df.columns:
        d_min = df["Distance in Miles"].min()
        d_max = df["Distance in Miles"].max()
        dist_range = st.slider("Distance in Miles", int(d_min), int(d_max), (int(d_min), int(d_max)))
        mask = (df["Distance in Miles"] >= dist_range[0]) & (df["Distance in Miles"] <= dist_range[1])
        df = apply_filter(df, mask, f"Distance in [{dist_range[0]}, {dist_range[1]}]")

    # 5) TSW Payment Amount (fill NaN with 0)
    if "TSWpaymentAmount" in df.columns:
        df["TSWpaymentAmount"] = pd.to_numeric(df["TSWpaymentAmount"], errors="coerce").fillna(0)
        min_pay = df["TSWpaymentAmount"].min()
        max_pay = df["TSWpaymentAmount"].max()
        pay_range = st.slider("TSW Payment Amount", int(min_pay), int(max_pay),
                              (int(min_pay), int(max_pay)))
        mask = (df["TSWpaymentAmount"] >= pay_range[0]) & (df["TSWpaymentAmount"] <= pay_range[1])
        df = apply_filter(df, mask, f"TSWpaymentAmount in [{pay_range[0]}, {pay_range[1]}]")

    # 6) Sum of Amount Financed
    if "Sum of Amount Financed" in df.columns:
        fmin = df["Sum of Amount Financed"].min()
        fmax = df["Sum of Amount Financed"].max()
        financed_range = st.slider("Sum of Amount Financed", int(fmin), int(fmax),
                                   (int(fmin), int(fmax)))
        mask = (df["Sum of Amount Financed"] >= financed_range[0]) & (df["Sum of Amount Financed"] <= financed_range[1])
        df = apply_filter(df, mask, f"Sum of Amount Financed in [{financed_range[0]}, {financed_range[1]}]")

    # 7) Home Value
    if "Home Value" in df.columns:
        df["Home Value"] = pd.to_numeric(df["Home Value"], errors="coerce").fillna(-1)
        pos_mask = (df["Home Value"] > 0)
        if pos_mask.any():
            hv_min = df.loc[pos_mask, "Home Value"].min()
            hv_max = df.loc[pos_mask, "Home Value"].max()
            hv_range = st.slider("Home Value (Positive Only)",
                                 float(hv_min), float(hv_max),
                                 (float(hv_min), float(hv_max)))
        else:
            hv_range = (0, 0)
            st.info("No positive home values found.")

        inc_neg = st.checkbox("Include Non-Numeric (Negative) Home Values?", True)
        mask_pos = (df["Home Value"] >= hv_range[0]) & (df["Home Value"] <= hv_range[1]) & (df["Home Value"] > 0)
        mask_neg = (df["Home Value"] < 0) & inc_neg
        df = apply_filter(df, mask_pos | mask_neg,
                          f"HomeValue in [{hv_range[0]}, {hv_range[1]}], negative={inc_neg}")

    # Show final results
    final_count = len(df)
    removed_total = original_count - final_count
    st.write(f"**Filtered Results**: {final_count} row(s) out of {original_count} originally.")
    st.write(f"**Total Removed**: {removed_total} row(s).")

    # Now show expanders for each filter's removed set
    if filter_removals:
        st.write("### Rows Removed at Each Filter Step")
        for reason, removed_df in filter_removals:
            if len(removed_df) > 0:
                with st.expander(f"{len(removed_df)} row(s) removed by {reason}"):
                    st.dataframe(removed_df)

    st.dataframe(df.head(20))

    if df.empty:
        st.warning("No data left after filters.")
        return

    # MAP
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        st.info("No lat/lon columns. Cannot map.")
        return

    before_map = len(df)
    map_df = df.dropna(subset=["Latitude","Longitude"])
    exclude_map = before_map - len(map_df)
    if exclude_map > 0:
        st.write(f"Excluded {exclude_map} row(s) missing lat/lon for the map.")

    if map_df.empty:
        st.warning("No valid lat/lon for map.")
        return

    # Let's color them by discrete statuses using color_discrete_map
    color_map = {
        "Active": "#90ee90",     # Light green
        "Defaulted": "#ff9999", # Light red
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
        color_discrete_map=color_map,  # any statuses not in the dict => fallback color
        zoom=4,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_owners_map()
