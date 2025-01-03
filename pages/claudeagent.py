import streamlit as st
import pandas as pd
import time
import requests

##############################
# 1) OpenPhone API Key       #
##############################
# NOTE: If you need 'Bearer ', add it manually:
# OPENPHONE_API_KEY = "Bearer YOUR_REAL_KEY"
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"  # No 'Bearer '

##############################
# 2) Rate-Limited Request    #
##############################
def rate_limited_request(url, headers, params=None, request_type='get'):
    """
    Make an API request while respecting rate limits (~5 requests/sec).
    """
    if params is None:
        params = {}
    time.sleep(1 / 5)
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
        st.warning(f"Exception: {str(e)}")
    return None

##############################
# 3) Fetch Phone Numbers     #
##############################
def get_phone_numbers():
    """
    Fetch phoneNumberId, phoneNumber for all lines in your OpenPhone account.
    Returns a list of dicts with { "phoneNumberId": "PN...", "phoneNumber": "+1..." }.
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {
        "Authorization": OPENPHONE_API_KEY,  # no 'Bearer ' prefix
        "Content-Type": "application/json"
    }
    data = rate_limited_request(url, headers, {})
    if not data or "data" not in data:
        return []

    results = []
    for item in data["data"]:
        pid = item.get("id")                # e.g. "PNsyKJnJnG"
        pnum = item.get("phoneNumber") or "No Phone#"
        results.append({
            "phoneNumberId": pid,
            "phoneNumber": pnum
        })
    return results

##############################
# 4) Fetch Calls & Messages  #
##############################
def fetch_calls(phone_number_id, max_contacts=100):
    """
    Fetch up to max_contacts calls for a given phoneNumberId.
    No 'participants' param to avoid 400 errors.
    """
    if not phone_number_id or not phone_number_id.startswith("PN"):
        # If invalid, return empty
        return []

    calls_url = "https://api.openphone.com/v1/calls"
    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }
    all_calls = []
    fetched = 0
    next_page = None

    while True:
        params = {"phoneNumberId": phone_number_id, "maxResults": 50}
        if next_page:
            params["pageToken"] = next_page

        resp = rate_limited_request(calls_url, headers, params, 'get')
        if not resp or "data" not in resp:
            break

        chunk = resp["data"]
        all_calls.extend(chunk)
        fetched += len(chunk)
        next_page = resp.get("nextPageToken")
        if not next_page or fetched >= max_contacts:
            break

    return all_calls

def fetch_messages(phone_number_id, max_contacts=100):
    """
    Fetch up to max_contacts messages for a given phoneNumberId.
    No 'participants' param to avoid 400 errors.
    """
    if not phone_number_id or not phone_number_id.startswith("PN"):
        return []

    messages_url = "https://api.openphone.com/v1/messages"
    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }
    all_msgs = []
    fetched = 0
    next_page = None

    while True:
        params = {"phoneNumberId": phone_number_id, "maxResults": 50}
        if next_page:
            params["pageToken"] = next_page

        resp = rate_limited_request(messages_url, headers, params, 'get')
        if not resp or "data" not in resp:
            break

        chunk = resp["data"]
        all_msgs.extend(chunk)
        fetched += len(chunk)
        next_page = resp.get("nextPageToken")
        if not next_page or fetched >= max_contacts:
            break

    return all_msgs

def get_agent_history(phone_number_id):
    """
    Returns (calls_df, messages_df):
     - Last 100 calls for that phoneNumberId (with transcripts if available)
     - Last 100 messages (with full text content)
    """
    calls_data = fetch_calls(phone_number_id, 100)
    if calls_data:
        calls_df = pd.DataFrame([
            {
                "Created At": c.get("createdAt", ""),
                "Direction": c.get("direction", ""),
                "Duration (sec)": c.get("duration", 0),
                "Status": c.get("status", ""),
                "Transcript": c.get("transcript", ""),
                "Recording URL": c.get("recordingUrl", "")
            }
            for c in calls_data
        ])
    else:
        calls_df = pd.DataFrame()

    messages_data = fetch_messages(phone_number_id, 100)
    if messages_data:
        messages_df = pd.DataFrame([
            {
                "Created At": m.get("createdAt", ""),
                "Direction": m.get("direction", ""),
                "Message Content": m.get("content", ""),
                "From": m.get("from", {}).get("phoneNumber", ""),
                "To": ", ".join(t.get("phoneNumber", "") for t in m.get("to", [])),
            }
            for m in messages_data
        ])
    else:
        messages_df = pd.DataFrame()

    return calls_df, messages_df

##############################
# 5) Single-Page Streamlit   #
##############################
def main():
    st.set_page_config(page_title="OpenPhone Fix", layout="wide")
    st.title("OpenPhone: List & Last 100 Contacts")

    # 1) Check if we have phoneNumberId in query params
    phone_number_id = st.query_params.get("phoneNumberId", [None])[0]

    if phone_number_id:
        # --- Detail View ---
        st.subheader(f"Detail for phoneNumberId = {phone_number_id}")
        # Double-check if it starts with "PN"
        if not phone_number_id.startswith("PN"):
            st.error("Invalid phoneNumberId. Must match '^PN(.*)'.")
            st.markdown("[Back to Main](?)")
            return

        with st.spinner("Fetching calls & messages..."):
            calls_df, messages_df = get_agent_history(phone_number_id)

        st.markdown("### Last 100 Calls")
        if calls_df.empty:
            st.info("No calls found or invalid ID.")
        else:
            st.dataframe(calls_df)

        st.markdown("### Last 100 Messages")
        if messages_df.empty:
            st.info("No messages found or invalid ID.")
        else:
            st.dataframe(messages_df)

        st.markdown("[Back to Main](?)")

    else:
        # --- Main Page: List All Phone Numbers ---
        st.header("All Phone Numbers in OpenPhone")

        phone_nums = get_phone_numbers()
        if not phone_nums:
            st.warning("No phone numbers found. Possibly no lines assigned or API issue.")
            return

        # Build a table with a clickable link
        table_data = []
        for pn in phone_nums:
            pid = pn["phoneNumberId"]
            pnum = pn["phoneNumber"]
            if pid and pid.startswith("PN"):
                # Relative link "?phoneNumberId=PNxxx"
                link = f'<a href="?phoneNumberId={pid}" target="_self">View History</a>'
            else:
                link = "No valid ID"

            table_data.append({
                "Phone Number": pnum,
                "Details": link
            })

        df = pd.DataFrame(table_data)
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
