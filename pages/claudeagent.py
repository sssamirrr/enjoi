import streamlit as st
import pandas as pd
import time
import requests
from datetime import datetime

# Configure the page
st.set_page_config(page_title="OpenPhone History", layout="wide")

# Your OpenPhone API Key
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"

def rate_limited_request(url, headers, params=None):
    """Make an API request while respecting rate limits"""
    if params is None:
        params = {}
    time.sleep(1 / 5)  # Rate limit to 5 requests per second
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            return resp.json()
        else:
            st.warning(f"API Error: {resp.status_code}")
            st.warning(f"Response: {resp.text}")
    except Exception as e:
        st.warning(f"Exception: {str(e)}")
    return None

def get_workspace_contacts():
    """Fetch all contacts from the workspace"""
    url = "https://api.openphone.com/v1/workspaces/contacts"
    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }
    data = rate_limited_request(url, headers)
    return data.get("data", []) if data else []

def get_phone_numbers():
    """Fetch all phone numbers from OpenPhone account"""
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }
    data = rate_limited_request(url, headers)
    if not data or "data" not in data:
        return []

    results = []
    for item in data["data"]:
        pid = item.get("id")
        pnum = item.get("phoneNumber") or "No Phone#"
        results.append({
            "phoneNumberId": pid,
            "phoneNumber": pnum
        })
    return results

def fetch_calls(phone_number_id):
    """Fetch calls for a specific phone number"""
    url = "https://api.openphone.com/v1/workspaces/calls"
    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }
    params = {
        "phoneNumberId": phone_number_id,
        "maxResults": 100
    }
    resp = rate_limited_request(url, headers, params=params)
    return resp.get("data", []) if resp else []

def fetch_messages(phone_number_id):
    """Fetch messages for a specific phone number"""
    url = "https://api.openphone.com/v1/workspaces/messages"
    headers = {
        "Authorization": OPENPHONE_API_KEY,
        "Content-Type": "application/json"
    }
    params = {
        "phoneNumberId": phone_number_id,
        "maxResults": 100
    }
    resp = rate_limited_request(url, headers, params=params)
    return resp.get("data", []) if resp else []

def get_contact_name(phone_number, contacts):
    """Look up contact name from phone number"""
    for contact in contacts:
        for number in contact.get("phoneNumbers", []):
            if number.get("phoneNumber") == phone_number:
                return f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
    return phone_number

def format_phone_number(phone):
    """Format phone number for better display"""
    if phone and len(phone) == 12 and phone.startswith('+1'):
        return f"{phone[2:5]}-{phone[5:8]}-{phone[8:]}"
    return phone

def main():
    st.title("OpenPhone: List & Last 100 Contacts")

    # Get phone_number_id from query params if it exists
    phone_number_id = st.query_params.get("phoneNumberId", None)

    # Fetch contacts once to use for both calls and messages
    contacts = get_workspace_contacts()

    if phone_number_id:
        # Detail View
        st.subheader(f"Detail for phoneNumberId = {phone_number_id}")
        
        # Validate phoneNumberId format
        if not phone_number_id.startswith("PN"):
            st.error("Invalid phoneNumberId. Must match '^PN(.*)'.")
            st.markdown("[Back to Main](?)")
            return

        # Fetch and display history
        with st.spinner("Fetching history..."):
            # Fetch calls
            calls_data = fetch_calls(phone_number_id)
            st.markdown("### Last 100 Calls")
            if calls_data:
                calls_df = pd.DataFrame([
                    {
                        "Date": datetime.fromtimestamp(c.get("createdAt", 0)).strftime('%Y-%m-%d %H:%M:%S'),
                        "Direction": c.get("direction", "").title(),
                        "Duration (sec)": c.get("duration", 0),
                        "Status": c.get("status", "").title(),
                        "From": get_contact_name(c.get("from"), contacts),
                        "To": get_contact_name(c.get("to"), contacts),
                        "Recording": "Yes" if c.get("recordingUrl") else "No"
                    }
                    for c in calls_data
                ])
                st.dataframe(calls_df, use_container_width=True)
                
                # Download button for calls
                csv = calls_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Calls CSV",
                    data=csv,
                    file_name=f'calls_{phone_number_id}.csv',
                    mime='text/csv'
                )
            else:
                st.info("No calls found.")

            # Fetch messages
            messages_data = fetch_messages(phone_number_id)
            st.markdown("### Last 100 Messages")
            if messages_data:
                messages_df = pd.DataFrame([
                    {
                        "Date": datetime.fromtimestamp(m.get("createdAt", 0)).strftime('%Y-%m-%d %H:%M:%S'),
                        "Direction": m.get("direction", "").title(),
                        "Content": m.get("content", ""),
                        "From": get_contact_name(m.get("from", {}).get("phoneNumber", ""), contacts),
                        "To": ", ".join([get_contact_name(t.get("phoneNumber", ""), contacts) for t in m.get("to", [])])
                    }
                    for m in messages_data
                ])
                st.dataframe(messages_df, use_container_width=True)
                
                # Download button for messages
                csv = messages_df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Download Messages CSV",
                    data=csv,
                    file_name=f'messages_{phone_number_id}.csv',
                    mime='text/csv'
                )
            else:
                st.info("No messages found.")

        st.markdown("[Back to Main](?)")

    else:
        # Main List View
        st.header("All Phone Numbers")
        
        phone_nums = get_phone_numbers()
        if not phone_nums:
            st.warning("No phone numbers found.")
            return

        # Create table with links
        table_data = []
        for pn in phone_nums:
            pid = pn["phoneNumberId"]
            pnum = format_phone_number(pn["phoneNumber"])
            if pid and pid.startswith("PN"):
                link = f'<a href="?phoneNumberId={pid}" target="_self">View History</a>'
            else:
                link = "Invalid ID"
            
            table_data.append({
                "Phone Number": pnum,
                "ID": pid,
                "Action": link
            })

        df = pd.DataFrame(table_data)
        st.markdown(df.to_html(escape=False, index=False), unsafe_allow_html=True)

if __name__ == "__main__":
    main()
