import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
import gspread
from google.oauth2 import service_account
import math
import requests
import time
import re

# Set page configuration
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

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

############################################
# Secure OpenPhone Credentials
############################################

# Access OpenPhone API credentials from st.secrets
OPENPHONE_API_KEY = st.secrets["openphone"]["api_key"]
OPENPHONE_NUMBER = st.secrets["openphone"]["number"]

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

# Helper Functions
def sanitize_key(key):
    """
    Sanitize the key by replacing non-alphanumeric characters with underscores.
    Ensures that the key is not empty by adding a prefix if necessary.
    """
    sanitized = re.sub(r'\W+', '_', key)
    if not sanitized:
        sanitized = 'resort'
    return f'resort_{sanitized}'

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

def rate_limited_request(url, headers, params, request_type='get'):
    """Make an API request while respecting rate limits."""
    time.sleep(1 / 5)  # 5 requests per second max
    try:
        if request_type == 'get':
            response = requests.get(url, headers=headers, params=params)
        elif request_type == 'post':
            response = requests.post(url, headers=headers, json=params)
        else:
            st.warning(f"Unsupported request type: {request_type}")
            return None

        if response and response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error: {response.status_code}")
            st.warning(f"Response: {response.text}")
    except Exception as e:
        st.warning(f"Exception during request: {str(e)}")
    return None

def get_all_phone_number_ids(headers):
    """Retrieve all phoneNumberIds associated with your OpenPhone account."""
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    response_data = rate_limited_request(phone_numbers_url, headers, {})
    return [pn.get('id') for pn in response_data.get('data', [])] if response_data else []

def get_last_communication_info(phone_number, headers):
    """Retrieve the last communication status with the guest."""
    phone_number_ids = get_all_phone_number_ids(headers)
    if not phone_number_ids:
        return "No Communications", None, None, None

    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    latest_datetime = None
    latest_type = None
    latest_direction = None
    call_duration = None
    agent_name = None

    for phone_number_id in phone_number_ids:
        params = {"phoneNumberId": phone_number_id, "participants": [phone_number], "maxResults": 50}
        
        # Fetch messages
        messages_response = rate_limited_request(messages_url, headers, params)
        if messages_response and 'data' in messages_response:
            for message in messages_response['data']:
                msg_time = datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00'))
                if not latest_datetime or msg_time > latest_datetime:
                    latest_datetime = msg_time
                    latest_type = "Message"
                    latest_direction = message.get("direction", "unknown")
                    agent_name = message.get("user", {}).get("name", "Unknown Agent")

        # Fetch calls
        calls_response = rate_limited_request(calls_url, headers, params)
        if calls_response and 'data' in calls_response:
            for call in calls_response['data']:
                call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00'))
                if not latest_datetime or call_time > latest_datetime:
                    latest_datetime = call_time
                    latest_type = "Call"
                    latest_direction = call.get("direction", "unknown")
                    call_duration = call.get("duration")
                    agent_name = call.get("user", {}).get("name", "Unknown Agent")

    if not latest_datetime:
        return "No Communications", None, None, None

    return f"{latest_type} - {latest_direction}", latest_datetime.strftime("%Y-%m-%d %H:%M:%S"), call_duration, agent_name

def fetch_communication_info(guest_df, headers):
    """Fetch communication info for all guests."""
    if 'Phone Number' not in guest_df.columns:
        st.error("The column 'Phone Number' is missing in the DataFrame.")
        return ["No Status"] * len(guest_df), [None] * len(guest_df), [None] * len(guest_df), ["Unknown"] * len(guest_df)

    guest_df['Phone Number'] = guest_df['Phone Number'].astype(str).str.strip()
    statuses, dates, durations, agent_names = [], [], [], []

    for _, row in guest_df.iterrows():
        phone = row['Phone Number']
        if phone and phone != 'No Data':
            try:
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

# Initialize session state variables
if 'communication_data' not in st.session_state:
    st.session_state['communication_data'] = {}

def init_session_state():
    if 'default_dates' not in st.session_state:
        st.session_state['default_dates'] = {}
    
    # Initialize date input keys for all resorts
    for resort in df['Market'].unique():
        sanitized_resort = sanitize_key(resort)
        check_in_start_key = f'check_in_start_input_{sanitized_resort}'
        check_in_end_key = f'check_in_end_input_{sanitized_resort}'
        check_out_start_key = f'check_out_start_input_{sanitized_resort}'
        check_out_end_key = f'check_out_end_input_{sanitized_resort}'
        
        if check_in_start_key not in st.session_state:
            st.session_state[check_in_start_key] = pd.to_datetime('today').date()
        if check_in_end_key not in st.session_state:
            st.session_state[check_in_end_key] = pd.to_datetime('today').date()
        if check_out_start_key not in st.session_state:
            st.session_state[check_out_start_key] = pd.to_datetime('today').date()
        if check_out_end_key not in st.session_state:
            st.session_state[check_out_end_key] = pd.to_datetime('today').date()

# Call the initialization function
init_session_state()

############################################
# Create Tabs
############################################
tab1, tab2, tab3 = st.tabs(["Dashboard", "Marketing", "Tour Prediction"])

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
        selected_rate_codes = st.multiselect(
            "Select Rate Codes",
            options=sorted(df['Rate Code Name'].unique()),
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

############################################
# Marketing Tab
############################################

with tab2:
    st.title("🏖️ Marketing Information by Resort")

    # Resort selection
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique())
    )

    # Sanitize the resort name for use in session_state keys
    sanitized_resort = sanitize_key(selected_resort)

    # Debugging: Display selected and sanitized resort
    st.write(f"Selected Resort: {selected_resort}")
    st.write(f"Sanitized Resort: {sanitized_resort}")

    # Filter for selected resort
    resort_df = df[df['Market'] == selected_resort].copy()
    st.subheader(f"Guest Information for {selected_resort}")

    # Compute min and max dates based on the selected resort's data
    if not resort_df.empty:
        arrival_dates = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
        departure_dates = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce')

        arrival_dates = arrival_dates.dropna()
        departure_dates = departure_dates.dropna()

        min_check_in = arrival_dates.min().date() if not arrival_dates.empty else date.today()
        max_check_out = departure_dates.max().date() if not departure_dates.empty else date.today()
    else:
        today = date.today()
        min_check_in = today
        max_check_out = today

    # Define unique keys for date inputs based on the sanitized resort name
    check_in_start_key = f'check_in_start_input_{sanitized_resort}'
    check_in_end_key = f'check_in_end_input_{sanitized_resort}'
    check_out_start_key = f'check_out_start_input_{sanitized_resort}'
    check_out_end_key = f'check_out_end_input_{sanitized_resort}'

    # Initialize date inputs in session_state if not already present
    if check_in_start_key not in st.session_state:
        st.session_state[check_in_start_key] = min_check_in
    if check_in_end_key not in st.session_state:
        st.session_state[check_in_end_key] = max_check_out
    if check_out_start_key not in st.session_state:
        st.session_state[check_out_start_key] = min_check_in
    if check_out_end_key not in st.session_state:
        st.session_state[check_out_end_key] = max_check_out

    # Debugging: Display session state keys and their values
    st.write(f"Check In Start Key: {check_in_start_key} = {st.session_state.get(check_in_start_key, 'Not Set')}")
    st.write(f"Check In End Key: {check_in_end_key} = {st.session_state.get(check_in_end_key, 'Not Set')}")
    st.write(f"Check Out Start Key: {check_out_start_key} = {st.session_state.get(check_out_start_key, 'Not Set')}")
    st.write(f"Check Out End Key: {check_out_end_key} = {st.session_state.get(check_out_end_key, 'Not Set')}")

    # Arrange the date inputs and the Reset button in columns
    col1, col2, col3 = st.columns([0.4, 0.4, 0.2])
    with col1:
        check_in_start = st.date_input(
            "Check In Date (Start)",
            value=st.session_state[check_in_start_key],
            key=check_in_start_key
        )
        check_in_end = st.date_input(
            "Check In Date (End)",
            value=st.session_state[check_in_end_key],
            key=check_in_end_key
        )

    with col2:
        check_out_start = st.date_input(
            "Check Out Date (Start)",
            value=st.session_state[check_out_start_key],
            key=check_out_start_key
        )
        check_out_end = st.date_input(
            "Check Out Date (End)",
            value=st.session_state[check_out_end_key],
            key=check_out_end_key
        )

    with col3:
        if st.button("Reset Dates", key=f'reset_button_{sanitized_resort}'):
            # Reset the date inputs to min_check_in and max_check_out
            st.session_state[check_in_start_key] = min_check_in
            st.session_state[check_in_end_key] = max_check_out
            st.session_state[check_out_start_key] = min_check_in
            st.session_state[check_out_end_key] = max_check_out
            st.success("Date filters have been reset to the default maximum range.")

    # Filter the DataFrame based on the selected dates
    if not resort_df.empty:
        resort_df['Arrival Date Short'] = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
        resort_df['Departure Date Short'] = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce')

        filtered_df = resort_df[
            (resort_df['Arrival Date Short'].dt.date >= check_in_start) &
            (resort_df['Arrival Date Short'].dt.date <= check_in_end) &
            (resort_df['Departure Date Short'].dt.date >= check_out_start) &
            (resort_df['Departure Date Short'].dt.date <= check_out_end)
        ].copy()

        if not filtered_df.empty:
            # Prepare display DataFrame
            display_df = filtered_df.rename(columns={
                'Name': 'Guest Name',
                'Arrival Date Short': 'Check In',
                'Departure Date Short': 'Check Out'
            })[['Guest Name', 'Check In', 'Check Out', 'Phone Number']].copy()

            # Format phone numbers
            display_df['Phone Number'] = display_df['Phone Number'].apply(cleanup_phone_number)

            # Initialize communication columns
            display_df['Communication Status'] = 'Not Checked'
            display_df['Last Communication Date'] = None
            display_df['Call Duration (seconds)'] = None
            display_df['Agent Name'] = 'Unknown'

            # Update values from session state
            if 'communication_data' in st.session_state and len(st.session_state['communication_data']) > 0:
                for idx, row in display_df.iterrows():
                    phone = row['Phone Number']
                    if phone in st.session_state['communication_data']:
                        comm_data = st.session_state['communication_data'][phone]
                        display_df.at[idx, 'Communication Status'] = comm_data.get('status', 'Not Checked')
                        display_df.at[idx, 'Last Communication Date'] = comm_data.get('date', None)
                        display_df.at[idx, 'Call Duration (seconds)'] = comm_data.get('duration', None)
                        display_df.at[idx, 'Agent Name'] = comm_data.get('agent', 'Unknown')

            # Add Select All checkbox
            select_all = st.checkbox("Select All", key=f'select_all_{sanitized_resort}')
            display_df['Select'] = select_all

            # Fetch Communication Info Button
            if st.button("Fetch Communication Info", key=f'fetch_info_{sanitized_resort}'):
                headers = {
                    "Authorization": OPENPHONE_API_KEY,
                    "Content-Type": "application/json"
                }

                with st.spinner('Fetching communication information...'):
                    # Clean up phone numbers first
                    display_df['Phone Number'] = display_df['Phone Number'].apply(cleanup_phone_number)
                    
                    statuses, dates, durations, agent_names = fetch_communication_info(display_df, headers)
                    
                    # Update session state and display DataFrame
                    for phone, status, date, duration, agent in zip(
                        display_df['Phone Number'], statuses, dates, durations, agent_names):
                        st.session_state['communication_data'][phone] = {
                            'status': status,
                            'date': date,
                            'duration': duration,
                            'agent': agent
                        }
                        
                    display_df['Communication Status'] = statuses
                    display_df['Last Communication Date'] = dates
                    display_df['Call Duration (seconds)'] = durations
                    display_df['Agent Name'] = agent_names
                    
                    # Convert phone numbers to string type explicitly
                    display_df['Phone Number'] = display_df['Phone Number'].astype(str)

            # Reorder columns
            display_df = display_df[[
                'Select', 'Guest Name', 'Check In', 'Check Out', 
                'Phone Number', 'Communication Status', 
                'Last Communication Date', 'Call Duration (seconds)', 
                'Agent Name'
            ]]

            # Display the interactive data editor
            edited_df = st.data_editor(
                display_df,
                column_config={
                    "Select": st.column_config.CheckboxColumn(
                        "Select",
                        help="Select or deselect this guest",
                        default=select_all
                    ),
                    "Guest Name": st.column_config.TextColumn(
                        "Guest Name",
                        help="Guest's full name"
                    ),
                    "Check In": st.column_config.DateColumn(
                        "Check In",
                        help="Check-in date"
                    ),
                    "Check Out": st.column_config.DateColumn(
                        "Check Out",
                        help="Check-out date"
                    ),
                    "Phone Number": st.column_config.TextColumn(
                        "Phone Number",
                        help="Guest's phone number"
                    ),
                    "Communication Status": st.column_config.TextColumn(
                        "Communication Status",
                        help="Last communication status with the guest",
                        disabled=True
                    ),
                    "Last Communication Date": st.column_config.TextColumn(
                        "Last Communication Date",
                        help="Date and time of the last communication with the guest",
                        disabled=True
                    ),
                },
                hide_index=True,
                use_container_width=True,
                key=f"guest_editor_{sanitized_resort}"
            )
        else:
            st.warning("No data available for the selected date range.")
    else:
        st.warning("No data available for the selected resort.")

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

############################################
# Raw Data Viewer
############################################
with st.expander("Show Raw Data"):
    st.dataframe(df)
