# homevalue.py

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
    Uses http.client to call the Zillow Working API endpoint `/byaddress`
    with the URL-encoded address.
    Returns the zestimate value if the call is successful; otherwise, returns None.
    """
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    # Build the request path with the encoded address.
    path = f"/byaddress?propertyaddress={encoded_address}"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }
    try:
        conn.request("GET", path, headers=headers)
        res = conn.getresponse()
        if res.status != 200:
            st.write(f"[DEBUG] Non-200 status: {res.status} for address {original_address}")
            return None
        data = res.read()
        response_str = data.decode("utf-8")
        st.write(f"[DEBUG] Raw API response (truncated): {response_str[:500]}...")
        response_json = json.loads(response_str)
        # Return the zestimate value
        return response_json.get("zestimate", None)
    except Exception as e:
        st.write(f"[DEBUG] Exception retrieving zestimate for '{original_address}': {e}")
        return None
    finally:
        conn.close()

def process_next_chunk_home_value():
    """
    Process the next chunk (e.g., 100 rows) in st.session_state["df_enriched"].
    For each row:
      - If Full_Address is invalid or empty, skip.
      - If "Home Value" is already set, skip.
      - Otherwise, URL-encode the full address, call Zillow's API, and store the returned zestimate.
    Advances the current index in session state.
    """
    df = st.session_state["df_enriched"]
    start_idx = st.session_state["current_index"]
    chunk_size = st.session_state["chunk_size"]
    end_idx = min(start_idx + chunk_size, len(df))
    
    st.write(f"**Processing rows {start_idx+1} to {end_idx}** out of {len(df)}")
    
    for i in range(start_idx, end_idx):
        row = df.loc[i]
        full_address = str(row.get("Full_Address", "")).strip()
        if not full_address:
            st.write(f"Row {i+1}: No valid address, skipping.")
            continue
        # If Home Value is already set, skip.
        if pd.notnull(row.get("Home Value", None)):
            st.write(f"Row {i+1}: Home Value already set, skipping.")
            continue
        
        encoded_address = urllib.parse.quote(full_address)
        st.write(f"Row {i+1}: Fetching Home Value for '{full_address}'...")
        home_value = get_newest_zestimate_httpclient(encoded_address, full_address)
        df.at[i, "Home Value"] = home_value
        time.sleep(0.5)  # To respect rate limits

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
    2. The app will build a full address like `"438 Vitoria Rd, Davenport, FL 33837"`.
    3. The data is processed in chunks (e.g., 100 rows at a time). After each chunk, you can stop or download the current results.
    4. For each valid address, the app calls Zillow's API to retrieve the newest zestimate.
    5. The enriched data with **Home Value** is displayed and can be downloaded as an Excel file.
    """)

    uploaded_file = st.file_uploader("📂 Upload Excel File (xlsx or xls)", type=["xlsx", "xls"])
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

    # Check required columns.
    required_cols = ["Address1", "City", "Zip Code"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"⚠️ Missing required columns: {missing_cols}")
        return

    # Clean and prepare columns.
    df["Zip Code"] = df["Zip Code"].astype(str).str.replace(".0", "", regex=False).str.strip()
    df["Address1"] = df["Address1"].fillna("").astype(str).str.replace("\t", " ", regex=False).str.strip()
    df["City"] = df["City"].fillna("").astype(str).str.replace("\t", " ", regex=False).str.strip()

    # Build Full_Address column.
    df["Full_Address"] = (df["Address1"] + ", " + df["City"] + ", " + df["Zip Code"]).str.strip()

    st.subheader("📝 Data with Full_Address Column")
    st.dataframe(df[["Address1", "City", "Zip Code", "Full_Address"]].head(10))

    # Ensure "Home Value" column exists.
    if "Home Value" not in df.columns:
        df["Home Value"] = None

    # Initialize session state for chunk processing if new file.
    if "df_enriched" not in st.session_state or "file_name" not in st.session_state or st.session_state["file_name"] != uploaded_file.name:
        st.session_state["df_enriched"] = df.copy()
        st.session_state["file_name"] = uploaded_file.name
        st.session_state["current_index"] = 0
        st.session_state["chunk_size"] = 100

    st.subheader("Home Value Lookup Controls")
    if st.button("Process Next Chunk", key="process_next_chunk_home_value"):
        process_next_chunk_home_value()

    total_len = len(st.session_state["df_enriched"])
    current_idx = st.session_state["current_index"]
    if current_idx >= total_len:
        st.success("All rows have been processed!")
    else:
        st.write(f"**Rows processed so far**: {current_idx} / {total_len}")

    st.subheader("📈 Enriched Data with Home Values")
    st.dataframe(st.session_state["df_enriched"].head(20))

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
