import streamlit as st
import requests
from datetime import datetime
import phonenumbers

###############################################################################
# 1) YOUR API KEY
###############################################################################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

###############################################################################
# 2) PHONE NUMBER MAP (ID -> {phone, name})
#    We ONLY display 'name' for calls, ignoring the phone field.
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
# 3) PARSE/FORMAT PHONE
###############################################################################
def format_phone_number_str(num_str: str) -> str:
    """Try to parse num_str as US E.164; fallback to original if parse fails."""
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
# 4) API CALLS
###############################################################################
def get_openphone_numbers():
    url = "https://api.openphone.com/v1/phone-numbers"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        return r.json().get("data", [])
    return []

def fetch_call_history(phone_number: str):
    e164 = format_phone_number_str(phone_number)
    if not e164:
        return []
    out=[]
    for pn in get_openphone_numbers():
        phone_number_id = pn.get("id")
        if phone_number_id:
            url = "https://api.openphone.com/v1/calls"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [e164],
                "maxResults": 100
            }
            resp = requests.get(url, headers=HEADERS, params=params)
            if resp.status_code==200:
                out.extend(resp.json().get("data", []))
    return out

def fetch_message_history(phone_number: str):
    e164 = format_phone_number_str(phone_number)
    if not e164:
        return []
    out=[]
    for pn in get_openphone_numbers():
        phone_number_id = pn.get("id")
        if phone_number_id:
            url="https://api.openphone.com/v1/messages"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [e164],
                "maxResults":100
            }
            resp = requests.get(url, headers=HEADERS, params=params)
            if resp.status_code==200:
                out.extend(resp.json().get("data", []))
    return out

def fetch_call_transcript(call_id: str):
    url=f"https://api.openphone.com/v1/call-transcripts/{call_id}"
    resp=requests.get(url, headers=HEADERS)
    if resp.status_code==200:
        return resp.json().get("data",{})
    return None

###############################################################################
# 5) CALL FROM/TO USING phoneNumberId + direction
###############################################################################
def unify_direction(direction: str):
    """
    Some calls have 'incoming'/'outgoing' instead of 'inbound'/'outbound'.
    We'll unify them to 'inbound' or 'outbound' if possible.
    """
    d = direction.lower()
    if d in ("inbound","incoming"):
        return "inbound"
    elif d in ("outbound","outgoing"):
        return "outbound"
    else:
        return "unknown"

def get_call_from_to(call_data, typed_phone: str):
    """
    1) We find the internal line name from phoneNumberId in PHONE_NUMBER_MAP
    2) If direction=inbound => from=typed_phone, to=(just the name)
    3) If direction=outbound => from=(just the name), to=typed_phone
    4) If not found in map => "Unknown Internal"
    """
    p_id = call_data.get("phoneNumberId","")
    info = PHONE_NUMBER_MAP.get(p_id, {"phone":"???","name":"Unknown Internal"})
    line_name = info["name"] or "Unknown Internal"

    direction = unify_direction(call_data.get("direction",""))
    e164_typed = format_phone_number_str(typed_phone) or "Unknown External"

    if direction=="inbound":
        return (e164_typed, line_name)
    elif direction=="outbound":
        return (line_name, e164_typed)
    else:
        # fallback if direction unknown
        return (line_name, e164_typed)

def format_duration_seconds(sec):
    if not sec or sec<0:
        return "0m 00s"
    sec=int(sec)
    m,s=divmod(sec,60)
    return f"{m}m {s:02d}s"

def get_msg_from_to(msg_data):
    # We'll do normal from=..., to=..., ignoring phoneNumberId
    # as messages are usually correct
    m_from = msg_data.get("from","Unknown")
    if not isinstance(m_from,str):
        m_from="Unknown"
    to_list = msg_data.get("to",[])
    if not isinstance(to_list, list):
        to_list=[]
    if to_list:
        to_str = ", ".join(to_list)
    else:
        to_str = "Unknown"
    return (m_from, to_str)

###############################################################################
# 6) METRICS, TIMELINE, DETAILS
###############################################################################
def display_metrics(calls, messages):
    st.header("📊 Metrics")

    # unify direction
    for c in calls:
        c["direction"] = unify_direction(c.get("direction",""))
    inbound_calls = [c for c in calls if c["direction"]=="inbound"]
    outbound_calls= [c for c in calls if c["direction"]=="outbound"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Calls", len(calls))
    col2.metric("Messages", len(messages))
    col3.metric("Inbound Calls", len(inbound_calls))
    col4.metric("Outbound Calls", len(outbound_calls))

def display_timeline(calls, messages, typed_phone: str):
    st.header("📅 Timeline (Descending)")

    # build a combined list
    items=[]
    for c in calls:
        dt = datetime.fromisoformat(c["createdAt"].replace("Z","+00:00"))
        direction=unify_direction(c.get("direction",""))
        fr, to_ = get_call_from_to(c, typed_phone)
        items.append({
            "time":dt,
            "type":"Call",
            "direction":direction,
            "from":fr,
            "to":to_,
            "duration":c.get("duration",0),
            "status":c.get("status","unknown"),
            "id":c.get("id"),
            "text":""
        })
    for m in messages:
        dt = datetime.fromisoformat(m["createdAt"].replace("Z","+00:00"))
        direction=unify_direction(m.get("direction",""))
        fr, to_ = get_msg_from_to(m)
        items.append({
            "time":dt,
            "type":"Message",
            "direction":direction,
            "from":fr,
            "to":to_,
            "duration":0,
            "status":m.get("status","unknown"),
            "id":m.get("id"),
            "text":m.get("text","No content")
        })

    # newest first
    items.sort(key=lambda x:x["time"], reverse=True)

    for i, it in enumerate(items):
        # alternate background: even -> #f9f9f9, odd-> #ffffff
        bg = "#f9f9f9" if i%2==0 else "#ffffff"
        # arrow
        if it["direction"]=="inbound":
            arrow="⬅️"
        elif it["direction"]=="outbound":
            arrow="➡️"
        else:
            arrow="↕️"

        t_str = it["time"].strftime("%Y-%m-%d %H:%M")
        # one line label
        label = f"{'📞' if it['type']=='Call' else '💬'} {arrow} {t_str}"

        # we'll just display in a box, not an expander
        st.markdown(
            f"""
            <div style="background-color:{bg}; padding:8px; margin-bottom:6px;">
              <strong>{label}</strong><br/>
              <strong>From:</strong> {it['from']}<br/>
              <strong>To:</strong> {it['to']}<br/>
              <strong>Direction:</strong> {it['direction']}<br/>
            """,
            unsafe_allow_html=True
        )

        if it["type"]=="Call":
            # Show duration
            if it["status"]=="missed":
                st.markdown("<strong>Status:</strong> MISSED", unsafe_allow_html=True)
            else:
                dur_str = format_duration_seconds(it["duration"])
                st.markdown(f"<strong>Duration:</strong> {dur_str}", unsafe_allow_html=True)

            # fetch transcript
            call_tr = fetch_call_transcript(it["id"])
            if call_tr and call_tr.get("dialogue"):
                st.markdown("**Transcript:**", unsafe_allow_html=True)
                for seg in call_tr["dialogue"]:
                    spkr = seg.get("identifier","???")
                    txt  = seg.get("content","")
                    st.markdown(f"&nbsp;&nbsp;&nbsp;{spkr}: {txt}", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)  # close the box
        else:
            # a message
            st.markdown(f"<strong>Message:</strong> {it['text']}", unsafe_allow_html=True)
            st.markdown(f"<strong>Status:</strong> {it['status']}", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

def display_full_conversation_desc(calls, messages, typed_phone: str):
    st.header("📋 Full Conversation (Newest First)")

    items=[]
    for c in calls:
        dt = datetime.fromisoformat(c["createdAt"].replace("Z","+00:00"))
        direction=unify_direction(c.get("direction",""))
        fr, to_ = get_call_from_to(c, typed_phone)
        items.append({
            "time":dt,
            "type":"Call",
            "direction":direction,
            "from":fr,
            "to":to_,
            "duration":c.get("duration",0),
            "status":c.get("status","unknown"),
            "id":c.get("id"),
            "text":""
        })
    for m in messages:
        dt = datetime.fromisoformat(m["createdAt"].replace("Z","+00:00"))
        direction=unify_direction(m.get("direction",""))
        fr, to_ = get_msg_from_to(m)
        items.append({
            "time":dt,
            "type":"Message",
            "direction":direction,
            "from":fr,
            "to":to_,
            "duration":0,
            "status":m.get("status","unknown"),
            "id":m.get("id"),
            "text":m.get("text","No content")
        })

    items.sort(key=lambda x:x["time"], reverse=True)

    for i, it in enumerate(items):
        bg = "#f9f9f9" if i%2==0 else "#ffffff"
        if it["direction"]=="inbound":
            arrow="⬅️"
        elif it["direction"]=="outbound":
            arrow="➡️"
        else:
            arrow="↕️"

        t_str = it["time"].strftime("%Y-%m-%d %H:%M")
        label = f"{'📞' if it['type']=='Call' else '💬'} {arrow} {t_str}"

        st.markdown(
            f"""
            <div style="background-color:{bg}; padding:8px; margin-bottom:6px;">
              <strong>{label}</strong><br/>
              <strong>From:</strong> {it['from']}<br/>
              <strong>To:</strong> {it['to']}<br/>
              <strong>Direction:</strong> {it['direction']}<br/>
            """,
            unsafe_allow_html=True
        )

        if it["type"]=="Call":
            if it["status"]=="missed":
                st.markdown("<strong>Status:</strong> MISSED", unsafe_allow_html=True)
            else:
                dur_str = format_duration_seconds(it["duration"])
                st.markdown(f"<strong>Duration:</strong> {dur_str}", unsafe_allow_html=True)

            call_tr = fetch_call_transcript(it["id"])
            if call_tr and call_tr.get("dialogue"):
                st.markdown("**Transcript:**", unsafe_allow_html=True)
                for seg in call_tr["dialogue"]:
                    spkr=seg.get("identifier","???")
                    txt =seg.get("content","")
                    st.markdown(f"&nbsp;&nbsp;&nbsp;{spkr}: {txt}", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<strong>Message:</strong> {it['text']}", unsafe_allow_html=True)
            st.markdown(f"<strong>Status:</strong> {it['status']}", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

###############################################################################
# MAIN
###############################################################################
def display_history(user_phone):
    st.title(f"📱 Communication History for {user_phone}")

    with st.spinner("Loading..."):
        calls_data    = fetch_call_history(user_phone)
        messages_data = fetch_message_history(user_phone)

    if not calls_data and not messages_data:
        st.warning("No communication history found for this number.")
        return

    # Show 3 tabs
    tab1, tab2, tab3 = st.tabs(["📊 Metrics", "📅 Timeline", "📋 Details"])
    with tab1:
        display_metrics(calls_data, messages_data)
    with tab2:
        display_timeline(calls_data, messages_data, typed_phone=user_phone)
    with tab3:
        display_full_conversation_desc(calls_data, messages_data, typed_phone=user_phone)

def main():
    st.set_page_config(page_title="Communication History",
                       page_icon="📱",
                       layout="wide")

    # get phone from query param or input
    q = st.query_params
    def_ph=""
    if "phone" in q:
        val=q["phone"]
        if isinstance(val,list):
            def_ph=val[0] or ""
        else:
            def_ph=val
    typed_phone = st.text_input("Enter phone number (US #, auto E.164 for calls):", def_ph)

    if typed_phone:
        display_history(typed_phone)
    else:
        st.error("Please provide a phone number.")

if __name__=="__main__":
    main()
