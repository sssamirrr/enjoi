import streamlit as st
import pandas as pd
import plotly.express as px
import os
import math

def run_owners_map():
    st.title("Timeshare Owners Map")

    file_path = "Owners home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    df = pd.read_excel(file_path)
    original_count = len(df)

    # For displaying each filter's removals
    filter_removals = []
    def apply_filter(df, mask, reason):
        kept = df[mask]
        removed = df[~mask]
        if len(removed) > 0:
            filter_removals.append((reason, removed.copy()))
        return kept

    # ------------------
    # 1) PREP lat/lon
    # ------------------
    if "Origin Latitude" in df.columns and "Origin Longitude" in df.columns:
        df.rename(columns={
            "Origin Latitude": "Latitude",
            "Origin Longitude": "Longitude"
        }, inplace=True)

    df["Latitude"] = pd.to_numeric(df.get("Latitude"), errors="coerce")
    df["Longitude"] = pd.to_numeric(df.get("Longitude"), errors="coerce")

    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    st.subheader("Filters")

    # ------------------
    # 2) State Filter
    # ------------------
    if "State" in df.columns:
        unique_states = sorted(df["State"].dropna().unique())
        selected_states = st.multiselect(
            "Filter by State(s)",
            options=unique_states,
            default=unique_states
        )
        mask = df["State"].isin(selected_states)
        df = apply_filter(df, mask, f"State filter: {selected_states}")

    # ------------------
    # 3) TSW Contract Status Filter
    # ------------------
    if "TSWcontractStatus" in df.columns:
        status_options = ["Active", "Defaulted", "Both"]
        chosen_status = st.selectbox(
            "Filter by Contract Status",
            status_options,
            index=2
        )
        if chosen_status != "Both":
            mask = (df["TSWcontractStatus"] == chosen_status)
            df = apply_filter(df, mask, f"TSWcontractStatus = {chosen_status}")

    # ------------------
    # 4) FICO Slider
    # ------------------
    if "FICO" in df.columns:
        min_fico_val = df["FICO"].min()
        max_fico_val = df["FICO"].max()
        fico_min = math.floor(min_fico_val)
        fico_max = math.ceil(max_fico_val)
        fico_range = st.slider(
            "FICO Range",
            fico_min,
            fico_max,
            (fico_min, fico_max)
        )
        mask = (df["FICO"] >= fico_range[0]) & (df["FICO"] <= fico_range[1])
        df = apply_filter(df, mask, f"FICO in [{fico_range[0]}, {fico_range[1]}]")

    # ------------------
    # 5) Distance in Miles
    # ------------------
    if "Distance in Miles" in df.columns:
        dist_min_val = df["Distance in Miles"].min()
        dist_max_val = df["Distance in Miles"].max()
        dmin = math.floor(dist_min_val)
        dmax = math.ceil(dist_max_val)
        dist_range = st.slider(
            "Distance in Miles",
            dmin, dmax, (dmin, dmax)
        )
        mask = (df["Distance in Miles"] >= dist_range[0]) & \
               (df["Distance in Miles"] <= dist_range[1])
        df = apply_filter(df, mask, f"Distance in [{dist_range[0]}, {dist_range[1]}]")

    # ------------------
    # 6) TSW Payment Amount
    # ------------------
    if "TSWpaymentAmount" in df.columns:
        df["TSWpaymentAmount"] = pd.to_numeric(df["TSWpaymentAmount"], errors="coerce").fillna(0)
        pay_min_val = df["TSWpaymentAmount"].min()
        pay_max_val = df["TSWpaymentAmount"].max()
        pmin = math.floor(pay_min_val)
        pmax = math.ceil(pay_max_val)
        pay_range = st.slider("TSW Payment Amount",
                              pmin, pmax, (pmin, pmax))
        mask = (df["TSWpaymentAmount"] >= pay_range[0]) & \
               (df["TSWpaymentAmount"] <= pay_range[1])
        df = apply_filter(df, mask, f"TSWpaymentAmount in [{pay_range[0]}, {pay_range[1]}]")

    # ------------------
    # 7) Sum of Amount Financed
    # ------------------
    if "Sum of Amount Financed" in df.columns:
        fin_min_val = df["Sum of Amount Financed"].min()
        fin_max_val = df["Sum of Amount Financed"].max()
        fmin = math.floor(fin_min_val)
        fmax = math.ceil(fin_max_val)
        financed_range = st.slider("Sum of Amount Financed",
                                   fmin, fmax, (fmin, fmax))
        mask = (df["Sum of Amount Financed"] >= financed_range[0]) & \
               (df["Sum of Amount Financed"] <= financed_range[1])
        df = apply_filter(df, mask,
            f"Sum of Amount Financed in [{financed_range[0]}, {financed_range[1]}]")

    # -------------------------------------------------
    # 8) HOME VALUE LOGIC: Non-numeric => unique negative codes
    # -------------------------------------------------
    if "Home Value" in df.columns:
        st.markdown("### Home Value Filters (numeric & non‐numeric)")

        # (a) keep original
        df["HV_original"] = df["Home Value"].astype(str)

        # (b) parse numeric => NaN if not numeric
        df["HV_numeric"] = pd.to_numeric(df["Home Value"], errors="coerce")

        # (c) find distinct texts
        non_numeric_mask = df["HV_numeric"].isna()
        non_numeric_vals = sorted(df.loc[non_numeric_mask, "HV_original"].unique())

        # (d) assign negative codes
        text2neg = {}
        for i, txt in enumerate(non_numeric_vals, start=1):
            text2neg[txt] = -float(i)  # e.g. -1.0, -2.0, etc.

        # (e) transform HV_numeric for non-numerics
        def to_hv_numeric(row):
            if pd.isna(row["HV_numeric"]):
                return text2neg[row["HV_original"]]
            else:
                return row["HV_numeric"]

        df["HV_numeric"] = df.apply(to_hv_numeric, axis=1)

        # Let user exclude all positives if they want
        exclude_positive = st.checkbox("Exclude rows with any positive (numeric) Home Value?")

        # Build checkboxes for each distinct non‐numeric text
        st.write("#### Non‐Numeric Home Values to Include?")
        keep_map = {}
        for txt in non_numeric_vals:
            neg_code = text2neg[txt]
            is_checked = st.checkbox(f"Include '{txt}' (code={neg_code})", value=True)
            keep_map[neg_code] = is_checked

        # If we are not excluding positives entirely => let them choose a slider
        # for positive HV
        if not exclude_positive:
            # gather only positive rows
            pos_mask = df["HV_numeric"] > 0
            if pos_mask.any():
                hv_min = df.loc[pos_mask, "HV_numeric"].min()
                hv_max = df.loc[pos_mask, "HV_numeric"].max()
                hv_floor = math.floor(hv_min)
                hv_ceil = math.ceil(hv_max)
                hv_range = st.slider(
                    "Home Value Range (Positive Only)",
                    float(hv_floor), float(hv_ceil),
                    (float(hv_floor), float(hv_ceil))
                )
            else:
                hv_range = (0, 0)
                st.info("No positive Home Values found.")
        else:
            hv_range = (0, 0)

        # Combine final filter for HV:
        #    if exclude_positive => keep only negative-coded rows
        #    else => keep negative-coded rows if user left them checked
        #            keep positive rows if within hv_range
        def hv_filter(row):
            val = row["HV_numeric"]
            if val < 0:
                # only keep if the user’s checkbox is True
                return keep_map.get(val, False)
            else:
                # it's positive or zero
                if exclude_positive:
                    return False
                else:
                    # must be within slider range
                    return (val >= hv_range[0]) and (val <= hv_range[1])

        hv_mask = df.apply(hv_filter, axis=1)
        df = apply_filter(df, hv_mask,
            f"Home Value Filter exclude_positive={exclude_positive}")

    # -------------------------------------------------------
    # Display final
    # -------------------------------------------------------
    final_count = len(df)
    removed_total = original_count - final_count
    st.write(f"**Filtered Results**: {final_count} row(s) out of {original_count} originally.")
    st.write(f"**Total Removed**: {removed_total} row(s).")

    if filter_removals:
        st.write("### Rows Removed by Each Filter")
        for (reason, removed_df) in filter_removals:
            if len(removed_df) > 0:
                with st.expander(f"{len(removed_df)} row(s) removed by {reason}"):
                    st.dataframe(removed_df)

    st.dataframe(df.head(20))
    if df.empty:
        st.warning("No data left after filters.")
        return

    # -------------- Summaries for TSW statuses --------------
    if "TSWcontractStatus" in df.columns:
        total_remaining = len(df)
        active_count = len(df[df["TSWcontractStatus"] == "Active"])
        defaulted_count = len(df[df["TSWcontractStatus"] == "Defaulted"])

        # Compute percentages if total_remaining > 0
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

    # -------------- MAP --------------
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        st.info("No latitude/longitude columns. Cannot map.")
        return

    before_map = len(df)
    map_df = df.dropna(subset=["Latitude","Longitude"])
    exclude_map = before_map - len(map_df)
    if exclude_map > 0:
        st.write(f"Excluded {exclude_map} row(s) missing lat/lon for map display.")

    if map_df.empty:
        st.warning("No rows with valid lat/lon to plot.")
        return

    # color by TSWcontractStatus
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


# Entry point
if __name__ == "__main__":
    run_owners_map()
