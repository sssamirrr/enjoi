import streamlit as st
import pandas as pd
import time
import requests

##############################
# 1) OpenPhone API Key Setup #
##############################
# Your OpenPhone API key WITHOUT 'Bearer '
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

##############################
# 2) Rate-Limited Request    #
##############################
def rate_limited_request(url, headers, params=None, request_type='get'):
    """
    Make an API request while respecting rate limits (5 requests per second).
    """
    if params is None:
        params = {}
    time.sleep(1 / 5)  # ~5 requests/second
    try:
        if request_type.lower() == 'get':
            r = requests.get(url, headers=headers, params=params)
        else:
            r = None

        if r and r.status_code == 200:
            return r.json()
        else:
            st.warning(f"API Error: {r.status_code}")
            st.warning(f"Response: {r.text}")
    except Exception as e:
        st.warning(f"Exception: {str(e)}")
    return None

##############################
# 3) Fetch Phone Number List #
##############################
def get_phone_numbers():
    """
    Fetch a list of all phone numbers in your OpenPhone account.
    Returns a list of dicts: [{phoneNumberId, phoneNumber}, ...]
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {
        "Authorization": OPENPHONE_API_KEY,  # no 'Bearer '
        "Content-Type": "application/json"
    }
    data = rate_limited_request(url, headers, {})
    if not data or "data" not in data:
        return []

    results = []
    for pn in data["data"]:
        pid = pn.get("id")
        pnum = pn.get("phoneNumber") or "No Phone#"
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
    Returns (calls_df, messages_df) for the given phoneNumberId.
    - Last 100 calls with transcripts if available
    - Last 100 messages with full text
    """
    # 1) Calls
    calls_data = fetch_calls(phone_number_id, max_contacts=100)
    if calls_data:
        calls_df = pd.DataFrame([{
            "Created At": c.get("createdAt", ""),
            "Direction": c.get("direction", ""),
            "Duration (sec)": c.get("duration", 0),
            "Status": c.get("status", ""),
            "Transcript": c.get("transcript", ""),
            "Recording URL": c.get("recordingUrl", "")
        } for c in calls_data])
    else:
        calls_df = pd.DataFrame()

    # 2) Messages
    messages_data = fetch_messages(phone_number_id, max_contacts=100)
    if messages_data:
        messages_df = pd.DataFrame([{
            "Created At": m.get("createdAt", ""),
            "Direction": m.get("direction", ""),
            "Message Content": m.get("content", ""),
            "From": m.get("from", {}).get("phoneNumber", ""),
            "To": ", ".join(x.get("phoneNumber", "") for x in m.get("to", []))
        } for m in messages_data])
    else:
        messages_df = pd.DataFrame()

    return calls_df, messages_df

##############################
# 5) Single-Page Streamlit   #
##############################
def main():
    st.set_page_config(page_title="OpenPhone Full List", layout="wide")
    st.title("OpenPhone Full List & Contact History")

    # 1) Check if there's a query param phoneNumberId
    phone_number_id = st.query_params.get("phoneNumberId", [None])[0]

    if phone_number_id:
        # Show detail for that phoneNumberId
        st.subheader(f"Last 100 Calls & Messages for {phone_number_id}")
        with st.spinner("Loading history..."):
            calls_df, messages_df = get_agent_history(phone_number_id)

        st.markdown("### Last 100 Calls")
        if calls_df.empty:
            st.info("No calls found for this phone number.")
        else:
            st.dataframe(calls_df)

        st.markdown("### Last 100 Messages")
        if messages_df.empty:
            st.info("No messages found for this phone number.")
        else:
            st.dataframe(messages_df)

        st.markdown("[Back to List](?)")  # Clears query param
    else:
        # Show the main list of phone numbers
        st.header("All Phone Numbers in Your OpenPhone Account")

        phone_numbers = get_phone_numbers()
        if not phone_numbers:
            st.warning("No phone numbers found. Ensure your OpenPhone account has assigned lines.")
            return

        # Build a table with clickable links
        rows = []
        for pn in phone_numbers:
            pid = pn["phoneNumberId"]
            pnum = pn["phoneNumber"]
            if pid:
                link_html = f'<a href="?phoneNumberId={pid}" target="_self">View History</a>'
            else:
                link_html = "No ID"
            rows.append({
                "Phone Number": pnum,
                "Details": link_html
            })

        df = pd.DataFrame(rows)
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
