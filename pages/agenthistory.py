import streamlit as st
import pandas as pd
import time
import requests
from urllib.parse import urlencode

############################
# 1) OpenPhone API Key     #
############################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

############################
# 2) Rate-limited request  #
############################
def rate_limited_request(url, headers, params=None, request_type='get'):
    if params is None:
        params = {}
    time.sleep(1/5)  # ~5 requests/sec rate limit
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

def get_headers():
    return {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }

##############################
# 3) Fetch PhoneNumbers      #
##############################
def get_phone_numbers():
    url = "https://api.openphone.com/v1/phone-numbers"
    data = rate_limited_request(url, get_headers())
    st.write("DEBUG /v1/phone-numbers RAW:", data)

    if not data or "data" not in data:
        return []

    results = []
    for pn in data["data"]:
        pid = pn.get("id", "")
        pnum = pn.get("phoneNumber", "No Number")
        results.append({"id": pid, "phoneNumber": pnum})
    return results

##############################
# 4) Fetch Calls & Messages  #
##############################
def fetch_calls(phone_number_id, participant_number=None, max_records=100):
    if not phone_number_id or not phone_number_id.startswith("PN"):
        return []

    calls_url = "https://api.openphone.com/v1/calls"
    all_calls = []
    fetched = 0
    next_page = None

    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
        if participant_number:
            params["participants"] = [participant_number]
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request(calls_url, get_headers(), params, 'get')
        st.write("DEBUG /v1/calls chunk RAW:", data)

        if not data or "data" not in data:
            break

        all_calls.extend(data["data"])
        fetched += len(data["data"])
        next_page = data.get("nextPageToken")
        if not next_page or fetched >= max_records:
            break

    return all_calls

def fetch_messages(phone_number_id, participant_number=None, max_records=100):
    if not phone_number_id or not phone_number_id.startswith("PN"):
        return []

    msgs_url = "https://api.openphone.com/v1/messages"
    all_msgs = []
    fetched = 0
    next_page = None

    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "maxResults": 50
        }
        if participant_number:
            params["participants"] = [participant_number]
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request(msgs_url, get_headers(), params, 'get')
        st.write("DEBUG /v1/messages chunk RAW:", data)

        if not data or "data" not in data:
            break

        all_msgs.extend(data["data"])
        fetched += len(data["data"])
        next_page = data.get("nextPageToken")
        if not next_page or fetched >= max_records:
            break

    return all_msgs

##############################
# 5) Main App                #
##############################
def parse_query_param(param):
    if param is None:
        return None
    if isinstance(param, str):
        return param
    if isinstance(param, list) and len(param) > 0:
        return param[0]
    return None

def main():
    st.set_page_config(page_title="OpenPhone Multi-Level Debug", layout="wide")
    st.title("OpenPhone Multi-Level Debug (Enhanced)")

    # Parse query params
    qparams = st.query_params
    phone_number_id = parse_query_param(qparams.get("phoneNumberId"))
    participant_number = parse_query_param(qparams.get("participantNumber"))

    st.write("DEBUG phoneNumberId:", phone_number_id)
    st.write("DEBUG participantNumber:", participant_number)

    if phone_number_id:
        st.subheader(f"Data for PhoneNumber ID: {phone_number_id}")

        with st.spinner("Fetching data..."):
            calls = fetch_calls(phone_number_id, participant_number)
            msgs = fetch_messages(phone_number_id, participant_number)

        # Display Calls
        st.markdown("### Calls")
        if calls:
            st.dataframe(pd.DataFrame(calls))
        else:
            st.info("No calls found.")

        # Display Messages
        st.markdown("### Messages")
        if msgs:
            st.dataframe(pd.DataFrame(msgs))
        else:
            st.info("No messages found.")
    else:
        st.header("Phone Numbers")
        phone_nums = get_phone_numbers()
        if phone_nums:
            st.dataframe(pd.DataFrame(phone_nums))
        else:
            st.warning("No phone numbers found.")

if __name__ == "__main__":
    main()
