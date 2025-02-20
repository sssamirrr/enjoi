import streamlit as st
import pandas as pd
import plotly.express as px
import os

def run_owners_map():
    st.title("Timeshare Owners Map")

    # --------------------------------------------------
    # 1) Load the Excel file
    # --------------------------------------------------
    file_path = "Owners enriched with home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    df = pd.read_excel(file_path)

    # --------------------------------------------------
    # 2) Rename Lat/Lon columns if needed
    # --------------------------------------------------
    if "Origin Latitude" in df.columns and "Origin Longitude" in df.columns:
        df.rename(columns={
            "Origin Latitude": "Latitude",
            "Origin Longitude": "Longitude"
        }, inplace=True)

    # (Optional) Quick preview
    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    # --------------------------------------------------
    # 3) Convert Lat/Lon to numeric (but do NOT drop rows)
    # --------------------------------------------------
    if "Latitude" in df.columns:
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    if "Longitude" in df.columns:
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # --------------------------------------------------
    # 4) Build Filters
    # --------------------------------------------------
    st.subheader("Filters")

    # ------------------------- 
    # State Filter
    # -------------------------
    if "State" in df.columns:
        unique_states = sorted(df["State"].dropna().unique())
        selected_states = st.multiselect(
            "Filter by State(s)",
            options=unique_states,
            default=unique_states
        )
        df = df[df["State"].isin(selected_states)]

    # -------------------------
    # TSW Contract Status Filter (Active, Defaulted, or Both)
    # -------------------------
    if "TSWcontractStatus" in df.columns:
        status_options = ["Active", "Defaulted", "Both"]
        selected_status = st.selectbox(
            "Filter by Contract Status",
            options=status_options,
            index=status_options.index("Both")
        )
        if selected_status != "Both":
            df = df[df["TSWcontractStatus"] == selected_status]

    # -------------------------
    # FICO Slider
    # -------------------------
    if "FICO" in df.columns:
        min_fico = df["FICO"].min()
        max_fico = df["FICO"].max()
        fico_range = st.slider(
            "FICO Range",
            min_value=int(min_fico),
            max_value=int(max_fico),
            value=(int(min_fico), int(max_fico))
        )
        df = df[(df["FICO"] >= fico_range[0]) & (df["FICO"] <= fico_range[1])]

    # -------------------------
    # Distance in Miles Slider
    # -------------------------
    if "Distance in Miles" in df.columns:
        min_dist = df["Distance in Miles"].min()
        max_dist = df["Distance in Miles"].max()
        dist_range = st.slider(
            "Distance in Miles",
            min_value=int(min_dist),
            max_value=int(max_dist),
            value=(int(min_dist), int(max_dist))
        )
        df = df[(df["Distance in Miles"] >= dist_range[0]) & (df["Distance in Miles"] <= dist_range[1])]

    # -------------------------
    # TSWpaymentAmount Slider
    # -------------------------
    if "TSWpaymentAmount" in df.columns:
        min_payment = df["TSWpaymentAmount"].min()
        max_payment = df["TSWpaymentAmount"].max()
        payment_range = st.slider(
            "TSW Payment Amount",
            min_value=int(min_payment),
            max_value=int(max_payment),
            value=(int(min_payment), int(max_payment))
        )
        df = df[(df["TSWpaymentAmount"] >= payment_range[0]) & (df["TSWpaymentAmount"] <= payment_range[1])]

    # -------------------------
    # Sum of Amount Financed Slider
    # -------------------------
    if "Sum of Amount Financed" in df.columns:
        min_financed = df["Sum of Amount Financed"].min()
        max_financed = df["Sum of Amount Financed"].max()
        financed_range = st.slider(
            "Sum of Amount Financed",
            min_value=int(min_financed),
            max_value=int(max_financed),
            value=(int(min_financed), int(max_financed))
        )
        df = df[(df["Sum of Amount Financed"] >= financed_range[0]) & (df["Sum of Amount Financed"] <= financed_range[1])]

    # --------------------------------------------------
    # Home Value Filter: Numeric vs. Non-Numeric
    # --------------------------------------------------
    if "Home Value" in df.columns:
        # 1) Convert to numeric; non-numerics => NaN
        df["Home Value"] = pd.to_numeric(df["Home Value"], errors="coerce")
        # 2) Replace NaN (originally non-numeric) with -1
        df["Home Value"] = df["Home Value"].fillna(-1)

        # If we have positive numeric values, we let the user filter by slider
        pos_mask = df["Home Value"] > 0
        if pos_mask.sum() > 0:
            hv_min_pos = df.loc[pos_mask, "Home Value"].min()
            hv_max_pos = df.loc[pos_mask, "Home Value"].max()
            hv_range = st.slider(
                "Home Value (Positive Only)",
                min_value=float(hv_min_pos),
                max_value=float(hv_max_pos),
                value=(float(hv_min_pos), float(hv_max_pos))
            )
        else:
            hv_range = (0, 0)
            st.info("No positive Home Values found. Slider not applicable.")

        # Checkbox to include negative placeholders (originally non-numeric)
        include_negative = st.checkbox("Include Non-Numeric (Negative) Home Values?", value=True)

        # Final filter for Home Value
        # Keep rows that have Home Value in [hv_range[0], hv_range[1]] if > 0
        # OR have Home Value < 0 if 'include_negative' is True
        df = df[
            (
                (df["Home Value"] > 0) &
                (df["Home Value"] >= hv_range[0]) &
                (df["Home Value"] <= hv_range[1])
            )
            |
            (
                (df["Home Value"] < 0) & include_negative
            )
        ]

    st.write(f"**Filtered Results**: {len(df)} row(s).")
    st.dataframe(df.head(20))

    # ------------------------------------------------
    # 8) Plot Map (color by TSW contract status)
    # ------------------------------------------------
    if df.empty:
        st.warning("No data left after filters.")
        return

    st.subheader("Map View by TSW Contract Status")

    # Dynamic count for active and default
    if "TSWcontractStatus" in df.columns:
        active_count = len(df[df["TSWcontractStatus"] == "Active"])
        default_count = len(df[df["TSWcontractStatus"] == "Defaulted"])
        st.write(f"**Active:** {active_count} | **Defaulted:** {default_count}")

        # Color logic
        df["Color"] = df["TSWcontractStatus"].apply(
            lambda x: "green" if x == "Active" else ("gray" if x == "Defaulted" else "blue")
        )
    else:
        df["Color"] = "blue"

    # Build a map subset with valid lat/lon
    # (We do NOT remove them from df, just skip them for the map)
    if "Latitude" in df.columns and "Longitude" in df.columns:
        map_df = df.dropna(subset=["Latitude", "Longitude"]).copy()
        if map_df.empty:
            st.info("No valid Latitude/Longitude in the filtered dataset. No map to display.")
            return

        # Only include columns that actually exist
        hover_cols = [
            "OwnerName", "Last Name 1", "First Name 1", "Last Name 2", "First Name 2",
            "FICO", "Home Value", "Distance in Miles", 
            "Sum of Amount Financed", "TSWpaymentAmount", 
            "TSWcontractStatus", "Address", "City", "State", "Zip Code"
        ]
        hover_cols = [c for c in hover_cols if c in map_df.columns]

        fig = px.scatter_mapbox(
            map_df,
            lat="Latitude",
            lon="Longitude",
            color="Color",
            hover_data=hover_cols,
            zoom=4,
            height=600
        )
        fig.update_layout(mapbox_style="open-street-map")
        fig.update_layout(margin={"r":0, "t":0, "l":0, "b":0})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Latitude/Longitude columns not found. No map to display.")

# -----------------------------------------------------
# Streamlit entry point
# -----------------------------------------------------
if __name__ == "__main__":
    run_owners_map()
