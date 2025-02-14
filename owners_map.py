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

    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df_map = df.dropna(subset=["Latitude","Longitude"]).copy()

    if df_map.empty:
        st.warning("No valid rows with Latitude/Longitude found.")
        st.stop()

    st.subheader("Map (Active = Green, Default = Red)")

    # If you ONLY want Active/Default, uncomment:
    # df_map = df_map[df_map["TSWcontractStatus"].isin(["Active","Default"])]

    # Or let them pick statuses
    if "TSWcontractStatus" in df_map.columns:
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

    hover_cols = [
        "OwnerName","FICO","City","State","TSWcontractStatus"
    ]
    hover_cols = [c for c in hover_cols if c in df_map.columns]

    # Define color_discrete_map for EXACT color
    # Any statuses NOT in the dict get an automatically chosen color
    color_map = {
        "Active": "green",
        "Default": "red"
        # If you have more statuses, add them here or let Plotly pick a default
        # "Other Status": "blue"
    }

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
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_owners_map()
