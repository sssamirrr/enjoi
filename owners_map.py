import streamlit as st
import pandas as pd
import plotly.express as px
import os

def run_owners_map():
    st.title("Owners Map (Green = Active, Red = Default)")

    file_path = "Owners enriched with home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    # Read data
    df = pd.read_excel(file_path)

    # Rename lat/lon columns if needed
    df.rename(
        columns={
            "Origin Latitude": "Latitude",
            "Origin Longitude": "Longitude"
        },
        inplace=True
    )

    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        st.error("Missing Latitude/Longitude columns.")
        st.stop()

    # Convert lat/lon to numeric
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # Drop invalid rows
    df_map = df.dropna(subset=["Latitude", "Longitude"]).copy()
    if df_map.empty:
        st.warning("No valid rows with Latitude/Longitude found.")
        return

    st.subheader("Data Preview")
    st.dataframe(df_map.head(10))

    # ------------------------------------------
    # 1. Standardize TSWcontractStatus to 'Active'/'Default'
    #    if it contains those words (case-insensitive).
    # ------------------------------------------
    if "TSWcontractStatus" in df_map.columns:
        def normalize_status(val: str) -> str:
            val = str(val).strip().lower()
            if "active" in val:
                return "Active"
            elif "default" in val:
                return "Default"
            else:
                return val

        df_map["TSWcontractStatus"] = df_map["TSWcontractStatus"].apply(normalize_status)

        # Let users pick which statuses to show
        all_statuses = sorted(df_map["TSWcontractStatus"].dropna().unique())
        selected_statuses = st.multiselect(
            "Select Contract Status(es)",
            options=all_statuses,
            default=all_statuses
        )
        df_map = df_map[df_map["TSWcontractStatus"].isin(selected_statuses)]
    else:
        st.warning("No TSWcontractStatus column found; everything will be one color.")
        # If we have no column, we can't color by status.

    if df_map.empty:
        st.warning("No data left after filtering.")
        return

    # ------------------------------------------
    # 2. Define color mapping
    # ------------------------------------------
    color_discrete_map = {
        "Active": "#00FF00",   # Green
        "Default": "#FF0000"   # Red
        # Any other status not in this map gets auto-colored by Plotly
    }

    # ------------------------------------------
    # 3. Plot the map
    # ------------------------------------------
    hover_cols = ["OwnerName", "FICO", "City", "State", "TSWcontractStatus"]
    hover_cols = [c for c in hover_cols if c in df_map.columns]

    fig = px.scatter_mapbox(
        df_map,
        lat="Latitude",
        lon="Longitude",
        color="TSWcontractStatus",            # color by TSWcontractStatus
        color_discrete_map=color_discrete_map,  # apply custom green/red
        hover_data=hover_cols,
        zoom=4,
        height=600
    )

    # Increase marker size
    fig.update_traces(marker=dict(size=10), selector=dict(mode='markers'))

    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

    st.subheader("Final Map")
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_owners_map()
