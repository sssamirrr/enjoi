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

def get_openphone_numbers():
    """Get all OpenPhone numbers associated with the account."""
    url = "https://api.openphone.com/v1/phone-numbers"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code != 200:
        st.error(f"Failed to fetch OpenPhone numbers: {response.text}")
        return []
    
    data = response.json()
    return data.get("data", [])

def fetch_call_history(phone_number):
    """Fetch call history for a given external phone number."""
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        return []

    all_calls = []
    openphone_numbers = get_openphone_numbers()
    
    for op_number in openphone_numbers:
        phone_number_id = op_number.get("id")
        if not phone_number_id:
            continue

        url = "https://api.openphone.com/v1/calls"
        params = {
            "phoneNumberId": phone_number_id,
            "participants": [formatted_phone],
            "maxResults": 50
        }
        
        response = requests.get(url, headers=HEADERS, params=params)
        
        if response.status_code == 200:
            data = response.json()
            all_calls.extend(data.get("data", []))
        else:
            st.write(f"Error fetching calls for {phone_number_id}: {response.text}")

    return all_calls

def fetch_message_history(phone_number):
    """Fetch message history for a given external phone number."""
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        return []

    all_messages = []
    openphone_numbers = get_openphone_numbers()
    
    for op_number in openphone_numbers:
        phone_number_id = op_number.get("id")
        if not phone_number_id:
            continue

        url = "https://api.openphone.com/v1/messages"
        params = {
            "phoneNumberId": phone_number_id,
            "participants": [formatted_phone],
            "maxResults": 50
        }
        
        response = requests.get(url, headers=HEADERS, params=params)
        
        if response.status_code == 200:
            data = response.json()
            all_messages.extend(data.get("data", []))
        else:
            st.write(f"Error fetching messages for {phone_number_id}: {response.text}")

    return all_messages

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
        for call in sorted(call_history, key=lambda x: x['createdAt'], reverse=True):
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
        for message in sorted(message_history, key=lambda x: x['createdAt'], reverse=True):
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
