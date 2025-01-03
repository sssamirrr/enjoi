import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime, timedelta
from urllib.parse import urlencode

############################
# 1) OpenPhone API Key     #
############################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

############################
# 2) Rate-limited request  #
############################
def rate_limited_request(url, headers, params=None, request_type='get'):
    """
    Makes a GET request with proper parameter formatting.
    """
    if params is None:
        params = {}
    
    time.sleep(1/5)
    try:
        if request_type.lower() == 'get':
            resp = requests.get(url, headers=headers, params=params)
            st.write("DEBUG Request URL:", resp.url)  # Debug the final URL
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

def get_date_range():
    """
    Returns date range for the last 3 months in ISO format
    """
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=90)
    return start_date.isoformat() + "Z", end_date.isoformat() + "Z"

##############################
# 3) Fetch Calls            #
##############################
def fetch_all_calls(phone_number_id, max_records=1000):
    """
    Fetch all calls for a phone number with date filtering
    """
    if not phone_number_id or not phone_number_id.startswith("PN"):
        return []

    calls_url = "https://api.openphone.com/v1/calls"
    all_calls = []
    fetched = 0
    next_page = None
    
    # Get date range for last 3 months
    start_date, end_date = get_date_range()

    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50,
            "createdAfter": start_date,
            "createdBefore": end_date
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
        if not next_page or fetched >= max_records:
            break

    return all_calls

##############################
# 4) Format Call Data        #
##############################
def format_duration(seconds):
    """Convert seconds to readable duration"""
    if not seconds:
        return "N/A"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}m {remaining_seconds}s"

def format_phone_number(number):
    """Format phone number for display"""
    if not number:
        return "Unknown"
    # Remove any formatting and keep just the numbers
    clean_number = ''.join(filter(str.isdigit, number))
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    elif len(clean_number) == 11:
        return f"+{clean_number[0]} ({clean_number[1:4]}) {clean_number[4:7]}-{clean_number[7:]}"
    return number

def get_call_details(call):
    """Extract relevant call details"""
    return {
        "Date": pd.to_datetime(call.get("createdAt")).strftime("%Y-%m-%d %H:%M:%S"),
        "From": format_phone_number(call.get("from", {}).get("phoneNumber", "Unknown")),
        "To": format_phone_number(call.get("to", [{}])[0].get("phoneNumber", "Unknown")),
        "Direction": call.get("direction", "Unknown"),
        "Status": call.get("status", "Unknown"),
        "Duration": format_duration(call.get("duration")),
        "Recording": "Yes" if call.get("recording") else "No"
    }

##############################
# 5) Main App               #
##############################
def main():
    st.set_page_config(page_title="OpenPhone Call History", layout="wide")
    st.title("OpenPhone Call History")

    # Get phone numbers first
    with st.spinner("Loading phone numbers..."):
        url = "https://api.openphone.com/v1/phone-numbers"
        response = rate_limited_request(url, get_headers())
        
        if not response or "data" not in response:
            st.error("Failed to load phone numbers. Please check your API key.")
            return
            
        phone_numbers = [(pn["id"], pn["phoneNumber"]) for pn in response["data"]]

    # Phone number selector
    if phone_numbers:
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
                    st.info("No calls found for this number in the last 3 months.")
        else:
            st.error("Failed to identify phone number ID.")
    else:
        st.error("No phone numbers found in your account.")

if __name__ == "__main__":
    main()
