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

    # 1) Keep the original text so we know what was non-numeric
    df["HV_original"] = df["Home Value"].astype(str)

    # 2) Attempt numeric => NaN if not numeric
    df["HV_numeric"] = pd.to_numeric(df["Home Value"], errors="coerce")

    # 3) Identify which rows are truly non‐numeric
    non_numeric_df = df[df["HV_numeric"].isna()].copy()
    unique_non_numeric_vals = sorted(non_numeric_df["HV_original"].unique())

    # 4) Build a dictionary giving each distinct string a unique negative code
    # For instance, "Apartment" => -1, "Not available" => -2, etc.
    # Obviously you can shift by 1 if you prefer
    text2neg = {}
    for i, val in enumerate(unique_non_numeric_vals, start=1):
        text2neg[val] = -float(i)  # e.g. "Apartment" => -1.0, "PO Box" => -2.0, etc.

    # 5) Overwrite HV_numeric in non‐numeric rows with that distinct negative code
    def get_hv_numeric(row):
        if pd.isna(row["HV_numeric"]):  # means it was non‐numeric
            return text2neg[row["HV_original"]]
        else:
            return row["HV_numeric"]

    df["HV_numeric"] = df.apply(get_hv_numeric, axis=1)

    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    # Rename lat/lon if needed
    if "Origin Latitude" in df.columns and "Origin Longitude" in df.columns:
        df.rename(columns={"Origin Latitude":"Latitude",
                           "Origin Longitude":"Longitude"}, inplace=True)

    if "Latitude" in df.columns:
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    if "Longitude" in df.columns:
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    # Now we do the standard filters (State, FICO, etc.), but focusing on Home Value:
    st.subheader("Filters")

    # Example: State filter
    if "State" in df.columns:
        all_states = sorted(df["State"].dropna().unique())
        chosen_states = st.multiselect("Filter by State(s)", all_states, default=all_states)
        df = df[df["State"].isin(chosen_states)]

    # [Add other filters as you wish, e.g. FICO slider, Payment slider, etc.]

    # ============ Home Value Filters ============

    st.write("#### Home Value Filters")

    # A) Let the user pick which negative codes (strings) to keep
    # We'll build a checkbox for each non‐numeric text
    # We'll store the user choices in a dict: {val: True/False}
    keep_map = {}
    for val in unique_non_numeric_vals:
        neg_code = text2neg[val]
        default_checked = True  # or however you want
        is_checked = st.checkbox(f"Include '{val}'", value=default_checked)
        keep_map[neg_code] = is_checked

    # B) Numeric slider for all positive HV_numeric
    numeric_mask = (df["HV_numeric"] > 0)
    if numeric_mask.any():
        hv_min = df.loc[numeric_mask, "HV_numeric"].min()
        hv_max = df.loc[numeric_mask, "HV_numeric"].max()
        # Round for integer slider or keep float
        hv_floor = math.floor(hv_min)
        hv_ceil = math.ceil(hv_max)
        hv_range = st.slider("Home Value (Positive Only)",
                             float(hv_floor),
                             float(hv_ceil),
                             (float(hv_floor), float(hv_ceil)))
    else:
        hv_range = (0,0)
        st.info("No positive home values found.")

    # Now unify the final mask:
    #  1) If HV_numeric > 0, it must be within hv_range
    #  2) If HV_numeric < 0 => it's one of the negative codes => user must have checked that code
    mask_pos = (df["HV_numeric"] > 0) & \
               (df["HV_numeric"] >= hv_range[0]) & \
               (df["HV_numeric"] <= hv_range[1])
    # For negative codes
    mask_neg = df["HV_numeric"] < 0

    # We only keep negative-coded rows if the user has "Include 'text'" checked
    # So we build a mask that says: HV_numeric < 0 AND keep_map[that code] is True
    # We'll do that row by row
    def keep_this_row(row):
        val = row["HV_numeric"]
        if val < 0:
            # If the user left that box checked => keep it
            return keep_map.get(val, False)
        else:
            return False  # handled in mask_pos

    # apply keep_this_row only to negative rows
    # simpler approach => apply row by row
    keep_neg_series = df.apply(keep_this_row, axis=1)

    # final mask => either is in the positive range OR is in the negative-coded keep list
    df_filtered = df[mask_pos | keep_neg_series]

    st.write(f"**Filtered Results**: {len(df_filtered)} row(s) out of {original_count} originally.")
    st.dataframe(df_filtered.head(20))

    if df_filtered.empty:
        st.warning("No data left after filters.")
        return

    # -------- Plot map -----------
    if "Latitude" not in df_filtered.columns or "Longitude" not in df_filtered.columns:
        st.info("No lat/lon columns. Cannot map.")
        return

    map_df = df_filtered.dropna(subset=["Latitude","Longitude"])
    if map_df.empty:
        st.warning("No valid lat/lon to show on map.")
        return

    # color by TSW contract status, for instance
    color_map = {
        "Active": "#90ee90",
        "Defaulted": "#ff9999"
    }
    hover_cols = [
        "OwnerName","HV_original","HV_numeric","TSWcontractStatus","FICO","Address"
    ]
    hover_cols = [c for c in hover_cols if c in map_df.columns]

    fig = px.scatter_mapbox(
        map_df,
        lat="Latitude",
        lon="Longitude",
        color="TSWcontractStatus",
        color_discrete_map=color_map,
        hover_data=hover_cols,
        zoom=4,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    run_owners_map()
