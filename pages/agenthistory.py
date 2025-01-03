import streamlit as st
import pandas as pd
from urllib.parse import urlencode

# Import existing helpers from communication.py
# Make sure communication.py is in the same folder or in your PYTHONPATH
from communication import (
    OPENPHONE_API_KEY,
    rate_limited_request
)

########################
# 1) Fetch All Agents  #
########################
def get_phone_numbers_and_agents():
    """
    Retrieves phone numbers from OpenPhone and their associated user/agent data.
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
    url = "https://api.openphone.com/v1/phone-numbers"
    # NOTE: No "Bearer " prefix here
    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }
    response_data = rate_limited_request(url, headers, {}, request_type='get')
    results = []
    if response_data and "data" in response_data:
        for pn in response_data["data"]:
            # Each phone number may have a 'users' list
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

##################################
# 2) Fetch Calls & Messages (100) #
##################################
def get_agent_history(phone_number_id):
    """
    Fetch the last 100 calls and last 100 messages for a given phoneNumberId.
    Returns (calls_df, messages_df) as pandas DataFrames.
    """
    # NOTE: No "Bearer " prefix
    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }

    # Endpoints:
    calls_url = "https://api.openphone.com/v1/calls"
    messages_url = "https://api.openphone.com/v1/messages"

    # ------------------------------------------
    # Fetch up to 100 calls via pagination
    # ------------------------------------------
    calls_data = []
    calls_fetched = 0
    next_page = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50,  # fetch 50 at a time
        }
        if next_page:
            params["pageToken"] = next_page

        resp_json = rate_limited_request(calls_url, headers, params, request_type='get')
        if not resp_json or "data" not in resp_json:
            break

        chunk = resp_json["data"]
        calls_data.extend(chunk)
        calls_fetched += len(chunk)
        next_page = resp_json.get("nextPageToken")

        # Stop once we have 100 or no more data
        if not next_page or calls_fetched >= 100:
            break

    # Convert calls to DataFrame
    if calls_data:
        call_rows = []
        for c in calls_data:
            call_rows.append({
                "Created At": c.get("createdAt", ""),
                "Direction": c.get("direction", ""),
                "Duration (sec)": c.get("duration", 0),
                "Status": c.get("status", ""),
                "Transcript": c.get("transcript", ""),       # could be empty
                "Recording URL": c.get("recordingUrl", ""),  # could be empty
            })
        calls_df = pd.DataFrame(call_rows)
    else:
        calls_df = pd.DataFrame()

    # ------------------------------------------
    # Fetch up to 100 messages via pagination
    # ------------------------------------------
    messages_data = []
    msgs_fetched = 0
    next_page = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50,
        }
        if next_page:
            params["pageToken"] = next_page

        resp_json = rate_limited_request(messages_url, headers, params, request_type='get')
        if not resp_json or "data" not in resp_json:
            break

        chunk = resp_json["data"]
        messages_data.extend(chunk)
        msgs_fetched += len(chunk)
        next_page = resp_json.get("nextPageToken")

        # Stop once we have 100 or no more data
        if not next_page or msgs_fetched >= 100:
            break

    # Convert messages to DataFrame
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

########################
# 3) Streamlit App     #
########################
def main():
    st.title("Agent History")

    # Use the new st.query_params
    query_params = st.query_params
    phone_number_id = query_params.get("phoneNumberId", [None])[0]

    if phone_number_id:
        # ===== Detail Page =====
        st.subheader("Last 100 Calls & Messages")

        calls_df, messages_df = get_agent_history(phone_number_id)

        st.markdown("### Calls (Up to 100)")
        if not calls_df.empty:
            st.dataframe(calls_df)
        else:
            st.info("No calls found for this phoneNumberId.")

        st.markdown("### Messages (Up to 100)")
        if not messages_df.empty:
            st.dataframe(messages_df)
        else:
            st.info("No messages found for this phoneNumberId.")

        st.markdown("[Back to Agents List](?phoneNumberId=)")

    else:
        # ===== Main Page (List of Agents) =====
        st.header("All Agents (Phone Numbers) in OpenPhone")

        agents = get_phone_numbers_and_agents()
        if not agents:
            st.warning("No phone numbers (agents) found in your OpenPhone account.")
            return

        # Create a small table with clickable "View History" links
        table_data = []
        for agent in agents:
            pid = agent["phoneNumberId"]
            link_params = {"phoneNumberId": pid}
            view_link = f"[View History]({urlencode(link_params)})"
            table_data.append({
                "Agent Name": agent["userName"],
                "Phone Number": agent["phoneNumber"],
                "Details": view_link
            })

        df = pd.DataFrame(table_data)
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
