import streamlit as st
import pandas as pd
import phonenumbers
import requests
import time
import io
import queue
import concurrent.futures
from datetime import datetime

########################################
# 1) YOUR OPENPHONE API KEYS (NO 'Bearer')
########################################
OPENPHONE_API_KEYS = [
    "NRFVc43Gee39yIBu6mfC6Ya34K5moaSL",
    "s270j8VAfL9mqRCr7y8PwIoDnoADfFlO",
    "vP92GK3ZjiHi1aRVR29QKzilRsu0xnMI",
    "1mCfUABVby1FmX8LSiAk6UHOPWGEApRQ"
]

# A queue of keys so each row uses exactly 1 distinct key at a time
available_keys = queue.Queue()
for k in OPENPHONE_API_KEYS:
    available_keys.put(k)

########################################
# 2) FORMAT PHONE => E.164 (US)
########################################
def format_phone_number_us(raw_number: str) -> str:
    s = raw_number.strip()
    if not s:
        return None
    try:
        pn = phonenumbers.parse(s, "US")
        if phonenumbers.is_valid_number(pn):
            return phonenumbers.format_number(pn, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return None

########################################
# 3) RATE-LIMITED GET (~5 req/sec)
########################################
def rate_limited_get(url, headers, params):
    """
    Sleep 0.2s => ~5 requests/sec per thread. 
    If 3 workers run, watch out for total concurrency. 
    """
    time.sleep(0.2)
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            return resp.json()
        else:
            return None
    except Exception:
        return None

########################################
# 4) GET CALLS & MESSAGES FOR ONE KEY
########################################
def get_communication_info(e164_phone, chosen_key, arrival_date=None):
    """
    1) Use the single chosen_key for phoneNumberIds
    2) Then fetch calls/messages 
    3) Return stats
    """
    headers = {"Authorization": chosen_key, "Content-Type": "application/json"}

    # GET phoneNumberIds
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    data = rate_limited_get(phone_numbers_url, headers, params={})
    if not data or "data" not in data:
        return {
            'status': "No Communications",
            'last_date': None,
            'call_duration': None,
            'agent_name': None,
            'total_messages': 0,
            'total_calls': 0,
            'answered_calls': 0,
            'missed_calls': 0,
            'call_attempts': 0,
            'pre_arrival_calls': 0,
            'pre_arrival_texts': 0,
            'post_arrival_calls': 0,
            'post_arrival_texts': 0,
            'calls_under_40sec': 0
        }
    phone_number_ids = [pn.get("id") for pn in data["data"] if pn.get("id")]
    if not phone_number_ids:
        return {
            'status': "No Communications",
            'last_date': None,
            'call_duration': None,
            'agent_name': None,
            'total_messages': 0,
            'total_calls': 0,
            'answered_calls': 0,
            'missed_calls': 0,
            'call_attempts': 0,
            'pre_arrival_calls': 0,
            'pre_arrival_texts': 0,
            'post_arrival_calls': 0,
            'post_arrival_texts': 0,
            'calls_under_40sec': 0
        }

    if isinstance(arrival_date, str):
        try:
            arrival_date = datetime.fromisoformat(arrival_date)
        except ValueError:
            arrival_date = None
    elif isinstance(arrival_date, pd.Timestamp):
        arrival_date = arrival_date.to_pydatetime()
    arrival_date_only = arrival_date.date() if arrival_date else None

    msg_url  = "https://api.openphone.com/v1/messages"
    call_url = "https://api.openphone.com/v1/calls"

    latest_dt = None
    latest_type, latest_dir, call_dur = None, None, None
    agent_name = None

    total_msgs, total_calls = 0, 0
    ans_calls, mis_calls, attempts = 0, 0, 0
    pre_calls, pre_texts = 0, 0
    post_calls, post_texts = 0, 0
    calls_under_40 = 0

    for pn_id in phone_number_ids:
        # MESSAGES
        next_page = None
        while True:
            params = {
                "phoneNumberId": pn_id,
                "participants": [e164_phone],
                "maxResults": 50
            }
            if next_page:
                params["pageToken"] = next_page
            mdata = rate_limited_get(msg_url, headers, params)
            if not mdata or "data" not in mdata:
                break
            msgs = mdata["data"]
            total_msgs += len(msgs)
            for m in msgs:
                mtime = datetime.fromisoformat(m["createdAt"].replace("Z","+00:00"))
                if arrival_date_only:
                    if mtime.date() <= arrival_date_only:
                        pre_texts += 1
                    else:
                        post_texts += 1
                if not latest_dt or mtime > latest_dt:
                    latest_dt   = mtime
                    latest_type = "Message"
                    latest_dir  = m.get("direction","unknown")
                    agent_name  = m.get("user",{}).get("name","Unknown Agent")
            next_page = mdata.get("nextPageToken")
            if not next_page:
                break

        # CALLS
        next_page = None
        while True:
            params = {
                "phoneNumberId": pn_id,
                "participants": [e164_phone],
                "maxResults": 50
            }
            if next_page:
                params["pageToken"] = next_page
            cdata = rate_limited_get(call_url, headers, params)
            if not cdata or "data" not in cdata:
                break
            calls = cdata["data"]
            total_calls += len(calls)
            for c in calls:
                ctime = datetime.fromisoformat(c["createdAt"].replace("Z","+00:00"))
                dur   = c.get("duration",0)
                if arrival_date_only:
                    if ctime.date() <= arrival_date_only:
                        pre_calls += 1
                    else:
                        post_calls += 1
                if dur < 40:
                    calls_under_40 += 1

                if not latest_dt or ctime > latest_dt:
                    latest_dt   = ctime
                    latest_type = "Call"
                    latest_dir  = c.get("direction","unknown")
                    call_dur    = dur
                    agent_name  = c.get("user",{}).get("name","Unknown Agent")

                attempts += 1
                status = c.get("status","unknown")
                if status == "completed":
                    ans_calls += 1
                elif status in ["missed","no-answer","busy","failed"]:
                    mis_calls += 1
            next_page = cdata.get("nextPageToken")
            if not next_page:
                break

    if not latest_dt:
        status = "No Communications"
    else:
        status = f"{latest_type} - {latest_dir}"

    return {
        'status': status,
        'last_date': latest_dt.strftime("%Y-%m-%d %H:%M:%S") if latest_dt else None,
        'call_duration': call_dur,
        'agent_name': agent_name,
        'total_messages': total_msgs,
        'total_calls': total_calls,
        'answered_calls': ans_calls,
        'missed_calls': mis_calls,
        'call_attempts': attempts,
        'pre_arrival_calls': pre_calls,
        'pre_arrival_texts': pre_texts,
        'post_arrival_calls': post_calls,
        'post_arrival_texts': post_texts,
        'calls_under_40sec': calls_under_40
    }

########################################
# 5) PROCESS ONE ROW => EXACTLY ONE KEY
########################################
def process_one_row(idx, row):
    import queue
    chosen_key = available_keys.get()  # blocks if no key
    try:
        raw_phone = str(row.get("Phone Number","")).strip()
        arrival_val= row.get("Arrival Date",None)
        e164_phone = format_phone_number_us(raw_phone)
        if not e164_phone:
            # invalid phone => skip
            return {
                "status":"Invalid Number",
                "last_date":None,
                "call_duration":None,
                "agent_name":"Unknown",
                "total_messages":0,
                "total_calls":0,
                "answered_calls":0,
                "missed_calls":0,
                "call_attempts":0,
                "pre_arrival_calls":0,
                "pre_arrival_texts":0,
                "post_arrival_calls":0,
                "post_arrival_texts":0,
                "calls_under_40sec":0
            }
        # else
        info = get_communication_info(e164_phone, chosen_key, arrival_val)
        return info
    finally:
        # put key back so another row can use it
        available_keys.put(chosen_key)

########################################
# 6) CONCURRENCY WITH 3 WORKERS
########################################
def fetch_communication_info_unique_keys(df):
    """
    Each row => pick EXACTLY 1 key from the queue. 
    We run up to 3 rows in parallel (3 workers).
    """
    results = [None]*len(df)

    def row_worker(i, r):
        return (i, process_one_row(i, r))

    max_workers = 3  # <--- Here is the limit to 3 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as exe:
        fut_map = {}
        for i, row in df.iterrows():
            fut = exe.submit(row_worker, i, row)
            fut_map[fut] = i

        for fut in concurrent.futures.as_completed(fut_map):
            i, res = fut.result()
            results[i] = res

    # build columns
    out_df = df.copy()
    out_df["Status"] = [r["status"] for r in results]
    out_df["Last Contact Date"] = [r["last_date"] for r in results]
    out_df["Last Call Duration"] = [r["call_duration"] for r in results]
    out_df["Last Agent Name"]    = [r["agent_name"] for r in results]
    out_df["Total Messages"]     = [r["total_messages"] for r in results]
    out_df["Total Calls"]        = [r["total_calls"] for r in results]
    out_df["Answered Calls"]     = [r["answered_calls"] for r in results]
    out_df["Missed Calls"]       = [r["missed_calls"] for r in results]
    out_df["Call Attempts"]      = [r["call_attempts"] for r in results]
    out_df["Pre-Arrival Calls"]  = [r["pre_arrival_calls"] for r in results]
    out_df["Pre-Arrival Texts"]  = [r["pre_arrival_texts"] for r in results]
    out_df["Post-Arrival Calls"] = [r["post_arrival_calls"] for r in results]
    out_df["Post-Arrival Texts"] = [r["post_arrival_texts"] for r in results]
    out_df["Calls <40s"]         = [r["calls_under_40sec"] for r in results]

    return out_df

########################################
# 7) STREAMLIT UI
########################################
def run_guest_status_tab():
    st.title("Concurrent: 3 workers, each row => distinct key, skip invalid phone")
    uploaded_file = st.file_uploader("Upload Excel/CSV with 'Phone Number'", type=["xlsx","xls","csv"])
    if not uploaded_file:
        st.info("Awaiting file.")
        return

    if uploaded_file.name.lower().endswith(("xlsx","xls")):
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.read_csv(uploaded_file)

    if "Phone Number" not in df.columns:
        st.error("Missing 'Phone Number' column.")
        return

    st.write("Data preview:", df.head())

    final_df = fetch_communication_info_unique_keys(df)
    st.success("All done! 3 concurrency, 1 key per row at a time.")
    st.dataframe(final_df.head(50))

    # Download
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        final_df.to_excel(writer, index=False, sheet_name="Updated")
    buf.seek(0)

    st.download_button(
        "Download Updated Excel",
        data=buf.getvalue(),
        file_name="updated_unique_keys_3workers.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# if run directly:
#   streamlit run your_file.py
if __name__ == "__main__":
    run_guest_status_tab()
