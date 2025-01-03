import streamlit as st
import pandas as pd
import time
import requests

################################
# 1) OpenPhone API Credentials #
################################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"  # No 'Bearer '

################################
# 2) Rate-Limited Request      #
################################
def rate_limited_request(url, headers, params=None, request_type='get'):
    """
    A function to make an API request while respecting rate limits.
    """
    if not params:
        params = {}
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

################################
# 3) Fetch Phone Numbers       #
################################
def get_phone_numbers():
    """
    Get all phone numbers from your OpenPhone account.
    Returns a list of dict with phoneNumberId and phoneNumber.
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {
        "Authorization": OPENPHONE_API_KEY,  # no 'Bearer ' prefix
        "Content-Type": "application/json"
    }
    data = rate_limited_request(url, headers, {}, 'get')
    st.write("DEBUG phone-numbers:", data)  # For debugging

    if not data or "data" not in data:
        return []

    results = []
    for item in data["data"]:
        phone_number_id = item.get("id")
        phone_number_str = item.get("phoneNumber") or "No Phone#"
        results.append({
            "phoneNumberId": phone_number_id,
            "phoneNumber": phone_number_str
        })
    return results

################################
# 4) Fetch History (Calls, Msgs)
################################
def get_agent_history(phone_number_id):
    """
    Fetch the last 100 calls and the last 100 messages for this phoneNumberId.
    Return calls_df, messages_df
    """
    headers = {
        "Authorization": OPENPHONE_API_KEY,  # no 'Bearer '
        "Content-Type": "application/json"
    }

    # -- Calls --
    calls_url = "https://api.openphone.com/v1/calls"
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
        calls_df = pd.DataFrame([
            {
                "Created At": c.get("createdAt", ""),
                "Direction": c.get("direction", ""),
                "Duration (sec)": c.get("duration", 0),
                "Status": c.get("status", ""),
                "Transcript": c.get("transcript", ""),
                "Recording URL": c.get("recordingUrl", ""),
            }
            for c in calls_data
        ])
    else:
        calls_df = pd.DataFrame()

    # -- Messages --
    messages_url = "https://api.openphone.com/v1/messages"
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

################################
# 5) Single-Page Streamlit App #
################################
def main():
    st.set_page_config(page_title="OpenPhone Viewer", layout="wide")

    st.title("OpenPhone Viewer")
    st.write("Query Params Debug:", st.query_params)  # Debug line

    # Check for ?phoneNumberId=xxx
    phone_number_id = st.query_params.get("phoneNumberId", [None])[0]

    if phone_number_id:
        # We're in the detail view
        st.subheader(f"Detail View for {phone_number_id}")

        with st.spinner("Fetching calls and messages..."):
            calls_df, messages_df = get_agent_history(phone_number_id)

        st.markdown("### Calls (Last 100)")
        if calls_df.empty:
            st.info("No calls found for this phone number.")
        else:
            st.dataframe(calls_df)

        st.markdown("### Messages (Last 100)")
        if messages_df.empty:
            st.info("No messages found for this phone number.")
        else:
            st.dataframe(messages_df)

        # Back link: remove all query params -> goes to main list
        st.markdown("[Back to Main](?)")

    else:
        # We're in the main list
        st.header("All Phone Numbers")
        phone_numbers = get_phone_numbers()

        if not phone_numbers:
            st.warning("No phone numbers found. Double-check your OpenPhone workspace.")
            return

        # Build a table with clickable links
        rows = []
        for pn in phone_numbers:
            pid = pn["phoneNumberId"]
            phone_str = pn["phoneNumber"]
            if pid:
                # A relative link "?phoneNumberId=PID"
                link_html = f'<a href="?phoneNumberId={pid}" target="_self">View History</a>'
            else:
                link_html = "No ID"
            rows.append({
                "Phone Number": phone_str,
                "Details": link_html
            })

        df = pd.DataFrame(rows)
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
