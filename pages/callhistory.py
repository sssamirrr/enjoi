import streamlit as st
import requests
from datetime import datetime
import phonenumbers

OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": f"Bearer {OPENPHONE_API_KEY}",
    "Content-Type": "application/json"
}

# Function to validate and format phone number to E.164
def format_phone_number(phone):
    try:
        parsed_phone = phonenumbers.parse(phone, "US")  # Assuming "US" as default region
        if phonenumbers.is_valid_number(parsed_phone):
            return phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
        else:
            return None
    except phonenumbers.NumberParseException:
        return None

# Fetch Call History from OpenPhone API
def fetch_call_history(phone_number):
    # Format the phone number to E.164 format
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        st.error(f"Invalid phone number: {phone_number}. Please provide a valid E.164 format number.")
        return []

    calls_url = "https://api.openphone.com/v1/calls"
    params = {"participants": [formatted_phone], "maxResults": 50}
    st.write(f"Formatted Phone: {formatted_phone}")  # Debugging
    st.write(f"API Request Params: {params}")       # Debugging

    try:
        response = requests.get(calls_url, headers=HEADERS, params=params)
        if response.status_code == 200:
            return response.json().get("data", [])
        else:
            st.error(f"Failed to fetch call history: {response.status_code}")
            st.write(f"API Response: {response.text}")  # Debugging
            return []
    except Exception as e:
        st.error(f"Error fetching call history: {str(e)}")
        return []

# Main function to display call history page
def run_call_history_page():
    st.title("Call History Viewer")

    # Retrieve the phone number from query parameters
    phone_number = st.query_params.get("phone", [None])[0]
    st.write(f"Retrieved Phone Number: {phone_number}")  # Debugging

    if not phone_number:
        st.error("No phone number provided!")
        return

    st.subheader(f"Call History for {phone_number}")
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
            st.write("---")

# Entry point for the script
if __name__ == "__main__":
    st.set_page_config(page_title="Call History Viewer", layout="wide")
    run_call_history_page()
