import streamlit as st
import pandas as pd
import http.client
import time
import urllib.parse
import json
from collections import defaultdict
import datetime

# ------------------------------
# HARD-CODED ZILLOW WORKING API CREDENTIALS
# ------------------------------
RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"
RAPIDAPI_HOST = "zillow-working-api.p.rapidapi.com"

def run_home_value_tab():
    """
    Streamlit app that:
      1. Uploads Excel (with Address1, City, Zip Code, [State])
      2. Builds a full address, e.g. "123 Main St, City, ST 12345"
      3. Calls Zillow via http.client with the /graph_charts endpoint (byaddress=...)
      4. Parses the JSON response, picks the newest+highest zestimate
      5. Adds "Home Value" column, displays, and provides CSV download
    """

    st.title("Home Value Lookup via http.client (Newest & Highest)")

    st.markdown("""
    **Instructions**:
    - Upload an Excel file with columns: **Address1**, **City**, **Zip Code**, and optionally **State**.
    - If your data **does not** include a **State** column, you will need to specify a default State below.
    - The app will build a single string like "Address1, City, ST ZIP" for each row.
    - We make **one** request per row to the Zillow Working API using **http.client**.
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
        st.error("Missing libraries: 'openpyxl' (for .xlsx) or 'xlrd==1.2.0' (for .xls). Please install them:\n`pip install openpyxl xlrd==1.2.0`")
        return
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")
        return

    st.subheader("Preview of Uploaded Data")
    st.dataframe(df.head())

    # 3) Check required columns
    required_cols = ["Address1", "City", "Zip Code"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        st.error(f"Missing required columns: {missing_cols}")
        return

    # 4) Determine if 'State' column exists
    has_state = "State" in df.columns
    if not has_state:
        st.warning("No 'State' column found in the data. Please specify a default State for all addresses below.")
        # Let user select a default state
        default_state = st.selectbox(
            "Select Default State (applied to all addresses without a 'State' column)",
            options=[
                "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
                "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
                "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
            ],
            index=35  # Default to "NC" if suitable
        )
    else:
        # If 'State' column exists, ensure it's in the correct format (2-letter abbreviations)
        # You might need to clean or validate this
        st.info("Detected 'State' column in the data.")

    # 5) Clean ZIP codes: remove ".0" if any
    df["Zip Code"] = df["Zip Code"].astype(str).str.replace(".0", "", regex=False).str.strip()

    # 6) Clean Address1 and City
    df["Address1"] = df["Address1"].fillna("").astype(str).str.replace("\t", " ", regex=False).str.strip()
    df["City"] = df["City"].fillna("").astype(str).str.replace("\t", " ", regex=False).str.strip()

    # 7) Build a "Full_Address" column
    if has_state:
        df["Full_Address"] = (
            df["Address1"] + ", " +
            df["City"] + ", " +
            df["State"].fillna("").astype(str).str.strip() + " " +
            df["Zip Code"]
        ).str.strip()
    else:
        df["Full_Address"] = (
            df["Address1"] + ", " +
            df["City"] + ", " +
            default_state + " " +
            df["Zip Code"]
        ).str.strip()

    st.subheader("Data with Full_Address Column")
    st.dataframe(df[["Address1", "City", "Zip Code", "State" if has_state else None, "Full_Address"]].head(10))

    # 8) Initialize Home Values list
    home_values = []

    # 9) Process each address
    for idx, row in df.iterrows():
        full_address = row["Full_Address"]
        if not full_address:
            home_values.append(None)
            st.write(f"**Row {idx}:** Empty address. Skipping.")
            continue

        # URL-encode the address
        encoded_address = urllib.parse.quote(full_address)

        # Log which address is being processed
        st.write(f"**Processing Row {idx}:** {full_address}")

        # Call the http.client GET request
        zestimate_val = get_newest_highest_zestimate_httpclient(encoded_address, full_address)
        home_values.append(zestimate_val)

        # Log the result
        if zestimate_val is not None:
            st.success(f"Row {idx}: Zestimate found - ${zestimate_val:,.2f}")
        else:
            st.warning(f"Row {idx}: Zestimate not found or request failed.")

        # Sleep to avoid hitting rate limits
        time.sleep(0.5)

    # 10) Add the "Home Value" column
    df["Home Value"] = home_values

    st.subheader("Enriched Data (Newest & Highest Zestimate)")
    st.dataframe(df.head(20))

    # 11) Download button
    csv_data = df.to_csv(index=False)
    st.download_button(
        "Download Enriched CSV",
        data=csv_data,
        file_name="enriched_zestimate_httpclient.csv",
        mime="text/csv"
    )


def get_newest_highest_zestimate_httpclient(encoded_address: str, original_address: str):
    """
    Uses http.client to call /graph_charts?recent_first=True&which=zestimate_history&byaddress=ENCODED_ADDRESS
    Then picks the newest+highest zestimate from the JSON, or None if no data or 404.
    Logs status codes and outcomes.
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

        # Log the status code
        st.write(f"API Response Status for '{original_address}': **{status_code}**")

        if status_code != 200:
            # Log warning if not successful
            st.warning(f"Zestimate request **failed** ({status_code}) for address: {original_address}")
            return None

        # Read and decode the response
        data_raw = res.read()
        data_str = data_raw.decode("utf-8")

        # Parse JSON
        response_json = json.loads(data_str)

        # Parse the Zestimate
        zestimate_val = parse_zestimate_history(response_json)

        if zestimate_val is None:
            st.warning(f"No zestimate found in response for address: {original_address}")
        else:
            st.info(f"Zestimate retrieved: ${zestimate_val:,.2f}")

        return zestimate_val

    except Exception as e:
        # Log any exceptions that occur
        st.error(f"Error retrieving Zestimate for {original_address}: {e}")
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
        zestimate = item.get("zestimate")
        if d_str and zestimate:
            date_groups[d_str].append(item)

    # For each date, pick the entry with the highest zestimate
    best_per_date = []
    for d_str, items_on_date in date_groups.items():
        # Sort items by zestimate descending and pick the first
        items_on_date.sort(key=lambda x: x.get("zestimate", 0), reverse=True)
        best_per_date.append(items_on_date[0])

    if not best_per_date:
        return None

    # Sort the best_per_date by date descending to get the newest first
    def parse_date(d_str):
        try:
            return datetime.datetime.strptime(d_str, "%Y-%m-%d")
        except:
            return datetime.datetime.min

    best_per_date.sort(key=lambda x: parse_date(x.get("date")), reverse=True)

    # The first item is the newest date's highest zestimate
    newest_highest_item = best_per_date[0]
    return newest_highest_item.get("zestimate")


# If you run this file directly, you can test it locally.
# In your main app.py, import this module and call run_home_value_tab()
if __name__ == "__main__":
    run_home_value_tab()
