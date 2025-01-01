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
    ])

    # Step B: Map each agent’s full email --> shortened (remove domain)
    def short_agent_name(full_email):
        return full_email.replace("@enjoiresorts.com", "")

    agent_map = {agent: short_agent_name(agent) for agent in all_agents}

    # We present only the "shortened" names in the multiselect
    agent_choices = list(agent_map.values())

    selected_short_names = st.multiselect(
        "Select Agents",
        agent_choices,
        default=[]
    )

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
    agent_performance['Agent'] = agent_performance['userId'].map(agent_map)

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
    agent_success_rate['Agent'] = agent_success_rate['userId'].map(agent_map)

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
        fig = px.bar(
            agent_performance,
            x='Agent',
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
            x='Agent',
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

        st.subheader("Compare Agents: Successful Outbound Calls (Day vs. Hour)")
        df_agent_so = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='count')
        for agent in selected_agents:
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
        group_outbound = outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='outbound_count')
        group_success = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='success_count')

        group_outbound['day'] = group_outbound['day'].astype(str)
        group_outbound['hour'] = group_outbound['hour'].astype(str)
        group_success['day'] = group_success['day'].astype(str)
        group_success['hour'] = group_success['hour'].astype(str)

        merged = pd.merge(group_outbound, group_success, on=['userId','day','hour'], how='outer').fillna(0)
        merged['success_rate'] = (merged['success_count'] / merged['outbound_count']) * 100

        for agent in selected_agents:
            agent_short = agent_map.get(agent, agent)
            agent_df = merged[merged['userId'] == agent]
            if agent_df.empty:
                st.write(f"No outbound calls for agent: {agent_short}")
                continue

            pivot_srate = agent_df.pivot(index='day', columns='hour', values='success_rate')
            pivot_srate.index = pivot_srate.index.astype(str)
            pivot_srate.columns = pivot_srate.columns.astype(str)
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
# 18. AGENT-BY-AGENT HEATMAPS: Success Rate & Outbound Calls
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
st.subheader("Agent-by-Agent Heatmaps: Success Rate & Outbound Calls")

if len(selected_agents) >= 1 and not successful_outbound_calls.empty and not outbound_calls.empty:
    for agent_id in selected_agents:
        agent_name = agent_map.get(agent_id, agent_id)

        st.markdown(f"### {agent_name}")
        col1, col2 = st.columns(2)

        # Build data
        agent_outbound = outbound_calls[outbound_calls['userId'] == agent_id].copy()
        agent_success  = successful_outbound_calls[successful_outbound_calls['userId'] == agent_id].copy()

        outb_df = agent_outbound.groupby(['day','hour']).size().reset_index(name='outbound_count')
        succ_df = agent_success.groupby(['day','hour']).size().reset_index(name='success_count')
        merged_df = pd.merge(outb_df, succ_df, on=['day','hour'], how='outer').fillna(0)
        merged_df['success_rate'] = (merged_df['success_count'] / merged_df['outbound_count']) * 100

        # Summaries for agent
        total_outbound_left = merged_df['outbound_count'].sum()
        total_outbound_right = total_outbound_left  # same in both columns

        # --- Left Column: Success Rate ---
        with col1:
            st.subheader("Success Rate (%)")
            if total_outbound_left == 0:
                st.write("No outbound calls for this agent.")
            else:
                df_rate = merged_df[['day','hour','success_rate','success_count','outbound_count']].copy()

                fig_rate = px.density_heatmap(
                    df_rate,
                    x='hour',
                    y='day',
                    z='success_rate',
                    histfunc='avg',
                    nbinsx=len(hour_order),
                    nbinsy=len(day_order),
                    color_continuous_scale='RdYlGn',  # or 'Blues', your choice
                    range_color=[0, 100],
                    title="Success Rate by Day/Hour"
                )

                # Enhanced tooltip with success_count & outbound_count
                fig_rate.update_traces(
                    customdata=df_rate[['success_count', 'outbound_count']].values,
                    hovertemplate=(
                        "Hour: %{x}<br>"
                        "Day: %{y}<br>"
                        "Success Rate: %{z:.1f}%<br>"
                        "Successful Calls: %{customdata[0]}<br>"
                        "Total Calls: %{customdata[1]}"
                    ),
                    selector=dict(type='heatmap')
                )
                fig_rate.update_yaxes(categoryorder='array', categoryarray=day_order)
                fig_rate.update_xaxes(categoryorder='array', categoryarray=hour_order)
                fig_rate.update_layout(height=400)
                st.plotly_chart(fig_rate, use_container_width=True)

        # --- Right Column: Outbound Calls ---
        with col2:
            st.subheader("Total Outbound Calls (#)")
            if total_outbound_right == 0:
                st.write("No outbound calls for this agent.")
            else:
                df_calls = merged_df[['day','hour','outbound_count','success_count','success_rate']].copy()

                fig_calls = px.density_heatmap(
                    df_calls,
                    x='hour',
                    y='day',
                    z='outbound_count',
                    histfunc='sum',
                    nbinsx=len(hour_order),
                    nbinsy=len(day_order),
                    color_continuous_scale='Blues',
                    title="Outbound Calls by Day/Hour"
                )

                # Enhanced tooltip with success_count & success_rate
                fig_calls.update_traces(
                    customdata=df_calls[['success_count', 'success_rate']].values,
                    hovertemplate=(
                        "Hour: %{x}<br>"
                        "Day: %{y}<br>"
                        "Total Calls: %{z}<br>"
                        "Successful Calls: %{customdata[0]}<br>"
                        "Success Rate: %{customdata[1]:.1f}%"
                    ),
                    selector=dict(type='heatmap')
                )
                fig_calls.update_yaxes(categoryorder='array', categoryarray=day_order)
                fig_calls.update_xaxes(categoryorder='array', categoryarray=hour_order)
                fig_calls.update_layout(height=400)
                st.plotly_chart(fig_calls, use_container_width=True)

    # (Optional) Summary table for all agents
    st.subheader("Summary Table: Outbound Calls & Success Rate")
    total_success = successful_outbound_calls.groupby('userId').size()
    total_calls_df = outbound_calls.groupby('userId').size()
    summary_df = pd.DataFrame({
        'Total Outbound Calls': total_calls_df,
        'Successful Calls': total_success
    }).fillna(0)
    summary_df['Success Rate (%)'] = (
        summary_df['Successful Calls'] / summary_df['Total Outbound Calls'] * 100
    ).round(1)
    summary_df['Agent'] = summary_df.index.map(agent_map)
    summary_table = summary_df[['Agent','Successful Calls','Total Outbound Calls','Success Rate (%)']]
    st.table(summary_table)

else:
    st.warning("No outbound calls or no agents selected. Cannot show agent-by-agent heatmaps.")


    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 19. AGENT-COLUMNS (Compare Agents Side-by-Side)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Compare Agents Side-by-Side: Successful vs Total Calls")

    if len(selected_agents) >= 2 and not successful_outbound_calls.empty and not outbound_calls.empty:
        # Calculate totals for each agent
        success_totals = successful_outbound_calls.groupby('userId').size().reset_index(name='successful_calls')
        total_calls_df = outbound_calls.groupby('userId').size().reset_index(name='total_calls')

        # Merge the data
        summary = pd.merge(success_totals, total_calls_df, on='userId', how='outer').fillna(0)

        # Add agent names
        summary['agent_name'] = summary['userId'].map(agent_map)

        # Calculate success rate
        summary['success_rate'] = (summary['successful_calls'] / summary['total_calls'] * 100).round(2)

        # Create a figure with grouped bars for each agent
        fig = px.bar(
            summary,
            x=['successful_calls', 'total_calls'],
            y='agent_name',
            orientation='h',
            barmode='group',
            title="Successful vs Total Calls by Agent",
            labels={
                'value': 'Number of Calls',
                'agent_name': 'Agent',
                'variable': 'Call Type'
            },
            color_discrete_map={
                'successful_calls': 'green',
                'total_calls': 'blue'
            },
            text_auto=True
        )

        fig.update_layout(
            showlegend=True,
            legend_title_text='Call Type',
            yaxis={'categoryorder': 'total ascending'}
        )

        st.plotly_chart(fig, use_container_width=True)

        st.write("Detailed Summary:")
        summary_table = summary[['agent_name', 'successful_calls', 'total_calls', 'success_rate']]
        summary_table.columns = ['Agent', 'Successful Calls', 'Total Calls', 'Success Rate (%)']
        st.table(summary_table)

    else:
        st.warning("Comparison not shown. Need 2+ agents selected and some calls present.")

    st.success("Enhanced Dashboard Complete!")
