import streamlit as st
import pandas as pd
import time
import requests
import concurrent.futures
import queue
from datetime import datetime
import pytz
from dateutil import parser

##############################################################################
# 1) YOUR FIVE OPENPHONE API KEYS, in a queue for exclusive use per row
##############################################################################
OPENPHONE_API_KEYS = [
    "j4sjHuvWO94IZWurOUca6aebhl6lG6Z7",  # original
    "aU3PhsAQ2Qw0E3WvJcCf4wul8u7QW0u5",
    "prXONwAEznwZzzTVFSVxym9ykQBiLcpF",
    "v5i6aToq7CbSy8oBodmdHz1i1ByUFNdc",
    "tJKJxdTdXrtelTqnDLhKwak3JGJAvHKp"
]

available_keys = queue.Queue()
for k in OPENPHONE_API_KEYS:
    available_keys.put(k)

##############################################################################
# 2) RATE-LIMITED REQUEST
#    - Sleep 0.2s => ~5 requests/sec per thread
##############################################################################
def rate_limited_request(url, headers, params, request_type='get'):
    # Simple rate-limit to ~5 requests/sec per thread
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

##############################################################################
# 3) GET CALL/MSG INFO FOR ONE phoneNumberId
##############################################################################
def get_communication_info(api_key, phone_number_id, guest_phone, arrival_date_str):
    """
    Fetch calls & messages for one phoneNumberId, for guest_phone,
    counting pre vs post arrival_date_str (like '3/27/2025').
    """
    local_tz = pytz.timezone("Etc/GMT-4")  # or "America/New_York" if DST is needed

    if arrival_date_str:
        arrival_dt = datetime.strptime(arrival_date_str, "%m/%d/%Y")
        arrival_dt_local = local_tz.localize(arrival_dt)
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

##############################################################################
# 4) FETCH ALL phoneNumberIds FOR ONE KEY, THEN CALLS + MESSAGES FOR GUEST
##############################################################################
def fetch_communication_for_guest_and_key(api_key, guest_phone, arrival_date_str):
    """
    1) Get all phoneNumberIds for api_key
    2) For each phoneNumberId, gather calls+msgs for guest_phone
    3) Sum them up
    """
    # fetch phoneNumberIds
    headers = {"Authorization": f"Bearer {api_key}"}
    url = "https://api.openphone.com/v1/phone-numbers"
    data = rate_limited_request(url, headers, params={})
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

##############################################################################
# 5) PROCESS A SINGLE ROW: GRAB A KEY FROM THE QUEUE, DO THE FETCH, RETURN KEY
##############################################################################
def process_one_row(idx, row):
    """
    Expects columns:
      'Phone Number', 'Arrival Date Short'
    """
    phone = row.get("Phone Number", "")
    arrival = row.get("Arrival Date Short", "")

    st.write(f"[Row {idx}] Starting: phone={phone}, arrival={arrival}")

    if not phone or phone == "No Data":
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
    st.write(f"[Row {idx}]  -> Using API key: {api_key[:6]}...")

    # gather data
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
        # Always put the key back so another row can use it
        available_keys.put(api_key)

    st.write(
        f"[Row {idx}] Finished => "
        f"{combined['total_messages']} msgs, {combined['total_calls']} calls"
    )
    return combined

##############################################################################
# 6) MAIN FUNCTION: RUN ROWS IN PARALLEL, ONE KEY PER ROW
##############################################################################
def fetch_communication_info_unique_keys(owner_df):
    """
    Requires columns: "Phone Number" and "Arrival Date Short"
    """
    # Verify columns exist
    required_cols = {"Phone Number", "Arrival Date Short"}
    if not required_cols.issubset(set(owner_df.columns)):
        st.error(f"Missing required columns. Your file must contain: {required_cols}")
        st.stop()

    results = [None]*len(owner_df)

    def row_worker(idx, row):
        return (idx, process_one_row(idx, row))

    # up to 5 concurrent rows => each row uses a different key
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

##############################################################################
# 7) STREAMLIT APP: UPLOAD EXCEL, RUN THE FUNCTION
##############################################################################
def main():
    st.title("OpenPhone Concurrency: One Key Per Row (Fixed Columns)")

    uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx", "xls"])

    if uploaded_file is not None:
        # Read Excel into DataFrame
        df = pd.read_excel(uploaded_file)
        st.write("Uploaded DataFrame columns:", df.columns.tolist())
        st.write(df.head())

        # Quick check or rename if your sheet has slightly different names
        # e.g., if your columns are "phone" and "arrival_date", do:
        # df.rename(columns={"phone": "Phone Number", "arrival_date": "Arrival Date Short"}, inplace=True)

        st.write("Starting concurrency. Each row uses a unique API key from the pool...")
        final_df = fetch_communication_info_unique_keys(df)

        st.write("All done! Here are the results:")
        st.dataframe(final_df)
    else:
        st.write("Please upload an Excel file with columns: 'Phone Number' and 'Arrival Date Short'.")

if __name__ == "__main__":
    main()
