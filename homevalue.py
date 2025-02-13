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
    Returns the zestimate or fallback price if successful; otherwise, returns None.
    
    Fallback Logic:
      1) Try to get 'zestimate' from the JSON.
      2) If it's missing, null, or zero, try 'Price'.
      3) If neither is found, return 0 (but we treat 0 as "no real value").
    """
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
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

        # 1) Get 'zestimate'
        zestimate_val = response_json.get("zestimate", None)
        # If 'zestimate' is missing, null, 0, or "0", fallback to 'Price'
        if not zestimate_val:
            zestimate_val = response_json.get("Price", 0)  # default to 0 if 'Price' is also missing
        
        return zestimate_val

    except Exception as e:
        st.write(f"[DEBUG] Exception retrieving zestimate for '{original_address}': {e}")
        return None
    finally:
        conn.close()


def process_next_chunk_home_value():
    """
    Process the next chunk (1500 rows) in st.session_state["df_enriched"].
    For each row:
      - If Full_Address is invalid or empty, skip.
      - If "Home Value" is already set (non-null), skip.
      - Otherwise:
          1) URL-encode the full address: Street + City + Zip
             Call Zillow's API.
          2) If None or 0, try again with just Street + Zip.
          3) Store the final result; if none, store 0.
    Advances the current index in session state.
    """
    df = st.session_state["df_enriched"]
    start_idx = st.session_state["current_index"]
    chunk_size = st.session_state["chunk_size"]
    end_idx = min(start_idx + chunk_size, len(df))
    
    # Figure out which column is used for "Address" 
    # (we do this only once outside the loop for performance)
    if "Address1" in df.columns:
        address_col = "Address1"
    elif "Address" in df.columns:
        address_col = "Address"
    else:
        address_col = "Address1"  # fallback if missing (shouldn't happen if data is valid)
    
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
        
        # 1) Attempt with full address (street + city + zip)
        encoded_address = urllib.parse.quote(full_address)
        st.write(f"Row {i+1}: Fetching Home Value for '{full_address}'...")
        home_value = get_newest_zestimate_httpclient(encoded_address, full_address)
        time.sleep(0.5)  # courtesy sleep to respect rate limits

        # 2) If that returned None or 0, try fallback with street + zip
        #    (i.e., ignoring City).
        if not home_value or home_value == 0:
            fallback_address = f"{row[address_col]}, {row['Zip Code']}"
            fallback_address = fallback_address.strip().strip(",")
            st.write(f"Row {i+1}: Trying fallback with '{fallback_address}'...")
            encoded_fallback_address = urllib.parse.quote(fallback_address)
            fallback_value = get_newest_zestimate_httpclient(encoded_fallback_address, fallback_address)
            time.sleep(0.5)  # courtesy sleep for second call

            if fallback_value and fallback_value != 0:
                home_value = fallback_value
        
        # 3) If still None or 0, store zero
        if not home_value or home_value == 0:
            home_value = 0

        df.at[i, "Home Value"] = home_value

    st.session_state["current_index"] = end_idx
    st.success(f"Chunk processed! Rows {start_idx+1} to {end_idx} done.")


def run_home_value_tab():
    """
    Streamlit app that:
      1. Uploads an Excel file with columns: Address1, City, Zip Code
         (If "Address1" is missing, it will try "Address" instead).
      2. Looks for data in the sheet "Sheet1"; if not found, tries "unqCC".
      3. Builds a Full_Address column by combining the address, city, zip code.
      4. Processes data in chunks of 1500 rows to call Zillow's API for the newest zestimate or price fallback.
      5. If the first attempt with (street+city+zip) yields no value, it tries (street+zip) only.
      6. Enriches the data with a "Home Value" column.
      7. Displays partial progress and allows downloading the enriched Excel file.
    """
    st.title("🏡 Home Value Lookup via Zillow API (Newest Zestimate/Price Fallback)")

    st.markdown("""
    **Instructions**:
    1. **Upload** an Excel file with columns: **Address1** (or **Address**), **City**, **Zip Code**.
    2. The app will try reading from the sheet **"Sheet1"**. If that sheet is not found, it will attempt **"unqCC"**.
    3. A **Full_Address** column is built like `"438 Vitoria Rd, Davenport, FL 33837"`.
    4. Data is processed in chunks of 1500 rows. After each chunk, you can process more or download the partially-enriched file.
    5. If 'zestimate' is missing or zero, the code will try 'Price'. If both are missing, it defaults to 0.
    6. If the address+city+zip call yields no value, we **retry with street+zip only**.
    7. The enriched data with **Home Value** can be downloaded as an Excel file.
    """)

    uploaded_file = st.file_uploader("📂 Upload Excel File (xlsx or xls)", type=["xlsx", "xls"])
    if uploaded_file is None:
        st.info("Please upload an Excel file to begin.")
        return

    # Try reading from "Sheet1", if not found, try "unqCC"
    try:
        df = pd.read_excel(uploaded_file, sheet_name="Sheet1")
    except ValueError:
        st.write("[DEBUG] Could not find 'Sheet1', trying 'unqCC'...")
        try:
            df = pd.read_excel(uploaded_file, sheet_name="unqCC")
        except Exception as e2:
            st.error(f"Could not read from Sheet1 or unqCC: {e2}")
            return
    except Exception as e:
        st.error(f"⚠️ Error reading Excel file: {e}")
        return

    st.subheader("📊 Preview of Uploaded Data")
    st.dataframe(df.head())

    # Address column detection
    if "Address1" in df.columns:
        address_col = "Address1"
    elif "Address" in df.columns:
        address_col = "Address"
    else:
        st.error("⚠️ Missing required column: 'Address1' or 'Address'.")
        return

    # Check for City and Zip Code
    if "City" not in df.columns or "Zip Code" not in df.columns:
        st.error("⚠️ Missing required columns: 'City' and/or 'Zip Code'.")
        return

    # Clean up the Zip Code to only its first 5 digits
    # remove non-digits, then slice first 5
    df["Zip Code"] = (
        df["Zip Code"]
        .astype(str)
        .str.replace(r"[^0-9]", "", regex=True)
        .str[:5]
    )

    # Clean address columns (remove tabs, trim whitespace)
    df[address_col] = (
        df[address_col]
        .fillna("")
        .astype(str)
        .str.replace("\t", " ", regex=False)
        .str.strip()
    )
    df["City"] = (
        df["City"]
        .fillna("")
        .astype(str)
        .str.replace("\t", " ", regex=False)
        .str.strip()
    )

    # Build Full_Address column
    df["Full_Address"] = (
        df[address_col] + ", " + df["City"] + ", " + df["Zip Code"]
    ).str.strip()

    st.subheader("📝 Data with Full_Address Column")
    st.dataframe(df[[address_col, "City", "Zip Code", "Full_Address"]].head(10))

    # Ensure "Home Value" column exists
    if "Home Value" not in df.columns:
        df["Home Value"] = None

    # Initialize session state for chunk processing if new file
    if ("df_enriched" not in st.session_state 
        or "file_name" not in st.session_state 
        or st.session_state["file_name"] != uploaded_file.name):
        st.session_state["df_enriched"] = df.copy()
        st.session_state["file_name"] = uploaded_file.name
        st.session_state["current_index"] = 0
        st.session_state["chunk_size"] = 1500  # Process 1500 rows at a time

    st.subheader("Home Value Lookup Controls")
    if st.button("Process Next 1500 Rows", key="process_next_chunk_home_value"):
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
        st.session_state["df_enriched"].to_excel(
            writer,
            index=False,
            sheet_name="Enriched Zestimate"
        )
    out_buffer.seek(0)
    st.download_button(
        label="Download Excel",
        data=out_buffer.getvalue(),
        file_name="enriched_zestimate.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    run_home_value_tab()
