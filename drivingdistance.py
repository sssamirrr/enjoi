import streamlit as st
import pandas as pd
import http.client
import time
import urllib.parse
import json
import io  # for BytesIO (Excel download)
import re

# -----------------------------------
# HARD-CODED DRIVING DISTANCE API CREDENTIALS (via RapidAPI)
# -----------------------------------
RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"
RAPIDAPI_HOST = "driving-distance-calculator-between-two-points.p.rapidapi.com"

# -----------------------------------
# FIXED DESTINATION (example)
# -----------------------------------
FIXED_DESTINATION = "2913 S Ocean Blvd, Myrtle Beach, SC 29577"

def parse_travel_time(time_str: str):
    """
    Given a string like "12 minutes, 49 seconds" or "1 hours, 12 minutes, 49 seconds",
    extract hours, minutes, and seconds, then compute:
      - A human-readable "Hh Mm" string (e.g., "1h 12m")
      - Total minutes as a float (e.g., 72.82)
    Returns (travel_time_hm, total_minutes).
    """
    if not time_str:
        # If empty or None, return defaults
        return ("0h 0m", 0)

    hours = 0
    minutes = 0
    seconds = 0

    match_hours = re.search(r"(\d+)\s+hours?", time_str)
    if match_hours:
        hours = int(match_hours.group(1))

    match_minutes = re.search(r"(\d+)\s+minutes?", time_str)
    if match_minutes:
        minutes = int(match_minutes.group(1))

    match_seconds = re.search(r"(\d+)\s+seconds?", time_str)
    if match_seconds:
        seconds = int(match_seconds.group(1))

    total_minutes = hours * 60 + minutes + (seconds / 60.0)
    travel_time_hm = f"{hours}h {minutes}m"
    return travel_time_hm, total_minutes

def get_driving_info_httpclient(origin_address: str):
    """
    Calls the driving distance API with the URL-encoded origin and FIXED_DESTINATION.
    Returns:
      distance_in_miles (float or None),
      travel_time_raw (str),
      origin_lat (str or None),
      origin_lon (str or None)
    """
    encoded_origin = urllib.parse.quote(origin_address)
    encoded_dest = urllib.parse.quote(FIXED_DESTINATION)

    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    path = f"/data?origin={encoded_origin}&destination={encoded_dest}"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    try:
        conn.request("GET", path, headers=headers)
        res = conn.getresponse()
        if res.status != 200:
            st.write(f"[DEBUG] Non-200 status: {res.status} for origin={origin_address}")
            return None, None, None, None

        data = res.read().decode("utf-8")
        st.write(f"[DEBUG] Raw API response (truncated): {data[:250]}...")
        response_json = json.loads(data)

        distance_miles = response_json.get("distance_in_miles")
        travel_time_raw = response_json.get("travel_time")
        origin_lat = response_json.get("origin_latitude")
        origin_lon = response_json.get("origin_longitude")

        return distance_miles, travel_time_raw, origin_lat, origin_lon

    except Exception as e:
        st.write(f"[DEBUG] Exception retrieving driving info for '{origin_address}': {e}")
        return None, None, None, None
    finally:
        conn.close()

def get_candidate_addresses(row, address_col: str):
    """
    Returns a list of candidate addresses from the row in the following order:
      1. Street + City + Zip Code
      2. City + Zip Code
      3. Street + Zip Code
      4. Street + City
      5. City + State
    """
    address_val = str(row.get(address_col, "")).strip()
    city = str(row.get("City", "")).strip()
    state = str(row.get("State", "")).strip()
    zip_code = str(row.get("Zip Code", "")).strip()

    candidates = []
    if address_val and city and zip_code:
        candidates.append(f"{address_val}, {city}, {zip_code}")
    if city and zip_code:
        candidates.append(f"{city}, {zip_code}")
    if address_val and zip_code:
        candidates.append(f"{address_val}, {zip_code}")
    if address_val and city:
        candidates.append(f"{address_val}, {city}")
    if city and state:
        candidates.append(f"{city}, {state}")

    # Remove duplicates while preserving order
    unique_candidates = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)

    return unique_candidates

def run_driving_distance():
    """
    Streamlit app that:
      1. Uploads an Excel file with columns: (Address1 or Address), City, Zip Code, optionally State.
      2. Reads the file, cleans data, and sets up session state for results.
      3. Processes data in chunks of 1500 rows, calling an API for driving distance & time.
      4. Shows partial progress, allows chunk-by-chunk processing, and final download.
    """
    st.title("🚗 Driving Distance & Time Lookup")

    st.markdown(f"""
    **Instructions**:
    1. **Upload** an Excel file with columns:
       - **Address1** (or **Address**),
       - **City**,
       - **Zip Code**,
       - optionally **State**.
    2. For each row, this app attempts multiple address formats:
       - Street + City + Zip
       - City + Zip
       - Street + Zip
       - Street + City
       - City + State
    3. The **destination** is fixed:
       > {FIXED_DESTINATION}
    4. Data is processed in chunks of 1500 rows. 
       Each time you click "Process Next 1500 Rows," it processes another 1500 rows.
    5. The final columns include:
       - **Distance in Miles**
       - **Travel Time (h/m)** (e.g. "2h 15m")
       - **Driving Time (Minutes)**
       - **Origin Latitude**
       - **Origin Longitude**
    6. You can **download** the enriched file as Excel anytime.
    """)

    uploaded_file = st.file_uploader(
        "📂 Upload Excel File (xlsx or xls)",
        type=["xlsx", "xls"],
        key="drivingdistance_file_uploader"
    )

    # If no file is uploaded, don't proceed further.
    if uploaded_file is None:
        st.info("Please upload an Excel file to begin.")
        return

    # Read the Excel file (default sheet)
    try:
        df = pd.read_excel(uploaded_file)
    except ImportError:
        st.error("⚠️ Missing libraries: 'openpyxl' (for .xlsx) or 'xlrd==1.2.0' (for .xls).")
        return
    except Exception as e:
        st.error(f"⚠️ Error reading Excel file: {e}")
        return

    st.subheader("📊 Preview of Uploaded Data")
    st.dataframe(df.head())

    # Determine which address column to use
    if "Address1" in df.columns:
        address_col = "Address1"
    elif "Address" in df.columns:
        address_col = "Address"
    else:
        st.error("⚠️ Missing required column: 'Address1' or 'Address'.")
        return

    # Check for City, Zip Code, etc.
    if "City" not in df.columns or "Zip Code" not in df.columns:
        st.error("⚠️ Missing required columns: 'City' and/or 'Zip Code'.")
        return

    # Clean up the Zip Code to only its first 5 digits (remove non-digit characters)
    df["Zip Code"] = (
        df["Zip Code"]
        .astype(str)
        .str.replace(r"[^0-9]", "", regex=True)  # remove non-digit
        .str[:5]                                 # keep only first 5
    )

    # Clean/prepare address, city, state columns
    for col_name in [address_col, "City", "State"]:
        if col_name in df.columns:
            df[col_name] = (
                df[col_name]
                .fillna("")
                .astype(str)
                .str.replace("\t", " ", regex=False)
                .str.strip()
            )

    # Ensure the enriched columns exist
    if "Distance in Miles" not in df.columns:
        df["Distance in Miles"] = None
    if "Travel Time (h/m)" not in df.columns:
        df["Travel Time (h/m)"] = None
    if "Driving Time (Minutes)" not in df.columns:
        df["Driving Time (Minutes)"] = None
    if "Origin Latitude" not in df.columns:
        df["Origin Latitude"] = None
    if "Origin Longitude" not in df.columns:
        df["Origin Longitude"] = None

    # Initialize session state if it's a new file or not processed yet
    if (
        "df_enriched" not in st.session_state
        or "file_name" not in st.session_state
        or st.session_state["file_name"] != uploaded_file.name
    ):
        st.session_state["df_enriched"] = df.copy()
        st.session_state["file_name"] = uploaded_file.name
        st.session_state["current_index"] = 0
        st.session_state["chunk_size"] = 1500  # You can adjust as needed
        st.session_state["address_col"] = address_col

    def process_next_chunk_driving_distance():
        """
        Processes the next chunk (1500 rows) in st.session_state["df_enriched"].
        For each row, attempts multiple address combinations until a nonzero distance is returned.
        Stores:
          - Distance in Miles
          - Travel Time (h/m)
          - Driving Time (Minutes)
          - Origin Latitude
          - Origin Longitude
        """
        df_local = st.session_state["df_enriched"]
        start_idx = st.session_state["current_index"]
        chunk_size = st.session_state["chunk_size"]
        end_idx = min(start_idx + chunk_size, len(df_local))

        address_col_local = st.session_state["address_col"]  # which column to use for address

        st.write(f"**Processing rows {start_idx+1} to {end_idx}** out of {len(df_local)}")

        for i in range(start_idx, end_idx):
            row = df_local.loc[i]

            # If Distance in Miles is already populated, skip
            if pd.notnull(row.get("Distance in Miles", None)):
                st.write(f"Row {i+1}: Already has Distance, skipping.")
                continue

            # Generate candidate addresses for this row
            candidates = get_candidate_addresses(row, address_col_local)
            result_found = False

            # Try each candidate address until we find a nonzero distance
            for candidate in candidates:
                st.write(f"Row {i+1}: Trying candidate address '{candidate}'...")
                distance_miles, travel_time_raw, origin_lat, origin_lon = get_driving_info_httpclient(candidate)

                # Check if the API returned a nonzero distance
                if distance_miles not in (None, 0, "0", 0.0):
                    travel_time_hm, total_minutes = parse_travel_time(travel_time_raw)

                    # Store results
                    df_local.at[i, "Distance in Miles"] = distance_miles
                    df_local.at[i, "Travel Time (h/m)"] = travel_time_hm
                    df_local.at[i, "Driving Time (Minutes)"] = round(total_minutes, 2)
                    df_local.at[i, "Origin Latitude"] = origin_lat
                    df_local.at[i, "Origin Longitude"] = origin_lon

                    st.write(f"Row {i+1}: Found valid driving info with '{candidate}'.")
                    result_found = True
                    break
                else:
                    st.write(f"Row {i+1}: Candidate '{candidate}' returned zero or no data.")

            # If all candidates failed, set distance to 0
            if not result_found:
                st.write(f"Row {i+1}: All candidates gave zero distance. Setting Distance as 0.")
                df_local.at[i, "Distance in Miles"] = 0
                df_local.at[i, "Travel Time (h/m)"] = "0h 0m"
                df_local.at[i, "Driving Time (Minutes)"] = 0
                df_local.at[i, "Origin Latitude"] = None
                df_local.at[i, "Origin Longitude"] = None

            # Sleep to respect possible API rate limits
            time.sleep(0.5)

        # Update session state
        st.session_state["current_index"] = end_idx
        st.success(f"Chunk processed! Rows {start_idx+1} to {end_idx} done.")

    st.subheader("Driving Distance Lookup Controls")
    if st.button("Process Next 1500 Rows"):
        process_next_chunk_driving_distance()

    total_len = len(st.session_state["df_enriched"])
    current_idx = st.session_state["current_index"]
    if current_idx >= total_len:
        st.success("All rows have been processed!")
    else:
        st.write(f"**Rows processed so far**: {current_idx} / {total_len}")

    st.subheader("📈 Enriched Data with Driving Distance & Time")
    st.dataframe(st.session_state["df_enriched"].head(20))

    st.subheader("⬇️ Download Enriched Excel")
    out_buffer = io.BytesIO()
    with pd.ExcelWriter(out_buffer, engine="xlsxwriter") as writer:
        st.session_state["df_enriched"].to_excel(
            writer,
            index=False,
            sheet_name="Enriched Driving Info"
        )
    out_buffer.seek(0)
    st.download_button(
        label="Download Excel",
        data=out_buffer.getvalue(),
        file_name="enriched_driving_distance.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    # Always run the app with: streamlit run drivingdistance.py
    run_driving_distance()
