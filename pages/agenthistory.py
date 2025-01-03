import streamlit as st
import pandas as pd
import time
import requests
from urllib.parse import urlencode

############################
# 1) OpenPhone API Key     #
############################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"  # Or "Bearer YOUR_KEY"

############################
# 2) Rate-limited requests #
############################
def rate_limited_request(url, headers, params=None, request_type='get'):
    """
    A helper that respects ~5 requests/second. 
    Adjust if you need to post or handle transcripts differently.
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

##############################
# 3) Basic OpenPhone Helpers #
##############################
def get_headers():
    return {
        "Authorization": OPENPHONE_API_KEY,  # e.g., "Bearer <KEY>"
        "Content-Type": "application/json"
    }

def get_phone_numbers():
    """
    Step 1: Lists all phone numbers in your OpenPhone workspace.
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    data = rate_limited_request(url, get_headers())
    if not data or "data" not in data:
        return []
    results = []
    for pn in data["data"]:
        results.append({
            "id": pn.get("id"),             # e.g. "PNabcd1234"
            "phoneNumber": pn.get("phoneNumber", "No Number")
        })
    return results

def fetch_calls(phone_number_id, max_records=100):
    """
    Step 2 (part A): Fetch up to 'max_records' calls for a given phoneNumberId.
    """
    calls_url = "https://api.openphone.com/v1/calls"
    all_calls = []
    fetched = 0
    next_token = None

    while True:
        params = {
            "phoneNumberId": phone_number_id,
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
    Step 2 (part B): Fetch up to 'max_records' messages for that phoneNumberId.
    """
    msgs_url = "https://api.openphone.com/v1/messages"
    all_msgs = []
    fetched = 0
    next_token = None

    while True:
        params = {
            "phoneNumberId": phone_number_id,
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

def fetch_call_transcript(call_id):
    """
    Step 3: Retrieve the full call transcript for a specific call ID.
    GET /v1/call-transcripts/{id}
    """
    url = f"https://api.openphone.com/v1/call-transcripts/{call_id}"
    data = rate_limited_request(url, get_headers())
    if not data or "data" not in data:
        return None
    return data["data"]  # Might have 'dialogue', 'status', etc.

def fetch_full_message(message_id):
    """
    Step 4: Retrieve the full message content using GET /v1/messages/{messageId}.
    """
    url = f"https://api.openphone.com/v1/messages/{message_id}"
    data = rate_limited_request(url, get_headers())
    if not data or "data" not in data:
        return None
    return data["data"]

##############################
# 4) Our Multi-Level App     #
##############################
def main():
    st.title("OpenPhone Multi-Level Logs & Transcripts")

    query_params = st.experimental_get_query_params()
    phone_number_id = query_params.get("phoneNumberId", [None])[0]
    contact_number = query_params.get("contactNumber", [None])[0]

    if phone_number_id and contact_number:
        # -------------------
        # LEVEL 2: Show Full Transcripts & Full Messages for This Contact
        # -------------------
        st.subheader(f"Call Transcripts & Message Bodies\n\nLine ID = {phone_number_id}\nContact = {contact_number}")

        # Fetch calls & messages again
        with st.spinner("Loading calls & messages..."):
            all_calls = fetch_calls(phone_number_id, max_records=100)
            all_msgs = fetch_messages(phone_number_id, max_records=100)

        # Filter calls relevant to 'contact_number'
        # We'll see if 'participants' includes contact_number
        relevant_calls = []
        for c in all_calls:
            participants = c.get("participants", [])
            # If contact_number is in any participant phoneNumber
            if any(contact_number == p.get("phoneNumber") for p in participants):
                relevant_calls.append(c)

        st.markdown("### Calls with Full Transcripts")
        if not relevant_calls:
            st.info(f"No calls found with {contact_number}.")
        else:
            call_rows = []
            for call in relevant_calls:
                call_id = call.get("id", "")
                # Attempt to fetch transcripts
                transcript_data = fetch_call_transcript(call_id)
                if transcript_data and "dialogue" in transcript_data:
                    # Flatten the transcript into a string
                    # Alternatively, store as JSON or list
                    dialogue_str = "\n".join([
                        f"{seg.get('identifier', 'Unknown')} > {seg.get('content', '')}"
                        for seg in transcript_data["dialogue"]
                    ])
                else:
                    dialogue_str = "No transcript or in progress."

                call_rows.append({
                    "Call ID": call_id,
                    "Created At": call.get("createdAt", ""),
                    "Direction": call.get("direction", ""),
                    "Transcript": dialogue_str
                })

            if call_rows:
                df_calls = pd.DataFrame(call_rows)
                st.dataframe(df_calls)

        st.markdown("### Messages with Full Content")
        # Filter messages relevant to 'contact_number'
        relevant_msgs = []
        for m in all_msgs:
            participants = m.get("participants", [])
            # If contact_number is in participants
            # or from == contact_number, or to
            # But typically 'participants' includes both from & to
            if any(contact_number == p.get("phoneNumber") for p in participants):
                relevant_msgs.append(m)

        if not relevant_msgs:
            st.info(f"No messages found with {contact_number}.")
        else:
            msg_rows = []
            for msg in relevant_msgs:
                msg_id = msg.get("id", "")
                full_msg = fetch_full_message(msg_id)  # Step 4
                if full_msg:
                    # full_msg might have "body", "createdAt", etc.
                    body = full_msg.get("content", "") or full_msg.get("body", "")
                    direction = full_msg.get("direction", "")
                    created_at = full_msg.get("createdAt", "")
                else:
                    body = "No content found"
                    direction = msg.get("direction", "")
                    created_at = msg.get("createdAt", "")

                msg_rows.append({
                    "Message ID": msg_id,
                    "Created At": created_at,
                    "Direction": direction,
                    "Full Content": body
                })

            df_msgs = pd.DataFrame(msg_rows)
            st.dataframe(df_msgs)

        # Link back
        back_params = {"phoneNumberId": phone_number_id}
        st.markdown(f"[Back to Unique Contacts](?{urlencode(back_params)})")

    elif phone_number_id and not contact_number:
        # -------------------
        # LEVEL 1: Show Unique Contacted Numbers for This phoneNumberId
        # -------------------
        st.subheader(f"Unique Contacts for PhoneNumberId: {phone_number_id}")

        with st.spinner("Loading calls & messages..."):
            all_calls = fetch_calls(phone_number_id, max_records=100)
            all_msgs = fetch_messages(phone_number_id, max_records=100)

        # We gather a set of "contact numbers" from participants
        # that are not the line's own phone number (optional).
        # We'll do a naive approach: just gather from calls & messages
        contacts_set = set()

        # For calls:
        for c in all_calls:
            participants = c.get("participants", [])
            for p in participants:
                pn = p.get("phoneNumber")
                if pn:
                    contacts_set.add(pn)

        # For messages:
        for m in all_msgs:
            participants = m.get("participants", [])
            for p in participants:
                pn = p.get("phoneNumber")
                if pn:
                    contacts_set.add(pn)

        if not contacts_set:
            st.info("No contacts found in last 100 calls/messages.")
            st.markdown("[Back to Main](?)")
            return

        # Build a table of contacts with a link to see transcripts/messages
        table_rows = []
        for contact_pn in contacts_set:
            # We skip if the contact is the same as the line's phone number (optional)
            # Or we can keep it, if you want to see "self" calls/messages.
            link_params = {
                "phoneNumberId": phone_number_id,
                "contactNumber": contact_pn
            }
            link_html = f'<a href="?{urlencode(link_params)}" target="_self">View Full Logs</a>'
            table_rows.append({
                "Contact Phone": contact_pn,
                "Details": link_html
            })

        df_contacts = pd.DataFrame(table_rows)
        st.markdown(df_contacts.to_html(escape=False, index=False), unsafe_allow_html=True)

        # Link back
        st.markdown("[Back to Main](?)")

    else:
        # -------------------
        # LEVEL 0: Show All Phone Numbers
        # -------------------
        st.header("All OpenPhone Numbers in Your Workspace")

        with st.spinner("Loading phone numbers..."):
            phone_nums = get_phone_numbers()

        if not phone_nums:
            st.warning("No phone numbers found in your workspace or invalid API Key.")
            return

        table_rows = []
        for pn in phone_nums:
            pid = pn["id"]
            pnum = pn["phoneNumber"]
            if pid and pid.startswith("PN"):
                link_params = {"phoneNumberId": pid}
                link_html = f'<a href="?{urlencode(link_params)}" target="_self">Show Contacts</a>'
            else:
                link_html = "Invalid or no ID"
            table_rows.append({
                "Phone Number": pnum,
                "Details": link_html
            })

        df = pd.DataFrame(table_rows)
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)


if __name__ == "__main__":
    st.set_page_config(page_title="OpenPhone Multi-Step", layout="wide")
    main()
