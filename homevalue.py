import streamlit as st
import pandas as pd
import requests
import time
import json

# You can store your API credentials in Streamlit secrets
# or directly in the code (not recommended for production).
# e.g. st.secrets["RAPIDAPI_KEY"] = "YOUR_RAPIDAPI_KEY"
#      st.secrets["RAPIDAPI_HOST"] = "zillow-working-api.p.rapidapi.com"

def run_home_value_tab():
    """
    Streamlit page that:
      1. Uploads an Excel file with columns: Address1, City, Zip Code
      2. Builds a full address string
      3. Calls a Zillow API on RapidAPI to get a property 'zpid' from the address
      4. Then calls a separate endpoint for the Zestimate
      5. Adds the Zestimate to the DataFrame, displays and offers CSV download
    """

    st.title("Home Value Lookup via RapidAPI (Zillow)")

    st.write("""
    **Instructions:**
    1. Upload an Excel file with the columns `Address1`, `City`, and `Zip Code`.
    2. This app will create a full address string for each row.
    3. We'll call the RapidAPI Zillow Working API to fetch a `zpid` and then the Zestimate for each address.
    4. The enriched data (with a "Home Value" column) will be displayed and can be downloaded as a CSV.
    """)

    # 1. File uploader
    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])

    if uploaded_file is not None:
        # 2. Read the Excel file
        df = pd.read_excel(uploaded_file)

        # Basic check for the required columns
        required_cols = ["Address1", "City", "Zip Code"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            st.error(f"Missing required columns: {missing_cols}")
            return

        # 3. Build the Full Address column
        #    Example: "Address1, City ZipCode"
        df["Full_Address"] = (
            df["Address1"].fillna("").astype(str)
            + ", "
            + df["City"].fillna("").astype(str)
            + " "
            + df["Zip Code"].fillna("").astype(str)
        )

        st.subheader("Preview of Uploaded Data (with Full_Address)")
        st.dataframe(df.head(10))

        # 4. For each row, call the API to get a home value
        home_values = []
        for i, row in df.iterrows():
            full_address = row["Full_Address"]
            zpid = get_zpid_from_address(full_address)
            if zpid is not None:
                home_val = get_zestimate_from_zpid(zpid)
            else:
                home_val = None  # or 0.0, etc.

            home_values.append(home_val)
            # Sleep a bit to avoid any rate-limiting
            time.sleep(0.5)

        # 5. Add the new column to the DataFrame
        df["Home Value"] = home_values

        st.subheader("Enriched Data")
        st.dataframe(df.head(20))

        # Provide a download button
        csv_data = df.to_csv(index=False)
        st.download_button(
            label="Download Enriched Data (CSV)",
            data=csv_data,
            file_name="home_value_enriched.csv",
            mime="text/csv"
        )


def get_zpid_from_address(full_address: str):
    """
    Example function to search for a ZPID given a full address string.
    Using the 'Search Zillow' (or similar) endpoint from the Zillow Working API on RapidAPI.
    Adjust the endpoint & JSON parsing as needed for your API.
    """

    # For instance, let's assume there's an endpoint like:
    # GET /search_zillow?location={full_address}
    # (This is just an example; check your actual RapidAPI docs.)

    # Retrieve your credentials (in practice, you might store them in st.secrets)
    RAPIDAPI_KEY = st.secrets["RAPIDAPI_KEY"]
    RAPIDAPI_HOST = st.secrets["RAPIDAPI_HOST"]

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
            # This part depends on how your response is structured.
            # Suppose the endpoint returns something like:
            # {
            #   "results": [
            #       { "zpid": "12345678", "address": "...", ...}
            #   ]
            # }
            #
            results = data.get("results", [])
            if results:
                zpid = results[0].get("zpid")
                return zpid
            else:
                st.warning(f"No results found for address: {full_address}")
                return None
        else:
            st.warning(f"Search request failed ({resp.status_code}). Address: {full_address}")
            return None

    except Exception as e:
        st.warning(f"Error searching ZPID for {full_address}: {e}")
        return None


def get_zestimate_from_zpid(zpid: str):
    """
    Example function that uses a 'Zestimate' endpoint to retrieve the home value,
    given a known ZPID. Adjust this code to match your actual endpoint & JSON structure.
    """

    RAPIDAPI_KEY = st.secrets["RAPIDAPI_KEY"]
    RAPIDAPI_HOST = st.secrets["RAPIDAPI_HOST"]

    url = f"https://{RAPIDAPI_HOST}/graph_charts"
    # This "graph_charts" endpoint might differ in your case.
    # We'll pass some typical query params:
    #   byzpid=..., which=zestimate_history, etc.
    # Again, check your actual docs.
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
            # Typically, you'd parse out the most recent zestimate.
            # The structure might look like: {"data": [{"zestimate": 300000, ...}, ...]}
            # We'll just assume the last item is the most recent:
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
