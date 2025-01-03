import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime, timedelta

############################
# 1) OpenPhone API Key     #
############################
# NOTE: Including your API key exactly as you requested (no 'Bearer ' prefix).
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

def get_headers():
    """
    Returns the headers for OpenPhone API requests,
    using the API key exactly as provided.
    """
    return {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }

def rate_limited_request(url, headers, params=None):
    """
    Makes a GET request, sleeping ~0.2s to respect ~5 req/sec limit.
    """
    time.sleep(0.2)
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        return resp.json()
    else:
        st.warning(f"API Error: {resp.status_code}")
        st.warning(f"Response: {resp.text}")
    return None

def fetch_calls(phone_number_id, your_e164_number, start_date, end_date, max_calls=200):
    """
    Fetch calls for 'phoneNumberId' within [start_date, end_date].
    - 'your_e164_number' is your E.164 formatted phone, e.g. '+14155550100'.
    - We pass 'participants[]=your_e164_number' to retrieve calls involving this number.
    """
    base_url = "https://api.openphone.com/v1/calls"
    all_calls = []
    next_page_token = None

    while True:
        # We'll build `params` as a list of tuples to encode multiple query params properly.
        params_list = [
            ("phoneNumberId", phone_number_id),
            ("createdAfter", start_date.isoformat()),   # e.g. "2023-09-01T00:00:00Z"
            ("createdBefore", end_date.isoformat()),    # e.g. "2023-12-01T00:00:00Z"
            ("maxResults", "50"),
            # Trick: pass your E.164 phone to satisfy the "required participants" constraint
            ("participants[]", your_e164_number),
        ]
        if next_page_token:
            params_list.append(("pageToken", next_page_token))

        data = rate_limited_request(base_url, get_headers(), params=params_list)
        if not data or "data" not in data:
            break

        all_calls.extend(data["data"])
        next_page_token = data.get("nextPageToken")

        if not next_page_token or len(all_calls) >= max_calls:
            break

    return all_calls[:max_calls]

def main():
    st.set_page_config(page_title="OpenPhone - All Calls for My Number", layout="wide")
    st.title("OpenPhone: All Calls for My Number")

    # Let user specify their line details
    st.write("Enter your phoneNumberId (e.g., PNxxxxxxxx) and your E.164 phone number (e.g. +14155550100).")
    phone_number_id = st.text_input("Phone Number ID:", "PNxxxxxx")
    your_e164_number = st.text_input("Your E.164 Phone Number:", "+YOUR_E164_PHONE")

    if st.button("Fetch Calls (Last 3 Months)"):
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=90)  # ~3 months

        with st.spinner("Loading calls..."):
            calls = fetch_calls(phone_number_id, your_e164_number, start_date, end_date, max_calls=200)
        st.success(f"Fetched {len(calls)} calls.")

        # Display them in a table
        if calls:
            rows = []
            for c in calls:
                rows.append({
                    "Call ID": c.get("id", ""),
                    "Direction": c.get("direction", ""),
                    "Status": c.get("status", ""),
                    "From": c.get("from", {}).get("phoneNumber", "") if isinstance(c.get("from"), dict) else c.get("from"),
                    "To": c.get("to", []),
                    "Created At": c.get("createdAt", "")
                })
            df = pd.DataFrame(rows)
            st.dataframe(df)

if __name__ == "__main__":
    main()
