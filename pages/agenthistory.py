import streamlit as st
import pandas as pd
import time
import requests
from urllib.parse import urlencode

############################
# 1) OpenPhone API Key     #
############################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"  # or "Bearer j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

############################
# 2) Rate-limited requests #
############################
def rate_limited_request(url, headers, params=None, request_type='get'):
    """
    A helper that respects ~5 requests/second.
    """
    if params is None:
        params = {}
    time.sleep(1/5)
    try:
        if request_type.lower() == 'get':
            resp = requests.get(url, headers=headers, params=params)
        else:
            resp = None

        if resp and resp.status_code == 200:
            return resp.json()
        else:
            st.warning(f"API Error: {resp.status_code}")
            st.warning(f"Response: {resp.text}")
    except Exception as e:
        st.warning(f"Exception: {e}")
    return None

def get_headers():
    return {
        "Authorization": OPENPHONE_API_KEY,  # e.g., "Bearer <API_KEY>"
        "Content-Type": "application/json"
    }

##############################
# 3) Fetch Phone Numbers     #
##############################
def get_phone_numbers():
    """
    Fetch all phone numbers in your workspace.
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    data = rate_limited_request(url, get_headers())
    if not data or "data" not in data:
        return []

    results = []
    for pn in data["data"]:
        pid = pn.get("id", "")
        pnum = pn.get("phoneNumber", "No Number")
        results.append({"id": pid, "phoneNumber": pnum})
    return results

##############################
# 4) Fetch Calls & Messages  #
##############################
def fetch_calls(phone_number_id, max_records=100):
    """
    Fetch up to max_records calls for phoneNumberId, without using participants.
    """
    if not phone_number_id or not phone_number_id.startswith("PN"):
        return []

    calls_url = "https://api.openphone.com/v1/calls"
    all_calls = []
    fetched = 0
    next_token = None

    while True:
        params = {
            "phoneNumberId": phone_number_id,  # No participants param
            "maxResults": 50
        }
        if next_token:
            params["pageToken"] = next_token

        data = rate_limited_request(calls_url, get_headers(), params, 'get')
        if not data or "data" not in data:
            break

        chunk = data["data"]
        all_calls.extend(chunk)
        fetched += len(chunk)

        next_token = data.get("nextPageToken")
        if not next_token or fetched >= max_records:
            break

    return all_calls

def fetch_messages(phone_number_id, max_records=100):
    """
    Fetch up to max_records messages for phoneNumberId, without using participants.
    """
    if not phone_number_id or not phone_number_id.startswith("PN"):
        return []

    msgs_url = "https://api.openphone.com/v1/messages"
    all_msgs = []
    fetched = 0
    next_token = None

    while True:
        params = {
            "phoneNumberId": phone_number_id,  # No participants param
            "maxResults": 50
        }
        if next_token:
            params["pageToken"] = next_token

        data = rate_limited_request(msgs_url, get_headers(), params, 'get')
        if not data or "data" not in data:
            break

        chunk = data["data"]
        all_msgs.extend(chunk)
        fetched += len(chunk)

        next_token = data.get("nextPageToken")
        if not next_token or fetched >= max_records:
            break

    return all_msgs

##############################
# 5) Fetch Full Details      #
##############################
def fetch_call_transcript(call_id):
    """
    GET /v1/call-transcripts/{callId} to get the full dialogue.
    """
    url = f"https://api.openphone.com/v1/call-transcripts/{call_id}"
    data = rate_limited_request(url, get_headers())
    if not data or "data" not in data:
        return None
    return data["data"]

def fetch_full_message(message_id):
    """
    GET /v1/messages/{messageId} to get full content.
    """
    url = f"https://api.openphone.com/v1/messages/{message_id}"
    data = rate_limited_request(url, get_headers())
    if not data or "data" not in data:
        return None
    return data["data"]

##############################
# 6) Multi-Level Streamlit   #
##############################
def main():
    st.set_page_config(page_title="OpenPhone Multi-Level", layout="wide")
    st.title("OpenPhone Multi-Level Logs & Transcripts")

    # Use st.query_params instead of st.experimental_get_query_params
    query_params = st.query_params
    phone_number_id = query_params.get("phoneNumberId", [None])[0]
    contact_number = query_params.get("contactNumber", [None])[0]

    if phone_number_id and contact_number:
        # =====================
        # LEVEL 2: Transcripts + Full Messages for This Contact
        # =====================
        st.subheader(f"Line: {phone_number_id}, Contact: {contact_number}")
        with st.spinner("Loading last 100 calls/messages..."):
            all_calls = fetch_calls(phone_number_id)
            all_msgs = fetch_messages(phone_number_id)

        # Filter calls that involve contact_number
        relevant_calls = []
        for c in all_calls:
            participants = c.get("participants", [])
            # If any participant has phoneNumber == contact_number
            if any(contact_number == p.get("phoneNumber") for p in participants):
                relevant_calls.append(c)

        st.markdown("### Calls with Transcripts")
        if not relevant_calls:
            st.info(f"No calls found with {contact_number}.")
        else:
            call_rows = []
            for call in relevant_calls:
                call_id = call.get("id", "")
                transcript_data = fetch_call_transcript(call_id)
                if transcript_data and "dialogue" in transcript_data:
                    # Flatten dialogue
                    dialogue_str = "\n".join(
                        f"{seg.get('identifier','?')} > {seg.get('content','')}"
                        for seg in transcript_data["dialogue"]
                    )
                else:
                    dialogue_str = "No transcript or in progress."

                call_rows.append({
                    "Call ID": call_id,
                    "Created At": call.get("createdAt",""),
                    "Direction": call.get("direction",""),
                    "Transcript": dialogue_str
                })
            df_calls = pd.DataFrame(call_rows)
            st.dataframe(df_calls)

        st.markdown("### Messages with Full Content")
        relevant_msgs = []
        for m in all_msgs:
            participants = m.get("participants", [])
            if any(contact_number == p.get("phoneNumber") for p in participants):
                relevant_msgs.append(m)

        if not relevant_msgs:
            st.info(f"No messages found with {contact_number}.")
        else:
            msg_rows = []
            for msg in relevant_msgs:
                msg_id = msg.get("id", "")
                # fetch full content
                full_data = fetch_full_message(msg_id)
                if full_data:
                    body = full_data.get("content","") or full_data.get("body","")
                    direction = full_data.get("direction","")
                    created_at = full_data.get("createdAt","")
                else:
                    # fallback from partial data
                    body = msg.get("content","")
                    direction = msg.get("direction","")
                    created_at = msg.get("createdAt","")

                msg_rows.append({
                    "Message ID": msg_id,
                    "Created At": created_at,
                    "Direction": direction,
                    "Full Content": body
                })
            df_msgs = pd.DataFrame(msg_rows)
            st.dataframe(df_msgs)

        # Link back to contact list
        back_params = {"phoneNumberId": phone_number_id}
        st.markdown(f"[Back to Unique Contacts](?{urlencode(back_params)})")

    elif phone_number_id and not contact_number:
        # =====================
        # LEVEL 1: Unique Contacts for phoneNumberId
        # =====================
        st.subheader(f"Unique Contacts for {phone_number_id}")
        with st.spinner("Loading last 100 calls & messages..."):
            all_calls = fetch_calls(phone_number_id)
            all_msgs = fetch_messages(phone_number_id)

        # Collect participant phoneNumbers
        contacts_set = set()

        for c in all_calls:
            for p in c.get("participants", []):
                pn = p.get("phoneNumber", None)
                if pn:
                    contacts_set.add(pn)

        for m in all_msgs:
            for p in m.get("participants", []):
                pn = p.get("phoneNumber", None)
                if pn:
                    contacts_set.add(pn)

        if not contacts_set:
            st.info("No contacts found in last 100 calls/messages.")
            st.markdown("[Back to Main](?)")
            return

        rows = []
        for cn in contacts_set:
            link_params = {"phoneNumberId": phone_number_id, "contactNumber": cn}
            link_html = f'<a href="?{urlencode(link_params)}" target="_self">View Full Logs</a>'
            rows.append({
                "Contact Phone": cn,
                "Details": link_html
            })
        df_contacts = pd.DataFrame(rows)
        st.markdown(df_contacts.to_html(escape=False, index=False), unsafe_allow_html=True)

        st.markdown("[Back to Main](?)")

    else:
        # =====================
        # LEVEL 0: All Phone Numbers
        # =====================
        st.header("All OpenPhone Numbers in Your Workspace")

        with st.spinner("Loading phone numbers..."):
            phone_nums = get_phone_numbers()

        if not phone_nums:
            st.warning("No phone numbers found, or invalid API Key.")
            return

        table_rows = []
        for pn in phone_nums:
            pid = pn["id"]
            num = pn["phoneNumber"]
            if pid and pid.startswith("PN"):
                link_html = f'<a href="?{urlencode({"phoneNumberId": pid})}" target="_self">Show Contacts</a>'
            else:
                link_html = "Invalid or no ID"

            table_rows.append({
                "Phone Number": num,
                "Details": link_html
            })
        df_main = pd.DataFrame(table_rows)
        st.markdown(df_main.to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
