# drivingdistance.py

import streamlit as st
import pandas as pd
import http.client
import time
import urllib.parse
import json
import io  # for BytesIO (Excel download)

# -----------------------------------
# HARD-CODED DRIVING DISTANCE API CREDENTIALS (via RapidAPI)
# -----------------------------------
RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"
RAPIDAPI_HOST = "driving-distance-calculator-between-two-points.p.rapidapi.com"

FIXED_DESTINATION = "2913 S Ocean Blvd, Myrtle Beach, SC 29577"

def get_candidate_addresses(row):
    """
    Returns a list of candidate addresses from the row in the following order:
      1. Street + City + Zip Code
      2. City + Zip Code
      3. Street + Zip Code
      4. Street + City
      5. City + State
    """
    address1 = str(row.get("Address1", "")).strip()
    city = str(row.get("City", "")).strip()
    state = str(row.get("State", "")).strip()
    zip_code = str(row.get("Zip Code", "")).strip()
    candidates = []
    if address1 and city and zip_code:
        candidates.append(f"{address1}, {city}, {zip_code}")
    if city and zip_code:
        candidates.append(f"{city}, {zip_code}")
    if address1 and zip_code:
        candidates.append(f"{address1}, {zip_code}")
    if address1 and city:
        candidates.append(f"{address1}, {city}")
    if city and state:
        candidates.append(f"{city}, {state}")
    # Remove duplicates while preserving order
    unique_candidates = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates

def get_driving_info_httpclient(origin_address: str):
    """
    Calls the driving distance API with the URL-encoded origin and fixed destination.
    Returns a tuple (distance_in_miles, travel_time) if successful, else (None, None).
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
            return None, None
        data = res.read().decode("utf-8")
        st.write(f"[DEBUG] Raw API response (truncated): {data[:500]}...")
        response_json = json.loads(data)
        distance_miles = response_json.get("distance_in_miles")
        travel_time = response_json.get("travel_time")  # e.g. "10 hours, 31 minutes"
        return distance_miles, travel_time
    except Exception as e:
        st.write(f"[DEBUG] Exception retrieving driving info for '{origin_address}': {e}")
        return None, None
    finally:
        conn.close()

def process_next_chunk_driving_distance():
    """
    Processes the next chunk (e.g., 100 rows) in st.session_state["df_enriched"].
    For each row, attempts multiple address combinations until a nonzero distance is returned.
    """
    df = st.session_state["df_enriched"]
    start_idx = st.session_state["current_index"]
    chunk_size = st.session_state["chunk_size"]
    end_idx = min(start_idx + chunk_size, len(df))

    st.write(f"**Processing rows {start_idx+1} to {end_idx}** out of {len(df)}")

    for i in range(start_idx, end_idx):
        row = df.loc[i]
        # If distance is already present, skip
        if pd.notnull(row.get("Distance in Miles", None)):
            st.write(f"Row {i+1}: Already has Distance, skipping.")
            continue

        # Retrieve candidate addresses
        candidates = get_candidate_addresses(row)
        result_found = False
        for candidate in candidates:
            st.write(f"Row {i+1}: Trying candidate address '{candidate}'...")
            distance_miles, travel_time = get_driving_info_httpclient(candidate)
            # Check if the API returned a nonzero value. (It might return 0 as int or "0" as a string.)
            if distance_miles not in (None, 0, "0", 0.0):
                df.at[i, "Distance in Miles"] = distance_miles
                df.at[i, "Travel Time"] = travel_time
                st.write(f"Row {i+1}: Found valid driving info with candidate '{candidate}'.")
                result_found = True
                break
            else:
                st.write(f"Row {i+1}: Candidate '{candidate}' returned zero distance.")
        if not result_found:
            st.write(f"Row {i+1}: All candidate addresses resulted in zero distance. Setting Distance as 0.")
            df.at[i, "Distance in Miles"] = 0
            df.at[i, "Travel Time"] = "N/A"
        time.sleep(0.5)

    st.session_state["current_index"] = end_idx
    st.success(f"Chunk processed! Rows {start_idx+1} to {end_idx} done.")

def run_driving_distance():
    """
    Streamlit app that:
      1. Uploads an Excel file with columns: Address1, City, Zip Code (optionally State).
      2. Attempts multiple address constructions per row until a nonzero driving distance is returned.
      3. Processes the data in chunks (100 rows at a time) via the driving-distance API.
      4. Enriches the data with distance (in miles) and travel time.
      5. Displays progress and allows download of the enriched Excel file.
    """
    st.title("🚗 Driving Distance & Time Lookup")

    st.markdown(f"""
    **Instructions**:
    1. **Upload** an Excel file with columns such as **Address1**, **City**, **Zip Code** (and/or **State**).
    2. For each row, this app attempts to build an origin address.
       The **destination** is always:
       > {FIXED_DESTINATION}
    3. The data is processed in chunks (e.g., 100 rows at a time).
    4. The final columns **Distance in Miles** and **Travel Time** are added to your dataset.
    5. If the API returns zero for the first candidate, the app will try:
       - First with City + Zip Code,
       - Then Street + Zip,
       - Then Street + City,
       - Then City + State.
    6. You can **download** the enriched file as Excel once you've processed the desired rows.
    """)

    uploaded_file = st.file_uploader(
        "📂 Upload Excel File (xlsx or xls)", 
        type=["xlsx", "xls"],
        key="drivingdistance_file_uploader"
    )
    if uploaded_file is None:
        st.info("Please upload an Excel file to begin.")
        return

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

    # Check for at least one of the required columns
    possible_cols = ["Address1", "City", "Zip Code", "State"]
    if not any(col in df.columns for col in possible_cols):
        st.error(f"⚠️ The uploaded file must have at least one of these columns: {possible_cols}")
        return

    # Clean and prepare columns if they exist
    if "Zip Code" in df.columns:
        df["Zip Code"] = df["Zip Code"].astype(str).str.replace(".0", "", regex=False).str.strip()
    for col in ["Address1", "City", "State"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.replace("\t", " ", regex=False).str.strip()

    # Ensure the enriched columns exist
    if "Distance in Miles" not in df.columns:
        df["Distance in Miles"] = None
    if "Travel Time" not in df.columns:
        df["Travel Time"] = None

    # Initialize session state if it's a new file or hasn't been processed yet
    if ("df_enriched" not in st.session_state or
        "file_name" not in st.session_state or
        st.session_state["file_name"] != uploaded_file.name):
        st.session_state["df_enriched"] = df.copy()
        st.session_state["file_name"] = uploaded_file.name
        st.session_state["current_index"] = 0
        st.session_state["chunk_size"] = 100

    st.subheader("Driving Distance Lookup Controls")
    if st.button("Process Next Chunk", key="process_next_chunk_driving_distance"):
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
        st.session_state["df_enriched"].to_excel(writer, index=False, sheet_name="Enriched Driving Info")
    out_buffer.seek(0)
    st.download_button(
        label="Download Excel",
        data=out_buffer.getvalue(),
        file_name="enriched_driving_distance.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    run_driving_distance()
