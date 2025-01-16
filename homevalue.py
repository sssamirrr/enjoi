import streamlit as st
import pandas as pd
import http.client
import time
import urllib.parse
import json
from collections import defaultdict
import datetime

# Hard-coded RapidAPI credentials
RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"
RAPIDAPI_HOST = "zillow-working-api.p.rapidapi.com"

def run_home_value_tab():
    """
    Streamlit app that:
      1. Uploads Excel (with Address1, City, Zip Code)
      2. Builds a full address, e.g. "123 Main St, City, ST 12345"
      3. Calls Zillow via http.client with the /graph_charts endpoint (byaddress=...)
      4. Parses the JSON response, picks the newest+highest zestimate
      5. Adds "Home Value" column, displays, and provides CSV download
    """

    st.title("Home Value Lookup via http.client (Newest & Highest)")

    st.markdown("""
    **Instructions**:
    - Upload an Excel file with columns: **Address1**, **City**, **Zip Code**.
    - We build a single string like "Address1, City, ST ZIP" (feel free to modify for your state).
    - We make **one** request per row to the Zillow Working API using **http.client** format:

    ```python
    import http.client
    conn = http.client.HTTPSConnection("zillow-working-api.p.rapidapi.com")
    headers = {...}
    conn.request("GET", "/graph_charts?...&byaddress=ENCODED_ADDRESS", headers=headers)
    ```
    
    - If Zillow finds a match, we parse the returned JSON to get the newest and highest zestimate.
    - A 404 indicates that Zillow can’t match the address.
    """)

    # 1) File uploader
    uploaded_file = st.file_uploader("Upload Excel (xlsx or xls)", type=["xlsx", "xls"])
    if uploaded_file is None:
        st.info("Please upload an Excel file to begin.")
        return

    # 2) Read the Excel into a DataFrame
    try:
        df = pd.read_excel(uploaded_file)
    except ImportError:
        st.error("Missing openpyxl or xlrd. Install: pip install openpyxl xlrd==1.2.0")
        return
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")
        return

    st.subheader("Preview of Uploaded Data")
    st.dataframe(df.head())

    # Check required columns
    required_cols = ["Address1", "City", "Zip Code"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"Missing columns: {missing_cols}")
        return

    # (Optional) Clean ZIP codes: remove ".0"
    df["Zip Code"] = df["Zip Code"].astype(str).str.replace(".0", "", regex=False)

    # If you have a single-state scenario, you can hard-code a state:
    # e.g., ", NC" – or if your data has a "State" column, incorporate that.
    state_abbrev = ", NC"  # Change or remove if needed

    # Build a "Full_Address"
    # e.g., "168 N Ridge Dr, Waynesville, NC 28785"
    df["Full_Address"] = (
        df["Address1"].fillna("").str.strip() + ", "
        + df["City"].fillna("").str.strip()
        + state_abbrev + " "
        + df["Zip Code"].fillna("").str.strip()
    ).str.strip()

    st.subheader("Check the 'Full_Address' Column")
    st.dataframe(df[["Address1", "City", "Zip Code", "Full_Address"]].head(10))

    # 3) For each row, call the /graph_charts?recent_first=True&which=zestimate_history&byaddress=...
    home_values = []
    for _, row in df.iterrows():
        full_address = row["Full_Address"]
        if not full_address:
            home_values.append(None)
            continue

        # URL-encode the address
        encoded_address = urllib.parse.quote(full_address)

        # Do the http.client GET request
        zestimate_val = get_newest_highest_zestimate_httpclient(encoded_address)
        home_values.append(zestimate_val)

        # Sleep to avoid rate-limit
        time.sleep(0.5)

    # 4) Add the "Home Value" column
    df["Home Value"] = home_values

    st.subheader("Enriched Data (Newest & Highest Zestimate)")
    st.dataframe(df.head(20))

    # 5) Download button
    csv_data = df.to_csv(index=False)
    st.download_button(
        "Download Enriched CSV",
        data=csv_data,
        file_name="enriched_zestimate_httpclient.csv",
        mime="text/csv"
    )


def get_newest_highest_zestimate_httpclient(encoded_address: str):
    """
    Uses http.client to call /graph_charts?recent_first=True&which=zestimate_history&byaddress=ENCODED_ADDRESS
    Then picks the newest+highest zestimate from the JSON, or None if no data or 404.
    """

    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)

    # Example path:
    # /graph_charts?recent_first=True&which=zestimate_history&byaddress=123%20Main%20St%2C%20Raleigh
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

        # If status != 200, likely 404 or other error
        if res.status != 200:
            return None

        data_raw = res.read()
        data_str = data_raw.decode("utf-8")
        response_json = json.loads(data_str)

        zestimate_val = parse_zestimate_history(response_json)
        return zestimate_val

    except Exception as e:
        return None
    finally:
        conn.close()


def parse_zestimate_history(response_json):
    """
    Given the JSON for zestimate_history, pick the newest & highest zestimate.
    Adjust field names as needed to match your actual JSON structure.
    """
    hv_data = response_json.get("homeValueChartData", [])
    if not hv_data:
        return None

    # Group by date, pick highest among items with the same date.
    date_groups = defaultdict(list)
    for item in hv_data:
        d_str = item.get("date")
        date_groups[d_str].append(item)

    best_per_date = []
    for d_str, items_on_date in date_groups.items():
        items_on_date.sort(key=lambda x: x.get("zestimate", 0), reverse=True)
        best_per_date.append(items_on_date[0])  # highest zestimate on that date

    # Sort by date descending => newest first
    def parse_date(d_str):
        if not d_str:
            return datetime.datetime.min
        try:
            return datetime.datetime.strptime(d_str, "%Y-%m-%d")
        except:
            return datetime.datetime.min

    best_per_date.sort(key=lambda x: parse_date(x.get("date")), reverse=True)

    newest_highest_item = best_per_date[0]
    return newest_highest_item.get("zestimate")


# If you run this file directly, you can test it locally.
# In your main app.py, just do:
#   import homevalue
#   homevalue.run_home_value_tab()
if __name__ == "__main__":
    run_home_value_tab()
