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

def format_phone_number(phone_number):
    """Format phone number to E.164 format."""
    try:
        parsed = phonenumbers.parse(phone_number, "US")
        if phonenumbers.is_valid_number(parsed):
            return f"+{parsed.country_code}{parsed.national_number}"
    except Exception as e:
        st.error(f"Error parsing phone number: {e}")
    return None

def rate_limited_request(url, headers, params):
    """Make API request with rate limiting."""
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 429:  # Rate limited
            time.sleep(1)  # Wait and retry
            return rate_limited_request(url, headers, params)
        return response.json()
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None

def fetch_call_history(phone_number):
    """Fetch call history for a given external phone number."""
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        return []

    url = "https://api.openphone.com/v1/calls"
    params = {
        "participants": [formatted_phone],
        "maxResults": 50
    }
    
    st.write(f"Making API call to {url} with params: {params}")
    response = requests.get(url, headers=HEADERS, params=params)
    
    if response.status_code != 200:
        st.write(f"API Error: {response.status_code}")
        st.write(f"Response: {response.text}")
        st.write(f"\nFailed to fetch call history for {formatted_phone}.")
        return []

    data = response.json()
    return data.get("data", [])

def fetch_message_history(phone_number):
    """Fetch message history for a given external phone number."""
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        return []

    url = "https://api.openphone.com/v1/messages"
    params = {
        "participants": [formatted_phone],
        "maxResults": 50
    }
    
    st.write(f"Making API call to {url} with params: {params}")
    response = requests.get(url, headers=HEADERS, params=params)
    
    if response.status_code != 200:
        st.write(f"API Error: {response.status_code}")
        st.write(f"Response: {response.text}")
        st.write(f"\nFailed to fetch message history for {formatted_phone}.")
        return []

    data = response.json()
    return data.get("data", [])

def display_history(phone_number):
    """Display call and message history."""
    st.title("Communication History Viewer")
    st.write(f"Retrieved Phone Number: {phone_number}")
    st.write(f"\nCommunication History for {format_phone_number(phone_number)}")

    # Fetch both call and message history
    call_history = fetch_call_history(phone_number)
    message_history = fetch_message_history(phone_number)

    # Display Calls
    st.header("Call History")
    if call_history:
        for call in call_history:
            # Debug the call data structure
            st.write("Call Data:", call)  # This will help us see the actual structure
            
            try:
                call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                with st.expander(f"Call on {call_time}"):
                    st.write(f"**Direction**: {call.get('direction', 'unknown')}")
                    st.write(f"**Duration**: {call.get('duration', 'unknown')} seconds")
                    st.write(f"**Status**: {call.get('status', 'unknown')}")
                    if 'participants' in call:
                        st.write(f"**Participants**: {', '.join(call['participants'])}")
                    st.write("---")
            except Exception as e:
                st.error(f"Error displaying call: {e}")
    else:
        st.write("No call history found for this number.")

    # Display Messages
    st.header("Message History")
    if message_history:
        for message in message_history:
            try:
                message_time = datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')
                with st.expander(f"Message on {message_time}"):
                    st.write(f"**Content**: {message.get('content', 'No content')}")
                    st.write(f"**Direction**: {message.get('direction', 'unknown')}")
                    st.write(f"**Status**: {message.get('status', 'unknown')}")
                    if 'attachments' in message and message['attachments']:
                        st.write("**Attachments**: Yes")
                        for attachment in message['attachments']:
                            st.write(f"- {attachment.get('url', 'No URL')}")
                    st.write("---")
            except Exception as e:
                st.error(f"Error displaying message: {e}")
    else:
        st.write("No message history found for this number.")

def main():
    """Main function to run the Streamlit app."""
    st.set_page_config(page_title="Communication History Viewer", page_icon="📱")
    
    # Input for phone number
    phone_number = st.text_input("Enter phone number to search:", value="4075206507")
    
    if phone_number:
        display_history(phone_number)

if __name__ == "__main__":
    main()
