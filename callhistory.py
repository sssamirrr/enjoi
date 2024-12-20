# callhistory.py

import requests
import time
import pandas as pd
from datetime import datetime
import phonenumbers
from urllib.parse import quote  # For URL encoding

# Function to format phone number to E.164
def format_phone_number(phone):
    try:
        parsed_phone = phonenumbers.parse(phone, "US")
        if phonenumbers.is_valid_number(parsed_phone):
            return phonenumbers.format_number(parsed_phone, phonenumbers.PhoneNumberFormat.E164)
        else:
            return None
    except phonenumbers.NumberParseException:
        return None

# Rate-Limited API Request
def rate_limited_request(url, headers, params):
    time.sleep(1 / 5)  # Rate limit: 5 requests per second
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            error_message = f"API Error: {response.status_code}, Response: {response.text}"
            # Raise an exception to be handled by the caller
            raise Exception(error_message)
    except Exception as e:
        # Re-raise the exception to be handled by the caller
        raise e

# Function to generate call history link
def generate_call_history_link(phone_number):
    # Use your app's URL here
    base_url = "https://ldmcbiowzbdeqvmabvudyy.streamlit.app"
    formatted_number = format_phone_number(phone_number)

    if formatted_number:
        encoded_number = quote(formatted_number)  # URL encode the phone number
        return f"{base_url}/?view=call-history&number={encoded_number}"
    return None

# Fetch OpenPhone Communication Data
def get_communication_info(phone_number, headers):
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        return {
            'status': "Invalid Number",
            'last_date': None,
            'total_messages': 0,
            'total_calls': 0,
            'Call History': None
        }

    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    messages_url = "https://api.openphone.com/v1/messages"
    calls_url = "https://api.openphone.com/v1/calls"

    try:
        response_data = rate_limited_request(phone_numbers_url, headers, {})
        phone_number_ids = [pn.get('id') for pn in response_data.get('data', [])] if response_data else []
    except Exception as e:
        # Handle or log the error as needed
        raise Exception(f"Failed to fetch phone number IDs: {e}")

    if not phone_number_ids:
        return {
            'status': "No Communications",
            'last_date': None,
            'total_messages': 0,
            'total_calls': 0,
            'Call History': None
        }

    latest_datetime = None
    total_messages = 0
    total_calls = 0

    for phone_number_id in phone_number_ids:
        params = {
            "phoneNumberId": phone_number_id,
            "participants": [formatted_phone],
            "maxResults": 50
        }

        # Fetch Messages
        try:
            messages_response = rate_limited_request(messages_url, headers, params)
            if messages_response:
                total_messages += len(messages_response.get('data', []))
        except Exception as e:
            # Handle or log the error as needed
            pass  # Continue processing even if there's an error

        # Fetch Calls
        try:
            calls_response = rate_limited_request(calls_url, headers, params)
            if calls_response:
                calls = calls_response.get('data', [])
                total_calls += len(calls)
                for call in calls:
                    call_time = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00'))
                    if not latest_datetime or call_time > latest_datetime:
                        latest_datetime = call_time
        except Exception as e:
            # Handle or log the error as needed
            pass  # Continue processing even if there's an error

    status = "No Communications" if not latest_datetime else "Active"
    call_history_link = generate_call_history_link(phone_number)

    return {
        'status': status,
        'last_date': latest_datetime.strftime("%Y-%m-%d %H:%M:%S") if latest_datetime else None,
        'total_messages': total_messages,
        'total_calls': total_calls,
        'Call History': call_history_link  # Include the call history link
    }

# Function to get call history data
def get_call_history_data(phone_number, headers):
    formatted_phone = format_phone_number(phone_number)
    if not formatted_phone:
        return pd.DataFrame()

    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    calls_url = "https://api.openphone.com/v1/calls"

    try:
        response_data = rate_limited_request(phone_numbers_url, headers, {})
        phone_number_ids = [pn.get('id') for pn in response_data.get('data', [])] if response_data else []
    except Exception as e:
        # Handle or log the error as needed
        raise Exception(f"Failed to fetch phone number IDs: {e}")

    if not phone_number_ids:
        return pd.DataFrame()

    all_calls = []

    for phone_number_id in phone_number_ids:
        params = {
            "phoneNumberId": phone_number_id,
            "participants": [formatted_phone],
            "maxResults": 50  # Adjust as needed
        }

        try:
            calls_response = rate_limited_request(calls_url, headers, params)
            if calls_response:
                calls = calls_response.get('data', [])
                for call in calls:
                    call_info = {
                        'Date': call['createdAt'],
                        'From': call['from']['phone'] if 'from' in call and 'phone' in call['from'] else None,
                        'To': call['to']['phone'] if 'to' in call and 'phone' in call['to'] else None,
                        'Direction': call['direction'],
                        'Duration (s)': call.get('duration', 0),
                        'Status': call['status'],
                        # Add other call details as needed
                    }
                    all_calls.append(call_info)
        except Exception as e:
            # Handle or log the error as needed
            pass  # Continue processing even if there's an error

    if all_calls:
        df_calls = pd.DataFrame(all_calls)
        df_calls['Date'] = pd.to_datetime(df_calls['Date']).dt.strftime('%Y-%m-%d %H:%M:%S')
        return df_calls.sort_values('Date', ascending=False)
    else:
        return pd.DataFrame()
