import streamlit as st
import pandas as pd
import requests
import time
import json

def run_home_value_tab():
    """
    Streamlit page that:
      1. Uploads an Excel file (xlsx or xls) with columns: Address1, City, Zip Code
      2. Builds a full address string
      3. Calls the RapidAPI Zillow Working API to fetch a ZPID from the address
      4. Calls a separate endpoint to retrieve the Zestimate (or other home value)
      5. Adds the home value to the DataFrame, displays and offers CSV download
    """

    st.title("Enrich Customer Data with Home Values")

    st.write("""
    1. Upload an Excel file containing customer data (one row per customer).
    2. Ensure there are columns named **Address1**, **City**, and **Zip Code** 
       that we can combine into a full address.
    3. We will then call the Zillow API on RapidAPI to get an approximate home value (Zestimate).
    4. The resulting enriched data will appear below, and you can download it.
    """)

    # 1. File uploader
    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx", "xls"])

    if uploaded_file is not None:
        # 2. Try reading the Excel file into a DataFrame
        try:
            df = pd.read_excel(uploaded_file)
        except ImportError as e:
            st.error(
                "**Missing library**: It looks like 'openpyxl' (for .xlsx) or 'xlrd' (for .xls) "
                "is not installed in this environment. Please install them:\n"
                "`pip install openpyxl xlrd==1.2.0`"
            )
            return
        except Exception as e:
            st.error(f"Error reading Excel file: {e}")
            return

        st.subheader("Preview of Uploaded Data")
        st.dataframe(df.head())

        # Check for required columns
        required_cols = ["Address1", "City", "Zip Code"]
        missing_cols = [c for c in required_cols if c not in df.columns]
        if missing_cols:
            st.error(f"Missing required columns: {missing_cols}")
            return

        # 3. Build a Full_Address column
        df["Full_Address"] = (
            df["Address1"].fillna("").astype(str)
            + ", "
            + df["City"].fillna("").astype(str)
            + " "
            + df["Zip Code"].fillna("").astype(str)
        )

        st.subheader("Data with Full_Address Column")
        st.dataframe(df.head())

        # 4. Look up each address in the Zillow API
        home_values = []
        for _, row in df.iterrows():
            full_address = row["Full_Address"]
            if not full_address.strip():
                home_values.append(None)
                continue

            # First, get the ZPID
            zpid = get_zpid_from_address(full_address)
            if zpid:
                # Then, get the home value from the ZPID
                home_val = get_zestimate_from_zpid(zpid)
            else:
                home_val = None

            home_values.append(home_val)

            # Optional: Sleep to avoid rate-limiting; adjust as needed
            time.sleep(0.5)

        # 5. Add the Home Value column to the DataFrame
        df["Home Value"] = home_values

        st.subheader("Enriched Data with Home Values")
        st.dataframe(df.head(20))

        # Download button for CSV
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="Download Enriched Data as CSV",
            data=csv_data,
            file_name="enriched_home_values.csv",
            mime="text/csv"
        )


def get_zpid_from_address(full_address: str):
    """
    Example function to get a ZPID from a full address string using a RapidAPI Zillow endpoint.
    Adjust the endpoint & JSON parsing to match your actual 'search' method on the 'Zillow Working API'.
    """

    # Pull credentials from Streamlit secrets (or you could hard-code them for testing)
    try:
        RAPIDAPI_KEY = st.secrets["RAPIDAPI_KEY"]
        RAPIDAPI_HOST = st.secrets["RAPIDAPI_HOST"]
    except Exception:
        st.error("Please set 'RAPIDAPI_KEY' and 'RAPIDAPI_HOST' in Streamlit secrets.")
        return None

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

            # Adjust the parsing below to match the actual response structure
            results = data.get("results", [])
            if not results:
                st.warning(f"No results found for address: {full_address}")
                return None

            zpid = results[0].get("zpid")
            return zpid
        else:
            st.warning(f"Search (ZPID) request failed ({resp.status_code}). Address: {full_address}")
            return None

    except Exception as e:
        st.warning(f"Error searching ZPID for {full_address}: {e}")
        return None


def get_zestimate_from_zpid(zpid: str):
    """
    Example function to retrieve the home's Zestimate using the ZPID.
    Adjust the endpoint & JSON parsing to match your actual 'Zestimate' method on the 'Zillow Working API'.
    """

    try:
        RAPIDAPI_KEY = st.secrets["RAPIDAPI_KEY"]
        RAPIDAPI_HOST = st.secrets["RAPIDAPI_HOST"]
    except Exception:
        st.error("Please set 'RAPIDAPI_KEY' and 'RAPIDAPI_HOST' in Streamlit secrets.")
        return None

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
            # Typically you'd parse out the most recent zestimate.
            # This is just an example parse; real structure may differ.
            items = data.get("data", [])
            if items:
                most_recent = items[-1]
                zestimate = most_recent.get("zestimate", 0)
                return float(zestimate)
            else:
                return None
        else:
            st.warning(f"Zestimate request failed ({resp.status_code}) for ZPID: {zpid}")
            return None

    except Exception as e:
        st.warning(f"Error retrieving Zestimate for ZPID {zpid}: {e}")
        return None
