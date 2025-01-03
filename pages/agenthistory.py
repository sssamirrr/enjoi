import streamlit as st
import pandas as pd
import time
import requests
from urllib.parse import urlencode

############################
# 1) OpenPhone API Key     #
############################
# If OpenPhone requires "Bearer ", prepend it:
# OPENPHONE_API_KEY = "Bearer j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

############################
# 2) Rate-limited request  #
############################
def rate_limited_request(url, headers, params=None, request_type='get'):
    """
    Makes a GET request, sleeping ~1/5 second to respect ~5 req/sec.
    Prints errors if any.
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
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }

##############################
# 3) Fetch PhoneNumbers      #
##############################
def get_phone_numbers():
    """
    Lists all phone numbers from /v1/phone-numbers.
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    data = rate_limited_request(url, get_headers())
    st.write("DEBUG /v1/phone-numbers RAW:", data)  # Debug full response

    if not data or "data" not in data:
        return []

    results = []
    for pn in data["data"]:
        pid = pn.get("id","")
        pnum = pn.get("phoneNumber","No Number")
        results.append({"id": pid, "phoneNumber": pnum})
    return results

##############################
# 4) Fetch Calls & Messages  #
##############################
def fetch_calls(phone_number_id, max_records=100):
    """
    Fetch up to max_records calls for phoneNumberId.
    No 'participants' param. Debug prints each chunk + each record.
    """
    if not phone_number_id or not phone_number_id.startswith("PN"):
        return []

    calls_url = "https://api.openphone.com/v1/calls"
    all_calls = []
    fetched = 0
    next_page = None

    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request(calls_url, get_headers(), params, 'get')
        st.write("DEBUG /v1/calls chunk RAW:", data)

        if not data or "data" not in data:
            break

        chunk = data["data"]
        for item in chunk:
            st.write("DEBUG Single Call Record:", item)

        all_calls.extend(chunk)
        fetched += len(chunk)

        next_page = data.get("nextPageToken")
        if not next_page or fetched >= max_records:
            break

    return all_calls

def fetch_messages(phone_number_id, max_records=100):
    """
    Fetch up to max_records messages for phoneNumberId.
    No 'participants' param. Debug prints each chunk + record.
    """
    if not phone_number_id or not phone_number_id.startswith("PN"):
        return []

    msgs_url = "https://api.openphone.com/v1/messages"
    all_msgs = []
    fetched = 0
    next_page = None

    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request(msgs_url, get_headers(), params, 'get')
        st.write("DEBUG /v1/messages chunk RAW:", data)

        if not data or "data" not in data:
            break

        chunk = data["data"]
        for item in chunk:
            st.write("DEBUG Single Message Record:", item)

        all_msgs.extend(chunk)
        fetched += len(chunk)

        next_page = data.get("nextPageToken")
        if not next_page or fetched >= max_records:
            break

    return all_msgs

##############################
# 5) Gather Contact Numbers  #
##############################
def get_contact_numbers_from_call(call_record):
    """
    Fallback approach: tries participants, else 'from'/'to'.
    """
    contacts = set()
    participants = call_record.get("participants", [])
    if participants:
        for p in participants:
            ph = p.get("phoneNumber")
            if ph:
                contacts.add(ph)
    else:
        frm = call_record.get("from")
        if isinstance(frm, dict):
            ph = frm.get("phoneNumber","")
            if ph: contacts.add(ph)
        elif isinstance(frm, str):
            if frm: contacts.add(frm)

        t_data = call_record.get("to", [])
        if isinstance(t_data, list):
            for t in t_data:
                if isinstance(t, dict):
                    ph = t.get("phoneNumber","")
                    if ph: contacts.add(ph)
                elif isinstance(t, str):
                    if t: contacts.add(t)
        elif isinstance(t_data, str):
            if t_data: contacts.add(t_data)
    return contacts

def get_contact_numbers_from_message(msg_record):
    """
    Fallback approach: tries participants, else 'from'/'to'.
    """
    contacts = set()
    participants = msg_record.get("participants", [])
    if participants:
        for p in participants:
            ph = p.get("phoneNumber")
            if ph:
                contacts.add(ph)
    else:
        frm = msg_record.get("from")
        if isinstance(frm, dict):
            ph = frm.get("phoneNumber","")
            if ph: contacts.add(ph)
        elif isinstance(frm, str):
            if frm: contacts.add(frm)

        t_data = msg_record.get("to", [])
        if isinstance(t_data, list):
            for t in t_data:
                if isinstance(t, dict):
                    ph = t.get("phoneNumber","")
                    if ph: contacts.add(ph)
                elif isinstance(t, str):
                    if t: contacts.add(t)
        elif isinstance(t_data, str):
            if t_data: contacts.add(t_data)
    return contacts

##############################
# 6) Full Transcripts        #
##############################
def fetch_call_transcript(call_id):
    url = f"https://api.openphone.com/v1/call-transcripts/{call_id}"
    data = rate_limited_request(url, get_headers())
    st.write("DEBUG fetch_call_transcript:", data)
    if not data or "data" not in data:
        return None
    return data["data"]

def fetch_full_message(message_id):
    url = f"https://api.openphone.com/v1/messages/{message_id}"
    data = rate_limited_request(url, get_headers())
    st.write("DEBUG fetch_full_message:", data)
    if not data or "data" not in data:
        return None
    return data["data"]

##############################
# 7) Multi-Level App         #
##############################
def parse_query_param(param):
    """
    Safely parse a param that might be string or list.
    """
    if param is None:
        return None
    if isinstance(param, str):
        return param
    if isinstance(param, list) and len(param) > 0:
        return param[0]
    return None

def main():
    st.set_page_config(page_title="OP Multi-Level Debug (Fixed)", layout="wide")
    st.title("OpenPhone Multi-Level Debug (Fixed for Query Params)")

    # Safely parse query params
    qparams = st.query_params
    raw_phone_id = qparams.get("phoneNumberId")  # could be string or list
    phone_number_id = parse_query_param(raw_phone_id)

    raw_contact_val = qparams.get("contactNumber")
    contact_number = parse_query_param(raw_contact_val)

    # Debug
    st.write("DEBUG raw_phone_id:", raw_phone_id)
    st.write("DEBUG final phone_number_id:", phone_number_id)
    st.write("DEBUG contact_number:", contact_number)

    if phone_number_id and contact_number:
        # LEVEL 2: Show transcripts & messages for that contact
        st.subheader(f"Line: {phone_number_id}, Contact: {contact_number}")

        with st.spinner("Loading calls & messages..."):
            calls = fetch_calls(phone_number_id)
            msgs = fetch_messages(phone_number_id)

        # Filter calls
        relevant_calls = []
        for c in calls:
            cnums = get_contact_numbers_from_call(c)
            if contact_number in cnums:
                relevant_calls.append(c)

        st.markdown("### Calls & Transcripts")
        if not relevant_calls:
            st.info(f"No calls found with {contact_number}")
        else:
            call_rows = []
            for rc in relevant_calls:
                cid = rc.get("id","")
                trans_data = fetch_call_transcript(cid)
                if trans_data and "dialogue" in trans_data:
                    text = "\n".join(
                        f"{seg.get('identifier','?')} > {seg.get('content','')}"
                        for seg in trans_data["dialogue"]
                    )
                else:
                    text = "No transcript"

                call_rows.append({
                    "Call ID": cid,
                    "Created At": rc.get("createdAt",""),
                    "Direction": rc.get("direction",""),
                    "Transcript": text
                })
            st.dataframe(pd.DataFrame(call_rows))

        # Filter messages
        st.markdown("### Messages & Full Content")
        relevant_msgs = []
        for rm in msgs:
            mnums = get_contact_numbers_from_message(rm)
            if contact_number in mnums:
                relevant_msgs.append(rm)

        if not relevant_msgs:
            st.info(f"No messages found with {contact_number}")
        else:
            msg_rows = []
            for mm in relevant_msgs:
                mid = mm.get("id","")
                full_m = fetch_full_message(mid)
                if full_m:
                    b = full_m.get("content","") or full_m.get("body","")
                    direction = full_m.get("direction","")
                    created_at = full_m.get("createdAt","")
                else:
                    b = mm.get("content","")
                    direction = mm.get("direction","")
                    created_at = mm.get("createdAt","")

                msg_rows.append({
                    "Message ID": mid,
                    "Created At": created_at,
                    "Direction": direction,
                    "Full Content": b
                })
            st.dataframe(pd.DataFrame(msg_rows))

        # Back link
        back_params = {"phoneNumberId": phone_number_id}
        st.markdown(f"[Back to Unique Contacts](?{urlencode(back_params)})")

    elif phone_number_id and not contact_number:
        # LEVEL 1: Show unique contacts for that phoneNumberId
        st.subheader(f"Unique Contacts for {phone_number_id}")

        with st.spinner("Loading calls & messages..."):
            calls = fetch_calls(phone_number_id)
            msgs = fetch_messages(phone_number_id)

        contact_set = set()

        for c in calls:
            cnums = get_contact_numbers_from_call(c)
            contact_set.update(cnums)

        for m in msgs:
            mnums = get_contact_numbers_from_message(m)
            contact_set.update(mnums)

        if not contact_set:
            st.info("No contacts found in last 100 calls/messages.")
            st.markdown("[Back to Main](?)")
            return

        rows = []
        for cn in contact_set:
            link_params = {"phoneNumberId": phone_number_id, "contactNumber": cn}
            link_html = f'<a href="?{urlencode(link_params)}" target="_self">View Full Logs</a>'
            rows.append({"Contact Phone": cn, "Details": link_html})

        st.markdown(pd.DataFrame(rows).to_html(escape=False, index=False), unsafe_allow_html=True)
        st.markdown("[Back to Main](?)")

    else:
        # LEVEL 0: Show all phone numbers
        st.header("All Phone Numbers in Your Workspace")

        with st.spinner("Loading phone numbers..."):
            phone_nums = get_phone_numbers()

        if not phone_nums:
            st.warning("No phone numbers found or invalid API Key.")
            return

        data_list = []
        for pn in phone_nums:
            pid = pn["id"]
            num = pn["phoneNumber"]
            if pid and pid.startswith("PN"):
                link_html = f'<a href="?{urlencode({"phoneNumberId": pid})}" target="_self">Show Contacts</a>'
            else:
                link_html = "Invalid / No ID"

            data_list.append({
                "Phone Number": num,
                "Details": link_html
            })

        st.markdown(pd.DataFrame(data_list).to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
