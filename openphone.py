import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

def run_openphone_tab():
    st.header("Enhanced OpenPhone Operations Dashboard")

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

    # Call and Message Conversion
    bookings = filtered_data[filtered_data['status'] == 'booked']
    total_bookings = len(bookings)
    call_conversion_rate = (len(calls[calls['status'] == 'booked']) / len(calls) * 100) if len(calls) > 0 else 0
    message_conversion_rate = (len(messages[messages['status'] == 'booked']) / len(messages) * 100) if len(messages) > 0 else 0

    # Agent Performance with Bookings
    agent_bookings = bookings.groupby('userId').size().reset_index(name='total_bookings')
    agent_performance = calls.groupby('userId').size().reset_index(name='total_calls')
    agent_performance = pd.merge(agent_performance, agent_bookings, on='userId', how='outer').fillna(0)
    agent_performance['booking_rate'] = (agent_performance['total_bookings'] / agent_performance['total_calls'] * 100).fillna(0)

    # Outbound Call Success Rate
    st.subheader("Outbound Call Success Rate")
    min_success_duration = st.slider(
        "Minimum Call Duration (seconds) to Count as Success",
        min_value=0,
        max_value=int(calls['duration'].max()) if 'duration' in calls.columns and not calls['duration'].isnull().all() else 60,
        value=30
    )

    outbound_calls = calls[calls['direction'] == 'outgoing']
    successful_outbound_calls = outbound_calls[outbound_calls['duration'] >= min_success_duration]

    success_rate = (
        len(successful_outbound_calls) / len(outbound_calls) * 100 if len(outbound_calls) > 0 else 0
    )

    # Success Rate per Agent
    agent_success = successful_outbound_calls.groupby('userId').size().reset_index(name='successful_calls')
    agent_outbound = outbound_calls.groupby('userId').size().reset_index(name='total_outbound_calls')
    agent_success_rate = pd.merge(agent_outbound, agent_success, on='userId', how='outer').fillna(0)
    agent_success_rate['success_rate'] = (
        agent_success_rate['successful_calls'] / agent_success_rate['total_outbound_calls'] * 100
    ).fillna(0)

    # Metrics
    st.subheader("Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Bookings", total_bookings)
    with col2:
        st.metric("Call Conversion Rate", f"{call_conversion_rate:.2f}%")
    with col3:
        st.metric("Message Conversion Rate", f"{message_conversion_rate:.2f}%")
    with col4:
        st.metric("Outbound Call Success Rate", f"{success_rate:.2f}%")

    # Hourly Trends
    st.subheader("Hourly Trends")
    calls['hour'] = calls['createdAtPT'].dt.hour
    hourly_stats = calls.groupby(['hour', 'direction']).size().reset_index(name='count')
    fig = px.bar(hourly_stats, x='hour', y='count', color='direction', barmode='group', title='Call Volume by Hour')
    st.plotly_chart(fig)

    # Call Duration Analysis
    st.subheader("Call Duration Analysis")
    if 'duration' in calls.columns and not calls['duration'].isnull().all():
        long_calls = calls[calls['duration'] >= calls['duration'].mean()]
        long_call_times = long_calls.groupby('hour').size().reset_index(name='count')
        fig = px.bar(long_call_times, x='hour', y='count', title='Long Calls by Hour')
        st.plotly_chart(fig)

        # Heatmap for Call Duration
        calls['day'] = calls['createdAtPT'].dt.day_name()
        duration_heatmap_data = calls.groupby(['day', 'hour'])['duration'].mean().reset_index()
        duration_heatmap_pivot = duration_heatmap_data.pivot(index='day', columns='hour', values='duration').fillna(0)
        fig = px.imshow(
            duration_heatmap_pivot,
            title="Heatmap of Average Call Duration by Day and Hour",
            labels=dict(x="Hour", y="Day", color="Duration (seconds)"),
        )
        st.plotly_chart(fig)

    # Incoming Message Analysis
    st.subheader("Incoming Messages by Hour")
    messages['hour'] = messages['createdAtPT'].dt.hour
    incoming_messages = messages[messages['direction'] == 'incoming']
    incoming_message_times = incoming_messages.groupby('hour').size().reset_index(name='count')
    fig = px.bar(incoming_message_times, x='hour', y='count', title='Incoming Messages by Hour')
    st.plotly_chart(fig)

    # Agent Performance
    st.subheader("Agent Performance")
    fig = px.bar(
        agent_performance,
        x='userId',
        y=['total_calls', 'total_bookings'],
        title="Agent Performance: Calls and Bookings",
        barmode='group',
    )
    st.plotly_chart(fig)
    st.dataframe(agent_performance.rename(columns={
        'userId': 'Agent',
        'total_calls': 'Total Calls',
        'total_bookings': 'Total Bookings',
        'booking_rate': 'Booking Rate (%)'
    }))

    # Agent Outbound Success Rate
    st.subheader("Agent Outbound Success Rate")
    fig = px.bar(
        agent_success_rate,
        x='userId',
        y=['total_outbound_calls', 'successful_calls'],
        title="Agent Outbound Success Rate",
        barmode='group',
    )
    st.plotly_chart(fig)
    st.dataframe(agent_success_rate.rename(columns={
        'userId': 'Agent',
        'total_outbound_calls': 'Total Outbound Calls',
        'successful_calls': 'Successful Calls',
        'success_rate': 'Success Rate (%)'
    }))

    # Heatmap of Call Volume by Time
    st.subheader("Call Volume Heatmap")
    calls['day'] = calls['createdAtPT'].dt.day_name()
    heatmap_data = calls.groupby(['day', 'hour']).size().reset_index(name='count')
    heatmap_pivot = heatmap_data.pivot(index='day', columns='hour', values='count').fillna(0)
    fig = px.imshow(
        heatmap_pivot,
        title="Heatmap of Call Volume by Day and Hour",
        labels=dict(x="Hour", y="Day", color="Volume"),
    )
    st.plotly_chart(fig)

    st.success("Enhanced Dashboard Ready!")
