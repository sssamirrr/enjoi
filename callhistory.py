import streamlit as st
import requests
import time
from datetime import datetime, timedelta
import phonenumbers
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import calendar

# OpenPhone API Credentials
OPENPHONE_API_KEY = "j4sjHuvWO94IZWurOUca6Aebhl6lG6Z7"
HEADERS = {
    "Authorization": OPENPHONE_API_KEY,
    "Content-Type": "application/json"
}

# [Keep all your existing functions for API calls]

def create_communication_dataframe(call_history, message_history):
    """Create a DataFrame from call and message history."""
    calls_data = []
    for call in call_history:
        calls_data.append({
            'timestamp': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')),
            'type': 'Call',
            'direction': call.get('direction', 'unknown'),
            'duration': call.get('duration', 0),
            'status': call.get('status', 'unknown'),
            'hour': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')).hour,
            'day': datetime.fromisoformat(call['createdAt'].replace('Z', '+00:00')).strftime('%A')
        })
    
    messages_data = []
    for message in message_history:
        messages_data.append({
            'timestamp': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')),
            'type': 'Message',
            'direction': message.get('direction', 'unknown'),
            'content': message.get('content', ''),
            'status': message.get('status', 'unknown'),
            'hour': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')).hour,
            'day': datetime.fromisoformat(message['createdAt'].replace('Z', '+00:00')).strftime('%A')
        })
    
    df = pd.DataFrame(calls_data + messages_data)
    df = df.sort_values('timestamp', ascending=False)
    return df

def display_analytics(df):
    """Display analytics dashboard."""
    st.header("Communication Analytics")
    
    # Create columns for key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_calls = len(df[df['type'] == 'Call'])
        st.metric("Total Calls", total_calls)
    
    with col2:
        total_messages = len(df[df['type'] == 'Message'])
        st.metric("Total Messages", total_messages)
    
    with col3:
        inbound = len(df[df['direction'] == 'inbound'])
        st.metric("Inbound Communications", inbound)
    
    with col4:
        outbound = len(df[df['direction'] == 'outbound'])
        st.metric("Outbound Communications", outbound)

    # Create heatmap using Plotly
    st.subheader("Communication Heatmap")
    pivot_table = pd.pivot_table(
        df,
        values='timestamp',
        index='day',
        columns='hour',
        aggfunc='count',
        fill_value=0
    )
    
    #
