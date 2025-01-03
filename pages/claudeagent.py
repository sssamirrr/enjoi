import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime

# Constants
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
BASE_URL = "https://api.openphone.com/v1"

def get_headers():
    return {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }

def make_request(url, params=None):
    """Make API request with rate limiting"""
    time.sleep(0.2)  # Rate limit: 5 requests per second
    try:
        response = requests.get(url, headers=get_headers(), params=params)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            st.error(f"Response: {response.text}")
    except Exception as e:
        st.error(f"Request failed: {e}")
    return None

def get_phone_numbers():
    """Get list of phone numbers"""
    response = make_request(f"{BASE_URL}/phone-numbers")
    if response and "data" in response:
        return response["data"]
    return []

def get_all_calls(phone_number_id):
    """Get all calls for a phone number"""
    all_calls = []
    next_page = None
    
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 100,
            "participants": []  # Empty array to get all calls
        }
        if next_page:
            params["pageToken"] = next_page
            
        response = make_request(f"{BASE_URL}/calls", params)
        if not response or "data" not in response:
            break
            
        all_calls.extend(response["data"])
        next_page = response.get("nextPageToken")
        
        if not next_page:
            break
            
    return all_calls

def format_phone_number(number):
    """Format phone number for display"""
    if not number:
        return "Unknown"
    clean_number = ''.join(filter(str.isdigit, str(number)))
    if len(clean_number) == 10:
        return f"({clean_number[:3]}) {clean_number[3:6]}-{clean_number[6:]}"
    return number

def format_duration(seconds):
    """Format duration in seconds to minutes and seconds"""
    if not seconds:
        return "0:00"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}:{remaining_seconds:02d}"

def main():
    st.title("OpenPhone Call History")
    
    # Get phone numbers
    phone_numbers = get_phone_numbers()
    
    if not phone_numbers:
        st.error("No phone numbers found. Please check your API key.")
        return
    
    # Debug: Print raw phone numbers data
    st.write("DEBUG - Phone Numbers Data:", phone_numbers)
        
    # Create dropdown for phone number selection
    phone_options = {}
    for pn in phone_numbers:
        # Try different possible fields for phone number
        number = pn.get("phoneNumber") or pn.get("number") or pn.get("e164")
        if number and pn.get("id"):
            phone_options[number] = pn["id"]
    
    if not phone_options:
        st.error("No valid phone numbers found in the response.")
        return
        
    selected_number = st.selectbox(
        "Select Phone Number",
        options=list(phone_options.keys()),
        format_func=format_phone_number
    )
    
    if selected_number:
        phone_id = phone_options[selected_number]
        
        # Get all calls
        with st.spinner("Loading calls..."):
            calls = get_all_calls(phone_id)
            
        if calls:
            # Process call data
            call_data = []
            for call in calls:
                # Get call details
                created_at = datetime.fromisoformat(call.get("createdAt", "").replace("Z", "+00:00"))
                
                # Get from/to numbers
                from_number = (call.get("from") or {}).get("phoneNumber", "Unknown")
                to_numbers = [to.get("phoneNumber", "Unknown") for to in (call.get("to") or [])]
                to_number = to_numbers[0] if to_numbers else "Unknown"
                
                call_data.append({
                    "Date": created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "From": format_phone_number(from_number),
                    "To": format_phone_number(to_number),
                    "Direction": call.get("direction", "Unknown"),
                    "Duration": format_duration(call.get("duration", 0)),
                    "Status": call.get("status", "Unknown"),
                    "Recording": "Yes" if call.get("recording") else "No"
                })
            
            # Create DataFrame
            df = pd.DataFrame(call_data)
            
            # Display stats
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Calls", len(calls))
            with col2:
                incoming = len([c for c in calls if c.get("direction") == "incoming"])
                st.metric("Incoming Calls", incoming)
            with col3:
                outgoing = len([c for c in calls if c.get("direction") == "outgoing"])
                st.metric("Outgoing Calls", outgoing)
            
            # Display calls
            st.dataframe(df)
            
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

if __name__ == "__main__":
    main()
