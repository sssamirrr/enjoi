import streamlit as st
import pandas as pd
import plotly.express as px
import pytz
from datetime import datetime
import numpy as np

def run_text_success_rate_heatmap(messages, day_order, hour_order, agent_map=None):
    """
    # 20. TEXT SUCCESS RATE HEATMAP BY DAY & HOUR

    messages: DataFrame of text messages with columns:
       - userId (str) => agent email
       - direction (str) => 'incoming' or 'outgoing'
       - createdAtET (datetime64[ns, tz]) => timestamp in Eastern Time
       - phoneNumber (str) => or some unique ID for the message recipient
       - (Optional) type == 'message' to differentiate from calls, if needed

    day_order: list of days in desired order, e.g.:
        ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    hour_order: list of 12-hour clock strings, e.g.:
        ["12 AM","01 AM","02 AM","03 AM","04 AM","05 AM","06 AM","07 AM",
         "08 AM","09 AM","10 AM","11 AM","12 PM","01 PM","02 PM","03 PM",
         "04 PM","05 PM","06 PM","07 PM","08 PM","09 PM","10 PM","11 PM"]

    agent_map: dict (optional), mapping full emails to short agent names
        e.g. {"john@enjoiresorts.com": "john", ...}
        If None, the function uses the raw userId.

    Steps in this code:
       1) Identifies 'first outbound messages' each day by userId + phoneNumber
       2) Checks for any incoming reply from the same phoneNumber within 24 hrs
       3) Computes success rate per (agent, day, hour)
       4) Renders a heatmap for each agent, coloring by success rate
       5) Tooltip shows day, hour, success rate, # first messages, # successful
    """

    # Make a copy to avoid modifying the original df
    messages = messages.copy()

    # Create 'day' & 'hour' columns if not present
    messages['day'] = messages['createdAtET'].dt.strftime('%A')
    messages['hour'] = messages['createdAtET'].dt.strftime('%I %p')

    # Debugging: Check initial messages DataFrame
    st.write("### Initial Messages DataFrame:")
    st.write(messages.head())

    # Separate outgoing vs. incoming
    msgs_out = messages[messages['direction'] == 'outgoing'].copy()
    msgs_in  = messages[messages['direction'] == 'incoming'].copy()

    # Debugging: Check separated DataFrames
    st.write("### Outgoing Messages DataFrame:")
    st.write(msgs_out.head())
    st.write("### Incoming Messages DataFrame:")
    st.write(msgs_in.head())

    # Sort outgoing by time
    msgs_out.sort_values(by=['userId','phoneNumber','day','createdAtET'], inplace=True)

    # Debugging: Check sorted outgoing DataFrame
    st.write("### Sorted Outgoing Messages DataFrame:")
    st.write(msgs_out.head())

    # Mark only the FIRST outbound text per (agent, phoneNumber, day)
    msgs_out['is_first_message'] = (
        msgs_out.groupby(['userId','phoneNumber','day'])['createdAtET']
        .rank(method='first')
        .eq(1)
        .astype(int)
    )

    # Debugging: Check 'is_first_message' flag
    st.write("### Outgoing Messages with 'is_first_message' Flag:")
    st.write(msgs_out[['userId', 'phoneNumber', 'day', 'createdAtET', 'is_first_message']].head())

    df_first = msgs_out[msgs_out['is_first_message'] == 1].copy()
    df_first['window_end'] = df_first['createdAtET'] + pd.Timedelta(hours=24)

    # Debugging: Check 'df_first' DataFrame
    st.write("### First Outgoing Messages DataFrame:")
    st.write(df_first.head())

    # Merge each first outbound with potential inbound replies (same phoneNumber)
    df_first = df_first.reset_index(drop=False).rename(columns={'index':'orig_index'})
    merged = df_first.merge(
        msgs_in[['phoneNumber','createdAtET','direction']],
        on='phoneNumber', how='left', suffixes=('_out','_in')
    )

    # Debugging: Check merged DataFrame before applying conditions
    st.write("### Merged DataFrame before Conditions:")
    st.write(merged.head())

    cond = (
        (merged['createdAtET_in'] >= merged['createdAtET_out']) &
        (merged['createdAtET_in'] <= merged['window_end'])
    )
    merged['reply_success'] = np.where(cond, 1, 0)

    # Debugging: Check 'reply_success' column
    st.write("### Merged DataFrame with 'reply_success' Flag:")
    st.write(merged[['userId', 'phoneNumber', 'createdAtET_out', 'createdAtET_in', 'reply_success']].head())

    # If ANY inbound matched for that orig_index, success_flag=1
    success_df = merged.groupby('orig_index')['reply_success'].max().reset_index(name='success_flag')
    df_first = df_first.merge(success_df, on='orig_index', how='left')

    # Replace NaN in 'success_flag' with 0 (no reply)
    df_first['success_flag'] = df_first['success_flag'].fillna(0)

    # Debugging: Check 'df_first' after merging 'success_flag'
    st.write("### 'df_first' DataFrame after Merging 'success_flag':")
    st.write(df_first[['userId', 'phoneNumber', 'day', 'createdAtET', 'success_flag']].head())

    # Summarize by agent, day, hour
    df_first['day'] = df_first['day'].astype(str)
    df_first['hour'] = df_first['hour'].astype(str)

    group_text = df_first.groupby(['userId','day','hour']).agg(
        first_messages=('is_first_message','sum'),
        successful=('success_flag','sum')
    ).reset_index()

    group_text['success_rate'] = (
        group_text['successful'] / group_text['first_messages'] * 100
    ).fillna(0)

    # Debugging: Check grouped data
    st.write("### Grouped Text Data:")
    st.write(group_text.head())

    # Build Heatmaps per agent
    if agent_map is None:
        agent_map = {}

    def get_agent_short(u):
        return agent_map.get(u, u)

    st.subheader("20) Agent Text Success Rate Heatmap by Day & Hour")

    all_agents = group_text['userId'].unique()
    if len(all_agents) == 0:
        st.warning("No text messages found or no 'first messages' to display.")
        return

    for agent_id in all_agents:
        agent_df = group_text[group_text['userId'] == agent_id].copy()
        if agent_df.empty:
            continue

        pivot_rate  = agent_df.pivot(index='day', columns='hour', values='success_rate').fillna(0)
        pivot_first = agent_df.pivot(index='day', columns='hour', values='first_messages').fillna(0)
        pivot_succ  = agent_df.pivot(index='day', columns='hour', values='successful').fillna(0)

        pivot_rate  = pivot_rate.reindex(index=day_order, columns=hour_order, fill_value=0)
        pivot_first = pivot_first.reindex(index=day_order, columns=hour_order, fill_value=0)
        pivot_succ  = pivot_succ.reindex(index=day_order, columns=hour_order, fill_value=0)

        agent_title = f"{get_agent_short(agent_id)} ({agent_id})"

        fig = px.imshow(
            pivot_rate,
            color_continuous_scale='Blues',
            range_color=[0,100],
            labels=dict(x="Hour", y="Day", color="Rate (%)"),
            title=f"Agent: {agent_title} - Text Success Rate"
        )

        # Build 2D custom hover text
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

    # Overall Summary Table
    sum_agent = group_text.groupby('userId').agg(
        total_first=('first_messages','sum'),
        total_success=('successful','sum')
    ).reset_index()
    sum_agent['success_rate'] = (sum_agent['total_success'] / sum_agent['total_first'] * 100).round(1).fillna(0)
    sum_agent['Agent'] = sum_agent['userId'].map(get_agent_short)

    # Debugging: Check summary table
    st.write("### Texting Summary by Agent:")
    st.write(sum_agent[['Agent', 'userId', 'total_first', 'total_success', 'success_rate']])

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

    if openphone_data['createdAtET'].empty:
        st.error("No 'createdAtET' data available after processing.")
        return

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

    if not all_agents:
        st.warning("No agents found with '@enjoiresorts.com' domain.")
        return

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

    if not selected_short_names:
        st.warning("Please select at least one agent to proceed.")
        return

    # Convert user’s choice (shortened name) back to the full email
    selected_agents = [
        full_email
        for full_email, short_name in agent_map.items()
        if short_name in selected_short_names
    ]

    # Filter only selected agents
    openphone_data = openphone_data[openphone_data['userId'].isin(selected_agents)]

    if openphone_data.empty:
        st.warning("No data available for the selected agents and date range.")
        return

    # ----------------------------------------------------------------------
    # CREATE A "phoneNumber" COLUMN FOR #20 (TEXT SUCCESS RATE)
    # For outgoing => use the 'to' column
    # For incoming => use the 'from' column
    # ----------------------------------------------------------------------
    openphone_data['phoneNumber'] = np.where(
        openphone_data['direction'] == 'incoming',
        openphone_data['from'],
        openphone_data['to']
    )

    # Split multiple phone numbers into separate rows
    openphone_data['phoneNumber'] = openphone_data['phoneNumber'].astype(str)  # Ensure all are strings
    openphone_data['phoneNumber'] = openphone_data['phoneNumber'].str.split(',')
    openphone_data = openphone_data.explode('phoneNumber')
    openphone_data['phoneNumber'] = openphone_data['phoneNumber'].str.strip()

    # Drop rows with missing phoneNumber
    openphone_data = openphone_data.dropna(subset=['phoneNumber'])

    # Debugging: Check after splitting phone numbers
    st.write("### Data after Splitting and Exploding 'phoneNumber':")
    st.write(openphone_data[['phoneNumber']].head())

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 4. SPLIT: CALLS VS. MESSAGES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    calls = openphone_data[openphone_data['type'] == 'call']
    messages = openphone_data[openphone_data['type'] == 'message']

    # Debugging: Check split DataFrames
    st.write("### Calls DataFrame Sample:")
    st.write(calls.head())
    st.write("### Messages DataFrame Sample:")
    st.write(messages.head())

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

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 19. AGENT-COLUMNS (Compare Agents Side-by-Side)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 20. SMS FOLLOW-UP CALL EFFECTIVENESS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("SMS Follow-up Call Effectiveness")

    # Slider for time window between SMS and Call
    time_window_hours = st.slider(
        "Time between initial SMS and follow-up Call (hours)",
        min_value=1,
        max_value=24,
        value=24,
        step=1
    )

    if not messages.empty:
        # Define outgoing SMS
        sms_df = messages[
            (messages['direction'] == 'outgoing') &
            (messages['type'] == 'message')
        ].copy()

        # Define successful outgoing calls
        successful_calls_df = openphone_data[
            (openphone_data['direction'] == 'outgoing') &
            (openphone_data['type'] == 'call') &
            (openphone_data['status'] == 'completed') &
            (openphone_data['duration'] > 0)
        ].copy()

        # Debugging: Check SMS and Successful Calls DataFrames
        st.write("### SMS DataFrame:")
        st.write(sms_df.head())
        st.write("### Successful Calls DataFrame:")
        st.write(successful_calls_df.head())

        # Check if both DataFrames have necessary data
        if sms_df.empty or successful_calls_df.empty:
            st.warning("Not enough data to analyze SMS Follow-up Call Effectiveness.")
        else:
            # Sort DataFrames
            sms_df = sms_df.sort_values(['userId', 'phoneNumber', 'sms_time'])
            successful_calls_df = successful_calls_df.sort_values(['userId', 'phoneNumber', 'call_time'])

            # Debugging: Verify sorting
            st.write("### SMS DataFrame after Sorting:")
            st.write(sms_df.head())
            st.write("### Successful Calls DataFrame after Sorting:")
            st.write(successful_calls_df.head())

            # Rename columns for merge_asof
            sms_df = sms_df.rename(columns={'createdAtET': 'sms_time'})
            successful_calls_df = successful_calls_df.rename(columns={'createdAtET': 'call_time'})

            # Perform merge_asof to find the first call after SMS within the time window
            merged_calls = pd.merge_asof(
                sms_df,
                successful_calls_df,
                left_on='sms_time',
                right_on='call_time',
                by=['userId', 'phoneNumber'],
                direction='forward',
                tolerance=pd.Timedelta(hours=time_window_hours)
            )

            # Debugging: Check merged DataFrame
            st.write("### Merged Calls DataFrame:")
            st.write(merged_calls.head())

            # Calculate time difference
            merged_calls['time_diff_hours'] = (merged_calls['call_time'] - merged_calls['sms_time']).dt.total_seconds() / 3600

            # Drop rows where no call was found within the time window
            merged_calls = merged_calls.dropna(subset=['call_time'])

            # Only keep calls that occurred after SMS
            merged_calls = merged_calls[merged_calls['time_diff_hours'] >= 0]

            # Debugging: Check after filtering
            st.write("### Merged Calls DataFrame after Filtering:")
            st.write(merged_calls.head())

            # Now, each row represents an SMS followed by a successful Call within the time window
            # Count total interactions
            total_interactions = len(merged_calls)

            # Count interactions per agent
            interactions_per_agent = merged_calls.groupby('userId').size().reset_index(name='interactions')
            interactions_per_agent['Agent'] = interactions_per_agent['userId'].map(agent_map)

            # Display statistics
            st.markdown(f"**Total SMS Follow-up Call Interactions within {time_window_hours} hours:** {total_interactions}")
            st.subheader(f"Interactions per Agent within {time_window_hours} hours")
            st.dataframe(interactions_per_agent[['Agent', 'interactions']])

            # Optional: Success Rate per Agent (if needed)
            # Here, since we only count successful calls, it's equivalent to the interaction count
            # If you have a different definition, adjust accordingly

    else:
        st.warning("No text messages available to analyze SMS Follow-up Call Effectiveness.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 21. SMS SUCCESS RATE HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Run #20: Text Success Rate Heatmap - Initial outbound message received a response within 24 hours") 
    # If phoneNumber doesn't exist, #20 won't work
    if 'phoneNumber' not in messages.columns:
        st.warning("No 'phoneNumber' column found in messages. #20 requires it to group texts by recipient.")
    else:
        run_text_success_rate_heatmap(messages, day_order, hour_order, agent_map)

    st.success("Enhanced Dashboard Complete!")

# Optionally, define a main() if you prefer:
# def main():
#     run_openphone_tab()
#
# if __name__ == "__main__":
#     main()
