import streamlit as st
import pandas as pd
import math
import time
import requests
from datetime import datetime
from google.oauth2 import service_account

############################################
# Helper Functions
############################################

def cleanup_phone_number(phone):
    """Clean up phone number format"""
    if pd.isna(phone):
        return 'No Data'
    # Remove spaces and non-numeric characters
    phone = ''.join(filter(str.isdigit, str(phone)))
    if len(phone) == 10:
        return f"+1{phone}"
    elif len(phone) == 11 and phone.startswith('1'):
        return f"+{phone}"
    return 'No Data'

def truncate_text(text, max_length=30):
    """Truncate text to a maximum length with ellipsis"""
    if isinstance(text, str) and len(text) > max_length:
        return text[:max_length] + "..."
    return text

def reset_filters(selected_resort, min_check_in, max_check_out, total_price_min, total_price_max):
    """
    Reset filter-related session state variables based on the provided resort and date range.
    """
    try:
        st.session_state['reset_trigger'] = True
        st.session_state[f'default_check_in_start_{selected_resort}'] = min_check_in
        st.session_state[f'default_check_in_end_{selected_resort}'] = max_check_out
        st.session_state[f'default_check_out_start_{selected_resort}'] = min_check_in
        st.session_state[f'default_check_out_end_{selected_resort}'] = max_check_out
        st.session_state[f'default_total_price_{selected_resort}'] = (
            float(total_price_min), 
            float(total_price_max)
        )
        st.session_state[f'default_rate_code_{selected_resort}'] = "All"
    except Exception as e:
        st.error(f"Error resetting filters: {e}")

def rate_limited_request(url, headers, params, request_type='get'):
    """
    Make an API request while respecting rate limits.
    """
    time.sleep(1 / 5)  # 5 requests per second max
    try:
        response = (
            requests.get(url, headers=headers, params=params)
            if request_type == 'get'
            else None
        )
        if response and response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error: {response.status_code}")
            st.warning(f"Response: {response.text}")
    except Exception as e:
        st.warning(f"Exception during request: {str(e)}")
    return None

def get_all_phone_number_ids(headers):
    """
    Retrieve all phoneNumberIds associated with your OpenPhone account.
    """
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    response_data = rate_limited_request(phone_numbers_url, headers, {})
    return [pn.get('id') for pn in response_data.get('data', [])] if response_data else []

def get_communication_info(phone_number, headers, arrival_date):
    """
    Fetch messages/calls data for a given phone number and categorize them as 
    pre-arrival or post-arrival based on arrival_date.
    """
    phone_number_ids = get_all_phone_number_ids(headers)
    if not phone_number_ids:
        return {
            'status': "No Communications",
            'last_date': None,
            'call_duration': None,
            'agent_name': None,
            'total_messages': 0,
            'total_calls': 0,
            'answered_calls': 0,
            'missed_calls': 0,
            'call_attempts': 0,
            'pre_arrival_calls': 0,
            'pre_arrival_texts': 0,
            'post_arrival_calls': 0,
            'post_arrival_texts': 0,
            'calls_under_40sec': 0
        }

    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    latest_datetime = None
    latest_type = None
    latest_direction = None
    call_duration = None
    agent_name = None

    total_messages = 0
    total_calls = 0
    answered_calls = 0
    missed_calls = 0
    call_attempts = 0

    pre_arrival_calls = 0
    pre_arrival_texts = 0
    post_arrival_calls = 0
    post_arrival_texts = 0
    calls_under_40sec = 0

    # Ensure arrival_date is a datetime object
    if isinstance(arrival_date, str):
        arrival_date = datetime.fromisoformat(arrival_date)
    elif isinstance(arrival_date, pd.Timestamp):
        arrival_date = arrival_date.to_pydatetime()
    arrival_date_only = arrival_date.date()

    for phone_number_id in phone_number_ids:
        # Messages pagination
        next_page = None
        while True:
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [phone_number],
                "maxResults": 50
            }
            if next_page:
                params['pageToken'] = next_page

            # Fetch messages
            messages_response = rate_limited_request(messages_url, headers, params)
            if messages_response and 'data' in messages_response:
                messages = messages_response['data']
                total_messages += len(messages)
                for message in messages:
                    msg_time = datetime.fromisoformat(
                        message['createdAt'].replace('Z', '+00:00')
                    )
                    msg_date = msg_time.date()
                    if msg_date <= arrival_date_only:
                        pre_arrival_texts += 1
                    else:
                        post_arrival_texts += 1

                    if not latest_datetime or msg_time > latest_datetime:
                        latest_datetime = msg_time
                        latest_type = "Message"
                        latest_direction = message.get("direction", "unknown")
                        agent_name = message.get("user", {}).get("name", "Unknown Agent")

                next_page = messages_response.get('nextPageToken')
                if not next_page:
                    break
            else:
                break

        # Calls pagination
        next_page = None
        while True:
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [phone_number],
                "maxResults": 50
            }
            if next_page:
                params['pageToken'] = next_page

            # Fetch calls
            calls_response = rate_limited_request(calls_url, headers, params)
            if calls_response and 'data' in calls_response:
                calls = calls_response['data']
                total_calls += len(calls)
                for call in calls:
                    call_time = datetime.fromisoformat(
                        call['createdAt'].replace('Z', '+00:00')
                    )
                    call_date = call_time.date()
                    duration = call.get("duration", 0)

                    if call_date <= arrival_date_only:
                        pre_arrival_calls += 1
                    else:
                        post_arrival_calls += 1

                    if duration < 40:
                        calls_under_40sec += 1

                    if not latest_datetime or call_time > latest_datetime:
                        latest_datetime = call_time
                        latest_type = "Call"
                        latest_direction = call.get("direction", "unknown")
                        call_duration = duration
                        agent_name = call.get("user", {}).get("name", "Unknown Agent")

                    call_attempts += 1

                    call_status = call.get('status', 'unknown')
                    if call_status == 'completed':
                        answered_calls += 1
                    elif call_status in ['missed', 'no-answer', 'busy', 'failed']:
                        missed_calls += 1

                next_page = calls_response.get('nextPageToken')
                if not next_page:
                    break
            else:
                break

    if not latest_datetime:
        status = "No Communications"
    else:
        status = f"{latest_type} - {latest_direction}"

    return {
        'status': status,
        'last_date': (
            latest_datetime.strftime("%Y-%m-%d %H:%M:%S")
            if latest_datetime else None
        ),
        'call_duration': call_duration,
        'agent_name': agent_name,
        'total_messages': total_messages,
        'total_calls': total_calls,
        'answered_calls': answered_calls,
        'missed_calls': missed_calls,
        'call_attempts': call_attempts,
        'pre_arrival_calls': pre_arrival_calls,
        'pre_arrival_texts': pre_arrival_texts,
        'post_arrival_calls': post_arrival_calls,
        'post_arrival_texts': post_arrival_texts,
        'calls_under_40sec': calls_under_40sec
    }

def fetch_communication_info(guest_df, headers):
    """
    Loops over the guest DataFrame (with columns 'Phone Number' and 'Check In') 
    and fetches communication info for each guest.
    """
    statuses, dates, durations, agent_names = [], [], [], []
    total_messages_list, total_calls_list = [], []
    answered_calls_list, missed_calls_list, call_attempts_list = [], [], []
    pre_arrival_calls_list, pre_arrival_texts_list = [], []
    post_arrival_calls_list, post_arrival_texts_list = [], []
    calls_under_40sec_list = []

    for _, row in guest_df.iterrows():
        phone = row['Phone Number']
        arrival_date = row['Check In']  # Use 'Check In'
        if phone and phone != 'No Data':
            try:
                comm_info = get_communication_info(phone, headers, arrival_date)
                statuses.append(comm_info['status'])
                dates.append(comm_info['last_date'])
                durations.append(comm_info['call_duration'])
                agent_names.append(comm_info['agent_name'])
                total_messages_list.append(comm_info['total_messages'])
                total_calls_list.append(comm_info['total_calls'])
                answered_calls_list.append(comm_info['answered_calls'])
                missed_calls_list.append(comm_info['missed_calls'])
                call_attempts_list.append(comm_info['call_attempts'])
                pre_arrival_calls_list.append(comm_info['pre_arrival_calls'])
                pre_arrival_texts_list.append(comm_info['pre_arrival_texts'])
                post_arrival_calls_list.append(comm_info['post_arrival_calls'])
                post_arrival_texts_list.append(comm_info['post_arrival_texts'])
                calls_under_40sec_list.append(comm_info['calls_under_40sec'])
            except Exception:
                # In case of an unexpected error
                statuses.append("Error")
                dates.append(None)
                durations.append(None)
                agent_names.append("Unknown")
                total_messages_list.append(0)
                total_calls_list.append(0)
                answered_calls_list.append(0)
                missed_calls_list.append(0)
                call_attempts_list.append(0)
                pre_arrival_calls_list.append(0)
                pre_arrival_texts_list.append(0)
                post_arrival_calls_list.append(0)
                post_arrival_texts_list.append(0)
                calls_under_40sec_list.append(0)
        else:
            # Invalid or missing phone
            statuses.append("Invalid Number")
            dates.append(None)
            durations.append(None)
            agent_names.append("Unknown")
            total_messages_list.append(0)
            total_calls_list.append(0)
            answered_calls_list.append(0)
            missed_calls_list.append(0)
            call_attempts_list.append(0)
            pre_arrival_calls_list.append(0)
            pre_arrival_texts_list.append(0)
            post_arrival_calls_list.append(0)
            post_arrival_texts_list.append(0)
            calls_under_40sec_list.append(0)

    return (
        statuses, dates, durations, agent_names,
        total_messages_list, total_calls_list, answered_calls_list,
        missed_calls_list, call_attempts_list,
        pre_arrival_calls_list, pre_arrival_texts_list,
        post_arrival_calls_list, post_arrival_texts_list,
        calls_under_40sec_list
    )

############################################
# MARKETING TAB Main Function
############################################

def show_marketing_tab(df, OPENPHONE_API_KEY, OPENPHONE_NUMBER):
    """
    Displays the Marketing tab for a Streamlit application.
    Expects a DataFrame 'df' containing reservation data with columns like:
      'Market', 'Arrival Date Short', 'Departure Date Short', 'Rate Code Name', 'Total Price'
    """
    st.title("💼 Marketing Information by Resort")

    # Resort selection
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique())
    )

    # Filter for selected resort
    resort_df = df[df['Market'] == selected_resort].copy()
    st.subheader(f"Guest Information for {selected_resort}")

    # Determine default date range
    if not resort_df.empty:
        arrival_dates = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
        departure_dates = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce')

        arrival_dates = arrival_dates.dropna()
        departure_dates = departure_dates.dropna()

        min_check_in = arrival_dates.min().date() if not arrival_dates.empty else pd.to_datetime('today').date()
        max_check_out = departure_dates.max().date() if not departure_dates.empty else pd.to_datetime('today').date()
    else:
        today = pd.to_datetime('today').date()
        min_check_in = today
        max_check_out = today

    # Date filters
    col1, col2, col3 = st.columns([0.3, 0.3, 0.4])
    with col1:
        check_in_start = st.date_input(
            "Check In Date (Start)",
            value=min_check_in,
            key=f'check_in_start_input_{selected_resort}'
        )
        check_in_end = st.date_input(
            "Check In Date (End)",
            value=max_check_out,
            key=f'check_in_end_input_{selected_resort}'
        )

    with col2:
        check_out_start = st.date_input(
            "Check Out Date (Start)",
            value=min_check_in,
            key=f'check_out_start_input_{selected_resort}'
        )
        check_out_end = st.date_input(
            "Check Out Date (End)",
            value=max_check_out,
            key=f'check_out_end_input_{selected_resort}'
        )

    with col3:
        # Slider for Total Price
        if 'Total Price' in resort_df.columns and not resort_df['Total Price'].isnull().all():
            total_price_min = resort_df['Total Price'].min()
            total_price_max = resort_df['Total Price'].max()

            # Handle single-value range by adding a buffer
            if total_price_min == total_price_max:
                total_price_min = total_price_min - 1
                total_price_max = total_price_max + 1

            total_price_range = st.slider(
                "Total Price Range",
                min_value=float(total_price_min),
                max_value=float(total_price_max),
                value=(float(total_price_min), float(total_price_max)),
                key=f'total_price_slider_{selected_resort}'
            )
        else:
            st.warning("No valid Total Price data available for filtering.")
            total_price_range = (0, 0)

        # Dropdown for Rate Code
        rate_code_options = (
            sorted(resort_df['Rate Code Name'].dropna().unique())
            if 'Rate Code Name' in resort_df.columns
            else []
        )
        selected_rate_code = st.selectbox(
            "Select Rate Code",
            options=["All"] + rate_code_options,
            key=f'rate_code_filter_{selected_resort}'
        )

    # Reset Filters Button
    if st.button("Reset Filters"):
        reset_filters(selected_resort, min_check_in, max_check_out, total_price_min, total_price_max)

    # Apply filters
    if not resort_df.empty:
        resort_df['Arrival Date Short'] = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
        resort_df['Departure Date Short'] = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce')

        filtered_df = resort_df[
            (resort_df['Arrival Date Short'].dt.date >= check_in_start) &
            (resort_df['Arrival Date Short'].dt.date <= check_in_end) &
            (resort_df['Departure Date Short'].dt.date >= check_out_start) &
            (resort_df['Departure Date Short'].dt.date <= check_out_end)
        ]

        # Apply Total Price filter
        if 'Total Price' in filtered_df.columns:
            filtered_df = filtered_df[
                (filtered_df['Total Price'] >= total_price_range[0]) &
                (filtered_df['Total Price'] <= total_price_range[1])
            ]

        # Apply Rate Code filter
        if (selected_rate_code != "All") and ('Rate Code Name' in filtered_df.columns):
            filtered_df = filtered_df[filtered_df['Rate Code Name'] == selected_rate_code]

        # Remove duplicate rows based on 'Phone Number'
        display_df = filtered_df.drop_duplicates(subset=['Phone Number']).reset_index(drop=True)

        if not display_df.empty:
            # Rename columns for readability
            display_df = display_df.rename(columns={
                'Name': 'Guest Name',
                'Arrival Date Short': 'Check In',
                'Departure Date Short': 'Check Out',
                'Rate Code Name': 'Rate Code',
                'Total Price': 'Price'
            })

            # Ensure required columns
            for col in [
                'Guest Name', 'Check In', 'Check Out', 'Phone Number', 'Rate Code',
                'Price', 'Communication Status', 'Last Communication Date',
                'Call Duration (seconds)', 'Agent Name', 'Total Messages', 
                'Total Calls', 'Answered Calls', 'Missed Calls', 'Call Attempts',
                'Pre-Arrival Calls', 'Pre-Arrival Texts', 'Post-Arrival Calls',
                'Post-Arrival Texts', 'Calls Under 40 sec'
            ]:
                if col not in display_df.columns:
                    display_df[col] = None

            # Format phone numbers
            display_df['Phone Number'] = display_df['Phone Number'].apply(cleanup_phone_number)

            # Truncate long text fields
            display_df['Guest Name'] = display_df['Guest Name'].apply(
                lambda x: truncate_text(x, max_length=30)
            )
            display_df['Agent Name'] = display_df['Agent Name'].apply(
                lambda x: truncate_text(x, max_length=30)
            )

            # Select All checkbox
            select_all = st.checkbox("Select All Guests", key=f'select_all_{selected_resort}')
            display_df['Select'] = select_all

            # Initialize session state for communication data
            if 'communication_data' not in st.session_state:
                st.session_state['communication_data'] = {}
            if selected_resort not in st.session_state['communication_data']:
                st.session_state['communication_data'][selected_resort] = {}

            # Retrieve existing Communication Data from session state
            for idx, row in display_df.iterrows():
                phone = row['Phone Number']
                if phone in st.session_state['communication_data'][selected_resort]:
                    comm_data = st.session_state['communication_data'][selected_resort][phone]
                    display_df.at[idx, 'Communication Status'] = comm_data.get('status', 'Not Checked')
                    display_df.at[idx, 'Last Communication Date'] = comm_data.get('date', None)
                    display_df.at[idx, 'Call Duration (seconds)'] = comm_data.get('duration', None)
                    display_df.at[idx, 'Agent Name'] = comm_data.get('agent', 'Unknown')
                    display_df.at[idx, 'Total Messages'] = comm_data.get('total_messages', 0)
                    display_df.at[idx, 'Total Calls'] = comm_data.get('total_calls', 0)
                    display_df.at[idx, 'Answered Calls'] = comm_data.get('answered_calls', 0)
                    display_df.at[idx, 'Missed Calls'] = comm_data.get('missed_calls', 0)
                    display_df.at[idx, 'Call Attempts'] = comm_data.get('call_attempts', 0)
                    display_df.at[idx, 'Pre-Arrival Calls'] = comm_data.get('pre_arrival_calls', 0)
                    display_df.at[idx, 'Pre-Arrival Texts'] = comm_data.get('pre_arrival_texts', 0)
                    display_df.at[idx, 'Post-Arrival Calls'] = comm_data.get('post_arrival_calls', 0)
                    display_df.at[idx, 'Post-Arrival Texts'] = comm_data.get('post_arrival_texts', 0)
                    display_df.at[idx, 'Calls Under 40 sec'] = comm_data.get('calls_under_40sec', 0)

            # Fetch Communication Info Button
            if st.button("Fetch Communication Info", key=f'fetch_info_{selected_resort}'):
                headers = {
                    "Authorization": OPENPHONE_API_KEY,
                    "Content-Type": "application/json"
                }
                with st.spinner('Fetching communication information...'):
                    (
                        statuses, dates, durations, agent_names,
                        total_messages_list, total_calls_list,
                        answered_calls_list, missed_calls_list,
                        call_attempts_list,
                        pre_arrival_calls_list, pre_arrival_texts_list,
                        post_arrival_calls_list, post_arrival_texts_list,
                        calls_under_40sec_list
                    ) = fetch_communication_info(display_df, headers)

                    # Update display_df in bulk
                    display_df['Communication Status'] = statuses
                    display_df['Last Communication Date'] = dates
                    display_df['Call Duration (seconds)'] = durations
                    display_df['Agent Name'] = agent_names
                    display_df['Total Messages'] = total_messages_list
                    display_df['Total Calls'] = total_calls_list
                    display_df['Answered Calls'] = answered_calls_list
                    display_df['Missed Calls'] = missed_calls_list
                    display_df['Call Attempts'] = call_attempts_list
                    display_df['Pre-Arrival Calls'] = pre_arrival_calls_list
                    display_df['Pre-Arrival Texts'] = pre_arrival_texts_list
                    display_df['Post-Arrival Calls'] = post_arrival_calls_list
                    display_df['Post-Arrival Texts'] = post_arrival_texts_list
                    display_df['Calls Under 40 sec'] = calls_under_40sec_list

                    # Update session state
                    st.session_state['communication_data'][selected_resort] = {
                        phone: {
                            'status': status,
                            'date': date,
                            'duration': duration,
                            'agent': agent,
                            'total_messages': total_msgs,
                            'total_calls': total_cls,
                            'answered_calls': answered_cls,
                            'missed_calls': missed_cls,
                            'call_attempts': call_atpts,
                            'pre_arrival_calls': pre_calls,
                            'pre_arrival_texts': pre_texts,
                            'post_arrival_calls': post_calls,
                            'post_arrival_texts': post_texts,
                            'calls_under_40sec': under_40sec
                        }
                        for phone, status, date, duration, agent, total_msgs, total_cls,
                            answered_cls, missed_cls, call_atpts, pre_calls, pre_texts,
                            post_calls, post_texts, under_40sec
                        in zip(
                            display_df['Phone Number'], statuses, dates, durations, agent_names,
                            total_messages_list, total_calls_list, answered_calls_list,
                            missed_calls_list, call_attempts_list, pre_arrival_calls_list,
                            pre_arrival_texts_list, post_arrival_calls_list,
                            post_arrival_texts_list, calls_under_40sec_list
                        )
                    }
                    st.success("Communication information successfully fetched and updated.")

            # Reorder columns
            display_df = display_df[
                [
                    'Select', 'Guest Name', 'Check In', 'Check Out', 'Phone Number',
                    'Rate Code', 'Price', 'Communication Status', 'Last Communication Date',
                    'Call Duration (seconds)', 'Agent Name', 'Total Messages', 'Total Calls',
                    'Answered Calls', 'Missed Calls', 'Call Attempts', 'Pre-Arrival Calls',
                    'Pre-Arrival Texts', 'Post-Arrival Calls', 'Post-Arrival Texts',
                    'Calls Under 40 sec'
                ]
            ]

            # Data editor
            edited_df = st.data_editor(
                display_df,
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Select",
                        help="Select or deselect this guest",
                        default=False,
                        width="60px"
                    ),
                    "Guest Name": st.column_config.TextColumn(
                        "Guest Name",
                        width="200px"
                    ),
                    "Check In": st.column_config.DateColumn(
                        "Check In",
                        width="120px"
                    ),
                    "Check Out": st.column_config.DateColumn(
                        "Check Out",
                        width="120px"
                    ),
                    "Phone Number": st.column_config.TextColumn(
                        "Phone Number",
                        width="150px"
                    ),
                    "Rate Code": st.column_config.TextColumn(
                        "Rate Code",
                        width="100px"
                    ),
                    "Price": st.column_config.NumberColumn(
                        "Price",
                        format="$%.2f",
                        width="100px"
                    ),
                    "Communication Status": st.column_config.TextColumn(
                        "Communication Status",
                        disabled=True,
                        width="150px"
                    ),
                    "Last Communication Date": st.column_config.TextColumn(
                        "Last Communication Date",
                        disabled=True,
                        width="180px"
                    ),
                    "Call Duration (seconds)": st.column_config.NumberColumn(
                        "Call Duration (seconds)",
                        format="%d",
                        disabled=True,
                        width="150px"
                    ),
                    "Agent Name": st.column_config.TextColumn(
                        "Agent Name",
                        disabled=True,
                        width="150px"
                    ),
                    "Total Messages": st.column_config.NumberColumn(
                        "Total Messages",
                        format="%d",
                        disabled=True,
                        width="120px"
                    ),
                    "Total Calls": st.column_config.NumberColumn(
                        "Total Calls",
                        format="%d",
                        disabled=True,
                        width="100px"
                    ),
                    "Answered Calls": st.column_config.NumberColumn(
                        "Answered Calls",
                        format="%d",
                        disabled=True,
                        width="120px"
                    ),
                    "Missed Calls": st.column_config.NumberColumn(
                        "Missed Calls",
                        format="%d",
                        disabled=True,
                        width="120px"
                    ),
                    "Call Attempts": st.column_config.NumberColumn(
                        "Call Attempts",
                        format="%d",
                        disabled=True,
                        width="120px"
                    ),
                    "Pre-Arrival Calls": st.column_config.NumberColumn(
                        "Pre-Arrival Calls",
                        format="%d",
                        disabled=True,
                        width="140px"
                    ),
                    "Pre-Arrival Texts": st.column_config.NumberColumn(
                        "Pre-Arrival Texts",
                        format="%d",
                        disabled=True,
                        width="140px"
                    ),
                    "Post-Arrival Calls": st.column_config.NumberColumn(
                        "Post-Arrival Calls",
                        format="%d",
                        disabled=True,
                        width="140px"
                    ),
                    "Post-Arrival Texts": st.column_config.NumberColumn(
                        "Post-Arrival Texts",
                        format="%d",
                        disabled=True,
                        width="140px"
                    ),
                    "Calls Under 40 sec": st.column_config.NumberColumn(
                        "Calls Under 40 sec",
                        format="%d",
                        disabled=True,
                        width="140px"
                    ),
                },
                hide_index=True,
                use_container_width=True,
                key=f"guest_editor_{selected_resort}"
            )

            # Ensure 'Select' column is boolean
            if 'Select' in edited_df.columns:
                edited_df['Select'] = edited_df['Select'].map({
                    True: True, False: False, 'True': True, 'False': False
                })
                edited_df['Select'] = edited_df['Select'].fillna(False)
                edited_df['Select'] = edited_df['Select'].astype(bool)
                selected_guests = edited_df[edited_df['Select']]
            else:
                st.error("The 'Select' column is missing from the edited data.")
                selected_guests = pd.DataFrame()

            st.write("Display DataFrame after editing:")
            st.dataframe(edited_df.head())

            # Message Templates
            st.markdown("---")
            st.subheader("Message Templates")

            message_templates = {
                "Welcome Message": f"Welcome to {selected_resort}! Please visit our concierge desk for your welcome gift! 🎁",
                "Check-in Follow-up": f"Hello, we hope you're enjoying your stay at {selected_resort}. Don't forget to collect your welcome gift at the concierge desk! 🎁",
                "Checkout Message": f"Thank you for staying with us at {selected_resort}! We hope you had a great stay. Please stop by the concierge desk before you leave for a special gift! 🎁"
            }

            selected_template = st.selectbox(
                "Choose a Message Template",
                options=list(message_templates.keys())
            )

            message_preview = message_templates[selected_template]
            st.text_area("Message Preview", value=message_preview, height=100, disabled=True)

            # Send SMS
            if not edited_df.empty:
                selected_guests = edited_df[edited_df['Select']]
                num_selected = len(selected_guests)
                if not selected_guests.empty:
                    button_label = f"Send SMS to {num_selected} Guest{'s' if num_selected != 1 else ''}"
                    if st.button(button_label):
                        openphone_url = "https://api.openphone.com/v1/messages"
                        headers_sms = {
                            "Authorization": OPENPHONE_API_KEY,
                            "Content-Type": "application/json"
                        }
                        sender_phone_number = OPENPHONE_NUMBER

                        for idx, row in selected_guests.iterrows():
                            recipient_phone = row['Phone Number']
                            payload = {
                                "content": message_preview,
                                "from": sender_phone_number,
                                "to": [recipient_phone]
                            }
                            try:
                                response = requests.post(
                                    openphone_url, 
                                    json=payload, 
                                    headers=headers_sms
                                )
                                if response.status_code == 202:
                                    st.success(
                                        f"Message sent to {row['Guest Name']} ({recipient_phone})"
                                    )
                                else:
                                    st.error(
                                        f"Failed to send message to {row['Guest Name']} ({recipient_phone})"
                                    )
                                    st.write("Response Status Code:", response.status_code)
                                    try:
                                        st.write("Response Body:", response.json())
                                    except:
                                        st.write("Response Body:", response.text)
                            except Exception as e:
                                st.error(
                                    f"Exception while sending message to {row['Guest Name']} ({recipient_phone}): {str(e)}"
                                )
                            time.sleep(0.2)  # Respect rate limits
                else:
                    st.info("No guests selected to send SMS.")
            else:
                st.info("No guest data available to send SMS.")
        else:
            st.warning("No data available for the selected filters.")
    else:
        st.warning("No data for this resort.")
