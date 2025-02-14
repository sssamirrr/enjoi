import streamlit as st
import pandas as pd
import plotly.express as px
import os

def run_owners_map():
    st.title("Timeshare Owners Map (Green=Active, Red=Default)")

    file_path = "Owners enriched with home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    df = pd.read_excel(file_path)

    # Rename if your sheet uses these column names
    df.rename(
        columns={
            "Origin Latitude": "Latitude",
            "Origin Longitude": "Longitude"
        },
        inplace=True
    )

    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        st.error("Missing Latitude/Longitude columns.")
        st.stop()

    # Coerce to numeric
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # Drop invalid coordinates
    df_map = df.dropna(subset=["Latitude","Longitude"]).copy()
    if df_map.empty:
        st.warning("No valid rows with Latitude/Longitude found.")
        return

    # OPTIONAL: Normalize TSWcontractStatus for exact matching
    if "TSWcontractStatus" in df_map.columns:
        # For example, if you might have "ACTIVE", "active ", "Defaulted" etc.
        def normalize_status(val):
            val = str(val).strip().title()  # e.g. "active " => "Active"
            # If you want "Defaulted" => "Default", do:
            if val.startswith("Default"):
                return "Default"
            return val
        
        df_map["TSWcontractStatus"] = df_map["TSWcontractStatus"].apply(normalize_status)

        # Let the user filter which statuses to show
        all_statuses = sorted(df_map["TSWcontractStatus"].dropna().unique())
        selected_statuses = st.multiselect(
            "Select Contract Status(es)",
            options=all_statuses,
            default=all_statuses
        )
        df_map = df_map[df_map["TSWcontractStatus"].isin(selected_statuses)]

    if df_map.empty:
        st.warning("No data left after filtering.")
        return

    # Use explicit hex colors for Active & Default
    color_discrete_map = {
        "Active": "#00FF00",   # Bright green
        "Default": "#FF0000"   # Bright red
    }

    hover_cols = ["OwnerName", "FICO", "City", "State", "TSWcontractStatus"]
    hover_cols = [c for c in hover_cols if c in df_map.columns]

    # Create the scatter mapbox figure
    fig = px.scatter_mapbox(
        df_map,
        lat="Latitude",
        lon="Longitude",
        color="TSWcontractStatus",
        hover_data=hover_cols,
        zoom=4,
        height=600,
        color_discrete_map=color_discrete_map
    )

    # Increase the marker size
    fig.update_traces(
        marker=dict(size=10),
        selector=dict(mode='markers')
    )

    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_owners_map()
