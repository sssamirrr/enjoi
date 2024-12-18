import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import time
import phonenumbers
import logging
from logging.handlers import RotatingFileHandler
import pgeocode  # For geocoding ZIP codes to latitude and longitude
import requests  # For OpenPhone API requests

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
@st.cache_data(ttl=600)
def get_owner_sheet_data():
    """
    Fetch owner data from Google Sheets.
    Returns a pandas DataFrame containing owner information.
    """
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
        df = pd.DataFrame(data)

        if df.empty:
            st.warning("The Google Sheet is empty. Please ensure it contains data.")
            logger.warning("Fetched data from Google Sheet is empty.")

        # Data Cleaning
        for date_col in ['Sale Date', 'Maturity Date']:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

        for num_col in ['Points', 'Primary FICO']:
            if num_col in df.columns:
                df[num_col] = pd.to_numeric(df[num_col], errors='coerce')

        if 'Phone Number' in df.columns:
            df['Phone Number'] = df['Phone Number'].astype(str)

        if 'Campaign Type' not in df.columns:
            df['Campaign Type'] = 'Text'  # Default campaign type

        return df

    except gspread.exceptions.SpreadsheetNotFound:
        st.error("Google Sheet not found. Please check the sheet key and permissions.")
        logger.error("Google Sheet not found. Check the sheet key and permissions.")
        return pd.DataFrame()

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {str(e)}")
        logger.error(f"Google Sheet Access Error: {str(e)}")
        return pd.DataFrame()

def format_phone_number(phone):
    """Format phone number to E.164 format"""
    try:
        parsed_phone = phonenumbers.parse(phone, "US")
        if phonenumbers.is_valid_number(parsed_phone):
            return phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return None

def clean_zip_code(zip_code):
    """Clean and validate ZIP code"""
    if pd.isna(zip_code):
        return None
    zip_str = str(zip_code)
    zip_digits = ''.join(filter(str.isdigit, zip_str))
    return zip_digits[:5] if len(zip_digits) >= 5 else None

def get_communication_info(phone_number, headers):
    """
    Fetch communication data for a given phone number from OpenPhone.
    Returns a dictionary with communication details.
    """
    phone_number_ids = get_all_phone_number_ids(headers)
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

    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    latest_datetime = None
    call_duration = None
    agent_name = None

    total_messages = 0
    total_calls = 0
    answered_calls = 0
    missed_calls = 0
    call_attempts = 0

    for phone_number_id in phone_number_ids:
        # Messages pagination
        next_page = None
        while True:
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [phone_number],
                "maxResults": 50
            }
            if next_page:
                params['pageToken'] = next_page

            # Fetch messages
            messages_response = requests.get(messages_url, headers=headers, params=params)
            if messages_response and messages_response.status_code == 200:
                messages = messages_response.json()['data']
                total_messages += len(messages)
                for message in messages:
                    msg_time = datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00'))
                    if not latest_datetime or msg_time > latest_datetime:
                        latest_datetime = msg_time
                        latest_direction = message.get("direction", "unknown")
                        agent_name = message.get("user", {}).get("name", "Unknown Agent")

                next_page = messages_response.json().get('nextPageToken')
                if not next_page:
                    break
            else:
                break

        # Calls pagination
        next_page = None
        while True:
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [phone_number],
                "maxResults": 50
            }
            if next_page:
                params['pageToken'] = next_page

            # Fetch calls
            calls_response = requests.get(calls_url, headers=headers, params=params)
            if calls_response and calls_response.status_code == 200:
                calls = calls_response.json()['data']
                total_calls += len(calls)
                for call in calls:
                    call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00'))
                    if not latest_datetime or call_time > latest_datetime:
                        latest_datetime = call_time
                        call_duration = call.get("duration")
                        agent_name = call.get("user", {}).get("name", "Unknown Agent")

                    call_attempts += 1

                    # Determine if the call was answered
                    call_status = call.get('status', 'unknown')
                    if call_status == 'completed':
                        answered_calls += 1
                    elif call_status in ['missed', 'no-answer', 'busy', 'failed']:
                        missed_calls += 1
                next_page = calls_response.json().get('nextPageToken')
                if not next_page:
                    break
            else:
                break
    
    return {
        'status': "Communication Found",
        'last_date': latest_datetime.strftime("%Y-%m-%d %H:%M:%S") if latest_datetime else None,
        'call_duration': call_duration,
        'agent_name': agent_name,
        'total_messages': total_messages,
        'total_calls': total_calls,
        'answered_calls': answered_calls,
        'missed_calls': missed_calls,
        'call_attempts': call_attempts
    }

def get_all_phone_number_ids(headers):
    """
    Retrieve all phoneNumberIds associated with your OpenPhone account.
    """
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    response_data = requests.get(phone_numbers_url, headers=headers)
    return [pn.get('id') for pn in response_data.json().get('data', [])] if response_data else []

def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    # Display Demo Mode Notification
    if DEMO_MODE:
        st.warning("**Demo Mode Enabled:** No real emails or SMS messages will be sent.")
    else:
        st.success("**Live Mode Enabled:** Emails and SMS messages will be sent as configured.")

    # Campaign Type Selection
    campaign_tabs = st.tabs([" \U0001F4F1 Text Message Campaign", " \U0001F4E9 Email Campaign"])

    # Now, loop over the campaign tabs
    for idx, campaign_type in enumerate(["Text", "Email"]):
        with campaign_tabs[idx]:
            st.header(f"{campaign_type} Campaign Management")

            # Apply filters inside the tab
            with st.expander(" \u2699\ufe0f", expanded=True):
                col1, col2, col3 = st.columns(3)

                # Column 1 Filters
                with col1:
                    selected_states = []
                    if 'State' in owner_df.columns:
                        states = sorted(owner_df['State'].dropna().unique().tolist())
                        selected_states = st.multiselect(
                            'Select States',
                            states,
                            key=f'states_{campaign_type}'
                        )

                    selected_unit = 'All'
                    if 'Unit' in owner_df.columns:
                        units = ['All'] + sorted(owner_df['Unit'].dropna().unique().tolist())
                        selected_unit = st.selectbox(
                            'Unit Type',
                            units,
                            key=f'unit_{campaign_type}'
                        )

                # Column 2 Filters
                with col2:
                    sale_date_min = owner_df['Sale Date'].min().date() if 'Sale Date' in owner_df.columns else datetime.today().date()
                    sale_date_max = owner_df['Sale Date'].max().date() if 'Sale Date' in owner_df.columns else datetime.today().date()
                    date_range = st.date_input(
                        'Sale Date Range',
                        value=(sale_date_min, sale_date_max),
                        key=f'dates_{campaign_type}'
                    )

                # Column 3 Filters (FICO)
                with col3:
                    fico_range = (300, 850)
                    if 'Primary FICO' in owner_df.columns:
                        valid_fico = owner_df['Primary FICO'].dropna()
                        if not valid_fico.empty:
                            min_fico = max(300, int(valid_fico.min()))
                            max_fico = min(850, int(valid_fico.max()))
                            fico_range = st.slider(
                                'FICO Score Range',
                                min_value=300,
                                max_value=850,
                                value=(min_fico, max_fico),
                                key=f'fico_{campaign_type}'
                            )
                        else:
                            fico_range = st.slider(
                                'FICO Score Range',
                                min_value=300,
                                max_value=850,
                                value=(300, 850),
                                key=f'fico_{campaign_type}'
                            )

            # Apply filters to the data
            campaign_filtered_df = owner_df.copy()

            if selected_states:
                campaign_filtered_df = campaign_filtered_df[campaign_filtered_df['State'].isin(selected_states)]

            if selected_unit != 'All':
                campaign_filtered_df = campaign_filtered_df[campaign_filtered_df['Unit'] == selected_unit]

            if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
                campaign_filtered_df = campaign_filtered_df[
                    (campaign_filtered_df['Sale Date'].dt.date >= date_range[0]) &
                    (campaign_filtered_df['Sale Date'].dt.date <= date_range[1])
                ]

            if 'Primary FICO' in campaign_filtered_df.columns:
                campaign_filtered_df = campaign_filtered_df[
                    (campaign_filtered_df['Primary FICO'] >= fico_range[0]) &
                    (campaign_filtered_df['Primary FICO'] <= fico_range[1])
                ]

            # Show Dataframe with Selectable Rows
            st.subheader("Filtered Owner Sheets Data")
            if campaign_filtered_df.empty:
                st.warning("No data matches the selected filters.")
            else:
                # Add a 'Select' checkbox for each row
                selected_rows = []
                for index, row in campaign_filtered_df.iterrows():
                    if st.checkbox(f"{row['Phone Number']} (Owner Name: {row.get('Owner Name', 'N/A')})", key=index):
                        selected_rows.append(row)

                if st.button("Fetch Communication Info for Selected"):
                    headers = {
                        "Authorization": st.secrets["openphone_api_key"],
                        "Content-Type": "application/json"
                    }

                    # Initialize lists to hold fetched communication information
                    statuses, dates, durations, agent_names = [], [], [], []
                    total_messages_list, total_calls_list = [], []
                    answered_calls_list, missed_calls_list, call_attempts_list = [], [], []

                    # Iterate over the selected rows and fetch their communication info
                    for row in selected_rows:
                        phone = row['Phone Number']
                        try:
                            comm_info = get_communication_info(phone, headers)
                            statuses.append(comm_info['status'])
                            dates.append(comm_info['last_date'])
                            durations.append(comm_info['call_duration'])
                            agent_names.append(comm_info['agent_name'])
                            total_messages_list.append(comm_info['total_messages'])
                            total_calls_list.append(comm_info['total_calls'])
                            answered_calls_list.append(comm_info['answered_calls'])
                            missed_calls_list.append(comm_info['missed_calls'])
                            call_attempts_list.append(comm_info['call_attempts'])
                        except Exception as e:
                            statuses.append("Error")
                            dates.append(None)
                            durations.append(None)
                            agent_names.append("Unknown")
                            total_messages_list.append(0)
                            total_calls_list.append(0)
                            answered_calls_list.append(0)
                            missed_calls_list.append(0)
                            call_attempts_list.append(0)

                    # Create a DataFrame from the fetched data
                    comm_df = pd.DataFrame({
                        'Phone Number': [row['Phone Number'] for row in selected_rows],
                        'Status': statuses,
                        'Last Date': dates,
                        'Call Duration (s)': durations,
                        'Agent Name': agent_names,
                        'Total Messages': total_messages_list,
                        'Total Calls': total_calls_list,
                        'Answered Calls': answered_calls_list,
                        'Missed Calls': missed_calls_list,
                        'Call Attempts': call_attempts_list
                    })

                    # Display the communication info DataFrame
                    st.subheader("Fetched Communication Information")
                    st.dataframe(comm_df)

            # Continue with the existing campaign setup and execution logic...
            # Add here the metrics and message templates along with the campaign execution buttons...

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
