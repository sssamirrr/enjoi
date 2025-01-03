# pages/02_AgentDetail.py
import streamlit as st
import pandas as pd
from communication import OPENPHONE_API_KEY, rate_limited_request

def get_agent_history(phone_number_id):
    """
    Fetch up to 100 calls and 100 messages for a given phoneNumberId.
    Returns (calls_df, messages_df).
    """
    headers = {
        "Authorization": OPENPHONE_API_KEY,  # no 'Bearer '
        "Content-Type": "application/json"
    }

    calls_url = "https://api.openphone.com/v1/calls"
    messages_url = "https://api.openphone.com/v1/messages"

    # --- Calls ---
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

        resp_json = rate_limited_request(calls_url, headers, params, 'get')
        if not resp_json or "data" not in resp_json:
            break

        chunk = resp_json["data"]
        calls_data.extend(chunk)
        calls_fetched += len(chunk)
        next_page = resp_json.get("nextPageToken")

        if not next_page or calls_fetched >= 100:
            break

    if calls_data:
        call_rows = []
        for c in calls_data:
            call_rows.append({
                "Created At": c.get("createdAt", ""),
                "Direction": c.get("direction", ""),
                "Duration (sec)": c.get("duration", 0),
                "Status": c.get("status", ""),
                "Transcript": c.get("transcript", ""),       # might be empty
                "Recording URL": c.get("recordingUrl", ""),  # might be empty
            })
        calls_df = pd.DataFrame(call_rows)
    else:
        calls_df = pd.DataFrame()

    # --- Messages ---
    messages_data = []
    msgs_fetched = 0
    next_page = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
        if next_page:
            params["pageToken"] = next_page

        resp_json = rate_limited_request(messages_url, headers, params, 'get')
        if not resp_json or "data" not in resp_json:
            break

        chunk = resp_json["data"]
        messages_data.extend(chunk)
        msgs_fetched += len(chunk)
        next_page = resp_json.get("nextPageToken")

        if not next_page or msgs_fetched >= 100:
            break

    if messages_data:
        msg_rows = []
        for m in messages_data:
            msg_rows.append({
                "Created At": m.get("createdAt", ""),
                "Direction": m.get("direction", ""),
                "Message Content": m.get("content", ""),
                "From": m.get("from", {}).get("phoneNumber", ""),
                "To": ", ".join(t.get("phoneNumber", "") for t in m.get("to", []))
            })
        messages_df = pd.DataFrame(msg_rows)
    else:
        messages_df = pd.DataFrame()

    return calls_df, messages_df

def main():
    st.title("Agent Detail Page")

    # Grab the phoneNumberId query param
    query_params = st.query_params
    phone_number_id = query_params.get("phoneNumberId", [None])[0]

    if not phone_number_id:
        st.warning("No phoneNumberId provided in the URL.")
        st.markdown('<a href="01_AgentList" target="_self">Go to Agent List</a>', 
                    unsafe_allow_html=True)
        return

    # Show calls & messages
    calls_df, messages_df = get_agent_history(phone_number_id)

    st.markdown(f"## History for: `{phone_number_id}`")

    st.markdown("### Calls (up to 100)")
    if not calls_df.empty:
        st.dataframe(calls_df)
    else:
        st.info("No recent calls found.")

    st.markdown("### Messages (up to 100)")
    if not messages_df.empty:
        st.dataframe(messages_df)
    else:
        st.info("No recent messages found.")

    # Simple back link
    st.markdown('<a href="01_AgentList" target="_self">Back to Agent List</a>', 
                unsafe_allow_html=True)

if __name__ == "__main__":
    main()
