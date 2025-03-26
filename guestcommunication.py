# guestcommunication.py
# Final code: logs are queued in worker threads, displayed afterward in the main thread.

import re
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
# 0) GLOBAL LOG QUEUE
##########################################################################
log_queue = queue.Queue()

def log(message):
    """
    Instead of st.write, we store messages in log_queue.
    We'll display them later in the main thread.
    """
    log_queue.put(message)

##########################################################################
# 1) YOUR FIVE OPENPHONE API KEYS
##########################################################################
OPENPHONE_API_KEYS = [
    "j4sjHuvWO94IZWurOUca6aebhl6lG6Z7",
    "aU3PhsAQ2Qw0E3WvJcCf4wul8u7QW0u5",
    "prXONwAEznwZzzTVFSVxym9ykQBiLcpF",
    "v5i6aToq7CbSy8oBodmdHz1i1ByUFNdc",
    "tJKJxdTdXrtelTqnDLhKwak3JGJAvHKp"
]

# Put them into a queue for concurrency
import queue
available_keys = queue.Queue()
for k in OPENPHONE_API_KEYS:
    available_keys.put(k)

##########################################################################
# 2) RATE-LIMITED REQUEST (~5 requests/sec)
##########################################################################
def rate_limited_request(url, headers, params, request_type='get'):
    """
    Makes an OpenPhone API request, sleeping ~0.2s => ~5 requests/sec (per thread).
    No st.write calls here, we log to the queue if needed.
    """
    time.sleep(0.2)
    try:
        if request_type.lower() == 'get':
            log(f"Making GET request to: {url} with {params}")
            resp = requests.get(url, headers=headers, params=params)
        else:
            log(f"Making {request_type.upper()} request to: {url} with {params}")
            resp = requests.request(request_type.upper(), url, headers=headers, params=params)

        if resp and resp.status_code == 200:
            return resp.json()
        else:
            log(f"API Error: {resp.status_code} => {resp.text}")
    except Exception as e:
        log(f"Request exception: {str(e)}")

    return None

##########################################################################
# 3) GET COMM INFO (CALLS & MESSAGES) FOR ONE phoneNumberId
##########################################################################
def get_communication_info(api_key, phone_number_id, guest_phone, arrival_date_str):
    local_tz = pytz.timezone("Etc/GMT-4")  # or "America/New_York"

    if arrival_date_str:
        try:
            arrival_dt = datetime.strptime(arrival_date_str, "%m/%d/%Y")
            arrival_dt_local = local_tz.localize(arrival_dt)
        except ValueError:
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

##########################################################################
# 4) FETCH phoneNumberIds FOR ONE KEY, THEN CALLS+MESSAGES FOR GUEST
##########################################################################
def fetch_communication_for_guest_and_key(api_key, guest_phone, arrival_date_str):
    headers = {"Authorization": f"Bearer {api_key}"}
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    log(f"Fetching phone numbers for key {api_key[:6]} ...")
    data = rate_limited_request(phone_numbers_url, headers, params={})

    phone_number_ids = []
    if data and "data" in data:
        phone_number_ids = [pn.get("id") for pn in data["data"]]

    log(f"Found {len(phone_number_ids)} phoneNumberIds for key {api_key[:6]}. Fetching messages/calls...")

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
# 5) PROCESS ONE ROW (No st.write inside the thread!)
##########################################################################
def process_one_row(idx, row):
    phone_raw = row.get("Phone Number", "")
    phone = str(phone_raw).strip()

    arrival_raw = row.get("Arrival Date Short", "")
    arrival = str(arrival_raw).strip()

    log(f"[Row {idx}] Starting => phone='{phone}', arrival='{arrival}'")

    if not phone or phone.lower() == "no data":
        log(f"[Row {idx}] -> Invalid phone => skipping.")
        return {
            "status": "Invalid Number",
            "total_messages": 0,
            "total_calls": 0,
            "pre_arrival_texts": 0,
            "post_arrival_texts": 0,
            "pre_arrival_calls": 0,
            "post_arrival_calls": 0
        }

    # Unique key
    api_key = available_keys.get()
    log(f"[Row {idx}] -> Using API key: {api_key[:6]}...")

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
        # Put the key back
        available_keys.put(api_key)

    log(f"[Row {idx}] Finished => {combined['total_messages']} msgs, {combined['total_calls']} calls")
    return combined

##########################################################################
# 6) FETCH COMM INFO (CONCURRENCY). We store logs in a queue.
##########################################################################
def fetch_communication_info_unique_keys(owner_df):
    """
    Each row is processed in parallel, but no st.write calls in threads.
    We'll display logs after concurrency.
    """
    results = [None]*len(owner_df)

    def row_worker(idx, row):
        return (idx, process_one_row(idx, row))

    with st.spinner("Fetching data from OpenPhone..."):
        max_workers = 5
        futures = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for i, row in owner_df.iterrows():
                fut = executor.submit(row_worker, i, row)
                futures.append(fut)

        # Collect results
        for fut in concurrent.futures.as_completed(futures):
            idx, row_result = fut.result()
            results[idx] = row_result

    # Build final DataFrame
    out_df = owner_df.copy()
    out_df["Status"] = [r["status"] for r in results]
    out_df["Total Messages"] = [r["total_messages"] for r in results]
    out_df["Total Calls"] = [r["total_calls"] for r in results]
    out_df["Pre-Arrival Texts"] = [r["pre_arrival_texts"] for r in results]
    out_df["Post-Arrival Texts"] = [r["post_arrival_texts"] for r in results]
    out_df["Pre-Arrival Calls"] = [r["pre_arrival_calls"] for r in results]
    out_df["Post-Arrival Calls"] = [r["post_arrival_calls"] for r in results]

    # Now show logs from the queue in the main thread
    st.write("**Logs:**")
    while not log_queue.empty():
        message = log_queue.get()
        st.write(message)

    return out_df

##########################################################################
# 7) OPTIONAL run_guest_status_tab() - Logs shown after concurrency
##########################################################################
def run_guest_status_tab():
    st.title("Add Guest OpenPhone Status (Multi-Key Concurrency) - No st.write in threads")

    uploaded_file = st.file_uploader(
        "Upload Excel/CSV with 'Phone Number' & 'Arrival Date Short'",
        type=["xlsx","xls","csv"]
    )
    if not uploaded_file:
        st.info("Please upload a file to proceed.")
        return

    # Read the file
    if uploaded_file.name.lower().endswith((".xlsx", ".xls")):
        owner_df = pd.read_excel(uploaded_file)
    else:
        owner_df = pd.read_csv(uploaded_file)

    required_cols = {"Phone Number", "Arrival Date Short"}
    if not required_cols.issubset(owner_df.columns):
        st.error(f"Missing required columns. Must include: {required_cols}")
        return

    st.write("Data Preview:", owner_df.head())

    final_df = fetch_communication_info_unique_keys(owner_df)
    st.success("Done! Here are your results:")
    st.dataframe(final_df)

    # Optionally let user download
    csv_data = final_df.to_csv(index=False)
    st.download_button("Download CSV", data=csv_data, file_name="openphone_results.csv", mime="text/csv")

##########################################################################
# 8) DEMO USAGE
##########################################################################
def main():
    st.title("Concurrent Rows (5 Keys) - No st.write in Worker Threads")
    sample_data = {
        "Phone Number": ["+1234567890", "+1987654321", "No Data"],
        "Arrival Date Short": ["3/27/2025", "3/28/2025", ""]
    }
    df = pd.DataFrame(sample_data)
    st.write("Sample data:", df)

    final_df = fetch_communication_info_unique_keys(df)
    st.write("All done with sample data!")
    st.dataframe(final_df)

# If you want to run this directly:
#   streamlit run guestcommunication.py
# if __name__ == "__main__":
#     main()
