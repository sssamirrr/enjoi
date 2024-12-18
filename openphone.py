# openphone.py

import pandas as pd
import gspread
from google.oauth2 import service_account
import requests
import time

def init_session_state(st):
    if 'default_dates' not in st.session_state:
        st.session_state['default_dates'] = {}
    if 'communication_data' not in st.session_state:
        st.session_state['communication_data'] = {}

def get_google_sheet_data(st):
    try:
        # Retrieve Google Sheets credentials from st.secrets
        service_account_info = st.secrets["gcp_service_account"]

        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ],
        )
        
        # Authorize with gspread using the credentials
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(st.secrets["sheets"]["sheet_key"])
        worksheet = spreadsheet.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None

def rate_limited_request(url, headers, params, request_type='get'):
    time.sleep(1 / 5)  # 5 requests per second max
    try:
        response = requests.get(url, headers=headers, params=params) if request_type == 'get' else None
        return response.json() if response and response.status_code == 200 else None
    except Exception as e:
        return None

def get_all_phone_number_ids(headers):
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    response_data = rate_limited_request(phone_numbers_url, headers, {})
    return [pn.get('id') for pn in response_data.get('data', [])] if response_data else []

def get_communication_info(phone_number, headers):
    # Implementation of function to get communication info
    pass

# Other functions related to OpenPhone can go here.
