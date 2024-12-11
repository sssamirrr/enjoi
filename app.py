import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2 import service_account
import math
import requests
import time

# Configure Page
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

# Optional CSS
st.markdown("""
    <style>
    .stDateInput {
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

# Constants (replace with real credentials)
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
OPENPHONE_NUMBER = "+18438972426"

# Google Sheets Connection
@st.cache_resource
def get_google_sheet_data():
    try:
        service_account_info = st.secrets["gcp_service_account"]
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ])
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(st.secrets["sheets"]["sheet_key"])
        worksheet = spreadsheet.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None

# Load Data
df = get_google_sheet_data()
if df is None:
    st.error("Failed to load data.")
    st.stop()

# Helper Functions
def rate_limited_request(url, headers, params, request_type='get'):
    time.sleep(1 / 5)
    try:
        response = requests.get(url, headers=headers, params=params) if request_type == 'get' else None
        if response and response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.warning(f"Exception during request: {str(e)}")
        return None

def get_last_communication_info(phone_number, headers):
    phone_number_ids = get_all_phone_number_ids(headers)
    if not phone_number_ids:
        st.error("No OpenPhone numbers found.")
        return "No Communications", None, None, None
    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"
    latest_datetime, latest_type, latest_direction, call_duration, agent_name = None, None, None, None, None
    for phone_number_id in phone_number_ids:
        params = {"phoneNumberId": phone_number_id, "participants": [phone_number], "maxResults": 50}
        for message in rate_limited_request(messages_url, headers, params).get('data', []):
            handle_communication_update(message, "Message", latest_datetime, latest_type, latest_direction, agent_name)
    return finalize_communication_info(latest_datetime, latest_type, latest_direction, call_duration, agent_name)

def handle_communication_update(item, item_type, latest_datetime, latest_type, latest_direction, agent_name):
    item_time = datetime.fromisoformat(item['createdAt'].replace('Z', '+00:00'))
    if not latest_datetime or item_time > latest_datetime:
        latest_datetime = item_time
        latest_type = item_type
        latest_direction = item.get("direction", "unknown")
        agent_name = item.get("user", {}).get("name", "Unknown Agent")

def get_all_phone_number_ids(headers):
    return [pn.get('id') for pn in rate_limited_request("https://api.openphone.com/v1/phone-numbers", headers, {}).get('data', [])]

def finalize_communication_info(latest_datetime, latest_type, latest_direction, call_duration, agent_name):
    if not latest_datetime:
        return "No Communications", None, None, None
    return f"{latest_type} - {latest_direction}", latest_datetime.strftime("%Y-%m-%d %H:%M:%S"), call_duration, agent_name

def fetch_communication_info(guest_df, headers):
    if 'Phone Number' not in guest_df.columns:
        st.error("Missing 'Phone Number' column.")
        return ["No Status"] * len(guest_df), [None] * len(guest_df), [None] * len(guest_df), ["Unknown"] * len(guest_df)
    guest_df['Phone Number'] = guest_df['Phone Number'].astype(str).str.strip()
    statuses, dates, durations, agent_names = [], [], [], []
    for _, row in guest_df.iterrows():
        if (phone := row['Phone Number']):
            status, date, duration, agent = get_last_communication_info(phone, headers)
            statuses.append(status)
            dates.append(date)
            durations.append(duration)
            agent_names.append(agent)
        else:
            statuses.append("Invalid Number")
            dates.append(None)
            durations.append(None)
            agent_names.append("Unknown")
    return statuses, dates, durations, agent_names

# Dashboard Tab
tab1, tab2, tab3 = st.tabs(["Dashboard", "Marketing", "Tour Prediction"])

with tab1:
    st.title("🏨 Hotel Reservations Dashboard")
    st.markdown("Real-time analysis of hotel reservations")
    col1, col2, col3 = st.columns(3)
    selected_hotel = col1.multiselect("Select Hotel", options=sorted(df['Market'].unique()), default=[])
    min_date, max_date = pd.to_datetime(df['Arrival Date Short']).min(), pd.to_datetime(df['Arrival Date Short']).max()
    date_range = col2.date_input("Select Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    selected_rate_codes = col3.multiselect("Select Rate Codes", options=sorted(df['Rate Code Name'].unique()), default=[])
    filter_data(selected_hotel, date_range, selected_rate_codes)

def filter_data(selected_hotel, date_range, selected_rate_codes):
    filtered_df = df.copy()
    if selected_hotel: filtered_df = filtered_df[filtered_df['Market'].isin(selected_hotel)]
    if isinstance(date_range, tuple) and len(date_range) == 2:
        filtered_df = filtered_df[(pd.to_datetime(filtered_df['Arrival Date Short']).dt.date >= date_range[0]) & (pd.to_datetime(filtered_df['Arrival Date Short']).dt.date <= date_range[1])]
    if selected_rate_codes: filtered_df = filtered_df[filtered_df['Rate Code Name'].isin(selected_rate_codes)]
    display_metrics(filtered_df)

def display_metrics(filtered_df):
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Reservations", len(filtered_df))
    col2.metric("Average Nights", f"{filtered_df['# Nights'].mean():.1f}" if not math.isnan(filtered_df['# Nights'].mean()) else "0")
    col3.metric("Total Room Nights", f"{filtered_df['# Nights'].sum():,.0f}")
    col4.metric("Unique Guests", filtered_df['Name'].nunique())
    display_charts(filtered_df)

def display_charts(filtered_df):
    col1, col2 = st.columns(2)
    plot_reservations_by_hotel(filtered_df, col1)
    plot_length_of_stay_distribution(filtered_df, col2)

    col1, col2 = st.columns(2)
    plot_rate_code_distribution(filtered_df, col1)
    plot_arrivals_by_date(filtered_df, col2)

def plot_reservations_by_hotel(filtered_df, col):
    reservations_by_hotel = filtered_df.groupby('Market').size().reset_index(name='Reservations').rename(columns={'Market': 'Hotel'})
    fig_hotels = px.bar(reservations_by_hotel, x='Hotel', y='Reservations', labels={'Hotel': 'Hotel', 'Reservations': 'Reservations'}, title='Reservations by Hotel')
    col.plotly_chart(fig_hotels, use_container_width=True) if not reservations_by_hotel.empty else col.warning("No reservation data available.")

def plot_length_of_stay_distribution(filtered_df, col):
    fig_los = px.histogram(filtered_df, x='# Nights', title='Length of Stay Distribution')
    col.plotly_chart(fig_los, use_container_width=True)

def plot_rate_code_distribution(filtered_df, col):
    fig_rate = px.pie(filtered_df, names='Rate Code Name', title='Rate Code Distribution')
    col.plotly_chart(fig_rate, use_container_width=True)

def plot_arrivals_by_date(filtered_df, col):
    daily_arrivals = filtered_df['Arrival Date Short'].value_counts().sort_index()
    fig_arrivals = px.line(x=daily_arrivals.index, y=daily_arrivals.values, labels={'x': 'Date', 'y': 'Arrivals'}, title='Arrivals by Date')
    col.plotly_chart(fig_arrivals, use_container_width=True) if not daily_arrivals.empty else col.warning("No arrival data available.")

############################################
# Marketing Tab
############################################
with tab2:
    st.title("📊 Marketing Information by Resort")
    
    if 'communication_fetched' not in st.session_state:
        st.session_state.communication_fetched = False

    selected_resort = st.selectbox("Select Resort", options=sorted(df['Market'].unique()))
    resort_df = df[df['Market'] == selected_resort].copy()
    st.subheader(f"Guest Information for {selected_resort}")

    def reset_filter_defaults():
        st.session_state.update({
            'check_in_start': st.session_state['default_dates'].get('check_in_start'),
            'check_in_end': st.session_state['default_dates'].get('check_in_end'),
            'check_out_start': st.session_state['default_dates'].get('check_out_start'),
            'check_out_end': st.session_state['default_dates'].get('check_out_end'),
        })

    # Establishing the default dates for filtering
    if not resort_df.empty:
        arrival_dates = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
        departure_dates = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce')

        min_check_in = arrival_dates.min().date() if not arrival_dates.empty else pd.to_datetime('today').date()
        max_check_out = departure_dates.max().date() if not departure_dates.empty else pd.to_datetime('today').date()

        if 'default_dates' not in st.session_state or not st.session_state['default_dates']:
            st.session_state['default_dates'] = {'check_in_start': min_check_in, 'check_in_end': max_check_out, 'check_out_start': min_check_in, 'check_out_end': max_check_out}

    # Define UI components for selecting date filter ranges
    col1, col2, col3 = st.columns([0.4, 0.4, 0.2])
    with col1:
        check_in_start = st.date_input("Check In Date (Start)", value=st.session_state['default_dates']['check_in_start'], key='check_in_start')
        check_in_end = st.date_input("Check In Date (End)", value=st.session_state['default_dates']['check_in_end'], key='check_in_end')

    with col2:
        check_out_start = st.date_input("Check Out Date (Start)", value=st.session_state['default_dates']['check_out_start'], key='check_out_start')
        check_out_end = st.date_input("Check Out Date (End)", value=st.session_state['default_dates']['check_out_end'], key='check_out_end')

    with col3:
        if st.button("Reset Dates"):
            reset_filter_defaults()

    # Apply date filters
    resort_df['Check In'] = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce').dt.date
    resort_df['Check Out'] = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce').dt.date
    filtered_df = resort_df[
        (resort_df['Check In'] >= check_in_start) &
        (resort_df['Check In'] <= check_in_end) &
        (resort_df['Check Out'] >= check_out_start) &
        (resort_df['Check Out'] <= check_out_end)
    ]

    # Handle empty DataFrame
    if filtered_df.empty:
        st.warning("No guests found for the selected filters.")
        display_df = pd.DataFrame(columns=['Select', 'Guest Name', 'Check In', 'Check Out', 'Phone Number', 'Communication Status', 'Last Communication Date', 'Call Duration (seconds)', 'Agent Name'])
    else:
        display_df = filtered_df[['Name', 'Check In', 'Check Out', 'Phone Number']].copy()
        display_df.columns = ['Guest Name', 'Check In', 'Check Out', 'Phone Number']
        display_df['Communication Status'] = 'Not Checked'
        display_df['Last Communication Date'] = None

        # Format phone numbers correctly
        def format_phone_number(phone):
            phone = ''.join(filter(str.isdigit, str(phone)))
            if len(phone) == 10:
                return f"+1{phone}"
            elif len(phone) == 11 and phone.startswith('1'):
                return f"+{phone}"
            return phone

        display_df['Phone Number'] = display_df['Phone Number'].apply(format_phone_number)

        # Assume communication information has not yet been updated
        if st.button("Fetch Communication Status"):
            st.session_state.communication_fetched = True
            headers = {"Authorization": OPENPHONE_API_KEY, "Content-Type": "application/json"}
            statuses, dates, durations, agent_names = fetch_communication_info(display_df, headers)
            display_df['Communication Status'] = statuses
            display_df['Last Communication Date'] = dates
            display_df['Call Duration (seconds)'] = durations
            display_df['Agent Name'] = agent_names

        # Add "Select All" option
        select_all = st.checkbox("Select All")
        display_df['Select'] = select_all

        # Ensure all necessary columns are present
        required_columns = ['Select', 'Guest Name', 'Check In', 'Check Out', 'Phone Number', 'Communication Status', 'Last Communication Date', 'Call Duration (seconds)', 'Agent Name']
        for col in required_columns:
            if col not in display_df.columns:
                display_df[col] = None

        # Reorder columns
        display_df = display_df[['Select', 'Guest Name', 'Check In', 'Check Out', 'Phone Number', 'Communication Status', 'Last Communication Date', 'Call Duration (seconds)', 'Agent Name']]
        
        # Display editable DataFrame
        edited_df = st.data_editor(display_df, hide_index=True, use_container_width=True, key="guest_editor")

    ############################################
    # Send SMS to Selected Guests
    ############################################
    if 'edited_df' in locals() and not edited_df.empty:
        selected_guests = edited_df[edited_df['Select']]
        num_selected = len(selected_guests)
        if not selected_guests.empty:
            if st.button(f"Send SMS to {num_selected} Guest{'s' if num_selected != 1 else ''}"):
                openphone_url = "https://api.openphone.com/v1/messages"
                headers_sms = {"Authorization": OPENPHONE_API_KEY, "Content-Type": "application/json"}
                sender_phone_number = OPENPHONE_NUMBER

                for idx, row in selected_guests.iterrows():
                    recipient_phone = row['Phone Number']
                    payload = {"content": message_preview, "from": sender_phone_number, "to": [recipient_phone]}

                    try:
                        response = requests.post(openphone_url, json=payload, headers=headers_sms)
                        if response.status_code == 202:
                            st.success(f"Message sent to {row['Guest Name']} ({recipient_phone})")
                        else:
                            st.error(f"Failed to send message to {row['Guest Name']} ({recipient_phone}): {response.text}")
                    except Exception as e:
                        st.error(f"Exception while sending message to {row['Guest Name']} ({recipient_phone}): {str(e)}")
                    time.sleep(0.2)
        else:
            st.info("No guests selected to send SMS.")

############################################
# Tour Prediction Tab
############################################
with tab3:
    st.title("🔮 Tour Prediction Dashboard")
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Start Date for Tour Prediction", value=pd.to_datetime(df['Arrival Date Short']).min().date())
    end_date = col2.date_input("End Date for Tour Prediction", value=pd.to_datetime(df['Arrival Date Short']).max().date())

    if start_date > end_date:
        st.error("Start Date cannot be after End Date.")
    else:
        all_resorts_tour_data = []
        for resort in sorted(df['Market'].unique()):
            prepare_tour_prediction_report(df, resort, start_date, end_date, all_resorts_tour_data)

        aggregate_and_display_data(all_resorts_tour_data)

def prepare_tour_prediction_report(df, resort, start_date, end_date, all_resorts_tour_data):
    resort_df = df[df['Market'] == resort].copy()
    resort_df['Arrival Date Short'] = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce')
    filtered_resort_df = resort_df[
        (resort_df['Arrival Date Short'].dt.date >= start_date) &
        (resort_df['Arrival Date Short'].dt.date <= end_date)
    ]

    # Daily Arrivals
    daily_arrivals = filtered_resort_df.groupby(filtered_resort_df['Arrival Date Short'].dt.date).size().reset_index(name='Arrivals')

    st.subheader(f"{resort}")
    conversion_rate = st.number_input(f"Conversion Rate for {resort} (%)", min_value=0.0, max_value=100.0, value=10.0, step=0.5, key=f"conversion_{resort}") / 100
    daily_arrivals['Tours'] = daily_arrivals['Arrivals'].apply(lambda a: math.floor(a * conversion_rate))
    st.dataframe(daily_arrivals)
    all_resorts_tour_data.append(daily_arrivals.assign(Market=resort))

def aggregate_and_display_data(all_resorts_tour_data):
    if all_resorts_tour_data:
        full_summary_df = pd.concat(all_resorts_tour_data, ignore_index=True)
        overall_summary = full_summary_df.groupby('Date').sum().reset_index()
        st.markdown("---")
        st.subheader("Overall Tour Summary Across All Resorts")
        st.dataframe(overall_summary)
        col1, col2 = st.columns(2)
        col1.metric("Total Arrivals for All Resorts", overall_summary['Arrivals'].sum())
        col2.metric("Total Estimated Tours for All Resorts", overall_summary['Tours'].sum())
    else:
        st.info("No tour data available for the selected date range.")

# Raw Data Viewer
with st.expander("Show Raw Data"):
    st.dataframe(df)
