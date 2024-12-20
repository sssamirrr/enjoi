# owner_marketing.py

import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import time
from urllib.parse import quote  # For URL encoding

# Import the callhistory module (Ensure it's in your PYTHONPATH or same directory)
import callhistory

# Define the function to get owner sheet data
def get_owner_sheet_data():
    """
    Retrieves the data from the Google Sheet and returns it as a Pandas DataFrame.
    """
    # Create a connection to Google Sheets
    # Note: Replace 'your_service_account_info' with your actual service account credentials
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
        ],
    )
    # Authorize the gspread client
    client = gspread.authorize(credentials)

    # Open the Google Sheet by URL or by name
    # Replace 'YOUR_GOOGLE_SHEET_URL' with your actual sheet URL
    sheet = client.open_by_url(st.secrets["private_gsheets_url"]).sheet1

    # Get all records from the sheet
    data = sheet.get_all_records()

    # Convert the data to a Pandas DataFrame
    df = pd.DataFrame(data)

    return df

# Define the main function to run the owner marketing tab
def run_owner_marketing_tab():
    st.title("Owner Marketing")

    # Retrieve owner sheet data
    owner_df = get_owner_sheet_data()

    # Perform any preprocessing or setup required
    # For example, you might initialize or reset session state variables

    # Display the dataframe and other UI elements
    # ... [Your existing code for displaying and interacting with the data] ...

    # Communication Updates
    if st.button("Update Communication Info", key="update_button"):
        selected_rows = edited_df[edited_df['Select']].index.tolist()
        if not selected_rows:
            st.warning("No rows selected!")
        else:
            with st.spinner("Fetching communication info..."):
                for idx in selected_rows:
                    phone_number = edited_df.at[idx, "Phone Number"]
                    try:
                        comm_data = callhistory.get_communication_info(phone_number, HEADERS)
                        for key, value in comm_data.items():
                            # Update both DataFrames
                            edited_df.at[idx, key] = value
                            st.session_state.working_df.at[idx, key] = value
                    except Exception as e:
                        st.warning(f"Error fetching communication info for {phone_number}: {e}")
                        continue  # Proceed to the next phone number if there's an error

            st.success("Communication info updated!")
            st.experimental_rerun()

# Define the function to display call history
def display_call_history(phone_number):
    st.title(f"Call History for {phone_number}")
    # Fetch and display call history data
    try:
        call_history_data = callhistory.get_call_history_data(phone_number, HEADERS)
        if not call_history_data.empty:
            st.dataframe(call_history_data, use_container_width=True)
        else:
            st.warning("No call history available for this number.")
    except Exception as e:
        st.warning(f"Error fetching call history for {phone_number}: {e}")
