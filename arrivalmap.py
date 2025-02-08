import streamlit as st
import pandas as pd
import plotly.express as px
import io
import time
import http.client
import json


############################################
# 1) RAPIDAPI CONFIG
############################################
RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"  # <-- Your hardcoded key
RAPIDAPI_HOST = "google-maps-geocoding3.p.rapidapi.com"

def geocode_address_rapidapi(address: str):
    """
    Geocode a single address using the RapidAPI "google-maps-geocoding3" endpoint.
    Returns (latitude, longitude) or (None, None) if not found or error.
    
    We enforce ~8 calls/sec by sleeping 0.125s between calls.
    """
    if not address:
        return None, None

    # ~8 calls per second
    time.sleep(0.125)
    try:
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
        headers = {
            'x-rapidapi-key': RAPIDAPI_KEY,
            'x-rapidapi-host': RAPIDAPI_HOST
        }
        # URL-encode spaces
        endpoint = f"/geocode?address={address.replace(' ', '%20')}"
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()

        json_data = json.loads(data.decode("utf-8"))
        # If 'latitude'/'longitude' keys exist
        if "latitude" in json_data and "longitude" in json_data:
            return json_data["latitude"], json_data["longitude"]
        else:
            return None, None
    except Exception as e:
        st.write(f"Error geocoding '{address}': {e}")
        return None, None


def geocode_dataframe_rapidapi(df_input: pd.DataFrame) -> pd.DataFrame:
    """
    Geocode the DataFrame's 'Full_Address' column using RapidAPI.
    - Skip rows that already have Latitude/Longitude.
    - Skip rows that have an empty 'Full_Address'.
    - Shows row-by-row progress and logs.
    - Rate limit: ~8 calls/sec.
    """
    df = df_input.copy()

    # Ensure columns for lat/lon exist
    if "Latitude" not in df.columns:
        df["Latitude"] = None
    if "Longitude" not in df.columns:
        df["Longitude"] = None

    n_rows = len(df)
    if n_rows == 0:
        return df

    st.write(f"**Total rows to process:** {n_rows}")
    progress_bar = st.progress(0)

    for i, row in df.iterrows():
        # Already have lat/lon?
        if pd.notnull(row["Latitude"]) and pd.notnull(row["Longitude"]):
            st.write(f"Row {i+1}/{n_rows}: Already has lat/lon, skipping.")
        else:
            address = row.get("Full_Address", "")
            if not address.strip():  # empty address
                st.write(f"Row {i+1}/{n_rows}: Empty address, skipping.")
            else:
                st.write(f"Row {i+1}/{n_rows}: Geocoding '{address}'...")
                lat, lon = geocode_address_rapidapi(address)
                df.at[i, "Latitude"] = lat
                df.at[i, "Longitude"] = lon

        # Update progress bar
        progress_bar.progress((i+1) / n_rows)

    st.success("Geocoding complete!")
    return df


############################################
# 2) MAIN STREAMLIT APP
############################################
def run_arrival_map():
    st.title("📍 Arrival Map (RapidAPI ~8 calls/sec)")

    st.markdown("""
    **Instructions**:
    1. Upload an Excel file with at least these columns:
       - **Address1**, **City**, **State**, **Zip Code**
       - **Market** (used for coloring dots)
       - **Total Stay Value With Taxes (Base)** (Ticket Value)
       - (Optionally) **Home Value** for additional filter/hover info.
    2. We'll build a **Full_Address**, then geocode each row via **RapidAPI** 
       at ~8 requests/sec, showing row-by-row progress (skipping empty or 
       already-geocoded rows).
    3. You can filter by State, Market, Ticket Value, and optionally Home Value.
    4. We show how many dots appear & let you download the geocoded data as Excel.
    """)

    # 1) File uploader
    uploaded_file = st.file_uploader("📂 Upload Excel File (xlsx/xls)", type=["xlsx", "xls"])
    if not uploaded_file:
        st.info("Please upload a valid Excel file to proceed.")
        return

    # 2) Read the Excel into a DataFrame
    try:
        df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")
        return

    st.subheader("Preview of Uploaded Data")
    st.dataframe(df.head(10))

    # 3) Check required columns
    required_cols = [
        "Address1", 
        "City", 
        "State", 
        "Zip Code", 
        "Market", 
        "Total Stay Value With Taxes (Base)"
    ]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"Missing required columns: {missing_cols}")
        return

    # 4) Clean up address columns
    df["Address1"] = df["Address1"].fillna("").astype(str).str.strip()
    df["City"]     = df["City"].fillna("").astype(str).str.strip()
    df["State"]    = df["State"].fillna("").astype(str).str.strip()
    df["Zip Code"] = (
        df["Zip Code"]
        .fillna("")
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # Create a "Full_Address" column
    df["Full_Address"] = (
        df["Address1"] + ", "
        + df["City"] + ", "
        + df["State"] + " "
        + df["Zip Code"]
    ).str.strip()

    st.subheader("Full Addresses")
    show_cols = ["Full_Address", "Market", "Total Stay Value With Taxes (Base)"]
    if "Home Value" in df.columns:
        show_cols.append("Home Value")  # Show it if present
    st.dataframe(df[show_cols].head(10))

    # 5) Geocode with RapidAPI (show progress/log)
    st.info("Geocoding addresses via RapidAPI (~8 calls/sec).")
    df_geocoded = geocode_dataframe_rapidapi(df)

    # Drop rows with missing lat/lon for the map
    df_map = df_geocoded.dropna(subset=["Latitude","Longitude"]).copy()

    # 6) Filters
    # State filter
    unique_states = sorted(df_map["State"].dropna().unique())
    state_filter = st.multiselect(
        "Filter by State(s)",
        options=unique_states,
        default=unique_states
    )

    # Market filter
    unique_markets = sorted(df_map["Market"].dropna().unique())
    market_filter = st.multiselect(
        "Filter by Market(s)",
        options=unique_markets,
        default=unique_markets
    )

    # Ticket Value slider
    min_ticket = float(df_map["Total Stay Value With Taxes (Base)"].min() or 0)
    max_ticket = float(df_map["Total Stay Value With Taxes (Base)"].max() or 0)
    ticket_value_range = st.slider(
        "Filter by Ticket Value",
        min_value=min_ticket,
        max_value=max_ticket,
        value=(min_ticket, max_ticket)
    )

    # Home Value (if present)
    home_value_exists = "Home Value" in df_map.columns
    if home_value_exists:
        st.subheader("Home Value Filter")
        home_val_min = float(df_map["Home Value"].min() or 0)
        home_val_max = float(df_map["Home Value"].max() or 0)
        home_value_range = st.slider(
            "Home Value Range",
            min_value=home_val_min,
            max_value=home_val_max,
            value=(home_val_min, home_val_max)
        )

    # Apply the filters
    df_filtered = df_map[
        (df_map["State"].isin(state_filter)) &
        (df_map["Market"].isin(market_filter)) &
        (df_map["Total Stay Value With Taxes (Base)"] >= ticket_value_range[0]) &
        (df_map["Total Stay Value With Taxes (Base)"] <= ticket_value_range[1])
    ]

    if home_value_exists:
        df_filtered = df_filtered[
            (df_filtered["Home Value"] >= home_value_range[0]) &
            (df_filtered["Home Value"] <= home_value_range[1])
        ]

    st.subheader("Filtered Data for Map")
    num_dots = len(df_filtered)
    st.write(f"**Number of dots on the map:** {num_dots}")
    st.dataframe(df_filtered.head(20))

    if df_filtered.empty:
        st.warning("No data after applying filters. Adjust filters above.")
        return

    # 7) Plotly map
    st.subheader("📍 Map of Addresses")

    # Which columns to show in hover_data
    hover_data_cols = ["State", "Total Stay Value With Taxes (Base)"]
    if home_value_exists:
        hover_data_cols.append("Home Value")

    fig = px.scatter_mapbox(
        df_filtered,
        lat="Latitude",
        lon="Longitude",
        color="Market",
        hover_name="Full_Address",
        hover_data=hover_data_cols,
        zoom=3,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0, "t":0, "l":0, "b":0})

    st.plotly_chart(fig, use_container_width=True)

    # 8) Download the geocoded dataset
    st.subheader("⬇️ Download Geocoded Excel")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_geocoded.to_excel(writer, index=False, sheet_name="GeocodedData")
    output.seek(0)

    st.download_button(
        label="Download Excel (Geocoded)",
        data=output.getvalue(),
        file_name="arrival_map_geocoded.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


if __name__ == "__main__":
    run_arrival_map()
