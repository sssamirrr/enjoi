import streamlit as st
import pandas as pd
import time
import requests
from urllib.parse import urlencode

# -- Import from your communication.py
from communication import (
    OPENPHONE_API_KEY,          # "j4s..." etc.
    rate_limited_request,       # The function you shared in communication.py
    get_all_phone_number_ids,   # If you want to reuse the logic for phone number IDs
)

# Headers WITHOUT "Bearer "
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

def get_phone_numbers_and_users():
    """
    Retrieves phone numbers and the associated user/agent data from OpenPhone.
    Returns a list of dicts like:
    [
      {
        'phoneNumberId': 'pn_id',
        'phoneNumber': '+1...',
        'userName': 'Agent Name'
      },
      ...
    ]
    """
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    response_data = rate_limited_request(phone_numbers_url, HEADERS, {}, request_type='get')
    results = []
    if response_data and "data" in response_data:
        for pn in response_data["data"]:
            # Each phone number object might have users[]
            user_info = pn.get("users", [])
            user_name = user_info[0].get("name", "Unknown Agent") if user_info else "Unknown Agent"
            
            results.append({
                "phoneNumberId": pn.get("id"),
                "phoneNumber": pn.get("phoneNumber"),
                "userName": user_name
            })
    return results


def get_agent_history(phone_number_id):
    """
    Fetch the last 100 calls and last 100 messages for a given phoneNumberId.
    Returns (calls_df, messages_df) DataFrames.
    """

    calls_url = "https://api.openphone.com/v1/calls"
    messages_url = "https://api.openphone.com/v1/messages"

    # --- Fetch calls ---
    calls_data = []
    calls_fetched = 0
    next_page = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50,
        }
        if next_page:
            params["pageToken"] = next_page
        
        call_resp = rate_limited_request(calls_url, HEADERS, params, request_type='get')
        if not call_resp or "data" not in call_resp:
            break
        
        chunk = call_resp["data"]
        calls_data.extend(chunk)
        calls_fetched += len(chunk)
        next_page = call_resp.get("nextPageToken")

        # Stop once we have at least 100
        if not next_page or calls_fetched >= 100:
            break

    # Convert calls to a DataFrame
    if calls_data:
        call_rows = []
        for c in calls_data:
            call_rows.append({
                "Created At": c.get("createdAt", ""),
                "Direction": c.get("direction", ""),
                "Duration (sec)": c.get("duration", 0),
                "Status": c.get("status", ""),
                "Transcript": c.get("transcript", ""),       # May be empty
                "Recording URL": c.get("recordingUrl", ""),  # May be empty
            })
        calls_df = pd.DataFrame(call_rows)
    else:
        calls_df = pd.DataFrame()

    # --- Fetch messages ---
    messages_data = []
    messages_fetched = 0
    next_page = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50,
        }
        if next_page:
            params["pageToken"] = next_page
        
        msg_resp = rate_limited_request(messages_url, HEADERS, params, request_type='get')
        if not msg_resp or "data" not in msg_resp:
            break
        
        chunk = msg_resp["data"]
        messages_data.extend(chunk)
        messages_fetched += len(chunk)
        next_page = msg_resp.get("nextPageToken")

        # Stop once we have at least 100
        if not next_page or messages_fetched >= 100:
            break

    # Convert messages to a DataFrame
    if messages_data:
        msg_rows = []
        for m in messages_data:
            msg_rows.append({
                "Created At": m.get("createdAt", ""),
                "Direction": m.get("direction", ""),
                "Message Content": m.get("content", ""),
                "From": m.get("from", {}).get("phoneNumber", ""),
                "To": ", ".join(t.get("phoneNumber", "") for t in m.get("to", [])),
            })
        messages_df = pd.DataFrame(msg_rows)
    else:
        messages_df = pd.DataFrame()

    return calls_df, messages_df


def main():
    st.title("Agent History")

    # Use st.query_params (modern approach)
    query_params = st.query_params
    phone_number_id = query_params.get("phoneNumberId", [None])[0]

    if phone_number_id:
        # Display the detail page for a specific agent
        st.header("Last 100 Calls & Messages")

        calls_df, messages_df = get_agent_history(phone_number_id)

        st.subheader("Calls (up to 100)")
        if not calls_df.empty:
            st.dataframe(calls_df)
        else:
            st.info("No recent calls for this agent.")

        st.subheader("Messages (up to 100)")
        if not messages_df.empty:
            st.dataframe(messages_df)
        else:
            st.info("No recent messages for this agent.")

        st.markdown("[Back to Agents List](?phoneNumberId=)")
    else:
        # Main page: show all agents
        st.header("All Agents in OpenPhone")

        agent_list = get_phone_numbers_and_users()
        if not agent_list:
            st.warning("No phone numbers (agents) found in your OpenPhone account.")
            return

        # Build a table with a 'View History' link
        table_data = []
        for agent in agent_list:
            pn_id = agent["phoneNumberId"]
            link_params = {"phoneNumberId": pn_id}
            # Build a clickable link
            detail_link = f"[View History]({urlencode(link_params)})"
            table_data.append({
                "Agent Name": agent["userName"],
                "Phone Number": agent["phoneNumber"],
                "Details": detail_link
            })

        df = pd.DataFrame(table_data)
        # Display table with clickable links
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
