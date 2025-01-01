import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pytz
from datetime import datetime

def run_openphone_tab():
    st.header("Enhanced OpenPhone Operations Dashboard (with Preceding Text Stats & 2-Column Agent Comparison)")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 1. UPLOAD FILE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    uploaded_file = st.file_uploader("Upload OpenPhone CSV File", type=["csv"])
    if not uploaded_file:
        st.warning("Please upload the OpenPhone CSV file to proceed.")
        return

    # 1A) If your CSV has no header, define column names. Adjust as needed:
    colnames = [
        "timestamp1", "col2", "userId", "timestamp2", "userIdAgain",
        "col6", "col7", "agentName", "direction", "duration", 
        "phoneNumber", "col12", "col13", "col14", "col15", 
        "callStatus", "col17", "col18", "col19", "col20",
        "col21", "col22", "col23", "col24", "col25", 
        "col26", "col27", "col28", "col29", "col30"
        # Make sure you have enough names to match the CSV columns
    ]

    # If your CSV already has headers, remove `names=colnames, header=None`
    openphone_data = pd.read_csv(
        uploaded_file,
        names=colnames,
        header=None
        # If your CSV has a header row, do: header=0 and remove 'names='
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 2. TIME ZONE CONVERSION (PT -> ET)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    pacific_tz = pytz.timezone("America/Los_Angeles")
    eastern_tz = pytz.timezone("America/New_York")

    # We assume your "createdAtPT" is in column "timestamp1"
    # If your CSV stores the timestamp differently, adapt this line:
    openphone_data['createdAtPT'] = pd.to_datetime(openphone_data['timestamp1'], errors='coerce')
    openphone_data = openphone_data.dropna(subset=['createdAtPT'])  # remove rows w/o valid time

    openphone_data['createdAtET'] = (
        openphone_data['createdAtPT']
        .dt.tz_localize(pacific_tz, ambiguous='infer', nonexistent='shift_forward')
        .dt.tz_convert(eastern_tz)
    )

    # If there's an answeredAtPT column, adapt similarly if needed:
    # if 'answeredAtPT' in openphone_data.columns:
    #     ...

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 3. FILTERS (DATE RANGE)
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
        st.error("Error: Start date must be before end date.")
        return

    # Filter data by date range
    openphone_data = openphone_data[
        (openphone_data['createdAtET'].dt.date >= start_date) &
        (openphone_data['createdAtET'].dt.date <= end_date)
    ]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 3B. FILTERS (AGENTS @enjoiresorts.com)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    if 'userId' not in openphone_data.columns:
        st.error("No 'userId' column found in the dataset.")
        return

    all_emails = [
        email for email in openphone_data['userId'].dropna().unique()
        if isinstance(email, str) and email.endswith('@enjoiresorts.com')
    ]
    if not all_emails:
        st.warning("No agents found with '@enjoiresorts.com' in this date range.")
        return

    display_names = [email.split('@')[0] for email in all_emails]   # short names
    agent_map = dict(zip(display_names, all_emails))                # short -> full email

    selected_short_names = st.multiselect(
        "Select Agents (Enjoi Resorts Only)",
        options=sorted(display_names),
        default=[]
    )
    selected_emails = [agent_map[name] for name in selected_short_names]
    openphone_data = openphone_data[openphone_data['userId'].isin(selected_emails)]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 4. SPLIT: CALLS VS. MESSAGES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # If 'type' doesn't exist, define it from e.g. 'col23' if it says 'call' or 'message'
    # Adjust if your CSV has the call/message indicator in col23:
    openphone_data['type'] = openphone_data['col23']  # e.g. "call"/"message"

    calls = openphone_data[openphone_data['type'] == 'call']
    messages = openphone_data[openphone_data['type'] == 'message']

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 5. CALCULATE BOOKING & CONVERSION RATES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Suppose 'status' is from callStatus col
    openphone_data['status'] = openphone_data['callStatus']
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
    # 7. day/hour + ordering
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
    # 8. OUTBOUND CALL SUCCESS RATE
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Outbound Call Success Rate")

    max_duration = 60
    if ('duration' in openphone_data.columns) and not calls['duration'].isnull().all():
        # if your CSV has "duration" in col9, adapt e.g. calls['duration'] = calls['col9'].astype(int)
        max_duration = int(calls['duration'].max())

    min_success_duration = st.slider(
        "Minimum Call Duration (seconds) to Count as Success",
        min_value=0,
        max_value=max_duration,
        value=30
    )

    # If direction is in "direction" col:
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
        st.metric("Call Conv Rate", f"{call_conversion_rate:.2f}%")
    with c3:
        st.metric("Msg Conv Rate", f"{message_conversion_rate:.2f}%")
    with c4:
        st.metric("Outbound Success Rate", f"{success_rate:.2f}%")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 10. HOURLY TRENDS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Hourly Trends")
    if not calls.empty:
        calls['hour'] = pd.Categorical(calls['hour'], categories=hour_order, ordered=True)
        hourly_stats = calls.groupby(['hour','direction']).size().reset_index(name='count')
        fig = px.bar(
            hourly_stats,
            x='hour',
            y='count',
            color='direction',
            barmode='group',
            title='Call Volume by Hour (12 AM -> 11 PM)'
        )
        st.plotly_chart(fig)
    else:
        st.warning("No calls found in the selected filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 11. CALL DURATION ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Call Duration Analysis")
    if 'duration' in openphone_data.columns and not calls['duration'].isnull().all() and not calls.empty:
        mean_duration = calls['duration'].mean()
        long_calls = calls[calls['duration'] >= mean_duration]

        if not long_calls.empty:
            long_calls['hour'] = pd.Categorical(long_calls['hour'], categories=hour_order, ordered=True)
            long_hourly = long_calls.groupby('hour').size().reset_index(name='count')
            fig = px.bar(long_hourly, x='hour', y='count',
                         title='Long Calls (Above Mean) by Hour')
            st.plotly_chart(fig)

        # Heatmap of Average Call Duration (day vs. hour)
        dur_data = calls.groupby(['day','hour'])['duration'].mean().reset_index()
        if not dur_data.empty:
            pivot_dur = dur_data.pivot(index='day', columns='hour', values='duration')
            pivot_dur.index = pivot_dur.index.astype(str)
            pivot_dur.columns = pivot_dur.columns.astype(str)
            adays = [d for d in day_order if d in pivot_dur.index]
            ahours = [h for h in hour_order if h in pivot_dur.columns]
            pivot_dur = pivot_dur.reindex(index=adays, columns=ahours).fillna(0)

            fig = px.imshow(
                pivot_dur,
                title="Heatmap of Avg Call Duration by Day & Hour",
                labels=dict(x="Hour", y="Day", color="Duration (s)")
            )
            st.plotly_chart(fig)
    else:
        st.warning("No valid 'duration' data or no calls in filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 12. INCOMING MESSAGE ANALYSIS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Incoming Messages by Hour")
    if not messages.empty:
        messages['hour'] = pd.Categorical(messages['hour'], categories=hour_order, ordered=True)
        inc_msgs = messages[messages['direction'] == 'incoming']
        inc_counts = inc_msgs.groupby('hour').size().reset_index(name='count')

        fig = px.bar(inc_counts, x='hour', y='count', title='Incoming Messages by Hour (12 AM -> 11 PM)')
        st.plotly_chart(fig)

        st.subheader("Message Volume Heatmap")
        msg_heat_data = messages.groupby(['day','hour']).size().reset_index(name='count')
        if not msg_heat_data.empty:
            pivot_msg = msg_heat_data.pivot(index='day', columns='hour', values='count')
            pivot_msg.index = pivot_msg.index.astype(str)
            pivot_msg.columns = pivot_msg.columns.astype(str)
            adays = [d for d in day_order if d in pivot_msg.index]
            ahours = [h for h in hour_order if h in pivot_msg.columns]
            pivot_msg = pivot_msg.reindex(index=adays, columns=ahours).fillna(0)

            fig = px.imshow(
                pivot_msg,
                title="Heatmap of Message Volume by Day & Hour",
                labels=dict(x="Hour", y="Day", color="Volume")
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
            y=['total_calls','total_bookings'],
            title="Agent Performance (Calls vs. Bookings)",
            barmode='group'
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
            y=['total_outbound_calls','successful_calls'],
            title="Agent Outbound Success Rate",
            barmode='group'
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
    # 15. CALL VOLUME HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Call Volume Heatmap")
    if not calls.empty:
        call_heatmap_data = calls.groupby(['day','hour']).size().reset_index(name='count')
        if not call_heatmap_data.empty:
            pivot_call = call_heatmap_data.pivot(index='day', columns='hour', values='count')
            pivot_call.index = pivot_call.index.astype(str)
            pivot_call.columns = pivot_call.columns.astype(str)
            adays = [d for d in day_order if d in pivot_call.index]
            ahours = [h for h in hour_order if h in pivot_call.columns]
            pivot_call = pivot_call.reindex(index=adays, columns=ahours).fillna(0)

            fig = px.imshow(
                pivot_call,
                title="Heatmap of Call Volume by Day & Hour",
                labels=dict(x="Hour", y="Day", color="Volume")
            )
            st.plotly_chart(fig)
    else:
        st.warning("No calls to display in the volume heatmap.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 16. SUCCESSFUL OUTBOUND CALLS HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Successful Outbound Calls Heatmap")
    if not successful_outbound_calls.empty:
        so_data = successful_outbound_calls.groupby(['day','hour']).size().reset_index(name='count')
        pivot_so = so_data.pivot(index='day', columns='hour', values='count')
        pivot_so.index = pivot_so.index.astype(str)
        pivot_so.columns = pivot_so.columns.astype(str)
        adays = [d for d in day_order if d in pivot_so.index]
        ahours = [h for h in hour_order if h in pivot_so.columns]
        pivot_so = pivot_so.reindex(index=adays, columns=ahours).fillna(0)

        fig = px.imshow(
            pivot_so,
            title="Heatmap of Successful Outbound Calls by Day & Hour",
            labels=dict(x="Hour", y="Day", color="Volume"),
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig)

        # Compare Agents
        st.subheader("Compare Agents: Successful Outbound Calls Heatmap by Day & Hour")
        agent_so_df = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='count')
        for full_email in selected_emails:
            adf = agent_so_df[agent_so_df['userId'] == full_email]
            if adf.empty:
                st.write(f"No successful outbound calls for agent: {full_email}")
                continue

            pivot_a = adf.pivot(index='day', columns='hour', values='count')
            pivot_a.index = pivot_a.index.astype(str)
            pivot_a.columns = pivot_a.columns.astype(str)

            a_days = [d for d in day_order if d in pivot_a.index]
            a_hours = [h for h in hour_order if h in pivot_a.columns]
            pivot_a = pivot_a.reindex(index=a_days, columns=a_hours).fillna(0)

            short_name = [k for k,v in agent_map.items() if v == full_email]
            short_name = short_name[0] if short_name else full_email

            fig = px.imshow(
                pivot_a,
                color_continuous_scale='Blues',
                labels=dict(x="Hour", y="Day", color="Count"),
                title=f"Successful Outbound Calls - {short_name}"
            )
            st.plotly_chart(fig)
    else:
        st.warning("No successful outbound calls found in the selected filters.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 17. AGENT SUCCESS RATE HEATMAP
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Agent Success Rate Heatmap (Day & Hour)")
    if not outbound_calls.empty:
        grp_outbound = outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='outbound_count')
        grp_success = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='success_count')

        grp_outbound['day'] = grp_outbound['day'].astype(str)
        grp_outbound['hour'] = grp_outbound['hour'].astype(str)
        grp_success['day'] = grp_success['day'].astype(str)
        grp_success['hour'] = grp_success['hour'].astype(str)

        merged_rate = pd.merge(grp_outbound, grp_success, on=['userId','day','hour'], how='outer').fillna(0)
        merged_rate['success_rate'] = (merged_rate['success_count'] / merged_rate['outbound_count'] * 100)

        for full_email in selected_emails:
            agent_df = merged_rate[merged_rate['userId'] == full_email]
            if agent_df.empty:
                st.write(f"No outbound calls for agent: {full_email}")
                continue

            pivot_srate = agent_df.pivot(index='day', columns='hour', values='success_rate')
            pivot_srate.index = pivot_srate.index.astype(str)
            pivot_srate.columns = pivot_srate.columns.astype(str)

            a_days = [d for d in day_order if d in pivot_srate.index]
            a_hours = [h for h in hour_order if h in pivot_srate.columns]
            pivot_srate = pivot_srate.reindex(index=a_days, columns=a_hours).fillna(0)

            short_name = [k for k,v in agent_map.items() if v == full_email]
            short_name = short_name[0] if short_name else full_email

            fig = px.imshow(
                pivot_srate,
                color_continuous_scale='Blues',
                labels=dict(x="Hour", y="Day", color="Success Rate (%)"),
                title=f"Success Rate Heatmap - {short_name}"
            )
            fig.update_xaxes(side="top")
            fig.update_layout(coloraxis=dict(cmin=0, cmax=100))
            st.plotly_chart(fig)
    else:
        st.warning("No outbound calls for success rate heatmap.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 18A. PRECEDING TEXT STATS (Sankey for Text < X min vs No Text → Call → Success/Fail)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Sankey: Call with/without Preceding Text within X Minutes, Then Success/Fail")

    text_window = st.slider(
        "Minutes for 'Text < X min' before Call",
        min_value=1,
        max_value=720,
        value=60,
        help="If there's a text from the same phoneNumber in the last X minutes, label calls as 'Text < X min'."
    )

    if not calls.empty:
        # Sort all interactions
        all_sorted = openphone_data.sort_values(by='createdAtET').reset_index(drop=True)

        def is_success(row):
            return (row['status'] == 'completed')  # or adapt your logic

        # We'll store last_text_time for each phoneNumber
        last_text_time = {}
        text_bucket = []

        for _, row in all_sorted.iterrows():
            # If direction in 'direction' col, phoneNumber in 'phoneNumber' col
            # If missing, adapt accordingly.
            phone = row['phoneNumber']

            if row['type'] == 'message':
                # update last text time
                last_text_time[phone] = row['createdAtET']
                text_bucket.append(None)
            elif row['type'] == 'call':
                if phone in last_text_time:
                    delta_sec = (row['createdAtET'] - last_text_time[phone]).total_seconds()
                    if delta_sec <= text_window * 60:
                        text_bucket.append("Text < X min")
                    else:
                        text_bucket.append("No Text")
                else:
                    text_bucket.append("No Text")
            else:
                text_bucket.append(None)

        all_sorted['text_bucket'] = text_bucket
        # Only calls
        sankey_calls = all_sorted[all_sorted['type'] == 'call'].copy()
        sankey_calls.dropna(subset=['text_bucket'], inplace=True)

        sankey_calls['call_result'] = sankey_calls.apply(
            lambda r: "Success" if is_success(r) else "Fail",
            axis=1
        )

        text_count = len(sankey_calls[sankey_calls['text_bucket'] == "Text < X min"])
        no_text_count = len(sankey_calls[sankey_calls['text_bucket'] == "No Text"])
        success_count = len(sankey_calls[sankey_calls['call_result'] == "Success"])
        fail_count = len(sankey_calls[sankey_calls['call_result'] == "Fail"])

        source = []
        target = []
        value  = []

        # Node indexes:
        # 0 = "Text < X min"
        # 1 = "No Text"
        # 2 = "Call"
        # 3 = "Call Success"
        # 4 = "Call Fail"

        source.append(0); target.append(2); value.append(text_count)
        source.append(1); target.append(2); value.append(no_text_count)
        source.append(2); target.append(3); value.append(success_count)
        source.append(2); target.append(4); value.append(fail_count)

        labels = [
            f"Text < {text_window} min",
            "No Text",
            "Call",
            "Call Success",
            "Call Fail"
        ]

        sankey_fig = go.Figure(data=[go.Sankey(
            arrangement = "snap",
            node = dict(
                pad = 15,
                thickness = 20,
                line = dict(color="black", width=0.5),
                label = labels
            ),
            link = dict(
                source = source,
                target = target,
                value = value
            )
        )])
        sankey_fig.update_layout(
            title_text=f"Sankey: Text < {text_window} min vs. No Text → Call → Success/Fail",
            font_size=14
        )
        st.plotly_chart(sankey_fig)
    else:
        st.warning("No calls in data for Sankey diagram logic.")

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # 18B. SIDE-BY-SIDE HEATMAP: SUCCESSFUL OUTBOUND CALLS + SUCCESS RATE
    #    with max 2 agents per row: facet_col_wrap=2
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    st.subheader("Side-by-Side: Successful Calls (Count) vs. Success Rate per Agent (Max 2 Agents per Row)")

    # We'll reuse `outbound_calls` and `successful_outbound_calls`.
    if (len(selected_emails) >= 1) and (not successful_outbound_calls.empty) and (not outbound_calls.empty):
        # 1) Count dataset
        df_count = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='count')
        df_count['day'] = df_count['day'].astype(str)
        df_count['hour'] = df_count['hour'].astype(str)
        df_count['metric'] = "Count"
        df_count.rename(columns={'count': 'value'}, inplace=True)

        # 2) Success rate dataset
        df_outb = outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='outbound_count')
        df_succ = successful_outbound_calls.groupby(['userId','day','hour']).size().reset_index(name='success_count')
        merged_df = pd.merge(df_outb, df_succ, on=['userId','day','hour'], how='outer').fillna(0)
        merged_df['success_rate'] = (merged_df['success_count'] / merged_df['outbound_count']) * 100
        merged_df['day'] = merged_df['day'].astype(str)
        merged_df['hour'] = merged_df['hour'].astype(str)

        df_srate = merged_df[['userId','day','hour','success_rate']].copy()
        df_srate['metric'] = "Success Rate"
        df_srate.rename(columns={'success_rate': 'value'}, inplace=True)

        # 3) Combine
        combined = pd.concat([df_count, df_srate], ignore_index=True)

        # agent_display = short name
        combined['agent_display'] = combined['userId'].apply(
            lambda full: next((k for k,v in agent_map.items() if v == full), full)
        )

        # 4) Now we do a facet with 2 columns per row
        fig = px.density_heatmap(
            combined,
            x='hour',
            y='day',
            z='value',
            facet_col='agent_display',   # columns = each agent
            facet_row='metric',          # rows = (Count vs. Success Rate)
            facet_col_wrap=2,           # max 2 agents per row
            color_continuous_scale='Blues',
            category_orders={
                "hour": hour_order,
                "day": day_order,
                "metric": ["Count","Success Rate"], 
                "agent_display": sorted([k for k in agent_map.keys() if agent_map[k] in selected_emails])
            },
            title="Side-by-Side: Successful Calls vs. Success Rate (2 Agents Per Row)",
            text_auto=True
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Not enough agents or data to show side-by-side calls vs. success rate.")

    st.success("Enhanced Dashboard Complete!")
