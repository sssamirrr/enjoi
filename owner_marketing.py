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
import json

# Define a global flag for demo mode
DEMO_MODE = True  # Set to False to enable live functionality

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
handler = RotatingFileHandler('campaign.log', maxBytes=1000000, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def initialize_connection():
    """Initialize Google Sheets connection with error handling"""
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ],
        )
        return gspread.authorize(credentials)
    except Exception as e:
        logger.error(f"Failed to initialize connection: {str(e)}")
        raise

@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_owner_sheet_data():
    """
    Fetch and process owner data from Google Sheets with error handling and data validation
    """
    try:
        logger.info("Fetching data from Google Sheets...")
        
        # Initialize connection
        client = initialize_connection()
        sheet_key = st.secrets["owners_sheets"]["owners_sheet_key"]
        sheet = client.open_by_key(sheet_key)
        worksheet = sheet.get_worksheet(0)
        data = worksheet.get_all_records()

        if not data:
            logger.warning("No data found in Google Sheet")
            return pd.DataFrame()

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Data cleaning and validation
        df = clean_and_validate_data(df)

        logger.info(f"Successfully fetched {len(df)} rows of data")
        return df

    except Exception as e:
        logger.error(f"Error in get_owner_sheet_data: {str(e)}")
        raise

def clean_and_validate_data(df):
    """Clean and validate the DataFrame"""
    try:
        # Convert date columns
        date_columns = ['Sale Date', 'Maturity Date']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

        # Convert numeric columns
        numeric_columns = ['Points', 'Primary FICO']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # Clean phone numbers
        if 'Phone Number' in df.columns:
            df['Phone Number'] = df['Phone Number'].astype(str)
            df['Phone Number'] = df['Phone Number'].apply(clean_phone_number)

        # Add communication tracking columns
        tracking_columns = {
            'Last Communication Status': '',
            'Last Communication Date': '',
            'Total Calls': 0,
            'Total Messages': 0,
            'Select': False
        }

        for col, default_value in tracking_columns.items():
            if col not in df.columns:
                df[col] = default_value

        return df

    except Exception as e:
        logger.error(f"Error in clean_and_validate_data: {str(e)}")
        raise

def clean_phone_number(phone):
    """Clean and format phone numbers"""
    try:
        if pd.isna(phone) or phone == '':
            return ''
        # Remove any non-numeric characters
        cleaned = ''.join(filter(str.isdigit, str(phone)))
        # Ensure proper length and format
        if len(cleaned) == 10:
            cleaned = '1' + cleaned
        elif len(cleaned) > 11 or len(cleaned) < 10:
            return ''
        return cleaned
    except Exception as e:
        logger.error(f"Error cleaning phone number: {str(e)}")
        return ''

def fetch_openphone_data(phone_number):
    """
    Fetch communication data from OpenPhone API with error handling
    """
    if DEMO_MODE:
        # Return mock data in demo mode
        return {
            "Last Communication Status": "Demo Mode",
            "Last Communication Date": datetime.now().isoformat(),
            "Total Calls": 0,
            "Total Messages": 0
        }

    try:
        OPENPHONE_API_KEY = st.secrets["openphone_api_key"]
        headers = {
            "Authorization": f"Bearer {OPENPHONE_API_KEY}",
            "Content-Type": "application/json"
        }
        url = "https://api.openphone.co/v1/calls"
        params = {"participants": [phone_number], "maxResults": 50}

        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes

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

    except requests.exceptions.RequestException as e:
        logger.error(f"OpenPhone API error: {str(e)}")
        return {
            "Last Communication Status": "API Error",
            "Last Communication Date": None,
            "Total Calls": 0,
            "Total Messages": 0
        }

def update_communication_info(df, selected_rows):
    """Update communication information for selected rows"""
    try:
        for idx in selected_rows:
            if idx in df.index and "Phone Number" in df.columns:
                phone_number = df.loc[idx, "Phone Number"]
                if phone_number:
                    communication_data = fetch_openphone_data(phone_number)
                    
                    # Update the DataFrame using .loc
                    for key, value in communication_data.items():
                        if key in df.columns:
                            df.loc[idx, key] = value
                    
                    # Add a small delay to avoid API rate limits
                    time.sleep(0.1)
        
        return df

    except Exception as e:
        logger.error(f"Error in update_communication_info: {str(e)}")
        raise

def run_owner_marketing_tab(owner_df):
    """Main function to run the owner marketing dashboard"""
    try:
        st.title("Owner Marketing Dashboard")

        # Reset index and ensure proper column setup
        owner_df = owner_df.reset_index(drop=True)
        
        # Display filters
        with st.expander("Filters"):
            # Add your filter controls here
            pass

        # Create selection interface
        st.subheader("Select Owners to Update")
        
        # Create checkboxes for selection
        selected_rows = []
        for index, row in owner_df.iterrows():
            owner_df.loc[index, 'Select'] = st.checkbox(
                f"Select Row {index+1}", 
                value=owner_df.loc[index, 'Select'],
                key=f"row_{index}"
            )
            if owner_df.loc[index, 'Select']:
                selected_rows.append(index)

        # Update button
        if st.button("Update Communication Info"):
            if not selected_rows:
                st.warning("Please select at least one row to update.")
            else:
                with st.spinner("Updating communication information..."):
                    owner_df = update_communication_info(owner_df, selected_rows)
                st.success(f"Updated {len(selected_rows)} rows successfully!")

        # Display the DataFrame
        st.subheader("Owner Data")
        st.dataframe(owner_df)

    except Exception as e:
        logger.error(f"Error in run_owner_marketing_tab: {str(e)}")
        st.error("An error occurred while running the dashboard. Please check the logs for details.")

def run_minimal_app():
    """Main application entry point"""
    try:
        st.set_page_config(page_title="Owner Marketing", layout="wide")
        
        owner_df = get_owner_sheet_data()
        if not owner_df.empty:
            run_owner_marketing_tab(owner_df)
        else:
            st.error("No data available. Please check the Google Sheet connection.")

    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        st.error("An error occurred while starting the application. Please check the logs for details.")

if __name__ == "__main__":
    run_minimal_app()
