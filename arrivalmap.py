import streamlit as st
import pandas as pd
import plotly.express as px
import io
import time
import datetime

# For geocoding
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

############################################
# 1. Define a cached function for geocoding
############################################
@st.cache_data  # or @st.cache if you're on older Streamlit
def geocode_dataframe(df_input: pd.DataFrame) -> pd.DataFrame:
    """
    Geocode the DataFrame's addresses only once, unless df_input changes.
    Returns a copy of df_input with 'Latitude'/'Longitude' columns added.
    """
    # Deep copy to avoid mutating original
    df = df_input.copy()

    # Prepare the geolocator
    geolocator = Nominatim(user_agent="arrival_map_app")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    lat_list = []
    lon_list = []

    for addr in df["Full_Address"]:
        if not addr:
            lat_list.append(None)
            lon_list.append(None)
            continue
        try:
            location = geocode(addr)
            if location:
                lat_list.append(location.latitude)
                lon_list.append(location.longitude)
            else:
                lat_list.append(None)
                lon_list.append(None)
        except:
            lat_list.append(None)
            lon_list.append(None)

    df["Latitude"] = lat_list
    df["Longitude"] = lon_list
    return df


def run_arrival_map():
    """
    Streamlit app that:
    1) Uploads an Excel file
    2) Geocodes Address1 + City + State + Zip into lat/lon (cached)
    3) Plots addresses on a map with color = Market
    4) Filters by State, Market, and Ticket Value
    """

    st.title("📍 Arrival Map with Market Colors (Cached Geocoding)")

    # 1) File uploader
    uploaded_file = st.file_uploader("📂 Upload Excel File (xlsx/xls)", type=["xlsx","xls"])
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

    # Basic checks for required columns
    required_cols = [
        "Address1", "City", "State", 
        "Zip Code", "Market", 
        "Total Stay Value With Taxes (Base)"
    ]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"Missing required columns: {missing_cols}")
        return

    # Clean up address columns
    df["Address1"] = df["Address1"].fillna("").astype(str).str.strip()
    df["City"] = df["City"].fillna("").astype(str).str.strip()
    df["State"] = df["State"].fillna("").astype(str).str.strip()
    df["Zip Code"] = (
        df["Zip Code"].fillna("").astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # Create a full address column
    df["Full_Address"] = (
        df["Address1"] + ", " 
        + df["City"] + ", " 
        + df["State"] + " " 
        + df["Zip Code"]
    ).str.strip()

    st.subheader("Full Addresses")
    st.dataframe(df[["Full_Address", "Market", "Total Stay Value With Taxes (Base)"]].head(10))

    ############################################
    # 3) CALL THE CACHED GEOCODING FUNCTION
    ############################################
    st.info("Geocoding addresses... (this is cached, so it won’t re-run unless data changes)")
    df_geocoded = geocode_dataframe(df)  # <--- caching is handled here

    # Drop rows with missing lat/lon
    df_map = df_geocoded.dropna(subset=["Latitude","Longitude"]).copy()

    # 4) Filters: State(s), Market(s), and Ticket Value
    unique_states = sorted(df_map["State"].dropna().unique())
    state_filter = st.multiselect(
        "Filter by State(s)", 
        unique_states, 
        default=unique_states
    )

    unique_markets = sorted(df_map["Market"].dropna().unique())
    market_filter = st.multiselect(
        "Filter by Market(s)",
        unique_markets,
        default=unique_markets
    )

    # Ticket value range
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
        (df_map["State"].isin(state_filter))
        & (df_map["Market"].isin(market_filter))
        & (df_map["Total Stay Value With Taxes (Base)"] >= ticket_value_range[0])
        & (df_map["Total Stay Value With Taxes (Base)"] <= ticket_value_range[1])
    ]

    st.subheader("Filtered Data for Map")
    st.write(f"Rows after filters: {len(df_filtered)}")
    st.dataframe(df_filtered.head(20))

    if df_filtered.empty:
        st.warning("No data after applying filters. Adjust filters above.")
        return

    # 5) Plotly map with color by Market
    st.subheader("📍 Map of Addresses")
    fig = px.scatter_mapbox(
        df_filtered,
        lat="Latitude",
        lon="Longitude",
        color="Market",   # color by Market
        hover_name="Full_Address",
        hover_data=["State", "Total Stay Value With Taxes (Base)"],
        zoom=3,
        height=600
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0, "t":0, "l":0, "b":0})

    st.plotly_chart(fig, use_container_width=True)

    # 6) (Optional) Provide a download of the geocoded dataset as Excel
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


# If you want to run this file directly, you can test it locally:
if __name__ == "__main__":
    run_arrival_map()
