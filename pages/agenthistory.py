import streamlit as st
import pandas as pd
from urllib.parse import urlencode

# Import your existing helper functions and API key from communication.py
from communication import (
    OPENPHONE_API_KEY,
    rate_limited_request,
    get_all_phone_number_ids,
)

BASE_URL = "https://api.openphone.com/v1"

def get_phone_numbers_and_users(headers):
    """
    Retrieves phone numbers and the associated user/agent data.
    Returns a list of dicts like:
    [
      {
        'phoneNumberId': 'pn_id',
        'phoneNumber': '+1...',
        'userName': 'Agent A'
      },
      ...
    ]
    """
    phone_numbers_url = f"{BASE_URL}/phone-numbers"
    response_data = rate_limited_request(phone_numbers_url, headers, {})
    results = []
    if response_data and "data" in response_data:
        for pn in response_data["data"]:
            # Each phone number object can have `users` - usually 1 for a single owner
            user_info = pn.get("users", [])
            if user_info:
                user_name = user_info[0].get("name", "Unknown Agent")
            else:
                user_name = "Unknown Agent"
            
            results.append({
                "phoneNumberId": pn.get("id"),
                "phoneNumber": pn.get("phoneNumber"),
                "userName": user_name
            })
    return results

def get_agent_details(phone_number_id, headers):
    """
    Fetch the last 100 calls and last 100 messages for a given phoneNumberId.
    Returns (calls_df, messages_df) dataframes or empty if no data.
    """
    calls_url = f"{BASE_URL}/calls"
    messages_url = f"{BASE_URL}/messages"

    # --- Fetch calls ---
    calls_data = []
    next_page = None
    retrieved = 0
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50,
        }
        if next_page:
            params["pageToken"] = next_page
        response = rate_limited_request(calls_url, headers, params)
        if not response or "data" not in response:
            break

        data_chunk = response["data"]
        calls_data.extend(data_chunk)
        retrieved += len(data_chunk)
        next_page = response.get("nextPageToken")

        # Stop if we've retrieved >= 100
        if not next_page or retrieved >= 100:
            break

    # Convert calls to a dataframe
    if calls_data:
        calls_list = []
        for c in calls_data:
            # Some calls have 'transcript' or 'recordingUrl'
            # Not all calls will have a transcript, so handle safely
            call_transcript = c.get("transcript", "")
            calls_list.append({
                "Created At": c.get("createdAt", ""),
                "Direction": c.get("direction", ""),
                "Duration (sec)": c.get("duration", 0),
                "Status": c.get("status", ""),
                "Transcript": call_transcript,
                "Recording URL": c.get("recordingUrl", "")
            })
        calls_df = pd.DataFrame(calls_list)
    else:
        calls_df = pd.DataFrame()

    # --- Fetch messages ---
    messages_data = []
    next_page = None
    retrieved = 0
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50,
        }
        if next_page:
            params["pageToken"] = next_page
        response = rate_limited_request(messages_url, headers, params)
        if not response or "data" not in response:
            break

        data_chunk = response["data"]
        messages_data.extend(data_chunk)
        retrieved += len(data_chunk)
        next_page = response.get("nextPageToken")

        # Stop if we've retrieved >= 100
        if not next_page or retrieved >= 100:
            break

    # Convert messages to a dataframe
    if messages_data:
        messages_list = []
        for m in messages_data:
            messages_list.append({
                "Created At": m.get("createdAt", ""),
                "Direction": m.get("direction", ""),
                "Message Content": m.get("content", ""),
                "From": m.get("from", {}).get("phoneNumber", ""),
                "To": ", ".join([t.get("phoneNumber", "") for t in m.get("to", [])]),
            })
        messages_df = pd.DataFrame(messages_list)
    else:
        messages_df = pd.DataFrame()

    return calls_df, messages_df


def main():
    st.title("Agent History")

    # We check if there's a query parameter specifying phoneNumberId
    query_params = st.experimental_get_query_params()
    phone_number_id = query_params.get("phoneNumberId", [None])[0]

    headers = {"Authorization": f"Bearer {OPENPHONE_API_KEY}"}

    if phone_number_id:
        # --- Detail page for a specific agent ---
        st.header("Agent Call & Message History")

        calls_df, messages_df = get_agent_details(phone_number_id, headers)

        st.subheader("Last 100 Calls")
        if not calls_df.empty:
            st.dataframe(calls_df)
        else:
            st.info("No calls found for this agent.")

        st.subheader("Last 100 Messages")
        if not messages_df.empty:
            st.dataframe(messages_df)
        else:
            st.info("No messages found for this agent.")

        st.markdown("[Back to Agents List](?phoneNumberId=)")
    else:
        # --- Main page: Show list of agents ---
        st.header("All Agents")

        agent_list = get_phone_numbers_and_users(headers)

        if not agent_list:
            st.info("No phone numbers (agents) found in your OpenPhone account.")
            return

        # Create a table of agent info with a column for 'Details' link
        table_data = []
        for agent in agent_list:
            phone_number_id = agent["phoneNumberId"]
            link_params = {"phoneNumberId": phone_number_id}
            detail_link = f"[View History]({urlencode(link_params)})"
            table_data.append({
                "Agent Name": agent["userName"],
                "Phone Number": agent["phoneNumber"],
                "Details": detail_link
            })

        df = pd.DataFrame(table_data)
        # Use unsafe_allow_html to allow Markdown links
        st.table(df.to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
