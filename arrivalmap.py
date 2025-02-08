import streamlit as st
import pandas as pd
import plotly.express as px
import io
import time
import http.client
import json

# -------------------------------------------------
# 1) HARD-CODED RAPIDAPI CONFIG
# -------------------------------------------------
RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"  # <--- Your key
RAPIDAPI_HOST = "google-maps-geocoding3.p.rapidapi.com"

def geocode_address_rapidapi(address: str):
    """
    Geocode a single address using the RapidAPI "google-maps-geocoding3" endpoint.
    Returns (latitude, longitude) or (None, None) if not found or error.
    Rate limit ~8 calls/sec => time.sleep(0.125).
    """
    if not address:
        return None, None

    # ~8 calls/second
    time.sleep(0.125)

    try:
        conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
        headers = {
            'x-rapidapi-key': RAPIDAPI_KEY,
            'x-rapidapi-host': RAPIDAPI_HOST
        }
        endpoint = f"/geocode?address={address.replace(' ', '%20')}"
        conn.request("GET", endpoint, headers=headers)
        res = conn.getresponse()
        data = res.read()
        conn.close()

        json_data = json.loads(data.decode("utf-8"))
        if "latitude" in json_data and "longitude" in json_data:
            return json_data["latitude"], json_data["longitude"]
        else:
            return None, None
    except Exception as e:
        st.write(f"Error geocoding '{address}': {e}")
        return None, None


def process_next_chunk():
    """
    Process the next chunk of rows (up to chunk_size) in st.session_state["df_geocoded"].
    Skip rows that:
      - Already have Latitude & Longitude
      - Address1, City, State, Zip Code all empty
    Update rows with newly geocoded lat/lon.
    """
    df = st.session_state["df_geocoded"]
    start_idx = st.session_state["current_index"]
    chunk_size = st.session_state["chunk_size"]
    end_idx = min(start_idx + chunk_size, len(df))

    st.write(f"**Processing rows {start_idx+1} to {end_idx}** out of {len(df)}")

    # Row-by-row geocoding for this chunk
    for i in range(start_idx, end_idx):
        row = df.loc[i]

        # Already geocoded?
        if pd.notnull(row["Latitude"]) and pd.notnull(row["Longitude"]):
            st.write(f"Row {i+1}: Already has lat/lon, skipping.")
            continue

        # Check if all address fields are empty
        addr1 = str(row.get("Address1", "")).strip()
        city  = str(row.get("City", "")).strip()
        state = str(row.get("State", "")).strip()
        zipc  = str(row.get("Zip Code", "")).strip()

        if not any([addr1, city, state, zipc]):
            st.write(f"Row {i+1}: No valid address, skipping.")
            continue

        # Geocode
        full_address = str(row.get("Full_Address", "")).strip()
        st.write(f"Row {i+1}: Geocoding '{full_address}'...")
        lat, lon = geocode_address_rapidapi(full_address)
        df.at[i, "Latitude"] = lat
        df.at[i, "Longitude"] = lon

    # Update the current index
    st.session_state["current_index"] = end_idx

    st.success(f"Chunk processed! Rows {start_idx+1}-{end_idx} done.")


def run_arrival_map():
    """
    Chunk-Based Geocoding with Partial Progress & Download.
    """
    st.title("📍 Chunk-Based Geocoding with Partial Progress & Download")

    st.write("""
    **How it works**:
    1. Upload an Excel file with columns:
       - Address1, City, State, Zip Code
       - Market, Total Stay Value With Taxes (Base)
       - (Optional) Home Value
    2. We'll create 'Full_Address' and let you geocode in **chunks** (e.g. 100 rows at a time).
    3. After each chunk, you can stop or download the partially geocoded file.
    4. This avoids timeouts for very large files and gives you control over stopping.
    """)

    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx", "xls"])
    if not uploaded_file:
        st.info("Awaiting file upload...")
        return

    # Read the file
    try:
        df_uploaded = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Could not read Excel file: {e}")
        return

    # Check mandatory columns
    required_cols = ["Address1", "City", "State", "Zip Code", "Market", "Total Stay Value With Taxes (Base)"]
    missing = [c for c in required_cols if c not in df_uploaded.columns]
    if missing:
        st.error(f"Missing required columns: {missing}")
        return

    st.subheader("Uploaded File Preview")
    st.dataframe(df_uploaded.head(10))

    # If first time or new file, initialize session state
    if "df_geocoded" not in st.session_state or "file_name" not in st.session_state \
       or st.session_state["file_name"] != uploaded_file.name:

        df_uploaded["Address1"] = df_uploaded["Address1"].fillna("").astype(str).str.strip()
        df_uploaded["City"]     = df_uploaded["City"].fillna("").astype(str).str.strip()
        df_uploaded["State"]    = df_uploaded["State"].fillna("").astype(str).str.strip()
        df_uploaded["Zip Code"] = (
            df_uploaded["Zip Code"].fillna("").astype(str)
            .str.replace(".0", "", regex=False)
            .str.strip()
        )
        df_uploaded["Full_Address"] = (
            df_uploaded["Address1"] + ", " +
            df_uploaded["City"] + ", " +
            df_uploaded["State"] + " " +
            df_uploaded["Zip Code"]
        ).str.strip()

        if "Latitude" not in df_uploaded.columns:
            df_uploaded["Latitude"] = None
        if "Longitude" not in df_uploaded.columns:
            df_uploaded["Longitude"] = None

        st.session_state["df_geocoded"] = df_uploaded.copy()
        st.session_state["file_name"] = uploaded_file.name
        st.session_state["current_index"] = 0
        st.session_state["chunk_size"] = 100

    st.subheader("Geocoding Controls")
    if st.button("Process Next Chunk"):
        process_next_chunk()

    total_len = len(st.session_state["df_geocoded"])
    current_idx = st.session_state["current_index"]
    if current_idx >= total_len:
        st.success("All rows have been processed!")
    else:
        st.write(f"**Rows processed so far**: {current_idx} / {total_len}")

    # ---------------------------------------------------
    # Map & Filters (Optional)
    # ---------------------------------------------------
    # Drop rows without valid latitude/longitude
    df_map = st.session_state["df_geocoded"].dropna(subset=["Latitude", "Longitude"]).copy()

    # Convert Latitude and Longitude to numeric types
    if not df_map.empty:
        df_map["Latitude"] = pd.to_numeric(df_map["Latitude"], errors="coerce")
        df_map["Longitude"] = pd.to_numeric(df_map["Longitude"], errors="coerce")

    if not df_map.empty:
        st.subheader("Filtering & Map")

        # State filter
        states = sorted(df_map["State"].dropna().unique())
        state_selection = st.multiselect("Filter by State(s)", options=states, default=states)
        # Market filter
        markets = sorted(df_map["Market"].dropna().unique())
        market_selection = st.multiselect("Filter by Market(s)", options=markets, default=markets)
        # Ticket Value range
        min_ticket = float(df_map["Total Stay Value With Taxes (Base)"].min() or 0)
        max_ticket = float(df_map["Total Stay Value With Taxes (Base)"].max() or 0)
        ticket_value_range = st.slider("Filter by Ticket Value", min_value=min_ticket, max_value=max_ticket, value=(min_ticket, max_ticket))

        # Apply filters
        df_filtered = df_map[
            (df_map["State"].isin(state_selection)) &
            (df_map["Market"].isin(market_selection)) &
            (df_map["Total Stay Value With Taxes (Base)"] >= ticket_value_range[0]) &
            (df_map["Total Stay Value With Taxes (Base)"] <= ticket_value_range[1])
        ]

        # Optional Home Value filter
        if "Home Value" in df_filtered.columns:
            st.subheader("Home Value Filter")
            min_home = float(df_filtered["Home Value"].min() or 0)
            max_home = float(df_filtered["Home Value"].max() or 0)
            hv_range = st.slider("Home Value Range", min_value=min_home, max_value=max_home, value=(min_home, max_home))
            df_filtered = df_filtered[
                (df_filtered["Home Value"] >= hv_range[0]) &
                (df_filtered["Home Value"] <= hv_range[1])
            ]

        st.write(f"**Filtered Results**: {len(df_filtered)} rows")
        st.dataframe(df_filtered.head(20))

        if not df_filtered.empty:
            st.subheader("Map View")
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
    else:
        st.info("No rows with valid latitude/longitude yet.")

    # ---------------------------------------------------
    # Download Partial or Full Results
    # ---------------------------------------------------
    st.subheader("Download Partial/Full Geocoded Results")
    df_enriched = st.session_state["df_geocoded"]
    out_buffer = io.BytesIO()
    with pd.ExcelWriter(out_buffer, engine="xlsxwriter") as writer:
        df_enriched.to_excel(writer, index=False, sheet_name="GeocodedData")
    out_buffer.seek(0)

    st.download_button(
        label="Download Geocoded Excel",
        data=out_buffer,
        file_name="arrival_map_geocoded.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    run_arrival_map()
