import streamlit as st
import pandas as pd
import http.client
import time
import urllib.parse
import json
import io  # for BytesIO (Excel download)

# ------------------------------
# HARD-CODED ZILLOW WORKING API CREDENTIALS (via RapidAPI)
# ------------------------------
RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"
RAPIDAPI_HOST = "zillow-working-api.p.rapidapi.com"

def get_newest_zestimate_httpclient(encoded_address: str, original_address: str):
    """
    Uses http.client to call /graph_charts?recent_first=True&which=zestimate_history&byaddress=ENCODED_ADDRESS,
    then picks the newest zestimate from the JSON, or returns None if no data is found.
    """
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    # Build the request path
    path = (
        "/graph_charts"
        "?recent_first=True"
        "&which=zestimate_history"
        f"&byaddress={encoded_address}"
    )
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    try:
        conn.request("GET", path, headers=headers)
        res = conn.getresponse()
        if res.status != 200:
            return None
        data_raw = res.read()
        data_str = data_raw.decode("utf-8")
        try:
            response_json = json.loads(data_str)
        except json.JSONDecodeError:
            return None
        zestimate_val = parse_zestimate_history(response_json)
        return zestimate_val
    except Exception:
        return None
    finally:
        conn.close()

def parse_zestimate_history(response_json):
    """
    Given the JSON response for zestimate_history, pick the newest zestimate.
    Adjust field names as needed to match the actual JSON structure.
    """
    data_points = response_json.get("DataPoints", {})
    hv_data = data_points.get("homeValueChartData", [])
    if not hv_data:
        return None
    # Look for the data corresponding to "This home"
    this_home_data = None
    for item in hv_data:
        if item.get("name", "").lower() == "this home":
            this_home_data = item
            break
    if not this_home_data:
        return None
    points = this_home_data.get("points", [])
    if not points:
        return None
    # Assuming recent_first=True so the first point is the newest
    latest_zestimate = points[0].get("y")
    return latest_zestimate

def process_next_chunk_home_value():
    """
    Process the next chunk (e.g., 100 rows) in st.session_state["df_enriched"].
    For each row:
      - Skip if there is no valid Full_Address.
      - Skip if the "Home Value" is already set.
      - Otherwise, call the Zillow API to fetch the newest zestimate.
    Updates the DataFrame in session state and advances the current index.
    """
    df = st.session_state["df_enriched"]
    start_idx = st.session_state["current_index"]
    chunk_size = st.session_state["chunk_size"]
    end_idx = min(start_idx + chunk_size, len(df))
    
    st.write(f"**Processing rows {start_idx+1} to {end_idx}** out of {len(df)}")
    
    for i in range(start_idx, end_idx):
        row = df.loc[i]
        full_address = str(row.get("Full_Address", "")).strip()
        # If there's no valid full address, skip this row.
        if not full_address:
            st.write(f"Row {i+1}: No valid address, skipping.")
            continue
        # If the Home Value is already present, skip.
        if pd.notnull(row.get("Home Value", None)):
            st.write(f"Row {i+1}: Home Value already set, skipping.")
            continue

        # URL-encode the address for the API call.
        encoded_address = urllib.parse.quote(full_address)
        st.write(f"Row {i+1}: Fetching Home Value for '{full_address}'...")
        home_value = get_newest_zestimate_httpclient(encoded_address, full_address)
        df.at[i, "Home Value"] = home_value
        # Sleep to avoid rate limits (adjust as needed)
        time.sleep(0.5)
    
    # Update current index.
    st.session_state["current_index"] = end_idx
    st.success(f"Chunk processed! Rows {start_idx+1} to {end_idx} done.")

def run_home_value_tab():
    """
    Streamlit app that:
      1. Uploads an Excel file with columns: Address1, City, Zip Code.
      2. Builds a Full_Address column.
      3. Processes the data in chunks (e.g., 100 rows at a time) to call Zillow's API.
      4. Enriches the data with the newest Zestimate as "Home Value".
      5. Displays partial progress and allows download of the enriched Excel file.
    """
    st.title("🏡 Home Value Lookup via Zillow API (Newest Zestimate)")

    st.markdown("""
    **Instructions**:
    1. **Upload** an Excel file with columns: **Address1**, **City**, **Zip Code**.
    2. The app will build a single string like `"Address1, City, ZIP"` for each row.
    3. For each row (processed in chunks), the app calls Zillow's API to retrieve the newest zestimate.
    4. The enriched data with **Home Value** will be displayed and can be downloaded as an Excel file.
    5. Process the file in chunks (e.g., 100 rows at a time) so you can see partial progress and stop at any time.
    """)

    # 1) File uploader
    uploaded_file = st.file_uploader("📂 Upload Excel File (xlsx or xls)", type=["xlsx", "xls"])
    if uploaded_file is None:
        st.info("Please upload an Excel file to begin.")
        return

    # 2) Read the Excel file into a DataFrame
    try:
        df = pd.read_excel(uploaded_file)
    except ImportError:
        st.error("⚠️ Missing libraries: 'openpyxl' (for .xlsx) or 'xlrd==1.2.0' (for .xls). Please install them:\n`pip install openpyxl xlrd==1.2.0`")
        return
    except Exception as e:
        st.error(f"⚠️ Error reading Excel file: {e}")
        return

    st.subheader("📊 Preview of Uploaded Data")
    st.dataframe(df.head())

    # 3) Check for required columns
    required_cols = ["Address1", "City", "Zip Code"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"⚠️ Missing required columns: {missing_cols}")
        return

    # 4) Clean ZIP codes and text columns
    df["Zip Code"] = df["Zip Code"].astype(str).str.replace(".0", "", regex=False).str.strip()
    df["Address1"] = df["Address1"].fillna("").astype(str).str.replace("\t", " ", regex=False).str.strip()
    df["City"] = df["City"].fillna("").astype(str).str.replace("\t", " ", regex=False).str.strip()

    # 5) Build the "Full_Address" column (e.g., "168 N Ridge Dr, Waynesville, 28785")
    df["Full_Address"] = (
        df["Address1"] + ", " +
        df["City"] + ", " +
        df["Zip Code"]
    ).str.strip()

    st.subheader("📝 Data with Full_Address Column")
    st.dataframe(df[["Address1", "City", "Zip Code", "Full_Address"]].head(10))

    # 6) Initialize the "Home Value" column if not already present
    if "Home Value" not in df.columns:
        df["Home Value"] = None

    # 7) Initialize session state for chunk processing if this is a new upload
    if "df_enriched" not in st.session_state or "file_name" not in st.session_state \
       or st.session_state["file_name"] != uploaded_file.name:
        st.session_state["df_enriched"] = df.copy()
        st.session_state["file_name"] = uploaded_file.name
        st.session_state["current_index"] = 0  # start at row 0
        st.session_state["chunk_size"] = 100   # process 100 rows per chunk

    # 8) Button for chunk-based processing with a unique key to avoid duplicate element errors
    st.subheader("Home Value Lookup Controls")
    if st.button("Process Next Chunk", key="process_next_chunk_home_value"):
        process_next_chunk_home_value()

    total_len = len(st.session_state["df_enriched"])
    current_idx = st.session_state["current_index"]
    if current_idx >= total_len:
        st.success("All rows have been processed!")
    else:
        st.write(f"**Rows processed so far**: {current_idx} / {total_len}")

    # 9) Show a preview of the enriched data
    st.subheader("📈 Enriched Data with Home Values")
    st.dataframe(st.session_state["df_enriched"].head(20))

    # 10) Download the partially or fully enriched Excel file
    st.subheader("⬇️ Download Enriched Excel")
    out_buffer = io.BytesIO()
    with pd.ExcelWriter(out_buffer, engine="xlsxwriter") as writer:
        st.session_state["df_enriched"].to_excel(writer, index=False, sheet_name="Enriched Zestimate")
    out_buffer.seek(0)
    st.download_button(
        label="Download Excel",
        data=out_buffer.getvalue(),
        file_name="enriched_zestimate.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    run_home_value_tab()
