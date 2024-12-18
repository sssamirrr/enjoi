import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import logging
from logging.handlers import RotatingFileHandler
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

# Fetch Google Sheets data
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
            st.warning("The Google Sheet is empty. Please ensure it contains data.")
            return pd.DataFrame()

        df = pd.DataFrame(data)

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

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {str(e)}")
        return pd.DataFrame()

# Fetch OpenPhone data
def fetch_openphone_data(phone_number):
    OPENPHONE_API_KEY = st.secrets["openphone_api_key"]
    headers = {
        "Authorization": f"Bearer {OPENPHONE_API_KEY}",
        "Content-Type": "application/json"
    }
    url = "https://api.openphone.co/v1/calls"
    params = {"participants": [phone_number], "maxResults": 50}

    try:
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
    except Exception:
        return {
            "Last Communication Status": "Error",
            "Last Communication Date": None,
            "Total Calls": 0,
            "Total Messages": 0
        }

# Update communication info
def update_communication_info(df, selected_rows):
    for idx in selected_rows:
        phone_number = df.at[idx, "Phone Number"]
        communication_data = fetch_openphone_data(phone_number)
        df.at[idx, "Last Communication Status"] = communication_data["Last Communication Status"]
        df.at[idx, "Last Communication Date"] = communication_data["Last Communication Date"]
        df.at[idx, "Total Calls"] = communication_data["Total Calls"]
        df.at[idx, "Total Messages"] = communication_data["Total Messages"]
    return df

# Main App Function
def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    # Filters
    st.subheader("Filters")
    col1, col2, col3 = st.columns(3)

    with col1:
        states = owner_df['State'].dropna().unique()
        selected_states = st.multiselect("Filter by State", states)

    with col2:
        min_date, max_date = owner_df['Sale Date'].min(), owner_df['Sale Date'].max()
        date_range = st.date_input("Filter by Sale Date Range", [min_date, max_date])

    with col3:
        ficos = owner_df['Primary FICO'].dropna()
        min_fico, max_fico = st.slider("Filter by FICO Score", int(ficos.min()), int(ficos.max()), (int(ficos.min()), int(ficos.max())))

    # Apply filters
    filtered_df = owner_df.copy()
    if selected_states:
        filtered_df = filtered_df[filtered_df['State'].isin(selected_states)]
    if date_range:
        filtered_df = filtered_df[(filtered_df['Sale Date'] >= pd.Timestamp(date_range[0])) &
                                  (filtered_df['Sale Date'] <= pd.Timestamp(date_range[1]))]
    filtered_df = filtered_df[(filtered_df['Primary FICO'] >= min_fico) & (filtered_df['Primary FICO'] <= max_fico)]

    # Add checkboxes for row selection
    st.subheader("Owner Data")
    selected_rows = []
    for idx in filtered_df.index:
        selected = st.checkbox(f"Select Row {idx}", key=f"select_{idx}")
        filtered_df.at[idx, "Select"] = selected
        if selected:
            selected_rows.append(idx)

    # Display filtered table
    st.dataframe(filtered_df.drop(columns=["Select"]), use_container_width=True)

    # Update Communication Info Button
    if st.button("Update Communication Info"):
        if not selected_rows:
            st.warning("No rows selected. Please select rows to update.")
        else:
            with st.spinner("Fetching communication info..."):
                updated_df = update_communication_info(filtered_df, selected_rows)
            st.success("Communication info updated successfully!")
            st.dataframe(updated_df)

    # Campaign Management
    st.subheader("Message Templates")
    campaign_type = st.radio("Choose Campaign Type", ["Text", "Email"])
    if campaign_type == "Text":
        message_template = st.text_area("Text Message", "Welcome to our premium ownership program!")
    else:
        subject = st.text_input("Email Subject", "Welcome to Our Program")
        email_body = st.text_area("Email Body", "Dear Customer,\n\nWelcome to our program!")

    if st.button("Send Campaign"):
        for idx in selected_rows:
            if campaign_type == "Text":
                phone = filtered_df.at[idx, "Phone Number"]
                st.write(f"Sending text to {phone}: {message_template}")
            else:
                email = filtered_df.at[idx, "Email"]
                st.write(f"Sending email to {email}: {subject} - {email_body}")
        st.success("Campaign sent successfully!")

def run_minimal_app():
    owner_df = get_owner_sheet_data()
    if not owner_df.empty:
        run_owner_marketing_tab(owner_df)
    else:
        st.error("No owner data available to display.")

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    run_minimal_app()
