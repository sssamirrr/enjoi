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
    # 7. DEFINE 'day' AND 'hour' (LOGICAL ORDER)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    hour_order = [
        "12 AM","01 AM","02 AM","03 AM","04 AM","05 AM","06 AM","07 AM",
        "08 AM","09 AM","10 AM","11 AM","12 PM","01 PM","02 PM","03 PM",
        "04 PM","05 PM","06 PM","07 PM","08 PM","09 PM","10 PM","11 PM"
    ]

    # If calls/messages are not empty, add day/hour
    if not calls.empty:
        calls['day'] = calls['createdAtET'].dt.strftime('%A')  # e.g. "Monday"
        calls['hour'] = calls['createdAtET'].dt.strftime('%I %p')
        # Make them categorical with your hour_order
        calls['hour'] = pd.Categorical(calls['hour'], categories=hour_order, ordered=True)

    if not messages.empty:
        messages['day'] = messages['createdAtET'].dt.strftime('%A')
        messages['hour'] = messages['createdAtET'].dt.strftime('%I %p')
        messages['hour'] = pd.Categorical(messages['hour'], categories=hour_order, ordered=True)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 8. OUTBOUND CALL SUCCESS RATE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Outbound Call Success Rate")

    max_duration = 60  # default if no 'duration'
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
    # 9. METRICS
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
    # 10. HOURLY TRENDS (AM/PM in ET)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Hourly Trends")

    if not calls.empty:
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
    else:
        st.warning("No calls found in the selected range/filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 11. CALL DURATION ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Call Duration Analysis")
    if 'duration' in calls.columns and not calls['duration'].isnull().all() and not calls.empty:
        mean_duration = calls['duration'].mean()
        long_calls = calls[calls['duration'] >= mean_duration]

        # Long Calls by Hour
        if not long_calls.empty:
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
        if not duration_heatmap_data.empty:
            duration_heatmap_pivot = duration_heatmap_data.pivot(index='day', columns='hour', values='duration')

            # Convert columns to non-categorical so reindex won't break
            duration_heatmap_pivot.columns = duration_heatmap_pivot.columns.astype(str)

            duration_heatmap_pivot = duration_heatmap_pivot.reindex(columns=hour_order)
            duration_heatmap_pivot = duration_heatmap_pivot.fillna(0)

            fig = px.imshow(
                duration_heatmap_pivot,
                title="Heatmap of Avg Call Duration by Day & Hour (ET, AM/PM)",
                labels=dict(x="Hour", y="Day", color="Duration (seconds)"),
            )
            st.plotly_chart(fig)
    else:
        st.warning("No valid 'duration' data found or no calls in the selected filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 12. INCOMING MESSAGE ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Incoming Messages by Hour (ET, AM/PM) [Logical Order]")
    if not messages.empty:
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
        message_heatmap_pivot = message_heatmap_data.pivot(index='day', columns='hour', values='count')

        # Convert columns to non-categorical so reindex won't break
        message_heatmap_pivot.columns = message_heatmap_pivot.columns.astype(str)

        message_heatmap_pivot = message_heatmap_pivot.reindex(columns=hour_order)
        message_heatmap_pivot = message_heatmap_pivot.fillna(0)

        fig = px.imshow(
            message_heatmap_pivot,
            title="Heatmap of Message Volume by Day & Hour (ET, AM/PM)",
            labels=dict(x="Hour", y="Day", color="Volume"),
        )
        st.plotly_chart(fig)
    else:
        st.warning("No messages found in the selected filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 13. AGENT PERFORMANCE: CALLS & BOOKINGS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Performance: Calls & Bookings")
    if not agent_performance.empty:
        fig = px.bar(
            agent_performance,
            x='userId',
            y=['total_calls', 'total_bookings'],
            title="Agent Performance (Calls vs. Bookings)",
            barmode='group',
        )
        st.plotly_chart(fig)

        st.dataframe(
            agent_performance.rename(columns={
                'userId': 'Agent',
                'total_calls': 'Total Calls',
                'total_bookings': 'Total Bookings',
                'booking_rate': 'Booking Rate (%)'
            })
        )
    else:
        st.warning("No agent performance data available.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 14. AGENT OUTBOUND SUCCESS RATE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Outbound Success Rate")
    if not agent_success_rate.empty:
        fig = px.bar(
            agent_success_rate,
            x='userId',
            y=['total_outbound_calls', 'successful_calls'],
            title="Agent Outbound Success Rate",
            barmode='group',
        )
        st.plotly_chart(fig)

        st.dataframe(
            agent_success_rate.rename(columns={
                'userId': 'Agent',
                'total_outbound_calls': 'Total Outbound Calls',
                'successful_calls': 'Successful Calls',
                'success_rate': 'Success Rate (%)'
            })
        )
    else:
        st.warning("No outbound success data available.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 15. CALL VOLUME HEATMAP (AGGREGATE) with Logical Hour Order
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Call Volume Heatmap (ET, AM/PM) [Logical Order]")
    if not calls.empty:
        call_heatmap_data = calls.groupby(['day', 'hour']).size().reset_index(name='count')
        call_heatmap_pivot = call_heatmap_data.pivot(index='day', columns='hour', values='count')

        # Convert columns so they're not categorical
        call_heatmap_pivot.columns = call_heatmap_pivot.columns.astype(str)

        call_heatmap_pivot = call_heatmap_pivot.reindex(columns=hour_order)
        call_heatmap_pivot = call_heatmap_pivot.fillna(0)

        fig = px.imshow(
            call_heatmap_pivot,
            title="Heatmap of Call Volume by Day & Hour (ET, AM/PM)",
            labels=dict(x="Hour", y="Day", color="Volume"),
        )
        st.plotly_chart(fig)
    else:
        st.warning("No calls to display in the volume heatmap.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 16. SUCCESSFUL OUTBOUND CALLS HEATMAP (AGGREGATE & INDIVIDUAL)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Successful Outbound Calls Heatmap (ET, AM/PM) [Logical Order]")

    if not successful_outbound_calls.empty:
        success_heat_data = successful_outbound_calls.groupby(['day', 'hour']).size().reset_index(name='count')
        success_heat_pivot = success_heat_data.pivot(index='day', columns='hour', values='count')

        # Convert columns to non-categorical
        success_heat_pivot.columns = success_heat_pivot.columns.astype(str)

        success_heat_pivot = success_heat_pivot.reindex(columns=hour_order)
        success_heat_pivot = success_heat_pivot.fillna(0)

        fig = px.imshow(
            success_heat_pivot,
            title="Heatmap of Successful Outbound Calls by Day & Hour (ET, AM/PM)",
            labels=dict(x="Hour", y="Day", color="Volume"),
            color_continuous_scale="Blues",
        )
        st.plotly_chart(fig)

        # Individual Agent Comparison
        st.subheader("Compare Agents: Successful Outbound Calls Heatmap by Day & Hour")
        df_agent_success_heat = successful_outbound_calls.groupby(['userId', 'day', 'hour']).size().reset_index(name='count')

        for agent in selected_agents:
            agent_data = df_agent_success_heat[df_agent_success_heat['userId'] == agent]
            if agent_data.empty:
                st.write(f"No successful outbound calls for agent: {agent}")
                continue

            pivot_table = agent_data.pivot(index='day', columns='hour', values='count')

            # Convert columns
            pivot_table.columns = pivot_table.columns.astype(str)
            pivot_table = pivot_table.reindex(columns=hour_order)
            pivot_table = pivot_table.fillna(0)

            fig = px.imshow(
                pivot_table,
                color_continuous_scale='Blues',
                labels=dict(x="Hour (AM/PM)", y="Day of Week", color="Call Volume"),
                title=f"Successful Outbound Calls Heatmap for Agent: {agent}",
            )
            st.plotly_chart(fig)
    else:
        st.warning("No successful outbound calls found in the selected filters or minimum duration.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 17. AGENT SUCCESS RATE HEATMAP BY DAY & HOUR
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Success Rate Heatmap by Day & Hour")

    if not outbound_calls.empty:
        # 1) Group outbound calls by agent, day, hour -> total_outbound
        agent_outbound_grouped = outbound_calls.groupby(['userId', 'day', 'hour']).size().reset_index(name='outbound_count')

        # 2) Group successful outbound calls by agent, day, hour -> success_count
        agent_success_grouped = successful_outbound_calls.groupby(['userId', 'day', 'hour']).size().reset_index(name='success_count')

        # 3) Merge them to compute success_rate
        agent_day_hour = pd.merge(
            agent_outbound_grouped,
            agent_success_grouped,
            on=['userId', 'day', 'hour'],
            how='outer'
        ).fillna(0)

        agent_day_hour['success_rate'] = (
            agent_day_hour['success_count'] / agent_day_hour['outbound_count']
        ) * 100

        # 4) Loop over each selected agent & build a heatmap of success_rate
        for agent in selected_agents:
            this_agent = agent_day_hour[agent_day_hour['userId'] == agent]
            if this_agent.empty:
                st.write(f"No outbound calls found for agent: {agent}")
                continue

            pivot_table = this_agent.pivot(index='day', columns='hour', values='success_rate')

            # Convert columns to non-categorical
            pivot_table.columns = pivot_table.columns.astype(str)
            pivot_table = pivot_table.reindex(columns=hour_order)
            pivot_table = pivot_table.fillna(0)

            fig = px.imshow(
                pivot_table,
                color_continuous_scale='Blues',
                labels=dict(x="Hour (AM/PM)", y="Day", color="Success Rate (%)"),
                title=f"Success Rate Heatmap for Agent: {agent}",
            )
            # Set a consistent color range from 0-100
            fig.update_xaxes(side="top")
            fig.update_layout(coloraxis=dict(cmin=0, cmax=100))

            st.plotly_chart(fig)
    else:
        st.warning("No outbound calls to display success rate heatmap.")

    st.success("Enhanced Dashboard with ET (AM/PM), Agent Filter, Logical Hour Ordering, "
               "and Additional Agent Success Rate Heatmaps is Ready!")
