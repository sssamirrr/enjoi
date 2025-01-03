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
        "Authorization": OPENPHONE_API_KEY,  # Removed 'Bearer'
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
    if all_participants:
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

        df = pd.DataFrame(participant_records)
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Participants CSV",
            data=csv,
            file_name=f'participants_{phone_number_id}.csv',
            mime='text/csv'
        )

# Add to your main function:
def main():
    if phone_number_id:
        col1, col2 = st.columns([1, 5])
        with col1:
            if st.button("Debug Participants"):
                debug_participants(phone_number_id)
