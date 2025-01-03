import streamlit as st
import pandas as pd
import time
import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta

############################
# 1) OpenPhone API Key     #
############################
# NOTE: As requested, using the API key "as is" (no 'Bearer ' prefix).
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

def get_headers():
    """
    Returns the headers for all OpenPhone API requests.
    """
    return {
        "Authorization": OPENPHONE_API_KEY,  # No 'Bearer' prefix
        "Content-Type": "application/json"
    }

def rate_limited_request(url, headers, params=None):
    """
    Makes a GET request, sleeping ~0.2 seconds to respect ~5 req/sec.
    Accepts `params` as a list of tuples or a dict.
    """
    time.sleep(0.2)  # simple rate limit
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

def get_phone_numbers():
    """
    Fetch phone numbers from OpenPhone.
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

def fetch_calls(phone_number_id, start_date, end_date, max_calls=500):
    """
    Fetch calls for phoneNumberId between start_date and end_date.
    Instead of passing 'participants': [], we attach `participants[]` = ''
    in the query string (list of tuples) to work around 'required property' errors.
    """
    url = "https://api.openphone.com/v1/calls"
    all_calls = []
    next_page = None

    while True:
        # We'll build `params` as a list of tuples. The server sometimes
        # expects participants[] in the query string as array syntax:
        base_params = [
            ("phoneNumberId", phone_number_id),
            ("createdAfter", start_date.isoformat()),
            ("createdBefore", end_date.isoformat()),
            ("maxResults", "50")
        ]
        # Trick: pass an empty participants[] array
        # This often satisfies the "Expected array" requirement
        base_params.append(("participants[]", ""))

        if next_page:
            base_params.append(("pageToken", next_page))

        data = rate_limited_request(url, get_headers(), params=base_params)
        if not data or "data" not in data:
            break

        chunk = data["data"]
        all_calls.extend(chunk)

        next_page = data.get("nextPageToken")
        if not next_page or len(all_calls) >= max_calls:
            break

    return all_calls[:max_calls]

def fetch_messages(phone_number_id, start_date, end_date, max_msgs=500):
    """
    Fetch messages for phoneNumberId between start_date and end_date.
    We also append participants[] as empty in the query string for consistency.
    """
    url = "https://api.openphone.com/v1/messages"
    all_msgs = []
    next_page = None

    while True:
        base_params = [
            ("phoneNumberId", phone_number_id),
            ("createdAfter", start_date.isoformat()),
            ("createdBefore", end_date.isoformat()),
            ("maxResults", "50")
        ]
        # Trick: pass an empty participants[] array
        base_params.append(("participants[]", ""))

        if next_page:
            base_params.append(("pageToken", next_page))

        data = rate_limited_request(url, get_headers(), params=base_params)
        if not data or "data" not in data:
            break

        chunk = data["data"]
        all_msgs.extend(chunk)

        next_page = data.get("nextPageToken")
        if not next_page or len(all_msgs) >= max_msgs:
            break

    return all_msgs[:max_msgs]

# -------------- Contact Extraction --------------
def get_contact_numbers_from_call(call_record):
    """
    Return a set of phone numbers from a call record.
    """
    contacts = set()
    # Check 'participants' if present
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
    # Check 'participants' if present
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

# -------------- Transcripts & Messages --------------
def fetch_call_transcript(call_id):
    """
    GET /v1/calls/{callId}/transcription (Business plan).
    """
    url = f"https://api.openphone.com/v1/calls/{call_id}/transcription"
    data = rate_limited_request(url, get_headers())
    if not data or "data" not in data:
        return None
    return data["data"]

def fetch_full_message(message_id):
    """
    GET /v1/messages/{messageId} to get full message content if needed.
    """
    url = f"https://api.openphone.com/v1/messages/{message_id}"
    data = rate_limited_request(url, get_headers())
    if not data or "data" not in data:
        return None
    return data["data"]

# -------------- Streamlit UI --------------
def main():
    st.set_page_config(page_title="OpenPhone - Last 3 Months Calls & Messages", layout="wide")
    st.title("OpenPhone: Calls & Messages for Last 3 Months")

    # Step A: Let user pick from their available phone numbers
    phone_nums = get_phone_numbers()
    if not phone_nums:
        st.error("No phone numbers found or invalid API Key.")
        return

    phone_map = {pn["phoneNumber"]: pn["id"] for pn in phone_nums if pn["id"]}
    if not phone_map:
        st.error("No valid phone number IDs found.")
        return

    choice = st.selectbox("Select a Phone Number:", list(phone_map.keys()))
    phone_number_id = phone_map[choice]

    # Step B: Date range for the last 3 months
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=90)

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

    # Step E: Display calls/messages per contact
    for contact_number in unique_contacts:
        with st.expander(f"Contact: {contact_number}"):
            # Filter calls for this contact
            contact_calls = []
            for call in calls:
                if contact_number in get_contact_numbers_from_call(call):
                    contact_calls.append(call)

            call_rows = []
            for ccall in contact_calls:
                cid = ccall.get("id", "")
                direction = ccall.get("direction", "")
                created_at = ccall.get("createdAt", "")
                # Fetch transcript if any
                transcript_data = fetch_call_transcript(cid)
                if transcript_data and "dialogue" in transcript_data:
                    lines = []
                    for seg in transcript_data["dialogue"]:
                        speaker = seg.get("identifier", "?")
                        content = seg.get("content", "")
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
            for mm in msgs:
                if contact_number in get_contact_numbers_from_message(mm):
                    contact_msgs.append(mm)

            msg_rows = []
            for mm in contact_msgs:
                mid = mm.get("id", "")
                direction = mm.get("direction", "")
                created_at = mm.get("createdAt", "")
                # Optionally fetch full message
                full_m = fetch_full_message(mid)
                if full_m:
                    body = full_m.get("content", "") or full_m.get("body", "")
                else:
                    body = mm.get("content", "") or mm.get("body", "")

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
