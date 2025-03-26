import streamlit as st
import pandas as pd
import phonenumbers
import requests
import time
import io
import concurrent.futures
from datetime import datetime
from queue import Queue

########################################
# 0) GLOBAL LOG QUEUE
########################################
log_queue = Queue()

def log(message):
    """
    Worker threads will call this instead of st.write.
    We'll display messages after concurrency finishes.
    """
    log_queue.put(message)

########################################
# 1) FOUR API KEYS (NO 'Bearer')
########################################
OPENPHONE_API_KEYS = [
    "NRFVc43Gee39yIBu6mfC6Ya34K5moaSL",
    "s270j8VAfL9mqRCr7y8PwIoDnoADfFlO",
    "vP92GK3ZjiHi1aRVR29QKzilRsu0xnMI",
    "1mCfUABVby1FmX8LSiAk6UHOPWGEApRQ"
]

########################################
# 2) FORMAT PHONE => E.164
########################################
def format_phone_number_us(raw_number: str) -> str:
    s = raw_number.strip()
    if not s:
        return None
    try:
        parsed = phonenumbers.parse(s, "US")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return None

########################################
# 3) RATE-LIMITED GET REQUEST (~5 RPS)
########################################
def rate_limited_get(url, headers, params, max_retries=3):
    time.sleep(0.2)  # ~5 requests/sec
    backoff_delay = 1
    retries = 0
    while retries < max_retries:
        try:
            resp = requests.get(url, headers=headers, params=params)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                log("429 Too Many Requests => backing off {}s".format(backoff_delay))
                time.sleep(backoff_delay)
                backoff_delay *= 2
                retries += 1
                continue
            else:
                log(f"API Error {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            log(f"Request exception: {e}")
            return None
    return None

########################################
# 4) TRY KEYS => GET phoneNumberIds
########################################
def try_get_phone_number_ids():
    """
    Loops over the 4 keys. 
    If success => (ids, key). If all fail => ([], None).
    """
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    for key in OPENPHONE_API_KEYS:
        log(f"Trying key={key[:6]} => GET /phone-numbers")
        headers = {"Authorization": key, "Content-Type": "application/json"}
        data = rate_limited_get(phone_numbers_url, headers, params={})
        if data and "data" in data:
            pn_ids = [d.get("id") for d in data["data"] if d.get("id")]
            if pn_ids:
                log(f"Success with key={key[:6]} => Found {len(pn_ids)} phoneNumberIds.")
                return (pn_ids, key)
            else:
                log(f"Key={key[:6]} => 200 but no phoneNumberIds.")
        else:
            log(f"Key={key[:6]} => unauthorized or error.")
    return ([], None)

########################################
# 5) GET CALLS & MESSAGES
########################################
def get_communication_info(e164_phone, arrival_date=None):
    phone_number_ids, chosen_key = try_get_phone_number_ids()
    if not chosen_key or not phone_number_ids:
        log(f"No valid key => {e164_phone} => All keys unauthorized.")
        return {
            'status': "No Communications (All Keys Unauthorized)",
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

    headers = {"Authorization": chosen_key, "Content-Type": "application/json"}
    msg_url  = "https://api.openphone.com/v1/messages"
    call_url = "https://api.openphone.com/v1/calls"

    latest_dt       = None
    latest_type     = None
    latest_dir      = None
    call_dur        = None
    agent_name      = None

    total_msgs      = 0
    total_calls     = 0
    ans_calls       = 0
    mis_calls       = 0
    attempts        = 0

    pre_calls       = 0
    pre_texts       = 0
    post_calls      = 0
    post_texts      = 0
    calls_under_40  = 0

    for pn_id in phone_number_ids:
        log(f"[{e164_phone}] => phoneNumberId={pn_id}")

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
            data = rate_limited_get(msg_url, headers, params)
            if not data or "data" not in data:
                break
            msgs = data["data"]
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
            next_page = data.get("nextPageToken")
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
            data = rate_limited_get(call_url, headers, params)
            if not data or "data" not in data:
                break
            calls = data["data"]
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
            next_page = data.get("nextPageToken")
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
# 6) process_one_row: concurrency worker
########################################
def process_one_row(i, row):
    raw_phone = str(row.get("Phone Number","")).strip()
    arrival_val= row.get("Arrival Date", None)
    e164_phone = format_phone_number_us(raw_phone)

    if not e164_phone:
        log(f"[Row {i}] => invalid phone '{raw_phone}' => skipping.")
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

    log(f"[Row {i}] => phone={e164_phone}, arrival={arrival_val}")
    result = get_communication_info(e164_phone, arrival_val)
    log(f"[Row {i}] => {result['status']}, {result['total_calls']} calls, {result['total_messages']} msgs.")
    return result

########################################
# 7) concurrency
########################################
def fetch_communication_info_concurrent(df):
    import concurrent.futures
    results = [None]*len(df)

    def row_worker(i, r):
        return (i, process_one_row(i, r))

    max_workers=5
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as exe:
        future_list = []
        for i, row in df.iterrows():
            fut = exe.submit(row_worker, i, row)
            future_list.append(fut)

        for fut in concurrent.futures.as_completed(future_list):
            i, res = fut.result()
            results[i] = res

    # build columns
    statuses, dates, durations, agent_names = [], [], [], []
    total_msgs_list, total_calls_list = [], []
    ans_calls_list, mis_calls_list, attempts_list = [], [], []
    pre_calls_list, pre_texts_list = [], []
    post_calls_list, post_texts_list= [], []
    calls_u40_list = []

    for r in results:
        statuses.append(r["status"])
        dates.append(r["last_date"])
        durations.append(r["call_duration"])
        agent_names.append(r["agent_name"])
        total_msgs_list.append(r["total_messages"])
        total_calls_list.append(r["total_calls"])
        ans_calls_list.append(r["answered_calls"])
        mis_calls_list.append(r["missed_calls"])
        attempts_list.append(r["call_attempts"])
        pre_calls_list.append(r["pre_arrival_calls"])
        pre_texts_list.append(r["pre_arrival_texts"])
        post_calls_list.append(r["post_arrival_calls"])
        post_texts_list.append(r["post_arrival_texts"])
        calls_u40_list.append(r["calls_under_40sec"])

    out_df = df.copy()
    out_df["Status"] = statuses
    out_df["Last Contact Date"] = dates
    out_df["Last Call Duration"] = durations
    out_df["Last Agent Name"] = agent_names
    out_df["Total Messages"] = total_msgs_list
    out_df["Total Calls"] = total_calls_list
    out_df["Answered Calls"] = ans_calls_list
    out_df["Missed Calls"] = mis_calls_list
    out_df["Call Attempts"] = attempts_list
    out_df["Pre-Arrival Calls"] = pre_calls_list
    out_df["Pre-Arrival Texts"] = pre_texts_list
    out_df["Post-Arrival Calls"] = post_calls_list
    out_df["Post-Arrival Texts"] = post_texts_list
    out_df["Calls <40s"] = calls_u40_list

    return out_df

########################################
# 8) MAIN STREAMLIT
########################################
def run_guest_status_tab():
    st.title("Concurrent (5 threads), 4 Keys, E.164, plus logs in queue")
    file = st.file_uploader("Upload Excel/CSV with 'Phone Number'", type=["xlsx","xls","csv"])
    if not file:
        st.info("Please upload a file.")
        return

    if file.name.lower().endswith(("xlsx","xls")):
        df = pd.read_excel(file)
    else:
        df = pd.read_csv(file)

    if "Phone Number" not in df.columns:
        st.error("No 'Phone Number' column.")
        return

    st.write("Data Preview:", df.head())

    with st.spinner("Processing in concurrency..."):
        final_df = fetch_communication_info_concurrent(df)

    st.success("All done!")
    st.dataframe(final_df.head(50))

    # Show logs from the queue
    st.write("### Logs:")
    while not log_queue.empty():
        msg = log_queue.get()
        st.write(msg)

    # Optionally allow downloading final
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        final_df.to_excel(writer, index=False, sheet_name="Updated")
    buf.seek(0)

    st.download_button(
        "Download Updated Excel",
        data=buf.getvalue(),
        file_name="openphone_concurrent_logs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# If run directly:
# streamlit run your_file.py
if __name__ == "__main__":
    run_guest_status_tab()
