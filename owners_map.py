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
    # TSW Contract Status Filter (Active, Defaulted, or Both)
    # -------------------------
    if "TSWcontractStatus" in df_map.columns:
        status_options = ["Active", "Defaulted", "Both"]
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

    # -------------------------
    # FICO Slider
    # -------------------------
    if "FICO" in df_map.columns:
        min_fico = df_map["FICO"].min()
        max_fico = df_map["FICO"].max()
        fico_range = st.slider(
            "FICO Range",
            min_value=int(min_fico),
            max_value=int(max_fico),
            value=(int(min_fico), int(max_fico))
        )
        df_map = df_map[(df_map["FICO"] >= fico_range[0]) & (df_map["FICO"] <= fico_range[1])]

    # -------------------------
    # Distance in Miles Slider
    # -------------------------
    if "Distance in Miles" in df_map.columns:
        min_dist = df_map["Distance in Miles"].min()
        max_dist = df_map["Distance in Miles"].max()
        dist_range = st.slider(
            "Distance in Miles",
            min_value=int(min_dist),
            max_value=int(max_dist),
            value=(int(min_dist), int(max_dist))
        )
        df_map = df_map[(df_map["Distance in Miles"] >= dist_range[0]) & (df_map["Distance in Miles"] <= dist_range[1])]

    # -------------------------
    # TSWpaymentAmount Slider
    # -------------------------
    if "TSWpaymentAmount" in df_map.columns:
        min_payment = df_map["TSWpaymentAmount"].min()
        max_payment = df_map["TSWpaymentAmount"].max()
        payment_range = st.slider(
            "TSW Payment Amount",
            min_value=int(min_payment),
            max_value=int(max_payment),
            value=(int(min_payment), int(max_payment))
        )
        df_map = df_map[(df_map["TSWpaymentAmount"] >= payment_range[0]) & (df_map["TSWpaymentAmount"] <= payment_range[1])]

    # -------------------------
    # Sum of Amount Financed Slider
    # -------------------------
    if "Sum of Amount Financed" in df_map.columns:
        min_financed = df_map["Sum of Amount Financed"].min()
        max_financed = df_map["Sum of Amount Financed"].max()
        financed_range = st.slider(
            "Sum of Amount Financed",
            min_value=int(min_financed),
            max_value=int(max_financed),
            value=(int(min_financed), int(max_financed))
        )
        df_map = df_map[(df_map["Sum of Amount Financed"] >= financed_range[0]) & (df_map["Sum of Amount Financed"] <= financed_range[1])]

    # -------------------------
    # Home Value Filter
    # -------------------------
    include_non_numeric_hv = st.checkbox(
        "Include Non-Numeric Home Value Entries (e.g. 'Apartment', 'Not available')?",
        value=True
    )

    if "Home Value" in df_map.columns:
        # Convert "Home Value" to numeric => invalid => NaN
        df_map["Home Value"] = pd.to_numeric(df_map["Home Value"], errors="coerce")

        # Get numeric and non-numeric entries separately
        numeric_values = df_map["Home Value"].dropna()
        non_numeric_values = df_map[df_map["Home Value"].isna()]

        # Check if user wants to include non-numeric entries
        if not include_non_numeric_hv:
            df_map = df_map[df_map["Home Value"].notna()]  # Keep only numeric values

        # Numeric filter with the slider
        if not numeric_values.empty:
            min_home_val = numeric_values.min()
            max_home_val = numeric_values.max()
            home_range = st.slider(
                "Home Value Range",
                min_value=float(min_home_val),
                max_value=float(max_home_val),
                value=(float(min_home_val), float(max_home_val))
            )
            # Apply home value filter for numeric data
            df_map = df_map[
                (df_map["Home Value"].fillna(-999999999) >= home_range[0]) & 
                (df_map["Home Value"].fillna(999999999) <= home_range[1])
            ]

    # Display filtered data count
    st.write(f"**Filtered Results**: {len(df_map)} row(s).")
    st.dataframe(df_map.head(20))

    # ------------------------------------------------
    # 8) PLOT MAP (color by TSW contract status)
    # ------------------------------------------------
    if df_map.empty:
        st.warning("No data left after filters.")
        return

    st.subheader("Map View by TSW Contract Status")

    # Dynamic count for active and default statuses
    active_count = len(df_map[df_map["TSWcontractStatus"] == "Active"])
    default_count = len(df_map[df_map["TSWcontractStatus"] == "Defaulted"])

    # Show dynamic count labels for active and default
    st.write(f"**Active:** {active_count} | **Defaulted:** {default_count}")

    # Color based on contract status
    df_map["Color"] = df_map["TSWcontractStatus"].apply(
        lambda x: "green" if x == "Active" else "gray"  # Defaulted as gray
    )

    # Only include columns actually in the DataFrame
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
    hover_cols = [c for c in hover_cols if c in df_map.columns]

    fig = px.scatter_mapbox(
        df_map,
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
