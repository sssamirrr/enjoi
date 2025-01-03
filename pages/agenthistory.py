import requests
import time
from datetime import datetime, timedelta

############################
# 1) OpenPhone API Key     #
############################
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

def get_headers():
    return {
        "Authorization": OPENPHONE_API_KEY,  # Not using "Bearer " prefix here
        "Content-Type": "application/json"
    }

def fetch_calls(phone_number_id, start_date, end_date, max_per_page=100):
    """
    Fetch all calls for 'phone_number_id' between start_date and end_date.
    This function paginates using nextPageToken if there are more results than 'max_per_page'.
    """
    url = "https://api.openphone.com/v1/calls"
    all_calls = []
    next_page_token = None

    while True:
        # Rate limit: ~1/5 second per request
        time.sleep(0.2)

        params = {
            "phoneNumberId": phone_number_id,
            "createdAfter": start_date.isoformat(), 
            "createdBefore": end_date.isoformat(),
            "maxResults": max_per_page
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        # Make the request
        resp = requests.get(url, headers=get_headers(), params=params)
        if resp.status_code != 200:
            print(f"Error fetching calls: {resp.status_code} {resp.text}")
            break

        data = resp.json()
        if "data" not in data:
            break

        # Accumulate calls
        all_calls.extend(data["data"])

        # Check if there is another page
        next_page_token = data.get("nextPageToken")
        if not next_page_token:
            break

    return all_calls

if __name__ == "__main__":
    # Example: last 3 months
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=90)

    # Replace with your actual OpenPhone number ID (e.g., "PNabcdef123456")
    phone_number_id = "PNxxxxxx"

    calls = fetch_calls(phone_number_id, start_date, end_date)
    print(f"Fetched {len(calls)} calls.")
    for c in calls:
        print(
            f"Call ID: {c.get('id')}, "
            f"Direction: {c.get('direction')}, "
            f"Created At: {c.get('createdAt')}"
        )
