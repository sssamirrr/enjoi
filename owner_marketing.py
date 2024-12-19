import phonenumbers
import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import requests
import time

# Hardcoded OpenPhone API Key and Headers
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

# Format phone number to E.164
def format_phone_number(phone):
    try:
        parsed_phone = phonenumbers.parse(phone, "US")
        if phonenumbers.is_valid_number(parsed_phone):
            return phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
        else:
            return None
    except phonenumbers.NumberParseException:
        return None

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

        # Add communication columns
        df['status'] = "Not Updated"
        df['last_date'] = None
        df['total_messages'] = 0
        df['total_calls'] = 0

        df['Select'] = False  # Selection column
        df = df[['Select'] + [col for col in df.columns if col != 'Select']]  # Move Select to first column
        return df

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {e}")
        return pd.DataFrame()

# Rate-Limited API Request
def rate_limited_request(url, params):
    time.sleep(1 / 5)
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error: {response.status_code}")
            st.warning(f"Response: {response.text}")
    except Exception as e:
        st.warning(f"Exception during request: {str(e)}")
    return None

# Fetch OpenPhone Communication Data
def get_communication_info(phone_number):
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        return {
            'status': "Invalid Number",
            'last_date': None,
            'total_messages': 0,
            'total_calls': 0
        }

    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    response_data = rate_limited_request(phone_numbers_url, {})
    phone_number_ids = [pn.get('id') for pn in response_data.get('data', [])] if response_data else []

    if not phone_number_ids:
        return {
            'status': "No Communications",
            'last_date': None,
            'total_messages': 0,
            'total_calls': 0
        }

    latest_datetime = None
    total_messages = 0
    total_calls = 0

    for phone_number_id in phone_number_ids:
        params = {"phoneNumberId": phone_number_id, "participants": [formatted_phone], "maxResults": 50}

        # Fetch Messages
        messages_response = rate_limited_request(messages_url, params)
        if messages_response:
            total_messages += len(messages_response.get('data', []))

        # Fetch Calls
        calls_response = rate_limited_request(calls_url, params)
        if calls_response:
            calls = calls_response.get('data', [])
            total_calls += len(calls)
            for call in calls:
                call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00'))
                if not latest_datetime or call_time > latest_datetime:
                    latest_datetime = call_time

    status = "No Communications" if not latest_datetime else "Active"
    return {
        'status': status,
        'last_date': latest_datetime.strftime("%Y-%m-%d %H:%M:%S") if latest_datetime else None,
        'total_messages': total_messages,
        'total_calls': total_calls
    }

# Main App Function
def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    # Filters
    st.subheader("Filters")
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_states = st.multiselect("Select States", owner_df['State'].dropna().unique())
    with col2:
        date_range = st.date_input("Sale Date Range", [owner_df['Sale Date'].min(), owner_df['Sale Date'].max()])
    with col3:
        fico_range = st.slider("FICO Score", int(owner_df['Primary FICO'].min()), int(owner_df['Primary FICO'].max()), 
                               (int(owner_df['Primary FICO'].min()), int(owner_df['Primary FICO'].max())))

    # Apply Filters
    filtered_df = owner_df.copy()
    if selected_states:
        filtered_df = filtered_df[filtered_df['State'].isin(selected_states)]
    if date_range:
        filtered_df = filtered_df[(filtered_df['Sale Date'] >= pd.Timestamp(date_range[0])) & 
                                  (filtered_df['Sale Date'] <= pd.Timestamp(date_range[1]))]
    filtered_df = filtered_df[(filtered_df['Primary FICO'] >= fico_range[0]) & (filtered_df['Primary FICO'] <= fico_range[1])]

    # Display Table
    st.subheader("Owner Data")
    edited_df = st.data_editor(filtered_df, use_container_width=True, column_config={
        "Select": st.column_config.CheckboxColumn("Select")
    })

    # Communication Updates
    if st.button("Update Communication Info"):
        selected_rows = edited_df[edited_df['Select']].index.tolist()
        if not selected_rows:
            st.warning("No rows selected!")
        else:
            with st.spinner("Fetching communication info..."):
                for idx in selected_rows:
                    phone_number = filtered_df.at[idx, "Phone Number"]
                    comm_data = get_communication_info(phone_number)
                    for key, value in comm_data.items():
                        filtered_df.at[idx, key] = value
            st.success("Communication info updated!")
            st.dataframe(filtered_df)

# Run Minimal App
def run_minimal_app():
    owner_df = get_owner_sheet_data()
    if not owner_df.empty:
        run_owner_marketing_tab(owner_df)
    else:
        st.error("No owner data available.")

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    run_minimal_app()
