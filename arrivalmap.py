import streamlit as st
import pandas as pd
import plotly.express as px
import io
import datetime
import time

# Geopy for geocoding
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter


############################################
# 1) CACHED GEOCODING FUNCTION
############################################
@st.cache_data  # (If on older Streamlit, use @st.cache instead)
def geocode_dataframe(df_input: pd.DataFrame) -> pd.DataFrame:
    """
    Geocode the DataFrame's 'Full_Address' column only once unless the DataFrame changes.
    Returns a copy of df_input with 'Latitude'/'Longitude'.
    Respects a 1-second delay between requests for Nominatim usage policy.
    
    If a row already has valid Latitude/Longitude, we skip geocoding to avoid duplicate calls.
    """

    df = df_input.copy()

    # Nominatim with custom user_agent & higher timeout
    geolocator = Nominatim(
        user_agent="MyArrivalMapApp/1.0 (myemail@domain.com)", 
        timeout=10  # up to 10s before giving up
    )
    # Rate limit: 1 request per second (Nominatim's public max)
    geocode = RateLimiter(
        geolocator.geocode, 
        min_delay_seconds=1,
        max_retries=2,  # retry a couple times if we get a transient error
    )

    # If 'Latitude'/'Longitude' columns don't exist yet, create them
    if "Latitude" not in df.columns:
        df["Latitude"] = None
    if "Longitude" not in df.columns:
        df["Longitude"] = None

    for idx, row in df.iterrows():
        # 1. If we already have lat/lon, skip geocoding
        if pd.notnull(row["Latitude"]) and pd.notnull(row["Longitude"]):
            continue

        # 2. If there's no Full_Address, skip & leave lat/lon as None
        full_address = row.get("Full_Address", "")
        if not full_address:
            continue

        # 3. Attempt geocoding
        try:
            location = geocode(full_address)
            if location:
                df.at[idx, "Latitude"] = location.latitude
                df.at[idx, "Longitude"] = location.longitude
            else:
                df.at[idx, "Latitude"] = None
                df.at[idx, "Longitude"] = None
        except:
            # If geopy fails or times out, store None
            df.at[idx, "Latitude"] = None
            df.at[idx, "Longitude"] = None

    return df


############################################
# 2) MAIN STREAMLIT FUNCTION
############################################
def run_arrival_map():
    """
    Streamlit app that:
      - Uploads an Excel file
      - Creates 'Full_Address' from Address1 + City + State + Zip Code
      - Geocodes with Nominatim at 1 request per second (cached)
      - Filters by State, Market, Ticket Value
      - Shows how many dots (rows) on the map
      - Allows downloading geocoded data
    """

    st.title("📍 Arrival Map (1 Request/sec, Cached)")

    st.markdown("""
    **Instructions**:
    1. Upload an Excel file with at least these columns:
       - **Address1**, **City**, **State**, **Zip Code**
       - **Market** (used for coloring dots)
       - **Total Stay Value With Taxes (Base)** (Ticket Value).
    2. We'll build a **Full_Address**, geocode it with a **1 request/sec** limit for Nominatim.
    3. Filters: State, Market, Ticket Value
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
    st.dataframe(df[["Full_Address", "Market", "Total Stay Value With Taxes (Base)"]].head(10))

    # 5) Geocode (cached)
    st.info("Geocoding addresses at 1 request/second (Nominatim usage policy).")
    df_geocoded = geocode_dataframe(df)

    # Drop rows with missing lat/lon
    df_map = df_geocoded.dropna(subset=["Latitude","Longitude"]).copy()

    # 6) Filters: State, Market, Ticket Value
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

    # Apply the filters
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

    # 7) Plotly map with color by Market
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
    fig.update_layout(margin={"r":0, "t":0, "l":0, "b":0})

    st.plotly_chart(fig, use_container_width=True)

    # 8) Download the geocoded dataset
    st.subheader("⬇️ Download Geocoded Excel")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_map.to_excel(writer, index=False, sheet_name="GeocodedData")
    output.seek(0)

    st.download_button(
        label="Download Excel (Geocoded)",
        data=output.getvalue(),
        file_name="arrival_map_geocoded.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# If run as a standalone script:
if __name__ == "__main__":
    run_arrival_map()
