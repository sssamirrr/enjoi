import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import pgeocode
import requests
import time

# Define DEMO Mode
DEMO_MODE = True  # Set to False to enable live functionality

# Fetch Google Sheets Data
def get_owner_sheet_data():
    try:
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
            st.warning("The Google Sheet is empty.")
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Clean Data
        for col in ['Sale Date', 'Maturity Date']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
        df['Select'] = False  # Selection column
        df = df[['Select'] + [col for col in df.columns if col != 'Select']]  # Move Select to first column
        return df

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {e}")
        return pd.DataFrame()

# Function to manage API requests with rate limiting
def rate_limited_request(url, headers, params, request_type='get'):
    time.sleep(1 / 5)  # 5 requests per second max
    try:
        response = requests.get(url, headers=headers, params=params) if request_type == 'get' else None
        if response and response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error: {response.status_code}")
            st.warning(f"Response: {response.text}")
    except Exception as e:
        st.warning(f"Exception during request: {str(e)}")
    return None

# Fetch OpenPhone Data
def get_communication_info(phone_number, headers):
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    response_data = rate_limited_request(phone_numbers_url, headers, {})
    phone_number_ids = [pn.get('id') for pn in response_data.get('data', [])] if response_data else []

    # If no phone numbers are associated with the account
    if not phone_number_ids:
        return {
            'status': "No Communications",
            'last_date': None,
            'call_duration': None,
            'agent_name': None,
            'total_messages': 0,
            'total_calls': 0,
            'answered_calls': 0,
            'missed_calls': 0,
            'call_attempts': 0
        }

    latest_datetime = None
    total_messages = 0
    total_calls = 0
    answered_calls = 0
    missed_calls = 0
    call_attempts = 0
    agent_name = "Unknown"

    for phone_number_id in phone_number_ids:
        params = {"phoneNumberId": phone_number_id, "participants": [phone_number], "maxResults": 50}

        # Fetch Messages
        messages_response = rate_limited_request(messages_url, headers, params)
        if messages_response:
            total_messages += len(messages_response.get('data', []))

        # Fetch Calls
        calls_response = rate_limited_request(calls_url, headers, params)
        if calls_response:
            calls = calls_response.get('data', [])
            total_calls += len(calls)
            for call in calls:
                call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00'))
                if not latest_datetime or call_time > latest_datetime:
                    latest_datetime = call_time
                    agent_name = call.get('user', {}).get('name', 'Unknown Agent')
                call_status = call.get('status', 'unknown')
                call_attempts += 1
                if call_status == 'completed':
                    answered_calls += 1
                elif call_status in ['missed', 'no-answer']:
                    missed_calls += 1

    status = "No Communications" if not latest_datetime else "Call - Latest"
    return {
        'status': status,
        'last_date': latest_datetime.strftime("%Y-%m-%d %H:%M:%S") if latest_datetime else None,
        'agent_name': agent_name,
        'total_messages': total_messages,
        'total_calls': total_calls,
        'answered_calls': answered_calls,
        'missed_calls': missed_calls,
        'call_attempts': call_attempts
    }

def fetch_communication_info(guest_df, headers):
    statuses, dates, agents = [], [], []
    total_messages, total_calls = [], []
    answered_calls, missed_calls, call_attempts = [], [], []

    for _, row in guest_df.iterrows():
        phone = row['Phone Number']
        if phone:
            comm_info = get_communication_info(phone, headers)
            statuses.append(comm_info['status'])
            dates.append(comm_info['last_date'])
            agents.append(comm_info['agent_name'])
            total_messages.append(comm_info['total_messages'])
            total_calls.append(comm_info['total_calls'])
            answered_calls.append(comm_info['answered_calls'])
            missed_calls.append(comm_info['missed_calls'])
            call_attempts.append(comm_info['call_attempts'])
        else:
            statuses.append("Invalid Number")
            dates.append(None)
            agents.append("Unknown")
            total_messages.append(0)
            total_calls.append(0)
            answered_calls.append(0)
            missed_calls.append(0)
            call_attempts.append(0)

    return statuses, dates, agents, total_messages, total_calls, answered_calls, missed_calls, call_attempts

# Main App Function
def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    headers = {"Authorization": f"Bearer {st.secrets['openphone']['api_key']}"}

    # Apply Filters
    st.subheader("Owner Data")
    statuses, dates, agents, total_messages, total_calls, answered_calls, missed_calls, call_attempts = fetch_communication_info(owner_df, headers)
    owner_df['Status'] = statuses
    owner_df['Last Communication Date'] = dates
    owner_df['Agent Name'] = agents
    owner_df['Total Messages'] = total_messages
    owner_df['Total Calls'] = total_calls

    st.dataframe(owner_df)

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    owner_df = get_owner_sheet_data()
    if not owner_df.empty:
        run_owner_marketing_tab(owner_df)
    else:
        st.error("No owner data available.")
