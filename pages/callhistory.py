import streamlit as st
import requests
from datetime import datetime
import phonenumbers
import pandas as pd
from collections import Counter
import altair as alt

# OpenPhone API Credentials
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

def format_phone_number(phone_number):
    """
    Format and validate phone numbers with better error handling and user feedback.
    Returns tuple of (formatted_number, error_message)
    """
    if not phone_number:
        return None, "Please enter a phone number"
    
    # Remove any non-numeric characters except + sign
    cleaned_number = ''.join(c for c in phone_number if c.isdigit() or c == '+')
    
    # Add US country code if not present
    if not cleaned_number.startswith('+'):
        if cleaned_number.startswith('1'):
            cleaned_number = '+' + cleaned_number
        else:
            cleaned_number = '+1' + cleaned_number

    try:
        parsed = phonenumbers.parse(cleaned_number)
        if phonenumbers.is_valid_number(parsed):
            return f"+{parsed.country_code}{parsed.national_number}", None
        else:
            return None, "Invalid phone number format. Please enter a valid US phone number."
    except phonenumbers.NumberParseException as e:
        if len(cleaned_number) < 10:
            return None, "Phone number is too short. Please enter a complete phone number."
        elif len(cleaned_number) > 15:
            return None, "Phone number is too long. Please enter a valid phone number."
        else:
            return None, f"Invalid phone number format: {str(e)}"

def get_openphone_numbers():
    url = "https://api.openphone.com/v1/phone-numbers"
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        st.error(f"Failed to fetch OpenPhone numbers: {response.text}")
        return []
    return response.json().get("data", [])

def fetch_call_history(phone_number):
    formatted_phone, error = format_phone_number(phone_number)
    if error:
        st.error(error)
        return []
    
    all_calls = []
    for op_number in get_openphone_numbers():
        phone_number_id = op_number.get("id")
        if phone_number_id:
            url = "https://api.openphone.com/v1/calls"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [formatted_phone],
                "maxResults": 100
            }
            response = requests.get(url, headers=HEADERS, params=params)
            if response.status_code == 200:
                all_calls.extend(response.json().get("data", []))
    return all_calls

def fetch_message_history(phone_number):
    formatted_phone, error = format_phone_number(phone_number)
    if error:
        st.error(error)
        return []
    
    all_messages = []
    for op_number in get_openphone_numbers():
        phone_number_id = op_number.get("id")
        if phone_number_id:
            url = "https://api.openphone.com/v1/messages"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [formatted_phone],
                "maxResults": 100
            }
            response = requests.get(url, headers=HEADERS, params=params)
            if response.status_code == 200:
                all_messages.extend(response.json().get("data", []))
    return all_messages

def calculate_response_times(communications):
    response_times = []
    sorted_comms = sorted(communications, key=lambda x: x['time'])
    
    for i in range(1, len(sorted_comms)):
        if sorted_comms[i]['direction'] != sorted_comms[i-1]['direction']:
            time_diff = (sorted_comms[i]['time'] - sorted_comms[i-1]['time']).total_seconds() / 60  # in minutes
            response_times.append(time_diff)
    
    return response_times

def display_metrics(calls, messages):
    st.header("📊 Communication Metrics")
    
    # Basic Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_calls = len(calls)
    total_messages = len(messages)
    inbound_calls = len([c for c in calls if c.get('direction') == 'inbound'])
    outbound_calls = len([c for c in calls if c.get('direction') == 'outbound'])
    
    with col1:
        st.metric("Total Calls", total_calls)
    with col2:
        st.metric("Total Messages", total_messages)
    with col3:
        st.metric("Inbound Calls", inbound_calls)
    with col4:
        st.metric("Outbound Calls", outbound_calls)

    # Call Duration Metrics
    st.subheader("📞 Call Analytics")
    call_durations = [c.get('duration', 0) for c in calls if c.get('duration')]
    if call_durations:
        avg_duration = sum(call_durations) / len(call_durations)
        max_duration = max(call_durations)
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Average Call Duration (seconds)", f"{avg_duration:.1f}")
        with col2:
            st.metric("Longest Call (seconds)", max_duration)

    # Message Analytics
    st.subheader("💬 Message Analytics")
    message_lengths = [len(m.get('content', '')) for m in messages if m.get('content')]
    if message_lengths:
        avg_length = sum(message_lengths) / len(message_lengths)
        st.metric("Average Message Length (characters)", f"{avg_length:.1f}")

    # Response Time Analysis
    communications = []
    for call in calls:
        communications.append({
            'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction')
        })
    for message in messages:
        communications.append({
            'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction')
        })
    
    response_times = calculate_response_times(communications)
    if response_times:
        avg_response_time = sum(response_times) / len(response_times)
        st.metric("Average Response Time (minutes)", f"{avg_response_time:.1f}")

def display_timeline(calls, messages):
    st.header("📅 Communication Timeline")
    
    # Combine and sort communications
    communications = []
    
    for call in calls:
        from_number = call.get('from', {}).get('phoneNumber', 'Unknown')
        to_number = call.get('to', {}).get('phoneNumber', 'Unknown')
        
        communications.append({
            'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction', 'unknown'),
            'duration': call.get('duration', 'N/A'),
            'status': call.get('status', 'unknown'),
            'id': call.get('id'),
            'from': from_number,
            'to': to_number
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
    
    for comm in communications:
        time_str = comm['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if comm['type'] == "Call" else "💬"
        direction_icon = "⬅️" if comm['direction'] == "inbound" else "➡️"
        
        with st.expander(f"{icon} {direction_icon} {time_str}"):
            if comm['type'] == "Call":
                st.write(f"**Who Called:** {comm['from']} to {comm['to']}")
                st.write(f"**Duration:** {comm['duration']} seconds")
                st.write(f"[Transcript Link](https://api.openphone.com/v1/call-transcripts/{comm['id']})")
            else:
                st.write(f"**Message:** {comm['content']}")
            st.write(f"**Status:** {comm['status']}")

def display_history(phone_number):
    formatted_phone, error = format_phone_number(phone_number)
    if error:
        st.error(error)
        return

    st.title(f"📱 Communication History for {formatted_phone}")
    
    with st.spinner('Fetching communication history...'):
        calls = fetch_call_history(formatted_phone)
        messages = fetch_message_history(formatted_phone)

    if not calls and not messages:
        st.warning("No communication history found for this number.")
        return

    # Display all sections in tabs
    tab1, tab2, tab3 = st.tabs(["📊 Metrics", "📅 Timeline", "📋 Details"])
    
    with tab1:
        display_metrics(calls, messages)
    
    with tab2:
        display_timeline(calls, messages)
    
    with tab3:
        st.header("Detailed History")
        show_calls = st.checkbox("Show Calls", True)
        show_messages = st.checkbox("Show Messages", True)
        
        if show_calls:
            st.subheader("📞 Calls")
            for call in sorted(calls, key=lambda x: x['createdAt'], reverse=True):
                call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                direction = "Incoming" if call.get('direction') == 'inbound' else "Outgoing"
                st.write(f"**{call_time}** - {direction} call ({call.get('duration', 'N/A')} seconds)")
        
        if show_messages:
            st.subheader("💬 Messages")
            for message in sorted(messages, key=lambda x: x['createdAt'], reverse=True):
                message_time = datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                direction = "Received" if message.get('direction') == 'inbound' else "Sent"
                st.write(f"**{message_time}** - {direction}: {message.get('content', 'No content')}")

def main():
    st.set_page_config(
        page_title="Communication History",
        page_icon="📱",
        layout="wide"
    )

    # Get phone number from URL parameters
    query_params = st.query_params
    phone_param = query_params.get("phone", [""])[0]

    # Add a text input field for phone number
    phone_input = st.text_input(
        "Enter Phone Number",
        value=phone_param,
        help="Enter a US phone number (e.g., +1234567890 or 1234567890)"
    )

    if phone_input:
        formatted_phone, error_message = format_phone_number(phone_input)
        
        if error_message:
            st.error(error_message)
            st.info("""
            Please enter a valid US phone number in one of these formats:
            - +1XXXXXXXXXX
            - 1XXXXXXXXXX
            - XXXXXXXXXX (10 digits)
            """)
        else:
            # Update URL with formatted phone number
            if formatted_phone != phone_param:
                st.query_params["phone"] = formatted_phone
            
            # Display communication history
            display_history(formatted_phone)
    else:
        st.info("Please enter a phone number to view communication history")

if __name__ == "__main__":
    main()
