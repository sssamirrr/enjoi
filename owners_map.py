import streamlit as st
import pandas as pd
import plotly.express as px
import os

def run_owners_map():
    st.title("Timeshare Owners Map (Green = Active, Red = Default)")

    file_path = "Owners enriched with home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    df = pd.read_excel(file_path)
    df.rename(columns={"Origin Latitude": "Latitude",
                       "Origin Longitude": "Longitude"}, inplace=True)

    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    # Must have numeric lat/lon
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df_map = df.dropna(subset=["Latitude","Longitude"]).copy()
    if df_map.empty:
        st.warning("No valid rows with Latitude/Longitude found.")
        return

    # Clean up or standardize TSWcontractStatus
    if "TSWcontractStatus" in df_map.columns:
        def normalize_status(val):
            val = str(val).strip().lower()
            if "active" in val:
                return "Active"
            elif "default" in val:
                return "Default"
            else:
                return val  # e.g. "Cancelled", "Unknown", etc.

        df_map["TSWcontractStatus"] = df_map["TSWcontractStatus"].apply(normalize_status)

        # Print unique statuses to debug
        st.write("Unique statuses after normalization:", df_map["TSWcontractStatus"].unique())

        # Let them pick
        all_statuses = sorted(df_map["TSWcontractStatus"].dropna().unique())
        selected_statuses = st.multiselect(
            "Select Contract Status(es)",
            options=all_statuses,
            default=all_statuses
        )
        df_map = df_map[df_map["TSWcontractStatus"].isin(selected_statuses)]

    # If there's nothing left, stop
    if df_map.empty:
        st.warning("No data left after filtering.")
        return

    # Choose your color map for known statuses
    color_map = {
        "Active": "green",
        "Default": "red"
        # Others will get a random color
    }

    # Hover columns
    hover_cols = ["TSWcontractStatus","OwnerName","FICO","City","State"]
    hover_cols = [c for c in hover_cols if c in df_map.columns]

    # Create the map
    fig = px.scatter_mapbox(
        df_map,
        lat="Latitude",
        lon="Longitude",
        color="TSWcontractStatus",
        hover_data=hover_cols,
        zoom=4,
        height=600,
        color_discrete_map=color_map
    )
    fig.update_layout(mapbox_style="open-street-map")
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_owners_map()
