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
    df_map = df.dropna(subset=["Latitude","Longitude"]).copy()

    if df_map.empty:
        st.warning("No valid rows with Latitude/Longitude found. Cannot display map.")
        st.stop()

    # 6) BUILD FILTERS
    st.subheader("Filters")

    # -------------------------
    # Contract Status Filter
    # -------------------------
    if "TSWcontractStatus" in df_map.columns:
        all_statuses = sorted(df_map["TSWcontractStatus"].dropna().unique())
        # By default, select all
        selected_statuses = st.multiselect(
            "Select Contract Status(es)",
            options=all_statuses,
            default=all_statuses
        )
    else:
        selected_statuses = []

    # -------------------------
    # State Filter
    # -------------------------
    if "State" in df_map.columns:
        unique_states = sorted(df_map["State"].dropna().unique())
        default_states = unique_states  # show all by default
        selected_states = st.multiselect(
            "Filter by State(s)",
            options=unique_states,
            default=default_states
        )
    else:
        selected_states = []

    # -------------------------
    # FICO Filter
    # -------------------------
    if "FICO" in df_map.columns:
        df_map["FICO"] = pd.to_numeric(df_map["FICO"], errors="coerce")
        min_fico_val = df_map["FICO"].min(skipna=True)
        max_fico_val = df_map["FICO"].max(skipna=True)
        if pd.isna(min_fico_val):
            min_fico_val = 0
        if pd.isna(max_fico_val):
            max_fico_val = 850

        fico_range = st.slider(
            "FICO Range",
            min_value=float(min_fico_val),
            max_value=float(max_fico_val),
            value=(float(min_fico_val), float(max_fico_val))
        )
    else:
        fico_range = (0, 850)

    # -------------------------
    # Check box: Include non-numeric home values?
    # -------------------------
    include_non_numeric_hv = st.checkbox(
        "Include Non-Numeric Home Value Entries (e.g. 'Apartment','PO BOX')?",
        value=True
    )

    # -------------------------
    # Home Value
    # -------------------------
    if "Home Value" in df_map.columns:
        df_map["HomeValue_Original"] = df_map["Home Value"]
        # Coerce to numeric
        df_map["Home Value"] = pd.to_numeric(df_map["Home Value"], errors="coerce")

        numeric_mask = df_map["Home Value"].notna()
        if numeric_mask.sum() == 0:
            st.warning("All 'Home Value' entries are non-numeric. No numeric filtering applied.")
            home_range = (0, 9999999)
        else:
            min_home_val = df_map.loc[numeric_mask, "Home Value"].min()
            max_home_val = df_map.loc[numeric_mask, "Home Value"].max()
            home_range = st.slider(
                "Home Value Range",
                min_value=float(min_home_val),
                max_value=float(max_home_val),
                value=(float(min_home_val), float(max_home_val))
            )
    else:
        home_range = (0, 9999999)
        include_non_numeric_hv = True

    # -------------------------
    # Distance in Miles Filter
    # -------------------------
    if "Distance in Miles" in df_map.columns:
        df_map["Distance in Miles"] = pd.to_numeric(df_map["Distance in Miles"], errors="coerce")
        min_dist_val = df_map["Distance in Miles"].min(skipna=True)
        max_dist_val = df_map["Distance in Miles"].max(skipna=True)
        if pd.isna(min_dist_val):
            min_dist_val = 0
        if pd.isna(max_dist_val):
            max_dist_val = 0
        dist_range = st.slider(
            "Driving Distance (Miles)",
            min_value=float(min_dist_val),
            max_value=float(max_dist_val),
            value=(float(min_dist_val), float(max_dist_val))
        )
    else:
        dist_range = (0, 999999)

    # -------------------------
    # Sum of Amount Financed
    # -------------------------
    if "Sum of Amount Financed" in df_map.columns:
        df_map["Sum of Amount Financed"] = pd.to_numeric(
            df_map["Sum of Amount Financed"], errors="coerce")
        min_fin_val = df_map["Sum of Amount Financed"].min(skipna=True)
        max_fin_val = df_map["Sum of Amount Financed"].max(skipna=True)
        if pd.isna(min_fin_val):
            min_fin_val = 0
        if pd.isna(max_fin_val):
            max_fin_val = 0
        financed_range = st.slider(
            "Sum of Amount Financed",
            min_value=float(min_fin_val),
            max_value=float(max_fin_val),
            value=(float(min_fin_val), float(max_fin_val))
        )
    else:
        financed_range = (0, 999999999)

    # -------------------------
    # TSW Payment Amount
    # -------------------------
    if "TSWpaymentAmount" in df_map.columns:
        df_map["TSWpaymentAmount"] = pd.to_numeric(df_map["TSWpaymentAmount"], errors="coerce")
        min_pay_val = df_map["TSWpaymentAmount"].min(skipna=True)
        max_pay_val = df_map["TSWpaymentAmount"].max(skipna=True)
        if pd.isna(min_pay_val):
            min_pay_val = 0
        if pd.isna(max_pay_val):
            max_pay_val = 0
        pay_range = st.slider(
            "TSW Payment Amount",
            min_value=float(min_pay_val),
            max_value=float(max_pay_val),
            value=(float(min_pay_val), float(max_pay_val))
        )
    else:
        pay_range = (0, 999999999)

    # ------------------------------------------------
    # 7) APPLY FILTERS
    # ------------------------------------------------
    df_filtered = df_map.copy()

    # TSWcontractStatus filter
    if "TSWcontractStatus" in df_filtered.columns and selected_statuses:
        df_filtered = df_filtered[df_filtered["TSWcontractStatus"].isin(selected_statuses)]

    # State filter
    if "State" in df_filtered.columns and selected_states:
        df_filtered = df_filtered[df_filtered["State"].isin(selected_states)]

    # FICO filter
    if "FICO" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["FICO"] >= fico_range[0]) &
            (df_filtered["FICO"] <= fico_range[1])
        ]

    # Home Value filter
    if "Home Value" in df_filtered.columns:
        if not include_non_numeric_hv:
            # Exclude rows with non-numeric values
            df_filtered = df_filtered[df_filtered["Home Value"].notna()]
        df_filtered = df_filtered[
            (df_filtered["Home Value"].fillna(-999999999) >= home_range[0]) &
            (df_filtered["Home Value"].fillna(999999999) <= home_range[1])
        ]

    # Distance in Miles
    if "Distance in Miles" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["Distance in Miles"] >= dist_range[0]) &
            (df_filtered["Distance in Miles"] <= dist_range[1])
        ]

    # Sum of Amount Financed
    if "Sum of Amount Financed" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["Sum of Amount Financed"] >= financed_range[0]) &
            (df_filtered["Sum of Amount Financed"] <= financed_range[1])
        ]

    # TSW Payment Amount
    if "TSWpaymentAmount" in df_filtered.columns:
        df_filtered = df_filtered[
            (df_filtered["TSWpaymentAmount"] >= pay_range[0]) &
            (df_filtered["TSWpaymentAmount"] <= pay_range[1])
        ]

    st.write(f"**Filtered Results**: {len(df_filtered)} row(s).")
    st.dataframe(df_filtered.head(20))

    # ------------------------------------------------
    # 8) PLOT MAP
    # ------------------------------------------------
    if df_filtered.empty:
        st.warning("No data left after filters.")
        return

    st.subheader("Map View by TSW Contract Status")

    # We'll color by TSWcontractStatus if present
    color_col = "TSWcontractStatus" if "TSWcontractStatus" in df_filtered.columns else None

    # Hover data
    possible_hover_cols = [
        "OwnerName",
        "Last Name 1",
        "First Name 1",
        "Last Name 2",
        "First Name 2",
        "FICO",
        "HomeValue_Original",   # original text or numeric
        "Distance in Miles",
        "Sum of Amount Financed",
        "TSWpaymentAmount",
        "TSWcontractStatus",
        "Address",
        "City",
        "State",
        "Zip Code"
    ]
    hover_cols = [c for c in possible_hover_cols if c in df_filtered.columns]

    fig = px.scatter_mapbox(
        df_filtered,
        lat="Latitude",
        lon="Longitude",
        color=color_col,  # distinct color per contract status
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
