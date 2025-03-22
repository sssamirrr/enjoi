import streamlit as st
import requests
from datetime import datetime
import phonenumbers
import pandas as pd
import altair as alt

# =============================================================================
# API Configuration
# WARNING: Hard-coding an API key is not recommended in production!
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
    """
    Fetch message history from OpenPhone, filtering by the given phone_number.
    Merges messages across all of your OpenPhone numbers (if multiple).
    """
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

def format_duration_seconds(sec):
    """
    Convert an integer or float 'sec' into "Xm YYs".
    Example: 185 -> "3m 05s".
    """
    if not sec or sec < 0:
        return "0m 00s"
    sec = int(sec)
    m, s = divmod(sec, 60)
    return f"{m}m {s:02d}s"

def display_metrics(calls, messages):
    """
    Display top-level metrics: total calls, messages, inbound/outbound counts, etc.
    """
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
        
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Average Call Duration (seconds)", f"{avg_duration:.1f}")
        with col_b:
            st.metric("Longest Call (seconds)", max_duration)

    st.subheader("💬 Message Analytics")
    message_lengths = [len(m.get('text', '')) for m in messages if m.get('text')]
    if message_lengths:
        avg_length = sum(message_lengths) / len(message_lengths)
        st.metric("Average Message Length (characters)", f"{avg_length:.1f}")

def display_timeline(calls, messages):
    """
    Example timeline with expanders, if you still want it.
    Otherwise, you can remove or simplify.
    """
    st.header("📅 Communication Timeline")

    # Combine calls + messages in descending chronological order
    timeline = []
    for call in calls:
        timeline.append({
            'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction', 'unknown'),
            'duration': call.get('duration', 'N/A'),
            'status': call.get('status', 'unknown'),
            'id': call.get('id')
        })
    for message in messages:
        timeline.append({
            'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction', 'unknown'),
            'text': message.get('text', 'No content'),
            'status': message.get('status', 'unknown'),
            'id': message.get('id')
        })
    
    timeline.sort(key=lambda x: x['time'], reverse=True)

    for item in timeline:
        t_str = item['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if item['type'] == "Call" else "💬"
        direction_icon = "⬅️" if item['direction'] == "inbound" else "➡️"
        
        label = f"{icon} {direction_icon} {t_str}"
        with st.expander(label):
            if item['type'] == "Call":
                dur_str = str(item['duration']) + " sec"
                st.write(f"Duration: {dur_str}")
                st.write(f"Status: {item['status']}")
            else:
                st.write(f"Text: {item.get('text','No content')}")
                st.write(f"Status: {item['status']}")

def display_history(phone_number):
    """
    The main logic that organizes tabs:
    - Tab 1: Metrics
    - Tab 2: Timeline
    - Tab 3: *New* 'like a book' chronological details
    """
    st.title(f"📱 Communication History for {phone_number}")

    with st.spinner('Fetching communication history...'):
        calls = fetch_call_history(phone_number)
        messages = fetch_message_history(phone_number)

    if not calls and not messages:
        st.warning("No communication history found for this number.")
        return

    tab1, tab2, tab3 = st.tabs(["📊 Metrics", "📅 Timeline", "📋 Details"])

    # 1) Metrics
    with tab1:
        display_metrics(calls, messages)

    # 2) Timeline
    with tab2:
        display_timeline(calls, messages)

    # 3) Book-style chronological conversation
    with tab3:
        st.header("Full Conversation (Chronological)")

        # Combine calls + messages
        communications = []

        # Add calls
        for c in calls:
            dt_obj = datetime.fromisoformat(c['createdAt'].replace('Z', '+00:00'))
            communications.append({
                'time': dt_obj,
                'type': 'call',
                'direction': c.get('direction', 'unknown'),
                'from': c.get('from', {}).get('phoneNumber', 'Unknown'),
                'to': c.get('to', {}).get('phoneNumber', 'Unknown'),
                'status': c.get('status', 'unknown'), # 'completed', 'missed', etc.
                'duration': c.get('duration', 0)
            })

        # Add messages
        for m in messages:
            dt_obj = datetime.fromisoformat(m['createdAt'].replace('Z', '+00:00'))
            from_num = m.get('from', {}).get('phoneNumber', 'Unknown')
            to_num = m.get('to', {}).get('phoneNumber', 'Unknown')
            communications.append({
                'time': dt_obj,
                'type': 'message',
                'direction': m.get('direction', 'unknown'),
                'from': from_num,
                'to': to_num,
                'text': m.get('text', 'No content')
            })

        # Sort ascending by time
        communications.sort(key=lambda x: x['time'])

        # Print each in chronological order
        for item in communications:
            ts_str = item['time'].strftime("%Y-%m-%d %H:%M")
            dir_str = item['direction']

            if item['type'] == 'call':
                # If missed call, show [MISSED]
                if item['status'] == 'missed':
                    st.write(
                        f"{ts_str} {dir_str} call from {item['from']} "
                        f"to {item['to']} [MISSED]"
                    )
                else:
                    # Show the duration in min+sec
                    dur_str = format_duration_seconds(item['duration'])
                    st.write(
                        f"{ts_str} {dir_str} call from {item['from']} "
                        f"to {item['to']} ({dur_str})"
                    )
            else:
                # It's a message
                msg_txt = item.get('text', '')
                st.write(
                    f"{ts_str} {dir_str} message from {item['from']} "
                    f"to {item['to']}: {msg_txt}"
                )

def main():
    st.set_page_config(
        page_title="Communication History",
        page_icon="📱",
        layout="wide"
    )

    # Grab phone number from query params or from text input
    query_params = st.query_params
    default_phone = query_params.get("phone", [""])[0] if isinstance(query_params.get("phone", ""), list) else ""

    phone_number = st.text_input("Enter phone number:", value=default_phone)

    if phone_number:
        display_history(phone_number)
    else:
        st.error("Please provide a phone number.")

if __name__ == "__main__":
    main()
