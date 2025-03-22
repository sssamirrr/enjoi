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
def format_phone_number_str(num_str: str) -> str:
    """
    Attempt to parse num_str as a US phone number and produce an E.164 
    string (e.g., '+17168600690'). 
    If parsing fails, return the original user input.
    """
    if not num_str:
        return ""
    try:
        parsed = phonenumbers.parse(num_str, "US")
        if phonenumbers.is_valid_number(parsed):
            return f"+{parsed.country_code}{parsed.national_number}"
    except Exception:
        pass
    # fallback if parse fails
    return num_str

def get_openphone_numbers():
    """Return a list of your OpenPhone numbers from the API."""
    url = "https://api.openphone.com/v1/phone-numbers"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("data", [])
    return []

def fetch_call_history(phone_number: str):
    """
    Fetch call history from OpenPhone using an E.164 US format
    if possible, else the raw input if parse fails.
    """
    from_num = format_phone_number_str(phone_number)
    if not from_num:
        return []
    all_calls = []
    for op_number in get_openphone_numbers():
        phone_number_id = op_number.get("id")
        if phone_number_id:
            url = "https://api.openphone.com/v1/calls"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [from_num],
                "maxResults": 100
            }
            resp = requests.get(url, headers=HEADERS, params=params)
            if resp.status_code == 200:
                all_calls.extend(resp.json().get("data", []))
    return all_calls

def fetch_message_history(phone_number: str):
    """
    Fetch message history from OpenPhone using an E.164 US format
    if possible, else the raw input if parse fails.
    """
    from_num = format_phone_number_str(phone_number)
    if not from_num:
        return []
    all_msgs = []
    for op_number in get_openphone_numbers():
        phone_number_id = op_number.get("id")
        if phone_number_id:
            url = "https://api.openphone.com/v1/messages"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [from_num],
                "maxResults": 100
            }
            resp = requests.get(url, headers=HEADERS, params=params)
            if resp.status_code == 200:
                all_msgs.extend(resp.json().get("data", []))
    return all_msgs

def fetch_call_transcript(call_id: str):
    """Fetch transcript lines for a given call ID."""
    url = f"https://api.openphone.com/v1/call-transcripts/{call_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("data", {})
    return None

def format_duration_seconds(sec):
    """
    Convert integer/float 'sec' -> "Xm YYs".
    Example: 185 -> "3m 05s"
    """
    if not sec or sec < 0:
        return "0m 00s"
    sec = int(sec)
    m, s = divmod(sec, 60)
    return f"{m}m {s:02d}s"

def get_call_from_to(call_data):
    """
    For calls, 'from' & 'to' might be strings or dicts with 'phoneNumber'.
    Return (str_from, str_to).
    """
    c_from = call_data.get("from", "")
    c_to   = call_data.get("to", "")
    
    # If dict, get .get('phoneNumber')
    if isinstance(c_from, dict):
        c_from = c_from.get("phoneNumber", "")
    if isinstance(c_to, dict):
        c_to = c_to.get("phoneNumber", "")

    c_from = format_phone_number_str(c_from) if c_from else ""
    c_to   = format_phone_number_str(c_to)   if c_to   else ""

    # fallback
    if not c_from:
        c_from = "Unknown"
    if not c_to:
        c_to = "Unknown"

    return c_from, c_to

def get_msg_from_to(msg_data):
    """
    For messages, doc says: 
      "from": "+15555550123" (string)
      "to": ["+15555550123"] (array of strings)
    Return (str_from, str_to).
    If there's multiple recipients in 'to', we join them with commas.
    """
    m_from = msg_data.get("from", "")
    if not isinstance(m_from, str):
        m_from = ""
    # parse to E.164 if possible
    m_from = format_phone_number_str(m_from) if m_from else ""

    m_to_list = msg_data.get("to", [])
    if not isinstance(m_to_list, list):
        m_to_list = []
    # parse each
    m_to_list = [format_phone_number_str(x) for x in m_to_list if x]
    m_to = ", ".join(m_to_list) if m_to_list else ""

    if not m_from:
        m_from = "Unknown"
    if not m_to:
        m_to = "Unknown"

    return (m_from, m_to)

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
    msg_lengths = [len(m.get('text', '')) for m in messages if m.get('text')]
    if msg_lengths:
        avg_length = sum(msg_lengths) / len(msg_lengths)
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
        c_from, c_to = get_call_from_to(c)
        timeline.append({
            'time': t,
            'type': 'Call',
            'direction': c.get('direction', 'unknown'),
            'duration': c.get('duration', 0),
            'status': c.get('status', 'unknown'),
            'id': c.get('id'),
            'from': c_from,
            'to': c_to
        })

    # Prepare messages
    for m in messages:
        t = datetime.fromisoformat(m['createdAt'].replace('Z', '+00:00'))
        m_from, m_to = get_msg_from_to(m)
        timeline.append({
            'time': t,
            'type': 'Message',
            'direction': m.get('direction', 'unknown'),
            'text': m.get('text', 'No content'),
            'status': m.get('status', 'unknown'),
            'id': m.get('id'),
            'from': m_from,
            'to': m_to
        })

    # Sort descending
    timeline.sort(key=lambda x: x['time'], reverse=True)

    for item in timeline:
        time_str = item['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if item['type'] == "Call" else "💬"
        direction_icon = "⬅️" if item['direction'] == "inbound" else "➡️"
        label = f"{icon} {direction_icon} {time_str}"

        with st.expander(label):
            st.write(f"**From:** {item['from']}")
            st.write(f"**To:**   {item['to']}")
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
# CHRONOLOGICAL DETAILS (TAB 3) - WITH A VISUAL SEPARATOR
###############################################################################
def display_full_chronological(calls, messages):
    """
    Show calls & messages in ascending chronological order,
    with transcripts for non-missed calls, phone numbers from 'from'/'to' fields,
    and a horizontal rule between items.
    """
    st.header("Full Conversation (Chronological)")

    comms = []

    # Add calls
    for c in calls:
        t = datetime.fromisoformat(c['createdAt'].replace('Z', '+00:00'))
        c_from, c_to = get_call_from_to(c)
        comms.append({
            'time': t,
            'type': 'call',
            'direction': c.get('direction','unknown'),
            'from': c_from,
            'to': c_to,
            'status': c.get('status', 'unknown'),
            'duration': c.get('duration', 0),
            'id': c.get('id')
        })

    # Add messages
    for m in messages:
        t = datetime.fromisoformat(m['createdAt'].replace('Z', '+00:00'))
        m_from, m_to = get_msg_from_to(m)
        comms.append({
            'time': t,
            'type': 'message',
            'direction': m.get('direction','unknown'),
            'from': m_from,
            'to': m_to,
            'text': m.get('text','No content')
        })

    # Sort ascending
    comms.sort(key=lambda x: x['time'])

    for idx, item in enumerate(comms):
        ts_str = item['time'].strftime("%Y-%m-%d %H:%M")
        dir_str = item['direction']

        if item['type'] == 'call':
            # If missed
            if item['status'] == 'missed':
                st.write(
                    f"**{ts_str}** {dir_str} **call** from {item['from']} "
                    f"to {item['to']} [MISSED]"
                )
            else:
                # Show duration
                dur_str = format_duration_seconds(item['duration'])
                st.write(
                    f"**{ts_str}** {dir_str} **call** from {item['from']} "
                    f"to {item['to']} ({dur_str})"
                )
                # Print transcript if not missed
                transcript = fetch_call_transcript(item['id'])
                if transcript and transcript.get('dialogue'):
                    for seg in transcript['dialogue']:
                        spkr = seg.get('identifier','???')
                        cnt  = seg.get('content','')
                        # Indent transcript lines
                        st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;**{spkr}:** {cnt}", unsafe_allow_html=True)
        else:
            # It's a message
            st.write(
                f"**{ts_str}** {dir_str} **message** from {item['from']} "
                f"to {item['to']}: {item.get('text','')}"
            )

        # Add a horizontal rule after each item
        if idx < len(comms) - 1:
            st.markdown("<hr style='border:1px solid #ddd;'/>", unsafe_allow_html=True)

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

    # Grab phone from query params or text input
    query_params = st.query_params
    default_phone = ""
    if "phone" in query_params:
        val = query_params["phone"]
        if isinstance(val, list):
            default_phone = val[0] or ""
        else:
            default_phone = val or ""

    phone_number = st.text_input(
        "Enter phone number (US #, will be auto-converted to E.164):",
        value=default_phone
    )
    if phone_number:
        display_history(phone_number)
    else:
        st.error("Please provide a phone number.")

if __name__ == "__main__":
    main()
