import streamlit as st
import requests
from datetime import datetime
import phonenumbers
import pandas as pd
import altair as alt

###############################################################################
# API CONFIG
###############################################################################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

###############################################################################
# HELPER FUNCTIONS
###############################################################################
def format_phone_number(phone_number):
    """
    Parse and format the phone number to E.164 standard, e.g. '+14155550123'.
    If parsing fails, return the original string.
    """
    try:
        parsed = phonenumbers.parse(phone_number, "US")
        if phonenumbers.is_valid_number(parsed):
            return f"+{parsed.country_code}{parsed.national_number}"
    except:
        pass
    return phone_number

def get_openphone_numbers():
    """Return a list of your OpenPhone numbers from the API."""
    url = "https://api.openphone.com/v1/phone-numbers"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("data", [])
    return []

def fetch_call_history(phone_number):
    """
    Fetch call history for the given phone_number across all your OpenPhone lines.
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
    Fetch message history for the given phone_number across all your OpenPhone lines.
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

def fetch_call_transcript(call_id):
    """
    Fetch transcript data for a given call ID (line by line).
    """
    url = f"https://api.openphone.com/v1/call-transcripts/{call_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        return resp.json().get("data", {})
    return None

def format_duration_seconds(sec):
    """
    Convert an integer/float 'sec' into a string "Xm YYs".
    Example: 185 -> "3m 05s"
    """
    if not sec or sec < 0:
        return "0m 00s"
    sec = int(sec)
    m, s = divmod(sec, 60)
    return f"{m}m {s:02d}s"

def extract_from_to_participants(participants):
    """
    Given a list like:
      [
        { "direction": "source", "phoneNumber": "+1555..." },
        { "direction": "destination", "phoneNumber": "+1666..." }
      ]
    or possibly strings instead of dicts,
    return (from_number, to_number).
    """
    from_num = "Unknown"
    to_num = "Unknown"

    for p in participants or []:
        if isinstance(p, dict):
            p_dir = p.get('direction', '')
            p_num = p.get('phoneNumber', '')
            if p_dir == 'source':
                from_num = p_num
            elif p_dir == 'destination':
                to_num = p_num
        elif isinstance(p, str):
            # If it's a string phone number, guess it's 'source' if from_num is still 'Unknown'.
            # Then the next string can be 'to_num'.
            if from_num == "Unknown":
                from_num = p
            else:
                to_num = p
        # else: skip if None or unexpected type
    
    return (from_num, to_num)

###############################################################################
# METRICS (TAB 1)
###############################################################################
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
        cA, cB = st.columns(2)
        with cA:
            st.metric("Average Call Duration (seconds)", f"{avg_duration:.1f}")
        with cB:
            st.metric("Longest Call (seconds)", max_duration)

    st.subheader("💬 Message Analytics")
    message_lengths = [len(m.get('text', '')) for m in messages if m.get('text')]
    if message_lengths:
        avg_length = sum(message_lengths) / len(message_lengths)
        st.metric("Avg Message Length", f"{avg_length:.1f}")

###############################################################################
# TIMELINE (TAB 2)
###############################################################################
def display_timeline(calls, messages):
    """
    Show calls/messages in descending chronological order with expanders.
    """
    st.header("📅 Communication Timeline")

    timeline = []

    # Prepare calls
    for c in calls:
        t = datetime.fromisoformat(c['createdAt'].replace('Z', '+00:00'))
        timeline.append({
            'time': t,
            'type': 'Call',
            'direction': c.get('direction', 'unknown'),
            'duration': c.get('duration', 0),
            'status': c.get('status', 'unknown'),
            'id': c.get('id'),
            'participants': c.get('participants', [])
        })

    # Prepare messages
    for m in messages:
        t = datetime.fromisoformat(m['createdAt'].replace('Z', '+00:00'))
        timeline.append({
            'time': t,
            'type': 'Message',
            'direction': m.get('direction', 'unknown'),
            'text': m.get('text', 'No content'),
            'status': m.get('status', 'unknown'),
            'id': m.get('id'),
            'participants': m.get('participants', [])
        })

    # Sort descending
    timeline.sort(key=lambda x: x['time'], reverse=True)

    for item in timeline:
        time_str = item['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if item['type'] == "Call" else "💬"
        direction_icon = "⬅️" if item['direction'] == "inbound" else "➡️"
        label = f"{icon} {direction_icon} {time_str}"

        with st.expander(label):
            from_, to_ = extract_from_to_participants(item['participants'])
            st.write(f"**From:** {from_}")
            st.write(f"**To:** {to_}")
            st.write(f"**Direction:** {item['direction']}")

            if item['type'] == "Call":
                if item['status'] == 'missed':
                    st.write("**Status:** MISSED")
                else:
                    dur_str = format_duration_seconds(item['duration'])
                    st.write(f"**Duration:** {dur_str}")
                # Show transcript if available
                transcript = fetch_call_transcript(item['id'])
                if transcript and transcript.get('dialogue'):
                    st.write("**Transcript:**")
                    for seg in transcript['dialogue']:
                        spkr = seg.get('identifier','???')
                        txt  = seg.get('content','')
                        st.write(f"{spkr}: {txt}")
            else:
                # It's a message
                st.write(f"**Text:** {item.get('text','No content')}")
                st.write(f"**Status:** {item['status']}")

###############################################################################
# CHRONOLOGICAL DETAILS (TAB 3)
###############################################################################
def display_full_chronological(calls, messages):
    """
    Show calls & messages in ascending chronological order, 
    with transcripts for completed calls and phone numbers from participants.
    """
    st.header("Full Conversation (Chronological)")

    comms = []

    # Add calls
    for c in calls:
        t = datetime.fromisoformat(c['createdAt'].replace('Z', '+00:00'))
        from_, to_ = extract_from_to_participants(c.get('participants', []))
        comms.append({
            'time': t,
            'type': 'call',
            'direction': c.get('direction','unknown'),
            'from': from_,
            'to': to_,
            'status': c.get('status','unknown'),
            'duration': c.get('duration', 0),
            'id': c.get('id')
        })

    # Add messages
    for m in messages:
        t = datetime.fromisoformat(m['createdAt'].replace('Z', '+00:00'))
        from_, to_ = extract_from_to_participants(m.get('participants', []))
        comms.append({
            'time': t,
            'type': 'message',
            'direction': m.get('direction','unknown'),
            'from': from_,
            'to': to_,
            'text': m.get('text','No content')
        })

    # Sort ascending
    comms.sort(key=lambda x: x['time'])

    # Print them in chronological order
    for item in comms:
        ts_str = item['time'].strftime("%Y-%m-%d %H:%M")
        dir_str = item['direction']

        if item['type'] == 'call':
            if item['status'] == 'missed':
                st.write(
                    f"{ts_str} {dir_str} call from {item['from']} "
                    f"to {item['to']} [MISSED]"
                )
            else:
                dur_str = format_duration_seconds(item['duration'])
                st.write(
                    f"{ts_str} {dir_str} call from {item['from']} "
                    f"to {item['to']} ({dur_str})"
                )
                # Show transcript if not missed
                transcript = fetch_call_transcript(item['id'])
                if transcript and transcript.get('dialogue'):
                    for seg in transcript['dialogue']:
                        spkr = seg.get('identifier','???')
                        cnt  = seg.get('content','')
                        st.write(f"    {spkr}: {cnt}")
        else:
            # It's a message
            st.write(
                f"{ts_str} {dir_str} message from {item['from']} "
                f"to {item['to']}: {item.get('text','')}"
            )

###############################################################################
# MAIN LOGIC
###############################################################################
def display_history(phone_number):
    st.title(f"📱 Communication History for {phone_number}")

    with st.spinner('Fetching communication history...'):
        calls = fetch_call_history(phone_number)
        messages = fetch_message_history(phone_number)

    if not calls and not messages:
        st.warning("No communication history found for this number.")
        return

    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📊 Metrics", "📅 Timeline", "📋 Details"])

    with tab1:
        display_metrics(calls, messages)

    with tab2:
        display_timeline(calls, messages)

    with tab3:
        display_full_chronological(calls, messages)

def main():
    st.set_page_config(
        page_title="Communication History",
        page_icon="📱",
        layout="wide"
    )

    query_params = st.query_params
    default_phone = ""
    if "phone" in query_params:
        val = query_params["phone"]
        if isinstance(val, list):
            default_phone = val[0] or ""
        else:
            default_phone = val or ""

    phone_number = st.text_input("Enter phone number:", value=default_phone)
    if phone_number:
        display_history(phone_number)
    else:
        st.error("Please provide a phone number.")

if __name__ == "__main__":
    main()
