import streamlit as st
import pandas as pd
import plotly.express as px
import os

def run_owners_map():
    st.title("Timeshare Owners Map")

    file_path = "Owners home value and driving distance.xlsx"
    if not os.path.exists(file_path):
        st.error(f"File not found: {file_path}")
        st.stop()

    df = pd.read_excel(file_path)
    original_count = len(df)

    # Keep track of what each filter removes
    filter_messages = []
    def apply_filter(df, mask, desc):
        before = len(df)
        out = df[mask]
        removed = before - len(out)
        if removed:
            filter_messages.append(f"- {removed} row(s) removed by {desc}")
        return out

    # Rename lat/lon if needed
    if "Origin Latitude" in df.columns and "Origin Longitude" in df.columns:
        df.rename(columns={"Origin Latitude":"Latitude", "Origin Longitude":"Longitude"}, inplace=True)

    st.subheader("Data Preview")
    st.dataframe(df.head(10))

    # Convert lat/lon
    if "Latitude" in df.columns:
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    if "Longitude" in df.columns:
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")

    st.subheader("Filters")

    # ---- State Filter ----
    if "State" in df.columns:
        unique_states = sorted(df["State"].dropna().unique())
        selected_states = st.multiselect("Filter by State(s)", unique_states, default=unique_states)
        df = apply_filter(df, df["State"].isin(selected_states), f"State filter: {selected_states}")

    # ---- TSW Status Filter ----
    if "TSWcontractStatus" in df.columns:
        status_opts = ["Active", "Defaulted", "Both"]
        chosen_status = st.selectbox("Filter by Contract Status", status_opts, index=2)
        if chosen_status != "Both":
            df = apply_filter(df, df["TSWcontractStatus"] == chosen_status, f"TSW Status={chosen_status}")

    # ---- FICO Filter ----
    if "FICO" in df.columns:
        min_fico = df["FICO"].min()
        max_fico = df["FICO"].max()
        fico_slider = st.slider("FICO Range", int(min_fico), int(max_fico), (int(min_fico), int(max_fico)))
        df = apply_filter(df, (df["FICO"] >= fico_slider[0]) & (df["FICO"] <= fico_slider[1]),
                          f"FICO in [{fico_slider[0]}, {fico_slider[1]}]")

    # ---- Distance Filter ----
    if "Distance in Miles" in df.columns:
        min_d = df["Distance in Miles"].min()
        max_d = df["Distance in Miles"].max()
        dist_slider = st.slider("Distance in Miles", int(min_d), int(max_d), (int(min_d), int(max_d)))
        df = apply_filter(df, (df["Distance in Miles"] >= dist_slider[0]) & (df["Distance in Miles"] <= dist_slider[1]),
                          f"Distance in [{dist_slider[0]}, {dist_slider[1]}]")

    # ---- TSW Payment Filter (fill blanks with 0) ----
    if "TSWpaymentAmount" in df.columns:
        df["TSWpaymentAmount"] = pd.to_numeric(df["TSWpaymentAmount"], errors="coerce").fillna(0)
        min_pay = df["TSWpaymentAmount"].min()
        max_pay = df["TSWpaymentAmount"].max()
        pay_slider = st.slider("TSW Payment Amount", int(min_pay), int(max_pay), (int(min_pay), int(max_pay)))
        df = apply_filter(df, (df["TSWpaymentAmount"] >= pay_slider[0]) & (df["TSWpaymentAmount"] <= pay_slider[1]),
                          f"TSW Payment in [{pay_slider[0]}, {pay_slider[1]}]")

    # ---- Sum of Amount Financed ----
    if "Sum of Amount Financed" in df.columns:
        mn = df["Sum of Amount Financed"].min()
        mx = df["Sum of Amount Financed"].max()
        fin_slider = st.slider("Sum of Amount Financed", int(mn), int(mx), (int(mn), int(mx)))
        df = apply_filter(df, (df["Sum of Amount Financed"] >= fin_slider[0]) & (df["Sum of Amount Financed"] <= fin_slider[1]),
                          f"Financed in [{fin_slider[0]}, {fin_slider[1]}]")

    # ---- Home Value ----
    if "Home Value" in df.columns:
        df["Home Value"] = pd.to_numeric(df["Home Value"], errors="coerce").fillna(-1)
        pos_mask = df["Home Value"] > 0
        if pos_mask.any():
            hv_min = df.loc[pos_mask, "Home Value"].min()
            hv_max = df.loc[pos_mask, "Home Value"].max()
            hv_slider = st.slider("Home Value (Positive Only)", float(hv_min), float(hv_max), (float(hv_min), float(hv_max)))
        else:
            hv_slider = (0,0)
            st.info("No positive Home Values found.")
        inc_neg = st.checkbox("Include Non-Numeric (Negative) Home Values?", True)

        mask_pos = (df["Home Value"] > 0) & (df["Home Value"] >= hv_slider[0]) & (df["Home Value"] <= hv_slider[1])
        mask_neg = (df["Home Value"] < 0) & inc_neg
        df = apply_filter(df, mask_pos | mask_neg,
                          f"Home Value in [{hv_slider[0]}, {hv_slider[1]}], negative={inc_neg}")

    # Show final results
    final_count = len(df)
    excluded_total = original_count - final_count
    st.write(f"**Filtered Results**: {final_count} of {original_count} originally.")
    st.write(f"**Total Removed**: {excluded_total} row(s).")

    if filter_messages:
        st.write("**Filter Breakdown**:")
        for msg in filter_messages:
            st.write(msg)

    st.dataframe(df.head(20))

    if df.empty:
        st.warning("No data left after filters.")
        return

    # ---- Build Map ----
    if "Latitude" not in df.columns or "Longitude" not in df.columns:
        st.info("No lat/lon columns. Cannot show map.")
        return

    before_map = len(df)
    map_df = df.dropna(subset=["Latitude","Longitude"])
    excluded_map = before_map - len(map_df)
    if excluded_map > 0:
        st.write(f"Excluded {excluded_map} row(s) missing lat/lon for map.")

    if map_df.empty:
        st.warning("No rows with valid lat/lon to show on map.")
        return

    # Step A: define a function to pick each row's exact hex color
    def pick_color(status):
        # handle possible whitespace or case differences
        s = str(status).strip().lower()
        if s == "active":
            return "#90ee90"   # light green
        elif s == "defaulted":
            return "#ff9999"  # light red
        # fallback
        return "#808080"     # gray or something

    # create a column with the row color
    map_df["MapColor"] = map_df["TSWcontractStatus"].apply(pick_color)

    hover_cols = [
        "OwnerName","Last Name 1","First Name 1","Last Name 2","First Name 2",
        "FICO","Home Value","Distance in Miles","Sum of Amount Financed",
        "TSWpaymentAmount","TSWcontractStatus","Address","City","State","Zip Code"
    ]
    hover_cols = [c for c in hover_cols if c in map_df.columns]

    # Create the figure WITHOUT a color= param
    fig = px.scatter_mapbox(
        map_df,
        lat="Latitude",
        lon="Longitude",
        hover_data=hover_cols,
        # do not pass color=..., else Plotly picks its own color scale
        zoom=4,
        height=600
    )

    # Force each marker to use our "MapColor" column
    # and maybe set a marker size if you want (like 7)
    fig.update_traces(
        marker=dict(size=7, color=map_df["MapColor"]),
        selector=dict(mode='markers')
    )

    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    run_owners_map()
