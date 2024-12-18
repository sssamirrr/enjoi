import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

def run_openphone_tab():
    st.header("OpenPhone Operations Dashboard")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload OpenPhone CSV File", type=["csv"])
    if not uploaded_file:
        st.warning("Please upload the OpenPhone CSV file to proceed.")
        return

    # Read the CSV file
    openphone_data = pd.read_csv(uploaded_file)
    openphone_data['createdAtPT'] = pd.to_datetime(openphone_data['createdAtPT'], errors='coerce')
    openphone_data['answeredAtPT'] = pd.to_datetime(openphone_data['answeredAtPT'], errors='coerce')

    # Default filter range
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

    # Filter data by date
    filtered_data = openphone_data[
        (openphone_data['createdAtPT'].dt.date >= start_date) &
        (openphone_data['createdAtPT'].dt.date <= end_date)
    ]

    # Calls and Messages
    calls = filtered_data[filtered_data['type'] == 'call']
    messages = filtered_data[filtered_data['type'] == 'message']

    # Response Rate Slider
    st.subheader("Filter by Call Duration")
    min_duration = int(calls['duration'].min()) if 'duration' in calls.columns and not calls['duration'].isnull().all() else 0
    max_duration = int(calls['duration'].max()) if 'duration' in calls.columns and not calls['duration'].isnull().all() else 60

    selected_duration = st.slider(
        "Minimum Call Duration (seconds) for Valid Response",
        min_value=min_duration,
        max_value=max_duration,
        value=min_duration,
        step=1
    )

    # Filter calls based on the selected duration
    if 'duration' in calls.columns:
        filtered_calls = calls[calls['duration'] >= selected_duration]
        valid_responses = filtered_calls[filtered_calls['status'] == 'completed']
    else:
        st.warning("Duration data not found. Using all answered calls for response rate calculation.")
        valid_responses = calls[calls['status'] == 'completed']

    # Calculate response rate with filtered calls
    response_rate_filtered = (len(valid_responses) / len(calls) * 100) if len(calls) > 0 else 0

    # Text Message Response Rate
    inbound_messages = messages[messages['direction'] == 'incoming']
    outbound_messages = messages[messages['direction'] == 'outgoing']
    responded_inbound_messages = inbound_messages[inbound_messages['to'].isin(outbound_messages['from'])]
    text_response_rate = (
        len(responded_inbound_messages) / len(inbound_messages) * 100 if len(inbound_messages) > 0 else 0
    )

    # Metrics
    st.subheader("Metrics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Calls", len(calls))
    with col2:
        st.metric("Total Messages", len(messages))
    with col3:
        st.metric("Answer
