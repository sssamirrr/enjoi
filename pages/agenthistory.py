import streamlit as st
import pandas as pd
import time
import requests
from urllib.parse import urlencode

OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

def make_request(url, headers):
    """Basic request function with error handling"""
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.error(f"Request failed: {str(e)}")
        return None

def get_phone_numbers():
    """Fetch phone numbers from OpenPhone"""
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {
        "Authorization": OPENPHONE_API_KEY
    }
    
    response = make_request(url, headers)
    if response and "data" in response:
        return [{
            "phoneNumberId": item.get("id"),
            "phoneNumber": item.get("phoneNumber", "No Number")
        } for item in response["data"]]
    return []

def get_agent_history(phone_number_id):
    """Fetch call and message history"""
    headers = {
        "Authorization": OPENPHONE_API_KEY
    }
    
    # Get calls
    calls_url = f"https://api.openphone.com/v1/calls?phoneNumberId={phone_number_id}&maxResults=100"
    calls_response = make_request(calls_url, headers)
    calls_df = pd.DataFrame()
    if calls_response and "data" in calls_response:
        calls_df = pd.DataFrame(calls_response["data"])
    
    # Get messages
    messages_url = f"https://api.openphone.com/v1/messages?phoneNumberId={phone_number_id}&maxResults=100"
    messages_response = make_request(messages_url, headers)
    messages_df = pd.DataFrame()
    if messages_response and "data" in messages_response:
        messages_df = pd.DataFrame(messages_response["data"])
    
    return calls_df, messages_df

def main():
    st.title("OpenPhone History Viewer")
    
    if 'phone_number_id' not in st.session_state:
        st.session_state.phone_number_id = None
    
    # Get phone numbers
    phone_numbers = get_phone_numbers()
    
    if not phone_numbers:
        st.warning("No phone numbers found")
        return
    
    # Display phone numbers
    for phone in phone_numbers:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(phone["phoneNumber"])
        with col2:
            if st.button("View History", key=phone["phoneNumberId"]):
                st.session_state.phone_number_id = phone["phoneNumberId"]
                st.rerun()
    
    # Show history if phone number is selected
    if st.session_state.phone_number_id:
        calls_df, messages_df = get_agent_history(st.session_state.phone_number_id)
        
        st.header("Call History")
        if not calls_df.empty:
            st.dataframe(calls_df)
        else:
            st.info("No calls found")
            
        st.header("Message History")
        if not messages_df.empty:
            st.dataframe(messages_df)
        else:
            st.info("No messages found")

if __name__ == "__main__":
    main()
