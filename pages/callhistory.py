import streamlit as st
import requests
import time
from datetime import datetime
import phonenumbers

# OpenPhone API Credentials
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

# Helper: Format phone number to E.164
def format_phone_number(phone):
    """
    Format a phone number to E.164 format.
    """
    try:
        parsed_phone = phonenumbers.parse(phone, "US")  # Default to US region
        if phonenumbers.is_valid_number(parsed_phone):
            return phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
        else:
            return None
    except phonenumbers.NumberParseException:
        return None

# Helper: Make API requests with rate limiting
def rate_limited_request(url, headers, params, request_type='get'):
    """
    Make an API request while respecting rate limits.
    """
    time.sleep(1 / 5)  # 5 requests per second max
    try:
        st.write(f"Making API call to {url} with params: {params}")
        response = requests.get(url, headers=headers, params=params) if request_type == 'get' else None
        if response and response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error: {response.status_code}")
            st.warning(f"Response: {response.text}")
    except Exception as e:
        st.warning(f"Exception during request: {str(e)}")
    return None

# Fetch call history
def fetch_call_history(phone_number):
    """
    Fetch call history for a given phone number using OpenPhone API.
    """
    # Step 1: Retrieve all phone numbers and match the phoneNumberId
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    phone_numbers_data = rate_limited_request(phone_numbers_url, HEADERS, {})
    if not phone_numbers_data or "data" not in phone_numbers_data:
        st.error("Failed to retrieve phone numbers.")
        return []

    # Match phone number with phoneNumberId
    formatted_phone = format_phone_number(phone_number)
    phone_number_id = None
    for pn in phone_numbers_data["data"]:
        if pn.get("e164") == formatted_phone:
            phone_number_id = pn.get("id")
            break

    if not phone_number_id:
        st.error(f"No matching phoneNumberId found for {formatted_phone}.")
        return []

    # Step 2: Fetch calls for the matched phoneNumberId
    calls_url = "https://api.openphone.com/v1/calls"
    params = {"phoneNumberId": phone_number_id, "participants": [formatted_phone], "maxResults": 50}
    calls_data = rate_limited_request(calls_url, HEADERS, params)

    if not calls_data or "data" not in calls_data:
        st.error(f"Failed to fetch call history for {formatted_phone}.")
        return []

    # Process call history data
    call_history = calls_data["data"]
    return call_history

# Display call history
def display_call_history(phone_number):
    """
    Display call history for the provided phone number.
    """
    st.title("Call History Viewer")

    # Format and validate the phone number
    st.write(f"Retrieved Phone Number: {phone_number}")
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        st.error(f"Invalid phone number: {phone_number}. Please provide a valid E.164 format number.")
        return

    st.subheader(f"Call History for {formatted_phone}")
    call_history = fetch_call_history(phone_number)

    if not call_history:
        st.warning("No call history found for this number.")
        return

    # Display Call Statistics
    total_calls = len(call_history)
    total_duration = sum(call.get("duration", 0) for call in call_history)
    average_duration = total_duration / total_calls if total_calls > 0 else 0

    st.metric("Total Calls", total_calls)
    st.metric("Total Duration (seconds)", total_duration)
    st.metric("Average Call Duration (seconds)", round(average_duration, 2))

    # Display Call Details
    st.subheader("Call Details")
    for call in call_history:
        with st.expander(f"Call on {datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')}"):
            st.write(f"**Type**: {call['type']}")
            st.write(f"**Duration**: {call['duration']} seconds")
            st.write(f"**Participants**: {', '.join(call['participants'])}")
            st.write(f"**Direction**: {call.get('direction', 'unknown')}")
            st.write(f"**Status**: {call.get('status', 'unknown')}")
            st.write("---")

# Main function to run the app
def run_call_history_page():
    """
    Run the Streamlit app for call history viewer.
    """
    st.set_page_config(page_title="Call History Viewer", layout="wide")
    phone_number = st.query_params.get("phone", [None])[0]


    if not phone_number:
        st.error("No phone number provided!")
        return

    display_call_history(phone_number)

# Entry point
if __name__ == "__main__":
    run_call_history_page()
