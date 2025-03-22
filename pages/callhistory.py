import streamlit as st
import requests
from datetime import datetime
import pytz
import phonenumbers
import pandas as pd
import altair as alt
import numpy as np

# =============================================================================
# API Configuration
# Replace "YOUR_ACTUAL_OPENPHONE_API_KEY" with your real key.
# =============================================================================
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

def format_phone_number(phone_number):
    """
    Parse and format the phone number to E.164 standard,
    e.g. '+14155550123'.
    """
    try:
        parsed = phonenumbers.parse(phone_number, "US")
        if phonenumbers.is_valid_number(parsed):
            return f"+{parsed.country_code}{parsed.national_number}"
    except Exception as e:
        st.error(f"Error parsing phone number: {e}")
    return None

def get_openphone_numbers():
    """
    Fetch the list of your OpenPhone numbers via the API.
    Returns a list of phone number objects.
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("data", [])
    return []

def fetch_call_history(phone_number):
    """
    Fetch call history from OpenPhone, filtering by the given phone_number.
    Merges calls across all of your OpenPhone numbers (if you have multiple).
    """
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
    """
    Fetch message history from OpenPhone, filtering by the given phone_number.
    Merges messages across all of your OpenPhone numbers (if multiple).
    """
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

def fetch_call_transcript(call_id):
    """
    Fetch transcript for a given call ID.
    """
    url = f"https://api.openphone.com/v1/call-transcripts/{call_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        data = response.json().get("data", {})
        if data and data.get("dialogue"):
            return data
    return None

def format_duration_seconds(sec):
    """
    Converts an integer `sec` into a string "Xm YYs".
    Example: 185 -> "3m 05s".
    """
    if not sec or sec < 0:
        return "0m 00s"
    m, s = divmod(sec, 60)
    return f"{m}m {s:02d}s"

def localize_to_gmt_minus_4(iso_str):
    """
    Takes an ISO datetime string (which may be in UTC or PT),
    localizes it to Los Angeles time, then converts it to GMT-4.
    Returns a Python datetime with tzinfo=Etc/GMT+4 (Myrtle Beach DST).
    """
    # 1) Convert raw string to a datetime in UTC
    dt_utc = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    
    # 2) Localize to America/Los_Angeles
    tz_pt = pytz.timezone("America/Los_Angeles")
    dt_pt = dt_utc.astimezone(tz_pt)
    
    # 3) Convert from PT to GMT-4 (Etc/GMT+4)
    tz_gmt_4 = pytz.timezone("Etc/GMT+4")
    dt_gmt4 = dt_pt.astimezone(tz_gmt_4)
    
    return dt_gmt4

def create_communication_metrics(calls, messages):
    """
    Compute basic metrics for display in a summary dashboard:
    - total calls, total messages, inbound/outbound counts, call durations, etc.
    """
    total_calls = len(calls)
    total_messages = len(messages)
    inbound_calls = len([c for c in calls if c.get('direction') == 'inbound'])
    outbound_calls = len([c for c in calls if c.get('direction') == 'outbound'])
    inbound_messages = len([m for m in messages if m.get('direction') == 'inbound'])
    outbound_messages = len([m for m in messages if m.get('direction') == 'outbound'])

    call_durations = [c.get('duration', 0) for c in calls if c.get('duration')]
    avg_duration = np.mean(call_durations) if call_durations else 0
    max_duration = max(call_durations) if call_durations else 0

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
    """
    Display top-level metrics (call counts, message counts, durations, etc.) in columns.
    """
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
        # Show average/max call duration in seconds (numerically) 
        # or use format_duration_seconds for the display if desired.
        st.metric("Avg Call Duration (sec)", f"{metrics['avg_call_duration']:.1f}")
        st.metric("Max Call Duration (sec)", f"{metrics['max_call_duration']:.1f}")
        st.metric("Avg Message Length", f"{metrics['avg_message_length']:.1f}")

def create_time_series_chart(communications):
    """
    Creates a line chart (Altair) that shows daily call/message counts over time.
    """
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
    """
    Creates a heatmap (Altair) showing activity distribution by hour-of-day vs. day-of-week.
    """
    df = pd.DataFrame(communications)
    df['hour'] = pd.to_datetime(df['time']).dt.hour
    df['day_of_week'] = pd.to_datetime(df['time']).dt.day_name()
    
    hourly_counts = df.groupby(['day_of_week', 'hour']).size().reset_index(name='count')
    
    # Order days to show Monday -> Sunday
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
    """
    Display time-series chart, heatmap, and optional call duration distribution chart.
    """
    communications = []
    
    # Convert calls
    for call in calls:
        dt_gmt4 = localize_to_gmt_minus_4(call['createdAt'])
        communications.append({
            'time': dt_gmt4,
            'type': 'Call',
            'direction': call.get('direction'),
            'duration': call.get('duration', 0)
        })
    
    # Convert messages
    for message in messages:
        dt_gmt4 = localize_to_gmt_minus_4(message['createdAt'])
        communications.append({
            'time': dt_gmt4,
            'type': 'Message',
            'direction': message.get('direction')
        })

    st.subheader("📈 Communication Trends")
    time_series = create_time_series_chart(communications)
    st.altair_chart(time_series, use_container_width=True)

    st.subheader("🗓️ Activity Patterns")
    heatmap = create_hourly_heatmap(communications)
    st.altair_chart(heatmap, use_container_width=True)

    # Display Call Duration Distribution
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
    """
    An optional chronological timeline with expanders for each call or message.
    Shows participants, transcripts, etc.
    """
    st.subheader("📅 Communication Timeline")
    
    timeline = []
    
    # Prepare calls
    for call in calls:
        dt_gmt4 = localize_to_gmt_minus_4(call['createdAt'])
        timeline.append({
            'time': dt_gmt4,
            'type': 'Call',
            'direction': call.get('direction', 'unknown'),
            'duration': call.get('duration', 'N/A'),
            'status': call.get('status', 'unknown'),
            'id': call.get('id'),
            'participants': call.get('participants', [])
        })
    
    # Prepare messages
    for message in messages:
        dt_gmt4 = localize_to_gmt_minus_4(message['createdAt'])
        timeline.append({
            'time': dt_gmt4,
            'type': 'Message',
            'direction': message.get('direction', 'unknown'),
            'content': message.get('content', 'No content'),
            'status': message.get('status', 'unknown'),
            'id': message.get('id'),
            'participants': message.get('participants', [])
        })
    
    # Sort descending by time
    timeline.sort(key=lambda x: x['time'], reverse=True)
    
    for item in timeline:
        time_str = item['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if item['type'] == "Call" else "💬"
        direction_icon = "⬅️" if item['direction'] == "inbound" else "➡️"
        
        with st.expander(f"{icon} {direction_icon} {time_str}"):
            participants = item.get('participants', [])
            if participants:
                st.write("**Participants:**")
                for p in participants:
                    p_number = p.get('phoneNumber', 'Unknown')
                    p_name = p.get('name', '')
                    display_str = p_name + f" ({p_number})" if p_name else p_number
                    st.write("- " + display_str)

            if item['type'] == "Call":
                # Format duration
                if isinstance(item['duration'], int):
                    st.write(f"**Duration:** {format_duration_seconds(item['duration'])}")
                else:
                    st.write(f"**Duration:** {item['duration']}")
                
                # Fetch transcript if available
                transcript = fetch_call_transcript(item['id'])
                if transcript and transcript.get('dialogue'):
                    with st.expander("View Transcript"):
                        for seg in transcript['dialogue']:
                            speaker = seg.get('identifier', 'Unknown')
                            content = seg.get('content', '')
                            start = seg.get('start', 0)
                            end = seg.get('end', 0)
                            st.write(f"**{speaker}** [{start}s - {end}s]: {content}")
                else:
                    st.write("Transcript not available or in progress.")
            else:
                # Message item
                st.write(f"**Message:** {item['content']}")
            
            st.write(f"**Status:** {item['status']}")

def display_all_events_in_one_table(calls, messages):
    """
    NEW Overview Table:
    Shows calls & messages in one combined DataFrame, 
    each row has DisplayTime, Type, Direction, From, To, Content, Duration, etc.
    """
    rows = []
    
    # Process calls
    for c in calls:
        dt_gmt4 = localize_to_gmt_minus_4(c['createdAt'])
        
        # Identify "From" / "To" from participants if needed
        from_ = ""
        to_ = ""
        for p in c.get('participants', []):
            role = p.get('direction', 'unknown')  # Could be 'source' or 'destination'
            number = p.get('phoneNumber', '')
            if role == 'source':
                from_ = number
            elif role == 'destination':
                to_ = number

        rows.append({
            "DisplayTime": dt_gmt4.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "Call",
            "direction": c.get('direction', ''),
            "From": from_,
            "To": to_,
            "Content": f"Call Transcript ID: {c.get('id')}",
            "Duration": format_duration_seconds(c.get('duration', 0))
        })

    # Process messages
    for m in messages:
        dt_gmt4 = localize_to_gmt_minus_4(m['createdAt'])
        from_ = ""
        to_ = ""
        for p in m.get('participants', []):
            role = p.get('direction', 'unknown')
            number = p.get('phoneNumber', '')
            if role == 'source':
                from_ = number
            elif role == 'destination':
                to_ = number

        rows.append({
            "DisplayTime": dt_gmt4.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "Message",
            "direction": m.get('direction', ''),
            "From": from_,
            "To": to_,
            "Content": m.get('content', 'No content'),
            "Duration": ""
        })
    
    # Convert to DataFrame and sort by DisplayTime (ascending)
    df = pd.DataFrame(rows)
    df.sort_values(by="DisplayTime", inplace=True)

    st.subheader("📋 All Calls & Messages (Overview)")
    st.dataframe(df.reset_index(drop=True), use_container_width=True)

def main():
    st.set_page_config(
        page_title="Communication Analytics",
        page_icon="📊",
        layout="wide"
    )

    st.title("📱 Communication Analytics Dashboard")

    # Optionally read phone from URL param
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

            tab1, tab2, tab3, tab4 = st.tabs([
                "📊 Overview Metrics", 
                "📈 Analysis", 
                "📅 Timeline", 
                "📝 Combined Table"
            ])

            # 1) Overview Metrics
            with tab1:
                metrics = create_communication_metrics(calls, messages)
                display_metrics_dashboard(metrics)

            # 2) Analysis (Charts)
            with tab2:
                display_communications_analysis(calls, messages)

            # 3) Timeline (Expanders + transcripts)
            with tab3:
                display_timeline(calls, messages)

            # 4) Combined Overview Table
            with tab4:
                display_all_events_in_one_table(calls, messages)

if __name__ == "__main__":
    main()
