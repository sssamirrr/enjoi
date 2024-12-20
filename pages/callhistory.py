import streamlit as st
import requests
from datetime import datetime, timedelta
import phonenumbers
import pandas as pd
import altair as alt
import numpy as np

# API Configuration
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
    if response.status_code == 200:
        return response.json().get("data", [])
    return []

def fetch_call_history(phone_number):
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

def create_communication_metrics(calls, messages):
    # Basic metrics
    total_calls = len(calls)
    total_messages = len(messages)
    inbound_calls = len([c for c in calls if c.get('direction') == 'inbound'])
    outbound_calls = len([c for c in calls if c.get('direction') == 'outbound'])
    inbound_messages = len([m for m in messages if m.get('direction') == 'inbound'])
    outbound_messages = len([m for m in messages if m.get('direction') == 'outbound'])

    # Calculate call durations
    call_durations = [c.get('duration', 0) for c in calls if c.get('duration')]
    avg_duration = np.mean(call_durations) if call_durations else 0
    max_duration = max(call_durations) if call_durations else 0

    # Message lengths
    message_lengths = [len(str(m.get('content', ''))) for m in messages if m.get('content')]
    avg_message_length = np.mean(message_lengths) if message_lengths else 0

    return {
        'total_calls': total_calls,
        'total_messages': total_messages,
        'inbound_calls': inbound_calls,
        'outbound_calls': outbound_calls,
        'inbound_messages': inbound_messages,
        'outbound_messages': outbound_messages,
        'avg_call_duration': avg_duration,
        'max_call_duration': max_duration,
        'avg_message_length': avg_message_length
    }

def display_metrics_dashboard(metrics):
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
        st.metric("Avg Call Duration (sec)", f"{metrics['avg_call_duration']:.1f}")
        st.metric("Max Call Duration (sec)", f"{metrics['max_call_duration']:.1f}")
        st.metric("Avg Message Length", f"{metrics['avg_message_length']:.1f}")

def create_time_series_chart(communications):
    df = pd.DataFrame(communications)
    df['date'] = pd.to_datetime(df['time']).dt.date
    daily_counts = df.groupby(['date', 'type']).size().reset_index(name='count')
    
    chart = alt.Chart(daily_counts).mark_line(point=True).encode(
        x='date:T',
        y='count:Q',
        color='type:N',
        tooltip=['date', 'type', 'count']
    ).properties(
        title='Communication Activity Over Time',
        width=700,
        height=400
    ).interactive()
    
    return chart

def create_hourly_heatmap(communications):
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

def display_communications_analysis(calls, messages):
    # Prepare combined communications data
    communications = []
    
    for call in calls:
        communications.append({
            'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction'),
            'duration': call.get('duration', 0)
        })
    
    for message in messages:
        communications.append({
            'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction')
        })

    # Time series chart
    st.subheader("📈 Communication Trends")
    time_series = create_time_series_chart(communications)
    st.altair_chart(time_series, use_container_width=True)

    # Activity heatmap
    st.subheader("🗓️ Activity Patterns")
    heatmap = create_hourly_heatmap(communications)
    st.altair_chart(heatmap, use_container_width=True)

    # Call duration distribution
    if calls:
        st.subheader("⏱️ Call Duration Distribution")
        call_durations = [c.get('duration', 0) for c in calls if c.get('duration')]
        if call_durations:
            df_durations = pd.DataFrame({'duration': call_durations})
            duration_chart = alt.Chart(df_durations).mark_bar().encode(
                x=alt.X('duration:Q', bin=alt.Bin(maxbins=20)),
                y='count()',
                tooltip=['count()']
            ).properties(
                width=700,
                height=300
            )
            st.altair_chart(duration_chart, use_container_width=True)

def display_timeline(calls, messages):
    st.subheader("📅 Communication Timeline")
    
    # Combine and sort all communications
    timeline = []
    
    for call in calls:
        timeline.append({
            'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction', 'unknown'),
            'duration': call.get('duration', 'N/A'),
            'status': call.get('status', 'unknown')
        })
    
    for message in messages:
        timeline.append({
            'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction', 'unknown'),
            'content': message.get('content', 'No content'),
            'status': message.get('status', 'unknown')
        })
    
    # Sort by time
    timeline.sort(key=lambda x: x['time'], reverse=True)
    
    # Display timeline
    for item in timeline:
        time_str = item['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if item['type'] == "Call" else "💬"
        direction_icon = "⬅️" if item['direction'] == "inbound" else "➡️"
        
        with st.expander(f"{icon} {direction_icon} {time_str}"):
            if item['type'] == "Call":
                st.write(f"**Duration:** {item['duration']} seconds")
            else:
                st.write(f"**Message:** {item['content']}")
            st.write(f"**Status:** {item['status']}")

def main():
    st.set_page_config(page_title="Communication Analytics", 
                      page_icon="📊", 
                      layout="wide")

    st.title("📱 Communication Analytics Dashboard")

    # Get phone number from URL parameter or input
    query_params = st.experimental_get_query_params()
    phone_number = query_params.get("phone", [""])[0]
    
    if not phone_number:
        phone_number = st.text_input("Enter phone number:")
    
    if phone_number:
        with st.spinner('Loading communication history...'):
            calls = fetch_call_history(phone_number)
            messages = fetch_message_history(phone_number)

            if not calls and not messages:
                st.warning("No communication history found for this number.")
                return

            # Create tabs for different views
            tab1, tab2, tab3 = st.tabs(["📊 Overview", "📈 Analysis", "📅 Timeline"])

            with tab1:
                metrics = create_communication_metrics(calls, messages)
                display_metrics_dashboard(metrics)

            with tab2:
                display_communications_analysis(calls, messages)

            with tab3:
                display_timeline(calls, messages)

if __name__ == "__main__":
    main()
