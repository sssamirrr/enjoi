# ownermarketing.py

import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import time
from urllib.parse import quote  # For URL encoding

# Import the callhistory module
import callhistory

# Securely load your OpenPhone API Key and other secrets
OPENPHONE_API_KEY = st.secrets["openphone_api"]["api_key"]
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

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
        df['Call History'] = ""  # Initialize with empty strings

        df['Select'] = False  # Selection column
        df = df[['Select'] + [col for col in df.columns if col != 'Select']]  # Move Select to first column
        return df

    except Exception as e:
        st.error(f"Error accessing Google Sheet: {e}")
        return pd.DataFrame()

# Main App Function
def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing Dashboard")

    # Initialize session state
    if 'working_df' not in st.session_state:
        st.session_state.working_df = owner_df.copy()
    else:
        # Ensure working_df has the latest data
        st.session_state.working_df.update(owner_df)

    # Filters
    st.subheader("Filters")
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_states = st.multiselect("Select States", st.session_state.working_df['State'].dropna().unique())
    with col2:
        sale_date_min = st.session_state.working_df['Sale Date'].min()
        sale_date_max = st.session_state.working_df['Sale Date'].max()
        date_range = st.date_input("Sale Date Range",
                                   [sale_date_min, sale_date_max],
                                   min_value=sale_date_min,
                                   max_value=sale_date_max)
    with col3:
        fico_min = int(st.session_state.working_df['Primary FICO'].min())
        fico_max = int(st.session_state.working_df['Primary FICO'].max())
        fico_range = st.slider("FICO Score", fico_min, fico_max, (fico_min, fico_max))

    # Apply Filters
    filtered_df = st.session_state.working_df.copy()
    if selected_states:
        filtered_df = filtered_df[filtered_df['State'].isin(selected_states)]
    if date_range:
        filtered_df = filtered_df[(filtered_df['Sale Date'] >= pd.Timestamp(date_range[0])) &
                                  (filtered_df['Sale Date'] <= pd.Timestamp(date_range[1]))]
    filtered_df = filtered_df[(filtered_df['Primary FICO'] >= fico_range[0]) &
                              (filtered_df['Primary FICO'] <= fico_range[1])]

    # Display Table
    st.subheader("Owner Data")

    # Configure columns for st.data_editor
    column_config = {
        "Select": st.column_config.CheckboxColumn("Select"),
        "Call History": st.column_config.LinkColumn(
            label="Call History",
            display_text="View Call History",
            help="Click to view call history for this number"
        )
    }

    # Ensure that 'Call History' column contains URLs (or empty strings)
    filtered_df['Call History'] = filtered_df['Call History'].fillna('')

    # Display the data editor
    edited_df = st.data_editor(
        filtered_df,
        column_config=column_config,
        use_container_width=True,
        key='data_editor'
    )

    # Communication Updates
    if st.button("Update Communication Info", key="update_button"):
        selected_rows = edited_df[edited_df['Select']].index.tolist()
        if not selected_rows:
            st.warning("No rows selected!")
        else:
            with st.spinner("Fetching communication info..."):
                for idx in selected_rows:
                    phone_number = edited_df.at[idx, "Phone Number"]
                    comm_data = callhistory.get_communication_info(phone_number, HEADERS)
                    for key, value in comm_data.items():
                        # Update both DataFrames
                        edited_df.at[idx, key] = value
                        st.session_state.working_df.at[idx, key] = value

            st.success("Communication info updated!")
            st.experimental_rerun()

def display_call_history(phone_number):
    st.title(f"Call History for {phone_number}")
    # Fetch and display call history data
    call_history_data = callhistory.get_call_history_data(phone_number, HEADERS)
    if not call_history_data.empty:
        st.dataframe(call_history_data, use_container_width=True)
    else:
        st.warning("No call history available for this number.")

def run_minimal_app():
    # Check if 'view' query parameter is 'call-history'
    query_params = st.experimental_get_query_params()
    view = query_params.get('view', [None])[0]
    phone_number = query_params.get('number', [None])[0]

    if view == 'call-history' and phone_number:
        display_call_history(phone_number)
    else:
        owner_df = get_owner_sheet_data()
        if not owner_df.empty:
            run_owner_marketing_tab(owner_df)
        else:
            st.error("No owner data available.")

if __name__ == "__main__":
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    run_minimal_app()
