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
                "https://www.googleapis.com/auth/drive.readonly",
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


def rate_limited_request(url, headers, params, request_type="get"):
    time.sleep(1 / 5)  # 5 requests per second max
    try:
        response = (
            requests.get(url, headers=headers, params=params)
            if request_type == "get"
            else None
        )
        if response and response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception:
        return None


def get_all_phone_number_ids(headers):
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    response_data = rate_limited_request(phone_numbers_url, headers, {})
    return (
        [pn.get("id") for pn in response_data.get("data", [])] if response_data else []
    )


def get_last_communication_info(phone_number, headers):
    phone_number_ids = get_all_phone_number_ids(headers)
    if not phone_number_ids:
        return "No Communications", None

    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    latest_datetime = None
    latest_type = None
    latest_direction = None

    for phone_number_id in phone_number_ids:
        params = {
            "phoneNumberId": phone_number_id,
            "participants": [phone_number],
            "maxResults": 50,
        }
        messages_response = rate_limited_request(messages_url, headers, params)
        if messages_response and "data" in messages_response:
            for message in messages_response["data"]:
                msg_time = datetime.fromisoformat(
                    message["createdAt"].replace("Z", "+00:00")
                )
                if not latest_datetime or msg_time > latest_datetime:
                    latest_datetime = msg_time
                    latest_type = "Message"
                    latest_direction = message.get("direction", "unknown")

        calls_response = rate_limited_request(calls_url, headers, params)
        if calls_response and "data" in calls_response:
            for call in calls_response["data"]:
                call_time = datetime.fromisoformat(
                    call["createdAt"].replace("Z", "+00:00")
                )
                if not latest_datetime or call_time > latest_datetime:
                    latest_datetime = call_time
                    latest_type = "Call"
                    latest_direction = call.get("direction", "unknown")

    if not latest_datetime:
        return "No Communications", None

    return f"{latest_type} - {latest_direction}", latest_datetime.strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def fetch_communication_info(guest_df, headers):
    if "Phone Number" not in guest_df.columns:
        st.error("The column 'Phone Number' is missing in the DataFrame.")
        return ["No Status"] * len(guest_df), [None] * len(guest_df)

    guest_df["Phone Number"] = guest_df["Phone Number"].astype(str).str.strip()
    statuses = ["No Status"] * len(guest_df)
    dates = [None] * len(guest_df)

    for idx, row in guest_df.iterrows():
        phone = row["Phone Number"]
        if pd.notna(phone) and phone:
            try:
                status, last_date = get_last_communication_info(phone, headers)
                statuses[idx] = status
                dates[idx] = last_date
            except Exception:
                statuses[idx] = "Error"
                dates[idx] = None
        else:
            statuses[idx] = "Invalid Number"
            dates[idx] = None

    return statuses, dates


############################################
# Marketing Tab
############################################
st.title("📊 Marketing Information by Resort")

selected_resort = st.selectbox("Select Resort", options=sorted(df["Market"].unique()))
resort_df = df[df["Market"] == selected_resort].copy()
st.subheader(f"Guest Information for {selected_resort}")

resort_df["Check In"] = pd.to_datetime(resort_df["Arrival Date Short"], errors="coerce")
resort_df["Check Out"] = pd.to_datetime(
    resort_df["Departure Date Short"], errors="coerce"
)
resort_df = resort_df.dropna(subset=["Check In", "Check Out"])

display_df = resort_df[["Name", "Check In", "Check Out", "Phone Number"]].copy()
display_df.columns = ["Guest Name", "Check In", "Check Out", "Phone Number"]

display_df["Communication Status"] = None
display_df["Last Communication Date"] = None

headers = {"Authorization": OPENPHONE_API_KEY, "Content-Type": "application/json"}

if st.button("Load Status for All Numbers"):
    statuses, dates = fetch_communication_info(display_df, headers)
    display_df["Communication Status"] = statuses
    display_df["Last Communication Date"] = dates

for idx in range(len(display_df)):
    guest_name = display_df.iloc[idx]["Guest Name"]
    phone_number = display_df.iloc[idx]["Phone Number"]
    check_status_key = f"check_status_{idx}"
    if st.button(f"Check Status for {guest_name}", key=check_status_key):
        status, last_date = get_last_communication_info(phone_number, headers)
        display_df.at[idx, "Communication Status"] = status
        display_df.at[idx, "Last Communication Date"] = last_date

st.write(display_df)
