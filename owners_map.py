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

    # -------------------------------------------------
    # 1) Store original text of "Home Value"
    # -------------------------------------------------
    df["HV_original"] = df["Home Value"].astype(str)  # Keep exact strings

    # -------------------------------------------------
    # 2) Create numeric version (NaN if not numeric)
    # -------------------------------------------------
    df["HV_numeric"] = pd.to_numeric(df["Home Value"], errors="coerce")

    # Rename lat/lon if needed
    df.rename(columns={"Origin Latitude": "Latitude", 
                       "Origin Longitude": "Longitude"}, 
              inplace=True)

    # Convert Latitude/Longitude
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df.dropna(subset=["Latitude", "Longitude"], inplace=True)

    if df.empty:
        st.warning("No valid lat/lon rows found.")
        st.stop()

    # -------------------------------------------------
    # Example: TSW Status Filter
    # -------------------------------------------------
    if "TSWcontractStatus" in df.columns:
        status_choices = ["Active", "Defaulted", "Both"]
        chosen_status = st.selectbox("TSW Contract Status", status_choices, index=2)
        if chosen_status != "Both":
            df = df[df["TSWcontractStatus"] == chosen_status]

    # -------------------------------------------------
    # 3) Identify distinct non-numeric categories
    # -------------------------------------------------
    # Only consider rows where HV_numeric is NaN => original wasn't numeric
    non_numeric_rows = df[df["HV_numeric"].isna()].copy()
    unique_non_numeric_vals = sorted(non_numeric_rows["HV_original"].unique())

    # -------------------------------------------------
    # 4) Build slider for numeric Home Values (e.g. only positive)
    # -------------------------------------------------
    numeric_rows = df[df["HV_numeric"].notna()].copy()  # has a valid float
    pos_mask = numeric_rows["HV_numeric"] > 0  # if you only want > 0
    if pos_mask.sum() > 0:
        hv_min = numeric_rows.loc[pos_mask, "HV_numeric"].min()
        hv_max = numeric_rows.loc[pos_mask, "HV_numeric"].max()

        # Slider from min positive to max positive
        hv_range = st.slider(
            "Home Value (Numeric Only)",
            min_value=float(hv_min),
            max_value=float(hv_max),
            value=(float(hv_min), float(hv_max)),
            step=1.0,
        )
    else:
        hv_range = (0, 0)
        st.info("No positive numeric Home Values to filter on.")

    # -------------------------------------------------
    # 5) Build checkboxes for non-numeric categories
    # -------------------------------------------------
    st.write("### Non-Numeric Home Value Categories")
    included_non_numeric_vals = []
    for val in unique_non_numeric_vals:
        # We can create a short label, or show the entire string
        is_checked = st.checkbox(f"Include '{val}'", value=True)
        if is_checked:
            included_non_numeric_vals.append(val)

    # -------------------------------------------------
    # 6) Combine Filter Logic
    # -------------------------------------------------
    # We want rows that are:
    #   (numeric & in slider range) OR (non-numeric & category included)
    df_filtered = df[
        (
            # Condition for numeric rows
            (df["HV_numeric"].notna()) &
            (df["HV_numeric"] >= hv_range[0]) &
            (df["HV_numeric"] <= hv_range[1])
        )
        |
        (
            # Condition for non-numeric rows
            df["HV_numeric"].isna() &
            df["HV_original"].isin(included_non_numeric_vals)
        )
    ]

    st.write(f"**Filtered Rows**: {len(df_filtered)}")
    st.dataframe(df_filtered.head(20))

    # -------------------------------------------------
    # Plot Map if any rows remain
    # -------------------------------------------------
    if df_filtered.empty:
        st.warning("No data left after filters.")
        return

    # Color by TSW contract status for demonstration
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
            "OwnerName", "Home Value", "HV_original", "HV_numeric",
            "TSWcontractStatus", "FICO", 
            "Distance in Miles", "Address", 
            "City", "State", "Zip Code"
        ]
        if c in df_filtered.columns
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
    fig.update_layout(margin={"r":0, "t":0, "l":0, "b":0})
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_owners_map()
