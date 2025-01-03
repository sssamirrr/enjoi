import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode

OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

def rate_limited_request(url, headers, params=None, request_type='get'):
    if params is None:
        params = {}
    
    time.sleep(1/5)
    try:
        if request_type.lower() == 'get':
            resp = requests.get(url, headers=headers, params=params)
            st.write("DEBUG Request URL:", resp.url)
        else:
            resp = None

        if resp and resp.status_code == 200:
            return resp.json()
        else:
            st.warning(f"API Error: {resp.status_code}")
            st.warning(f"Response: {resp.text}")
    except Exception as e:
        st.warning(f"Exception: {e}")
    return None

def get_headers():
    return {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }

def fetch_all_calls(phone_number_id):
    """
    Fetch all calls for a phone number
    """
    if not phone_number_id or not phone_number_id.startswith("PN"):
        return []

    calls_url = "https://api.openphone.com/v1/calls"
    all_calls = []
    fetched = 0
    next_page = None

    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
            
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request(calls_url, get_headers(), params)
        if not data or "data" not in data:
            break

        chunk = data["data"]
        all_calls.extend(chunk)
        fetched += len(chunk)

        next_page = data.get("nextPageToken")
        if not next_page or fetched >= 1000:  # Limit to 1000 calls
            break

    return all_calls

def format_duration(seconds):
    if not seconds:
        return "N/A"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}m {remaining_seconds}s"

def format_phone_number(number):
    if not number:
        return "Unknown"
    clean_number = ''.join(filter(str.isdigit, str(number)))
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    elif len(clean_number) == 11:
        return f"+{clean_number[0]} ({clean_number[1:4]}) {clean_number[4:7]}-{clean_number[7:]}"
    return str(number)

def get_call_details(call):
    from_number = "Unknown"
    to_number = "Unknown"
    
    # Handle 'from' field
    from_data = call.get("from", {})
    if isinstance(from_data, dict):
        from_number = from_data.get("phoneNumber", "Unknown")
    elif isinstance(from_data, str):
        from_number = from_data

    # Handle 'to' field
    to_data = call.get("to", [])
    if isinstance(to_data, list) and to_data:
        if isinstance(to_data[0], dict):
            to_number = to_data[0].get("phoneNumber", "Unknown")
        elif isinstance(to_data[0], str):
            to_number = to_data[0]
    elif isinstance(to_data, str):
        to_number = to_data

    return {
        "Date": pd.to_datetime(call.get("createdAt", "")).strftime("%Y-%m-%d %H:%M:%S"),
        "From": format_phone_number(from_number),
        "To": format_phone_number(to_number),
        "Direction": call.get("direction", "Unknown"),
        "Status": call.get("status", "Unknown"),
        "Duration": format_duration(call.get("duration")),
        "Recording": "Yes" if call.get("recording") else "No"
    }

def main():
    st.set_page_config(page_title="OpenPhone Call History", layout="wide")
    st.title("OpenPhone Call History")

    # Get phone numbers
    with st.spinner("Loading phone numbers..."):
        url = "https://api.openphone.com/v1/phone-numbers"
        response = rate_limited_request(url, get_headers())
        
        if not response or "data" not in response:
            st.error("Failed to load phone numbers. Please check your API key.")
            return

        # Debug output
        st.write("DEBUG: Phone Numbers Response:", response)
            
        # Safely extract phone numbers
        phone_numbers = []
        for pn in response.get("data", []):
            phone_id = pn.get("id")
            phone_num = None
            
            # Try different possible fields for phone number
            if "phoneNumber" in pn:
                phone_num = pn["phoneNumber"]
            elif "number" in pn:
                phone_num = pn["number"]
            elif "e164" in pn:
                phone_num = pn["e164"]
                
            if phone_id and phone_num:
                phone_numbers.append((phone_id, phone_num))

    # Phone number selector
    if phone_numbers:
        st.write(f"Found {len(phone_numbers)} phone numbers")
        selected_number = st.selectbox(
            "Select Phone Number",
            options=[pn[1] for pn in phone_numbers],
            format_func=lambda x: format_phone_number(x)
        )
        
        phone_id = next((pn[0] for pn in phone_numbers if pn[1] == selected_number), None)
        
        if phone_id:
            with st.spinner("Loading call history..."):
                calls = fetch_all_calls(phone_id)
                
                if calls:
                    # Convert calls to DataFrame
                    calls_data = [get_call_details(call) for call in calls]
                    df = pd.DataFrame(calls_data)
                    
                    # Display stats
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total Calls", len(calls))
                    with col2:
                        st.metric("Incoming Calls", len(df[df['Direction'] == 'incoming']))
                    with col3:
                        st.metric("Outgoing Calls", len(df[df['Direction'] == 'outgoing']))
                    with col4:
                        st.metric("Recorded Calls", len(df[df['Recording'] == 'Yes']))
                    
                    # Display calls
                    st.dataframe(df, use_container_width=True)
                    
                    # Export option
                    csv = df.to_csv(index=False)
                    st.download_button(
                        "Download Call History",
                        csv,
                        "call_history.csv",
                        "text/csv",
                        key='download-csv'
                    )
                else:
                    st.info("No calls found for this number.")
        else:
            st.error("Failed to identify phone number ID.")
    else:
        st.error("No phone numbers found in your account.")

if __name__ == "__main__":
    main()
