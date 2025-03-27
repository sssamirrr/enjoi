import streamlit as st
import pandas as pd
import phonenumbers
import requests
import time
import io
import queue
import concurrent.futures
from datetime import datetime
import pyarrow as pa

########################################
# 0) GLOBALS
########################################
log_queue = queue.Queue()

def log(msg):
    """
    Worker threads call this to store log messages.
    We'll display them after concurrency finishes.
    """
    log_queue.put(msg)

########################################
# 1) HARD-CODED OPENPHONE API KEYS
########################################
OPENPHONE_API_KEYS = [
    "NRFVc43Gee39yIBu6mfC6Ya34K5moaSL",
    "s270j8VAfL9mqRCr7y8PwIoDnoADfFlO",
    "vP92GK3ZjiHi1aRVR29QKzilRsu0xnMI",
    "1mCfUABVby1FmX8LSiAk6UHOPWGEApRQ"
]

# phone_number_details: {key -> { phoneNumberId -> { "fallbackAgentName": ..., "users":[...] } } }
key_to_phone_number_details = {}

# user_id_to_name: {key -> { "xyz" -> "FirstName LastName", ... }}
key_to_user_map = {}

# A queue of keys for concurrency
available_keys = queue.Queue()
for k in OPENPHONE_API_KEYS:
    available_keys.put(k)

########################################
# 2) E.164 HELPER
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
# 3) RATE-LIMITED GET (5 RPS per thread)
########################################
def rate_limited_get(url, headers, params=None):
    time.sleep(0.2)  # ~5 requests/second
    try:
        r = requests.get(url, headers=headers, params=params or {})
        if r.status_code == 200:
            return r.json()
        else:
            log(f"API Error {r.status_code}: {r.text}")
            return None
    except Exception as e:
        log(f"Request exception: {e}")
        return None

########################################
# 4A) FETCH phone-numbers => fallback user
########################################
def fetch_phone_numbers_for_key(key):
    headers = {"Authorization": key, "Content-Type": "application/json"}
    url = "https://api.openphone.com/v1/phone-numbers"
    data = rate_limited_get(url, headers)
    details_map = {}

    if data and "data" in data:
        for pn in data["data"]:
            pn_id = pn.get("id")
            if not pn_id:
                continue
            users_arr = pn.get("users", [])  # each user is {id, firstName, lastName, email, ...}
            fallback_pieces = []
            for u in users_arr:
                fn = (u.get("firstName") or "").strip()
                ln = (u.get("lastName") or "").strip()
                if fn or ln:
                    fallback_pieces.append(f"{fn} {ln}".strip())
                else:
                    fallback_pieces.append(u.get("email","UnknownUser"))
            fallback_str = ", ".join(x for x in fallback_pieces if x)
            if not fallback_str:
                fallback_str = "Unknown Agent"

            details_map[pn_id] = {
                "users": users_arr,
                "fallbackAgentName": fallback_str
            }
    else:
        log(f"phone-numbers => No data for key={key[:6]}")

    key_to_phone_number_details[key] = details_map

########################################
# 4B) FETCH /users => map userId -> "First Last"
########################################
def fetch_users_for_key(key):
    headers = {"Authorization": key, "Content-Type": "application/json"}
    url = "https://api.openphone.com/v1/users"
    data = rate_limited_get(url, headers)

    user_map = {}
    if data and "data" in data:
        for user in data["data"]:
            uid = user.get("id")
            if not uid:
                continue
            fn = (user.get("firstName") or "").strip()
            ln = (user.get("lastName") or "").strip()
            if fn or ln:
                full_name = f"{fn} {ln}".strip()
            else:
                full_name = user.get("email","UnknownUser")
            user_map[uid] = full_name
    else:
        log(f"users => No data for key={key[:6]}")

    key_to_user_map[key] = user_map

########################################
# 4C) Initialize all keys once
########################################
def initialize_all_keys():
    for key in OPENPHONE_API_KEYS:
        log(f"Fetching phone numbers and users for key={key[:6]} ...")
        fetch_phone_numbers_for_key(key)
        fetch_users_for_key(key)
        details_count = len(key_to_phone_number_details.get(key, {}))
        user_count = len(key_to_user_map.get(key, {}))
        log(f"  -> key={key[:6]} => {details_count} phoneNumbers, {user_count} users")

########################################
# 5) FETCH calls/messages
########################################
def get_communication_info(e164_phone, chosen_key, arrival_date=None):
    details_map = key_to_phone_number_details.get(chosen_key, {})
    phone_number_ids = list(details_map.keys())
    user_map = key_to_user_map.get(chosen_key, {})

    if not phone_number_ids:
        return blank_info_dict("No Communications")

    arr_dt = None
    if isinstance(arrival_date, str) and arrival_date:
        try:
            arr_dt = datetime.fromisoformat(arrival_date.replace("Z","+00:00"))
        except ValueError:
            try:
                arr_dt = datetime.strptime(arrival_date, "%m/%d/%Y")
            except ValueError:
                pass
    elif isinstance(arrival_date, pd.Timestamp):
        arr_dt = arrival_date.to_pydatetime()
    elif isinstance(arrival_date, datetime):
        arr_dt = arrival_date

    headers = {"Authorization": chosen_key, "Content-Type": "application/json"}
    msg_url = "https://api.openphone.com/v1/messages"
    call_url= "https://api.openphone.com/v1/calls"

    latest_dt   = None
    latest_type = None
    latest_dir  = None
    call_dur    = None
    agent_name  = None

    total_msgs, total_calls = 0, 0
    ans_calls, mis_calls, attempts = 0, 0, 0
    pre_calls, pre_texts = 0, 0
    post_calls, post_texts= 0, 0
    calls_under_40 = 0

    for pn_id, pn_info in details_map.items():
        fallback_agent = pn_info["fallbackAgentName"]

        # =========== MESSAGES ===========
        next_page = None
        while True:
            params = {
                "phoneNumberId": pn_id,
                "participants": [e164_phone],
                "maxResults": 50
            }
            if next_page:
                params["pageToken"] = next_page
            data_m = rate_limited_get(msg_url, headers, params)
            if not data_m or "data" not in data_m:
                break

            msgs = data_m["data"]
            total_msgs += len(msgs)
            for m in msgs:
                mtime = datetime.fromisoformat(m["createdAt"].replace("Z","+00:00"))
                m_naive = mtime.replace(tzinfo=None)

                if arr_dt:
                    if m_naive < arr_dt:
                        pre_texts += 1
                    else:
                        post_texts += 1

                user_info = m.get("user", {})
                uid = user_info.get("id")
                if uid and uid in user_map:
                    this_agent_name = user_map[uid]
                elif user_info.get("name"):
                    this_agent_name = user_info["name"]
                else:
                    this_agent_name = fallback_agent if fallback_agent else "Unknown Agent"

                if (not latest_dt) or (m_naive > latest_dt):
                    latest_dt   = m_naive
                    latest_type = "Message"
                    latest_dir  = m.get("direction","unknown")
                    agent_name  = this_agent_name

            next_page = data_m.get("nextPageToken")
            if not next_page:
                break

        # =========== CALLS ===========
        next_page = None
        while True:
            params = {
                "phoneNumberId": pn_id,
                "participants": [e164_phone],
                "maxResults": 50
            }
            if next_page:
                params["pageToken"] = next_page
            data_c = rate_limited_get(call_url, headers, params)
            if not data_c or "data" not in data_c:
                break

            calls = data_c["data"]
            total_calls += len(calls)
            for c in calls:
                ctime = datetime.fromisoformat(c["createdAt"].replace("Z","+00:00"))
                c_naive = ctime.replace(tzinfo=None)
                dur = c.get("duration", 0)

                if arr_dt:
                    if c_naive < arr_dt:
                        pre_calls += 1
                    else:
                        post_calls += 1

                if dur < 40:
                    calls_under_40 += 1

                user_info = c.get("user", {})
                uid = user_info.get("id")
                if uid and uid in user_map:
                    this_agent_name = user_map[uid]
                elif user_info.get("name"):
                    this_agent_name = user_info["name"]
                else:
                    this_agent_name = fallback_agent if fallback_agent else "Unknown Agent"

                if (not latest_dt) or (c_naive > latest_dt):
                    latest_dt   = c_naive
                    latest_type = "Call"
                    latest_dir  = c.get("direction","unknown")
                    agent_name  = this_agent_name
                    call_dur    = dur

                attempts += 1
                status = c.get("status","unknown")
                if status == "completed":
                    ans_calls += 1
                elif status in ["missed","no-answer","busy","failed"]:
                    mis_calls += 1

            next_page = data_c.get("nextPageToken")
            if not next_page:
                break

    if not latest_dt:
        return blank_info_dict("No Communications")
    else:
        return {
            'status': f"{latest_type} - {latest_dir}",
            'last_date': latest_dt.strftime("%Y-%m-%d %H:%M:%S"),
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

def blank_info_dict(status_text):
    """Return a dict of zeroed fields, plus a custom status."""
    return {
        'status': status_text,
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

########################################
# 6) PROCESS ONE ROW => EXACTLY 1 KEY
########################################
def process_one_row(idx, row):
    raw_phone = str(row.get("Phone Number","")).strip()

    arrival_val = None
    if "Arrival Date Short" in row:
        ad_short = str(row["Arrival Date Short"]).strip()
        if ad_short:
            dt = try_parse_date(ad_short)
            if dt: arrival_val = dt

    if arrival_val is None and "Arrival Date" in row:
        ad_str = str(row["Arrival Date"]).strip()
        if ad_str:
            dt2 = try_parse_date(ad_str)
            if dt2: arrival_val = dt2

    chosen_key = available_keys.get()
    log(f"[Row {idx}] => phone='{raw_phone}', got key={chosen_key[:6]}")

    try:
        e164_phone = format_phone_number_us(raw_phone)
        if not e164_phone:
            log(f"[Row {idx}] => invalid phone => skipping.")
            return blank_info_dict("Invalid Number")

        log(f"[Row {idx}] => E.164={e164_phone}, arrival={arrival_val}")
        info = get_communication_info(e164_phone, chosen_key, arrival_val)
        log(
            f"[Row {idx}] => Done => {info['status']}, "
            f"calls={info['total_calls']}, msgs={info['total_messages']}"
        )
        return info
    finally:
        log(f"[Row {idx}] => returning key={chosen_key[:6]}")
        available_keys.put(chosen_key)

def try_parse_date(s):
    s = s.replace("Z","+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    # fallback to mm/dd/yyyy
    try:
        return datetime.strptime(s, "%m/%d/%Y")
    except ValueError:
        return None

########################################
# 7) CONCURRENT => 3 WORKERS + PROGRESS
########################################
def fetch_communication_info_unique_keys(df):
    """
    - concurrency=3 => up to 3 rows in parallel.
    - Show a progress bar as rows finish.
    - Return a dataframe with columns including agent name, pre/post-arrival calls, etc.
    """
    n = len(df)
    st.write(f"Processing {n} total rows...")

    progress_bar = st.progress(0)
    progress_text = st.empty()

    results = [None]*n

    def row_worker(i, r):
        return (i, process_one_row(i, r))

    completed = 0
    max_workers = 3

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as exe:
        fut_map = {}
        for i, row in df.iterrows():
            fut = exe.submit(row_worker, i, row)
            fut_map[fut] = i

        for fut in concurrent.futures.as_completed(fut_map):
            i, res = fut.result()
            results[i] = res

            # Update counters
            completed += 1
            percent_done = int(completed * 100 / n)
            progress_bar.progress(percent_done)
            rows_left = n - completed
            progress_text.info(f"Processed {completed} of {n} rows. {rows_left} left.")

    out_df = df.copy()
    out_df["Status"] = [r["status"] for r in results]
    out_df["Last Contact Date"] = [r["last_date"] for r in results]
    out_df["Last Call Duration"] = [r["call_duration"] for r in results]
    out_df["Last Agent Name"] = [r["agent_name"] for r in results]
    out_df["Total Messages"] = [r["total_messages"] for r in results]
    out_df["Total Calls"] = [r["total_calls"] for r in results]
    out_df["Answered Calls"] = [r["answered_calls"] for r in results]
    out_df["Missed Calls"] = [r["missed_calls"] for r in results]
    out_df["Call Attempts"] = [r["call_attempts"] for r in results]
    out_df["Pre-Arrival Calls"] = [r["pre_arrival_calls"] for r in results]
    out_df["Pre-Arrival Texts"] = [r["pre_arrival_texts"] for r in results]
    out_df["Post-Arrival Calls"] = [r["post_arrival_calls"] for r in results]
    out_df["Post-Arrival Texts"] = [r["post_arrival_texts"] for r in results]
    out_df["Calls <40s"] = [r["calls_under_40sec"] for r in results]

    return out_df

########################################
# 8) MAIN STREAMLIT
########################################
def run_guest_status_tab():
    st.title("OpenPhone concurrency with Agent Names & Pre-Arrival Stats")

    # 1) Pre-fetch phoneNumberIds & /users for each key
    st.write("**Initializing phoneNumberIds & user info for each key** ...")
    initialize_all_keys()
    st.write("**Initialization done**. Ready to process rows in concurrency.")

    file = st.file_uploader("Upload Excel/CSV with 'Phone Number'", type=["xlsx","xls","csv"])
    if not file:
        st.info("Awaiting file...")
        return

    if file.name.lower().endswith(("xlsx","xls")):
        df = pd.read_excel(file)
    else:
        df = pd.read_csv(file)

    if "Phone Number" not in df.columns:
        st.error("No 'Phone Number' column found.")
        return

    st.write("Data Preview:", df.head())

    # 2) Perform concurrency with progress
    final_df = fetch_communication_info_unique_keys(df)

    # ==== FIX ARROW SERIALIZATION by forcing object columns to string ====
    for col in final_df.columns:
        if final_df[col].dtype == "object":
            final_df[col] = final_df[col].astype(str)

    st.success("All done. Here is the result:")
    st.dataframe(final_df.head(50))

    st.write("### Logs:")
    from queue import Empty
    while True:
        try:
            msg = log_queue.get_nowait()
        except Empty:
            break
        st.write(msg)

    # 3) Download final
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        final_df.to_excel(writer, index=False, sheet_name="Updated")
    buffer.seek(0)

    st.download_button(
        "Download Updated Excel",
        data=buffer.getvalue(),
        file_name="updated_with_agent_names_prepost.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    run_guest_status_tab()
