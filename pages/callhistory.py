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

def create_phone_name_map():
    numbers = get_openphone_numbers()
    phone_name_map = {}
    for num in numbers:
        phone_num = num.get('phoneNumber', '')
        name = num.get('name', '')
        if phone_num:
            phone_name_map[phone_num] = name if name else phone_num
    return phone_name_map

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
                "maxResults": 100
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
            time_diff = (sorted_comms[i]['time'] - sorted_comms[i-1]['time']).total_seconds() / 60
            response_times.append(time_diff)
    
    return response_times

def display_metrics(calls, messages):
    st.header("📊 Communication Metrics")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_calls = len(calls)
    total_messages = len(messages)
    inbound_calls = [c for c in calls if c.get('direction') == 'inbound']
    outbound_calls = [c for c in calls if c.get('direction') == 'outbound']
    inbound_voicemails = [c for c in inbound_calls if c.get('status') == 'voicemail']
    
    with col1:
        st.metric("Total Calls", total_calls)
    with col2:
        st.metric("Total Messages", total_messages)
    with col3:
        st.metric("Inbound Calls", len(inbound_calls))
    with col4:
        st.metric("Outbound Calls", len(outbound_calls))
    with col5:
        st.metric("Inbound Voicemails", len(inbound_voicemails))

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

    st.subheader("💬 Message Analytics")
    message_lengths = [len(m.get('content', '')) for m in messages if m.get('content')]
    if message_lengths:
        avg_length = sum(message_lengths) / len(message_lengths)
        st.metric("Average Message Length (characters)", f"{avg_length:.1f}")

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

def fetch_call_transcript(call_id):
    url = f"https://api.openphone.com/v1/call-transcripts/{call_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("data", {})
    return None

def display_timeline(calls, messages):
    st.header("📅 Communication Timeline")

    phone_name_map = create_phone_name_map()

    def get_display_name(phone_num):
        return phone_name_map.get(phone_num, phone_num)

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
            'status': message.get('status', 'unknown'),
        })
    
    communications.sort(key=lambda x: x['time'], reverse=True)
    
    for comm in communications:
        time_str = comm['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if comm['type'] == "Call" else "💬"
        direction_icon = "⬅️" if comm['direction'] == "inbound" else "➡️"
        
        with st.expander(f"{icon} {direction_icon} {time_str}"):
            if comm['type'] == "Call":
                from_name = get_display_name(comm['from'])
                to_name = get_display_name(comm['to'])
                st.write(f"**Who Called:** {from_name} to {to_name}")
                st.write(f"**Duration:** {comm['duration']} seconds")
                
                transcript_data = fetch_call_transcript(comm['id'])
                if transcript_data and transcript_data.get('dialogue'):
                    # Show summary by default
                    all_contents = " ".join([seg.get('content', '') for seg in transcript_data['dialogue']])
                    summary = all_contents[:200] + ("..." if len(all_contents) > 200 else "")
                    st.write("**Transcript Summary:**")
                    st.write(summary)

                    # Create a row of buttons
                    col_show, col_copy = st.columns(2)
                    show_full = col_show.button("Show Full Transcript", key=f"full_transcript_{comm['id']}")
                    copy_button = col_copy.button("Copy Transcript", key=f"copy_transcript_{comm['id']}")

                    full_transcript_text = "\n".join([f"{seg.get('identifier', 'Unknown')}: {seg.get('content', '')}" for seg in transcript_data['dialogue']])
                    
                    # If user clicks Show Full Transcript
                    if show_full:
                        st.write("**Full Transcript:**")
                        for seg in transcript_data['dialogue']:
                            speaker = seg.get('identifier', 'Unknown')
                            content = seg.get('content', '')
                            st.write(f"**{speaker}**: {content}")

                    # If user clicks Copy Transcript, display in a text area
                    if copy_button:
                        st.write("**Copy the transcript from below:**")
                        st.text_area("Transcript", full_transcript_text, height=300)
                else:
                    st.write("Transcript not available or in progress.")
            else:
                if comm['direction'] == 'inbound':
                    st.write("**Who Texted:** Guest texted")
                else:
                    st.write("**Who Texted:** We (Agent) texted")
                st.write(f"**Message:** {comm.get('content', 'No content')}")
            st.write(f"**Status:** {comm['status']}")

def display_history(phone_number):
    st.title(f"📱 Communication History for {phone_number}")
    
    with st.spinner('Fetching communication history...'):
        calls = fetch_call_history(phone_number)
        messages = fetch_message_history(phone_number)

    if not calls and not messages:
        st.warning("No communication history found for this number.")
        return

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

        st.subheader("All Call Transcripts")
        if st.button("Show All Transcripts"):
            for call in calls:
                st.write(f"**Call {call['id']} Transcript:**")
                transcript_data = fetch_call_transcript(call['id'])
                if transcript_data and transcript_data.get('dialogue'):
                    for seg in transcript_data['dialogue']:
                        speaker = seg.get('identifier', 'Unknown')
                        content = seg.get('content', '')
                        st.write(f"**{speaker}**: {content}")
                else:
                    st.write("No transcript available for this call.")

def main():
    st.set_page_config(
        page_title="Communication History",
        page_icon="📱",
        layout="wide"
    )

    # Get phone number from query params or user input
    query_params = st.query_params
    default_phone = query_params.get("phone", "")
    
    # Add a box at the top where the user can type another phone number
    phone_number = st.text_input("Enter another phone number:", value=default_phone)
    
    if phone_number:
        display_history(phone_number)
    else:
        st.error("Please provide a phone number.")
        
if __name__ == "__main__":
    main()
