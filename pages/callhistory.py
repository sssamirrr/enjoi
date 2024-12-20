import streamlit as st
import requests
import time
from datetime import datetime
import phonenumbers

# OpenPhone API Configuration

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
        
        if response.status_code != 200:
            st.write(f"API Error: {response.status_code}")
            st.write(f"Response: {response.text}")
            return None
            
        return response.json()
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None

def fetch_call_and_message_history(phone_number):
    """
    Fetch both call and message history for a given external phone number across all OpenPhone numbers.
    """
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        return [], []

    # Step 1: Get all OpenPhone numbers
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    phone_numbers_data = rate_limited_request(phone_numbers_url, HEADERS, {})
    
    if not phone_numbers_data or "data" not in phone_numbers_data:
        st.error("Failed to retrieve OpenPhone numbers.")
        return [], []

    all_calls = []
    all_messages = []

    # Step 2: Search for calls and messages across all OpenPhone numbers
    for op_number in phone_numbers_data["data"]:
        phone_number_id = op_number.get("id")
        if not phone_number_id:
            continue

        # Fetch calls
        calls_url = "https://api.openphone.com/v1/calls"
        calls_params = {
            "phoneNumberId": phone_number_id,
            "participants": [formatted_phone],
            "maxResults": 50
        }
        
        calls_data = rate_limited_request(calls_url, HEADERS, calls_params)
        if calls_data and "data" in calls_data:
            all_calls.extend(calls_data["data"])

        # Fetch messages
        messages_url = "https://api.openphone.com/v1/messages"
        messages_params = {
            "phoneNumberId": phone_number_id,
            "participants": [formatted_phone],
            "maxResults": 50
        }
        
        messages_data = rate_limited_request(messages_url, HEADERS, messages_params)
        if messages_data and "data" in messages_data:
            all_messages.extend(messages_data["data"])

    # Sort both calls and messages by creation date
    all_calls.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
    all_messages.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
    
    return all_calls, all_messages

def display_history(phone_number):
    """Display call and message history."""
    st.title("Communication History Viewer")
    st.write(f"Retrieved Phone Number: {phone_number}")
    st.write(f"\nCommunication History for {format_phone_number(phone_number)}")

    call_history, message_history = fetch_call_and_message_history(phone_number)

    # Display Calls
    st.header("Call History")
    if call_history:
        for call in call_history:
            with st.expander(f"Call on {datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')}"):
                st.write(f"**Type**: {call['type']}")
                st.write(f"**Duration**: {call['duration']} seconds")
                st.write(f"**OpenPhone Number**: {call.get('phoneNumber', 'unknown')}")
                st.write(f"**Participants**: {', '.join(call['participants'])}")
                st.write(f"**Direction**: {call.get('direction', 'unknown')}")
                st.write(f"**Status**: {call.get('status', 'unknown')}")
                st.write("---")
    else:
        st.write("No call history found for this number.")

    # Display Messages
    st.header("Message History")
    if message_history:
        for message in message_history:
            with st.expander(f"Message on {datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M:%S')}"):
                st.write(f"**Type**: {message.get('type', 'unknown')}")
                st.write(f"**Content**: {message.get('content', 'No content')}")
                st.write(f"**OpenPhone Number**: {message.get('phoneNumber', 'unknown')}")
                st.write(f"**Direction**: {message.get('direction', 'unknown')}")
                st.write(f"**Status**: {message.get('status', 'unknown')}")
                if 'attachments' in message and message['attachments']:
                    st.write("**Attachments**: Yes")
                    for attachment in message['attachments']:
                        st.write(f"- {attachment.get('url', 'No URL')}")
                st.write("---")
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
