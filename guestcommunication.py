import time
import requests
import io
from datetime import datetime
import pandas as pd
import streamlit as st
import phonenumbers  # For phone number formatting

############################################
# 1. Hard-coded API credentials:
############################################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6aebhl6lG6Z7"  # Replace with your real API key
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,  # <-- No "Bearer " prefix here
    "Content-Type": "application/json"
}

############################################
# 1b. Helper to format phone numbers to E.164
############################################
def format_phone_number_us(raw_number: str) -> str:
    """
    Attempts to parse a phone number as a US number and return
    it in E.164 format (e.g., +14075206507).
    Returns None if parsing fails or invalid number.
    """
    try:
        parsed = phonenumbers.parse(raw_number, "US")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    return None

############################################
# 2. Rate-limited request (max ~10 req/sec)
############################################
def rate_limited_request(url, headers, params, request_type='get', max_retries=5):
    """
    Makes an API request with:
    - Throttle of 5 requests per second
    - Exponential backoff on 429 rate-limit errors
    - Honors 'Retry-After' header if provided
    """
    # Lower the throttle to 5 requests/sec to reduce bursts
    time.sleep(1 / 5)

    retries = 0
    backoff_delay = 1  # initial backoff

    while retries < max_retries:
        try:
            if request_type == 'get':
                response = requests.get(url, headers=headers, params=params)
            else:
                response = None

            if response is None:
                st.warning("No valid response object. Possibly invalid request_type.")
                break

            if response.status_code == 200:
                # Success
                return response.json()
            elif response.status_code == 429:
                # Rate limit error
                st.warning("429 Too Many Requests encountered!")
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    # If the API says 'wait X seconds'
                    wait_time = int(retry_after)
                    st.warning(f"Server says wait {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    # Otherwise do exponential backoff
                    st.warning(f"Backing off {backoff_delay}s ...")
                    time.sleep(backoff_delay)
                    backoff_delay *= 2
                retries += 1
                continue
            else:
                # Some other error (4xx, 5xx, etc.)
                st.warning(f"API Error {response.status_code}")
                st.warning(f"Response: {response.text}")
                break

        except Exception as e:
            st.warning(f"Exception during request: {str(e)}")
            break

    # Return None if all retries fail
    return None

############################################
# 3. Get phone number IDs
############################################
def get_all_phone_number_ids(headers):
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    response_data = rate_limited_request(phone_numbers_url, headers, {})
    if not response_data:
        return []
    return [pn.get('id') for pn in response_data.get('data', [])]

############################################
# 4. Get communication info
############################################
def get_communication_info(phone_number, headers, arrival_date=None):
    """
    Retrieves messages and calls info for the given phone_number from OpenPhone,
    including stats like total_messages, total_calls, etc.

    phone_number must be in E.164 format (e.g., +15555550123).
    """
    phone_number_ids = get_all_phone_number_ids(headers)
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

    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    latest_datetime = None
    latest_type = None
    latest_direction = None
    call_duration = None
    agent_name = None

    total_messages = 0
    total_calls = 0
    answered_calls = 0
    missed_calls = 0
    call_attempts = 0

    pre_arrival_calls = 0
    pre_arrival_texts = 0
    post_arrival_calls = 0
    post_arrival_texts = 0
    calls_under_40sec = 0

    # Convert arrival_date to datetime if provided
    if isinstance(arrival_date, str):
        arrival_date = datetime.fromisoformat(arrival_date)
    elif isinstance(arrival_date, pd.Timestamp):
        arrival_date = arrival_date.to_pydatetime()
    arrival_date_only = arrival_date.date() if arrival_date else None

    for phone_number_id in phone_number_ids:
        # Messages
        next_page = None
        while True:
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [phone_number],  # E.164
                "maxResults": 50
            }
            if next_page:
                params['pageToken'] = next_page

            messages_response = rate_limited_request(messages_url, headers, params)
            if messages_response and 'data' in messages_response:
                messages = messages_response['data']
                total_messages += len(messages)
                for message in messages:
                    msg_time = datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00'))
                    if arrival_date_only:
                        if msg_time.date() <= arrival_date_only:
                            pre_arrival_texts += 1
                        else:
                            post_arrival_texts += 1

                    if not latest_datetime or msg_time > latest_datetime:
                        latest_datetime = msg_time
                        latest_type = "Message"
                        latest_direction = message.get("direction", "unknown")
                        agent_name = message.get("user", {}).get("name", "Unknown Agent")

                next_page = messages_response.get('nextPageToken')
                if not next_page:
                    break
            else:
                break

        # Calls
        next_page = None
        while True:
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [phone_number],
                "maxResults": 50
            }
            if next_page:
                params['pageToken'] = next_page

            calls_response = rate_limited_request(calls_url, headers, params)
            if calls_response and 'data' in calls_response:
                calls = calls_response['data']
                total_calls += len(calls)
                for call in calls:
                    call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00'))
                    duration = call.get("duration", 0)

                    if arrival_date_only:
                        if call_time.date() <= arrival_date_only:
                            pre_arrival_calls += 1
                        else:
                            post_arrival_calls += 1

                    if duration < 40:
                        calls_under_40sec += 1

                    if not latest_datetime or call_time > latest_datetime:
                        latest_datetime = call_time
                        latest_type = "Call"
                        latest_direction = call.get("direction", "unknown")
                        call_duration = duration
                        agent_name = call.get("user", {}).get("name", "Unknown Agent")

                    call_attempts += 1
                    call_status = call.get('status', 'unknown')
                    if call_status == 'completed':
                        answered_calls += 1
                    elif call_status in ['missed', 'no-answer', 'busy', 'failed']:
                        missed_calls += 1
                next_page = calls_response.get('nextPageToken')
                if not next_page:
                    break
            else:
                break

    if not latest_datetime:
        status = "No Communications"
    else:
        status = f"{latest_type} - {latest_direction}"

    return {
        'status': status,
        'last_date': latest_datetime.strftime("%Y-%m-%d %H:%M:%S") if latest_datetime else None,
        'call_duration': call_duration,
        'agent_name': agent_name,
        'total_messages': total_messages,
        'total_calls': total_calls,
        'answered_calls': answered_calls,
        'missed_calls': missed_calls,
        'call_attempts': call_attempts,
        'pre_arrival_calls': pre_arrival_calls,
        'pre_arrival_texts': pre_arrival_texts,
        'post_arrival_calls': post_arrival_calls,
        'post_arrival_texts': post_arrival_texts,
        'calls_under_40sec': calls_under_40sec
    }

############################################
# 5. For a DataFrame with 'Phone Number'
############################################
def fetch_communication_info(df, headers):
    """
    Loops through each row in a DataFrame (must have 'Phone Number' column)
    and calls get_communication_info() for each phone number (formatted to E.164).
    """
    # Prepare new columns
    statuses = []
    dates = []
    durations = []
    agent_names = []
    total_messages_list = []
    total_calls_list = []
    answered_calls_list = []
    missed_calls_list = []
    call_attempts_list = []
    pre_arrival_calls_list = []
    pre_arrival_texts_list = []
    post_arrival_calls_list = []
    post_arrival_texts_list = []
    calls_under_40sec_list = []

    for _, row in df.iterrows():
        raw_phone = row.get('Phone Number')
        arrival_date = row.get('Arrival Date')  # optional column

        # 1) Convert to +1XXXXXXXXXX format
        phone = format_phone_number_us(str(raw_phone)) if raw_phone else None

        if phone:
            # 2) Fetch data
            try:
                comm_info = get_communication_info(phone, headers, arrival_date)
                statuses.append(comm_info['status'])
                dates.append(comm_info['last_date'])
                durations.append(comm_info['call_duration'])
                agent_names.append(comm_info['agent_name'])
                total_messages_list.append(comm_info['total_messages'])
                total_calls_list.append(comm_info['total_calls'])
                answered_calls_list.append(comm_info['answered_calls'])
                missed_calls_list.append(comm_info['missed_calls'])
                call_attempts_list.append(comm_info['call_attempts'])
                pre_arrival_calls_list.append(comm_info['pre_arrival_calls'])
                pre_arrival_texts_list.append(comm_info['pre_arrival_texts'])
                post_arrival_calls_list.append(comm_info['post_arrival_calls'])
                post_arrival_texts_list.append(comm_info['post_arrival_texts'])
                calls_under_40sec_list.append(comm_info['calls_under_40sec'])
            except Exception as e:
                st.warning(f"Error fetching info for phone {phone}: {e}")
                # Fill placeholders
                statuses.append("Error")
                dates.append(None)
                durations.append(None)
                agent_names.append("Unknown")
                total_messages_list.append(0)
                total_calls_list.append(0)
                answered_calls_list.append(0)
                missed_calls_list.append(0)
                call_attempts_list.append(0)
                pre_arrival_calls_list.append(0)
                pre_arrival_texts_list.append(0)
                post_arrival_calls_list.append(0)
                post_arrival_texts_list.append(0)
                calls_under_40sec_list.append(0)
        else:
            # Invalid or missing phone number
            statuses.append("Invalid Number")
            dates.append(None)
            durations.append(None)
            agent_names.append("Unknown")
            total_messages_list.append(0)
            total_calls_list.append(0)
            answered_calls_list.append(0)
            missed_calls_list.append(0)
            call_attempts_list.append(0)
            pre_arrival_calls_list.append(0)
            pre_arrival_texts_list.append(0)
            post_arrival_calls_list.append(0)
            post_arrival_texts_list.append(0)
            calls_under_40sec_list.append(0)

    # Create columns in the DataFrame
    df['Communication Status'] = statuses
    df['Last Contact Date'] = dates
    df['Last Call Duration'] = durations
    df['Last Agent Name'] = agent_names
    df['Total Messages'] = total_messages_list
    df['Total Calls'] = total_calls_list
    df['Answered Calls'] = answered_calls_list
    df['Missed Calls'] = missed_calls_list
    df['Call Attempts'] = call_attempts_list
    df['Pre-Arrival Calls'] = pre_arrival_calls_list
    df['Pre-Arrival Texts'] = pre_arrival_texts_list
    df['Post-Arrival Calls'] = post_arrival_calls_list
    df['Post-Arrival Texts'] = post_arrival_texts_list
    df['Calls < 40s'] = calls_under_40sec_list

    return df

############################################
# 6. Main Streamlit function
############################################
def run_guest_status_tab():
    """
    Streamlit UI:
      1) Upload Excel (with 'Phone Number')
      2) Convert phone => E.164
      3) Fetch data from OpenPhone
      4) Display & Download
    """
    st.title("Guest Communication Insights (No 'Bearer', Single API Key)")

    uploaded_file = st.file_uploader("Upload Excel (with 'Phone Number')", type=["xlsx","xls"])
    if not uploaded_file:
        st.info("Please upload a file.")
        return

    df = pd.read_excel(uploaded_file)
    if 'Phone Number' not in df.columns:
        st.error("Missing 'Phone Number' column.")
        return

    updated_df = fetch_communication_info(df, HEADERS)

    st.subheader("Preview of Updated Data")
    st.dataframe(updated_df.head(50))

    # Prepare for download
    import io
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        updated_df.to_excel(writer, index=False, sheet_name='Updated')

    output.seek(0)

    st.download_button(
        label="Download Updated Excel",
        data=output.getvalue(),
        file_name="updated_communication_info.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# If you want to run this directly
if __name__ == "__main__":
    run_guest_status_tab()
