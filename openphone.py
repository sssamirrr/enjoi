import streamlit as st
import pandas as pd
import plotly.express as px
import pytz
from datetime import datetime
import numpy as np

###############################################################################
# 20) Text Success Rate Heatmap (function)
###############################################################################
def run_text_success_rate_heatmap(messages, day_order, hour_order, agent_map=None):
    """
    # 20. TEXT SUCCESS RATE HEATMAP BY DAY & HOUR
    
    1) Identifies 'first outbound messages' each day by (userId + phoneNumber)
    2) Checks for any *incoming* reply within 24 hours
    3) Builds a day-hour heatmap of 'success rate' (the fraction of first msgs
       that got an incoming reply).
    """

    # Make a copy to avoid modifying the original
    messages = messages.copy()

    # Ensure 'day' & 'hour' columns
    messages['day'] = messages['createdAtET'].dt.strftime('%A')
    messages['hour'] = messages['createdAtET'].dt.strftime('%I %p')

    # Separate outgoing vs incoming
    msgs_out = messages[messages['direction'] == 'outgoing'].copy()
    msgs_in  = messages[messages['direction'] == 'incoming'].copy()

    # Sort by time
    msgs_out.sort_values(by=['userId','phoneNumber','day','createdAtET'], inplace=True)

    # Mark only the FIRST outbound text per (userId, phoneNumber, day)
    msgs_out['is_first_message'] = (
        msgs_out.groupby(['userId','phoneNumber','day'])['createdAtET']
        .rank(method='first')
        .eq(1)
        .astype(int)
    )

    # Now create a 24-hr window
    df_first = msgs_out[msgs_out['is_first_message'] == 1].copy()
    df_first['window_end'] = df_first['createdAtET'] + pd.Timedelta(hours=24)

    # Merge each "first outbound" with potential inbound replies
    df_first = df_first.reset_index(drop=False).rename(columns={'index':'orig_index'})
    merged = df_first.merge(
        msgs_in[['phoneNumber','createdAtET','direction']],
        on='phoneNumber', how='left', suffixes=('_out','_in')
    )

    # Condition: inbound in [outbound_time, outbound_time + 24h]
    cond = (
        (merged['createdAtET_in'] >= merged['createdAtET_out']) &
        (merged['createdAtET_in'] <= merged['window_end'])
    )
    merged['reply_success'] = np.where(cond, 1, 0)

    # If ANY inbound matched for that orig_index => success_flag=1
    success_df = merged.groupby('orig_index')['reply_success'].max().reset_index(name='success_flag')
    df_first = df_first.merge(success_df, on='orig_index', how='left')

    # Summarize
    df_first['day']  = df_first['day'].astype(str)
    df_first['hour'] = df_first['hour'].astype(str)

    group_text = df_first.groupby(['userId','day','hour']).agg(
        first_messages=('is_first_message','sum'),
        successful=('success_flag','sum')
    ).reset_index()

    group_text['success_rate'] = (group_text['successful'] / group_text['first_messages'] * 100).fillna(0)

    # If no agent_map, default
    if agent_map is None:
        agent_map = {}

    def get_agent_short(u):
        return agent_map.get(u, u)

    st.subheader("20) Agent Text Success Rate Heatmap by Day & Hour")

    all_agents = group_text['userId'].unique()
    if len(all_agents) == 0:
        st.warning("No text messages found or no 'first messages' to display.")
        return

    # Build Heatmaps
    for agent_id in all_agents:
        agent_df = group_text[group_text['userId'] == agent_id].copy()
        if agent_df.empty:
            continue

        pivot_rate  = agent_df.pivot(index='day', columns='hour', values='success_rate').fillna(0)
        pivot_first = agent_df.pivot(index='day', columns='hour', values='first_messages').fillna(0)
        pivot_succ  = agent_df.pivot(index='day', columns='hour', values='successful').fillna(0)

        # Reindex
        pivot_rate  = pivot_rate.reindex(index=day_order, columns=hour_order, fill_value=0)
        pivot_first = pivot_first.reindex(index=day_order, columns=hour_order, fill_value=0)
        pivot_succ  = pivot_succ.reindex(index=day_order, columns=hour_order, fill_value=0)

        agent_title = f"{get_agent_short(agent_id)} ({agent_id})"

        fig = px.imshow(
            pivot_rate,
            color_continuous_scale='Blues',
            range_color=[0, 100],
            labels=dict(x="Hour", y="Day", color="Rate (%)"),
            title=f"Agent: {agent_title} - Text Success Rate"
        )

        hover_text = []
        for d in day_order:
            row_text = []
            for h in hour_order:
                r_val   = pivot_rate.loc[d, h]
                f_count = pivot_first.loc[d, h]
                s_count = pivot_succ.loc[d, h]
                txt = (
                    f"Day: {d}<br>Hour: {h}<br>"
                    f"Success Rate: {r_val:.1f}%<br>"
                    f"First Msgs: {int(f_count)}<br>"
                    f"Successful: {int(s_count)}"
                )
                row_text.append(txt)
            hover_text.append(row_text)

        fig.update_traces(
            customdata=hover_text,
            hovertemplate="%{customdata}<extra></extra>"
        )
        fig.update_xaxes(side="top")
        fig.update_layout(height=400, margin=dict(l=50, r=50, t=50, b=50))

        st.plotly_chart(fig, use_container_width=True)

    # Overall Summary
    sum_agent = group_text.groupby('userId').agg(
        total_first=('first_messages','sum'),
        total_success=('successful','sum')
    ).reset_index()
    sum_agent['success_rate'] = (sum_agent['total_success'] / sum_agent['total_first'] * 100).round(1).fillna(0)
    sum_agent['Agent'] = sum_agent['userId'].map(get_agent_short)

    st.subheader("Texting Summary by Agent")
    st.dataframe(sum_agent[['Agent', 'userId', 'total_first', 'total_success', 'success_rate']])


###############################################################################
# 22) Compare Call Durations: Per-Agent Preceding Text Logic (No earliest contact)
###############################################################################
def run_call_duration_preceded_by_text(messages, calls, default_time_window=8):
    """
    # 22. CALL DURATION COMPARISON: WITH vs. WITHOUT A PRECEDING TEXT (Per-Agent)

    Steps:
      1) Filter calls to outbound only (duration >= 0).
      2) For each call, check if the *same userId* had an outbound text
         in [call_time - X hours, call_time).
      3) Compare avg call duration for “preceded by text” vs. “not preceded,”
         both overall (all selected agents combined) and per agent.

    Important:
      - This function expects that `messages` is *not* filtered by userId. Keep
        *all* messages so that each agent sees their own texts. Other agents'
        messages won't interfere, because merges happen on (userId, phoneNumber).
      - `calls` can be filtered to only the agents you want to display. 
        That won't affect per-agent logic, since each agent will still only see 
        their own texts in the merges.
    """

    import numpy as np
    import pandas as pd
    import plotly.express as px
    import streamlit as st

    st.subheader("22) Compare Call Durations (Per-Agent Preceding Text Logic)")

    if messages.empty or calls.empty:
        st.warning("No messages or calls to analyze for #22.")
        return

    # Ask user how many hours count as "preceded by text"
    time_window_hours = st.slider(
        "Time Window (hours) for a Preceding Outbound Text (#22)",
        min_value=1, max_value=72, value=default_time_window, step=1
    )

    # Require a 'duration' column
    if 'duration' not in calls.columns:
        st.warning("No 'duration' column found in calls. Cannot measure durations for #22.")
        return

    # (1) Keep only outbound calls with valid duration
    calls_out = calls[
        (calls['direction'] == 'outgoing') &
        (calls['duration'] >= 0)
    ].copy()
    if calls_out.empty:
        st.warning("No outbound calls left after filtering for #22.")
        return

    calls_out['call_time'] = pd.to_datetime(calls_out['createdAtET'], errors='coerce')

    # (2) All outgoing texts (not filtered by agent)
    msgs_out = messages[
        (messages['direction'] == 'outgoing') &
        (messages['type'] == 'message')
    ].copy()
    msgs_out['text_time'] = pd.to_datetime(msgs_out['createdAtET'], errors='coerce')

    # Sort them
    msgs_out.sort_values(by=['userId','phoneNumber','text_time'], inplace=True)
    calls_out.sort_values(by=['userId','phoneNumber','call_time'], inplace=True)

    # For each call, "preceded" means a text in [call_time - X hrs, call_time)
    calls_out['min_text_time'] = calls_out['call_time'] - pd.Timedelta(hours=time_window_hours)

    # Merge on (userId, phoneNumber)
    merged = calls_out.merge(
        msgs_out[['userId','phoneNumber','text_time']],
        on=['userId','phoneNumber'],
        how='left'
    )

    # Condition: text_time in [call_time - X hrs, call_time)
    cond = (
        (merged['text_time'] >= merged['min_text_time']) &
        (merged['text_time'] < merged['call_time'])
    )
    merged['text_preceded'] = np.where(cond, 1, 0)

    # If ANY text_preceded=1 for that call => call_preceded_flag=1
    merged = merged.reset_index(drop=False).rename(columns={'index':'call_index'})
    preceded_df = merged.groupby('call_index')['text_preceded'].max().reset_index(name='call_preceded_flag')

    calls_out = calls_out.reset_index(drop=False).rename(columns={'index':'orig_call_idx'})
    calls_out = calls_out.merge(preceded_df, left_on='orig_call_idx', right_on='call_index', how='left')
    calls_out['call_preceded_flag'] = calls_out['call_preceded_flag'].fillna(0).astype(int)

    # (3a) Overall comparison
    comp_df = calls_out.groupby('call_preceded_flag')['duration'].mean().reset_index()
    comp_df['call_preceded_flag'] = comp_df['call_preceded_flag'].map({
        0: 'No preceding text',
        1: 'Preceded by text'
    })
    comp_df.rename(columns={'duration': 'avg_duration'}, inplace=True)

    st.markdown("#### Overall: Combined (All Selected Agents)")
    fig = px.bar(
        comp_df,
        x='call_preceded_flag',
        y='avg_duration',
        color='call_preceded_flag',
        labels=dict(call_preceded_flag="Preceding Text?", avg_duration="Avg Duration (s)"),
        title="Avg Call Duration: w/o vs. w/ Preceding Text (#22)"
    )
    fig.update_layout(showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
    st.table(comp_df)

    # (3b) Per-Agent comparison
    st.markdown("#### Per-Agent: Compare Preceded vs. Not Preceded (#22)")
    agent_df = calls_out.groupby(['userId','call_preceded_flag'])['duration'].mean().reset_index()
    agent_df.rename(columns={'duration': 'avg_duration'}, inplace=True)
    agent_df['call_preceded_flag'] = agent_df['call_preceded_flag'].map({
        0: 'No preceding text',
        1: 'Preceded by text'
    })

    fig_per_agent = px.bar(
        agent_df,
        x='avg_duration',
        y='userId',
        color='call_preceded_flag',
        orientation='h',
        barmode='group',
        labels=dict(
            userId="Agent (userId)",
            avg_duration="Avg Duration (sec)",
            call_preceded_flag="Preceding Text?"
        ),
        title="Call Duration by Agent: w/o vs. w/ Preceding Text"
    )
    fig_per_agent.update_layout(legend_title_text="Preceding Text?")
    st.plotly_chart(fig_per_agent, use_container_width=True)
    st.dataframe(agent_df)

    # ~Optional~ If you want zero-height bars for missing combos, pivot/unstack:
    # import itertools
    # all_agents = calls_out['userId'].unique()
    # all_flags = [0, 1]
    # combos = pd.DataFrame(
    #     itertools.product(all_agents, all_flags),
    #     columns=['userId','call_preceded_flag']
    # )
    # grouped = calls_out.groupby(['userId','call_preceded_flag'])['duration'].mean().reset_index(name='avg_duration')
    # forced_df = combos.merge(grouped, on=['userId','call_preceded_flag'], how='left').fillna(0)
    # forced_df['call_preceded_flag'] = forced_df['call_preceded_flag'].map({0: 'No preceding text', 1: 'Preceded by text'})
    # # Then build your chart from forced_df to ensure every agent has both bars (even if 0).


###############################################################################
# Main function
###############################################################################
def run_openphone_tab():
    st.header("Enhanced OpenPhone Operations Dashboard")

    # 1) UPLOAD CSV
    uploaded_file = st.file_uploader("Upload OpenPhone CSV File", type=["csv"])
    if not uploaded_file:
        st.warning("Please upload the OpenPhone CSV file to proceed.")
        return

    openphone_data = pd.read_csv(uploaded_file)

    # 2) TIME ZONE CONVERSION
    pacific_tz = pytz.timezone("America/Los_Angeles")
    eastern_tz = pytz.timezone("America/New_York")

    openphone_data['createdAtPT'] = pd.to_datetime(openphone_data['createdAtPT'], errors='coerce')
    openphone_data = openphone_data.dropna(subset=['createdAtPT'])

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

    # 3) FILTERS
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

    # Filter by date
    openphone_data = openphone_data[
        (openphone_data['createdAtET'].dt.date >= start_date) &
        (openphone_data['createdAtET'].dt.date <= end_date)
    ]

    # Agent filter
    if 'userId' not in openphone_data.columns:
        st.error("No 'userId' column found in the dataset.")
        return

    all_agents = sorted([
        agent for agent in openphone_data['userId'].dropna().unique()
        if agent.endswith("@enjoiresorts.com")
    ])
    def short_agent_name(full_email):
        return full_email.replace("@enjoiresorts.com", "")

    agent_map = {agent: short_agent_name(agent) for agent in all_agents}
    agent_choices = list(agent_map.values())

    selected_short_names = st.multiselect(
        "Select Agents",
        agent_choices,
        default=[]
    )
    selected_agents = [
        full_email
        for full_email, short_name in agent_map.items()
        if short_name in selected_short_names
    ]
    openphone_data = openphone_data[openphone_data['userId'].isin(selected_agents)]

    # Create phoneNumber col
    openphone_data['phoneNumber'] = np.where(
        openphone_data['direction'] == 'incoming',
        openphone_data['from'],
        openphone_data['to']
    )

    # 4) SPLIT CALLS VS MESSAGES
    calls = openphone_data[openphone_data['type'] == 'call']
    messages = openphone_data[openphone_data['type'] == 'message']

    # 5) BOOKING / CONVERSION
    bookings = openphone_data[openphone_data['status'] == 'booked']
    total_bookings = len(bookings)

    call_conversion_rate = (
        len(calls[calls['status'] == 'booked']) / len(calls) * 100
        if len(calls) else 0
    )
    message_conversion_rate = (
        len(messages[messages['status'] == 'booked']) / len(messages) * 100
        if len(messages) else 0
    )

    # 6) AGENT PERFORMANCE
    agent_bookings = bookings.groupby('userId').size().reset_index(name='total_bookings')
    agent_calls    = calls.groupby('userId').size().reset_index(name='total_calls')

    agent_performance = pd.merge(agent_calls, agent_bookings, on='userId', how='outer').fillna(0)
    agent_performance['booking_rate'] = (
        agent_performance['total_bookings'] / agent_performance['total_calls'] * 100
    ).fillna(0)
    agent_performance['Agent'] = agent_performance['userId'].map(agent_map)

    # 7) Define day_order & hour_order
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

    # 8) OUTBOUND CALL SUCCESS
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
        if len(outbound_calls) else 0
    )

    agent_success = successful_outbound_calls.groupby('userId').size().reset_index(name='successful_calls')
    agent_outbound = outbound_calls.groupby('userId').size().reset_index(name='total_outbound_calls')
    agent_success_rate = pd.merge(agent_outbound, agent_success, on='userId', how='outer').fillna(0)
    agent_success_rate['success_rate'] = (
        agent_success_rate['successful_calls'] / agent_success_rate['total_outbound_calls'] * 100
    ).fillna(0)
    agent_success_rate['Agent'] = agent_success_rate['userId'].map(agent_map)

    # 9) KEY METRICS
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

    # 10) HOURLY TRENDS
    st.subheader("Hourly Trends (12 AM -> 11 PM)")
    if not calls.empty:
        calls['hour'] = pd.Categorical(calls['hour'], categories=hour_order, ordered=True)
        hourly_stats = calls.groupby(['hour','direction']).size().reset_index(name='count')
        fig = px.bar(hourly_stats, x='hour', y='count', color='direction',
                     barmode='group', title="Calls by Hour")
        st.plotly_chart(fig)
    else:
        st.warning("No calls found in range/filters.")

    # 11) CALL DURATION ANALYSIS
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

    # 12) INCOMING MESSAGE ANALYSIS
    st.subheader("Incoming Messages by Hour")
    if not messages.empty:
        messages['hour'] = pd.Categorical(messages['hour'], categories=hour_order, ordered=True)
        inc_msgs = messages[messages['direction'] == 'incoming']
        inc_counts = inc_msgs.groupby('hour').size().reset_index(name='count')
        fig = px.bar(inc_counts, x='hour', y='count', title="Incoming Msgs by Hour (12 AM -> 11 PM)")
        st.plotly_chart(fig)

        # day-hour heatmap
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

    # 13) AGENT PERFORMANCE (CALLS & BOOKINGS)
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

    # 14) AGENT OUTBOUND SUCCESS RATE
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

    # 15) CALL VOLUME HEATMAP
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

    # 16) SUCCESSFUL OUTBOUND CALLS HEATMAP
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

    # 17) AGENT SUCCESS RATE HEATMAP (Day & Hour)
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

    # 18) AGENT-BY-AGENT HEATMAPS: Combined
    st.subheader("Agent-by-Agent Heatmaps: Success Rate & Outbound Calls (Combined)")
    if len(selected_agents) >= 1 and not successful_outbound_calls.empty and not outbound_calls.empty:
        for agent_id in selected_agents:
            agent_name = agent_map.get(agent_id, agent_id)
            st.markdown(f"### {agent_name}")

            agent_outbound = outbound_calls[outbound_calls['userId'] == agent_id].copy()
            agent_success  = successful_outbound_calls[successful_outbound_calls['userId'] == agent_id].copy()

            outb_df = agent_outbound.groupby(['day','hour']).size().reset_index(name='outbound_count')
            succ_df = agent_success.groupby(['day','hour']).size().reset_index(name='success_count')
            merged_df = pd.merge(outb_df, succ_df, on=['day','hour'], how='outer').fillna(0)
            merged_df['success_rate'] = (merged_df['success_count'] / merged_df['outbound_count']) * 100

            pivot_rate     = merged_df.pivot(index='day', columns='hour', values='success_rate')
            pivot_outbound = merged_df.pivot(index='day', columns='hour', values='outbound_count')
            pivot_success  = merged_df.pivot(index='day', columns='hour', values='success_count')

            pivot_rate     = pivot_rate.reindex(index=day_order, columns=hour_order).fillna(0)
            pivot_outbound = pivot_outbound.reindex(index=day_order, columns=hour_order).fillna(0)
            pivot_success  = pivot_success.reindex(index=day_order, columns=hour_order).fillna(0)

            fig_combined = px.imshow(
                pivot_rate,
                color_continuous_scale='Blues',
                range_color=[0, 100],
                labels=dict(x="Hour", y="Day", color="Success Rate (%)"),
                title="Success Rate (Color) + Calls Tooltip"
            )

            # Build custom hover text
            hover_text = [
                [
                    f"Hour: {hour}<br>Day: {day}"
                    f"<br>Success Rate: {pivot_rate.loc[day, hour]:.1f}%"
                    f"<br>Successful: {int(float(pivot_success.loc[day, hour]))}"
                    f"<br>Total: {int(float(pivot_outbound.loc[day, hour]))}"
                    for hour in pivot_rate.columns
                ]
                for day in pivot_rate.index
            ]

            fig_combined.update_traces(
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover_text
            )
            fig_combined.update_xaxes(side="top")
            fig_combined.update_layout(height=300, margin=dict(l=50, r=50, t=50, b=20))

            st.plotly_chart(fig_combined, use_container_width=True)

        summary_df = pd.DataFrame({
            'Total': outbound_calls.groupby('userId').size(),
            'Success': successful_outbound_calls.groupby('userId').size()
        }).fillna(0)
        summary_df['Rate %'] = (summary_df['Success'] / summary_df['Total'] * 100).round(1)
        summary_df['Agent'] = summary_df.index.map(agent_map)
        st.table(summary_df[['Agent', 'Success', 'Total', 'Rate %']])
    else:
        st.warning("No outbound calls or no agents selected.")

    # 19) Compare Agents Side-by-Side
    st.subheader("Compare Agents Side-by-Side: Successful vs Total Calls")
    if len(selected_agents) >= 2 and not successful_outbound_calls.empty and not outbound_calls.empty:
        success_totals = successful_outbound_calls.groupby('userId').size().reset_index(name='successful_calls')
        total_calls_df = outbound_calls.groupby('userId').size().reset_index(name='total_calls')

        summary = pd.merge(success_totals, total_calls_df, on='userId', how='outer').fillna(0)
        summary['agent_name'] = summary['userId'].map(agent_map)
        summary['success_rate'] = (summary['successful_calls'] / summary['total_calls'] * 100).round(2)

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

    # CALLING #20
    if not messages.empty:
        st.subheader("Run #20: Text Success Rate Heatmap")
        if 'phoneNumber' not in messages.columns:
            st.warning("No 'phoneNumber' column found in messages for #20.")
        else:
            run_text_success_rate_heatmap(messages, day_order, hour_order, agent_map)
    else:
        st.warning("No text messages to analyze for #20.")

    # CALLING #22
    if not messages.empty and not calls.empty:
        run_call_duration_preceded_by_text(messages, calls, default_time_window=8)
    else:
        st.warning("No messages or calls to compare call durations (#22).")

    st.success("Enhanced Dashboard Complete!")


# Optional main
# def main():
#     run_openphone_tab()
#
# if __name__ == "__main__":
#     main()
