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

    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    # Ensure we have latitude/longitude
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        st.error("Missing 'Latitude' or 'Longitude' columns.")
        st.stop()

    # Convert lat/lon to numeric
    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # Drop invalid rows
    df_map = df.dropna(subset=["Latitude","Longitude"]).copy()
    if df_map.empty:
        st.warning("No valid rows with Latitude/Longitude found.")
        return

    # -----------------------
    # FILTERS
    # -----------------------
    st.subheader("Filters")

    # 1) TSWcontractStatus filter
    if "TSWcontractStatus" in df_map.columns:
        # Normalize/trimming if needed
        df_map["TSWcontractStatus"] = df_map["TSWcontractStatus"].astype(str).str.strip()

        all_statuses = sorted(df_map["TSWcontractStatus"].dropna().unique())

        # By default, only show "Active" & "Default" if they exist
        default_statuses = []
        if "Active" in all_statuses:
            default_statuses.append("Active")
        if "Default" in all_statuses:
            default_statuses.append("Default")
        # If neither "Active" nor "Default" are in the data, default to everything
        if not default_statuses:
            default_statuses = all_statuses

        selected_statuses = st.multiselect(
            "Filter by Contract Status(es)",
            options=all_statuses,
            default=default_statuses
        )
        # Filter
        df_map = df_map[df_map["TSWcontractStatus"].isin(selected_statuses)]
    else:
        st.info("No TSWcontractStatus column found.")
        selected_statuses = []

    if df_map.empty:
        st.warning("No data left after TSWcontractStatus filter.")
        return

    # 2) State filter
    if "State" in df_map.columns:
        unique_states = sorted(df_map["State"].dropna().unique())
        selected_states = st.multiselect(
            "Filter by State(s)",
            options=unique_states,
            default=unique_states
        )
        df_map = df_map[df_map["State"].isin(selected_states)]
    else:
        selected_states = []

    if df_map.empty:
        st.warning("No data left after State filter.")
        return

    # 3) FICO filter
    if "FICO" in df_map.columns:
        df_map["FICO"] = pd.to_numeric(df_map["FICO"], errors="coerce")
        min_fico = df_map["FICO"].min(skipna=True)
        max_fico = df_map["FICO"].max(skipna=True)
        if pd.isna(min_fico):
            min_fico = 0
        if pd.isna(max_fico):
            max_fico = 850
        fico_range = st.slider("FICO Range", float(min_fico), float(max_fico), (float(min_fico), float(max_fico)))
        df_map = df_map[(df_map["FICO"] >= fico_range[0]) & (df_map["FICO"] <= fico_range[1])]

    if df_map.empty:
        st.warning("No data left after FICO filter.")
        return

    # 4) Home Value filter
    include_non_numeric_hv = st.checkbox(
        "Include Non-Numeric Home Value Entries (e.g. 'Apartment','PO BOX')?",
        value=True
    )
    if "Home Value" in df_map.columns:
        df_map["HomeValue_Original"] = df_map["Home Value"]
        df_map["Home Value"] = pd.to_numeric(df_map["Home Value"], errors="coerce")
        numeric_mask = df_map["Home Value"].notna()
        if numeric_mask.sum() == 0:
            st.warning("All 'Home Value' entries appear to be non-numeric.")
            home_range = (0, 9999999)
        else:
            min_home_val = df_map.loc[numeric_mask, "Home Value"].min()
            max_home_val = df_map.loc[numeric_mask, "Home Value"].max()
            home_range = st.slider(
                "Home Value Range",
                float(min_home_val),
                float(max_home_val),
                (float(min_home_val), float(max_home_val))
            )

        if not include_non_numeric_hv:
            df_map = df_map[df_map["Home Value"].notna()]

        df_map = df_map[
            (df_map["Home Value"].fillna(-999999999) >= home_range[0]) &
            (df_map["Home Value"].fillna(999999999) <= home_range[1])
        ]

    if df_map.empty:
        st.warning("No data left after Home Value filter.")
        return

    # 5) Distance filter
    if "Distance in Miles" in df_map.columns:
        df_map["Distance in Miles"] = pd.to_numeric(df_map["Distance in Miles"], errors="coerce")
        min_dist = df_map["Distance in Miles"].min(skipna=True)
        max_dist = df_map["Distance in Miles"].max(skipna=True)
        if pd.isna(min_dist):
            min_dist = 0
        if pd.isna(max_dist):
            max_dist = 0
        dist_range = st.slider("Driving Distance (Miles)", float(min_dist), float(max_dist), (float(min_dist), float(max_dist)))
        df_map = df_map[
            (df_map["Distance in Miles"] >= dist_range[0]) &
            (df_map["Distance in Miles"] <= dist_range[1])
        ]

    if df_map.empty:
        st.warning("No data left after Distance filter.")
        return

    # 6) Sum of Amount Financed
    if "Sum of Amount Financed" in df_map.columns:
        df_map["Sum of Amount Financed"] = pd.to_numeric(df_map["Sum of Amount Financed"], errors="coerce")
        min_fin = df_map["Sum of Amount Financed"].min(skipna=True)
        max_fin = df_map["Sum of Amount Financed"].max(skipna=True)
        if pd.isna(min_fin):
            min_fin = 0
        if pd.isna(max_fin):
            max_fin = 0
        financed_range = st.slider("Sum of Amount Financed", float(min_fin), float(max_fin), (float(min_fin), float(max_fin)))
        df_map = df_map[
            (df_map["Sum of Amount Financed"] >= financed_range[0]) &
            (df_map["Sum of Amount Financed"] <= financed_range[1])
        ]

    if df_map.empty:
        st.warning("No data left after Sum of Amount Financed filter.")
        return

    # 7) TSW Payment Amount
    if "TSWpaymentAmount" in df_map.columns:
        df_map["TSWpaymentAmount"] = pd.to_numeric(df_map["TSWpaymentAmount"], errors="coerce")
        min_pay = df_map["TSWpaymentAmount"].min(skipna=True)
        max_pay = df_map["TSWpaymentAmount"].max(skipna=True)
        if pd.isna(min_pay):
            min_pay = 0
        if pd.isna(max_pay):
            max_pay = 0
        pay_range = st.slider("TSW Payment Amount", float(min_pay), float(max_pay), (float(min_pay), float(max_pay)))
        df_map = df_map[
            (df_map["TSWpaymentAmount"] >= pay_range[0]) &
            (df_map["TSWpaymentAmount"] <= pay_range[1])
        ]

    if df_map.empty:
        st.warning("No data left after TSW Payment Amount filter.")
        return

    # -----------------------------
    # Display final row count, plus how many are Active/Default
    # -----------------------------
    st.write(f"**Filtered Results**: {len(df_map)} row(s).")

    if "TSWcontractStatus" in df_map.columns:
        # Count how many are Active/Default
        counts = df_map["TSWcontractStatus"].value_counts()
        active_count = counts.get("Active", 0)
        default_count = counts.get("Default", 0)

        col1, col2 = st.columns(2)
        col1.metric("Total Active (Filtered)", active_count)
        col2.metric("Total Default (Filtered)", default_count)

    st.dataframe(df_map.head(20))

    # -----------------------------
    # MAP
    # -----------------------------
    st.subheader("Map View by TSW Contract Status")

    # Softer color palette for Active & Default
    color_map = {
        "Active": "#66CC66",
        "Default": "#FF6666"
    }

    color_col = "TSWcontractStatus" if "TSWcontractStatus" in df_map.columns else None

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
    hover_cols = [c for c in hover_cols if c in df_map.columns]

    fig = px.scatter_mapbox(
        df_map,
        lat="Latitude",
        lon="Longitude",
        color=color_col,              # color by TSWcontractStatus if present
        color_discrete_map=color_map, # use green/red for Active/Default
        hover_data=hover_cols,
        zoom=4,
        height=600
        # no marker size override => use Plotly's default
    )

    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    run_owners_map()
