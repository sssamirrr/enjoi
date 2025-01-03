import streamlit as st
import pandas as pd
import time
import requests
from urllib.parse import urlencode

################################
# 0) Configure your base URL   #
################################
# Replace this with your actual .streamlit.app URL (without a trailing slash).
BASE_URL = "https://ldmcbiowzbdeqvmabvudyy.streamlit.app"

################################
# 1) OpenPhone API Helpers     #
################################

# Your OpenPhone API key WITHOUT "Bearer "
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

def rate_limited_request(url, headers, params, request_type='get'):
    """Make an API request while respecting rate limits."""
    time.sleep(1 / 5)  # Up to 5 requests per second
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
        st.warning(f"Exception during request: {str(e)}")
    return None

def get_phone_numbers():
    """
    Fetch phoneNumberId and phoneNumber for all numbers in your OpenPhone account.
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {"Authorization": OPENPHONE_API_KEY, "Content-Type": "application/json"}

    data = rate_limited_request(url, headers, {}, 'get')
    if not data or "data" not in data:
        return []

    results = []
    for pn in data["data"]:
        phone_number_id = pn.get("id")
        phone_number_str = pn.get("phoneNumber") or "No Phone#"
        results.append({
            "phoneNumberId": phone_number_id,
            "phoneNumber": phone_number_str,
        })
    return results

def get_agent_history(phone_number_id):
    """
    Fetch the last 100 calls and last 100 messages for a given phoneNumberId.
    Returns (calls_df, messages_df) DataFrames.
    """
    headers = {"Authorization": OPENPHONE_API_KEY, "Content-Type": "application/json"}

    # -- Calls --
    calls_url = "https://api.openphone.com/v1/calls"
    calls_data = []
    fetched = 0
    next_token = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
        if next_token:
            params["pageToken"] = next_token

        resp = rate_limited_request(calls_url, headers, params, 'get')
        if not resp or "data" not in resp:
            break

        chunk = resp["data"]
        calls_data.extend(chunk)
        fetched += len(chunk)
        next_token = resp.get("nextPageToken")
        if not next_token or fetched >= 100:
            break

    if calls_data:
        calls_df = pd.DataFrame([{
            "Created At": c.get("createdAt", ""),
            "Direction": c.get("direction", ""),
            "Duration (sec)": c.get("duration", 0),
            "Status": c.get("status", ""),
            "Transcript": c.get("transcript", ""),
            "Recording URL": c.get("recordingUrl", ""),
        } for c in calls_data])
    else:
        calls_df = pd.DataFrame()

    # -- Messages --
    messages_url = "https://api.openphone.com/v1/messages"
    messages_data = []
    fetched = 0
    next_token = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
        if next_token:
            params["pageToken"] = next_token

        resp = rate_limited_request(messages_url, headers, params, 'get')
        if not resp or "data" not in resp:
            break
        chunk = resp["data"]
        messages_data.extend(chunk)
        fetched += len(chunk)
        next_token = resp.get("nextPageToken")
        if not next_token or fetched >= 100:
            break

    if messages_data:
        messages_df = pd.DataFrame([{
            "Created At": m.get("createdAt", ""),
            "Direction": m.get("direction", ""),
            "Message Content": m.get("content", ""),
            "From": m.get("from", {}).get("phoneNumber", ""),
            "To": ", ".join(t.get("phoneNumber", "") for t in m.get("to", [])),
        } for m in messages_data])
    else:
        messages_df = pd.DataFrame()

    return calls_df, messages_df

################################
# 2) Single-Page Streamlit App #
################################

def main():
    st.title("Single Page with Full-URL Links (.streamlit.app)")

    # Check if we have phoneNumberId in query params
    phone_number_id = st.query_params.get("phoneNumberId", [None])[0]

    if phone_number_id:
        # ----- Detail View -----
        st.subheader(f"Detail View for {phone_number_id}")

        calls_df, messages_df = get_agent_history(phone_number_id)

        st.markdown("### Last 100 Calls")
        if calls_df.empty:
            st.info("No calls found.")
        else:
            st.dataframe(calls_df)

        st.markdown("### Last 100 Messages")
        if messages_df.empty:
            st.info("No messages found.")
        else:
            st.dataframe(messages_df)

        # Link to reset param -> go back to main list
        back_url = f"{BASE_URL}"  # no query
        st.markdown(f"[Back to Main List]({back_url})")

    else:
        # ----- Main List of PhoneNumbers -----
        st.header("All Phone Numbers")

        phone_numbers = get_phone_numbers()
        if not phone_numbers:
            st.warning("No phone numbers found in OpenPhone.")
            return

        table_rows = []
        for item in phone_numbers:
            pid = item["phoneNumberId"]
            pstr = item["phoneNumber"]
            if pid:
                # Build a full URL that sets ?phoneNumberId=pid
                # target="_blank" => opens in new tab
                link_params = {"phoneNumberId": pid}
                full_url = f"{BASE_URL}?{urlencode(link_params)}"
                link_html = f'<a href="{full_url}" target="_blank">View History</a>'
            else:
                link_html = "No ID"

            table_rows.append({
                "Phone Number": pstr,
                "Detail": link_html
            })

        df = pd.DataFrame(table_rows)
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
