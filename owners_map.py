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
    # 2) No dropping rows for lat/lon; keep them all (user doesn't want drop)
    # ---------------------------------------------------------------------
    # If you used to do dropna(subset=["Latitude","Longitude"]), remove it.
    # df.dropna(subset=["Latitude", "Longitude"], inplace=True)  # <- Removed

    # Just convert lat/lon to numeric in case they're strings
    if "Latitude" in df.columns:
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    if "Longitude" in df.columns:
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # ---------------------------------------------------------------------
    # 3) Filter TSWcontractStatus (example), or any other filters first
    # ---------------------------------------------------------------------
    if "TSWcontractStatus" in df.columns:
        status_options = ["Active", "Defaulted", "Both"]
        chosen_status = st.selectbox("Filter by Contract Status", status_options, index=2)
        if chosen_status != "Both":
            df = df[df["TSWcontractStatus"] == chosen_status]

    # ---------------------------------------------------------------------
    # 4) Build slider for positive Home Values only (i.e. > 0)
    # ---------------------------------------------------------------------
    # Identify all positive rows
    positive_mask = df["Home Value"] > 0
    if positive_mask.sum() > 0:
        min_val = df.loc[positive_mask, "Home Value"].min()
        max_val = df.loc[positive_mask, "Home Value"].max()
        hv_min, hv_max = st.slider(
            "Home Value (Positive Only)",
            min_value=float(min_val),
            max_value=float(max_val),
            value=(float(min_val), float(max_val))
        )
    else:
        # No positive values found, set slider range to (0,0)
        hv_min, hv_max = 0, 0
        st.info("No positive home values found, so numeric slider is not applicable.")

    # ---------------------------------------------------------------------
    # 5) Checkbox to include negative (originally non-numeric) values
    # ---------------------------------------------------------------------
    include_negative = st.checkbox("Include Non-Numeric (Negative) Home Values?", value=True)

    # ---------------------------------------------------------------------
    # 6) Final Filter Logic
    #    - Keep rows that have Home Value within [hv_min, hv_max] if > 0
    #    - OR keep rows that are negative if checkbox is checked
    # ---------------------------------------------------------------------
    df_filtered = df[
        (
            # (Positive HV rows) AND within slider range
            (df["Home Value"] > 0) &
            (df["Home Value"] >= hv_min) &
            (df["Home Value"] <= hv_max)
        )
        |
        (
            # Negative HV rows
            (df["Home Value"] < 0) & (include_negative)
        )
    ]

    st.write(f"**Filtered Rows**: {len(df_filtered)}")
    st.dataframe(df_filtered.head(20))

    # ---------------------------------------------------------------------
    # 7) Plot a Map (optional) if lat/lon exist
    # ---------------------------------------------------------------------
    if df_filtered.empty:
        st.warning("No data left after filters.")
        return

    if {"Latitude", "Longitude"}.issubset(df_filtered.columns):
        # If TSWcontractStatus is present, color-coded for demonstration
        if "TSWcontractStatus" in df_filtered.columns:
            def pick_color(status):
                if status == "Active":
                    return "green"
                elif status == "Defaulted":
                    return "red"
                return "blue"
            df_filtered["Color"] = df_filtered["TSWcontractStatus"].apply(pick_color)
        else:
            df_filtered["Color"] = "blue"

        hover_cols = [
            c for c in [
                "OwnerName", "Home Value", 
                "TSWcontractStatus", "FICO",
                "Distance in Miles", "Address",
                "City", "State", "Zip Code"
            ] if c in df_filtered.columns
        ]

        fig = px.scatter_mapbox(
            df_filtered,
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
    else:
        st.info("Latitude/Longitude columns not present or all missing. No map to display.")

if __name__ == "__main__":
    run_owners_map()
