import streamlit as st
import requests
from datetime import datetime
import phonenumbers
import pandas as pd
import altair as alt

###############################################################################
# API CONFIG
###############################################################################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

###############################################################################
# HELPER FUNCTIONS
###############################################################################
def format_phone_number_str(num_str: str) -> str:
    """
    Attempt to parse num_str as a US phone number and produce an E.164 
    string (e.g., '+17168600690'). 
    If parsing fails, return the original user input.
    """
    if not num_str:
        return ""
    try:
        parsed = phonenumbers.parse(num_str, "US")
        if phonenumbers.is_valid_number(parsed):
            return f"+{parsed.country_code}{parsed.national_number}"
    except Exception:
        pass
    # fallback if parse fails
    return num_str

def get_openphone_numbers():
    """Return a list of your OpenPhone numbers from the API."""
    url = "https://api.openphone.com/v1/phone-numbers"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("data", [])
    return []

def fetch_call_history(phone_number: str):
    """
    Fetch call history from OpenPhone using an E.164 US format
    if possible, else the raw input if parse fails.
    """
    from_num = format_phone_number_str(phone_number)
    if not from_num:
        return []
    all_calls = []
    for op_number in get_openphone_numbers():
        phone_number_id = op_number.get("id")
        if phone_number_id:
            url = "https://api.openphone.com/v1/calls"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [from_num],
                "maxResults": 100
            }
            resp = requests.get(url, headers=HEADERS, params=params)
            if resp.status_code == 200:
                all_calls.extend(resp.json().get("data", []))
    return all_calls

def fetch_message_history(phone_number: str):
    """
    Fetch message history from OpenPhone using an E.164 US format
    if possible, else the raw input if parse fails.
    """
    from_num = format_phone_number_str(phone_number)
    if not from_num:
        return []
    all_msgs = []
    for op_number in get_openphone_numbers():
        phone_number_id = op_number.get("id")
        if phone_number_id:
            url = "https://api.openphone.com/v1/messages"
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [from_num],
                "maxResults": 100
            }
            resp = requests.get(url, headers=HEADERS, params=params)
            if resp.status_code == 200:
                all_msgs.extend(resp.json().get("data", []))
    return all_msgs

def fetch_call_transcript(call_id: str):
    """Fetch transcript lines for a given call ID."""
    url = f"https://api.openphone.com/v1/call-transcripts/{call_id}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        return response.json().get("data", {})
    return None

def format_duration_seconds(sec):
    """
    Convert integer/float 'sec' -> "Xm YYs".
    Example: 185 -> "3m 05s"
    """
    if not sec or sec < 0:
        return "0m 00s"
    sec = int(sec)
    m, s = divmod(sec, 60)
    return f"{m}m {s:02d}s"

def get_call_from_to(call_data):
    """
    For calls, 'from' & 'to' might be strings or dicts with 'phoneNumber'.
    Return (str_from, str_to).
    """
    c_from = call_data.get("from", "")
    c_to   = call_data.get("to", "")
    
    # If dict, get .get('phoneNumber')
    if isinstance(c_from, dict):
        c_from = c_from.get("phoneNumber", "")
    if isinstance(c_to, dict):
        c_to = c_to.get("phoneNumber", "")

    c_from = format_phone_number_str(c_from) if c_from else ""
    c_to   = format_phone_number_str(c_to)   if c_to   else ""

    # fallback
    if not c_from:
        c_from = "Unknown"
    if not c_to:
        c_to = "Unknown"

    return c_from, c_to

def get_msg_from_to(msg_data):
    """
    For messages, doc says: 
      "from": "+15555550123" (string)
      "to": ["+15555550123"] (array of strings)
    Return (str_from, str_to).
    If there's multiple recipients in 'to', we join them with commas.
    """
    m_from = msg_data.get("from", "")
    if not isinstance(m_from, str):
        m_from = ""
    # parse to E.164 if possible
    m_from = format_phone_number_str(m_from) if m_from else ""

    m_to_list = msg_data.get("to", [])
    if not isinstance(m_to_list, list):
        m_to_list = []
    # parse each
    m_to_list = [format_phone_number_str(x) for x in m_to_list if x]
    m_to = ", ".join(m_to_list) if m_to_list else ""

    if not m_from:
        m_from = "Unknown"
    if not m_to:
        m_to = "Unknown"

    return (m_from, m_to)

###############################################################################
# METRICS (TAB 1)
###############################################################################
def display_metrics(calls, messages):
    st.header("📊 Communication Metrics")

    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_calls = len_
