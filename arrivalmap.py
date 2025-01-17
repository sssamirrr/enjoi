import streamlit as st
import pandas as pd
import plotly.express as px
import io
import time
import json
import urllib.parse
import http.client

############################################
# 1) CACHED FUNCTION TO GEOCODE
############################################
@st.cache_data
def geocode_addresses(
    df_input: pd.DataFrame,
    rapidapi_key: str,
    rapidapi_host: str
) -> pd.DataFrame:
    """
    Geocode rows that do NOT already have Latitude/Longitude.
    Uses google-maps-geocoding3 API at 2 requests/second => time.sleep(0.5).
    Returns the updated DataFrame with 'Latitude' / 'Longitude' columns.
    """

    df = df_input.copy()

    # Ensure columns exist
    if "Latitude" not in df.columns:
        df["Latitude"] = None
    if "Longitude" not in df.columns:
        df["Longitude"] = None

    # Shared headers for RapidAPI
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": rapidapi_host
    }

    # Iterate over rows
    for idx, row in df.iterrows():
        lat = row.get("Latitude")
        lon = row.get("Longitude")

        # If already geocoded, skip
        if pd.notna(lat) and pd.notna(lon):
            continue

        full_addr = row.get("Full_Address", "")
        if not full_addr:
            # If there's no address, skip
            continue

        # 2 requests per second => sleep 0.5
        time.sleep(0.5)

        # Build the connection
        conn = http.client.HTTPSConnection(rapidapi_host)

        # Encode address for the URL
        encoded_address = urllib.parse.quote(full_addr)
        path = f"/geocode?address={encoded_address}"

        try:
            conn.request("GET", path, headers=headers)
            res = conn.getresponse()
            data_bytes = res.read()
            data_str = data_bytes.decode("utf-8")
            data_json = json.loads(data_str)

            results = data_json.get("results", [])
            if len(results) > 0:
                geom = results[0].get("geometry", {})
                loc = geom.get("location", {})
                latitude = loc.get("lat")
                longitude = loc.get("lng")

                df.at[idx, "Latitude"] = latitude
                df.at[idx, "Longitude"] = longitude

        except Exception as e:
            # If error, just keep None
            pass
        finally:
            conn.close()

    return df


############################################
# 2) MAIN STREAMLIT APP
############################################
def run_arrival_map():
    """
    Streamlit app that:
      - Uploads an Excel file
      - Builds 'Full_Address' from Address1 + City + State + Zip Code
      - Geocodes only rows that have no lat/lon
      - Rate = 2 requests/second => time.sleep(0.5)
      - Hardcoded API key
      - Skips re-geocoding pre-geocoded rows
      - Caches results so filters won't re-geocode
      - Lets user filter by State, Market, Ticket Value
      - Plots on a map, shows dot count
      - Download geocoded Excel
    """

    st.title("📍 Arrival Map (2 req/sec, Hardcoded API Key, Skip Pre-Geocoded Rows)")

    st.markdown("""
    **Instructions**:
    1. **Upload** an Excel file with:
       - **Address1**, **City**, **State**, **Zip Code**
       - **Market**, **Total Stay Value With Taxes (Base)**
       - Optionally, **Latitude**, **Longitude** (rows with these won't be re-geocoded).
    2. We build **Full_Address** (Address1 + City + State + Zip).
    3. If **Latitude** or **Longitude** is missing, we geocode that row at **2 requests/sec** 
       using **google-maps-geocoding3** on RapidAPI.
    4. We **cache** results. Changing filters won't trigger new geocoding 
       unless you upload a different Excel.
    """)

    # HARDCODED API credentials:
    RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"   # <--- your key
    RAPIDAPI_HOST = "google-maps-geocoding3.p.rapidapi.com"

    # 1) File uploader
    uploaded_file = st.file_uploader(
        "📂 Upload Excel (xlsx/xls) with optional Latitude/Longitude columns", 
        type=["xlsx","xls"]
    )
    if not uploaded_file:
        st.info("Please upload an Excel file.")
        return

    # 2) Read Excel into df
    try:
        df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Error reading Excel: {e}")
        return

    st.subheader("Preview of Uploaded Data")
    st.dataframe(df.head(10))

    # Basic required columns
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

    # Clean up address columns
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

    # Build "Full_Address"
    df["Full_Address"] = (
        df["Address1"] + ", "
        + df["City"] + ", "
        + df["State"] + " "
        + df["Zip Code"]
    ).str.strip()

    # 3) Geocode (cached) only rows missing lat/lon
    st.info("Geocoding missing rows @ 2 req/sec. Pre-geocoded rows are skipped.")
    df_geocoded = geocode_addresses(df, RAPIDAPI_KEY, RAPIDAPI_HOST)

    # Drop rows with missing lat/lon
    df_map = df_geocoded.dropna(subset=["Latitude","Longitude"]).copy()

    # 4) Filters
    unique_states = sorted(df_map["State"].dropna().unique())
    state_filter = st.multiselect(
        "Filter by State(s)",
        options=unique_states,
        default=unique_states
    )

    unique_markets = sorted(df_map["Market"].dropna().unique())
    market_filter = st.multiselect(
        "Filter by Market(s)",
        options=unique_markets,
        default=unique_markets
    )

    min_ticket = float(df_map["Total Stay Value With Taxes (Base)"].min() or 0)
    max_ticket = float(df_map["Total Stay Value With Taxes (Base)"].max() or 0)

    ticket_value_range = st.slider(
        "Filter by Ticket Value",
        min_value=min_ticket,
        max_value=max_ticket,
        value=(min_ticket, max_ticket)
    )

    # Apply filters
    df_filtered = df_map[
        (df_map["State"].isin(state_filter)) &
        (df_map["Market"].isin(market_filter)) &
        (df_map["Total Stay Value With Taxes (Base)"] >= ticket_value_range[0]) &
        (df_map["Total Stay Value With Taxes (Base)"] <= ticket_value_range[1])
    ]

    st.subheader("Filtered Data for Map")
    num_dots = len(df_filtered)
    st.write(f"**Number of dots on the map:** {num_dots}")
    st.dataframe(df_filtered.head(20))

    if df_filtered.empty:
        st.warning("No data after applying filters. Adjust filters above.")
        return

    # 5) Plotly map
    st.subheader("📍 Map of Addresses")
    fig = px.scatter_mapbox(
        df_filtered,
        lat="Latitude",
        lon="Longitude",
        color="Market",
        hover_name="Full_Address",
        hover_data=["State", "Total Stay Value With Taxes (Base)"],
        zoom=3,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})

    st.plotly_chart(fig, use_container_width=True)

    # 6) Download geocoded Excel
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


# Run as standalone:
if __name__ == "__main__":
    run_arrival_map()
