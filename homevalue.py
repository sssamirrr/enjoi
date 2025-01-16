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
      3. Calls Zillow via http.client with /graph_charts (byaddress=...)
      4. Logs the status code & parsed zestimate
      5. Picks the newest+highest zestimate, adds 'Home Value' column, and displays
    """

    st.title("Home Value Lookup (Newest & Highest), with Logging")

    st.markdown("""
    **Instructions**:
    - Upload an Excel file with columns: **Address1**, **City**, **Zip Code**.
    - We build a single string like "Address1, City, ST ZIP".
    - For each row, we call `https://zillow-working-api.p.rapidapi.com/graph_charts` 
      with `byaddress=<encoded_address>`.
    - We **log** the status code for each address, plus whether a Zestimate is found.
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

    # Clean ZIP codes: remove ".0" if any
    df["Zip Code"] = df["Zip Code"].astype(str).str.replace(".0", "", regex=False)

    # If all addresses in the same state, e.g., NC:
    state_abbrev = ", NC"  # change or remove if needed

    # Build a "Full_Address"
    df["Full_Address"] = (
        df["Address1"].fillna("").str.strip() + ", "
        + df["City"].fillna("").str.strip()
        + state_abbrev + " "
        + df["Zip Code"].fillna("").str.strip()
    ).str.strip()

    st.subheader("Check the 'Full_Address' Column")
    st.dataframe(df[["Address1", "City", "Zip Code", "Full_Address"]].head(10))

    # For each row, call the API
    home_values = []
    for idx, row in df.iterrows():
        full_address = row["Full_Address"]
        if not full_address:
            home_values.append(None)
            continue

        # URL-encode
        encoded_address = urllib.parse.quote(full_address)

        # Log which address we are processing:
        st.write(f"**Processing row {idx}:** {full_address}")

        # Call the http.client GET
        zestimate_val = get_newest_highest_zestimate_httpclient(
            encoded_address, 
            original_address=full_address
        )
        home_values.append(zestimate_val)

        # Sleep a bit to avoid any rate-limit issues
        time.sleep(0.5)

    df["Home Value"] = home_values

    st.subheader("Enriched Data (Newest & Highest Zestimate)")
    st.dataframe(df.head(20))

    # Provide a download button
    csv_data = df.to_csv(index=False)
    st.download_button(
        "Download Enriched CSV",
        data=csv_data,
        file_name="enriched_zestimate_httpclient.csv",
        mime="text/csv"
    )


def get_newest_highest_zestimate_httpclient(encoded_address: str, original_address: str):
    """
    Uses http.client to call /graph_charts?which=zestimate_history&byaddress=ENCODED_ADDRESS
    Returns the newest+highest zestimate or None if not found.
    Also logs status codes and any parsing outcomes to Streamlit.
    """

    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)

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
        # Log the status
        st.write(f"API Status for '{original_address}': **{status_code}**")

        if status_code != 200:
            # If it's 404 or something else, log and return None
            st.warning(f"Zestimate request **failed** ({status_code}). Address: {original_address}")
            return None

        data_raw = res.read()
        data_str = data_raw.decode("utf-8")
        response_json = json.loads(data_str)

        zestimate_val = parse_zestimate_history(response_json)
        if zestimate_val is None:
            st.warning(f"No zestimate found in JSON. Address: {original_address}")
        else:
            st.info(f"Zestimate found: {zestimate_val} for {original_address}")

        return zestimate_val

    except Exception as e:
        st.error(f"Error retrieving Zestimate for {original_address}: {e}")
        return None

    finally:
        conn.close()


def parse_zestimate_history(response_json):
    """
    Given JSON for zestimate_history, return the newest+highest zestimate or None.
    Logs no messages here; done in the calling function.
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
        best_per_date.append(items_on_date[0])  # highest on that date

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
if __name__ == "__main__":
    run_home_value_tab()
