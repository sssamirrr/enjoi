import time
import requests
import io
from datetime import datetime
import pandas as pd
import streamlit as st

############################################
# 1. Hard-coded API credentials:
############################################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"  # <--- Replace if needed
OPENPHONE_NUMBER = "+18438972426"                      # <--- Replace if needed

############################################
# 2. Helper Function: rate_limited_request
############################################
def rate_limited_request(url, headers, params, request_type='get'):
    """
    Make an API request while respecting rate limits.
    By default, sleeps 1/5 seconds (5 requests/second).
    """
    time.sleep(1 / 5)  # 5 requests per second max
    try:
        if request_type == 'get':
            response = requests.get(url, headers=headers, params=params)
        else:
            # Adjust for other request types as needed
            response = None

        if response and response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error: {response.status_code}")
            st.warning(f"Response: {response.text}")
    except Exception as e:
        st.warning(f"Exception during request: {str(e)}")
    return None

############################################
# 3. Helper Function: get_all_phone_number_ids
############################################
def get_all_phone_number_ids(headers):
    """
    Retrieve all phoneNumberIds associated with your OpenPhone account.
    """
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    response_data = rate_limited_request(phone_numbers_url, headers, {})
    if not response_data:
        return []
    # Extract phoneNumber IDs
    return [pn.get('id') for pn in response_data.get('data', [])]

############################################
# 4. Main Logic: get_communication_info
############################################
def get_communication_info(phone_number, headers, arrival_date=None):
    """
    Retrieve communication info for a specific phone number from the OpenPhone API.
    - If arrival_date is provided, we separate calls/texts into pre-arrival vs. post-arrival.
    - If arrival_date is not relevant, we simply fetch all data.
    """
    # 4.1. Get all phoneNumberIds
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

    # 4.2. Define endpoints
    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    # 4.3. Initialize tracking variables
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

    # 4.4. Convert arrival_date to date if provided
    if isinstance(arrival_date, str):
        arrival_date = datetime.fromisoformat(arrival_date)
    elif isinstance(arrival_date, pd.Timestamp):
        arrival_date = arrival_date.to_pydatetime()
    if arrival_date:
        arrival_date_only = arrival_date.date()
    else:
        arrival_date_only = None

    # 4.5. Loop through each phoneNumberId and fetch messages/calls
    for phone_number_id in phone_number_ids:
        # ------------------------------
        # A) Paginate through MESSAGES
        # ------------------------------
        next_page = None
        while True:
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [phone_number],
                "maxResults": 50
            }
            if next_page:
                params['pageToken'] = next_page

            messages_response = rate_limited_request(messages_url, headers, params)
            if messages_response and 'data' in messages_response:
                messages = messages_response['data']
                total_messages += len(messages)

                for message in messages:
                    msg_time = datetime.fromisoformat(
                        message['createdAt'].replace('Z', '+00:00')
                    )
                    msg_date = msg_time.date()
                    if arrival_date_only:
                        if msg_date <= arrival_date_only:
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
                # No data or error, break out
                break

        # ---------------------------
        # B) Paginate through CALLS
        # ---------------------------
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
                    call_time = datetime.fromisoformat(
                        call['createdAt'].replace('Z', '+00:00')
                    )
                    call_date = call_time.date()
                    duration = call.get("duration", 0)

                    if arrival_date_only:
                        if call_date <= arrival_date_only:
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

                    # Determine if the call was answered
                    call_status = call.get('status', 'unknown')
                    if call_status == 'completed':
                        answered_calls += 1
                    elif call_status in ['missed', 'no-answer', 'busy', 'failed']:
                        missed_calls += 1

                next_page = calls_response.get('nextPageToken')
                if not next_page:
                    break
            else:
                # No data or error, break out
                break

    # 4.6. Determine final "status"
    if not latest_datetime:
        status = "No Communications"
    else:
        status = f"{latest_type} - {latest_direction}"

    # 4.7. Return the dictionary of metrics
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
# 5. fetch_communication_info for a DataFrame
############################################
def fetch_communication_info(df, headers):
    """
    Loops through each row in a DataFrame (must have 'Phone Number' column)
    and appends communication info as new columns.

    Returns a new DataFrame with appended columns.
    """
    # Prepare columns to store results
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

    for idx, row in df.iterrows():
        phone = row.get('Phone Number')
        # If you have an 'Arrival Date' or 'Check In' column, adapt accordingly:
        arrival_date = row.get('Arrival Date')  # or row.get('Check In')

        if phone and phone != 'No Data':
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
                # Fill in default values
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

    # Create new columns in the DF
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
# 6. The main Streamlit function to run
############################################
def run_guest_status_tab():
    """
    Streamlit UI to:
      1) Upload an Excel file with phone numbers
      2) Call fetch_communication_info to enrich data
      3) Download the updated file
    """
    st.title("Guest Communication Insights (Hard-Coded API Key)")

    # A) File uploader
    uploaded_file = st.file_uploader("Upload an Excel file (with 'Phone Number' column)", type=["xlsx", "xls"])

    if uploaded_file is not None:
        # B) Convert uploaded file to DataFrame
        df = pd.read_excel(uploaded_file)

        if 'Phone Number' not in df.columns:
            st.error("Please ensure your Excel has a column named 'Phone Number'.")
            return

        # C) Prepare headers (no 'Bearer', just key)
        headers = {
            "X-Api-Key": OPENPHONE_API_KEY,      # <--- Non-bearer usage
            "Content-Type": "application/json"
        }

        st.info("Enriching data with OpenPhone communication details. This may take a while if you have many rows...")

        # D) Fetch communication info and update the DataFrame
        updated_df = fetch_communication_info(df, headers)

        # E) Show a preview
        st.subheader("Preview of Updated Data")
        st.dataframe(updated_df.head(50))

        # F) Download button
        st.subheader("Download Updated Excel")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            updated_df.to_excel(writer, index=False, sheet_name='Updated')
            writer.save()

        st.download_button(
            label="Download Updated Excel",
            data=output.getvalue(),
            file_name="updated_communication_info.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

############################################
# 7. If you run this file directly with:
#    streamlit run guestcommunication.py
#    the function below will execute.
############################################
if __name__ == "__main__":
    run_guest_status_tab()