import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import requests
import time

# Hardcoded OpenPhone API Key
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

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
        df['Communication Status'] = "Not Updated"
        df['Last Communication Date'] = None
        df['Total Messages'] = 0
        df['Total Calls'] = 0
        return df

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {e}")
        return pd.DataFrame()

# Rate-Limited API Request
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

# Fetch OpenPhone Communication Data
def get_communication_info(phone_number):
    headers = {"Authorization": OPENPHONE_API_KEY}
    url = "https://api.openphone.com/v1/calls"
    params = {"participants": [phone_number], "maxResults": 50}

    response = rate_limited_request(url, headers, params)
    if response and response.get('data'):
        calls = response['data']
        last_date = max([call['createdAt'] for call in calls], default=None)
        total_calls = len(calls)
        return {
            'Communication Status': "Updated",
            'Last Communication Date': last_date,
            'Total Messages': 0,
            'Total Calls': total_calls,
        }
    else:
        return {
            'Communication Status': "Failed",
            'Last Communication Date': None,
            'Total Messages': 0,
            'Total Calls': 0,
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

    # Display Filtered Table with Checkboxes
    st.subheader("Filtered Owner Data")
    filtered_df = filtered_df.reset_index(drop=True)  # Reset index for consistency
    edited_df = st.data_editor(
        filtered_df,
        use_container_width=True,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", help="Select rows for updates")
        }
    )

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
                        owner_df.at[idx, key] = value
            st.success("Communication info updated!")
            st.dataframe(owner_df)

    # Email and Text Campaign
    st.subheader("Campaign Management")
    campaign_type = st.radio("Select Campaign Type", ["Email", "Text"])
    if campaign_type == "Email":
        email_subject = st.text_input("Email Subject", "Welcome to our Premium Ownership Family")
        email_body = st.text_area("Email Body", "We are excited to have you as part of our community.")
    else:
        text_message = st.text_area("Text Message", "Welcome to our community! Reply STOP to opt out.")

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
