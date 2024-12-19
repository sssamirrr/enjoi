import phonenumbers
import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import requests
import time

# Hardcoded OpenPhone API Key and Headers
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6aebhl6lG6Z7"
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

# Fetch Detailed Communication Logs
def get_detailed_logs(phone_number):
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        return None, None

    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    # Fetch all communication details
    response_data = requests.get(phone_numbers_url, headers=HEADERS).json()
    phone_number_ids = [pn.get('id') for pn in response_data.get('data', [])] if response_data else []

    if not phone_number_ids:
        return None, None

    messages = []
    calls = []

    for phone_number_id in phone_number_ids:
        params = {"phoneNumberId": phone_number_id, "participants": [formatted_phone], "maxResults": 50}

        # Fetch Messages
        messages_response = requests.get(messages_url, headers=HEADERS, params=params).json()
        if messages_response:
            messages.extend(messages_response.get('data', []))

        # Fetch Calls
        calls_response = requests.get(calls_url, headers=HEADERS, params=params).json()
        if calls_response:
            calls.extend(calls_response.get('data', []))

    return messages, calls

# Detailed Logs Page
def detailed_logs_page(phone_number):
    st.title(f"Communication Logs for {phone_number}")

    messages, calls = get_detailed_logs(phone_number)

    if messages:
        st.subheader("Messages")
        messages_df = pd.DataFrame([
            {
                "Message ID": msg["id"],
                "Content": msg["content"],
                "Created At": datetime.fromisoformat(msg["createdAt"].replace('Z', '+00:00'))
            }
            for msg in messages
        ])
        st.dataframe(messages_df)

    if calls:
        st.subheader("Calls")
        calls_df = pd.DataFrame([
            {
                "Call ID": call["id"],
                "Direction": call["direction"],
                "Duration (s)": call["duration"],
                "Created At": datetime.fromisoformat(call["createdAt"].replace('Z', '+00:00'))
            }
            for call in calls
        ])
        st.dataframe(calls_df)

    if not messages and not calls:
        st.warning("No communication logs found.")

# Main Tab with Links
def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    # Add links for communication logs
    owner_df["Logs Link"] = owner_df["Phone Number"].apply(
        lambda x: f'<a href="?phone={x}" target="_self">View Logs</a>'
    )

    # Render HTML table with links
    st.subheader("Owner Data")
    st.markdown(
        owner_df.to_html(escape=False, index=False), 
        unsafe_allow_html=True
    )

    # Handle query parameter for phone number
    query_params = st.query_params
    phone_number = query_params.get("phone")
    if phone_number:
        detailed_logs_page(phone_number)

# Main App Function
def run_minimal_app():
    owner_df = get_owner_sheet_data()
    if not owner_df.empty:
        run_owner_marketing_tab(owner_df)
    else:
        st.error("No owner data available.")

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    run_minimal_app()
