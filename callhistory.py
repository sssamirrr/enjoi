import streamlit as st
import requests
from datetime import datetime
import phonenumbers
import pandas as pd

# OpenPhone API Credentials
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

def format_phone_number(phone_number):
    try:
        parsed = phonenumbers.parse(phone_number, "US")
        if phonenumbers.is_valid_number(parsed):
            return f"+{parsed.country_code}{parsed.national_number}"
    except Exception as e:
        st.error(f"Error parsing phone number: {e}")
    return None

def get_openphone_numbers():
    url = "https://api.openphone.com/v1/phone-numbers"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        st.error(f"Failed to fetch OpenPhone numbers: {response.text}")
        return []
    return response.json().get("data", [])

def fetch_call_history(phone_number):
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        return []
    
    all_calls = []
    for op_number in get_openphone_numbers():
        phone_number_id = op_number.get("id")
        if phone_number_id:
            url = "https://api.openphone.com/v1/calls"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [formatted_phone],
                "maxResults": 50
            }
            response = requests.get(url, headers=HEADERS, params=params)
            if response.status_code == 200:
                all_calls.extend(response.json().get("data", []))
    return all_calls

def fetch_message_history(phone_number):
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        return []
    
    all_messages = []
    for op_number in get_openphone_numbers():
        phone_number_id = op_number.get("id")
        if phone_number_id:
            url = "https://api.openphone.com/v1/messages"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [formatted_phone],
                "maxResults": 50
            }
            response = requests.get(url, headers=HEADERS, params=params)
            if response.status_code == 200:
                all_messages.extend(response.json().get("data", []))
    return all_messages

def display_quick_stats(calls, messages):
    st.header("Quick Statistics")
    col1, col2, col3, col4 = st.columns(4)
    
    inbound_calls = len([c for c in calls if c.get('direction') == 'inbound'])
    outbound_calls = len([c for c in calls if c.get('direction') == 'outbound'])
    inbound_messages = len([m for m in messages if m.get('direction') == 'inbound'])
    outbound_messages = len([m for m in messages if m.get('direction') == 'outbound'])
    
    with col1:
        st.metric("Inbound Calls", inbound_calls)
    with col2:
        st.metric("Outbound Calls", outbound_calls)
    with col3:
        st.metric("Inbound Messages", inbound_messages)
    with col4:
        st.metric("Outbound Messages", outbound_messages)

def display_timeline(calls, messages):
    # Combine and sort communications
    communications = []
    
    for call in calls:
        communications.append({
            'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction', 'unknown'),
            'duration': call.get('duration', 'N/A'),
            'status': call.get('status', 'unknown')
        })
    
    for message in messages:
        communications.append({
            'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction', 'unknown'),
            'content': message.get('content', 'No content'),
            'status': message.get('status', 'unknown')
        })
    
    # Sort by time
    communications.sort(key=lambda x: x['time'], reverse=True)
    
    # Display timeline
    st.header("Communication Timeline")
    for comm in communications:
        time_str = comm['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if comm['type'] == "Call" else "💬"
        direction_icon = "⬅️" if comm['direction'] == "inbound" else "➡️"
        
        with st.expander(f"{icon} {direction_icon} {time_str}"):
            if comm['type'] == "Call":
                st.write(f"**Duration:** {comm['duration']} seconds")
            else:
                st.write(f"**Message:** {comm['content']}")
            st.write(f"**Status:** {comm['status']}")

def display_history(phone_number):
    st.title("Communication History")
    st.write(f"Analysis for: {format_phone_number(phone_number)}")

    with st.spinner('Fetching data...'):
        calls = fetch_call_history(phone_number)
        messages = fetch_message_history(phone_number)

    display_quick_stats(calls, messages)
    
    tab1, tab2 = st.tabs(["📊 Timeline", "📋 Details"])
    
    with tab1:
        display_timeline(calls, messages)
    
    with tab2:
        st.header("Detailed History")
        show_calls = st.checkbox("Show Calls", True)
        show_messages = st.checkbox("Show Messages", True)
        
        if show_calls:
            st.subheader("Calls")
            for call in sorted(calls, key=lambda x: x['createdAt'], reverse=True):
                call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                st.write(f"**{call_time}** - {call.get('direction', 'unknown')} call ({call.get('duration', 'N/A')} seconds)")
        
        if show_messages:
            st.subheader("Messages")
            for message in sorted(messages, key=lambda x: x['createdAt'], reverse=True):
                message_time = datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                st.write(f"**{message_time}** - {message.get('direction', 'unknown')}: {message.get('content', 'No content')}")

def main():
    st.set_page_config(
        page_title="Communication History",
        page_icon="📱",
        layout="wide"
    )
    
    phone_number = st.text_input("Enter phone number to analyze:", value="4075206507")
    
    if phone_number:
        display_history(phone_number)

if __name__ == "__main__":
    main()
