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

    # Convert answeredAtPT -> answeredAtET if applicable
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

    # A) Date Filters
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

    # Filter data by date
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
    # 6. AGENT PERFORMANCE
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

    if not calls.empty:
        calls['day'] = calls['createdAtET'].dt.strftime('%A')
        calls['hour'] = calls['createdAtET'].dt.strftime('%I %p')
        # Make calls['hour'] a Categorical
        calls['hour'] = pd.Categorical(calls['hour'], categories=hour_order, ordered=True)

    if not messages.empty:
        messages['day'] = messages['createdAtET'].dt.strftime('%A')
        messages['hour'] = messages['createdAtET'].dt.strftime('%I %p')
        messages['hour'] = pd.Categorical(messages['hour'], categories=hour_order, ordered=True)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 8. OUTBOUND CALL SUCCESS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Outbound Call Success Rate")

    max_duration = 60
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
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Bookings", total_bookings)
    with c2:
        st.metric("Call Conversion Rate", f"{call_conversion_rate:.2f}%")
    with c3:
        st.metric("Message Conversion Rate", f"{message_conversion_rate:.2f}%")
    with c4:
        st.metric("Outbound Call Success Rate", f"{success_rate:.2f}%")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 10. HOURLY TRENDS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Hourly Trends")
    if not calls.empty:
        hourly_stats = calls.groupby(['hour', 'direction']).size().reset_index(name='count')
        fig = px.bar(hourly_stats, x='hour', y='count', color='direction',
                     barmode='group', title='Call Volume by Hour')
        st.plotly_chart(fig)
    else:
        st.warning("No calls found.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 11. CALL DURATION ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Call Duration Analysis")
    if 'duration' in calls.columns and not calls['duration'].isnull().all() and not calls.empty:
        mean_duration = calls['duration'].mean()
        long_calls = calls[calls['duration'] >= mean_duration]

        if not long_calls.empty:
            lc_df = long_calls.groupby('hour').size().reset_index(name='count')
            fig = px.bar(lc_df, x='hour', y='count', title='Long Calls by Hour')
            st.plotly_chart(fig)

        # Duration heatmap
        dur_data = calls.groupby(['day', 'hour'])['duration'].mean().reset_index()
        if not dur_data.empty:
            pivot_dur = dur_data.pivot(index='day', columns='hour', values='duration')

            # Convert columns -> string
            pivot_dur.columns = pivot_dur.columns.astype(str)

            # Let's not forcibly reindex. Instead, just fill missing
            pivot_dur = pivot_dur.fillna(0)

            fig = px.imshow(pivot_dur, title="Heatmap of Avg Call Duration",
                            labels=dict(x="Hour", y="Day", color="Seconds"))
            st.plotly_chart(fig)
    else:
        st.warning("No duration data or no calls.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 12. INCOMING MESSAGE ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Incoming Messages by Hour")
    if not messages.empty:
        inc_msgs = messages[messages['direction'] == 'incoming']
        inc_counts = inc_msgs.groupby('hour').size().reset_index(name='count')
        fig = px.bar(inc_counts, x='hour', y='count', title='Incoming Messages by Hour')
        st.plotly_chart(fig)

        # Message volume heatmap
        msg_data = messages.groupby(['day', 'hour']).size().reset_index(name='count')
        if not msg_data.empty:
            pivot_msg = msg_data.pivot(index='day', columns='hour', values='count')
            pivot_msg.columns = pivot_msg.columns.astype(str)
            pivot_msg = pivot_msg.fillna(0)

            fig = px.imshow(pivot_msg, title="Message Volume Heatmap",
                            labels=dict(x="Hour", y="Day", color="Volume"))
            st.plotly_chart(fig)
    else:
        st.warning("No messages in filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 13. AGENT PERFORMANCE: CALLS & BOOKINGS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Performance: Calls & Bookings")
    if not agent_performance.empty:
        fig = px.bar(agent_performance, x='userId', y=['total_calls', 'total_bookings'],
                     title="Agent Performance", barmode='group')
        st.plotly_chart(fig)

        st.dataframe(agent_performance.rename(columns={
            'userId': 'Agent',
            'total_calls': 'Total Calls',
            'total_bookings': 'Total Bookings',
            'booking_rate': 'Booking Rate (%)'
        }))
    else:
        st.warning("No agent performance data.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 14. AGENT OUTBOUND SUCCESS RATE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Outbound Success Rate")
    if not agent_success_rate.empty:
        fig = px.bar(agent_success_rate, x='userId',
                     y=['total_outbound_calls', 'successful_calls'],
                     title="Outbound Success Rate", barmode='group')
        st.plotly_chart(fig)

        st.dataframe(agent_success_rate.rename(columns={
            'userId': 'Agent',
            'total_outbound_calls': 'Total Outbound Calls',
            'successful_calls': 'Successful Calls',
            'success_rate': 'Success Rate (%)'
        }))
    else:
        st.warning("No outbound success data.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 15. CALL VOLUME HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Call Volume Heatmap")
    if not calls.empty:
        call_count = calls.groupby(['day', 'hour']).size().reset_index(name='count')
        if not call_count.empty:
            pivot_call = call_count.pivot(index='day', columns='hour', values='count')
            pivot_call.columns = pivot_call.columns.astype(str)
            pivot_call = pivot_call.fillna(0)

            fig = px.imshow(pivot_call, title="Heatmap of Call Volume",
                            labels=dict(x="Hour", y="Day", color="Volume"))
            st.plotly_chart(fig)
    else:
        st.warning("No calls for volume heatmap.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 16. SUCCESSFUL OUTBOUND CALLS HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Successful Outbound Calls Heatmap")
    if not successful_outbound_calls.empty:
        so_data = successful_outbound_calls.groupby(['day', 'hour']).size().reset_index(name='count')
        pivot_so = so_data.pivot(index='day', columns='hour', values='count')
        pivot_so.columns = pivot_so.columns.astype(str)
        pivot_so = pivot_so.fillna(0)

        fig = px.imshow(pivot_so, title="Heatmap: Successful Outbound Calls",
                        labels=dict(x="Hour", y="Day", color="Volume"),
                        color_continuous_scale="Blues")
        st.plotly_chart(fig)

        # Individual Agents
        st.subheader("Compare Agents: Successful Outbound Calls Heatmap")
        df_agent_so = successful_outbound_calls.groupby(['userId', 'day', 'hour']).size().reset_index(name='count')

        for agent in selected_agents:
            agent_data = df_agent_so[df_agent_so['userId'] == agent]
            if agent_data.empty:
                st.write(f"No successful outbound calls for agent: {agent}")
                continue

            pivot_a = agent_data.pivot(index='day', columns='hour', values='count')
            pivot_a.columns = pivot_a.columns.astype(str)
            pivot_a = pivot_a.fillna(0)

            fig = px.imshow(pivot_a, color_continuous_scale='Blues',
                            labels=dict(x="Hour", y="Day", color="Call Volume"),
                            title=f"Successful Outbound Calls Heatmap for Agent: {agent}")
            st.plotly_chart(fig)
    else:
        st.warning("No successful outbound calls in filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 17. AGENT SUCCESS RATE HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Success Rate Heatmap by Day & Hour")
    if not outbound_calls.empty:
        # 1) Outbound calls by agent/day/hour
        group_outbound = outbound_calls.groupby(['userId', 'day', 'hour']).size().reset_index(name='outbound_count')

        # 2) Successful calls by agent/day/hour
        group_success = successful_outbound_calls.groupby(['userId', 'day', 'hour']).size().reset_index(name='success_count')

        # 3) Merge
        df_merge = pd.merge(group_outbound, group_success,
                            on=['userId','day','hour'], how='outer').fillna(0)
        df_merge['success_rate'] = (df_merge['success_count'] / df_merge['outbound_count']) * 100

        for agent in selected_agents:
            this_agent = df_merge[df_merge['userId'] == agent]
            if this_agent.empty:
                st.write(f"No outbound calls for agent: {agent}")
                continue

            # Pivot day vs. hour
            pivot_srate = this_agent.pivot(index='day', columns='hour', values='success_rate')

            # Convert columns -> string to avoid setitem issues
            pivot_srate.columns = pivot_srate.columns.astype(str)
            # Convert index -> string (just in case)
            pivot_srate.index = pivot_srate.index.astype(str)

            # Fill missing with 0
            pivot_srate = pivot_srate.fillna(0)

            # (Optional) If you want hours in a partial order, do:
            # actual_cols = [h for h in hour_order if h in pivot_srate.columns]
            # pivot_srate = pivot_srate[actual_cols]

            fig = px.imshow(
                pivot_srate,
                color_continuous_scale='Blues',
                labels=dict(x="Hour (AM/PM)", y="Day", color="Success Rate (%)"),
                title=f"Success Rate Heatmap for Agent: {agent}",
            )
            fig.update_xaxes(side="top")
            fig.update_layout(coloraxis=dict(cmin=0, cmax=100))
            st.plotly_chart(fig)
    else:
        st.warning("No outbound calls to show success rate heatmap.")

    st.success("Enhanced Dashboard Ready — with final fixes for 'Cannot setitem on a Categorical'!")
