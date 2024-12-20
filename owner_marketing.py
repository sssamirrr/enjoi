# main_app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import phonenumbers
from google.oauth2 import service_account
import gspread
import requests
import time

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

        # Add necessary columns
        df['Select'] = False
        df['Call History'] = df['Phone Number'].apply(lambda x: f"/callhistory?phone={x}")

        return df

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {e}")
        return pd.DataFrame()

# Main App Function
def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    # Filters
    st.subheader("Filters")
    col1, col2 = st.columns(2)
    with col1:
        selected_states = st.multiselect("Select States", owner_df['State'].dropna().unique())
    with col2:
        date_range = st.date_input(
            "Sale Date Range",
            [owner_df['Sale Date'].min(), owner_df['Sale Date'].max()]
        )

    # Apply Filters
    filtered_df = owner_df.copy()
    if selected_states:
        filtered_df = filtered_df[filtered_df['State'].isin(selected_states)]
    if date_range:
        filtered_df = filtered_df[(filtered_df['Sale Date'] >= pd.Timestamp(date_range[0])) &
                                  (filtered_df['Sale Date'] <= pd.Timestamp(date_range[1]))]

    # Display Table
    st.subheader("Owner Data")
    st.data_editor(
        filtered_df,
        use_container_width=True,
        column_config={
            "Call History": st.column_config.LinkColumn(display_text="View Call History")
        },
        key='data_editor'
    )

def run_minimal_app():
    owner_df = get_owner_sheet_data()
    if not owner_df.empty:
        run_owner_marketing_tab(owner_df)
    else:
        st.error("No owner data available.")

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    run_minimal_app()
