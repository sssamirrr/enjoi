import streamlit as st
import pandas as pd
import plotly.express as px
import pytz
from datetime import datetime

def run_openphone_tab():
    st.header("Enhanced OpenPhone Operations Dashboard")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 1. UPLOAD FILE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    uploaded_file = st.file_uploader("Upload OpenPhone CSV File", type=["csv"])
    if not uploaded_file:
        st.warning("Please upload the OpenPhone CSV file to proceed.")
        return

    openphone_data = pd.read_csv(uploaded_file)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 2. TIME ZONE CONVERSION (PT -> ET)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    pacific_tz = pytz.timezone("America/Los_Angeles")
    eastern_tz = pytz.timezone("America/New_York")

    openphone_data['createdAtPT'] = pd.to_datetime(openphone_data['createdAtPT'], errors='coerce')
    openphone_data = openphone_data.dropna(subset=['createdAtPT'])  # remove rows with no createdAtPT

    openphone_data['createdAtET'] = (
        openphone_data['createdAtPT']
        .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
        .dt.tz_convert(eastern_tz)
    )

    if 'answeredAtPT' in openphone_data.columns:
        openphone_data['answeredAtPT'] = pd.to_datetime(openphone_data['answeredAtPT'], errors='coerce')
        openphone_data['answeredAtET'] = (
            openphone_data['answeredAtPT']
            .dropna()
            .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
            .dt.tz_convert(eastern_tz)
        )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 3. FILTERS (DATE RANGE & AGENT)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Filters")

    min_date = openphone_data['createdAtET'].min().date()
    max_date = openphone_data['createdAtET'].max().date()
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=min_date, min_value=min_date, max_value=max_date)
    with col2:
        end_date = st.date_input("End Date", value=max_date, min_value=min_date, max_value=max_date)

    if start_date > end_date:
        st.error("Start date cannot exceed end date.")
        return

    # Filter by date range
    openphone_data = openphone_data[
        (openphone_data['createdAtET'].dt.date >= start_date) &
        (openphone_data['createdAtET'].dt.date <= end_date)
    ]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # AGENT FILTER WITH @enjoiresorts.com ONLY
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    if 'userId' not in openphone_data.columns:
        st.error("No 'userId' column found in the dataset.")
        return

    # Step A: Only agents whose emails end with "@enjoiresorts.com"
    all_agents = sorted([
        agent for agent in openphone_data['userId'].dropna().unique()
        if agent.endswith("@enjoiresorts.com")
    ])  # <-- UPDATED

    # Step B: Map each agent’s full email --> shortened (remove domain)
    def short_agent_name(full_email):
        return full_email.replace("@enjoiresorts.com", "")

    agent_map = {agent: short_agent_name(agent) for agent in all_agents}

    # We present only the "shortened" names in the multiselect
    agent_choices = list(agent_map.values())  # all shortened names

    selected_short_names = st.multiselect(
        "Select Agents",
        agent_choices,
        default=[]
    )  # by default no agent is selected

    # Convert user’s choice (shortened name) back to the full email
    selected_agents = [
        full_email
        for full_email, short_name in agent_map.items()
        if short_name in selected_short_names
    ]

    openphone_data = openphone_data[openphone_data['userId'].isin(selected_agents)]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 4. SPLIT: CALLS VS. MESSAGES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    calls = openphone_data[openphone_data['type'] == 'call']
    messages = openphone_data[openphone_data['type'] == 'message']

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 5. BOOKING / CONVERSION
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
    # 6. AGENT PERFORMANCE (CALLS & BOOKINGS)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    agent_bookings = bookings.groupby('userId').size().reset_index(name='total_bookings')
    agent_calls = calls.groupby('userId').size().reset_index(name='total_calls')

    agent_performance = pd.merge(agent_calls, agent_bookings, on='userId', how='outer').fillna(0)
    agent_performance['booking_rate'] = (
        agent_performance['total_bookings'] / agent_performance['total_calls'] * 100
    ).fillna(0)

    # Create a column with the shortened agent name for display
    agent_performance['Agent'] = agent_performance['userId'].map(agent_map)  # <-- UPDATED

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 7. DEFINE day AND hour (STRING) + day_order & hour_order
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    hour_order = [
        "12 AM","01 AM","02 AM","03 AM","04 AM","05 AM","06 AM","07 AM",
        "08 AM","09 AM","10 AM","11 AM","12 PM","01 PM","02 PM","03 PM",
        "04 PM","05 PM","06 PM","07 PM","08 PM","09 PM","10 PM","11 PM"
    ]

    if not calls.empty:
        calls['day'] = calls['createdAtET'].dt.strftime('%A').astype(str)
        calls['hour'] = calls['createdAtET'].dt.strftime('%I %p').astype(str)

    if not messages.empty:
        messages['day'] = messages['createdAtET'].dt.strftime('%A').astype(str)
        messages['hour'] = messages['createdAtET'].dt.strftime('%I %p').astype(str)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 8. OUTBOUND CALL SUCCESS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Outbound Call Success Rate")

    max_duration = 60
    if 'duration' in calls.columns and not calls['duration'].isnull().all():
        max_duration = int(calls['duration'].max())

    min_success_duration = st.slider(
        "Min Call Duration (seconds) for Success",
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

    # Shorten agent name for display
    agent_success_rate['Agent'] = agent_success_rate['userId'].map(agent_map)  # <-- UPDATED

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 9. KEY METRICS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Key Metrics")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Bookings", total_bookings)
    with c2:
        st.metric("Call Conv. Rate", f"{call_conversion_rate:.2f}%")
    with c3:
        st.metric("Msg Conv. Rate", f"{message_conversion_rate:.2f}%")
    with c4:
        st.metric("Outbound Success Rate", f"{success_rate:.2f}%")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 10. HOURLY TRENDS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Hourly Trends (12 AM -> 11 PM)")
    if not calls.empty:
        # Ensure calls['hour'] is categorical
        calls['hour'] = pd.Categorical(calls['hour'], categories=hour_order, ordered=True)

        hourly_stats = calls.groupby(['hour','direction']).size().reset_index(name='count')
        fig = px.bar(hourly_stats, x='hour', y='count', color='direction',
                     barmode='group', title="Calls by Hour")
        st.plotly_chart(fig)
    else:
        st.warning("No calls found in range/filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 11. CALL DURATION ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Call Duration Analysis")
    if 'duration' in calls.columns and not calls['duration'].isnull().all() and not calls.empty:
        mean_dur = calls['duration'].mean()
        long_calls = calls[calls['duration'] >= mean_dur]

        # Also ensure hour is categorical in long_calls
        if not long_calls.empty:
            long_calls['hour'] = pd.Categorical(long_calls['hour'], categories=hour_order, ordered=True)
            lc_df = long_calls.groupby('hour').size().reset_index(name='count')
            fig = px.bar(lc_df, x='hour', y='count', title="Long Calls by Hour (12 AM -> 11 PM)")
            st.plotly_chart(fig)

        # Heatmap: day vs. hour (Avg Duration)
        dur_data = calls.groupby(['day','hour'])['duration'].mean().reset_index()
        if not dur_data.empty:
            pivot_dur = dur_data.pivot(index='day', columns='hour', values='duration')
            pivot_dur.index = pivot_dur.index.astype(str)
            pivot_dur.columns = pivot_dur.columns.astype(str)

            # Reindex day/hour intersection
            actual_days = [d for d in day_order if d in pivot_dur.index]
            actual_hours = [h for h in hour_order if h in pivot_dur.columns]

            pivot_dur = pivot_dur.reindex(index=actual_days, columns=actual_hours).fillna(0)
            fig = px.imshow(
                pivot_dur,
                title="Heatmap of Avg Call Duration (Day vs. Hour)",
                labels=dict(x="Hour", y="Day", color="Duration (s)")
            )
            st.plotly_chart(fig)
    else:
        st.warning("No 'duration' data or no calls in filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 12. INCOMING MESSAGE ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Incoming Messages by Hour")
    if not messages.empty:
        # Make messages['hour'] a categorical
        messages['hour'] = pd.Categorical(messages['hour'], categories=hour_order, ordered=True)

        inc_msgs = messages[messages['direction'] == 'incoming']
        inc_counts = inc_msgs.groupby('hour').size().reset_index(name='count')
        fig = px.bar(inc_counts, x='hour', y='count', title="Incoming Msgs by Hour (12 AM -> 11 PM)")
        st.plotly_chart(fig)

        # Heatmap: day vs. hour
        msg_df = messages.groupby(['day','hour']).size().reset_index(name='count')
        if not msg_df.empty:
            pivot_msg = msg_df.pivot(index='day', columns='hour', values='count')
            pivot_msg.index = pivot_msg.index.astype(str)
            pivot_msg.columns = pivot_msg.columns.astype(str)

            actual_days = [d for d in day_order if d in pivot_msg.index]
            actual_hours = [h for h in hour_order if h in pivot_msg.columns]
            pivot_msg = pivot_msg.reindex(index=actual_days, columns=actual_hours).fillna(0)

            fig = px.imshow(
                pivot_msg,
                title="Message Volume Heatmap (Day vs. Hour)",
                labels=dict(x="Hour", y="Day", color="Volume")
            )
            st.plotly_chart(fig)
    else:
        st.warning("No messages found in range/filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 13. AGENT PERFORMANCE (CALLS & BOOKINGS)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Performance: Calls vs. Bookings")
    if not agent_performance.empty:
        # We use 'Agent' (the shortened name) as the x-axis
        fig = px.bar(
            agent_performance,
            x='Agent',  # <-- UPDATED
            y=['total_calls','total_bookings'],
            title="Agent Performance",
            barmode='group'
        )
        st.plotly_chart(fig)

        st.dataframe(agent_performance.rename(columns={
            'Agent': 'Agent (short)',
            'total_calls': 'Total Calls',
            'total_bookings': 'Total Bookings',
            'booking_rate': 'Booking Rate (%)'
        }))
    else:
        st.warning("No agent performance data available.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 14. AGENT OUTBOUND SUCCESS RATE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Outbound Success Rate")
    if not agent_success_rate.empty:
        fig = px.bar(
            agent_success_rate,
            x='Agent',  # <-- UPDATED
            y=['total_outbound_calls','successful_calls'],
            title="Outbound Success Rate",
            barmode='group'
        )
        st.plotly_chart(fig)

        st.dataframe(agent_success_rate.rename(columns={
            'Agent': 'Agent (short)',
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
        vol_df = calls.groupby(['day','hour']).size().reset_index(name='count')
        if not vol_df.empty:
            pivot_vol = vol_df.pivot(index='day', columns='hour', values='count')
            pivot_vol.index = pivot_vol.index.astype(str)
            pivot_vol.columns = pivot_vol.columns.astype(str)

            actual_days = [d for d in day_order if d in pivot_vol.index]
            actual_hours = [h for h in hour_order if h in pivot_vol.columns]

            pivot_vol = pivot_vol.reindex(index=actual_days, columns=actual_hours).fillna(0)

            fig = px.imshow(
                pivot_vol,
                title="Call Volume Heatmap (Day vs. Hour)",
                labels=dict(x="Hour", y="Day", color="Count")
            )
            st.plotly_chart(fig)
    else:
        st.warning("No calls to show volume heatmap.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 16. SUCCESSFUL OUTBOUND CALLS HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Successful Outbound Calls Heatmap")
    if not successful_outbound_calls.empty:
        so_df = successful_outbound_calls.groupby(['day','hour']).size().reset_index(name='count')
        pivot_so = so_df.pivot(index='day', columns='hour', values='count')
        pivot_so.index = pivot_so.index.astype(str)
        pivot_so.columns = pivot_so.columns.astype(str)

        # Reindex
        actual_days = [d for d in day_order if d in pivot_so.index]
        actual_hours = [h for h in hour_order if h in pivot_so.columns]
        pivot_so = pivot_so.reindex(index=actual_days, columns=actual_hours).fillna(0)

        fig = px.imshow(
            pivot_so,
            title="Successful Outbound Calls Heatmap",
            labels=dict(x="Hour", y="Day", color="Volume"),
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig)

        # Compare Agents (Individually)
        st.subheader("Compare Agents: Successful Outbound Calls (Day vs. Hour)")
        df_agent_so = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='count')

        for agent in selected_agents:
            # use short name for the header
            agent_short = agent_map.get(agent, agent)
            adf = df_agent_so[df_agent_so['userId'] == agent]
            if adf.empty:
                st.write(f"No successful outbound calls for: {agent_short}")
                continue

            pivot_a = adf.pivot(index='day', columns='hour', values='count')
            pivot_a.index = pivot_a.index.astype(str)
            pivot_a.columns = pivot_a.columns.astype(str)

            a_days = [d for d in day_order if d in pivot_a.index]
            a_hours = [h for h in hour_order if h in pivot_a.columns]

            pivot_a = pivot_a.reindex(index=a_days, columns=a_hours).fillna(0)
            fig = px.imshow(
                pivot_a,
                color_continuous_scale='Blues',
                labels=dict(x="Hour", y="Day", color="Count"),
                title=f"Agent {agent_short} - Successful Outbound Calls"
            )
            st.plotly_chart(fig)
    else:
        st.warning("No successful outbound calls found.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 17. AGENT SUCCESS RATE HEATMAP (Day & Hour)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Success Rate Heatmap by Day & Hour")

    if not outbound_calls.empty:
        # Group outbound calls
        group_outbound = outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='outbound_count')
        # Group successful
        group_success = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='success_count')

        # Convert to string if not already
        group_outbound['day'] = group_outbound['day'].astype(str)
        group_outbound['hour'] = group_outbound['hour'].astype(str)
        group_success['day'] = group_success['day'].astype(str)
        group_success['hour'] = group_success['hour'].astype(str)

        # Merge
        merged = pd.merge(group_outbound, group_success, on=['userId','day','hour'], how='outer').fillna(0)
        merged['success_rate'] = (merged['success_count'] / merged['outbound_count']) * 100

        # Pivot per agent
        for agent in selected_agents:
            agent_short = agent_map.get(agent, agent)  # short name
            agent_df = merged[merged['userId'] == agent]
            if agent_df.empty:
                st.write(f"No outbound calls for agent: {agent_short}")
                continue

            pivot_srate = agent_df.pivot(index='day', columns='hour', values='success_rate')

            pivot_srate.index = pivot_srate.index.astype(str)
            pivot_srate.columns = pivot_srate.columns.astype(str)

            # Reindex rows & columns by intersection with day_order / hour_order
            a_days = [d for d in day_order if d in pivot_srate.index]
            a_hours = [h for h in hour_order if h in pivot_srate.columns]
            pivot_srate = pivot_srate.reindex(index=a_days, columns=a_hours).fillna(0)

            fig = px.imshow(
                pivot_srate,
                color_continuous_scale='Blues',
                labels=dict(x="Hour (AM/PM)", y="Day", color="Success Rate (%)"),
                title=f"Success Rate Heatmap - {agent_short}",
            )
            fig.update_xaxes(side="top")
            fig.update_layout(coloraxis=dict(cmin=0, cmax=100))
            st.plotly_chart(fig)
    else:
        st.warning("No outbound calls for success rate heatmap.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 18. SIDE-BY-SIDE HEATMAP: SUCCESSFUL OUTBOUND CALLS + SUCCESS RATE
    #     in one figure (if 2+ agents are selected)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Compare Agents Side-by-Side: Calls vs. Success Rate in One Figure")

    if len(selected_agents) >= 2 and not successful_outbound_calls.empty and not outbound_calls.empty:
        # 1) Build 'count' dataset
        df_count = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='count')
        df_count['day'] = df_count['day'].astype(str)
        df_count['hour'] = df_count['hour'].astype(str)
        df_count['metric'] = "Count"
        df_count.rename(columns={'count': 'value'}, inplace=True)

        # 2) Build 'success_rate' dataset
        group_outbound = outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='outbound_count')
        group_success = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='success_count')
        merged_df = pd.merge(group_outbound, group_success, on=['userId','day','hour'], how='outer').fillna(0)
        merged_df['success_rate'] = (merged_df['success_count'] / merged_df['outbound_count']) * 100
        merged_df['day'] = merged_df['day'].astype(str)
        merged_df['hour'] = merged_df['hour'].astype(str)

        df_srate = merged_df[['userId','day','hour','success_rate']].copy()
        df_srate['metric'] = "Success Rate"
        df_srate.rename(columns={'success_rate': 'value'}, inplace=True)

        # 3) Combine them
        combined = pd.concat([df_count, df_srate], ignore_index=True)

        # 4) We'll use facet_col='userId' and facet_row='metric'
        #    so top row = metric=Count, bottom row=metric=Success Rate
        #    left to right = userId
        # But we want the short names on the facet columns
        # --> We can replace userId in "combined" with the short names:
        combined['short_user'] = combined['userId'].map(agent_map)

        fig = px.density_heatmap(
            combined,
            x='hour',
            y='day',
            z='value',
            facet_col='short_user',  # <-- use the short name in the facets
            facet_row='metric',
            color_continuous_scale='Blues',
            category_orders={
                "hour": hour_order,
                "day": day_order,
                "metric": ["Count", "Success Rate"],  # ensures Count row is top
                "short_user": [agent_map[a] for a in selected_agents],  # keep user-chosen order
            },
            title="Side-by-Side: Successful Calls (Count) vs. Success Rate per Agent",
            text_auto=True
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Side-by-side calls vs. success rate not shown. Need 2+ agents selected and some calls present.")

    st.success("Enhanced Dashboard Complete!")
