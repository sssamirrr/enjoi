import streamlit as st
import pandas as pd
import requests
import time

# Replace these with your own RapidAPI credentials
RAPIDAPI_KEY = "dfeb75b744mshcf88e410704f433p1b871ejsn398130bf7076"
RAPIDAPI_HOST = "zillow-working-api.p.rapidapi.com"

def run_home_value_tab():
    """
    Renders the 'Add Home Value' tab in Streamlit.
    Allows the user to upload an Excel file with addresses
    and enrich each row by calling the Zillow API for a home value (Zestimate).
    """

    st.title("Enrich Customer Data with Home Values")

    st.write("""
        1. Upload an Excel file containing customer data (one row per customer).
        2. Make sure there is a column named 'Address' (optionally 'City', 'State', 'ZIP') 
           that we can pass to the Zillow API.
        3. We will then call the Zillow API to get an approximate home value (Zestimate) 
           for each address.
        4. The resulting enriched data will appear below, and you can download it.
    """)

    # 1. File uploader
    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx", "xls"])

    if uploaded_file is not None:
        # 2. Read the Excel file into a DataFrame
        df = pd.read_excel(uploaded_file)

        st.subheader("Preview of Uploaded Data")
        st.dataframe(df.head())

        # Check if user has the essential column(s) for address
        if 'Address' not in df.columns:
            st.error("No 'Address' column found in the uploaded file. Please ensure it exists.")
            return

        # 3. Add a new column for Home Value
        #    We'll do this in a loop, calling a helper function that queries the Zillow API.
        home_values = []
        for i, row in df.iterrows():
            address_str = row['Address']
            # Optional: If you have separate columns for City, State, etc., build a full address
            # e.g. address_str = f"{row['Address']}, {row['City']}, {row['State']} {row['ZIP']}"

            # Call the function to get the Zestimate
            zestimate = get_zestimate_from_zillow(address_str)
            home_values.append(zestimate)

            # Throttle requests slightly to avoid hitting rate limits, if needed
            time.sleep(0.5)

        # Assign the new column to the DataFrame
        df['Estimated Home Value'] = home_values

        st.subheader("Enriched Data")
        st.dataframe(df.head(20))

        # 4. Provide a download button for the enriched data
        st.download_button(
            label="Download Enriched Data as CSV",
            data=df.to_csv(index=False),
            file_name="enriched_home_values.csv",
            mime="text/csv"
        )


def get_zestimate_from_zillow(full_address: str) -> float:
    """
    Given a full address string, use Zillow's API (via RapidAPI) 
    to retrieve a home value (Zestimate). Returns 0.0 if not found.
    """

    # This uses the "Search" endpoint to get a "zpid" from an address,
    # then fetches the "Zestimate" from a second endpoint.
    # The exact approach may vary depending on which endpoints you are using.
    # Below is a *conceptual* example.

    try:
        # 1) Get ZPID from address search
        zpid = get_zpid_from_address(full_address)
        if not zpid:
            return 0.0  # If we can't find a ZPID, return 0.0 or None

        # 2) Once we have a ZPID, call the "Zestimate History (Home Values)" endpoint (or similar)
        url = f"https://{RAPIDAPI_HOST}/graph_charts"
        querystring = {
            "recent_first": "True",
            "which": "zestimate_history",
            "byzpid": str(zpid)
        }
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }

        response = requests.get(url, headers=headers, params=querystring)
        if response.status_code != 200:
            st.warning(f"Zestimate request failed for address: {full_address}")
            return 0.0

        data = response.json()
        # Typically you'd parse out the most recent zestimate from data
        # This is just an example—adjust to the actual structure returned:
        zestimate = data.get('data', [{}])[-1].get('zestimate', 0)
        return float(zestimate)

    except Exception as e:
        st.warning(f"Error retrieving Zestimate for {full_address}: {e}")
        return 0.0


def get_zpid_from_address(full_address: str) -> str:
    """
    Use Zillow's 'Search' endpoint (or 'Property Info' endpoint) to retrieve the zpid
    corresponding to the address. Return None if not found or on error.
    """

    # For example, there's an endpoint:
    # GET /searchZillow?location=...
    # or GET /propertySearch?address=...
    # This code depends on your chosen endpoint from the Zillow Working API on RapidAPI.
    # Adjust the URL and querystring for your specific endpoint.

    try:
        search_url = f"https://{RAPIDAPI_HOST}/search_zillow"
        query = {
            "location": full_address
        }
        headers = {
            "X-RapidAPI-Key": RAPIDAPI_KEY,
            "X-RapidAPI-Host": RAPIDAPI_HOST
        }

        resp = requests.get(search_url, headers=headers, params=query)
        if resp.status_code != 200:
            return None

        results = resp.json().get('results', [])
        # Example: The first result might have 'zpid'
        if not results:
            return None
        
        zpid = results[0].get('zpid', None)
        return zpid

    except Exception as e:
        st.warning(f"Error searching ZPID for {full_address}: {e}")
        return None
