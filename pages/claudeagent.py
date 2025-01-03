import streamlit as st
import pandas as pd
import time
import requests

##############################
# 1) OpenPhone API Key       #
##############################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

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
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }
    data = rate_limited_request(url, headers, {})
    if not data or "data" not in data:
        return []

    results = []
    for item in data["data"]:
        pid = item.get("id")
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
    """
    if not phone_number_id or not phone_number_id.startswith("PN"):
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
    Returns (calls_df, messages_df) with last 100 of each
    """
    calls_data = fetch_calls(phone_number_id, 100)
    if calls_data:
        calls_df = pd.DataFrame([
            {
                "Created At": pd.to_datetime(c.get("createdAt", ""), unit='s'),
                "Direction": c.get("direction", ""),
                "Duration (sec)": c.get("duration", 0),
                "Status": c.get("status", ""),
                "From": c.get("from", ""),
                "To": c.get("to", ""),
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
                "Created At": pd.to_datetime(m.get("createdAt", ""), unit='s'),
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
# 5) Main Streamlit App      #
##############################
def main():
    st.set_page_config(page_title="OpenPhone History", layout="wide")
    st.title("OpenPhone: List & Last 100 Contacts")

    # Get phone_number_id from query params if it exists
    params = st.experimental_get_query_params()
    phone_number_id = params.get("phoneNumberId", [None])[0]

    if phone_number_id:
        # Detail View
        st.subheader(f"Detail for phoneNumberId = {phone_number_id}")
        
        # Validate phoneNumberId format
        if not phone_number_id.startswith("PN"):
            st.error("Invalid phoneNumberId. Must match '^PN(.*)'.")
            st.markdown("[Back to Main](?)")
            return

        # Fetch and display history
        with st.spinner("Fetching history..."):
            calls_df, messages_df = get_agent_history(phone_number_id)

            st.markdown("### Last 100 Calls")
            if not calls_df.empty:
                st.dataframe(calls_df)
            else:
                st.info("No calls found.")

            st.markdown("### Last 100 Messages")
            if not messages_df.empty:
                st.dataframe(messages_df)
            else:
                st.info("No messages found.")

        st.markdown("[Back to Main](?)")

    else:
        # Main List View
        st.header("All Phone Numbers")
        
        phone_nums = get_phone_numbers()
        if not phone_nums:
            st.warning("No phone numbers found.")
            return

        # Create table with links
        table_data = []
        for pn in phone_nums:
            pid = pn["phoneNumberId"]
            pnum = pn["phoneNumber"]
            if pid and pid.startswith("PN"):
                link = f'<a href="?phoneNumberId={pid}" target="_self">View History</a>'
            else:
                link = "Invalid ID"
            
            table_data.append({
                "Phone Number": pnum,
                "Details": link
            })

        df = pd.DataFrame(table_data)
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
