import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import time
from urllib.parse import quote
import callhistory

def get_owner_sheet_data():
    """
    Retrieves the data from the Google Sheet and returns it as a Pandas DataFrame.
    """
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
        ],
    )
    client = gspread.authorize(credentials)
    sheet_key = st.secrets["owners_sheets"]["owners_sheet_key"]
    sheet = client.open_by_key(sheet_key)
    worksheet = sheet.sheet1
    data = worksheet.get_all_records()
    df = pd.DataFrame(data)
    return df

def display_call_history(phone_number):
    st.title(f"Call History for {phone_number}")
    try:
        call_history_data = callhistory.get_call_history_data(phone_number)
        if not call_history_data.empty:
            st.dataframe(call_history_data, use_container_width=True)
        else:
            st.warning("No call history available for this number.")
    except Exception as e:
        st.warning(f"Error fetching call history for {phone_number}: {e}")

def run_owner_marketing_tab(owner_df):
    st.title("Owner Marketing")
    
    # Initialize session state if not exists
    if 'working_df' not in st.session_state:
        st.session_state.working_df = owner_df.copy()
    
    # Create edited_df from working_df
    edited_df = st.session_state.working_df.copy()
    
    # Add a select column if it doesn't exist
    if 'Select' not in edited_df.columns:
        edited_df['Select'] = False

    # Create columns for the layout
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1])

    # Buttons in the first row
    with col1:
        if st.button("Update Communication Info"):
            selected_rows = edited_df[edited_df['Select']].index.tolist()
            if not selected_rows:
                st.warning("No rows selected!")
            else:
                with st.spinner("Fetching communication info..."):
                    for idx in selected_rows:
                        phone_number = edited_df.at[idx, "Phone Number"]
                        try:
                            comm_data = callhistory.get_communication_info(phone_number)
                            for key, value in comm_data.items():
                                edited_df.at[idx, key] = value
                                st.session_state.working_df.at[idx, key] = value
                        except Exception as e:
                            st.warning(f"Error fetching communication info for {phone_number}: {e}")
                            continue
                st.success("Communication info updated!")
                st.experimental_rerun()

    with col2:
        if st.button("Send Text Message"):
            selected_rows = edited_df[edited_df['Select']].index.tolist()
            if not selected_rows:
                st.warning("No rows selected!")
            else:
                phone_numbers = edited_df.loc[selected_rows, "Phone Number"].tolist()
                message = st.text_area("Enter your message:")
                if st.button("Send", key="send_text"):
                    st.success("Messages sent!")

    with col3:
        if st.button("Make Call"):
            selected_rows = edited_df[edited_df['Select']].index.tolist()
            if not selected_rows:
                st.warning("No rows selected!")
            else:
                for idx in selected_rows:
                    phone_number = edited_df.at[idx, "Phone Number"]
                    link = f"tel:{phone_number}"
                    st.markdown(f'<a href="{link}" target="_blank">Call {phone_number}</a>', unsafe_allow_html=True)

    with col4:
        if st.button("View Call History"):
            selected_rows = edited_df[edited_df['Select']].index.tolist()
            if not selected_rows:
                st.warning("No rows selected!")
            else:
                for idx in selected_rows:
                    phone_number = edited_df.at[idx, "Phone Number"]
                    display_call_history(phone_number)

    # Modified DataFrame display
    edited_df = st.data_editor(
        edited_df,
        column_config={
            "Select": "checkbox",
            "Phone Number": "text",
            "Last Contact": "date",
            "Notes": st.column_config.TextColumn(
                "Notes",
                width="large",
            ),
        },
        disabled=["Phone Number", "Last Contact"],  # Make certain columns read-only
        hide_index=True,
        use_container_width=True,
    )

    # Update the session state with any edits
    st.session_state.working_df = edited_df.copy()

    return edited_df

def initialize():
    st.set_page_config(page_title="Owner Marketing", layout="wide")
    
if __name__ == "__main__":
    initialize()
    owner_df = get_owner_sheet_data()
    run_owner_marketing_tab(owner_df)
