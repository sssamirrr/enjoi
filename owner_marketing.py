# main_app.py
import streamlit as st
import pandas as pd
from datetime import datetime, date
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
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_states = st.multiselect("Select States", owner_df['State'].dropna().unique())
    with col2:
        # Ensure `Sale Date` is properly converted to datetime and handle missing values
        if 'Sale Date' in owner_df.columns:
            owner_df['Sale Date'] = pd.to_datetime(owner_df['Sale Date'], errors='coerce')

            # Determine minimum and maximum valid dates
            if not owner_df['Sale Date'].dropna().empty:
                min_date = owner_df['Sale Date'].min().date()
                max_date = owner_df['Sale Date'].max().date()
            else:
                min_date = date.today()
                max_date = date.today()
        else:
            min_date = date.today()
            max_date = date.today()

        # Use the determined range in the date input
        try:
            date_range = st.date_input(
                "Sale Date Range",
                [min_date, max_date]
            )
        except Exception as e:
            st.error(f"An error occurred while initializing the date input: {e}")
            date_range = [date.today(), date.today()]

    with col3:
        if 'FICO Score' in owner_df.columns:
            fico_min = int(owner_df['FICO Score'].min())
            fico_max = int(owner_df['FICO Score'].max())
            fico_range = st.slider("Filter by FICO Score", fico_min, fico_max, (fico_min, fico_max))

    # Apply Filters
    filtered_df = owner_df.copy()
    if selected_states:
        filtered_df = filtered_df[filtered_df['State'].isin(selected_states)]
    if date_range:
        filtered_df = filtered_df[(filtered_df['Sale Date'] >= pd.Timestamp(date_range[0])) &
                                  (filtered_df['Sale Date'] <= pd.Timestamp(date_range[1]))]
    if 'FICO Score' in owner_df.columns and 'fico_range' in locals():
        filtered_df = filtered_df[(filtered_df['FICO Score'] >= fico_range[0]) &
                                  (filtered_df['FICO Score'] <= fico_range[1])]

    # Display Table
    st.subheader("Owner Data")
    if 'Select' in filtered_df.columns:
        cols = ['Select'] + [col for col in filtered_df.columns if col != 'Select']
        filtered_df = filtered_df[cols]

    st.data_editor(
        filtered_df,
        use_container_width=True,
        column_config={
            "Call History": st.column_config.LinkColumn(display_text="View Call History")
        },
        key='data_editor'
    )

def run_text_marketing_tab(owner_df):
    st.title("Text Marketing Dashboard")

    st.subheader("Send Bulk Texts")
    col1, col2 = st.columns(2)
    with col1:
        selected_rows = st.multiselect("Select Owners to Message", owner_df.index.tolist())
    with col2:
        message = st.text_area("Message Content")

    if st.button("Send Messages"):
        if not selected_rows or not message:
            st.warning("Please select owners and enter a message.")
        else:
            for idx in selected_rows:
                phone_number = owner_df.loc[idx, "Phone Number"]
                formatted_phone = format_phone_number(phone_number)
                if formatted_phone:
                    st.write(f"Message sent to {formatted_phone}: {message}")
                else:
                    st.error(f"Invalid phone number: {phone_number}")

def run_minimal_app():
    owner_df = get_owner_sheet_data()
    if not owner_df.empty:
        tab1, tab2 = st.tabs(["Owner Marketing", "Text Marketing"])

        with tab1:
            run_owner_marketing_tab(owner_df)
        with tab2:
            run_text_marketing_tab(owner_df)
    else:
        st.error("No owner data available.")

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    run_minimal_app()
