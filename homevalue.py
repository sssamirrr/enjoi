import streamlit as st
import pandas as pd
import http.client
import time
import urllib.parse
import json
from collections import defaultdict
import datetime
import io  # <-- for BytesIO (important for Excel download)

# ------------------------------
# HARD-CODED ZILLOW WORKING API CREDENTIALS
# ------------------------------
RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"
RAPIDAPI_HOST = "zillow-working-api.p.rapidapi.com"

def run_home_value_tab():
    """
    Streamlit app that:
      1. Uploads Excel (with Address1, City, Zip Code)
      2. Builds a full address, e.g. "123 Main St, City, ZIP"
      3. Calls Zillow via http.client with the /graph_charts endpoint (byaddress=...)
      4. Parses the JSON response, picks the newest zestimate
      5. Adds "Home Value" column, displays, and provides an Excel download
    """

    st.title("🏡 Home Value Lookup via Zillow API (Newest Zestimate)")

    st.markdown("""
    **Instructions**:
    1. **Upload** an Excel file with columns: **Address1**, **City**, **Zip Code**.
    2. The app will build a single string like `"Address1, City, ZIP"` for each row.
    3. For each row, we make a **request** to the Zillow Working API using **http.client**.
    4. If Zillow finds a match, we parse the returned JSON to get the **newest** zestimate.
    5. The enriched data with **Home Value** will be displayed and can be **downloaded** as an Excel file.

    **Note**: Ensure that the addresses are complete and correctly formatted to improve Zillow's address matching.
    """)

    # 1) File uploader
    uploaded_file = st.file_uploader("📂 Upload Excel File (xlsx or xls)", type=["xlsx", "xls"])
    if uploaded_file is None:
        st.info("Please upload an Excel file to begin.")
        return

    # 2) Read the Excel into a DataFrame
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

    # 3) Check required columns
    required_cols = ["Address1", "City", "Zip Code"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"⚠️ Missing required columns: {missing_cols}")
        return

    # 4) Clean ZIP codes: remove ".0" if any
    df["Zip Code"] = df["Zip Code"].astype(str).str.replace(".0", "", regex=False).str.strip()

    # 5) Clean Address1 and City
    df["Address1"] = df["Address1"].fillna("").astype(str).str.replace("\t", " ", regex=False).str.strip()
    df["City"] = df["City"].fillna("").astype(str).str.replace("\t", " ", regex=False).str.strip()

    # 6) Build a "Full_Address" column
    # e.g., "168 N Ridge Dr, Waynesville, 28785"
    df["Full_Address"] = (
        df["Address1"] + ", " +
        df["City"] + ", " +
        df["Zip Code"]
    ).str.strip()

    st.subheader("📝 Data with Full_Address Column")
    st.dataframe(df[["Address1", "City", "Zip Code", "Full_Address"]].head(10))

    # 7) Initialize Home Values list
    home_values = []

    # 8) Process each address
    for idx, row in df.iterrows():
        full_address = row["Full_Address"]
        if not full_address:
            home_values.append(None)
            continue

        # URL-encode the address
        encoded_address = urllib.parse.quote(full_address)

        # Call the http.client GET request
        zestimate_val = get_newest_zestimate_httpclient(encoded_address, full_address)
        home_values.append(zestimate_val)

        # Sleep a bit to avoid hitting rate limits
        time.sleep(0.5)

    # 9) Add the "Home Value" column
    df["Home Value"] = home_values

    st.subheader("📈 Enriched Data with Home Values")
    st.dataframe(df.head(20))

    # 10) Download as an Excel file
    st.subheader("⬇️ Download Enriched Excel")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Enriched Zestimate")

    # Rewind to the start of the buffer
    output.seek(0)

    st.download_button(
        label="Download Excel",
        data=output.getvalue(),
        file_name="enriched_zestimate.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def get_newest_zestimate_httpclient(encoded_address: str, original_address: str):
    """
    Uses http.client to call /graph_charts?recent_first=True&which=zestimate_history&byaddress=ENCODED_ADDRESS
    Then picks the newest zestimate from the JSON, or None if no data or 404.
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

        status_code = res.status
        if status_code != 200:
            # Non-successful response; skip
            return None

        # Read and decode the response
        data_raw = res.read()
        data_str = data_raw.decode("utf-8")

        # Parse JSON
        try:
            response_json = json.loads(data_str)
        except json.JSONDecodeError:
            return None

        # Parse the Zestimate
        zestimate_val = parse_zestimate_history(response_json)
        return zestimate_val

    except Exception:
        # Handle any exception that occurs during the API call
        return None

    finally:
        conn.close()

def parse_zestimate_history(response_json):
    """
    Given the JSON for zestimate_history, pick the newest zestimate.
    Adjust field names as needed to match your actual JSON structure.
    """
    data_points = response_json.get("DataPoints", {})
    hv_data = data_points.get("homeValueChartData", [])

    if not hv_data:
        return None

    # Find the 'This home' data
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

    # Assuming 'recent_first=True', the first point is the newest
    latest_zestimate = points[0].get("y")
    return latest_zestimate

# If you run this file directly, you can test it locally.
# In your main app.py, import this module and call run_home_value_tab()
if __name__ == "__main__":
    run_home_value_tab()
