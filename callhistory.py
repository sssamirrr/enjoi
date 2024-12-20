# callhistory.py
import streamlit as st
import requests
from datetime import datetime

OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

# Fetch Call History
def fetch_call_history(phone_number):
    url = "https://api.openphone.com/v1/calls"
    params = {"participants": [phone_number], "maxResults": 50}
    response = requests.get(url, headers=HEADERS, params=params)
    if response.status_code == 200:
        return response.json().get('data', [])
    else:
        st.error(f"Error fetching call history: {response.status_code}")
        return []

# Main Call History Page
def run_call_history_page():
    st.title("Call History")
    phone_number = st.experimental_get_query_params().get("phone", [None])[0]
    if not phone_number:
        st.error("No phone number provided!")
        return

    st.subheader(f"Call History for {phone_number}")
    call_data = fetch_call_history(phone_number)
    if call_data:
        st.write(f"Total calls: {len(call_data)}")
        for call in call_data:
            st.write(f"Call Time: {datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00'))}")
            st.write(f"Duration: {call['duration']} seconds")
            st.write(f"Type: {call['type']}")
            st.write("---")
    else:
        st.warning("No call history found.")

if __name__ == "__main__":
    run_call_history_page()
