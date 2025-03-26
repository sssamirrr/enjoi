import time
import requests
import pytz
from dateutil import parser
from datetime import datetime
import concurrent.futures
import pandas as pd
import streamlit as st

#########################################################
# 1) YOUR FOUR OPENPHONE API KEYS
#########################################################
OPENPHONE_API_KEYS = [
    "aU3PhsAQ2Qw0E3WvJcCf4wul8u7QW0u5",
    "v5i6aToq7CbSy8oBodmdHz1i1ByUFNdc",
    "prXONwAEznwZzzTVFSVxym9ykQBiLcpF",
    "tJKJxdTdXrtelTqnDLhKwak3JGJAvHKp"
]

#########################################################
# 2) HELPER: RATE-LIMITED REQUEST
#########################################################
def rate_limited_request(url, headers, params, request_type='get'):
    """
    Make an API request with a small sleep to reduce risk of 429 errors.
    Adjust the sleep or remove if needed.
    """
    time.sleep(0.2)  # 5 requests/sec => 0.2s per request
    try:
        if request_type.lower() == 'get':
            response = requests.get(url, headers=headers, params=params)
        else:
            response = requests.request(request_type.upper(), url, headers=headers, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error: {response.status_code}")
            st.warning(f"Response: {response.text}")
    except Exception as e:
        st.warning(f"Exception during request: {str(e)}")

    return None

#########################################################
# 3) GET ALL PHONE NUMBERS (FOR A GIVEN KEY)
#########################################################
def get_all_phone_number_ids(api_key):
    """
    Retrieve all phoneNumberIds associated with one OpenPhone API key.
    """
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    data = rate_limited_request(url, headers, params={})
    if not data or "data" not in data:
        return []
    # Extract IDs
    return [pn.get('id') for pn in data['data']]

#########################################################
# 4) FETCH CALLS & MESSAGES FOR ONE PHONE NUMBER ID
#    (This is the same old approach – if you must do per-guest calls,
#     you can still parallelize across multiple keys or phone numbers.)
#########################################################
def get_communication_info_for_guest(
    api_key, phone_number_id, guest_phone, arrival_date_local
):
    """
    For a single phoneNumberId and a single guest phone,
    fetch calls and messages, classify them as pre or post arrival,
    and return aggregated data.

    `arrival_date_local` is a naive or aware datetime in your local (GMT-4) time zone
    you want to compare against.
    """
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    # Basic counters
    total_messages = 0
    total_calls = 0
    pre_arrival_texts = 0
    post_arrival_texts = 0
    pre_arrival_calls = 0
    post_arrival_calls = 0

    # PAGINATION for messages
    next_page = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "participants": [guest_phone],
            "maxResults": 50
        }
        if next_page:
            params['pageToken'] = next_page

        resp = rate_limited_request(messages_url, headers, params)
        if not resp or 'data' not in resp:
            break

        for msg in resp['data']:
            total_messages += 1
            # Convert the message time (UTC) to local time
            utc_time = parser.isoparse(msg['createdAt'])  # e.g. "2022-01-01T00:00:00Z"
            local_time = utc_time.astimezone(pytz.timezone("Etc/GMT-4"))
            # Compare with arrival_date
            if arrival_date_local and local_time.date() <= arrival_date_local.date():
                pre_arrival_texts += 1
            else:
                post_arrival_texts += 1

        next_page = resp.get('nextPageToken')
        if not next_page:
            break

    # PAGINATION for calls
    next_page = None
    while True:
        params = {
            "phoneNumberId": phone_number_id,
            "participants": [guest_phone],
            "maxResults": 50
        }
        if next_page:
            params['pageToken'] = next_page

        resp = rate_limited_request(calls_url, headers, params)
        if not resp or 'data' not in resp:
            break

        for call in resp['data']:
            total_calls += 1
            # Convert call time (UTC) to local time
            utc_time = parser.isoparse(call['createdAt'])  # e.g. "2022-01-01T00:00:00Z"
            local_time = utc_time.astimezone(pytz.timezone("Etc/GMT-4"))
            if arrival_date_local and local_time.date() <= arrival_date_local.date():
                pre_arrival_calls += 1
            else:
                post_arrival_calls += 1

        next_page = resp.get('nextPageToken')
        if not next_page:
            break

    return {
        "phoneNumberId": phone_number_id,
        "total_messages": total_messages,
        "total_calls": total_calls,
        "pre_arrival_texts": pre_arrival_texts,
        "post_arrival_texts": post_arrival_texts,
        "pre_arrival_calls": pre_arrival_calls,
        "post_arrival_calls": post_arrival_calls
    }

#########################################################
# 5) WRAPPER: RUN FOR ONE GUEST PHONE, ACROSS ALL NUMBER IDs
#    (One key, or multiple keys)
#########################################################
def fetch_guest_communication_for_key(
    api_key, guest_phone, arrival_date_str
):
    """
    For a single API key and single guest phone, fetch all phoneNumberIds,
    then gather calls/texts from each phoneNumberId.
    """
    phone_number_ids = get_all_phone_number_ids(api_key)

    # Parse the arrival date in local GMT-4 (or just naive local)
    # arrival_date_str is something like "3/27/2025"
    if arrival_date_str:
        arrival_date_local = datetime.strptime(arrival_date_str, "%m/%d/%Y")
        # Force it to GMT-4 if you like:
        arrival_date_local = pytz.timezone("Etc/GMT-4").localize(arrival_date_local)
    else:
        arrival_date_local = None

    # Accumulate total results
    final_counts = {
        "total_messages": 0,
        "total_calls": 0,
        "pre_arrival_texts": 0,
        "post_arrival_texts": 0,
        "pre_arrival_calls": 0,
        "post_arrival_calls": 0,
    }

    # For each phoneNumberId
    for pn_id in phone_number_ids:
        info = get_communication_info_for_guest(
            api_key, pn_id, guest_phone, arrival_date_local
        )
        final_counts["total_messages"]    += info["total_messages"]
        final_counts["total_calls"]       += info["total_calls"]
        final_counts["pre_arrival_texts"] += info["pre_arrival_texts"]
        final_counts["post_arrival_texts"]+= info["post_arrival_texts"]
        final_counts["pre_arrival_calls"] += info["pre_arrival_calls"]
        final_counts["post_arrival_calls"]+= info["post_arrival_calls"]

    return final_counts

#########################################################
# 6) RUN CONCURRENTLY FOR MULTIPLE API KEYS / GUEST PHONES
#########################################################
def fetch_communication_concurrently(owner_df):
    """
    Suppose owner_df has columns:
       - 'Phone Number'
       - 'Arrival Date Short' (like '3/27/2025')
    We will run each row in parallel across ALL API keys,
    combine the results, then store them.
    """
    results_list = []

    # We'll do a simple approach: For each row, run all 4 keys in series,
    # but each row in parallel. If you need to do each key in parallel too,
    # you can nest your concurrency carefully or chunk it differently.
    #
    # WARNING: The more concurrency you do, the higher risk of hitting 429.

    def process_one_row(row):
        phone = row['Phone Number']
        arrival = row['Arrival Date Short']
        if not phone or phone == 'No Data':
            return {
                "status": "Invalid Number",
                "total_messages": 0,
                "total_calls": 0,
                "pre_arrival_texts": 0,
                "post_arrival_texts": 0,
                "pre_arrival_calls": 0,
                "post_arrival_calls": 0
            }

        # Combine results across *all* your keys
        combined = {
            "status": "OK",
            "total_messages": 0,
            "total_calls": 0,
            "pre_arrival_texts": 0,
            "post_arrival_texts": 0,
            "pre_arrival_calls": 0,
            "post_arrival_calls": 0
        }

        for api_key in OPENPHONE_API_KEYS:
            partial = fetch_guest_communication_for_key(api_key, phone, arrival)
            combined["total_messages"] += partial["total_messages"]
            combined["total_calls"]    += partial["total_calls"]
            combined["pre_arrival_texts"]  += partial["pre_arrival_texts"]
            combined["post_arrival_texts"] += partial["post_arrival_texts"]
            combined["pre_arrival_calls"]  += partial["pre_arrival_calls"]
            combined["post_arrival_calls"] += partial["post_arrival_calls"]

        return combined

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_index = {}
        for idx, row in owner_df.iterrows():
            # Submit each row to the pool
            future = executor.submit(process_one_row, row)
            future_to_index[future] = idx

        # Collect results
        results = [None]*len(owner_df)
        for future in concurrent.futures.as_completed(future_to_index):
            idx = future_to_index[future]
            data = future.result()
            results[idx] = data

    # Attach results back to DataFrame or return them
    # For demonstration, just build a new DataFrame:
    out_df = owner_df.copy()
    out_df["Status"] = [r["status"] for r in results]
    out_df["Total Messages"] = [r["total_messages"] for r in results]
    out_df["Total Calls"] = [r["total_calls"] for r in results]
    out_df["Pre-Arrival Texts"] = [r["pre_arrival_texts"] for r in results]
    out_df["Post-Arrival Texts"] = [r["post_arrival_texts"] for r in results]
    out_df["Pre-Arrival Calls"] = [r["pre_arrival_calls"] for r in results]
    out_df["Post-Arrival Calls"] = [r["post_arrival_calls"] for r in results]

    return out_df

#########################################################
# 7) USAGE EXAMPLE
#########################################################
def main():
    # EXAMPLE data
    data = {
        "Phone Number": ["+1234567890", "+1987654321", "No Data"],
        "Arrival Date Short": ["3/27/2025", "4/01/2025", ""]
    }
    df = pd.DataFrame(data)

    st.write("Starting concurrent fetch...")
    final_df = fetch_communication_concurrently(df)
    st.write("Done!")
    st.dataframe(final_df)

# if __name__ == "__main__":
#     main()
