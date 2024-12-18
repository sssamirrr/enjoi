import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import plotly.express as px

def rate_limited_request(url, headers, params=None, request_type='get'):
    """Make an API request while respecting rate limits."""
    time.sleep(1 / 5)  # 5 requests per second max
    try:
        if request_type == 'get':
            response = requests.get(url, headers=headers, params=params)
        else:
            response = requests.post(url, headers=headers, json=params)
            
        if response.status_code == 200:
            return response.json()
        else:
            st.warning(f"API Error: {response.status_code}")
            return None
    except Exception as e:
        st.warning(f"Request Error: {str(e)}")
        return None

def get_all_phone_number_ids(headers):
    """Retrieve all phoneNumberIds associated with your OpenPhone account."""
    phone_numbers_url = "https://api.openphone.com/v1/phone-numbers"
    response_data = rate_limited_request(phone_numbers_url, headers, {})
    if response_data and 'data' in response_data:
        return [pn.get('id') for pn in response_data['data']]
    return []

def get_communication_stats(headers, start_date=None, end_date=None):
    """Get communication statistics for the specified date range."""
    phone_number_ids = get_all_phone_number_ids(headers)
    
    stats = {
        'total_calls': 0,
        'total_messages': 0,
        'answered_calls': 0,
        'missed_calls': 0,
        'agents_activity': {}
    }
    
    for phone_id in phone_number_ids:
        # Get calls
        calls_url = "https://api.openphone.com/v1/calls"
        calls_params = {"phoneNumberId": phone_id}
        calls_data = rate_limited_request(calls_url, headers, calls_params)
        
        if calls_data and 'data' in calls_data:
            for call in calls_data['data']:
                call_date = datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00'))
                if (not start_date or call_date.date() >= start_date) and \
                   (not end_date or call_date.date() <= end_date):
                    stats['total_calls'] += 1
                    if call.get('status') == 'completed':
                        stats['answered_calls'] += 1
                    elif call.get('status') in ['missed', 'no-answer']:
                        stats['missed_calls'] += 1
                        
                    # Track agent activity
                    agent = call.get('user', {}).get('name', 'Unknown')
                    if agent not in stats['agents_activity']:
                        stats['agents_activity'][agent] = {'calls': 0, 'messages': 0}
                    stats['agents_activity'][agent]['calls'] += 1
        
        # Get messages
        messages_url = "https://api.openphone.com/v1/messages"
        messages_params = {"phoneNumberId": phone_id}
        messages_data = rate_limited_request(messages_url, headers, messages_params)
        
        if messages_data and 'data' in messages_data:
            for message in messages_data['data']:
                message_date = datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00'))
                if (not start_date or message_date.date() >= start_date) and \
                   (not end_date or message_date.date() <= end_date):
                    stats['total_messages'] += 1
                    
                    # Track agent activity
                    agent = message.get('user', {}).get('name', 'Unknown')
                    if agent not in stats['agents_activity']:
                        stats['agents_activity'][agent] = {'calls': 0, 'messages': 0}
                    stats['agents_activity'][agent]['messages'] += 1
    
    return stats

def run_openphone_tab():
    """Main function to run the OpenPhone statistics tab."""
    st.header("OpenPhone Statistics")
    
    # Date range selector
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=pd.to_datetime('today').date())
    with col2:
        end_date = st.date_input("End Date", value=pd.to_datetime('today').date())

    if start_date > end_date:
        st.error("Error: Start date must be before end date")
        return

    # Initialize headers with API key from secrets
    headers = {
        "Authorization": st.secrets["OPENPHONE_API_KEY"],
        "Content-Type": "application/json"
    }

    if st.button("Fetch OpenPhone Statistics"):
        try:
            with st.spinner("Fetching statistics..."):
                stats = get_communication_stats(headers, start_date, end_date)
                
                # Display metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Calls", stats['total_calls'])
                with col2:
                    st.metric("Total Messages", stats['total_messages'])
                with col3:
                    st.metric("Answered Calls", stats['answered_calls'])
                with col4:
                    st.metric("Missed Calls", stats['missed_calls'])
                
                # Display agent activity
                st.subheader("Agent Activity")
                agent_df = pd.DataFrame.from_dict(
                    stats['agents_activity'],
                    orient='index'
                ).reset_index()
                agent_df.columns = ['Agent', 'Calls', 'Messages']
                
                # Create bar chart
                fig = px.bar(
                    agent_df,
                    x='Agent',
                    y=['Calls', 'Messages'],
                    title='Agent Activity',
                    barmode='group'
                )
                st.plotly_chart(fig)
                
                # Display detailed data
                st.subheader("Detailed Agent Statistics")
                st.dataframe(agent_df)

        except Exception as e:
            st.error(f"Error fetching OpenPhone statistics: {str(e)}")
