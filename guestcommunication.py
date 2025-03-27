import streamlit as st
import pandas as pd
import phonenumbers
import requests
import time
import io
import queue
import concurrent.futures
from datetime import datetime, timedelta

########################################
# 0) GLOBALS
########################################
log_queue = queue.Queue()

def log(msg):
    log_queue.put(msg)

########################################
# 1) FOUR OPENPHONE API KEYS (HARD-CODED)
########################################
OPENPHONE_API_KEYS = [
    "NRFVc43Gee39yIBu6mfC6Ya34K5moaSL",
    "s270j8VAfL9mqRCr7y8PwIoDnoADfFlO",
    "vP92GK3ZjiHi1aRVR29QKzilRsu0xnMI",
    "1mCfUABVby1FmX8LSiAk6UHOPWGEApRQ"
]

key_to_pnids = {}
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
def rate_limited_get(url, headers, params):
    time.sleep(0.2)  # ~5 requests/sec
    try:
        r = requests.get(url, headers=headers, params=params)
        if r.status_code == 200:
            return r.json()
        else:
            log(f"API Error {r.status_code}: {r.text}")
            return None
    except Exception as e:
        log(f"Request exception: {e}")
        return None

########################################
# 4) FETCH phoneNumberIds FOR EACH KEY
########################################
def initialize_phone_number_ids():
    for key in OPENPHONE_API_KEYS:
        log(f"Fetching phoneNumberIds for key={key[:6]} once...")
        headers = {"Authorization": key, "Content-Type": "application/json"}
        url = "https://api.openphone.com/v1/phone-numbers"
        data = rate_limited_get(url, headers, params={})
        if data and "data" in data:
            pn_ids = [d.get("id") for d in data["data"] if d.get("id")]
            key_to_pnids[key] = pn_ids
            log(f"  -> Found {len(pn_ids)} phoneNumberIds with key={key[:6]}")
        else:
            key_to_pnids[key] = []
            log(f"  -> Error or no data with key={key[:6]} => 0 phoneNumberIds")

########################################
# 5) FETCH calls/messages
########################################
def get_communication_info(e164_phone, chosen_key, arrival_date=None):
    """
    We define 'pre_arrival' as any call/text that occurred
    BEFORE 11:00 AM on the arrival date. 'post_arrival' is
    on or after 11:00 AM that date.
    """
    phone_number_ids = key_to_pnids.get(chosen_key, [])
    if not phone_number_ids:
        log(f"   -> key={chosen_key[:6]} => no phoneNumberIds => 'No Communications'")
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

    # If arrival_date is a string, try parsing it
    # (you can unify this logic if you parse earlier)
    if isinstance(arrival_date, str):
        try:
            # handle "2025-03-14" style
            arrival_date = datetime.fromisoformat(arrival_date)
        except ValueError:
            # handle "3/14/2025" style
            try:
                arrival_date = datetime.strptime(arrival_date, "%m/%d/%Y")
            except ValueError:
                arrival_date = None
    elif isinstance(arrival_date, pd.Timestamp):
        arrival_date = arrival_date.to_pydatetime()

    # The critical check: define an 11:00 AM threshold
    arrival_11am = None
    if arrival_date:
        arrival_11am = arrival_date.replace(
            hour=11, minute=0, second=0, microsecond=0
        )

    headers = {"Authorization": chosen_key, "Content-Type": "application/json"}
    msg_url  = "https://api.openphone.com/v1/messages"
    call_url = "https://api.openphone.com/v1/calls"

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

    for pn_id in phone_number_ids:
        log(f"      -> key={chosen_key[:6]}, phoneNumberId={pn_id}, phone={e164_phone}")
        
        # ========== MESSAGES ==========
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
                # parse "2022-01-01T00:00:00Z" => "2022-01-01T00:00:00+00:00"
                mtime = datetime.fromisoformat(
                    m["createdAt"].replace("Z", "+00:00")
                )
                # Make it "naive" by dropping tzinfo, if you prefer
                mtime_naive = mtime.replace(tzinfo=None)

                if arrival_11am:
                    # before 11am => pre
                    if mtime_naive < arrival_11am:
                        pre_texts += 1
                    else:
                        post_texts += 1

                # track the "last" (most recent) communication
                if not latest_dt or mtime_naive > latest_dt:
                    latest_dt   = mtime_naive
                    latest_type = "Message"
                    latest_dir  = m.get("direction","unknown")
                    agent_name  = m.get("user",{}).get("name","Unknown Agent")

            next_page = data_m.get("nextPageToken")
            if not next_page:
                break

        # ========== CALLS ==========
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
                ctime_naive = ctime.replace(tzinfo=None)
                dur   = c.get("duration",0)

                if arrival_11am:
                    if ctime_naive < arrival_11am:
                        pre_calls += 1
                    else:
                        post_calls += 1

                if dur < 40:
                    calls_under_40 += 1

                # track most recent communication
                if not latest_dt or ctime_naive > latest_dt:
                    latest_dt   = ctime_naive
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

            next_page = data_c.get("nextPageToken")
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
# 6) PROCESS ONE ROW => EXACTLY 1 KEY
########################################
def process_one_row(idx, row):
    raw_phone = str(row.get("Phone Number","")).strip()

    # Our logic for reading arrival date from columns
    arrival_val = None
    # Try 'Arrival Date Short' if present
    if "Arrival Date Short" in row:
        ad_short = str(row["Arrival Date Short"]).strip()
        if ad_short:
            try:
                # parse e.g. "3/14/2025"
                arrival_val = datetime.strptime(ad_short, "%m/%d/%Y")
            except ValueError:
                pass

    # If still None, try 'Arrival Date' if present
    if arrival_val is None and "Arrival Date" in row:
        ad_str = str(row["Arrival Date"]).strip()
        if ad_str:
            # try "2025-03-14"
            try:
                arrival_val = datetime.fromisoformat(ad_str)
            except ValueError:
                # fallback or ignore
                pass

    chosen_key = available_keys.get()
    log(f"[Row {idx}] => phone='{raw_phone}', got key={chosen_key[:6]}")

    try:
        e164_phone = format_phone_number_us(raw_phone)
        if not e164_phone:
            log(f"[Row {idx}] => invalid phone => skipping.")
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

        log(f"[Row {idx}] => E.164={e164_phone}, arrival={arrival_val}")
        info = get_communication_info(e164_phone, chosen_key, arrival_val)
        log(f"[Row {idx}] => Done => {info['status']}, calls={info['total_calls']}, msgs={info['total_messages']}")
        return info

    finally:
        log(f"[Row {idx}] => returning key={chosen_key[:6]}")
        available_keys.put(chosen_key)

########################################
# 7) CONCURRENT => 3 WORKERS
########################################
def fetch_communication_info_unique_keys(df):
    results = [None]*len(df)
    def row_worker(i, r):
        return (i, process_one_row(i, r))

    max_workers = 3
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as exe:
        fut_map = {}
        for i, row in df.iterrows():
            fut = exe.submit(row_worker, i, row)
            fut_map[fut] = i

        for fut in concurrent.futures.as_completed(fut_map):
            i, res = fut.result()
            results[i] = res

    out_df = df.copy()
    out_df["Status"] = [r["status"] for r in results]
    out_df["Last Contact Date"] = [r["last_date"] for r in results]
    out_df["Date of Last Communication"] = [
        r["last_date"].split(" ")[0] if r["last_date"] else None
        for r in results
    ]
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
    st.title("Fetch phoneNumberIds once, concurrency=3, pre- vs. post-arrival by 11am")

    st.write("**Initializing phoneNumberIds for each key** ...")
    initialize_phone_number_ids()
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
    final_df = fetch_communication_info_unique_keys(df)
    st.success("All done with concurrency. Here is the result:")
    st.dataframe(final_df.head(50))

    st.write("### Logs:")
    from queue import Empty
    while True:
        try:
            msg = log_queue.get_nowait()
        except Empty:
            break
        st.write(msg)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        final_df.to_excel(writer, index=False, sheet_name="Updated")
    buffer.seek(0)

    st.download_button(
        "Download Updated Excel",
        data=buffer.getvalue(),
        file_name="updated_unique_keys_3workers_logs.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    run_guest_status_tab()
