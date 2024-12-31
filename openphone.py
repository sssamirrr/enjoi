import streamlit as st
import pandas as pd
import plotly.express as px
import pytz
from datetime import datetime

def run_openphone_tab():
    st.header("Enhanced OpenPhone Operations Dashboard (with ET AM/PM & Agent Filter)")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 1. UPLOAD FILE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    uploaded_file = st.file_uploader("Upload OpenPhone CSV File", type=["csv"])
    if not uploaded_file:
        st.warning("Please upload the OpenPhone CSV file to proceed.")
        return

    openphone_data = pd.read_csv(uploaded_file)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 2. TIME ZONE CONVERSION FROM PT -> ET
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    pacific_tz = pytz.timezone("America/Los_Angeles")
    eastern_tz = pytz.timezone("America/New_York")

    openphone_data['createdAtPT'] = pd.to_datetime(openphone_data['createdAtPT'], errors='coerce')
    openphone_data = openphone_data.dropna(subset=['createdAtPT'])  # Ensure no NaT rows

    # Convert createdAtPT -> createdAtET
    openphone_data['createdAtET'] = (
        openphone_data['createdAtPT']
        .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
        .dt.tz_convert(eastern_tz)
    )

    # Convert answeredAtPT -> answeredAtET if needed
    if 'answeredAtPT' in openphone_data.columns:
        openphone_data['answeredAtPT'] = pd.to_datetime(openphone_data['answeredAtPT'], errors='coerce')
        openphone_data['answeredAtET'] = (
            openphone_data['answeredAtPT']
            .dropna()
            .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
            .dt.tz_convert(eastern_tz)
        )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 3. FILTERS (DATE RANGE & AGENTS)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Filters")

    # A) Date Filters based on ET
    min_date = openphone_data['createdAtET'].min().date()
    max_date = openphone_data['createdAtET'].max().date()
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)

    if start_date > end_date:
        st.error("Error: Start date must be before end date.")
        return

    # Filter data by date range
    openphone_data = openphone_data[
        (openphone_data['createdAtET'].dt.date >= start_date) &
        (openphone_data['createdAtET'].dt.date <= end_date)
    ]

    # B) Agent Filter
    if 'userId' not in openphone_data.columns:
        st.error("No 'userId' column found in the dataset.")
        return

    all_agents = sorted(openphone_data['userId'].dropna().unique())
    selected_agents = st.multiselect("Select Agents to Include", all_agents, default=all_agents)

    # Filter data by selected agents
    openphone_data = openphone_data[openphone_data['userId'].isin(selected_agents)]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 4. SPLIT INTO CALLS VS. MESSAGES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    calls = openphone_data[openphone_data['type'] == 'call']
    messages = openphone_data[openphone_data['type'] == 'message']

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 5. CALCULATE BOOKING & CONVERSION RATES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    bookings = openphone_data[openphone_data['status'] == 'booked']
    total_bookings = len(bookings)

    call_conversion_rate = (
        len(calls[calls['status'] == 'booked']) / len(calls) * 100
        if len(calls) > 0 else 0
    )
    message_conversion_rate = (
        len(messages[messages['status'] == 'booked']) / len(messages) * 100
        if len(messages) > 0 else 0
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 6. AGENT PERFORMANCE FOR CALLS & BOOKINGS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    agent_bookings = bookings.groupby('userId').size().reset_index(name='total_bookings')
    agent_calls = calls.groupby('userId').size().reset_index(name='total_calls')

    agent_performance = pd.merge(agent_calls, agent_bookings, on='userId', how='outer').fillna(0)
    agent_performance['booking_rate'] = (
        agent_performance['total_bookings'] / agent_performance['total_calls'] * 100
    ).fillna(0)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 7. OUTBOUND CALL SUCCESS RATE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Outbound Call Success Rate")

    max_duration = 60  # default if no 'duration' column
    if 'duration' in calls.columns and not calls['duration'].isnull().all():
        max_duration = int(calls['duration'].max())

    min_success_duration = st.slider(
        "Minimum Call Duration (seconds) to Count as Success",
        min_value=0,
        max_value=max_duration,
        value=30
    )

    outbound_calls = calls[calls['direction'] == 'outgoing']
    successful_outbound_calls = outbound_calls[outbound_calls['duration'] >= min_success_duration]

    success_rate = (
        len(successful_outbound_calls) / len(outbound_calls) * 100
        if len(outbound_calls) > 0 else 0
    )

    agent_success = successful_outbound_calls.groupby('userId').size().reset_index(name='successful_calls')
    agent_outbound = outbound_calls.groupby('userId').size().reset_index(name='total_outbound_calls')
    agent_success_rate = pd.merge(agent_outbound, agent_success, on='userId', how='outer').fillna(0)
    agent_success_rate['success_rate'] = (
        agent_success_rate['successful_calls'] / agent_success_rate['total_outbound_calls'] * 100
    ).fillna(0)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 8. METRICS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 9. HOURLY TRENDS (AM/PM in ET) with Logical Hour Order
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Hourly Trends")

    # Define desired order from 12 AM through 11 PM
    hour_order = [
        "12 AM","01 AM","02 AM","03 AM","04 AM","05 AM","06 AM","07 AM",
        "08 AM","09 AM","10 AM","11 AM","12 PM","01 PM","02 PM","03 PM",
        "04 PM","05 PM","06 PM","07 PM","08 PM","09 PM","10 PM","11 PM"
    ]

    # Convert createdAtET to day/hour columns
    calls['day'] = calls['createdAtET'].dt.strftime('%A')  # e.g. "Monday"
    calls['hour'] = calls['createdAtET'].dt.strftime('%I %p')  # e.g. "01 PM"

    # Make hour a categorical with a fixed order
    calls['hour'] = pd.Categorical(calls['hour'], categories=hour_order, ordered=True)

    # Aggregate for chart
    hourly_stats = calls.groupby(['hour', 'direction']).size().reset_index(name='count')
    fig = px.bar(
        hourly_stats,
        x='hour',
        y='count',
        color='direction',
        barmode='group',
        title='Call Volume by Hour (ET, AM/PM) [Logical Order]'
    )
    st.plotly_chart(fig)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 10. CALL DURATION ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Call Duration Analysis")
    if 'duration' in calls.columns and not calls['duration'].isnull().all():
        mean_duration = calls['duration'].mean()
        long_calls = calls[calls['duration'] >= mean_duration]

        # Long Calls by Hour
        long_hourly = long_calls.groupby('hour').size().reset_index(name='count')
        fig = px.bar(
            long_hourly,
            x='hour',
            y='count',
            title='Long Calls (Above Mean Duration) by Hour (ET, AM/PM)'
        )
        st.plotly_chart(fig)

        # Heatmap of Average Call Duration by Day & Hour
        duration_heatmap_data = calls.groupby(['day', 'hour'])['duration'].mean().reset_index()
        duration_heatmap_pivot = duration_heatmap_data.pivot(index='day', columns='hour', values='duration').fillna(0)

        # Reindex columns (hours) to ensure 12 AM -> 11 PM order
        duration_heatmap_pivot = duration_heatmap_pivot.reindex(columns=hour_order, fill_value=0)

        fig = px.imshow(
            duration_heatmap_pivot,
            title="Heatmap of Avg Call Duration by Day & Hour (ET, AM/PM)",
            labels=dict(x="Hour", y="Day", color="Duration (seconds)"),
        )
        st.plotly_chart(fig)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 11. INCOMING MESSAGE ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Incoming Messages by Hour (ET, AM/PM)")
    messages['hour'] = messages['createdAtET'].dt.strftime('%I %p')
    messages['day'] = messages['createdAtET'].dt.strftime('%A')

    # Make hour a categorical with the same hour_order
    messages['hour'] = pd.Categorical(messages['hour'], categories=hour_order, ordered=True)

    incoming_messages = messages[messages['direction'] == 'incoming']
    incoming_message_times = incoming_messages.groupby('hour').size().reset_index(name='count')
    fig = px.bar(
        incoming_message_times,
        x='hour',
        y='count',
        title='Incoming Messages by Hour (ET, AM/PM) [Logical Order]'
    )
    st.plotly_chart(fig)

    # Heatmap for Message Volume
    st.subheader("Message Volume Heatmap (ET, AM/PM)")
    message_heatmap_data = messages.groupby(['day', 'hour']).size().reset_index(name='count')
    message_heatmap_pivot = message_heatmap_data.pivot(index='day', columns='hour', values='count').fillna(0)

    # Reindex columns (hours) to ensure a consistent 12 AM -> 11 PM order
    message_heatmap_pivot = message_heatmap_pivot.reindex(columns=hour_order, fill_value=0)

    fig = px.imshow(
        message_heatmap_pivot,
        title="Heatmap of Message Volume by Day & Hour (ET, AM/PM)",
        labels=dict(x="Hour", y="Day", color="Volume"),
    )
    st.plotly_chart(fig)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 12. AGENT PERFORMANCE: CALLS & BOOKINGS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Performance: Calls & Bookings")
    fig = px.bar(
        agent_performance,
        x='userId',
        y=['total_calls', 'total_bookings'],
        title="Agent Performance (Calls vs. Bookings)",
        barmode='group',
    )
    st.plotly_chart(fig)

    st.dataframe(agent_performance.rename(columns={
        'userId': 'Agent',
        'total_calls': 'Total Calls',
        'total_bookings': 'Total Bookings',
        'booking_rate': 'Booking Rate (%)'
    }))

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 13. AGENT OUTBOUND SUCCESS RATE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 14. CALL VOLUME HEATMAP (AGGREGATE) with Logical Hour Order
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Call Volume Heatmap (ET, AM/PM) [Logical Order]")

    call_heatmap_data = calls.groupby(['day', 'hour']).size().reset_index(name='count')
    call_heatmap_pivot = call_heatmap_data.pivot(index='day', columns='hour', values='count').fillna(0)

    # Reindex columns (hours)
    call_heatmap_pivot = call_heatmap_pivot.reindex(columns=hour_order, fill_value=0)

    fig = px.imshow(
        call_heatmap_pivot,
        title="Heatmap of Call Volume by Day & Hour (ET, AM/PM)",
        labels=dict(x="Hour", y="Day", color="Volume"),
    )
    st.plotly_chart(fig)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 15. COMPARE AGENTS: INDIVIDUAL HEATMAPS (Logical Hour Order)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Compare Agents: Call Volume Heatmap by Day & Hour")

    df_agent_heat = calls.groupby(['userId', 'day', 'hour']).size().reset_index(name='count')
    for agent in selected_agents:
        agent_data = df_agent_heat[df_agent_heat['userId'] == agent]
        if agent_data.empty:
            continue

        pivot_table = agent_data.pivot(index='day', columns='hour', values='count').fillna(0)

        # Reindex to ensure "12 AM" through "11 PM" columns in order
        pivot_table = pivot_table.reindex(columns=hour_order, fill_value=0)

        fig = px.imshow(
            pivot_table,
            color_continuous_scale='Blues',
            labels=dict(x="Hour (AM/PM)", y="Day of Week", color="Call Volume"),
            title=f"Call Volume Heatmap for Agent: {agent}",
        )
        st.plotly_chart(fig)

    st.success("Enhanced Dashboard with ET (AM/PM), Agent Filter, and Logical 12 AM-11 PM Hour Ordering is Ready!")
