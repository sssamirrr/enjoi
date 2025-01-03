# pages/02_AgentDetail.py
import streamlit as st
import pandas as pd
from communication import OPENPHONE_API_KEY, rate_limited_request

def get_agent_history(phone_number_id):
    """Fetch the last 100 calls & messages for this phoneNumberId."""
    headers = {
        "Authorization": OPENPHONE_API_KEY,  # No 'Bearer '
        "Content-Type": "application/json"
    }
    calls_url = "https://api.openphone.com/v1/calls"
    messages_url = "https://api.openphone.com/v1/messages"

    # =========== Calls ===========
    calls_data = []
    calls_fetched = 0
    next_page = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
        if next_page:
            params["pageToken"] = next_page

        resp = rate_limited_request(calls_url, headers, params, 'get')
        if not resp or "data" not in resp:
            break

        chunk = resp["data"]
        calls_data.extend(chunk)
        calls_fetched += len(chunk)
        next_page = resp.get("nextPageToken")

        if not next_page or calls_fetched >= 100:
            break

    if calls_data:
        calls_df = pd.DataFrame([{
            "Created At": c.get("createdAt", ""),
            "Direction": c.get("direction", ""),
            "Duration": c.get("duration", 0),
            "Status": c.get("status", ""),
            "Transcript": c.get("transcript", ""),
            "Recording URL": c.get("recordingUrl", "")
        } for c in calls_data])
    else:
        calls_df = pd.DataFrame()

    # =========== Messages ===========
    messages_data = []
    messages_fetched = 0
    next_page = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
        if next_page:
            params["pageToken"] = next_page

        resp = rate_limited_request(messages_url, headers, params, 'get')
        if not resp or "data" not in resp:
            break

        chunk = resp["data"]
        messages_data.extend(chunk)
        messages_fetched += len(chunk)
        next_page = resp.get("nextPageToken")

        if not next_page or messages_fetched >= 100:
            break

    if messages_data:
        messages_df = pd.DataFrame([{
            "Created At": m.get("createdAt", ""),
            "Direction": m.get("direction", ""),
            "Content": m.get("content", ""),
            "From": m.get("from", {}).get("phoneNumber", ""),
            "To": ", ".join(t.get("phoneNumber", "") for t in m.get("to", []))
        } for m in messages_data])
    else:
        messages_df = pd.DataFrame()

    return calls_df, messages_df

def main():
    st.title("2) Agent Detail Page")

    query_params = st.query_params
    phone_number_id = query_params.get("phoneNumberId", [None])[0]
    if not phone_number_id:
        st.warning("No 'phoneNumberId' found in query params.")
        # Provide a link back to Page 1
        st.markdown('<a href="?page=01_AgentList" target="_self">Go to Agent List</a>', 
                    unsafe_allow_html=True)
        return

    # Show calls & messages
    calls_df, messages_df = get_agent_history(phone_number_id)

    st.markdown(f"## History for ID: `{phone_number_id}`")

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

    # Simple back link
    st.markdown('<a href="?page=01_AgentList" target="_self">Back to Agent List</a>',
                unsafe_allow_html=True)

if __name__ == "__main__":
    main()
