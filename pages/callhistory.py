import streamlit as st
import requests
from datetime import datetime
import phonenumbers

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
    if response.status_code != 200:
        st.error(f"Failed to fetch OpenPhone numbers: {response.text}")
        return []
    return response.json().get("data", [])

def fetch_call_history(phone_number):
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
                calls = response.json().get("data", [])
                for call in calls:
                    call["transcriptLink"] = call.get("transcript", {}).get("url", None)
                all_calls.extend(calls)
    return all_calls

def fetch_message_history(phone_number):
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
                messages = response.json().get("data", [])
                for message in messages:
                    message["transcriptLink"] = message.get("transcript", {}).get("url", None)
                all_messages.extend(messages)
    return all_messages

def display_timeline(calls, messages):
    st.header("\ud83d\udcc5 Communication Timeline")

    communications = []

    for call in calls:
        communications.append({
            'time': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction', 'unknown'),
            'duration': call.get('duration', 'N/A'),
            'status': call.get('status', 'unknown'),
            'transcriptLink': call.get('transcriptLink')
        })

    for message in messages:
        communications.append({
            'time': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction', 'unknown'),
            'content': message.get('content', 'No content'),
            'status': message.get('status', 'unknown'),
            'transcriptLink': message.get('transcriptLink')
        })

    communications.sort(key=lambda x: x['time'], reverse=True)

    for comm in communications:
        time_str = comm['time'].strftime("%Y-%m-%d %H:%M")
        icon = "\ud83d\udcde" if comm['type'] == "Call" else "\ud83d\udcac"
        direction_icon = "\u2b05\ufe0f" if comm['direction'] == "inbound" else "\u27a1\ufe0f"

        with st.expander(f"{icon} {direction_icon} {time_str}"):
            if comm['type'] == "Call":
                st.write(f"**Duration:** {comm['duration']} seconds")
            else:
                st.write(f"**Message:** {comm['content']}")
            st.write(f"**Status:** {comm['status']}")
            if comm['transcriptLink']:
                st.markdown(f"[View Transcript]({comm['transcriptLink']})", unsafe_allow_html=True)

def display_history(phone_number):
    st.title(f"\ud83d\udcde Communication History for {phone_number}")

    with st.spinner('Fetching communication history...'):
        calls = fetch_call_history(phone_number)
        messages = fetch_message_history(phone_number)

    if not calls and not messages:
        st.warning("No communication history found for this number.")
        return

    tab1, tab2 = st.tabs(["\ud83d\udcc5 Timeline", "\ud83d\udcc3 Details"])

    with tab1:
        display_timeline(calls, messages)

    with tab2:
        st.header("Detailed History")
        show_calls = st.checkbox("Show Calls", True)
        show_messages = st.checkbox("Show Messages", True)

        if show_calls:
            st.subheader("\ud83d\udcde Calls")
            for call in sorted(calls, key=lambda x: x['createdAt'], reverse=True):
                call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                direction = "Incoming" if call.get('direction') == 'inbound' else "Outgoing"
                transcript_link = call.get('transcriptLink')
                st.write(f"**{call_time}** - {direction} call ({call.get('duration', 'N/A')} seconds)")
                if transcript_link:
                    st.markdown(f"[View Transcript]({transcript_link})", unsafe_allow_html=True)

        if show_messages:
            st.subheader("\ud83d\udcac Messages")
            for message in sorted(messages, key=lambda x: x['createdAt'], reverse=True):
                message_time = datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                direction = "Received" if message.get('direction') == 'inbound' else "Sent"
                transcript_link = message.get('transcriptLink')
                st.write(f"**{message_time}** - {direction}: {message.get('content', 'No content')}")
                if transcript_link:
                    st.markdown(f"[View Transcript]({transcript_link})", unsafe_allow_html=True)

def main():
    st.set_page_config(
        page_title="Communication History",
        page_icon="\ud83d\udcde",
        layout="wide"
    )

    query_params = st.experimental_get_query_params()
    phone_number = query_params.get("phone", [""])[0]

    if phone_number:
        display_history(phone_number)
    else:
        st.error("Please provide a phone number in the URL using ?phone=PHONENUMBER")

if __name__ == "__main__":
    main()
