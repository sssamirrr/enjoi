# owner_marketing.py

import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2 import service_account
import time
from urllib.parse import quote  # For URL encoding

# Import the callhistory module (Ensure it's in your PYTHONPATH or same directory)
import callhistory

# ... [Rest of your code above remains the same] ...

# Inside the run_owner_marketing_tab function, update the Communication Updates section:

# Communication Updates
if st.button("Update Communication Info", key="update_button"):
    selected_rows = edited_df[edited_df['Select']].index.tolist()
    if not selected_rows:
        st.warning("No rows selected!")
    else:
        with st.spinner("Fetching communication info..."):
            for idx in selected_rows:
                phone_number = edited_df.at[idx, "Phone Number"]
                try:
                    comm_data = callhistory.get_communication_info(phone_number, HEADERS)
                    for key, value in comm_data.items():
                        # Update both DataFrames
                        edited_df.at[idx, key] = value
                        st.session_state.working_df.at[idx, key] = value
                except Exception as e:
                    st.warning(f"Error fetching communication info for {phone_number}: {e}")
                    continue  # Proceed to the next phone number if there's an error

        st.success("Communication info updated!")
        st.experimental_rerun()

# Similarly, update the display_call_history function:

def display_call_history(phone_number):
    st.title(f"Call History for {phone_number}")
    # Fetch and display call history data
    try:
        call_history_data = callhistory.get_call_history_data(phone_number, HEADERS)
        if not call_history_data.empty:
            st.dataframe(call_history_data, use_container_width=True)
        else:
            st.warning("No call history available for this number.")
    except Exception as e:
        st.warning(f"Error fetching call history for {phone_number}: {e}")
