import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

def run_openphone_tab():
    """Display OpenPhone statistics for the company owner."""
    st.header("OpenPhone Effectiveness Dashboard")
    
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

    # Filters
    st.subheader("Filters")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=pd.to_datetime('today').date())
    with col2:
        end_date = st.date_input("End Date", value=pd.to_datetime('today').date())

    if start_date > end_date:
        st.error("Error: Start date must be before end date.")
        return

    # Filter the data by date
    filtered_data = openphone_data[
        (openphone_data['createdAtPT'].dt.date >= start_date) &
        (openphone_data['createdAtPT'].dt.date <= end_date)
    ]

    # Calls vs Messages Stats
    calls = filtered_data[filtered_data['type'] == 'call']
    messages = filtered_data[filtered_data['type'] == 'message']
    answered_calls = calls[calls['status'] == 'completed']
    missed_calls = calls[calls['status'].isin(['missed', 'no-answer'])]

    # Effectiveness Stats
    total_calls = len(calls)
    total_messages = len(messages)
    answered_calls_count = len(answered_calls)
    missed_calls_count = len(missed_calls)
    calls_after_messages = answered_calls.merge(
        messages[['to', 'createdAtPT']],
        on='to',
        suffixes=('_call', '_message')
    )
    calls_after_messages = calls_after_messages[
        calls_after_messages['createdAtPT_message'] < calls_after_messages['createdAtPT_call']
    ]

    # Display Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Calls", total_calls)
    with col2:
        st.metric("Total Messages", total_messages)
    with col3:
        st.metric("Answered Calls", answered_calls_count)
    with col4:
        st.metric("Missed Calls", missed_calls_count)

    # Calls and Messages Over Time
    st.subheader("Calls and Messages Over Time")
    filtered_data['hour'] = filtered_data['createdAtPT'].dt.hour
    hourly_stats = filtered_data.groupby(['hour', 'type']).size().reset_index(name='count')
    fig = px.bar(hourly_stats, x='hour', y='count', color='type', barmode='group', title='Communication by Hour')
    st.plotly_chart(fig)

    # Agent Performance
    st.subheader("Agent Performance")
    agent_stats = filtered_data.groupby(['userId', 'type']).size().reset_index(name='count')
    fig = px.bar(agent_stats, x='userId', y='count', color='type', barmode='group', title='Agent Performance')
    st.plotly_chart(fig)

    # Calls After Text Messages
    st.subheader("Calls Effectiveness After Messages")
    st.metric("Calls After Text Messages", len(calls_after_messages))

    # Answered Calls by Hour
    st.subheader("Best Time to Call")
    answered_calls['hour'] = answered_calls['answeredAtPT'].dt.hour
    best_time_to_call = answered_calls.groupby('hour').size().reset_index(name='answered_calls')
    fig = px.bar(best_time_to_call, x='hour', y='answered_calls', title='Answered Calls by Hour')
    st.plotly_chart(fig)

    st.success("Dashboard Ready! Explore the insights.")
