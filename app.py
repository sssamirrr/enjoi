import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import gspread
from google.oauth2 import service_account
import math
import requests
import time

# Set page configuration
st.set_page_config(page_title="Hotel Reservations Dashboard", layout="wide")

# Add CSS for optional styling
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
    .stDataFrame {
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)

############################################
# OpenPhone Credentials
############################################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
OPENPHONE_NUMBER = "+18438972426"

############################################
# Connect to Google Sheets
############################################
@st.cache_resource
def get_google_sheet_data():
    try:
        service_account_info = st.secrets["gcp_service_account"]
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=[
                "https://www.googleapis.com/auth/spreadsheets.readonly",
                "https://www.googleapis.com/auth/drive.readonly"
            ]
        )
        gc = gspread.authorize(credentials)
        spreadsheet = gc.open_by_key(st.secrets["sheets"]["sheet_key"])
        worksheet = spreadsheet.get_worksheet(0)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {str(e)}")
        return None

# Load data from Google Sheets
df = get_google_sheet_data()
if df is None:
    st.error("Failed to load data. Please check your connection and credentials.")
    st.stop()

############################################
# OpenPhone API Functions
############################################
def rate_limited_request(url, headers, params):
    time.sleep(1 / 5)
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        st.warning(f"Request Error: {e}")
        return None

def get_all_phone_number_ids(headers):
    url = "https://api.openphone.com/v1/phone-numbers"
    response = rate_limited_request(url, headers, {})
    return [num.get('id') for num in response.get('data', [])] if response else []

def fetch_communication_info_batch(guest_df, headers, phone_number_id):
    participants = guest_df['Phone Number'].unique().tolist()
    params = {"phoneNumberId": phone_number_id, "participants": participants, "maxResults": 50}
    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    messages_response = rate_limited_request(messages_url, headers, params)
    calls_response = rate_limited_request(calls_url, headers, params)

    statuses, dates, durations, agents = {}, {}, {}, {}
    if messages_response and 'data' in messages_response:
        for message in messages_response['data']:
            phone = message.get('to', [{}])[0].get('phoneNumber', 'Unknown')
            statuses[phone] = "Message - " + message.get("direction", "unknown")
            dates[phone] = message.get('createdAt', None)
            agents[phone] = message.get("from", {}).get("phoneNumber", "Unknown")

    if calls_response and 'data' in calls_response:
        for call in calls_response['data']:
            phone = call.get('to', [{}])[0].get('phoneNumber', 'Unknown')
            statuses[phone] = "Call - " + call.get("direction", "unknown")
            dates[phone] = call.get('createdAt', None)
            duration = call.get('duration', 0)
            durations[phone] = f"{duration // 60}m {duration % 60}s"
            agents[phone] = call.get("from", {}).get("phoneNumber", "Unknown")

    guest_df['Communication Status'] = guest_df['Phone Number'].map(statuses)
    guest_df['Last Communication Date'] = guest_df['Phone Number'].map(dates)
    guest_df['Call Duration'] = guest_df['Phone Number'].map(durations)
    guest_df['Agent Phone Number'] = guest_df['Phone Number'].map(agents)
    return guest_df

############################################
# Create Tabs
############################################
tab1, tab2, tab3 = st.tabs(["Dashboard", "Marketing", "Tour Prediction"])

############################################
# Tab 1: Dashboard
############################################
with tab1:
    st.title("🏨 Hotel Reservations Dashboard")
    st.markdown("Real-time analysis of hotel reservations")

    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Reservations", len(df))
    with col2:
        average_nights = df['# Nights'].mean()
        st.metric("Average Nights", f"{average_nights:.1f}")
    with col3:
        total_room_nights = df['# Nights'].sum()
        st.metric("Total Room Nights", f"{total_room_nights:,.0f}")
    with col4:
        unique_guests = df['Name'].nunique()
        st.metric("Unique Guests", unique_guests)

    # Charts
    col1, col2 = st.columns(2)
    with col1:
        reservations_by_hotel = df.groupby('Market').size().reset_index(name='Reservations')
        reservations_by_hotel.rename(columns={'Market': 'Hotel'}, inplace=True)
        if not reservations_by_hotel.empty:
            fig_hotels = px.bar(reservations_by_hotel, x='Hotel', y='Reservations', title='Reservations by Hotel')
            st.plotly_chart(fig_hotels, use_container_width=True)
        else:
            st.warning("No reservation data available.")

    with col2:
        fig_los = px.histogram(df, x='# Nights', title='Length of Stay Distribution')
        st.plotly_chart(fig_los, use_container_width=True)

############################################
# Tab 2: Marketing
############################################
with tab2:
    st.title("📊 Marketing Information by Resort")
    selected_resort = st.selectbox(
        "Select Resort",
        options=sorted(df['Market'].unique()),
        help="Choose a resort to analyze marketing information"
    )

    resort_df = df[df['Market'] == selected_resort]
    if not resort_df.empty:
        resort_df = resort_df.copy()
        resort_df['Phone Number'] = resort_df['Phone Number'].astype(str).str.strip()

        display_df = resort_df[['Name', 'Arrival Date Short', 'Departure Date Short', 'Phone Number']].copy()
        display_df.columns = ['Guest Name', 'Check In', 'Check Out', 'Phone Number']

        headers = {"Authorization": OPENPHONE_API_KEY"}
        phone_number_id = get_all_phone_number_ids(headers)[0]

        enriched_df = fetch_communication_info_batch(display_df, headers, phone_number_id)
        enriched_df['Select'] = st.checkbox("Select All", value=False)
        st.dataframe(enriched_df)

        st.subheader("Message Templates")
        message_templates = {
            "Welcome Message": f"Welcome to {selected_resort}! Visit our concierge desk for your welcome gift! 🎁",
            "Check-in Follow-up": f"Hello! Hope you're enjoying your stay at {selected_resort}. Don't forget your welcome gift! 🎁",
            "Checkout Message": f"Thank you for staying with us at {selected_resort}! Collect your special gift before you leave! 🎁"
        }

        selected_template = st.selectbox("Choose a Message Template", list(message_templates.keys()))
        message_preview = message_templates[selected_template]
        st.text_area("Message Preview", value=message_preview, height=100, disabled=True)

        if st.button("Send SMS to Selected Guests"):
            selected_guests = enriched_df[enriched_df['Select']]
            if not selected_guests.empty:
                openphone_url = "https://api.openphone.com/v1/messages"
                headers_sms = {"Authorization": f"Bearer {OPENPHONE_API_KEY}", "Content-Type": "application/json"}

                for _, row in selected_guests.iterrows():
                    payload = {"content": message_preview, "from": OPENPHONE_NUMBER, "to": [row['Phone Number']]}
                    response = requests.post(openphone_url, json=payload, headers=headers_sms)
                    if response.status_code == 202:
                        st.success(f"Message sent to {row['Guest Name']} ({row['Phone Number']})")
                    else:
                        st.error(f"Failed to send message to {row['Guest Name']} ({row['Phone Number']})")
            else:
                st.warning("No guests selected.")
    else:
        st.warning("No data available for the selected resort.")

############################################
# Tab 3: Tour Prediction
############################################
with tab3:
    st.title("🔮 Tour Prediction Dashboard")
    start_date = st.date_input("Start Date", value=pd.to_datetime(df['Arrival Date Short']).min())
    end_date = st.date_input("End Date", value=pd.to_datetime(df['Arrival Date Short']).max())

    if start_date > end_date:
        st.error("Start date cannot be after the end date.")
    else:
        filtered_df = df[(pd.to_datetime(df['Arrival Date Short']) >= start_date) & 
                         (pd.to_datetime(df['Arrival Date Short']) <= end_date)]
        st.write(f"Total Arrivals: {len(filtered_df)}")
