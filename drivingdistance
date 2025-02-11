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

def build_origin_address(row):
    """
    Tries to build a valid origin address string from the row.
    We require at least one of the following combos:
      - Address1 + City + Zip Code
      - City + Zip Code
      - City + State
      - Address1 + City
    Returns the constructed string or None if insufficient data.
    """
    address1 = str(row.get("Address1", "")).strip()
    city = str(row.get("City", "")).strip()
    state = str(row.get("State", "")).strip()
    zip_code = str(row.get("Zip Code", "")).strip()

    # Some basic priority logic:
    if address1 and city and zip_code:
        return f"{address1}, {city}, {zip_code}"
    elif city and zip_code:
        return f"{city}, {zip_code}"
    elif city and state:
        return f"{city}, {state}"
    elif address1 and city:
        return f"{address1}, {city}"
    else:
        return None

def get_driving_info_httpclient(origin_address: str):
    """
    Calls the driving distance API, passing the origin_address (URL-encoded)
    and the fixed destination (URL-encoded).
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
    For each row:
      - Build an origin address from the row. If invalid or empty, skip.
      - If Distance in Miles is already set, skip (assuming we already processed it).
      - Otherwise, call the driving distance API and store the returned data.
    Advances the current index in session state.
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

        origin = build_origin_address(row)
        if not origin:
            st.write(f"Row {i+1}: Not enough data to build a valid address, skipping.")
            continue

        st.write(f"Row {i+1}: Fetching driving info for origin '{origin}'...")
        distance_miles, travel_time = get_driving_info_httpclient(origin)
        df.at[i, "Distance in Miles"] = distance_miles
        df.at[i, "Travel Time"] = travel_time

        # Short sleep to respect potential rate limits
        time.sleep(0.5)

    st.session_state["current_index"] = end_idx
    st.success(f"Chunk processed! Rows {start_idx+1} to {end_idx} done.")

def run_driving_distance_tab():
    """
    Streamlit app that:
      1. Uploads an Excel file with columns: Address1, City, Zip Code (optionally State).
      2. Builds an origin address from the row, using minimal logic.
      3. Processes the data in chunks (100 rows at a time) to call the driving-distance API.
      4. Enriches the data with distance (in miles) and travel time.
      5. Displays partial progress and allows download of the enriched Excel file.
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
    5. You can **download** the enriched file as Excel once you've processed the desired rows.
    """)

    uploaded_file = st.file_uploader("📂 Upload Excel File (xlsx or xls)", type=["xlsx", "xls"])
    if uploaded_file is None:
        st.info("Please upload an Excel file to begin.")
        return

    # Attempt to read the file
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

    # Check for at least some columns we might use:
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

    # Ensure "Distance in Miles" and "Travel Time" columns exist
    if "Distance in Miles" not in df.columns:
        df["Distance in Miles"] = None
    if "Travel Time" not in df.columns:
        df["Travel Time"] = None

    # Initialize session state if it's a new file or not yet done
    if ("df_enriched" not in st.session_state or
        "file_name" not in st.session_state or
        st.session_state["file_name"] != uploaded_file.name
    ):
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
    run_driving_distance_tab()
