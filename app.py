import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2 import service_account
import math
import requests
import time

# Set page config
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

# Add CSS for styling
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

@st.cache_resource
def get_google_sheet_data():
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
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
        st.error(f"Error: {str(e)}")
        return None

# Load the data
df = get_google_sheet_data()

if df is None:
    st.error("Failed to load data. Please check your connection and credentials.")
    st.stop()

# Create tabs
tab1, tab2, tab3 = st.tabs(["Dashboard", "Marketing", "Tour Prediction"])

# Dashboard Tab
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
    
    if len(date_range) == 2:
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
        st.metric("Average Nights", f"{filtered_df['# Nights'].mean():.1f}")
    with col3:
        st.metric("Total Room Nights", f"{filtered_df['# Nights'].sum():,.0f}")
    with col4:
        st.metric("Unique Guests", filtered_df['Name'].nunique())

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        fig_hotels = px.bar(
            filtered_df['Market'].value_counts().reset_index(),
            x='Market',
            y='count',
            title='Reservations by Hotel'
        )
        st.plotly_chart(fig_hotels, use_container_width=True)

    with col2:
        fig_los = px.histogram(
            filtered_df,
            x='# Nights',
            title='Length of Stay Distribution'
        )
        st.plotly_chart(fig_los, use_container_width=True)

    col1, col2 = st.columns(2)

    with col1:
        fig_rate = px.pie(
            filtered_df,
            names='Rate Code Name',
            title='Rate Code Distribution'
        )
        st.plotly_chart(fig_rate, use_container_width=True)

    with col2:
        daily_arrivals = filtered_df['Arrival Date Short'].value_counts().sort_index()
        fig_arrivals = px.line(
            x=daily_arrivals.index,
            y=daily_arrivals.values,
            title='Arrivals by Date'
        )
        st.plotly_chart(fig_arrivals, use_container_width=True)

# Session state initialization
if 'check_in_start' not in st.session_state:
    st.session_state['check_in_start'] = None
if 'check_in_end' not in st.session_state:
    st.session_state['check_in_end'] = None
if 'check_out_start' not in st.session_state:
    st.session_state['check_out_start'] = None
if 'check_out_end' not in st.session_state:
    st.session_state['check_out_end'] = None
if 'refresh' not in st.session_state:
    st.session_state['refresh'] = False

if 'check_in_start' not in st.session_state or st.session_state['check_in_start'] is None:
    st.session_state['check_in_start'] = datetime(2024, 11, 16).date()
if 'check_in_end' not in st.session_state or st.session_state['check_in_end'] is None:
    st.session_state['check_in_end'] = datetime(2024, 11, 22).date()
if 'check_out_start' not in st.session_state or st.session_state['check_out_start'] is None:
    st.session_state['check_out_start'] = datetime(2024, 11, 23).date()
if 'check_out_end' not in st.session_state or st.session_state['check_out_end'] is None:
    st.session_state['check_out_end'] = datetime(2024, 11, 27).date()

if 'check_in_start' not in st.session_state:
    st.session_state['check_in_start'] = pd.to_datetime(df['Arrival Date Short']).min().date()
if 'check_in_end' not in st.session_state:
    st.session_state['check_in_end'] = pd.to_datetime(df['Arrival Date Short']).max().date()
if 'check_out_start' not in st.session_state:
    st.session_state['check_out_start'] = pd.to_datetime(df['Departure Date Short']).min().date()
if 'check_out_end' not in st.session_state:
    st.session_state['check_out_end'] = pd.to_datetime(df['Departure Date Short']).max().date()
if 'select_all_state' not in st.session_state:
    st.session_state['select_all_state'] = False

############################################
# Updated Functions for v1 Only
############################################

def get_phone_number_id(headers, phone_number):
    url = "https://api.openphone.com/v1/phone-numbers"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        st.write("Phone Numbers Response:", data)  # Debug line to inspect structure
        for pn in data.get('data', []):
            st.write("Number object:", pn)  # Debug line to see all top-level keys
            # Compare top-level 'number' field to your phone_number
            if pn.get('number') == phone_number:
                return pn['id']
    else:
        st.write(f"Error retrieving phone numbers: {response.status_code}")
        st.write("Response:", response.text)
    return None

    else:
        st.write(f"Error retrieving phone numbers: {response.status_code}")
        st.write("Response:", response.text)
    return None

def get_last_communication_status(phone_number, headers, openphone_number):
    # Retrieve phoneNumberId using v1 endpoint
    phone_number_id = get_phone_number_id(headers, openphone_number)
    if not phone_number_id:
        st.write("Failed to retrieve phoneNumberId")
        return "Error"

    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    # maxResults must be greater than 1
    params = {
        "phoneNumberId": phone_number_id,
        "participants": [phone_number],
        "maxResults": 2  # Changed to 2 as per API requirements
    }

    last_message = None
    last_call = None

    # Fetch the last message
    message_response = requests.get(messages_url, headers=headers, params=params)
    st.write("Message API Response:", message_response.text)  # Debug
    if message_response.status_code == 200:
        message_data = message_response.json()
        if message_data.get('data'):
            last_message = message_data['data'][0]
    else:
        st.write(f"Message API Error for {phone_number}: {message_response.status_code}")
        st.write("Response:", message_response.text)
        return "Error"

    # Fetch the last call
    call_response = requests.get(calls_url, headers=headers, params=params)
    st.write("Call API Response:", call_response.text)  # Debug
    if call_response.status_code == 200:
        call_data = call_response.json()
        if call_data.get('data'):
            last_call = call_data['data'][0]
    else:
        st.write(f"Call API Error for {phone_number}: {call_response.status_code}")
        st.write("Response:", call_response.text)
        return "Error"

    # Determine timestamps and direction
    # Print them out to verify correct keys
    if last_message:
        st.write("Last Message:", last_message)
    if last_call:
        st.write("Last Call:", last_call)

    # Assuming v1 messages and calls both have 'createdAt' and 'direction' keys at top level
    # If not, adjust based on printed output
    def parse_datetime(item):
        # Try top-level createdAt
        created_at = item.get('createdAt')
        if created_at:
            return datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        # If not found, try attributes
        attrs = item.get('attributes', {})
        if attrs.get('createdAt'):
            return datetime.fromisoformat(attrs['createdAt'].replace('Z', '+00:00'))
        return None

    def parse_direction(item):
        # Try top-level direction
        direction = item.get('direction')
        if direction:
            return direction
        # If not found, try attributes
        attrs = item.get('attributes', {})
        return attrs.get('direction')

    message_time = parse_datetime(last_message) if last_message else None
    call_time = parse_datetime(last_call) if last_call else None

    # Compare times
    if last_message and last_call:
        if message_time > call_time:
            # Last communication was a message
            direction = parse_direction(last_message)
            # Assuming 'outgoing' and 'incoming' are the direction values; adjust if different
            return "Sent Message" if direction in ['outgoing', 'outbound'] else "Received Message"
        else:
            direction = parse_direction(last_call)
            return "Made Call" if direction in ['outgoing', 'outbound'] else "Received Call"
    elif last_message:
        direction = parse_direction(last_message)
        return "Sent Message" if direction in ['outgoing', 'outbound'] else "Received Message"
    elif last_call:
        direction = parse_direction(last_call)
        return "Made Call" if direction in ['outgoing', 'outbound'] else "Received Call"
    else:
        return "No Communications"

@st.cache_data
def fetch_communication_statuses(guest_df, headers, openphone_number):
    statuses = []
    for idx, row in guest_df.iterrows():
        phone_number = row['Phone Number']
        status = get_last_communication_status(phone_number, headers, openphone_number)
        statuses.append(status)
        time.sleep(0.2)  # respect rate limits
    return statuses

# Marketing Tab
with tab2:
    st.title("📊 Marketing Information by Resort")

    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique())
    )

    resort_df = df[df['Market'] == selected_resort].copy()
    st.subheader(f"Guest Information for {selected_resort}")

    # Date filters already handled above
    # Apply filters to resort_df similarly as in the dashboard if needed

    resort_df['Check In'] = pd.to_datetime(resort_df['Arrival Date Short'], errors='coerce').dt.date
    resort_df['Check Out'] = pd.to_datetime(resort_df['Departure Date Short'], errors='coerce').dt.date
    resort_df = resort_df.dropna(subset=['Check In', 'Check Out'])

    mask = (
        (resort_df['Check In'] >= st.session_state['check_in_start']) &
        (resort_df['Check In'] <= st.session_state['check_in_end']) &
        (resort_df['Check Out'] >= st.session_state['check_out_start']) &
        (resort_df['Check Out'] <= st.session_state['check_out_end'])
    )
    filtered_df = resort_df[mask]

    if filtered_df.empty:
        st.warning("No guests found for the selected filters.")
        display_df = pd.DataFrame(columns=['Select', 'Guest Name', 'Check In', 'Check Out', 'Phone Number', 'Communication Status'])
    else:
        display_df = filtered_df[['Name', 'Check In', 'Check Out', 'Phone Number']].copy()
        display_df.columns = ['Guest Name', 'Check In', 'Check Out', 'Phone Number']

        def format_phone_number(phone):
            phone = ''.join(filter(str.isdigit, str(phone)))
            if len(phone) == 10:
                return f"+1{phone}"
            elif len(phone) == 11 and phone.startswith('1'):
                return f"+{phone}"
            else:
                return phone

        display_df['Phone Number'] = display_df['Phone Number'].apply(format_phone_number)
        display_df['Select'] = False
        display_df['Communication Status'] = 'Checking...'

        select_all = st.checkbox("Select All", key="select_all_checkbox")
        display_df['Select'] = select_all

        headers = {
            "Authorization": "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7",  # Your OpenPhone API key (update if needed)
            "Content-Type": "application/json"
        }

        openphone_number = "+18438972426"  # Replace with your actual OpenPhone number in E.164 format
        display_df['Communication Status'] = fetch_communication_statuses(display_df, headers, openphone_number)

        display_df = display_df[['Select', 'Guest Name', 'Check In', 'Check Out', 'Phone Number', 'Communication Status']]
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Select": st.column_config.CheckboxColumn("Select", help="Select or deselect this guest", default=select_all),
                "Guest Name": st.column_config.TextColumn("Guest Name", help="Guest's full name"),
                "Check In": st.column_config.DateColumn("Check In", help="Check-in date"),
                "Check Out": st.column_config.DateColumn("Check Out", help="Check-out date"),
                "Phone Number": st.column_config.TextColumn("Phone Number", help="Guest's phone number"),
                "Communication Status": st.column_config.TextColumn("Communication Status", help="Last communication status with the guest", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="guest_editor"
        )

    st.markdown("---")
    st.subheader("Message Templates")

    message_templates = {
        "Welcome Message": f"Welcome to {selected_resort}! Please visit our concierge desk for your welcome gift! 🎁",
        "Check-in Follow-up": f"Hello, we hope you're enjoying your stay at {selected_resort}. Don't forget to collect your welcome gift at the concierge desk! 🎁",
        "Checkout Message": f"Thank you for staying with us at {selected_resort}! We hope you had a great stay. Please stop by the concierge desk before you leave for a special gift! 🎁"
    }

    selected_template = st.selectbox("Choose a Message Template", options=list(message_templates.keys()))
    message_preview = message_templates[selected_template]
    st.text_area("Message Preview", value=message_preview, height=100, disabled=True)

    if 'edited_df' in locals() and not edited_df.empty:
        selected_guests = edited_df[edited_df['Select']]
        num_selected = len(selected_guests)
        if not selected_guests.empty:
            button_label = f"Send SMS to {num_selected} Guest{'s' if num_selected != 1 else ''}"
            if st.button(button_label):
                openphone_url = "https://api.openphone.com/v1/messages"
                headers = {
                    "Authorization": "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7",
                    "Content-Type": "application/json"
                }
                sender_phone_number = "+18438972426"  # Your OpenPhone number
                for idx, row in selected_guests.iterrows():
                    recipient_phone = "+14075206507"  # Hard-coded test number
                    payload = {
                        "content": message_preview,
                        "from": sender_phone_number,
                        "to": [recipient_phone]
                    }

                    response = requests.post(openphone_url, json=payload, headers=headers)

                    if response.status_code == 202:
                        st.success(f"Message sent to {row['Guest Name']} ({recipient_phone})")
                    else:
                        st.error(f"Failed to send message to {row['Guest Name']} ({recipient_phone})")
                        st.write("Response Status Code:", response.status_code)
                        st.write("Response Body:", response.json())
                        st.write(headers)

                    time.sleep(0.2)
        else:
            st.info("No guests selected to send SMS.")
    else:
        st.info("No guest data available to send SMS.")

# Tour Prediction Tab
with tab3:
    st.title("🔮 Tour Prediction Dashboard")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date for Tour Prediction", value=pd.to_datetime(df['Arrival Date Short']).min().date())
    with col2:
        end_date = st.date_input("End Date for Tour Prediction", value=pd.to_datetime(df['Arrival Date Short']).max().date())

    all_resorts_tour_data = []
    for resort in df['Market'].unique():
        resort_df = df[df['Market'] == resort].copy()
        resort_df['Arrival Date Short'] = pd.to_datetime(resort_df['Arrival Date Short'])
        filtered_resort_df = resort_df[(resort_df['Arrival Date Short'].dt.date >= start_date) & 
                                       (resort_df['Arrival Date Short'].dt.date <= end_date)]
        
        daily_arrivals = filtered_resort_df.groupby(filtered_resort_df['Arrival Date Short'].dt.date).size().reset_index()
        daily_arrivals.columns = ['Date', 'Arrivals']
        
        st.subheader(f"{resort}")
        conversion_rate = st.number_input(f"Conversion Rate for {resort} (%)", min_value=0.0, max_value=100.0, value=10.0, step=0.5, key=f"conversion_{resort}") / 100
        daily_arrivals['Tours'] = daily_arrivals['Arrivals'].apply(lambda a: math.floor(a * conversion_rate))
        st.dataframe(daily_arrivals)
        all_resorts_tour_data.append(daily_arrivals.assign(Market=resort))

    full_summary_df = pd.concat(all_resorts_tour_data)
    st.markdown("---")
    st.subheader("Overall Tour Summary Across All Resorts")

    overall_summary = full_summary_df.groupby('Date').sum().reset_index()
    st.dataframe(overall_summary)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Arrivals for All Resorts", overall_summary['Arrivals'].sum())
    with col2:
        st.metric("Total Estimated Tours for All Resorts", overall_summary['Tours'].sum())

with st.expander("Show Raw Data"):
    st.dataframe(df)
