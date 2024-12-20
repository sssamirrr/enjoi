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

# Previous functions remain the same until display_metrics...

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
            
            # Track calls ending in voicemail
            if call.get('endReason') == 'voicemail':
                agent_stats[agent_number]['voicemail_endings'] += 1
            
            # Add call duration
            if call.get('duration'):
                agent_stats[agent_number]['total_call_duration'] += call.get('duration')
            
            # Add transcript info if available
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
    
    with col1:
        st.metric("Total Calls", total_calls)
    with col2:
        st.metric("Total Messages", total_messages)
    with col3:
        st.metric("Inbound Calls", inbound_calls)
    with col4:
        st.metric("Outbound Calls", outbound_calls)

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
            
            # Display transcript links
            if stats['transcripts']:
                st.subheader("📝 Call Transcripts")
                for transcript in sorted(stats['transcripts'], key=lambda x: x['time'], reverse=True):
                    time_str = datetime.fromisoformat(transcript['time'].replace('Z', '+00:00')).strftime("%Y-%m-%d %H:%M")
                    st.write(f"[{time_str} - Call Transcript](https://app.openphone.com/transcripts/{transcript['id']})")

    # Call Duration Metrics
    st.subheader("📞 Call Analytics")
    voicemail_endings = len([c for c in calls if c.get('endReason') == 'voicemail'])
    call_durations = [c.get('duration', 0) for c in calls if c.get('duration')]
    
    if call_durations:
        avg_duration = sum(call_durations) / len(call_durations)
        max_duration = max(call_durations)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Average Call Duration (seconds)", f"{avg_duration:.1f}")
        with col2:
            st.metric("Longest Call (seconds)", max_duration)
        with col3:
            st.metric("Calls Ending in Voicemail", voicemail_endings)

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

# Update the display_timeline function to include transcript links
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
                st.write(f"[View Transcript](https://app.openphone.com/transcripts/{comm['id']})")
            else:
                st.write(f"**Agent:** {comm['from'] if comm['direction'] == 'outbound' else comm['to']}")
                st.write(f"**Message:** {comm['content']}")
            st.write(f"**Status:** {comm['status']}")

# Rest of the code remains the same...
