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

    # Rename "Origin Latitude"/"Origin Longitude" => "Latitude"/"Longitude"
    if "Origin Latitude" in df.columns and "Origin Longitude" in df.columns:
        df.rename(columns={
            "Origin Latitude": "Latitude",
            "Origin Longitude": "Longitude"
        }, inplace=True)

    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    # Check if lat/lon columns exist
    # (We won't drop them from df, but we will skip missing lat/lon at map time)
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
        selected_states = st.multiselect(
            "Filter by State(s)", 
            unique_states, 
            default=unique_states
        )
        df = df[df["State"].isin(selected_states)]

    # -------------------------
    # TSW Contract Status Filter
    # -------------------------
    if "TSWcontractStatus" in df.columns:
        status_options = ["Active", "Defaulted", "Both"]
        selected_status = st.selectbox("Filter by Contract Status", status_options, index=2)
        if selected_status != "Both":
            df = df[df["TSWcontractStatus"] == selected_status]

    # -------------------------
    # FICO Range
    # -------------------------
    if "FICO" in df.columns:
        min_fico = df["FICO"].min()
        max_fico = df["FICO"].max()
        fico_range = st.slider(
            "FICO Range",
            int(min_fico),
            int(max_fico),
            (int(min_fico), int(max_fico))
        )
        df = df[(df["FICO"] >= fico_range[0]) & (df["FICO"] <= fico_range[1])]

    # -------------------------
    # Distance in Miles
    # -------------------------
    if "Distance in Miles" in df.columns:
        min_dist = df["Distance in Miles"].min()
        max_dist = df["Distance in Miles"].max()
        dist_range = st.slider(
            "Distance in Miles",
            int(min_dist),
            int(max_dist),
            (int(min_dist), int(max_dist))
        )
        df = df[(df["Distance in Miles"] >= dist_range[0]) & (df["Distance in Miles"] <= dist_range[1])]

    # -------------------------
    # TSWpaymentAmount
    # -------------------------
    if "TSWpaymentAmount" in df.columns:
        min_payment = df["TSWpaymentAmount"].min()
        max_payment = df["TSWpaymentAmount"].max()
        payment_range = st.slider(
            "TSW Payment Amount",
            int(min_payment),
            int(max_payment),
            (int(min_payment), int(max_payment))
        )
        df = df[(df["TSWpaymentAmount"] >= payment_range[0]) & (df["TSWpaymentAmount"] <= payment_range[1])]

    # -------------------------
    # Sum of Amount Financed
    # -------------------------
    if "Sum of Amount Financed" in df.columns:
        min_financed = df["Sum of Amount Financed"].min()
        max_financed = df["Sum of Amount Financed"].max()
        financed_range = st.slider(
            "Sum of Amount Financed",
            int(min_financed),
            int(max_financed),
            (int(min_financed), int(max_financed))
        )
        df = df[(df["Sum of Amount Financed"] >= financed_range[0]) & (df["Sum of Amount Financed"] <= financed_range[1])]

    # -------------------------
    # Home Value: convert to numeric, slider for positives, checkbox for negative
    # -------------------------
    if "Home Value" in df.columns:
        df["Home Value"] = pd.to_numeric(df["Home Value"], errors="coerce")  # non-numeric -> NaN
        df["Home Value"] = df["Home Value"].fillna(-1)  # replace NaN with -1
        pos_mask = df["Home Value"] > 0
        if pos_mask.sum() > 0:
            hv_min = df.loc[pos_mask, "Home Value"].min()
            hv_max = df.loc[pos_mask, "Home Value"].max()
            hv_range = st.slider("Home Value (Positive Only)", float(hv_min), float(hv_max), (float(hv_min), float(hv_max)))
        else:
            hv_range = (0, 0)
            st.info("No positive Home Values found.")
        include_negative = st.checkbox("Include Non-Numeric (Negative) Home Values?", True)

        df = df[
            (
                (df["Home Value"] > 0) &
                (df["Home Value"] >= hv_range[0]) &
                (df["Home Value"] <= hv_range[1])
            )
            |
            (
                (df["Home Value"] < 0) & include_negative
            )
        ]

    st.write(f"**Filtered Results**: {len(df)} row(s).")
    st.dataframe(df.head(30))

    # -------------------------
    # Plot the map if not empty
    # -------------------------
    if df.empty:
        st.warning("No data left after filters.")
        return

    # For the map, only rows with valid lat/lon
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        st.info("Latitude/Longitude columns not found. No map to display.")
        return

    map_df = df.dropna(subset=["Latitude","Longitude"]).copy()
    if map_df.empty:
        st.info("No valid lat/lon in filtered dataset. No map to display.")
        return

    # Color by TSWcontractStatus if it exists
    if "TSWcontractStatus" in map_df.columns:
        def pick_color(status):
            if status == "Active":
                return "green"
            elif status == "Defaulted":
                return "red"
            else:
                return "blue"
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
        color="Color",
        hover_data=hover_cols,
        zoom=4,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_owners_map()
