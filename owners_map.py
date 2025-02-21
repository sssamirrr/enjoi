import streamlit as st
import pandas as pd
import plotly.express as px
import os
import math

def run_owners_map():
    st.title("Timeshare Owners Map")

    # ------------------------------------------------------------------
    # 1) Load & Prepare the DataFrame with a unique name, df_home
    # ------------------------------------------------------------------
    file_path = "Owners home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    df_home = pd.read_excel(file_path)
    original_count = len(df_home)

    # Keep track of which rows get removed at each filter step
    filter_removals = []
    def apply_filter(df, mask, reason):
        kept = df[mask]
        removed = df[~mask]
        if len(removed) > 0:
            filter_removals.append((reason, removed.copy()))
        return kept

    # Rename lat/lon columns if they exist
    if "Origin Latitude" in df_home.columns and "Origin Longitude" in df_home.columns:
        df_home.rename(columns={
            "Origin Latitude": "Latitude",
            "Origin Longitude": "Longitude"
        }, inplace=True)

    # Convert lat/lon to numeric (if they exist)
    df_home["Latitude"] = pd.to_numeric(df_home.get("Latitude"), errors="coerce")
    df_home["Longitude"] = pd.to_numeric(df_home.get("Longitude"), errors="coerce")

    st.subheader("Filters")

    # ------------------------------------------------------------------
    # 2) State Filter
    # ------------------------------------------------------------------
    if "State" in df_home.columns:
        unique_states = sorted(df_home["State"].dropna().unique())
        selected_states = st.multiselect(
            "Filter by State(s)",
            options=unique_states,
            default=unique_states
        )
        mask = df_home["State"].isin(selected_states)
        df_home = apply_filter(df_home, mask, f"State filter: {selected_states}")

    # ------------------------------------------------------------------
    # 3) TSW Contract Status Filter
    # ------------------------------------------------------------------
    if "TSWcontractStatus" in df_home.columns:
        status_options = ["Active", "Defaulted", "Both"]
        chosen_status = st.selectbox(
            "Filter by Contract Status",
            status_options,
            index=2
        )
        if chosen_status != "Both":
            mask = (df_home["TSWcontractStatus"] == chosen_status)
            df_home = apply_filter(df_home, mask, f"TSWcontractStatus = {chosen_status}")

    # ------------------------------------------------------------------
    # 4) FICO Slider
    # ------------------------------------------------------------------
    if "FICO" in df_home.columns:
        min_fico_val = df_home["FICO"].min()
        max_fico_val = df_home["FICO"].max()
        fico_min = math.floor(min_fico_val)
        fico_max = math.ceil(max_fico_val)
        fico_range = st.slider("FICO Range", fico_min, fico_max, (fico_min, fico_max))
        mask = (df_home["FICO"] >= fico_range[0]) & (df_home["FICO"] <= fico_range[1])
        df_home = apply_filter(df_home, mask, f"FICO in [{fico_range[0]}, {fico_range[1]}]")

    # ------------------------------------------------------------------
    # 5) Distance in Miles Slider
    # ------------------------------------------------------------------
    if "Distance in Miles" in df_home.columns:
        dist_min_val = df_home["Distance in Miles"].min()
        dist_max_val = df_home["Distance in Miles"].max()
        dmin = math.floor(dist_min_val)
        dmax = math.ceil(dist_max_val)
        dist_range = st.slider("Distance in Miles", dmin, dmax, (dmin, dmax))
        mask = (df_home["Distance in Miles"] >= dist_range[0]) & (df_home["Distance in Miles"] <= dist_range[1])
        df_home = apply_filter(df_home, mask, f"Distance in [{dist_range[0]}, {dist_range[1]}]")

    # ------------------------------------------------------------------
    # 6) TSW Payment Amount Slider
    # ------------------------------------------------------------------
    if "TSWpaymentAmount" in df_home.columns:
        df_home["TSWpaymentAmount"] = pd.to_numeric(df_home["TSWpaymentAmount"], errors="coerce").fillna(0)
        pay_min_val = df_home["TSWpaymentAmount"].min()
        pay_max_val = df_home["TSWpaymentAmount"].max()
        pmin = math.floor(pay_min_val)
        pmax = math.ceil(pay_max_val)
        pay_range = st.slider("TSW Payment Amount", pmin, pmax, (pmin, pmax))
        mask = (df_home["TSWpaymentAmount"] >= pay_range[0]) & (df_home["TSWpaymentAmount"] <= pay_range[1])
        df_home = apply_filter(df_home, mask, f"TSWpaymentAmount in [{pay_range[0]}, {pay_range[1]}]")

    # ------------------------------------------------------------------
    # 7) Sum of Amount Financed Slider
    # ------------------------------------------------------------------
    if "Sum of Amount Financed" in df_home.columns:
        fin_min_val = df_home["Sum of Amount Financed"].min()
        fin_max_val = df_home["Sum of Amount Financed"].max()
        fmin = math.floor(fin_min_val)
        fmax = math.ceil(fin_max_val)
        financed_range = st.slider("Sum of Amount Financed", fmin, fmax, (fmin, fmax))
        mask = (df_home["Sum of Amount Financed"] >= financed_range[0]) & (df_home["Sum of Amount Financed"] <= financed_range[1])
        df_home = apply_filter(df_home, mask, f"Sum of Amount Financed in [{financed_range[0]}, {financed_range[1]}]")

    # ------------------------------------------------------------------
    # 8) HOME VALUE: First parse and handle numeric slider
    # ------------------------------------------------------------------
    if "Home Value" in df_home.columns:
        # Keep original in HV_original
        df_home["HV_original"] = df_home["Home Value"].astype(str)
        # Attempt parse => NaN if not numeric
        df_home["HV_numeric"] = pd.to_numeric(df_home["Home Value"], errors="coerce")

        # Identify any non-numeric
        non_numeric_mask = df_home["HV_numeric"].isna()
        non_numeric_vals = sorted(df_home.loc[non_numeric_mask, "HV_original"].unique())

        # Map each distinct non-numeric text to a unique negative code
        text2neg = {}
        for i, txt in enumerate(non_numeric_vals, start=1):
            text2neg[txt] = -float(i)

        # Convert HV_numeric so that non-numerics become negative codes
        def to_hv_numeric(row):
            if pd.isna(row["HV_numeric"]):
                return text2neg[row["HV_original"]]
            else:
                return row["HV_numeric"]
        df_home["HV_numeric"] = df_home.apply(to_hv_numeric, axis=1)

        # Now display the slider for the numeric portion:
        # We'll only consider the positive portion in this slider
        # so the user can filter "normal" numeric home values
        st.markdown("### Numeric Home Value Range")
        pos_mask = (df_home["HV_numeric"] > 0)
        if pos_mask.any():
            hv_min = df_home.loc[pos_mask, "HV_numeric"].min()
            hv_max = df_home.loc[pos_mask, "HV_numeric"].max()
            hv_floor = math.floor(hv_min)
            hv_ceil = math.ceil(hv_max)
            hv_range = st.slider(
                "Numeric Home Value Range",
                float(hv_floor),
                float(hv_ceil),
                (float(hv_floor), float(hv_ceil))
            )
        else:
            hv_range = (0.0, 0.0)
            st.info("No positive numeric home values found.")

        # ------------------------------------------------------------------
        # 9) Non-Numeric Home Value Checkboxes
        # ------------------------------------------------------------------
        st.markdown("### Non‐Numeric Home Values")
        st.write("(Check each one you want to keep)")

        keep_map = {}
        for txt in non_numeric_vals:
            neg_code = text2neg[txt]
            label = f"Include '{txt}'"
            is_checked = st.checkbox(label, value=True)
            keep_map[neg_code] = is_checked

        # Build final mask
        def hv_filter(row):
            val = row["HV_numeric"]
            if val < 0:
                # negative means non-numeric => keep only if its checkbox is selected
                return keep_map.get(val, False)
            else:
                # numeric => keep if in the user-chosen range
                return (val >= hv_range[0]) and (val <= hv_range[1])

        hv_mask = df_home.apply(hv_filter, axis=1)
        df_home = apply_filter(df_home, hv_mask, "Home Value (numeric slider + checkboxes)")

    # ------------------------------------------------------------------
    # Wrap up
    # ------------------------------------------------------------------
    final_count = len(df_home)
    removed_total = original_count - final_count
    st.write(f"**Filtered Results**: {final_count} row(s) out of {original_count} originally.")
    st.write(f"**Total Removed**: {removed_total} row(s).")

    # Show breakdown of removed sets
    if filter_removals:
        st.write("### Rows Removed by Each Filter")
        for (reason, removed_df) in filter_removals:
            if not removed_df.empty:
                with st.expander(f"{len(removed_df)} row(s) removed by {reason}"):
                    st.dataframe(removed_df)

    # If empty => stop
    if df_home.empty:
        st.warning("No data left after filters.")
        return

    # Summaries for TSW statuses
    if "TSWcontractStatus" in df_home.columns:
        total_remaining = len(df_home)
        active_count = len(df_home[df_home["TSWcontractStatus"] == "Active"])
        defaulted_count = len(df_home[df_home["TSWcontractStatus"] == "Defaulted"])
        if total_remaining > 0:
            active_pct = (active_count / total_remaining) * 100
            defaulted_pct = (defaulted_count / total_remaining) * 100
        else:
            active_pct = 0
            defaulted_pct = 0

        st.write(
            f"**Active**: {active_count} ({active_pct:.2f}%) | "
            f"**Defaulted**: {defaulted_count} ({defaulted_pct:.2f}%)"
        )

    # ------------------------------------------------------------------
    # MAP
    # ------------------------------------------------------------------
    if "Latitude" not in df_home.columns or "Longitude" not in df_home.columns:
        st.info("No latitude/longitude columns. Cannot map.")
        return

    before_map = len(df_home)
    map_df = df_home.dropna(subset=["Latitude","Longitude"])
    exclude_map = before_map - len(map_df)
    if exclude_map > 0:
        st.write(f"Excluded {exclude_map} row(s) missing lat/lon for map display.")

    if map_df.empty:
        st.warning("No rows with valid lat/lon to plot.")
        return

    # Use a color map for TSW statuses
    color_map = {
        "Active": "#90ee90",     # light green
        "Defaulted": "#ff9999"  # light red
    }
    hover_cols = [
        "OwnerName", "Last Name 1", "First Name 1", "Last Name 2", "First Name 2",
        "FICO", "Home Value", "HV_original", "HV_numeric",
        "Distance in Miles", "Sum of Amount Financed",
        "TSWpaymentAmount", "TSWcontractStatus",
        "Address", "City", "State", "Zip Code"
    ]
    hover_cols = [c for c in hover_cols if c in map_df.columns]

    fig = px.scatter_mapbox(
        map_df,
        lat="Latitude",
        lon="Longitude",
        hover_data=hover_cols,
        color="TSWcontractStatus",
        color_discrete_map=color_map,
        zoom=4,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0, "t":0, "l":0, "b":0})
    st.plotly_chart(fig, use_container_width=True)

    # Show final data in an expander at the bottom
    with st.expander("Show Included Data After Filtering"):
        st.dataframe(df_home)

# Streamlit entrypoint
if __name__ == "__main__":
    run_owners_map()
