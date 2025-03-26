# guestcommunication.py (Final code without any 'State' references)

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
# 1) YOUR FIVE OPENPHONE API KEYS
##########################################################################
OPENPHONE_API_KEYS = [
    "j4sjHuvWO94IZWurOUca6aebhl6lG6Z7",
    "aU3PhsAQ2Qw0E3WvJcCf4wul8u7QW0u5",
    "prXONwAEznwZzzTVFSVxym9ykQBiLcpF",
    "v5i6aToq7CbSy8oBodmdHz1i1ByUFNdc",
    "tJKJxdTdXrtelTqnDLhKwak3JGJAvHKp"
]

# Put them into a queue for concurrency (each row gets its own key up to 5 threads)
available_keys = queue.Queue()
for k in OPENPHONE_API_KEYS:
    available_keys.put(k)

##########################################################################
# 2) RATE-LIMITED REQUEST (~5 requests/sec)
##########################################################################
def rate_limited_request(url, headers, params, request_type='get'):
    """
    Makes an OpenPhone API request, sleeping ~0.2s => ~5 requests/sec (per thread).
    If your rate limit allows more, you can reduce or remove the sleep.
    """
    time.sleep(0.2)
    try:
        if request_type.lower() == 'get':
            st.write(f"Making GET request to: {url} with {params}")
            resp = requests.get(url, headers=headers, params=params)
        else:
            st.write(f"Making {request_type.upper()} request to: {url} with {params}")
            resp = requests.request(request_type.upper(), url, headers=headers, params=params)

        if resp and resp.status_code == 200:
            return resp.json()
        else:
            st.warning(f"API Error: {resp.status_code} => {resp.text}")
    except Exception as e:
        st.warning(f"Request exception: {str(e)}")

    return None

##########################################################################
# 3) GET COMM INFO (CALLS & MESSAGES) FOR ONE phoneNumberId
##########################################################################
def get_communication_info(api_key, phone_number_id, guest_phone, arrival_date_str):
    """
    Fetch calls & messages for ONE phoneNumberId + guest_phone,
    counting pre vs. post arrival_date_str if valid (e.g., '3/27/2025').
    No references to 'State'.
    """
    local_tz = pytz.timezone("Etc/GMT-4")  # or "America/New_York" if DST is needed

    # Attempt to parse arrival_date_str like '3/27/2025'
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

    # Counters
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
            utc_time = parser.isoparse(msg["createdAt"])
            local_time = utc_time.astimezone(local_tz)
            if arrival_dt_local:
                # Compare local date to arrival date
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

    # Return a dict with all relevant counts
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
    """
    1) Get all phoneNumberIds for api_key.
    2) For each phoneNumberId, gather calls+msgs for guest_phone.
    3) Sum up the results (no 'State').
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    st.write(f"Fetching phone numbers for key {api_key[:6]} ...")
    data = rate_limited_request(phone_numbers_url, headers, params={})

    phone_number_ids = []
    if data and "data" in data:
        phone_number_ids = [pn.get("id") for pn in data["data"]]

    st.write(f"Found {len(phone_number_ids)} phoneNumberIds for key {api_key[:6]}. Fetching messages/calls...")

    # Summaries
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
# 5) PROCESS ONE ROW: Grab a key, do the fetch, return key
##########################################################################
def process_one_row(idx, row):
    """
    Convert phone to string, parse arrival date, no 'State' references.
    """
    # Ensure phone is string
    phone_raw = row.get("Phone Number", "")
    phone = str(phone_raw)

    arrival_raw = row.get("Arrival Date Short", "")
    arrival = str(arrival_raw).strip()

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

    # Grab a unique key from the queue
    api_key = available_keys.get()
    st.write(f"[Row {idx}]  -> Using API key: {api_key[:6]}...")

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
        # Put the key back so another row can reuse it
        available_keys.put(api_key)

    st.write(
        f"[Row {idx}] Finished => {combined['total_messages']} msgs, {combined['total_calls']} calls"
    )
    return combined

##########################################################################
# 6) FETCH COMM INFO (CONCURRENCY) - No "State"
##########################################################################
def fetch_communication_info_unique_keys(owner_df):
    """
    Each row is processed in parallel, each row uses a unique key from the queue.
    We'll log row-by-row progress and never reference 'State'.
    Returns a DataFrame with total/pre/post calls/messages.
    """

    results = [None] * len(owner_df)

    def row_worker(idx, row):
        return (idx, process_one_row(idx, row))

    max_workers = 5
    st.write(f"Processing {len(owner_df)} rows with concurrency (max_workers={max_workers})...")

    with st.spinner("Fetching data from OpenPhone..."):
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {}
            for i, row in owner_df.iterrows():
                fut = executor.submit(row_worker, i, row)
                future_to_idx[fut] = i

            for fut in concurrent.futures.as_completed(future_to_idx):
                idx, result_dict = fut.result()
                results[idx] = result_dict

    # Build final DataFrame
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
# 7) OPTIONAL TAB: run_guest_status_tab (No "State")
##########################################################################
def run_guest_status_tab():
    """
    If called from your main app, it shows a UI for uploading a file 
    that must have 'Phone Number' & 'Arrival Date Short'. 
    We'll do concurrency with no reference to 'State'.
    """
    st.title("Add Guest OpenPhone Status (Multi-Key Concurrency)")

    uploaded_file = st.file_uploader(
        "Upload Excel/CSV with 'Phone Number' & 'Arrival Date Short'",
        type=["xlsx", "xls", "csv"]
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

    # Do concurrency
    final_df = fetch_communication_info_unique_keys(owner_df)
    st.success("Done! Here are your results:")
    st.dataframe(final_df)

    # Optionally let user download
    csv_data = final_df.to_csv(index=False)
    st.download_button("Download CSV", data=csv_data, file_name="openphone_results.csv", mime="text/csv")

##########################################################################
# 8) DEMO USAGE - No references to 'State'
##########################################################################
def main():
    """
    If you run 'streamlit run guestcommunication.py' directly,
    it shows a sample DataFrame (no 'State' column), concurrency logs, and final results.
    """
    st.title("Concurrent Rows Demo (5 Keys) - No 'State'")
    sample_data = {
        "Phone Number": [
            "+1234567890",
            "+1987654321",
            "No Data",
            "+14443339999",
            "+13081112222"
        ],
        "Arrival Date Short": [
            "3/27/2025",
            "3/28/2025",
            "",
            "4/01/2025",
            "5/02/2025"
        ]
    }
    df = pd.DataFrame(sample_data)
    st.write("Sample Demo data (no 'State' column):", df)

    final_df = fetch_communication_info_unique_keys(df)
    st.write("All done with sample data!")
    st.dataframe(final_df)

# Uncomment if you want to run directly:
#   streamlit run guestcommunication.py
# if __name__ == "__main__":
#     main()

