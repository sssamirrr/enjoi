import streamlit as st
import pandas as pd
import plotly.express as px
import os

def run_owners_map():
    st.title("Timeshare Owners Map")

    # 1) LOAD THE EXCEL FILE
    # Make sure this file is in the same directory as owners_map.py
    file_path = "Owners enriched with home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    # Read the spreadsheet
    df = pd.read_excel(file_path)

    # 2) RENAME LAT/LON COLUMNS IF DESIRED
    #   (Your file has 'Origin Latitude' and 'Origin Longitude'—rename them to 'Latitude' / 'Longitude')
    df.rename(
        columns={
            "Origin Latitude": "Latitude",
            "Origin Longitude": "Longitude"
        },
        inplace=True
    )

    # 3) QUICK DATA PREVIEW
    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    # 4) CHECK/CONVERT LATITUDE & LONGITUDE TO NUMERIC
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        st.error("Missing 'Origin Latitude' or 'Origin Longitude' columns in the spreadsheet.")
        st.stop()

    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # Drop rows where lat/lon is not valid
    df_map = df.dropna(subset=["Latitude","Longitude"]).copy()

    if df_map.empty:
        st.warning("No valid rows with Latitude/Longitude found. Cannot display map.")
        st.stop()

    # 5) BUILD FILTERS

    st.subheader("Filters")

    # -- State filter --
    unique_states = sorted(df_map["State"].dropna().unique())
    default_states = unique_states  # Show all states by default
    selected_states = st.multiselect(
        "Filter by State(s)",
        options=unique_states,
        default=default_states
    )

    # -- FICO filter --
    min_fico = float(df_map["FICO"].min() if pd.notnull(df_map["FICO"].min()) else 0)
    max_fico = float(df_map["FICO"].max() if pd.notnull(df_map["FICO"].max()) else 850)
    fico_range = st.slider(
        "FICO Range",
        min_value=min_fico,
        max_value=max_fico,
        value=(min_fico, max_fico)
    )

    # -- Home Value filter --
    if "Home Value" in df_map.columns:
        min_home = float(df_map["Home Value"].min() if pd.notnull(df_map["Home Value"].min()) else 0)
        max_home = float(df_map["Home Value"].max() if pd.notnull(df_map["Home Value"].max()) else 9999999)
        home_range = st.slider(
            "Home Value Range",
            min_value=min_home,
            max_value=max_home,
            value=(min_home, max_home)
        )
    else:
        # If no column found, set a dummy range
        home_range = (0, 999999999)

    # -- Driving Distance filter (Distance in Miles) --
    if "Distance in Miles" in df_map.columns:
        min_dist = float(df_map["Distance in Miles"].min() if pd.notnull(df_map["Distance in Miles"].min()) else 0)
        max_dist = float(df_map["Distance in Miles"].max() if pd.notnull(df_map["Distance in Miles"].max()) else 0)
        dist_range = st.slider(
            "Driving Distance (Miles)",
            min_value=min_dist,
            max_value=max_dist,
            value=(min_dist, max_dist)
        )
    else:
        dist_range = (0, 999999)

    # -- Sum of Amount Financed filter --
    if "Sum of Amount Financed" in df_map.columns:
        min_fin = float(df_map["Sum of Amount Financed"].min() if pd.notnull(df_map["Sum of Amount Financed"].min()) else 0)
        max_fin = float(df_map["Sum of Amount Financed"].max() if pd.notnull(df_map["Sum of Amount Financed"].max()) else 0)
        financed_range = st.slider(
            "Sum of Amount Financed",
            min_value=min_fin,
            max_value=max_fin,
            value=(min_fin, max_fin)
        )
    else:
        financed_range = (0, 999999999)

    # -- TSWpaymentAmount filter --
    if "TSWpaymentAmount" in df_map.columns:
        min_pay = float(df_map["TSWpaymentAmount"].min() if pd.notnull(df_map["TSWpaymentAmount"].min()) else 0)
        max_pay = float(df_map["TSWpaymentAmount"].max() if pd.notnull(df_map["TSWpaymentAmount"].max()) else 0)
        pay_range = st.slider(
            "TSW Payment Amount",
            min_value=min_pay,
            max_value=max_pay,
            value=(min_pay, max_pay)
        )
    else:
        pay_range = (0, 999999999)

    # 6) APPLY FILTERS
    df_filtered = df_map.copy()

    # State filter
    df_filtered = df_filtered[df_filtered["State"].isin(selected_states)]

    # FICO filter
    df_filtered = df_filtered[
        (df_filtered["FICO"] >= fico_range[0]) &
        (df_filtered["FICO"] <= fico_range[1])
    ]

    # Home Value filter
    if "Home Value" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["Home Value"] >= home_range[0]) &
            (df_filtered["Home Value"] <= home_range[1])
        ]

    # Distance filter
    if "Distance in Miles" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["Distance in Miles"] >= dist_range[0]) &
            (df_filtered["Distance in Miles"] <= dist_range[1])
        ]

    # Sum of Amount Financed filter
    if "Sum of Amount Financed" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["Sum of Amount Financed"] >= financed_range[0]) &
            (df_filtered["Sum of Amount Financed"] <= financed_range[1])
        ]

    # TSW Payment Amount filter
    if "TSWpaymentAmount" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["TSWpaymentAmount"] >= pay_range[0]) &
            (df_filtered["TSWpaymentAmount"] <= pay_range[1])
        ]

    st.write(f"**Filtered Results**: {len(df_filtered)} row(s).")
    st.dataframe(df_filtered.head(20))

    # 7) PLOT MAP (color by TSWcontractStatus)
    if df_filtered.empty:
        st.warning("No data left after filters.")
        return

    # Set up the map
    st.subheader("Map View by TSW Contract Status")

    hover_cols = [
        "OwnerName",
        "Last Name 1",
        "First Name 1",
        "Last Name 2",
        "First Name 2",
        "FICO",
        "Home Value",
        "Distance in Miles",
        "Sum of Amount Financed",
        "TSWpaymentAmount",
        "TSWcontractStatus",
        "Address",
        "City",
        "State",
        "Zip Code"
    ]
    # Only include columns actually in the DataFrame
    hover_cols = [c for c in hover_cols if c in df_filtered.columns]

    fig = px.scatter_mapbox(
        df_filtered,
        lat="Latitude",
        lon="Longitude",
        color="TSWcontractStatus",  # color by status: Active/Default
        hover_data=hover_cols,
        zoom=4,
        height=600
    )

    # Use open-street-map style
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)


# Streamlit entry point
if __name__ == "__main__":
    run_owners_map()
