# unique_key_per_row.py

import streamlit as st
import pandas as pd
import time
import requests
import concurrent.futures
import queue
from datetime import datetime
import pytz
from dateutil import parser

##########################################################################
# 1) YOUR FIVE OPENPHONE API KEYS, in a queue for exclusive use per row
##########################################################################
OPENPHONE_API_KEYS = [
    "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7",  # newly added
    "aU3PhsAQ2Qw0E3WvJcCf4wul8u7QW0u5",
    "prXONwAEznwZzzTVFSVxym9ykQBiLcpF",
    "v5i6aToq7CbSy8oBodmdHz1i1ByUFNdc",
    "tJKJxdTdXrtelTqnDLhKwak3JGJAvHKp"
]

# Put them in a queue so each row uses a unique key at a time
available_keys = queue.Queue()
for k in OPENPHONE_API_KEYS:
    available_keys.put(k)

##########################################################################
# 2) RATE-LIMITED REQUEST
#    - Sleep 0.2s => ~5 requests/sec per thread
##########################################################################
def rate_limited_request(url, headers, params, request_type='get'):
    """
    Make an API request, sleeping 0.2 seconds each time => ~5 requests/sec.
    If you have higher limits, reduce or remove the sleep.
    """
    time.sleep(0.2)
    try:
        if request_type.lower() == 'get':
            resp = requests.get(url, headers=headers, params=params)
        else:
            resp = requests.request(request_type.upper(), url, headers=headers, params=params)

        if resp and resp.status_code == 200:
            return resp.json()
        else:
            st.warning(f"API Error: {resp.status_code} => {resp.text}")
    except Exception as e:
        st.warning(f"Request exception: {str(e)}")
    return None

##########################################################################
# 3) GET CALL/MSG INFO FOR ONE phoneNumberId
##########################################################################
def get_communication_info(api_key, phone_number_id, guest_phone, arrival_date_str):
    """
    Fetch calls & messages for one phoneNumberId, for guest_phone,
    counting pre vs. post arrival_date_str (like '3/27/2025') if valid.
    """
    local_tz = pytz.timezone("Etc/GMT-4")  # or "America/New_York" if DST needed

    # Parse arrival_date_str if it's not empty
    if arrival_date_str:
        try:
            arrival_dt = datetime.strptime(arrival_date_str, "%m/%d/%Y")
            arrival_dt_local = local_tz.localize(arrival_dt)
        except ValueError:
            # If invalid (e.g., not mm/dd/yyyy), treat as None
            arrival_dt_local = None
    else:
        arrival_dt_local = None

    headers = {"Authorization": f"Bearer {api_key}"}
    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    total_messages = 0
    total_calls = 0
    pre_arrival_texts = 0
    post_arrival_texts = 0
    pre_arrival_calls = 0
    post_arrival_calls = 0

    # -----------------------
    # PAGINATION: MESSAGES
    # -----------------------
    next_page = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "participants": [guest_phone],
            "maxResults": 50
        }
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request(messages_url, headers, params)
        if not data or "data" not in data:
            break

        for msg in data["data"]:
            total_messages += 1
            # convert UTC -> local
            utc_time = parser.isoparse(msg["createdAt"])
            local_time = utc_time.astimezone(local_tz)
            if arrival_dt_local:
                if local_time.date() <= arrival_dt_local.date():
                    pre_arrival_texts += 1
                else:
                    post_arrival_texts += 1

        next_page = data.get("nextPageToken")
        if not next_page:
            break

    # -----------------------
    # PAGINATION: CALLS
    # -----------------------
    next_page = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "participants": [guest_phone],
            "maxResults": 50
        }
        if next_page:
            params["pageToken"] = next_page

        data = rate_limited_request(calls_url, headers, params)
        if not data or "data" not in data:
            break

        for call in data["data"]:
            total_calls += 1
            utc_time = parser.isoparse(call["createdAt"])
            local_time = utc_time.astimezone(local_tz)
            if arrival_dt_local:
                if local_time.date() <= arrival_dt_local.date():
                    pre_arrival_calls += 1
                else:
                    post_arrival_calls += 1

        next_page = data.get("nextPageToken")
        if not next_page:
            break

    return {
        "total_messages": total_messages,
        "total_calls": total_calls,
        "pre_arrival_texts": pre_arrival_texts,
        "post_arrival_texts": post_arrival_texts,
        "pre_arrival_calls": pre_arrival_calls,
        "post_arrival_calls": post_arrival_calls
    }

##########################################################################
# 4) FETCH ALL phoneNumberIds FOR ONE KEY, THEN CALLS + MESSAGES FOR GUEST
##########################################################################
def fetch_communication_for_guest_and_key(api_key, guest_phone, arrival_date_str):
    """
    1) Get all phoneNumberIds for api_key
    2) For each phoneNumberId, gather calls+msgs for guest_phone
    3) Sum them up
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    data = rate_limited_request(phone_numbers_url, headers, params={})
    phone_number_ids = []
    if data and "data" in data:
        phone_number_ids = [pn.get("id") for pn in data["data"]]

    # aggregate
    result = {
        "total_messages": 0,
        "total_calls": 0,
        "pre_arrival_texts": 0,
        "post_arrival_texts": 0,
        "pre_arrival_calls": 0,
        "post_arrival_calls": 0
    }

    for pn_id in phone_number_ids:
        info = get_communication_info(api_key, pn_id, guest_phone, arrival_date_str)
        result["total_messages"]       += info["total_messages"]
        result["total_calls"]          += info["total_calls"]
        result["pre_arrival_texts"]    += info["pre_arrival_texts"]
        result["post_arrival_texts"]   += info["post_arrival_texts"]
        result["pre_arrival_calls"]    += info["pre_arrival_calls"]
        result["post_arrival_calls"]   += info["post_arrival_calls"]

    return result

##########################################################################
# 5) PROCESS A SINGLE ROW: GRAB A KEY FROM THE QUEUE, DO THE FETCH, RETURN KEY
##########################################################################
def process_one_row(idx, row):
    phone = row.get("Phone Number", "")
    arrival = str(row.get("Arrival Date Short", "")).strip()

    st.write(f"[Row {idx}] Starting => phone='{phone}', arrival='{arrival}'")

    if not phone or phone.lower() == "no data":
        st.write(f"[Row {idx}]  -> Invalid phone => skipping.")
        return {
            "status": "Invalid Number",
            "total_messages": 0,
            "total_calls": 0,
            "pre_arrival_texts": 0,
            "post_arrival_texts": 0,
            "pre_arrival_calls": 0,
            "post_arrival_calls": 0
        }

    # --------------- Pick a key from the pool ---------------
    api_key = available_keys.get()
    st.write(f"[Row {idx}]  -> Using API key: {api_key[:6]}...")  # partial key for logging

    try:
        partial = fetch_communication_for_guest_and_key(api_key, phone, arrival)
        combined = {
            "status": "OK",
            "total_messages": partial["total_messages"],
            "total_calls": partial["total_calls"],
            "pre_arrival_texts": partial["pre_arrival_texts"],
            "post_arrival_texts": partial["post_arrival_texts"],
            "pre_arrival_calls": partial["pre_arrival_calls"],
            "post_arrival_calls": partial["post_arrival_calls"]
        }
    finally:
        # put the key back so another row can use it
        available_keys.put(api_key)

    st.write(
        f"[Row {idx}] Finished => "
        f"{combined['total_messages']} msgs, {combined['total_calls']} calls"
    )
    return combined

##########################################################################
# 6) MAIN FUNCTION: RUN ROWS IN PARALLEL, ONE KEY PER ROW
##########################################################################
def fetch_communication_info_unique_keys(owner_df):
    """
    Each row is processed in parallel, each row uses a unique key from the queue.
    Returns a new DataFrame with columns for total/pre/post calls/messages.
    """
    results = [None]*len(owner_df)

    def row_worker(idx, row):
        return (idx, process_one_row(idx, row))

    # up to 5 concurrent rows => each row uses a different key from the queue
    max_workers = 5
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {}
        for i, row in owner_df.iterrows():
            fut = executor.submit(row_worker, i, row)
            future_to_idx[fut] = i

        for fut in concurrent.futures.as_completed(future_to_idx):
            idx, result_dict = fut.result()
            results[idx] = result_dict

    # build output DF
    out_df = owner_df.copy()
    out_df["Status"] = [r["status"] for r in results]
    out_df["Total Messages"] = [r["total_messages"] for r in results]
    out_df["Total Calls"] = [r["total_calls"] for r in results]
    out_df["Pre-Arrival Texts"] = [r["pre_arrival_texts"] for r in results]
    out_df["Post-Arrival Texts"] = [r["post_arrival_texts"] for r in results]
    out_df["Pre-Arrival Calls"] = [r["pre_arrival_calls"] for r in results]
    out_df["Post-Arrival Calls"] = [r["post_arrival_calls"] for r in results]

    return out_df

##########################################################################
# 7) DEMO USAGE
##########################################################################
def main():
    st.title("Concurrent Rows, Each Row Uses a Distinct Key (Total 5 Keys)")

    sample_data = {
        "Phone Number": ["+1234567890", "+1987654321", "No Data", "+14443339999", "+13081112222"],
        "Arrival Date Short": ["3/27/2025", "3/28/2025", "", "4/01/2025", "5/02/2025"]
    }
    df = pd.DataFrame(sample_data)

    st.write("Starting concurrency: each row uses a different key from the pool if available...")
    final_df = fetch_communication_info_unique_keys(df)
    st.write("All done!")
    st.dataframe(final_df)

# if __name__ == "__main__":
#     main()
