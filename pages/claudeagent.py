import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import time
import json

# Configuration and Settings
st.set_page_config(page_title="OpenPhone Dashboard", layout="wide")

# Constants
OPENPHONE_API_KEY = st.secrets["OPENPHONE_API_KEY"]

def rate_limited_request(url, headers, params=None):
    """Make API request with rate limiting"""
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 429:  # Rate limit hit
            time.sleep(60)  # Wait for 60 seconds
            response = requests.get(url, headers=headers, params=params)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        st.error(f"API Error: {str(e)}")
        return None

def get_workspace_phone_numbers():
    """Fetch all phone numbers from the workspace"""
    url = "https://api.openphone.com/v1/phone-numbers"
    headers = {
        "Authorization": f"Bearer {OPENPHONE_API_KEY}",
        "Content-Type": "application/json"
    }
    data = rate_limited_request(url, headers)
    return data.get("data", []) if data else []

def get_workspace_contacts():
    """Fetch all contacts from the workspace"""
    url = "https://api.openphone.com/v1/contacts"
    headers = {
        "Authorization": f"Bearer {OPENPHONE_API_KEY}",
        "Content-Type": "application/json"
    }
    data = rate_limited_request(url, headers)
    return data.get("data", []) if data else []

def fetch_calls(phone_number_id):
    """Fetch calls for a specific phone number"""
    url = "https://api.openphone.com/v1/calls"
    headers = {
        "Authorization": f"Bearer {OPENPHONE_API_KEY}",
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
    url = "https://api.openphone.com/v1/messages"
    headers = {
        "Authorization": f"Bearer {OPENPHONE_API_KEY}",
        "Content-Type": "application/json"
    }
    params = {
        "phoneNumberId": phone_number_id,
        "maxResults": 100
    }
    resp = rate_limited_request(url, headers, params=params)
    return resp.get("data", []) if resp else []

def get_contact_name(phone_number, contacts):
    """Get contact name from phone number"""
    for contact in contacts:
        for number in contact.get("phoneNumbers", []):
            if number.get("phoneNumber") == phone_number:
                return f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
    return "Unknown"

def debug_participants(phone_number_id):
    """Debug function to show all participants for a phone number"""
    st.subheader("🔍 Debug Participants Information")
    
    # Store all participants
    participants_data = {
        "calls": [],
        "messages": [],
        "contacts": []
    }

    # 1. Debug API Headers
    st.write("🔑 API Configuration:")
    headers = {
        "Authorization": f"Bearer {OPENPHONE_API_KEY}",
        "Content-Type": "application/json"
    }
    st.json(headers)

    # 2. Debug Phone Number Details
    st.write("\n📱 Phone Number Details:")
    phone_url = f"https://api.openphone.com/v1/phone-numbers/{phone_number_id}"
    phone_response = requests.get(phone_url, headers=headers)
    st.write(f"Phone Number API Status: {phone_response.status_code}")
    if phone_response.status_code == 200:
        st.json(phone_response.json())

    # 3. Debug Calls
    st.write("\n📞 Calls Data:")
    calls_url = f"https://api.openphone.com/v1/calls"
    calls_params = {
        "phoneNumberId": phone_number_id,
        "maxResults": 100
    }
    calls_response = requests.get(calls_url, headers=headers, params=calls_params)
    st.write(f"Calls API Status: {calls_response.status_code}")
    
    if calls_response.status_code == 200:
        calls_data = calls_response.json()
        st.json(calls_data)
        
        # Extract participants from calls
        for call in calls_data.get('data', []):
            if call.get('from'):
                participants_data['calls'].append({
                    'number': call['from'],
                    'type': 'from',
                    'timestamp': call.get('createdAt'),
                    'duration': call.get('duration')
                })
            if call.get('to'):
                participants_data['calls'].append({
                    'number': call['to'],
                    'type': 'to',
                    'timestamp': call.get('createdAt'),
                    'duration': call.get('duration')
                })

    # 4. Debug Messages
    st.write("\n💬 Messages Data:")
    messages_url = f"https://api.openphone.com/v1/messages"
    messages_params = {
        "phoneNumberId": phone_number_id,
        "maxResults": 100
    }
    messages_response = requests.get(messages_url, headers=headers, params=messages_params)
    st.write(f"Messages API Status: {messages_response.status_code}")
    
    if messages_response.status_code == 200:
        messages_data = messages_response.json()
        st.json(messages_data)
        
        # Extract participants from messages
        for message in messages_data.get('data', []):
            if message.get('from', {}).get('phoneNumber'):
                participants_data['messages'].append({
                    'number': message['from']['phoneNumber'],
                    'type': 'from',
                    'timestamp': message.get('createdAt'),
                    'content': message.get('content', '')[:50]
                })
            for to in message.get('to', []):
                if to.get('phoneNumber'):
                    participants_data['messages'].append({
                        'number': to['phoneNumber'],
                        'type': 'to',
                        'timestamp': message.get('createdAt'),
                        'content': message.get('content', '')[:50]
                    })

    # 5. Debug Contacts
    st.write("\n👥 Contacts Data:")
    contacts_url = "https://api.openphone.com/v1/contacts"
    contacts_response = requests.get(contacts_url, headers=headers)
    st.write(f"Contacts API Status: {contacts_response.status_code}")
    
    if contacts_response.status_code == 200:
        contacts_data = contacts_response.json()
        st.json(contacts_data)
        
        # Extract contacts information
        for contact in contacts_data.get('data', []):
            for phone in contact.get('phoneNumbers', []):
                participants_data['contacts'].append({
                    'number': phone.get('phoneNumber'),
                    'name': f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip(),
                    'email': contact.get('email', '')
                })

    # 6. Display Participants Summary
    st.write("\n📊 Participants Summary:")
    
    # Unique participants from calls
    call_participants = set(p['number'] for p in participants_data['calls'])
    st.write(f"\nUnique Call Participants ({len(call_participants)}):")
    for number in call_participants:
        st.write(f"- {number}")

    # Unique participants from messages
    message_participants = set(p['number'] for p in participants_data['messages'])
    st.write(f"\nUnique Message Participants ({len(message_participants)}):")
    for number in message_participants:
        st.write(f"- {number}")

    # All unique participants
    all_participants = call_participants.union(message_participants)
    st.write(f"\nTotal Unique Participants ({len(all_participants)}):")
    for number in all_participants:
        # Try to find contact name
        contact_name = next((c['name'] for c in participants_data['contacts'] 
                           if c['number'] == number), 'Unknown')
        st.write(f"- {number} ({contact_name})")

    # 7. Create Downloadable CSV
    participant_records = []
    for number in all_participants:
        contact_name = next((c['name'] for c in participants_data['contacts'] 
                           if c['number'] == number), 'Unknown')
        call_count = sum(1 for p in participants_data['calls'] if p['number'] == number)
        message_count = sum(1 for p in participants_data['messages'] if p['number'] == number)
        
        participant_records.append({
            'Phone Number': number,
            'Contact Name': contact_name,
            'Call Count': call_count,
            'Message Count': message_count
        })

    if participant_records:
        df = pd.DataFrame(participant_records)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Participants CSV",
            data=csv,
            file_name=f'participants_{phone_number_id}.csv',
            mime='text/csv'
        )

def analyze_communication_patterns(phone_number_id):
    """Analyze communication patterns for the phone number"""
    st.subheader("📊 Communication Analysis")
    
    calls = fetch_calls(phone_number_id)
    messages = fetch_messages(phone_number_id)
    
    # Time-based analysis
    call_times = [datetime.fromtimestamp(call.get("createdAt", 0)) for call in calls]
    message_times = [datetime.fromtimestamp(msg.get("createdAt", 0)) for msg in messages]
    
    if call_times or message_times:
        # Create time-based statistics
        df_times = pd.DataFrame({
            'timestamp': call_times + message_times,
            'type': ['call'] * len(call_times) + ['message'] * len(message_times)
        })
        
        # Display hourly distribution
        st.write("Hourly Distribution")
        hourly_dist = df_times['timestamp'].dt.hour.value_counts().sort_index()
        st.bar_chart(hourly_dist)
        
        # Display weekly distribution
        st.write("Weekly Distribution")
        weekly_dist = df_times['timestamp'].dt.day_name().value_counts()
        st.bar_chart(weekly_dist)

def main():
    st.title("OpenPhone Dashboard")

    # Get all phone numbers
    phone_numbers = get_workspace_phone_numbers()
    
    # Create sidebar for phone number selection
    st.sidebar.title("Select Phone Number")
    
    if not phone_numbers:
        st.sidebar.error("No phone numbers found")
        return

    # Create phone number selection
    phone_options = {f"{pn.get('phoneNumber', 'Unknown')}: {pn.get('id', 'Unknown')}": pn.get('id') 
                    for pn in phone_numbers}
    selected_phone = st.sidebar.selectbox(
        "Choose a phone number",
        options=list(phone_options.keys())
    )
    
    phone_number_id = phone_options.get(selected_phone)

    if phone_number_id:
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("Debug Participants"):
                debug_participants(phone_number_id)

        # Display contacts
        st.subheader("📋 Contacts")
        contacts = get_workspace_contacts()
        if contacts:
            st.write(f"Found {len(contacts)} contacts")
            # Display contacts in a table
            contact_data = []
            for contact in contacts:
                contact_data.append({
                    'Name': f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip(),
                    'Phone': ', '.join([p.get('phoneNumber', '') for p in contact.get('phoneNumbers', [])]),
                    'Email': contact.get('email', '')
                })
            st.dataframe(pd.DataFrame(contact_data))
        else:
            st.write("No contacts found")

        # Display calls
        st.subheader("📞 Last 100 Calls")
        calls = fetch_calls(phone_number_id)
        if calls:
            call_data = []
            for call in calls:
                call_data.append({
                    'From': call.get('from', ''),
                    'To': call.get('to', ''),
                    'Duration': call.get('duration', 0),
                    'Time': datetime.fromtimestamp(call.get('createdAt', 0))
                })
            st.dataframe(pd.DataFrame(call_data))
        else:
            st.write("No calls found")

        # Display messages
        st.subheader("💬 Last 100 Messages")
        messages = fetch_messages(phone_number_id)
        if messages:
            message_data = []
            for message in messages:
                message_data.append({
                    'From': message.get('from', {}).get('phoneNumber', ''),
                    'To': ', '.join([to.get('phoneNumber', '') for to in message.get('to', [])]),
                    'Content': message.get('content', '')[:50],
                    'Time': datetime.fromtimestamp(message.get('createdAt', 0))
                })
            st.dataframe(pd.DataFrame(message_data))
        else:
            st.write("No messages found")

    st.sidebar.button("Back to Main")

if __name__ == "__main__":
    main()
