# owner_marketing.py

import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from datetime import datetime

@st.cache_resource
def get_owner_sheet_data():
    """
    Fetch owner data from Google Sheets.
    Returns a pandas DataFrame containing owner information.
    """
    try:
        # Retrieve Google Sheets credentials from st.secrets
        service_account_info = st.secrets["gcp_service_account"]
        
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ],
        )

        gc = gspread.authorize(credentials)
        # Replace with your owner data sheet key
        spreadsheet = gc.open_by_key(st.secrets["sheets"]["owner_sheet_key"])
        worksheet = spreadsheet.get_worksheet(0)  # Adjust worksheet index as needed
        data = worksheet.get_all_records()
        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Error connecting to Owner Google Sheet: {str(e)}")
        return pd.DataFrame()  # Return empty DataFrame on error

# Define helper functions within this module or import them from a shared utils.py
def cleanup_phone_number(phone):
    """Clean up phone number format"""
    if pd.isna(phone):
        return 'No Data'
    phone = ''.join(filter(str.isdigit, str(phone)))
    if len(phone) == 10:
        return f"+1{phone}"
    elif len(phone) == 11 and phone.startswith('1'):
        return f"+{phone}"
    return 'No Data'

def fetch_communication_info(guest_df, headers):
    """
    Retrieve communication info for all guests in the DataFrame.
    Returns lists of statuses, dates, durations, and agent names.
    """
    if 'Phone Number' not in guest_df.columns:
        st.error("The column 'Phone Number' is missing in the DataFrame.")
        return ["No Status"] * len(guest_df), [None] * len(guest_df), [None] * len(guest_df), ["Unknown"] * len(guest_df)

    guest_df['Phone Number'] = guest_df['Phone Number'].astype(str).str.strip()
    statuses, dates, durations, agent_names = [], [], [], []

    for _, row in guest_df.iterrows():
        phone = row['Phone Number']
        if phone and phone != 'No Data':
            try:
                # Implement your actual logic to fetch communication info
                status, last_date, duration, agent_name = get_last_communication_info(phone, headers)
                statuses.append(status)
                dates.append(last_date)
                durations.append(duration)
                agent_names.append(agent_name)
            except Exception as e:
                statuses.append("Error")
                dates.append(None)
                durations.append(None)
                agent_names.append("Unknown")
        else:
            statuses.append("Invalid Number")
            dates.append(None)
            durations.append(None)
            agent_names.append("Unknown")

    return statuses, dates, durations, agent_names

def get_last_communication_info(phone_number, headers):
    """
    Placeholder function to fetch the last communication info.
    Replace this with actual API interaction logic.
    """
    # Example placeholder logic
    # Replace this with your actual OpenPhone API calls
    status = "Message - sent"
    last_date = "2024-01-01 12:00:00"
    duration = None
    agent_name = "Agent Smith"
    return status, last_date, duration, agent_name

def run_owner_marketing_tab(owner_df):
    """
    Function to render the Owner Marketing tab.
    """
    st.header("🏠 Owner Marketing Dashboard")

    if owner_df.empty:
        st.warning("No owner data available.")
        st.stop()

    # Display the columns for debugging (optional)
    st.write("Owner Data Columns:", owner_df.columns.tolist())
    st.dataframe(owner_df.head())

    # Define date columns
    date_cols = ["Contract Start Date", "Contract End Date"]

    # Convert Contract Start/End to datetime if present
    for dcol in date_cols:
        if dcol in owner_df.columns:
            owner_df[dcol] = pd.to_datetime(owner_df[dcol], errors='coerce')

    # Convert Revenue to numeric if present
    if "Revenue" in owner_df.columns:
        # If revenue is stored in a format like "$123.00", remove $ and convert
        owner_df["Revenue"] = owner_df["Revenue"].replace({'\$':''}, regex=True)
        owner_df["Revenue"] = pd.to_numeric(owner_df["Revenue"], errors='coerce')

    # Cleanup phone numbers if present
    if "Phone Number" in owner_df.columns:
        owner_df["Phone Number"] = owner_df["Phone Number"].apply(cleanup_phone_number)
    else:
        owner_df["Phone Number"] = "No Data"

    # Sidebar filters
    st.sidebar.title("Owner Filters")

    filtered_owner_df = owner_df.copy()

    # Dynamically create filters
    for col in owner_df.columns:
        col_data = owner_df[col].dropna()
        if col_data.empty:
            continue
        col_type = owner_df[col].dtype

        # Date filters (for Contract Start/End)
        if col in date_cols:
            valid_dates = col_data.dropna()
            if not valid_dates.empty:
                min_date = valid_dates.min().date()
                max_date = valid_dates.max().date()
                date_range = st.sidebar.date_input(
                    f"{col} range",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date
                )
                if isinstance(date_range, tuple) and len(date_range) == 2:
                    start, end = date_range
                    filtered_owner_df = filtered_owner_df[
                        (filtered_owner_df[col].dt.date >= start) & 
                        (filtered_owner_df[col].dt.date <= end)
                    ]

        # Numeric filters (e.g., Revenue, Account ID if present)
        elif np.issubdtype(col_type, np.number):
            min_val, max_val = float(col_data.min()), float(col_data.max())
            if min_val == max_val:
                st.sidebar.write(f"All {col} = {min_val}")
            else:
                val_range = st.sidebar.slider(
                    f"{col} range",
                    min_value=min_val, max_value=max_val,
                    value=(min_val, max_val)
                )
                filtered_owner_df = filtered_owner_df[
                    (filtered_owner_df[col] >= val_range[0]) & 
                    (filtered_owner_df[col] <= val_range[1])
                ]

        else:
            # For text/categorical
            unique_vals = sorted(col_data.unique())
            if len(unique_vals) <= 20:
                # Multi-select filter
                selected_vals = st.sidebar.multiselect(
                    f"{col} filter", 
                    options=unique_vals, 
                    default=unique_vals
                )
                filtered_owner_df = filtered_owner_df[
                    filtered_owner_df[col].isin(selected_vals)
                ]
            else:
                # Text search
                text_filter = st.sidebar.text_input(f"Search in {col}")
                if text_filter:
                    filtered_owner_df = filtered_owner_df[
                        filtered_owner_df[col].astype(str).str.contains(text_filter, case=False, na=False)
                    ]

    # Prepare display DataFrame
    display_owner_df = filtered_owner_df.copy()

    # Ensure required columns for communication info
    required_owner_columns = [
        'Owner Name', 'Start Date', 'End Date', 'Phone Number', 'Rate Code', 'Revenue',
        'Communication Status', 'Last Communication Date', 'Call Duration (seconds)', 'Agent Name'
    ]
    for rc in required_owner_columns:
        if rc not in display_owner_df.columns:
            display_owner_df[rc] = None

    # Insert Select column at the start
    display_owner_df.insert(0, 'Select', False)

    # Initialize session state for communication data if not present
    if 'communication_data' not in st.session_state:
        st.session_state['communication_data'] = {}
    # Assuming 'selected_resort' is available; adjust accordingly
    selected_resort = "Owner Marketing"  # Or pass as a parameter if needed
    if selected_resort not in st.session_state['communication_data']:
        st.session_state['communication_data'][selected_resort] = {}

    # Load existing communication data if any
    for idx, row in display_owner_df.iterrows():
        phone = row['Phone Number']
        if phone in st.session_state['communication_data'][selected_resort]:
            comm_data = st.session_state['communication_data'][selected_resort][phone]
            display_owner_df.at[idx, 'Communication Status'] = comm_data.get('status', 'Not Checked')
            display_owner_df.at[idx, 'Last Communication Date'] = comm_data.get('date', None)
            display_owner_df.at[idx, 'Call Duration (seconds)'] = comm_data.get('duration', None)
            display_owner_df.at[idx, 'Agent Name'] = comm_data.get('agent', 'Unknown')

    # Fetch Communication Info Button
    if st.button("Fetch Communication Info", key=f'fetch_info_{selected_resort}'):
        headers = {
            "Authorization": st.secrets["openphone"]["api_key"],
            "Content-Type": "application/json"
        }
        with st.spinner('Fetching communication information...'):
            statuses, dates, durations, agent_names = fetch_communication_info(display_owner_df, headers)

            for phone, status, date, duration, agent in zip(
                display_owner_df['Phone Number'], statuses, dates, durations, agent_names
            ):
                st.session_state['communication_data'][selected_resort][phone] = {
                    'status': status,
                    'date': date,
                    'duration': duration,
                    'agent': agent
                }

                # Update display_df
                idx_list = display_owner_df.index[display_owner_df['Phone Number'] == phone].tolist()
                if idx_list:
                    idx = idx_list[0]
                    display_owner_df.at[idx, 'Communication Status'] = status
                    display_owner_df.at[idx, 'Last Communication Date'] = date
                    display_owner_df.at[idx, 'Call Duration (seconds)'] = duration
                    display_owner_df.at[idx, 'Agent Name'] = agent

        st.success("Communication info fetched.")

    # Reorder columns
    display_owner_df = display_owner_df[[
        'Select', 'Owner Name', 'Start Date', 'End Date', 
        'Phone Number', 'Rate Code', 'Revenue', 
        'Communication Status', 'Last Communication Date', 
        'Call Duration (seconds)', 'Agent Name'
    ]]

    # Display the interactive data editor
    edited_owner_df = st.data_editor(
        display_owner_df,
        column_config={
            "Select": st.column_config.CheckboxColumn("Select", help="Select or deselect this owner"),
            "Owner Name": st.column_config.TextColumn("Owner Name"),
            "Start Date": st.column_config.DateColumn("Start Date"),
            "End Date": st.column_config.DateColumn("End Date"),
            "Phone Number": st.column_config.TextColumn("Phone Number"),
            "Rate Code": st.column_config.TextColumn("Rate Code"),
            "Revenue": st.column_config.NumberColumn("Revenue", format="$%.2f"),
            "Communication Status": st.column_config.TextColumn("Communication Status", disabled=True),
            "Last Communication Date": st.column_config.TextColumn("Last Communication Date", disabled=True),
            "Call Duration (seconds)": st.column_config.NumberColumn("Call Duration (seconds)", disabled=True),
            "Agent Name": st.column_config.TextColumn("Agent Name", disabled=True)
        },
        hide_index=True,
        use_container_width=True,
        key=f"owner_editor_{selected_resort}"
    )

    ############################################
    # Message Templates for Owners
    ############################################
    st.markdown("---")
    st.subheader("Owner Message Templates")

    owner_message_templates = {
        "Welcome Owner": "Hello! Thank you for partnering with us. Please stop by our office for a special welcome gift! 🎁",
        "Revenue Update": "Hello, this is your updated revenue summary. Please contact us if you have any questions!",
        "Contract Renewal": "Your contract is approaching renewal. Let's discuss the best options moving forward!"
    }

    selected_owner_template = st.selectbox(
        "Choose an Owner Message Template",
        options=list(owner_message_templates.keys())
    )

    owner_message_preview = owner_message_templates[selected_owner_template]
    custom_message = st.text_area("Message Preview (You can edit)", value=owner_message_preview, height=100)

    ############################################
    # Send SMS to Selected Owners
    ############################################
    selected_owners = edited_owner_df[edited_owner_df['Select']]
    num_selected_owners = len(selected_owners)
    if num_selected_owners > 0:
        st.write(f"{num_selected_owners} owner(s) selected.")
        if st.button("Send SMS to Selected Owners"):
            openphone_url = "https://api.openphone.com/v1/messages"
            headers_sms = {
                "Authorization": st.secrets["openphone"]["api_key"],
                "Content-Type": "application/json"
            }
            sender_phone_number = st.secrets["openphone"]["phone_number"]

            for idx, row in selected_owners.iterrows():
                recipient_phone = row['Phone Number']
                payload = {
                    "content": custom_message,
                    "from": sender_phone_number,
                    "to": [recipient_phone]
                }

                try:
                    response = requests.post(openphone_url, json=payload, headers=headers_sms)
                    if response.status_code == 202:
                        st.success(f"Message sent to {row.get('Owner Name', 'Owner')} ({recipient_phone})")
                    else:
                        st.error(f"Failed to send message to {row.get('Owner Name', 'Owner')} ({recipient_phone})")
                        st.write("Response Status Code:", response.status_code)
                        try:
                            st.write("Response Body:", response.json())
                        except:
                            st.write("Response Body:", response.text)
                except Exception as e:
                    st.error(f"Exception while sending message to {row.get('Owner Name', 'Owner')} ({recipient_phone}): {str(e)}")

                time.sleep(0.2)  # Respect rate limits
    else:
        st.info("No owners selected to send SMS.")
