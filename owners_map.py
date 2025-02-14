import streamlit as st
import pandas as pd
import plotly.express as px
import os

def run_owners_map():
    st.title("Timeshare Owners Map")

    # 1) LOAD THE EXCEL FILE
    file_path = "Owners enriched with home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    # 2) READ THE SPREADSHEET
    df = pd.read_excel(file_path)

    # 3) RENAME LAT/LON COLUMNS IF NEEDED
    df.rename(
        columns={
            "Origin Latitude": "Latitude",
            "Origin Longitude": "Longitude"
        },
        inplace=True
    )

    # QUICK PREVIEW
    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    # 4) CHECK THAT WE HAVE LATITUDE/LONGITUDE
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        st.error("Missing 'Origin Latitude' or 'Origin Longitude' columns in the spreadsheet.")
        st.stop()

    # 5) MAKE LAT/LON NUMERIC & DROP INVALID ROWS
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    df_map = df.dropna(subset=["Latitude", "Longitude"]).copy()

    if df_map.empty:
        st.warning("No valid rows with Latitude/Longitude found. Cannot display map.")
        st.stop()

    # 6) BUILD FILTERS
    st.subheader("Filters")

    # -------------------------
    # State Filter
    # -------------------------
    if "State" in df_map.columns:
        unique_states = sorted(df_map["State"].dropna().unique())
        selected_states = st.multiselect(
            "Filter by State(s)",
            options=unique_states,
            default=unique_states
        )
    else:
        selected_states = []

    # -------------------------
    # TSW Contract Status Filter
    # -------------------------
    if "TSWcontractStatus" in df_map.columns:
        status_options = ["Active", "Inactive", "Both"]
        selected_status = st.selectbox(
            "Filter by Contract Status",
            options=status_options,
            index=status_options.index("Both")
        )
    else:
        selected_status = "Both"

    # Apply the contract status filter
    if selected_status != "Both":
        df_map = df_map[df_map["TSWcontractStatus"] == selected_status]

    # Show the counts for active and inactive
    active_count = len(df_map[df_map["TSWcontractStatus"] == "Active"])
    inactive_count = len(df_map[df_map["TSWcontractStatus"] == "Inactive"])
    st.write(f"**Active:** {active_count} | **Inactive:** {inactive_count}")

    # ------------------------------------------------
    # 7) APPLY FILTERS
    # ------------------------------------------------
    df_filtered = df_map.copy()

    # State filter
    if selected_states:
        df_filtered = df_filtered[df_filtered["State"].isin(selected_states)]

    st.write(f"**Filtered Results**: {len(df_filtered)} row(s).")
    st.dataframe(df_filtered.head(20))

    # ------------------------------------------------
    # 8) PLOT MAP (color by TSW contract status)
    # ------------------------------------------------
    if df_filtered.empty:
        st.warning("No data left after filters.")
        return

    st.subheader("Map View by TSW Contract Status")

    # Color based on contract status
    df_filtered["Color"] = df_filtered["TSWcontractStatus"].apply(
        lambda x: "green" if x == "Active" else "red" if x == "Inactive" else "gray"
    )

    # Only include columns actually in the DataFrame
    hover_cols = [
        "OwnerName",
        "Last Name 1",
        "First Name 1",
        "Last Name 2",
        "First Name 2",
        "FICO",
        "HomeValue_Original",
        "Distance in Miles",
        "Sum of Amount Financed",
        "TSWpaymentAmount",
        "TSWcontractStatus",
        "Address",
        "City",
        "State",
        "Zip Code"
    ]
    hover_cols = [c for c in hover_cols if c in df_filtered.columns]

    fig = px.scatter_mapbox(
        df_filtered,
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

# Streamlit entry point
if __name__ == "__main__":
    run_owners_map()
