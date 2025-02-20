import streamlit as st
import pandas as pd
import plotly.express as px
import os

def run_owners_map():
    st.title("Timeshare Owners Map")
    file_path = "Owners enriched with home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    df = pd.read_excel(file_path)
    original_count = len(df)  # track how many we start with

    # A list to store filter summary messages
    filter_messages = []

    # Helper function to track how many rows a given filter removes
    def apply_filter(df, mask, description):
        old_len = len(df)
        filtered = df[mask]
        removed = old_len - len(filtered)
        if removed > 0:
            filter_messages.append(f"- {removed} row(s) removed by {description}")
        return filtered

    # Rename lat/lon if needed
    if "Origin Latitude" in df.columns and "Origin Longitude" in df.columns:
        df.rename(columns={
            "Origin Latitude": "Latitude",
            "Origin Longitude": "Longitude"
        }, inplace=True)

    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    # Convert lat/lon to numeric but do NOT drop from df
    if "Latitude" in df.columns:
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    if "Longitude" in df.columns:
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    st.subheader("Filters")

    # ------------------------- 
    # State Filter
    # -------------------------
    if "State" in df.columns:
        unique_states = sorted(df["State"].dropna().unique())
        selected_states = st.multiselect("Filter by State(s)", unique_states, default=unique_states)
        mask = df["State"].isin(selected_states)
        df = apply_filter(df, mask, f"State filter: {selected_states}")

    # -------------------------
    # TSW Contract Status Filter
    # -------------------------
    if "TSWcontractStatus" in df.columns:
        status_options = ["Active", "Defaulted", "Both"]
        chosen_status = st.selectbox("Filter by Contract Status", status_options, index=2)
        if chosen_status != "Both":
            mask = (df["TSWcontractStatus"] == chosen_status)
            df = apply_filter(df, mask, f"TSW Status = {chosen_status}")

    # -------------------------
    # FICO
    # -------------------------
    if "FICO" in df.columns:
        min_fico = df["FICO"].min()
        max_fico = df["FICO"].max()
        fico_range = st.slider("FICO Range", int(min_fico), int(max_fico), (int(min_fico), int(max_fico)))
        mask = (df["FICO"] >= fico_range[0]) & (df["FICO"] <= fico_range[1])
        df = apply_filter(df, mask, f"FICO in [{fico_range[0]}, {fico_range[1]}]")

    # -------------------------
    # Distance in Miles
    # -------------------------
    if "Distance in Miles" in df.columns:
        min_dist = df["Distance in Miles"].min()
        max_dist = df["Distance in Miles"].max()
        dist_range = st.slider("Distance in Miles", int(min_dist), int(max_dist), (int(min_dist), int(max_dist)))
        mask = (df["Distance in Miles"] >= dist_range[0]) & (df["Distance in Miles"] <= dist_range[1])
        df = apply_filter(df, mask, f"Distance in [{dist_range[0]}, {dist_range[1]}]")

    # -------------------------
    # TSW Payment Amount (fill NaN with 0)
    # -------------------------
    if "TSWpaymentAmount" in df.columns:
        # Make sure TSWpaymentAmount is numeric; fill blanks with 0
        df["TSWpaymentAmount"] = pd.to_numeric(df["TSWpaymentAmount"], errors="coerce").fillna(0)

        min_payment = df["TSWpaymentAmount"].min()
        max_payment = df["TSWpaymentAmount"].max()
        payment_range = st.slider("TSW Payment Amount",
                                  int(min_payment), int(max_payment),
                                  (int(min_payment), int(max_payment)))
        mask = (df["TSWpaymentAmount"] >= payment_range[0]) & (df["TSWpaymentAmount"] <= payment_range[1])
        df = apply_filter(df, mask, f"TSW Payment in [{payment_range[0]}, {payment_range[1]}]")

    # -------------------------
    # Sum of Amount Financed
    # -------------------------
    if "Sum of Amount Financed" in df.columns:
        min_financed = df["Sum of Amount Financed"].min()
        max_financed = df["Sum of Amount Financed"].max()
        financed_range = st.slider("Sum of Amount Financed",
                                   int(min_financed), int(max_financed),
                                   (int(min_financed), int(max_financed)))
        mask = (df["Sum of Amount Financed"] >= financed_range[0]) & (df["Sum of Amount Financed"] <= financed_range[1])
        df = apply_filter(df, mask, f"Amount Financed in [{financed_range[0]}, {financed_range[1]}]")

    # -------------------------
    # Home Value
    # -------------------------
    if "Home Value" in df.columns:
        df["Home Value"] = pd.to_numeric(df["Home Value"], errors="coerce").fillna(-1)
        pos_mask = df["Home Value"] > 0
        if pos_mask.sum() > 0:
            hv_min = df.loc[pos_mask, "Home Value"].min()
            hv_max = df.loc[pos_mask, "Home Value"].max()
            hv_range = st.slider("Home Value (Positive Only)",
                                 float(hv_min), float(hv_max),
                                 (float(hv_min), float(hv_max)))
        else:
            hv_range = (0, 0)
            st.info("No positive Home Values found.")
        include_negative = st.checkbox("Include Non-Numeric (Negative) Home Values?", True)

        mask_positive = (df["Home Value"] > 0) & (df["Home Value"] >= hv_range[0]) & (df["Home Value"] <= hv_range[1])
        mask_negative = (df["Home Value"] < 0) & include_negative
        combined = mask_positive | mask_negative
        df = apply_filter(df, combined, f"Home Value in [{hv_range[0]}, {hv_range[1]}], negative={include_negative}")

    # -------------------------------------------------
    # SHOW FINAL FILTER RESULTS
    # -------------------------------------------------
    final_count = len(df)
    removed_total = original_count - final_count
    st.write(f"**Filtered Results**: {final_count} row(s) out of {original_count} originally.")
    st.write(f"**Total Removed**: {removed_total} row(s).")
    if filter_messages:
        st.write("**Filter Breakdown**:")
        for msg in filter_messages:
            st.write(msg)

    st.dataframe(df.head(30))

    if df.empty:
        st.warning("No data left after filters.")
        return

    # -------------------------------------------------
    # PLOT THE MAP
    # -------------------------------------------------
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        st.info("No 'Latitude'/'Longitude' columns to map.")
        return

    before_map = len(df)
    map_df = df.dropna(subset=["Latitude","Longitude"])
    excluded_map = before_map - len(map_df)
    if excluded_map > 0:
        st.write(f"Excluded {excluded_map} row(s) with missing Lat/Lon for the map plot.")

    if map_df.empty:
        st.warning("No rows with valid lat/lon to plot.")
        return

    # Use LIGHT GREEN (#90ee90) for "Active" and LIGHT RED (#ff9999) for "Defaulted"
    def pick_color(status):
        if status == "Active":
            return "#90ee90"  # light green
        elif status == "Defaulted":
            return "#ff9999"  # light red
        else:
            return "blue"

    if "TSWcontractStatus" in map_df.columns:
        map_df["Color"] = map_df["TSWcontractStatus"].apply(pick_color)
    else:
        map_df["Color"] = "blue"

    hover_cols = [
        "OwnerName", "Last Name 1", "First Name 1", "Last Name 2", "First Name 2",
        "FICO", "Home Value", "Distance in Miles", "Sum of Amount Financed",
        "TSWpaymentAmount", "TSWcontractStatus", "Address", "City", "State", "Zip Code"
    ]
    hover_cols = [c for c in hover_cols if c in map_df.columns]

    fig = px.scatter_mapbox(
        map_df,
        lat="Latitude",
        lon="Longitude",
        hover_data=hover_cols,
        color="Color",
        zoom=4,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_owners_map()
