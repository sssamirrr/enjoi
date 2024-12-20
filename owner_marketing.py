# owner_marketing.py

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
                if st.button("Send"):
                    for phone in phone_numbers:
                        # Add your text message sending logic here
                        pass
                    st.success("Messages sent!")

    with col3:
        if st.button("Make Call"):
            selected_rows = edited_df[edited_df['Select']].index.tolist()
            if not selected_rows:
                st.warning("No rows selected!")
            else:
                for idx in selected_rows:
                    phone_number = edited_df.at[idx, "Phone Number"]
                    # Add your call making logic here
                    pass

    with col4:
        if st.button("View Call History"):
            selected_rows = edited_df[edited_df['Select']].index.tolist()
            if not selected_rows:
                st.warning("No rows selected!")
            else:
                for idx in selected_rows:
                    phone_number = edited_df.at[idx, "Phone Number"]
                    display_call_history(phone_number)

    # Display the DataFrame with editable cells
    st.dataframe(
        edited_df,
        column_config={
            "Select": st.column_config.CheckboxColumn(
                "Select",
                help="Select rows for bulk actions",
                default=False,
            ),
            "Phone Number": st.column_config.TextColumn(
                "Phone Number",
                help="Contact phone number",
            ),
            "Last Contact": st.column_config.DateColumn(
                "Last Contact",
                help="Date of last contact",
            ),
            "Notes": st.column_config.TextColumn(
                "Notes",
                help="Additional notes",
                width="large",
            ),
        },
        hide_index=True,
        use_container_width=True,
        editable=True,
    )

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

# For the main app.py file, use:
# import owner_marketing
# owner_df = owner_marketing.get_owner_sheet_data()
# owner_marketing.run_owner_marketing_tab(owner_df=owner_df)
