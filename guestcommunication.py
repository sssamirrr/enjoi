import time
import requests
import io
from datetime import datetime
import pandas as pd
import streamlit as st
import phonenumbers

############################################
# 1. API Credentials
############################################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}


############################################
# 2. Rate-limited request (10 req/sec with backoff)
############################################
def rate_limited_request(url, headers, params, request_type='get', max_retries=5):
    """
    Makes an API request with rate-limiting (10 requests/sec) and exponential backoff
    in case of hitting the rate limit (429 status).
    """
    retries = 0
    delay = 0.1  # 0.1 seconds = 10 requests per second

    while retries < max_retries:
        try:
            if request_type == 'get':
                response = requests.get(url, headers=headers, params=params)
            else:
                response = None

            # If the request is successful
            if response and response.status_code == 200:
                return response.json()

            # Handle rate-limiting (429 Too Many Requests)
            if response and response.status_code == 429:
                st.warning(f"Rate limit exceeded. Retrying in {delay} seconds...")
                time.sleep(delay)
                retries += 1
                delay *= 2  # Exponential backoff
                continue

            # For other non-200 errors, show a warning
            st.warning(f"API Error: {response.status_code}")
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

    phone_number must already be in E.164 format (e.g., +15555550123).
    """
    # Make sure phone_number is already in E.164 format here
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

    # Convert arrival_date to datetime
    if isinstance(arrival_date, str):
        arrival_date = datetime.fromisoformat(arrival_date)
    elif isinstance(arrival_date, pd.Timestamp):
        arrival_date = arrival_date.to_pydatetime()
    arrival_date_only = arrival_date.date() if arrival_date else None

    for phone_number_id in phone_number_ids:
        # -------------------------------------------
        # 1) Messages
        # -------------------------------------------
        next_page = None
        while True:
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [phone_number],  # phone_number is E.164
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

                    # Track the latest communication
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

        # -------------------------------------------
        # 2) Calls
        # -------------------------------------------
        next_page = None
        while True:
            params = {
                "phoneNumberId": phone_number_id,
                "participants": [phone_number],  # phone_number is E.164
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

                    # Pre/Post arrival
                    if arrival_date_only:
                        if call_time.date() <= arrival_date_only:
                            pre_arrival_calls += 1
                        else:
                            post_arrival_calls += 1

                    # Under 40s
                    if duration < 40:
                        calls_under_40sec += 1

                    # Track the latest communication
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

    # Final status
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
