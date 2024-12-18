import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import time
import phonenumbers
import logging
from logging.handlers import RotatingFileHandler
import pgeocode
import requests

# Define a global flag for demo mode
DEMO_MODE = True  # Set to False to enable live functionality

# Setup logging with rotation to manage log file sizes
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = RotatingFileHandler('campaign.log', maxBytes=1000000, backupCount=5)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Cache data fetching to improve performance
def get_owner_sheet_data():
    """
    Fetch owner data from Google Sheets.
    Returns a pandas DataFrame containing owner information.
    """
    try:
        # Log the start of the process
        logger.info("Attempting to fetch data from Google Sheets...")

        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ],
        )

        client = gspread.authorize(credentials)
        sheet_key = st.secrets["owners_sheets"]["owners_sheet_key"]
        sheet = client.open_by_key(sheet_key)
        worksheet = sheet.get_worksheet(0)
        data = worksheet.get_all_records()

        if not data:
            logger.warning("Google Sheet is empty.")
            st.warning("The Google Sheet is empty. Please ensure it contains data.")
            return pd.DataFrame()

        df = pd.DataFrame(data)
        logger.info(f"Successfully fetched {len(df)} rows from Google Sheets.")

        # Data Cleaning
        for date_col in ['Sale Date', 'Maturity Date']:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

        for num_col in ['Points', 'Primary FICO']:
            if num_col in df.columns:
                df[num_col] = pd.to_numeric(df[num_col], errors='coerce')

        if 'Phone Number' in df.columns:
            df['Phone Number'] = df['Phone Number'].astype(str)

        # Add communication-related columns
        df['Last Communication Status'] = ""
        df['Last Communication Date'] = ""
        df['Total Calls'] = 0
        df['Total Messages'] = 0
        df['Select'] = False

        return df

    except gspread.exceptions.SpreadsheetNotFound:
        st.error("Google Sheet not found. Please check the sheet key and permissions.")
        logger.error("Google Sheet not found. Check the sheet key and permissions.")
        return pd.DataFrame()

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {str(e)}")
        logger.error(f"Google Sheet Access Error: {str(e)}")
        return pd.DataFrame()

# Function to fetch communication data from OpenPhone
def fetch_openphone_data(phone_number):
    """
    Fetch communication data (calls and messages) for a given phone number from OpenPhone.
    """
    OPENPHONE_API_KEY = st.secrets["openphone_api_key"]
    headers = {
        "Authorization": f"Bearer {OPENPHONE_API_KEY}",
        "Content-Type": "application/json"
    }
    url = "https://api.openphone.co/v1/calls"
    params = {"participants": [phone_number], "maxResults": 50}

    try:
        logger.info(f"Fetching OpenPhone data for {phone_number}...")
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            data = response.json().get('data', [])
            total_calls = len([d for d in data if d.get("type") == "call"])
            total_messages = len([d for d in data if d.get("type") == "message"])
            last_communication = max(data, key=lambda x: x.get('createdAt', 0), default=None)
            status = last_communication.get("status", "") if last_communication else "No Communications"
            last_date = last_communication.get("createdAt", "") if last_communication else None
            return {
                "Last Communication Status": status,
                "Last Communication Date": last_date,
                "Total Calls": total_calls,
                "Total Messages": total_messages
            }
        else:
            logger.error(f"OpenPhone API error: {response.status_code} - {response.text}")
            return {
                "Last Communication Status": "API Error",
                "Last Communication Date": None,
                "Total Calls": 0,
                "Total Messages": 0
            }
    except Exception as e:
        logger.error(f"Error fetching OpenPhone data for {phone_number}: {str(e)}")
        return {
            "Last Communication Status": "Error",
            "Last Communication Date": None,
            "Total Calls": 0,
            "Total Messages": 0
        }

# Function to update communication info for selected rows
def update_communication_info(df, selected_rows):
    """
    Update the communication info for selected rows in the DataFrame.
    """
    for idx in selected_rows:
        phone_number = df.at[idx, "Phone Number"]
        communication_data = fetch_openphone_data(phone_number)
        df.at[idx, "Last Communication Status"] = communication_data["Last Communication Status"]
        df.at[idx, "Last Communication Date"] = communication_data["Last Communication Date"]
        df.at[idx, "Total Calls"] = communication_data["Total Calls"]
        df.at[idx, "Total Messages"] = communication_data["Total Messages"]
    return df

# Run the main Streamlit app
def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    # Interactive table for editing
    st.subheader("Owner Data")
    for i in range(len(owner_df)):
        owner_df.at[i, 'Select'] = st.checkbox(f"Select Row {i+1}", key=f"row_{i}")

    # Button to update communication info
    if st.button("Update Communication Info"):
        selected_rows = [i for i in range(len(owner_df)) if owner_df.at[i, 'Select']]
        if not selected_rows:
            st.warning("No rows selected. Please select rows to update.")
        else:
            with st.spinner("Fetching communication info..."):
                updated_df = update_communication_info(owner_df, selected_rows)
            st.success("Communication info updated successfully!")
            st.dataframe(updated_df)

def run_minimal_app():
    st.title("Owner Marketing Dashboard")
    owner_df = get_owner_sheet_data()
    if not owner_df.empty:
        run_owner_marketing_tab(owner_df)
    else:
        st.error("No owner data available to display.")

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    run_minimal_app()
