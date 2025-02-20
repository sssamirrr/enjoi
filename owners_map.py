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

    # ---------------------------------------------------------------------
    # 1) Convert "Home Value" to numeric; replace non-numeric with -1
    # ---------------------------------------------------------------------
    df["Home Value"] = pd.to_numeric(df["Home Value"], errors="coerce")  # non-numeric -> NaN
    df["Home Value"] = df["Home Value"].fillna(-1)                       # replace NaN with -1

    # ---------------------------------------------------------------------
    # 2) Convert lat/lon to numeric (but do NOT drop missing lat/lon)
    # ---------------------------------------------------------------------
    if "Latitude" in df.columns:
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    if "Longitude" in df.columns:
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # ---------------------------------------------------------------------
    # 3) TSW Contract Status Filter (as example)
    # ---------------------------------------------------------------------
    if "TSWcontractStatus" in df.columns:
        status_options = ["Active", "Defaulted", "Both"]
        chosen_status = st.selectbox("Filter by Contract Status", status_options, index=2)
        if chosen_status != "Both":
            df = df[df["TSWcontractStatus"] == chosen_status]

    # ---------------------------------------------------------------------
    # 4) Build slider for positive Home Value only
    # ---------------------------------------------------------------------
    positive_mask = df["Home Value"] > 0
    if positive_mask.sum() > 0:
        min_val = df.loc[positive_mask, "Home Value"].min()
        max_val = df.loc[positive_mask, "Home Value"].max()
        hv_min, hv_max = st.slider(
            "Home Value (Positive Only)",
            min_value=float(min_val),
            max_value=float(max_val),
            value=(float(min_val), float(max_val)),
            step=1.0
        )
    else:
        hv_min, hv_max = 0, 0
        st.info("No positive home values found, so numeric slider is not applicable.")

    # ---------------------------------------------------------------------
    # 5) Checkbox to include negative (non-numeric) values
    # ---------------------------------------------------------------------
    include_negative = st.checkbox("Include Non-Numeric (Negative) Home Values?", value=True)

    # ---------------------------------------------------------------------
    # 6) Final Filter Logic
    # ---------------------------------------------------------------------
    # Keep rows that:
    #  1) Have Home Value within [hv_min, hv_max] if > 0
    # OR
    #  2) Are negative (originally non-numeric) if user checked
    df_filtered = df[
        (
            (df["Home Value"] > 0)
            & (df["Home Value"] >= hv_min)
            & (df["Home Value"] <= hv_max)
        )
        |
        (
            (df["Home Value"] < 0) & include_negative
        )
    ]

    st.write(f"**Filtered Rows:** {len(df_filtered)}")
    st.dataframe(df_filtered.head(20))

    # ---------------------------------------------------------------------
    # 7) Build a subset for the map: only rows with valid lat/lon
    # ---------------------------------------------------------------------
    # We do NOT remove these rows from df_filtered entirely,
    # but only from what we pass to the map.
    if "Latitude" not in df_filtered.columns or "Longitude" not in df_filtered.columns:
        st.info("Latitude/Longitude columns not found. No map to display.")
        return

    map_df = df_filtered.dropna(subset=["Latitude", "Longitude"]).copy()
    if map_df.empty:
        st.info("No valid lat/lon in the filtered dataset. No map to display.")
        return

    # ---------------------------------------------------------------------
    # 8) Plot the map
    # ---------------------------------------------------------------------
    # Optional: color code by TSWcontractStatus
    if "TSWcontractStatus" in map_df.columns:
        def pick_color(status):
            if status == "Active":
                return "green"
            elif status == "Defaulted":
                return "red"
            return "blue"
        map_df["Color"] = map_df["TSWcontractStatus"].apply(pick_color)
    else:
        map_df["Color"] = "blue"

    hover_cols = [
        c for c in [
            "OwnerName", "Home Value", "TSWcontractStatus", "FICO",
            "Distance in Miles", "Address", "City", "State", "Zip Code"
        ]
        if c in map_df.columns
    ]

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
    fig.update_layout(margin={"r":0, "t":0, "l":0, "b":0})
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_owners_map()
