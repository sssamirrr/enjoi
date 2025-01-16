import streamlit as st
import pandas as pd
import requests
import time
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
    Streamlit page that:
      1. Uploads an Excel file (xlsx or xls) with columns: Address1, City, Zip Code
      2. Builds a full address string
      3. Calls the RapidAPI Zillow Working API to fetch a ZPID from the address
      4. Calls a separate endpoint to retrieve the Zestimate (zestimate_history)
      5. Picks the newest, highest value from the result
      6. Adds that value to the DataFrame, displays, and offers CSV download
    """

    st.title("Home Value Lookup (Newest & Highest Zestimate)")

    st.write("""
    **Steps**:
    1. Upload an Excel file with `Address1`, `City`, and `Zip Code`.
    2. We'll build a single full address, e.g. "123 Main St, CityName, NC 12345".
    3. We call the "search_zillow" endpoint to find a ZPID.
    4. We call "zestimate_history" to get an array of home values.
    5. We pick the newest & highest zestimate if multiple exist.
    6. You can download the enriched data as CSV.
    
    **Note**: If the address is incomplete (e.g., no state) or doesn't exist on Zillow, you'll get 404 or no data.
    """)

    # 1. File uploader
    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx", "xls"])

    if uploaded_file is not None:
        # 2. Try reading the Excel file into a DataFrame
        try:
            df = pd.read_excel(uploaded_file)
        except ImportError:
            st.error(
                "**Missing library**: 'openpyxl' (for .xlsx) or 'xlrd==1.2.0' (for .xls)."
                "Please install them:\n`pip install openpyxl xlrd==1.2.0`"
            )
            return
        except Exception as e:
            st.error(f"Error reading Excel file: {e}")
            return

        st.subheader("Preview of Uploaded Data")
        st.dataframe(df.head())

        # 2a. Ensure required columns
        required_cols = ["Address1", "City", "Zip Code"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            st.error(f"Missing required columns: {missing_cols}")
            return

        # 2b. (Optional) Clean ZIP to remove trailing .0
        df["Zip Code"] = df["Zip Code"].astype(str).str.replace(".0", "", regex=False)

        # 2c. Hard-code a state if you like (Zillow often needs it).
        # For example, if all addresses are in NC, do:
        # state_col = "NC"  
        # Or if your sheet has a 'State' column, incorporate that.
        state_col = ""  # replace with e.g. ", NC" if all in NC

        # 3. Build Full_Address
        df["Full_Address"] = (
            df["Address1"].fillna("").astype(str).str.strip()
            + ", "
            + df["City"].fillna("").astype(str).str.strip()
            + state_col + " "
            + df["Zip Code"].fillna("").astype(str).str.strip()
        ).str.strip()

        st.subheader("Data with Full_Address Column")
        st.dataframe(df[["Address1", "City", "Zip Code", "Full_Address"]].head())

        # 4. For each row, do the ZPID lookup + get the newest/highest zestimate
        home_values = []
        for i, row in df.iterrows():
            full_address = row["Full_Address"]
            if not full_address:
                home_values.append(None)
                continue

            # Get ZPID by searching the address
            zpid = get_zpid_from_address(full_address)
            if not zpid:
                home_values.append(None)
                continue

            # Now fetch the zestimate history and parse out the newest/highest
            zestimate_val = get_newest_highest_zestimate(zpid)
            home_values.append(zestimate_val)

            # Sleep a bit to avoid any rate-limit issues
            time.sleep(0.5)

        # 5. Add the "Home Value" column
        df["Home Value"] = home_values

        st.subheader("Enriched Data (Newest & Highest Zestimate)")
        st.dataframe(df.head(20))

        # 6. Download as CSV
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="Download Enriched Data (CSV)",
            data=csv_data,
            file_name="enriched_home_values.csv",
            mime="text/csv"
        )


def get_zpid_from_address(full_address: str):
    """
    Calls the 'search_zillow' endpoint with the address to retrieve a ZPID.
    Returns None if 404 or no results.
    """
    url = f"https://{RAPIDAPI_HOST}/search_zillow"
    querystring = {"location": full_address}
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }

    try:
        resp = requests.get(url, headers=headers, params=querystring)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if not results:
                st.warning(f"No ZPID found for: {full_address}")
                return None
            # Just take the first match
            zpid = results[0].get("zpid")
            return zpid
        else:
            st.warning(f"Search (ZPID) request failed ({resp.status_code}). Address: {full_address}")
            return None
    except Exception as e:
        st.warning(f"Error searching ZPID for {full_address}: {e}")
        return None


def get_newest_highest_zestimate(zpid: str):
    """
    Calls the 'zestimate_history' endpoint (graph_charts) with 'recent_first=true',
    then parses the 'homeValueChartData' to find the newest, highest zestimate.

    Returns None if no data is found.
    """
    url = f"https://{RAPIDAPI_HOST}/graph_charts"
    querystring = {
        "recent_first": "true",
        "which": "zestimate_history",
        "byzpid": zpid
    }
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }

    try:
        resp = requests.get(url, headers=headers, params=querystring)
        if resp.status_code == 200:
            data = resp.json()
            return parse_zestimate_history(data)
        else:
            st.warning(f"Zestimate request failed ({resp.status_code}) for ZPID {zpid}")
            return None
    except Exception as e:
        st.warning(f"Error retrieving Zestimate for ZPID {zpid}: {e}")
        return None


def parse_zestimate_history(response_json):
    """
    Given the JSON response for 'zestimate_history', picks the newest & highest zestimate.
    - 'newest' means the most recent date
    - if multiple items share the same date, picks the highest among them

    Adjust field names based on your actual 'homeValueChartData' structure.
    """
    # The data might look like:
    # {
    #   "message": "200: Success",
    #   "homeValueChartData": [
    #       {"date": "2023-07-15", "zestimate": 210000, ...},
    #       {"date": "2023-07-01", "zestimate": 208000, ...},
    #       ...
    #   ]
    # }
    if "homeValueChartData" not in response_json:
        return None

    data_points = response_json["homeValueChartData"]
    if not data_points:
        return None

    # Group by date, so we handle multiple points on the same date
    date_to_items = defaultdict(list)
    for item in data_points:
        d_str = item.get("date")
        date_to_items[d_str].append(item)

    # For each date, pick the entry with the highest zestimate
    best_per_date = []
    for d_str, items_on_date in date_to_items.items():
        items_on_date.sort(key=lambda x: x.get("zestimate", 0), reverse=True)
        best_per_date.append(items_on_date[0])  # highest item for that date

    # Now we have one 'best' item per date. Sort them by date descending to find the newest.
    def parse_date(d_str):
        # Adjust format if needed
        return datetime.datetime.strptime(d_str, "%Y-%m-%d")

    best_per_date.sort(
        key=lambda x: parse_date(x["date"]) if x.get("date") else datetime.datetime.min,
        reverse=True
    )

    # The first item is now the newest date's highest zestimate
    newest_highest = best_per_date[0]
    return newest_highest.get("zestimate")


# -----------------------------
# If you're running this as your main app:
if __name__ == "__main__":
    run_home_value_tab()
