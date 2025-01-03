import streamlit as st
import pandas as pd
import time
import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta

# --------------------
# 1) Setup and Helpers
# --------------------
OPENPHONE_API_KEY = "YOUR_API_KEY_HERE"

def get_headers():
    """
    Returns the headers used for all OpenPhone API requests.
    Note: NO 'Bearer ' prefix, as requested.
    """
    return {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }

def rate_limited_request(url, headers, params=None):
    """
    Makes a GET request, sleeping ~1/5 second to respect ~5 req/sec.
    """
    if params is None:
        params = {}
    time.sleep(0.2)
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            return resp.json()
        else:
            st.warning(f"API Error: {resp.status_code}")
            st.warning(f"Response: {resp.text}")
    except Exception as e:
        st.warning(f"Exception: {e}")
    return None

# ---------------------------
# 2) Fetch Phone Numbers List
# ---------------------------
def get_phone_numbers():
    url = "https://api.openphone.com/v1/phone-numbers"
    data = rate_limited_request(url, get_headers())
    if not data or "data" not in data:
        return []
    results = []
    for pn in data["data"]:
        pid = pn.get("id","")
        pnum = pn.get("phoneNumber","No Number")
        results.append({"id": pid, "phoneNumber": pnum})
    return results

# ---------------------------------------
# 3) Fetch Calls with Date Range (3 mos)
# ---------------------------------------
def fetch_calls(phone_number_id, start_date, end_date, max_calls=500):
    """
    Fetch calls for phoneNumberId within [start_date, end_date].
    Passing participants=[] to 'trick' the API if it's required.
    Limit to max_calls if needed.
    """
    calls_url = "https://api.openphone.com/v1/calls"
    all_calls = []
    next_page = None

    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "createdAfter": start_date.isoformat(),  # e.g. 2023-09-01T00:00:00Z
            "createdBefore": end_date.isoformat(),
            "maxResults": 50,
            # Empty array to satisfy any 'participants' requirement
            "participants": []
        }
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request(calls_url, get_headers(), params)
        if not data or "data" not in data:
            break

        chunk = data["data"]
        all_calls.extend(chunk)

        next_page = data.get("nextPageToken")
        if not next_page or len(all_calls) >= max_calls:
            break

    return all_calls[:max_calls]

# -----------------------------------------------
# 4) Fetch Messages with Date Range (3 months)
# -----------------------------------------------
def fetch_messages(phone_number_id, start_date, end_date, max_msgs=500):
    """
    Fetch messages for phoneNumberId within [start_date, end_date].
    Also passing participants=[] to 'trick' the API if needed.
    Limit to max_msgs if needed.
    """
    msgs_url = "https://api.openphone.com/v1/messages"
    all_msgs = []
    next_page = None

    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "createdAfter": start_date.isoformat(),
            "createdBefore": end_date.isoformat(),
            "maxResults": 50,
            # Empty array for any 'participants' requirement
            "participants": []
        }
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request(msgs_url, get_headers(), params)
        if not data or "data" not in data:
            break

        chunk = data["data"]
        all_msgs.extend(chunk)

        next_page = data.get("nextPageToken")
        if not next_page or len(all_msgs) >= max_msgs:
            break

    return all_msgs[:max_msgs]

# -------------------------
# 5) Extract Contact Numbers
# -------------------------
def get_contact_numbers_from_call(call_record):
    """
    Return a set of phone numbers from a call record.
    """
    contacts = set()
    # Try participants first
    participants = call_record.get("participants", [])
    if participants:
        for p in participants:
            ph = p.get("phoneNumber")
            if ph:
                contacts.add(ph)
    else:
        # Fallback to from/to
        frm = call_record.get("from", {})
        if isinstance(frm, dict):
            ph = frm.get("phoneNumber")
            if ph:
                contacts.add(ph)
        elif isinstance(frm, str):
            if frm:
                contacts.add(frm)

        to_list = call_record.get("to", [])
        if isinstance(to_list, list):
            for t in to_list:
                if isinstance(t, dict):
                    ph = t.get("phoneNumber")
                    if ph:
                        contacts.add(ph)
                elif isinstance(t, str):
                    if t:
                        contacts.add(t)
        elif isinstance(to_list, str):
            if to_list:
                contacts.add(to_list)
    return contacts

def get_contact_numbers_from_message(msg_record):
    """
    Return a set of phone numbers from a message record.
    """
    contacts = set()
    # Try participants first
    participants = msg_record.get("participants", [])
    if participants:
        for p in participants:
            ph = p.get("phoneNumber")
            if ph:
                contacts.add(ph)
    else:
        # Fallback to from/to
        frm = msg_record.get("from", {})
        if isinstance(frm, dict):
            ph = frm.get("phoneNumber")
            if ph:
                contacts.add(ph)
        elif isinstance(frm, str):
            if frm:
                contacts.add(frm)

        to_list = msg_record.get("to", [])
        if isinstance(to_list, list):
            for t in to_list:
                if isinstance(t, dict):
                    ph = t.get("phoneNumber")
                    if ph:
                        contacts.add(ph)
                elif isinstance(t, str):
                    if t:
                        contacts.add(t)
        elif isinstance(to_list, str):
            if to_list:
                contacts.add(to_list)
    return contacts

# --------------------------------
# 6) Transcripts & Message Details
# --------------------------------
def fetch_call_transcript(call_id):
    """
    GET /v1/calls/{callId}/transcription
    (Requires Business plan to see transcripts)
    """
    url = f"https://api.openphone.com/v1/calls/{call_id}/transcription"
    data = rate_limited_request(url, get_headers())
    if not data or "data" not in data:
        return None
    return data["data"]

def fetch_full_message(message_id):
    """
    GET /v1/messages/{messageId}
    to retrieve full message content if needed.
    """
    url = f"https://api.openphone.com/v1/messages/{message_id}"
    data = rate_limited_request(url, get_headers())
    if not data or "data" not in data:
        return None
    return data["data"]

# ---------------
# 7) Streamlit UI
# ---------------
def main():
    st.set_page_config(page_title="OpenPhone - Last 100 Contacts (3 Months)", layout="wide")
    st.title("OpenPhone: Calls & Messages for Last 3 Months")

    # Step A: Let user pick from their available phone numbers
    phone_nums = get_phone_numbers()
    if not phone_nums:
        st.error("No phone numbers found or invalid API Key.")
        return

    # Let user choose phone number from dropdown
    phone_num_map = {pn["phoneNumber"]: pn["id"] for pn in phone_nums if pn["id"]}
    choice = st.selectbox("Select a Phone Number:", list(phone_num_map.keys()))
    phone_number_id = phone_num_map[choice]

    # Step B: Define date range for last 3 months
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=90)  # ~3 months

    # Step C: Fetch calls & messages (with spinner)
    st.info("Fetching calls and messages from the past 3 months…")
    with st.spinner("Loading calls..."):
        calls = fetch_calls(phone_number_id, start_date, end_date, max_calls=500)
    with st.spinner("Loading messages..."):
        msgs = fetch_messages(phone_number_id, start_date, end_date, max_msgs=500)

    st.write(f"Fetched {len(calls)} calls and {len(msgs)} messages.")

    # Step D: Gather up to 100 unique contacts
    contact_set = set()

    for c in calls:
        if len(contact_set) >= 100:
            break
        contact_set.update(get_contact_numbers_from_call(c))
        if len(contact_set) >= 100:
            break

    for m in msgs:
        if len(contact_set) >= 100:
            break
        contact_set.update(get_contact_numbers_from_message(m))
        if len(contact_set) >= 100:
            break

    unique_contacts = list(contact_set)[:100]
    st.write(f"Found {len(unique_contacts)} unique contacts (limited to 100).")

    # Step E: For each contact, show relevant calls & messages
    # Expanders so the page isn't too large
    for contact_number in unique_contacts:
        with st.expander(f"Contact: {contact_number}"):
            # Filter calls for this contact
            contact_calls = []
            for call in calls:
                these_numbers = get_contact_numbers_from_call(call)
                if contact_number in these_numbers:
                    contact_calls.append(call)

            # Display calls + transcripts
            call_rows = []
            for ccall in contact_calls:
                cid = ccall.get("id", "")
                direction = ccall.get("direction", "")
                created_at = ccall.get("createdAt", "")
                # Attempt transcript fetch
                transcript_data = fetch_call_transcript(cid)
                transcript_text = ""
                if transcript_data and "dialogue" in transcript_data:
                    lines = []
                    for seg in transcript_data["dialogue"]:
                        speaker = seg.get("identifier","?")
                        content = seg.get("content","")
                        lines.append(f"{speaker}: {content}")
                    transcript_text = "\n".join(lines)
                elif transcript_data and "summary" in transcript_data:
                    transcript_text = transcript_data["summary"]
                else:
                    transcript_text = "No transcript data"

                call_rows.append({
                    "Call ID": cid,
                    "Created At": created_at,
                    "Direction": direction,
                    "Transcript": transcript_text
                })

            if call_rows:
                st.markdown("**Calls**")
                st.dataframe(pd.DataFrame(call_rows))

            # Filter messages for this contact
            contact_msgs = []
            for msg in msgs:
                these_numbers = get_contact_numbers_from_message(msg)
                if contact_number in these_numbers:
                    contact_msgs.append(msg)

            msg_rows = []
            for mm in contact_msgs:
                mid = mm.get("id", "")
                direction = mm.get("direction", "")
                created_at = mm.get("createdAt", "")
                # Optionally fetch full message
                full_m = fetch_full_message(mid)
                if full_m:
                    body = full_m.get("content","") or full_m.get("body","")
                else:
                    body = mm.get("content","") or mm.get("body","")

                msg_rows.append({
                    "Message ID": mid,
                    "Created At": created_at,
                    "Direction": direction,
                    "Content": body
                })

            if msg_rows:
                st.markdown("**Messages**")
                st.dataframe(pd.DataFrame(msg_rows))

if __name__ == "__main__":
    main()
