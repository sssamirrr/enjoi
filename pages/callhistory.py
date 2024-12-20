import streamlit as st
import requests
from datetime import datetime, timedelta
import phonenumbers
import pandas as pd
import altair as alt
import numpy as np
import plotly.express as px
from datetime import datetime, timezone
import json

# API Configuration
OPENPHONE_API_KEY = "your_api_key_here"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

# Page Configuration
st.set_page_config(
    page_title="Communication Analytics",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .stMetric .metric-label { font-size: 14px !important; }
    .stMetric .metric-value { font-size: 24px !important; }
    .stAlert { padding: 10px !important; }
    </style>
    """, unsafe_allow_html=True)

def format_phone_number(phone_number):
    """Format phone number to E.164 format"""
    try:
        parsed = phonenumbers.parse(phone_number, "US")
        if phonenumbers.is_valid_number(parsed):
            return f"+{parsed.country_code}{parsed.national_number}"
    except Exception as e:
        st.error(f"Error parsing phone number: {e}")
    return None

def get_openphone_numbers():
    """Fetch all OpenPhone numbers associated with the account"""
    url = "https://api.openphone.com/v1/phone-numbers"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("data", [])
    return []

def fetch_call_history(phone_number):
    """Fetch call history for a specific phone number"""
    formatted_phone = format_phone_number(phone_number)
    all_calls = []
    if formatted_phone:
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
    """Fetch message history for a specific phone number"""
    formatted_phone = format_phone_number(phone_number)
    all_messages = []
    if formatted_phone:
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

def fetch_transcript(call_id):
    """Fetch transcript for a specific call"""
    url = f"https://api.openphone.com/v1/calls/{call_id}/transcript"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("data", {})
    return None

def format_duration(seconds):
    """Format duration in seconds to readable time"""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    remaining_seconds = seconds % 60
    return f"{minutes}m {remaining_seconds}s"

def create_communication_metrics(calls, messages):
    """Calculate communication metrics"""
    metrics = {
        'total_calls': len(calls),
        'total_messages': len(messages),
        'inbound_calls': len([c for c in calls if c.get('direction') == 'inbound']),
        'outbound_calls': len([c for c in calls if c.get('direction') == 'outbound']),
        'inbound_messages': len([m for m in messages if m.get('direction') == 'inbound']),
        'outbound_messages': len([m for m in messages if m.get('direction') == 'outbound']),
        'avg_call_duration': np.mean([c.get('duration', 0) for c in calls]) if calls else 0,
        'max_call_duration': max([c.get('duration', 0) for c in calls]) if calls else 0,
        'avg_message_length': np.mean([len(str(m.get('content', ''))) for m in messages]) if messages else 0,
        'recorded_calls': len([c for c in calls if c.get('recordingUrl')]),
        'transcribable_calls': len([c for c in calls if c.get('id')])
    }
    return metrics

def display_metrics_dashboard(metrics):
    """Display main metrics dashboard"""
    st.subheader("📊 Overview Metrics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Calls", metrics['total_calls'])
        st.metric("Inbound Calls", metrics['inbound_calls'])
        st.metric("Outbound Calls", metrics['outbound_calls'])
    
    with col2:
        st.metric("Total Messages", metrics['total_messages'])
        st.metric("Inbound Messages", metrics['inbound_messages'])
        st.metric("Outbound Messages", metrics['outbound_messages'])
    
    with col3:
        st.metric("Avg Call Duration", format_duration(int(metrics['avg_call_duration'])))
        st.metric("Recorded Calls", metrics['recorded_calls'])
        st.metric("Transcribable Calls", metrics['transcribable_calls'])

def create_time_series_chart(communications):
    """Create time series chart for communications"""
    df = pd.DataFrame(communications)
    df['date'] = pd.to_datetime(df['time']).dt.date
    daily_counts = df.groupby(['date', 'type']).size().reset_index(name='count')
    
    chart = alt.Chart(daily_counts).mark_line(point=True).encode(
        x=alt.X('date:T', title='Date'),
        y=alt.Y('count:Q', title='Count'),
        color='type:N',
        tooltip=['date', 'type', 'count']
    ).properties(
        title='Communication Activity Over Time',
        width=700,
        height=400
    ).interactive()
    
    return chart

def display_timeline(calls, messages):
    """Display communication timeline"""
    st.subheader("📅 Communication Timeline")
    
    timeline = []
    
    for call in calls:
        timeline.append({
            'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction', 'unknown'),
            'duration': call.get('duration', 0),
            'status': call.get('status', 'unknown'),
            'id': call.get('id'),
            'recording_url': call.get('recordingUrl')
        })
    
    for message in messages:
        timeline.append({
            'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction', 'unknown'),
            'content': message.get('content', 'No content'),
            'status': message.get('status', 'unknown'),
            'attachments': message.get('attachments', [])
        })
    
    timeline.sort(key=lambda x: x['time'], reverse=True)
    
    for item in timeline:
        time_str = item['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if item['type'] == "Call" else "💬"
        direction_icon = "⬅️" if item['direction'] == "inbound" else "➡️"
        
        with st.expander(f"{icon} {direction_icon} {time_str}"):
            if item['type'] == "Call":
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write(f"**Duration:** {format_duration(item['duration'])}")
                    st.write(f"**Status:** {item['status'].title()}")
                    
                    if item.get('recording_url'):
                        st.audio(item['recording_url'], format='audio/mp3')
                    
                    if item.get('id'):
                        if st.button(f"View Transcript", key=f"transcript_{item['id']}"):
                            with st.spinner('Loading transcript...'):
                                transcript = fetch_transcript(item['id'])
                                if transcript:
                                    st.markdown("### 📝 Transcript")
                                    for segment in transcript.get('segments', []):
                                        speaker = "Agent" if segment.get('speakerId') == 0 else "Customer"
                                        text = segment.get('text', '')
                                        timestamp = segment.get('startTime', 0)
                                        minutes = int(timestamp // 60)
                                        seconds = int(timestamp % 60)
                                        st.markdown(f"**[{minutes:02d}:{seconds:02d}] {speaker}:** {text}")
                                else:
                                    st.warning("No transcript available")
                
                with col2:
                    if item.get('recording_url'):
                        st.write("📀 Recording available")
            else:
                st.write(f"**Message:** {item['content']}")
                st.write(f"**Status:** {item['status'].title()}")
                
                if item.get('attachments'):
                    st.write("**Attachments:**")
                    for attachment in item['attachments']:
                        if attachment.get('url'):
                            if attachment.get('type', '').startswith('image/'):
                                st.image(attachment['url'])
                            else:
                                st.markdown(f"[📎 Download Attachment]({attachment['url']})")

def create_hourly_heatmap(communications):
    """Create hourly activity heatmap"""
    df = pd.DataFrame(communications)
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    df['day_of_week'] = pd.to_datetime(df['time']).dt.day_name()
    
    hourly_counts = df.groupby(['day_of_week', 'hour']).size().reset_index(name='count')
    
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    hourly_counts['day_of_week'] = pd.Categorical(hourly_counts['day_of_week'], 
                                                categories=days_order, 
                                                ordered=True)
    
    heatmap = alt.Chart(hourly_counts).mark_rect().encode(
        x=alt.X('hour:O', title='Hour of Day'),
        y=alt.Y('day_of_week:O', title='Day of Week'),
        color=alt.Color('count:Q', scale=alt.Scale(scheme='viridis')),
        tooltip=['day_of_week', 'hour', 'count']
    ).properties(
        title='Activity Heatmap',
        width=700,
        height=300
    )
    
    return heatmap

def main():
    st.title("📱 Communication Analytics Dashboard")

    query_params = st.experimental_get_query_params()
    phone_number = query_params.get("phone", [""])[0]
    
    if not phone_number:
        phone_number = st.text_input("Enter phone number:", placeholder="+1234567890")
    
    if phone_number:
        with st.spinner('Loading communication history...'):
            calls = fetch_call_history(phone_number)
            messages = fetch_message_history(phone_number)

            if not calls and not messages:
                st.warning("No communication history found for this number.")
                return

            # Create tabs
            tab1, tab2, tab3 = st.tabs(["📊 Overview", "📈 Analysis", "📅 Timeline"])

            with tab1:
                metrics = create_communication_metrics(calls, messages)
                display_metrics_dashboard(metrics)

            with tab2:
                st.subheader("📈 Communication Patterns")
                
                # Prepare data for visualizations
                communications = []
                for call in calls:
                    communications.append({
                        'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
                        'type': 'Call'
                    })
                for message in messages:
                    communications.append({
                        'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
                        'type': 'Message'
                    })
                
                # Display time series chart
                time_series = create_time_series_chart(communications)
                st.altair_chart(time_series, use_container_width=True)
                
                # Display heatmap
                st.subheader("🗓️ Activity Patterns")
                heatmap = create_hourly_heatmap(communications)
                st.altair_chart(heatmap, use_container_width=True)

            with tab3:
                display_timeline(calls, messages)

if __name__ == "__main__":
    main()
