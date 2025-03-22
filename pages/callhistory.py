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
    return num_str

def get_openphone_numbers():
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
    For calls, we prefer to parse 'participants' first:
      each participant is a dict with 'direction' (source/destination) 
      and 'phoneNumber'.
    If that fails, fallback to call_data['from'] / call_data['to'].

    This ensures we see the actual phone numbers 
    even if call_data['from']/['to'] is missing or partial.
    """
    from_num = "Unknown"
    to_num = "Unknown"

    participants = call_data.get("participants", [])
    # First, try participants array
    if participants:
        for p in participants:
            if isinstance(p, dict):
                p_dir = p.get('direction','')
                p_ph  = p.get('phoneNumber','')
                # Format to E.164 if possible
                p_ph  = format_phone_number_str(p_ph)
                if p_dir == 'source' and from_num == "Unknown":
                    from_num = p_ph or "Unknown"
                elif p_dir == 'destination' and to_num == "Unknown":
                    to_num = p_ph or "Unknown"

    # If from_num / to_num are still "Unknown," fallback
    if from_num == "Unknown":
        c_from = call_data.get("from","")
        if isinstance(c_from, dict):
            c_from = c_from.get("phoneNumber","")
        from_num = format_phone_number_str(c_from) or "Unknown"

    if to_num == "Unknown":
        c_to = call_data.get("to","")
        if isinstance(c_to, dict):
            c_to = c_to.get("phoneNumber","")
        to_num = format_phone_number_str(c_to) or "Unknown"

    return (from_num, to_num)

def get_msg_from_to(msg_data):
    """
    For messages, doc says:
      "from": "+15555550123" (string)
      "to":   ["+15555550123"] (array of strings)
    We'll parse them to E.164 if possible, 
    then combine 'to' array with commas if multiple.
    """
    m_from = msg_data.get("from","")
    if not isinstance(m_from, str):
        m_from = ""
    m_from = format_phone_number_str(m_from) if m_from else "Unknown"

    m_to_list = msg_data.get("to",[])
    if not isinstance(m_to_list, list):
        m_to_list = []
    # format each in E.164
    m_to_list = [format_phone_number_str(x) for x in m_to_list if x]

    if m_to_list:
        m_to = ", ".join(m_to_list)
    else:
        m_to = "Unknown"

    if not m_from:
        m_from = "Unknown"
    return (m_from, m_to)

###################### METRICS / TIMELINE / DETAILS ######################
def display_metrics(calls, messages):
    st.header("📊 Communication Metrics")

    total_calls = len(calls)
    total_messages = len(messages)
    inbound_calls = [c for c in calls if c.get('direction') == 'inbound']
    outbound_calls = [c for c in calls if c.get('direction') == 'outbound']
    inbound_voicemails = [c for c in inbound_calls if c.get('status') == 'voicemail']

    col1, col2, col3, col4, col5 = st.columns(5)
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

    st.subheader("Call Durations")
    durations = [c.get('duration', 0) for c in calls if c.get('duration')]
    if durations:
        avg_duration = sum(durations)/len(durations)
        max_duration = max(durations)
        cA, cB = st.columns(2)
        with cA:
            st.metric("Avg (sec)", f"{avg_duration:.1f}")
        with cB:
            st.metric("Longest (sec)", max_duration)

    st.subheader("Message Lengths")
    msg_lens = [len(m.get('text','')) for m in messages if m.get('text')]
    if msg_lens:
        avg_len = sum(msg_lens)/len(msg_lens)
        st.metric("Avg Message (chars)", f"{avg_len:.1f}")

def display_timeline(calls, messages):
    st.header("📅 Timeline (Descending)")

    timeline = []
    # calls
    for c in calls:
        dt = datetime.fromisoformat(c['createdAt'].replace('Z','+00:00'))
        c_from, c_to = get_call_from_to(c)
        timeline.append({
            'time': dt,
            'type': 'Call',
            'direction': c.get('direction','unknown'),
            'from': c_from,
            'to': c_to,
            'duration': c.get('duration',0),
            'status': c.get('status','unknown'),
            'id': c.get('id'),
            'text': ""
        })
    # messages
    for m in messages:
        dt = datetime.fromisoformat(m['createdAt'].replace('Z','+00:00'))
        m_from, m_to = get_msg_from_to(m)
        timeline.append({
            'time': dt,
            'type': 'Message',
            'direction': m.get('direction','unknown'),
            'from': m_from,
            'to': m_to,
            'status': m.get('status','unknown'),
            'id': m.get('id'),
            'text': m.get('text','')
        })
    timeline.sort(key=lambda x:x['time'], reverse=True)

    for item in timeline:
        t_str = item['time'].strftime("%Y-%m-%d %H:%M")
        icon = "📞" if item['type']=='Call' else "💬"
        dir_icon = "⬅️" if item['direction']=='inbound' else "➡️"
        label = f"{icon} {dir_icon} {t_str}"

        with st.expander(label):
            st.write(f"**From:** {item['from']}")
            st.write(f"**To:**   {item['to']}")
            st.write(f"**Direction:** {item['direction']}")
            if item['type']=='Call':
                if item['status']=='missed':
                    st.write("**Status:** MISSED")
                else:
                    dur_str = format_duration_seconds(item['duration'])
                    st.write(f"**Duration:** {dur_str}")
                # transcripts
                call_tr = fetch_call_transcript(item['id'])
                if call_tr and call_tr.get("dialogue"):
                    st.write("**Transcript:**")
                    for seg in call_tr["dialogue"]:
                        spkr = seg.get('identifier','???')
                        txt  = seg.get('content','')
                        st.write(f"{spkr}: {txt}")
            else:
                st.write(f"**Message:** {item['text']}")
                st.write(f"**Status:** {item['status']}")

def display_full_chronological(calls, messages):
    st.header("📋 Full Conversation (Ascending)")

    comms=[]
    for c in calls:
        dt = datetime.fromisoformat(c['createdAt'].replace('Z','+00:00'))
        c_from, c_to = get_call_from_to(c)
        comms.append({
            'time': dt,
            'type': 'call',
            'direction': c.get('direction','unknown'),
            'from': c_from,
            'to': c_to,
            'duration': c.get('duration',0),
            'status': c.get('status','unknown'),
            'id': c.get('id'),
            'text':""
        })
    for m in messages:
        dt = datetime.fromisoformat(m['createdAt'].replace('Z','+00:00'))
        m_from, m_to = get_msg_from_to(m)
        comms.append({
            'time': dt,
            'type': 'message',
            'direction': m.get('direction','unknown'),
            'from': m_from,
            'to': m_to,
            'text': m.get('text',''),
            'status': m.get('status','unknown'),
            'id': m.get('id'),
            'duration':0
        })

    comms.sort(key=lambda x:x['time'])

    for i, item in enumerate(comms):
        t_str = item['time'].strftime("%Y-%m-%d %H:%M")
        dir_str = item['direction']
        if item['type']=='call':
            if item['status']=='missed':
                st.write(f"**{t_str}** {dir_str} call from {item['from']} to {item['to']} [MISSED]")
            else:
                dur_str = format_duration_seconds(item['duration'])
                st.write(f"**{t_str}** {dir_str} call from {item['from']} to {item['to']} ({dur_str})")
                if item['status']!='missed':
                    call_tr = fetch_call_transcript(item['id'])
                    if call_tr and call_tr.get('dialogue'):
                        for seg in call_tr['dialogue']:
                            spkr = seg.get('identifier','???')
                            txt  = seg.get('content','')
                            st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;**{spkr}:** {txt}", unsafe_allow_html=True)
        else:
            # message
            st.write(f"**{t_str}** {dir_str} message from {item['from']} to {item['to']}: {item['text']}")

        if i<len(comms)-1:
            st.markdown("<hr style='border:1px solid #ccc;'/>", unsafe_allow_html=True)

###############################################################################
# MAIN
###############################################################################
def display_history(phone_number):
    st.title(f"📱 Communication History for {phone_number}")

    with st.spinner("Loading history..."):
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
        display_full_chronological(calls, messages)

def main():
    st.set_page_config(
        page_title="Communication History",
        page_icon="📱",
        layout="wide"
    )

    # Attempt to read phone from query params or from text input
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
