import streamlit as st
import requests
from datetime import datetime
import phonenumbers

OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

def format_phone_number_str(num_str: str) -> str:
    """Try to parse num_str as a US number, return E.164 if valid, else original."""
    if not num_str:
        return ""
    try:
        parsed = phonenumbers.parse(num_str, "US")
        if phonenumbers.is_valid_number(parsed):
            return f"+{parsed.country_code}{parsed.national_number}"
    except:
        pass
    return num_str

def get_openphone_numbers():
    url = "https://api.openphone.com/v1/phone-numbers"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        return resp.json().get("data", [])
    return []

def fetch_call_history(phone_number: str):
    e164_num = format_phone_number_str(phone_number)
    if not e164_num:
        return []
    all_calls = []
    for op_number in get_openphone_numbers():
        phone_number_id = op_number.get("id")
        if phone_number_id:
            url = "https://api.openphone.com/v1/calls"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [e164_num],
                "maxResults": 100
            }
            r = requests.get(url, headers=HEADERS, params=params)
            if r.status_code == 200:
                all_calls.extend(r.json().get("data", []))
    return all_calls

def fetch_message_history(phone_number: str):
    e164_num = format_phone_number_str(phone_number)
    if not e164_num:
        return []
    all_msgs = []
    for op_number in get_openphone_numbers():
        phone_number_id = op_number.get("id")
        if phone_number_id:
            url = "https://api.openphone.com/v1/messages"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [e164_num],
                "maxResults": 100
            }
            r = requests.get(url, headers=HEADERS, params=params)
            if r.status_code == 200:
                all_msgs.extend(r.json().get("data", []))
    return all_msgs

def fetch_call_transcript(call_id: str):
    url = f"https://api.openphone.com/v1/call-transcripts/{call_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        return resp.json().get("data", {})
    return None

def format_duration_seconds(sec):
    if not sec or sec < 0:
        return "0m 00s"
    sec = int(sec)
    m, s = divmod(sec, 60)
    return f"{m}m {s:02d}s"

def handle_call_participants(direction: str, user_phone: str):
    """
    We ignore participants or call['from']/call['to'] entirely.
    - For inbound => from=user_phone, to="OpenPhone"
    - For outbound => from="OpenPhone", to=user_phone
    """
    user_e164 = format_phone_number_str(user_phone) or "Unknown"
    if direction == "inbound":
        return (user_e164, "OpenPhone")
    elif direction == "outbound":
        return ("OpenPhone", user_e164)
    else:
        return (user_e164, "OpenPhone")  # fallback if direction is unknown

def handle_message_participants(msg_data):
    """
    We keep the standard logic from the doc:
    'from' => a single phone string,
    'to' => list of phone strings => we join them
    """
    m_from = msg_data.get("from","") or "Unknown"
    if not isinstance(m_from, str):
        m_from = "Unknown"
    to_list = msg_data.get("to", [])
    if not isinstance(to_list, list):
        to_list = []
    # join them
    to_str = ", ".join(to_list) if to_list else "Unknown"
    return (m_from, to_str)

####################### METRICS, TIMELINE, DETAILS #######################
def display_metrics(calls, messages):
    st.header("📊 Communication Metrics")

    total_calls = len(calls)
    total_messages = len(messages)
    inbound_calls = [c for c in calls if c.get('direction') == 'inbound']
    outbound_calls = [c for c in calls if c.get('direction') == 'outbound']

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
        # optionally do voicemails
        voicemails = [c for c in calls if c.get('status')=='voicemail']
        st.metric("Voicemails", len(voicemails))

def display_timeline(calls, messages, user_phone: str):
    st.header("📅 Timeline (Descending)")

    timeline = []
    for c in calls:
        dt = datetime.fromisoformat(c['createdAt'].replace('Z','+00:00'))
        direction = c.get('direction','unknown')
        from_num, to_num = handle_call_participants(direction, user_phone)
        timeline.append({
            'time': dt,
            'type': 'Call',
            'direction': direction,
            'from': from_num,
            'to': to_num,
            'duration': c.get('duration',0),
            'status': c.get('status','unknown'),
            'id': c.get('id'),
            'text': ""
        })

    for m in messages:
        dt = datetime.fromisoformat(m['createdAt'].replace('Z','+00:00'))
        direction = m.get('direction','unknown')
        from_num, to_num = handle_message_participants(m)
        timeline.append({
            'time': dt,
            'type': 'Message',
            'direction': direction,
            'from': from_num,
            'to': to_num,
            'status': m.get('status','unknown'),
            'id': m.get('id'),
            'text': m.get('text','No content'),
            'duration':0
        })

    # sort descending (newest to oldest)
    timeline.sort(key=lambda x: x['time'], reverse=True)

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
                call_tr = fetch_call_transcript(item['id'])
                if call_tr and call_tr.get('dialogue'):
                    st.write("**Transcript:**")
                    for seg in call_tr['dialogue']:
                        spkr = seg.get('identifier','???')
                        txt  = seg.get('content','')
                        st.write(f"{spkr}: {txt}")
            else:
                st.write(f"**Message:** {item['text']}")
                st.write(f"**Status:** {item['status']}")

def display_full_conversation_descending(calls, messages, user_phone: str):
    """
    Full conversation in newest -> oldest.
    We do the same logic for calls vs. messages,
    but always place calls at the correct from/to based on direction,
    ignoring participants or call['from'] fields.
    """
    st.header("📋 Full Conversation (Newest First)")

    comms = []
    for c in calls:
        dt = datetime.fromisoformat(c['createdAt'].replace('Z','+00:00'))
        direction = c.get('direction','unknown')
        from_num, to_num = handle_call_participants(direction, user_phone)
        comms.append({
            'time': dt,
            'type': 'Call',
            'direction': direction,
            'from': from_num,
            'to': to_num,
            'duration': c.get('duration',0),
            'status': c.get('status','unknown'),
            'id': c.get('id'),
            'text': ""
        })
    for m in messages:
        dt = datetime.fromisoformat(m['createdAt'].replace('Z','+00:00'))
        direction = m.get('direction','unknown')
        from_num, to_num = handle_message_participants(m)
        comms.append({
            'time': dt,
            'type': 'Message',
            'direction': direction,
            'from': from_num,
            'to': to_num,
            'status': m.get('status','unknown'),
            'id': m.get('id'),
            'text': m.get('text','No content'),
            'duration':0
        })

    # sort descending
    comms.sort(key=lambda x: x['time'], reverse=True)

    for i, item in enumerate(comms):
        t_str = item['time'].strftime("%Y-%m-%d %H:%M")
        d_str = item['direction']
        if item['type']=='Call':
            if item['status']=='missed':
                st.write(f"**{t_str}** {d_str} call from {item['from']} to {item['to']} [MISSED]")
            else:
                dur_str = format_duration_seconds(item['duration'])
                st.write(f"**{t_str}** {d_str} call from {item['from']} to {item['to']} ({dur_str})")
                if item['status']!='missed':
                    call_tr = fetch_call_transcript(item['id'])
                    if call_tr and call_tr.get('dialogue'):
                        for seg in call_tr['dialogue']:
                            spkr = seg.get('identifier','???')
                            txt  = seg.get('content','')
                            st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;**{spkr}:** {txt}", unsafe_allow_html=True)
        else:
            st.write(f"**{t_str}** {d_str} message from {item['from']} to {item['to']}: {item['text']}")

        if i < len(comms)-1:
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
        # We pass the user_phone so we can place inbound/outbound calls
        display_timeline(calls, messages, user_phone=phone_number)

    with tab3:
        display_full_conversation_descending(calls, messages, user_phone=phone_number)

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
