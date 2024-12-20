import streamlit as st
import requests
from datetime import datetime
import phonenumbers
import pandas as pd
from collections import Counter
import altair as alt
import urllib.parse

# OpenPhone API Credentials
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

def get_phone_from_url():
    """Extract phone number from URL parameters in different formats"""
    # Get the full URL path
    full_path = st.experimental_get_query_params()
    
    # Check for phone number in query parameters
    phone_param = full_path.get("phone", [""])[0]
    
    # If no phone found in query params, check the path
    if not phone_param and "callhistory" in str(full_path):
        try:
            path_parts = str(full_path).split("callhistory?phone=")
            if len(path_parts) > 1:
                phone_param = path_parts[1].split("&")[0]
        except:
            pass
    
    return phone_param

def format_phone_number(phone_number):
    """
    Format and validate phone numbers with better error handling and user feedback.
    Returns tuple of (formatted_number, error_message)
    """
    if not phone_number:
        return None, "Please enter a phone number"
    
    # Remove any non-numeric characters except + sign
    cleaned_number = ''.join(c for c in str(phone_number) if c.isdigit() or c == '+')
    
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
            time_diff = (sorted_comms[i]['time'] - sorted_comms[i-1]['time']).total_seconds() / 60
            response_times.append(time_diff)
    
    return response_times

def get_transcript_url(call_id):
    """Generate the correct transcript URL based on the current domain"""
    base_url = st.experimental_get_query_params()
    if "ldmcbiowzbdeqvmabvudyy.streamlit.app" in str(base_url):
        return f"https://ldmcbiowzbdeqvmabvudyy.streamlit.app/transcripts/{call_id}"
    return f"https://app.openphone.com/transcripts/{call_id}"

def get_agent_stats(calls, messages):
    """Calculate statistics for each agent's interactions"""
    agent_stats = {}
    
    # Process calls
    for call in calls:
        agent_number = call.get('to', {}).get('phoneNumber') if call.get('direction') == 'inbound' else call.get('from', {}).get('phoneNumber')
        if agent_number:
            if agent_number not in agent_stats:
                agent_stats[agent_number] = {
                    'calls_made': 0,
                    'calls_received': 0,
                    'messages_sent': 0,
                    'messages_received': 0,
                    'voicemail_endings': 0,
                    'total_call_duration': 0,
                    'transcripts': []
                }
            
            if call.get('direction') == 'outbound':
                agent_stats[agent_number]['calls_made'] += 1
            else:
                agent_stats[agent_number]['calls_received'] += 1
            
            if call.get('endReason') == 'voicemail':
                agent_stats[agent_number]['voicemail_endings'] += 1
            
            if call.get('duration'):
                agent_stats[agent_number]['total_call_duration'] += call.get('duration')
            
            if call.get('id'):
                agent_stats[agent_number]['transcripts'].append({
                    'id': call.get('id'),
                    'time': call.get('createdAt'),
                    'type': 'call'
                })
    
    # Process messages
    for message in messages:
        agent_number = message.get('to', {}).get('phoneNumber') if message.get('direction') == 'inbound' else message.get('from', {}).get('phoneNumber')
        if agent_number:
            if agent_number not in agent_stats:
                agent_stats[agent_number] = {
                    'calls_made': 0,
                    'calls_received': 0,
                    'messages_sent': 0,
                    'messages_received': 0,
                    'voicemail_endings': 0,
                    'total_call_duration': 0,
                    'transcripts': []
                }
            
            if message.get('direction') == 'outbound':
                agent_stats[agent_number]['messages_sent'] += 1
            else:
                agent_stats[agent_number]['messages_received'] += 1
    
    return agent_stats

def display_metrics(calls, messages):
    st.header("📊 Communication Metrics")
    
    # Basic Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    total_calls = len(calls)
    total_messages = len(messages)
    inbound_calls = len([c for c in calls if c.get('direction') == 'inbound'])
    outbound_calls = len([c for c in calls if c.get('direction') == 'outbound'])
    voicemail_endings = len([c for c in calls if c.get('endReason') == 'voicemail'])
    
    with col1:
        st.metric("Total Calls", total_calls)
    with col2:
        st.metric("Total Messages", total_messages)
    with col3:
        st.metric("Inbound Calls", inbound_calls)
    with col4:
        st.metric("Voicemail Endings", voicemail_endings)

    # Agent Statistics
    st.subheader("👤 Agent Activity")
    agent_stats = get_agent_stats(calls, messages)
    
    for agent_number, stats in agent_stats.items():
        with st.expander(f"Agent: {agent_number}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Calls Made", stats['calls_made'])
                st.metric("Messages Sent", stats['messages_sent'])
            with col2:
                st.metric("Calls Received", stats['calls_received'])
                st.metric("Messages Received", stats['messages_received'])
            with col3:
                st.metric("Voicemail Endings", stats['voicemail_endings'])
                avg_duration = stats['total_call_duration'] / (stats['calls_made'] + stats['calls_received']) if (stats['calls_made'] + stats['calls_received']) > 0 else 0
                st.metric("Avg Call Duration (s)", f"{avg_duration:.1f}")
            
            if stats['transcripts']:
                st.subheader("📝 Call Transcripts")
                for transcript in sorted(stats['transcripts'], key=lambda x: x['time'], reverse=True):
                    time_str = datetime.fromisoformat(transcript['time'].replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M")
                    transcript_url = get_transcript_url(transcript['id'])
                    st.write(f"[{time_str} - Call Transcript]({transcript_url})")

def display_timeline(calls, messages):
    st.header("📅 Communication Timeline")
    
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
            'to': to_number,
            'end_reason': call.get('endReason', 'unknown')
        })
    
    for message in messages:
        communications.append({
            'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction', 'unknown'),
            'content': message.get('content', 'No content'),
            'status': message.get('status', 'unknown'),
            'from': message.get('from', {}).get('phoneNumber', 'Unknown'),
            'to': message.get('to', {}).get('phoneNumber', 'Unknown')
        })
    
    communications.sort(key=lambda x: x['time'], reverse=True)
    
    for comm in communications:
        time_str = comm['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if comm['type'] == "Call" else "💬"
        direction_icon = "⬅️" if comm['direction'] == "inbound" else "➡️"
        
        with st.expander(f"{icon} {direction_icon} {time_str}"):
            if comm['type'] == "Call":
                st.write(f"**Agent:** {comm['from'] if comm['direction'] == 'outbound' else comm['to']}")
                st.write(f"**Duration:** {comm['duration']} seconds")
                if comm.get('end_reason') == 'voicemail':
                    st.write("⚠️ **Call ended in voicemail**")
                transcript_url = get_transcript_url(comm['id'])
                st.write(f"[View Transcript]({transcript_url})")
            else:
                st.write(f"**Agent:** {comm['from'] if comm['direction'] == 'outbound' else comm['to']}")
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
                end_reason = f" (Ended in voicemail)" if call.get('endReason') == 'voicemail' else ""
                st.write(f"**{call_time}** - {direction} call ({call.get('duration', 'N/A')} seconds){end_reason}")
        
        if show_messages:
            st.subheader("💬 Messages")
            for message in sorted(messages, key=lambda x: x['createdAt'], reverse=True):
                message_time = datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                direction = "Received" if message.get('direction') == 'inbound' else "Sent"
                st.write(f"**{message_time}** - {direction}: {message.get('content', 'No content')}")

def main():
    st.set_page_config(
