# communication_concurrent.py

import time
import requests
from datetime import datetime
import pandas as pd
import streamlit as st
import concurrent.futures
import pytz
from dateutil import parser

###################################################
# 1) FIVE OPENPHONE API KEYS
###################################################
OPENPHONE_API_KEYS = [
    "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7",  # original
    "aU3PhsAQ2Qw0E3WvJcCf4wul8u7QW0u5",
    "v5i6aToq7CbSy8oBodmdHz1i1ByUFNdc",
    "prXONwAEznwZzzTVFSVxym9ykQBiLcpF",
    "tJKJxdTdXrtelTqnDLhKwak3JGJAvHKp"
]

# Your "original" OpenPhone number was: +18438972426
# If you need to store that, keep it, but not strictly required here.

###################################################
# 2) RATE-LIMITED REQUEST
###################################################
def rate_limited_request(url, headers, params, request_type='get'):
    """
    Make an API request while respecting rate limits (lightly).
    Currently sleeps 0.2s => max ~5 requests/sec.
    Adjust as needed.
    """
    time.sleep(0.2)  # limit to ~5 requests/sec
    try:
        if request_type.lower() == 'get':
            response = requests.get(url, headers=headers, params=params)
        else:
            # If you had other request types, handle them here
            response = requests.request(request_type.upper(), url, headers=headers, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error {response.status_code} => {response.text}")
    except Exception as e:
        st.warning(f"Request exception: {str(e)}")
    return None

###################################################
# 3) GET ALL PHONE NUMBER IDS FOR ONE API KEY
###################################################
def get_all_phone_number_ids(api_key):
    """
    Retrieve all phoneNumberIds for the given OpenPhone API key.
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {"Authorization": f"Bearer {api_key}"}
    response_data = rate_limited_request(url, headers, params={})
    if response_data and "data" in response_data:
        return [pn.get('id') for pn in response_data['data']]
    return []

###################################################
# 4) GET COMM INFO FOR ONE GUEST PHONE, ONE PHONE-NUMBER-ID
###################################################
def get_communication_info(api_key, phone_number_id, guest_phone, arrival_date_str):
    """
    Fetch calls & messages for (phone_number_id) with participant = guest_phone,
    count how many are pre-arrival vs post-arrival based on arrival_date_str,
    which is something like "3/27/2025".
    
    OpenPhone timestamps are UTC: "2022-01-01T00:00:00Z".
    We convert them to your local timezone (example: GMT-4).
    """

    # Parse arrival date
    # If arrival_date_str is blank or None, we skip pre/post logic
    local_tz = pytz.timezone("Etc/GMT-4")  # or "America/New_York" if you need DST
    if arrival_date_str:
        arrival_dt = datetime.strptime(arrival_date_str, "%m/%d/%Y")
        arrival_dt_local = local_tz.localize(arrival_dt)
    else:
        arrival_dt_local = None

    headers = {"Authorization": f"Bearer {api_key}"}
    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    # Keep track
    total_messages = 0
    total_calls = 0
    pre_arrival_texts = 0
    post_arrival_texts = 0
    pre_arrival_calls = 0
    post_arrival_calls = 0

    # PAGINATION: MESSAGES
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
            # Convert from UTC
            utc_time = parser.isoparse(msg["createdAt"])
            local_time = utc_time.astimezone(local_tz)

            # Pre/post arrival
            if arrival_dt_local:
                if local_time.date() <= arrival_dt_local.date():
                    pre_arrival_texts += 1
                else:
                    post_arrival_texts += 1

        next_page = data.get("nextPageToken")
        if not next_page:
            break

    # PAGINATION: CALLS
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

###################################################
# 5) FOR ONE GUEST, GATHER FROM ALL PHONE-NUMBER-IDs
#    (FOR A SINGLE API KEY)
###################################################
def fetch_communication_for_guest_and_key(api_key, guest_phone, arrival_date_str):
    """
    1) Get all phoneNumberIds for this API key
    2) For each phoneNumberId, fetch communications with the guest phone
    3) Sum them all up
    """
    phone_number_ids = get_all_phone_number_ids(api_key)

    aggregated = {
        "total_messages": 0,
        "total_calls": 0,
        "pre_arrival_texts": 0,
        "post_arrival_texts": 0,
        "pre_arrival_calls": 0,
        "post_arrival_calls": 0
    }

    for pn_id in phone_number_ids:
        info = get_communication_info(api_key, pn_id, guest_phone, arrival_date_str)
        aggregated["total_messages"]    += info["total_messages"]
        aggregated["total_calls"]       += info["total_calls"]
        aggregated["pre_arrival_texts"] += info["pre_arrival_texts"]
        aggregated["post_arrival_texts"]+= info["post_arrival_texts"]
        aggregated["pre_arrival_calls"] += info["pre_arrival_calls"]
        aggregated["post_arrival_calls"]+= info["post_arrival_calls"]

    return aggregated

###################################################
# 6) CONCURRENT WRAPPER: PROCESS EACH ROW IN PARALLEL
#    AND FOR EACH ROW, LOOP OVER ALL 5 API KEYS
###################################################
def fetch_communication_info_concurrently(owner_df):
    """
    owner_df must have:
      - 'Phone Number'
      - 'Arrival Date Short' (like '3/27/2025')
    We create threads to process each row in parallel.
    """
    results_list = []

    def process_one_row(idx, row):
        phone = row.get("Phone Number", "")
        arrival = row.get("Arrival Date Short", "")

        # "Live logging" at the start of the row:
        st.write(f"[Row {idx}] Starting => Phone={phone}, Arrival={arrival}")

        # If phone invalid => skip
        if not phone or phone == 'No Data':
            st.write(f"[Row {idx}] Invalid phone => skipping.")
            return {
                "status": "Invalid Number",
                "total_messages": 0,
                "total_calls": 0,
                "pre_arrival_texts": 0,
                "post_arrival_texts": 0,
                "pre_arrival_calls": 0,
                "post_arrival_calls": 0
            }

        # For each row, loop over all 5 keys in series
        combined = {
            "status": "OK",
            "total_messages": 0,
            "total_calls": 0,
            "pre_arrival_texts": 0,
            "post_arrival_texts": 0,
            "pre_arrival_calls": 0,
            "post_arrival_calls": 0
        }

        for key_idx, api_key in enumerate(OPENPHONE_API_KEYS, start=1):
            st.write(f"[Row {idx}]  -> Using API key #{key_idx} ...")
            partial = fetch_communication_for_guest_and_key(api_key, phone, arrival)
            combined["total_messages"]       += partial["total_messages"]
            combined["total_calls"]          += partial["total_calls"]
            combined["pre_arrival_texts"]    += partial["pre_arrival_texts"]
            combined["post_arrival_texts"]   += partial["post_arrival_texts"]
            combined["pre_arrival_calls"]    += partial["pre_arrival_calls"]
            combined["post_arrival_calls"]   += partial["post_arrival_calls"]

        st.write(f"[Row {idx}] Finished => "
                 f"{combined['total_messages']} msgs, {combined['total_calls']} calls")

        return combined

    # We’ll use a ThreadPoolExecutor to parallelize “each row”
    max_workers = 5  # adjust up/down as needed
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {}
        for idx, row in owner_df.iterrows():
            # Submit each row to the pool
            future = executor.submit(process_one_row, idx, row)
            future_to_idx[future] = idx

        # Collect results in order
        results = [None] * len(owner_df)
        for future in concurrent.futures.as_completed(future_to_idx):
            idx = future_to_idx[future]
            res = future.result()  # res is the dict from process_one_row
            results[idx] = res

    # Merge back into a DataFrame
    out_df = owner_df.copy()
    out_df["Status"] = [r["status"] for r in results]
    out_df["Total Messages"] = [r["total_messages"] for r in results]
    out_df["Total Calls"] = [r["total_calls"] for r in results]
    out_df["Pre-Arrival Texts"] = [r["pre_arrival_texts"] for r in results]
    out_df["Post-Arrival Texts"] = [r["post_arrival_texts"] for r in results]
    out_df["Pre-Arrival Calls"] = [r["pre_arrival_calls"] for r in results]
    out_df["Post-Arrival Calls"] = [r["post_arrival_calls"] for r in results]

    return out_df

###################################################
# 7) DEMO USAGE
###################################################
def main():
    st.title("Concurrent OpenPhone Fetch (5 API Keys)")

    # Sample data
    data = {
        "Phone Number": ["+11234567890", "+11987654321", "No Data"],
        "Arrival Date Short": ["3/27/2025", "3/27/2025", ""]
    }
    df = pd.DataFrame(data)

    st.write("Starting concurrency with 5 OpenPhone keys...")
    final_df = fetch_communication_info_concurrently(df)
    st.write("All done!")
    st.write(final_df)

# if __name__ == "__main__":
#     main()
