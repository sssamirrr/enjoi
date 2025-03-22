import streamlit as st
import requests
from datetime import datetime
import pytz
import phonenumbers
import pandas as pd
import altair as alt
import numpy as np

# API Configuration
# OpenPhone API Credentials
OPENPHONE_API_KEY = "YOUR_OPENPHONE_API_KEY"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

def format_phone_number(phone_number):
    """Parse and format phone number to E.164."""
    try:
        parsed = phonenumbers.parse(phone_number, "US")
        if phonenumbers.is_valid_number(parsed):
            return f"+{parsed.country_code}{parsed.national_number}"
    except Exception as e:
        st.error(f"Error parsing phone number: {e}")
    return None

def get_openphone_numbers():
    """Fetch the list of your OpenPhone numbers."""
    url = "https://api.openphone.com/v1/phone-numbers"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("data", [])
    return []

def fetch_call_history(phone_number):
    """Fetch call history involving the given phone_number from your OpenPhone numbers."""
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
    """Fetch message history involving the given phone_number from your OpenPhone numbers."""
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
    """Fetch transcript for a given call ID."""
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
    Example: 185 -> "3m 05s"
    """
    if not sec or sec < 0:
        return "0m 00s"
    m, s = divmod(sec, 60)
    return f"{m}m {s:02d}s"

def localize_to_gmt_minus_4(iso_str):
    """
    Takes an ISO datetime string (which may be in UTC or appended with +00:00),
    localizes it to Los Angeles time first (as the original is said to be PT),
    then converts it to GMT-4 (Myrtle Beach time during DST).
    Returns a Python datetime in that final timezone.
    """
    # 1. Convert the raw string to a datetime (assumed UTC if it ends with Z)
    dt_utc = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
    
    # 2. Localize to America/Los_Angeles (PT)
    tz_pt = pytz.timezone("America/Los_Angeles")
    dt_pt = dt_utc.astimezone(tz_pt)
    
    # 3. Convert to Etc/GMT+4 (which is effectively UTC-4)
    tz_gmt_4 = pytz.timezone("Etc/GMT+4")
    dt_gmt4 = dt_pt.astimezone(tz_gmt_4)
    
    return dt_gmt4

def create_communication_metrics(calls, messages):
    """Compute various metrics (counts, durations, etc.) for display."""
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
    """Display summary metrics (calls, messages, etc.)."""
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
        # For the Avg/Max call duration metrics, we can keep them numeric or format them.
        # Below keeps them numeric. If you prefer "3m 05s" style here, just call `format_duration_seconds(...)`.
        st.metric("Avg Call Duration (sec)", f"{metrics['avg_call_duration']:.1f}")
        st.metric("Max Call Duration (sec)", f"{metrics['max_call_duration']:.1f}")
        st.metric("Avg Message Length", f"{metrics['avg_message_length']:.1f}")

def create_time_series_chart(communications):
    """Create a line chart (Altair) showing daily call/message counts over time."""
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
    """Create a heatmap (Altair) showing activity by day-of-week vs hour-of-day."""
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
    """Display interactive charts (time series, heatmap, etc.) for calls and messages."""
    communications = []
    
    for call in calls:
        # Convert createdAt to a proper datetime
        dt_gmt4 = localize_to_gmt_minus_4(call['createdAt'])
        communications.append({
            'time': dt_gmt4,
            'type': 'Call',
            'direction': call.get('direction'),
            'duration': call.get('duration', 0)
        })
    
    for message in messages:
        dt_gmt4 = localize_to_gmt_minus_4(message['createdAt'])
        communications.append({
            'time': dt_gmt4,
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
    """
    (Optional) Original timeline view, with expanders, transcripts, etc.
    If you still want a chronological 'timeline' you can keep this.
    """
    st.subheader("📅 Communication Timeline")
    
    timeline = []
    
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
                # Display formatted duration
                if isinstance(item['duration'], int):
                    st.write(f"**Duration:** {format_duration_seconds(item['duration'])}")
                else:
                    st.write(f"**Duration:** {item['duration']}")
                
                # Attempt to fetch transcript
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
                # It's a message
                st.write(f"**Message:** {item['content']}")
            
            st.write(f"**Status:** {item['status']}")

def display_all_events_in_one_table(calls, messages):
    """
    NEW FUNCTION:
    Shows calls & messages in a single DataFrame (single 'Overview' table),
    with columns for DisplayTime (GMT-4), type, direction, from, to, content, duration, etc.
    """
    # We'll assemble lists/dicts for each row, then convert to a DataFrame.
    rows = []
    
    for c in calls:
        dt_gmt4 = localize_to_gmt_minus_4(c['createdAt'])
        # Attempt to find from/to phone numbers. 
        # Typically 'participants' might hold details, but it depends on your API response structure.
        from_ = None
        to_ = None
        for p in c.get('participants', []):
            role = p.get('direction', 'unknown')  # or p.get('direction') might not exist
            number = p.get('phoneNumber', '')
            # Heuristic: if call direction is outbound, our number might be "from", the other is "to".
            # Adjust to your data shape as needed:
            if role == 'source':
                from_ = number
            elif role == 'destination':
                to_ = number

        row = {
            "DisplayTime": dt_gmt4.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "Call",
            "direction": c.get('direction', ''),
            "From": from_ or "",
            "To": to_ or "",
            "Content": f"Call Transcript ID: {c.get('id')}",  # or short snippet
            "Duration": format_duration_seconds(c.get('duration', 0))
        }
        rows.append(row)

    for m in messages:
        dt_gmt4 = localize_to_gmt_minus_4(m['createdAt'])
        from_ = None
        to_ = None
        for p in m.get('participants', []):
            # Similar heuristic
            # If direction == 'source', that's 'from'; if 'destination', that's 'to'.
            # Adjust as needed:
            role = p.get('direction', 'unknown')
            number = p.get('phoneNumber', '')
            if role == 'source':
                from_ = number
            elif role == 'destination':
                to_ = number

        row = {
            "DisplayTime": dt_gmt4.strftime("%Y-%m-%d %H:%M:%S"),
            "type": "Message",
            "direction": m.get('direction', ''),
            "From": from_ or "",
            "To": to_ or "",
            "Content": m.get('content', 'No content'),
            "Duration": ""  # Not applicable for messages
        }
        rows.append(row)
    
    # Convert to DataFrame and sort chronologically
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

            # 3) Timeline (Old Expander View)
            with tab3:
                display_timeline(calls, messages)

            # 4) NEW: Combined Overview Table
            with tab4:
                display_all_events_in_one_table(calls, messages)

if __name__ == "__main__":
    main()
