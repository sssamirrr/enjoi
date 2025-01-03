import time
import requests
import streamlit as st
import pandas as pd

OPENPHONE_API_KEY = "YOUR_OPENPHONE_API_KEY"

def rate_limited_request(url, headers, params, request_type='get'):
    time.sleep(1 / 5)  # 5 requests/second
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

def fetch_calls(phone_number_id, max_count=100):
    """
    Fetch up to max_count calls for a given phoneNumberId, no participants filter.
    """
    if not phone_number_id or not phone_number_id.startswith("PN"):
        # Invalid phoneNumberId
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
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50  # fetch 50 at a time
        }
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request(calls_url, headers, params, 'get')
        if not data or "data" not in data:
            break

        chunk = data["data"]
        all_calls.extend(chunk)
        fetched += len(chunk)

        next_page = data.get("nextPageToken")
        if not next_page or fetched >= max_count:
            break

    return all_calls

def fetch_messages(phone_number_id, max_count=100):
    """
    Fetch up to max_count messages for a given phoneNumberId, no participants filter.
    """
    if not phone_number_id or not phone_number_id.startswith("PN"):
        # Invalid phoneNumberId
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
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request(messages_url, headers, params, 'get')
        if not data or "data" not in data:
            break

        chunk = data["data"]
        all_msgs.extend(chunk)
        fetched += len(chunk)

        next_page = data.get("nextPageToken")
        if not next_page or fetched >= max_count:
            break

    return all_msgs


def get_agent_history(phone_number_id):
    """
    Combined function: returns (calls_df, messages_df).
    Omits participants to avoid 400 errors.
    """
    # 1) Fetch calls
    calls_data = fetch_calls(phone_number_id, max_count=100)
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

    # 2) Fetch messages
    messages_data = fetch_messages(phone_number_id, max_count=100)
    if messages_data:
        messages_df = pd.DataFrame([{
            "Created At": m.get("createdAt", ""),
            "Direction": m.get("direction", ""),
            "Message Content": m.get("content", ""),
            "From": m.get("from", {}).get("phoneNumber", ""),
            "To": ", ".join(t.get("phoneNumber", "") for t in m.get("to", []))
        } for m in messages_data])
    else:
        messages_df = pd.DataFrame()

    return calls_df, messages_df


def main():
    st.title("OpenPhone Fix for 400 Error Demo")

    # Example usage:
    test_phone_number_id = st.text_input("Enter phoneNumberId (must start with PN...)",
                                         value="PNsyKJnJnG")

    if st.button("Fetch Data"):
        calls_df, messages_df = get_agent_history(test_phone_number_id)

        st.markdown("### Calls")
        if calls_df.empty:
            st.info("No calls returned or invalid ID.")
        else:
            st.dataframe(calls_df)

        st.markdown("### Messages")
        if messages_df.empty:
            st.info("No messages returned or invalid ID.")
        else:
            st.dataframe(messages_df)

if __name__ == "__main__":
    main()
