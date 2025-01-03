import streamlit as st
import pandas as pd
import time
import requests
from urllib.parse import urlencode

############################
# 1) OpenPhone API Key     #
############################
# If OpenPhone requires "Bearer ", prepend it:
# OPENPHONE_API_KEY = "Bearer j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

############################
# 2) Rate-limited request  #
############################
def rate_limited_request(url, headers, params=None, request_type='get'):
    """
    Makes a GET request, sleeping ~1/5 second to respect ~5 req/sec.
    Prints errors if any.
    """
    if params is None:
        params = {}
    time.sleep(1/5)
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
    """
    Lists all phone numbers from /v1/phone-numbers.
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    data = rate_limited_request(url, get_headers())
    st.write("DEBUG /v1/phone-numbers RAW:", data)  # Debug full response

    if not data or "data" not in data:
        return []

    results = []
    for pn in data["data"]:
        pid = pn.get("id","")
        pnum = pn.get("phoneNumber","No Number")
        results.append({"id": pid, "phoneNumber": pnum})
    return results

##############################
# 4) Fetch Calls          #
##############################
def get_calls():
    """
    Lists all calls from /v1/calls.
    """
    url = "https://api.openphone.com/v1/calls"
    data = rate_limited_request(url, get_headers())
    st.write("DEBUG /v1/calls RAW:", data)  # Debug full response

    if not data or "data" not in data:
        return []

    results = []
    for c in data["data"]:
        pid = c.get("id","")
        pnum = c.get("phoneNumber","No Number")
        results.append({"id": pid, "phoneNumber": pnum})
    return results

##############################
# 5) Fetch Messages       #
##############################
def get_messages():
    """
    Lists all messages from /v1/messages.
    """
    url = "https://api.openphone.com/v1/messages"
    data = rate_limited_request(url, get_headers())
    st.write("DEBUG /v1/messages RAW:", data)  # Debug full response

    if not data or "data" not in data:
        return []

    results = []
    for m in data["data"]:
        pid = m.get("id","")
        pnum = m.get("phoneNumber","No Number")
        results.append({"id": pid, "phoneNumber": pnum})
    return results

##############################
# 6) Fetch Contact Numbers #
##############################
def get_contact_numbers_from_call(c):
    """
    Fetches contact numbers from a call.
    """
    url = f"https://api.openphone.com/v1/calls/{c['id']}/participants"
    data = rate_limited_request(url, get_headers())
    return [pn["phoneNumber"] for pn in data["data"]]

def get_contact_numbers_from_message(m):
    """
    Fetches contact numbers from a message.
    """
    url = f"https://api.openphone.com/v1/messages/{m['id']}/participants"
    data = rate_limited_request(url, get_headers())
    return [pn["phoneNumber"] for pn in data["data"]]

##############################
# 7) Main Function       #
##############################
def main():
    phone_number_id = st.text_input("Enter Phone Number ID")

    if phone_number_id:
        contact_set = set()

        calls = get_calls()
        for c in calls:
            cnums = get_contact_numbers_from_call(c)
            contact_set.update(cnums)

        msgs = get_messages()
        for m in msgs:
            mnums = get_contact_numbers_from_message(m)
            contact_set.update(mnums)

        if not contact_set:
            st.info("No contacts found in last 100 calls/messages.")
            st.markdown("[Back to Main](?)")
            return

        rows = []
        for cn in contact_set:
            link_params = {"phoneNumberId": phone_number_id, "contactNumber": cn}
            link_html = f'<a href="?{urlencode(link_params)}" target="_self">View Full Logs</a>'
            rows.append({"Contact Phone": cn, "Details": link_html})

        st.markdown(pd.DataFrame(rows).to_html(escape=False, index=False), unsafe_allow_html=True)
        st.markdown("[Back to Main](?)")

    else:
        # LEVEL 0: Show all phone numbers
        st.header("All Phone Numbers in Your Workspace")

        with st.spinner("Loading phone numbers..."):
            phone_nums = get_phone_numbers()

        if not phone_nums:
            st.warning("No phone numbers found or invalid API Key.")
            return

        data_list = []
        for pn in phone_nums:
            pid = pn["id"]
            num = pn["phoneNumber"]
            if pid and pid.startswith("PN"):
                link_html = f'<a href="?{urlencode({"phoneNumberId": pid})}" target="_self">Show Contacts</a>'
            else:
                link_html = "Invalid / No ID"

            data_list.append({
                "Phone Number": num,
                "Details": link_html
            })

        st.markdown(pd.DataFrame(data_list).to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
