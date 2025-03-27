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
# 1) FOUR HARD-CODED OPENPHONE API KEYS
########################################
OPENPHONE_API_KEYS = [
    "NRFVc43Gee39yIBu6mfC6Ya34K5moaSL",
    "s270j8VAfL9mqRCr7y8PwIoDnoADfFlO",
    "vP92GK3ZjiHi1aRVR29QKzilRsu0xnMI",
    "1mCfUABVby1FmX8LSiAk6UHOPWGEApRQ"
]

# We will store, for each key, a dict { phoneNumberId -> phoneNumberName }.
key_to_phone_number_map = {}

# A queue of keys so each row picks exactly one key at a time
available_keys = queue.Queue()
for k in OPENPHONE_API_KEYS:
    available_keys.put(k)

########################################
# 2) E.164 HELPER
########################################
def format_phone_number_us(raw_number: str) -> str:
    """
    Convert a raw phone string to E.164 if valid, else None.
    Example: '1 843 4285482' -> '+18434285482'
    """
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
    """
    Add a small delay to keep ~5 requests/second per worker thread
    so we don't hit OpenPhone rate limits.
    """
    time.sleep(0.2)
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
# 4) INITIALIZE PHONE-NUMBERS => GET /phone-numbers
########################################
def initialize_phone_numbers_for_key(key):
    """
    For a single key => call GET /phone-numbers => store phoneNumberId -> phoneNumberName
    """
    headers = {"Authorization": key, "Content-Type": "application/json"}
    url = "https://api.openphone.com/v1/phone-numbers"
    data = rate_limited_get(url, headers=headers)
    phone_map = {}

    if data and "data" in data:
        for pn in data["data"]:
            pn_id = pn.get("id")
            if not pn_id:
                continue

            # The phone number's "Name" field => fallback for 'Agent Name'
            number_name = pn.get("name") or "Unknown Number Name"
            phone_map[pn_id] = number_name
    else:
        log(f"phone-numbers => No data for key={key[:6]}")

    key_to_phone_number_map[key] = phone_map

def initialize_all_keys():
    """
    For each key, call GET /phone-numbers once and store results in key_to_phone_number_map.
    """
    for key in OPENPHONE_API_KEYS:
        log(f"Fetching phone numbers for key={key[:6]} ...")
        initialize_phone_numbers_for_key(key)
        count_pns = len(key_to_phone_number_map.get(key, {}))
        log(f"  -> key={key[:6]} => {count_pns} phoneNumbers found")

########################################
# 5) FETCH calls/messages
########################################
def blank_info_dict(status_text):
    """
    Return a dict of zeroed fields + a custom status, for no communications or invalid phone.
    """
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

def parse_arrival_datetime(val):
    """
    Attempt to parse arrival date from multiple formats:
      - datetime/datetime64
      - "2025-03-27"
      - "3/27/2025"
      - "2025-03-27T00:00:00Z"
    Return a Python datetime or None if invalid.
    """
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, pd.Timestamp):
        return val.to_pydatetime()

    s = str(val).strip()
    s = s.replace("Z","+00:00")
    # Try ISO parse
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    # Then try mm/dd/yyyy
    try:
        return datetime.strptime(s, "%m/%d/%Y")
    except ValueError:
        return None

def get_communication_info(e164_phone, chosen_key, arrival_date=None):
    """
    - For each phoneNumberId => GET messages/calls for e164_phone
    - If a message/call has user["name"], use it. Otherwise fallback to phoneNumber's "name".
    - Classify events as pre- vs. post-arrival if arrival_date is known.
    """
    phone_map = key_to_phone_number_map.get(chosen_key, {})
    if not phone_map:
        return blank_info_dict("No Communications")

    arr_dt = parse_arrival_datetime(arrival_date)

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

    # Iterate over phoneNumberId => phoneNumberName
    for pn_id, pn_name in phone_map.items():
        # 1) MESSAGES
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

                # pre/post arrival
                if arr_dt:
                    if m_naive < arr_dt:
                        pre_texts += 1
                    else:
                        post_texts += 1

                # if message has user["name"], use it; else fallback to phoneNumber name
                user_info = m.get("user", {})
                u_name = user_info.get("name")
                if not (u_name and u_name.strip()):
                    u_name = pn_name

                # track last communication
                if (not latest_dt) or (m_naive > latest_dt):
                    latest_dt   = m_naive
                    latest_type = "Message"
                    latest_dir  = m.get("direction","unknown")
                    agent_name  = u_name

            next_page = data_m.get("nextPageToken")
            if not next_page:
                break

        # 2) CALLS
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
                dur = c.get("duration",0)

                if arr_dt:
                    if c_naive < arr_dt:
                        pre_calls += 1
                    else:
                        post_calls += 1

                if dur < 40:
                    calls_under_40 += 1

                user_info = c.get("user", {})
                u_name = user_info.get("name")
                if not (u_name and u_name.strip()):
                    u_name = pn_name

                if (not latest_dt) or (c_naive > latest_dt):
                    latest_dt   = c_naive
                    latest_type = "Call"
                    latest_dir  = c.get("direction","unknown")
                    agent_name  = u_name
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

########################################
# 6) PROCESS ONE ROW => EXACTLY 1 KEY
########################################
def process_one_row(idx, row):
    """
    Extract phone from 'Phone Number', parse arrival date from 'Arrival Date Short'
    or 'Arrival Date', pick a key, fetch comm info, return results dict.
    """
    raw_phone = str(row.get("Phone Number","")).strip()

    # parse arrival
    arrival_val = None
    if "Arrival Date Short" in row:
        ad_short = str(row["Arrival Date Short"]).strip()
        if ad_short:
            dt_short = parse_arrival_datetime(ad_short)
            if dt_short:
                arrival_val = dt_short

    if not arrival_val and "Arrival Date" in row:
        ad_str = str(row["Arrival Date"]).strip()
        if ad_str:
            dt_full = parse_arrival_datetime(ad_str)
            if dt_full:
                arrival_val = dt_full

    chosen_key = available_keys.get()
    log(f"[Row {idx}] => phone='{raw_phone}', got key={chosen_key[:6]}")

    try:
        e164_phone = format_phone_number_us(raw_phone)
        if not e164_phone:
            log(f"[Row {idx}] => invalid phone => skipping.")
            # Return the blank info for "Invalid Number"
            d = blank_info_dict("Invalid Number")
            d["agent_name"] = "Unknown"
            return d

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

########################################
# 7) CONCURRENT => 3 WORKERS + PROGRESS
########################################
def fetch_communication_info_unique_keys(df):
    """
    Process the DataFrame rows with concurrency=3.
    Show a progress bar as each row finishes, returning an augmented DataFrame.
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

            completed += 1
            pct = int(completed * 100 / n)
            progress_bar.progress(pct)
            left = n - completed
            progress_text.info(f"Processed {completed} of {n} rows. {left} left.")

    # Build columns
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
    st.title("OpenPhone concurrency – fallback to phoneNumber.name if user.name is empty")

    # 1) Pre-fetch phone numbers => store phoneNumberId -> phoneNumberName
    st.write("**Initializing phone numbers for each key** ...")
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

    # 2) concurrency
    final_df = fetch_communication_info_unique_keys(df)

    # Force object columns to string => fix arrow errors
    for col in final_df.columns:
        if final_df[col].dtype == "object":
            final_df[col] = final_df[col].astype(str)

    st.success("All done. Here is the result:")
    st.dataframe(final_df.head(50))

    # Show logs
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
        file_name="updated_phoneNumberName_fallback.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    run_guest_status_tab()
