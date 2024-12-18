import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

def run_openphone_tab():
    """Display OpenPhone statistics for monitoring operations."""
    st.header("OpenPhone Operations Dashboard")
    
    # File uploader for openphone.csv
    uploaded_file = st.file_uploader("Upload OpenPhone CSV File", type=["csv"])
    if not uploaded_file:
        st.warning("Please upload the OpenPhone CSV file to proceed.")
        return

    # Read the uploaded CSV
    openphone_data = pd.read_csv(uploaded_file)

    # Convert date columns to datetime
    openphone_data['createdAtPT'] = pd.to_datetime(openphone_data['createdAtPT'], errors='coerce')
    openphone_data['answeredAtPT'] = pd.to_datetime(openphone_data['answeredAtPT'], errors='coerce')

    # Set default filter dates
    min_date = openphone_data['createdAtPT'].min().date()
    max_date = openphone_data['createdAtPT'].max().date()

    # Filters
    st.subheader("Filters")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)

    if start_date > end_date:
        st.error("Error: Start date must be before end date.")
        return

    # Filter the data by date
    filtered_data = openphone_data[
        (openphone_data['createdAtPT'].dt.date >= start_date) &
        (openphone_data['createdAtPT'].dt.date <= end_date)
    ]

    # Calls and Messages Stats
    calls = filtered_data[filtered_data['type'] == 'call']
    messages = filtered_data[filtered_data['type'] == 'message']
    inbound_calls = calls[calls['direction'] == 'incoming']
    outbound_calls = calls[calls['direction'] == 'outgoing']
    answered_calls = calls[calls['status'] == 'completed']
    missed_calls = calls[calls['status'].isin(['missed', 'no-answer'])]

    # Calculate additional stats
    response_rate_calls = (len(answered_calls) / len(calls) * 100) if len(calls) > 0 else 0
    response_rate_messages = (len(messages[messages['status'] == 'received']) / len(messages) * 100) if len(messages) > 0 else 0
    average_response_time = (
        (messages['answeredAtPT'] - messages['createdAtPT']).dt.total_seconds().mean() / 60
        if len(messages['answeredAtPT'].dropna()) > 0 else 0
    )

    # Display Metrics
    st.subheader("Overall Statistics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Calls", len(calls))
    with col2:
        st.metric("Inbound Calls", len(inbound_calls))
    with col3:
        st.metric("Outbound Calls", len(outbound_calls))
    with col4:
        st.metric("Answered Calls", len(answered_calls))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Messages", len(messages))
    with col2:
        st.metric("Missed Calls", len(missed_calls))
    with col3:
        st.metric("Response Rate (Calls)", f"{response_rate_calls:.2f}%")
    with col4:
        st.metric("Response Rate (Messages)", f"{response_rate_messages:.2f}%")

    # Call Effectiveness by Hour
    st.subheader("Call Effectiveness by Hour")
    calls['hour'] = calls['createdAtPT'].dt.hour
    hourly_stats = calls.groupby(['hour', 'direction']).size().reset_index(name='count')
    fig = px.bar(hourly_stats, x='hour', y='count', color='direction', barmode='group', title='Calls by Hour')
    st.plotly_chart(fig)

    # Agent Performance
    st.subheader("Agent Performance")
    
