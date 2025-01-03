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
BASE_URL = "https://api.openphone.com/v1"
HEADERS = {
    "Authorization": f"Bearer {OPENPHONE_API_KEY}",
    "Content-Type": "application/json"
}

# API Helper Functions
def make_api_request(endpoint, params=None):
    """Generic API request function with error handling and rate limiting"""
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code == 429:  # Rate limit
            st.warning("Rate limit hit. Waiting 60 seconds...")
            time.sleep(60)
            response = requests.get(url, headers=HEADERS, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Request Error: {str(e)}")
        return None

# Data Fetching Functions
def get_phone_numbers():
    """Fetch all phone numbers"""
    response = make_api_request("phone-numbers")
    return response.get("data", []) if response else []

def get_contacts():
    """Fetch all contacts"""
    response = make_api_request("contacts")
    return response.get("data", []) if response else []

def get_calls(phone_number_id):
    """Fetch calls for a specific phone number"""
    params = {"phoneNumberId": phone_number_id, "maxResults": 100}
    response = make_api_request("calls", params)
    return response.get("data", []) if response else []

def get_messages(phone_number_id):
    """Fetch messages for a specific phone number"""
    params = {"phoneNumberId": phone_number_id, "maxResults": 100}
    response = make_api_request("messages", params)
    return response.get("data", []) if response else []

# Data Processing Functions
def process_contact_data(contacts):
    """Process contacts into displayable format"""
    contact_data = []
    for contact in contacts:
        contact_data.append({
            'Name': f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip(),
            'Phone': ', '.join([p.get('phoneNumber', '') for p in contact.get('phoneNumbers', [])]),
            'Email': contact.get('email', ''),
            'Company': contact.get('company', ''),
            'Created': datetime.fromtimestamp(contact.get('createdAt', 0))
        })
    return contact_data

def process_call_data(calls):
    """Process calls into displayable format"""
    call_data = []
    for call in calls:
        call_data.append({
            'From': call.get('from', ''),
            'To': call.get('to', ''),
            'Duration (s)': call.get('duration', 0),
            'Status': call.get('status', ''),
            'Time': datetime.fromtimestamp(call.get('createdAt', 0))
        })
    return call_data

def process_message_data(messages):
    """Process messages into displayable format"""
    message_data = []
    for message in messages:
        message_data.append({
            'From': message.get('from', {}).get('phoneNumber', ''),
            'To': ', '.join([to.get('phoneNumber', '') for to in message.get('to', [])]),
            'Content': message.get('content', '')[:100] + '...' if len(message.get('content', '')) > 100 else message.get('content', ''),
            'Type': message.get('type', ''),
            'Time': datetime.fromtimestamp(message.get('createdAt', 0))
        })
    return message_data

def analyze_participants(phone_number_id):
    """Analyze and display participant information"""
    st.subheader("👥 Participant Analysis")
    
    calls = get_calls(phone_number_id)
    messages = get_messages(phone_number_id)
    contacts = get_contacts()
    
    # Collect unique participants
    participants = set()
    
    # From calls
    for call in calls:
        if call.get('from'): participants.add(call['from'])
        if call.get('to'): participants.add(call['to'])
    
    # From messages
    for message in messages:
        if message.get('from', {}).get('phoneNumber'):
            participants.add(message['from']['phoneNumber'])
        for to in message.get('to', []):
            if to.get('phoneNumber'):
                participants.add(to['phoneNumber'])

    # Create participant analysis
    participant_data = []
    for number in participants:
        # Find matching contact
        contact_name = "Unknown"
        for contact in contacts:
            for phone in contact.get('phoneNumbers', []):
                if phone.get('phoneNumber') == number:
                    contact_name = f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip()
                    break
        
        # Count interactions
        call_count = sum(1 for call in calls if call.get('from') == number or call.get('to') == number)
        message_count = sum(1 for msg in messages 
                          if (msg.get('from', {}).get('phoneNumber') == number 
                              or any(to.get('phoneNumber') == number for to in msg.get('to', []))))
        
        participant_data.append({
            'Phone Number': number,
            'Contact Name': contact_name,
            'Total Calls': call_count,
            'Total Messages': message_count,
            'Total Interactions': call_count + message_count
        })
    
    # Display participant analysis
    if participant_data:
        df = pd.DataFrame(participant_data)
        df = df.sort_values('Total Interactions', ascending=False)
        st.dataframe(df)
        
        # Create downloadable CSV
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Participant Data",
            data=csv,
            file_name=f'participants_{phone_number_id}.csv',
            mime='text/csv'
        )
    else:
        st.write("No participant data found")

# Main Application
def main():
    st.title("📱 OpenPhone Dashboard")
    
    # Sidebar
    st.sidebar.title("Navigation")
    phone_numbers = get_phone_numbers()
    
    if not phone_numbers:
        st.error("No phone numbers found. Please check your API key.")
        return
    
    # Phone number selection
    phone_options = {f"{pn.get('phoneNumber', 'Unknown')}: {pn.get('id', 'Unknown')}": pn.get('id') 
                    for pn in phone_numbers}
    selected_phone = st.sidebar.selectbox(
        "Select Phone Number",
        options=list(phone_options.keys())
    )
    
    phone_number_id = phone_options.get(selected_phone)
    
    if phone_number_id:
        # Add tabs for different views
        tabs = st.tabs(["📞 Calls", "💬 Messages", "👥 Contacts", "📊 Analysis"])
        
        with tabs[0]:
            st.subheader("Recent Calls")
            calls = get_calls(phone_number_id)
            if calls:
                call_df = pd.DataFrame(process_call_data(calls))
                st.dataframe(call_df, use_container_width=True)
            else:
                st.write("No calls found")
        
        with tabs[1]:
            st.subheader("Recent Messages")
            messages = get_messages(phone_number_id)
            if messages:
                message_df = pd.DataFrame(process_message_data(messages))
                st.dataframe(message_df, use_container_width=True)
            else:
                st.write("No messages found")
        
        with tabs[2]:
            st.subheader("Contacts")
            contacts = get_contacts()
            if contacts:
                contact_df = pd.DataFrame(process_contact_data(contacts))
                st.dataframe(contact_df, use_container_width=True)
            else:
                st.write("No contacts found")
        
        with tabs[3]:
            analyze_participants(phone_number_id)

    # Sidebar additional options
    st.sidebar.markdown("---")
    if st.sidebar.button("Refresh Data"):
        st.experimental_rerun()

if __name__ == "__main__":
    main()
