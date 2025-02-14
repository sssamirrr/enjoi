import streamlit as st
import pandas as pd
import plotly.express as px
import os

def run_big_owner_map():
    st.set_page_config(layout="wide")  # Make the page wide so we can see more data
    
    st.title("Owners with TSW Contract Status")

    ############################################################################
    # 1) LOAD DATA
    #    Adjust this path to wherever your full dataset is saved.
    ############################################################################
    file_path = "YOUR_OWNERS_DATA.xlsx"  # or .csv

    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    # Example: read Excel (or read_csv)
    if file_path.lower().endswith(".csv"):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    st.subheader("Data Preview (First 20 Rows)")
    st.dataframe(df.head(20), use_container_width=True)

    ############################################################################
    # 2) CLEANUP / PREP THE DATA
    ############################################################################
    # Ensure TSWcontractStatus exists
    if "TSWcontractStatus" not in df.columns:
        st.error("The 'TSWcontractStatus' column is missing from the data!")
        st.stop()

    # Normalize TSWcontractStatus to remove extra spaces
    df["TSWcontractStatus"] = df["TSWcontractStatus"].astype(str).str.strip()

    # Also ensure we have lat/lon columns:
    # If your lat/lon columns are called something else, rename them here.
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        # Possibly your dataset has columns like "Origin Latitude" & "Origin Longitude"
        # You can rename them:
        # df.rename(columns={"Origin Latitude": "Latitude","Origin Longitude": "Longitude"}, inplace=True)
        st.error("Missing 'Latitude' or 'Longitude' columns in the data!")
        st.stop()

    # Convert them to numeric
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # Drop rows lacking valid lat/lon
    df = df.dropna(subset=["Latitude","Longitude"]).copy()
    if df.empty:
        st.warning("No valid rows with lat/lon found. Cannot display map.")
        st.stop()

    ############################################################################
    # 3) FILTERS
    ############################################################################
    st.subheader("Filters")

    # A) TSWcontractStatus Filter
    all_statuses = sorted(df["TSWcontractStatus"].dropna().unique())
    # By default, pick Active & Default if they exist; else pick all
    default_choices = []
    if "Active" in all_statuses:
        default_choices.append("Active")
    if "Default" in all_statuses:
        default_choices.append("Default")
    if not default_choices:
        default_choices = all_statuses  # fallback to all if Active/Default not found

    chosen_statuses = st.multiselect(
        "Select TSW Contract Status(es)",
        options=all_statuses,
        default=default_choices
    )
    df_filtered = df[df["TSWcontractStatus"].isin(chosen_statuses)]

    # B) Optionally add more filters (e.g., FICO or State, etc.):
    # ...
    # Example: If you also have a State column:
    if "State" in df_filtered.columns:
        unique_states = sorted(df_filtered["State"].dropna().unique())
        selected_states = st.multiselect(
            "Choose State(s)",
            options=unique_states,
            default=unique_states
        )
        df_filtered = df_filtered[df_filtered["State"].isin(selected_states)]

    st.write(f"**Filtered Row Count**: {len(df_filtered)}")

    # If no rows left, stop
    if df_filtered.empty:
        st.warning("No data after filtering.")
        return

    # Show the entire filtered data as a large table
    st.subheader("All Filtered Rows")
    st.dataframe(df_filtered, use_container_width=True)

    ############################################################################
    # 4) MAP
    ############################################################################
    st.subheader("Map by TSW Contract Status")

    # We'll define a color map. Any statuses not in the dict will
    # automatically get a default color from Plotly.
    color_map = {
        "Active": "#66CC66",    # soft green
        "Default": "#FF6666",   # soft red
        "PaidInFull": "#0080FF",
        "CancelActiveToX": "#FF7F50",
        "Reinstatements": "#FFA500",
        "Foreclosure": "#FF00FF"
    }
    # You can add or remove from this dictionary as you wish.

    # For the hover, pick whichever columns you want to see on hover:
    possible_cols = [
        "OwnerName","TSWcontractStatus","FICO","State","Home Value",
        "Distance in Miles","Sum of Amount Financed","Address"
    ]
    hover_cols = [c for c in possible_cols if c in df_filtered.columns]

    fig = px.scatter_mapbox(
        df_filtered,
        lat="Latitude",
        lon="Longitude",
        color="TSWcontractStatus",  # color by status
        color_discrete_map=color_map,
        hover_data=hover_cols,
        zoom=4,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin=dict(r=0,t=0,l=0,b=0))

    st.plotly_chart(fig, use_container_width=True)

############################################################################
# MAIN
############################################################################
if __name__ == "__main__":
    run_big_owner_map()
