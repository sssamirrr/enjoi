import streamlit as st  # Import Streamlit first

# Set the page configuration as the first command
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

# Now import other modules
import openphone 
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2 import service_account
import math
import requests
import time
import owner_marketing  # Ensure this module is also free of Streamlit commands






def init_session_state():
    if 'default_dates' not in st.session_state:
        st.session_state['default_dates'] = {}
    if 'communication_data' not in st.session_state:
        st.session_state['communication_data'] = {}

# Call the initialization function
init_session_state()



# Add CSS for optional styling (can be customized or removed)
st.markdown("""
    <style>
    .stDateInput {
        width: 100%;
    }
    .stTextInput, .stNumberInput {
        max-width: 200px;
    }
    div[data-baseweb="input"] {
        width: 100%;
    }
    .stDateInput > div {
        width: 100%;
    }
    div[data-baseweb="input"] > div {
        width: 100%;
    }
    .stDataFrame {
        width: 100%;
    }
    .dataframe-container {
        margin-top: 1rem;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)
# Define all tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Dashboard", 
    "Marketing", 
    "Tour Prediction",
    "Owner Marketing",
    "Overnight Misses",
    "OpenPhone Stats"
])

############################################
# Hard-coded OpenPhone Credentials
############################################

# Replace with your actual OpenPhone API key and number
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
OPENPHONE_NUMBER = "+18438972426"

############################################
# Connect to Google Sheets
############################################

@st.cache_resource
def get_google_sheet_data():
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
        spreadsheet = gc.open_by_key(st.secrets["sheets"]["sheet_key"])
        worksheet = spreadsheet.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)

    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None

# Load the data
df = get_google_sheet_data()
if df is None:
    st.error("Failed to load data. Please check your connection and credentials.")
    st.stop()

############################################
# OpenPhone API Functions
############################################

import time
import requests
import streamlit as st
from datetime import datetime
import pandas as pd

def rate_limited_request(url, headers, params, request_type='get'):
    """
    Make an API request while respecting rate limits.
    """
    time.sleep(1 / 5)  # 5 requests per second max
    try:
        st.write(f"Making API call to {url} with params: {params}")
        start_time = time.time()
        response = requests.get(url, headers=headers, params=params) if request_type == 'get' else None
        elapsed_time = time.time() - start_time
        st.write(f"API call completed in {elapsed_time:.2f} seconds")

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

def get_communication_info(phone_number, headers):
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
            'call_attempts': 0
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
                    msg_time = datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00'))
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
                    call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00'))
                    if not latest_datetime or call_time > latest_datetime:
                        latest_datetime = call_time
                        latest_type = "Call"
                        latest_direction = call.get("direction", "unknown")
                        call_duration = call.get("duration")
                        agent_name = call.get("user", {}).get("name", "Unknown Agent")

                    call_attempts += 1

                    # Determine if the call was answered
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
        'last_date': latest_datetime.strftime("%Y-%m-%d %H:%M:%S") if latest_datetime else None,
        'call_duration': call_duration,
        'agent_name': agent_name,
        'total_messages': total_messages,
        'total_calls': total_calls,
        'answered_calls': answered_calls,
        'missed_calls': missed_calls,
        'call_attempts': call_attempts
    }


def fetch_communication_info(guest_df, headers):
    if 'Phone Number' not in guest_df.columns:
        num_rows = len(guest_df)
        return (
            ["No Status"] * num_rows,
            [None] * num_rows,
            [None] * num_rows,
            ["Unknown"] * num_rows,
            [0] * num_rows,  # total_messages
            [0] * num_rows,  # total_calls
            [0] * num_rows,  # answered_calls
            [0] * num_rows,  # missed_calls
            [0] * num_rows   # call_attempts
        )

    statuses, dates, durations, agent_names = [], [], [], []
    total_messages_list, total_calls_list = [], []
    answered_calls_list, missed_calls_list, call_attempts_list = [], [], []

    for _, row in guest_df.iterrows():
        phone = row['Phone Number']
        if phone and phone != 'No Data':
            try:
                comm_info = get_communication_info(phone, headers)
                statuses.append(comm_info['status'])
                dates.append(comm_info['last_date'])
                durations.append(comm_info['call_duration'])
                agent_names.append(comm_info['agent_name'])
                total_messages_list.append(comm_info['total_messages'])
                total_calls_list.append(comm_info['total_calls'])
                answered_calls_list.append(comm_info['answered_calls'])
                missed_calls_list.append(comm_info['missed_calls'])
                call_attempts_list.append(comm_info['call_attempts'])
            except Exception as e:
                statuses.append("Error")
                dates.append(None)
                durations.append(None)
                agent_names.append("Unknown")
                total_messages_list.append(0)
                total_calls_list.append(0)
                answered_calls_list.append(0)
                missed_calls_list.append(0)
                call_attempts_list.append(0)
        else:
            statuses.append("Invalid Number")
            dates.append(None)
            durations.append(None)
            agent_names.append("Unknown")
            total_messages_list.append(0)
            total_calls_list.append(0)
            answered_calls_list.append(0)
            missed_calls_list.append(0)
            call_attempts_list.append(0)

    # Return the collected data
    return (
        statuses, dates, durations, agent_names,
        total_messages_list, total_calls_list,
        answered_calls_list, missed_calls_list,
        call_attempts_list
    )


    # Output results for debugging
    st.write("Statuses:", statuses)
    st.write("Dates:", dates)
    return statuses, dates


with tab4:
    st.header("Owner Marketing")
    # Placeholder for Owner Marketing functionality
    st.info("Owner Marketing functionality coming soon...")
    
    # You can add some basic structure for future development
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Owner Statistics")
        # Placeholder for owner stats
        
    with col2:
        st.subheader("Marketing Campaigns")
        # Placeholder for marketing campaigns

with tab5:
    st.header("Overnight Misses")
    # Placeholder for Overnight Misses functionality
    st.info("Overnight Misses functionality coming soon...")
    
    # You can add some basic structure for future development
    st.subheader("Missed Opportunities")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Misses", "---")
    with col2:
        st.metric("Revenue Impact", "$---")
    with col3:
        st.metric("Recovery Rate", "---")

############################################
# Dashboard Tab
############################################
with tab1:
    st.title("🏨 Hotel Reservations Dashboard")
    st.markdown("Real-time analysis of hotel reservations")

    # Filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        selected_hotel = st.multiselect(
            "Select Hotel",
            options=sorted(df['Market'].unique()),
            default=[]
        )

    with col2:
        min_date = pd.to_datetime(df['Arrival Date Short']).min()
        max_date = pd.to_datetime(df['Arrival Date Short']).max()
        date_range = st.date_input(
            "Select Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )

    with col3:
        # New code
        if 'Rate Code Name' not in df.columns:
            st.error("The 'Rate Code Name' column is missing.")
            st.stop()
        elif df['Rate Code Name'].isnull().all():
            st.warning("The 'Rate Code Name' column has no valid data.")
            options = []
        else:
            # Convert to strings and handle nulls
            df['Rate Code Name'] = df['Rate Code Name'].astype(str)
            df['Rate Code Name'] = df['Rate Code Name'].replace('nan', None).fillna('Unknown')
            options = sorted(df['Rate Code Name'].unique())
        
        selected_rate_codes = st.multiselect(
            "Select Rate Codes",
            options=options,
            default=[]
        )

    # Filter data
    filtered_df = df.copy()
    
    if selected_hotel:
        filtered_df = filtered_df[filtered_df['Market'].isin(selected_hotel)]
    
    if isinstance(date_range, tuple) and len(date_range) == 2:
        filtered_df = filtered_df[
            (pd.to_datetime(filtered_df['Arrival Date Short']).dt.date >= date_range[0]) &
            (pd.to_datetime(filtered_df['Arrival Date Short']).dt.date <= date_range[1])
        ]
    
    if selected_rate_codes:
        filtered_df = filtered_df[filtered_df['Rate Code Name'].isin(selected_rate_codes)]

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Reservations", len(filtered_df))
    with col2:
        average_nights = filtered_df['# Nights'].mean()
        st.metric("Average Nights", f"{average_nights:.1f}" if not math.isnan(average_nights) else "0")
    with col3:
        total_room_nights = filtered_df['# Nights'].sum()
        st.metric("Total Room Nights", f"{total_room_nights:,.0f}")
    with col4:
        unique_guests = filtered_df['Name'].nunique()
        st.metric("Unique Guests", unique_guests)

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        # Reservations by Hotel using groupby
        reservations_by_hotel = filtered_df.groupby('Market').size().reset_index(name='Reservations')
        reservations_by_hotel = reservations_by_hotel.rename(columns={'Market': 'Hotel'})
        
        # Conditional Plotting
        if reservations_by_hotel.empty:
            st.warning("No reservation data available for the selected filters.")
        else:
            fig_hotels = px.bar(
                reservations_by_hotel,
                x='Hotel',
                y='Reservations',
                labels={'Hotel': 'Hotel', 'Reservations': 'Reservations'},
                title='Reservations by Hotel'
            )
            st.plotly_chart(fig_hotels, use_container_width=True)

    with col2:
        # Length of Stay Distribution
        fig_los = px.histogram(
            filtered_df,
            x='# Nights',
            title='Length of Stay Distribution'
        )
        st.plotly_chart(fig_los, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        # Rate Code Distribution
        fig_rate = px.pie(
            filtered_df,
            names='Rate Code Name',
            title='Rate Code Distribution'
        )
        st.plotly_chart(fig_rate, use_container_width=True)

    with col2:
        # Arrivals by Date
        daily_arrivals = filtered_df['Arrival Date Short'].value_counts().sort_index()
        
        if daily_arrivals.empty:
            st.warning("No arrival data available for the selected filters.")
        else:
            fig_arrivals = px.line(
                x=daily_arrivals.index,
                y=daily_arrivals.values,
                labels={'x': 'Date', 'y': 'Arrivals'},
                title='Arrivals by Date'
            )
            st.plotly_chart(fig_arrivals, use_container_width=True)





import pandas as pd
import requests
import time
import json

############################################
# Marketing Tab
############################################

# Helper Functions
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
        # Set the reset trigger to True
        st.session_state['reset_trigger'] = True

        # Store the new defaults in session state
        st.session_state[f'default_check_in_start_{selected_resort}'] = min_check_in
        st.session_state[f'default_check_in_end_{selected_resort}'] = max_check_out
        st.session_state[f'default_check_out_start_{selected_resort}'] = min_check_in
        st.session_state[f'default_check_out_end_{selected_resort}'] = max_check_out
        st.session_state[f'default_total_price_{selected_resort}'] = (float(total_price_min), float(total_price_max))
        st.session_state[f'default_rate_code_{selected_resort}'] = "All"
    except Exception as e:
        st.error(f"Error resetting filters: {e}")

# Updated fetch_communication_info function
def fetch_communication_info(guest_df, headers):
    statuses, dates, durations, agent_names = [], [], [], []
    total_messages_list, total_calls_list = [], []
    answered_calls_list, missed_calls_list, call_attempts_list = [], [], []
    pre_arrival_calls_list, pre_arrival_texts_list = [], []
    post_arrival_calls_list, post_arrival_texts_list = [], []
    calls_under_40sec_list = []

    for _, row in guest_df.iterrows():
        phone = row['Phone Number']
        arrival_date = row['Check In']  # Use 'Check In' instead of 'Arrival Date Short'
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
            except Exception as e:
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
        total_messages_list, total_calls_list,
        answered_calls_list, missed_calls_list,
        call_attempts_list,
        pre_arrival_calls_list, pre_arrival_texts_list,
        post_arrival_calls_list, post_arrival_texts_list,
        calls_under_40sec_list
    )

# Updated get_communication_info function
def get_communication_info(phone_number, headers, arrival_date):
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

    # Convert arrival_date to datetime
    if isinstance(arrival_date, str):
        arrival_date = datetime.fromisoformat(arrival_date)
    elif isinstance(arrival_date, pd.Timestamp):
        arrival_date = arrival_date.to_pydatetime()
    else:
        # Assuming it's already datetime
        pass
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
                    msg_time = datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00'))
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
                    call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00'))
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
                        call_duration = call.get("duration")
                        agent_name = call.get("user", {}).get("name", "Unknown Agent")

                    call_attempts += 1

                    # Determine if the call was answered
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
        'last_date': latest_datetime.strftime("%Y-%m-%d %H:%M:%S") if latest_datetime else None,
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

# Main Tab2 Content
with tab2:
    st.title("�� Marketing Information by Resort")

    # Resort selection
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique())
    )

    # Filter for selected resort
    resort_df = df[df['Market'] == selected_resort].copy()
    st.subheader(f"Guest Information for {selected_resort}")

    # Set default dates based on the selected resort
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

    # Date filters with unique keys to reset when a new resort is selected
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
                total_price_min = total_price_min - 1  # Add a buffer of 1 unit
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
            total_price_range = (0, 0)  # Default range if no valid data

        # Dropdown for Rate Code
        rate_code_options = sorted(resort_df['Rate Code Name'].dropna().unique()) if 'Rate Code Name' in resort_df.columns else []
        selected_rate_code = st.selectbox(
            "Select Rate Code",
            options=["All"] + rate_code_options,
            key=f'rate_code_filter_{selected_resort}'
        )

    with st.container():
        # Reset Filters Button
        if st.button("Reset Filters"):
            reset_filters(selected_resort, min_check_in, max_check_out, total_price_min, total_price_max)

    # Process and display data
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
        if selected_rate_code != "All" and 'Rate Code Name' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Rate Code Name'] == selected_rate_code]

        # Remove duplicate rows based on 'Phone Number' and reset index
        display_df = filtered_df.drop_duplicates(subset=['Phone Number']).reset_index(drop=True)

        # Optional: Verify that 'Phone Number' is unique
        if display_df['Phone Number'].duplicated().any():
            st.error("Duplicate Phone Numbers found in the data. Please ensure each guest has a unique phone number.")
            st.stop()

        if not display_df.empty:
            # Prepare display DataFrame
            display_df = display_df.rename(columns={
                'Name': 'Guest Name',
                'Arrival Date Short': 'Check In',
                'Departure Date Short': 'Check Out',
                'Rate Code Name': 'Rate Code',
                'Total Price': 'Price'
            })

            # Ensure required columns are present
            required_columns = [
                'Guest Name', 'Check In', 'Check Out', 'Phone Number', 'Rate Code', 'Price',
                'Communication Status', 'Last Communication Date', 'Call Duration (seconds)', 'Agent Name',
                'Total Messages', 'Total Calls', 'Answered Calls', 'Missed Calls', 'Call Attempts',
                'Pre-Arrival Calls', 'Pre-Arrival Texts', 'Post-Arrival Calls', 'Post-Arrival Texts', 'Calls Under 40 sec'
            ]
            for col in required_columns:
                if col not in display_df.columns:
                    display_df[col] = None  # Add missing column with default value

            # Format phone numbers
            display_df['Phone Number'] = display_df['Phone Number'].apply(cleanup_phone_number)

            # Truncate long text fields to prevent overflow
            display_df['Guest Name'] = display_df['Guest Name'].apply(lambda x: truncate_text(x, max_length=30))
            display_df['Agent Name'] = display_df['Agent Name'].apply(lambda x: truncate_text(x, max_length=30))

            # Add Select All checkbox
            select_all = st.checkbox("Select All Guests", key=f'select_all_{selected_resort}')
            display_df['Select'] = select_all

            # Initialize session state for communication data, scoped by resort
            if 'communication_data' not in st.session_state:
                st.session_state['communication_data'] = {}
            if selected_resort not in st.session_state['communication_data']:
                st.session_state['communication_data'][selected_resort] = {}

            # **Retrieve and Apply Existing Communication Data**
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

            # **Fetch Communication Info Button**
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

                    # Verify that all lists have the same length as display_df
                    expected_length = len(display_df)
                    actual_lengths = [len(lst) for lst in [
                        statuses, dates, durations, agent_names,
                        total_messages_list, total_calls_list,
                        answered_calls_list, missed_calls_list,
                        call_attempts_list,
                        pre_arrival_calls_list, pre_arrival_texts_list,
                        post_arrival_calls_list, post_arrival_texts_list,
                        calls_under_40sec_list
                    ]]
                    if not all(length == expected_length for length in actual_lengths):
                        st.error("Mismatch in communication data lengths. Aborting update to prevent data misalignment.")
                        st.stop()

                    # Assign communication data directly to display_df
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

                    # Update session state scoped to the selected resort
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
                        for phone, status, date, duration, agent, total_msgs, total_cls, answered_cls, missed_cls, call_atpts, pre_calls, pre_texts, post_calls, post_texts, under_40sec
                        in zip(
                            display_df['Phone Number'], statuses, dates, durations, agent_names,
                            total_messages_list, total_calls_list, answered_calls_list, missed_calls_list, call_attempts_list,
                            pre_arrival_calls_list, pre_arrival_texts_list,
                            post_arrival_calls_list, post_arrival_texts_list,
                            calls_under_40sec_list
                        )
                    }

                    st.success("Communication information successfully fetched and updated.")

            # Reorder columns
            display_df = display_df[
                [
                    'Select', 'Guest Name', 'Check In', 'Check Out',
                    'Phone Number', 'Rate Code', 'Price',
                    'Communication Status', 'Last Communication Date',
                    'Call Duration (seconds)', 'Agent Name',
                    'Total Messages', 'Total Calls', 'Answered Calls', 'Missed Calls', 'Call Attempts',
                    'Pre-Arrival Calls', 'Pre-Arrival Texts', 'Post-Arrival Calls', 'Post-Arrival Texts', 'Calls Under 40 sec'
                ]
            ]

            # Display the interactive data editor with adjusted column widths
            edited_df = st.data_editor(
                display_df,
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Select",
                        help="Select or deselect this guest",
                        default=False,
                        width="60px"  # Narrow width for checkboxes
                    ),
                    "Guest Name": st.column_config.TextColumn(
                        "Guest Name",
                        width="200px"  # Adjust as needed
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

            # Ensure 'Select' column contains valid boolean values
            if 'Select' in edited_df.columns:
                # Map string representations to booleans
                edited_df['Select'] = edited_df['Select'].map({True: True, False: False, 'True': True, 'False': False})
                # Fill any NaN values with False
                edited_df['Select'] = edited_df['Select'].fillna(False)
                # Ensure the 'Select' column is of boolean data type
                edited_df['Select'] = edited_df['Select'].astype(bool)
                # Now select the guests safely
                selected_guests = edited_df[edited_df['Select']]
            else:
                st.error("The 'Select' column is missing from the edited data.")

            # Debugging: Verify DataFrame After Editing
            st.write("Display DataFrame after editing:")
            st.dataframe(edited_df.head())

    else:
        st.warning("No data available for the selected filters.")

############################################
# Message Templates Section
############################################
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

############################################
# Send SMS to Selected Guests
############################################
if 'edited_df' in locals() and not edited_df.empty:
    selected_guests = edited_df[edited_df['Select']]
    num_selected = len(selected_guests)
    if not selected_guests.empty:
        button_label = f"Send SMS to {num_selected} Guest{'s' if num_selected!= 1 else ''}"
        if st.button(button_label):
            openphone_url = "https://api.openphone.com/v1/messages"
            headers_sms = {
                "Authorization": OPENPHONE_API_KEY,
                "Content-Type": "application/json"
            }
            sender_phone_number = OPENPHONE_NUMBER  # Your OpenPhone number

            for idx, row in selected_guests.iterrows():
                recipient_phone = row['Phone Number']  # Use actual guest's phone number
                payload = {
                    "content": message_preview,
                    "from": sender_phone_number,
                    "to": [recipient_phone]
                }

                try:
                    response = requests.post(openphone_url, json=payload, headers=headers_sms)
                    if response.status_code == 202:
                        st.success(f"Message sent to {row['Guest Name']} ({recipient_phone})")
                    else:
                        st.error(f"Failed to send message to {row['Guest Name']} ({recipient_phone})")
                        st.write("Response Status Code:", response.status_code)
                        try:
                            st.write("Response Body:", response.json())
                        except:
                            st.write("Response Body:", response.text)
                except Exception as e:
                    st.error(f"Exception while sending message to {row['Guest Name']} ({recipient_phone}): {str(e)}")

                time.sleep(0.2)  # Respect rate limits
    else:
        st.info("No guests selected to send SMS.")
else:
    st.info("No guest data available to send SMS.")


############################################
# Tour Prediction Tab
############################################
with tab3:
    st.title("🔮 Tour Prediction Dashboard")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date for Tour Prediction", 
            value=pd.to_datetime(df['Arrival Date Short']).min().date()
        )
    with col2:
        end_date = st.date_input(
            "End Date for Tour Prediction", 
            value=pd.to_datetime(df['Arrival Date Short']).max().date()
        )

    # Validate date range
    if start_date > end_date:
        st.error("Start Date cannot be after End Date.")
    else:
        # Prepare a DataFrame to collect all resort data
        all_resorts_tour_data = []
        
        for resort in sorted(df['Market'].unique()):
            resort_df = df[df['Market'] == resort].copy()
            resort_df['Arrival Date Short'] = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
            filtered_resort_df = resort_df[
                (resort_df['Arrival Date Short'].dt.date >= start_date) & 
                (resort_df['Arrival Date Short'].dt.date <= end_date)
            ]

            # Daily Arrivals
            daily_arrivals = filtered_resort_df.groupby(filtered_resort_df['Arrival Date Short'].dt.date).size().reset_index(name='Arrivals')
            daily_arrivals = daily_arrivals.rename(columns={'Arrival Date Short': 'Date'})  # Rename for consistency

            st.subheader(f"{resort}")

            # Conversion Rate Input
            conversion_rate = st.number_input(
                f"Conversion Rate for {resort} (%)", 
                min_value=0.0, 
                max_value=100.0, 
                value=10.0, 
                step=0.5,
                key=f"conversion_{resort}"
            ) / 100

            # Calculate Tours, rounded down using math.floor
            daily_arrivals['Tours'] = daily_arrivals['Arrivals'].apply(
                lambda a: math.floor(a * conversion_rate)
            )

            st.dataframe(daily_arrivals)

            # Aggregate summaries for visualization later
            all_resorts_tour_data.append(daily_arrivals.assign(Market=resort))

        # Concatenate all resort data
        if all_resorts_tour_data:
            full_summary_df = pd.concat(all_resorts_tour_data, ignore_index=True)

            # Check if 'Date' column exists
            if 'Date' not in full_summary_df.columns:
                st.error("The 'Date' column is missing from the tour summary data.")
            else:
                # Overall Summary
                st.markdown("---")
                st.subheader("Overall Tour Summary Across All Resorts")

                # Handle empty DataFrame
                if full_summary_df.empty:
                    st.warning("No tour data available for the selected date range.")
                else:
                    overall_summary = full_summary_df.groupby('Date').sum().reset_index()

                    # Check if 'Date' column exists
                    if 'Date' not in overall_summary.columns:
                        st.error("The 'Date' column is missing from the overall summary data.")
                    else:
                        st.dataframe(overall_summary)

                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Total Arrivals for All Resorts", overall_summary['Arrivals'].sum())
                        with col2:
                            st.metric("Total Estimated Tours for All Resorts", overall_summary['Tours'].sum())
        else:
            st.info("No tour data available for the selected date range.")

with tab4:
    # Pass the owner DataFrame to the Owner Marketing module
    owner_df = owner_marketing.get_owner_sheet_data()
    owner_marketing.run_owner_marketing_tab(owner_df=owner_df)
    # Ensure that `get_owner_sheet_data` is properly defined in owner_marketing.py
    # Alternatively, pass `owner_df` from the main app if it's already loaded

with tab5:
    st.header("Overnight Misses")
    # Placeholder for Overnight Misses functionality
    st.info("Overnight Misses functionality coming soon...")
    
    # You can add some basic structure for future development
    st.subheader("Missed Opportunities")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Misses", "---")
    with col2:
        st.metric("Revenue Impact", "$---")
    with col3:
        st.metric("Recovery Rate", "---")
with tab6:
    try:
        from openphone import run_openphone_tab
        run_openphone_tab()
    except Exception as e:
        st.error(f"Error in OpenPhone tab: {str(e)}")
############################################
# Raw Data Viewer
############################################
with st.expander("Show Raw Data"):
    st.dataframe(df)
