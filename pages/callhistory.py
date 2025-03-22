import streamlit as st
import requests
from datetime import datetime
import phonenumbers

OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

###############################################################################
# 1) MAPPING OF phoneNumberId -> { "phone": ..., "name": ... }
###############################################################################
PHONE_NUMBER_MAP = {
    "PNsyKJnJnG": {"phone": "+18438972426", "name": "Samir"},
    "PNPD94sWrs": {"phone": "+18432419969", "name": "Lisa"},
    "PN1TwV9Rt5": {"phone": "+18434179936", "name": "Missy"},
    "PNk6Tx1cp7": {"phone": "+18434385533", "name": "Star"},
    "PNs1mwzuic": {"phone": "+18434179597", "name": "Primary"},
    "PNx6dsCw5T": {"phone": "+18434285482", "name": "Owner Services Shared Line"},
    "PNbK2tV7Vy": {"phone": "+18434387793", "name": "Sarah"},
    "PN2d84ZAyo": {"phone": "+18432794288", "name": "Skylar"},
    "PNCodikitq": {"phone": "+18434285639", "name": "Jamie N"},
    "PNxEKglaCO": {"phone": "+18432419546", "name": "Debony Grapes"},
    "PN2iapapXC": {"phone": "+18434273290", "name": "Primary"},
    "PNKpWDGPSL": {"phone": "+18435854949", "name": "Daniel Wallace"},
    "PNjzABQ0Fk": {"phone": "+18435855608", "name": "Leslie Soto"},
    "PNRhaAEguy": {"phone": "+18432419780", "name": "David"},
    "PNtA6F8XBT": {"phone": "+18438085639", "name": "Adam Price"},
    "PN3IGqw7q6": {"phone": "+19803858169", "name": "Adam Price"},
    "PN4NgOb13s": {"phone": "+18434385764", "name": "Leanne Foster"},
    "PNWDaXfX3j": {"phone": "+18434280171", "name": "Jason P"},
    "PNwcAahsIP": {"phone": "+18437334351", "name": "Primary"},
    "PNLE0H9fEg": {"phone": "+18432419357", "name": "Vacant"},
    "PNa0uaQY9Q": {"phone": "+18433536523", "name": "Karlyn"},
    "PNjcHJguji": {"phone": "+18434273625", "name": "Marlena"},
    "PNAaLtcBHr": {"phone": "+18434287797", "name": "VACANT"},
    "PNG6YH4CQN": {"phone": "+18434298339", "name": "Primary"},
    "PNwDvJZ86q": {"phone": "+18434385435", "name": "Amanda"},
    "PNk2GcXz3L": {"phone": "+18434387649", "name": "Chris B"},
    "PNMA2KQqic": {"phone": "+18434387799", "name": "Bonnie"},
    "PNwyfyJ77m": {"phone": "+18437337467", "name": "Vacant"},
    "PNd0Daor0j": {"phone": "+18438943975", "name": "Ashlynn"},
    "PNjRCueHec": {"phone": "+18438947565", "name": "Frenchie"},
    "PNLIutppas": {"phone": "+18559081919", "name": "Skylar Brundage"},
    "PNW9l66oQA": {"phone": "+18434387297", "name": "Primary"},
    "PNKsfLx1Xc": {"phone": "+18434286810", "name": "Shawn B"},
    "PNHphJ81wy": {"phone": "+18432129399", "name": "Ceejay"},
    "PN4lKkMXz5": {"phone": "+18434285829", "name": "Brian Bashaw"},
    "PNZ5SjPblu": {"phone": "+18434287550", "name": "Thomas Wescott"},
    "PNw4dEFGU1": {"phone": "+13863563138", "name": "Primary"},
}

###############################################################################
# 2) E.164 parse of the external user’s typed phone
###############################################################################
def format_phone_number_str(num_str: str) -> str:
    if not num_str:
        return ""
    try:
        parsed = phonenumbers.parse(num_str, "US")
        if phonenumbers.is_valid_number(parsed):
            return f"+{parsed.country_code}{parsed.national_number}"
    except:
        pass
    return num_str

###############################################################################
# 3) API CALLS
###############################################################################
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

###############################################################################
# 4) SHOW CALL FROM/TO BASED ON phoneNumberId + direction
###############################################################################
def format_duration_seconds(sec):
    if not sec or sec < 0:
        return "0m 00s"
    sec = int(sec)
    m, s = divmod(sec, 60)
    return f"{m}m {s:02d}s"

def get_call_from_to(call_data, external_phone: str):
    """
    - direction=inbound => from=external_phone, to=(internal_line_number + name)
    - direction=outbound => from=(internal_line_number + name), to=external_phone
    We find the internal line via phoneNumberId => PHONE_NUMBER_MAP
    """
    direction = call_data.get("direction","unknown")
    phoneNumberId = call_data.get("phoneNumberId","")

    # Look up your dictionary
    info = PHONE_NUMBER_MAP.get(phoneNumberId, {"phone":"???","name":"???"})
    line_phone = info["phone"]
    line_name  = info["name"]

    # Build the label like "+18434285482 (Owner Services Shared)"
    internal_label = f"{line_phone} ({line_name})" if line_phone!="???" else "Unknown Internal"

    # decide based on direction
    e164_ext = format_phone_number_str(external_phone) or "Unknown External"

    if direction == "inbound":
        return (e164_ext, internal_label)
    elif direction == "outbound":
        return (internal_label, e164_ext)
    else:
        # fallback if direction unknown
        return (e164_ext, internal_label)

def get_msg_from_to(msg_data):
    """
    The normal logic for messages is typically correct:
    'from' is a string, 'to' is a list => we join them.
    We'll just keep it. The user phone is presumably the 'from' or 'to' anyway.
    """
    m_from = msg_data.get("from","") or "Unknown"
    if not isinstance(m_from, str):
        m_from = "Unknown"
    to_list = msg_data.get("to", []) or []
    if not isinstance(to_list, list):
        to_list = []
    if to_list:
        to_str = ", ".join(to_list)
    else:
        to_str = "Unknown"
    return (m_from, to_str)

###############################################################################
# 5) METRICS, TIMELINE, DETAILS
###############################################################################
def display_metrics(calls, messages):
    st.header("📊 Communication Metrics")

    total_calls = len(calls)
    total_messages = len(messages)
    inbound_calls = [c for c in calls if c.get('direction')=='inbound']
    outbound_calls = [c for c in calls if c.get('direction')=='outbound']

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Calls", total_calls)
    with col2:
        st.metric("Messages", total_messages)
    with col3:
        st.metric("Inbound Calls", len(inbound_calls))
    with col4:
        st.metric("Outbound Calls", len(outbound_calls))

def display_timeline(calls, messages, external_phone: str):
    st.header("📅 Timeline (Descending)")

    timeline=[]
    for c in calls:
        dt = datetime.fromisoformat(c["createdAt"].replace("Z","+00:00"))
        from_, to_ = get_call_from_to(c, external_phone)
        timeline.append({
            "time": dt,
            "type":"Call",
            "direction": c.get("direction","unknown"),
            "from": from_,
            "to": to_,
            "duration": c.get("duration",0),
            "status": c.get("status","unknown"),
            "id": c.get("id"),
            "text":""
        })
    for m in messages:
        dt = datetime.fromisoformat(m["createdAt"].replace("Z","+00:00"))
        m_from, m_to = get_msg_from_to(m)
        timeline.append({
            "time": dt,
            "type":"Message",
            "direction": m.get("direction","unknown"),
            "from": m_from,
            "to": m_to,
            "status": m.get("status","unknown"),
            "id": m.get("id"),
            "text": m.get("text","No content"),
            "duration":0
        })

    # sort newest -> oldest
    timeline.sort(key=lambda x:x["time"], reverse=True)

    for item in timeline:
        t_str = item["time"].strftime("%Y-%m-%d %H:%M")
        icon  = "📞" if item["type"]=="Call" else "💬"
        dir_icon = "⬅️" if item["direction"]=="inbound" else "➡️"
        label = f"{icon} {dir_icon} {t_str}"

        with st.expander(label):
            st.write(f"**From:** {item['from']}")
            st.write(f"**To:** {item['to']}")
            st.write(f"**Direction:** {item['direction']}")
            if item["type"]=="Call":
                if item["status"]=="missed":
                    st.write("**Status:** MISSED")
                else:
                    d_str = format_duration_seconds(item["duration"])
                    st.write(f"**Duration:** {d_str}")
                tr = fetch_call_transcript(item["id"])
                if tr and tr.get("dialogue"):
                    st.write("**Transcript:**")
                    for seg in tr["dialogue"]:
                        spkr = seg.get("identifier","???")
                        txt  = seg.get("content","")
                        st.write(f"{spkr}: {txt}")
            else:
                st.write(f"**Message:** {item['text']}")
                st.write(f"**Status:** {item['status']}")

def display_full_conversation_desc(calls, messages, external_phone: str):
    """
    Show calls/messages in DESCENDING order (newest -> oldest).
    EXACT same logic as timeline, but we print in one big list
    with transcripts inline, separated by <hr>.
    """
    st.header("📋 Full Conversation (Newest First)")

    comms=[]
    for c in calls:
        dt = datetime.fromisoformat(c["createdAt"].replace("Z","+00:00"))
        from_, to_ = get_call_from_to(c, external_phone)
        comms.append({
            "time":dt,
            "type":"Call",
            "direction": c.get("direction","unknown"),
            "from": from_,
            "to": to_,
            "duration": c.get("duration",0),
            "status": c.get("status","unknown"),
            "id": c.get("id"),
            "text":""
        })
    for m in messages:
        dt = datetime.fromisoformat(m["createdAt"].replace("Z","+00:00"))
        m_from,m_to = get_msg_from_to(m)
        comms.append({
            "time": dt,
            "type":"Message",
            "direction":m.get("direction","unknown"),
            "from": m_from,
            "to": m_to,
            "status": m.get("status","unknown"),
            "id": m.get("id"),
            "text": m.get("text","No content"),
            "duration":0
        })

    comms.sort(key=lambda x:x["time"], reverse=True)

    for i, item in enumerate(comms):
        t_str = item["time"].strftime("%Y-%m-%d %H:%M")
        d_str = item["direction"]
        if item["type"]=="Call":
            if item["status"]=="missed":
                st.write(f"**{t_str}** {d_str} call from {item['from']} to {item['to']} [MISSED]")
            else:
                dur_str = format_duration_seconds(item["duration"])
                st.write(f"**{t_str}** {d_str} call from {item['from']} to {item['to']} ({dur_str})")
                if item["status"]!="missed":
                    tr = fetch_call_transcript(item["id"])
                    if tr and tr.get("dialogue"):
                        for seg in tr["dialogue"]:
                            spkr = seg.get("identifier","???")
                            txt  = seg.get("content","")
                            st.write(f"&nbsp;&nbsp;&nbsp;&nbsp;**{spkr}:** {txt}", unsafe_allow_html=True)
        else:
            st.write(f"**{t_str}** {d_str} message from {item['from']} to {item['to']}: {item['text']}")

        if i<len(comms)-1:
            st.markdown("<hr style='border:1px solid #ccc;'/>", unsafe_allow_html=True)

###############################################################################
# MAIN
###############################################################################
def display_history(user_phone):
    st.title(f"📱 Communication History for {user_phone}")

    with st.spinner("Loading..."):
        calls_data    = fetch_call_history(user_phone)
        messages_data = fetch_message_history(user_phone)

    if not calls_data and not messages_data:
        st.warning("No communication history found.")
        return

    tab1, tab2, tab3 = st.tabs(["📊 Metrics", "📅 Timeline", "📋 Details"])

    with tab1:
        display_metrics(calls_data, messages_data)

    with tab2:
        display_timeline(calls_data, messages_data, external_phone=user_phone)

    with tab3:
        display_full_conversation_desc(calls_data, messages_data, external_phone=user_phone)

def main():
    st.set_page_config(page_title="Communication History",
                       page_icon="📱",
                       layout="wide")

    query_params = st.query_params
    default_phone = ""
    if "phone" in query_params:
        val = query_params["phone"]
        if isinstance(val, list):
            default_phone = val[0]
        else:
            default_phone = val

    typed_phone = st.text_input("Enter phone number (auto E.164 for calls):",
                                value=default_phone)

    if typed_phone:
        display_history(typed_phone)
    else:
        st.error("Please enter a phone number.")

if __name__=="__main__":
    main()
